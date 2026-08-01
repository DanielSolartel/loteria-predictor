from __future__ import annotations

from uuid import UUID

from app.application.interfaces.sorteo_repository import SorteoRepository


class EliminarSorteo:
    def __init__(self, sorteo_repository: SorteoRepository):
        self._sorteos = sorteo_repository

    def ejecutar(self, sorteo_id: UUID) -> None:
        self._sorteos.eliminar(sorteo_id)
