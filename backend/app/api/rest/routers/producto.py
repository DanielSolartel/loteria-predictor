"""
API REST de Producto 1 (JSON): resumen por juego y pronosticos
experimentales guardados. Solo lectura.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_consultar_pronosticos, get_consultar_resumen_juego
from app.application.interfaces.pronostico_experimental_store import PronosticoIlegible
from app.application.use_cases.consultar_resumen_juego import SLUG_A_CODIGO_RESUMEN, ConsultarResumenJuego
from app.application.use_cases.pronostico_experimental import (
    ConsultarPronosticosExperimentales,
    PronosticoExperimentalNoDisponibleError,
    decisiones_ae39,
)

router = APIRouter(prefix="/api")


@router.get("/estadisticas/{codigo}/resumen")
def resumen(codigo: str, hasta_numero_sorteo: int | None = Query(default=None, ge=1),
            consultar: ConsultarResumenJuego = Depends(get_consultar_resumen_juego)) -> dict:
    if codigo not in SLUG_A_CODIGO_RESUMEN.values():
        raise HTTPException(status_code=404, detail=f"Juego no admitido: {codigo}")
    return consultar.ejecutar(codigo, hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo)


def _ilegible(e: PronosticoIlegible) -> dict:
    return {"identificador": e.identificador, "motivo": e.motivo}


@router.get("/pronosticos/{codigo}")
def pronosticos(codigo: str, consultar: ConsultarPronosticosExperimentales = Depends(get_consultar_pronosticos)) -> dict:
    try:
        r = consultar.resumen(codigo)
    except PronosticoExperimentalNoDisponibleError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        "juego": codigo,
        "estado_de_uso": "experimental_no_acreditado",
        "no_go_historico": decisiones_ae39(),
        "ultimo": None if r.ultimo is None else _detalle(consultar, codigo, r.ultimo),
        "guardados": [{"identificador": g.identificador, "objetivo": g.artefacto["pronostico"]["objetivo"],
                       "version": g.version, "versiones": g.versiones,
                       "clasificacion_temporal": (g.artefacto["generacion"].get("clasificacion_temporal") or {}).get("tipo"),
                       "corte": g.artefacto["datos"]["corte"],
                       "generado_en": g.artefacto["generacion"]["generado_en"]} for g in r.guardados],
        "ilegibles": [_ilegible(e) for e in r.ilegibles],
    }


def _detalle(consultar: ConsultarPronosticosExperimentales, codigo: str, guardado) -> dict:
    """Artefacto guardado tal cual, mas su version y el estado temporal
    de hoy frente a la base (None si la base no esta disponible)."""
    return {"identificador": guardado.identificador, "version": guardado.version, "versiones": guardado.versiones,
            "estado_actual": consultar.estado_actual(codigo, guardado.artefacto), **guardado.artefacto}


@router.get("/pronosticos/{codigo}/{identificador}")
def pronostico(codigo: str, identificador: str,
               consultar: ConsultarPronosticosExperimentales = Depends(get_consultar_pronosticos)) -> dict:
    try:
        elemento = consultar.obtener(codigo, identificador)
    except PronosticoExperimentalNoDisponibleError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if elemento is None:
        raise HTTPException(status_code=404, detail="Pronostico no encontrado")
    if isinstance(elemento, PronosticoIlegible):
        raise HTTPException(status_code=409, detail=_ilegible(elemento))
    return _detalle(consultar, codigo, elemento)
