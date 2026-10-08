"""Producto 5: simulacion Monte Carlo y controles exactos.

- las dos carteras se miden sobre los MISMOS sorteos sinteticos; conteos,
  maximos, multiplicidades de ColorLoto y superbalota separada se recalculan
  aqui de forma independiente (conjuntos y multiconjuntos de Python);
- las combinaciones no cuentan como sorteos independientes (denominadores);
- hipergeometrica y enumeracion exacta del maximo frente a recuentos por
  fuerza bruta en un dominio pequeno;
- escenarios separados, reproducibilidad por lotes, presupuesto validado,
  ceros sin afirmar imposibilidad y sin reentrenar."""
from __future__ import annotations

import math
from collections import Counter
from itertools import combinations

import numpy as np
import pytest

from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_construccion as cc
from app.application.ml import carteras_simulacion as cs
from app.application.ml import laboratorio_modelos as lm
from tests.unit.fixtures_producto5 import fuente_colorloto, fuente_numeros


def _cartera(fuente, juego, cantidad=5, semilla=42, sugerencia=True):
    return cc.construir(fuente, juego, con_sugerencia=sugerencia, cantidad=cantidad, semilla=semilla,
                        diversidad="libre")["combinaciones"]


def lv_rango(juego):
    return cs.lv.REGLAS[juego].rango[1]


def _sorteos(juego, fuente, semilla, escenario, m):
    """Los sorteos sinteticos del escenario (mismo flujo documentado)."""
    reglas = cs.lv.REGLAS[juego]
    rng, rng_sb = cc.flujos(semilla, cc.FLUJO_SIMULACION, juego, escenario)
    n = len(fuente["candidatos"])
    pesos = np.full(n, 1 / n) if escenario == 1 else cc.pesos_normalizados(fuente["probabilidades"])
    if reglas.colores:
        indices = cc.muestrear_con_reemplazo(rng, pesos, 6, filas=m)
        principales = [[tuple(fuente["candidatos"][i]) for i in fila] for fila in indices]
    else:
        indices = cc.muestrear_sin_reemplazo(rng, pesos, 5, filas=m)
        principales = [{fuente["candidatos"][i] for i in fila} for fila in indices]
    sb = None
    if reglas.superbalota:
        p = np.full(16, 1 / 16) if escenario == 1 else cc.pesos_normalizados(fuente["superbalota"]["probabilidades"])
        sb = [int(x) + 1 for x in cc.muestrear_con_reemplazo(rng_sb, p, 1, filas=m)[:, 0]]
    return principales, sb


def _aciertos_independientes(combinacion, sorteo, colores):
    if colores:
        a, b = Counter(tuple(p) for p in combinacion["pares"]), Counter(sorteo)
        return sum(min(a[k], b[k]) for k in a)
    return len(set(combinacion["numeros"]) & sorteo)


@pytest.mark.parametrize("juego", ["BALOTO", "MILOTO", "COLORLOTO"])
def test_conteos_y_maximos_coinciden_con_un_recuento_independiente(juego):
    colores = juego == "COLORLOTO"
    n = 42 if colores else lv_rango(juego)
    fuente = fuente_colorloto(np.arange(1, n + 1)) if colores else fuente_numeros(juego, np.arange(1, n + 1))
    elegida = _cartera(fuente, juego)
    uniforme = _cartera(fuente_colorloto() if colores else fuente_numeros(juego), juego, sugerencia=False)
    m = 1000
    r = cs.simular(juego, fuente, elegida, uniforme, m, 9)
    for e, escenario in enumerate(cs.ESCENARIOS, start=1):
        principales, sb = _sorteos(juego, fuente, 9, e, m)
        res = r[escenario]
        k = 6 if colores else 5
        tabla = np.zeros((k + 1, k + 1), dtype=int)
        maximos = {}
        for nombre, cartera in (("elegida", elegida), ("uniforme", uniforme)):
            por_comb = Counter()
            maximo = Counter()
            sb_alguna = 0
            sb_max = Counter()
            for i, sorteo in enumerate(principales):
                aciertos = [_aciertos_independientes(c, sorteo, colores) for c in cartera]
                por_comb.update(aciertos)
                maximo[max(aciertos)] += 1
                if sb is not None:
                    con = [a for a, c in zip(aciertos, cartera) if c["superbalota"] == sb[i]]
                    sb_alguna += bool(con)
                    sb_max[max(con) if con else "ninguna"] += 1
                maximos.setdefault(nombre, []).append(max(aciertos))
            datos = res["carteras"][nombre]
            assert datos["aciertos_por_combinacion"]["conteos"] == [por_comb[a] for a in range(k + 1)]
            assert datos["aciertos_por_combinacion"]["denominador"] == m * 5  # lineas x sorteos
            assert datos["maximo_de_la_cartera"]["conteos"] == [maximo[a] for a in range(k + 1)]
            assert datos["maximo_de_la_cartera"]["denominador"] == m  # sorteos, no combinaciones
            for t in range(2, k + 1):
                assert datos["al_menos"][str(t)]["conteo"] == sum(maximo[a] for a in range(t, k + 1))
                assert datos["al_menos"][str(t)]["denominador"] == m
            assert abs(datos["media_del_maximo"] - sum(a * c for a, c in maximo.items()) / m) < 1e-6
            if sb is not None:
                assert datos["superbalota"]["al_menos_una_linea"]["conteo"] == sb_alguna
                s = datos["superbalota"]["maximo_principal_entre_lineas_con_superbalota"]
                assert s["conteos"] == [sb_max[a] for a in range(k + 1)] and s["sin_superbalota"] == sb_max["ninguna"]
            else:
                assert "superbalota" not in datos
        for a, b in zip(maximos["elegida"], maximos["uniforme"]):
            tabla[a, b] += 1
        emparejado = res["emparejado"]
        assert emparejado["tabla"] == tabla.tolist()  # mismo sorteo para las dos carteras
        assert emparejado["elegida_mayor"] == int(np.tril(tabla, -1).sum())
        assert emparejado["uniforme_mayor"] == int(np.triu(tabla, 1).sum())
        assert emparejado["elegida_mayor"] + emparejado["iguales"] + emparejado["uniforme_mayor"] == m


def test_una_cartera_frente_a_si_misma_empata_en_todos_los_sorteos():
    fuente = fuente_numeros("BALOTO", np.arange(1, 44))
    cartera = _cartera(fuente, "BALOTO")
    r = cs.simular("BALOTO", fuente, cartera, cartera, 1000, 3)
    for escenario in cs.ESCENARIOS:
        e = r[escenario]["emparejado"]
        assert e["iguales"] == 1000 and e["elegida_mayor"] == e["uniforme_mayor"] == 0
        assert all(v == 0 for v in e["diferencia_en_al_menos"].values())


def test_aciertos_con_multiplicidad_en_colorloto():
    candidatos = [(n, c) for n in range(1, 8) for c in ("AZUL", "ROJO")]
    indice = {p: i for i, p in enumerate(candidatos)}
    cartera = [{"pares": [[1, "AZUL"], [1, "AZUL"], [2, "ROJO"], [3, "AZUL"], [4, "ROJO"], [5, "AZUL"]]}]
    matriz = cs._indices_de_cartera(cartera, candidatos, True)
    sorteo = np.array([[indice[(1, "AZUL")], indice[(1, "AZUL")], indice[(1, "AZUL")], indice[(2, "ROJO")],
                        indice[(6, "AZUL")], indice[(7, "ROJO")]]])
    assert cs._aciertos(sorteo, matriz, len(candidatos), True).tolist() == [[3]]  # min(2,3) + min(1,1)


def test_hipergeometrica_frente_a_recuento_por_fuerza_bruta():
    n, k = 10, 3
    jugada = {1, 2, 3}
    conteo = Counter(len(jugada & set(s)) for s in combinations(range(1, n + 1), k))
    total = math.comb(n, k)
    assert np.allclose(cs.hipergeometrica(n, k), [conteo[a] / total for a in range(k + 1)], atol=1e-15)
    assert abs(sum(cs.hipergeometrica(43, 5)) - 1) < 1e-12
    assert cs.hipergeometrica(43, 5)[5] == 1 / math.comb(43, 5)


def test_maximo_exacto_por_enumeracion_en_un_dominio_pequeno():
    n, k = 9, 3
    cartera = [[1, 2, 3], [3, 4, 5], [7, 8, 9]]
    esperado = Counter(max(len(set(c) & set(s)) for c in cartera) for s in combinations(range(1, n + 1), k))
    r = cs.maximo_exacto_uniforme(cartera, n, k)
    assert r["espacio"] == math.comb(n, k) == 84
    assert r["conteos"] == [esperado[a] for a in range(k + 1)]
    assert r["al_menos"]["2"] == (esperado[2] + esperado[3]) / 84
    una = cs.maximo_exacto_uniforme([[2, 5, 9]], n, k)  # una sola linea: hipergeometrica
    assert np.allclose(una["probabilidades"], cs.hipergeometrica(n, k), atol=1e-15)


def test_controles_exactos_de_una_cartera_real_y_coherencia_monte_carlo():
    fuente = fuente_numeros("BALOTO", np.arange(1, 44))
    elegida = _cartera(fuente, "BALOTO")
    uniforme = _cartera(fuente_numeros("BALOTO"), "BALOTO", sugerencia=False)
    ex = cs.controles_exactos("BALOTO", elegida, uniforme)
    assert ex["disponible"] and ex["espacio_de_combinaciones"] == math.comb(43, 5) == 962598
    assert ex["espacio_con_superbalota"] == 962598 * 16
    for nombre in ("elegida", "uniforme"):
        p = ex["maximo_exacto"][nombre]["probabilidades"]
        assert abs(sum(p) - 1) < 1e-12 and ex["maximo_exacto"][nombre]["al_menos"]["5"] > 0
    assert ex["superbalota"]["al_menos_una_linea"]["elegida"] == len({c["superbalota"] for c in elegida}) / 16
    m = 20000
    r = cs.simular("BALOTO", fuente, elegida, uniforme, m, 11)["sorteos_uniformes"]
    for nombre in ("elegida", "uniforme"):
        simulado = r["carteras"][nombre]["maximo_de_la_cartera"]["conteos"]
        for a, p in enumerate(ex["maximo_exacto"][nombre]["probabilidades"]):
            # semilla fija: el resultado es determinista; la tolerancia (6 desviaciones) solo documenta la coherencia
            assert abs(simulado[a] / m - p) <= 6 * math.sqrt(p * (1 - p) / m) + 1 / m
    sin = cs.controles_exactos("COLORLOTO", [], [])
    assert sin["disponible"] is False and "ColorLoto" in sin["motivo"]


def test_escenarios_separados_lotes_presupuesto_y_ceros():
    fuente = fuente_numeros("MILOTO", np.arange(1, 40))
    elegida = _cartera(fuente, "MILOTO")
    uniforme = _cartera(fuente_numeros("MILOTO"), "MILOTO", sugerencia=False)
    a = cs.simular("MILOTO", fuente, elegida, uniforme, 3000, 5)
    b = cs.simular("MILOTO", fuente, elegida, uniforme, 3000, 5, lote=777)
    assert a == b  # el tamano de lote no cambia nada
    assert list(a) == list(cs.ESCENARIOS)
    assert a["sorteos_uniformes"]["supuestos"]["escenario"] == "sorteos_uniformes"
    assert "advertencia" not in a["sorteos_uniformes"]["supuestos"]
    assert "no es una confirmacion independiente" in a["muestreo_ponderado"]["supuestos"]["advertencia"]
    assert a["sorteos_uniformes"]["carteras"] != a["muestreo_ponderado"]["carteras"]
    assert cs.simular("MILOTO", fuente, elegida, uniforme, 3000, 6) != a
    for invalido in (999, 50001, 1000.0, True):
        with pytest.raises(cs.SimulacionNoValida):
            cs.simular("MILOTO", fuente, elegida, uniforme, invalido, 5)
    with pytest.raises(cs.SimulacionNoValida):
        cs.simular("MILOTO", fuente, elegida, uniforme[:4], 1000, 5)
    pequena = cs.simular("MILOTO", fuente, elegida, uniforme, 1000, 5)["sorteos_uniformes"]
    cero = pequena["carteras"]["uniforme"]["al_menos"]["5"]
    assert cero["conteo"] == 0 and cero["frecuencia_simulada"] == 0.0 and cero["denominador"] == 1000
    exacto = cs.controles_exactos("MILOTO", elegida, uniforme)["maximo_exacto"]["uniforme"]["al_menos"]["5"]
    assert exacto > 0  # cero en 1000 simulaciones no es imposibilidad


def test_simular_una_cartera_guardada_no_reentrena(monkeypatch):
    fuente = fuente_numeros("BALOTO", np.arange(1, 44))
    elegida = {"juego": "BALOTO", "fuente": fuente, "clave_de_entrada": "a" * 64,
               "modelo": {"id": "x", "nombre": "X"}, "linea": {"id": "x-v1-n5-libre-s42"},
               "cartera": {"combinaciones": _cartera(fuente, "BALOTO"), "objetivo": 10, "parametros": {}},
               "datos": {"corte": 9}}
    uniforme = {**elegida, "clave_de_entrada": "b" * 64,
                "cartera": {**elegida["cartera"],
                            "combinaciones": _cartera(fuente_numeros("BALOTO"), "BALOTO", sugerencia=False)}}

    def prohibido(*a, **k):
        raise AssertionError("la simulacion no debe ajustar modelos")
    monkeypatch.setattr(lm, "ajustar_candidato", prohibido)
    identidad = ca.identidad_de_simulacion(elegida, uniforme, 1000, 42)
    cuerpo = ca.cuerpo_de_simulacion(identidad, elegida, uniforme)
    assert cuerpo["clave"] == ca.huella(identidad) and cuerpo["identidad"]["fuente_sha256"] == ca.huella(fuente)
    assert "no significa imposibilidad" in cuerpo["nota"] and "premios" in cuerpo["nota"]
    assert set(cuerpo["resultados"]) == set(cs.ESCENARIOS)
    csv = ca.csv_de_simulacion(ca.componer(cuerpo, "ejecucion", {}))
    filas = csv.splitlines()
    assert filas[0].startswith("juego,objetivo,escenario,cartera") and len(filas) == 1 + 2 * 2 * (6 + 4 + 1)
    assert ca.identidad_de_simulacion(elegida, uniforme, 1000, 43) != identidad
    assert ca.identidad_de_simulacion(elegida, uniforme, 2000, 42) != identidad
