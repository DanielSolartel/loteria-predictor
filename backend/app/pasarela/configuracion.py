"""Configuracion de la pasarela (Fase 9.1), solo del servidor.

Se lee una vez al arrancar, del entorno o del archivo privado
`pasarela.privado.env` (en `backend/`, fuera de Git: `*.privado.env`):

- `PASARELA_CLAVE_API`: la clave en claro emitida para el frontend. La API solo
  conoce su huella (`API_PUBLICA_CLAVES`). Sin clave valida la pasarela arranca
  CERRADA: sirve la SPA y responde 503 a toda consulta.
- `PASARELA_API_URL`: destino fijo, `http://` sobre una IP loopback con puerto y
  sin credenciales, ruta, consulta ni fragmento (por defecto
  `http://127.0.0.1:8010`).
- `PASARELA_HOSTS` y `PASARELA_ORIGENES`: valores admitidos de `Host` y `Origin`
  (por defecto los de la propia pasarela en el puerto 8020). El modo Vite los
  amplia de forma explicita con su puerto; nunca con comodines.
- `PASARELA_DIST`: carpeta de la SPA compilada (por defecto `frontend/dist`).
- `PASARELA_CONSOLA_LOCAL`: enlace opcional a la consola HTMX local; vacio
  (desactivado) por defecto y validado como `http://` loopback.

Un valor no valido de destino, hosts, origenes o enlace impide arrancar.
"""
from __future__ import annotations

import dataclasses
import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_DEL_REPOSITORIO = Path(__file__).resolve().parents[3]
DIST_POR_DEFECTO = RAIZ_DEL_REPOSITORIO / "frontend" / "dist"
ARCHIVO_PRIVADO = "pasarela.privado.env"
_FORMATO_CLAVE = re.compile(r"[\x21-\x7e]{32,256}")
_NOMBRE_LOCAL = {"localhost"}


class ConfiguracionNoValida(ValueError):
    """La configuracion impide arrancar; el mensaje no incluye la clave."""


class AjustesPasarela(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PASARELA_", env_file=ARCHIVO_PRIVADO, extra="ignore")

    clave_api: SecretStr = SecretStr("")
    api_url: str = "http://127.0.0.1:8010"
    hosts: str = "127.0.0.1:8020,localhost:8020"
    origenes: str = "http://127.0.0.1:8020,http://localhost:8020"
    dist: str = ""
    consola_local: str = ""


@dataclasses.dataclass(frozen=True)
class Destino:
    host: str
    puerto: int

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.puerto}"


@dataclasses.dataclass(frozen=True)
class ConfiguracionPasarela:
    destino: Destino
    clave: SecretStr = dataclasses.field(repr=False)
    hosts: frozenset[str]
    origenes: frozenset[str]
    dist: Path
    consola_local: str | None = None

    @property
    def abierta(self) -> bool:
        return _FORMATO_CLAVE.fullmatch(self.clave.get_secret_value()) is not None


def _es_loopback(host: str, *, admitir_nombre: bool) -> bool:
    if admitir_nombre and host in _NOMBRE_LOCAL:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _url_local(texto: str, nombre: str, *, admitir_nombre: bool) -> tuple[str, int, str]:
    try:
        partes = urlsplit(texto)
        puerto = partes.port
    except ValueError as error:
        raise ConfiguracionNoValida(f"{nombre}: URL no valida") from error
    if partes.scheme != "http" or partes.username is not None or partes.password is not None:
        raise ConfiguracionNoValida(f"{nombre}: debe ser http:// sin credenciales")
    if partes.query or partes.fragment or partes.path not in ("", "/") or "@" in partes.netloc:
        raise ConfiguracionNoValida(f"{nombre}: sin ruta, consulta ni fragmento")
    host = partes.hostname or ""
    if puerto is None or not 1 <= puerto <= 65535 or not _es_loopback(host, admitir_nombre=admitir_nombre):
        raise ConfiguracionNoValida(f"{nombre}: debe ser una direccion loopback con puerto explicito")
    return host, puerto, f"http://{partes.netloc}"


def leer_destino(texto: str) -> Destino:
    host, puerto, _ = _url_local(texto.strip(), "PASARELA_API_URL", admitir_nombre=False)
    return Destino(host, puerto)


def leer_hosts(texto: str) -> frozenset[str]:
    hosts = set()
    for valor in (v.strip() for v in texto.split(",") if v.strip()):
        if not re.fullmatch(r"(localhost|127\.0\.0\.1|\[::1\]):[0-9]{1,5}", valor) or not \
                1 <= int(valor.rsplit(":", 1)[1]) <= 65535:
            raise ConfiguracionNoValida("PASARELA_HOSTS: cada valor debe ser host:puerto local (sin comodines)")
        hosts.add(valor)
    if not hosts:
        raise ConfiguracionNoValida("PASARELA_HOSTS: al menos un host:puerto local")
    return frozenset(hosts)


def leer_origenes(texto: str) -> frozenset[str]:
    origenes = set()
    for valor in (v.strip() for v in texto.split(",") if v.strip()):
        _, _, origen = _url_local(valor, "PASARELA_ORIGENES", admitir_nombre=True)
        if valor.rstrip("/") != origen:
            raise ConfiguracionNoValida("PASARELA_ORIGENES: origen exacto http://host:puerto")
        origenes.add(origen)
    if not origenes:
        raise ConfiguracionNoValida("PASARELA_ORIGENES: al menos un origen local")
    return frozenset(origenes)


def leer_consola(texto: str) -> str | None:
    texto = texto.strip()
    if not texto:
        return None
    _, _, origen = _url_local(texto, "PASARELA_CONSOLA_LOCAL", admitir_nombre=True)
    return origen + "/"


def desde_ajustes(ajustes: AjustesPasarela) -> ConfiguracionPasarela:
    return ConfiguracionPasarela(destino=leer_destino(ajustes.api_url), clave=ajustes.clave_api,
                                 hosts=leer_hosts(ajustes.hosts), origenes=leer_origenes(ajustes.origenes),
                                 dist=Path(ajustes.dist).resolve() if ajustes.dist else DIST_POR_DEFECTO,
                                 consola_local=leer_consola(ajustes.consola_local))
