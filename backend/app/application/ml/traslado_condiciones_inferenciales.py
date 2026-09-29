"""
Traslado de las condiciones inferenciales al contrato del repositorio
-Etapa AE-63, validada (solo esta auditoria del traslado, sus condiciones
y sus pruebas; no demuestra que los teoremas de las fuentes sean aplicables
al repositorio ni aprueba ninguna inferencia).

AE-62 registro que enunciados de las fuentes estan comprobados (por la
revision atribuida de un auditor externo) y dejo su traslado al contrato
en `aplicacion_al_repositorio_sin_verificar`. Este modulo audita, condicion
por condicion, si las hipotesis se cumplen en el contrato concreto:
dominio de reportes, acotacion de d_t en Log Loss, Brier y P@5,
`EPSILON_CLIP`, propiedad de cada regla en su dominio exacto, signo de
d_t, cota de incrementos, filtracion y anterioridad, nulas y omisiones.
Cada condicion queda demostrada (derivacion propia sobre el codigo),
refutada (contraejemplo exacto) o pendiente (falta un enunciado exacto de
la fuente o una decision del operador).

No convierte una garantia bajo una nula mas fuerte en garantia para P1b,
no cambia ningun uso de 1/E, no fija ninguna decision y no modifica el
expediente de AE-60 a AE-62: el estado sigue en `expediente_sin_eleccion`
con `AUTORIZA_EVALUACION = False`. Puro: sin datos reales, PostgreSQL,
entrenamiento ni predicciones reales.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml.metricas import EPSILON_CLIP
from app.application.ml.propuesta_inferencia_prospectiva import (
    DECISIONES_INFERENCIALES_ABIERTAS,
    DECISIONES_REQUERIDAS,
    Decision,
)
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame

ESTADOS_CONDICION = ("demostrada", "refutada", "pendiente")
SUSTENTOS = ("derivacion_propia_sobre_el_codigo", "contraejemplo_exacto", "requiere_enunciado_de_fuente",
             "requiere_decision_del_operador", "requiere_evidencia_o_hipotesis_declarada")

_JUEGOS = MappingProxyType({"BALOTO": BalotoGame, "BALOTO_REVANCHA": BalotoRevanchaGame})

DOMINIO_DEL_CONTRATO = MappingProxyType({
    "reportes": "43 probabilidades float finitas en el intervalo abierto (0, 1), sin restriccion conjunta (sin suma "
                "fija ni normalizacion)",
    "resultados": "5 numeros distintos en 1..43; las marginales reales q_i estan en [0, 1] y tienen suma 5; esa "
                  "restriccion afecta a q, no a los reportes",
    "desempate_top5": "probabilidad descendente y, en empate, numero ascendente; la uniforme empata y elige 1..5",
    "extremos": "los extremos citados como alcanzables lo son en este dominio sin restriccion conjunta; una "
                "restriccion como suma de reportes igual a 5 seria una decision del operador y los cambiaria",
    "simbolos": ("especificacion_evaluacion_prospectiva:metricas_por_sorteo", "metricas:calcular_log_loss",
                 "metricas:calcular_brier_score", "metricas:_top5_deterministico", "baselines:baseline_uniforme"),
})
"""Dominio de reportes y resultados comprobado en el codigo de la base."""


# ---------------------------------------------------------------------------
# Intervalos de d_t = uniforme - estrategia en el dominio del contrato
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Intervalo:
    inferior: float
    superior: float
    cerrado: bool


def _parametros(codigo_juego: str) -> tuple[int, int]:
    if codigo_juego not in _JUEGOS:
        raise ValueError(f"Juego no autorizado: {codigo_juego!r}")
    juego = _JUEGOS[codigo_juego]()
    rango_min, rango_max = juego.number_range
    return rango_max - rango_min + 1, juego.numbers_to_pick


def intervalo_diferencia_log_loss(codigo_juego: str) -> Intervalo:
    """[LL_u + log(eps), LL_u + log(1 - eps)]: la perdida por fila con p
    recortada esta en [-log(1 - eps), -log(eps)] y la media de filas
    tambien; los extremos se alcanzan en el dominio sin restriccion
    conjunta."""
    tamano, cantidad = _parametros(codigo_juego)
    p = cantidad / tamano
    uniforme = -(cantidad * math.log(p) + (tamano - cantidad) * math.log(1 - p)) / tamano
    return Intervalo(uniforme + math.log(EPSILON_CLIP), uniforme + math.log(1 - EPSILON_CLIP), True)


def intervalo_diferencia_brier(codigo_juego: str) -> Intervalo:
    """(B_u - 1, B_u): sin recorte y con reportes en (0, 1), cada fila
    (p - y)^2 esta en (0, 1); intervalo abierto, extremos no alcanzados.

    El intervalo abierto describe los valores matematicos ideales. El
    valor calculado en coma flotante por `metricas_por_sorteo`
    puede coincidir con un extremo por redondeo cuando la distancia
    ideal es menor que media unidad en la ultima posicion (por ejemplo,
    con reportes a 1e-9 del extremo la distancia al supremo es 1e-18)."""
    tamano, cantidad = _parametros(codigo_juego)
    p = cantidad / tamano
    uniforme = (cantidad * (1 - p) ** 2 + (tamano - cantidad) * p ** 2) / tamano
    return Intervalo(uniforme - 1, uniforme, False)


def intervalo_diferencia_precision_en_5() -> Intervalo:
    """[-1, 1]: P@5 de la estrategia y de la uniforme estan en [0, 1] y
    ambos extremos se alcanzan."""
    return Intervalo(-1.0, 1.0, True)


def ancho(intervalo: Intervalo) -> float:
    return intervalo.superior - intervalo.inferior


def cota_de_incrementos(intervalo: Intervalo) -> float:
    """Con d_t en [a, b], g_t = E[d_t | F_(t-1)] tambien esta en [a, b] y
    |eps_t| = |d_t - g_t| <= b - a. Es un ancho derivado, no el valor de
    la decision `cota`, que sigue sin decidir."""
    return ancho(intervalo)


# ---------------------------------------------------------------------------
# Condiciones de traslado
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Condicion:
    id: str
    ambito: str
    afirmacion: str
    estado: str
    sustento: str
    dominio: str
    simbolos_del_repositorio: tuple[str, ...]
    enunciado_de_fuente_necesario: str = ""
    decision_del_operador: str = ""
    evidencia_necesaria: str = ""


_V6 = "arXiv:2110.00115v6"
_DERIVACION, _CONTRAEJEMPLO, _FUENTE, _DECISION, _EVIDENCIA = SUSTENTOS

ENUNCIADOS_DE_FUENTE_NECESARIOS = (
    f"{_V6}, teorema 2: hipotesis exacta de acotacion (que variable, intervalo conocido a priori o no, escala)",
    f"{_V6}, teorema 1: parametrizacion exacta de la subgaussianidad condicional",
    f"{_V6}, seccion 4: definicion y signo de los diferenciales y de Delta_t (orden de la resta; perdida o ganancia)",
    f"{_V6}, seccion 4.2: definicion de la filtracion G y exigencia de predictibilidad del pronostico",
    f"{_V6}: formula exacta del truncamiento de la puntuacion logaritmica",
    f"{_V6}: si los teoremas exigen una regla de puntuacion de probabilidades o admiten cualquier diferencial "
    "acotado",
)
"""Enunciados que el registro de AE-62 no contiene; los aporta el operador
o el auditor externo."""

_SIMB_LL = ("metricas:EPSILON_CLIP", "metricas:_recortar", "metricas:calcular_log_loss",
            "especificacion_evaluacion_prospectiva:metricas_por_sorteo", "baselines:baseline_uniforme")
_SIMB_BRIER = ("metricas:calcular_brier_score", "especificacion_evaluacion_prospectiva:metricas_por_sorteo",
               "baselines:baseline_uniforme")
_SIMB_P5 = ("metricas:calcular_precision_recall_en_5", "metricas:_top5_deterministico", "baselines:baseline_uniforme",
            "especificacion_evaluacion_prospectiva:metricas_por_sorteo")
_SIMB_SIGNO = ("especificacion_evaluacion_prospectiva:metricas_por_sorteo", "registro_prospectivo:REGLAS_EVALUACION_AE52",
               "propuesta_inferencia_prospectiva:ORIENTACION_MEJORA_POR_METRICA")
_SIMB_ANTERIORIDAD = ("registro_prospectivo:ALCANCE_REGISTRO", "registro_prospectivo:PENDIENTES_BORRADOR_AE52",
                      "especificacion_evaluacion_prospectiva:validar_secuencia_objetivos")
_SIMB_OMISIONES = ("especificacion_evaluacion_prospectiva:validar_secuencia_objetivos",
                   "semantica_omisiones_prospectivas:ALTERNATIVAS_OMISION",
                   "propuesta_inferencia_prospectiva:CONDICION_IGUALDAD_ESPERANZA")
_SIMB_NULAS = ("propuesta_inferencia_prospectiva:VERIFICACION_FUENTES_SECUENCIALES",
               "propuesta_inferencia_prospectiva:PREMISA_DE_LA_INVERSION",
               "propuesta_inferencia_prospectiva:FAMILIAS_INFERENCIALES")

CONDICIONES_DE_TRASLADO = (
    # Log Loss
    Condicion("L1_acotacion_log_loss", "log_loss",
              "d_t de Log Loss esta en [LL_u + log(eps), LL_u + log(1 - eps)], de ancho log((1 - eps)/eps); los "
              "extremos se alcanzan en el dominio sin restriccion conjunta",
              "demostrada", _DERIVACION, "reportes del contrato", _SIMB_LL),
    Condicion("L2_log_loss_propia", "log_loss",
              "para verdades reportables q en (0, 1), el reporte veraz p = q es admisible y alcanza el optimo: la "
              "perdida esperada es convexa en clip(p) con minimo en clip(q)",
              "demostrada", _DERIVACION, "q en (0, 1); reporte en (0, 1)", _SIMB_LL),
    Condicion("L2_log_loss_verdades_de_frontera", "log_loss",
              "con q en {0, 1} no hay reporte veraz admisible: p = q no es admisible porque el dominio de reportes es "
              "(0, 1); el minimo de la perdida esperada, -log(1 - eps), se alcanza mediante el recorte, y los "
              "minimizadores admisibles son exactamente 0 < p <= eps si q = 0 y 1 - eps <= p < 1 si q = 1; p = 0 y "
              "p = 1 quedan fuera del dominio",
              "demostrada", _DERIVACION, "q en {0, 1}; reporte en (0, 1)", _SIMB_LL),
    Condicion("L2_log_loss_estricta_en_todo_el_dominio", "log_loss",
              "con q = 1e-7, los reportes 1e-7 y 1e-8 tienen la misma perdida esperada: hay optimos no unicos si "
              "q <= eps o q >= 1 - eps",
              "refutada", _CONTRAEJEMPLO, "q en (0, 1); reporte en (0, 1)", _SIMB_LL),
    Condicion("L2_log_loss_estricta_en_D", "log_loss",
              "con q y reporte en [eps, 1 - eps] el recorte es la identidad y el optimo es unico en p = q; "
              "restringir solo los reportes no basta, porque con q < eps el optimo es eps; que las q reales esten en "
              "ese intervalo es otra condicion (L2_marginales_reales_en_el_intervalo)",
              "demostrada", _DERIVACION, "q en [eps, 1 - eps] y reporte en [eps, 1 - eps]", _SIMB_LL),
    Condicion("L2_marginales_reales_en_el_intervalo", "log_loss",
              "no se sabe si las marginales reales q_i estan en [eps, 1 - eps]; ninguna decision sobre reportes lo "
              "establece",
              "pendiente", _EVIDENCIA, "marginales reales", _SIMB_LL,
              evidencia_necesaria="evidencia sobre el mecanismo de sorteo (P3) o una hipotesis declarada y "
                                  "justificada de que las q_i reales estan en [eps, 1 - eps]"),
    # Brier
    Condicion("B1_acotacion_brier", "brier_score",
              "d_t de Brier esta en el intervalo abierto (B_u - 1, B_u), de ancho supremo 1; los extremos no se "
              "alcanzan en los valores matematicos ideales; el valor calculado en coma flotante puede coincidir con "
              "un extremo por redondeo cuando la distancia ideal es menor que media ulp",
              "demostrada", _DERIVACION, "reportes del contrato", _SIMB_BRIER),
    Condicion("B2_brier_estricta_q_interior", "brier_score",
              "E[(p - Y)^2] = (p - q)^2 + q(1 - q): minimo unico en p = q; con q en {0, 1} el infimo no se alcanza "
              "en el dominio abierto",
              "demostrada", _DERIVACION, "q en (0, 1); reporte en (0, 1)", _SIMB_BRIER),
    # P@5
    Condicion("P1_acotacion_precision_en_5", "precision_en_5",
              "d_t de P@5 esta en [-1, 1] y ambos extremos se alcanzan",
              "demostrada", _DERIVACION, "reportes del contrato", _SIMB_P5),
    Condicion("P2_precision_en_5_propia_no_estricta", "precision_en_5",
              "E[P@5(A)] = (1/5) suma de q_i en A; por intercambio, cinco marginales maximas maximizan esa suma, y "
              "el Top-5 del reporte veraz las toma porque el desempate solo elige entre marginales iguales",
              "demostrada", _DERIVACION, "q en (0, 1) con suma 5; reporte veraz admisible", _SIMB_P5),
    Condicion("P2_precision_en_5_estricta", "precision_en_5",
              "cualquier reporte con el mismo Top-5, o con otro Top-5 de igual suma de marginales, tiene la misma "
              "esperanza",
              "refutada", _CONTRAEJEMPLO, "q en (0, 1) con suma 5", _SIMB_P5),
    # Signo y cotas
    Condicion("S1_signo_de_d_t_en_el_codigo", "d_t",
              "d_t = uniforme - estrategia en las tres metricas; con Log Loss y Brier, la estrategia no mejora a la "
              "uniforme si y solo si Delta <= 0; en P@5 la mejora es negativa",
              "demostrada", _DERIVACION, "codigo de la base", _SIMB_SIGNO),
    Condicion("K1_cota_de_incrementos", "incrementos",
              "|eps_t| <= ancho del intervalo de d_t: log((1 - eps)/eps) en Log Loss, 1 en Brier (supremo) y 2 en "
              "P@5; son anchos derivados, no el valor de la decision cota",
              "demostrada", _DERIVACION, "reportes del contrato", (*_SIMB_LL, *_SIMB_BRIER, *_SIMB_P5)),
    Condicion("K2_subgaussianidad_por_acotacion", "incrementos",
              "un diferencial acotado en un intervalo de ancho w es condicionalmente subgaussiano con proxy w^2/4 "
              "(lema de Hoeffding, derivacion estandar sin fuente primaria examinada)",
              "demostrada", _DERIVACION, "reportes del contrato", _SIMB_LL),
    # Correspondencia con los enunciados exactos de la fuente
    Condicion("C1_correspondencia_acotacion_teorema_2", "fuente",
              "si la acotacion de L1 y B1 satisface la hipotesis del teorema 2", "pendiente", _FUENTE,
              "enunciado de la fuente", (*_SIMB_LL, *_SIMB_BRIER),
              enunciado_de_fuente_necesario=ENUNCIADOS_DE_FUENTE_NECESARIOS[0],
              decision_del_operador="lectura_primaria_pendiente_de_fuentes_secuenciales"),
    Condicion("C2_correspondencia_subgaussiana_teorema_1", "fuente",
              "si la subgaussianidad de K2 coincide con la parametrizacion del teorema 1", "pendiente", _FUENTE,
              "enunciado de la fuente", _SIMB_LL, enunciado_de_fuente_necesario=ENUNCIADOS_DE_FUENTE_NECESARIOS[1],
              decision_del_operador="lectura_primaria_pendiente_de_fuentes_secuenciales"),
    Condicion("C3_correspondencia_de_signo", "fuente",
              "si el signo de d_t del repositorio coincide con el de los diferenciales y Delta_t de la fuente",
              "pendiente", _FUENTE, "enunciado de la fuente", _SIMB_SIGNO,
              enunciado_de_fuente_necesario=ENUNCIADOS_DE_FUENTE_NECESARIOS[2],
              decision_del_operador="lectura_primaria_pendiente_de_fuentes_secuenciales"),
    Condicion("C4_truncamiento_de_la_fuente_frente_a_EPSILON_CLIP", "fuente",
              "relacion entre el truncamiento logaritmico que describe la fuente y EPSILON_CLIP; no se afirma "
              "equivalencia", "pendiente", _FUENTE, "enunciado de la fuente", _SIMB_LL,
              enunciado_de_fuente_necesario=ENUNCIADOS_DE_FUENTE_NECESARIOS[4],
              decision_del_operador="lectura_primaria_pendiente_de_fuentes_secuenciales"),
    Condicion("C5_aplicabilidad_a_precision_en_5", "fuente",
              "si los teoremas se aplican a P@5; cuestion distinta de su propiedad como regla", "pendiente", _FUENTE,
              "enunciado de la fuente", _SIMB_P5, enunciado_de_fuente_necesario=ENUNCIADOS_DE_FUENTE_NECESARIOS[5],
              decision_del_operador="papel_y_direccion_de_la_secundaria"),
    # Filtracion y anterioridad
    Condicion("F1_anterioridad", "filtracion",
              "que p_t se fije antes del sorteo no es demostrable en el codigo: la cadena de hashes no acredita la "
              "fecha y el sellado externo sigue pendiente",
              "pendiente", _DECISION, "registro y sellado", _SIMB_ANTERIORIDAD,
              decision_del_operador="mecanismo_de_sellado_temporal_externo"),
    Condicion("F2_correspondencia_de_la_filtracion", "fuente",
              "si la filtracion G de la fuente corresponde a la del repositorio (pasado de sorteos, p_1..p_t y la "
              "uniforme determinista)", "pendiente", _FUENTE, "enunciado de la fuente", _SIMB_ANTERIORIDAD,
              enunciado_de_fuente_necesario=ENUNCIADOS_DE_FUENTE_NECESARIOS[3],
              decision_del_operador="lectura_primaria_pendiente_de_fuentes_secuenciales"),
    # Nulas
    Condicion("N1_traslado_automatico_desde_H0w", "nulas",
              "un e-proceso para H0w (todo t >= 1) no da automaticamente valores p validos para la nula terminal ni "
              "para la nula sobre T: contraejemplo exacto de AE-62",
              "refutada", _CONTRAEJEMPLO, "nulas del expediente", _SIMB_NULAS),
    Condicion("N2_inversion_para_p1b", "nulas",
              "la inversion de la secuencia de confianza para P1b vale solo bajo PREMISA_DE_LA_INVERSION; sus "
              "dependencias, por via inferencial, metrica, interpretacion y requisitos operativos, estan desglosadas "
              "en verificacion_primaria_choe_ramdas.DEPENDENCIAS_DE_N2 (AE-64)", "pendiente", _FUENTE, "nulas del expediente", _SIMB_NULAS,
              enunciado_de_fuente_necesario=f"{_V6}, teoremas 1 y 2: enunciados exactos de sus hipotesis",
              decision_del_operador="lectura_primaria_pendiente_de_fuentes_secuenciales"),
    Condicion("U1_usos_de_1_sobre_E", "nulas",
              "1/E_100 bajo la nula terminal y 1/sup_T E_t bajo la nula sobre T siguen pendientes de demostracion",
              "pendiente", _FUENTE, "nulas del expediente", _SIMB_NULAS,
              enunciado_de_fuente_necesario=f"{_V6}, teorema 3: enunciado exacto; su nula es H0w, no la del expediente",
              decision_del_operador="lectura_primaria_pendiente_de_fuentes_secuenciales"),
    # Omisiones
    Condicion("O1_omision_predecible", "omisiones",
              "con I_t medible en F_(t-1), E[I_t d_t | F_(t-1)] = I_t g_t: la subsucesion conserva la estructura de "
              "diferencia de martingala",
              "demostrada", _DERIVACION, "omision decidida antes del sorteo", _SIMB_OMISIONES),
    Condicion("O2_omision_dependiente_del_resultado", "omisiones",
              "con d_t = +1 o -1 equiprobable (g_t = 0) e inclusion solo si d_t = +1, la media incluida es 1",
              "refutada", _CONTRAEJEMPLO, "omision decidida tras el resultado", _SIMB_OMISIONES),
    Condicion("O3_tratamiento_de_omisiones", "omisiones",
              "el tratamiento aplicable (propuesta de AE-53 sin aprobar) y los tiempos T en supervision",
              "pendiente", _DECISION, "omisiones y resultados pendientes", _SIMB_OMISIONES,
              decision_del_operador="tratamiento_de_omisiones"),
)
"""Una condicion por hallazgo de la auditoria de AE-63. Ninguna condicion
global de traslado queda demostrada."""

_EXISTENTES = MappingProxyType({
    **{d.id: d for d in DECISIONES_REQUERIDAS},
    **dict(DECISIONES_INFERENCIALES_ABIERTAS),
})

DECISIONES_DEL_OPERADOR_AE63 = MappingProxyType({
    "cota": _EXISTENTES["cota"],
    "rango_admisible_de_probabilidades_de_la_estrategia": Decision(
        "rango_admisible_de_probabilidades_de_la_estrategia", "humana"),
    "tratamiento_de_omisiones": _EXISTENTES["tratamiento_de_omisiones"],
    "mecanismo_de_sellado_temporal_externo": _EXISTENTES["mecanismo_de_sellado_temporal_externo"],
    "lectura_primaria_pendiente_de_fuentes_secuenciales": _EXISTENTES["lectura_primaria_pendiente_de_fuentes_secuenciales"],
    "papel_y_direccion_de_la_secundaria": _EXISTENTES["papel_y_direccion_de_la_secundaria"],
    "tiempos_supervision": _EXISTENTES["tiempos_supervision"],
})
"""Decisiones del operador que afectan al traslado, todas sin valor. Solo
`rango_admisible_de_probabilidades_de_la_estrategia` es nueva; su alcance
esta en ALCANCE_DE_LA_DECISION_SOBRE_REPORTES."""

ALCANCE_DE_LA_DECISION_SOBRE_REPORTES = (
    "rango_admisible_de_probabilidades_de_la_estrategia solo restringe los reportes de la estrategia; no es evidencia "
    "sobre las marginales reales q_i del sorteo, que siguen pendientes (L2_marginales_reales_en_el_intervalo); la "
    "propiedad estricta de L2_log_loss_estricta_en_D exige ambas cosas")
"""Separa la decision sobre reportes de la cuestion sobre el mecanismo."""
