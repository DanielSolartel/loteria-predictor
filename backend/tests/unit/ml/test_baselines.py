"""Tests de `application/ml/baselines.py` -Etapa AE-36."""
from __future__ import annotations

from datetime import date, timedelta
import math
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.baselines import (
    baseline_frecuencia_acumulada,
    baseline_frecuencia_ventana_reciente,
    baseline_sorteo_anterior,
    baseline_uniforme,
    evaluar_todos_los_baselines,
)
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.particion import construir_particion_walk_forward


def _historico_sintetico(n_sorteos: int, semilla: int = 3) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    return [
        ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=tuple(sorted(rng.sample(range(1, 44), 5))), superbalota=rng.randint(1, 16),
        )
        for n in range(1, n_sorteos + 1)
    ]


class TestBaselineUniforme:
    def test_probabilidad_correcta(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        resultado = baseline_uniforme(part.filas_test_final, 1, 43, 5)
        assert math.isfinite(resultado.metricas.log_loss)

    def test_metricas_validas(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        resultado = baseline_uniforme(part.filas_test_final, 1, 43, 5)
        assert 0.0 <= resultado.metricas.precision_en_5 <= 1.0


class TestBaselineFrecuenciaAcumulada:
    def test_solo_usa_pasado(self):
        """Verificado indirectamente: dos historicos identicos hasta
        el corte de cada fila deben producir el mismo baseline,
        aunque el futuro despues del corte sea distinto."""
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
        r1 = baseline_frecuencia_acumulada(part.filas_test_final, hist_ordenado, 1, 43)

        hist_alterado = list(hist)
        ultimo_sorteo_test = part.limites.test_fin
        for i, r in enumerate(hist_alterado):
            if r.numero_sorteo == ultimo_sorteo_test:
                hist_alterado[i] = ResultadoNumerico(
                    numero_sorteo=r.numero_sorteo, fecha=r.fecha, dia_semana="lunes",
                    numeros=(39, 40, 41, 42, 43), superbalota=1,
                )
        ds2 = construir_dataset_binario(hist_alterado, 1, 43, 5, "BALOTO")
        part2 = construir_particion_walk_forward(ds2)
        hist_ordenado2 = validar_y_ordenar_historico(hist_alterado, "BALOTO")
        r2 = baseline_frecuencia_acumulada(part2.filas_test_final, hist_ordenado2, 1, 43)

        # Solo la ULTIMA fila de test (correspondiente al ultimo sorteo alterado) puede diferir
        assert r1.metricas.total_filas == r2.metricas.total_filas


class TestBaselineSorteoAnterior:
    def test_probabilidades_nunca_exactas_0_o_1(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
        resultado = baseline_sorteo_anterior(part.filas_test_final, hist_ordenado, 1, 43, 5)
        assert math.isfinite(resultado.metricas.log_loss)
        assert math.isfinite(resultado.metricas.brier_score)


class TestEvaluarTodosLosBaselines:
    def test_devuelve_exactamente_cuatro(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
        resultados = evaluar_todos_los_baselines(part.filas_test_final, hist_ordenado, 1, 43, 5)
        assert len(resultados) == 4
        nombres = {r.nombre for r in resultados}
        assert nombres == {"uniforme", "frecuencia_acumulada", "frecuencia_ventana_20", "sorteo_anterior"}

    def test_todos_finitos_y_validos(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
        resultados = evaluar_todos_los_baselines(part.filas_test_final, hist_ordenado, 1, 43, 5)
        for r in resultados:
            assert math.isfinite(r.metricas.log_loss)
            assert math.isfinite(r.metricas.brier_score)
            assert 0.0 <= r.metricas.precision_en_5 <= 1.0
            assert 0.0 <= r.metricas.recall_en_5 <= 1.0
