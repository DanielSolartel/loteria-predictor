"""Tests del caso de uso `SimularReferenciaAzarUniforme` -Etapa AE-49,
validada. Repositorios fake con historicos sinteticos: nunca
PostgreSQL ni resultados reales."""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from app.application.simulaciones import montecarlo_uniforme as mc
from app.application.use_cases import simular_referencia_azar_uniforme as modulo_caso
from app.application.use_cases.simular_referencia_azar_uniforme import SimularReferenciaAzarUniforme
from app.domain.games.baloto import BalotoGame
from tests.unit.simulaciones import sinteticos


def _caso(juegos=None, resultados=None, iteraciones=5, semilla=3):
    juegos = juegos or sinteticos.JuegoRepositoryFake()
    resultados = resultados or sinteticos.ResultadosRepositoryFake()
    return SimularReferenciaAzarUniforme(juegos, resultados, iteraciones=iteraciones, semilla=semilla), juegos, resultados


def test_valores_por_defecto_son_las_constantes_fijadas():
    caso = SimularReferenciaAzarUniforme(sinteticos.JuegoRepositoryFake(), sinteticos.ResultadosRepositoryFake())
    assert (caso.semilla, caso.iteraciones) == (mc.SEMILLA_AE49, mc.ITERACIONES_AE49)


def test_consulta_solo_baloto_y_revancha_con_corte_2705():
    caso, juegos, resultados = _caso()
    reporte = caso.ejecutar("0006")
    assert juegos.consultas == ["BALOTO", "BALOTO_REVANCHA"]
    assert "MILOTO" not in juegos.consultas
    assert resultados.consultas == [(sinteticos.ID_BALOTO, 2705), (sinteticos.ID_REVANCHA, 2705)]
    assert [j["codigo"] for j in reporte["juegos"]] == ["BALOTO", "BALOTO_REVANCHA"]
    assert reporte["alembic_revision"] == "0006"


def test_reporte_con_huella_y_totales_por_juego():
    caso, _, _ = _caso()
    reporte = caso.ejecutar("0006")
    baloto, revancha = reporte["juegos"]
    assert baloto["entrada_sha256"] == mc.huella_entrada("BALOTO", sinteticos.historico_baloto())
    assert revancha["entrada_sha256"] == mc.huella_entrada("BALOTO_REVANCHA", sinteticos.historico_revancha())
    assert (baloto["total_sorteos"], baloto["total_transiciones"], baloto["total_superbalotas"]) == (625, 624, 625)
    assert reporte["parametros"]["semilla"] == 3 and reporte["parametros"]["iteraciones"] == 5


def test_semillas_derivadas_por_juego(monkeypatch):
    capturadas = []
    original = mc.comparar_juego

    def espia(historico, params, *, semilla, iteraciones):
        capturadas.append((params.codigo, semilla))
        return original(historico, params, semilla=semilla, iteraciones=iteraciones)

    caso, _, _ = _caso()
    monkeypatch.setattr(modulo_caso, "comparar_juego", espia)
    caso.ejecutar("0006")
    assert capturadas == [
        ("BALOTO", mc.semilla_por_juego(3, "BALOTO")),
        ("BALOTO_REVANCHA", mc.semilla_por_juego(3, "BALOTO_REVANCHA")),
    ]


def test_mismo_insumo_mismo_reporte():
    assert _caso()[0].ejecutar("0006") == _caso()[0].ejecutar("0006")


def test_juego_inexistente_es_entrada_invalida():
    juegos = sinteticos.JuegoRepositoryFake({"BALOTO": sinteticos.juego("BALOTO", sinteticos.ID_BALOTO)})
    caso, _, _ = _caso(juegos=juegos)
    with pytest.raises(mc.EntradaSimulacionInvalidaError, match="BALOTO_REVANCHA"):
        caso.ejecutar("0006")


@pytest.mark.parametrize("cambio", [
    {"rango_max": 45}, {"cantidad_numeros": 6}, {"superbalota_max": 15}, {"tiene_superbalota": False},
])
def test_parametros_de_bd_distintos_del_dominio_son_entrada_invalida(cambio):
    juegos = sinteticos.JuegoRepositoryFake({
        "BALOTO": sinteticos.juego("BALOTO", sinteticos.ID_BALOTO, **cambio),
        "BALOTO_REVANCHA": sinteticos.juego("BALOTO_REVANCHA", sinteticos.ID_REVANCHA),
    })
    caso, _, _ = _caso(juegos=juegos)
    with pytest.raises(mc.EntradaSimulacionInvalidaError):
        caso.ejecutar("0006")


def test_historico_fuera_de_rango_es_entrada_invalida():
    historicos = {
        sinteticos.ID_BALOTO: sinteticos.historico_baloto()[:-1],
        sinteticos.ID_REVANCHA: sinteticos.historico_revancha(),
    }
    caso, _, _ = _caso(resultados=sinteticos.ResultadosRepositoryFake(historicos))
    with pytest.raises(mc.EntradaSimulacionInvalidaError):
        caso.ejecutar("0006")


def test_fallo_en_el_segundo_juego_se_propaga_sin_reporte_parcial():
    caso, _, _ = _caso(resultados=sinteticos.ResultadosRepositoryFake(fallar_en=sinteticos.ID_REVANCHA))
    with pytest.raises(RuntimeError, match="fallo sintetico"):
        caso.ejecutar("0006")


@pytest.mark.parametrize("iteraciones", [0, -1, True, 2.0])
def test_iteraciones_invalidas(iteraciones):
    with pytest.raises(ValueError):
        SimularReferenciaAzarUniforme(sinteticos.JuegoRepositoryFake(), sinteticos.ResultadosRepositoryFake(),
                                      iteraciones=iteraciones)


def test_caso_de_uso_no_importa_ml_infraestructura_ni_escribe():
    ruta = Path(modulo_caso.__file__)
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            modulo = nodo.module or ""
            assert not modulo.startswith(("app.application.ml", "app.infrastructure", "sqlalchemy")), modulo
    texto = ruta.read_text(encoding="utf-8")
    for prohibido in ("guardar(", ".add(", "commit(", "SimulacionORM", "INSERT", "UPDATE", "DELETE"):
        assert prohibido not in texto, prohibido


def test_dataclass_de_parametros_es_inmutable():
    params = mc.parametros_desde_dominio("BALOTO", BalotoGame())
    with pytest.raises(dataclasses.FrozenInstanceError):
        params.rango_max = 99
