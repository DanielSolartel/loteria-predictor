"""FIXTURES DE PRUEBA de la Etapa AE-76 -NO OPERATIVAS.

Claves Ed25519 deterministas derivadas de etiquetas publicas
(`SHA-256("fixture AE-76 ...")`): cualquiera puede recalcularlas, asi que no
son secretas ni identifican a nadie. Firman con `cryptography`. El registro es
sintetico (protocolo 1.2 del contrato de AE-74 con predicciones fabricadas) y
las horas del canal son cadenas fijadas por la prueba, nunca el reloj.
"""
from __future__ import annotations

import functools
import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.application.ml import contrato_vinculo_r0 as cv
from app.application.ml import inventario_declaracion_previa_del_protocolo as iv
from app.application.ml import prototipo_vinculo_declaracion_r0 as pv
from app.application.ml import registro_prospectivo as rp
from tests.unit.simulaciones import sinteticos

CORTES = {"BALOTO": 2713, "BALOTO_REVANCHA": 2713}
PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""
CANAL = "canal-sintetico-ae76"
ETIQUETAS = {"firmante": "fixture AE-76 firmante R0 (no operativa)",
             "canal": "fixture AE-76 canal de acuses (no operativa)",
             "ajena": "fixture AE-76 clave no admitida (no operativa)"}


@functools.lru_cache(maxsize=None)
def clave_privada(nombre: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(ETIQUETAS[nombre].encode("utf-8")).digest())


def clave_publica(nombre: str) -> bytes:
    return clave_privada(nombre).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def firmar(m, pieza: dict, nombre: str, *, alterar: bool = False):
    """ObjetoFirmado de `pieza` con la clave `nombre`; `alterar` cambia un
    byte de los datos despues de firmar."""
    datos = m.bytes_canonicos(pieza)
    firma = clave_privada(nombre).sign(datos)
    if alterar:
        datos = datos.replace(b'"', b"'", 1)
    return m.ObjetoFirmado(datos, firma, clave_publica(nombre))


def politica(m):
    return m.PoliticaDeClavesDePrueba(claves=(
        m.ClaveDePrueba(clave_publica("firmante"), "firmante_r0", ETIQUETAS["firmante"]),
        m.ClaveDePrueba(clave_publica("canal"), "canal", ETIQUETAS["canal"]),
    ))


def _estrategia():
    return {"nombre": "estrategia_sintetica", "descripcion": "estrategia sintetica solo para pruebas",
            "huella_codigo": "a" * 64, "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
            "entorno": {"python": "3.x", "scikit_learn": "0.0"}}


def _elementos(valor="valor-de-prueba"):
    return {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"{valor}-{i}"}}
            for i, e in enumerate(iv.ELEMENTOS_DE_R0)}


@functools.lru_cache(maxsize=None)
def registro(objetivos=(2714, 2715, 2716), valor="valor-de-prueba"):
    """(entradas, bytes de la declaracion) de un registro 1.2 sintetico."""
    declaracion = pv.construir_declaracion(_elementos(valor))
    protocolo = cv.construir_protocolo_del_contrato(declaracion, protocolo_id="sintetico-ae76",
                                                    estrategia=_estrategia(), cortes=CORTES)
    entradas = [rp.serializar_entrada(protocolo)]
    for objetivo in objetivos:
        prediccion = rp.nueva_prediccion(rp.validar_registro(entradas), "BALOTO", objetivo,
                                         sinteticos.historico(2081, objetivo - 1), PROBABILIDADES)
        entradas.append(rp.serializar_entrada(prediccion))
    return tuple(entradas), pv.bytes_de_declaracion(declaracion)


def acuses(m, entradas, objetivos=(2714, 2715, 2716), *, clave="canal"):
    """Acuses firmados y encadenados, uno por objetivo, en orden."""
    objetos, anterior = [], None
    for secuencia, objetivo in enumerate(objetivos, start=1):
        pieza = m.construir_acuse(entradas, canal=CANAL, codigo_juego="BALOTO", sorteo_objetivo=objetivo,
                                  secuencia=secuencia, acuse_anterior=anterior,
                                  hora_declarada_utc=f"2026-10-0{secuencia}T12:00:00Z",
                                  clave_publica=clave_publica(clave))
        objeto = firmar(m, pieza, clave)
        objetos.append(objeto)
        anterior = m.hash_de_pieza(objeto.datos)
    return objetos


def cierre(m, entradas, objetos, *, conjunto=(("BALOTO", 2714), ("BALOTO", 2715), ("BALOTO", 2716)),
           declara_completo=True, clave="canal", **cambios):
    pieza = m.construir_cierre(canal=CANAL, protocolo_hash=rp.hash_entrada(entradas[0]), conjunto_declarado=conjunto,
                               acuses=[o.datos for o in objetos], declara_completo=declara_completo,
                               clave_publica=clave_publica(clave))
    pieza.update(cambios)
    return firmar(m, pieza, clave)
