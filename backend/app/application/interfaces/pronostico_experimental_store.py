"""
Puerto: almacen de pronosticos experimentales (Producto 1).

El identificador de cada artefacto es su `clave_de_entrada` (juego,
reglas, corte, historico, configuracion y versiones). Guardar dos veces la
misma clave no crea otro archivo ni cambia el primero: `guardar` lanza
`FileExistsError` y el llamador devuelve el ya guardado. Un historico
corregido produce otra clave y queda como otra version del mismo objetivo.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PronosticoGuardado:
    identificador: str
    codigo_juego: str
    artefacto: dict
    reutilizado: bool = False
    version: int | None = None
    """Posicion (desde 1) entre los artefactos validos del mismo objetivo,
    por la secuencia de emision sellada en cada artefacto
    (`generacion.secuencia_en_el_objetivo`), nunca por fecha ni nombre."""
    versiones: int | None = None


@dataclass(frozen=True)
class PronosticoIlegible:
    identificador: str
    codigo_juego: str
    motivo: str


class PronosticoExperimentalStore(ABC):
    @abstractmethod
    def guardar(self, codigo_juego: str, artefacto: dict) -> PronosticoGuardado:
        """Persiste el artefacto con su clave; `FileExistsError` si ya
        existe uno con la misma clave (nunca sobrescribe)."""

    @abstractmethod
    def listar(self, codigo_juego: str) -> list[PronosticoGuardado | PronosticoIlegible]:
        """Del objetivo mas reciente al mas antiguo y, dentro de cada
        objetivo, de la version mas reciente a la primera; los archivos
        alterados o ilegibles se devuelven como `PronosticoIlegible`."""

    @abstractmethod
    def obtener(self, codigo_juego: str, identificador: str) -> PronosticoGuardado | PronosticoIlegible | None:
        """None si no existe."""
