"""
Puerto: almacen de Producto 5 (comparaciones del modelo combinado, carteras,
simulaciones y configuraciones).

Artefactos inmutables identificados por su clave determinista. Guardar dos
veces la misma clave lanza `FileExistsError` (nunca sobrescribe); el
llamador devuelve lo ya guardado. Las carteras se ordenan por linea y
objetivo con una secuencia sellada, nunca por fecha, hash, mtime ni orden
de directorio. Las configuraciones son versiones numeradas e inmutables.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardadoCarteras:
    identificador: str
    juego: str
    tipo: str
    artefacto: dict
    linea: str | None = None
    reutilizado: bool = False
    version: int = 1
    versiones: int = 1

    @property
    def objetivo(self) -> int | None:
        if self.tipo == "cartera":
            return self.artefacto.get("cartera", {}).get("objetivo")
        return self.artefacto.get("objetivo")

    @property
    def secuencia(self) -> int:
        return int((self.artefacto.get("generacion") or {}).get("secuencia_en_la_linea") or 0)


@dataclass(frozen=True)
class IlegibleCarteras:
    identificador: str
    juego: str
    tipo: str
    motivo: str
    linea: str | None = None
    objetivo: int | None = None


class CarterasStore(ABC):
    @abstractmethod
    def guardar_comparacion(self, artefacto: dict) -> GuardadoCarteras: ...

    @abstractmethod
    def obtener_comparacion(self, clave: str) -> GuardadoCarteras | IlegibleCarteras | None: ...

    @abstractmethod
    def comparaciones(self, juego: str) -> list: ...

    @abstractmethod
    def guardar_cartera(self, artefacto: dict) -> GuardadoCarteras: ...

    @abstractmethod
    def obtener_cartera(self, clave: str) -> GuardadoCarteras | IlegibleCarteras | None: ...

    @abstractmethod
    def lineas(self, juego: str) -> list[str]: ...

    @abstractmethod
    def carteras(self, juego: str, linea: str) -> list: ...

    @abstractmethod
    def guardar_simulacion(self, artefacto: dict) -> GuardadoCarteras: ...

    @abstractmethod
    def obtener_simulacion(self, clave: str) -> GuardadoCarteras | IlegibleCarteras | None: ...

    @abstractmethod
    def simulaciones(self, juego: str) -> list: ...

    @abstractmethod
    def guardar_configuracion(self, juego: str, crear_cuerpo) -> GuardadoCarteras: ...

    @abstractmethod
    def configuraciones(self, juego: str) -> list: ...
