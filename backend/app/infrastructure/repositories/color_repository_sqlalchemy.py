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
        fecha_ref = en_fecha or date.today()
        stmt = select(ColorORM).where(
            ColorORM.juego_id == juego_id,
            ColorORM.activo.is_(True),
        )
        orms = self._session.scalars(stmt)
        colores = [_to_entity(o) for o in orms]
        return [c for c in colores if c.esta_vigente_en(fecha_ref)]

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
