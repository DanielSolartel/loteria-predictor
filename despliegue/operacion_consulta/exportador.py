"""Exportador de solo lectura en 127.0.0.1, sin rutas en la API ni en el proxy."""
from __future__ import annotations

import json
import socket
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .estado import Almacen
from .modelo import Rechazo
from .observabilidad import metricas


def crear_servidor(almacen: Almacen, puerto: int, *, host: str = "127.0.0.1", ahora=None):
    if host != "127.0.0.1" or type(puerto) is not int or not 0 <= puerto <= 65535:
        raise Rechazo("exportador_solo_loopback")
    ahora = ahora or (lambda: datetime.now(timezone.utc))

    class Servidor(ThreadingHTTPServer):
        daemon_threads = True
        address_family = socket.AF_INET
        request_queue_size = 16

        def __init__(self, *args):
            self.plazas = threading.BoundedSemaphore(16)
            super().__init__(*args)

        def process_request(self, request, client_address):
            if not self.plazas.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except BaseException:
                self.plazas.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.plazas.release()

    class Manejador(BaseHTTPRequestHandler):
        server_version = "ConsultaInterna"
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(2)

        def log_message(self, *args):
            pass

        def respuesta(self, codigo, datos, tipo):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            if self.path not in ("/metricas", "/salud"):
                self.respuesta(404, b'{"error":"ruta"}\n', "application/json")
                return
            try:
                texto, sano = metricas(almacen.leer("observacion.json"), ahora())
                estado = "verificado" if sano else "sin_verificar"
            except (ValueError, OSError, KeyError, TypeError, OverflowError):
                texto, sano, estado = 'loteria_consulta_verificada 0\nloteria_alerta{tipo="observacion_ausente"} 1\n', False, "sin_observacion"
            if self.path == "/metricas":
                self.respuesta(200, texto.encode(), "text/plain; version=0.0.4; charset=utf-8")
            else:
                self.respuesta(200 if sano else 503, (json.dumps({"estado": estado}) + "\n").encode(), "application/json")

        def do_POST(self):
            self.respuesta(405, b'{"error":"metodo"}\n', "application/json")

    return Servidor((host, puerto), Manejador)
