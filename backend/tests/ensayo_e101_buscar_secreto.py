"""Ensayo E10.1 (Windows/Brave): ¿aparece una contraseña SINTÉTICA del ensayo en ciertos archivos?

La contraseña se pide con entrada oculta (`getpass`): no va en argumentos, en el texto del comando, en el
historial de PowerShell ni en la salida. Solo se informa, por archivo, si aparece (en UTF-8, UTF-16LE o
UTF-16BE) y el total; nunca la contraseña ni fragmentos del archivo.

Uso, desde backend/:  python -m tests.ensayo_e101_buscar_secreto --archivo "<ruta>" [--archivo "<ruta>" ...]
Salida: JSON con {"archivos": [{"archivo": <nombre>, "existe": bool, "aparece": bool}], "apariciones": n}.
Código: 0 si no aparece en ninguno, 1 si aparece en alguno, 2 si la entrada no es válida o falta un archivo.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

CODIFICACIONES = ("utf-8", "utf-16-le", "utf-16-be")


def aparece(datos: bytes, secreto: str) -> bool:
    return any(secreto.encode(codificacion) in datos for codificacion in CODIFICACIONES)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Busca una contraseña sintética (entrada oculta) en archivos")
    p.add_argument("--archivo", action="append", required=True, type=Path)
    a = p.parse_args(argv)
    secreto = getpass.getpass("Contraseña SINTÉTICA del ensayo (no se muestra): ")
    if len(secreto) < 12:
        print(json.dumps({"error": "entrada_no_valida"}))
        return 2
    filas, faltan = [], False
    for ruta in a.archivo:
        existe = ruta.is_file()
        faltan |= not existe
        filas.append({"archivo": ruta.name, "existe": existe, "aparece": existe and aparece(ruta.read_bytes(), secreto)})
    del secreto
    total = sum(f["aparece"] for f in filas)
    print(json.dumps({"archivos": filas, "apariciones": total}, ensure_ascii=False))
    return 2 if faltan else (1 if total else 0)


if __name__ == "__main__":
    sys.exit(main())
