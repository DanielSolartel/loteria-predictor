"""Cliente HTTP de `/api/v1` para la pasarela (Fase 9.1), con `http.client`.

La consulta bloqueante se ejecuta en un hilo (`anyio.to_thread`), nunca en el
bucle asincrono. Limites:

- concurrencia: `CONCURRENCIA` consultas a la vez; una solicitud que no obtiene
  hueco en `ESPERA_DE_HUECO` segundos recibe 503 `pasarela_ocupada`;
- tiempo: `TIEMPO_TOTAL` segundos para toda la consulta (conexion, envio, estado
  y cabeceras, cuerpo y EOF) y, dentro de ese plazo, `TIEMPO_POR_OPERACION` por
  operacion de socket: cada espera usa el menor de los dos. Al superarlos, 504
  `api_sin_respuesta` en cuanto vence la espera en curso; la consulta termina
  ahi (no queda trabajo bloqueado) y solo entonces se libera su hueco;
- tamano: `MAXIMO_BYTES` de cuerpo; al superarlo, 502 `respuesta_demasiado_grande`.

Cada consulta abre su propia conexion y la cierra al terminar. No sigue
redirecciones (`http.client` no lo hace) ni reenvia cabeceras del navegador.
"""
from __future__ import annotations

import dataclasses
import http.client
import socket
import time

import anyio

from app.pasarela.configuracion import Destino

CONCURRENCIA = 4
ESPERA_DE_HUECO = 2.0
TIEMPO_POR_OPERACION = 10.0
TIEMPO_TOTAL = 15.0
MAXIMO_BYTES = 4 * 1024 * 1024
_TROZO = 64 * 1024
_CABECERAS = ("content-type", "retry-after", "x-request-id", "x-ratelimit-limit", "x-ratelimit-remaining")


@dataclasses.dataclass(frozen=True)
class RespuestaDeLaApi:
    estado: int
    cabeceras: dict[str, str]
    cuerpo: bytes


class FalloDeDestino(Exception):
    """Fallo al consultar la API; `codigo` es publico y no contiene detalles."""

    def __init__(self, estado: int, codigo: str):
        super().__init__(codigo)
        self.estado, self.codigo = estado, codigo


class _SocketConPlazo(socket.socket):
    """Socket cuyas esperas (conexion, envio y cada lectura) duran como mucho el menor entre el
    tiempo por operacion y lo que queda del plazo total; con el plazo agotado no espera nada."""

    def plazos(self, tiempo: float, limite: float) -> None:
        self._tiempo, self._limite = tiempo, limite

    def _ajustar(self) -> None:
        restante = self._limite - time.monotonic()
        if restante <= 0:
            raise TimeoutError("plazo total agotado")
        self.settimeout(min(self._tiempo, restante))

    def connect(self, direccion) -> None:
        self._ajustar()
        super().connect(direccion)

    def sendall(self, datos, *args) -> None:  # el plazo cubre el envio completo
        self._ajustar()
        super().sendall(datos, *args)

    def recv(self, *args):
        self._ajustar()
        return super().recv(*args)

    def recv_into(self, *args):  # lo usa el lector de la respuesta en cada lectura del socket
        self._ajustar()
        return super().recv_into(*args)


class _ConexionConPlazo(http.client.HTTPConnection):
    """`HTTPConnection` sobre `_SocketConPlazo`; el destino es una IP literal (sin DNS)."""

    def __init__(self, destino: Destino, tiempo: float, limite: float):
        super().__init__(destino.host, destino.puerto, timeout=tiempo)
        self._plazos = tiempo, limite

    def connect(self) -> None:
        familia, tipo, protocolo, _, direccion = socket.getaddrinfo(
            self.host, self.port, 0, socket.SOCK_STREAM, 0, socket.AI_NUMERICHOST)[0]
        conector = _SocketConPlazo(familia, tipo, protocolo)
        try:
            conector.plazos(*self._plazos)
            conector.connect(direccion)
            conector.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except BaseException:
            conector.close()
            raise
        self.sock = conector


def consultar(destino: Destino, ruta: str, clave: str, *, tiempo: float = TIEMPO_POR_OPERACION,
              tiempo_total: float = TIEMPO_TOTAL, maximo: int = MAXIMO_BYTES) -> RespuestaDeLaApi:
    """GET bloqueante a `destino` + `ruta` (ya saneada) con la clave del servidor."""
    limite = time.monotonic() + tiempo_total
    conexion = _ConexionConPlazo(destino, tiempo, limite)

    def a_tiempo() -> None:  # tambien tras lo que llega del bufer sin esperar al socket
        if time.monotonic() > limite:
            raise FalloDeDestino(504, "api_sin_respuesta")

    respuesta = None
    try:
        conexion.request("GET", ruta, headers={"Accept": "application/json", "X-API-Key": clave,
                                               "User-Agent": "loteria-pasarela/9.1", "Connection": "close"})
        respuesta = conexion.getresponse()
        a_tiempo()
        partes, total = [], 0
        while trozo := respuesta.read1(_TROZO):
            total += len(trozo)
            if total > maximo:
                raise FalloDeDestino(502, "respuesta_demasiado_grande")
            a_tiempo()
            partes.append(trozo)
        a_tiempo()  # el EOF que cierra el cuerpo tambien debe llegar dentro del plazo
        cabeceras = {k: v for k in _CABECERAS if (v := respuesta.getheader(k)) is not None}
        return RespuestaDeLaApi(respuesta.status, cabeceras, b"".join(partes))
    except TimeoutError as error:
        raise FalloDeDestino(504, "api_sin_respuesta") from error
    except (OSError, http.client.HTTPException) as error:
        raise FalloDeDestino(503, "api_no_disponible") from error
    finally:
        # Con `Connection: close` (o HTTP/1.0) `http.client` cede el socket a la respuesta:
        # se cierra tambien, para no dejarlo abierto en una salida por error o por plazo.
        if respuesta is not None:
            respuesta.close()
        conexion.close()


class ClienteDeLaApi:
    """Consultas concurrentes acotadas; una instancia por aplicacion."""

    def __init__(self, destino: Destino, *, concurrencia: int = CONCURRENCIA, espera: float = ESPERA_DE_HUECO,
                 consultar_=consultar):
        self._destino, self._espera, self._consultar = destino, espera, consultar_
        self._huecos = anyio.Semaphore(concurrencia)
        self.concurrencia = concurrencia

    async def get(self, ruta: str, clave: str) -> RespuestaDeLaApi:
        try:
            with anyio.fail_after(self._espera):
                await self._huecos.acquire()
        except TimeoutError as error:
            raise FalloDeDestino(503, "pasarela_ocupada") from error
        try:
            return await anyio.to_thread.run_sync(lambda: self._consultar(self._destino, ruta, clave))
        finally:
            self._huecos.release()
