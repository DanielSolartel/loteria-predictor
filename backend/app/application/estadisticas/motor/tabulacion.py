"""
Tabulación — conteo derivado por sorteo, tabulado como distribución.

Extraído a su propio módulo tras la Etapa G: `distribuciones.py` ya
tenía este patrón privado (`_distribucion_conteo_por_sorteo`), y
`consecutivos.py` necesitaba exactamente lo mismo -mismo
razonamiento que llevó a consolidar `corte_temporal.py`: mientras más
lugares reimplementen la misma lógica de tabulación por separado,
mayor el riesgo de que una futura corrección se aplique en un lugar
y no en otro.

El patrón en sí: muchos análisis de este motor calculan, PARA CADA
SORTEO, un conteo entero derivado (cuántos números son pares,
cuántos son bajos, cuántos pares consecutivos hay, cuál es la racha
más larga...), y luego quieren saber cuántos sorteos tuvieron cada
valor posible de ese conteo. Es la misma operación de tabulación en
todos los casos -la única diferencia es CÓMO se calculó el conteo por
sorteo, que es responsabilidad de quien llama, no de este módulo.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.application.estadisticas.tipos import FrecuenciaObservada


def tabular_conteo_por_sorteo(
    conteos_por_sorteo: Sequence[int], valor_maximo: int, total_sorteos: int,
) -> list[FrecuenciaObservada]:
    """Tabula, para cada valor posible 0..valor_maximo, cuántos
    sorteos tuvieron exactamente ese conteo. `total_sorteos` se
    recibe explícito (no se infiere de `len(conteos_por_sorteo)`)
    para que quien llama tenga control total sobre el denominador
    -en la práctica siempre coincide con `len(conteos_por_sorteo)`,
    pero mantenerlo como parámetro explícito evita cualquier
    ambigüedad si en el futuro alguien filtra `conteos_por_sorteo`
    antes de tabular."""
    contador = Counter(conteos_por_sorteo)
    filas = []
    for valor_posible in range(valor_maximo + 1):
        apariciones = contador.get(valor_posible, 0)
        frecuencia_relativa = (apariciones / total_sorteos) if total_sorteos else 0.0
        filas.append(
            FrecuenciaObservada(
                valor=str(valor_posible), apariciones=apariciones,
                total_sorteos=total_sorteos, frecuencia_relativa=frecuencia_relativa,
            )
        )
    return filas
