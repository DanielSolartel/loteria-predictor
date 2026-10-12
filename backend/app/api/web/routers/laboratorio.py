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

Fase 3, modelos registrados:
- `POST /laboratorio/experimentos/{clave}/entrenar`: «Entrenar y guardar
  version» de un candidato del informe (POST protegido; progreso en la misma
  pagina de ejecuciones; misma entrada -> la misma version).
- `GET /laboratorio/modelos[?juego=slug]`: catalogo registrable y versiones de
  cada juego, con su compatibilidad y las incidencias del almacen.
- `GET /laboratorio/modelo/{clave}`: ficha (entrenamiento, variables,
  componentes, evaluacion asociada frente a la uniforme, procedencia).
- `POST /laboratorio/modelo/{clave}/verificar`: integridad, compatibilidad,
  carga restringida y pronostico de control (POST protegido).
- `POST /laboratorio/modelo/{clave}/generar`: pronostico con la version
  recargada, sin reentrenar (POST protegido).
Elegir la version para la operacion diaria se hace en la configuracion de
carteras (Producto 5); nada de esto la cambia.

Ningun GET entrena, carga un estimador, importa ni escribe.
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
from app.application.ml import laboratorio_modelos as lm
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
                "fallo_de_ajuste": 422, "fallo_del_trabajador": 500, "incompatible": 409, "corte_no_valido": 422,
                "estimador_no_admitido": 409, "no_registrable": 422, "tiempo_agotado": 504,
                "base_no_disponible": 503}
ESTADOS_DE_ENTRENAMIENTO = {"terminado": "versión nueva guardada", "reutilizado": "versión ya existente (misma entrada)",
                            "tiempo_agotado": "tiempo agotado", "no_registrable": "no registrable",
                            "alterado": "versión existente alterada", "muestra_insuficiente": "muestra insuficiente",
                            "no_converge": "no converge", "clase_insuficiente": "clases insuficientes",
                            "salida_invalida": "salida no válida", "fallo_de_ajuste": "fallo de ajuste",
                            "no_reproduce": "el estimador recargado no reproduce el control",
                            "estimador_no_admitido": "estimador no admitido", "fallo": "error"}


def _contexto(request: Request, db_conectada: bool) -> dict:
    return {**_base(request, "laboratorio", db_conectada), "nombres": NOMBRES, "slugs": SLUGS,
            "token_local": proteccion_local.token_local(), "estados_resumen": ESTADOS_RESUMEN,
            "veredictos": VEREDICTOS, "estados_de_entrenamiento": ESTADOS_DE_ENTRENAMIENTO}


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
    colores = informe["juego"] == "COLORLOTO"
    cantidad = informe["identidad"]["reglas"]["cantidad"]
    return templates.TemplateResponse(request=request, name="laboratorio/informe.html", context={
        **_contexto(request, _conectada(db)), "i": informe, "clave": guardado.identificador,
        "base": lab.estado_frente_a_la_base(informe), "graficas": graficas,
        "pronosticos": {c["id"] for c in informe["candidatos"] if c["genera_pronostico"]},
        "registrables": {c["id"] for c in informe["candidatos"]
                         if c["id"] in lm.CATALOGO and lm.registrable(lm.CATALOGO[c["id"]])},
        "secundarias": {c["id"]: le.metricas_secundarias(c, colores, cantidad) for c in informe["candidatos"]
                        if c["estado"] == "completo"},
        "uniforme_id": next((c["id"] for c in informe["candidatos"] if c["familia"] == "uniforme"), None)})


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
        "e": ejecucion, "nombres": NOMBRES, "estados_resumen": ESTADOS_RESUMEN,
        "estados_de_entrenamiento": ESTADOS_DE_ENTRENAMIENTO})


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


# ---------------------------------------------------------------------------
# Fase 3: modelos registrados (antes de las rutas con {slug})
# ---------------------------------------------------------------------------

@router.post("/laboratorio/experimentos/{clave}/entrenar")
def entrenar(clave: str, request: Request, modelo: Annotated[str, Form()] = "",
             token_local: Annotated[str, Form()] = "", lab: LaboratorioDeModelos = Depends(get_laboratorio),
             lanzar=Depends(get_lanzador_de_laboratorio)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        inicio_ = lab.iniciar_entrenamiento(clave, modelo, "web")
    except LaboratorioError as error:
        return _error(request, f"No se inició el entrenamiento: {error}", _CODIGO_HTTP.get(error.codigo, 400))
    except EjecucionActivaError as error:
        return _error(request, "Ya hay un trabajo del laboratorio en curso para "
                      + ", ".join(NOMBRES[j] for j in sorted(error.activas)) + ". Ábrelo o espera a que termine.",
                      409, activas=error.activas)
    except OSError as error:
        return _error(request, f"No se pudo registrar el entrenamiento: {mensaje_legible(error)}", 500)
    try:
        lanzar(lab.ejecutar_entrenamiento, inicio_)
    except Exception as error:  # no se pudo crear el hilo: nada queda falsamente activo
        lab.abortar(inicio_, str(error))
        return _error(request, f"No se pudo iniciar el entrenamiento: {mensaje_legible(error)}", 500)
    return RedirectResponse(url=f"/laboratorio/experimentos/{inicio_.ejecucion['id']}", status_code=303)


@router.get("/laboratorio/modelos")
def modelos(request: Request, juego: str | None = Query(default=None), db: Session = Depends(get_db),
            lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    codigos = [_codigo(juego)] if juego else list(JUEGOS)
    return templates.TemplateResponse(request=request, name="laboratorio/modelos.html", context={
        **_contexto(request, _conectada(db)), "datos": [lab.modelos(c) for c in codigos],
        "catalogo": lab.catalogo(), "filtro": juego})


@router.get("/laboratorio/modelo/{clave}")
def ficha_del_modelo(clave: str, request: Request, db: Session = Depends(get_db),
                     lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    try:
        ficha = lab.ficha_del_modelo(clave)
    except LaboratorioError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="laboratorio/modelo.html", context={
        **_contexto(request, _conectada(db)), "f": ficha, "a": ficha["modelo"], "clave": clave,
        "lectura_informe": _lectura_del_informe(lab, ficha["modelo"]), "etapas": _etapas(ficha["modelo"])})


_CONTRATO_CONGELADO = "estimador, calibracion y parametros elegidos quedan congelados (no se reajustan)"


def _lectura_del_informe(lab: LaboratorioDeModelos, artefacto: dict) -> dict:
    """Lectura del informe de procedencia GUARDADO para la ficha: su estado, quien quedo primero (o los
    empatados) y la clasificacion tal cual, con esta receta marcada. Solo lee el informe: no reentrena, no
    recalcula ni reordena. Asi la ficha distingue la evaluacion de su receta del ganador del informe."""
    modelo = artefacto["identidad"]["modelo"]["id"]
    try:
        resumen = lab.experimento(artefacto["procedencia"]["experimento"]).artefacto["resumen"]
    except LaboratorioError as error:
        return {"disponible": False, "motivo": str(error)}
    ranking = [{**r, "es_esta_receta": r["id"] == modelo} for r in resumen.get("ranking") or []]
    primeros = [r for r in ranking if r["log_loss"] == ranking[0]["log_loss"]] if ranking else []
    return {"disponible": True, "estado": resumen["estado"], "ranking": ranking, "primeros": primeros,
            "incompletos": resumen.get("incompletos") or []}


def _etapas(artefacto: dict) -> dict:
    """Etapas reales de la version: si tiene paso de calibracion (clasificadores calibrados) o no (Poisson:
    intensidades transformadas en probabilidades con codigo versionado). El manifiesto guarda un texto de
    contrato comun; para un modelo sin calibracion, la ficha lo presenta sin atribuirle esa etapa."""
    calibrado = any(c.get("paso") == "calibracion" for c in artefacto.get("componentes") or [])
    contrato = artefacto["contrato_de_inferencia"]
    if not calibrado and _CONTRATO_CONGELADO in contrato:
        detalle = (artefacto["identidad"].get("transformacion") or {}).get("detalle", "")
        contrato = contrato.replace(_CONTRATO_CONGELADO, (
            "estimador y parametros elegidos quedan congelados (no se reajustan); este modelo no tiene calibracion: "
            f"sus intensidades se transforman en probabilidades con codigo versionado ({detalle})"))
    return {"calibrado": calibrado, "contrato": contrato}


@router.post("/laboratorio/modelo/{clave}/verificar")
def verificar_modelo(clave: str, request: Request, token_local: Annotated[str, Form()] = "",
                     db: Session = Depends(get_db), lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        resultado = lab.verificar_modelo(clave)
    except LaboratorioError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="laboratorio/verificacion_modelo.html", context={
        **_contexto(request, _conectada(db)), "r": resultado, "clave": clave})


@router.post("/laboratorio/modelo/{clave}/generar")
def generar_con_modelo(clave: str, request: Request, corte: Annotated[str, Form()] = "",
                       token_local: Annotated[str, Form()] = "", lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    corte = corte.strip()
    if corte and not corte.isdigit():
        return _error(request, "El corte de entrada debe ser un número de sorteo cargado.", 422)
    try:
        guardado = lab.generar_con_modelo(clave, int(corte) if corte else None, "web")
    except LaboratorioError as error:
        return _error(request, f"No se generó el pronóstico: {error}", _CODIGO_HTTP.get(error.codigo, 400))
    except OSError as error:
        return _error(request, f"No se pudo guardar el pronóstico: {mensaje_legible(error)}", 500)
    sufijo = "?reutilizado=1" if guardado.reutilizado else ""
    return RedirectResponse(url=f"/laboratorio/pronosticos/{guardado.identificador}{sufijo}", status_code=303)


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
