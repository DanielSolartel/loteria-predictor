"""
API REST interna de la Fase 7 (JSON, solo lectura): mismo caso de uso que la
web y el comando `python -m scripts.simulaciones`.

- `GET /api/simulaciones/catalogo`: iteraciones admitidas, semilla, algoritmo y
  estadisticas fijadas por juego.
- `GET /api/simulaciones/panel`: corte, sorteos y simulaciones de los cuatro juegos.
- `GET /api/simulaciones[?juego=&limite=]`: filas de la tabla `simulaciones`
  (Fase 7) con su integridad.
- `GET /api/simulaciones/ejecuciones[/{id}]`: progreso de los trabajos.
- `GET /api/simulaciones/{id}`: fila verificada; `/{id}/csv` y `/{id}/json`
  son exportaciones derivadas; `/{id}/verificacion` comprueba integridad y
  base actual (sin reproducir).

Simular escribe y consume CPU: se lanza desde la web (POST protegido) o con
el comando. No es la API publica de la Fase 8. 404: juego, ejecucion o fila
inexistentes; 409: fila alterada; 422: parametro no valido; 503: base no
disponible.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.api.dependencies import get_simulaciones
from app.application.use_cases.operacion_diaria import identificador_valido
from app.application.use_cases.simulaciones import JUEGOS, SimulacionesError, SimulacionesFase7

router = APIRouter(prefix="/api/simulaciones")
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "base_no_disponible": 503}


def _http(error: SimulacionesError) -> HTTPException:
    return HTTPException(status_code=_CODIGO_HTTP.get(error.codigo, 400),
                         detail={"codigo": error.codigo, "mensaje": str(error)})


@router.get("/catalogo")
def catalogo(servicio: SimulacionesFase7 = Depends(get_simulaciones)) -> dict:
    return servicio.catalogo()


@router.get("/panel")
def panel(servicio: SimulacionesFase7 = Depends(get_simulaciones)) -> dict:
    return {"juegos": servicio.panel()}


@router.get("/ejecuciones")
def ejecuciones(limite: int = Query(default=20, ge=1, le=200), servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    return {"ejecuciones": servicio.recientes(limite)}


@router.get("/ejecuciones/{identificador}")
def ejecucion(identificador: str, servicio: SimulacionesFase7 = Depends(get_simulaciones)) -> dict:
    encontrada = servicio.consultar_ejecucion(identificador) if identificador_valido(identificador) else None
    if encontrada is None:
        raise HTTPException(status_code=404, detail={"codigo": "no_encontrado", "mensaje": "Ejecucion no encontrada"})
    return encontrada


@router.get("")
def listar(juego: str | None = Query(default=None), limite: int = Query(default=50, ge=1, le=200),
           servicio: SimulacionesFase7 = Depends(get_simulaciones)) -> dict:
    if juego is not None and juego not in JUEGOS:
        raise HTTPException(status_code=404, detail={"codigo": "no_encontrado", "mensaje": f"Juego no admitido: {juego}"})
    try:
        return {"simulaciones": servicio.listar(juego, limite)}
    except SimulacionesError as error:
        raise _http(error) from error


@router.get("/{identificador}")
def obtener(identificador: str, servicio: SimulacionesFase7 = Depends(get_simulaciones)) -> dict:
    try:
        return servicio.obtener(identificador)
    except SimulacionesError as error:
        raise _http(error) from error


@router.get("/{identificador}/csv", response_class=PlainTextResponse)
def exportar_csv(identificador: str, servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    try:
        return PlainTextResponse(servicio.exportar_csv(identificador), media_type="text/csv; charset=utf-8")
    except SimulacionesError as error:
        raise _http(error) from error


@router.get("/{identificador}/json", response_class=PlainTextResponse)
def exportar_json(identificador: str, servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    try:
        return PlainTextResponse(servicio.exportar_json(identificador), media_type="application/json")
    except SimulacionesError as error:
        raise _http(error) from error


@router.get("/{identificador}/verificacion")
def verificacion(identificador: str, servicio: SimulacionesFase7 = Depends(get_simulaciones)) -> dict:
    try:
        return servicio.verificar(identificador, reproducir=False)
    except SimulacionesError as error:
        raise _http(error) from error
