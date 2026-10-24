"""
Proceso trabajador de la Fase 7 (simulaciones bajo el mecanismo uniforme).

Mismo mecanismo que Productos 4 y 5 (`laboratorio_trabajador`,
`carteras_trabajador`): cada trabajo arranca un proceso NUEVO con el
contexto `spawn` (igual en Windows y Linux), limitado a un hilo numerico. La
web y la operacion automatica no cambian sus hilos.

TIEMPO MAXIMO. Cada trabajo tiene un limite (`tiempo_maximo`, por defecto el
de la configuracion `TIEMPO_MAXIMO_TRABAJADOR_SIMULACIONES`). Si se supera,
el padre detiene el proceso (`kill`), espera su fin y lanza
`TiempoAgotadoError`: no se publica nada. Si el proceso siguiera vivo tras
detenerlo, el mensaje lo dice.

Entrada: el historico canonico ya cortado y los parametros. Salida por una
cola: avances por lote y un unico resultado o error. El trabajador no
escribe archivos ni abre la base.
"""
from __future__ import annotations

import multiprocessing
import queue
import threading
import time
from collections.abc import Callable

from app.application.interfaces.ejecutor_simulaciones import (
    EjecutorDeSimulaciones,
    TiempoAgotadoError,
    TrabajadorFallidoError,
)

ESPERA_DE_SONDEO = 0.2
TIEMPO_MAXIMO_PREDETERMINADO = 3600.0


def _trabajador(cola, tarea: dict) -> None:
    """Punto de entrada del proceso hijo (importable: requisito de `spawn`)."""
    from app.infrastructure.recursos_ml import limitar_trabajador

    from app.application.fase7 import motor as fm

    limite = limitar_trabajador(1)
    avance = (lambda fase, **datos: cola.put(("avance", fase, datos)))
    try:
        if tarea["tipo"] == "simular":
            resultado = fm.calcular(tarea["juego"], tarea["sorteos"], tarea["iteraciones"], tarea["semilla"],
                                    avance=avance)
        elif tarea["tipo"] == "dormir":  # solo pruebas del tiempo maximo
            time.sleep(tarea["segundos"])
            resultado = {"durmio": tarea["segundos"]}
        elif tarea["tipo"] == "terminar":  # solo pruebas: el hijo muere sin resultado
            import os

            os._exit(3)
        else:
            raise ValueError(f"tarea no admitida: {tarea['tipo']!r}")
        cola.put(("resultado", resultado))
    except fm.MuestraInsuficienteFase7 as error:
        cola.put(("muestra_insuficiente", str(error)))
    except fm.SimulacionFase7NoValida as error:
        cola.put(("no_valido", str(error)))
    except BaseException as error:  # error inesperado: se informa, el padre decide
        cola.put(("fallo", f"{type(error).__name__}: {error}"[:500]))
    finally:
        limite.close()


class EjecutorSimulacionesEnProceso(EjecutorDeSimulaciones):
    def __init__(self, tiempo_maximo: float | None = None, al_lanzar: Callable | None = None):
        """`tiempo_maximo` en segundos por trabajo; `al_lanzar(proceso)` es un
        gancho de pruebas."""
        self.tiempo_maximo = float(tiempo_maximo or TIEMPO_MAXIMO_PREDETERMINADO)
        self._contexto = multiprocessing.get_context("spawn")
        self._al_lanzar = al_lanzar
        self._lock = threading.Lock()
        self.activos = 0
        self.lanzados = 0

    def simular(self, juego, sorteos, iteraciones, semilla, avance=None):
        return self._ejecutar({"tipo": "simular", "juego": juego, "sorteos": sorteos, "iteraciones": iteraciones,
                               "semilla": semilla}, avance)

    def ejecutar_tarea(self, tarea: dict, avance=None):
        """Solo pruebas: tareas de control (`dormir`, `terminar`)."""
        return self._ejecutar(tarea, avance)

    def _ejecutar(self, tarea: dict, avance=None):
        from app.application.fase7 import motor as fm

        cola = self._contexto.Queue()
        proceso = self._contexto.Process(target=_trabajador, args=(cola, tarea), daemon=True,
                                         name=f"simulaciones-{tarea['tipo']}")
        inicio = time.monotonic()
        proceso.start()
        with self._lock:
            self.lanzados += 1
            self.activos += 1
        try:
            if self._al_lanzar is not None:
                self._al_lanzar(proceso)
            while True:
                if time.monotonic() - inicio > self.tiempo_maximo:
                    proceso.kill()
                    proceso.join(timeout=10)
                    sigue = proceso.is_alive()
                    raise TiempoAgotadoError(
                        f"la simulacion supero el tiempo maximo de {self.tiempo_maximo:g} s y se detuvo"
                        + (" (el proceso trabajador sigue vivo tras detenerlo)" if sigue else ""))
                try:
                    mensaje = cola.get(timeout=ESPERA_DE_SONDEO)
                except queue.Empty:
                    if proceso.is_alive():
                        continue
                    try:
                        mensaje = cola.get(timeout=1.0)
                    except queue.Empty:
                        raise TrabajadorFallidoError(
                            f"el proceso trabajador termino sin resultado (codigo de salida {proceso.exitcode})") from None
                tipo = mensaje[0]
                if tipo == "avance":
                    if avance is not None:
                        avance(mensaje[1], **mensaje[2])
                    continue
                if tipo == "resultado":
                    return mensaje[1]
                if tipo == "muestra_insuficiente":
                    raise fm.MuestraInsuficienteFase7(mensaje[1])
                if tipo == "no_valido":
                    raise fm.SimulacionFase7NoValida(mensaje[1])
                raise TrabajadorFallidoError(f"el proceso trabajador fallo: {mensaje[1]}")
        finally:
            proceso.join(timeout=10)
            if proceso.is_alive():
                proceso.terminate()
                proceso.join(timeout=10)
            cola.close()
            with self._lock:
                self.activos -= 1
