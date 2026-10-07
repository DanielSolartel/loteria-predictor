"""
Operacion diaria por juego (Producto 3).

Un unico caso de uso para la web y el comando. Por cada juego:

1. estado inicial (ultimo sorteo cargado);
2. si el modo es `actualizar`, la importacion incremental existente
   (`SincronizarSorteos`, inyectada como `sincronizar`);
3. validacion del historico resultante con las reglas actuales de la linea
   del juego (`GenerarPronosticoExperimental.validar`, sin entrenar);
4. resultados observados de los pronosticos guardados
   (`CompararConResultadosObservados`, en lectura);
5. generacion o reutilizacion del pronostico del corte actual
   (`GenerarPronosticoExperimental.ejecutar`: misma clave -> el mismo
   artefacto; historico corregido -> otra version, sin reescribir);
6. resumen registrado en el registro de ejecuciones.

Modos: `local` usa solo el historico cargado y no escribe sorteos (quien
abre las dependencias usa una transaccion de solo lectura); `actualizar`
importa antes desde el origen existente. Si la actualizacion de un juego
falla, ese juego no se genera dentro de la misma ejecucion (ni con su
historico anterior): se informa el fallo y se puede repetir despues en
modo `local`. Los demas juegos siguen.

Estados de juego: `ok`, `datos_insuficientes`, `fallo` (e `interrumpido`
si no llego a terminar). Estado global: `exito` (todos ok), `parcial`
(alguno no) o `fallo` (ninguno ok); `en_curso` mientras su trabajador vive
e `interrumpida` si ya no hay trabajador y el cierre global no se escribio
(proceso muerto, disco lleno, hilo que no se pudo lanzar). La vida del
trabajador se reconoce por el cerrojo de la ejecucion, que mantiene hasta
el final; no se deduce de que sus juegos hayan terminado. Una ejecucion
interrumpida conserva el estado de los juegos que si terminaron y nunca se
convierte en un exito que no llego a registrarse.

Concurrencia: un cerrojo del sistema operativo por juego, adquirido para
todos los juegos pedidos antes de empezar (todos o ninguno). Una segunda
peticion incompatible recibe `EjecucionActivaError` con la ejecucion
activa. Cada juego abre sus propias dependencias (su propia sesion de base
de datos): nada se comparte entre hilos.

No cambia el esquema ni las huellas de los pronosticos: el identificador
de la ejecucion solo vive en el registro operativo.
"""
from __future__ import annotations

import re
import secrets
from collections import Counter
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.application.exceptions import JuegoNoEncontradoError
from app.application.use_cases.pronostico_experimental import (
    JUEGOS,
    CompararConResultadosObservados,
    GenerarPronosticoExperimental,
    PronosticoExperimentalNoDisponibleError,
)

MODOS = ("local", "actualizar")
FORMATO_IDENTIFICADOR = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")


def nuevo_identificador(momento: datetime) -> str:
    """`AAAAMMDDThhmmssZ-<8 hex>`: ordenable por fecha y sin colisiones."""
    return f"{momento.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"


def identificador_valido(valor: str | None) -> bool:
    return bool(FORMATO_IDENTIFICADOR.fullmatch(valor or ""))
ESTADOS_FINALES = ("exito", "parcial", "fallo", "interrumpida")


class EjecucionActivaError(Exception):
    def __init__(self, activas: dict[str, str | None]):
        self.activas = activas
        juegos = ", ".join(sorted(activas))
        super().__init__(f"ya hay una ejecucion en curso para {juegos}")


@dataclass
class DependenciasDeJuego:
    """Lo que necesita un juego, con su propia sesion. `sincronizar` solo
    existe en modo `actualizar`: recibe el codigo y devuelve el reporte de
    `SincronizarSorteos`."""
    juego_repository: Any
    resultados_repository: Any
    sincronizar: Callable[[str], Any] | None = None


@dataclass
class Inicio:
    ejecucion: dict
    cerrojos: Any
    juegos: tuple[str, ...] = field(default_factory=tuple)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


_ETIQUETAS = re.compile(r"<[^>]{0,500}>")


def mensaje_legible(error: object, limite: int = 300) -> str:
    """Mensaje corto y sin HTML (nunca una respuesta HTML completa)."""
    texto = _ETIQUETAS.sub(" ", str(error))
    texto = re.sub(r"\s+", " ", texto).strip()
    if "OperationalError" in type(error).__name__ or "could not connect" in texto or "Connection refused" in texto:
        return "Sin conexion con la base de datos."
    return (texto[:limite] + "…") if len(texto) > limite else (texto or type(error).__name__)


def _ultimo(dep: DependenciasDeJuego, codigo: str) -> dict:
    juego = dep.juego_repository.obtener_por_codigo(codigo)
    if juego is None:
        raise JuegoNoEncontradoError(codigo)
    listar = (dep.resultados_repository.listar_resultados_colorloto if codigo == "COLORLOTO"
              else dep.resultados_repository.listar_resultados_numericos)
    datos = listar(juego.id)
    if not datos:
        return {"sorteos": 0, "ultimo_sorteo": None, "fecha": None}
    ultimo = max(datos, key=lambda r: r.numero_sorteo)
    return {"sorteos": len(datos), "ultimo_sorteo": ultimo.numero_sorteo, "fecha": ultimo.fecha.isoformat()}


class OperacionDiaria:
    def __init__(self, almacen, registro, cerrojo,
                 abrir_dependencias: Callable[[str, str], AbstractContextManager[DependenciasDeJuego]],
                 reloj: Callable[[], datetime] = _ahora, configuraciones=None,
                 generador_de_identificador: Callable[[datetime], str] = nuevo_identificador):
        self._almacen = almacen
        self._registro = registro
        self._cerrojo = cerrojo
        self._abrir = abrir_dependencias
        self._reloj = reloj
        self._configuraciones = configuraciones
        self._nuevo_identificador = generador_de_identificador

    # ------------------------------------------------------------------
    # Inicio y ejecucion
    # ------------------------------------------------------------------

    def iniciar(self, juegos: Iterable[str], modo: str, origen: str) -> Inicio:
        juegos = tuple(dict.fromkeys(juegos))
        if not juegos or any(j not in JUEGOS for j in juegos):
            raise ValueError(f"juegos admitidos: {', '.join(JUEGOS)}")
        if modo not in MODOS:
            raise ValueError(f"modos admitidos: {', '.join(MODOS)}")
        ahora = self._reloj()
        identificador = self._nuevo_identificador(ahora)
        cerrojos = self._cerrojo.adquirir(juegos, identificador)
        if isinstance(cerrojos, dict):
            raise EjecucionActivaError(cerrojos)
        ejecucion = {
            "id": identificador, "modo": modo, "origen": origen, "estado": "en_curso",
            "iniciada_en": ahora.isoformat(), "finalizada_en": None,
            "orden": list(juegos),
            "juegos": {j: {"juego": j, "estado": "pendiente", "pasos": []} for j in juegos},
        }
        try:
            self._registro.guardar(ejecucion)
        except BaseException:
            cerrojos.liberar()
            raise
        return Inicio(ejecucion, cerrojos, juegos)

    def ejecutar(self, inicio: Inicio) -> dict:
        ejecucion = inicio.ejecucion
        try:
            for codigo in inicio.juegos:
                ejecucion["juegos"][codigo] = self._un_juego(ejecucion, codigo)
                inicio.cerrojos.liberar(codigo)
                self._registro.guardar(ejecucion)
            estados = Counter(r["estado"] for r in ejecucion["juegos"].values())
            ejecucion["estado"] = ("exito" if estados["ok"] == len(inicio.juegos)
                                   else "fallo" if estados["ok"] == 0 else "parcial")
            ejecucion["finalizada_en"] = self._reloj().isoformat()
            self._registro.guardar(ejecucion)
            return ejecucion
        finally:
            inicio.cerrojos.liberar()

    def ejecutar_ahora(self, juegos: Iterable[str], modo: str, origen: str) -> dict:
        return self.ejecutar(self.iniciar(juegos, modo, origen))

    def _paso(self, ejecucion: dict, resultado: dict, nombre: str, **datos) -> None:
        resultado["pasos"].append({"paso": nombre, "en": self._reloj().isoformat(), **datos})
        ejecucion["juegos"][resultado["juego"]] = resultado
        self._registro.guardar(ejecucion)

    def _un_juego(self, ejecucion: dict, codigo: str) -> dict:
        modo = ejecucion["modo"]
        r = {"juego": codigo, "estado": "en_curso", "inicio": self._reloj().isoformat(), "fin": None,
             "ultimo_antes": None, "ultimo_despues": None, "sincronizacion": None, "validacion": None,
             "resultados": None, "pronostico": None, "mensaje": None, "pasos": []}
        try:
            with self._abrir(codigo, modo) as dep:
                r["ultimo_antes"] = _ultimo(dep, codigo)
                self._paso(ejecucion, r, "estado_inicial", **r["ultimo_antes"])
                if modo == "actualizar":
                    if not self._sincronizar(ejecucion, r, dep, codigo):
                        return self._cerrar(r, "fallo")
                r["ultimo_despues"] = _ultimo(dep, codigo)
                generar = GenerarPronosticoExperimental(dep.juego_repository, dep.resultados_repository, self._almacen,
                                                        reloj=self._reloj, configuraciones=self._configuraciones)
                try:
                    r["validacion"] = {"estado": "valido", **generar.validar(codigo)}
                except PronosticoExperimentalNoDisponibleError as error:
                    insuficiente = "atos insuficientes" in str(error) or "nsuficiente" in str(error)
                    r["validacion"] = {"estado": "datos_insuficientes" if insuficiente else "invalido",
                                       "mensaje": mensaje_legible(error)}
                    self._paso(ejecucion, r, "validacion", estado=r["validacion"]["estado"])
                    r["mensaje"] = r["validacion"]["mensaje"]
                    return self._cerrar(r, "datos_insuficientes" if insuficiente else "fallo")
                self._paso(ejecucion, r, "validacion", estado="valido", sorteos=r["validacion"]["sorteos"])
                filas = CompararConResultadosObservados(self._almacen, dep.juego_repository,
                                                        dep.resultados_repository).ejecutar(codigo)
                estados = Counter(f["comparacion"]["estado"] for f in filas)
                r["resultados"] = {"pronosticos_guardados": len(filas), "observados": estados["observado"],
                                   "pendientes": estados["pendiente"], "no_corresponde": estados["no_corresponde"]}
                self._paso(ejecucion, r, "resultados_observados", **r["resultados"])
                guardado = generar.ejecutar(codigo)
                r["pronostico"] = {"objetivo": guardado.artefacto["pronostico"]["objetivo"],
                                   "identificador": guardado.identificador,
                                   "reutilizado": guardado.reutilizado,
                                   "version": guardado.version, "versiones": guardado.versiones}
                self._paso(ejecucion, r, "pronostico", **r["pronostico"])
                return self._cerrar(r, "ok")
        except PronosticoExperimentalNoDisponibleError as error:
            r["mensaje"] = mensaje_legible(error)
            return self._cerrar(r, "datos_insuficientes" if "atos insuficientes" in str(error) else "fallo")
        except Exception as error:  # base caida, juego no registrado, error inesperado: el juego falla, los demas siguen
            r["mensaje"] = mensaje_legible(error)
            return self._cerrar(r, "fallo")

    def _sincronizar(self, ejecucion: dict, r: dict, dep: DependenciasDeJuego, codigo: str) -> bool:
        if dep.sincronizar is None:
            raise RuntimeError("modo actualizar sin importador configurado")
        try:
            reporte = dep.sincronizar(codigo)
        except Exception as error:
            r["sincronizacion"] = {"estado": "fallido", "mensaje": mensaje_legible(error)}
            r["mensaje"] = ("La actualizacion fallo; no se genero con el historico anterior. "
                            f"Motivo: {r['sincronizacion']['mensaje']}")
            self._paso(ejecucion, r, "sincronizacion", estado="fallido")
            return False
        e = reporte.ejecucion
        errores = [mensaje_legible(d.get("error", d), 160) for d in (e.detalle_errores or [])[:3]]
        r["sincronizacion"] = {
            "estado": e.estado, "sorteos_nuevos": e.sorteos_nuevos, "sorteos_duplicados": e.sorteos_duplicados,
            "sorteos_fallidos": e.sorteos_fallidos, "sorteos_corregidos": None,
            "nota_corregidos": "el importador no informa correcciones de sorteos ya cargados",
            "ultimo_sorteo_importado": e.ultimo_sorteo_importado, "errores": errores,
        }
        self._paso(ejecucion, r, "sincronizacion", estado=e.estado, sorteos_nuevos=e.sorteos_nuevos)
        if e.estado != "completado":
            r["mensaje"] = ("La actualizacion fallo; no se genero con el historico anterior. "
                            + (f"Motivo: {errores[0]}" if errores else ""))
            return False
        return True

    def _cerrar(self, r: dict, estado: str) -> dict:
        r["estado"] = estado
        r["fin"] = self._reloj().isoformat()
        return r

    # ------------------------------------------------------------------
    # Consulta y recuperacion
    # ------------------------------------------------------------------

    def _derivar(self, ejecucion: dict | None) -> dict | None:
        """Una ejecucion `en_curso` sin trabajador vivo (su cerrojo de
        ejecucion ya no esta tomado) se informa como `interrumpida`, aunque
        todos sus juegos hubieran terminado: su cierre global no se escribio.
        Solo lectura: no modifica el registro."""
        if ejecucion is None or ejecucion.get("estado") != "en_curso":
            return ejecucion
        if not self._cerrojo.ejecucion_viva(ejecucion["id"]):
            return {**ejecucion, "estado": "interrumpida",
                    "mensaje": ("El proceso que la ejecutaba termino antes de acabar. Lo ya publicado se conserva; "
                                "vuelva a ejecutar: una entrada identica reutiliza el pronostico guardado.")}
        return ejecucion

    def consultar(self, identificador: str) -> dict | None:
        return self._derivar(self._registro.obtener(identificador))

    def recientes(self, limite: int = 20) -> list[dict]:
        return [self._derivar(e) for e in self._registro.listar(limite)]

    def activa(self, codigo: str) -> str | None:
        return self._cerrojo.activa(codigo)

    def abortar(self, inicio: Inicio, motivo: str) -> None:
        """El trabajo no llego a lanzarse: suelta los cerrojos y deja anotada
        la ejecucion como interrumpida (si no se puede anotar, la consulta la
        deriva igualmente como interrumpida)."""
        inicio.cerrojos.liberar()
        ejecucion = {**inicio.ejecucion, "estado": "interrumpida", "finalizada_en": self._reloj().isoformat(),
                     "mensaje": f"No se pudo iniciar el trabajo: {mensaje_legible(motivo)}"}
        try:
            self._registro.guardar(ejecucion)
        except OSError:
            pass

    def recuperar(self) -> list[str]:
        """Anota como `interrumpida` cada ejecucion en curso sin trabajador
        vivo. Los juegos que terminaron conservan su estado; los demas pasan a
        `interrumpido`. No borra ni repite publicaciones."""
        marcadas = []
        for e in self._registro.listar(200):
            derivada = self._derivar(e)
            if derivada is not e and derivada.get("estado") == "interrumpida":
                derivada = {**derivada, "juegos": {j: dict(r) for j, r in derivada.get("juegos", {}).items()}}
                derivada["finalizada_en"] = self._reloj().isoformat()
                for r in derivada["juegos"].values():
                    if r.get("estado") in ("pendiente", "en_curso"):
                        r["estado"] = "interrumpido"
                self._registro.guardar(derivada)
                marcadas.append(derivada["id"])
        return marcadas


def ultima_por_juego(ejecuciones: list[dict], codigo: str) -> tuple[dict | None, dict | None]:
    """(ejecucion, resultado del juego) mas reciente que incluye el juego."""
    for e in ejecuciones:
        if e and codigo in e.get("juegos", {}):
            return e, e["juegos"][codigo]
    return None, None
