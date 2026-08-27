"""
Tests de `application/estadisticas/motor/consecutivos.py`.

Dataset de referencia (rango 1-40, K=5):

    S1: 3, 4, 5, 20, 21    -> racha de 3 (3,4,5) + racha de 2 (20,21)
                              -> pares=3, trios=1, racha_maxima=3
    S2: 1, 10, 20, 30, 40  -> sin ningun consecutivo
                              -> pares=0, trios=0, racha_maxima=1
    S3: 6, 7, 8, 9, 30     -> una racha de 4 (6,7,8,9)
                              -> pares=3, trios=2, racha_maxima=4
    S4: 1, 2, 3, 4, 5      -> totalmente consecutivo (racha de 5)
                              -> pares=4, trios=3, racha_maxima=5
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.consecutivos import (
    calcular_distribucion_pares_consecutivos,
    calcular_distribucion_pares_consecutivos_colorloto,
    calcular_distribucion_racha_maxima,
    calcular_distribucion_racha_maxima_colorloto,
    calcular_distribucion_trios_consecutivos,
    calcular_distribucion_trios_consecutivos_colorloto,
)
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
    _num(1, (3, 4, 5, 20, 21)),
    _num(2, (1, 10, 20, 30, 40)),
    _num(3, (6, 7, 8, 9, 30)),
    _num(4, (1, 2, 3, 4, 5)),
]


def _por_valor(filas):
    return {f.valor: f for f in filas}


class TestCalcularDistribucionParesConsecutivos:
    def test_conteo_exacto_sobre_el_dataset_de_referencia(self):
        filas = calcular_distribucion_pares_consecutivos(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        por_valor = _por_valor(filas)
        assert por_valor["3"].apariciones == 2
        assert por_valor["0"].apariciones == 1
        assert por_valor["4"].apariciones == 1

    def test_universo_0_a_k_menos_1(self):
        filas = calcular_distribucion_pares_consecutivos(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert {f.valor for f in filas} == {"0", "1", "2", "3", "4"}

    def test_sorteo_totalmente_consecutivo_da_k_menos_1_pares(self):
        filas = calcular_distribucion_pares_consecutivos(
            [_num(1, (1, 2, 3, 4, 5))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        assert _por_valor(filas)["4"].apariciones == 1

    def test_sin_ningun_consecutivo_da_cero_pares(self):
        filas = calcular_distribucion_pares_consecutivos(
            [_num(1, (1, 10, 20, 30, 40))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        assert _por_valor(filas)["0"].apariciones == 1

    def test_cero_sorteos_no_divide_por_cero(self):
        filas = calcular_distribucion_pares_consecutivos([], rango_min=1, rango_max=40, cantidad_numeros=5)
        assert all(f.apariciones == 0 and f.frecuencia_relativa == 0.0 for f in filas)

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset_invalido = [_num(1, (1, 2, 999, 4, 5))]
        with pytest.raises(ValueError, match="999"):
            calcular_distribucion_pares_consecutivos(dataset_invalido, rango_min=1, rango_max=40, cantidad_numeros=5)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_distribucion_pares_consecutivos(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert _DATASET == copia

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET[2], _DATASET[0], _DATASET[3], _DATASET[1]]
        f1 = calcular_distribucion_pares_consecutivos(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        f2 = calcular_distribucion_pares_consecutivos(desordenado, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert f1 == f2


class TestCalcularDistribucionTriosConsecutivos:
    def test_conteo_exacto_sobre_el_dataset_de_referencia(self):
        filas = calcular_distribucion_trios_consecutivos(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        por_valor = _por_valor(filas)
        assert por_valor["1"].apariciones == 1
        assert por_valor["0"].apariciones == 1
        assert por_valor["2"].apariciones == 1
        assert por_valor["3"].apariciones == 1

    def test_racha_de_exactamente_3_da_un_solo_trio(self):
        filas = calcular_distribucion_trios_consecutivos(
            [_num(1, (3, 4, 5, 20, 21))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        assert _por_valor(filas)["1"].apariciones == 1

    def test_racha_de_4_da_dos_trios(self):
        filas = calcular_distribucion_trios_consecutivos(
            [_num(1, (6, 7, 8, 9, 30))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        assert _por_valor(filas)["2"].apariciones == 1

    def test_no_confunde_pares_con_trios(self):
        filas_pares = calcular_distribucion_pares_consecutivos(
            [_num(1, (1, 10, 20, 21, 30))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        filas_trios = calcular_distribucion_trios_consecutivos(
            [_num(1, (1, 10, 20, 21, 30))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        assert _por_valor(filas_pares)["1"].apariciones == 1
        assert _por_valor(filas_trios)["0"].apariciones == 1

    def test_cero_sorteos(self):
        filas = calcular_distribucion_trios_consecutivos([], rango_min=1, rango_max=40, cantidad_numeros=5)
        assert all(f.apariciones == 0 for f in filas)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_distribucion_trios_consecutivos(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert _DATASET == copia


class TestCalcularDistribucionRachaMaxima:
    def test_conteo_exacto_sobre_el_dataset_de_referencia(self):
        filas = calcular_distribucion_racha_maxima(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        por_valor = _por_valor(filas)
        assert por_valor["3"].apariciones == 1
        assert por_valor["1"].apariciones == 1
        assert por_valor["4"].apariciones == 1
        assert por_valor["5"].apariciones == 1

    def test_dos_rachas_separadas_toma_la_maxima_no_la_suma(self):
        filas = calcular_distribucion_racha_maxima(
            [_num(1, (3, 4, 5, 20, 21))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        assert _por_valor(filas)["3"].apariciones == 1
        assert all(f.apariciones == 0 for f in filas if f.valor == "5")

    def test_universo_empieza_en_1_nunca_incluye_0(self):
        filas = calcular_distribucion_racha_maxima(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert "0" not in {f.valor for f in filas}
        assert {f.valor for f in filas} == {"1", "2", "3", "4", "5"}

    def test_numero_aislado_es_racha_de_longitud_1(self):
        filas = calcular_distribucion_racha_maxima(
            [_num(1, (1, 10, 20, 30, 40))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        assert _por_valor(filas)["1"].apariciones == 1

    def test_cero_sorteos_no_divide_por_cero_y_sigue_sin_incluir_cero(self):
        filas = calcular_distribucion_racha_maxima([], rango_min=1, rango_max=40, cantidad_numeros=5)
        assert "0" not in {f.valor for f in filas}
        assert all(f.apariciones == 0 for f in filas)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_distribucion_racha_maxima(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert _DATASET == copia

    def test_consistencia_cruzada_con_trios(self):
        filas_trios = calcular_distribucion_trios_consecutivos(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)
        filas_racha = calcular_distribucion_racha_maxima(_DATASET, rango_min=1, rango_max=40, cantidad_numeros=5)

        sorteos_con_trio = sum(f.apariciones for f in filas_trios if f.valor != "0")
        sorteos_con_racha_3_o_mas = sum(f.apariciones for f in filas_racha if int(f.valor) >= 3)
        assert sorteos_con_trio <= sorteos_con_racha_3_o_mas


class TestColorLotoConDeduplicacion:
    def test_numero_repetido_no_alarga_la_racha(self):
        dataset = [_cl(1, ((2, "ROJO"), (2, "AZUL"), (3, "VERDE"), (5, "ROJO"), (6, "AZUL"), (7, "VERDE")))]
        filas_pares = calcular_distribucion_pares_consecutivos_colorloto(
            dataset, rango_min=1, rango_max=7, cantidad_balotas=6
        )
        filas_trios = calcular_distribucion_trios_consecutivos_colorloto(
            dataset, rango_min=1, rango_max=7, cantidad_balotas=6
        )
        filas_racha = calcular_distribucion_racha_maxima_colorloto(
            dataset, rango_min=1, rango_max=7, cantidad_balotas=6
        )

        assert _por_valor(filas_pares)["3"].apariciones == 1
        assert _por_valor(filas_trios)["1"].apariciones == 1
        assert _por_valor(filas_racha)["3"].apariciones == 1

    def test_todo_el_sorteo_repetido_da_racha_de_un_solo_numero_distinto(self):
        dataset = [_cl(1, ((4, "ROJO"), (4, "AZUL"), (4, "VERDE"), (4, "ROJO"), (4, "AZUL"), (4, "VERDE")))]
        filas = calcular_distribucion_racha_maxima_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["1"].apariciones == 1

    def test_no_muta_la_entrada_colorloto(self):
        dataset = [_cl(1, ((2, "ROJO"), (2, "AZUL"), (3, "VERDE")))]
        copia = list(dataset)
        calcular_distribucion_pares_consecutivos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert dataset == copia

    def test_numero_fuera_de_rango_colorloto_lanza_value_error(self):
        dataset_invalido = [_cl(1, ((9, "ROJO"),))]
        with pytest.raises(ValueError, match="9"):
            calcular_distribucion_pares_consecutivos_colorloto(
                dataset_invalido, rango_min=1, rango_max=7, cantidad_balotas=6
            )


class TestPropiedadAntiFuga:
    def test_anti_fuga_pares_consecutivos(self):
        r_n = calcular_distribucion_pares_consecutivos(
            _DATASET, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2
        )
        ampliado = _DATASET + [_num(5, (1, 2, 3, 4, 5))]
        r_amp = calcular_distribucion_pares_consecutivos(
            ampliado, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2
        )
        assert r_n == r_amp

    def test_anti_fuga_trios_consecutivos(self):
        r_n = calcular_distribucion_trios_consecutivos(
            _DATASET, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2
        )
        ampliado = _DATASET + [_num(5, (1, 2, 3, 4, 5))]
        r_amp = calcular_distribucion_trios_consecutivos(
            ampliado, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2
        )
        assert r_n == r_amp

    def test_anti_fuga_racha_maxima(self):
        r_n = calcular_distribucion_racha_maxima(
            _DATASET, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2
        )
        ampliado = _DATASET + [_num(5, (1, 2, 3, 4, 5))]
        r_amp = calcular_distribucion_racha_maxima(
            ampliado, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2
        )
        assert r_n == r_amp

    def test_anti_fuga_colorloto(self):
        dataset_cl = [_cl(1, ((1, "ROJO"), (2, "AZUL"))), _cl(2, ((5, "VERDE"), (6, "ROJO")))]
        r_n = calcular_distribucion_racha_maxima_colorloto(
            dataset_cl, rango_min=1, rango_max=7, cantidad_balotas=2, hasta_numero_sorteo=1
        )
        ampliado = dataset_cl + [_cl(3, ((3, "AZUL"), (4, "VERDE")))]
        r_amp = calcular_distribucion_racha_maxima_colorloto(
            ampliado, rango_min=1, rango_max=7, cantidad_balotas=2, hasta_numero_sorteo=1
        )
        assert r_n == r_amp
