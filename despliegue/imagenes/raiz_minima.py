"""PR #109 (CI109-03): arma, dentro de la etapa `raiz-ejecucion` (misma base Python de Debian 13 que antes), la raiz
MINIMA de ejecucion de las imagenes API y pasarela.

- Copia SOLO los archivos de los paquetes Debian que el servicio carga de verdad (biblioteca de C, runtime de
  C++ que usan numpy/scipy, zlib, OpenSSL, zstd, libffi, bzip2, xz) mas datos imprescindibles (zona horaria,
  netbase y base-files con `os-release`). Son los mismos paquetes y versiones de la base fijada: no se mezclan
  distribuciones ni se actualiza nada.
- Por cada paquete incluido escribe su ficha real de dpkg (`dpkg-query -s`) y sus md5sums en
  `/var/lib/dpkg/status.d/`, de modo que el SBOM y los escaneres ven exactamente lo que hay. Ningun paquete
  incluido queda oculto; los no incluidos no tienen archivos en la imagen.
- Copia Python (`/usr/local`) SIN los modulos opcionales de la biblioteca estandar que el servicio no usa y que
  arrastran paquetes con avisos graves: sqlite3 (`_sqlite3`), curses/readline (ncurses, readline), dbm
  (`_dbm`, `_gdbm`), el acelerador C de uuid (`_uuid`, de util-linux) y tkinter.
- No copia `pip` (ni su programa en /usr/local/bin): no se usa en ejecucion y lleva copias propias de msgpack,
  urllib3 y setuptools. La instalacion estricta y `pip check` ya se hicieron en `base-dependencias`.
- Escribe usuarios (root y consulta 10001), la configuracion del cargador y su cache (`ldconfig -r`), y /tmp.
- Comprueba que cada ELF copiado resuelve sus bibliotecas DENTRO de la raiz; si falta alguna, falla.

Uso (como root en la etapa): python raiz_minima.py /raiz
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

PAQUETES = ("base-files", "netbase", "tzdata", "libc6", "libgcc-s1", "libstdc++6", "zlib1g", "libssl3t64",
            "libzstd1", "libffi8", "libbz2-1.0", "liblzma5")
MODULOS_RETIRADOS = ("_sqlite3", "_curses", "_curses_panel", "readline", "_dbm", "_gdbm", "_uuid", "_tkinter")


def ejecutar(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def copiar(origen: str, raiz: Path) -> None:
    destino = raiz / origen.lstrip("/")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if os.path.islink(origen):
        if not destino.exists() and not destino.is_symlink():
            os.symlink(os.readlink(origen), destino)
    elif os.path.isfile(origen):
        shutil.copy2(origen, destino)


def paquete(nombre: str, raiz: Path) -> None:
    estado = ejecutar("dpkg-query", "-W", "-f=${db:Status-Status}", nombre)
    if estado != "installed":
        raise SystemExit(f"{nombre}: no instalado en la base ({estado})")
    for ruta in ejecutar("dpkg", "-L", nombre).splitlines():
        if ruta and (os.path.isfile(ruta) or os.path.islink(ruta)):
            copiar(ruta, raiz)
    status_d = raiz / "var/lib/dpkg/status.d"
    status_d.mkdir(parents=True, exist_ok=True)
    (status_d / nombre).write_text(ejecutar("dpkg-query", "-s", nombre), encoding="utf-8")
    for md5 in glob.glob(f"/var/lib/dpkg/info/{nombre}.md5sums") + glob.glob(f"/var/lib/dpkg/info/{nombre}:*.md5sums"):
        shutil.copy2(md5, status_d / f"{nombre}.md5sums")


def python(raiz: Path) -> None:
    def ignorar(carpeta, nombres):
        fuera = [n for n in nombres if n.split(".")[0] in MODULOS_RETIRADOS and n.endswith(".so")]
        if carpeta.endswith("/site-packages") or carpeta.endswith("/bin"):
            fuera += [n for n in nombres if n == "pip" or n.startswith(("pip-", "pip3"))]
        return fuera
    shutil.copytree("/usr/local", raiz / "usr/local", symlinks=True, ignore=ignorar, dirs_exist_ok=True)


def sistema(raiz: Path) -> None:
    (raiz / "etc").mkdir(exist_ok=True)
    (raiz / "etc/passwd").write_text("root:x:0:0:root:/root:/usr/sbin/nologin\n"
                                     "consulta:x:10001:10001::/nonexistent:/usr/sbin/nologin\n", encoding="ascii")
    (raiz / "etc/group").write_text("root:x:0:\nconsulta:x:10001:\n", encoding="ascii")
    (raiz / "etc/ld.so.conf").write_text("/usr/local/lib\ninclude /etc/ld.so.conf.d/*.conf\n", encoding="ascii")
    ejecutar("ldconfig", "-r", str(raiz))
    tmp = raiz / "tmp"
    tmp.mkdir(exist_ok=True)
    tmp.chmod(0o1777)


def comprobar(raiz: Path) -> None:
    """Cada ELF de Python en la raiz resuelve sus dependencias con el cargador y la cache de la PROPIA raiz
    (`chroot raiz ld-linux --list`), igual que en la imagen final. Cualquier `not found` hace fallar."""
    cargador = "/lib64/ld-linux-x86-64.so.2"
    if not (raiz / cargador.lstrip("/")).exists():
        raise SystemExit("la raiz minima no contiene el cargador dinamico")
    faltan, revisados = [], 0
    for d, _, archivos in os.walk(raiz / "usr/local"):
        for f in archivos:
            p = Path(d) / f
            if p.is_symlink() or not p.is_file():
                continue
            cabecera = p.read_bytes()[:18]
            # Solo ejecutables (ET_EXEC=2) y objetos compartidos (ET_DYN=3): los objetos reubicables (python.o)
            # nunca se cargan.
            if cabecera[:4] != b"\x7fELF" or int.from_bytes(cabecera[16:18], "little") not in (2, 3):
                continue
            revisados += 1
            r = subprocess.run(["chroot", str(raiz), cargador, "--list", "/" + str(p.relative_to(raiz))],
                               capture_output=True, text=True)
            faltan += [f"{p.relative_to(raiz)}: {l.strip()}" for l in (r.stdout + r.stderr).splitlines()
                       if "not found" in l]
            if r.returncode != 0 and not faltan:
                faltan.append(f"{p.relative_to(raiz)}: el cargador devolvio {r.returncode}: {r.stderr.strip()[:200]}")
    if revisados == 0:
        raise SystemExit("ningun ELF revisado: la comprobacion no es valida")
    if faltan:
        raise SystemExit("bibliotecas ausentes en la raiz minima:\n" + "\n".join(faltan))
    print(f"{revisados} ELF de Python resuelven sus bibliotecas dentro de la raiz")


def main() -> int:
    raiz = Path(sys.argv[1])
    raiz.mkdir(parents=True, exist_ok=False)
    for nombre in PAQUETES:
        paquete(nombre, raiz)
    python(raiz)
    sistema(raiz)
    comprobar(raiz)
    print(f"raiz minima: {len(PAQUETES)} paquetes; modulos retirados: {', '.join(MODULOS_RETIRADOS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
