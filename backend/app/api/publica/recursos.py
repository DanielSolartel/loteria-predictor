"""Recursos y frontera de la API publica (Fase 10, E10.2: SEC-04 y SEC-08).

- `costosa`: las consultas de coste 5 (estadisticas y resultados) ocupan un
  hueco de un semaforo acotado (`API_PUBLICA_CONCURRENCIA_COSTOSAS`). El hueco
  se toma y se libera DENTRO del hilo que ejecuta la consulta: si el cliente se
  desconecta, la capacidad no vuelve hasta que el trabajo termina de verdad
  (el `statement_timeout` del rol lector acota lo que dura en la base). Sin
  hueco en `API_PUBLICA_ESPERA_COSTOSAS` segundos: 503 `consultas_ocupadas`
  con `Retry-After`. Con 0 (modo local) no hay limite, como antes.
- `FronteraPrivada`: en el perfil privado solo admite el socket de las IP
  exactas de `API_PUBLICA_CLIENTES` (la pasarela) y un unico `Host` de
  `API_PUBLICA_HOSTS`. No lee `X-Forwarded-For` ni ninguna otra cabecera de
  red: la API sigue arrancando con `--no-proxy-headers`.

Ninguna de las dos cambia rutas, parametros ni respuestas del OpenAPI.
"""
from __future__ import annotations

import functools
import inspect
import json
import threading
import uuid

from fastapi import Request

from app.api.publica.errores import ErrorPublico, registro

_PARAMETRO = "_peticion_de_consulta_costosa"


class LimiteDeCostosas:
    """Semaforo de las consultas de coste 5 de UNA aplicacion (por proceso)."""

    def __init__(self, concurrencia: int, espera: float):
        self.concurrencia, self.espera = concurrencia, espera
        self._semaforo = threading.BoundedSemaphore(concurrencia) if concurrencia else None
        self._cerrojo = threading.Lock()
        self.en_curso = 0
        self.rechazos = 0

    def ejecutar(self, funcion, *args, **kwargs):
        if self._semaforo is None:
            return funcion(*args, **kwargs)
        if not self._semaforo.acquire(timeout=self.espera):
            with self._cerrojo:
                self.rechazos += 1
            raise ErrorPublico(503, "consultas_ocupadas",
                               "Demasiadas consultas costosas en curso; reintente en un momento",
                               {"Retry-After": "1"})
        with self._cerrojo:
            self.en_curso += 1
        try:
            return funcion(*args, **kwargs)
        finally:
            with self._cerrojo:
                self.en_curso -= 1
            self._semaforo.release()


def costosa(funcion):
    """Decorador de un endpoint SINCRONO de coste 5. Anade a la firma un parametro `Request` (FastAPI no lo
    documenta en el OpenAPI) para llegar al semaforo de su propia aplicacion."""
    if inspect.iscoroutinefunction(funcion):
        raise TypeError("costosa solo admite endpoints sincronos (se ejecutan en un hilo)")
    firma = inspect.signature(funcion, eval_str=True)  # anotaciones ya resueltas en el modulo del endpoint

    @functools.wraps(funcion)
    def envoltura(*args, **kwargs):
        peticion: Request = kwargs.pop(_PARAMETRO)
        return peticion.app.state.costosas.ejecutar(funcion, *args, **kwargs)

    extra = inspect.Parameter(_PARAMETRO, inspect.Parameter.KEYWORD_ONLY, annotation=Request)
    envoltura.__signature__ = firma.replace(parameters=[*firma.parameters.values(), extra])
    return envoltura


class FronteraPrivada:
    """Middleware ASGI externo del perfil privado: IP del socket y `Host` exactos; nada mas."""

    def __init__(self, app, *, hosts: frozenset[str], clientes: frozenset[str]):
        if not hosts or not clientes:
            raise ValueError("la frontera privada exige hosts y clientes explicitos")
        self.app, self.hosts, self.clientes = app, hosts, clientes
        self.rechazos = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cliente = (scope.get("client") or ("", 0))[0]
        hosts = [v for k, v in scope.get("headers", ()) if k == b"host"]
        if cliente not in self.clientes:
            return await self._rechazar(send, "cliente_no_permitido", "Origen de red no admitido")
        if len(hosts) != 1 or hosts[0].decode("latin-1").lower() not in self.hosts:
            return await self._rechazar(send, "host_no_permitido", "Host no admitido")
        return await self.app(scope, receive, send)

    async def _rechazar(self, send, codigo: str, mensaje: str) -> None:
        self.rechazos += 1
        solicitud = uuid.uuid4().hex
        registro.warning("api_publica frontera=%s solicitud=%s", codigo, solicitud)
        cuerpo = json.dumps({"error": {"codigo": codigo, "mensaje": mensaje, "solicitud": solicitud}}).encode()
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(cuerpo)).encode()),
                                (b"x-request-id", solicitud.encode()), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": cuerpo})
