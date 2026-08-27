"""
Tests de `application/estadisticas/motor/repeticiones.py`.

Dataset de referencia (rango 1-40, K=5), con un HUECO deliberado en
la numeración (100, 101, 105 -falta 102-104):

    S100: 1, 5, 10, 20, 30
    S101: 5, 8, 10, 22, 31   -> repetidos con S100: {5,10} = 2
    S105: 5, 8, 10, 22, 31   -> IDÉNTICO a S101, pero 101->105 NO es
                                 transición válida (hueco) -no debe
                                 contarse como "5 repetidos".
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.repeticiones import (
    calcular_repeticion_superbalota_entre_sorteos,
    calcular_repeticiones_entre_sorteos,
    calcular_repeticiones_entre_sorteos_colorloto,
)
from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico

_FECHA_BASE = date(2024, 1, 1)


def _num(numero_sorteo: int, numeros: tuple[int, ...], superbalota: int | None = None) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=superbalota,
    )


def _cl(numero_sorteo: int, pares: tuple[tuple[int, str], ...]) -> ResultadoColorLoto:
    return ResultadoColorLoto(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", pares=pares,
    )


_DATASET_CON_HUECO = [
    _num(100, (1, 5, 10, 20, 30), superbalota=3),
    _num(101, (5, 8, 10, 22, 31), superbalota=3),
    _num(105, (5, 8, 10, 22, 31), superbalota=7),
]


def _por_valor(filas):
    return {f.valor: f for f in filas}


class TestTransicionesNormales:
    def test_dos_sorteos_consecutivos_cero_repetidos(self):
        dataset = [_num(1, (1, 2, 3, 4, 5)), _num(2, (6, 7, 8, 9, 10))]
        filas = calcular_repeticiones_entre_sorteos(dataset, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert _por_valor(filas)["0"].apariciones == 1

    def test_dos_sorteos_consecutivos_todos_repetidos(self):
        dataset = [_num(1, (1, 2, 3, 4, 5)), _num(2, (1, 2, 3, 4, 5))]
        filas = calcular_repeticiones_entre_sorteos(dataset, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert _por_valor(filas)["5"].apariciones == 1

    def test_caso_intermedio_dos_repetidos(self):
        dataset = [_num(100, (1, 5, 10, 20, 30)), _num(101, (5, 8, 10, 22, 31))]
        filas = calcular_repeticiones_entre_sorteos(dataset, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert _por_valor(filas)["2"].apariciones == 1

    def test_universo_completo_0_a_k(self):
        dataset = [_num(1, (1, 2, 3, 4, 5)), _num(2, (1, 2, 3, 4, 5))]
        filas = calcular_repeticiones_entre_sorteos(dataset, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert {f.valor for f in filas} == {"0", "1", "2", "3", "4", "5"}

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET_CON_HUECO[2], _DATASET_CON_HUECO[0], _DATASET_CON_HUECO[1]]
        f1 = calcular_repeticiones_entre_sorteos(_DATASET_CON_HUECO, rango_min=1, rango_max=40, cantidad_numeros=5)
        f2 = calcular_repeticiones_entre_sorteos(desordenado, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert f1 == f2

    def test_no_muta_la_entrada_original(self):
        copia = list(_DATASET_CON_HUECO)
        calcular_repeticiones_entre_sorteos(_DATASET_CON_HUECO, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert _DATASET_CON_HUECO == copia


class TestHuecos:
    def test_100_a_101_participa_101_a_105_no(self):
        filas = calcular_repeticiones_entre_sorteos(_DATASET_CON_HUECO, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert _por_valor(filas)["2"].apariciones == 1
        assert _por_valor(filas)["5"].apariciones == 0
        assert all(f.total_sorteos == 1 for f in filas)

    def test_hueco_no_se_cuenta_como_cero_repetidos(self):
        filas = calcular_repeticiones_entre_sorteos(_DATASET_CON_HUECO, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert sum(f.apariciones for f in filas) == 1

    def test_hueco_de_dos_transiciones_deja_al_menos_las_validas(self):
        dataset = [_num(1, (1, 2, 3, 4, 5)), _num(2, (1, 2, 3, 4, 5)), _num(10, (1, 2, 3, 4, 5))]
        filas = calcular_repeticiones_entre_sorteos(dataset, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert sum(f.apariciones for f in filas) == 1
        assert _por_valor(filas)["5"].apariciones == 1


class TestCortesTemporales:
    def test_resultados_posteriores_al_corte_no_participan(self):
        dataset = [_num(1, (1, 2, 3, 4, 5)), _num(2, (1, 2, 3, 4, 5)), _num(3, (6, 7, 8, 9, 10))]
        filas = calcular_repeticiones_entre_sorteos(
            dataset, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2,
        )
        assert sum(f.apariciones for f in filas) == 1
        assert _por_valor(filas)["5"].apariciones == 1

    def test_resultado_futuro_no_puede_crear_una_transicion(self):
        dataset = [_num(1, (1, 2, 3, 4, 5))]
        dataset_completo = dataset + [_num(2, (1, 2, 3, 4, 5))]
        filas_cortado = calcular_repeticiones_entre_sorteos(
            dataset_completo, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=1,
        )
        assert sum(f.apariciones for f in filas_cortado) == 0

    def test_propiedad_anti_fuga_agregar_futuros_no_cambia_el_resultado(self):
        dataset = [_num(1, (1, 2, 3, 4, 5)), _num(2, (1, 2, 3, 4, 5))]
        resultado_n = calcular_repeticiones_entre_sorteos(
            dataset, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2,
        )
        dataset_ampliado = dataset + [_num(3, (1, 2, 3, 4, 5)), _num(4, (6, 7, 8, 9, 10))]
        resultado_n_ampliado = calcular_repeticiones_entre_sorteos(
            dataset_ampliado, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2,
        )
        assert resultado_n == resultado_n_ampliado

    def test_filtrado_ocurre_antes_del_analisis(self):
        dataset = [_num(1, (1, 2, 3, 4, 5)), _num(2, (6, 7, 8, 9, 10)), _num(3, (6, 7, 8, 9, 10))]
        filas_con_corte = calcular_repeticiones_entre_sorteos(
            dataset, rango_min=1, rango_max=40, cantidad_numeros=5, hasta_numero_sorteo=2,
        )
        assert sum(f.apariciones for f in filas_con_corte) == 1


class TestCasosPequenos:
    def test_cero_sorteos(self):
        filas = calcular_repeticiones_entre_sorteos([], rango_min=1, rango_max=40, cantidad_numeros=5)
        assert all(f.apariciones == 0 and f.frecuencia_relativa == 0.0 for f in filas)
        assert all(f.total_sorteos == 0 for f in filas)

    def test_un_solo_sorteo_sin_transiciones(self):
        filas = calcular_repeticiones_entre_sorteos(
            [_num(1, (1, 2, 3, 4, 5))], rango_min=1, rango_max=40, cantidad_numeros=5
        )
        assert all(f.apariciones == 0 for f in filas)
        assert all(f.total_sorteos == 0 for f in filas)

    def test_cero_transiciones_validas_por_huecos_en_todo_el_dataset(self):
        dataset = [_num(1, (1, 2, 3, 4, 5)), _num(50, (6, 7, 8, 9, 10)), _num(100, (1, 2, 3, 4, 5))]
        filas = calcular_repeticiones_entre_sorteos(dataset, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_dos_resultados_con_el_mismo_numero_sorteo_se_excluyen_naturalmente(self):
        dataset = [_num(5, (1, 2, 3, 4, 5)), _num(5, (6, 7, 8, 9, 10))]
        filas = calcular_repeticiones_entre_sorteos(dataset, rango_min=1, rango_max=40, cantidad_numeros=5)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)


class TestValidacion:
    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_num(1, (1, 2, 999, 4, 5)), _num(2, (1, 2, 3, 4, 5))]
        with pytest.raises(ValueError, match="999"):
            calcular_repeticiones_entre_sorteos(dataset, rango_min=1, rango_max=40, cantidad_numeros=5)

    def test_numero_fuera_de_rango_colorloto_lanza_value_error(self):
        dataset = [_cl(1, ((9, "ROJO"),)), _cl(2, ((1, "AZUL"),))]
        with pytest.raises(ValueError, match="9"):
            calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)


class TestSuperbalota:
    def test_superbalotas_diferentes_da_cero(self):
        dataset = [_num(1, (1, 2, 3, 4, 5), superbalota=3), _num(2, (6, 7, 8, 9, 10), superbalota=9)]
        filas = calcular_repeticion_superbalota_entre_sorteos(dataset)
        assert _por_valor(filas)["0"].apariciones == 1
        assert _por_valor(filas)["1"].apariciones == 0

    def test_superbalotas_iguales_da_uno(self):
        dataset = [_num(1, (1, 2, 3, 4, 5), superbalota=7), _num(2, (6, 7, 8, 9, 10), superbalota=7)]
        filas = calcular_repeticion_superbalota_entre_sorteos(dataset)
        assert _por_valor(filas)["1"].apariciones == 1

    def test_transicion_con_superbalota_none_no_participa(self):
        dataset = [_num(1, (1, 2, 3, 4, 5), superbalota=None), _num(2, (6, 7, 8, 9, 10), superbalota=7)]
        filas = calcular_repeticion_superbalota_entre_sorteos(dataset)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_huecos_tambien_aplican_a_superbalota(self):
        filas = calcular_repeticion_superbalota_entre_sorteos(_DATASET_CON_HUECO)
        assert _por_valor(filas)["1"].apariciones == 1
        assert sum(f.apariciones for f in filas) == 1

    def test_corte_temporal_en_superbalota(self):
        dataset = [
            _num(1, (1, 2, 3, 4, 5), superbalota=3),
            _num(2, (6, 7, 8, 9, 10), superbalota=3),
            _num(3, (1, 1, 1, 1, 1), superbalota=9),
        ]
        filas = calcular_repeticion_superbalota_entre_sorteos(dataset, hasta_numero_sorteo=2)
        assert sum(f.apariciones for f in filas) == 1
        assert _por_valor(filas)["1"].apariciones == 1

    def test_entrada_desordenada(self):
        dataset = [_num(2, (6, 7, 8, 9, 10), superbalota=7), _num(1, (1, 2, 3, 4, 5), superbalota=7)]
        filas = calcular_repeticion_superbalota_entre_sorteos(dataset)
        assert _por_valor(filas)["1"].apariciones == 1

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_CON_HUECO)
        calcular_repeticion_superbalota_entre_sorteos(_DATASET_CON_HUECO)
        assert _DATASET_CON_HUECO == copia

    def test_universo_es_binario_0_1(self):
        filas = calcular_repeticion_superbalota_entre_sorteos(_DATASET_CON_HUECO)
        assert {f.valor for f in filas} == {"0", "1"}


class TestColorLotoMulticonjunto:
    def test_sin_repeticion_compartida(self):
        dataset = [
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(2, ((7, "ROJO"), (7, "AZUL"), (7, "VERDE"), (7, "ROJO"), (7, "AZUL"), (7, "VERDE"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["0"].apariciones == 1

    def test_repeticion_parcial(self):
        dataset = [
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(2, ((1, "AZUL"), (2, "VERDE"), (7, "ROJO"), (7, "AZUL"), (7, "VERDE"), (7, "ROJO"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["2"].apariciones == 1

    def test_caso_del_enunciado_multiconjunto_da_4(self):
        dataset = [
            _cl(1, ((2, "ROJO"), (2, "AZUL"), (3, "VERDE"), (5, "ROJO"), (6, "AZUL"), (7, "VERDE"))),
            _cl(2, ((2, "ROJO"), (2, "AZUL"), (4, "VERDE"), (5, "ROJO"), (5, "AZUL"), (7, "VERDE"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["4"].apariciones == 1

    def test_repeticion_interna_en_ambos_sorteos(self):
        dataset = [
            _cl(1, ((3, "ROJO"), (3, "AZUL"), (1, "VERDE"), (2, "ROJO"), (4, "AZUL"), (5, "VERDE"))),
            _cl(2, ((3, "ROJO"), (3, "AZUL"), (6, "VERDE"), (7, "ROJO"), (1, "AZUL"), (2, "VERDE"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["4"].apariciones == 1

    def test_las_6_balotas_iguales_en_ambos_sorteos(self):
        dataset = [
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(2, ((1, "AZUL"), (2, "VERDE"), (3, "ROJO"), (4, "AZUL"), (5, "VERDE"), (6, "ROJO"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["6"].apariciones == 1

    def test_numero_repetido_dos_veces_en_ambos_aporta_2_no_1(self):
        dataset = [
            _cl(1, ((5, "ROJO"), (5, "AZUL"), (1, "VERDE"), (2, "ROJO"), (3, "AZUL"), (4, "VERDE"))),
            _cl(2, ((5, "ROJO"), (5, "AZUL"), (6, "VERDE"), (7, "ROJO"), (1, "AZUL"), (2, "VERDE"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["4"].apariciones == 1
        assert _por_valor(filas)["3"].apariciones == 0

    def test_es_multiconjunto_no_conjunto_verificacion_directa(self):
        dataset = [
            _cl(1, ((2, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(2, ((2, "ROJO"), (7, "AZUL"), (7, "VERDE"), (7, "ROJO"), (7, "AZUL"), (7, "VERDE"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["1"].apariciones == 1

    def test_huecos_en_colorloto(self):
        dataset = [
            _cl(100, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(105, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_corte_temporal_en_colorloto(self):
        dataset = [
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(2, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(3, ((7, "ROJO"), (7, "AZUL"), (7, "VERDE"), (7, "ROJO"), (7, "AZUL"), (7, "VERDE"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(
            dataset, rango_min=1, rango_max=7, cantidad_balotas=6, hasta_numero_sorteo=2,
        )
        assert sum(f.apariciones for f in filas) == 1
        assert _por_valor(filas)["6"].apariciones == 1

    def test_entrada_desordenada_colorloto(self):
        dataset = [
            _cl(2, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(1, ((1, "AZUL"), (2, "VERDE"), (3, "ROJO"), (4, "AZUL"), (5, "VERDE"), (6, "ROJO"))),
        ]
        filas = calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert _por_valor(filas)["6"].apariciones == 1

    def test_no_muta_la_entrada_colorloto(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "AZUL"))), _cl(2, ((1, "AZUL"), (3, "VERDE")))]
        copia = list(dataset)
        calcular_repeticiones_entre_sorteos_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=2)
        assert dataset == copia

    def test_anti_fuga_colorloto(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "AZUL"))), _cl(2, ((1, "AZUL"), (2, "VERDE")))]
        r_n = calcular_repeticiones_entre_sorteos_colorloto(
            dataset, rango_min=1, rango_max=7, cantidad_balotas=2, hasta_numero_sorteo=2,
        )
        ampliado = dataset + [_cl(3, ((5, "ROJO"), (6, "AZUL")))]
        r_amp = calcular_repeticiones_entre_sorteos_colorloto(
            ampliado, rango_min=1, rango_max=7, cantidad_balotas=2, hasta_numero_sorteo=2,
        )
        assert r_n == r_amp
