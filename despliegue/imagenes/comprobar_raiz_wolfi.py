"""Verifica el cargador ELF, libpython y las extensiones nativas de la biblioteca estándar."""
import os
from pathlib import Path
import subprocess
import sys
import sysconfig


def main():
    cargador = "/lib64/ld-linux-x86-64.so.2"
    carpeta = Path(sysconfig.get_config_var("DESTSHARED"))
    extensiones = sorted(carpeta.glob("*.so"))
    if not extensiones:
        raise SystemExit("No se encontraron extensiones nativas de Python.")
    biblioteca = Path(sysconfig.get_config_var("LIBDIR")) / sysconfig.get_config_var("INSTSONAME")
    objetos = [Path(sys.executable).resolve(), biblioteca, *extensiones]
    for objeto in objetos:
        proceso = subprocess.run([cargador, "--list", os.fspath(objeto)], capture_output=True, text=True)
        if proceso.returncode or proceso.stderr or "not found" in proceso.stdout or not proceso.stdout.strip():
            raise SystemExit(f"No se resolvieron las bibliotecas de {objeto}: {proceso.stderr}{proceso.stdout}")
    print(f"{len(objetos)} ELF de Python comprobados en la raíz de ejecución.")


if __name__ == "__main__":
    main()
