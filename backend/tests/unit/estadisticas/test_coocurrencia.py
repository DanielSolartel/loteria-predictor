"""
Tests de `application/estadisticas/motor/coocurrencia.py`.

Dataset de referencia (rango 1-10, K=4, chico a propósito para que
las combinaciones sean verificables a mano):

    S1: 1, 2, 3, 8
    S2: 1, 2, 5, 9
    S3: 1, 2, 3, 4
    S4: 5, 6, 7, 10

La pareja (1,2) aparece en S1, S2, S3 -> soporte 3.
El trío (1,2,3) aparece en S1, S3 -> soporte 2.
El trío (8,9,10) nunca coocurre en ningún sorteo (8 solo en S1, 9
solo en S2, 10 solo en S4) -caso usado para verificar ausencia.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.estadisticas.motor.coocurrencia import (
    _contar_coocurrencias_crudo,
    calcular_coocurrencia_pares,
    calcular_coocurrencia_pares_colores,
    calcular_coocurrencia_pares_colorloto,
    calcular_coocurrencia_trios,
    calcular_coocurrencia_trios_colores,
    calcular_coocurrencia_trios_colorloto,
)
from app.application.estadisticas.tipos import MetricaAsociacion, ResultadoColorLoto, ResultadoNumerico

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
    _num(1, (1, 2, 3, 8)),
    _num(2, (1, 2, 5, 9)),
    _num(3, (1, 2, 3, 4)),
    _num(4, (5, 6, 7, 10)),
]


def _por_elementos(filas: list[MetricaAsociacion]) -> dict[tuple[str, ...], MetricaAsociacion]:
    return {f.elementos: f for f in filas}


class TestCalcularCoocurrenciaPares:
    def test_soporte_exacto_pareja_1_2(self):
        filas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        por_elem = _por_elementos(filas)
        assert por_elem[("1", "2")].soporte == 3

    def test_elementos_en_orden_canonico_ascendente(self):
        filas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        for fila in filas:
            valores = [int(v) for v in fila.elementos]
            assert valores == sorted(valores)

    def test_pares_repetidos_entre_sorteos_se_acumulan(self):
        filas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        por_elem = _por_elementos(filas)
        assert por_elem[("1", "3")].soporte == 2
        assert por_elem[("2", "3")].soporte == 2

    def test_par_nunca_observado_esta_ausente(self):
        filas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        por_elem = _por_elementos(filas)
        assert ("8", "10") not in por_elem

    def test_frecuencia_relativa_correcta(self):
        filas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        por_elem = _por_elementos(filas)
        assert por_elem[("1", "2")].frecuencia_relativa == 3 / 4

    def test_ordenado_por_soporte_descendente(self):
        filas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        soportes = [f.soporte for f in filas]
        assert soportes == sorted(soportes, reverse=True)

    def test_frecuencia_esperada_hipergeometrica_verificada_independientemente(self):
        filas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        n, k = 10, 4
        esperado_alternativo = (k * (k - 1)) / (n * (n - 1))
        assert filas[0].frecuencia_esperada == pytest.approx(esperado_alternativo)

    def test_lift_es_frecuencia_relativa_sobre_esperada(self):
        filas = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        por_elem = _por_elementos(filas)
        fila = por_elem[("1", "2")]
        assert fila.lift == pytest.approx(fila.frecuencia_relativa / fila.frecuencia_esperada)

    def test_cero_sorteos(self):
        filas = calcular_coocurrencia_pares([], rango_min=1, rango_max=10, cantidad_numeros=4)
        assert filas == []

    def test_un_solo_sorteo(self):
        filas = calcular_coocurrencia_pares([_num(1, (1, 2, 3, 4))], rango_min=1, rango_max=10, cantidad_numeros=4)
        assert len(filas) == 6
        assert all(f.soporte == 1 for f in filas)

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET[2], _DATASET[0], _DATASET[3], _DATASET[1]]
        f1 = calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        f2 = calcular_coocurrencia_pares(desordenado, rango_min=1, rango_max=10, cantidad_numeros=4)
        assert sorted(f1, key=lambda f: f.elementos) == sorted(f2, key=lambda f: f.elementos)

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_coocurrencia_pares(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        assert _DATASET == copia

    def test_numero_fuera_de_rango_lanza_value_error(self):
        dataset_invalido = [_num(1, (1, 2, 999, 4))]
        with pytest.raises(ValueError, match="999"):
            calcular_coocurrencia_pares(dataset_invalido, rango_min=1, rango_max=10, cantidad_numeros=4)


class TestCalcularCoocurrenciaTrios:
    def test_soporte_exacto_trio_1_2_3(self):
        filas = calcular_coocurrencia_trios(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        por_elem = _por_elementos(filas)
        assert por_elem[("1", "2", "3")].soporte == 2

    def test_trio_observado_esta_presente_y_no_observado_esta_ausente(self):
        filas = calcular_coocurrencia_trios(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        por_elem = _por_elementos(filas)
        assert ("5", "6", "7") in por_elem  # observado en S4
        assert ("8", "9", "10") not in por_elem  # 8,9,10 nunca coinciden en el mismo sorteo

    def test_frecuencia_esperada_trio_verificada_independientemente(self):
        filas = calcular_coocurrencia_trios(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        n, k = 10, 4
        esperado_alternativo = (k * (k - 1) * (k - 2)) / (n * (n - 1) * (n - 2))
        assert filas[0].frecuencia_esperada == pytest.approx(esperado_alternativo)

    def test_cero_sorteos(self):
        assert calcular_coocurrencia_trios([], rango_min=1, rango_max=10, cantidad_numeros=4) == []

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET)
        calcular_coocurrencia_trios(_DATASET, rango_min=1, rango_max=10, cantidad_numeros=4)
        assert _DATASET == copia


class TestCorteTemporalYAntiFuga:
    def test_corte_temporal_excluye_sorteos_posteriores(self):
        filas = calcular_coocurrencia_pares(
            _DATASET, rango_min=1, rango_max=10, cantidad_numeros=4, hasta_numero_sorteo=2
        )
        por_elem = _por_elementos(filas)
        assert por_elem[("1", "2")].soporte == 2

    def test_propiedad_anti_fuga(self):
        resultado_n = calcular_coocurrencia_pares(
            _DATASET, rango_min=1, rango_max=10, cantidad_numeros=4, hasta_numero_sorteo=2
        )
        ampliado = _DATASET + [_num(5, (1, 2, 6, 7))]
        resultado_n_ampliado = calcular_coocurrencia_pares(
            ampliado, rango_min=1, rango_max=10, cantidad_numeros=4, hasta_numero_sorteo=2
        )
        assert sorted(resultado_n, key=lambda f: f.elementos) == sorted(resultado_n_ampliado, key=lambda f: f.elementos)


class TestColorLoto:
    def test_deduplica_numero_repetido_dentro_del_mismo_sorteo(self):
        dataset = [_cl(1, ((2, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE")))]
        filas = calcular_coocurrencia_pares_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        por_elem = _por_elementos(filas)
        assert ("2", "2") not in por_elem
        assert len(filas) == 10  # C(5,2) sobre {2,3,4,5,6} distintos

    def test_repeticion_interna_en_dos_sorteos_no_infla_el_soporte(self):
        dataset = [
            _cl(1, ((2, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
            _cl(2, ((2, "ROJO"), (2, "AZUL"), (3, "VERDE"), (7, "ROJO"), (1, "AZUL"), (4, "VERDE"))),
        ]
        filas = calcular_coocurrencia_pares_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        por_elem = _por_elementos(filas)
        assert por_elem[("2", "3")].soporte == 2

    def test_ignora_el_color(self):
        dataset = [_cl(1, ((2, "ROJO"), (3, "AZUL"))), _cl(2, ((2, "VERDE"), (3, "NEGRO")))]
        filas = calcular_coocurrencia_pares_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=2)
        assert _por_elementos(filas)[("2", "3")].soporte == 2

    def test_frecuencia_esperada_es_none(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "AZUL")))]
        filas = calcular_coocurrencia_pares_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=2)
        assert all(f.frecuencia_esperada is None for f in filas)

    def test_lift_es_none(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "AZUL")))]
        filas = calcular_coocurrencia_pares_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=2)
        assert all(f.lift is None for f in filas)

    def test_soporte_y_frecuencia_relativa_si_se_calculan(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "AZUL"))), _cl(2, ((1, "VERDE"), (2, "NEGRO")))]
        filas = calcular_coocurrencia_pares_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=2)
        fila = _por_elementos(filas)[("1", "2")]
        assert fila.soporte == 2
        assert fila.frecuencia_relativa == 1.0

    def test_trios_colorloto_con_deduplicacion(self):
        dataset = [_cl(1, ((1, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "ROJO"), (4, "AZUL"), (5, "VERDE")))]
        filas = calcular_coocurrencia_trios_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=6)
        por_elem = _por_elementos(filas)
        assert ("1", "1", "2") not in por_elem
        assert ("1", "2", "3") in por_elem

    def test_numero_fuera_de_rango_colorloto_lanza_value_error(self):
        dataset = [_cl(1, ((9, "ROJO"), (1, "AZUL")))]
        with pytest.raises(ValueError, match="9"):
            calcular_coocurrencia_pares_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=2)

    def test_no_muta_la_entrada_colorloto(self):
        dataset = [_cl(1, ((1, "ROJO"), (1, "AZUL"), (2, "VERDE")))]
        copia = list(dataset)
        calcular_coocurrencia_pares_colorloto(dataset, rango_min=1, rango_max=7, cantidad_balotas=3)
        assert dataset == copia

    def test_anti_fuga_colorloto(self):
        dataset = [_cl(1, ((1, "ROJO"), (2, "AZUL"))), _cl(2, ((1, "VERDE"), (2, "NEGRO")))]
        r_n = calcular_coocurrencia_pares_colorloto(
            dataset, rango_min=1, rango_max=7, cantidad_balotas=2, hasta_numero_sorteo=1
        )
        ampliado = dataset + [_cl(3, ((1, "ROJO"), (2, "AZUL")))]
        r_amp = calcular_coocurrencia_pares_colorloto(
            ampliado, rango_min=1, rango_max=7, cantidad_balotas=2, hasta_numero_sorteo=1
        )
        assert sorted(r_n, key=lambda f: f.elementos) == sorted(r_amp, key=lambda f: f.elementos)


# Dataset de referencia para coocurrencia de colores (Etapa M), mismo
# dataset de referencia usado en test_distribuciones.py para las
# métricas de color:
#
#   S1: distintos {ROJO,AZUL,VERDE} (ROJO repetido x3 dentro del sorteo)
#   S2: distintos {ROJO,AZUL,VERDE}
#   S3: distintos {VERDE} (VERDE x6, un solo color distinto -> sin pares)
_DATASET_COLOR = [
    _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "AZUL"), (5, "AZUL"), (6, "VERDE"))),
    _cl(2, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))),
    _cl(3, ((1, "VERDE"), (2, "VERDE"), (3, "VERDE"), (4, "VERDE"), (5, "VERDE"), (6, "VERDE"))),
]


class TestCalcularCoocurrenciaParesColores:
    def test_soporte_exacto_par_azul_rojo(self):
        filas = calcular_coocurrencia_pares_colores(_DATASET_COLOR)
        por_elem = _por_elementos(filas)
        assert por_elem[("AZUL", "ROJO")].soporte == 2  # S1 y S2

    def test_todos_los_pares_esperados_presentes(self):
        filas = calcular_coocurrencia_pares_colores(_DATASET_COLOR)
        por_elem = _por_elementos(filas)
        assert por_elem[("AZUL", "VERDE")].soporte == 2
        assert por_elem[("ROJO", "VERDE")].soporte == 2

    def test_color_repetido_no_forma_pareja_consigo_mismo(self):
        """Caso central pedido explícitamente: ROJO aparece 3 veces
        en S1, pero (ROJO,ROJO) nunca debe aparecer como combinación."""
        filas = calcular_coocurrencia_pares_colores(_DATASET_COLOR)
        assert ("ROJO", "ROJO") not in _por_elementos(filas)

    def test_repeticion_no_infla_el_soporte(self):
        """El soporte de (AZUL,ROJO) debe ser 2 (S1+S2), NO 3 -aunque
        ROJO aparezca 3 veces dentro de S1, esa repetición interna no
        multiplica el soporte de la pareja."""
        filas = calcular_coocurrencia_pares_colores(_DATASET_COLOR)
        assert _por_elementos(filas)[("AZUL", "ROJO")].soporte == 2

    def test_sorteo_con_un_solo_color_distinto_no_aporta_pares(self):
        filas = calcular_coocurrencia_pares_colores([_DATASET_COLOR[2]])  # solo S3: {VERDE}
        assert filas == []

    def test_frecuencia_esperada_y_lift_son_none(self):
        filas = calcular_coocurrencia_pares_colores(_DATASET_COLOR)
        assert all(f.frecuencia_esperada is None for f in filas)
        assert all(f.lift is None for f in filas)

    def test_orden_canonico_ascendente(self):
        filas = calcular_coocurrencia_pares_colores(_DATASET_COLOR)
        for f in filas:
            assert list(f.elementos) == sorted(f.elementos)

    def test_cero_sorteos(self):
        assert calcular_coocurrencia_pares_colores([]) == []

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_COLOR)
        calcular_coocurrencia_pares_colores(_DATASET_COLOR)
        assert _DATASET_COLOR == copia

    def test_entrada_desordenada_da_el_mismo_resultado(self):
        desordenado = [_DATASET_COLOR[2], _DATASET_COLOR[0], _DATASET_COLOR[1]]
        f1 = calcular_coocurrencia_pares_colores(_DATASET_COLOR)
        f2 = calcular_coocurrencia_pares_colores(desordenado)
        assert sorted(f1, key=lambda f: f.elementos) == sorted(f2, key=lambda f: f.elementos)

    def test_hasta_numero_sorteo_y_anti_fuga(self):
        resultado_n = calcular_coocurrencia_pares_colores(_DATASET_COLOR, hasta_numero_sorteo=2)
        ampliado = _DATASET_COLOR + [_cl(4, ((1, "NEGRO"), (2, "BLANCO")))]
        resultado_n_ampliado = calcular_coocurrencia_pares_colores(ampliado, hasta_numero_sorteo=2)
        assert sorted(resultado_n, key=lambda f: f.elementos) == sorted(resultado_n_ampliado, key=lambda f: f.elementos)

    def test_helper_crudo_produce_el_conteo_esperado_con_colores(self):
        """Verificación independiente pedida: comprobar que
        _contar_coocurrencias_crudo, al recibir listas de colores
        directamente (sin pasar por calcular_coocurrencia_pares_colores),
        produce exactamente el mismo conteo crudo."""
        listas_de_colores = [[c for _, c in r.pares] for r in _DATASET_COLOR]
        crudo = _contar_coocurrencias_crudo(listas_de_colores, 2)
        assert crudo[("AZUL", "ROJO")] == 2
        assert crudo[("AZUL", "VERDE")] == 2
        assert crudo[("ROJO", "VERDE")] == 2
        assert ("ROJO", "ROJO") not in crudo


class TestCalcularCoocurrenciaTriosColores:
    def test_soporte_exacto_trio(self):
        filas = calcular_coocurrencia_trios_colores(_DATASET_COLOR)
        por_elem = _por_elementos(filas)
        assert por_elem[("AZUL", "ROJO", "VERDE")].soporte == 2  # S1 y S2

    def test_deduplicacion_en_trios(self):
        """Un color repetido dentro del sorteo no debe aportar más de
        una vez al trío -verificado también para tríos, no solo pares."""
        filas = calcular_coocurrencia_trios_colores(_DATASET_COLOR)
        elementos_presentes = {f.elementos for f in filas}
        # con 3 colores distintos por sorteo (S1,S2), solo hay UN trio
        # posible: (AZUL,ROJO,VERDE) -pese a que ROJO aparece 3 veces
        assert elementos_presentes == {("AZUL", "ROJO", "VERDE")}

    def test_frecuencia_esperada_y_lift_son_none(self):
        filas = calcular_coocurrencia_trios_colores(_DATASET_COLOR)
        assert all(f.frecuencia_esperada is None and f.lift is None for f in filas)

    def test_cero_sorteos(self):
        assert calcular_coocurrencia_trios_colores([]) == []

    def test_no_muta_la_entrada(self):
        copia = list(_DATASET_COLOR)
        calcular_coocurrencia_trios_colores(_DATASET_COLOR)
        assert _DATASET_COLOR == copia

    def test_helper_crudo_produce_el_conteo_esperado_para_trios(self):
        listas_de_colores = [[c for _, c in r.pares] for r in _DATASET_COLOR]
        crudo = _contar_coocurrencias_crudo(listas_de_colores, 3)
        assert crudo[("AZUL", "ROJO", "VERDE")] == 2

    def test_anti_fuga(self):
        resultado_n = calcular_coocurrencia_trios_colores(_DATASET_COLOR, hasta_numero_sorteo=2)
        ampliado = _DATASET_COLOR + [_cl(4, ((1, "NEGRO"), (2, "BLANCO"), (3, "GRIS")))]
        resultado_n_ampliado = calcular_coocurrencia_trios_colores(ampliado, hasta_numero_sorteo=2)
        assert sorted(resultado_n, key=lambda f: f.elementos) == sorted(resultado_n_ampliado, key=lambda f: f.elementos)


class TestPruebaCruzadaMultiplicidadVsConjunto:
    """Prueba cruzada explícita pedida: demuestra en un solo test que
    conteo/máximo de repetición (distribuciones.py) usan multiplicidad,
    mientras que coocurrencia (este módulo) usa conjunto/deduplicación
    -sobre el MISMO sorteo con ROJO repetido 3 veces."""

    def test_mismo_sorteo_multiplicidad_en_distribuciones_conjunto_en_coocurrencia(self):
        from app.application.estadisticas.motor.distribuciones import (
            calcular_distribucion_conteo_color,
            calcular_maximo_repeticion_color_por_sorteo,
        )

        sorteo_con_repeticion = [
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "AZUL"), (5, "AZUL"), (6, "VERDE")))
        ]

        # distribuciones.py: MULTIPLICIDAD -cuenta las 3 balotas ROJO
        conteo_rojo = calcular_distribucion_conteo_color(sorteo_con_repeticion, color_objetivo="ROJO", cantidad_balotas=6)
        fila_3 = next(f for f in conteo_rojo if f.valor == "3")
        assert fila_3.apariciones == 1  # el sorteo SI cuenta como "3 rojas"

        maximo = calcular_maximo_repeticion_color_por_sorteo(sorteo_con_repeticion, cantidad_balotas=6)
        fila_max_3 = next(f for f in maximo if f.valor == "3")
        assert fila_max_3.apariciones == 1  # el maximo de repeticion SI es 3

        # coocurrencia.py: CONJUNTO -ROJO deduplicado, nunca se empareja consigo mismo
        pares = calcular_coocurrencia_pares_colores(sorteo_con_repeticion)
        assert ("ROJO", "ROJO") not in {f.elementos for f in pares}
        # solo colores DISTINTOS generan pares: {ROJO,AZUL,VERDE} -> 3 pares, cada uno soporte 1
        assert len(pares) == 3
        assert all(f.soporte == 1 for f in pares)
