"""PR #109 (CI109-MIN-01): el comprobador de ejecucion de las imagenes evalua el CODIGO DE SALIDA y TODA la salida
del cargador para CADA extension; la unica tolerancia (lightgbm/lib_lightgbm.so sin libgomp.so.1) es exacta y no
oculta otros errores ni se arrastra entre extensiones.

Se EJECUTA el comprobador real (`runpy`) aislando solo el descubrimiento (distribuciones, glob) y las
importaciones, y controlando la respuesta del cargador por extension. Los casos de ELF invalido y de extension
valida usan el cargador REAL del sistema."""
from __future__ import annotations

import contextlib
import importlib
import importlib.metadata as metadata
import io
import json
import runpy
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="comprobador de imagenes Linux")

RAIZ = Path(__file__).resolve().parents[3]
COMPROBADOR = RAIZ / "despliegue" / "imagenes" / "comprobar_ejecucion_imagen.py"
CARGADOR = Path("/lib64/ld-linux-x86-64.so.2")
RETIRADOS = {"sqlite3", "_sqlite3", "curses", "_curses", "readline", "dbm.gnu", "dbm.ndbm", "_uuid", "tkinter"}
REAL_RUN = subprocess.run
REAL_IMPORT = importlib.import_module
GOMP_LIST = "\tlibgomp.so.1 => not found\n"
GOMP_ERROR = ("{so}: error while loading shared libraries: libgomp.so.1: cannot open shared object file: "
              "No such file or directory\n")
REAL = object()  # marca: esta extension la evalua el cargador real


class _Distribucion:
    def __init__(self, nombre):
        self.nombre, self.files = nombre, []

    def read_text(self, archivo):
        return self.nombre if archivo == "top_level.txt" else None


def rc(codigo, salida="", errores=""):
    return subprocess.CompletedProcess([], codigo, stdout=salida, stderr=errores)


def ejecutar(extensiones: dict, importaciones: dict | None = None, distribuciones=("json",)):
    """extensiones: {ruta: CompletedProcess | REAL | excepcion}; importaciones: {modulo: excepcion}."""
    importaciones = importaciones or {}
    llamadas = []

    def cargador(args, *a, **k):
        llamadas.append(args)
        respuesta = extensiones[args[2]]
        if respuesta is REAL:
            return REAL_RUN(args, *a, **k)
        if isinstance(respuesta, BaseException):
            raise respuesta
        return respuesta

    def importar(nombre, *a, **k):
        if nombre in importaciones:
            raise importaciones[nombre]
        if nombre in RETIRADOS:
            raise ImportError("retirado en el escenario")
        if nombre.startswith("app.") or nombre in distribuciones:
            return types.ModuleType(nombre)
        return REAL_IMPORT(nombre, *a, **k)

    lotes = iter([list(extensiones), []])
    salida = io.StringIO()
    with patch.object(metadata, "distributions", return_value=[_Distribucion(d) for d in distribuciones]), \
            patch.object(importlib, "import_module", side_effect=importar), \
            patch("glob.glob", side_effect=lambda *a, **k: next(lotes, [])), \
            patch("subprocess.run", side_effect=cargador), \
            patch.object(sys, "argv", [str(COMPROBADOR), "api"]), contextlib.redirect_stdout(salida):
        try:
            runpy.run_path(str(COMPROBADOR), run_name="__main__")
            codigo = 0
        except SystemExit as e:
            codigo = e.code
    informe = json.loads(salida.getvalue())
    assert len(llamadas) == len(extensiones)  # cada extension se evalua una vez
    return codigo, informe


LGBM = "/opt/venv/lib/python3.14/site-packages/lightgbm/lib/lib_lightgbm.so"
OTRA = "/opt/venv/lib/python3.14/site-packages/numpy/_core/_multiarray_umath.cpython-314-x86_64-linux-gnu.so"
CORRECTA = rc(0, "\tlinux-vdso.so.1 (0x00007ffd)\n\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f00)\n"
                 "\t/lib64/ld-linux-x86-64.so.2 (0x00007f11)\n")


# --- los siete casos de la sonda de Codex, mas formatos reales ---------------------------------------------------
@pytest.mark.parametrize("respuesta, ruta, esperado", [
    (rc(0, "libc.so.6 => /lib/libc.so.6\n"), OTRA, 0),                                   # control correcto
    (rc(2), OTRA, 1),                                                                     # codigo 2 sin salida
    (rc(127, "libajena.so => not found\n"), OTRA, 1),                                     # biblioteca ajena
    (rc(127, GOMP_LIST), LGBM, 0),                                                        # tolerancia exacta
    (rc(127, "libajena.so => not found\n"), LGBM, 1),                                     # otra lib en lightgbm
    (rc(127, GOMP_LIST, "error: invalid ELF header\n"), LGBM, 1),                         # tolerancia + error
    (rc(1, "", GOMP_ERROR.format(so=LGBM)), LGBM, 0),                                     # formato real de error
    (rc(1, "", GOMP_ERROR.format(so=OTRA).replace("libgomp.so.1", "libajena.so.2")), OTRA, 1),
    (rc(1, "", GOMP_ERROR.format(so=OTRA)), OTRA, 1),                                     # libgomp en OTRO archivo
    (rc(0, GOMP_LIST), OTRA, 1),                                                          # not found con codigo 0
    (rc(1, CORRECTA.stdout), OTRA, 1),                                                    # codigo 1 sin explicar
    (rc(0, CORRECTA.stdout + "\tstatically linked\n"), OTRA, 1),                          # linea no reconocida
    (rc(0, CORRECTA.stdout, "aviso inesperado del cargador\n"), OTRA, 1),                 # stderr con codigo 0
    (rc(127, GOMP_LIST + "\tlibajena.so => not found\n"), LGBM, 1),                       # libgomp + otra
    (rc(127, GOMP_LIST), LGBM.replace("lib_lightgbm.so", "otro.so"), 1),                  # otro archivo de lightgbm
    (CORRECTA, OTRA, 0),                                                                  # salida real completa
])
def test_cada_extension_se_juzga_por_codigo_y_salida(respuesta, ruta, esperado):
    codigo, informe = ejecutar({ruta: respuesta})
    assert codigo == esperado, informe
    if esperado == 0:
        assert informe["resueltas"] + len(informe["toleradas"]) == informe["extensiones"] == 1
    else:
        assert informe["fallos"] and all(f.startswith(ruta) for f in informe["fallos"])


def test_tolerancia_registrada_explicitamente():
    codigo, informe = ejecutar({LGBM: rc(127, GOMP_LIST), OTRA: CORRECTA})
    assert codigo == 0 and informe["resueltas"] == 1 and informe["fallos"] == []
    assert informe["toleradas"] == [{"extension": LGBM, "falta": "libgomp.so.1",
                                     "detalle": "libgomp.so.1 => not found (codigo 127)"}]


def test_la_tolerancia_no_se_arrastra_a_la_extension_siguiente():
    otra_lgbm = "/opt/venv/lib/python3.14/site-packages/scipy/_lib/_ccallback_c.so"
    codigo, informe = ejecutar({LGBM: rc(127, GOMP_LIST), otra_lgbm: rc(127, GOMP_LIST)})
    assert codigo == 1 and len(informe["toleradas"]) == 1
    assert informe["fallos"] == [f"{otra_lgbm}: libgomp.so.1 => not found", f"{otra_lgbm}: codigo de salida 127"]


def test_cargador_que_no_se_puede_ejecutar_es_fallo():
    codigo, informe = ejecutar({OTRA: FileNotFoundError(2, "No such file or directory")})
    assert codigo == 1 and "no se pudo ejecutar el cargador" in informe["fallos"][0]
    codigo, informe = ejecutar({OTRA: subprocess.TimeoutExpired(["ld"], 60)})
    assert codigo == 1 and "TimeoutExpired" in informe["fallos"][0]


@pytest.mark.parametrize("modulo, error, esperado", [
    ("lightgbm", OSError("libgomp.so.1: cannot open shared object file: No such file or directory"), 0),
    ("lightgbm", OSError("libajena.so: cannot open shared object file: No such file or directory"), 1),
    ("lightgbm", ImportError("libgomp.so.1: cannot open shared object file"), 1),  # otro tipo de error
    ("numpy", OSError("libgomp.so.1: cannot open shared object file: No such file or directory"), 1),
])
def test_tolerancia_de_importacion_exacta(modulo, error, esperado):
    codigo, informe = ejecutar({OTRA: CORRECTA}, {modulo: error}, distribuciones=("json", modulo))
    assert codigo == esperado, informe
    assert len(informe["toleradas"]) == (1 if esperado == 0 else 0)


# --- cargador REAL -------------------------------------------------------------------------------------------
requiere_cargador = pytest.mark.skipif(not CARGADOR.is_file(), reason="sin cargador x86_64 de glibc")


@requiere_cargador
def test_elf_truncado_con_el_cargador_real(tmp_path):
    malo = tmp_path / "malformado.so"
    malo.write_bytes(b"\x7fELF\x02\x01\x01" + b"\0" * 9 + b"\x03\0")
    codigo, informe = ejecutar({str(malo): REAL})
    assert codigo == 1 and informe["resueltas"] == 0
    assert any("diagnostico del cargador" in f for f in informe["fallos"]), informe


@requiere_cargador
def test_elf_truncado_en_ruta_de_lightgbm_no_queda_tolerado(tmp_path):
    malo = tmp_path / "lightgbm" / "lib" / "lib_lightgbm.so"
    malo.parent.mkdir(parents=True)
    malo.write_bytes(b"\x7fELF\x02\x01\x01" + b"\0" * 9 + b"\x03\0")
    codigo, informe = ejecutar({str(malo): REAL})
    assert codigo == 1 and informe["toleradas"] == []


@requiere_cargador
def test_extension_valida_con_el_cargador_real():
    import _json  # extension compilada de la biblioteca estandar si existe; si no, libpython/libc
    ruta = getattr(_json, "__file__", None) or next(
        p for p in ("/lib/x86_64-linux-gnu/libz.so.1", "/usr/lib/x86_64-linux-gnu/libz.so.1") if Path(p).exists())
    codigo, informe = ejecutar({str(ruta): REAL})
    assert codigo == 0 and informe["resueltas"] == 1 and informe["fallos"] == [], informe


# --- objetos compartidos sin dependencias ('statically linked'): resueltos SOLO si el ELF lo confirma ------------
def elf(ruta: Path, tipo=3, maquina=62, necesarias=0, dt_null=True) -> str:
    """ELF64 LE minimo con una cabecera de programa PT_DYNAMIC y `necesarias` entradas DT_NEEDED."""
    import struct
    dinamica = b"".join(struct.pack("<qQ", 1, 0) for _ in range(necesarias)) + (struct.pack("<qQ", 0, 0)
                                                                                 if dt_null else b"")
    cabecera = (b"\x7fELF\x02\x01\x01" + b"\0" * 9 + struct.pack("<HHIQQQIHHHHHH", tipo, maquina, 1, 0, 64, 0,
                                                                  0, 64, 56, 1, 0, 0, 0))
    programa = struct.pack("<IIQQQQQQ", 2, 6, 120, 0, 0, len(dinamica), len(dinamica), 8)
    ruta.write_bytes(cabecera + programa + dinamica)
    return str(ruta)


ESTATICA = rc(0, "\tstatically linked\n")


@pytest.mark.parametrize("parametros, respuesta, esperado", [
    ({}, ESTATICA, 0),                                        # ET_DYN x86-64 sin DT_NEEDED: sin dependencias
    ({"necesarias": 1}, ESTATICA, 1),                         # dice 'statically linked' pero el ELF tiene NEEDED
    ({"tipo": 2}, ESTATICA, 1),                               # ET_EXEC
    ({"maquina": 183}, ESTATICA, 1),                          # otra arquitectura
    ({"dt_null": False}, ESTATICA, 1),                        # seccion dinamica inconsistente
    ({}, rc(1, "\tstatically linked\n"), 1),                  # codigo distinto de 0
    ({}, rc(0, "\tstatically linked\n", "aviso\n"), 1),       # con diagnostico
    ({}, rc(0, ""), 1),                                       # codigo 0 sin ninguna salida
])
def test_sin_dependencias_solo_si_el_elf_lo_confirma(tmp_path, parametros, respuesta, esperado):
    so = elf(tmp_path / "x.cpython-314-x86_64-linux-gnu.so", **parametros)
    codigo, informe = ejecutar({so: respuesta})
    assert codigo == esperado, informe
    assert informe["sin_dependencias"] == ([so] if esperado == 0 else [])
    assert informe["toleradas"] == []


def test_statically_linked_de_un_archivo_inexistente_es_fallo():
    codigo, informe = ejecutar({OTRA: ESTATICA})
    assert codigo == 1 and informe["sin_dependencias"] == [] and "sin confirmar" in informe["fallos"][0]


@requiere_cargador
def test_extension_sin_dependencias_con_el_cargador_real():
    import sysconfig
    sitio = Path(sysconfig.get_path("platlib"))
    posibles = sorted((Path(sysconfig.get_path("platstdlib")) / "lib-dynload").glob("_heapq*.so")) + sorted(
        p for patron in ("numpy/_core/_operand_flag_tests*.so", "scipy/_lib/_fpumode*.so") for p in sitio.glob(patron))
    candidatas = [p for p in posibles
                  if REAL_RUN([str(CARGADOR), "--list", str(p)], capture_output=True, text=True).stdout.strip()
                  == "statically linked"]
    if not candidatas:
        pytest.skip("este Python no trae extensiones sin dependencias")
    codigo, informe = ejecutar({str(candidatas[0]): REAL})
    assert codigo == 0 and informe["sin_dependencias"] == [str(candidatas[0])], informe


# Auditoria Codex: un aviso conocido no oculta una senal o un codigo de salida no explicado.
@pytest.mark.parametrize("codigo_cargador", [-15, -11, 0, 2, 137])
def test_tolerancia_no_oculta_senal_ni_codigo_no_explicado(codigo_cargador):
    codigo, informe = ejecutar({LGBM: rc(codigo_cargador, GOMP_LIST)})
    assert codigo == 1, informe
    assert informe["toleradas"] == []
    assert informe["fallos"] and all(f.startswith(LGBM) for f in informe["fallos"])
