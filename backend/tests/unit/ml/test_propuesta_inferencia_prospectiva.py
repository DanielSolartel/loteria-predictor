"""Tests de `app/application/ml/propuesta_inferencia_prospectiva.py`
-Etapa AE-60, validada: expediente preparatorio de inferencia
prospectiva. Todo sintetico: solo constantes del expediente y, para la
orientacion por metrica, probabilidades fabricadas para un unico sorteo
construido a mano. Sin datos reales, PostgreSQL, entrenamiento ni
predicciones reales. El expediente no elige pregunta, familia ni valor
alguno y no autoriza ninguna evaluacion."""
from __future__ import annotations

import ast
import dataclasses
import json
import re
from pathlib import Path
from types import MappingProxyType

import pytest

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53, metricas_por_sorteo
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52

ARCHIVO = Path(pi.__file__)
RAIZ_BACKEND = ARCHIVO.resolve().parents[3]
FAMILIAS = {f.id: f for f in pi.FAMILIAS_INFERENCIALES}
PREGUNTAS = {p.id: p for p in pi.PREGUNTAS_INFERENCIALES}
ESCENARIOS = {e.id: e for e in pi.ESCENARIOS_ESTUDIO}


# ---------------------------------------------------------------------------
# Estado del expediente y verificacion de la base
# ---------------------------------------------------------------------------

def test_estado_fijo_sin_eleccion_ni_autorizacion():
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False


def test_verificar_expediente_pasa_con_la_base():
    pi.verificar_expediente()


@pytest.mark.parametrize("cambio", [
    lambda m: m.setattr(pi, "PENDIENTES_BORRADOR_AE52", PENDIENTES_BORRADOR_AE52[:6]),
    lambda m: m.setattr(pi, "ESPECIFICACION_CANDIDATA_AE53", {**ESPECIFICACION_CANDIDATA_AE53, "estado": "otro"}),
    lambda m: m.setattr(pi, "REGLAS_EVALUACION_AE52", {**REGLAS_EVALUACION_AE52, "minimo_sorteos_resueltos_por_juego": 50}),
    lambda m: m.setattr(pi, "REGLAS_EVALUACION_AE52",
                        {**REGLAS_EVALUACION_AE52, "orientacion_diferencia": "estrategia_menos_uniforme"}),
    lambda m: m.setattr(pi, "SUPUESTOS_POR_FAMILIA", MappingProxyType({**dr.SUPUESTOS_POR_FAMILIA, "nueva": ("x",)})),
    lambda m: m.setattr(pi, "SUPUESTOS_POR_FAMILIA", MappingProxyType(
        {**dr.SUPUESTOS_POR_FAMILIA, "remuestreo_iid_media": ("otro_supuesto",)})),
])
def test_verificar_expediente_detecta_divergencias(monkeypatch, cambio):
    cambio(monkeypatch)
    with pytest.raises(pi.ExpedienteDivergenteError):
        pi.verificar_expediente()


# ---------------------------------------------------------------------------
# Preguntas
# ---------------------------------------------------------------------------

def test_preguntas_exactas():
    assert tuple(PREGUNTAS) == ("P1a", "P1b_unico", "P1b_supervision", "P2", "P3")
    assert all(p.id in pi.IDS_PREGUNTAS for p in pi.PREGUNTAS_INFERENCIALES)


def test_p1b_unico_y_supervision_son_distintas():
    unico, supervision = PREGUNTAS["P1b_unico"], PREGUNTAS["P1b_supervision"]
    assert unico.momento == "unico_al_completar_la_ventana"
    assert supervision.momento == "tiempos_declarados"
    assert "para todo t en T" in supervision.h0
    assert "para todo" not in unico.h0
    assert supervision.conflicto_si_tiempo_menor_que_minimo_ae52 is True
    assert unico.conflicto_si_tiempo_menor_que_minimo_ae52 is False


def test_direcciones_y_p3_fuera_del_registro():
    assert PREGUNTAS["P2"].direccion == "no_direccional"
    for p in ("P1a", "P1b_unico", "P1b_supervision"):
        assert PREGUNTAS[p].direccion == "mejora"
    assert PREGUNTAS["P3"].responde_con_registro is False
    assert all(PREGUNTAS[p].responde_con_registro for p in ("P1a", "P1b_unico", "P1b_supervision", "P2"))


def test_condicion_de_igualdad_de_esperanza():
    assert pi.CONDICION_IGUALDAD_ESPERANZA == {
        "vale_si": "ventana_fija_antes_de_los_datos_y_sus_100_objetivos_resueltos",
        "con_omisiones_sustitucion_seleccion_o_parada_dependiente_de_datos": "pendiente",
    }


# ---------------------------------------------------------------------------
# Familias
# ---------------------------------------------------------------------------

def test_familias_de_ae56_coinciden_con_el_catalogo():
    internas = {f.id: f for f in pi.FAMILIAS_INFERENCIALES if not f.fuera_del_catalogo_ae56}
    assert set(internas) == set(dr.SUPUESTOS_POR_FAMILIA)
    for clave, familia in internas.items():
        assert familia.supuestos == dr.SUPUESTOS_POR_FAMILIA[clave]


def test_familias_externas_marcadas():
    externas = {f.id for f in pi.FAMILIAS_INFERENCIALES if f.fuera_del_catalogo_ae56}
    assert externas == {"cota_martingala_tiempo_fijo", "secuencia_confianza_uniforme_martingala",
                        "secuencia_confianza_apuesta_media_comun"}


def test_vocabularios_de_familia_cerrados():
    for familia in pi.FAMILIAS_INFERENCIALES:
        assert familia.garantia in pi.GARANTIAS
        assert familia.media in pi.MEDIAS
        assert familia.modo_p1b_unico in pi.MODOS_P1B_UNICO
        assert familia.uso_1_sobre_e_nula_terminal in pi.USOS_1_SOBRE_E
        assert set(familia.preguntas) <= set(pi.IDS_PREGUNTAS)
        assert set(familia.referencias) <= set(pi.REFERENCIAS)


def test_apuesta_exige_media_condicional_comun_y_no_aplica_a_p1b():
    apuesta = FAMILIAS["secuencia_confianza_apuesta_media_comun"]
    assert apuesta.media == "condicional_comun"
    assert apuesta.aplicable_a_p1b is False
    assert apuesta.preguntas == ()
    assert apuesta.modo_p1b_unico == "no_aplica"


def test_cota_de_azuma_solo_p1b_unico_a_tiempo_fijo():
    azuma = FAMILIAS["cota_martingala_tiempo_fijo"]
    assert azuma.preguntas == ("P1b_unico",)
    assert azuma.garantia == "no_asintotica_tiempo_fijo"
    assert azuma.media == "condicional_variable_admitida"
    assert azuma.modo_p1b_unico == "valor_p_azuma_tiempo_fijo"


def test_secuencia_de_confianza_p1b_unico_solo_por_inversion():
    secuencia = FAMILIAS["secuencia_confianza_uniforme_martingala"]
    assert set(secuencia.preguntas) == {"P1b_unico", "P1b_supervision"}
    assert secuencia.garantia == "uniforme_en_el_tiempo"
    assert secuencia.media == "condicional_variable_admitida"
    assert secuencia.modo_p1b_unico == "inversion_intervalo_t100"
    assert secuencia.uso_1_sobre_e_nula_terminal == "pendiente_de_demostracion"


def test_solo_garantia_uniforme_responde_a_supervision():
    for familia in pi.FAMILIAS_INFERENCIALES:
        if "P1b_supervision" in familia.preguntas:
            assert familia.garantia == "uniforme_en_el_tiempo"


def test_familias_de_media_solo_p1a_y_gw_solo_p2():
    for clave in ("remuestreo_iid_media", "remuestreo_bloques_media", "t_media_sin_autocorrelacion",
                  "t_media_varianza_hac"):
        assert FAMILIAS[clave].preguntas == ("P1a",)
        assert FAMILIAS[clave].media == "comun_estacionaria"
        assert FAMILIAS[clave].modo_p1b_unico == "no_aplica"
    assert FAMILIAS["contraste_condicional"].preguntas == ("P2",)
    assert FAMILIAS["contraste_condicional"].media == "nula_condicional_cero"
    assert not any("P3" in f.preguntas for f in pi.FAMILIAS_INFERENCIALES)


def test_valor_p_de_e_procesos_declara_proceso_tiempo_regla_y_nula():
    for familia in pi.FAMILIAS_INFERENCIALES:
        texto = familia.valor_p
        assert texto
        if "1/E" in texto:
            for requisito in ("proceso", "tiempo", "regla", "nula"):
                assert requisito in texto, (familia.id, requisito)


# ---------------------------------------------------------------------------
# Escenarios del estudio posterior
# ---------------------------------------------------------------------------

def test_escenarios_exactos_y_vocabulario():
    assert tuple(ESCENARIOS) == ("A0", "A1", "A2", "A3", "A4", "L_unif", "L_sint")
    for escenario in pi.ESCENARIOS_ESTUDIO:
        assert set(escenario.estado_por_pregunta) == {"P1a", "P1b_unico", "P1b_supervision", "P2"}
        assert set(escenario.estado_por_pregunta.values()) <= set(pi.ESTADOS_NULA)
        assert escenario.tipo in pi.TIPOS_ESCENARIO
        assert escenario.realizable_con_sorteos_uniformes in pi.REALIZABILIDAD


def test_a1_nulo_para_p1b_unico_y_segun_t_para_supervision():
    """v2: con T = {100} la nula de supervision coincide con la terminal y
    A1 es nulo; con tiempos intermedios de prefijo positivo es alternativa."""
    estados = ESCENARIOS["A1"].estado_por_pregunta
    assert estados["P1b_unico"] == "nula_frontera"
    assert estados["P1b_supervision"] == "segun_T"


def test_nulas_de_p2_solo_con_ventaja_condicional_nula():
    nulos_p2 = {e.id for e in pi.ESCENARIOS_ESTUDIO if e.estado_por_pregunta["P2"] == "nula"}
    assert nulos_p2 == {"A0", "A4"}
    for clave in ("A2", "L_unif"):
        estados = ESCENARIOS[clave].estado_por_pregunta
        assert estados["P2"] == "alternativa"
        assert estados["P1a"] == estados["P1b_unico"] == estados["P1b_supervision"] == "nula_interior"


def test_realizabilidad_con_sorteos_uniformes():
    realizables = {e.id: e.realizable_con_sorteos_uniformes for e in pi.ESCENARIOS_ESTUDIO}
    assert {k for k, v in realizables.items() if v == "si"} == {"A2", "L_unif"}
    assert {k for k, v in realizables.items() if v == "solo_degenerado"} == {"A0"}
    assert realizables["L_sint"] == "no"
    assert ESCENARIOS["L_sint"].tipo == "metricas_por_sorteo_mecanismo_sintetico_no_uniforme"


def test_error_tipo_i_solo_en_escenarios_nulos_de_cada_pregunta():
    for pregunta in ("P1a", "P1b_unico", "P1b_supervision", "P2"):
        nulos = pi.escenarios_nulos(pregunta)
        assert all(ESCENARIOS[e].estado_por_pregunta[pregunta] != "alternativa" for e in nulos)
    assert "L_unif" not in pi.escenarios_nulos("P2")
    assert "A1" not in pi.escenarios_nulos("P1b_supervision")
    with pytest.raises(pi.ExpedienteDivergenteError):
        pi.escenarios_nulos("P3")


# ---------------------------------------------------------------------------
# Orientacion por metrica y conjuncion
# ---------------------------------------------------------------------------

def test_orientacion_de_mejora_por_metrica():
    assert pi.ORIENTACION_MEJORA_POR_METRICA == {"log_loss": "positiva", "brier_score": "positiva",
                                                 "precision_en_5": "negativa"}


def test_orientacion_coherente_con_metricas_por_sorteo():
    numeros = [10, 11, 12, 13, 14]
    probabilidades = [0.9 if n in numeros else 0.01 for n in range(1, 44)]
    diferencias = metricas_por_sorteo("BALOTO", 2714, probabilidades, numeros).diferencias
    signos = {m: ("positiva" if v > 0 else "negativa") for m, v in diferencias.items()}
    assert signos == dict(pi.ORIENTACION_MEJORA_POR_METRICA)


def test_conjuncion_y_formas_entre_juegos():
    assert pi.CONJUNCION == {
        "por_juego_valor_p": "maximo_de_p_log_loss_y_p_brier",
        "por_juego_e": "minimo_de_e_log_loss_y_e_brier",
        "por_juego_e_estado": "condicionado_a_e_valores_validos_por_metrica_hoy_pendientes",
        "entre_juegos_ambos": "interseccion_union_maximo_de_p_juego",
        "entre_juegos_al_menos_uno": "holm_sobre_p_juego",
        "solo_informes_por_juego": "sin_control_del_error_familiar",
        "secundaria": "fuera_de_la_conjuncion_mejora_negativa",
    }


# ---------------------------------------------------------------------------
# Sin valores de decision
# ---------------------------------------------------------------------------

def test_decisiones_inferenciales_abiertas_sin_valor():
    assert set(pi.DECISIONES_INFERENCIALES_ABIERTAS) == {
        "alfa", "longitud_bloque", "ancho_banda", "efecto_minimo", "potencia_objetivo",
        "correccion_multiplicidad", "tiempos_supervision", "cota",
    }
    for decision in pi.DECISIONES_INFERENCIALES_ABIERTAS.values():
        assert decision.valor is None
        assert decision.estado == "sin_decidir"


def test_parametros_a_fijar_son_solo_nombres():
    for familia in pi.FAMILIAS_INFERENCIALES:
        assert isinstance(familia.parametros_a_fijar, tuple)
        assert all(isinstance(p, str) and re.fullmatch(r"[a-z_0-9]+", p) for p in familia.parametros_a_fijar)


def test_familias_y_preguntas_sin_campo_de_valor_elegido():
    for clase in (pi.Familia, pi.Pregunta, pi.Escenario):
        nombres = {f.name for f in dataclasses.fields(clase)}
        assert not nombres & {"valor", "valor_elegido", "alfa", "longitud_bloque", "ancho_banda", "efecto_minimo",
                              "potencia", "correccion"}


def test_decisiones_requeridas_por_clase():
    clases = {d.clase for d in pi.DECISIONES_REQUERIDAS}
    assert clases == {"humana", "inferencial", "externa"}
    for decision in pi.DECISIONES_REQUERIDAS:
        assert decision.valor is None and decision.estado == "sin_decidir"
    externas = {d.id for d in pi.DECISIONES_REQUERIDAS if d.clase == "externa"}
    assert {"mecanismo_de_sellado_temporal_externo", "autorizacion_ae41_para_prerregistro",
            "aprobacion_de_la_estrategia_a_congelar"} <= externas


def test_criterios_de_detencion():
    assert [c.split(":")[0] for c in pi.CRITERIOS_DE_DETENCION] == ["a", "b", "c", "d", "e"]


# ---------------------------------------------------------------------------
# Vocabulario cerrado: sin aprobacion, GO, cumplimiento ni desbloqueo
# ---------------------------------------------------------------------------

_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida"}


def _textos(valor):
    if dataclasses.is_dataclass(valor):
        for campo in dataclasses.fields(valor):
            yield from _textos(getattr(valor, campo.name))
    elif isinstance(valor, (dict, MappingProxyType)):
        for clave, contenido in valor.items():
            yield from _textos(clave)
            yield from _textos(contenido)
    elif isinstance(valor, (tuple, list)):
        for elemento in valor:
            yield from _textos(elemento)
    elif isinstance(valor, str):
        yield valor


def test_ningun_texto_del_expediente_aprueba_ni_autoriza():
    constantes = (pi.PREGUNTAS_INFERENCIALES, pi.FAMILIAS_INFERENCIALES, pi.ESCENARIOS_ESTUDIO,
                  pi.DECISIONES_INFERENCIALES_ABIERTAS, pi.DECISIONES_REQUERIDAS, pi.CRITERIOS_DE_DETENCION,
                  pi.CONJUNCION, pi.ORIENTACION_MEJORA_POR_METRICA, pi.CONDICION_IGUALDAD_ESPERANZA,
                  pi.ESTADO_EXPEDIENTE)
    palabras = {p.lower() for texto in _textos(constantes) for p in re.split(r"[^A-Za-zÁÉÍÓÚáéíóúñÑ]+", texto) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


# ---------------------------------------------------------------------------
# Referencias, inmutabilidad, invariantes y aislamiento
# ---------------------------------------------------------------------------

def test_referencias_con_identificador_verificable():
    for clave, texto in pi.REFERENCIAS.items():
        assert re.search(r"doi:10\.\d{4,9}/\S+|jstor\.org/stable/\d+|RFC 3161", texto), clave


def test_inmutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        pi.FAMILIAS_INFERENCIALES[0].garantia = "otra"
    with pytest.raises(TypeError):
        pi.CONJUNCION["secundaria"] = "otra"
    with pytest.raises(TypeError):
        pi.ESCENARIOS_ESTUDIO[0].estado_por_pregunta["P2"] = "nula"


def test_constantes_de_la_base_intactas():
    antes = json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                       sort_keys=True)
    pi.verificar_expediente()
    assert json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                      sort_keys=True) == antes
    assert len(PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"


def test_modulo_puro_y_aislado():
    arbol = ast.parse(ARCHIVO.read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add(nodo.module or "")
    assert modulos <= {"__future__", "dataclasses", "types", "app.application.ml.diseno_regla_prospectiva",
                       "app.application.ml.especificacion_evaluacion_prospectiva",
                       "app.application.ml.registro_prospectivo"}, modulos


def test_no_expuesto_en_la_web_ni_en_scripts():
    raiz = RAIZ_BACKEND / "app"
    rutas = [*(raiz / "api").rglob("*.py"), raiz / "main.py", *(raiz / "templates").rglob("*.html"),
             *(RAIZ_BACKEND / "scripts").rglob("*.py")]
    for ruta in rutas:
        assert "propuesta_inferencia_prospectiva" not in ruta.read_text(encoding="utf-8"), ruta


# ---------------------------------------------------------------------------
# Regresiones v2: supervision sin atribuir a Ville una garantia no demostrada
# ---------------------------------------------------------------------------

def test_v2_supervision_restringida_a_la_ventana():
    supervision = PREGUNTAS["P1b_supervision"]
    assert "T contenido en la ventana de 100 objetivos" in supervision.h0
    assert "extension del horizonte decidida por el operador" in supervision.relacion_ae52


def test_v2_supervision_por_inversion_de_la_secuencia_simultanea():
    secuencia = FAMILIAS["secuencia_confianza_uniforme_martingala"]
    assert secuencia.modo_p1b_supervision == "inversion_secuencia_simultanea"
    assert secuencia.uso_1_sobre_e_supervision == "pendiente_de_demostracion"
    assert secuencia.uso_1_sobre_e_nula_terminal == "pendiente_de_demostracion"
    assert "Ville" not in secuencia.valor_p
    assert "inf C_t > 0 para algun t de T" in secuencia.valor_p


def test_v2_modos_de_supervision_cerrados():
    for familia in pi.FAMILIAS_INFERENCIALES:
        assert familia.modo_p1b_supervision in pi.MODOS_P1B_SUPERVISION
        assert familia.uso_1_sobre_e_supervision in pi.USOS_1_SOBRE_E
        if "P1b_supervision" in familia.preguntas:
            assert familia.modo_p1b_supervision == "inversion_secuencia_simultanea"
        else:
            assert familia.modo_p1b_supervision == "no_aplica"


def test_v2_ninguna_familia_declara_valido_1_sobre_e():
    for familia in pi.FAMILIAS_INFERENCIALES:
        assert "Ville" not in familia.valor_p
        assert not re.search(r"1/(sup )?E\S*[^;]*\bvalid", familia.valor_p), familia.id


def test_v2_estado_de_a1_y_l_sint_en_supervision_depende_de_t():
    assert ESCENARIOS["A1"].estado_por_pregunta["P1b_supervision"] == "segun_T"
    assert ESCENARIOS["L_sint"].estado_por_pregunta["P1b_supervision"] == "segun_T"
    assert pi.escenarios_nulos("P1b_supervision") == ("A0", "A2", "A4", "L_unif")


_PENDIENTES_ALTERADOS = ("otro",) + PENDIENTES_BORRADOR_AE52[1:]


def _especificacion_con(cambio):
    especificacion = json.loads(json.dumps(ESPECIFICACION_CANDIDATA_AE53))
    cambio(especificacion)
    return especificacion


@pytest.mark.parametrize("nombre, valor", [
    ("PENDIENTES_BORRADOR_AE52", _PENDIENTES_ALTERADOS),
    ("PENDIENTES_BORRADOR_AE52", list(PENDIENTES_BORRADOR_AE52)),
    ("ESPECIFICACION_CANDIDATA_AE53",
     _especificacion_con(lambda e: e["propuestas"]["omisiones"].__setitem__("estado", "otro"))),
    ("ESPECIFICACION_CANDIDATA_AE53",
     _especificacion_con(lambda e: e["propuestas"]["horizonte"]["valor_propuesto"].__setitem__("objetivos", 120))),
    ("ESPECIFICACION_CANDIDATA_AE53",
     _especificacion_con(lambda e: e["pendientes"]["nivel_y_umbral"].__setitem__("valor", 0.05))),
    ("ESPECIFICACION_CANDIDATA_AE53", _especificacion_con(lambda e: e["pendientes"].pop("efecto_minimo"))),
    ("ESPECIFICACION_CANDIDATA_AE53", _especificacion_con(lambda e: e.pop("propuestas"))),
    ("ESPECIFICACION_CANDIDATA_AE53", None),
    ("ESPECIFICACION_CANDIDATA_AE53", []),
    ("REGLAS_EVALUACION_AE52", None),
    ("REGLAS_EVALUACION_AE52", "reglas"),
    ("SUPUESTOS_POR_FAMILIA", None),
    ("SUPUESTOS_POR_FAMILIA", ["remuestreo_iid_media"]),
])
def test_v2_verificar_expediente_detecta_contenido_y_tipos(monkeypatch, nombre, valor):
    monkeypatch.setattr(pi, nombre, valor)
    with pytest.raises(pi.ExpedienteDivergenteError):
        pi.verificar_expediente()
