"""Fase 10 (E10.2, v2): servidor HTTPS LOCAL de ensayo con certificado de cliente obligatorio (biblioteca estandar
y `cryptography`, ya en requirements.txt). Lo arranca `ensayo_brave_mtls_e102.ps1`; no es la consulta privada ni
toca datos.

- Escucha solo en 127.0.0.1 y exige un certificado de cliente de la CA de prueba (`--ca`). Solo cuenta como
  verificado el CN esperado (`--cn-esperado`); otro CN recibe 403 y queda anotado.
- La contrasena del PFX del servidor llega por la entrada estandar (una linea) y no se guarda.
- **El resultado se escribe de forma ATOMICA (temporal + fsync + os.replace) ANTES de responder** a la peticion
  valida: sobrevive a un fin forzado posterior. El archivo refleja siempre el ultimo estado conocido:
  `escuchando`, `verificado`, `sin_resultado`, `arranque_fallido`.
- Cierre COOPERATIVO: termina al aparecer el archivo `--parar` (o SIGTERM/SIGINT) o al vencer `--plazo`;
  confirma el cierre en el resultado (`fin`). El fin forzado es solo el ultimo recurso del guion.
- Cada conexion tiene su propio plazo de handshake (`--plazo-handshake`) en un hilo: un cliente que no completa
  TLS no bloquea a los demas. Los handshakes fallidos (sin certificado, otra CA) se cuentan.

Codigos de salida: 0 verificado; 2 sin resultado valido al terminar (plazo o parada); 3 arranque fallido.

Uso: python servidor_mtls_e102.py --pfx <servidor.pfx> --ca <ca.pem> --puerto <n> --resultado <json>
     [--cn-esperado invitado-brave] [--plazo 300] [--plazo-handshake 10] [--parar <archivo>]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import signal
import socket
import ssl
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Estado:
    """Estado del ensayo, persistido atomicamente en cada cambio relevante."""

    def __init__(self, ruta: Path, cn_esperado: str):
        self.ruta, self.cerrojo = ruta, threading.RLock()
        self.datos = {"version": 2, "estado": "iniciando", "cn_esperado": cn_esperado, "cn": [], "solicitudes": [],
                      "rechazos_cn": [], "handshakes_fallidos": 0, "inicio": time.time(), "fin": None}

    def guardar(self, **cambios) -> None:
        with self.cerrojo:
            self.datos.update(cambios)
            texto = json.dumps(self.datos, ensure_ascii=False, indent=1).encode("utf-8")
            descriptor, temporal = tempfile.mkstemp(prefix=".resultado-", dir=str(self.ruta.parent))
            try:
                with os.fdopen(descriptor, "wb") as f:
                    f.write(texto)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporal, self.ruta)
            except BaseException:
                if os.path.exists(temporal):
                    os.remove(temporal)
                raise

    def anotar(self, clave: str, valor) -> None:
        with self.cerrojo:
            self.datos[clave].append(valor)
            self.guardar()

    @property
    def verificado(self) -> bool:
        return bool(self.datos["cn"])


def contexto(pfx: Path, contrasena: bytes, ca: Path) -> ssl.SSLContext:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    clave, certificado, _ = pkcs12.load_key_and_certificates(pfx.read_bytes(), contrasena)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(cafile=str(ca))
    # load_cert_chain solo acepta archivos: PEM temporal privado, borrado en cuanto se carga.
    descriptor, ruta = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(descriptor, "wb") as f:
            f.write(certificado.public_bytes(serialization.Encoding.PEM))
            f.write(clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))
        ctx.load_cert_chain(ruta)
    finally:
        os.remove(ruta)
    return ctx


def construir_servidor(puerto: int, ctx: ssl.SSLContext, estado: Estado, plazo_handshake: float):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):  # noqa: N802
            sujeto = dict(x[0] for x in self.connection.getpeercert().get("subject", ()))
            cn = sujeto.get("commonName", "")
            if cn != estado.datos["cn_esperado"]:
                estado.anotar("rechazos_cn", cn[:64])
                cuerpo = b"Certificado de otro titular: no se acepta para este ensayo.\n"
                codigo = 403
            else:
                with estado.cerrojo:
                    estado.datos["solicitudes"].append({"cn": cn, "ruta": self.path[:64], "instante": time.time()})
                    estado.guardar(estado="verificado", cn=sorted(set(estado.datos["cn"]) | {cn}))  # ANTES de responder
                cuerpo = (f"<!doctype html><meta charset='utf-8'><title>Ensayo mTLS E10.2</title>"
                          f"<h1>Certificado de cliente verificado</h1><p>CN: <b>{html.escape(cn)}</b></p>"
                          f"<p>Puede cerrar esta ventana; PowerShell continua solo.</p>").encode("utf-8")
                codigo = 200
            self.send_response(codigo)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(cuerpo)

    class Servidor(ThreadingHTTPServer):
        daemon_threads = True

        def get_request(self):
            conexion, direccion = self.socket.accept()
            conexion.settimeout(plazo_handshake)
            return conexion, direccion

        def finish_request(self, request, client_address):  # en el hilo de la conexion
            try:
                tls = ctx.wrap_socket(request, server_side=True)
            except (ssl.SSLError, OSError):
                with estado.cerrojo:
                    estado.datos["handshakes_fallidos"] += 1
                    estado.guardar()
                return
            try:
                self.RequestHandlerClass(tls, client_address, self)
            finally:
                tls.close()

    return Servidor(("127.0.0.1", puerto), Manejador)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pfx", required=True)
    p.add_argument("--ca", required=True)
    p.add_argument("--puerto", type=int, required=True)
    p.add_argument("--resultado", required=True)
    p.add_argument("--cn-esperado", default="invitado-brave")
    p.add_argument("--plazo", type=float, default=300)
    p.add_argument("--plazo-handshake", type=float, default=10)
    p.add_argument("--parar", default=None)
    a = p.parse_args(argv)
    estado = Estado(Path(a.resultado), a.cn_esperado)
    contrasena = sys.stdin.readline().strip().encode("ascii")
    try:
        servidor = construir_servidor(a.puerto, contexto(Path(a.pfx), contrasena, Path(a.ca)), estado,
                                      a.plazo_handshake)
    except Exception as error:  # PFX, contrasena, CA o puerto: nunca un servidor a medias
        estado.guardar(estado="arranque_fallido", motivo=type(error).__name__, fin=time.time())
        print(f"arranque fallido: {type(error).__name__}", file=sys.stderr, flush=True)
        return 3
    detener = threading.Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(senal, lambda *_: detener.set())
    hilo = threading.Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    hilo.start()
    estado.guardar(estado="escuchando", puerto=a.puerto)
    print(f"escuchando en https://localhost:{a.puerto}/ (plazo {a.plazo:.0f} s)", flush=True)
    limite, motivo = time.monotonic() + a.plazo, "plazo"
    while time.monotonic() < limite:
        if detener.wait(0.2):
            motivo = "senal"
            break
        if a.parar and os.path.exists(a.parar):
            motivo = "parada_cooperativa"
            break
    servidor.shutdown()
    servidor.server_close()
    hilo.join(5)
    verificado = estado.verificado
    estado.guardar(estado="verificado" if verificado else "sin_resultado", fin=time.time(), motivo_fin=motivo)
    return 0 if verificado else 2


if __name__ == "__main__":
    raise SystemExit(main())
