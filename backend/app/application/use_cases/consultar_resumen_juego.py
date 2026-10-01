"""
Caso de uso: resumen estadistico de un juego (Producto 1).

Lee el historico con `ResultadosHistoricosRepository` (solo lectura, sin
escribir la cache de `estadisticas`) y arma el resumen con
`app.application.estadisticas.resumen_juego`. Las reglas vienen de la
clase de dominio creada por `GameFactory`; la paleta de ColorLoto, de la
tabla `colores`.
"""
from __future__ import annotations

from datetime import date

from app.application.estadisticas.resumen_juego import resumen_juego_colorloto, resumen_juego_numerico
from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.use_cases.game_factory import GameFactory
from app.domain.games.colorloto import BALLS_TO_PICK, NUMBER_RANGE

SLUG_A_CODIGO_RESUMEN = {
    "baloto": "BALOTO",
    "baloto-revancha": "BALOTO_REVANCHA",
    "miloto": "MILOTO",
    "colorloto": "COLORLOTO",
}


class ConsultarResumenJuego:
    def __init__(self, juego_repository: JuegoRepository, resultados_repository: ResultadosHistoricosRepository,
                 color_repository: ColorRepository):
        self._juegos = juego_repository
        self._resultados = resultados_repository
        self._colores = color_repository

    def ejecutar(self, codigo_juego: str, *, hoy: date, hasta_numero_sorteo: int | None = None) -> dict:
        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)
        if codigo_juego == "COLORLOTO":
            colores = [c.codigo for c in self._colores.listar_vigentes(juego.id)]
            resultados = self._resultados.listar_resultados_colorloto(juego.id)
            return resumen_juego_colorloto(resultados, nombre=juego.nombre, rango=NUMBER_RANGE,
                                           cantidad_balotas=BALLS_TO_PICK, colores=colores, hoy=hoy,
                                           hasta_numero_sorteo=hasta_numero_sorteo)
        dominio = GameFactory(self._colores).crear(juego)
        resultados = self._resultados.listar_resultados_numericos(juego.id)
        return resumen_juego_numerico(
            resultados, codigo_juego=codigo_juego, nombre=juego.nombre, rango=dominio.number_range,
            cantidad_numeros=dominio.numbers_to_pick,
            rango_superbalota=dominio.superballot_range if dominio.has_superballot else None,
            hoy=hoy, hasta_numero_sorteo=hasta_numero_sorteo)
