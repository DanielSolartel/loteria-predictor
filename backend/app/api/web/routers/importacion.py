"""
Router web del panel "Importación".

Igual que el resto de routers web: solo traduce HTTP <-> casos de
uso, sin lógica propia. La sincronización se ejecuta de forma
síncrona dentro del request HTTP (con HTMX mostrando un indicador de
carga) -es una simplificación deliberada para este MVP; con
histórico completo (100+ páginas) puede tardar bastante, así que el
botón "Sincronizar ahora" acepta un límite de páginas para uso
interactivo, y "Reimportar todo" está pensado para dejarlo corriendo
sin límite.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import (
    get_estado_importacion,
    get_reimportar_sorteo,
    get_reporte_calidad_datos,
    get_reprocesar_desde_html,
    get_sincronizar_sorteos,
    get_validar_integridad,
)
from app.application.exceptions import DominioError
from app.application.use_cases.generar_reporte_calidad_datos import GenerarReporteCalidadDatos
from app.application.use_cases.obtener_estado_importacion import ObtenerEstadoImportacion
from app.application.use_cases.reimportar_sorteo import ReimportarSorteo
from app.application.use_cases.reprocesar_sorteos_desde_html import ReprocesarSorteosDesdeHtml
from app.application.use_cases.sincronizar_sorteos import SincronizarSorteos
from app.application.use_cases.validar_integridad import ValidarIntegridadDatos
from app.infrastructure.logging_config import leer_ultimas_lineas

router = APIRouter(prefix="/importacion")
templates = Jinja2Templates(directory="app/templates")


def _estado_a_vm(estado) -> dict:
    ultima = estado.ultima_ejecucion
    return {
        "codigo": estado.juego.codigo,
        "nombre": estado.juego.nombre,
        "total_sorteos": estado.total_sorteos_almacenados,
        "ultimo_sorteo_almacenado": estado.ultimo_sorteo_almacenado,
        "ultima_sincronizacion": {
            "estado": ultima.estado,
            "iniciado_en": ultima.iniciado_en.strftime("%Y-%m-%d %H:%M"),
            "sorteos_nuevos": ultima.sorteos_nuevos,
            "sorteos_fallidos": ultima.sorteos_fallidos,
            "duracion_ms": ultima.duracion_ms,
            "detalle_errores": ultima.detalle_errores[:10],
        } if ultima else None,
    }


@router.get("")
def panel_importacion(
    request: Request, obtener_estado: ObtenerEstadoImportacion = Depends(get_estado_importacion)
):
    # verificar_salud=False: la carga inicial del panel NUNCA debe
    # esperar a una petición HTTP en vivo al sitio origen -eso podría
    # bloquear la página hasta 3 * timeout si el origen está lento o
    # caído. La salud de cada conector se pide después, por separado,
    # vía /importacion/salud/{codigo} (ver badge_salud.html + HTMX).
    estados = [_estado_a_vm(e) for e in obtener_estado.ejecutar(verificar_salud=False)]
    return templates.TemplateResponse(
        request=request, name="importacion/panel.html",
        context={"active_page": "importacion", "conectores": estados},
    )


@router.get("/salud/{codigo_juego}")
def salud_conector(
    codigo_juego: str, request: Request,
    obtener_estado: ObtenerEstadoImportacion = Depends(get_estado_importacion),
):
    """Endpoint dedicado, cargado vía HTMX con `hx-trigger="load"`
    desde cada tarjeta del panel -así el chequeo de salud (una
    petición HTTP real al origen) nunca bloquea el renderizado
    inicial de la página, y cada conector se verifica en paralelo
    (una petición HTMX por tarjeta, no una serie de N health_check
    encadenados en el mismo request)."""
    salud = obtener_estado.verificar_salud_de(codigo_juego)
    return templates.TemplateResponse(
        request=request, name="importacion/partials/badge_salud.html",
        context={
            "codigo": codigo_juego,
            "disponible": salud.disponible,
            "mensaje": salud.mensaje,
            "latencia_ms": round(salud.latencia_ms) if salud.latencia_ms else None,
        },
    )


@router.post("/sincronizar/{codigo_juego}")
def sincronizar_ahora(
    codigo_juego: str,
    request: Request,
    max_paginas: int | None = None,
    sincronizar: SincronizarSorteos = Depends(get_sincronizar_sorteos),
    obtener_estado: ObtenerEstadoImportacion = Depends(get_estado_importacion),
):
    """
    max_paginas=None por defecto: NO se limita artificialmente el
    número de páginas a recorrer. La sincronización se detiene sola
    cuando corresponde:
      - ya no hay página "Siguiente" en el origen,
      - la página no trae más sorteos,
      - o se alcanza `ultimo_conocido` (sincronización incremental).
    El único límite real es el techo de seguridad configurable de
    BaseConnector (`max_paginas_absoluto`, ver ConnectorRegistry),
    pensado para evitar un bucle infinito ante un origen que nunca
    deje de paginar -no para acotar una carga histórica legítima.
    Si se quiere acotar una corrida puntual (p.ej. para pruebas),
    sigue siendo posible pasar ?max_paginas=N explícitamente.
    """
    try:
        reporte = sincronizar.ejecutar(codigo_juego, max_paginas=max_paginas)
        mensaje = (
            f"Sincronización de {codigo_juego}: {reporte.ejecucion.sorteos_nuevos} nuevo(s), "
            f"{reporte.ejecucion.sorteos_fallidos} fallido(s)."
        )
    except DominioError as e:
        mensaje = f"Error al sincronizar {codigo_juego}: {e}"

    estados = [_estado_a_vm(e) for e in obtener_estado.ejecutar(verificar_salud=False)]
    return templates.TemplateResponse(
        request=request, name="importacion/partials/panel_contenido.html",
        context={"conectores": estados, "mensaje": mensaje},
    )


@router.post("/reimportar-todo/{codigo_juego}")
def reimportar_todo(
    codigo_juego: str,
    request: Request,
    sincronizar: SincronizarSorteos = Depends(get_sincronizar_sorteos),
    obtener_estado: ObtenerEstadoImportacion = Depends(get_estado_importacion),
):
    try:
        reporte = sincronizar.ejecutar(codigo_juego, forzar_completo=True)
        mensaje = (
            f"Reimportación completa de {codigo_juego}: {reporte.ejecucion.sorteos_nuevos} sorteo(s) "
            f"procesados, {reporte.ejecucion.sorteos_fallidos} fallido(s)."
        )
    except DominioError as e:
        mensaje = f"Error al reimportar {codigo_juego}: {e}"

    estados = [_estado_a_vm(e) for e in obtener_estado.ejecutar(verificar_salud=False)]
    return templates.TemplateResponse(
        request=request, name="importacion/partials/panel_contenido.html",
        context={"conectores": estados, "mensaje": mensaje},
    )


@router.post("/reimportar-sorteo/{sorteo_id}")
def reimportar_sorteo_endpoint(
    sorteo_id: UUID,
    request: Request,
    reimportar: ReimportarSorteo = Depends(get_reimportar_sorteo),
):
    try:
        sorteo = reimportar.ejecutar(sorteo_id)
        return templates.TemplateResponse(
            request=request, name="importacion/partials/mensaje_simple.html",
            context={"mensaje": f"Sorteo #{sorteo.numero_sorteo} reimportado correctamente.", "es_error": False},
        )
    except DominioError as e:
        return templates.TemplateResponse(
            request=request, name="importacion/partials/mensaje_simple.html",
            context={"mensaje": f"Error al reimportar el sorteo: {e}", "es_error": True},
        )


@router.post("/reprocesar-html/{codigo_juego}")
def reprocesar_desde_html(
    codigo_juego: str,
    request: Request,
    reprocesar: ReprocesarSorteosDesdeHtml = Depends(get_reprocesar_desde_html),
    obtener_estado: ObtenerEstadoImportacion = Depends(get_estado_importacion),
):
    try:
        reporte = reprocesar.ejecutar_todos(codigo_juego)
        mensaje = (
            f"Reprocesado desde HTML ({codigo_juego}): {reporte.total_html_disponibles} archivo(s) "
            f"→ {reporte.creados} creado(s), {reporte.actualizados} actualizado(s), "
            f"{reporte.fallidos} fallido(s), {reporte.incompletos} incompleto(s). Sin usar la red."
        )
    except (DominioError, ValueError) as e:
        mensaje = f"Error al reprocesar {codigo_juego} desde HTML: {e}"

    estados = [_estado_a_vm(e) for e in obtener_estado.ejecutar(verificar_salud=False)]
    return templates.TemplateResponse(
        request=request, name="importacion/partials/panel_contenido.html",
        context={"conectores": estados, "mensaje": mensaje},
    )


@router.get("/validar/{codigo_juego}")
def validar_integridad_endpoint(
    codigo_juego: str, request: Request, validar: ValidarIntegridadDatos = Depends(get_validar_integridad)
):
    try:
        reporte = validar.ejecutar(codigo_juego)
        return templates.TemplateResponse(
            request=request, name="importacion/partials/reporte_integridad.html",
            context={"reporte": reporte},
        )
    except DominioError as e:
        return templates.TemplateResponse(
            request=request, name="importacion/partials/reporte_integridad.html",
            context={"reporte": None, "error": str(e)},
        )


@router.get("/calidad/{codigo_juego}")
def reporte_calidad_datos(
    codigo_juego: str, request: Request,
    generar_reporte: GenerarReporteCalidadDatos = Depends(get_reporte_calidad_datos),
):
    try:
        reporte = generar_reporte.ejecutar(codigo_juego)
        return templates.TemplateResponse(
            request=request, name="importacion/partials/reporte_calidad.html",
            context={"reporte": reporte},
        )
    except DominioError as e:
        return templates.TemplateResponse(
            request=request, name="importacion/partials/reporte_calidad.html",
            context={"reporte": None, "error": str(e)},
        )


@router.get("/logs", response_class=PlainTextResponse)
def ver_logs(lineas: int = 200):
    return "".join(leer_ultimas_lineas(lineas)) or "Sin actividad registrada todavía."
