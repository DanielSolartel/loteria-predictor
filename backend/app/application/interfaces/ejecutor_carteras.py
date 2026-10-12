"""
Puerto: donde se entrenan los componentes, se calcula el vector fuente y se
simula en Producto 5.

Como en Producto 4, nada de esto se ejecuta en el proceso que atiende la web:
la aplicacion usa un proceso trabajador dedicado
(`app/infrastructure/carteras_trabajador.py`) con un TIEMPO MAXIMO por
trabajo. Recibe la instantanea ya congelada (sin sesiones SQL) o las carteras
guardadas, informa el progreso y devuelve el resultado; nunca escribe. La
publicacion la hace el proceso padre.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.application.interfaces.ejecutor_laboratorio import TiempoAgotadoError, TrabajadorFallidoError

__all__ = ["EjecutorDeCarteras", "TiempoAgotadoError", "TrabajadorFallidoError"]


class EjecutorDeCarteras(ABC):
    @abstractmethod
    def comparar(self, instantanea, protocolo, avance: Callable[..., None] | None = None) -> tuple[dict, dict]:
        """(cuerpo, tiempos) de `carteras_ensemble.evaluar`."""

    @abstractmethod
    def fuente(self, instantanea, modelo: str, perfil: str, avance: Callable[..., None] | None = None) -> dict:
        """Vector fuente de `carteras_ensemble.fuente`."""

    @abstractmethod
    def simular(self, identidad: dict, elegida: dict, uniforme: dict,
                avance: Callable[..., None] | None = None) -> dict:
        """Cuerpo de `carteras_artefactos.cuerpo_de_simulacion`."""

    def fuente_registrada(self, artefacto: dict, estimador: bytes, instantanea,
                          avance: Callable[..., None] | None = None) -> dict:
        """Fase 3: vector fuente con un modelo registrado congelado
        (`modelos_registrados.fuente_registrada`), sin reentrenar."""
        raise NotImplementedError
