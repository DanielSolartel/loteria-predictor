"""
Diagnostico estructurado del bloqueo predictivo -Etapa AE-46,
validada.

Explica, por juego, POR QUE la prediccion sigue bloqueada y que
condiciones faltan, sin habilitar nada. Traduce, sin reevaluarlos:
- el reporte operativo de AE-41 (y el de elegibilidad de AE-40 que
  lleva anidado) en un progreso de sorteos nuevos desde 2706;
- la decision validada de AE-39 en la condicion cientifica;
- `resolver_prediccion` (AE-43) en el estado y los motivos, que se
  reutilizan tal cual para que diagnostico y reporte nunca discrepen.

Dos condiciones no tienen ningun mecanismo en AE-46 -protocolo
prospectivo prerregistrado y evaluacion prospectiva positiva- y por
tanto siempre estan pendientes: ningun diagnostico puede ser
desbloqueable. Alcanzar el minimo de sorteos nuevos no cambia la
decision de AE-39. Nunca produce numeros, combinaciones,
probabilidades ni confianza; no consulta repositorios ni el reloj."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.application.ml.prediccion_bloqueada import resolver_prediccion
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import (
    DecisionContinuidadML,
    EstadoAutorizacionOperativaML,
    EstadoElegibilidadReaperturaML,
    EstadoPrediccionML,
    ReporteAutorizacionOperativaML,
)
from app.application.ml.ventanas_temporales import INICIO_HOLDOUT


class CondicionDesbloqueoML(Enum):
    """Conjunto CERRADO de condiciones, en el orden en que se reportan.
    Cumplirlas todas no existe como camino en AE-46: las dos ultimas
    no tienen mecanismo."""

    NUMERACION_HOLDOUT_VALIDA = "numeracion_holdout_valida"
    MINIMO_SORTEOS_NUEVOS = "minimo_sorteos_nuevos"
    EVIDENCIA_CIENTIFICA_AE39 = "evidencia_cientifica_ae39"
    PROTOCOLO_PROSPECTIVO_PRERREGISTRADO = "protocolo_prospectivo_prerregistrado"
    EVALUACION_PROSPECTIVA_POSITIVA = "evaluacion_prospectiva_positiva"


CONDICIONES_SIN_MECANISMO_AE46 = frozenset({
    CondicionDesbloqueoML.PROTOCOLO_PROSPECTIVO_PRERREGISTRADO,
    CondicionDesbloqueoML.EVALUACION_PROSPECTIVA_POSITIVA,
})


class DiagnosticoBloqueoInvalidoError(ValueError):
    """Entradas de tipo incorrecto, juego no autorizado o reportes de
    AE-40/41 incoherentes entre si."""


@dataclass(frozen=True)
class EstadoCondicionDesbloqueo:
    condicion: CondicionDesbloqueoML
    cumplida: bool
    detalle: str

    def __post_init__(self) -> None:
        if not isinstance(self.condicion, CondicionDesbloqueoML):
            raise ValueError("condicion debe ser un CondicionDesbloqueoML")
        if not isinstance(self.cumplida, bool):
            raise ValueError("cumplida debe ser bool")
        if not self.detalle.strip():
            raise ValueError("detalle es obligatorio")


@dataclass(frozen=True)
class ProgresoSorteosNuevos:
    """Progreso de sorteos nuevos desde 2706, copiado del reporte de
    AE-40. Solo `faltantes` se deriva aqui (`minimo - total`, nunca
    negativo). Sin reporte de AE-40 (numeracion invalida) no es
    evaluable y todas las cifras son `None`."""
    evaluable: bool
    desde_numero_sorteo: int
    total_sorteos_nuevos: int | None
    minimo_requerido: int | None
    faltantes: int | None
    numero_sorteo_objetivo_minimo: int | None

    def __post_init__(self) -> None:
        cifras = (self.total_sorteos_nuevos, self.minimo_requerido, self.faltantes, self.numero_sorteo_objetivo_minimo)
        if not self.evaluable:
            if any(c is not None for c in cifras):
                raise ValueError("un progreso no evaluable no puede llevar cifras")
            return
        if any(isinstance(c, bool) or not isinstance(c, int) for c in cifras):
            raise ValueError("un progreso evaluable exige cifras enteras")
        if self.total_sorteos_nuevos < 0 or self.minimo_requerido <= 0:
            raise ValueError("total_sorteos_nuevos debe ser >= 0 y minimo_requerido > 0")
        if self.faltantes != max(0, self.minimo_requerido - self.total_sorteos_nuevos):
            raise ValueError("faltantes debe ser max(0, minimo_requerido - total_sorteos_nuevos)")


@dataclass(frozen=True)
class DiagnosticoBloqueoJuego:
    """Diagnostico de un juego. `estado` y `motivos` son los de
    `resolver_prediccion`; `condiciones` lleva una entrada por cada
    `CondicionDesbloqueoML`, en orden. Nunca contiene salidas
    predictivas y `desbloqueable` es siempre `False` en AE-46."""
    juego_codigo: str
    estado: EstadoPrediccionML
    motivos: tuple[EstadoPrediccionML, ...]
    progreso: ProgresoSorteosNuevos
    condiciones: tuple[EstadoCondicionDesbloqueo, ...]
    desbloqueable: bool = False

    def __post_init__(self) -> None:
        if self.desbloqueable is not False:
            raise ValueError("desbloqueable debe ser siempre False en AE-46")
        if not self.motivos or self.estado is not self.motivos[0]:
            raise ValueError("estado debe ser el primer motivo y motivos no puede estar vacio")
        if [c.condicion for c in self.condiciones] != list(CondicionDesbloqueoML):
            raise ValueError("condiciones debe tener una entrada por condicion, en orden")
        cumplidas = {c.condicion: c.cumplida for c in self.condiciones}
        for condicion in CONDICIONES_SIN_MECANISMO_AE46:
            if cumplidas[condicion]:
                raise ValueError(f"{condicion.name} no tiene mecanismo en AE-46 y no puede estar cumplida")
        if cumplidas[CondicionDesbloqueoML.NUMERACION_HOLDOUT_VALIDA] != self.progreso.evaluable:
            raise ValueError("la numeracion es valida si y solo si el progreso es evaluable")
        minimo_alcanzado = self.progreso.evaluable and self.progreso.faltantes == 0
        if cumplidas[CondicionDesbloqueoML.MINIMO_SORTEOS_NUEVOS] != minimo_alcanzado:
            raise ValueError("MINIMO_SORTEOS_NUEVOS debe coincidir con faltantes == 0")
        sin_no_go = EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO not in self.motivos
        if cumplidas[CondicionDesbloqueoML.EVIDENCIA_CIENTIFICA_AE39] != sin_no_go:
            raise ValueError("EVIDENCIA_CIENTIFICA_AE39 debe coincidir con la ausencia del motivo NO-GO")

    @property
    def condiciones_pendientes(self) -> tuple[CondicionDesbloqueoML, ...]:
        return tuple(c.condicion for c in self.condiciones if not c.cumplida)


def _progreso(autorizacion: ReporteAutorizacionOperativaML) -> ProgresoSorteosNuevos:
    elegibilidad = autorizacion.reporte_elegibilidad
    if elegibilidad is None:
        return ProgresoSorteosNuevos(
            evaluable=False, desde_numero_sorteo=INICIO_HOLDOUT, total_sorteos_nuevos=None,
            minimo_requerido=None, faltantes=None, numero_sorteo_objetivo_minimo=None,
        )
    progreso = ProgresoSorteosNuevos(
        evaluable=True,
        desde_numero_sorteo=elegibilidad.proximo_holdout_inicio,
        total_sorteos_nuevos=elegibilidad.total_sorteos_nuevos,
        minimo_requerido=elegibilidad.minimo_sorteos_nuevos_requeridos,
        faltantes=max(0, elegibilidad.minimo_sorteos_nuevos_requeridos - elegibilidad.total_sorteos_nuevos),
        numero_sorteo_objetivo_minimo=elegibilidad.numero_sorteo_objetivo_minimo,
    )
    elegible = elegibilidad.estado is EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO
    if elegible != (progreso.faltantes == 0):
        raise DiagnosticoBloqueoInvalidoError(
            f"Reporte de AE-40 incoherente para {autorizacion.juego_codigo}: estado {elegibilidad.estado.value} "
            f"con {progreso.faltantes} sorteos faltantes"
        )
    return progreso


def _condiciones(
    autorizacion: ReporteAutorizacionOperativaML,
    decision: DecisionContinuidadML,
    progreso: ProgresoSorteosNuevos,
) -> tuple[EstadoCondicionDesbloqueo, ...]:
    if progreso.evaluable:
        numeracion = EstadoCondicionDesbloqueo(
            CondicionDesbloqueoML.NUMERACION_HOLDOUT_VALIDA, True,
            f"Numeracion de sorteos desde {progreso.desde_numero_sorteo} coherente segun AE-40.",
        )
        minimo = EstadoCondicionDesbloqueo(
            CondicionDesbloqueoML.MINIMO_SORTEOS_NUEVOS, progreso.faltantes == 0,
            f"{progreso.total_sorteos_nuevos} de {progreso.minimo_requerido} sorteos nuevos contiguos desde "
            f"{progreso.desde_numero_sorteo}; faltan {progreso.faltantes} (primer intervalo completo posible "
            f"hasta {progreso.numero_sorteo_objetivo_minimo}). Alcanzarlo solo permite reconsiderar la "
            f"elegibilidad; no habilita predicciones.",
        )
    else:
        numeracion = EstadoCondicionDesbloqueo(
            CondicionDesbloqueoML.NUMERACION_HOLDOUT_VALIDA, False, autorizacion.motivo,
        )
        minimo = EstadoCondicionDesbloqueo(
            CondicionDesbloqueoML.MINIMO_SORTEOS_NUEVOS, False,
            "No evaluable: la numeracion de sorteos nuevos es invalida.",
        )

    if decision is DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE:
        evidencia = EstadoCondicionDesbloqueo(
            CondicionDesbloqueoML.EVIDENCIA_CIENTIFICA_AE39, False,
            "AE-39 NO-GO: sin evidencia de mejora frente al baseline uniforme. Alcanzar el minimo de "
            "sorteos nuevos no cambia esta decision.",
        )
    else:
        evidencia = EstadoCondicionDesbloqueo(
            CondicionDesbloqueoML.EVIDENCIA_CIENTIFICA_AE39, True,
            "Evidencia exploratoria de AE-39, nunca confirmatoria: requiere igualmente una evaluacion "
            "prospectiva prerregistrada.",
        )

    protocolo = EstadoCondicionDesbloqueo(
        CondicionDesbloqueoML.PROTOCOLO_PROSPECTIVO_PRERREGISTRADO, False,
        "No existe ningun protocolo prospectivo prerregistrado ni mecanismo para registrarlo en AE-46.",
    )
    evaluacion = EstadoCondicionDesbloqueo(
        CondicionDesbloqueoML.EVALUACION_PROSPECTIVA_POSITIVA, False,
        "No existe ninguna evaluacion prospectiva; los sorteos desde 2706 ya observados no son un "
        "holdout ciego.",
    )
    return (numeracion, minimo, evidencia, protocolo, evaluacion)


def diagnosticar_bloqueo(
    autorizacion: ReporteAutorizacionOperativaML,
    decision_continuidad: DecisionContinuidadML,
) -> DiagnosticoBloqueoJuego:
    """Diagnostico puro y determinista de un juego. No reevalua AE-39,
    AE-40, AE-41 ni AE-43: solo traduce sus resultados."""
    if not isinstance(autorizacion, ReporteAutorizacionOperativaML):
        raise DiagnosticoBloqueoInvalidoError("autorizacion debe ser un ReporteAutorizacionOperativaML de AE-41")
    if not isinstance(decision_continuidad, DecisionContinuidadML):
        raise DiagnosticoBloqueoInvalidoError("decision_continuidad debe ser un DecisionContinuidadML de AE-39")
    if autorizacion.juego_codigo not in JUEGOS_AUTORIZADOS_AE40:
        raise DiagnosticoBloqueoInvalidoError(
            f"'{autorizacion.juego_codigo}' no esta autorizado -unicamente {sorted(JUEGOS_AUTORIZADOS_AE40)}"
        )
    if (autorizacion.reporte_elegibilidad is None) != (
        autorizacion.estado is EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA
    ):
        raise DiagnosticoBloqueoInvalidoError("Reporte de AE-41 incoherente con su reporte de elegibilidad")

    reporte = resolver_prediccion(autorizacion, decision_continuidad)
    progreso = _progreso(autorizacion)
    return DiagnosticoBloqueoJuego(
        juego_codigo=reporte.juego_codigo,
        estado=reporte.estado,
        motivos=reporte.motivos,
        progreso=progreso,
        condiciones=_condiciones(autorizacion, decision_continuidad, progreso),
    )
