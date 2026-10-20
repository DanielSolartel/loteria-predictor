"""Límites exclusivos del trabajador, incluidas bibliotecas cargadas después.

No invocar desde el servidor: los límites nativos son de proceso. El
ExitStack restaura tanto el entorno heredado como las bibliotecas ya cargadas.
"""
from contextlib import ExitStack
import os


def limitar_trabajador(hilos: int) -> ExitStack:
    from threadpoolctl import threadpool_limits

    salida = ExitStack()
    nombres = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    anteriores = {nombre: os.environ.get(nombre) for nombre in nombres}

    def restaurar():
        for nombre, valor in anteriores.items():
            if valor is None:
                os.environ.pop(nombre, None)
            else:
                os.environ[nombre] = valor

    salida.callback(restaurar)
    try:
        for nombre in nombres:
            os.environ[nombre] = str(hilos)
        salida.enter_context(threadpool_limits(limits=hilos))
    except BaseException:
        salida.close()
        raise
    return salida
