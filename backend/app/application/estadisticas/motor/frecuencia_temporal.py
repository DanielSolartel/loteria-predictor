"""
Motor de frecuencia temporal (Etapa O).

Responde una pregunta distinta tanto de `frecuencia.py` (frecuencia
total, sin condicionar) como de `generales.py` (frecuencia de
SORTEOS por periodo, sin mirar los números): aquí se pregunta "¿con
qué frecuencia aparece este número/superbalota/color/par, restringido
a los sorteos de tal año/mes/día de la semana?".

Es DELIBERADAMENTE una capa delgada de filtrado + reutilización, no
una reimplementación de conteo: cada función filtra `resultados` por
la dimensión temporal pedida y delega el conteo por completo en las
funciones ya existentes de `frecuencia.py` (`calcular_frecuencia_numeros`,
`calcular_frecuencia_superbalota`, `calcular_frecuencia_colores`,
`calcular_frecuencia_pares_numero_color`), sin modificarlas ni
duplicar su lógica.

Definición de "mes": mes CALENDARIO (1..12), AGREGADO across todos
los años del histórico -mismo criterio ya establecido por
`calcular_frecuencia_sorteos_por_mes` (generales.py, Etapa C): mes=3
incluye marzo de 2022, 2023, 2024, etc., nunca una combinación
año-mes. "día de semana" reutiliza el literal exacto del dominio
("lunes".."domingo"), mismo vocabulario que el resto del motor.

`total_sorteos`/`frecuencia_relativa` en cada `FrecuenciaObservada`
resultante representan el SUBCONJUNTO temporal filtrado, nunca el
histórico completo -si marzo tiene 5 sorteos, total_sorteos=5 para
cada fila de esa consulta, exactamente igual que si se hubiera
llamado a `calcular_frecuencia_numeros` con solo esos 5 resultados
desde el principio (que es, literalmente, lo que ocurre internamente).

Sin ninguna probabilidad teórica, frecuencia esperada, lift,
independencia ni coocurrencia -esta etapa es exclusivamente
frecuencia descriptiva condicionada por tiempo, nada de inferencia.
"""
from __future__ import annotations

from collections.abc import Sequence

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.frecuencia import (
    calcular_frecuencia_colores,
    calcular_frecuencia_numeros,
    calcular_frecuencia_numeros_colorloto,
    calcular_frecuencia_pares_numero_color,
    calcular_frecuencia_superbalota,
)
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico

_DIAS_SEMANA_VALIDOS = {"lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"}


def _validar_mes(mes: int) -> None:
    if not (1 <= mes <= 12):
        raise ValueError(f"mes debe estar entre 1 y 12, se recibió {mes}")


def _validar_dia_semana(dia_semana: str) -> None:
    if dia_semana not in _DIAS_SEMANA_VALIDOS:
        raise ValueError(
            f"dia_semana='{dia_semana}' no es un valor válido del dominio -debe ser uno de {sorted(_DIAS_SEMANA_VALIDOS)}"
        )


def _filtrar_por_anio(resultados: Sequence, anio: int) -> list:
    return [r for r in resultados if r.fecha.year == anio]


def _filtrar_por_mes(resultados: Sequence, mes: int) -> list:
    _validar_mes(mes)
    return [r for r in resultados if r.fecha.month == mes]


def _filtrar_por_dia_semana(resultados: Sequence, dia_semana: str) -> list:
    _validar_dia_semana(dia_semana)
    return [r for r in resultados if r.dia_semana == dia_semana]


# --- Números ---

def calcular_frecuencia_numeros_por_anio(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, anio: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Frecuencia de cada número, restringida a sorteos con
    fecha.year == anio. Reutiliza calcular_frecuencia_numeros sin
    modificarla -corte temporal primero, filtro de año después,
    conteo delegado por completo."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_anio(historico, anio)
    return calcular_frecuencia_numeros(subconjunto, rango_min, rango_max)


def calcular_frecuencia_numeros_por_mes(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, mes: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """mes = 1..12, calendario, AGREGADO across todos los años (ver
    docstring del módulo). ValueError si mes está fuera de 1..12."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_mes(historico, mes)
    return calcular_frecuencia_numeros(subconjunto, rango_min, rango_max)


def calcular_frecuencia_numeros_por_dia_semana(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, dia_semana: str,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """dia_semana = literal exacto del dominio ("lunes".."domingo").
    ValueError si no es uno de los valores válidos."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_dia_semana(historico, dia_semana)
    return calcular_frecuencia_numeros(subconjunto, rango_min, rango_max)


# --- Números de ColorLoto (Fase 5) ---

def calcular_frecuencia_numeros_colorloto_por_anio(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, anio: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Número de la balota ignorando su color, restringido a un año. Reutiliza
    calcular_frecuencia_numeros_colorloto: cada balota cuenta (multiplicidad), así que
    frecuencia_relativa es un promedio de balotas por sorteo, no una proporción de sorteos."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    return calcular_frecuencia_numeros_colorloto(_filtrar_por_anio(historico, anio), rango_min, rango_max)


def calcular_frecuencia_numeros_colorloto_por_mes(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, mes: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    return calcular_frecuencia_numeros_colorloto(_filtrar_por_mes(historico, mes), rango_min, rango_max)


def calcular_frecuencia_numeros_colorloto_por_dia_semana(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, dia_semana: str,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    return calcular_frecuencia_numeros_colorloto(_filtrar_por_dia_semana(historico, dia_semana), rango_min, rango_max)


# --- Superbalota ---

def calcular_frecuencia_superbalota_por_anio(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, anio: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Pool independiente del principal, mismo criterio de todo el
    motor. Reutiliza calcular_frecuencia_superbalota sin modificarla."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_anio(historico, anio)
    return calcular_frecuencia_superbalota(subconjunto, rango_min, rango_max)


def calcular_frecuencia_superbalota_por_mes(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, mes: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_mes(historico, mes)
    return calcular_frecuencia_superbalota(subconjunto, rango_min, rango_max)


def calcular_frecuencia_superbalota_por_dia_semana(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, dia_semana: str,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_dia_semana(historico, dia_semana)
    return calcular_frecuencia_superbalota(subconjunto, rango_min, rango_max)


# --- Colores de ColorLoto ---

def calcular_frecuencia_colores_por_anio(
    resultados: Sequence[ResultadoColorLoto], colores_vigentes: Sequence[str], anio: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_frecuencia_colores sin modificarla.
    `colores_vigentes` conserva exactamente el mismo criterio que la
    función base -nunca se pierde un color observado, aunque no esté
    vigente."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_anio(historico, anio)
    return calcular_frecuencia_colores(subconjunto, colores_vigentes)


def calcular_frecuencia_colores_por_mes(
    resultados: Sequence[ResultadoColorLoto], colores_vigentes: Sequence[str], mes: int,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_mes(historico, mes)
    return calcular_frecuencia_colores(subconjunto, colores_vigentes)


def calcular_frecuencia_colores_por_dia_semana(
    resultados: Sequence[ResultadoColorLoto], colores_vigentes: Sequence[str], dia_semana: str,
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_dia_semana(historico, dia_semana)
    return calcular_frecuencia_colores(subconjunto, colores_vigentes)


# --- Pares número-color de ColorLoto ---

def calcular_frecuencia_pares_numero_color_por_anio(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, colores_vigentes: Sequence[str],
    anio: int, hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_frecuencia_pares_numero_color sin
    modificarla. valor = "numero-color", mismo formato que la función base."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_anio(historico, anio)
    return calcular_frecuencia_pares_numero_color(subconjunto, rango_min, rango_max, colores_vigentes)


def calcular_frecuencia_pares_numero_color_por_mes(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, colores_vigentes: Sequence[str],
    mes: int, hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_mes(historico, mes)
    return calcular_frecuencia_pares_numero_color(subconjunto, rango_min, rango_max, colores_vigentes)


def calcular_frecuencia_pares_numero_color_por_dia_semana(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, colores_vigentes: Sequence[str],
    dia_semana: str, hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    subconjunto = _filtrar_por_dia_semana(historico, dia_semana)
    return calcular_frecuencia_pares_numero_color(subconjunto, rango_min, rango_max, colores_vigentes)
