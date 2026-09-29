"""Tests de la Etapa AE-63, validada: traslado de las condiciones
inferenciales registradas en AE-62 al contrato concreto del repositorio.

Comprueban, sobre el codigo y con entradas sinteticas, el dominio de
reportes del contrato (43 probabilidades en (0, 1) sin restriccion
conjunta), la acotacion de d_t en Log Loss, Brier y P@5, la cota de
incrementos, la propiedad de cada regla en su dominio exacto, el signo de
d_t, el efecto de las omisiones y la clasificacion de cada condicion como
demostrada, refutada o pendiente. Ninguna condicion global de traslado
queda demostrada y todos los usos de 1/E siguen pendientes.

El modulo nuevo se importa dentro de cada prueba para que, sobre la base,
cada regresion falle por separado. Todo sintetico: sin datos reales,
PostgreSQL, entrenamiento ni predicciones reales."""
from __future__ import annotations

import importlib
import json
import math
import re
from fractions import Fraction

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53, metricas_por_sorteo
from app.application.ml.metricas import EPSILON_CLIP, _recortar, _top5_deterministico
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52
from app.application.ml.tipos import FilaCandidato

EPS = EPSILON_CLIP
SORTEO = [10, 11, 12, 13, 14]


def _modulo():
    return importlib.import_module("app.application.ml.traslado_condiciones_inferenciales")


def _probabilidades(p_en_sorteo, p_fuera, sorteo=SORTEO):
    return [p_en_sorteo if n in sorteo else p_fuera for n in range(1, 44)]


def _perdida_log_esperada(q, p):
    c = min(max(p, EPS), 1 - EPS)
    return -(q * math.log(c) + (1 - q) * math.log(1 - c))


# ---------------------------------------------------------------------------
# Dominio del contrato e intervalos de d_t
# ---------------------------------------------------------------------------

def test_dominio_del_contrato_sin_restriccion_conjunta():
    m = _modulo()
    vectores = ([1e-9] * 43, [1 - 1e-9] * 43, _probabilidades(1e-9, 1 - 1e-9))
    sumas = [math.fsum(v) for v in vectores]
    assert all(0.0 < p < 1.0 for v in vectores for p in v)
    assert sumas[0] < 1e-6
    assert 38 - 1e-6 < sumas[2] < 38
    assert 43 - 1e-6 < sumas[1] < 43
    for v in vectores:
        metricas_por_sorteo("BALOTO", 1, v, SORTEO)  # aceptado: ninguna suma fija
    dominio = m.DOMINIO_DEL_CONTRATO
    assert "sin restriccion conjunta" in dominio["reportes"]
    assert "suma 5" in dominio["resultados"]
    assert "numero ascendente" in dominio["desempate_top5"]
    assert "especificacion_evaluacion_prospectiva:metricas_por_sorteo" in dominio["simbolos"]


def test_intervalo_log_loss_exacto_y_alcanzable_en_el_dominio():
    m = _modulo()
    for juego in ("BALOTO", "BALOTO_REVANCHA"):
        intervalo = m.intervalo_diferencia_log_loss(juego)
        assert intervalo.cerrado is True
        peor = metricas_por_sorteo(juego, 1, _probabilidades(1e-9, 1 - 1e-9), SORTEO).diferencias["log_loss"]
        mejor = metricas_por_sorteo(juego, 1, _probabilidades(1 - 1e-9, 1e-9), SORTEO).diferencias["log_loss"]
        assert math.isclose(peor, intervalo.inferior, rel_tol=0, abs_tol=1e-9)
        assert math.isclose(mejor, intervalo.superior, rel_tol=0, abs_tol=1e-9)
        assert math.isclose(m.ancho(intervalo), math.log((1 - EPS) / EPS), rel_tol=1e-12)


def test_intervalo_brier_abierto_y_supremos():
    m = _modulo()
    intervalo = m.intervalo_diferencia_brier("BALOTO")
    assert intervalo.cerrado is False
    uniforme = metricas_por_sorteo("BALOTO", 1, [5 / 43] * 43, SORTEO).uniforme.brier_score
    assert math.isclose(intervalo.superior, uniforme, rel_tol=1e-12)
    assert math.isclose(intervalo.inferior, uniforme - 1, rel_tol=1e-12)
    # Comparacion estricta con un punto interior cuya distancia al extremo es representable: con reportes a
    # 1e-5 del extremo, la distancia ideal al supremo es 1e-10 y al infimo 2e-5 (menos terminos de orden
    # 1e-10), muy por encima del error de redondeo de sumar 43 terminos (decenas de ulp, ~1e-15).
    peor = metricas_por_sorteo("BALOTO", 1, _probabilidades(1e-5, 1 - 1e-5), SORTEO).diferencias["brier_score"]
    mejor = metricas_por_sorteo("BALOTO", 1, _probabilidades(1 - 1e-5, 1e-5), SORTEO).diferencias["brier_score"]
    assert intervalo.inferior < peor < intervalo.inferior + 1e-4
    assert intervalo.superior - 1e-9 < mejor < intervalo.superior
    assert math.isclose(intervalo.superior - mejor, 1e-10, rel_tol=1e-4)
    assert m.ancho(intervalo) == 1.0
    # Con reportes a 1e-9 del extremo, la distancia ideal 1e-18 es menor que media ulp de B_u (~1,39e-17): el
    # valor en coma flotante puede redondearse al extremo, y el supremo en forma cerrada puede diferir de la
    # suma de 43 terminos de metricas_por_sorteo en decenas de ulp. No se exige desigualdad estricta ahi; solo
    # cercania dentro del error de redondeo. El intervalo abierto describe los valores matematicos ideales.
    assert 1e-18 < math.ulp(intervalo.superior) / 2
    redondeado = metricas_por_sorteo("BALOTO", 1, _probabilidades(1 - 1e-9, 1e-9), SORTEO).diferencias["brier_score"]
    assert abs(redondeado - intervalo.superior) <= 64 * math.ulp(intervalo.superior)


def test_brier_distingue_valores_ideales_de_coma_flotante():
    m = _modulo()
    documentacion = m.intervalo_diferencia_brier.__doc__
    for fragmento in ("valores matematicos ideales", "coma flotante", "puede coincidir con un extremo"):
        assert fragmento in documentacion, fragmento
    b1 = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}["B1_acotacion_brier"]
    assert b1.estado == "demostrada"
    for fragmento in ("valores matematicos ideales", "coma flotante", "puede coincidir con un extremo por redondeo"):
        assert fragmento in b1.afirmacion, fragmento


def test_intervalo_precision_en_5_extremos_alcanzables():
    m = _modulo()
    intervalo = m.intervalo_diferencia_precision_en_5()
    assert (intervalo.inferior, intervalo.superior, intervalo.cerrado) == (-1.0, 1.0, True)
    # d = 1: sale {1..5} (la uniforme acierta todo) y la estrategia no acierta.
    d_max = metricas_por_sorteo("BALOTO", 1, _probabilidades(0.1, 0.9, [1, 2, 3, 4, 5]), [1, 2, 3, 4, 5])
    # d = -1: sale {6..10} (la uniforme no acierta) y el Top-5 de la estrategia es el sorteo.
    d_min = metricas_por_sorteo("BALOTO", 1, _probabilidades(0.9, 0.1, [6, 7, 8, 9, 10]), [6, 7, 8, 9, 10])
    assert d_max.diferencias["precision_en_5"] == 1.0
    assert d_min.diferencias["precision_en_5"] == -1.0


def test_cota_de_incrementos_es_el_ancho():
    m = _modulo()
    assert math.isclose(m.cota_de_incrementos(m.intervalo_diferencia_log_loss("BALOTO")),
                        math.log((1 - EPS) / EPS), rel_tol=1e-12)
    assert m.cota_de_incrementos(m.intervalo_diferencia_brier("BALOTO")) == 1.0
    assert m.cota_de_incrementos(m.intervalo_diferencia_precision_en_5()) == 2.0
    # Con d en [a, b], g = E[d | F] tambien esta en [a, b] y |d - g| <= b - a.
    a, b = Fraction(-3), Fraction(2)
    for peso in (Fraction(0), Fraction(1, 3), Fraction(1)):
        g = peso * a + (1 - peso) * b
        assert a <= g <= b and max(abs(a - g), abs(b - g)) <= b - a


# ---------------------------------------------------------------------------
# Propiedad de las reglas en su dominio exacto
# ---------------------------------------------------------------------------

def test_log_loss_propia_en_verdades_reportables_y_no_estricta():
    m = _modulo()
    q = 1e-7
    assert _perdida_log_esperada(q, 1e-7) == _perdida_log_esperada(q, 1e-8)  # empate exacto
    for q in (0.05, 0.3, 0.7):
        rejilla = [i / 1000 for i in range(1, 1000)]
        optimo = min(_perdida_log_esperada(q, p) for p in rejilla)
        assert _perdida_log_esperada(q, q) <= optimo + 1e-15
    condiciones = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}
    propia = condiciones["L2_log_loss_propia"]
    assert propia.estado == "demostrada"
    # La propiedad se afirma solo para verdades reportables: q en (0, 1), nunca q en [0, 1].
    assert propia.dominio == "q en (0, 1); reporte en (0, 1)"
    assert "[0, 1]" not in propia.dominio
    assert "q en (0, 1)" in propia.afirmacion
    estricta = condiciones["L2_log_loss_estricta_en_todo_el_dominio"]
    assert estricta.estado == "refutada"
    assert "[0, 1]" not in estricta.dominio


def test_log_loss_verdades_de_frontera_sin_reporte_veraz():
    m = _modulo()
    minimo = -math.log(1 - EPS)
    # Extremos abiertos: p = 0 y p = 1 no pertenecen al dominio contractual (0, 1).
    for prohibido in (0.0, 1.0):
        try:
            metricas_por_sorteo("BALOTO", 1, [prohibido] + [0.5] * 42, SORTEO)
        except ValueError:
            pass
        else:
            raise AssertionError(f"el contrato acepto p = {prohibido}")
    # Con q = 0 la perdida esperada es -log(1 - clip(p)), estrictamente creciente en clip(p); con q = 1 es
    # -log(clip(p)), estrictamente decreciente. Los minimizadores admisibles son, exactamente, los p del
    # dominio (0, 1) con clip(p) = eps (q = 0) o clip(p) = 1 - eps (q = 1).
    borde = 1 - EPS
    # q = 0: exactamente 0 < p <= eps, extremos abiertos incluidos en su lado admisible.
    for p in (math.nextafter(0.0, 1.0), 1e-300, 1e-9, math.nextafter(EPS, 0.0), EPS):
        assert 0.0 < p <= EPS and _recortar(p) == EPS and _perdida_log_esperada(0.0, p) == minimo
    for p in (math.nextafter(EPS, 1.0), 2e-6, 0.5, math.nextafter(1.0, 0.0)):
        assert _recortar(p) > EPS  # fuera del conjunto de minimizadores
    for p in (2e-6, 0.5, math.nextafter(1.0, 0.0)):
        assert _perdida_log_esperada(0.0, p) > minimo  # diferencias representables en coma flotante
    # q = 1: exactamente 1 - eps <= p < 1.
    for p in (borde, math.nextafter(borde, 1.0), 1 - 1e-9, math.nextafter(1.0, 0.0)):
        assert borde <= p < 1.0 and _recortar(p) == borde and _perdida_log_esperada(1.0, p) == minimo
    for p in (math.nextafter(borde, 0.0), 0.5, math.nextafter(0.0, 1.0)):
        assert _recortar(p) < borde
    for p in (1 - 2e-6, 0.5, math.nextafter(0.0, 1.0)):
        assert _perdida_log_esperada(1.0, p) > minimo
    condicion = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}["L2_log_loss_verdades_de_frontera"]
    assert condicion.estado == "demostrada"
    assert condicion.dominio == "q en {0, 1}; reporte en (0, 1)"
    for fragmento in ("0 < p <= eps", "1 - eps <= p < 1", "se alcanza mediante el recorte", "no es admisible"):
        assert fragmento in condicion.afirmacion, fragmento
    for impreciso in ("cualquier p <= eps", "p >= 1 - eps", "limite"):
        assert impreciso not in condicion.afirmacion, impreciso
    assert "veraz" not in condicion.afirmacion.replace("no hay reporte veraz admisible", "")


def test_marginales_reales_separadas_de_la_decision_sobre_reportes():
    m = _modulo()
    condicion = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}["L2_marginales_reales_en_el_intervalo"]
    assert condicion.estado == "pendiente"
    assert condicion.sustento == "requiere_evidencia_o_hipotesis_declarada"
    assert condicion.decision_del_operador != "rango_admisible_de_probabilidades_de_la_estrategia"
    for fragmento in ("mecanismo de sorteo (P3)", "hipotesis declarada y justificada"):
        assert fragmento in condicion.evidencia_necesaria, fragmento
    alcance = m.ALCANCE_DE_LA_DECISION_SOBRE_REPORTES
    for fragmento in ("solo restringe los reportes", "no es evidencia sobre las marginales reales q_i"):
        assert fragmento in alcance, fragmento
    estricta = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}["L2_log_loss_estricta_en_D"]
    assert "L2_marginales_reales_en_el_intervalo" in estricta.afirmacion


def test_log_loss_estricta_solo_con_q_y_reporte_en_el_intervalo():
    m = _modulo()
    q = 0.3
    assert _perdida_log_esperada(q, q) < min(_perdida_log_esperada(q, q - 1e-4), _perdida_log_esperada(q, q + 1e-4))
    # Con q < EPS y reportes restringidos a [EPS, 1 - EPS], el optimo es EPS, distinto de q.
    q = 1e-7
    rejilla = [EPS * (1 + k / 10) for k in range(0, 50)]
    mejor = min(rejilla, key=lambda p: _perdida_log_esperada(q, p))
    assert mejor == EPS and mejor != q and q < EPS
    condiciones = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}
    estricta = condiciones["L2_log_loss_estricta_en_D"]
    assert estricta.estado == "demostrada"
    assert "q en [eps, 1 - eps]" in estricta.dominio and "reporte en [eps, 1 - eps]" in estricta.dominio
    assert condiciones["L2_marginales_reales_en_el_intervalo"].estado == "pendiente"


def test_brier_estrictamente_propia_con_q_interior():
    m = _modulo()
    for q in (Fraction(1, 10), Fraction(1, 2), Fraction(5, 43)):
        for p in (Fraction(1, 100), Fraction(1, 3), q, Fraction(9, 10)):
            esperada = q * (1 - p) ** 2 + (1 - q) * p ** 2
            assert esperada == (p - q) ** 2 + q * (1 - q)
            if p != q:
                assert esperada > q * (1 - q)
    # Con q = 0 el infimo p = 0 no esta en el dominio abierto: ningun reporte lo alcanza.
    assert all(p ** 2 > 0 for p in (Fraction(1, 10 ** k) for k in range(1, 8)))
    condicion = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}["B2_brier_estricta_q_interior"]
    assert condicion.estado == "demostrada" and "q en (0, 1)" in condicion.dominio


def test_precision_en_5_propia_no_estricta():
    m = _modulo()
    # Mezcla factible: componente uniforme (5/43 por numero) y dos sorteos fijos.
    w_uniforme, w1, w2 = Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)
    d1, d2 = {10, 11, 12, 13, 14}, {10, 11, 12, 20, 21}
    q = {i: w_uniforme * Fraction(5, 43) + w1 * (i in d1) + w2 * (i in d2) for i in range(1, 44)}
    assert w_uniforme + w1 + w2 == 1
    assert all(0 < v < 1 for v in q.values()) and sum(q.values()) == 5

    def esperanza(conjunto):
        # E_uniforme|A ∩ sorteo| = 5 * 5/43 en forma cerrada.
        return (w_uniforme * Fraction(25, 43) + w1 * len(conjunto & d1) + w2 * len(conjunto & d2)) / 5

    reporte = [float(q[n]) for n in range(1, 44)]
    filas = [FilaCandidato(codigo_juego="BALOTO", sorteo_objetivo=1, calculado_hasta_sorteo=0, numero_candidato=n,
                           etiqueta=0, frecuencia_acumulada=0.0, frecuencia_ventana_10=0.0,
                           frecuencia_ventana_20=0.0, frecuencia_ventana_50=0.0,
                           sorteos_desde_ultima_aparicion=None, aparecio_en_sorteo_anterior=0)
             for n in range(1, 44)]
    veraz = {f.numero_candidato for f in _top5_deterministico(list(zip(filas, reporte)))}
    assert veraz == {10, 11, 12, 13, 14}  # 13 y 14 ganan el empate del cuarto al septimo puesto
    candidatos = [veraz, {10, 11, 12, 20, 21}, {10, 11, 12, 13, 20}, {10, 11, 13, 14, 20}, {1, 2, 3, 4, 5},
                  {13, 14, 20, 21, 1}]
    for conjunto in candidatos:
        assert esperanza(conjunto) == sum(q[i] for i in conjunto) / 5
        assert esperanza(veraz) >= esperanza(conjunto)
    # Empate en el quinto puesto: el desempate no reduce la esperanza.
    assert esperanza(veraz) == esperanza({10, 11, 12, 20, 21}) == esperanza({10, 11, 12, 13, 20})
    # No estricta: otro reporte con el mismo Top-5 tiene la misma esperanza.
    otro = [0.9 if n in veraz else 0.01 for n in range(1, 44)]
    assert {f.numero_candidato for f in _top5_deterministico(list(zip(filas, otro)))} == veraz
    condiciones = {c.id: c.estado for c in m.CONDICIONES_DE_TRASLADO}
    assert condiciones["P2_precision_en_5_propia_no_estricta"] == "demostrada"
    assert condiciones["P2_precision_en_5_estricta"] == "refutada"
    assert condiciones["C5_aplicabilidad_a_precision_en_5"] == "pendiente"


def test_signo_de_d_t_en_las_tres_metricas():
    m = _modulo()
    buena = metricas_por_sorteo("BALOTO", 1, _probabilidades(0.9, 0.01), SORTEO).diferencias
    assert buena["log_loss"] > 0 and buena["brier_score"] > 0 and buena["precision_en_5"] < 0
    assert REGLAS_EVALUACION_AE52["orientacion_diferencia"] == "uniforme_menos_estrategia"
    assert dict(pi.ORIENTACION_MEJORA_POR_METRICA) == {"log_loss": "positiva", "brier_score": "positiva",
                                                       "precision_en_5": "negativa"}
    estados = {c.id: c.estado for c in m.CONDICIONES_DE_TRASLADO}
    assert estados["S1_signo_de_d_t_en_el_codigo"] == "demostrada"
    assert estados["C3_correspondencia_de_signo"] == "pendiente"


# ---------------------------------------------------------------------------
# Omisiones
# ---------------------------------------------------------------------------

def test_omision_dependiente_del_resultado_rompe_la_martingala():
    m = _modulo()
    ley = {Fraction(1): Fraction(1, 2), Fraction(-1): Fraction(1, 2)}
    assert sum(d * p for d, p in ley.items()) == 0  # g_t = 0
    incluido = {d: p for d, p in ley.items() if d > 0}  # se omite si d_t < 0
    media_incluida = sum(d * p for d, p in incluido.items()) / sum(incluido.values())
    assert media_incluida == 1
    assert {c.id: c.estado for c in m.CONDICIONES_DE_TRASLADO}["O2_omision_dependiente_del_resultado"] == "refutada"


def test_omision_predecible_conserva_la_diferencia_de_martingala():
    m = _modulo()
    for g in (Fraction(0), Fraction(1, 3), Fraction(-1, 5)):
        ley = {1: (1 + g) / 2, -1: (1 - g) / 2}  # d_t en {-1, 1} con E[d_t | F] = g
        for indicador in (0, 1):  # I_t fijado antes del sorteo
            assert sum(indicador * d * p for d, p in ley.items()) == indicador * g
    assert {c.id: c.estado for c in m.CONDICIONES_DE_TRASLADO}["O1_omision_predecible"] == "demostrada"


# ---------------------------------------------------------------------------
# Registro de condiciones, simbolos, nulas y decisiones
# ---------------------------------------------------------------------------

_DEMOSTRADAS = {"L1_acotacion_log_loss", "L2_log_loss_propia", "L2_log_loss_verdades_de_frontera",
                "L2_log_loss_estricta_en_D", "B1_acotacion_brier",
                "B2_brier_estricta_q_interior", "P1_acotacion_precision_en_5", "P2_precision_en_5_propia_no_estricta",
                "S1_signo_de_d_t_en_el_codigo", "K1_cota_de_incrementos", "K2_subgaussianidad_por_acotacion",
                "O1_omision_predecible"}
_REFUTADAS = {"L2_log_loss_estricta_en_todo_el_dominio", "P2_precision_en_5_estricta",
              "N1_traslado_automatico_desde_H0w", "O2_omision_dependiente_del_resultado"}
_PENDIENTES = {"L2_marginales_reales_en_el_intervalo", "C1_correspondencia_acotacion_teorema_2",
               "C2_correspondencia_subgaussiana_teorema_1", "C3_correspondencia_de_signo",
               "C4_truncamiento_de_la_fuente_frente_a_EPSILON_CLIP", "C5_aplicabilidad_a_precision_en_5",
               "F1_anterioridad", "F2_correspondencia_de_la_filtracion", "N2_inversion_para_p1b",
               "O3_tratamiento_de_omisiones", "U1_usos_de_1_sobre_E"}


def test_condiciones_registradas_y_clasificadas():
    m = _modulo()
    assert m.ESTADOS_CONDICION == ("demostrada", "refutada", "pendiente")
    assert m.SUSTENTOS == ("derivacion_propia_sobre_el_codigo", "contraejemplo_exacto", "requiere_enunciado_de_fuente",
                           "requiere_decision_del_operador", "requiere_evidencia_o_hipotesis_declarada")
    condiciones = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}
    assert len(condiciones) == len(m.CONDICIONES_DE_TRASLADO)
    assert {k for k, c in condiciones.items() if c.estado == "demostrada"} == _DEMOSTRADAS
    assert {k for k, c in condiciones.items() if c.estado == "refutada"} == _REFUTADAS
    assert {k for k, c in condiciones.items() if c.estado == "pendiente"} == _PENDIENTES
    for c in condiciones.values():
        assert c.sustento in m.SUSTENTOS and c.afirmacion and c.simbolos_del_repositorio, c.id
        if c.estado == "demostrada":
            assert c.sustento == "derivacion_propia_sobre_el_codigo", c.id
        if c.estado == "refutada":
            assert c.sustento == "contraejemplo_exacto", c.id
        if c.estado == "pendiente":
            assert c.sustento in ("requiere_enunciado_de_fuente", "requiere_decision_del_operador",
                                  "requiere_evidencia_o_hipotesis_declarada"), c.id
            assert c.enunciado_de_fuente_necesario or c.decision_del_operador or c.evidencia_necesaria, c.id
        if c.sustento == "requiere_evidencia_o_hipotesis_declarada":
            assert c.evidencia_necesaria and not c.decision_del_operador, c.id
    for c in condiciones.values():
        if c.sustento == "requiere_enunciado_de_fuente":
            assert "arXiv:2110.00115v6" in c.enunciado_de_fuente_necesario, c.id
    assert len(m.ENUNCIADOS_DE_FUENTE_NECESARIOS) == 6
    assert all("arXiv:2110.00115v6" in e for e in m.ENUNCIADOS_DE_FUENTE_NECESARIOS)


def test_simbolos_del_repositorio_existen():
    m = _modulo()
    simbolos = {s for c in m.CONDICIONES_DE_TRASLADO for s in c.simbolos_del_repositorio}
    simbolos |= set(m.DOMINIO_DEL_CONTRATO["simbolos"])
    for referencia in sorted(simbolos):
        modulo, simbolo = referencia.split(":")
        assert hasattr(importlib.import_module(f"app.application.ml.{modulo}"), simbolo), referencia


def test_sin_traslado_de_nula_fuerte_a_p1b_y_1_sobre_e_pendiente():
    m = _modulo()
    condiciones = {c.id: c for c in m.CONDICIONES_DE_TRASLADO}
    assert condiciones["N1_traslado_automatico_desde_H0w"].estado == "refutada"
    assert condiciones["N2_inversion_para_p1b"].estado == "pendiente"
    assert condiciones["U1_usos_de_1_sobre_E"].estado == "pendiente"
    assert not any(c.estado == "demostrada" and ("1/E" in c.afirmacion or "P1b" in c.afirmacion)
                   for c in m.CONDICIONES_DE_TRASLADO)
    for familia in pi.FAMILIAS_INFERENCIALES:
        assert familia.uso_1_sobre_e_nula_terminal in ("no_aplica", "pendiente_de_demostracion")
        assert familia.uso_1_sobre_e_supervision in ("no_aplica", "pendiente_de_demostracion")
    choe = pi.VERIFICACION_FUENTES_SECUENCIALES["choe_ramdas_arxiv_2110_00115v6"]["campos"]
    assert choe["trasladable_al_contrato"][0] == "aplicacion_al_repositorio_sin_verificar"


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def test_decisiones_del_operador_sin_valor_y_textos_sin_aprobacion():
    m = _modulo()
    decisiones = m.DECISIONES_DEL_OPERADOR_AE63
    assert set(decisiones) == {"cota", "rango_admisible_de_probabilidades_de_la_estrategia", "tratamiento_de_omisiones",
                               "mecanismo_de_sellado_temporal_externo",
                               "lectura_primaria_pendiente_de_fuentes_secuenciales",
                               "papel_y_direccion_de_la_secundaria", "tiempos_supervision"}
    existentes = {d.id for d in pi.DECISIONES_REQUERIDAS} | set(pi.DECISIONES_INFERENCIALES_ABIERTAS)
    assert set(decisiones) - existentes == {"rango_admisible_de_probabilidades_de_la_estrategia"}
    for decision in decisiones.values():
        assert decision.valor is None and decision.estado == "sin_decidir"
    for c in m.CONDICIONES_DE_TRASLADO:
        assert not c.decision_del_operador or c.decision_del_operador in decisiones, c.id
    textos = [*m.ENUNCIADOS_DE_FUENTE_NECESARIOS, *(v for k, v in m.DOMINIO_DEL_CONTRATO.items() if k != "simbolos"),
              m.ALCANCE_DE_LA_DECISION_SOBRE_REPORTES]
    for c in m.CONDICIONES_DE_TRASLADO:
        textos += [c.id, c.ambito, c.afirmacion, c.dominio, c.enunciado_de_fuente_necesario, c.decision_del_operador,
                   c.evidencia_necesaria]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


# ---------------------------------------------------------------------------
# Invariante: estado, bloqueos y base intactos (no importa el modulo nuevo)
# ---------------------------------------------------------------------------

def test_estado_bloqueos_y_base_intactos():
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    for familia in pi.FAMILIAS_INFERENCIALES:
        if familia.id == "secuencia_confianza_uniforme_martingala":
            assert familia.uso_1_sobre_e_nula_terminal == familia.uso_1_sobre_e_supervision == \
                "pendiente_de_demostracion"
    pi.verificar_expediente()
    assert len(PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"
    registro = json.dumps({k: {c: list(v) for c, v in e["campos"].items()}
                           for k, e in pi.VERIFICACION_FUENTES_SECUENCIALES.items()}, sort_keys=True)
    assert registro.count("aplicacion_al_repositorio_sin_verificar") == 2
    assert registro.count("enunciado_comprobado_en_preprint_identificado") == 14
