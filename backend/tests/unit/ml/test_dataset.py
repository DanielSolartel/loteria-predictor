"""Tests de `application/ml/dataset.py` -Etapa AE-36. Concentra las
pruebas anti-fuga mas criticas del proyecto: demuestran, con datos
sinteticos deterministas, que ninguna feature del sorteo objetivo `t`
puede depender de informacion posterior a `t`."""
from __future__ import annotations

from datetime import date, timedelta
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import PERIODO_CALENTAMIENTO_MINIMO, construir_dataset_binario
from app.application.ml.historico_util import HistoricoInconsistenteError


def _historico_sintetico(n_sorteos: int, semilla: int = 42, rango_max: int = 43) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    salida = []
    for n in range(1, n_sorteos + 1):
        numeros = tuple(sorted(rng.sample(range(1, rango_max + 1), 5)))
        salida.append(ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=numeros, superbalota=rng.randint(1, 16),
        ))
    return salida


class TestConstruirDatasetBinario:
    def test_conteo_de_filas_y_sorteos_objetivo(self):
        hist = _historico_sintetico(120)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        assert len(ds.sorteos_objetivo) == 120 - PERIODO_CALENTAMIENTO_MINIMO
        assert len(ds.filas) == (120 - PERIODO_CALENTAMIENTO_MINIMO) * 43

    def test_primer_sorteo_elegible_respeta_el_calentamiento(self):
        hist = _historico_sintetico(120)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        assert ds.sorteos_objetivo[0] == PERIODO_CALENTAMIENTO_MINIMO + 1

    def test_conservacion_positivas_y_negativas_por_sorteo(self):
        hist = _historico_sintetico(120)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        por_sorteo: dict[int, list[int]] = {}
        for f in ds.filas:
            por_sorteo.setdefault(f.sorteo_objetivo, []).append(f.etiqueta)
        for sorteo, etiquetas in por_sorteo.items():
            assert sum(etiquetas) == 5, sorteo
            assert len(etiquetas) - sum(etiquetas) == 38, sorteo

    def test_ningun_candidato_duplicado_por_sorteo(self):
        hist = _historico_sintetico(120)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        por_sorteo: dict[int, list[int]] = {}
        for f in ds.filas:
            por_sorteo.setdefault(f.sorteo_objetivo, []).append(f.numero_candidato)
        for sorteo, candidatos in por_sorteo.items():
            assert len(candidatos) == len(set(candidatos)), sorteo

    def test_ningun_candidato_fuera_de_rango(self):
        hist = _historico_sintetico(120)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        assert all(1 <= f.numero_candidato <= 43 for f in ds.filas)

    def test_calculado_hasta_sorteo_siempre_menor_que_objetivo(self):
        hist = _historico_sintetico(120)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        assert all(f.calculado_hasta_sorteo < f.sorteo_objetivo for f in ds.filas)

    def test_historico_insuficiente_produce_dataset_vacio(self):
        hist = _historico_sintetico(PERIODO_CALENTAMIENTO_MINIMO)  # exactamente el minimo, sin nada objetivo despues
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        assert ds.filas == ()
        assert ds.sorteos_objetivo == ()

    def test_historico_vacio_produce_dataset_vacio(self):
        ds = construir_dataset_binario([], 1, 43, 5, "BALOTO")
        assert ds.filas == ()

    def test_historico_duplicado_se_rechaza(self):
        hist = _historico_sintetico(60)
        hist_con_duplicado = hist + [hist[0]]
        with pytest.raises(HistoricoInconsistenteError):
            construir_dataset_binario(hist_con_duplicado, 1, 43, 5, "BALOTO")

    def test_historico_desordenado_produce_el_mismo_dataset(self):
        hist = _historico_sintetico(120)
        hist_desordenado = list(reversed(hist))
        ds_a = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        ds_b = construir_dataset_binario(hist_desordenado, 1, 43, 5, "BALOTO")
        assert ds_a.filas == ds_b.filas
        assert ds_a.sorteos_objetivo == ds_b.sorteos_objetivo


class TestAntiFugaTemporal:
    """El nucleo de la disciplina anti-fuga de AE-36: pruebas
    construidas para FALLAR si alguna vez se introduce una fuga."""

    def test_alterar_sorteos_posteriores_no_cambia_features_de_un_objetivo_anterior(self):
        hist = _historico_sintetico(120)
        ds_original = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        objetivo_fijo = 80
        filas_v1 = sorted(
            (f for f in ds_original.filas if f.sorteo_objetivo == objetivo_fijo),
            key=lambda f: f.numero_candidato,
        )

        hist_alterado = list(hist)
        for i in range(80, 120):  # todo lo posterior al objetivo, alterado drasticamente
            hist_alterado[i] = ResultadoNumerico(
                numero_sorteo=hist[i].numero_sorteo, fecha=hist[i].fecha, dia_semana="lunes",
                numeros=(1, 2, 3, 4, 5), superbalota=1,
            )
        ds_alterado = construir_dataset_binario(hist_alterado, 1, 43, 5, "BALOTO")
        filas_v2 = sorted(
            (f for f in ds_alterado.filas if f.sorteo_objetivo == objetivo_fijo),
            key=lambda f: f.numero_candidato,
        )

        assert filas_v1 == filas_v2

    def test_alterar_el_propio_resultado_objetivo_no_cambia_sus_propias_features(self):
        hist = _historico_sintetico(120)
        ds_original = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        objetivo_fijo = 80
        filas_v1 = sorted(
            (f for f in ds_original.filas if f.sorteo_objetivo == objetivo_fijo),
            key=lambda f: f.numero_candidato,
        )

        hist_alterado = list(hist)
        indice_objetivo = objetivo_fijo - 1  # numero_sorteo 80 esta en indice 79 (1-based -> 0-based)
        hist_alterado[indice_objetivo] = ResultadoNumerico(
            numero_sorteo=hist[indice_objetivo].numero_sorteo, fecha=hist[indice_objetivo].fecha,
            dia_semana="lunes", numeros=(39, 40, 41, 42, 43), superbalota=1,
        )
        ds_alterado = construir_dataset_binario(hist_alterado, 1, 43, 5, "BALOTO")
        filas_v2 = sorted(
            (f for f in ds_alterado.filas if f.sorteo_objetivo == objetivo_fijo),
            key=lambda f: f.numero_candidato,
        )

        features_v1 = [(f.frecuencia_acumulada, f.frecuencia_ventana_10, f.frecuencia_ventana_20,
                         f.frecuencia_ventana_50, f.sorteos_desde_ultima_aparicion, f.aparecio_en_sorteo_anterior)
                        for f in filas_v1]
        features_v2 = [(f.frecuencia_acumulada, f.frecuencia_ventana_10, f.frecuencia_ventana_20,
                         f.frecuencia_ventana_50, f.sorteos_desde_ultima_aparicion, f.aparecio_en_sorteo_anterior)
                        for f in filas_v2]
        assert features_v1 == features_v2

        etiquetas_v1 = [f.etiqueta for f in filas_v1]
        etiquetas_v2 = [f.etiqueta for f in filas_v2]
        assert etiquetas_v1 != etiquetas_v2  # la etiqueta SI debe cambiar

    def test_filacandidato_rechaza_calculado_hasta_mayor_o_igual_que_objetivo(self):
        from app.application.ml.tipos import FilaCandidato
        with pytest.raises(ValueError):
            FilaCandidato(
                codigo_juego="BALOTO", sorteo_objetivo=100, calculado_hasta_sorteo=100,
                numero_candidato=1, etiqueta=1, frecuencia_acumulada=0.0,
                frecuencia_ventana_10=0.0, frecuencia_ventana_20=0.0, frecuencia_ventana_50=0.0,
                sorteos_desde_ultima_aparicion=None, aparecio_en_sorteo_anterior=0,
            )
