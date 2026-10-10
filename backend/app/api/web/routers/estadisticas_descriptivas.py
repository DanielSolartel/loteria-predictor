"""
Router web de la Fase 5: estadísticas descriptivas nuevas y panel unificado por juego.

- `/estadisticas/{juego}/panel`: todas las métricas del juego en una sola vista, sobre la misma
  muestra (corte opcional), con su cifra clave, si su página es nueva o anterior y las que no
  aplican con su motivo.
- `/estadisticas/{juego}/{metrica}`: cada métrica nueva (`descriptivas.CATALOGO`), con corte y, según
  la métrica, `anio`, `mes`, `dia_semana` o `ventana`.

`juego`: `baloto`, `baloto-revancha`, `miloto` o `colorloto`. Una métrica que no aplica al juego
(superbalota en MiLoto o ColorLoto, decenas o independencia en ColorLoto) responde 404 con el
motivo. Se registra DESPUÉS del router de estadísticas anterior: sus rutas literales de ColorLoto
(`/estadisticas/colorloto/distribucion-sumas`, ...) conservan la prioridad y no cambian.

Solo lectura: ningún GET escribe en la base (ni la caché `estadisticas`). Sin base de datos, la
página lo indica en lugar de mostrar ceros.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.dependencies import get_consultar_estadisticas_descriptivas
from app.api.web.navegacion_descriptivas import (
    NOMBRES,
    juegos_nav,
    navegacion_fase5,
    reglas_estaticas,
    url_estadistica,
)
from app.api.web.routers.estadisticas import _VentanaValida
from app.api.web.routers.producto import _base, _conectada, _Corte
from app.application.estadisticas.descriptivas import CATALOGO, ETIQUETAS_TIPO_P_VALUE, GRUPOS, POR_SLUG
from app.application.use_cases.consultar_estadisticas_descriptivas import ConsultarEstadisticasDescriptivas
from app.application.use_cases.consultar_resumen_juego import SLUG_A_CODIGO_RESUMEN
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

DiaSemana = Literal["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def formatear(valor, formato: str = "entero") -> str:
    """Formato de presentación de una celda; `None` se muestra como «—» (nunca 0)."""
    if valor is None:
        return "—"
    if formato == "tipo_p":
        return ETIQUETAS_TIPO_P_VALUE.get(valor, str(valor))
    if formato == "texto" or isinstance(valor, str):
        return str(valor)
    if formato == "entero":
        return f"{int(valor)}"
    if formato == "pct":
        return f"{valor:.1f}"
    if formato == "pp":
        return f"{valor:+.1f}"
    if formato == "p":
        return "< 0.0001" if valor < 0.0001 else f"{valor:.4f}"
    decimales = {"dec1": 1, "dec2": 2, "dec3": 3}.get(formato, 2)
    return f"{valor:.{decimales}f}"


templates.env.globals["navegacion_fase5"] = navegacion_fase5
templates.env.filters["formatear"] = formatear


def _codigo(juego_slug: str) -> str:
    codigo = SLUG_A_CODIGO_RESUMEN.get(juego_slug)
    if codigo is None:
        raise HTTPException(status_code=404, detail=f"Estadísticas no disponibles para '{juego_slug}'")
    return codigo


def _contexto(request: Request, juego_slug: str, codigo: str, conectada: bool, activa: str,
              hasta_numero_sorteo: int | None) -> dict:
    return {**_base(request, "estadisticas", conectada), "slug": juego_slug, "codigo": codigo,
            "nombre": NOMBRES[codigo], "hasta_numero_sorteo": hasta_numero_sorteo, "activa": activa,
            "juegos_nav": juegos_nav(activa, juego_slug), "grupos_nombres": dict(GRUPOS),
            "url_estadistica": url_estadistica}


@router.get("/estadisticas/{juego_slug}/panel")
def panel(juego_slug: str, request: Request, hasta_numero_sorteo: _Corte = None, db: Session = Depends(get_db),
          consultar: ConsultarEstadisticasDescriptivas = Depends(get_consultar_estadisticas_descriptivas)):
    codigo = _codigo(juego_slug)
    conectada = _conectada(db)
    datos = consultar.panel(codigo, hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo) if conectada else None
    return templates.TemplateResponse(request=request, name="descriptivas/panel.html", context={
        **_contexto(request, juego_slug, codigo, conectada, "panel", hasta_numero_sorteo), "datos": datos})


def _pagina(slug_metrica: str, juego_slug: str, request: Request, hasta_numero_sorteo: int | None, db: Session,
            consultar: ConsultarEstadisticasDescriptivas, parametros: dict):
    codigo = _codigo(juego_slug)
    definicion = POR_SLUG[slug_metrica]
    reglas = reglas_estaticas(juego_slug)
    if not definicion.aplica(reglas):
        motivo = definicion.motivo_no_aplica(reglas) if definicion.motivo_no_aplica else "no aplica a este juego"
        raise HTTPException(status_code=404, detail=f"«{definicion.titulo}» no está disponible para "
                                                    f"{NOMBRES[codigo]}: {motivo}")
    if not definicion.es_nueva(reglas):  # la sirve el router anterior (ruta literal registrada antes)
        raise HTTPException(status_code=404, detail=f"«{definicion.titulo}» de {NOMBRES[codigo]} es una página "
                                                    "anterior a la Fase 5")
    conectada = _conectada(db)
    datos = consultar.metrica(codigo, slug_metrica, hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo,
                              parametros=parametros) if conectada else None
    return templates.TemplateResponse(request=request, name="descriptivas/metrica.html", context={
        **_contexto(request, juego_slug, codigo, conectada, slug_metrica, hasta_numero_sorteo),
        "definicion": definicion, "datos": datos, "parametros": parametros})


def _registrar(slug_metrica: str, parametro: str | None) -> None:
    """Una ruta explícita por métrica (nunca `/estadisticas/{juego}/{metrica}` genérica, que taparía
    otras rutas). Cada ruta declara solo su parámetro: uno ajeno no se acepta en silencio."""
    ruta = f"/estadisticas/{{juego_slug}}/{slug_metrica}"
    nombre = "descriptiva_" + slug_metrica.replace("-", "_")
    dependencias = {"db": Depends(get_db), "consultar": Depends(get_consultar_estadisticas_descriptivas)}

    if parametro == "anio":
        def vista(juego_slug: str, request: Request, hasta_numero_sorteo: _Corte = None,
                  anio: Annotated[int | None, Query(ge=1, le=9999)] = None, db: Session = dependencias["db"],
                  consultar: ConsultarEstadisticasDescriptivas = dependencias["consultar"]):
            return _pagina(slug_metrica, juego_slug, request, hasta_numero_sorteo, db, consultar, {"anio": anio})
    elif parametro == "mes":
        def vista(juego_slug: str, request: Request, hasta_numero_sorteo: _Corte = None,
                  mes: Annotated[int | None, Query(ge=1, le=12)] = None, db: Session = dependencias["db"],
                  consultar: ConsultarEstadisticasDescriptivas = dependencias["consultar"]):
            return _pagina(slug_metrica, juego_slug, request, hasta_numero_sorteo, db, consultar, {"mes": mes})
    elif parametro == "dia_semana":
        def vista(juego_slug: str, request: Request, hasta_numero_sorteo: _Corte = None,
                  dia_semana: Annotated[DiaSemana | None, Query()] = None, db: Session = dependencias["db"],
                  consultar: ConsultarEstadisticasDescriptivas = dependencias["consultar"]):
            return _pagina(slug_metrica, juego_slug, request, hasta_numero_sorteo, db, consultar,
                           {"dia_semana": dia_semana})
    elif parametro == "ventana":
        def vista(juego_slug: str, request: Request, hasta_numero_sorteo: _Corte = None,
                  ventana: _VentanaValida = 20, db: Session = dependencias["db"],
                  consultar: ConsultarEstadisticasDescriptivas = dependencias["consultar"]):
            return _pagina(slug_metrica, juego_slug, request, hasta_numero_sorteo, db, consultar, {"ventana": ventana})
    else:
        def vista(juego_slug: str, request: Request, hasta_numero_sorteo: _Corte = None,
                  db: Session = dependencias["db"],
                  consultar: ConsultarEstadisticasDescriptivas = dependencias["consultar"]):
            return _pagina(slug_metrica, juego_slug, request, hasta_numero_sorteo, db, consultar, {})
    vista.__name__ = nombre
    router.add_api_route(ruta, vista, methods=["GET"], name=nombre)


SLUGS_CON_PAGINA: tuple[str, ...] = tuple(m.slug for m in CATALOGO if m.construir is not None)
for _m in CATALOGO:
    if _m.construir is not None:
        _registrar(_m.slug, _m.parametro)
