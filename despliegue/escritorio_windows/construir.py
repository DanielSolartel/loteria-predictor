"""Compila el instalador NSIS a partir del ZIP portátil verificado."""

import argparse
import hashlib
import json
import os
import runpy
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

FUENTES = Path(__file__).resolve().parent
REPO = FUENTES.parents[1]
PORTATIL_SHA256 = "b4fd73590a6b82ecbc8dcb2ea7ca626bd19597350a4b73576bc594bafe94535c"
ARRANQUE = (
    "python.exe", "python314.dll", "python314.zip", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt",
)


def huella(ruta: Path) -> str:
    with ruta.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def preparar(portatil: Path, raiz: Path) -> tuple[Path, Path, str]:
    if huella(portatil) != PORTATIL_SHA256:
        raise ValueError("El SHA-256 del ZIP portátil no coincide con el piloto validado.")
    carga = raiz / "carga"
    with ZipFile(portatil) as z:
        z.extractall(carga)
    verificar = runpy.run_path(str(carga / "arrancar.py"), run_name="verificador_piloto")["verificar"]
    manifiesto = verificar(carga)
    for nombre in ("piloto_windows.py", "perfil_piloto_windows.py"):
        relativo = f"backend/scripts/{nombre}"
        shutil.copyfile(REPO / relativo, carga / relativo)
        manifiesto["archivos"][relativo] = huella(carga / relativo)
    manifiesto["entrega"] = "instalador_usuario"
    ruta_manifiesto = carga / "manifiesto-kit.json"
    ruta_manifiesto.write_bytes((json.dumps(manifiesto, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    verificar(carga)

    gestor = raiz / "gestor"
    gestor.mkdir()
    for nombre in ARRANQUE:
        shutil.copyfile(carga / "runtime" / nombre, gestor / nombre)
    shutil.copyfile(carga / "backend/scripts/perfil_piloto_windows.py", gestor / "perfil_piloto_windows.py")
    (gestor / "python314._pth").write_bytes(b"python314.zip\r\n.\r\n")
    return carga, gestor, huella(ruta_manifiesto)


def compilar(makensis: Path, nsis_dir: Path, carga: Path, gestor: Path, sha: str, salida: Path, *,
             operativo: bool = False) -> None:
    orden = [makensis.resolve(), "-NOCONFIG", "-INPUTCHARSET", "UTF8", "-V2",
             f"-DLP11_CARGA={carga}", f"-DLP11_BOOTSTRAP={gestor}", f"-DLP11_SALIDA={salida}",
             f"-DLP11_MANIFIESTO_SHA256={sha}"]
    if operativo:
        orden.append("-DLP11_OPERATIVO")
    orden.append(FUENTES / "instalador.nsi")
    subprocess.run(orden, check=True, env={**os.environ, "NSISDIR": str(nsis_dir.resolve())})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portatil", required=True, type=Path)
    parser.add_argument("--makensis", required=True, type=Path)
    parser.add_argument("--nsis-dir", required=True, type=Path)
    parser.add_argument("--salida", required=True, type=Path)
    args = parser.parse_args()
    salida = args.salida.resolve()
    salida.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=salida.parent, prefix="lp11-compilar-") as temporal:
        raiz = Path(temporal)
        carga, gestor, sha = preparar(args.portatil.resolve(), raiz)
        ejecutable = raiz / salida.name
        compilar(args.makensis, args.nsis_dir, carga, gestor, sha, ejecutable)
        ejecutable.replace(salida)
    print(f"{salida.name} {salida.stat().st_size} bytes SHA256 {huella(salida)}")


if __name__ == "__main__":
    main()
