"""Tests de la Etapa AE-75, validada (solo sobre datos, anclas y plazos
sinteticos): sello temporal RFC 3161 (con RFC
5816) sobre el compromiso canonico y versionado `compromiso-sello-r0-objetivo/1`
y plano temporal separado del contrato de AE-74.

Tres grupos:

G1  funcionalidad nueva:
    - modulo `sello_temporal_r0`, importado dentro de cada prueba (sobre la
      base falla con `ModuleNotFoundError`);
    - D8 registrada solo para el modelo sintetico y dependencias fijadas en
      `requirements.txt` (sobre la base fallan por asercion).
G2  invariantes: huellas de AE-52 y AE-63 a AE-74 (sin D8), bytes y hashes
    literales de los registros 1.0, 1.1 y 1.2, estados y bloqueos,
    `evaluar_admision` sin entrada de evidencia.
G3  premisas sobre codigo existente y sobre las bibliotecas elegidas.

Los tokens salen de `fixtures_sello_temporal` (claves, CA, TSA y politicas de
prueba, no operativas) salvo uno emitido por OpenSSL y fijado como contraste
independiente. Ningun resultado llega a `superada`: la cadena frente a una
CA de fixture no es una TSA aprobada. Ni un sello del compromiso ni el
tiempo comprobado prueban autenticacion de R0, recepcion de predicciones ni
completitud o unicidad del canal, y `r0_final` sigue rechazada. Sin red,
reloj local, datos reales ni PostgreSQL; `AUTORIZA_EVALUACION = False`."""
from __future__ import annotations

import ast
import dataclasses
import functools
import hashlib
import importlib
import inspect
import json
import re
import shutil
import subprocess
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path

import pytest

from app.application.ml import analisis_alternativas_de_declaracion_previa as aa
from app.application.ml import auditoria_obligaciones_de_aplicacion as ao
from app.application.ml import contrato_vinculo_r0 as cv
from app.application.ml import especificacion_condiciones_del_protocolo as ec
from app.application.ml import inventario_declaracion_previa_del_protocolo as iv
from app.application.ml import propuesta_evidencia_temporal_externa as pe
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import prototipo_vinculo_declaracion_r0 as pv
from app.application.ml import registro_prospectivo as rp
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml import verificacion_primaria_choe_ramdas as vp
from app.application.ml import verificacion_primaria_rfc_sellado_y_transparencia as vr
from app.application.ml import vinculo_declaracion_previa_con_protocolo as vv
from app.application.ml import vinculo_r0_campo_explicito as ve
from tests.unit.ml import fixtures_sello_temporal as f
from tests.unit.simulaciones import sinteticos

PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""
CORTES = {"BALOTO": 2713, "BALOTO_REVANCHA": 2713}
PLAZO = "2026-10-10T00:00:00Z"
GEN = "2026-10-01T12:00:00Z"
RAIZ = Path(__file__).resolve().parents[4]


def _m():
    return importlib.import_module("app.application.ml.sello_temporal_r0")


def _estrategia():
    return {"nombre": "estrategia_sintetica", "descripcion": "estrategia sintetica solo para pruebas",
            "huella_codigo": "a" * 64, "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
            "entorno": {"python": "3.x", "scikit_learn": "0.0"}}


def _elementos():
    return {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"valor-de-prueba-{i}"}}
            for i, e in enumerate(iv.ELEMENTOS_DE_R0)}


@functools.lru_cache(maxsize=None)
def _registro(objetivos=(2714,), protocolo_id="sintetico-ae75"):
    declaracion = pv.construir_declaracion(_elementos())
    protocolo = cv.construir_protocolo_del_contrato(declaracion, protocolo_id=protocolo_id,
                                                    estrategia=_estrategia(), cortes=CORTES)
    entradas = [rp.serializar_entrada(protocolo)]
    for objetivo in objetivos:
        prediccion = rp.nueva_prediccion(rp.validar_registro(entradas), "BALOTO", objetivo,
                                         sinteticos.historico(2081, objetivo - 1), PROBABILIDADES)
        entradas.append(rp.serializar_entrada(prediccion))
    return tuple(entradas), pv.bytes_de_declaracion(declaracion)


def _politica(m, *, margen="0", politicas=(f.POLITICA_DE_PRUEBA,), anclas=None):
    if anclas is None:
        anclas = (m.AnclaDePrueba(f.der(f.mundo().ca), "CA de prueba AE-75 (fixture)"),)
    return m.PoliticaDeConfianzaTemporal(anclas=anclas, politicas_admitidas=politicas, margen=margen)


def _compromiso(m, *, plazo=PLAZO, objetivo=2714, registro=None):
    entradas, bd = registro or _registro()
    return m.construir_compromiso(entradas, bd, codigo_juego="BALOTO", sorteo_objetivo=objetivo, plazo_utc=plazo)


def _evidencia(m, *, compromiso=None, gen=GEN, **opciones):
    compromiso = compromiso if compromiso is not None else _compromiso(m)
    datos = m.bytes_de_compromiso(compromiso)
    return m.EvidenciaDeSello(f.respuesta(datos, f.Opciones(gen_time=f.instante(gen), **opciones)), datos)


def _verificar(m, evidencia, *, politica=None, objetivo=2714, juego="BALOTO", registro=None):
    entradas, bd = registro or _registro()
    return m.verificar_sello(entradas, bd, evidencia, politica or _politica(m), codigo_juego=juego,
                             sorteo_objetivo=objetivo)


def _todas(informe):
    return {**informe.vinculo_del_compromiso, **informe.comprobaciones_criptograficas}


def _motivos(informe):
    return {motivo for c in _todas(informe).values() for motivo in c.motivos}


def _plano(valor):
    if dataclasses.is_dataclass(valor):
        return {f_.name: _plano(getattr(valor, f_.name)) for f_ in dataclasses.fields(valor)}
    if isinstance(valor, Mapping):
        return {str(k): _plano(v) for k, v in valor.items()}
    if isinstance(valor, (tuple, list, set, frozenset)):
        return [_plano(v) for v in (sorted(valor) if isinstance(valor, (set, frozenset)) else valor)]
    return valor


def _huella(valor):
    return hashlib.sha256(json.dumps(_plano(valor), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ===========================================================================
# G1: compromiso versionado por objetivo
# ===========================================================================

def test_g1_compromiso_canonico_por_objetivo():
    m = _m()
    entradas, bd = _registro()
    c = _compromiso(m)
    assert tuple(sorted(c)) == tuple(sorted(m.CLAVES_DEL_COMPROMISO))
    assert c["esquema"] == m.ESQUEMA_COMPROMISO == "compromiso-sello-r0-objetivo/1"
    assert (c["contrato"], c["regla"], c["esquema_del_protocolo"]) == (
        "contrato-vinculo-r0/1", "ae74-vinculo-r0-contrato/1", "registro-prospectivo-ml/1.2")
    assert c["protocolo_hash"] == rp.hash_entrada(entradas[0])
    assert c["hash_declaracion"] == rp.hash_entrada(bd)
    assert (c["codigo_juego"], c["sorteo_objetivo"], c["plazo_utc"], c["procedencia_del_plazo"]) == (
        "BALOTO", 2714, PLAZO, "sintetica_de_prueba")
    datos = m.bytes_de_compromiso(c)
    assert datos == rp.serializar_entrada(c) and datos.endswith(b"\n")
    assert m.leer_compromiso(datos) == c
    otro = m.bytes_de_compromiso(_compromiso(m, objetivo=2715))
    assert otro != datos


@pytest.mark.parametrize("cambio, motivo", [
    ({"esquema": "compromiso-sello-r0-objetivo/2"}, "version_de_compromiso_desconocida"),
    ({"esquema": "compromiso-sello-r0/1"}, "version_de_compromiso_desconocida"),
    ({"extra": 1}, "compromiso_ilegible"),
])
def test_g1_otra_version_o_claves_no_se_reinterpretan(cambio, motivo):
    m = _m()
    datos = rp.serializar_entrada({**_compromiso(m), **cambio})
    with pytest.raises(m.CompromisoInvalido) as error:
        m.leer_compromiso(datos)
    assert error.value.motivo == motivo


def test_g1_compromiso_no_canonico_se_rechaza():
    m = _m()
    c = _compromiso(m)
    datos = json.dumps(c, sort_keys=True, indent=1).encode("utf-8")
    with pytest.raises(m.CompromisoInvalido) as error:
        m.leer_compromiso(datos)
    assert error.value.motivo == "compromiso_no_canonico"


@pytest.mark.parametrize("juego, objetivo, plazo, procedencia, motivo", [
    ("BALOTO", 2713, PLAZO, "sintetica_de_prueba", "objetivo_no_posterior_al_corte"),
    ("BALOTO", 2600, PLAZO, "sintetica_de_prueba", "objetivo_no_posterior_al_corte"),
    ("MILOTO", 2714, PLAZO, "sintetica_de_prueba", "juego_fuera_del_protocolo"),
    ("BALOTO", 2714, "2026-10-10T00:00:00", "sintetica_de_prueba", "plazo_sin_utc_explicito"),
    ("BALOTO", 2714, "2026-10-09T19:00:00-05:00", "sintetica_de_prueba", "plazo_sin_utc_explicito"),
    ("BALOTO", 2714, "2026-10-10T00:00:00.50Z", "sintetica_de_prueba", "plazo_sin_utc_explicito"),
    ("BALOTO", 2714, "2026-12-31T23:59:60Z", "sintetica_de_prueba", "plazo_sin_utc_explicito"),
    ("BALOTO", 2714, "2026-02-30T00:00:00Z", "sintetica_de_prueba", "plazo_sin_utc_explicito"),
    ("BALOTO", 2714, PLAZO, "calendario_oficial", "procedencia_del_plazo_no_admitida"),
])
def test_g1_compromiso_exige_objetivo_del_registro_y_plazo_utc_sintetico(juego, objetivo, plazo, procedencia, motivo):
    m = _m()
    entradas, bd = _registro()
    with pytest.raises(m.CompromisoInvalido) as error:
        m.construir_compromiso(entradas, bd, codigo_juego=juego, sorteo_objetivo=objetivo, plazo_utc=plazo,
                               procedencia_del_plazo=procedencia)
    assert error.value.motivo == motivo


def test_g1_compromiso_solo_para_la_ruta_1_2_con_vinculo_integro():
    m = _m()
    p10 = rp.construir_protocolo(protocolo_id="sintetico-ae75", estrategia=_estrategia(), cortes=CORTES,
                                 pendientes=[], sintetico=True)
    _, bd = _registro()
    with pytest.raises(m.CompromisoInvalido) as error:
        m.construir_compromiso([rp.serializar_entrada(p10)], bd, codigo_juego="BALOTO", sorteo_objetivo=2714,
                               plazo_utc=PLAZO)
    assert error.value.motivo == "ruta_no_admitida"
    entradas, _ = _registro()
    with pytest.raises(m.CompromisoInvalido) as error:
        m.construir_compromiso(entradas, bd + b" ", codigo_juego="BALOTO", sorteo_objetivo=2714, plazo_utc=PLAZO)
    assert error.value.motivo == "vinculo_no_integro"


# ===========================================================================
# G1: aritmetica temporal exacta y bordes (D8)
# ===========================================================================

def test_g1_instantes_exactos_sin_truncar():
    m = _m()
    assert m.instante_de_plazo("1970-01-01T00:00:00Z") == 0
    assert m.instante_de_plazo("1970-01-01T00:00:01.000000001Z") == 1 + Fraction(1, 10 ** 9)
    assert m.instante_de_gen_time("19700101000000.0000000005Z") == Fraction(5, 10 ** 10)
    assert m.instante_de_gen_time("20260930120000Z") == m.instante_de_plazo("2026-09-30T12:00:00Z")
    assert m.texto_utc(m.instante_de_gen_time("19920722132100.3Z")) == "1992-07-22T13:21:00.3Z"
    assert m.texto_utc(m.instante_de_plazo("2026-10-01T12:00:01.7501Z")) == "2026-10-01T12:00:01.7501Z"
    assert m.segundos_decimales("1.5001") == Fraction(15001, 10000)
    for malo in ("20260930120000.50Z", "20260930120000", "20260930120000+0000", "202609301200Z", "20260930120000.Z"):
        with pytest.raises(ValueError):
            m.instante_de_gen_time(malo)
    with pytest.raises(m.SegundoIntercalar):
        m.instante_de_gen_time("20261231235960Z")
    for malo in ("-1", "1.50", ".5", "1e3", 1):
        with pytest.raises(ValueError):
            m.segundos_decimales(malo)


def test_g1_bordes_de_la_regla_estricta():
    m = _m()
    g, a, margen = Fraction(1000), Fraction(3, 2), Fraction(1, 4)
    superior, inferior = g + a + margen, g - a - margen
    eps = Fraction(1, 10 ** 9)
    assert m.comparar_con_plazo(g, a, margen, superior + eps) == "anterior_al_plazo"
    assert m.comparar_con_plazo(g, a, margen, superior) == "no_concluyente_intervalo_cruza_el_plazo"
    assert m.comparar_con_plazo(g, a, margen, g) == "no_concluyente_intervalo_cruza_el_plazo"
    assert m.comparar_con_plazo(g, a, margen, inferior + eps) == "no_concluyente_intervalo_cruza_el_plazo"
    assert m.comparar_con_plazo(g, a, margen, inferior) == "posterior_al_plazo"
    assert m.comparar_con_plazo(g, a, margen, inferior - eps) == "posterior_al_plazo"
    assert m.comparar_con_plazo(g, Fraction(0), Fraction(0), g) == "posterior_al_plazo"
    assert m.comparar_con_plazo(g, Fraction(0), Fraction(0), g + eps) == "anterior_al_plazo"
    assert m.comparar_con_plazo(g, None, margen, g + 10 ** 6) == "precision_ausente_pendiente"
    assert m.comparar_con_plazo(g, None, Fraction(0), g - 10 ** 6) == "precision_ausente_pendiente"
    with pytest.raises(ValueError):
        m.comparar_con_plazo(g, a, Fraction(-1), superior)


# ===========================================================================
# G1: token de prueba y conclusion temporal separada
# ===========================================================================

def test_g1_token_de_prueba_pasa_lo_criptografico_y_el_plano_sigue_pendiente():
    m = _m()
    informe = _verificar(m, _evidencia(m, gen="2026-10-01T12:00:00.25Z", tsa="propio",
                                       precision=(1, 500, 100)))
    cripto = {k: v.estado for k, v in informe.comprobaciones_criptograficas.items()}
    assert tuple(cripto) == m.COMPROBACIONES_CRIPTOGRAFICAS
    assert cripto.pop("revocacion") == "pendiente"
    assert set(cripto.values()) == {"superada"}
    assert {k: v.estado for k, v in informe.vinculo_del_compromiso.items()} == dict.fromkeys(
        m.COMPROBACIONES_DEL_VINCULO, "superada")
    t = informe.conclusion_temporal
    assert t.resultado == "anterior_al_plazo"
    assert (t.gen_time_utc, t.precision_segundos, t.margen_segundos) == ("2026-10-01T12:00:00.25Z", "1.5001", "0")
    assert (t.limite_inferior_utc, t.limite_superior_utc) == ("2026-10-01T11:59:58.7499Z", "2026-10-01T12:00:01.7501Z")
    assert (t.plazo_utc, t.procedencia_del_plazo) == (PLAZO, "sintetica_de_prueba")
    assert t.condicionada_a == m.LIMITES_OPERATIVOS
    assert informe.estado_del_plano == "pendiente"
    assert informe.motivos_del_plano == ("ancla_de_prueba_no_operativa", "revocacion_sin_comprobar",
                                         "plazo_sintetico_sin_calendario_oficial")
    assert set(informe.no_prueba) >= {"autenticacion_de_r0", "recepcion_de_predicciones",
                                      "completitud_y_unicidad_del_canal", "calendario_oficial"}
    assert "superada" not in m.ESTADOS_DEL_PLANO


@pytest.mark.parametrize("plazo, resultado, estado, motivos", [
    ("2026-10-01T12:00:02.000101Z", "anterior_al_plazo", "pendiente", None),
    ("2026-10-01T12:00:02.0001Z", "no_concluyente_intervalo_cruza_el_plazo", "no_concluyente",
     ("intervalo_cruza_el_plazo",)),
    ("2026-10-01T12:00:00Z", "no_concluyente_intervalo_cruza_el_plazo", "no_concluyente",
     ("intervalo_cruza_el_plazo",)),
    ("2026-10-01T11:59:57.9999Z", "posterior_al_plazo", "rechazada", ("sello_posterior_al_plazo",)),
    ("2026-10-01T11:00:00Z", "posterior_al_plazo", "rechazada", ("sello_posterior_al_plazo",)),
])
def test_g1_bordes_con_tokens_reales(plazo, resultado, estado, motivos):
    """genTime 12:00:00Z, accuracy 1,5001 s y margen 0,5 s: el limite
    superior es 12:00:02.0001Z y el inferior 11:59:57.9999Z."""
    m = _m()
    evidencia = _evidencia(m, compromiso=_compromiso(m, plazo=plazo), precision=(1, 500, 100))
    informe = _verificar(m, evidencia, politica=_politica(m, margen="0.5"))
    assert informe.conclusion_temporal.resultado == resultado
    assert informe.conclusion_temporal.limite_superior_utc == "2026-10-01T12:00:02.0001Z"
    assert informe.conclusion_temporal.limite_inferior_utc == "2026-10-01T11:59:57.9999Z"
    assert informe.estado_del_plano == estado
    assert informe.motivos_del_plano == (motivos or m.LIMITES_OPERATIVOS)


def test_g1_precision_ausente_queda_pendiente_y_no_vale_cero():
    m = _m()
    informe = _verificar(m, _evidencia(m, precision=None))
    assert informe.conclusion_temporal.resultado == "precision_ausente_pendiente"
    assert informe.conclusion_temporal.precision_segundos is None
    assert informe.conclusion_temporal.limite_superior_utc is None
    assert informe.estado_del_plano == "pendiente"
    assert informe.motivos_del_plano[0] == "precision_ausente"
    cero = _verificar(m, _evidencia(m, precision=(None, None, None)))
    assert cero.conclusion_temporal.precision_segundos == "0"
    assert cero.conclusion_temporal.resultado == "anterior_al_plazo"


def test_g1_fraccion_de_gen_time_no_se_trunca():
    """rfc3161-client 1.0.9 entrega 12:00:00; con el genTime exacto
    12:00:00.25 y accuracy 0,1 s el intervalo cruza un plazo de 12:00:00.3."""
    m = _m()
    compromiso = _compromiso(m, plazo="2026-10-01T12:00:00.3Z")
    informe = _verificar(m, _evidencia(m, compromiso=compromiso, gen="2026-10-01T12:00:00.25Z",
                                       precision=(None, 100, None)))
    assert informe.comprobaciones_criptograficas["gen_time_coherente"].estado == "superada"
    assert informe.conclusion_temporal.gen_time_utc == "2026-10-01T12:00:00.25Z"
    assert informe.conclusion_temporal.resultado == "no_concluyente_intervalo_cruza_el_plazo"


# ===========================================================================
# G1: manipulaciones independientes
# ===========================================================================

_MANIPULACIONES = [
    ("firma", dict(alterar_firma=True), "firma_del_token", "firma_del_token_no_coincide"),
    ("contenido_tras_firmar", dict(alterar_contenido_tras_firmar=True), "atributos_firmados",
     "message_digest_no_coincide"),
    ("content_type_firmado", dict(content_type_firmado=f.OID_DATA), "atributos_firmados",
     "atributo_content_type_incorrecto"),
    ("certificado_de_otra_ca", dict(firmante="tsa_ajena"), "cadena_hasta_el_ancla", "cadena_sin_ancla"),
    ("intermedia_no_incluida", dict(firmante="tsa_via_intermedia"), "cadena_hasta_el_ancla", "cadena_sin_ancla"),
    ("eku_no_critica", dict(firmante="tsa_eku_no_critica"), "proposito_de_sellado", "uso_extendido_no_critico"),
    ("eku_con_otro_proposito", dict(firmante="tsa_eku_extra"), "proposito_de_sellado", "uso_extendido_no_exclusivo"),
    ("sin_eku", dict(firmante="tsa_sin_eku"), "proposito_de_sellado", "uso_extendido_ausente"),
    ("certificado_caducado", dict(firmante="tsa_caducada"), "vigencia_en_gen_time",
     "certificado_no_vigente_en_gen_time"),
    ("extension_critica_en_certificado", dict(firmante="tsa_extension_desconocida"), "extensiones_criticas",
     "extension_critica_desconocida"),
    ("extension_critica_en_tstinfo", dict(extension_critica_en_tstinfo=True), "extensiones_criticas",
     "extension_critica_desconocida"),
    ("identificador_de_otro_certificado", dict(identificador="v2_otro_certificado"), "identificador_del_certificado",
     "identificador_de_certificado_no_coincide"),
    ("identificador_solo_sha1", dict(identificador="v1"), "identificador_del_certificado",
     "identificador_de_certificado_solo_sha1"),
    ("sin_identificador", dict(identificador="ninguno"), "identificador_del_certificado",
     "identificador_de_certificado_ausente"),
    ("politica_no_admitida", dict(politica=f.POLITICA_NO_ADMITIDA), "politica_admitida", "politica_no_admitida"),
    ("nombre_tsa_ajeno", dict(tsa="ajeno"), "nombre_de_la_tsa", "nombre_de_la_tsa_no_coincide"),
    ("impronta_de_otros_bytes", dict(impronta=b"\x11" * 32), "impronta_coincide", "impronta_no_coincide"),
    ("impronta_sha1", dict(algoritmo_impronta="sha1"), "impronta_coincide", "algoritmo_de_impronta_no_admitido"),
    ("precision_mal_formada", dict(precision=(None, 0, None)), "estructura_del_token", "precision_mal_formada"),
    ("estado_concedido_con_cambios", dict(estado=1), "estado_concedido", "estado_pki_no_concedido"),
    ("estado_rechazado", dict(estado=2), "estado_concedido", "estado_pki_no_concedido"),
]


@pytest.mark.parametrize("nombre, opciones, comprobacion, motivo", _MANIPULACIONES,
                         ids=[x[0] for x in _MANIPULACIONES])
def test_g1_cada_manipulacion_se_rechaza_con_causa_y_sin_leer_el_tiempo(nombre, opciones, comprobacion, motivo):
    m = _m()
    informe = _verificar(m, _evidencia(m, gen="2026-10-01T12:00:00Z", **opciones))
    resultado = _todas(informe)[comprobacion]
    assert resultado.estado == "rechazada" and motivo in resultado.motivos, (nombre, resultado)
    assert informe.estado_del_plano == "rechazada"
    assert motivo in informe.motivos_del_plano
    assert informe.conclusion_temporal.resultado == "no_evaluable"
    assert informe.conclusion_temporal.gen_time_utc is None


def test_g1_la_verificacion_integral_de_openssl_coincide_en_firma_cadena_y_proposito():
    m = _m()
    for opciones in (dict(alterar_firma=True), dict(firmante="tsa_ajena"), dict(firmante="tsa_eku_extra"),
                     dict(firmante="tsa_caducada"), dict(alterar_contenido_tras_firmar=True)):
        informe = _verificar(m, _evidencia(m, **opciones))
        integral = informe.comprobaciones_criptograficas["verificacion_integral"]
        assert integral.estado == "rechazada", opciones
        assert integral.motivos == ("verificacion_integral_no_superada",)
    valida = _verificar(m, _evidencia(m, firmante="tsa_via_intermedia", incluidos=("firmante", "intermedia")))
    assert valida.comprobaciones_criptograficas["cadena_hasta_el_ancla"].estado == "superada"
    assert valida.comprobaciones_criptograficas["verificacion_integral"].estado == "superada"


def test_g1_vinculo_de_bytes_incorrecto_se_rechaza():
    m = _m()
    c = _compromiso(m)
    for cambio, motivo in (({"hash_declaracion": "0" * 64}, "hash_de_declaracion_no_coincide"),
                           ({"protocolo_hash": "0" * 64}, "protocolo_hash_no_coincide"),
                           ({"regla": "ae73-vinculo-r0-campo-explicito/1"}, "contrato_o_regla_no_coincide")):
        informe = _verificar(m, _evidencia(m, compromiso={**c, **cambio}))
        r = informe.vinculo_del_compromiso["compromiso_corresponde_al_registro"]
        assert r.estado == "rechazada" and motivo in r.motivos
        assert informe.comprobaciones_criptograficas["firma_del_token"].estado == "superada"
        assert informe.estado_del_plano == "rechazada"
    evidencia = _evidencia(m)
    otra = _compromiso(m, plazo="2026-10-11T00:00:00Z")
    cambiada = m.EvidenciaDeSello(evidencia.respuesta_der, m.bytes_de_compromiso(otra))
    informe = _verificar(m, cambiada)
    assert informe.vinculo_del_compromiso["impronta_coincide"].motivos == ("impronta_no_coincide",)
    assert informe.comprobaciones_criptograficas["verificacion_integral"].estado == "rechazada"


def test_g1_un_sello_no_se_reutiliza_para_otro_objetivo():
    m = _m()
    registro = _registro((2714, 2715))
    evidencia = _evidencia(m, compromiso=_compromiso(m, registro=registro))
    propio = _verificar(m, evidencia, registro=registro, objetivo=2714)
    assert propio.estado_del_plano == "pendiente"
    ajeno = _verificar(m, evidencia, registro=registro, objetivo=2715)
    assert ajeno.vinculo_del_compromiso["objetivo_corresponde"].motivos == ("objetivo_no_coincide",)
    assert ajeno.estado_del_plano == "rechazada"
    otro_juego = _verificar(m, evidencia, registro=registro, juego="BALOTO_REVANCHA")
    assert "objetivo_no_coincide" in otro_juego.vinculo_del_compromiso["objetivo_corresponde"].motivos


def test_g1_objetivo_y_plazo_manipulados_dentro_de_lo_sellado():
    m = _m()
    c = _compromiso(m)
    casos = (({"sorteo_objetivo": 2713}, "objetivo_corresponde", "objetivo_no_posterior_al_corte", 2713),
             ({"codigo_juego": "MILOTO"}, "objetivo_corresponde", "juego_fuera_del_protocolo", 2714),
             ({"plazo_utc": "2026-10-10T00:00:00"}, "plazo_utc_explicito", "plazo_sin_utc_explicito", 2714),
             ({"procedencia_del_plazo": "calendario_oficial"}, "plazo_utc_explicito",
              "procedencia_del_plazo_no_admitida", 2714))
    for cambio, comprobacion, motivo, objetivo in casos:
        juego = cambio.get("codigo_juego", "BALOTO")
        informe = _verificar(m, _evidencia(m, compromiso={**c, **cambio}), juego=juego, objetivo=objetivo)
        r = informe.vinculo_del_compromiso[comprobacion]
        assert r.estado == "rechazada" and motivo in r.motivos, (cambio, r)
        assert informe.conclusion_temporal.resultado == "no_evaluable"


def test_g1_respuesta_ilegible_sin_ancla_y_dependencia_ausente():
    m = _m()
    evidencia = _evidencia(m)
    ilegible = _verificar(m, m.EvidenciaDeSello(b"\x30\x03\x02\x01\x00", evidencia.bytes_compromiso))
    assert ilegible.comprobaciones_criptograficas["respuesta_decodificada"].motivos == ("respuesta_ilegible",)
    assert ilegible.estado_del_plano == "rechazada"
    sin_ancla = _verificar(m, evidencia, politica=_politica(m, anclas=()))
    assert sin_ancla.comprobaciones_criptograficas["verificacion_integral"].motivos == ("sin_ancla_configurada",)
    assert sin_ancla.estado_del_plano == "pendiente"
    assert sin_ancla.conclusion_temporal.resultado == "no_evaluable"


def test_g1_dependencia_criptografica_ausente_deja_pendiente(monkeypatch):
    m = _m()

    def ausente():
        raise ImportError("rfc3161_client no instalado")

    monkeypatch.setattr(m, "_bibliotecas", ausente)
    informe = _verificar(m, _evidencia(m))
    assert {v.motivos for v in informe.comprobaciones_criptograficas.values()} == {
        ("dependencia_criptografica_ausente",)}
    assert informe.vinculo_del_compromiso["impronta_coincide"].estado == "pendiente"
    assert informe.estado_del_plano == "pendiente"
    assert informe.conclusion_temporal.resultado == "no_evaluable"


def test_g1_politica_y_anclas_solo_de_prueba():
    m = _m()
    assert m.NATURALEZAS_DE_ANCLA == ("fixture_de_prueba",) and m.ANCLAS_OPERATIVAS_APROBADAS == ()
    with pytest.raises(ValueError):
        m.AnclaDePrueba(f.der(f.mundo().ca), "x", naturaleza="operativa")
    for politicas, margen in (((), "0"), (("no-es-oid",), "0"), ((f.POLITICA_DE_PRUEBA,), "-1"),
                              ((f.POLITICA_DE_PRUEBA,), "0.10")):
        with pytest.raises(ValueError):
            m.PoliticaDeConfianzaTemporal(anclas=(), politicas_admitidas=politicas, margen=margen)
    assert "margen" in inspect.signature(m.PoliticaDeConfianzaTemporal).parameters
    assert inspect.signature(m.PoliticaDeConfianzaTemporal).parameters["margen"].default is inspect.Parameter.empty


# ===========================================================================
# G1: contraste independiente
# ===========================================================================

def test_g1_token_emitido_por_openssl_se_verifica_con_las_bibliotecas():
    m = _m()
    respuesta, ca, datos = f.openssl_fijado()
    assert datos == m.bytes_de_compromiso(_compromiso(m, plazo="2026-10-10T00:00:00Z"))
    politica = _politica(m, anclas=(m.AnclaDePrueba(ca, "CA de prueba AE-75 creada con openssl (fixture)"),))
    informe = _verificar(m, m.EvidenciaDeSello(respuesta, datos), politica=politica)
    cripto = {k: v.estado for k, v in informe.comprobaciones_criptograficas.items()}
    assert cripto.pop("revocacion") == "pendiente" and set(cripto.values()) == {"superada"}
    assert informe.conclusion_temporal.resultado == "anterior_al_plazo"
    assert informe.conclusion_temporal.precision_segundos == "1.5001"
    assert informe.estado_del_plano == "pendiente"
    ajena = _verificar(m, m.EvidenciaDeSello(respuesta, datos))
    assert ajena.comprobaciones_criptograficas["cadena_hasta_el_ancla"].estado == "rechazada"


@pytest.mark.skipif(shutil.which("openssl") is None,
                    reason="sin OpenSSL en PATH: el contraste con `openssl ts -verify` queda pendiente aqui")
@pytest.mark.parametrize("opciones, acepta", [
    (dict(), True), (dict(tsa="propio", precision=(0, 1, 1)), True), (dict(alterar_firma=True), False),
    (dict(firmante="tsa_eku_extra"), False), (dict(identificador="v2_otro_certificado"), False),
    (dict(alterar_contenido_tras_firmar=True), False), (dict(firmante="tsa_ajena"), False),
])
def test_g1_contraste_con_openssl_ts_verify(tmp_path, opciones, acepta):
    """Contraste independiente: OpenSSL (`openssl ts -verify`) y la ruta de
    este modulo coinciden al aceptar o rechazar los mismos tokens."""
    m = _m()
    evidencia = _evidencia(m, **opciones)
    (tmp_path / "r.tsr").write_bytes(evidencia.respuesta_der)
    (tmp_path / "d.bin").write_bytes(evidencia.bytes_compromiso)
    (tmp_path / "ca.pem").write_bytes(f.pem(f.mundo().ca))
    salida = subprocess.run(["openssl", "ts", "-verify", "-data", str(tmp_path / "d.bin"), "-in",
                             str(tmp_path / "r.tsr"), "-CAfile", str(tmp_path / "ca.pem")],
                            capture_output=True, text=True, check=False)
    assert (salida.returncode == 0 and "Verification: OK" in salida.stdout) is acepta, salida.stderr
    informe = _verificar(m, evidencia)
    assert (informe.estado_del_plano == "pendiente") is acepta


# ===========================================================================
# G1: plano temporal separado del contrato de AE-74
# ===========================================================================

def test_g1_plano_temporal_separado_y_r0_final_intacta():
    m = _m()
    entradas, bd = _registro()
    evidencias = {("BALOTO", 2714): _evidencia(m)}
    informe = m.evaluar_admision_con_plano_temporal(entradas, bd, evidencias, _politica(m))
    base = cv.evaluar_admision(entradas, bd)
    assert _plano(informe.admision) == _plano(base)
    assert informe.admision.puertas["r0_final"].estado == "rechazada"
    assert informe.admision.puertas["r0_final"].motivos == base.puertas["r0_final"].motivos
    assert informe.plano_temporal == "pendiente"
    assert informe.planos == {**base.planos, "sello_temporal_de_r0": "pendiente"}
    for plano in ("autenticacion_de_r0", "recepcion_antes_del_plazo", "completitud_y_unicidad_del_canal"):
        assert informe.planos[plano] == "sin_evidencia"
    assert informe.planos["aptitud_inferencial"] == "no_autorizada"
    assert informe.sellos[("BALOTO", 2714)].conclusion_temporal.resultado == "anterior_al_plazo"


def test_g1_plano_temporal_agrega_por_objetivo():
    m = _m()
    registro = _registro((2714, 2715))
    entradas, bd = registro
    politica = _politica(m)
    vacio = m.evaluar_admision_con_plano_temporal(entradas, bd, {}, politica)
    assert (vacio.plano_temporal, vacio.motivos_del_plano) == ("sin_evidencia", ())
    falta = m.evaluar_admision_con_plano_temporal(
        entradas, bd, {("BALOTO", 2714): _evidencia(m, compromiso=_compromiso(m, registro=registro))}, politica,
        objetivos_esperados=[("BALOTO", 2714), ("BALOTO", 2715)])
    assert falta.plano_temporal == "pendiente" and "objetivo_sin_sello" in falta.motivos_del_plano
    malo = m.evaluar_admision_con_plano_temporal(entradas, bd, {
        ("BALOTO", 2714): _evidencia(m, compromiso=_compromiso(m, registro=registro)),
        ("BALOTO", 2715): _evidencia(m, compromiso=_compromiso(m, registro=registro, objetivo=2715),
                                     alterar_firma=True)}, politica)
    assert malo.plano_temporal == "rechazada"
    assert malo.admision.puertas["r0_final"].estado == "rechazada"
    cruza = m.evaluar_admision_con_plano_temporal(entradas, bd, {
        ("BALOTO", 2714): _evidencia(m, compromiso=_compromiso(m, registro=registro, plazo=GEN))}, politica)
    assert (cruza.plano_temporal, cruza.motivos_del_plano) == ("no_concluyente", ("intervalo_cruza_el_plazo",))
    v11 = {"regla": "ae73-vinculo-r0-campo-explicito/1", "esquema_declaracion": "declaracion-r0-sintetica/1",
           "hash_declaracion": rp.hash_entrada(bd), "pendientes": []}
    p11 = rp.construir_protocolo_con_vinculo_r0(protocolo_id="sintetico-ae75", estrategia=_estrategia(),
                                                cortes=CORTES, pendientes=[], sintetico=True, vinculo_r0=v11)
    ruta = m.evaluar_admision_con_plano_temporal([rp.serializar_entrada(p11)], bd, {("BALOTO", 2714): _evidencia(m)},
                                                 politica)
    assert (ruta.plano_temporal, ruta.motivos_del_plano, ruta.sellos) == ("no_evaluable", ("ruta_no_admitida",), {})


def test_g1_motivos_y_estados_del_vocabulario():
    m = _m()
    vistos = set()
    for _, opciones, _, _ in _MANIPULACIONES:
        informe = _verificar(m, _evidencia(m, **opciones))
        vistos |= _motivos(informe) | set(informe.motivos_del_plano)
        assert {c.estado for c in _todas(informe).values()} <= set(m.ESTADOS_DE_COMPROBACION)
        assert informe.estado_del_plano in m.ESTADOS_DEL_PLANO
    assert vistos <= set(m.MOTIVOS), vistos - set(m.MOTIVOS)
    assert len(m.MOTIVOS) == len(set(m.MOTIVOS))
    assert set(m.HERRAMIENTAS) == set(m.COMPROBACIONES_DEL_VINCULO) | set(m.COMPROBACIONES_CRIPTOGRAFICAS)
    assert set(m.RESULTADOS_TEMPORALES) >= {"anterior_al_plazo", "posterior_al_plazo", "no_evaluable",
                                            "no_concluyente_intervalo_cruza_el_plazo", "precision_ausente_pendiente"}
    nombres = [*m.ESTADOS_DEL_PLANO, *m.ESTADOS_DE_COMPROBACION, *m.MOTIVOS, *m.RESULTADOS_TEMPORALES,
               *m.COMPROBACIONES_DEL_VINCULO, *m.COMPROBACIONES_CRIPTOGRAFICAS, m.PLANO_TEMPORAL]
    for nombre in nombres:
        assert not re.search(r"autenticad|acreditad|fijad|aprobad|(?<!in)valid|verificad|apt[ao]", nombre), nombre


_PROHIBIDAS = {"go", "cumplido", "cumplida", "desbloqueado", "desbloqueada", "autorizado", "autorizada",
               "autenticado", "autenticada", "acreditado", "acreditada", "fijado", "fijada", "valido", "valida",
               "verificado", "verificada", "operativo_aprobado"}


def test_g1_herramientas_fuentes_y_politica_documentadas():
    m = _m()
    assert "OpenSSL" in m.HERRAMIENTAS["verificacion_integral"][0]
    assert "rfc3161-client" in m.HERRAMIENTAS["verificacion_integral"][0]
    assert "cryptography" in m.HERRAMIENTAS["firma_del_token"][0]
    assert "hazmat.asn1" in m.HERRAMIENTAS["identificador_del_certificado"][0]
    assert "sin fraccion" in m.HERRAMIENTAS["gen_time_coherente"][1]
    assert m.HERRAMIENTAS["revocacion"][0] == "ninguna"
    ids = [c.id for c in m.FUENTES_PRIMARIAS]
    assert ids == [f"E{i}" for i in range(1, 18)]
    for c in m.FUENTES_PRIMARIAS:
        assert c.fuente in ("rfc_3161", "rfc_5816") and c.lineas[0] <= c.lineas[1] and c.cita and c.alcance
    assert {c.fuente for c in m.FUENTES_PRIMARIAS} == {"rfc_3161", "rfc_5816"}
    assert set(m.POLITICA_ELEGIDA) == {f"P{i}" for i in range(1, 14)}
    assert "SHA-1" in m.POLITICA_ELEGIDA["P6"]["base"] and "SHOULD" in m.POLITICA_ELEGIDA["P5"]["base"]
    assert any("calendario oficial" in r for r in m.REQUISITOS_PARA_USO_OPERATIVO)
    assert any("AUTENTICACION_DE_R0" in r for r in m.REQUISITOS_PARA_USO_OPERATIVO)
    textos = [*(t for _, t in m.HERRAMIENTAS.values()), *(v["texto"] for v in m.POLITICA_ELEGIDA.values()),
              *m.REQUISITOS_PARA_USO_OPERATIVO, *(c.alcance for c in m.FUENTES_PRIMARIAS)]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS
    assert not any("9162" in t for t in textos)


def test_g1_modulo_sin_reloj_local_red_ni_archivos():
    m = _m()
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess", "random", "os", "pathlib",
                  "sqlalchemy", "shutil", "tempfile"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
            assert not (nodo.module or "").startswith("app.infrastructure")
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "today", "utcnow", "time", "getmtime", "stat", "fromtimestamp"}, nodo.attr
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id not in {"open", "eval", "exec"}
        if isinstance(nodo, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            objetivos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            assert not any(isinstance(o, ast.Attribute) for o in objetivos)


# ===========================================================================
# G1: D8 registrada solo para el modelo sintetico y dependencias
# ===========================================================================

def test_g1_d8_aprobada_solo_para_el_modelo_sintetico():
    d8 = cv.DECISIONES_DEL_CONTRATO["D8"]
    assert d8["estado"] == "aprobada_solo_para_el_modelo_sintetico"
    for fragmento in ("genTime + accuracy + margen < plazo", "la igualdad no pasa", "no es concluyente",
                      "queda pendiente", "calendario_oficial siguen sin fijar", "plazo sintetico explicito"):
        assert fragmento in d8["texto"], fragmento
    assert "D8" in cv.__doc__ and "evaluar_admision` no cambia" in cv.__doc__


def test_g1_dependencias_criptograficas_fijadas_en_requirements():
    lineas = (RAIZ / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert "cryptography==50.0.1" in lineas
    assert "rfc3161-client==1.0.9" in lineas


# ===========================================================================
# G2: invariantes (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae63_a_ae74():
    assert _huella((rp.ESQUEMA_ENTRADA, rp.TIPOS_ENTRADA, rp.REGLAS_EVALUACION_AE52, rp.PENDIENTES_BORRADOR_AE52,
                    rp.NOTA_PROTOCOLO, rp.ALCANCE_REGISTRO)) == (
        "4f31cdeb3c4d29b1740592d4d81de2f8f51305abf4a82743c49f12985621c50b")
    assert _huella((tc.CONDICIONES_DE_TRASLADO, tc.DECISIONES_DEL_OPERADOR_AE63,
                    tc.ENUNCIADOS_DE_FUENTE_NECESARIOS)) == (
        "2600313c17c65eab1b6f69c5a9abe3708f87f951df57edca6266ef46bc014186")
    assert _huella((vp.PROCEDENCIA_V6, vp.LECTURA_POR_PUNTO, vp.ENUNCIADOS_NULAS_Y_E_PROCESOS, vp.DISCREPANCIAS,
                    vp.DEPENDENCIAS_DE_N2, vp.DERIVACION_1_SOBRE_E_TEOREMA_3, vp.ESTADOS_TRAS_AE64)) == (
        "631091da5a81a5097ad2d840043085fd43cec1929dcddd17644222121e91e054")
    assert _huella((ao.OBLIGACIONES_AE65, ao.EVIDENCIA_REQUERIDA_O3, ao.ASPECTOS_DE_PREDICTIBILIDAD,
                    ao.COMPONENTES_DE_F2, ao.CONSECUENCIAS, ao.OBSERVACION_DEPENDENCIA_O3_COMUN,
                    ao.HIPOTESIS_UNIFORMIDAD_CONDICIONAL, ao.NIVELES_DE_ANTERIORIDAD, ao.USOS)) == (
        "209cf5282031f5489c5f75e7497cc680dd15f73b190144491e4fbea36ea03b7f")
    assert _huella((pe.REQUISITOS, pe.COLUMNAS_DE_LA_MATRIZ, pe.ESTADOS_DE_CELDA, pe.RESULTADOS_OMISION_DECLARADA,
                    pe.RESULTADOS_AUSENCIA_INFERIDA, pe.FUENTES_PRIMARIAS, pe.ALTERNATIVAS, pe.COMPLEMENTOS,
                    pe.CONDICIONES_PENDIENTES_DEL_PROTOCOLO, pe.NO_DEMUESTRA_NINGUNA, pe.PREGUNTAS_ABIERTAS,
                    pe.RECOMENDACION_CONDICIONAL)) == (
        "17f9e0ba301092c76fc412063d5ad5f764dd6412d8feaeb76cd307ef018c639a")
    assert _huella((vr.PROCEDENCIA_RFC, vr.ESTADOS_AFIRMACION, vr.AFIRMACIONES_RFC_3161, vr.AFIRMACIONES_RFC_9162,
                    vr.CONDICIONES_DEL_REPOSITORIO, vr.DISCREPANCIAS_CON_AE66, vr.DERIVACION_MARGEN_RFC_9162,
                    vr.RESULTADOS_SELLO)) == "eb094cddc0659b3b4e015922025db9ca3327116d10677677a26224270da857c5"
    assert _huella((ec.ALCANCE_RFC_9162, ec.MODELO_DE_FIRMA, ec.AUTENTICACION_DE_R0, ec.REQUISITOS_PREVIOS,
                    ec.CONDICIONES_DEL_PROTOCOLO, ec.CORRESPONDENCIA_CON_AE66, ec.DEPENDENCIAS_NORMATIVAS,
                    ec.DEPENDENCIAS_DE_VERIFICACION, ec.INSTANTES, ec.HIPOTESIS_TEMPORALES,
                    ec.LIMITE_DE_COMPLETITUD, tuple(ec.REGLAS_DE_DUPLICADOS_CANDIDATAS),
                    ec.REGLA_DE_DUPLICADOS_ELEGIDA, ec.RESULTADOS_RELOJ, ec.REQUISITOS_DE_VIA,
                    ec.RESULTADOS_DE_VIA)) == "03c83bb1719e68bc14744bde36971f92a7a0f45784512424566305c2f504b00d"
    assert _huella((iv.SITUACIONES_EN_AE52, iv.RELACION_CON_AE52, iv.ELEMENTOS_DE_R0, iv.ESTADO_ACTUAL_DE_R0,
                    iv.CORRESPONDENCIA_CON_PENDIENTES_AE52, iv.PREGUNTAS_ABIERTAS_AE69, iv.ESTADOS_DE_ELEMENTO,
                    iv.RESULTADOS_DECLARACION, iv.ALCANCE_DE_LA_COMPLETITUD, iv.TRATAMIENTO_DE_VALORES_VACIOS,
                    iv.CLASES_DE_AFIRMACION, iv.CLASIFICACION_DE_AFIRMACIONES)) == (
        "b5637fe7ee274d0a9b63d6a87837dd9d0e0a6a108772e10c26dde23c55d83a24")
    assert _huella((vv.SUPUESTOS_DEL_MODELO, vv.TOPOLOGIAS_DE_VINCULO, vv.CRITERIOS_DE_VINCULO, vv.ESTADOS_DE_CELDA,
                    vv.MATRIZ_DE_VINCULO, vv.TOPOLOGIA_ELEGIDA, vv.REPRESENTACIONES_DE_PENDIENTES,
                    vv.REPRESENTACION_ELEGIDA, vv.CONSECUENCIA_DE_COMPLETAR_DESPUES, vv.ALCANCE_DEL_ANALISIS,
                    vv.CLASIFICACION_DE_AFIRMACIONES)) == (
        "23c622009ec080a506d4f8f299b02382ff5229bb1a6aed162f88a7ab64648350")
    assert _huella((aa.SEPARACION_DE_PLANOS, aa.SUPUESTOS_ADICIONALES_AE71, aa.HIPOTESIS_PARA_CRONOLOGIA,
                    aa.COMPONENTES_DE_FIJADO, aa.DISTINCION_DE_ESTADOS, aa.LAGUNAS_DE_DISTINCION,
                    aa.ESTADOS_VERIFICABLES, aa.DECISIONES_DEL_OPERADOR_AE71, aa.DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR,
                    aa.RELACIONES_DE_BYTES, aa.MARCA_SIN_CRONOLOGIA, aa.FICHAS_POR_TOPOLOGIA,
                    aa.ALCANCE_DEL_ANALISIS_AE71, aa.CLASIFICACION_DE_AFIRMACIONES)) == (
        "5f28e0924a986bbf157ad086333f940acf04becf9ccedbd0d22931eda75c8de7")
    assert _huella((pv.ESQUEMA_DECLARACION, pv.TOPOLOGIA_CANDIDATA, pv.ESTADO_DE_LA_TOPOLOGIA, pv.ACTIVACION,
                    pv.REGLA_CANDIDATA, pv.CLAVE_RESERVADA, pv.RUTA_DEL_HASH, pv.COMPARACION_DE_TOPOLOGIAS,
                    pv.ESTADOS_DE_ELEMENTO, pv.RESUMENES_DE_DECLARACION, sorted(pv.MARCADORES_TEXTUALES),
                    pv.PLANOS_DEL_INFORME, pv.ESTADOS_DE_BYTES, pv.ESTADOS_DE_PLANO,
                    pv.CONSECUENCIA_DE_COMPLETAR_UN_PENDIENTE, pv.COMPATIBILIDAD, pv.LIMITES_DEL_PROTOTIPO,
                    pv.DECISIONES_REQUERIDAS, pv.CRITERIOS_PARA_PROMOVER, pv.CRITERIOS_PARA_DESCARTAR)) == (
        "f5dad07207a06be891b99b0378f69328c6557ed7e7e216130344d2122c157926")
    assert _huella((rp.ESQUEMA_ENTRADA_PROTOCOLO_VINCULO_R0, rp.ESQUEMAS_PROTOCOLO, rp.CAMPO_VINCULO_R0,
                    rp.REGLA_VINCULO_R0_CAMPO_EXPLICITO, rp.ESQUEMA_DECLARACION_R0, rp.MOTIVOS_VINCULO_R0,
                    ve.RUTAS, ve.ESTADO_DE_LAS_RUTAS, ve.ACTIVACION, ve.PLANOS_DEL_INFORME, ve.ESTADOS_DE_BYTES,
                    ve.COMPARACION_DE_RUTAS, ve.REQUISITOS_DE_MIGRACION, ve.MIGRACION_EJECUTADA,
                    ve.DECISIONES_REQUERIDAS, ve.COMPATIBILIDAD, ve.LIMITES)) == (
        "0ab953f95566948581dbb8cbad19797ecf44ae55f2943491441a2f414047a54d")
    assert _huella((rp.ESQUEMA_ENTRADA_PROTOCOLO_CONTRATO_R0, rp.CONTRATO_VINCULO_R0, rp.REGLA_VINCULO_R0_CONTRATO,
                    rp.MOTIVOS_VINCULO_R0_CONTRATO, cv.CONTRATO, cv.ESQUEMA_DEL_PROTOCOLO, cv.REGLA, cv.PUERTAS,
                    cv.ESTADOS_DE_PUERTA, cv.RUTAS, cv.MOTIVOS_DE_PUERTA, cv.TRANSICIONES,
                    cv.ESCENARIOS_DE_DEMOSTRACION, cv.RUTAS_COMPATIBLES, cv.REQUISITOS_FALTANTES,
                    cv.COMPATIBILIDAD, cv.LIMITES)) == (
        "752c360d7dc87de0f954e4f226510bc05b0f99a50ffe05705d3ca6a12ecbb21f")
    assert _huella({k: v for k, v in cv.DECISIONES_DEL_CONTRATO.items() if k != "D8"}) == (
        "1e20374698c18de98b8b1686bc9f8aa9ba317584ae1fbc2f83205a532be91b81")


def test_g2_bytes_y_hashes_de_1_0_1_1_y_1_2_intactos():
    p = rp.construir_protocolo(protocolo_id="sintetico-ae73", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                               sintetico=True)
    b = rp.serializar_entrada(p)
    assert rp.hash_entrada(b) == "c9e73601ac6d9668a3e50c8e76b75a130b214a68efaf5cf115b17d5a67ea3892"
    pred = rp.nueva_prediccion(rp.validar_registro([b]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                               PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(pred)) == (
        "435918926917ea8ab712c7162eff5544998d340f3df711b1508815ce6429f2c6")
    assert rp.hash_entrada(rp.serializar_entrada(rp.construir_protocolo_borrador(_estrategia()))) == (
        "4b0096fea982e015c0ee8c2561c82d44d2b4ae5923383c5433a7c4dcaacd2d68")
    v11 = {"regla": "ae73-vinculo-r0-campo-explicito/1", "esquema_declaracion": "declaracion-r0-sintetica/1",
           "hash_declaracion": "1" * 64, "pendientes": ["regla_de_duplicados"]}
    p11 = rp.construir_protocolo_con_vinculo_r0(protocolo_id="sintetico-ae74", estrategia=_estrategia(), cortes=CORTES,
                                                pendientes=[], sintetico=True, vinculo_r0=v11)
    b11 = rp.serializar_entrada(p11)
    assert rp.hash_entrada(b11) == "9ded8373d753fa68473b91728d900340e996c5af46ced4d2cc94ef5f56e80d0b"
    pred11 = rp.nueva_prediccion(rp.validar_registro([b11]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                                 PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(pred11)) == (
        "b9576ab70dede1a399e390946ad819d0792f24b3e946bbdfd67fe7bf603abc4a")
    declaracion = pv.construir_declaracion(_elementos())
    bd = pv.bytes_de_declaracion(declaracion)
    assert rp.hash_entrada(bd) == "5c75c5051d6343dc6463e70946d77b21db9da49b0033197ced558832933fced4"
    p12 = cv.construir_protocolo_del_contrato(declaracion, protocolo_id="sintetico-ae74", estrategia=_estrategia(),
                                              cortes=CORTES)
    b12 = rp.serializar_entrada(p12)
    assert rp.hash_entrada(b12) == "68e3660d19fe49c56e619d5d1b3b9260fa1cce2d53291deee2ea900c69f76c7c"
    pred12 = rp.nueva_prediccion(rp.validar_registro([b12]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                                 PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(pred12)) == (
        "cd648d5cb0013b3bf5b750351c83ecce3a2436318cdb7a75c808c5e0841b36ec")


def test_g2_estados_y_bloqueos_sin_cambios():
    assert pi.AUTORIZA_EVALUACION is False
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert {r.estado for r in ec.REQUISITOS_PREVIOS.values()} == {"sin_fijar"}
    assert {r.estado for r in ec.CONDICIONES_DEL_PROTOCOLO.values()} == {"sin_fijar"}
    assert len(ec.CONDICIONES_DEL_PROTOCOLO) == 8
    assert ec.CONDICIONES_DEL_PROTOCOLO["calendario_oficial"].estado == "sin_fijar"
    assert set(vr.CONDICIONES_DEL_REPOSITORIO.values()) == {"sin_fijar"}
    assert "calendario_oficial" in vr.CONDICIONES_DEL_REPOSITORIO
    assert set(iv.ESTADO_ACTUAL_DE_R0.values()) == {"pendiente"}
    assert {v["estado"] for v in iv.PREGUNTAS_ABIERTAS_AE69.values()} == {"sin_respuesta"}
    for pendiente in ("mecanismo_de_sellado_temporal_externo", "corte_temporal_por_juego"):
        assert pendiente in rp.PENDIENTES_BORRADOR_AE52
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    assert {v["estado"] for v in aa.DECISIONES_DEL_OPERADOR_AE71.values()} == {"sin_decidir"}
    assert cv.DECISIONES_DEL_CONTRATO["D9"]["estado"] == "espera_provisional_aprobada"


def test_g2_evaluar_admision_sin_evidencia_y_r0_final_rechazada():
    assert "evidencia" not in " ".join(inspect.signature(cv.evaluar_admision).parameters)
    entradas, bd = _registro()
    informe = cv.evaluar_admision(entradas, bd)
    assert informe.puertas["r0_final"].estado == "rechazada"
    assert "protocolo_sintetico" in informe.puertas["r0_final"].motivos
    assert informe.planos["recepcion_antes_del_plazo"] == "sin_evidencia"
    assert "sello_temporal_de_r0" not in informe.planos


# ===========================================================================
# G3: premisas sobre codigo existente y bibliotecas
# ===========================================================================

def test_g3_el_corte_es_un_numero_de_sorteo_y_no_un_instante():
    entradas, _ = _registro()
    protocolo = rp.validar_registro(list(entradas)).protocolo
    assert protocolo["juegos"]["BALOTO"] == {"ultimo_sorteo_conocido": 2713}
    assert type(protocolo["juegos"]["BALOTO"]["ultimo_sorteo_conocido"]) is int
    assert not any(k in json.dumps(protocolo) for k in ("plazo", "genTime", "fecha"))


def test_g3_la_regla_de_ae67_ya_era_estricta_en_el_limite_superior():
    from datetime import datetime, timedelta, timezone
    g = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    p = vr.PrecisionSello(seconds=1)
    assert vr.sello_anterior_al_plazo(g, p, g + timedelta(seconds=1)) == "no_concluyente_por_precision"
    assert vr.sello_anterior_al_plazo(g, p, g - timedelta(seconds=1)) == "posterior_al_plazo_con_margen_de_precision"
    assert vr.sello_anterior_al_plazo(g, None, g + timedelta(days=1)) == "precision_ausente_pendiente"


def test_g3_rfc3161_client_descarta_la_fraccion_y_no_compara_el_identificador():
    import rfc3161_client
    datos = b"premisa\n"
    r = f.respuesta(datos, f.Opciones(gen_time=f.instante("2026-10-01T12:00:00.25Z")))
    decodificada = rfc3161_client.decode_timestamp_response(r)
    assert decodificada.tst_info.gen_time.microsecond == 0
    otro = rfc3161_client.decode_timestamp_response(
        f.respuesta(datos, f.Opciones(gen_time=f.instante(GEN), identificador="v2_otro_certificado")))
    verificador = rfc3161_client.VerifierBuilder().add_root_certificate(f.mundo().ca).build()
    assert verificador.verify_message(otro, datos) is True
