"""
API REST de Producto 5 (JSON, solo lectura): catalogo, diagnostico y
configuracion por juego, ejecuciones, comparaciones del modelo combinado,
carteras, simulaciones y seguimiento. Las cifras e identidades son las mismas
que muestran la web y el comando (salen de los mismos artefactos guardados).
Comparar, generar, simular y configurar no se exponen aqui: se hacen desde la
web (POST protegido) o con `python -m scripts.carteras_modelos`.

404: juego, ejecucion, artefacto o linea inexistentes; 409: archivo alterado;
422: parametro no valido.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.api.dependencies import get_carteras
from app.application.interfaces.carteras_store import GuardadoCarteras
from app.application.ml import carteras_artefactos as ca
from app.application.use_cases.carteras import JUEGOS, CarterasDeModelos, CarterasError

router = APIRouter(prefix="/api/carteras")
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409}


def _http(error: CarterasError) -> HTTPException:
    return HTTPException(status_code=_CODIGO_HTTP.get(error.codigo, 400), detail={"codigo": error.codigo,
                                                                               "mensaje": str(error)})


def _juego(codigo: str) -> str:
    if codigo not in JUEGOS:
        raise HTTPException(status_code=404, detail={"codigo": "no_encontrado", "mensaje": f"Juego no admitido: {codigo}"})
    return codigo


def _elemento(e) -> dict:
    if not isinstance(e, GuardadoCarteras):
        return {"clave": e.identificador, "estado": "ilegible", "motivo": e.motivo}
    return {"clave": e.identificador, "objetivo": e.objetivo, "version": e.version, "versiones": e.versiones,
            "generado_en": e.artefacto.get("generacion", {}).get("generado_en")}


@router.get("/catalogo")
def catalogo(servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    return servicio.catalogo()


@router.get("/ejecuciones")
def ejecuciones(limite: int = Query(default=20, ge=1, le=200), servicio: CarterasDeModelos = Depends(get_carteras)):
    return {"ejecuciones": servicio.recientes(limite)}


@router.get("/ejecuciones/{identificador}")
def ejecucion(identificador: str, servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    encontrada = servicio.consultar_ejecucion(identificador)
    if encontrada is None:
        raise HTTPException(status_code=404, detail={"codigo": "no_encontrado", "mensaje": "Ejecucion no encontrada"})
    return encontrada


@router.get("/comparaciones/{clave}")
def comparacion(clave: str, servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    try:
        informe = servicio.comparacion(clave).artefacto
    except CarterasError as error:
        raise _http(error) from error
    return {"comparacion": informe, "base_actual": servicio.estado_frente_a_la_base(informe)}


@router.get("/guardadas/{clave}")
def cartera(clave: str, servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    try:
        guardado = servicio.cartera(clave)
    except CarterasError as error:
        raise _http(error) from error
    return {"cartera": guardado.artefacto, "version": guardado.version, "versiones": guardado.versiones,
            "resultado_observado": servicio.observado_de_cartera(guardado.artefacto),
            "simulaciones": [s.identificador for s in servicio.simulaciones_de_cartera(clave)]}


@router.get("/guardadas/{clave}/csv", response_class=PlainTextResponse)
def cartera_csv(clave: str, servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        return PlainTextResponse(servicio.exportar_csv(clave), media_type="text/csv; charset=utf-8")
    except CarterasError as error:
        raise _http(error) from error


@router.get("/simulaciones/{clave}")
def simulacion(clave: str, servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    try:
        return {"simulacion": servicio.simulacion(clave).artefacto}
    except CarterasError as error:
        raise _http(error) from error


@router.get("/simulaciones/{clave}/csv", response_class=PlainTextResponse)
def simulacion_csv(clave: str, servicio: CarterasDeModelos = Depends(get_carteras)):
    try:
        return PlainTextResponse(ca.csv_de_simulacion(servicio.simulacion(clave).artefacto),
                                 media_type="text/csv; charset=utf-8")
    except CarterasError as error:
        raise _http(error) from error


@router.get("/{codigo}/comparaciones")
def comparaciones(codigo: str, servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    return {"juego": codigo, "comparaciones": servicio.diagnostico(_juego(codigo))["comparaciones"]}


@router.get("/{codigo}/lineas")
def lineas(codigo: str, servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    _juego(codigo)
    return {"juego": codigo, "lineas": {nombre: [_elemento(e) for e in servicio.carteras_de_linea(codigo, nombre)]
                                        for nombre in servicio.lineas(codigo)}}


@router.get("/{codigo}/configuracion")
def configuracion(codigo: str, servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    _juego(codigo)
    try:
        vigente = servicio.configuracion_vigente(codigo)
    except CarterasError as error:
        raise _http(error) from error
    return {"juego": codigo, "vigente": vigente.artefacto if vigente else None,
            "versiones": [e.artefacto if isinstance(e, GuardadoCarteras) else
                          {"version": e.identificador, "estado": "ilegible", "motivo": e.motivo}
                          for e in servicio.configuraciones(codigo)]}


@router.get("/{codigo}/seguimiento")
def seguimiento(codigo: str, linea: str | None = Query(default=None), tipo: str = Query(default="seguimiento"),
                servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    try:
        return servicio.seguimiento(_juego(codigo), linea, tipo)
    except CarterasError as error:
        raise _http(error) from error


@router.get("/{codigo}")
def diagnostico(codigo: str, servicio: CarterasDeModelos = Depends(get_carteras)) -> dict:
    return servicio.diagnostico(_juego(codigo))
