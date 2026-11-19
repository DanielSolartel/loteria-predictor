"""Ensayo de escritorio portátil. Solo utiliza el clúster y los datos del paquete."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import webbrowser
from contextlib import closing
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPException
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.control_piloto import ControlVisor
from scripts.perfil_piloto_windows import VERSION, _directorio_local, _guardar, _instancia_unica, _sin_enlace
from scripts.piloto_escritorio import BASE_PRUEBA, IP, LECTOR, PilotoError, _entorno, _interrumpir, _servir, referencia_sintetica

JUEGOS = {"BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"}
_INSTANCIA = re.compile(r"[a-f0-9]{12}")
_TCP_TABLE_OWNER_PID_LISTENER = 3
_ERROR_INSUFFICIENT_BUFFER = 122


class _FilaTcpWindows(ctypes.Structure):
    _fields_ = [(campo, ctypes.c_uint32) for campo in (
        "estado", "direccion_local", "puerto_local", "direccion_remota", "puerto_remoto", "pid",
    )]


class _TablaTcpWindows(ctypes.Structure):
    _fields_ = [("cantidad", ctypes.c_uint32), ("filas", _FilaTcpWindows * 1)]


def _reabrir(directorio: Path) -> bool:
    ruta = directorio / "activa.json"
    try:
        if ruta.is_symlink() or ruta.stat().st_size > 512:
            return False
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        ident, puerto = datos["instancia"], datos["puerto"]
        if not _INSTANCIA.fullmatch(ident) or type(puerto) is not int or not 1 <= puerto <= 65535:
            return False
        with closing(HTTPConnection(IP, puerto, timeout=2)) as c:
            c.request("GET", "/escritorio/instancia")
            respuesta = c.getresponse()
            if respuesta.status != 200 or json.loads(respuesta.read(256)) != {"instancia": ident}:
                return False
        if not webbrowser.open(f"http://{IP}:{puerto}/"):
            return False
        raiz = directorio / f"p-{ident}"
        if raiz.is_symlink() or raiz.is_junction() or not raiz.is_dir():
            return False
        marca = raiz / "reapertura.ok"
        if not marca.exists():
            with marca.open("xb"):
                pass
        return True
    except (OSError, HTTPException, webbrowser.Error, ValueError, KeyError, TypeError):
        return False


def _conexion(base: str):
    u = make_url(base)
    if (u.host, u.database, u.username) != (IP, BASE_PRUEBA, LECTOR):
        raise PilotoError("La conexión no corresponde al lector sintético.")
    return psycopg.connect(host=IP, port=u.port, dbname=BASE_PRUEBA, user=LECTOR, password=u.password,
                           connect_timeout=3, sslmode="disable", options="")


def _permisos(base: str) -> dict:
    with _conexion(base) as db:
        solo_lectura = db.execute("SHOW transaction_read_only").fetchone()[0] == "on"
        db.execute("SET default_transaction_read_only = off")
        db.commit()
        estados = {}
        for nombre, orden in (("update", "UPDATE sorteos SET fuente = fuente WHERE false"),
                              ("create", "CREATE TABLE public.prueba_permiso_f11 (id integer)")):
            try:
                db.execute(orden)
            except psycopg.Error as error:
                estados[nombre] = error.sqlstate
            else:
                estados[nombre] = "permitido"
            finally:
                db.rollback()
        return {"transaccion_lectura": solo_lectura, **estados}


def _foto_base(base: str) -> dict[str, str]:
    with _conexion(base) as db:
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        nombres = db.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename").fetchall()
        revision = db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        fuentes = db.execute("SELECT DISTINCT fuente FROM sorteos").fetchall()
        juegos = {fila[0] for fila in db.execute("SELECT codigo FROM juegos")}
        if revision != "0006" or fuentes != [("fixture_sintetica",)] or juegos != JUEGOS or len(nombres) != 13:
            raise PilotoError("La base restaurada no coincide con la referencia sintética.")
        return {n: hashlib.sha256("\n".join(f[0] for f in db.execute(sql.SQL(
            "SELECT to_jsonb(t)::text FROM public.{} t ORDER BY 1").format(sql.Identifier(n)))).encode()).hexdigest()
                for (n,) in nombres}


def _archivos(referencia: Path):
    for directorio, carpetas, nombres in os.walk(referencia, followlinks=False):
        padre = Path(directorio)
        for nombre in (*carpetas, *nombres):
            ruta = padre / nombre
            if ruta.is_symlink() or ruta.is_junction():
                raise PilotoError("Apareció un enlace en la referencia del ensayo.")
        yield from (padre / nombre for nombre in nombres)


def _foto_archivos(referencia: Path) -> dict[str, str]:
    return {ruta.relative_to(referencia).as_posix(): hashlib.sha256(ruta.read_bytes()).hexdigest()
            for ruta in _archivos(referencia)}


def _cerrojo_lectura(referencia: Path) -> bool:
    ruta = referencia / "publicacion" / "carteras" / "operacion" / "BALOTO.lock"
    ruta.parent.mkdir()
    ruta.write_bytes(b"prueba-f11")
    for archivo in _archivos(referencia):
        archivo.chmod(stat.S_IREAD)
    try:
        descriptor = os.open(ruta, os.O_RDWR)
    except PermissionError:
        return True
    os.close(descriptor)
    return False


def _puertos_en_escucha_windows() -> set[int]:
    """Consulta las escuchas IPv4 de loopback, incluidas las de dirección comodín."""
    consultar = ctypes.WinDLL("iphlpapi.dll").GetExtendedTcpTable
    consultar.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
                          ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    consultar.restype = ctypes.c_uint32
    tamano = ctypes.c_uint32()
    tabla = None
    for _ in range(4):
        codigo = consultar(tabla, ctypes.byref(tamano), False, socket.AF_INET, _TCP_TABLE_OWNER_PID_LISTENER, 0)
        if codigo == 0 and tabla is not None:
            break
        if codigo != _ERROR_INSUFFICIENT_BUFFER or tamano.value < _TablaTcpWindows.filas.offset:
            raise PilotoError(f"No se pudo consultar la tabla TCP de Windows (código {codigo}).")
        tabla = ctypes.create_string_buffer(tamano.value)
    else:
        raise PilotoError("La tabla TCP de Windows cambió durante la verificación del cierre.")

    inicio = _TablaTcpWindows.filas.offset
    if len(tabla) < inicio:
        raise PilotoError("Windows devolvió una tabla TCP incompleta.")
    cantidad = ctypes.c_uint32.from_buffer(tabla).value
    if inicio + cantidad * ctypes.sizeof(_FilaTcpWindows) > len(tabla):
        raise PilotoError("Windows devolvió una tabla TCP incompleta.")
    filas = (_FilaTcpWindows * cantidad).from_buffer(tabla, inicio)
    loopback = int.from_bytes(socket.inet_aton(IP), sys.byteorder)
    return {socket.ntohs(fila.puerto_local & 0xFFFF) for fila in filas if fila.direccion_local in (0, loopback)}


def _puerto_cerrado(puerto: int | None, puertos_en_escucha: set[int] | None = None) -> bool:
    if puerto is None:
        return False
    if puertos_en_escucha is not None:
        return puerto not in puertos_en_escucha
    try:
        with socket.create_connection((IP, puerto), timeout=1):
            return False
    except ConnectionRefusedError:
        return True


def _quitar_solo_lectura(funcion, ruta, error):
    if not isinstance(error, PermissionError):
        raise error
    os.chmod(ruta, stat.S_IREAD | stat.S_IWRITE)
    funcion(ruta)


def _comprobar_binarios(kit: Path) -> Path:
    binarios = kit / "pgsql" / "bin"
    runtime = kit / "runtime"
    bibliotecas = runtime / "Lib" / "site-packages" / "sklearn" / ".libs"
    # ICU en el ZIP de PostgreSQL importa MSVCP140. El wheel fijado de sklearn la incluye.
    os.environ["PATH"] = os.pathsep.join((str(runtime), str(bibliotecas), str(binarios), os.environ.get("PATH", "")))
    for nombre in ("postgres", "initdb", "pg_ctl", "pg_restore"):
        try:
            salida = subprocess.run([binarios / f"{nombre}.exe", "--version"], check=True, capture_output=True,
                                    timeout=10, env=_entorno()).stdout
        except (OSError, subprocess.SubprocessError) as error:
            raise PilotoError(f"Windows no pudo iniciar {nombre}.exe. Revisa las dependencias nativas.") from error
        if b"17.11" not in salida:
            raise PilotoError("La versión de PostgreSQL no coincide con el ensayo.")
    return binarios


def _ensayar(kit: Path, directorio: Path, informe: dict) -> None:
    control = ControlVisor()
    raiz = directorio / f"p-{control.identificador}"
    activa = directorio / "activa.json"
    informe["directorio_ensayo"] = raiz.name
    informe["etapa"] = "binarios"
    binarios = _comprobar_binarios(kit)
    informe["etapa"] = "restaurar_referencia"
    try:
        with referencia_sintetica(binarios, raiz, semilla=kit / "referencia") as (ref, base):
            informe["etapa"] = "verificar_lectura"
            puerto_pg = make_url(base).port
            permisos = _permisos(base)
            informe["permisos_sql"] = permisos
            informe["archivo_solo_lectura"] = _cerrojo_lectura(ref)
            if (permisos != {"transaccion_lectura": True, "update": "42501", "create": "42501"}
                    or not informe["archivo_solo_lectura"]):
                raise PilotoError("Falló un control de permisos del lector.")
            tablas, archivos = _foto_base(base), _foto_archivos(ref)
            informe["etapa"] = "visor"
            try:
                _servir(raiz, ref, kit / "interfaz", base, control=control,
                        publicar=lambda: _guardar(activa, {"instancia": control.identificador, "puerto": control.puerto}))
            except KeyboardInterrupt:
                pass
            informe["sesion_navegador"] = control.sesion
            informe["cierre_desde_visor"] = control.cierre_solicitado
            informe["reutilizo_instancia"] = (raiz / "reapertura.ok").is_file()
            informe["juegos_consultados"] = sorted(j for j in JUEGOS if f"/api/v1/juegos/{j}/predicciones" in control.consultas)
            informe["comparacion_consultada"] = any(r.endswith("/comparacion") for r in control.consultas)
            informe["sincronizacion_consultada"] = "/api/v1/escritorio/sincronizacion" in control.consultas
            informe["tablas_identicas"] = len(tablas) if _foto_base(base) == tablas else 0
            informe["archivos_identicos"] = len(archivos) if _foto_archivos(ref) == archivos else 0
    finally:
        os.chdir(kit)
        activa.unlink(missing_ok=True)

    informe["etapa"] = "cierre"
    informe["puertos_locales"] = {"visor": control.puerto, "postgres": puerto_pg}
    informe["visor_detenido"] = None
    informe["postgres_detenido"] = None
    escuchas = _puertos_en_escucha_windows() if os.name == "nt" else None
    informe["visor_detenido"] = _puerto_cerrado(control.puerto, escuchas)
    informe["postgres_detenido"] = (not (raiz / "pg" / "postmaster.pid").exists()
                                   and _puerto_cerrado(puerto_pg, escuchas))
    if not (informe["visor_detenido"] and informe["postgres_detenido"] and informe["tablas_identicas"]
            and informe["archivos_identicos"]):
        raise PilotoError("El cierre o la conservación de la referencia quedó pendiente.")
    informe["etapa"] = "limpieza"
    shutil.rmtree(raiz, onexc=_quitar_solo_lectura)
    informe["temporal_retirado"] = True
    completo = (informe["sesion_navegador"] and informe["cierre_desde_visor"] and informe["reutilizo_instancia"]
                and set(informe["juegos_consultados"]) == JUEGOS and informe["comparacion_consultada"]
                and informe["sincronizacion_consultada"])
    informe["estado"] = "ensayo_completado" if completo else "ensayo_parcial"


def iniciar(kit: Path, manifiesto: dict) -> int:
    if os.name != "nt" or sys.maxsize <= 2**32 or ctypes.windll.shell32.IsUserAnAdmin():
        print("Abre el piloto en Windows x64 desde una sesión normal de usuario.")
        return 1
    signal.signal(signal.SIGTERM, _interrumpir)
    os.environ.pop("BROWSER", None)
    directorio = _directorio_local()
    with _instancia_unica(directorio) as primera:
        if not primera:
            print("Se abrió la instancia existente." if _reabrir(directorio) else "Ya hay un piloto iniciándose o cerrándose.")
            return 0
        informe = {"version": VERSION, "base_codigo": manifiesto["base_codigo"], "datos": "sinteticos",
                   "fecha_utc": datetime.now(timezone.utc).isoformat(), "estado": "ensayo_detenido",
                   "temporal_retirado": False}
        evidencias = kit
        if manifiesto.get("entrega") == "instalador_usuario":
            evidencias = directorio / "evidencias"
            _sin_enlace(evidencias)
            evidencias.mkdir(mode=0o700, exist_ok=True)
            informe["entrega"] = "instalador_usuario"
        print("Preparando la referencia sintética en una carpeta privada. Se abrirá el navegador.", flush=True)
        try:
            _ensayar(kit, directorio, informe)
        except (Exception, KeyboardInterrupt) as error:
            informe["tipo_error"] = type(error).__name__
            if isinstance(error, PilotoError):
                informe["motivo"] = str(error)
                print(error)
        destino = evidencias / f"evidencia-f11-{informe.get('directorio_ensayo', 'inicio')}.json"
        _guardar(destino, informe)
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        print(f"\nComparte el archivo {destino}")
        return 0 if informe["estado"] in ("ensayo_completado", "ensayo_parcial") else 1
