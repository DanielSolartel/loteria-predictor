"""
Caso de uso: EvaluarBaselineMLProbabilidadNumeros -Etapa AE-36,
validada.

Unico punto de union entre infraestructura (repositorios reales) y
el nucleo puro `application/ml/`. Nunca persiste nada -el reporte
devuelto existe solo en memoria durante esta ejecucion. Solo Baloto
y Baloto Revancha estan autorizados (Etapa AE-35, GO CONDICIONAL);
MiLoto (NO-GO temporal, 70 sorteos) y ColorLoto (pospuesto) se
rechazan explicitamente, nunca en silencio."""
from __future__ import annotations

from app.application.exceptions import DominioError, JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.ml.evaluacion import evaluar_juego
from app.application.ml.tipos import ReporteEvaluacionJuego
from app.application.use_cases.game_factory import GameFactory

JUEGOS_AUTORIZADOS_AE36 = frozenset({"BALOTO", "BALOTO_REVANCHA"})
"""Conjunto CERRADO -Etapa AE-35 emitio GO CONDICIONAL unicamente
para estos dos juegos; MiLoto y ColorLoto se rechazan explicitamente
sin importar cuantos sorteos tengan en el momento de ejecutar esta
etapa, porque la decision de AE-35 se basa en la auditoria real ya
ejecutada, no en un conteo dinamico."""


class JuegoNoAutorizadoParaMLError(DominioError):
    """Etapa AE-36: excepcion propia y pequena -MiLoto (NO-GO
    temporal) y ColorLoto (pospuesto) nunca deben entrar a este
    pipeline, sin importar su estado real de datos. Hereda
    directamente de `DominioError` (no de `JuegoNoSoportadoError`,
    cuyo constructor solo acepta un `codigo` y arma su propio
    mensaje fijo, incompatible con un mensaje libre como este)."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)


class EvaluarBaselineMLProbabilidadNumeros:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        resultados_historicos_repository: ResultadosHistoricosRepository,
        game_factory: GameFactory,
    ):
        self._juegos = juego_repository
        self._resultados = resultados_historicos_repository
        self._game_factory = game_factory

    def ejecutar(self, codigo_juego: str, semilla: int = 42) -> ReporteEvaluacionJuego:
        if codigo_juego not in JUEGOS_AUTORIZADOS_AE36:
            raise JuegoNoAutorizadoParaMLError(
                f"'{codigo_juego}' no esta autorizado para Machine Learning en AE-36 -"
                f"unicamente {sorted(JUEGOS_AUTORIZADOS_AE36)} recibieron GO en AE-35"
            )

        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)

        juego_dominio = self._game_factory.crear(juego)
        rango_min, rango_max = juego_dominio.number_range
        cantidad_numeros = juego_dominio.numbers_to_pick

        historico = self._resultados.listar_resultados_numericos(juego.id)

        return evaluar_juego(historico, rango_min, rango_max, cantidad_numeros, codigo_juego, semilla=semilla)
