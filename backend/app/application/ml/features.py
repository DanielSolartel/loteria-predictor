"""
Features puramente retrospectivas -Etapa AE-36, validada.

Todas las funciones de este modulo reciben EXCLUSIVAMENTE el
historico ya ordenado y validado (`historico_util.validar_y_ordenar_historico`)
correspondiente a sorteos con `numero_sorteo < sorteo_objetivo` -nunca
reciben ni consultan el sorteo objetivo. El llamador (`dataset.py`)
es responsable de construir ese corte antes de invocar cualquier
funcion de aqui; ninguna funcion de este modulo conoce el concepto
de "sorteo objetivo"."""
from __future__ import annotations

from collections.abc import Sequence

from app.application.estadisticas.tipos import ResultadoNumerico


def frecuencia_historica(historico_previo: Sequence[ResultadoNumerico], numero_candidato: int) -> float:
    """Proporcion de sorteos de `historico_previo` en los que
    `numero_candidato` aparecio entre los numeros principales.
    Historico vacio -> 0.0 (nunca division por cero)."""
    if not historico_previo:
        return 0.0
    apariciones = sum(1 for r in historico_previo if numero_candidato in r.numeros)
    return apariciones / len(historico_previo)


def frecuencia_en_ventana(
    historico_previo: Sequence[ResultadoNumerico], numero_candidato: int, tamano_ventana: int,
) -> float:
    """Igual que `frecuencia_historica`, pero restringida a los
    ultimos `tamano_ventana` sorteos de `historico_previo` (los mas
    recientes, es decir los ultimos elementos de la secuencia ya
    ordenada ascendente). Si el historico disponible es menor que
    `tamano_ventana`, usa el historico completo disponible -nunca
    completa con ceros ni con sorteos futuros."""
    ventana = historico_previo[-tamano_ventana:] if tamano_ventana > 0 else []
    return frecuencia_historica(ventana, numero_candidato)


def sorteos_desde_ultima_aparicion(
    historico_previo: Sequence[ResultadoNumerico], numero_candidato: int,
) -> int | None:
    """Cuenta cuantos sorteos de `historico_previo` transcurrieron
    desde la ultima vez que `numero_candidato` aparecio (0 si
    aparecio en el ultimo sorteo disponible de `historico_previo`).
    `None` si `numero_candidato` nunca aparecio en todo
    `historico_previo` (incluye el caso de historico vacio)."""
    for distancia, resultado in enumerate(reversed(historico_previo)):
        if numero_candidato in resultado.numeros:
            return distancia
    return None


def aparecio_en_sorteo_anterior(
    historico_previo: Sequence[ResultadoNumerico], numero_candidato: int,
) -> int:
    """1 si `numero_candidato` aparecio en el ultimo sorteo de
    `historico_previo` (el mas cercano al objetivo), 0 en caso
    contrario -incluido el caso de historico vacio (0, nunca
    excepcion: ausencia de sorteo anterior no es una aparicion)."""
    if not historico_previo:
        return 0
    return 1 if numero_candidato in historico_previo[-1].numeros else 0
