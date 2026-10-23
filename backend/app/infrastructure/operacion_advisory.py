"""Exclusion de datos por juego en PostgreSQL, compartida por auto y CRUD.

El ciclo toma un advisory de SESION en su conexion fijada. Cada escritura
ordinaria toma el mismo recurso a nivel de transaccion. El propietario de
la sesion puede volver a tomarlo al confirmar cada sorteo; otros escritores
reciben un error accionable, sin una espera no acotada. SQLite solo se usa
en fixtures aisladas y no acredita esta exclusion distribuida.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager

from sqlalchemy import text

from app.application.exceptions import OperacionConcurrenteError


def clave_de_juego(juego_id) -> int:
    valor = hashlib.sha256(("loteria:datos:" + str(juego_id)).encode("ascii")).digest()[:8]
    return int.from_bytes(valor, "big", signed=True)


def _dialecto(conexion) -> str:
    return conexion.dialect.name


def proteger_escritura(session, juego_id) -> None:
    dialecto = session.get_bind().dialect.name
    if dialecto == "sqlite":
        return  # solo pruebas; no se presenta como exclusion PostgreSQL
    if dialecto != "postgresql":
        raise RuntimeError("El coordinador de datos requiere PostgreSQL")
    libre = session.execute(text("SELECT pg_try_advisory_xact_lock(:clave)"),
                            {"clave": clave_de_juego(juego_id)}).scalar_one()
    if not libre:
        raise OperacionConcurrenteError("Hay una operacion de datos activa para este juego; vuelva a intentar")


@contextmanager
def proteger_ciclo(conexion, juego_id):
    dialecto = _dialecto(conexion)
    if dialecto == "sqlite":
        yield {"alcance": "fixture_sqlite_sin_advisory"}
        return
    if dialecto != "postgresql":
        raise RuntimeError("El ejecutor de datos requiere PostgreSQL")
    clave = clave_de_juego(juego_id)
    libre = conexion.execute(text("SELECT pg_try_advisory_lock(:clave)"), {"clave": clave}).scalar_one()
    conexion.commit()  # el lock de sesion sobrevive a commits sorteo a sorteo
    if not libre:
        raise OperacionConcurrenteError("Otra instancia mantiene el ciclo de este juego")
    try:
        yield {"alcance": "postgresql_sesion", "recurso": "datos_del_juego"}
    finally:
        # Una transaccion fallida debe cerrarse antes de ejecutar unlock.
        conexion.rollback()
        liberado = conexion.execute(text("SELECT pg_advisory_unlock(:clave)"), {"clave": clave}).scalar_one()
        conexion.commit()
        if not liberado:
            raise RuntimeError("No se pudo confirmar la liberacion del recurso de datos")
