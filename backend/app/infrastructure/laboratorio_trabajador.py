"""
Proceso trabajador del laboratorio de modelos (Producto 4).

Cada comparacion, generacion o verificacion que entrena o predice se ejecuta
en un proceso NUEVO creado con el contexto `spawn` (el mismo mecanismo en
Windows y en Linux). El proceso que atiende la web y la operacion diaria de
Producto 3 no cambia nunca sus hilos numericos: solo el trabajador fija
`laboratorio_modelos.HILOS` para si mismo (`threadpool_limits`), y lo pierde
al terminar.

Entrada: la instantanea ya congelada en forma canonica (la lectura de la base
termino antes; ninguna sesion SQL pasa al trabajador), los identificadores de
las recetas del catalogo y el protocolo, o el informe y el modelo de un
pronostico. Salida por una cola: mensajes de progreso y un unico resultado o
error. El trabajador no escribe archivos: la publicacion inmutable la hace el
proceso padre. Si el trabajador muere o termina sin resultado, el padre lanza
`TrabajadorFallidoError`; si el padre muere, la ejecucion queda sin cerrojo
vivo y se informa como interrumpida (Producto 3), y el trabajador huerfano
termina sin publicar nada.
"""
from __future__ import annotations

import multiprocessing
import queue
import threading
from collections.abc import Callable

from app.application.interfaces.ejecutor_laboratorio import EjecutorDeLaboratorio, TrabajadorFallidoError

ESPERA_DE_SONDEO = 0.2


def _trabajador(cola, tarea: dict) -> None:
    """Punto de entrada del proceso hijo (importable: requisito de `spawn`)."""
    from threadpoolctl import threadpool_limits

    from app.application.ml import laboratorio_artefactos as la
    from app.application.ml import laboratorio_evaluacion as le
    from app.application.ml import laboratorio_modelos as lm
    from app.application.ml import laboratorio_variables as lv

    limite = threadpool_limits(limits=lm.HILOS)  # solo este proceso dedicado
    try:
        if tarea["tipo"] == "evaluar":
            instantanea = lv.instantanea_desde_canonicos(tarea["juego"], tarea["sorteos"])
            entradas = [lm.CATALOGO[i] for i in tarea["modelos"]]
            protocolo = le.Protocolo(**tarea["protocolo"])
            resultado = le.evaluar(instantanea, entradas, protocolo,
                                   avance=lambda fase, **datos: cola.put(("avance", fase, datos)))
        else:
            resultado = la.cuerpo_del_pronostico(tarea["informe"], lm.CATALOGO[tarea["modelo"]])
        cola.put(("resultado", resultado))
    except lm.CandidatoNoDisponible as error:
        cola.put(("candidato_no_disponible", error.estado, error.motivo))
    except le.MuestraInsuficienteError as error:
        cola.put(("muestra_insuficiente", error.codigo, error.sorteos, error.evaluables, error.requeridos))
    except lv.HistoricoNoValidoError as error:
        cola.put(("historico_no_valido", str(error)))
    except la.ArtefactoLaboratorioError as error:
        cola.put(("artefacto", str(error)))
    except BaseException as error:  # error inesperado: se informa, el padre decide
        cola.put(("fallo", f"{type(error).__name__}: {error}"[:500]))
    finally:
        limite.restore_original_limits()


class EjecutorEnProceso(EjecutorDeLaboratorio):
    def __init__(self, al_lanzar: Callable | None = None):
        """`al_lanzar(proceso)` es un gancho de pruebas (p. ej. para interrumpir)."""
        self._contexto = multiprocessing.get_context("spawn")
        self._al_lanzar = al_lanzar
        self._lock = threading.Lock()
        self.activos = 0
        self.maximo_simultaneo = 0
        self.lanzados = 0

    def evaluar(self, instantanea, entradas, protocolo, avance=None):
        from dataclasses import asdict

        from app.application.ml import laboratorio_modelos as lm
        from app.application.ml import laboratorio_variables as lv

        for e in entradas:
            if lm.CATALOGO.get(e.id) != e:
                raise ValueError(f"el trabajador solo admite recetas del catalogo: {e.id}")
        tarea = {"tipo": "evaluar", "juego": instantanea.codigo, "sorteos": lv.sorteos_canonicos(instantanea),
                 "modelos": [e.id for e in entradas], "protocolo": asdict(protocolo)}
        return tuple(self._ejecutar(tarea, avance))

    def pronostico(self, informe, entrada):
        return self._ejecutar({"tipo": "pronostico", "informe": informe, "modelo": entrada.id})

    def _ejecutar(self, tarea: dict, avance=None):
        from app.application.ml import laboratorio_artefactos as la
        from app.application.ml import laboratorio_evaluacion as le
        from app.application.ml import laboratorio_modelos as lm
        from app.application.ml import laboratorio_variables as lv

        cola = self._contexto.Queue()
        proceso = self._contexto.Process(target=_trabajador, args=(cola, tarea), daemon=True,
                                         name=f"laboratorio-{tarea['tipo']}")
        proceso.start()
        with self._lock:
            self.lanzados += 1
            self.activos += 1
            self.maximo_simultaneo = max(self.maximo_simultaneo, self.activos)
        try:
            if self._al_lanzar is not None:
                self._al_lanzar(proceso)
            while True:
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
                if tipo == "muestra_insuficiente":
                    raise le.MuestraInsuficienteError(*mensaje[1:])
                if tipo == "historico_no_valido":
                    raise lv.HistoricoNoValidoError(mensaje[1])
                if tipo == "artefacto":
                    raise la.ArtefactoLaboratorioError(mensaje[1])
                raise TrabajadorFallidoError(f"el proceso trabajador fallo: {mensaje[1]}")
        finally:
            proceso.join(timeout=10)
            if proceso.is_alive():
                proceso.terminate()
                proceso.join(timeout=10)
            cola.close()
            with self._lock:
                self.activos -= 1
