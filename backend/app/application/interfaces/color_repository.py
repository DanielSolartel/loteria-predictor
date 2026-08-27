from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.domain.value_objects.color import Color


class ColorRepository(ABC):
    @abstractmethod
    def listar_vigentes(self, juego_id: UUID, en_fecha: date | None = None) -> list[Color]:
        """Sin `en_fecha`: paleta ACTUAL -colores activos hoy, es la
        fuente de verdad que alimenta al constructor de
        `ColorLotoGame` (nunca cambia este contrato). Con `en_fecha`:
        paleta HISTÓRICAMENTE vigente en esa fecha -incluye un color
        hoy inactivo si su ventana `[vigente_desde, vigente_hasta]`
        (límites inclusivos, ver `Color.esta_vigente_en`) contiene
        `en_fecha`; el estado `activo` actual NUNCA determina este
        resultado cuando se pasa una fecha explícita, porque `activo`
        es un flag administrativo del presente, independiente de la
        ventana temporal real de un color (`cerrar_vigencia` nunca lo
        toca)."""

    @abstractmethod
    def listar_todos(self, juego_id: UUID) -> list[Color]:
        """Catálogo COMPLETO del juego -colores activos e inactivos,
        futuros, actuales y vencidos, sin ningún filtro de fecha ni
        de `activo`. Una sola consulta, sin N+1. Complementa a
        `listar_vigentes` (que sigue siendo la única fuente correcta
        para construir `ColorLotoGame` con la paleta de HOY) -nunca
        lo reemplaza. Pensado para que quien llama resuelva vigencia
        histórica en memoria contra `Color.esta_vigente_en(fecha)`
        para múltiples fechas sin repetir consultas."""

    @abstractmethod
    def guardar(self, juego_id: UUID, color: Color) -> Color:
        ...

    @abstractmethod
    def cerrar_vigencia(self, juego_id: UUID, codigo: str, hasta: date) -> None:
        """Cierra la vigencia de un color retirado sin borrar el
        histórico -los sorteos pasados que usaron ese color siguen
        siendo válidos y consultables."""
