"""
Tests de `application/estadisticas/motor/frecuencia.py`.

Dataset armado a mano para MiLoto-like (rango 1-5, K=3, elegido chico
a propósito para que los conteos sean verificables por inspección) y
para ColorLoto-like (rango 1-3, 3 colores, con repetición dentro del
sorteo).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.frecuencia import (
    calcular_frecuencia_colores,
    calcular_frecuencia_numeros,
    calcular_frecuencia_numeros_colorloto,
    calcular_frecuencia_pares_numero_color,
    calcular_frecuencia_superbalota,
    construir_tabla_frecuencia,
    frecuencia_a_feature,
    frecuencia_relativa_esperada,
)
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico


def _num(numero_sorteo: int, numeros: tuple[int, ...], superbalota: int | None = None) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=date(2024, 1, numero_sorteo), dia_semana="lunes",
        numeros=numeros, superbalota=superbalota,
    )


def _cl(numero_sorteo: int, pares: tuple[tuple[int, str], ...]) -> ResultadoColorLoto:
    return ResultadoColorLoto(
        numero_sorteo=numero_sorteo, fecha=date(2024, 1, numero_sorteo), dia_semana="lunes", pares=pares,
    )


_DATASET_NUMERICO = [
    _num(1, (1, 2, 3), superbalota=10),
    _num(2, (1, 3, 5), superbalota=10),
    _num(3, (2, 4, 5), superbalota=None),
]

_DATASET_COLORLOTO = [
    _cl(1, ((1, "ROJO"), (1, "ROJO"), (2, "AZUL"))),
    _cl(2, ((3, "VERDE"), (2, "AZUL"), (1, "ROJO"))),
]


class TestFrecuenciaRelativaEsperada:
    def test_caso_clasico_miloto(self):
        assert frecuencia_relativa_esperada(5, 39) == pytest.approx(5 / 39)

    def test_caso_colorloto_colores_k_igual_n_da_uno(self):
        assert frecuencia_relativa_esperada(6, 6) == 1.0

    def test_n_cero_lanza_value_error(self):
        with pytest.raises(ValueError):
            frecuencia_relativa_esperada(1, 0)

    def test_n_negativo_lanza_value_error(self):
        with pytest.raises(ValueError):
            frecuencia_relativa_esperada(1, -5)


class TestConstruirTablaFrecuencia:
    def test_unico_esperado_para_todo_el_pool_y_diferencia_con_signo_correcto(self):
        frecuencias = [
            FrecuenciaObservada(valor="1", apariciones=8, total_sorteos=10, frecuencia_relativa=0.8),
            FrecuenciaObservada(valor="2", apariciones=1, total_sorteos=10, frecuencia_relativa=0.1),
        ]
        filas = construir_tabla_frecuencia(frecuencias, k=1, n=5)
        esperada = 1 / 5

        fila_1 = next(f for f in filas if f.valor == "1")
        fila_2 = next(f for f in filas if f.valor == "2")

        assert fila_1.probabilidad_teorica.probabilidad == esperada
        assert fila_1.diferencia == pytest.approx(0.8 - esperada)
        assert fila_2.diferencia == pytest.approx(0.1 - esperada)

    def test_frecuencia_observada_y_probabilidad_teorica_quedan_separadas(self):
        frecuencias = [FrecuenciaObservada(valor="1", apariciones=5, total_sorteos=10, frecuencia_relativa=0.5)]
        fila = construir_tabla_frecuencia(frecuencias, k=1, n=5)[0]
        assert isinstance(fila.frecuencia_observada, FrecuenciaObservada)
        assert fila.frecuencia_observada.apariciones == 5
        assert fila.probabilidad_teorica.metodo == "K/N = 1/5"

    def test_lista_vacia(self):
        assert construir_tabla_frecuencia([], k=1, n=5) == []


class TestCalcularFrecuenciaNumeros:
    def test_conteo_exacto_e_incluye_numeros_nunca_aparecidos(self):
        filas = calcular_frecuencia_numeros(_DATASET_NUMERICO, rango_min=1, rango_max=5)
        por_valor = {f.valor: f.apariciones for f in filas}
        assert por_valor == {"1": 2, "2": 2, "3": 2, "4": 1, "5": 2}

    def test_incluye_los_5_numeros_del_rango_aunque_falte_alguno(self):
        dataset = [_num(1, (1, 2, 3)), _num(2, (1, 2, 4))]
        filas = calcular_frecuencia_numeros(dataset, rango_min=1, rango_max=5)
        assert len(filas) == 5
        fila_5 = next(f for f in filas if f.valor == "5")
        assert fila_5.apariciones == 0
        assert fila_5.frecuencia_relativa == 0.0

    def test_lista_vacia_no_divide_por_cero(self):
        filas = calcular_frecuencia_numeros([], rango_min=1, rango_max=5)
        assert len(filas) == 5
        assert all(f.apariciones == 0 and f.frecuencia_relativa == 0.0 for f in filas)

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_num(1, (1, 2, 99))]
        with pytest.raises(ValueError, match="fuera del rango"):
            calcular_frecuencia_numeros(dataset, rango_min=1, rango_max=5)

    def test_nunca_incluye_la_superbalota_en_el_conteo(self):
        filas = calcular_frecuencia_numeros(_DATASET_NUMERICO, rango_min=1, rango_max=5)
        assert sum(f.apariciones for f in filas) == 3 * 3


class TestCalcularFrecuenciaSuperbalota:
    def test_pool_independiente_del_principal(self):
        filas = calcular_frecuencia_superbalota(_DATASET_NUMERICO, rango_min=1, rango_max=16)
        fila_10 = next(f for f in filas if f.valor == "10")
        assert fila_10.apariciones == 2

    def test_superbalota_ausente_no_cuenta_como_cero_ni_rompe(self):
        filas = calcular_frecuencia_superbalota(_DATASET_NUMERICO, rango_min=1, rango_max=16)
        assert filas[0].total_sorteos == 2

    def test_lista_vacia(self):
        filas = calcular_frecuencia_superbalota([], rango_min=1, rango_max=16)
        assert all(f.apariciones == 0 for f in filas)

    def test_todas_las_superbalotas_ausentes_no_divide_por_cero(self):
        dataset = [_num(1, (1, 2, 3), superbalota=None)]
        filas = calcular_frecuencia_superbalota(dataset, rango_min=1, rango_max=16)
        assert all(f.total_sorteos == 0 and f.frecuencia_relativa == 0.0 for f in filas)


class TestCalcularFrecuenciaNumerosColorLoto:
    def test_respeta_multiplicidad_numero_repetido_en_el_mismo_sorteo_cuenta_dos_veces(self):
        filas = calcular_frecuencia_numeros_colorloto(_DATASET_COLORLOTO, rango_min=1, rango_max=3)
        fila_1 = next(f for f in filas if f.valor == "1")
        assert fila_1.apariciones == 3

    def test_frecuencia_relativa_puede_superar_1_por_repeticion(self):
        filas = calcular_frecuencia_numeros_colorloto(_DATASET_COLORLOTO, rango_min=1, rango_max=3)
        fila_1 = next(f for f in filas if f.valor == "1")
        assert fila_1.frecuencia_relativa == 3 / 2

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_cl(1, ((9, "ROJO"),))]
        with pytest.raises(ValueError, match="fuera del rango"):
            calcular_frecuencia_numeros_colorloto(dataset, rango_min=1, rango_max=7)

    def test_lista_vacia(self):
        filas = calcular_frecuencia_numeros_colorloto([], rango_min=1, rango_max=3)
        assert all(f.apariciones == 0 for f in filas)


class TestCalcularFrecuenciaColores:
    def test_conteo_exacto_ignorando_el_numero(self):
        filas = calcular_frecuencia_colores(_DATASET_COLORLOTO, colores_vigentes=["ROJO", "AZUL", "VERDE"])
        por_valor = {f.valor: f.apariciones for f in filas}
        assert por_valor == {"ROJO": 3, "AZUL": 2, "VERDE": 1}

    def test_color_observado_pero_no_vigente_no_se_pierde(self):
        dataset = [_cl(1, ((1, "MORADO"),))]
        filas = calcular_frecuencia_colores(dataset, colores_vigentes=["ROJO", "AZUL"])
        valores = {f.valor for f in filas}
        assert "MORADO" in valores

    def test_color_vigente_sin_apariciones_queda_en_cero(self):
        dataset = [_cl(1, ((1, "ROJO"),))]
        filas = calcular_frecuencia_colores(dataset, colores_vigentes=["ROJO", "AZUL"])
        fila_azul = next(f for f in filas if f.valor == "AZUL")
        assert fila_azul.apariciones == 0

    def test_lista_vacia_no_divide_por_cero(self):
        filas = calcular_frecuencia_colores([], colores_vigentes=["ROJO"])
        assert filas[0].apariciones == 0 and filas[0].frecuencia_relativa == 0.0


class TestCalcularFrecuenciaParesNumeroColor:
    def test_el_par_es_la_unidad_atomica(self):
        filas = calcular_frecuencia_pares_numero_color(
            _DATASET_COLORLOTO, rango_min=1, rango_max=3, colores_vigentes=["ROJO", "AZUL", "VERDE"],
        )
        fila_1_rojo = next(f for f in filas if f.valor == "1-ROJO")
        assert fila_1_rojo.apariciones == 3

    def test_formato_del_valor_es_numero_guion_color(self):
        filas = calcular_frecuencia_pares_numero_color(
            _DATASET_COLORLOTO, rango_min=1, rango_max=3, colores_vigentes=["ROJO", "AZUL", "VERDE"],
        )
        assert any(f.valor == "2-AZUL" for f in filas)

    def test_par_nunca_observado_aparece_con_cero(self):
        filas = calcular_frecuencia_pares_numero_color(
            _DATASET_COLORLOTO, rango_min=1, rango_max=3, colores_vigentes=["ROJO", "AZUL", "VERDE"],
        )
        fila_3_rojo = next(f for f in filas if f.valor == "3-ROJO")
        assert fila_3_rojo.apariciones == 0

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_cl(1, ((9, "ROJO"),))]
        with pytest.raises(ValueError, match="fuera del rango"):
            calcular_frecuencia_pares_numero_color(dataset, rango_min=1, rango_max=7, colores_vigentes=["ROJO"])

    def test_lista_vacia(self):
        filas = calcular_frecuencia_pares_numero_color([], rango_min=1, rango_max=3, colores_vigentes=["ROJO"])
        assert all(f.apariciones == 0 for f in filas)


class TestFrecuenciaAFeature:
    def test_conserva_exactamente_el_corte_temporal_recibido(self):
        f = FrecuenciaObservada(valor="17", apariciones=5, total_sorteos=10, frecuencia_relativa=0.5)
        feature = frecuencia_a_feature(f, calculado_hasta_sorteo=583, ventana="ultimos_50")
        assert feature.calculado_hasta_sorteo == 583
        assert feature.ventana == "ultimos_50"
        assert feature.nombre == "17"
        assert feature.valor == 0.5

    def test_ventana_por_defecto_es_historico_completo(self):
        f = FrecuenciaObservada(valor="17", apariciones=5, total_sorteos=10, frecuencia_relativa=0.5)
        feature = frecuencia_a_feature(f, calculado_hasta_sorteo=100)
        assert feature.ventana == "historico_completo"
