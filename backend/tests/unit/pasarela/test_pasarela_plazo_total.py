"""F9-LIM-01 (auditoria de la v1): el plazo total de `consultar` cubre conexion, envio, estado y
cabeceras, cuerpo y EOF; cada operacion de socket espera como mucho el menor entre el tiempo por
operacion y lo que queda del plazo. Al vencer: 504 `api_sin_respuesta`, a tiempo y con la conexion
cerrada, y el hueco de concurrencia se libera solo cuando la consulta ha terminado.

Plazos cortos sobre un servidor HTTP sintetico en loopback. `MARGEN` cubre la planificacion del
sistema (temporizadores de Windows incluidos); en la v1 estos mismos casos superaban el plazo en
0,35 s o mas, o devolvian 200, asi que la tolerancia no oculta el fallo."""
from __future__ import annotations

import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import pytest

from app.pasarela import cliente as cl
from app.pasarela.configuracion import Destino

PLAZO = 0.25
MARGEN = 0.25
CUERPO = b'{"estado":"ok","api":"v1"}'
CLAVE = "c" * 40


class ServidorLento:
    """API sintetica que responde segun la ruta y anota cuando el cliente cierra cada conexion."""

    def __init__(self):
        self.recibidas: list[str] = []
        self.cierres: list[float] = []
        servidor = self

        class Manejador(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_):
                pass

            def cerrada(self) -> bool:
                """El cliente cerro: el socket es legible y no hay datos (EOF o RST)."""
                legible, _, _ = select.select([self.connection], [], [], 0)
                if not legible:
                    return False
                try:
                    return self.connection.recv(1, socket.MSG_PEEK) == b""
                except OSError:
                    return True

            def esperar(self, segundos: float) -> bool:
                """Espera `segundos` vigilando el cierre; True (y lo anota) si el cliente cerro."""
                fin = time.monotonic() + segundos
                while time.monotonic() < fin:
                    if self.cerrada():
                        servidor.cierres.append(time.monotonic())
                        return True
                    time.sleep(0.005)
                return False

            def enviar(self, datos: bytes) -> bool:
                try:
                    self.wfile.write(datos)
                    self.wfile.flush()
                    return True
                except OSError:
                    servidor.cierres.append(time.monotonic())
                    return False

            def do_GET(self):  # noqa: N802 - nombre de http.server
                servidor.recibidas.append(self.path)
                getattr(self, "responder_" + self.path.strip("/").replace("-", "_"))()

            def responder_cabeceras_lentas(self):  # cada fragmento llega antes del tiempo por operacion
                fragmentos = [b"HTTP/1.1 200 OK\r\n", b"Content-Type: application/json\r\n",
                              *(b"X-Relleno-%d: x\r\n" % i for i in range(8))]
                for fragmento in fragmentos:
                    if not self.enviar(fragmento) or self.esperar(0.1):
                        return
                self.enviar(b"Content-Length: %d\r\n\r\n%s" % (len(CUERPO), CUERPO))

            def responder_eof_lento(self):  # HTTP/1.0 sin Content-Length: el EOF delimita el cuerpo
                self.enviar(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n" + CUERPO)
                self.esperar(1.0)
                self.close_connection = True

            def responder_cuerpo_lento(self):  # cabeceras a tiempo; un byte del cuerpo cada 0,6 s
                self.enviar(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n")
                for _ in range(20):
                    if self.esperar(0.6) or not self.enviar(b" "):
                        return

            def responder_silencio(self):  # nada durante 1 s
                self.esperar(1.0)

            def responder_rapida(self):
                self.enviar(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nX-Request-ID: " + b"a" * 32
                            + b"\r\nSet-Cookie: no=reenviar\r\nContent-Length: %d\r\n\r\n%s" % (len(CUERPO), CUERPO))

            def responder_grande(self):  # como la API real: `Connection: close`; espera el cierre del cliente
                cuerpo = b"x" * 5000
                self.enviar(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n"
                            b"Content-Length: %d\r\n\r\n%s" % (len(cuerpo) * 2, cuerpo))
                self.esperar(1.0)

        self._servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self._servidor.daemon_threads = True
        self.destino = Destino("127.0.0.1", self._servidor.server_address[1])
        self._hilo = threading.Thread(target=self._servidor.serve_forever, daemon=True)
        self._hilo.start()

    def cerrar(self):
        self._servidor.shutdown()
        self._servidor.server_close()
        self._hilo.join(timeout=5)


@pytest.fixture
def lento():
    s = ServidorLento()
    try:
        yield s
    finally:
        s.cerrar()


def _vence(destino, ruta, *, tiempo=1.0, tiempo_total=PLAZO) -> float:
    """Ejecuta la consulta, exige 504 `api_sin_respuesta` y devuelve los segundos transcurridos."""
    inicio = time.monotonic()
    with pytest.raises(cl.FalloDeDestino) as fallo:
        cl.consultar(destino, ruta, CLAVE, tiempo=tiempo, tiempo_total=tiempo_total)
    transcurrido = time.monotonic() - inicio
    assert (fallo.value.estado, fallo.value.codigo) == (504, "api_sin_respuesta")
    return transcurrido


def _cierre_a_tiempo(servidor: ServidorLento, inicio: float) -> None:
    limite = time.monotonic() + 1.0
    while not servidor.cierres and time.monotonic() < limite:
        time.sleep(0.01)
    assert servidor.cierres and servidor.cierres[0] - inicio < PLAZO + MARGEN, "la conexion no se cerro a tiempo"


def test_cabeceras_por_fragmentos_respetan_el_plazo_total(lento):
    inicio = time.monotonic()
    assert _vence(lento.destino, "/cabeceras-lentas") < PLAZO + MARGEN
    _cierre_a_tiempo(lento, inicio)


def test_cuerpo_completo_con_eof_tardio_no_se_acepta_fuera_de_plazo(lento):
    # El tiempo por operacion (2 s) supera el retraso del cierre (1 s): la v1 aceptaba un 200 tardio.
    inicio = time.monotonic()
    assert _vence(lento.destino, "/eof-lento", tiempo=2.0) < PLAZO + MARGEN
    _cierre_a_tiempo(lento, inicio)


def test_cuerpo_por_goteo_respeta_el_plazo_total(lento):
    inicio = time.monotonic()
    assert _vence(lento.destino, "/cuerpo-lento") < PLAZO + MARGEN
    _cierre_a_tiempo(lento, inicio)


def test_plazo_agotado_antes_de_conectar_no_envia_la_consulta(lento):
    assert _vence(lento.destino, "/rapida", tiempo_total=0) < MARGEN
    time.sleep(0.1)
    assert lento.recibidas == []


def test_respuesta_rapida_normal_sin_cambios(lento):
    inicio = time.monotonic()
    r = cl.consultar(lento.destino, "/rapida", CLAVE, tiempo=1.0, tiempo_total=PLAZO)
    assert time.monotonic() - inicio < PLAZO
    assert (r.estado, r.cuerpo) == (200, CUERPO)
    assert r.cabeceras == {"content-type": "application/json", "x-request-id": "a" * 32}


def test_tiempo_por_operacion_se_conserva_con_plazo_total_holgado(lento):
    transcurrido = _vence(lento.destino, "/silencio", tiempo=0.2, tiempo_total=5)
    assert 0.15 < transcurrido < 0.2 + MARGEN


def test_limite_de_tamano_se_conserva_y_cierra_la_conexion(lento):
    """Con `Connection: close` la respuesta es duena del socket: una salida por error tambien lo cierra."""
    inicio = time.monotonic()
    with pytest.raises(cl.FalloDeDestino) as fallo:
        cl.consultar(lento.destino, "/grande", CLAVE, tiempo=1.0, tiempo_total=PLAZO, maximo=1000)
    assert (fallo.value.estado, fallo.value.codigo) == (502, "respuesta_demasiado_grande")
    _cierre_a_tiempo(lento, inicio)


def test_huecos_de_concurrencia_se_recuperan_al_vencer_el_plazo(lento):
    """Cuatro consultas lentas con dos huecos: dos tandas que vencen a su plazo. El hueco no se
    libera antes de que termine la consulta y despues una consulta normal funciona."""
    activas, maximo, estado = 0, 0, threading.Lock()

    def consultar_(destino, ruta, clave):
        nonlocal activas, maximo
        with estado:
            activas += 1
            maximo = max(maximo, activas)
        try:
            return cl.consultar(destino, ruta, clave, tiempo=1.0, tiempo_total=PLAZO)
        finally:
            with estado:
                activas -= 1

    cliente = cl.ClienteDeLaApi(lento.destino, concurrencia=2, espera=2.0, consultar_=consultar_)
    resultados: list[object] = []

    async def una(ruta):
        try:
            resultados.append(await cliente.get(ruta, CLAVE))
        except cl.FalloDeDestino as fallo:
            resultados.append((fallo.estado, fallo.codigo))

    async def principal():
        inicio = time.monotonic()
        async with anyio.create_task_group() as grupo:
            for _ in range(4):
                grupo.start_soon(una, "/cabeceras-lentas")
        transcurrido = time.monotonic() - inicio
        await una("/rapida")
        return transcurrido

    transcurrido = anyio.run(principal)
    assert resultados[:4] == [(504, "api_sin_respuesta")] * 4
    assert getattr(resultados[4], "estado", None) == 200
    assert maximo == 2 and activas == 0
    assert transcurrido < 2 * PLAZO + 2 * MARGEN
