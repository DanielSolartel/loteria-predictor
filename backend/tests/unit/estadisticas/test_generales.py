"""
Tests de `application/estadisticas/motor/generales.py`.

Dataset de referencia armado a mano (verificable por inspección, no
por herramientas externas): 4 sorteos de un juego numérico genérico,
cubriendo 2 años, 3 meses y 3 días de la semana distintos, con un
hueco deliberado en la numeración (falta el sorteo 3).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.application.estadisticas.motor.generales import (
    calcular_frecuencia_sorteos_por_anio,
    calcular_frecuencia_sorteos_por_dia_semana,
    calcular_frecuencia_sorteos_por_mes,
    calcular_resumen_general,
    detectar_huecos_serie_historica,
    validar_consistencia_temporal,
)
from app.application.estadisticas.tipos import ResultadoNumerico


def _resultado(numero_sorteo: int, fecha: date, dia_semana: str) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=fecha, dia_semana=dia_semana,
        numeros=(1, 2, 3, 4, 5), superbalota=None,
    )


# Sorteo 3 deliberadamente ausente -hueco en la numeración.
_DATASET = [
    _resultado(1, date(2023, 12, 28), "jueves"),
    _resultado(2, date(2024, 1, 4), "jueves"),
    _resultado(4, date(2024, 2, 15), "jueves"),
    _resultado(5, date(2024, 3, 1), "viernes"),
]


class TestCalcularResumenGeneral:
    def test_lista_vacia_no_falla_y_todo_queda_en_none(self):
        r = calcular_resumen_general([], juego_codigo="MILOTO")
        assert r.total_sorteos == 0
        assert r.primer_sorteo_numero is None
        assert r.primer_sorteo_fecha is None
        assert r.ultimo_sorteo_numero is None
        assert r.ultimo_sorteo_fecha is None
        assert r.numero_sorteo_minimo is None
        assert r.numero_sorteo_maximo is None

    def test_un_solo_sorteo(self):
        r = calcular_resumen_general([_DATASET[0]], juego_codigo="MILOTO")
        assert r.total_sorteos == 1
        assert r.primer_sorteo_numero == 1
        assert r.ultimo_sorteo_numero == 1
        assert r.numero_sorteo_minimo == 1
        assert r.numero_sorteo_maximo == 1

    def test_resumen_completo_con_varios_sorteos(self):
        r = calcular_resumen_general(_DATASET, juego_codigo="MILOTO")
        assert r.juego_codigo == "MILOTO"
        assert r.total_sorteos == 4
        assert r.primer_sorteo_numero == 1
        assert r.primer_sorteo_fecha == date(2023, 12, 28)
        assert r.ultimo_sorteo_numero == 5
        assert r.ultimo_sorteo_fecha == date(2024, 3, 1)
        assert r.numero_sorteo_minimo == 1
        assert r.numero_sorteo_maximo == 5

    def test_no_asume_que_la_entrada_ya_viene_ordenada(self):
        desordenado = [_DATASET[2], _DATASET[0], _DATASET[3], _DATASET[1]]
        r = calcular_resumen_general(desordenado, juego_codigo="MILOTO")
        assert r.primer_sorteo_numero == 1
        assert r.ultimo_sorteo_numero == 5


class TestFrecuenciaSorteosPorAnio:
    def test_lista_vacia(self):
        assert calcular_frecuencia_sorteos_por_anio([]) == []

    def test_conteo_exacto_por_anio(self):
        filas = calcular_frecuencia_sorteos_por_anio(_DATASET)
        por_valor = {f.valor: f for f in filas}
        assert por_valor["2023"].apariciones == 1
        assert por_valor["2024"].apariciones == 3
        assert por_valor["2023"].total_sorteos == 4
        assert por_valor["2024"].frecuencia_relativa == 3 / 4

    def test_no_incluye_anios_sin_sorteos(self):
        filas = calcular_frecuencia_sorteos_por_anio(_DATASET)
        valores = {f.valor for f in filas}
        assert valores == {"2023", "2024"}


class TestFrecuenciaSorteosPorMes:
    def test_conteo_exacto_por_mes(self):
        filas = calcular_frecuencia_sorteos_por_mes(_DATASET)
        por_valor = {f.valor: f.apariciones for f in filas}
        assert por_valor == {"12": 1, "1": 1, "2": 1, "3": 1}

    def test_agrega_across_anios_no_por_combinacion_anio_mes(self):
        dataset_repetido = _DATASET + [_resultado(6, date(2025, 1, 20), "lunes")]
        filas = calcular_frecuencia_sorteos_por_mes(dataset_repetido)
        por_valor = {f.valor: f.apariciones for f in filas}
        assert por_valor["1"] == 2  # enero 2024 + enero 2025, agregados


class TestFrecuenciaSorteosPorDiaSemana:
    def test_conteo_exacto_y_usa_el_literal_de_dia_semana_tal_cual(self):
        filas = calcular_frecuencia_sorteos_por_dia_semana(_DATASET)
        por_valor = {f.valor: f.apariciones for f in filas}
        assert por_valor == {"jueves": 3, "viernes": 1}


class TestDetectarHuecosSerieHistorica:
    def test_lista_vacia_no_divide_por_cero(self):
        r = detectar_huecos_serie_historica([])
        assert r.total_esperado == 0
        assert r.total_presente == 0
        assert r.huecos == ()
        assert r.porcentaje_cobertura == 0.0

    def test_sin_huecos_cobertura_100(self):
        r = detectar_huecos_serie_historica([1, 2, 3, 4, 5])
        assert r.huecos == ()
        assert r.porcentaje_cobertura == 100.0

    def test_detecta_el_hueco_exacto(self):
        r = detectar_huecos_serie_historica([1, 2, 4, 5])
        assert r.total_esperado == 5
        assert r.total_presente == 4
        assert r.huecos == (3,)
        assert r.porcentaje_cobertura == 80.0

    def test_deduplica_defensivamente(self):
        r = detectar_huecos_serie_historica([1, 2, 2, 3, 3, 3])
        assert r.total_esperado == 3
        assert r.total_presente == 3
        assert r.huecos == ()

    def test_un_solo_numero_sorteo(self):
        r = detectar_huecos_serie_historica([7])
        assert r.total_esperado == 1
        assert r.total_presente == 1
        assert r.huecos == ()
        assert r.porcentaje_cobertura == 100.0


class TestValidarConsistenciaTemporal:
    def test_lista_vacia_es_consistente(self):
        r = validar_consistencia_temporal([])
        assert r.es_consistente is True
        assert r.problemas == ()

    def test_un_solo_sorteo_es_consistente(self):
        r = validar_consistencia_temporal([_DATASET[0]])
        assert r.es_consistente is True

    def test_dataset_ordenado_correctamente_es_consistente(self):
        r = validar_consistencia_temporal(_DATASET)
        assert r.es_consistente is True
        assert r.problemas == ()

    def test_detecta_una_fecha_que_retrocede(self):
        roto = [
            _resultado(1, date(2024, 3, 1), "viernes"),
            _resultado(2, date(2024, 2, 1), "jueves"),  # retrocede respecto al 1
        ]
        r = validar_consistencia_temporal(roto)
        assert r.es_consistente is False
        assert len(r.problemas) == 1
        assert "2" in r.problemas[0] and "1" in r.problemas[0]

    def test_reporta_todas_las_violaciones_no_solo_la_primera(self):
        roto = [
            _resultado(1, date(2024, 3, 1), "viernes"),
            _resultado(2, date(2024, 2, 1), "jueves"),   # retrocede vs 1
            _resultado(3, date(2024, 1, 1), "lunes"),    # retrocede vs 2
        ]
        r = validar_consistencia_temporal(roto)
        assert r.es_consistente is False
        assert len(r.problemas) == 2

    def test_no_asume_orden_de_entrada(self):
        desordenado = [_DATASET[3], _DATASET[0], _DATASET[2], _DATASET[1]]
        r = validar_consistencia_temporal(desordenado)
        assert r.es_consistente is True
