"""
Metricas de evaluacion -Etapa AE-36, validada.

Log Loss y Brier Score se calculan sobre TODAS las filas
candidato-etiqueta (nunca agrupadas). Precision@5 y Recall@5 se
calculan agrupando por sorteo objetivo, con desempate determinista
por numero de candidato ascendente -nunca por el orden de llegada de
las filas ni por un desempate aleatorio."""
from __future__ import annotations

import math
from collections.abc import Sequence

from app.application.ml.tipos import FilaCandidato, MetricasEvaluacion

EPSILON_CLIP = 1e-6
"""Recorte de probabilidades antes de Log Loss -evita log(0) exacto
por una probabilidad de 0.0 o 1.0 exacta, sin alterar de forma
material ninguna probabilidad real."""


def _recortar(probabilidad: float) -> float:
    return min(max(probabilidad, EPSILON_CLIP), 1.0 - EPSILON_CLIP)


def calcular_log_loss(filas: Sequence[FilaCandidato], probabilidades: Sequence[float]) -> float:
    if len(filas) != len(probabilidades):
        raise ValueError("filas y probabilidades deben tener la misma longitud")
    if not filas:
        raise ValueError("no se puede calcular log loss sobre un conjunto vacio")
    total = 0.0
    for fila, prob in zip(filas, probabilidades):
        p = _recortar(prob)
        total += -(fila.etiqueta * math.log(p) + (1 - fila.etiqueta) * math.log(1 - p))
    return total / len(filas)


def calcular_brier_score(filas: Sequence[FilaCandidato], probabilidades: Sequence[float]) -> float:
    if len(filas) != len(probabilidades):
        raise ValueError("filas y probabilidades deben tener la misma longitud")
    if not filas:
        raise ValueError("no se puede calcular brier score sobre un conjunto vacio")
    total = sum((prob - fila.etiqueta) ** 2 for fila, prob in zip(filas, probabilidades))
    return total / len(filas)


def _top5_deterministico(filas_de_un_sorteo: list[tuple[FilaCandidato, float]]) -> list[FilaCandidato]:
    """Ordena por probabilidad descendente y, en empate, por
    `numero_candidato` ASCENDENTE -desempate determinista, nunca
    dependiente del orden de llegada de la lista."""
    ordenado = sorted(filas_de_un_sorteo, key=lambda par: (-par[1], par[0].numero_candidato))
    return [fila for fila, _ in ordenado[:5]]


def calcular_precision_recall_en_5(
    filas: Sequence[FilaCandidato], probabilidades: Sequence[float],
) -> tuple[float, float]:
    """Agrupa `filas` por `sorteo_objetivo`, toma el Top-5 por
    probabilidad (desempate ascendente por numero) de cada grupo, y
    promedia Precision@5/Recall@5 entre sorteos -nunca sobre filas
    individuales."""
    if len(filas) != len(probabilidades):
        raise ValueError("filas y probabilidades deben tener la misma longitud")

    por_sorteo: dict[int, list[tuple[FilaCandidato, float]]] = {}
    for fila, prob in zip(filas, probabilidades):
        por_sorteo.setdefault(fila.sorteo_objetivo, []).append((fila, prob))

    precisiones: list[float] = []
    recalls: list[float] = []
    for sorteo, pares in por_sorteo.items():
        top5 = _top5_deterministico(pares)
        aciertos = sum(1 for fila in top5 if fila.etiqueta == 1)
        total_positivas = sum(1 for fila, _ in pares if fila.etiqueta == 1)
        precisiones.append(aciertos / len(top5) if top5 else 0.0)
        recalls.append(aciertos / total_positivas if total_positivas else 0.0)

    precision_promedio = sum(precisiones) / len(precisiones) if precisiones else 0.0
    recall_promedio = sum(recalls) / len(recalls) if recalls else 0.0
    return precision_promedio, recall_promedio


def evaluar(filas: Sequence[FilaCandidato], probabilidades: Sequence[float]) -> MetricasEvaluacion:
    """Construye el reporte completo de metricas sobre un bloque de
    filas -funcion unica que el resto del pipeline (modelo y
    baselines) invoca para producir un `MetricasEvaluacion`
    consistente."""
    precision5, recall5 = calcular_precision_recall_en_5(filas, probabilidades)
    return MetricasEvaluacion(
        log_loss=calcular_log_loss(filas, probabilidades),
        brier_score=calcular_brier_score(filas, probabilidades),
        precision_en_5=precision5,
        recall_en_5=recall5,
        total_sorteos=len({f.sorteo_objetivo for f in filas}),
        total_filas=len(filas),
    )
