"""Supervisor optativo para baterías focal y completa Windows, sin datos reales.

No se importa la aplicación en este proceso. El CLI exige Windows; las funciones
pequeñas de supervisión permiten ensayar plazos y errores reales también en Linux.
La validación se ejecuta en una copia pública verificada, fuera del worktree.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

# Una raíz privada corta, con espacio y sufijo aleatorio de mkdtemp. Pytest
# conserva sus propios niveles pytest-of-<usuario>/pytest-0, sin --basetemp.
PREFIJO_TEMPORAL = "m "
CARPETA_ESPEJO = "c"


def rutas_temporales(temporal):
    """También acepta PureWindowsPath para medir el presupuesto en Linux."""
    return {"codigo": temporal / CARPETA_ESPEJO, "pytest": temporal, "mediciones": temporal / "e",
            "sinteticos": temporal / "s"}


def _conservar_mediciones(origen: Path, evidencia: Path) -> dict:
    """Nombre final corto: Downloads no recibe los nombres de cada prueba."""
    destino = evidencia / "mediciones-fase4.zip"
    filas = []
    with zipfile.ZipFile(destino, "x", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(origen.rglob("*")) if origen.exists() else []:
            if p.is_file():
                b = p.read_bytes(); n = p.relative_to(origen).as_posix()
                z.writestr(n, b)
                filas.append({"ruta": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    with zipfile.ZipFile(destino) as z:
        if z.testzip() is not None:
            raise RuntimeError("CRC incorrecto al conservar mediciones")
    return {"archivo": destino.name, "sha256": hashlib.sha256(destino.read_bytes()).hexdigest(),
            "archivos": filas, "cantidad": len(filas)}


def _guardar(ruta: Path, resultado: dict) -> None:
    ruta.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _huella(contenido: bytes, tipo: str) -> str:
    if tipo == "texto":
        contenido = contenido.replace(b"\r\n", b"\n")
    elif tipo != "binario":
        raise ValueError("Tipo de contenido no reconocido")
    return hashlib.sha256(contenido).hexdigest()


def _ruta_publica(nombre: str) -> Path:
    ruta = PurePosixPath(nombre)
    if not nombre or "\\" in nombre or ruta.is_absolute() or any(p in ("", ".", "..") for p in ruta.parts):
        raise ValueError("Ruta pública no válida")
    if any(p.lower() in (".git", ".env", "__pycache__") for p in ruta.parts):
        raise ValueError("El inventario no puede incluir datos privados ni generados")
    almacenes = {"backend/storage/" + n + "/.gitkeep" for n in
                 ("carteras", "html", "laboratorio", "logs", "predicciones", "pronosticos", "resultados")}
    if (ruta.parts[0].lower() == "storage" or tuple(p.lower() for p in ruta.parts[:2]) == ("backend", "storage")) and nombre not in almacenes:
        raise ValueError("El inventario solo admite los marcadores públicos .gitkeep, nunca datos de almacenes")
    return Path(*ruta.parts)


def _preparar_espejo(worktree: Path, manifiesto: dict, destino: Path) -> int:
    vistos = set()
    filas = manifiesto["inventario_publico"]
    for fila in filas:
        relativa = _ruta_publica(fila["ruta"])
        clave = relativa.as_posix().casefold()
        if clave in vistos:
            raise ValueError("Ruta pública repetida sin distinguir mayúsculas")
        vistos.add(clave)
        origen = worktree / relativa
        if origen.is_symlink() or any(p.is_symlink() for p in origen.parents if p != worktree.parent):
            raise ValueError("El espejo público no admite redirecciones por enlaces")
        contenido = origen.read_bytes()
        esperado = fila["despues"]
        if isinstance(esperado, dict):
            esperado = esperado["sha256"]
        if _huella(contenido, fila["tipo"]) != esperado:
            raise ValueError("El código no coincide con el manifiesto: " + relativa.as_posix())
        # .env.example es documentación pública; no se necesita en la ejecución.
        if relativa.name == ".env.example":
            continue
        salida = destino / relativa
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_bytes(contenido)
    return len(vistos)


def _finalizar_arbol(proceso: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proceso.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
    else:
        try:
            os.killpg(proceso.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proceso.wait(timeout=30)


def _ejecutar(nombre: str, comando: list[str], *, cwd: Path, entorno: dict[str, str],
              evidencia: Path, plazo: float) -> dict:
    inicio = time.monotonic()
    log = evidencia / (nombre + ".log")
    resultado = {"nombre": nombre, "comando": comando, "codigo": None,
                 "plazo_agotado": False, "log": log.name}
    opciones = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with log.open("wb") as archivo:
        proceso = subprocess.Popen(comando, cwd=cwd, env=entorno, stdout=archivo,
                                   stderr=subprocess.STDOUT, **opciones)
        try:
            resultado["codigo"] = proceso.wait(timeout=max(0.1, plazo))
        except subprocess.TimeoutExpired:
            resultado["plazo_agotado"] = True
            _finalizar_arbol(proceso)
            resultado["codigo"] = proceso.returncode
        except BaseException:
            _finalizar_arbol(proceso)
            raise
    resultado["segundos"] = round(time.monotonic() - inicio, 3)
    return resultado


def _contar_junit(ruta: Path) -> dict:
    raiz = ET.parse(ruta).getroot()
    cuentas = Counter(aprobadas=0, fallidas=0, errores=0, omitidas=0)
    omisiones = []
    for caso in raiz.iter("testcase"):
        if caso.find("failure") is not None:
            cuentas["fallidas"] += 1
        elif caso.find("error") is not None:
            cuentas["errores"] += 1
        elif (omitida := caso.find("skipped")) is not None:
            cuentas["omitidas"] += 1
            omisiones.append({"clase": caso.get("classname"), "prueba": caso.get("name"),
                              "motivo": omitida.get("message", ""),
                              "clasificacion": "pendiente_revision; no cuenta como aprobada"})
        else:
            cuentas["aprobadas"] += 1
    return {**cuentas, "omisiones": omisiones}


def validar(worktree: Path, manifiesto: Path, evidencia: Path, plazo_segundos: int = 7200, bateria="focal") -> int:
    """Guardar el resultado principal antes de intentar borrar temporales propios."""
    evidencia.mkdir(parents=True, exist_ok=False)
    ruta_resultado = evidencia / "resultado-validacion.json"
    resultado = {"version": 1, "plataforma": platform.platform(), "python": sys.version,
                 "suite": bateria, "pasos": [],
                 "estado": "error", "codigo": 1, "error": None, "avisos_limpieza": [],
                 "inicio_utc": datetime.now(timezone.utc).isoformat()}
    temporal = None
    inicio = time.monotonic()
    try:
        if plazo_segundos < 1:
            raise ValueError("El plazo debe ser positivo")
        if bateria not in ("focal", "completa"):
            raise ValueError("Batería desconocida")
        mf = json.loads(manifiesto.read_text(encoding="utf-8-sig"))
        if mf.get("version") != "ml-cinco-familias-1" or mf.get("base") != "90e6ab06b2a188fde9416fb0aac9e7366b7b04a6":
            raise ValueError("Manifiesto ajeno a esta entrega")
        # mkdtemp respeta el TEMP normal de la consola. Nunca modifica TEMP/TMP.
        temporal = Path(tempfile.mkdtemp(prefix=PREFIJO_TEMPORAL))
        rutas = rutas_temporales(temporal)
        espejo = rutas["codigo"]
        espejo.mkdir()
        if os.name == "nt":
            largas = [str(espejo / _ruta_publica(f["ruta"])) for f in mf["inventario_publico"]
                      if len(str(espejo / _ruta_publica(f["ruta"]))) > 259]
            if largas:
                raise ValueError("El espejo excede el presupuesto Win32 de 259 caracteres: " + largas[0])
        resultado["archivos_publicos_verificados"] = _preparar_espejo(worktree, mf, espejo)
        entorno = os.environ.copy()
        for nombre in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE"):
            entorno.pop(nombre, None)
        entorno.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
                       PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", DATABASE_URL="postgresql+psycopg://sintetico:sintetico@127.0.0.1:1/ml_pruebas?connect_timeout=1",
                       OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
                       FASE4_EVIDENCIA=str(rutas["mediciones"]),
                       ENVIRONMENT="test", PYTEST_DEBUG_TEMPROOT=str(rutas["pytest"]))
        for sufijo, carpeta in (("PRONOSTICOS_EXPERIMENTALES", "pronosticos"), ("OPERACION", "operacion"),
                                ("LABORATORIO_MODELOS", "laboratorio"), ("CARTERAS_MODELOS", "carteras"),
                                ("RESULTADOS_MODELOS", "resultados"), ("PREDICCIONES_MODELOS", "predicciones")):
            almacen = rutas["sinteticos"] / carpeta
            almacen.mkdir(parents=True)
            entorno["DIRECTORIO_" + sufijo] = str(almacen)
        backend = espejo / "backend"
        junit = evidencia / ("resultados-windows-" + bateria + ".xml")
        pruebas = (["tests/unit/test_fase4_publicacion_registro.py", "tests/unit/test_producto4_aislamiento.py",
                    "tests/unit/test_ml_incidencias_windows.py", "tests/unit/test_ml_registro.py",
                    "tests/unit/test_ml_cinco_flujo.py", "tests/unit/test_ml_recursos_publicacion.py"]
                   if bateria == "focal" else ["tests"])
        comandos = [
            ("diagnostico-numerico", [sys.executable, "-m", "tests.diagnostico_ml_numerico", "--salida", str(evidencia / "matriz-numerica.json")]),
            ("pytest-" + bateria, [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rsw", "--junitxml=" + str(junit), *pruebas]),
            ("pip-check", [sys.executable, "-m", "pip", "check"]),
        ]
        if bateria == "completa":
            comandos[2:2] = [("openssl-exigir", [sys.executable, "scripts/ci_contrastes_openssl.py", str(junit), "--modo", "exigir"]),
                             ("demostracion-ml", [sys.executable, "-m", "tests.demostracion_ml_cinco_familias"])]
        for nombre, comando in comandos:
            restante = plazo_segundos - (time.monotonic() - inicio)
            if restante <= 0:
                raise TimeoutError("Se agotó el plazo global antes de " + nombre)
            paso = _ejecutar(nombre, comando, cwd=backend, entorno=entorno, evidencia=evidencia, plazo=restante)
            resultado["pasos"].append(paso)
            if nombre.startswith("pytest-") and junit.exists():
                resultado["junit"] = _contar_junit(junit)
            # Un fallo conserva el JUnit y bloquea las acciones posteriores.
            if paso["codigo"] != 0 or paso["plazo_agotado"]:
                raise RuntimeError("Falló " + nombre + "; consulte " + paso["log"])
            if nombre.startswith("pytest-") and resultado.get("junit", {}).get("omitidas", 0):
                raise RuntimeError("Hay omisiones; deben clasificarse y resolverse antes del cierre")
        resultado.update(estado="aprobado", codigo=0)
    except BaseException as exc:
        resultado["error"] = type(exc).__name__ + ": " + str(exc)
        if isinstance(exc, KeyboardInterrupt):
            resultado["codigo"] = 130
    finally:
        conservar = True
        if temporal is not None:
            try:
                resultado["mediciones"] = _conservar_mediciones(rutas["mediciones"], evidencia)
            except Exception as exc:
                conservar = False
                resultado["error_mediciones"] = repr(exc)
                resultado["temporal_pendiente"] = str(temporal)
                if resultado["error"] is None:
                    resultado.update(error="No se pudieron conservar las mediciones", codigo=1, estado="error")
        resultado["segundos"] = round(time.monotonic() - inicio, 3)
        # Esta escritura ocurre incluso si rmtree falla posteriormente.
        _guardar(ruta_resultado, resultado)
        if temporal is not None and conservar:
            try:
                shutil.rmtree(temporal)
            except Exception as exc:
                resultado["avisos_limpieza"].append(type(exc).__name__ + ": " + str(exc))
                resultado["temporal_pendiente"] = str(temporal)
                _guardar(ruta_resultado, resultado)
    return resultado["codigo"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--manifiesto", type=Path, required=True)
    parser.add_argument("--evidencia", type=Path, required=True)
    parser.add_argument("--plazo-segundos", type=int, default=7200)
    parser.add_argument("--bateria", choices=("focal", "completa"), default="focal")
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("El CLI acredita Windows nativo y solo se ejecuta en Windows; Linux no lo sustituye")
    return validar(args.worktree.resolve(), args.manifiesto.resolve(), args.evidencia.resolve(), args.plazo_segundos, args.bateria)


if __name__ == "__main__":
    raise SystemExit(main())
