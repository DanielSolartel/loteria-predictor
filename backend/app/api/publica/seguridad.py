"""Autenticacion por clave de API (`X-API-Key`) y cuota por clave.

- La clave solo se acepta en la cabecera (nunca en la URL). Se compara su
  SHA-256 con las huellas configuradas en tiempo constante; el servidor no
  guarda ni registra claves: solo el identificador de la clave aceptada.
- Sin configuracion valida, toda ruta protegida responde 503 `no_configurada`.
- La cuota se descuenta DESPUES de autenticar: una clave inventada no crea
  estado (el limite por IP del middleware la frena). Cada ruta declara su coste.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections.abc import Callable

from fastapi import Request, Response, Security
from fastapi.security import APIKeyHeader

from app.api.publica.configuracion import ClaveConfigurada
from app.api.publica.errores import ErrorPublico

ENCABEZADO = "X-API-Key"
PREFIJO = "lpk_"
_FORMATO = re.compile(r"[\x21-\x7e]{32,256}")

esquema = APIKeyHeader(name=ENCABEZADO, auto_error=False, scheme_name="ClaveDeAPI",
                       description="Clave de API emitida por el operador "
                                   "(nunca en la URL ni en el código distribuido).")


def generar_clave() -> str:
    return PREFIJO + secrets.token_urlsafe(32)


def huella(clave: str) -> str:
    return hashlib.sha256(clave.encode("ascii")).hexdigest()


def formato_admitido(clave: str | None) -> bool:
    return bool(clave) and _FORMATO.fullmatch(clave) is not None


def identificar(clave: str | None, claves: tuple[ClaveConfigurada, ...]) -> str | None:
    """Identificador de la clave configurada que coincide, o None. Recorre
    todas las huellas con `compare_digest` (sin salida temprana)."""
    if not formato_admitido(clave):
        return None
    digest = hashlib.sha256(clave.encode("ascii")).digest()
    encontrada = None
    for configurada in claves:
        if hmac.compare_digest(digest, configurada.huella):
            encontrada = configurada.identificador
    return encontrada


def acceso(coste: int) -> Callable:
    """Dependencia de una ruta protegida que cuesta `coste` fichas."""
    def _acceso(request: Request, response: Response, clave: str | None = Security(esquema)) -> str:
        estado = request.app.state
        if not estado.configuracion.abierta:
            raise ErrorPublico(503, "no_configurada", "La API pública no tiene claves válidas configuradas")
        identificador = identificar(clave, estado.configuracion.claves)
        if identificador is None:
            raise ErrorPublico(401, "no_autenticado", "Clave de API ausente o no válida",
                               {"WWW-Authenticate": f'ApiKey header="{ENCABEZADO}"'})
        request.state.cliente = identificador
        decision = estado.limitador_por_clave.consumir(identificador, coste)
        limites = {"X-RateLimit-Limit": str(estado.limitador_por_clave.capacidad),
                   "X-RateLimit-Remaining": str(decision.restantes)}
        if not decision.permitida:
            raise ErrorPublico(429, "limite_excedido",
                               f"Límite de uso de la clave excedido; reintente en {decision.reintentar_en} s",
                               {**limites, "Retry-After": str(decision.reintentar_en)})
        response.headers.update(limites)
        return identificador
    return _acceso
