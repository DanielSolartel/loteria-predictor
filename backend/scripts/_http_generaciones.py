"""Cliente HTTP local para las consultas selladas, sin dependencias de pruebas.

Uvicorn sirve la misma aplicacion en este proceso para conservar el registro
DAT-01 de aperturas de archivos. El socket reservado solo escucha en loopback.
"""
from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from urllib.parse import urlsplit


class ConsultaLocalNoValida(RuntimeError):
    pass


class ClienteLocal:
    def __init__(self, app, *, espera: float = 30, arranque: float = 10):
        self.app, self.espera, self.arranque = app, espera, arranque
        self.socket = self.servidor = self.hilo = None
        self.puerto = None
        self.error = None

    def __enter__(self):
        from uvicorn import Config, Server

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind(("127.0.0.1", 0))
            self.socket.listen(16)
            self.socket.setblocking(False)
            self.puerto = self.socket.getsockname()[1]
            conf = Config(self.app, host="127.0.0.1", port=self.puerto,
                interface="asgi3", loop="asyncio", http="h11", ws="none", lifespan="off",
                log_config=None, log_level="critical", access_log=False, proxy_headers=False,
                server_header=False, date_header=False, timeout_keep_alive=1, workers=1)
            self.servidor = Server(conf)

            def servir():
                try:
                    self.servidor.run(sockets=[self.socket])
                except BaseException as error:
                    self.error = type(error).__name__

            self.hilo = threading.Thread(target=servir, name="consulta-generacion-local", daemon=True)
            self.hilo.start()
            fin = time.monotonic() + self.arranque
            while not self.servidor.started:
                if not self.hilo.is_alive() or time.monotonic() >= fin:
                    raise ConsultaLocalNoValida("servidor_de_consultas_no_iniciado")
                time.sleep(0.01)
            return self
        except BaseException:
            self.close()
            raise

    def get(self, ruta: str, clave: str) -> tuple[int, object]:
        if not isinstance(ruta, str):
            raise ConsultaLocalNoValida("ruta_de_consulta_no_local")
        p = urlsplit(ruta)
        if (not isinstance(ruta, str) or not ruta.startswith("/api/v1/") or p.scheme or p.netloc
                or p.fragment or "\r" in ruta or "\n" in ruta or self.puerto is None or self.socket is None):
            raise ConsultaLocalNoValida("ruta_de_consulta_no_local")
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=self.espera)
        try:
            c.request("GET", ruta, headers={"X-API-Key": clave, "Connection": "close"})
            r = c.getresponse()
            b = r.read(16 * 1024 * 1024 + 1)
            if len(b) > 16 * 1024 * 1024:
                raise ConsultaLocalNoValida("respuesta_de_consulta_excesiva")
            try:
                return r.status, json.loads(b)
            except (ValueError, UnicodeError):
                return r.status, None
        finally:
            c.close()

    def close(self):
        if self.servidor is not None:
            self.servidor.should_exit = True
        if self.hilo is not None and self.hilo.ident is not None:
            self.hilo.join(5)
            if self.hilo.is_alive():
                self.servidor.force_exit = True
                self.hilo.join(2)
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        if self.hilo is not None and self.hilo.is_alive():
            raise ConsultaLocalNoValida("servidor_de_consultas_no_detenido")

    def __exit__(self, *args):
        self.close()
