"""
Composicion de la API publica (Fase 8), separada de `app.main`.

Arranque soportado (desde `backend/`), el mismo de `docs/fase8_api_publica.md`:

    `uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers`

- `--no-access-log`: el registro de acceso de Uvicorn escribiria la URL
  completa con su consulta (p. ej. una clave enviada por error en `?api_key=`).
  El registro propio `app.api.publica` sigue activo y no la incluye.
- `--no-proxy-headers`: sin ella, Uvicorn reescribe la IP del cliente con
  `X-Forwarded-For` y una sola conexion local eludiria el limite por IP. Se usa
  siempre la IP del socket, tambien en el perfil privado de la Fase 10
  (`app.api.publica.privada:app`, `docs/fase10_consulta_privada.md`): alli el
  unico cliente admitido es la pasarela (IP exactas) y la identidad de cada
  persona la decide la pasarela, nunca una cabecera que llegue a la API.

Solo monta las rutas GET de `rutas.py` bajo `/api/v1`, la
documentacion (`/api/v1/docs`, `/api/v1/openapi.json`, desactivable) y la
salud. No monta la web, los estaticos ni ningun router REST interno: las
escrituras de `/api/sorteos` (POST/DELETE) y los POST de la web no existen aqui.

El estado de cuotas y monitoreo vive en memoria de este proceso
(`app.state`), separado de la base, los historicos, los modelos y los
almacenes del producto. CORS parte deshabilitado; si se configura, solo para
origenes explicitos, metodo GET y la cabecera de la clave.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.publica import rutas
from app.api.publica.configuracion import ConfiguracionPublica, desde_settings, validar
from app.api.publica.errores import registrar_manejadores, registro
from app.api.publica.limites import LimitadorDeCuota
from app.api.publica.monitoreo import MiddlewarePublico, Monitor
from app.api.publica.recursos import FronteraPrivada, LimiteDeCostosas
from app.api.publica.seguridad import ENCABEZADO
from app.core.config import get_settings

DESCRIPCION = """
API pública de **solo lectura** del Sistema Predictivo de Loterías (Baloto, Baloto Revancha,
MiLoto y ColorLoto): juegos, sorteos, estadísticas descriptivas, predicciones guardadas y
simulaciones guardadas, modelos registrados, carteras de Producto 5 y resultados observados de Producto 6.

- **Autenticación:** cabecera `X-API-Key` con una clave emitida por el operador. Sin clave
  válida: 401. Sin claves configuradas en el servidor: 503.
- **Límites:** cubeta de fichas **por proceso** (por clave y por IP). Al superarla: 429 con
  `Retry-After`. Coste: 1 consultas ligeras, 2 listados y fichas guardadas, 3 predicciones, 5 estadísticas y resultados.
- **Errores:** `{"error": {"codigo", "mensaje", "solicitud"}}`; `solicitud` coincide con la
  cabecera `X-Request-ID`.

Uso **experimental_no_acreditado**: AE-39 sigue en NO-GO y `AUTORIZA_EVALUACION = False`. Las
predicciones no acreditan ventaja frente al azar.
"""


def _configurar_registro() -> None:
    """Bajo Uvicorn el registro raiz no tiene manejadores y las lineas INFO de
    monitoreo se perderian: se anade uno propio solo si no hay ninguno."""
    if registro.level == logging.NOTSET:
        registro.setLevel(logging.INFO)
    if not registro.handlers and not logging.getLogger().handlers:
        manejador = logging.StreamHandler()
        manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        registro.addHandler(manejador)


def crear_app(configuracion: ConfiguracionPublica | None = None) -> FastAPI:
    configuracion = validar(configuracion) if configuracion is not None else desde_settings(get_settings())
    _configurar_registro()
    documentacion = configuracion.documentacion
    app = FastAPI(title="Lotería Predictor — API pública", version="1.0.0", description=DESCRIPCION,
                  openapi_url="/api/v1/openapi.json" if documentacion else None,
                  docs_url="/api/v1/docs" if documentacion else None, redoc_url=None,
                  swagger_ui_oauth2_redirect_url=None, swagger_ui_parameters={"persistAuthorization": False})
    app.state.configuracion = configuracion
    app.state.limitador_por_clave = LimitadorDeCuota(configuracion.fichas_por_minuto,
                                                     max(1, len(configuracion.claves)))
    app.state.limitador_por_ip = LimitadorDeCuota(configuracion.fichas_por_minuto_ip, configuracion.max_clientes_ip)
    app.state.monitor = Monitor()
    app.state.costosas = LimiteDeCostosas(configuracion.concurrencia_costosas, configuracion.espera_costosas)
    registrar_manejadores(app)
    app.include_router(rutas.publico)
    app.include_router(rutas.router)
    app.add_middleware(MiddlewarePublico)
    if configuracion.cors_origenes:  # el ultimo anadido es el mas externo: responde antes el preflight
        app.add_middleware(CORSMiddleware, allow_origins=list(configuracion.cors_origenes), allow_methods=["GET"],
                           allow_headers=[ENCABEZADO], allow_credentials=False,
                           expose_headers=["Retry-After", "X-Request-ID", "X-RateLimit-Limit",
                                           "X-RateLimit-Remaining"])
    if configuracion.hosts or configuracion.clientes:  # perfil privado (E10.2): la capa mas externa
        app.add_middleware(FronteraPrivada, hosts=configuracion.hosts, clientes=configuracion.clientes)
    return app


app = crear_app()
