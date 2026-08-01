from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.interfaces.juego_repository import JuegoRepository
from app.domain.entities.juego import Juego
from app.infrastructure.db.models import JuegoORM


def _to_entity(orm: JuegoORM) -> Juego:
    return Juego(
        id=orm.id,
        codigo=orm.codigo,
        nombre=orm.nombre,
        rango_min=orm.rango_min,
        rango_max=orm.rango_max,
        cantidad_numeros=orm.cantidad_numeros,
        tiene_superbalota=orm.tiene_superbalota,
        superbalota_min=orm.superbalota_min,
        superbalota_max=orm.superbalota_max,
        tiene_color=orm.tiene_color,
        permite_repeticion=orm.permite_repeticion,
        activo=orm.activo,
    )


class JuegoRepositorySQLAlchemy(JuegoRepository):
    def __init__(self, session: Session):
        self._session = session

    def obtener_por_codigo(self, codigo: str) -> Juego | None:
        orm = self._session.scalar(select(JuegoORM).where(JuegoORM.codigo == codigo))
        return _to_entity(orm) if orm else None

    def obtener_por_id(self, juego_id: UUID) -> Juego | None:
        orm = self._session.get(JuegoORM, juego_id)
        return _to_entity(orm) if orm else None

    def listar_activos(self) -> list[Juego]:
        orms = self._session.scalars(select(JuegoORM).where(JuegoORM.activo.is_(True)))
        return [_to_entity(o) for o in orms]

    def guardar(self, juego: Juego) -> Juego:
        if juego.id is not None:
            orm = self._session.get(JuegoORM, juego.id)
            if orm is None:
                raise ValueError(f"Juego con id {juego.id} no existe")
        else:
            orm = JuegoORM()
            self._session.add(orm)

        orm.codigo = juego.codigo
        orm.nombre = juego.nombre
        orm.rango_min = juego.rango_min
        orm.rango_max = juego.rango_max
        orm.cantidad_numeros = juego.cantidad_numeros
        orm.tiene_superbalota = juego.tiene_superbalota
        orm.superbalota_min = juego.superbalota_min
        orm.superbalota_max = juego.superbalota_max
        orm.tiene_color = juego.tiene_color
        orm.permite_repeticion = juego.permite_repeticion
        orm.activo = juego.activo

        self._session.flush()
        return _to_entity(orm)
