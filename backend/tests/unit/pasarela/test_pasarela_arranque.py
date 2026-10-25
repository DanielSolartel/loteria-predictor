"""Fase 9.1, pasarela: el arranque documentado en `docs/fase9_frontend.md`, como
proceso Uvicorn real (solo cambia el puerto y, para provocar un fallo, la
aplicacion), frente a una API falsa local. Sin registro de acceso, sin
`X-Forwarded-For`, sin canarios ni trazas en el registro; y todos los ejemplos
de arranque de la pasarela y de la API con sus dos opciones."""
from __future__ import annotations

import http.client
import json
import os
import re
import shlex
import socket

from tests.unit.api_publica import fixtures_api_publica as fa
from tests.unit.pasarela import fixtures_pasarela as fp

GUIA = fa.BACKEND / "docs" / "fase9_frontend.md"
OBJETIVO = "app.pasarela.aplicacion:app"
COMANDO = re.compile(r"(?:python -m )?uvicorn app\.pasarela\.aplicacion:app[^`\n]*")
OPCIONES = {"--no-access-log", "--no-proxy-headers"}
SONDA = '''import os

from app.pasarela import aplicacion


def fallar(*_):
    raise RuntimeError("F9_SONDA_INTERNA=" + os.environ["PASARELA_CLAVE_API"])


aplicacion.rutas.buscar = fallar
app = aplicacion.app
'''


def arranque_documentado(puerto: int, objetivo: str = OBJETIVO) -> list[str]:
    linea = next(x for x in GUIA.read_text(encoding="utf-8").splitlines() if "Arrancar la pasarela" in x)
    argumentos = shlex.split(COMANDO.search(linea).group(0))
    argumentos = argumentos[argumentos.index(OBJETIVO):]
    argumentos[0] = objetivo
    argumentos[argumentos.index("--port") + 1] = str(puerto)
    return argumentos


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _entorno(raiz, destino, puerto: int, clave: str) -> dict[str, str]:
    entorno = {k: v for k, v in os.environ.items() if not k.startswith(("UVICORN_", "PASARELA_", "API_PUBLICA_"))
               and k != "FORWARDED_ALLOW_IPS"}
    entorno.update({"PASARELA_CLAVE_API": clave, "PASARELA_API_URL": destino.url,
                    "PASARELA_HOSTS": f"127.0.0.1:{puerto}", "PASARELA_ORIGENES": f"http://127.0.0.1:{puerto}",
                    "PASARELA_DIST": str(fp.dist(raiz)), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"})
    return entorno


def _get(puerto: int, ruta: str, cabeceras: dict[str, str] | None = None) -> tuple[int, dict, bytes]:
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
    try:
        c.putrequest("GET", ruta, skip_host=True)
        for k, v in {"Host": f"127.0.0.1:{puerto}", **(cabeceras or {})}.items():
            c.putheader(k, v)
        c.endheaders()
        r = c.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    finally:
        c.close()


def test_proceso_real_sin_registro_de_acceso_ni_canarios(tmp_path):
    clave = fp.clave_sintetica()
    (tmp_path / "sonda_f9.py").write_text(SONDA, encoding="utf-8")
    with fp.destino_falso() as d:
        puerto = _puerto_libre()
        registro = tmp_path / "pasarela.log"
        with fa.proceso_uvicorn(arranque_documentado(puerto), _entorno(tmp_path / "a", d.destino, puerto, clave),
                                registro):
            en_url = _get(puerto, f"/api/v1/juegos?api_key={clave}")
            salud = _get(puerto, "/api/v1/salud", {"X-Forwarded-For": "10.0.0.9"})  # sigue siendo el socket local
            rebinding = _get(puerto, "/api/v1/salud", {"Host": "evil.example"})
            spa = _get(puerto, "/juegos/BALOTO")
        puerto_sonda = _puerto_libre()
        registro_sonda = tmp_path / "sonda.log"
        with fa.proceso_uvicorn(arranque_documentado(puerto_sonda, "sonda_f9:app"),
                                _entorno(tmp_path / "b", d.destino, puerto_sonda, clave), registro_sonda,
                                app_dir=tmp_path):
            fallo = _get(puerto_sonda, "/api/v1/juegos")
        recibidas = [x.ruta for x in d.recibidas]
    texto = registro.read_text(encoding="utf-8", errors="replace") + registro_sonda.read_text(encoding="utf-8",
                                                                                              errors="replace")
    cuerpo_fallo = json.loads(fallo[2])["error"]
    propias = [x for x in texto.splitlines() if "app.pasarela pasarela GET" in x]
    criterios = {
        "clave_en_url_rechazada_sin_reenvio": en_url[0] == 422 and recibidas == ["/api/v1/salud"],
        "x_forwarded_for_ignorado": salud[0] == 200,
        "rebinding_rechazado": rebinding[0] == 403,
        "spa_servida": spa[0] == 200 and b"<div id=" in spa[2],
        "fallo_500_sanitizado": fallo[0] == 500 and cuerpo_fallo["codigo"] == "error_interno",
        "fallo_id_coherente": fallo[1].get("x-request-id") == cuerpo_fallo["solicitud"],
        "fallo_no_store": fallo[1].get("cache-control") == "no-store",
        "sin_clave": clave not in texto, "sin_consulta": "api_key" not in texto,
        "sin_registro_de_acceso": '"GET /' not in texto, "sin_traza": "Traceback" not in texto,
        "sin_mensaje": "F9_SONDA_INTERNA" not in texto, "sin_error_asgi": "Exception in ASGI application" not in texto,
        "registro_propio": len(propias) >= 5 and any(" /api/v1/salud 200 " in x for x in propias),
        "error_propio_sin_mensaje": f"error_interno=RuntimeError solicitud={cuerpo_fallo['solicitud']}" in texto,
    }
    incumplidos = sorted(k for k, v in criterios.items() if not v)
    assert not incumplidos, "incumplidos: " + ", ".join(incumplidos)


def test_todos_los_ejemplos_de_arranque_usan_las_opciones_soportadas():
    raiz = fa.BACKEND.parent
    documentos = [raiz / "README.md", raiz / "ROADMAP.md", raiz / "ARCHITECTURE.md", fa.BACKEND / ".env.example",
                  fa.BACKEND / "pasarela.ejemplo.env", *sorted((fa.BACKEND / "docs").glob("fase9*.md")),
                  *sorted((fa.BACKEND / "app" / "pasarela").glob("*.py")), raiz / "frontend" / "README.md"]
    vistos: dict[str, list[bool]] = {}
    for documento in documentos:
        texto = documento.read_text(encoding="utf-8")
        for comando in COMANDO.findall(texto) + fa.COMANDO.findall(texto):
            vistos.setdefault(documento.name, []).append(OPCIONES <= set(comando.split()))
    assert {"README.md", "ARCHITECTURE.md", "fase9_frontend.md", "fase9_windows.md", "aplicacion.py",
            "pasarela.ejemplo.env"} <= set(vistos)
    assert all(all(v) for v in vistos.values()), vistos
    assert OPCIONES <= set(arranque_documentado(8020))
