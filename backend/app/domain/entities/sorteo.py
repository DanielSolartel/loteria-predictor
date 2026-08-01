"""
Entidad Sorteo.

A diferencia de `Combination` (Value Object sin identidad), `Sorteo`
SÍ tiene identidad propia (id, numero_sorteo) y representa un hecho
histórico ya ocurrido y persistido -no una combinación candidata.
Contiene la `Combination` resultante más los metadatos propios de un
sorteo real (fecha, fuente, día de la semana).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.domain.value_objects.combination import Combination


@dataclass
class Sorteo:
    id: UUID | None
    juego_id: UUID
    numero_sorteo: int
    fecha: date
    dia_semana: str
    resultado: Combination
    fuente: str | None = None
    creado_en: datetime | None = None

    def __post_init__(self) -> None:
        dias_validos = {
            "lunes", "martes", "miercoles", "jueves",
            "viernes", "sabado", "domingo",
        }
        if self.dia_semana.lower() not in dias_validos:
            raise ValueError(f"Día de la semana inválido: {self.dia_semana}")
