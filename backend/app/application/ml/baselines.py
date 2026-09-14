"""
Baselines honestos -Etapa AE-36, validada.

Los cuatro operan exclusivamente sobre el prefijo de historico
anterior a cada sorteo objetivo -mismo contrato anti-fuga que
`features.py`; ninguno usa el conjunto de test para ajustar su
propio comportamiento. Todas las probabilidades se recortan lejos de
0/1 exactos para permitir Log Loss finito, igual que el modelo real."""
from __future__ import annotations

from collections.abc import Sequence

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.features import (
    aparecio_en_sorteo_anterior,
    frecuencia_en_ventana,
    frecuencia_historica,
)
from app.application.ml.metricas import EPSILON_CLIP, evaluar, _recortar
from app.application.ml.tipos import FilaCandidato, MetricasEvaluacion, ResultadoBaseline

TAMANO_VENTANA_BASELINE_RECIENTE = 20
"""Ventana fija y documentada del baseline de frecuencia reciente
-Etapa AE-36; deliberadamente igual a una de las features del
modelo, nunca ajustada contra el test final."""

SUAVIZADO_LAPLACE = 1.0
"""Suavizado aditivo (Laplace/add-one) aplicado a los baselines de
frecuencia -evita probabilidades exactamente 0 incluso cuando un
numero nunca fue observado en la ventana correspondiente."""


def _suavizar(apariciones: int, total: int, tamano_rango: int) -> float:
    """`(apariciones + SUAVIZADO_LAPLACE) / (total + SUAVIZADO_LAPLACE * tamano_rango)`
    -suavizado de Laplace estandar sobre `tamano_rango` categorias
    posibles (los numeros candidatos), nunca sobre 2 categorias."""
    return (apariciones + SUAVIZADO_LAPLACE) / (total + SUAVIZADO_LAPLACE * tamano_rango)


def _reconstruir_historico_previo_por_fila(
    fila: FilaCandidato, historico_ordenado: Sequence[ResultadoNumerico],
) -> list[ResultadoNumerico]:
    """Reconstruye, a partir de `calculado_hasta_sorteo` (ya
    guardado en la fila con disciplina anti-fuga por `dataset.py`),
    exactamente el mismo prefijo de historico que se uso para
    calcular las features de esa fila -los baselines nunca reciben
    una fecha de corte distinta a la que ya valido el dataset."""
    return [r for r in historico_ordenado if r.numero_sorteo <= fila.calculado_hasta_sorteo]


def baseline_uniforme(
    filas: Sequence[FilaCandidato], rango_min: int, rango_max: int, cantidad_numeros: int,
) -> ResultadoBaseline:
    tamano_rango = rango_max - rango_min + 1
    probabilidad = cantidad_numeros / tamano_rango
    probabilidades = [probabilidad] * len(filas)
    return ResultadoBaseline(
        nombre="uniforme",
        descripcion=f"cantidad_numeros/tamano_rango = {cantidad_numeros}/{tamano_rango}",
        metricas=evaluar(filas, probabilidades),
    )


def baseline_frecuencia_acumulada(
    filas: Sequence[FilaCandidato], historico_ordenado: Sequence[ResultadoNumerico],
    rango_min: int, rango_max: int,
) -> ResultadoBaseline:
    tamano_rango = rango_max - rango_min + 1
    probabilidades = []
    for fila in filas:
        previo = _reconstruir_historico_previo_por_fila(fila, historico_ordenado)
        apariciones = round(frecuencia_historica(previo, fila.numero_candidato) * len(previo)) if previo else 0
        probabilidades.append(_recortar(_suavizar(apariciones, len(previo), tamano_rango)))
    return ResultadoBaseline(
        nombre="frecuencia_acumulada",
        descripcion="frecuencia historica completa (solo pasado), suavizado de Laplace",
        metricas=evaluar(filas, probabilidades),
    )


def baseline_frecuencia_ventana_reciente(
    filas: Sequence[FilaCandidato], historico_ordenado: Sequence[ResultadoNumerico],
    rango_min: int, rango_max: int,
) -> ResultadoBaseline:
    tamano_rango = rango_max - rango_min + 1
    probabilidades = []
    for fila in filas:
        previo = _reconstruir_historico_previo_por_fila(fila, historico_ordenado)
        ventana = previo[-TAMANO_VENTANA_BASELINE_RECIENTE:]
        apariciones = round(frecuencia_historica(ventana, fila.numero_candidato) * len(ventana)) if ventana else 0
        probabilidades.append(_recortar(_suavizar(apariciones, len(ventana), tamano_rango)))
    return ResultadoBaseline(
        nombre=f"frecuencia_ventana_{TAMANO_VENTANA_BASELINE_RECIENTE}",
        descripcion=f"frecuencia de los ultimos {TAMANO_VENTANA_BASELINE_RECIENTE} sorteos anteriores, suavizado de Laplace",
        metricas=evaluar(filas, probabilidades),
    )


def baseline_sorteo_anterior(
    filas: Sequence[FilaCandidato], historico_ordenado: Sequence[ResultadoNumerico],
    rango_min: int, rango_max: int, cantidad_numeros: int,
) -> ResultadoBaseline:
    """Control ingenuo: asigna una probabilidad alta (pero nunca
    exactamente 1.0) a los numeros del sorteo inmediatamente
    anterior, y una probabilidad baja (nunca exactamente 0.0, ni
    ajustada contra el test) al resto -transformacion fija, nunca
    calibrada contra el conjunto final."""
    tamano_rango = rango_max - rango_min + 1
    probabilidad_alta = 1.0 - EPSILON_CLIP * 10
    probabilidad_baja = max(EPSILON_CLIP * 10, (cantidad_numeros - 1) / (tamano_rango - cantidad_numeros)) if tamano_rango > cantidad_numeros else EPSILON_CLIP * 10
    probabilidad_baja = min(probabilidad_baja, 0.5)

    probabilidades = []
    for fila in filas:
        previo = _reconstruir_historico_previo_por_fila(fila, historico_ordenado)
        aparecio = aparecio_en_sorteo_anterior(previo, fila.numero_candidato)
        probabilidades.append(_recortar(probabilidad_alta if aparecio else probabilidad_baja))
    return ResultadoBaseline(
        nombre="sorteo_anterior",
        descripcion=(
            f"probabilidad {probabilidad_alta:.4f} si aparecio en el sorteo inmediatamente anterior, "
            f"{probabilidad_baja:.4f} en caso contrario -transformacion fija, nunca ajustada con el test"
        ),
        metricas=evaluar(filas, probabilidades),
    )


def evaluar_todos_los_baselines(
    filas: Sequence[FilaCandidato], historico_ordenado: Sequence[ResultadoNumerico],
    rango_min: int, rango_max: int, cantidad_numeros: int,
) -> tuple[ResultadoBaseline, ...]:
    return (
        baseline_uniforme(filas, rango_min, rango_max, cantidad_numeros),
        baseline_frecuencia_acumulada(filas, historico_ordenado, rango_min, rango_max),
        baseline_frecuencia_ventana_reciente(filas, historico_ordenado, rango_min, rango_max),
        baseline_sorteo_anterior(filas, historico_ordenado, rango_min, rango_max, cantidad_numeros),
    )
