"""Planes inmutables; solo referencias a secretos, nunca su contenido."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

PRIVADAS = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


class Rechazo(ValueError):
    """Entrada o transición no admitida (el mensaje no incluye datos de configuración)."""


def canonico(valor: object) -> bytes:
    return (json.dumps(valor, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def json_estricto(datos: bytes, maximo: int = 262144):
    def pares(elementos):
        resultado = {}
        for clave, valor in elementos:
            if clave in resultado:
                raise Rechazo("json_claves_repetidas")
            resultado[clave] = valor
        return resultado
    if len(datos) > maximo:
        raise Rechazo("json_demasiado_grande")
    try:
        return json.loads(datos, object_pairs_hook=pares,
                          parse_constant=lambda _: (_ for _ in ()).throw(Rechazo("json_no_finito")))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise Rechazo("json_no_valido") from error


def huella(valor: object) -> str:
    return hashlib.sha256(canonico(valor)).hexdigest()


def hexadecimal(valor: object, longitud: int) -> bool:
    return isinstance(valor, str) and re.fullmatch(r"[a-f0-9]{%d}" % longitud, valor) is not None


def _ruta(valor: object) -> str:
    if (not isinstance(valor, str) or not re.fullmatch(r"/[A-Za-z0-9_./-]+", valor) or len(valor) > 1024
            or any(c in valor for c in "\x00\n\r\\") or ".." in Path(valor).parts
            or str(Path(valor)) != valor or valor == "/"):
        raise Rechazo("ruta_no_admitida")
    return valor


@dataclass(frozen=True)
class Plan:
    formato: str
    modo: str
    generacion: str
    manifiesto_sha256: str
    huella_app: str
    imagen_api: str
    imagen_pasarela: str
    imagen_proxy: str
    host: str
    puerto: int
    red_interna: str
    red_servicio: str
    red_datos: str
    ip_datos_api: str
    directorio_generacion: str
    clave_publica: str
    secretos: str
    pki_proxy: str
    pki_sonda: str
    drenaje_s: int = 30
    presupuesto_corte_s: int = 120

    @classmethod
    def de(cls, valor: object) -> "Plan":
        if not isinstance(valor, dict):
            raise Rechazo("plan_no_es_objeto")
        if cls is Plan and valor.get("formato") == "operacion-consulta-local/1":
            from .local import PlanLocal
            return PlanLocal.de(valor)
        try:
            p = cls(**valor)
        except TypeError as error:
            raise Rechazo("campos_del_plan") from error
        if p.formato != "operacion-consulta/1" or p.modo != "ensayo":
            raise Rechazo("solo_ensayo")
        if not (hexadecimal(p.generacion, 32) and hexadecimal(p.manifiesto_sha256, 64)
                and hexadecimal(p.huella_app, 64)):
            raise Rechazo("identidad_del_plan")
        for imagen in (p.imagen_api, p.imagen_pasarela, p.imagen_proxy):
            if not isinstance(imagen, str) or not re.fullmatch(
                    r"[a-z0-9][a-z0-9./:_-]{0,220}@sha256:[a-f0-9]{64}", imagen):
                raise Rechazo("imagen_sin_digest")
        if (not isinstance(p.host, str) or len(p.host) > 120
                or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", p.host)):
            raise Rechazo("host_del_plan")
        for numero, minimo, maximo in ((p.puerto, 1024, 65535), (p.drenaje_s, 25, 60),
                                       (p.presupuesto_corte_s, 60, 600)):
            if type(numero) is not int or not minimo <= numero <= maximo:
                raise Rechazo("limite_del_plan")
        if p.presupuesto_corte_s < p.drenaje_s + 30:
            raise Rechazo("presupuesto_insuficiente")
        try:
            redes = [ipaddress.ip_network(r, strict=True) for r in (p.red_interna, p.red_servicio)]
            ip = ipaddress.ip_address(p.ip_datos_api)
        except (ValueError, TypeError) as error:
            raise Rechazo("red_del_plan") from error
        if (any(r.version != 4 or r.prefixlen != 24 or not any(r.subnet_of(v) for v in PRIVADAS) for r in redes)
                or redes[0].overlaps(redes[1]) or ip.version != 4 or not any(ip in v for v in PRIVADAS)
                or ip.is_loopback or any(ip in r for r in redes)):
            raise Rechazo("red_no_aislada")
        if (not isinstance(p.red_datos, str)
                or not re.fullmatch(r"e105ensayo[a-z0-9-]{8,48}", p.red_datos)):
            raise Rechazo("red_de_datos_no_es_de_ensayo")
        for nombre in ("directorio_generacion", "clave_publica", "secretos", "pki_proxy", "pki_sonda"):
            _ruta(getattr(p, nombre))
        if Path(p.directorio_generacion).name != p.generacion:
            raise Rechazo("carpeta_de_otra_generacion")
        return p

    def objeto(self) -> dict:
        return asdict(self)

    @property
    def id(self) -> str:
        return huella(self.objeto())

    def proyecto(self, propietario: str) -> str:
        if not hexadecimal(propietario, 32):
            raise Rechazo("propietario_no_valido")
        return "e105" + propietario + self.id[:16]

    def ip(self, red: str, ultimo: int) -> str:
        return str(ipaddress.ip_network(getattr(self, red)).network_address + ultimo)


def leer_plan(ruta: Path) -> Plan:
    with ruta.open("rb") as entrada:
        return Plan.de(json_estricto(entrada.read(262145)))
