"""Monitoreo basico en memoria de ESTE proceso: solicitudes por ruta y clase de
estado, latencia media y maxima. Agrupa por plantilla de ruta (no por URL
real) y por metodo estandar: las rutas inexistentes cuentan juntas en
`sin_ruta` y los metodos no estandar en `OTRO`, asi el estado no crece con lo
que envie un cliente. No guarda claves, IP, consultas ni cuerpos.

El middleware tambien:
- asigna `X-Request-ID` a cada respuesta (y a los errores);
- aplica el limite por IP antes de enrutar (frena claves inventadas, la
  documentacion y la salud);
- convierte un fallo inesperado en un 500 sanitizado, para que no llegue al
  servidor con su traza y su mensaje;
- marca las respuestas `Cache-Control: no-store`;
- registra una linea por solicitud: metodo acotado, plantilla, estado,
  latencia, identificador de la clave aceptada (no la clave) y solicitud."""
from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.publica.errores import error_inesperado, registro, respuesta_de_error

#: Metodos de RFC 9110 y PATCH. Cualquier otro se anota y se registra como `OTRO`.
METODOS_ESTANDAR = frozenset({"GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"})


def metodo_acotado(metodo: str) -> str:
    return metodo if metodo in METODOS_ESTANDAR else "OTRO"


class Monitor:
    def __init__(self, reloj=time.monotonic):
        self._reloj = reloj
        self._inicio = reloj()
        self.iniciado_en = datetime.now(timezone.utc).isoformat()
        self._cerrojo = threading.Lock()
        self._rutas: dict[tuple[str, str], dict] = defaultdict(
            lambda: {"solicitudes": 0, "errores_4xx": 0, "errores_5xx": 0, "total_ms": 0.0, "maximo_ms": 0.0})
        self._clases: dict[str, int] = defaultdict(int)

    def anotar(self, metodo: str, ruta: str, estado: int, milisegundos: float) -> None:
        with self._cerrojo:
            r = self._rutas[(metodo, ruta)]
            r["solicitudes"] += 1
            r["errores_4xx"] += 400 <= estado < 500
            r["errores_5xx"] += estado >= 500
            r["total_ms"] += milisegundos
            r["maximo_ms"] = max(r["maximo_ms"], milisegundos)
            self._clases[f"{estado // 100}xx"] += 1

    def resumen(self) -> dict:
        with self._cerrojo:
            rutas = [{"metodo": m, "ruta": ruta, "solicitudes": r["solicitudes"], "errores_4xx": r["errores_4xx"],
                      "errores_5xx": r["errores_5xx"], "latencia_media_ms": round(r["total_ms"] / r["solicitudes"], 3),
                      "latencia_maxima_ms": round(r["maximo_ms"], 3)} for (m, ruta), r in sorted(self._rutas.items())]
            return {"iniciado_en": self.iniciado_en, "segundos_activo": round(self._reloj() - self._inicio, 3),
                    "solicitudes": sum(self._clases.values()), "por_clase": dict(sorted(self._clases.items())),
                    "rutas": rutas}


def _plantilla(request: Request) -> str:
    return getattr(request.scope.get("route"), "path", None) or "sin_ruta"


class MiddlewarePublico(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.solicitud = uuid.uuid4().hex
        request.state.cliente = None
        inicio = time.perf_counter()
        try:
            respuesta, plantilla = await self._responder(request, call_next)
        except Exception as exc:  # no BaseException: las cancelaciones y salidas del proceso siguen su curso
            respuesta, plantilla = error_inesperado(request, exc), _plantilla(request)
        respuesta.headers["X-Request-ID"] = request.state.solicitud
        respuesta.headers["Cache-Control"] = "no-store"
        self._anotar(request, plantilla, respuesta.status_code, inicio)
        return respuesta

    @staticmethod
    async def _responder(request: Request, call_next):
        ip = request.client.host if request.client else "desconocido"
        decision = request.app.state.limitador_por_ip.consumir(ip)
        if not decision.permitida:
            return respuesta_de_error(request, 429, "limite_excedido",
                                      f"Demasiadas solicitudes desde este origen; reintente en "
                                      f"{decision.reintentar_en} s",
                                      headers={"Retry-After": str(decision.reintentar_en)}), "limite_por_ip"
        respuesta = await call_next(request)
        return respuesta, _plantilla(request)

    @staticmethod
    def _anotar(request: Request, plantilla: str, estado: int, inicio: float) -> None:
        milisegundos = (time.perf_counter() - inicio) * 1000
        metodo = metodo_acotado(request.method)
        request.app.state.monitor.anotar(metodo, plantilla, estado, milisegundos)
        registro.info("api_publica %s %s %s %.1fms clave=%s solicitud=%s", metodo, plantilla, estado,
                      milisegundos, request.state.cliente or "-", request.state.solicitud)
