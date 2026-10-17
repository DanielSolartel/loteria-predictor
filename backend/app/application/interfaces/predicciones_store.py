"""
Puerto: almacen de explicaciones de predicciones de la Fase 4. Artefactos
inmutables (nunca se sobrescriben ni se borran): la misma entrada reutiliza
la explicacion; una entrada distinta crea otra.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ExplicacionGuardada:
    clave: str
    juego: str
    artefacto: dict
    reutilizado: bool = False

    @property
    def cartera(self) -> str:
        return self.artefacto["cartera"]["clave"]


@dataclass(frozen=True)
class ExplicacionIlegible:
    clave: str
    juego: str
    motivo: str


class PrediccionesStore(ABC):
    @abstractmethod
    def guardar(self, artefacto: dict) -> ExplicacionGuardada: ...

    @abstractmethod
    def obtener(self, clave: str) -> ExplicacionGuardada | ExplicacionIlegible | None: ...

    @abstractmethod
    def de_cartera(self, juego: str, cartera: str) -> list[ExplicacionGuardada | ExplicacionIlegible]:
        """Explicaciones de una cartera (normalmente una por version de la explicacion)."""

    @abstractmethod
    def listar(self, juego: str) -> list[ExplicacionGuardada | ExplicacionIlegible]: ...
