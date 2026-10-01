"""FIXTURES DE PRUEBA de la Etapa AE-79 -NO OPERATIVAS.

Expedientes AE-78 sinteticos con historias distintas del mismo protocolo, y
capturadores Ed25519 deterministas derivados de etiquetas publicas (no son
secretos ni identifican a nadie). Reutilizan las fixtures de AE-75 a AE-78.
Las claves RSA de la TSA de prueba se generan en cada ejecucion: los bytes
de los tokens y los hashes de los manifiestos cambian entre ejecuciones; los
estados y motivos no. Nunca se lee el reloj.
"""
from __future__ import annotations

import functools
import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.application.ml import expediente_portable as ep
from app.application.ml import expediente_r0_recepcion as ex
from app.application.ml import recepcion_por_objetivo as ro
from app.application.ml import sello_temporal_r0 as st
from tests.unit.ml import fixtures_expediente_portable as fp
from tests.unit.ml import fixtures_expediente_r0 as fx
from tests.unit.ml import fixtures_recepcion_por_objetivo as fo
from tests.unit.ml import fixtures_sello_temporal as fs

ETIQUETAS = {"a": "fixture AE-79 capturador A (no operativa)",
             "b": "fixture AE-79 capturador B (no operativa)",
             "c": "fixture AE-79 capturador C (no operativa)",
             "ajeno": "fixture AE-79 capturador no admitido (no operativa)"}
CORTES_ADMITIDOS = (2715, 2716)


@functools.lru_cache(maxsize=None)
def clave_privada(nombre: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(ETIQUETAS[nombre].encode("utf-8")).digest())


def clave_publica(nombre: str) -> bytes:
    if nombre in fx.ETIQUETAS:
        return fx.clave_publica(nombre)
    return clave_privada(nombre).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def firmar(pieza: dict, nombre: str) -> ex.ObjetoFirmado:
    if nombre in fx.ETIQUETAS:
        return fx.firmar(ex, pieza, nombre)
    datos = ex.bytes_canonicos(pieza)
    return ex.ObjetoFirmado(datos, clave_privada(nombre).sign(datos), clave_publica(nombre))


def claves_privadas() -> list:
    """Bytes crudos de todas las claves privadas de fixture de AE-76 a AE-79."""
    propias = [clave_privada(n).private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                              serialization.NoEncryption()) for n in ETIQUETAS]
    return [*fp.claves_privadas_de_fixture(), *propias]


@functools.lru_cache(maxsize=None)
def expediente(objetivos: tuple = (2714, 2715, 2716), *, valor: str = "valor-de-prueba",
               sellos_de_acuses: int | None = None) -> dict:
    """{ruta: bytes} de un expediente AE-78 integro cuya historia cubre
    `objetivos` en orden. El corte sintetico es el ultimo objetivo, el
    conjunto esperado es la ultima declaracion de la vista del observador y
    la vista crece un objetivo por declaracion. `sellos_de_acuses` limita
    cuantos acuses llevan sello (una alteracion coherente de archivos y
    manifiesto que AE-78 por si solo deja en pendiente)."""
    entradas, bd = fx.registro(objetivos, valor)
    acuses = fx.acuses(ex, entradas, objetivos)
    pares = tuple(("BALOTO", o) for o in objetivos)
    etapas = [(pares[:i], objetivos[i - 1]) for i in range(1, len(objetivos) + 1)]
    vista = fo.cadena(ro, ex, entradas, etapas)
    sobre = fx.firmar(ex, ex.construir_sobre(entradas, bd, clave_publica=fx.clave_publica("firmante")), "firmante")
    compromiso = st.construir_compromiso(entradas, bd, codigo_juego="BALOTO", sorteo_objetivo=objetivos[0],
                                         plazo_utc=fo.PLAZO)
    datos_r0 = st.bytes_de_compromiso(compromiso)
    sellos_r0 = {("BALOTO", objetivos[0]): st.EvidenciaDeSello(
        fs.respuesta(datos_r0, fs.Opciones(gen_time=fs.instante(fo.GEN))), datos_r0)}
    return ep.componer_expediente(
        entradas=entradas, bytes_declaracion=bd, sobre=sobre, sellos_r0=sellos_r0, acuses=acuses,
        sellos_de_acuses=[fo.sellar_acuse(ro, entradas, a) for a in acuses[:sellos_de_acuses]],
        cierre=fx.cierre(ex, entradas, acuses, conjunto=pares), conjunto_esperado=vista[-1], vistas=[vista])


@functools.lru_cache(maxsize=None)
def politica_del_verificador() -> dict:
    return fp.politica(ep)


def _ac():
    """Importacion diferida: sobre la base de AE-78 el modulo no existe."""
    import importlib
    return importlib.import_module("app.application.ml.auditoria_cruzada")


def politica_de_auditoria(capturadores=("a", "b", "c"), cortes=CORTES_ADMITIDOS, *, etiquetas=None) -> dict:
    ac = _ac()
    etiquetas = etiquetas or [ETIQUETAS.get(n, n) for n in capturadores]
    return ac.componer_politica_de_auditoria(
        capturadores=[(clave_publica(n), e) for n, e in zip(capturadores, etiquetas)], cortes_admitidos=cortes)


def sha256_politica() -> str:
    return hashlib.sha256(politica_del_verificador()[ep.NOMBRE_POLITICA]).hexdigest()


def capturar(archivos: dict, capturador: str, secuencia: int = 1, anterior=None, *, observador=None,
             **cambios) -> ex.ObjetoFirmado:
    """Captura firmada del expediente `archivos` por `capturador`.
    `anterior` puede ser un ObjetoFirmado o un hash."""
    if isinstance(anterior, ex.ObjetoFirmado):
        anterior = ex.hash_de_pieza(anterior.datos)
    pieza = _ac().construir_captura(ep.leer_expediente(archivos), sha256_politica=sha256_politica(),
                                 observador=observador or f"capturador-{capturador}", secuencia=secuencia,
                                 anterior=anterior, clave_publica=clave_publica(capturador))
    pieza.update(cambios)
    return firmar(pieza, capturador)


def sha(archivos: dict) -> str:
    return hashlib.sha256(archivos[ep.NOMBRE_MANIFIESTO]).hexdigest()


def id_(objeto) -> str:
    return ex.hash_de_pieza(objeto.datos)


# Historias de la demostracion (mismo protocolo, canal y alcance):
#   E1: 2714, 2715 (corte 2715);  E2: 2714, 2715, 2716 (corte 2716), extiende E1;
#   E3: 2714, 2716 (corte 2716), diverge de E2 en la posicion 2;
#   E4: protocolo distinto (otra declaracion R0), 2714, 2715.
def e1():
    return expediente((2714, 2715))


def e2():
    return expediente((2714, 2715, 2716))


def e3():
    return expediente((2714, 2716))


def e4():
    return expediente((2714, 2715), valor="otra-declaracion")


def e2_sin_un_sello():
    """E2 reempaquetado sin el sello del ultimo acuse: manifiesto nuevo y
    coherente con sus archivos."""
    return expediente((2714, 2715, 2716), sellos_de_acuses=2)
