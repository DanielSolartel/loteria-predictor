"""
Auditoria de las obligaciones de aplicacion F1, F2 y O3 -Etapa AE-65,
validada (solo esta auditoria de obligaciones y sus pruebas; no
acredita anterioridad, filtracion ni unicidad del registro y no autoriza
inferencia ni evaluacion).

AE-64 dejo pendientes tres obligaciones para aplicar al repositorio las
garantias de Choe y Ramdas (arXiv:2110.00115v6): la anterioridad de las
predicciones (F1), la correspondencia de p_t con la filtracion G (F2) y
el tratamiento de omisiones (O3). Para cada una este modulo registra:

1. que garantiza hoy el codigo (posibilidad estructural);
2. que depende de evidencia temporal o externa que el repositorio no
   posee;
3. que decisiones siguen abiertas;
4. que contraejemplos sinteticos detectan una conclusion indebida.

Separa la anterioridad temporal, la dependencia funcional de la salida,
la predictibilidad de gamma (via del teorema 2) y la de xi (uso con
omisiones). La posibilidad estructural no es anterioridad acreditada:
ninguna obligacion cambia de estado, y F1, F2, O3, N2 y U1 siguen
pendientes. No modifica los registros de AE-63 ni de AE-64, no elige
metodo, alfa, lambda, tratamiento de omisiones, mecanismo ni regla y no
autoriza ninguna evaluacion: el expediente sigue en
`expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`. Puro: sin
datos reales, PostgreSQL, reloj, entrenamiento ni predicciones reales.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

NIVELES_DE_ANTERIORIDAD = ("posibilidad_estructural", "acreditada_con_evidencia_externa")
"""El segundo nivel exige un mecanismo externo que sigue sin decidir; en
AE-65 es inalcanzable y ninguna obligacion lo tiene."""

USOS = ("cs_via_teorema_1", "cs_via_teorema_2", "e_proceso_teorema_3", "subsucesion_por_omisiones")


@dataclass(frozen=True)
class Garantia:
    texto: str
    simbolos: tuple[str, ...]


@dataclass(frozen=True)
class Contraejemplo:
    id: str
    descripcion: str
    conclusion_indebida: str


@dataclass(frozen=True)
class Obligacion:
    id: str
    garantiza_hoy: tuple[Garantia, ...]
    depende_de_evidencia_externa: tuple[str, ...]
    decisiones_abiertas: tuple[tuple[str, str], ...]
    contraejemplos: tuple[Contraejemplo, ...]
    estado: str = "pendiente"
    nivel: str = "posibilidad_estructural"


@dataclass(frozen=True)
class Aspecto:
    id: str
    que_exige: str
    referencias: tuple[tuple[str, str], ...]
    aplica_a: tuple[str, ...]


# ---------------------------------------------------------------------------
# Evidencia requerida para O3 (obligacion de evidencia y diseno, sin mecanismo)
# ---------------------------------------------------------------------------

EVIDENCIA_REQUERIDA_O3 = MappingProxyType({
    "cabeza_sellada_antes_del_plazo": "una cabeza de la cadena sellada externamente antes del vencimiento del plazo "
                                      "de cada sorteo",
    "unicidad_y_completitud_de_la_cabeza": "acreditacion de que esa cabeza representa el registro completo y unico en "
                                           "ese momento, sin cadenas paralelas ni bifurcaciones reveladas despues",
    "calendario_oficial": "el calendario oficial que fija el plazo de cada sorteo y el ultimo sorteo ocurrido",
    "ausencia_de_prediccion_valida_al_plazo": "que en ese momento no existia una prediccion valida para ese objetivo",
})
"""Una cabeza sellada no basta por si sola: sin unicidad y completitud
acreditadas, varias cabezas selladas permiten revelar despues la rama
favorable. O3 no se reduce a F1."""

_SELLADO = "mecanismo_de_sellado_temporal_externo"
_DR = "propuesta_inferencia_prospectiva:DECISIONES_REQUERIDAS"
_DA = "propuesta_inferencia_prospectiva:DECISIONES_INFERENCIALES_ABIERTAS"
_AE52 = "registro_prospectivo:PENDIENTES_BORRADOR_AE52"
_AE53 = "especificacion_evaluacion_prospectiva:ESPECIFICACION_CANDIDATA_AE53"
_SEM = "semantica_omisiones_prospectivas:_SIN_DECIDIR"

# ---------------------------------------------------------------------------
# Obligaciones
# ---------------------------------------------------------------------------

OBLIGACIONES_AE65 = MappingProxyType({
    "F1_anterioridad": Obligacion(
        "F1_anterioridad",
        garantiza_hoy=(
            Garantia("la cadena de hashes fija el orden interno y detecta el cambio de cualquier entrada que tenga "
                     "otra detras", ("registro_prospectivo:validar_registro", "registro_prospectivo:hash_entrada")),
            Garantia("una prediccion solo cuenta para objetivos posteriores al corte del protocolo, con entrada "
                     "declarada hasta objetivo - 1, sin sobrescritura ni retroceso de objetivos",
                     ("registro_prospectivo:_validar_prediccion", "registro_prospectivo:nueva_prediccion")),
            Garantia("el resultado va detras de su prediccion en la cadena y no se repite",
                     ("registro_prospectivo:_validar_resultado",)),
            Garantia("un protocolo real queda en borrador y no admite salidas; el resumen declara siempre el "
                     "sellado externo como no verificado",
                     ("registro_prospectivo:construir_protocolo_borrador", "registro_prospectivo:resumir_registro",
                      "registro_prospectivo:ALCANCE_REGISTRO")),
        ),
        depende_de_evidencia_externa=(
            "sello temporal externo de cada salida, o de la cabeza, anterior a cada sorteo",
            "hora oficial de cada sorteo",
            "anclaje externo de la ultima entrada",
            "unicidad_y_completitud_de_la_cabeza",
        ),
        decisiones_abiertas=((_DR, _SELLADO), (_AE52, _SELLADO), (_AE53, _SELLADO)),
        contraejemplos=(
            Contraejemplo("F1a_registro_retroactivo_indistinguible",
                          "un registro construido antes de cada sorteo y otro construido despues de conocerlos son "
                          "identicos byte a byte; ninguna entrada lleva fecha",
                          "que una cadena valida muestre que las salidas son anteriores a los sorteos"),
            Contraejemplo("F1b_oraculo_retroactivo_valida",
                          "un registro fabricado tras conocer los resultados, con 0,9 en los numeros sorteados, "
                          "supera la validacion y el resumen no cambia",
                          "que superar validar_registro excluya la fabricacion posterior"),
            Contraejemplo("F1c_bifurcacion_de_salidas",
                          "dos ramas con salidas distintas para el mismo objetivo, ambas selladas antes del sorteo; "
                          "revelar despues la favorable deja cada salida anterior, pero la salida revelada depende "
                          "del resultado",
                          "que la anterioridad de cada salida sin unicidad de la cabeza haga predecible la salida "
                          "revelada"),
        ),
    ),
    "F2_correspondencia_de_la_filtracion": Obligacion(
        "F2_correspondencia_de_la_filtracion",
        garantiza_hoy=(
            Garantia("la referencia uniforme es determinista y los limites de d_t son constantes: ambos predecibles "
                     "(P4_uniforme_y_limites_predecibles de AE-64)",
                     ("baselines:baseline_uniforme", "verificacion_primaria_choe_ramdas:LECTURA_POR_PUNTO")),
            Garantia("la entrada declarada termina en el sorteo anterior al objetivo (rezago 1 estructural) y el "
                     "resultado entra solo como entrada posterior",
                     ("registro_prospectivo:_validar_historico_entrada", "registro_prospectivo:huella_entrada")),
        ),
        depende_de_evidencia_externa=(
            "anterioridad temporal de la salida (F1)",
            "o bien dependencia funcional acreditada: recomputacion determinista de la salida con el codigo congelado "
            "sobre la entrada declarada, con el codigo fijado antes de los sorteos; la huella de la entrada no la "
            "acredita",
        ),
        decisiones_abiertas=((_DR, _SELLADO), (_AE52, "aprobacion_de_la_estrategia_a_congelar")),
        contraejemplos=(
            Contraejemplo("F2a_misma_huella_salida_dependiente_de_y",
                          "dos predicciones con la misma entrada declarada y salidas construidas a partir de "
                          "resultados distintos superan ambas la validacion",
                          "que la huella de la entrada acredite que la salida no usa informacion de y_t"),
            Contraejemplo("F2b_brier_predecible_frente_a_oraculo",
                          "bajo uniformidad condicional, un p fijado antes de y_t tiene E[d_t] <= 0; el oraculo que "
                          "observa y_t obtiene d_t = B_u - 0,01 > 0 en todo sorteo",
                          "que d_t > 0 muestre habilidad cuando la salida no es predecible"),
            Contraejemplo("F2c_uniformidad_solo_marginal",
                          "con y_t = sigma(y_(t-1)) los sorteos son marginalmente uniformes y un p predecible acierta "
                          "siempre; el calculo exige uniformidad condicional",
                          "que la uniformidad marginal baste para E[d_t] <= 0"),
        ),
    ),
    "O3_tratamiento_de_omisiones": Obligacion(
        "O3_tratamiento_de_omisiones",
        garantiza_hoy=(
            Garantia("la ventana se clasifica en resueltos, futuros, resultado pendiente y omisiones dado el ultimo "
                     "sorteo ocurrido, que aporta quien llama",
                     ("especificacion_evaluacion_prospectiva:validar_secuencia_objetivos",)),
            Garantia("segun la propuesta de AE-53 sin aprobar, cualquier omision deja el juego no evaluable",
                     ("especificacion_evaluacion_prospectiva:ESPECIFICACION_CANDIDATA_AE53",
                      "semantica_omisiones_prospectivas:ALTERNATIVAS_OMISION")),
            Garantia("la cadena impide rellenar un hueco despues de registrar un objetivo posterior",
                     ("registro_prospectivo:_validar_prediccion",)),
            Garantia("O1 (omision predecible) y O2 (omision dependiente del resultado) son derivaciones sobre la ley, "
                     "no comprobaciones sobre un registro",
                     ("traslado_condiciones_inferenciales:CONDICIONES_DE_TRASLADO",)),
        ),
        depende_de_evidencia_externa=tuple(EVIDENCIA_REQUERIDA_O3),
        decisiones_abiertas=((_DR, "tratamiento_de_omisiones"), (_DA, "tiempos_supervision"),
                             (_DR, "momento_y_tiempos_de_analisis"), (_SEM, "ampliar_equivale_a_sustituir"),
                             (_SEM, "serie_consecutiva_posterior_al_corte"), (_DR, _SELLADO)),
        contraejemplos=(
            Contraejemplo("O3a_momento_de_la_omision_indistinguible",
                          "una omision decidida antes del sorteo y otra decidida tras ver un resultado desfavorable "
                          "dan registros identicos y la misma clasificacion; un registro retroactivo no tiene "
                          "omisiones",
                          "que la clasificacion de omisiones muestre que la omision fue predecible"),
            Contraejemplo("O3b_bifurcacion_con_cabezas_selladas",
                          "una rama con prediccion y otra sin ella para el mismo objetivo, ambas con cabeza sellada "
                          "antes del plazo; cualquiera de las dos puede revelarse despues",
                          "que una cabeza sellada sin unicidad y completitud resuelva O3"),
            Contraejemplo("O3c_resultados_retenidos_y_omisiones_finales",
                          "retener un resultado deja la ventana incompleta, no completa; el resumen del registro no "
                          "lista las omisiones posteriores al ultimo objetivo registrado, la secuencia si",
                          "que el resumen del registro muestre todas las omisiones"),
        ),
    ),
})
"""Las tres obligaciones siguen pendientes; F1 no pasa de posibilidad
estructural."""

# ---------------------------------------------------------------------------
# Aspectos de predictibilidad por via y por uso
# ---------------------------------------------------------------------------

ASPECTOS_DE_PREDICTIBILIDAD = MappingProxyType({
    "anterioridad_temporal": Aspecto(
        "anterioridad_temporal",
        "que cada salida p_t se fije antes de y_t; sin sello externo solo hay posibilidad estructural",
        (("CONDICIONES_DE_TRASLADO", "F1_anterioridad"), ("LECTURA_POR_PUNTO", "P4_anterioridad_de_p_t")),
        USOS),
    "dependencia_funcional_de_la_salida": Aspecto(
        "dependencia_funcional_de_la_salida",
        "que la salida sea funcion solo de informacion anterior a y_t; la huella certifica la entrada declarada, no "
        "la funcion que produjo la salida",
        (("CONDICIONES_DE_TRASLADO", "F2_correspondencia_de_la_filtracion"),
         ("ESTADOS_TRAS_AE64", "F2_correspondencia_de_la_filtracion")),
        USOS),
    "gamma_predecible": Aspecto(
        "gamma_predecible",
        "que la sucesion gamma_i sea predecible; condicion propia de la via del teorema 2 y del e-proceso del "
        "teorema 3, que depende del procedimiento sin decidir",
        (("LECTURA_POR_PUNTO", "P1_gamma_predecible"),),
        ("cs_via_teorema_2", "e_proceso_teorema_3")),
    "xi_predecible": Aspecto(
        "xi_predecible",
        "que el indicador de inclusion xi_t sea predecible cuando se usa una subsucesion por omisiones; el estimando "
        "pasa a Delta_t(xi)",
        (("CONDICIONES_DE_TRASLADO", "O3_tratamiento_de_omisiones"), ("LECTURA_POR_PUNTO", "P4_omisiones_predecibles")),
        ("subsucesion_por_omisiones",)),
})
"""gamma y xi no son requisitos para que p_t corresponda a G; se anaden
segun la via y el uso."""

COMPONENTES_DE_F2 = ("anterioridad_temporal", "dependencia_funcional_de_la_salida")

OBSERVACION_DEPENDENCIA_O3_COMUN = (
    "DEPENDENCIAS_DE_N2 de AE-64 incluye O3_tratamiento_de_omisiones en ambas vias como dependencia comun; AE-65 la "
    "documenta como requisito del uso con omisiones (xi predecible), que no puede excluirse mientras "
    "tratamiento_de_omisiones siga sin decidir; el registro de AE-64 no se modifica")

CONSECUENCIAS = MappingProxyType({"N2_inversion_para_p1b": "pendiente", "U1_usos_de_1_sobre_E": "pendiente"})
"""N2 y U1 siguen pendientes; sus dependencias estan en AE-64."""

# ---------------------------------------------------------------------------
# Contraejemplo de Brier
# ---------------------------------------------------------------------------

HIPOTESIS_UNIFORMIDAD_CONDICIONAL = (
    "cada sorteo es uniforme condicionalmente a la informacion disponible antes de predecir: P(y_t = A | G_(t-1)) "
    "= 1/C(43, 5) para todo conjunto A de cinco numeros; de ahi P(i en y_t | G_(t-1)) = 5/43. No basta la "
    "uniformidad marginal, y la hipotesis es una suposicion sobre el mecanismo, no un hecho establecido")


def esperanza_diferencia_brier_bajo_uniformidad_condicional(probabilidades: Sequence[Fraction]) -> Fraction:
    """E[d_t | G_(t-1)] de Brier para un vector p fijado antes de y_t, bajo
    HIPOTESIS_UNIFORMIDAD_CONDICIONAL: -(1/43) suma de (p_i - 5/43)^2, que
    es <= 0 con igualdad solo en la uniforme. No aplica a una salida que
    observe y_t."""
    q = Fraction(5, 43)
    if len(probabilidades) != 43:
        raise ValueError("se esperan 43 probabilidades")
    return -sum((Fraction(p) - q) ** 2 for p in probabilidades) / 43
