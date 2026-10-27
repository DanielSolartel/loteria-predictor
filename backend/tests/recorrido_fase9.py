"""Recorrido HTTP completo de la Fase 9.1 con procesos reales y datos SINTETICOS.

Arranca, con las opciones documentadas (`--host 127.0.0.1 --no-access-log
--no-proxy-headers`) y puertos libres reservados:
- la API publica real con proveedores sinteticos (`tests.fase9_api_sintetica:app`,
  SQLite de la Fase 7 y almacenes temporales de la Fase 4). Es el SUSTITUTO de
  la API con PostgreSQL: este recorrido NO es una prueba de PostgreSQL;
- la pasarela (`app.pasarela.aplicacion:app`) con una clave canario generada
  para esta ejecucion y la SPA compilada (`frontend/dist`);
- en el escenario `vite`, ademas, el servidor de desarrollo de Vite en loopback.

Despues lanza el recorrido de Chromium (`frontend/e2e/recorrido.mjs`), hace
peticiones HTTP directas de control (Host ajeno, Origin ajeno, rutas y
recursos inexistentes) y busca el canario en los registros de todos los
procesos. La clave y su huella nunca se imprimen ni se escriben en los
resultados: solo se informa de si aparecieron.

Fase 9.3: `fiabilidad` (recorrido dirigido de explicacion, clasificacion y
fiabilidad, con controles directos de la ruta nueva; tambien va dentro de
`normal`) y `cuota_fiabilidad` (6 fichas por minuto: carga inicial 1+3=4;
429 solo tras consultar explicitamente la fiabilidad, con reintento manual).

Uso (desde backend/, con el venv del proyecto):
    python -m tests.recorrido_fase9 --salida <carpeta> [--escenario normal|cuota|api_caida|sin_clave|clave_incorrecta|vite|fiabilidad|cuota_fiabilidad]
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
FRONTEND = REPO / "frontend"
OPCIONES = ["--host", "127.0.0.1", "--no-access-log", "--no-proxy-headers"]
ESCENARIOS = ("normal", "cuota", "api_caida", "sin_clave", "clave_incorrecta", "vite", "fiabilidad", "cuota_fiabilidad")
FICHAS = {"cuota": "8", "cuota_fiabilidad": "6"}  # el resto: 100000 por minuto
ESPERA_ARRANQUE = 180


def puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def entorno_minimo(**extra: str) -> dict[str, str]:
    """Entorno sin variables del proyecto (ni DATABASE_URL ni claves ajenas)."""
    base = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "HOME",
                                       "USERPROFILE", "LANG", "PLAYWRIGHT_BROWSERS_PATH", "APPDATA", "LOCALAPPDATA")
            if k in os.environ}
    base.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
    base.update(extra)
    return base


@contextmanager
def proceso(nombre: str, argumentos: list[str], entorno: dict[str, str], registros: Path, *, cwd: Path,
            listo: str):
    """Proceso con su salida en `registros/<nombre>.log`; espera a `listo` en el registro."""
    registro = registros / f"{nombre}.log"
    with open(registro, "wb") as salida:
        p = subprocess.Popen(argumentos, cwd=cwd, env=entorno, stdout=salida, stderr=subprocess.STDOUT)
    try:
        limite = time.monotonic() + ESPERA_ARRANQUE
        while listo not in registro.read_text(encoding="utf-8", errors="replace"):
            if p.poll() is not None or time.monotonic() > limite:
                raise RuntimeError(f"{nombre} no arranco (codigo {p.poll()}); ver {registro.name}")
            time.sleep(0.1)
        yield p
    finally:
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=20)


def uvicorn(nombre: str, app: str, puerto: int, entorno: dict[str, str], registros: Path):
    return proceso(nombre, [sys.executable, "-B", "-m", "uvicorn", app, *OPCIONES[:2], "--port", str(puerto),
                            *OPCIONES[2:]],
                   entorno, registros, cwd=BACKEND, listo=f"Uvicorn running on http://127.0.0.1:{puerto}")


def peticion(puerto: int, ruta: str, cabeceras: dict[str, str] | None = None) -> dict:
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=30)
    try:
        c.putrequest("GET", ruta, skip_host=True, skip_accept_encoding=True)
        for k, v in {"Host": f"127.0.0.1:{puerto}", **(cabeceras or {})}.items():
            c.putheader(k, v)
        c.endheaders()
        r = c.getresponse()
        cuerpo = r.read()
        tipo = r.getheader("content-type") or ""
        codigo = None
        if tipo.startswith("application/json"):
            try:
                codigo = (json.loads(cuerpo).get("error") or {}).get("codigo")
            except (ValueError, AttributeError):
                codigo = "no_json"
        return {"ruta": ruta, "estado": r.status, "tipo": tipo.split(";")[0], "codigo": codigo,
                "cabeceras": {k.lower(): v for k, v in r.getheaders()
                              if k.lower() in ("content-security-policy", "x-frame-options", "x-content-type-options",
                                               "referrer-policy", "cache-control", "x-request-id", "retry-after",
                                               "access-control-allow-origin", "set-cookie")}}
    finally:
        c.close()


CONTROLES_VITE = [
    ("vite_host_ajeno", "/api/v1/juegos", {"Host": "rebinding.example"}),
    ("vite_origen_ajeno", "/api/v1/juegos", {"Origin": "http://ajeno.example"}),
    ("vite_api_inexistente", "/api/v1/nada", {}),
]


CONTROLES_FIABILIDAD = [  # Fase 9.3: la ruta nueva a traves de la pasarela, fuera del navegador
    ("fiabilidad_corte", "/api/v1/juegos/BALOTO/fiabilidad?hasta=2190", {}),
    ("fiabilidad_linea_no_admitida", "/api/v1/juegos/BALOTO/fiabilidad?linea=carteras:uniforme-v1", {}),
    ("fiabilidad_hasta_repetido", "/api/v1/juegos/BALOTO/fiabilidad?hasta=1&hasta=2", {}),
    ("fiabilidad_hasta_no_valido", "/api/v1/juegos/BALOTO/fiabilidad?hasta=0", {}),
    ("fiabilidad_juego_inexistente", "/api/v1/juegos/QUINELA/fiabilidad", {}),
    ("fiabilidad_origen_ajeno", "/api/v1/juegos/BALOTO/fiabilidad", {"Origin": "http://ajeno.example"}),
]


def controles_directos(puerto: int, casos: list | None = None) -> list[dict]:
    """Peticiones HTTP directas (fuera del navegador) a la pasarela o, en modo Vite, a Vite."""
    casos = casos or [
        ("indice", "/", {}),
        ("ruta_spa", "/juegos/BALOTO/sorteos", {}),
        ("api_inexistente", "/api/v1/nada", {}),
        ("recurso_inexistente", "/assets/nada.js", {}),
        ("archivo_fuera_de_dist", "/..%2f..%2fbackend%2fpasarela.ejemplo.env", {}),
        ("host_ajeno", "/api/v1/juegos", {"Host": "rebinding.example:%d" % puerto}),
        ("origen_ajeno", "/api/v1/juegos", {"Origin": "http://ajeno.example"}),
        ("sitio_cruzado", "/api/v1/juegos", {"Sec-Fetch-Site": "cross-site"}),
        ("cors", "/api/v1/juegos", {"Origin": "http://ajeno.example", "Access-Control-Request-Method": "GET"}),
        ("documentacion_excluida", "/api/v1/docs", {}),
        ("openapi_excluido", "/api/v1/openapi.json", {}),
    ]
    salida = []
    for nombre, ruta, cabeceras in casos:
        r = peticion(puerto, ruta, cabeceras)
        salida.append({"caso": nombre, **r})
    return salida


def buscar_canario(carpeta: Path, canarios: dict[str, str]) -> dict[str, list[str]]:
    """Archivos de `carpeta` (recursivo) que contienen algun canario, por nombre de canario."""
    encontrados: dict[str, list[str]] = {n: [] for n in canarios}
    for archivo in sorted(p for p in carpeta.rglob("*") if p.is_file()):
        datos = archivo.read_bytes()
        for nombre, valor in canarios.items():
            if valor.encode() in datos:
                encontrados[nombre].append(str(archivo.relative_to(carpeta)))
    return encontrados


def ejecutar(escenario: str, salida: Path, *, anchos: str, node: str) -> int:
    salida.mkdir(parents=True, exist_ok=True)
    registros = salida / "registros"
    registros.mkdir(exist_ok=True)
    dist = FRONTEND / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("falta frontend/dist: ejecuta antes `npm run build`")
    clave = "f9canario-" + secrets.token_hex(24)
    huella = hashlib.sha256(clave.encode("ascii")).hexdigest()
    p_api, p_pasarela = puerto_libre(), puerto_libre()
    p_vite = puerto_libre() if escenario == "vite" else None
    fichas = FICHAS.get(escenario, "100000")
    with ExitStack() as pila:
        raiz = Path(pila.enter_context(tempfile.TemporaryDirectory(prefix="f9-recorrido-")))
        entorno_api = entorno_minimo(F9_RAIZ=str(raiz / "api"), API_PUBLICA_CLAVES=f"f9:sha256:{huella}",
                                     F9_FICHAS_POR_MINUTO=fichas, F9_FICHAS_POR_MINUTO_IP="100000")
        pila.enter_context(uvicorn("api", "tests.fase9_api_sintetica:app", p_api, entorno_api, registros))
        destino = p_api if escenario != "api_caida" else puerto_libre()
        hosts = [f"127.0.0.1:{p_pasarela}", f"localhost:{p_pasarela}"]
        origenes = [f"http://127.0.0.1:{p_pasarela}", f"http://localhost:{p_pasarela}"]
        if p_vite is not None:
            hosts.append(f"127.0.0.1:{p_vite}")
            origenes.append(f"http://127.0.0.1:{p_vite}")
        entorno_pasarela = entorno_minimo(PASARELA_API_URL=f"http://127.0.0.1:{destino}", PASARELA_HOSTS=",".join(hosts),
                                          PASARELA_ORIGENES=",".join(origenes), PASARELA_DIST=str(dist),
                                          PASARELA_CONSOLA_LOCAL="http://127.0.0.1:8000/")
        if escenario == "clave_incorrecta":  # formato valido, pero la API no conoce su huella
            entorno_pasarela["PASARELA_CLAVE_API"] = "f9otra-" + secrets.token_hex(24)
        elif escenario != "sin_clave":
            entorno_pasarela["PASARELA_CLAVE_API"] = clave
        pila.enter_context(uvicorn("pasarela", "app.pasarela.aplicacion:app", p_pasarela, entorno_pasarela, registros))
        base = f"http://127.0.0.1:{p_pasarela}"
        resultado: dict = {"escenario": escenario, "sustitutos": {
            "api": "tests.fase9_api_sintetica:app (crear_app real; SQLite sintetica de la Fase 7 y almacenes "
                   "temporales de la Fase 4); no es PostgreSQL",
            "pasarela": "app.pasarela.aplicacion:app real", "spa": "frontend/dist compilado"},
            "fichas_por_minuto": int(fichas)}
        if p_vite is not None:
            entorno_vite = entorno_minimo(PASARELA_URL=base, VITE_PUERTO=str(p_vite))
            # `npm run dev` equivale a `vite`; se lanza con node para poder terminarlo tambien en Windows.
            vite = str(FRONTEND / "node_modules" / "vite" / "bin" / "vite.js")
            pila.enter_context(proceso("vite", [node, vite], entorno_vite, registros, cwd=FRONTEND,
                                       listo=f"http://127.0.0.1:{p_vite}/"))
            base = f"http://127.0.0.1:{p_vite}"
        resultado["controles_directos"] = ([*controles_directos(p_pasarela), *controles_directos(p_pasarela, CONTROLES_FIABILIDAD)]
                                           if escenario == "normal" else
                                           controles_directos(p_vite, CONTROLES_VITE) if p_vite is not None else
                                           controles_directos(p_pasarela, CONTROLES_FIABILIDAD) if escenario == "fiabilidad"
                                           else [])
        navegador = salida / "navegador"
        cuerpos = raiz / "respuestas"  # temporal: no forma parte de las evidencias
        cuerpos.mkdir()
        argumentos = [node, str(FRONTEND / "e2e" / "recorrido.mjs"), "--base", base, "--escenario", escenario,
                      "--salida", str(navegador), "--anchos", anchos, "--cuerpos", str(cuerpos)]
        with open(registros / "navegador.log", "wb") as log:
            codigo = subprocess.run(argumentos, cwd=FRONTEND, env=entorno_minimo(), stdout=log,
                                    stderr=subprocess.STDOUT, timeout=3600).returncode
        resultado["codigo_navegador"] = codigo
        resultado["respuestas_al_navegador_inspeccionadas"] = sum(1 for _ in cuerpos.iterdir())
        canario_en_respuestas = buscar_canario(cuerpos, {"clave": clave, "huella": huella})
    canarios = {"clave": clave, "huella": huella}
    resultado["canario"] = {
        "respuestas_al_navegador": canario_en_respuestas,
        "registros": buscar_canario(registros, canarios),
        "navegador": buscar_canario(salida / "navegador", canarios) if (salida / "navegador").exists() else {},
        "dist": buscar_canario(dist, canarios),
    }
    filtrado = any(v for grupo in resultado["canario"].values() for v in grupo.values())
    resultado["canario_encontrado"] = filtrado
    fallos_directos = [c for c in resultado["controles_directos"] if not esperado(c)]
    resultado["controles_fallidos"] = [c["caso"] for c in fallos_directos]
    (salida / "recorrido.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if codigo == 0 and not filtrado and not fallos_directos else 1


_ESPERADO = {
    "indice": (200, None), "ruta_spa": (200, None), "api_inexistente": (404, "ruta_no_disponible"),
    "recurso_inexistente": (404, None), "archivo_fuera_de_dist": (400, "ruta_no_valida"),
    "host_ajeno": (403, "host_no_permitido"), "origen_ajeno": (403, "origen_no_permitido"),
    "sitio_cruzado": (403, "origen_no_permitido"), "cors": (403, "origen_no_permitido"),
    "documentacion_excluida": (404, "ruta_no_disponible"), "openapi_excluido": (404, "ruta_no_disponible"),
    "vite_host_ajeno": (403, None), "vite_origen_ajeno": (403, "origen_no_permitido"),
    "vite_api_inexistente": (404, "ruta_no_disponible"),
    "fiabilidad_corte": (200, None), "fiabilidad_linea_no_admitida": (422, "parametro_no_admitido"),
    "fiabilidad_hasta_repetido": (422, "parametro_repetido"), "fiabilidad_hasta_no_valido": (422, "parametro_no_valido"),
    "fiabilidad_juego_inexistente": (404, "no_encontrado"), "fiabilidad_origen_ajeno": (403, "origen_no_permitido"),
}


def esperado(caso: dict) -> bool:
    estado, codigo = _ESPERADO[caso["caso"]]
    if caso["estado"] != estado or (codigo is not None and caso["codigo"] != codigo):
        return False
    if caso["caso"] in ("indice", "ruta_spa"):
        return caso["tipo"] == "text/html" and "frame-ancestors 'none'" in caso["cabeceras"].get(
            "content-security-policy", "")
    if caso["caso"] == "recurso_inexistente":
        return caso["tipo"] != "text/html"
    return "access-control-allow-origin" not in caso["cabeceras"] and "set-cookie" not in caso["cabeceras"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--escenario", choices=ESCENARIOS, default="normal")
    parser.add_argument("--anchos", default="360,390,1280")
    parser.add_argument("--node", default=shutil.which("node") or "node")
    args = parser.parse_args(argv)
    return ejecutar(args.escenario, args.salida.resolve(), anchos=args.anchos, node=args.node)


if __name__ == "__main__":
    sys.exit(main())
