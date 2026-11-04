"""PR #109 (CI109-03): comprueba DENTRO de cada imagen final (sin red, solo lectura, usuario de la imagen) que la
raiz minima basta para el servicio. Solo biblioteca estandar; se ejecuta igual en CI y en local:

    docker run --rm -i --network none --read-only --tmpfs /tmp --entrypoint python <imagen> -B - <objetivo> \\
        < despliegue/imagenes/comprobar_ejecucion_imagen.py

- Importa los modulos de nivel superior de TODAS las distribuciones instaladas (top_level.txt o RECORD) y los
  modulos del servicio que no se autoconfiguran (las aplicaciones terminan a proposito sin su configuracion
  privada), mas los de la biblioteca estandar que usa (ssl, hashlib, zlib, ctypes, ...).
- Resuelve las dependencias de cada extension compilada con el CARGADOR de la propia imagen
  (`ld-linux --list`; la imagen no lleva ldd). Cada extension se evalua POR SEPARADO con su codigo de salida y
  TODA su salida (PR #109, CI109-MIN-01): una extension solo se da por resuelta si el cargador devuelve 0 y no
  emite ningun diagnostico. Un codigo distinto de 0 sin explicacion, un ELF invalido, cualquier linea no
  reconocida, la ausencia de salida o una biblioteca ausente son fallos, aunque no aparezca `not found`.
- `statically linked` (lo que imprime el cargador para un objeto compartido SIN dependencias) solo cuenta como
  resuelta si es la unica linea, el codigo es 0, no hay diagnosticos y el propio ELF lo confirma: ELF64 x86-64,
  tipo ET_DYN, con seccion dinamica y CERO entradas DT_NEEDED. Se lista aparte en `sin_dependencias`; no es una
  tolerancia.
- Exige que los modulos RETIRADOS de la imagen minima no esten disponibles (sqlite3, curses, readline, dbm,
  _uuid, tkinter): si reaparecen, reaparecen sus paquetes.
- Unica tolerancia, preexistente y EXACTA: el archivo `lightgbm/lib/lib_lightgbm.so` (y el import de `lightgbm`)
  con `libgomp.so.1` como UNICA biblioteca ausente y ningun otro diagnostico; ninguna base slim trae libgomp y
  ningun modulo servido importa lightgbm. Se registra explicitamente en `toleradas`. No cubre otro archivo, otra
  biblioteca, un ELF invalido ni un error simultaneo, y no se arrastra de una extension a otra.
"""
import glob
import importlib
import importlib.metadata as md
import json
import os
import platform
import re
import struct
import subprocess
import sys
import sysconfig
from pathlib import PurePosixPath

TOLERADA_MODULO, TOLERADA_ARCHIVO, TOLERADA_BIBLIOTECA = "lightgbm", "lib_lightgbm.so", "libgomp.so.1"
RETIRADOS = ("sqlite3", "_sqlite3", "curses", "_curses", "readline", "dbm.gnu", "dbm.ndbm", "_uuid", "tkinter")
CARGADOR = "/lib64/ld-linux-x86-64.so.2"
# Formatos del cargador de glibc: resolucion correcta (`lib => /ruta (0x...)`, `/ruta (0x...)`, `linux-vdso...`),
# dependencia ausente en `--list` (`lib => not found`) y error al cargar (`...: error while loading shared
# libraries: lib: cannot open shared object file: ...`). Todo lo demas es un diagnostico no explicado.
NO_ENCONTRADA = re.compile(r"^\s*(\S+) => not found\s*$")
RESUELTA = re.compile(r"^\s*(\S+ => \S+( \(0x[0-9a-f]+\))?|\S+ \(0x[0-9a-f]+\))\s*$")
NO_ABRE = re.compile(r"error while loading shared libraries: (\S+): cannot open shared object file")
objetivo = sys.argv[1] if len(sys.argv) > 1 else ""
r = {"objetivo": objetivo, "python": sys.version.split()[0], "maquina": platform.machine(),
     "soabi": sysconfig.get_config_var("SOABI"), "uid": os.getuid(), "distribuciones": 0, "modulos": 0,
     "extensiones": 0, "resueltas": 0, "sin_dependencias": [], "fallos": [], "preexistentes": [], "toleradas": [],
     "retirados_presentes": []}
SIN_DEPENDENCIAS = re.compile(r"^\s*statically linked\s*$")


def es_archivo_tolerado(so: str) -> bool:
    p = PurePosixPath(so)
    return p.name == TOLERADA_ARCHIVO and TOLERADA_MODULO in p.parts[-3:-1]


def dependencias_elf(so: str) -> int | None:
    """Numero de entradas DT_NEEDED de un objeto compartido ELF64 x86-64 (ET_DYN) con seccion dinamica; None si el
    archivo no es exactamente eso o no se puede leer completo."""
    try:
        with open(so, "rb") as f:
            b = f.read()
        if b[:4] != b"\x7fELF" or b[4] != 2 or b[5] != 1:
            return None
        e_type, e_machine = struct.unpack_from("<HH", b, 16)
        (phoff,) = struct.unpack_from("<Q", b, 32)
        phentsize, phnum = struct.unpack_from("<HH", b, 54)
        if e_type != 3 or e_machine != 62 or phentsize < 56:
            return None
        for i in range(phnum):
            p_type, _flags, off, _va, _pa, filesz = struct.unpack_from("<IIQQQQ", b, phoff + i * phentsize)
            if p_type == 2:  # PT_DYNAMIC
                necesarias = 0
                for j in range(0, filesz - 15, 16):
                    (etiqueta,) = struct.unpack_from("<q", b, off + j)
                    if etiqueta == 0:  # DT_NULL
                        return necesarias
                    necesarias += etiqueta == 1  # DT_NEEDED
                return None  # seccion dinamica sin DT_NULL: ELF inconsistente
        return None
    except (OSError, struct.error):
        return None


def evaluar_extension(so: str, codigo: int, salida: str, errores: str) -> tuple[str, list[str]]:
    """Clasifica UNA extension: ('resuelta' | 'sin_dependencias' | 'tolerada' | 'fallo', diagnosticos). Sin estado
    compartido entre extensiones."""
    lineas = [l for l in (salida or "").splitlines() if l.strip()]
    if len(lineas) == 1 and SIN_DEPENDENCIAS.match(lineas[0]) and not (errores or "").strip():
        if codigo == 0 and dependencias_elf(so) == 0:
            return "sin_dependencias", []
        return "fallo", [f"'statically linked' sin confirmar (codigo {codigo}, DT_NEEDED {dependencias_elf(so)})"]
    ausentes, no_explicados = [], []
    for linea in (salida or "").splitlines():
        if not linea.strip():
            continue
        m = NO_ENCONTRADA.match(linea)
        if m:
            ausentes.append(m.group(1))
        elif not RESUELTA.match(linea):
            no_explicados.append(f"salida no reconocida: {linea.strip()[:200]}")
    for linea in (errores or "").splitlines():
        if not linea.strip():
            continue
        m = NO_ABRE.search(linea)
        if m:
            ausentes.append(m.group(1))
        else:
            no_explicados.append(f"diagnostico del cargador: {linea.strip()[:200]}")
    if not ausentes and not no_explicados:
        if codigo == 0 and lineas:
            return "resuelta", []
        if codigo == 0:
            return "fallo", ["el cargador devolvio 0 sin ninguna salida"]
        return "fallo", [f"el cargador devolvio {codigo} sin diagnostico"]
    # La biblioteca ausente no explica una senal, un codigo de error distinto ni un exito contradictorio.
    # 127 es el error de carga de glibc; 1 se admite para el formato de error ya contrastado por las pruebas.
    if codigo in (1, 127) and not no_explicados and set(ausentes) == {TOLERADA_BIBLIOTECA} and es_archivo_tolerado(so):
        return "tolerada", [f"{TOLERADA_BIBLIOTECA} => not found (codigo {codigo})"]
    return "fallo", [f"{b} => not found" for b in dict.fromkeys(ausentes)] + no_explicados + (
        [f"codigo de salida {codigo}"] if codigo != 0 else [])


def nombres(d):
    tl = d.read_text("top_level.txt")
    if tl:
        return {n.strip() for n in tl.split() if n.strip()}
    salida = set()
    for f in d.files or []:
        p = f.parts
        if not p or p[0].endswith((".dist-info", ".data")) or p[0] in ("..", "bin"):
            continue
        if len(p) > 1 and p[0].isidentifier():
            salida.add(p[0])
        elif p[0].endswith(".py"):
            salida.add(p[0][:-3])
    return salida


modulos = set()
for d in md.distributions():
    r["distribuciones"] += 1
    modulos |= {n for n in nombres(d) if n.isidentifier() and not n.startswith("_") and n not in ("tests", "test")}
servicio = (["app.api.publica.configuracion", "app.api.publica.perfil_privado", "app.api.publica.rutas",
             "app.api.publica.recursos", "app.api.publica.guardados"] if objetivo == "api" else
            ["app.pasarela.configuracion", "app.pasarela.privada", "app.pasarela.rutas", "app.pasarela.cliente"])
estandar = ["ssl", "hashlib", "zlib", "bz2", "lzma", "ctypes", "decimal", "zoneinfo", "uuid", "json", "asyncio"]
for n in sorted(modulos) + servicio + estandar:
    r["modulos"] += 1
    try:
        importlib.import_module(n)
    except BaseException as e:
        texto = f"{n}: {type(e).__name__}: {str(e)[:200]}"
        if (n == TOLERADA_MODULO and isinstance(e, OSError)
                and f"{TOLERADA_BIBLIOTECA}: cannot open shared object file" in str(e)):
            r["preexistentes"].append(texto)
            r["toleradas"].append({"modulo": n, "falta": TOLERADA_BIBLIOTECA, "detalle": texto})
        else:
            r["fallos"].append(texto)
try:
    import zoneinfo
    zoneinfo.ZoneInfo("America/Bogota")
except Exception as e:
    r["fallos"].append(f"zona horaria: {type(e).__name__}: {e}")
for n in RETIRADOS:
    try:
        importlib.import_module(n)
        r["retirados_presentes"].append(n)
    except ImportError:
        pass
patrones = [os.path.join(sys.prefix, "lib", "**", "*.so*"),
            os.path.join(sys.base_prefix, "lib", "python3*", "lib-dynload", "*.so")]
for so in sorted({p for pat in patrones for p in glob.glob(pat, recursive=True)}):
    r["extensiones"] += 1
    try:
        proceso = subprocess.run([CARGADOR, "--list", so], capture_output=True, text=True, timeout=60)
        estado, diagnosticos = evaluar_extension(so, proceso.returncode, proceso.stdout, proceso.stderr)
    except (OSError, subprocess.SubprocessError) as e:
        estado, diagnosticos = "fallo", [f"no se pudo ejecutar el cargador: {type(e).__name__}: {e}"]
    if estado == "resuelta":
        r["resueltas"] += 1
    elif estado == "sin_dependencias":
        r["resueltas"] += 1
        r["sin_dependencias"].append(so)
    elif estado == "tolerada":
        r["preexistentes"] += [f"{so}: {d}" for d in diagnosticos]
        r["toleradas"].append({"extension": so, "falta": TOLERADA_BIBLIOTECA, "detalle": diagnosticos[0]})
    else:
        r["fallos"] += [f"{so}: {d}" for d in diagnosticos]
print(json.dumps(r, indent=1))
sys.exit(1 if r["fallos"] or r["retirados_presentes"] or r["distribuciones"] == 0 or r["extensiones"] == 0
         or r["resueltas"] + len([t for t in r["toleradas"] if "extension" in t]) != r["extensiones"] else 0)
