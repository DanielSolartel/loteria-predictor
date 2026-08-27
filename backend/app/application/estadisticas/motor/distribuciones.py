"""
Motor de distribuciones (Paso 8).

Analiza propiedades estructurales de la combinación COMPLETA de cada
sorteo (nunca de un número individual): cuántos de los K números
principales son pares, cuántos caen en la mitad alta del rango,
cuánto suman entre sí, y en qué franjas de diez se agrupan. Siempre
sobre los números principales -la superbalota queda fuera de este
módulo por completo (ver más abajo).

Igual que el resto del motor: funciones puras, sin conocimiento de
infraestructura. Y la misma advertencia que en atrasos.py: esto sigue
siendo frecuencia histórica de un fenómeno derivado, no evidencia de
que el siguiente sorteo deba "compensar" una desviación observada.
Una suma inusualmente alta o baja en el pasado no hace más ni menos
probable la suma del próximo sorteo -es la misma falacia del atraso
("ya le toca"), aplicada ahora a la combinación completa en vez de a
un número individual.

Alcance excluido deliberadamente de esta etapa:
  - Superbalota: con K=1, "distribución de pares" es una clasificación
    binaria trivial (0 o 1) y "suma" es literalmente el número mismo
    -ya cubierto por calcular_frecuencia_superbalota (Etapa C), sin
    información nueva que aportar.
  - Decenas para ColorLoto: su rango (1-7) es más chico que una sola
    decena: el concepto no tiene sentido estadístico ahí.

Reutilización: `calcular_distribucion_decenas` NO reimplementa el
conteo de apariciones por número -llama a `calcular_frecuencia_numeros`
(Etapa C, sin modificar) y reagrupa esas filas por franja. Al hacerlo,
`apariciones` se SUMA entre números de la misma franja (correcto:
son conteos enteros independientes), pero `total_sorteos` se toma
directo de `len(historico)` -NUNCA se suma entre filas, porque todas
las filas individuales ya comparten el mismo total_sorteos (vienen
del mismo `resultados`); sumarlo las multiplicaría incorrectamente.
`frecuencia_relativa` se recalcula como apariciones_franja/total_sorteos
en vez de sumar las frecuencias relativas individuales -mismo
resultado matemático, pero más claro y sin arrastre de error de
punto flotante.
"""
from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros
from app.application.estadisticas.motor.tabulacion import tabular_conteo_por_sorteo
from app.application.estadisticas.tipos import (
    FeatureCandidata,
    FrecuenciaObservada,
    ResultadoColorLoto,
    ResultadoNumerico,
)

_PERCENTILES = (10, 25, 50, 75, 90)


@dataclass(frozen=True)
class DistribucionSumas:
    """Agrupa todos los estadísticos descriptivos de UNA distribución
    de sumas en un solo objeto navegable, en vez de una lista suelta
    de valores sin agrupar. minimo/maximo son None (no 0) cuando no
    hay datos -0 sería una suma válida en teoría, no una ausencia de
    dato."""

    total_sorteos: int
    minimo: int | None
    maximo: int | None
    media: float
    mediana: float
    desviacion_estandar: float  # poblacional (pstdev): describe el conjunto completo analizado, no una muestra
    percentiles: dict[int, float]  # {10: ..., 25: ..., 50: ..., 75: ..., 90: ...}; {} si no hay datos


def _punto_de_corte_altos_bajos(rango_min: int, rango_max: int) -> int:
    """bajos = [rango_min, punto_de_corte]; altos = [punto_de_corte+1, rango_max].
    Partición lo más equilibrada posible; si el rango es impar, el
    número sobrante queda del lado alto (convención documentada)."""
    mitad = (rango_max - rango_min + 1) // 2
    return rango_min + mitad - 1


def _construir_franjas_decenas(rango_min: int, rango_max: int) -> list[tuple[int, int]]:
    franjas = []
    inicio = rango_min
    while inicio <= rango_max:
        fin = min(inicio + 9, rango_max)
        franjas.append((inicio, fin))
        inicio = fin + 1
    return franjas


def calcular_distribucion_pares_impares(
    resultados: Sequence[ResultadoNumerico], cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """valor = cantidad de números pares en el sorteo ("0".."K").
    Sobre los números principales únicamente."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    conteos = [sum(1 for n in r.numeros if n % 2 == 0) for r in historico]
    return tabular_conteo_por_sorteo(conteos, cantidad_numeros, len(historico))


def calcular_distribucion_altos_bajos(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """valor = cantidad de números "bajos" en el sorteo ("0".."K").
    Metodología del corte: ver _punto_de_corte_altos_bajos."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    corte = _punto_de_corte_altos_bajos(rango_min, rango_max)
    conteos = [sum(1 for n in r.numeros if n <= corte) for r in historico]
    return tabular_conteo_por_sorteo(conteos, cantidad_numeros, len(historico))


def calcular_distribucion_sumas(
    resultados: Sequence[ResultadoNumerico], hasta_numero_sorteo: int | None = None,
) -> DistribucionSumas:
    """Suma de los números principales de cada sorteo (nunca la
    superbalota). min/max/media/mediana/desviación estándar
    (poblacional)/percentiles P10,P25,P50,P75,P90 sobre esa serie de
    sumas."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    sumas = [sum(r.numeros) for r in historico]
    return _construir_distribucion_sumas(sumas)


def calcular_distribucion_decenas(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_frecuencia_numeros (Etapa C) y reagrupa por
    franja de diez -ver docstring del módulo para la justificación
    exacta de por qué apariciones se suma pero total_sorteos NO."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    frecuencias_individuales = calcular_frecuencia_numeros(historico, rango_min, rango_max)
    total_sorteos = len(historico)  # tomado directo del dato real, nunca sumado desde las filas individuales

    filas = []
    for inicio, fin in _construir_franjas_decenas(rango_min, rango_max):
        apariciones_franja = sum(
            f.apariciones for f in frecuencias_individuales if inicio <= int(f.valor) <= fin
        )
        frecuencia_relativa = (apariciones_franja / total_sorteos) if total_sorteos else 0.0
        filas.append(
            FrecuenciaObservada(
                valor=f"{inicio}-{fin}", apariciones=apariciones_franja,
                total_sorteos=total_sorteos, frecuencia_relativa=frecuencia_relativa,
            )
        )
    return filas


def calcular_distribucion_pares_impares_colorloto(
    resultados: Sequence[ResultadoColorLoto], cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Sobre los NÚMEROS de las balotas, ignorando el color -mismo
    alcance ya establecido para atrasos/recencia de ColorLoto en
    etapas previas. El atraso/recencia/intervalos del par número-color
    (Etapa L) y la distribución/coocurrencia de color (Etapa M) tienen
    sus propias funciones dedicadas, en atrasos.py/recencia.py/coocurrencia.py."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    conteos = [sum(1 for n, _ in r.pares if n % 2 == 0) for r in historico]
    return tabular_conteo_por_sorteo(conteos, cantidad_balotas, len(historico))


def calcular_distribucion_altos_bajos_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    corte = _punto_de_corte_altos_bajos(rango_min, rango_max)
    conteos = [sum(1 for n, _ in r.pares if n <= corte) for r in historico]
    return tabular_conteo_por_sorteo(conteos, cantidad_balotas, len(historico))


def calcular_distribucion_sumas_colorloto(
    resultados: Sequence[ResultadoColorLoto], hasta_numero_sorteo: int | None = None,
) -> DistribucionSumas:
    """Suma de los NÚMEROS de las 6 balotas, ignorando el color."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    sumas = [sum(n for n, _ in r.pares) for r in historico]
    return _construir_distribucion_sumas(sumas)


def _construir_distribucion_sumas(sumas: list[int]) -> DistribucionSumas:
    total_sorteos = len(sumas)
    if total_sorteos == 0:
        return DistribucionSumas(
            total_sorteos=0, minimo=None, maximo=None, media=0.0, mediana=0.0,
            desviacion_estandar=0.0, percentiles={},
        )

    if total_sorteos == 1:
        unico = sumas[0]
        return DistribucionSumas(
            total_sorteos=1, minimo=unico, maximo=unico, media=float(unico), mediana=float(unico),
            desviacion_estandar=0.0, percentiles={p: float(unico) for p in _PERCENTILES},
        )

    cuantiles = statistics.quantiles(sumas, n=100, method="inclusive")  # cuantiles[i] = percentil (i+1)
    percentiles = {p: cuantiles[p - 1] for p in _PERCENTILES}

    return DistribucionSumas(
        total_sorteos=total_sorteos,
        minimo=min(sumas),
        maximo=max(sumas),
        media=statistics.mean(sumas),
        mediana=statistics.median(sumas),
        desviacion_estandar=statistics.pstdev(sumas),
        percentiles=percentiles,
    )


def distribucion_sumas_a_features(
    distribucion: DistribucionSumas, calculado_hasta_sorteo: int, ventana: str = "historico_completo",
) -> list[FeatureCandidata]:
    """Desempaqueta media/mediana/desviación estándar/percentiles en
    FeatureCandidata individuales, cada una con su propio corte
    temporal explícito -mismo patrón que frecuencia_a_feature
    (Etapa C). Con distribucion vacía (total_sorteos=0), devuelve
    lista vacía -no hay nada que ofrecer como feature."""
    if distribucion.total_sorteos == 0:
        return []

    features = [
        FeatureCandidata(
            nombre="suma_media", valor=distribucion.media,
            calculado_hasta_sorteo=calculado_hasta_sorteo, ventana=ventana,
        ),
        FeatureCandidata(
            nombre="suma_mediana", valor=distribucion.mediana,
            calculado_hasta_sorteo=calculado_hasta_sorteo, ventana=ventana,
        ),
        FeatureCandidata(
            nombre="suma_desviacion_estandar", valor=distribucion.desviacion_estandar,
            calculado_hasta_sorteo=calculado_hasta_sorteo, ventana=ventana,
        ),
    ]
    for p, valor in sorted(distribucion.percentiles.items()):
        features.append(
            FeatureCandidata(
                nombre=f"suma_p{p}", valor=valor,
                calculado_hasta_sorteo=calculado_hasta_sorteo, ventana=ventana,
            )
        )
    return features


def calcular_distribucion_conteo_color(
    resultados: Sequence[ResultadoColorLoto], color_objetivo: str, cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Distribución de cuántas balotas de `color_objetivo` aparecen
    por sorteo, tabulado 0..cantidad_balotas (Etapa M). CON
    multiplicidad: si 3 balotas son ROJO en un sorteo, ese sorteo
    aporta el conteo 3, no 1 -a diferencia de la coocurrencia de
    colores (deduplicada), aquí se cuentan las balotas físicas, no
    los valores distintos. `color_objetivo` no vigente o nunca
    observado no produce error: el universo 0..K se tabula igual,
    con todo en 0 si el color nunca aparece."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    conteos = [sum(1 for _, c in r.pares if c == color_objetivo) for r in historico]
    return tabular_conteo_por_sorteo(conteos, cantidad_balotas, len(historico))


def calcular_maximo_repeticion_color_por_sorteo(
    resultados: Sequence[ResultadoColorLoto], cantidad_balotas: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Distribución de la MAYOR cantidad de balotas del mismo color
    dentro de un sorteo, tabulado 1..cantidad_balotas (Etapa M). Con
    las 6 balotas del mismo color -> máximo 6; con 6 colores
    distintos -> máximo 1. Inherentemente multiset: se cuenta la
    multiplicidad de cada color dentro del sorteo (Counter) y se toma
    el máximo -nunca 0, ya que con al menos una balota el color de
    esa balota ya tiene multiplicidad >= 1."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    conteos = [max(Counter(c for _, c in r.pares).values()) for r in historico]
    filas = tabular_conteo_por_sorteo(conteos, cantidad_balotas, len(historico))
    return [f for f in filas if f.valor != "0"]
