"""
Tests de `application/estadisticas/motor/probabilidad.py`.

Ninguna función de este módulo recibe una lista de resultados
históricos -verificado también estructuralmente (ver
TestModuloNoDependeDeHistorico): las firmas solo aceptan enteros.
"""
from __future__ import annotations

import inspect
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor import probabilidad
from app.application.estadisticas.motor.probabilidad import (
    probabilidad_combinacion_exacta_desde_espacio_muestral,
    probabilidad_combinacion_exacta_sin_repeticion,
    probabilidad_seleccion_individual,
)
from app.application.estadisticas.tipos import ProbabilidadTeorica


class TestProbabilidadSeleccionIndividual:
    def test_miloto_5_de_39(self):
        p = probabilidad_seleccion_individual(universo=39, seleccion=5)
        assert isinstance(p, ProbabilidadTeorica)
        assert p.probabilidad == pytest.approx(5 / 39)
        assert p.valor == "*"
        assert p.metodo == "K/N = 5/39"

    def test_baloto_5_de_43(self):
        p = probabilidad_seleccion_individual(universo=43, seleccion=5)
        assert p.probabilidad == pytest.approx(5 / 43)

    def test_baloto_revancha_5_de_43_mismo_resultado_que_baloto(self):
        # Baloto y Revancha comparten mecánica -misma fórmula, mismo
        # resultado; la separación entre ambos ocurre en la capa de
        # orquestación (juego_id distinto), no aquí.
        p_baloto = probabilidad_seleccion_individual(universo=43, seleccion=5)
        p_revancha = probabilidad_seleccion_individual(universo=43, seleccion=5)
        assert p_baloto.probabilidad == p_revancha.probabilidad == pytest.approx(5 / 43)

    def test_superbalota_1_de_16(self):
        p = probabilidad_seleccion_individual(universo=16, seleccion=1)
        assert p.probabilidad == pytest.approx(1 / 16)
        assert p.metodo == "K/N = 1/16"

    def test_superbalota_nunca_se_mezcla_con_el_pool_principal(self):
        p_principal = probabilidad_seleccion_individual(universo=43, seleccion=5)
        p_superbalota = probabilidad_seleccion_individual(universo=16, seleccion=1)
        assert p_principal.probabilidad != p_superbalota.probabilidad

    def test_reutiliza_correctamente_frecuencia_relativa_esperada(self):
        from app.application.estadisticas.motor.frecuencia import frecuencia_relativa_esperada
        p = probabilidad_seleccion_individual(universo=39, seleccion=5)
        assert p.probabilidad == frecuencia_relativa_esperada(5, 39)

    def test_universo_invalido_lanza_value_error(self):
        with pytest.raises(ValueError):
            probabilidad_seleccion_individual(universo=0, seleccion=1)

    def test_es_probabilidad_teorica_nunca_frecuencia_observada(self):
        p = probabilidad_seleccion_individual(universo=39, seleccion=5)
        assert isinstance(p, ProbabilidadTeorica)
        assert not hasattr(p, "apariciones")  # no es (ni se parece a) FrecuenciaObservada


class TestProbabilidadCombinacionExactaSinRepeticion:
    def test_baloto_1_sobre_c43_5(self):
        p = probabilidad_combinacion_exacta_sin_repeticion(universo=43, seleccion=5)
        assert p.probabilidad == pytest.approx(1 / math.comb(43, 5))
        assert p.metodo == "1/C(43,5)"

    def test_miloto_1_sobre_c39_5(self):
        p = probabilidad_combinacion_exacta_sin_repeticion(universo=39, seleccion=5)
        assert p.probabilidad == pytest.approx(1 / math.comb(39, 5))

    def test_k_igual_cero_es_valido_c_n_0_es_1(self):
        p = probabilidad_combinacion_exacta_sin_repeticion(universo=39, seleccion=0)
        assert p.probabilidad == 1.0
        assert p.metodo == "1/C(39,0)"

    def test_k_igual_n_es_valido_c_n_n_es_1(self):
        p = probabilidad_combinacion_exacta_sin_repeticion(universo=5, seleccion=5)
        assert p.probabilidad == 1.0

    def test_k_mayor_que_n_lanza_value_error(self):
        with pytest.raises(ValueError, match="mayor que universo"):
            probabilidad_combinacion_exacta_sin_repeticion(universo=5, seleccion=10)

    def test_universo_no_positivo_lanza_value_error(self):
        with pytest.raises(ValueError):
            probabilidad_combinacion_exacta_sin_repeticion(universo=0, seleccion=1)
        with pytest.raises(ValueError):
            probabilidad_combinacion_exacta_sin_repeticion(universo=-5, seleccion=1)

    def test_seleccion_negativa_lanza_value_error(self):
        with pytest.raises(ValueError):
            probabilidad_combinacion_exacta_sin_repeticion(universo=39, seleccion=-1)

    def test_usa_math_comb(self):
        p = probabilidad_combinacion_exacta_sin_repeticion(universo=10, seleccion=3)
        assert p.probabilidad == pytest.approx(1 / math.comb(10, 3))


class TestProbabilidadCombinacionExactaDesdeEspacioMuestral:
    def test_espacio_muestral_arbitrario(self):
        p = probabilidad_combinacion_exacta_desde_espacio_muestral(1_000_000)
        assert p.probabilidad == pytest.approx(1 / 1_000_000)
        assert "1000000" in p.metodo
        assert "provisto externamente" in p.metodo

    def test_agnostica_al_origen_del_tamano(self):
        # Un mismo tamaño de espacio muestral produce el mismo
        # resultado sin importar si "vendría" de una fórmula con o
        # sin repetición -la función no lo sabe ni lo necesita saber.
        p1 = probabilidad_combinacion_exacta_desde_espacio_muestral(575_757)
        p2 = probabilidad_combinacion_exacta_desde_espacio_muestral(575_757)
        assert p1 == p2

    def test_espacio_muestral_cero_lanza_value_error(self):
        with pytest.raises(ValueError):
            probabilidad_combinacion_exacta_desde_espacio_muestral(0)

    def test_espacio_muestral_negativo_lanza_value_error(self):
        with pytest.raises(ValueError):
            probabilidad_combinacion_exacta_desde_espacio_muestral(-10)

    def test_no_implementa_ninguna_formula_de_repeticion(self):
        # Verificación estructural: la función no debe requerir
        # ningún argumento relacionado con repetición, rango o
        # cantidad de elementos -solo el tamaño ya resuelto.
        parametros = list(inspect.signature(probabilidad_combinacion_exacta_desde_espacio_muestral).parameters)
        assert parametros == ["tamano_espacio_muestral"]


class TestModuloNoDependeDeHistorico:
    """Verificación estructural: ninguna función pública del módulo
    acepta una secuencia de resultados -es estructuralmente imposible
    que probabilidad.py use datos históricos."""

    def test_ninguna_funcion_publica_acepta_resultados_o_secuencias(self):
        funciones_publicas = [
            probabilidad_seleccion_individual,
            probabilidad_combinacion_exacta_sin_repeticion,
            probabilidad_combinacion_exacta_desde_espacio_muestral,
        ]
        for fn in funciones_publicas:
            for nombre_param in inspect.signature(fn).parameters:
                assert "resultado" not in nombre_param.lower()
                assert "historic" not in nombre_param.lower()

    def test_modulo_no_importa_tipos_de_resultados_historicos(self):
        codigo_fuente = inspect.getsource(probabilidad)
        assert "ResultadoNumerico" not in codigo_fuente
        assert "ResultadoColorLoto" not in codigo_fuente
