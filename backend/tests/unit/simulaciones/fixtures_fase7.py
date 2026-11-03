"""FIXTURES SINTETICAS de la Fase 7, solo para pruebas.

Una base SQLite AISLADA por prueba (en `tmp_path`) con el esquema de los
modelos ORM de produccion (adaptado solo en el DDL, como el fixture de la
Fase 6), los cuatro juegos, la paleta y historicos sinteticos generados con
`random.Random`. Nunca se conecta a PostgreSQL ni a Internet; ningun dato es
real. SQLite no acredita el advisory de PostgreSQL: esa exclusion se
comprueba con `tests/postgres_fase7.py` sobre un PostgreSQL de pruebas."""
from __future__ import annotations

import dataclasses
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, MetaData, Uuid, create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.application.use_cases.simulaciones import (
    EjecutorSimulacionesEnEsteProceso,
    LecturaSimulaciones,
    SimulacionesFase7,
)
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import ColorORM, JuegoORM
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
    ResultadosHistoricosRepositorySQLAlchemy,
)
from app.infrastructure.repositories.simulaciones_repository_sqlalchemy import SimulacionesRepositorySQLAlchemy
from app.infrastructure.repositories.sorteo_repository_sqlalchemy import SorteoRepositorySQLAlchemy
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from tests.unit import fixtures_producto1 as fx

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
TAMANOS = {"BALOTO": 60, "BALOTO_REVANCHA": 50, "MILOTO": 40, "COLORLOTO": 45}
LOCAL = ("127.0.0.1", 50000)


def historicos(tamanos: dict | None = None) -> dict:
    t = {**TAMANOS, **(tamanos or {})}
    return {"BALOTO": fx.historico_numerico("BALOTO", t["BALOTO"]),
            "BALOTO_REVANCHA": fx.historico_numerico("BALOTO_REVANCHA", t["BALOTO_REVANCHA"]),
            "MILOTO": fx.historico_numerico("MILOTO", t["MILOTO"], primero=530),
            "COLORLOTO": fx.historico_colorloto(t["COLORLOTO"])}


def metadatos_sqlite() -> MetaData:
    """Adapta solo el DDL del fixture; conserva el mapeo ORM de produccion."""
    meta = MetaData()
    for tabla in Base.metadata.sorted_tables:
        tabla.to_metadata(meta)
    for tabla in meta.tables.values():
        for columna in tabla.columns:
            if isinstance(columna.type, JSONB):
                columna.type = JSON()
            elif isinstance(columna.type, PGUUID):
                columna.type = Uuid(native_uuid=False)
    return meta


def guardar_sorteos(session: Session, codigo: str, resultados) -> None:
    entidad = JuegoRepositorySQLAlchemy(session).obtener_por_codigo(codigo)
    repo = SorteoRepositorySQLAlchemy(session)
    for r in resultados:
        if codigo == "COLORLOTO":
            comb = Combination(pares=tuple(ColorNumberPair(n, Color(c, c.title())) for n, c in r.pares))
        else:
            comb = Combination(numeros=r.numeros, superbalota=r.superbalota)
        repo.guardar(Sorteo(None, entidad.id, r.numero_sorteo, r.fecha, r.dia_semana, comb, "fixture_sintetica",
                            datetime(2026, 1, 1, tzinfo=timezone.utc)))


class Reloj:
    def __init__(self, instante=datetime(2026, 10, 23, 12, tzinfo=timezone.utc)):
        self.instante = instante

    def __call__(self):
        return self.instante


@dataclasses.dataclass
class Entorno:
    raiz: Path
    engine: object
    sesiones: sessionmaker
    historicos: dict

    def abrir_lectura(self):
        @contextmanager
        def abrir():
            session = self.sesiones()
            try:
                yield LecturaSimulaciones(JuegoRepositorySQLAlchemy(session),
                                          ResultadosHistoricosRepositorySQLAlchemy(session),
                                          SimulacionesRepositorySQLAlchemy(session))
                session.rollback()
            except BaseException:
                session.rollback()
                raise
            finally:
                session.close()
        return abrir

    def abrir_publicacion(self):
        @contextmanager
        def abrir():
            session = self.sesiones()
            try:
                yield LecturaSimulaciones(JuegoRepositorySQLAlchemy(session),
                                          ResultadosHistoricosRepositorySQLAlchemy(session),
                                          SimulacionesRepositorySQLAlchemy(session))
                session.commit()
            except BaseException:
                session.rollback()
                raise
            finally:
                session.close()
        return abrir

    @property
    def operacion(self) -> Path:
        return self.raiz / "simulaciones" / "operacion"

    def servicio(self, ejecutor=None, *, abrir_lectura=None, abrir_publicacion=None, reloj=None, **extra):
        return SimulacionesFase7(RegistroEjecucionesArchivo(self.operacion), CerrojoPorJuego(self.operacion),
                                 abrir_lectura or self.abrir_lectura(), abrir_publicacion or self.abrir_publicacion(),
                                 ejecutor=ejecutor or EjecutorSimulacionesEnEsteProceso(), reloj=reloj or Reloj(),
                                 **extra)

    def agregar(self, codigo: str, resultados) -> None:
        with self.sesiones() as session:
            guardar_sorteos(session, codigo, resultados)
            session.commit()

    def filas(self) -> list[dict]:
        from app.infrastructure.db.models import SimulacionORM

        with self.sesiones() as session:
            return [{"id": f.id, "juego_id": f.juego_id, "num_iteraciones": f.num_iteraciones,
                     "parametros": f.parametros, "resultado_resumen": f.resultado_resumen}
                    for f in session.query(SimulacionORM).order_by(SimulacionORM.ejecutado_en, SimulacionORM.id)]


def entorno(raiz: Path, tamanos: dict | None = None, *, cargar: tuple[str, ...] = JUEGOS) -> Entorno:
    raiz.mkdir(parents=True, exist_ok=True)
    engine = create_engine("sqlite+pysqlite:///" + str(raiz / "f7.sqlite"), poolclass=NullPool)
    metadatos_sqlite().create_all(engine)
    sesiones = sessionmaker(bind=engine, autoflush=False, future=True)
    datos = historicos(tamanos)
    with sesiones() as session:
        for j in JUEGOS:
            session.add(JuegoORM(**asdict(fx.juego(j))))
        session.flush()
        jcolor = JuegoRepositorySQLAlchemy(session).obtener_por_codigo("COLORLOTO")
        for color in fx.COLORES:
            session.add(ColorORM(juego_id=jcolor.id, codigo=color, nombre=color.title(), activo=True))
        session.flush()
        for j in cargar:
            guardar_sorteos(session, j, datos[j])
        session.commit()
    return Entorno(raiz, engine, sesiones, datos)


def lanzar_ya(funcion, inicio):
    funcion(inicio)


def cliente(e: Entorno, servicio=None, *, client=LOCAL, lanzador=lanzar_ya, conectada: bool = True):
    """TestClient de la aplicacion real con el caso de uso sintetico."""
    from tests import consola_sesion

    from app.api import dependencies as dep
    from app.infrastructure.db.session import get_db
    from app.main import app

    s = servicio or e.servicio()
    app.dependency_overrides = {get_db: lambda: fx._SesionFalsa(conectada), dep.get_simulaciones: lambda: s,
                                dep.get_lanzador_de_simulaciones: lambda: lanzador}
    return consola_sesion.cliente_de_consola(app, client=client)  # E10.1: sesión legítima explícita


def limpiar():
    from app.main import app

    app.dependency_overrides = {}


def token(c) -> str:
    return c.get("/simulaciones").text.split('name="token_local" value="', 1)[1].split('"', 1)[0]
