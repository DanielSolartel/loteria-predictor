"""Composición del visor local. El lanzador fija la base y las rutas antes de importarla."""
from __future__ import annotations

import re
import secrets
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Annotated, Callable, Literal

from fastapi import Depends, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.api import dependencies as dep
from app.api.publica import dependencias as lecturas
from app.api.publica.aplicacion import crear_app as crear_api
from app.api.publica.configuracion import ClaveConfigurada, ConfiguracionPublica
from app.api.publica.errores import ErrorPublico, respuesta_de_error
from app.api.publica.esquemas_guardados import ComparacionResultadosGuardados, ResumenResultadoGuardado
from app.api.publica.recursos import FronteraPrivada, costosa
from app.api.publica.rutas import CodigoJuego, _juego
from app.api.publica.seguridad import ENCABEZADO, acceso, generar_clave, huella
from app.application.use_cases.obtener_estado_importacion import ObtenerEstadoImportacion
from app.application.use_cases.obtener_sorteo_con_pareja import PAREJAS_DE_JUEGO
from app.application.use_cases.resultados import Filtros, ResultadosError
from app.control_piloto import ControlVisor
from app.escritorio_apuestas import RUTA_APUESTAS, rutas_apuestas
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
from app.pasarela.aplicacion import SEGURIDAD
from app.pasarela.rutas import buscar

_CONSULTAS = frozenset({"/api/v1/salud", "/api/v1/juegos", "/api/v1/juegos/{codigo}/predicciones",
                        "/api/v1/juegos/{codigo}/carteras-guardadas", "/api/v1/juegos/{codigo}/resultados"})
_SINCRONIZACION = "/api/v1/escritorio/sincronizacion"
_COMPARACION = "/api/v1/escritorio/juegos/{codigo}/comparacion"
_COMPARACION_RUTA = re.compile(r"/api/v1/escritorio/juegos/[A-Za-z_-]{1,32}/comparacion")
_SESION = "/escritorio/sesion"
_CIERRE = "/api/v1/escritorio/cerrar"
_DURACION_SESION = 8 * 60 * 60
_ESTADO = re.compile(r"[a-z_]{1,50}")
Linea = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,160}$")]
Fuente = Literal["sinteticos", "fase6"]


class Comparacion(BaseModel):
    juego: str
    comparacion: ComparacionResultadosGuardados
    resumenes: dict[str, ResumenResultadoGuardado]


class Sincronizacion(BaseModel):
    estado: str
    iniciado_en: datetime
    finalizado_en: datetime | None
    sorteos_nuevos: int


class EstadoJuego(BaseModel):
    juego: str
    ultimo_sorteo: int | None
    total_sorteos: int
    estado_fase6: str
    ultima_comprobacion: datetime | None
    sincronizacion: Sincronizacion | None


class EstadoReferencia(BaseModel):
    datos: Fuente
    fecha_referencia: datetime | None
    juegos: list[EstadoJuego]


def _estado_guardado(almacen: AlmacenAutomatizacion, codigo: str) -> tuple[str, datetime | None]:
    try:
        registro = almacen.estado(codigo)
        estado, fecha = registro.get("estado"), registro.get("ultima_comprobacion")
        if not isinstance(estado, str) or not _ESTADO.fullmatch(estado):
            return "no_disponible", None
        return estado, datetime.fromisoformat(fecha) if isinstance(fecha, str) else None
    except (OSError, ValueError):
        return "no_disponible", None


def _coincide(recibida: str, esperada: str) -> bool:
    return len(recibida) == len(esperada) and secrets.compare_digest(recibida.encode(), esperada.encode())


def crear_app(*, frontend: Path, automatizacion: Path, fecha_referencia: datetime | None, puerto: int, arranque: str,
              control: ControlVisor | None = None, cerrar: Callable[[], None] | None = None,
              datos: Fuente = "sinteticos", apuestas: Path | None = None):
    """Una sola API y sus estáticos. El navegador solo recibe una sesión del visor."""
    host = f"127.0.0.1:{puerto}"
    origen = f"http://{host}"
    clave_api = generar_clave()
    cookie = f"lp_escritorio_{puerto}"
    control = control or ControlVisor()
    sesion = secrets.token_urlsafe(32)
    vence_arranque, vence_sesion = monotonic() + 300, 0.0
    aplicacion = crear_api(ConfiguracionPublica(
        claves=(ClaveConfigurada("escritorio", bytes.fromhex(huella(clave_api))),),
        fichas_por_minuto=180, fichas_por_minuto_ip=180, documentacion=False, concurrencia_costosas=2,
    ))
    aplicacion.title = "Lotería Predictor — piloto de escritorio"
    aplicacion.router.redirect_slashes = False
    almacen = AlmacenAutomatizacion(automatizacion)
    rutas_locales = {_SINCRONIZACION: ("GET",), _CIERRE: ("POST",)}
    if apuestas is not None:
        aplicacion.include_router(rutas_apuestas(apuestas, origen))
        rutas_locales[RUTA_APUESTAS] = ("GET", "POST")

    def centro_de_predicciones():
        return dep.get_predicciones(dep.construir_carteras(consultar_actividad=False))

    aplicacion.dependency_overrides[lecturas.centro_de_predicciones] = centro_de_predicciones

    @aplicacion.post(_SESION, status_code=204)
    async def iniciar_sesion(request: Request) -> Response:
        nonlocal vence_sesion
        if (request.headers.getlist("origin") != [origen] or monotonic() >= vence_arranque or control.sesion
                or not _coincide(request.headers.get("x-arranque-escritorio", ""), arranque)):
            raise ErrorPublico(403, "arranque_no_valido", "Abre el piloto desde su lanzador.")
        vence_sesion = monotonic() + _DURACION_SESION
        control.sesion = True
        respuesta = Response(status_code=204)
        respuesta.set_cookie(cookie, sesion, max_age=_DURACION_SESION, path="/api/v1", httponly=True,
                              samesite="strict")
        return respuesta

    @aplicacion.get("/escritorio/instancia")
    def instancia():
        return {"instancia": control.identificador}

    @aplicacion.get("/escritorio/origen")
    def origen_de_datos():
        return {"datos": datos, "apuestas": None if apuestas is None else {"parejas": PAREJAS_DE_JUEGO}}

    @aplicacion.post(_CIERRE, status_code=204)
    async def cerrar_piloto(request: Request) -> Response:
        nonlocal vence_sesion
        if request.headers.getlist("origin") != [origen]:
            raise ErrorPublico(403, "origen_no_permitido", "Abre el piloto desde su lanzador.")
        vence_sesion = 0
        control.cierre_solicitado = True
        respuesta = Response(status_code=204, background=BackgroundTask(cerrar) if cerrar else None)
        respuesta.delete_cookie(cookie, path="/api/v1", httponly=True, samesite="strict")
        return respuesta

    @aplicacion.get(_SINCRONIZACION, response_model=EstadoReferencia)
    def sincronizacion(_: str = Depends(acceso(2)), db: Session = Depends(lecturas.sesion_de_lectura)):
        servicio = ObtenerEstadoImportacion(dep.get_juego_repository(db), dep.get_sorteo_repository(db),
                                           dep.get_sincronizacion_repository(db))
        juegos = []
        for fila in servicio.ejecutar(verificar_salud=False):
            codigo = fila.juego.codigo
            estado, fecha = _estado_guardado(almacen, codigo)
            intento = fila.ultima_ejecucion
            juegos.append(EstadoJuego(
                juego=codigo, ultimo_sorteo=fila.ultimo_sorteo_almacenado, total_sorteos=fila.total_sorteos_almacenados,
                estado_fase6=estado, ultima_comprobacion=fecha,
                sincronizacion=None if intento is None else Sincronizacion(
                    estado=intento.estado, iniciado_en=intento.iniciado_en, finalizado_en=intento.finalizado_en,
                    sorteos_nuevos=intento.sorteos_nuevos),
            ))
        return EstadoReferencia(datos=datos, fecha_referencia=fecha_referencia, juegos=juegos)

    @aplicacion.get(_COMPARACION, response_model=Comparacion)
    @costosa
    def comparar(codigo: str = CodigoJuego, linea: list[Linea] = Query(min_length=2, max_length=8),
                 tipo: Literal["seguimiento", "retrospectiva"] = "seguimiento",
                 desde: int | None = Query(None, ge=1), hasta: int | None = Query(None, ge=1),
                 _: str = Depends(acceso(5))):
        if len(set(linea)) != len(linea):
            raise ErrorPublico(422, "parametro_no_valido", "Elige líneas distintas para comparar.")
        juego = _juego(codigo)
        try:
            resultado = dep.get_resultados(dep.get_carteras()).consultar(
                juego, Filtros(lineas=tuple(linea), tipo=tipo, desde=desde, hasta=hasta), por_pagina=1,
            )
        except ResultadosError as error:
            raise ErrorPublico(422, "parametro_no_valido", "Revisa las líneas y el intervalo de sorteos.") from error
        return {"juego": juego, "comparacion": resultado["comparacion"],
                "resumenes": {clave: resultado["resumenes"][clave] for clave in linea}}

    @aplicacion.get("/")
    def interfaz():
        return FileResponse(frontend / "index.html", media_type="text/html")

    @aplicacion.get("/favicon.svg")
    def icono():
        return FileResponse(frontend / "favicon.svg", media_type="image/svg+xml")

    aplicacion.mount("/assets", StaticFiles(directory=frontend / "assets"))

    @aplicacion.middleware("http")
    async def limitar(request: Request, siguiente):
        ruta = request.url.path
        origenes = request.headers.getlist("origin")
        sitio = request.headers.get("sec-fetch-site", "none")
        if (origenes not in ([], [origen]) or sitio not in ("same-origin", "none")
                or any(k in request.headers for k in ("forwarded", "x-forwarded-for", "x-forwarded-host",
                                                      "x-forwarded-proto"))):
            return respuesta_de_error(request, 403, "origen_no_permitido", "Origen no admitido.", headers=SEGURIDAD)
        if ruta.startswith("/api/"):
            metodos = rutas_locales.get(ruta)
            if metodos is None:
                publica = buscar(ruta)
                if not (publica is not None and publica.plantilla in _CONSULTAS or _COMPARACION_RUTA.fullmatch(ruta)):
                    return respuesta_de_error(request, 404, "no_encontrado", "Consulta no disponible.", headers=SEGURIDAD)
                metodos = ("GET",)
            if request.method not in metodos:
                return respuesta_de_error(request, 405, "metodo_no_permitido", "Método no admitido.",
                                          headers={**SEGURIDAD, "Allow": ", ".join(metodos)})
            if ruta != "/api/v1/salud":
                if monotonic() >= vence_sesion or not _coincide(request.cookies.get(cookie, ""), sesion):
                    return respuesta_de_error(request, 401, "sesion_requerida", "Abre el piloto desde su lanzador.",
                                              headers=SEGURIDAD)
                request.scope["headers"] = [(k, v) for k, v in request.scope["headers"] if k != ENCABEZADO.lower().encode()]
                request.scope["headers"].append((ENCABEZADO.lower().encode(), clave_api.encode()))
        respuesta = await siguiente(request)
        if respuesta.status_code == 200 and ruta.startswith("/api/v1/") and ruta != "/api/v1/salud":
            control.consultas.add(ruta)
            if (ruta.startswith("/api/v1/juegos/") and ruta.endswith("/predicciones")
                    and request.query_params.get("cartera")):
                control.juegos_con_cartera_consultada.add(ruta.split("/")[-2])
        respuesta.headers.update(SEGURIDAD)
        return respuesta

    aplicacion.add_middleware(FronteraPrivada, hosts=frozenset({host}), clientes=frozenset({"127.0.0.1"}))
    return aplicacion
