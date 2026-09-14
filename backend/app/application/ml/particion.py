"""
Particion cronologica walk-forward -Etapa AE-36, validada.

Nunca usa `train_test_split` aleatorio, nunca baraja sorteos. Cada
sorteo objetivo es un grupo indivisible -todas sus filas
(`(sorteo_objetivo, numero_candidato)`) quedan siempre en el mismo
lado de cualquier corte, porque los cortes se deciden sobre
`sorteos_objetivo` (ints), nunca sobre indices de filas."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.ml.tipos import DatasetSupervisado, FilaCandidato, LimitesTemporales

PROPORCION_TEST_FINAL = 0.20
TAMANO_BLOQUE_VALIDACION = 10
"""Cantidad de sorteos objetivo por bloque de validacion
walk-forward, sobre el 80% previo al test final -Etapa AE-36. Valor
conservador y fijo, no ajustado por busqueda de hiperparametros."""


@dataclass(frozen=True)
class ParticionTemporal:
    limites: LimitesTemporales
    filas_entrenamiento_por_bloque: tuple[tuple[FilaCandidato, ...], ...]
    filas_validacion_por_bloque: tuple[tuple[FilaCandidato, ...], ...]
    filas_test_final: tuple[FilaCandidato, ...]


def construir_particion_walk_forward(dataset: DatasetSupervisado) -> ParticionTemporal:
    """Construye la particion walk-forward expansiva sobre
    `dataset.sorteos_objetivo` (ya ascendente, sin duplicados,
    garantizado por `dataset.py`). El ultimo `PROPORCION_TEST_FINAL`
    de los sorteos elegibles se reserva como test final -nunca
    participa en ningun bloque de entrenamiento o validacion."""
    sorteos = dataset.sorteos_objetivo
    total = len(sorteos)
    if total == 0:
        raise ValueError(f"Dataset de {dataset.codigo_juego} no tiene ningun sorteo elegible")

    indice_corte_test = total - max(1, round(total * PROPORCION_TEST_FINAL))
    sorteos_previos_a_test = sorteos[:indice_corte_test]
    sorteos_test = sorteos[indice_corte_test:]
    if not sorteos_test:
        raise ValueError(f"Dataset de {dataset.codigo_juego} no tiene suficientes sorteos para separar un test final")

    filas_por_sorteo: dict[int, list[FilaCandidato]] = {s: [] for s in sorteos}
    for fila in dataset.filas:
        filas_por_sorteo[fila.sorteo_objetivo].append(fila)

    bloques_validacion: list[tuple[int, ...]] = []
    inicio = 0
    while inicio < len(sorteos_previos_a_test):
        fin = min(inicio + TAMANO_BLOQUE_VALIDACION, len(sorteos_previos_a_test))
        bloques_validacion.append(sorteos_previos_a_test[inicio:fin])
        inicio = fin

    entrenamiento_bloques: list[tuple[int, int]] = []
    validacion_bloques: list[tuple[int, int]] = []
    filas_entrenamiento_por_bloque: list[tuple[FilaCandidato, ...]] = []
    filas_validacion_por_bloque: list[tuple[FilaCandidato, ...]] = []

    for i, bloque_val in enumerate(bloques_validacion):
        if i == 0:
            continue  # el primer bloque no tiene nada previo para entrenar -se salta como bloque evaluable
        sorteos_entrenamiento = sorteos_previos_a_test[:sum(len(b) for b in bloques_validacion[:i])]
        if not sorteos_entrenamiento:
            continue
        entrenamiento_bloques.append((sorteos_entrenamiento[0], sorteos_entrenamiento[-1]))
        validacion_bloques.append((bloque_val[0], bloque_val[-1]))
        filas_entrenamiento_por_bloque.append(
            tuple(f for s in sorteos_entrenamiento for f in filas_por_sorteo[s])
        )
        filas_validacion_por_bloque.append(tuple(f for s in bloque_val for f in filas_por_sorteo[s]))

    filas_test_final = tuple(f for s in sorteos_test for f in filas_por_sorteo[s])

    limites = LimitesTemporales(
        primer_sorteo_elegible=sorteos[0],
        calentamiento_hasta=dataset.filas[0].calculado_hasta_sorteo if dataset.filas else sorteos[0],
        entrenamiento_bloques=tuple(entrenamiento_bloques),
        validacion_bloques=tuple(validacion_bloques),
        test_inicio=sorteos_test[0],
        test_fin=sorteos_test[-1],
    )

    return ParticionTemporal(
        limites=limites,
        filas_entrenamiento_por_bloque=tuple(filas_entrenamiento_por_bloque),
        filas_validacion_por_bloque=tuple(filas_validacion_por_bloque),
        filas_test_final=filas_test_final,
    )
