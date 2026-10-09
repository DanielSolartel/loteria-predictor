"""Puerto del almacen de informes guardados de Producto 6."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InformeGuardado:
    clave: str
    juego: str
    artefacto: dict
    reutilizado: bool = False


@dataclass(frozen=True)
class InformeIlegible:
    clave: str
    juego: str
    motivo: str


class ResultadosStore(ABC):
    @abstractmethod
    def guardar(self, artefacto: dict) -> InformeGuardado:
        """Publica el informe sin sobrescribir; si ya existe la misma clave,
        devuelve el guardado con `reutilizado=True`."""

    @abstractmethod
    def obtener(self, clave: str) -> InformeGuardado | InformeIlegible | None: ...

    @abstractmethod
    def listar(self, juego: str) -> list[InformeGuardado | InformeIlegible]: ...
