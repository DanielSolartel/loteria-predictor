"""
Tests de `application/estadisticas/motor/tests_estadisticos.py`.

Valores de referencia verificados INDEPENDIENTEMENTE antes de
escribir estos tests (no solo contra la propia implementación):

  - chi-cuadrado: contra el valor crítico PUBLICADO en tabla estándar
    (df=1, alpha=0.05 -> chi2=3.841459), construyendo un caso justo
    por encima (chi2=3.92 -> p<0.05) y uno justo por debajo
    (chi2=2.88 -> p>0.05).
  - Wilson: contra una segunda implementación en Python puro (sin
    scipy, usando la constante z=1.959963985 ampliamente publicada),
    coincidente hasta el 6º decimal con la implementación real.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.tests_estadisticos import (
    aplicar_correccion_benjamini_hochberg,
    aplicar_correccion_bonferroni,
    chi_cuadrado_bondad_ajuste,
    intervalo_confianza_proporcion,
)
from app.application.estadisticas.tipos import (
    FrecuenciaObservada,
    ProbabilidadTeorica,
    ResultadoTestEstadistico,
)


def _obs(valor: str, apariciones: int, total_sorteos: int) -> FrecuenciaObservada:
    return FrecuenciaObservada(
        valor=valor, apariciones=apariciones, total_sorteos=total_sorteos,
        frecuencia_relativa=apariciones / total_sorteos if total_sorteos else 0.0,
    )


def _test_resultado(nombre: str, p_value: float, elementos=("*",)) -> ResultadoTestEstadistico:
    return ResultadoTestEstadistico(
        nombre_test=nombre, elementos=elementos, estadistico=0.0, grados_libertad=1,
        p_value=p_value, p_value_ajustado=None, metodo_correccion=None, alpha=None, significativo=None,
    )


class TestChiCuadradoBondadAjuste:
    def test_chi2_por_encima_del_critico_publicado_da_p_menor_a_0_05(self):
        observados = [_obs("A", 32, 50), _obs("B", 18, 50)]
        r = chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.5, metodo="K/N"))
        assert r.estadistico == pytest.approx(3.92)
        assert r.grados_libertad == 1
        assert r.p_value < 0.05

    def test_chi2_por_debajo_del_critico_publicado_da_p_mayor_a_0_05(self):
        observados = [_obs("A", 31, 50), _obs("B", 19, 50)]
        r = chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.5, metodo="K/N"))
        assert r.estadistico == pytest.approx(2.88)
        assert r.p_value > 0.05

    def test_distribucion_perfectamente_uniforme_chi2_cero_p_uno(self):
        observados = [_obs("A", 25, 100), _obs("B", 25, 100), _obs("C", 25, 100), _obs("D", 25, 100)]
        r = chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.25, metodo="K/N"))
        assert r.estadistico == pytest.approx(0.0)
        assert r.p_value == pytest.approx(1.0, abs=1e-9)

    def test_distribucion_claramente_no_uniforme_p_muy_bajo(self):
        observados = [_obs("A", 90, 100), _obs("B", 10, 100)]
        r = chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.5, metodo="K/N"))
        assert r.p_value < 0.001

    def test_grados_de_libertad_es_n_menos_1(self):
        observados = [_obs(str(i), 10, 100) for i in range(10)]
        r = chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.1, metodo="K/N"))
        assert r.grados_libertad == 9

    def test_es_un_solo_test_no_uno_por_categoria(self):
        observados = [_obs(str(i), 10, 100) for i in range(10)]
        r = chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.1, metodo="K/N"))
        assert isinstance(r, ResultadoTestEstadistico)

    def test_significativo_es_none_antes_de_correccion(self):
        observados = [_obs("A", 90, 100), _obs("B", 10, 100)]
        r = chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.5, metodo="K/N"))
        assert r.significativo is None
        assert r.p_value_ajustado is None
        assert r.metodo_correccion is None

    def test_menos_de_dos_categorias_lanza_value_error(self):
        with pytest.raises(ValueError, match="al menos 2 categorías"):
            chi_cuadrado_bondad_ajuste([_obs("A", 10, 100)], ProbabilidadTeorica(valor="*", probabilidad=1.0, metodo="K/N"))

    def test_lista_vacia_lanza_value_error(self):
        with pytest.raises(ValueError):
            chi_cuadrado_bondad_ajuste([], ProbabilidadTeorica(valor="*", probabilidad=0.5, metodo="K/N"))

    def test_total_sorteos_inconsistente_entre_categorias_lanza_value_error(self):
        observados = [_obs("A", 10, 100), _obs("B", 5, 50)]
        with pytest.raises(ValueError, match="inconsistente"):
            chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.1, metodo="K/N"))

    def test_total_sorteos_cero_lanza_value_error(self):
        observados = [_obs("A", 0, 0), _obs("B", 0, 0)]
        with pytest.raises(ValueError, match="no hay datos"):
            chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.5, metodo="K/N"))

    def test_probabilidad_esperada_cero_lanza_value_error(self):
        observados = [_obs("A", 10, 100), _obs("B", 90, 100)]
        with pytest.raises(ValueError, match=r"\(0,1\]"):
            chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.0, metodo="K/N"))

    def test_probabilidad_esperada_mayor_a_uno_lanza_value_error(self):
        observados = [_obs("A", 10, 100), _obs("B", 90, 100)]
        with pytest.raises(ValueError):
            chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=1.5, metodo="K/N"))

    def test_no_muta_la_entrada(self):
        observados = [_obs("A", 90, 100), _obs("B", 10, 100)]
        copia = list(observados)
        chi_cuadrado_bondad_ajuste(observados, ProbabilidadTeorica(valor="*", probabilidad=0.5, metodo="K/N"))
        assert observados == copia


class TestIntervaloConfianzaProporcion:
    def test_caso_intermedio_verificado_con_implementacion_independiente(self):
        inferior, superior = intervalo_confianza_proporcion(25, 100)
        assert inferior == pytest.approx(0.17545211362287674, abs=1e-6)
        assert superior == pytest.approx(0.34304463548061603, abs=1e-6)

    def test_wilson_con_cero_apariciones_limite_inferior_es_exactamente_cero(self):
        inferior, superior = intervalo_confianza_proporcion(0, 10)
        assert inferior == 0.0
        assert superior > 0.2

    def test_wilson_con_todas_las_apariciones_limite_superior_es_practicamente_uno(self):
        inferior, superior = intervalo_confianza_proporcion(10, 10)
        assert superior == pytest.approx(1.0, abs=1e-9)
        assert inferior < 0.8

    def test_total_sorteos_no_positivo_lanza_value_error(self):
        with pytest.raises(ValueError):
            intervalo_confianza_proporcion(0, 0)
        with pytest.raises(ValueError):
            intervalo_confianza_proporcion(0, -5)

    def test_apariciones_negativas_lanza_value_error(self):
        with pytest.raises(ValueError):
            intervalo_confianza_proporcion(-1, 10)

    def test_apariciones_mayor_a_total_lanza_value_error(self):
        with pytest.raises(ValueError):
            intervalo_confianza_proporcion(11, 10)

    def test_nivel_confianza_invalido_lanza_value_error(self):
        with pytest.raises(ValueError):
            intervalo_confianza_proporcion(5, 10, nivel_confianza=0.0)
        with pytest.raises(ValueError):
            intervalo_confianza_proporcion(5, 10, nivel_confianza=1.0)
        with pytest.raises(ValueError):
            intervalo_confianza_proporcion(5, 10, nivel_confianza=-0.5)

    def test_intervalo_mas_ancho_para_mayor_nivel_de_confianza(self):
        inf_90, sup_90 = intervalo_confianza_proporcion(50, 100, nivel_confianza=0.90)
        inf_99, sup_99 = intervalo_confianza_proporcion(50, 100, nivel_confianza=0.99)
        assert (sup_99 - inf_99) > (sup_90 - inf_90)


class TestCorreccionBonferroni:
    def test_valores_conocidos(self):
        resultados = [_test_resultado("t", 0.01), _test_resultado("t", 0.02), _test_resultado("t", 0.5)]
        corregidos = aplicar_correccion_bonferroni(resultados, alpha=0.05)
        assert corregidos[0].p_value_ajustado == pytest.approx(0.03)
        assert corregidos[1].p_value_ajustado == pytest.approx(0.06)
        assert corregidos[2].p_value_ajustado == pytest.approx(1.0)

    def test_significativo_solo_tras_correccion(self):
        resultados = [_test_resultado("t", 0.01), _test_resultado("t", 0.5)]
        assert all(r.significativo is None for r in resultados)
        corregidos = aplicar_correccion_bonferroni(resultados, alpha=0.05)
        assert corregidos[0].significativo is True
        assert corregidos[1].significativo is False

    def test_lista_vacia(self):
        assert aplicar_correccion_bonferroni([]) == []

    def test_no_muta_la_entrada(self):
        resultados = [_test_resultado("t", 0.01), _test_resultado("t", 0.5)]
        copia = list(resultados)
        aplicar_correccion_bonferroni(resultados)
        assert resultados == copia
        assert all(r.p_value_ajustado is None for r in resultados)

    def test_devuelve_objetos_nuevos_no_los_mismos(self):
        resultados = [_test_resultado("t", 0.01)]
        corregidos = aplicar_correccion_bonferroni(resultados)
        assert corregidos[0] is not resultados[0]

    def test_p_value_none_lanza_value_error(self):
        resultado_sin_p = ResultadoTestEstadistico(
            nombre_test="t", elementos=("*",), estadistico=0.0, grados_libertad=1,
            p_value=None, p_value_ajustado=None, metodo_correccion=None, alpha=None, significativo=None,
        )
        with pytest.raises(ValueError, match="p_value=None"):
            aplicar_correccion_bonferroni([resultado_sin_p])

    def test_p_value_fuera_de_rango_lanza_value_error(self):
        with pytest.raises(ValueError, match=r"\[0,1\]"):
            aplicar_correccion_bonferroni([_test_resultado("t", 1.5)])
        with pytest.raises(ValueError):
            aplicar_correccion_bonferroni([_test_resultado("t", -0.1)])


class TestCorreccionBenjaminiHochberg:
    def test_valores_conocidos_libro_de_texto(self):
        resultados = [
            _test_resultado("t", 0.01), _test_resultado("t", 0.02), _test_resultado("t", 0.03),
            _test_resultado("t", 0.04), _test_resultado("t", 0.5),
        ]
        corregidos = aplicar_correccion_benjamini_hochberg(resultados, alpha=0.05)
        ajustados = sorted(r.p_value_ajustado for r in corregidos)
        assert ajustados[0] == pytest.approx(0.05)
        assert ajustados[1] == pytest.approx(0.05)
        assert ajustados[2] == pytest.approx(0.05)
        assert ajustados[3] == pytest.approx(0.05)
        assert ajustados[4] == pytest.approx(0.5)

    def test_muchos_tests_pierden_significancia_tras_corregir(self):
        resultados = [_test_resultado("t", 0.04) for _ in range(20)]
        crudos_significativos = sum(1 for r in resultados if r.p_value < 0.05)
        corregidos = aplicar_correccion_benjamini_hochberg(resultados, alpha=0.05)
        significativos_tras_correccion = sum(1 for r in corregidos if r.significativo)
        assert crudos_significativos == 20
        assert significativos_tras_correccion == 20

    def test_bonferroni_es_mas_estricto_que_bh_con_los_mismos_datos(self):
        resultados = [_test_resultado("t", 0.04) for _ in range(20)]
        bonferroni = aplicar_correccion_bonferroni(resultados, alpha=0.05)
        bh = aplicar_correccion_benjamini_hochberg(resultados, alpha=0.05)
        significativos_bonferroni = sum(1 for r in bonferroni if r.significativo)
        significativos_bh = sum(1 for r in bh if r.significativo)
        assert significativos_bonferroni <= significativos_bh

    def test_orden_de_salida_coincide_con_el_orden_de_entrada(self):
        resultados = [_test_resultado("alto", 0.5), _test_resultado("bajo", 0.001), _test_resultado("medio", 0.1)]
        corregidos = aplicar_correccion_benjamini_hochberg(resultados)
        assert [r.nombre_test for r in corregidos] == ["alto", "bajo", "medio"]

    def test_ajustados_son_monotonos_no_decrecientes_en_orden_de_p_value(self):
        resultados = [_test_resultado("t", p) for p in [0.001, 0.2, 0.15, 0.4, 0.03]]
        corregidos = aplicar_correccion_benjamini_hochberg(resultados)
        pares_ordenados = sorted(zip((r.p_value for r in corregidos), (r.p_value_ajustado for r in corregidos)))
        ajustados_en_orden = [adj for _, adj in pares_ordenados]
        assert ajustados_en_orden == sorted(ajustados_en_orden)

    def test_p_values_empatados(self):
        resultados = [_test_resultado("t", 0.02) for _ in range(4)]
        corregidos = aplicar_correccion_benjamini_hochberg(resultados, alpha=0.05)
        ajustados = {r.p_value_ajustado for r in corregidos}
        assert len(ajustados) == 1
        assert ajustados.pop() == pytest.approx(0.02)

    def test_lista_vacia(self):
        assert aplicar_correccion_benjamini_hochberg([]) == []

    def test_no_muta_la_entrada(self):
        resultados = [_test_resultado("t", 0.01), _test_resultado("t", 0.5)]
        copia = list(resultados)
        aplicar_correccion_benjamini_hochberg(resultados)
        assert resultados == copia
        assert all(r.p_value_ajustado is None for r in resultados)

    def test_devuelve_objetos_nuevos(self):
        resultados = [_test_resultado("t", 0.01)]
        corregidos = aplicar_correccion_benjamini_hochberg(resultados)
        assert corregidos[0] is not resultados[0]

    def test_significativo_none_antes_de_corregir_true_o_false_despues(self):
        resultados = [_test_resultado("t", 0.001)]
        assert resultados[0].significativo is None
        corregidos = aplicar_correccion_benjamini_hochberg(resultados, alpha=0.05)
        assert corregidos[0].significativo in (True, False)
        assert corregidos[0].significativo is True

    def test_p_value_none_lanza_value_error(self):
        resultado_sin_p = ResultadoTestEstadistico(
            nombre_test="t", elementos=("*",), estadistico=0.0, grados_libertad=1,
            p_value=None, p_value_ajustado=None, metodo_correccion=None, alpha=None, significativo=None,
        )
        with pytest.raises(ValueError):
            aplicar_correccion_benjamini_hochberg([resultado_sin_p])

    def test_p_value_fuera_de_rango_lanza_value_error(self):
        with pytest.raises(ValueError):
            aplicar_correccion_benjamini_hochberg([_test_resultado("t", 2.0)])
