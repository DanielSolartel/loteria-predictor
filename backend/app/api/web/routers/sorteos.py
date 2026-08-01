"""
Router web de sorteos.

Es el router más ilustrativo de la integración: nunca construye SQL,
nunca valida reglas de juego -solo traduce entre formularios HTML y
los casos de uso (`RegistrarSorteo`, `EditarSorteo`, `EliminarSorteo`,
`ObtenerSorteo`, `ListarSorteos`), capturando las excepciones de
aplicación para mostrarlas como errores de formulario.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import (
    get_editar_sorteo,
    get_eliminar_sorteo,
    get_gestionar_paleta_colores,
    get_listar_juegos,
    get_listar_sorteos,
    get_obtener_sorteo,
    get_registrar_sorteo,
)
from app.api.web.view_models import juego_a_vm, sorteo_a_vm
from app.application.exceptions import SorteoDuplicadoError, SorteoInvalidoError
from app.application.use_cases.consultar_juegos import ListarJuegos
from app.application.use_cases.editar_sorteo import EditarSorteo, EditarSorteoInput
from app.application.use_cases.eliminar_sorteo import EliminarSorteo
from app.application.use_cases.gestionar_paleta_colores import GestionarPaletaColores
from app.application.use_cases.listar_sorteos import ListarSorteos, ListarSorteosInput
from app.application.use_cases.obtener_sorteo import ObtenerSorteo
from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination

router = APIRouter(prefix="/sorteos")
templates = Jinja2Templates(directory="app/templates")


def _construir_combination(
    codigo_juego: str,
    numeros: list[int] | None,
    superbalota: int | None,
    colorloto_numeros: list[int] | None,
    colorloto_colores: list[str] | None,
) -> Combination:
    if codigo_juego == "COLORLOTO":
        pares = tuple(
            ColorNumberPair(numero=n, color=Color(codigo=c, nombre=c))
            for n, c in zip(colorloto_numeros or [], colorloto_colores or [])
        )
        return Combination(pares=pares)
    return Combination(numeros=tuple(numeros or []), superbalota=superbalota)


@router.get("")
def lista_sorteos(
    request: Request,
    juego: str | None = None,
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    listar_sorteos: ListarSorteos = Depends(get_listar_sorteos),
):
    juegos = [juego_a_vm(j) for j in listar_juegos.ejecutar()]
    sorteos_vm, total = _sorteos_y_total(juego, juegos, listar_sorteos)
    return templates.TemplateResponse(
        request=request,
        name="sorteos/lista.html",
        context={
            "active_page": "sorteos",
            "juegos": juegos,
            "juego_seleccionado": juego or "",
            "sorteos": sorteos_vm,
            "total": total,
        },
    )


@router.get("/tabla")
def tabla_sorteos(
    request: Request,
    juego: str | None = None,
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    listar_sorteos: ListarSorteos = Depends(get_listar_sorteos),
):
    juegos = [juego_a_vm(j) for j in listar_juegos.ejecutar()]
    sorteos_vm, total = _sorteos_y_total(juego, juegos, listar_sorteos)
    return templates.TemplateResponse(
        request=request,
        name="sorteos/partials/tabla.html",
        context={"sorteos": sorteos_vm, "total": total, "juego_seleccionado": juego or ""},
    )


def _sorteos_y_total(juego_codigo, juegos_vm, listar_sorteos: ListarSorteos):
    if juego_codigo:
        resultado = listar_sorteos.ejecutar(ListarSorteosInput(codigo_juego=juego_codigo))
        return [sorteo_a_vm(s) for s in resultado.sorteos], resultado.total

    sorteos_vm: list[dict] = []
    total = 0
    for j in juegos_vm:
        resultado = listar_sorteos.ejecutar(ListarSorteosInput(codigo_juego=j["codigo"]))
        sorteos_vm.extend(sorteo_a_vm(s) for s in resultado.sorteos)
        total += resultado.total
    sorteos_vm.sort(key=lambda s: s["fecha"], reverse=True)
    return sorteos_vm, total


@router.get("/campos")
def campos_dinamicos(
    request: Request,
    juego: str = "",
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    gestionar_colores: GestionarPaletaColores = Depends(get_gestionar_paleta_colores),
):
    if not juego:
        return HTMLResponse("")

    juegos = {j.codigo: j for j in listar_juegos.ejecutar()}
    juego_entidad = juegos.get(juego)
    if juego_entidad is None:
        return HTMLResponse("<p class='text-danger small'>Juego no encontrado.</p>")

    if juego_entidad.tiene_color:
        colores = gestionar_colores.listar_paleta_vigente(juego_entidad.id)
        return templates.TemplateResponse(
            request=request,
            name="sorteos/partials/campos_colorloto.html",
            context={
                "cantidad_balotas": juego_entidad.cantidad_numeros,
                "colores": [{"codigo": c.codigo, "nombre": c.nombre} for c in colores],
                "valores_pares": None,
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="sorteos/partials/campos_estandar.html",
        context={
            "cantidad_numeros": juego_entidad.cantidad_numeros,
            "rango_min": juego_entidad.rango_min,
            "rango_max": juego_entidad.rango_max,
            "tiene_superbalota": juego_entidad.tiene_superbalota,
            "superbalota_min": juego_entidad.superbalota_min,
            "superbalota_max": juego_entidad.superbalota_max,
            "valores_numeros": None,
            "valor_superbalota": None,
        },
    )


@router.get("/nuevo")
def formulario_nuevo(
    request: Request, juego: str = "", listar_juegos: ListarJuegos = Depends(get_listar_juegos)
):
    juegos = [juego_a_vm(j) for j in listar_juegos.ejecutar()]
    return templates.TemplateResponse(
        request=request,
        name="sorteos/formulario.html",
        context={
            "active_page": "sorteos",
            "modo_edicion": False,
            "juegos": juegos,
            "juego_preseleccionado": juego,
            "error": False,
            "errores": [],
        },
    )


@router.post("")
async def crear_sorteo(
    request: Request,
    codigo_juego: str = Form(...),
    numero_sorteo: int = Form(...),
    fecha: date = Form(...),
    fuente: str = Form(""),
    registrar_sorteo: RegistrarSorteo = Depends(get_registrar_sorteo),
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
):
    form = await request.form()
    numeros = [int(v) for v in form.getlist("numeros")] if form.getlist("numeros") else None
    superbalota = int(form["superbalota"]) if form.get("superbalota") else None
    colorloto_numeros = [int(v) for v in form.getlist("colorloto_numero")] or None
    colorloto_colores = form.getlist("colorloto_color") or None

    resultado = _construir_combination(
        codigo_juego, numeros, superbalota, colorloto_numeros, colorloto_colores
    )

    try:
        registrar_sorteo.ejecutar(
            RegistrarSorteoInput(
                codigo_juego=codigo_juego,
                numero_sorteo=numero_sorteo,
                fecha=fecha,
                resultado=resultado,
                fuente=fuente or None,
            )
        )
    except (SorteoInvalidoError, SorteoDuplicadoError) as e:
        errores = list(getattr(e, "errores", [str(e)]))
        juegos = [juego_a_vm(j) for j in listar_juegos.ejecutar()]
        return templates.TemplateResponse(
            request=request,
            name="sorteos/formulario.html",
            context={
                "active_page": "sorteos",
                "modo_edicion": False,
                "juegos": juegos,
                "juego_preseleccionado": codigo_juego,
                "error": True,
                "errores": errores,
            },
        )

    response = HTMLResponse(status_code=200)
    response.headers["HX-Redirect"] = "/sorteos"
    return response


@router.get("/{sorteo_id}")
def detalle_sorteo(
    sorteo_id: UUID,
    request: Request,
    obtener_sorteo: ObtenerSorteo = Depends(get_obtener_sorteo),
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
):
    sorteo = obtener_sorteo.ejecutar(sorteo_id)
    juegos = {j.id: j for j in listar_juegos.ejecutar()}
    juego = juegos.get(sorteo.juego_id)
    return templates.TemplateResponse(
        request=request,
        name="sorteos/detalle.html",
        context={
            "active_page": "sorteos",
            "sorteo": sorteo_a_vm(sorteo),
            "juego_nombre": juego.nombre if juego else "—",
        },
    )


@router.get("/{sorteo_id}/editar")
def formulario_editar(
    sorteo_id: UUID,
    request: Request,
    obtener_sorteo: ObtenerSorteo = Depends(get_obtener_sorteo),
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
):
    sorteo = obtener_sorteo.ejecutar(sorteo_id)
    juegos = {j.id: j for j in listar_juegos.ejecutar()}
    juego = juegos.get(sorteo.juego_id)
    return templates.TemplateResponse(
        request=request,
        name="sorteos/formulario.html",
        context={
            "active_page": "sorteos",
            "modo_edicion": True,
            "sorteo": sorteo_a_vm(sorteo),
            "juego_actual": juego_a_vm(juego) if juego else None,
            "error": False,
            "errores": [],
        },
    )


@router.put("/{sorteo_id}")
async def actualizar_sorteo(
    sorteo_id: UUID,
    request: Request,
    codigo_juego: str = Form(...),
    fecha: date = Form(...),
    fuente: str = Form(""),
    editar_sorteo: EditarSorteo = Depends(get_editar_sorteo),
    obtener_sorteo: ObtenerSorteo = Depends(get_obtener_sorteo),
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
):
    form = await request.form()
    numeros = [int(v) for v in form.getlist("numeros")] if form.getlist("numeros") else None
    superbalota = int(form["superbalota"]) if form.get("superbalota") else None
    colorloto_numeros = [int(v) for v in form.getlist("colorloto_numero")] or None
    colorloto_colores = form.getlist("colorloto_color") or None

    resultado = _construir_combination(
        codigo_juego, numeros, superbalota, colorloto_numeros, colorloto_colores
    )

    try:
        editar_sorteo.ejecutar(
            EditarSorteoInput(
                sorteo_id=sorteo_id, fecha=fecha, resultado=resultado, fuente=fuente or None
            )
        )
    except SorteoInvalidoError as e:
        sorteo_actual = obtener_sorteo.ejecutar(sorteo_id)
        juegos = {j.id: j for j in listar_juegos.ejecutar()}
        juego = juegos.get(sorteo_actual.juego_id)
        return templates.TemplateResponse(
            request=request,
            name="sorteos/formulario.html",
            context={
                "active_page": "sorteos",
                "modo_edicion": True,
                "sorteo": sorteo_a_vm(sorteo_actual),
                "juego_actual": juego_a_vm(juego) if juego else None,
                "error": True,
                "errores": list(e.errores),
            },
        )

    response = HTMLResponse(status_code=200)
    response.headers["HX-Redirect"] = f"/sorteos/{sorteo_id}"
    return response


@router.delete("/{sorteo_id}")
def eliminar_sorteo_endpoint(
    sorteo_id: UUID,
    request: Request,
    eliminar_sorteo: EliminarSorteo = Depends(get_eliminar_sorteo),
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    listar_sorteos: ListarSorteos = Depends(get_listar_sorteos),
):
    eliminar_sorteo.ejecutar(sorteo_id)
    juegos = [juego_a_vm(j) for j in listar_juegos.ejecutar()]
    sorteos_vm, total = _sorteos_y_total(None, juegos, listar_sorteos)
    return templates.TemplateResponse(
        request=request,
        name="sorteos/partials/tabla.html",
        context={"sorteos": sorteos_vm, "total": total, "juego_seleccionado": ""},
    )
