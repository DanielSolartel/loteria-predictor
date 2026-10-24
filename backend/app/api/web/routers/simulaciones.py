"""
Router web de la Fase 7: simulaciones bajo el mecanismo uniforme.

- `GET /simulaciones`: los cuatro juegos (corte, sorteos, frescura, mecanismo,
  estadisticas fijadas y simulaciones guardadas en la tabla `simulaciones`),
  formulario y trabajos recientes. Solo lectura.
- `POST /simulaciones/simular`: trabajo en segundo plano (303 a su progreso;
  409 si el juego ya tiene una simulacion activa).
- `GET /simulaciones/ejecuciones/{id}` y `.../estado` (fragmento HTMX):
  progreso por lotes; se puede recargar sin iniciar otro trabajo.
- `GET /simulaciones/resultados/{id}`: fila verificada (integridad) con sus
  comparaciones; `exportar.json` y `exportar.csv` derivados de la fila.
- `POST /simulaciones/resultados/{id}/verificar`: integridad y coincidencia
  del historico hasta el corte con la base actual (la reproduccion completa
  se pide con `python -m scripts.simulaciones verificar --reproducir`).

Todos los POST: solo desde la propia maquina y con el token local
(`proteccion_local`). Ningun GET simula ni escribe.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.dependencies import get_lanzador_de_simulaciones, get_simulaciones
from app.api.web import proteccion_local
from app.api.web.routers.producto import _base, _conectada
from app.application.fase7 import motor as fm
from app.application.use_cases.operacion_diaria import EjecucionActivaError, identificador_valido, mensaje_legible
from app.application.use_cases.simulaciones import JUEGOS, NOMBRES, SLUGS, SimulacionesError, SimulacionesFase7
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
SLUG_A_CODIGO = {s: c for c, s in SLUGS.items()}
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "base_no_disponible": 503}
ESTADOS = {"terminado": ("bg-success", "terminada"), "reutilizado": ("bg-success", "resultado ya existente"),
           "muestra_insuficiente": ("bg-warning text-dark", "muestra insuficiente"),
           "historico_no_valido": ("bg-danger", "histórico no válido"), "no_valido": ("bg-danger", "petición no válida"),
           "base_no_disponible": ("bg-danger", "base no disponible"), "tiempo_agotado": ("bg-danger", "tiempo agotado"),
           "alterado": ("bg-danger", "fila alterada"), "fallo": ("bg-danger", "error"),
           "pendiente": ("bg-secondary", "pendiente"), "en_curso": ("bg-info text-dark", "en curso"),
           "interrumpido": ("bg-danger", "interrumpido")}
FASES = {"inicio": "Iniciando…", "obteniendo_datos": "Obteniendo el histórico hasta el corte (una lectura)…",
         "simulando": "Simulando", "publicando": "Publicando el resultado completo en la tabla simulaciones…"}


def _contexto(request: Request, db_conectada: bool) -> dict:
    return {**_base(request, "simulaciones", db_conectada), "nombres": NOMBRES, "slugs": SLUGS,
            "token_local": proteccion_local.token_local(), "estados": ESTADOS, "fases": FASES,
            "iteraciones_admitidas": fm.ITERACIONES_ADMITIDAS,
            "iteraciones_predeterminadas": fm.ITERACIONES_PREDETERMINADAS,
            "semilla_predeterminada": fm.SEMILLA_PREDETERMINADA, "semilla_maxima": fm.SEMILLA_MAXIMA}


def _error(request: Request, mensaje: str, status_code: int, **extra):
    return templates.TemplateResponse(request=request, name="simulaciones/error.html", status_code=status_code,
                                      context={**_contexto(request, True), "mensaje": mensaje, **extra})


def _rechazo(request: Request, token: str):
    motivo = proteccion_local.motivo_de_rechazo(request, token)
    if motivo is None:
        return None
    return _error(request, f"Acción rechazada: {motivo}. Abre la aplicación en esta misma máquina (por ejemplo "
                  "http://localhost:8004), recarga la página y vuelve a pulsar el botón.", 403)


def _entero_opcional(valor: str, nombre: str) -> int | None:
    texto = (valor or "").strip()
    if not texto:
        return None
    try:
        return int(texto)
    except ValueError:
        raise SimulacionesError("no_valido", f"{nombre} debe ser un número entero") from None


def _descarga(contenido: str, nombre: str, tipo: str) -> Response:
    return Response(content=contenido.encode("utf-8"), media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"',
                             "X-Content-Type-Options": "nosniff"})


@router.get("/simulaciones")
def inicio(request: Request, db: Session = Depends(get_db), servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    return templates.TemplateResponse(request=request, name="simulaciones/panel.html", context={
        **_contexto(request, _conectada(db)), "juegos": servicio.panel(), "ejecuciones": servicio.recientes(10),
        "catalogo": servicio.catalogo()})


@router.post("/simulaciones/simular")
def simular(request: Request, juego: Annotated[str, Form()] = "",
            iteraciones: Annotated[int, Form()] = fm.ITERACIONES_PREDETERMINADAS,
            semilla: Annotated[str, Form()] = "", corte: Annotated[str, Form()] = "",
            token_local: Annotated[str, Form()] = "", servicio: SimulacionesFase7 = Depends(get_simulaciones),
            lanzar=Depends(get_lanzador_de_simulaciones)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    codigo = SLUG_A_CODIGO.get(juego, juego)
    try:
        semilla_ = _entero_opcional(semilla, "la semilla")
        inicio_ = servicio.iniciar(codigo, iteraciones, fm.SEMILLA_PREDETERMINADA if semilla_ is None else semilla_,
                                   _entero_opcional(corte, "el corte"), "web")
    except SimulacionesError as error:
        return _error(request, f"Petición no válida: {error}", _CODIGO_HTTP.get(error.codigo, 400))
    except EjecucionActivaError as error:
        return _error(request, "Ya hay una simulación en curso para "
                      + ", ".join(NOMBRES.get(j, j) for j in sorted(error.activas)) + ". Ábrela o espera a que termine.",
                      409, activas=error.activas)
    except OSError as error:
        return _error(request, f"No se pudo registrar el trabajo: {mensaje_legible(error)}", 500)
    try:
        lanzar(servicio.ejecutar, inicio_)
    except Exception as error:  # no se pudo crear el hilo: nada queda falsamente activo
        servicio.abortar(inicio_, str(error))
        return _error(request, f"No se pudo iniciar el trabajo: {mensaje_legible(error)}", 500)
    return RedirectResponse(url=f"/simulaciones/ejecuciones/{inicio_.ejecucion['id']}", status_code=303)


def _ejecucion(identificador: str, servicio: SimulacionesFase7) -> dict:
    encontrada = servicio.consultar_ejecucion(identificador) if identificador_valido(identificador) else None
    if encontrada is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return encontrada


@router.get("/simulaciones/ejecuciones/{identificador}")
def ejecucion(identificador: str, request: Request, db: Session = Depends(get_db),
              servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    return templates.TemplateResponse(request=request, name="simulaciones/ejecucion.html", context={
        **_contexto(request, _conectada(db)), "e": _ejecucion(identificador, servicio)})


@router.get("/simulaciones/ejecuciones/{identificador}/estado")
def estado_ejecucion(identificador: str, request: Request, servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    """Fragmento HTMX del progreso (solo lectura)."""
    return templates.TemplateResponse(request=request, name="simulaciones/_ejecucion_estado.html", context={
        "e": _ejecucion(identificador, servicio), "nombres": NOMBRES, "estados": ESTADOS, "fases": FASES})


def _fila(request: Request, identificador: str, servicio: SimulacionesFase7):
    try:
        return servicio.obtener(identificador), None
    except SimulacionesError as error:
        return None, _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))


@router.get("/simulaciones/resultados/{identificador}")
def resultado(identificador: str, request: Request, db: Session = Depends(get_db),
              servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    fila, error = _fila(request, identificador, servicio)
    if error is not None:
        return error
    return templates.TemplateResponse(request=request, name="simulaciones/resultado.html", context={
        **_contexto(request, _conectada(db)), "f": fila, "p": fila["parametros"],
        "c": fila["resultado_resumen"]["contenido"], "x": fila["resultado_resumen"]["ejecucion"]})


@router.get("/simulaciones/resultados/{identificador}/exportar.json")
def exportar_json(identificador: str, request: Request, servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    try:
        return _descarga(servicio.exportar_json(identificador), f"simulacion-{identificador}.json", "application/json")
    except SimulacionesError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))


@router.get("/simulaciones/resultados/{identificador}/exportar.csv")
def exportar_csv(identificador: str, request: Request, servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    try:
        return _descarga(servicio.exportar_csv(identificador), f"simulacion-{identificador}.csv",
                         "text/csv; charset=utf-8")
    except SimulacionesError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))


@router.post("/simulaciones/resultados/{identificador}/verificar")
def verificar(identificador: str, request: Request, token_local: Annotated[str, Form()] = "",
              db: Session = Depends(get_db), servicio: SimulacionesFase7 = Depends(get_simulaciones)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        r = servicio.verificar(identificador, reproducir=False)
    except SimulacionesError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="simulaciones/verificacion.html", context={
        **_contexto(request, _conectada(db)), "r": r})
