"""Tests de la Etapa AE-69, validada: inventario verificable del contenido
de R0 (la declaracion previa del protocolo) frente al formato del protocolo
de AE-52, con un comprobador sintetico de completitud.

Tres grupos:

G1  dependen del modulo nuevo, que se importa dentro de cada prueba; sobre
    la base cada una falla por separado con `ModuleNotFoundError`.
G2  invariantes sobre codigo existente (huellas de AE-52 y AE-63 a AE-68,
    estados y decisiones); pasan sobre la base.
G3  integraciones contra la API publica real de AE-52 (A1, A2, A4, A11);
    pasan sobre la base porque comprueban codigo que ya existe.

`completa_sintetica_sin_autenticar` solo indica completitud estructural de
los once elementos: no acredita suficiencia de sus valores, autenticacion,
fijacion de R0 ni cumplimiento de ninguna condicion. R0, R9 y las ocho
condiciones siguen `sin_fijar`. Todo sintetico: sin red, relojes o servicios
reales, datos reales, PostgreSQL ni predicciones reales."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import pytest

from app.application.ml import auditoria_obligaciones_de_aplicacion as ao
from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import especificacion_condiciones_del_protocolo as ec
from app.application.ml import propuesta_evidencia_temporal_externa as pe
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import registro_prospectivo as rp
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml import verificacion_primaria_choe_ramdas as vp
from app.application.ml import verificacion_primaria_rfc_sellado_y_transparencia as vr
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from tests.unit.simulaciones import sinteticos

ONCE = ("conjunto_de_claves_y_revocacion", "identidad_del_canal", "composicion_de_la_clave_de_unicidad",
        "regla_de_duplicados", "reloj_zona_resolucion_cota_y_trato_del_intervalo", "margen_delta_y_mmd",
        "procedimiento_de_revision_completa", "politica_ante_vistas_divididas", "fuente_del_calendario",
        "definicion_del_plazo", "formato_de_entrada_y_recibo")
OCHO = tuple(ec.CONDICIONES_DEL_PROTOCOLO)
R0, R9 = "declaracion_previa_del_protocolo", "puente_entrada_canal"
BASE = "@9cd222c"
PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""


def _modulo():
    return importlib.import_module("app.application.ml.inventario_declaracion_previa_del_protocolo")


def _pendiente():
    return {"estado": "pendiente"}


def _declarado(valor):
    return {"estado": "declarado_sintetico", "valor": valor}


def _todos_pendientes():
    return {e: _pendiente() for e in ONCE}


def _completa():
    """Valores sinteticos de prueba: no son propuestas ni decisiones."""
    return {e: _declarado({"sintetico": f"valor-de-prueba-{i}"}) for i, e in enumerate(ONCE)}


def _estrategia():
    return {
        "nombre": "estrategia_sintetica", "descripcion": "estrategia sintetica solo para pruebas",
        "huella_codigo": "a" * 64, "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
        "entorno": {"python": "3.x", "scikit_learn": "0.0"},
    }


def _protocolo_sintetico(pendientes=()):
    return rp.construir_protocolo(protocolo_id="sintetico-ae69", estrategia=_estrategia(),
                                  cortes={"BALOTO": 2713, "BALOTO_REVANCHA": 2713}, pendientes=list(pendientes),
                                  sintetico=True)


def _plano(valor):
    if dataclasses.is_dataclass(valor):
        return {f.name: _plano(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, Mapping):
        return {str(k): _plano(v) for k, v in valor.items()}
    if isinstance(valor, (tuple, list)):
        return [_plano(v) for v in valor]
    return valor


def _huella(valor):
    return hashlib.sha256(json.dumps(_plano(valor), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ===========================================================================
# G1: dependen del modulo nuevo (fallan sobre la base con ModuleNotFoundError)
# ===========================================================================

def test_g1_once_elementos_con_todos_los_campos_y_pendientes():
    m = _modulo()
    assert tuple(m.ELEMENTOS_DE_R0) == ONCE
    for id_, e in m.ELEMENTOS_DE_R0.items():
        assert e.id == id_ and e.estado == "pendiente", id_
        for campo in ("definicion", "evidencia_que_lo_resolveria", "criterio_para_mantener_pendiente"):
            assert getattr(e, campo).strip(), (id_, campo)
        assert e.alimenta and e.estandar, id_
        assert e.situacion_en_ae52 in m.SITUACIONES_EN_AE52, id_
    situaciones = {id_: e.situacion_en_ae52 for id_, e in m.ELEMENTOS_DE_R0.items()}
    assert situaciones.pop("composicion_de_la_clave_de_unicidad") == \
        "componentes_en_prediccion_sin_declaracion_de_clave"
    assert set(situaciones.values()) == {"sin_campo_en_el_protocolo_ae52"}


def test_g1_cobertura_de_las_ocho_condiciones_y_r9():
    m = _modulo()
    destinos = [d for e in m.ELEMENTOS_DE_R0.values() for d in e.alimenta]
    assert set(destinos) == {*OCHO, R9}
    assert R0 not in destinos
    assert set(ec.DEPENDENCIAS_NORMATIVAS[R0]) == {*OCHO, R9}
    assert m.ELEMENTOS_DE_R0["formato_de_entrada_y_recibo"].alimenta == (R9,)
    assert set(m.ELEMENTOS_DE_R0["politica_ante_vistas_divididas"].alimenta) == {"revision_completa"}
    assert {"fuente_del_calendario", "definicion_del_plazo"} == {
        id_ for id_, e in m.ELEMENTOS_DE_R0.items() if "calendario_oficial" in e.alimenta}


def test_g1_elementos_disjuntos_de_los_pendientes_de_ae52_y_correspondencia_con_la_autenticacion():
    m = _modulo()
    assert not set(m.ELEMENTOS_DE_R0) & set(rp.PENDIENTES_BORRADOR_AE52)
    assert set(m.CORRESPONDENCIA_CON_PENDIENTES_AE52) <= set(rp.PENDIENTES_BORRADOR_AE52)
    sellado = m.CORRESPONDENCIA_CON_PENDIENTES_AE52["mecanismo_de_sellado_temporal_externo"]
    assert sellado["corresponde_a"] == "autenticacion_de_r0:sello_externo_anterior_al_corte"
    assert "sello_externo_anterior_al_corte" in ec.AUTENTICACION_DE_R0
    corte = m.CORRESPONDENCIA_CON_PENDIENTES_AE52["corte_temporal_por_juego"]
    assert corte["corresponde_a"] == "relacionado_con_definicion_del_plazo_sin_identificar"
    for c in m.CORRESPONDENCIA_CON_PENDIENTES_AE52.values():
        assert not c["corresponde_a"] in m.ELEMENTOS_DE_R0
    assert set(m.PREGUNTAS_ABIERTAS_AE69) == {"ubicacion_de_la_declaracion", "definicion_del_plazo_frente_al_corte",
                                              "expresion_de_pendientes_de_r0_en_ae52"}
    assert {p["estado"] for p in m.PREGUNTAS_ABIERTAS_AE69.values()} == {"sin_respuesta"}


@pytest.mark.parametrize("caso", [
    "no_es_dict", "proxy", "falta", "sobra", "clave_no_textual", "estado_desconocido", "pendiente_con_valor",
    "declarado_sin_valor", "elemento_no_dict", "float", "tuple", "set", "bytes", "clave_entera_en_valor",
    "proxy_en_valor",
])
def test_g1_declaraciones_incompletas_o_con_forma_invalida(caso):
    m = _modulo()
    d = _completa()
    e = ONCE[0]
    if caso == "no_es_dict":
        d = list(d.items())
    elif caso == "proxy":
        d = MappingProxyType(d)
    elif caso == "falta":
        del d[e]
    elif caso == "sobra":
        d["elemento_inventado"] = _pendiente()
    elif caso == "clave_no_textual":
        d[1] = d.pop(e)
    elif caso == "estado_desconocido":
        d[e] = {"estado": "fijado"}
    elif caso == "pendiente_con_valor":
        d[e] = {"estado": "pendiente", "valor": 1}
    elif caso == "declarado_sin_valor":
        d[e] = {"estado": "declarado_sintetico"}
    elif caso == "elemento_no_dict":
        d[e] = "pendiente"
    elif caso == "float":
        d[e] = _declarado(1.5)
    elif caso == "tuple":
        d[e] = _declarado(("a", "b"))
    elif caso == "set":
        d[e] = _declarado({"a"})
    elif caso == "bytes":
        d[e] = _declarado(b"a")
    elif caso == "clave_entera_en_valor":
        d[e] = _declarado({1: "a"})
    elif caso == "proxy_en_valor":
        d[e] = _declarado(MappingProxyType({"a": "b"}))
    assert m.comprobar_declaracion_sintetica(d) == "incompleta"
    motivos = m.motivos_de_incompletitud(d)
    assert motivos and list(motivos) == sorted(motivos)
    with pytest.raises(m.DeclaracionSinteticaInvalidaError):
        m.hash_de_declaracion_sintetica(d)


@pytest.mark.parametrize("vacio", [None, "", "   ", [], {}, {"sintetico": None}, ["a", ""], {"a": {}}])
def test_g1_valor_vacio_o_nulo_no_cuenta_como_declaracion_sustantiva(vacio):
    """Se define y prueba antes de usar el resultado completo: un valor vacio
    o nulo, tambien anidado, da `incompleta` y no se hashea."""
    m = _modulo()
    d = _completa()
    d["identidad_del_canal"] = _declarado(vacio)
    assert m.comprobar_declaracion_sintetica(d) == "incompleta"
    assert any(x.startswith("valor_vacio_o_nulo:identidad_del_canal") for x in m.motivos_de_incompletitud(d))
    with pytest.raises(m.DeclaracionSinteticaInvalidaError):
        m.hash_de_declaracion_sintetica(d)
    parcial = _todos_pendientes()
    parcial["identidad_del_canal"] = _declarado(vacio)
    assert m.comprobar_declaracion_sintetica(parcial) == "incompleta"
    assert "vacio" in m.TRATAMIENTO_DE_VALORES_VACIOS and "nulo" in m.TRATAMIENTO_DE_VALORES_VACIOS


def test_g1_resultados_todos_pendientes_parcial_y_completa_estructural():
    m = _modulo()
    assert m.RESULTADOS_DECLARACION == ("incompleta", "todos_pendientes", "parcial",
                                        "completa_sintetica_sin_autenticar")
    assert m.comprobar_declaracion_sintetica(_todos_pendientes()) == "todos_pendientes"
    mezcla = _todos_pendientes()
    mezcla["identidad_del_canal"] = _declarado("canal-sintetico")
    assert m.comprobar_declaracion_sintetica(mezcla) == "parcial"
    assert m.comprobar_declaracion_sintetica(_completa()) == "completa_sintetica_sin_autenticar"
    for d in (_todos_pendientes(), mezcla, _completa()):
        assert m.motivos_de_incompletitud(d) == ()
    for valor in (0, False, True, -3, "x", ["x"], {"k": 0}):
        uno = _completa()
        uno["regla_de_duplicados"] = _declarado(valor)
        assert m.comprobar_declaracion_sintetica(uno) == "completa_sintetica_sin_autenticar", valor
    omision = _completa()
    del omision["politica_ante_vistas_divididas"]
    assert m.comprobar_declaracion_sintetica(omision) == "incompleta"
    assert "falta:politica_ante_vistas_divididas" in m.motivos_de_incompletitud(omision)
    for r in m.RESULTADOS_DECLARACION:
        assert not re.search(r"autenticad|fijad|acreditad|aprobad", r), r
    alcance = m.ALCANCE_DE_LA_COMPLETITUD
    for frase in ("completitud estructural", "suficiencia", "autenticacion", "fijacion de R0",
                  "cumplimiento de ninguna condicion"):
        assert frase in alcance, frase


def test_g1_estado_actual_de_r0_todos_pendientes():
    m = _modulo()
    assert dict(m.ESTADO_ACTUAL_DE_R0) == {e: "pendiente" for e in ONCE}
    declaracion = {e: {"estado": s} for e, s in m.ESTADO_ACTUAL_DE_R0.items()}
    assert m.comprobar_declaracion_sintetica(declaracion) == "todos_pendientes"


def test_g1_hash_por_serializacion_de_ae52_en_ejemplos_concretos():
    """A10, limitado a los ejemplos probados: no se afirma nada universal
    sobre colisiones."""
    m = _modulo()
    ejemplos = [_todos_pendientes(), _completa()]
    for d in ejemplos:
        assert m.hash_de_declaracion_sintetica(d) == rp.hash_entrada(rp.serializar_entrada(d))
    base = _completa()
    variantes = []
    otro = _completa()
    otro["margen_delta_y_mmd"] = _pendiente()
    variantes.append(otro)
    otro = _completa()
    otro["margen_delta_y_mmd"] = _declarado({"sintetico": "otro-valor-de-prueba"})
    variantes.append(otro)
    otro = _completa()
    otro["margen_delta_y_mmd"] = _declarado(True)
    variantes.append(otro)
    otro = _completa()
    otro["margen_delta_y_mmd"] = _declarado(1)
    variantes.append(otro)
    hashes = [m.hash_de_declaracion_sintetica(d) for d in (base, *variantes)]
    assert len(set(hashes)) == len(hashes)
    assert m.hash_de_declaracion_sintetica(_completa()) == hashes[0]
    with pytest.raises(m.DeclaracionSinteticaInvalidaError):
        m.hash_de_declaracion_sintetica({})
    nan = _completa()
    nan["margen_delta_y_mmd"] = _declarado(float("nan"))
    assert m.comprobar_declaracion_sintetica(nan) == "incompleta"
    with pytest.raises(m.DeclaracionSinteticaInvalidaError):
        m.hash_de_declaracion_sintetica(nan)


def test_g1_contenido_completo_no_autentica_r0():
    m = _modulo()
    assert m.comprobar_declaracion_sintetica(_completa()) == "completa_sintetica_sin_autenticar"
    m.hash_de_declaracion_sintetica(_completa())
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert ec.REQUISITOS_PREVIOS[R0].estado == "sin_fijar"
    assert ec.REQUISITOS_PREVIOS[R9].estado == "sin_fijar"
    assert {c.estado for c in ec.CONDICIONES_DEL_PROTOCOLO.values()} == {"sin_fijar"}
    assert {e.estado for e in m.ELEMENTOS_DE_R0.values()} == {"pendiente"}
    assert dict(m.ESTADO_ACTUAL_DE_R0) == {e: "pendiente" for e in ONCE}


def test_g1_referencias_al_estandar_solo_de_ae67_y_rfc_9162_solo_certificados():
    m = _modulo()
    afirmaciones = {a.id for a in (*vr.AFIRMACIONES_RFC_3161, *vr.AFIRMACIONES_RFC_9162)}
    for e in m.ELEMENTOS_DE_R0.values():
        for ref in e.estandar:
            if ref == "ninguno":
                continue
            coincide = re.fullmatch(r"AE-67:(T\d|C\d)( solo_certificados)?", ref)
            assert coincide and coincide.group(1) in afirmaciones, (e.id, ref)
            if coincide.group(1).startswith("C"):
                assert ref.endswith("solo_certificados"), (e.id, ref)
    assert m.ELEMENTOS_DE_R0["fuente_del_calendario"].estandar == ("ninguno",)
    assert m.ELEMENTOS_DE_R0["formato_de_entrada_y_recibo"].estandar == ec.REQUISITOS_PREVIOS[R9].estandar


def test_g1_clasificacion_de_afirmaciones_con_procedencia_exacta():
    m = _modulo()
    assert m.CLASES_DE_AFIRMACION == ("hecho_observado_en_codigo", "hecho_citado_de_fuente", "derivacion_propia",
                                      "hipotesis_de_aplicacion")
    ids = tuple(a.id for a in m.CLASIFICACION_DE_AFIRMACIONES)
    assert ids == tuple(f"A{i}" for i in range(1, 12))
    clases = {a.id: a.clase for a in m.CLASIFICACION_DE_AFIRMACIONES}
    assert clases == {"A1": "hecho_observado_en_codigo", "A2": "hecho_observado_en_codigo",
                      "A3": "derivacion_propia", "A4": "hecho_observado_en_codigo",
                      "A5": "hipotesis_de_aplicacion", "A6": "derivacion_propia", "A7": "derivacion_propia",
                      "A8": "hecho_citado_de_fuente", "A9": "hipotesis_de_aplicacion",
                      "A10": "hecho_observado_en_codigo", "A11": "hecho_observado_en_codigo"}
    afirmaciones_9162 = {a.id: a for a in vr.AFIRMACIONES_RFC_9162}
    afirmaciones_67 = {a.id for a in (*vr.AFIRMACIONES_RFC_3161, *vr.AFIRMACIONES_RFC_9162)}
    pruebas = {n for n in globals() if n.startswith("test_")}
    for a in m.CLASIFICACION_DE_AFIRMACIONES:
        assert a.texto.strip() and a.evidencia.strip() and a.procedencia, a.id
        if a.clase == "hecho_observado_en_codigo":
            assert any(p.endswith(BASE) and p.startswith("backend/app/") for p in a.procedencia), a.id
            citadas = [p.removeprefix("prueba:") for p in a.procedencia if p.startswith("prueba:")]
            assert citadas and set(citadas) <= pruebas, a.id
            assert a.estado == "observado_en_pruebas", a.id
        elif a.clase == "hecho_citado_de_fuente":
            for p in a.procedencia:
                coincide = re.fullmatch(r"AE-67:(C\d|T\d)", p)
                assert coincide and coincide.group(1) in afirmaciones_67, (a.id, p)
            assert a.estado == "citado_de_ae67", a.id
        elif a.clase == "derivacion_propia":
            for p in a.procedencia:
                assert p.startswith("premisa:"), (a.id, p)
                premisa = p.removeprefix("premisa:")
                if re.fullmatch(r"A\d+", premisa):
                    assert premisa in ids and premisa != a.id
                elif premisa.startswith("AE-67:"):
                    assert premisa.removeprefix("AE-67:") in afirmaciones_67
                else:
                    modulo, simbolo = premisa.rsplit(".", 1)
                    assert hasattr(importlib.import_module(f"app.application.ml.{modulo}"), simbolo), p
            assert a.estado == "derivado", a.id
        else:
            assert a.estado == "pendiente", a.id
    (a8,) = [a for a in m.CLASIFICACION_DE_AFIRMACIONES if a.id == "A8"]
    assert set(a8.procedencia) == {f"AE-67:C{i}" for i in range(1, 8)}
    for p in a8.procedencia:
        assert afirmaciones_9162[p.removeprefix("AE-67:")].referencias, p
    (a10,) = [a for a in m.CLASIFICACION_DE_AFIRMACIONES if a.id == "A10"]
    assert "ejemplos" in a10.texto and "colisiones" in a10.texto


def test_g1_vias_siguen_pendientes_con_el_estado_actual_de_r0():
    m = _modulo()
    por_requisito = {}
    for id_, e in m.ELEMENTOS_DE_R0.items():
        for d in e.alimenta:
            por_requisito.setdefault(d, []).append(id_)
    por_requisito["politica_de_vistas_divididas"] = ["politica_ante_vistas_divididas"]
    por_requisito[R0] = list(ONCE)
    antes = {id_: r.estado for id_, r in {**ec.REQUISITOS_PREVIOS, **ec.CONDICIONES_DEL_PROTOCOLO}.items()}
    for via, requisitos in ec.REQUISITOS_DE_VIA.items():
        escenario = {k: bool(por_requisito.get(k)) and all(
            m.ESTADO_ACTUAL_DE_R0[e] == "declarado_sintetico" for e in por_requisito[k]) for k in requisitos}
        assert not any(escenario.values()), via
        assert ec.estado_hipotetico_de_via(via, escenario) == "pendiente", via
    despues = {id_: r.estado for id_, r in {**ec.REQUISITOS_PREVIOS, **ec.CONDICIONES_DEL_PROTOCOLO}.items()}
    assert antes == despues and set(despues.values()) == {"sin_fijar"}


def test_g1_modulo_puro_sin_red_reloj_ni_archivos():
    m = _modulo()
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess", "random", "os", "pathlib",
                  "sqlalchemy", "datetime"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
            assert not (nodo.module or "").startswith("app.infrastructure")
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "utcnow", "today"}, nodo.attr
        if isinstance(nodo, ast.Name):
            assert nodo.id not in {"open", "eval", "exec"}, nodo.id


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida",
               "autenticado", "autenticada", "acreditado", "acreditada", "fijado", "fijada", "valido", "valida"}


def test_g1_textos_sin_aprobacion_autorizacion_ni_acreditacion():
    m = _modulo()
    textos = [m.ALCANCE_DE_LA_COMPLETITUD, m.TRATAMIENTO_DE_VALORES_VACIOS, m.RELACION_CON_AE52,
              *m.RESULTADOS_DECLARACION, *m.SITUACIONES_EN_AE52]
    textos += [p["texto"] for p in m.PREGUNTAS_ABIERTAS_AE69.values()]
    textos += [c["texto"] for c in m.CORRESPONDENCIA_CON_PENDIENTES_AE52.values()]
    for e in m.ELEMENTOS_DE_R0.values():
        textos += [e.definicion, e.evidencia_que_lo_resolveria, e.criterio_para_mantener_pendiente]
    for a in m.CLASIFICACION_DE_AFIRMACIONES:
        textos += [a.texto, a.evidencia]
    fijos = "|".join(sorted({*OCHO, R0, R9}, key=len, reverse=True))
    textos = [re.sub(fijos, " ", t) for t in textos]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


# ===========================================================================
# G2: invariantes sobre codigo existente (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae63_a_ae67():
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


def test_g2_huellas_de_ae68_y_ae52():
    assert _huella((ec.ALCANCE_RFC_9162, ec.MODELO_DE_FIRMA, ec.AUTENTICACION_DE_R0, ec.REQUISITOS_PREVIOS,
                    ec.CONDICIONES_DEL_PROTOCOLO, ec.CORRESPONDENCIA_CON_AE66, ec.DEPENDENCIAS_NORMATIVAS,
                    ec.DEPENDENCIAS_DE_VERIFICACION, ec.INSTANTES, ec.HIPOTESIS_TEMPORALES,
                    ec.LIMITE_DE_COMPLETITUD, tuple(ec.REGLAS_DE_DUPLICADOS_CANDIDATAS),
                    ec.REGLA_DE_DUPLICADOS_ELEGIDA, ec.RESULTADOS_RELOJ, ec.REQUISITOS_DE_VIA,
                    ec.RESULTADOS_DE_VIA)) == (
        "03c83bb1719e68bc14744bde36971f92a7a0f45784512424566305c2f504b00d")
    assert _huella((rp.ESQUEMA_ENTRADA, rp.TIPOS_ENTRADA, rp.REGLAS_EVALUACION_AE52, rp.PENDIENTES_BORRADOR_AE52,
                    rp.NOTA_PROTOCOLO, rp.ALCANCE_REGISTRO)) == (
        "4f31cdeb3c4d29b1740592d4d81de2f8f51305abf4a82743c49f12985621c50b")
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"


def test_g2_estados_decisiones_y_bloqueos_sin_cambios():
    assert {r.estado for r in {**ec.REQUISITOS_PREVIOS, **ec.CONDICIONES_DEL_PROTOCOLO}.values()} == {"sin_fijar"}
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert ec.REGLA_DE_DUPLICADOS_ELEGIDA is None
    assert set(vr.CONDICIONES_DEL_REPOSITORIO.values()) == {"sin_fijar"}
    condiciones = {c.id: c.estado for c in tc.CONDICIONES_DE_TRASLADO}
    for id_ in ("F1_anterioridad", "F2_correspondencia_de_la_filtracion", "O3_tratamiento_de_omisiones",
                "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert condiciones[id_] == "pendiente", id_
    for id_ in ("F2_correspondencia_de_la_filtracion", "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert vp.ESTADOS_TRAS_AE64[id_]["estado"] == "pendiente", id_
    for o in ao.OBLIGACIONES_AE65.values():
        assert o.estado == "pendiente", o.id
    (sellado,) = [d for d in pi.DECISIONES_REQUERIDAS if d.id == "mecanismo_de_sellado_temporal_externo"]
    assert sellado.valor is None and sellado.estado == "sin_decidir"
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    pi.verificar_expediente()
    assert len(rp.PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"


# ===========================================================================
# G3: integraciones contra la API publica real de AE-52 (pasan sobre la base)
# ===========================================================================

def test_g3_a1_protocolo_sintetico_con_clave_adicional_se_rechaza():
    protocolo = _protocolo_sintetico()
    assert rp.validar_registro([rp.serializar_entrada(protocolo)]).total == 1
    ampliado = {**protocolo, "identidad_del_canal": None}
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        rp.validar_registro([rp.serializar_entrada(ampliado)])


def test_g3_a2_identificador_de_r0_en_pendientes_se_rechaza_tambien_sintetico():
    assert _protocolo_sintetico(pendientes=[])["sintetico"] is True
    for elemento in ONCE:
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            _protocolo_sintetico(pendientes=[elemento])


def test_g3_a4_prediccion_sintetica_contiene_los_componentes_de_la_clave():
    entradas = [rp.serializar_entrada(_protocolo_sintetico())]
    estado = rp.validar_registro(entradas)
    prediccion = rp.nueva_prediccion(estado, "BALOTO", 2714, sinteticos.historico(2081, 2713), PROBABILIDADES)
    assert {"protocolo_hash", "codigo_juego", "sorteo_objetivo"} <= set(prediccion)
    assert prediccion["protocolo_hash"] == estado.hash_protocolo
    entradas.append(rp.serializar_entrada(prediccion))
    assert rp.validar_registro(entradas).total == 2


def test_g3_a11_comportamiento_observado_del_serializador_de_ae52():
    s = rp.serializar_entrada
    assert s([1]) == b"[1]\n" and s("t") == b'"t"\n' and s(1.0) == b"1.0\n"
    assert s({1: "x"}) == s({"1": "x"})
    assert s({"a": (1, 2)}) == s({"a": [1, 2]})
    for invalido in ({"a": float("nan")}, {"a": {1, 2}}, {"a": b"x"}, MappingProxyType({"a": 1}), {1: "x", "b": 2}):
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            s(invalido)
    with pytest.raises(TypeError):
        rp.hash_entrada("texto")
    assert rp.hash_entrada(b"") == hashlib.sha256(b"").hexdigest()
    assert rp.leer_entrada(s({"b": 1, "a": 2})) == {"a": 2, "b": 1}
