"""
Puerto: HtmlStorage.

Los conectores dependen de esta abstracción, no de `open()`
directamente -así el almacenamiento del HTML crudo (requisito
explícito: poder reprocesar sin volver a golpear el sitio si cambia
su estructura) se puede mover a otro backend (S3, etc.) sin tocar
ningún conector.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class HtmlStorage(ABC):
    @abstractmethod
    def guardar(self, prefijo: str, draw_id: str, html: str) -> str:
        """Guarda el HTML crudo y devuelve la ruta/clave donde quedó."""

    @abstractmethod
    def leer(self, prefijo: str, draw_id: str) -> str | None:
        """Lee un HTML previamente guardado, o None si no existe."""

    @abstractmethod
    def listar(self, prefijo: str) -> list[str]:
        """Lista los draw_id con HTML guardado para un prefijo (juego)."""
