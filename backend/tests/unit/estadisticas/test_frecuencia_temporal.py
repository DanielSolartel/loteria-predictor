"""
Tests de `application/estadisticas/motor/frecuencia_temporal.py`.

Dataset de referencia (verificado independientemente con
`collections.Counter` puro, sin usar ninguna función del motor, antes
de escribir estos tests):

    S1: 2023-03-05 (domingo), numeros=(1,2,3), sb=9
    S2: 2023-03-12 (domingo), numeros=(1,4,5), sb=9
    S3: 2024-03-01 (viernes), numeros=(2,3,6), sb=7
    S4: 2024-06-01 (sabado),  numeros=(1,2,7), sb=9

Verificado a mano:
  - año 2023: sorteos {S1,S2}, conteo {1:2,2:1,3:1,4:1,5:1}
  - mes=3 (agregado entre años): sorteos {S1,S2,S3}, conteo
    {1:2,2:2,3:2,4:1,5:1,6:1}
  - dia_semana=domingo: sorteos {S1,S2}, conteo numeros igual al de
    2023 (coincide en este dataset), superbalota {9:2}
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.frecuencia_temporal import (
    calcular_frecuencia_colores_por_anio,
    calcular_frecuencia_colores_por_dia_semana,
    calcular_frecuencia_colores_por_mes,
    calcular_frecuencia_numeros_por_anio,
    calcular_frecuencia_numeros_por_dia_semana,
    calcular_frecuencia_numeros_por_mes,
    calcular_frecuencia_pares_numero_color_por_anio,
    calcular_frecuencia_pares_numero_color_por_dia_semana,
    calcular_frecuencia_pares_numero_color_por_mes,
    calcular_frecuencia_superbalota_por_anio,
    calcular_frecuencia_superbalota_por_dia_semana,
    calcular_frecuencia_superbalota_por_mes,
)
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico


def _num(numero_sorteo: int, numeros: tuple[int, ...], fecha: date, dia_semana: str, superbalota: int | None = None) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=fecha, dia_semana=dia_semana, numeros=numeros, superbalota=superbalota,
    )


def _cl(numero_sorteo: int, pares: tuple[tuple[int, str], ...], fecha: date, dia_semana: str) -> ResultadoColorLoto:
    return ResultadoColorLoto(numero_sorteo=numero_sorteo, fecha=fecha, dia_semana=dia_semana, pares=pares)


_DATASET = [
    _num(1, (1, 2, 3), date(2023, 3, 5), "domingo", superbalota=9),
    _num(2, (1, 4, 5), date(2023, 3, 12), "domingo", superbalota=9),
    _num(3, (2, 3, 6), date(2024, 3, 1), "viernes", superbalota=7),
    _num(4, (1, 2, 7), date(2024, 6, 1), "sabado", superbalota=9),
]

_DATASET_CL = [
    _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "AZUL")), date(2023, 3, 5), "domingo"),
    _cl(2, ((1, "ROJO"), (4, "AZUL"), (5, "VERDE")), date(2023, 3, 12), "domingo"),
    _cl(3, ((2, "AZUL"), (3, "AZUL"), (6, "VERDE")), date(2024, 3, 1), "viernes"),
    _cl(4, ((1, "ROJO"), (2, "AZUL"), (7, "VERDE")), date(2024, 6, 1), "sabado"),
]


def _por_valor(filas: list[FrecuenciaObservada]) -> dict[str, FrecuenciaObservada]:
    return {f.valor: f for f in filas}


class TestFrecuenciaNumerosPorAnio:
    def test_filtra_correctamente_por_anio(self):
        filas = calcular_frecuencia_numeros_por_anio(_DATASET, rango_min=1, rango_max=7, anio=2023)
        por_valor = _por_valor(filas)
        assert por_valor["1"].apariciones == 2
        assert por_valor["2"].apariciones == 1
        assert por_valor["6"].apariciones == 0
        assert por_valor["7"].apariciones == 0

    def test_total_sorteos_es_el_subconjunto_no_el_historico_completo(self):
        filas = calcular_frecuencia_numeros_por_anio(_DATASET, rango_min=1, rango_max=7, anio=2023)
        assert all(f.total_sorteos == 2 for f in filas)

    def test_frecuencia_relativa_respecto_al_subconjunto(self):
        filas = calcular_frecuencia_numeros_por_anio(_DATASET, rango_min=1, rango_max=7, anio=2023)
        assert _por_valor(filas)["1"].frecuencia_relativa == 1.0

    def test_anio_sin_sorteos(self):
        filas = calcular_frecuencia_numeros_por_anio(_DATASET, rango_min=1, rango_max=7, anio=1999)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_dataset_vacio(self):
        filas = calcular_frecuencia_numeros_por_anio([], rango_min=1, rango_max=7, anio=2023)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_un_solo_sorteo(self):
        filas = calcular_frecuencia_numeros_por_anio([_DATASET[0]], rango_min=1, rango_max=7, anio=2023)
        assert _por_valor(filas)["1"].apariciones == 1
        assert all(f.total_sorteos == 1 for f in filas)

    def test_numero_nunca_observado_en_el_subconjunto(self):
        filas = calcular_frecuencia_numeros_por_anio(_DATASET, rango_min=1, rango_max=7, anio=2023)
        assert _por_valor(filas)["7"].apariciones == 0

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET[3], _DATASET[0], _DATASET[2], _DATASET[1]]
        f1 = calcular_frecuencia_numeros_por_anio(_DATASET, rango_min=1, rango_max=7, anio=2023)
        f2 = calcular_frecuencia_numeros_por_anio(desordenado, rango_min=1, rango_max=7, anio=2023)
        assert f1 == f2

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_frecuencia_numeros_por_anio(_DATASET, rango_min=1, rango_max=7, anio=2023)
        assert _DATASET == copia

    def test_huecos_en_numero_sorteo_no_afectan_el_filtro_por_fecha(self):
        dataset_con_hueco = [
            _num(1, (5,), date(2023, 1, 1), "domingo"),
            _num(100, (5,), date(2023, 6, 1), "jueves"),
        ]
        filas = calcular_frecuencia_numeros_por_anio(dataset_con_hueco, rango_min=1, rango_max=10, anio=2023)
        assert _por_valor(filas)["5"].apariciones == 2

    def test_hasta_numero_sorteo_y_anti_fuga(self):
        resultado_n = calcular_frecuencia_numeros_por_anio(
            _DATASET, rango_min=1, rango_max=7, anio=2023, hasta_numero_sorteo=1,
        )
        ampliado = _DATASET + [_num(5, (1, 2), date(2023, 3, 20), "lunes")]
        resultado_n_ampliado = calcular_frecuencia_numeros_por_anio(
            ampliado, rango_min=1, rango_max=7, anio=2023, hasta_numero_sorteo=1,
        )
        assert resultado_n == resultado_n_ampliado
        assert all(f.total_sorteos == 1 for f in resultado_n)


class TestFrecuenciaNumerosPorMes:
    def test_mes_agrega_entre_anios(self):
        filas = calcular_frecuencia_numeros_por_mes(_DATASET, rango_min=1, rango_max=7, mes=3)
        assert all(f.total_sorteos == 3 for f in filas)
        por_valor = _por_valor(filas)
        assert por_valor["1"].apariciones == 2
        assert por_valor["2"].apariciones == 2
        assert por_valor["3"].apariciones == 2
        assert por_valor["6"].apariciones == 1

    def test_mes_sin_sorteos(self):
        filas = calcular_frecuencia_numeros_por_mes(_DATASET, rango_min=1, rango_max=7, mes=12)
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_mes_fuera_de_rango_lanza_value_error(self):
        with pytest.raises(ValueError, match="entre 1 y 12"):
            calcular_frecuencia_numeros_por_mes(_DATASET, rango_min=1, rango_max=7, mes=13)
        with pytest.raises(ValueError):
            calcular_frecuencia_numeros_por_mes(_DATASET, rango_min=1, rango_max=7, mes=0)

    def test_no_crea_dimension_anio_mes(self):
        filas = calcular_frecuencia_numeros_por_mes(_DATASET, rango_min=1, rango_max=7, mes=3)
        assert _por_valor(filas)["3"].apariciones == 2

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_frecuencia_numeros_por_mes(_DATASET, rango_min=1, rango_max=7, mes=3)
        assert _DATASET == copia

    def test_anti_fuga(self):
        resultado_n = calcular_frecuencia_numeros_por_mes(
            _DATASET, rango_min=1, rango_max=7, mes=3, hasta_numero_sorteo=2,
        )
        ampliado = _DATASET + [_num(5, (1,), date(2025, 3, 1), "sabado")]
        resultado_n_ampliado = calcular_frecuencia_numeros_por_mes(
            ampliado, rango_min=1, rango_max=7, mes=3, hasta_numero_sorteo=2,
        )
        assert resultado_n == resultado_n_ampliado


class TestFrecuenciaNumerosPorDiaSemana:
    def test_filtra_correctamente(self):
        filas = calcular_frecuencia_numeros_por_dia_semana(_DATASET, rango_min=1, rango_max=7, dia_semana="domingo")
        assert all(f.total_sorteos == 2 for f in filas)
        assert _por_valor(filas)["1"].apariciones == 2

    def test_diferentes_dias_de_semana_dan_resultados_distintos(self):
        domingo = calcular_frecuencia_numeros_por_dia_semana(_DATASET, rango_min=1, rango_max=7, dia_semana="domingo")
        viernes = calcular_frecuencia_numeros_por_dia_semana(_DATASET, rango_min=1, rango_max=7, dia_semana="viernes")
        assert domingo != viernes
        assert all(f.total_sorteos == 1 for f in viernes)

    def test_dia_semana_sin_sorteos(self):
        filas = calcular_frecuencia_numeros_por_dia_semana(_DATASET, rango_min=1, rango_max=7, dia_semana="martes")
        assert all(f.apariciones == 0 and f.total_sorteos == 0 for f in filas)

    def test_dia_semana_invalido_lanza_value_error(self):
        with pytest.raises(ValueError, match="no es un valor válido"):
            calcular_frecuencia_numeros_por_dia_semana(_DATASET, rango_min=1, rango_max=7, dia_semana="funday")

    def test_vocabulario_exacto_del_dominio_sin_tildes(self):
        filas = calcular_frecuencia_numeros_por_dia_semana(_DATASET, rango_min=1, rango_max=7, dia_semana="sabado")
        assert all(f.total_sorteos == 1 for f in filas)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_frecuencia_numeros_por_dia_semana(_DATASET, rango_min=1, rango_max=7, dia_semana="domingo")
        assert _DATASET == copia

    def test_anti_fuga(self):
        resultado_n = calcular_frecuencia_numeros_por_dia_semana(
            _DATASET, rango_min=1, rango_max=7, dia_semana="domingo", hasta_numero_sorteo=1,
        )
        ampliado = _DATASET + [_num(5, (1,), date(2025, 1, 1), "domingo")]
        resultado_n_ampliado = calcular_frecuencia_numeros_por_dia_semana(
            ampliado, rango_min=1, rango_max=7, dia_semana="domingo", hasta_numero_sorteo=1,
        )
        assert resultado_n == resultado_n_ampliado


class TestFrecuenciaSuperbalotaTemporal:
    def test_por_anio(self):
        filas = calcular_frecuencia_superbalota_por_anio(_DATASET, rango_min=1, rango_max=16, anio=2023)
        assert _por_valor(filas)["9"].apariciones == 2

    def test_por_mes_agrega_entre_anios(self):
        filas = calcular_frecuencia_superbalota_por_mes(_DATASET, rango_min=1, rango_max=16, mes=3)
        por_valor = _por_valor(filas)
        assert por_valor["9"].apariciones == 2
        assert por_valor["7"].apariciones == 1

    def test_por_dia_semana(self):
        filas = calcular_frecuencia_superbalota_por_dia_semana(_DATASET, rango_min=1, rango_max=16, dia_semana="domingo")
        assert _por_valor(filas)["9"].apariciones == 2

    def test_superbalota_no_observada_en_el_subconjunto(self):
        filas = calcular_frecuencia_superbalota_por_dia_semana(_DATASET, rango_min=1, rango_max=16, dia_semana="viernes")
        assert _por_valor(filas)["9"].apariciones == 0

    def test_reutiliza_calcular_frecuencia_superbalota_no_reimplementa_el_conteo(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_superbalota
        subconjunto_manual = [r for r in _DATASET if r.fecha.year == 2023]
        esperado = calcular_frecuencia_superbalota(subconjunto_manual, 1, 16)
        real = calcular_frecuencia_superbalota_por_anio(_DATASET, rango_min=1, rango_max=16, anio=2023)
        assert esperado == real

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_frecuencia_superbalota_por_anio(_DATASET, rango_min=1, rango_max=16, anio=2023)
        assert _DATASET == copia


class TestFrecuenciaColoresTemporal:
    def test_por_anio(self):
        filas = calcular_frecuencia_colores_por_anio(_DATASET_CL, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2023)
        por_valor = _por_valor(filas)
        assert por_valor["ROJO"].apariciones == 3
        assert all(f.total_sorteos == 2 for f in filas)

    def test_por_mes_agrega_entre_anios(self):
        filas = calcular_frecuencia_colores_por_mes(_DATASET_CL, colores_vigentes=["ROJO", "AZUL", "VERDE"], mes=3)
        assert all(f.total_sorteos == 3 for f in filas)

    def test_por_dia_semana(self):
        filas = calcular_frecuencia_colores_por_dia_semana(_DATASET_CL, colores_vigentes=["ROJO", "AZUL", "VERDE"], dia_semana="domingo")
        assert all(f.total_sorteos == 2 for f in filas)

    def test_color_nunca_observado_en_el_subconjunto(self):
        filas = calcular_frecuencia_colores_por_dia_semana(_DATASET_CL, colores_vigentes=["ROJO", "AZUL", "VERDE"], dia_semana="viernes")
        assert _por_valor(filas)["ROJO"].apariciones == 0

    def test_color_no_vigente_no_se_pierde(self):
        dataset = [_cl(1, ((1, "MORADO"),), date(2023, 1, 1), "domingo")]
        filas = calcular_frecuencia_colores_por_anio(dataset, colores_vigentes=["ROJO"], anio=2023)
        assert "MORADO" in {f.valor for f in filas}

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_CL)
        calcular_frecuencia_colores_por_anio(_DATASET_CL, colores_vigentes=["ROJO", "AZUL"], anio=2023)
        assert _DATASET_CL == copia

    def test_anti_fuga(self):
        resultado_n = calcular_frecuencia_colores_por_anio(
            _DATASET_CL, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2023, hasta_numero_sorteo=1,
        )
        ampliado = _DATASET_CL + [_cl(5, ((1, "ROJO"),), date(2023, 3, 20), "lunes")]
        resultado_n_ampliado = calcular_frecuencia_colores_por_anio(
            ampliado, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2023, hasta_numero_sorteo=1,
        )
        assert resultado_n == resultado_n_ampliado


class TestFrecuenciaParesNumeroColorTemporal:
    def test_por_anio(self):
        filas = calcular_frecuencia_pares_numero_color_por_anio(
            _DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2023,
        )
        por_valor = _por_valor(filas)
        assert por_valor["1-ROJO"].apariciones == 2

    def test_par_nunca_observado_en_el_subconjunto(self):
        filas = calcular_frecuencia_pares_numero_color_por_anio(
            _DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2023,
        )
        assert _por_valor(filas)["6-VERDE"].apariciones == 0

    def test_por_mes_agrega_entre_anios(self):
        filas = calcular_frecuencia_pares_numero_color_por_mes(
            _DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"], mes=3,
        )
        assert all(f.total_sorteos == 3 for f in filas)

    def test_por_dia_semana(self):
        filas = calcular_frecuencia_pares_numero_color_por_dia_semana(
            _DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"], dia_semana="domingo",
        )
        assert all(f.total_sorteos == 2 for f in filas)

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_cl(1, ((99, "ROJO"),), date(2023, 1, 1), "domingo")]
        with pytest.raises(ValueError, match="99"):
            calcular_frecuencia_pares_numero_color_por_anio(
                dataset, rango_min=1, rango_max=7, colores_vigentes=["ROJO"], anio=2023,
            )

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_CL)
        calcular_frecuencia_pares_numero_color_por_anio(
            _DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2023,
        )
        assert _DATASET_CL == copia

    def test_anti_fuga(self):
        resultado_n = calcular_frecuencia_pares_numero_color_por_anio(
            _DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2023,
            hasta_numero_sorteo=1,
        )
        ampliado = _DATASET_CL + [_cl(5, ((1, "ROJO"),), date(2023, 3, 20), "lunes")]
        resultado_n_ampliado = calcular_frecuencia_pares_numero_color_por_anio(
            ampliado, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2023,
            hasta_numero_sorteo=1,
        )
        assert resultado_n == resultado_n_ampliado


class TestReutilizacionSinReimplementarConteo:
    def test_numeros_coincide_con_llamada_manual_a_calcular_frecuencia_numeros(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros
        subconjunto_manual = [r for r in _DATASET if r.fecha.month == 3]
        esperado = calcular_frecuencia_numeros(subconjunto_manual, 1, 7)
        real = calcular_frecuencia_numeros_por_mes(_DATASET, rango_min=1, rango_max=7, mes=3)
        assert esperado == real

    def test_colores_coincide_con_llamada_manual_a_calcular_frecuencia_colores(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        subconjunto_manual = [r for r in _DATASET_CL if r.dia_semana == "domingo"]
        esperado = calcular_frecuencia_colores(subconjunto_manual, ["ROJO", "AZUL", "VERDE"])
        real = calcular_frecuencia_colores_por_dia_semana(
            _DATASET_CL, colores_vigentes=["ROJO", "AZUL", "VERDE"], dia_semana="domingo",
        )
        assert esperado == real

    def test_pares_numero_color_coincide_con_llamada_manual(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        subconjunto_manual = [r for r in _DATASET_CL if r.fecha.year == 2024]
        esperado = calcular_frecuencia_pares_numero_color(subconjunto_manual, 1, 7, ["ROJO", "AZUL", "VERDE"])
        real = calcular_frecuencia_pares_numero_color_por_anio(
            _DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"], anio=2024,
        )
        assert esperado == real
