"""
Casos de uso del pronostico experimental de Baloto y Revancha (Producto 1).

`GenerarPronosticoExperimental` lee el historico real hasta un corte y,
aparte, todo el historico cargado, para clasificar el objetivo
(simulacion retrospectiva, pronostico sobre el ultimo dato disponible u
objetivo no cargado) y medir la frescura. Antes de entrenar calcula la
clave de entrada: si ya existe un artefacto con esa clave lo devuelve tal
cual (sin reentrenar ni cambiar su fecha). Si no, ejecuta la linea de
`app.application.ml.pronostico_experimental` y guarda el artefacto sin
sobrescribir ninguno.

`ConsultarPronosticosExperimentales` solo lee lo guardado y, si tiene
acceso a la base, recalcula el estado temporal actual de cada objetivo.
`VerificarPronosticoExperimental` recalcula un artefacto con el
historico actual hasta su corte y lo compara; reentrena, por eso la web
solo lo ofrece por POST protegido.

Ningun caso de uso escribe en PostgreSQL, cambia el NO-GO de AE-39, el
estado operativo de AE-41 ni `AUTORIZA_EVALUACION`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from app.application.estadisticas.resumen_juego import evaluar_frescura
from app.application.exceptions import DominioError, JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.pronostico_experimental_store import (
    PronosticoExperimentalStore,
    PronosticoGuardado,
    PronosticoIlegible,
)
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.ml import pronostico_experimental as pe
from app.application.use_cases.resolver_estado_prediccion import (
    DECISIONES_CONTINUIDAD_AE39,
    PROCEDENCIA_DECISIONES_AE39,
)
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame

JUEGOS = {"BALOTO": BalotoGame(), "BALOTO_REVANCHA": BalotoRevanchaGame()}


class PronosticoExperimentalNoDisponibleError(DominioError):
    """Juego no admitido, historico insuficiente o inconsistente, o
    artefacto existente alterado."""


def decisiones_ae39() -> dict:
    """NO-GO historico de AE-39, tal como quedo registrado."""
    return {"decisiones": {c: d.value for c, d in DECISIONES_CONTINUIDAD_AE39.items()},
            "procedencia": PROCEDENCIA_DECISIONES_AE39}


def _juego(codigo_juego: str):
    if codigo_juego not in JUEGOS:
        raise PronosticoExperimentalNoDisponibleError(
            f"El pronostico experimental solo existe para {', '.join(JUEGOS)}; '{codigo_juego}' no lo admite")
    return JUEGOS[codigo_juego]


def _reglas(dominio) -> dict:
    return {"rango_min": dominio.number_range[0], "rango_max": dominio.number_range[1],
            "cantidad_numeros": dominio.numbers_to_pick,
            "rango_superbalota": dominio.superballot_range if dominio.has_superballot else None}


def _historicos(juego_repository, resultados_repository, codigo_juego, hasta_numero_sorteo):
    """(historico hasta el corte, historico completo cargado)."""
    juego = juego_repository.obtener_por_codigo(codigo_juego)
    if juego is None:
        raise JuegoNoEncontradoError(codigo_juego)
    completo = resultados_repository.listar_resultados_numericos(juego.id)
    if hasta_numero_sorteo is None:
        return completo, completo
    return resultados_repository.listar_resultados_numericos(juego.id, hasta_numero_sorteo=hasta_numero_sorteo), completo


def _no_disponible(funcion, *args, **kwargs):
    try:
        return funcion(*args, **kwargs)
    except ValueError as error:
        raise PronosticoExperimentalNoDisponibleError(str(error)) from error


def _cuerpo(codigo_juego, historico, hasta_numero_sorteo, configuracion):
    return _no_disponible(
        pe.generar_pronostico, historico, codigo_juego=codigo_juego, **_reglas(_juego(codigo_juego)),
        hasta_numero_sorteo=hasta_numero_sorteo,
        decisiones_ae39={c: d.value for c, d in DECISIONES_CONTINUIDAD_AE39.items()}, configuracion=configuracion)


def estado_temporal(artefacto: dict, completo, hoy) -> dict:
    """Clasificacion y frescura de un artefacto frente al historico
    cargado `completo`, en la fecha `hoy`."""
    superbalota = artefacto["superbalota"]["pronostico"]["sugerida"] if artefacto.get("superbalota") else None
    clasificacion = pe.clasificar_objetivo(artefacto["pronostico"]["objetivo"], completo,
                                           numeros_sugeridos=artefacto["pronostico"]["numeros_sugeridos"],
                                           superbalota_sugerida=superbalota)
    ultima = max(completo, key=lambda r: r.numero_sorteo).fecha
    return {"clasificacion_temporal": clasificacion, "frescura": evaluar_frescura(ultima, hoy)}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class GenerarPronosticoExperimental:
    def __init__(self, juego_repository: JuegoRepository, resultados_repository: ResultadosHistoricosRepository,
                 almacen: PronosticoExperimentalStore, reloj: Callable[[], datetime] = _ahora,
                 configuracion: pe.ConfiguracionExperimental = pe.ConfiguracionExperimental()):
        self._juegos = juego_repository
        self._resultados = resultados_repository
        self._almacen = almacen
        self._reloj = reloj
        self._configuracion = configuracion

    def _existente(self, codigo_juego: str, clave: str) -> PronosticoGuardado | None:
        existente = self._almacen.obtener(codigo_juego, clave)
        if isinstance(existente, PronosticoIlegible):
            raise PronosticoExperimentalNoDisponibleError(
                f"Ya existe un artefacto con la misma entrada pero esta alterado o ilegible ({existente.motivo}); "
                "no se sobrescribe. Revisa el archivo en el almacen de pronosticos.")
        return None if existente is None else replace(existente, reutilizado=True)

    def ejecutar(self, codigo_juego: str, hasta_numero_sorteo: int | None = None) -> PronosticoGuardado:
        reglas = _reglas(_juego(codigo_juego))
        historico, completo = _historicos(self._juegos, self._resultados, codigo_juego, hasta_numero_sorteo)
        clave = _no_disponible(pe.clave_de_entrada, historico, codigo_juego=codigo_juego, **reglas,
                               hasta_numero_sorteo=hasta_numero_sorteo, configuracion=self._configuracion)
        existente = self._existente(codigo_juego, clave)
        if existente is not None:
            return existente
        cuerpo = _cuerpo(codigo_juego, historico, hasta_numero_sorteo, self._configuracion)
        ahora = self._reloj()
        estado = estado_temporal(cuerpo, completo, ahora.date())
        artefacto = pe.componer_artefacto(cuerpo, generado_en=ahora.isoformat(), **estado)
        try:
            return self._almacen.guardar(codigo_juego, artefacto)
        except FileExistsError:  # otra peticion guardo la misma clave mientras se entrenaba
            existente = self._existente(codigo_juego, clave)
            if existente is None:
                raise
            return existente


@dataclass(frozen=True)
class ResumenPronosticos:
    codigo_juego: str
    ultimo: PronosticoGuardado | None
    guardados: list
    ilegibles: list


class ConsultarPronosticosExperimentales:
    def __init__(self, almacen: PronosticoExperimentalStore, juego_repository: JuegoRepository | None = None,
                 resultados_repository: ResultadosHistoricosRepository | None = None,
                 reloj: Callable[[], datetime] = _ahora):
        self._almacen = almacen
        self._juegos = juego_repository
        self._resultados = resultados_repository
        self._reloj = reloj

    def resumen(self, codigo_juego: str) -> ResumenPronosticos:
        _juego(codigo_juego)
        elementos = self._almacen.listar(codigo_juego)
        guardados = [e for e in elementos if isinstance(e, PronosticoGuardado)]
        ilegibles = [e for e in elementos if isinstance(e, PronosticoIlegible)]
        return ResumenPronosticos(codigo_juego, guardados[0] if guardados else None, guardados, ilegibles)

    def obtener(self, codigo_juego: str, identificador: str):
        _juego(codigo_juego)
        return self._almacen.obtener(codigo_juego, identificador)

    def estado_actual(self, codigo_juego: str, artefacto: dict) -> dict | None:
        """Clasificacion y frescura de hoy frente a la base; None si no hay
        acceso a la base o no hay sorteos cargados."""
        if self._juegos is None or self._resultados is None:
            return None
        try:
            _, completo = _historicos(self._juegos, self._resultados, codigo_juego, None)
            return estado_temporal(artefacto, completo, self._reloj().date()) if completo else None
        except Exception:  # base no disponible: la consulta de lo guardado sigue funcionando
            return None


class VerificarPronosticoExperimental:
    """Recalcula un artefacto guardado con el historico actual hasta su
    corte y su configuracion, sin guardar nada. Reentrena el modelo."""

    def __init__(self, juego_repository: JuegoRepository, resultados_repository: ResultadosHistoricosRepository,
                 almacen: PronosticoExperimentalStore):
        self._juegos = juego_repository
        self._resultados = resultados_repository
        self._almacen = almacen

    def ejecutar(self, codigo_juego: str, identificador: str) -> dict:
        guardado = self._almacen.obtener(codigo_juego, identificador)
        if guardado is None:
            raise PronosticoExperimentalNoDisponibleError(f"No existe el pronostico {identificador}")
        if isinstance(guardado, PronosticoIlegible):
            raise PronosticoExperimentalNoDisponibleError(f"Pronostico ilegible: {guardado.motivo}")
        artefacto = guardado.artefacto
        configuracion = pe.ConfiguracionExperimental(**artefacto["configuracion"])
        corte = artefacto["datos"]["corte"]
        historico, _ = _historicos(self._juegos, self._resultados, codigo_juego, corte)
        cuerpo = _cuerpo(codigo_juego, historico, corte, configuracion)
        return {"identificador": identificador, **pe.comprobar_reproduccion(artefacto, cuerpo)}
