"""
Semantica de omisiones prospectivas -Etapa AE-58, validada (solo la
semantica descriptiva, la deteccion de divergencias y sus pruebas; no
aprueba ninguna alternativa ante omisiones, el horizonte de AE-53, una
regla inferencial ni la evaluacion operativa).

Formaliza, para un juego, cuatro nociones distintas:

- objetivo: posicion `corte+1..corte+100` de la ventana PROPUESTA por
  AE-53 (no aprobada);
- prediccion registrada;
- sorteo ocurrido: `<= ultimo_sorteo_ocurrido`;
- resultado resuelto.

Con ellas informa hechos (omisiones en la ventana, resueltos consecutivos
desde el corte, recuento descriptivo como el de AE-52) y las
CONSECUENCIAS de cada alternativa ante una omision, sin elegir, aprobar
ni recomendar ninguna. Un recuento de 100 tras una omision es
hipotetico: nunca significa que se alcance el minimo de AE-52, que fija
sorteos consecutivos sin sustitucion y omisiones informadas sin
sustituirlas. Ninguna alternativa autoriza una evaluacion: el NO-GO de
AE-39, AE-41 y `regla_estadistica_de_decision` siguen vigentes.

Reutiliza `validar_secuencia_objetivos` de AE-53 sin modificarla y anade
el invariante de entrada de AE-52: predecir el sorteo `o` exige una
entrada que termina en `o - 1`, asi que ninguna prediccion puede ser
posterior a `ultimo_sorteo_ocurrido + 1`. No calcula metricas, no agrega
y no lee datos: solo recibe numeros de sorteo del llamador.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.ml.especificacion_evaluacion_prospectiva import (
    ESPECIFICACION_CANDIDATA_AE53,
    InformeSecuenciaObjetivos,
    validar_secuencia_objetivos,
)
from app.application.ml.registro_prospectivo import REGLAS_EVALUACION_AE52

ALTERNATIVAS_OMISION = ("no_evaluable", "ventana_fija_sin_ampliar", "ampliar_ventana", "reemplazar_objetivo")
ORIGENES = ("propuesta_ae53_no_aprobada", "sin_decidir")
ESTADOS_RECUENTO = ("alcanza_100_hipotetico", "no_puede_alcanzar_100", "puede_alcanzar_100")
RELACIONES_AE52 = ("incompatible_con_minimo", "incompatible_con_sin_sustitucion",
                   "no_establecida_requiere_interpretacion", "sin_conflicto_conocido")

_MINIMO_AE52 = 100
_VALORES_FIJADOS_AE52 = {
    "minimo_sorteos_resueltos_por_juego": _MINIMO_AE52,
    "sin_agregados_antes_del_minimo": True,
    "sorteos_consecutivos_sin_sustitucion": True,
}
"""Reglas de AE-52 de las que depende AE-58, con su valor esperado exacto."""
_FIJADO_POR_AE52 = tuple(sorted(_VALORES_FIJADOS_AE52))
_PROPUESTAS_ESPERADAS_AE53 = {
    "horizonte": {"objetivos": _MINIMO_AE52, "desde": "primer_objetivo_posterior_al_corte",
                  "analisis": "unico_al_completar_el_horizonte"},
    "omisiones": "cualquier_omision_en_el_horizonte_no_evaluable",
}
"""Propuestas de AE-53 de las que depende AE-58, con su valor propuesto exacto."""
_PROPUESTO_POR_AE53 = tuple(sorted(_PROPUESTAS_ESPERADAS_AE53))
_SIN_DECIDIR = ("ampliar_equivale_a_sustituir", "serie_consecutiva_posterior_al_corte", "tratamiento_de_omisiones")


class SemanticaOmisionesError(ValueError):
    """Entrada imposible bajo las reglas de registro de AE-52."""


class BaseDivergenteError(SemanticaOmisionesError):
    """Las reglas de AE-52 o las propuestas de AE-53 no son las que AE-58 supone."""


def _igual_estricto(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_igual_estricto(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def verificar_base_ae52_ae53() -> None:
    """Comprueba explicitamente que las reglas fijadas por AE-52 y las
    propuestas de AE-53 de las que depende AE-58 existen, tienen el valor
    esperado y que las propuestas siguen sin aprobar. Cualquier
    divergencia (clave ausente, valor o estado distinto) lanza
    `BaseDivergenteError`; nunca se filtra en silencio.

    AE-59 anade: ambas constantes deben ser dict; la especificacion debe
    seguir en `candidata_no_aprobada`; cada propuesta usada tiene
    exactamente las claves `estado` y `valor_propuesto`; y la copia
    `fijado_por_ae52` de AE-53 debe ser estrictamente igual a
    `REGLAS_EVALUACION_AE52`."""
    if not isinstance(REGLAS_EVALUACION_AE52, dict):
        raise BaseDivergenteError("REGLAS_EVALUACION_AE52 no es un objeto")
    if not isinstance(ESPECIFICACION_CANDIDATA_AE53, dict):
        raise BaseDivergenteError("ESPECIFICACION_CANDIDATA_AE53 no es un objeto")
    faltan = sorted(k for k in _VALORES_FIJADOS_AE52 if k not in REGLAS_EVALUACION_AE52)
    if faltan:
        raise BaseDivergenteError(f"Faltan reglas fijadas por AE-52: {faltan}")
    distintas = sorted(k for k, v in _VALORES_FIJADOS_AE52.items() if not _igual_estricto(REGLAS_EVALUACION_AE52[k], v))
    if distintas:
        raise BaseDivergenteError(f"Reglas de AE-52 con un valor distinto del esperado: {distintas}")
    if ESPECIFICACION_CANDIDATA_AE53.get("estado") != "candidata_no_aprobada":
        raise BaseDivergenteError("La especificacion de AE-53 ya no esta en estado candidata_no_aprobada")
    if not _igual_estricto(ESPECIFICACION_CANDIDATA_AE53.get("fijado_por_ae52"), REGLAS_EVALUACION_AE52):
        raise BaseDivergenteError("La copia fijado_por_ae52 de AE-53 difiere de REGLAS_EVALUACION_AE52")
    propuestas = ESPECIFICACION_CANDIDATA_AE53.get("propuestas")
    if not isinstance(propuestas, dict):
        raise BaseDivergenteError("La especificacion de AE-53 no tiene propuestas")
    faltan = sorted(k for k in _PROPUESTAS_ESPERADAS_AE53 if k not in propuestas)
    if faltan:
        raise BaseDivergenteError(f"Faltan propuestas de AE-53: {faltan}")
    for clave, valor in _PROPUESTAS_ESPERADAS_AE53.items():
        propuesta = propuestas[clave]
        if not isinstance(propuesta, dict) or set(propuesta) != {"estado", "valor_propuesto"}:
            raise BaseDivergenteError(f"La propuesta {clave} de AE-53 no tiene exactamente estado y valor_propuesto")
        if propuesta.get("estado") != "propuesta_no_aprobada":
            raise BaseDivergenteError(f"La propuesta {clave} de AE-53 ya no esta en estado propuesta_no_aprobada")
        if not _igual_estricto(propuesta.get("valor_propuesto"), valor):
            raise BaseDivergenteError(f"La propuesta {clave} de AE-53 tiene un valor distinto del esperado")


@dataclass(frozen=True)
class ConsecuenciaAlternativa:
    """Consecuencia HIPOTETICA de una alternativa ante las omisiones.

    - `conjunto_hipotetico_contado`: resultados que esa alternativa
      contaria ahora.
    - `estado_recuento_hipotetico`: aritmetico y dependiente del momento;
      nunca significa minimo de AE-52 alcanzado.
    - `relacion_con_reglas_ae52`: relacion con las reglas fijadas;
      `sin_conflicto_conocido` no afirma que se cumplan.
    - `autoriza_evaluacion`: siempre False."""

    alternativa: str
    origen: str
    conjunto_hipotetico_contado: tuple[int, ...]
    recuento_hipotetico: int
    estado_recuento_hipotetico: str
    relacion_con_reglas_ae52: str
    autoriza_evaluacion: bool = False


@dataclass(frozen=True)
class InformeOmisiones:
    """Hechos de un juego y consecuencias de cada alternativa.

    `total_resueltos_descriptivo` y `faltantes_como_en_resumen_ae52` son
    recuentos descriptivos, iguales a los del resumen de AE-52: incluyen
    resultados posteriores a la ventana y no son elegibilidad. Los
    objetivos anteriores o iguales al corte y los sorteos no ocurridos se
    rechazan en la entrada, asi que nunca cuentan.
    `resueltos_consecutivos_desde_el_corte` no tiene tope."""

    corte: int
    ultimo_sorteo_ocurrido: int
    objetivos: tuple[int, ...]
    predicciones_registradas: tuple[int, ...]
    sorteos_ocurridos_en_ventana: tuple[int, ...]
    resultados_resueltos: tuple[int, ...]
    omisiones_en_ventana: tuple[int, ...]
    resueltos_consecutivos_desde_el_corte: int
    cien_consecutivos_desde_el_corte: bool
    total_resueltos_descriptivo: int
    faltantes_como_en_resumen_ae52: int
    secuencia_ae53: InformeSecuenciaObjetivos
    estado_segun_propuesta_ae53: str
    consecuencias: tuple[ConsecuenciaAlternativa, ...]
    fijado_por_ae52: tuple[str, ...]
    propuesto_por_ae53: tuple[str, ...]
    sin_decidir: tuple[str, ...]
    decision: str = "sin_decidir"
    autoriza_evaluacion: bool = False


def _estado_recuento(recuento: int, puede_crecer: bool) -> str:
    if recuento >= _MINIMO_AE52:
        return "alcanza_100_hipotetico"
    return "puede_alcanzar_100" if puede_crecer else "no_puede_alcanzar_100"


def _ventana_ampliada(corte: int, ultimo: int, predicciones: set[int]) -> tuple[int, ...]:
    """Primeros 100 sorteos posteriores al corte que NO son omisiones
    (AE-59): los ocurridos con prediccion y, despues, los futuros. Los
    resultados pendientes y los futuros ocupan su lugar; solo una omision
    (sorteo ocurrido sin prediccion) cede su lugar al siguiente.

    Trabajo acotado por la cantidad de predicciones y los 100 lugares:
    nunca recorre el intervalo `corte..ultimo`, que puede ser muy grande.
    Como las predicciones ocurridas son `<= ultimo` y los futuros
    `> ultimo`, el orden coincide con el recorrido sorteo a sorteo."""
    ocurridas = sorted(o for o in predicciones if corte < o <= ultimo)[:_MINIMO_AE52]
    inicio = max(corte + 1, ultimo + 1)
    return tuple(ocurridas) + tuple(range(inicio, inicio + _MINIMO_AE52 - len(ocurridas)))


def _consecuencias(ventana: set[int], ampliada: tuple[int, ...], resueltos: tuple[int, ...],
                   hay_omision: bool) -> tuple:
    en_ventana = tuple(o for o in resueltos if o in ventana)
    # AE-59: ampliar y reemplazar cuentan los resueltos de la ventana ampliada
    # solo por omisiones; un resultado pendiente no se salta.
    en_ampliada = set(ampliada)
    ampliado = tuple(o for o in resueltos if o in en_ampliada)
    relaciones = {
        "no_evaluable": "sin_conflicto_conocido",
        "ventana_fija_sin_ampliar": "incompatible_con_minimo" if hay_omision else "sin_conflicto_conocido",
        # Mismo conjunto contado que reemplazar: admitirlo exigiria decidir
        # que ampliar no es sustituir. No es un permiso operativo.
        "ampliar_ventana": "no_establecida_requiere_interpretacion" if hay_omision else "sin_conflicto_conocido",
        "reemplazar_objetivo": "incompatible_con_sin_sustitucion" if hay_omision else "sin_conflicto_conocido",
    }
    contados = {"no_evaluable": en_ventana, "ventana_fija_sin_ampliar": en_ventana,
                "ampliar_ventana": ampliado, "reemplazar_objetivo": ampliado}
    puede_crecer = {"no_evaluable": not hay_omision, "ventana_fija_sin_ampliar": not hay_omision,
                    "ampliar_ventana": True, "reemplazar_objetivo": True}
    return tuple(
        ConsecuenciaAlternativa(
            alternativa=a, origen="propuesta_ae53_no_aprobada" if a == "no_evaluable" else "sin_decidir",
            conjunto_hipotetico_contado=contados[a], recuento_hipotetico=len(contados[a]),
            estado_recuento_hipotetico=_estado_recuento(len(contados[a]), puede_crecer[a]),
            relacion_con_reglas_ae52=relaciones[a],
        )
        for a in ALTERNATIVAS_OMISION
    )


def analizar_omisiones(*, corte: int, ultimo_sorteo_ocurrido: int, objetivos_con_prediccion: Sequence[int],
                       objetivos_con_resultado: Sequence[int]) -> InformeOmisiones:
    """Hechos y consecuencias de cada alternativa ante las omisiones de un
    juego. Valida las entradas como AE-53 (sus errores se propagan) y
    ademas el invariante de AE-52: ninguna prediccion posterior a
    `ultimo_sorteo_ocurrido + 1`. Antes verifica la base de AE-52 y AE-53
    (`verificar_base_ae52_ae53`). No decide, no aprueba y no autoriza."""
    verificar_base_ae52_ae53()
    prediccion = list(objetivos_con_prediccion)
    resultado = list(objetivos_con_resultado)
    secuencia = validar_secuencia_objetivos(corte=corte, ultimo_sorteo_ocurrido=ultimo_sorteo_ocurrido,
                                            objetivos_con_prediccion=prediccion,
                                            objetivos_con_resultado=resultado)
    imposibles = sorted(o for o in prediccion if o > ultimo_sorteo_ocurrido + 1)
    if imposibles:
        raise SemanticaOmisionesError(
            f"Predicciones posteriores a ultimo_sorteo_ocurrido + 1 ({ultimo_sorteo_ocurrido + 1}): {imposibles}. "
            "Bajo AE-52 predecir el sorteo o exige una entrada que termina en o - 1, que ya debe haber ocurrido."
        )

    objetivos = tuple(range(secuencia.ventana_desde, secuencia.ventana_hasta + 1))
    ventana = set(objetivos)
    resueltos = tuple(sorted(resultado))
    conjunto_resueltos = set(resueltos)
    consecutivos = 0
    while corte + consecutivos + 1 in conjunto_resueltos:
        consecutivos += 1
    omisiones = secuencia.omisiones
    return InformeOmisiones(
        corte=corte,
        ultimo_sorteo_ocurrido=ultimo_sorteo_ocurrido,
        objetivos=objetivos,
        predicciones_registradas=tuple(sorted(prediccion)),
        sorteos_ocurridos_en_ventana=tuple(o for o in objetivos if o <= ultimo_sorteo_ocurrido),
        resultados_resueltos=resueltos,
        omisiones_en_ventana=omisiones,
        resueltos_consecutivos_desde_el_corte=consecutivos,
        cien_consecutivos_desde_el_corte=consecutivos >= _MINIMO_AE52,
        total_resueltos_descriptivo=len(resueltos),
        faltantes_como_en_resumen_ae52=max(0, _MINIMO_AE52 - len(resueltos)),
        secuencia_ae53=secuencia,
        estado_segun_propuesta_ae53=secuencia.estado,
        consecuencias=_consecuencias(ventana, _ventana_ampliada(corte, ultimo_sorteo_ocurrido, set(prediccion)),
                                     resueltos, bool(omisiones)),
        fijado_por_ae52=_FIJADO_POR_AE52,
        propuesto_por_ae53=_PROPUESTO_POR_AE53,
        sin_decidir=_SIN_DECIDIR,
    )
