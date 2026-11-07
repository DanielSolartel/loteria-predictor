"""Diagnostico de lectura para UN ensayo E107 conservado.

Comandos Docker cerrados: ps, inspect y logs. Nunca start, exec, stop, rm ni
consultas a una base. El informe contiene solo campos permitidos; no copia
stderr, logs crudos, variables de entorno, contrasenas ni archivos de datos.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import signal
import stat
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ETIQUETA = "es.loteria.e107.ejecucion"
IMAGENES = {
    "sha256:3f1ef0b339e50f76326297bb15367eb40216f1bd6df3a85f07d6c71cd2ea2530",
    "sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab",
}
FORMATO_INSPECCION = ('{"Id":{{json .Id}},"Name":{{json .Name}},"Image":{{json .Image}},'
    '"State":{{json .State}},"Labels":{{json .Config.Labels}},"User":{{json .Config.User}},'
    '"Cmd":{{json .Config.Cmd}},"Mounts":{{json .Mounts}}}')


class Rechazo(ValueError):
    pass


def validar_raiz(valor: str) -> Path:
    if not isinstance(valor, str) or not re.fullmatch(r"/tmp/e107pc-[a-z0-9_-]{8,40}", valor):
        raise Rechazo("directorio_no_es_de_un_ensayo_e107")
    return Path(valor)


def ejecutar(args: list[str]) -> bytes:
    # Una regresion futura tampoco puede introducir acciones mutables aqui.
    if not args or args[0] not in {"ps", "inspect", "logs"}:
        raise Rechazo("comando_fuera_del_diagnostico")
    p = None
    try:
        p = subprocess.Popen(["docker", "--host", "unix:///var/run/docker.sock", *args],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True)
        salida, errores = p.communicate(timeout=15)
    except BaseException:
        if p is not None:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.communicate(timeout=3)
        raise Rechazo("consulta_docker_no_completa") from None
    if p.returncode or len(salida) + len(errores) > 1048576:
        raise Rechazo("consulta_docker_rechazada")
    if args[0] == "logs":
        return salida + b"\n" + errores
    return salida


def seleccionar(d: dict, raiz: Path, propietarios=frozenset()) -> str | None:
    try:
        run = d["Labels"][ETIQUETA]
        if not isinstance(run, str) or not re.fullmatch(r"[a-f0-9]{32}", run):
            return None
        if (not re.fullmatch(r"[a-f0-9]{64}", d["Id"])
                or not re.fullmatch(r"/e107" + run + r"-(?:postgres|preparacion-[1-9][0-9]*)", d["Name"])
                or d["Image"] not in IMAGENES):
            return None
        bind = {m["Destination"]: m for m in d["Mounts"] if m.get("Type") == "bind"}
        origenes = {m["Source"] for m in bind.values()}
        if d["Name"].endswith("-postgres"):
            return "postgres" if (str(raiz / "pgdatos") in origenes or (
                run in propietarios and set(bind) == {"/var/lib/postgresql/data", "/run/secrets/password"})) else None
        cmd = d["Cmd"]
        # Docker Desktop puede traducir Source. Destination y el comando del
        # auxiliar siguen ligando los dos montajes al directorio exacto del ensayo.
        if (set(bind) != {str(raiz), str(raiz / "fuente")}
                or bind[str(raiz)].get("RW") is not True or bind[str(raiz / "fuente")].get("RW") is not False
                or not isinstance(cmd, list) or len(cmd) != 5 or cmd[0] != "-B"
                or cmd[1] != str(raiz / "fuente/despliegue/pc_local/preparar.py")
                or cmd[2] not in {"comprobar", "migrar", "generar", "verificar"}
                or cmd[3:] != [str(raiz), str(raiz / "fuente")]):
            return None
        return cmd[2]
    except (KeyError, TypeError, AttributeError):
        return None


PATRONES = {
    "sistema_de_archivos_solo_lectura": r"Read-only file system|Errno 30",
    "permiso_denegado": r"Permission denied|Errno 13",
    "modulo_python_no_disponible": r"ModuleNotFoundError|No module named",
    "biblioteca_nativa_no_disponible": r"cannot open shared object file|Library not loaded|libgomp[^\n]{0,80}not found",
    "limite_de_hilos": r"Thread creation failed|pthread_create failed|Resource temporarily unavailable",
    "conexion_postgresql_rechazada": r"connection refused|Connection refused|password authentication failed",
    "tiempo_agotado": r"TimeoutExpired|timed out|timeout expired",
}


def resumir_logs(datos: bytes) -> dict:
    texto = datos.decode("utf-8", errors="replace")
    # Ambos canales se procesan localmente. Se exportan solo codigos, clases y
    # campos cerrados, nunca el texto libre que pudo imprimir un proceso.
    pasos = []
    for linea in texto.splitlines():
        m = re.match(r'^\s*\{\s*"id"\s*:\s*"(D[0-9]{2}[a-z]?|R[0-9]{2}|N-respaldo-(?:alterado|truncado))"\s*,\s*"ok"\s*:\s*(true|false)', linea)
        if m:
            pasos.append({"id": m[1], "ok": m[2] == "true"})
    modulos = []
    for m in re.finditer(r"No module named [\\\"']+([a-zA-Z0-9_.]+)", texto):
        nombre = m[1]
        if (len(nombre) <= 100 and nombre.split(".")[0] in {
                "httpx", "pytest", "fastapi", "psycopg", "sqlalchemy", "cryptography", "uvicorn",
                "alembic", "numpy", "scipy", "sklearn", "xgboost", "lightgbm", "app", "tests", "scripts"}):
            modulos.append(nombre)
    tipos = sorted(set(re.findall(r'\b(ModuleNotFoundError|ImportError|ValueError|KeyError|TypeError|AttributeError|RuntimeError|OSError|PermissionError|FileNotFoundError|OperationalError|ProgrammingError|IntegrityError|StopIteration|MemoryError|NameError|SyntaxError)\s*:', texto)))
    normal = texto.replace('\\"', '"').replace('\\n', '\n')
    puntos = []
    for m in re.finditer(r'''File ["'][^"']*/fuente/((?:backend|despliegue)/[A-Za-z0-9_./-]+\.py)["'], line ([1-9][0-9]{0,5})''', normal):
        if ".." not in Path(m[1]).parts:
            puntos.append({"archivo_relativo": m[1], "linea": int(m[2])})
    return {"lineas_leidas": len(texto.splitlines()), "pasos": pasos,
            "indicios": sorted(k for k, patron in PATRONES.items() if re.search(patron, texto)),
            "tipos_de_error": tipos,
            "puntos_de_codigo": puntos[-6:],
            "modulos_ausentes": sorted(set(modulos)),
            "marcador_preparacion_presente": "E107_PREPARACION:" in texto}


def metadatos(raiz: Path) -> dict:
    resultado = {}
    for nombre in (".", "fuente", "generaciones", "generaciones/fuente", "generaciones/capturas",
                   "generaciones/capturas-respaldo", "generaciones/srv-pub", "generaciones/respaldos",
                   "generaciones/restauracion", "pki", "preparacion.json"):
        ruta = raiz if nombre == "." else raiz / nombre
        try:
            if any(p.is_symlink() for p in (raiz, *ruta.parents) if p == raiz or raiz in p.parents):
                resultado[nombre] = {"consulta": "enlace_no_seguido"}
                continue
            st = ruta.lstat()
            resultado[nombre] = {"existe": True, "enlace": stat.S_ISLNK(st.st_mode),
                                "uid": st.st_uid, "permisos": oct(stat.S_IMODE(st.st_mode))}
        except FileNotFoundError:
            resultado[nombre] = {"existe": False}
        except OSError:
            resultado[nombre] = {"consulta": "no_disponible"}
    return resultado


def diagnosticar(directorio: str, *, consultar=ejecutar) -> dict:
    raiz = validar_raiz(directorio)
    r = {"version": "e107-diagnostico-lectura/1", "codigo": 0,
         "fecha_utc": datetime.now(timezone.utc).isoformat(), "directorio_ensayo": str(raiz),
         "contenedores_modificados": False, "bases_consultadas": False,
         "fase6_intervenida": False, "archivos_de_secretos_leidos": False,
         "logs_crudos_exportados": False, "produccion_autorizada": False,
         "contenedores": [], "avisos": []}
    ids = consultar(["ps", "-aq", "--filter", "label=" + ETIQUETA]).decode("ascii").split()
    if len(ids) > 64 or len(set(ids)) != len(ids) or any(not re.fullmatch(r"[a-f0-9]{12,64}", i) for i in ids):
        raise Rechazo("inventario_de_contenedores_no_admitido")
    if ids:
        datos = consultar(["inspect", "--format", FORMATO_INSPECCION, *ids])
        objetos = [json.loads(l) for l in datos.splitlines() if l.strip()]
        if len(objetos) != len(ids):
            raise Rechazo("inspeccion_no_coincide")
        vistos = set()
        for d in objetos:
            cid = d.get("Id", "")
            if (not isinstance(cid, str) or cid in vistos or not re.fullmatch(r"[a-f0-9]{64}", cid)
                    or len([i for i in ids if cid.startswith(i)]) != 1):
                raise Rechazo("identidad_de_inspeccion_no_coincide")
            vistos.add(cid)
        propietarios = {d["Labels"][ETIQUETA] for d in objetos if seleccionar(d, raiz) not in (None, "postgres")}
        for d in objetos:
            tipo = seleccionar(d, raiz, propietarios)
            if tipo is None:
                continue
            s = d.get("State", {})
            if type(s.get("ExitCode")) is not int or type(s.get("OOMKilled")) is not bool or type(s.get("Running")) is not bool:
                raise Rechazo("estado_docker_no_admitido")
            fila = {"tipo": tipo, "en_ejecucion": s["Running"], "codigo_salida": s["ExitCode"],
                    "terminado_por_memoria": s["OOMKilled"], "error_runtime_presente": bool(s.get("Error")),
                    "usuario": d.get("User") if re.fullmatch(r"[0-9]+(?::[0-9]+)?", d.get("User", "")) else "de_imagen"}
            if tipo != "postgres":
                fila["origenes_de_montaje_traducidos"] = any(m.get("Type") == "bind" and m["Source"] != m["Destination"] for m in d["Mounts"])
                try:
                    fila["resumen_logs"] = resumir_logs(consultar(["logs", "--tail", "160", d["Id"]]))
                except Rechazo:
                    fila["resumen_logs"] = {"consulta": "no_disponible"}
            r["contenedores"].append(fila)
    if not r["contenedores"]:
        r["codigo"] = 1
        r["avisos"].append("no_se_encontro_el_ensayo_indicado")
    if any(c["en_ejecucion"] for c in r["contenedores"]):
        r["avisos"].append("se_observaron_recursos_activos_sin_modificarlos")
    r["metadatos_de_rutas"] = metadatos(raiz)
    return r


def emitir(informe: dict):
    b = (json.dumps(informe, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode()
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("resultado.json", b)
        z.writestr("SHA256SUMS", hashlib.sha256(b).hexdigest() + "  resultado.json\n")
    datos = salida.getvalue()
    print("E107_DIAGNOSTICO_JSON:" + json.dumps({"resumen": informe,
        "evidencia_base64": base64.b64encode(datos).decode(), "evidencia_bytes": len(datos),
        "evidencia_sha256": hashlib.sha256(datos).hexdigest()}, ensure_ascii=True), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--directorio-ensayo", required=True)
    a = p.parse_args()
    try:
        r = diagnosticar(a.directorio_ensayo)
    except BaseException as error:
        r = {"version": "e107-diagnostico-lectura/1", "codigo": 1, "contenedores_modificados": False,
             "motivo": str(error) if isinstance(error, Rechazo) else "diagnostico_no_completo"}
    emitir(r)
    return r["codigo"]


if __name__ == "__main__":
    raise SystemExit(main())
