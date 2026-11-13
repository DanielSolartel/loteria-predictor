"""Empaqueta el ensayo operativo para el Python que ya utiliza Fase 6."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = ("__init__.py", "piloto_operativo.py", "piloto_escritorio.py", "piloto_windows.py", "perfil_piloto_windows.py")


def construir(interfaz: Path, salida: Path):
    if not (interfaz / "index.html").is_file() or not (interfaz / "assets").is_dir():
        raise ValueError("Compila primero el frontend en modo escritorio.")
    backend = RAIZ / "backend"
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RAIZ).strip()
    with ZipFile(salida, "x") as paquete:
        def agregar(nombre: str, datos: bytes):
            if nombre.endswith(".py"):
                compile(datos, nombre, "exec")
            paquete.writestr(ZipInfo(nombre, (2026, 11, 12, 0, 0, 0)), datos, compress_type=ZIP_DEFLATED)

        agregar("__main__.py", b"from scripts.piloto_operativo import main\nraise SystemExit(main())\n")
        agregar("base-codigo.txt", base + b"\n")
        for fuente in sorted((backend / "app").rglob("*.py")):
            agregar(fuente.relative_to(backend).as_posix(), fuente.read_bytes())
        for script in SCRIPTS:
            agregar(f"scripts/{script}", (backend / "scripts" / script).read_bytes())
        for archivo in sorted(interfaz.rglob("*")):
            if archivo.is_file():
                agregar(f"interfaz/{archivo.relative_to(interfaz).as_posix()}", archivo.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interfaz", default=RAIZ / "frontend/dist-escritorio", type=Path)
    parser.add_argument("--salida", required=True, type=Path)
    args = parser.parse_args()
    construir(args.interfaz, args.salida)
