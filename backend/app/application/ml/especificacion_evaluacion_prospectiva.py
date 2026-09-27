"""
Contrato preparatorio de una futura evaluacion prospectiva -Etapa
AE-53, validada.

Prepara, antes de que exista cualquier dato prospectivo, tres piezas
verificables:

  1. `ESPECIFICACION_CANDIDATA_AE53`: especificacion candidata, NO
     aprobada, con tres grupos separados: lo que AE-52 ya fijo (copia
     de `REGLAS_EVALUACION_AE52`), propuestas no aprobadas (horizonte,
     omisiones y referencia secundaria) y decisiones pendientes sin
     valor (metodo inferencial, dependencia serial, nivel, efecto
     minimo, multiplicidad y sellado temporal). `huella_especificacion`
     la identifica; no prueba cuando se fijo.
  2. `validar_secuencia_objetivos`: clasifica, para un juego, los
     objetivos de la ventana propuesta en resueltos, con resultado
     pendiente, futuros y omisiones. Es estructural: no calcula ningun
     resultado estadistico.
  3. `metricas_por_sorteo`: Log Loss, Brier y Precision@5/Recall@5 de
     un unico sorteo con las definiciones vigentes (`metricas.evaluar`
     y `baselines.baseline_uniforme`), sin agregar entre sorteos.

No hay bootstrap, prueba de signos, intervalos, agregados ni
veredictos: la inferencia la elegira una etapa posterior. No cierra
ningun pendiente del borrador de AE-52 y no modifica el NO-GO de AE-39,
el bloqueo de AE-41 ni las condiciones de AE-46. No entrena, no carga
modelos y no lee datos: solo recibe valores del llamador, y en AE-53
no tiene llamadores fuera de sus pruebas sinteticas. El modulo no
puede saber si esos valores son sinteticos o reales.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from app.application.ml.baselines import baseline_uniforme
from app.application.ml.metricas import evaluar
from app.application.ml.registro_prospectivo import REGLAS_EVALUACION_AE52
from app.application.ml.tipos import FilaCandidato, MetricasEvaluacion
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame

_PROPUESTA = "propuesta_no_aprobada"
_HORIZONTE_PROPUESTO = REGLAS_EVALUACION_AE52["minimo_sorteos_resueltos_por_juego"]

ESPECIFICACION_CANDIDATA_AE53 = {
    "esquema": "especificacion-evaluacion-prospectiva-ml/1.0",
    "etapa": "AE-53",
    "estado": "candidata_no_aprobada",
    "fijado_por_ae52": copy.deepcopy(REGLAS_EVALUACION_AE52),
    "propuestas": {
        "horizonte": {
            "valor_propuesto": {"objetivos": _HORIZONTE_PROPUESTO, "desde": "primer_objetivo_posterior_al_corte",
                                "analisis": "unico_al_completar_el_horizonte"},
            "estado": _PROPUESTA,
        },
        "omisiones": {"valor_propuesto": "cualquier_omision_en_el_horizonte_no_evaluable", "estado": _PROPUESTA},
        "referencia_secundaria": {
            "valor_propuesto": "definicion_vigente_uniforme_con_desempate_determinista_pareada_por_sorteo",
            "estado": _PROPUESTA,
        },
    },
    "pendientes": {
        nombre: {"valor": None, "estado": "pendiente"}
        for nombre in (
            "unidad_y_metodo_inferencial", "tratamiento_dependencia_serial", "nivel_y_umbral", "efecto_minimo",
            "multiplicidad_entre_juegos", "mecanismo_de_sellado_temporal_externo",
        )
    },
    "nota": (
        "Especificacion candidata de AE-53: no aprueba ninguna regla, no cierra los pendientes del borrador de AE-52 "
        "y no modifica el NO-GO de AE-39. Las propuestas no estan aprobadas y los pendientes no tienen valor. La "
        "huella identifica este texto exacto y detecta cambios, pero no prueba cuando se fijo: la anterioridad "
        "exige un anclaje temporal externo, que sigue pendiente."
    ),
}
"""Especificacion candidata. Nunca contiene un estado aprobado."""

_JUEGOS = MappingProxyType({"BALOTO": BalotoGame, "BALOTO_REVANCHA": BalotoRevanchaGame})


class EspecificacionProspectivaError(ValueError):
    """Entrada invalida para el contrato preparatorio de AE-53."""


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


# ---------------------------------------------------------------------------
# Huella de la especificacion
# ---------------------------------------------------------------------------

def serializar_especificacion(especificacion: dict | None = None) -> bytes:
    """JSON canonico (mismo formato que las entradas de AE-52): claves
    ordenadas, sin espacios, UTF-8 y terminado en LF."""
    datos = ESPECIFICACION_CANDIDATA_AE53 if especificacion is None else especificacion
    texto = json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return (texto + "\n").encode("utf-8")


def huella_especificacion(especificacion: dict | None = None) -> str:
    """SHA-256 del JSON canonico. Identifica la especificacion y detecta
    cambios; no es un sello temporal."""
    return hashlib.sha256(serializar_especificacion(especificacion)).hexdigest()


# ---------------------------------------------------------------------------
# Secuencia de objetivos de un juego
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InformeSecuenciaObjetivos:
    """Clasificacion estructural de la ventana propuesta de un juego.

    - `resueltos`: objetivos con prediccion y resultado.
    - `resultado_pendiente`: el sorteo ya ocurrio y tiene prediccion,
      pero su resultado aun no se incorporo.
    - `futuros`: el sorteo aun no ocurrio (con o sin prediccion).
    - `omisiones`: el sorteo ya ocurrio y no tiene prediccion.
    - `fuera_de_horizonte`: predicciones posteriores a la ventana; no
      la extienden.
    """
    ventana_desde: int
    ventana_hasta: int
    horizonte: int
    resueltos: tuple[int, ...]
    resultado_pendiente: tuple[int, ...]
    futuros: tuple[int, ...]
    omisiones: tuple[int, ...]
    fuera_de_horizonte: tuple[int, ...]
    estado: str
    motivo: str
    reglas_aplicadas: MappingProxyType = field(default_factory=lambda: MappingProxyType({
        "horizonte": _PROPUESTA, "omisiones": _PROPUESTA,
    }))


def _objetivos(valores, nombre: str, corte: int) -> set[int]:
    lista = list(valores)
    if not all(_es_entero(v) for v in lista):
        raise EspecificacionProspectivaError(f"{nombre} debe contener solo enteros")
    if len(set(lista)) != len(lista):
        raise EspecificacionProspectivaError(f"{nombre} contiene objetivos duplicados")
    anteriores = [v for v in lista if v <= corte]
    if anteriores:
        raise EspecificacionProspectivaError(
            f"{nombre} contiene objetivos iguales o anteriores al corte {corte}: {sorted(anteriores)}"
        )
    return set(lista)


def validar_secuencia_objetivos(*, corte: int, ultimo_sorteo_ocurrido: int,
                                objetivos_con_prediccion: Sequence[int],
                                objetivos_con_resultado: Sequence[int]) -> InformeSecuenciaObjetivos:
    """Clasifica la ventana `corte+1..corte+horizonte` de un juego.

    `ultimo_sorteo_ocurrido` es el ultimo sorteo que ya se celebro,
    tenga o no resultado incorporado. Es la unica forma de distinguir
    un objetivo futuro (todavia no celebrado) de una omision (celebrado
    sin prediccion). Aplica solo las propuestas no aprobadas de
    horizonte y omisiones; no calcula ningun resultado estadistico."""
    if not _es_entero(corte):
        raise EspecificacionProspectivaError("corte debe ser un entero")
    if not _es_entero(ultimo_sorteo_ocurrido) or ultimo_sorteo_ocurrido < corte:
        raise EspecificacionProspectivaError("ultimo_sorteo_ocurrido debe ser un entero igual o posterior al corte")
    con_prediccion = _objetivos(objetivos_con_prediccion, "objetivos_con_prediccion", corte)
    con_resultado = _objetivos(objetivos_con_resultado, "objetivos_con_resultado", corte)
    sin_prediccion = sorted(con_resultado - con_prediccion)
    if sin_prediccion:
        raise EspecificacionProspectivaError(f"Hay resultados sin prediccion previa: {sin_prediccion}")
    no_ocurridos = sorted(o for o in con_resultado if o > ultimo_sorteo_ocurrido)
    if no_ocurridos:
        raise EspecificacionProspectivaError(f"Hay resultados de sorteos que aun no ocurrieron: {no_ocurridos}")

    horizonte = _HORIZONTE_PROPUESTO
    desde, hasta = corte + 1, corte + horizonte
    resueltos, pendientes, futuros, omisiones = [], [], [], []
    for objetivo in range(desde, hasta + 1):
        if objetivo in con_resultado:
            resueltos.append(objetivo)
        elif objetivo > ultimo_sorteo_ocurrido:
            futuros.append(objetivo)
        elif objetivo in con_prediccion:
            pendientes.append(objetivo)
        else:
            omisiones.append(objetivo)

    if omisiones:
        estado = "no_evaluable_por_omision"
        motivo = (f"Sorteos celebrados sin prediccion dentro del horizonte: {omisiones}. Segun la propuesta no "
                  "aprobada de omisiones, el juego no seria evaluable; no se sustituyen ni se amplia la ventana.")
    elif len(resueltos) == horizonte:
        estado = "completa"
        motivo = f"Los {horizonte} objetivos del horizonte propuesto tienen prediccion y resultado."
    else:
        estado = "incompleta"
        motivo = (f"{len(resueltos)} de {horizonte} objetivos resueltos; {len(pendientes)} con resultado pendiente "
                  f"y {len(futuros)} futuros.")
    return InformeSecuenciaObjetivos(
        ventana_desde=desde, ventana_hasta=hasta, horizonte=horizonte, resueltos=tuple(resueltos),
        resultado_pendiente=tuple(pendientes), futuros=tuple(futuros), omisiones=tuple(omisiones),
        fuera_de_horizonte=tuple(sorted(o for o in con_prediccion if o > hasta)), estado=estado, motivo=motivo,
    )


# ---------------------------------------------------------------------------
# Metricas de un unico sorteo con las definiciones vigentes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricasSorteo:
    """Metricas de un unico sorteo: estrategia, referencia uniforme y
    diferencias orientadas como uniforme - estrategia. Descriptivas:
    no implican ninguna inferencia."""
    codigo_juego: str
    sorteo_objetivo: int
    estrategia: MetricasEvaluacion
    uniforme: MetricasEvaluacion
    diferencias: MappingProxyType


def _filas_del_sorteo(codigo: str, objetivo: int, numeros: set[int], rango_min: int, rango_max: int) -> list:
    """Filas minimas para las funciones de metricas: solo cuentan
    `sorteo_objetivo`, `numero_candidato` y `etiqueta`; las features
    quedan neutras porque las metricas no las usan."""
    return [FilaCandidato(
        codigo_juego=codigo, sorteo_objetivo=objetivo, calculado_hasta_sorteo=objetivo - 1, numero_candidato=n,
        etiqueta=1 if n in numeros else 0, frecuencia_acumulada=0.0, frecuencia_ventana_10=0.0,
        frecuencia_ventana_20=0.0, frecuencia_ventana_50=0.0, sorteos_desde_ultima_aparicion=None,
        aparecio_en_sorteo_anterior=0,
    ) for n in range(rango_min, rango_max + 1)]


def metricas_por_sorteo(codigo_juego: str, sorteo_objetivo: int, probabilidades: Sequence[float],
                        numeros: Sequence[int]) -> MetricasSorteo:
    """Metricas de un sorteo con `metricas.evaluar` y
    `baselines.baseline_uniforme`, sin redefinirlas. Comprueba que
    Precision@5 = Recall@5, que es una identidad cuando se eligen 5
    numeros y salen 5."""
    if codigo_juego not in _JUEGOS:
        raise EspecificacionProspectivaError(f"Juego no autorizado: {codigo_juego!r}")
    if not _es_entero(sorteo_objetivo):
        raise EspecificacionProspectivaError("sorteo_objetivo debe ser un entero")
    juego = _JUEGOS[codigo_juego]()
    rango_min, rango_max = juego.number_range
    cantidad = juego.numbers_to_pick
    tamano = rango_max - rango_min + 1
    if (isinstance(probabilidades, (str, bytes)) or len(probabilidades) != tamano
            or not all(isinstance(p, float) and math.isfinite(p) and 0.0 < p < 1.0 for p in probabilidades)):
        raise EspecificacionProspectivaError(f"Se requieren {tamano} probabilidades reales en (0, 1), una por numero")
    lista = list(numeros)
    if (len(lista) != cantidad or not all(_es_entero(n) for n in lista) or len(set(lista)) != cantidad
            or min(lista) < rango_min or max(lista) > rango_max):
        raise EspecificacionProspectivaError(
            f"numeros debe contener {cantidad} enteros distintos en [{rango_min}, {rango_max}]"
        )
    filas = _filas_del_sorteo(codigo_juego, sorteo_objetivo, set(lista), rango_min, rango_max)
    estrategia = evaluar(filas, list(probabilidades))
    uniforme = baseline_uniforme(filas, rango_min, rango_max, cantidad).metricas
    for nombre, metricas in (("estrategia", estrategia), ("uniforme", uniforme)):
        if metricas.precision_en_5 != metricas.recall_en_5:
            raise EspecificacionProspectivaError(
                f"Precision@5 y Recall@5 de {nombre} difieren en un sorteo con {cantidad} numeros: la identidad no se cumple"
            )
    diferencias = MappingProxyType({
        metrica: getattr(uniforme, metrica) - getattr(estrategia, metrica)
        for metrica in ("log_loss", "brier_score", "precision_en_5")
    })
    return MetricasSorteo(codigo_juego=codigo_juego, sorteo_objetivo=sorteo_objetivo, estrategia=estrategia,
                          uniforme=uniforme, diferencias=diferencias)
