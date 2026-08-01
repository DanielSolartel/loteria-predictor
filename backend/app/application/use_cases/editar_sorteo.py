"""
Caso de uso: EditarSorteo.

Reutiliza la misma validación de `LotteryGame.validate_draw` que
`RegistrarSorteo` -editar un sorteo con un resultado inválido debe
rechazarse exactamente igual que registrarlo inválido por primera
vez. No hay reglas de validación duplicadas entre ambos casos de
uso.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.application.exceptions import (
    JuegoNoEncontradoError,
    SorteoInvalidoError,
    SorteoNoEncontradoError,
)
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.application.use_cases.game_factory import GameFactory
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.combination import Combination

DIAS_SEMANA_ES = [
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
]


@dataclass
class EditarSorteoInput:
    sorteo_id: UUID
    fecha: date
    resultado: Combination
    fuente: str | None = None


class EditarSorteo:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        sorteo_repository: SorteoRepository,
        game_factory: GameFactory,
    ):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository
        self._game_factory = game_factory

    def ejecutar(self, datos: EditarSorteoInput) -> Sorteo:
        sorteo_actual = self._sorteos.obtener_por_id(datos.sorteo_id)
        if sorteo_actual is None:
            raise SorteoNoEncontradoError(str(datos.sorteo_id))

        juego = self._juegos.obtener_por_id(sorteo_actual.juego_id)
        if juego is None:
            raise JuegoNoEncontradoError(str(sorteo_actual.juego_id))

        lottery_game = self._game_factory.crear(juego)
        validacion = lottery_game.validate_draw(datos.resultado)
        if not validacion:
            raise SorteoInvalidoError(validacion.errors)

        sorteo_actualizado = Sorteo(
            id=sorteo_actual.id,
            juego_id=sorteo_actual.juego_id,
            numero_sorteo=sorteo_actual.numero_sorteo,
            fecha=datos.fecha,
            dia_semana=DIAS_SEMANA_ES[datos.fecha.weekday()],
            resultado=datos.resultado,
            fuente=datos.fuente,
            creado_en=sorteo_actual.creado_en,
        )
        return self._sorteos.actualizar(sorteo_actualizado)
