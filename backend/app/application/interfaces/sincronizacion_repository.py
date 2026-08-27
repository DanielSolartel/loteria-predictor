from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.sincronizacion import EjecucionSincronizacion


class SincronizacionRepository(ABC):
    @abstractmethod
    def guardar(self, ejecucion: EjecucionSincronizacion) -> EjecucionSincronizacion:
        """Crea o actualiza (si `ejecucion.id` ya existe) un registro
        de ejecución de sincronización."""

    @abstractmethod
    def obtener_ultima(self, juego_id: UUID) -> EjecucionSincronizacion | None:
        ...

    @abstractmethod
    def listar_recientes(self, juego_id: UUID, limite: int = 20) -> list[EjecucionSincronizacion]:
        ...
