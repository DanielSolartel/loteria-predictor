from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.juego import Juego


class JuegoRepository(ABC):
    @abstractmethod
    def obtener_por_codigo(self, codigo: str) -> Juego | None:
        ...

    @abstractmethod
    def obtener_por_id(self, juego_id: UUID) -> Juego | None:
        ...

    @abstractmethod
    def listar_activos(self) -> list[Juego]:
        ...

    @abstractmethod
    def guardar(self, juego: Juego) -> Juego:
        ...
