from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.api.dependencies import get_listar_juegos, get_obtener_juego
from app.api.web.view_models import juego_a_vm, juego_con_reglas_a_vm
from app.application.use_cases.consultar_juegos import ListarJuegos, ObtenerJuego

router = APIRouter(prefix="/juegos")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def lista_juegos(request: Request, listar_juegos: ListarJuegos = Depends(get_listar_juegos)):
    juegos = [juego_a_vm(j) for j in listar_juegos.ejecutar()]
    return templates.TemplateResponse(
        request=request,
        name="juegos/lista.html",
        context={"active_page": "juegos", "juegos": juegos},
    )


@router.get("/{codigo}")
def detalle_juego(
    codigo: str, request: Request, obtener_juego: ObtenerJuego = Depends(get_obtener_juego)
):
    resultado = obtener_juego.ejecutar(codigo)
    return templates.TemplateResponse(
        request=request,
        name="juegos/detalle.html",
        context={"active_page": "juegos", "juego": juego_con_reglas_a_vm(resultado)},
    )
