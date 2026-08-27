"""
Caso de uso: EliminarSorteo.

Invalidación de caché: a diferencia de Registrar/Editar, `eliminar()`
no devuelve el sorteo eliminado -por eso se obtiene primero
(`obtener_por_id`) para capturar `juego_id`/`numero_sorteo` ANTES de
borrar. Si el sorteo no existe, se lanza `SorteoNoEncontradoError`
aquí mismo (mismo contrato que `sorteo_repository.eliminar` ya
garantizaba) -evita un viaje redundante al repositorio y deja claro
que la invalidación nunca ocurre si no había nada que eliminar.
"""
from __future__ import annotations

from uuid import UUID

from app.application.exceptions import SorteoNoEncontradoError
from app.application.interfaces.estadistica_repository import EstadisticaRepository
from app.application.interfaces.sorteo_repository import SorteoRepository


class EliminarSorteo:
    def __init__(self, sorteo_repository: SorteoRepository, estadistica_repository: EstadisticaRepository):
        self._sorteos = sorteo_repository
        self._estadisticas = estadistica_repository

    def ejecutar(self, sorteo_id: UUID) -> None:
        sorteo = self._sorteos.obtener_por_id(sorteo_id)
        if sorteo is None:
            raise SorteoNoEncontradoError(str(sorteo_id))

        self._sorteos.eliminar(sorteo_id)

        # Invalidación SOLO tras una eliminación exitosa.
        self._estadisticas.invalidar_por_juego(sorteo.juego_id, desde_numero_sorteo=sorteo.numero_sorteo)
