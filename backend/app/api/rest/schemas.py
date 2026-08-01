from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class JuegoOut(BaseModel):
    id: UUID
    codigo: str
    nombre: str
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    tiene_superbalota: bool
    superbalota_min: int | None
    superbalota_max: int | None
    tiene_color: bool
    permite_repeticion: bool
    activo: bool


class JuegoConReglasOut(JuegoOut):
    espacio_muestral: int
    dimensiones: dict


class ColorNumberPairOut(BaseModel):
    numero: int
    color_codigo: str
    color_nombre: str


class SorteoOut(BaseModel):
    id: UUID
    juego_id: UUID
    numero_sorteo: int
    fecha: date
    dia_semana: str
    numeros: list[int]
    superbalota: int | None
    pares: list[ColorNumberPairOut]
    fuente: str | None


class SorteoListadoOut(BaseModel):
    sorteos: list[SorteoOut]
    total: int


class ColorNumberPairIn(BaseModel):
    numero: int
    color_codigo: str


class RegistrarSorteoIn(BaseModel):
    codigo_juego: str
    numero_sorteo: int = Field(gt=0)
    fecha: date
    numeros: list[int] = Field(default_factory=list)
    superbalota: int | None = None
    pares: list[ColorNumberPairIn] = Field(default_factory=list)
    fuente: str | None = None


class ColorOut(BaseModel):
    codigo: str
    nombre: str
    activo: bool
    vigente_desde: date | None
    vigente_hasta: date | None


class ErrorOut(BaseModel):
    detalle: str
    errores: list[str] = Field(default_factory=list)
