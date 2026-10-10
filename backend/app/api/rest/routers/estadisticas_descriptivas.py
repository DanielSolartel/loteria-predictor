"""
API REST de la Fase 5 (JSON, solo lectura): los mismos datos que las páginas descriptivas.

- `GET /api/estadisticas/{codigo}/panel`: el panel unificado (`juego`, `muestra`, `grupos`).
- `GET /api/estadisticas/{codigo}/descriptivas/{metrica}`: una métrica nueva (`juego`, `muestra`,
  `metrica`), con `hasta_numero_sorteo` y, según la métrica, `anio`, `mes`, `dia_semana` o `ventana`.

`codigo`: BALOTO, BALOTO_REVANCHA, MILOTO o COLORLOTO (como `/api/estadisticas/{codigo}/resumen`,
que no cambia). 404: código, métrica o combinación que no aplica; 422: parámetro inválido; 503: base
de datos no disponible. Nunca escribe en la base.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_consultar_estadisticas_descriptivas
from app.application.estadisticas.descriptivas import POR_SLUG, VENTANAS
from app.application.use_cases.consultar_estadisticas_descriptivas import ConsultarEstadisticasDescriptivas
from app.application.use_cases.consultar_resumen_juego import SLUG_A_CODIGO_RESUMEN

router = APIRouter(prefix="/api")

_CODIGO_A_SLUG = {codigo: slug for slug, codigo in SLUG_A_CODIGO_RESUMEN.items()}


def _codigo(codigo: str) -> str:
    if codigo not in _CODIGO_A_SLUG:
        raise HTTPException(status_code=404, detail=f"Juego no admitido: {codigo}")
    return codigo


def _sin_base(error: SQLAlchemyError) -> HTTPException:
    return HTTPException(status_code=503, detail="Base de datos no disponible para leer el histórico")


@router.get("/estadisticas/{codigo}/panel")
def panel(codigo: str, hasta_numero_sorteo: int | None = Query(default=None, ge=1),
          consultar: ConsultarEstadisticasDescriptivas = Depends(get_consultar_estadisticas_descriptivas)) -> dict:
    _codigo(codigo)
    try:
        return consultar.panel(codigo, hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo)
    except SQLAlchemyError as e:
        raise _sin_base(e) from e


@router.get("/estadisticas/{codigo}/descriptivas/{metrica}")
def metrica(codigo: str, metrica: str, hasta_numero_sorteo: int | None = Query(default=None, ge=1),
            anio: int | None = Query(default=None, ge=1, le=9999), mes: int | None = Query(default=None, ge=1, le=12),
            dia_semana: Literal["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"] | None = None,
            ventana: int | None = Query(default=None),
            consultar: ConsultarEstadisticasDescriptivas = Depends(get_consultar_estadisticas_descriptivas)) -> dict:
    _codigo(codigo)
    definicion = POR_SLUG.get(metrica)
    if definicion is None or definicion.construir is None:
        raise HTTPException(status_code=404, detail=f"Métrica descriptiva desconocida: {metrica}")
    recibidos = {"anio": anio, "mes": mes, "dia_semana": dia_semana, "ventana": ventana}
    ajenos = [k for k, v in recibidos.items() if v is not None and k != definicion.parametro]
    if ajenos:
        raise HTTPException(status_code=422, detail=f"Parámetro(s) no admitido(s) por {metrica}: {', '.join(ajenos)}")
    if definicion.parametro == "ventana" and ventana is not None and ventana not in VENTANAS:
        raise HTTPException(status_code=422, detail=f"ventana debe ser una de {list(VENTANAS)}")
    parametros = {definicion.parametro: recibidos[definicion.parametro]} if definicion.parametro else {}
    try:
        reglas = consultar.reglas(codigo)
        if not definicion.aplica(reglas):
            motivo = definicion.motivo_no_aplica(reglas) if definicion.motivo_no_aplica else "no aplica a este juego"
            raise HTTPException(status_code=404, detail=f"{metrica} no está disponible para {codigo}: {motivo}")
        if not definicion.es_nueva(reglas):
            raise HTTPException(status_code=404, detail=(
                f"{metrica} de {codigo} es una visualización anterior a la Fase 5: "
                f"/estadisticas/{_CODIGO_A_SLUG[codigo]}/{metrica}"))
        return consultar.metrica(codigo, metrica, hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo,
                                 parametros=parametros)
    except SQLAlchemyError as e:
        raise _sin_base(e) from e
