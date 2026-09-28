"""Tests de la Etapa AE-61, validada: auditoria del expediente de
inferencia prospectiva (AE-60). Regresiones de los hallazgos de la
auditoria de `app/application/ml/propuesta_inferencia_prospectiva.py`,
escritas antes de corregir:

- E1: condicion suficiente (anidamiento en el nivel) para la formula de
  inversion de P1b-unico;
- E2: descripcion de A2 coherente con su estado en P2;
- E3: la conjuncion con e-valores queda condicionada a e-valores validos,
  hoy pendientes;
- H1: garantia conjunta frente a garantia clasica sobre un estimando
  aleatorio;
- H2: construccion explicita de L-sint como condicion suficiente;
- D1: decision de multiplicidad entre preguntas o familias.

Todo sintetico: solo constantes del expediente. Sin datos reales,
PostgreSQL, entrenamiento ni predicciones reales. No convierte ninguna
garantia pendiente en valida ni elige pregunta, familia o valor."""
from __future__ import annotations

import json
import re

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52

FAMILIAS = {f.id: f for f in pi.FAMILIAS_INFERENCIALES}
ESCENARIOS = {e.id: e for e in pi.ESCENARIOS_ESTUDIO}


def _clausula_unico(texto: str) -> str:
    return texto.split("unico:", 1)[1]


def test_e1_condicion_suficiente_para_la_inversion_de_p1b_unico():
    unico = _clausula_unico(FAMILIAS["secuencia_confianza_uniforme_martingala"].valor_p)
    assert "anidada en el nivel" in unico
    assert "condicion suficiente" in unico


def test_e2_a2_exige_ventaja_condicional_negativa_en_alguna_t():
    a2 = ESCENARIOS["A2"]
    assert "g_t < 0 en alguna t" in a2.descripcion
    assert a2.estado_por_pregunta["P2"] == "alternativa"


def test_e3_conjuncion_con_e_valores_condicionada():
    assert pi.CONJUNCION["por_juego_e"] == "minimo_de_e_log_loss_y_e_brier"
    assert pi.CONJUNCION["por_juego_e_estado"] == "condicionado_a_e_valores_validos_por_metrica_hoy_pendientes"
    for familia in pi.FAMILIAS_INFERENCIALES:
        assert familia.uso_1_sobre_e_nula_terminal in ("no_aplica", "pendiente_de_demostracion")
        assert familia.uso_1_sobre_e_supervision in ("no_aplica", "pendiente_de_demostracion")
    secuencia = FAMILIAS["secuencia_confianza_uniforme_martingala"]
    assert secuencia.uso_1_sobre_e_nula_terminal == secuencia.uso_1_sobre_e_supervision == "pendiente_de_demostracion"


def test_h1_sentido_de_la_garantia():
    assert pi.SENTIDO_DE_LA_GARANTIA_P1B == {
        "conjunta": "P(rechazo y evento nulo) <= nivel en cualquier ley, dadas las cotas de incrementos y la "
                    "estructura predictible de la familia; no es garantia condicional dado el evento nulo",
        "clasica": "solo para la clase de leyes en que la nula vale casi seguro",
    }
    for clave in ("cota_martingala_tiempo_fijo", "secuencia_confianza_uniforme_martingala"):
        assert "garantia conjunta" in FAMILIAS[clave].valor_p, clave


def test_h2_construccion_explicita_de_l_sint():
    descripcion = ESCENARIOS["L_sint"].descripcion
    for fragmento in ("p_t y q_t fijadas de antemano", "suma exacta cero", "condicion suficiente"):
        assert fragmento in descripcion, fragmento


def test_d1_multiplicidad_entre_preguntas_o_familias():
    decisiones = {d.id: d for d in pi.DECISIONES_REQUERIDAS}
    decision = decisiones["multiplicidad_entre_preguntas_o_familias"]
    assert decision.clase == "humana"
    assert decision.valor is None and decision.estado == "sin_decidir"


# ---------------------------------------------------------------------------
# Invariantes: ningun estado, garantia ni valor cambia
# ---------------------------------------------------------------------------

_ESTADOS_BASE = {
    "A0": ("nula_frontera", "nula_frontera", "nula_frontera", "nula"),
    "A1": ("nula_frontera", "nula_frontera", "segun_T", "alternativa"),
    "A2": ("nula_interior", "nula_interior", "nula_interior", "alternativa"),
    "A3": ("alternativa", "alternativa", "alternativa", "alternativa"),
    "A4": ("nula_frontera", "nula_frontera", "nula_frontera", "nula"),
    "L_unif": ("nula_interior", "nula_interior", "nula_interior", "alternativa"),
    "L_sint": ("nula_frontera", "nula_frontera", "segun_T", "alternativa"),
}


def test_estados_de_escenarios_sin_cambios():
    for clave, estados in _ESTADOS_BASE.items():
        actual = ESCENARIOS[clave].estado_por_pregunta
        assert tuple(actual[p] for p in ("P1a", "P1b_unico", "P1b_supervision", "P2")) == estados, clave


def test_familias_y_garantias_sin_cambios():
    esperado = {
        "remuestreo_iid_media": (("P1a",), "aproximada_por_remuestreo", "no_aplica", "no_aplica"),
        "remuestreo_bloques_media": (("P1a",), "aproximada_por_remuestreo", "no_aplica", "no_aplica"),
        "t_media_sin_autocorrelacion": (("P1a",), "asintotica_tiempo_fijo", "no_aplica", "no_aplica"),
        "t_media_varianza_hac": (("P1a",), "asintotica_tiempo_fijo", "no_aplica", "no_aplica"),
        "contraste_condicional": (("P2",), "asintotica_tiempo_fijo", "no_aplica", "no_aplica"),
        "cota_martingala_tiempo_fijo": (("P1b_unico",), "no_asintotica_tiempo_fijo", "valor_p_azuma_tiempo_fijo",
                                        "no_aplica"),
        "secuencia_confianza_uniforme_martingala": (("P1b_unico", "P1b_supervision"), "uniforme_en_el_tiempo",
                                                    "inversion_intervalo_t100", "inversion_secuencia_simultanea"),
        "secuencia_confianza_apuesta_media_comun": ((), "uniforme_en_el_tiempo", "no_aplica", "no_aplica"),
    }
    actual = {f.id: (f.preguntas, f.garantia, f.modo_p1b_unico, f.modo_p1b_supervision)
              for f in pi.FAMILIAS_INFERENCIALES}
    assert actual == esperado


def test_decisiones_abiertas_sin_valor_y_estado_fijo():
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def test_textos_nuevos_sin_aprobacion_ni_autorizacion():
    textos = [*pi.SENTIDO_DE_LA_GARANTIA_P1B.values(), pi.CONJUNCION["por_juego_e_estado"],
              ESCENARIOS["A2"].descripcion, ESCENARIOS["L_sint"].descripcion,
              FAMILIAS["cota_martingala_tiempo_fijo"].valor_p,
              FAMILIAS["secuencia_confianza_uniforme_martingala"].valor_p]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS


def test_verificacion_y_constantes_de_la_base_intactas():
    pi.verificar_expediente()
    antes = json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                       sort_keys=True)
    assert len(PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"
    assert json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                      sort_keys=True) == antes
