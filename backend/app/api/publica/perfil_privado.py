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
    from app.api.publica import aplicacion
    from app.core.config import get_settings

    comprobar(get_settings(), aplicacion.app.state.configuracion)
    return aplicacion.app
