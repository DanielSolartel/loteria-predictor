"""
Implementación concreta de EstadisticaRepository.

Sigue el mismo patrón que el resto de `infrastructure/repositories/`:
recibe una `Session` inyectada, no hace commit por su cuenta (el
commit ocurre en el límite del request, vía `get_db()`, mismo
criterio que `SorteoRepositorySQLAlchemy`) -salvo que sí llama
`flush()` donde se necesita que el estado quede visible dentro de la
misma transacción (tras `guardar`, y para que `rowcount` de
`invalidar_por_juego` sea confiable antes del commit externo).

`guardar()` es un UPSERT atómico de PostgreSQL (`INSERT ... ON
CONFLICT ... DO UPDATE`), no un INSERT incondicional -corrección
posterior a la Etapa R/invalidación: los dos índices únicos parciales
(`uq_estadisticas_con_corte`/`uq_estadisticas_sin_corte`) representan
UNA sola fila reutilizable por identidad
(juego_id, tipo_estadistica, hasta_numero_sorteo, parametros_hash),
incluso si esa fila está invalidada (`valido_hasta` no forma parte de
la identidad, solo de su vigencia). Recalcular una estadística
invalidada debe REEMPLAZAR esa fila (mismo id, resultado/calculado_en/
valido_hasta nuevos), nunca intentar crear una segunda fila -eso es
exactamente lo que producía `UniqueViolation`.

Se usan DOS conflict targets, uno por cada índice parcial (el
conflict target debe coincidir exactamente con las columnas Y el
predicado WHERE del índice, o PostgreSQL no puede asociarlo) -jamás
uno solo que intente cubrir ambos casos. Es un upsert genuinamente
atómico a nivel de base de datos: sin ventana de carrera entre
"buscar" y "escribir", a diferencia de un patrón buscar-y-actualizar
manual (dos requests concurrentes que intentan crear la MISMA
identidad por primera vez nunca chocan; el segundo INSERT
automáticamente se resuelve como UPDATE del mismo conflicto)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.application.interfaces.estadistica_repository import (
    EstadisticaCalculada,
    EstadisticaRepository,
    calcular_parametros_hash,
)
from app.infrastructure.db.models import EstadisticaORM


def _a_entidad(orm: EstadisticaORM) -> EstadisticaCalculada:
    return EstadisticaCalculada(
        id=orm.id,
        juego_id=orm.juego_id,
        tipo_estadistica=orm.tipo_estadistica,
        hasta_numero_sorteo=orm.hasta_numero_sorteo,
        parametros=orm.parametros,
        parametros_hash=orm.parametros_hash,
        resultado=orm.resultado,
        calculado_en=orm.calculado_en,
        valido_hasta=orm.valido_hasta,
    )


class EstadisticaRepositorySQLAlchemy(EstadisticaRepository):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, entrada: EstadisticaCalculada) -> EstadisticaCalculada:
        hash_calculado = calcular_parametros_hash(entrada.parametros)

        valores = dict(
            juego_id=entrada.juego_id,
            tipo_estadistica=entrada.tipo_estadistica,
            hasta_numero_sorteo=entrada.hasta_numero_sorteo,
            parametros=entrada.parametros,
            parametros_hash=hash_calculado,
            resultado=entrada.resultado,
            valido_hasta=entrada.valido_hasta,
        )

        stmt = pg_insert(EstadisticaORM).values(**valores)

        # calculado_en tiene server_default=func.now(), que SOLO se
        # aplica en INSERT -en la rama DO UPDATE hay que fijarlo
        # explícitamente para que el recálculo quede reflejado
        # (requisito: "calculado_en refleja el recálculo").
        campos_a_actualizar = {
            "parametros": stmt.excluded.parametros,
            "parametros_hash": stmt.excluded.parametros_hash,
            "resultado": stmt.excluded.resultado,
            "calculado_en": func.now(),
            "valido_hasta": stmt.excluded.valido_hasta,
        }

        if entrada.hasta_numero_sorteo is None:
            # Conflict target = exactamente las columnas + predicado
            # de uq_estadisticas_sin_corte -si no coincide con el
            # índice parcial exacto, PostgreSQL no puede asociarlo y
            # falla en tiempo de ejecución, no silenciosamente.
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    EstadisticaORM.juego_id, EstadisticaORM.tipo_estadistica, EstadisticaORM.parametros_hash,
                ],
                index_where=EstadisticaORM.hasta_numero_sorteo.is_(None),
                set_=campos_a_actualizar,
            )
        else:
            # Conflict target = exactamente uq_estadisticas_con_corte.
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    EstadisticaORM.juego_id, EstadisticaORM.tipo_estadistica,
                    EstadisticaORM.hasta_numero_sorteo, EstadisticaORM.parametros_hash,
                ],
                index_where=EstadisticaORM.hasta_numero_sorteo.is_not(None),
                set_=campos_a_actualizar,
            )

        self._session.execute(stmt)
        self._session.flush()

        # Re-consulta por identidad -deliberadamente NO se usa
        # RETURNING sobre el propio INSERT (evita depender de la
        # sintaxis más nueva de "ORM-enabled INSERT...RETURNING", más
        # difícil de verificar sin una conexión real disponible). El
        # resultado es el mismo: la fila definitiva, ya sea insertada
        # o actualizada, con el MISMO id si fue un reemplazo.
        fila = self._session.scalars(
            select(EstadisticaORM).where(
                EstadisticaORM.juego_id == entrada.juego_id,
                EstadisticaORM.tipo_estadistica == entrada.tipo_estadistica,
                EstadisticaORM.hasta_numero_sorteo == entrada.hasta_numero_sorteo,
                EstadisticaORM.parametros_hash == hash_calculado,
            )
        ).one()
        return _a_entidad(fila)

    def buscar_vigente(
        self, juego_id: UUID, tipo_estadistica: str, hasta_numero_sorteo: int | None, parametros: dict,
    ) -> EstadisticaCalculada | None:
        hash_calculado = calcular_parametros_hash(parametros)
        ahora = datetime.now(timezone.utc)

        stmt = select(EstadisticaORM).where(
            EstadisticaORM.juego_id == juego_id,
            EstadisticaORM.tipo_estadistica == tipo_estadistica,
            EstadisticaORM.hasta_numero_sorteo == hasta_numero_sorteo,
            EstadisticaORM.parametros_hash == hash_calculado,
            or_(EstadisticaORM.valido_hasta.is_(None), EstadisticaORM.valido_hasta > ahora),
        )
        orm = self._session.scalars(stmt).first()
        return _a_entidad(orm) if orm is not None else None

    def invalidar_por_juego(self, juego_id: UUID, desde_numero_sorteo: int | None = None) -> int:
        ahora = datetime.now(timezone.utc)

        condicion_corte = EstadisticaORM.hasta_numero_sorteo.is_(None)
        if desde_numero_sorteo is not None:
            condicion_corte = or_(
                condicion_corte,
                EstadisticaORM.hasta_numero_sorteo >= desde_numero_sorteo,
            )

        stmt = (
            update(EstadisticaORM)
            .where(
                EstadisticaORM.juego_id == juego_id,
                condicion_corte,
                or_(EstadisticaORM.valido_hasta.is_(None), EstadisticaORM.valido_hasta > ahora),
            )
            .values(valido_hasta=ahora)
        )
        resultado = self._session.execute(stmt)
        self._session.flush()
        return resultado.rowcount

    def listar_por_juego_y_tipo(self, juego_id: UUID, tipo_estadistica: str) -> list[EstadisticaCalculada]:
        stmt = (
            select(EstadisticaORM)
            .where(EstadisticaORM.juego_id == juego_id, EstadisticaORM.tipo_estadistica == tipo_estadistica)
            .order_by(EstadisticaORM.calculado_en.desc())
        )
        return [_a_entidad(orm) for orm in self._session.scalars(stmt).all()]
