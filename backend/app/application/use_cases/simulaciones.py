"""
Fase 7: simulaciones bajo el mecanismo uniforme de cada juego -el caso de
uso comun `SimulacionesFase7` para la web, la API interna y el comando
`python -m scripts.simulaciones`.

- `catalogo`/`panel`: iteraciones admitidas (100, 1.000, 10.000, 100.000 y
  1.000.000), semilla predeterminada, estadisticas fijadas y mecanismo por
  juego; corte, sorteos y simulaciones guardadas de cada juego (lectura).
- Trabajo en segundo plano (`iniciar` + `ejecutar`) con las primitivas de
  Producto 3 (cerrojo del sistema operativo por juego, cerrojo de la
  ejecucion y registro de progreso persistente en la carpeta propia):
  1. UNA lectura del historico hasta el corte, en una transaccion de solo
     lectura que se cierra antes de simular;
  2. identidad y clave (`fase7.artefacto`); si la tabla `simulaciones` ya
     tiene esa clave y la fila es integra, se REUTILIZA sin simular;
  3. simulacion por lotes en el proceso trabajador (tiempo maximo, progreso);
  4. PUBLICACION: una transaccion propia inserta la fila COMPLETA (o
     devuelve la que otro publico antes con la misma clave) y se verifica
     despues releyendola. Nada parcial llega a la tabla.
  Estados finales por juego: `terminado`, `reutilizado`, `muestra_insuficiente`,
  `historico_no_valido`, `base_no_disponible`, `tiempo_agotado`, `alterado`,
  `fallo`. El trabajador escribe su cierre ANTES de soltar el cerrojo de la
  ejecucion: una lectura que lo observa libre relee el registro y solo
  informa `interrumpida` si sigue `en_curso`; `recuperar` lo persiste bajo
  ese mismo cerrojo. Repetir la misma entrada reutiliza lo publicado.
- `listar`/`obtener`/`exportar_*`/`verificar`: filas de la tabla verificadas
  con UNA comprobacion (`fase7.artefacto.verificar_fila`: tipos, integridad
  y juego de `juego_id` frente al de la identidad), exportaciones derivadas
  y coincidencia del historico con la base actual; `verificar(reproducir=True)`
  vuelve a simular y compara la huella del contenido. No escriben.

El registro de progreso nunca es fuente del resultado: solo referencia la
fila. Nada de esto importa sorteos, entrena modelos ni cambia AE-49-51,
Producto 5, la operacion automatica, `experimental_no_acreditado`, el NO-GO
de AE-39 o `AUTORIZA_EVALUACION = False`.
"""
from __future__ import annotations

import errno
import platform
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import numpy as np

from app.application.estadisticas.resumen_juego import evaluar_frescura
from app.application.exceptions import JuegoNoEncontradoError
from app.application.fase7 import artefacto as fa
from app.application.fase7 import motor as fm
from app.application.interfaces.ejecutor_simulaciones import (
    EjecutorDeSimulaciones,
    TiempoAgotadoError,
    TrabajadorFallidoError,
)
from app.application.interfaces.simulaciones_repository import PublicacionConcurrenteError
from app.application.ml import laboratorio_variables as lv
from app.application.use_cases.laboratorio import JUEGOS, NOMBRES, SLUGS, leer_historico
from app.application.use_cases.operacion_diaria import (
    EjecucionActivaError,
    identificador_valido,
    mensaje_legible,
    nuevo_identificador,
)
from app.domain.entities.analitica import Simulacion

TIPO_DE_TRABAJO = "simulacion_fase7"
INTERVALO_DE_PROGRESO = 1.0
"""Segundos minimos entre dos escrituras del progreso de lotes (las fases se
escriben siempre)."""
MENSAJE_INTERRUMPIDA = ("El proceso que la ejecutaba termino antes de acabar. No se publico nada parcial; repetir la "
                        "misma entrada reutiliza lo que ya este en la tabla.")
__all__ = ["SimulacionesFase7", "SimulacionesError", "EjecutorSimulacionesEnEsteProceso", "JUEGOS", "NOMBRES",
           "SLUGS"]


class SimulacionesError(Exception):
    """Error esperado con un codigo estable (`no_valido`, `no_encontrado`,
    `alterado`, `base_no_disponible`, `fallo_del_trabajador`, `tiempo_agotado`)."""

    def __init__(self, codigo: str, mensaje: str):
        self.codigo = codigo
        super().__init__(mensaje)


@dataclass
class LecturaSimulaciones:
    juego_repository: Any
    resultados_repository: Any
    simulaciones_repository: Any


@dataclass
class Inicio:
    ejecucion: dict
    cerrojos: object
    juego: str
    parametros: dict = field(default_factory=dict)
    # Observador opcional del progreso (p. ej. el comando lo muestra); no se guarda.
    observador: Callable[[dict], None] | None = field(default=None, repr=False)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class EjecutorSimulacionesEnEsteProceso(EjecutorDeSimulaciones):
    """Simula en el proceso que llama. SOLO PARA PRUEBAS Y VERIFICACION
    LOCAL: no aisla ni tiene tiempo maximo; la aplicacion usa
    `EjecutorSimulacionesEnProceso`."""

    def __init__(self, lote: int | None = None):
        self.lote = lote

    def simular(self, juego, sorteos, iteraciones, semilla, avance=None):
        return fm.calcular(juego, sorteos, iteraciones, semilla, lote=self.lote, avance=avance)


def _validar_juego(juego: str) -> None:
    if juego not in JUEGOS:
        raise SimulacionesError("no_valido", f"juego no admitido: {juego!r}; admitidos: {', '.join(JUEGOS)}")


def _uuid(identificador) -> UUID:
    try:
        return identificador if isinstance(identificador, UUID) else UUID(str(identificador))
    except (TypeError, ValueError):
        raise SimulacionesError("no_encontrado", f"No existe la simulacion {identificador!r}") from None


def _iso(valor) -> str | None:
    if valor is None:
        return None
    return valor.isoformat() if hasattr(valor, "isoformat") else str(valor)


def entorno() -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__, "sistema": platform.system(),
            "maquina": platform.machine()}


class SimulacionesFase7:
    def __init__(self, registro, cerrojo, abrir_lectura: Callable[[], AbstractContextManager[LecturaSimulaciones]],
                 abrir_publicacion: Callable[[], AbstractContextManager[LecturaSimulaciones]], *,
                 ejecutor: EjecutorDeSimulaciones, reloj: Callable[[], datetime] = _ahora,
                 monotono: Callable[[], float] = time.monotonic,
                 generador_de_identificador: Callable[[datetime], str] = nuevo_identificador,
                 intervalo_de_progreso: float = INTERVALO_DE_PROGRESO):
        self._registro = registro
        self._cerrojo = cerrojo
        self._abrir = abrir_lectura
        self._abrir_publicacion = abrir_publicacion
        self._ejecutor = ejecutor
        self._reloj = reloj
        self._monotono = monotono
        self._nuevo_identificador = generador_de_identificador
        self._intervalo = intervalo_de_progreso

    # ------------------------------------------------------------------
    # Catalogo y panel (lectura)
    # ------------------------------------------------------------------

    @staticmethod
    def catalogo() -> dict:
        juegos = {}
        for j in JUEGOS:
            r = lv.REGLAS[j]
            juegos[j] = {"nombre": NOMBRES[j], "estadisticas": fm.definicion_de_familia(j),
                         "reglas": {"rango": list(r.rango), "cantidad": r.cantidad,
                                    "superbalota": list(r.superbalota) if r.superbalota else None,
                                    "pares_numero_color_con_multiplicidad": r.colores}}
        return {"version_motor": fm.VERSION_MOTOR, "iteraciones": list(fm.ITERACIONES_ADMITIDAS),
                "iteraciones_predeterminadas": fm.ITERACIONES_PREDETERMINADAS,
                "semilla_predeterminada": fm.SEMILLA_PREDETERMINADA, "semilla_maxima": fm.SEMILLA_MAXIMA,
                "alpha": fm.ALPHA, "algoritmo": fm.algoritmo(), "juegos": juegos, "nota": fm.NOTA,
                "cobertura_del_ajuste": fm.COBERTURA_AJUSTE, "estado_de_uso": fa.ESTADO_DE_USO,
                "determinismo": ("Misma identidad (historico, corte, reglas, algoritmo, version de NumPy, semilla e "
                                 "iteraciones) -> mismo contenido y misma huella, con cualquier tamano de lote. La "
                                 "identidad de bytes entre versiones de NumPy se comprueba, no se supone.")}

    def _historico(self, juego: str, hasta: int | None = None) -> list:
        with self._abrir() as lectura:
            return list(leer_historico(lectura, juego, hasta))

    def panel(self) -> list[dict]:
        return [self.diagnostico(j) for j in JUEGOS]

    def diagnostico(self, juego: str) -> dict:
        _validar_juego(juego)
        salida = {"juego": juego, "nombre": NOMBRES[juego], "slug": SLUGS[juego], "activa": self._cerrojo.activa(juego)}
        try:  # solo un fallo de lectura de la base; una fila alterada se marca en el listado
            historico = self._leer(lambda lectura: list(leer_historico(lectura, juego)))
            salida["simulaciones"] = self.listar(juego, 10)
        except SimulacionesError as error:
            if error.codigo != "base_no_disponible":
                raise
            return {**salida, "estado": "base_no_disponible", "mensaje": str(error), "simulaciones": []}
        if not historico:
            return {**salida, "estado": "sin_datos", "mensaje": "No hay sorteos cargados para este juego."}
        try:
            h = fm.preparar(juego, historico)
        except fm.MuestraInsuficienteFase7 as error:
            return {**salida, "estado": "muestra_insuficiente", "mensaje": str(error)}
        except fm.SimulacionFase7NoValida as error:
            return {**salida, "estado": "historico_no_valido", "mensaje": str(error)}
        datos = fm.descripcion_historico(h)
        return {**salida, "estado": "disponible", "datos": datos, "corte": h.instantanea.corte,
                "frescura": evaluar_frescura(h.instantanea.sorteos[-1].fecha, self._reloj().date()),
                "mecanismo": fm.reglas_y_mecanismo(h)["mecanismo"],
                "dobles_por_iteracion": h.dobles_por_iteracion}

    # ------------------------------------------------------------------
    # Trabajo en segundo plano
    # ------------------------------------------------------------------

    def iniciar(self, juego: str, iteraciones, semilla=fm.SEMILLA_PREDETERMINADA, corte=None,
                origen: str = "web") -> Inicio:
        _validar_juego(juego)
        try:
            iteraciones, semilla = fm.validar_parametros(iteraciones, semilla)
        except fm.SimulacionFase7NoValida as error:
            raise SimulacionesError("no_valido", str(error)) from error
        if corte is not None and (isinstance(corte, bool) or not isinstance(corte, int) or corte < 1):
            raise SimulacionesError("no_valido", "el corte debe ser un numero de sorteo entero positivo")
        parametros = {"juego": juego, "iteraciones": iteraciones, "semilla": semilla, "corte": corte}
        ahora = self._reloj()
        identificador = self._nuevo_identificador(ahora)
        cerrojos = self._cerrojo.adquirir((juego,), identificador)
        if isinstance(cerrojos, dict):
            raise EjecucionActivaError(cerrojos)
        ejecucion = {"id": identificador, "tipo": TIPO_DE_TRABAJO, "origen": origen, "estado": "en_curso",
                     "fase": "inicio", "iniciada_en": ahora.isoformat(), "finalizada_en": None, "orden": [juego],
                     "parametros": parametros, "juegos": {juego: {"juego": juego, "estado": "pendiente", "fase": "inicio"}}}
        try:
            self._registro.guardar(ejecucion)
        except BaseException:
            cerrojos.liberar()
            raise
        return Inicio(ejecucion, cerrojos, juego, parametros)

    def ejecutar(self, inicio: Inicio) -> dict:
        ejecucion = inicio.ejecucion
        try:
            ejecucion["fase"] = "trabajando"
            r = self._procesar(ejecucion, inicio.juego, inicio.parametros, inicio.observador)
            ejecucion["juegos"][inicio.juego] = r
            ejecucion["estado"] = "exito" if r["estado"] in ("terminado", "reutilizado") else "fallo"
            ejecucion["resumen"] = {r["estado"]: 1}
            ejecucion["fase"] = "terminado"
            ejecucion["finalizada_en"] = self._reloj().isoformat()
            self._registro.guardar(ejecucion)
            return ejecucion
        finally:
            inicio.cerrojos.liberar()

    def ahora(self, juego: str, iteraciones, semilla=fm.SEMILLA_PREDETERMINADA, corte=None,
              origen: str = "comando") -> dict:
        return self.ejecutar(self.iniciar(juego, iteraciones, semilla, corte, origen))

    def _avance(self, ejecucion: dict, r: dict, fase: str, forzar: bool = True, observador=None, **datos) -> None:
        ahora = self._monotono()
        if not forzar and ahora - r.get("_escrito", float("-inf")) < self._intervalo:
            r.update({"fase": fase, **datos})
            return
        r.update({"fase": fase, **datos})
        r["_escrito"] = ahora
        ejecucion["juegos"][r["juego"]] = {k: v for k, v in r.items() if not k.startswith("_")}
        self._registro.guardar(ejecucion)
        if observador is not None:
            observador(ejecucion)

    def _cerrar(self, r: dict, estado: str, mensaje: str | None = None, **extra) -> dict:
        r.update({"estado": estado, "fase": "terminado", "fin": self._reloj().isoformat(), "mensaje": mensaje, **extra})
        return {k: v for k, v in r.items() if not k.startswith("_")}

    def _procesar(self, ejecucion: dict, juego: str, parametros: dict, observador=None) -> dict:
        r = {"juego": juego, "estado": "en_curso", "fase": "inicio", "inicio": self._reloj().isoformat(), "fin": None,
             "resultado": None, "clave": None, "mensaje": None}
        avance = (lambda fase, forzar=True, **d: self._avance(ejecucion, r, fase, forzar, observador, **d))
        try:
            return self._simular_juego(ejecucion, r, juego, parametros, avance)
        except fm.MuestraInsuficienteFase7 as error:
            return self._cerrar(r, "muestra_insuficiente", str(error))
        except fm.SimulacionFase7NoValida as error:
            return self._cerrar(r, "historico_no_valido", str(error))
        except TiempoAgotadoError as error:
            return self._cerrar(r, "tiempo_agotado", f"Tiempo agotado: {mensaje_legible(error)}")
        except TrabajadorFallidoError as error:  # el proceso trabajador murio: nada se publico
            return self._cerrar(r, "fallo", f"Fallo del proceso de trabajo: {mensaje_legible(error)}")
        except fa.ArtefactoSimulacionError as error:
            return self._cerrar(r, "alterado", f"La fila guardada con esta clave no es integra: {error}. No se "
                                                "sobrescribe; revisala antes de repetir.")
        except PublicacionConcurrenteError as error:
            return self._cerrar(r, "fallo", mensaje_legible(error))
        except SimulacionesError as error:
            estado = error.codigo if error.codigo in ("base_no_disponible", "alterado", "no_valido") else "fallo"
            return self._cerrar(r, estado, str(error))
        except JuegoNoEncontradoError as error:
            return self._cerrar(r, "fallo", mensaje_legible(error))
        except Exception as error:  # base caida u otro fallo inesperado: explicito, sin publicar
            return self._cerrar(r, "fallo", mensaje_legible(error))

    def _simular_juego(self, ejecucion: dict, r: dict, juego: str, parametros: dict, avance) -> dict:
        avance("obteniendo_datos")
        corte = parametros.get("corte")
        try:
            with self._abrir() as lectura:
                entidad = lectura.juego_repository.obtener_por_codigo(juego)
                if entidad is None:
                    raise JuegoNoEncontradoError(juego)
                historico = list(leer_historico(lectura, juego, corte))
        except JuegoNoEncontradoError:
            raise
        except Exception as error:  # una sola lectura; sin ella no se simula
            raise SimulacionesError("base_no_disponible", mensaje_legible(error)) from error
        if not historico:
            raise fm.MuestraInsuficienteFase7(f"No hay sorteos cargados de {juego}"
                                              + (f" hasta el corte {corte}" if corte is not None else ""))
        if corte is not None and historico[-1].numero_sorteo != corte:
            raise SimulacionesError("no_valido", f"el corte {corte} no es un sorteo cargado de {juego}")
        h = fm.preparar(juego, historico, corte)
        param = fa.parametros(fa.identidad(h, parametros["iteraciones"], parametros["semilla"]))
        clave = param["clave"]
        r.update({"clave": clave, "corte": h.instantanea.corte, "sorteos": h.sorteos})
        existente = self._existente(entidad.id, juego, clave)
        if existente is not None:
            return self._cerrar(r, "reutilizado", "Ya existia una simulacion integra con la misma identidad.",
                                resultado=str(existente.id))
        iteraciones = parametros["iteraciones"]
        avance("simulando", hechas=0, de=iteraciones)
        progreso = (lambda fase, **d: avance(fase, forzar=d.get("hechas") == d.get("de"), **d))
        calculado = self._ejecutor.simular(juego, lv.sorteos_canonicos(h.instantanea), iteraciones,
                                           parametros["semilla"], avance=progreso)
        if calculado["historico_sha256"] != param["historico"]["sha256"]:
            raise RuntimeError("el trabajador simulo un historico distinto del leido")
        resumen = fa.resultado(param, calculado["contenido"], {
            **calculado["procesamiento"], "duracion_ms": calculado["duracion_ms"], "entorno": entorno(),
            "origen": ejecucion["origen"], "ejecucion": ejecucion["id"],
            "nota": "metadatos de esta ejecucion; no forman parte del resultado cientifico ni de la identidad"})
        avance("publicando")
        fila = Simulacion(id=None, juego_id=entidad.id, num_iteraciones=iteraciones, parametros=param,
                          resultado_resumen=resumen, duracion_ms=calculado["duracion_ms"])
        with self._abrir_publicacion() as publicacion:
            publicada, creada = publicacion.simulaciones_repository.publicar(fila, clave)
        if not creada:
            self._verificar_fila(publicada, juego)
            return self._cerrar(r, "reutilizado", "Otra ejecucion publico la misma identidad antes; se conserva "
                                                  "esa fila.", resultado=str(publicada.id))
        try:  # verificacion tras confirmar (ida y vuelta por la base)
            releida = self._fila(publicada.id)
        except SimulacionesError as error:
            if error.codigo != "base_no_disponible":
                raise
            return self._cerrar(r, "terminado", f"Publicada; no se pudo releer para verificarla ({error}). "
                                                "Verificala cuando la base este disponible.", resultado=str(publicada.id))
        if releida["resultado_resumen"]["contenido_sha256"] != resumen["contenido_sha256"]:
            raise fa.ArtefactoSimulacionError("la fila releida no coincide con la publicada")
        return self._cerrar(r, "terminado", None, resultado=str(publicada.id))

    def _existente(self, juego_id, juego: str, clave: str) -> Simulacion | None:
        filas = self._leer(lambda lectura: lectura.simulaciones_repository.por_clave(juego_id, clave))
        if not filas:
            return None
        for f in filas:  # todas deben ser integras; si hay mas de una, deben tener el mismo contenido
            self._verificar_fila(f, juego)
        if len({f.resultado_resumen["contenido_sha256"] for f in filas}) != 1:
            raise fa.ArtefactoSimulacionError("hay filas duplicadas con la misma clave y contenido distinto")
        return filas[0]

    # ------------------------------------------------------------------
    # Estado de las ejecuciones
    # ------------------------------------------------------------------

    def consultar_ejecucion(self, identificador: str) -> dict | None:
        return self._derivar(self._registro.obtener(identificador))

    def recientes(self, limite: int = 20) -> list[dict]:
        return [self._derivar(e) for e in self._registro.listar(limite)]

    def _derivar(self, ejecucion: dict | None) -> dict | None:
        """Proyeccion de lectura (no escribe). Observa UNA vez si el
        trabajador mantiene el cerrojo de la ejecucion: vivo -> `en_curso` es
        una instantanea valida hasta el siguiente sondeo. Libre -> relee el
        registro, porque el trabajador escribe su cierre antes de soltarlo:
        un cierre persistido se devuelve tal cual y solo un `en_curso`
        confirmado se informa `interrumpida`."""
        if ejecucion is None or ejecucion.get("estado") != "en_curso":
            return ejecucion
        if self._cerrojo.ejecucion_viva(ejecucion["id"]):
            return ejecucion
        actual = self._registro.obtener(ejecucion["id"])
        actual = actual if isinstance(actual, dict) else ejecucion
        if actual.get("estado") != "en_curso":
            return actual
        return {**actual, "estado": "interrumpida", "fase": "interrumpida", "mensaje": MENSAJE_INTERRUMPIDA}

    def abortar(self, inicio: Inicio, motivo: str) -> None:
        inicio.cerrojos.liberar()
        try:
            self._registro.guardar({**inicio.ejecucion, "estado": "interrumpida", "fase": "interrumpida",
                                    "finalizada_en": self._reloj().isoformat(),
                                    "mensaje": f"No se pudo iniciar el trabajo: {mensaje_legible(motivo)}"})
        except OSError:
            pass

    def recuperar(self) -> list[str]:
        """Persiste `interrumpida` SOLO para interrupciones confirmadas. La
        lectura del registro y la observacion del cerrojo solo seleccionan
        candidatas; la actualizacion la decide `_interrumpir_confirmada` bajo
        el recurso de la propia ejecucion. Nunca sobrescribe un cierre
        terminal ni toca una ejecucion activa."""
        marcadas = []
        for e in self._registro.listar(200):
            if not isinstance(e, dict) or e.get("estado") != "en_curso" or not identificador_valido(e.get("id")):
                continue
            identificador = e["id"]
            if self._cerrojo.ejecucion_viva(identificador):
                continue
            if self._interrumpir_confirmada(identificador):
                marcadas.append(identificador)
        return marcadas

    def _interrumpir_confirmada(self, identificador: str) -> bool:
        # Solo el cerrojo de la ejecucion (sin juegos): es el que el trabajador
        # mantiene hasta escribir su cierre, y no espera a otra simulacion del
        # mismo juego.
        try:
            recurso = self._cerrojo.adquirir((), identificador)
        except OSError as error:
            if error.errno == errno.EBUSY:
                return False  # el trabajador sigue vivo
            raise
        try:
            actual = self._registro.obtener(identificador)  # relectura bajo exclusion
            if (not isinstance(actual, dict) or actual.get("id") != identificador
                    or actual.get("estado") != "en_curso" or not isinstance(actual.get("juegos", {}), dict)):
                return False
            juegos = {j: dict(x) if isinstance(x, dict) else x for j, x in actual.get("juegos", {}).items()}
            for x in juegos.values():
                if isinstance(x, dict) and x.get("estado") in ("pendiente", "en_curso"):
                    x["estado"] = "interrumpido"
            self._registro.guardar({**actual, "estado": "interrumpida", "fase": "interrumpida",
                                    "mensaje": MENSAJE_INTERRUMPIDA, "finalizada_en": self._reloj().isoformat(),
                                    "juegos": juegos})
            return True
        finally:
            recurso.liberar()

    # ------------------------------------------------------------------
    # Resultados guardados (tabla `simulaciones`)
    # ------------------------------------------------------------------

    @staticmethod
    def _como_dict(f: Simulacion) -> dict:
        return {"id": str(f.id), "juego": f.parametros.get("juego"), "num_iteraciones": f.num_iteraciones,
                "ejecutado_en": _iso(f.ejecutado_en), "duracion_ms": f.duracion_ms, "parametros": f.parametros,
                "resultado_resumen": f.resultado_resumen}

    def _leer(self, funcion):
        """Una lectura de la base; si no esta disponible, error con codigo estable."""
        try:
            with self._abrir() as lectura:
                return funcion(lectura)
        except SimulacionesError:
            raise
        except Exception as error:
            raise SimulacionesError("base_no_disponible", mensaje_legible(error)) from error

    @staticmethod
    def _es_de_fase7(f: Simulacion) -> bool:
        """Mismo criterio que el filtro SQL del listado (`parametros ->> 'clave'`)."""
        return isinstance(f.parametros, dict) and f.parametros.get("clave") is not None

    @staticmethod
    def _verificar_fila(f: Simulacion, juego_de_la_fila: str | None) -> None:
        """La comprobacion de toda lectura de la tabla; `juego_de_la_fila` es
        el codigo del juego de su `juego_id` (None si no es ninguno)."""
        fa.verificar_fila(f.parametros, f.resultado_resumen, f.num_iteraciones, juego_de_la_fila)

    def _fila(self, identificador) -> dict:
        ident = _uuid(identificador)

        def leer(lectura):  # no toca el JSON: el juego sale de la columna `juego_id`
            f = lectura.simulaciones_repository.obtener(ident)
            entidad = None if f is None else lectura.juego_repository.obtener_por_id(f.juego_id)
            return f, None if entidad is None else entidad.codigo
        f, juego_de_la_fila = self._leer(leer)
        if f is None or not self._es_de_fase7(f):
            raise SimulacionesError("no_encontrado", f"No existe la simulacion de la Fase 7 {identificador}")
        try:
            self._verificar_fila(f, juego_de_la_fila)
        except fa.ArtefactoSimulacionError as error:
            raise SimulacionesError("alterado", f"La simulacion {identificador} no es integra: {error}") from error
        return {**self._como_dict(f), "integridad": "verificada"}

    def obtener(self, identificador) -> dict:
        return self._fila(identificador)

    def listar(self, juego: str | None = None, limite: int = 50) -> list[dict]:
        """Cada fila se comprueba por separado: una alterada se identifica (id,
        juego de su `juego_id`, hora y motivo) sin exponer su identidad ni su
        umbral, y no impide listar las demas."""
        if juego is not None:
            _validar_juego(juego)

        def leer(lectura):
            codigos = {}
            for codigo in (JUEGOS if juego is None else (juego,)):
                entidad = lectura.juego_repository.obtener_por_codigo(codigo)
                if entidad is not None:
                    codigos[entidad.id] = codigo
            if juego is None:
                return lectura.simulaciones_repository.listar(None, limite), codigos
            if not codigos:
                return [], codigos
            (juego_id,) = codigos
            return lectura.simulaciones_repository.listar(juego_id, limite), codigos
        filas, codigos = self._leer(leer)
        salida = []
        for f in filas:
            juego_de_la_fila = codigos.get(f.juego_id)
            fila = {"id": str(f.id), "juego": juego_de_la_fila, "clave": None, "corte": None,
                    "iteraciones": f.num_iteraciones, "semilla": None, "ejecutado_en": _iso(f.ejecutado_en),
                    "duracion_ms": f.duracion_ms, "integridad": "alterada", "motivo": None,
                    "alguna_supera_umbral_exploratorio": None}
            try:
                self._verificar_fila(f, juego_de_la_fila)
            except fa.ArtefactoSimulacionError as error:
                fila["motivo"] = str(error)
            else:
                p = f.parametros
                fila.update(clave=p["clave"], corte=p["corte"], semilla=p["semilla"], integridad="verificada",
                            alguna_supera_umbral_exploratorio=f.resultado_resumen["contenido"][
                                "alguna_supera_umbral_exploratorio"])
            salida.append(fila)
        return salida

    def exportar_json(self, identificador) -> str:
        return fa.json_de_exportacion(self._fila(identificador))

    def exportar_csv(self, identificador) -> str:
        return fa.csv_de_exportacion(self._fila(identificador))

    def verificar(self, identificador, reproducir: bool = False) -> dict:
        """Integridad de la fila, coincidencia del historico hasta el corte con
        la base actual y, si se pide, reproduccion (vuelve a simular en el
        ejecutor y compara la huella del contenido). No escribe nada."""
        fila = self._fila(identificador)
        p = fila["parametros"]
        salida = {"id": fila["id"], "clave": p["clave"], "integridad": "verificada", "base": None, "reproduccion": None}
        try:
            historico = self._historico(p["juego"], p["corte"])
            h = fm.preparar(p["juego"], historico, p["corte"])
        except fm.SimulacionFase7NoValida as error:
            salida["base"] = {"estado": "historico_no_valido", "mensaje": str(error)}
            return salida
        except Exception as error:
            salida["base"] = {"estado": "base_no_disponible", "mensaje": mensaje_legible(error)}
            return salida
        actual = fm.descripcion_historico(h)["sha256"]
        coincide = actual == p["historico"]["sha256"]
        salida["base"] = {"estado": "coincide" if coincide else "difiere", "sha256_guardado": p["historico"]["sha256"],
                          "sha256_actual": actual}
        if reproducir:
            if not coincide:
                salida["reproduccion"] = {"estado": "no_aplicable", "mensaje": "el historico actual hasta el corte "
                                                                                "difiere del simulado"}
            elif p["algoritmo"]["numpy"] != np.__version__:
                salida["reproduccion"] = {"estado": "no_aplicable", "mensaje": (
                    f"version de NumPy distinta ({np.__version__} frente a {p['algoritmo']['numpy']}): la identidad "
                    "de bytes no se garantiza entre versiones")}
            else:
                calculado = self._ejecutor.simular(p["juego"], lv.sorteos_canonicos(h.instantanea), p["iteraciones"],
                                                   p["semilla"])
                guardada = fila["resultado_resumen"]["contenido_sha256"]
                nueva = fa.sha256(calculado["contenido"])
                salida["reproduccion"] = {"estado": "reproducida" if nueva == guardada else "difiere",
                                          "contenido_sha256_guardado": guardada, "contenido_sha256_nuevo": nueva}
        return salida
