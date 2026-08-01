from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_listar_juegos, get_obtener_juego
from app.api.rest.mappers import juego_con_reglas_to_schema, juego_to_schema
from app.api.rest.schemas import JuegoConReglasOut, JuegoOut
from app.application.use_cases.consultar_juegos import ListarJuegos, ObtenerJuego

router = APIRouter(prefix="/api/juegos", tags=["juegos"])


@router.get("", response_model=list[JuegoOut])
def listar_juegos(listar: ListarJuegos = Depends(get_listar_juegos)):
    return [juego_to_schema(j) for j in listar.ejecutar()]


@router.get("/{codigo}", response_model=JuegoConReglasOut)
def obtener_juego(codigo: str, obtener: ObtenerJuego = Depends(get_obtener_juego)):
    return juego_con_reglas_to_schema(obtener.ejecutar(codigo))
