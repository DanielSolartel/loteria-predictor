"""
Tests de `application/estadisticas/motor/distribuciones.py`.

Dataset numérico de referencia (rango 1-20, K=4, elegido chico para
verificar todo a mano):

    S1: 2, 4, 6, 8      -> 4 pares, suma=20
    S2: 1, 3, 5, 7      -> 0 pares, suma=16
    S3: 2, 4, 11, 13    -> 2 pares, suma=30
    S4: 1, 12, 14, 16   -> 3 pares, suma=43
"""
from __future__ import annotations

import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.distribuciones import (
    DistribucionSumas,
    calcular_distribucion_altos_bajos,
    calcular_distribucion_altos_bajos_colorloto,
    calcular_distribucion_conteo_color,
    calcular_distribucion_decenas,
    calcular_distribucion_pares_impares,
    calcular_distribucion_pares_impares_colorloto,
    calcular_distribucion_sumas,
    calcular_distribucion_sumas_colorloto,
    calcular_maximo_repeticion_color_por_sorteo,
    distribucion_sumas_a_features,
)
from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico

_FECHA_BASE = date(2024, 1, 1)


def _num(numero_sorteo: int, numeros: tuple[int, ...]) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=None,
    )


def _cl(numero_sorteo: int, pares: tuple[tuple[int, str], ...]) -> ResultadoColorLoto:
    return ResultadoColorLoto(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", pares=pares,
    )


_DATASET = [
    _num(1, (2, 4, 6, 8)),
    _num(2, (1, 3, 5, 7)),
    _num(3, (2, 4, 11, 13)),
    _num(4, (1, 12, 14, 16)),
]


def _por_valor(filas: list[FrecuenciaObservada]) -> dict[str, FrecuenciaObservada]:
    return {f.valor: f for f in filas}


class TestCalcularDistribucionParesImpares:
    def test_conteo_exacto_por_sorteo(self):
        filas = calcular_distribucion_pares_impares(_DATASET, cantidad_numeros=4)
        por_valor = _por_valor(filas)
        assert por_valor["4"].apariciones == 1
        assert por_valor["0"].apariciones == 1
        assert por_valor["2"].apariciones == 1
        assert por_valor["3"].apariciones == 1
        assert por_valor["1"].apariciones == 0

    def test_incluye_todo_el_universo_0_a_k(self):
        filas = calcular_distribucion_pares_impares(_DATASET, cantidad_numeros=4)
        assert {f.valor for f in filas} == {"0", "1", "2", "3", "4"}

    def test_total_sorteos_correcto(self):
        filas = calcular_distribucion_pares_impares(_DATASET, cantidad_numeros=4)
        assert all(f.total_sorteos == 4 for f in filas)

    def test_cero_sorteos_no_divide_por_cero(self):
        filas = calcular_distribucion_pares_impares([], cantidad_numeros=5)
        assert len(filas) == 6
        assert all(f.apariciones == 0 and f.frecuencia_relativa == 0.0 for f in filas)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_distribucion_pares_impares(_DATASET, cantidad_numeros=4)
        assert _DATASET == copia

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET[2], _DATASET[0], _DATASET[3], _DATASET[1]]
        f1 = calcular_distribucion_pares_impares(_DATASET, cantidad_numeros=4)
        f2 = calcular_distribucion_pares_impares(desordenado, cantidad_numeros=4)
        assert f1 == f2


class TestCalcularDistribucionAltosBajos:
    def test_punto_de_corte_para_rango_1_20(self):
        filas = calcular_distribucion_altos_bajos(_DATASET, rango_min=1, rango_max=20, cantidad_numeros=4)
        por_valor = _por_valor(filas)
        assert por_valor["4"].apariciones == 2
        assert por_valor["2"].apariciones == 1
        assert por_valor["1"].apariciones == 1

    def test_incluye_todo_el_universo(self):
        filas = calcular_distribucion_altos_bajos(_DATASET, rango_min=1, rango_max=20, cantidad_numeros=4)
        assert {f.valor for f in filas} == {"0", "1", "2", "3", "4"}

    def test_miloto_corte_correcto(self):
        dataset = [_num(1, (19, 20, 21, 22, 39))]
        filas = calcular_distribucion_altos_bajos(dataset, rango_min=1, rango_max=39, cantidad_numeros=5)
        assert _por_valor(filas)["1"].apariciones == 1

    def test_cero_sorteos(self):
        filas = calcular_distribucion_altos_bajos([], rango_min=1, rango_max=39, cantidad_numeros=5)
        assert all(f.apariciones == 0 for f in filas)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_distribucion_altos_bajos(_DATASET, rango_min=1, rango_max=20, cantidad_numeros=4)
        assert _DATASET == copia


class TestCalcularDistribucionSumas:
    def test_estadisticos_exactos_sobre_el_dataset_de_referencia(self):
        d = calcular_distribucion_sumas(_DATASET)
        sumas_esperadas = [20, 16, 30, 43]

        assert d.total_sorteos == 4
        assert d.minimo == 16
        assert d.maximo == 43
        assert d.media == pytest.approx(statistics.mean(sumas_esperadas))
        assert d.mediana == pytest.approx(statistics.median(sumas_esperadas))
        assert d.desviacion_estandar == pytest.approx(statistics.pstdev(sumas_esperadas))

    def test_usa_desviacion_estandar_poblacional_no_muestral(self):
        sumas_esperadas = [20, 16, 30, 43]
        d = calcular_distribucion_sumas(_DATASET)
        assert d.desviacion_estandar == pytest.approx(statistics.pstdev(sumas_esperadas))
        assert d.desviacion_estandar != pytest.approx(statistics.stdev(sumas_esperadas))

    def test_percentiles_p10_p25_p50_p75_p90_presentes(self):
        d = calcular_distribucion_sumas(_DATASET)
        assert set(d.percentiles.keys()) == {10, 25, 50, 75, 90}

    def test_percentil_50_coincide_aproximadamente_con_la_mediana(self):
        d = calcular_distribucion_sumas(_DATASET)
        assert d.percentiles[50] == pytest.approx(d.mediana, rel=0.15)

    def test_cero_sorteos_sin_dividir_por_cero(self):
        d = calcular_distribucion_sumas([])
        assert d.total_sorteos == 0
        assert d.minimo is None
        assert d.maximo is None
        assert d.media == 0.0
        assert d.percentiles == {}

    def test_un_solo_sorteo_percentiles_triviales(self):
        d = calcular_distribucion_sumas([_num(1, (1, 2, 3, 4))])
        assert d.total_sorteos == 1
        assert d.minimo == d.maximo == 10
        assert d.media == 10.0
        assert d.mediana == 10.0
        assert d.desviacion_estandar == 0.0
        assert all(v == 10.0 for v in d.percentiles.values())

    def test_no_incluye_la_superbalota_en_la_suma(self):
        dataset_con_sb = [ResultadoNumerico(
            numero_sorteo=1, fecha=_FECHA_BASE, dia_semana="lunes",
            numeros=(1, 2, 3), superbalota=99,
        )]
        d = calcular_distribucion_sumas(dataset_con_sb)
        assert d.minimo == 6

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_distribucion_sumas(_DATASET)
        assert _DATASET == copia


class TestCalcularDistribucionDecenas:
    def test_apariciones_se_suma_correctamente_entre_numeros_de_la_misma_franja(self):
        filas = calcular_distribucion_decenas(_DATASET, rango_min=1, rango_max=20)
        por_valor = _por_valor(filas)
        assert por_valor["1-10"].apariciones == 11

    def test_total_sorteos_no_se_suma_entre_filas_individuales(self):
        filas = calcular_distribucion_decenas(_DATASET, rango_min=1, rango_max=20)
        assert all(f.total_sorteos == 4 for f in filas)
        assert all(f.total_sorteos != 4 * 10 for f in filas)

    def test_frecuencia_relativa_recalculada_no_sumada(self):
        filas = calcular_distribucion_decenas(_DATASET, rango_min=1, rango_max=20)
        fila_1_10 = _por_valor(filas)["1-10"]
        assert fila_1_10.frecuencia_relativa == pytest.approx(11 / 4)

    def test_franjas_correctas_para_rango_no_multiplo_de_10(self):
        filas = calcular_distribucion_decenas([], rango_min=1, rango_max=39)
        valores = [f.valor for f in filas]
        assert valores == ["1-10", "11-20", "21-30", "31-39"]

    def test_coincide_con_agrupar_manualmente_calcular_frecuencia_numeros(self):
        frecuencias_individuales = calcular_frecuencia_numeros(_DATASET, rango_min=1, rango_max=20)
        total_individual = sum(f.apariciones for f in frecuencias_individuales)

        filas_decenas = calcular_distribucion_decenas(_DATASET, rango_min=1, rango_max=20)
        total_decenas = sum(f.apariciones for f in filas_decenas)

        assert total_decenas == total_individual == 16

    def test_cero_sorteos_no_divide_por_cero(self):
        filas = calcular_distribucion_decenas([], rango_min=1, rango_max=20)
        assert all(f.apariciones == 0 and f.frecuencia_relativa == 0.0 for f in filas)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_distribucion_decenas(_DATASET, rango_min=1, rango_max=20)
        assert _DATASET == copia


class TestColorLoto:
    _DATASET_CL = [
        _cl(1, ((2, "ROJO"), (4, "AZUL"), (6, "VERDE"), (1, "ROJO"), (3, "AZUL"), (7, "VERDE"))),
        _cl(2, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
    ]

    def test_pares_impares_colorloto_ignora_el_color(self):
        filas = calcular_distribucion_pares_impares_colorloto(self._DATASET_CL, cantidad_balotas=6)
        assert _por_valor(filas)["3"].apariciones == 2

    def test_pares_impares_colorloto_respeta_repeticion(self):
        filas = calcular_distribucion_pares_impares_colorloto(self._DATASET_CL, cantidad_balotas=6)
        assert sum(f.apariciones for f in filas) == 2

    def test_altos_bajos_colorloto(self):
        filas = calcular_distribucion_altos_bajos_colorloto(
            self._DATASET_CL, rango_min=1, rango_max=7, cantidad_balotas=6,
        )
        assert _por_valor(filas)["3"].apariciones == 2

    def test_sumas_colorloto_ignora_color_y_respeta_repeticion(self):
        d = calcular_distribucion_sumas_colorloto(self._DATASET_CL)
        assert d.minimo == 21
        assert d.maximo == 23
        assert d.total_sorteos == 2

    def test_no_muta_la_entrada_colorloto(self):
        copia = list(self._DATASET_CL)
        calcular_distribucion_pares_impares_colorloto(self._DATASET_CL, cantidad_balotas=6)
        calcular_distribucion_sumas_colorloto(self._DATASET_CL)
        assert self._DATASET_CL == copia


class TestPropiedadAntiFuga:
    def test_anti_fuga_pares_impares(self):
        r_n = calcular_distribucion_pares_impares(_DATASET, cantidad_numeros=4, hasta_numero_sorteo=2)
        ampliado = _DATASET + [_num(5, (1, 2, 3, 4)), _num(6, (5, 6, 7, 8))]
        r_amp = calcular_distribucion_pares_impares(ampliado, cantidad_numeros=4, hasta_numero_sorteo=2)
        assert r_n == r_amp

    def test_anti_fuga_altos_bajos(self):
        r_n = calcular_distribucion_altos_bajos(
            _DATASET, rango_min=1, rango_max=20, cantidad_numeros=4, hasta_numero_sorteo=2,
        )
        ampliado = _DATASET + [_num(5, (1, 2, 3, 4))]
        r_amp = calcular_distribucion_altos_bajos(
            ampliado, rango_min=1, rango_max=20, cantidad_numeros=4, hasta_numero_sorteo=2,
        )
        assert r_n == r_amp

    def test_anti_fuga_sumas(self):
        r_n = calcular_distribucion_sumas(_DATASET, hasta_numero_sorteo=2)
        ampliado = _DATASET + [_num(5, (1, 2, 3, 4))]
        r_amp = calcular_distribucion_sumas(ampliado, hasta_numero_sorteo=2)
        assert r_n == r_amp

    def test_anti_fuga_decenas(self):
        r_n = calcular_distribucion_decenas(_DATASET, rango_min=1, rango_max=20, hasta_numero_sorteo=2)
        ampliado = _DATASET + [_num(5, (1, 2, 3, 4))]
        r_amp = calcular_distribucion_decenas(ampliado, rango_min=1, rango_max=20, hasta_numero_sorteo=2)
        assert r_n == r_amp


class TestValoresFueraDeRango:
    def test_altos_bajos_no_revienta_con_datos_atipicos(self):
        dataset_raro = [_num(1, (999,))]
        filas = calcular_distribucion_altos_bajos(dataset_raro, rango_min=1, rango_max=20, cantidad_numeros=1)
        assert sum(f.apariciones for f in filas) == 1

    def test_decenas_valida_rango_via_calcular_frecuencia_numeros(self):
        dataset_invalido = [_num(1, (999,))]
        with pytest.raises(ValueError, match="fuera del rango"):
            calcular_distribucion_decenas(dataset_invalido, rango_min=1, rango_max=20)


class TestDistribucionSumasAFeatures:
    def test_desempaqueta_media_mediana_desviacion_y_percentiles(self):
        d = calcular_distribucion_sumas(_DATASET)
        features = distribucion_sumas_a_features(d, calculado_hasta_sorteo=4, ventana="ultimos_4")
        nombres = {f.nombre for f in features}
        assert "suma_media" in nombres
        assert "suma_mediana" in nombres
        assert "suma_desviacion_estandar" in nombres
        assert "suma_p50" in nombres

    def test_conserva_el_corte_temporal_en_cada_feature(self):
        d = calcular_distribucion_sumas(_DATASET)
        features = distribucion_sumas_a_features(d, calculado_hasta_sorteo=583, ventana="ultimos_50")
        assert all(f.calculado_hasta_sorteo == 583 and f.ventana == "ultimos_50" for f in features)

    def test_distribucion_vacia_da_lista_vacia_de_features(self):
        d = calcular_distribucion_sumas([])
        assert distribucion_sumas_a_features(d, calculado_hasta_sorteo=0) == []


# Dataset de referencia para las métricas de color (Etapa M):
#
#   S1: (1,ROJO),(2,ROJO),(3,ROJO),(4,AZUL),(5,AZUL),(6,VERDE)  -> ROJO:3,AZUL:2,VERDE:1 -> max=3
#   S2: (1,ROJO),(2,AZUL),(3,VERDE),(4,ROJO),(5,AZUL),(6,VERDE) -> ROJO:2,AZUL:2,VERDE:2 -> max=2
#   S3: (1,VERDE),(2,VERDE),(3,VERDE),(4,VERDE),(5,VERDE),(6,VERDE) -> VERDE:6            -> max=6
_DATASET_COLOR = [
    _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "AZUL"), (5, "AZUL"), (6, "VERDE"))),
    _cl(2, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
    _cl(3, ((1, "VERDE"), (2, "VERDE"), (3, "VERDE"), (4, "VERDE"), (5, "VERDE"), (6, "VERDE"))),
]


class TestCalcularDistribucionConteoColor:
    def test_conteo_exacto_con_multiplicidad(self):
        filas = calcular_distribucion_conteo_color(_DATASET_COLOR, color_objetivo="ROJO", cantidad_balotas=6)
        por_valor = _por_valor(filas)
        # S1:3 rojas, S2:2 rojas, S3:0 rojas -> un sorteo por cada valor
        assert por_valor["3"].apariciones == 1
        assert por_valor["2"].apariciones == 1
        assert por_valor["0"].apariciones == 1

    def test_universo_completo_0_a_k_incluso_si_color_nunca_aparece(self):
        filas = calcular_distribucion_conteo_color(_DATASET_COLOR, color_objetivo="AMARILLO", cantidad_balotas=6)
        assert len(filas) == 7  # "0".."6"
        assert _por_valor(filas)["0"].apariciones == 3  # nunca aparece en ningun sorteo

    def test_no_deduplica_cuenta_balotas_fisicas(self):
        """Verificación cruzada explícita pedida: esta métrica usa
        MULTIPLICIDAD (3 balotas ROJO = conteo 3), a diferencia de
        coocurrencia (deduplicada)."""
        filas = calcular_distribucion_conteo_color(_DATASET_COLOR, color_objetivo="ROJO", cantidad_balotas=6)
        # si estuviera deduplicado, S1 aportaria "1" (un solo color
        # distinto ROJO presente), no "3" -confirmamos que aporta 3
        assert _por_valor(filas)["3"].apariciones == 1

    def test_cero_sorteos(self):
        filas = calcular_distribucion_conteo_color([], color_objetivo="ROJO", cantidad_balotas=6)
        assert all(f.apariciones == 0 and f.frecuencia_relativa == 0.0 for f in filas)

    def test_un_solo_sorteo(self):
        filas = calcular_distribucion_conteo_color([_DATASET_COLOR[0]], color_objetivo="ROJO", cantidad_balotas=6)
        assert _por_valor(filas)["3"].apariciones == 1
        assert all(f.total_sorteos == 1 for f in filas)

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET_COLOR[2], _DATASET_COLOR[0], _DATASET_COLOR[1]]
        f1 = calcular_distribucion_conteo_color(_DATASET_COLOR, color_objetivo="ROJO", cantidad_balotas=6)
        f2 = calcular_distribucion_conteo_color(desordenado, color_objetivo="ROJO", cantidad_balotas=6)
        assert f1 == f2

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_COLOR)
        calcular_distribucion_conteo_color(_DATASET_COLOR, color_objetivo="ROJO", cantidad_balotas=6)
        assert _DATASET_COLOR == copia

    def test_hasta_numero_sorteo_y_anti_fuga(self):
        resultado_n = calcular_distribucion_conteo_color(
            _DATASET_COLOR, color_objetivo="ROJO", cantidad_balotas=6, hasta_numero_sorteo=2,
        )
        ampliado = _DATASET_COLOR + [_cl(4, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "ROJO")))]
        resultado_n_ampliado = calcular_distribucion_conteo_color(
            ampliado, color_objetivo="ROJO", cantidad_balotas=6, hasta_numero_sorteo=2,
        )
        assert resultado_n == resultado_n_ampliado

    def test_huecos_en_numero_sorteo_no_distorsionan_el_conteo(self):
        dataset_con_hueco = [_cl(1, ((1, "ROJO"), (2, "ROJO"))), _cl(10, ((1, "AZUL"),))]
        filas = calcular_distribucion_conteo_color(dataset_con_hueco, color_objetivo="ROJO", cantidad_balotas=2)
        # total_sorteos sigue siendo 2 (cantidad real de resultados), el hueco no afecta el conteo
        assert all(f.total_sorteos == 2 for f in filas)
        assert _por_valor(filas)["2"].apariciones == 1
        assert _por_valor(filas)["0"].apariciones == 1


class TestCalcularMaximoRepeticionColorPorSorteo:
    def test_maximo_exacto_sobre_el_dataset_de_referencia(self):
        filas = calcular_maximo_repeticion_color_por_sorteo(_DATASET_COLOR, cantidad_balotas=6)
        por_valor = _por_valor(filas)
        assert por_valor["3"].apariciones == 1  # S1
        assert por_valor["2"].apariciones == 1  # S2
        assert por_valor["6"].apariciones == 1  # S3

    def test_seis_balotas_del_mismo_color_da_maximo_seis(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "ROJO")))]
        filas = calcular_maximo_repeticion_color_por_sorteo(dataset, cantidad_balotas=6)
        assert _por_valor(filas)["6"].apariciones == 1

    def test_seis_colores_distintos_da_maximo_uno(self):
        dataset = [_cl(1, ((1, "A"), (2, "B"), (3, "C"), (4, "D"), (5, "E"), (6, "F")))]
        filas = calcular_maximo_repeticion_color_por_sorteo(dataset, cantidad_balotas=6)
        assert _por_valor(filas)["1"].apariciones == 1

    def test_universo_nunca_incluye_cero(self):
        filas = calcular_maximo_repeticion_color_por_sorteo(_DATASET_COLOR, cantidad_balotas=6)
        assert "0" not in {f.valor for f in filas}

    def test_usa_multiplicidad_no_conjunto(self):
        """Verificación cruzada explícita: esta métrica es
        inherentemente multiset -toma el Counter de colores dentro
        del sorteo, no un conjunto deduplicado."""
        filas = calcular_maximo_repeticion_color_por_sorteo([_DATASET_COLOR[2]], cantidad_balotas=6)  # S3: 6 VERDE
        assert _por_valor(filas)["6"].apariciones == 1  # si fuera conjunto, seria "1" (1 color distinto)

    def test_cero_sorteos(self):
        filas = calcular_maximo_repeticion_color_por_sorteo([], cantidad_balotas=6)
        assert all(f.apariciones == 0 for f in filas)

    def test_un_solo_sorteo(self):
        filas = calcular_maximo_repeticion_color_por_sorteo([_DATASET_COLOR[0]], cantidad_balotas=6)
        assert _por_valor(filas)["3"].apariciones == 1

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET_COLOR[2], _DATASET_COLOR[0], _DATASET_COLOR[1]]
        f1 = calcular_maximo_repeticion_color_por_sorteo(_DATASET_COLOR, cantidad_balotas=6)
        f2 = calcular_maximo_repeticion_color_por_sorteo(desordenado, cantidad_balotas=6)
        assert f1 == f2

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_COLOR)
        calcular_maximo_repeticion_color_por_sorteo(_DATASET_COLOR, cantidad_balotas=6)
        assert _DATASET_COLOR == copia

    def test_hasta_numero_sorteo_y_anti_fuga(self):
        resultado_n = calcular_maximo_repeticion_color_por_sorteo(_DATASET_COLOR, cantidad_balotas=6, hasta_numero_sorteo=2)
        ampliado = _DATASET_COLOR + [_cl(4, ((1, "X"), (2, "X"), (3, "X"), (4, "X"), (5, "X"), (6, "X")))]
        resultado_n_ampliado = calcular_maximo_repeticion_color_por_sorteo(ampliado, cantidad_balotas=6, hasta_numero_sorteo=2)
        assert resultado_n == resultado_n_ampliado
