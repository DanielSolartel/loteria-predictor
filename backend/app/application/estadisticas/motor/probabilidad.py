"""
Motor de probabilidad teórica (Paso 5).

Igual que el resto del motor: funciones puras, sin conocimiento de
infraestructura. Ninguna función de este módulo recibe datos
históricos -eso es, por definición, imposible de mezclar aquí, ya que
ninguna firma acepta una lista de resultados. Solo enteros, derivados
exclusivamente de las reglas del juego.

Decisión de diseño (aprobada en el diseño de la Etapa D): NO existe
una función `probabilidad_combinacion_exacta(..., repeticion: bool)`.
`ColorLotoGame.sample_space_size()` documenta explícitamente que su
fórmula con repetición es un supuesto sin verificar contra el
reglamento oficial completo -reimplementar esa misma combinatoria
aquí duplicaría un supuesto que el propio dominio ya aisló en un
solo lugar, rompiendo la promesa de que una futura corrección solo
requiere tocar `ColorLotoGame`. En su lugar:

  - `probabilidad_combinacion_exacta_sin_repeticion` cubre el caso
    seguro y no ambiguo (K distintos de N, sin reemplazo) -MiLoto,
    Baloto, Baloto Revancha.
  - `probabilidad_combinacion_exacta_desde_espacio_muestral` cubre
    CUALQUIER juego, incluido ColorLoto, recibiendo el tamaño del
    espacio muestral ya resuelto por el dominio (típicamente
    `LotteryGame.sample_space_size()`, en una etapa posterior de
    orquestación) -esta función no decide nada sobre repetición,
    rango, ni fórmula: solo transforma un tamaño ya conocido en
    1/tamaño.
"""
from __future__ import annotations

import math

from app.application.estadisticas.motor.frecuencia import frecuencia_relativa_esperada
from app.application.estadisticas.tipos import ProbabilidadTeorica


def probabilidad_seleccion_individual(universo: int, seleccion: int) -> ProbabilidadTeorica:
    """K/N: probabilidad teórica de que un elemento específico del
    pool sea seleccionado, bajo azar uniforme. Reutiliza
    frecuencia_relativa_esperada de motor.frecuencia -misma fórmula,
    una sola fuente de verdad- envuelta explícitamente como
    ProbabilidadTeorica (nunca como FrecuenciaObservada: esto es
    matemática derivada de las reglas, no un conteo histórico).

    Válida sin distinción para: número principal específico,
    superbalota específica, color específico de ColorLoto, número
    específico de ColorLoto, par específico de ColorLoto -la
    separación entre pools ocurre en los argumentos de la llamada
    (universo/seleccion distintos), no en funciones separadas: no hay
    extracción de datos que lo justifique, a diferencia de
    calcular_frecuencia_superbalota en frecuencia.py.

    ValueError si universo <= 0 (delegado a frecuencia_relativa_esperada)."""
    probabilidad = frecuencia_relativa_esperada(seleccion, universo)
    return ProbabilidadTeorica(
        valor="*",
        probabilidad=probabilidad,
        metodo=f"K/N = {seleccion}/{universo}",
    )


def probabilidad_combinacion_exacta_sin_repeticion(universo: int, seleccion: int) -> ProbabilidadTeorica:
    """1/C(N,K): probabilidad de una combinación exacta de K
    elementos DISTINTOS elegidos de N, sin importar el orden, sin
    reemplazo. Fórmula segura y no ambigua -válida para MiLoto,
    Baloto, Baloto Revancha (pool principal) y, en general, cualquier
    selección sin repetición.

    NO válida para ColorLoto (permite repetición) -usar
    probabilidad_combinacion_exacta_desde_espacio_muestral en su
    lugar.

    ValueError si: universo <= 0, seleccion < 0, o
    seleccion > universo (no se pueden elegir más elementos distintos
    de los que existen en el universo)."""
    if universo <= 0:
        raise ValueError(f"universo debe ser positivo, se recibió universo={universo}")
    if seleccion < 0:
        raise ValueError(f"seleccion no puede ser negativa, se recibió seleccion={seleccion}")
    if seleccion > universo:
        raise ValueError(
            f"seleccion ({seleccion}) no puede ser mayor que universo ({universo}) "
            f"sin repetición -no existen tantos elementos distintos"
        )

    combinaciones = math.comb(universo, seleccion)
    return ProbabilidadTeorica(
        valor="*",
        probabilidad=1 / combinaciones,
        metodo=f"1/C({universo},{seleccion})",
    )


def probabilidad_combinacion_exacta_desde_espacio_muestral(tamano_espacio_muestral: int) -> ProbabilidadTeorica:
    """1/tamaño: transforma un espacio muestral YA RESUELTO por el
    dominio en una probabilidad. No conoce ni decide si hubo
    repetición, el rango, la cantidad de elementos, ni la fórmula
    usada para llegar a ese tamaño -su única responsabilidad es esta
    división. Es la forma universal, válida para cualquier juego
    (incluido ColorLoto), precisamente porque delega toda la
    combinatoria a quien la llama.

    ValueError si tamano_espacio_muestral <= 0."""
    if tamano_espacio_muestral <= 0:
        raise ValueError(
            f"tamano_espacio_muestral debe ser positivo, se recibió {tamano_espacio_muestral}"
        )

    return ProbabilidadTeorica(
        valor="*",
        probabilidad=1 / tamano_espacio_muestral,
        metodo=(
            f"1/{tamano_espacio_muestral} (tamaño de espacio muestral provisto externamente)"
        ),
    )
