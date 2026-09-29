"""
Verificacion primaria de los enunciados inferenciales pendientes en Choe
y Ramdas, arXiv:2110.00115v6 -Etapa AE-64, validada (solo esta verificacion primaria preparatoria y
sus pruebas; no aplica los teoremas al repositorio ni aprueba ninguna
inferencia).

AE-63 dejo seis enunciados de la fuente por verificar
(`ENUNCIADOS_DE_FUENTE_NECESARIOS`). Este modulo los registra leyendo el
PDF de v6 aportado por el operador y separa tres clases:

1. `el_articulo_afirma`: enunciados del articulo, con pagina y teorema,
   ecuacion o seccion; las formulas se comprobaron visualmente;
2. `derivacion_propia`: derivaciones matematicas sobre el codigo o sobre
   los enunciados, que no se atribuyen al articulo;
3. `aplicacion_al_repositorio`: condiciones cuya aplicacion a este
   repositorio sigue sin verificarse o exige una decision.

El articulo demuestra el e-proceso del teorema 3 solo para la nula debil
en todo tiempo. La cota conjunta para la nula terminal o sobre T es una
derivacion propia, condicionada a las hipotesis de la supermartingala, y
su aplicacion al repositorio sigue pendiente. No elige pregunta, familia,
cota, lambda, alfa ni regla, no autoriza ninguna evaluacion y no cambia
ningun uso de 1/E: el expediente sigue en `expediente_sin_eleccion` con
`AUTORIZA_EVALUACION = False`. Puro: sin datos reales, PostgreSQL,
entrenamiento ni predicciones reales.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml.traslado_condiciones_inferenciales import CONDICIONES_DE_TRASLADO, Intervalo, ancho

PROCEDENCIA_V6 = MappingProxyType({
    "version": "arXiv:2110.00115v6",
    "sello_en_el_pdf": "arXiv:2110.00115v6 [stat.ME] 9 Nov 2023",
    "fecha_de_portada": "November 10, 2023",
    "sha256_pdf": "fd87e23a30c6657fd8dd272f671d0bd8a3aa469f5aafbec85a00bb9501764286",
    "bytes_pdf": 6089652,
    "paginas_pdf": 61,
    "via": "pdf_v6_aportado_por_el_operador_leido_por_claude",
    "metodo": "extraccion de texto propia (flujos Flate, flujos de objetos y mapas ToUnicode) y comprobacion visual "
              "de las formulas citadas en paginas renderizadas fuera del repositorio",
    "paginas_comprobadas_visualmente": ("1", "8", "9", "10", "11", "13", "14", "16", "17", "18", "26", "32", "33", "34",
                                        "47", "48", "50", "51"),
    "html_v6": "no_consultado_bloqueado",
    "coincidencia_con_arxiv": "no comprobable desde el sandbox; la version queda acreditada por el sello impreso",
    "pdf_en_el_repositorio": "no",
})
"""Procedencia del texto primario. Nada se atribuye al HTML de v6."""

CLASES = ("el_articulo_afirma", "derivacion_propia", "aplicacion_al_repositorio")
ESTADOS_ENUNCIADO = ("verificado_en_pdf_v6", "discrepancia_con_registro_previo", "no_encontrado_en_v6")
ESTADOS_HIPOTESIS = ("demostrada", "refutada", "pendiente")


@dataclass(frozen=True)
class EnunciadoFuente:
    id: str
    pagina: str
    referencia: str
    parafrasis: str
    comprobacion: str
    estado: str = "verificado_en_pdf_v6"
    clase: str = "el_articulo_afirma"


@dataclass(frozen=True)
class Hipotesis:
    id: str
    clase: str
    afirmacion: str
    estado: str
    simbolos_del_repositorio: tuple[str, ...]
    base: str = ""
    exige: str = ""


@dataclass(frozen=True)
class Punto:
    numero: int
    tema: str
    enunciados: tuple[EnunciadoFuente, ...]
    hipotesis: tuple[Hipotesis, ...]


# ---------------------------------------------------------------------------
# Constantes de escala derivadas de los intervalos de AE-63
# ---------------------------------------------------------------------------

def constante_c_teorema_2(intervalo: Intervalo) -> float:
    """c tal que |d_t| <= c/2 (hipotesis del teorema 2): 2 * max(|a|, |b|)."""
    return 2 * max(abs(intervalo.inferior), abs(intervalo.superior))


def constante_c_teorema_1(intervalo: Intervalo) -> float:
    """c tal que |d_t| <= c, condicion suficiente de la p. 13 para la
    subgaussianidad del teorema 1: max(|a|, |b|)."""
    return max(abs(intervalo.inferior), abs(intervalo.superior))


def constante_c_centrada(intervalo: Intervalo) -> float:
    """Derivacion propia: restando la constante conocida m = (a + b)/2, el
    diferencial centrado cumple |d_t - m| <= (b - a)/2, luego c = b - a;
    el estimando se desplaza en la constante m. No fija la decision `cota`."""
    return ancho(intervalo)


# ---------------------------------------------------------------------------
# Lectura por punto
# ---------------------------------------------------------------------------

_E = EnunciadoFuente
_H = Hipotesis
_DER, _APL = "derivacion_propia", "aplicacion_al_repositorio"
_INTERVALOS = ("traslado_condiciones_inferenciales:intervalo_diferencia_log_loss",
               "traslado_condiciones_inferenciales:intervalo_diferencia_brier",
               "traslado_condiciones_inferenciales:intervalo_diferencia_precision_en_5")

LECTURA_POR_PUNTO = (
    Punto(1, "acotacion del teorema 2", (
        _E("T2_hipotesis", "14", "teorema 2, ecuacion (15)",
           "si |delta_hat_i| <= c/2 para todo i >= 1, con c en (0, inf), y V_t = suma de (delta_hat_i - gamma_i)^2 "
           "con gamma_i predecible respecto de G y valores en [-c/2, c/2], entonces C^EB_t = (Delta_hat_t +- "
           "u(V_t)/t) es una (1 - alfa)-CS para Delta_t, con u = u_{alfa/2,c} frontera subexponencial", "visual"),
        _E("F2_cota_fija", "48", "seccion F.2, ecuacion (103)",
           "los teoremas 2 y 3 exigen una cota fija |delta_hat_i| <= c/2; si c no se conoce a priori, se admiten "
           "cotas predecibles c_i", "visual"),
        _E("P7_cotas_predecibles", "50", "proposicion 7, ecuaciones (108)-(111)",
           "con |delta_hat_i| <= c_i/2, c_i predecible estrictamente positiva y gamma_i predecible en [-c_i/2, "
           "c_i/2], el proceso (110) es un e-proceso para H0w(p, q)", "visual"),
        _E("A1_proposicion_1", "32", "proposicion 1, ecuaciones (27)-(32)",
           "para cualquier proceso X_i con medias condicionales y X_i - gamma_i >= -c_i con gamma_i y c_i "
           "predecibles, el producto (28) es una supermartingala de prueba", "visual"),
    ), (
        _H("P1_acotacion_constante_en_el_repositorio", _DER,
           "los limites de d_t son constantes conocidas antes de los datos, asi que |d_t| <= c/2 con c = 2 max(|a|, "
           "|b|): Log Loss 26,9121308208; Brier 1,794483504598 (supremo); P@5 2",
           "demostrada", (*_INTERVALOS, "verificacion_primaria_choe_ramdas:constante_c_teorema_2"),
           base="intervalos de AE-63 derivados de EPSILON_CLIP, del dominio (0, 1) y de los parametros del juego"),
        _H("P1_centrado_por_constante", _DER,
           "restando la constante conocida m = (a + b)/2, c = b - a (Log Loss 13,8155; Brier 1; P@5 2) y el "
           "estimando se desplaza en m", "demostrada", ("verificacion_primaria_choe_ramdas:constante_c_centrada",),
           base="m es determinista; no fija la decision cota"),
        _H("P1_gamma_predecible", _APL,
           "la sucesion gamma_i (el articulo usa por defecto Delta_hat_(i-1), p. 14) depende del procedimiento, "
           "que sigue sin decidir", "pendiente", ("propuesta_inferencia_prospectiva:DECISIONES_INFERENCIALES_ABIERTAS",),
           exige="eleccion del procedimiento inferencial, sin decidir (unidad_y_metodo_inferencial de AE-53)"),
    )),
    Punto(2, "subgaussianidad del teorema 1", (
        _E("T1_hipotesis", "13", "teorema 1, ecuaciones (13)-(14)",
           "si delta_hat_i es c-subgaussiano condicionado a G_(i-1), es decir, E_(i-1)[exp(lambda (delta_hat_i - "
           "delta_i))] <= exp(lambda^2 c^2/2) para todo lambda real, entonces C^H_t = (Delta_hat_t +- u(t)/t) es una "
           "(1 - alfa)-CS para Delta_t, con u = u_{alfa/2,c} subgaussiana unilateral (o bilateral con alfa)", "visual"),
        _E("T1_condicion_suficiente", "13", "seccion 4.3.2",
           "si |delta_hat_i| <= c para algun c > 0, delta_hat_i es c-subgaussiano condicionado a G_(i-1) "
           "(Hoeffding, 1963)", "visual"),
    ), (
        _H("P2_subgaussiana_por_condicion_suficiente", _DER,
           "por la condicion suficiente de la p. 13, c = max(|a|, |b|): Log Loss 13,4560654104; Brier 0,8972417523; "
           "P@5 1", "demostrada", (*_INTERVALOS, "verificacion_primaria_choe_ramdas:constante_c_teorema_1"),
           base="acotacion constante de los diferenciales del repositorio"),
        _H("P2_parametrizacion_coherente_con_K2", _DER,
           "el proxy w^2/4 de K2 (AE-63) equivale a c = w/2 tras centrar por una constante", "demostrada",
           ("traslado_condiciones_inferenciales:ancho",), base="lema de Hoeffding, derivacion estandar"),
    )),
    Punto(3, "definicion y signo de los diferenciales", (
        _E("orientacion_positiva", "8", "seccion 3.2",
           "las reglas de puntuacion se toman positivamente orientadas: mayor puntuacion, mejor pronostico; una "
           "regla es cualquier funcion real extendida S: P x Y -> R", "visual"),
        _E("reglas_binarias", "9", "seccion 3.2",
           "Brier S(p, y) = 1 - (p - y)^2; logaritmica S(p, y) = y log(p) + (1 - y) log(1 - p)", "visual"),
        _E("diferenciales", "11", "ecuaciones (8)-(10)",
           "Delta_t = (1/t) suma de E_(i-1)[S(p_i, y_i) - S(q_i, y_i)] respecto de G; delta_hat_i = S(p_i, y_i) - "
           "S(q_i, y_i); S_t = suma de (delta_hat_i - delta_i) es martingala", "visual"),
        _E("nula_debil", "16", "ecuacion (18)",
           "H0w(p, q): Delta_t <= 0 para todo t = 1, 2, ...: p no es mejor que q en promedio", "visual"),
    ), (
        _H("P3_signo_log_loss_y_brier", _DER,
           "con p = estrategia, q = uniforme y S = -perdida, delta_hat = S_estrategia - S_uniforme = d_t "
           "(uniforme - estrategia en perdidas); la nula P1b en d coincide con H0w(estrategia, uniforme) "
           "restringida a la ventana", "demostrada",
           ("especificacion_evaluacion_prospectiva:metricas_por_sorteo", "registro_prospectivo:REGLAS_EVALUACION_AE52"),
           base="algebra sobre las diferencias del contrato"),
        _H("P3_signo_precision_en_5", _DER,
           "P@5 es ganancia: delta_hat = P@5_estrategia - P@5_uniforme = -d_t", "demostrada",
           ("especificacion_evaluacion_prospectiva:metricas_por_sorteo",
            "propuesta_inferencia_prospectiva:ORIENTACION_MEJORA_POR_METRICA"),
           base="algebra sobre las diferencias del contrato"),
    )),
    Punto(4, "filtraciones y predictibilidad", (
        _E("filtraciones", "10-11", "seccion 4.2",
           "F observable: p_t, q_t e y_t adaptados; G oraculo: G_(t-1) incluye F_(t-1) y la informacion de la "
           "realidad antes de y_t; p_t, q_t y r_t son predecibles respecto de G e y_t adaptado; los pronosticadores "
           "no usan r_t ni el futuro y la realidad puede elegir r_t tras ver p_t y q_t", "visual"),
        _E("parada", "8", "ecuacion (3)",
           "la cobertura de una CS se mantiene en tiempos de parada arbitrarios", "visual"),
        _E("F1_subsucesiones_predecibles", "47-48", "seccion F.1, ecuaciones (96)-(102)",
           "con xi_t en {0, 1} predecible, la CS y el e-proceso siguen siendo validos, pero el estimando pasa a ser "
           "Delta_t(xi), el promedio solo en los tiempos con xi_t = 1", "visual"),
        _E("rezago", "26", "seccion 6",
           "pronosticos hechos h > 1 rondas antes requieren condicionar a la filtracion del momento del pronostico "
           "(seccion E)", "visual"),
    ), (
        _H("P4_uniforme_y_limites_predecibles", _DER,
           "la uniforme es determinista (5/43) y los limites de d_t son constantes: ambos son predecibles",
           "demostrada", ("baselines:baseline_uniforme", *_INTERVALOS), base="constantes del contrato"),
        _H("P4_anterioridad_de_p_t", _APL,
           "que p_t se fije antes del sorteo (rezago 1, predecible respecto de G) no es demostrable en el codigo: "
           "la cadena de hashes no acredita la fecha", "pendiente",
           ("registro_prospectivo:ALCANCE_REGISTRO", "registro_prospectivo:PENDIENTES_BORRADOR_AE52"),
           exige="decision mecanismo_de_sellado_temporal_externo"),
        _H("P4_omisiones_predecibles", _APL,
           "solo una omision predecible conserva la validez, con estimando Delta_t(xi); una omision que depende del "
           "resultado la rompe (O2 de AE-63)", "pendiente",
           ("semantica_omisiones_prospectivas:ALTERNATIVAS_OMISION",
            "especificacion_evaluacion_prospectiva:validar_secuencia_objetivos"),
           exige="decision tratamiento_de_omisiones y, en supervision, tiempos_supervision"),
    )),
    Punto(5, "Log Loss truncado frente a EPSILON_CLIP", (
        _E("truncada_no_propia", "13", "seccion 4.3.2",
           "variante truncada S(p, y) = y log(p v eps) + (1 - y) log((1 - p) v eps) para algun eps > 0 pequeno: "
           "\"although the score is no longer proper, our methods remain valid\"", "visual"),
        _E("truncada_impropia", "14", "seccion 4.3.3",
           "se admite cualquier regla acotada, incluida la \"truncated logarithmic score (improper)\"", "visual"),
        _E("no_acotadas", "26", "seccion 6",
           "con diferenciales no acotados: CS asintotica (seccion C) o puntuacion de Winkler (seccion D)", "visual"),
    ), (
        _H("P5_equivalencia_con_EPSILON_CLIP", _DER,
           "la puntuacion del repositorio, y log(c) + (1 - y) log(1 - c) con c = min(max(p, eps), 1 - eps) y eps = "
           "1e-6, no es la truncada del articulo: con y = 1 y p = 1 - 1e-9 dan log(1 - 1e-6) frente a "
           "log(1 - 1e-9)", "refutada", ("metricas:EPSILON_CLIP", "metricas:_recortar"),
           base="contraejemplo exacto"),
        _H("P5_propiedad_distinta", _DER,
           "la truncada del articulo es impropia (con q = eps/2, un reporte eps/4 supera al veraz); la del "
           "repositorio es propia no estricta (L2 de AE-63)", "demostrada", ("metricas:_recortar",),
           base="contraejemplo exacto y L2 de AE-63"),
        _H("P5_validez_por_acotacion", _DER,
           "la validez de los teoremas depende solo de la acotacion (L1 de AE-63), no de la equivalencia de "
           "formulas", "demostrada", ("traslado_condiciones_inferenciales:intervalo_diferencia_log_loss",),
           base="hipotesis de los teoremas 1 y 2"),
    )),
    Punto(6, "alcance: regla probabilistica o diferencial acotado", (
        _E("resumen_acotadas", "1", "resumen", "\"our main theorems apply to any bounded scores\"", "visual"),
        _E("definicion_regla", "8", "seccion 3.2",
           "una regla de puntuacion es cualquier funcion real extendida S: P x Y -> R", "visual"),
        _E("requieren_acotadas", "26", "seccion 6",
           "los resultados principales (teoremas 2 y 3) requieren reglas acotadas", "visual"),
        _E("proposicion_1_general", "32", "proposicion 1",
           "la proposicion 1 vale para cualquier proceso X_i cuyas medias condicionales existen", "visual"),
        _E("generalizacion_acotada", "51", "seccion G, ecuacion (114)",
           "los teoremas 2 y 3 son aplicables cuando los diferenciales asociados estan acotados, |S(p, y) - S(q, y)| "
           "<= c/2", "visual"),
        _E("elicitacion_separada", "10", "nota 5",
           "el articulo separa el problema de comparacion del de elicitacion (pronosticos honestos)", "visual"),
    ), (
        _H("P6_acotacion_de_las_tres_metricas", _DER,
           "Log Loss recortada, Brier y P@5 tienen diferenciales acotados, asi que cumplen la hipotesis de "
           "acotacion; la propiedad no es requisito de validez", "demostrada", _INTERVALOS,
           base="intervalos de AE-63"),
        _H("P6_pronostico_funcional", _DER,
           "los reportes son 43 marginales, no una distribucion sobre los resultados; la validez descansa en la "
           "generalidad de la proposicion 1 (cualquier proceso con medias condicionales)", "demostrada",
           ("especificacion_evaluacion_prospectiva:metricas_por_sorteo",), base="proposicion 1 y acotacion"),
        _H("P6_interpretacion_de_la_puntuacion", _APL,
           "leer una diferencia como mejor pronostico probabilistico depende de la propiedad de la regla y de las "
           "marginales reales (L2 de AE-63); P@5 mide aciertos del Top-5", "pendiente",
           ("traslado_condiciones_inferenciales:CONDICIONES_DE_TRASLADO",),
           exige="evidencia sobre las marginales reales y decision papel_y_direccion_de_la_secundaria"),
    )),
)
"""Seis puntos de AE-63, cada uno con enunciados del articulo e hipotesis
en el repositorio separados."""

ENUNCIADOS_NULAS_Y_E_PROCESOS = (
    _E("nula_fuerte", "17", "ecuacion (21)",
       "H0s(p, q): delta_t <= 0 para todo t; implica H0w, pero no al reves", "visual"),
    _E("corolario_1", "16", "corolario 1, ecuaciones (19)-(20)",
       "rechazar H0w(p, q) si L_t > 0 es una prueba secuencial de nivel alfa para las dos nulas debiles "
       "conjuntamente; se admite probar una sola vez en un tiempo designado", "visual"),
    _E("teorema_3", "17", "teorema 3, ecuacion (24)",
       "con las condiciones del teorema 2 y lambda en [0, 1/c), E_t(lambda) = exp(lambda suma de delta_hat_i - "
       "psi_E,c(lambda) V_t) es un e-proceso para H0w(p, q); tambien la mezcla sobre F", "visual"),
    _E("definicion_e_proceso", "17", "ecuacion (23)",
       "un e-proceso cumple E_P[E_tau] <= 1 para toda P de la nula y todo tiempo de parada tau", "visual"),
    _E("prueba_proposicion_2", "33-34", "proposicion 2, ecuaciones (38)-(40)",
       "bajo cualquier P de H0w(p, q), exp(-lambda suma de delta_i) >= 1, luego E_t(lambda) <= L_t(lambda) en "
       "todo t, con L_t supermartingala de prueba", "visual"),
    _E("p_proceso", "18", "ecuaciones (25)-(26)",
       "p_t = 1/sup_(i <= t) E_i es un p-proceso para la nula del e-proceso; p_t tambien puede definirse como el "
       "menor alfa cuya CS excluye el cero", "visual"),
)
"""Nulas, pruebas y e-procesos del articulo (seccion 4.4 y apendice A)."""

DISCREPANCIAS = (
    MappingProxyType({
        "registro": "propuesta_inferencia_prospectiva:VERIFICACION_FUENTES_SECUENCIALES",
        "fuente": "choe_ramdas_arxiv_2110_00115v6",
        "campo": "acotacion",
        "texto_registrado": "truncarla altera su propiedad de puntuacion estrictamente propia",
        "texto_pdf_v6": "p. 13: \"although the score is no longer proper, our methods remain valid\"; p. 14: "
                        "\"truncated logarithmic score (improper)\"",
        "tratamiento": "se conserva la atribucion original a la revision externa; prevalece la lectura del PDF v6: "
                       "la truncada del articulo deja de ser propia, no solo estrictamente propia",
    }),
)
"""Discrepancias entre registros previos y la lectura del PDF v6."""


# ---------------------------------------------------------------------------
# Dependencias de N2 y derivacion de 1/E
# ---------------------------------------------------------------------------

_COMUNES = ("C3_correspondencia_de_signo", "F1_anterioridad", "F2_correspondencia_de_la_filtracion",
            "O3_tratamiento_de_omisiones")

DEPENDENCIAS_DE_N2 = MappingProxyType({
    "cobertura_via_teorema_1": ("C2_correspondencia_subgaussiana_teorema_1", *_COMUNES),
    "cobertura_via_teorema_2": ("C1_correspondencia_acotacion_teorema_2", "P1_gamma_predecible", *_COMUNES),
    "cobertura_por_metrica": MappingProxyType({
        "log_loss": ("L1_acotacion_log_loss",),
        "brier_score": ("B1_acotacion_brier",),
        "precision_en_5": ("P1_acotacion_precision_en_5", "P3_signo_precision_en_5"),
    }),
    "interpretacion": ("L2_log_loss_propia", "L2_marginales_reales_en_el_intervalo",
                       "P2_precision_en_5_propia_no_estricta"),
    "operativos": ("mecanismo_de_sellado_temporal_externo", "tratamiento_de_omisiones", "tiempos_supervision", "cota",
                   "alfa"),
})
"""Dependencias de `N2_inversion_para_p1b` separadas por via inferencial,
metrica, interpretacion de la puntuacion y requisitos operativos. C4 no es
requisito de cobertura: la validez depende de la acotacion, no de la
equivalencia con la truncada del articulo."""

DERIVACION_1_SOBRE_E_TEOREMA_3 = MappingProxyType({
    "clase": "derivacion_propia",
    "base_en_el_articulo": "el articulo demuestra el e-proceso solo para la nula debil H0w (todo t >= 1): teorema 3 "
                           "(p. 17, ecuacion (24)) y prueba de la proposicion 2 (p. 34, ecuaciones (39)-(40))",
    "hipotesis": "condiciones del teorema 2 (|delta_hat_i| <= c/2 con c constante y gamma_i predecible en [-c/2, "
                 "c/2]) y marco G (p_t y q_t predecibles), bajo las cuales L_t(lambda) es supermartingala de prueba "
                 "respecto de G (proposicion 1); lambda en [0, 1/c), o la mezcla F, y el conjunto T fijados antes "
                 "de los datos, sin elegirlos aqui",
    "identidad": "E_t(lambda) = L_t(lambda) exp(lambda t Delta_t), de modo que E_t(lambda) <= L_t(lambda) en el "
                 "evento Delta_t <= 0",
    "nula_terminal": "cota conjunta P(E_100 >= 1/alfa y Delta_100 <= 0) <= P(L_100 >= 1/alfa) <= alfa, por Markov; "
                     "para las leyes en que Delta_100 <= 0 casi seguro, P(E_100 >= 1/alfa) <= alfa",
    "nula_sobre_T": "cota conjunta P(sup sobre t en T de E_t >= 1/alfa y Delta_t <= 0 para todo t en T) <= "
                    "P(sup_t L_t >= 1/alfa) <= alfa, por Ville, con T fijado antes de los datos",
    "limitacion": "1/sup_(i <= 100) E_i no queda cubierto bajo la nula terminal, porque el supremo recorre tiempos "
                  "en que Delta_i puede ser positiva; la derivacion es propia de esta construccion exponencial y no "
                  "contradice el contraejemplo de AE-62 para e-procesos arbitrarios",
    "estado_de_la_derivacion": "demostrada_bajo_las_hipotesis_de_la_supermartingala",
    "estado_de_aplicacion_al_repositorio": "pendiente",
    "dependencias_de_aplicacion": ("C1_correspondencia_acotacion_teorema_2", "P1_gamma_predecible",
                                   "C3_correspondencia_de_signo", "F1_anterioridad",
                                   "F2_correspondencia_de_la_filtracion", "O3_tratamiento_de_omisiones"),
})
"""Derivacion propia para 1/E_100 y 1/sup_T E_t bajo las nulas exactas del
expediente. No es un enunciado del articulo ni una probabilidad
condicional al evento nulo; su aplicacion al repositorio sigue pendiente."""


# ---------------------------------------------------------------------------
# Estados tras AE-64
# ---------------------------------------------------------------------------

def combinar(estados) -> str:
    """Pendiente si alguna dependencia lo esta; si no, refutada si alguna lo
    esta; si no, demostrada."""
    estados = tuple(estados)
    if "pendiente" in estados:
        return "pendiente"
    if "refutada" in estados:
        return "refutada"
    return "demostrada"


def mejor_via(estados) -> str:
    """Una conclusion con varias vias queda demostrada si alguna lo esta."""
    estados = tuple(estados)
    if "demostrada" in estados:
        return "demostrada"
    return "pendiente" if "pendiente" in estados else "refutada"


_DEPENDENCIAS_TRAS_AE64 = (
    ("C1_correspondencia_acotacion_teorema_2", ("P1_acotacion_constante_en_el_repositorio",),
     "el teorema 2 exige |delta_hat_i| <= c/2 con c constante (p. 14); el repositorio la cumple"),
    ("C2_correspondencia_subgaussiana_teorema_1", ("P2_subgaussiana_por_condicion_suficiente",),
     "condicion suficiente de la p. 13 con c = max(|a|, |b|)"),
    ("C3_correspondencia_de_signo", ("P3_signo_log_loss_y_brier", "P3_signo_precision_en_5"),
     "orientacion positiva (p. 8) y delta_hat = S(p) - S(q) (p. 11)"),
    ("C4_truncamiento_de_la_fuente_frente_a_EPSILON_CLIP", ("P5_equivalencia_con_EPSILON_CLIP",),
     "la equivalencia queda refutada; no es requisito de validez"),
    ("C5_aplicabilidad_a_precision_en_5", ("P6_acotacion_de_las_tres_metricas", "P6_pronostico_funcional"),
     "los teoremas admiten cualquier diferencial acotado; la interpretacion sigue aparte"),
    ("F2_correspondencia_de_la_filtracion", ("P4_anterioridad_de_p_t",),
     "G exige p_t predecible; depende de la anterioridad, sin sellado"),
)


def recalcular_estados() -> dict[str, str]:
    """Estados de C1-C5, F2, N2 y U1 derivados de sus dependencias."""
    hipotesis = {h.id: h.estado for punto in LECTURA_POR_PUNTO for h in punto.hipotesis}
    base = {c.id: c.estado for c in CONDICIONES_DE_TRASLADO}
    estados = {}
    for id_, dependencias, _ in _DEPENDENCIAS_TRAS_AE64:
        estados[id_] = combinar(hipotesis[d] for d in dependencias)

    def estado(dep):
        return estados.get(dep) or hipotesis.get(dep) or base[dep]

    metricas = DEPENDENCIAS_DE_N2["cobertura_por_metrica"]
    vias = (combinar(estado(d) for d in DEPENDENCIAS_DE_N2[via])
            for via in ("cobertura_via_teorema_1", "cobertura_via_teorema_2"))
    estados["N2_inversion_para_p1b"] = combinar(
        (mejor_via(vias), *(estado(d) for deps in metricas.values() for d in deps)))
    estados["U1_usos_de_1_sobre_E"] = combinar(
        estado(d) for d in DERIVACION_1_SOBRE_E_TEOREMA_3["dependencias_de_aplicacion"])
    return estados


_ESTADOS = recalcular_estados()

ESTADOS_TRAS_AE64 = MappingProxyType({
    **{id_: MappingProxyType({"estado": _ESTADOS[id_], "dependencias": deps, "motivo": motivo})
       for id_, deps, motivo in _DEPENDENCIAS_TRAS_AE64},
    "N2_inversion_para_p1b": MappingProxyType({
        "estado": _ESTADOS["N2_inversion_para_p1b"],
        "dependencias": tuple(DEPENDENCIAS_DE_N2["cobertura_via_teorema_1"])
        + tuple(DEPENDENCIAS_DE_N2["cobertura_via_teorema_2"]),
        "motivo": "ambas vias dependen de la anterioridad (F1) y del tratamiento de omisiones (O3), pendientes"}),
    "U1_usos_de_1_sobre_E": MappingProxyType({
        "estado": _ESTADOS["U1_usos_de_1_sobre_E"],
        "dependencias": DERIVACION_1_SOBRE_E_TEOREMA_3["dependencias_de_aplicacion"],
        "motivo": "existe una derivacion condicionada a la supermartingala, pero su aplicacion al repositorio "
                  "depende de la anterioridad, la filtracion, las omisiones y la eleccion de gamma"}),
})
"""Estados de las condiciones de AE-63 tras la lectura de v6. No modifica
`CONDICIONES_DE_TRASLADO` ni los usos de 1/E del expediente."""
