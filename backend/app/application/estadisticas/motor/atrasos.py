"""
Motor de atrasos (Paso 6) — atraso ACTUAL desde un corte temporal.

Igual que el resto del motor: funciones puras, sin conocimiento de
infraestructura. El atraso es EXCLUSIVAMENTE una propiedad histórica
("cuántos sorteos han transcurrido desde la última aparición"),
nunca una sugerencia de que un elemento "ya le toca" salir -por eso
ningún nombre, campo ni comentario de este módulo sugiere eso.

Alcance de esta etapa: solo el atraso ACTUAL (distancia desde la
última aparición hasta el sorteo de referencia). NO se implementan
todavía: máximo histórico de atraso, promedio, mediana, ni
distribución de intervalos -quedan para una iteración posterior del
Paso 6.

ColorLoto: `calcular_atrasos_numeros_colorloto` (número, ignorando
color), `calcular_atrasos_colores` (color, ignorando número) y
`calcular_atrasos_pares_numero_color` (par completo) -las tres
implementadas. El atraso de la "combinación de colores" dentro de un
sorteo (repeticiones, secuencias, patrones) sigue fuera de alcance,
reservado para una futura etapa dedicada a esa sección específica del
Paso 13.

Definición exacta del atraso, usando SIEMPRE numero_sorteo real
(nunca la posición ordinal en la lista -así el atraso no se
distorsiona si hay huecos en lo importado):

    atraso(valor) = numero_sorteo_referencia - numero_sorteo_de_ultima_aparicion(valor)

numero_sorteo_referencia es `hasta_numero_sorteo` si se especifica;
si no, el numero_sorteo máximo presente en los resultados (ya
filtrados). Un elemento nunca observado tiene atraso=None -nunca -1
ni 0 artificiales, para no confundir "nunca observado" con una
magnitud numérica real.
"""
from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.tipos import IntervalosHistoricos, ResultadoColorLoto, ResultadoNumerico


@dataclass(frozen=True)
class AtrasoObservado:
    """Colocado aquí (no en tipos.py) porque es un tipo de salida
    propio y exclusivo de este módulo -a diferencia de
    ResultadoNumerico/ResultadoColorLoto (tipos.py), que son DTOs de
    ENTRADA compartidos por varios módulos del motor (frecuencia.py,
    generales.py y este). AtrasoObservado no lo consume nadie más
    todavía; si en el futuro otro módulo del motor lo necesita,
    moverlo a tipos.py en ese momento estará justificado -hacerlo
    ahora sería anticipar una necesidad que no existe aún."""

    valor: str
    atraso: int | None  # None = nunca observado en la ventana analizada
    ultimo_sorteo_aparicion: int | None  # numero_sorteo de la última aparición; None si nunca
    total_sorteos: int  # tamaño de la ventana analizada (contexto/trazabilidad)


def _calcular_atrasos_genericos(
    apariciones_por_valor: dict[str, int],
    universo: Iterable[str],
    numero_sorteo_referencia: int,
    total_sorteos: int,
) -> list[AtrasoObservado]:
    """Helper interno compartido por las tres funciones públicas de
    este módulo -mismo patrón que _frecuencia_desde_contador en
    frecuencia.py. `apariciones_por_valor` ya trae, por cada valor
    que apareció al menos una vez, el numero_sorteo de su ÚLTIMA
    aparición (el máximo)."""
    filas = []
    for valor in sorted(universo, key=lambda v: int(v) if v.lstrip("-").isdigit() else v):
        ultima_aparicion = apariciones_por_valor.get(valor)
        if ultima_aparicion is None:
            filas.append(
                AtrasoObservado(
                    valor=valor, atraso=None, ultimo_sorteo_aparicion=None, total_sorteos=total_sorteos
                )
            )
        else:
            filas.append(
                AtrasoObservado(
                    valor=valor,
                    atraso=numero_sorteo_referencia - ultima_aparicion,
                    ultimo_sorteo_aparicion=ultima_aparicion,
                    total_sorteos=total_sorteos,
                )
            )
    return filas


def _validar_rango(valores: Sequence[int], rango_min: int, rango_max: int, etiqueta: str) -> None:
    fuera_de_rango = [v for v in valores if not (rango_min <= v <= rango_max)]
    if fuera_de_rango:
        raise ValueError(
            f"{etiqueta}: valores fuera del rango [{rango_min},{rango_max}]: {sorted(set(fuera_de_rango))}"
        )


def _filtrar_por_corte(resultados: Sequence, hasta_numero_sorteo: int | None) -> tuple[list, int | None]:
    """Delega el filtrado al módulo compartido `corte_temporal.py`
    (consolidado en la Etapa F) y además determina el
    numero_sorteo_referencia -responsabilidad propia de este módulo,
    ya que "cuál es el sorteo de referencia para el atraso" no aplica
    a recencia.py ni a distribuciones.py."""
    filtrados = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    if hasta_numero_sorteo is not None:
        return filtrados, hasta_numero_sorteo

    referencia = max((r.numero_sorteo for r in filtrados), default=None)
    return filtrados, referencia


def calcular_atrasos_numeros(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> list[AtrasoObservado]:
    """Incluye TODOS los números de [rango_min, rango_max] -mismo
    principio que frecuencia. Nunca muta `resultados`; acepta entrada
    desordenada sin que el resultado cambie. Un número que aparece
    dos veces dentro del mismo ResultadoNumerico (no debería ocurrir
    en juegos estándar, pero la función es defensiva) no produce dos
    apariciones distintas -solo importa el numero_sorteo."""
    filtrados, numero_sorteo_referencia = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    total_sorteos = len(filtrados)

    todos_los_numeros = [n for r in filtrados for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_atrasos_numeros")

    ultima_aparicion: dict[str, int] = {}
    for r in filtrados:
        for n in set(r.numeros):  # set(): un numero repetido en el mismo resultado no duplica nada
            valor = str(n)
            if valor not in ultima_aparicion or r.numero_sorteo > ultima_aparicion[valor]:
                ultima_aparicion[valor] = r.numero_sorteo

    universo = [str(n) for n in range(rango_min, rango_max + 1)]
    referencia = numero_sorteo_referencia if numero_sorteo_referencia is not None else 0
    return _calcular_atrasos_genericos(ultima_aparicion, universo, referencia, total_sorteos)


def calcular_atrasos_superbalota(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> list[AtrasoObservado]:
    """Pool INDEPENDIENTE del principal -nunca se mezcla con
    calcular_atrasos_numeros. superbalota=None se ignora: no cuenta
    como aparición ni rompe el cálculo de los demás valores.
    `total_sorteos` refleja los sorteos filtrados por el corte (no
    solo los que tienen superbalota), igual criterio que
    total_sorteos en el resto del motor -es el tamaño de la ventana
    analizada, no un conteo de datos válidos."""
    filtrados, numero_sorteo_referencia = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    total_sorteos = len(filtrados)

    superbalotas_presentes = [r.superbalota for r in filtrados if r.superbalota is not None]
    _validar_rango(superbalotas_presentes, rango_min, rango_max, "calcular_atrasos_superbalota")

    ultima_aparicion: dict[str, int] = {}
    for r in filtrados:
        if r.superbalota is None:
            continue
        valor = str(r.superbalota)
        if valor not in ultima_aparicion or r.numero_sorteo > ultima_aparicion[valor]:
            ultima_aparicion[valor] = r.numero_sorteo

    universo = [str(n) for n in range(rango_min, rango_max + 1)]
    referencia = numero_sorteo_referencia if numero_sorteo_referencia is not None else 0
    return _calcular_atrasos_genericos(ultima_aparicion, universo, referencia, total_sorteos)


def calcular_atrasos_numeros_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> list[AtrasoObservado]:
    """Atraso del NÚMERO de la balota, ignorando el color. Un número
    repetido dentro del mismo sorteo (p.ej. (5,ROJO) y (5,AZUL) en el
    mismo sorteo) tiene una sola última aparición -el numero_sorteo,
    no la balota individual. Atraso de color y de par número-color:
    diferidos al Paso 13 (ver docstring del módulo)."""
    filtrados, numero_sorteo_referencia = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    total_sorteos = len(filtrados)

    todos_los_numeros = [n for r in filtrados for n, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_atrasos_numeros_colorloto")

    ultima_aparicion: dict[str, int] = {}
    for r in filtrados:
        numeros_del_sorteo = {n for n, _ in r.pares}  # set(): ignora repeticiones dentro del sorteo
        for n in numeros_del_sorteo:
            valor = str(n)
            if valor not in ultima_aparicion or r.numero_sorteo > ultima_aparicion[valor]:
                ultima_aparicion[valor] = r.numero_sorteo

    universo = [str(n) for n in range(rango_min, rango_max + 1)]
    referencia = numero_sorteo_referencia if numero_sorteo_referencia is not None else 0
    return _calcular_atrasos_genericos(ultima_aparicion, universo, referencia, total_sorteos)


def calcular_atrasos_colores(
    resultados: Sequence[ResultadoColorLoto], colores_vigentes: Sequence[str],
    hasta_numero_sorteo: int | None = None,
) -> list[AtrasoObservado]:
    """Atraso del COLOR, ignorando el número (Etapa L, Paso 13).
    Universo = colores_vigentes MÁS cualquier color observado que no
    esté en colores_vigentes -mismo criterio de "nunca perder un dato
    observado" ya usado en calcular_frecuencia_colores. Un color
    repetido dentro del mismo sorteo (varias balotas del mismo color)
    tiene una sola última aparición -el numero_sorteo, no la balota
    individual, mismo criterio exacto que calcular_atrasos_numeros_colorloto."""
    filtrados, numero_sorteo_referencia = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    total_sorteos = len(filtrados)

    todos_los_colores = [c for r in filtrados for _, c in r.pares]

    ultima_aparicion: dict[str, int] = {}
    for r in filtrados:
        colores_del_sorteo = {c for _, c in r.pares}  # set(): ignora repeticiones dentro del sorteo
        for c in colores_del_sorteo:
            if c not in ultima_aparicion or r.numero_sorteo > ultima_aparicion[c]:
                ultima_aparicion[c] = r.numero_sorteo

    universo = set(colores_vigentes) | set(todos_los_colores)
    referencia = numero_sorteo_referencia if numero_sorteo_referencia is not None else 0
    return _calcular_atrasos_genericos(ultima_aparicion, universo, referencia, total_sorteos)


def calcular_atrasos_pares_numero_color(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, colores_vigentes: Sequence[str],
    hasta_numero_sorteo: int | None = None,
) -> list[AtrasoObservado]:
    """Atraso del PAR (número, color) como unidad atómica (Etapa L,
    Paso 13) -mismo criterio que
    frecuencia.py::calcular_frecuencia_pares_numero_color. valor =
    "numero-color", p.ej. "5-ROJO". Universo = producto de
    [rango_min,rango_max] × colores_a_reportar (vigentes más
    cualquier color observado), MÁS cualquier par realmente
    observado (nunca se pierde un dato aunque su color no esté en
    colores_vigentes)."""
    filtrados, numero_sorteo_referencia = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    total_sorteos = len(filtrados)

    todos_los_pares = [par for r in filtrados for par in r.pares]
    _validar_rango([n for n, _ in todos_los_pares], rango_min, rango_max, "calcular_atrasos_pares_numero_color")

    ultima_aparicion: dict[str, int] = {}
    for r in filtrados:
        pares_del_sorteo = set(r.pares)  # set(): ignora repeticiones dentro del sorteo
        for n, c in pares_del_sorteo:
            valor = f"{n}-{c}"
            if valor not in ultima_aparicion or r.numero_sorteo > ultima_aparicion[valor]:
                ultima_aparicion[valor] = r.numero_sorteo

    colores_a_reportar = set(colores_vigentes) | {c for _, c in todos_los_pares}
    universo_tuplas = {(n, c) for n in range(rango_min, rango_max + 1) for c in colores_a_reportar}
    universo_tuplas |= set(todos_los_pares)  # nunca se pierde un par observado, aunque no esté en el universo teórico
    universo = [f"{n}-{c}" for n, c in universo_tuplas]

    referencia = numero_sorteo_referencia if numero_sorteo_referencia is not None else 0
    return _calcular_atrasos_genericos(ultima_aparicion, universo, referencia, total_sorteos)


def _construir_intervalos_historicos(valor: str, numeros_sorteo_apariciones: list[int]) -> IntervalosHistoricos:
    """A partir de los numero_sorteo (reales, no posiciones) donde un
    valor apareció -ya sin duplicar por repetición dentro de un mismo
    sorteo, responsabilidad de quien construye esa lista antes de
    llamar aquí-, calcula todos los intervalos consecutivos y sus
    estadísticos descriptivos. Con menos de 2 apariciones, no hay
    ningún intervalo que calcular: todos los campos numéricos quedan
    en None (nunca 0, que sería una magnitud real distinta -un
    intervalo de 0 nunca ocurre, ya que dos apariciones en el mismo
    sorteo cuentan como una sola aparición, no como dos consecutivas)."""
    ordenados = sorted(set(numeros_sorteo_apariciones))
    cantidad_apariciones = len(ordenados)

    if cantidad_apariciones < 2:
        return IntervalosHistoricos(
            valor=valor, cantidad_apariciones=cantidad_apariciones, cantidad_intervalos=0,
            intervalo_minimo=None, intervalo_maximo=None, intervalo_promedio=None,
            intervalo_mediana=None, intervalos=(),
        )

    intervalos = tuple(actual - anterior for anterior, actual in zip(ordenados, ordenados[1:]))
    return IntervalosHistoricos(
        valor=valor, cantidad_apariciones=cantidad_apariciones, cantidad_intervalos=len(intervalos),
        intervalo_minimo=min(intervalos), intervalo_maximo=max(intervalos),
        intervalo_promedio=statistics.mean(intervalos), intervalo_mediana=statistics.median(intervalos),
        intervalos=intervalos,
    )


def calcular_intervalos_historicos_numeros(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> list[IntervalosHistoricos]:
    """Estadísticos sobre TODOS los intervalos históricos entre
    apariciones consecutivas de cada número (Paso 6, segunda mitad
    -Etapa N). Incluye TODO el rango, incluso números con 0 o 1
    aparición (sin intervalos posibles, ver _construir_intervalos_historicos)."""
    filtrados, _ = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in filtrados for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_intervalos_historicos_numeros")

    apariciones_por_valor: dict[str, list[int]] = {}
    for r in filtrados:
        for n in set(r.numeros):  # set(): una repetición dentro del mismo sorteo no duplica la aparición
            apariciones_por_valor.setdefault(str(n), []).append(r.numero_sorteo)

    return [
        _construir_intervalos_historicos(str(n), apariciones_por_valor.get(str(n), []))
        for n in range(rango_min, rango_max + 1)
    ]


def calcular_intervalos_historicos_superbalota(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> list[IntervalosHistoricos]:
    """Pool independiente del principal, mismo criterio que en el
    resto del motor. superbalota=None se ignora -no cuenta como
    aparición ni rompe el cálculo de otros valores."""
    filtrados, _ = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    superbalotas_presentes = [r.superbalota for r in filtrados if r.superbalota is not None]
    _validar_rango(superbalotas_presentes, rango_min, rango_max, "calcular_intervalos_historicos_superbalota")

    apariciones_por_valor: dict[str, list[int]] = {}
    for r in filtrados:
        if r.superbalota is None:
            continue
        apariciones_por_valor.setdefault(str(r.superbalota), []).append(r.numero_sorteo)

    return [
        _construir_intervalos_historicos(str(n), apariciones_por_valor.get(str(n), []))
        for n in range(rango_min, rango_max + 1)
    ]


def calcular_intervalos_historicos_colores(
    resultados: Sequence[ResultadoColorLoto], colores_vigentes: Sequence[str],
    hasta_numero_sorteo: int | None = None,
) -> list[IntervalosHistoricos]:
    """Intervalos históricos del COLOR, ignorando el número. Universo
    = colores_vigentes MÁS cualquier color observado que no esté ahí
    -nunca se pierde un dato, mismo criterio que calcular_atrasos_colores."""
    filtrados, _ = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    todos_los_colores = [c for r in filtrados for _, c in r.pares]

    apariciones_por_valor: dict[str, list[int]] = {}
    for r in filtrados:
        for c in {c for _, c in r.pares}:  # set(): una repetición de color dentro del mismo sorteo no duplica
            apariciones_por_valor.setdefault(c, []).append(r.numero_sorteo)

    universo = set(colores_vigentes) | set(todos_los_colores)
    return [_construir_intervalos_historicos(c, apariciones_por_valor.get(c, [])) for c in sorted(universo)]


def calcular_intervalos_historicos_pares_numero_color(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, colores_vigentes: Sequence[str],
    hasta_numero_sorteo: int | None = None,
) -> list[IntervalosHistoricos]:
    """Intervalos históricos del PAR (número, color) como unidad
    atómica -mismo criterio que calcular_atrasos_pares_numero_color.
    valor = "numero-color", p.ej. "5-ROJO"."""
    filtrados, _ = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    todos_los_pares = [par for r in filtrados for par in r.pares]
    _validar_rango(
        [n for n, _ in todos_los_pares], rango_min, rango_max, "calcular_intervalos_historicos_pares_numero_color",
    )

    apariciones_por_valor: dict[str, list[int]] = {}
    for r in filtrados:
        for n, c in set(r.pares):  # set(): una repetición del mismo par dentro del sorteo no duplica
            apariciones_por_valor.setdefault(f"{n}-{c}", []).append(r.numero_sorteo)

    colores_a_reportar = set(colores_vigentes) | {c for _, c in todos_los_pares}
    universo_tuplas = {(n, c) for n in range(rango_min, rango_max + 1) for c in colores_a_reportar}
    universo_tuplas |= set(todos_los_pares)  # nunca se pierde un par observado, aunque no esté en el universo teórico
    universo = sorted(f"{n}-{c}" for n, c in universo_tuplas)

    return [_construir_intervalos_historicos(v, apariciones_por_valor.get(v, [])) for v in universo]


def calcular_intervalos_historicos_numeros_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> list[IntervalosHistoricos]:
    """Intervalos históricos del NÚMERO de la balota, ignorando el
    color -mismo criterio que calcular_atrasos_numeros_colorloto."""
    filtrados, _ = _filtrar_por_corte(resultados, hasta_numero_sorteo)
    todos_los_numeros = [n for r in filtrados for n, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_intervalos_historicos_numeros_colorloto")

    apariciones_por_valor: dict[str, list[int]] = {}
    for r in filtrados:
        for n in {n for n, _ in r.pares}:  # set(): una repetición del número dentro del sorteo no duplica
            apariciones_por_valor.setdefault(str(n), []).append(r.numero_sorteo)

    return [
        _construir_intervalos_historicos(str(n), apariciones_por_valor.get(str(n), []))
        for n in range(rango_min, rango_max + 1)
    ]
