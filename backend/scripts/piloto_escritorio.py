"""Inicia el visor con un clúster y una publicación sintéticos nuevos."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

from app.control_piloto import ControlVisor

BACKEND = Path(__file__).resolve().parents[1]
IP = "127.0.0.1"
BASE_PRUEBA = "escritorio_prueba"
PROPIETARIO = "escritorio_propietario"
LECTOR = "escritorio_lector"
_ALMACENES = {"PRONOSTICOS_EXPERIMENTALES": "pronosticos", "LABORATORIO_MODELOS": "laboratorio",
              "CARTERAS_MODELOS": "carteras", "PREDICCIONES_MODELOS": "predicciones", "RESULTADOS_MODELOS": "resultados"}
_PREFIJOS = ("PG", "PYTHON", "DATABASE_", "DIRECTORIO_", "BASE_", "API_PUBLICA_", "PASARELA_", "CONSOLE_",
             "CONSOLA_", "ARCHIVO_OPERACION_")


class PilotoError(RuntimeError):
    pass


def _entorno() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.upper().startswith(_PREFIJOS)}


def _socket_local() -> socket.socket:
    escucha = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        escucha.bind((IP, 0))
    except OSError:
        escucha.close()
        raise
    return escucha


def _url(puerto: int, usuario: str, clave: str) -> str:
    return URL.create("postgresql+psycopg", username=usuario, password=clave, host=IP, port=puerto,
                      database=BASE_PRUEBA, query={"connect_timeout": "3"}).render_as_string(hide_password=False)


def _ejecutar(orden: list[str | Path], raiz: Path, etapa: str, *, entorno: dict | None = None, limite: int = 60):
    try:
        with (raiz / "preparacion.log").open("ab") as log:
            subprocess.run(orden, cwd=raiz, env=entorno if entorno is not None else _entorno(), stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=limite)
    except (subprocess.SubprocessError, OSError) as error:
        raise PilotoError(f"Falló {etapa}. Revisa preparacion.log en la carpeta del ensayo.") from error


def _comprobar_publicacion(referencia: Path) -> None:
    publicacion = referencia / "publicacion"
    esperado = json.loads((referencia / "manifiesto-publicacion.json").read_text(encoding="utf-8"))["huellas"]
    actual = {}
    if publicacion.is_symlink() or publicacion.is_junction():
        raise PilotoError("La publicación sintética contiene un enlace.")
    for directorio, carpetas, archivos in os.walk(publicacion, followlinks=False):
        for nombre in (*carpetas, *archivos):
            ruta = Path(directorio) / nombre
            if ruta.is_symlink() or ruta.is_junction():
                raise PilotoError("La publicación sintética contiene un enlace.")
        for nombre in archivos:
            ruta = Path(directorio) / nombre
            with ruta.open("rb") as f:
                actual[ruta.relative_to(publicacion).as_posix()] = hashlib.file_digest(f, "sha256").hexdigest()
    if not actual or actual != esperado:
        raise PilotoError("Los archivos de la referencia no coinciden con el manifiesto.")


def _restaurar(binarios: Path, raiz: Path, semilla: Path, puerto: int, clave: str) -> None:
    restaurar = binarios / ("pg_restore.exe" if os.name == "nt" else "pg_restore")
    entorno = {**_entorno(), "PGHOST": IP, "PGPORT": str(puerto), "PGUSER": PROPIETARIO, "PGPASSWORD": clave,
               "PGCONNECT_TIMEOUT": "3", "PGSSLMODE": "disable"}
    _ejecutar([restaurar, "--dbname", BASE_PRUEBA, "--exit-on-error", "--single-transaction", "--no-owner",
              "--no-acl", semilla / "base.dump"], raiz, "la restauración sintética", entorno=entorno, limite=120)
    referencia = raiz / "referencia"
    referencia.mkdir()
    for nombre in ("publicacion", "automatizacion"):
        shutil.copytree(semilla / nombre, referencia / nombre, copy_function=shutil.copyfile)
    for nombre in ("manifiesto-publicacion.json", "esperado-consultas.json", "fecha-referencia.json"):
        shutil.copyfile(semilla / nombre, referencia / nombre)


@contextmanager
def referencia_sintetica(binarios: Path, raiz: Path, *, semilla: Path | None = None):
    """Solo crea recursos debajo de una raíz nueva y detiene el clúster que inició."""
    ext = ".exe" if os.name == "nt" else ""
    initdb, control = (binarios / (n + ext) for n in ("initdb", "pg_ctl"))
    if not initdb.is_file() or not control.is_file():
        raise PilotoError("Indica la carpeta bin de PostgreSQL con initdb y pg_ctl.")
    raiz.mkdir(mode=0o700, exist_ok=False)
    cluster = raiz / "pg"
    fichero_clave = raiz / "inicializacion.txt"
    propietario, lector = secrets.token_hex(24), secrets.token_hex(24)
    fichero_clave.write_text(propietario + "\n", encoding="ascii")
    try:
        _ejecutar([initdb, "-D", cluster, "-U", PROPIETARIO, "--auth=scram-sha-256", "--encoding=UTF8",
                   "--no-locale", "--pwfile", fichero_clave], raiz, "la inicialización de PostgreSQL")
    finally:
        fichero_clave.unlink(missing_ok=True)

    with _socket_local() as reserva:
        puerto = reserva.getsockname()[1]
    conexion = {"host": IP, "port": puerto, "user": PROPIETARIO, "password": propietario, "connect_timeout": 3,
                "sslmode": "disable", "options": "", "autocommit": True}
    opciones = f"-h {IP} -p {puerto} -c unix_socket_directories=''" if os.name != "nt" else f"-h {IP} -p {puerto}"
    try:
        _ejecutar([control, "-D", cluster, "-l", raiz / "postgres.log", "-o", opciones, "-w", "start"],
                  raiz, "el arranque de PostgreSQL")
        with psycopg.connect(dbname="postgres", **conexion) as s:
            directorio = s.execute("SHOW data_directory").fetchone()[0]
            if Path(directorio).resolve() != cluster:
                raise PilotoError("PostgreSQL no corresponde al clúster recién creado.")
            s.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(BASE_PRUEBA)))
            s.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(LECTOR), sql.Literal(lector)))

        if semilla is None:
            entorno = {**_entorno(), "PYTHONPATH": str(BACKEND), "PYTHONDONTWRITEBYTECODE": "1",
                       "DATABASE_URL": _url(puerto, PROPIETARIO, propietario)}
            _ejecutar([sys.executable, "-m", "tests.preparar_piloto_escritorio"], raiz, "la preparación de la referencia",
                      entorno=entorno, limite=600)
        else:
            _restaurar(binarios, raiz, semilla, puerto, propietario)
        referencia = raiz / "referencia"
        _comprobar_publicacion(referencia)
        with psycopg.connect(dbname=BASE_PRUEBA, **conexion) as s:
            s.execute("REVOKE CONNECT, TEMPORARY ON DATABASE escritorio_prueba FROM PUBLIC")
            s.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            s.execute("GRANT CONNECT ON DATABASE escritorio_prueba TO escritorio_lector")
            s.execute("GRANT USAGE ON SCHEMA public TO escritorio_lector")
            s.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO escritorio_lector")
            s.execute("ALTER ROLE escritorio_lector SET default_transaction_read_only = on")
        yield referencia, _url(puerto, LECTOR, lector)
    finally:
        if (cluster / "postmaster.pid").is_file():
            _ejecutar([control, "-D", cluster, "-m", "fast", "-w", "stop"], raiz, "el cierre de PostgreSQL")


def _servir(raiz: Path, referencia: Path, frontend: Path, base: str, *, control: ControlVisor | None = None,
            publicar: Callable[[], None] | None = None) -> None:
    entorno = _entorno()
    os.chdir(raiz)
    os.environ.clear()
    os.environ.update(entorno)
    os.environ.update(DATABASE_URL=base, BASE_TIEMPO_MAXIMO_CONSULTA_MS="5000",
                      BASE_TIEMPO_MAXIMO_INACTIVA_MS="5000", BASE_POOL_TAMANO="4", BASE_POOL_ESPERA_S="2")
    for variable, carpeta in _ALMACENES.items():
        os.environ[f"DIRECTORIO_{variable}"] = str(referencia / "publicacion" / carpeta)

    fecha = datetime.fromisoformat(json.loads((referencia / "fecha-referencia.json").read_text(encoding="utf-8")))
    servir_visor(frontend, referencia / "automatizacion", fecha, control=control, publicar=publicar,
                 apuestas=raiz / "apuestas.sqlite3")


def servir_visor(frontend: Path, automatizacion: Path, fecha: datetime | None, *,
                 datos: Literal["sinteticos", "fase6"] = "sinteticos", control: ControlVisor | None = None,
                 publicar: Callable[[], None] | None = None, apuestas: Path | None = None) -> None:
    import uvicorn

    from app.escritorio import crear_app

    arranque = secrets.token_urlsafe(32)
    control = control or ControlVisor()
    with _socket_local() as escucha:
        puerto = escucha.getsockname()[1]
        control.puerto = puerto

        def cerrar():
            servidor.should_exit = True

        app = crear_app(frontend=frontend, automatizacion=automatizacion, fecha_referencia=fecha,
                        puerto=puerto, arranque=arranque, control=control, cerrar=cerrar, datos=datos, apuestas=apuestas)
        servidor = uvicorn.Server(uvicorn.Config(app, host=IP, port=puerto, proxy_headers=False, access_log=False,
                                                 timeout_graceful_shutdown=8))
        apertura_fallida = threading.Event()

        def abrir():
            for _ in range(100):
                if servidor.should_exit:
                    return
                if servidor.started:
                    try:
                        if publicar is not None:
                            publicar()
                        if webbrowser.open(f"http://{IP}:{puerto}/#inicio={arranque}"):
                            return
                    except (OSError, webbrowser.Error):
                        pass
                    break
                time.sleep(0.05)
            apertura_fallida.set()
            servidor.should_exit = True

        threading.Thread(target=abrir, daemon=True).start()
        servidor.run(sockets=[escucha])
        if apertura_fallida.is_set() or not servidor.started:
            raise PilotoError("No se pudo abrir el piloto en el navegador predeterminado.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Piloto sintético de escritorio con PostgreSQL aislado.")
    parser.add_argument("--postgres-bin", required=True, type=Path)
    parser.add_argument("--salida", required=True, type=Path, help="carpeta nueva para el ensayo")
    parser.add_argument("--frontend", type=Path, default=BACKEND.parent / "frontend" / "dist-escritorio")
    args = parser.parse_args(argv)
    raiz, frontend = args.salida.resolve(), args.frontend.resolve()
    try:
        if not (frontend / "index.html").is_file() or not (frontend / "assets").is_dir():
            raise PilotoError("Compila primero el frontend con npm run build:escritorio.")
        print(f"Preparando datos sintéticos en {raiz}", flush=True)
        with referencia_sintetica(args.postgres_bin.resolve(), raiz) as (referencia, base):
            print("Referencia verificada. Para cerrar el ensayo, vuelve a esta consola y pulsa Ctrl+C.", flush=True)
            _servir(raiz, referencia, frontend, base)
    except KeyboardInterrupt:
        return 0
    except PilotoError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, ValueError, psycopg.Error) as error:
        print(f"No se completó el piloto ({type(error).__name__}). Carpeta del ensayo: {raiz}", file=sys.stderr)
        return 1
    return 0


def _interrumpir(_senal, _marco):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _interrumpir)
    raise SystemExit(main())
