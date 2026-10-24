"""Fase 7: medicion de rendimiento y memoria del motor con datos SINTETICOS
representativos (no es una prueba de pytest; no usa la base ni escribe en el
repositorio).

Tamanos de los historicos: los documentados al 23 de octubre de 2026 (Baloto y
Revancha 2081..2725 = 645 sorteos, MiLoto 97, ColorLoto 229), generados con
`random.Random`. Cada punto (juego, iteraciones) corre en un PROCESO NUEVO, como
el trabajador real, y mide:
- `segundos`: tiempo de `fase7.motor.calcular` (sin el arranque del proceso);
- `pico_memoria_mb`: pico del proceso segun el sistema operativo (Linux:
  `ru_maxrss`; Windows: `PeakWorkingSetSize`), y `base_mb` tras importar, para
  separar el coste de las importaciones;
- `lote`, `lotes` y `dobles_por_iteracion`.

Uso (desde `backend`):
  python tests/medicion_fase7.py [--iteraciones 100,1000,10000,100000,1000000] [--juegos BALOTO,MILOTO]
Salida: JSON por la salida estandar; progreso por la de errores.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TAMANOS = {"BALOTO": 645, "BALOTO_REVANCHA": 645, "MILOTO": 97, "COLORLOTO": 229}


def _pico_mb() -> float | None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Contadores(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        c = Contadores()
        c.cb = ctypes.sizeof(c)
        proceso = ctypes.windll.kernel32.GetCurrentProcess()
        if not ctypes.windll.psapi.GetProcessMemoryInfo(proceso, ctypes.byref(c), c.cb):
            return None
        return c.PeakWorkingSetSize / 2**20
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB en Linux


def _uno(juego: str, iteraciones: int) -> dict:
    sys.path.insert(0, str(BACKEND))
    from app.application.ml import laboratorio_variables as lv
    from app.application.fase7 import motor as fm
    from tests.unit import fixtures_producto1 as fx

    n = TAMANOS[juego]
    datos = fx.historico_colorloto(n) if juego == "COLORLOTO" else fx.historico_numerico(juego, n)
    canonicos = lv.sorteos_canonicos(lv.validar_instantanea(juego, datos))
    base = _pico_mb()
    inicio = time.perf_counter()
    r = fm.calcular(juego, canonicos, iteraciones, fm.SEMILLA_PREDETERMINADA)
    segundos = time.perf_counter() - inicio
    return {"juego": juego, "sorteos": n, "iteraciones": iteraciones, "segundos": round(segundos, 3),
            "pico_memoria_mb": round(_pico_mb() or -1, 1), "base_mb": round(base or -1, 1),
            **r["procesamiento"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uno", nargs=2)
    parser.add_argument("--iteraciones", default="100,1000,10000,100000,1000000")
    parser.add_argument("--juegos", default=",".join(TAMANOS))
    args = parser.parse_args()
    if args.uno:
        print(json.dumps(_uno(args.uno[0], int(args.uno[1]))))
        return 0
    import numpy

    puntos = []
    for juego in args.juegos.split(","):
        for iteraciones in (int(i) for i in args.iteraciones.split(",")):
            sys.stderr.write(f"{juego} {iteraciones}...\n")
            sys.stderr.flush()
            hecho = subprocess.run([sys.executable, "-B", __file__, "--uno", juego, str(iteraciones)], cwd=BACKEND,
                                   capture_output=True, text=True, check=True)
            puntos.append(json.loads(hecho.stdout))
            sys.stderr.write(f"  {puntos[-1]['segundos']} s, pico {puntos[-1]['pico_memoria_mb']} MB\n")
    print(json.dumps({"entorno": {"python": platform.python_version(), "numpy": numpy.__version__,
                                  "sistema": platform.system(), "version": platform.version(),
                                  "maquina": platform.machine(), "procesador": platform.processor(),
                                  "cpus": os.cpu_count()},
                      "datos": "sinteticos (random.Random), tamanos documentados al 23-10-2026",
                      "puntos": puntos}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
