"""FIXTURES DE PRUEBA de la Etapa AE-81 -NO OPERATIVAS.

Publicadores y monitores Ed25519 deterministas derivados de etiquetas
publicas (no son secretos ni identifican a nadie), checkpoints y
observaciones sinteticos sobre las constancias de AE-80. Nunca se lee el
reloj ni la red.

Estado AE-80 presentado: entradas S2, constancias X1 (S1), X2 (S2,
anterior X1) e Y1 (S2): cabezas X2 e Y1. Registro sintetico del publicador
P: C1 (posicion 1, cabeza X1) y C2 (posicion 2, anterior C1, cabezas X2 e
Y1).
"""
from __future__ import annotations

import functools
import hashlib
import importlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.application.ml import expediente_r0_recepcion as ex
from tests.unit.ml import fixtures_constancias_auditoria as fc

ETIQUETAS = {"p": "fixture AE-81 publicador P (no operativa)",
             "q": "fixture AE-81 publicador Q (no operativa)",
             "m1": "fixture AE-81 monitor M1 (no operativa)",
             "m2": "fixture AE-81 monitor M2 (no operativa)",
             "m3": "fixture AE-81 monitor M3 (no operativa)",
             "ajeno": "fixture AE-81 clave no admitida (no operativa)"}
REGISTRO = "registro-sintetico-ae81"


def _m():
    """Importacion diferida: sobre la base de AE-80 el modulo no existe."""
    return importlib.import_module("app.application.ml.publicacion_constancias")


@functools.lru_cache(maxsize=None)
def clave_privada(nombre: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(ETIQUETAS[nombre].encode("utf-8")).digest())


def clave_publica(nombre: str) -> bytes:
    if nombre in ETIQUETAS:
        return clave_privada(nombre).public_key().public_bytes(serialization.Encoding.Raw,
                                                               serialization.PublicFormat.Raw)
    return fc.clave_publica(nombre)


def huella(nombre: str) -> str:
    return ex.huella_de_clave(clave_publica(nombre))


def firmar(pieza: dict, nombre: str) -> ex.ObjetoFirmado:
    if nombre not in ETIQUETAS:
        return fc.firmar(pieza, nombre)
    datos = ex.bytes_canonicos(pieza)
    return ex.ObjetoFirmado(datos, clave_privada(nombre).sign(datos), clave_publica(nombre))


def claves_privadas() -> list:
    propias = [clave_privada(n).private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                              serialization.NoEncryption()) for n in ETIQUETAS]
    return [*fc.claves_privadas(), *propias]


@functools.lru_cache(maxsize=None)
def constancias() -> tuple:
    x1 = fc.constancia("s1")
    return (x1, fc.constancia("s2", "x", 2, x1), fc.constancia("s2", "y"))


def cabeza(objeto, nombre: str, serie: str = fc.SERIE, secuencia: int = 1) -> list:
    return [ex.huella_de_clave(fc.clave_publica(nombre)), serie, secuencia, ex.hash_de_pieza(objeto.datos)]


def cabezas_c1() -> list:
    return [cabeza(constancias()[0], "x")]


def cabezas_c2() -> list:
    x1, x2, y1 = constancias()
    return [cabeza(x2, "x", secuencia=2), cabeza(y1, "y")]


def sha_politica_de_constancias() -> str:
    return hashlib.sha256(fc.politica_de_constancias()["politica_constancias.json"]).hexdigest()


def checkpoint(cabezas, posicion: int = 1, anterior=None, *, publicador: str = "p", registro: str = REGISTRO,
               **cambios) -> ex.ObjetoFirmado:
    if isinstance(anterior, ex.ObjetoFirmado):
        anterior = ex.hash_de_pieza(anterior.datos)
    pieza = _m().construir_checkpoint(cabezas=cabezas, sha256_politica_de_constancias=sha_politica_de_constancias(),
                                      registro=registro, posicion=posicion, anterior=anterior,
                                      clave_publica=clave_publica(publicador))
    pieza.update(cambios)
    return firmar(pieza, publicador)


@functools.lru_cache(maxsize=None)
def c1():
    return checkpoint(cabezas_c1())


@functools.lru_cache(maxsize=None)
def c2():
    return checkpoint(cabezas_c2(), 2, c1())


@functools.lru_cache(maxsize=None)
def c2_sustituto():
    """Otro checkpoint de P en la posicion 2 que omite la cabeza Y1."""
    return checkpoint(cabezas_c2()[:1], 2, c1())


def observacion(objeto, monitor: str, **cambios) -> ex.ObjetoFirmado:
    pieza = _m().construir_observacion(objeto, clave_publica=clave_publica(monitor))
    pieza.update(cambios)
    return firmar(pieza, monitor)


def politica(rol: str, nombres) -> dict:
    return _m().componer_politica_de_rol(rol=rol, claves=[(clave_publica(n), ETIQUETAS.get(n, n)) for n in nombres])


def inventario(*, checkpoints=None, cabezas=None, monitores=("m1", "m2"),
               procedencia: str = "declarada_por_quien_verifica") -> dict:
    checkpoints = checkpoints if checkpoints is not None else [c1(), c2()]
    entradas = []
    for c in checkpoints:
        pieza = ex.json.loads(c.datos)
        entradas.append([pieza["huella_de_clave"], pieza["registro"], pieza["posicion"], ex.hash_de_pieza(c.datos)])
    cabezas = cabezas if cabezas is not None else [c[3] for c in cabezas_c2()]
    return _m().componer_inventario(procedencia=procedencia, checkpoints=entradas, cabezas=cabezas,
                                    monitores=[huella(n) for n in monitores])


def id_(objeto) -> str:
    return ex.hash_de_pieza(objeto.datos)


def entradas(*, checkpoints=None, observaciones=None, inventario_=False, publicadores=("p", "q"),
             monitores=("m1", "m2", "m3")) -> dict:
    """Argumentos de `verificar`. Por defecto: continuidad valida."""
    m = _m()
    checkpoints = checkpoints if checkpoints is not None else [c1(), c2()]
    observaciones = observaciones if observaciones is not None else [observacion(c2(), "m1"),
                                                                     observacion(c2(), "m2")]
    base = fc.entradas("s2")
    return {**base, "politica_de_constancias": fc.politica_de_constancias(),
            "constancias": [fc._m().componer_constancias(list(constancias()))],
            "politica_de_publicadores": politica("publicador", publicadores),
            "politica_de_monitores": politica("monitor", monitores),
            "checkpoints": [m.componer_checkpoints(list(checkpoints))] if checkpoints else [],
            "observaciones": [m.componer_observaciones(list(observaciones))] if observaciones else [],
            "inventario": inventario() if inventario_ is False else inventario_}
