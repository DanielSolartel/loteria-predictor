"""Producto 3: seguimiento acumulado del rendimiento. Las perdidas se
comparan con calculos independientes sobre fixtures pequenas; la politica
de una emision por objetivo se prueba contra versiones posteriores."""
from __future__ import annotations

import dataclasses
import math
from collections import Counter
from datetime import date

import pytest

from app.application.ml import pronostico_experimental as pe
from app.application.ml import pronostico_miloto as pm
from app.application.ml import rendimiento_observado as rm
from app.application.ml.registro_prospectivo import serializar_entrada
from app.application.use_cases import pronostico_experimental as uc
from app.application.use_cases.pronostico_experimental import GenerarPronosticoExperimental
from app.application.use_cases.rendimiento import ConsultarRendimiento
from tests.unit import fixtures_producto3 as f3

EPS = 1e-6


@pytest.fixture
def entorno(tmp_path):
    return f3.entorno(tmp_path)


def _generar(entorno, codigo, hasta=None, configuraciones=None, reloj=None):
    return GenerarPronosticoExperimental(entorno.juegos, entorno.resultados, entorno.almacen,
                                         reloj=reloj or f3.RELOJ,
                                         configuraciones=configuraciones or f3.CONFIGS).ejecutar(
        codigo, hasta_numero_sorteo=hasta)


def _rendimiento(entorno, codigo, **filtros):
    return ConsultarRendimiento(entorno.almacen, entorno.juegos, entorno.resultados).ejecutar(codigo, **filtros)


def _bce(p, y):
    p = min(max(p, EPS), 1 - EPS)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def test_perdidas_numeros_coinciden_con_calculo_independiente(entorno):
    for hasta in (60, 61, 62):
        _generar(entorno, "MILOTO", hasta=hasta)
    r = _rendimiento(entorno, "MILOTO")
    filas = [f for f in r["filas"] if f["estado"] == "incluido"]
    assert [f["objetivo"] for f in filas] == [61, 62, 63] and {f["tipo"] for f in filas} == {"retrospectiva"}
    reales = {x.numero_sorteo: set(x.numeros) for x in entorno.historicos["MILOTO"]}
    esperadas, uniformes = [], []
    for f in filas:
        ranking = entorno.almacen.obtener("MILOTO", f["identificador"]).artefacto["pronostico"]["ranking"]
        ll = sum(_bce(x["probabilidad"], int(x["numero"] in reales[f["objetivo"]])) for x in ranking) / 39
        llu = sum(_bce(5 / 39, int(x["numero"] in reales[f["objetivo"]])) for x in ranking) / 39
        assert math.isclose(f["metricas"]["log_loss"], ll, rel_tol=1e-9)
        assert math.isclose(f["metricas"]["log_loss_uniforme"], llu, rel_tol=1e-6)
        br = sum((x["probabilidad"] - int(x["numero"] in reales[f["objetivo"]])) ** 2 for x in ranking) / 39
        assert math.isclose(f["metricas"]["brier"], br, rel_tol=1e-9)
        esperadas.append(ll)
        uniformes.append(llu)
    agg = r["por_tipo"]["retrospectiva"]
    assert agg["incluidos"] == 3 and agg["muestra_pequena"] is True
    assert math.isclose(agg["perdidas"]["log_loss"]["modelo"], sum(esperadas) / 3, rel_tol=1e-9)
    assert math.isclose(agg["perdidas"]["log_loss"]["diferencia"], (sum(esperadas) - sum(uniformes)) / 3, rel_tol=1e-6)
    acumulada = [s["acumulada"] for s in agg["serie"]]
    assert math.isclose(acumulada[-1], sum(esperadas) - sum(uniformes), rel_tol=1e-6)
    assert agg["aciertos"]["suma"] == sum(f["aciertos"] for f in filas) and agg["aciertos"]["de"] == 5


def test_perdidas_colorloto_por_balota_y_multiconjunto(entorno):
    _generar(entorno, "COLORLOTO", hasta=50)
    fila = next(f for f in _rendimiento(entorno, "COLORLOTO")["filas"] if f["objetivo"] == 51)
    assert fila["estado"] == "incluido" and fila["de"] == 6
    a = entorno.almacen.obtener("COLORLOTO", fila["identificador"]).artefacto
    dist = {(x["numero"], x["color"]): x["probabilidad"] for x in a["pronostico"]["ranking_de_pares"]}
    pares = [tuple(p) for p in next(r for r in entorno.historicos["COLORLOTO"] if r.numero_sorteo == 51).pares]
    esperado = sum(-math.log(dist[p]) for p in pares) / 6
    assert math.isclose(fila["metricas"]["log_loss"], esperado, rel_tol=1e-12)
    m = len(dist)
    assert math.isclose(fila["metricas"]["log_loss_uniforme"], math.log(m), rel_tol=1e-9)
    conteo = Counter(pares)
    coef = math.factorial(6) / math.prod(math.factorial(k) for k in conteo.values())
    assert math.isclose(fila["metricas"]["log_loss_multiconjunto"],
                        -math.log(coef * math.prod(dist[p] ** k for p, k in conteo.items())), rel_tol=1e-9)


def test_superbalota_misma_definicion_que_la_evaluacion_walk_forward():
    """La metrica multiclase por objetivo, promediada con las probabilidades
    del walk-forward, reproduce el agregado de la superbalota del artefacto."""
    from tests.unit import fixtures_producto1 as fx
    historico = fx.historico_numerico("BALOTO", 80)
    objetivos = [r.numero_sorteo for r in historico[40:]]
    bloque = pe._superbalota(historico, (1, 16), objetivos, 12)
    previos, perdidas, brier = Counter(), [], []
    for i, r in enumerate(historico):
        if r.numero_sorteo in objetivos:
            p = {c: (previos[c] + 1) / (i + 16) for c in range(1, 17)}
            m = rm.metricas_multiclase(p, r.superbalota)
            perdidas.append(m["log_loss"])
            brier.append(m["brier"])
        previos[r.superbalota] += 1
    modelo = bloque["evaluacion_walk_forward"]["estrategia"]
    assert round(sum(perdidas) / len(perdidas), 12) == modelo["log_loss"]
    assert round(sum(brier) / len(brier), 12) == modelo["brier"]


def test_superbalota_separada_de_los_numeros(entorno):
    _generar(entorno, "BALOTO", hasta=2200)
    r = _rendimiento(entorno, "BALOTO")
    fila = r["filas"][0]
    real = next(x for x in entorno.historicos["BALOTO"] if x.numero_sorteo == 2201)
    a = entorno.almacen.obtener("BALOTO", fila["identificador"]).artefacto
    p = {x["superbalota"]: x["probabilidad"] for x in a["superbalota"]["pronostico"]["ranking"]}
    assert math.isclose(fila["superbalota"]["log_loss"], -math.log(p[real.superbalota]), rel_tol=1e-12)
    assert fila["superbalota"]["acierto"] == (a["superbalota"]["pronostico"]["sugerida"] == real.superbalota)
    sb = r["por_tipo"]["retrospectiva"]["superbalota"]
    assert sb["objetivos"] == 1 and math.isclose(sb["log_loss"]["uniforme"], math.log(16), rel_tol=1e-9)
    assert fila["de"] == 5  # numeros principales, sin la superbalota


def test_una_emision_por_objetivo_la_primera_aunque_haya_otra_version(entorno):
    v1 = _generar(entorno, "MILOTO", hasta=60)
    otra = {**f3.CONFIGS, "MILOTO": pm.ConfiguracionMiLoto(fuerza_previa=5.0)}
    v2 = _generar(entorno, "MILOTO", hasta=60, configuraciones=otra)
    assert v2.identificador != v1.identificador and v2.version == 2
    fila = _rendimiento(entorno, "MILOTO")["filas"][0]
    assert fila["identificador"] == v1.identificador and fila["versiones"] == 2 and fila["estado"] == "incluido"


def test_historico_cambiado_excluye_sin_sustituir_por_una_version_posterior(entorno):
    v1 = _generar(entorno, "MILOTO", hasta=60)
    mid = entorno.juegos.obtener_por_codigo("MILOTO").id
    entorno.resultados.numericos[mid] = [dataclasses.replace(r, numeros=(1, 2, 3, 4, 5)) if r.numero_sorteo == 10 else r
                                         for r in entorno.historicos["MILOTO"]]
    v2 = _generar(entorno, "MILOTO", hasta=60)  # coincide con la base actual
    assert v2.identificador != v1.identificador
    fila = _rendimiento(entorno, "MILOTO")["filas"][0]
    assert fila["identificador"] == v1.identificador and fila["estado"] == "excluido"
    assert fila["motivo"] == "historico_hasta_el_corte_cambio"


def test_artefacto_ilegible_y_orden_ambiguo_se_excluyen(entorno):
    _generar(entorno, "MILOTO", hasta=60)
    g = _generar(entorno, "MILOTO", hasta=61)
    ruta = next((entorno.almacen._directorio / "MILOTO").glob(f"62-{g.identificador}.json"))
    ruta.write_bytes(ruta.read_bytes()[:-5])  # alterado
    # Dos artefactos antiguos sin secuencia para el objetivo 64: orden ambiguo.
    carpeta = entorno.almacen._directorio / "MILOTO"
    h = uc._historicos(entorno.juegos, entorno.resultados, "MILOTO", 63)[0]
    for fuerza in (39.0, 7.0):
        cuerpo = uc._cuerpo("MILOTO", h, 63, pm.ConfiguracionMiLoto(fuerza_previa=fuerza))
        a = pe.componer_artefacto(cuerpo, generado_en="2026-10-01T12:00:00+00:00")
        (carpeta / f"64-{a['clave_de_entrada']}.json").write_bytes(serializar_entrada(a))
    r = _rendimiento(entorno, "MILOTO")
    motivos = {f["objetivo"]: (f["estado"], f["motivo"]) for f in r["filas"]}
    assert motivos[61] == ("incluido", None)
    assert motivos[62] == ("excluido", "artefacto_ilegible_en_el_objetivo")
    assert motivos[64] == ("excluido", "orden_de_emision_ambiguo")
    assert r["artefactos_ilegibles"] == 1


def test_tipos_separados_pendientes_filtros_y_denominadores(entorno):
    for hasta in (60, 61):
        _generar(entorno, "MILOTO", hasta=hasta, reloj=lambda: f3.RELOJ().replace(day=1))
    _generar(entorno, "MILOTO", reloj=lambda: f3.RELOJ().replace(day=5))  # objetivo 85, no cargado: seguimiento
    r = _rendimiento(entorno, "MILOTO")
    assert r["por_tipo"]["retrospectiva"]["incluidos"] == 2
    seg = r["por_tipo"]["seguimiento"]
    assert (seg["objetivos"], seg["pendientes"], seg["incluidos"]) == (1, 1, 0)
    for tipo, agg in r["por_tipo"].items():
        filas = [f for f in r["filas"] if f["tipo"] == tipo]
        assert agg["objetivos"] == len(filas) == agg["incluidos"] + agg["pendientes"] + agg["excluidos"]
        assert len(agg["serie"]) == agg["incluidos"]
    # Llega el resultado del 85: el seguimiento pasa a incluido, separado de las reconstrucciones.
    mid = entorno.juegos.obtener_por_codigo("MILOTO").id
    entorno.resultados.numericos[mid] = [*entorno.historicos["MILOTO"], *entorno.siguiente("MILOTO")]
    r = _rendimiento(entorno, "MILOTO")
    assert r["por_tipo"]["seguimiento"]["incluidos"] == 1 and r["por_tipo"]["retrospectiva"]["incluidos"] == 2
    solo = _rendimiento(entorno, "MILOTO", emision="seguimiento")
    assert list(solo["por_tipo"]) == ["seguimiento"] and [f["objetivo"] for f in solo["filas"]] == [85]
    periodo = _rendimiento(entorno, "MILOTO", desde=date(2026, 10, 2))
    assert [f["objetivo"] for f in periodo["filas"]] == [85]
    assert periodo["por_tipo"]["retrospectiva"]["objetivos"] == 0
    with pytest.raises(ValueError):
        _rendimiento(entorno, "MILOTO", emision="favorables")


def test_resultado_corregido_cambia_la_comparacion_con_aviso(entorno):
    g = _generar(entorno, "MILOTO", hasta=60)
    antes = _rendimiento(entorno, "MILOTO")["filas"][0]
    mid = entorno.juegos.obtener_por_codigo("MILOTO").id
    entorno.resultados.numericos[mid] = [dataclasses.replace(r, numeros=(35, 36, 37, 38, 39)) if r.numero_sorteo == 61
                                         else r for r in entorno.historicos["MILOTO"]]
    despues = _rendimiento(entorno, "MILOTO")["filas"][0]
    assert despues["identificador"] == g.identificador == antes["identificador"]
    assert "resultado_observado_cambio" in despues["avisos"] and despues["metricas"] != antes["metricas"]
    assert entorno.almacen.obtener("MILOTO", g.identificador).artefacto == g.artefacto


def test_juego_no_admitido_y_sin_pronosticos(entorno):
    from app.application.use_cases.pronostico_experimental import PronosticoExperimentalNoDisponibleError
    with pytest.raises(PronosticoExperimentalNoDisponibleError):
        _rendimiento(entorno, "QUINA")
    vacio = _rendimiento(entorno, "COLORLOTO")
    assert vacio["filas"] == [] and vacio["por_tipo"]["retrospectiva"]["incluidos"] == 0
    assert vacio["walk_forward_del_ultimo_artefacto"] is None
