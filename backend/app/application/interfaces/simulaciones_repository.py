"""
Puerto: SimulacionesRepository (Fase 7).

La tabla `simulaciones` es la fuente canonica de los resultados de la
Fase 7. Este puerto solo traduce filas <-> `Simulacion` del dominio y
publica una fila COMPLETA; no calcula nada. El repositorio nunca confirma:
la transaccion la abre y la confirma quien lo usa (una lectura de solo
lectura o la publicacion, cada una en su propia sesion).

Publicar es idempotente por clave de identidad: dentro de la transaccion se
toma el recurso exclusivo de esa clave (advisory de transaccion en
PostgreSQL), se buscan filas con la misma clave y solo si no hay ninguna se
inserta. Si ya existe, se devuelve la existente (el llamador verifica su
integridad) y no se escribe nada.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.analitica import Simulacion


class PublicacionConcurrenteError(RuntimeError):
    """No se obtuvo el recurso de la clave en el tiempo maximo."""


class SimulacionesRepository(ABC):
    @abstractmethod
    def por_clave(self, juego_id: UUID, clave: str) -> list[Simulacion]:
        """Filas con esa clave de identidad, de la mas antigua a la mas reciente
        (mas de una solo si alguien inserto fuera de este puerto)."""

    @abstractmethod
    def obtener(self, identificador: UUID) -> Simulacion | None:
        ...

    @abstractmethod
    def listar(self, juego_id: UUID | None = None, limite: int = 50) -> list[Simulacion]:
        """Filas de la Fase 7 (las que tienen clave), mas recientes primero."""

    @abstractmethod
    def publicar(self, simulacion: Simulacion, clave: str) -> tuple[Simulacion, bool]:
        """(fila, creada). `creada` es False si ya habia una con la misma clave."""
