"""Recorrido focal Fase 9.4: API real sintetica, pasarela real y SPA compilada.

No es PostgreSQL ni Windows. Cada escenario prepara almacenes nuevos y despues
comprueba sus huellas antes/despues de los GET. No intercepta respuestas HTTP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path

from tests import recorrido_fase9 as r9
from tests.unit.fixtures_fase4 import arbol

BACKEND, FRONTEND = r9.BACKEND, r9.FRONTEND
ESCENARIOS = ("normal", "vacio", "alterado", "incompatible", "cuota")
CONTROLES = [
    ("modelos", "/api/v1/juegos/BALOTO/modelos-guardados", {}),
    ("carteras", "/api/v1/juegos/COLORLOTO/carteras-guardadas", {}),
    ("resultados", "/api/v1/juegos/MILOTO/resultados?por_pagina=1", {}),
    ("juego_inexistente", "/api/v1/juegos/QUINELA/modelos-guardados", {}),
    ("parametro_ajeno", "/api/v1/juegos/BALOTO/modelos-guardados?reparar=true", {}),
    ("parametro_repetido", "/api/v1/juegos/BALOTO/resultados?pagina=1&pagina=2", {}),
    ("pagina_no_valida", "/api/v1/juegos/BALOTO/carteras-guardadas?pagina=0", {}),
    ("origen_ajeno", "/api/v1/juegos/BALOTO/modelos-guardados", {"Origin": "http://ajeno.example"}),
]
ESPERADOS = {"modelos": (200, None), "carteras": (200, None), "resultados": (200, None),
             "juego_inexistente": (404, "no_encontrado"), "parametro_ajeno": (422, "parametro_no_admitido"),
             "parametro_repetido": (422, "parametro_repetido"), "pagina_no_valida": (422, "parametro_no_valido"),
             "origen_ajeno": (403, "origen_no_permitido")}


def ejecutar(escenario: str, salida: Path, *, anchos: str, node: str, navegador: str | None = None) -> int:
    salida.mkdir(parents=True, exist_ok=True)
    registros = salida / "registros"
    registros.mkdir(exist_ok=True)
    dist = FRONTEND / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("falta frontend/dist: ejecuta antes npm run build")
    clave = "f94canario-" + secrets.token_hex(24)
    huella = hashlib.sha256(clave.encode("ascii")).hexdigest()
    p_api, p_pasarela = r9.puerto_libre(), r9.puerto_libre()
    resultado = {"escenario": escenario, "plataforma": sys.platform,
                 "sustitutos": {"api": "crear_app publica real con SQLite y artefactos sinteticos reales; no PostgreSQL",
                                "pasarela": "app.pasarela.aplicacion:app real", "spa": "frontend/dist compilado",
                                "intercepcion_http": False},
                 "fichas_por_minuto": 6 if escenario == "cuota" else 100000}
    # Atribuir el recorrido al bundle servido, independiente de las fuentes o
    # de una compilación posterior. Son huellas; no se incluyen compilados.
    compilado_antes = arbol(dist)
    resultado["spa_compilada"] = {"archivos": compilado_antes}
    with ExitStack() as pila:
        raiz = Path(pila.enter_context(tempfile.TemporaryDirectory(prefix="f94-")))
        datos = raiz / "api"
        entorno_api = r9.entorno_minimo(
            F94_RAIZ=str(datos), F94_ESTADO="normal" if escenario == "cuota" else escenario,
            API_PUBLICA_CLAVES=f"f94:sha256:{huella}",
            F9_FICHAS_POR_MINUTO=str(resultado["fichas_por_minuto"]), F9_FICHAS_POR_MINUTO_IP="100000",
            DATABASE_URL="sqlite:///" + (raiz / "sin-uso.sqlite").as_posix(),
            **{f"DIRECTORIO_{n}": str(raiz / "inutilizado" / n.lower()) for n in (
                "PRONOSTICOS_EXPERIMENTALES", "OPERACION", "LABORATORIO_MODELOS", "CARTERAS_MODELOS",
                "RESULTADOS_MODELOS", "PREDICCIONES_MODELOS", "AUTOMATIZACION", "SIMULACIONES")})
        pila.enter_context(r9.uvicorn("api", "tests.fase94_api_sintetica:app", p_api, entorno_api, registros))
        antes = arbol(datos)
        entorno_pasarela = r9.entorno_minimo(
            PASARELA_API_URL=f"http://127.0.0.1:{p_api}", PASARELA_CLAVE_API=clave,
            PASARELA_HOSTS=f"127.0.0.1:{p_pasarela},localhost:{p_pasarela}",
            PASARELA_ORIGENES=f"http://127.0.0.1:{p_pasarela},http://localhost:{p_pasarela}",
            PASARELA_DIST=str(dist), PASARELA_CONSOLA_LOCAL="http://127.0.0.1:8000/")
        pila.enter_context(r9.uvicorn("pasarela", "app.pasarela.aplicacion:app", p_pasarela, entorno_pasarela, registros))
        resultado["controles_directos"] = (r9.controles_directos(p_pasarela, CONTROLES) if escenario == "normal" else [])
        cuerpos = raiz / "respuestas"
        cuerpos.mkdir()
        argumentos = [node, str(FRONTEND / "e2e" / "guardados.mjs"), "--base", f"http://127.0.0.1:{p_pasarela}",
                      "--escenario", escenario, "--salida", str(salida / "navegador"), "--anchos", anchos,
                      "--cuerpos", str(cuerpos)]
        if navegador:
            argumentos += ["--navegador", navegador]
        with (registros / "navegador.log").open("wb") as log:
            codigo = subprocess.run(argumentos, cwd=FRONTEND, env=r9.entorno_minimo(), stdout=log,
                                    stderr=subprocess.STDOUT, timeout=900).returncode
        resultado["codigo_navegador"] = codigo
        despues = arbol(datos)
        resultado["almacenes"] = {"archivos_antes": len(antes), "archivos_despues": len(despues),
                                  "intactos": antes == despues, "antes": antes, "despues": despues}
        resultado["respuestas_al_navegador_inspeccionadas"] = sum(1 for _ in cuerpos.iterdir())
        resultado["canario"] = {"respuestas_al_navegador": r9.buscar_canario(cuerpos, {"clave": clave, "huella": huella})}
        resultado["almacenes_ajenos_creados"] = (raiz / "inutilizado").exists()
    canarios = {"clave": clave, "huella": huella}
    resultado["canario"].update({"registros": r9.buscar_canario(registros, canarios),
                                 "navegador": r9.buscar_canario(salida / "navegador", canarios),
                                 "dist": r9.buscar_canario(dist, canarios)})
    resultado["canario_encontrado"] = any(v for grupo in resultado["canario"].values() for v in grupo.values())
    fallos = []
    for caso in resultado["controles_directos"]:
        estado, cod = ESPERADOS[caso["caso"]]
        if caso["estado"] != estado or caso["codigo"] != cod:
            fallos.append(caso["caso"])
        if caso["caso"] in ("modelos", "carteras", "resultados") and (
                caso["cabeceras"].get("cache-control") != "no-store" or not caso["cabeceras"].get("x-request-id")):
            fallos.append(caso["caso"] + "_cabeceras")
    resultado["controles_fallidos"] = fallos
    resultado["spa_compilada"]["intacta_durante_recorrido"] = arbol(dist) == compilado_antes
    resultado["ok"] = (codigo == 0 and not fallos and not resultado["canario_encontrado"] and antes == despues
                       and not resultado["almacenes_ajenos_creados"]
                       and resultado["spa_compilada"]["intacta_durante_recorrido"])
    (salida / "recorrido.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if resultado["ok"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--escenario", choices=ESCENARIOS, default="normal")
    parser.add_argument("--anchos", default="360,390,1280")
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--navegador", help="Ejecutable externo Chromium/Brave ya instalado; solo cambia el ensayo")
    args = parser.parse_args(argv)
    return ejecutar(args.escenario, args.salida.resolve(), anchos=args.anchos, node=args.node, navegador=args.navegador)


if __name__ == "__main__":
    raise SystemExit(main())
