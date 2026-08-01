from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.domain.value_objects.color import Color


class ColorRepository(ABC):
    @abstractmethod
    def listar_vigentes(self, juego_id: UUID, en_fecha: date | None = None) -> list[Color]:
        """Colores activos y vigentes en `en_fecha` (hoy si no se
        especifica). Es la fuente de verdad que alimenta al
        constructor de `ColorLotoGame`."""

    @abstractmethod
    def guardar(self, juego_id: UUID, color: Color) -> Color:
        ...

    @abstractmethod
    def cerrar_vigencia(self, juego_id: UUID, codigo: str, hasta: date) -> None:
        """Cierra la vigencia de un color retirado sin borrar el
        histórico -los sorteos pasados que usaron ese color siguen
        siendo válidos y consultables."""
