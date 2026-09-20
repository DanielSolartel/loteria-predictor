"""
Gate operativo de elegibilidad para la reapertura del holdout de
Machine Learning -Etapa AE-40, validada.

Nucleo puro, determinista, que responde EXCLUSIVAMENTE si existen
suficientes sorteos nuevos, completos en numeracion, desde el
proximo holdout genuino (`2706`) para que una etapa FUTURA pueda
prerregistrar un protocolo antes de observar sus resultados. Nunca
entrena modelos, nunca evalua Log Loss/Brier/Precision@5/Recall@5,
nunca lee resultados historicos completos, nunca consulta
repositorios ni abre archivos -recibe exclusivamente un
`ResumenDisponibilidadHoldout` (conteos y numeros de sorteo, nunca
numeros ganadores ni superbalota) ya construido por el llamador.
Permanece puro -no importa scikit-learn, NumPy, SciPy, pandas,
SQLAlchemy, FastAPI ni Jinja2; reutiliza sin duplicar las constantes
de `PoliticaReaperturaML` ya validadas en AE-39.

ALCANCE DE VALIDACION (deliberadamente dividido en dos capas, nunca
mezclado): este modulo -el nucleo puro- valida exclusivamente la
COHERENCIA INTERNA de un `ResumenDisponibilidadHoldout` ya recibido
(juego autorizado, conteos y numeros de sorteo consistentes entre
si). Nunca compara ese resumen contra el codigo de juego que el
llamador originalmente solicito -ese modulo no recibe ese dato. La
comprobacion de que el resumen devuelto por el repositorio
corresponde EFECTIVAMENTE al juego solicitado es responsabilidad
exclusiva del caso de uso (`EvaluarElegibilidadReaperturaML`), que
si conoce ambos valores.

`ELEGIBLE_PARA_PRERREGISTRO` nunca significa GO, evidencia
predictiva, autorizacion para entrenar, autorizacion para mirar
resultados, autorizacion para consumir el holdout, ni autorizacion
para desplegar."""
from __future__ import annotations

from app.application.ml.incertidumbre import (
    MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT,
    PROXIMO_HOLDOUT_INICIO,
)
from app.application.ml.tipos import (
    EstadoElegibilidadReaperturaML,
    ReporteElegibilidadReaperturaML,
    ResumenDisponibilidadHoldout,
)

JUEGOS_AUTORIZADOS_AE40 = frozenset({"BALOTO", "BALOTO_REVANCHA"})
"""Mismo conjunto cerrado exacto de AE-35/36/37/38/39 -nunca se
mezclan Baloto y Baloto Revancha; cada juego se evalua por
separado."""

NUMERO_SORTEO_OBJETIVO_MINIMO = PROXIMO_HOLDOUT_INICIO + MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT - 1
"""Primer intervalo completo posible si no hay huecos:
`2706 + 100 - 1 = 2805` -derivado de las constantes de AE-39, nunca
un numero magico independiente."""


class DisponibilidadHoldoutInvalidaError(ValueError):
    """Excepcion propia y pequena de AE-40 -nunca `assert` para
    validaciones publicas de dominio. Cubre, dentro de la COHERENCIA
    INTERNA de un unico resumen: conteos negativos, total de
    registros distinto del total de numeros de sorteo distintos
    (duplicados), primer sorteo posterior a `2706`, presencia de un
    sorteo anterior a `2706`, minimo mayor que maximo, huecos en la
    numeracion, conteo inconsistente con `maximo - 2706 + 1`, juego
    no autorizado, valores no enteros y metadatos incompletos o
    incoherentes. Las inconsistencias estructurales nunca se
    convierten silenciosamente en un estado normal. Esta misma
    excepcion tambien se usa, desde el caso de uso
    (`EvaluarElegibilidadReaperturaML`), para rechazar un resumen
    cuyo `juego_codigo` no coincide con el juego solicitado -esa
    comprobacion especifica NO ocurre en este modulo puro, ver el
    docstring del modulo."""


def _validar_resumen(resumen: ResumenDisponibilidadHoldout) -> None:
    if resumen.juego_codigo not in JUEGOS_AUTORIZADOS_AE40:
        raise DisponibilidadHoldoutInvalidaError(
            f"'{resumen.juego_codigo}' no esta autorizado para AE-40 -"
            f"unicamente {sorted(JUEGOS_AUTORIZADOS_AE40)}"
        )

    for nombre, valor in (
        ("desde_numero_sorteo", resumen.desde_numero_sorteo),
        ("total_registros", resumen.total_registros),
        ("total_numeros_distintos", resumen.total_numeros_distintos),
    ):
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise DisponibilidadHoldoutInvalidaError(f"{nombre} debe ser un entero, recibido {valor!r} ({type(valor).__name__})")

    if resumen.desde_numero_sorteo != PROXIMO_HOLDOUT_INICIO:
        raise DisponibilidadHoldoutInvalidaError(
            f"desde_numero_sorteo debe ser exactamente {PROXIMO_HOLDOUT_INICIO}, recibido {resumen.desde_numero_sorteo}"
        )

    if resumen.total_registros < 0:
        raise DisponibilidadHoldoutInvalidaError(f"total_registros no puede ser negativo: {resumen.total_registros}")
    if resumen.total_numeros_distintos < 0:
        raise DisponibilidadHoldoutInvalidaError(f"total_numeros_distintos no puede ser negativo: {resumen.total_numeros_distintos}")

    if resumen.total_registros != resumen.total_numeros_distintos:
        raise DisponibilidadHoldoutInvalidaError(
            f"total_registros ({resumen.total_registros}) distinto de total_numeros_distintos "
            f"({resumen.total_numeros_distintos}) -indica sorteos duplicados en el rango consultado"
        )

    if resumen.total_registros == 0:
        if resumen.numero_sorteo_minimo is not None or resumen.numero_sorteo_maximo is not None:
            raise DisponibilidadHoldoutInvalidaError(
                "Con total_registros=0, numero_sorteo_minimo y numero_sorteo_maximo deben ser None "
                f"(recibidos {resumen.numero_sorteo_minimo!r}, {resumen.numero_sorteo_maximo!r})"
            )
        return

    if resumen.numero_sorteo_minimo is None or resumen.numero_sorteo_maximo is None:
        raise DisponibilidadHoldoutInvalidaError(
            f"Con total_registros={resumen.total_registros} > 0, numero_sorteo_minimo y "
            f"numero_sorteo_maximo no pueden ser None"
        )

    for nombre, valor in (("numero_sorteo_minimo", resumen.numero_sorteo_minimo), ("numero_sorteo_maximo", resumen.numero_sorteo_maximo)):
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise DisponibilidadHoldoutInvalidaError(f"{nombre} debe ser un entero, recibido {valor!r} ({type(valor).__name__})")

    if resumen.numero_sorteo_minimo > resumen.numero_sorteo_maximo:
        raise DisponibilidadHoldoutInvalidaError(
            f"numero_sorteo_minimo ({resumen.numero_sorteo_minimo}) no puede ser mayor que "
            f"numero_sorteo_maximo ({resumen.numero_sorteo_maximo})"
        )

    if resumen.numero_sorteo_minimo < resumen.desde_numero_sorteo:
        raise DisponibilidadHoldoutInvalidaError(
            f"numero_sorteo_minimo ({resumen.numero_sorteo_minimo}) es anterior a desde_numero_sorteo "
            f"({resumen.desde_numero_sorteo}) -la consulta debio filtrar numero_sorteo >= {resumen.desde_numero_sorteo}"
        )

    if resumen.numero_sorteo_minimo != resumen.desde_numero_sorteo:
        raise DisponibilidadHoldoutInvalidaError(
            f"numero_sorteo_minimo ({resumen.numero_sorteo_minimo}) es posterior a "
            f"desde_numero_sorteo ({resumen.desde_numero_sorteo}) -indica sorteos faltantes justo "
            f"al inicio del rango, una inconsistencia estructural que no se convierte en un "
            f"NO_ELEGIBLE silencioso"
        )

    rango_esperado = resumen.numero_sorteo_maximo - resumen.numero_sorteo_minimo + 1
    if rango_esperado != resumen.total_numeros_distintos:
        raise DisponibilidadHoldoutInvalidaError(
            f"Hueco en la numeracion: el rango [{resumen.numero_sorteo_minimo}, {resumen.numero_sorteo_maximo}] "
            f"implica {rango_esperado} sorteos, pero total_numeros_distintos es {resumen.total_numeros_distintos}"
        )

    conteo_esperado_desde_corte = resumen.numero_sorteo_maximo - PROXIMO_HOLDOUT_INICIO + 1
    if conteo_esperado_desde_corte != resumen.total_numeros_distintos:
        raise DisponibilidadHoldoutInvalidaError(
            f"total_numeros_distintos ({resumen.total_numeros_distintos}) es inconsistente con "
            f"numero_sorteo_maximo - {PROXIMO_HOLDOUT_INICIO} + 1 = {conteo_esperado_desde_corte}"
        )


def evaluar_elegibilidad_reapertura_ml(resumen: ResumenDisponibilidadHoldout) -> ReporteElegibilidadReaperturaML:
    """Unica funcion publica de AE-40. Recibe un
    `ResumenDisponibilidadHoldout` YA CONSTRUIDO (por el caso de uso,
    a partir del puerto de disponibilidad) y devuelve un
    `ReporteElegibilidadReaperturaML` inmutable -nunca entrena nada,
    nunca evalua metricas de ML, nunca observa resultados. Valida
    unicamente la coherencia interna de `resumen` -ver el docstring
    del modulo sobre la division de responsabilidades con el caso de
    uso.

    Umbral inclusivo: `0..99` sorteos nuevos ->
    `NO_ELEGIBLE_DATOS_INSUFICIENTES`; `100` o mas ->
    `ELEGIBLE_PARA_PRERREGISTRO`. Reproducible: la misma entrada
    produce siempre el mismo reporte."""
    _validar_resumen(resumen)

    total_nuevos = resumen.total_numeros_distintos
    estado = (
        EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO
        if total_nuevos >= MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT
        else EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES
    )

    return ReporteElegibilidadReaperturaML(
        juego_codigo=resumen.juego_codigo,
        estado=estado,
        proximo_holdout_inicio=PROXIMO_HOLDOUT_INICIO,
        minimo_sorteos_nuevos_requeridos=MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT,
        total_sorteos_nuevos=total_nuevos,
        numero_sorteo_minimo=resumen.numero_sorteo_minimo,
        numero_sorteo_maximo=resumen.numero_sorteo_maximo,
        numero_sorteo_objetivo_minimo=NUMERO_SORTEO_OBJETIVO_MINIMO,
        numeracion_contigua=True,
        resultados_observados=False,
        modelos_entrenados=False,
        holdout_consumido=False,
    )
