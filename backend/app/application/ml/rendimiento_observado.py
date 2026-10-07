"""
Metricas de un pronostico guardado frente a su resultado observado, por
objetivo (Producto 3). Modulo puro.

Reutiliza las definiciones del dominio con las probabilidades GUARDADAS en
el artefacto (nunca reentrena):
- numeros (Baloto, Revancha, MiLoto): Log Loss y Brier sobre las filas
  candidato-objetivo con `metricas.calcular_log_loss` y
  `metricas.calcular_brier_score` (las de la evaluacion walk-forward);
- superbalota: Log Loss y Brier multiclase de la clase observada, la misma
  definicion que la evaluacion walk-forward de la superbalota;
- ColorLoto: `pronostico_colorloto.metricas_de_objetivo` (Log Loss y Brier
  por balota y Log Loss del multiconjunto) con la distribucion de pares
  guardada.
La referencia es la uniforme que el propio artefacto declara
(`probabilidad_uniforme`). Diferencia = perdida del modelo - perdida de la
uniforme: negativa si el modelo tuvo menor perdida en ese objetivo.
"""
from __future__ import annotations

import math
from collections import namedtuple
from collections.abc import Sequence

from app.application.ml import pronostico_colorloto as colorloto
from app.application.ml.metricas import calcular_brier_score, calcular_log_loss

_Fila = namedtuple("_Fila", "sorteo_objetivo numero_candidato etiqueta")


class ObjetivoNoEvaluableError(ValueError):
    """El resultado observado no se puede evaluar con las probabilidades
    guardadas (p. ej. un numero o par fuera de las previstas)."""


def metricas_numeros(artefacto: dict, numeros_observados: Sequence[int]) -> dict:
    pronostico = artefacto["pronostico"]
    ranking = sorted(pronostico["ranking"], key=lambda f: f["numero"])
    candidatos = {f["numero"] for f in ranking}
    if not set(numeros_observados) <= candidatos:
        raise ObjetivoNoEvaluableError("el resultado trae numeros fuera de los candidatos del artefacto")
    filas = [_Fila(pronostico["objetivo"], f["numero"], 1 if f["numero"] in numeros_observados else 0) for f in ranking]
    modelo = [f["probabilidad"] for f in ranking]
    uniforme = [f["probabilidad_uniforme"] for f in ranking]
    return {"log_loss": calcular_log_loss(filas, modelo), "log_loss_uniforme": calcular_log_loss(filas, uniforme),
            "brier": calcular_brier_score(filas, modelo), "brier_uniforme": calcular_brier_score(filas, uniforme),
            "filas": len(filas)}


def metricas_multiclase(probabilidades: dict, observado) -> dict:
    """Log Loss y Brier de una clase observada (superbalota)."""
    if observado not in probabilidades:
        raise ObjetivoNoEvaluableError("clase observada fuera de las previstas")
    return {"log_loss": -math.log(probabilidades[observado]),
            "brier": sum((p - (1.0 if c == observado else 0.0)) ** 2 for c, p in probabilidades.items())}


def metricas_superbalota(artefacto: dict, superbalota_observada: int | None) -> dict | None:
    bloque = artefacto.get("superbalota")
    if not bloque or superbalota_observada is None:
        return None
    ranking = bloque["pronostico"]["ranking"]
    modelo = metricas_multiclase({f["superbalota"]: f["probabilidad"] for f in ranking}, superbalota_observada)
    uniforme = metricas_multiclase({f["superbalota"]: f["probabilidad_uniforme"] for f in ranking},
                                   superbalota_observada)
    return {"acierto": bloque["pronostico"]["sugerida"] == superbalota_observada,
            "log_loss": modelo["log_loss"], "log_loss_uniforme": uniforme["log_loss"],
            "brier": modelo["brier"], "brier_uniforme": uniforme["brier"]}


def metricas_colorloto(artefacto: dict, pares_observados: Sequence) -> dict:
    ranking = artefacto["pronostico"]["ranking_de_pares"]
    modelo = {(f["numero"], f["color"]): f["probabilidad"] for f in ranking}
    uniforme = {(f["numero"], f["color"]): f["probabilidad_uniforme"] for f in ranking}
    pares = [tuple(p) for p in pares_observados]
    if any(p not in modelo for p in pares):
        raise ObjetivoNoEvaluableError("el resultado trae un color o par fuera de la paleta del artefacto")
    m = colorloto.metricas_de_objetivo(modelo, pares)
    u = colorloto.metricas_de_objetivo(uniforme, pares)
    return {"log_loss": m["log_loss_por_balota"], "log_loss_uniforme": u["log_loss_por_balota"],
            "brier": m["brier_por_balota"], "brier_uniforme": u["brier_por_balota"],
            "log_loss_multiconjunto": m["log_loss_multiconjunto"],
            "log_loss_multiconjunto_uniforme": u["log_loss_multiconjunto"], "balotas": len(pares)}
