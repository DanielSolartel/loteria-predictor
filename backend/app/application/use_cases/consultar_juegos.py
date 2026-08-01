"""
Casos de uso de solo lectura sobre el catálogo de juegos.

`ObtenerJuego` combina la entidad persistida (`Juego`) con el
`LotteryGame` que construye `GameFactory`, para exponer también
metadatos calculados (tamaño del espacio muestral, dimensiones del
espacio de combinaciones) que no están en la tabla `juegos` pero son
información legítima de dominio -así la pantalla "Gestión de
juegos" no necesita reimplementar esos cálculos.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.use_cases.game_factory import GameFactory
from app.domain.entities.juego import Juego


@dataclass
class JuegoConReglas:
    juego: Juego
    espacio_muestral: int
    dimensiones: dict


class ListarJuegos:
    def __init__(self, juego_repository: JuegoRepository):
        self._juegos = juego_repository

    def ejecutar(self) -> list[Juego]:
        return self._juegos.listar_activos()


class ObtenerJuego:
    def __init__(self, juego_repository: JuegoRepository, game_factory: GameFactory):
        self._juegos = juego_repository
        self._game_factory = game_factory

    def ejecutar(self, codigo_juego: str) -> JuegoConReglas:
        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)

        lottery_game = self._game_factory.crear(juego)
        return JuegoConReglas(
            juego=juego,
            espacio_muestral=lottery_game.sample_space_size(),
            dimensiones=lottery_game.combination_space_dimensions(),
        )
