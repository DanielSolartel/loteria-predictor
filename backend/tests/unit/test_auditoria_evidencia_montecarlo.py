"""Tests de `scripts/auditoria_evidencia_montecarlo.py` -Etapa AE-51,
validada: auditoria de una evidencia AE-49 frente al historico
actual 2081..2705 (huella normalizada de entrada, totales y
estadisticas observadas). Todo sintetico: repositorios fake e
historicos generados con formulas; nunca PostgreSQL ni datos reales."""
from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pytest

from app.application.simulaciones import montecarlo_uniforme as mc
from scripts import auditoria_evidencia_montecarlo as aud
from scripts import verificacion_evidencia_montecarlo as verif
from tests.unit.simulaciones import evidencia_auditable as ea
from tests.unit.simulaciones import sinteticos

ARCHIVO = Path(aud.__file__)


def _auditar(reporte, historicos=None, juegos=None):
    return aud.auditar_contra_historico(
        reporte, juegos or sinteticos.JuegoRepositoryFake(), sinteticos.ResultadosRepositoryFake(historicos),
    )


def _con_sorteo_cambiado(historico, numero_sorteo=2400, numeros=(1, 2, 3, 4, 5)):
    return [dataclasses.replace(r, numeros=numeros) if r.numero_sorteo == numero_sorteo else r for r in historico]


# ---------------------------------------------------------------------------
# Lectura: siempre AE-50 primero
# ---------------------------------------------------------------------------

class TestLectura:
    def test_evidencia_auditable_pasa_ae50_y_se_devuelve_parseada(self):
        contenido = ea.evidencia_auditable()
        resumen, reporte = aud.leer_evidencia_validada(contenido)
        assert resumen == verif.validar_evidencia(contenido)
        assert reporte == ea.reporte_auditable()

    @pytest.mark.parametrize("contenido, error", [
        (b"{roto", verif.EvidenciaIlegibleError),
        (b"[]\n", verif.EvidenciaInvalidaError),
    ])
    def test_errores_de_ae50_se_propagan(self, contenido, error):
        with pytest.raises(error):
            aud.leer_evidencia_validada(contenido)


# ---------------------------------------------------------------------------
# Comparacion con el historico actual
# ---------------------------------------------------------------------------

class TestComparacion:
    def test_coincide_todo(self):
        juegos = _auditar(ea.reporte_auditable())
        assert [j["codigo"] for j in juegos] == ["BALOTO", "BALOTO_REVANCHA"]
        for juego in juegos:
            assert juego["huella_coincide"] is True
            assert juego["totales_coinciden"] is True
            assert [e["nombre"] for e in juego["estadisticas_observadas"]] == list(mc.ESTADISTICAS_AE49)
            assert all(e["coincide"] is True for e in juego["estadisticas_observadas"])
            assert juego["entrada_sha256_evidencia"] == juego["entrada_sha256_actual"]

    def test_lee_solo_hasta_2705_y_solo_baloto_y_revancha(self):
        juegos_repo = sinteticos.JuegoRepositoryFake()
        resultados_repo = sinteticos.ResultadosRepositoryFake()
        aud.auditar_contra_historico(ea.reporte_auditable(), juegos_repo, resultados_repo)
        assert juegos_repo.consultas == ["BALOTO", "BALOTO_REVANCHA"]
        assert resultados_repo.consultas == [(sinteticos.ID_BALOTO, 2705), (sinteticos.ID_REVANCHA, 2705)]

    def test_datos_actuales_distintos_no_coinciden(self):
        historicos = {
            sinteticos.ID_BALOTO: _con_sorteo_cambiado(sinteticos.historico_baloto()),
            sinteticos.ID_REVANCHA: sinteticos.historico_revancha(),
        }
        baloto, revancha = _auditar(ea.reporte_auditable(), historicos)
        assert baloto["huella_coincide"] is False
        assert baloto["entrada_sha256_actual"] != baloto["entrada_sha256_evidencia"]
        assert not all(e["coincide"] for e in baloto["estadisticas_observadas"])
        assert revancha["huella_coincide"] is True
        assert all(e["coincide"] for e in revancha["estadisticas_observadas"])

    def test_observado_alterado_en_la_evidencia_se_detecta_con_huella_igual(self):
        reporte = ea.copia(ea.reporte_auditable())
        reporte["juegos"][1]["estadisticas"][1]["observado"] += 1
        baloto, revancha = _auditar(reporte)
        assert revancha["huella_coincide"] is True
        coincidencias = [e["coincide"] for e in revancha["estadisticas_observadas"]]
        assert coincidencias == [True, False, True, True]
        assert all(e["coincide"] for e in baloto["estadisticas_observadas"])

    def test_huella_alterada_en_la_evidencia_se_detecta(self):
        reporte = ea.copia(ea.reporte_auditable())
        reporte["juegos"][0]["entrada_sha256"] = "f" * 64
        baloto, _ = _auditar(reporte)
        assert baloto["huella_coincide"] is False
        assert all(e["coincide"] for e in baloto["estadisticas_observadas"])

    def test_comparacion_de_observados_distingue_tipos(self):
        reporte = ea.copia(ea.reporte_auditable())
        valor = reporte["juegos"][0]["estadisticas"][1]["observado"]
        reporte["juegos"][0]["estadisticas"][1]["observado"] = float(valor)
        baloto, _ = _auditar(reporte)
        assert baloto["estadisticas_observadas"][1]["coincide"] is False


class TestHistoricoActualInvalido:
    @pytest.mark.parametrize("mutar", [
        lambda h: h[:-1],
        lambda h: [dataclasses.replace(h[0], numero_sorteo=2080)] + h,
        lambda h: [dataclasses.replace(r, superbalota=None) if r.numero_sorteo == 2400 else r for r in h],
    ])
    def test_historico_fuera_de_contrato(self, mutar):
        historicos = {
            sinteticos.ID_BALOTO: mutar(sinteticos.historico_baloto()),
            sinteticos.ID_REVANCHA: sinteticos.historico_revancha(),
        }
        with pytest.raises(mc.EntradaSimulacionInvalidaError):
            _auditar(ea.reporte_auditable(), historicos)

    def test_juego_inexistente(self):
        juegos = sinteticos.JuegoRepositoryFake({"BALOTO": sinteticos.juego("BALOTO", sinteticos.ID_BALOTO)})
        with pytest.raises(mc.EntradaSimulacionInvalidaError, match="BALOTO_REVANCHA"):
            _auditar(ea.reporte_auditable(), juegos=juegos)

    @pytest.mark.parametrize("cambio", [{"rango_max": 45}, {"superbalota_max": 15}, {"cantidad_numeros": 6}])
    def test_parametros_de_bd_distintos_del_dominio(self, cambio):
        juegos = sinteticos.JuegoRepositoryFake({
            "BALOTO": sinteticos.juego("BALOTO", sinteticos.ID_BALOTO, **cambio),
            "BALOTO_REVANCHA": sinteticos.juego("BALOTO_REVANCHA", sinteticos.ID_REVANCHA),
        })
        with pytest.raises(mc.EntradaSimulacionInvalidaError):
            _auditar(ea.reporte_auditable(), juegos=juegos)

    def test_fallo_del_repositorio_se_propaga(self):
        repo = sinteticos.ResultadosRepositoryFake(fallar_en=sinteticos.ID_REVANCHA)
        with pytest.raises(RuntimeError):
            aud.auditar_contra_historico(ea.reporte_auditable(), sinteticos.JuegoRepositoryFake(), repo)


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def _informe(reporte=None, historicos=None, revision_actual="0006"):
    reporte = reporte or ea.reporte_auditable()
    contenido = json.dumps(reporte).encode()
    resumen = {"sha256": "a" * 64, "bytes": len(contenido), "juegos": []}
    return aud.construir_informe_auditoria(resumen, reporte, _auditar(reporte, historicos), revision_actual)


class TestInforme:
    def test_claves_y_resultado_coincide(self):
        informe = _informe()
        assert set(informe) == {
            "esquema", "resultado", "evidencia", "alembic_revision_evidencia", "alembic_revision_actual",
            "misma_revision_alembic", "rango_auditado", "juegos", "comprobado", "no_comprobado", "alcance",
        }
        assert informe["esquema"] == "auditoria-evidencia-montecarlo/1.0"
        assert informe["resultado"] == "coincide"
        assert informe["evidencia"] == {"sha256": "a" * 64, "bytes": informe["evidencia"]["bytes"]}
        assert informe["rango_auditado"] == {"desde": 2081, "hasta": 2705}
        assert informe["comprobado"] == list(aud.COMPROBADO)
        assert informe["no_comprobado"] == list(aud.NO_COMPROBADO)
        assert informe["alcance"] == aud.ALCANCE_AUDITORIA

    def test_cualquier_discrepancia_da_no_coincide(self):
        reporte = ea.copia(ea.reporte_auditable())
        reporte["juegos"][1]["estadisticas"][2]["observado"] = 0.25
        assert _informe(reporte)["resultado"] == "no_coincide"
        reporte = ea.copia(ea.reporte_auditable())
        reporte["juegos"][0]["entrada_sha256"] = "0" * 64
        assert _informe(reporte)["resultado"] == "no_coincide"

    def test_revision_alembic_distinta_es_informativa(self):
        informe = _informe(revision_actual="0007")
        assert informe["misma_revision_alembic"] is False
        assert (informe["alembic_revision_evidencia"], informe["alembic_revision_actual"]) == ("0006", "0007")
        assert informe["resultado"] == "coincide"

    def test_no_publica_valores_estadisticos(self):
        informe = _informe()

        def claves(nodo):
            if isinstance(nodo, dict):
                for clave, valor in nodo.items():
                    yield clave
                    yield from claves(valor)
            elif isinstance(nodo, list):
                for valor in nodo:
                    yield from claves(valor)

        assert set(claves(informe)) == {
            "esquema", "resultado", "evidencia", "sha256", "bytes", "alembic_revision_evidencia",
            "alembic_revision_actual", "misma_revision_alembic", "rango_auditado", "desde", "hasta", "juegos",
            "codigo", "entrada_sha256_evidencia", "entrada_sha256_actual", "huella_coincide", "totales_coinciden",
            "estadisticas_observadas", "nombre", "coincide", "comprobado", "no_comprobado", "alcance",
        }

    def test_no_comprobado_y_alcance_explicitos(self):
        assert set(aud.NO_COMPROBADO) >= {
            "simulacion_monte_carlo_no_repetida", "medias_y_desviaciones_simuladas", "percentiles_y_p_valores",
            "bonferroni_y_umbral_frente_a_datos", "procedencia_historica_del_archivo", "tramo_2706_en_adelante",
        }
        for fragmento in ("READ ONLY", "ROLLBACK", "no repite Monte Carlo", "no verifica", "p-valores",
                          "no prueba la procedencia historica", "exploratori", "no modifica el NO-GO de AE-39",
                          "2706 en adelante no se lee"):
            assert fragmento in aud.ALCANCE_AUDITORIA, fragmento


# ---------------------------------------------------------------------------
# Estructura: sin Monte Carlo, sin BD directa y sin escrituras
# ---------------------------------------------------------------------------

def _nombres_usados():
    arbol = ast.parse(ARCHIVO.read_text(encoding="utf-8"))
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            nombres.add(nodo.attr)
        elif isinstance(nodo, ast.ImportFrom):
            nombres.update(alias.name for alias in nodo.names)
            nombres.add(nodo.module or "")
        elif isinstance(nodo, ast.Import):
            nombres.update(alias.name for alias in nodo.names)
    return nombres


def test_no_repite_monte_carlo():
    nombres = _nombres_usados()
    for prohibido in ("comparar_juego", "simular_historia", "Random", "random", "semilla_por_juego",
                      "aplicar_correccion_bonferroni"):
        assert prohibido not in nombres, prohibido


def test_reutiliza_ae49_y_ae50_sin_modificarlos():
    nombres = _nombres_usados()
    for requerido in ("validar_evidencia", "verificar_rango_principal", "huella_entrada", "calcular_estadisticas",
                      "parametros_desde_dominio"):
        assert requerido in nombres, requerido


def test_modulo_sin_sqlalchemy_ml_ni_escrituras():
    nombres = _nombres_usados()
    for prohibido in ("sqlalchemy", "app.infrastructure", "app.application.ml", "open"):
        assert prohibido not in nombres, prohibido
    texto = ARCHIVO.read_text(encoding="utf-8")
    for prohibido in ("commit(", ".add(", "INSERT", "UPDATE", "DELETE", "resolver_estado_prediccion",
                      "diagnostico_bloqueo", "diagnosticar_estado_prediccion"):
        assert prohibido not in texto, prohibido
