"""
API REST de Productos 1 y 2 (JSON): resumen por juego, pronosticos
experimentales guardados de Baloto, Revancha, MiLoto y ColorLoto, y su
comparacion con los resultados observados. Solo lectura.

- `GET /api/pronosticos/{codigo}` y `/api/pronosticos/{codigo}/{id}`:
  artefactos tal cual, con `estado_actual` y `resultado_observado`;
- `GET /api/resultados-observados/{codigo}`: cada pronostico guardado
  frente a su sorteo objetivo (`observado`, `pendiente`, `no_corresponde`).

404: codigo no admitido o juego no registrado; 409: artefacto alterado;
503: base de datos no disponible para leer los resultados.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_comparar_resultados, get_consultar_pronosticos, get_consultar_resumen_juego
from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.pronostico_experimental_store import PronosticoIlegible
from app.application.use_cases.consultar_resumen_juego import SLUG_A_CODIGO_RESUMEN, ConsultarResumenJuego
from app.application.use_cases.pronostico_experimental import (
    CompararConResultadosObservados,
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
    """Artefacto guardado tal cual, mas su version, el estado temporal de
    hoy frente a la base y la comparacion con el resultado observado
    (ambos None si la base no esta disponible)."""
    return {"identificador": guardado.identificador, "version": guardado.version, "versiones": guardado.versiones,
            "estado_actual": consultar.estado_actual(codigo, guardado.artefacto),
            "resultado_observado": consultar.resultado_observado(codigo, guardado.artefacto), **guardado.artefacto}


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


@router.get("/resultados-observados/{codigo}")
def resultados_observados(codigo: str,
                          comparar: CompararConResultadosObservados = Depends(get_comparar_resultados)) -> dict:
    try:
        filas = comparar.ejecutar(codigo)
    except (PronosticoExperimentalNoDisponibleError, JuegoNoEncontradoError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Base de datos no disponible para leer los resultados") from error
    return {"juego": codigo, "estado_de_uso": "experimental_no_acreditado",
            "nota": "comparacion de lectura: los artefactos no se modifican; la fecha de generacion es del reloj "
                    "local y no acredita anterioridad frente al sorteo real",
            "pronosticos": filas}
