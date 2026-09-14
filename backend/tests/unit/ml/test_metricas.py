"""Tests de `application/ml/metricas.py` -Etapa AE-36."""
from __future__ import annotations

import math

import pytest

from app.application.ml.metricas import (
    calcular_brier_score,
    calcular_log_loss,
    calcular_precision_recall_en_5,
    evaluar,
)
from app.application.ml.tipos import FilaCandidato


def _f(sorteo: int, candidato: int, etiqueta: int) -> FilaCandidato:
    return FilaCandidato(
        codigo_juego="BALOTO", sorteo_objetivo=sorteo, calculado_hasta_sorteo=sorteo - 1,
        numero_candidato=candidato, etiqueta=etiqueta, frecuencia_acumulada=0.0,
        frecuencia_ventana_10=0.0, frecuencia_ventana_20=0.0, frecuencia_ventana_50=0.0,
        sorteos_desde_ultima_aparicion=None, aparecio_en_sorteo_anterior=0,
    )


class TestLogLoss:
    def test_ejemplo_manual_verificable(self):
        filas = [_f(100, 1, 1), _f(100, 2, 0)]
        probs = [0.8, 0.3]
        esperado = -(math.log(0.8) + math.log(0.7)) / 2
        assert calcular_log_loss(filas, probs) == pytest.approx(esperado)

    def test_probabilidad_extrema_no_produce_infinito(self):
        filas = [_f(100, 1, 1), _f(100, 2, 0)]
        probs = [1.0, 0.0]
        resultado = calcular_log_loss(filas, probs)
        assert math.isfinite(resultado)

    def test_longitudes_distintas_falla(self):
        with pytest.raises(ValueError):
            calcular_log_loss([_f(100, 1, 1)], [0.5, 0.5])

    def test_vacio_falla(self):
        with pytest.raises(ValueError):
            calcular_log_loss([], [])


class TestBrierScore:
    def test_ejemplo_manual_verificable(self):
        filas = [_f(100, 1, 1), _f(100, 2, 0)]
        probs = [0.8, 0.3]
        esperado = ((0.8 - 1) ** 2 + (0.3 - 0) ** 2) / 2
        assert calcular_brier_score(filas, probs) == pytest.approx(esperado)

    def test_prediccion_perfecta_da_cero(self):
        filas = [_f(100, 1, 1), _f(100, 2, 0)]
        probs = [1.0 - 1e-9, 1e-9]
        assert calcular_brier_score(filas, probs) == pytest.approx(0.0, abs=1e-6)


class TestPrecisionRecallEn5:
    def test_top5_determinista_por_numero_ascendente_en_empate(self):
        filas = [_f(200, i, 1 if i in (1, 3, 5) else 0) for i in range(1, 9)]
        probs = [0.5] * 8  # todos empatados
        precision, recall = calcular_precision_recall_en_5(filas, probs)
        assert precision == pytest.approx(0.6)  # 3 aciertos de 5 en el top [1,2,3,4,5]
        assert recall == pytest.approx(1.0)  # las 3 positivas reales estan en el top5

    def test_agrupa_por_sorteo_no_por_fila(self):
        filas_s1 = [_f(1, i, 1 if i == 1 else 0) for i in range(1, 6)]
        filas_s2 = [_f(2, i, 1 if i == 1 else 0) for i in range(1, 6)]
        probs = [0.9, 0.1, 0.1, 0.1, 0.1] * 2
        precision, recall = calcular_precision_recall_en_5(filas_s1 + filas_s2, probs)
        assert 0.0 <= precision <= 1.0
        assert 0.0 <= recall <= 1.0

    def test_recall_correcto_cuando_no_todas_las_positivas_caben_en_top5(self):
        filas = [_f(300, i, 1) for i in range(1, 8)] + [_f(300, i, 0) for i in range(8, 44)]
        probs = [0.9] * 7 + [0.1] * 36  # 7 positivas, pero top5 solo puede tomar 5
        _, recall = calcular_precision_recall_en_5(filas, probs)
        assert recall == pytest.approx(5 / 7)


class TestEvaluar:
    def test_construye_metricas_validas(self):
        filas = [_f(100, 1, 1), _f(100, 2, 0)]
        probs = [0.8, 0.3]
        m = evaluar(filas, probs)
        assert math.isfinite(m.log_loss)
        assert math.isfinite(m.brier_score)
        assert 0.0 <= m.precision_en_5 <= 1.0
        assert 0.0 <= m.recall_en_5 <= 1.0
        assert m.total_sorteos == 1
        assert m.total_filas == 2

    def test_metricasevaluacion_rechaza_valores_no_finitos(self):
        from app.application.ml.tipos import MetricasEvaluacion
        with pytest.raises(ValueError):
            MetricasEvaluacion(
                log_loss=float("inf"), brier_score=0.1, precision_en_5=0.5, recall_en_5=0.5,
                total_sorteos=1, total_filas=2,
            )

    def test_metricasevaluacion_rechaza_precision_fuera_de_rango(self):
        from app.application.ml.tipos import MetricasEvaluacion
        with pytest.raises(ValueError):
            MetricasEvaluacion(
                log_loss=0.5, brier_score=0.1, precision_en_5=1.5, recall_en_5=0.5,
                total_sorteos=1, total_filas=2,
            )
