"""
Router web de Producto 6: centro de resultados y evaluacion continua.

- `GET /resultados`: los cuatro juegos (ultimo resultado cargado, objetivos de
  seguimiento incluidos, pendientes y excluidos, procedencias disponibles).
- `GET /resultados/{slug}`: filtros (procedencias, lineas, tipo de emision,
  intervalo u objetivo), resumen por linea, comparacion directa sobre la
  muestra comun, evolucion, calibracion, historial paginado y carteras.
  `exportar.csv` y `exportar.json`: el conjunto filtrado COMPLETO.
- `POST /resultados/{slug}/informes`: guarda una fotografia verificable.
  `GET /resultados/informes/{clave}` (y `exportar.json`) la muestra;
  `POST /resultados/informes/{clave}/verificar` separa integridad,
  reproduccion y coincidencia con la base actual.
- `GET /resultados/{slug}/configuracion?linea=`: vista previa de «usar esta
  configuracion»; `POST` la guarda con el caso de uso versionado de
  Producto 5 (idempotente; no entrena ni genera carteras).

Todos los POST: solo desde la propia maquina y con el token local. Ningun GET
entrena, importa, inicia trabajadores ni escribe.
"""
from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.dependencies import get_resultados
from app.api.web import proteccion_local
from app.api.web.routers.producto import _base, _conectada
from app.application.ml import resultados_calibracion as rc
from app.application.ml import resultados_informes as ri
from app.application.ml import resultados_procedencias as rp
from app.application.use_cases.operacion_diaria import mensaje_legible
from app.application.use_cases.resultados import (
    JUEGOS,
    NOMBRES,
    POR_PAGINA,
    SLUGS,
    CentroDeResultados,
    Filtros,
    ResultadosError,
)
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
SLUG_A_CODIGO = {s: c for c, s in SLUGS.items()}
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409}
VEREDICTOS = {"menor_perdida_que_la_uniforme_en_esta_muestra": "menor pérdida que la uniforme en esta muestra",
              "la_uniforme_fue_mejor": "la uniforme fue mejor", "empate": "empate", "referencia": "referencia"}
ESTADOS = {"incluido": "incluido", "pendiente": "pendiente", "excluido": "excluido",
           "sin_base": "sin base (no consultada)"}
TIPOS = {"seguimiento": "Seguimiento (objetivo sin cargar al emitir)",
         "retrospectiva": "Reconstrucciones retrospectivas"}
COLORES = ("#4b3f8f", "#c2410c", "#0f766e", "#b91c1c", "#1d4ed8", "#a16207", "#7e22ce", "#15803d")


def _contexto(request: Request, db_conectada: bool) -> dict:
    return {**_base(request, "resultados", db_conectada), "nombres": NOMBRES, "slugs": SLUGS,
            "token_local": proteccion_local.token_local(), "veredictos": VEREDICTOS, "estados": ESTADOS,
            "tipos": TIPOS, "procedencias_nombres": rp.NOMBRES_DE_PROCEDENCIA}


def _error(request: Request, mensaje: str, status_code: int):
    return templates.TemplateResponse(request=request, name="resultados/error.html", status_code=status_code,
                                      context={**_contexto(request, True), "mensaje": mensaje})


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


def _entero(valor: str | None, nombre: str) -> int | None:
    if valor is None or not valor.strip():
        return None
    try:
        return int(valor.strip())
    except ValueError:
        raise ResultadosError("no_valido", f"«{nombre}» debe ser un número de sorteo") from None


def filtros_de(procedencia: list[str] | None, linea: list[str] | None, tipo: str, desde: str | None,
               hasta: str | None, objetivo: str | None, cartera: list[str] | None) -> Filtros:
    """Filtros de la consulta (los mismos para la pagina, las exportaciones y el informe)."""
    return Filtros(tuple(procedencia or ()) or rp.PROCEDENCIAS, tuple(linea or ()), tipo or "seguimiento",
                   _entero(desde, "desde"), _entero(hasta, "hasta"), _entero(objetivo, "objetivo"),
                   tuple(cartera or ())).validar()


def consulta_de(filtros: dict, **extra) -> str:
    """Cadena de consulta con claves repetidas (procedencia, linea, cartera)."""
    pares = [("procedencia", p) for p in filtros["procedencias"]]
    pares += [("linea", l) for l in filtros["lineas"]]
    pares.append(("tipo", filtros["tipo"]))
    pares += [(k, filtros[k]) for k in ("desde", "hasta", "objetivo") if filtros[k] is not None]
    pares += [("cartera", c) for c in filtros["carteras"]]
    pares += [(k, v) for k, v in extra.items() if v is not None]
    return urlencode(pares)


def _descarga(contenido: bytes | str, nombre: str, tipo: str) -> Response:
    datos = contenido.encode("utf-8") if isinstance(contenido, str) else contenido
    return Response(content=datos, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"',
                             "X-Content-Type-Options": "nosniff"})


# ---------------------------------------------------------------------------
# Graficas SVG (sin bibliotecas externas; los mismos valores van en tablas)
# ---------------------------------------------------------------------------

def grafica_de_evolucion(series: dict[str, list[dict]], nombres: dict[str, str], ancho: int = 680,
                         alto: int = 240, margen: int = 40) -> dict | None:
    """Diferencia ACUMULADA de Log Loss frente a la uniforme, una polilinea por
    linea, sobre los mismos objetivos (la muestra comun de la comparacion)."""
    series = {clave: s for clave, s in series.items() if s}
    if not series:
        return None
    objetivos = sorted({p["objetivo"] for s in series.values() for p in s})
    valores = [p["acumulada"] for s in series.values() for p in s]
    bajo, alto_v = min(0.0, *valores), max(0.0, *valores)
    rango = (alto_v - bajo) or 1.0
    paso = (ancho - 2 * margen) / max(len(objetivos) - 1, 1)
    posicion = {o: round(margen + i * paso, 1) for i, o in enumerate(objetivos)}

    def y(v: float) -> float:
        return round(margen + (alto_v - v) / rango * (alto - 2 * margen), 1)

    trazos = []
    for i, (clave, s) in enumerate(series.items()):
        puntos = [{"x": posicion[p["objetivo"]], "y": y(p["acumulada"]), "objetivo": p["objetivo"],
                   "acumulada": p["acumulada"]} for p in s]
        # anchos decrecientes y guiones alternos: dos lineas con los mismos valores siguen viendose
        trazos.append({"clave": clave, "nombre": nombres.get(clave, clave), "color": COLORES[i % len(COLORES)],
                       "guiones": "6 3" if i % 2 else "", "ancho": max(1.5, 4.0 - i), "puntos": puntos,
                       "polilinea": " ".join(f"{p['x']},{p['y']}" for p in puntos), "final": s[-1]["acumulada"]})
    marcas = objetivos if len(objetivos) <= 12 else objetivos[::max(1, len(objetivos) // 10)]
    return {"ancho": ancho, "alto": alto, "margen": margen, "cero": y(0.0), "trazos": trazos, "maximo": alto_v,
            "minimo": bajo, "ejes": [{"x": posicion[o], "objetivo": o} for o in marcas]}


def grafica_de_calibracion(diagnostico: dict, ancho: int = 320, alto: int = 280, margen: int = 40) -> dict | None:
    """Curva de fiabilidad: probabilidad media (x) frente a valor observado
    medio (y) de cada intervalo NO vacio, con la diagonal y = x. La escala
    llega hasta el mayor valor representado (las probabilidades de estos
    juegos son pequenas)."""
    llenos = [i for i in diagnostico["intervalos"] if i["predicciones"]]
    if not llenos:
        return None
    limite = max(max(i["probabilidad_media"] for i in llenos), max(i["valor_observado_medio"] for i in llenos))
    limite = min(1.0, max(0.02, limite * 1.1))
    lado_x, lado_y = ancho - 2 * margen, alto - 2 * margen

    def px(v: float) -> float:
        return round(margen + v / limite * lado_x, 1)

    def py(v: float) -> float:
        return round(alto - margen - v / limite * lado_y, 1)

    puntos = [{"x": px(i["probabilidad_media"]), "y": py(i["valor_observado_medio"]),
               "r": round(min(7.0, 2.5 + i["objetivos"] ** 0.5), 1), "desde": i["desde"], "hasta": i["hasta"],
               "p": i["probabilidad_media"], "o": i["valor_observado_medio"], "n": i["predicciones"],
               "objetivos": i["objetivos"]} for i in llenos]
    marcas = [round(limite * k / 4, 4) for k in range(5)]
    return {"ancho": ancho, "alto": alto, "margen": margen, "limite": limite, "puntos": puntos,
            "polilinea": " ".join(f"{p['x']},{p['y']}" for p in puntos),
            "diagonal": {"x1": px(0), "y1": py(0), "x2": px(limite), "y2": py(limite)},
            "marcas": [{"valor": m, "x": px(m), "y": py(m)} for m in marcas]}


def tabla_de_evolucion(series: dict[str, list[dict]]) -> list[dict]:
    """Los mismos puntos de la grafica, por objetivo (una columna por linea)."""
    objetivos = sorted({p["objetivo"] for s in series.values() for p in s})
    por_linea = {clave: {p["objetivo"]: p for p in s} for clave, s in series.items()}
    return [{"objetivo": o, "valores": {clave: por_linea[clave].get(o) for clave in series}} for o in objetivos]


def _graficas(vista: dict) -> dict:
    nombres = {m["clave"]: m["nombre"] for m in vista["lineas"]}
    return {"evolucion": grafica_de_evolucion(vista["evolucion"], nombres),
            "tabla_evolucion": tabla_de_evolucion(vista["evolucion"]),
            "calibracion": {clave: {nombre: grafica_de_calibracion(d) for nombre, d in c["diagnosticos"].items()}
                            for clave, c in vista["calibracion"].items()}}


# ---------------------------------------------------------------------------
# Paginas de lectura
# ---------------------------------------------------------------------------

@router.get("/resultados")
def indice(request: Request, db: Session = Depends(get_db), centro: CentroDeResultados = Depends(get_resultados)):
    return templates.TemplateResponse(request=request, name="resultados/indice.html", context={
        **_contexto(request, _conectada(db)), "datos": centro.indice()})


@router.get("/resultados/informes/{clave}")
def informe(clave: str, request: Request, reutilizado: int = Query(default=0), db: Session = Depends(get_db),
            centro: CentroDeResultados = Depends(get_resultados)):
    try:
        a = centro.informe(clave)
    except ResultadosError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    nombres = {m["clave"]: m["nombre"] for m in a["lineas"]}
    comparacion = a["calculos"]["comparacion"]
    return templates.TemplateResponse(request=request, name="resultados/informe.html", context={
        **_contexto(request, _conectada(db)), "a": a, "clave": clave, "reutilizado": bool(reutilizado),
        "nombres_de_linea": nombres, "juego": a["juego"], "lineas_por_clave": {m["clave"]: m for m in a["lineas"]},
        "evolucion": grafica_de_evolucion({k: v["serie"] for k, v in comparacion["por_linea"].items()}, nombres),
        "tabla_evolucion": tabla_de_evolucion({k: v["serie"] for k, v in comparacion["por_linea"].items()}),
        "graficas_calibracion": {clave: {nombre: grafica_de_calibracion(d) for nombre, d in c["diagnosticos"].items()}
                                 for clave, c in a["calculos"]["calibracion"].items()},
        "consulta": consulta_de(a["filtros"])})


@router.get("/resultados/informes/{clave}/exportar.json")
def exportar_informe(clave: str, request: Request, centro: CentroDeResultados = Depends(get_resultados)):
    try:
        a = centro.informe(clave)
    except ResultadosError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return _descarga(ri.json_canonico(a), f"informe-resultados-{a['juego']}-{clave[:12]}.json", "application/json")


def _filtros_o_error(request, procedencia, linea, tipo, desde, hasta, objetivo, cartera):
    try:
        return filtros_de(procedencia, linea, tipo, desde, hasta, objetivo, cartera), None
    except ResultadosError as error:
        return None, _error(request, f"Filtro no válido: {error}", 422)


_Lista = Annotated[list[str] | None, Query()]


@router.get("/resultados/{slug}/exportar.csv")
def exportar_csv(slug: str, request: Request, procedencia: _Lista = None, linea: _Lista = None,
                 tipo: str = "seguimiento", desde: str | None = None, hasta: str | None = None,
                 objetivo: str | None = None, cartera: _Lista = None,
                 centro: CentroDeResultados = Depends(get_resultados)):
    codigo = _codigo(slug)
    filtros, error = _filtros_o_error(request, procedencia, linea, tipo, desde, hasta, objetivo, cartera)
    if error is not None:
        return error
    try:
        contenido = centro.exportar_csv(codigo, filtros)
    except ResultadosError as e:
        return _error(request, str(e), _CODIGO_HTTP.get(e.codigo, 400))
    return _descarga(contenido, f"resultados-{codigo}-{filtros.tipo}.csv", "text/csv; charset=utf-8")


@router.get("/resultados/{slug}/exportar.json")
def exportar_json(slug: str, request: Request, procedencia: _Lista = None, linea: _Lista = None,
                  tipo: str = "seguimiento", desde: str | None = None, hasta: str | None = None,
                  objetivo: str | None = None, cartera: _Lista = None,
                  centro: CentroDeResultados = Depends(get_resultados)):
    codigo = _codigo(slug)
    filtros, error = _filtros_o_error(request, procedencia, linea, tipo, desde, hasta, objetivo, cartera)
    if error is not None:
        return error
    try:
        contenido = centro.exportar_json(codigo, filtros)
    except ResultadosError as e:
        return _error(request, str(e), _CODIGO_HTTP.get(e.codigo, 400))
    return _descarga(ri.json_canonico(contenido), f"resultados-{codigo}-{filtros.tipo}.json", "application/json")


@router.get("/resultados/{slug}/configuracion")
def configuracion(slug: str, request: Request, linea: str = Query(default=""), db: Session = Depends(get_db),
                  centro: CentroDeResultados = Depends(get_resultados)):
    codigo = _codigo(slug)
    try:
        datos = centro.propuesta_de_configuracion(codigo, linea)
    except ResultadosError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="resultados/configuracion.html", context={
        **_contexto(request, _conectada(db)), "juego": codigo, "linea": linea, "d": datos, "resultado": None})


@router.get("/resultados/{slug}")
def juego(slug: str, request: Request, procedencia: _Lista = None, linea: _Lista = None,
          tipo: str = "seguimiento", desde: str | None = None, hasta: str | None = None,
          objetivo: str | None = None, cartera: _Lista = None,
          pagina: int = Query(default=1, ge=1), db: Session = Depends(get_db),
          centro: CentroDeResultados = Depends(get_resultados)):
    codigo = _codigo(slug)
    filtros, error = _filtros_o_error(request, procedencia, linea, tipo, desde, hasta, objetivo, cartera)
    if error is not None:
        return error
    try:
        vista = centro.consultar(codigo, filtros, pagina=pagina, por_pagina=POR_PAGINA)
        informes = centro.informes(codigo)
    except ResultadosError as e:
        return _error(request, str(e), _CODIGO_HTTP.get(e.codigo, 400))
    except OSError as e:
        return _error(request, f"No se pudieron leer los almacenes: {mensaje_legible(e)}", 500)
    fijados = {**vista["filtros"], "lineas": vista["seleccion"]}
    return templates.TemplateResponse(request=request, name="resultados/juego.html", context={
        **_contexto(request, _conectada(db)), "juego": codigo, "v": vista, "graficas": _graficas(vista),
        "nombres_de_linea": {m["clave"]: m["nombre"] for m in vista["lineas"]}, "informes": informes,
        "lineas_por_clave": {m["clave"]: m for m in vista["lineas"]},
        "consulta": consulta_de(vista["filtros"]), "consulta_fijada": consulta_de(fijados),
        "consulta_retrospectiva": consulta_de({**vista["filtros"], "tipo": "retrospectiva"}),
        "paginas": {n: consulta_de(vista["filtros"], pagina=n) for n in
                    sorted({1, vista["historial"]["pagina"] - 1, vista["historial"]["pagina"],
                            vista["historial"]["pagina"] + 1, vista["historial"]["paginas"]})
                    if 1 <= n <= vista["historial"]["paginas"]},
        "bordes": rc.BORDES})


# ---------------------------------------------------------------------------
# Acciones (POST protegidos)
# ---------------------------------------------------------------------------

_Campos = Annotated[list[str] | None, Form()]


@router.post("/resultados/{slug}/informes")
def guardar_informe(slug: str, request: Request, token_local: Annotated[str, Form()] = "",
                    procedencia: _Campos = None, linea: _Campos = None,
                    tipo: Annotated[str, Form()] = "seguimiento",
                    desde: Annotated[str, Form()] = "", hasta: Annotated[str, Form()] = "",
                    objetivo: Annotated[str, Form()] = "", cartera: _Campos = None,
                    centro: CentroDeResultados = Depends(get_resultados)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    codigo = _codigo(slug)
    filtros, error = _filtros_o_error(request, procedencia, linea, tipo, desde, hasta, objetivo, cartera)
    if error is not None:
        return error
    try:
        r = centro.guardar_informe(codigo, filtros, "web")
    except ResultadosError as e:
        return _error(request, str(e), _CODIGO_HTTP.get(e.codigo, 400))
    except OSError as e:
        return _error(request, f"No se pudo guardar el informe: {mensaje_legible(e)}", 500)
    return RedirectResponse(url=f"/resultados/informes/{r['clave']}?reutilizado={int(r['reutilizado'])}",
                            status_code=303)


@router.post("/resultados/informes/{clave}/verificar")
def verificar_informe(clave: str, request: Request, token_local: Annotated[str, Form()] = "",
                      db: Session = Depends(get_db), centro: CentroDeResultados = Depends(get_resultados)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    try:
        r = centro.verificar_informe(clave)
    except ResultadosError as error:
        return _error(request, str(error), _CODIGO_HTTP.get(error.codigo, 400))
    return templates.TemplateResponse(request=request, name="resultados/verificacion.html", context={
        **_contexto(request, _conectada(db)), "r": r, "clave": clave})


@router.post("/resultados/{slug}/configuracion")
def usar_configuracion(slug: str, request: Request, linea: Annotated[str, Form()] = "",
                       token_local: Annotated[str, Form()] = "", db: Session = Depends(get_db),
                       centro: CentroDeResultados = Depends(get_resultados)):
    rechazo = _rechazo(request, token_local)
    if rechazo is not None:
        return rechazo
    codigo = _codigo(slug)
    try:
        resultado = centro.usar_configuracion(codigo, linea, "web")
        datos = centro.propuesta_de_configuracion(codigo, linea)
    except ResultadosError as error:
        return _error(request, f"No se guardó la configuración: {error}", _CODIGO_HTTP.get(error.codigo, 400))
    except OSError as error:
        return _error(request, f"No se pudo guardar la configuración: {mensaje_legible(error)}", 500)
    return templates.TemplateResponse(request=request, name="resultados/configuracion.html", context={
        **_contexto(request, _conectada(db)), "juego": codigo, "linea": linea, "d": datos, "resultado": resultado})


__all__ = ["router", "filtros_de", "consulta_de", "grafica_de_evolucion", "grafica_de_calibracion", "JUEGOS"]
