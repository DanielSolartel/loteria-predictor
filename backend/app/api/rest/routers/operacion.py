"""
API REST de Producto 3 (JSON, solo lectura): panel diario, ejecuciones de
la operacion diaria y seguimiento del rendimiento. Consultar nunca
sincroniza ni genera; para ejecutar se usa el panel (POST protegido) o el
comando `python -m scripts.operacion_diaria`.

404: juego o ejecucion inexistente; 422: filtro no valido; 503: base de
datos no disponible para leer el historico.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_consultar_panel, get_consultar_rendimiento, get_operacion_diaria
from app.application.use_cases.operacion_diaria import OperacionDiaria
from app.application.use_cases.panel_diario import ConsultarPanelDiario
from app.application.use_cases.pronostico_experimental import JUEGOS
from app.application.use_cases.rendimiento import FILTROS_DE_EMISION, ConsultarRendimiento

router = APIRouter(prefix="/api")


@router.get("/operacion/panel")
def panel(consultar: ConsultarPanelDiario = Depends(get_consultar_panel)) -> dict:
    return consultar.ejecutar()


@router.get("/operacion/ejecuciones")
def ejecuciones(limite: int = Query(default=20, ge=1, le=200),
                operacion: OperacionDiaria = Depends(get_operacion_diaria)) -> dict:
    return {"ejecuciones": operacion.recientes(limite)}


@router.get("/operacion/ejecuciones/{identificador}")
def ejecucion(identificador: str, operacion: OperacionDiaria = Depends(get_operacion_diaria)) -> dict:
    encontrada = operacion.consultar(identificador)
    if encontrada is None:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada")
    return encontrada


@router.get("/rendimiento/{codigo}")
def rendimiento(codigo: str, emision: str = Query(default="todas"), desde: date | None = Query(default=None),
                hasta: date | None = Query(default=None),
                consultar: ConsultarRendimiento = Depends(get_consultar_rendimiento)) -> dict:
    if codigo not in JUEGOS:
        raise HTTPException(status_code=404, detail=f"Juego no admitido: {codigo}")
    if emision not in FILTROS_DE_EMISION:
        raise HTTPException(status_code=422, detail=f"emision admitida: {', '.join(FILTROS_DE_EMISION)}")
    try:
        return consultar.ejecutar(codigo, emision=emision, desde=desde, hasta=hasta)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Base de datos no disponible para leer los resultados") from error
