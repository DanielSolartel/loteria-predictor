"""Configuracion de la API publica, leida una vez al construir la aplicacion.

Las claves se configuran como HUELLAS SHA-256 (`id:sha256:<64 hex>`, separadas
por comas), nunca en claro. Sin claves predeterminadas: si la lista falta o
cualquier entrada no es valida, la API queda CERRADA (503 en toda consulta
protegida). Limites o CORS no validos impiden arrancar: `*` no se admite."""
from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass

_IDENTIFICADOR = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
_HUELLA = re.compile(r"[0-9a-f]{64}")
_ORIGEN = re.compile(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?")
_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
                   r"|[0-9]{1,3}(?:\.[0-9]{1,3}){3}|\[[0-9a-f:]+\]):[0-9]{1,5}")
HUELLA_VACIA = hashlib.sha256(b"").hexdigest()
COSTE_MAXIMO = 5
"""Fichas de la consulta mas costosa; el limite por clave no puede ser menor."""


class ConfiguracionNoValida(ValueError):
    """Limites u origenes CORS no validos: la aplicacion no arranca."""


@dataclass(frozen=True)
class ClaveConfigurada:
    identificador: str
    huella: bytes


@dataclass(frozen=True)
class ConfiguracionPublica:
    claves: tuple[ClaveConfigurada, ...]
    fichas_por_minuto: int = 60
    fichas_por_minuto_ip: int = 120
    max_clientes_ip: int = 1024
    cors_origenes: tuple[str, ...] = ()
    documentacion: bool = True
    # Fase 10 (E10.2). Vacios / 0: sin cambio respecto del modo local.
    hosts: frozenset[str] = frozenset()
    clientes: frozenset[str] = frozenset()
    concurrencia_costosas: int = 0
    espera_costosas: float = 0.5

    @property
    def abierta(self) -> bool:
        return bool(self.claves)


def leer_claves(texto: str | None) -> tuple[ClaveConfigurada, ...]:
    """Tupla vacia si falta la configuracion o si alguna entrada no es valida
    (identificador, prefijo `sha256`, huella hexadecimal, huella de la cadena
    vacia o duplicados): con una entrada erronea no se admite ninguna."""
    entradas = [e.strip() for e in (texto or "").split(",") if e.strip()]
    claves: list[ClaveConfigurada] = []
    for entrada in entradas:
        partes = entrada.split(":")
        if (len(partes) != 3 or partes[1] != "sha256" or not _IDENTIFICADOR.fullmatch(partes[0])
                or not _HUELLA.fullmatch(partes[2]) or partes[2] == HUELLA_VACIA):
            return ()
        claves.append(ClaveConfigurada(partes[0], bytes.fromhex(partes[2])))
    if len({c.identificador for c in claves}) != len(claves) or len({c.huella for c in claves}) != len(claves):
        return ()
    return tuple(claves)


def leer_origenes(texto: str | None) -> tuple[str, ...]:
    origenes = tuple(o.strip().rstrip("/") for o in (texto or "").split(",") if o.strip())
    for origen in origenes:
        if not _ORIGEN.fullmatch(origen):
            raise ConfiguracionNoValida("API_PUBLICA_CORS_ORIGENES solo admite origenes explicitos "
                                        "http(s)://host[:puerto]; '*' no se admite")
    return origenes


def leer_hosts(texto: str | None) -> frozenset[str]:
    """Valores exactos de `Host` (`host:puerto`); sin comodines ni puertos fuera de rango."""
    hosts = set()
    for valor in (v.strip().lower() for v in (texto or "").split(",") if v.strip()):
        if not _HOST.fullmatch(valor) or not 1 <= int(valor.rsplit(":", 1)[1]) <= 65535:
            raise ConfiguracionNoValida("API_PUBLICA_HOSTS: cada valor debe ser host:puerto exacto (sin comodines)")
        hosts.add(valor)
    return frozenset(hosts)


def leer_clientes(texto: str | None) -> frozenset[str]:
    """IP exactas del socket admitidas; no se aceptan redes, la direccion sin especificar ni multidifusion."""
    clientes = set()
    for valor in (v.strip() for v in (texto or "").split(",") if v.strip()):
        try:
            ip = ipaddress.ip_address(valor)
        except ValueError as error:
            raise ConfiguracionNoValida("API_PUBLICA_CLIENTES: solo direcciones IP exactas, sin redes") from error
        if ip.is_unspecified or ip.is_multicast:
            raise ConfiguracionNoValida("API_PUBLICA_CLIENTES: direccion no admitida")
        clientes.add(str(ip))
    return frozenset(clientes)


def validar(configuracion: ConfiguracionPublica) -> ConfiguracionPublica:
    if not COSTE_MAXIMO <= configuracion.fichas_por_minuto <= 100_000:
        raise ConfiguracionNoValida(f"API_PUBLICA_FICHAS_POR_MINUTO debe estar entre {COSTE_MAXIMO} y 100000")
    if not 1 <= configuracion.fichas_por_minuto_ip <= 100_000:
        raise ConfiguracionNoValida("API_PUBLICA_FICHAS_POR_MINUTO_IP debe estar entre 1 y 100000")
    if not 16 <= configuracion.max_clientes_ip <= 1_000_000:
        raise ConfiguracionNoValida("API_PUBLICA_MAX_CLIENTES_IP debe estar entre 16 y 1000000")
    if bool(configuracion.hosts) != bool(configuracion.clientes):
        raise ConfiguracionNoValida("API_PUBLICA_HOSTS y API_PUBLICA_CLIENTES van juntos (frontera privada)")
    if not 0 <= configuracion.concurrencia_costosas <= 64:
        raise ConfiguracionNoValida("API_PUBLICA_CONCURRENCIA_COSTOSAS debe estar entre 0 (sin limite) y 64")
    if not 0 < configuracion.espera_costosas <= 30:
        raise ConfiguracionNoValida("API_PUBLICA_ESPERA_COSTOSAS debe estar entre 0 y 30 segundos")
    return configuracion


def desde_settings(settings) -> ConfiguracionPublica:
    return validar(ConfiguracionPublica(
        claves=leer_claves(settings.api_publica_claves),
        fichas_por_minuto=settings.api_publica_fichas_por_minuto,
        fichas_por_minuto_ip=settings.api_publica_fichas_por_minuto_ip,
        max_clientes_ip=settings.api_publica_max_clientes_ip,
        cors_origenes=leer_origenes(settings.api_publica_cors_origenes),
        documentacion=settings.api_publica_documentacion,
        hosts=leer_hosts(settings.api_publica_hosts),
        clientes=leer_clientes(settings.api_publica_clientes),
        concurrencia_costosas=settings.api_publica_concurrencia_costosas,
        espera_costosas=settings.api_publica_espera_costosas))
