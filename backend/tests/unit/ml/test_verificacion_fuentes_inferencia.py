"""Tests de la Etapa AE-62, validada: verificacion de fuentes primarias
y condiciones inferenciales pendientes del expediente de inferencia
prospectiva (AE-60/AE-61).

Distinguen tres estados por campo: enunciado comprobado en un preprint
identificado (por la revision atribuida de un auditor externo del
proyecto, no por Claude, cuyo sandbox no accede a los PDF), aplicacion al
repositorio sin verificar y texto no examinado. Comprueban tambien la
premisa de la inversion, la separacion entre Azuma y la inversion, la
exclusion de la familia concreta de apuesta, las decisiones nuevas sin
valor y un contraejemplo exacto de dos pasos: una garantia bajo una nula
mas fuerte no se traslada automaticamente a la nula terminal ni a la nula
sobre T (no refuta el teorema 3 de Choe y Ramdas, cuya nula es otra).

Todo sintetico: solo constantes del expediente y aritmetica exacta. Sin
datos reales, PostgreSQL, entrenamiento ni predicciones reales. No elige
pregunta, familia ni valor y no cambia ningun uso de 1/E."""
from __future__ import annotations

import json
import re
from fractions import Fraction

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52

A = "enunciado_comprobado_en_preprint_identificado"
B = "aplicacion_al_repositorio_sin_verificar"
C = "texto_no_examinado"

CHOE = "choe_ramdas_arxiv_2110_00115v6"
HOWARD = "howard_et_al_arxiv_1810_08240v9"
WSR = "waudby_smith_ramdas_arxiv_2010_09686v7"
RAMDAS = "ramdas_et_al_arxiv_2210_01948v2"

CAMPOS = ("fuente_y_version", "teorema_o_seccion", "estimando", "nula_y_cuantificacion_temporal", "filtracion",
          "acotacion", "predictibilidad", "medias_condicionales", "garantia", "trasladable_al_contrato")

FAMILIAS = {f.id: f for f in pi.FAMILIAS_INFERENCIALES}
ESCENARIOS = {e.id: e for e in pi.ESCENARIOS_ESTUDIO}

_VALOR_P_AZUMA_BASE = (
    "con S = suma sobre W de d_t: p = exp(-S^2 / (2 * 100 * c^2)) si S > 0 y p = 1 si no; solo en n = 100, "
    "no valido si se mira antes; garantia conjunta en el sentido de SENTIDO_DE_LA_GARANTIA_P1B, que "
    "presupone |eps_t| <= c y p_t fijada antes del sorteo")


def _campos(fuente):
    return pi.VERIFICACION_FUENTES_SECUENCIALES[fuente]["campos"]


# ---------------------------------------------------------------------------
# Registro por fuente, version y campo
# ---------------------------------------------------------------------------

def test_estados_de_verificacion_cerrados():
    assert pi.ESTADOS_VERIFICACION_FUENTE == (A, B, C)
    assert pi.CAMPOS_VERIFICACION_TEOREMA == CAMPOS


def test_registro_por_fuente_version_y_revision():
    registro = pi.VERIFICACION_FUENTES_SECUENCIALES
    assert tuple(registro) == (CHOE, HOWARD, WSR, RAMDAS)
    esperado = {
        CHOE: ("arXiv:2110.00115v6", "revision_del_preprint_por_auditor_externo", "auditor_externo_del_proyecto",
               "choe_ramdas_2024"),
        HOWARD: ("arXiv:1810.08240v9", "ficha_arxiv_consultada_por_auditor_externo",
                 "auditor_externo_sin_revision_especifica_del_teorema", "howard_et_al_2021"),
        WSR: ("arXiv:2010.09686v7", "ficha_arxiv_consultada_por_auditor_externo", "auditor_externo_del_proyecto",
              "waudby_smith_ramdas_2024"),
        RAMDAS: ("arXiv:2210.01948v2", "ficha_arxiv_consultada_por_auditor_externo", "sin_revision_de_contenido",
                 "ramdas_et_al_2023"),
    }
    for fuente, (version, identificacion, revision, publicada) in esperado.items():
        entrada = registro[fuente]
        assert set(entrada) == {"version", "identificacion_de_version", "revision", "acceso_desde_sandbox_claude",
                                "referencia_publicada", "campos"}, fuente
        assert entrada["version"] == version
        assert entrada["version"] != "no_indicada"
        assert entrada["identificacion_de_version"] == identificacion
        assert entrada["revision"] == revision
        assert entrada["acceso_desde_sandbox_claude"] == "inaccesible"
        assert entrada["referencia_publicada"] == publicada and publicada in pi.REFERENCIAS
        assert version in entrada["campos"]["fuente_y_version"][1]


def test_campos_completos_con_estado_y_contenido():
    for fuente in pi.VERIFICACION_FUENTES_SECUENCIALES:
        campos = _campos(fuente)
        assert tuple(campos) == CAMPOS, fuente
        for campo, (estado, contenido) in campos.items():
            assert estado in pi.ESTADOS_VERIFICACION_FUENTE, (fuente, campo)
            assert isinstance(contenido, str) and contenido, (fuente, campo)


def test_choe_ramdas_v6_enunciados_atribuidos_y_traslado_sin_verificar():
    campos = _campos(CHOE)
    for campo in CAMPOS[:-1]:
        assert campos[campo][0] == A, campo
    assert campos["trasladable_al_contrato"][0] == B
    assert "filtracion observable F" in campos["filtracion"][1]
    assert "filtracion G" in campos["filtracion"][1]
    for fragmento in ("teorema 1 (p. 13 del PDF)", "teorema 2 (p. 14 del PDF)", "seccion 4.2", "seccion 4.4",
                      "teorema 3", "teorema 4 de Howard"):
        assert fragmento in campos["teorema_o_seccion"][1], fragmento
    assert "para todo t >= 1" in campos["nula_y_cuantificacion_temporal"][1]
    assert "estrictamente propia" in campos["acotacion"][1]
    assert "P(para todo t >= 1: Delta_t en C_t) >= 1 - alfa" in campos["garantia"][1]
    # El recorte del repositorio solo figura como aplicacion por comprobar.
    for campo in CAMPOS[:-1]:
        assert "EPSILON_CLIP" not in campos[campo][1], campo
    traslado = campos["trasladable_al_contrato"][1]
    assert "EPSILON_CLIP" in traslado and "por comprobar" in traslado
    assert "H0w no es la nula terminal ni la nula sobre T" in traslado


def test_howard_teorema_4_sin_revision_especifica():
    campos = _campos(HOWARD)
    assert campos["fuente_y_version"][0] == A
    for campo in CAMPOS[1:]:
        assert campos[campo][0] == C, campo
    assert "teorema 4" in campos["teorema_o_seccion"][1]
    assert "extension" in campos["teorema_o_seccion"][1]


def test_waudby_smith_ramdas_familia_concreta():
    campos = _campos(WSR)
    comprobados = {c for c in CAMPOS if campos[c][0] == A}
    assert comprobados == {"fuente_y_version", "teorema_o_seccion", "medias_condicionales"}
    assert campos["trasladable_al_contrato"][0] == B
    assert "mu constante" in campos["medias_condicionales"][1]
    assert "proposicion 2" in campos["medias_condicionales"][1]
    assert "sin reemplazo" in campos["medias_condicionales"][1]
    assert "familia concreta" in campos["trasladable_al_contrato"][1]
    assert "no se afirma que toda apuesta exija media comun" in campos["trasladable_al_contrato"][1]
    for campo in ("estimando", "nula_y_cuantificacion_temporal", "filtracion", "acotacion", "predictibilidad",
                  "garantia"):
        assert campos[campo][0] == C, campo


def test_ramdas_2023_sin_completar_por_analogia():
    campos = _campos(RAMDAS)
    assert campos["fuente_y_version"][0] == A
    for campo in CAMPOS[1:]:
        assert campos[campo][0] == C, campo


def test_ningun_traslado_al_contrato_en_estado_comprobado():
    for fuente in pi.VERIFICACION_FUENTES_SECUENCIALES:
        assert _campos(fuente)["trasladable_al_contrato"][0] != A, fuente
    clases = {clase for material in pi.MATERIAL_NO_PRIMARIO_CONSULTADO.values() for clase, _ in material}
    assert clases <= {"readme_de_autores", "codigo_de_autores", "tercero_no_usado"}
    assert set(pi.MATERIAL_NO_PRIMARIO_CONSULTADO) == set(pi.VERIFICACION_FUENTES_SECUENCIALES)


# ---------------------------------------------------------------------------
# Premisa de la inversion y separacion de Azuma
# ---------------------------------------------------------------------------

def test_premisa_de_la_inversion_y_valor_p_condicional():
    premisa = pi.PREMISA_DE_LA_INVERSION
    for fragmento in ("P(para todo t >= 1: Delta_t en C_t) >= 1 - nivel", "teoremas 1 y 2 de arXiv:2110.00115v6",
                      "auditor externo", "filtracion G",
                      "falta demostrar que las metricas, cotas, filtracion, predicciones y omisiones"):
        assert fragmento in premisa, fragmento
    valor_p = FAMILIAS["secuencia_confianza_uniforme_martingala"].valor_p
    assert "si se cumplen las condiciones de un teorema de cobertura simultanea (PREMISA_DE_LA_INVERSION)" in valor_p
    assert "solo bajo PREMISA_DE_LA_INVERSION" in valor_p
    assert "como P(existe t" not in valor_p
    assert "no verificada por fuente primaria" not in valor_p
    assert "no verificada por fuente primaria" not in premisa


def test_azuma_separada_de_la_inversion():
    azuma = FAMILIAS["cota_martingala_tiempo_fijo"].valor_p
    assert azuma == _VALOR_P_AZUMA_BASE
    assert "PREMISA_DE_LA_INVERSION" not in azuma
    assert pi.SENTIDO_DE_LA_GARANTIA_P1B == {
        "conjunta": "P(rechazo y evento nulo) <= nivel en cualquier ley, dadas las cotas de incrementos y la "
                    "estructura predictible de la familia; no es garantia condicional dado el evento nulo",
        "clasica": "solo para la clase de leyes en que la nula vale casi seguro",
    }


def test_apuesta_familia_concreta_sin_generalizar():
    apuesta = FAMILIAS["secuencia_confianza_apuesta_media_comun"]
    for fragmento in ("esta familia concreta", "mu constante", "proposicion 2 de arXiv:2010.09686v7",
                      "no se afirma que toda apuesta exija media comun"):
        assert fragmento in apuesta.valor_p, fragmento
    assert apuesta.media == "condicional_comun"
    assert apuesta.aplicable_a_p1b is False and apuesta.preguntas == ()


def test_decisiones_nuevas_sin_valor():
    decisiones = {d.id: d for d in pi.DECISIONES_REQUERIDAS}
    for clave, clase in (("validez_de_1_sobre_sup_e_contra_la_nula_sobre_T", "inferencial"),
                         ("aplicacion_de_condiciones_de_cobertura_al_repositorio", "inferencial"),
                         ("lectura_primaria_pendiente_de_fuentes_secuenciales", "humana")):
        assert decisiones[clave].clase == clase
        assert decisiones[clave].valor is None and decisiones[clave].estado == "sin_decidir"


# ---------------------------------------------------------------------------
# Contraejemplo exacto: sin traslado automatico desde una nula mas fuerte
# ---------------------------------------------------------------------------

def _ley(p1, p2_si_sube, p2_si_baja):
    """Ley de (d_1, d_2) en {-1, 1}^2 con P(d_1 = 1) = p1 y
    P(d_2 = 1 | d_1) dado por los dos ultimos argumentos."""
    return {(d1, d2): (p1 if d1 == 1 else 1 - p1) * (q if d2 == 1 else 1 - q)
            for d1, q in ((1, p2_si_sube), (-1, p2_si_baja)) for d2 in (1, -1)}


def _e_proceso(d1):
    """E_1 = 1 + d_1 y E_2 = E_1: no negativo con d_1 en [-1, 1]."""
    return 1 + d1


def _valor_p(e):
    """p = min(1, 1/E_2); en el evento E_2 = 0 se toma p = 1."""
    return Fraction(1) if e == 0 else min(Fraction(1), Fraction(1, 1) / e)


def test_contraejemplo_traslado_desde_nula_fuerte():
    # Bajo la nula fuerte S (g_1 <= 0 y g_1 + g_2 <= 0), E es supermartingala.
    for g1 in (Fraction(-1), Fraction(-1, 2), Fraction(0)):
        assert 1 + g1 <= 1  # E[E_1 | F_0] = 1 + g_1; E[E_2 | F_1] = E_1
    # Ley L: g_1 = 1/2, g_2 = -1/2, Delta_2 = 0 (nula terminal y nula sobre T = {2}).
    ley = _ley(Fraction(3, 4), Fraction(1, 4), Fraction(1, 4))
    assert sum(ley.values()) == 1
    g1 = sum(pr * d1 for (d1, _), pr in ley.items())
    g2_si_sube = Fraction(1, 4) * 1 + Fraction(3, 4) * -1
    assert g1 == Fraction(1, 2) and g2_si_sube == Fraction(-1, 2)
    delta_2 = (g1 + g2_si_sube) / 2
    assert delta_2 == 0
    esperanza = sum(pr * _e_proceso(d1) for (d1, _), pr in ley.items())
    assert esperanza == Fraction(3, 2)
    assert _valor_p(0) == 1 and _valor_p(2) == Fraction(1, 2)
    rechazo = sum(pr for (d1, _), pr in ley.items() if _valor_p(_e_proceso(d1)) <= Fraction(1, 2))
    assert rechazo == Fraction(3, 4) > Fraction(1, 2)
    # Con T = {1, 2}, L viola la nula sobre T: Delta_1 = g_1 > 0.
    assert g1 > 0


# ---------------------------------------------------------------------------
# Invariantes
# ---------------------------------------------------------------------------

def test_usos_1_sobre_e_familias_y_escenarios_sin_cambios():
    esperado = {
        "remuestreo_iid_media": (("P1a",), "aproximada_por_remuestreo", "comun_estacionaria", "no_aplica",
                                 "no_aplica", "no_aplica", "no_aplica"),
        "remuestreo_bloques_media": (("P1a",), "aproximada_por_remuestreo", "comun_estacionaria", "no_aplica",
                                     "no_aplica", "no_aplica", "no_aplica"),
        "t_media_sin_autocorrelacion": (("P1a",), "asintotica_tiempo_fijo", "comun_estacionaria", "no_aplica",
                                        "no_aplica", "no_aplica", "no_aplica"),
        "t_media_varianza_hac": (("P1a",), "asintotica_tiempo_fijo", "comun_estacionaria", "no_aplica",
                                 "no_aplica", "no_aplica", "no_aplica"),
        "contraste_condicional": (("P2",), "asintotica_tiempo_fijo", "nula_condicional_cero", "no_aplica",
                                  "no_aplica", "no_aplica", "no_aplica"),
        "cota_martingala_tiempo_fijo": (("P1b_unico",), "no_asintotica_tiempo_fijo", "condicional_variable_admitida",
                                        "valor_p_azuma_tiempo_fijo", "no_aplica", "no_aplica", "no_aplica"),
        "secuencia_confianza_uniforme_martingala": (("P1b_unico", "P1b_supervision"), "uniforme_en_el_tiempo",
                                                    "condicional_variable_admitida", "inversion_intervalo_t100",
                                                    "inversion_secuencia_simultanea", "pendiente_de_demostracion",
                                                    "pendiente_de_demostracion"),
        "secuencia_confianza_apuesta_media_comun": ((), "uniforme_en_el_tiempo", "condicional_comun", "no_aplica",
                                                    "no_aplica", "no_aplica", "no_aplica"),
    }
    actual = {f.id: (f.preguntas, f.garantia, f.media, f.modo_p1b_unico, f.modo_p1b_supervision,
                     f.uso_1_sobre_e_nula_terminal, f.uso_1_sobre_e_supervision) for f in pi.FAMILIAS_INFERENCIALES}
    assert actual == esperado
    estados = {
        "A0": ("nula_frontera", "nula_frontera", "nula_frontera", "nula"),
        "A1": ("nula_frontera", "nula_frontera", "segun_T", "alternativa"),
        "A2": ("nula_interior", "nula_interior", "nula_interior", "alternativa"),
        "A3": ("alternativa", "alternativa", "alternativa", "alternativa"),
        "A4": ("nula_frontera", "nula_frontera", "nula_frontera", "nula"),
        "L_unif": ("nula_interior", "nula_interior", "nula_interior", "alternativa"),
        "L_sint": ("nula_frontera", "nula_frontera", "segun_T", "alternativa"),
    }
    for clave, esperados in estados.items():
        e = ESCENARIOS[clave].estado_por_pregunta
        assert tuple(e[p] for p in ("P1a", "P1b_unico", "P1b_supervision", "P2")) == esperados, clave


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def test_textos_nuevos_sin_aprobacion_ni_autorizacion():
    textos = [pi.PREMISA_DE_LA_INVERSION, FAMILIAS["secuencia_confianza_uniforme_martingala"].valor_p,
              FAMILIAS["secuencia_confianza_apuesta_media_comun"].valor_p]
    for fuente, entrada in pi.VERIFICACION_FUENTES_SECUENCIALES.items():
        textos += [fuente, *(v for k, v in entrada.items() if k != "campos")]
        textos += [t for par in entrada["campos"].values() for t in par]
    textos += [t for material in pi.MATERIAL_NO_PRIMARIO_CONSULTADO.values() for par in material for t in par]
    textos += [d.id for d in pi.DECISIONES_REQUERIDAS]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


def test_estado_bloqueos_y_base_intactos():
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    pi.verificar_expediente()
    antes = json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                       sort_keys=True)
    assert len(PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"
    assert json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                      sort_keys=True) == antes
