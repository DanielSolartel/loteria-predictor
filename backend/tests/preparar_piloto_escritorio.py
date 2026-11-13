"""Preparador de datos desechables, invocado por el lanzador en un proceso separado."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.domain.entities.sincronizacion import EjecucionSincronizacion
from app.infrastructure.db import session as db
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.sincronizacion_repository_sqlalchemy import SincronizacionRepositorySQLAlchemy
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
from scripts.piloto_escritorio import BASE_PRUEBA, PROPIETARIO
from tests import e102_preparar_publicacion as e102, fase94_api_sintetica as f94


def _carteras_pendientes(datos: dict) -> None:
    e4 = datos["e4"]
    baloto, segundo = "BALOTO", "markov_apariciones"
    registrado = f94.registrar(e4, baloto, modelo=segundo)
    e4.configurar(baloto, segundo, registrado=registrado.identificador)
    e4.centro().ahora(baloto)
    e4.configurar(baloto, f94.MODELOS[baloto], registrado=datos["modelos"][baloto][-1].identificador)
    datos["modelos"][baloto].append(registrado)
    for juego in e102.JUEGOS:
        e4.centro().ahora(juego)
        servicio = e4.carteras()
        datos["carteras"][juego] = [c for linea in servicio.lineas(juego)
                                   for c in servicio.carteras_de_linea(juego, linea)]
        objetivo = e4.cargados(juego)[-1].numero_sorteo + 1
        cantidad = sum(c.objetivo == objetivo for c in datos["carteras"][juego])
        if cantidad < (2 if juego == baloto else 1):
            raise RuntimeError("La referencia no tiene las carteras pendientes esperadas.")


def _guardar_estados(raiz: Path, fecha: datetime) -> None:
    almacen = AlmacenAutomatizacion(raiz / "automatizacion")
    with db.SessionLocal.begin() as sesion:
        juegos = JuegoRepositorySQLAlchemy(sesion)
        sincronizaciones = SincronizacionRepositorySQLAlchemy(sesion)
        for codigo, estado, novedades in (("BALOTO", "correcto", 1), ("BALOTO_REVANCHA", "sin_novedad", 0),
                                          ("MILOTO", "fallo_consulta", 0)):
            juego = juegos.obtener_por_codigo(codigo)
            intento = EjecucionSincronizacion(None, juego.id, "fixture_sintetica", fecha - timedelta(seconds=1),
                                               "fallido" if estado == "fallo_consulta" else "completado",
                                               finalizado_en=fecha, sorteos_nuevos=novedades)
            sincronizaciones.guardar(intento)
            almacen.guardar_estado(codigo, {"estado": estado, "ultima_comprobacion": fecha.isoformat()})


def main() -> None:
    raiz = Path.cwd()
    url = make_url(get_settings().database_url)
    if (url.drivername, url.host, url.database, url.username) != ("postgresql+psycopg", "127.0.0.1",
                                                                BASE_PRUEBA, PROPIETARIO):
        raise RuntimeError("Se requiere el PostgreSQL desechable del lanzador.")
    with db.SessionLocal() as sesion:
        directorio = sesion.execute(text("SHOW data_directory")).scalar_one()
        if Path(directorio).resolve() != raiz / "pg":
            raise RuntimeError("La base no pertenece a la instancia sintética.")

    backend = Path(__file__).resolve().parents[1]
    configuracion = Config(str(backend / "alembic.ini"))
    configuracion.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(configuracion, "head")
    destino = raiz / "referencia"
    if e102.main(["--salida", str(destino)], ampliar_escenario=_carteras_pendientes):
        raise RuntimeError("No se pudo preparar la referencia sintética.")
    fecha = datetime.now(timezone.utc)
    _guardar_estados(destino, fecha)
    (destino / "fecha-referencia.json").write_text(json.dumps(fecha.isoformat()) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
