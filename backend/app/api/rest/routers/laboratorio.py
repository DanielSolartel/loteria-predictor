"""
API REST de Producto 4 (JSON, solo lectura): catalogo, diagnostico por
juego, ejecuciones, experimentos, pronosticos y seguimiento del
laboratorio. Las cifras e identidades son las mismas que muestran la web y
el comando (salen de los mismos informes guardados). Comparar y generar no
se exponen aqui: se hacen desde la web (POST protegido) o con
`python -m scripts.laboratorio_modelos`.

Fase 3: `GET /modelos[?juego=]` (versiones registradas, compatibilidad e
incidencias) y `GET /modelos/{clave}` (ficha: manifiesto, compatibilidad,
proyeccion a las tablas de la Fase 1 y pronosticos de su linea). Ninguno
deserializa el estimador; entrenar, verificar y generar con un modelo
registrado se hacen desde la web (POST protegido) o el comando.

404: juego, ejecucion, experimento, pronostico o linea inexistentes;
409: archivo alterado; 422: parametro no valido.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_laboratorio
from app.application.use_cases.laboratorio import JUEGOS, LaboratorioDeModelos, LaboratorioError

router = APIRouter(prefix="/api/laboratorio")
_CODIGO_HTTP = {"no_encontrado": 404, "no_valido": 422, "alterado": 409, "no_disponible": 409, "incompatible": 409}


def _http(error: LaboratorioError) -> HTTPException:
    return HTTPException(status_code=_CODIGO_HTTP.get(error.codigo, 400), detail={"codigo": error.codigo,
                                                                               "mensaje": str(error)})


@router.get("/catalogo")
def catalogo(lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    return lab.catalogo()


@router.get("/ejecuciones")
def ejecuciones(limite: int = Query(default=20, ge=1, le=200), lab: LaboratorioDeModelos = Depends(get_laboratorio)):
    return {"ejecuciones": lab.recientes(limite)}


@router.get("/ejecuciones/{identificador}")
def ejecucion(identificador: str, lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    encontrada = lab.consultar_ejecucion(identificador)
    if encontrada is None:
        raise HTTPException(status_code=404, detail={"codigo": "no_encontrado", "mensaje": "Ejecucion no encontrada"})
    return encontrada


@router.get("/experimentos/{clave}")
def experimento(clave: str, lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    try:
        informe = lab.experimento(clave).artefacto
    except LaboratorioError as error:
        raise _http(error) from error
    return {"informe": informe, "base_actual": lab.estado_frente_a_la_base(informe)}


@router.get("/pronosticos/{clave}")
def pronostico(clave: str, lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    try:
        guardado = lab.pronostico(clave)
    except LaboratorioError as error:
        raise _http(error) from error
    return {"pronostico": guardado.artefacto, "version": guardado.version, "versiones": guardado.versiones,
            "resultado_observado": lab.estado_del_pronostico(guardado.artefacto)}


@router.get("/modelos")
def modelos(juego: str | None = Query(default=None), lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    codigos = [_juego(juego)] if juego else list(JUEGOS)
    return {"juegos": {c: lab.modelos(c) for c in codigos}, "familias_futuras": lab.catalogo()["familias_futuras"]}


@router.get("/modelos/{clave}")
def modelo(clave: str, lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    try:
        return lab.ficha_del_modelo(clave)
    except LaboratorioError as error:
        raise _http(error) from error


def _juego(codigo: str) -> str:
    if codigo not in JUEGOS:
        raise HTTPException(status_code=404, detail={"codigo": "no_encontrado", "mensaje": f"Juego no admitido: {codigo}"})
    return codigo


@router.get("/{codigo}/experimentos")
def experimentos(codigo: str, lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    elementos = lab.experimentos(_juego(codigo))
    return {"juego": codigo, "experimentos": [
        {"clave": e.identificador, "estado": "ilegible", "motivo": e.motivo} if not hasattr(e, "artefacto") else
        {"clave": e.identificador, "corte": e.artefacto["datos"]["corte"], "resumen": e.artefacto["resumen"],
         "terminado_en": e.artefacto["ejecucion"].get("terminado_en")} for e in elementos]}


@router.get("/{codigo}/seguimiento")
def seguimiento(codigo: str, linea: str | None = Query(default=None), tipo: str = Query(default="seguimiento"),
                lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    try:
        return lab.seguimiento(_juego(codigo), linea, tipo)
    except LaboratorioError as error:
        raise _http(error) from error


@router.get("/{codigo}")
def diagnostico(codigo: str, lab: LaboratorioDeModelos = Depends(get_laboratorio)) -> dict:
    return lab.diagnostico(_juego(codigo))
