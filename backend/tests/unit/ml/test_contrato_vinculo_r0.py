"""Tests de la Etapa AE-74, validada: contrato de vinculacion R0 elegido
por el operador (D1, D2 y D7 aprobadas; D9 con espera provisional), fijado
en los bytes del protocolo con la version `registro-prospectivo-ml/1.2`, y
puertas de admision independientes.

Cuatro grupos:

G1a extension 1.2 de AE-52; sobre la base fallan con `AttributeError`.
G1b modulo nuevo `contrato_vinculo_r0`, importado dentro de cada prueba;
    sobre la base fallan con `ModuleNotFoundError`.
G2  invariantes: huellas de AE-52 y AE-63 a AE-73, bytes y hashes literales
    de registros 1.0 y 1.1 construidos en la base, estados y bloqueos.
G3  premisas sobre codigo existente, incluidos los recorridos de AE-72 y
    AE-73.

La puerta «R0 final» no puede superarse con la evidencia existente. Un hash
coincidente, una lista vacia de pendientes o pruebas sinteticas no elevan
nada a autenticado, recibido antes del plazo, fijado o apto para
evaluacion. `AUTORIZA_EVALUACION = False`. Todo sintetico: sin sorteos
reales, entrenamiento, inferencia, sellos, firmas, relojes, canales ni
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
from app.application.ml import vinculo_r0_campo_explicito as ve
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from tests.unit.simulaciones import sinteticos

PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""
ELEMENTOS = tuple(iv.ELEMENTOS_DE_R0)
CORTES = {"BALOTO": 2713, "BALOTO_REVANCHA": 2713}
V12 = "registro-prospectivo-ml/1.2"
PUERTAS = ("borrador_sintetico", "vinculo_integro", "declaracion_estructuralmente_completa", "r0_final")


def _modulo():
    return importlib.import_module("app.application.ml.contrato_vinculo_r0")


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


def _elementos(valor="valor-de-prueba", pendientes=(), marcadores=()):
    d = {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"{valor}-{i}"}} for i, e in enumerate(ELEMENTOS)}
    for e in pendientes:
        d[e] = {"estado": "pendiente"}
    for e in marcadores:
        d[e] = {"estado": "declarado_sintetico", "valor": "TBD"}
    return d


def _vinculo_1_2(h="1" * 64, pendientes=()):
    return {"contrato": "contrato-vinculo-r0/1", "regla": "ae74-vinculo-r0-contrato/1",
            "esquema_declaracion": "declaracion-r0-sintetica/1", "hash_declaracion": h,
            "pendientes": sorted(pendientes)}


def _vinculo_1_1(h="1" * 64, pendientes=()):
    return {"regla": "ae73-vinculo-r0-campo-explicito/1", "esquema_declaracion": "declaracion-r0-sintetica/1",
            "hash_declaracion": h, "pendientes": sorted(pendientes)}


def _protocolo_1_2(vinculo=None, **cambios):
    """Protocolo 1.2 construido a mano para probar la validacion de AE-52."""
    p = rp.construir_protocolo(protocolo_id="sintetico-ae74", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                               sintetico=True)
    p = {**p, "esquema": V12, "declaracion_r0": vinculo if vinculo is not None else _vinculo_1_2()}
    p.update(cambios)
    return p


def _registro(protocolo, objetivos=(2714,)):
    entradas = [rp.serializar_entrada(protocolo)]
    for objetivo in objetivos:
        prediccion = rp.nueva_prediccion(rp.validar_registro(entradas), "BALOTO", objetivo,
                                         sinteticos.historico(2081, objetivo - 1), PROBABILIDADES)
        entradas.append(rp.serializar_entrada(prediccion))
    return entradas


def _recorrido(m, elementos=None, objetivos=(2714,)):
    declaracion = pv.construir_declaracion(elementos if elementos is not None else _elementos())
    protocolo = m.construir_protocolo_del_contrato(declaracion, protocolo_id="sintetico-ae74",
                                                   estrategia=_estrategia(), cortes=CORTES)
    return declaracion, pv.bytes_de_declaracion(declaracion), protocolo, _registro(protocolo, objetivos)


def _segundo_protocolo(bytes_primero, protocolo):
    return rp.serializar_entrada({**protocolo, "secuencia": 2, "hash_anterior": rp.hash_entrada(bytes_primero)})


def _puertas(informe):
    return {p: informe.puertas[p].estado for p in PUERTAS}


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
# G1a: version 1.2 de AE-52 (fallan sobre la base con AttributeError)
# ===========================================================================

def test_g1a_constantes_de_la_version_1_2():
    assert _rp("ESQUEMA_ENTRADA_PROTOCOLO_CONTRATO_R0") == V12
    assert _rp("CONTRATO_VINCULO_R0") == "contrato-vinculo-r0/1"
    assert _rp("REGLA_VINCULO_R0_CONTRATO") == "ae74-vinculo-r0-contrato/1"
    assert set(_rp("MOTIVOS_VINCULO_R0_CONTRATO")) == {
        "vinculo_ausente_en_esquema_1_2", "vinculo_no_es_objeto", "claves_del_vinculo_distintas",
        "contrato_desconocido", "regla_desconocida", "esquema_de_declaracion_desconocido", "hash_mal_formado",
        "pendientes_mal_formados", "vinculo_solo_sintetico", "doble_vinculo"}
    assert rp.ESQUEMAS_PROTOCOLO == ("registro-prospectivo-ml/1.0", "registro-prospectivo-ml/1.1")
    assert rp.CAMPO_VINCULO_R0 == "declaracion_r0"


def test_g1a_constructor_1_2_y_convivencia_con_1_0_y_1_1():
    construir = _rp("construir_protocolo_con_contrato_r0")
    vinculo = _vinculo_1_2("2" * 64, pendientes=(ELEMENTOS[4],))
    p = construir(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES, pendientes=[], sintetico=True,
                  vinculo_r0=vinculo)
    assert p["esquema"] == V12 and p["declaracion_r0"] == vinculo and p["declaracion_r0"] is not vinculo
    entradas = _registro(p)
    assert rp.validar_registro(entradas).total == 2
    assert rp.leer_entrada(entradas[1])["esquema"] == rp.ESQUEMA_ENTRADA
    rp.resumir_registro(rp.validar_registro(entradas))
    p11 = rp.construir_protocolo_con_vinculo_r0(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES,
                                                pendientes=[], sintetico=True, vinculo_r0=_vinculo_1_1("2" * 64))
    assert p11["esquema"] == "registro-prospectivo-ml/1.1"
    assert {k: v for k, v in p.items() if k not in ("esquema", "declaracion_r0")} == \
        {k: v for k, v in p11.items() if k not in ("esquema", "declaracion_r0")}


def _caso(motivo):
    if motivo == "vinculo_ausente_en_esquema_1_2":
        p = _protocolo_1_2()
        del p["declaracion_r0"]
        return p
    if motivo == "vinculo_no_es_objeto":
        return _protocolo_1_2(vinculo="1" * 64)
    if motivo == "claves_del_vinculo_distintas":
        return _protocolo_1_2(vinculo=_vinculo_1_1())
    if motivo == "contrato_desconocido":
        return _protocolo_1_2(vinculo={**_vinculo_1_2(), "contrato": "contrato-vinculo-r0/2"})
    if motivo == "regla_desconocida":
        return _protocolo_1_2(vinculo={**_vinculo_1_2(), "regla": "ae73-vinculo-r0-campo-explicito/1"})
    if motivo == "esquema_de_declaracion_desconocido":
        return _protocolo_1_2(vinculo={**_vinculo_1_2(), "esquema_declaracion": "declaracion-r0-sintetica/2"})
    if motivo == "hash_mal_formado":
        return _protocolo_1_2(vinculo={**_vinculo_1_2(), "hash_declaracion": "A" * 64})
    if motivo == "pendientes_mal_formados":
        return _protocolo_1_2(vinculo={**_vinculo_1_2(), "pendientes": ["b_elemento", "a_elemento"]})
    if motivo == "vinculo_solo_sintetico":
        return _protocolo_1_2(sintetico=False, pendientes=list(rp.PENDIENTES_BORRADOR_AE52),
                              juegos={"BALOTO": {"ultimo_sorteo_conocido": None}})
    if motivo == "doble_vinculo":
        return _protocolo_1_2(estrategia=_estrategia({"semilla": 1, "vinculo_r0_candidato": {"x": 1}}))
    raise AssertionError(motivo)


@pytest.mark.parametrize("motivo", [
    "vinculo_ausente_en_esquema_1_2", "vinculo_no_es_objeto", "claves_del_vinculo_distintas", "contrato_desconocido",
    "regla_desconocida", "esquema_de_declaracion_desconocido", "hash_mal_formado", "pendientes_mal_formados",
    "vinculo_solo_sintetico", "doble_vinculo",
])
def test_g1a_vinculos_1_2_mal_formados_se_rechazan_con_motivo(motivo):
    _rp("ESQUEMA_ENTRADA_PROTOCOLO_CONTRATO_R0")
    with pytest.raises(rp.VinculoR0InvalidoError) as info:
        rp.validar_registro([rp.serializar_entrada(_caso(motivo))])
    assert info.value.motivo == motivo


def test_g1a_protocolos_parcialmente_migrados_y_versiones_desconocidas():
    _rp("ESQUEMA_ENTRADA_PROTOCOLO_CONTRATO_R0")
    p11_con_contrato = _protocolo_1_2(esquema="registro-prospectivo-ml/1.1")
    with pytest.raises(rp.VinculoR0InvalidoError) as info:
        rp.validar_registro([rp.serializar_entrada(p11_con_contrato)])
    assert info.value.motivo == "claves_del_vinculo_distintas"
    p10_con_contrato = _protocolo_1_2(esquema=rp.ESQUEMA_ENTRADA)
    with pytest.raises(rp.VinculoR0InvalidoError) as info:
        rp.validar_registro([rp.serializar_entrada(p10_con_contrato)])
    assert info.value.motivo == "vinculo_en_esquema_1_0"
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="esquema desconocido") as info:
        rp.validar_registro([rp.serializar_entrada(_protocolo_1_2(esquema="registro-prospectivo-ml/1.3"))])
    assert type(info.value) is rp.EntradaRegistroInvalidaError
    entradas = _registro(_protocolo_1_2())
    prediccion = rp.leer_entrada(entradas[1])
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="esquema desconocido"):
        rp.validar_registro([entradas[0], rp.serializar_entrada({**prediccion, "esquema": V12})])


# ===========================================================================
# G1b: contrato (fallan sobre la base con ModuleNotFoundError)
# ===========================================================================

def test_g1b_contrato_versionado_y_decisiones_aprobadas():
    m = _modulo()
    assert m.CONTRATO == rp.CONTRATO_VINCULO_R0 and m.ESQUEMA_DEL_PROTOCOLO == V12
    assert m.REGLA == rp.REGLA_VINCULO_R0_CONTRATO
    d = m.DECISIONES_DEL_CONTRATO
    aprobadas = ("D1", "D2", "D7")
    assert {k: d[k]["estado"] for k in aprobadas} == {k: "aprobada_por_el_operador" for k in aprobadas}
    assert d["D3"]["estado"] == d["D4"]["estado"] == "decidida_solo_para_esta_ruta"
    assert d["D5"]["estado"] == d["D6"]["estado"] == "inaplicable_a_esta_ruta"
    # AE-75: D8 paso de sin_decidir a una regla comparativa aprobada solo para el modelo sintetico;
    # el plazo operativo y calendario_oficial siguen sin fijar.
    assert d["D8"]["estado"] == "aprobada_solo_para_el_modelo_sintetico"
    assert d["D9"]["estado"] == "espera_provisional_aprobada"
    assert "rechazo" in d["D9"]["texto"] and "sin decidir" in d["D9"]["texto"]
    assert {v["estado"] for v in aa.DECISIONES_DEL_OPERADOR_AE71.values()} == {"sin_decidir"}
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    assert tuple(m.PUERTAS) == PUERTAS
    assert set(m.ESTADOS_DE_PUERTA) == {"superada", "pendiente", "rechazada", "no_evaluable"}


def test_g1b_vinculo_desde_la_declaracion():
    m = _modulo()
    d = pv.construir_declaracion(_elementos(pendientes=(ELEMENTOS[6], ELEMENTOS[1])))
    assert m.construir_vinculo_del_contrato(d) == {
        "contrato": m.CONTRATO, "regla": m.REGLA, "esquema_declaracion": pv.ESQUEMA_DECLARACION,
        "hash_declaracion": pv.hash_de_declaracion(d), "pendientes": sorted((ELEMENTOS[6], ELEMENTOS[1]))}


def test_g1b_recorrido_completo_y_puertas_de_una_declaracion_completa():
    m = _modulo()
    declaracion, bd, protocolo, entradas = _recorrido(m, objetivos=(2714, 2715))
    informe = m.evaluar_admision(entradas, bd, protocolo_hash_esperado=rp.hash_entrada(entradas[0]),
                                 objetivos_esperados=(("BALOTO", 2714), ("BALOTO", 2715)))
    assert informe.contrato == m.CONTRATO and informe.ruta == "contrato_1_2"
    assert _puertas(informe) == {"borrador_sintetico": "superada", "vinculo_integro": "superada",
                                 "declaracion_estructuralmente_completa": "superada", "r0_final": "rechazada"}
    assert informe.estados_alcanzados == ("borrador_sintetico", "vinculo_integro",
                                          "declaracion_estructuralmente_completa")
    assert informe.hash_declaracion == pv.hash_de_declaracion(declaracion)
    assert informe.predicciones_vinculadas == 2


def test_g1b_borrador_con_pendientes_tiene_vinculo_integro_sin_ser_completo():
    m = _modulo()
    e = ELEMENTOS[3]
    _, bd, protocolo, entradas = _recorrido(m, elementos=_elementos(pendientes=(e,)))
    assert protocolo["declaracion_r0"]["pendientes"] == [e]
    informe = m.evaluar_admision(entradas, bd)
    assert _puertas(informe) == {"borrador_sintetico": "superada", "vinculo_integro": "superada",
                                 "declaracion_estructuralmente_completa": "pendiente", "r0_final": "rechazada"}
    assert informe.puertas["declaracion_estructuralmente_completa"].motivos == ("elementos_pendientes",)
    assert "registro_con_pendientes" in informe.puertas["r0_final"].motivos
    assert informe.elementos[e] == "sin_fijar_explicito"


def test_g1b_marcadores_textuales_quedan_en_espera():
    m = _modulo()
    _, bd, _, entradas = _recorrido(m, elementos=_elementos(marcadores=(ELEMENTOS[5],)))
    informe = m.evaluar_admision(entradas, bd)
    completa = informe.puertas["declaracion_estructuralmente_completa"]
    assert completa.estado == "pendiente" and completa.motivos == ("marcadores_textuales_sin_resolver",)
    assert informe.puertas["borrador_sintetico"].estado == "superada"
    assert informe.puertas["vinculo_integro"].estado == "superada"
    assert informe.elementos[ELEMENTOS[5]] == "declarado_con_marcador_textual"
    ambos = _recorrido(m, elementos=_elementos(pendientes=(ELEMENTOS[0],), marcadores=(ELEMENTOS[5],)))
    motivos = m.evaluar_admision(ambos[3], ambos[1]).puertas["declaracion_estructuralmente_completa"].motivos
    assert motivos == ("elementos_pendientes", "marcadores_textuales_sin_resolver")


def test_g1b_r0_final_nunca_se_supera_con_la_evidencia_existente():
    m = _modulo()
    assert "evidencia" not in " ".join(inspect.signature(m.evaluar_admision).parameters)
    _, bd, _, entradas = _recorrido(m)
    informe = m.evaluar_admision(entradas, bd, protocolo_hash_esperado=rp.hash_entrada(entradas[0]),
                                 objetivos_esperados=(("BALOTO", 2714),))
    r0 = informe.puertas["r0_final"]
    assert r0.estado == "rechazada"
    for motivo in ("protocolo_sintetico", "sin_evidencia_de_autenticacion_de_r0",
                   "sin_evidencia_de_recepcion_antes_del_plazo", "sin_evidencia_de_completitud_y_unicidad_del_canal"):
        assert motivo in r0.motivos, motivo
    assert "r0_final" not in informe.estados_alcanzados
    for escenario, resumen in m.demostrar_estados(sinteticos.historico(2081, 2713)).items():
        assert resumen["r0_final"] != "superada", escenario


def test_g1b_planos_separados_y_nunca_elevados():
    m = _modulo()
    _, bd, _, entradas = _recorrido(m)
    informe = m.evaluar_admision(entradas, bd)
    assert informe.planos == {"integridad_de_bytes": "superada", "autenticacion_de_r0": "sin_evidencia",
                              "recepcion_antes_del_plazo": "sin_evidencia",
                              "completitud_y_unicidad_del_canal": "sin_evidencia",
                              "aptitud_inferencial": "no_autorizada"}
    assert pi.AUTORIZA_EVALUACION is False
    todos = [*m.PUERTAS, *m.ESTADOS_DE_PUERTA, *m.MOTIVOS_DE_PUERTA, *m.RUTAS]
    for texto in todos:
        assert not re.search(r"autenticad|acreditad|fijad|aprobad|(?<!in)valid|apt[ao]", texto), texto


@pytest.mark.parametrize("ruta", ["ae72", "1_1", "1_0"])
def test_g1b_rutas_compatibles_no_admitidas_por_el_contrato(ruta):
    m = _modulo()
    d = pv.construir_declaracion(_elementos())
    bd = pv.bytes_de_declaracion(d)
    if ruta == "ae72":
        p = pv.construir_protocolo_candidato(d, protocolo_id="s", estrategia=_estrategia(), cortes=CORTES)
        esperado, verificacion = "ruta_ae72_no_admitida", "vinculo_de_bytes_verificado"
    elif ruta == "1_1":
        p = ve.construir_protocolo_con_campo_explicito(d, protocolo_id="s", estrategia=_estrategia(), cortes=CORTES)
        esperado, verificacion = "ruta_1_1_no_admitida", "vinculo_de_bytes_verificado"
    else:
        p = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                                   sintetico=True)
        esperado, verificacion = "sin_vinculo_r0", "protocolo_sin_vinculo_r0"
    entradas = _registro(p)
    informe = m.evaluar_admision(entradas, bd)
    assert informe.puertas["borrador_sintetico"].estado == "rechazada"
    assert informe.puertas["borrador_sintetico"].motivos == (esperado,)
    assert {informe.puertas[q].estado for q in PUERTAS[1:3]} == {"no_evaluable"}
    assert informe.puertas["r0_final"].estado == "rechazada"
    assert informe.verificacion_de_la_ruta == verificacion
    assert informe.estados_alcanzados == ()


@pytest.mark.parametrize("motivo", ["doble_vinculo", "claves_del_vinculo_distintas", "vinculo_ausente_en_esquema_1_2",
                                    "contrato_desconocido"])
def test_g1b_vinculo_doble_y_parcialmente_migrado(motivo):
    m = _modulo()
    informe = m.evaluar_admision([rp.serializar_entrada(_caso(motivo))], b"{}\n")
    assert informe.puertas["borrador_sintetico"].estado == "rechazada"
    assert informe.puertas["borrador_sintetico"].motivos == (motivo,)
    assert informe.ruta == "registro_invalido"


def test_g1b_version_desconocida_y_prediccion_ligada_al_protocolo_equivocado():
    m = _modulo()
    informe = m.evaluar_admision([rp.serializar_entrada(_protocolo_1_2(esquema="registro-prospectivo-ml/1.3"))], None)
    assert informe.puertas["borrador_sintetico"].motivos == ("registro_invalido",)
    _, bd, _, entradas = _recorrido(m)
    prediccion = rp.leer_entrada(entradas[1])
    alterada = rp.serializar_entrada({**prediccion, "protocolo_hash": "f" * 64})
    informe = m.evaluar_admision([entradas[0], alterada], bd)
    assert informe.puertas["borrador_sintetico"].estado == "rechazada"
    assert "protocolo distinto" in informe.detalle
    _, _, _, otro = _recorrido(m, elementos=_elementos("otro"))
    informe = m.evaluar_admision([entradas[0], otro[1]], bd)
    assert informe.puertas["borrador_sintetico"].motivos == ("registro_invalido",)


def test_g1b_cambios_de_declaracion_y_pendientes_contradictorios():
    m = _modulo()
    _, bd, _, entradas = _recorrido(m)
    otra = pv.bytes_de_declaracion(pv.construir_declaracion(_elementos("cambiada")))
    informe = m.evaluar_admision(entradas, otra)
    assert informe.puertas["vinculo_integro"].estado == "rechazada"
    assert informe.puertas["vinculo_integro"].motivos == ("hash_de_declaracion_no_coincide",)
    assert informe.puertas["declaracion_estructuralmente_completa"].estado == "no_evaluable"
    assert informe.puertas["declaracion_estructuralmente_completa"].motivos == ("declaracion_no_designada",)
    ausente = m.evaluar_admision(entradas, None)
    assert ausente.puertas["vinculo_integro"].estado == "pendiente"
    assert ausente.puertas["vinculo_integro"].motivos == ("declaracion_ausente",)
    invalida = m.evaluar_admision(entradas, b"no es json\n")
    assert invalida.puertas["vinculo_integro"].motivos == ("declaracion_invalida",)
    d = pv.construir_declaracion(_elementos(pendientes=(ELEMENTOS[2],)))
    p = rp.construir_protocolo_con_contrato_r0(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES,
                                               pendientes=[], sintetico=True,
                                               vinculo_r0=_vinculo_1_2(pv.hash_de_declaracion(d), pendientes=()))
    informe = m.evaluar_admision(_registro(p), pv.bytes_de_declaracion(d))
    assert informe.puertas["vinculo_integro"].motivos == ("pendientes_contradictorios",)
    assert "registro_con_pendientes" not in informe.puertas["r0_final"].motivos
    assert "vinculo_no_integro" in informe.puertas["r0_final"].motivos
    assert m.evaluar_admision(entradas, bd, protocolo_hash_esperado="0" * 64).puertas["vinculo_integro"].motivos == \
        ("protocolo_hash_no_coincide",)
    omitida = m.evaluar_admision(entradas, bd, objetivos_esperados=(("BALOTO", 2716),))
    assert omitida.puertas["vinculo_integro"].motivos == ("prediccion_omitida",)


def test_g1b_transiciones_permitidas_y_prohibidas():
    m = _modulo()
    t = m.TRANSICIONES
    assert t[("borrador_con_pendientes", "declaracion_estructuralmente_completa")] == \
        "solo_con_otro_protocolo_y_otro_registro"
    assert t[("borrador_con_pendientes", "r0_final")] == "prohibida"
    assert t[("declaracion_estructuralmente_completa", "r0_final")] == "prohibida_sin_evidencia"
    assert t[("r0_final", "borrador_con_pendientes")] == "prohibida"
    assert set(t.values()) <= {"solo_con_otro_protocolo_y_otro_registro", "prohibida", "prohibida_sin_evidencia"}
    e = ELEMENTOS[3]
    _, b_antes, _, r_antes = _recorrido(m, elementos=_elementos(pendientes=(e,)))
    _, b_despues, p_despues, r_despues = _recorrido(m)
    assert m.evaluar_admision(r_antes, b_despues).puertas["vinculo_integro"].motivos == \
        ("hash_de_declaracion_no_coincide",)
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="esquema desconocido|segundo protocolo"):
        rp.validar_registro([r_antes[0], _segundo_protocolo(r_antes[0], p_despues)])
    despues = m.evaluar_admision(r_despues, b_despues)
    assert despues.puertas["declaracion_estructuralmente_completa"].estado == "superada"
    assert despues.puertas["r0_final"].estado == "rechazada"


def test_g1b_propagacion_de_un_cambio_de_elemento():
    m = _modulo()
    base = _recorrido(m)
    cambiado_el = _elementos()
    cambiado_el[ELEMENTOS[8]] = {"estado": "declarado_sintetico", "valor": {"sintetico": "otro"}}
    cambiado = _recorrido(m, elementos=cambiado_el)
    assert base[1] != cambiado[1]
    assert base[2]["declaracion_r0"]["hash_declaracion"] != cambiado[2]["declaracion_r0"]["hash_declaracion"]
    assert rp.hash_entrada(base[3][0]) != rp.hash_entrada(cambiado[3][0])
    assert rp.leer_entrada(base[3][1])["protocolo_hash"] != rp.leer_entrada(cambiado[3][1])["protocolo_hash"]


def test_g1b_demostracion_reproducible_de_los_estados():
    m = _modulo()
    historico = sinteticos.historico(2081, 2713)
    a, b = m.demostrar_estados(historico), m.demostrar_estados(historico)
    assert a == b
    assert set(a) == set(m.ESCENARIOS_DE_DEMOSTRACION)
    assert a["declaracion_completa"]["declaracion_estructuralmente_completa"] == "superada"
    assert a["borrador_con_pendientes"]["vinculo_integro"] == "superada"
    assert a["borrador_con_pendientes"]["declaracion_estructuralmente_completa"] == "pendiente"
    assert a["declaracion_cambiada"]["vinculo_integro"] == "rechazada"
    assert a["ruta_ae72"]["borrador_sintetico"] == "rechazada"
    assert a["ruta_1_1"]["borrador_sintetico"] == "rechazada"
    assert a["vinculo_doble"]["borrador_sintetico"] == "rechazada"


def test_g1b_rutas_compatibles_y_requisitos_faltantes_documentados():
    m = _modulo()
    assert set(m.RUTAS_COMPATIBLES) == {"1_0", "ae72_parametros", "1_1_campo_explicito", "1_2_contrato"}
    admitidas = {k for k, v in m.RUTAS_COMPATIBLES.items() if v["admitida_por_el_contrato"]}
    assert admitidas == {"1_2_contrato"}
    for requisito in ("autenticacion_de_r0", "recepcion_antes_del_plazo", "completitud_y_unicidad_del_canal",
                      "protocolo_real", "D8", "D9", "autorizacion_de_evaluacion"):
        assert any(requisito in r for r in m.REQUISITOS_FALTANTES), requisito
    assert "1.1" in m.COMPATIBILIDAD and "1.0" in m.COMPATIBILIDAD


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


_PROHIBIDAS = {"go", "cumplido", "cumplida", "desbloqueado", "desbloqueada", "autorizado", "autorizada",
               "recomendado", "recomendada", "autenticado", "autenticada", "acreditado", "acreditada", "fijado",
               "fijada", "valido", "valida"}


def test_g1b_textos_sin_acreditacion():
    m = _modulo()
    textos = [m.COMPATIBILIDAD, m.LIMITES, *m.REQUISITOS_FALTANTES]
    textos += [v["texto"] for v in m.DECISIONES_DEL_CONTRATO.values()]
    textos += [v["texto"] for v in m.RUTAS_COMPATIBLES.values()]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


# ===========================================================================
# G2: invariantes (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae63_a_ae73():
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
    assert _huella((rp.ESQUEMA_ENTRADA_PROTOCOLO_VINCULO_R0, rp.ESQUEMAS_PROTOCOLO, rp.CAMPO_VINCULO_R0,
                    rp.REGLA_VINCULO_R0_CAMPO_EXPLICITO, rp.ESQUEMA_DECLARACION_R0, rp.MOTIVOS_VINCULO_R0,
                    ve.RUTAS, ve.ESTADO_DE_LAS_RUTAS, ve.ACTIVACION, ve.PLANOS_DEL_INFORME, ve.ESTADOS_DE_BYTES,
                    ve.COMPARACION_DE_RUTAS, ve.REQUISITOS_DE_MIGRACION, ve.MIGRACION_EJECUTADA,
                    ve.DECISIONES_REQUERIDAS, ve.COMPATIBILIDAD, ve.LIMITES)) == (
        "0ab953f95566948581dbb8cbad19797ecf44ae55f2943491441a2f414047a54d")
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"


def test_g2_bytes_de_registros_1_0_y_1_1_sin_cambios():
    p = rp.construir_protocolo(protocolo_id="sintetico-ae73", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                               sintetico=True)
    b = rp.serializar_entrada(p)
    assert rp.hash_entrada(b) == "c9e73601ac6d9668a3e50c8e76b75a130b214a68efaf5cf115b17d5a67ea3892"
    prediccion = rp.nueva_prediccion(rp.validar_registro([b]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                                     PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(prediccion)) == (
        "435918926917ea8ab712c7162eff5544998d340f3df711b1508815ce6429f2c6")
    assert rp.hash_entrada(rp.serializar_entrada(rp.construir_protocolo_borrador(_estrategia()))) == (
        "4b0096fea982e015c0ee8c2561c82d44d2b4ae5923383c5433a7c4dcaacd2d68")
    v = _vinculo_1_1("1" * 64, pendientes=("regla_de_duplicados",))
    p11 = rp.construir_protocolo_con_vinculo_r0(protocolo_id="sintetico-ae74", estrategia=_estrategia(), cortes=CORTES,
                                                pendientes=[], sintetico=True, vinculo_r0=v)
    b11 = rp.serializar_entrada(p11)
    assert rp.hash_entrada(b11) == "9ded8373d753fa68473b91728d900340e996c5af46ced4d2cc94ef5f56e80d0b"
    prediccion11 = rp.nueva_prediccion(rp.validar_registro([b11]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                                       PROBABILIDADES)
    assert rp.hash_entrada(rp.serializar_entrada(prediccion11)) == (
        "b9576ab70dede1a399e390946ad819d0792f24b3e946bbdfd67fe7bf603abc4a")


def test_g2_estados_decisiones_y_bloqueos_sin_cambios():
    assert {r.estado for r in {**ec.REQUISITOS_PREVIOS, **ec.CONDICIONES_DEL_PROTOCOLO}.values()} == {"sin_fijar"}
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert {e.estado for e in iv.ELEMENTOS_DE_R0.values()} == {"pendiente"}
    assert {p["estado"] for p in iv.PREGUNTAS_ABIERTAS_AE69.values()} == {"sin_respuesta"}
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    assert {d["estado"] for d in aa.DECISIONES_DEL_OPERADOR_AE71.values()} == {"sin_decidir"}
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

def test_g3_recorridos_de_ae72_y_ae73_siguen_funcionando():
    assert pv.demostrar_recorrido_sintetico(sinteticos.historico(2081, 2713)).estado_de_bytes == \
        "vinculo_de_bytes_verificado"
    d = pv.construir_declaracion(_elementos())
    p = ve.construir_protocolo_con_campo_explicito(d, protocolo_id="s", estrategia=_estrategia(), cortes=CORTES)
    informe = ve.verificar_vinculo_r0(_registro(p), pv.bytes_de_declaracion(d))
    assert informe.ruta == "ae73_campo_explicito" and informe.estado_de_bytes == "vinculo_de_bytes_verificado"


def test_g3_ae52_rechaza_segundo_protocolo_y_prediccion_con_protocolo_distinto():
    p1 = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia({"a": 1}), cortes=CORTES, pendientes=[],
                                sintetico=True)
    p2 = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia({"a": 2}), cortes=CORTES, pendientes=[],
                                sintetico=True)
    entradas = _registro(p1)
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="segundo protocolo"):
        rp.validar_registro([entradas[0], _segundo_protocolo(entradas[0], p2)])
    prediccion = rp.leer_entrada(entradas[1])
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="protocolo distinto"):
        rp.validar_registro([entradas[0], rp.serializar_entrada({**prediccion, "protocolo_hash": "f" * 64})])


def test_g3_ae72_informa_pendientes_y_marcadores_por_elemento():
    elementos = _elementos(pendientes=(ELEMENTOS[0],), marcadores=(ELEMENTOS[1],))
    d = pv.construir_declaracion(elementos)
    estados = pv.estados_de_elementos(d)
    assert estados[ELEMENTOS[0]] == "sin_fijar_explicito"
    assert estados[ELEMENTOS[1]] == "declarado_con_marcador_textual"
