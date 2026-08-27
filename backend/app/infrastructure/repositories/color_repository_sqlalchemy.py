from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.interfaces.color_repository import ColorRepository
from app.domain.value_objects.color import Color
from app.infrastructure.db.models import ColorORM


def _to_entity(orm: ColorORM) -> Color:
    return Color(
        codigo=orm.codigo,
        nombre=orm.nombre,
        activo=orm.activo,
        vigente_desde=orm.vigente_desde,
        vigente_hasta=orm.vigente_hasta,
    )


class ColorRepositorySQLAlchemy(ColorRepository):
    def __init__(self, session: Session):
        self._session = session

    def listar_vigentes(self, juego_id: UUID, en_fecha: date | None = None) -> list[Color]:
        if en_fecha is None:
            # Paleta ACTUAL: contrato exacto ya usado por GameFactory,
            # sin ningún cambio -filtra por activo=True en SQL (un
            # color inactivo NUNCA debe aparecer como parte de la
            # paleta de HOY), y por vigencia en memoria sobre ese
            # subconjunto ya reducido.
            stmt = select(ColorORM).where(
                ColorORM.juego_id == juego_id,
                ColorORM.activo.is_(True),
            ).order_by(ColorORM.codigo)
            colores = [_to_entity(o) for o in self._session.scalars(stmt)]
            return [c for c in colores if c.esta_vigente_en(date.today())]

        # Paleta HISTÓRICA en `en_fecha`: NUNCA filtra por `activo`
        # -ese flag es administrativo del presente, independiente de
        # la ventana temporal real de un color (`cerrar_vigencia`
        # nunca lo toca). Una sola consulta trae TODOS los colores
        # del juego (activos e inactivos), y la vigencia se resuelve
        # en memoria vía `Color.esta_vigente_en`, la misma función
        # pura ya usada arriba -sin duplicar la regla de negocio.
        return self._listar_por_vigencia_en(juego_id, en_fecha)

    def _listar_por_vigencia_en(self, juego_id: UUID, fecha_ref: date) -> list[Color]:
        colores = self.listar_todos(juego_id)
        return [c for c in colores if c.esta_vigente_en(fecha_ref)]

    def listar_todos(self, juego_id: UUID) -> list[Color]:
        stmt = select(ColorORM).where(ColorORM.juego_id == juego_id).order_by(ColorORM.codigo)
        return [_to_entity(o) for o in self._session.scalars(stmt)]

    def guardar(self, juego_id: UUID, color: Color) -> Color:
        orm = ColorORM(
            juego_id=juego_id,
            codigo=color.codigo,
            nombre=color.nombre,
            activo=color.activo,
            vigente_desde=color.vigente_desde,
            vigente_hasta=color.vigente_hasta,
        )
        self._session.add(orm)
        self._session.flush()
        return _to_entity(orm)

    def cerrar_vigencia(self, juego_id: UUID, codigo: str, hasta: date) -> None:
        orm = self._session.scalar(
            select(ColorORM).where(
                ColorORM.juego_id == juego_id,
                ColorORM.codigo == codigo,
                ColorORM.vigente_hasta.is_(None),
            )
        )
        if orm is None:
            raise ValueError(f"No hay un color vigente con código '{codigo}' para este juego")
        orm.vigente_hasta = hasta
        self._session.flush()
