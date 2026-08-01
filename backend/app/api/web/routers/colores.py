from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates

from app.api.dependencies import get_gestionar_paleta_colores, get_listar_juegos
from app.api.web.view_models import color_a_vm
from app.application.use_cases.consultar_juegos import ListarJuegos
from app.application.use_cases.gestionar_paleta_colores import (
    AgregarColorInput,
    GestionarPaletaColores,
    RetirarColorInput,
)

router = APIRouter(prefix="/colores")
templates = Jinja2Templates(directory="app/templates")


def _juego_colorloto_id(listar_juegos: ListarJuegos):
    for j in listar_juegos.ejecutar():
        if j.codigo == "COLORLOTO":
            return j.id
    return None


@router.get("")
def lista_colores(
    request: Request,
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    gestionar_colores: GestionarPaletaColores = Depends(get_gestionar_paleta_colores),
):
    juego_id = _juego_colorloto_id(listar_juegos)
    colores = gestionar_colores.listar_paleta_vigente(juego_id) if juego_id else []
    return templates.TemplateResponse(
        request=request,
        name="colores/lista.html",
        context={"active_page": "colores", "colores": [color_a_vm(c) for c in colores]},
    )


@router.post("")
def agregar_color(
    request: Request,
    codigo: str = Form(...),
    nombre: str = Form(...),
    vigente_desde: date = Form(...),
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    gestionar_colores: GestionarPaletaColores = Depends(get_gestionar_paleta_colores),
):
    juego_id = _juego_colorloto_id(listar_juegos)
    gestionar_colores.agregar_color(
        AgregarColorInput(
            juego_id=juego_id, codigo=codigo.strip().upper(), nombre=nombre.strip(),
            vigente_desde=vigente_desde,
        )
    )
    colores = gestionar_colores.listar_paleta_vigente(juego_id)
    return templates.TemplateResponse(
        request=request,
        name="colores/partials/tabla.html",
        context={"colores": [color_a_vm(c) for c in colores]},
    )


@router.delete("/{codigo}")
def retirar_color(
    codigo: str,
    request: Request,
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    gestionar_colores: GestionarPaletaColores = Depends(get_gestionar_paleta_colores),
):
    juego_id = _juego_colorloto_id(listar_juegos)
    gestionar_colores.retirar_color(
        RetirarColorInput(juego_id=juego_id, codigo=codigo, vigente_hasta=date.today())
    )
    colores = gestionar_colores.listar_paleta_vigente(juego_id)
    return templates.TemplateResponse(
        request=request,
        name="colores/partials/tabla.html",
        context={"colores": [color_a_vm(c) for c in colores]},
    )
