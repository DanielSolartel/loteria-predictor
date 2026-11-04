"""Errores de la API publica: un unico formato JSON
`{"error": {"codigo", "mensaje", "solicitud"[, "detalles"]}}`.

Nunca devuelven la clave, cabeceras, la entrada recibida, rutas de archivos,
trazas ni mensajes de la base de datos: un fallo inesperado es `error_interno`
y uno de la base `base_no_disponible`, con el identificador de la solicitud
para correlacionarlo con el registro del servidor.

Un fallo inesperado lo convierte `MiddlewarePublico` (ver `error_inesperado`),
asi no llega al servidor, que imprimiria su traza y su mensaje. El manejador
de `Exception` queda solo para un fallo del propio middleware."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.exceptions import (
    DominioError,
    JuegoNoEncontradoError,
    ResultadoHistoricoInconsistenteError,
    SorteoNoEncontradoError,
)

registro = logging.getLogger("app.api.publica")
SQLSTATE_CONSULTA_CANCELADA = "57014"  # query_canceled: `statement_timeout` o cancelacion explicita

_POR_ESTADO = {400: ("solicitud_no_valida", "Solicitud no válida"),
               401: ("no_autenticado", "Clave de API ausente o no válida"),
               404: ("no_encontrado", "Recurso no encontrado"),
               405: ("metodo_no_permitido", "Método no permitido: la API pública solo admite GET"),
               409: ("conflicto", "El recurso guardado no es íntegro"),
               422: ("parametro_no_valido", "Parámetro no válido"),
               429: ("limite_excedido", "Límite de uso excedido"),
               503: ("no_disponible", "Servicio no disponible")}


class ErrorPublico(Exception):
    def __init__(self, estado: int, codigo: str, mensaje: str, headers: dict[str, str] | None = None):
        super().__init__(mensaje)
        self.estado, self.codigo, self.mensaje, self.headers = estado, codigo, mensaje, headers or {}


def respuesta_de_error(request: Request, estado: int, codigo: str, mensaje: str, *,
                       headers: dict[str, str] | None = None, detalles: list | None = None) -> JSONResponse:
    error = {"codigo": codigo, "mensaje": mensaje, "solicitud": getattr(request.state, "solicitud", None)}
    if detalles:
        error["detalles"] = detalles
    return JSONResponse(status_code=estado, content={"error": error}, headers=headers)


def error_inesperado(request: Request, exc: Exception) -> JSONResponse:
    """500 sanitizado; registra solo la clase de la excepcion, sin su mensaje ni su traza."""
    registro.error("api_publica error_interno=%s solicitud=%s", type(exc).__name__,
                   getattr(request.state, "solicitud", None))
    return respuesta_de_error(request, 500, "error_interno", "Error interno")


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorPublico)
    async def _publico(request: Request, exc: ErrorPublico):
        return respuesta_de_error(request, exc.estado, exc.codigo, exc.mensaje, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codigo, mensaje = _POR_ESTADO.get(exc.status_code, ("error", "Error"))
        if isinstance(exc.detail, dict):  # errores con codigo de los casos de uso reutilizados
            codigo, mensaje = exc.detail.get("codigo", codigo), exc.detail.get("mensaje", mensaje)
        elif exc.status_code not in (404, 405) and isinstance(exc.detail, str):
            mensaje = exc.detail
        headers = {k: v for k, v in (exc.headers or {}).items() if k.lower() == "allow"}
        return respuesta_de_error(request, exc.status_code, codigo, mensaje, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError):
        detalles = [{"ubicacion": [str(x) for x in e.get("loc", ())], "mensaje": e.get("msg", "")}
                    for e in exc.errors()]
        return respuesta_de_error(request, 422, "parametro_no_valido", "Parámetro no válido", detalles=detalles)

    @app.exception_handler(JuegoNoEncontradoError)
    async def _juego(request: Request, exc: JuegoNoEncontradoError):
        return respuesta_de_error(request, 404, "no_encontrado", "Juego no encontrado")

    @app.exception_handler(SorteoNoEncontradoError)
    async def _sorteo(request: Request, exc: SorteoNoEncontradoError):
        return respuesta_de_error(request, 404, "no_encontrado", "Sorteo no encontrado")

    @app.exception_handler(ResultadoHistoricoInconsistenteError)
    async def _historico(request: Request, exc: ResultadoHistoricoInconsistenteError):
        # El histórico guardado no supera la validación de la muestra: no se calcula ni se descarta
        # ningún sorteo. Sin el detalle (sorteo y valores) en la respuesta; solo la clase en el registro.
        registro.warning("api_publica historico_no_valido solicitud=%s", getattr(request.state, "solicitud", None))
        return respuesta_de_error(request, 409, "historico_no_valido",
                                  "El histórico cargado no es consistente; no se calcula la estadística")

    @app.exception_handler(DominioError)
    async def _dominio(request: Request, exc: DominioError):
        registro.warning("api_publica error_de_dominio=%s solicitud=%s", type(exc).__name__,
                         getattr(request.state, "solicitud", None))
        return respuesta_de_error(request, 500, "error_interno", "Error interno al leer los datos")

    @app.exception_handler(SQLAlchemyError)
    async def _base(request: Request, exc: SQLAlchemyError):
        if getattr(getattr(exc, "orig", None), "sqlstate", None) == SQLSTATE_CONSULTA_CANCELADA:
            # Fase 10 (E10.2): `statement_timeout` del rol lector. La sesion de lectura termina con ROLLBACK y
            # la conexion vuelve sana al pool; solo se informa la clase del fallo.
            registro.warning("api_publica consulta_cancelada solicitud=%s", getattr(request.state, "solicitud", None))
            return respuesta_de_error(request, 503, "consulta_cancelada",
                                      "La consulta superó el tiempo máximo; reintente más tarde",
                                      headers={"Retry-After": "5"})
        registro.warning("api_publica base_no_disponible=%s solicitud=%s", type(exc).__name__,
                         getattr(request.state, "solicitud", None))
        return respuesta_de_error(request, 503, "base_no_disponible", "Base de datos no disponible")

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception):
        return error_inesperado(request, exc)
