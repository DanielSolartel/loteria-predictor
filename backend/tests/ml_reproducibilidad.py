"""Referencia directa en un proceso de prueba aislado, sin cambiar el servidor.

No usa el ejecutor del producto: llama a evaluar con la misma instantánea,
recetas, protocolo y recursos numéricos que el trabajador. El padre conserva
su entorno y sus pools, incluso durante el cálculo.
"""
from dataclasses import asdict
import multiprocessing
import os
import queue
import time


def _local(cola, tarea):
    from threadpoolctl import threadpool_info
    from app.application.ml import laboratorio_evaluacion as le, laboratorio_modelos as lm, laboratorio_variables as lv
    from app.infrastructure.recursos_ml import limitar_trabajador
    try:
        with limitar_trabajador(tarea["hilos"]):
            informe, _ = le.evaluar(lv.instantanea_desde_canonicos(tarea["juego"], tarea["sorteos"]),
                                   [lm.CATALOGO[i] for i in tarea["modelos"]], le.Protocolo(**tarea["protocolo"]))
            cola.put(("ok", informe, threadpool_info()))
    except BaseException as e:
        cola.put(("error", repr(e)))


def referencia_local(instantanea, entradas, protocolo, hilos, plazo=120):
    from threadpoolctl import threadpool_info
    from app.application.ml import laboratorio_variables as lv
    nombres = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    antes = {n: os.environ.get(n) for n in nombres}
    def pools():
        return sorted((p["filepath"], p["num_threads"]) for p in threadpool_info())
    perfil = pools()
    ctx = multiprocessing.get_context("spawn")
    cola = ctx.Queue()
    tarea = {"juego": instantanea.codigo, "sorteos": lv.sorteos_canonicos(instantanea),
             "modelos": [e.id for e in entradas], "protocolo": asdict(protocolo), "hilos": hilos}
    p = ctx.Process(target=_local, args=(cola, tarea))
    p.start()
    muestras, limite = 0, time.monotonic() + plazo
    try:
        while time.monotonic() < limite:
            assert pools() == perfil and {n: os.environ.get(n) for n in nombres} == antes
            muestras += 1
            try:
                salida = cola.get(timeout=.05)
                break
            except queue.Empty:
                if not p.is_alive():
                    raise AssertionError("Referencia local terminó sin resultado")
        else:
            raise TimeoutError("Referencia local agotó su plazo")
        assert salida[0] == "ok", salida
        assert muestras and all(m["num_threads"] <= hilos for m in salida[2])
        return salida[1]
    finally:
        p.join(10)
        if p.is_alive():
            p.kill(); p.join(10)
        cola.close(); cola.join_thread()
        assert pools() == perfil and {n: os.environ.get(n) for n in nombres} == antes
