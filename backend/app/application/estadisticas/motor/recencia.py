"""
Motor de recencia (Paso 7).

Compara la frecuencia histórica completa de un valor contra su
frecuencia en una ventana reciente (últimos N sorteos). Es
DELIBERADAMENTE un módulo delgado: la única responsabilidad propia
es recortar la ventana (windowing puro, sobre listas) -el conteo en
sí lo hace `frecuencia.py`, reutilizado sin cambios. Nunca hay dos
lugares con la misma lógica de conteo de apariciones.

Distinción fundamental que este módulo preserva: `ComparacionRecencia`
expone la frecuencia histórica y la reciente como dos
`FrecuenciaObservada` INDEPENDIENTES, más un campo `diferencia`. En
ningún caso esa diferencia se convierte en una probabilidad de que el
valor aparezca en el siguiente sorteo -sigue siendo, de principio a
fin, la comparación de dos conteos históricos.

Decisión de diseño (aprobada): "últimos N sorteos" se define por
CANTIDAD de resultados reales disponibles, no por aritmética de
numero_sorteo. Es una asimetría deliberada frente a `atrasos.py`
(que sí usa numero_sorteo real para la distancia de atraso) -son
preguntas estadísticas distintas: el atraso mide una distancia
oficial real; "últimos N" es el tamaño de una muestra. Si hay menos
de N sorteos disponibles, se usan todos los que existan -nunca es un
error, es un historial corto.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.frecuencia import (
    calcular_frecuencia_colores,
    calcular_frecuencia_numeros,
    calcular_frecuencia_numeros_colorloto,
    calcular_frecuencia_pares_numero_color,
    calcular_frecuencia_superbalota,
)
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico


@dataclass(frozen=True)
class ComparacionRecencia:
    """Frecuencia histórica y reciente quedan accesibles POR
    SEPARADO -mismo principio que FilaFrecuencia en frecuencia.py-,
    nunca fusionadas en un solo número. `diferencia` es meramente
    descriptiva: reciente.frecuencia_relativa - historica.frecuencia_relativa."""

    valor: str
    frecuencia_historica: FrecuenciaObservada
    frecuencia_reciente: FrecuenciaObservada
    ventana: str  # etiqueta libre, p.ej. "ultimos_10" -la decide quien llama, no está hardcodeada aquí
    diferencia: float


def tomar_ultimos_n_sorteos(
    resultados: Sequence, n: int, hasta_numero_sorteo: int | None = None
) -> list:
    """Filtra defensivamente por hasta_numero_sorteo, ordena una
    COPIA por numero_sorteo (nunca muta la entrada original) y
    devuelve los últimos `n`. Si hay menos de `n` disponibles,
    devuelve todos los que existan -nunca lanza error por eso."""
    if n <= 0:
        raise ValueError(f"n debe ser positivo, se recibió n={n}")

    filtrados = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    ordenados = sorted(filtrados, key=lambda r: r.numero_sorteo)
    return ordenados[-n:] if n < len(ordenados) else ordenados


def _construir_comparaciones(
    historicas: list[FrecuenciaObservada], recientes: list[FrecuenciaObservada], etiqueta_ventana: str,
) -> list[ComparacionRecencia]:
    recientes_por_valor = {f.valor: f for f in recientes}
    comparaciones = []
    for historica in historicas:
        reciente = recientes_por_valor[historica.valor]
        comparaciones.append(
            ComparacionRecencia(
                valor=historica.valor,
                frecuencia_historica=historica,
                frecuencia_reciente=reciente,
                ventana=etiqueta_ventana,
                diferencia=reciente.frecuencia_relativa - historica.frecuencia_relativa,
            )
        )
    return comparaciones


def comparar_frecuencia_numeros_por_ventana(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    ventana: int, etiqueta_ventana: str, hasta_numero_sorteo: int | None = None,
) -> list[ComparacionRecencia]:
    """Compara la frecuencia de números sobre TODO el histórico
    (hasta el corte) contra la frecuencia sobre los últimos `ventana`
    sorteos. Reutiliza calcular_frecuencia_numeros para ambos
    conteos -nunca reimplementa el conteo aquí."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    reciente = tomar_ultimos_n_sorteos(resultados, ventana, hasta_numero_sorteo)

    frecuencias_historicas = calcular_frecuencia_numeros(historico, rango_min, rango_max)
    frecuencias_recientes = calcular_frecuencia_numeros(reciente, rango_min, rango_max)

    return _construir_comparaciones(frecuencias_historicas, frecuencias_recientes, etiqueta_ventana)


def comparar_frecuencia_superbalota_por_ventana(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    ventana: int, etiqueta_ventana: str, hasta_numero_sorteo: int | None = None,
) -> list[ComparacionRecencia]:
    """Pool independiente del principal, mismo principio que en
    frecuencia.py y atrasos.py. Reutiliza
    calcular_frecuencia_superbalota para ambos conteos."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    reciente = tomar_ultimos_n_sorteos(resultados, ventana, hasta_numero_sorteo)

    frecuencias_historicas = calcular_frecuencia_superbalota(historico, rango_min, rango_max)
    frecuencias_recientes = calcular_frecuencia_superbalota(reciente, rango_min, rango_max)

    return _construir_comparaciones(frecuencias_historicas, frecuencias_recientes, etiqueta_ventana)


def comparar_frecuencia_numeros_colorloto_por_ventana(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int,
    ventana: int, etiqueta_ventana: str, hasta_numero_sorteo: int | None = None,
) -> list[ComparacionRecencia]:
    """Frecuencia del NÚMERO de la balota (ignorando color), mismo
    alcance que calcular_atrasos_numeros_colorloto en la Etapa D. El
    par número-color completo tiene su propia función:
    comparar_frecuencia_pares_numero_color_por_ventana (Etapa L)."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    reciente = tomar_ultimos_n_sorteos(resultados, ventana, hasta_numero_sorteo)

    frecuencias_historicas = calcular_frecuencia_numeros_colorloto(historico, rango_min, rango_max)
    frecuencias_recientes = calcular_frecuencia_numeros_colorloto(reciente, rango_min, rango_max)

    return _construir_comparaciones(frecuencias_historicas, frecuencias_recientes, etiqueta_ventana)


def comparar_frecuencia_colores_por_ventana(
    resultados: Sequence[ResultadoColorLoto], colores_vigentes: Sequence[str],
    ventana: int, etiqueta_ventana: str, hasta_numero_sorteo: int | None = None,
) -> list[ComparacionRecencia]:
    """Reutiliza calcular_frecuencia_colores para ambos conteos.
    `colores_vigentes` se recibe desde afuera, igual que en
    frecuencia.py -este módulo tampoco conoce la paleta por su
    cuenta.

    **Corrección real de un defecto confirmado por auditoría
    independiente antes de AE-30** (Etapa AE-30): `calcular_frecuencia_colores`
    construye su propio universo por llamada como `set(colores_vigentes)
    | set(observados-en-ESA-porción)` (confirmado real en
    `frecuencia.py`) -como este motor la invoca DOS VECES con
    porciones distintas (`historico` completo vs. `reciente`, un
    subconjunto temporal siempre incluido en `historico`), un color
    observado en `historico` pero ausente de `colores_vigentes` Y
    ausente de `reciente` (retirado y no vigente, o simplemente sin
    apariciones recientes) generaba universos DIVERGENTES entre
    ambas llamadas -reproducido real: `KeyError: 'ROJO'` en
    `_construir_comparaciones`, que asume el mismo universo en
    ambos lados. **Corrección real**: se calcula un ÚNICO universo
    compartido -`colores_vigentes` UNIDO con TODOS los colores
    observados en `historico` (nunca en `reciente`, que es siempre
    un subconjunto del mismo `resultados` ya filtrado por el corte,
    así que `historico` ya lo cubre por completo)- y se pasa ESE
    MISMO universo, ordenado de forma determinista, a AMBAS
    llamadas. Como `reciente ⊆ historico`, el universo que
    `calcular_frecuencia_colores` calcularía internamente para la
    llamada reciente (`universo_compartido ∪ observados-en-reciente`)
    es siempre igual a `universo_compartido` -garantizando universos
    idénticos por construcción, sin modificar `calcular_frecuencia_colores`
    ni `_construir_comparaciones`. Un color histórico ausente de la
    ventana reciente obtiene correctamente `apariciones=0` con el
    `total_sorteos` reciente real (nunca inventado). Nunca se oculta
    el error con `try/except`, nunca se descarta una fila histórica,
    nunca se usa `dict.get()` sin universo compartido."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    reciente = tomar_ultimos_n_sorteos(resultados, ventana, hasta_numero_sorteo)

    universo_compartido = sorted(set(colores_vigentes) | {color for r in historico for _, color in r.pares})

    frecuencias_historicas = calcular_frecuencia_colores(historico, universo_compartido)
    frecuencias_recientes = calcular_frecuencia_colores(reciente, universo_compartido)

    return _construir_comparaciones(frecuencias_historicas, frecuencias_recientes, etiqueta_ventana)


def comparar_frecuencia_pares_numero_color_por_ventana(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, colores_vigentes: Sequence[str],
    ventana: int, etiqueta_ventana: str, hasta_numero_sorteo: int | None = None,
) -> list[ComparacionRecencia]:
    """Reutiliza calcular_frecuencia_pares_numero_color (Etapa C)
    para ambos conteos -mismo patrón exacto que las demás funciones
    de este módulo, cerrando la deuda del Paso 13 señalada desde la
    Etapa E.

    **Corrección real del mismo defecto estructural que
    `comparar_frecuencia_colores_por_ventana` (Etapa AE-30,
    mantenimiento del módulo -esta función todavía no tiene página
    web conectada, pero conservaba el mismo defecto latente que
    habría bloqueado su propia conexión futura)**: `calcular_frecuencia_pares_numero_color`
    construye `colores_a_reportar` de la misma forma dependiente de
    la porción recibida (confirmado real en `frecuencia.py`) -mismo
    `KeyError` reproducido real: `KeyError: '1-ROJO'`. Misma
    corrección real: universo de colores compartido -`colores_vigentes`
    unido con todos los colores observados en `historico`- pasado a
    ambas llamadas; `rango_min`/`rango_max` (el eje numérico del par)
    ya eran fijos por argumento en ambas llamadas y nunca formaron
    parte del defecto."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    reciente = tomar_ultimos_n_sorteos(resultados, ventana, hasta_numero_sorteo)

    universo_compartido = sorted(set(colores_vigentes) | {color for r in historico for _, color in r.pares})

    frecuencias_historicas = calcular_frecuencia_pares_numero_color(historico, rango_min, rango_max, universo_compartido)
    frecuencias_recientes = calcular_frecuencia_pares_numero_color(reciente, rango_min, rango_max, universo_compartido)

    return _construir_comparaciones(frecuencias_historicas, frecuencias_recientes, etiqueta_ventana)
