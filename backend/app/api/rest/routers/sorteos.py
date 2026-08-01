from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_eliminar_sorteo,
    get_listar_sorteos,
    get_obtener_sorteo,
    get_registrar_sorteo,
)
from app.api.rest.mappers import sorteo_to_schema
from app.api.rest.schemas import RegistrarSorteoIn, SorteoListadoOut, SorteoOut
from app.application.exceptions import (
    JuegoNoEncontradoError,
    SorteoDuplicadoError,
    SorteoInvalidoError,
    SorteoNoEncontradoError,
)
from app.application.use_cases.eliminar_sorteo import EliminarSorteo
from app.application.use_cases.listar_sorteos import ListarSorteos, ListarSorteosInput
from app.application.use_cases.obtener_sorteo import ObtenerSorteo
from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination

router = APIRouter(prefix="/api/sorteos", tags=["sorteos"])


@router.get("", response_model=SorteoListadoOut)
def listar_sorteos(codigo_juego: str, listar: ListarSorteos = Depends(get_listar_sorteos)):
    try:
        resultado = listar.ejecutar(ListarSorteosInput(codigo_juego=codigo_juego))
    except JuegoNoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SorteoListadoOut(
        sorteos=[sorteo_to_schema(s) for s in resultado.sorteos], total=resultado.total
    )


@router.get("/{sorteo_id}", response_model=SorteoOut)
def obtener_sorteo(sorteo_id: UUID, obtener: ObtenerSorteo = Depends(get_obtener_sorteo)):
    try:
        return sorteo_to_schema(obtener.ejecutar(sorteo_id))
    except SorteoNoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("", response_model=SorteoOut, status_code=201)
def crear_sorteo(datos: RegistrarSorteoIn, registrar: RegistrarSorteo = Depends(get_registrar_sorteo)):
    resultado = Combination(
        numeros=tuple(datos.numeros),
        superbalota=datos.superbalota,
        pares=tuple(
            ColorNumberPair(numero=p.numero, color=Color(codigo=p.color_codigo, nombre=p.color_codigo))
            for p in datos.pares
        ),
    )
    try:
        sorteo = registrar.ejecutar(
            RegistrarSorteoInput(
                codigo_juego=datos.codigo_juego,
                numero_sorteo=datos.numero_sorteo,
                fecha=datos.fecha,
                resultado=resultado,
                fuente=datos.fuente,
            )
        )
    except JuegoNoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SorteoInvalidoError as e:
        raise HTTPException(status_code=422, detail="; ".join(e.errores)) from e
    except SorteoDuplicadoError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return sorteo_to_schema(sorteo)


@router.delete("/{sorteo_id}", status_code=204)
def eliminar_sorteo(sorteo_id: UUID, eliminar: EliminarSorteo = Depends(get_eliminar_sorteo)):
    try:
        eliminar.ejecutar(sorteo_id)
    except SorteoNoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
