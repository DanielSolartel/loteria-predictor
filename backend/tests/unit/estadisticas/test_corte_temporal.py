"""
Tests de `application/estadisticas/motor/corte_temporal.py`.

Contrato probado aquí, en un solo lugar, en profundidad -en vez de
repetirse en cada módulo que lo usa (atrasos, recencia,
distribuciones). Esos módulos siguen teniendo sus propios tests de
integración (que el corte realmente afecte SUS cálculos), pero el
comportamiento puro de la función se verifica una sola vez, aquí.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.tipos import ResultadoNumerico

_FECHA_BASE = date(2024, 1, 1)


def _num(numero_sorteo: int) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=(1, 2, 3), superbalota=None,
    )


_DATASET = [_num(1), _num(2), _num(3), _num(4), _num(5)]


class TestFiltrarPorCorteTemporal:
    def test_hasta_numero_sorteo_none_devuelve_todo(self):
        resultado = filtrar_por_corte_temporal(_DATASET, None)
        assert [r.numero_sorteo for r in resultado] == [1, 2, 3, 4, 5]

    def test_filtra_correctamente_por_el_corte(self):
        resultado = filtrar_por_corte_temporal(_DATASET, hasta_numero_sorteo=3)
        assert [r.numero_sorteo for r in resultado] == [1, 2, 3]

    def test_corte_exacto_en_el_maximo_no_excluye_nada(self):
        resultado = filtrar_por_corte_temporal(_DATASET, hasta_numero_sorteo=5)
        assert len(resultado) == 5

    def test_corte_menor_al_minimo_devuelve_lista_vacia(self):
        resultado = filtrar_por_corte_temporal(_DATASET, hasta_numero_sorteo=0)
        assert resultado == []

    def test_no_asume_entrada_ordenada(self):
        desordenado = [_DATASET[3], _DATASET[0], _DATASET[4], _DATASET[1], _DATASET[2]]
        resultado = filtrar_por_corte_temporal(desordenado, hasta_numero_sorteo=3)
        assert {r.numero_sorteo for r in resultado} == {1, 2, 3}

    def test_no_muta_la_entrada_original(self):
        copia = list(_DATASET)
        filtrar_por_corte_temporal(_DATASET, hasta_numero_sorteo=3)
        assert _DATASET == copia

    def test_siempre_devuelve_una_lista_nueva_nunca_la_misma_referencia(self):
        resultado = filtrar_por_corte_temporal(_DATASET, None)
        assert resultado is not _DATASET

    def test_lista_vacia(self):
        assert filtrar_por_corte_temporal([], hasta_numero_sorteo=10) == []
        assert filtrar_por_corte_temporal([], None) == []
