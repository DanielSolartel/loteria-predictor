"""Tests de `app/application/simulaciones/factibilidad_regla_prospectiva.py`
-Etapa AE-55, validada: calculadora analitica de factibilidad. Todo
analitico o por enumeracion exhaustiva; sin simulacion, datos reales,
PostgreSQL ni predicciones reales. Verifican calculos bajo supuestos
declarados, no la validez de ninguna regla prospectiva."""
from __future__ import annotations

import ast
import json
import math
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import pytest
from scipy import stats

from app.application.simulaciones import factibilidad_regla_prospectiva as fa

ARCHIVO = Path(fa.__file__)
RAIZ_BACKEND = ARCHIVO.resolve().parents[3]


# ---------------------------------------------------------------------------
# Distribucion exacta de aciertos del top y diferencia pareada
# ---------------------------------------------------------------------------

def _enumerar(rango, cantidad, solape):
    """Varianza exacta de (aciertos A - aciertos B) enumerando todos los
    sorteos equiprobables; A y B son dos tops de `cantidad` con `solape`."""
    a = set(range(cantidad))
    b = set(range(cantidad - solape, 2 * cantidad - solape))
    valores = [len(a & set(s)) - len(b & set(s)) for s in combinations(range(rango), cantidad)]
    media = Fraction(sum(valores), len(valores))
    return Fraction(sum(v * v for v in valores), len(valores)) - media * media


class TestAciertos:
    def test_hipergeometrica_43_5(self):
        d = fa.distribucion_aciertos(43, 5)
        assert sum(d["probabilidades"]) == 1
        assert len(d["probabilidades"]) == 6
        assert d["probabilidades"][0] == Fraction(math.comb(38, 5), math.comb(43, 5))
        assert d["media_aciertos"] == Fraction(25, 43)
        assert d["media_precision"] == Fraction(5, 43)
        assert d["varianza_aciertos"] == Fraction(5 * 5 * 38 * 38, 43 * 43 * 42)

    @pytest.mark.parametrize("rango, cantidad", [(8, 3), (10, 3), (9, 4)])
    def test_hipergeometrica_por_enumeracion(self, rango, cantidad):
        d = fa.distribucion_aciertos(rango, cantidad)
        top = set(range(cantidad))
        conteos = [0] * (cantidad + 1)
        for s in combinations(range(rango), cantidad):
            conteos[len(top & set(s))] += 1
        total = sum(conteos)
        assert d["probabilidades"] == [Fraction(c, total) for c in conteos]

    @pytest.mark.parametrize("rango, cantidad", [(8, 3), (10, 3), (9, 4)])
    def test_varianza_pareada_por_enumeracion(self, rango, cantidad):
        for solape in range(cantidad + 1):
            resultado = fa.varianza_diferencia_aciertos(rango, cantidad, solape)
            assert resultado["varianza_aciertos"] == _enumerar(rango, cantidad, solape), solape
            assert resultado["varianza_precision"] == resultado["varianza_aciertos"] / (cantidad * cantidad)

    def test_varianza_pareada_43_5_forma_cerrada(self):
        for solape in range(6):
            resultado = fa.varianza_diferencia_aciertos(43, 5, solape)
            assert resultado["varianza_aciertos"] == Fraction(190, 903) * (5 - solape)
            assert resultado["varianza_precision"] == Fraction(38, 4515) * (5 - solape)
        assert fa.varianza_diferencia_aciertos(43, 5, 5)["varianza_aciertos"] == 0

    @pytest.mark.parametrize("argumentos", [(43, 5, 6), (43, 5, -1), (43, 0, 0), (4, 5, 0), (43, 5, 1.0), (True, 5, 0)])
    def test_entradas_invalidas(self, argumentos):
        with pytest.raises(fa.FactibilidadInvalidaError):
            fa.varianza_diferencia_aciertos(*argumentos)

    def test_rango_unitario_con_solape_total_da_cero_exacto(self):
        resultado = fa.varianza_diferencia_aciertos(1, 1, 1)
        assert resultado == {"solape": 1, "varianza_aciertos": Fraction(0), "varianza_precision": Fraction(0)}
        assert isinstance(resultado["varianza_aciertos"], Fraction)
        assert isinstance(resultado["varianza_precision"], Fraction)

    @pytest.mark.parametrize("rango, cantidad", [(1, 1), (3, 3), (43, 5), (10, 3)])
    def test_solape_total_da_cero_exacto(self, rango, cantidad):
        resultado = fa.varianza_diferencia_aciertos(rango, cantidad, cantidad)
        assert resultado["varianza_aciertos"] == 0 and resultado["varianza_precision"] == 0
        assert isinstance(resultado["varianza_aciertos"], Fraction)


# ---------------------------------------------------------------------------
# Efecto minimo detectable y potencia, en unidades de sigma
# ---------------------------------------------------------------------------

class TestPotencia:
    def test_cuantiles_frente_a_scipy(self):
        assert fa.cuantil_normal(0.975) == pytest.approx(stats.norm.ppf(0.975), abs=1e-12)
        assert fa.cuantil_normal(0.8) == pytest.approx(stats.norm.ppf(0.8), abs=1e-12)

    def test_emd_de_referencia(self):
        esperado = (stats.norm.ppf(0.975) + stats.norm.ppf(0.8)) / 10
        assert fa.efecto_minimo_detectable(100, 0.025, 0.8, 1.0) == pytest.approx(esperado, abs=1e-12)
        assert fa.efecto_minimo_detectable(100, 0.025, 0.8, 1.0) == pytest.approx(0.2802, abs=1e-4)
        assert fa.efecto_minimo_detectable(100, 0.025, 0.9, 1.0) == pytest.approx(0.3242, abs=1e-4)
        assert fa.efecto_minimo_detectable(100, 0.025, 0.8, 4.0) == pytest.approx(2 * 0.28016, abs=1e-4)

    def test_monotonia(self):
        base = fa.efecto_minimo_detectable(100, 0.025, 0.8, 1.0)
        assert fa.efecto_minimo_detectable(200, 0.025, 0.8, 1.0) < base
        assert fa.efecto_minimo_detectable(100, 0.05, 0.8, 1.0) < base
        assert fa.efecto_minimo_detectable(100, 0.025, 0.9, 1.0) > base
        assert fa.efecto_minimo_detectable(100, 0.025, 0.8, 2.0) > base

    @pytest.mark.parametrize("potencia, inflacion", [(0.8, 1.0), (0.9, 1.0), (0.8, 4.0), (0.5, 1.857)])
    def test_potencia_en_el_emd_es_la_objetivo(self, potencia, inflacion):
        emd = fa.efecto_minimo_detectable(100, 0.025, potencia, inflacion)
        assert fa.potencia_aproximada(emd, 100, 0.025, inflacion) == pytest.approx(potencia, abs=1e-12)

    @pytest.mark.parametrize("potencia, alfa", [(0.01, 0.025), (0.025, 0.025), (0.2, 0.3), (0.3, 0.3)])
    def test_potencia_no_mayor_que_alfa_se_rechaza(self, potencia, alfa):
        with pytest.raises(fa.FactibilidadInvalidaError, match="potencia"):
            fa.efecto_minimo_detectable(100, alfa, potencia, 1.0)

    @pytest.mark.parametrize("potencia", [0.026, 0.05, 0.5, 0.8, 0.999])
    def test_emd_positivo_en_todo_el_dominio(self, potencia):
        emd = fa.efecto_minimo_detectable(100, 0.025, potencia, 1.0)
        assert emd > 0
        assert fa.potencia_aproximada(emd, 100, 0.025, 1.0) == pytest.approx(potencia, abs=1e-12)

    def test_potencia_sin_efecto_es_alfa(self):
        assert fa.potencia_aproximada(0.0, 100, 0.025, 1.0) == pytest.approx(0.025, abs=1e-12)

    def test_inflacion_ar1_frente_a_la_suma_de_autocorrelaciones(self):
        for rho in (-0.5, 0.0, 0.3, 0.6):
            suma = 1 + 2 * math.fsum(rho ** k for k in range(1, 2000))
            assert fa.inflacion_varianza_ar1(rho) == pytest.approx(suma, rel=1e-12)
        assert fa.inflacion_varianza_ar1(0.6) == pytest.approx(4.0)

    @pytest.mark.parametrize("llamada", [
        lambda: fa.inflacion_varianza_ar1(1.0), lambda: fa.inflacion_varianza_ar1(-1.0),
        lambda: fa.efecto_minimo_detectable(1, 0.025, 0.8, 1.0), lambda: fa.efecto_minimo_detectable(100, 0.0, 0.8, 1.0),
        lambda: fa.efecto_minimo_detectable(100, 0.025, 1.0, 1.0), lambda: fa.efecto_minimo_detectable(100, 0.025, 0.8, 0.0),
        lambda: fa.potencia_aproximada(0.1, 100, 0.6, 1.0), lambda: fa.efecto_minimo_detectable(True, 0.025, 0.8, 1.0),
    ])
    def test_entradas_invalidas(self, llamada):
        with pytest.raises(fa.FactibilidadInvalidaError):
            llamada()


# ---------------------------------------------------------------------------
# Tabla fija y descriptiva
# ---------------------------------------------------------------------------

class TestTabla:
    def test_contenido(self):
        tabla = fa.tabla_factibilidad()
        assert tabla["caracter"] == "analitico_bajo_supuestos"
        assert tabla["n"] == 100 and tabla["alfa_unilateral"] == 0.025
        filas = {(f["potencia"], f["escenario_dependencia"]): f for f in tabla["efecto_minimo_detectable"]}
        assert set(filas) == {(p, e) for p in (0.8, 0.9) for e in ("sin_dependencia", "ar1_rho_0.3", "ar1_rho_0.6")}
        assert filas[(0.8, "sin_dependencia")]["emd_en_sigmas"] == pytest.approx(0.2802, abs=1e-4)
        assert filas[(0.8, "ar1_rho_0.6")]["inflacion"] == pytest.approx(4.0)
        assert tabla["secundaria"]["media_aciertos"] == "25/43"
        assert tabla["secundaria"]["media_precision"] == "5/43"
        assert [f["solape"] for f in tabla["secundaria"]["diferencia_pareada"]] == [0, 1, 2, 3, 4, 5]
        assert tabla["secundaria"]["diferencia_pareada"][0]["varianza_precision"] == "38/903"

    def test_determinista_serializable_y_sin_veredictos(self):
        texto = json.dumps(fa.tabla_factibilidad(), sort_keys=True, ensure_ascii=False)
        assert texto == json.dumps(fa.tabla_factibilidad(), sort_keys=True, ensure_ascii=False)
        for prohibido in ("aprobad", "cumplid", "suficiente", "debil", "veredicto", '"GO"', "recomend"):
            assert prohibido not in texto, prohibido
        for supuesto in ("normal", "estacionari", "sigma", "uniforme"):
            assert supuesto in texto, supuesto


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------

def test_modulo_puro_y_sin_conexiones():
    arbol = ast.parse(ARCHIVO.read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add(nodo.module or "")
    assert modulos <= {"__future__", "math", "fractions", "statistics"}, modulos


def test_no_expuesto_en_la_web_ni_en_scripts():
    raiz = RAIZ_BACKEND / "app"
    rutas = [*(raiz / "api").rglob("*.py"), raiz / "main.py", *(raiz / "templates").rglob("*.html"),
             *(RAIZ_BACKEND / "scripts").rglob("*.py")]
    for ruta in rutas:
        assert "factibilidad_regla_prospectiva" not in ruta.read_text(encoding="utf-8"), ruta
