"""
Casos de uso de los pronosticos experimentales (Productos 1 y 2).

Cuatro juegos, cada uno con su linea:
- Baloto y Revancha: `pronostico-experimental/1`
  (`app.application.ml.pronostico_experimental`, sin cambios);
- MiLoto: `pronostico-experimental/2` (`app.application.ml.pronostico_miloto`);
- ColorLoto: `pronostico-experimental/2` (`app.application.ml.pronostico_colorloto`).

`GenerarPronosticoExperimental` lee el historico real hasta un corte y,
aparte, todo el historico cargado, para clasificar el objetivo
(simulacion retrospectiva, pronostico sobre el ultimo dato disponible u
objetivo no cargado) y medir la frescura. Antes de entrenar calcula la
clave de entrada: si ya existe un artefacto con esa clave lo devuelve tal
cual (sin reentrenar ni cambiar su fecha). Si no, ejecuta la linea del
juego y guarda el artefacto sin sobrescribir ninguno.

`ConsultarPronosticosExperimentales` solo lee lo guardado y, si tiene
acceso a la base, recalcula el estado temporal actual de cada objetivo.
`VerificarPronosticoExperimental` recalcula un artefacto con el
historico actual hasta su corte y lo compara; reentrena, por eso la web
solo lo ofrece por POST protegido. `CompararConResultadosObservados`
relaciona cada pronostico guardado con su sorteo objetivo, en lectura.

Ningun caso de uso escribe en PostgreSQL, cambia el NO-GO de AE-39, el
estado operativo de AE-41 ni `AUTORIZA_EVALUACION`.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType

from app.application.estadisticas.resumen_juego import evaluar_frescura
from app.application.exceptions import DominioError, JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.pronostico_experimental_store import (
    PronosticoExperimentalStore,
    PronosticoGuardado,
    PronosticoIlegible,
)
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.ml import pronostico_colorloto as pcl
from app.application.ml import pronostico_experimental as pe
from app.application.ml import pronostico_miloto as pml
from app.application.ml import resultados_observados as ro
from app.application.use_cases.resolver_estado_prediccion import (
    DECISIONES_CONTINUIDAD_AE39,
    PROCEDENCIA_DECISIONES_AE39,
)
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame

JUEGOS_V1 = {"BALOTO": BalotoGame(), "BALOTO_REVANCHA": BalotoRevanchaGame()}
JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
"""Juegos con pronostico experimental, en el orden en que se muestran."""


class PronosticoExperimentalNoDisponibleError(DominioError):
    """Juego no admitido, historico insuficiente o inconsistente, o
    artefacto existente alterado."""


def decisiones_ae39() -> dict:
    """NO-GO historico de AE-39, tal como quedo registrado."""
    return {"decisiones": {c: d.value for c, d in DECISIONES_CONTINUIDAD_AE39.items()},
            "procedencia": PROCEDENCIA_DECISIONES_AE39}


def _juego(codigo_juego: str) -> str:
    if codigo_juego not in JUEGOS:
        raise PronosticoExperimentalNoDisponibleError(
            f"El pronostico experimental solo existe para {', '.join(JUEGOS)}; '{codigo_juego}' no lo admite")
    return codigo_juego


def _reglas_v1(codigo_juego: str) -> dict:
    dominio = JUEGOS_V1[codigo_juego]
    return {"rango_min": dominio.number_range[0], "rango_max": dominio.number_range[1],
            "cantidad_numeros": dominio.numbers_to_pick,
            "rango_superbalota": dominio.superballot_range if dominio.has_superballot else None}


def configuracion_por_defecto(codigo_juego: str):
    if codigo_juego == "MILOTO":
        return pml.ConfiguracionMiLoto()
    if codigo_juego == "COLORLOTO":
        return pcl.ConfiguracionColorLoto()
    return pe.ConfiguracionExperimental()


def configuracion_del_artefacto(artefacto: dict):
    clase = {"MILOTO": pml.ConfiguracionMiLoto, "COLORLOTO": pcl.ConfiguracionColorLoto}.get(
        artefacto["juego"], pe.ConfiguracionExperimental)
    return clase(**artefacto["configuracion"])


def _historicos(juego_repository, resultados_repository, codigo_juego, hasta_numero_sorteo):
    """(historico hasta el corte, historico completo cargado)."""
    juego = juego_repository.obtener_por_codigo(codigo_juego)
    if juego is None:
        raise JuegoNoEncontradoError(codigo_juego)
    listar = (resultados_repository.listar_resultados_colorloto if codigo_juego == "COLORLOTO"
              else resultados_repository.listar_resultados_numericos)
    completo = listar(juego.id)
    if hasta_numero_sorteo is None:
        return completo, completo
    return listar(juego.id, hasta_numero_sorteo=hasta_numero_sorteo), completo


def _no_disponible(funcion, *args, **kwargs):
    try:
        return funcion(*args, **kwargs)
    except ValueError as error:
        raise PronosticoExperimentalNoDisponibleError(str(error)) from error


def _clave(codigo_juego, historico, hasta_numero_sorteo, configuracion):
    if codigo_juego == "MILOTO":
        return _no_disponible(pml.clave_de_entrada, historico, hasta_numero_sorteo=hasta_numero_sorteo,
                              configuracion=configuracion)
    if codigo_juego == "COLORLOTO":
        return _no_disponible(pcl.clave_de_entrada, historico, hasta_numero_sorteo=hasta_numero_sorteo,
                              configuracion=configuracion)
    return _no_disponible(pe.clave_de_entrada, historico, codigo_juego=codigo_juego, **_reglas_v1(codigo_juego),
                          hasta_numero_sorteo=hasta_numero_sorteo, configuracion=configuracion)


def _cuerpo(codigo_juego, historico, hasta_numero_sorteo, configuracion):
    if _juego(codigo_juego) == "MILOTO":
        return _no_disponible(pml.generar_pronostico, historico, hasta_numero_sorteo=hasta_numero_sorteo,
                              configuracion=configuracion)
    if codigo_juego == "COLORLOTO":
        return _no_disponible(pcl.generar_pronostico, historico, hasta_numero_sorteo=hasta_numero_sorteo,
                              configuracion=configuracion)
    return _no_disponible(
        pe.generar_pronostico, historico, codigo_juego=codigo_juego, **_reglas_v1(codigo_juego),
        hasta_numero_sorteo=hasta_numero_sorteo,
        decisiones_ae39={c: d.value for c, d in DECISIONES_CONTINUIDAD_AE39.items()}, configuracion=configuracion)


def estado_temporal(artefacto: dict, completo, hoy) -> dict:
    """Clasificacion y frescura de un artefacto frente al historico
    cargado `completo`, en la fecha `hoy`."""
    superbalota = artefacto["superbalota"]["pronostico"]["sugerida"] if artefacto.get("superbalota") else None
    clasificacion = ro.clasificar_objetivo(artefacto["juego"], artefacto["pronostico"], superbalota, completo)
    ultima = max(completo, key=lambda r: r.numero_sorteo).fecha
    return {"clasificacion_temporal": clasificacion, "frescura": evaluar_frescura(ultima, hoy)}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class GenerarPronosticoExperimental:
    def __init__(self, juego_repository: JuegoRepository, resultados_repository: ResultadosHistoricosRepository,
                 almacen: PronosticoExperimentalStore, reloj: Callable[[], datetime] = _ahora,
                 configuracion: pe.ConfiguracionExperimental | None = None,
                 configuraciones: Mapping[str, object] | None = None):
        """`configuracion` (Producto 1) se aplica a Baloto y Revancha;
        `configuraciones` admite una por juego y tiene prioridad."""
        self._juegos = juego_repository
        self._resultados = resultados_repository
        self._almacen = almacen
        self._reloj = reloj
        propias = dict(configuraciones or {})
        if configuracion is not None:
            for codigo in JUEGOS_V1:
                propias.setdefault(codigo, configuracion)
        self._configuraciones = MappingProxyType(propias)

    def configuracion(self, codigo_juego: str):
        return self._configuraciones.get(codigo_juego) or configuracion_por_defecto(codigo_juego)

    def validar(self, codigo_juego: str, hasta_numero_sorteo: int | None = None) -> dict:
        """Valida el historico cargado con las reglas actuales de la linea del
        juego (las mismas que aplica `ejecutar`) sin entrenar. Devuelve el
        corte, los sorteos validados y la clave de entrada que tendria el
        pronostico; lanza `PronosticoExperimentalNoDisponibleError` si el
        historico no es valido."""
        configuracion = self.configuracion(_juego(codigo_juego))
        historico, _ = _historicos(self._juegos, self._resultados, codigo_juego, hasta_numero_sorteo)
        clave = _clave(codigo_juego, historico, hasta_numero_sorteo, configuracion)
        return {"sorteos": len(historico), "corte": max((r.numero_sorteo for r in historico), default=None),
                "clave_de_entrada": clave}

    def _existente(self, codigo_juego: str, clave: str) -> PronosticoGuardado | None:
        existente = self._almacen.obtener(codigo_juego, clave)
        if isinstance(existente, PronosticoIlegible):
            raise PronosticoExperimentalNoDisponibleError(
                f"Ya existe un artefacto con la misma entrada pero esta alterado o ilegible ({existente.motivo}); "
                "no se sobrescribe. Revisa el archivo en el almacen de pronosticos.")
        return None if existente is None else replace(existente, reutilizado=True)

    def ejecutar(self, codigo_juego: str, hasta_numero_sorteo: int | None = None) -> PronosticoGuardado:
        configuracion = self.configuracion(_juego(codigo_juego))
        historico, completo = _historicos(self._juegos, self._resultados, codigo_juego, hasta_numero_sorteo)
        clave = _clave(codigo_juego, historico, hasta_numero_sorteo, configuracion)
        existente = self._existente(codigo_juego, clave)
        if existente is not None:
            return existente
        cuerpo = _cuerpo(codigo_juego, historico, hasta_numero_sorteo, configuracion)
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

    def historico_actual(self, codigo_juego: str):
        """Historico completo cargado; None si no hay acceso a la base."""
        if self._juegos is None or self._resultados is None:
            return None
        try:
            _, completo = _historicos(self._juegos, self._resultados, codigo_juego, None)
            return completo
        except Exception:  # base no disponible: la consulta de lo guardado sigue funcionando
            return None

    def estado_actual(self, codigo_juego: str, artefacto: dict) -> dict | None:
        """Clasificacion y frescura de hoy frente a la base; None si no hay
        acceso a la base o no hay sorteos cargados."""
        completo = self.historico_actual(codigo_juego)
        return estado_temporal(artefacto, completo, self._reloj().date()) if completo else None

    def resultados_observados(self, codigo_juego: str, guardados: list) -> dict | None:
        """{identificador: comparacion} con una sola lectura del historico;
        None sin acceso a la base."""
        completo = self.historico_actual(codigo_juego)
        if completo is None:
            return None
        return {g.identificador: ro.comparar_con_resultado(g.artefacto, completo) for g in guardados}

    def resultado_observado(self, codigo_juego: str, artefacto: dict) -> dict | None:
        """Comparacion con el resultado observado; None sin acceso a la base."""
        completo = self.historico_actual(codigo_juego)
        return None if completo is None else ro.comparar_con_resultado(artefacto, completo)


class CompararConResultadosObservados:
    """Cada pronostico guardado de un juego frente a su sorteo objetivo, en
    lectura: no modifica artefactos ni escribe en la base."""

    def __init__(self, almacen: PronosticoExperimentalStore, juego_repository: JuegoRepository,
                 resultados_repository: ResultadosHistoricosRepository):
        self._consultar = ConsultarPronosticosExperimentales(almacen, juego_repository, resultados_repository)
        self._juegos = juego_repository
        self._resultados = resultados_repository

    def ejecutar(self, codigo_juego: str) -> list[dict]:
        resumen = self._consultar.resumen(codigo_juego)
        _, completo = _historicos(self._juegos, self._resultados, codigo_juego, None)
        filas = []
        for g in resumen.guardados:
            filas.append({"identificador": g.identificador, "version": g.version, "versiones": g.versiones,
                          "esquema": g.artefacto["esquema"], "corte": g.artefacto["datos"]["corte"],
                          "generado_en": g.artefacto["generacion"]["generado_en"],
                          "comparacion": ro.comparar_con_resultado(g.artefacto, completo)})
        for e in resumen.ilegibles:
            filas.append({"identificador": e.identificador, "comparacion": {
                "estado": "no_corresponde", "motivo": f"artefacto ilegible o alterado ({e.motivo})",
                "historico_hasta_el_corte": {"estado": "no_disponible",
                                             "motivo": "el artefacto no se puede leer: su corte es desconocido"}}})
        return filas


def elegir_corte_retrospectivo(juego_repository: JuegoRepository,
                               resultados_repository: ResultadosHistoricosRepository, codigo_juego: str,
                               configuracion) -> dict:
    """Corte existente para comprobar un resultado observado de MiLoto o
    ColorLoto, tomado del historico cargado (solo lectura): el mayor corte
    con al menos `minimo` sorteos hasta el (incluido) y cuyo objetivo,
    corte + 1, tambien figura en la base. Ningun numero se supone."""
    if codigo_juego not in ("MILOTO", "COLORLOTO"):
        raise PronosticoExperimentalNoDisponibleError("el corte retrospectivo se elige solo para MILOTO y COLORLOTO")
    minimo = configuracion.minimo_sorteos_de_entrenamiento + configuracion.minimo_objetivos_evaluados
    _, completo = _historicos(juego_repository, resultados_repository, codigo_juego, None)
    ordenado = sorted(completo, key=lambda r: r.numero_sorteo)
    por_numero = {r.numero_sorteo: r for r in ordenado}
    for indice in range(len(ordenado) - 1, minimo - 2, -1):
        corte = ordenado[indice].numero_sorteo
        objetivo = por_numero.get(corte + 1)
        if indice + 1 >= minimo and objetivo is not None:
            return {"juego": codigo_juego, "sorteos_cargados": len(ordenado), "corte": corte,
                    "sorteos_hasta_el_corte": indice + 1, "minimo": minimo, "objetivo": corte + 1,
                    "fecha_objetivo": objetivo.fecha.isoformat()}
    raise PronosticoExperimentalNoDisponibleError(
        f"no hay un corte con al menos {minimo} sorteos hasta el y un objetivo (corte + 1) cargado en la base "
        f"({len(ordenado)} sorteos de {codigo_juego})")


class VerificarPronosticoExperimental:
    """Recalcula un artefacto guardado con el historico actual hasta su
    corte y su configuracion, sin guardar nada. Reentrena el modelo."""

    def __init__(self, juego_repository: JuegoRepository, resultados_repository: ResultadosHistoricosRepository,
                 almacen: PronosticoExperimentalStore):
        self._juegos = juego_repository
        self._resultados = resultados_repository
        self._almacen = almacen

    def ejecutar(self, codigo_juego: str, identificador: str) -> dict:
        _juego(codigo_juego)
        guardado = self._almacen.obtener(codigo_juego, identificador)
        if guardado is None:
            raise PronosticoExperimentalNoDisponibleError(f"No existe el pronostico {identificador}")
        if isinstance(guardado, PronosticoIlegible):
            raise PronosticoExperimentalNoDisponibleError(f"Pronostico ilegible: {guardado.motivo}")
        artefacto = guardado.artefacto
        configuracion = configuracion_del_artefacto(artefacto)
        corte = artefacto["datos"]["corte"]
        historico, _ = _historicos(self._juegos, self._resultados, codigo_juego, corte)
        cuerpo = _cuerpo(codigo_juego, historico, corte, configuracion)
        return {"identificador": identificador, **_comprobar(artefacto, cuerpo)}


def _comprobar(artefacto: dict, cuerpo: dict) -> dict:
    """`pe.comprobar_reproduccion` para el esquema 1; para el esquema 2 la
    misma comparacion sobre su forma de pronostico."""
    if artefacto["esquema"] == pe.ESQUEMA_ARTEFACTO:
        return pe.comprobar_reproduccion(artefacto, cuerpo)
    guardado = pe.cuerpo_del_artefacto(artefacto)
    exacta = pe.huella_de_reproduccion(guardado) == pe.huella_de_reproduccion(cuerpo)
    if artefacto["juego"] == "COLORLOTO":
        clave = ("ranking_de_pares", lambda f: (f["numero"], f["color"]))
        sugeridos = lambda c: c["pronostico"]["pares"]  # noqa: E731
    else:
        clave = ("ranking", lambda f: f["numero"])
        sugeridos = lambda c: c["pronostico"]["numeros_sugeridos"]  # noqa: E731
    a = {clave[1](f): f["probabilidad"] for f in guardado["pronostico"][clave[0]]}
    b = {clave[1](f): f["probabilidad"] for f in cuerpo["pronostico"][clave[0]]}
    diferencia = max(abs(a[k] - b[k]) for k in a) if set(a) == set(b) else float("inf")
    return {"huella_exacta": exacta,
            "mismos_datos": guardado["datos"]["sha256_historico"] == cuerpo["datos"]["sha256_historico"],
            "mismos_numeros_sugeridos": sugeridos(guardado) == sugeridos(cuerpo),
            "maxima_diferencia_de_probabilidad": diferencia}
