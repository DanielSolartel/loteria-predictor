"""Panel de Fase 6: lectura explícita y acciones locales protegidas.

No instala tareas ni inicia un programador al importar este módulo. La
comprobación manual usa el mismo ciclo que la CLI, en un trabajo acotado.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.automatizacion_dependencies import get_automatizacion, get_lanzador_automatizacion
from app.api.web import proteccion_local
from app.application.exceptions import OperacionConcurrenteError
from app.application.use_cases.operacion_diaria import identificador_valido

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
NOMBRES = {"BALOTO": "Baloto", "BALOTO_REVANCHA": "Baloto Revancha", "MILOTO": "MiLoto", "COLORLOTO": "ColorLoto"}
ESTADOS = {
    "sin_configurar": "Sin configurar", "pausada": "En pausa", "habilitada": "Habilitada",
    "activada": "Habilitado", "en_curso": "En curso", "pendiente": "Pendiente",
    "sin_ejecutar": "Sin comprobación", "ok": "Completado", "exito": "Completado",
    "correcto": "Completado", "parcial": "Completado con avisos", "fallo": "Fallo",
    "error": "Error", "bloqueado": "Bloqueado", "interrumpida": "Interrumpida",
    "interrumpido": "Interrumpida", "aplazado": "Próxima consulta programada",
    "sorteo_previsto": "Sorteo previsto", "horario_alcanzado_sin_confirmar": "Horario alcanzado; celebración sin confirmar",
    "celebrado_resultado_no_publicado": "Celebrado; resultado sin publicar",
    "resultado_detectado_validado": "Resultado detectado y validado", "fallo_consulta": "Fallo al consultar",
    "fuera_de_plazo": "Emisión fuera de plazo", "pendiente_revision": "Revisión pendiente",
    "sin_comprobar": "Sin comprobación", "revision_pendiente": "Revisión pendiente",
    "modelo_no_congelado": "Versión registrada necesaria", "calendario_no_verificado": "Calendario sin verificar",
    "sin_corte_admisible": "Corte no admisible", "resultado_retrasado": "Resultado pendiente o retrasado",
    "generacion_bloqueada": "Predicción bloqueada", "sin_consultas_debidas": "Próxima consulta programada",
    "ocupado": "Recurso en uso",
    "historico_incompleto": "Histórico incompleto; recuperación necesaria",
}


def fecha_operativa(valor):
    """Fecha guardada en Bogotá; no infiere el estado del evento."""
    if isinstance(valor, dict):
        valor = valor.get("instante") or valor.get("inicio_utc") or valor.get("fecha_local") or valor.get("fecha")
    if not valor:
        return "Sin registrar"
    try:
        instante = datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return str(valor)
    if instante.tzinfo is None:
        return str(valor) + " (zona no registrada)"
    try:
        local = instante.astimezone(ZoneInfo("America/Bogota"))
    except ZoneInfoNotFoundError:
        return str(valor) + " (offset guardado; zona Bogotá no disponible)"
    desplazamiento = local.strftime("%z")
    return local.strftime("%Y-%m-%d %H:%M:%S") + " · Bogotá (UTC" + desplazamiento[:3] + ":" + desplazamiento[3:] + ")"


templates.env.filters["fecha_operativa"] = fecha_operativa


def _contexto(request: Request, **datos) -> dict:
    return {"request": request, "active_page": "automatizacion", "estado_db": "Estado guardado",
            "token_local": proteccion_local.token_local(), "nombres": NOMBRES, "estados": ESTADOS, **datos}


def _error(request: Request, mensaje: str, codigo: int):
    return templates.TemplateResponse(request=request, name="automatizacion/error.html",
                                      status_code=codigo, context=_contexto(request, mensaje=mensaje))


@router.get("/automatizacion")
def panel(request: Request, servicio=Depends(get_automatizacion)):
    """Consultar solo los registros: no conecta con el proveedor ni ejecuta un ciclo."""
    try:
        datos = servicio.panel()
    except (OSError, ValueError, RuntimeError):
        return _error(request, "No se pudo leer el estado de automatización. Conserva los registros y revisa las rutas configuradas.", 503)
    return templates.TemplateResponse(request=request, name="automatizacion/panel.html",
                                      context=_contexto(request, panel=datos))


@router.get("/automatizacion/ejecuciones/{identificador}")
def ejecucion(identificador: str, request: Request, servicio=Depends(get_automatizacion)):
    if not identificador_valido(identificador):
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    try:
        datos = servicio.consultar_ejecucion(identificador)
    except (OSError, ValueError, RuntimeError):
        return _error(request, "No se pudo leer esta ejecución. Conserva sus registros antes de intentar recuperarla.", 503)
    if datos is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return templates.TemplateResponse(request=request, name="automatizacion/ejecucion.html",
                                      context=_contexto(request, ejecucion=datos))


@router.post("/automatizacion/{accion}")
def actuar(accion: str, request: Request, token_local: Annotated[str, Form()] = "",
           juego: Annotated[str, Form()] = "todos", servicio=Depends(get_automatizacion),
           lanzar=Depends(get_lanzador_automatizacion)):
    if proteccion_local.motivo_de_rechazo(request, token_local) is not None:
        return _error(request, "Acción rechazada. Abre el panel desde localhost en esta máquina y vuelve a intentarlo con su formulario.", 403)
    if accion not in ("pausar", "reanudar", "recuperar", "comprobar") or juego not in (*NOMBRES, "todos"):
        return _error(request, "Acción o juego no reconocido.", 422)
    try:
        if accion == "comprobar":
            juegos = None if juego == "todos" else [juego]
            lanzar(lambda: servicio.ciclo(juegos=juegos, forzar=True, origen="web"))
        else:
            getattr(servicio, accion)()
    except OperacionConcurrenteError:
        return _error(request, "Otro proceso conserva este recurso. Espera a que termine y revisa el estado antes de repetir la acción.", 409)
    except (OSError, RuntimeError):
        return _error(request, "No se pudo completar la solicitud. Revisa el estado y los registros antes de repetirla.", 503)
    except ValueError:
        return _error(request, "La configuración operativa no permite esta acción. Revisa sus rutas y la versión registrada de cada juego.", 422)
    return RedirectResponse(url="/automatizacion", status_code=303)
