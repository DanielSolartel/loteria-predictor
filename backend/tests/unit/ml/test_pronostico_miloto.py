"""Producto 2: pronostico experimental de MiLoto (5 numeros distintos de
1..39, sin superbalota) con una evaluacion temporal para muestras cortas.

Estimador de frecuencia contraido hacia la uniforme, ventana creciente y
evaluacion de cada sorteo con al menos `minimo_sorteos_de_entrenamiento`
anteriores. Las metricas se recalculan aqui de forma independiente.
Historicos sinteticos."""
from __future__ import annotations

import dataclasses
import math

import pytest

from app.application.ml import pronostico_miloto as pm
from tests.unit import fixtures_producto1 as fx

CONFIG = pm.ConfiguracionMiLoto()


@pytest.fixture(scope="module")
def historico():
    return fx.historico_numerico("MILOTO", 84, primero=1)


@pytest.fixture(scope="module")
def cuerpo(historico):
    return pm.generar_pronostico(historico, configuracion=CONFIG)


def test_probabilidades_contraidas_suman_cinco_y_respetan_el_rango(historico):
    p = pm.probabilidades_de_inclusion(historico[:30], CONFIG)
    assert sorted(p) == list(range(1, 40)) and math.isclose(sum(p.values()), 5.0, abs_tol=1e-12)
    n = 7
    c = sum(1 for r in historico[:30] if n in r.numeros)
    assert math.isclose(p[n], (c + CONFIG.fuerza_previa * 5 / 39) / (30 + CONFIG.fuerza_previa), abs_tol=1e-15)
    assert all(0 < v < 1 for v in p.values())
    sin_datos = pm.probabilidades_de_inclusion([], CONFIG)
    assert set(round(v, 12) for v in sin_datos.values()) == {round(5 / 39, 12)}


def test_cuerpo_v2_con_contrato_y_dominio(cuerpo):
    assert cuerpo["esquema"] == "pronostico-experimental/2" and cuerpo["juego"] == "MILOTO"
    assert cuerpo["estado_de_uso"] == "experimental_no_acreditado"
    assert cuerpo["contexto"]["AUTORIZA_EVALUACION"] is False and cuerpo["contexto"]["resultado_acreditado"] is False
    assert cuerpo["estrategia"]["nombre"] == "frecuencia_con_contraccion_a_la_uniforme"
    assert cuerpo["estrategia"]["referencia"].startswith("uniforme")
    p = cuerpo["pronostico"]
    assert p["objetivo"] == 85 and p["calculado_hasta_sorteo"] == 84
    assert len(p["numeros_sugeridos"]) == 5 and len(set(p["numeros_sugeridos"])) == 5
    assert all(1 <= n <= 39 for n in p["numeros_sugeridos"]) and "superbalota" not in p
    assert {f["numero"] for f in p["ranking"][:5]} == set(p["numeros_sugeridos"])
    assert p["numeros_sugeridos"] == sorted(p["numeros_sugeridos"])
    assert sorted(f["numero"] for f in p["ranking"]) == list(range(1, 40))
    assert cuerpo.get("superbalota") is None


def test_evaluacion_de_muestra_corta_y_bloques(cuerpo):
    e = cuerpo["evaluacion_walk_forward"]
    assert e["muestra"] == {"sorteos": 84, "objetivos_evaluados": 64, "primer_objetivo": 21, "ultimo_objetivo": 84,
                            "minimo_sorteos_de_entrenamiento": 20, "minimo_objetivos_evaluados": 10}
    tamanos = [b["modelo"]["sorteos"] for b in e["bloques"]]
    assert sum(tamanos) == 64 and all(t == 8 for t in tamanos)
    assert e["bloques"][0]["objetivos"] == [21, 28] and e["bloques"][0]["entrenamiento"] == {"desde": 1, "hasta": 20}
    assert e["agregado"]["comparacion"]["veredicto"] in ("el_modelo_no_supera_a_la_referencia_uniforme",
                                                         "el_modelo_supera_a_la_referencia_en_log_loss_y_brier")


def test_metricas_recalculadas_independientemente(historico, cuerpo):
    """Log Loss y Brier sobre 39 filas por sorteo; aciertos top-5 con
    desempate ascendente; referencia 5/39."""
    perdidas, brier, aciertos, perd_u, brier_u, aciertos_u = [], [], [], [], [], []
    u = 5 / 39
    for i in range(20, 84):
        p = pm.probabilidades_de_inclusion(historico[:i], CONFIG)
        real = set(historico[i].numeros)
        for n in range(1, 40):
            y = 1 if n in real else 0
            q = min(max(p[n], 1e-6), 1 - 1e-6)
            perdidas.append(-(y * math.log(q) + (1 - y) * math.log(1 - q)))
            brier.append((p[n] - y) ** 2)
            perd_u.append(-(y * math.log(u) + (1 - y) * math.log(1 - u)))
            brier_u.append((u - y) ** 2)
        top = sorted(range(1, 40), key=lambda n: (-p[n], n))[:5]
        aciertos.append(len(real & set(top)))
        aciertos_u.append(len(real & {1, 2, 3, 4, 5}))
    a = cuerpo["evaluacion_walk_forward"]["agregado"]
    assert a["modelo"]["log_loss"] == round(sum(perdidas) / len(perdidas), 12)
    assert a["modelo"]["brier"] == round(sum(brier) / len(brier), 12)
    assert a["modelo"]["aciertos_top5_por_sorteo"] == round(sum(aciertos) / len(aciertos), 12)
    assert a["referencia_uniforme"]["log_loss"] == round(sum(perd_u) / len(perd_u), 12)
    assert a["referencia_uniforme"]["brier"] == round(sum(brier_u) / len(brier_u), 12)
    assert a["referencia_uniforme"]["aciertos_top5_por_sorteo"] == round(sum(aciertos_u) / len(aciertos_u), 12)
    assert a["modelo"]["filas"] == 64 * 39 and a["modelo"]["sorteos"] == 64


def test_sin_fuga_temporal(historico):
    """Cambiar sorteos desde el objetivo no cambia su prediccion."""
    i = 40
    alterado = [r if r.numero_sorteo < historico[i].numero_sorteo else dataclasses.replace(r, numeros=(1, 2, 3, 4, 5))
                for r in historico]
    assert pm.probabilidades_de_inclusion(historico[:i], CONFIG) == pm.probabilidades_de_inclusion(alterado[:i], CONFIG)
    corto = pm.generar_pronostico(historico[:60], configuracion=CONFIG)
    largo = pm.generar_pronostico(historico, configuracion=CONFIG)
    assert largo["evaluacion_walk_forward"]["bloques"][0] == corto["evaluacion_walk_forward"]["bloques"][0]


def test_determinista_y_clave(historico, cuerpo):
    otro = pm.generar_pronostico(list(reversed(historico)), configuracion=CONFIG)
    assert otro == cuerpo
    clave = pm.clave_de_entrada(historico, configuracion=CONFIG)
    assert cuerpo["clave_de_entrada"] == clave and len(clave) == 64
    assert pm.clave_de_entrada(historico, configuracion=dataclasses.replace(CONFIG, fuerza_previa=10.0)) != clave
    assert pm.clave_de_entrada(historico[:-1], configuracion=CONFIG) != clave


def test_corte_y_rechazo_de_posteriores(historico):
    c = pm.generar_pronostico(historico[:50], hasta_numero_sorteo=50, configuracion=CONFIG)
    assert c["pronostico"]["objetivo"] == 51 and c["datos"]["corte"] == 50
    with pytest.raises(pm.PronosticoExperimentalError, match="posteriores al corte"):
        pm.generar_pronostico(historico, hasta_numero_sorteo=50, configuracion=CONFIG)


def test_datos_insuficientes_con_estado_claro(historico):
    with pytest.raises(pm.DatosInsuficientesError) as error:
        pm.generar_pronostico(historico[:29], configuracion=CONFIG)
    assert error.value.disponibles == 29 and error.value.requeridos == 30
    assert "datos insuficientes" in str(error.value).lower()
    assert pm.generar_pronostico(historico[:30], configuracion=CONFIG)["evaluacion_walk_forward"]["muestra"][
        "objetivos_evaluados"] == 10


def test_reglas_del_dominio_miloto(historico):
    malo = [*historico[:-1], dataclasses.replace(historico[-1], numeros=(1, 2, 3, 4, 40))]
    with pytest.raises(pm.PronosticoExperimentalError, match="fuera de"):
        pm.generar_pronostico(malo, configuracion=CONFIG)
    con_superbalota = [*historico[:-1], dataclasses.replace(historico[-1], superbalota=3)]
    with pytest.raises(pm.PronosticoExperimentalError, match="superbalota"):
        pm.generar_pronostico(con_superbalota, configuracion=CONFIG)
    repetidos = [*historico[:-1], dataclasses.replace(historico[-1], numeros=(1, 1, 2, 3, 4))]
    with pytest.raises(pm.PronosticoExperimentalError):
        pm.generar_pronostico(repetidos, configuracion=CONFIG)


def test_no_es_una_seleccion_uniforme(cuerpo):
    probs = {f["probabilidad"] for f in cuerpo["pronostico"]["ranking"]}
    assert len(probs) > 1
    assert cuerpo["estrategia"]["nombre"] != "uniforme"
