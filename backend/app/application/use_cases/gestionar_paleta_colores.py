"""
Caso de uso: GestionarPaletaColores.

Cumple directamente el requisito de que la arquitectura permita
modificar la paleta de ColorLoto si Coljuegos actualiza las reglas,
sin perder la validez de los sorteos históricos. Retirar un color no
lo borra: se cierra su vigencia (`vigente_hasta`), y los sorteos
pasados que lo usaron siguen siendo consultables y estadísticamente
correctos.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.application.interfaces.color_repository import ColorRepository
from app.domain.value_objects.color import Color


@dataclass
class AgregarColorInput:
    juego_id: UUID
    codigo: str
    nombre: str
    vigente_desde: date


@dataclass
class RetirarColorInput:
    juego_id: UUID
    codigo: str
    vigente_hasta: date


class GestionarPaletaColores:
    def __init__(self, color_repository: ColorRepository):
        self._colores = color_repository

    def agregar_color(self, datos: AgregarColorInput) -> Color:
        nuevo = Color(
            codigo=datos.codigo,
            nombre=datos.nombre,
            activo=True,
            vigente_desde=datos.vigente_desde,
            vigente_hasta=None,
        )
        return self._colores.guardar(datos.juego_id, nuevo)

    def retirar_color(self, datos: RetirarColorInput) -> None:
        self._colores.cerrar_vigencia(datos.juego_id, datos.codigo, datos.vigente_hasta)

    def listar_paleta_vigente(self, juego_id: UUID, en_fecha: date | None = None) -> list[Color]:
        return self._colores.listar_vigentes(juego_id, en_fecha)
