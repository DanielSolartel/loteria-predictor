"""
Caso de uso: DiagnosticarEstadoPrediccion -Etapa AE-46, validada.

Expone por juego el diagnostico estructurado del bloqueo
(`diagnosticar_bloqueo`): estado y motivos identicos a los de AE-44,
progreso de sorteos nuevos desde 2706 y condiciones pendientes. Una
sola llamada a AE-41 por ejecucion (solo metadatos agregados).

Reutiliza, sin copiarlos, el registro inmutable de decisiones de
AE-39 y sus errores definidos en AE-44 -el registro se lee del modulo
de AE-44 en cada ejecucion, sin decision por defecto. No lee numeros
ganadores, no construye filas de inferencia, no entrena, no predice ni
persiste. No esta expuesto en rutas, plantillas, scripts ni `main`."""
from __future__ import annotations

from app.application.exceptions import DominioError
from app.application.ml.diagnostico_bloqueo import DiagnosticoBloqueoJuego, diagnosticar_bloqueo
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.use_cases import resolver_estado_prediccion as registro_ae44
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML
from app.application.use_cases.resolver_estado_prediccion import (
    DecisionContinuidadAusenteError,
    JuegoNoAutorizadoParaEstadoPrediccionError,
)


class DiagnosticarEstadoPrediccion:
    def __init__(self, caso_uso_autorizacion: EvaluarAutorizacionOperativaML):
        self._caso_uso_autorizacion = caso_uso_autorizacion

    def ejecutar(self, codigo_juego: str) -> DiagnosticoBloqueoJuego:
        if codigo_juego not in JUEGOS_AUTORIZADOS_AE40:
            raise JuegoNoAutorizadoParaEstadoPrediccionError(
                f"'{codigo_juego}' no esta autorizado para AE-46 -"
                f"unicamente {sorted(JUEGOS_AUTORIZADOS_AE40)}"
            )
        decisiones = registro_ae44.DECISIONES_CONTINUIDAD_AE39
        if codigo_juego not in decisiones:
            raise DecisionContinuidadAusenteError(
                f"No existe decision de AE-39 registrada para '{codigo_juego}' -"
                f"no se usa ninguna decision por defecto"
            )
        decision = decisiones[codigo_juego]

        autorizacion = self._caso_uso_autorizacion.ejecutar(codigo_juego)
        if autorizacion.juego_codigo != codigo_juego:
            raise DominioError(
                f"AE-41 devolvio un reporte de '{autorizacion.juego_codigo}' para '{codigo_juego}'"
            )

        return diagnosticar_bloqueo(autorizacion, decision)
