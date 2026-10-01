"""
Router web de Producto 1: resumen estadistico por juego y pronostico
experimental de Baloto y Revancha.

- `/estadisticas`: entrada con los cuatro juegos.
- `/estadisticas/{slug}/resumen`: resumen de un juego (`baloto`,
  `baloto-revancha`, `miloto`, `colorloto`), con corte opcional.
- `/pronosticos`: pronosticos experimentales guardados de Baloto y
  Revancha, con su comparacion frente a la referencia uniforme y el NO-GO
  historico de AE-39.
- `/pronosticos/{slug}`: detalle con versiones y clasificacion temporal;
  `POST /pronosticos/{slug}/generar` entrena y guarda (o devuelve el ya
  guardado con la misma entrada); `GET /pronosticos/{slug}/verificar`
  solo muestra el formulario y `POST` recalcula (reentrena).

Los POST que entrenan solo se aceptan desde la propia maquina, con el
token local del formulario y sin origen ajeno (`proteccion_local`).
Solo lectura de PostgreSQL. Los pronosticos se guardan como archivos
inmutables; ninguno es un resultado acreditado.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BeforeValidator, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.web import proteccion_local
from app.api.dependencies import (
    get_consultar_pronosticos,
    get_consultar_resumen_juego,
    get_generar_pronostico,
    get_verificar_pronostico,
)
from app.application.exceptions import JuegoNoEncontradoError
from app.application.use_cases.consultar_resumen_juego import SLUG_A_CODIGO_RESUMEN, ConsultarResumenJuego
from app.application.use_cases.pronostico_experimental import (
    ConsultarPronosticosExperimentales,
    GenerarPronosticoExperimental,
    PronosticoExperimentalNoDisponibleError,
    VerificarPronosticoExperimental,
    decisiones_ae39,
)
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

SLUG_A_CODIGO_PRONOSTICO = {"baloto": "BALOTO", "baloto-revancha": "BALOTO_REVANCHA"}
NOMBRES = {"BALOTO": "Baloto", "BALOTO_REVANCHA": "Baloto Revancha", "MILOTO": "MiLoto", "COLORLOTO": "ColorLoto"}
CODIGO_A_SLUG = {codigo: slug for slug, codigo in SLUG_A_CODIGO_RESUMEN.items()}


def _vacio_a_none(valor):
    return None if valor == "" else valor


_Corte = Annotated[Annotated[int, Field(ge=1)] | None, BeforeValidator(_vacio_a_none), Query()]


def _conectada(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _base(request: Request, pagina: str, db_conectada: bool) -> dict:
    return {"request": request, "active_page": pagina, "db_conectada": db_conectada,
            "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD"}


@router.get("/estadisticas")
def indice_estadisticas(request: Request, db: Session = Depends(get_db),
                        resumen: ConsultarResumenJuego = Depends(get_consultar_resumen_juego)):
    conectada = _conectada(db)
    hoy = date.today()
    tarjetas = []
    for slug, codigo in SLUG_A_CODIGO_RESUMEN.items():
        tarjeta = {"slug": slug, "codigo": codigo, "nombre": NOMBRES[codigo], "resumen": None, "error": None}
        if conectada:
            try:
                tarjeta["resumen"] = resumen.ejecutar(codigo, hoy=hoy)
            except JuegoNoEncontradoError:
                tarjeta["error"] = "El juego no está registrado en la base de datos."
        tarjetas.append(tarjeta)
    return templates.TemplateResponse(request=request, name="producto/estadisticas_indice.html",
                                      context={**_base(request, "estadisticas", conectada), "tarjetas": tarjetas})


@router.get("/estadisticas/{juego_slug}/resumen")
def resumen_juego(juego_slug: str, request: Request, hasta_numero_sorteo: _Corte = None,
                  db: Session = Depends(get_db),
                  resumen: ConsultarResumenJuego = Depends(get_consultar_resumen_juego)):
    codigo = SLUG_A_CODIGO_RESUMEN.get(juego_slug)
    if codigo is None:
        raise HTTPException(status_code=404, detail=f"Estadísticas no disponibles para '{juego_slug}'")
    conectada = _conectada(db)
    datos = resumen.ejecutar(codigo, hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo) if conectada else None
    return templates.TemplateResponse(request=request, name="producto/resumen_juego.html", context={
        **_base(request, "estadisticas", conectada), "slug": juego_slug, "codigo": codigo,
        "nombre": NOMBRES[codigo], "datos": datos, "hasta_numero_sorteo": hasta_numero_sorteo,
        "juegos": [(s, NOMBRES[c]) for s, c in SLUG_A_CODIGO_RESUMEN.items()],
        "tiene_pronostico": juego_slug in SLUG_A_CODIGO_PRONOSTICO})


def _codigo_pronostico(juego_slug: str) -> str:
    codigo = SLUG_A_CODIGO_PRONOSTICO.get(juego_slug)
    if codigo is None:
        raise HTTPException(status_code=404,
                            detail=f"El pronóstico experimental solo existe para Baloto y Baloto Revancha, no para "
                                   f"'{juego_slug}'")
    return codigo


def _rechazo(request: Request, juego_slug: str, codigo: str, mensaje: str, status_code: int):
    return templates.TemplateResponse(request=request, name="producto/pronostico_error.html", status_code=status_code,
                                      context={**_base(request, "pronosticos", True), "slug": juego_slug,
                                               "nombre": NOMBRES[codigo], "mensaje": mensaje})


@router.get("/pronosticos")
def indice_pronosticos(request: Request, db: Session = Depends(get_db),
                       consultar: ConsultarPronosticosExperimentales = Depends(get_consultar_pronosticos)):
    juegos = []
    for slug, codigo in SLUG_A_CODIGO_PRONOSTICO.items():
        resumen = consultar.resumen(codigo)
        actual = consultar.estado_actual(codigo, resumen.ultimo.artefacto) if resumen.ultimo else None
        juegos.append({"slug": slug, "codigo": codigo, "nombre": NOMBRES[codigo], "ultimo": resumen.ultimo,
                       "actual": actual, "total": len(resumen.guardados), "ilegibles": resumen.ilegibles})
    return templates.TemplateResponse(request=request, name="producto/pronosticos_indice.html", context={
        **_base(request, "pronosticos", _conectada(db)), "juegos": juegos, "no_go": decisiones_ae39()})


@router.get("/pronosticos/{juego_slug}")
def detalle_pronostico(juego_slug: str, request: Request, id: str | None = Query(default=None),
                       reutilizado: int = Query(default=0), db: Session = Depends(get_db),
                       consultar: ConsultarPronosticosExperimentales = Depends(get_consultar_pronosticos)):
    codigo = _codigo_pronostico(juego_slug)
    resumen = consultar.resumen(codigo)
    seleccionado = resumen.ultimo
    if id is not None:
        seleccionado = consultar.obtener(codigo, id)
        if seleccionado is None:
            raise HTTPException(status_code=404, detail="Pronóstico no encontrado")
    actual = None
    if seleccionado is not None and not hasattr(seleccionado, "motivo"):
        actual = consultar.estado_actual(codigo, seleccionado.artefacto)
    return templates.TemplateResponse(request=request, name="producto/pronostico_detalle.html", context={
        **_base(request, "pronosticos", _conectada(db)), "slug": juego_slug, "codigo": codigo,
        "nombre": NOMBRES[codigo], "seleccionado": seleccionado, "actual": actual, "historial": resumen.guardados,
        "ilegibles": resumen.ilegibles, "no_go": decisiones_ae39(), "reutilizado": bool(reutilizado),
        "token_local": proteccion_local.token_local()})


@router.post("/pronosticos/{juego_slug}/generar")
def generar_pronostico(juego_slug: str, request: Request,
                       hasta_numero_sorteo: Annotated[str, Form()] = "",
                       token_local: Annotated[str, Form()] = "",
                       generar: GenerarPronosticoExperimental = Depends(get_generar_pronostico)):
    codigo = _codigo_pronostico(juego_slug)
    motivo = proteccion_local.motivo_de_rechazo(request, token_local)
    if motivo is not None:
        return _rechazo(request, juego_slug, codigo, f"Entrenamiento rechazado: {motivo}. Abre la aplicación en "
                        "http://localhost:8000 en esta misma máquina, recarga la página y vuelve a pulsar el botón, "
                        "o usa el comando python -m scripts.pronostico_experimental.", 403)
    corte = None
    if hasta_numero_sorteo.strip():
        if not hasta_numero_sorteo.strip().isdigit() or int(hasta_numero_sorteo) < 1:
            raise HTTPException(status_code=422, detail="El corte debe ser un número de sorteo positivo")
        corte = int(hasta_numero_sorteo)
    if not proteccion_local.CERROJO_DE_ENTRENAMIENTO.acquire(blocking=False):
        return _rechazo(request, juego_slug, codigo, "Ya hay un entrenamiento en curso. Espera a que termine y "
                        "vuelve a intentarlo.", 429)
    try:
        guardado = generar.ejecutar(codigo, hasta_numero_sorteo=corte)
    except (PronosticoExperimentalNoDisponibleError, JuegoNoEncontradoError) as error:
        return _rechazo(request, juego_slug, codigo, str(error), 422)
    finally:
        proteccion_local.CERROJO_DE_ENTRENAMIENTO.release()
    sufijo = "&reutilizado=1" if guardado.reutilizado else ""
    return RedirectResponse(url=f"/pronosticos/{juego_slug}?id={guardado.identificador}{sufijo}", status_code=303)


@router.get("/pronosticos/{juego_slug}/verificar")
def formulario_verificacion(juego_slug: str, request: Request, id: str = Query(...)):
    """Solo muestra el formulario: verificar reentrena y se hace por POST."""
    codigo = _codigo_pronostico(juego_slug)
    return templates.TemplateResponse(request=request, name="producto/pronostico_verificacion.html", context={
        **_base(request, "pronosticos", True), "slug": juego_slug, "nombre": NOMBRES[codigo],
        "identificador": id, "resultado": None, "token_local": proteccion_local.token_local()})


@router.post("/pronosticos/{juego_slug}/verificar")
def verificar_pronostico(juego_slug: str, request: Request, id: Annotated[str, Form()],
                         token_local: Annotated[str, Form()] = "",
                         verificar: VerificarPronosticoExperimental = Depends(get_verificar_pronostico)):
    codigo = _codigo_pronostico(juego_slug)
    motivo = proteccion_local.motivo_de_rechazo(request, token_local)
    if motivo is not None:
        return _rechazo(request, juego_slug, codigo, f"Verificación rechazada: {motivo}.", 403)
    if not proteccion_local.CERROJO_DE_ENTRENAMIENTO.acquire(blocking=False):
        return _rechazo(request, juego_slug, codigo, "Ya hay un entrenamiento en curso. Espera a que termine.", 429)
    try:
        resultado = verificar.ejecutar(codigo, id)
    except PronosticoExperimentalNoDisponibleError as error:
        resultado = {"identificador": id, "error": str(error)}
    finally:
        proteccion_local.CERROJO_DE_ENTRENAMIENTO.release()
    return templates.TemplateResponse(request=request, name="producto/pronostico_verificacion.html", context={
        **_base(request, "pronosticos", True), "slug": juego_slug, "nombre": NOMBRES[codigo],
        "identificador": id, "resultado": resultado, "token_local": proteccion_local.token_local()})
