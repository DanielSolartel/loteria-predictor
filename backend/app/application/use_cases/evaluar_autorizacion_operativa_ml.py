"""
Caso de uso: EvaluarAutorizacionOperativaML -Etapa AE-41,
validada.

Unico punto de union entre la politica pura de bloqueo operativo
(`application/ml/autorizacion_operativa.py`) y el gate YA VALIDADO
de AE-40 (`EvaluarElegibilidadReaperturaML`, recibido por inyeccion
de dependencias -nunca reconstruido ni reimplementado aqui). Delega
completamente la evaluacion de elegibilidad al caso de uso de AE-40
-unica fuente funcional de verdad sobre elegibilidad- y traduce su
resultado (o su excepcion) a una decision de autorizacion operativa.

Nunca consulta `ResultadosHistoricosRepository`, nunca observa
numeros ganadores, nunca construye datasets, nunca extrae features,
nunca entrena modelos, nunca genera predicciones, nunca persiste
nada. Solo Baloto y Baloto Revancha estan autorizados, igual que
AE-36/37/38/39/40; MiLoto y ColorLoto se rechazan explicitamente
antes de consultar cualquier repositorio -incluido el caso de uso de
AE-40, que nunca llega a invocarse para esos juegos."""
from __future__ import annotations

from app.application.exceptions import DominioError
from app.application.ml.autorizacion_operativa import (
    construir_reporte_bloqueado_por_numeracion_invalida,
    evaluar_autorizacion_operativa_desde_elegibilidad,
)
from app.application.ml.reapertura import DisponibilidadHoldoutInvalidaError, JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import ReporteAutorizacionOperativaML
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML

JUEGOS_AUTORIZADOS_AE41 = JUEGOS_AUTORIZADOS_AE40
"""Mismo conjunto cerrado exacto de AE-35/36/37/38/39/40, reutilizado
sin duplicar -nunca se mezclan Baloto y Baloto Revancha; cada juego
se evalua por separado."""


class JuegoNoAutorizadoParaAutorizacionOperativaError(DominioError):
    """Etapa AE-41: mismo criterio exacto de AE-36/37/38/39/40 -MiLoto
    (NO-GO temporal) y ColorLoto (pospuesto) nunca deben entrar a
    esta politica. Se comprueba en este caso de uso ANTES de invocar
    el caso de uso de AE-40 -nunca se le delega esta comprobacion,
    aunque AE-40 tambien la haga por su cuenta."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)


class EvaluarAutorizacionOperativaML:
    def __init__(self, caso_uso_elegibilidad: EvaluarElegibilidadReaperturaML):
        self._caso_uso_elegibilidad = caso_uso_elegibilidad

    def ejecutar(self, codigo_juego: str) -> ReporteAutorizacionOperativaML:
        if codigo_juego not in JUEGOS_AUTORIZADOS_AE41:
            raise JuegoNoAutorizadoParaAutorizacionOperativaError(
                f"'{codigo_juego}' no esta autorizado para AE-41 -"
                f"unicamente {sorted(JUEGOS_AUTORIZADOS_AE41)}"
            )

        try:
            reporte_elegibilidad = self._caso_uso_elegibilidad.ejecutar(codigo_juego)
        except DisponibilidadHoldoutInvalidaError as error:
            return construir_reporte_bloqueado_por_numeracion_invalida(codigo_juego, str(error))

        return evaluar_autorizacion_operativa_desde_elegibilidad(reporte_elegibilidad)
