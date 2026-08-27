"""
Tests de `application/estadisticas/motor/recencia.py`.

Dataset pequeño verificable a mano: 6 sorteos numéricos donde el
comportamiento reciente (últimos 2 sorteos) difiere claramente del
histórico completo -el número 9 solo aparece en los 2 sorteos
recientes, el número 1 solo en los 4 antiguos.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.recencia import (
    ComparacionRecencia,
    comparar_frecuencia_colores_por_ventana,
    comparar_frecuencia_numeros_colorloto_por_ventana,
    comparar_frecuencia_numeros_por_ventana,
    comparar_frecuencia_pares_numero_color_por_ventana,
    comparar_frecuencia_superbalota_por_ventana,
    tomar_ultimos_n_sorteos,
)
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico

_FECHA_BASE = date(2024, 1, 1)


def _num(numero_sorteo: int, numeros: tuple[int, ...], superbalota: int | None = None) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo), dia_semana="lunes",
        numeros=numeros, superbalota=superbalota,
    )


def _cl(numero_sorteo: int, pares: tuple[tuple[int, str], ...]) -> ResultadoColorLoto:
    return ResultadoColorLoto(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo), dia_semana="lunes",
        pares=pares,
    )


# 1 aparece solo en los 4 sorteos antiguos; 9 aparece solo en los 2 recientes.
_DATASET = [
    _num(1, (1, 2), superbalota=5),
    _num(2, (1, 3), superbalota=5),
    _num(3, (1, 4), superbalota=6),
    _num(4, (1, 2), superbalota=6),
    _num(5, (9, 3), superbalota=7),
    _num(6, (9, 4), superbalota=7),
]


def _por_valor(filas: list[ComparacionRecencia]) -> dict[str, ComparacionRecencia]:
    return {f.valor: f for f in filas}


class TestTomarUltimosNSorteos:
    def test_toma_exactamente_los_n_mas_recientes(self):
        resultado = tomar_ultimos_n_sorteos(_DATASET, n=2)
        assert [r.numero_sorteo for r in resultado] == [5, 6]

    def test_ventana_mas_grande_que_el_historico_devuelve_todo_sin_error(self):
        resultado = tomar_ultimos_n_sorteos(_DATASET, n=100)
        assert len(resultado) == 6
        assert [r.numero_sorteo for r in resultado] == [1, 2, 3, 4, 5, 6]

    def test_ventana_exacta_al_limite(self):
        resultado = tomar_ultimos_n_sorteos(_DATASET, n=6)
        assert len(resultado) == 6

    def test_no_asume_entrada_ordenada(self):
        desordenado = [_DATASET[4], _DATASET[0], _DATASET[5], _DATASET[2], _DATASET[1], _DATASET[3]]
        resultado = tomar_ultimos_n_sorteos(desordenado, n=2)
        assert [r.numero_sorteo for r in resultado] == [5, 6]

    def test_no_muta_la_entrada_original(self):
        desordenado = [_DATASET[4], _DATASET[0], _DATASET[5], _DATASET[2], _DATASET[1], _DATASET[3]]
        copia = list(desordenado)
        tomar_ultimos_n_sorteos(desordenado, n=2)
        assert desordenado == copia

    def test_hasta_numero_sorteo_filtra_antes_de_tomar_la_ventana(self):
        # Con corte en 4, los sorteos 5 y 6 no existen todavia -los
        # "ultimos 2" deben ser el 3 y el 4, no el 5 y el 6.
        resultado = tomar_ultimos_n_sorteos(_DATASET, n=2, hasta_numero_sorteo=4)
        assert [r.numero_sorteo for r in resultado] == [3, 4]

    def test_cero_sorteos(self):
        assert tomar_ultimos_n_sorteos([], n=10) == []

    def test_n_no_positivo_lanza_value_error(self):
        with pytest.raises(ValueError):
            tomar_ultimos_n_sorteos(_DATASET, n=0)
        with pytest.raises(ValueError):
            tomar_ultimos_n_sorteos(_DATASET, n=-1)


class TestCompararFrecuenciaNumerosPorVentana:
    def test_diferencia_clara_entre_historico_y_reciente(self):
        filas = comparar_frecuencia_numeros_por_ventana(
            _DATASET, rango_min=1, rango_max=9, ventana=2, etiqueta_ventana="ultimos_2",
        )
        por_valor = _por_valor(filas)

        # "1" aparece 4/6 en el historico, 0/2 en lo reciente
        fila_1 = por_valor["1"]
        assert fila_1.frecuencia_historica.apariciones == 4
        assert fila_1.frecuencia_historica.total_sorteos == 6
        assert fila_1.frecuencia_reciente.apariciones == 0
        assert fila_1.frecuencia_reciente.total_sorteos == 2
        assert fila_1.diferencia == pytest.approx(0 / 2 - 4 / 6)

        # "9" aparece 2/6 en el historico completo (sorteos 5 y 6 -que
        # tambien son parte del historico-) y 2/2 en lo reciente
        fila_9 = por_valor["9"]
        assert fila_9.frecuencia_historica.apariciones == 2
        assert fila_9.frecuencia_reciente.apariciones == 2
        assert fila_9.diferencia == pytest.approx(2 / 2 - 2 / 6)

    def test_frecuencia_historica_y_reciente_quedan_como_objetos_independientes(self):
        filas = comparar_frecuencia_numeros_por_ventana(
            _DATASET, rango_min=1, rango_max=9, ventana=2, etiqueta_ventana="ultimos_2",
        )
        fila = filas[0]
        assert isinstance(fila.frecuencia_historica, FrecuenciaObservada)
        assert isinstance(fila.frecuencia_reciente, FrecuenciaObservada)
        assert fila.frecuencia_historica is not fila.frecuencia_reciente

    def test_etiqueta_ventana_se_preserva_tal_cual(self):
        filas = comparar_frecuencia_numeros_por_ventana(
            _DATASET, rango_min=1, rango_max=9, ventana=2, etiqueta_ventana="mi_etiqueta_personalizada",
        )
        assert all(f.ventana == "mi_etiqueta_personalizada" for f in filas)

    def test_incluye_todo_el_rango_incluso_numeros_nunca_aparecidos(self):
        filas = comparar_frecuencia_numeros_por_ventana(
            _DATASET, rango_min=1, rango_max=9, ventana=2, etiqueta_ventana="ultimos_2",
        )
        assert len(filas) == 9
        fila_7 = _por_valor(filas)["7"]
        assert fila_7.frecuencia_historica.apariciones == 0
        assert fila_7.frecuencia_reciente.apariciones == 0

    def test_ventana_mayor_al_historico_no_falla(self):
        filas = comparar_frecuencia_numeros_por_ventana(
            _DATASET, rango_min=1, rango_max=9, ventana=1000, etiqueta_ventana="todo",
        )
        # con ventana >= historico completo, ambas frecuencias deben coincidir
        for f in filas:
            assert f.frecuencia_historica.apariciones == f.frecuencia_reciente.apariciones
            assert f.diferencia == pytest.approx(0.0)

    def test_cero_sorteos_no_falla(self):
        filas = comparar_frecuencia_numeros_por_ventana(
            [], rango_min=1, rango_max=5, ventana=10, etiqueta_ventana="ultimos_10",
        )
        assert len(filas) == 5
        assert all(f.frecuencia_historica.apariciones == 0 and f.frecuencia_reciente.apariciones == 0 for f in filas)

    def test_no_muta_la_entrada_original(self):
        copia = list(_DATASET)
        comparar_frecuencia_numeros_por_ventana(
            _DATASET, rango_min=1, rango_max=9, ventana=2, etiqueta_ventana="ultimos_2",
        )
        assert _DATASET == copia

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset_invalido = [_num(1, (1, 99))]
        with pytest.raises(ValueError):
            comparar_frecuencia_numeros_por_ventana(
                dataset_invalido, rango_min=1, rango_max=9, ventana=1, etiqueta_ventana="ultimos_1",
            )


class TestPropiedadAntiFuga:
    def test_agregar_sorteos_futuros_no_cambia_una_ventana_ya_calculada_con_corte_fijo(self):
        resultado_n = comparar_frecuencia_numeros_por_ventana(
            _DATASET, rango_min=1, rango_max=9, ventana=2, etiqueta_ventana="ultimos_2",
            hasta_numero_sorteo=6,
        )

        dataset_ampliado = _DATASET + [
            _num(7, (9, 9), superbalota=1), _num(8, (1, 1), superbalota=2),
        ]
        resultado_n_ampliado = comparar_frecuencia_numeros_por_ventana(
            dataset_ampliado, rango_min=1, rango_max=9, ventana=2, etiqueta_ventana="ultimos_2",
            hasta_numero_sorteo=6,
        )

        assert resultado_n == resultado_n_ampliado

    def test_anti_fuga_superbalota(self):
        resultado_n = comparar_frecuencia_superbalota_por_ventana(
            _DATASET, rango_min=1, rango_max=16, ventana=2, etiqueta_ventana="ultimos_2",
            hasta_numero_sorteo=4,
        )
        dataset_ampliado = _DATASET + [_num(7, (1, 2), superbalota=15)]
        resultado_n_ampliado = comparar_frecuencia_superbalota_por_ventana(
            dataset_ampliado, rango_min=1, rango_max=16, ventana=2, etiqueta_ventana="ultimos_2",
            hasta_numero_sorteo=4,
        )
        assert resultado_n == resultado_n_ampliado

    def test_anti_fuga_colorloto(self):
        dataset_cl = [_cl(1, ((1, "ROJO"),)), _cl(2, ((2, "AZUL"),)), _cl(3, ((3, "VERDE"),))]
        resultado_n = comparar_frecuencia_numeros_colorloto_por_ventana(
            dataset_cl, rango_min=1, rango_max=7, ventana=2, etiqueta_ventana="ultimos_2",
            hasta_numero_sorteo=2,
        )
        dataset_ampliado = dataset_cl + [_cl(4, ((4, "AMARILLO"),))]
        resultado_n_ampliado = comparar_frecuencia_numeros_colorloto_por_ventana(
            dataset_ampliado, rango_min=1, rango_max=7, ventana=2, etiqueta_ventana="ultimos_2",
            hasta_numero_sorteo=2,
        )
        assert resultado_n == resultado_n_ampliado


class TestCompararFrecuenciaSuperbalotaPorVentana:
    def test_pool_independiente_del_principal(self):
        filas_numeros = comparar_frecuencia_numeros_por_ventana(
            _DATASET, rango_min=1, rango_max=9, ventana=2, etiqueta_ventana="ultimos_2",
        )
        filas_superbalota = comparar_frecuencia_superbalota_por_ventana(
            _DATASET, rango_min=1, rango_max=16, ventana=2, etiqueta_ventana="ultimos_2",
        )
        # "7" es superbalota en los 2 sorteos recientes, y tambien
        # podria aparecer como numero -deben ser calculos independientes
        fila_7_sb = _por_valor(filas_superbalota)["7"]
        assert fila_7_sb.frecuencia_reciente.apariciones == 2  # sorteos 5 y 6 tienen superbalota=7

    def test_superbalota_ausente_no_rompe_el_calculo(self):
        dataset_con_ausente = _DATASET + [_num(7, (1, 2), superbalota=None)]
        filas = comparar_frecuencia_superbalota_por_ventana(
            dataset_con_ausente, rango_min=1, rango_max=16, ventana=2, etiqueta_ventana="ultimos_2",
        )
        assert len(filas) == 16  # no revienta


class TestCompararFrecuenciaColoresPorVentana:
    def test_diferencia_de_color_entre_historico_y_reciente(self):
        dataset_cl = [
            _cl(1, ((1, "ROJO"), (2, "ROJO"))),
            _cl(2, ((1, "ROJO"), (2, "ROJO"))),
            _cl(3, ((1, "AZUL"), (2, "AZUL"))),
        ]
        filas = comparar_frecuencia_colores_por_ventana(
            dataset_cl, colores_vigentes=["ROJO", "AZUL"], ventana=1, etiqueta_ventana="ultimos_1",
        )
        por_valor = _por_valor(filas)
        assert por_valor["ROJO"].frecuencia_historica.apariciones == 4
        assert por_valor["ROJO"].frecuencia_reciente.apariciones == 0
        assert por_valor["AZUL"].frecuencia_reciente.apariciones == 2

    def test_color_no_vigente_pero_observado_no_se_pierde(self):
        dataset_cl = [_cl(1, ((1, "MORADO"),))]
        filas = comparar_frecuencia_colores_por_ventana(
            dataset_cl, colores_vigentes=["ROJO"], ventana=1, etiqueta_ventana="ultimos_1",
        )
        assert "MORADO" in _por_valor(filas)


class TestCompararFrecuenciaParesNumeroColorPorVentana:
    # Dataset: 4 sorteos, donde el par (2,ROJO) solo aparece en los 2
    # ultimos (recientes), y (3,AZUL) solo aparece en los 2 primeros
    # (historico antiguo, ausente de lo reciente).
    _DATASET = [
        _cl(1, ((3, "AZUL"), (5, "VERDE"))),
        _cl(2, ((3, "AZUL"), (6, "VERDE"))),
        _cl(3, ((2, "ROJO"), (7, "VERDE"))),
        _cl(4, ((2, "ROJO"), (5, "VERDE"))),
    ]

    def test_diferencia_clara_entre_historico_y_reciente(self):
        filas = comparar_frecuencia_pares_numero_color_por_ventana(
            self._DATASET, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=2, etiqueta_ventana="ultimos_2",
        )
        por_valor = {f.valor: f for f in filas}

        fila_2_rojo = por_valor["2-ROJO"]
        assert fila_2_rojo.frecuencia_historica.apariciones == 2  # S3 y S4 (dentro de los 4 sorteos historicos)
        assert fila_2_rojo.frecuencia_reciente.apariciones == 2   # tambien en los 2 recientes (S3,S4)

        fila_3_azul = por_valor["3-AZUL"]
        assert fila_3_azul.frecuencia_historica.apariciones == 2  # S1 y S2
        assert fila_3_azul.frecuencia_reciente.apariciones == 0   # ausente de los 2 recientes (S3,S4)

    def test_frecuencia_historica_y_reciente_quedan_como_objetos_independientes(self):
        filas = comparar_frecuencia_pares_numero_color_por_ventana(
            self._DATASET, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=2, etiqueta_ventana="ultimos_2",
        )
        fila = filas[0]
        assert isinstance(fila.frecuencia_historica, FrecuenciaObservada)
        assert isinstance(fila.frecuencia_reciente, FrecuenciaObservada)
        assert fila.frecuencia_historica is not fila.frecuencia_reciente

    def test_etiqueta_ventana_se_preserva(self):
        filas = comparar_frecuencia_pares_numero_color_por_ventana(
            self._DATASET, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=2, etiqueta_ventana="mi_etiqueta",
        )
        assert all(f.ventana == "mi_etiqueta" for f in filas)

    def test_ventana_mayor_al_historico_no_falla(self):
        filas = comparar_frecuencia_pares_numero_color_por_ventana(
            self._DATASET, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=1000, etiqueta_ventana="todo",
        )
        for f in filas:
            assert f.frecuencia_historica.apariciones == f.frecuencia_reciente.apariciones
            assert f.diferencia == pytest.approx(0.0)

    def test_cero_sorteos_no_falla(self):
        filas = comparar_frecuencia_pares_numero_color_por_ventana(
            [], rango_min=1, rango_max=3, colores_vigentes=["ROJO"], ventana=10, etiqueta_ventana="ultimos_10",
        )
        assert all(f.frecuencia_historica.apariciones == 0 and f.frecuencia_reciente.apariciones == 0 for f in filas)

    def test_no_muta_la_entrada(self):
        copia = list(self._DATASET)
        comparar_frecuencia_pares_numero_color_por_ventana(
            self._DATASET, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=2, etiqueta_ventana="ultimos_2",
        )
        assert self._DATASET == copia

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset_invalido = [_cl(1, ((99, "ROJO"),))]
        with pytest.raises(ValueError):
            comparar_frecuencia_pares_numero_color_por_ventana(
                dataset_invalido, rango_min=1, rango_max=7, colores_vigentes=["ROJO"],
                ventana=1, etiqueta_ventana="ultimos_1",
            )

    def test_anti_fuga(self):
        resultado_n = comparar_frecuencia_pares_numero_color_por_ventana(
            self._DATASET, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=2, etiqueta_ventana="ultimos_2", hasta_numero_sorteo=4,
        )
        ampliado = self._DATASET + [_cl(5, ((2, "ROJO"), (3, "AZUL")))]
        resultado_n_ampliado = comparar_frecuencia_pares_numero_color_por_ventana(
            ampliado, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=2, etiqueta_ventana="ultimos_2", hasta_numero_sorteo=4,
        )
        assert resultado_n == resultado_n_ampliado

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [self._DATASET[2], self._DATASET[0], self._DATASET[3], self._DATASET[1]]
        f1 = comparar_frecuencia_pares_numero_color_por_ventana(
            self._DATASET, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=2, etiqueta_ventana="ultimos_2",
        )
        f2 = comparar_frecuencia_pares_numero_color_por_ventana(
            desordenado, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL", "VERDE"],
            ventana=2, etiqueta_ventana="ultimos_2",
        )
        assert sorted(f1, key=lambda f: f.valor) == sorted(f2, key=lambda f: f.valor)
