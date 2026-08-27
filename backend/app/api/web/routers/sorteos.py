"""
Router web de sorteos.

Es el router más ilustrativo de la integración: nunca construye SQL,
nunca valida reglas de juego -solo traduce entre formularios HTML y
los casos de uso (`RegistrarSorteo`, `EditarSorteo`, `EliminarSorteo`,
`ObtenerSorteo`, `ListarSorteos`), capturando las excepciones de
aplicación para mostrarlas como errores de formulario.
"""
from __future__ import annotations

import math
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
    get_obtener_sorteo_con_pareja,
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
from app.application.use_cases.obtener_sorteo_con_pareja import ObtenerSorteoConPareja
from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination

router = APIRouter(prefix="/sorteos")
templates = Jinja2Templates(directory="app/templates")

TAMANOS_PAGINA_VALIDOS = (25, 50, 100, 250)
TAMANO_PAGINA_DEFECTO = 100
COOKIE_TAMANO_PAGINA = "tamano_pagina_sorteos"
ORDEN_CAMPOS_VALIDOS = ("numero_sorteo", "fecha")


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


def _combination_desde_formulario(form, codigo_juego: str) -> Combination:
    """Traduce los campos crudos del formulario HTML (compartidos por
    crear_sorteo y actualizar_sorteo, antes duplicados verbatim en
    ambos) a un Combination."""
    numeros = [int(v) for v in form.getlist("numeros")] if form.getlist("numeros") else None
    superbalota = int(form["superbalota"]) if form.get("superbalota") else None
    colorloto_numeros = [int(v) for v in form.getlist("colorloto_numero")] or None
    colorloto_colores = form.getlist("colorloto_color") or None
    return _construir_combination(codigo_juego, numeros, superbalota, colorloto_numeros, colorloto_colores)


def _tamano_pagina_efectivo(request: Request, tamano: int | None) -> int:
    if tamano in TAMANOS_PAGINA_VALIDOS:
        return tamano
    cookie = request.cookies.get(COOKIE_TAMANO_PAGINA)
    if cookie and cookie.isdigit() and int(cookie) in TAMANOS_PAGINA_VALIDOS:
        return int(cookie)
    return TAMANO_PAGINA_DEFECTO


def _construir_paginacion(pagina: int, tamano: int, total: int) -> dict:
    total_paginas = max(1, math.ceil(total / tamano)) if total else 1
    pagina = min(max(1, pagina), total_paginas)
    desde_registro = (pagina - 1) * tamano + 1 if total else 0
    hasta_registro = min(pagina * tamano, total)
    return {
        "pagina_actual": pagina,
        "total_paginas": total_paginas,
        "total_registros": total,
        "tamano_pagina": tamano,
        "desde_registro": desde_registro,
        "hasta_registro": hasta_registro,
        "hay_anterior": pagina > 1,
        "hay_siguiente": pagina < total_paginas,
        "tamanos_disponibles": TAMANOS_PAGINA_VALIDOS,
        # rango corto de páginas alrededor de la actual, para no listar
        # cientos de números de página cuando hay miles de sorteos
        "paginas_visibles": [
            p for p in range(max(1, pagina - 2), min(total_paginas, pagina + 2) + 1)
        ],
    }


def _sorteos_paginados(
    request: Request,
    listar_sorteos: ListarSorteos,
    juego_codigo: str,
    pagina: int,
    tamano: int | None,
    orden: str | None,
    direccion: str | None,
    numero: int | None,
    numero_desde: int | None,
    numero_hasta: int | None,
    fecha_desde: date | None,
    fecha_hasta: date | None,
) -> tuple[list[dict], dict, dict]:
    """Ejecuta la consulta paginada para UN juego y arma (sorteos_vm,
    paginacion, filtros_vm) listos para el template. Toda la
    paginación ocurre en la base de datos (LIMIT/OFFSET real vía
    FiltroSorteos) -en ningún momento se cargan todos los sorteos del
    juego en memoria."""
    tamano_efectivo = _tamano_pagina_efectivo(request, tamano)
    orden_efectivo = orden if orden in ORDEN_CAMPOS_VALIDOS else "numero_sorteo"
    direccion_efectiva = direccion if direccion in ("asc", "desc") else "desc"

    if numero is not None:
        numero_desde = numero_hasta = numero

    resultado = listar_sorteos.ejecutar(
        ListarSorteosInput(
            codigo_juego=juego_codigo,
            desde=fecha_desde, hasta=fecha_hasta,
            numero_desde=numero_desde, numero_hasta=numero_hasta,
            orden_campo=orden_efectivo, orden_direccion=direccion_efectiva,
            limite=tamano_efectivo, offset=(max(1, pagina) - 1) * tamano_efectivo,
        )
    )

    paginacion = _construir_paginacion(pagina, tamano_efectivo, resultado.total)
    paginacion["orden"] = orden_efectivo
    paginacion["direccion"] = direccion_efectiva

    filtros_vm = {
        "numero": numero, "numero_desde": numero_desde, "numero_hasta": numero_hasta,
        "fecha_desde": fecha_desde.isoformat() if fecha_desde else "",
        "fecha_hasta": fecha_hasta.isoformat() if fecha_hasta else "",
    }

    return [sorteo_a_vm(s) for s in resultado.sorteos], paginacion, filtros_vm


@router.get("")
def lista_sorteos(
    request: Request,
    juego: str | None = None,
    pagina: int = 1,
    tamano: int | None = None,
    orden: str | None = None,
    direccion: str | None = None,
    numero: int | None = None,
    numero_desde: int | None = None,
    numero_hasta: int | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    listar_sorteos: ListarSorteos = Depends(get_listar_sorteos),
):
    juegos = [juego_a_vm(j) for j in listar_juegos.ejecutar()]

    if juego:
        sorteos_vm, paginacion, filtros_vm = _sorteos_paginados(
            request, listar_sorteos, juego, pagina, tamano, orden, direccion,
            numero, numero_desde, numero_hasta, fecha_desde, fecha_hasta,
        )
    else:
        # Sin un juego seleccionado no hay un único criterio de orden
        # ni de paginación consistente entre juegos distintos -se
        # muestra una vista previa reciente y se invita a elegir un
        # juego para la exploración completa con paginación.
        sorteos_vm = _vista_previa_todos_los_juegos(listar_sorteos, juegos)
        paginacion, filtros_vm = None, {}

    respuesta = templates.TemplateResponse(
        request=request,
        name="sorteos/lista.html",
        context={
            "active_page": "sorteos",
            "juegos": juegos,
            "juego_seleccionado": juego or "",
            "sorteos": sorteos_vm,
            "paginacion": paginacion,
            "filtros": filtros_vm,
        },
    )
    if paginacion:
        respuesta.set_cookie(COOKIE_TAMANO_PAGINA, str(paginacion["tamano_pagina"]), max_age=60 * 60 * 24 * 365)
    return respuesta


@router.get("/tabla")
def tabla_sorteos(
    request: Request,
    juego: str | None = None,
    pagina: int = 1,
    tamano: int | None = None,
    orden: str | None = None,
    direccion: str | None = None,
    numero: int | None = None,
    numero_desde: int | None = None,
    numero_hasta: int | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    listar_sorteos: ListarSorteos = Depends(get_listar_sorteos),
):
    if not juego:
        return HTMLResponse(
            "<div class='p-4 text-muted'>Selecciona un juego para explorar su historial paginado.</div>"
        )

    sorteos_vm, paginacion, filtros_vm = _sorteos_paginados(
        request, listar_sorteos, juego, pagina, tamano, orden, direccion,
        numero, numero_desde, numero_hasta, fecha_desde, fecha_hasta,
    )
    respuesta = templates.TemplateResponse(
        request=request,
        name="sorteos/partials/tabla.html",
        context={
            "sorteos": sorteos_vm, "paginacion": paginacion, "filtros": filtros_vm,
            "juego_seleccionado": juego,
        },
    )
    respuesta.set_cookie(COOKIE_TAMANO_PAGINA, str(paginacion["tamano_pagina"]), max_age=60 * 60 * 24 * 365)
    return respuesta


def _vista_previa_todos_los_juegos(listar_sorteos: ListarSorteos, juegos_vm: list[dict]) -> list[dict]:
    sorteos_vm: list[dict] = []
    for j in juegos_vm:
        resultado = listar_sorteos.ejecutar(
            ListarSorteosInput(codigo_juego=j["codigo"], orden_campo="fecha", orden_direccion="desc", limite=20)
        )
        sorteos_vm.extend(sorteo_a_vm(s) for s in resultado.sorteos)
    sorteos_vm.sort(key=lambda s: s["fecha"], reverse=True)
    return sorteos_vm


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
    resultado = _combination_desde_formulario(form, codigo_juego)

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
    obtener_sorteo_con_pareja: ObtenerSorteoConPareja = Depends(get_obtener_sorteo_con_pareja),
):
    resultado = obtener_sorteo_con_pareja.ejecutar(sorteo_id)
    return templates.TemplateResponse(
        request=request,
        name="sorteos/detalle.html",
        context={
            "active_page": "sorteos",
            "sorteo": sorteo_a_vm(resultado.sorteo),
            "juego_nombre": resultado.juego.nombre,
            "juego_codigo": resultado.juego.codigo,
            "sorteo_pareja": sorteo_a_vm(resultado.sorteo_pareja) if resultado.sorteo_pareja else None,
            "juego_pareja_nombre": resultado.juego_pareja.nombre if resultado.juego_pareja else None,
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
    resultado = _combination_desde_formulario(form, codigo_juego)

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
    juego: str | None = None,
    pagina: int = 1,
    tamano: int | None = None,
    orden: str | None = None,
    direccion: str | None = None,
    eliminar_sorteo: EliminarSorteo = Depends(get_eliminar_sorteo),
    listar_juegos: ListarJuegos = Depends(get_listar_juegos),
    listar_sorteos: ListarSorteos = Depends(get_listar_sorteos),
):
    eliminar_sorteo.ejecutar(sorteo_id)

    if not juego:
        return HTMLResponse(
            "<div class='p-4 text-muted'>Sorteo eliminado. Selecciona un juego para ver el historial.</div>"
        )

    # Se re-renderiza la MISMA página/orden en la que estaba el
    # usuario -si esa página quedó vacía (era la última y solo tenía
    # ese registro), _construir_paginacion la ajusta automáticamente
    # a la última página válida según el nuevo total.
    sorteos_vm, paginacion, filtros_vm = _sorteos_paginados(
        request, listar_sorteos, juego, pagina, tamano, orden, direccion,
        None, None, None, None, None,
    )
    respuesta = templates.TemplateResponse(
        request=request,
        name="sorteos/partials/tabla.html",
        context={
            "sorteos": sorteos_vm, "paginacion": paginacion, "filtros": filtros_vm,
            "juego_seleccionado": juego,
        },
    )
    respuesta.set_cookie(COOKIE_TAMANO_PAGINA, str(paginacion["tamano_pagina"]), max_age=60 * 60 * 24 * 365)
    return respuesta
