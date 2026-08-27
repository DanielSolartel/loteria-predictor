"""
GameFactory: puente entre la entidad persistida `Juego` y la clase
de dominio `LotteryGame` que sabe razonar sobre sus reglas.

Es el único lugar del sistema que conoce el mapeo
`codigo -> clase concreta`. Añadir un cuarto juego significa: crear
su clase en domain/games, registrar una fila en la tabla `juegos`, y
añadir una línea aquí. Nada más se modifica.
"""
from __future__ import annotations

from uuid import UUID

from app.application.exceptions import JuegoNoSoportadoError
from app.application.interfaces.color_repository import ColorRepository
from app.domain.entities.juego import Juego
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from app.domain.games.base_game import LotteryGame
from app.domain.games.colorloto import ColorLotoGame
from app.domain.games.miloto import MiLotoGame

_JUEGOS_SIN_COLOR: dict[str, type[LotteryGame]] = {
    "MILOTO": MiLotoGame,
    "BALOTO": BalotoGame,
    "BALOTO_REVANCHA": BalotoRevanchaGame,
}


class GameFactory:
    def __init__(self, color_repository: ColorRepository):
        self._color_repository = color_repository

    def crear(self, juego: Juego) -> LotteryGame:
        if juego.codigo in _JUEGOS_SIN_COLOR:
            return _JUEGOS_SIN_COLOR[juego.codigo]()

        if juego.codigo == "COLORLOTO":
            juego_id: UUID = juego.id  # type: ignore[assignment]
            colores = self._color_repository.listar_vigentes(juego_id)
            return ColorLotoGame(colors=colores)

        raise JuegoNoSoportadoError(juego.codigo)
