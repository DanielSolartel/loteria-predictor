"""
Tests de `application/estadisticas/motor/atrasos.py`.

Dataset de referencia (verificado a mano en el diseño de la Etapa D,
consistente con el ejemplo del enunciado):

    S1: 1, 2
    S2: 3, 4
    S3: 1, 5
    S4: 2, 3

Referencia = numero_sorteo 4 (el máximo, si no se especifica corte).
Atrasos esperados: 1→1, 2→0, 3→0, 4→2, 5→1, 6→None (nunca observado).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.atrasos import (
    AtrasoObservado,
    calcular_atrasos_colores,
    calcular_atrasos_numeros,
    calcular_atrasos_numeros_colorloto,
    calcular_atrasos_pares_numero_color,
    calcular_atrasos_superbalota,
    calcular_intervalos_historicos_colores,
    calcular_intervalos_historicos_numeros,
    calcular_intervalos_historicos_numeros_colorloto,
    calcular_intervalos_historicos_pares_numero_color,
    calcular_intervalos_historicos_superbalota,
)
from app.application.estadisticas.tipos import IntervalosHistoricos, ResultadoColorLoto, ResultadoNumerico


from datetime import date, timedelta

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


# Dataset de referencia -rango 1..6, para poder incluir el "6" como
# nunca observado dentro del universo pedido.
_DATASET = [
    _num(1, (1, 2)),
    _num(2, (3, 4)),
    _num(3, (1, 5)),
    _num(4, (2, 3)),
]


def _por_valor(filas: list[AtrasoObservado]) -> dict[str, AtrasoObservado]:
    return {f.valor: f for f in filas}


class TestCalcularAtrasosNumerosDatasetDeReferencia:
    def test_atrasos_exactos_segun_el_dataset_verificado_a_mano(self):
        filas = calcular_atrasos_numeros(_DATASET, rango_min=1, rango_max=6)
        por_valor = _por_valor(filas)

        assert por_valor["1"].atraso == 1
        assert por_valor["2"].atraso == 0
        assert por_valor["3"].atraso == 0
        assert por_valor["4"].atraso == 2
        assert por_valor["5"].atraso == 1
        assert por_valor["6"].atraso is None

    def test_ultimo_sorteo_aparicion_correcto(self):
        filas = calcular_atrasos_numeros(_DATASET, rango_min=1, rango_max=6)
        por_valor = _por_valor(filas)

        assert por_valor["1"].ultimo_sorteo_aparicion == 3  # ultima vez: sorteo 3 (tambien salio en 1)
        assert por_valor["2"].ultimo_sorteo_aparicion == 4
        assert por_valor["6"].ultimo_sorteo_aparicion is None

    def test_total_sorteos_es_el_tamano_de_la_ventana(self):
        filas = calcular_atrasos_numeros(_DATASET, rango_min=1, rango_max=6)
        assert all(f.total_sorteos == 4 for f in filas)

    def test_usa_numero_sorteo_real_no_posicion_ordinal(self):
        """Diferencia crítica: si hubiera un hueco en la numeración,
        usar la posición ordinal subestimaría el atraso. Dataset:
        el numero 7 aparece en el sorteo 100; la referencia es el
        sorteo 105, pero en la LISTA solo hay 2 elementos (posiciones
        0 y 1). Si el cálculo usara posición ordinal, el atraso
        sería 1; con numero_sorteo real, debe ser 5."""
        dataset_con_hueco = [_num(100, (7,)), _num(105, (1,))]
        filas = calcular_atrasos_numeros(dataset_con_hueco, rango_min=1, rango_max=10)
        por_valor = _por_valor(filas)
        assert por_valor["7"].atraso == 5  # 105 - 100, NO "1" (que daría la posicion ordinal)
        assert por_valor["1"].atraso == 0


class TestCasosLimite:
    def test_cero_sorteos_todo_none(self):
        filas = calcular_atrasos_numeros([], rango_min=1, rango_max=5)
        assert len(filas) == 5
        assert all(f.atraso is None and f.ultimo_sorteo_aparicion is None for f in filas)
        assert all(f.total_sorteos == 0 for f in filas)

    def test_un_sorteo_lo_que_aparecio_atraso_cero_lo_demas_none(self):
        filas = calcular_atrasos_numeros([_num(1, (1, 2))], rango_min=1, rango_max=5)
        por_valor = _por_valor(filas)
        assert por_valor["1"].atraso == 0
        assert por_valor["2"].atraso == 0
        assert por_valor["3"].atraso is None

    def test_nunca_observado_no_es_menos_uno_ni_cero(self):
        filas = calcular_atrasos_numeros(_DATASET, rango_min=1, rango_max=6)
        fila_6 = _por_valor(filas)["6"]
        assert fila_6.atraso is None
        assert fila_6.atraso != -1
        assert fila_6.atraso != 0

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET[2], _DATASET[0], _DATASET[3], _DATASET[1]]
        filas_ordenado = calcular_atrasos_numeros(_DATASET, rango_min=1, rango_max=6)
        filas_desordenado = calcular_atrasos_numeros(desordenado, rango_min=1, rango_max=6)
        assert filas_ordenado == filas_desordenado

    def test_no_muta_la_lista_original(self):
        copia_referencia = list(_DATASET)
        desordenado = [_DATASET[2], _DATASET[0], _DATASET[3], _DATASET[1]]
        copia_antes = list(desordenado)
        calcular_atrasos_numeros(desordenado, rango_min=1, rango_max=6)
        assert desordenado == copia_antes
        assert _DATASET == copia_referencia

    def test_numero_fuera_de_rango_lanza_value_error_con_mensaje_util(self):
        dataset = [_num(1, (1, 2, 99))]
        with pytest.raises(ValueError, match="99"):
            calcular_atrasos_numeros(dataset, rango_min=1, rango_max=5)

    def test_hasta_numero_sorteo_menor_al_minimo_todo_none(self):
        filas = calcular_atrasos_numeros(_DATASET, rango_min=1, rango_max=6, hasta_numero_sorteo=0)
        assert all(f.atraso is None for f in filas)
        assert all(f.total_sorteos == 0 for f in filas)


class TestHastaNumeroSorteoFiltraDefensivamente:
    def test_sorteos_posteriores_al_corte_no_influyen_en_nada(self):
        filas_con_todo = calcular_atrasos_numeros(_DATASET, rango_min=1, rango_max=6, hasta_numero_sorteo=2)
        # Solo deben considerarse los sorteos 1 (1,2) y 2 (3,4)
        por_valor = _por_valor(filas_con_todo)
        assert por_valor["1"].atraso == 1  # referencia=2, ultima aparicion=1 (sorteo1)
        assert por_valor["2"].atraso == 1  # tambien aparece solo en sorteo1
        assert por_valor["3"].atraso == 0  # aparece en sorteo2 = referencia
        assert por_valor["4"].atraso == 0
        assert por_valor["5"].atraso is None  # aun no existe hasta el sorteo 2
        assert all(f.total_sorteos == 2 for f in filas_con_todo)

    def test_propiedad_anti_fuga_agregar_sorteos_futuros_no_cambia_el_resultado(self):
        resultado_n = calcular_atrasos_numeros(_DATASET, rango_min=1, rango_max=6, hasta_numero_sorteo=4)

        dataset_ampliado = _DATASET + [
            _num(5, (6, 1)), _num(6, (2, 2)), _num(7, (3, 4)), _num(8, (5, 6)), _num(9, (1, 3)),
        ]
        resultado_n_ampliado = calcular_atrasos_numeros(
            dataset_ampliado, rango_min=1, rango_max=6, hasta_numero_sorteo=4
        )

        assert resultado_n == resultado_n_ampliado


class TestCalcularAtrasosSuperbalota:
    def test_pool_independiente_del_principal(self):
        dataset = [_num(1, (1, 2, 3), superbalota=10), _num(2, (4, 5, 6), superbalota=9)]
        filas_numeros = calcular_atrasos_numeros(dataset, rango_min=1, rango_max=10)
        filas_superbalota = calcular_atrasos_superbalota(dataset, rango_min=1, rango_max=16)
        # "10" no debe aparecer influenciado por el pool de numeros ni viceversa
        assert _por_valor(filas_numeros)["10"].atraso is None  # 10 esta fuera del rango de numeros pedido...
        assert _por_valor(filas_superbalota)["10"].atraso == 1  # referencia=2, ultima aparicion sb=1

    def test_superbalota_ausente_no_cuenta_como_aparicion(self):
        dataset = [_num(1, (1, 2, 3), superbalota=10), _num(2, (4, 5, 6), superbalota=None)]
        filas = calcular_atrasos_superbalota(dataset, rango_min=1, rango_max=16)
        fila_10 = _por_valor(filas)["10"]
        # el sorteo 2 (sin superbalota) no debe "limpiar" ni afectar el atraso del 10
        assert fila_10.ultimo_sorteo_aparicion == 1
        assert fila_10.atraso == 1  # referencia=2 (total_sorteos cuenta ambos sorteos), ultima=1

    def test_superbalota_ausente_no_rompe_el_calculo_de_otros_valores(self):
        dataset = [_num(1, (1, 2, 3), superbalota=None), _num(2, (4, 5, 6), superbalota=5)]
        filas = calcular_atrasos_superbalota(dataset, rango_min=1, rango_max=16)
        fila_5 = _por_valor(filas)["5"]
        assert fila_5.atraso == 0

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_num(1, (1, 2, 3), superbalota=99)]
        with pytest.raises(ValueError, match="99"):
            calcular_atrasos_superbalota(dataset, rango_min=1, rango_max=16)

    def test_hasta_numero_sorteo_aplica_tambien_a_superbalota(self):
        dataset = [_num(1, (1, 2, 3), superbalota=10), _num(2, (4, 5, 6), superbalota=9)]
        filas = calcular_atrasos_superbalota(dataset, rango_min=1, rango_max=16, hasta_numero_sorteo=1)
        fila_9 = _por_valor(filas)["9"]
        assert fila_9.atraso is None  # el sorteo 2 (donde aparece el 9) queda fuera del corte


class TestCalcularAtrasosNumerosColorLoto:
    def test_numero_repetido_en_el_mismo_sorteo_no_duplica_la_aparicion(self):
        dataset = [_cl(100, ((5, "ROJO"), (5, "AZUL"), (1, "VERDE")))]
        filas = calcular_atrasos_numeros_colorloto(dataset, rango_min=1, rango_max=7)
        fila_5 = _por_valor(filas)["5"]
        assert fila_5.ultimo_sorteo_aparicion == 100
        assert fila_5.atraso == 0

    def test_ignora_el_color_solo_analiza_el_numero(self):
        dataset = [_cl(1, ((5, "ROJO"),)), _cl(2, ((5, "AZUL"),))]
        filas = calcular_atrasos_numeros_colorloto(dataset, rango_min=1, rango_max=7)
        fila_5 = _por_valor(filas)["5"]
        # la ultima aparicion del NUMERO 5 es el sorteo 2, sin importar que cambio de color
        assert fila_5.ultimo_sorteo_aparicion == 2
        assert fila_5.atraso == 0

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_cl(1, ((9, "ROJO"),))]
        with pytest.raises(ValueError, match="9"):
            calcular_atrasos_numeros_colorloto(dataset, rango_min=1, rango_max=7)

    def test_nunca_observado_es_none(self):
        dataset = [_cl(1, ((1, "ROJO"),))]
        filas = calcular_atrasos_numeros_colorloto(dataset, rango_min=1, rango_max=7)
        fila_7 = _por_valor(filas)["7"]
        assert fila_7.atraso is None


class TestPropiedadAntiFugaTodasLasFunciones:
    def test_anti_fuga_atrasos_superbalota(self):
        dataset = [_num(1, (1, 2, 3), superbalota=10), _num(2, (4, 5, 6), superbalota=9)]
        resultado_n = calcular_atrasos_superbalota(dataset, rango_min=1, rango_max=16, hasta_numero_sorteo=2)

        dataset_ampliado = dataset + [_num(3, (1, 2, 3), superbalota=15), _num(4, (4, 5, 6), superbalota=1)]
        resultado_n_ampliado = calcular_atrasos_superbalota(
            dataset_ampliado, rango_min=1, rango_max=16, hasta_numero_sorteo=2
        )
        assert resultado_n == resultado_n_ampliado

    def test_anti_fuga_atrasos_colorloto(self):
        dataset = [_cl(1, ((1, "ROJO"),)), _cl(2, ((2, "AZUL"),))]
        resultado_n = calcular_atrasos_numeros_colorloto(dataset, rango_min=1, rango_max=7, hasta_numero_sorteo=2)

        dataset_ampliado = dataset + [_cl(3, ((3, "VERDE"),)), _cl(4, ((1, "ROJO"),))]
        resultado_n_ampliado = calcular_atrasos_numeros_colorloto(
            dataset_ampliado, rango_min=1, rango_max=7, hasta_numero_sorteo=2
        )
        assert resultado_n == resultado_n_ampliado

    def test_no_mutar_input_en_ninguna_de_las_tres_funciones(self):
        dataset_num = [_num(2, (1, 2)), _num(1, (3, 4))]
        copia = list(dataset_num)
        calcular_atrasos_numeros(dataset_num, rango_min=1, rango_max=5)
        calcular_atrasos_superbalota(dataset_num, rango_min=1, rango_max=16)
        assert dataset_num == copia

        dataset_cl = [_cl(2, ((1, "ROJO"),)), _cl(1, ((2, "AZUL"),))]
        copia_cl = list(dataset_cl)
        calcular_atrasos_numeros_colorloto(dataset_cl, rango_min=1, rango_max=7)
        assert dataset_cl == copia_cl


# Dataset de referencia para color/par (Etapa L), con un HUECO
# deliberado en la numeración (falta el sorteo 3):
#
#   S1 (numero_sorteo=1): (2,ROJO), (3,AZUL)
#   S2 (numero_sorteo=2): (2,AZUL), (4,AZUL)
#   S3 (numero_sorteo=4): (2,ROJO), (5,ROJO)
#
# ROJO: ultima aparicion en el sorteo 4 -> atraso=0 (referencia=4)
# AZUL: ultima aparicion en el sorteo 2 -> atraso=4-2=2
# VERDE: vigente pero nunca observado -> atraso=None
_DATASET_CL_COLOR = [
    _cl(1, ((2, "ROJO"), (3, "AZUL"))),
    _cl(2, ((2, "AZUL"), (4, "AZUL"))),
    _cl(4, ((2, "ROJO"), (5, "ROJO"))),
]


def _por_valor_atraso(filas: list[AtrasoObservado]) -> dict[str, AtrasoObservado]:
    return {f.valor: f for f in filas}


class TestCalcularAtrasosColores:
    def test_atrasos_exactos_sobre_el_dataset_de_referencia(self):
        filas = calcular_atrasos_colores(_DATASET_CL_COLOR, colores_vigentes=["ROJO", "AZUL", "VERDE"])
        por_valor = _por_valor_atraso(filas)
        assert por_valor["ROJO"].atraso == 0
        assert por_valor["AZUL"].atraso == 2
        assert por_valor["VERDE"].atraso is None

    def test_usa_numero_sorteo_real_no_posicion_ordinal_pese_al_hueco(self):
        """El hueco (falta el sorteo 3) no debe distorsionar el
        atraso: la referencia sigue siendo el numero_sorteo real
        maximo (4), no la posicion ordinal (3 sorteos en la lista)."""
        filas = calcular_atrasos_colores(_DATASET_CL_COLOR, colores_vigentes=["ROJO", "AZUL"])
        por_valor = _por_valor_atraso(filas)
        assert por_valor["ROJO"].ultimo_sorteo_aparicion == 4
        assert por_valor["ROJO"].atraso == 0  # NO seria 0 si se usara mal la posicion ordinal

    def test_color_repetido_dentro_del_mismo_sorteo_no_altera_el_atraso(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO")))]  # ROJO 3 veces en el mismo sorteo
        filas = calcular_atrasos_colores(dataset, colores_vigentes=["ROJO"])
        por_valor = _por_valor_atraso(filas)
        assert por_valor["ROJO"].atraso == 0
        assert por_valor["ROJO"].ultimo_sorteo_aparicion == 1

    def test_color_observado_pero_no_vigente_no_se_pierde(self):
        dataset = [_cl(1, ((1, "MORADO"),))]
        filas = calcular_atrasos_colores(dataset, colores_vigentes=["ROJO", "AZUL"])
        assert "MORADO" in {f.valor for f in filas}

    def test_cero_sorteos(self):
        filas = calcular_atrasos_colores([], colores_vigentes=["ROJO", "AZUL"])
        assert all(f.atraso is None and f.ultimo_sorteo_aparicion is None and f.total_sorteos == 0 for f in filas)

    def test_un_solo_sorteo(self):
        filas = calcular_atrasos_colores([_cl(1, ((1, "ROJO"),))], colores_vigentes=["ROJO", "AZUL"])
        por_valor = _por_valor_atraso(filas)
        assert por_valor["ROJO"].atraso == 0
        assert por_valor["AZUL"].atraso is None

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET_CL_COLOR[2], _DATASET_CL_COLOR[0], _DATASET_CL_COLOR[1]]
        f1 = calcular_atrasos_colores(_DATASET_CL_COLOR, colores_vigentes=["ROJO", "AZUL"])
        f2 = calcular_atrasos_colores(desordenado, colores_vigentes=["ROJO", "AZUL"])
        assert f1 == f2

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_CL_COLOR)
        calcular_atrasos_colores(_DATASET_CL_COLOR, colores_vigentes=["ROJO", "AZUL"])
        assert _DATASET_CL_COLOR == copia

    def test_hasta_numero_sorteo_filtra_defensivamente(self):
        filas = calcular_atrasos_colores(_DATASET_CL_COLOR, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=2)
        por_valor = _por_valor_atraso(filas)
        # con corte en 2, el sorteo 4 (donde ROJO reaparece) no existe todavia
        assert por_valor["ROJO"].atraso == 1  # referencia=2, ultima aparicion=1
        assert por_valor["AZUL"].atraso == 0  # referencia=2, ultima aparicion=2

    def test_propiedad_anti_fuga(self):
        resultado_n = calcular_atrasos_colores(_DATASET_CL_COLOR, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=2)
        ampliado = _DATASET_CL_COLOR + [_cl(5, ((1, "VERDE"),)), _cl(6, ((2, "ROJO"),))]
        resultado_n_ampliado = calcular_atrasos_colores(ampliado, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=2)
        assert resultado_n == resultado_n_ampliado


class TestCalcularAtrasosParesNumeroColor:
    def test_atrasos_exactos_sobre_el_dataset_de_referencia(self):
        filas = calcular_atrasos_pares_numero_color(
            _DATASET_CL_COLOR, rango_min=1, rango_max=5, colores_vigentes=["ROJO", "AZUL", "VERDE"],
        )
        por_valor = _por_valor_atraso(filas)
        assert por_valor["2-ROJO"].atraso == 0    # S1(1), S3(4) -> ultima=4, referencia=4
        assert por_valor["2-AZUL"].atraso == 2    # S2(2) -> ultima=2, referencia=4
        assert por_valor["3-AZUL"].atraso == 3    # S1(1) -> ultima=1, referencia=4
        assert por_valor["5-ROJO"].atraso == 0    # S3(4) -> ultima=4

    def test_formato_del_valor_es_numero_guion_color(self):
        filas = calcular_atrasos_pares_numero_color(
            _DATASET_CL_COLOR, rango_min=1, rango_max=5, colores_vigentes=["ROJO", "AZUL", "VERDE"],
        )
        assert any(f.valor == "2-ROJO" for f in filas)

    def test_par_nunca_observado_es_none(self):
        filas = calcular_atrasos_pares_numero_color(
            _DATASET_CL_COLOR, rango_min=1, rango_max=5, colores_vigentes=["ROJO", "AZUL", "VERDE"],
        )
        por_valor = _por_valor_atraso(filas)
        assert por_valor["1-VERDE"].atraso is None

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_cl(1, ((99, "ROJO"),))]
        with pytest.raises(ValueError, match="99"):
            calcular_atrasos_pares_numero_color(dataset, rango_min=1, rango_max=7, colores_vigentes=["ROJO"])

    def test_par_repetido_dentro_del_mismo_sorteo_no_altera_el_atraso(self):
        dataset = [_cl(1, ((1, "ROJO"), (1, "ROJO")))]  # (1,ROJO) dos veces en el mismo sorteo
        filas = calcular_atrasos_pares_numero_color(dataset, rango_min=1, rango_max=3, colores_vigentes=["ROJO"])
        por_valor = _por_valor_atraso(filas)
        assert por_valor["1-ROJO"].atraso == 0
        assert por_valor["1-ROJO"].ultimo_sorteo_aparicion == 1

    def test_cero_sorteos(self):
        filas = calcular_atrasos_pares_numero_color([], rango_min=1, rango_max=3, colores_vigentes=["ROJO"])
        assert all(f.atraso is None for f in filas)

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET_CL_COLOR[2], _DATASET_CL_COLOR[0], _DATASET_CL_COLOR[1]]
        f1 = calcular_atrasos_pares_numero_color(_DATASET_CL_COLOR, rango_min=1, rango_max=5, colores_vigentes=["ROJO", "AZUL"])
        f2 = calcular_atrasos_pares_numero_color(desordenado, rango_min=1, rango_max=5, colores_vigentes=["ROJO", "AZUL"])
        assert f1 == f2

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_CL_COLOR)
        calcular_atrasos_pares_numero_color(_DATASET_CL_COLOR, rango_min=1, rango_max=5, colores_vigentes=["ROJO", "AZUL"])
        assert _DATASET_CL_COLOR == copia

    def test_hasta_numero_sorteo_y_anti_fuga(self):
        resultado_n = calcular_atrasos_pares_numero_color(
            _DATASET_CL_COLOR, rango_min=1, rango_max=5, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=2,
        )
        ampliado = _DATASET_CL_COLOR + [_cl(5, ((2, "ROJO"),))]
        resultado_n_ampliado = calcular_atrasos_pares_numero_color(
            ampliado, rango_min=1, rango_max=5, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=2,
        )
        assert resultado_n == resultado_n_ampliado


def _por_valor_intervalos(filas: list[IntervalosHistoricos]) -> dict[str, IntervalosHistoricos]:
    return {f.valor: f for f in filas}


# Dataset de referencia (Etapa N): el número 1 aparece en los
# sorteos 10, 14, 20, 27 -exactamente el caso verificado
# independientemente en el diseño (intervalos [4,6,7]).
# El número 2 aparece en un solo sorteo (sin intervalos posibles).
# El número 3 nunca aparece (0 apariciones).
_DATASET_INTERVALOS = [
    _num(10, (1,)),
    _num(14, (1,)),
    _num(20, (1, 2)),
    _num(27, (1,)),
]


class TestCalcularIntervalosHistoricosNumeros:
    def test_caso_verificado_independientemente_cuatro_apariciones_tres_intervalos(self):
        filas = calcular_intervalos_historicos_numeros(_DATASET_INTERVALOS, rango_min=1, rango_max=5)
        fila_1 = _por_valor_intervalos(filas)["1"]
        assert fila_1.cantidad_apariciones == 4
        assert fila_1.cantidad_intervalos == 3
        assert fila_1.intervalos == (4, 6, 7)
        assert fila_1.intervalo_minimo == 4
        assert fila_1.intervalo_maximo == 7
        assert fila_1.intervalo_promedio == pytest.approx(17 / 3)
        assert fila_1.intervalo_mediana == 6

    def test_cero_apariciones(self):
        filas = calcular_intervalos_historicos_numeros(_DATASET_INTERVALOS, rango_min=1, rango_max=5)
        fila_3 = _por_valor_intervalos(filas)["3"]
        assert fila_3.cantidad_apariciones == 0
        assert fila_3.cantidad_intervalos == 0
        assert fila_3.intervalo_minimo is None
        assert fila_3.intervalo_maximo is None
        assert fila_3.intervalo_promedio is None
        assert fila_3.intervalo_mediana is None
        assert fila_3.intervalos == ()

    def test_una_aparicion_sin_intervalos(self):
        filas = calcular_intervalos_historicos_numeros(_DATASET_INTERVALOS, rango_min=1, rango_max=5)
        fila_2 = _por_valor_intervalos(filas)["2"]
        assert fila_2.cantidad_apariciones == 1
        assert fila_2.cantidad_intervalos == 0
        assert fila_2.intervalo_minimo is None
        assert fila_2.intervalos == ()

    def test_dos_apariciones_un_intervalo(self):
        dataset = [_num(5, (9,)), _num(12, (9,))]
        filas = calcular_intervalos_historicos_numeros(dataset, rango_min=1, rango_max=9)
        fila_9 = _por_valor_intervalos(filas)["9"]
        assert fila_9.cantidad_apariciones == 2
        assert fila_9.cantidad_intervalos == 1
        assert fila_9.intervalos == (7,)
        assert fila_9.intervalo_minimo == fila_9.intervalo_maximo == 7
        assert fila_9.intervalo_promedio == 7.0
        assert fila_9.intervalo_mediana == 7.0

    def test_repeticion_dentro_del_mismo_sorteo_no_genera_intervalo_artificial(self):
        """Un número que aparece dos veces en el mismo sorteo (caso
        defensivo, no debería ocurrir en juegos estándar) no debe
        producir un intervalo de longitud 0."""
        dataset = [_num(1, (5, 5)), _num(2, (5,))]
        filas = calcular_intervalos_historicos_numeros(dataset, rango_min=1, rango_max=5)
        fila_5 = _por_valor_intervalos(filas)["5"]
        assert fila_5.cantidad_apariciones == 2  # no 3
        assert fila_5.intervalos == (1,)  # no incluye ningun 0

    def test_huecos_en_numero_sorteo_se_reflejan_correctamente(self):
        """El intervalo usa numero_sorteo real -si hay un hueco de
        importación entre dos apariciones, el intervalo debe
        reflejarlo correctamente (no subestimarlo)."""
        dataset = [_num(100, (7,)), _num(105, (7,))]  # sin datos de 101-104
        filas = calcular_intervalos_historicos_numeros(dataset, rango_min=1, rango_max=9)
        fila_7 = _por_valor_intervalos(filas)["7"]
        assert fila_7.intervalos == (5,)  # 105-100=5, correcto pese al hueco

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET_INTERVALOS[3], _DATASET_INTERVALOS[0], _DATASET_INTERVALOS[2], _DATASET_INTERVALOS[1]]
        f1 = calcular_intervalos_historicos_numeros(_DATASET_INTERVALOS, rango_min=1, rango_max=5)
        f2 = calcular_intervalos_historicos_numeros(desordenado, rango_min=1, rango_max=5)
        assert f1 == f2

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_INTERVALOS)
        calcular_intervalos_historicos_numeros(_DATASET_INTERVALOS, rango_min=1, rango_max=5)
        assert _DATASET_INTERVALOS == copia

    def test_hasta_numero_sorteo_y_anti_fuga(self):
        resultado_n = calcular_intervalos_historicos_numeros(
            _DATASET_INTERVALOS, rango_min=1, rango_max=5, hasta_numero_sorteo=20,
        )
        ampliado = _DATASET_INTERVALOS + [_num(30, (1,)), _num(40, (1,))]
        resultado_n_ampliado = calcular_intervalos_historicos_numeros(
            ampliado, rango_min=1, rango_max=5, hasta_numero_sorteo=20,
        )
        assert resultado_n == resultado_n_ampliado

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_num(1, (1, 99))]
        with pytest.raises(ValueError, match="99"):
            calcular_intervalos_historicos_numeros(dataset, rango_min=1, rango_max=5)


class TestCalcularIntervalosHistoricosSuperbalota:
    def test_caso_basico(self):
        dataset = [
            _num(10, (1, 2, 3), superbalota=9),
            _num(14, (1, 2, 3), superbalota=9),
            _num(20, (1, 2, 3), superbalota=9),
        ]
        filas = calcular_intervalos_historicos_superbalota(dataset, rango_min=1, rango_max=16)
        fila_9 = _por_valor_intervalos(filas)["9"]
        assert fila_9.intervalos == (4, 6)

    def test_superbalota_ausente_no_cuenta_como_aparicion(self):
        dataset = [_num(1, (1,), superbalota=5), _num(2, (1,), superbalota=None), _num(3, (1,), superbalota=5)]
        filas = calcular_intervalos_historicos_superbalota(dataset, rango_min=1, rango_max=16)
        fila_5 = _por_valor_intervalos(filas)["5"]
        assert fila_5.cantidad_apariciones == 2
        assert fila_5.intervalos == (2,)  # 3-1=2, el sorteo 2 (sin superbalota) no cuenta

    def test_cero_apariciones(self):
        filas = calcular_intervalos_historicos_superbalota([_num(1, (1,), superbalota=None)], rango_min=1, rango_max=16)
        assert all(f.cantidad_apariciones == 0 for f in filas)

    def test_no_muta_la_entrada(self):
        dataset = [_num(1, (1,), superbalota=5), _num(2, (1,), superbalota=5)]
        copia = list(dataset)
        calcular_intervalos_historicos_superbalota(dataset, rango_min=1, rango_max=16)
        assert dataset == copia

    def test_anti_fuga(self):
        dataset = [_num(1, (1,), superbalota=5), _num(2, (1,), superbalota=5)]
        resultado_n = calcular_intervalos_historicos_superbalota(dataset, rango_min=1, rango_max=16, hasta_numero_sorteo=2)
        ampliado = dataset + [_num(3, (1,), superbalota=5)]
        resultado_n_ampliado = calcular_intervalos_historicos_superbalota(ampliado, rango_min=1, rango_max=16, hasta_numero_sorteo=2)
        assert resultado_n == resultado_n_ampliado


class TestCalcularIntervalosHistoricosColores:
    _DATASET_CL = [
        _cl(10, ((1, "ROJO"),)),
        _cl(14, ((1, "ROJO"),)),
        _cl(20, ((1, "ROJO"), (2, "AZUL"))),
        _cl(27, ((1, "ROJO"),)),
    ]

    def test_caso_basico_mismo_patron_que_numeros(self):
        filas = calcular_intervalos_historicos_colores(self._DATASET_CL, colores_vigentes=["ROJO", "AZUL", "VERDE"])
        fila_rojo = _por_valor_intervalos(filas)["ROJO"]
        assert fila_rojo.intervalos == (4, 6, 7)

    def test_color_nunca_observado_cero_apariciones(self):
        filas = calcular_intervalos_historicos_colores(self._DATASET_CL, colores_vigentes=["ROJO", "AZUL", "VERDE"])
        fila_verde = _por_valor_intervalos(filas)["VERDE"]
        assert fila_verde.cantidad_apariciones == 0

    def test_color_repetido_dentro_del_mismo_sorteo_no_genera_intervalo_artificial(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"))), _cl(2, ((1, "ROJO"),))]
        filas = calcular_intervalos_historicos_colores(dataset, colores_vigentes=["ROJO"])
        fila_rojo = _por_valor_intervalos(filas)["ROJO"]
        assert fila_rojo.cantidad_apariciones == 2
        assert fila_rojo.intervalos == (1,)

    def test_color_observado_pero_no_vigente_no_se_pierde(self):
        dataset = [_cl(1, ((1, "MORADO"),)), _cl(2, ((1, "MORADO"),))]
        filas = calcular_intervalos_historicos_colores(dataset, colores_vigentes=["ROJO"])
        assert "MORADO" in {f.valor for f in filas}

    def test_no_muta_la_entrada(self):
        copia = list(self._DATASET_CL)
        calcular_intervalos_historicos_colores(self._DATASET_CL, colores_vigentes=["ROJO", "AZUL"])
        assert self._DATASET_CL == copia

    def test_anti_fuga(self):
        resultado_n = calcular_intervalos_historicos_colores(
            self._DATASET_CL, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=20,
        )
        ampliado = self._DATASET_CL + [_cl(30, ((1, "ROJO"),))]
        resultado_n_ampliado = calcular_intervalos_historicos_colores(
            ampliado, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=20,
        )
        assert resultado_n == resultado_n_ampliado


class TestCalcularIntervalosHistoricosParesNumeroColor:
    _DATASET_CL = [
        _cl(10, ((5, "ROJO"),)),
        _cl(14, ((5, "ROJO"),)),
        _cl(20, ((5, "ROJO"), (2, "AZUL"))),
        _cl(27, ((5, "ROJO"),)),
    ]

    def test_caso_basico(self):
        filas = calcular_intervalos_historicos_pares_numero_color(
            self._DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL"],
        )
        fila = _por_valor_intervalos(filas)["5-ROJO"]
        assert fila.intervalos == (4, 6, 7)

    def test_par_nunca_observado_cero_apariciones(self):
        filas = calcular_intervalos_historicos_pares_numero_color(
            self._DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL"],
        )
        fila = _por_valor_intervalos(filas)["1-AZUL"]
        assert fila.cantidad_apariciones == 0

    def test_par_repetido_dentro_del_mismo_sorteo_no_genera_intervalo_artificial(self):
        dataset = [_cl(1, ((5, "ROJO"), (5, "ROJO"))), _cl(2, ((5, "ROJO"),))]
        filas = calcular_intervalos_historicos_pares_numero_color(dataset, rango_min=1, rango_max=7, colores_vigentes=["ROJO"])
        fila = _por_valor_intervalos(filas)["5-ROJO"]
        assert fila.cantidad_apariciones == 2
        assert fila.intervalos == (1,)

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_cl(1, ((99, "ROJO"),))]
        with pytest.raises(ValueError, match="99"):
            calcular_intervalos_historicos_pares_numero_color(dataset, rango_min=1, rango_max=7, colores_vigentes=["ROJO"])

    def test_no_muta_la_entrada(self):
        copia = list(self._DATASET_CL)
        calcular_intervalos_historicos_pares_numero_color(
            self._DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL"],
        )
        assert self._DATASET_CL == copia

    def test_anti_fuga(self):
        resultado_n = calcular_intervalos_historicos_pares_numero_color(
            self._DATASET_CL, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=20,
        )
        ampliado = self._DATASET_CL + [_cl(30, ((5, "ROJO"),))]
        resultado_n_ampliado = calcular_intervalos_historicos_pares_numero_color(
            ampliado, rango_min=1, rango_max=7, colores_vigentes=["ROJO", "AZUL"], hasta_numero_sorteo=20,
        )
        assert resultado_n == resultado_n_ampliado


class TestCalcularIntervalosHistoricosNumerosColorLoto:
    _DATASET_CL = [
        _cl(10, ((5, "ROJO"),)),
        _cl(14, ((5, "AZUL"),)),  # mismo numero, color distinto -sigue siendo el mismo "numero"
        _cl(20, ((5, "VERDE"), (2, "AZUL"))),
        _cl(27, ((5, "ROJO"),)),
    ]

    def test_caso_basico_ignora_el_color(self):
        filas = calcular_intervalos_historicos_numeros_colorloto(self._DATASET_CL, rango_min=1, rango_max=7)
        fila_5 = _por_valor_intervalos(filas)["5"]
        assert fila_5.intervalos == (4, 6, 7)  # mismo resultado, color irrelevante

    def test_numero_repetido_dentro_del_mismo_sorteo_no_genera_intervalo_artificial(self):
        dataset = [_cl(1, ((5, "ROJO"), (5, "AZUL"))), _cl(2, ((5, "VERDE"),))]
        filas = calcular_intervalos_historicos_numeros_colorloto(dataset, rango_min=1, rango_max=7)
        fila_5 = _por_valor_intervalos(filas)["5"]
        assert fila_5.cantidad_apariciones == 2
        assert fila_5.intervalos == (1,)

    def test_cero_apariciones(self):
        filas = calcular_intervalos_historicos_numeros_colorloto(self._DATASET_CL, rango_min=1, rango_max=7)
        fila_7 = _por_valor_intervalos(filas)["7"]
        assert fila_7.cantidad_apariciones == 0

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset = [_cl(1, ((99, "ROJO"),))]
        with pytest.raises(ValueError, match="99"):
            calcular_intervalos_historicos_numeros_colorloto(dataset, rango_min=1, rango_max=7)

    def test_no_muta_la_entrada(self):
        copia = list(self._DATASET_CL)
        calcular_intervalos_historicos_numeros_colorloto(self._DATASET_CL, rango_min=1, rango_max=7)
        assert self._DATASET_CL == copia

    def test_anti_fuga(self):
        resultado_n = calcular_intervalos_historicos_numeros_colorloto(self._DATASET_CL, rango_min=1, rango_max=7, hasta_numero_sorteo=20)
        ampliado = self._DATASET_CL + [_cl(30, ((5, "ROJO"),))]
        resultado_n_ampliado = calcular_intervalos_historicos_numeros_colorloto(ampliado, rango_min=1, rango_max=7, hasta_numero_sorteo=20)
        assert resultado_n == resultado_n_ampliado
