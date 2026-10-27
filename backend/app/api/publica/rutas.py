"""
Endpoints de la API publica v1. Todos son GET y de solo lectura; cada uno
reutiliza un caso de uso existente y proyecta un contrato publico propio.

Coste en fichas de la cuota por clave: 1 consultas ligeras, 2 listados,
3 predicciones y su fiabilidad (almacenes y base), 5 estadisticas (recorren el
historico).
`/salud` es la unica ruta sin clave (ademas de la documentacion).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request

from app.api.publica import dependencias as d
from app.api.publica import esquemas as e
from app.api.publica.errores import ErrorPublico
from app.api.publica.seguridad import acceso
from app.application.estadisticas.descriptivas import VENTANAS
from app.application.use_cases import metricas_anteriores
from app.application.use_cases.consultar_estadisticas_descriptivas import ConsultarEstadisticasDescriptivas
from app.application.use_cases.consultar_juegos import ListarJuegos, ObtenerJuego
from app.application.use_cases.consultar_resumen_juego import SLUG_A_CODIGO_RESUMEN, ConsultarResumenJuego
from app.application.use_cases.listar_sorteos import ListarSorteos, ListarSorteosInput
from app.application.use_cases.predicciones import CentroDePredicciones, PrediccionesError
from app.application.use_cases.simulaciones import SimulacionesError, SimulacionesFase7

JUEGOS = tuple(SLUG_A_CODIGO_RESUMEN.values())
MAXIMO_POR_PAGINA = 100
MAXIMO_PAGINA = 10_000
MAXIMO_HISTORIAL = 50
MAXIMO_SIMULACIONES = 50
LIGERA, LISTADO, PREDICCIONES, ESTADISTICAS = 1, 2, 3, 5
_ORDEN = {"fecha_desc": ("fecha", "desc"), "fecha_asc": ("fecha", "asc"),
          "numero_desc": ("numero_sorteo", "desc"), "numero_asc": ("numero_sorteo", "asc")}
_HTTP_DE_CASO = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409,
                 "incompatible": 409, "sin_configuracion": 409, "base_no_disponible": 503}


def _errores(*estados: int) -> dict:
    textos = {401: "Clave ausente o no válida", 404: "Juego o recurso inexistente",
              409: "Recurso guardado no íntegro o histórico no válido",
              422: "Parámetro no válido", 503: "API sin claves configuradas o base no disponible",
              429: "Límite de uso excedido (cabecera Retry-After)"}
    return {s: {"model": e.ErrorRespuesta, "description": textos[s]} for s in (401, 429, 503, *estados)}


router = APIRouter(prefix="/api/v1")
publico = APIRouter(prefix="/api/v1")

CodigoJuego = Path(description=f"Código del juego: {', '.join(JUEGOS)}", examples=["BALOTO"])


def _juego(codigo: str) -> str:
    if codigo not in JUEGOS:
        raise ErrorPublico(404, "no_encontrado", f"Juego no admitido; admitidos: {', '.join(JUEGOS)}")
    return codigo


def _de_caso(error: PrediccionesError | SimulacionesError) -> ErrorPublico:
    estado = _HTTP_DE_CASO.get(error.codigo)
    if estado is None:  # codigo no previsto en una lectura: sin su mensaje interno
        return ErrorPublico(500, "error_interno", "Error interno al leer los datos")
    mensaje = "Base de datos no disponible" if estado == 503 else str(error)
    return ErrorPublico(estado, error.codigo, mensaje)


# ---------------------------------------------------------------------------
# Salud y estado
# ---------------------------------------------------------------------------

@publico.get("/salud", response_model=e.Salud, tags=["sistema"], summary="Salud del proceso (sin clave)")
def salud() -> e.Salud:
    return e.Salud(estado="ok", api="v1")


@router.get("/estado", response_model=e.EstadoDelServicio, tags=["sistema"], responses=_errores(),
            summary="Monitoreo de este proceso: solicitudes, latencia, límites y base")
def estado(request: Request, _: str = Depends(acceso(LIGERA)), base: str = Depends(d.estado_de_la_base)):
    s = request.app.state
    return {"api": "v1", "base": base, "claves_configuradas": len(s.configuracion.claves), **s.monitor.resumen(),
            "limites": {"alcance": "por_proceso", "fichas_por_minuto_por_clave": s.limitador_por_clave.capacidad,
                        "fichas_por_minuto_por_ip": s.limitador_por_ip.capacidad,
                        "costes": {"ligera": LIGERA, "listado": LISTADO, "predicciones": PREDICCIONES,
                                   "estadisticas": ESTADISTICAS},
                        "rechazos_por_clave": s.limitador_por_clave.rechazos,
                        "rechazos_por_ip": s.limitador_por_ip.rechazos,
                        "ips_seguidas": s.limitador_por_ip.identidades,
                        "max_ips_seguidas": s.configuracion.max_clientes_ip}}


# ---------------------------------------------------------------------------
# Juegos y sorteos
# ---------------------------------------------------------------------------

def _juego_publico(j) -> dict:
    return {k: getattr(j, k) for k in e.Juego.model_fields}


@router.get("/juegos", response_model=e.Juegos, tags=["juegos"], responses=_errores(503),
            summary="Los cuatro juegos y sus reglas")
def juegos(_: str = Depends(acceso(LIGERA)), listar: ListarJuegos = Depends(d.listar_juegos)):
    por_codigo = {j.codigo: j for j in listar.ejecutar()}
    return {"juegos": [_juego_publico(por_codigo[c]) for c in JUEGOS if c in por_codigo]}


@router.get("/juegos/{codigo}", response_model=e.JuegoDetalle, tags=["juegos"], responses=_errores(404, 503),
            summary="Un juego con su espacio muestral")
def juego(codigo: str = CodigoJuego, _: str = Depends(acceso(LIGERA)),
          obtener: ObtenerJuego = Depends(d.obtener_juego)):
    datos = obtener.ejecutar(_juego(codigo))
    return {**_juego_publico(datos.juego), "espacio_muestral": datos.espacio_muestral,
            "dimensiones": datos.dimensiones}


def _sorteo_publico(s) -> dict:
    return {"numero_sorteo": s.numero_sorteo, "fecha": s.fecha, "dia_semana": s.dia_semana,
            "numeros": list(s.resultado.numeros), "superbalota": s.resultado.superbalota,
            "pares": [{"numero": p.numero, "color_codigo": p.color.codigo, "color_nombre": p.color.nombre}
                      for p in s.resultado.pares]}


@router.get("/juegos/{codigo}/sorteos", response_model=e.PaginaDeSorteos, tags=["sorteos"],
            responses=_errores(404, 422, 503), summary="Sorteos paginados (máximo 100 por página)")
def sorteos(codigo: str = CodigoJuego, pagina: int = Query(1, ge=1, le=MAXIMO_PAGINA),
            por_pagina: int = Query(20, ge=1, le=MAXIMO_POR_PAGINA), desde: date | None = None,
            hasta: date | None = None, numero_desde: int | None = Query(None, ge=1),
            numero_hasta: int | None = Query(None, ge=1),
            orden: Literal["fecha_desc", "fecha_asc", "numero_desc", "numero_asc"] = "fecha_desc",
            _: str = Depends(acceso(LISTADO)), listar: ListarSorteos = Depends(d.listar_sorteos)):
    _juego(codigo)
    if (desde and hasta and desde > hasta) or (numero_desde and numero_hasta and numero_desde > numero_hasta):
        raise ErrorPublico(422, "parametro_no_valido", "El inicio del intervalo no puede ser posterior al final")
    campo, direccion = _ORDEN[orden]
    r = listar.ejecutar(ListarSorteosInput(codigo_juego=codigo, desde=desde, hasta=hasta, numero_desde=numero_desde,
                                           numero_hasta=numero_hasta, orden_campo=campo, orden_direccion=direccion,
                                           limite=por_pagina, offset=(pagina - 1) * por_pagina))
    return {"juego": codigo, "pagina": pagina, "por_pagina": por_pagina, "total": r.total,
            "paginas": math.ceil(r.total / por_pagina), "sorteos": [_sorteo_publico(s) for s in r.sorteos]}


@router.get("/juegos/{codigo}/sorteos/{numero_sorteo}", response_model=e.Sorteo, tags=["sorteos"],
            responses=_errores(404, 422, 503), summary="Un sorteo por su número")
def sorteo(codigo: str = CodigoJuego, numero_sorteo: int = Path(ge=1), _: str = Depends(acceso(LIGERA)),
           listar: ListarSorteos = Depends(d.listar_sorteos)):
    r = listar.ejecutar(ListarSorteosInput(codigo_juego=_juego(codigo), numero_desde=numero_sorteo,
                                           numero_hasta=numero_sorteo, limite=1))
    if not r.sorteos:
        raise ErrorPublico(404, "no_encontrado", "Sorteo no encontrado")
    return _sorteo_publico(r.sorteos[0])


# ---------------------------------------------------------------------------
# Estadisticas (Productos 1 y Fase 5)
# ---------------------------------------------------------------------------

@router.get("/juegos/{codigo}/estadisticas", response_model=e.IndiceDeEstadisticas, tags=["estadisticas"],
            responses=_errores(404, 503), summary="Métricas descriptivas disponibles para el juego")
def indice_de_estadisticas(codigo: str = CodigoJuego, _: str = Depends(acceso(LIGERA)),
                           consultar: ConsultarEstadisticasDescriptivas = Depends(d.consultar_estadisticas)):
    reglas = consultar.reglas(_juego(codigo))
    base = f"/api/v1/juegos/{codigo}/estadisticas"
    return {"juego": codigo, "resumen": f"{base}/resumen", "panel": f"{base}/panel",
            "metricas": metricas_anteriores.paginas(reglas)}


@router.get("/juegos/{codigo}/estadisticas/resumen", response_model=e.Resumen, tags=["estadisticas"],
            responses=_errores(404, 409, 422, 503), summary="Resumen del juego hasta un corte opcional")
def resumen(codigo: str = CodigoJuego, hasta_numero_sorteo: int | None = Query(None, ge=1),
            _: str = Depends(acceso(ESTADISTICAS)), consultar: ConsultarResumenJuego = Depends(d.consultar_resumen)):
    return consultar.ejecutar(_juego(codigo), hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo)


@router.get("/juegos/{codigo}/estadisticas/panel", response_model=e.Estadisticas, tags=["estadisticas"],
            responses=_errores(404, 409, 422, 503), summary="Panel descriptivo unificado (Fase 5)")
def panel(codigo: str = CodigoJuego, hasta_numero_sorteo: int | None = Query(None, ge=1),
          _: str = Depends(acceso(ESTADISTICAS)),
          consultar: ConsultarEstadisticasDescriptivas = Depends(d.consultar_estadisticas)):
    return consultar.panel(_juego(codigo), hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo)


@router.get("/juegos/{codigo}/estadisticas/{metrica}", response_model=e.RespuestaDeMetrica, tags=["estadisticas"],
            responses=_errores(404, 409, 422, 503),
            summary="Una métrica descriptiva: de la Fase 5 o anterior (receta de la consola)")
def metrica(codigo: str = CodigoJuego, metrica: str = Path(examples=["frecuencia-colores"]),
            hasta_numero_sorteo: int | None = Query(None, ge=1), anio: int | None = Query(None, ge=1, le=9999),
            mes: int | None = Query(None, ge=1, le=12),
            dia_semana: Literal["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"] | None = None,
            ventana: int | None = Query(None),
            color: str | None = Query(None, pattern="^[A-Z][A-Z_]{0,31}$",
                                      description="Código exacto de un color (distribucion-conteo-color de ColorLoto)"),
            pagina: int | None = Query(None, ge=1, le=MAXIMO_PAGINA,
                                       description="Página de una tabla paginada (100 filas); solo si el índice la declara"),
            _: str = Depends(acceso(ESTADISTICAS)),
            consultar: ConsultarEstadisticasDescriptivas = Depends(d.consultar_estadisticas)):
    _juego(codigo)
    disponible = next((m for m in metricas_anteriores.paginas(consultar.reglas(codigo)) if m["metrica"] == metrica), None)
    if disponible is None:
        raise ErrorPublico(404, "no_encontrado", "Métrica no disponible para este juego")
    recibidos = {"anio": anio, "mes": mes, "dia_semana": dia_semana, "ventana": ventana, "color": color}
    ajenos = sorted(k for k, v in recibidos.items() if v is not None and k != disponible["parametro"])
    if pagina is not None and not disponible["paginada"]:
        ajenos.append("pagina")
    if ajenos:
        raise ErrorPublico(422, "parametro_no_valido",
                           f"Parámetros no admitidos por esta métrica: {', '.join(ajenos)}")
    if disponible["parametro"] == "ventana" and ventana is not None and ventana not in VENTANAS:
        raise ErrorPublico(422, "parametro_no_valido", f"ventana debe ser una de {list(VENTANAS)}")
    parametros = {disponible["parametro"]: recibidos[disponible["parametro"]]} if disponible["parametro"] else {}
    try:
        return consultar.metrica(codigo, metrica, hoy=date.today(), hasta_numero_sorteo=hasta_numero_sorteo,
                                 parametros=parametros, pagina=pagina)
    except metricas_anteriores.ParametroNoValido as error:
        raise ErrorPublico(422, "parametro_no_valido", str(error)) from error


# ---------------------------------------------------------------------------
# Predicciones guardadas (Fase 4)
# ---------------------------------------------------------------------------

def _explicacion_publica(x: dict | None) -> dict | None:
    """Explicacion guardada sin sus campos internos (sello, rankings repetidos, contexto);
    los objetos anidados los acota su modelo publico."""
    return None if x is None else {k: x.get(k) for k in e.Explicacion.model_fields}


def _prediccion_publica(p: dict) -> dict:
    generacion, modelo, datos = p.get("generacion") or {}, p.get("modelo") or {}, p.get("datos") or {}
    registrado = (p.get("linea_del_artefacto") or {}).get("registrado")
    return {"clave": p["clave"], "integridad": p["integridad"], "linea": p["linea"], "objetivo": p["objetivo"],
            "corte": datos.get("corte"), "sha256_historico": datos.get("sha256_historico"),
            "generado_en": generacion.get("generado_en"),
            "clasificacion_temporal": generacion.get("clasificacion_temporal"),
            "modelo": {k: modelo.get(k) for k in e.ModeloDeLaPrediccion.model_fields},
            "combinaciones": p.get("combinaciones") or [], "rankings": p.get("rankings"),
            "observado": p.get("observado"), "frente_a_la_base": p.get("frente_a_la_base"),
            "explicacion_disponible": p.get("explicacion") is not None,
            "linea_de_modelo": p.get("linea_de_modelo"),
            "registrado": None if not registrado else {"clave": registrado["clave"], "numero": registrado["numero"]},
            "explicacion": _explicacion_publica(p.get("explicacion")),
            "explicaciones_ilegibles": [{"clave": x["clave"], "motivo": x["motivo"]}
                                        for x in p.get("explicaciones_ilegibles") or []],
            "reproduccion": p.get("reproduccion")}


@router.get("/juegos/{codigo}/predicciones", response_model=e.Predicciones, tags=["predicciones"],
            responses=_errores(404, 409, 422, 503),
            summary="Predicción guardada (la última o la indicada) e historial acotado")
def predicciones(codigo: str = CodigoJuego,
                 cartera: str | None = Query(None, pattern="^[0-9a-f]{64}$",
                                             description="Clave de una predicción guardada"),
                 historial: int = Query(20, ge=0, le=MAXIMO_HISTORIAL), _: str = Depends(acceso(PREDICCIONES)),
                 centro: CentroDePredicciones = Depends(d.centro_de_predicciones)):
    try:
        r = centro.consultar(_juego(codigo), cartera)
    except PrediccionesError as error:
        raise _de_caso(error) from error
    base = r.get("base") or {}
    base = {**{k: base.get(k) for k in e.BaseDelJuego.model_fields}, "estado": base.get("estado") or "desconocido"}
    guardadas = [{k: h.get(k) for k in e.PrediccionGuardada.model_fields} for h in r.get("historial") or []]
    return {"juego": r["juego"], "nombre": r["nombre"], "estado_de_uso": r["estado_de_uso"], "aviso": r["aviso"],
            "contexto": r["contexto"], "configuracion": (r.get("configuracion") or {}).get("estado") or "desconocido",
            "base": base,
            "prediccion": None if r.get("prediccion") is None else _prediccion_publica(r["prediccion"]),
            "historial": guardadas[:historial], "historial_total": len(guardadas)}


# ---------------------------------------------------------------------------
# Fiabilidad observada de las predicciones (Fase 4)
# ---------------------------------------------------------------------------

_FALLO_DE_CALCULO = "no se pudieron calcular las cifras; el detalle queda en la consola local"


def _motivo_publico(x: dict) -> str | None:
    return _FALLO_DE_CALCULO if x.get("estado") == "fallo_de_calculo" else x.get("motivo")


def _metrica_de_fiabilidad(m: dict) -> dict:
    return {**{k: m.get(k) for k in e.MetricaDeFiabilidad.model_fields}, "motivo": _motivo_publico(m),
            "semilla": None if m.get("semilla") is None else str(m["semilla"])}


def _componente_de_fiabilidad(c: dict) -> dict:
    metricas = c.get("metricas")
    return {**{k: c.get(k) for k in e.ComponenteDeFiabilidad.model_fields}, "motivo": _motivo_publico(c),
            "metricas": None if metricas is None else {n: _metrica_de_fiabilidad(m) for n, m in metricas.items()}}


def _evaluacion_de_fiabilidad(ev: dict) -> dict:
    muestra = ev.get("muestra")
    return {**{k: ev.get(k) for k in e.EvaluacionDeFiabilidad.model_fields}, "motivo": _motivo_publico(ev),
            "muestra": None if muestra is None else {**{k: muestra.get(k) for k in e.MuestraDeFiabilidad.model_fields},
                                                      "exclusiones": muestra.get("exclusiones") or []},
            "componentes": {n: _componente_de_fiabilidad(c) for n, c in (ev.get("componentes") or {}).items()}}


@router.get("/juegos/{codigo}/fiabilidad", response_model=e.Fiabilidad, tags=["predicciones"],
            responses=_errores(404, 422, 503),
            summary="Fiabilidad observada: seguimiento, retrospectiva y evaluación de la receta, por separado")
def fiabilidad(codigo: str = CodigoJuego,
               hasta: int | None = Query(None, ge=1, description="Solo objetivos hasta este sorteo; no acredita que "
                                                                 "el informe o la emisión existieran al generar una cartera"),
               _: str = Depends(acceso(PREDICCIONES)),
               centro: CentroDePredicciones = Depends(d.centro_de_predicciones)):
    try:
        f = centro.fiabilidad(_juego(codigo), hasta=hasta)
    except PrediccionesError as error:
        raise _de_caso(error) from error
    registrado, base = f.get("registrado"), f.get("base") or {}
    return {"juego": f["juego"], "nombre": f["nombre"], "estado_de_uso": e.ESTADO_DE_USO, "aviso": f["aviso"],
            "contexto": f["contexto"], "configuracion": (f.get("configuracion") or {}).get("estado") or "desconocido",
            "registrado": None if not registrado else {
                k: registrado.get(k) for k in e.VersionRegistradaDeLaConfiguracion.model_fields},
            "base": {**{k: base.get(k) for k in e.BaseDeFiabilidad.model_fields},
                     "estado": base.get("estado") or "desconocido"},
            "hasta": f["hasta"], "metodo": f["metodo"],
            "lineas": [{**{k: linea.get(k) for k in ("linea", "papel", "nombre", "estimador")},
                        "evaluaciones": [_evaluacion_de_fiabilidad(ev) for ev in linea.get("evaluaciones") or []]}
                       for linea in f.get("lineas") or []],
            "receta": _evaluacion_de_fiabilidad(f["receta"])}


# ---------------------------------------------------------------------------
# Simulaciones guardadas (Fase 7)
# ---------------------------------------------------------------------------

@router.get("/juegos/{codigo}/simulaciones", response_model=e.Simulaciones, tags=["simulaciones"],
            responses=_errores(404, 422, 503), summary="Simulaciones guardadas del juego (máximo 50)")
def simulaciones(codigo: str = CodigoJuego, limite: int = Query(20, ge=1, le=MAXIMO_SIMULACIONES),
                 _: str = Depends(acceso(LISTADO)), servicio: SimulacionesFase7 = Depends(d.simulaciones)):
    try:
        filas = servicio.listar(_juego(codigo), limite)
    except SimulacionesError as error:
        raise _de_caso(error) from error
    return {"juego": codigo, "limite": limite, "estado_de_uso": e.ESTADO_DE_USO,
            "simulaciones": [{k: f.get(k) for k in e.SimulacionResumen.model_fields} for f in filas]}


@router.get("/simulaciones/{identificador}", response_model=e.Simulacion, tags=["simulaciones"],
            responses=_errores(404, 409, 422, 503), summary="Una simulación guardada, verificada")
def simulacion(identificador: str = Path(pattern="^[0-9a-fA-F-]{32,36}$", description="UUID de la fila"),
               _: str = Depends(acceso(LISTADO)), servicio: SimulacionesFase7 = Depends(d.simulaciones)):
    try:
        f = servicio.obtener(identificador)
    except SimulacionesError as error:
        raise _de_caso(error) from error
    resumen_ = f["resultado_resumen"]
    return {"id": f["id"], "juego": f["juego"], "num_iteraciones": f["num_iteraciones"],
            "ejecutado_en": f["ejecutado_en"], "duracion_ms": f["duracion_ms"], "integridad": f["integridad"],
            "estado_de_uso": e.ESTADO_DE_USO, "parametros": f["parametros"], "contenido": resumen_["contenido"],
            "contenido_sha256": resumen_["contenido_sha256"]}
