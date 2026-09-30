"""FIXTURES DE PRUEBA de la Etapa AE-78 -NO OPERATIVAS.

Escenarios sinteticos del expediente portable, construidos solo con las
fixtures de AE-75 (CA, TSA y politica 2.999.75.x), AE-76 (registro, firmante
y canal) y AE-77 (observador). Las claves privadas viven solo aqui: el
expediente y la politica exportados contienen claves publicas y certificados.
Las claves RSA de la TSA de prueba se generan en cada ejecucion, asi que los
bytes de los tokens (y el hash del manifiesto) cambian entre ejecuciones; los
estados y motivos no. Nunca se lee el reloj.
"""
from __future__ import annotations

from pathlib import Path

from app.application.ml import expediente_r0_recepcion as ex
from app.application.ml import recepcion_por_objetivo as ro
from app.application.ml import sello_temporal_r0 as st
from tests.unit.ml import fixtures_expediente_r0 as fx
from tests.unit.ml import fixtures_recepcion_por_objetivo as fo
from tests.unit.ml import fixtures_sello_temporal as fs

ETAPAS = (((("BALOTO", 2714),), 2714), ((("BALOTO", 2714), ("BALOTO", 2715)), 2715),
          ((("BALOTO", 2714), ("BALOTO", 2715), ("BALOTO", 2716)), 2716))


def escenario(nombre: str = "integro") -> dict:
    """Piezas de un escenario de demostracion. `nombre` en ESCENARIOS."""
    entradas, bd = fx.registro()
    acuses = fx.acuses(ex, entradas)
    objetivos_cierre = (("BALOTO", 2714), ("BALOTO", 2715), ("BALOTO", 2716))
    sobre = fx.firmar(ex, ex.construir_sobre(entradas, bd, clave_publica=fx.clave_publica("firmante")), "firmante")
    compromiso = st.construir_compromiso(entradas, bd, codigo_juego="BALOTO", sorteo_objetivo=2714,
                                         plazo_utc=fo.PLAZO)
    datos_r0 = st.bytes_de_compromiso(compromiso)
    sellos_r0 = {("BALOTO", 2714): st.EvidenciaDeSello(
        fs.respuesta(datos_r0, fs.Opciones(gen_time=fs.instante(fo.GEN))), datos_r0)}
    sellos = [fo.sellar_acuse(ro, entradas, a) for a in acuses]
    vistas = [fo.cadena(ro, ex, entradas, ETAPAS)]
    if nombre == "acuse_alterado":
        alterado = fx.firmar(ex, ex.leer_acuse(acuses[0].datos), "canal", alterar=True)
        acuses = [alterado, *acuses[1:]]
        sellos = [ro.EvidenciaDeSelloDeAcuse(alterado, sellos[0].respuesta_der, sellos[0].bytes_compromiso),
                  *sellos[1:]]
    elif nombre == "sello_de_otro_acuse":
        sellos = [ro.EvidenciaDeSelloDeAcuse(acuses[0], sellos[1].respuesta_der, sellos[1].bytes_compromiso),
                  *sellos[1:]]
    elif nombre == "objetivo_omitido":
        acuses = acuses[:2]
        sellos = sellos[:2]
        objetivos_cierre = objetivos_cierre[:2]
    elif nombre == "vistas_contradictorias":
        vistas = [vistas[0], fo.cadena(ro, ex, entradas, [ETAPAS[0], ((("BALOTO", 2714), ("BALOTO", 2716)), 2716)])]
    elif nombre != "integro":
        raise ValueError(nombre)
    cierre = fx.cierre(ex, entradas, acuses, conjunto=objetivos_cierre)
    return {"entradas": entradas, "bytes_declaracion": bd, "sobre": sobre, "sellos_r0": sellos_r0,
            "acuses": acuses, "sellos_de_acuses": sellos, "cierre": cierre,
            "conjunto_esperado": fo.declaracion(ro, ex, entradas), "vistas": vistas}


ESCENARIOS = ("integro", "acuse_alterado", "sello_de_otro_acuse", "objetivo_omitido", "vistas_contradictorias")


def politica(m, *, corte_esperado: int = 2716) -> dict:
    """Archivos de la politica de prueba del verificador (solo publicos).
    Canal y corte esperados son decision de quien verifica."""
    return m.componer_politica(
        anclas=[(fs.der(fs.mundo().ca), "CA de prueba AE-75 (fixture, no operativa)")],
        politicas_admitidas=[fs.POLITICA_DE_PRUEBA], margen="0",
        claves=[(fx.clave_publica("firmante"), "firmante_r0", fx.ETIQUETAS["firmante"]),
                (fx.clave_publica("canal"), "canal", fx.ETIQUETAS["canal"])],
        observadores=[(fo.clave_publica("observador"), fo.ETIQUETAS["observador"])],
        canal=fx.CANAL, corte_esperado=corte_esperado)


def escribir(directorio: Path, archivos: dict) -> Path:
    directorio.mkdir(parents=True)
    for ruta, datos in archivos.items():
        destino = directorio.joinpath(*ruta.split("/"))
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    return directorio


def claves_privadas_de_fixture() -> list:
    """Bytes crudos de todas las claves privadas Ed25519 de fixture, para
    comprobar que el expediente exportado no las contiene."""
    from cryptography.hazmat.primitives import serialization
    privadas = [fx.clave_privada(n) for n in fx.ETIQUETAS] + [fo.clave_privada(n) for n in fo.ETIQUETAS]
    return [k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                            serialization.NoEncryption()) for k in privadas]
