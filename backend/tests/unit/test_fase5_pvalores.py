"""Fase 5 v2: p-values de las pruebas estadísticas nuevas (regresiones escritas antes de corregir).

Defectos de la v1 que reproducen:
  - `correlacionar` tomaba el p-value de SciPy (`spearmanr` y `pearsonr`), una aproximación para muestras grandes:
    con 3 pares ordenados daba p = 0 y la permutación bilateral exacta da 1/3;
  - la correlación serial publicaba esos p-values aunque las transiciones N -> N+1 comparten sorteos;
  - el chi-cuadrado no decía que su p-value es asintótico.
Sintético: datos construidos aquí, no sorteos reales."""
from __future__ import annotations

import itertools
import math
import random
from datetime import date, timedelta

import numpy as np
import pytest
from scipy import stats

from app.application.estadisticas import descriptivas as de
from app.application.estadisticas.motor import correlaciones as co
from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico
from tests.unit import fixtures_producto1 as fx

BALOTO = de.ReglasJuego("BALOTO", "Baloto", "numeros", (1, 43), 5, (1, 16))
COLORLOTO = de.ReglasJuego("COLORLOTO", "ColorLoto", "colorloto", (1, 7), 6, None, fx.COLORES, True)


def _exacto_fuerza_bruta(x, y, estadistico) -> float:
    """p bilateral de permutación por fuerza bruta, con SciPy para cada ordenación (referencia independiente)."""
    observado = abs(estadistico(x, y))
    ordenaciones = list(itertools.permutations(y))
    extremos = sum(1 for p in ordenaciones if abs(estadistico(x, list(p))) >= observado - 1e-12)
    return extremos / len(ordenaciones)


def _spearman(x, y):
    return stats.spearmanr(x, y).statistic


def _pearson(x, y):
    return stats.pearsonr(x, y).statistic


def _num(n, numeros, sb=None, fecha=date(2025, 3, 3)):
    return ResultadoNumerico(n, fecha, "lunes", tuple(numeros), sb)


# --- muestras pequeñas: permutación exacta ---------------------------------------------------------

def test_tres_pares_ordenados_dan_un_tercio_y_no_cero():
    pearson, spearman = co.correlacionar([1, 2, 3], [1, 2, 3])
    assert spearman.p_value == pytest.approx(1 / 3)  # v1: 0.0 (aproximación de SciPy)
    assert pearson.p_value == pytest.approx(1 / 3)
    assert spearman.coeficiente == pytest.approx(1.0) and pearson.coeficiente == pytest.approx(1.0)
    assert spearman.contraste == "permutacion_exacta" and spearman.permutaciones == 6


@pytest.mark.parametrize("x,y", [
    ([1, 1, 2, 3, 5], [2, 2, 1, 4, 3]),          # empates en las dos series
    ([3, 1, 4, 1, 5, 9], [2, 6, 5, 3, 5, 8]),    # empates en ambas y n = 6
    ([10, 20, 30, 40], [1, 3, 2, 4]),
])
def test_permutacion_exacta_coincide_con_fuerza_bruta_con_empates(x, y):
    pearson, spearman = co.correlacionar(x, y)
    assert spearman.p_value == pytest.approx(_exacto_fuerza_bruta(x, y, _spearman))
    assert pearson.p_value == pytest.approx(_exacto_fuerza_bruta(x, y, _pearson))
    assert spearman.coeficiente == pytest.approx(_spearman(x, y))
    assert spearman.permutaciones == math.factorial(len(x))


def test_series_constantes_o_cortas_no_tienen_coeficiente_ni_p_value():
    for x, y, texto in (([5, 5, 5], [1, 2, 3], "constante"), ([1, 2, 3], [4, 4, 4], "constante"),
                        ([1, 2], [2, 1], "al menos 3")):
        pearson, spearman = co.correlacionar(x, y)
        for c in (pearson, spearman):
            assert c.coeficiente is None and c.p_value is None and c.contraste is None
            assert texto in c.motivo and c.motivo_p_value


# --- muestras mayores: Monte Carlo reproducible ----------------------------------------------------

def test_monte_carlo_reproducible_valido_y_cercano_a_la_exacta():
    rng = random.Random(3)
    x = [rng.randint(0, 9) for _ in range(8)]
    y = [rng.randint(0, 9) for _ in range(8)]
    exacta = co.correlacionar(x, y)[1]
    mc = co.correlacionar(x, y, maximo_exacto=0)[1]
    assert exacta.contraste == "permutacion_exacta" and mc.contraste == "permutacion_monte_carlo"
    assert mc.permutaciones == co.PERMUTACIONES_MONTE_CARLO
    assert abs(mc.p_value - exacta.p_value) < 0.02  # error de Monte Carlo (B = 9999) muy por debajo
    k = mc.p_value * (co.PERMUTACIONES_MONTE_CARLO + 1) - 1  # p = (1 + k) / (1 + B), k entero
    assert abs(k - round(k)) < 1e-6 and mc.p_value >= 1 / (co.PERMUTACIONES_MONTE_CARLO + 1)
    assert co.correlacionar(x, y, maximo_exacto=0)[1].p_value == mc.p_value  # misma semilla, mismo p
    assert "semilla" in mc.motivo_p_value


def test_monte_carlo_no_depende_de_numpy_para_sus_ordenaciones():
    a = co.ordenaciones_monte_carlo(5, 3, semilla=11)
    rng = random.Random(11)
    esperado = []
    for _ in range(3):
        indices = list(range(5))
        for i in range(4, 0, -1):
            j = int(rng.random() * (i + 1))
            indices[i], indices[j] = indices[j], indices[i]
        esperado.append(indices)
    assert np.asarray(a).tolist() == esperado


# --- comparación entre mitades: la muestra son las categorías ---------------------------------------

def test_mitades_colorloto_usa_permutacion_exacta_sobre_7_categorias():
    sorteos = [ResultadoColorLoto(i, date(2025, 1, 1) + timedelta(days=3 * i), "lunes",
                                  tuple((1 + (i * j) % 7, "ROJO") for j in range(1, 7))) for i in range(1, 21)]
    r = co.calcular_estabilidad_frecuencia_numeros_colorloto(sorteos, 1, 7)
    assert r.categorias == 7 and r.spearman.contraste == "permutacion_exacta" and r.spearman.permutaciones == 5040
    f1 = [sum(1 for s in sorteos[:10] for n, _ in s.pares if n == v) for v in range(1, 8)]
    f2 = [sum(1 for s in sorteos[10:] for n, _ in s.pares if n == v) for v in range(1, 8)]
    assert r.spearman.p_value == pytest.approx(_exacto_fuerza_bruta(f1, f2, _spearman))  # v1: aproximación de SciPy


def test_mitades_numericas_usan_monte_carlo_sobre_43_categorias():
    r = co.calcular_estabilidad_frecuencia_numeros(fx.historico_numerico("BALOTO", 80), 1, 43)
    assert r.categorias == 43
    for c in (r.pearson, r.spearman):
        assert c.contraste == "permutacion_monte_carlo" and 0 < c.p_value <= 1 and c.n == 43


# --- correlación serial: transiciones que comparten sorteos ------------------------------------------

def test_serial_conserva_el_coeficiente_y_no_publica_p_value():
    sorteos = fx.historico_numerico("BALOTO", 30)
    r = co.calcular_correlacion_serial_sumas(sorteos)
    for c in (r.pearson, r.spearman):
        assert c.coeficiente is not None
        assert c.p_value is None  # v1: p-value de SciPy, que supone pares independientes
        assert c.contraste is None and "comparten" in c.motivo_p_value


# --- chi-cuadrado: p-value asintótico -----------------------------------------------------------------

def test_chi_cuadrado_declara_p_value_asintotico_y_que_el_factor_no_lo_hace_exacto():
    c = de.construir_metrica("pruebas-uniformidad", BALOTO, fx.historico_numerico("BALOTO", 60))
    resumen = next(t for t in c["tablas"] if t["id"] == "resumen")
    assert all(f["tipo_p_value"] == "asintotico" for f in resumen["filas"])  # v1: no lo decía
    assert any(col["clave"] == "tipo_p_value" for col in resumen["columnas"])
    notas = " ".join(c["notas"])
    assert "asintótic" in notas and "no convierte" in notas and "exact" in notas
    pocos = de.construir_metrica("pruebas-uniformidad", BALOTO, fx.historico_numerico("BALOTO", 20))
    assert "poco fiable" in next(t for t in pocos["tablas"] if t["id"] == "resumen")["filas"][0]["motivo"]


def test_numero_por_color_declara_p_value_asintotico():
    c = de.construir_metrica("correlaciones", COLORLOTO, fx.historico_colorloto(60))
    etiquetas = [i["etiqueta"] for i in c["indicadores"]]
    assert any("asintótico" in e for e in etiquetas if "número × color" in e)
    assert "asintótico" in next(t for t in c["tablas"] if t["id"] == "contingencia")["nota"]


# --- representación en el catálogo, JSON y HTML ---------------------------------------------------------

def _filas_correlacion(c):
    return next(t for t in c["tablas"] if t["id"] == "correlaciones")["filas"]


def test_correlaciones_distinguen_el_contraste_y_su_motivo():
    c = de.construir_metrica("correlaciones", BALOTO, fx.historico_numerico("BALOTO", 80))
    serial, mitades = _filas_correlacion(c)[:2], _filas_correlacion(c)[2:]
    assert all(f["p_value"] is None and f["contraste"] is None and "comparten" in f["motivo_p_value"] for f in serial)
    assert all(f["contraste"] == "permutacion_monte_carlo" and f["permutaciones"] == co.PERMUTACIONES_MONTE_CARLO
               for f in mitades)
    assert all("Monte Carlo" in f["como_p_value"] for f in mitades)
    cl = de.construir_metrica("correlaciones", COLORLOTO, fx.historico_colorloto(60))
    assert all(f["contraste"] == "permutacion_exacta" and "exacta" in f["como_p_value"] for f in _filas_correlacion(cl)[2:])


def test_correlacion_parcial_no_se_marca_insuficiente():
    tres = [_num(1, (1, 2, 3, 4, 5)), _num(2, (6, 7, 8, 9, 10)), _num(3, (11, 12, 13, 14, 15))]
    c = de.construir_metrica("correlaciones", BALOTO, tres)
    assert c["estado"] == "ok"
    filas = _filas_correlacion(c)
    assert filas[0]["coeficiente"] is None and "al menos 3" in filas[0]["motivo"]  # 2 transiciones
    assert filas[2]["coeficiente"] is not None  # mitades: 43 categorías


@pytest.fixture
def cliente(tmp_path):
    from tests.unit.test_fase5_web import _cliente
    c = _cliente(tmp_path)
    yield c
    from app.main import app
    app.dependency_overrides = {}


def test_api_y_html_muestran_metodo_y_limites(cliente):
    datos = cliente.get("/api/estadisticas/BALOTO/descriptivas/correlaciones").json()["metrica"]
    filas = _filas_correlacion(datos)
    assert filas[0]["p_value"] is None and "comparten" in filas[0]["motivo_p_value"]
    assert filas[2]["contraste"] == "permutacion_monte_carlo"
    html = cliente.get("/estadisticas/baloto/correlaciones").text
    assert "Monte Carlo" in html and "semilla" in html and "no se calcula" in html
    html_cl = cliente.get("/estadisticas/colorloto/correlaciones").text
    assert "permutación exacta" in html_cl and "asintótico" in html_cl
    uniformidad = cliente.get("/estadisticas/miloto/pruebas-uniformidad").text
    assert "asintótico" in uniformidad
    api = cliente.get("/api/estadisticas/MILOTO/descriptivas/pruebas-uniformidad").json()["metrica"]
    assert next(t for t in api["tablas"] if t["id"] == "resumen")["filas"][0]["tipo_p_value"] == "asintotico"


# --- añadidas tras corregir: reproducibilidad entre versiones y calibración en simulación -------------

X43 = [15, 5, 23, 18, 9, 6, 28, 23, 13, 24, 22, 24, 8, 17, 7, 20, 26, 23, 15, 11, 13, 16, 23, 19, 30, 6, 9, 17,
       22, 10, 16, 2, 23, 24, 27, 6, 22, 24, 23, 14, 29, 22, 26]
Y43 = [27, 20, 4, 17, 6, 27, 13, 1, 24, 11, 20, 13, 14, 3, 23, 23, 4, 24, 10, 12, 10, 11, 25, 6, 10, 13, 13, 10,
       18, 6, 28, 27, 13, 7, 6, 1, 23, 7, 24, 0, 27, 8, 27]


def test_monte_carlo_da_el_mismo_p_en_cualquier_version():
    """Valores fijados en Linux (Python 3.11, NumPy 2.4). En Windows (Python 3.14) deben salir iguales:
    las ordenaciones solo dependen de `random.Random(5).random()`, cuya secuencia Python garantiza."""
    assert co.ordenaciones_monte_carlo(43, co.PERMUTACIONES_MONTE_CARLO)[0][:10].tolist() == [
        24, 20, 34, 8, 18, 40, 36, 25, 4, 9]
    pearson, spearman = co.correlacionar(X43, Y43)
    assert pearson.p_value == pytest.approx(6484 / 10000) and spearman.p_value == pytest.approx(5837 / 10000)


def _uniforme(rng, n):
    return 1 + int(rng.random() * n)


def _fraccion_rechazos(pvalores, alfa):
    return sum(1 for p in pvalores if p <= alfa) / len(pvalores)


@pytest.mark.parametrize("alfa", [0.05, 0.20])
def test_mitades_exactas_no_rechazan_de_mas_bajo_h0(alfa):
    """Simulación bajo H0 (balotas uniformes e independientes, 7 números): la permutación exacta no
    rechaza más que alfa + 3 errores típicos. Comprueba el argumento de intercambiabilidad del motor;
    no dice nada de los sorteos reales."""
    rng = random.Random(7)
    pvalores = []
    for _ in range(300):
        sorteos = [ResultadoColorLoto(i, date(2025, 1, 1) + timedelta(days=i), "lunes",
                                      tuple((_uniforme(rng, 7), "ROJO") for _ in range(6))) for i in range(1, 31)]
        r = co.calcular_estabilidad_frecuencia_numeros_colorloto(sorteos, 1, 7)
        if r.spearman.p_value is not None:
            pvalores.append(r.spearman.p_value)
    assert len(pvalores) >= 290
    assert _fraccion_rechazos(pvalores, alfa) <= alfa + 3 * math.sqrt(alfa * (1 - alfa) / len(pvalores))


def test_mitades_monte_carlo_no_rechazan_de_mas_bajo_h0():
    """Igual con 5 de 43 sin reemplazo (Baloto) y Monte Carlo: alfa = 0,10."""
    rng = random.Random(11)
    pvalores = {"pearson": [], "spearman": []}
    for _ in range(200):
        sorteos = []
        for i in range(1, 41):
            bolsa = list(range(1, 44))
            elegidos = [bolsa.pop(int(rng.random() * len(bolsa))) for _ in range(5)]
            sorteos.append(_num(i, sorted(elegidos), fecha=date(2025, 1, 1) + timedelta(days=i)))
        r = co.calcular_estabilidad_frecuencia_numeros(sorteos, 1, 43)
        pvalores["pearson"].append(r.pearson.p_value)
        pvalores["spearman"].append(r.spearman.p_value)
    for valores in pvalores.values():
        assert _fraccion_rechazos(valores, 0.10) <= 0.10 + 3 * math.sqrt(0.09 / 200)


def test_formato_en_pantalla_del_tipo_de_p_value():
    from app.api.web.routers.estadisticas_descriptivas import formatear
    assert formatear("asintotico", "tipo_p").startswith("asintótico")
    assert formatear("permutacion_exacta", "tipo_p") == "permutación exacta"
    assert formatear("permutacion_monte_carlo", "tipo_p") == "permutación Monte Carlo"
    assert formatear(None, "tipo_p") == "—"


def _color(n, numeros):
    return ResultadoColorLoto(n, date(2025, 2, 1) + timedelta(days=3 * n), "lunes",
                              tuple((v, fx.COLORES[j % 6]) for j, v in enumerate(numeros)))


def test_muestras_pequenas_y_constantes_en_json_y_html(tmp_path):
    from tests.unit.test_fase5_web import _cliente
    inicio = date.today() - timedelta(days=30)
    tres = fx.historico_numerico("BALOTO", 3, inicio=inicio)
    constantes = [_color(i, (1, 1, 1, 1, 1, 1)) for i in range(1, 5)]  # sumas 6, 6, 6: serie constante
    c = _cliente(tmp_path, numericos={"BALOTO": tres, "BALOTO_REVANCHA": tres, "MILOTO": []}, colorloto=constantes)
    try:
        filas = _filas_correlacion(c.get("/api/estadisticas/BALOTO/descriptivas/correlaciones").json()["metrica"])
        assert "al menos 3" in filas[0]["motivo"] and filas[0]["motivo_p_value"] == co.SIN_COEFICIENTE
        assert filas[2]["coeficiente"] is not None and filas[2]["contraste"] == "permutacion_monte_carlo"
        html = c.get("/estadisticas/baloto/correlaciones").text
        assert "Se necesitan al menos 3 pares y hay 2. Sin coeficiente no hay p-value." in html
        assert "Permutación Monte Carlo, B = 9999, semilla 5" in html
        cl = c.get("/api/estadisticas/COLORLOTO/descriptivas/correlaciones").json()["metrica"]
        filas = _filas_correlacion(cl)
        assert filas[0]["coeficiente"] is None and "constante" in filas[0]["motivo"] and filas[0]["contraste"] is None
        assert filas[2]["contraste"] == "permutacion_exacta" and filas[2]["permutaciones"] == 5040
        html = c.get("/estadisticas/colorloto/correlaciones").text
        assert "Una de las series es constante" in html and "Permutación exacta, 5040 ordenaciones" in html
    finally:
        from app.main import app
        app.dependency_overrides = {}
