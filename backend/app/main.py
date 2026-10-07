"""
Composición raíz de la aplicación.

Este es el único archivo que conoce ambos adaptadores de entrada
(web y REST) y los conecta con el framework HTTP. No contiene
lógica de negocio: solo montaje de routers, archivos estáticos,
plantillas y el manejo global de excepciones de dominio -que aquí
se traducen a respuestas HTTP apropiadas, siguiendo el mismo mapeo
para ambos adaptadores (la app web usa este manejador solo como red
de seguridad, ya que sus routers capturan las excepciones más
específicas caso por caso para mostrar errores de formulario).
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.rest.routers import colores as rest_colores
from app.api.rest.routers import juegos as rest_juegos
from app.api.rest.routers import operacion as rest_operacion
from app.api.rest.routers import producto as rest_producto
from app.api.rest.routers import sorteos as rest_sorteos
from app.api.web.routers import colores as web_colores
from app.api.web.routers import dashboard as web_dashboard
from app.api.web.routers import estadisticas as web_estadisticas
from app.api.web.routers import importacion as web_importacion
from app.api.web.routers import juegos as web_juegos
from app.api.web.routers import operacion as web_operacion
from app.api.web.routers import producto as web_producto
from app.api.web.routers import sorteos as web_sorteos
from app.application.exceptions import (
    ColorNoVigenteError,
    ConectorNoDisponibleError,
    DominioError,
    JuegoNoEncontradoError,
    JuegoNoSoportadoError,
    JuegoSinSuperbalotaError,
    ResultadoHistoricoInconsistenteError,
    SorteoDuplicadoError,
    SorteoInvalidoError,
    SorteoNoEncontradoError,
)

app = FastAPI(title="Sistema Predictivo de Loterías", version="0.1.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Adaptador web (HTML + HTMX)
app.include_router(web_dashboard.router)
app.include_router(web_juegos.router)
app.include_router(web_sorteos.router)
app.include_router(web_colores.router)
app.include_router(web_importacion.router)
app.include_router(web_producto.router)
app.include_router(web_estadisticas.router)
app.include_router(web_operacion.router)

# Adaptador REST (JSON, puente hacia una futura UI en React/Next.js)
app.include_router(rest_juegos.router)
app.include_router(rest_sorteos.router)
app.include_router(rest_colores.router)
app.include_router(rest_producto.router)
app.include_router(rest_operacion.router)


_STATUS_POR_EXCEPCION = {
    JuegoNoEncontradoError: 404,
    JuegoNoSoportadoError: 422,
    JuegoSinSuperbalotaError: 422,
    SorteoNoEncontradoError: 404,
    SorteoDuplicadoError: 409,
    SorteoInvalidoError: 422,
    ColorNoVigenteError: 422,
    ConectorNoDisponibleError: 502,
    # 500, no 422: a diferencia de JuegoSinSuperbalotaError (el
    # usuario pidió una operación incompatible y puede elegir otra
    # métrica), aquí el request puede ser perfectamente válido -el
    # servidor encontró que los datos históricos persistidos son
    # inconsistentes con cantidad_numeros. El usuario no puede
    # corregir esto cambiando su solicitud; devolver 422 le atribuiría
    # incorrectamente el problema al request. Confirmado inalcanzable
    # con datos reales (StandardNumberGame.validate_draw ya lo impide
    # al escribir), pero si ocurriera, es un fallo de integridad
    # server-side, no una entrada del usuario procesable de otra forma.
    ResultadoHistoricoInconsistenteError: 500,
}


@app.exception_handler(DominioError)
async def manejar_error_dominio(request: Request, exc: DominioError):
    status_code = _STATUS_POR_EXCEPCION.get(type(exc), 400)

    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=status_code, content={"detalle": str(exc)})

    return HTMLResponse(
        content=f"<div class='alert alert-danger m-4'>{exc}</div>", status_code=status_code
    )
