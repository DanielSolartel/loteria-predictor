"""
Tests de `application/estadisticas/motor/relacion_baloto_revancha.py`.

Dataset de referencia (verificado INDEPENDIENTEMENTE con Python
estándar puro -emparejamiento manual con dict, intersección de
conjuntos, `collections.Counter`- antes de escribir estos tests):

    Baloto:   S1(1,2,3,4,5,sb=9)  S2(10,20,30,40,41,sb=3)  S3(1,2,3,10,11,sb=7)  S5(...)
    Revancha: S1(1,2,3,6,7,sb=9)  S2(11,12,13,14,15,sb=3)  S3(1,2,3,10,11,sb=None)  S4(...)

Emparejados por numero_sorteo (inner join): solo {1,2,3} -S5 (solo
Baloto) y S4 (solo Revancha) quedan excluidos.

Coincidencias verificadas a mano: S1->3, S2->0, S3->5 (máximo).
Superbalota: S1 coincide (9=9), S2 coincide (3=3), S3 excluida
(revancha sb=None) -distribución final: {"1": 2} sobre 2 parejas
con dato, no 3.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.relacion_baloto_revancha import (
    calcular_coincidencia_superbalota_baloto_revancha,
    calcular_coincidencias_baloto_revancha,
)
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoNumerico

_FECHA_BASE = date(2024, 1, 1)


def _num(numero_sorteo: int, numeros: tuple[int, ...], superbalota: int | None = None) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=superbalota,
    )


_BALOTO = [
    _num(1, (1, 2, 3, 4, 5), superbalota=9),
    _num(2, (10, 20, 30, 40, 41), superbalota=3),
    _num(3, (1, 2, 3, 10, 11), superbalota=7),
    _num(5, (6, 7, 8, 9, 12), superbalota=1),  # sin pareja en Revancha
]

_REVANCHA = [
    _num(1, (1, 2, 3, 6, 7), superbalota=9),
    _num(2, (11, 12, 13, 14, 15), superbalota=3),
    _num(3, (1, 2, 3, 10, 11), superbalota=None),
    _num(4, (20, 21, 22, 23, 24), superbalota=1),  # sin pareja en Baloto
]


def _por_valor(filas: list[FrecuenciaObservada]) -> dict[str, FrecuenciaObservada]:
    return {f.valor: f for f in filas}


class TestEmparejamientoPorNumeroSorteo:
    def test_solo_los_sorteos_presentes_en_ambas_familias_participan(self):
        filas = calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        assert sum(f.apariciones for f in filas) == 3

    def test_sorteo_solo_en_baloto_se_excluye_no_cuenta_como_cero(self):
        filas = calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        assert all(f.total_sorteos == 3 for f in filas)

    def test_sorteo_solo_en_revancha_se_excluye(self):
        baloto_minimo = [_num(1, (1, 2, 3, 4, 5), superbalota=9)]
        revancha_minima = [_num(1, (1, 2, 3, 4, 5), superbalota=9), _num(2, (6, 7, 8, 9, 10), superbalota=1)]
        filas = calcular_coincidencias_baloto_revancha(baloto_minimo, revancha_minima, cantidad_numeros=5)
        assert sum(f.apariciones for f in filas) == 1

    def test_emparejamiento_nunca_usa_posicion_ordinal_de_la_lista(self):
        baloto_desordenado = [_BALOTO[3], _BALOTO[1], _BALOTO[0], _BALOTO[2]]
        revancha_desordenada = [_REVANCHA[2], _REVANCHA[0], _REVANCHA[3], _REVANCHA[1]]

        f_original = calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        f_baloto_desordenado = calcular_coincidencias_baloto_revancha(baloto_desordenado, _REVANCHA, cantidad_numeros=5)
        f_revancha_desordenada = calcular_coincidencias_baloto_revancha(_BALOTO, revancha_desordenada, cantidad_numeros=5)
        f_ambas_desordenadas = calcular_coincidencias_baloto_revancha(baloto_desordenado, revancha_desordenada, cantidad_numeros=5)

        assert f_original == f_baloto_desordenado == f_revancha_desordenada == f_ambas_desordenadas

    def test_cero_parejas_ninguna_familia_comparte_numero_sorteo(self):
        baloto = [_num(1, (1, 2, 3, 4, 5))]
        revancha = [_num(99, (1, 2, 3, 4, 5))]
        filas = calcular_coincidencias_baloto_revancha(baloto, revancha, cantidad_numeros=5)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_cero_parejas_alguna_lista_vacia(self):
        filas = calcular_coincidencias_baloto_revancha([], _REVANCHA, cantidad_numeros=5)
        assert all(f.total_sorteos == 0 for f in filas)
        filas2 = calcular_coincidencias_baloto_revancha(_BALOTO, [], cantidad_numeros=5)
        assert all(f.total_sorteos == 0 for f in filas2)

    def test_una_sola_pareja(self):
        filas = calcular_coincidencias_baloto_revancha([_BALOTO[0]], [_REVANCHA[0]], cantidad_numeros=5)
        assert all(f.total_sorteos == 1 for f in filas)
        assert _por_valor(filas)["3"].apariciones == 1

    def test_huecos_en_numero_sorteo_no_afectan_el_emparejamiento(self):
        baloto = [_num(100, (1, 2, 3, 4, 5), superbalota=9)]
        revancha = [_num(100, (1, 2, 3, 4, 5), superbalota=9), _num(105, (6, 7, 8, 9, 10), superbalota=1)]
        filas = calcular_coincidencias_baloto_revancha(baloto, revancha, cantidad_numeros=5)
        assert sum(f.apariciones for f in filas) == 1
        assert _por_valor(filas)["5"].apariciones == 1

    def test_no_muta_ninguna_de_las_dos_entradas(self):
        copia_baloto = list(_BALOTO)
        copia_revancha = list(_REVANCHA)
        calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        calcular_coincidencia_superbalota_baloto_revancha(_BALOTO, _REVANCHA)
        assert _BALOTO == copia_baloto
        assert _REVANCHA == copia_revancha


class TestCoincidenciasNumeros:
    def test_distribucion_exacta_verificada_independientemente(self):
        filas = calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        por_valor = _por_valor(filas)
        assert por_valor["3"].apariciones == 1
        assert por_valor["0"].apariciones == 1
        assert por_valor["5"].apariciones == 1

    def test_cero_coincidencias(self):
        filas = calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        assert _por_valor(filas)["0"].apariciones == 1

    def test_coincidencia_parcial(self):
        filas = calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        assert _por_valor(filas)["3"].apariciones == 1

    def test_coincidencia_maxima(self):
        filas = calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        assert _por_valor(filas)["5"].apariciones == 1

    def test_universo_completo_0_a_cantidad_numeros(self):
        filas = calcular_coincidencias_baloto_revancha(_BALOTO, _REVANCHA, cantidad_numeros=5)
        assert {f.valor for f in filas} == {"0", "1", "2", "3", "4", "5"}

    def test_cantidad_numeros_respetada_con_otro_valor(self):
        baloto = [_num(1, (1, 2, 3))]
        revancha = [_num(1, (1, 2, 9))]
        filas = calcular_coincidencias_baloto_revancha(baloto, revancha, cantidad_numeros=3)
        assert {f.valor for f in filas} == {"0", "1", "2", "3"}
        assert _por_valor(filas)["2"].apariciones == 1

    def test_hasta_numero_sorteo_y_anti_fuga(self):
        resultado_n = calcular_coincidencias_baloto_revancha(
            _BALOTO, _REVANCHA, cantidad_numeros=5, hasta_numero_sorteo=2,
        )
        baloto_ampliado = _BALOTO + [_num(6, (1, 2, 3, 4, 5), superbalota=9)]
        revancha_ampliada = _REVANCHA + [_num(6, (1, 2, 3, 4, 5), superbalota=9)]
        resultado_n_ampliado = calcular_coincidencias_baloto_revancha(
            baloto_ampliado, revancha_ampliada, cantidad_numeros=5, hasta_numero_sorteo=2,
        )
        assert resultado_n == resultado_n_ampliado
        assert all(f.total_sorteos == 2 for f in resultado_n)


class TestCoincidenciaSuperbalota:
    def test_coincidencia(self):
        baloto = [_num(1, (1, 2, 3, 4, 5), superbalota=9)]
        revancha = [_num(1, (1, 2, 3, 4, 5), superbalota=9)]
        filas = calcular_coincidencia_superbalota_baloto_revancha(baloto, revancha)
        assert _por_valor(filas)["1"].apariciones == 1

    def test_no_coincidencia(self):
        baloto = [_num(1, (1, 2, 3, 4, 5), superbalota=9)]
        revancha = [_num(1, (1, 2, 3, 4, 5), superbalota=3)]
        filas = calcular_coincidencia_superbalota_baloto_revancha(baloto, revancha)
        assert _por_valor(filas)["0"].apariciones == 1

    def test_none_en_baloto_excluye_la_pareja(self):
        baloto = [_num(1, (1, 2, 3, 4, 5), superbalota=None)]
        revancha = [_num(1, (1, 2, 3, 4, 5), superbalota=9)]
        filas = calcular_coincidencia_superbalota_baloto_revancha(baloto, revancha)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_none_en_revancha_excluye_la_pareja(self):
        baloto = [_num(1, (1, 2, 3, 4, 5), superbalota=9)]
        revancha = [_num(1, (1, 2, 3, 4, 5), superbalota=None)]
        filas = calcular_coincidencia_superbalota_baloto_revancha(baloto, revancha)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_none_en_ambos_excluye_la_pareja(self):
        baloto = [_num(1, (1, 2, 3, 4, 5), superbalota=None)]
        revancha = [_num(1, (1, 2, 3, 4, 5), superbalota=None)]
        filas = calcular_coincidencia_superbalota_baloto_revancha(baloto, revancha)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_none_no_se_cuenta_como_cero(self):
        baloto = [_num(1, (1, 2, 3, 4, 5), superbalota=9), _num(2, (6, 7, 8, 9, 10), superbalota=None)]
        revancha = [_num(1, (1, 2, 3, 4, 5), superbalota=3), _num(2, (6, 7, 8, 9, 10), superbalota=1)]
        filas = calcular_coincidencia_superbalota_baloto_revancha(baloto, revancha)
        assert _por_valor(filas)["0"].apariciones == 1
        assert all(f.total_sorteos == 1 for f in filas)

    def test_distribucion_verificada_independientemente(self):
        filas = calcular_coincidencia_superbalota_baloto_revancha(_BALOTO, _REVANCHA)
        assert _por_valor(filas)["1"].apariciones == 2
        assert all(f.total_sorteos == 2 for f in filas)

    def test_universo_binario(self):
        filas = calcular_coincidencia_superbalota_baloto_revancha(_BALOTO, _REVANCHA)
        assert {f.valor for f in filas} == {"0", "1"}

    def test_hasta_numero_sorteo_y_anti_fuga(self):
        resultado_n = calcular_coincidencia_superbalota_baloto_revancha(_BALOTO, _REVANCHA, hasta_numero_sorteo=2)
        baloto_ampliado = _BALOTO + [_num(6, (1,), superbalota=1)]
        revancha_ampliada = _REVANCHA + [_num(6, (1,), superbalota=2)]
        resultado_n_ampliado = calcular_coincidencia_superbalota_baloto_revancha(
            baloto_ampliado, revancha_ampliada, hasta_numero_sorteo=2,
        )
        assert resultado_n == resultado_n_ampliado
