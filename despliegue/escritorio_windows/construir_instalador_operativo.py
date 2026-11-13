"""Empaqueta la versión de Lotería Predictor con Mis apuestas para Windows."""

import argparse
from base64 import b64encode
from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from construir import ARRANQUE, FUENTES, REPO, compilar, huella


VISOR_SHA256 = "3c1b79f6296c1e122ceac676b145d78b3ce9506a7f7fbbcd3b863d8041e91447"
GESTOR_SHA256 = {
    "python.exe": "d718435b892db4ad5b547d12fec61be7baa7faf7a58d857ea58053be24c7a000",
    "python314.dll": "d8a06cc6ca3348925ea29e343e1c5c5895fe0bb433ff913e1cee44caf358aa6a",
    "python314.zip": "4e97b321fe7f470c5a2cda0414f2b9caa896835edadf03eef251a0ebc3c24cc3",
    "vcruntime140.dll": "d1f4225df2cd877dbf130d5668a021dce3f94118455ff5ec952061c30afc9ce7",
    "vcruntime140_1.dll": "a7146c08f89fe5b04541ab507cdb59ff7b44534d4ba3c668a426c6450a03434e",
    "LICENSE.txt": "935cf13e19f8c31b497d20b05d73623431a226b230c3599bc30fa3348979bc68",
}
PERFIL = REPO / "backend/scripts/perfil_piloto_windows.py"


def preparar(visor: Path, bootstrap: Path, raiz: Path, *, visor_sha256: str = VISOR_SHA256) -> tuple[Path, Path, str]:
    contenido = visor.read_bytes()
    huella_visor = sha256(contenido).hexdigest()
    if huella_visor != visor_sha256.lower():
        raise ValueError("La huella del visor operativo no coincide con el SHA-256 esperado.")
    carga = raiz / "carga"
    carga.mkdir()
    lanzador = carga / "abrir.zip"
    with ZipFile(lanzador, "x") as archivos:
        for nombre, fuente in (("__main__.py", FUENTES / "abrir_operativo.py"), (PERFIL.name, PERFIL)):
            codigo = fuente.read_bytes()
            compile(codigo, nombre, "exec")
            archivos.writestr(ZipInfo(nombre), codigo, compress_type=ZIP_DEFLATED)
        archivos.writestr(ZipInfo("visor.zip"), contenido)
    comando = (FUENTES / "abrir_operativo.ps1").read_text(encoding="utf-8")
    comando = comando.replace("__PAQUETE_SHA256__", huella(lanzador))
    comando64 = b64encode(comando.encode("utf-16-le")).decode("ascii")
    lineas = (
        '@echo off',
        'setlocal DisableDelayedExpansion',
        'set "LP11_RAIZ=%~dp0"',
        '"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" '
        f'-NoLogo -NoProfile -EncodedCommand {comando64}',
        'set "LP11_CODIGO=%ERRORLEVEL%"',
        'echo(',
        'echo Codigo del visor %LP11_CODIGO%',
        'pause',
        'exit /b %LP11_CODIGO%',
        '',
    )
    (carga / "Abrir Loteria Predictor.cmd").write_bytes("\r\n".join(lineas).encode("ascii"))
    manifiesto = {"version": "fase11-operativo-windows/1", "entrega": "operativo_usuario", "version_instalacion": "2.0.0",
                  "visor_sha256": huella_visor, "archivos": {p.name: huella(p) for p in sorted(carga.iterdir())}}
    ruta_manifiesto = carga / "manifiesto-kit.json"
    ruta_manifiesto.write_bytes((json.dumps(manifiesto, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    gestor = raiz / "gestor"
    gestor.mkdir()
    for nombre in ARRANQUE:
        fuente = bootstrap / nombre
        if huella(fuente) != GESTOR_SHA256[nombre]:
            raise ValueError(f"El archivo {nombre} del gestor difiere del utilizado en el instalador del piloto.")
        shutil.copyfile(fuente, gestor / nombre)
    shutil.copyfile(PERFIL, gestor / PERFIL.name)
    (gestor / "python314._pth").write_bytes(b"python314.zip\r\n.\r\n")
    return carga, gestor, huella(ruta_manifiesto)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visor", required=True, type=Path)
    parser.add_argument("--visor-sha256", default=VISOR_SHA256,
                        help="SHA-256 esperado del visor. Por defecto usa el de la entrega original v2.")
    parser.add_argument("--bootstrap", required=True, type=Path)
    parser.add_argument("--makensis", required=True, type=Path)
    parser.add_argument("--nsis-dir", required=True, type=Path)
    parser.add_argument("--salida", required=True, type=Path)
    args = parser.parse_args()
    salida = args.salida.resolve()
    salida.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=salida.parent, prefix="lp11-compilar-") as temporal:
        carga, gestor, sha = preparar(args.visor, args.bootstrap, Path(temporal), visor_sha256=args.visor_sha256)
        ejecutable = Path(temporal) / salida.name
        compilar(args.makensis, args.nsis_dir, carga, gestor, sha, ejecutable, operativo=True)
        ejecutable.replace(salida)
    print(f"{salida.name} {salida.stat().st_size} bytes SHA256 {huella(salida)}")


if __name__ == "__main__":
    main()
