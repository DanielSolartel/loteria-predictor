"""Abre el visor comprobado con el Python de la tarea operativa de Fase 6."""

import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import mkdtemp
from zipfile import BadZipFile, ZipFile

from perfil_piloto_windows import (
    CARPETA_OPERATIVA, VERSION_OPERATIVA, PerfilPilotoError,
    _directorio_local, _instancia_unica, _sin_enlace,
)


EVIDENCIA = re.compile(r"evidencia-f11-fase6-[a-f0-9]{12}\.json")
VISOR = "visor.zip"


def abrir(paquete: Path, perfil: Path, backend: str, configuracion: str) -> int:
    evidencias = perfil / "evidencias"
    _sin_enlace(evidencias)
    evidencias.mkdir(mode=0o700, exist_ok=True)
    trabajo = Path(mkdtemp(dir=perfil, prefix="sesion-"))
    visor = trabajo / VISOR
    conservadas = 0
    try:
        with ZipFile(paquete) as archivos:
            archivos.extract(VISOR, trabajo)
        codigo = subprocess.run([sys.executable, "-I", "-B", visor, backend, configuracion],
                                env={**os.environ, "LP11_INSTALADO": "1"}, check=False).returncode
    finally:
        try:
            for origen in trabajo.iterdir():
                if not EVIDENCIA.fullmatch(origen.name):
                    continue
                _sin_enlace(origen)
                destino = evidencias / origen.name
                _sin_enlace(destino)
                if destino.exists():
                    raise PerfilPilotoError("Ya existe un archivo con el nombre de esta evidencia.")
                origen.rename(destino)
                conservadas += 1
                print(f"Evidencia guardada: {destino}", flush=True)
        finally:
            visor.unlink(missing_ok=True)
            if not any(trabajo.iterdir()):
                trabajo.rmdir()
    if codigo == 0 and not conservadas:
        raise PerfilPilotoError("La consola mostró el resultado. No se encontró el archivo de evidencia.")
    return codigo


def main() -> int:
    try:
        if len(sys.argv) != 3:
            raise PerfilPilotoError("Abre Lotería Predictor desde el menú Inicio.")
        perfil = _directorio_local(CARPETA_OPERATIVA, VERSION_OPERATIVA)
        with _instancia_unica(perfil) as libre:
            if not libre:
                raise PerfilPilotoError("Lotería Predictor ya está abierto. Usa la pestaña existente.")
            return abrir(Path(sys.argv[0]).resolve(strict=True), perfil, sys.argv[1], sys.argv[2])
    except PerfilPilotoError as error:
        print(error, flush=True)
    except (BadZipFile, OSError, ValueError, KeyError, KeyboardInterrupt) as error:
        print(f"Lotería Predictor se detuvo ({type(error).__name__}). Revisa la salida de la consola.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
