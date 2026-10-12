"""
Router web de Producto 5: modelo combinado, carteras y simulacion.

- `GET /carteras`: los cuatro juegos (corte, frescura, configuracion vigente,
  ultima comparacion) y las ejecuciones recientes. Solo lectura.
- `GET /carteras/{slug}`: modelos admitidos con sus requisitos, formulario de
  cartera, configuracion versionada, comparaciones y lineas guardadas.
- `POST /carteras/comparar`, `POST /carteras/generar`,
  `POST /carteras/configuradas`, `POST /carteras/guardadas/{clave}/simular`:
  trabajos en segundo plano (responden 303 a su progreso; 409 si el juego ya
  tiene un trabajo activo). `POST /carteras/{slug}/configurar` guarda una
  version nueva de la configuracion. `POST .../verificar` comprueba
  integridad, reproduccion y base actual. Todos los POST: solo desde la
  propia maquina y con el token local (`proteccion_local`).
- `GET /carteras/ejecuciones/{id}`: progreso por juego (se puede recargar o
  abrir en otra pestana sin iniciar otro trabajo).
- `GET /carteras/comparaciones/{clave}`, `/carteras/guardadas/{clave}`,
  `/carteras/simulaciones/{clave}`: artefactos guardados; `exportar.json`
  (bytes canonicos) y `exportar.csv` (UTF-8, sin formulas).
- `GET /carteras/{slug}/seguimiento`: aciertos observados por linea.

Ningun GET entrena, simula, importa ni escribe.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.dependencies import get_carteras, get_lanzador_de_carteras
from app.api.web import proteccion_local
from app.api.web.routers.operacion import grafica
from app.api.web.routers.producto import _base, _conectada
from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_construccion as cc
from app.application.ml import carteras_ensemble as ce
from app.application.ml import carteras_simulacion as cs
from app.application.use_cases.carteras import JUEGOS, NOMBRES, SLUGS, CarterasDeModelos, CarterasError
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
TRABAJOS = {"comparacion": "Comparación del modelo combinado", "cartera": "Generación de cartera",
            "simulacion": "Simulación de cartera", "carteras_configuradas": "Carteras configuradas"}
ESCENARIOS = {"sorteos_uniformes": "Sorteos uniformes", "muestreo_ponderado": "Hipótesis de muestreo ponderado"}
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409,
                "muestra_insuficiente": 422, "parcial": 409, "sin_configuracion": 409, "fallo_del_trabajador": 500,
                "tiempo_agotado": 504}


def _contexto(request: Request, db_conectada: bool) -> dict:
    return {**_base(request, "carteras", db_conectada), "nombres": NOMBRES, "slugs": SLUGS,
            "token_local": proteccion_local.token_local(), "estados_resumen": ESTADOS_RESUMEN,
            "veredictos": VEREDICTOS, "trabajos": TRABAJOS, "escenarios": ESCENARIOS}


def _error(request: Request, mensaje: str, status_code: int, **extra):
    return templates.TemplateResponse(request=request, name="carteras/error.html", status_code=status_code,
                                      context={**_contexto(request, True), "mensaje": mensaje, **extra})


def _rechazo(request: Request, token: str):
    motivo = proteccion_local.motivo_de_rechazo(request, token)
    if motivo is None:
        return None
    return _error(request, f"Acción rechazada: {motivo}. Abre la aplicación en esta misma máquina (por ejemplo "
                  "http://localhost:8004), recarga la página y vuelve a pulsar el botón.", 403)


def _codigo(slug: str) -> str:
    if slug not in SLUG_A_CODIGO:
        raise HTTPException(status_code=404, detail=f"Juego no admitido: {slug}")
    return SLUG_A_CODIGO[slug]


def _lanzar(request: Request, servicio: CarterasDeModelos, lanzar, tipo: str, juegos: list[str], parametros: dict):
    """Inicia un trabajo y redirige a su progreso (o devuelve la pagina de error)."""
    try:
        inicio_ = servicio.iniciar(tipo, juegos, parametros, "web")
    except (CarterasError, cc.ParametrosNoValidos, cs.SimulacionNoValida, ValueError) as error:
        return _error(request, f"Petición no válida: {error}", 422)
    except EjecucionActivaError as error:
        return _error(request, "Ya hay un trabajo de carteras en curso para "
                      + ", ".join(NOMBRES[j] for j in sorted(error.activas)) + ". Ábrelo o espera a que termine.",
                      409, activas=error.activas)
    except OSError as error:
        return _error(request, f"No se pudo registrar el trabajo: {mensaje_legible(error)}", 500)
    try:
        lanzar(servicio.ejecutar, inicio_)
    except Exception as error:  # no se pudo crear el hilo: nada queda falsamente activo
        servicio.abortar(inicio_, str(error))
        return _error(request, f"No se pudo iniciar el trabajo: {mensaje_legible(error)}", 500)
    return RedirectResponse(url=f"/carteras/ejecuciones/{inicio_.ejecucion['id']}", status_code=303)


def _juegos_de(juego: str) -> list[str]:
    return list(JUEGOS) if juego == "todos" else [SLUG_A_CODIGO.get(juego, juego)]


def barras(series: dict[str, list[float]], etiquetas: list, ancho: int = 640, alto: int = 200,
           margen: int = 30) -> dict:
    """Geometria SVG de barras agrupadas (sin bibliotecas externas). Los mismos
    valores se listan en la tabla accesible de la plantilla."""
    maximo = max([v for s in series.values() for v in s] + [1e-12])
    grupos = len(etiquetas)
    ancho_grupo = (ancho - 2 * margen) / max(grupos, 1)
    ancho_barra = ancho_grupo * 0.8 / max(len(series), 1)
    rects = []
    for j, (nombre, valores) in enumerate(series.items()):
        for i, v in enumerate(valores):
            h = round(v / maximo * (alto - 2 * margen), 1)
            rects.append({"serie": j, "nombre": nombre, "x": round(margen + i * ancho_grupo + ancho_grupo * 0.1
                                                                    + j * ancho_barra, 1),
                          "y": round(alto - margen - h, 1), "alto": h, "ancho": round(ancho_barra - 1, 1),
                          "valor": v, "etiqueta": etiquetas[i]})
    return {"ancho": ancho, "alto": alto, "margen": margen, "rects": rects, "maximo": maximo,
            "ejes": [{"x": round(margen + (i + 0.5) * ancho_grupo, 1), "etiqueta": e} for i, e in enumerate(etiquetas)]}


def _graficas_de_simulacion(resultados: dict) -> dict:
    salida = {}
    for escenario, r in resultados.items():
        elegida = r["carteras"]["elegida"]["maximo_de_la_cartera"]
        uniforme = r["carteras"]["uniforme"]["maximo_de_la_cartera"]
        n = elegida["denominador"]
        salida[escenario] = barras({"elegida": [c / n for c in elegida["conteos"]],
                                    "uniforme": [c / n for c in uniforme["conteos"]]},
                                   list(range(len(elegida["conteos"]))))
    return salida


def _serie(por_objetivo: list[dict]) -> list[dict]:
    acumulada, serie = 0.0, []
    for f in por_objetivo:
        acumulada += f["diferencia_log_loss"]
        serie.append({"objetivo": f["objetivo"], "diferencia": f["diferencia_log_loss"], "acumulada": acumulada})
    return serie


def _ranking(fuente: dict) -> list[dict]:
    """Probabilidades del vector fuente de mayor a menor (desempate estable por candidato)."""
    filas = [{"candidato": c, "probabilidad": p} for c, p in zip(fuente["candidatos"], fuente["probabilidades"])]
    return sorted(filas, key=lambda f: -f["probabilidad"])


def _descarga(contenido: bytes | str, nombre: str, tipo: str) -> Response:
    datos = contenido.encode("utf-8") if isinstance(contenido, str) else contenido
    return Response(content=datos, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"',
                             "X-Content-Type-Options": "nosniff"})


# ---------------------------------------------------------------------------
# Paginas de lectura
# ---------------------------------------------------------------------------

@router.get("/carteras")
def inicio(request: Request, db: Session = Depends(get_db), servicio: CarterasDeModelos = Depends(get_carteras)):
    return templates.TemplateResponse(request=request, name="carteras/panel.html", context={
        **_contexto(request, _conectada(db)), "juegos": servicio.panel(), "ejecuciones": servicio.recientes(10),
        "max_bloques": ce.MAXIMO_BLOQUES})


@router.get("/carteras/ejecuciones/{identificador}")
def ejecucion(identificador: str, request: Request, db: Session = Depends(get_db),
              servicio: CarterasDeModelos = Depends(get_carteras)):
    encontrada = servicio.consultar_ejecucion(identificador) if identificador_valido(identificador) else None
    if encontrada is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return templates.TemplateResponse(request=request, name="carteras/ejecucion.html", context={
        **_contexto(request, _conectada(db)), "e": encontrada})


@router.get("/carteras/ejecuciones/{identificador}/estado")
def estado_ejecucion(identificador: str, request: Request, servicio: CarterasDeModelos = Depends(get_carteras)):
    """Fragmento HTMX del progreso (solo lectura)."""
    encontrada = servicio.consultar_ejecucion(identificador) if identificador_valido(identificador) else None
    if encontrada is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return templates.TemplateResponse(request=request, name="carteras/_ejecucion_estado.html", context={
        "e": encontrada, "nombres": NOMBRES, "estados_resumen": ESTADOS_RESUMEN, "trabajos": TRABAJOS,
        "escenarios": ESCENARIOS})


@router.get("/carteras/comparaciones/{clave}")
def comparacion(clave: str, request: Request, db: Session = Depends(get_db),
                servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        guardado = servicio.comparacion(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    informe = guardado.artefacto
    graficas = {c["id"]: grafica(_serie(c["por_objetivo"])) for c in informe["candidatos"]
                if c["estado"] == "completo" and c["familia"] != "uniforme"}
    return templates.TemplateResponse(request=request, name="carteras/comparacion.html", context={
        **_contexto(request, _conectada(db)), "i": informe, "clave": guardado.identificador,
        "base": servicio.estado_frente_a_la_base(informe), "graficas": graficas,
        "ensemble": next(c for c in informe["candidatos"] if c["id"] == ce.ID_ENSEMBLE)})


@router.get("/carteras/comparaciones/{clave}/exportar.json")
def exportar_comparacion(clave: str, request: Request, servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        guardado = servicio.comparacion(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return _descarga(ca.json_canonico(guardado.artefacto), f"comparacion-{guardado.juego}-{clave[:12]}.json",
                     "application/json")


@router.get("/carteras/guardadas/{clave}")
def cartera(clave: str, request: Request, reutilizado: int = Query(default=0), db: Session = Depends(get_db),
            servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        guardado = servicio.cartera(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="carteras/cartera.html", context={
        **_contexto(request, _conectada(db)), "g": guardado, "a": guardado.artefacto, "reutilizado": bool(reutilizado),
        "observado": servicio.observado_de_cartera(guardado.artefacto),
        "simulaciones": servicio.simulaciones_de_cartera(clave), "ranking_fuente": _ranking(guardado.artefacto["fuente"]),
        "sim": {
            "predeterminadas": cs.SIMULACIONES_PREDETERMINADAS, "minimas": cs.SIMULACIONES_MINIMAS,
            "maximas": cs.SIMULACIONES_MAXIMAS}})


@router.get("/carteras/guardadas/{clave}/exportar.csv")
def exportar_cartera_csv(clave: str, request: Request, servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        guardado = servicio.cartera(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return _descarga(ca.csv_de_cartera(guardado.artefacto), f"cartera-{guardado.juego}-{clave[:12]}.csv",
                     "text/csv; charset=utf-8")


@router.get("/carteras/guardadas/{clave}/exportar.json")
def exportar_cartera_json(clave: str, request: Request, servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        guardado = servicio.cartera(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return _descarga(ca.json_canonico(guardado.artefacto), f"cartera-{guardado.juego}-{clave[:12]}.json",
                     "application/json")


@router.get("/carteras/simulaciones/{clave}")
def simulacion(clave: str, request: Request, reutilizado: int = Query(default=0), db: Session = Depends(get_db),
               servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        guardado = servicio.simulacion(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    a = guardado.artefacto
    colores = a["juego"] == "COLORLOTO"
    identidades = {k: sorted(cc.identidad_de_combinacion(c, colores) for c in a["carteras"][k]["combinaciones"])
                   for k in ("elegida", "uniforme")}
    return templates.TemplateResponse(request=request, name="carteras/simulacion.html", context={
        **_contexto(request, _conectada(db)), "g": guardado, "a": a, "reutilizado": bool(reutilizado),
        "graficas": _graficas_de_simulacion(a["resultados"]),
        "identicas": identidades["elegida"] == identidades["uniforme"]})


@router.get("/carteras/simulaciones/{clave}/exportar.csv")
def exportar_simulacion_csv(clave: str, request: Request, servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        guardado = servicio.simulacion(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return _descarga(ca.csv_de_simulacion(guardado.artefacto),
                     f"simulacion-{guardado.juego}-{clave[:12]}.csv", "text/csv; charset=utf-8")


@router.get("/carteras/simulaciones/{clave}/exportar.json")
def exportar_simulacion_json(clave: str, request: Request, servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        guardado = servicio.simulacion(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return _descarga(ca.json_canonico(guardado.artefacto), f"simulacion-{guardado.juego}-{clave[:12]}.json",
                     "application/json")


@router.get("/carteras/{slug}/seguimiento")
def seguimiento(slug: str, request: Request, linea: str | None = Query(default=None),
                tipo: str = Query(default="seguimiento"), db: Session = Depends(get_db),
                servicio: CarterasDeModelos = Depends(get_carteras)):
    codigo = _codigo(slug)
    try:
        datos = servicio.seguimiento(codigo, linea or None, tipo)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="carteras/seguimiento.html", context={
        **_contexto(request, _conectada(db)), "juego": codigo, "datos": datos, "linea": linea, "tipo": tipo,
        "todas_las_lineas": servicio.lineas(codigo)})


@router.get("/carteras/{slug}")
def juego(slug: str, request: Request, modelo: str | None = Query(default=None),
          registrado: str | None = Query(default=None), db: Session = Depends(get_db),
          servicio: CarterasDeModelos = Depends(get_carteras)):
    """`modelo` y `registrado` (Fase 3) solo PRESELECCIONAN el formulario de
    configuracion; no guardan nada."""
    codigo = _codigo(slug)
    lineas = []
    for nombre in servicio.lineas(codigo):
        elementos = servicio.carteras_de_linea(codigo, nombre)
        lineas.append({"id": nombre, "elementos": elementos[:5], "total": len(elementos)})
    return templates.TemplateResponse(request=request, name="carteras/juego.html", context={
        **_contexto(request, _conectada(db)), "juego": codigo, "d": servicio.diagnostico(codigo), "lineas": lineas,
        "configuraciones": servicio.configuraciones(codigo), "max_bloques": ce.MAXIMO_BLOQUES,
        "cartera": servicio.catalogo()["cartera"], "registrados": servicio.modelos_registrados(codigo),
        "preseleccion": {"modelo": modelo, "registrado": registrado}})


# ---------------------------------------------------------------------------
# Acciones (POST protegidos)
# ---------------------------------------------------------------------------

@router.post("/carteras/comparar")
def comparar(request: Request, juego: Annotated[str, Form()] = "", bloques: Annotated[int, Form()] = ce.MAXIMO_BLOQUES,
             token_local: Annotated[str, Form()] = "", servicio: CarterasDeModelos = Depends(get_carteras),
             lanzar=Depends(get_lanzador_de_carteras)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    return _lanzar(request, servicio, lanzar, "comparacion", _juegos_de(juego), {"protocolo": {"bloques": bloques}})


@router.post("/carteras/generar")
def generar(request: Request, juego: Annotated[str, Form()] = "", modelo: Annotated[str, Form()] = "",
            cantidad: Annotated[int, Form()] = cc.CANTIDAD_PREDETERMINADA,
            diversidad: Annotated[str, Form()] = "libre", semilla: Annotated[int, Form()] = cc.SEMILLA_PREDETERMINADA,
            token_local: Annotated[str, Form()] = "", servicio: CarterasDeModelos = Depends(get_carteras),
            lanzar=Depends(get_lanzador_de_carteras)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    return _lanzar(request, servicio, lanzar, "cartera", _juegos_de(juego),
                   {"modelo": modelo, "cantidad": cantidad, "diversidad": diversidad, "semilla": semilla})


@router.post("/carteras/configuradas")
def configuradas(request: Request, juego: Annotated[str, Form()] = "todos", token_local: Annotated[str, Form()] = "",
                 servicio: CarterasDeModelos = Depends(get_carteras), lanzar=Depends(get_lanzador_de_carteras)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    return _lanzar(request, servicio, lanzar, "carteras_configuradas", _juegos_de(juego), {})


@router.post("/carteras/guardadas/{clave}/simular")
def simular(clave: str, request: Request, simulaciones: Annotated[int, Form()] = cs.SIMULACIONES_PREDETERMINADAS,
            semilla: Annotated[int, Form()] = cc.SEMILLA_PREDETERMINADA, token_local: Annotated[str, Form()] = "",
            servicio: CarterasDeModelos = Depends(get_carteras), lanzar=Depends(get_lanzador_de_carteras)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        guardado = servicio.cartera(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return _lanzar(request, servicio, lanzar, "simulacion", [guardado.juego],
                   {"cartera": clave, "simulaciones": simulaciones, "semilla": semilla})


@router.post("/carteras/{slug}/configurar")
def configurar(slug: str, request: Request, modelo: Annotated[str, Form()] = "",
               cantidad: Annotated[int, Form()] = cc.CANTIDAD_PREDETERMINADA,
               diversidad: Annotated[str, Form()] = "libre", semilla: Annotated[int, Form()] = cc.SEMILLA_PREDETERMINADA,
               registrado: Annotated[str, Form()] = "", token_local: Annotated[str, Form()] = "",
               servicio: CarterasDeModelos = Depends(get_carteras)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    codigo = _codigo(slug)
    try:
        servicio.configurar(codigo, modelo, cantidad, diversidad, semilla, origen="web", registrado=registrado or None)
    except CarterasError as error:
        return _error(request, f"Configuración no válida: {error}", _CODIGO_HTTP.get(error.codigo, 400))
    except OSError as error:
        return _error(request, f"No se pudo guardar la configuración: {mensaje_legible(error)}", 500)
    return RedirectResponse(url=f"/carteras/{slug}#configuracion", status_code=303)


def _verificacion(request: Request, db: Session, tipo: str, clave: str, funcion):
    try:
        resultado = funcion(clave)
    except CarterasError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="carteras/verificacion.html", context={
        **_contexto(request, _conectada(db)), "r": resultado, "tipo": tipo, "clave": clave})


@router.post("/carteras/comparaciones/{clave}/verificar")
def verificar_comparacion(clave: str, request: Request, token_local: Annotated[str, Form()] = "",
                          db: Session = Depends(get_db), servicio: CarterasDeModelos = Depends(get_carteras)):
    rechazo = _rechazo(request, token_local)
    return rechazo if rechazo is not None else _verificacion(request, db, "comparacion", clave,
                                                             servicio.verificar_comparacion)


@router.post("/carteras/guardadas/{clave}/verificar")
def verificar_cartera(clave: str, request: Request, token_local: Annotated[str, Form()] = "",
                      db: Session = Depends(get_db), servicio: CarterasDeModelos = Depends(get_carteras)):
    rechazo = _rechazo(request, token_local)
    return rechazo if rechazo is not None else _verificacion(request, db, "cartera", clave, servicio.verificar_cartera)


@router.post("/carteras/simulaciones/{clave}/verificar")
def verificar_simulacion(clave: str, request: Request, token_local: Annotated[str, Form()] = "",
                         db: Session = Depends(get_db), servicio: CarterasDeModelos = Depends(get_carteras)):
    rechazo = _rechazo(request, token_local)
    return rechazo if rechazo is not None else _verificacion(request, db, "simulacion", clave,
                                                             servicio.verificar_simulacion)
