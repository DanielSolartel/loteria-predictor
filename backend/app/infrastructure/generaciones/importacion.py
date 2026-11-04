"""Importador de generaciones en el servidor de consulta (E10.4; activacion en E10.5 segun D11).

    <raiz>/preparacion/<id>/   preparacion aislada (nunca la lee la API)
    <raiz>/generaciones/<id>/  generacion ACEPTADA: manifiesto, firma, coherencia y `archivos/` (solo lectura)
    <raiz>/registro/           informe de cada importacion (aceptada o rechazada)
    <raiz>/activa.json         generacion que debe servir el proximo arranque (solo la cambia `activar`)

Base: `prep_<id>` mientras se prepara; `pub_<id>` al aceptarla, con `COMMENT ON DATABASE` =
`loteria-generacion:<id>:<sha256 del manifiesto>`, solo lectura por defecto y CONNECT/SELECT para el rol lector.

Pasos (cualquier fallo: RECHAZO y limpieza de lo creado en ESTA importacion; la generacion activa y las
aceptadas no se tocan; nunca queda una generacion parcial utilizable porque la API exige `pub_<id>` con el
comentario exacto Y la carpeta `generaciones/<id>` con su manifiesto firmado):
 1. verificacion del paquete (`verificacion`): firma, identidad, archivos exactos y huellas;
 2. compatibilidad: revision de Alembic y huella de las fuentes (`app/` y `alembic/`) iguales a las del codigo
    que importa (la imagen de la API se construye con el mismo commit);
 3. base nueva `prep_<id>` y migracion de Alembic a la revision del manifiesto; huella del esquema identica;
 4. carga de filas en una transaccion y huella de contenido de cada tabla identica a la del manifiesto;
 5. copia verificada de `archivos/`, solo lectura;
 6. coherencia cruzada OTRA VEZ contra la base restaurada: mismo resumen y sin rechazos;
 7. permisos de solo lectura y consultas de humo (19 endpoints x 4 juegos + procedencias, rol lector, en un
    proceso aparte) con criterios de contenido y medicion de lecturas de archivos (DAT-01);
 8. aceptacion: `prep_<id>` -> `pub_<id>` + comentario; `preparacion/<id>` -> `generaciones/<id>`; registro.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import os
import secrets
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.generaciones import archivos as ar
from app.infrastructure.generaciones import base_logica as bl
from app.infrastructure.generaciones import coherencia as co
from app.infrastructure.generaciones import consultas
from app.infrastructure.generaciones import firma
from app.infrastructure.generaciones import inventario as inv
from app.infrastructure.generaciones.captura import BACKEND, huella_del_codigo, id_de
from app.infrastructure.generaciones.formato import (
    COHERENCIA, FIRMA, MANIFIESTO, GeneracionNoValida, canonico, escribir_exclusivo, es_id, leer_canonico,
    sha256_archivo,
)
from app.infrastructure.generaciones.verificacion import verificar

COMENTARIO = "loteria-generacion"


class ImportacionRechazada(RuntimeError):
    def __init__(self, paso: str, motivo: str):
        super().__init__(f"{paso}: {motivo}")
        self.paso, self.motivo = paso, motivo


@dataclass
class Destino:
    raiz: Path
    url_admin: str          # rol con CREATEDB (sin superusuario) sobre la base de mantenimiento
    url_lector: str         # rol lector de la API (su base se sustituye por la de la generacion)
    rol_lector: str = "consulta_lector"
    espera_exclusion: float = 0.0  # segundos que se espera a otra importacion/restauracion del servidor


# ---------------------------------------------------------------------------
# Propiedad y exclusion en el servidor (E104-IMP-01)
# ---------------------------------------------------------------------------
#
# EXCLUSION: toda importacion o restauracion toma el MISMO advisory de sesion en la base de mantenimiento
# (`postgres`) del servidor, sea cual sea su raiz: dos procesos nunca preparan, recuperan ni borran bases a la
# vez. Los advisory son por base de datos; todos los importadores se conectan a la misma de mantenimiento.
#
# PROPIEDAD: cada base que se crea lleva, desde justo despues de su `CREATE DATABASE`, el ajuste
# `loteria.importacion = '<id de la raiz>:<intento>'` (o `loteria.restauracion`), que sobrevive al cambio de
# nombre y no forma parte del esquema. Antes de crearla, la raiz registra el intento en
# `preparacion/<id>.intento`. Una base solo se borra si su duena es el rol actual Y su ajuste es el de ESTA raiz
# y ESTE intento registrado (y, si se creo en esta llamada, su OID no cambio). Nunca se borra una base por su
# nombre: `pub_<id>` aceptada en otra raiz, o cualquier base sin esa prueba, rechaza la importacion sin tocarla.

AJUSTE_IMPORTACION, AJUSTE_RESTAURACION = "loteria.importacion", "loteria.restauracion"
CLAVE_EXCLUSION = int.from_bytes(hashlib.sha256(b"loteria:generaciones:importacion-y-restauracion").digest()[:8],
                                 "big", signed=True)
_ID_RAIZ = re.compile(r"^[0-9a-f]{32}$")


def id_de_raiz(raiz: Path, *, crear: bool = True) -> str:
    """Identificador aleatorio y estable de una raiz (`.raiz-e104`, creado una vez en modo exclusivo)."""
    ruta = raiz / ".raiz-e104"
    if crear and not os.path.lexists(ruta):
        try:
            escribir_exclusivo(ruta, (secrets.token_hex(16) + "\n").encode("ascii"))
        except FileExistsError:
            pass
    if ruta.is_symlink() or not ruta.is_file():
        raise GeneracionNoValida("la identidad de la raiz no es un archivo regular")
    valor = ruta.read_text(encoding="ascii").strip()
    if not _ID_RAIZ.fullmatch(valor):
        raise GeneracionNoValida("identidad de la raiz no valida")
    return valor


class Exclusion:
    """Advisory de sesion del servidor; se suelta al salir (y con la conexion, si el proceso muere)."""

    def __init__(self, admin, espera: float = 0.0, reloj=time.monotonic, dormir=time.sleep):
        self.admin, self.espera, self.reloj, self.dormir = admin, espera, reloj, dormir

    def __enter__(self):
        fin = self.reloj() + self.espera
        while True:
            fila = self.admin.execute("SELECT pg_try_advisory_lock(%s)", (CLAVE_EXCLUSION,)).fetchone()
            if fila and fila[0] is True:
                return self
            if self.reloj() >= fin:
                raise ImportacionRechazada("exclusion", "otra importacion o restauracion esta en curso en este "
                                                        "servidor (o no se pudo acreditar la exclusion)")
            self.dormir(min(0.5, max(0.0, fin - self.reloj())))

    def __exit__(self, *_):
        try:
            self.admin.execute("SELECT pg_advisory_unlock(%s)", (CLAVE_EXCLUSION,))
        except Exception:  # la conexion se cierra igualmente y el advisory de sesion se libera con ella
            pass


def ajuste_de(admin, nombre: str, ajuste: str) -> str | None:
    fila = admin.execute(
        "SELECT s.setconfig FROM pg_db_role_setting s JOIN pg_database d ON d.oid = s.setdatabase "
        "WHERE d.datname = %s AND s.setrole = 0", (nombre,)).fetchone()
    for valor in (fila[0] if fila and fila[0] else []):
        clave, _, contenido = str(valor).partition("=")
        if clave == ajuste:
            return contenido
    return None


def _oid(admin, nombre: str):
    fila = admin.execute("SELECT oid FROM pg_database WHERE datname = %s", (nombre,)).fetchone()
    return fila[0] if fila else None


def _es_duena(admin, nombre: str) -> bool:
    fila = admin.execute("SELECT pg_get_userbyid(datdba) = current_user FROM pg_database WHERE datname = %s",
                         (nombre,)).fetchone()
    return bool(fila and fila[0] is True)


def marcar_base(admin, nombre: str, ajuste: str, valor: str) -> None:
    from psycopg import sql
    admin.execute(sql.SQL("ALTER DATABASE {} SET {} = {}").format(sql.Identifier(nombre), sql.SQL(ajuste),
                                                                 sql.Literal(valor)))


def borrar_base_propia(admin, nombre: str, ajuste: str, valor: str, oid=None) -> bool:
    """Borra `nombre` solo con prueba de propiedad; devuelve False (sin tocarla) si no la hay o no existe."""
    if not _existe_base(admin, nombre):
        return False
    if not _es_duena(admin, nombre) or ajuste_de(admin, nombre, ajuste) != valor:
        return False
    if oid is not None and _oid(admin, nombre) != oid:
        return False
    admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s "
                  "AND pid <> pg_backend_pid()", (nombre,))
    admin.execute(f"DROP DATABASE {_ident(nombre)}")
    return True


def _url_con_base(url: str, base: str) -> str:
    from sqlalchemy.engine import make_url

    return make_url(url).set(database=base).render_as_string(hide_password=False)


def _ident(nombre: str) -> str:
    return '"' + nombre.replace('"', '""') + '"'


def nombre_base(gid: str, aceptada: bool) -> str:
    return f"{'pub' if aceptada else 'prep'}_{gid}"


def comentario(gid: str, sha_manifiesto: str) -> str:
    return f"{COMENTARIO}:{gid}:{sha_manifiesto}"


def _existe_base(admin, nombre: str) -> bool:
    return admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,)).fetchone() is not None


def _migrar(url: str, revision: str) -> None:
    entorno = {k: v for k, v in os.environ.items() if not k.startswith(("DATABASE_URL", "DIRECTORIO_"))}
    entorno["DATABASE_URL"] = url if "+psycopg" in url else url.replace("postgresql://", "postgresql+psycopg://", 1)
    r = subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", revision], cwd=BACKEND, env=entorno,
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise ImportacionRechazada("migracion", (r.stderr or r.stdout).strip().splitlines()[-1][:300])


def _historico_de(url: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import NullPool

    from app.application.use_cases.laboratorio import Lectura, leer_historico
    from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
    from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
        ResultadosHistoricosRepositorySQLAlchemy,
    )

    motor = create_engine(url if "+psycopg" in url else url.replace("postgresql://", "postgresql+psycopg://", 1),
                          poolclass=NullPool)
    sesion = Session(motor)
    lectura = Lectura(JuegoRepositorySQLAlchemy(sesion), ResultadosHistoricosRepositorySQLAlchemy(sesion))

    def historico(juego):
        try:
            return list(leer_historico(lectura, juego))
        except Exception as error:
            if type(error).__name__ == "JuegoNoEncontradoError":
                return None
            raise

    def cerrar():
        sesion.close()
        motor.dispose()

    return historico, cerrar


def consultas_en_proceso_aparte(url_lector: str, carpeta_archivos: Path, salida: Path,
                                esperado: dict | None = None) -> dict:
    """Ejecuta `scripts.generaciones consultas` con el rol lector y los almacenes de la generacion."""
    entorno = {k: v for k, v in os.environ.items() if not k.startswith(("DATABASE_URL", "DIRECTORIO_",
                                                                         "API_PUBLICA_", "GENERACION_"))}
    entorno["DATABASE_URL"] = url_lector if "+psycopg" in url_lector else \
        url_lector.replace("postgresql://", "postgresql+psycopg://", 1)
    for a in inv.ALMACENES:
        entorno[a.ajuste.upper()] = str(carpeta_archivos / a.nombre if a.clase == inv.PUBLICABLE
                                        else carpeta_archivos.parent / "sin-publicar" / a.nombre)
    orden = [sys.executable, "-B", "-m", "scripts.generaciones", "consultas", "--salida", str(salida)]
    if esperado is not None:  # recuentos de la coherencia sellada: minimos de lo que deben devolver las consultas
        ruta_esperado = salida.with_suffix(".esperado.json")
        escribir_exclusivo(ruta_esperado, canonico(esperado))
        orden += ["--esperado", str(ruta_esperado)]
    r = subprocess.run(orden,
                       cwd=BACKEND, env=entorno, capture_output=True, text=True, timeout=900)
    if r.returncode not in (0, 1) or not salida.exists():
        raise ImportacionRechazada("consultas", (r.stderr or r.stdout).strip()[-300:])
    return json.loads(salida.read_text(encoding="utf-8"))


def _registrar(raiz: Path, gid: str, informe: dict) -> Path:
    marca = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    ruta = raiz / "registro" / f"{gid}-{informe['resultado']}-{marca}.json"
    escribir_exclusivo(ruta, canonico(informe))
    return ruta


def _registro_de_intento(raiz: Path, gid: str) -> Path:
    return raiz / "preparacion" / f"{gid}.intento"


def leer_intento(ruta: Path) -> str | None:
    """Intento registrado por ESTA raiz (archivo regular pequeno, sin enlaces), o None si no hay registro."""
    if not os.path.lexists(ruta):
        return None
    if ruta.is_symlink() or not ruta.is_file() or ruta.stat().st_size > 400:
        raise ImportacionRechazada("restos", f"registro de intento no valido: {ruta.name}")
    try:
        intento = json.loads(ruta.read_text(encoding="utf-8"))["intento"]
    except (ValueError, KeyError, TypeError) as error:
        raise ImportacionRechazada("restos", f"registro de intento ilegible: {ruta.name}") from error
    if not isinstance(intento, str) or not re.fullmatch(r"[0-9a-f]{32}", intento):
        raise ImportacionRechazada("restos", f"registro de intento no valido: {ruta.name}")
    return intento


def bases_con_prefijo(admin, prefijo: str) -> list[str]:
    filas = admin.execute("SELECT datname FROM pg_database WHERE left(datname, %s) = %s ORDER BY datname",
                          (len(prefijo), prefijo)).fetchall()
    return [f[0] for f in filas]


def _recuperar_restos(admin, raiz: Path, gid: str, rid: str, informe: dict) -> None:
    """Restos de una importacion interrumpida de ESTE id en ESTA raiz: se borran solo con prueba de propiedad.
    Una base `prep_` ajena no estorba (los nombres llevan el intento) y se informa sin tocarla; una `pub_<id>`
    o una carpeta de preparacion sin prueba rechazan la importacion con diagnostico."""
    registro = _registro_de_intento(raiz, gid)
    intento = leer_intento(registro)
    valor = f"{rid}:{intento}" if intento else None
    ajenas = []
    for nombre in bases_con_prefijo(admin, f"prep_{gid}_"):
        if valor and borrar_base_propia(admin, nombre, AJUSTE_IMPORTACION, valor):
            informe.setdefault("restos_recuperados", []).append(nombre)
        else:
            ajenas.append(nombre)
    if ajenas:
        informe["bases_ajenas_intactas"] = ajenas
    publica = nombre_base(gid, True)
    if _existe_base(admin, publica):
        activa = raiz / "activa.json"
        es_activa = activa.is_file() and leer_canonico(activa).get("id") == gid
        if valor and not es_activa and borrar_base_propia(admin, publica, AJUSTE_IMPORTACION, valor):
            informe.setdefault("restos_recuperados", []).append(publica)
        else:
            marca = ajuste_de(admin, publica, AJUSTE_IMPORTACION) or ""
            motivo = ("generacion_aceptada_en_otra_raiz" if marca and not marca.startswith(rid + ":") else
                      "base_publicada_sin_prueba_de_propiedad")
            raise ImportacionRechazada("restos", f"{motivo}: {publica} existe y no se toca (retirela a mano tras "
                                                 "comprobar que no sirve a ninguna raiz)")
    carpeta = raiz / "preparacion" / gid
    if os.path.lexists(carpeta) or os.path.lexists(ar.marca_de(carpeta)):
        try:
            if not intento:
                raise ar.NoPropia("sin registro de intento")
            ar.borrar_propia(carpeta, raiz / "preparacion", intento)
            informe.setdefault("restos_recuperados", []).append(f"preparacion/{gid}")
        except ar.NoPropia as error:
            raise ImportacionRechazada("restos", f"carpeta_de_preparacion_sin_prueba_de_propiedad: {error}") \
                from error
    if intento:
        registro.unlink()


def importar(paquete: Path, clave_publica: Path, destino: Destino, *,
             fase: Callable[[str], None] = lambda _: None) -> dict:
    raiz = destino.raiz
    for sub in ("preparacion", "generaciones", "registro"):
        (raiz / sub).mkdir(parents=True, exist_ok=True)
    informe = {"paquete": paquete.name, "inicio": dt.datetime.now(dt.timezone.utc).isoformat(), "pasos": []}
    gid, creadas, prep_dir, intento, valor = None, {}, None, None, None
    admin = bl.conectar(_url_con_base(destino.url_admin, "postgres"), autocommit=True)
    exclusion = Exclusion(admin, destino.espera_exclusion)
    try:
        try:
            exclusion.__enter__()
            rid = id_de_raiz(raiz)
            try:
                manifiesto = verificar(paquete, clave_publica)
            except GeneracionNoValida as error:
                raise ImportacionRechazada("verificacion", str(error)) from error
            gid = manifiesto["id"]
            informe["id"] = gid
            informe["pasos"].append("verificacion")
            fase("verificacion")
            codigo = huella_del_codigo()
            if manifiesto["codigo"]["revision_alembic"] != codigo["revision_alembic"] or \
                    manifiesto["esquema"]["revision_alembic"] != codigo["revision_alembic"]:
                raise ImportacionRechazada("compatibilidad", "revision de Alembic distinta de la del codigo que importa")
            if manifiesto["codigo"]["huella_fuentes"] != codigo["huella_fuentes"] or \
                    manifiesto["codigo"].get("huella_app") != codigo["huella_app"]:
                raise ImportacionRechazada("compatibilidad", "huella de las fuentes distinta: la generacion es de otro "
                                           "codigo (importe con el mismo commit)")
            informe["pasos"].append("compatibilidad")
            final_dir = raiz / "generaciones" / gid
            if os.path.lexists(final_dir):
                verificar_publicada(final_dir, clave_publica, admin, raiz_id=rid)
                registro = _registro_de_intento(raiz, gid)
                if os.path.lexists(registro) and leer_intento(registro):
                    registro.unlink()  # aceptacion completa interrumpida justo antes de retirar su registro
                informe.update(resultado="ya_importada", pasos=informe["pasos"] + ["ya_aceptada"])
                return informe
            _recuperar_restos(admin, raiz, gid, rid, informe)
            intento = secrets.token_hex(16)
            valor = f"{rid}:{intento}"
            escribir_exclusivo(_registro_de_intento(raiz, gid),
                               canonico({"intento": intento, "raiz": rid, "id": gid}))
            base = f"prep_{gid}_{intento[:16]}"
            admin.execute(f"CREATE DATABASE {_ident(base)} TEMPLATE template0 ENCODING 'UTF8'")
            creadas[base] = _oid(admin, base)
            marcar_base(admin, base, AJUSTE_IMPORTACION, valor)
            admin.execute(f"REVOKE ALL ON DATABASE {_ident(base)} FROM PUBLIC")
            url_prep = _url_con_base(destino.url_admin, base)
            fase("base_creada")
            _migrar(url_prep, manifiesto["esquema"]["revision_alembic"])
            with bl.conectar(url_prep) as c:
                if bl.huella_esquema(c) != manifiesto["esquema"]["huella"]:
                    raise ImportacionRechazada("esquema", "la huella del esquema migrado no es la del manifiesto")
                catalogo = bl.tablas(c)
                c.commit()
                informe["pasos"].append("esquema")
                fase("esquema")
                try:
                    bl.restaurar(c, paquete / "base", manifiesto["base"], catalogo)
                except GeneracionNoValida as error:
                    raise ImportacionRechazada("restauracion", str(error)) from error
                fase("filas_cargadas")
                c.commit()
            informe["pasos"].append("restauracion")
            prep_dir = ar.crear_propia(raiz / "preparacion" / gid, intento)
            for ruta in sorted(manifiesto["archivos"]):
                if ruta.startswith("archivos/") or ruta == COHERENCIA:
                    ar.copiar_verificado(paquete / ruta, prep_dir / ruta)
            for a in inv.PUBLICABLES:
                (prep_dir / "archivos" / a.nombre).mkdir(parents=True, exist_ok=True)
            for nombre in (MANIFIESTO, FIRMA):
                ar.copiar_verificado(paquete / nombre, prep_dir / nombre)
            fase("archivos")
            historico, cerrar = _historico_de(url_prep)
            try:
                recalculada = co.evaluar(prep_dir / "archivos", historico, juegos_de_la_base=manifiesto["juegos"])
            finally:
                cerrar()
            if recalculada["rechazos"] or recalculada["resumen"] != manifiesto["coherencia"]:
                raise ImportacionRechazada("coherencia", "la coherencia contra la base restaurada no es la sellada")
            informe["pasos"].append("coherencia")
            fase("coherencia")
            with bl.conectar(url_prep, autocommit=True) as c:
                c.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
                c.execute(f"GRANT USAGE ON SCHEMA public TO {_ident(destino.rol_lector)}")
                c.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {_ident(destino.rol_lector)}")
            admin.execute(f"GRANT CONNECT ON DATABASE {_ident(base)} TO {_ident(destino.rol_lector)}")
            admin.execute(f"ALTER DATABASE {_ident(base)} SET default_transaction_read_only = on")
            ar.solo_lectura(prep_dir, raiz / "preparacion", intento)
            fase("permisos")
            humo = consultas_en_proceso_aparte(_url_con_base(destino.url_lector, base), prep_dir / "archivos",
                                               raiz / "registro" / f"{gid}-consultas-{secrets.token_hex(4)}.json",
                                               esperado=consultas.esperado_de(
                                                   manifiesto["juegos"], leer_canonico(prep_dir / COHERENCIA)))
            informe["consultas"] = {k: humo[k] for k in ("total", "fallos", "contenido", "lecturas")}
            if humo["fallos"] or humo["lecturas"]["fuera_de_lo_declarado"]:
                raise ImportacionRechazada("consultas", "; ".join((humo["fallos"] +
                                                                  humo["lecturas"]["fuera_de_lo_declarado"])[:5]))
            informe["huellas_consultas"] = humo["rutas"]
            informe["pasos"].append("consultas")
            fase("consultas")
            aceptada = nombre_base(gid, True)
            if _oid(admin, base) != creadas[base]:
                raise ImportacionRechazada("aceptacion", "la base preparada fue sustituida durante la importacion")
            admin.execute(f"ALTER DATABASE {_ident(base)} RENAME TO {_ident(aceptada)}")
            creadas = {aceptada: creadas[base]}
            sha = sha256_archivo(prep_dir / MANIFIESTO)[1]
            from psycopg import sql
            admin.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(aceptada),
                                                                     sql.Literal(comentario(gid, sha))))
            fase("base_aceptada")
            ar.soltar_marca(prep_dir)
            os.rename(prep_dir, final_dir)
            prep_dir = None
            creadas = {}
            _registro_de_intento(raiz, gid).unlink()
            informe.update(resultado="aceptada", base=aceptada, carpeta=f"generaciones/{gid}", sha256_manifiesto=sha)
            informe["pasos"].append("aceptada")
            informe["registro"] = _registrar(raiz, gid, informe).name
            return informe
        except BaseException as error:
            paso, motivo = (error.paso, error.motivo) if isinstance(error, ImportacionRechazada) else \
                ("fallo_intermedio", f"{type(error).__name__}: {str(error)[:300]}")
            limpio = True
            for nombre, oid in creadas.items():
                try:
                    if not borrar_base_propia(admin, nombre, AJUSTE_IMPORTACION, valor, oid) and \
                            _existe_base(admin, nombre):
                        limpio = False
                        motivo += f" (no se borra {nombre}: sin prueba de propiedad)"
                except Exception as fallo:  # se informa; la base no es utilizable sin carpeta aceptada
                    limpio = False
                    motivo += f" (no se pudo borrar {nombre}: {type(fallo).__name__})"
            if prep_dir is not None or (intento and os.path.lexists(raiz / "preparacion" / (gid or "-"))):
                try:
                    ar.borrar_propia(raiz / "preparacion" / gid, raiz / "preparacion", intento)
                except Exception as fallo:
                    limpio = False
                    motivo += f" (no se pudo retirar preparacion/{gid}: {type(fallo).__name__}: {fallo})"
            if intento and limpio:
                registro = _registro_de_intento(raiz, gid)
                if os.path.lexists(registro):
                    registro.unlink()
            elif intento:
                informe["recuperacion"] = (f"queda preparacion/{gid}.intento: la proxima importacion de este id "
                                           "en esta raiz retira sus restos propios o explica cuales no puede")
            informe.update(resultado="rechazada", paso=paso, motivo=motivo)
            informe["registro"] = _registrar(raiz, gid or "sin-id", informe).name
            if isinstance(error, ImportacionRechazada):
                raise
            raise ImportacionRechazada(paso, motivo) from error
        finally:
            exclusion.__exit__()
    finally:
        admin.close()


def verificar_publicada(carpeta: Path, clave_publica: Path, admin=None, *, url_base: str | None = None,
                        raiz_id: str | None = None) -> dict:
    """Generacion ACEPTADA: firma e identidad del manifiesto, archivos exactos (sin `base/`, que esta en la
    base) y, si se da una conexion, la base `pub_<id>` con el comentario exacto (y, con `raiz_id`, importada
    por ESA raiz: una base del mismo id aceptada por otra raiz del servidor no se adopta)."""
    manifiesto = leer_canonico(carpeta / MANIFIESTO)
    publica, id_clave = firma.cargar_publica(clave_publica)
    if manifiesto.get("clave_firma") != id_clave:
        raise GeneracionNoValida("otra clave de firma")
    firma.verificar(publica, (carpeta / MANIFIESTO).read_bytes(), (carpeta / FIRMA).read_text(encoding="ascii"))
    if not es_id(manifiesto.get("id", "")) or id_de(manifiesto) != manifiesto["id"] or carpeta.name != manifiesto["id"]:
        raise GeneracionNoValida("identidad de la generacion no valida")
    esperados = {r: v for r, v in manifiesto["archivos"].items() if not r.startswith("base/")}
    reales = set()
    for raiz, subcarpetas, nombres in os.walk(carpeta, followlinks=False):
        for nombre in subcarpetas + nombres:
            if (Path(raiz) / nombre).is_symlink():
                raise GeneracionNoValida("enlace simbolico en la generacion")
        reales |= {(Path(raiz) / n).relative_to(carpeta).as_posix() for n in nombres}
    if reales - {MANIFIESTO, FIRMA} != set(esperados):
        raise GeneracionNoValida("archivos de la generacion distintos de los declarados")
    for ruta, v in esperados.items():
        if sha256_archivo(carpeta / ruta) != (v["bytes"], v["sha256"]):
            raise GeneracionNoValida(f"{ruta}: alterado")
    sha = sha256_archivo(carpeta / MANIFIESTO)[1]
    if admin is not None:
        nombre = nombre_base(manifiesto["id"], True)
        fila = admin.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s",
                             (nombre,)).fetchone()
        if fila is None or fila[0] != comentario(manifiesto["id"], sha):
            raise GeneracionNoValida("la base de la generacion no existe o no corresponde a su manifiesto")
        if raiz_id is not None and not (ajuste_de(admin, nombre, AJUSTE_IMPORTACION) or "").startswith(raiz_id + ":"):
            raise GeneracionNoValida("generacion_aceptada_en_otra_raiz: la base no fue importada por esta raiz")
    return {"manifiesto": manifiesto, "sha256_manifiesto": sha}


def activar(raiz: Path, gid: str, clave_publica: Path, url_admin: str) -> dict:
    """Escribe `activa.json` (renombrado atomico) tras verificar la generacion aceptada y su base. No arranca ni
    para procesos: el par API/pasarela de esa generacion se arranca con su configuracion inmutable (E10.5, D11).
    Un fallo deja `activa.json` como estaba."""
    if not es_id(gid):
        raise GeneracionNoValida("id no valido")
    with bl.conectar(_url_con_base(url_admin, "postgres"), autocommit=True) as admin:
        datos = verificar_publicada(raiz / "generaciones" / gid, clave_publica, admin,
                                    raiz_id=id_de_raiz(raiz, crear=False))
    anterior = None
    if (raiz / "activa.json").exists():
        anterior = leer_canonico(raiz / "activa.json").get("id")
    registro = {"id": gid, "base": nombre_base(gid, True), "carpeta": f"generaciones/{gid}",
                "sha256_manifiesto": datos["sha256_manifiesto"], "anterior": anterior,
                "activada_en": dt.datetime.now(dt.timezone.utc).isoformat()}
    temporal = raiz / f".activa.{secrets.token_hex(8)}.tmp"
    escribir_exclusivo(temporal, canonico(registro))
    os.replace(temporal, raiz / "activa.json")
    return registro
