"""
Caso de uso: ResolverEstadoPrediccion -Etapa AE-44, validada.

Punto de entrada por juego de la Fase 4 (el roadmap lo nombra
`GenerarPredicciones`; ese nombre queda reservado para una etapa
futura con evidencia prospectiva). Une, sin reevaluarlos:
- el estado operativo real de AE-41 (`EvaluarAutorizacionOperativaML`,
  que solo consulta metadatos agregados desde 2706);
- la decision cientifica validada de AE-39, tomada de un registro
  inmutable por juego (`DECISIONES_CONTINUIDAD_AE39`);
- el resolvedor puro de AE-43 (`resolver_prediccion`).

Siempre devuelve un `ReportePrediccionJuego` BLOQUEADO: no lee
numeros ganadores, no construye filas de inferencia, no entrena, no
predice ni persiste. No esta expuesto en rutas, plantillas ni
scripts.

Procedencia de las decisiones AE-39 (validadas por el usuario en
Windows/Python 3.14.6, analisis sobre los 18 bloques externos de
AE-38, historico de desarrollo 2081..2590; ver ARCHITECTURE.md,
seccion AE-39). Diferencias uniforme - modelo, positivo = mejora:
- BALOTO: Log Loss -0.000136584231 (IC95% [-0.000217, -0.000051]),
  Brier -0.000026473413 (IC95% [-0.000044, -0.000008]) ->
  NO_GO_SIN_EVIDENCIA_SUFICIENTE.
- BALOTO_REVANCHA: Log Loss -0.000647734500 (IC95% [-0.001108,
  -0.000231]), Brier -0.000137653795 (IC95% [-0.000237, -0.000050])
  -> NO_GO_SIN_EVIDENCIA_SUFICIENTE."""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from app.application.exceptions import DominioError
from app.application.ml.prediccion_bloqueada import resolver_prediccion
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import DecisionContinuidadML, ReportePrediccionJuego
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML

PROCEDENCIA_DECISIONES_AE39 = (
    "AE-39 validada: bootstrap por bloques sobre los 18 bloques externos de AE-38 (2081..2590). "
    "BALOTO Log Loss -0.000136584231, Brier -0.000026473413; "
    "BALOTO_REVANCHA Log Loss -0.000647734500, Brier -0.000137653795 -> NO-GO en ambos."
)

DECISIONES_CONTINUIDAD_AE39: Mapping[str, DecisionContinuidadML] = MappingProxyType({
    "BALOTO": DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE,
    "BALOTO_REVANCHA": DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE,
})
"""Registro inmutable de las decisiones validadas de AE-39 por juego
(procedencia en `PROCEDENCIA_DECISIONES_AE39` y en el docstring del
modulo). No se recalcula ni se lee de ningun archivo; cambiarlo
exigira una etapa propia con evidencia prospectiva."""


class JuegoNoAutorizadoParaEstadoPrediccionError(DominioError):
    """MiLoto (NO-GO temporal) y ColorLoto (pospuesto) se rechazan
    antes de consultar cualquier repositorio."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)


class DecisionContinuidadAusenteError(DominioError):
    """Falta la decision de AE-39 para un juego autorizado -nunca se
    usa una decision por defecto."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)


class ResolverEstadoPrediccion:
    def __init__(self, caso_uso_autorizacion: EvaluarAutorizacionOperativaML):
        self._caso_uso_autorizacion = caso_uso_autorizacion

    def ejecutar(self, codigo_juego: str) -> ReportePrediccionJuego:
        if codigo_juego not in JUEGOS_AUTORIZADOS_AE40:
            raise JuegoNoAutorizadoParaEstadoPrediccionError(
                f"'{codigo_juego}' no esta autorizado para AE-44 -"
                f"unicamente {sorted(JUEGOS_AUTORIZADOS_AE40)}"
            )
        if codigo_juego not in DECISIONES_CONTINUIDAD_AE39:
            raise DecisionContinuidadAusenteError(
                f"No existe decision de AE-39 registrada para '{codigo_juego}' -"
                f"no se usa ninguna decision por defecto"
            )
        decision = DECISIONES_CONTINUIDAD_AE39[codigo_juego]

        autorizacion = self._caso_uso_autorizacion.ejecutar(codigo_juego)
        if autorizacion.juego_codigo != codigo_juego:
            raise DominioError(
                f"AE-41 devolvio un reporte de '{autorizacion.juego_codigo}' para '{codigo_juego}'"
            )

        return resolver_prediccion(autorizacion, decision)
