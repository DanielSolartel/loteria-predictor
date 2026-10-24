"""
Puerto: donde se ejecuta la simulacion de la Fase 7.

Como en Productos 4 y 5, la simulacion no corre en el proceso que atiende la
web: la aplicacion usa un proceso trabajador dedicado
(`app/infrastructure/simulaciones_trabajador.py`) con TIEMPO MAXIMO. Recibe
el historico canonico ya leido (sin sesiones SQL), informa el progreso por
lotes y devuelve el contenido; nunca escribe. La publicacion en la tabla
`simulaciones` la hace el proceso padre, en una transaccion propia.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.application.interfaces.ejecutor_laboratorio import TiempoAgotadoError, TrabajadorFallidoError

__all__ = ["EjecutorDeSimulaciones", "TiempoAgotadoError", "TrabajadorFallidoError"]


class EjecutorDeSimulaciones(ABC):
    @abstractmethod
    def simular(self, juego: str, sorteos: list, iteraciones: int, semilla: int,
                avance: Callable[..., None] | None = None) -> dict:
        """`sorteos`: forma canonica (`laboratorio_variables.sorteos_canonicos`)
        hasta el corte. Devuelve {"contenido", "procesamiento", "historico_sha256",
        "duracion_ms"}."""
