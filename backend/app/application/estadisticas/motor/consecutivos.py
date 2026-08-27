"""
Motor de consecutivos (Paso 9).

Analiza si el conjunto de números principales de cada sorteo contiene
números consecutivos entre sí (n, n+1) -nunca la superbalota (K=1: no
hay con qué ser consecutivo dentro de la misma selección, mismo
criterio de exclusión ya aplicado en distribuciones.py).

Tres métricas, cada una resolviendo una parte distinta de lo pedido
originalmente ("cantidad de números consecutivos; pares consecutivos;
tríos consecutivos; distribución de combinaciones con consecutivos"):

  - pares consecutivos: cuántos pares adyacentes (n, n+1 ambos
    presentes) hay en el sorteo.
  - tríos consecutivos: cuántos tríos adyacentes (n, n+1, n+2 los
    tres presentes) hay en el sorteo.
  - racha máxima: la longitud de la racha consecutiva más larga del
    sorteo -responde de un solo golpe tanto "cantidad de números
    consecutivos" (te dice cuántos números tiene el grupo más grande)
    como "distribución de combinaciones con consecutivos" (¿cuántos
    sorteos tuvieron alguna racha de 2+, de 3+?).

Misma advertencia que en atrasos.py y distribuciones.py: esto sigue
siendo frecuencia histórica de una propiedad derivada, nunca evidencia
de que las combinaciones consecutivas sean "menos probables" -eso solo
puede evaluarse comparando contra la probabilidad matemática (Paso
12, fuera de esta etapa). No asumir nada sobre qué tan "aleatoria"
parece una combinación por tener o no números consecutivos.

ColorLoto permite repetición dentro del sorteo -los números se
DEDUPLICAN antes de buscar rachas: dos apariciones del mismo número no
son consecutivas entre sí (no difieren en 1), así que una repetición
nunca debe alargar artificialmente una racha.
"""
from __future__ import annotations

from collections.abc import Sequence

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.tabulacion import tabular_conteo_por_sorteo
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico


def _rachas_consecutivas(numeros: Sequence[int]) -> list[int]:
    """Dado un conjunto de números (se deduplica internamente),
    devuelve la longitud de cada racha de consecutivos que contiene.
    P.ej. (3,4,5,20,21) -> [3, 2]. Un número sin vecino consecutivo es
    una racha de longitud 1: (1, 2, 5, 9) -> [2, 1, 1]."""
    distintos = sorted(set(numeros))
    if not distintos:
        return []

    rachas = []
    racha_actual = 1
    for anterior, actual in zip(distintos, distintos[1:]):
        if actual == anterior + 1:
            racha_actual += 1
        else:
            rachas.append(racha_actual)
            racha_actual = 1
    rachas.append(racha_actual)
    return rachas


def _contar_pares_consecutivos(numeros: Sequence[int]) -> int:
    """Cantidad de pares adyacentes (n, n+1 ambos presentes). Se
    deriva de las rachas: una racha de longitud L aporta (L-1) pares."""
    return sum(max(0, longitud - 1) for longitud in _rachas_consecutivas(numeros))


def _contar_trios_consecutivos(numeros: Sequence[int]) -> int:
    """Cantidad de tríos adyacentes (n, n+1, n+2 los tres presentes).
    Una racha de longitud L aporta max(0, L-2) tríos -p.ej. una racha
    de 4 (3,4,5,6) contiene 2 tríos: (3,4,5) y (4,5,6)."""
    return sum(max(0, longitud - 2) for longitud in _rachas_consecutivas(numeros))


def _racha_maxima(numeros: Sequence[int]) -> int:
    """Longitud de la racha más larga. 0 si no hay ningún número
    (sorteo vacío, caso defensivo)."""
    rachas = _rachas_consecutivas(numeros)
    return max(rachas) if rachas else 0


def _validar_rango(valores: Sequence[int], rango_min: int, rango_max: int, etiqueta: str) -> None:
    fuera_de_rango = [v for v in valores if not (rango_min <= v <= rango_max)]
    if fuera_de_rango:
        raise ValueError(
            f"{etiqueta}: valores fuera del rango [{rango_min},{rango_max}]: {sorted(set(fuera_de_rango))}"
        )


def calcular_distribucion_pares_consecutivos(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """valor = cantidad de pares consecutivos en el sorteo, tabulado
    0..(K-1)."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_distribucion_pares_consecutivos")

    conteos = [_contar_pares_consecutivos(r.numeros) for r in historico]
    return tabular_conteo_por_sorteo(conteos, max(0, cantidad_numeros - 1), len(historico))


def calcular_distribucion_trios_consecutivos(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """valor = cantidad de tríos consecutivos en el sorteo, tabulado
    0..max(0, K-2)."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_distribucion_trios_consecutivos")

    conteos = [_contar_trios_consecutivos(r.numeros) for r in historico]
    return tabular_conteo_por_sorteo(conteos, max(0, cantidad_numeros - 2), len(historico))


def calcular_distribucion_racha_maxima(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """valor = longitud de la racha más larga del sorteo, tabulado
    1..K (nunca 0 con al menos un número: un número aislado ya es una
    racha de longitud 1)."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_distribucion_racha_maxima")

    conteos = [_racha_maxima(r.numeros) for r in historico]
    # tabular_conteo_por_sorteo arranca en 0 -se pide el universo
    # completo 0..K y luego se recorta la fila "0" (nunca ocurre con
    # al menos un número), para no confundir con "racha de longitud 0".
    filas = tabular_conteo_por_sorteo(conteos, cantidad_numeros, len(historico))
    return [f for f in filas if f.valor != "0"]


def calcular_distribucion_pares_consecutivos_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Sobre los NÚMEROS de las balotas, deduplicados dentro de cada
    sorteo antes de buscar rachas -una repetición no alarga una
    racha."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_distribucion_pares_consecutivos_colorloto")

    conteos = [_contar_pares_consecutivos({n for n, _ in r.pares}) for r in historico]
    return tabular_conteo_por_sorteo(conteos, max(0, cantidad_balotas - 1), len(historico))


def calcular_distribucion_trios_consecutivos_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_distribucion_trios_consecutivos_colorloto")

    conteos = [_contar_trios_consecutivos({n for n, _ in r.pares}) for r in historico]
    return tabular_conteo_por_sorteo(conteos, max(0, cantidad_balotas - 2), len(historico))


def calcular_distribucion_racha_maxima_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in historico for n, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_distribucion_racha_maxima_colorloto")

    conteos = [_racha_maxima({n for n, _ in r.pares}) for r in historico]
    filas = tabular_conteo_por_sorteo(conteos, cantidad_balotas, len(historico))
    return [f for f in filas if f.valor != "0"]
