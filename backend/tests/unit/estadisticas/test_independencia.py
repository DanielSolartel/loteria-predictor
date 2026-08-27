"""
Tests de `application/estadisticas/motor/independencia.py`.

Dataset de referencia (rango 1-6, K=3, universo chico a propósito
para poder cubrir C(6,2)=15 pares y C(6,3)=20 tríos por completo y
verificar todo a mano):

    S1: 1, 2, 3
    S2: 1, 2, 4
    S3: 1, 2, 5

El par (1,2) coocurre en los 3 sorteos -soporte=3, el máximo posible
con total_sorteos=3. El par (5,6) nunca coocurre -soporte=0, y debe
seguir apareciendo en el resultado (universo completo).

Valores de referencia verificados INDEPENDIENTEMENTE antes de
escribir estos tests (ver sesión de verificación previa):
  - probabilidad teórica de pareja/trío: contra la fórmula alternativa
    C(N-t,K-t)/C(N,K) vía math.comb (misma que usa coocurrencia.py).
  - un p-value binomial exacto: contra una suma directa de la función
    de masa binomial (math.comb, sin usar scipy para la verificación).
"""
from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from scipy.stats import binomtest

from app.application.estadisticas.motor.coocurrencia import (
    _contar_coocurrencias_crudo,
    calcular_coocurrencia_pares,
    calcular_coocurrencia_trios,
)
from app.application.estadisticas.motor.independencia import (
    calcular_independencia_pares,
    calcular_independencia_trios,
)
from app.application.estadisticas.tipos import ResultadoNumerico, ResultadoTestEstadistico

_FECHA_BASE = date(2024, 1, 1)


def _num(numero_sorteo: int, numeros: tuple[int, ...]) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=None,
    )


_DATASET = [
    _num(1, (1, 2, 3)),
    _num(2, (1, 2, 4)),
    _num(3, (1, 2, 5)),
]


def _por_elementos(filas: list[ResultadoTestEstadistico]) -> dict[tuple[str, ...], ResultadoTestEstadistico]:
    return {f.elementos: f for f in filas}


class TestUniversoCompletoPares:
    def test_cantidad_de_resultados_es_exactamente_c_n_2(self):
        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        assert len(filas) == math.comb(6, 2) == 15

    def test_combinacion_nunca_observada_aparece_con_soporte_cero(self):
        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        por_elem = _por_elementos(filas)
        assert ("5", "6") in por_elem
        assert por_elem[("5", "6")].estadistico == 0.0

    def test_par_con_soporte_igual_al_total_de_sorteos(self):
        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        por_elem = _por_elementos(filas)
        assert por_elem[("1", "2")].estadistico == 3.0

    def test_probabilidad_teorica_correcta_para_pares(self):
        n, k = 6, 3
        p_esperada = (k * (k - 1)) / (n * (n - 1))
        p_alternativa = math.comb(n - 2, k - 2) / math.comb(n, k)
        assert p_esperada == pytest.approx(p_alternativa)
        assert p_esperada == pytest.approx(0.2)

        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        p_value_esperado = binomtest(3, 3, 0.2, alternative="two-sided").pvalue
        assert _por_elementos(filas)[("1", "2")].p_value == pytest.approx(p_value_esperado)

    def test_verificacion_independiente_del_p_value_sin_usar_scipy_como_referencia(self):
        def p_value_manual(k_obs, n_trials, p):
            pmf = lambda x: math.comb(n_trials, x) * (p**x) * ((1 - p) ** (n_trials - x))
            p_k = pmf(k_obs)
            return sum(pmf(x) for x in range(n_trials + 1) if pmf(x) <= p_k * (1 + 1e-9))

        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        fila_1_2 = _por_elementos(filas)[("1", "2")]
        manual = p_value_manual(3, 3, 0.2)
        assert fila_1_2.p_value == pytest.approx(manual, abs=1e-9)

    def test_test_bilateral(self):
        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        fila = _por_elementos(filas)[("1", "2")]
        esperado_bilateral = binomtest(3, 3, 0.2, alternative="two-sided").pvalue
        assert fila.p_value == pytest.approx(esperado_bilateral)

        esperado_bilateral_5 = binomtest(0, 3, 0.2, alternative="two-sided").pvalue
        fila_5_6 = _por_elementos(filas)[("5", "6")]
        assert fila_5_6.p_value == pytest.approx(esperado_bilateral_5)

    def test_grados_libertad_none(self):
        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        assert all(f.grados_libertad is None for f in filas)

    def test_sin_significancia_antes_de_correccion(self):
        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        assert all(f.significativo is None for f in filas)
        assert all(f.p_value_ajustado is None for f in filas)
        assert all(f.metodo_correccion is None for f in filas)
        assert all(f.alpha is None for f in filas)

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET[2], _DATASET[0], _DATASET[1]]
        f1 = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        f2 = calcular_independencia_pares(desordenado, rango_min=1, rango_max=6, cantidad_numeros=3)
        assert sorted(f1, key=lambda f: f.elementos) == sorted(f2, key=lambda f: f.elementos)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        assert _DATASET == copia

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset_invalido = [_num(1, (1, 2, 99))]
        with pytest.raises(ValueError, match="99"):
            calcular_independencia_pares(dataset_invalido, rango_min=1, rango_max=6, cantidad_numeros=3)

    def test_cero_sorteos_lanza_value_error(self):
        with pytest.raises(ValueError, match="no hay sorteos"):
            calcular_independencia_pares([], rango_min=1, rango_max=6, cantidad_numeros=3)

    def test_cantidad_numeros_menor_a_dos_lanza_value_error(self):
        with pytest.raises(ValueError, match=">= 2"):
            calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=1)

    def test_rango_invertido_lanza_value_error(self):
        with pytest.raises(ValueError, match="rango_max"):
            calcular_independencia_pares(_DATASET, rango_min=10, rango_max=1, cantidad_numeros=3)


class TestUniversoCompletoTrios:
    def test_cantidad_de_resultados_es_exactamente_c_n_3(self):
        filas = calcular_independencia_trios(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        assert len(filas) == math.comb(6, 3) == 20

    def test_trio_observado_y_no_observado(self):
        filas = calcular_independencia_trios(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        por_elem = _por_elementos(filas)
        assert por_elem[("1", "2", "3")].estadistico == 1.0
        assert por_elem[("4", "5", "6")].estadistico == 0.0

    def test_probabilidad_teorica_correcta_para_trios(self):
        n, k = 6, 3
        p_esperada = (k * (k - 1) * (k - 2)) / (n * (n - 1) * (n - 2))
        p_alternativa = math.comb(n - 3, k - 3) / math.comb(n, k)
        assert p_esperada == pytest.approx(p_alternativa)
        assert p_esperada == pytest.approx(0.05)

        filas = calcular_independencia_trios(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        p_value_esperado = binomtest(1, 3, 0.05, alternative="two-sided").pvalue
        assert _por_elementos(filas)[("1", "2", "3")].p_value == pytest.approx(p_value_esperado)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_independencia_trios(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        assert _DATASET == copia

    def test_cantidad_numeros_menor_a_tres_lanza_value_error(self):
        with pytest.raises(ValueError, match=">= 3"):
            calcular_independencia_trios(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=2)

    def test_cero_sorteos_lanza_value_error(self):
        with pytest.raises(ValueError):
            calcular_independencia_trios([], rango_min=1, rango_max=6, cantidad_numeros=3)


class TestCorteTemporalYAntiFuga:
    def test_corte_temporal_excluye_sorteos_posteriores(self):
        filas = calcular_independencia_pares(
            _DATASET, rango_min=1, rango_max=6, cantidad_numeros=3, hasta_numero_sorteo=2,
        )
        por_elem = _por_elementos(filas)
        assert por_elem[("1", "2")].estadistico == 2.0

    def test_propiedad_anti_fuga(self):
        resultado_n = calcular_independencia_pares(
            _DATASET, rango_min=1, rango_max=6, cantidad_numeros=3, hasta_numero_sorteo=2,
        )
        ampliado = _DATASET + [_num(4, (1, 2, 6))]
        resultado_n_ampliado = calcular_independencia_pares(
            ampliado, rango_min=1, rango_max=6, cantidad_numeros=3, hasta_numero_sorteo=2,
        )
        assert sorted(resultado_n, key=lambda f: f.elementos) == sorted(resultado_n_ampliado, key=lambda f: f.elementos)


class TestHelperExtraidoDeCoocurrencia:
    def test_contar_coocurrencias_crudo_es_reutilizado_correctamente(self):
        listas = [list(r.numeros) for r in _DATASET]
        crudo = _contar_coocurrencias_crudo(listas, 2)
        assert crudo[(1, 2)] == 3
        assert (5, 6) not in crudo

    def test_coocurrencia_py_sigue_reportando_solo_lo_observado_tras_la_extraccion(self):
        filas_descriptivas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        elementos_descriptivos = {f.elementos for f in filas_descriptivas}
        assert ("5", "6") not in elementos_descriptivos
        assert len(filas_descriptivas) < math.comb(6, 2)

    def test_coocurrencia_py_trios_sigue_igual(self):
        filas_descriptivas = calcular_coocurrencia_trios(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        elementos_descriptivos = {f.elementos for f in filas_descriptivas}
        assert ("4", "5", "6") not in elementos_descriptivos
        assert len(filas_descriptivas) < math.comb(6, 3)


class TestIntegracionConCorrecciones:
    def test_pipeline_completo_independencia_a_correccion(self):
        from app.application.estadisticas.motor.tests_estadisticos import aplicar_correccion_benjamini_hochberg

        filas = calcular_independencia_pares(_DATASET, rango_min=1, rango_max=6, cantidad_numeros=3)
        assert all(f.significativo is None for f in filas)

        corregidas = aplicar_correccion_benjamini_hochberg(filas, alpha=0.05)
        assert len(corregidas) == len(filas)
        assert all(f.significativo in (True, False) for f in corregidas)
        assert all(f.metodo_correccion == "benjamini_hochberg" for f in corregidas)
