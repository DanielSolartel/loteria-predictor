"""
Router web de Producto 3: panel diario y seguimiento del rendimiento.

- `GET /operacion`: estado de los cuatro juegos (solo lectura: nunca
  sincroniza ni entrena), ejecuciones recientes y acciones.
- `POST /operacion/ejecutar`: inicia «Generar con datos locales» o
  «Actualizar datos y generar» para un juego o para todos. Solo desde la
  propia maquina, con el token local (`proteccion_local`). Devuelve en
  seguida el identificador de la ejecucion (redireccion 303); el trabajo
  sigue en segundo plano y su progreso queda en el registro persistente.
  Si el juego ya tiene una ejecucion activa (web o comando) responde 409
  con la ejecucion activa.
- `GET /operacion/ejecuciones/{id}`: progreso o resultado (sobrevive a
  recargar la pagina y a reiniciar el servidor; una ejecucion cuyo proceso
  murio aparece como interrumpida).
- `GET /rendimiento`: seguimiento acumulado por juego, con filtros.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BeforeValidator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_consultar_panel,
    get_consultar_rendimiento,
    get_lanzador_de_operacion,
    get_operacion_diaria,
)
from app.api.web import proteccion_local
from app.api.web.routers.producto import _base, _conectada
from app.application.use_cases.operacion_diaria import MODOS, EjecucionActivaError, OperacionDiaria, mensaje_legible
from app.application.use_cases.panel_diario import NOMBRES, SLUGS, ConsultarPanelDiario
from app.application.use_cases.pronostico_experimental import JUEGOS, PronosticoExperimentalNoDisponibleError
from app.application.use_cases.rendimiento import FILTROS_DE_EMISION, ConsultarRendimiento
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
ETIQUETAS_MODO = {"local": "Generar con datos locales", "actualizar": "Actualizar datos y generar"}


def _vacio_a_none(valor):
    return None if valor in ("", None) else valor


_Fecha = Annotated[date | None, BeforeValidator(_vacio_a_none), Query()]


@router.get("/operacion")
def panel(request: Request, db: Session = Depends(get_db),
          consultar: ConsultarPanelDiario = Depends(get_consultar_panel)):
    datos = consultar.ejecutar()
    return templates.TemplateResponse(request=request, name="operacion/panel.html", context={
        **_base(request, "operacion", _conectada(db)), **datos, "token_local": proteccion_local.token_local(),
        "modos": ETIQUETAS_MODO})


def _pagina_error(request: Request, mensaje: str, status_code: int, activas: dict | None = None):
    return templates.TemplateResponse(request=request, name="operacion/error.html", status_code=status_code,
                                      context={**_base(request, "operacion", True), "mensaje": mensaje,
                                               "activas": activas or {}, "nombres": NOMBRES})


@router.post("/operacion/ejecutar")
def ejecutar(request: Request, juego: Annotated[str, Form()] = "", modo: Annotated[str, Form()] = "",
             token_local: Annotated[str, Form()] = "",
             operacion: OperacionDiaria = Depends(get_operacion_diaria),
             lanzar=Depends(get_lanzador_de_operacion)):
    motivo = proteccion_local.motivo_de_rechazo(request, token_local)
    if motivo is not None:
        return _pagina_error(request, f"Acción rechazada: {motivo}. Abre la aplicación en http://localhost:8000 en "
                             "esta misma máquina, recarga el panel y vuelve a pulsar el botón.", 403)
    juegos = list(JUEGOS) if juego == "todos" else [juego]
    if any(j not in JUEGOS for j in juegos) or modo not in MODOS:
        return _pagina_error(request, "Juego o acción no reconocidos.", 422)
    try:
        inicio = operacion.iniciar(juegos, modo, "web")
    except EjecucionActivaError as error:
        return _pagina_error(request, "Ya hay una ejecución en curso para "
                             + ", ".join(NOMBRES[j] for j in sorted(error.activas)) + ". Espera a que termine.",
                             409, error.activas)
    except OSError as error:
        return _pagina_error(request, f"No se pudo registrar la ejecución: {mensaje_legible(error)}", 500)
    try:
        lanzar(operacion.ejecutar, inicio)
    except Exception as error:  # p. ej. no se pudo crear el hilo: no queda nada falsamente activo
        operacion.abortar(inicio, str(error))
        return _pagina_error(request, f"No se pudo iniciar la ejecución: {mensaje_legible(error)}", 500)
    return RedirectResponse(url=f"/operacion/ejecuciones/{inicio.ejecucion['id']}", status_code=303)


def _ejecucion(operacion: OperacionDiaria, identificador: str) -> dict:
    ejecucion = operacion.consultar(identificador)
    if ejecucion is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return ejecucion


@router.get("/operacion/ejecuciones/{identificador}")
def detalle_ejecucion(identificador: str, request: Request, db: Session = Depends(get_db),
                      operacion: OperacionDiaria = Depends(get_operacion_diaria)):
    return templates.TemplateResponse(request=request, name="operacion/ejecucion.html", context={
        **_base(request, "operacion", _conectada(db)), "e": _ejecucion(operacion, identificador),
        "nombres": NOMBRES, "slugs": SLUGS, "modos": ETIQUETAS_MODO})


@router.get("/operacion/ejecuciones/{identificador}/estado")
def estado_ejecucion(identificador: str, request: Request,
                     operacion: OperacionDiaria = Depends(get_operacion_diaria)):
    """Fragmento HTMX para refrescar el progreso (solo lectura)."""
    return templates.TemplateResponse(request=request, name="operacion/_ejecucion_estado.html", context={
        "e": _ejecucion(operacion, identificador), "nombres": NOMBRES, "slugs": SLUGS, "modos": ETIQUETAS_MODO})


def grafica(serie: list[dict], ancho: int = 640, alto: int = 220, margen: int = 36) -> dict | None:
    """Geometria SVG de la diferencia acumulada (sin bibliotecas externas).
    Usa exactamente los puntos de `serie`, que tambien se listan en la
    tabla accesible."""
    if not serie:
        return None
    valores = [p["acumulada"] for p in serie]
    bajo, alto_v = min(0.0, *valores), max(0.0, *valores)
    rango = (alto_v - bajo) or 1.0
    paso = (ancho - 2 * margen) / max(len(serie) - 1, 1)

    def y(v: float) -> float:
        return round(margen + (alto_v - v) / rango * (alto - 2 * margen), 1)

    puntos = [{"x": round(margen + i * paso, 1), "y": y(p["acumulada"]), "objetivo": p["objetivo"],
               "acumulada": p["acumulada"]} for i, p in enumerate(serie)]
    return {"ancho": ancho, "alto": alto, "margen": margen, "cero": y(0.0), "puntos": puntos,
            "polilinea": " ".join(f"{p['x']},{p['y']}" for p in puntos), "maximo": alto_v, "minimo": bajo,
            "final": valores[-1]}


@router.get("/rendimiento")
def rendimiento(request: Request, juego: str = Query(default="BALOTO"), emision: str = Query(default="todas"),
                desde: _Fecha = None, hasta: _Fecha = None, db: Session = Depends(get_db),
                consultar: ConsultarRendimiento = Depends(get_consultar_rendimiento)):
    if juego not in JUEGOS:
        raise HTTPException(status_code=404, detail=f"Juego no admitido: {juego}")
    if emision not in FILTROS_DE_EMISION:
        raise HTTPException(status_code=422, detail="Tipo de emisión no admitido")
    datos, error = None, None
    try:
        datos = consultar.ejecutar(juego, emision=emision, desde=desde, hasta=hasta)
    except (SQLAlchemyError, PronosticoExperimentalNoDisponibleError, OSError) as excepcion:
        error = mensaje_legible(excepcion)
    except Exception as excepcion:  # base no disponible u otro fallo: estado legible, sin traceback
        error = mensaje_legible(excepcion)
    return templates.TemplateResponse(request=request, name="operacion/rendimiento.html", context={
        **_base(request, "rendimiento", _conectada(db)), "datos": datos, "error": error, "juego": juego,
        "nombres": NOMBRES, "slugs": SLUGS, "emision": emision, "desde": desde, "hasta": hasta,
        "filtros_emision": FILTROS_DE_EMISION,
        "graficas": {t: grafica(agg["serie"]) for t, agg in (datos or {}).get("por_tipo", {}).items()}})
