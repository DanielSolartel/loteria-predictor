"""
Pasarela local de la Fase 9.1: sirve la SPA compilada y reenvia a `/api/v1`.

Arranque soportado (desde `backend/`), el mismo de `docs/fase9_frontend.md`:

    `uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers`

- `--no-access-log`: el registro de acceso de Uvicorn escribiria la URL con su
  consulta. El registro propio `app.pasarela` no la incluye.
- `--no-proxy-headers`: el cliente es siempre el del socket; `X-Forwarded-For`
  no puede hacer pasar por local a otro origen.

Controles de cada solicitud, en este orden:
1. solo GET (405 con `Allow: GET` para el resto, sin CORS);
2. cliente loopback; `Host` en `PASARELA_HOSTS` (frente al DNS rebinding);
3. en `/api/v1` y `/pasarela`: `Origin`, si viene, en `PASARELA_ORIGENES`, y
   `Sec-Fetch-Site`, si viene, `same-origin` o `none`;
4. ruta sin ambiguedades: ASCII visible, sin `%`, `\\`, `//`, `.`/`..` ni barra
   final.

Las consultas a `/api/v1` deben casar con la lista cerrada de `rutas.py`; la
pasarela anade la clave del servidor y solo devuelve las cabeceras previstas.
Los errores propios tienen el formato de la API (`{"error": {"codigo",
"mensaje", "solicitud"}}`), `X-Request-ID` y `Cache-Control: no-store`; un fallo
inesperado se convierte aqui en un 500 sanitizado y no llega a Uvicorn.

Fuera de `/api/v1` solo se sirven archivos de `dist/` con extension conocida;
una ruta de la SPA (sin extension) recibe `index.html`; una ruta de API
desconocida, un recurso inexistente o un archivo fuera de `dist/`, nunca.

Perfil PRIVADO (Fase 10, E10.2; `PASARELA_PERFIL=privado`): el paso 2 cambia.
En lugar del cliente loopback se exige el ingreso del proxy autenticado
(`privada.identidad_verificada`: IP exacta del socket, secreto del proxy en
tiempo constante e identidad de la persona); despues, `Host` en la lista
exacta. Cada consulta a `/api/v1` descuenta su coste de la cuota de la
persona y de la agregada ANTES de reenviarse (429 con `Retry-After`). El
arranque soportado es el mismo modulo con `--workers 1` (ver `privada.py`).
"""
from __future__ import annotations

import ipaddress
import json
import logging
import re
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl

import anyio
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.pasarela import privada, rutas
from app.pasarela.cliente import ClienteDeLaApi, FalloDeDestino, RespuestaDeLaApi
from app.pasarela.configuracion import AjustesPasarela, ConfiguracionPasarela, desde_ajustes

registro = logging.getLogger("app.pasarela")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
SEGURIDAD = {"Content-Security-Policy": CSP, "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff",
             "Referrer-Policy": "no-referrer", "Cross-Origin-Opener-Policy": "same-origin",
             "Cross-Origin-Resource-Policy": "same-origin",
             "Permissions-Policy": "camera=(), microphone=(), geolocation=()", "Cache-Control": "no-store"}
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
         ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8", ".json": "application/json"}
ESTADOS_DE_LA_API = frozenset({200, 401, 404, 409, 422, 429, 500, 503})
_RUTA_SEGURA = re.compile(r"/(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*)?")
_ID = re.compile(r"[0-9a-f]{32}")
_DIGITOS = re.compile(r"[0-9]{1,6}")
_METODOS = frozenset({"GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"})
_SEC_FETCH_SITE = frozenset({"same-origin", "none"})


def _configurar_registro() -> None:
    if registro.level == logging.NOTSET:
        registro.setLevel(logging.INFO)
    if not registro.handlers and not logging.getLogger().handlers:
        manejador = logging.StreamHandler()
        manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        registro.addHandler(manejador)


def error(estado: int, codigo: str, mensaje: str, solicitud: str, cabeceras: dict | None = None) -> JSONResponse:
    return JSONResponse({"error": {"codigo": codigo, "mensaje": mensaje, "solicitud": solicitud}}, status_code=estado,
                        headers=cabeceras)


class Pasarela:
    """Aplicacion ASGI de la pasarela."""

    def __init__(self, configuracion: ConfiguracionPasarela, cliente: ClienteDeLaApi | None = None):
        self.configuracion = configuracion
        self.cliente = cliente or ClienteDeLaApi(configuracion.destino)
        perfil = configuracion.privado
        self.cuotas = (privada.CuotasDeConsulta(perfil.fichas_persona, perfil.fichas_agregadas, perfil.max_personas)
                       if perfil is not None else None)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while (mensaje := await receive())["type"] != "lifespan.shutdown":
                if mensaje["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
            await send({"type": "lifespan.shutdown.complete"})
            return
        if scope["type"] != "http":
            return
        request = Request(scope, receive)
        solicitud, inicio, plantilla = uuid.uuid4().hex, time.perf_counter(), "rechazo"
        request.state.identidad = None
        try:
            respuesta, plantilla = await self._responder(request, solicitud)
        except Exception as exc:  # no BaseException: cancelaciones y salidas del proceso siguen su curso
            registro.error("pasarela error_interno=%s solicitud=%s", type(exc).__name__, solicitud)
            respuesta, plantilla = error(500, "error_interno", "Error interno de la pasarela", solicitud), "error"
        respuesta.headers.setdefault("X-Request-ID", solicitud)
        for nombre, valor in SEGURIDAD.items():
            respuesta.headers[nombre] = valor
        metodo = request.method if request.method in _METODOS else "OTRO"
        if self.configuracion.privado is None:
            registro.info("pasarela %s %s %s %.1fms solicitud=%s", metodo, plantilla, respuesta.status_code,
                          (time.perf_counter() - inicio) * 1000, solicitud)
        else:  # la identidad acreditada por el proxy (nunca la clave, el secreto ni la consulta)
            registro.info("pasarela %s %s %s %.1fms identidad=%s solicitud=%s", metodo, plantilla,
                          respuesta.status_code, (time.perf_counter() - inicio) * 1000,
                          request.state.identidad or "-", solicitud)
        await respuesta(scope, receive, send)

    # ------------------------------------------------------------------
    async def _responder(self, request: Request, solicitud: str) -> tuple[Response, str]:
        conf = self.configuracion
        if request.method != "GET":
            return error(405, "metodo_no_permitido", "La pasarela solo admite GET", solicitud,
                         {"Allow": "GET"}), "rechazo"
        cliente = request.client.host if request.client else ""
        if conf.privado is not None:
            try:
                request.state.identidad = privada.identidad_verificada(
                    cliente, request.scope.get("headers", ()), conf.privado.proxies,
                    conf.privado.secreto.get_secret_value())
            except privada.IngresoNoFiable as fallo:
                return error(403, fallo.codigo, fallo.mensaje, solicitud), "rechazo"
        elif not _loopback(cliente):
            return error(403, "cliente_no_local", "Solo se admiten clientes de este equipo", solicitud), "rechazo"
        if request.headers.get("host", "") not in conf.hosts or len(request.headers.getlist("host")) != 1:
            return error(403, "host_no_permitido", "Host no admitido", solicitud), "rechazo"
        crudo = request.scope.get("raw_path") or request.scope["path"].encode()
        try:
            ruta = crudo.decode("ascii")
        except UnicodeDecodeError:
            ruta = ""
        if not _RUTA_SEGURA.fullmatch(ruta) or ".." in ruta or "/./" in ruta or ruta.endswith("/.") \
                or (len(ruta) > 1 and ruta.endswith("/")) or len(ruta) > 512:
            return error(400, "ruta_no_valida", "Ruta no válida", solicitud), "rechazo"
        es_api = ruta == "/api" or ruta.startswith("/api/")
        if es_api or ruta.startswith("/pasarela/"):
            origen = request.headers.get("origin")
            if origen is not None and origen not in conf.origenes:
                return error(403, "origen_no_permitido", "Origen no admitido", solicitud), "rechazo"
            sitio = request.headers.get("sec-fetch-site")
            if sitio is not None and sitio not in _SEC_FETCH_SITE:
                return error(403, "origen_no_permitido", "Origen no admitido", solicitud), "rechazo"
        if es_api:
            return await self._api(request, ruta, solicitud)
        if ruta == "/pasarela/configuracion":
            return JSONResponse({"consola_local": conf.consola_local, "api": "v1"}), "configuracion"
        return await self._estatico(ruta, solicitud)

    async def _api(self, request: Request, ruta: str, solicitud: str) -> tuple[Response, str]:
        publica = rutas.buscar(ruta)
        if publica is None:
            return error(404, "ruta_no_disponible", "Ruta de API no disponible", solicitud), "sin_ruta"
        consulta_cruda = request.scope.get("query_string", b"")
        try:
            pares = parse_qsl(consulta_cruda.decode("ascii"), keep_blank_values=True, strict_parsing=bool(consulta_cruda),
                              max_num_fields=16)
            consulta = rutas.consulta_reenviable(publica, pares, len(consulta_cruda))
        except rutas.ConsultaNoAdmitida as fallo:
            return error(422, fallo.codigo, fallo.mensaje, solicitud), publica.plantilla
        except (UnicodeDecodeError, ValueError):
            return error(422, "parametro_no_valido", "Consulta no válida", solicitud), publica.plantilla
        if not self.configuracion.abierta:
            return error(503, "pasarela_no_configurada", "La pasarela no tiene una clave de API válida",
                         solicitud), publica.plantilla
        if self.cuotas is not None:
            decision = self.cuotas.consumir(request.state.identidad, privada.COSTES[publica.plantilla])
            limites = {"X-RateLimit-Limit": str(decision.capacidad), "X-RateLimit-Remaining": str(decision.restantes)}
            if not decision.permitida:
                codigo, mensaje = {
                    "persona": ("limite_excedido", "Límite de consultas de su identidad excedido"),
                    "agregado": ("limite_agregado_excedido", "Límite conjunto de consultas excedido"),
                    "capacidad": ("limite_identidades_excedido",
                                  "Demasiadas identidades con consultas recientes; reintente más tarde"),
                }[decision.alcance]
                return error(429, codigo, f"{mensaje}; reintente en {decision.reintentar_en} s", solicitud,
                             {**limites, "Retry-After": str(decision.reintentar_en)}), publica.plantilla
        try:
            r = await self.cliente.get(ruta + (f"?{consulta}" if consulta else ""),
                                       self.configuracion.clave.get_secret_value())
        except FalloDeDestino as fallo:
            cabeceras = {"Retry-After": "1"} if fallo.codigo == "pasarela_ocupada" else None
            return error(fallo.estado, fallo.codigo, _MENSAJES[fallo.codigo], solicitud, cabeceras), publica.plantilla
        respuesta = _desde_la_api(r, solicitud)
        if self.cuotas is not None:  # la persona ve su propia cuota, no la de la clave compartida de la pasarela
            respuesta.headers.update(limites)
        return respuesta, publica.plantilla

    async def _estatico(self, ruta: str, solicitud: str) -> tuple[Response, str]:
        dist = self.configuracion.dist
        nombre = ruta.rsplit("/", 1)[-1]
        if "." in nombre or ruta.startswith("/assets/") or ruta == "/assets":
            extension = "." + nombre.rsplit(".", 1)[-1] if "." in nombre else ""
            archivo = _dentro_de(dist, ruta)
            if extension not in TIPOS or archivo is None:
                return _no_encontrado(solicitud), "estatico"
            contenido = await anyio.to_thread.run_sync(archivo.read_bytes)
            return Response(contenido, media_type=TIPOS[extension]), "estatico"
        indice = _dentro_de(dist, "/index.html")
        if indice is None:
            return error(503, "frontend_no_compilado", "La interfaz no está compilada", solicitud), "spa"
        return Response(await anyio.to_thread.run_sync(indice.read_bytes), media_type=TIPOS[".html"]), "spa"


_MENSAJES = {"api_no_disponible": "La API pública no está disponible",
             "api_sin_respuesta": "La API pública no respondió a tiempo",
             "respuesta_demasiado_grande": "La respuesta de la API supera el tamaño admitido",
             "respuesta_no_valida": "La respuesta de la API no es válida",
             "pasarela_ocupada": "La pasarela está ocupada; reintente en un momento"}


def _loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _dentro_de(dist: Path, ruta: str) -> Path | None:
    """El archivo regular de `dist` que corresponde a `ruta`, sin salir de `dist` ni seguir enlaces fuera."""
    try:
        base = dist.resolve(strict=True)
        candidato = (base / ruta.lstrip("/")).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not candidato.is_relative_to(base) or not candidato.is_file():
        return None
    return candidato


def _no_encontrado(solicitud: str) -> Response:
    return Response("No encontrado", status_code=404, media_type="text/plain; charset=utf-8",
                    headers={"X-Request-ID": solicitud})


def _desde_la_api(r: RespuestaDeLaApi, solicitud: str) -> Response:
    """Devuelve la respuesta contractual de la API tal cual, o un 502 si no lo es."""
    tipo = r.cabeceras.get("content-type", "")
    valido = r.estado in ESTADOS_DE_LA_API and tipo.split(";")[0].strip() == "application/json"
    if valido:
        try:
            cuerpo = json.loads(r.cuerpo)
        except ValueError:
            valido = False
        else:
            if r.estado != 200:
                detalle = cuerpo.get("error") if isinstance(cuerpo, dict) else None
                valido = isinstance(detalle, dict) and isinstance(detalle.get("codigo"), str)
    if not valido:
        return error(502, "respuesta_no_valida", _MENSAJES["respuesta_no_valida"], solicitud)
    cabeceras = {}
    if _ID.fullmatch(r.cabeceras.get("x-request-id", "")):
        cabeceras["X-Request-ID"] = r.cabeceras["x-request-id"]
    if r.estado in (429, 503) and _DIGITOS.fullmatch(r.cabeceras.get("retry-after", "")):
        cabeceras["Retry-After"] = r.cabeceras["retry-after"]
    for nombre in ("x-ratelimit-limit", "x-ratelimit-remaining"):
        if _DIGITOS.fullmatch(r.cabeceras.get(nombre, "")):
            cabeceras[nombre.title().replace("Ratelimit", "RateLimit")] = r.cabeceras[nombre]
    return Response(r.cuerpo, status_code=r.estado, media_type="application/json", headers=cabeceras)


def crear_app(configuracion: ConfiguracionPasarela | None = None) -> Pasarela:
    _configurar_registro()
    return Pasarela(configuracion if configuracion is not None else desde_ajustes(AjustesPasarela()))


app = crear_app()
