"""
Resolvedor de prediccion bloqueada -Etapa AE-43, validada.

Traduce, sin reevaluarlos, el estado operativo de AE-41
(`ReporteAutorizacionOperativaML`) y la decision cientifica de AE-39
(`DecisionContinuidadML`) a un `ReportePrediccionJuego`. En AE-43
TODOS los resultados posibles son bloqueos: `EstadoPrediccionML` no
tiene ningun estado habilitado y el reporte rechaza cualquier salida
predictiva en su propio `__post_init__`.

Limitacion explicita: `DecisionContinuidadML` es solo un Enum y no
lleva identidad de juego, asi que este modulo no puede verificar a
que juego corresponde la decision recibida (AE-39 fue NO-GO en ambos
juegos). No consulta repositorios, no lee archivos, no entrena ni
predice."""
from __future__ import annotations

from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import (
    DecisionContinuidadML,
    EstadoAutorizacionOperativaML,
    EstadoPrediccionML,
    ReporteAutorizacionOperativaML,
    ReportePrediccionJuego,
)

TOP_COMBINACIONES = 5
"""Contrato de la Fase 4 para una etapa futura -AE-43 nunca lo llena."""
TOP_NUMEROS = 10
"""Contrato de la Fase 4 para una etapa futura -AE-43 nunca lo llena."""

DISCLAIMER_PERMANENTE = (
    "Analisis estadistico, no garantia: los sorteos son aleatorios y ningun modelo evaluado "
    "hasta ahora supero al azar uniforme. No se generan recomendaciones de apuesta."
)

_EXPLICACIONES = {
    EstadoPrediccionML.BLOQUEADO_NUMERACION_INVALIDA:
        "el gate de AE-40/41 detecto una numeracion invalida en los sorteos nuevos",
    EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES:
        "no hay suficientes sorteos nuevos para reconsiderar la elegibilidad (AE-40/41)",
    EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO:
        "AE-39 no encontro evidencia de mejora frente al baseline uniforme",
    EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT:
        "no existe ninguna evaluacion prospectiva prerregistrada que respalde predicciones",
}


class PrediccionNoAutorizadaError(ValueError):
    """Juego fuera del conjunto cerrado o entradas de tipo incorrecto."""


def resolver_prediccion(
    autorizacion: ReporteAutorizacionOperativaML,
    decision_continuidad: DecisionContinuidadML,
) -> ReportePrediccionJuego:
    """Prioridad: numeracion invalida > datos insuficientes > NO-GO >
    sin evaluacion del holdout. `motivos` incluye todos los bloqueos
    aplicables; `SIN_EVALUACION_HOLDOUT` aplica siempre en AE-43."""
    if not isinstance(autorizacion, ReporteAutorizacionOperativaML):
        raise PrediccionNoAutorizadaError("autorizacion debe ser un ReporteAutorizacionOperativaML de AE-41")
    if not isinstance(decision_continuidad, DecisionContinuidadML):
        raise PrediccionNoAutorizadaError("decision_continuidad debe ser un DecisionContinuidadML de AE-39")
    if autorizacion.juego_codigo not in JUEGOS_AUTORIZADOS_AE40:
        raise PrediccionNoAutorizadaError(
            f"'{autorizacion.juego_codigo}' no esta autorizado -unicamente {sorted(JUEGOS_AUTORIZADOS_AE40)}"
        )

    motivos: list[EstadoPrediccionML] = []
    if autorizacion.estado is EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA:
        motivos.append(EstadoPrediccionML.BLOQUEADO_NUMERACION_INVALIDA)
    elif autorizacion.estado is EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES:
        motivos.append(EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES)
    if decision_continuidad is DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE:
        motivos.append(EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO)
    motivos.append(EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT)

    explicacion = "Prediccion bloqueada: " + "; ".join(_EXPLICACIONES[m] for m in motivos) + "."
    return ReportePrediccionJuego(
        juego_codigo=autorizacion.juego_codigo,
        estado=motivos[0],
        motivos=tuple(motivos),
        explicacion=explicacion,
        disclaimer=DISCLAIMER_PERMANENTE,
    )
