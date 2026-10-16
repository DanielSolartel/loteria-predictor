"""
API REST de la Fase 4 (JSON, solo lectura): centro de predicciones. Mismo caso
de uso que la web y el comando `python -m scripts.predicciones`.

- `GET /api/predicciones`: los cuatro juegos (configuracion, version
  registrada, base y ultima prediccion).
- `GET /api/predicciones/{codigo}[?cartera=<clave>]`: la prediccion con
  combinaciones, rankings, explicacion y proyeccion a la tabla `predicciones`.
- `GET /api/predicciones/{codigo}/fiabilidad[?linea=&hasta=]`: rendimiento
  observado e incertidumbre por linea y tipo de evaluacion.

Generar y explicar escriben: se hacen desde la web (POST protegido) o con el
comando. 404: juego o cartera inexistentes; 409: artefacto alterado o sin
configuracion; 422: parametro no valido.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_predicciones
from app.api.parametros import CorteOpcional
from app.application.use_cases.predicciones import JUEGOS, CentroDePredicciones, PrediccionesError

router = APIRouter(prefix="/api/predicciones")
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409, "incompatible": 409,
                "sin_configuracion": 409}


def _http(error: PrediccionesError) -> HTTPException:
    return HTTPException(status_code=_CODIGO_HTTP.get(error.codigo, 400),
                         detail={"codigo": error.codigo, "mensaje": str(error)})


def _juego(codigo: str) -> str:
    if codigo not in JUEGOS:
        raise HTTPException(status_code=404, detail={"codigo": "no_encontrado", "mensaje": f"Juego no admitido: {codigo}"})
    return codigo


@router.get("")
def indice(centro: CentroDePredicciones = Depends(get_predicciones)) -> dict:
    return centro.indice()


@router.get("/{codigo}")
def prediccion(codigo: str, cartera: str | None = Query(None),
               centro: CentroDePredicciones = Depends(get_predicciones)) -> dict:
    try:
        return centro.consultar(_juego(codigo), cartera)
    except PrediccionesError as error:
        raise _http(error) from error


@router.get("/{codigo}/fiabilidad")
def fiabilidad(codigo: str, linea: str | None = Query(None), hasta: CorteOpcional = None,
               centro: CentroDePredicciones = Depends(get_predicciones)) -> dict:
    try:
        return centro.fiabilidad(_juego(codigo), linea, hasta)
    except PrediccionesError as error:
        raise _http(error) from error
