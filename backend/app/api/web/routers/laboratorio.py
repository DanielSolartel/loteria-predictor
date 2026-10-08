"""
Router web de Producto 4: laboratorio de modelos.

- `GET /laboratorio`: los cuatro juegos (muestra, corte, frescura, ultimo
  experimento) y las ejecuciones recientes. Solo lectura.
- `GET /laboratorio/{slug}`: muestra, catalogo con parametros legibles,
  historial de experimentos, lineas con pronosticos y el formulario.
- `POST /laboratorio/comparar`: «Comparar modelos» de un juego o de todos.
  Solo desde la propia maquina y con el token local (`proteccion_local`).
  Responde 303 en seguida; la comparacion sigue en otro hilo. 409 si ya hay
  una comparacion activa para ese juego.
- `GET /laboratorio/experimentos/{id}`: con el identificador de una
  ejecucion, su progreso (se puede recargar o abrir en otra pestana sin
  iniciar otro trabajo); con la clave de un experimento, su informe.
- `POST /laboratorio/experimentos/{clave}/generar`: «Generar pronostico con
  este modelo» (POST protegido). Usa la receta y el historico congelado del
  experimento; misma entrada -> el mismo pronostico.
- `POST .../verificar`: integridad, reproduccion y coincidencia con la base
  (reentrena; POST protegido).
- `GET /laboratorio/pronosticos/{clave}`: pronostico del laboratorio.
- `GET /laboratorio/{slug}/seguimiento`: resultados observados por linea.

Ningun GET entrena, importa ni escribe.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.dependencies import get_laboratorio, get_lanzador_de_laboratorio
from app.api.web import proteccion_local
from app.api.web.routers.operacion import grafica
from app.api.web.routers.producto import _base, _conectada
from app.application.ml import laboratorio_evaluacion as le
from app.application.use_cases.laboratorio import JUEGOS, NOMBRES, SLUGS, LaboratorioDeModelos, LaboratorioError
from app.application.use_cases.operacion_diaria import EjecucionActivaError, identificador_valido, mensaje_legible
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
SLUG_A_CODIGO = {s: c for c, s in SLUGS.items()}
ESTADOS_RESUMEN = {"menor_perdida_en_esta_evaluacion": "Menor pérdida en esta evaluación",
                   "la_uniforme_fue_mejor": "La uniforme fue mejor", "empate": "Empate",
                   "comparacion_incompleta": "Comparación incompleta"}
VEREDICTOS = {"menor_perdida_que_la_uniforme_en_esta_evaluacion": "menor pérdida que la uniforme en esta evaluación",
              "la_uniforme_fue_mejor": "la uniforme fue mejor", "empate": "empate", "referencia": "referencia"}
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409,
                "muestra_insuficiente": 422, "no_converge": 422, "clase_insuficiente": 422, "salida_invalida": 422,
                "fallo_de_ajuste": 422, "fallo_del_trabajador": 500}


def _contexto(request: Request, db_conectada: bool) -> dict:
    return {**_base(request, "laboratorio", db_conectada), "nombres": NOMBRES, "slugs": SLUGS,
            "token_local": proteccion_local.token_local(), "estados_resumen": ESTADOS_RESUMEN,
            "veredictos": VEREDICTOS}


def _error(request: Request, mensaje: str, status_code: int, **extra):
    return templates.TemplateResponse(request=request, name="laboratorio/error.html", status_code=status_code,
                                      context={**_contexto(request, True), "mensaje": mensaje, **extra})


def _rechazo(request: Request, token: str):
    motivo = proteccion_local.motivo_de_rechazo(request, token)
    if motivo is None:
        return None
    return _error(request, f"Acción rechazada: {motivo}. Abre la aplicación en esta misma máquina (por ejemplo "
                  "http://localhost:8003), recarga la página y vuelve a pulsar el botón.", 403)


def _codigo(slug: str) -> str:
    if slug not in SLUG_A_CODIGO:
        raise HTTPException(status_code=404, detail=f"Juego no admitido: {slug}")
    return SLUG_A_CODIGO[slug]


@router.get("/laboratorio")
def inicio(request: Request, db: Session = Depends(get_db), lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    return templates.TemplateResponse(request=request, name="laboratorio/panel.html", context={
        **_contexto(request, _conectada(db)), "juegos": lab.panel(), "ejecuciones": lab.recientes(10),
        "max_bloques": le.MAXIMO_BLOQUES})


@router.get("/laboratorio/experimentos/{identificador}")
def experimento(identificador: str, request: Request, db: Session = Depends(get_db),
                lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    if identificador_valido(identificador):
        ejecucion = lab.consultar_ejecucion(identificador)
        if ejecucion is None:
            raise HTTPException(status_code=404, detail="Ejecución no encontrada")
        return templates.TemplateResponse(request=request, name="laboratorio/ejecucion.html", context={
            **_contexto(request, _conectada(db)), "e": ejecucion})
    try:
        guardado = lab.experimento(identificador)
    except LaboratorioError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    informe = guardado.artefacto
    graficas = {c["id"]: grafica(_serie(c["por_objetivo"])) for c in informe["candidatos"]
                if c["estado"] == "completo" and c["familia"] != "uniforme"}
    return templates.TemplateResponse(request=request, name="laboratorio/informe.html", context={
        **_contexto(request, _conectada(db)), "i": informe, "clave": guardado.identificador,
        "base": lab.estado_frente_a_la_base(informe), "graficas": graficas,
        "pronosticos": {c["id"] for c in informe["candidatos"] if c["genera_pronostico"]}})


def _serie(por_objetivo: list[dict]) -> list[dict]:
    acumulada, serie = 0.0, []
    for f in por_objetivo:
        acumulada += f["diferencia_log_loss"]
        serie.append({"objetivo": f["objetivo"], "diferencia": f["diferencia_log_loss"], "acumulada": acumulada})
    return serie


@router.get("/laboratorio/experimentos/{identificador}/estado")
def estado_ejecucion(identificador: str, request: Request, lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    """Fragmento HTMX del progreso (solo lectura)."""
    ejecucion = lab.consultar_ejecucion(identificador) if identificador_valido(identificador) else None
    if ejecucion is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return templates.TemplateResponse(request=request, name="laboratorio/_ejecucion_estado.html", context={
        "e": ejecucion, "nombres": NOMBRES, "estados_resumen": ESTADOS_RESUMEN})


@router.post("/laboratorio/comparar")
def comparar(request: Request, juego: Annotated[str, Form()] = "", bloques: Annotated[int, Form()] = le.MAXIMO_BLOQUES,
             token_local: Annotated[str, Form()] = "", lab: LaboratorioDeModelos = Depends(get_laboratorio),
             lanzar=Depends(get_lanzador_de_laboratorio)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    juegos = list(JUEGOS) if juego == "todos" else [SLUG_A_CODIGO.get(juego, juego)]
    try:
        protocolo = le.Protocolo(bloques=bloques)
        inicio_ = lab.iniciar_comparacion(juegos, protocolo, "web")
    except (ValueError, LaboratorioError) as error:
        return _error(request, f"Petición no válida: {error}", 422)
    except EjecucionActivaError as error:
        return _error(request, "Ya hay una comparación en curso para "
                      + ", ".join(NOMBRES[j] for j in sorted(error.activas)) + ". Ábrela o espera a que termine.",
                      409, activas=error.activas)
    except OSError as error:
        return _error(request, f"No se pudo registrar la comparación: {mensaje_legible(error)}", 500)
    try:
        lanzar(lab.ejecutar_comparacion, inicio_)
    except Exception as error:  # no se pudo crear el hilo: nada queda falsamente activo
        lab.abortar(inicio_, str(error))
        return _error(request, f"No se pudo iniciar la comparación: {mensaje_legible(error)}", 500)
    return RedirectResponse(url=f"/laboratorio/experimentos/{inicio_.ejecucion['id']}", status_code=303)


@router.post("/laboratorio/experimentos/{clave}/generar")
def generar(clave: str, request: Request, modelo: Annotated[str, Form()] = "",
            token_local: Annotated[str, Form()] = "", lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        guardado = lab.generar(clave, modelo)
    except LaboratorioError as error:
        return _error(request, f"No se generó el pronóstico: {error}", _CODIGO_HTTP.get(error.codigo, 400))
    except OSError as error:
        return _error(request, f"No se pudo guardar el pronóstico: {mensaje_legible(error)}", 500)
    sufijo = "?reutilizado=1" if guardado.reutilizado else ""
    return RedirectResponse(url=f"/laboratorio/pronosticos/{guardado.identificador}{sufijo}", status_code=303)


@router.post("/laboratorio/experimentos/{clave}/verificar")
def verificar_experimento(clave: str, request: Request, token_local: Annotated[str, Form()] = "",
                          db: Session = Depends(get_db), lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        resultado = lab.verificar_experimento(clave)
    except LaboratorioError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="laboratorio/verificacion.html", context={
        **_contexto(request, _conectada(db)), "r": resultado, "tipo": "experimento", "clave": clave})


@router.get("/laboratorio/pronosticos/{clave}")
def pronostico(clave: str, request: Request, reutilizado: int = Query(default=0), db: Session = Depends(get_db),
               lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    try:
        guardado = lab.pronostico(clave)
    except LaboratorioError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="laboratorio/pronostico.html", context={
        **_contexto(request, _conectada(db)), "g": guardado, "a": guardado.artefacto, "reutilizado": bool(reutilizado),
        "observado": lab.estado_del_pronostico(guardado.artefacto)})


@router.post("/laboratorio/pronosticos/{clave}/verificar")
def verificar_pronostico(clave: str, request: Request, token_local: Annotated[str, Form()] = "",
                         db: Session = Depends(get_db), lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        resultado = lab.verificar_pronostico(clave)
    except LaboratorioError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="laboratorio/verificacion.html", context={
        **_contexto(request, _conectada(db)), "r": resultado, "tipo": "pronostico", "clave": clave})


@router.get("/laboratorio/{slug}/seguimiento")
def seguimiento(slug: str, request: Request, linea: str | None = Query(default=None),
                tipo: str = Query(default="seguimiento"), db: Session = Depends(get_db),
                lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    codigo = _codigo(slug)
    try:
        datos = lab.seguimiento(codigo, linea or None, tipo)
    except LaboratorioError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="laboratorio/seguimiento.html", context={
        **_contexto(request, _conectada(db)), "juego": codigo, "datos": datos, "linea": linea, "tipo": tipo,
        "todas_las_lineas": lab.lineas(codigo)})


@router.get("/laboratorio/{slug}")
def juego(slug: str, request: Request, db: Session = Depends(get_db),
          lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    codigo = _codigo(slug)
    return templates.TemplateResponse(request=request, name="laboratorio/juego.html", context={
        **_contexto(request, _conectada(db)), "juego": codigo, "d": lab.diagnostico(codigo),
        "max_bloques": le.MAXIMO_BLOQUES})
