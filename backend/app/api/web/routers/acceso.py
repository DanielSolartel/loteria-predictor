"""Acceso y salida de la consola local (Fase 10, E10.1).

Excepciones de autenticación, únicas y concretas (ver `seguridad_consola.politicas.EXCEPCIONES`):
- `GET /acceso`: formulario; crea una presesión y deriva su token CSRF.
- `POST /acceso`: credenciales. La dependencia global ya comprobó límite local, origen y CSRF de presesión;
  aquí se aplican la limitación de intentos, la verificación y la creación de la sesión (identificador nuevo).
- `POST /salir`: exige sesión y su CSRF; invalida la sesión en el servidor.

No hay alta ni recuperación de cuentas por web: solo `python -m scripts.consola_cuentas` en el equipo.
"""
from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.seguridad_consola.almacen import ABSOLUTA, PRESESION_DURACION, derivar_csrf
from app.seguridad_consola.consola import COOKIE_PRESESION, COOKIE_SESION, ErrorConsola, nombre_cookie, templates

router = APIRouter()

_SIGUIENTE = re.compile(r"/(?![/\\])[A-Za-z0-9_\-./%?=&]{0,500}")
MENSAJES = {
    "credenciales": "Usuario o contraseña no válidos.",
    "espera": "Demasiados intentos. Espera unos minutos antes de volver a intentarlo.",
    "presesion": "El formulario de acceso caducó. Vuelve a intentarlo.",
}


def siguiente_seguro(valor: str | None) -> str:
    """Solo rutas relativas de la propia consola; nunca otro origen, `//`, barras invertidas ni el acceso."""
    if not isinstance(valor, str) or not _SIGUIENTE.fullmatch(valor) or valor.startswith(("/acceso", "/salir")):
        return "/"
    return valor


def _cookie(respuesta, nombre: str, valor: str, edad: int) -> None:
    respuesta.set_cookie(nombre_cookie(nombre), valor, max_age=edad, path="/", httponly=True, samesite="strict",
                         secure=get_settings().consola_cookie_segura)


def _borrar(respuesta, nombre: str) -> None:
    respuesta.delete_cookie(nombre_cookie(nombre), path="/", httponly=True, samesite="strict",
                            secure=get_settings().consola_cookie_segura)


def _formulario(request: Request, siguiente: str, mensaje: str | None = None, estado: int = 200, cabeceras=None):
    almacen = request.scope["consola"].almacen
    presesion = almacen.crear_presesion()
    respuesta = templates.TemplateResponse(request=request, name="seguridad/acceso.html", status_code=estado,
                                           headers={"Cache-Control": "no-store", **(cabeceras or {})},
                                           context={"csrf_acceso": derivar_csrf(presesion, "acceso"),
                                                    "siguiente": siguiente, "mensaje": mensaje})
    _cookie(respuesta, COOKIE_PRESESION, presesion, PRESESION_DURACION)
    return respuesta


@router.get("/acceso")
def formulario_acceso(request: Request, siguiente: str = "/"):
    almacen = request.scope["consola"].almacen
    if almacen.sesion(request.cookies.get(nombre_cookie(COOKIE_SESION))) is not None:
        return RedirectResponse(siguiente_seguro(siguiente), status_code=303, headers={"Cache-Control": "no-store"})
    return _formulario(request, siguiente_seguro(siguiente))


@router.post("/acceso")
def acceder(request: Request, usuario: Annotated[str, Form(max_length=200)] = "",
            contrasena: Annotated[str, Form(max_length=1024)] = "", siguiente: Annotated[str, Form()] = "/"):
    almacen = request.scope["consola"].almacen
    destino = siguiente_seguro(siguiente)
    resultado, identificador = almacen.autenticar(usuario, contrasena, request.cookies.get(nombre_cookie(COOKIE_PRESESION)),
                                                  request.client.host if request.client else "")
    if resultado != "ok":
        estado = {"credenciales": 401, "espera": 429, "presesion": 400}[resultado]
        cabeceras = {"Retry-After": "60"} if resultado == "espera" else None
        return _formulario(request, destino, MENSAJES[resultado], estado, cabeceras)
    respuesta = RedirectResponse(destino, status_code=303, headers={"Cache-Control": "no-store"})
    _borrar(respuesta, COOKIE_PRESESION)
    _cookie(respuesta, COOKIE_SESION, identificador, ABSOLUTA)
    return respuesta


@router.post("/salir")
def salir(request: Request):
    contexto = request.scope["consola"]
    if contexto.usuario is None:
        raise ErrorConsola(401, "sin_sesion", "No hay una sesión abierta.", redirigir=True)
    contexto.almacen.cerrar_sesion(request.cookies.get(nombre_cookie(COOKIE_SESION)), contexto.usuario)
    respuesta = RedirectResponse("/acceso", status_code=303, headers={"Cache-Control": "no-store"})
    _borrar(respuesta, COOKIE_SESION)
    return respuesta
