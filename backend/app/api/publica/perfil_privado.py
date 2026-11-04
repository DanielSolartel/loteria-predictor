"""
Perfil PRIVADO de la API publica (Fase 10, E10.2): reglas del punto de entrada
`app.api.publica.privada:app`, separado de `app.main` y del arranque local
(`app.api.publica.aplicacion:app`, que no cambia):

    `uvicorn app.api.publica.privada:app --host <IP interna> --port 8010 --workers 1 --no-access-log --no-proxy-headers`

Antes de importar la configuracion lee los secretos de ARCHIVOS montados en
tiempo de ejecucion (nunca de la imagen ni del entorno del contenedor):

- `DATABASE_URL_ARCHIVO`: URL del rol LECTOR de PostgreSQL (una linea);
- `API_PUBLICA_CLAVES_ARCHIVO`: huellas `id:sha256:<64 hex>` (una por linea,
  `#` comenta). Varias huellas a la vez permiten rotar con solapamiento.

Si `DATABASE_URL` o `API_PUBLICA_CLAVES` llegan ademas por el entorno, no
arranca (una sola fuente). Tampoco arranca, sin servir nada, si falta
cualquiera de estas condiciones (cerrado ante el fallo):

- huellas validas (al menos una) y base PostgreSQL;
- frontera explicita (`API_PUBLICA_HOSTS` y `API_PUBLICA_CLIENTES`), sin CORS;
- limites de recursos: `API_PUBLICA_CONCURRENCIA_COSTOSAS` > 0,
  `BASE_TIEMPO_MAXIMO_CONSULTA_MS` > 0 y `BASE_TIEMPO_MAXIMO_INACTIVA_MS` > 0;
- los almacenes de consulta de la generacion presentes como directorios
  legibles (laboratorio, carteras, predicciones y pronosticos): un montaje
  ausente no se sirve como una respuesta vacia aprobada;
- un usuario distinto de root (en POSIX).

Las claves y la URL se leen UNA vez: rotar o revocar exige reiniciar este
proceso (sin promesa de cero cortes antes de D11).

GENERACION (Fase 10, E10.4). Con `GENERACION_DIRECTORIO=<raiz>/generaciones/<id>` y
`GENERACION_CLAVE_PUBLICA=<archivo>`, el proceso queda ligado a UNA generacion aceptada por el importador:
- los cuatro `DIRECTORIO_*` de consulta se fijan a `<generacion>/archivos/<almacen>` (si ya llegan por el
  entorno con otro valor, no arranca) y ningun otro `DIRECTORIO_*` puede apuntar dentro de la generacion;
- al arrancar se verifican la firma Ed25519 y la identidad del manifiesto y cada archivo de la generacion
  (tamano y SHA-256, sin archivos de mas ni enlaces);
- la base de `DATABASE_URL_ARCHIVO` debe ser `pub_<id>` con el comentario que escribio el importador
  (`loteria-generacion:<id>:<sha256 del manifiesto>`) y en solo lectura por defecto;
- CODIGO (E104-GEN-02): la huella de `app/` que declara el manifiesto debe ser la que este proceso recalcula
  sobre sus PROPIOS archivos (`generaciones.codigo.huella_app`, valida en la imagen minima, que no lleva
  `alembic/`), y la revision del esquema del manifiesto, la que exige este codigo (`REVISION_ESQUEMA`) y la de
  la tabla `alembic_version` de la base conectada deben ser la misma.
Si algo no coincide, no arranca (codigo 3). Nunca se cambia la generacion bajo un proceso en marcha: otra
generacion es otro proceso (E10.5, D11). Sin `GENERACION_DIRECTORIO` el perfil se comporta como en E10.2.
"""
from __future__ import annotations

import os
from pathlib import Path

SECRETOS = (("DATABASE_URL", "DATABASE_URL_ARCHIVO"), ("API_PUBLICA_CLAVES", "API_PUBLICA_CLAVES_ARCHIVO"))
ALMACENES_DE_CONSULTA = ("directorio_laboratorio_modelos", "directorio_carteras_modelos",
                         "directorio_predicciones_modelos", "directorio_pronosticos_experimentales")
MAXIMO_SECRETO = 64 * 1024


class PerfilPrivadoNoValido(RuntimeError):
    """El perfil privado no arranca; el mensaje nunca incluye un secreto."""


def _leer_archivo(ruta: str, nombre: str) -> str:
    try:
        datos = Path(ruta).read_bytes()
    except OSError as error:
        raise PerfilPrivadoNoValido(f"{nombre}: no se puede leer el archivo") from error
    if len(datos) > MAXIMO_SECRETO:
        raise PerfilPrivadoNoValido(f"{nombre}: archivo demasiado grande")
    try:
        texto = datos.decode("ascii")
    except UnicodeDecodeError as error:
        raise PerfilPrivadoNoValido(f"{nombre}: solo ASCII") from error
    lineas = [l.strip() for l in texto.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not lineas:
        raise PerfilPrivadoNoValido(f"{nombre}: archivo vacio")
    return ",".join(lineas)


def cargar_secretos(entorno=os.environ) -> None:
    for variable, archivo in SECRETOS:
        if entorno.get(variable):
            raise PerfilPrivadoNoValido(f"{variable} no se admite en el entorno del perfil privado; use {archivo}")
        ruta = entorno.get(archivo, "")
        if not ruta:
            raise PerfilPrivadoNoValido(f"{archivo} es obligatorio en el perfil privado")
        valor = _leer_archivo(ruta, archivo)
        if variable == "DATABASE_URL" and "," in valor:
            raise PerfilPrivadoNoValido(f"{archivo}: una sola URL")
        entorno[variable] = valor


GENERACION, GENERACION_CLAVE = "GENERACION_DIRECTORIO", "GENERACION_CLAVE_PUBLICA"


def vincular_generacion(entorno=os.environ) -> Path | None:
    """Fija los almacenes de consulta a la generacion (antes de leer la configuracion)."""
    ruta = entorno.get(GENERACION, "")
    if not ruta:
        return None
    from app.infrastructure.generaciones import inventario as inv

    carpeta = Path(ruta)
    if carpeta.is_symlink() or not carpeta.is_dir():
        raise PerfilPrivadoNoValido(f"{GENERACION}: no es una carpeta de generacion")
    carpeta = carpeta.resolve()
    if not entorno.get(GENERACION_CLAVE):
        raise PerfilPrivadoNoValido(f"{GENERACION_CLAVE} es obligatorio con {GENERACION}")
    for almacen in inv.ALMACENES:
        variable = almacen.ajuste.upper()
        if almacen.clase == inv.PUBLICABLE:
            esperado = carpeta / "archivos" / almacen.nombre
            if entorno.get(variable) and Path(entorno[variable]).resolve() != esperado:
                raise PerfilPrivadoNoValido(f"{variable} no coincide con la generacion")
            entorno[variable] = str(esperado)
        elif entorno.get(variable):
            otro = Path(entorno[variable]).resolve()
            if otro == carpeta or carpeta in otro.parents:
                raise PerfilPrivadoNoValido(f"{variable} no puede apuntar dentro de la generacion")
    return carpeta


def comprobar_generacion(carpeta: Path, clave_publica: Path, engine) -> dict:
    """Firma, identidad y archivos de la generacion; la base conectada es la suya y es de solo lectura."""
    from sqlalchemy import text

    from app.infrastructure.generaciones import importacion as im
    from app.infrastructure.generaciones.formato import GeneracionNoValida

    try:
        datos = im.verificar_publicada(carpeta, clave_publica)
    except (GeneracionNoValida, OSError, ValueError) as error:
        raise PerfilPrivadoNoValido(f"{GENERACION}: generacion no valida ({error})") from None
    gid = datos["manifiesto"]["id"]
    from app.infrastructure.generaciones import codigo

    declarado = datos["manifiesto"].get("codigo") or {}
    propia, _ = codigo.huella_app(codigo.raiz_de_esta_app())
    if declarado.get("huella_app") != propia:
        raise PerfilPrivadoNoValido(f"{GENERACION}: la generacion {gid} es de otro codigo de la API (huella de app/)")
    revision = (datos["manifiesto"].get("esquema") or {}).get("revision_alembic")
    if revision != codigo.REVISION_ESQUEMA or declarado.get("revision_alembic") != codigo.REVISION_ESQUEMA:
        raise PerfilPrivadoNoValido(f"{GENERACION}: la generacion {gid} es de otra revision del esquema")
    try:
        with engine.connect() as c:
            base, nota, solo_lectura = c.execute(text(
                "SELECT current_database(), shobj_description(d.oid, 'pg_database'), "
                "current_setting('default_transaction_read_only') FROM pg_database d "
                "WHERE d.datname = current_database()")).one()
            revisiones = [r[0] for r in c.execute(text("SELECT version_num FROM alembic_version")).all()]
    except Exception:  # el motivo no se repite: podria contener la URL
        raise PerfilPrivadoNoValido(f"{GENERACION}: no se pudo comprobar la base de la generacion") from None
    if revisiones != [codigo.REVISION_ESQUEMA]:
        raise PerfilPrivadoNoValido(f"{GENERACION}: la base conectada no esta en la revision {codigo.REVISION_ESQUEMA}")
    if base != im.nombre_base(gid, True) or nota != im.comentario(gid, datos["sha256_manifiesto"]):
        raise PerfilPrivadoNoValido(f"{GENERACION}: la base conectada no es la de la generacion {gid}")
    if solo_lectura != "on":
        raise PerfilPrivadoNoValido(f"{GENERACION}: la base de la generacion no es de solo lectura por defecto")
    return {"id": gid, "sha256_manifiesto": datos["sha256_manifiesto"], "huella_app": propia,
            "revision_esquema": codigo.REVISION_ESQUEMA}


def comprobar(settings, configuracion, *, es_root: bool | None = None) -> None:
    """Condiciones del perfil privado sobre la configuracion YA leida."""
    from sqlalchemy.engine import make_url

    faltas = []
    if not configuracion.abierta:
        faltas.append("API_PUBLICA_CLAVES_ARCHIVO sin huellas validas")
    try:
        postgres = make_url(settings.database_url).get_backend_name() == "postgresql"
    except Exception:  # URL no valida: el motivo no se repite (podria contener la contrasena)
        postgres = False
    if not postgres:
        faltas.append("DATABASE_URL_ARCHIVO debe ser una URL de PostgreSQL")
    if not configuracion.hosts or not configuracion.clientes:
        faltas.append("API_PUBLICA_HOSTS y API_PUBLICA_CLIENTES son obligatorios")
    if configuracion.cors_origenes:
        faltas.append("API_PUBLICA_CORS_ORIGENES debe quedar vacio (la pasarela es del mismo origen)")
    if configuracion.concurrencia_costosas <= 0:
        faltas.append("API_PUBLICA_CONCURRENCIA_COSTOSAS debe ser > 0")
    if settings.base_tiempo_maximo_consulta_ms <= 0 or settings.base_tiempo_maximo_inactiva_ms <= 0:
        faltas.append("BASE_TIEMPO_MAXIMO_CONSULTA_MS y BASE_TIEMPO_MAXIMO_INACTIVA_MS deben ser > 0")
    for nombre in ALMACENES_DE_CONSULTA:
        ruta = Path(getattr(settings, nombre))
        if not ruta.is_dir() or not os.access(ruta, os.R_OK | os.X_OK):
            faltas.append(f"{nombre.upper()}: almacen de consulta ausente o ilegible")
    if es_root is None:
        es_root = hasattr(os, "geteuid") and os.geteuid() == 0
    if es_root:
        faltas.append("el perfil privado no se ejecuta como root")
    if faltas:
        raise PerfilPrivadoNoValido("perfil privado no valido: " + "; ".join(faltas))


def crear_app_privada():
    cargar_secretos()
    generacion = vincular_generacion()
    from app.api.publica import aplicacion
    from app.core.config import get_settings

    comprobar(get_settings(), aplicacion.app.state.configuracion)
    aplicacion.app.state.generacion = None
    if generacion is not None:
        from app.infrastructure.db import session as db_session

        aplicacion.app.state.generacion = comprobar_generacion(generacion, Path(os.environ[GENERACION_CLAVE]),
                                                               db_session.engine)
    return aplicacion.app
