"""
Expediente preparatorio de inferencia prospectiva -Etapa AE-60,
validada (solo el expediente preparatorio y sus pruebas; no elige
pregunta, metodo ni valor alguno y deja pendientes las formulas con 1/E).

Formaliza, sin elegir nada, que preguntas inferenciales caben con los
contratos de AE-52 a AE-59 y que familias de metodos responderian a cada
una, con su garantia, lo que exigen de la media, como se obtendria su
valor p y que evidencia falta. Tambien especifica los escenarios de un
estudio sintetico POSTERIOR, las decisiones requeridas y los criterios
para detenerse sin eleccion.

No contiene ningun valor de decision (alfa, longitud de bloque, ancho de
banda, efecto minimo, potencia, correccion de multiplicidad, tiempos de
supervision ni cota): esas decisiones figuran sin valor y sin decidir.
No selecciona pregunta ni familia, no cierra
`regla_estadistica_de_decision` ni ningun pendiente de AE-52, no toca la
especificacion candidata de AE-53, no modifica el catalogo de AE-56 y no
cambia el NO-GO de AE-39 ni los bloqueos de AE-41/AE-46. La validez de un
metodo secuencial no altera el minimo ni la prohibicion de agregados
antes del minimo fijados por AE-52.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml.diseno_regla_prospectiva import SUPUESTOS_POR_FAMILIA
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52

ESTADO_EXPEDIENTE = "expediente_sin_eleccion"
AUTORIZA_EVALUACION = False

IDS_PREGUNTAS = ("P1a", "P1b_unico", "P1b_supervision", "P2", "P3")
GARANTIAS = ("aproximada_por_remuestreo", "asintotica_tiempo_fijo", "no_asintotica_tiempo_fijo",
             "uniforme_en_el_tiempo")
MEDIAS = ("comun_estacionaria", "condicional_comun", "condicional_variable_admitida", "nula_condicional_cero")
MODOS_P1B_UNICO = ("inversion_intervalo_t100", "no_aplica", "valor_p_azuma_tiempo_fijo")
MODOS_P1B_SUPERVISION = ("inversion_secuencia_simultanea", "no_aplica")
USOS_1_SOBRE_E = ("no_aplica", "pendiente_de_demostracion")
ESTADOS_NULA = ("alternativa", "nula", "nula_frontera", "nula_interior", "segun_T")
TIPOS_ESCENARIO = ("abstracto", "metricas_por_sorteo_mecanismo_sintetico_no_uniforme",
                   "metricas_por_sorteo_sorteos_uniformes")
REALIZABILIDAD = ("no", "si", "solo_degenerado")


class ExpedienteDivergenteError(ValueError):
    """La base de AE-52, AE-53 o AE-56 no es la que el expediente supone."""


# ---------------------------------------------------------------------------
# Preguntas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Pregunta:
    id: str
    estimando: str
    h0: str
    h1: str
    direccion: str
    momento: str
    relacion_ae52: str
    conflicto_si_tiempo_menor_que_minimo_ae52: bool
    responde_con_registro: bool


PREGUNTAS_INFERENCIALES = (
    Pregunta("P1a", "mu_W = (1/100) suma sobre W de E[d_t]", "mu_W <= 0", "mu_W > 0", "mejora",
             "unico_al_completar_la_ventana", "compatible con un analisis unico tras el minimo", False, True),
    Pregunta("P1b_unico", "Delta_100 = (1/100) suma sobre W de g_t, con g_t = E[d_t | F_(t-1)]",
             "Delta_100 <= 0 (nula terminal; admite prefijos positivos)", "Delta_100 > 0", "mejora",
             "unico_al_completar_la_ventana", "compatible con un analisis unico tras el minimo", False, True),
    Pregunta("P1b_supervision", "Delta_t en los tiempos declarados T, con T contenido en la ventana de 100 objetivos",
             "Delta_t <= 0 para todo t en T, con T contenido en la ventana de 100 objetivos (nula sobre T; no "
             "restringe los prefijos fuera de T)", "existe t en T con Delta_t > 0", "mejora", "tiempos_declarados",
             "conflicto con ningun agregado antes del minimo si algun t de T tiene menos de 100 resueltos, asi que "
             "con las reglas vigentes solo cabe T = {100}; tiempos mayores que 100 requieren una extension del "
             "horizonte decidida por el operador", True, True),
    Pregunta("P2", "E[d_t | F_(t-1)] para cada t de W", "E[d_t | F_(t-1)] = 0 para toda t de W",
             "E[d_t | F_(t-1)] distinto de 0 en alguna t", "no_direccional", "unico_al_completar_la_ventana",
             "pregunta distinta; rechazarla no indica mejora", False, True),
    Pregunta("P3", "mecanismo de sorteo", "sorteo uniforme e independiente", "otro mecanismo", "no_aplica",
             "no_aplica", "no se responde con el registro de estrategias", False, False),
)

SENTIDO_DE_LA_GARANTIA_P1B = MappingProxyType({
    "conjunta": "P(rechazo y evento nulo) <= nivel en cualquier ley, dadas las cotas de incrementos y la "
                "estructura predictible de la familia; no es garantia condicional dado el evento nulo",
    "clasica": "solo para la clase de leyes en que la nula vale casi seguro",
})
"""AE-61: Delta_100 y Delta_t dependen de la trayectoria. Con incrementos
acotados (|eps_t| <= c fijada a priori) y p_t fijada antes de cada sorteo,
Azuma y la inversion dan la cota conjunta; la lectura clasica solo vale
para la clase de leyes en que la nula se cumple casi seguro."""

CONDICION_IGUALDAD_ESPERANZA = MappingProxyType({
    "vale_si": "ventana_fija_antes_de_los_datos_y_sus_100_objetivos_resueltos",
    "con_omisiones_sustitucion_seleccion_o_parada_dependiente_de_datos": "pendiente",
})
"""Cuando E[Delta_100] = mu_W (ley de esperanzas iteradas)."""


# ---------------------------------------------------------------------------
# Familias
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Familia:
    id: str
    fuera_del_catalogo_ae56: bool
    preguntas: tuple[str, ...]
    garantia: str
    media: str
    supuestos: tuple[str, ...]
    valor_p: str
    parametros_a_fijar: tuple[str, ...]
    evidencia_faltante: tuple[str, ...]
    aplicable_a_p1b: bool
    modo_p1b_unico: str
    uso_1_sobre_e_nula_terminal: str
    referencias: tuple[str, ...]
    modo_p1b_supervision: str = "no_aplica"
    uso_1_sobre_e_supervision: str = "no_aplica"


FAMILIAS_INFERENCIALES = (
    Familia("remuestreo_iid_media", False, ("P1a",), "aproximada_por_remuestreo", "comun_estacionaria",
            ("independencia_de_d_t",),
            "proporcion de medias bootstrap centradas en la media observada que son >= la media observada, "
            "a tiempo fijo",
            ("replicas", "semilla"), ("independencia de d_t, violada si g_t persiste",), False, "no_aplica",
            "no_aplica", ()),
    Familia("remuestreo_bloques_media", False, ("P1a",), "aproximada_por_remuestreo", "comun_estacionaria",
            ("dependencia_debil", "estacionariedad", "memoria_menor_que_longitud_bloque"),
            "como la anterior sobre remuestras de bloques, a tiempo fijo",
            ("longitud_bloque", "variante", "replicas", "semilla"),
            ("memoria de g_t bajo la estrategia congelada", "pocos bloques con 100 sorteos"), False, "no_aplica",
            "no_aplica", ("kunsch_1989", "politis_romano_1994")),
    Familia("t_media_sin_autocorrelacion", False, ("P1a",), "asintotica_tiempo_fijo", "comun_estacionaria",
            ("sin_autocorrelacion_de_d_t",), "1 - F_t(n-1)(estadistico), a tiempo fijo", (),
            ("ausencia de autocorrelacion de d_t",), False, "no_aplica", "no_aplica",
            ("diebold_mariano_1995", "harvey_leybourne_newbold_1997")),
    Familia("t_media_varianza_hac", False, ("P1a",), "asintotica_tiempo_fijo", "comun_estacionaria",
            ("ancho_banda_adecuado", "estacionariedad_en_covarianza"),
            "normal o valores criticos de teoria fixed-b segun se declare, a tiempo fijo", ("kernel", "ancho_banda"),
            ("estacionariedad en covarianza", "ancho de banda fijado sin mirar los datos"), False, "no_aplica",
            "no_aplica", ("newey_west_1987", "kiefer_vogelsang_2005")),
    Familia("contraste_condicional", False, ("P2",), "asintotica_tiempo_fijo", "nula_condicional_cero",
            ("aproximacion_asintotica", "memoria_limitada_o_parametros_congelados"),
            "1 - F_chi2(q)(estadistico), a tiempo fijo", ("funcion_prueba",),
            ("una pregunta humana que quiera P2",
             "compatibilidad de la frecuencia acumulada de AE-36 con la memoria limitada"),
            False, "no_aplica", "no_aplica", ("giacomini_white_2006",)),
    Familia("cota_martingala_tiempo_fijo", True, ("P1b_unico",), "no_asintotica_tiempo_fijo",
            "condicional_variable_admitida", ("puntuaciones_acotadas", "p_t_fijada_antes_del_sorteo"),
            "con S = suma sobre W de d_t: p = exp(-S^2 / (2 * 100 * c^2)) si S > 0 y p = 1 si no; solo en n = 100, "
            "no valido si se mira antes; garantia conjunta en el sentido de SENTIDO_DE_LA_GARANTIA_P1B, que "
            "presupone |eps_t| <= c y p_t fijada antes del sorteo",
            ("cota",), ("potencia con la cota real de Log Loss recortado", "anterioridad de p_t"), True,
            "valor_p_azuma_tiempo_fijo", "no_aplica", ("azuma_1967",)),
    Familia("secuencia_confianza_uniforme_martingala", True, ("P1b_unico", "P1b_supervision"),
            "uniforme_en_el_tiempo", "condicional_variable_admitida",
            ("puntuaciones_acotadas", "p_t_fijada_antes_del_sorteo"),
            "supervision: inversion de la secuencia simultanea, se rechaza si inf C_t > 0 para algun t de T; como "
            "P(existe t con Delta_t fuera de C_t) <= nivel, bajo la nula sobre T el rechazo exige que algun Delta_t "
            "quede fuera de C_t; p = menor nivel con inf C_t > 0 para algun t de T si la familia es monotona en el "
            "nivel; unico: inversion del intervalo C_100, p = menor nivel con inf C_100 > 0 si la familia esta anidada "
            "en el nivel (condicion suficiente para esta formula); ambas con garantia conjunta en el sentido de "
            "SENTIDO_DE_LA_GARANTIA_P1B; las formulas con "
            "1/sup E_t sobre T y con 1/E_100 (proceso E_t, tiempos, regla de supervision y nula declarados) quedan "
            "pendientes de demostracion bajo la nula sobre T y la terminal, "
            "porque un proceso construido desde el inicio puede exigir restricciones en prefijos fuera de T",
            ("variante", "cota", "tiempos_supervision", "regla_de_parada"),
            ("condiciones exactas en el texto completo", "potencia", "incorporacion al catalogo por decision humana",
             "anterioridad de p_t", "conflicto con el minimo de AE-52 si hay tiempos anteriores"),
            True, "inversion_intervalo_t100", "pendiente_de_demostracion",
            ("howard_et_al_2021", "choe_ramdas_2024", "ramdas_et_al_2023"),
            "inversion_secuencia_simultanea", "pendiente_de_demostracion"),
    Familia("secuencia_confianza_apuesta_media_comun", True, (), "uniforme_en_el_tiempo", "condicional_comun",
            ("media_condicional_comun", "puntuaciones_acotadas"),
            "igual que la anterior, solo bajo su supuesto de media condicional comun; no aplicable con g_t variable",
            ("variante", "cota"), ("extension verificada a medias condicionales variables",), False, "no_aplica",
            "no_aplica", ("waudby_smith_ramdas_2024",)),
)


# ---------------------------------------------------------------------------
# Escenarios del estudio sintetico posterior
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Escenario:
    id: str
    descripcion: str
    tipo: str
    estado_por_pregunta: MappingProxyType
    realizable_con_sorteos_uniformes: str


def _escenario(id_, descripcion, tipo, p1a, p1b_unico, p1b_supervision, p2, realizable):
    return Escenario(id_, descripcion, tipo, MappingProxyType({
        "P1a": p1a, "P1b_unico": p1b_unico, "P1b_supervision": p1b_supervision, "P2": p2,
    }), realizable)


ESCENARIOS_ESTUDIO = (
    _escenario("A0", "g_t = 0 y eps_t diferencia de martingala", "abstracto",
               "nula_frontera", "nula_frontera", "nula_frontera", "nula", "solo_degenerado"),
    _escenario("A1", "g_t determinista y persistente con suma cero en W y prefijos positivos", "abstracto",
               "nula_frontera", "nula_frontera", "segun_T", "alternativa", "no"),
    _escenario("A2", "g_t <= 0 en toda t de W, con g_t < 0 en alguna t", "abstracto",
               "nula_interior", "nula_interior", "nula_interior", "alternativa", "si"),
    _escenario("A3", "g_t = delta > 0 con delta dado por el operador", "abstracto",
               "alternativa", "alternativa", "alternativa", "alternativa", "no"),
    _escenario("A4", "g_t = 0 con eps_t heterocedastico", "abstracto",
               "nula_frontera", "nula_frontera", "nula_frontera", "nula", "no"),
    _escenario("L_unif", "sorteos uniformes sinteticos con estrategia no uniforme", "metricas_por_sorteo_sorteos_uniformes",
               "nula_interior", "nula_interior", "nula_interior", "alternativa", "si"),
    _escenario("L_sint", "mecanismo sintetico no uniforme: p_t y q_t fijadas de antemano, elegidas para que la "
               "suma exacta cero de g_t en W se cumpla, con g_t calculada con las marginales (condicion suficiente "
               "para la frontera; no se afirma que sea necesaria)",
               "metricas_por_sorteo_mecanismo_sintetico_no_uniforme",
               "nula_frontera", "nula_frontera", "segun_T", "alternativa", "no"),
)
"""Estado de cada nula por pregunta. `segun_T`: la nula de supervision es
verdadera o falsa segun los tiempos T declarados (con T = {100} coincide
con la terminal). Con sorteos uniformes, g_t <= 0 y la
frontera no degenerada de P1 no es realizable; L_sint no dice nada del
mecanismo real."""


def escenarios_nulos(pregunta: str) -> tuple[str, ...]:
    """Escenarios donde la nula de `pregunta` es verdadera para cualquier
    eleccion de T: los unicos en los que se calcularia su error tipo I."""
    if pregunta not in ("P1a", "P1b_unico", "P1b_supervision", "P2"):
        raise ExpedienteDivergenteError(f"Pregunta sin escenarios de estudio: {pregunta!r}")
    return tuple(e.id for e in ESCENARIOS_ESTUDIO
                 if e.estado_por_pregunta[pregunta] in ("nula", "nula_frontera", "nula_interior"))


# ---------------------------------------------------------------------------
# Orientacion, conjuncion, decisiones y criterios
# ---------------------------------------------------------------------------

ORIENTACION_MEJORA_POR_METRICA = MappingProxyType({
    "log_loss": "positiva", "brier_score": "positiva", "precision_en_5": "negativa",
})
"""Signo de d = uniforme - estrategia que indica mejora: en perdidas es
positivo; en la ganancia P@5 es negativo."""

CONJUNCION = MappingProxyType({
    "por_juego_valor_p": "maximo_de_p_log_loss_y_p_brier",
    "por_juego_e": "minimo_de_e_log_loss_y_e_brier",
    "por_juego_e_estado": "condicionado_a_e_valores_validos_por_metrica_hoy_pendientes",
    "entre_juegos_ambos": "interseccion_union_maximo_de_p_juego",
    "entre_juegos_al_menos_uno": "holm_sobre_p_juego",
    "solo_informes_por_juego": "sin_control_del_error_familiar",
    "secundaria": "fuera_de_la_conjuncion_mejora_negativa",
})


@dataclass(frozen=True)
class Decision:
    id: str
    clase: str
    valor: None = None
    estado: str = "sin_decidir"


DECISIONES_INFERENCIALES_ABIERTAS = MappingProxyType({
    "alfa": Decision("alfa", "humana"),
    "longitud_bloque": Decision("longitud_bloque", "inferencial"),
    "ancho_banda": Decision("ancho_banda", "inferencial"),
    "efecto_minimo": Decision("efecto_minimo", "humana"),
    "potencia_objetivo": Decision("potencia_objetivo", "humana"),
    "correccion_multiplicidad": Decision("correccion_multiplicidad", "humana"),
    "tiempos_supervision": Decision("tiempos_supervision", "humana"),
    "cota": Decision("cota", "inferencial"),
})

DECISIONES_REQUERIDAS = (
    *(Decision(d, "humana") for d in (
        "pregunta", "alfa", "efecto_minimo", "forma_de_la_afirmacion_entre_juegos", "correccion_multiplicidad",
        "potencia_objetivo", "momento_y_tiempos_de_analisis", "tratamiento_de_omisiones",
        "incorporacion_de_familias_externas", "papel_y_direccion_de_la_secundaria", "criterios_del_estudio",
        "multiplicidad_entre_preguntas_o_familias")),
    *(Decision(d, "inferencial") for d in (
        "memoria_y_estacionariedad_de_g_t", "potencia_de_familias_de_martingala",
        "condiciones_exactas_de_las_secuencias_de_confianza", "validez_de_1_sobre_e_contra_la_nula_terminal",
        "reentrenamiento_e_incertidumbre_de_estimacion")),
    *(Decision(d, "externa") for d in (
        "mecanismo_de_sellado_temporal_externo", "autorizacion_ae41_para_prerregistro",
        "aprobacion_de_la_estrategia_a_congelar", "tramo_de_entrenamiento", "contrato_de_inferencia_prospectiva")),
)

CRITERIOS_DE_DETENCION = (
    "a: faltan decisiones requeridas antes del estudio",
    "b: ningun par pregunta y familia cumple los criterios del operador en todos sus escenarios nulos",
    "c: el unico par que los cumple usa una familia fuera del catalogo de AE-56 sin decision de incorporarla",
    "d: la pregunta es P1b_supervision con tiempos anteriores a 100 resueltos",
    "e: no hay un mecanismo de sellado temporal externo; la candidata solo se documenta como condicional",
)

REFERENCIAS = MappingProxyType({
    "diebold_mariano_1995": "Diebold y Mariano (1995), JBES 13(3):253-263, doi:10.1080/07350015.1995.10524599",
    "diebold_2015": "Diebold (2015), JBES 33(1):1, doi:10.1080/07350015.2014.983236",
    "harvey_leybourne_newbold_1997": "Harvey, Leybourne y Newbold (1997), IJF 13(2):281-291, "
                                     "doi:10.1016/S0169-2070(96)00719-4",
    "giacomini_white_2006": "Giacomini y White (2006), Econometrica 74(6):1545-1578, "
                            "doi:10.1111/j.1468-0262.2006.00718.x",
    "west_1996": "West (1996), Econometrica 64(5):1067-1084, jstor.org/stable/2171956",
    "newey_west_1987": "Newey y West (1987), Econometrica 55(3):703-708, jstor.org/stable/1913610",
    "kiefer_vogelsang_2005": "Kiefer y Vogelsang (2005), Econometric Theory 21(6):1130-1164, "
                             "doi:10.1017/S0266466605050565",
    "kunsch_1989": "Kunsch (1989), Ann. Statist. 17(3):1217-1241, doi:10.1214/aos/1176347265",
    "politis_romano_1994": "Politis y Romano (1994), JASA 89(428):1303-1313, doi:10.1080/01621459.1994.10476870",
    "gneiting_raftery_2007": "Gneiting y Raftery (2007), JASA 102(477):359-378, doi:10.1198/016214506000001437",
    "berger_1982": "Berger (1982), Technometrics 24(4):295-300, doi:10.2307/1267823",
    "holm_1979": "Holm (1979), Scand. J. Statist. 6(2):65-70, jstor.org/stable/4615733",
    "azuma_1967": "Azuma (1967), Tohoku Math. J. 19(3):357-367, doi:10.2748/tmj/1178243286",
    "howard_et_al_2021": "Howard, Ramdas, McAuliffe y Sekhon (2021), Ann. Statist. 49(2):1055-1080, "
                         "doi:10.1214/20-AOS1991",
    "choe_ramdas_2024": "Choe y Ramdas (2024), Operations Research 72(4):1368-1387, doi:10.1287/opre.2021.0792",
    "waudby_smith_ramdas_2024": "Waudby-Smith y Ramdas (2024), JRSS B 86(1):1-27, doi:10.1093/jrsssb/qkad009",
    "ramdas_et_al_2023": "Ramdas, Grunwald, Vovk y Shafer (2023), Statistical Science 38(4):576-601, "
                         "doi:10.1214/23-STS894",
    "lan_demets_1983": "Lan y DeMets (1983), Biometrika 70(3):659-663, doi:10.1093/biomet/70.3.659",
    "rfc_3161": "Adams, Cain, Pinkas y Zuccherato (2001), RFC 3161, IETF",
})


# ---------------------------------------------------------------------------
# Verificacion explicita de la base
# ---------------------------------------------------------------------------

_PENDIENTES_AE52_ESPERADOS = (
    "aprobacion_de_la_estrategia_a_congelar", "tramo_de_entrenamiento", "contrato_de_inferencia_prospectiva",
    "autorizacion_ae41_para_prerregistro", "corte_temporal_por_juego", "regla_estadistica_de_decision",
    "mecanismo_de_sellado_temporal_externo",
)
_PROPUESTAS_AE53_ESPERADAS = {
    "horizonte": {"objetivos": 100, "desde": "primer_objetivo_posterior_al_corte",
                  "analisis": "unico_al_completar_el_horizonte"},
    "omisiones": "cualquier_omision_en_el_horizonte_no_evaluable",
    "referencia_secundaria": "definicion_vigente_uniforme_con_desempate_determinista_pareada_por_sorteo",
}
_PENDIENTES_AE53_ESPERADOS = ("unidad_y_metodo_inferencial", "tratamiento_dependencia_serial", "nivel_y_umbral",
                              "efecto_minimo", "multiplicidad_entre_juegos", "mecanismo_de_sellado_temporal_externo")


def _igual_estricto(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_igual_estricto(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def verificar_expediente() -> None:
    """Comprueba los invariantes de la base de los que depende el
    expediente y lanza `ExpedienteDivergenteError` ante cualquier
    divergencia en ellos, incluidos los tipos:

    - AE-52: los siete pendientes exactos y en orden (tupla), el minimo de
      100 resueltos y la orientacion uniforme - estrategia;
    - AE-53: especificacion en estado candidata sin aprobar, con sus tres
      propuestas exactas (valor y estado) y sus seis pendientes sin valor;
    - AE-56: las familias del catalogo y sus supuestos.

    No comprueba otras claves de esas constantes. No elige ni autoriza nada."""
    if not isinstance(PENDIENTES_BORRADOR_AE52, tuple) or PENDIENTES_BORRADOR_AE52 != _PENDIENTES_AE52_ESPERADOS:
        raise ExpedienteDivergenteError("Los siete pendientes de AE-52 no son los esperados")
    if not isinstance(REGLAS_EVALUACION_AE52, dict):
        raise ExpedienteDivergenteError("REGLAS_EVALUACION_AE52 no es un objeto")
    minimo = REGLAS_EVALUACION_AE52.get("minimo_sorteos_resueltos_por_juego")
    if type(minimo) is not int or minimo != 100:
        raise ExpedienteDivergenteError("El minimo de AE-52 ya no es 100 resueltos")
    if REGLAS_EVALUACION_AE52.get("orientacion_diferencia") != "uniforme_menos_estrategia":
        raise ExpedienteDivergenteError("La orientacion de AE-52 ya no es uniforme - estrategia")
    if not isinstance(ESPECIFICACION_CANDIDATA_AE53, dict):
        raise ExpedienteDivergenteError("ESPECIFICACION_CANDIDATA_AE53 no es un objeto")
    if ESPECIFICACION_CANDIDATA_AE53.get("estado") != "candidata_no_aprobada":
        raise ExpedienteDivergenteError("La especificacion de AE-53 ya no es una candidata sin aprobar")
    propuestas = ESPECIFICACION_CANDIDATA_AE53.get("propuestas")
    if not isinstance(propuestas, dict) or set(propuestas) != set(_PROPUESTAS_AE53_ESPERADAS):
        raise ExpedienteDivergenteError("Las propuestas de AE-53 no son las esperadas")
    for clave, valor in _PROPUESTAS_AE53_ESPERADAS.items():
        propuesta = propuestas[clave]
        if not _igual_estricto(propuesta, {"valor_propuesto": valor, "estado": "propuesta_no_aprobada"}):
            raise ExpedienteDivergenteError(f"La propuesta {clave} de AE-53 no es la esperada")
    pendientes = ESPECIFICACION_CANDIDATA_AE53.get("pendientes")
    if not isinstance(pendientes, dict) or set(pendientes) != set(_PENDIENTES_AE53_ESPERADOS):
        raise ExpedienteDivergenteError("Los pendientes de AE-53 no son los esperados")
    for clave in _PENDIENTES_AE53_ESPERADOS:
        if not _igual_estricto(pendientes[clave], {"valor": None, "estado": "pendiente"}):
            raise ExpedienteDivergenteError(f"El pendiente {clave} de AE-53 ya tiene valor o cambio de estado")
    if not isinstance(SUPUESTOS_POR_FAMILIA, (dict, MappingProxyType)):
        raise ExpedienteDivergenteError("SUPUESTOS_POR_FAMILIA no es un objeto")
    internas = {f.id: f for f in FAMILIAS_INFERENCIALES if not f.fuera_del_catalogo_ae56}
    if set(internas) != set(SUPUESTOS_POR_FAMILIA):
        raise ExpedienteDivergenteError("Las familias del catalogo de AE-56 no coinciden con el expediente")
    distintas = sorted(k for k, f in internas.items() if tuple(SUPUESTOS_POR_FAMILIA[k]) != f.supuestos)
    if distintas:
        raise ExpedienteDivergenteError(f"Supuestos de AE-56 distintos de los del expediente: {distintas}")
