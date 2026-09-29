"""Tests de la Etapa AE-66, validada: propuesta revisable de evidencia
temporal externa para F1, F2 y O3.

Comprueban el catalogo de alternativas y complementos, el estado de
verificacion de las fuentes primarias, la separacion entre la omision
declarada (via 1) y la ausencia inferida de una vista (via 2), y los
contraejemplos sinteticos B1-B7. Cada contraejemplo indica que afirmacion
refuta y que supuestos del modelo usa. Ningun resultado afirma una
acreditacion operativa; ninguna decision recibe valor y ningun estado
cambia.

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
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import registro_prospectivo as rp
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml import verificacion_primaria_choe_ramdas as vp
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53, metricas_por_sorteo
from tests.unit.simulaciones import sinteticos

CORTE = 2713
BOGOTA = timezone(timedelta(hours=-5))
PLAZO = datetime(2021, 9, 29, 21, 0, tzinfo=BOGOTA)
MARGEN = timedelta(minutes=30)
CLAVE_PRUEBA = b"clave-sintetica-solo-para-pruebas"
FIJA = tuple(0.9 if n <= 5 else 0.1 for n in range(1, 44))


def _modulo():
    return importlib.import_module("app.application.ml.propuesta_evidencia_temporal_externa")


def _historico(hasta):
    return sinteticos.historico(2081, hasta)


def _sorteo(numero):
    return tuple(_historico(numero)[-1].numeros)


def _oraculo(numeros):
    return tuple(0.9 if n in numeros else 0.1 for n in range(1, 44))


def _diferencia_brier(probabilidades, numeros):
    return metricas_por_sorteo("BALOTO", CORTE + 1, list(probabilidades), list(numeros)).diferencias["brier_score"]


def _protocolo():
    estrategia = {
        "nombre": "estrategia_sintetica_ae66", "descripcion": "estrategia sintetica solo para pruebas",
        "huella_codigo": "c" * 64, "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
        "entorno": {"python": "3.x"},
    }
    return rp.construir_protocolo(protocolo_id="ae66-sintetico", estrategia=estrategia, cortes={"BALOTO": CORTE},
                                  pendientes=[], sintetico=True)


class _Registro:
    def __init__(self, entradas=None):
        self.entradas = list(entradas) if entradas is not None else [rp.serializar_entrada(_protocolo())]

    @property
    def estado(self):
        return rp.validar_registro(self.entradas)

    def predecir(self, objetivo, probabilidades):
        entrada = rp.nueva_prediccion(self.estado, "BALOTO", objetivo, _historico(objetivo - 1), list(probabilidades))
        self.entradas.append(rp.serializar_entrada(entrada))

    def resultado(self, objetivo):
        self.entradas.append(rp.serializar_entrada(rp.nuevo_resultado(self.estado, "BALOTO", objetivo,
                                                                      _sorteo(objetivo))))


def _entrada(m, objetivo, tipo, recibido, incluido, contenido="a"):
    return m.EntradaBitacora(clave=("p" * 64, "BALOTO", objetivo), tipo=tipo,
                             contenido_hash=hashlib.sha256(contenido.encode()).hexdigest(),
                             recibido_en=recibido, incluido_en=incluido)


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
# Catalogo, fuentes y recomendacion
# ---------------------------------------------------------------------------

def test_catalogo_de_alternativas_y_complementos_completo():
    m = _modulo()
    assert m.REQUISITOS == ("a_salida_y_vinculo", "b_unico_y_completo", "c_ausencia_de_prediccion",
                            "d_calendario_y_hora")
    assert m.COLUMNAS_DE_LA_MATRIZ == ("a_salida_y_vinculo", "b_unico_y_completo", "c_via_1_omision_declarada",
                                       "c_via_2_ausencia_inferida", "d_calendario_y_hora")
    assert set(m.ALTERNATIVAS) == {"A1", "A2", "A3", "A4", "A5"}
    assert set(m.COMPLEMENTOS) == {"M", "R", "C", "K"}
    for a in m.ALTERNATIVAS.values():
        for campo in ("nombre", "instante", "precision", "latencia", "costo"):
            assert getattr(a, campo), (a.id, campo)
        assert a.supuestos and a.pruebas_verificables and a.fallos_posibles, a.id
        assert set(a.matriz) == set(m.COLUMNAS_DE_LA_MATRIZ), a.id
        for celda in a.matriz.values():
            assert celda.estado in m.ESTADOS_DE_CELDA and celda.texto, a.id
    for c in m.COMPLEMENTOS.values():
        assert c.nombre and c.supuestos and c.demuestra and c.no_demuestra, c.id


def test_matriz_distingue_las_dos_vias_de_la_ausencia():
    m = _modulo()
    a = m.ALTERNATIVAS
    for id_ in ("A1", "A2"):
        assert a[id_].matriz["b_unico_y_completo"].estado == "no_demuestra"
        assert a[id_].matriz["c_via_1_omision_declarada"].estado == "no_demuestra"
    assert a["A3"].matriz["c_via_1_omision_declarada"].estado == "parcial"
    for id_ in ("A4", "A5"):
        assert a[id_].matriz["b_unico_y_completo"].estado == "condicionado"
        assert a[id_].matriz["c_via_1_omision_declarada"].estado == "condicionado"
    for alternativa in a.values():
        assert alternativa.matriz["c_via_2_ausencia_inferida"].estado == "pendiente", alternativa.id
        assert all(c.estado != "demuestra_bajo_supuestos" for k, c in alternativa.matriz.items()
                   if k.startswith(("b_", "c_"))), alternativa.id


def test_fuentes_primarias_y_su_verificacion():
    m = _modulo()
    f = m.FUENTES_PRIMARIAS
    assert set(f) == {"rfc_3161", "rfc_9162", "opentimestamps_autores"}
    for id_ in ("rfc_3161", "rfc_9162"):
        assert f[id_].estado == "pendiente_de_verificacion_primaria" and f[id_].verificado == (), id_
        assert f[id_].atribuido_pendiente, id_
    ots = f["opentimestamps_autores"]
    assert ots.estado == "verificada_en_documentacion_de_los_autores"
    assert any("few hours" in cita for cita in ots.verificado)
    assert any("precision" in p for p in ots.atribuido_pendiente)
    for a in m.ALTERNATIVAS.values():
        assert set(a.fuentes) <= set(f), a.id


def test_lo_que_ninguna_demuestra_y_reglas_pendientes():
    m = _modulo()
    assert {"fuga_anticipada_de_y_t", "integridad_del_sorteo", "validez_inferencial"} <= set(m.NO_DEMUESTRA_NINGUNA)
    assert tuple(m.CONDICIONES_PENDIENTES_DEL_PROTOCOLO) == (
        "identidad_autorizada", "canal_canonico_exclusivo", "clave_unica_por_objetivo", "regla_de_duplicados",
        "recepcion_antes_del_plazo", "revision_completa")
    for pregunta in ("definicion_del_plazo", "reloj_de_recepcion", "margen_de_incorporacion",
                     "procedimiento_de_revision_completa"):
        assert pregunta in m.PREGUNTAS_ABIERTAS, pregunta
    assert "no demuestra anterioridad ni ausencia de fuga" in m.COMPLEMENTOS["R"].no_demuestra


def test_recomendacion_condicional_limitada_a_la_via_1():
    m = _modulo()
    r = m.RECOMENDACION_CONDICIONAL
    assert r["estado"] == "recomendacion_condicional_para_decision_del_operador"
    assert r["combinacion"] == ("A4", "C", "M", "K")
    assert "solo por la via 1" in r["texto"] and "via 2 sigue pendiente" in r["texto"]
    assert "unica" not in r["texto"]
    (sellado,) = [d for d in pi.DECISIONES_REQUERIDAS if d.id == "mecanismo_de_sellado_temporal_externo"]
    assert sellado.valor is None and sellado.estado == "sin_decidir"
    assert "mecanismo_de_sellado_temporal_externo" in rp.PENDIENTES_BORRADOR_AE52
    assert ESPECIFICACION_CANDIDATA_AE53["pendientes"]["mecanismo_de_sellado_temporal_externo"]["valor"] is None


def test_vocabulario_de_resultados_exacto_y_sin_acreditacion():
    m = _modulo()
    assert m.RESULTADOS_OMISION_DECLARADA == ("omision_declarada_sujeta_a_reglas_pendientes", "conflicto_de_clave",
                                              "declaracion_recibida_despues_del_plazo", "sin_declaracion")
    assert m.RESULTADOS_AUSENCIA_INFERIDA == ("entrada_recibida_antes_del_plazo",
                                              "vista_no_concluyente_anterior_a_plazo_mas_margen",
                                              "ausencia_inferida_pendiente_de_reloj_margen_y_revision",
                                              "ausencia_inferida_pendiente_sin_margen")
    assert not set(m.RESULTADOS_OMISION_DECLARADA) & set(m.RESULTADOS_AUSENCIA_INFERIDA)
    for resultado in (*m.RESULTADOS_OMISION_DECLARADA, *m.RESULTADOS_AUSENCIA_INFERIDA):
        assert "acreditad" not in resultado and resultado != "ausencia", resultado


# ---------------------------------------------------------------------------
# B1-B3: sellos, unicidad y consistencia
# ---------------------------------------------------------------------------

def _ramas_bifurcadas():
    prefijo = _Registro()
    prefijo.predecir(2714, FIJA)
    prefijo.resultado(2714)
    con, sin = _Registro(prefijo.entradas), _Registro(prefijo.entradas)
    con.predecir(2715, FIJA)
    return con, sin


def test_b1_sello_aislado_no_acredita_unicidad():
    """Refuta: 'un sello anterior al plazo acredita unicidad'. Supuesto:
    el sello se modela como HMAC de prueba sobre (hash, instante)."""
    m = _modulo()
    con, sin = _ramas_bifurcadas()
    antes = PLAZO - timedelta(hours=1)
    sellos = [m.sellar_sintetico(r.estado.cabeza, antes, CLAVE_PRUEBA) for r in (con, sin)]
    validos = m.sellos_antes_del_plazo(sellos, PLAZO, CLAVE_PRUEBA)
    assert len(validos) == 2
    for rama in (con, sin):
        assert any(s.hash in rp.validar_registro(rama.entradas).hashes for s in validos)
    assert not m.es_prefijo(tuple(con.entradas), tuple(sin.entradas)) or len(con.entradas) != len(sin.entradas)
    falso = dataclasses.replace(sellos[0], instante=antes - timedelta(days=1))
    assert m.sellos_antes_del_plazo([falso], PLAZO, CLAVE_PRUEBA) == ()


def test_b2a_duplicados_en_una_bitacora_consistente():
    """Refuta: 'la consistencia de la bitacora acredita la unicidad de las
    predicciones'. Supuesto: bitacora como lista; consistencia como prefijo."""
    m = _modulo()
    antes = PLAZO - timedelta(hours=2)
    bitacora = (_entrada(m, 2714, "prediccion", antes, antes, "x"),
                _entrada(m, 2715, "prediccion", antes, antes, "salida-1"),
                _entrada(m, 2715, "prediccion", antes, antes + timedelta(minutes=1), "salida-2"))
    testigo_1, testigo_2 = bitacora, bitacora
    assert m.vistas_consistentes(testigo_1, testigo_2)
    assert m.vistas_consistentes(bitacora[:2], bitacora)


def test_b2b_clave_unica_detecta_la_duplicacion_sin_elegir_regla():
    """Refuta: que el caso pase inadvertido si el protocolo exige clave unica
    y revision completa. La regla de aceptacion no se elige."""
    m = _modulo()
    antes = PLAZO - timedelta(hours=2)
    bitacora = (_entrada(m, 2715, "prediccion", antes, antes, "salida-1"),
                _entrada(m, 2715, "prediccion", antes, antes, "salida-2"),
                _entrada(m, 2716, "prediccion", antes, antes, "salida-3"))
    assert m.claves_duplicadas(bitacora) == (("p" * 64, "BALOTO", 2715),)
    assert "regla_de_duplicados" in m.CONDICIONES_PENDIENTES_DEL_PROTOCOLO
    assert not hasattr(m, "aplicar_regla_de_duplicados")


def test_b2c_rama_sellada_fuera_del_canal_no_aparece_en_la_bitacora():
    """Refuta: 'cualquier sello anterior al plazo cuenta'. Supuesto: el canal
    canonico exclusivo es una regla pendiente."""
    m = _modulo()
    con, sin = _ramas_bifurcadas()
    antes = PLAZO - timedelta(hours=1)
    fuera = m.sellar_sintetico(con.estado.cabeza, antes, CLAVE_PRUEBA)  # sello privado valido
    assert m.sellos_antes_del_plazo([fuera], PLAZO, CLAVE_PRUEBA) == (fuera,)
    bitacora = (_entrada(m, 2714, "prediccion", antes, antes, sin.estado.cabeza),)
    assert all(e.contenido_hash != hashlib.sha256(con.estado.cabeza.encode()).hexdigest() for e in bitacora)
    assert "canal_canonico_exclusivo" in m.CONDICIONES_PENDIENTES_DEL_PROTOCOLO


def test_b3_vista_dividida_solo_se_detecta_comparando_testigos():
    """Refuta: 'un punto de control firmado basta sin comparacion entre
    testigos'. Supuesto: al menos un testigo honesto que compara."""
    m = _modulo()
    antes = PLAZO - timedelta(hours=2)
    comun = (_entrada(m, 2714, "prediccion", antes, antes, "x"),)
    vista_1 = comun + (_entrada(m, 2715, "prediccion", antes, antes, "salida-1"),)
    vista_2 = comun + (_entrada(m, 2715, "omision_declarada", antes, antes, "omision"),)
    assert m.claves_duplicadas(vista_1) == () and m.claves_duplicadas(vista_2) == ()
    assert not m.vistas_consistentes(vista_1, vista_2)
    assert m.vistas_consistentes(comun, vista_1) and m.vistas_consistentes(comun, vista_2)


# ---------------------------------------------------------------------------
# B4: omision declarada (via 1) frente a ausencia inferida (via 2)
# ---------------------------------------------------------------------------

def test_b4a_recibida_antes_incluida_despues_vista_del_plazo_no_concluyente():
    """Refuta: 'un punto de control en el plazo prueba la ausencia'.
    Supuestos: reloj de recepcion de la bitacora y margen, pendientes."""
    m = _modulo()
    entrada = _entrada(m, 2715, "prediccion", PLAZO - timedelta(minutes=1), PLAZO + timedelta(minutes=10))
    bitacora = (entrada,)
    vista = m.vista_publicada_en(bitacora, PLAZO)
    assert vista == ()
    clave = entrada.clave
    assert m.evaluar_ausencia_inferida(vista, clave, PLAZO, MARGEN, PLAZO, reloj_de_recepcion="reloj_de_la_bitacora") \
        == "vista_no_concluyente_anterior_a_plazo_mas_margen"


def test_b4b_vista_tras_plazo_mas_margen_contiene_la_entrada():
    """Muestra la dependencia del margen. Supuesto: la bitacora respeta el
    margen y declara bien la recepcion."""
    m = _modulo()
    entrada = _entrada(m, 2715, "prediccion", PLAZO - timedelta(minutes=1), PLAZO + timedelta(minutes=10))
    publicada = PLAZO + MARGEN
    vista = m.vista_publicada_en((entrada,), publicada)
    assert vista == (entrada,)
    assert m.evaluar_ausencia_inferida(vista, entrada.clave, PLAZO, MARGEN, publicada,
                                       reloj_de_recepcion="reloj_de_la_bitacora") == "entrada_recibida_antes_del_plazo"


def test_b4c_vista_sin_la_clave_deja_la_ausencia_pendiente():
    """Refuta: 'la ausencia se infiere automaticamente de una vista sin
    entrada'."""
    m = _modulo()
    otra = _entrada(m, 2716, "prediccion", PLAZO - timedelta(hours=1), PLAZO - timedelta(hours=1))
    publicada = PLAZO + MARGEN + timedelta(minutes=5)
    vista = m.vista_publicada_en((otra,), publicada)
    resultado = m.evaluar_ausencia_inferida(vista, ("p" * 64, "BALOTO", 2715), PLAZO, MARGEN, publicada,
                                            reloj_de_recepcion="reloj_de_la_bitacora")
    assert resultado == "ausencia_inferida_pendiente_de_reloj_margen_y_revision"


def test_b4d_sin_margen_ni_reloj_la_ausencia_queda_pendiente():
    m = _modulo()
    clave = ("p" * 64, "BALOTO", 2715)
    publicada = PLAZO + timedelta(days=1)
    assert m.evaluar_ausencia_inferida((), clave, PLAZO, None, publicada, reloj_de_recepcion="reloj_de_la_bitacora") \
        == "ausencia_inferida_pendiente_sin_margen"
    assert m.evaluar_ausencia_inferida((), clave, PLAZO, MARGEN, publicada, reloj_de_recepcion=None) \
        == "ausencia_inferida_pendiente_sin_margen"


def test_b4e_omision_declarada_sujeta_a_reglas_pendientes():
    """Refuta: 'una declaracion de omision basta por si sola, sin reglas'."""
    m = _modulo()
    antes, despues = PLAZO - timedelta(hours=1), PLAZO + timedelta(minutes=5)
    clave = ("p" * 64, "BALOTO", 2715)
    declarada = _entrada(m, 2715, "omision_declarada", antes, antes, "omision")
    assert m.evaluar_omision_declarada((declarada,), clave, PLAZO) == "omision_declarada_sujeta_a_reglas_pendientes"
    prediccion = _entrada(m, 2715, "prediccion", antes, antes, "salida")
    assert m.evaluar_omision_declarada((declarada, prediccion), clave, PLAZO) == "conflicto_de_clave"
    tarde = _entrada(m, 2715, "omision_declarada", despues, despues, "omision")
    assert m.evaluar_omision_declarada((tarde,), clave, PLAZO) == "declaracion_recibida_despues_del_plazo"
    assert m.evaluar_omision_declarada((prediccion,), clave, PLAZO) == "sin_declaracion"
    assert m.evaluar_omision_declarada((), clave, PLAZO) == "sin_declaracion"


# ---------------------------------------------------------------------------
# B5-B7: fuga, recomputacion y zona horaria
# ---------------------------------------------------------------------------

def test_b5_fuga_anticipada_pasa_las_comprobaciones_temporales():
    """Refuta: 'la evidencia temporal excluye la fuga'. Supuesto: la
    uniformidad condicional es solo una hipotesis (AE-65)."""
    m = _modulo()
    y = _sorteo(2715)  # filtrado antes del plazo
    registro = _Registro()
    registro.predecir(2714, FIJA)
    registro.resultado(2714)
    registro.predecir(2715, _oraculo(y))
    antes = PLAZO - timedelta(hours=1)
    sello = m.sellar_sintetico(registro.estado.cabeza, antes, CLAVE_PRUEBA)
    assert m.sellos_antes_del_plazo([sello], PLAZO, CLAVE_PRUEBA) == (sello,)
    bitacora = (_entrada(m, 2715, "prediccion", antes, antes, registro.estado.cabeza),)
    assert m.claves_duplicadas(bitacora) == ()
    assert _diferencia_brier(_oraculo(y), y) > 0.09
    assert "fuga_anticipada_de_y_t" in m.NO_DEMUESTRA_NINGUNA


def _estrategia_sintetica(artefactos):
    """Funcion determinista de los artefactos declarados."""
    auxiliar = artefactos["estado_auxiliar"]
    if "pista" in auxiliar:
        return _oraculo(auxiliar["pista"])
    return FIJA


def test_b6a_recomputacion_conforme_con_artefactos_fijados():
    m = _modulo()
    artefactos = {"entrada": "huella", "estado_auxiliar": {}, "semilla": 1}
    assert m.recomputar(_estrategia_sintetica, artefactos) == FIJA
    assert m.recomputacion_conforme(_estrategia_sintetica, artefactos, FIJA)
    assert not m.recomputacion_conforme(_estrategia_sintetica, artefactos, _oraculo(_sorteo(2715)))


def test_b6b_estado_auxiliar_con_informacion_futura():
    """Refuta: 'recomputacion conforme implica ausencia de fuga' y 'sellar el
    codigo excluye la dependencia de y_t'. Supuesto: el estado auxiliar es
    parte de los artefactos declarados."""
    m = _modulo()
    y = _sorteo(2715)
    artefactos = {"entrada": "huella", "estado_auxiliar": {"pista": y}, "semilla": 1}
    registrada = _oraculo(y)
    assert m.recomputacion_conforme(_estrategia_sintetica, artefactos, registrada)
    assert _diferencia_brier(registrada, y) > 0.09
    assert "estado_auxiliar" in m.COMPLEMENTOS["R"].supuestos[0]


def test_b7_instantes_sin_zona_se_rechazan():
    """Refuta: 'comparar horas sin zona es seguro'. Supuesto: UTC-5 fijo."""
    m = _modulo()
    sorteo_utc = datetime(2021, 9, 30, 2, 0, tzinfo=timezone.utc)  # 21:00 en Bogota
    sello_local_ingenuo = datetime(2021, 9, 29, 22, 0)  # 22:00 en Bogota, una hora despues
    assert sello_local_ingenuo < sorteo_utc.replace(tzinfo=None)  # la comparacion ingenua parece anterior
    assert sello_local_ingenuo.replace(tzinfo=BOGOTA) > sorteo_utc  # en realidad es posterior
    with pytest.raises(ValueError):
        m.sellar_sintetico("h" * 64, sello_local_ingenuo, CLAVE_PRUEBA)
    sello = m.sellar_sintetico("h" * 64, sello_local_ingenuo.replace(tzinfo=BOGOTA), CLAVE_PRUEBA)
    assert m.sellos_antes_del_plazo([sello], sorteo_utc, CLAVE_PRUEBA) == ()
    with pytest.raises(ValueError):
        m.sellos_antes_del_plazo([sello], sorteo_utc.replace(tzinfo=None), CLAVE_PRUEBA)
    with pytest.raises(ValueError):
        m.evaluar_omision_declarada((), ("p" * 64, "BALOTO", 2715), PLAZO.replace(tzinfo=None))


# ---------------------------------------------------------------------------
# Pureza, estados, vocabulario e invariante
# ---------------------------------------------------------------------------

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


def test_estados_sin_cambios():
    _modulo()
    condiciones = {c.id: c.estado for c in tc.CONDICIONES_DE_TRASLADO}
    for id_ in ("F1_anterioridad", "F2_correspondencia_de_la_filtracion", "O3_tratamiento_de_omisiones",
                "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert condiciones[id_] == "pendiente", id_
    for id_ in ("F2_correspondencia_de_la_filtracion", "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert vp.ESTADOS_TRAS_AE64[id_]["estado"] == "pendiente", id_
    for o in ao.OBLIGACIONES_AE65.values():
        assert o.estado == "pendiente" and o.nivel == "posibilidad_estructural", o.id


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def test_textos_sin_aprobacion_ni_autorizacion():
    m = _modulo()
    textos = [*m.NO_DEMUESTRA_NINGUNA.values(), *m.CONDICIONES_PENDIENTES_DEL_PROTOCOLO.values(),
              *m.PREGUNTAS_ABIERTAS.values(), m.RECOMENDACION_CONDICIONAL["texto"]]
    for a in m.ALTERNATIVAS.values():
        textos += [a.nombre, a.instante, a.precision, a.latencia, a.costo, *a.supuestos, *a.pruebas_verificables,
                   *a.fallos_posibles, *(c.texto for c in a.matriz.values())]
    for c in m.COMPLEMENTOS.values():
        textos += [c.nombre, *c.supuestos, c.demuestra, c.no_demuestra]
    for f in m.FUENTES_PRIMARIAS.values():
        textos += [f.referencia, f.acceso, *f.verificado, *f.atribuido_pendiente]
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
