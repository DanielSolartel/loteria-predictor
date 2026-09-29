"""Tests de la Etapa AE-65, validada: auditoria de las obligaciones de
aplicacion F1 (anterioridad), F2 (correspondencia de la filtracion) y O3
(tratamiento de omisiones) que AE-64 dejo pendientes.

Separan lo que el codigo garantiza hoy (posibilidad estructural) de la
anterioridad acreditada, que exige evidencia externa. Los contraejemplos
sinteticos muestran que una cadena valida no acredita la anterioridad, que
la huella de la entrada no acredita la dependencia funcional de la salida,
que una cabeza sellada sin unicidad y completitud acreditadas no resuelve
O3 y que el resultado de Brier exige uniformidad condicional, no solo
marginal. F1, F2, O3, N2 y U1 siguen pendientes.

El modulo nuevo se importa dentro de cada prueba para que, sobre la base,
cada regresion falle por separado. Todo sintetico: sin datos reales,
PostgreSQL, entrenamiento ni predicciones reales."""
from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import math
import re
from collections.abc import Mapping
from fractions import Fraction
from math import comb

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import registro_prospectivo as rp
from app.application.ml import semantica_omisiones_prospectivas as so
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml import verificacion_primaria_choe_ramdas as vp
from app.application.ml.especificacion_evaluacion_prospectiva import (
    ESPECIFICACION_CANDIDATA_AE53,
    metricas_por_sorteo,
    validar_secuencia_objetivos,
)
from tests.unit.simulaciones import sinteticos

CORTE = 2713
FIJA = tuple(0.9 if n <= 5 else 0.1 for n in range(1, 44))
"""Salida sintetica fijada sin conocer el sorteo: 0,9 en 1..5 y 0,1 en el resto."""


def _modulo():
    return importlib.import_module("app.application.ml.auditoria_obligaciones_de_aplicacion")


def _historico(hasta):
    return sinteticos.historico(2081, hasta)


def _sorteo(numero):
    return tuple(_historico(numero)[-1].numeros)


def _oraculo(numeros):
    """Salida de un oraculo que observa y_t antes de producirla."""
    return tuple(0.9 if n in numeros else 0.1 for n in range(1, 44))


def _protocolo():
    estrategia = {
        "nombre": "estrategia_sintetica_ae65", "descripcion": "estrategia sintetica solo para pruebas",
        "huella_codigo": "b" * 64, "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
        "entorno": {"python": "3.x"},
    }
    return rp.construir_protocolo(protocolo_id="ae65-sintetico", estrategia=estrategia, cortes={"BALOTO": CORTE},
                                  pendientes=[], sintetico=True)


class _Registro:
    """Registro en memoria: lista de bytes canonicos de cada entrada."""

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


def _diferencia_brier(probabilidades, numeros):
    return metricas_por_sorteo("BALOTO", CORTE + 1, list(probabilidades), list(numeros)).diferencias["brier_score"]


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
# Registro de obligaciones
# ---------------------------------------------------------------------------

def test_obligaciones_con_cuatro_apartados_y_pendientes():
    m = _modulo()
    assert set(m.OBLIGACIONES_AE65) == {"F1_anterioridad", "F2_correspondencia_de_la_filtracion",
                                        "O3_tratamiento_de_omisiones"}
    condiciones = {c.id for c in tc.CONDICIONES_DE_TRASLADO}
    for id_, o in m.OBLIGACIONES_AE65.items():
        assert o.id == id_ and id_ in condiciones
        assert o.garantiza_hoy and o.depende_de_evidencia_externa and o.decisiones_abiertas and o.contraejemplos, id_
        assert o.estado == "pendiente", id_
        assert o.nivel == "posibilidad_estructural", id_
    assert m.NIVELES_DE_ANTERIORIDAD == ("posibilidad_estructural", "acreditada_con_evidencia_externa")
    assert {c.id for c in m.OBLIGACIONES_AE65["F1_anterioridad"].contraejemplos} == {
        "F1a_registro_retroactivo_indistinguible", "F1b_oraculo_retroactivo_valida", "F1c_bifurcacion_de_salidas"}
    assert {c.id for c in m.OBLIGACIONES_AE65["F2_correspondencia_de_la_filtracion"].contraejemplos} == {
        "F2a_misma_huella_salida_dependiente_de_y", "F2b_brier_predecible_frente_a_oraculo",
        "F2c_uniformidad_solo_marginal"}
    assert {c.id for c in m.OBLIGACIONES_AE65["O3_tratamiento_de_omisiones"].contraejemplos} == {
        "O3a_momento_de_la_omision_indistinguible", "O3b_bifurcacion_con_cabezas_selladas",
        "O3c_resultados_retenidos_y_omisiones_finales"}
    for o in m.OBLIGACIONES_AE65.values():
        for c in o.contraejemplos:
            assert c.descripcion and c.conclusion_indebida, c.id


def test_simbolos_citados_existen():
    m = _modulo()
    for o in m.OBLIGACIONES_AE65.values():
        for garantia in o.garantiza_hoy:
            assert garantia.texto and garantia.simbolos, o.id
            for referencia in garantia.simbolos:
                modulo, simbolo = referencia.split(":")
                assert hasattr(importlib.import_module(f"app.application.ml.{modulo}"), simbolo), referencia


def _decision_sin_valor(fuente, clave):
    if fuente == "propuesta_inferencia_prospectiva:DECISIONES_REQUERIDAS":
        (decision,) = [d for d in pi.DECISIONES_REQUERIDAS if d.id == clave]
        return decision.valor is None and decision.estado == "sin_decidir"
    if fuente == "propuesta_inferencia_prospectiva:DECISIONES_INFERENCIALES_ABIERTAS":
        decision = pi.DECISIONES_INFERENCIALES_ABIERTAS[clave]
        return decision.valor is None and decision.estado == "sin_decidir"
    if fuente == "especificacion_evaluacion_prospectiva:ESPECIFICACION_CANDIDATA_AE53":
        return ESPECIFICACION_CANDIDATA_AE53["pendientes"][clave]["valor"] is None
    if fuente == "registro_prospectivo:PENDIENTES_BORRADOR_AE52":
        return clave in rp.PENDIENTES_BORRADOR_AE52
    if fuente == "semantica_omisiones_prospectivas:_SIN_DECIDIR":
        return clave in so._SIN_DECIDIR
    raise AssertionError(f"fuente desconocida: {fuente}")


def test_decisiones_abiertas_existen_y_siguen_sin_valor():
    m = _modulo()
    for o in m.OBLIGACIONES_AE65.values():
        for fuente, clave in o.decisiones_abiertas:
            assert _decision_sin_valor(fuente, clave), (o.id, fuente, clave)
    claves = {id_: {c for _, c in o.decisiones_abiertas} for id_, o in m.OBLIGACIONES_AE65.items()}
    assert "mecanismo_de_sellado_temporal_externo" in claves["F1_anterioridad"]
    assert "aprobacion_de_la_estrategia_a_congelar" in claves["F2_correspondencia_de_la_filtracion"]
    assert {"tratamiento_de_omisiones", "tiempos_supervision", "ampliar_equivale_a_sustituir",
            "serie_consecutiva_posterior_al_corte"} <= claves["O3_tratamiento_de_omisiones"]


def test_evidencia_de_o3_exige_mas_que_la_anterioridad():
    m = _modulo()
    assert tuple(m.EVIDENCIA_REQUERIDA_O3) == (
        "cabeza_sellada_antes_del_plazo", "unicidad_y_completitud_de_la_cabeza", "calendario_oficial",
        "ausencia_de_prediccion_valida_al_plazo")
    assert "completo y unico" in m.EVIDENCIA_REQUERIDA_O3["unicidad_y_completitud_de_la_cabeza"]
    o3 = m.OBLIGACIONES_AE65["O3_tratamiento_de_omisiones"]
    assert set(m.EVIDENCIA_REQUERIDA_O3) <= set(o3.depende_de_evidencia_externa)
    assert "unicidad_y_completitud_de_la_cabeza" in m.OBLIGACIONES_AE65["F1_anterioridad"].depende_de_evidencia_externa


# ---------------------------------------------------------------------------
# Dependencias separadas por aspecto, via y uso
# ---------------------------------------------------------------------------

def test_aspectos_de_predictibilidad_separados_por_via_y_uso():
    m = _modulo()
    assert m.USOS == ("cs_via_teorema_1", "cs_via_teorema_2", "e_proceso_teorema_3", "subsucesion_por_omisiones")
    a = m.ASPECTOS_DE_PREDICTIBILIDAD
    assert set(a) == {"anterioridad_temporal", "dependencia_funcional_de_la_salida", "gamma_predecible",
                      "xi_predecible"}
    assert set(a["anterioridad_temporal"].aplica_a) == set(m.USOS)
    assert set(a["dependencia_funcional_de_la_salida"].aplica_a) == set(m.USOS)
    assert set(a["gamma_predecible"].aplica_a) == {"cs_via_teorema_2", "e_proceso_teorema_3"}
    assert set(a["xi_predecible"].aplica_a) == {"subsucesion_por_omisiones"}
    # F2 (correspondencia de p_t con G) no incluye gamma ni xi.
    assert set(m.COMPONENTES_DE_F2) == {"anterioridad_temporal", "dependencia_funcional_de_la_salida"}


def test_identificadores_citados_existen_en_su_catalogo():
    m = _modulo()
    condiciones = {c.id for c in tc.CONDICIONES_DE_TRASLADO}
    hipotesis = {h.id for p in vp.LECTURA_POR_PUNTO for h in p.hipotesis}
    for aspecto in m.ASPECTOS_DE_PREDICTIBILIDAD.values():
        assert aspecto.que_exige and aspecto.referencias, aspecto.id
        for catalogo, id_ in aspecto.referencias:
            if catalogo == "CONDICIONES_DE_TRASLADO":
                assert id_ in condiciones, id_
            elif catalogo == "LECTURA_POR_PUNTO":
                assert id_ in hipotesis, id_
            elif catalogo == "ESTADOS_TRAS_AE64":
                assert id_ in vp.ESTADOS_TRAS_AE64, id_
            else:
                raise AssertionError(catalogo)
    assert ("LECTURA_POR_PUNTO", "P1_gamma_predecible") in m.ASPECTOS_DE_PREDICTIBILIDAD["gamma_predecible"].referencias
    assert ("LECTURA_POR_PUNTO", "P4_omisiones_predecibles") in m.ASPECTOS_DE_PREDICTIBILIDAD["xi_predecible"].referencias


def test_dependencia_o3_comun_de_ae64_documentada_sin_reescribirla():
    m = _modulo()
    for via in ("cobertura_via_teorema_1", "cobertura_via_teorema_2"):
        assert "O3_tratamiento_de_omisiones" in vp.DEPENDENCIAS_DE_N2[via]
    assert "P1_gamma_predecible" in vp.DEPENDENCIAS_DE_N2["cobertura_via_teorema_2"]
    assert "P1_gamma_predecible" not in vp.DEPENDENCIAS_DE_N2["cobertura_via_teorema_1"]
    (f2,) = [d for d in vp._DEPENDENCIAS_TRAS_AE64 if d[0] == "F2_correspondencia_de_la_filtracion"]
    assert f2[1] == ("P4_anterioridad_de_p_t",)
    texto = m.OBSERVACION_DEPENDENCIA_O3_COMUN
    assert "DEPENDENCIAS_DE_N2" in texto and "no se modifica" in texto and "xi" in texto


# ---------------------------------------------------------------------------
# F1: anterioridad temporal
# ---------------------------------------------------------------------------

def _registro_con_fija(objetivos):
    registro = _Registro()
    for objetivo in objetivos:
        registro.predecir(objetivo, FIJA)
        registro.resultado(objetivo)
    return registro


def test_f1a_registro_honesto_y_retroactivo_son_identicos():
    _modulo()
    honesto = _registro_con_fija((2714, 2715, 2716))  # cada prediccion antes de su resultado
    conocidos = {t: _sorteo(t) for t in (2714, 2715, 2716)}  # todo se conoce antes de construir
    retroactivo = _Registro()
    for objetivo in sorted(conocidos):
        retroactivo.predecir(objetivo, FIJA)
        retroactivo.resultado(objetivo)
    assert honesto.entradas == retroactivo.entradas
    assert rp.resumir_registro(honesto.estado) == rp.resumir_registro(retroactivo.estado)
    claves = {k for e in honesto.entradas for k in json.loads(e)}
    assert not claves & {"fecha", "hora", "timestamp", "registrado_en", "sello"}


def test_f1b_oraculo_retroactivo_valida_y_no_cambia_el_resumen():
    _modulo()
    registro = _Registro()
    for objetivo in (2714, 2715, 2716):
        registro.predecir(objetivo, _oraculo(_sorteo(objetivo)))  # fabricada tras conocer el resultado
        registro.resultado(objetivo)
    resumen = rp.resumir_registro(registro.estado)
    assert resumen["evaluacion"]["evaluable"] is False
    assert "sellado_temporal_externo_no_verificado" in resumen["evaluacion"]["motivos"]
    for objetivo in (2714, 2715, 2716):
        assert _diferencia_brier(_oraculo(_sorteo(objetivo)), _sorteo(objetivo)) > 0.09


def _cabeza_sellada_en_el_registro(entradas, sellos):
    return any(h in sellos for h in rp.validar_registro(entradas).hashes)


def test_f1c_bifurcacion_de_salidas_selladas_antes_del_sorteo():
    _modulo()
    prefijo = _registro_con_fija((2714,)).entradas
    rama_a, rama_b = _Registro(prefijo), _Registro(prefijo)
    rama_a.predecir(2715, FIJA)
    rama_b.predecir(2715, tuple(reversed(FIJA)))
    sellos = {rama_a.estado.cabeza, rama_b.estado.cabeza}  # ambas selladas antes del sorteo 2715
    rama_a.resultado(2715)
    rama_b.resultado(2715)
    y = _sorteo(2715)
    revelada = max((rama_a, rama_b), key=lambda r: _diferencia_brier(
        json.loads(r.entradas[-2])["salida"]["probabilidades"], y))  # eleccion tras ver y_2715
    for rama in (rama_a, rama_b):
        assert _cabeza_sellada_en_el_registro(rama.entradas, sellos)
        rp.validar_registro(rama.entradas)
    assert revelada in (rama_a, rama_b) and rama_a.entradas != rama_b.entradas


# ---------------------------------------------------------------------------
# F2: dependencia funcional de la salida
# ---------------------------------------------------------------------------

def test_f2a_misma_huella_de_entrada_con_salida_dependiente_de_y():
    _modulo()
    salidas = {}
    for y in ((1, 2, 3, 4, 5), (39, 40, 41, 42, 43)):
        registro = _Registro()
        registro.predecir(2714, _oraculo(y))
        rp.validar_registro(registro.entradas)
        salidas[y] = json.loads(registro.entradas[-1])
    a, b = salidas.values()
    assert a["entrada"] == b["entrada"]
    assert a["salida"] != b["salida"]


def test_f2b_brier_bajo_uniformidad_condicional_frente_al_oraculo():
    m = _modulo()
    assert "condicionalmente" in m.HIPOTESIS_UNIFORMIDAD_CONDICIONAL
    q = Fraction(comb(42, 4), comb(43, 5))  # P(i en y_t | G_(t-1)) bajo uniformidad condicional
    assert q == Fraction(5, 43)
    fija = [Fraction(9, 10) if n <= 5 else Fraction(1, 10) for n in range(1, 44)]
    esperada = m.esperanza_diferencia_brier_bajo_uniformidad_condicional(fija)
    assert esperada == -sum((p - q) ** 2 for p in fija) / 43
    assert esperada < Fraction(-1, 100)
    uniforme = [q] * 43
    assert m.esperanza_diferencia_brier_bajo_uniformidad_condicional(uniforme) == 0
    # Coherencia con metricas_por_sorteo: Brier = media de (p_i - y_i)^2 en cualquier sorteo.
    b_u = q * (1 - q)
    for y in (_sorteo(2714), _sorteo(2715), (1, 2, 3, 4, 5)):
        esperado = float(b_u) - sum((float(p) - (1 if n in y else 0)) ** 2 for n, p in zip(range(1, 44), fija)) / 43
        assert math.isclose(_diferencia_brier([float(p) for p in fija], y), esperado, rel_tol=1e-12, abs_tol=1e-15)
    # Oraculo que observa y_t: d = B_u - 0,01 > 0 en todo sorteo probado.
    for y in (_sorteo(2714), _sorteo(2715), _sorteo(2716), (1, 2, 3, 4, 5), (39, 40, 41, 42, 43)):
        assert math.isclose(_diferencia_brier(_oraculo(y), y), float(b_u) - 0.01, rel_tol=1e-12)
        assert _diferencia_brier(_oraculo(y), y) > 0.09


def test_f2c_uniformidad_solo_marginal_no_basta():
    m = _modulo()
    assert "marginal" in m.HIPOTESIS_UNIFORMIDAD_CONDICIONAL
    # y_t = sigma(y_(t-1)) con sigma(n) = n mod 43 + 1: biyeccion, asi que si y_1 es uniforme cada y_t lo es
    # marginalmente; pero y_t queda determinado por el pasado y un p fijado antes de y_t acierta siempre.
    sigma = {n: n % 43 + 1 for n in range(1, 44)}
    assert sorted(sigma.values()) == list(range(1, 44))
    for anterior in (_sorteo(2714), (1, 2, 3, 4, 5), (39, 40, 41, 42, 43)):
        siguiente = tuple(sorted(sigma[n] for n in anterior))
        p = _oraculo(siguiente)  # fijado con y_(t-1), antes de y_t: predecible
        assert _diferencia_brier(p, siguiente) > 0.09


# ---------------------------------------------------------------------------
# O3: tratamiento de omisiones
# ---------------------------------------------------------------------------

def _con_omision(decidir_tras_ver):
    registro = _registro_con_fija((2714,))
    omitir = _diferencia_brier(FIJA, _sorteo(2715)) < 0 if decidir_tras_ver else True
    assert omitir  # en esta serie sintetica ambas reglas omiten 2715
    registro.predecir(2716, FIJA)
    registro.resultado(2716)
    return registro


def test_o3a_momento_de_la_omision_indistinguible():
    _modulo()
    antes, despues = _con_omision(False), _con_omision(True)
    assert antes.entradas == despues.entradas
    informes = [validar_secuencia_objetivos(corte=CORTE, ultimo_sorteo_ocurrido=2716,
                                            objetivos_con_prediccion=[2714, 2716],
                                            objetivos_con_resultado=[2714, 2716]) for _ in range(2)]
    assert informes[0] == informes[1]
    assert informes[0].omisiones == (2715,) and informes[0].estado == "no_evaluable_por_omision"
    # Un registro retroactivo simplemente no tiene omisiones.
    sin_omision = validar_secuencia_objetivos(corte=CORTE, ultimo_sorteo_ocurrido=2716,
                                              objetivos_con_prediccion=[2714, 2715, 2716],
                                              objetivos_con_resultado=[2714, 2715, 2716])
    assert sin_omision.omisiones == () and sin_omision.estado == "incompleta"


def test_o3b_cabezas_selladas_sin_unicidad_no_resuelven_la_omision():
    _modulo()
    prefijo = _registro_con_fija((2714,)).entradas
    con_prediccion, sin_prediccion = _Registro(prefijo), _Registro(prefijo)
    con_prediccion.predecir(2715, FIJA)
    sellos = {con_prediccion.estado.cabeza, sin_prediccion.estado.cabeza}  # ambas antes del plazo de 2715
    con_prediccion.resultado(2715)
    sin_prediccion.predecir(2716, FIJA)
    for rama in (con_prediccion, sin_prediccion):
        rp.validar_registro(rama.entradas)
        assert _cabeza_sellada_en_el_registro(rama.entradas, sellos)
    objetivos = {id(r): sorted(o for _, o in r.estado.predicciones) for r in (con_prediccion, sin_prediccion)}
    assert objetivos[id(con_prediccion)] == [2714, 2715]
    assert objetivos[id(sin_prediccion)] == [2714, 2716]
    informe = validar_secuencia_objetivos(corte=CORTE, ultimo_sorteo_ocurrido=2716,
                                          objetivos_con_prediccion=objetivos[id(sin_prediccion)],
                                          objetivos_con_resultado=[2714])
    assert informe.omisiones == (2715,)


def test_o3c_resultados_retenidos_y_omisiones_finales():
    _modulo()
    predichos = list(range(CORTE + 1, CORTE + 101))
    retenidos = [o for o in predichos if o != CORTE + 50]
    informe = validar_secuencia_objetivos(corte=CORTE, ultimo_sorteo_ocurrido=CORTE + 100,
                                          objetivos_con_prediccion=predichos, objetivos_con_resultado=retenidos)
    assert informe.estado == "incompleta" and informe.resultado_pendiente == (CORTE + 50,)
    registro = _registro_con_fija((2714,))
    registro.predecir(2715, FIJA)
    (juego,) = rp.resumir_registro(registro.estado)["juegos"]
    assert juego["predicciones_sin_resultado"] == [2715]
    # Omisiones posteriores al ultimo objetivo registrado: el resumen no las lista; la secuencia si.
    solo = _registro_con_fija((2714,))
    (juego,) = rp.resumir_registro(solo.estado)["juegos"]
    assert juego["omisiones"] == []
    finales = validar_secuencia_objetivos(corte=CORTE, ultimo_sorteo_ocurrido=2716, objetivos_con_prediccion=[2714],
                                          objetivos_con_resultado=[2714])
    assert finales.omisiones == (2715, 2716)


# ---------------------------------------------------------------------------
# Estados, vocabulario e invariante
# ---------------------------------------------------------------------------

def test_estados_sin_cambios_en_cada_catalogo():
    m = _modulo()
    condiciones = {c.id: c.estado for c in tc.CONDICIONES_DE_TRASLADO}
    for id_ in ("F1_anterioridad", "F2_correspondencia_de_la_filtracion", "O3_tratamiento_de_omisiones",
                "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert condiciones[id_] == "pendiente", id_
    assert condiciones["O1_omision_predecible"] == "demostrada"
    assert condiciones["O2_omision_dependiente_del_resultado"] == "refutada"
    for id_ in ("F2_correspondencia_de_la_filtracion", "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert vp.ESTADOS_TRAS_AE64[id_]["estado"] == "pendiente", id_
    assert "F1_anterioridad" not in vp.ESTADOS_TRAS_AE64
    assert "O3_tratamiento_de_omisiones" not in vp.ESTADOS_TRAS_AE64
    assert vp.recalcular_estados() == {k: v["estado"] for k, v in vp.ESTADOS_TRAS_AE64.items()}
    assert all(o.nivel != "acreditada_con_evidencia_externa" for o in m.OBLIGACIONES_AE65.values())
    assert set(m.CONSECUENCIAS) == {"N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"}
    assert all(v == "pendiente" for v in m.CONSECUENCIAS.values())


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def test_textos_sin_aprobacion_ni_autorizacion():
    m = _modulo()
    textos = [m.HIPOTESIS_UNIFORMIDAD_CONDICIONAL, m.OBSERVACION_DEPENDENCIA_O3_COMUN,
              *m.EVIDENCIA_REQUERIDA_O3.values()]
    for o in m.OBLIGACIONES_AE65.values():
        textos += [g.texto for g in o.garantiza_hoy] + list(o.depende_de_evidencia_externa)
        textos += [t for c in o.contraejemplos for t in (c.descripcion, c.conclusion_indebida)]
    for a in m.ASPECTOS_DE_PREDICTIBILIDAD.values():
        textos.append(a.que_exige)
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


def test_estado_bloqueos_y_registros_intactos():
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    secuencia = {f.id: f for f in pi.FAMILIAS_INFERENCIALES}["secuencia_confianza_uniforme_martingala"]
    assert secuencia.uso_1_sobre_e_nula_terminal == secuencia.uso_1_sobre_e_supervision == "pendiente_de_demostracion"
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
