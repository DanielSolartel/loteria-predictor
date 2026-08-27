from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.interfaces.sincronizacion_repository import SincronizacionRepository
from app.domain.entities.sincronizacion import EjecucionSincronizacion
from app.infrastructure.db.models import SincronizacionORM


def _to_entity(orm: SincronizacionORM) -> EjecucionSincronizacion:
    return EjecucionSincronizacion(
        id=orm.id, juego_id=orm.juego_id, conector=orm.conector,
        iniciado_en=orm.iniciado_en, finalizado_en=orm.finalizado_en, estado=orm.estado,
        sorteos_nuevos=orm.sorteos_nuevos, sorteos_fallidos=orm.sorteos_fallidos,
        sorteos_duplicados=orm.sorteos_duplicados, sorteos_incompletos=orm.sorteos_incompletos,
        total_sorteos_encontrados=orm.total_sorteos_encontrados,
        duracion_ms=orm.duracion_ms, ultimo_sorteo_importado=orm.ultimo_sorteo_importado,
        detalle_errores=list(orm.detalle_errores or []),
    )


class SincronizacionRepositorySQLAlchemy(SincronizacionRepository):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, ejecucion: EjecucionSincronizacion) -> EjecucionSincronizacion:
        if ejecucion.id is not None:
            orm = self._session.get(SincronizacionORM, ejecucion.id)
        else:
            orm = None

        if orm is None:
            orm = SincronizacionORM(juego_id=ejecucion.juego_id)
            self._session.add(orm)

        orm.conector = ejecucion.conector
        orm.iniciado_en = ejecucion.iniciado_en
        orm.finalizado_en = ejecucion.finalizado_en
        orm.estado = ejecucion.estado
        orm.sorteos_nuevos = ejecucion.sorteos_nuevos
        orm.sorteos_fallidos = ejecucion.sorteos_fallidos
        orm.sorteos_duplicados = ejecucion.sorteos_duplicados
        orm.sorteos_incompletos = ejecucion.sorteos_incompletos
        orm.total_sorteos_encontrados = ejecucion.total_sorteos_encontrados
        orm.duracion_ms = ejecucion.duracion_ms
        orm.ultimo_sorteo_importado = ejecucion.ultimo_sorteo_importado
        orm.detalle_errores = ejecucion.detalle_errores

        self._session.flush()
        return _to_entity(orm)

    def obtener_ultima(self, juego_id: UUID) -> EjecucionSincronizacion | None:
        orm = self._session.scalar(
            select(SincronizacionORM)
            .where(SincronizacionORM.juego_id == juego_id)
            .order_by(SincronizacionORM.iniciado_en.desc())
            .limit(1)
        )
        return _to_entity(orm) if orm else None

    def listar_recientes(self, juego_id: UUID, limite: int = 20) -> list[EjecucionSincronizacion]:
        orms = self._session.scalars(
            select(SincronizacionORM)
            .where(SincronizacionORM.juego_id == juego_id)
            .order_by(SincronizacionORM.iniciado_en.desc())
            .limit(limite)
        )
        return [_to_entity(o) for o in orms]
