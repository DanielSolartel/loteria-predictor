"""
Entidad EjecucionSincronizacion.

Cada vez que `SincronizarSorteos` corre (manual o eventualmente
programado), queda un registro de esta entidad. Es lo que alimenta
la sección "Importación" del dashboard: estado del conector, última
sincronización, cantidad importada, tiempo de sincronización, y el
detalle de qué sorteos fallaron y por qué -sin que el usuario tenga
que ir a leer el archivo de log para saber qué pasó.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

ESTADOS_VALIDOS = {"en_progreso", "completado", "fallido"}


@dataclass
class EjecucionSincronizacion:
    id: UUID | None
    juego_id: UUID
    conector: str
    iniciado_en: datetime
    estado: str
    finalizado_en: datetime | None = None
    sorteos_nuevos: int = 0
    sorteos_fallidos: int = 0
    sorteos_duplicados: int = 0
    sorteos_incompletos: int = 0
    total_sorteos_encontrados: int = 0
    duracion_ms: int | None = None
    ultimo_sorteo_importado: int | None = None
    detalle_errores: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS_VALIDOS:
            raise ValueError(f"Estado de sincronización inválido: {self.estado}")

    def marcar_completada(
        self,
        sorteos_nuevos: int,
        errores: list[dict],
        duracion_ms: int,
        ultimo_sorteo_importado: int | None,
        finalizado_en: datetime,
        sorteos_duplicados: int = 0,
        sorteos_incompletos: int = 0,
        total_sorteos_encontrados: int = 0,
    ) -> None:
        self.estado = "completado" if not errores or sorteos_nuevos > 0 else "fallido"
        self.sorteos_nuevos = sorteos_nuevos
        self.sorteos_fallidos = len(errores)
        self.sorteos_duplicados = sorteos_duplicados
        self.sorteos_incompletos = sorteos_incompletos
        self.total_sorteos_encontrados = total_sorteos_encontrados
        self.detalle_errores = errores
        self.duracion_ms = duracion_ms
        self.ultimo_sorteo_importado = ultimo_sorteo_importado
        self.finalizado_en = finalizado_en

    def marcar_fallida(self, error: str, finalizado_en: datetime) -> None:
        self.estado = "fallido"
        self.detalle_errores = [{"error": error}]
        self.finalizado_en = finalizado_en

    @property
    def porcentaje_exito(self) -> float:
        if self.total_sorteos_encontrados == 0:
            return 100.0
        return round(100.0 * self.sorteos_nuevos / self.total_sorteos_encontrados, 1)
