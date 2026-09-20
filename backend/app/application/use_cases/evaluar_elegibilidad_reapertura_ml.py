"""
Caso de uso: EvaluarElegibilidadReaperturaML -Etapa AE-40,
validada.

Unico punto de union entre infraestructura (repositorios reales) y
el nucleo puro `application/ml/reapertura.py`. Consulta EXCLUSIVAMENTE
el puerto dedicado de disponibilidad (`DisponibilidadHoldoutRepository`)
-nunca `ResultadosHistoricosRepository`, nunca ejecuta ninguna
evaluacion de Machine Learning, nunca invoca los casos de uso de
AE-36/AE-37/AE-38, nunca persiste nada. Solo Baloto y Baloto Revancha
estan autorizados, igual que AE-36/37/38/39; MiLoto y ColorLoto se
rechazan explicitamente antes de consultar cualquier repositorio.

ALCANCE DE VALIDACION (deliberadamente dividido en dos capas, ver
tambien el docstring de `reapertura.py`): este caso de uso es el
UNICO responsable de comprobar que el `ResumenDisponibilidadHoldout`
devuelto por el repositorio corresponde EFECTIVAMENTE al
`codigo_juego` solicitado -el nucleo puro nunca recibe ese dato y
por tanto nunca puede detectar esta inconsistencia por si solo. Si
el repositorio devolviera (por un defecto de infraestructura) el
resumen de un juego distinto, la operacion se detiene aqui, antes de
producir cualquier reporte."""
from __future__ import annotations

from app.application.exceptions import DominioError, JuegoNoEncontradoError
from app.application.interfaces.disponibilidad_holdout_repository import DisponibilidadHoldoutRepository
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.ml.reapertura import (
    JUEGOS_AUTORIZADOS_AE40,
    DisponibilidadHoldoutInvalidaError,
    evaluar_elegibilidad_reapertura_ml,
)
from app.application.ml.incertidumbre import PROXIMO_HOLDOUT_INICIO
from app.application.ml.tipos import ReporteElegibilidadReaperturaML


class JuegoNoAutorizadoParaReaperturaError(DominioError):
    """Etapa AE-40: mismo criterio exacto de AE-36/37/38/39 -MiLoto
    (NO-GO temporal) y ColorLoto (pospuesto) nunca deben entrar a
    este gate."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)


class EvaluarElegibilidadReaperturaML:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        disponibilidad_repository: DisponibilidadHoldoutRepository,
    ):
        self._juegos = juego_repository
        self._disponibilidad = disponibilidad_repository

    def ejecutar(self, codigo_juego: str) -> ReporteElegibilidadReaperturaML:
        if codigo_juego not in JUEGOS_AUTORIZADOS_AE40:
            raise JuegoNoAutorizadoParaReaperturaError(
                f"'{codigo_juego}' no esta autorizado para AE-40 -"
                f"unicamente {sorted(JUEGOS_AUTORIZADOS_AE40)}"
            )

        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)

        resumen = self._disponibilidad.obtener_resumen_disponibilidad(
            juego.id, codigo_juego, PROXIMO_HOLDOUT_INICIO,
        )

        if resumen.juego_codigo != codigo_juego:
            raise DisponibilidadHoldoutInvalidaError(
                f"El resumen de disponibilidad corresponde a '{resumen.juego_codigo}', "
                f"pero se solicito '{codigo_juego}' -mezcla de juegos detectada, "
                f"la operacion se detiene antes de producir cualquier reporte"
            )

        return evaluar_elegibilidad_reapertura_ml(resumen)
