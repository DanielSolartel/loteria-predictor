"""
Implementación concreta de ResultadosHistoricosRepository.

Mismo patrón que `SorteoRepositorySQLAlchemy`: recibe una `Session`
inyectada, usa `selectinload` para traer las relaciones (números,
superbalota, colores) en una sola consulta adicional en vez de N+1.
El filtrado por `hasta_numero_sorteo` se aplica en el propio `WHERE`
de la consulta -nunca se trae el histórico completo para filtrarlo
después en Python.

La transformación ORM->DTO en sí vive en `_mapeo_resultados_historicos.py`
(sin ninguna dependencia de SQLAlchemy) -ver ese archivo para la
justificación completa.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.infrastructure.db.models import SorteoColorNumeroORM, SorteoORM
from app.infrastructure.repositories._mapeo_resultados_historicos import (
    a_resultado_colorloto,
    a_resultado_numerico,
)


class ResultadosHistoricosRepositorySQLAlchemy(ResultadosHistoricosRepository):
    def __init__(self, session: Session):
        self._session = session

    def listar_resultados_numericos(
        self, juego_id: UUID, hasta_numero_sorteo: int | None = None,
    ) -> list[ResultadoNumerico]:
        stmt = (
            select(SorteoORM)
            .options(selectinload(SorteoORM.numeros), selectinload(SorteoORM.superbalota))
            .where(SorteoORM.juego_id == juego_id)
            .order_by(SorteoORM.numero_sorteo.asc())
        )
        if hasta_numero_sorteo is not None:
            stmt = stmt.where(SorteoORM.numero_sorteo <= hasta_numero_sorteo)

        return [a_resultado_numerico(orm) for orm in self._session.scalars(stmt).all()]

    def listar_resultados_colorloto(
        self, juego_id: UUID, hasta_numero_sorteo: int | None = None,
    ) -> list[ResultadoColorLoto]:
        stmt = (
            select(SorteoORM)
            .options(selectinload(SorteoORM.colores_numeros).selectinload(SorteoColorNumeroORM.color))
            .where(SorteoORM.juego_id == juego_id)
            .order_by(SorteoORM.numero_sorteo.asc())
        )
        if hasta_numero_sorteo is not None:
            stmt = stmt.where(SorteoORM.numero_sorteo <= hasta_numero_sorteo)

        return [a_resultado_colorloto(orm) for orm in self._session.scalars(stmt).all()]
