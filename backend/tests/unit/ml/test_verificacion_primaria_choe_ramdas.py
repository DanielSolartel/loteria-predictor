"""Tests de la Etapa AE-64, validada: verificacion primaria, en el PDF
de Choe y Ramdas arXiv:2110.00115v6, de los enunciados inferenciales que
AE-63 dejo pendientes.

Comprueban que el modulo separa tres clases: lo que afirma el articulo
(con pagina, teorema, ecuacion o seccion y comprobacion visual de las
formulas), las derivaciones propias y las condiciones cuya aplicacion a
este repositorio sigue sin verificarse. El articulo demuestra el
e-proceso solo para la nula debil en todo tiempo; la cota conjunta para la
nula terminal o sobre T es una derivacion propia condicionada a las
hipotesis de la supermartingala, y su aplicacion al repositorio sigue
pendiente.

El modulo nuevo se importa dentro de cada prueba para que, sobre la base,
cada regresion falle por separado. Todo sintetico: sin datos reales,
PostgreSQL, entrenamiento ni predicciones reales."""
from __future__ import annotations

import importlib
import json
import math
import re

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53, metricas_por_sorteo
from app.application.ml.metricas import EPSILON_CLIP, _recortar
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52

SORTEO = [10, 11, 12, 13, 14]
PAGINAS_VISUALES = {"1", "8", "9", "10", "11", "13", "14", "16", "17", "18", "26", "32", "33", "34", "47", "48", "50",
                    "51"}


def _modulo():
    return importlib.import_module("app.application.ml.verificacion_primaria_choe_ramdas")


def _probabilidades(p_en_sorteo, p_fuera, sorteo=SORTEO):
    return [p_en_sorteo if n in sorteo else p_fuera for n in range(1, 44)]


def _todas_las_hipotesis(m):
    return {h.id: h for punto in m.LECTURA_POR_PUNTO for h in punto.hipotesis}


def _todos_los_enunciados(m):
    return [e for punto in m.LECTURA_POR_PUNTO for e in punto.enunciados] + list(m.ENUNCIADOS_NULAS_Y_E_PROCESOS)


# ---------------------------------------------------------------------------
# Procedencia y separacion de clases
# ---------------------------------------------------------------------------

def test_procedencia_pdf_v6():
    m = _modulo()
    p = m.PROCEDENCIA_V6
    assert p["version"] == "arXiv:2110.00115v6"
    assert p["sello_en_el_pdf"] == "arXiv:2110.00115v6 [stat.ME] 9 Nov 2023"
    assert p["sha256_pdf"] == "fd87e23a30c6657fd8dd272f671d0bd8a3aa469f5aafbec85a00bb9501764286"
    assert p["bytes_pdf"] == 6089652 and p["paginas_pdf"] == 61
    assert p["via"] == "pdf_v6_aportado_por_el_operador_leido_por_claude"
    assert p["html_v6"] == "no_consultado_bloqueado"
    assert set(p["paginas_comprobadas_visualmente"]) == PAGINAS_VISUALES
    assert not any("html" in e.referencia.lower() for e in _todos_los_enunciados(m))


def test_enunciados_con_referencia_exacta_y_formulas_comprobadas_visualmente():
    m = _modulo()
    assert m.ESTADOS_ENUNCIADO == ("verificado_en_pdf_v6", "discrepancia_con_registro_previo", "no_encontrado_en_v6")
    enunciados = _todos_los_enunciados(m)
    assert len({e.id for e in enunciados}) == len(enunciados)
    for e in enunciados:
        assert e.estado in m.ESTADOS_ENUNCIADO, e.id
        assert e.clase == "el_articulo_afirma", e.id
        if e.estado == "verificado_en_pdf_v6":
            assert re.fullmatch(r"\d+(-\d+)?", e.pagina), e.id
            assert re.search(r"teorema|ecuacion|seccion|proposicion|corolario|nota|resumen", e.referencia), e.id
            assert e.parafrasis, e.id
        paginas = set(e.pagina.split("-"))
        assert e.comprobacion == "visual" and paginas <= PAGINAS_VISUALES, e.id


def test_tres_clases_separadas():
    m = _modulo()
    assert m.CLASES == ("el_articulo_afirma", "derivacion_propia", "aplicacion_al_repositorio")
    assert m.ESTADOS_HIPOTESIS == ("demostrada", "refutada", "pendiente")
    for h in _todas_las_hipotesis(m).values():
        assert h.clase in ("derivacion_propia", "aplicacion_al_repositorio"), h.id
        assert h.estado in m.ESTADOS_HIPOTESIS, h.id
        assert h.afirmacion and h.simbolos_del_repositorio, h.id
        if h.estado == "demostrada":
            assert h.clase == "derivacion_propia" or h.base, h.id
        if h.estado == "pendiente":
            assert h.exige, h.id
    for referencia in {s for h in _todas_las_hipotesis(m).values() for s in h.simbolos_del_repositorio}:
        modulo, simbolo = referencia.split(":")
        assert hasattr(importlib.import_module(f"app.application.ml.{modulo}"), simbolo), referencia


# ---------------------------------------------------------------------------
# Puntos 1 a 6
# ---------------------------------------------------------------------------

def test_punto_1_constante_c_del_teorema_2():
    m = _modulo()
    ll = tc.intervalo_diferencia_log_loss("BALOTO")
    brier = tc.intervalo_diferencia_brier("BALOTO")
    p5 = tc.intervalo_diferencia_precision_en_5()
    assert math.isclose(m.constante_c_teorema_2(ll), 2 * max(abs(ll.inferior), abs(ll.superior)), rel_tol=1e-15)
    assert math.isclose(m.constante_c_teorema_2(ll), 26.9121308208, rel_tol=1e-10)
    assert math.isclose(m.constante_c_teorema_2(brier), 1.794483504598, rel_tol=1e-10)
    assert m.constante_c_teorema_2(p5) == 2.0
    # Centrado por una constante conocida: c = ancho del intervalo (derivacion propia).
    assert math.isclose(m.constante_c_centrada(ll), math.log((1 - EPSILON_CLIP) / EPSILON_CLIP), rel_tol=1e-12)
    assert m.constante_c_centrada(brier) == 1.0 and m.constante_c_centrada(p5) == 2.0
    h = _todas_las_hipotesis(m)
    assert h["P1_acotacion_constante_en_el_repositorio"].estado == "demostrada"
    assert h["P1_gamma_predecible"].estado == "pendiente"
    enunciado = {e.id: e for e in m.LECTURA_POR_PUNTO[0].enunciados}["T2_hipotesis"]
    assert (enunciado.pagina, enunciado.referencia) == ("14", "teorema 2, ecuacion (15)")


def test_punto_2_constante_c_del_teorema_1_y_coherencia_con_k2():
    m = _modulo()
    ll = tc.intervalo_diferencia_log_loss("BALOTO")
    assert math.isclose(m.constante_c_teorema_1(ll), 13.4560654104, rel_tol=1e-10)
    assert m.constante_c_teorema_1(tc.intervalo_diferencia_precision_en_5()) == 1.0
    # K2 de AE-63: proxy w^2/4 = c^2 con c = w/2 tras centrar por una constante.
    w = tc.ancho(ll)
    assert math.isclose((m.constante_c_centrada(ll) / 2) ** 2, w ** 2 / 4, rel_tol=1e-15)
    enunciado = {e.id: e for e in m.LECTURA_POR_PUNTO[1].enunciados}["T1_hipotesis"]
    assert (enunciado.pagina, enunciado.referencia) == ("13", "teorema 1, ecuaciones (13)-(14)")
    assert _todas_las_hipotesis(m)["P2_subgaussiana_por_condicion_suficiente"].estado == "demostrada"


def test_punto_3_signo_frente_a_la_orientacion_positiva():
    m = _modulo()
    r = metricas_por_sorteo("BALOTO", 1, _probabilidades(0.3, 0.1), SORTEO)
    # Articulo: S positivamente orientada, delta = S(p, y) - S(q, y), p = estrategia, q = uniforme.
    delta_ll = (-r.estrategia.log_loss) - (-r.uniforme.log_loss)
    delta_brier = (1 - r.estrategia.brier_score) - (1 - r.uniforme.brier_score)
    delta_p5 = r.estrategia.precision_en_5 - r.uniforme.precision_en_5
    assert math.isclose(delta_ll, r.diferencias["log_loss"], rel_tol=1e-12)
    assert math.isclose(delta_brier, r.diferencias["brier_score"], rel_tol=1e-12)
    assert delta_p5 == -r.diferencias["precision_en_5"]
    h = _todas_las_hipotesis(m)
    assert h["P3_signo_log_loss_y_brier"].estado == h["P3_signo_precision_en_5"].estado == "demostrada"


def test_punto_4_filtracion_anterioridad_y_omisiones():
    m = _modulo()
    h = _todas_las_hipotesis(m)
    assert h["P4_uniforme_y_limites_predecibles"].estado == "demostrada"
    assert h["P4_anterioridad_de_p_t"].estado == "pendiente"
    assert "mecanismo_de_sellado_temporal_externo" in h["P4_anterioridad_de_p_t"].exige
    assert h["P4_omisiones_predecibles"].estado == "pendiente"
    assert "tratamiento_de_omisiones" in h["P4_omisiones_predecibles"].exige
    enunciados = {e.id: e for e in m.LECTURA_POR_PUNTO[3].enunciados}
    assert (enunciados["F1_subsucesiones_predecibles"].pagina,
            enunciados["F1_subsucesiones_predecibles"].referencia) == ("47-48", "seccion F.1, ecuaciones (96)-(102)")
    assert "Delta_t(xi)" in enunciados["F1_subsucesiones_predecibles"].parafrasis
    estados = {c.id: c.estado for c in tc.CONDICIONES_DE_TRASLADO}
    assert estados["F1_anterioridad"] == estados["O3_tratamiento_de_omisiones"] == "pendiente"


def _log_truncada_del_articulo(p, y, eps):
    """Formula de la p. 13: y log(p v eps) + (1 - y) log((1 - p) v eps)."""
    return y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps))


def _log_del_repositorio(p, y):
    """-Log Loss por fila del repositorio: recorte a [eps, 1 - eps]."""
    c = _recortar(p)
    return y * math.log(c) + (1 - y) * math.log(1 - c)


def test_punto_5_truncamiento_no_equivalente_y_propiedad():
    m = _modulo()
    eps = EPSILON_CLIP
    assert _log_truncada_del_articulo(1 - 1e-9, 1, eps) != _log_del_repositorio(1 - 1e-9, 1)
    assert _log_truncada_del_articulo(1e-9, 0, eps) != _log_del_repositorio(1e-9, 0)
    # La truncada del articulo es impropia: con q = eps/2, un reporte menor que q supera al veraz.
    q = eps / 2
    esperada = lambda f, p: q * f(p, 1) + (1 - q) * f(p, 0)
    articulo = lambda p, y: _log_truncada_del_articulo(p, y, eps)
    assert esperada(articulo, eps / 4) > esperada(articulo, q)
    # La del repositorio no: ambos reportes se recortan a eps y empatan (propia, no estricta).
    assert esperada(_log_del_repositorio, eps / 4) == esperada(_log_del_repositorio, q)
    h = _todas_las_hipotesis(m)
    assert h["P5_equivalencia_con_EPSILON_CLIP"].estado == "refutada"
    assert h["P5_validez_por_acotacion"].estado == "demostrada"
    enunciados = {e.id: e for e in m.LECTURA_POR_PUNTO[4].enunciados}
    assert "no longer proper" in enunciados["truncada_no_propia"].parafrasis
    assert enunciados["truncada_no_propia"].pagina == "13"


def test_punto_6_alcance_de_los_teoremas():
    m = _modulo()
    referencias = {(e.pagina, e.referencia) for e in m.LECTURA_POR_PUNTO[5].enunciados}
    for esperado in (("1", "resumen"), ("8", "seccion 3.2"), ("26", "seccion 6"), ("32", "proposicion 1"),
                     ("51", "seccion G, ecuacion (114)"), ("10", "nota 5")):
        assert esperado in referencias, esperado
    h = _todas_las_hipotesis(m)
    assert h["P6_acotacion_de_las_tres_metricas"].estado == "demostrada"
    assert h["P6_pronostico_funcional"].estado == "demostrada"
    assert h["P6_interpretacion_de_la_puntuacion"].estado == "pendiente"


def test_discrepancia_con_el_registro_de_ae62():
    m = _modulo()
    (discrepancia,) = m.DISCREPANCIAS
    registrado = pi.VERIFICACION_FUENTES_SECUENCIALES["choe_ramdas_arxiv_2110_00115v6"]["campos"]["acotacion"][1]
    assert discrepancia["texto_registrado"] in registrado
    assert "no longer proper" in discrepancia["texto_pdf_v6"] and "improper" in discrepancia["texto_pdf_v6"]
    assert discrepancia["tratamiento"].startswith("se conserva la atribucion original")


# ---------------------------------------------------------------------------
# Dependencias de N2, derivacion de 1/E y estados tras AE-64
# ---------------------------------------------------------------------------

def test_dependencias_de_n2_por_via_y_metrica():
    m = _modulo()
    d = m.DEPENDENCIAS_DE_N2
    assert set(d) == {"cobertura_via_teorema_1", "cobertura_via_teorema_2", "cobertura_por_metrica",
                      "interpretacion", "operativos"}
    assert "C2_correspondencia_subgaussiana_teorema_1" in d["cobertura_via_teorema_1"]
    assert "C2_correspondencia_subgaussiana_teorema_1" not in d["cobertura_via_teorema_2"]
    assert "C1_correspondencia_acotacion_teorema_2" in d["cobertura_via_teorema_2"]
    assert "C1_correspondencia_acotacion_teorema_2" not in d["cobertura_via_teorema_1"]
    cobertura = set(d["cobertura_via_teorema_1"]) | set(d["cobertura_via_teorema_2"])
    cobertura |= {x for v in d["cobertura_por_metrica"].values() for x in v}
    assert "C4_truncamiento_de_la_fuente_frente_a_EPSILON_CLIP" not in cobertura
    for solo_interpretacion in ("L2_log_loss_propia", "L2_marginales_reales_en_el_intervalo"):
        assert solo_interpretacion in d["interpretacion"] and solo_interpretacion not in cobertura
    assert d["cobertura_por_metrica"]["log_loss"] == ("L1_acotacion_log_loss",)
    assert "P3_signo_precision_en_5" in d["cobertura_por_metrica"]["precision_en_5"]


def test_estados_tras_ae64_se_derivan_de_sus_dependencias():
    m = _modulo()
    estados = m.ESTADOS_TRAS_AE64
    assert set(estados) == {"C1_correspondencia_acotacion_teorema_2", "C2_correspondencia_subgaussiana_teorema_1",
                            "C3_correspondencia_de_signo", "C4_truncamiento_de_la_fuente_frente_a_EPSILON_CLIP",
                            "C5_aplicabilidad_a_precision_en_5", "F2_correspondencia_de_la_filtracion",
                            "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"}
    esperado = {"C1_correspondencia_acotacion_teorema_2": "demostrada",
                "C2_correspondencia_subgaussiana_teorema_1": "demostrada", "C3_correspondencia_de_signo": "demostrada",
                "C4_truncamiento_de_la_fuente_frente_a_EPSILON_CLIP": "refutada",
                "C5_aplicabilidad_a_precision_en_5": "demostrada", "F2_correspondencia_de_la_filtracion": "pendiente",
                "N2_inversion_para_p1b": "pendiente", "U1_usos_de_1_sobre_E": "pendiente"}
    assert {k: v["estado"] for k, v in estados.items()} == esperado
    assert m.recalcular_estados() == {k: v["estado"] for k, v in estados.items()}
    # La regla no prohibe una demostracion futura: con todas las dependencias demostradas, demostrada.
    assert m.combinar(("demostrada", "demostrada")) == "demostrada"
    assert m.combinar(("demostrada", "pendiente", "refutada")) == "pendiente"
    assert m.combinar(("demostrada", "refutada")) == "refutada"
    assert m.mejor_via(("pendiente", "demostrada")) == "demostrada"


def _psi_exponencial(lam, c):
    return (-math.log(1 - c * lam) - c * lam) / c ** 2


def test_derivacion_1_sobre_e_condicionada_a_la_supermartingala():
    m = _modulo()
    d = m.DERIVACION_1_SOBRE_E_TEOREMA_3
    assert "nula debil" in d["base_en_el_articulo"] and "p. 17" in d["base_en_el_articulo"]
    assert "p. 34" in d["base_en_el_articulo"] and "(40)" in d["base_en_el_articulo"]
    assert d["estado_de_la_derivacion"] == "demostrada_bajo_las_hipotesis_de_la_supermartingala"
    assert d["estado_de_aplicacion_al_repositorio"] == "pendiente"
    assert "P(E_100 >= 1/alfa y Delta_100 <= 0)" in d["nula_terminal"]
    for texto in (d["nula_terminal"], d["nula_sobre_T"]):
        assert "|" not in texto and "dado" not in texto
    assert "no queda cubierto" in d["limitacion"]
    assert {"F1_anterioridad", "F2_correspondencia_de_la_filtracion",
            "O3_tratamiento_de_omisiones"} <= set(d["dependencias_de_aplicacion"])
    # Ejemplo exacto con la ley de AE-62: delta_1 = 1/2, delta_2 = -1/2, Delta_2 = 0; |delta_hat| <= 1 = c/2.
    c, gamma = 2.0, 0.0
    ley = {(a, b): (0.75 if a == 1 else 0.25) * (0.25 if b == 1 else 0.75) for a in (1, -1) for b in (1, -1)}
    deltas = (0.5, -0.5)
    for lam in (0.1, 0.25, 0.4, 0.49):
        psi = _psi_exponencial(lam, c)
        esperanza_e2 = esperanza_l2 = 0.0
        for (a, b), pr in ley.items():
            v = (a - gamma) ** 2 + (b - gamma) ** 2
            e2 = math.exp(lam * (a + b) - psi * v)
            l2 = math.exp(lam * ((a - deltas[0]) + (b - deltas[1])) - psi * v)
            assert math.isclose(e2, l2 * math.exp(lam * (deltas[0] + deltas[1])), rel_tol=1e-12)
            esperanza_e2 += pr * e2
            esperanza_l2 += pr * l2
        assert esperanza_e2 <= esperanza_l2 + 1e-12 <= 1 + 1e-12  # Delta_2 = 0: E_2 = L_2 y E[L_2] <= 1
    # Limitacion: con Delta_1 = 1/2 > 0 y lambda = 0,4, E[E_1] > 1; el supremo sobre i <= 2 no queda cubierto.
    lam = 0.4
    psi = _psi_exponencial(lam, c)
    esperanza_e1 = sum(pr * math.exp(lam * a - psi * (a - gamma) ** 2) for a, pr in ((1, 0.75), (-1, 0.25)))
    assert esperanza_e1 > 1


def test_u1_sigue_pendiente_por_sus_dependencias_de_aplicacion():
    m = _modulo()
    u1 = m.ESTADOS_TRAS_AE64["U1_usos_de_1_sobre_E"]
    assert u1["estado"] == "pendiente"
    assert set(u1["dependencias"]) == set(m.DERIVACION_1_SOBRE_E_TEOREMA_3["dependencias_de_aplicacion"])
    for familia in pi.FAMILIAS_INFERENCIALES:
        assert familia.uso_1_sobre_e_nula_terminal in ("no_aplica", "pendiente_de_demostracion")
        assert familia.uso_1_sobre_e_supervision in ("no_aplica", "pendiente_de_demostracion")


def test_texto_de_n2_en_ae63_remite_al_desglose():
    _modulo()
    n2 = {c.id: c for c in tc.CONDICIONES_DE_TRASLADO}["N2_inversion_para_p1b"]
    assert "depende de C1, C3, F1 y F2" not in n2.afirmacion
    assert "verificacion_primaria_choe_ramdas.DEPENDENCIAS_DE_N2" in n2.afirmacion
    assert n2.estado == "pendiente"


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def test_textos_sin_aprobacion_ni_autorizacion():
    m = _modulo()
    textos = [str(v) for v in m.PROCEDENCIA_V6.values()]
    for e in _todos_los_enunciados(m):
        textos += [e.id, e.referencia, e.parafrasis]
    for h in _todas_las_hipotesis(m).values():
        textos += [h.id, h.afirmacion, h.base, h.exige]
    textos += [str(v) for v in m.DERIVACION_1_SOBRE_E_TEOREMA_3.values()]
    textos += [str(v["motivo"]) for v in m.ESTADOS_TRAS_AE64.values()]
    textos += [str(v) for d in m.DISCREPANCIAS for v in d.values()]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


# ---------------------------------------------------------------------------
# Invariante: estado, bloqueos y registros previos (no importa el modulo nuevo)
# ---------------------------------------------------------------------------

def test_estado_bloqueos_y_registros_intactos():
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    for decision in tc.DECISIONES_DEL_OPERADOR_AE63.values():
        assert decision.valor is None
    secuencia = {f.id: f for f in pi.FAMILIAS_INFERENCIALES}["secuencia_confianza_uniforme_martingala"]
    assert secuencia.uso_1_sobre_e_nula_terminal == secuencia.uso_1_sobre_e_supervision == "pendiente_de_demostracion"
    pi.verificar_expediente()
    assert len(PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"
    registro = json.dumps({k: {c: list(v) for c, v in e["campos"].items()}
                           for k, e in pi.VERIFICACION_FUENTES_SECUENCIALES.items()}, sort_keys=True)
    assert registro.count("enunciado_comprobado_en_preprint_identificado") == 14
    assert registro.count("aplicacion_al_repositorio_sin_verificar") == 2
    conteo = {}
    for c in tc.CONDICIONES_DE_TRASLADO:
        conteo[c.estado] = conteo.get(c.estado, 0) + 1
    assert conteo == {"demostrada": 12, "refutada": 4, "pendiente": 11}
