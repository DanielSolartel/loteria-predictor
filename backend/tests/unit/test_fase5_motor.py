"""Fase 5 (estadísticas descriptivas): funciones nuevas del motor, con ejemplos comprobables a mano.

Sintético: sorteos construidos en la prueba; no son datos reales."""
from __future__ import annotations

import math
import random
from datetime import date
from itertools import combinations

import pytest
from scipy import stats

from app.application.estadisticas.motor import correlaciones as co
from app.application.estadisticas.motor import independencia as ind
from app.application.estadisticas.motor.distribuciones import calcular_histograma_sumas
from app.application.estadisticas.motor.frecuencia import (
    calcular_frecuencia_numeros,
    calcular_frecuencia_numeros_colorloto,
    calcular_frecuencia_superbalota,
)
from app.application.estadisticas.motor.frecuencia_temporal import (
    calcular_frecuencia_numeros_colorloto_por_anio,
    calcular_frecuencia_numeros_colorloto_por_dia_semana,
    calcular_frecuencia_numeros_colorloto_por_mes,
)
from app.application.estadisticas.motor.tests_estadisticos import chi_cuadrado_bondad_ajuste, chi_cuadrado_uniformidad
from app.application.estadisticas.tipos import (
    FrecuenciaObservada,
    ProbabilidadTeorica,
    ResultadoColorLoto,
    ResultadoNumerico,
)


def _num(numero_sorteo: int, numeros, superbalota=None, fecha=date(2025, 1, 6)) -> ResultadoNumerico:
    return ResultadoNumerico(numero_sorteo, fecha, "lunes", tuple(numeros), superbalota)


def _color(numero_sorteo: int, pares, fecha=date(2025, 1, 6), dia="lunes") -> ResultadoColorLoto:
    return ResultadoColorLoto(numero_sorteo, fecha, dia, tuple(pares))


def _frecuencias(conteos: list[int], total: int) -> list[FrecuenciaObservada]:
    return [FrecuenciaObservada(str(i + 1), c, total, c / total) for i, c in enumerate(conteos)]


# --- chi-cuadrado de uniformidad -------------------------------------------------------------

def test_chi2_con_k_1_coincide_con_pearson_a_mano():
    # 3 sorteos de 1 valor entre 3: observados 2, 1, 0; esperado 1 cada uno; X = 1 + 0 + 1 = 2; gl = 2.
    r = chi_cuadrado_uniformidad(_frecuencias([2, 1, 0], 3), 1, sin_reemplazo=True)
    assert r.estadistico == pytest.approx(2.0) and r.grados_libertad == 2
    assert r.p_value == pytest.approx(math.exp(-1.0))  # chi2(2): sf(x) = exp(-x/2)


def test_chi2_sin_reemplazo_aplica_el_factor_exacto():
    # 2 sorteos de 2 distintos entre 4: {1,2} y {1,3} -> 2, 1, 1, 0; esperado 2*2/4 = 1; Pearson = 2;
    # corregido = 2 * (4-1)/(4-2) = 3; gl = 3.
    base = chi_cuadrado_bondad_ajuste(_frecuencias([2, 1, 1, 0], 2), ProbabilidadTeorica("*", 0.5, "2/4"))
    r = chi_cuadrado_uniformidad(_frecuencias([2, 1, 1, 0], 2), 2, sin_reemplazo=True)
    assert base.estadistico == pytest.approx(2.0)
    assert r.estadistico == pytest.approx(3.0) and r.grados_libertad == 3
    assert r.p_value == pytest.approx(stats.chi2.sf(3.0, 3)) and r.nombre_test == "chi2_uniformidad_sin_reemplazo"


def test_chi2_corregido_sigue_la_chi_cuadrado_bajo_sorteo_uniforme():
    """Monte Carlo (semilla fija): con 5 de 43 sin reemplazo, el Pearson sin corregir promedia N-K = 38 y el
    corregido N-1 = 42 (la media de una chi2(42)); sin la corrección el test sería conservador."""
    rng = random.Random(20261009)
    crudos, corregidos = [], []
    for _ in range(2000):
        sorteos = [_num(i, sorted(rng.sample(range(1, 44), 5))) for i in range(60)]
        f = calcular_frecuencia_numeros(sorteos, 1, 43)
        crudos.append(chi_cuadrado_bondad_ajuste(f, ProbabilidadTeorica("*", 5 / 43, "5/43")).estadistico)
        corregidos.append(chi_cuadrado_uniformidad(f, 5, sin_reemplazo=True).estadistico)
    assert abs(sum(crudos) / len(crudos) - 38.0) < 1.0
    assert abs(sum(corregidos) / len(corregidos) - 42.0) < 1.0


def test_chi2_con_reemplazo_colorloto_no_corrige():
    sorteos = [_color(1, [(1, "ROJO"), (1, "AZUL"), (2, "ROJO"), (3, "ROJO"), (7, "AZUL"), (7, "ROJO")])]
    f = calcular_frecuencia_numeros_colorloto(sorteos, 1, 7)  # balotas: 2, 1, 1, 0, 0, 0, 2
    r = chi_cuadrado_uniformidad(f, 6, sin_reemplazo=False)
    esperado = 6 / 7
    a_mano = sum((o - esperado) ** 2 / esperado for o in (2, 1, 1, 0, 0, 0, 2))
    assert r.nombre_test == "chi2_bondad_ajuste" and r.estadistico == pytest.approx(a_mano) and r.grados_libertad == 6


def test_chi2_rechaza_extraer_todas_las_categorias_sin_reemplazo():
    with pytest.raises(ValueError):
        chi_cuadrado_uniformidad(_frecuencias([1, 1], 1), 2, sin_reemplazo=True)


# --- histograma de sumas -----------------------------------------------------------------------

def test_histograma_de_sumas_a_mano_y_sin_superbalota():
    sorteos = [_num(1, (1, 2), 9), _num(2, (4, 5), 9), _num(3, (2, 4), 1)]  # sumas 3, 9, 6
    filas = calcular_histograma_sumas(sorteos, 1, 5, 2, ancho_intervalo=3)
    assert [(f.valor, f.apariciones, f.total_sorteos) for f in filas] == [("3-5", 1, 3), ("6-8", 1, 3), ("9-11", 1, 3)]
    assert sum(f.frecuencia_relativa for f in filas) == pytest.approx(1.0)


def test_histograma_aplica_el_corte_y_valida_el_rango():
    sorteos = [_num(1, (1, 2)), _num(2, (4, 5))]
    assert [f.apariciones for f in calcular_histograma_sumas(sorteos, 1, 5, 2, 3, hasta_numero_sorteo=1)] == [1, 0, 0]
    with pytest.raises(ValueError):
        calcular_histograma_sumas([_num(1, (1, 9))], 1, 5, 2, 3)


def test_histograma_vacio_tiene_intervalos_en_cero():
    filas = calcular_histograma_sumas([], 1, 43, 5)
    assert filas[0].valor == "10-19" and filas[-1].valor == "200-209"
    assert all(f.apariciones == 0 and f.frecuencia_relativa == 0.0 for f in filas)


# --- números de ColorLoto por periodo ------------------------------------------------------------

def test_numeros_colorloto_por_anio_cuentan_balotas_con_multiplicidad():
    sorteos = [_color(1, [(5, "ROJO"), (5, "AZUL"), (1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO")],
                      date(2024, 12, 30)),
               _color(2, [(5, "ROJO"), (6, "AZUL"), (6, "ROJO"), (6, "VERDE"), (7, "ROJO"), (7, "AZUL")],
                      date(2025, 1, 2), "jueves")]
    f2024 = {f.valor: f for f in calcular_frecuencia_numeros_colorloto_por_anio(sorteos, 1, 7, 2024)}
    assert f2024["5"].apariciones == 2 and f2024["5"].total_sorteos == 1 and f2024["5"].frecuencia_relativa == 2.0
    f2025 = {f.valor: f for f in calcular_frecuencia_numeros_colorloto_por_anio(sorteos, 1, 7, 2025)}
    assert f2025["6"].apariciones == 3 and f2025["1"].apariciones == 0
    assert {f.valor: f.apariciones for f in calcular_frecuencia_numeros_colorloto_por_mes(sorteos, 1, 7, 12)}["5"] == 2
    jueves = calcular_frecuencia_numeros_colorloto_por_dia_semana(sorteos, 1, 7, "jueves")
    assert {f.valor: f.apariciones for f in jueves}["7"] == 2 and jueves[0].total_sorteos == 1
    assert calcular_frecuencia_numeros_colorloto_por_anio(sorteos, 1, 7, 2025, hasta_numero_sorteo=1)[0].total_sorteos == 0
    with pytest.raises(ValueError):
        calcular_frecuencia_numeros_colorloto_por_mes(sorteos, 1, 7, 13)


# --- correlaciones -------------------------------------------------------------------------------

def test_correlacionar_a_mano_y_casos_no_calculables():
    p, s = co.correlacionar([1, 2, 3], [2, 4, 6])
    assert p.coeficiente == pytest.approx(1.0) and s.coeficiente == pytest.approx(1.0) and p.n == 3
    p, s = co.correlacionar([1, 2, 3, 4], [4, 3, 2, 1])
    assert p.coeficiente == pytest.approx(-1.0) and s.coeficiente == pytest.approx(-1.0)
    p, _ = co.correlacionar([1, 2], [3, 4])
    assert p.coeficiente is None and p.p_value is None and "al menos 3" in p.motivo
    p, _ = co.correlacionar([5, 5, 5], [1, 2, 3])
    assert p.coeficiente is None and "constante" in p.motivo


def test_correlacion_serial_solo_usa_transiciones_consecutivas():
    lineal = [_num(1, (1, 2, 3, 4, 5)), _num(2, (2, 3, 4, 5, 6)), _num(3, (3, 4, 5, 6, 7)), _num(4, (4, 5, 6, 7, 8))]
    r = co.calcular_correlacion_serial_sumas(lineal)  # sumas 15, 20, 25, 30: pares (15,20), (20,25), (25,30)
    assert r.transiciones == 3 and r.excluidas_por_hueco == 0 and r.pearson.coeficiente == pytest.approx(1.0)
    con_hueco = [_num(1, (1, 2, 3, 4, 5)), _num(2, (2, 3, 4, 5, 6)), _num(4, (3, 4, 5, 6, 7)), _num(5, (1, 2, 3, 4, 9))]
    r = co.calcular_correlacion_serial_sumas(con_hueco)
    assert r.transiciones == 2 and r.excluidas_por_hueco == 1 and r.pearson.coeficiente is None
    assert co.calcular_correlacion_serial_sumas(lineal, hasta_numero_sorteo=2).transiciones == 1


def test_correlacion_serial_colorloto_suma_los_seis_numeros_sin_color():
    sorteos = [_color(i, [(n, "ROJO")] * 6) for i, n in enumerate((1, 2, 3, 4), start=1)]  # sumas 6, 12, 18, 24
    r = co.calcular_correlacion_serial_sumas_colorloto(sorteos)
    assert r.transiciones == 3 and r.pearson.coeficiente == pytest.approx(1.0)


def test_estabilidad_entre_mitades_a_mano():
    # 4 sorteos de 2 entre 1..3: primera mitad {1,2},{1,3} -> (2,1,1); segunda {1,2},{1,3} -> (2,1,1): r = 1.
    sorteos = [_num(1, (1, 2)), _num(2, (1, 3)), _num(3, (1, 2)), _num(4, (1, 3))]
    r = co.calcular_estabilidad_frecuencia_numeros(sorteos, 1, 3)
    assert (r.sorteos_primera, r.sorteos_segunda, r.primera, r.segunda) == (2, 2, (1, 2), (3, 4))
    assert r.categorias == 3 and r.pearson.coeficiente == pytest.approx(1.0)
    vacio = co.calcular_estabilidad_frecuencia_numeros(sorteos[:1], 1, 3)
    assert vacio.sorteos_primera == 0 and vacio.pearson.coeficiente is None


def test_independencia_numero_color_a_mano():
    # Balotas: (1,ROJO) x3 y (2,AZUL) x3 -> tabla [[3,0],[0,3]], esperado 1.5 en cada celda:
    # chi2 = 4 x 1.5^2/1.5 = 6, gl = 1. VERDE no tiene balotas: queda fuera de la tabla.
    sorteos = [_color(1, [(1, "ROJO"), (1, "ROJO"), (2, "AZUL"), (2, "AZUL"), (1, "ROJO"), (2, "AZUL")])]
    r = co.calcular_independencia_numero_color(sorteos, 1, 2, ["ROJO", "AZUL", "VERDE"])
    assert r.observado == ((3, 0), (0, 3)) and r.colores == ("ROJO", "AZUL") and r.excluidos == ("VERDE",)
    assert r.resultado.estadistico == pytest.approx(6.0) and r.resultado.grados_libertad == 1
    assert r.resultado.p_value == pytest.approx(stats.chi2.sf(6.0, 1)) and r.esperado_minimo == pytest.approx(1.5)
    solo_un_color = co.calcular_independencia_numero_color([_color(1, [(1, "ROJO")] * 6)], 1, 2, ["ROJO"])
    assert solo_un_color.resultado is None and "al menos 2" in solo_un_color.motivo


# --- independencia: el cálculo por soporte no cambia ningún p-value -----------------------------

def test_independencia_da_los_mismos_p_values_que_binomtest_directo():
    rng = random.Random(7)
    sorteos = [_num(i, sorted(rng.sample(range(1, 13), 4))) for i in range(40)]
    obtenidos = ind.calcular_independencia_pares(sorteos, 1, 12, 4)
    p = ind._probabilidad_teorica_coocurrencia(12, 4, 2)
    for r in obtenidos:
        a, b = (int(x) for x in r.elementos)
        soporte = sum(1 for s in sorteos if a in s.numeros and b in s.numeros)
        assert r.estadistico == soporte
        assert r.p_value == float(stats.binomtest(soporte, len(sorteos), p, alternative="two-sided").pvalue)
    assert [r.elementos for r in obtenidos] == [tuple(str(x) for x in c) for c in combinations(range(1, 13), 2)]


def test_frecuencias_de_superbalota_no_se_mezclan_con_numeros():
    sorteos = [_num(1, (1, 2, 3, 4, 5), 1), _num(2, (1, 2, 3, 4, 6), 1)]
    assert {f.valor: f.apariciones for f in calcular_frecuencia_superbalota(sorteos, 1, 16)}["1"] == 2
    assert {f.valor: f.apariciones for f in calcular_frecuencia_numeros(sorteos, 1, 43)}["1"] == 2
    assert sum(f.apariciones for f in calcular_frecuencia_numeros(sorteos, 1, 43)) == 10
