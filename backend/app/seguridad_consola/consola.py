"""Seguridad de la consola local `app.main:app` (Fase 10, E10.1).

Dos capas, ambas activas por defecto (también con `environment=development`):

1. `LimiteLocal` (middleware ASGI, la capa más externa): toda solicitud HTTP, incluidos los recursos
   estáticos, debe venir de un cliente loopback, con un único `Host` local y sin cabeceras de reenvío
   (`Forwarded`, `X-Forwarded-*`, `X-Real-IP`). Una conexión remota (incluida la VPN) se rechaza aunque
   presente una sesión válida. Prepara el contexto y, al terminar, registra en auditoría las escrituras.
2. `autorizar_consola` (dependencia global de FastAPI, la primera que se resuelve en cada ruta): busca la
   política de la ruta (`politicas.POLITICAS`), comprueba el almacén (fallo cerrado), el origen y el CSRF
   de las escrituras, la sesión y el rol. Rechaza antes de que se resuelva cualquier otra dependencia de la
   ruta, así que una operación rechazada no construye servicios ni lanza trabajos.

Las defensas locales de las 26 rutas que ya las tenían (`proteccion_local.motivo_de_rechazo`, con
`TOKEN_LOCAL`) siguen en su sitio: el CSRF de sesión se añade, no las sustituye.
"""
from __future__ import annotations

import functools
import hmac
import logging
import re
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from app.core.config import get_settings
from app.seguridad_consola import politicas as pol
from app.seguridad_consola.almacen import (
    AlmacenSeguridad, ConsolaNoDisponible, derivar_csrf, identificador_valido, rol_suficiente, ruta_predeterminada,
    texto_seguro,
)

registro = logging.getLogger("app.seguridad_consola")
templates = Jinja2Templates(directory="app/templates")

CLIENTES_LOCALES = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})
CABECERAS_REENVIO = frozenset({"forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
                               "x-forwarded-port", "x-forwarded-prefix", "x-real-ip", "x-client-ip"})
METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
CABECERA_CSRF = "x-csrf-token"
CAMPO_CSRF = "csrf_token"
MENSAJES_NO_DISPONIBLE = {
    "no_provisionada": "La consola no tiene cuentas provisionadas.",
    "sin_cuentas": "La consola no tiene ninguna cuenta activa.",
    "permisos": "El almacén de seguridad tiene permisos que no son solo del propietario.",
    "permisos_no_verificables": "No se pudieron verificar los permisos del almacén de seguridad.",
    "corrupta": "El almacén de seguridad no se puede leer.",
    "esquema": "El almacén de seguridad no corresponde a esta consola.",
    "no_disponible": "El almacén de seguridad no está disponible.",
}


def nombre_cookie(base: str) -> str:
    return ("__Host-" + base) if get_settings().consola_cookie_segura else base


COOKIE_SESION = "lp_consola_sesion"
COOKIE_PRESESION = "lp_consola_presesion"


@dataclass
class Contexto:
    """Estado de seguridad de la solicitud en curso (en `scope["consola"]`)."""
    usuario: str | None = None
    rol: str | None = None
    csrf: str | None = None
    almacen: AlmacenSeguridad | None = None
    auditar: tuple[str, str] | None = None


class ErrorConsola(Exception):
    def __init__(self, estado: int, codigo: str, mensaje: str, *, redirigir: bool = False, cabeceras=None):
        super().__init__(codigo)
        self.estado, self.codigo, self.mensaje = estado, codigo, mensaje
        self.redirigir = redirigir
        self.cabeceras = dict(cabeceras or {})


@functools.lru_cache
def _almacen_configurado(directorio: str) -> AlmacenSeguridad:
    return AlmacenSeguridad(ruta_predeterminada(directorio))


def obtener_almacen(request: Request) -> AlmacenSeguridad:
    """El almacén inyectado en `app.state.almacen_seguridad` (pruebas y ensayos) o el configurado. Construirlo
    no crea archivos."""
    inyectado = getattr(request.app.state, "almacen_seguridad", None)
    return inyectado if inyectado is not None else _almacen_configurado(get_settings().consola_seguridad_directorio)


# v2 (E101-ROB-01): gramática cerrada del Host, sin `urlsplit` (que lanza con entradas como `[`). Solo
# `localhost`, `127.0.0.1` o `[::1]`, con puerto opcional de 1 a 5 cifras (<= 65535). Lo demás se rechaza (403).
_HOST_LOCAL = re.compile(r"(?i)(localhost|127\.0\.0\.1|\[::1\])(?::([0-9]{1,5}))?")


def host_local_valido(valor: str) -> bool:
    coincidencia = _HOST_LOCAL.fullmatch(valor) if isinstance(valor, str) and len(valor) <= 64 else None
    return coincidencia is not None and (coincidencia.group(2) is None or 0 < int(coincidencia.group(2)) <= 65535)


def _es_api(ruta: str) -> bool:
    return ruta == "/api" or ruta.startswith("/api/")


# ---------------------------------------------------------------------------- capa 1: límite local
class LimiteLocal:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cabeceras = [(k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in scope.get("headers", [])]
        motivo = None
        if any(k in CABECERAS_REENVIO for k, _ in cabeceras):
            motivo = "cabeceras de reenvío no admitidas"
        elif (scope.get("client") or ("", 0))[0] not in CLIENTES_LOCALES:
            motivo = "la conexión no viene de este equipo"
        else:
            hosts = [v for k, v in cabeceras if k == "host"]
            if len(hosts) != 1 or not host_local_valido(hosts[0]):
                motivo = "la cabecera Host no es local"
        if motivo is not None:
            registro.warning("consola rechazo_local motivo=%s ruta=%s", motivo, texto_seguro(scope.get("path", ""), 200))
            respuesta = _respuesta_simple(scope.get("path", ""), 403, "solo_local",
                                          f"Acción rechazada: {motivo}. La consola solo atiende en este equipo.")
            await respuesta(scope, receive, send)
            return
        contexto = Contexto()
        scope["consola"] = contexto
        estado = {"codigo": 500}

        async def enviar(mensaje):
            if mensaje["type"] == "http.response.start":
                estado["codigo"] = mensaje["status"]
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            if contexto.auditar is not None and contexto.almacen is not None:
                evento, detalle = contexto.auditar
                resultado = "ok" if estado["codigo"] < 400 else f"http_{estado['codigo']}"
                try:
                    contexto.almacen.auditar(contexto.usuario or "-", evento, detalle, resultado)
                except ConsolaNoDisponible:
                    registro.error("consola auditoria_no_disponible evento=%s", evento)
                registro.info("consola auditoria usuario=%s evento=%s detalle=%s resultado=%s",
                              contexto.usuario, evento, detalle, resultado)


def _respuesta_simple(ruta: str, estado: int, codigo: str, mensaje: str):
    if _es_api(ruta):
        return JSONResponse({"detail": mensaje, "codigo": codigo}, status_code=estado, headers={"Cache-Control": "no-store"})
    cuerpo = ("<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"UTF-8\"><title>Consola local</title></head>"
              f"<body><p>{_escapar(mensaje)}</p></body></html>")
    return HTMLResponse(cuerpo, status_code=estado, headers={"Cache-Control": "no-store"})


def _escapar(texto: str) -> str:
    return (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------- capa 2: autorización
def _origen_aceptable(request: Request) -> bool:
    host = request.headers.get("host", "")
    propio = f"{request.url.scheme}://{host}".lower()
    origen = request.headers.get("origin")
    if origen is not None and origen.lower() != propio:
        return False
    referente = request.headers.get("referer")
    if referente:
        try:
            partes = urlsplit(referente)
        except ValueError:  # Referer no interpretable: origen no acreditado (403, no 500)
            return False
        if f"{partes.scheme}://{partes.netloc}".lower() != propio:
            return False
    return request.headers.get("sec-fetch-site", "same-origin") in ("same-origin", "none")


def _coincide(token: str | None, esperado: str | None) -> bool:
    return isinstance(token, str) and isinstance(esperado, str) and len(token) == len(esperado) and \
        hmac.compare_digest(token.encode("ascii", "replace"), esperado.encode("ascii"))


async def autorizar_consola(request: Request) -> None:
    contexto: Contexto | None = request.scope.get("consola")
    if contexto is None:  # sin la capa 1 no se atiende nada (fallo cerrado)
        raise ErrorConsola(500, "limite_local_ausente", "La consola no tiene activo su límite local.")
    plantilla = getattr(request.scope.get("route"), "path", None)
    metodo = request.method
    politica = pol.politica(metodo, plantilla) if plantilla else None
    if politica is None:
        registro.warning("consola sin_politica metodo=%s ruta=%s", metodo, texto_seguro(plantilla, 200))
        raise ErrorConsola(403, "sin_politica", "Esta ruta no tiene una política de acceso registrada.")
    almacen = obtener_almacen(request)
    try:
        almacen.comprobar()
    except ConsolaNoDisponible as error:
        raise ErrorConsola(503, "consola_no_disponible", MENSAJES_NO_DISPONIBLE.get(error.motivo, "Consola no disponible."),
                           cabeceras={"Retry-After": "60"}) from None
    contexto.almacen = almacen
    insegura = metodo not in METODOS_SEGUROS
    formulario: dict[str, str] = {}
    if insegura:
        if not _origen_aceptable(request):
            raise ErrorConsola(403, "origen", "El origen de la solicitud es ajeno a la consola.")
        tipo = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if tipo in ("application/x-www-form-urlencoded", "multipart/form-data"):
            formulario = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
    token = request.headers.get(CABECERA_CSRF) or formulario.get(CAMPO_CSRF)
    if politica.tipo == "acceso":
        if insegura:
            presesion = request.cookies.get(nombre_cookie(COOKIE_PRESESION))
            # v2 (E101-ROB-01): forma y tamaño antes de derivar (una cookie no ASCII o enorme se rechaza, 403).
            if not identificador_valido(presesion) or not _coincide(token, derivar_csrf(presesion, "acceso")):
                almacen.auditar("-", "acceso", "csrf de presesión ausente o no válido", "rechazado")
                raise ErrorConsola(403, "csrf", "El formulario de acceso caducó o no es válido. Recarga la página.")
        return
    sesion = almacen.sesion(request.cookies.get(nombre_cookie(COOKIE_SESION)))
    if sesion is None:
        raise ErrorConsola(401, "sin_sesion", "Inicia sesión para usar la consola.", redirigir=True)
    contexto.usuario, contexto.rol, contexto.csrf = sesion.usuario, sesion.rol, sesion.csrf
    detalle = f"{metodo} {texto_seguro(plantilla, 120)}"
    if insegura and not _coincide(token, sesion.csrf):
        almacen.auditar(sesion.usuario, "csrf", detalle, "rechazado")
        raise ErrorConsola(403, "csrf", "Falta el token de la sesión o no es válido. Recarga la página.")
    if politica.tipo == "sesion":
        return
    requerido = politica.rol_requerido(request.path_params, formulario)
    if politica.por_accion:
        detalle += f" {politica.parametro}=" + texto_seguro(
            (request.path_params if politica.fuente == "ruta" else formulario).get(politica.parametro, ""), 40)
    if requerido is None:
        almacen.auditar(sesion.usuario, "accion_no_reconocida", detalle, "rechazado")
        raise ErrorConsola(422, "accion_no_reconocida", "Acción no reconocida.")
    if not rol_suficiente(sesion.rol, requerido):
        almacen.auditar(sesion.usuario, "permiso", f"{detalle} requiere={requerido}", "rechazado")
        raise ErrorConsola(403, "permiso", f"Tu rol ({sesion.rol}) no permite esta acción; requiere {requerido}.")
    if insegura:
        contexto.auditar = (politica.efecto, detalle)


def manejar_error_consola(request: Request, exc: ErrorConsola):
    cabeceras = {"Cache-Control": "no-store", **exc.cabeceras}
    ruta = request.url.path
    if _es_api(ruta):
        return JSONResponse({"detail": exc.mensaje, "codigo": exc.codigo}, status_code=exc.estado, headers=cabeceras)
    if exc.redirigir:
        destino = "/acceso?siguiente=" + quote(ruta + (("?" + request.url.query) if request.url.query else ""), safe="")
        if request.headers.get("hx-request") == "true":
            return HTMLResponse("", status_code=401, headers={**cabeceras, "HX-Redirect": destino})
        if request.method in METODOS_SEGUROS:
            return RedirectResponse(destino, status_code=303, headers=cabeceras)
    return templates.TemplateResponse(request=request, name="seguridad/mensaje.html", status_code=exc.estado,
                                      headers=cabeceras, context={"codigo": exc.codigo, "mensaje": exc.mensaje,
                                                                  "estado": exc.estado})
