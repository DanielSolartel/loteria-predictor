"""Fase 4 - contrato estadistico de la fiabilidad observada
(`predicciones_fiabilidad`): probabilidad emitida, rendimiento observado e
incertidumbre por separado; unidad = sorteo; bootstrap por bloques; estados
explicitos. Filas sinteticas con la misma forma y las mismas metricas que
Producto 6 (`resultados_procedencias`). Nada es real."""
from __future__ import annotations

import math

import numpy as np
import pytest

from app.application.ml import predicciones_fiabilidad as pf
from app.application.ml import resultados_procedencias as rp

NUMEROS = list(range(1, 44))
SUPERBALOTAS = list(range(1, 17))
PALETA = ["AMARILLO", "AZUL", "BLANCO", "NEGRO", "ROJO", "VERDE"]
PARES = [[n, c] for n in range(1, 8) for c in PALETA]


def _fila(juego, objetivo, fuente, resultado, *, tipo="seguimiento", estado="incluido", motivo=None):
    congelado = rp.congelado_de_fuente(juego, fuente)
    metricas, sb = rp.metricas_de_congelado(juego, objetivo, congelado, resultado)
    return {"tipo": tipo, "estado": estado, "motivo": motivo, "objetivo": objetivo, "congelado": congelado,
            "resultado": resultado, "metricas": metricas, "superbalota": sb}


def fila_numeros(objetivo, p, numeros, *, sb=None, sb_obs=None, **campos):
    fuente = {"candidatos": NUMEROS, "probabilidades": list(p), "masa": 5}
    if sb is not None:
        fuente["superbalota"] = {"candidatos": SUPERBALOTAS, "probabilidades": list(sb)}
    return _fila("BALOTO", objetivo, fuente, {"numeros": list(numeros), "superbalota": sb_obs}, **campos)


def fila_pares(objetivo, p, pares, **campos):
    fuente = {"candidatos": PARES, "probabilidades": list(p)}
    return _fila("COLORLOTO", objetivo, fuente, {"pares": [list(x) for x in pares]}, **campos)


UNIFORME = [5 / 43] * 43
# Mal calibrado: sobreconfiado en 1..10 (0.3 cada uno) frente a sorteos uniformes.
SOBRECONFIADO = [0.3] * 10 + [2 / 33] * 33


def sorteos_uniformes(n, semilla=7):
    rng = np.random.default_rng(semilla)
    return [sorted(rng.choice(NUMEROS, size=5, replace=False).tolist()) for _ in range(n)]


# ---------------------------------------------------------------------------
# Bootstrap por bloques
# ---------------------------------------------------------------------------

def test_longitud_de_bloque_es_la_regla_declarada():
    assert [pf.longitud_de_bloque(n) for n in (1, 8, 9, 30, 64, 65, 1000)] == [1, 2, 3, 4, 4, 5, 10]


def test_bootstrap_es_determinista_por_semilla_y_contiene_la_media():
    x = np.random.default_rng(1).normal(size=80)
    a = pf.bootstrap_por_bloques(x, 123)
    b = pf.bootstrap_por_bloques(x, 123)
    c = pf.bootstrap_por_bloques(x, 124)
    assert a == b and a["intervalo"] != c["intervalo"]
    assert a["intervalo"][0] < a["media"] < a["intervalo"][1]
    assert a["bloque"] == pf.longitud_de_bloque(80) and a["remuestreos"] == pf.REMUESTREOS and a["nivel"] == 0.95


def test_bootstrap_rechaza_series_vacias_o_no_finitas():
    with pytest.raises(pf.FalloDeCalculo):
        pf.bootstrap_por_bloques([], 1)
    with pytest.raises(pf.FalloDeCalculo):
        pf.bootstrap_por_bloques([0.1, math.nan, 0.2], 1)


def test_bloques_ensanchan_el_intervalo_con_dependencia_temporal():
    """Serie AR(1) positiva: remuestrear sorteos sueltos (bloque 1) ignora la
    dependencia y da un intervalo demasiado estrecho; los bloques lo ensanchan."""
    rng = np.random.default_rng(5)
    x = np.zeros(300)
    for t in range(1, 300):
        x[t] = 0.8 * x[t - 1] + rng.normal()
    iid = pf.bootstrap_por_bloques(x, 9, bloque=1)
    bloques = pf.bootstrap_por_bloques(x, 9)
    ancho = lambda r: r["intervalo"][1] - r["intervalo"][0]  # noqa: E731
    assert bloques["bloque"] == 7 and ancho(bloques) > 1.5 * ancho(iid)


def test_cobertura_aproximada_en_una_simulacion_de_control():
    """Comprobacion de cordura, no una promesa de cobertura: con series
    i.i.d. de media 0 el intervalo contiene el 0 en la mayoria de las
    replicas (la cobertura real con muestras pequenas puede quedar por
    debajo del 95 %)."""
    rng = np.random.default_rng(11)
    contiene = 0
    for r in range(200):
        x = rng.normal(size=60)
        iv = pf.bootstrap_por_bloques(x, r, remuestreos=400)["intervalo"]
        contiene += iv[0] <= 0 <= iv[1]
    assert 0.85 <= contiene / 200 <= 0.99


# ---------------------------------------------------------------------------
# Estados de una cifra
# ---------------------------------------------------------------------------

def test_estimar_distingue_sin_datos_muestra_insuficiente_estimable_y_fallo():
    assert pf.estimar([], ("x",), "diferencia_log_loss")["estado"] == "sin_datos"
    pequena = pf.estimar([0.1] * (pf.MINIMO_SORTEOS - 1), ("x",), "diferencia_log_loss")
    assert pequena["estado"] == "muestra_insuficiente" and pequena["intervalo"] is None
    assert pequena["media"] == pytest.approx(0.1) and "intervalo se calcula desde 30" in pequena["motivo"]
    suficiente = pf.estimar([0.1, -0.1] * 15, ("x",), "diferencia_log_loss")
    assert suficiente["estado"] == "estimable" and suficiente["n"] == 30 and suficiente["intervalo"] is not None
    fallo = pf.estimar([0.1] * 29 + [math.inf], ("x",), "diferencia_log_loss")
    assert fallo["estado"] == "fallo_de_calculo" and fallo["media"] is None


def test_no_hay_puntuacion_de_confianza_ni_etiquetas_alta_media_baja():
    for estado in pf.ESTADOS:
        assert not any(x in estado for x in ("alta", "media", "baja", "confianza"))
    texto = str(pf.METODO).lower()
    assert "puntuación de confianza" not in texto and "nivel de confianza" not in texto
    assert "no es una validación" in texto and "no corrige la selección" in texto


def test_fuentes_primarias_con_doi_verificados():
    dois = {f["doi"] for f in pf.FUENTES if f.get("doi")}
    assert dois == {"10.1214/aos/1176347265", "10.1093/biomet/82.3.561", "10.1198/016214506000001437"}
    assert any("Diebold" in f["cita"] and not f.get("doi") for f in pf.FUENTES)


# ---------------------------------------------------------------------------
# Emisiones congeladas (filas de Producto 6)
# ---------------------------------------------------------------------------

def test_uniforme_frente_a_uniforme_da_diferencia_cero_exacta():
    filas = [fila_numeros(k, UNIFORME, s) for k, s in enumerate(sorteos_uniformes(40), start=100)]
    ev = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "carteras:x"))
    m = ev["componentes"]["numeros"]["metricas"]
    assert ev["estado"] == "estimable" and ev["muestra"]["sorteos"] == 40
    for clave in ("diferencia_log_loss", "diferencia_brier"):
        assert m[clave]["media"] == 0 and m[clave]["intervalo"] == [0.0, 0.0]
        assert "Media numérica 0 en esta muestra" in m[clave]["lectura"]
        assert "El intervalo numérico incluye 0" in m[clave]["lectura"]


def test_modelo_mal_calibrado_queda_por_encima_de_la_uniforme_con_intervalo_que_excluye_cero():
    filas = [fila_numeros(k, SOBRECONFIADO, s) for k, s in enumerate(sorteos_uniformes(60), start=1)]
    ev = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "carteras:x"))
    m = ev["componentes"]["numeros"]["metricas"]
    assert m["diferencia_log_loss"]["intervalo"][0] > 0 and m["diferencia_brier"]["intervalo"][0] > 0
    assert "mayor pérdida que la uniforme" in m["diferencia_log_loss"]["lectura"]
    # Fuertes: el modelo espera 3 aciertos por sorteo en 1..10; salen ~10 x 5/43.
    f = m["fuertes_observado_menos_esperado"]
    assert f["intervalo"][1] < 0 and "menos aciertos que los esperados" in f["lectura"]
    extremos = ev["componentes"]["numeros"]["extremos"]["fuertes"]
    assert extremos["candidatos_por_sorteo"] == 10 and extremos["esperado"] == pytest.approx(60 * 3.0)


def test_muestra_insuficiente_da_media_sin_intervalo():
    filas = [fila_numeros(k, SOBRECONFIADO, s) for k, s in enumerate(sorteos_uniformes(12), start=1)]
    ev = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"))
    assert ev["estado"] == "muestra_insuficiente"
    m = ev["componentes"]["numeros"]["metricas"]["diferencia_log_loss"]
    assert m["estado"] == "muestra_insuficiente" and m["n"] == 12 and m["intervalo"] is None and m["media"] > 0


@pytest.mark.parametrize("estados,esperado", [
    ([], "sin_datos"),
    (["pendiente", "pendiente"], "sin_resultados"),
    (["sin_base", "pendiente"], "sin_base"),
    (["excluido"], "excluidas"),
])
def test_estados_sin_evidencia_distinguen_ausencia_pendiente_base_caida_y_exclusion(estados, esperado):
    filas = []
    for k, estado in enumerate(estados, start=1):
        f = fila_numeros(k, UNIFORME, [1, 2, 3, 4, 5], estado=estado, motivo="universo_distinto")
        if estado != "incluido":
            f.update(metricas=None, resultado=None)
        filas.append(f)
    ev = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"))
    assert ev["estado"] == esperado and ev["motivo"] and ev["componentes"] == {}
    if esperado == "excluidas":
        assert ev["muestra"]["exclusiones"] == [{"estado": "excluido", "motivo": "universo_distinto", "emisiones": 1}]


def test_tipos_separados_y_emisiones_sin_tipo_cuentan_como_exclusion_en_ambos():
    sorteos = sorteos_uniformes(6)
    filas = [fila_numeros(k, UNIFORME, sorteos[k]) for k in range(3)]
    filas += [fila_numeros(10 + k, UNIFORME, sorteos[3 + k], tipo="retrospectiva") for k in range(2)]
    sin_tipo = fila_numeros(20, UNIFORME, sorteos[5], tipo="sin_clasificacion", estado="excluido",
                            motivo="sin_clasificacion_temporal_al_generar")
    filas.append(sin_tipo)
    seg = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"))
    ret = pf.evaluar_emisiones(filas, "retrospectiva", ("BALOTO", "x"))
    assert seg["muestra"]["sorteos"] == 3 and ret["muestra"]["sorteos"] == 2
    for ev in (seg, ret):
        assert {"estado": "excluido", "motivo": "sin_clasificacion_temporal_al_generar", "emisiones": 1} in \
            ev["muestra"]["exclusiones"]


def test_la_unidad_es_el_sorteo_no_el_candidato():
    """43 candidatos por sorteo y 35 sorteos: n = 35 (una cifra por sorteo)."""
    filas = [fila_numeros(k, SOBRECONFIADO, s) for k, s in enumerate(sorteos_uniformes(35), start=1)]
    ev = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"))
    for m in ev["componentes"]["numeros"]["metricas"].values():
        assert m["n"] == 35
    assert ev["componentes"]["numeros"]["sorteos"] == 35 and ev["muestra"]["periodo"] == [1, 35]


def test_superbalota_es_un_componente_aparte_con_sus_propios_extremos():
    sb = [0.2, 0.2] + [0.6 / 14] * 14
    filas = [fila_numeros(k, UNIFORME, s, sb=sb, sb_obs=(k % 16) + 1)
             for k, s in enumerate(sorteos_uniformes(32), start=1)]
    ev = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"))
    assert set(ev["componentes"]) == {"numeros", "superbalota"}
    s = ev["componentes"]["superbalota"]
    assert s["sorteos"] == 32 and s["extremos"]["fuertes"]["candidatos_por_sorteo"] == pf.EXTREMO["superbalota"]
    # La uniforme en numeros sigue en 0: la superbalota no se mezcla con los numeros.
    assert ev["componentes"]["numeros"]["metricas"]["diferencia_log_loss"]["media"] == 0


def test_colorloto_usa_multiplicidad_entre_seis_y_no_al_menos_una_vez():
    p = [0.05] * 10 + [0.5 / 32] * 32  # los 10 primeros pares, mas probables
    fuertes = PARES[:10]
    resultado = [fuertes[0], fuertes[0], fuertes[1], PARES[20], PARES[30], PARES[41]]  # un par repetido
    v = pf.valores_de_emision(fila_pares(1, p, resultado))["pares"]
    observado, esperado, k = v["_fuertes"]
    assert k == 10 and observado == 3  # multiplicidad: el par repetido cuenta dos veces
    assert esperado == pytest.approx(6 * 10 * 0.05)
    assert v["fuertes_observado_menos_esperado"] == pytest.approx(3 - 3.0)


def test_hasta_limita_la_evidencia_y_la_misma_muestra_da_el_mismo_intervalo():
    filas = [fila_numeros(k, SOBRECONFIADO, s) for k, s in enumerate(sorteos_uniformes(40), start=1)]
    todo = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"))
    mismo = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"), hasta=40)
    assert todo["componentes"] == mismo["componentes"]
    corte = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"), hasta=31)
    assert corte["muestra"]["sorteos"] == 31 and corte["muestra"]["periodo"] == [1, 31]
    assert corte["muestra"]["hasta"] == 31


def test_series_y_resultados_no_finitos_dan_fallo_de_calculo_con_motivo():
    filas = [fila_numeros(k, UNIFORME, s) for k, s in enumerate(sorteos_uniformes(3), start=1)]
    del filas[1]["metricas"]["brier_uniforme"]
    ev = pf.evaluar_emisiones(filas, "seguimiento", ("BALOTO", "x"))
    assert ev["estado"] == "fallo_de_calculo" and "no se pudieron calcular" in ev["motivo"]


# ---------------------------------------------------------------------------
# Evaluacion de la receta (informe del laboratorio)
# ---------------------------------------------------------------------------

def _informe(n, *, delta=0.001, superbalota=False, uniforme_completa=True):
    por = [{"objetivo": 100 + i, "diferencia_log_loss": delta + (0.002 if i % 2 else -0.002), "brier": 0.10 + delta}
           for i in range(n)]
    uni = [{"objetivo": 100 + i, "brier": 0.10} for i in range(n if uniforme_completa else n - 1)]
    informe = {"clave": "k" * 64, "datos": {"corte": 99}, "identidad": {"reglas": {"colores": False}},
               "muestra_comun": {"excluidos": [{"objetivo": 1}]},
               "candidatos": [{"id": "m", "familia": "bosques", "estado": "completo", "por_objetivo": por},
                              {"id": "uniforme", "familia": "uniforme", "estado": "completo", "por_objetivo": uni}]}
    if superbalota:
        informe["superbalota"] = {"agregado": {}}
    return informe


def test_receta_con_reajustes_por_bloque_se_evalua_con_su_serie_por_objetivo():
    ev = pf.evaluar_informe(_informe(40, superbalota=True), "m", ("BALOTO", "k", "m"))
    assert ev["tipo"] == "evaluacion_de_receta" and ev["estado"] == "estimable"
    c = ev["componentes"]["numeros"]["metricas"]
    assert c["diferencia_log_loss"]["media"] == pytest.approx(0.001)
    assert c["diferencia_brier"]["media"] == pytest.approx(0.001) and c["diferencia_brier"]["n"] == 40
    for m in ("fuertes_observado_menos_esperado", "debiles_observado_menos_esperado"):
        assert c[m]["estado"] == "no_disponible" and c[m]["media"] is None
    assert ev["componentes"]["superbalota"]["estado"] == "no_disponible"
    assert ev["muestra"]["excluidos_de_la_muestra_comun"] == 1 and ev["corte_del_informe"] == 99


def test_receta_sin_uniforme_completa_sin_modelo_y_con_muestra_pequena():
    sin_uni = pf.evaluar_informe(_informe(40, uniforme_completa=False), "m", ("B", "k", "m"))
    assert sin_uni["componentes"]["numeros"]["metricas"]["diferencia_brier"]["estado"] == "no_disponible"
    assert pf.evaluar_informe(_informe(40), "otro", ("B", "k", "otro"))["estado"] == "sin_datos"
    pequena = pf.evaluar_informe(_informe(20), "m", ("B", "k", "m"))
    assert pequena["estado"] == "muestra_insuficiente"
    assert pf.evaluar_informe(_informe(40), "m", ("B", "k", "m"), hasta=50)["estado"] == "sin_datos"
