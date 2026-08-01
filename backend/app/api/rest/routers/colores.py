from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_gestionar_paleta_colores, get_listar_juegos
from app.api.rest.mappers import color_to_schema
from app.api.rest.schemas import ColorOut
from app.application.use_cases.consultar_juegos import ListarJuegos
from app.application.use_cases.gestionar_paleta_colores import (
    AgregarColorInput,
    GestionarPaletaColores,
    RetirarColorInput,
)

router = APIRouter(prefix="/api/colores", tags=["colores"])


def _juego_colorloto_id(listar_juegos: ListarJuegos):
    for j in listar_juegos.ejecutar():
        if j.codigo == "COLORLOTO":
            return j.id
    return None


@router.get("", response_model=list[ColorOut])
def listar_colores(
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    gestionar: GestionarPaletaColores = Depends(get_gestionar_paleta_colores),
):
    juego_id = _juego_colorloto_id(listar_juegos)
    if juego_id is None:
        raise HTTPException(status_code=404, detail="Juego COLORLOTO no configurado")
    return [color_to_schema(c) for c in gestionar.listar_paleta_vigente(juego_id)]


@router.post("", response_model=list[ColorOut], status_code=201)
def agregar_color(
    codigo: str,
    nombre: str,
    vigente_desde: date,
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    gestionar: GestionarPaletaColores = Depends(get_gestionar_paleta_colores),
):
    juego_id = _juego_colorloto_id(listar_juegos)
    if juego_id is None:
        raise HTTPException(status_code=404, detail="Juego COLORLOTO no configurado")
    gestionar.agregar_color(
        AgregarColorInput(juego_id=juego_id, codigo=codigo, nombre=nombre, vigente_desde=vigente_desde)
    )
    return [color_to_schema(c) for c in gestionar.listar_paleta_vigente(juego_id)]


@router.delete("/{codigo}", response_model=list[ColorOut])
def retirar_color(
    codigo: str,
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    gestionar: GestionarPaletaColores = Depends(get_gestionar_paleta_colores),
):
    juego_id = _juego_colorloto_id(listar_juegos)
    if juego_id is None:
        raise HTTPException(status_code=404, detail="Juego COLORLOTO no configurado")
    gestionar.retirar_color(RetirarColorInput(juego_id=juego_id, codigo=codigo, vigente_hasta=date.today()))
    return [color_to_schema(c) for c in gestionar.listar_paleta_vigente(juego_id)]
