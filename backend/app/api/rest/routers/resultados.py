"""
API REST de Producto 6 (JSON, solo lectura): indice de los cuatro juegos,
consulta filtrada con historial paginado, exportacion completa, informes
guardados y vista previa de «usar esta configuracion». Mismo caso de uso que
la web y el comando: mismos filtros, estados, objetivos y valores.
Guardar informes, verificarlos y usar una configuracion no se exponen aqui:
se hacen desde la web (POST protegido) o con `python -m scripts.resultados_modelos`.

Filtros (repetibles): `procedencia`, `linea`, `cartera`; ademas `tipo`
(seguimiento | retrospectiva), `desde`, `hasta`, `objetivo`, `pagina` y
`por_pagina`. 404: juego o informe inexistentes; 409: informe alterado;
422: filtro no valido.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.api.dependencies import get_resultados
from app.application.use_cases.resultados import (
    JUEGOS,
    MAXIMO_POR_PAGINA,
    POR_PAGINA,
    CentroDeResultados,
    Filtros,
    ResultadosError,
)

router = APIRouter(prefix="/api/resultados")
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409}
_Lista = Annotated[list[str] | None, Query()]


def _http(error: ResultadosError) -> HTTPException:
    return HTTPException(status_code=_CODIGO_HTTP.get(error.codigo, 400), detail={"codigo": error.codigo,
                                                                               "mensaje": str(error)})


def _juego(codigo: str) -> str:
    if codigo not in JUEGOS:
        raise HTTPException(status_code=404, detail={"codigo": "no_encontrado", "mensaje": f"Juego no admitido: {codigo}"})
    return codigo


def _filtros(procedencia, linea, tipo, desde, hasta, objetivo, cartera) -> Filtros:
    try:
        return Filtros(tuple(procedencia or ()) or Filtros().procedencias, tuple(linea or ()), tipo, desde, hasta,
                       objetivo, tuple(cartera or ())).validar()
    except ResultadosError as error:
        raise _http(error) from error


@router.get("")
def indice(centro: CentroDeResultados = Depends(get_resultados)) -> dict:
    return centro.indice()


@router.get("/informes/{clave}")
def informe(clave: str, centro: CentroDeResultados = Depends(get_resultados)) -> dict:
    try:
        return centro.informe(clave)
    except ResultadosError as error:
        raise _http(error) from error


@router.get("/{codigo}/informes")
def informes(codigo: str, centro: CentroDeResultados = Depends(get_resultados)) -> dict:
    return {"juego": codigo, "informes": centro.informes(_juego(codigo))}


@router.get("/{codigo}/configuracion")
def configuracion(codigo: str, linea: str = Query(...), centro: CentroDeResultados = Depends(get_resultados)) -> dict:
    try:
        return centro.propuesta_de_configuracion(_juego(codigo), linea)
    except ResultadosError as error:
        raise _http(error) from error


@router.get("/{codigo}/exportar.json")
def exportar_json(codigo: str, procedencia: _Lista = None, linea: _Lista = None, tipo: str = "seguimiento",
                  desde: int | None = None, hasta: int | None = None, objetivo: int | None = None,
                  cartera: _Lista = None, centro: CentroDeResultados = Depends(get_resultados)) -> dict:
    filtros = _filtros(procedencia, linea, tipo, desde, hasta, objetivo, cartera)
    try:
        return centro.exportar_json(_juego(codigo), filtros)
    except ResultadosError as error:
        raise _http(error) from error


@router.get("/{codigo}/exportar.csv", response_class=PlainTextResponse)
def exportar_csv(codigo: str, procedencia: _Lista = None, linea: _Lista = None, tipo: str = "seguimiento",
                 desde: int | None = None, hasta: int | None = None, objetivo: int | None = None,
                 cartera: _Lista = None, centro: CentroDeResultados = Depends(get_resultados)):
    filtros = _filtros(procedencia, linea, tipo, desde, hasta, objetivo, cartera)
    try:
        return PlainTextResponse(centro.exportar_csv(_juego(codigo), filtros), media_type="text/csv; charset=utf-8")
    except ResultadosError as error:
        raise _http(error) from error


@router.get("/{codigo}")
def consultar(codigo: str, procedencia: _Lista = None, linea: _Lista = None, tipo: str = "seguimiento",
              desde: int | None = None, hasta: int | None = None, objetivo: int | None = None,
              cartera: _Lista = None, pagina: int = Query(default=1, ge=1),
              por_pagina: int = Query(default=POR_PAGINA, ge=1, le=MAXIMO_POR_PAGINA),
              centro: CentroDeResultados = Depends(get_resultados)) -> dict:
    filtros = _filtros(procedencia, linea, tipo, desde, hasta, objetivo, cartera)
    try:
        return centro.consultar(_juego(codigo), filtros, pagina=pagina, por_pagina=por_pagina)
    except ResultadosError as error:
        raise _http(error) from error
