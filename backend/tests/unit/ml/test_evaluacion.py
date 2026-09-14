"""Tests de `application/ml/evaluacion.py` -Etapa AE-36."""
from __future__ import annotations

from datetime import date, timedelta
import math
import random

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.evaluacion import evaluar_juego
from app.application.ml.historico_util import HistoricoInconsistenteError

import pytest


def _historico_sintetico(n_sorteos: int, semilla: int = 123) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    return [
        ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=tuple(sorted(rng.sample(range(1, 44), 5))), superbalota=rng.randint(1, 16),
        )
        for n in range(1, n_sorteos + 1)
    ]


class TestEvaluarJuego:
    def test_reporte_completo_baloto(self):
        hist = _historico_sintetico(250)
        reporte = evaluar_juego(hist, 1, 43, 5, "BALOTO", semilla=42)
        assert reporte.codigo_juego == "BALOTO"
        assert reporte.rango_min == 1
        assert reporte.rango_max == 43
        assert reporte.cantidad_numeros == 5
        assert reporte.metricas_modelo is not None
        assert len(reporte.baselines) == 4
        assert reporte.version_sklearn != ""
        assert reporte.semilla == 42

    def test_reporte_completo_baloto_revancha(self):
        hist = _historico_sintetico(250, semilla=456)
        reporte = evaluar_juego(hist, 1, 43, 5, "BALOTO_REVANCHA", semilla=42)
        assert reporte.codigo_juego == "BALOTO_REVANCHA"
        assert reporte.metricas_modelo is not None

    def test_todas_las_metricas_finitas(self):
        hist = _historico_sintetico(250)
        reporte = evaluar_juego(hist, 1, 43, 5, "BALOTO", semilla=42)
        assert math.isfinite(reporte.metricas_modelo.log_loss)
        assert math.isfinite(reporte.metricas_modelo.brier_score)
        for b in reporte.baselines:
            assert math.isfinite(b.metricas.log_loss)
            assert math.isfinite(b.metricas.brier_score)

    def test_resumen_nunca_usa_lenguaje_promocional(self):
        hist = _historico_sintetico(250)
        reporte = evaluar_juego(hist, 1, 43, 5, "BALOTO", semilla=42)
        prohibidas = ["ganador", "prediccion", "alta confianza", "garantizada", "ventaja"]
        resumen_min = reporte.resumen.lower()
        for palabra in prohibidas:
            assert palabra not in resumen_min

    def test_historico_inconsistente_se_rechaza(self):
        hist = _historico_sintetico(250)
        hist_con_duplicado = hist + [hist[0]]
        with pytest.raises(HistoricoInconsistenteError):
            evaluar_juego(hist_con_duplicado, 1, 43, 5, "BALOTO", semilla=42)

    def test_reproducibilidad_misma_semilla(self):
        hist = _historico_sintetico(250)
        r1 = evaluar_juego(hist, 1, 43, 5, "BALOTO", semilla=42)
        r2 = evaluar_juego(hist, 1, 43, 5, "BALOTO", semilla=42)
        assert r1.metricas_modelo == r2.metricas_modelo
