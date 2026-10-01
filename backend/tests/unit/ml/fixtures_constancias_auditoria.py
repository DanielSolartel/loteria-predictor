"""FIXTURES DE PRUEBA de la Etapa AE-80 -NO OPERATIVAS.

Firmantes de constancias Ed25519 deterministas, derivados de etiquetas
publicas (no son secretos ni identifican a nadie), y estados auditados
sinteticos construidos con las fixtures de AE-79. Nunca se lee el reloj.
"""
from __future__ import annotations

import functools
import hashlib
import importlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.application.ml import expediente_r0_recepcion as ex
from tests.unit.ml import fixtures_auditoria_cruzada as fa

ETIQUETAS = {"x": "fixture AE-80 firmante de constancias X (no operativa)",
             "y": "fixture AE-80 firmante de constancias Y (no operativa)",
             "ajeno": "fixture AE-80 firmante no admitido (no operativa)"}
SERIE = "serie-sintetica-ae80"


def _m():
    """Importacion diferida: sobre la base de AE-79 el modulo no existe."""
    return importlib.import_module("app.application.ml.constancias_auditoria")


def _ac():
    return importlib.import_module("app.application.ml.auditoria_cruzada")


@functools.lru_cache(maxsize=None)
def clave_privada(nombre: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(ETIQUETAS[nombre].encode("utf-8")).digest())


def clave_publica(nombre: str) -> bytes:
    if nombre in ETIQUETAS:
        return clave_privada(nombre).public_key().public_bytes(serialization.Encoding.Raw,
                                                               serialization.PublicFormat.Raw)
    return fa.clave_publica(nombre)


def firmar(pieza: dict, nombre: str) -> ex.ObjetoFirmado:
    if nombre not in ETIQUETAS:
        return fa.firmar(pieza, nombre)
    datos = ex.bytes_canonicos(pieza)
    return ex.ObjetoFirmado(datos, clave_privada(nombre).sign(datos), clave_publica(nombre))


def claves_privadas() -> list:
    propias = [clave_privada(n).private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                              serialization.NoEncryption()) for n in ETIQUETAS]
    return [*fa.claves_privadas(), *propias]


def politica_de_constancias(firmantes=("x", "y"), *, etiquetas=None) -> dict:
    etiquetas = etiquetas or [ETIQUETAS.get(n, n) for n in firmantes]
    return _m().componer_politica_de_constancias(
        firmantes=[(clave_publica(n), e) for n, e in zip(firmantes, etiquetas)])


@functools.lru_cache(maxsize=None)
def capturas_s1() -> tuple:
    """Capturas del estado S1: A1 sobre E1 y B1 sobre E2."""
    return (fa.capturar(fa.e1(), "a"), fa.capturar(fa.e2(), "b"))


@functools.lru_cache(maxsize=None)
def capturas_s2() -> tuple:
    """Capturas del estado S2: las de S1 mas A2, que extiende A1."""
    a1, b1 = capturas_s1()
    return (a1, b1, fa.capturar(fa.e2(), "a", 2, a1))


def entradas(nombre: str) -> dict:
    """Argumentos de auditoria de un estado sintetico.
    s1: E1, E2 y capturas S1; s2: E1, E2 y capturas S2;
    sustituido: como s1 pero E2 reempaquetado sin un sello."""
    e2 = fa.e2_sin_un_sello() if nombre == "sustituido" else fa.e2()
    capturas = capturas_s2() if nombre == "s2" else capturas_s1()
    return {"expedientes": [fa.e1(), e2], "politica_del_verificador": fa.politica_del_verificador(),
            "politica_de_auditoria": fa.politica_de_auditoria(),
            "capturas": [_ac().componer_capturas(list(capturas))]}


@functools.lru_cache(maxsize=None)
def estado(nombre: str):
    return _m().estado_auditado(**entradas(nombre))


def constancia(nombre_estado: str, firmante: str = "x", secuencia: int = 1, anterior=None, *, serie: str = SERIE,
               **cambios) -> ex.ObjetoFirmado:
    """Constancia firmada del estado `nombre_estado`. `anterior` puede ser
    un ObjetoFirmado o un hash; `cambios` altera campos antes de firmar."""
    if isinstance(anterior, ex.ObjetoFirmado):
        anterior = ex.hash_de_pieza(anterior.datos)
    pieza = _m().construir_constancia(estado(nombre_estado), serie=serie, secuencia=secuencia, anterior=anterior,
                                      clave_publica=clave_publica(firmante))
    pieza.update(cambios)
    return firmar(pieza, firmante)


def id_(objeto) -> str:
    return ex.hash_de_pieza(objeto.datos)
