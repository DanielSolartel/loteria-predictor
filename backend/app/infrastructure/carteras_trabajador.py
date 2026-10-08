"""
Proceso trabajador de Producto 5 (modelo combinado, vector fuente y
simulacion).

Mismo mecanismo que Producto 4 (`laboratorio_trabajador`): cada trabajo
arranca un proceso NUEVO con el contexto `spawn` (igual en Windows y Linux),
que fija `laboratorio_modelos.HILOS` solo para si mismo. El proceso de la web
y de la operacion diaria no cambia sus hilos numericos.

TIEMPO MAXIMO. Cada trabajo tiene un limite (`tiempo_maximo`, por defecto el
de la configuracion: 300 s por juego). Si se supera, el padre detiene el
proceso (`kill`), espera su fin y lanza `TiempoAgotadoError`: el juego queda
`tiempo_agotado` y no se publica nada. Si el proceso siguiera vivo despues de
detenerlo, el mensaje lo dice; no se oculta.

Entrada: la instantanea canonica (la lectura de la base termino antes) o las
carteras ya guardadas. Salida por una cola: avances y un unico resultado o
error. El trabajador no escribe archivos.
"""
from __future__ import annotations

import multiprocessing
import queue
import threading
import time
from collections.abc import Callable

from app.application.interfaces.ejecutor_carteras import EjecutorDeCarteras, TiempoAgotadoError
from app.application.interfaces.ejecutor_laboratorio import TrabajadorFallidoError

ESPERA_DE_SONDEO = 0.2
TIEMPO_MAXIMO_PREDETERMINADO = 300.0


def _trabajador(cola, tarea: dict) -> None:
    """Punto de entrada del proceso hijo (importable: requisito de `spawn`)."""
    from threadpoolctl import threadpool_limits

    from app.application.ml import carteras_artefactos as ca
    from app.application.ml import carteras_construccion as cc
    from app.application.ml import carteras_ensemble as ce
    from app.application.ml import carteras_simulacion as cs
    from app.application.ml import laboratorio_modelos as lm
    from app.application.ml import laboratorio_variables as lv

    limite = threadpool_limits(limits=lm.HILOS)  # solo este proceso dedicado
    avance = (lambda fase, **datos: cola.put(("avance", fase, datos)))
    try:
        if tarea["tipo"] == "comparar":
            instantanea = lv.instantanea_desde_canonicos(tarea["juego"], tarea["sorteos"])
            resultado = ce.evaluar(instantanea, ce.ProtocoloCarteras(**tarea["protocolo"]), avance=avance)
        elif tarea["tipo"] == "fuente":
            instantanea = lv.instantanea_desde_canonicos(tarea["juego"], tarea["sorteos"])
            resultado = ce.fuente(instantanea, tarea["modelo"], tarea["perfil"], avance=avance)
        elif tarea["tipo"] == "simular":
            resultado = ca.cuerpo_de_simulacion(tarea["identidad"], tarea["elegida"], tarea["uniforme"], avance=avance)
        elif tarea["tipo"] == "dormir":  # solo pruebas del tiempo maximo
            time.sleep(tarea["segundos"])
            resultado = {"durmio": tarea["segundos"]}
        else:
            raise ValueError(f"tarea no admitida: {tarea['tipo']!r}")
        cola.put(("resultado", resultado))
    except lm.CandidatoNoDisponible as error:
        cola.put(("candidato_no_disponible", error.estado, error.motivo))
    except ce.ComponenteNoDisponible as error:
        cola.put(("componente_no_disponible", error.componente, error.estado, error.motivo))
    except ce.MuestraInsuficienteCarteras as error:
        cola.put(("muestra_insuficiente", error.codigo, error.sorteos, error.disponibles, error.requeridos, error.para))
    except lv.HistoricoNoValidoError as error:
        cola.put(("historico_no_valido", str(error)))
    except (ca.ArtefactoCarterasError, cs.SimulacionNoValida, cc.ParametrosNoValidos) as error:
        cola.put(("no_valido", str(error)))
    except BaseException as error:  # error inesperado: se informa, el padre decide
        cola.put(("fallo", f"{type(error).__name__}: {error}"[:500]))
    finally:
        limite.restore_original_limits()


class EjecutorCarterasEnProceso(EjecutorDeCarteras):
    def __init__(self, tiempo_maximo: float | None = None, al_lanzar: Callable | None = None):
        """`tiempo_maximo` en segundos por trabajo; `al_lanzar(proceso)` es un
        gancho de pruebas (p. ej. para interrumpir)."""
        self.tiempo_maximo = float(tiempo_maximo or TIEMPO_MAXIMO_PREDETERMINADO)
        self._contexto = multiprocessing.get_context("spawn")
        self._al_lanzar = al_lanzar
        self._lock = threading.Lock()
        self.activos = 0
        self.maximo_simultaneo = 0
        self.lanzados = 0

    def comparar(self, instantanea, protocolo, avance=None):
        from dataclasses import asdict

        from app.application.ml import laboratorio_variables as lv

        tarea = {"tipo": "comparar", "juego": instantanea.codigo, "sorteos": lv.sorteos_canonicos(instantanea),
                 "protocolo": asdict(protocolo)}
        return tuple(self._ejecutar(tarea, avance))

    def fuente(self, instantanea, modelo, perfil, avance=None):
        from app.application.ml import laboratorio_variables as lv

        return self._ejecutar({"tipo": "fuente", "juego": instantanea.codigo, "modelo": modelo, "perfil": perfil,
                               "sorteos": lv.sorteos_canonicos(instantanea)}, avance)

    def simular(self, identidad, elegida, uniforme, avance=None):
        return self._ejecutar({"tipo": "simular", "identidad": identidad, "elegida": elegida, "uniforme": uniforme},
                              avance)

    def ejecutar_tarea(self, tarea: dict, avance=None):
        """Solo pruebas: tareas de control (p. ej. `dormir`)."""
        return self._ejecutar(tarea, avance)

    def _ejecutar(self, tarea: dict, avance=None):
        from app.application.ml import carteras_artefactos as ca
        from app.application.ml import carteras_ensemble as ce
        from app.application.ml import laboratorio_modelos as lm
        from app.application.ml import laboratorio_variables as lv

        cola = self._contexto.Queue()
        proceso = self._contexto.Process(target=_trabajador, args=(cola, tarea), daemon=True,
                                         name=f"carteras-{tarea['tipo']}")
        inicio = time.monotonic()
        proceso.start()
        with self._lock:
            self.lanzados += 1
            self.activos += 1
            self.maximo_simultaneo = max(self.maximo_simultaneo, self.activos)
        try:
            if self._al_lanzar is not None:
                self._al_lanzar(proceso)
            while True:
                if time.monotonic() - inicio > self.tiempo_maximo:
                    proceso.kill()
                    proceso.join(timeout=10)
                    sigue = proceso.is_alive()
                    raise TiempoAgotadoError(
                        f"el trabajo supero el tiempo maximo de {self.tiempo_maximo:g} s y se detuvo"
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
                if tipo == "candidato_no_disponible":
                    raise lm.CandidatoNoDisponible(mensaje[1], mensaje[2])
                if tipo == "componente_no_disponible":
                    raise ce.ComponenteNoDisponible(*mensaje[1:])
                if tipo == "muestra_insuficiente":
                    raise ce.MuestraInsuficienteCarteras(*mensaje[1:])
                if tipo == "historico_no_valido":
                    raise lv.HistoricoNoValidoError(mensaje[1])
                if tipo == "no_valido":
                    raise ca.ArtefactoCarterasError(mensaje[1])
                raise TrabajadorFallidoError(f"el proceso trabajador fallo: {mensaje[1]}")
        finally:
            proceso.join(timeout=10)
            if proceso.is_alive():
                proceso.terminate()
                proceso.join(timeout=10)
            cola.close()
            with self._lock:
                self.activos -= 1
