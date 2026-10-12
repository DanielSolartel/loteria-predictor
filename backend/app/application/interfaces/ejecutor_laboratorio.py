"""
Puerto: donde se entrenan y predicen los candidatos del laboratorio
(Producto 4).

El laboratorio nunca entrena en el proceso que atiende la web: los limites de
hilos de las bibliotecas numericas son de proceso y cambiarlos alli
alteraria el entorno compartido con Producto 3. La aplicacion usa un
ejecutor de proceso dedicado (`app/infrastructure/laboratorio_trabajador.py`)
que recibe la instantanea ya congelada (sin sesiones SQL), informa el
progreso y devuelve el resultado; `EjecutorEnEsteProceso` (en
`use_cases/laboratorio.py`) es solo para pruebas y no limita hilos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class TrabajadorFallidoError(Exception):
    """El proceso trabajador termino sin entregar resultado (murio, fue
    interrumpido o fallo de forma inesperada)."""


class TiempoAgotadoError(TrabajadorFallidoError):
    """El trabajador supero su tiempo maximo y se detuvo (estado
    `tiempo_agotado`). Nada se publico. Comun a Productos 4 y 5."""


class EjecutorDeLaboratorio(ABC):
    @abstractmethod
    def evaluar(self, instantanea, entradas, protocolo, avance: Callable[..., None] | None = None) -> tuple[dict, dict]:
        """(resultado determinista, tiempos) de `laboratorio_evaluacion.evaluar`."""

    @abstractmethod
    def pronostico(self, informe: dict, entrada) -> dict:
        """Cuerpo de `laboratorio_artefactos.cuerpo_del_pronostico`."""

    def entrenar(self, informe: dict, entrada, avance: Callable[..., None] | None = None) -> dict:
        """Fase 3: resultado de `modelos_registrados.entrenar` (estimador
        serializado, detalle y pronostico de control). No escribe nada."""
        raise NotImplementedError

    def control_registrado(self, artefacto: dict, estimador: bytes, informe: dict) -> dict:
        """Fase 3: `modelos_registrados.control_recargado` (verificacion)."""
        raise NotImplementedError

    def pronostico_registrado(self, artefacto: dict, estimador: bytes, sorteos: list) -> dict:
        """Fase 3: cuerpo de `modelos_registrados.cuerpo_del_pronostico_registrado`
        con el estimador recargado (sin reentrenar) y la instantanea canonica."""
        raise NotImplementedError
