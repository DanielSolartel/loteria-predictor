"""
Proteccion de las acciones que entrenan modelos (Producto 1).

La aplicacion no tiene autenticacion ni middleware de seguridad global, y
cualquier pagina abierta en el navegador puede enviar un formulario POST
a `http://localhost:8000`. Entrenar y verificar consumen CPU durante
segundos, asi que solo se aceptan si se cumplen todas estas condiciones:

- el cliente TCP es la propia maquina (`127.0.0.1` o `::1`);
- la cabecera `Host` es local (`localhost`, `127.0.0.1` o `[::1]`), lo que
  frena el DNS rebinding;
- `Origin` y `Referer`, si vienen, son del mismo origen, y `Sec-Fetch-Site`
  no indica un sitio ajeno;
- el formulario trae el token local del proceso, que solo se obtiene
  leyendo una pagina de la propia aplicacion (otro origen no puede leerla).

Ademas, un unico entrenamiento a la vez por proceso (`CERROJO_DE_ENTRENAMIENTO`).
El comando `python -m scripts.pronostico_experimental` sigue disponible en la
propia maquina sin pasar por HTTP.
"""
from __future__ import annotations

import hmac
import secrets
import threading
from urllib.parse import urlsplit

from fastapi import Request

TOKEN_LOCAL = secrets.token_urlsafe(32)
"""Token aleatorio por proceso; cambia al reiniciar el servidor."""

CERROJO_DE_ENTRENAMIENTO = threading.Lock()

CLIENTES_LOCALES = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})
HOSTS_LOCALES = frozenset({"localhost", "127.0.0.1", "::1"})


def token_local() -> str:
    return TOKEN_LOCAL


def _nombre_de_host(valor: str) -> str:
    return (urlsplit(f"//{valor}").hostname or "").lower()


def motivo_de_rechazo(request: Request, token: str | None) -> str | None:
    """None si la peticion puede entrenar; si no, el motivo."""
    cliente = request.client.host if request.client else ""
    if cliente not in CLIENTES_LOCALES:
        return "la peticion no viene de esta misma maquina"
    host = request.headers.get("host", "")
    if _nombre_de_host(host) not in HOSTS_LOCALES:
        return "la cabecera Host no es local"
    propio = f"{request.url.scheme}://{host}".lower()
    origen = request.headers.get("origin")
    if origen is not None and origen.lower() != propio:
        return "el origen de la peticion es ajeno a la aplicacion"
    referente = request.headers.get("referer")
    if referente:
        partes = urlsplit(referente)
        if f"{partes.scheme}://{partes.netloc}".lower() != propio:
            return "la pagina de origen es ajena a la aplicacion"
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        return "el navegador indica una peticion entre sitios"
    if not token or not hmac.compare_digest(token, TOKEN_LOCAL):
        return "falta el token local del formulario o no es valido"
    return None
