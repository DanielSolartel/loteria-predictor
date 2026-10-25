"""FIXTURES SINTETICAS de la pasarela (Fase 9.1), solo para pruebas.

- `DestinoFalso`: servidor HTTP real en un hilo (127.0.0.1, puerto libre) que
  hace de API: registra cada solicitud recibida (ruta y cabeceras) y responde
  segun el `modo` elegido por la prueba (JSON contractual, lento, grande,
  redireccion, no JSON...). Asi se ejercita `http.client` de verdad.
- `dist(...)`: una SPA compilada minima en un directorio temporal.
- `pasarela(...)`: la aplicacion con una configuracion de prueba y un
  `TestClient` cuyo `Host` y cliente son los locales admitidos.

Las claves son sinteticas y se generan en cada prueba. Sin red externa ni
PostgreSQL; ningun dato es real."""
from __future__ import annotations

import contextlib
import dataclasses
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import anyio
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.pasarela.aplicacion import crear_app
from app.pasarela.configuracion import ConfiguracionPasarela, Destino

HOST = "127.0.0.1:8020"
ORIGEN = "http://127.0.0.1:8020"
LOCAL = ("127.0.0.1", 51000)
INDICE = "<!doctype html><html lang=\"es\"><head><script type=\"module\" src=\"/assets/app-1.js\"></script></head>" \
         "<body><div id=\"raiz\"></div></body></html>"


def clave_sintetica() -> str:
    return "lpk_" + secrets.token_urlsafe(32)


def dist(raiz: Path) -> Path:
    d = raiz / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text(INDICE, encoding="utf-8")
    (d / "assets" / "app-1.js").write_text("console.log('spa');\n", encoding="utf-8")
    (d / "assets" / "app-1.css").write_text("body{margin:0}\n", encoding="utf-8")
    (d / "favicon.svg").write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"/>", encoding="utf-8")
    return d


@dataclasses.dataclass
class Recibida:
    ruta: str
    cabeceras: dict[str, str]


class DestinoFalso:
    """API falsa en un hilo. `modo` decide la respuesta de la siguiente solicitud."""

    def __init__(self):
        self.recibidas: list[Recibida] = []
        self.modo = "ok"
        self.estado = 200
        self.cuerpo: bytes = json.dumps({"api": "v1", "estado": "ok"}).encode()
        self.cabeceras: dict[str, str] = {"Content-Type": "application/json", "X-Request-ID": "a" * 32}
        self.espera = 0.0
        self.abiertas = 0
        self.bloqueo = threading.Event()
        destino = self

        class Manejador(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # sin registro en la salida de las pruebas
                pass

            def do_GET(self):  # noqa: N802 - nombre de http.server
                destino.abiertas += 1
                try:
                    destino.recibidas.append(Recibida(self.path, {k.lower(): v for k, v in self.headers.items()}))
                    destino.responder(self)
                finally:
                    destino.abiertas -= 1

        self._servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self._servidor.daemon_threads = True
        self.puerto = self._servidor.server_address[1]
        self._hilo = threading.Thread(target=self._servidor.serve_forever, daemon=True)
        self._hilo.start()

    @property
    def destino(self) -> Destino:
        return Destino("127.0.0.1", self.puerto)

    def json(self, estado: int, cuerpo, **cabeceras: str) -> None:
        self.modo, self.estado = "ok", estado
        self.cuerpo = json.dumps(cuerpo).encode()
        self.cabeceras = {"Content-Type": "application/json", **cabeceras}

    def responder(self, h: BaseHTTPRequestHandler) -> None:
        if self.modo == "bloquear":
            self.bloqueo.wait(10)
        if self.espera:
            time.sleep(self.espera)
        if self.modo == "cortar":
            h.connection.close()
            return
        if self.modo == "goteo":  # bytes lentos: cada operacion de socket a tiempo, el total no
            h.send_response(200)
            h.send_header("Content-Type", "application/json")
            h.send_header("Content-Length", "64")
            h.end_headers()
            for _ in range(64):
                h.wfile.write(b" ")
                h.wfile.flush()
                time.sleep(0.05)
            return
        h.send_response(self.estado)
        for nombre, valor in self.cabeceras.items():
            h.send_header(nombre, valor)
        h.send_header("Content-Length", str(len(self.cuerpo)))
        h.end_headers()
        h.wfile.write(self.cuerpo)

    def cerrar(self) -> None:
        self.bloqueo.set()
        self._servidor.shutdown()
        self._servidor.server_close()


@contextlib.contextmanager
def destino_falso():
    d = DestinoFalso()
    try:
        yield d
    finally:
        d.cerrar()


def configuracion(destino: Destino, carpeta: Path, clave: str | None = None, **extra) -> ConfiguracionPasarela:
    return ConfiguracionPasarela(**{"destino": destino, "clave": SecretStr(clave if clave is not None else ""),
                                    "hosts": frozenset({HOST, "localhost:8020"}),
                                    "origenes": frozenset({ORIGEN, "http://localhost:8020"}), "dist": carpeta,
                                    **extra})


def cliente(app, *, client=LOCAL, host: str = HOST) -> TestClient:
    return TestClient(app, base_url=f"http://{host}", client=client, raise_server_exceptions=True)


def pasarela(destino: Destino, carpeta: Path, clave: str | None = None, **extra):
    return crear_app(configuracion(destino, carpeta, clave, **extra))


async def _asgi(app, ruta: bytes, metodo: str, cabeceras: list[tuple[str, str]], client, consulta: bytes):
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": metodo, "scheme": "http",
             "path": unquote(ruta.decode("latin-1")), "raw_path": ruta, "query_string": consulta, "root_path": "",
             "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in cabeceras],
             "client": client, "server": ("127.0.0.1", 8020)}
    mensajes: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(mensaje):
        mensajes.append(mensaje)

    await app(scope, receive, send)
    inicio = next(m for m in mensajes if m["type"] == "http.response.start")
    cuerpo = b"".join(m.get("body", b"") for m in mensajes if m["type"] == "http.response.body")
    return inicio["status"], {k.decode(): v.decode() for k, v in inicio["headers"]}, cuerpo


def crudo(app, ruta: bytes, *, metodo: str = "GET", cabeceras: list[tuple[str, str]] | None = None, client=LOCAL,
          consulta: bytes = b""):
    """Solicitud ASGI sin la normalizacion de URL de los clientes HTTP (para rutas ambiguas)."""
    return anyio.run(_asgi, app, ruta, metodo, cabeceras if cabeceras is not None else [("host", HOST)], client,
                     consulta)
