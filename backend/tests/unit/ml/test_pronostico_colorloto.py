"""Producto 2: pronostico experimental de ColorLoto.

Seis pares (numero 1..7, color) con repeticion; el orden de extraccion no
forma parte del objetivo (multiconjunto). Paleta tomada solo de los
sorteos anteriores al corte, multinomial con probabilidades suavizadas
(suavizado aditivo, media a posteriori de una Dirichlet) para pares escasos,
objetivos con colores nuevos excluidos con su motivo, combinacion mas
probable exacta y muestra reproducible con semilla. Historicos
sinteticos."""
from __future__ import annotations

import dataclasses
import itertools
import math
import random
from collections import Counter
from datetime import date, timedelta

import pytest

from app.application.estadisticas.tipos import ResultadoColorLoto
from app.application.ml import pronostico_colorloto as pc
from tests.unit import fixtures_producto1 as fx

CONFIG = pc.ConfiguracionColorLoto()


def _historico_con_paleta_cambiante(n=80, nuevo_desde=45):
    """Los primeros sorteos solo usan cinco colores; NEGRO aparece desde
    `nuevo_desde`."""
    rng = random.Random("paleta-cambiante")
    salida = []
    for i in range(n):
        colores = fx.COLORES[:5] if i < nuevo_desde else fx.COLORES
        pares = tuple((rng.randint(1, 7), rng.choice(colores)) for _ in range(6))
        fecha = date(2024, 8, 17) + timedelta(days=3 * i)
        salida.append(ResultadoColorLoto(i + 1, fecha, fx.DIAS[fecha.weekday()], pares))
    return salida


@pytest.fixture(scope="module")
def historico():
    return fx.historico_colorloto(80)


@pytest.fixture(scope="module")
def cuerpo(historico):
    return pc.generar_pronostico(historico, configuracion=CONFIG)


def test_paleta_solo_del_pasado():
    h = _historico_con_paleta_cambiante()
    assert pc.paleta_del_corte(h[:45]) == ("AMARILLO", "AZUL", "BLANCO", "ROJO", "VERDE")
    assert pc.paleta_del_corte(h) == tuple(sorted(fx.COLORES))
    c = pc.generar_pronostico(h[:44], configuracion=CONFIG)
    assert "NEGRO" not in c["pronostico"]["paleta"] and all(f["color"] != "NEGRO" for f in c["pronostico"]["pares"])


def test_probabilidades_con_suavizado_aditivo(historico):
    previos = historico[:30]
    d = pc.distribucion_de_pares(previos, CONFIG)
    paleta = pc.paleta_del_corte(previos)
    assert set(d) == {(n, c) for n in range(1, 8) for c in paleta}
    assert math.isclose(sum(d.values()), 1.0, abs_tol=1e-12)
    conteo = Counter(par for r in previos for par in r.pares)
    total = 6 * 30
    for par, p in d.items():
        assert math.isclose(p, (conteo[par] + CONFIG.alfa) / (total + CONFIG.alfa * 7 * len(paleta)), abs_tol=1e-15)
    assert min(d.values()) > 0


def test_multiconjunto_mas_probable_es_exacto_con_repeticion():
    dist = {(1, "A"): 0.5, (2, "A"): 0.3, (3, "B"): 0.2}
    moda = pc.multiconjunto_mas_probable(dist, 6)
    mejor = max(itertools.combinations_with_replacement(sorted(dist), 6),
                key=lambda m: pc.probabilidad_multiconjunto(dist, m))
    assert sorted(moda) == sorted(mejor) and len(moda) == 6
    assert Counter(moda)[(1, "A")] >= 2  # admite repeticion de un mismo par
    uniforme = {(n, c): 1 / 14 for n in range(1, 8) for c in ("A", "B")}
    assert len(set(pc.multiconjunto_mas_probable(uniforme, 6))) == 6


def test_probabilidad_del_multiconjunto_no_depende_del_orden():
    dist = {(1, "A"): 0.5, (2, "A"): 0.3, (3, "B"): 0.2}
    a = [(1, "A"), (1, "A"), (2, "A"), (3, "B"), (1, "A"), (2, "A")]
    assert pc.probabilidad_multiconjunto(dist, a) == pc.probabilidad_multiconjunto(dist, list(reversed(a)))
    esperado = math.factorial(6) / (math.factorial(3) * math.factorial(2) * 1) * 0.5 ** 3 * 0.3 ** 2 * 0.2
    assert math.isclose(pc.probabilidad_multiconjunto(dist, a), esperado, rel_tol=1e-12)
    total = sum(pc.probabilidad_multiconjunto(dist, m) for m in itertools.combinations_with_replacement(sorted(dist), 6))
    assert math.isclose(total, 1.0, rel_tol=1e-12)


def test_coincidencias_con_repeticion():
    assert pc.coincidencias([(1, "A"), (1, "A"), (2, "B")], [(1, "A"), (2, "B"), (2, "B")]) == 2
    assert pc.coincidencias([(1, "A")] * 6, [(1, "A")] * 2 + [(3, "C")] * 4) == 2


def test_cuerpo_v2_y_pronostico_del_dominio(cuerpo):
    assert cuerpo["esquema"] == "pronostico-experimental/2" and cuerpo["juego"] == "COLORLOTO"
    assert cuerpo["estado_de_uso"] == "experimental_no_acreditado" and cuerpo["contexto"]["AUTORIZA_EVALUACION"] is False
    p = cuerpo["pronostico"]
    assert p["objetivo"] == 81 and len(p["pares"]) == 6
    assert all(1 <= f["numero"] <= 7 and f["color"] in p["paleta"] for f in p["pares"])
    assert len(p["muestra_con_semilla"]["pares"]) == 6 and p["muestra_con_semilla"]["semilla"] == 42
    assert math.isclose(sum(f["probabilidad"] for f in p["ranking_de_pares"]), 1.0, abs_tol=1e-9)
    assert len(p["ranking_de_pares"]) == 7 * len(p["paleta"])
    assert cuerpo["estrategia"]["nombre"] == "pares_multinomial_con_suavizado_aditivo"


def test_metricas_y_referencia_independientes(historico, cuerpo):
    perd, perd_u, brier, brier_u, coin, coin_u, perd_multi = [], [], [], [], [], [], []
    for i in range(20, 80):
        previos = historico[:i]
        paleta = sorted({c for r in previos for _, c in r.pares})
        objetivo = list(historico[i].pares)
        if any(c not in paleta for _, c in objetivo):
            continue
        conteo = Counter(par for r in previos for par in r.pares)
        m = 7 * len(paleta)
        d = {(n, c): (conteo[(n, c)] + 1.0) / (6 * i + m) for n in range(1, 8) for c in paleta}
        for bola in objetivo:
            perd.append(-math.log(d[bola]))
            perd_u.append(math.log(m))
            brier.append(sum(v * v for v in d.values()) - 2 * d[bola] + 1)
            brier_u.append(1 - 1 / m)
        perd_multi.append(-math.log(pc.probabilidad_multiconjunto(d, objetivo)))
        coin.append(pc.coincidencias(pc.multiconjunto_mas_probable(d, 6), objetivo))
        orden = sorted(d)
        coin_u.append(pc.coincidencias(orden[:6], objetivo))
    a = cuerpo["evaluacion_walk_forward"]["agregado"]
    assert a["modelo"]["log_loss_por_balota"] == round(sum(perd) / len(perd), 12)
    assert a["referencia_uniforme"]["log_loss_por_balota"] == round(sum(perd_u) / len(perd_u), 12)
    assert a["modelo"]["brier_por_balota"] == round(sum(brier) / len(brier), 12)
    assert a["referencia_uniforme"]["brier_por_balota"] == round(sum(brier_u) / len(brier_u), 12)
    assert a["modelo"]["log_loss_multiconjunto"] == round(sum(perd_multi) / len(perd_multi), 12)
    assert a["modelo"]["coincidencias_de_pares_por_sorteo"] == round(sum(coin) / len(coin), 12)
    assert a["referencia_uniforme"]["coincidencias_de_pares_por_sorteo"] == round(sum(coin_u) / len(coin_u), 12)
    assert a["modelo"]["balotas"] == 6 * len(perd_multi) and a["modelo"]["sorteos"] == len(perd_multi)


def test_objetivos_con_color_nuevo_se_excluyen_con_motivo():
    h = _historico_con_paleta_cambiante()
    c = pc.generar_pronostico(h, configuracion=CONFIG)
    muestra = c["evaluacion_walk_forward"]["muestra"]
    primero_con_negro = next(r.numero_sorteo for r in h if any(c == "NEGRO" for _, c in r.pares))
    assert primero_con_negro >= 46
    assert muestra["objetivos_excluidos_por_color_nuevo"] >= 1
    assert muestra["primeros_objetivos_excluidos"][0] == primero_con_negro
    assert muestra["objetivos_evaluados"] + muestra["objetivos_excluidos_por_color_nuevo"] == 60
    assert "color" in muestra["motivo_de_exclusion"]


def test_sin_fuga_y_determinista(historico, cuerpo):
    alterado = [r if r.numero_sorteo < 40 else dataclasses.replace(r, pares=((7, "NEGRO"),) * 6) for r in historico]
    assert pc.distribucion_de_pares(historico[:39], CONFIG) == pc.distribucion_de_pares(alterado[:39], CONFIG)
    assert pc.generar_pronostico(list(reversed(historico)), configuracion=CONFIG) == cuerpo
    corto = pc.generar_pronostico(historico[:60], configuracion=CONFIG)
    assert corto["evaluacion_walk_forward"]["bloques"][0] == cuerpo["evaluacion_walk_forward"]["bloques"][0]
    otra_semilla = pc.generar_pronostico(historico, configuracion=dataclasses.replace(CONFIG, semilla=7))
    assert otra_semilla["clave_de_entrada"] != cuerpo["clave_de_entrada"]
    assert otra_semilla["pronostico"]["pares"] == cuerpo["pronostico"]["pares"]


def test_orden_de_las_balotas_no_cambia_nada(historico, cuerpo):
    invertido = [dataclasses.replace(r, pares=tuple(reversed(r.pares))) for r in historico]
    otro = pc.generar_pronostico(invertido, configuracion=CONFIG)
    assert otro["clave_de_entrada"] == cuerpo["clave_de_entrada"] and otro["pronostico"] == cuerpo["pronostico"]


def test_datos_insuficientes_y_reglas(historico):
    with pytest.raises(pc.DatosInsuficientesError) as error:
        pc.generar_pronostico(historico[:29], configuracion=CONFIG)
    assert error.value.disponibles == 29 and error.value.requeridos == 30
    malo = [*historico[:-1], dataclasses.replace(historico[-1], pares=historico[-1].pares[:5])]
    with pytest.raises(pc.PronosticoExperimentalError, match="6 balotas"):
        pc.generar_pronostico(malo, configuracion=CONFIG)
    fuera = [*historico[:-1], dataclasses.replace(historico[-1], pares=((8, "ROJO"),) + historico[-1].pares[1:])]
    with pytest.raises(pc.PronosticoExperimentalError, match="fuera de"):
        pc.generar_pronostico(fuera, configuracion=CONFIG)
    with pytest.raises(pc.PronosticoExperimentalError, match="posteriores al corte"):
        pc.generar_pronostico(historico, hasta_numero_sorteo=50, configuracion=CONFIG)


def test_la_distribucion_calculada_es_multinomial_con_probabilidades_suavizadas(historico, cuerpo):
    """Fija el diseno: la probabilidad del multiconjunto es una multinomial
    con las probabilidades puntuales p = (conteo + alfa) / (6T + alfa*7K)
    (media a posteriori de una Dirichlet). NO es la distribucion predictiva
    Dirichlet-multinomial, que integraria la incertidumbre sobre p."""
    previos = historico[:30]
    d = pc.distribucion_de_pares(previos, CONFIG)
    conteo = Counter(par for r in previos for par in r.pares)
    objetivo = [(1, "ROJO"), (1, "ROJO"), (1, "ROJO"), (2, "AZUL"), (2, "AZUL"), (5, "VERDE")]
    m = Counter(objetivo)
    coeficiente = math.factorial(6) / math.prod(math.factorial(k) for k in m.values())
    multinomial = coeficiente * math.prod(d[par] ** k for par, k in m.items())
    assert math.isclose(pc.probabilidad_multiconjunto(d, objetivo), multinomial, rel_tol=1e-12)

    a = {par: conteo[par] + CONFIG.alfa for par in d}
    total = sum(a.values())
    predictiva = coeficiente * math.exp(
        math.lgamma(total) - math.lgamma(total + 6)
        + sum(math.lgamma(a[par] + k) - math.lgamma(a[par]) for par, k in m.items()))
    assert not math.isclose(pc.probabilidad_multiconjunto(d, objetivo), predictiva, rel_tol=1e-3)

    e = cuerpo["estrategia"]
    assert e["nombre"] == "pares_multinomial_con_suavizado_aditivo"
    assert "no es la distribucion predictiva Dirichlet-multinomial" in e["descripcion"]
    assert "media a posteriori" in e["descripcion"]
