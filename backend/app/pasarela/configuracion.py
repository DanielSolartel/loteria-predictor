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

Perfil PRIVADO (Fase 10, E10.2; `PASARELA_PERFIL=privado`, `docs/fase10_consulta_privada.md`).
Detras de un proxy autenticado (TLS con certificado de cliente por persona). No
arranca si falta cualquiera de estos valores o si no es valido:

- `PASARELA_PROXIES_FIABLES`: IP EXACTAS del socket del proxy (sin redes, sin
  la direccion sin especificar). Cualquier otro cliente recibe 403; ni
  `X-Forwarded-For` ni una IP privada cualquiera bastan.
- `PASARELA_SECRETO_PROXY_ARCHIVO`: secreto compartido con el proxy (archivo
  montado en ejecucion); el proxy lo anade en `X-Consulta-Ingreso` y la
  pasarela lo compara en tiempo constante.
- `PASARELA_CLAVE_API_ARCHIVO`: la clave de API (archivo); `PASARELA_CLAVE_API`
  debe quedar vacia.
- `PASARELA_API_URL`: `http://` sobre una IP literal (sin DNS) con puerto.
- `PASARELA_HOSTS` (`nombre:puerto`) y `PASARELA_ORIGENES` (`https://nombre:puerto`)
  exactos, sin comodines; `PASARELA_CONSOLA_LOCAL` vacio (D4: la consola solo en
  el PC de Daniel).
- Cuotas: `PASARELA_FICHAS_PERSONA_POR_MINUTO`, `PASARELA_FICHAS_AGREGADAS_POR_MINUTO`
  y `PASARELA_MAX_PERSONAS` (con los costes de la API).
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
_FORMATO_SECRETO = re.compile(r"[\x21-\x7e]{32,256}")
_NOMBRE_DNS = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
_HOST_PRIVADO = re.compile(_NOMBRE_DNS + r":[0-9]{1,5}")
_ORIGEN_PRIVADO = re.compile(r"https://" + _NOMBRE_DNS + r":[0-9]{1,5}")
PERFILES = frozenset({"local", "privado"})


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
    # Fase 10 (E10.2): perfil privado
    perfil: str = "local"
    proxies_fiables: str = ""
    secreto_proxy_archivo: str = ""
    clave_api_archivo: str = ""
    fichas_persona_por_minuto: int = 30
    fichas_agregadas_por_minuto: int = 90
    max_personas: int = 64


@dataclasses.dataclass(frozen=True)
class Destino:
    host: str
    puerto: int

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.puerto}"


@dataclasses.dataclass(frozen=True)
class PerfilPrivado:
    """Ingreso fiable y cuotas del perfil privado (Fase 10, E10.2)."""
    proxies: frozenset[str]
    secreto: SecretStr = dataclasses.field(repr=False)
    fichas_persona: int = 30
    fichas_agregadas: int = 90
    max_personas: int = 64


@dataclasses.dataclass(frozen=True)
class ConfiguracionPasarela:
    destino: Destino
    clave: SecretStr = dataclasses.field(repr=False)
    hosts: frozenset[str]
    origenes: frozenset[str]
    dist: Path
    consola_local: str | None = None
    privado: PerfilPrivado | None = None

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


def _leer_secreto(ruta: str, nombre: str, formato: re.Pattern) -> SecretStr:
    if not ruta:
        raise ConfiguracionNoValida(f"{nombre}: obligatorio en el perfil privado")
    try:
        texto = Path(ruta).read_bytes()[:4096].decode("ascii").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise ConfiguracionNoValida(f"{nombre}: no se puede leer el archivo") from error
    if not formato.fullmatch(texto):
        raise ConfiguracionNoValida(f"{nombre}: contenido no valido")
    return SecretStr(texto)


def leer_proxies(texto: str) -> frozenset[str]:
    proxies = set()
    for valor in (v.strip() for v in texto.split(",") if v.strip()):
        try:
            ip = ipaddress.ip_address(valor)
        except ValueError as error:
            raise ConfiguracionNoValida("PASARELA_PROXIES_FIABLES: solo IP exactas, sin redes") from error
        if ip.is_unspecified or ip.is_multicast:
            raise ConfiguracionNoValida("PASARELA_PROXIES_FIABLES: direccion no admitida")
        proxies.add(str(ip))
    if not proxies:
        raise ConfiguracionNoValida("PASARELA_PROXIES_FIABLES: al menos una IP exacta")
    return frozenset(proxies)


def leer_destino_privado(texto: str) -> Destino:
    try:
        partes = urlsplit(texto.strip())
        puerto = partes.port
        ip = ipaddress.ip_address(partes.hostname or "")
    except ValueError as error:
        raise ConfiguracionNoValida("PASARELA_API_URL: http:// sobre una IP literal con puerto") from error
    if (partes.scheme != "http" or partes.username is not None or partes.password is not None or partes.query
            or partes.fragment or partes.path not in ("", "/") or "@" in partes.netloc or puerto is None
            or not 1 <= puerto <= 65535 or ip.is_unspecified or ip.is_multicast):
        raise ConfiguracionNoValida("PASARELA_API_URL: http:// sobre una IP literal con puerto, sin ruta ni credenciales")
    return Destino(str(ip), puerto)


def _lista_exacta(texto: str, patron: re.Pattern, nombre: str) -> frozenset[str]:
    valores = set()
    for valor in (v.strip() for v in texto.split(",") if v.strip()):
        if not patron.fullmatch(valor) or not 1 <= int(valor.rsplit(":", 1)[1]) <= 65535:
            raise ConfiguracionNoValida(f"{nombre}: valores exactos en minusculas, sin comodines")
        valores.add(valor)
    if not valores:
        raise ConfiguracionNoValida(f"{nombre}: al menos un valor")
    return frozenset(valores)


def desde_ajustes_privados(ajustes: AjustesPasarela) -> ConfiguracionPasarela:
    if ajustes.clave_api.get_secret_value():
        raise ConfiguracionNoValida("PASARELA_CLAVE_API: en el perfil privado use PASARELA_CLAVE_API_ARCHIVO")
    if ajustes.consola_local.strip():
        raise ConfiguracionNoValida("PASARELA_CONSOLA_LOCAL: no se admite en el perfil privado (D4)")
    if not 5 <= ajustes.fichas_persona_por_minuto <= 100_000:
        raise ConfiguracionNoValida("PASARELA_FICHAS_PERSONA_POR_MINUTO: entre 5 (coste maximo) y 100000")
    if not ajustes.fichas_persona_por_minuto <= ajustes.fichas_agregadas_por_minuto <= 1_000_000:
        raise ConfiguracionNoValida("PASARELA_FICHAS_AGREGADAS_POR_MINUTO: no menor que la cuota por persona")
    if not 2 <= ajustes.max_personas <= 10_000:
        raise ConfiguracionNoValida("PASARELA_MAX_PERSONAS: entre 2 y 10000")
    privado = PerfilPrivado(proxies=leer_proxies(ajustes.proxies_fiables),
                            secreto=_leer_secreto(ajustes.secreto_proxy_archivo, "PASARELA_SECRETO_PROXY_ARCHIVO",
                                                  _FORMATO_SECRETO),
                            fichas_persona=ajustes.fichas_persona_por_minuto,
                            fichas_agregadas=ajustes.fichas_agregadas_por_minuto, max_personas=ajustes.max_personas)
    clave = _leer_secreto(ajustes.clave_api_archivo, "PASARELA_CLAVE_API_ARCHIVO", _FORMATO_CLAVE)
    if clave.get_secret_value() == privado.secreto.get_secret_value():
        raise ConfiguracionNoValida("la clave de API y el secreto del proxy deben ser distintos")
    return ConfiguracionPasarela(destino=leer_destino_privado(ajustes.api_url), clave=clave,
                                 hosts=_lista_exacta(ajustes.hosts, _HOST_PRIVADO, "PASARELA_HOSTS"),
                                 origenes=_lista_exacta(ajustes.origenes, _ORIGEN_PRIVADO, "PASARELA_ORIGENES"),
                                 dist=Path(ajustes.dist).resolve() if ajustes.dist else DIST_POR_DEFECTO,
                                 consola_local=None, privado=privado)


def desde_ajustes(ajustes: AjustesPasarela) -> ConfiguracionPasarela:
    if ajustes.perfil not in PERFILES:
        raise ConfiguracionNoValida("PASARELA_PERFIL: local o privado")
    if ajustes.perfil == "privado":
        return desde_ajustes_privados(ajustes)
    if ajustes.proxies_fiables.strip() or ajustes.secreto_proxy_archivo or ajustes.clave_api_archivo:
        raise ConfiguracionNoValida("los ajustes del perfil privado exigen PASARELA_PERFIL=privado")
    return ConfiguracionPasarela(destino=leer_destino(ajustes.api_url), clave=ajustes.clave_api,
                                 hosts=leer_hosts(ajustes.hosts), origenes=leer_origenes(ajustes.origenes),
                                 dist=Path(ajustes.dist).resolve() if ajustes.dist else DIST_POR_DEFECTO,
                                 consola_local=leer_consola(ajustes.consola_local))
