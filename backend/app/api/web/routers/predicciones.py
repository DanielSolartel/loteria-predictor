"""
Router web de la Fase 4: centro de predicciones de los cuatro juegos.

- `GET /predicciones`: configuracion elegida, version registrada, estado de la
  base y ultima prediccion de cada juego. Solo lectura.
- `GET /predicciones/{slug}`: la prediccion (cartera de la configuracion) con
  combinaciones, fuertes y debiles, explicacion, proyeccion a la tabla
  `predicciones` y enlaces a los artefactos originales y sus resultados.
  `?cartera=<clave>` abre otra emision del centro.
- `GET /predicciones/{slug}/fiabilidad`: rendimiento observado e incertidumbre
  por linea y tipo de evaluacion (`?hasta=<sorteo>` limita la evidencia).
- `POST /predicciones/{slug}/generar` (cantidad `configuracion` o `cinco`) y
  `POST /predicciones/{slug}/explicar`: escriben; solo desde la propia maquina
  y con el token local (`proteccion_local`).
- `GET /predicciones/ejecuciones/{id}`: progreso de una generacion.

Ningun GET entrena, importa, genera, inicia trabajadores ni escribe.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.dependencies import get_lanzador_de_predicciones, get_predicciones
from app.api.parametros import CorteOpcional
from app.api.web import proteccion_local
from app.api.web.routers.producto import _base, _conectada
from app.application.ml import predicciones_fiabilidad as pf
from app.application.use_cases.operacion_diaria import EjecucionActivaError, identificador_valido, mensaje_legible
from app.application.use_cases.predicciones import NOMBRES, SLUGS, CentroDePredicciones, PrediccionesError
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["formatear_cifra"] = pf.formatear_cifra
SLUG_A_CODIGO = {s: c for c, s in SLUGS.items()}
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409, "incompatible": 409,
                "sin_configuracion": 409, "fallo_del_trabajador": 500, "muestra_insuficiente": 422}
ESTADOS_FIABILIDAD = {"estimable": "estimable", "muestra_insuficiente": "muestra insuficiente",
                      "sin_resultados": "sin resultados todavía", "sin_base": "base no disponible",
                      "excluidas": "emisiones excluidas", "sin_datos": "sin datos", "no_disponible": "no disponible",
                      "fallo_de_calculo": "fallo de cálculo"}
COMPONENTES = {"numeros": "Números principales", "pares": "Pares número-color", "superbalota": "Superbalota (aparte)"}
TIPOS = {"seguimiento": "Seguimiento", "retrospectiva": "Retrospectiva",
         "evaluacion_de_receta": "Evaluación de la receta (informe del laboratorio)"}


def _contexto(request: Request, db_conectada: bool) -> dict:
    return {**_base(request, "predicciones", db_conectada), "nombres": NOMBRES, "slugs": SLUGS,
            "token_local": proteccion_local.token_local(), "estados_fiabilidad": ESTADOS_FIABILIDAD,
            "componentes": COMPONENTES, "tipos": TIPOS, "metodo": pf.METODO}


def _error(request: Request, mensaje: str, status_code: int, **extra):
    return templates.TemplateResponse(request=request, name="predicciones/error.html", status_code=status_code,
                                      context={**_contexto(request, True), "mensaje": mensaje, **extra})


def _codigo(slug: str) -> str:
    if slug not in SLUG_A_CODIGO:
        raise HTTPException(status_code=404, detail=f"Juego no admitido: {slug}")
    return SLUG_A_CODIGO[slug]


def _rechazo(request: Request, token: str):
    motivo = proteccion_local.motivo_de_rechazo(request, token)
    if motivo is None:
        return None
    return _error(request, f"Acción rechazada: {motivo}. Abre la aplicación en esta misma máquina (por ejemplo "
                  "http://localhost:8007), recarga la página y vuelve a pulsar el botón.", 403)


def barras_ranking(filas: list[dict], ancho: int = 520, alto_fila: int = 18, margen: int = 70) -> dict:
    """Geometria SVG de barras horizontales: probabilidad emitida de cada
    candidato y linea de la referencia uniforme. Los valores se reservan
    en una columna fuera del area de barras y referencia; la tabla de la
    plantilla lista los mismos valores."""
    if not filas:
        return {"ancho": ancho, "alto": 0, "barras": [], "uniforme_x": None}
    maximo = max([f["probabilidad"] for f in filas] + [filas[0]["uniforme"]]) * 1.05 or 1.0
    util = ancho - margen - 60
    barras = []
    for i, f in enumerate(filas):
        c = f["candidato"]
        etiqueta = (f"{c[0]} {str(c[1]).lower()}" if isinstance(c, list) else c.lower() if isinstance(c, str)
                    else str(c))
        barras.append({"y": 6 + i * alto_fila, "ancho": round(f["probabilidad"] / maximo * util, 1),
                       "etiqueta": etiqueta, "valor": f["probabilidad"], "x_texto": margen - 6})
    return {"ancho": ancho, "alto": 12 + len(filas) * alto_fila, "barras": barras, "margen": margen,
            "uniforme_x": round(margen + filas[0]["uniforme"] / maximo * util, 1), "alto_fila": alto_fila,
            "valor_x": ancho - 5}


CORTAS = {"diferencia_log_loss": "Δ Log Loss", "diferencia_brier": "Δ Brier",
          "fuertes_observado_menos_esperado": "Aciertos − esperados (más probables)",
          "debiles_observado_menos_esperado": "Aciertos − esperados (menos probables)"}


def intervalos(metricas: dict, ancho: int = 640, margen: int = 250, alto_fila: int = 34) -> dict | None:
    """Geometria SVG de medias e intervalos: una fila por cifra con valor, cada
    una con SU propia escala simetrica alrededor de 0 (las cifras tienen
    unidades distintas: perdida por sorteo y aciertos por sorteo), con el 0 y
    los limites de la escala rotulados. Los mismos valores van en la tabla."""
    filas = [(k, m) for k, m in metricas.items() if m.get("media") is not None]
    if not filas:
        return None
    util = ancho - margen - 70
    centro = margen + util / 2
    salida = []
    for i, (k, m) in enumerate(filas):
        iv = m.get("intervalo")
        limite = max([abs(v) for v in [m["media"], *(iv or [])]] + [1e-12]) * 1.15
        escala = util / 2 / limite
        y = 16 + i * alto_fila
        salida.append({"y": y, "metrica": k, "etiqueta": CORTAS.get(k, k), "limite": limite,
                       "x": round(centro + m["media"] * escala, 1),
                       "x1": round(centro + iv[0] * escala, 1) if iv else None,
                       "x2": round(centro + iv[1] * escala, 1) if iv else None})
    return {"ancho": ancho, "alto": 14 + len(filas) * alto_fila, "cero": round(centro, 1), "filas": salida,
            "margen": margen, "derecha": margen + util, "alto_fila": alto_fila}


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

@router.get("/predicciones")
def indice(request: Request, db: Session = Depends(get_db), centro: CentroDePredicciones = Depends(get_predicciones)):
    return templates.TemplateResponse(request=request, name="predicciones/indice.html", context={
        **_contexto(request, _conectada(db)), "datos": centro.indice()})


@router.get("/predicciones/ejecuciones/{identificador}")
def ejecucion(identificador: str, request: Request, db: Session = Depends(get_db),
              centro: CentroDePredicciones = Depends(get_predicciones)):
    if not identificador_valido(identificador):
        raise HTTPException(status_code=404, detail="Identificador no valido")
    e = centro.ejecucion(identificador)
    if e is None:
        raise HTTPException(status_code=404, detail="No existe esa ejecucion")
    return templates.TemplateResponse(request=request, name="predicciones/ejecucion.html", context={
        **_contexto(request, _conectada(db)), "e": e})


@router.get("/predicciones/ejecuciones/{identificador}/estado")
def estado_de_ejecucion(identificador: str, request: Request, centro: CentroDePredicciones = Depends(get_predicciones)):
    if not identificador_valido(identificador):
        raise HTTPException(status_code=404, detail="Identificador no valido")
    e = centro.ejecucion(identificador)
    if e is None:
        raise HTTPException(status_code=404, detail="No existe esa ejecucion")
    return templates.TemplateResponse(request=request, name="predicciones/_ejecucion_estado.html", context={
        **_contexto(request, True), "e": e})


@router.get("/predicciones/{slug}")
def juego(slug: str, request: Request, cartera: str | None = Query(None), db: Session = Depends(get_db),
          centro: CentroDePredicciones = Depends(get_predicciones)):
    codigo = _codigo(slug)
    try:
        datos = centro.consultar(codigo, cartera)
    except PrediccionesError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 422))
    p = datos["prediccion"]
    graficas = {}
    if p:
        rk = p["rankings"]
        principal = rk.get("pares") or rk.get("numeros")
        graficas["fuertes"] = barras_ranking(principal["fuertes"])
        graficas["debiles"] = barras_ranking(principal["debiles"])
        if rk.get("superbalota"):
            graficas["superbalota"] = barras_ranking(rk["superbalota"]["todos"])
        if rk.get("pares"):
            graficas["numeros"] = barras_ranking(rk["numeros"]["todos"])
            graficas["colores"] = barras_ranking(rk["colores"]["todos"])
    fiabilidad = None
    if p:
        try:
            fiabilidad = centro.fiabilidad(codigo, hasta=p["datos"]["corte"])
        except PrediccionesError as error:
            fiabilidad = {"error": str(error)}
    return templates.TemplateResponse(request=request, name="predicciones/juego.html", context={
        **_contexto(request, _conectada(db)), "d": datos, "p": p, "graficas": graficas, "fiabilidad": fiabilidad,
        "colores": codigo == "COLORLOTO"})


@router.get("/predicciones/{slug}/fiabilidad")
def fiabilidad(slug: str, request: Request, linea: str | None = Query(None), hasta: CorteOpcional = None,
               db: Session = Depends(get_db), centro: CentroDePredicciones = Depends(get_predicciones)):
    codigo = _codigo(slug)
    try:
        datos = centro.fiabilidad(codigo, linea or None, hasta)
    except PrediccionesError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 422))
    graficas = {}
    for i, l in enumerate(datos["lineas"]):
        for ev in l["evaluaciones"]:
            for comp, c in ev["componentes"].items():
                if c.get("metricas"):
                    graficas[f"{i}-{ev['tipo']}-{comp}"] = intervalos(c["metricas"])
    for comp, c in (datos["receta"].get("componentes") or {}).items():
        if c.get("metricas"):
            graficas[f"receta-{comp}"] = intervalos(c["metricas"])
    return templates.TemplateResponse(request=request, name="predicciones/fiabilidad.html", context={
        **_contexto(request, _conectada(db)), "f": datos, "graficas": graficas, "colores": codigo == "COLORLOTO"})


# ---------------------------------------------------------------------------
# Acciones (escriben)
# ---------------------------------------------------------------------------

@router.post("/predicciones/{slug}/generar")
def generar(slug: str, request: Request, token_local: str = Form(""), cantidad: str = Form("configuracion"),
            centro: CentroDePredicciones = Depends(get_predicciones), lanzar=Depends(get_lanzador_de_predicciones)):
    codigo = _codigo(slug)
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        inicio_ = centro.iniciar(codigo, cantidad, "web")
    except PrediccionesError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 422))
    except EjecucionActivaError:
        return _error(request, f"Ya hay un trabajo de carteras en curso para {NOMBRES[codigo]}. Ábrelo desde "
                      "/carteras o espera a que termine.", 409)
    except OSError as error:
        return _error(request, f"No se pudo registrar el trabajo: {mensaje_legible(error)}", 500)
    try:
        lanzar(centro.ejecutar, inicio_)
    except Exception as error:  # no se pudo crear el hilo: nada queda falsamente activo
        centro.abortar(inicio_, str(error))
        return _error(request, f"No se pudo iniciar el trabajo: {mensaje_legible(error)}", 500)
    return RedirectResponse(url=f"/predicciones/ejecuciones/{inicio_.identificador}", status_code=303)


@router.post("/predicciones/{slug}/explicar")
def explicar(slug: str, request: Request, token_local: str = Form(""), cartera: str = Form(""),
             centro: CentroDePredicciones = Depends(get_predicciones)):
    codigo = _codigo(slug)
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        r = centro.explicar(cartera, "web", codigo)
    except PrediccionesError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 422))
    return RedirectResponse(url=f"/predicciones/{slug}?cartera={r['cartera']}#explicacion", status_code=303)
