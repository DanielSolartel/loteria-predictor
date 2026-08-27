"""
Puerto: SorteoRepository.

La capa de aplicación depende de esta interfaz, nunca de SQLAlchemy
directamente. La implementación concreta vive en
infrastructure/repositories y se inyecta vía el contenedor de DI de
la API. Esto permite, por ejemplo, testear casos de uso con un
repositorio en memoria sin levantar PostgreSQL.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.domain.entities.sorteo import Sorteo

ORDEN_CAMPOS_VALIDOS = {"fecha", "numero_sorteo"}
ORDEN_DIRECCIONES_VALIDAS = {"asc", "desc"}


@dataclass(frozen=True)
class FiltroSorteos:
    """Agrupa todos los criterios de consulta de sorteos -filtros,
    orden y paginación- en un solo objeto, en vez de una lista de
    parámetros que crece cada vez que se agrega un filtro nuevo.
    Extender la búsqueda en el futuro (p.ej. filtrar por fuente) es
    agregar un campo aquí, no tocar la firma de cada implementación
    del repositorio."""

    desde: date | None = None
    hasta: date | None = None
    numero_desde: int | None = None
    numero_hasta: int | None = None
    orden_campo: str = "fecha"
    orden_direccion: str = "desc"
    limite: int = 100
    offset: int = 0

    def __post_init__(self) -> None:
        if self.orden_campo not in ORDEN_CAMPOS_VALIDOS:
            raise ValueError(f"orden_campo inválido: {self.orden_campo!r} (válidos: {ORDEN_CAMPOS_VALIDOS})")
        if self.orden_direccion not in ORDEN_DIRECCIONES_VALIDAS:
            raise ValueError(f"orden_direccion inválido: {self.orden_direccion!r}")
        if self.limite <= 0:
            raise ValueError("limite debe ser positivo")
        if self.offset < 0:
            raise ValueError("offset no puede ser negativo")


class SorteoRepository(ABC):
    @abstractmethod
    def guardar(self, sorteo: Sorteo) -> Sorteo:
        """Persiste un sorteo nuevo. Debe lanzar `SorteoDuplicadoError`
        si ya existe un sorteo con el mismo juego_id + numero_sorteo."""

    @abstractmethod
    def obtener_por_id(self, sorteo_id: UUID) -> Sorteo | None:
        ...

    @abstractmethod
    def existe(self, juego_id: UUID, numero_sorteo: int) -> bool:
        ...

    @abstractmethod
    def listar_por_juego(self, juego_id: UUID, filtro: FiltroSorteos) -> list[Sorteo]:
        """Consulta paginada a nivel de base de datos (LIMIT/OFFSET
        real, nunca carga todo el histórico en memoria). `filtro`
        controla filtros de fecha/número, orden y paginación."""

    @abstractmethod
    def contar_por_juego(self, juego_id: UUID, filtro: FiltroSorteos | None = None) -> int:
        """Total de sorteos que matchean los filtros de `filtro`
        (fecha/número). Si se omite, cuenta todos los del juego.
        `orden_campo`/`orden_direccion`/`limite`/`offset` de `filtro`
        se ignoran aquí -el conteo no pagina."""

    @abstractmethod
    def ultimo_sorteo(self, juego_id: UUID) -> Sorteo | None:
        """Útil para saber desde qué numero_sorteo continuar al
        importar datos nuevos incrementalmente."""

    @abstractmethod
    def obtener_por_numero(self, juego_id: UUID, numero_sorteo: int) -> Sorteo | None:
        """Búsqueda directa por número de sorteo -evita tener que
        cargar listados completos cuando solo se necesita saber si
        un sorteo puntual existe (p.ej. en el flujo de upsert de
        `ReprocesarSorteosDesdeHtml`)."""

    @abstractmethod
    def listar_numeros_sorteo(self, juego_id: UUID) -> list[int]:
        """Solo la columna `numero_sorteo`, sin los joins a
        numeros/superbalota/colores. Pensado para operaciones que
        solo necesitan la numeración (huecos, rango histórico) y no
        el resultado completo -evitar cargar y reconstruir cientos
        de entidades `Sorteo` completas para eso (usado por
        `ValidarIntegridadDatos`, que ahora se ejecuta automáticamente
        tras cada sincronización vía el Data Quality Report)."""

    @abstractmethod
    def actualizar(self, sorteo: Sorteo) -> Sorteo:
        """Reemplaza el resultado de un sorteo existente (identificado
        por `sorteo.id`). Debe lanzar `SorteoNoEncontradoError` si no
        existe."""

    @abstractmethod
    def eliminar(self, sorteo_id: UUID) -> None:
        """Elimina un sorteo. Debe lanzar `SorteoNoEncontradoError` si
        no existe."""
