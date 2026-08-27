"""
Motor de coocurrencia (Paso 11).

Analiza qué pares y tríos de números aparecieron JUNTOS dentro del
mismo sorteo, y con qué frecuencia -nunca la superbalota (K=1: no se
pueden formar pares/tríos de un solo elemento).

Ruptura deliberada con el patrón "incluir todo el universo teórico,
incluso con cero apariciones" usado en frecuencia.py/distribuciones.py/
consecutivos.py: el universo de pares (hasta C(43,2)=903) y sobre todo
de tríos (hasta C(43,3)=12.341) es demasiado grande para reportarlo
completo -mayormente serían filas en cero, sin valor informativo. Este
módulo reporta ÚNICAMENTE combinaciones observadas al menos una vez
(soporte > 0), ordenadas por soporte descendente.

Frecuencia esperada y lift (Baloto/Revancha/MiLoto, sin repetición):
derivados de la distribución hipergeométrica -la probabilidad de que
dos (o tres) números ESPECÍFICOS caigan ambos en una selección
aleatoria uniforme de K de N:

    P(pareja) = C(N-2, K-2) / C(N, K)
    P(trío)   = C(N-3, K-3) / C(N, K)

Es la misma familia de combinatoria seleccionar-sin-reemplazo que
`domain.games.standard_number_game.StandardNumberGame.sample_space_size()`
ya usa (math.comb), y la misma que `probabilidad.py` usa para
`probabilidad_combinacion_exacta_sin_repeticion` -ninguna fórmula
nueva, ningún supuesto nuevo que verificar.

ColorLoto (K balotas CON repetición permitida): `ColorLotoGame.
sample_space_size()` documenta su propia fórmula de combinaciones-
con-repetición como un supuesto SIN VERIFICAR contra el reglamento
oficial completo. Calcular una frecuencia esperada de coocurrencia
bajo ese modelo requeriría asumir como cierto algo que el propio
dominio no da por cierto -mismo criterio de cautela ya aplicado en
`probabilidad.py` (Etapa D): NO se calcula. Para ColorLoto,
`frecuencia_esperada` y `lift` quedan en None; solo se reporta
`soporte`/`frecuencia_relativa`, que son puramente descriptivos y no
dependen de ningún supuesto combinatorio.

Advertencia estadística, igual que en el resto del motor: un lift
alto en el histórico NO implica que esa pareja/trío vaya a repetirse
con mayor probabilidad en el siguiente sorteo -es frecuencia
observada, no una predicción. Este módulo tampoco declara nada
"significativo": eso exige control de comparaciones múltiples (con
cientos de pares posibles, algunos lift altos aparecerán por puro
azar) y es responsabilidad exclusiva del Paso 12, todavía no
implementado.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import combinations

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.tipos import MetricaAsociacion, ResultadoColorLoto, ResultadoNumerico


def _validar_rango(valores: Sequence[int], rango_min: int, rango_max: int, etiqueta: str) -> None:
    fuera_de_rango = [v for v in valores if not (rango_min <= v <= rango_max)]
    if fuera_de_rango:
        raise ValueError(
            f"{etiqueta}: valores fuera del rango [{rango_min},{rango_max}]: {sorted(set(fuera_de_rango))}"
        )


def _frecuencia_esperada_hipergeometrica(n: int, k: int, tamano_combinacion: int) -> float | None:
    """P(los `tamano_combinacion` elementos específicos caen todos en
    una selección aleatoria de k de n, sin reemplazo). None si la
    combinatoria no está definida (k < tamano_combinacion, o n <= 0)."""
    if n <= 0 or k < tamano_combinacion or n < k:
        return None
    numerador = math.comb(n - tamano_combinacion, k - tamano_combinacion)
    denominador = math.comb(n, k)
    if denominador == 0:
        return None
    return numerador / denominador


def _contar_coocurrencias_crudo(
    listas_de_numeros: list[list[int]], tamano_combinacion: int,
) -> dict[tuple[int, ...], int]:
    """Conteo crudo: para cada combinación de `tamano_combinacion`
    elementos que coocurrió al menos una vez, cuántos sorteos
    distintos la contienen. Los números se deduplican DENTRO de cada
    sorteo antes de generar combinaciones (ColorLoto: un número
    repetido en el mismo sorteo nunca forma una combinación consigo
    mismo). Extraído como su propio helper (Etapa K) para que
    `independencia.py` pueda reutilizar el mismo conteo y completar
    el universo teórico con ceros, sin duplicar esta lógica ni
    cambiar el comportamiento de `_tabular_coocurrencia`, que sigue
    reportando únicamente lo observado."""
    conteo: dict[tuple[int, ...], int] = {}
    for numeros in listas_de_numeros:
        distintos = sorted(set(numeros))
        for combinacion in combinations(distintos, tamano_combinacion):
            conteo[combinacion] = conteo.get(combinacion, 0) + 1
    return conteo


def _tabular_coocurrencia(
    listas_de_numeros: list[list[int]], tamano_combinacion: int, total_sorteos: int,
    frecuencia_esperada: float | None,
) -> list[MetricaAsociacion]:
    """Genera todas las combinaciones de `tamano_combinacion`
    elementos DENTRO de cada sorteo (deduplicadas primero, para que
    un número repetido dentro del mismo sorteo -ColorLoto- nunca
    forme una combinación consigo mismo), cuenta cuántos sorteos
    distintos las contienen, y devuelve solo las observadas
    (soporte > 0), ordenadas por soporte descendente. Comportamiento
    sin cambios respecto a la Etapa I -delega el conteo en
    `_contar_coocurrencias_crudo`, pero sigue filtrando a lo
    observado, igual que siempre."""
    conteo = _contar_coocurrencias_crudo(listas_de_numeros, tamano_combinacion)

    filas = []
    for combinacion, soporte in conteo.items():
        frecuencia_relativa = (soporte / total_sorteos) if total_sorteos else 0.0
        lift = None
        if frecuencia_esperada is not None and frecuencia_esperada > 0:
            lift = frecuencia_relativa / frecuencia_esperada
        filas.append(
            MetricaAsociacion(
                elementos=tuple(str(n) for n in combinacion),
                soporte=soporte,
                total_sorteos=total_sorteos,
                frecuencia_relativa=frecuencia_relativa,
                frecuencia_esperada=frecuencia_esperada,
                lift=lift,
            )
        )

    filas.sort(key=lambda f: f.soporte, reverse=True)
    return filas


def calcular_coocurrencia_pares(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[MetricaAsociacion]:
    """Pares de números principales observados juntos al menos una
    vez. frecuencia_esperada/lift vía hipergeométrica (sin repetición)."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_coocurrencia_pares")

    universo = rango_max - rango_min + 1
    frecuencia_esperada = _frecuencia_esperada_hipergeometrica(universo, cantidad_numeros, 2)

    listas = [list(r.numeros) for r in historico]
    return _tabular_coocurrencia(listas, 2, len(historico), frecuencia_esperada)


def calcular_coocurrencia_trios(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[MetricaAsociacion]:
    """Tríos de números principales observados juntos al menos una
    vez. frecuencia_esperada/lift vía hipergeométrica (sin repetición)."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_coocurrencia_trios")

    universo = rango_max - rango_min + 1
    frecuencia_esperada = _frecuencia_esperada_hipergeometrica(universo, cantidad_numeros, 3)

    listas = [list(r.numeros) for r in historico]
    return _tabular_coocurrencia(listas, 3, len(historico), frecuencia_esperada)


def calcular_coocurrencia_pares_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[MetricaAsociacion]:
    """Sobre los NÚMEROS de las balotas (ignorando color), números
    deduplicados dentro de cada sorteo antes de generar pares -una
    repetición no forma pareja consigo misma. frecuencia_esperada y
    lift quedan en None (ver docstring del módulo)."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_coocurrencia_pares_colorloto")

    listas = [[n for n, _ in r.pares] for r in historico]
    return _tabular_coocurrencia(listas, 2, len(historico), frecuencia_esperada=None)


def calcular_coocurrencia_trios_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[MetricaAsociacion]:
    """Igual que calcular_coocurrencia_pares_colorloto, para tríos."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_coocurrencia_trios_colorloto")

    listas = [[n for n, _ in r.pares] for r in historico]
    return _tabular_coocurrencia(listas, 3, len(historico), frecuencia_esperada=None)


def calcular_coocurrencia_pares_colores(
    resultados: Sequence[ResultadoColorLoto], hasta_numero_sorteo: int | None = None,
) -> list[MetricaAsociacion]:
    """Pares de COLORES (no números) observados juntos en el mismo
    sorteo, al menos una vez (Etapa M). Basado en CONJUNTO -los
    colores se deduplican dentro de cada sorteo antes de generar
    pares, mismo precedente exacto que calcular_coocurrencia_pares
    para números: un color repetido dentro del mismo sorteo nunca
    forma una pareja consigo mismo. Reutiliza _tabular_coocurrencia
    sin ningún cambio -es agnóstica al tipo de elemento (str(color)
    es un no-op sobre un string).

    frecuencia_esperada y lift quedan en None: la probabilidad
    conjunta de dos colores específicos depende del mismo modelo de
    repetición sin verificar que ya bloqueó frecuencia_esperada/lift
    para pares de NÚMEROS de ColorLoto (Etapa I) -no se inventa una
    fórmula nueva aquí tampoco."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    listas_de_colores = [[c for _, c in r.pares] for r in historico]
    return _tabular_coocurrencia(listas_de_colores, 2, len(historico), frecuencia_esperada=None)


def calcular_coocurrencia_trios_colores(
    resultados: Sequence[ResultadoColorLoto], hasta_numero_sorteo: int | None = None,
) -> list[MetricaAsociacion]:
    """Igual que calcular_coocurrencia_pares_colores, para tríos de
    colores."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    listas_de_colores = [[c for _, c in r.pares] for r in historico]
    return _tabular_coocurrencia(listas_de_colores, 3, len(historico), frecuencia_esperada=None)
