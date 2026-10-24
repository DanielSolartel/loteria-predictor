"""Repositorio de la tabla `simulaciones` (Fase 7), sin cambio de esquema.

La clave de identidad vive en `parametros ->> 'clave'`. No hay indice unico:
anadirlo exigiria migrar la base real compartida y cambiaria la revision
Alembic que exigen los scripts de AE-49/51 y de auditoria. La unicidad la
garantiza la publicacion: en PostgreSQL toma `pg_advisory_xact_lock` sobre
un recurso PROPIO de la clave (espacio `loteria:simulaciones:`, distinto del
de datos por juego de la Fase 6), con `lock_timeout` acotado, y busca e
inserta dentro de la misma transaccion. El recurso se libera al confirmar o
deshacer. SQLite solo se usa en fixtures aisladas: no acredita esta
exclusion.
"""
from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.application.interfaces.simulaciones_repository import PublicacionConcurrenteError, SimulacionesRepository
from app.domain.entities.analitica import Simulacion
from app.infrastructure.db.models import SimulacionORM

ESPERA_MAXIMA_DEL_RECURSO = "10s"
_CON_CLAVE = text("simulaciones.parametros ->> 'clave' IS NOT NULL")


def recurso_de_clave(clave: str) -> int:
    valor = hashlib.sha256(("loteria:simulaciones:" + clave).encode("ascii")).digest()[:8]
    return int.from_bytes(valor, "big", signed=True)


def _entidad(fila: SimulacionORM) -> Simulacion:
    return Simulacion(id=fila.id, juego_id=fila.juego_id, num_iteraciones=fila.num_iteraciones,
                      parametros=fila.parametros, resultado_resumen=fila.resultado_resumen,
                      ejecutado_en=fila.ejecutado_en, duracion_ms=fila.duracion_ms)


class SimulacionesRepositorySQLAlchemy(SimulacionesRepository):
    def __init__(self, session: Session):
        self._session = session

    def por_clave(self, juego_id: UUID, clave: str) -> list[Simulacion]:
        consulta = (select(SimulacionORM).where(SimulacionORM.juego_id == juego_id)
                    .where(text("simulaciones.parametros ->> 'clave' = :clave").bindparams(clave=clave))
                    .order_by(SimulacionORM.ejecutado_en, SimulacionORM.id))
        return [_entidad(f) for f in self._session.scalars(consulta)]

    def obtener(self, identificador: UUID) -> Simulacion | None:
        fila = self._session.get(SimulacionORM, identificador)
        return None if fila is None else _entidad(fila)

    def listar(self, juego_id: UUID | None = None, limite: int = 50) -> list[Simulacion]:
        consulta = select(SimulacionORM).where(_CON_CLAVE)
        if juego_id is not None:
            consulta = consulta.where(SimulacionORM.juego_id == juego_id)
        consulta = consulta.order_by(SimulacionORM.ejecutado_en.desc(), SimulacionORM.id).limit(limite)
        return [_entidad(f) for f in self._session.scalars(consulta)]

    def _tomar_recurso(self, clave: str) -> None:
        dialecto = self._session.get_bind().dialect.name
        if dialecto == "sqlite":
            return  # solo fixtures; no se presenta como exclusion PostgreSQL
        if dialecto != "postgresql":
            raise RuntimeError("La publicacion de simulaciones requiere PostgreSQL")
        self._session.execute(text(f"SET LOCAL lock_timeout = '{ESPERA_MAXIMA_DEL_RECURSO}'"))
        try:
            self._session.execute(text("SELECT pg_advisory_xact_lock(:recurso)"), {"recurso": recurso_de_clave(clave)})
        except OperationalError as error:
            raise PublicacionConcurrenteError(
                f"Otra publicacion de la misma simulacion no termino en {ESPERA_MAXIMA_DEL_RECURSO}") from error

    def publicar(self, simulacion: Simulacion, clave: str) -> tuple[Simulacion, bool]:
        if simulacion.parametros.get("clave") != clave:
            raise ValueError("la clave no corresponde a los parametros")
        self._tomar_recurso(clave)
        existentes = self.por_clave(simulacion.juego_id, clave)
        if existentes:
            return existentes[0], False
        fila = SimulacionORM(juego_id=simulacion.juego_id, num_iteraciones=simulacion.num_iteraciones,
                             parametros=simulacion.parametros, resultado_resumen=simulacion.resultado_resumen,
                             duracion_ms=simulacion.duracion_ms)
        self._session.add(fila)
        self._session.flush()
        self._session.refresh(fila)
        return _entidad(fila), True
