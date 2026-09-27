"""Tests de `app/application/simulaciones/exploracion_inferencia_prospectiva.py`
-Etapa AE-54, validada: banco de exploracion sintetica de metodos
candidatos de inferencia. Verifican aritmetica, construccion de los
generadores y reproducibilidad; ninguna prueba afirma tasas de rechazo,
tamano, cobertura ni potencia. Todo sintetico: sin PostgreSQL, datos
reales ni predicciones reales."""
from __future__ import annotations

import ast
import dataclasses
import json
import math
from fractions import Fraction
from pathlib import Path
from random import Random

import pytest
from scipy import stats

from app.application.ml.especificacion_evaluacion_prospectiva import metricas_por_sorteo
from app.application.simulaciones import exploracion_inferencia_prospectiva as ex
from app.application.simulaciones import montecarlo_uniforme as ae49

ARCHIVO = Path(ex.__file__)
RAIZ_BACKEND = ARCHIVO.resolve().parents[3]
REDUCIDOS = dataclasses.replace(ex.PARAMETROS_AE54, n=12, b=39, r_e=3, r_l=2, calentamiento_l=25)
"""Parametros minimos solo para probar la mecanica; nunca la exploracion."""


class _RngFijo:
    def __init__(self, valores):
        self.valores = list(valores)

    def random(self):
        return self.valores.pop(0)


# ---------------------------------------------------------------------------
# Parametros fijos del banco
# ---------------------------------------------------------------------------

class TestParametros:
    def test_valores_fijados(self):
        p = ex.PARAMETROS_AE54
        assert (p.n, p.b, p.r_e, p.r_l, p.semilla) == (100, 999, 2000, 500, 20261001)
        assert (p.longitudes_bloque, p.ancho_banda) == ((5, 10), 4)
        assert (p.calentamiento_ar, p.calentamiento_l, p.ventana_l2) == (200, 100, 20)
        assert ex.ESCENARIOS_E == ("E1", "E2", "E3", "E4", "E5", "E6")
        assert ex.ESCENARIOS_L == ("L1", "L2")
        assert ex.METODOS == ("M1", "M2a", "M2b", "M3a", "M3b", "M4")

    def test_ancho_de_banda_es_la_regla_declarada(self):
        assert ex.PARAMETROS_AE54.ancho_banda == math.floor(4 * (100 / 100) ** (2 / 9))

    def test_valores_criticos_frente_a_scipy(self):
        assert ex.T_CRITICO_99_0975 == pytest.approx(stats.t.ppf(0.975, 99), abs=1e-12)
        assert ex.CHI2_2_095 == pytest.approx(stats.chi2.ppf(0.95, 2), abs=1e-12)

    @pytest.mark.parametrize("cambio", [dict(b=1000), dict(b=0), dict(n=1), dict(r_e=0), dict(ancho_banda=100),
                                        dict(longitudes_bloque=(0,)), dict(ventana_l2=0), dict(calentamiento_l=5)])
    def test_parametros_invalidos(self, cambio):
        with pytest.raises(ex.ParametrosExploracionError):
            dataclasses.replace(ex.PARAMETROS_AE54, **cambio)


# ---------------------------------------------------------------------------
# Generadores
# ---------------------------------------------------------------------------

class TestGeneradores:
    def test_innovacion_con_soporte_exactamente_simetrico(self):
        escala = 2.0 ** 53
        for k in (0, 1, 2, 12345, 2 ** 52, 2 ** 53 - 1):
            z = ex.innovacion_simetrica(_RngFijo([k / escala]))
            espejo = ex.innovacion_simetrica(_RngFijo([(2 ** 53 - 1 - k) / escala]))
            assert z == -espejo
            assert z != 0.0
        assert ex.innovacion_simetrica(_RngFijo([0.0])) == -((2 ** 53 - 1) / escala) * math.sqrt(3)

    @pytest.mark.parametrize("escenario", ex.ESCENARIOS_E)
    def test_series_e_con_longitud_y_reproducibles(self, escenario):
        a = ex.generar_serie_e(escenario, Random(7), 50, 200)
        assert len(a) == 50 and all(math.isfinite(v) for v in a)
        assert a == ex.generar_serie_e(escenario, Random(7), 50, 200)
        assert a != ex.generar_serie_e(escenario, Random(8), 50, 200)

    def test_e1_es_la_innovacion(self):
        rng = Random(3)
        esperado = [ex.innovacion_simetrica(rng) for _ in range(10)]
        assert ex.generar_serie_e("E1", Random(3), 10, 200) == esperado

    def test_e3_e4_son_ar1_con_los_coeficientes_declarados(self):
        for escenario, phi in (("E3", 0.3), ("E4", 0.6)):
            rng = Random(5)
            d = 0.0
            serie = []
            for t in range(200 + 10):
                d = phi * d + math.sqrt(1 - phi * phi) * ex.innovacion_simetrica(rng)
                if t >= 200:
                    serie.append(d)
            assert ex.generar_serie_e(escenario, Random(5), 10, 200) == serie

    def test_e5_es_ma_de_ventanas_solapadas(self):
        rng = Random(9)
        z = [ex.innovacion_simetrica(rng) for _ in range(10 + 4)]
        esperado = [math.fsum(z[t:t + 5]) / math.sqrt(5) for t in range(10)]
        assert ex.generar_serie_e("E5", Random(9), 10, 200) == esperado

    def test_e6_es_heterocedastico_con_la_formula_declarada(self):
        rng = Random(11)
        d = 0.0
        serie = []
        for t in range(200 + 10):
            d = math.sqrt(0.2 + 0.7 * d * d) * ex.innovacion_simetrica(rng)
            if t >= 200:
                serie.append(d)
        assert ex.generar_serie_e("E6", Random(11), 10, 200) == serie

    def test_e2_mezcla_con_factor_uno_o_cinco(self):
        rng = Random(13)
        esperado = []
        for _ in range(20):
            z = ex.innovacion_simetrica(rng)
            esperado.append((5.0 if rng.random() < 0.1 else 1.0) * z)
        assert ex.generar_serie_e("E2", Random(13), 20, 200) == esperado

    def test_escenario_desconocido(self):
        with pytest.raises(ex.ParametrosExploracionError):
            ex.generar_serie_e("E9", Random(1), 10, 200)

    def test_muestra_sin_reemplazo_igual_al_algoritmo_de_ae49(self):
        for semilla in range(20):
            assert ex.muestra_sin_reemplazo(Random(semilla), 43, 5) == ae49._muestra_sin_reemplazo(Random(semilla), 43, 5)

    def test_vector_l1_valido_y_fijo(self):
        p = ex.vector_l1(20261001)
        assert len(p) == 43 and all(0.0 < v < 1.0 for v in p)
        assert math.fsum(p) == pytest.approx(5.0, abs=1e-12)
        assert p == ex.vector_l1(20261001) and p != ex.vector_l1(1)

    def test_probabilidades_l2_solo_usan_sorteos_previos(self):
        previos = [[1, 2, 3, 4, 5]] * 10 + [[6, 7, 8, 9, 10]] * 10
        p = ex.probabilidades_l2(previos, 20)
        assert math.fsum(p) == pytest.approx(5.0, abs=1e-12)
        assert p[0] == pytest.approx(0.9 * 5 / 43 + 0.1 * 10 / 20)
        assert p[42] == pytest.approx(0.9 * 5 / 43)
        assert ex.probabilidades_l2(previos + [[40, 41, 42, 43, 1]], 20) != p
        assert ex.probabilidades_l2([[40, 41, 42, 43, 1]] + previos, 20) == p

    def test_serie_l_usa_metricas_por_sorteo(self):
        series = ex.generar_series_l("L2", Random(21), 3, 25, 20, ex.vector_l1(1))
        rng = Random(21)
        sorteos = [sorted(n + 1 for n in ex.muestra_sin_reemplazo(rng, 43, 5)) for _ in range(25 + 3)]
        esperado_ll, esperado_b = [], []
        for t in range(25, 28):
            m = metricas_por_sorteo("BALOTO", t + 1, ex.probabilidades_l2(sorteos[:t], 20), sorteos[t])
            esperado_ll.append(m.diferencias["log_loss"])
            esperado_b.append(m.diferencias["brier_score"])
        assert series == {"log_loss": esperado_ll, "brier_score": esperado_b}

    def test_serie_l1_usa_el_vector_fijo(self):
        q = ex.vector_l1(5)
        series = ex.generar_series_l("L1", Random(2), 2, 25, 20, q)
        rng = Random(2)
        sorteos = [sorted(n + 1 for n in ex.muestra_sin_reemplazo(rng, 43, 5)) for _ in range(27)]
        m = metricas_por_sorteo("BALOTO", 26, q, sorteos[25])
        assert series["log_loss"][0] == m.diferencias["log_loss"]


# ---------------------------------------------------------------------------
# Metodos contra calculos a mano
# ---------------------------------------------------------------------------

SERIE = [0.5, -1.0, 2.0, 0.25, -0.75, 1.5]


def _gamma_fraccion(x, k):
    x = [Fraction(v) for v in x]
    media = sum(x) / len(x)
    return sum((x[t] - media) * (x[t - k] - media) for t in range(k, len(x))) / len(x)


class TestMetodos:
    def test_media_y_autocovarianzas(self):
        assert ex.media(SERIE) == float(sum(Fraction(v) for v in SERIE) / 6)
        for k in range(4):
            assert ex.autocovarianza(SERIE, k) == pytest.approx(float(_gamma_fraccion(SERIE, k)), abs=1e-15)

    def test_dm_hln(self):
        n = 6
        g0 = float(_gamma_fraccion(SERIE, 0))
        esperado = math.sqrt((n - 1) / n) * ex.media(SERIE) / math.sqrt(g0 / n)
        resultado = ex.metodo_dm_hln(SERIE)
        assert resultado["estadistico"] == pytest.approx(esperado, rel=1e-13)
        assert resultado["rechaza"] is (esperado > ex.T_CRITICO_99_0975)

    def test_dm_hac_bartlett(self):
        m = 2
        v = _gamma_fraccion(SERIE, 0) + 2 * sum((1 - Fraction(k, m + 1)) * _gamma_fraccion(SERIE, k) for k in range(1, m + 1))
        esperado = ex.media(SERIE) / math.sqrt(float(v) / 6)
        resultado = ex.metodo_dm_hac(SERIE, m)
        assert resultado["estadistico"] == pytest.approx(esperado, rel=1e-13)
        assert resultado["degenerado"] is False

    def test_dm_degenerado_con_serie_constante(self):
        for resultado in (ex.metodo_dm_hln([1.0] * 5), ex.metodo_dm_hac([1.0] * 5, 2)):
            assert resultado == {"estadistico": None, "rechaza": False, "degenerado": True}

    def test_giacomini_white(self):
        x = [Fraction(v) for v in SERIE]
        z = [(x[t], x[t - 1] * x[t]) for t in range(1, 6)]
        n = len(z)
        zb = [sum(c[i] for c in z) / n for i in range(2)]
        a = sum(c[0] * c[0] for c in z) / n
        b = sum(c[0] * c[1] for c in z) / n
        d = sum(c[1] * c[1] for c in z) / n
        det = a * d - b * b
        esperado = n * (d * zb[0] ** 2 - 2 * b * zb[0] * zb[1] + a * zb[1] ** 2) / det
        resultado = ex.metodo_gw(SERIE)
        assert resultado["estadistico"] == pytest.approx(float(esperado), rel=1e-12)
        assert resultado["rechaza"] is (float(esperado) > ex.CHI2_2_095)

    def test_giacomini_white_singular(self):
        resultado = ex.metodo_gw([0.0, 1.0, 0.0, 1.0, 0.0])
        assert resultado == {"estadistico": None, "rechaza": False, "singular": True}

    def test_estadisticos_de_orden_del_intervalo(self):
        valores = [float(v) for v in range(999, 0, -1)]
        assert ex.limites_percentil(valores) == (25.0, 975.0)
        assert ex.limites_percentil([float(v) for v in range(1, 40)]) == (1.0, 39.0)
        with pytest.raises(ex.ParametrosExploracionError):
            ex.limites_percentil([1.0] * 100)

    def test_indices_de_bloques_circulares(self):
        rng = Random(4)
        inicios = [int(Random(4).random() * 10) for _ in range(1)]
        indices = ex.indices_bloques_circulares(rng, 10, 3)
        assert len(indices) == 10
        rng2 = Random(4)
        esperados = []
        for _ in range(4):
            s = int(rng2.random() * 10)
            esperados.extend((s + j) % 10 for j in range(3))
        assert indices == esperados[:10]
        assert indices[0] == inicios[0]

    def test_bootstrap_iid_y_bloques(self):
        serie = [float(v) for v in range(1, 13)]
        for resultado in (ex.metodo_bootstrap_iid(serie, Random(1), 39),
                          ex.metodo_bootstrap_bloques(serie, Random(1), 39, 3)):
            assert set(resultado) == {"inferior", "superior", "rechaza"}
            assert resultado["inferior"] <= ex.media(serie) <= resultado["superior"]
            assert resultado["rechaza"] is (resultado["inferior"] > 0)
        rng = Random(1)
        medias = sorted(ex.media([serie[int(rng.random() * 12)] for _ in range(12)]) for _ in range(39))
        assert ex.metodo_bootstrap_iid(serie, Random(1), 39)["inferior"] == medias[0]
        assert ex.metodo_bootstrap_iid(serie, Random(1), 39)["superior"] == medias[38]

    def test_autocorrelacion(self):
        assert ex.autocorrelaciones(SERIE, 3) == pytest.approx(
            [float(_gamma_fraccion(SERIE, k) / _gamma_fraccion(SERIE, 0)) for k in (1, 2, 3)], abs=1e-14)


# ---------------------------------------------------------------------------
# Reporte: reproducible, exploratorio y sin veredictos
# ---------------------------------------------------------------------------

def _texto(reporte):
    return json.dumps(reporte, sort_keys=True, ensure_ascii=False)


@pytest.fixture(scope="module")
def reporte():
    return ex.ejecutar_exploracion(REDUCIDOS)


class TestReporte:
    def test_reproducible_en_el_mismo_entorno_y_sensible_a_la_semilla(self, reporte):
        assert _texto(reporte) == _texto(ex.ejecutar_exploracion(REDUCIDOS))
        otro = ex.ejecutar_exploracion(dataclasses.replace(REDUCIDOS, semilla=1))
        assert _texto(otro["escenarios"]) != _texto(reporte["escenarios"])

    def test_estructura(self, reporte):
        assert reporte["esquema"] == ex.ESQUEMA_AE54 and reporte["caracter"] == "exploratorio_sintetico"
        assert reporte["parametros"]["n"] == 12 and reporte["parametros"]["b"] == 39
        ids = [(e["id"], e["metrica"]) for e in reporte["escenarios"]]
        assert ids == [(e, None) for e in ex.ESCENARIOS_E] + [
            ("L1", "log_loss"), ("L1", "brier_score"), ("L2", "log_loss"), ("L2", "brier_score")]
        for escenario in reporte["escenarios"]:
            replicas = 3 if escenario["id"].startswith("E") else 2
            assert [m["id"] for m in escenario["metodos"]] == list(ex.METODOS)
            assert len(escenario["diagnostico"]["autocorrelacion_media"]) == 5
            for metodo in escenario["metodos"]:
                assert metodo["replicas"] == replicas
                assert 0 <= metodo["rechazos"] <= replicas
                r = metodo["rechazos"] / replicas
                assert metodo["frecuencia"] == r
                assert metodo["error_mc"] == math.sqrt(r * (1 - r) / replicas)

    def test_hipotesis_por_escenario(self, reporte):
        por_id = {(e["id"], e["metrica"]): e["hipotesis"] for e in reporte["escenarios"]}
        for e in ("E1", "E2", "E6"):
            assert por_id[(e, None)] == {"media_cero_por_construccion": True, "nula_condicional_m4_verdadera": True}
        for e in ("E3", "E4", "E5"):
            assert por_id[(e, None)] == {"media_cero_por_construccion": True, "nula_condicional_m4_verdadera": False}
        assert por_id[("L2", "log_loss")] == {"media_cero_por_construccion": False, "nula_condicional_m4_verdadera": False}

    def test_sin_veredictos_ni_duracion(self, reporte):
        texto = _texto(reporte)
        for prohibido in ('"aprobado"', '"aprobada"', "cumplido", '"GO"', "veredicto", "duracion", "valido"):
            assert prohibido not in texto, prohibido
        for fragmento in ("exploratori", "no aprueba", "mismo entorno", "no establece"):
            assert fragmento in reporte["alcance"], fragmento


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------

def _importaciones():
    salida = []
    for nodo in ast.walk(ast.parse(ARCHIVO.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            salida.extend((alias.name, None) for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            salida.extend((nodo.module or "", alias.name) for alias in nodo.names)
    return salida


def test_modulo_puro_sin_conexiones_prohibidas():
    for modulo, nombre in _importaciones():
        assert modulo.split(".")[0] not in {"numpy", "scipy", "sklearn", "pandas", "sqlalchemy", "fastapi", "time",
                                            "datetime", "os", "pathlib", "statistics"}, modulo
        for prohibido in ("registro_prospectivo", "inferencia", "prediccion_bloqueada", "resolver_estado_prediccion",
                          "diagnostico_bloqueo", "modelo", "infrastructure", "incertidumbre"):
            assert prohibido not in modulo, modulo
        assert not (nombre or "").startswith("_"), (modulo, nombre)
    llamadas = {n.func.attr for n in ast.walk(ast.parse(ARCHIVO.read_text(encoding="utf-8")))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not llamadas & {"gauss", "normalvariate", "sample", "shuffle", "choice", "choices"}


def test_no_expuesto_en_la_web():
    raiz = RAIZ_BACKEND / "app"
    for ruta in [*(raiz / "api").rglob("*.py"), raiz / "main.py", *(raiz / "templates").rglob("*.html")]:
        assert "exploracion_inferencia_prospectiva" not in ruta.read_text(encoding="utf-8"), ruta
