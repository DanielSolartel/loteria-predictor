"""
Puerto: almacen del laboratorio de modelos (Producto 4).

Informes de experimento y pronosticos inmutables, identificados por su
clave determinista. Guardar dos veces la misma clave lanza
`FileExistsError` (nunca sobrescribe); el llamador devuelve lo ya guardado.
Los pronosticos se ordenan por linea de modelo y objetivo con una secuencia
sellada, nunca por fecha ni nombre.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardadoLaboratorio:
    identificador: str
    juego: str
    artefacto: dict
    linea: str | None = None
    reutilizado: bool = False
    version: int = 1
    versiones: int = 1

    @property
    def objetivo(self) -> int | None:
        return self.artefacto.get("pronostico", {}).get("objetivo")

    @property
    def secuencia(self) -> int:
        return int((self.artefacto.get("generacion") or {}).get("secuencia_en_la_linea") or 0)


@dataclass(frozen=True)
class IlegibleLaboratorio:
    identificador: str
    juego: str
    motivo: str
    linea: str | None = None
    objetivo: int | None = None


class LaboratorioStore(ABC):
    @abstractmethod
    def guardar_experimento(self, artefacto: dict) -> GuardadoLaboratorio: ...

    @abstractmethod
    def obtener_experimento(self, clave: str) -> GuardadoLaboratorio | IlegibleLaboratorio | None: ...

    @abstractmethod
    def experimentos(self, juego: str) -> list: ...

    @abstractmethod
    def guardar_pronostico(self, artefacto: dict) -> GuardadoLaboratorio: ...

    @abstractmethod
    def obtener_pronostico(self, clave: str) -> GuardadoLaboratorio | IlegibleLaboratorio | None: ...

    @abstractmethod
    def lineas(self, juego: str) -> list[str]: ...

    @abstractmethod
    def pronosticos(self, juego: str, linea: str) -> list: ...
