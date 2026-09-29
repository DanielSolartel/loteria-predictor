"""Tests de la Etapa AE-73, validada: alternativa optativa y versionada de
AE-52 para vincular la declaracion R0 con un campo explicito del protocolo
(`registro-prospectivo-ml/1.1`, campo `declaracion_r0`), junto a la ruta
candidata de AE-72 en `estrategia.parametros`.

Cuatro grupos:

G1a extension de AE-52 (constantes, constructor y validacion de la version
    1.1); sobre la base fallan con `AttributeError` porque no existen.
G1b modulo nuevo `vinculo_r0_campo_explicito`, importado dentro de cada
    prueba; sobre la base fallan con `ModuleNotFoundError`.
G2  invariantes: huellas de AE-52 y AE-63 a AE-72, hashes literales de
    protocolos y predicciones 1.0 construidos en la base, estados y bloqueos.
G3  premisas sobre codigo existente, incluido el recorrido completo de AE-72.

Las dos rutas son candidatas y optativas: D1-D9 siguen sin decidir y las
elecciones de AE-70 siguen en None. El verificador solo comprueba integridad
de bytes; la autenticacion de R0, la recepcion antes del plazo, la
completitud y unicidad del canal y la aptitud inferencial quedan pendientes.
Todo sintetico: sin sorteos reales, entrenamiento, inferencia, sello real ni
PostgreSQL."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import inspect
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.application.ml import analisis_alternativas_de_declaracion_previa as aa
from app.application.ml import auditoria_obligaciones_de_aplicacion as ao
from app.application.ml import diseno_regla_prospectiva as dr
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
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from tests.unit.simulaciones import sinteticos

PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""
ELEMENTOS = tuple(iv.ELEMENTOS_DE_R0)
CORTES = {"BALOTO": 2713, "BALOTO_REVANCHA": 2713}
AE73 = "ae73_campo_explicito"
AE72 = "ae72_parametros"


def _modulo():
    return importlib.import_module("app.application.ml.vinculo_r0_campo_explicito")


def _rp(nombre):
    """Atributo nuevo de AE-52; sobre la base falla con AttributeError."""
    return getattr(rp, nombre)


def _estrategia(parametros=None):
    return {
        "nombre": "estrategia_sintetica", "descripcion": "estrategia sintetica solo para pruebas",
        "huella_codigo": "a" * 64, "archivos_codigo": ["sintetico.py"],
        "parametros": parametros if parametros is not None else {"semilla": 1},
        "entorno": {"python": "3.x", "scikit_learn": "0.0"},
    }


def _elementos(valor="valor-de-prueba", pendientes=()):
    d = {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"{valor}-{i}"}} for i, e in enumerate(ELEMENTOS)}
    for e in pendientes:
        d[e] = {"estado": "pendiente"}
    return d


def _vinculo(h="1" * 64, pendientes=()):
    return {"regla": "ae73-vinculo-r0-campo-explicito/1", "esquema_declaracion": "declaracion-r0-sintetica/1",
            "hash_declaracion": h, "pendientes": sorted(pendientes)}


def _protocolo_1_1(vinculo=None, **cambios):
    """Protocolo 1.1 construido a mano para probar la validacion de AE-52."""
    p = rp.construir_protocolo(protocolo_id="sintetico-ae73", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                               sintetico=True)
    p = {**p, "esquema": "registro-prospectivo-ml/1.1",
         "declaracion_r0": vinculo if vinculo is not None else _vinculo()}
    p.update(cambios)
    return p


def _registro(protocolo, objetivos=(2714,)):
    entradas = [rp.serializar_entrada(protocolo)]
    for objetivo in objetivos:
        prediccion = rp.nueva_prediccion(rp.validar_registro(entradas), "BALOTO", objetivo,
                                         sinteticos.historico(2081, objetivo - 1), PROBABILIDADES)
        entradas.append(rp.serializar_entrada(prediccion))
    return entradas


def _recorrido(m, ruta, elementos=None, objetivos=(2714,)):
    declaracion = pv.construir_declaracion(elementos if elementos is not None else _elementos())
    if ruta == AE73:
        protocolo = m.construir_protocolo_con_campo_explicito(declaracion, protocolo_id="sintetico-ae73",
                                                              estrategia=_estrategia(), cortes=CORTES)
    else:
        protocolo = pv.construir_protocolo_candidato(declaracion, protocolo_id="sintetico-ae73",
                                                     estrategia=_estrategia(), cortes=CORTES)
    return declaracion, pv.bytes_de_declaracion(declaracion), protocolo, _registro(protocolo, objetivos)


def _segundo_protocolo(bytes_primero, protocolo):
    segundo = {**protocolo, "secuencia": 2, "hash_anterior": rp.hash_entrada(bytes_primero)}
    return rp.serializar_entrada(segundo)


def _plano(valor):
    if dataclasses.is_dataclass(valor):
        return {f.name: _plano(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, Mapping):
        return {str(k): _plano(v) for k, v in valor.items()}
    if isinstance(valor, (tuple, list, set, frozenset)):
        return [_plano(v) for v in (sorted(valor) if isinstance(valor, (set, frozenset)) else valor)]
    return valor


def _huella(valor):
    return hashlib.sha256(json.dumps(_plano(valor), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ===========================================================================
# G1a: extension de AE-52 (fallan sobre la base con AttributeError)
# ===========================================================================

def test_g1a_constantes_versionadas_de_ae52():
    assert _rp("ESQUEMA_ENTRADA_PROTOCOLO_VINCULO_R0") == "registro-prospectivo-ml/1.1"
    assert rp.ESQUEMA_ENTRADA == "registro-prospectivo-ml/1.0"
    assert _rp("ESQUEMAS_PROTOCOLO") == ("registro-prospectivo-ml/1.0", "registro-prospectivo-ml/1.1")
    assert _rp("REGLA_VINCULO_R0_CAMPO_EXPLICITO") == "ae73-vinculo-r0-campo-explicito/1"
    assert _rp("ESQUEMA_DECLARACION_R0") == pv.ESQUEMA_DECLARACION
    assert _rp("CAMPO_VINCULO_R0") == "declaracion_r0"
    assert set(_rp("MOTIVOS_VINCULO_R0")) == {
        "vinculo_ausente_en_esquema_1_1", "vinculo_en_esquema_1_0", "vinculo_no_es_objeto",
        "claves_del_vinculo_distintas", "regla_desconocida", "esquema_de_declaracion_desconocido",
        "hash_mal_formado", "pendientes_mal_formados", "vinculo_solo_sintetico", "doble_vinculo"}
    assert issubclass(_rp("VinculoR0InvalidoError"), rp.EntradaRegistroInvalidaError)
    assert _rp("VinculoR0InvalidoError").codigo_salida == rp.EntradaRegistroInvalidaError.codigo_salida


def test_g1a_constructor_1_1_y_convivencia_con_1_0():
    construir = _rp("construir_protocolo_con_vinculo_r0")
    vinculo = _vinculo("2" * 64, pendientes=(ELEMENTOS[1],))
    p = construir(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES, pendientes=[], sintetico=True,
                  vinculo_r0=vinculo)
    assert p["esquema"] == "registro-prospectivo-ml/1.1" and p["declaracion_r0"] == vinculo
    assert p["declaracion_r0"] is not vinculo
    entradas = _registro(p)
    estado = rp.validar_registro(entradas)
    assert estado.total == 2 and rp.leer_entrada(entradas[1])["esquema"] == rp.ESQUEMA_ENTRADA
    assert rp.leer_entrada(entradas[0]) == p and rp.serializar_entrada(p) == entradas[0]
    resumen = rp.resumir_registro(estado)
    assert resumen["protocolo"]["hash"] == rp.hash_entrada(entradas[0])
    p10 = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                                 sintetico=True)
    assert p10["esquema"] == rp.ESQUEMA_ENTRADA and "declaracion_r0" not in p10
    assert {k: v for k, v in p.items() if k not in ("esquema", "declaracion_r0")} == \
        {k: v for k, v in p10.items() if k != "esquema"}


def _caso(motivo):
    if motivo == "vinculo_ausente_en_esquema_1_1":
        p = _protocolo_1_1()
        del p["declaracion_r0"]
        return p
    if motivo == "vinculo_en_esquema_1_0":
        return _protocolo_1_1(esquema=rp.ESQUEMA_ENTRADA)
    if motivo == "vinculo_no_es_objeto":
        return _protocolo_1_1(vinculo="1" * 64)
    if motivo == "claves_del_vinculo_distintas":
        return _protocolo_1_1(vinculo={**_vinculo(), "extra": 1})
    if motivo == "regla_desconocida":
        return _protocolo_1_1(vinculo={**_vinculo(), "regla": "ae73-vinculo-r0-campo-explicito/2"})
    if motivo == "esquema_de_declaracion_desconocido":
        return _protocolo_1_1(vinculo={**_vinculo(), "esquema_declaracion": "declaracion-r0-sintetica/2"})
    if motivo == "hash_mal_formado":
        return _protocolo_1_1(vinculo={**_vinculo(), "hash_declaracion": "A" * 64})
    if motivo == "pendientes_mal_formados":
        return _protocolo_1_1(vinculo={**_vinculo(), "pendientes": ["b_elemento", "a_elemento"]})
    if motivo == "vinculo_solo_sintetico":
        return _protocolo_1_1(sintetico=False, pendientes=list(rp.PENDIENTES_BORRADOR_AE52),
                              juegos={"BALOTO": {"ultimo_sorteo_conocido": None}})
    if motivo == "doble_vinculo":
        return _protocolo_1_1(estrategia=_estrategia({"semilla": 1, "vinculo_r0_candidato": {"x": 1}}))
    raise AssertionError(motivo)


@pytest.mark.parametrize("motivo", [
    "vinculo_ausente_en_esquema_1_1", "vinculo_en_esquema_1_0", "vinculo_no_es_objeto",
    "claves_del_vinculo_distintas", "regla_desconocida", "esquema_de_declaracion_desconocido", "hash_mal_formado",
    "pendientes_mal_formados", "vinculo_solo_sintetico", "doble_vinculo",
])
def test_g1a_vinculos_mal_formados_se_rechazan_con_motivo_distinguible(motivo):
    error = _rp("VinculoR0InvalidoError")
    with pytest.raises(error) as info:
        rp.validar_registro([rp.serializar_entrada(_caso(motivo))])
    assert info.value.motivo == motivo


@pytest.mark.parametrize("pendientes", [
    ["b", "a"], ["a", "a"], "a", [1], ["Mayuscula"], [""], None,
])
def test_g1a_pendientes_estrictos(pendientes):
    error = _rp("VinculoR0InvalidoError")
    with pytest.raises(error) as info:
        rp.validar_registro([rp.serializar_entrada(_protocolo_1_1(vinculo={**_vinculo(), "pendientes": pendientes}))])
    assert info.value.motivo == "pendientes_mal_formados"


@pytest.mark.parametrize("valor", [1, None, ["x"]])
def test_g1a_tipos_invalidos_en_regla_y_hash(valor):
    error = _rp("VinculoR0InvalidoError")
    with pytest.raises(error) as info:
        rp.validar_registro([rp.serializar_entrada(_protocolo_1_1(vinculo={**_vinculo(), "regla": valor}))])
    assert info.value.motivo == "regla_desconocida"
    with pytest.raises(error) as info:
        rp.validar_registro([rp.serializar_entrada(_protocolo_1_1(vinculo={**_vinculo(), "hash_declaracion": valor}))])
    assert info.value.motivo == "hash_mal_formado"


def test_g1a_version_desconocida_y_entradas_posteriores_1_1():
    _rp("ESQUEMA_ENTRADA_PROTOCOLO_VINCULO_R0")
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="esquema desconocido") as info:
        rp.validar_registro([rp.serializar_entrada(_protocolo_1_1(esquema="registro-prospectivo-ml/1.9"))])
    assert type(info.value) is rp.EntradaRegistroInvalidaError
    entradas = _registro(_protocolo_1_1())
    prediccion = rp.leer_entrada(entradas[1])
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="esquema desconocido"):
        rp.validar_registro([entradas[0],
                             rp.serializar_entrada({**prediccion, "esquema": "registro-prospectivo-ml/1.1"})])
    with pytest.raises(_rp("VinculoR0InvalidoError")):
        _rp("construir_protocolo_con_vinculo_r0")(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES,
                                                  pendientes=[], sintetico=True, vinculo_r0={"regla": "x"})


# ===========================================================================
# G1b: modulo nuevo (fallan sobre la base con ModuleNotFoundError)
# ===========================================================================

def test_g1b_vinculo_desde_la_declaracion():
    m = _modulo()
    d = pv.construir_declaracion(_elementos(pendientes=(ELEMENTOS[5], ELEMENTOS[0])))
    v = m.construir_vinculo_r0(d)
    assert v == {"regla": rp.REGLA_VINCULO_R0_CAMPO_EXPLICITO, "esquema_declaracion": pv.ESQUEMA_DECLARACION,
                 "hash_declaracion": pv.hash_de_declaracion(d), "pendientes": sorted((ELEMENTOS[5], ELEMENTOS[0]))}
    assert m.RUTAS == (AE72, AE73)
    assert m.ESTADO_DE_LAS_RUTAS == "candidatas" and m.ACTIVACION == "optativa"


@pytest.mark.parametrize("ruta", [AE73, AE72])
def test_g1b_recorrido_de_extremo_a_extremo(ruta):
    m = _modulo()
    declaracion, bytes_decl, protocolo, entradas = _recorrido(m, ruta, objetivos=(2714, 2715))
    informe = m.verificar_vinculo_r0(entradas, bytes_decl, protocolo_hash_esperado=rp.hash_entrada(entradas[0]),
                                     objetivos_esperados=(("BALOTO", 2714), ("BALOTO", 2715)))
    assert informe.ruta == ruta and informe.estado_de_bytes == "vinculo_de_bytes_verificado"
    assert informe.hash_declaracion == pv.hash_de_declaracion(declaracion)
    assert informe.protocolo_hash == rp.hash_entrada(entradas[0]) and informe.predicciones_vinculadas == 2
    assert m.ruta_del_protocolo(protocolo) == ruta
    if ruta == AE73:
        assert "vinculo_r0_candidato" not in protocolo["estrategia"]["parametros"]
        assert protocolo["esquema"] == "registro-prospectivo-ml/1.1"
    else:
        assert "declaracion_r0" not in protocolo and protocolo["esquema"] == rp.ESQUEMA_ENTRADA


@pytest.mark.parametrize("ruta", [AE73, AE72])
def test_g1b_declaracion_ausente_alterada_o_invalida(ruta):
    m = _modulo()
    _, bytes_decl, _, entradas = _recorrido(m, ruta)
    assert m.verificar_vinculo_r0(entradas, None).estado_de_bytes == "declaracion_ausente"
    assert m.verificar_vinculo_r0(entradas, b"no es json\n").estado_de_bytes == "declaracion_invalida"
    otra = pv.bytes_de_declaracion(pv.construir_declaracion(_elementos("alterada")))
    assert m.verificar_vinculo_r0(entradas, otra).estado_de_bytes == "hash_de_declaracion_no_coincide"


@pytest.mark.parametrize("ruta", [AE73, AE72])
def test_g1b_regla_hash_de_protocolo_y_prediccion_con_protocolo_distinto(ruta):
    m = _modulo()
    _, bytes_decl, _, entradas = _recorrido(m, ruta)
    assert m.verificar_vinculo_r0(entradas, bytes_decl, regla="otra-regla/1").estado_de_bytes == "regla_distinta"
    assert m.verificar_vinculo_r0(entradas, bytes_decl, protocolo_hash_esperado="0" * 64).estado_de_bytes == \
        "protocolo_hash_no_coincide"
    prediccion = rp.leer_entrada(entradas[1])
    informe = m.verificar_vinculo_r0([entradas[0], rp.serializar_entrada({**prediccion, "protocolo_hash": "f" * 64})],
                                     bytes_decl)
    assert informe.estado_de_bytes == "registro_invalido" and "protocolo distinto" in informe.detalle


@pytest.mark.parametrize("ruta", [AE73, AE72])
def test_g1b_completar_un_pendiente_despues_exige_otro_protocolo_y_registro(ruta):
    m = _modulo()
    e = ELEMENTOS[3]
    _, b_antes, p_antes, entradas = _recorrido(m, ruta, elementos=_elementos(pendientes=(e,)))
    informe = m.verificar_vinculo_r0(entradas, b_antes)
    assert informe.estado_de_bytes == "vinculo_de_bytes_verificado" and informe.pendientes == (e,)
    assert informe.elementos[e] == "sin_fijar_explicito"
    assert "elementos_pendientes_en_la_declaracion" in informe.falta
    if ruta == AE73:
        assert p_antes["declaracion_r0"]["pendientes"] == [e]
    _, b_despues, p_despues, entradas_nuevas = _recorrido(m, ruta)
    assert m.verificar_vinculo_r0(entradas, b_despues).estado_de_bytes == "hash_de_declaracion_no_coincide"
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        rp.validar_registro([entradas[0], _segundo_protocolo(entradas[0], p_despues)])
    assert m.verificar_vinculo_r0(entradas_nuevas, b_despues).estado_de_bytes == "vinculo_de_bytes_verificado"


def test_g1b_pendientes_del_protocolo_deben_coincidir_con_la_declaracion():
    m = _modulo()
    d = pv.construir_declaracion(_elementos(pendientes=(ELEMENTOS[2],)))
    p = rp.construir_protocolo_con_vinculo_r0(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES,
                                              pendientes=[], sintetico=True,
                                              vinculo_r0=_vinculo(pv.hash_de_declaracion(d), pendientes=()))
    informe = m.verificar_vinculo_r0(_registro(p), pv.bytes_de_declaracion(d))
    assert informe.estado_de_bytes == "pendientes_no_coinciden"


def test_g1b_vinculo_mal_formado_segun_la_ruta():
    m = _modulo()
    entradas_ae73 = [rp.serializar_entrada(_caso("hash_mal_formado"))]
    informe = m.verificar_vinculo_r0(entradas_ae73, b"{}\n")
    assert informe.estado_de_bytes == "registro_invalido" and informe.motivo_de_registro == "hash_mal_formado"
    assert informe.ruta == AE73
    _, bytes_decl, protocolo, _ = _recorrido(m, AE72)
    mal = json.loads(json.dumps(protocolo))
    mal["estrategia"]["parametros"]["vinculo_r0_candidato"]["hash_declaracion"] = "A" * 64
    entradas_ae72 = [rp.serializar_entrada(mal)]
    assert rp.validar_registro(entradas_ae72).total == 1
    informe = m.verificar_vinculo_r0(entradas_ae72, bytes_decl)
    assert informe.ruta == AE72 and informe.estado_de_bytes == "vinculo_mal_formado"
    assert informe.motivo_de_registro is None


def test_g1b_coexistencia_de_registros():
    m = _modulo()
    plano = _registro(rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES,
                                             pendientes=[], sintetico=True))
    d, bd, _, r72 = _recorrido(m, AE72)
    _, _, _, r73 = _recorrido(m, AE73)
    for entradas in (plano, r72, r73):
        assert rp.validar_registro(entradas).total == 2
        rp.resumir_registro(rp.validar_registro(entradas))
    assert m.verificar_vinculo_r0(plano, bd).estado_de_bytes == "protocolo_sin_vinculo_r0"
    assert m.verificar_vinculo_r0(plano, bd).ruta is None
    assert m.verificar_vinculo_r0(r72, bd).ruta == AE72 and m.verificar_vinculo_r0(r73, bd).ruta == AE73
    with pytest.raises(rp.RegistroProspectivoError):
        rp.validar_registro([r73[0], r72[1]])
    with pytest.raises(rp.RegistroProspectivoError):
        rp.validar_registro([r72[0], r73[1]])
    equivalencia = m.equivalencia_de_designacion(r72, r73)
    assert equivalencia == {"mismo_hash_declaracion": True, "mismo_protocolo_hash": False,
                            "hash_declaracion": pv.hash_de_declaracion(d)}


@pytest.mark.parametrize("ruta", [AE73, AE72])
def test_g1b_cambio_de_un_elemento_se_propaga(ruta):
    m = _modulo()
    base = _recorrido(m, ruta)
    igual = _recorrido(m, ruta)
    cambiado_el = _elementos()
    cambiado_el[ELEMENTOS[7]] = {"estado": "declarado_sintetico", "valor": {"sintetico": "otro"}}
    cambiado = _recorrido(m, ruta, elementos=cambiado_el)
    assert base[1] == igual[1] and base[3] == igual[3]
    assert base[1] != cambiado[1]
    assert pv.hash_de_declaracion(base[0]) != pv.hash_de_declaracion(cambiado[0])
    assert base[3][0] != cambiado[3][0]
    assert rp.hash_entrada(base[3][0]) != rp.hash_entrada(cambiado[3][0])
    assert rp.leer_entrada(base[3][1])["protocolo_hash"] != rp.leer_entrada(cambiado[3][1])["protocolo_hash"]
    assert rp.leer_entrada(base[3][1])["protocolo_hash"] == rp.hash_entrada(base[3][0])
    assert rp.leer_entrada(cambiado[3][1])["protocolo_hash"] == rp.hash_entrada(cambiado[3][0])


def test_g1b_omision_de_prediccion():
    m = _modulo()
    _, bd, _, entradas = _recorrido(m, AE73)
    informe = m.verificar_vinculo_r0(entradas, bd, objetivos_esperados=(("BALOTO", 2714), ("BALOTO", 2716)))
    assert informe.estado_de_bytes == "prediccion_omitida" and informe.omitidas == (("BALOTO", 2716),)


def test_g1b_pendientes_y_marcadores_nunca_aparecen_como_fijados():
    m = _modulo()
    elementos = _elementos(pendientes=(ELEMENTOS[0],))
    elementos[ELEMENTOS[1]] = {"estado": "declarado_sintetico", "valor": "pendiente"}
    _, bd, _, entradas = _recorrido(m, AE73, elementos=elementos)
    informe = m.verificar_vinculo_r0(entradas, bd)
    assert informe.elementos[ELEMENTOS[0]] == "sin_fijar_explicito"
    assert informe.elementos[ELEMENTOS[1]] == "declarado_con_marcador_textual"
    assert informe.marcadores == (ELEMENTOS[1],) and informe.pendientes == (ELEMENTOS[0],)
    assert "valores_con_marcador_textual" in informe.falta
    assert not any(re.search(r"fijad", s) for s in informe.elementos.values())
    assert informe.resumen_de_declaracion == "parcial_con_pendientes_y_marcadores_textuales"


def test_g1b_cinco_planos_separados():
    m = _modulo()
    for ruta in (AE73, AE72):
        _, bd, _, entradas = _recorrido(m, ruta)
        informe = m.verificar_vinculo_r0(entradas, bd)
        assert informe.autenticacion_de_r0 == "sin_evidencia"
        assert informe.recepcion_antes_del_plazo == "sin_evidencia"
        assert informe.completitud_y_unicidad_del_canal == "sin_evidencia"
        assert informe.aptitud_inferencial == "no_autorizada"
        for faltante in ("autenticacion_de_r0", "recepcion_antes_del_plazo", "completitud_y_unicidad_del_canal",
                         "decisiones_del_operador_d1_a_d9", "autorizacion_de_evaluacion"):
            assert faltante in informe.falta, (ruta, faltante)
    assert tuple(m.PLANOS_DEL_INFORME) == tuple(pv.PLANOS_DEL_INFORME)
    for estado in (*m.ESTADOS_DE_BYTES, *pv.ESTADOS_DE_PLANO):
        assert not re.search(r"fijad|acreditad|autenticad|aprobad|(?<!in)valid|apt[ao]", estado), estado


def test_g1b_comparacion_verificable_de_las_rutas():
    m = _modulo()
    c = m.COMPARACION_DE_RUTAS
    assert set(c) == {AE72, AE73}
    for criterio in ("cambio_en_ae52", "semantica_del_campo", "identificacion_de_la_regla",
                     "ae52_rechaza_vinculos_mal_formados", "pendientes_en_el_protocolo", "rechaza_doble_vinculo",
                     "solo_sintetico", "compatibilidad_con_registros_1_0"):
        assert criterio in c[AE72] and criterio in c[AE73], criterio
    assert c[AE72]["ae52_rechaza_vinculos_mal_formados"] is False
    assert c[AE73]["ae52_rechaza_vinculos_mal_formados"] is True
    assert c[AE72]["pendientes_en_el_protocolo"] is False and c[AE73]["pendientes_en_el_protocolo"] is True
    assert c[AE73]["rechaza_doble_vinculo"] is True
    assert c[AE72]["compatibilidad_con_registros_1_0"] is True and c[AE73]["compatibilidad_con_registros_1_0"] is True


def test_g1b_migracion_documentada_y_no_ejecutada():
    m = _modulo()
    assert m.REQUISITOS_DE_MIGRACION and m.MIGRACION_EJECUTADA is False
    texto = " ".join(m.REQUISITOS_DE_MIGRACION)
    for frase in ("otro registro", "D1", "predicciones anteriores"):
        assert frase in texto, frase
    publicas = [n for n, f in vars(m).items() if inspect.isfunction(f) and f.__module__ == m.__name__]
    assert not any("migr" in n for n in publicas)


def test_g1b_decisiones_del_operador_sin_valor():
    m = _modulo()
    assert tuple(m.DECISIONES_REQUERIDAS) == tuple(aa.DECISIONES_DEL_OPERADOR_AE71)
    assert {d["estado"] for d in m.DECISIONES_REQUERIDAS.values()} == {"sin_decidir"}
    assert {k for k, d in m.DECISIONES_REQUERIDAS.items() if d["destacada"]} == {"D1", "D2", "D7"}
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    assert not any(n.endswith("_ELEGIDA") for n in vars(m))
    assert pi.AUTORIZA_EVALUACION is False and pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"


def test_g1b_modulo_puro_y_sin_asignaciones_externas():
    m = _modulo()
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess", "random", "os", "pathlib",
                  "sqlalchemy", "datetime"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            objetivos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            assert not any(isinstance(o, ast.Attribute) for o in objetivos)
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
            assert not (nodo.module or "").startswith("app.infrastructure")
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "utcnow", "today"}, nodo.attr
        if isinstance(nodo, ast.Name):
            assert nodo.id not in {"open", "eval", "exec"}, nodo.id


_PROHIBIDAS = {"aprobado", "aprobada", "go", "cumplido", "cumplida", "desbloqueado", "desbloqueada", "autorizado",
               "autorizada", "recomendado", "recomendada", "elegido", "elegida", "autenticado", "autenticada",
               "acreditado", "acreditada", "fijado", "fijada", "valido", "valida"}


def test_g1b_textos_sin_aprobacion_ni_acreditacion():
    m = _modulo()
    textos = [m.COMPATIBILIDAD, m.LIMITES, *m.REQUISITOS_DE_MIGRACION]
    for fila in m.COMPARACION_DE_RUTAS.values():
        textos += [v for v in fila.values() if isinstance(v, str)]
    textos += [d["supuesto_del_prototipo"] for d in m.DECISIONES_REQUERIDAS.values()]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS
    assert "RFC 9162" not in " ".join(textos) or "certificados" in " ".join(textos)


# ===========================================================================
# G2: invariantes (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae63_a_ae72():
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
                    vr.RESULTADOS_SELLO)) == (
        "eb094cddc0659b3b4e015922025db9ca3327116d10677677a26224270da857c5")
    assert _huella((ec.ALCANCE_RFC_9162, ec.MODELO_DE_FIRMA, ec.AUTENTICACION_DE_R0, ec.REQUISITOS_PREVIOS,
                    ec.CONDICIONES_DEL_PROTOCOLO, ec.CORRESPONDENCIA_CON_AE66, ec.DEPENDENCIAS_NORMATIVAS,
                    ec.DEPENDENCIAS_DE_VERIFICACION, ec.INSTANTES, ec.HIPOTESIS_TEMPORALES,
                    ec.LIMITE_DE_COMPLETITUD, tuple(ec.REGLAS_DE_DUPLICADOS_CANDIDATAS),
                    ec.REGLA_DE_DUPLICADOS_ELEGIDA, ec.RESULTADOS_RELOJ, ec.REQUISITOS_DE_VIA,
                    ec.RESULTADOS_DE_VIA)) == (
        "03c83bb1719e68bc14744bde36971f92a7a0f45784512424566305c2f504b00d")
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
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"


def test_g2_bytes_de_registros_1_0_sin_cambios():
    p = rp.construir_protocolo(protocolo_id="sintetico-ae73", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                               sintetico=True)
    b = rp.serializar_entrada(p)
    assert rp.hash_entrada(b) == "c9e73601ac6d9668a3e50c8e76b75a130b214a68efaf5cf115b17d5a67ea3892"
    prediccion = rp.nueva_prediccion(rp.validar_registro([b]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                                     PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(prediccion)) == (
        "435918926917ea8ab712c7162eff5544998d340f3df711b1508815ce6429f2c6")
    borrador = rp.construir_protocolo_borrador(_estrategia())
    assert rp.hash_entrada(rp.serializar_entrada(borrador)) == (
        "4b0096fea982e015c0ee8c2561c82d44d2b4ae5923383c5433a7c4dcaacd2d68")


def test_g2_estados_decisiones_y_bloqueos_sin_cambios():
    assert {r.estado for r in {**ec.REQUISITOS_PREVIOS, **ec.CONDICIONES_DEL_PROTOCOLO}.values()} == {"sin_fijar"}
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert {e.estado for e in iv.ELEMENTOS_DE_R0.values()} == {"pendiente"}
    assert {p["estado"] for p in iv.PREGUNTAS_ABIERTAS_AE69.values()} == {"sin_respuesta"}
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    assert {d["estado"] for d in aa.DECISIONES_DEL_OPERADOR_AE71.values()} == {"sin_decidir"}
    assert {d["estado"] for d in pv.DECISIONES_REQUERIDAS.values()} == {"sin_decidir"}
    assert pv.ESTADO_DE_LA_TOPOLOGIA == "candidata"
    condiciones = {c.id: c.estado for c in tc.CONDICIONES_DE_TRASLADO}
    for id_ in ("F1_anterioridad", "F2_correspondencia_de_la_filtracion", "O3_tratamiento_de_omisiones",
                "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert condiciones[id_] == "pendiente", id_
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    pi.verificar_expediente()
    assert len(rp.PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"


# ===========================================================================
# G3: premisas sobre codigo existente (pasan sobre la base)
# ===========================================================================

def test_g3_recorrido_de_ae72_sigue_funcionando():
    informe = pv.demostrar_recorrido_sintetico(sinteticos.historico(2081, 2713))
    assert informe.estado_de_bytes == "vinculo_de_bytes_verificado" and informe.aptitud_inferencial == "no_autorizada"


def test_g3_ae52_rechaza_claves_de_mas_y_esquemas_desconocidos_en_1_0():
    p = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                               sintetico=True)
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        rp.validar_registro([rp.serializar_entrada({**p, "clave_extra": 1})])
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="esquema desconocido"):
        rp.validar_registro([rp.serializar_entrada({**p, "esquema": "registro-prospectivo-ml/9.9"})])


def test_g3_predicciones_en_esquema_1_0_y_segundo_protocolo_rechazado():
    p1 = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia({"a": 1}), cortes=CORTES, pendientes=[],
                                sintetico=True)
    p2 = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia({"a": 2}), cortes=CORTES, pendientes=[],
                                sintetico=True)
    entradas = _registro(p1)
    assert rp.leer_entrada(entradas[1])["esquema"] == rp.ESQUEMA_ENTRADA
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="segundo protocolo"):
        rp.validar_registro([entradas[0], _segundo_protocolo(entradas[0], p2)])


def test_g3_ae72_acepta_en_ae52_un_vinculo_mal_formado_en_parametros():
    d = pv.construir_declaracion(_elementos())
    p = pv.construir_protocolo_candidato(d, protocolo_id="s", estrategia=_estrategia(), cortes=CORTES)
    p["estrategia"]["parametros"]["vinculo_r0_candidato"]["hash_declaracion"] = "A" * 64
    entradas = [rp.serializar_entrada(p)]
    assert rp.validar_registro(entradas).total == 1
    assert pv.verificar_vinculo(entradas, pv.bytes_de_declaracion(d)).estado_de_bytes == "vinculo_mal_formado"
