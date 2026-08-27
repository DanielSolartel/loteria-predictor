"""
Motor de repeticiones entre sorteos (Paso 10).

Analiza cuántos números principales de un sorteo coinciden con los
del sorteo INMEDIATAMENTE anterior. Sigue siendo, como todo el motor,
estadística puramente DESCRIPTIVA e histórica:

    - Un sorteo con muchos números repetidos respecto al anterior NO
      implica que el siguiente vaya a repetir menos.
    - Un sorteo sin ningún número repetido NO implica que "ahora
      debería repetirse" en el siguiente.
    - Ningún número tiene mayor o menor probabilidad de repetirse por
      lo observado en el pasado -es la misma falacia del jugador ya
      señalada en atrasos.py y consecutivos.py, aplicada ahora a la
      relación entre dos sorteos en vez de a un número aislado.

Definición de "sorteos consecutivos" (deliberadamente estricta):
una transición solo es válida cuando

    numero_sorteo_actual == numero_sorteo_anterior + 1

Un hueco en la numeración (p.ej. 101 -> 105, si 102-104 no se
importaron) NO SE CUENTA como una transición de 0 repetidos -sería
inventar una comparación entre sorteos que en la realidad no son
consecutivos. Simplemente se excluye de la tabulación, sin error:
un hueco de importación ya es detectado y reportado por otras
herramientas (`detectar_huecos_serie_historica`, `ValidarIntegridadDatos`);
este módulo no lo vuelve a señalar, solo evita usarlo incorrectamente.

ColorLoto se compara como MULTICONJUNTO, no como conjunto de valores
distintos: permite repetición dentro de un mismo sorteo (6 balotas
físicas), así que la intersección debe contar multiplicidades -dos
apariciones de "5" en ambos sorteos aportan 2 al conteo de repetidos,
no 1. Ver `_interseccion_multiconjunto`.

Reutiliza `tabular_conteo_por_sorteo` (tabulacion.py) para la
tabulación final. Salvedad semántica explícita: su parámetro
`total_sorteos` aquí NO es la cantidad de sorteos analizados, sino la
CANTIDAD DE TRANSICIONES VÁLIDAS (transiciones = sorteos - 1, menos
las excluidas por huecos) -la función en sí es genérica (tabula
cualquier secuencia de enteros contra un denominador explícito) y no
le importa qué represente ese denominador, así que reutilizarla aquí
es correcto, pero el nombre del parámetro sería engañoso sin esta
aclaración.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.tabulacion import tabular_conteo_por_sorteo
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico


def _validar_rango(valores: Sequence[int], rango_min: int, rango_max: int, etiqueta: str) -> None:
    fuera_de_rango = [v for v in valores if not (rango_min <= v <= rango_max)]
    if fuera_de_rango:
        raise ValueError(
            f"{etiqueta}: valores fuera del rango [{rango_min},{rango_max}]: {sorted(set(fuera_de_rango))}"
        )


def _transiciones_validas(historico: Sequence) -> list[tuple]:
    """Ordena una COPIA por numero_sorteo (nunca muta `historico`) y
    devuelve los pares (anterior, actual) que cumplen
    numero_sorteo_actual == numero_sorteo_anterior + 1. Dos
    resultados con el mismo numero_sorteo (no debería ocurrir por la
    restricción UNIQUE de la base de datos, pero esta función es
    defensiva) quedan excluidos de forma natural: la diferencia es 0,
    no 1, así que nunca se confunden con una transición válida."""
    ordenados = sorted(historico, key=lambda r: r.numero_sorteo)
    return [
        (anterior, actual)
        for anterior, actual in zip(ordenados, ordenados[1:])
        if actual.numero_sorteo == anterior.numero_sorteo + 1
    ]


def _interseccion_multiconjunto(anterior: Sequence[int], actual: Sequence[int]) -> int:
    """Cantidad de elementos en común entre dos multiconjuntos,
    contando multiplicidad: sum(min(cuenta_anterior[v], cuenta_actual[v])).
    Con listas sin repetición (MiLoto/Baloto/Revancha) esto coincide
    exactamente con el tamaño de la intersección de conjuntos -la
    misma fórmula sirve para ambos casos sin ninguna rama especial."""
    contador_anterior = Counter(anterior)
    contador_actual = Counter(actual)
    return sum((contador_anterior & contador_actual).values())


def calcular_repeticiones_entre_sorteos(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """valor = cantidad de números principales que coinciden con el
    sorteo inmediatamente anterior (transición estricta, ver
    docstring del módulo), tabulado 0..K. Nunca la superbalota -ver
    calcular_repeticion_superbalota_entre_sorteos."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_repeticiones_entre_sorteos")

    transiciones = _transiciones_validas(historico)
    conteos = [_interseccion_multiconjunto(anterior.numeros, actual.numeros) for anterior, actual in transiciones]

    return tabular_conteo_por_sorteo(conteos, cantidad_numeros, len(transiciones))


def calcular_repeticion_superbalota_entre_sorteos(
    resultados: Sequence[ResultadoNumerico], hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """valor = "0" (superbalota distinta) | "1" (superbalota igual a
    la del sorteo inmediatamente anterior). Una transición donde
    cualquiera de las dos superbalotas es None no participa -no se
    cuenta como "0" ni como "1", simplemente se excluye, igual
    criterio que un hueco temporal."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    transiciones = _transiciones_validas(historico)

    transiciones_con_dato = [
        (anterior, actual) for anterior, actual in transiciones
        if anterior.superbalota is not None and actual.superbalota is not None
    ]
    conteos = [
        1 if anterior.superbalota == actual.superbalota else 0
        for anterior, actual in transiciones_con_dato
    ]

    return tabular_conteo_por_sorteo(conteos, 1, len(transiciones_con_dato))


def calcular_repeticiones_entre_sorteos_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Igual que calcular_repeticiones_entre_sorteos, pero sobre los
    NÚMEROS de las balotas (ignorando color) y usando intersección de
    MULTICONJUNTOS -ver docstring del módulo para la justificación
    completa. Un número que aparece dos veces en ambos sorteos aporta
    2 al conteo, no 1."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_repeticiones_entre_sorteos_colorloto")

    transiciones = _transiciones_validas(historico)
    conteos = [
        _interseccion_multiconjunto([n for n, _ in anterior.pares], [n for n, _ in actual.pares])
        for anterior, actual in transiciones
    ]

    return tabular_conteo_por_sorteo(conteos, cantidad_balotas, len(transiciones))
