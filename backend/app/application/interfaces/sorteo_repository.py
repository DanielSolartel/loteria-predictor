"""
Puerto: SorteoRepository.

La capa de aplicación depende de esta interfaz, nunca de SQLAlchemy
directamente. La implementación concreta vive en
infrastructure/repositories y se inyecta vía el contenedor de DI de
la API. Esto permite, por ejemplo, testear casos de uso con un
repositorio en memoria sin levantar PostgreSQL.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.domain.entities.sorteo import Sorteo


class SorteoRepository(ABC):
    @abstractmethod
    def guardar(self, sorteo: Sorteo) -> Sorteo:
        """Persiste un sorteo nuevo. Debe lanzar `SorteoDuplicadoError`
        si ya existe un sorteo con el mismo juego_id + numero_sorteo."""

    @abstractmethod
    def obtener_por_id(self, sorteo_id: UUID) -> Sorteo | None:
        ...

    @abstractmethod
    def existe(self, juego_id: UUID, numero_sorteo: int) -> bool:
        ...

    @abstractmethod
    def listar_por_juego(
        self,
        juego_id: UUID,
        desde: date | None = None,
        hasta: date | None = None,
        limite: int = 100,
        offset: int = 0,
    ) -> list[Sorteo]:
        ...

    @abstractmethod
    def contar_por_juego(self, juego_id: UUID) -> int:
        ...

    @abstractmethod
    def ultimo_sorteo(self, juego_id: UUID) -> Sorteo | None:
        """Útil para saber desde qué numero_sorteo continuar al
        importar datos nuevos incrementalmente."""

    @abstractmethod
    def actualizar(self, sorteo: Sorteo) -> Sorteo:
        """Reemplaza el resultado de un sorteo existente (identificado
        por `sorteo.id`). Debe lanzar `SorteoNoEncontradoError` si no
        existe."""

    @abstractmethod
    def eliminar(self, sorteo_id: UUID) -> None:
        """Elimina un sorteo. Debe lanzar `SorteoNoEncontradoError` si
        no existe."""
