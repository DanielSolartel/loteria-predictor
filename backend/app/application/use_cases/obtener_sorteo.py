from __future__ import annotations

from uuid import UUID

from app.application.exceptions import SorteoNoEncontradoError
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.domain.entities.sorteo import Sorteo


class ObtenerSorteo:
    def __init__(self, sorteo_repository: SorteoRepository):
        self._sorteos = sorteo_repository

    def ejecutar(self, sorteo_id: UUID) -> Sorteo:
        sorteo = self._sorteos.obtener_por_id(sorteo_id)
        if sorteo is None:
            raise SorteoNoEncontradoError(str(sorteo_id))
        return sorteo
