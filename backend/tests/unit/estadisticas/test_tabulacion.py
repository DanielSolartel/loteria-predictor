"""
Tests de `application/estadisticas/motor/tabulacion.py`.

Contrato probado aquí, en un solo lugar -reemplaza los tests que
antes verificaban `_distribucion_conteo_por_sorteo` indirectamente
solo a través de pares/impares y altos/bajos en distribuciones.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.application.estadisticas.motor.tabulacion import tabular_conteo_por_sorteo


def _por_valor(filas):
    return {f.valor: f for f in filas}


class TestTabularConteoPorSorteo:
    def test_conteo_exacto(self):
        filas = tabular_conteo_por_sorteo([2, 0, 2, 2], valor_maximo=3, total_sorteos=4)
        por_valor = _por_valor(filas)
        assert por_valor["0"].apariciones == 1
        assert por_valor["2"].apariciones == 3
        assert por_valor["1"].apariciones == 0
        assert por_valor["3"].apariciones == 0

    def test_incluye_todo_el_universo_0_a_valor_maximo(self):
        filas = tabular_conteo_por_sorteo([1, 1], valor_maximo=5, total_sorteos=2)
        assert {f.valor for f in filas} == {"0", "1", "2", "3", "4", "5"}

    def test_frecuencia_relativa_correcta(self):
        filas = tabular_conteo_por_sorteo([2, 2, 0, 0], valor_maximo=2, total_sorteos=4)
        por_valor = _por_valor(filas)
        assert por_valor["2"].frecuencia_relativa == 0.5
        assert por_valor["0"].frecuencia_relativa == 0.5

    def test_total_sorteos_se_recibe_explicito_no_se_infiere(self):
        filas = tabular_conteo_por_sorteo([1, 1], valor_maximo=2, total_sorteos=10)
        assert all(f.total_sorteos == 10 for f in filas)
        por_valor = _por_valor(filas)
        assert por_valor["1"].frecuencia_relativa == 0.2

    def test_cero_sorteos_no_divide_por_cero(self):
        filas = tabular_conteo_por_sorteo([], valor_maximo=3, total_sorteos=0)
        assert all(f.apariciones == 0 and f.frecuencia_relativa == 0.0 for f in filas)

    def test_valor_maximo_cero_da_un_solo_valor_posible(self):
        filas = tabular_conteo_por_sorteo([0, 0], valor_maximo=0, total_sorteos=2)
        assert len(filas) == 1
        assert filas[0].valor == "0"
        assert filas[0].apariciones == 2
