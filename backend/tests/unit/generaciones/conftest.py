"""Fixtures de E10.4 sobre un PostgreSQL DE PRUEBAS (`E104_PG_SUPERUSUARIO_URL`, p. ej. el servicio de CI).

Sin esa variable, las pruebas que lo necesitan se omiten (las demas corren igual). Con ella:
- `plantilla` (una vez por sesion): base `prueba_e104_plantilla` migrada y poblada con los productores REALES
  (`tests.e102_preparar_publicacion`: cuatro juegos y tres procedencias) mas una prediccion de BALOTO con
  `objetivo = corte + 1` y su explicacion (C7);
- `fuente` (por prueba): copia de esa base (`CREATE DATABASE ... TEMPLATE`) y de sus almacenes, para que cada
  escenario pueda escribir sin afectar a los demas.
Nunca se usa una base que no se llame `prueba_e104_*`; todas se borran al terminar.
"""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
URL = os.environ.get("E104_PG_SUPERUSUARIO_URL", "")
requiere_pg = pytest.mark.skipif(not URL, reason="sin E104_PG_SUPERUSUARIO_URL (PostgreSQL de pruebas)")
ALMACENES = {"pronosticos": "f4/pronosticos", "laboratorio": "f4/laboratorio", "carteras": "f4/carteras",
             "predicciones": "f4/predicciones", "operacion": "f4/operacion-producto3"}


def url_de(base: str, driver: bool = False) -> str:
    from sqlalchemy.engine import make_url

    u = make_url(URL).set(database=base)
    if driver:
        u = u.set(drivername="postgresql+psycopg")
    return u.render_as_string(hide_password=False)


def admin():
    from app.infrastructure.generaciones import base_logica as bl
    return bl.conectar(url_de("postgres"), autocommit=True)


def borrar_base(nombre: str) -> None:
    assert nombre.startswith(("prueba_e104_", "prep_", "pub_", "rest_"))
    with admin() as c:
        c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (nombre,))
        c.execute(f'DROP DATABASE IF EXISTS "{nombre}"')


def _entorno(base: str, almacenes: dict | None = None) -> dict:
    e = {k: v for k, v in os.environ.items() if not k.startswith(("DATABASE_URL", "DIRECTORIO_"))}
    e["DATABASE_URL"] = url_de(base, driver=True)
    from app.infrastructure.generaciones.inventario import POR_NOMBRE
    for nombre, ruta in (almacenes or {}).items():
        e[POR_NOMBRE[nombre].ajuste.upper()] = str(ruta)
    return e


@pytest.fixture(scope="session")
def plantilla(tmp_path_factory):
    if not URL:
        pytest.skip("sin PostgreSQL de pruebas")
    base = "prueba_e104_plantilla"
    borrar_base(base)
    with admin() as c:
        c.execute(f'CREATE DATABASE "{base}" TEMPLATE template0 ENCODING \'UTF8\'')
    raiz = tmp_path_factory.mktemp("e104-plantilla")
    r = subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=_entorno(base),
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    r = subprocess.run([sys.executable, "-B", "-m", "tests.e102_preparar_publicacion", "--salida", str(raiz / "f")],
                       cwd=BACKEND, env=_entorno(base), capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, r.stderr[-800:]
    trabajo = next((raiz / "f").glob("e102-trabajo-*"))
    almacenes = {n: trabajo / "generacion" / r_ for n, r_ in ALMACENES.items()}
    for n in ("resultados", "automatizacion", "simulaciones"):
        almacenes[n] = trabajo / "sin_publicar" / n
    r = subprocess.run([sys.executable, "-B", "-m", "scripts.predicciones", "generar", "--juego", "BALOTO"],
                       cwd=BACKEND, env=_entorno(base, almacenes), capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-800:]
    from app.infrastructure.generaciones import firma
    firma.generar(raiz / "firma.pem", raiz / "firma.pub")
    yield {"base": base, "trabajo": trabajo, "almacenes": almacenes, "firma": raiz / "firma.pem",
           "publica": raiz / "firma.pub"}
    borrar_base(base)


@pytest.fixture
def fuente(plantilla, tmp_path):
    from app.infrastructure.generaciones.captura import Fuente

    base = f"prueba_e104_{secrets.token_hex(6)}"
    with admin() as c:
        c.execute(f'CREATE DATABASE "{base}" TEMPLATE "{plantilla["base"]}"')
    copia = tmp_path / "fuente"
    shutil.copytree(plantilla["trabajo"], copia, symlinks=True)
    almacenes = {n: copia / Path(r).relative_to(plantilla["trabajo"]) for n, r in plantilla["almacenes"].items()}
    yield {"fuente": Fuente(url_de(base), almacenes), "base": base, "url": url_de(base), "almacenes": almacenes,
           "firma": plantilla["firma"], "publica": plantilla["publica"], "entorno": _entorno(base, almacenes)}
    borrar_base(base)
