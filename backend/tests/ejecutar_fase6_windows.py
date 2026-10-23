"""Supervisor optativo Fase 6: dirigida, focal, regresiones y completa separadas.

El CLI solo acredita ejecución nativa Windows. Las funciones portables se
ensayan en Linux sin instalar tareas ni consultar datos/fuentes reales.
La batería elegida corre en un espejo público verificado y almacenes propios.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import sys
import tempfile
import time

from tests.ejecutar_ml_windows import (
    _conservar_mediciones, _contar_junit, _ejecutar, _guardar,
)

BASE = "2ac4d110b7d721e544f5588e9754230eef28184d"
VERSION = "fase6-3.3"
PREFIJO_TEMPORAL = "f6 "
ALMACENES_SINTETICOS = (("PRONOSTICOS_EXPERIMENTALES", "pronosticos"), ("OPERACION", "operacion"),
    ("LABORATORIO_MODELOS", "laboratorio"), ("CARTERAS_MODELOS", "carteras"),
    ("RESULTADOS_MODELOS", "resultados"), ("PREDICCIONES_MODELOS", "predicciones"),
    ("AUTOMATIZACION", "automatizacion"))
FOCALES = tuple("tests/unit/test_fase6_" + n + ".py" for n in (
    "calendario", "persistencia", "ciclo", "integracion", "web", "tarea_windows", "supervisor", "cli", "retry_http", "revisiones", "decisiones", "xml_windows", "ensayo_limpieza_windows", "exportacion_windows",
))
DIRIGIDAS = tuple("tests/unit/test_fase6_" + n + ".py" for n in (
    "tarea_windows", "xml_windows", "ensayo_limpieza_windows", "exportacion_windows", "supervisor",
))
REGRESIONES = tuple("tests/unit/" + n for n in (
    "test_fase4_publicacion_registro.py", "test_producto3_operacion.py",
    "test_producto4_aislamiento.py", "test_ml_registro.py", "test_ml_cinco_flujo.py",
    "test_ml_recursos_publicacion.py",
))


def rutas_temporales(temporal):
    """Acepta PureWindowsPath para el ensayo portable del presupuesto Win32."""
    return {"codigo": temporal / "c", "pytest": temporal,
            "mediciones": temporal / "e", "sinteticos": temporal / "s"}


def _ruta_publica(nombre):
    if not isinstance(nombre, str) or not nombre or "\\" in nombre or ":" in nombre:
        raise ValueError("Ruta pública no válida")
    if any(ord(c) < 32 for c in nombre):
        raise ValueError("Ruta pública con caracteres de control")
    ruta = PurePosixPath(nombre)
    if ruta.is_absolute() or ruta.as_posix() != nombre or any(p in ("", ".", "..") for p in ruta.parts):
        raise ValueError("Ruta pública no canónica")
    if any(p.casefold() in (".git", ".env", "__pycache__") for p in ruta.parts):
        raise ValueError("Ruta privada o generada en inventario")
    almacenes = {"backend/storage/" + n + "/.gitkeep" for n in (
        "carteras", "html", "laboratorio", "logs", "predicciones", "pronosticos", "resultados",
        "automatizacion", "operacion",
    )}
    partes = tuple(p.casefold() for p in ruta.parts)
    if (partes[0] == "storage" or partes[:2] == ("backend", "storage")) and nombre not in almacenes:
        raise ValueError("No se admiten datos de almacenes en el espejo")
    return Path(*ruta.parts)


def _contenido_canonico(contenido, tipo):
    if tipo == "texto":
        contenido.decode("utf-8")
        if b"\0" in contenido:
            raise ValueError("Un archivo de texto no puede contener NUL")
        return contenido.replace(b"\r\n", b"\n")
    if tipo != "binario":
        raise ValueError("Tipo de contenido no reconocido")
    return contenido


def _redireccion(ruta):
    if ruta.is_symlink() or (hasattr(ruta, "is_junction") and ruta.is_junction()):
        return True
    atributos = getattr(ruta.stat(), "st_file_attributes", 0)
    return bool(atributos & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _preparar_espejo(worktree, manifiesto, destino):
    """Valida todo antes de copiar y conserva los bytes físicos originales."""
    filas = manifiesto.get("inventario_publico")
    if not isinstance(filas, list) or not filas:
        raise ValueError("Falta el inventario público final")
    vistos = set()
    contenidos = []
    worktree = worktree.resolve()
    for fila in filas:
        relativa = _ruta_publica(fila["ruta"])
        clave = relativa.as_posix().casefold()
        if clave in vistos:
            raise ValueError("Ruta pública repetida sin distinguir mayúsculas")
        vistos.add(clave)
        origen = worktree / relativa
        for padre in (origen, *origen.parents):
            if padre == worktree.parent:
                break
            if _redireccion(padre):
                raise ValueError("El espejo no admite enlaces o redirecciones")
        b = origen.read_bytes()
        canonico = _contenido_canonico(b, fila["tipo"])
        esperado = fila["despues"]
        if not isinstance(esperado, dict) or set(("bytes", "sha256")) - esperado.keys():
            raise ValueError("La huella final debe declarar tamaño y SHA-256")
        if len(canonico) != esperado["bytes"] or hashlib.sha256(canonico).hexdigest() != esperado["sha256"]:
            raise ValueError("El código no coincide con el manifiesto: " + relativa.as_posix())
        if relativa.name != ".env.example":
            contenidos.append((relativa, b))
    for relativa, b in contenidos:
        salida = destino / relativa
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_bytes(b)
    return len(vistos)


def _comandos(bateria, junit, evidencia):
    etapas = {"dirigida": DIRIGIDAS, "focal": FOCALES, "regresiones": REGRESIONES, "completa": ("tests",)}
    pruebas = list(etapas[bateria])
    comandos = [("pytest-" + bateria, [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
                  "-rsw", "--junitxml=" + str(junit), *pruebas])]
    if bateria == "completa":
        comandos += [
            ("openssl-exigir", [sys.executable, "scripts/ci_contrastes_openssl.py", str(junit), "--modo", "exigir"]),
            ("demostracion-fase6", [sys.executable, "-m", "tests.demostracion_fase6",
                                    "--salida", str(evidencia / "demostracion-fase6.json")]),
        ]
    comandos.append(("pip-check", [sys.executable, "-m", "pip", "check"]))
    return comandos


def _entorno(rutas):
    env = os.environ.copy()
    for n in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR",
              "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE"):
        env.pop(n, None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", ENVIRONMENT="test",
               DATABASE_URL="postgresql+psycopg://sintetico:sintetico@127.0.0.1:1/fase6_pruebas?connect_timeout=1",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
               FASE4_EVIDENCIA=str(rutas["mediciones"]), PYTEST_DEBUG_TEMPROOT=str(rutas["pytest"]))
    for sufijo, carpeta in ALMACENES_SINTETICOS:
        almacen = rutas["sinteticos"] / carpeta
        almacen.mkdir(parents=True)
        env["DIRECTORIO_" + sufijo] = str(almacen)
    env["ARCHIVO_OPERACION_AUTOMATICA"] = str(rutas["sinteticos"] / "f6-config-inexistente.json")
    return env


def _limpiar_temporal(temporal):
    raiz = temporal.resolve()
    def resolver(funcion, nombre, error):
        p = Path(nombre)
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            raise error
        if p.resolve() != raiz and raiz not in p.resolve().parents:
            raise error
        p.chmod(p.stat().st_mode | stat.S_IWRITE)
        funcion(nombre)
    shutil.rmtree(temporal, onexc=resolver)


def validar(worktree, manifiesto, evidencia, plazo_segundos=7200, bateria="focal"):
    evidencia.mkdir(parents=True, exist_ok=False)
    ruta_resultado = evidencia / "resultado-validacion.json"
    r = {"version": VERSION, "plataforma": platform.platform(), "python": sys.version,
         "suite": bateria, "estado": "error", "codigo": 1, "error": None, "pasos": [],
         "estado_limpieza": "no_necesaria", "avisos_limpieza": [],
         "inicio_utc": datetime.now(timezone.utc).isoformat()}
    temporal = None
    inicio = time.monotonic()
    try:
        if bateria not in ("dirigida", "focal", "regresiones", "completa") or plazo_segundos < 1:
            raise ValueError("Batería o plazo no admitidos")
        mf = json.loads(manifiesto.read_text(encoding="utf-8-sig"))
        if mf.get("version") != VERSION or mf.get("base") != BASE:
            raise ValueError("Manifiesto ajeno a Fase 6")
        temporal = Path(tempfile.mkdtemp(prefix=PREFIJO_TEMPORAL))
        rutas = rutas_temporales(temporal)
        espejo = rutas["codigo"]
        if os.name == "nt":
            for f in mf["inventario_publico"]:
                if len(str(espejo / _ruta_publica(f["ruta"])).encode("utf-16-le")) // 2 > 259:
                    raise ValueError("El espejo excede el presupuesto Win32")
        r["archivos_publicos_verificados"] = _preparar_espejo(worktree, mf, espejo)
        env = _entorno(rutas)
        backend = espejo / "backend"
        junit = evidencia / ("resultados-" + bateria + ".xml")
        for nombre, comando in _comandos(bateria, junit, evidencia):
            restante = plazo_segundos - (time.monotonic() - inicio)
            if restante <= 0:
                raise TimeoutError("Se agotó el plazo antes de " + nombre)
            paso = _ejecutar(nombre, comando, cwd=backend, entorno=env, evidencia=evidencia, plazo=restante)
            r["pasos"].append(paso)
            if nombre.startswith("pytest-") and junit.exists():
                r["junit"] = _contar_junit(junit)
            _guardar(ruta_resultado, r)
            if paso["codigo"] != 0 or paso["plazo_agotado"]:
                raise RuntimeError("Falló " + nombre + "; consulte " + paso["log"])
            if nombre.startswith("pytest-") and r.get("junit", {}).get("omitidas", 0):
                raise RuntimeError("Hay omisiones: no se contabilizan como aprobadas")
        r.update(estado="aprobado", codigo=0)
    except BaseException as error:
        r["error"] = type(error).__name__ + ": " + str(error)
        if isinstance(error, KeyboardInterrupt):
            r["codigo"] = 130
    finally:
        conservar = True
        if temporal is not None:
            try:
                r["mediciones"] = _conservar_mediciones(rutas["mediciones"], evidencia)
            except Exception as error:
                conservar = False
                r["error_mediciones"] = type(error).__name__ + ": " + str(error)
                r["temporal_pendiente"] = str(temporal)
                r["estado_limpieza"] = "pendiente"
                if r["error"] is None:
                    r.update(estado="error", codigo=1, error="No se pudieron conservar las mediciones")
        r["segundos"] = round(time.monotonic() - inicio, 3)
        _guardar(ruta_resultado, r)
        if temporal is not None and conservar:
            try:
                _limpiar_temporal(temporal)
                r["estado_limpieza"] = "completa"
            except Exception as error:
                r["estado_limpieza"] = "pendiente"
                r["avisos_limpieza"].append(type(error).__name__ + ": " + str(error))
                r["temporal_pendiente"] = str(temporal)
            _guardar(ruta_resultado, r)
    return r["codigo"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--manifiesto", type=Path, required=True)
    parser.add_argument("--evidencia", type=Path, required=True)
    parser.add_argument("--plazo-segundos", type=int, default=7200)
    parser.add_argument("--bateria", choices=("dirigida", "focal", "regresiones", "completa"), default="focal")
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("El CLI solo ejecuta Windows nativo; las funciones portables no lo sustituyen")
    return validar(args.worktree.resolve(), args.manifiesto.resolve(), args.evidencia.resolve(),
                   args.plazo_segundos, args.bateria)


if __name__ == "__main__":
    raise SystemExit(main())
