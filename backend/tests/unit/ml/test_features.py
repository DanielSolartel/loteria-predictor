"""Tests de `application/ml/features.py` -Etapa AE-36."""
from __future__ import annotations

from datetime import date

from app.application.ml.features import (
    aparecio_en_sorteo_anterior,
    frecuencia_en_ventana,
    frecuencia_historica,
    sorteos_desde_ultima_aparicion,
)
from app.application.estadisticas.tipos import ResultadoNumerico


def _r(n: int, numeros: tuple[int, ...]) -> ResultadoNumerico:
    return ResultadoNumerico(numero_sorteo=n, fecha=date(2026, 1, n), dia_semana="lunes", numeros=numeros, superbalota=None)


_HIST = [
    _r(1, (7, 1, 2, 3, 4)),
    _r(2, (10, 11, 12, 13, 14)),
    _r(3, (7, 20, 21, 22, 23)),
    _r(4, (30, 31, 32, 33, 34)),
]


class TestFrecuenciaHistorica:
    def test_calculo_correcto(self):
        assert frecuencia_historica(_HIST, 7) == 0.5

    def test_numero_nunca_observado(self):
        assert frecuencia_historica(_HIST, 999) == 0.0

    def test_historico_vacio_no_divide_por_cero(self):
        assert frecuencia_historica([], 7) == 0.0


class TestFrecuenciaEnVentana:
    def test_ventana_menor_que_historico(self):
        assert frecuencia_en_ventana(_HIST, 7, 2) == 0.5  # sorteos 3,4 -> 7 en sorteo 3

    def test_ventana_mayor_que_historico_usa_todo_lo_disponible(self):
        assert frecuencia_en_ventana(_HIST, 7, 50) == frecuencia_historica(_HIST, 7)

    def test_ventana_sobre_historico_vacio(self):
        assert frecuencia_en_ventana([], 7, 10) == 0.0

    def test_nunca_completa_con_futuro(self):
        """Con ventana=10 sobre un historico de 4, el resultado debe
        ser identico a usar el historico completo -nunca debe
        aparecer un quinto sorteo inventado."""
        assert frecuencia_en_ventana(_HIST, 30, 10) == frecuencia_historica(_HIST, 30)


class TestSorteosDesdeUltimaAparicion:
    def test_penultimo_sorteo(self):
        assert sorteos_desde_ultima_aparicion(_HIST, 7) == 1

    def test_ultimo_sorteo_distancia_cero(self):
        assert sorteos_desde_ultima_aparicion(_HIST, 30) == 0

    def test_nunca_observado_devuelve_none(self):
        assert sorteos_desde_ultima_aparicion(_HIST, 999) is None

    def test_historico_vacio_devuelve_none(self):
        assert sorteos_desde_ultima_aparicion([], 7) is None


class TestAparecioEnSorteoAnterior:
    def test_aparece_en_el_ultimo_sorteo(self):
        assert aparecio_en_sorteo_anterior(_HIST, 30) == 1

    def test_no_aparece_en_el_ultimo_sorteo(self):
        assert aparecio_en_sorteo_anterior(_HIST, 7) == 0

    def test_historico_vacio_es_cero_no_excepcion(self):
        assert aparecio_en_sorteo_anterior([], 7) == 0
