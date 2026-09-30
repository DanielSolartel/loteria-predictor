"""FIXTURES DE PRUEBA de la Etapa AE-77 -NO OPERATIVAS.

Claves Ed25519 deterministas de un observador de fixture, derivadas de
etiquetas publicas y distintas de las del canal de AE-76. Los sellos de los
acuses salen de las fixtures de AE-75 (CA, TSA y politica 2.999.75.x de
prueba). Todos los instantes los fija la prueba; nunca se lee el reloj.
"""
from __future__ import annotations

import functools
import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.application.ml import sello_temporal_r0 as st
from tests.unit.ml import fixtures_expediente_r0 as fx
from tests.unit.ml import fixtures_sello_temporal as fs

ETIQUETAS = {"observador": "fixture AE-77 observador del conjunto esperado (no operativa)",
             "observador_ajeno": "fixture AE-77 observador no admitido (no operativa)"}
OBSERVADOR = "observador-sintetico-ae77"
PLAZO = "2026-10-10T00:00:00Z"
GEN = "2026-10-01T12:00:00Z"


@functools.lru_cache(maxsize=None)
def clave_privada(nombre: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(ETIQUETAS[nombre].encode("utf-8")).digest())


def clave_publica(nombre: str) -> bytes:
    if nombre in fx.ETIQUETAS:
        return fx.clave_publica(nombre)
    return clave_privada(nombre).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def firmar(m_ae76, pieza: dict, nombre: str, *, alterar: bool = False):
    if nombre in fx.ETIQUETAS:
        return fx.firmar(m_ae76, pieza, nombre, alterar=alterar)
    datos = m_ae76.bytes_canonicos(pieza)
    firma = clave_privada(nombre).sign(datos)
    if alterar:
        datos = datos.replace(b'"', b"'", 1)
    return m_ae76.ObjetoFirmado(datos, firma, clave_publica(nombre))


def politica_observadores(m):
    return m.PoliticaDeObservadoresDePrueba(claves=(
        m.ClaveDeObservadorDePrueba(clave_publica("observador"), ETIQUETAS["observador"]),))


def politica_sello(margen="0"):
    return st.PoliticaDeConfianzaTemporal(anclas=(st.AnclaDePrueba(fs.der(fs.mundo().ca), "CA fixture"),),
                                          politicas_admitidas=(fs.POLITICA_DE_PRUEBA,), margen=margen)


def sellar_acuse(m, entradas, acuse, *, plazo=PLAZO, gen=GEN, compromiso=None, **opciones):
    """EvidenciaDeSelloDeAcuse: compromiso del acuse y token de prueba sobre
    sus bytes (o sobre `compromiso` si la prueba lo manipula)."""
    compromiso = compromiso if compromiso is not None else m.construir_compromiso_de_acuse(entradas, acuse,
                                                                                         plazo_utc=plazo)
    datos = m.bytes_de_compromiso(compromiso)
    respuesta = fs.respuesta(datos, fs.Opciones(gen_time=fs.instante(gen), **opciones))
    return m.EvidenciaDeSelloDeAcuse(acuse, respuesta, datos)


def declaracion(m, m_ae76, entradas, *, objetivos=(("BALOTO", 2714), ("BALOTO", 2715), ("BALOTO", 2716)),
                corte_sintetico=2716, secuencia=1, anterior=None, clave="observador", alterar=False, **cambios):
    pieza = m.construir_conjunto_esperado(entradas, observador=OBSERVADOR, corte_sintetico=corte_sintetico,
                                          objetivos=objetivos, secuencia=secuencia, anterior=anterior,
                                          clave_publica=clave_publica(clave))
    pieza.update(cambios)
    return firmar(m_ae76, pieza, clave, alterar=alterar)


def cadena(m, m_ae76, entradas, etapas):
    """Vista encadenada: `etapas` es una lista de (objetivos, corte)."""
    vista, anterior = [], None
    for i, (objetivos, corte) in enumerate(etapas, start=1):
        objeto = declaracion(m, m_ae76, entradas, objetivos=objetivos, corte_sintetico=corte, secuencia=i,
                             anterior=anterior)
        vista.append(objeto)
        anterior = m_ae76.hash_de_pieza(objeto.datos)
    return vista
