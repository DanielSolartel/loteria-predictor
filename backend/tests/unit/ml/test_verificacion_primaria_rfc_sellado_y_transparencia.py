"""Tests de la Etapa AE-67, validada: verificacion primaria de RFC 3161,
RFC 5816 y RFC 9162 frente a las afirmaciones pendientes de AE-66.

Comprueban la procedencia de los archivos oficiales recibidos (TXT de RFC
3161 y RFC 5816, PDF de RFC 9162), la correspondencia uno a uno con las
afirmaciones de AE-66, la forma de las citas segun el formato (lineas del
TXT o pagina del PDF con comprobacion visual), las discrepancias con AE-66
y la separacion entre las garantias del estandar y las ocho condiciones
del repositorio, que siguen sin fijar. Las funciones del intervalo del
sello dependen de T2 (accuracy de RFC 3161); C4 se verifica aparte.

El modulo nuevo se importa dentro de cada prueba para que, sobre la base,
cada regresion falle por separado. Todo sintetico: sin red, reloj real,
servicio de sellado, datos reales, PostgreSQL ni predicciones reales."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.application.ml import auditoria_obligaciones_de_aplicacion as ao
from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import propuesta_evidencia_temporal_externa as pe
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import registro_prospectivo as rp
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml import verificacion_primaria_choe_ramdas as vp
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53

UTC = timezone.utc
PLAZO = datetime(2021, 9, 30, 2, 0, tzinfo=UTC)  # 21:00 en Bogota
CONDICIONES = ("identidad_autorizada", "canal_canonico", "unicidad_por_objetivo", "regla_de_duplicados",
               "reloj_de_recepcion", "margen_de_incorporacion", "revision_completa", "calendario_oficial")


def _modulo():
    return importlib.import_module("app.application.ml.verificacion_primaria_rfc_sellado_y_transparencia")


def _afirmaciones(m):
    return {a.id: a for a in (*m.AFIRMACIONES_RFC_3161, *m.AFIRMACIONES_RFC_9162)}


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


# ---------------------------------------------------------------------------
# Procedencia y forma de las citas
# ---------------------------------------------------------------------------

def test_procedencia_de_los_archivos_oficiales_recibidos():
    m = _modulo()
    p = m.PROCEDENCIA_RFC
    assert set(p) == {"rfc_3161", "rfc_5816", "rfc_9162"}
    assert (p["rfc_3161"].formato, p["rfc_3161"].bytes, p["rfc_3161"].sha256) == (
        "txt", 54585, "39fd17644ff2d654bc83814a78b1c5b5e7517f496741f34ead5064943eb98240")
    assert (p["rfc_5816"].formato, p["rfc_5816"].bytes, p["rfc_5816"].sha256) == (
        "txt", 10216, "9a3eba6ecf14afc7820c51034a608d54d188344a43e9189b0e023d4a6a98f649")
    assert (p["rfc_9162"].formato, p["rfc_9162"].bytes, p["rfc_9162"].sha256) == (
        "pdf", 665522, "f0fafb9ef6f0555fc9ea5a65fb3552dea5957999aeb04162b2e8d0a748b1a89d")
    for id_, procedencia in p.items():
        assert procedencia.via == "archivo_oficial_aportado_por_el_operador_leido_por_claude", id_
        assert "no autentica" in procedencia.alcance_del_hash, id_
        assert procedencia.url_declarada.startswith("https://www.rfc-editor.org/rfc/"), id_
        assert procedencia.erratas == "no_consultadas", id_
    assert p["rfc_3161"].lectura == p["rfc_5816"].lectura == "texto_fuente_txt"
    assert p["rfc_9162"].lectura == "pdf_visual" and p["rfc_9162"].paginas == 53
    assert p["rfc_9162"].cabecera["categoria"] == "Experimental"
    assert p["rfc_9162"].cabecera["obsoletes"] == "6962"
    assert p["rfc_3161"].cabecera["categoria"] == "Standards Track"


def test_relacion_updates_derivada_de_rfc_5816():
    m = _modulo()
    p = m.PROCEDENCIA_RFC
    assert p["rfc_5816"].cabecera["updates"] == "3161"
    assert "updated_by" not in p["rfc_3161"].cabecera  # RFC 3161 es anterior; no lo declara en su cabecera
    assert "rfc_5816" in p["rfc_3161"].relaciones["actualizado_por"]
    assert "derivad" in p["rfc_3161"].relaciones["actualizado_por"]


def test_impresiones_pdf_previas_solo_como_apoyo():
    m = _modulo()
    for id_ in ("rfc_3161", "rfc_5816"):
        (apoyo,) = m.PROCEDENCIA_RFC[id_].apoyo_renderizado
        assert apoyo["uso"] == "apoyo_de_lectura_no_fuente"
        assert apoyo["formato"] == "pdf_impreso_desde_el_navegador"
    for a in _afirmaciones(m).values():
        for r in a.referencias:
            assert r.comprobacion in ("texto_fuente_txt", "pdf_visual"), a.id


def test_forma_de_las_citas_segun_el_formato():
    m = _modulo()
    visuales = set(m.PROCEDENCIA_RFC["rfc_9162"].paginas_comprobadas_visualmente)
    for a in _afirmaciones(m).values():
        for r in a.referencias:
            assert r.seccion and r.cita, a.id
            if r.fuente in ("rfc_3161", "rfc_5816"):
                assert r.comprobacion == "texto_fuente_txt" and r.pagina is None, a.id
                inicio, fin = r.lineas
                assert 1 <= inicio <= fin, a.id
            else:
                assert r.fuente == "rfc_9162", a.id
                assert r.comprobacion == "pdf_visual" and r.lineas is None, a.id
                assert r.pagina in visuales, (a.id, r.pagina)


# ---------------------------------------------------------------------------
# Inventario frente a AE-66 y estados de las afirmaciones
# ---------------------------------------------------------------------------

def _textos_de_ae66(id_fuente, id_alternativa):
    alternativa = pe.ALTERNATIVAS[id_alternativa]
    return (set(pe.FUENTES_PRIMARIAS[id_fuente].atribuido_pendiente)
            | {alternativa.latencia, alternativa.instante, alternativa.precision, *alternativa.supuestos,
               *alternativa.fallos_posibles, *alternativa.pruebas_verificables})


def test_inventario_uno_a_uno_con_ae66():
    m = _modulo()
    assert [a.id for a in m.AFIRMACIONES_RFC_3161] == ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]
    assert [a.id for a in m.AFIRMACIONES_RFC_9162] == ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
    for afirmaciones, fuente, alternativa in ((m.AFIRMACIONES_RFC_3161, "rfc_3161", "A1"),
                                              (m.AFIRMACIONES_RFC_9162, "rfc_9162", "A4")):
        disponibles = _textos_de_ae66(fuente, alternativa)
        usados = {o for a in afirmaciones for o in a.origen_ae66}
        assert usados <= disponibles, usados - disponibles
        assert set(pe.FUENTES_PRIMARIAS[fuente].atribuido_pendiente) <= usados


def test_estados_y_referencias_de_cada_afirmacion():
    m = _modulo()
    assert m.ESTADOS_AFIRMACION == ("verificada_en_texto_oficial", "matizada_por_el_texto_oficial", "no_en_la_fuente",
                                    "pendiente_de_texto_oficial")
    for a in _afirmaciones(m).values():
        assert a.estado in m.ESTADOS_AFIRMACION, a.id
        assert a.lo_que_sostiene and a.condicion_del_repositorio, a.id
        if a.estado in ("verificada_en_texto_oficial", "matizada_por_el_texto_oficial"):
            assert a.referencias, a.id
    estados = {i: a.estado for i, a in _afirmaciones(m).items()}
    assert estados["T1"] == estados["T2"] == estados["T4"] == estados["T5"] == "verificada_en_texto_oficial"
    assert estados["T3"] == estados["T6"] == estados["T7"] == "matizada_por_el_texto_oficial"
    assert estados["C1"] == estados["C2"] == estados["C3"] == estados["C4"] == "verificada_en_texto_oficial"
    assert estados["C5"] == estados["C7"] == "matizada_por_el_texto_oficial"
    assert estados["C6"] == "no_en_la_fuente"


def test_t5_se_apoya_en_rfc_5816_para_el_certificado_del_firmante():
    m = _modulo()
    t5 = _afirmaciones(m)["T5"]
    fuentes = {r.fuente for r in t5.referencias}
    assert fuentes == {"rfc_3161", "rfc_5816"}
    assert any("ESSCertIDv2" in r.cita for r in t5.referencias if r.fuente == "rfc_5816")


def test_testigos_y_duplicados_siguen_como_condiciones_del_protocolo():
    m = _modulo()
    a = _afirmaciones(m)
    assert a["C6"].referencias and all(r.fuente == "rfc_9162" for r in a["C6"].referencias)
    assert "not defined here" in " ".join(r.cita for r in a["C6"].referencias)
    assert "trusted third party" in " ".join(r.cita for r in a["C5"].referencias)
    assert "SHOULD return the same SCT" in " ".join(r.cita for r in a["C7"].referencias)
    assert "regla_de_duplicados" in a["C7"].condicion_del_repositorio
    assert "canal_canonico" in a["T6"].condicion_del_repositorio


def test_condiciones_del_repositorio_sin_fijar():
    m = _modulo()
    assert tuple(m.CONDICIONES_DEL_REPOSITORIO) == CONDICIONES
    assert set(m.CONDICIONES_DEL_REPOSITORIO.values()) == {"sin_fijar"}
    mencionadas = {c for a in _afirmaciones(m).values() for c in CONDICIONES if c in a.condicion_del_repositorio}
    assert mencionadas == set(CONDICIONES)


def test_discrepancias_con_ae66_sin_reescribir_ae66():
    m = _modulo()
    ids = {d["afirmacion"] for d in m.DISCREPANCIAS_CON_AE66}
    assert {"T3", "T7", "C5", "C6", "C7", "categoria_rfc_9162"} <= ids
    for d in m.DISCREPANCIAS_CON_AE66:
        assert d["texto_ae66"] and d["texto_oficial"] and d["tratamiento"], d["afirmacion"]
        assert "no se modifica" in d["tratamiento"], d["afirmacion"]


def test_derivacion_del_margen_bajo_rfc_9162_es_propia_y_sin_fijar():
    m = _modulo()
    d = m.DERIVACION_MARGEN_RFC_9162
    assert d["clase"] == "derivacion_propia"
    assert "11.1" in d["base"] and "p. 46" in d["base"]
    assert d["estado_en_el_repositorio"] == "margen_de_incorporacion_sin_fijar"


# ---------------------------------------------------------------------------
# Intervalo del sello (depende de T2) y C4 por separado
# ---------------------------------------------------------------------------

def test_precision_y_intervalo_del_sello():
    m = _modulo()
    gen = datetime(2021, 9, 30, 1, 0, tzinfo=UTC)
    assert m.intervalo_del_sello(gen, m.PrecisionSello(seconds=1, millis=500)) == (
        gen - timedelta(seconds=1, milliseconds=500), gen + timedelta(seconds=1, milliseconds=500))
    assert m.intervalo_del_sello(gen, m.PrecisionSello()) == (gen, gen)  # campos ausentes valen cero
    assert m.intervalo_del_sello(gen, None) is None  # accuracy ausente: puede venir por otros medios
    for invalida in ({"millis": 0}, {"millis": 1000}, {"micros": 0}, {"seconds": -1}):
        with pytest.raises(ValueError):
            m.PrecisionSello(**invalida)


def test_sello_frente_al_plazo():
    m = _modulo()
    assert m.RESULTADOS_SELLO == ("anterior_con_margen_de_precision", "no_concluyente_por_precision",
                                  "posterior_al_plazo_con_margen_de_precision", "precision_ausente_pendiente")
    un_segundo = m.PrecisionSello(seconds=1)
    assert m.sello_anterior_al_plazo(PLAZO - timedelta(seconds=2), un_segundo, PLAZO) == \
        "anterior_con_margen_de_precision"
    assert m.sello_anterior_al_plazo(PLAZO - timedelta(milliseconds=500), un_segundo, PLAZO) == \
        "no_concluyente_por_precision"
    assert m.sello_anterior_al_plazo(PLAZO - timedelta(seconds=1), un_segundo, PLAZO) == "no_concluyente_por_precision"
    assert m.sello_anterior_al_plazo(PLAZO + timedelta(seconds=1), un_segundo, PLAZO) == \
        "posterior_al_plazo_con_margen_de_precision"
    assert m.sello_anterior_al_plazo(PLAZO - timedelta(hours=1), None, PLAZO) == "precision_ausente_pendiente"
    for resultado in m.RESULTADOS_SELLO:
        assert "acreditad" not in resultado


def test_solicitud_antes_del_plazo_no_implica_gentime_anterior():
    """Refuta: 'la latencia es la de una solicitud'. RFC 3161 admite respuestas
    diferidas (waiting, sondeo) y genTime es el instante de creacion del token."""
    m = _modulo()
    solicitud = PLAZO - timedelta(seconds=1)
    gen_time = PLAZO + timedelta(seconds=30)  # token creado tras una respuesta diferida
    assert solicitud < PLAZO
    assert m.sello_anterior_al_plazo(gen_time, m.PrecisionSello(seconds=1), PLAZO) == \
        "posterior_al_plazo_con_margen_de_precision"


def test_sello_anterior_no_implica_unicidad():
    """Dos cabezas bifurcadas selladas antes del plazo son ambas anteriores:
    el sello no aporta canal canonico ni unicidad por objetivo."""
    m = _modulo()
    clave = b"clave-sintetica-solo-para-pruebas"
    antes = PLAZO - timedelta(hours=1)
    sellos = [pe.sellar_sintetico(h, antes, clave) for h in ("a" * 64, "b" * 64)]
    assert len(pe.sellos_antes_del_plazo(sellos, PLAZO, clave)) == 2
    for s in sellos:
        assert m.sello_anterior_al_plazo(s.instante, m.PrecisionSello(seconds=1), PLAZO) == \
            "anterior_con_margen_de_precision"
    assert m.CONDICIONES_DEL_REPOSITORIO["unicidad_por_objetivo"] == "sin_fijar"


def test_c4_incorporacion_dentro_del_mmd_con_las_funciones_de_ae66():
    """C4 por separado: una entrada aceptada antes del plazo puede
    incorporarse despues, dentro del MMD; una vista anterior a plazo + MMD no
    es concluyente. El reloj es el del registro y el margen sigue sin fijar."""
    _modulo()
    mmd = timedelta(hours=24)
    entrada = pe.EntradaBitacora(clave=("p" * 64, "BALOTO", 2715), tipo="prediccion", contenido_hash="c" * 64,
                                 recibido_en=PLAZO - timedelta(minutes=1), incluido_en=PLAZO + timedelta(hours=20))
    temprana = PLAZO + timedelta(hours=12)
    vista = pe.vista_publicada_en((entrada,), temprana)
    assert vista == ()
    assert pe.evaluar_ausencia_inferida(vista, entrada.clave, PLAZO, mmd, temprana,
                                        reloj_de_recepcion="reloj_del_registro") == \
        "vista_no_concluyente_anterior_a_plazo_mas_margen"
    tardia = PLAZO + mmd
    vista = pe.vista_publicada_en((entrada,), tardia)
    assert pe.evaluar_ausencia_inferida(vista, entrada.clave, PLAZO, mmd, tardia,
                                        reloj_de_recepcion="reloj_del_registro") == "entrada_recibida_antes_del_plazo"


def test_instantes_sin_zona_se_rechazan():
    m = _modulo()
    with pytest.raises(ValueError):
        m.sello_anterior_al_plazo(datetime(2021, 9, 30, 1, 0), m.PrecisionSello(seconds=1), PLAZO)
    with pytest.raises(ValueError):
        m.intervalo_del_sello(datetime(2021, 9, 30, 1, 0), m.PrecisionSello(seconds=1))


# ---------------------------------------------------------------------------
# Estados, pureza, vocabulario e invariante
# ---------------------------------------------------------------------------

def test_estados_y_decisiones_sin_cambios():
    _modulo()
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
    assert pe.RECOMENDACION_CONDICIONAL["estado"] == "recomendacion_condicional_para_decision_del_operador"


def test_modulo_puro_sin_red_ni_reloj():
    m = _modulo()
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "utcnow", "today"}, nodo.attr


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def test_textos_sin_aprobacion_ni_autorizacion():
    m = _modulo()
    textos = [str(v) for v in m.DERIVACION_MARGEN_RFC_9162.values()]
    for a in _afirmaciones(m).values():
        textos += [a.lo_que_sostiene, a.condicion_del_repositorio]
    for d in m.DISCREPANCIAS_CON_AE66:
        textos += [str(v) for v in d.values()]
    for p in m.PROCEDENCIA_RFC.values():
        textos.append(p.alcance_del_hash)
    # Los identificadores fijos de las condiciones (p. ej. identidad_autorizada) no son vocabulario de autorizacion.
    textos = [re.sub("|".join(CONDICIONES), " ", t) for t in textos]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


def test_estado_bloqueos_y_registros_intactos():
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    pi.verificar_expediente()
    assert len(rp.PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"
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
