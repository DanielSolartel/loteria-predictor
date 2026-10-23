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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.application.exceptions import SorteoDuplicadoError, SorteoNoEncontradoError
from app.application.interfaces.sorteo_repository import FiltroSorteos, SorteoRepository
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
from app.infrastructure.operacion_advisory import proteger_escritura


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
        proteger_escritura(self._session, sorteo.juego_id)
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
        try:
            self._session.flush()
        except IntegrityError as e:
            self._session.rollback()
            raise SorteoDuplicadoError(str(sorteo.juego_id), sorteo.numero_sorteo) from e
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

    def listar_por_juego(self, juego_id: UUID, filtro: FiltroSorteos) -> list[Sorteo]:
        columna_orden = SorteoORM.fecha if filtro.orden_campo == "fecha" else SorteoORM.numero_sorteo
        direccion = columna_orden.desc() if filtro.orden_direccion == "desc" else columna_orden.asc()
        # Desempate estable por numero_sorteo: varios sorteos pueden
        # compartir fecha (p.ej. Baloto y Revancha el mismo día en
        # otra tabla, o simplemente para que el orden sea
        # determinista al paginar -sin esto, dos páginas consecutivas
        # podrían repetir o saltarse filas si hay empates).
        desempate = SorteoORM.numero_sorteo.desc() if filtro.orden_direccion == "desc" else SorteoORM.numero_sorteo.asc()

        stmt = (
            select(SorteoORM)
            .where(*self._condiciones_filtro(juego_id, filtro))
            .options(
                selectinload(SorteoORM.numeros),
                selectinload(SorteoORM.superbalota),
                selectinload(SorteoORM.colores_numeros).selectinload(SorteoColorNumeroORM.color),
            )
            .order_by(direccion, desempate)
            .limit(filtro.limite)
            .offset(filtro.offset)
        )
        orms = self._session.scalars(stmt)
        return [_to_entity(o) for o in orms]

    def contar_por_juego(self, juego_id: UUID, filtro: FiltroSorteos | None = None) -> int:
        condiciones = self._condiciones_filtro(juego_id, filtro) if filtro else [SorteoORM.juego_id == juego_id]
        return self._session.scalar(
            select(func.count()).select_from(SorteoORM).where(*condiciones)
        )

    @staticmethod
    def _condiciones_filtro(juego_id: UUID, filtro: FiltroSorteos) -> list:
        """Condiciones WHERE compartidas entre listar_por_juego y
        contar_por_juego -mantenerlas en un solo lugar evita que el
        conteo y el listado paginado puedan quedar desincronizados
        si se agrega un filtro nuevo en el futuro."""
        condiciones = [SorteoORM.juego_id == juego_id]
        if filtro.desde:
            condiciones.append(SorteoORM.fecha >= filtro.desde)
        if filtro.hasta:
            condiciones.append(SorteoORM.fecha <= filtro.hasta)
        if filtro.numero_desde is not None:
            condiciones.append(SorteoORM.numero_sorteo >= filtro.numero_desde)
        if filtro.numero_hasta is not None:
            condiciones.append(SorteoORM.numero_sorteo <= filtro.numero_hasta)
        return condiciones

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

    def obtener_por_numero(self, juego_id: UUID, numero_sorteo: int) -> Sorteo | None:
        orm = self._session.scalar(
            select(SorteoORM)
            .where(SorteoORM.juego_id == juego_id, SorteoORM.numero_sorteo == numero_sorteo)
            .options(
                selectinload(SorteoORM.numeros),
                selectinload(SorteoORM.superbalota),
                selectinload(SorteoORM.colores_numeros).selectinload(SorteoColorNumeroORM.color),
            )
        )
        return _to_entity(orm) if orm else None

    def listar_numeros_sorteo(self, juego_id: UUID) -> list[int]:
        return list(
            self._session.scalars(
                select(SorteoORM.numero_sorteo).where(SorteoORM.juego_id == juego_id)
            )
        )

    def actualizar(self, sorteo: Sorteo) -> Sorteo:
        proteger_escritura(self._session, sorteo.juego_id)
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
        orm.colores_numeros.clear()
        # DELETE debe preceder a INSERT: las posiciones son únicas dentro
        # del sorteo. Todo permanece en la misma transacción, sin commit;
        # un resultado nuevo inválido sigue restituyendo el anterior.
        self._session.flush()
        for posicion, numero in enumerate(sorteo.resultado.numeros, start=1):
            orm.numeros.append(SorteoNumeroORM(numero=numero, posicion=posicion))

        if sorteo.resultado.superbalota is not None:
            if orm.superbalota:
                orm.superbalota.numero = sorteo.resultado.superbalota
            else:
                orm.superbalota = SorteoSuperbalotaORM(numero=sorteo.resultado.superbalota)
        elif orm.superbalota:
            self._session.delete(orm.superbalota)

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

        orm = self._session.get(SorteoORM, sorteo_id)
        if orm is None:
            raise SorteoNoEncontradoError(str(sorteo_id))
        proteger_escritura(self._session, orm.juego_id)
        self._session.delete(orm)
        self._session.flush()
