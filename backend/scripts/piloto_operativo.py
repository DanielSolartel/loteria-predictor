"""Ejecuta un ensayo temporal del visor con el origen operativo de Fase 6."""
from __future__ import annotations

from contextlib import chdir
from datetime import datetime, timezone
import getpass
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
from runpy import run_path
import socket
import sys
from tempfile import TemporaryDirectory
import warnings
from zipfile import ZipFile

from sqlalchemy.engine import URL, make_url

from app.control_piloto import ControlVisor
from scripts.perfil_piloto_windows import CARPETA_OPERATIVA, VERSION_OPERATIVA, _directorio_local, _guardar
from scripts.piloto_escritorio import _ALMACENES, PilotoError, _entorno, servir_visor
from scripts.piloto_windows import JUEGOS, _puerto_cerrado, _puertos_en_escucha_windows


VERSION = "fase11-ensayo-operativo/1"
ROL = "loteria_visor_lector"
AUTO = "directorio_automatizacion"
DESTINOS = (*(f"directorio_{nombre.lower()}" for nombre in _ALMACENES), AUTO)
TABLAS = ("alembic_version", "colores", "juegos", "sincronizaciones", "sorteo_color_numero",
          "sorteo_numeros", "sorteo_superbalota", "sorteos")
TRANSPORTE = {"sslmode", "sslrootcert", "sslcert", "sslkey", "sslpassword", "channel_binding", "gssencmode",
              "target_session_attrs"}


class ProteccionArchivos:
    """Detecta intentos de mutación de las fuentes por las operaciones Python del visor."""

    _ESCRITURA = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_TRUNC | os.O_CREAT
    _UN_DESTINO = frozenset({"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.chown", "os.truncate",
                             "os.utime", "os.setxattr", "os.removexattr"})
    _DOS_DESTINOS = frozenset({"os.rename", "os.link", "os.symlink"})

    def __init__(self, *raices: Path):
        self.raices = raices
        self.intentos = 0

    def auditar(self, evento, argumentos):
        if evento == "open" and argumentos[2] & self._ESCRITURA:
            rutas = argumentos[:1]
        elif evento in self._UN_DESTINO:
            rutas = argumentos[:1]
        elif evento in self._DOS_DESTINOS:
            rutas = argumentos[:2]
        else:
            return
        for ruta in rutas:
            if isinstance(ruta, (str, bytes, os.PathLike)):
                resuelta = Path(os.fsdecode(ruta)).resolve()
                if any(resuelta.is_relative_to(raiz) for raiz in self.raices):
                    self.intentos += 1
                    raise PermissionError("El visor abrió una ruta protegida en modo de escritura.")


def origen_operativo(backend: Path, configuracion: Path) -> tuple[URL, dict[str, Path], ProteccionArchivos]:
    if configuracion.stat().st_size > 262144:
        raise PilotoError("configuracion_fase6_demasiado_grande")
    arranque = json.loads(configuracion.read_text(encoding="utf-8-sig"))
    if arranque.get("version") != 1 or Path(arranque["backend"]).resolve(strict=True) != backend:
        raise PilotoError("configuracion_backend_distinta")
    rutas = {nombre: Path(arranque["destinos"][nombre]) for nombre in DESTINOS}
    if not all(ruta.is_absolute() for ruta in rutas.values()):
        raise PilotoError("destino_de_artefactos_relativo")
    rutas = {nombre: ruta.resolve(strict=True) for nombre, ruta in rutas.items()}
    if not all(ruta.is_dir() and (os.name != "nt" or ":" in ruta.drive) for ruta in rutas.values()):
        raise PilotoError("destino_de_artefactos_no_local")

    guardia = ProteccionArchivos(backend, configuracion, *rutas.values())
    sys.addaudithook(guardia.auditar)
    with chdir(backend):
        ajustes = run_path(str(backend / "app/core/config.py"))["get_settings"]()
        if not hmac.compare_digest(hashlib.sha256(ajustes.database_url.encode("utf-8")).hexdigest(),
                                   arranque["database_sha256"]):
            raise PilotoError("huella_postgresql_distinta")
        if any(Path(getattr(ajustes, nombre)).resolve() != ruta for nombre, ruta in rutas.items()):
            raise PilotoError("destinos_fase6_distintos")
    url = make_url(ajustes.database_url)
    if (url.drivername not in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}
            or url.username != "loteria" or not url.host or not url.database):
        raise PilotoError("destino_postgresql_distinto")
    if (set(url.query) - TRANSPORTE - {"connect_timeout", "application_name"}
            or any(os.environ.get(k) for k in ("PGSERVICE", "PGHOSTADDR", "PGOPTIONS"))):
        raise PilotoError("parametros_postgresql_requieren_revision")
    puerto = url.port if url.port is not None else int(os.environ.get("PGPORT", "5432"))
    if not 1 <= puerto <= 65535:
        raise PilotoError("puerto_postgresql_fuera_de_rango")
    if url.host.casefold() == "localhost":
        ips = tuple(dict.fromkeys(fila[4][0] for fila in socket.getaddrinfo("localhost", puerto,
                                                                          type=socket.SOCK_STREAM)))
    else:
        ips = (url.host,)
    try:
        local = bool(ips) and all(ipaddress.ip_address(ip).is_loopback for ip in ips)
    except ValueError:
        local = False
    if not local:
        raise PilotoError("destino_postgresql_fuera_del_equipo")

    transporte = {k: v for k, v in url.query.items() if k in TRANSPORTE}
    if any(not isinstance(v, str) for v in transporte.values()):
        raise PilotoError("parametros_postgresql_requieren_revision")
    for nombre in ("sslrootcert", "sslcert", "sslkey"):
        if nombre in transporte and transporte[nombre] not in {"", "system"}:
            transporte[nombre] = str((backend / transporte[nombre]).resolve())
    lector = URL.create("postgresql+psycopg", username=ROL, host=",".join(url.host for _ in ips),
                        port=puerto, database=url.database,
                        query={**transporte, "hostaddr": ",".join(ips), "connect_timeout": "4"})
    return lector, rutas, guardia


def _contrasena() -> str:
    if not sys.stdin.isatty():
        raise PilotoError("abra_una_consola_interactiva_para_la_contrasena")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            clave = getpass.getpass(f"Contrasena de {ROL}: ")
        except getpass.GetPassWarning:
            raise PilotoError("la_consola_no_puede_ocultar_la_contrasena") from None
    if not clave or "\x00" in clave:
        raise PilotoError("contrasena_vacia_o_invalida")
    return clave


def verificar_lector(motor) -> dict:
    with motor.connect() as db:
        if not db.connection.driver_connection.pgconn.used_password:
            raise PilotoError("postgresql_no_comprobo_la_contrasena")
        db.exec_driver_sql("SET TRANSACTION READ ONLY")
        rol = db.exec_driver_sql("""
            SELECT current_user AS rol, current_user = session_user AS identidad_directa,
                   rolconnlimit AS limite, current_setting('server_version_num')::integer AS version,
                   current_setting('default_transaction_read_only') = 'on' AS lectura_por_defecto,
                   current_setting('transaction_read_only') = 'on' AS lectura,
                   current_schema() = 'public' AS esquema,
                   NOT (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls OR rolinherit)
                       AND NOT EXISTS (SELECT FROM pg_roles AS otro
                                       WHERE otro.oid <> r.oid AND pg_has_role(otro.oid, 'SET')) AS limitado
            FROM pg_roles AS r WHERE rolname = current_user
        """).mappings().one()
        if (rol["rol"] != ROL or rol["limite"] != 4 or rol["version"] < 160000
                or not all(rol[k] for k in ("identidad_directa", "lectura_por_defecto", "lectura", "esquema", "limitado"))):
            raise PilotoError("identidad_o_ajustes_del_lector_distintos")
        tablas = db.exec_driver_sql("""
            SELECT relname FROM pg_class AS c JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND relname = ANY(%s::text[]) AND c.relkind IN ('r', 'p')
              AND has_table_privilege(c.oid, 'SELECT')
        """, (list(TABLAS),)).scalars().all()
        if set(tablas) != set(TABLAS):
            raise PilotoError("permisos_de_consulta_incompletos")
        revision = db.exec_driver_sql("SELECT version_num FROM public.alembic_version LIMIT 2").scalars().all()
        if revision != ["0006"]:
            raise PilotoError("revision_alembic_distinta")
        return {"rol": ROL, "contrasena_comprobada": True, "transaccion_solo_lectura": True,
                "postgresql_version_num": rol["version"], "revision_alembic": revision, "tablas_select": len(tablas)}


def ensayar(paquete: ZipFile, temporal: Path, origen: URL, rutas: dict[str, Path], control: ControlVisor, informe: dict,
            apuestas: Path):
    for entrada in paquete.infolist():
        if entrada.filename.startswith("interfaz/"):
            paquete.extract(entrada, temporal)
    interfaz = temporal / "interfaz"
    if not (interfaz / "index.html").is_file():
        raise PilotoError("interfaz_incompleta")
    informe["etapa"] = "contrasena"
    origen = origen.set(password=_contrasena()).update_query_dict({"application_name": f"lp11_visor_{control.identificador}"})
    entorno = _entorno()
    if os.name == "nt":
        entorno.pop("BROWSER", None)
    os.environ.clear()
    os.environ.update(entorno)
    os.environ.update({nombre.upper(): str(ruta) for nombre, ruta in rutas.items()})
    os.environ.update(DATABASE_URL=origen.render_as_string(hide_password=False), BASE_POOL_TAMANO="4",
                      BASE_POOL_DESBORDE="0", BASE_POOL_ESPERA_S="2")
    del origen
    informe["etapa"] = "verificar_lector"
    try:
        from app.infrastructure.db.session import engine
    finally:
        del os.environ["DATABASE_URL"]
    try:
        informe.update(verificar_lector(engine))
        informe["etapa"] = "visor"
        print("Abriendo el visor en el navegador con datos reales de Fase 6.", flush=True)
        servir_visor(interfaz, rutas[AUTO], None, datos="fase6", control=control, apuestas=apuestas)
    finally:
        sin_conexiones_prestadas = engine.pool.checkedout() == 0
        informe["conexiones_visor_liberadas"] = False
        engine.dispose()
        informe["conexiones_visor_liberadas"] = sin_conexiones_prestadas


def main() -> int:
    control = ControlVisor()
    instalado = os.environ.get("LP11_INSTALADO") == "1"
    informe = {"version": VERSION, "datos": "fase6", "estado": "ensayo_detenido", "etapa": "configuracion",
               "fecha_utc": datetime.now(timezone.utc).isoformat(), "temporal_retirado": False}
    archivo = Path(sys.argv[0]).resolve()
    temporal = None
    guardia = None
    try:
        if len(sys.argv) != 3:
            raise PilotoError("indique_backend_y_configuracion")
        backend = Path(sys.argv[1]).resolve(strict=True)
        configuracion = Path(sys.argv[2]).resolve(strict=True)
        with ZipFile(archivo) as paquete:
            informe["base_codigo"] = paquete.read("base-codigo.txt").decode("ascii").strip()
            origen, rutas, guardia = origen_operativo(backend, configuracion)
            local = Path(os.environ["LOCALAPPDATA"]).resolve(strict=True) if os.name == "nt" else None
            with TemporaryDirectory(prefix="LP11-R-", dir=local) as carpeta:
                temporal = Path(carpeta)
                perfil = temporal
                if instalado:
                    perfil = _directorio_local(CARPETA_OPERATIVA, VERSION_OPERATIVA)
                apuestas = perfil / "apuestas.sqlite3"
                if any(apuestas.resolve().is_relative_to(raiz) for raiz in guardia.raices):
                    raise PilotoError("registro_de_apuestas_en_una_fuente_fase6")
                with chdir(temporal):
                    ensayar(paquete, temporal, origen, rutas, control, informe, apuestas)

        informe["etapa"] = "cierre"
        informe["puerto_visor"] = control.puerto
        escuchas = _puertos_en_escucha_windows() if os.name == "nt" else None
        informe["visor_detenido"] = _puerto_cerrado(control.puerto, escuchas)
        informe["sesion_navegador"] = control.sesion
        informe["cierre_desde_visor"] = control.cierre_solicitado
        informe["juegos_con_cartera_consultada"] = sorted(control.juegos_con_cartera_consultada)
        informe["comparacion_consultada"] = any(r.endswith("/comparacion") for r in control.consultas)
        informe["sincronizacion_consultada"] = "/api/v1/escritorio/sincronizacion" in control.consultas
        if not (informe["visor_detenido"] and informe["conexiones_visor_liberadas"]
                and not temporal.exists() and guardia.intentos == 0):
            raise PilotoError("cierre_o_proteccion_de_archivos_pendiente")
        completo = (control.sesion and control.cierre_solicitado and control.juegos_con_cartera_consultada == JUEGOS
                    and informe["comparacion_consultada"] and informe["sincronizacion_consultada"])
        if completo:
            informe["estado"] = "recorrido_completado"
        elif instalado and control.cierre_solicitado:
            informe["estado"] = "visor_cerrado"
        else:
            informe["estado"] = "recorrido_parcial"
    except (Exception, KeyboardInterrupt) as error:
        informe["tipo_error"] = type(error).__name__
        if isinstance(error, PilotoError):
            informe["motivo"] = str(error)
    finally:
        informe["intentos_de_escritura_en_fuentes"] = None if guardia is None else guardia.intentos
        informe["temporal_retirado"] = temporal is not None and not temporal.exists()
    codigo = 0 if informe["estado"] in {"recorrido_completado", "visor_cerrado"} else 1
    informe["codigo"] = codigo
    destino = archivo.with_name(f"evidencia-f11-fase6-{control.identificador}.json")
    try:
        _guardar(destino, informe)
    except OSError:
        informe["evidencia_guardada"] = False
    print(json.dumps(informe, ensure_ascii=True, indent=2), flush=True)
    if informe.get("evidencia_guardada", True):
        print(f"Evidencia: {destino}", flush=True)
    return codigo
