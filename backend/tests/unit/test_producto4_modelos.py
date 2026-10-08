"""Producto 4: entrenamiento real de las familias nuevas, validez de las
probabilidades y estados explicitos (sin fallback disfrazado)."""
from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import pronostico_colorloto as pcl
from tests.unit import fixtures_producto4 as f4

NUEVOS = {"BALOTO": ("logistica_regularizada", "hgb_clasificador"),
          "BALOTO_REVANCHA": ("logistica_regularizada", "hgb_clasificador"),
          "MILOTO": ("logistica_regularizada", "hgb_clasificador"),
          "COLORLOTO": ("poisson_regularizado", "hgb_poisson")}


def _instantanea(codigo, n, semilla=1):
    return lv.validar_instantanea(codigo, f4.historico(codigo, n, semilla))


@pytest.fixture(scope="module")
def evaluaciones_reales():
    """Recetas PREDETERMINADAS sobre historicos sinteticos del tamano real
    (Baloto y Revancha 638, MiLoto corta de 87, ColorLoto 224)."""
    return {c: le.evaluar(_instantanea(c, n), lm.candidatos_del_juego(c), le.Protocolo())[0]
            for c, n in f4.TAMANOS_REALES.items()}


@pytest.mark.parametrize("codigo", list(NUEVOS))
def test_las_dos_familias_nuevas_se_entrenan_en_los_cuatro_juegos(evaluaciones_reales, codigo):
    informe = evaluaciones_reales[codigo]
    por_id = {c["id"]: c for c in informe["candidatos"]}
    for modelo in NUEVOS[codigo]:
        c = por_id[modelo]
        assert c["tipo"] == "modelo_nuevo" and c["estado"] == "completo", c["incidencias"]
        assert c["objetivos_evaluados"] == informe["muestra_comun"]["total_objetivos"]
        assert all(b["estado"] == "evaluado" for b in c["bloques"])
        assert all(math.isfinite(f["log_loss"]) for f in c["por_objetivo"])
    assert informe["resumen"]["estado"] in ("menor_perdida_en_esta_evaluacion", "la_uniforme_fue_mejor", "empate")


def test_miloto_corta_compara_completa_sin_la_ventana_de_50(evaluaciones_reales):
    informe = evaluaciones_reales["MILOTO"]
    assert informe["muestra_comun"]["total_objetivos"] == 87 - 50  # 20 de calentamiento + 30 de ajuste
    assert [len(b["objetivos"]) for b in informe["muestra_comun"]["bloques"]] == [10, 10, 10, 7]
    assert informe["muestra_comun"]["muestra_pequena"] is True
    assert {c["estado"] for c in informe["candidatos"]} == {"completo"}


def test_baloto_real_incluye_la_receta_actual_completa(evaluaciones_reales):
    c = {c["id"]: c for c in evaluaciones_reales["BALOTO"]["candidatos"]}["actual_logistica_ae36"]
    assert c["estado"] == "completo" and c["tipo"] == "referencia"
    assert evaluaciones_reales["BALOTO"]["superbalota"]["sorteos"] == 60


@pytest.mark.parametrize("codigo", ["BALOTO", "MILOTO", "COLORLOTO"])
def test_probabilidades_validas_y_cardinalidad(codigo):
    instantanea = _instantanea(codigo, f4.TAMANOS_PEQUENOS[codigo])
    variables = lv.Variables(instantanea)
    n = len(instantanea)
    for modelo in NUEVOS[codigo]:
        ajustado = lm.ajustar_candidato(lm.CATALOGO[modelo], instantanea, variables, n)
        filas = variables.filas([n])
        p = ajustado.predecir(filas)
        assert np.all(np.isfinite(p)) and np.all(p > 0) and np.all(p < 1)
        if codigo == "COLORLOTO":
            assert len(p) == 7 * len(instantanea.paleta())
            assert abs(p.sum() - 1) < 1e-12  # distribucion de pares normalizada
        else:
            assert len(p) == len(instantanea.reglas.candidatos)  # soporte completo
            assert abs(p.sum() - 5) <= lm.TOLERANCIA_CARDINALIDAD


def test_ajuste_de_cardinalidad_estable_acotado_y_determinista():
    rng = np.random.default_rng(0)
    for _ in range(50):
        crudas = rng.uniform(0, 1, 43)
        a = lm.ajustar_cardinalidad(crudas, 5)
        assert abs(a.sum() - 5) <= 1e-9 and a.max() < 1 and a.min() > 0
        assert np.array_equal(a, lm.ajustar_cardinalidad(crudas, 5))
        assert np.array_equal(np.argsort(-a, kind="stable"), np.argsort(-np.clip(crudas, 1e-6, 1 - 1e-6), kind="stable"))
    extremas = np.array([1.0] * 6 + [0.0] * 37)  # una division simple daria valores > 1
    a = lm.ajustar_cardinalidad(extremas, 5)
    assert a.max() < 1 and abs(a.sum() - 5) <= 1e-9
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        lm.ajustar_cardinalidad([0.1, float("nan"), 0.2], 1)
    assert error.value.estado == "salida_invalida"


def test_normalizacion_de_intensidades():
    p = lm.normalizar_intensidades([0.0, 1.0, 3.0])
    assert abs(p.sum() - 1) < 1e-15 and p[0] > 0
    with pytest.raises(lm.CandidatoNoDisponible):
        lm.normalizar_intensidades([1.0, float("inf")])


def test_referencias_conservan_sus_probabilidades_originales():
    from app.application.ml import pronostico_miloto as pml
    instantanea = _instantanea("MILOTO", 87)
    variables = lv.Variables(instantanea)
    ajustado = lm.ajustar_candidato(lm.CATALOGO["actual_frecuencia_contraida"], instantanea, variables, 60)
    filas = variables.filas([60])
    esperadas = pml.probabilidades_de_inclusion(instantanea.sorteos[:60], pml.ConfiguracionMiLoto())
    assert ajustado.predecir(filas).tolist() == [esperadas[c] for c in filas.candidatos]
    color = _instantanea("COLORLOTO", 90)
    v = lv.Variables(color)
    p = lm.ajustar_candidato(lm.CATALOGO["actual_multinomial_suavizada"], color, v, 60).predecir(v.filas([60]))
    d = pcl.distribucion_de_pares(color.sorteos[:60], pcl.ConfiguracionColorLoto())
    assert np.allclose(p, [d[tuple(c)] for c in v.filas([60]).candidatos], rtol=0, atol=1e-15)


def test_colorloto_conserva_multiplicidades_y_seis_pares():
    instantanea = _instantanea("COLORLOTO", 90)
    v = lv.Variables(instantanea)
    filas = v.filas([60])
    assert set(filas.y.tolist()) <= set(range(7)) and filas.y.sum() == 6  # conteos 0..6, no binarios
    repetidos = [i for i, r in enumerate(instantanea.sorteos) if len(set(r.pares)) < 6]
    assert repetidos, "la fixture debe tener multiconjuntos con pares repetidos"
    i = next(i for i in repetidos if i >= lv.CALENTAMIENTO)
    assert v.filas([i]).y.max() >= 2


def test_no_convergencia_es_un_estado_explicito():
    instantanea = _instantanea("MILOTO", 87)
    entrada = dataclasses.replace(lm.CATALOGO["logistica_regularizada"],
                                  parametros={**lm.CATALOGO["logistica_regularizada"].parametros, "max_iter": 1})
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        lm.ajustar_candidato(entrada, instantanea, lv.Variables(instantanea), 70)
    assert error.value.estado == "no_converge"
    informe, _ = le.evaluar(instantanea, [lm.CATALOGO["uniforme"], entrada], le.Protocolo(bloques=1))
    c = informe["candidatos"][1]
    assert c["estado"] == "no_disponible" and c["agregado"] is None and c["incidencias"][0]["estado"] == "no_converge"
    assert informe["resumen"]["estado"] == "comparacion_incompleta"


def test_clase_insuficiente_y_salida_invalida_sin_fallback(monkeypatch):
    instantanea = _instantanea("MILOTO", 87)
    variables = lv.Variables(instantanea)
    original = variables.de_ajuste
    monkeypatch.setattr(variables, "de_ajuste",
                        lambda corte: dataclasses.replace(original(corte), y=np.zeros(len(original(corte)))))
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        lm.ajustar_candidato(lm.CATALOGO["hgb_clasificador"], instantanea, variables, 70)
    assert error.value.estado == "clase_insuficiente"
    monkeypatch.undo()
    ajustado = lm.ajustar_candidato(lm.CATALOGO["logistica_regularizada"], instantanea, lv.Variables(instantanea), 70)
    monkeypatch.setattr(ajustado, "_predecir", lambda f: np.full(len(f), np.nan))
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        ajustado.predecir(lv.Variables(instantanea).filas([70]))
    assert error.value.estado == "salida_invalida"


def test_ausencia_de_datos_y_muestra_insuficiente():
    corta = _instantanea("MILOTO", 55)
    with pytest.raises(le.MuestraInsuficienteError):
        le.muestra_comun(corta, le.Protocolo())
    with pytest.raises(lv.HistoricoNoValidoError):
        lv.validar_instantanea("MILOTO", [])
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        lm.ajustar_candidato(lm.CATALOGO["logistica_regularizada"], corta, lv.Variables(corta), 40)
    assert error.value.estado == "muestra_insuficiente"


def test_paleta_nueva_se_excluye_con_motivo_y_el_codificador_ignora_lo_no_visto():
    historico = f4.historico("COLORLOTO", 90)
    cambiado = list(historico)
    r = cambiado[85]
    cambiado[85] = dataclasses.replace(r, pares=((1, "MORADO"), *r.pares[1:]))
    instantanea = lv.validar_instantanea("COLORLOTO", cambiado)
    muestra = le.muestra_comun(instantanea, le.Protocolo())
    assert [x["objetivo"] for x in muestra["excluidos"]] == [cambiado[85].numero_sorteo]
    assert muestra["excluidos"][0]["motivo"] == "color_fuera_de_la_paleta_del_corte"
    assert "MORADO" not in instantanea.paleta(85)
    informe, _ = le.evaluar(instantanea, lm.candidatos_del_juego("COLORLOTO"), le.Protocolo())
    assert all(cambiado[85].numero_sorteo not in [f["objetivo"] for f in c["por_objetivo"]]
               for c in informe["candidatos"])
    v = lv.Variables(instantanea)  # MORADO ya forma parte de la paleta del objetivo siguiente
    for modelo in NUEVOS["COLORLOTO"]:
        p = lm.ajustar_candidato(lm.CATALOGO[modelo], instantanea, v, 70).predecir(v.filas([90]))
        assert np.all(np.isfinite(p)) and abs(p.sum() - 1) < 1e-12


def test_catalogo_rotula_referencias_y_modelos_nuevos():
    for codigo in lv.JUEGOS:
        entradas = lm.candidatos_del_juego(codigo)
        assert sum(e.tipo == "modelo_nuevo" for e in entradas) == 2
        assert sum(e.familia == "uniforme" for e in entradas) == 1
        assert sum(e.familia == "estrategia_actual" for e in entradas) == 1
        for e in entradas:
            assert e.id and e.version and e.explicacion and e.variables
    assert lm.CATALOGO["hgb_clasificador"].parametros["early_stopping"] is False
    assert lm.CATALOGO["hgb_poisson"].parametros["early_stopping"] is False
