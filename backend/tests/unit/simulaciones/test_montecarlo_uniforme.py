"""Tests de `app/application/simulaciones/montecarlo_uniforme.py`
-Etapa AE-49, validada: referencia Monte Carlo exploratoria bajo
azar uniforme sobre el rango reutilizado 2081..2705. Todo sintetico:
historicos construidos con formulas aritmeticas, nunca PostgreSQL ni
resultados reales."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from random import Random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.simulaciones import montecarlo_uniforme as mc
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from app.domain.value_objects.combination import Combination
from tests.unit.simulaciones import sinteticos

ARCHIVO = Path(mc.__file__)


def _params(codigo="BALOTO"):
    dominio = BalotoGame() if codigo == "BALOTO" else BalotoRevanchaGame()
    return mc.parametros_desde_dominio(codigo, dominio)


def _reemplazar(historico, numero_sorteo, **cambios):
    return [dataclasses.replace(r, **cambios) if r.numero_sorteo == numero_sorteo else r for r in historico]


# ---------------------------------------------------------------------------
# Constantes fijadas antes de consultar cualquier resultado real
# ---------------------------------------------------------------------------

class TestConstantesFijadas:
    def test_rango_principal_es_el_contrato_congelado_de_ae36(self):
        from app.application.ml import ventanas_temporales
        from app.application.use_cases.evaluar_baseline_ml_probabilidad_numeros import CORTE_CONTRATO_AE36

        assert mc.RANGO_PRINCIPAL_AE49 == (2081, 2705)
        assert mc.RANGO_PRINCIPAL_AE49 == (ventanas_temporales.INICIO_HISTORICO_REAL, ventanas_temporales.FIN_CONTRATO_AE36)
        assert mc.RANGO_PRINCIPAL_AE49[1] == CORTE_CONTRATO_AE36
        assert mc.RANGO_PRINCIPAL_AE49[1] < ventanas_temporales.INICIO_HOLDOUT

    def test_juegos_sin_miloto_ni_colorloto(self):
        assert mc.JUEGOS_AE49 == ("BALOTO", "BALOTO_REVANCHA")

    def test_estadisticas_y_familia_fijadas(self):
        assert mc.ESTADISTICAS_AE49 == (
            "dispersion_frecuencia_numeros",
            "rango_frecuencia_numeros",
            "media_repeticiones_entre_sorteos",
            "dispersion_frecuencia_superbalota",
        )
        assert mc.TAMANO_FAMILIA_AE49 == 8 == len(mc.JUEGOS_AE49) * len(mc.ESTADISTICAS_AE49)
        assert mc.ALPHA_AE49 == 0.05

    def test_parametros_de_simulacion_fijados(self):
        assert mc.SEMILLA_AE49 == 20260926
        assert mc.ITERACIONES_AE49 == 10_000
        assert mc.GENERADOR_AE49 == "ae49-fisher-yates-random-v1"

    def test_parametros_vienen_del_dominio(self):
        p = _params("BALOTO")
        assert (p.rango_min, p.rango_max, p.cantidad_numeros, p.superbalota_min, p.superbalota_max) == (1, 43, 5, 1, 16)


# ---------------------------------------------------------------------------
# Verificacion estricta del rango 2081..2705
# ---------------------------------------------------------------------------

class TestRangoPrincipal:
    def test_historico_exacto_se_acepta_y_se_devuelve_ordenado(self):
        historico = sinteticos.historico_baloto()
        verificado = mc.verificar_rango_principal(list(reversed(historico)), BalotoGame())
        assert [r.numero_sorteo for r in verificado] == list(range(2081, 2706))

    @pytest.mark.parametrize("nombre, mutar", [
        ("sorteo_anterior_a_2081", lambda h: [dataclasses.replace(h[0], numero_sorteo=2080)] + h),
        ("hueco", lambda h: [r for r in h if r.numero_sorteo != 2300]),
        ("duplicado", lambda h: h + [h[10]]),
        ("termina_en_2704", lambda h: h[:-1]),
        ("incluye_2706", lambda h: h + [dataclasses.replace(h[-1], numero_sorteo=2706)]),
        ("vacio", lambda h: []),
        ("superbalota_ausente", lambda h: _reemplazar(h, 2400, superbalota=None)),
        ("superbalota_fuera_de_rango", lambda h: _reemplazar(h, 2400, superbalota=17)),
        ("numero_fuera_de_rango", lambda h: _reemplazar(h, 2400, numeros=(1, 2, 3, 4, 44))),
        ("numero_repetido", lambda h: _reemplazar(h, 2400, numeros=(1, 1, 3, 4, 5))),
        ("cantidad_incorrecta", lambda h: _reemplazar(h, 2400, numeros=(1, 2, 3, 4))),
    ])
    def test_cualquier_desviacion_se_rechaza(self, nombre, mutar):
        with pytest.raises(mc.EntradaSimulacionInvalidaError):
            mc.verificar_rango_principal(mutar(sinteticos.historico_baloto()), BalotoGame())

    def test_el_error_no_publica_numeros_ganadores(self):
        historico = _reemplazar(sinteticos.historico_baloto(), 2400, numeros=(1, 2, 3, 4, 44))
        with pytest.raises(mc.EntradaSimulacionInvalidaError) as error:
            mc.verificar_rango_principal(historico, BalotoGame())
        assert "44" not in str(error.value) and "2400" in str(error.value)


# ---------------------------------------------------------------------------
# Huella de la entrada normalizada
# ---------------------------------------------------------------------------

class TestHuellaEntrada:
    def test_respuesta_conocida(self):
        historico = [
            ResultadoNumerico(numero_sorteo=2082, fecha=sinteticos.date(2020, 1, 2), dia_semana="jueves",
                              numeros=(40, 3, 17, 8, 22), superbalota=9),
            ResultadoNumerico(numero_sorteo=2081, fecha=sinteticos.date(2020, 1, 1), dia_semana="miercoles",
                              numeros=(1, 2, 3, 4, 5), superbalota=16),
        ]
        esperado = hashlib.sha256(
            b"ae49-entrada-v1\nBALOTO\n2081:1,2,3,4,5:16\n2082:3,8,17,22,40:9\n"
        ).hexdigest()
        assert mc.huella_entrada("BALOTO", historico) == esperado

    @pytest.mark.parametrize("nombre, mutar", [
        ("numero", lambda h: _reemplazar(h, 2300, numeros=(1, 2, 3, 4, 6))),
        ("superbalota", lambda h: _reemplazar(h, 2300, superbalota=(h[219].superbalota % 16) + 1)),
        ("numero_sorteo", lambda h: [dataclasses.replace(h[-1], numero_sorteo=2800)] + h[:-1]),
        ("sorteo_quitado", lambda h: h[:-1]),
        ("sorteo_anadido", lambda h: h + [dataclasses.replace(h[-1], numero_sorteo=2706)]),
    ])
    def test_cualquier_cambio_de_datos_cambia_la_huella(self, nombre, mutar):
        historico = sinteticos.historico_baloto()
        assert mc.huella_entrada("BALOTO", mutar(historico)) != mc.huella_entrada("BALOTO", historico)

    def test_el_codigo_del_juego_forma_parte_de_la_huella(self):
        historico = sinteticos.historico_baloto()
        assert mc.huella_entrada("BALOTO", historico) != mc.huella_entrada("BALOTO_REVANCHA", historico)

    def test_fecha_dia_y_orden_no_cambian_la_huella(self):
        historico = sinteticos.historico_baloto()
        otro = [dataclasses.replace(r, fecha=sinteticos.date(1999, 1, 1), dia_semana="domingo") for r in historico]
        assert mc.huella_entrada("BALOTO", otro) == mc.huella_entrada("BALOTO", historico)
        assert mc.huella_entrada("BALOTO", list(reversed(historico))) == mc.huella_entrada("BALOTO", historico)


# ---------------------------------------------------------------------------
# Generador reproducible
# ---------------------------------------------------------------------------

class TestGenerador:
    def test_semilla_por_juego_estable_e_independiente(self):
        esperada = int.from_bytes(hashlib.sha256(b"20260926:BALOTO").digest()[:8], "big")
        assert mc.semilla_por_juego(20260926, "BALOTO") == esperada
        assert mc.semilla_por_juego(20260926, "BALOTO") != mc.semilla_por_juego(20260926, "BALOTO_REVANCHA")

    def test_misma_semilla_mismas_historias_otra_semilla_distintas(self):
        historico, params = sinteticos.historico(2081, 2180), _params()
        a = mc.simular_historia(Random(1), historico, params)
        b = mc.simular_historia(Random(1), historico, params)
        c = mc.simular_historia(Random(2), historico, params)
        assert a == b and a != c

    def test_historia_simulada_conserva_numeracion_y_es_valida(self):
        historico, params = sinteticos.historico(2081, 2280), _params()
        simulada = mc.simular_historia(Random(7), historico, params)
        assert [r.numero_sorteo for r in simulada] == [r.numero_sorteo for r in historico]
        juego = BalotoGame()
        for r in simulada:
            assert list(r.numeros) == sorted(r.numeros)
            assert juego.validate_draw(Combination(numeros=r.numeros, superbalota=r.superbalota)).is_valid

    def test_frecuencia_marginal_cercana_a_k_sobre_n(self):
        historico, params = sinteticos.historico(2081, 2280), _params()
        rng, conteo, total = Random(11), [0] * 44, 0
        for _ in range(100):
            for r in mc.simular_historia(rng, historico, params):
                total += 1
                for n in r.numeros:
                    conteo[n] += 1
        for n in range(1, 44):
            assert abs(conteo[n] / total - 5 / 43) < 0.012, n


# ---------------------------------------------------------------------------
# Estadisticas exactas
# ---------------------------------------------------------------------------

def _hist(numeros_y_superbalotas, desde=2081):
    return [
        ResultadoNumerico(numero_sorteo=desde + i, fecha=sinteticos.date(2020, 1, 1), dia_semana="lunes",
                          numeros=numeros, superbalota=sb)
        for i, (numeros, sb) in enumerate(numeros_y_superbalotas)
    ]


class TestEstadisticas:
    def test_valores_exactos_a_mano(self):
        historico = _hist([((1, 2, 3, 4, 5), 1), ((1, 2, 3, 6, 7), 1), ((8, 9, 10, 11, 12), 2)])
        valores = mc.calcular_estadisticas(historico, _params())
        n, k, t = 43, 5, 3
        conteos = [2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1] + [0] * 31
        esperado_1 = Fraction(sum((n * o - t * k) ** 2 for o in conteos), n * t * k)
        esperado_4 = Fraction(sum((16 * o - t) ** 2 for o in [2, 1] + [0] * 14), 16 * t)
        assert valores.como_fracciones() == (esperado_1, Fraction(2), Fraction(3 + 0, 2), esperado_4)

    def test_huecos_reducen_transiciones(self):
        historico = _hist([((1, 2, 3, 4, 5), 1), ((1, 2, 3, 6, 7), 1)]) + _hist([((1, 2, 3, 4, 5), 1)], desde=2090)
        valores = mc.calcular_estadisticas(historico, _params())
        assert valores.total_transiciones == 1
        assert valores.como_fracciones()[2] == Fraction(3, 1)

    def test_simulacion_conserva_los_denominadores(self):
        historico, params = sinteticos.historico(2081, 2180), _params()
        observados = mc.calcular_estadisticas(historico, params)
        simulados = mc.calcular_estadisticas(mc.simular_historia(Random(3), historico, params), params)
        assert observados.denominadores == simulados.denominadores
        assert all(isinstance(x, int) for x in observados.numeradores + observados.denominadores)


class TestCalibracion:
    def test_medias_simuladas_cercanas_a_la_referencia_analitica(self):
        resultado = mc.comparar_juego(sinteticos.historico(2081, 2280), _params(), semilla=5, iteraciones=300)
        por_nombre = {c.nombre: c for c in resultado.comparaciones}
        assert abs(float(por_nombre["dispersion_frecuencia_numeros"].media) - 38) < 2.5
        assert abs(float(por_nombre["dispersion_frecuencia_numeros"].media) - 42) > 2.5  # no es N-1
        assert por_nombre["dispersion_frecuencia_numeros"].referencia == Fraction(38)
        assert abs(float(por_nombre["media_repeticiones_entre_sorteos"].media) - 25 / 43) < 0.03
        assert por_nombre["media_repeticiones_entre_sorteos"].referencia == Fraction(25, 43)
        assert abs(float(por_nombre["dispersion_frecuencia_superbalota"].media) - 15) < 2
        assert por_nombre["dispersion_frecuencia_superbalota"].referencia == Fraction(15)
        assert por_nombre["rango_frecuencia_numeros"].referencia is None


# ---------------------------------------------------------------------------
# p-valores empiricos y familia de ocho comparaciones
# ---------------------------------------------------------------------------

def _extremo(desde=2081, total=100):
    return _hist([((1, 2, 3, 4, 5), 1)] * total, desde=desde)


class TestPValores:
    def test_formula_bilateral_y_nunca_cero(self):
        resultado = mc.comparar_juego(_extremo(), _params(), semilla=1, iteraciones=200)
        for comparacion in resultado.comparaciones:
            assert comparacion.p_valor == Fraction(2, 201)
            assert comparacion.p_valor > 0
            assert comparacion.percentil == 1

    def test_intermedios_exactos_sin_floats(self):
        resultado = mc.comparar_juego(sinteticos.historico(2081, 2130), _params(), semilla=1, iteraciones=20)
        for c in resultado.comparaciones:
            for valor in (c.observado, c.media, c.varianza, c.percentil, c.p_valor):
                assert isinstance(valor, (int, Fraction)), (c.nombre, type(valor))

    def test_determinista(self):
        a = mc.comparar_juego(sinteticos.historico(2081, 2130), _params(), semilla=9, iteraciones=30)
        b = mc.comparar_juego(sinteticos.historico(2081, 2130), _params(), semilla=9, iteraciones=30)
        assert a == b


def _reporte(historicos, iteraciones, semilla=1):
    resultados = [
        mc.comparar_juego(historicos[0], _params("BALOTO"), semilla=mc.semilla_por_juego(semilla, "BALOTO"),
                          iteraciones=iteraciones),
        mc.comparar_juego(historicos[1], _params("BALOTO_REVANCHA"),
                          semilla=mc.semilla_por_juego(semilla, "BALOTO_REVANCHA"),
                          iteraciones=iteraciones),
    ]
    return mc.construir_reporte("0006", resultados, semilla=semilla, iteraciones=iteraciones)


class TestFamiliaDeOcho:
    def test_bonferroni_una_vez_sobre_las_ocho(self):
        reporte = _reporte([_extremo(), sinteticos.historico(2081, 2180)], iteraciones=40)
        entradas = [e for j in reporte["juegos"] for e in j["estadisticas"]]
        assert len(entradas) == 8
        for e in entradas:
            assert e["p_valor_ajustado_bonferroni"] == min(1.0, e["p_valor_empirico"] * 8)

    def test_umbral_depende_de_la_familia_de_ocho_y_no_de_cuatro(self):
        # p crudo = 2/201 ~ 0.00995: con 4 comparaciones pasaria (0.0398), con 8 no (0.0796).
        reporte = _reporte([_extremo(), sinteticos.historico(2081, 2180)], iteraciones=200)
        baloto = reporte["juegos"][0]["estadisticas"]
        assert all(abs(e["p_valor_empirico"] - 2 / 201) < 1e-12 for e in baloto)
        assert not any(e["supera_umbral_exploratorio"] for e in baloto)

    def test_discrepancia_extrema_supera_el_umbral_exploratorio(self):
        reporte = _reporte([_extremo(), sinteticos.historico(2081, 2180)], iteraciones=400)
        assert all(e["supera_umbral_exploratorio"] for e in reporte["juegos"][0]["estadisticas"])

    def test_historico_simulado_bajo_azar_no_supera_el_umbral(self):
        params = _params()
        historico = mc.simular_historia(Random(424242), sinteticos.historico(2081, 2280), params)
        otro = mc.simular_historia(Random(515151), sinteticos.historico(2081, 2280), params)
        reporte = _reporte([historico, otro], iteraciones=200)
        assert not any(e["supera_umbral_exploratorio"] for j in reporte["juegos"] for e in j["estadisticas"])

    def test_la_familia_exige_exactamente_ocho(self):
        solo_uno = [mc.comparar_juego(_extremo(), _params(), semilla=1, iteraciones=10)]
        with pytest.raises(ValueError):
            mc.construir_reporte("0006", solo_uno, semilla=1, iteraciones=10)


# ---------------------------------------------------------------------------
# Reporte JSON: caracter exploratorio y claves exactas
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def reporte():
    return _reporte([sinteticos.historico(2081, 2130), sinteticos.historico(2081, 2130, a=11, b=13)],
                    iteraciones=20)


class TestReporte:
    def test_claves_exactas(self, reporte):
        assert set(reporte) == {
            "esquema", "caracter", "alembic_revision", "parametros", "rango_principal",
            "familia_comparaciones", "juegos", "nota",
        }
        assert reporte["esquema"] == "simulacion-azar-uniforme/1.0"
        assert reporte["caracter"] == "exploratorio_sobre_datos_reutilizados"
        assert reporte["parametros"] == {
            "semilla": 1, "iteraciones": 20, "generador": "ae49-fisher-yates-random-v1",
            "estadisticas": list(mc.ESTADISTICAS_AE49),
        }
        assert set(reporte["rango_principal"]) == {"desde", "hasta", "tramos"}
        assert (reporte["rango_principal"]["desde"], reporte["rango_principal"]["hasta"]) == (2081, 2705)
        assert reporte["familia_comparaciones"] == {
            "metodo": "bonferroni", "tamano": 8, "alcance": "ocho_comparaciones_de_esta_ejecucion",
            "alpha": 0.05, "cobertura": mc.COBERTURA_AJUSTE,
        }
        assert [j["codigo"] for j in reporte["juegos"]] == ["BALOTO", "BALOTO_REVANCHA"]
        for juego in reporte["juegos"]:
            assert set(juego) == {
                "codigo", "total_sorteos", "total_transiciones", "total_superbalotas", "entrada_sha256",
                "estadisticas",
            }
            assert [e["nombre"] for e in juego["estadisticas"]] == list(mc.ESTADISTICAS_AE49)
            for e in juego["estadisticas"]:
                assert set(e) == {
                    "nombre", "observado", "media_simulada", "desviacion_simulada", "referencia_analitica",
                    "percentil_observado", "p_valor_empirico", "p_valor_ajustado_bonferroni",
                    "supera_umbral_exploratorio",
                }
                assert isinstance(e["supera_umbral_exploratorio"], bool)

    def test_textos_fijos_exploratorios(self, reporte):
        assert reporte["nota"] == mc.NOTA_AE49
        assert reporte["rango_principal"]["tramos"] == mc.TEXTO_TRAMOS
        for fragmento in ("exploratorio", "no es confirmatorio", "no esta prerregistrado",
                          "no es evidencia prospectiva", "NO-GO de AE-39"):
            assert fragmento in mc.NOTA_AE49
        assert "2591..2705" in mc.TEXTO_TRAMOS and "2706" in mc.TEXTO_TRAMOS
        assert "no corrige la seleccion ni la inspeccion previa" in mc.COBERTURA_AJUSTE
        assert "no demuestra" in mc.COBERTURA_AJUSTE

    def test_no_afirma_tasa_de_error_del_proceso_ni_confirmacion_ni_recomienda(self, reporte):
        texto = json.dumps(reporte, ensure_ascii=False).lower()
        assert '"significativo"' not in texto
        # Solo se descuentan las frases NEGATIVAS fijas del disclaimer; cualquier
        # otra aparicion (un campo o un texto que recomiende) sigue fallando.
        for frase_negativa in mc.FRASES_NEGATIVAS_DISCLAIMER:
            assert frase_negativa in texto, frase_negativa
            texto = texto.replace(frase_negativa, "")
        for prohibido in ("tasa de falsas alarmas", "confirmatorio", "5 %", "5%", "demuestra que",
                          "prediccion", "recomendacion", "recomendamos", "recomendad", "combinacion"):
            assert prohibido not in texto, prohibido

    def test_ninguna_clave_presenta_recomendaciones_o_combinaciones(self, reporte):
        def claves(nodo):
            if isinstance(nodo, dict):
                for clave, valor in nodo.items():
                    yield clave
                    yield from claves(valor)
            elif isinstance(nodo, list):
                for valor in nodo:
                    yield from claves(valor)

        for clave in claves(reporte):
            for prohibido in ("recomend", "combinacion", "prediccion", "sugerid", "jugar", "apuesta"):
                assert prohibido not in clave.lower(), clave

    def test_una_recomendacion_real_seria_detectada(self, reporte):
        # Control negativo: la comprobacion no queda vacia por descontar el disclaimer.
        falso = json.loads(json.dumps(reporte))
        falso["juegos"][0]["recomendacion"] = "jugar los numeros menos frecuentes"
        texto = json.dumps(falso, ensure_ascii=False).lower()
        for frase_negativa in mc.FRASES_NEGATIVAS_DISCLAIMER:
            texto = texto.replace(frase_negativa, "")
        assert "recomendacion" in texto

    def test_sin_numeros_ganadores_ni_claves_predictivas(self, reporte):
        from scripts.comparacion_estado_prediccion import CLAVES_PREDICTIVAS

        def recorrer(nodo):
            if isinstance(nodo, dict):
                for clave, valor in nodo.items():
                    assert clave not in CLAVES_PREDICTIVAS | {"numeros", "superbalota", "sorteos"}, clave
                    recorrer(valor)
            elif isinstance(nodo, list):
                assert not (nodo and all(isinstance(x, int) and not isinstance(x, bool) for x in nodo)), nodo
                for valor in nodo:
                    recorrer(valor)

        recorrer(reporte)

    def test_mismo_reporte_mismos_bytes(self):
        a = _reporte([sinteticos.historico(2081, 2130), sinteticos.historico(2081, 2130, a=11, b=13)], iteraciones=20)
        b = _reporte([sinteticos.historico(2081, 2130), sinteticos.historico(2081, 2130, a=11, b=13)], iteraciones=20)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ---------------------------------------------------------------------------
# Estructura: aritmetica exacta, generador y aislamiento
# ---------------------------------------------------------------------------

def _arbol():
    return ast.parse(ARCHIVO.read_text(encoding="utf-8"))


def _importaciones(arbol):
    salida = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            salida.extend((alias.name, None) for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            salida.extend((nodo.module or "", alias.name) for alias in nodo.names)
    return salida


class TestEstructura:
    def test_sin_sum_ni_numpy_scipy_statistics(self):
        arbol = _arbol()
        llamadas = [n.func.id for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        assert "sum" not in llamadas
        for modulo, _ in _importaciones(arbol):
            assert modulo.split(".")[0] not in {"numpy", "scipy", "statistics", "sklearn", "sqlalchemy"}, modulo

    def test_generador_solo_random_de_random(self):
        arbol = _arbol()
        desde_random = {nombre for modulo, nombre in _importaciones(arbol) if modulo == "random"}
        assert desde_random <= {"Random"}
        assert ("random", None) not in _importaciones(arbol)
        prohibidos = {"sample", "randint", "choice", "choices", "shuffle", "randrange", "uniform",
                      "getrandbits", "gauss", "seed"}
        atributos = {n.func.attr for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert not (atributos & prohibidos), atributos & prohibidos

    def test_reutiliza_motor_y_bonferroni_existentes(self):
        importados = {nombre for _, nombre in _importaciones(_arbol())}
        assert {"calcular_frecuencia_numeros", "calcular_frecuencia_superbalota",
                "calcular_repeticiones_entre_sorteos", "aplicar_correccion_bonferroni"} <= importados

    def test_no_importa_ml_ni_repositorios(self):
        for modulo, _ in _importaciones(_arbol()):
            assert not modulo.startswith("app.application.ml"), modulo
            assert not modulo.startswith("app.infrastructure"), modulo
            assert "prediccion" not in modulo and "inferencia" not in modulo, modulo
