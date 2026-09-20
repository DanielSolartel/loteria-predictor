"""
Implementacion concreta de DisponibilidadHoldoutRepository -Etapa
AE-40, validada.

Consulta agregada, de solo lectura, sobre `SorteoORM` UNICAMENTE
-nunca hace `join` ni `selectinload` de `SorteoNumeroORM`,
`SorteoSuperbalotaORM` ni `SorteoColorNumeroORM`, por lo que no
puede materializar numeros ganadores, superbalota ni colores aunque
quisiera. Proyecta exclusivamente `COUNT(*)`, `COUNT(DISTINCT
numero_sorteo)`, `MIN(numero_sorteo)` y `MAX(numero_sorteo)`; nunca
selecciona filas individuales, nunca escribe, nunca hace `INSERT`,
`UPDATE`, `DELETE`, `UPSERT`, `flush` ni `commit`. Reutiliza la
`Session` inyectada tal como `ResultadosHistoricosRepositorySQLAlchemy`,
compatible con `transaction_read_only=on`.

`construir_consulta_disponibilidad_holdout` es la UNICA
implementacion de esta consulta: tanto
`obtener_resumen_disponibilidad` como las pruebas de este modulo la
importan y compilan directamente -nunca se reconstruye una copia
paralela en las pruebas, para que estas fallen genuinamente si la
consulta de produccion cambia o queda defectuosa."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.application.interfaces.disponibilidad_holdout_repository import DisponibilidadHoldoutRepository
from app.application.ml.tipos import ResumenDisponibilidadHoldout
from app.infrastructure.db.models import SorteoORM


def construir_consulta_disponibilidad_holdout(juego_id: UUID, desde_numero_sorteo: int) -> Select:
    """Unica implementacion de produccion de la consulta agregada de
    disponibilidad -devuelve la sentencia SQLAlchemy sin ejecutarla,
    para que `obtener_resumen_disponibilidad` la ejecute contra la
    sesion real y las pruebas la compilen/inspeccionen directamente
    sin necesidad de PostgreSQL. Proyecta unicamente agregados sobre
    `SorteoORM.numero_sorteo`; nunca hace `join` con tablas de
    resultado."""
    return (
        select(
            func.count(SorteoORM.numero_sorteo),
            func.count(func.distinct(SorteoORM.numero_sorteo)),
            func.min(SorteoORM.numero_sorteo),
            func.max(SorteoORM.numero_sorteo),
        )
        .where(SorteoORM.juego_id == juego_id, SorteoORM.numero_sorteo >= desde_numero_sorteo)
    )


class DisponibilidadHoldoutRepositorySQLAlchemy(DisponibilidadHoldoutRepository):
    def __init__(self, session: Session):
        self._session = session

    def obtener_resumen_disponibilidad(
        self, juego_id: UUID, codigo_juego: str, desde_numero_sorteo: int,
    ) -> ResumenDisponibilidadHoldout:
        stmt = construir_consulta_disponibilidad_holdout(juego_id, desde_numero_sorteo)
        total_registros, total_distintos, minimo, maximo = self._session.execute(stmt).one()

        return ResumenDisponibilidadHoldout(
            juego_codigo=codigo_juego,
            desde_numero_sorteo=desde_numero_sorteo,
            total_registros=int(total_registros),
            total_numeros_distintos=int(total_distintos),
            numero_sorteo_minimo=int(minimo) if minimo is not None else None,
            numero_sorteo_maximo=int(maximo) if maximo is not None else None,
        )
