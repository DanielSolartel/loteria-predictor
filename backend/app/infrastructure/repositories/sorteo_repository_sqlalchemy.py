"""
Implementación concreta de SorteoRepository.

Este archivo concentra la traducción entre el modelo de dominio
(`Sorteo` + `Combination`, agnósticos a SQL) y las tablas
normalizadas del ER (`sorteos`, `sorteo_numeros`,
`sorteo_superbalota`, `sorteo_color_numero`). Es intencionalmente el
único lugar del sistema que conoce ambos mundos.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.application.interfaces.sorteo_repository import SorteoRepository
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination
from app.infrastructure.db.models import (
    ColorORM,
    SorteoColorNumeroORM,
    SorteoNumeroORM,
    SorteoORM,
    SorteoSuperbalotaORM,
)


def _to_entity(orm: SorteoORM) -> Sorteo:
    numeros = tuple(sn.numero for sn in sorted(orm.numeros, key=lambda x: x.posicion))
    superbalota = orm.superbalota.numero if orm.superbalota else None
    pares = tuple(
        ColorNumberPair(
            numero=scn.numero,
            color=Color(codigo=scn.color.codigo, nombre=scn.color.nombre, activo=scn.color.activo),
        )
        for scn in sorted(orm.colores_numeros, key=lambda x: x.posicion)
    )
    return Sorteo(
        id=orm.id,
        juego_id=orm.juego_id,
        numero_sorteo=orm.numero_sorteo,
        fecha=orm.fecha,
        dia_semana=orm.dia_semana,
        resultado=Combination(numeros=numeros, superbalota=superbalota, pares=pares),
        fuente=orm.fuente,
        creado_en=orm.creado_en,
    )


class SorteoRepositorySQLAlchemy(SorteoRepository):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, sorteo: Sorteo) -> Sorteo:
        orm = SorteoORM(
            juego_id=sorteo.juego_id,
            numero_sorteo=sorteo.numero_sorteo,
            fecha=sorteo.fecha,
            dia_semana=sorteo.dia_semana,
            fuente=sorteo.fuente,
        )

        for posicion, numero in enumerate(sorteo.resultado.numeros, start=1):
            orm.numeros.append(SorteoNumeroORM(numero=numero, posicion=posicion))

        if sorteo.resultado.superbalota is not None:
            orm.superbalota = SorteoSuperbalotaORM(numero=sorteo.resultado.superbalota)

        for posicion, par in enumerate(sorteo.resultado.pares, start=1):
            color_orm = self._session.scalar(
                select(ColorORM).where(
                    ColorORM.juego_id == sorteo.juego_id,
                    ColorORM.codigo == par.color.codigo,
                )
            )
            if color_orm is None:
                raise ValueError(f"Color '{par.color.codigo}' no existe para este juego")
            orm.colores_numeros.append(
                SorteoColorNumeroORM(color_id=color_orm.id, numero=par.numero, posicion=posicion)
            )

        self._session.add(orm)
        self._session.flush()
        return _to_entity(orm)

    def obtener_por_id(self, sorteo_id: UUID) -> Sorteo | None:
        orm = self._session.scalar(
            select(SorteoORM)
            .where(SorteoORM.id == sorteo_id)
            .options(
                selectinload(SorteoORM.numeros),
                selectinload(SorteoORM.superbalota),
                selectinload(SorteoORM.colores_numeros).selectinload(SorteoColorNumeroORM.color),
            )
        )
        return _to_entity(orm) if orm else None

    def existe(self, juego_id: UUID, numero_sorteo: int) -> bool:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(SorteoORM)
                .where(SorteoORM.juego_id == juego_id, SorteoORM.numero_sorteo == numero_sorteo)
            )
            > 0
        )

    def listar_por_juego(
        self,
        juego_id: UUID,
        desde: date | None = None,
        hasta: date | None = None,
        limite: int = 100,
        offset: int = 0,
    ) -> list[Sorteo]:
        stmt = (
            select(SorteoORM)
            .where(SorteoORM.juego_id == juego_id)
            .options(
                selectinload(SorteoORM.numeros),
                selectinload(SorteoORM.superbalota),
                selectinload(SorteoORM.colores_numeros).selectinload(SorteoColorNumeroORM.color),
            )
            .order_by(SorteoORM.fecha.desc())
            .limit(limite)
            .offset(offset)
        )
        if desde:
            stmt = stmt.where(SorteoORM.fecha >= desde)
        if hasta:
            stmt = stmt.where(SorteoORM.fecha <= hasta)

        orms = self._session.scalars(stmt)
        return [_to_entity(o) for o in orms]

    def contar_por_juego(self, juego_id: UUID) -> int:
        return self._session.scalar(
            select(func.count()).select_from(SorteoORM).where(SorteoORM.juego_id == juego_id)
        )

    def ultimo_sorteo(self, juego_id: UUID) -> Sorteo | None:
        orm = self._session.scalar(
            select(SorteoORM)
            .where(SorteoORM.juego_id == juego_id)
            .options(
                selectinload(SorteoORM.numeros),
                selectinload(SorteoORM.superbalota),
                selectinload(SorteoORM.colores_numeros).selectinload(SorteoColorNumeroORM.color),
            )
            .order_by(SorteoORM.numero_sorteo.desc())
            .limit(1)
        )
        return _to_entity(orm) if orm else None

    def actualizar(self, sorteo: Sorteo) -> Sorteo:
        from app.application.exceptions import SorteoNoEncontradoError

        orm = self._session.get(SorteoORM, sorteo.id)
        if orm is None:
            raise SorteoNoEncontradoError(str(sorteo.id))

        orm.fecha = sorteo.fecha
        orm.dia_semana = sorteo.dia_semana
        orm.fuente = sorteo.fuente

        # Reemplazo completo del resultado: se limpian las colecciones
        # hijas y se reconstruyen, en vez de intentar un diff
        # posición a posición -es más simple y el volumen por sorteo
        # es pequeño (5-6 elementos), así que el costo es despreciable.
        orm.numeros.clear()
        for posicion, numero in enumerate(sorteo.resultado.numeros, start=1):
            orm.numeros.append(SorteoNumeroORM(numero=numero, posicion=posicion))

        if sorteo.resultado.superbalota is not None:
            if orm.superbalota:
                orm.superbalota.numero = sorteo.resultado.superbalota
            else:
                orm.superbalota = SorteoSuperbalotaORM(numero=sorteo.resultado.superbalota)
        elif orm.superbalota:
            self._session.delete(orm.superbalota)

        orm.colores_numeros.clear()
        for posicion, par in enumerate(sorteo.resultado.pares, start=1):
            color_orm = self._session.scalar(
                select(ColorORM).where(
                    ColorORM.juego_id == orm.juego_id,
                    ColorORM.codigo == par.color.codigo,
                )
            )
            if color_orm is None:
                raise ValueError(f"Color '{par.color.codigo}' no existe para este juego")
            orm.colores_numeros.append(
                SorteoColorNumeroORM(color_id=color_orm.id, numero=par.numero, posicion=posicion)
            )

        self._session.flush()
        return _to_entity(orm)

    def eliminar(self, sorteo_id: UUID) -> None:
        from app.application.exceptions import SorteoNoEncontradoError

        orm = self._session.get(SorteoORM, sorteo_id)
        if orm is None:
            raise SorteoNoEncontradoError(str(sorteo_id))
        self._session.delete(orm)
        self._session.flush()
