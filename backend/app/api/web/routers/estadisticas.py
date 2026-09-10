"""
Router web: estadísticas.

Generalizado para soportar tres juegos mediante un slug en la URL:
`baloto`, `baloto-revancha`, `miloto` -un conjunto CERRADO
(`_SLUG_A_CODIGO`), nunca se usa un valor recibido directamente como
código de juego. Un slug fuera de ese conjunto produce 404 antes de
tocar la base de datos -no hay fallback silencioso a Baloto ni
consulta con código arbitrario.

Cuatro funciones (una por métrica: números, superbalota, observada vs.
esperada, atrasos -Etapa W), no doce: el juego es un parámetro de
ruta (`{juego_slug}`), no una copia de la función. Las URLs de Baloto
se conservan exactamente (`/estadisticas/baloto/...` ya es una
instancia válida de este mismo patrón parametrizado, sin ningún caso
especial).

Esta ruta sigue sin calcular una frecuencia, contar un número, ni
ordenar resultados estadísticamente -eso lo hace
`CalcularYPersistirEstadistica` y `view_models.py`, exactamente como
antes de esta generalización.
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BeforeValidator, Field
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_calcular_y_persistir_estadistica,
    get_color_repository,
    get_game_factory,
    get_juego_repository,
    get_resultados_historicos_repository,
)
from app.api.web.estadisticas_slugs import CAPACIDAD_SUPERBALOTA_POR_SLUG, resolver_codigo
from app.api.web.view_models import (
    atrasos_numeros_a_vm,
    atrasos_numeros_colorloto_a_vm,
    atrasos_colores_colorloto_a_vm,
    atrasos_pares_colorloto_a_vm,
    repeticiones_entre_sorteos_colorloto_a_vm,
    distribucion_pares_impares_colorloto_a_vm,
    distribucion_altos_bajos_colorloto_a_vm,
    maximo_repeticion_color_por_sorteo_colorloto_a_vm,
    distribucion_pares_consecutivos_colorloto_a_vm,
    distribucion_racha_maxima_colorloto_a_vm,
    distribucion_trios_consecutivos_colorloto_a_vm,
    coocurrencia_pares_colorloto_a_vm,
    coocurrencia_trios_colorloto_a_vm,
    coocurrencia_pares_colores_colorloto_a_vm,
    coocurrencia_trios_colores_colorloto_a_vm,
    intervalos_historicos_colores_colorloto_a_vm,
    distribucion_sumas_colorloto_a_vm,
    intervalos_historicos_numeros_colorloto_a_vm,
    intervalos_historicos_pares_numero_color_colorloto_a_vm,
    frecuencia_colores_por_anio_colorloto_a_vm,
    frecuencia_colores_por_mes_colorloto_a_vm,
    frecuencia_colores_por_dia_semana_colorloto_a_vm,
    frecuencia_pares_numero_color_por_anio_colorloto_a_vm,
    frecuencia_pares_numero_color_por_mes_colorloto_a_vm,
    frecuencia_pares_numero_color_por_dia_semana_colorloto_a_vm,
    distribucion_conteo_color_colorloto_a_vm,
    comparacion_frecuencia_numeros_por_ventana_colorloto_a_vm,
    comparacion_frecuencia_colores_por_ventana_colorloto_a_vm,
    comparacion_frecuencia_pares_numero_color_por_ventana_colorloto_a_vm,
    construir_navegacion_estadisticas,
    distribucion_altos_bajos_a_vm,
    distribucion_pares_consecutivos_a_vm,
    distribucion_pares_impares_a_vm,
    distribucion_racha_maxima_a_vm,
    distribucion_repeticiones_entre_sorteos_a_vm,
    frecuencia_colores_colorloto_a_vm,
    frecuencia_numeros_a_vm,
    frecuencia_numeros_colorloto_a_vm,
    frecuencia_pares_colorloto_a_vm,
    frecuencia_superbalota_a_vm,
    tabla_frecuencia_numeros_a_vm,
)
from app.application.exceptions import ColorNoVigenteError, JuegoNoEncontradoError, JuegoSinSuperbalotaError
from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.use_cases.calcular_y_persistir_estadistica import (
    POLITICA_UNIVERSO_COLORES_ACTUAL,
    CalcularYPersistirEstadistica,
    _codigos_colores_vigentes_en_referencia,
    _obtener_historico_colorloto,
)
from app.application.use_cases.game_factory import GameFactory
from app.infrastructure.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _resolver_codigo(juego_slug: str) -> str:
    """Slug desconocido -> 404 controlado, ANTES de cualquier consulta
    a la base de datos. La lógica de resolución en sí vive en
    `estadisticas_slugs.py` (sin FastAPI) -aquí solo se traduce un
    `None` en la excepción HTTP correspondiente."""
    codigo = resolver_codigo(juego_slug)
    if codigo is None:
        raise HTTPException(status_code=404, detail=f"Estadísticas no disponibles para '{juego_slug}'")
    return codigo


def _resolver_juego(juego_slug: str, juego_repository: JuegoRepository, game_factory: GameFactory):
    codigo = _resolver_codigo(juego_slug)
    juego = juego_repository.obtener_por_codigo(codigo)
    if juego is None:
        raise JuegoNoEncontradoError(codigo)
    return juego, game_factory.crear(juego)


def _nombres_reales(juego_repository: JuegoRepository, db_conectada: bool) -> dict[str, str] | None:
    if not db_conectada:
        return None
    try:
        return {j.codigo: j.nombre for j in juego_repository.listar_activos()}
    except Exception:
        return None


def _verificar_conexion(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _corte_vacio_a_none(valor):
    """Normaliza EXCLUSIVAMENTE la cadena vacía (`""`) a `None` antes de
    que Pydantic intente convertirla a `int` -corrección de mantenimiento
    global, previa a AE-29. Defecto real descubierto originalmente por
    validación visual real en el navegador durante AE-28 (nunca por las
    pruebas automatizadas previas de esa etapa, que construían la URL
    omitiendo el parámetro por completo en vez de incluirlo vacío, como
    sí hace la serialización nativa de un formulario GET real: todo
    campo `<input>` con `name` se envía SIEMPRE en la query string,
    incluso vacío). Auditoría real posterior (previa a AE-29) confirmó
    que el mismo defecto era LATENTE en las 36 rutas restantes -incluidas
    todas las que reutilizan `control_corte_temporal.html`, cuyo campo
    de corte nunca tuvo `required`- así que esta corrección deja de ser
    exclusiva de AE-28 y se generaliza a las 37 rutas reales.

    Se usa como `BeforeValidator` -corre ANTES de que Pydantic intente
    el `int_parsing`, así que nunca compite con él ni con `ge=1`
    (aplicado únicamente sobre la rama `int` mediante
    `Annotated[int, Field(ge=1)] | None`, confirmado real: `0`, `-1` y
    `"texto"` siguen produciendo `422` exactamente igual que antes,
    `""` y la ausencia total del parámetro producen ambos `None`).
    NUNCA convierte ningún otro valor -`"0"`, `"-1"`, `"texto"`, `" "`
    (con espacio) pasan intactos a la validación de tipo/rango normal,
    que los sigue rechazando con `422`; solo la cadena vacía exacta se
    normaliza. Aplicado ahora a las 37 rutas reales (vía el alias de
    tipo compartido `_CorteOpcional`, local a este módulo) -mismo
    contrato exacto para todas, confirmado por AST real: cero
    declaraciones nativas `Query(default=None, ge=1)` restantes."""
    return None if valor == "" else valor


_CorteOpcional = Annotated[
    Annotated[int, Field(ge=1)] | None, BeforeValidator(_corte_vacio_a_none), Query(),
]


@router.get("/estadisticas/colorloto/frecuencia-numeros")
def frecuencia_numeros_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-1: primera visualización descriptiva de ColorLoto
    -frecuencia de números observados (1..K), ignorando el color de
    cada balota. Reutiliza `calcular_frecuencia_numeros_colorloto`
    sin modificarlo.

    Ruta DELIBERADAMENTE AISLADA de las 9 rutas numéricas genéricas:
    NO usa `_resolver_codigo`/`SLUG_A_CODIGO` (agregar "colorloto" a
    ese diccionario compartido expondría las 9 métricas numéricas a
    ColorLoto, produciendo resultados matemáticamente incorrectos o
    errores no controlados -riesgo confirmado en la auditoría de
    diseño previa), resuelve únicamente el código fijo "COLORLOTO".
    Tampoco construye `ColorLotoGame`/`GameFactory` -`rango_min`,
    `rango_max` y `cantidad_numeros` se leen directamente de la
    entidad `Juego` ya persistida (mismos campos reales del seed),
    sin necesitar `has_superballot` (que `ColorLotoGame` ni siquiera
    tiene, al no heredar de `StandardNumberGame`).

    Un slug/métrica incompatible como
    `/estadisticas/colorloto/distribucion-pares-impares` nunca
    coincide con ninguna ruta registrada (ColorLoto no está en
    `SLUG_A_CODIGO`) -produce 404 nativo de FastAPI, nunca un
    `AttributeError` ni un 500 no controlado."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/frecuencia-numeros",
        "pagina_colorloto_activa": "frecuencia-numeros",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_numeros_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    rango_min, rango_max, cantidad_numeros = juego.rango_min, juego.rango_max, juego.cantidad_numeros

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_numeros_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros},
    )

    vm = frecuencia_numeros_colorloto_a_vm(resultado, rango_min, rango_max, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_numeros_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/frecuencia-colores")
def frecuencia_colores_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-2: segunda visualización descriptiva de ColorLoto
    -frecuencia de colores observados, ignorando el número de cada
    balota. Reutiliza `calcular_frecuencia_colores` sin modificarlo.

    Mismo aislamiento deliberado que `frecuencia_numeros_colorloto`
    (Etapa AE-1): ruta literal, fuera de `SLUG_A_CODIGO`, agrupada
    junto a las demás rutas de ColorLoto y registrada ANTES de
    cualquier ruta genérica -aunque ningún sufijo "frecuencia-colores"
    coincida con las 9 rutas numéricas existentes (confirmado con una
    simulación fiel del algoritmo de Starlette, sin colisión posible
    en ninguna posición), esta posición se conserva por prudencia y
    consistencia con el patrón ya establecido."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/frecuencia-colores",
        "pagina_colorloto_activa": "frecuencia-colores",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_colores_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_colores_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": juego.rango_min, "rango_max": juego.rango_max, "cantidad_numeros": juego.cantidad_numeros,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = frecuencia_colores_colorloto_a_vm(resultado, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_colores_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/frecuencia-pares-numero-color")
def frecuencia_pares_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-3: tercera visualización descriptiva de ColorLoto
    -frecuencia de cada PAR EXACTO número-color, la unidad atómica
    más granular de las tres. Reutiliza
    `calcular_frecuencia_pares_numero_color` sin modificarlo.

    Mismo aislamiento deliberado que AE-1/AE-2: ruta literal, fuera
    de `SLUG_A_CODIGO`, agrupada junto a las demás rutas de ColorLoto
    y registrada ANTES de cualquier ruta genérica -confirmado sin
    colisión posible con ninguno de los 9 sufijos numéricos existentes
    mediante simulación fiel del algoritmo de Starlette, misma
    posición mantenida por prudencia y consistencia."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/frecuencia-pares-numero-color",
        "pagina_colorloto_activa": "frecuencia-pares-numero-color",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_pares_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_pares_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": juego.rango_min, "rango_max": juego.rango_max, "cantidad_numeros": juego.cantidad_numeros,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = frecuencia_pares_colorloto_a_vm(resultado, juego.rango_min, juego.rango_max, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_pares_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/atrasos-numeros")
def atrasos_numeros_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-4: cuarta visualización descriptiva de ColorLoto
    -atraso del NÚMERO de cada balota, ignorando el color. Reutiliza
    `calcular_atrasos_numeros_colorloto` sin modificarlo.

    CRÍTICO -a diferencia de `frecuencia-colores`/`frecuencia-pares-numero-color`
    (Etapas AE-2/AE-3, sin colisión posible), esta ruta SÍ colisiona
    con la ruta genérica homónima `/estadisticas/{juego_slug}/atrasos-numeros`
    -mismo defecto que se corrigió en AE-1 (`frecuencia-numeros`).
    Por eso esta ruta se declara aquí, agrupada con las otras tres de
    ColorLoto, ANTES de cualquier ruta genérica -desde la primera
    edición, no como corrección posterior (confirmado con petición
    real de FastAPI/TestClient en los tests, no solo simulación
    estática)."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/atrasos-numeros",
        "pagina_colorloto_activa": "atrasos-numeros",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/atrasos_numeros_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="atrasos_numeros_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": juego.rango_min, "rango_max": juego.rango_max, "cantidad_numeros": juego.cantidad_numeros,
        },
    )

    vm = atrasos_numeros_colorloto_a_vm(resultado, juego.rango_min, juego.rango_max, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/atrasos_numeros_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/atrasos-colores")
def atrasos_colores_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-5: quinta visualización descriptiva de ColorLoto
    -atraso del COLOR de cada balota, ignorando el número. Reutiliza
    `calcular_atrasos_colores` sin modificarlo.

    Confirmado sin colisión posible con ninguna de las 9 rutas
    genéricas (a diferencia de `atrasos-numeros`, que sí colisiona);
    mantenida agrupada con las demás rutas de ColorLoto, antes de
    cualquier ruta genérica, por consistencia con el patrón ya
    establecido (mismo criterio que `frecuencia-colores`/
    `frecuencia-pares-numero-color`).

    Reutiliza el contrato temporal de paleta ya validado por AE-4P:
    el marcador estático `POLITICA_UNIVERSO_COLORES_ACTUAL` forma
    parte de la identidad de caché, mismo patrón exacto ya usado por
    `frecuencia_colores_colorloto`/`frecuencia_pares_colorloto`."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/atrasos-colores",
        "pagina_colorloto_activa": "atrasos-colores",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/atrasos_colores_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="atrasos_colores_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": juego.rango_min, "rango_max": juego.rango_max, "cantidad_numeros": juego.cantidad_numeros,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = atrasos_colores_colorloto_a_vm(resultado, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/atrasos_colores_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/atrasos-pares-numero-color")
def atrasos_pares_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-6: sexta visualización descriptiva de ColorLoto
    -atraso del PAR EXACTO (número, color) como unidad atómica,
    distinto de atrasos de número y de atrasos de color por
    separado. Reutiliza `calcular_atrasos_pares_numero_color` sin
    modificarlo.

    Confirmado sin colisión posible con ninguna de las 9 rutas
    genéricas (a diferencia de `atrasos-numeros`, que sí
    colisiona); mantenida agrupada con las demás rutas de
    ColorLoto, antes de cualquier ruta genérica, por consistencia
    con el patrón ya establecido.

    Reutiliza el contrato temporal de paleta ya validado por
    AE-4P: el marcador estático `POLITICA_UNIVERSO_COLORES_ACTUAL`
    forma parte de la identidad de caché, mismo patrón exacto ya
    usado por `frecuencia_pares_colorloto`/`atrasos_colores_colorloto`."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/atrasos-pares-numero-color",
        "pagina_colorloto_activa": "atrasos-pares-numero-color",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/atrasos_pares_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="atrasos_pares_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": juego.rango_min, "rango_max": juego.rango_max, "cantidad_numeros": juego.cantidad_numeros,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = atrasos_pares_colorloto_a_vm(resultado, juego.rango_min, juego.rango_max, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/atrasos_pares_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/repeticiones-entre-sorteos")
def repeticiones_entre_sorteos_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-7: séptima visualización descriptiva de ColorLoto
    -cuántos números (con multiplicidad, multiconjunto) coinciden
    entre cada par de sorteos numericamente consecutivos
    (numero_sorteo_actual == numero_sorteo_anterior + 1), ignorando
    color por completo. Reutiliza
    `calcular_repeticiones_entre_sorteos_colorloto` sin
    modificarlo.

    Ruta registrada OBLIGATORIAMENTE antes de la ruta genérica
    homonima `/estadisticas/{juego_slug}/repeticiones-entre-sorteos`
    -ambas comparten exactamente el mismo sufijo; si el orden
    fuera incorrecto, Starlette capturaria esta URL con el
    handler generico (`juego_slug='colorloto'`), que devolveria
    un 404 controlado via `_resolver_codigo` en vez de alcanzar
    este handler dedicado -mismo defecto critico ya corregido
    para atrasos-numeros (Etapa AE-4).

    `FrecuenciaObservada.total_sorteos` aqui es la cantidad de
    TRANSICIONES VALIDAS, nunca la cantidad de sorteos -mismo
    criterio exacto ya validado por
    `distribucion_repeticiones_entre_sorteos` (Etapa AC); el View
    Model la presenta como "Transiciones analizadas".

    Sin marcador de politica de colores en la identidad de
    cache: el motor ignora el color por completo, un cambio de
    paleta no puede alterar el resultado matematico."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/repeticiones-entre-sorteos",
        "pagina_colorloto_activa": "repeticiones-entre-sorteos",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/repeticiones_entre_sorteos_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="repeticiones_entre_sorteos_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": juego.rango_min, "rango_max": juego.rango_max, "cantidad_numeros": juego.cantidad_numeros,
        },
    )

    vm = repeticiones_entre_sorteos_colorloto_a_vm(resultado, juego.rango_min, juego.rango_max, juego.cantidad_numeros, juego)
    tiene_transiciones = vm["total_transiciones"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/repeticiones_entre_sorteos_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_transiciones": tiene_transiciones},
    )


@router.get("/estadisticas/colorloto/distribucion-pares-impares")
def distribucion_pares_impares_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-8: octava visualización descriptiva de ColorLoto
    -cuántos de los 6 números de las balotas de cada sorteo son
    pares, ignorando color por completo. Reutiliza
    `calcular_distribucion_pares_impares_colorloto` sin
    modificarlo.

    Ruta registrada OBLIGATORIAMENTE antes de la ruta genérica
    homonima `/estadisticas/{juego_slug}/distribucion-pares-impares`
    -ambas comparten exactamente el mismo sufijo; si el orden
    fuera incorrecto, Starlette capturaria esta URL con el
    handler generico (`juego_slug='colorloto'`), que devolveria
    un 404 controlado via `_resolver_codigo` en vez de alcanzar
    este handler dedicado -mismo defecto critico ya corregido
    para atrasos-numeros/repeticiones-entre-sorteos (Etapas
    AE-4/AE-7). La ruta generica de Baloto
    (`/estadisticas/baloto/distribucion-pares-impares`) sigue
    intacta y respondiendo 200, sin ninguna interferencia.

    Identidad de cache con una sola clave (`cantidad_numeros`),
    sin rango ni marcador de politica de colores: el motor
    ignora el color por completo, y el resultado de paridad
    nunca depende de los limites del rango -solo la validacion
    de integridad previa los necesita, usando el rango real y
    fijo de ColorLoto."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/distribucion-pares-impares",
        "pagina_colorloto_activa": "distribucion-pares-impares",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_pares_impares_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_pares_impares_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"cantidad_numeros": juego.cantidad_numeros},
    )

    vm = distribucion_pares_impares_colorloto_a_vm(resultado, juego.cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_pares_impares_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/distribucion-altos-bajos")
def distribucion_altos_bajos_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-9: novena visualización descriptiva de ColorLoto
    -cuántos de los 6 números de las balotas de cada sorteo son
    bajos (1..3, para el rango real 1..7), ignorando color por
    completo. Reutiliza `calcular_distribucion_altos_bajos_colorloto`
    sin modificarlo.

    Ruta registrada OBLIGATORIAMENTE antes de la ruta genérica
    homonima `/estadisticas/{juego_slug}/distribucion-altos-bajos`
    -ambas comparten exactamente el mismo sufijo; si el orden
    fuera incorrecto, Starlette capturaria esta URL con el
    handler generico (`juego_slug='colorloto'`), que devolveria
    un 404 controlado via `_resolver_codigo` en vez de alcanzar
    este handler dedicado -mismo defecto critico ya corregido
    para atrasos-numeros/repeticiones-entre-sorteos/distribucion-pares-impares
    (Etapas AE-4/AE-7/AE-8). La ruta generica de Baloto
    (`/estadisticas/baloto/distribucion-altos-bajos`) sigue
    intacta y respondiendo 200, sin ninguna interferencia.

    Identidad de cache con TRES claves (`rango_min`, `rango_max`,
    `cantidad_numeros`), sin marcador de politica de colores: a
    diferencia de AE-8 (paridad, que no depende del rango), el
    umbral bajos/altos de esta metrica SI depende materialmente
    de `rango_min`/`rango_max` -confirmado en la auditoria y su
    adenda correctiva- por lo que ambos forman parte obligatoria
    de la identidad. El motor ignora el color por completo, por
    eso el marcador de politica queda excluido."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/distribucion-altos-bajos",
        "pagina_colorloto_activa": "distribucion-altos-bajos",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_altos_bajos_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_altos_bajos_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": juego.rango_min, "rango_max": juego.rango_max, "cantidad_numeros": juego.cantidad_numeros,
        },
    )

    vm = distribucion_altos_bajos_colorloto_a_vm(resultado, juego.rango_min, juego.rango_max, juego.cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_altos_bajos_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/maximo-repeticion-color")
def maximo_repeticion_color_por_sorteo_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-10 (PROVISIONAL): décima visualización
    descriptiva de ColorLoto -para cada sorteo, la mayor
    cantidad de balotas que comparten un mismo color. Reutiliza
    `calcular_maximo_repeticion_color_por_sorteo` sin
    modificarlo.

    Literal y exclusiva de ColorLoto -sin ruta genérica
    equivalente, ya que ningún juego numérico tiene el
    concepto de color; confirmado con simulación exacta del
    algoritmo de Starlette en la auditoría previa que ninguna
    ruta genérica actual la captura. Se registra agrupada junto
    a las demás rutas literales de ColorLoto por coherencia con
    el patrón establecido, no por necesidad de resolver una
    colisión real.

    Identidad de cache con UNA SOLA clave (`cantidad_numeros`),
    sin rango ni marcador de politica de colores -decisión M1,
    justificada con evidencia directa en la auditoría y su
    adenda correctiva."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/maximo-repeticion-color",
        "pagina_colorloto_activa": "maximo-repeticion-color",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/maximo_repeticion_color_por_sorteo_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="maximo_repeticion_color_por_sorteo_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"cantidad_numeros": juego.cantidad_numeros},
    )

    vm = maximo_repeticion_color_por_sorteo_colorloto_a_vm(resultado, juego.cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/maximo_repeticion_color_por_sorteo_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/distribucion-pares-consecutivos")
def distribucion_pares_consecutivos_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-11 (PROVISIONAL): undécima visualización descriptiva
    de ColorLoto -para cada sorteo, cuántos pares de números
    adyacentes (diferencia exactamente 1) hay entre los números de
    las balotas, ignorando el color por completo. Reutiliza
    `calcular_distribucion_pares_consecutivos_colorloto` sin
    modificarlo.

    Ruta registrada OBLIGATORIAMENTE antes de la ruta genérica
    homónima `/estadisticas/{juego_slug}/distribucion-pares-consecutivos`
    -ambas comparten exactamente el mismo sufijo; si el orden fuera
    incorrecto, Starlette capturaría esta URL con el handler genérico
    (`juego_slug='colorloto'`), que devolvería un 404 controlado vía
    `_resolver_codigo` en vez de alcanzar este handler dedicado -mismo
    defecto crítico ya corregido para frecuencia-numeros/atrasos-numeros/
    repeticiones-entre-sorteos/distribucion-pares-impares/distribucion-altos-bajos
    (Etapas AE-1/AE-4/AE-7/AE-8/AE-9), confirmado con simulación real
    del motor de enrutamiento de Starlette en la adenda correctiva de
    la auditoría. La ruta genérica de Baloto/Baloto Revancha/MiLoto
    (`/estadisticas/{baloto,baloto-revancha,miloto}/distribucion-pares-consecutivos`)
    sigue intacta y respondiendo 200, sin ninguna interferencia.

    Identidad de caché con UNA SOLA clave (`cantidad_numeros`), sin
    rango ni marcador de política de colores -decisión M1, confirmada
    con evidencia directa (caracterización real) en la auditoría y su
    adenda correctiva: el motor exige `rango_min`/`rango_max` como
    argumentos posicionales, pero únicamente para su validación
    interna -el conteo de pares consecutivos y las categorías nunca
    dependen de esos límites."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/distribucion-pares-consecutivos",
        "pagina_colorloto_activa": "distribucion-pares-consecutivos",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_pares_consecutivos_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_pares_consecutivos_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"cantidad_numeros": juego.cantidad_numeros},
    )

    vm = distribucion_pares_consecutivos_colorloto_a_vm(resultado, juego.cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_pares_consecutivos_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/distribucion-racha-maxima")
def distribucion_racha_maxima_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-12 (PROVISIONAL): duodécima visualización descriptiva
    de ColorLoto -para cada sorteo, la longitud de su mayor racha de
    números consecutivos (diferencia exactamente 1), ignorando el
    color por completo. Reutiliza
    `calcular_distribucion_racha_maxima_colorloto` sin modificarlo.

    Ruta registrada OBLIGATORIAMENTE antes de la ruta genérica
    homónima `/estadisticas/{juego_slug}/distribucion-racha-maxima`
    -ambas comparten exactamente el mismo sufijo; si el orden fuera
    incorrecto, Starlette capturaría esta URL con el handler genérico
    (`juego_slug='colorloto'`), que devolvería un 404 controlado vía
    `_resolver_codigo` en vez de alcanzar este handler dedicado -mismo
    defecto crítico ya corregido para frecuencia-numeros/atrasos-numeros/
    repeticiones-entre-sorteos/distribucion-pares-impares/distribucion-altos-bajos/
    distribucion-pares-consecutivos (Etapas AE-1/AE-4/AE-7/AE-8/AE-9/AE-11),
    confirmado con simulación del motor real de enrutamiento de
    Starlette en la auditoría de AE-12. La ruta genérica de Baloto/Baloto
    Revancha/MiLoto (`/estadisticas/{baloto,baloto-revancha,miloto}/distribucion-racha-maxima`)
    sigue intacta y respondiendo 200, sin ninguna interferencia.

    Identidad de caché con UNA SOLA clave (`cantidad_numeros`), sin
    rango ni marcador de política de colores -decisión M1, confirmada
    con evidencia directa (caracterización real) en la auditoría de
    AE-12: el motor exige `rango_min`/`rango_max` como argumentos
    posicionales, pero únicamente para su validación interna -la
    longitud de la racha máxima y las categorías nunca dependen de
    esos límites. Categorías fijas 1..6, sin la categoría 0 (el
    propio motor la filtra: un sorteo con al menos un número siempre
    tiene una racha de longitud mínima 1)."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/distribucion-racha-maxima",
        "pagina_colorloto_activa": "distribucion-racha-maxima",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_racha_maxima_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_racha_maxima_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"cantidad_numeros": juego.cantidad_numeros},
    )

    vm = distribucion_racha_maxima_colorloto_a_vm(resultado, juego.cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_racha_maxima_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/distribucion-trios-consecutivos")
def distribucion_trios_consecutivos_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-13 (PROVISIONAL): decimotercera visualización
    descriptiva de ColorLoto -para cada sorteo, cuántos tríos de
    números consecutivos (tres números adyacentes con diferencia
    exactamente 1 entre cada par) hay entre los números de las
    balotas, ignorando el color por completo. Reutiliza
    `calcular_distribucion_trios_consecutivos_colorloto` sin
    modificarlo.

    A DIFERENCIA de las Etapas AE-1/AE-4/AE-7/AE-8/AE-9/AE-11/AE-12,
    esta ruta NO colisiona con ninguna ruta genérica: confirmado por
    la auditoría de AE-13 (simulación con el motor real de
    `starlette.routing.Route`) que
    `/estadisticas/{juego_slug}/distribucion-trios-consecutivos` NO
    existe entre las rutas registradas -ni el motor numérico
    (`calcular_distribucion_trios_consecutivos`) fue nunca conectado
    a `_CATALOGO` para ningún juego numérico. Baloto,
    `baloto-revancha` y MiLoto con este sufijo deben seguir
    resolviendo a 404 nativo de FastAPI (ausencia de match), sin
    ningún handler que los intercepte. Se registra igualmente dentro
    del bloque literal de ColorLoto, antes del bloque genérico, por
    prudencia y consistencia con el patrón establecido -mismo
    criterio ya aplicado a `maximo-repeticion-color` (Etapa AE-10),
    la única otra ruta de ColorLoto sin colisión real.

    Identidad de caché con UNA SOLA clave (`cantidad_numeros`), sin
    rango ni marcador de política de colores -decisión M1, confirmada
    con evidencia directa (caracterización real) en la auditoría de
    AE-13: el motor exige `rango_min`/`rango_max` como argumentos
    posicionales, pero únicamente para su validación interna -la
    cantidad de tríos consecutivos y las categorías nunca dependen de
    esos límites. Categorías fijas 0..4 (a diferencia de AE-12, esta
    métrica SÍ incluye la categoría 0: un sorteo sin ningún trío
    consecutivo es un valor real y posible, mismo criterio que AE-11).
    Los tríos superpuestos se cuentan por separado -una racha de
    longitud 4 aporta 2 tríos, confirmado por caracterización real."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/distribucion-trios-consecutivos",
        "pagina_colorloto_activa": "distribucion-trios-consecutivos",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_trios_consecutivos_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_trios_consecutivos_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"cantidad_numeros": juego.cantidad_numeros},
    )

    vm = distribucion_trios_consecutivos_colorloto_a_vm(resultado, juego.cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_trios_consecutivos_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/coocurrencia-pares")
def coocurrencia_pares_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-14 (PROVISIONAL): decimocuarta visualización
    descriptiva de ColorLoto -para el histórico analizado, qué pares
    de números (dos números distintos presentes en el mismo sorteo,
    deduplicados antes de formar el par) coocurrieron y con qué
    soporte (cantidad de sorteos que los contienen), ignorando el
    color por completo. Reutiliza `calcular_coocurrencia_pares_colorloto`
    sin modificarlo.

    A DIFERENCIA de toda visualización anterior de ColorLoto, esta
    NO es una distribución categórica por sorteo -es una tabla de
    asociaciones observadas entre pares de números, agregada sobre
    TODO el histórico analizado. Por eso, a diferencia de las trece
    páginas anteriores, esta página no usa gráfica de barras ni
    `<canvas>`: el motor reporta ÚNICAMENTE pares observados al menos
    una vez (nunca completa el universo teórico con soporte cero,
    comportamiento ya documentado en `motor/coocurrencia.py`, no
    modificado aquí), y una tabla es la presentación correcta para
    ese tipo de resultado -forzar una gráfica de barras habría sido
    una decisión de presentación arbitraria no respaldada por la
    forma real de los datos, confirmado en la auditoría de AE-14.
    Para ColorLoto (7 números posibles), el máximo teórico es
    C(7,2)=21 pares -manejable sin paginación ni top-N.

    Igual que `maximo-repeticion-color` (Etapa AE-10) y
    `distribucion-trios-consecutivos` (Etapa AE-13), esta ruta NO
    colisiona con ninguna ruta genérica -confirmado por la auditoría
    de AE-14 (simulación con el motor real de `starlette.routing.Route`)
    que `/estadisticas/{juego_slug}/coocurrencia-pares` no existe
    entre las rutas registradas, ni siquiera para el motor numérico
    equivalente (`calcular_coocurrencia_pares`, nunca conectado a
    `_CATALOGO` para ningún juego numérico). Baloto, `baloto-revancha`
    y MiLoto con este sufijo deben seguir resolviendo a 404 nativo de
    FastAPI (ausencia de match), sin ningún handler que los
    intercepte.

    Identidad de caché con el diccionario VACÍO `{}` -decisión
    consciente, no una omisión: confirmado por lectura directa del
    cuerpo real del motor y por caracterización real en la auditoría
    de AE-14 que `cantidad_balotas` aparece en la firma del motor
    pero JAMÁS se usa matemáticamente, y que `rango_min`/`rango_max`
    solo alimentan la validación interna del motor (mismo resultado
    bajo tres rangos distintos, verificado empíricamente) -ningún
    parámetro define la identidad matemática de este resultado.
    `frecuencia_esperada` y `lift` quedan siempre en `None` para
    ColorLoto (modelo de repetición del dominio sin verificar, ver
    docstring del motor) -esta página nunca inventa un valor de
    reemplazo ni presenta esos campos como si fueran cero."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/coocurrencia-pares",
        "pagina_colorloto_activa": "coocurrencia-pares",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/coocurrencia_pares_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="coocurrencia_pares_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={},
    )

    vm = coocurrencia_pares_colorloto_a_vm(resultado, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/coocurrencia_pares_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/coocurrencia-trios")
def coocurrencia_trios_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-15 (PROVISIONAL): decimoquinta visualización
    descriptiva de ColorLoto -para el histórico analizado, qué
    tríos de números (tres números distintos presentes en el mismo
    sorteo, deduplicados antes de formar el trío) coocurrieron y con
    qué soporte (cantidad de sorteos que los contienen), ignorando el
    color por completo. Reutiliza `calcular_coocurrencia_trios_colorloto`
    sin modificarlo, mismo patrón exacto que `coocurrencia-pares`
    (AE-14).

    Igual que `coocurrencia-pares`, esta página no usa gráfica de
    barras ni `<canvas>`: el motor reporta ÚNICAMENTE tríos observados
    al menos una vez (nunca completa el universo teórico con soporte
    cero), y una tabla es la presentación correcta. Para ColorLoto
    (7 números posibles), el máximo teórico es C(7,3)=35 tríos
    -manejable sin paginación ni top-N.

    Esta ruta NO colisiona con ninguna ruta genérica -mismo
    precedente exacto que `coocurrencia-pares`: `/estadisticas/
    {juego_slug}/coocurrencia-trios` no existe entre las rutas
    registradas. Baloto, `baloto-revancha` y MiLoto con este sufijo
    deben seguir resolviendo a 404 nativo de FastAPI (ausencia de
    match), sin ningún handler que los intercepte.

    Identidad de caché con el diccionario VACÍO `{}` -mismo criterio
    exacto que AE-14: ningún parámetro define la identidad
    matemática de este resultado. `frecuencia_esperada` y `lift`
    quedan siempre en `None` para ColorLoto -esta página nunca
    inventa un valor de reemplazo ni presenta esos campos como si
    fueran cero."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/coocurrencia-trios",
        "pagina_colorloto_activa": "coocurrencia-trios",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/coocurrencia_trios_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="coocurrencia_trios_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={},
    )

    vm = coocurrencia_trios_colorloto_a_vm(resultado, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/coocurrencia_trios_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/coocurrencia-pares-colores")
def coocurrencia_pares_colores_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-16 (PROVISIONAL): decimosexta visualización
    descriptiva de ColorLoto -para el histórico analizado, qué
    pares de CÓDIGOS DE COLOR (dos colores distintos presentes en
    el mismo sorteo, deduplicados antes de formar el par) coocurrieron
    y con qué soporte (cantidad de sorteos que los contienen).
    Reutiliza `calcular_coocurrencia_pares_colores` sin modificarlo,
    candidata aprobada por la auditoría previa (Decisión A).

    A DIFERENCIA de `coocurrencia-pares` (AE-14) y `coocurrencia-trios`
    (AE-15), que ignoran el color y calculan sobre los NÚMEROS, esta
    página ignora los NÚMEROS por completo y calcula sobre los
    CÓDIGOS DE COLOR -mismo patrón exacto de tabla de asociaciones,
    sin `<canvas>` ni Chart.js: el motor reporta ÚNICAMENTE pares de
    colores observados al menos una vez (nunca completa el universo
    teórico con soporte cero). El máximo de filas depende del
    universo histórico real de códigos de color -la auditoría previa
    confirmó que la paleta NO está hardcodeada a 6 colores (puede
    cambiar con el reglamento), así que esta página nunca asume ni
    fuerza un límite de C(6,2)=21 filas: muestra dinámicamente todo
    lo que el motor devuelva.

    Esta ruta NO colisiona con ninguna ruta genérica -mismo
    precedente exacto que `coocurrencia-pares`/`coocurrencia-trios`:
    `/estadisticas/{juego_slug}/coocurrencia-pares-colores` no existe
    entre las rutas registradas. Baloto, `baloto-revancha` y MiLoto
    con este sufijo deben seguir resolviendo a 404 nativo de FastAPI
    (ausencia de match), sin ningún handler que los intercepte.

    Identidad de caché con el diccionario VACÍO `{}` -mismo criterio
    exacto que AE-14/AE-15, esta vez demostrado por la auditoría
    previa: la función del motor no acepta ningún parámetro de
    rango, cantidad ni catálogo de colores, así que ningún parámetro
    define la identidad matemática de este resultado.
    `frecuencia_esperada` y `lift` quedan siempre en `None` -esta
    página nunca inventa un valor de reemplazo ni presenta esos
    campos como si fueran cero.

    A DIFERENCIA de `coocurrencia-pares`/`coocurrencia-trios`, esta
    receta serializa con `_serializar_metrica_asociacion_texto`
    (nueva en esta etapa) en vez de `_serializar_metrica_asociacion`
    -los elementos de esta métrica son códigos de color (`str`),
    nunca convertibles a `int` sin perder la información real."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/coocurrencia-pares-colores",
        "pagina_colorloto_activa": "coocurrencia-pares-colores",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/coocurrencia_pares_colores_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="coocurrencia_pares_colores_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={},
    )

    vm = coocurrencia_pares_colores_colorloto_a_vm(resultado, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/coocurrencia_pares_colores_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/coocurrencia-trios-colores")
def coocurrencia_trios_colores_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-17 (PROVISIONAL): decimoséptima visualización
    descriptiva de ColorLoto -para el histórico analizado, qué
    tríos de CÓDIGOS DE COLOR (tres colores distintos presentes en
    el mismo sorteo, deduplicados antes de formar el trío)
    coocurrieron y con qué soporte. Reutiliza
    `calcular_coocurrencia_trios_colores` sin modificarlo, candidata
    aprobada por la auditoría previa (Decisión A).

    Mismo patrón exacto que `coocurrencia-pares-colores` (AE-16),
    esta vez con tamaño de combinación 3. Tabla de asociaciones (sin
    `<canvas>` ni Chart.js): el motor reporta ÚNICAMENTE tríos de
    colores observados al menos una vez. La auditoría previa
    demostró con un histórico sintético de siete códigos que el
    número global de filas puede superar 20 (el máximo teórico de
    UN sorteo con seis colores) -esta página nunca impone ese
    número como límite fijo, muestra dinámicamente todo lo que el
    motor devuelva.

    Esta ruta NO colisiona con ninguna ruta genérica -mismo
    precedente exacto que las tres coocurrencias anteriores:
    `/estadisticas/{juego_slug}/coocurrencia-trios-colores` no
    existe entre las rutas registradas.

    Identidad de caché con el diccionario VACÍO `{}` -mismo criterio
    exacto que AE-14/AE-15/AE-16, demostrado por la auditoría
    previa: la función del motor no acepta ningún parámetro de
    rango, cantidad ni catálogo de colores.

    Reutiliza `_serializar_metrica_asociacion_texto` (Etapa AE-16)
    SIN NINGÚN CAMBIO -su comprensión de lista genérica acepta tres
    elementos exactamente igual que dos, confirmado por la auditoría
    previa mediante ejecución real."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/coocurrencia-trios-colores",
        "pagina_colorloto_activa": "coocurrencia-trios-colores",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/coocurrencia_trios_colores_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="coocurrencia_trios_colores_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={},
    )

    vm = coocurrencia_trios_colores_colorloto_a_vm(resultado, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/coocurrencia_trios_colores_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/intervalos-historicos-colores")
def intervalos_historicos_colores_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-18 (PROVISIONAL): decimoctava visualización
    descriptiva de ColorLoto -para el histórico analizado, los
    estadísticos descriptivos de TODOS los intervalos históricos
    entre apariciones consecutivas de cada color (mínimo, máximo,
    promedio, mediana), ignorando los números de las balotas por
    completo. Reutiliza `calcular_intervalos_historicos_colores` sin
    modificarlo, candidata aprobada por la auditoría previa (Decisión
    A, corregida).

    A diferencia de las coocurrencias (AE-14 a AE-17), esta receta SÍ
    deriva `colores_vigentes` -mismo patrón exacto ya validado por
    AE-5 (`_codigos_colores_vigentes_en_referencia`), unión de
    colores vigentes en la fecha del último sorteo real más
    cualquier color retirado realmente observado. Identidad de caché
    `{"politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`
    -demostrada por la auditoría previa: el motor no recibe ningún
    parámetro de rango/cantidad (a diferencia del motor de atrasos de
    AE-5), así que esas claves serían redundantes aquí; la política
    sí debe formar parte de la identidad porque versiona el algoritmo
    de derivación de `colores_vigentes`, no los datos en sí.

    Reutiliza `_serializar_atrasos` (Etapa AE-4, protegida) sin
    ningún cambio -confirmado por hash AST idéntico antes/después de
    esta etapa; `dataclasses.asdict` es genérico sobre cualquier
    dataclass, incluida la tupla `intervalos` de `IntervalosHistoricos`
    (se serializa como array JSON automáticamente).

    Tabla y gráfica -mismo patrón que AE-5 (`atrasos-colores`), no
    tabla pura como AE-14 a AE-17: cada color tiene múltiples
    estadísticos numéricos, y una barra del intervalo promedio por
    color complementa la tabla completa. Sin ninguna ruta genérica
    equivalente."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/intervalos-historicos-colores",
        "pagina_colorloto_activa": "intervalos-historicos-colores",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/intervalos_historicos_colores_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="intervalos_historicos_colores_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL},
    )

    vm = intervalos_historicos_colores_colorloto_a_vm(resultado, juego)
    tiene_sorteos = vm["cantidad_colores_analizados"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/intervalos_historicos_colores_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/distribucion-sumas")
def distribucion_sumas_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-19 (PROVISIONAL): decimonovena visualización
    descriptiva de ColorLoto -para el histórico analizado, los
    estadísticos descriptivos (mínimo, máximo, media, mediana,
    desviación estándar, percentiles P10/P25/P50/P75/P90) de la
    suma de los NÚMEROS de las 6 balotas de cada sorteo, ignorando
    el color por completo. Reutiliza `calcular_distribucion_sumas_colorloto`
    sin modificarlo, candidata aprobada tras dos auditorías previas
    (Decisión C: se pospuso `calcular_distribucion_conteo_color`
    -requiere una decisión de producto sobre selector de color sin
    ningún precedente real; no se implementa ningún selector ni
    receta agregadora aquí).

    Identidad de caché **diccionario VACÍO `{}`** -demostrada por
    ejecución real en la auditoría previa: el motor no recibe ningún
    parámetro de rango, cantidad, catálogo ni selector de color.

    A diferencia de las 27 páginas anteriores, esta página presenta
    **tarjetas y gráfica** -`DistribucionSumas` es un objeto único
    con varios estadísticos escalares (tarjetas) más 5 percentiles
    que sí forman una serie categórica (barra), no una lista de
    filas que tabular. Reutiliza `_serializar_distribucion_sumas`
    (nuevo, ver el caso de uso) y `_num_o_none` (Etapa AE-18,
    reutilizado sin ningún cambio)."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/distribucion-sumas",
        "pagina_colorloto_activa": "distribucion-sumas",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_sumas_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_sumas_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={},
    )

    vm = distribucion_sumas_colorloto_a_vm(resultado, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_sumas_colorloto.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/colorloto/intervalos-historicos-numeros")
def intervalos_historicos_numeros_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-20 (PROVISIONAL): vigésima visualización descriptiva
    de ColorLoto -para cada número (1 a 7), estadísticos descriptivos
    de TODOS los intervalos históricos entre apariciones consecutivas
    (cuántos sorteos separaron una aparición de la siguiente),
    ignorando el color por completo. Reutiliza
    `calcular_intervalos_historicos_numeros_colorloto` sin
    modificarlo, candidata aprobada tras tres auditorías previas.

    A diferencia de AE-14/AE-15/AE-16/AE-17/AE-19 (identidad `{}`),
    este motor SÍ construye su universo de filas directamente desde
    `rango_min`/`rango_max` (`range(rango_min, rango_max+1)`) -mismo
    criterio real ya demostrado por `frecuencia_numeros_colorloto`
    (AE-1) y `atrasos_numeros_colorloto` (AE-4). Por eso la identidad
    de esta etapa SÍ incluye `rango_min`/`rango_max`, tomados de la
    entidad `Juego` real (nunca de una constante privada del caso de
    uso, que no está importada aquí) -mismo patrón exacto ya usado
    por las rutas de AE-1/AE-4/AE-6. `cantidad_numeros` NO forma
    parte de la identidad: el motor de esta etapa no la recibe en
    absoluto, solo se usa dentro de la receta para validación
    defensiva."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/intervalos-historicos-numeros",
        "pagina_colorloto_activa": "intervalos-historicos-numeros",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/intervalos_historicos_numeros_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    rango_min, rango_max = juego.rango_min, juego.rango_max

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="intervalos_historicos_numeros_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": rango_min,
            "rango_max": rango_max,
        },
    )

    vm = intervalos_historicos_numeros_colorloto_a_vm(resultado, rango_min, rango_max, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/intervalos_historicos_numeros_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/intervalos-historicos-pares-numero-color")
def intervalos_historicos_pares_numero_color_colorloto(
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-21 (PROVISIONAL): vigésima primera visualización
    descriptiva de ColorLoto -para cada PAR (número, color) como
    unidad atómica, estadísticos descriptivos de TODOS los
    intervalos históricos entre apariciones consecutivas del par
    completo. Reutiliza `calcular_intervalos_historicos_pares_numero_color`
    sin modificarlo, candidata aprobada tras auditoría exhaustiva
    post-AE-20 (Decisión: se pospone `calcular_distribucion_conteo_color`
    -sigue exigiendo un selector de color explícito sin ningún
    precedente real; no se implementa ningún selector aquí).

    A diferencia de AE-20 (identidad solo con rango), este motor
    construye su universo con el producto cartesiano
    `range(rango_min, rango_max+1) × colores_a_reportar`, por lo que
    la identidad incluye TANTO el rango COMO la política de universo
    de colores -combinación real de los criterios ya demostrados por
    AE-20 (rango) y AE-5/AE-18 (política de colores)."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "url_historico_completo": "/estadisticas/colorloto/intervalos-historicos-pares-numero-color",
        "pagina_colorloto_activa": "intervalos-historicos-pares-numero-color",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/intervalos_historicos_pares_numero_color_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    rango_min, rango_max = juego.rango_min, juego.rango_max

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="intervalos_historicos_pares_numero_color_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "rango_min": rango_min,
            "rango_max": rango_max,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = intervalos_historicos_pares_numero_color_colorloto_a_vm(resultado, rango_min, rango_max, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/intervalos_historicos_pares_numero_color_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/frecuencia-colores-por-anio")
def frecuencia_colores_por_anio_colorloto(
    request: Request,
    anio: int | None = Query(default=None, ge=1, le=9999),
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-22 (PROVISIONAL): vigesimosegunda visualización
    descriptiva de ColorLoto -frecuencia de colores restringida a un
    año elegido por el usuario. Primera página de ColorLoto con un
    control de interfaz adicional al corte temporal, decisión de
    producto autorizada explícitamente tras la auditoría exhaustiva
    de las diez candidatas pendientes (ninguna otra podía resolverse
    sin selector o sin un agregador de motor en bucle, ambos sin
    precedente real en las 30 recetas ya conectadas).

    Sin `anio`: responde `200` mostrando únicamente el selector, sin
    ejecutar el orquestador, sin invocar el motor, sin consultar ni
    persistir ninguna caché -nunca se elige automáticamente un año
    "actual" ni "el último con datos" (decisión de producto explícita:
    cualquier valor por defecto sería arbitrario y quedaría obsoleto).
    Con `anio` fuera de `1..9999`: `422` nativo de FastAPI, antes de
    que el handler se ejecute. Con `anio` válido, incluso sin sorteos
    ese año: `200` con el universo completo de colores en cero -nunca
    un `404`, un año sin sorteos es un resultado descriptivo válido,
    no una ausencia de recurso.

    Reutiliza `calcular_frecuencia_colores_por_anio` sin modificarlo.
    Identidad `{"anio": anio, "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`
    -solo existe cuando hay año seleccionado; `anio` cambia
    matemáticamente el resultado (determina el subconjunto exacto
    analizado), por lo que forma parte de la identidad, a diferencia
    de `hasta_numero_sorteo`, que permanece en su propia columna."""
    db_conectada = _verificar_conexion(db)

    # Extensión de bidireccionalidad: "Histórico completo" limpia el
    # corte pero preserva el año ya seleccionado -el valor viene
    # siempre validado como entero por FastAPI (Query(ge=1, le=9999)),
    # nunca texto sin validar, por lo que construirlo aquí con un
    # f-string es seguro (no hay concatenación de HTML ni entrada de
    # usuario sin tipar involucrada).
    url_historico_completo = "/estadisticas/colorloto/frecuencia-colores-por-anio"
    if anio is not None:
        url_historico_completo = f"{url_historico_completo}?anio={anio}"

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "anio": anio,
        "url_historico_completo": url_historico_completo,
        "pagina_colorloto_activa": "frecuencia-colores-por-anio",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_colores_por_anio_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    if anio is None:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_colores_por_anio_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_colores_por_anio_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "anio": anio,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = frecuencia_colores_por_anio_colorloto_a_vm(resultado, anio, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_colores_por_anio_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/frecuencia-colores-por-mes")
def frecuencia_colores_por_mes_colorloto(
    request: Request,
    mes: int | None = Query(default=None, ge=1, le=12),
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-23 (PROVISIONAL): vigesimotercera visualización
    descriptiva de ColorLoto -frecuencia de colores restringida a un
    mes calendario elegido por el usuario, agregado a través de
    TODOS los años del histórico. Mismo precedente de selector ya
    validado por AE-22 (año), decisión de producto reutilizada
    explícitamente: "mes" combina el mismo mes calendario (p. ej.
    enero) de cada año disponible, nunca un año-mes concreto.

    Sin `mes`: responde `200` mostrando únicamente el selector, sin
    ejecutar el orquestador, sin invocar el motor, sin consultar ni
    persistir ninguna caché -nunca se elige automáticamente el mes
    actual (decisión de producto explícita: cualquier valor por
    defecto sería arbitrario). Con `mes` fuera de `1..12`: `422`
    nativo de FastAPI, antes de que el handler se ejecute. Con `mes`
    válido, incluso sin sorteos ese mes en ningún año: `200` con el
    universo completo de colores en cero -nunca un `404`.

    Reutiliza `calcular_frecuencia_colores_por_mes` sin modificarlo.
    Identidad `{"mes": mes, "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`
    -solo existe cuando hay mes seleccionado; `mes` cambia
    matemáticamente el resultado (determina el subconjunto exacto
    analizado), por lo que forma parte de la identidad, a diferencia
    de `hasta_numero_sorteo`, que permanece en su propia columna.
    Esta página nunca coloca `anio` en su contexto -ninguna página
    propaga simultáneamente `anio` y `mes`."""
    db_conectada = _verificar_conexion(db)

    # Misma extensión de bidireccionalidad ya validada por AE-22:
    # "Histórico completo" limpia el corte pero preserva el mes ya
    # seleccionado -el valor viene siempre validado como entero por
    # FastAPI (Query(ge=1, le=12)), nunca texto sin validar, por lo
    # que construirlo aquí con un f-string es seguro.
    url_historico_completo = "/estadisticas/colorloto/frecuencia-colores-por-mes"
    if mes is not None:
        url_historico_completo = f"{url_historico_completo}?mes={mes}"

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "mes": mes,
        "url_historico_completo": url_historico_completo,
        "pagina_colorloto_activa": "frecuencia-colores-por-mes",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_colores_por_mes_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    if mes is None:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_colores_por_mes_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_colores_por_mes_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "mes": mes,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = frecuencia_colores_por_mes_colorloto_a_vm(resultado, mes, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_colores_por_mes_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/frecuencia-colores-por-dia-semana")
def frecuencia_colores_por_dia_semana_colorloto(
    request: Request,
    dia_semana: Literal["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"] | None = Query(default=None),
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-24 (PROVISIONAL): vigesimocuarta visualización
    descriptiva de ColorLoto -frecuencia de colores restringida a un
    día de la semana elegido por el usuario, agregado a través de
    TODOS los meses y años del histórico. Mismo precedente de
    selector ya validado por AE-22 (año) y AE-23 (mes), decisión de
    producto reutilizada explícitamente: "día de la semana" combina
    ese mismo día calendario (p. ej. todos los lunes) de cada mes y
    año disponible, nunca una fecha concreta.

    Dominio real confirmado por auditoría (código real, no asumido):
    `dia_semana` es un STRING literal en español, minúsculas, SIN
    tildes -`{"lunes","martes","miercoles","jueves","viernes","sabado","domingo"}`,
    NUNCA un entero `0..6` ni `1..7` -mismo dominio exacto ya
    almacenado en `ResultadoColorLoto.dia_semana` (poblado una única
    vez, al registrar o editar un sorteo, con `DIAS_SEMANA_ES[fecha.weekday()]`).
    `Literal[...]` produce `422` nativo de FastAPI para cualquier
    valor fuera de esas siete cadenas exactas, sin necesidad de
    `ge`/`le` (que solo aplican a tipos numéricos, no al dominio real
    de esta etapa).

    Sin `dia_semana`: responde `200` mostrando únicamente el
    selector, sin ejecutar el orquestador, sin invocar el motor, sin
    consultar ni persistir ninguna caché -nunca se elige
    automáticamente el día actual (decisión de producto explícita).
    Con `dia_semana` válido, incluso sin sorteos ese día en ningún
    mes/año: `200` con el universo completo de colores en cero -nunca
    un `404`.

    Reutiliza `calcular_frecuencia_colores_por_dia_semana` sin
    modificarlo. Identidad `{"dia_semana": dia_semana, "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`
    -solo existe cuando hay día seleccionado; `dia_semana` cambia
    matemáticamente el resultado (determina el subconjunto exacto
    analizado), por lo que forma parte de la identidad, a diferencia
    de `hasta_numero_sorteo`, que permanece en su propia columna.
    Esta página nunca coloca `anio` ni `mes` en su contexto -ninguna
    página propaga simultáneamente más de uno entre `anio`, `mes` y
    `dia_semana`."""
    db_conectada = _verificar_conexion(db)

    # Misma extensión de bidireccionalidad ya validada por AE-22/AE-23:
    # "Histórico completo" limpia el corte pero preserva el día ya
    # seleccionado -el valor viene siempre validado por FastAPI como
    # uno de los siete literales exactos del dominio real (nunca
    # texto arbitrario sin validar), por lo que construirlo aquí con
    # un f-string es seguro.
    url_historico_completo = "/estadisticas/colorloto/frecuencia-colores-por-dia-semana"
    if dia_semana is not None:
        url_historico_completo = f"{url_historico_completo}?dia_semana={dia_semana}"

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "dia_semana": dia_semana,
        "url_historico_completo": url_historico_completo,
        "pagina_colorloto_activa": "frecuencia-colores-por-dia-semana",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_colores_por_dia_semana_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    if dia_semana is None:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_colores_por_dia_semana_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_colores_por_dia_semana_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "dia_semana": dia_semana,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = frecuencia_colores_por_dia_semana_colorloto_a_vm(resultado, dia_semana, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_colores_por_dia_semana_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/frecuencia-pares-numero-color-por-anio")
def frecuencia_pares_numero_color_por_anio_colorloto(
    request: Request,
    anio: int | None = Query(default=None, ge=1, le=9999),
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-25 (PROVISIONAL): vigesimoquinta visualización
    descriptiva de ColorLoto -frecuencia del PAR (número, color) como
    unidad atómica, restringida a un año elegido por el usuario.
    Mismo precedente exacto de selector ya validado por AE-22
    (año), aplicado esta vez sobre pares en lugar de colores.

    Sin `anio`: responde `200` mostrando únicamente el selector, sin
    ejecutar el orquestador, sin invocar el motor, sin consultar ni
    persistir ninguna caché -nunca se elige automáticamente un año
    (decisión de producto explícita). Con `anio` fuera de `1..9999`:
    `422` nativo de FastAPI, antes de que el handler se ejecute. Con
    `anio` válido, incluso sin sorteos ese año: `200` con el universo
    completo de pares en cero -nunca un `404`.

    Reutiliza `calcular_frecuencia_pares_numero_color_por_anio` sin
    modificarlo. Identidad
    `{"anio": anio, "rango_min": juego.rango_min, "rango_max": juego.rango_max, "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`
    -a diferencia de AE-22/AE-23/AE-24 (identidad solo con el
    selector + política de colores), este motor SÍ construye su
    universo con el producto cartesiano `rango × colores`, por lo que
    el rango forma parte de la identidad -mismo criterio ya
    demostrado por AE-20/AE-21, construido aquí desde `juego.rango_min`/
    `juego.rango_max` (la entidad real, nunca la constante privada
    `_RANGO_REAL_COLORLOTO`, inaccesible fuera del caso de uso).
    `anio` cambia matemáticamente el resultado (determina el
    subconjunto exacto analizado), por lo que también forma parte de
    la identidad, a diferencia de `hasta_numero_sorteo`, que
    permanece en su propia columna. Esta página nunca coloca `mes`
    ni `dia_semana` en su contexto -ninguna página propaga
    simultáneamente más de uno entre `anio`, `mes` y `dia_semana`."""
    db_conectada = _verificar_conexion(db)

    # Misma extensión de bidireccionalidad ya validada por AE-22:
    # "Histórico completo" limpia el corte pero preserva el año ya
    # seleccionado -el valor viene siempre validado como entero por
    # FastAPI (Query(ge=1, le=9999)), por lo que construirlo aquí con
    # un f-string es seguro.
    url_historico_completo = "/estadisticas/colorloto/frecuencia-pares-numero-color-por-anio"
    if anio is not None:
        url_historico_completo = f"{url_historico_completo}?anio={anio}"

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "anio": anio,
        "url_historico_completo": url_historico_completo,
        "pagina_colorloto_activa": "frecuencia-pares-numero-color-por-anio",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_pares_numero_color_por_anio_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    if anio is None:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_pares_numero_color_por_anio_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_pares_numero_color_por_anio_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "anio": anio,
            "rango_min": juego.rango_min,
            "rango_max": juego.rango_max,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = frecuencia_pares_numero_color_por_anio_colorloto_a_vm(resultado, anio, juego.rango_min, juego.rango_max, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_pares_numero_color_por_anio_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/frecuencia-pares-numero-color-por-mes")
def frecuencia_pares_numero_color_por_mes_colorloto(
    request: Request,
    mes: int | None = Query(default=None, ge=1, le=12),
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-26 (PROVISIONAL): vigesimosexta visualización
    descriptiva de ColorLoto -frecuencia del PAR (número, color) como
    unidad atómica, restringida a un mes calendario elegido por el
    usuario, agregado a través de TODOS los años del histórico.
    Mismo precedente de selector ya validado por AE-23 (mes, sobre
    colores) y AE-25 (pares, sobre año), combinado aquí.

    Sin `mes`: responde `200` mostrando únicamente el selector, sin
    ejecutar el orquestador, sin invocar el motor, sin consultar ni
    persistir ninguna caché -nunca se elige automáticamente el mes
    actual (decisión de producto explícita). Con `mes` fuera de
    `1..12`: `422` nativo de FastAPI, antes de que el handler se
    ejecute. Con `mes` válido, incluso sin sorteos ese mes en ningún
    año: `200` con el universo completo de 42 pares en cero -nunca
    un `404`.

    Reutiliza `calcular_frecuencia_pares_numero_color_por_mes` sin
    modificarlo. Identidad
    `{"mes": mes, "rango_min": juego.rango_min, "rango_max": juego.rango_max, "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`
    -mismo criterio de AE-25 (no AE-22/AE-23/AE-24): este motor SÍ
    construye su universo con el producto cartesiano `rango ×
    colores`, por lo que el rango forma parte de la identidad,
    construido aquí desde `juego.rango_min`/`juego.rango_max` (la
    entidad real, nunca la constante privada `_RANGO_REAL_COLORLOTO`,
    inaccesible fuera del caso de uso). `mes` cambia matemáticamente
    el resultado (determina el subconjunto exacto analizado), por lo
    que también forma parte de la identidad, a diferencia de
    `hasta_numero_sorteo`, que permanece en su propia columna. Esta
    página nunca coloca `anio` ni `dia_semana` en su contexto
    -ninguna página propaga simultáneamente más de uno entre `anio`,
    `mes` y `dia_semana`."""
    db_conectada = _verificar_conexion(db)

    # Misma extensión de bidireccionalidad ya validada por AE-23:
    # "Histórico completo" limpia el corte pero preserva el mes ya
    # seleccionado -el valor viene siempre validado como entero por
    # FastAPI (Query(ge=1, le=12)), por lo que construirlo aquí con
    # un f-string es seguro.
    url_historico_completo = "/estadisticas/colorloto/frecuencia-pares-numero-color-por-mes"
    if mes is not None:
        url_historico_completo = f"{url_historico_completo}?mes={mes}"

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "mes": mes,
        "url_historico_completo": url_historico_completo,
        "pagina_colorloto_activa": "frecuencia-pares-numero-color-por-mes",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_pares_numero_color_por_mes_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    if mes is None:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_pares_numero_color_por_mes_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_pares_numero_color_por_mes_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "mes": mes,
            "rango_min": juego.rango_min,
            "rango_max": juego.rango_max,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = frecuencia_pares_numero_color_por_mes_colorloto_a_vm(resultado, mes, juego.rango_min, juego.rango_max, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_pares_numero_color_por_mes_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/frecuencia-pares-numero-color-por-dia-semana")
def frecuencia_pares_numero_color_por_dia_semana_colorloto(
    request: Request,
    dia_semana: Literal["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"] | None = Query(default=None),
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-27 (PROVISIONAL): vigesimoséptima visualización
    descriptiva de ColorLoto -frecuencia del PAR (número, color) como
    unidad atómica, restringida a un día de la semana elegido por el
    usuario, agregado a través de TODOS los meses y años del
    histórico. Mismo precedente de selector ya validado por AE-24
    (día, sobre colores) y AE-25/AE-26 (pares, sobre año/mes),
    combinado aquí.

    Dominio real confirmado por auditoría (mismo dominio exacto ya
    usado por AE-24): string literal en español, minúsculas, sin
    tildes -`{"lunes","martes","miercoles","jueves","viernes","sabado","domingo"}`,
    NUNCA un entero. `Literal[...]` en el tipo del `Query` produce
    `422` nativo de FastAPI para el dominio real, sin `ge`/`le`.

    Sin `dia_semana`: responde `200` mostrando únicamente el
    selector, sin ejecutar el orquestador, sin invocar el motor, sin
    consultar ni persistir ninguna caché -nunca se elige
    automáticamente un día (decisión de producto explícita). Con
    `dia_semana` fuera del dominio real: `422` nativo de FastAPI,
    antes de que el handler se ejecute. Con `dia_semana` válido,
    incluso sin sorteos ese día en ningún mes/año: `200` con el
    universo completo de 42 pares en cero -nunca un `404`.

    Reutiliza `calcular_frecuencia_pares_numero_color_por_dia_semana`
    sin modificarlo. Identidad
    `{"dia_semana": dia_semana, "rango_min": juego.rango_min, "rango_max": juego.rango_max, "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`
    -mismo criterio de AE-25/AE-26 (no AE-22/AE-23/AE-24): este motor
    SÍ construye su universo con el producto cartesiano `rango ×
    colores`, por lo que el rango forma parte de la identidad,
    construido aquí desde `juego.rango_min`/`juego.rango_max` (la
    entidad real, nunca la constante privada `_RANGO_REAL_COLORLOTO`,
    inaccesible fuera del caso de uso). `dia_semana` cambia
    matemáticamente el resultado (determina el subconjunto exacto
    analizado), por lo que también forma parte de la identidad, a
    diferencia de `hasta_numero_sorteo`, que permanece en su propia
    columna. Esta página nunca coloca `anio` ni `mes` en su contexto
    -ninguna página propaga simultáneamente más de uno entre `anio`,
    `mes` y `dia_semana`."""
    db_conectada = _verificar_conexion(db)

    # Misma extensión de bidireccionalidad ya validada por AE-24:
    # "Histórico completo" limpia el corte pero preserva el día ya
    # seleccionado -el valor viene siempre validado por FastAPI como
    # uno de los siete literales exactos del dominio real (nunca
    # texto arbitrario sin validar), por lo que construirlo aquí con
    # un f-string es seguro.
    url_historico_completo = "/estadisticas/colorloto/frecuencia-pares-numero-color-por-dia-semana"
    if dia_semana is not None:
        url_historico_completo = f"{url_historico_completo}?dia_semana={dia_semana}"

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "dia_semana": dia_semana,
        "url_historico_completo": url_historico_completo,
        "pagina_colorloto_activa": "frecuencia-pares-numero-color-por-dia-semana",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_pares_numero_color_por_dia_semana_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    if dia_semana is None:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_pares_numero_color_por_dia_semana_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_pares_numero_color_por_dia_semana_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "dia_semana": dia_semana,
            "rango_min": juego.rango_min,
            "rango_max": juego.rango_max,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = frecuencia_pares_numero_color_por_dia_semana_colorloto_a_vm(resultado, dia_semana, juego.rango_min, juego.rango_max, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_pares_numero_color_por_dia_semana_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/distribucion-conteo-color")
def distribucion_conteo_color_colorloto(
    request: Request,
    color_objetivo: str | None = Query(default=None),
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    color_repository: ColorRepository = Depends(get_color_repository),
    historico_repo: ResultadosHistoricosRepository = Depends(get_resultados_historicos_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-28 (PROVISIONAL): vigesimooctava visualización
    descriptiva de ColorLoto -distribución de cuántas balotas de un
    color ELEGIDO POR EL USUARIO aparecen por sorteo, tabulado
    `0..cantidad_balotas`. Autorizada explícitamente tras una
    auditoría que se detuvo: `calcular_distribucion_conteo_color`
    exige `color_objetivo: str` obligatorio -primer selector de
    ColorLoto con dominio genuinamente DINÁMICO (códigos de color
    reales de la base de datos), a diferencia de `anio`/`mes`/
    `dia_semana`, cuyos dominios son estáticos y validables con
    `Query`/`Literal` nativos de FastAPI.

    **Universo seleccionable, construido en el router**: vigentes en
    la fecha de referencia (`_codigos_colores_vigentes_en_referencia`,
    protegida, sin cambios) UNIÓN observados dentro del corte
    (`{c for r in historico.pares for _, c in r.pares}`) -mismo
    criterio de unión ya usado internamente por los motores de AE-2/
    AE-3/AE-5/AE-18/AE-21 a AE-27, aplicado aquí para construir la
    lista de opciones del SELECTOR, no el universo del motor (que
    solo recibe UN color). Esto requiere que el router construya
    `historico` una vez para resolver el universo y validar/
    determinar el color efectivo ANTES de invocar al orquestador
    -que construye su propio `historico` internamente una segunda
    vez al ejecutar la receta-; es un costo arquitectónico honesto y
    documentado, específico de este primer selector con dominio
    dinámico: ningún selector anterior necesitaba consultar el
    histórico antes de invocar el orquestador, porque sus dominios
    ya eran validables de forma nativa por FastAPI.

    **Sin `color_objetivo` en la query string**: la página base
    responde igualmente con resultados reales -se elige
    automáticamente el PRIMERO en orden alfabético del universo
    seleccionable (mismo criterio de orden ya usado por
    `_codigos_colores_vigentes_en_referencia`, `sorted(...)`), regla
    determinista y documentada aquí explícitamente. Nunca se inventa
    un color: si el universo seleccionable está vacío (sin colores
    vigentes ni observados en el corte actual), la página responde
    `200` con un estado explícito de "sin colores disponibles",
    `estadistica=None`, sin invocar el orquestador.

    **`color_objetivo` inválido**: un valor que no coincide EXACTAMENTE
    (sin normalizar mayúsculas, tildes ni alias) con el universo
    seleccionable real produce `ColorNoVigenteError` -excepción de
    dominio protegida, ya existente y ya mapeada a HTTP `422` en
    `main.py`, nunca antes utilizada en el código real: mismo patrón
    HTTP ya establecido por el proyecto para entradas de usuario
    inválidas, sin necesitar ningún cambio a `exceptions.py` ni a
    `main.py`. El motor nunca se invoca y ninguna caché se persiste
    en este caso -confirmado por AST real: la comprobación de
    membresía ocurre antes de cualquier llamada a `.ejecutar`.

    **Identidad de caché con DOS claves, no tres**: `{"color_objetivo":
    <string>, "cantidad_balotas": <entero>}`. `cantidad_balotas` SÍ
    forma parte de la identidad (determina matemáticamente el
    universo `0..cantidad_balotas`, mismo criterio ya establecido por
    AE-20/AE-21/AE-25/AE-26/AE-27 para `rango_min`/`rango_max`),
    construida aquí desde `juego.cantidad_numeros` (la entidad real,
    nunca una constante privada). `politica_universo_colores` se
    EXCLUYE deliberadamente -a diferencia de AE-2/AE-3/AE-5/AE-18/
    AE-21 a AE-27, el motor de esta etapa no recibe ni consume esa
    política en ningún punto de su firma ni de su cuerpo (nunca
    construye un universo MULTI-color); el resultado cacheado depende
    matemáticamente solo de `(historico.pares filtrado por corte,
    color_objetivo, cantidad_balotas)`, así que incluir esa clave
    fragmentaría la caché sin ningún efecto real sobre el resultado
    -confirmado por auditoría real de la firma del motor.
    `hasta_numero_sorteo` permanece en su propia columna, nunca
    duplicado dentro de `parametros_metrica`.

    **`control_corte_temporal.html` NO se incluye en esta página**:
    su formulario, protegido y sin modificar, no tiene ningún
    mecanismo para conservar `color_objetivo` al enviarse (el
    `<form method="get">` compartido reemplaza toda la query string
    con sus propios campos al enviarse, y solo conoce `anio`/`mes`/
    `dia_semana`, nunca `color_objetivo`) -usarlo tal cual violaría
    el requisito explícito de conservar el color elegido al aplicar
    o retirar el corte. En su lugar, la plantilla nueva construye su
    propio formulario combinado (corte + color) en un único
    `<form method="get">`, con el mismo campo `hasta_numero_sorteo`,
    la misma etiqueta y el mismo criterio de corte -mismo
    comportamiento funcional exacto que el partial compartido, solo
    que ambos campos viajan juntos en la misma solicitud."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "pagina_colorloto_activa": "distribucion-conteo-color",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_conteo_color_colorloto.html",
            context={
                **contexto_base, "estadistica": None, "color_objetivo": None,
                "colores_seleccionables": [], "sin_colores_disponibles": False,
            },
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    historico = _obtener_historico_colorloto(historico_repo, color_repository, juego.id, hasta_numero_sorteo)
    vigentes = set(_codigos_colores_vigentes_en_referencia(historico))
    observados = {c for r in historico.pares for _, c in r.pares}
    colores_seleccionables = sorted(vigentes | observados)

    if not colores_seleccionables:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_conteo_color_colorloto.html",
            context={
                **contexto_base, "estadistica": None, "color_objetivo": None,
                "colores_seleccionables": [], "sin_colores_disponibles": True,
            },
        )

    if color_objetivo is None:
        color_objetivo = colores_seleccionables[0]
    elif color_objetivo not in colores_seleccionables:
        raise ColorNoVigenteError(color_objetivo)

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_conteo_color_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "color_objetivo": color_objetivo,
            "cantidad_balotas": juego.cantidad_numeros,
        },
    )

    vm = distribucion_conteo_color_colorloto_a_vm(resultado, color_objetivo, juego.cantidad_numeros, colores_seleccionables, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_conteo_color_colorloto.html",
        context={
            **contexto_base, "estadistica": vm, "color_objetivo": color_objetivo,
            "colores_seleccionables": colores_seleccionables, "sin_colores_disponibles": False,
        },
    )


_VENTANAS_VALIDAS = (5, 10, 20, 50)
_VENTANAS_VALIDAS_TEXTO = {"5", "10", "20", "50"}


def _validar_ventana(valor):
    """Corrección real de un defecto encontrado por auditoría
    independiente del parche provisional original: `int` puro más
    `AfterValidator` NO es léxicamente estricto -Pydantic, al
    coaccionar una cadena a `int`, acepta primero como `float` y
    luego confirma que es un número entero, así que `"5.0"`,
    `"5.00"` y `"20.0"` se convertían silenciosamente a `5`/`5`/`20`
    reales, confirmado real con `TestClient` antes de corregir -la
    afirmación "cualquier decimal produce 422" era falsa.

    Esta función es un `BeforeValidator`: recibe el valor ANTES de
    que Pydantic intente cualquier coacción de tipo, así que nunca
    pierde su forma léxica original. Si el valor es una cadena
    (siempre el caso real para un query parameter), se compara
    literalmente contra las CUATRO cadenas canónicas exactas -`"5"`,
    `"10"`, `"20"`, `"50"`- y solo esas cuatro se convierten con
    `int(...)`; cualquier otra representación de esos mismos números
    (`"5.0"`, `"05"`, `" 5"`, `"+5"`...) se rechaza explícitamente,
    porque nunca coincide con la comparación de cadenas exacta. Si el
    valor ya es un `int` (caso de pruebas internas que invocan el
    tipo directamente en Python, nunca a través de HTTP), se acepta
    solo si pertenece al conjunto `{5, 10, 20, 50}` -mismos cuatro
    valores, misma restricción, sin pasar por ninguna cadena.
    Cualquier otro caso -incluida la cadena vacía, texto, espacios,
    `"0"`, negativos, y cualquier entero fuera del conjunto- produce
    `ValueError`, que Pydantic traduce a `422` real antes de que el
    handler se ejecute."""
    if isinstance(valor, str):
        if valor in _VENTANAS_VALIDAS_TEXTO:
            return int(valor)
        raise ValueError("Input should be 5, 10, 20 or 50")
    if isinstance(valor, int) and not isinstance(valor, bool) and valor in _VENTANAS_VALIDAS:
        return valor
    raise ValueError("Input should be 5, 10, 20 or 50")


_VentanaValida = Annotated[int, BeforeValidator(_validar_ventana), Query()]


@router.get("/estadisticas/colorloto/comparacion-frecuencia-numeros-por-ventana")
def comparacion_frecuencia_numeros_por_ventana_colorloto(
    request: Request,
    ventana: _VentanaValida = 20,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-29 (PROVISIONAL): vigesimonovena visualización
    descriptiva de ColorLoto -compara, para cada número del rango
    real, su frecuencia en TODO el histórico disponible (ya filtrado
    por el corte) contra su frecuencia en los últimos `ventana`
    sorteos reales de ese mismo histórico. Primera etapa que conecta
    `motor/recencia.py`, hasta ahora sin integración web. Analiza el
    NÚMERO de la balota ignorando su color -nunca compara colores ni
    pares número-color, ambas etapas distintas y todavía sin
    conectar.

    **Selector cerrado, decisión de producto ya aprobada, corregido
    por auditoría independiente**: `ventana: _VentanaValida = 20`
    -dominio fijo `{5, 10, 20, 50}`, validado con un
    `BeforeValidator(_validar_ventana)` que compara la representación
    LÉXICA exacta de la query string contra las cuatro cadenas
    canónicas (`"5"`, `"10"`, `"20"`, `"50"`) antes de que Pydantic
    intente ninguna coacción de tipo -`422` real para cualquier otra
    representación de esos mismos números (`"5.0"`, `"5.00"`,
    `"20.0"`, `"05"`, `" 5"`), para cualquier entero fuera del
    conjunto, para `0`, negativos, texto, espacios y cadena vacía,
    confirmado real con `TestClient`, ANTES de que el handler se
    ejecute; sin `ventana` en la query string, se usa el valor por
    defecto `20` y la página responde `200` con resultados reales de
    inmediato -mismo patrón de "página siempre útil" ya establecido
    por AE-28 para `color_objetivo`, aplicado aquí a un dominio
    cerrado en vez de dinámico. `hasta_numero_sorteo` usa el mismo
    alias compartido `_CorteOpcional` ya validado por las 37 rutas
    anteriores y por el mantenimiento global -sin crear ningún alias
    nuevo.

    **Etiqueta interna siempre determinista**: `etiqueta_ventana` se
    deriva dentro de la receta (`f"ultimos_{ventana}"`), NUNCA se
    acepta desde HTTP, formulario ni VM -no forma parte de esta
    firma, de `parametros_metrica` ni de la identidad de caché.

    **Identidad de caché con TRES claves, las tres genuinamente
    consumidas por el cálculo -corregido por auditoría
    independiente**: `{"ventana": ventana, "rango_min":
    juego.rango_min, "rango_max": juego.rango_max}`, construida
    desde la entidad `Juego` real. El parche provisional original
    guardaba correctamente estas tres claves en la identidad, pero la
    receta ignoraba `rango_min`/`rango_max` y rederivaba un rango
    fijo internamente -contradicción real corregida: ahora la receta
    lee exactamente las tres claves de `parametros`, así que el
    universo de números realmente calculado coincide siempre con el
    que determina la identidad de caché. `ventana` forma parte de la
    identidad porque cambia materialmente la muestra reciente
    comparada; `rango_min`/`rango_max` porque determinan el universo
    numérico del resultado (mismo criterio ya establecido por
    AE-20/AE-21/AE-25/AE-26/AE-27/AE-28). `cantidad_numeros` y
    `politica_universo_colores` se excluyen deliberadamente -el
    motor de esta etapa no recibe la primera ni consume la segunda
    en ningún punto de su firma ni de su cuerpo (nunca construye un
    universo de colores, ignora el color por completo).
    `hasta_numero_sorteo` permanece en su propia columna, nunca
    duplicado dentro de `parametros_metrica` -mismo precedente exacto
    de las 37 rutas anteriores: el orquestador ya filtra el histórico
    por el corte general antes de invocar la receta, que aplica la
    ventana sobre ese subconjunto ya acotado, sin volver a introducir
    el corte por una segunda vía.

    **`control_corte_temporal.html` NO se incluye en esta página,
    deliberadamente**: ese partial no conoce `ventana` -mismo motivo
    exacto ya documentado en AE-28 para `color_objetivo`. La
    plantilla nueva construye su propio formulario combinado
    (ventana + corte) en un único `<form method="get">`, con el
    mismo campo `hasta_numero_sorteo` y el mismo criterio de corte;
    "Histórico completo" retira únicamente `hasta_numero_sorteo` y
    conserva `ventana` en la URL. Sin selección explícita de
    `ventana`, la URL base usa el valor por defecto `20`."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "ventana": ventana,
        "pagina_colorloto_activa": "comparacion-frecuencia-numeros-por-ventana",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/comparacion_frecuencia_numeros_por_ventana_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="comparacion_frecuencia_numeros_por_ventana_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "ventana": ventana,
            "rango_min": juego.rango_min,
            "rango_max": juego.rango_max,
        },
    )

    vm = comparacion_frecuencia_numeros_por_ventana_colorloto_a_vm(resultado, ventana, juego.rango_min, juego.rango_max, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/comparacion_frecuencia_numeros_por_ventana_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/comparacion-frecuencia-colores-por-ventana")
def comparacion_frecuencia_colores_por_ventana_colorloto(
    request: Request,
    ventana: _VentanaValida = 20,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-30 (PROVISIONAL): trigésima visualización descriptiva
    de ColorLoto -compara, para cada color del universo real
    (vigentes en la fecha de referencia UNIÓN observados en el
    histórico ya filtrado), su frecuencia en TODO el histórico
    disponible contra su frecuencia en los últimos `ventana` sorteos
    reales de ese mismo histórico. Segunda etapa que conecta
    `motor/recencia.py`, tras AE-29. Analiza el COLOR ignorando el
    número -sin selector individual de color: esta métrica compara
    TODOS los colores del universo válido a la vez, a diferencia de
    AE-28 (`distribucion_conteo_color_colorloto`), que sí elige un
    único color.

    **Defecto material confirmado por auditoría previa, corregido en
    el motor antes de esta etapa (Opción B autorizada)**:
    `comparar_frecuencia_colores_por_ventana` y
    `comparar_frecuencia_pares_numero_color_por_ventana` construían
    universos divergentes entre la porción histórica y la reciente
    -reproducido real: `KeyError: 'ROJO'` y `KeyError: '1-ROJO'`.
    Ambas funciones de `motor/recencia.py` fueron corregidas
    simétricamente para construir un único universo compartido
    (`colores_vigentes` unido con todos los colores observados en el
    histórico ya filtrado) y reutilizarlo en ambas llamadas -la
    función de pares queda corregida como mantenimiento del módulo,
    pero su página web NO se conecta en esta etapa, sigue siendo
    trabajo de una etapa posterior explícita.

    **Selector cerrado, mismo contrato exacto que AE-29, reutilizado
    sin duplicar ni relajar**: `ventana` (tipo `_VentanaValida`,
    default `20`) y `hasta_numero_sorteo` (tipo `_CorteOpcional`,
    default `None`) son los mismos símbolos de módulo ya definidos y
    validados por AE-29 -nunca se crea un alias nuevo ni una copia.
    Mismo dominio cerrado `{5, 10, 20, 50}`, mismo rechazo de
    decimales/formas no
    canónicas/texto/espacios/`0`/negativos con `422` antes de que el
    handler se ejecute, mismo comportamiento de corte ausente/vacío
    equivalente a histórico completo.

    **Etiqueta interna siempre determinista**: `etiqueta_ventana` se
    deriva dentro de la receta (`f"ultimos_{ventana}"`), NUNCA se
    acepta desde HTTP, formulario ni VM -no forma parte de esta
    firma, de `parametros_metrica` ni de la identidad de caché.

    **Identidad de caché con DOS claves, siguiendo el precedente real
    de AE-22/AE-23/AE-24 (nunca el de AE-2, la excepción temprana)**:
    `{"ventana": ventana, "politica_universo_colores":
    POLITICA_UNIVERSO_COLORES_ACTUAL}`. `rango_min`/`rango_max`/
    `cantidad_numeros` se excluyen deliberadamente -el motor de esta
    etapa no los recibe como argumentos matemáticos en absoluto
    (`comparar_frecuencia_colores_por_ventana` no tiene parámetros de
    rango), y se rederivan en la receta desde las constantes privadas
    ya validadas, mismo patrón exacto de AE-22/23/24. Ninguna lista
    dinámica de códigos de color entra en la identidad -el marcador
    estático ya cubre cualquier cambio de algoritmo. `hasta_numero_sorteo`
    permanece en su propia columna, nunca duplicado dentro de
    `parametros_metrica`.

    **`control_corte_temporal.html` NO se incluye en esta página,
    deliberadamente**: ese partial no conoce `ventana` -mismo motivo
    exacto ya documentado en AE-28/AE-29. La plantilla nueva
    construye su propio formulario combinado (ventana + corte) en un
    único `<form method="get">`, con el mismo campo
    `hasta_numero_sorteo` y el mismo criterio de corte; "Histórico
    completo" retira únicamente `hasta_numero_sorteo` y conserva
    `ventana` en la URL. Sin selección explícita de `ventana`, la URL
    base usa el valor por defecto `20`."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "ventana": ventana,
        "pagina_colorloto_activa": "comparacion-frecuencia-colores-por-ventana",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/comparacion_frecuencia_colores_por_ventana_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="comparacion_frecuencia_colores_por_ventana_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "ventana": ventana,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = comparacion_frecuencia_colores_por_ventana_colorloto_a_vm(resultado, ventana, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/comparacion_frecuencia_colores_por_ventana_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/colorloto/comparacion-frecuencia-pares-numero-color-por-ventana")
def comparacion_frecuencia_pares_numero_color_por_ventana_colorloto(
    request: Request,
    ventana: _VentanaValida = 20,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AE-31 (PROVISIONAL): trigésima primera visualización
    descriptiva de ColorLoto -compara, para cada par ATÓMICO
    (número, color), su frecuencia en TODO el histórico disponible
    (ya filtrado por el corte) contra su frecuencia en los últimos
    `ventana` sorteos reales de ese mismo histórico. Tercera etapa
    que conecta `motor/recencia.py`, tras AE-29 y AE-30. Analiza el
    PAR completo -mismo alcance exacto que
    `frecuencia_pares_colorloto` (Etapa AE-3); ni el número ni el
    color por separado.

    **El motor ya contiene la corrección de universo compartido de
    AE-30, sin volver a auditarlo ni modificarlo en esta etapa**:
    `comparar_frecuencia_pares_numero_color_por_ventana` construye un
    único universo de colores -vigentes UNIÓN observados en el
    histórico ya filtrado- compartido entre la porción histórica y
    la reciente, eliminando el defecto real `KeyError: '1-ROJO'` que
    habría bloqueado esta misma conexión si se hubiera intentado
    antes de AE-30.

    **Selector cerrado, mismo contrato exacto que AE-29/AE-30,
    reutilizado sin duplicar ni relajar**: `ventana` (tipo
    `_VentanaValida`, default `20`) y `hasta_numero_sorteo` (tipo
    `_CorteOpcional`, default `None`) son los mismos símbolos de
    módulo ya definidos y validados -nunca se crea un alias nuevo ni
    una copia. Mismo dominio cerrado `{5, 10, 20, 50}`, mismo rechazo
    de decimales/formas no canónicas/texto/espacios/`0`/negativos con
    `422` antes de que el handler se ejecute, mismo comportamiento de
    corte ausente/vacío equivalente a histórico completo.

    **Etiqueta interna siempre determinista**: `etiqueta_ventana` se
    deriva dentro de la receta (`f"ultimos_{ventana}"`), NUNCA se
    acepta desde HTTP, formulario ni VM -no forma parte de esta
    firma, de `parametros_metrica` ni de la identidad de caché.

    **Identidad de caché con CUATRO claves, corrigiendo
    deliberadamente el defecto real que AE-29 tuvo que corregir
    después de implementar (rederivar el rango desde una constante
    privada en vez de leerlo de la identidad)**: `{"ventana":
    ventana, "rango_min": juego.rango_min, "rango_max":
    juego.rango_max, "politica_universo_colores":
    POLITICA_UNIVERSO_COLORES_ACTUAL}`, construida desde la entidad
    `Juego` real -`rango_min`/`rango_max` se pasan al motor como
    argumentos matemáticos reales (a diferencia de AE-30, cuyo motor
    no los recibe en absoluto), así que la receta los lee
    directamente de esta misma identidad, nunca de una constante
    privada. `cantidad_numeros` se excluye -el motor no la recibe,
    se reutiliza solo para la validación defensiva interna vía la
    constante privada. Ninguna lista dinámica de colores entra en la
    identidad -el marcador estático ya cubre cualquier cambio de
    algoritmo.

    **`control_corte_temporal.html` NO se incluye en esta página,
    deliberadamente**: ese partial no conoce `ventana` -mismo motivo
    exacto ya documentado en AE-28/AE-29/AE-30. La plantilla nueva
    construye su propio formulario combinado (ventana + corte) en un
    único `<form method="get">`, con el mismo campo
    `hasta_numero_sorteo` y el mismo criterio de corte; "Histórico
    completo" retira únicamente `hasta_numero_sorteo` y conserva
    `ventana` en la URL."""
    db_conectada = _verificar_conexion(db)

    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "ventana": ventana,
        "pagina_colorloto_activa": "comparacion-frecuencia-pares-numero-color-por-ventana",
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/comparacion_frecuencia_pares_numero_color_por_ventana_colorloto.html",
            context={**contexto_base, "estadistica": None},
        )

    juego = juego_repository.obtener_por_codigo("COLORLOTO")
    if juego is None:
        raise JuegoNoEncontradoError("COLORLOTO")

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="comparacion_frecuencia_pares_numero_color_por_ventana_colorloto",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={
            "ventana": ventana,
            "rango_min": juego.rango_min,
            "rango_max": juego.rango_max,
            "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL,
        },
    )

    vm = comparacion_frecuencia_pares_numero_color_por_ventana_colorloto_a_vm(resultado, ventana, juego)

    return templates.TemplateResponse(
        request=request, name="estadisticas/comparacion_frecuencia_pares_numero_color_por_ventana_colorloto.html",
        context={**contexto_base, "estadistica": vm},
    )


@router.get("/estadisticas/{juego_slug}/frecuencia-numeros")
def frecuencia_numeros(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_numeros.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)
    rango_min, rango_max = juego_dominio.number_range

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_numeros",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max},
    )

    vm = frecuencia_numeros_a_vm(resultado, rango_min, rango_max, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_numeros.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/{juego_slug}/frecuencia-superbalota")
def frecuencia_superbalota(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Si el juego no soporta superbalota (`has_superballot=False` o
    `superballot_range is None` -caso real de MiLoto), se lanza
    `JuegoSinSuperbalotaError` (422), manejada por el
    exception_handler global de `main.py` -nunca un 500, nunca una
    gráfica vacía fabricada."""
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "frecuencia-superbalota", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_superbalota.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)

    if not juego_dominio.has_superballot or juego_dominio.superballot_range is None:
        raise JuegoSinSuperbalotaError(juego.codigo)

    rango_min, rango_max = juego_dominio.superballot_range

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="frecuencia_superbalota",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max},
    )

    vm = frecuencia_superbalota_a_vm(resultado, rango_min, rango_max, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_superbalota.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/{juego_slug}/frecuencia-observada-esperada")
def frecuencia_observada_esperada(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """`number_range`/`numbers_to_pick` vienen de `juego_dominio`,
    nunca escritos a mano -MiLoto (1-39) y Baloto/Revancha (1-43)
    respetan su configuración real."""
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "frecuencia-observada-esperada", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/frecuencia_observada_esperada.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)
    rango_min, rango_max = juego_dominio.number_range
    cantidad_numeros = juego_dominio.numbers_to_pick

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="tabla_frecuencia_numeros",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros},
    )

    vm = tabla_frecuencia_numeros_a_vm(resultado, rango_min, rango_max, cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/frecuencia_observada_esperada.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/{juego_slug}/atrasos-numeros")
def atrasos_numeros(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa W: cuarta visualización -distancia desde la última
    aparición, sobre números principales de los 3 juegos soportados
    (sin superbalota, sin ColorLoto). `number_range` viene de
    `juego_dominio`, igual que en las otras rutas -MiLoto (1-39)
    nunca calcula 40-43.

    NO se pasa `hasta_numero_sorteo` a `parametros_metrica`: el corte
    ya es su propia columna de identidad de caché
    (`EstadisticaCalculada.hasta_numero_sorteo`), separada de
    `parametros_metrica` -mezclarlos duplicaría el corte dentro del
    hash. La receta (`_calcular_atrasos_numeros`) deriva la
    referencia del último sorteo REAL dentro del histórico ya
    filtrado por el orquestador, nunca de un número de corte
    aritmético que pueda no corresponder a ningún sorteo real (ver
    docstring de la receta para el caso exacto verificado)."""
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "atrasos-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/atrasos_numeros.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)
    rango_min, rango_max = juego_dominio.number_range

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="atrasos_numeros",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max},
    )

    vm = atrasos_numeros_a_vm(resultado, rango_min, rango_max, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/atrasos_numeros.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/{juego_slug}/distribucion-pares-impares")
def distribucion_pares_impares(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa Y: quinta visualización -distribución de cuántos de los
    K números principales de cada sorteo son pares, sobre los 3
    juegos soportados (sin superbalota, sin ColorLoto). `K` viene de
    `juego_dominio.numbers_to_pick`, nunca hardcodeado -aunque los 3
    juegos comparten K=5 hoy, eso se lee del dominio, no se asume.

    La validación defensiva (cada resultado debe tener exactamente K
    números) vive en la receta (`_calcular_distribucion_pares_impares`),
    no aquí -si falla, propaga `ResultadoHistoricoInconsistenteError`
    (una `DominioError` específica, no un `ValueError` genérico -ver
    `app/application/exceptions.py`), manejada de forma controlada
    por `manejar_error_dominio` en `main.py` (422, vía
    `_STATUS_POR_EXCEPCION`, nunca un 500)."""
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "distribucion-pares-impares", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_pares_impares.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)
    cantidad_numeros = juego_dominio.numbers_to_pick

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_pares_impares",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"cantidad_numeros": cantidad_numeros},
    )

    vm = distribucion_pares_impares_a_vm(resultado, cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_pares_impares.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/{juego_slug}/distribucion-altos-bajos")
def distribucion_altos_bajos(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa Z: sexta visualización -distribución inferior/superior,
    sobre números principales de los 3 juegos soportados (sin
    superbalota, sin ColorLoto). `rango_min`/`rango_max`/`cantidad_numeros`
    vienen de `juego_dominio`, nunca hardcodeados -aunque hoy los 3
    juegos comparten K=5, y Baloto/Revancha comparten rango 1-43, eso
    se lee del dominio en cada request.

    La validación defensiva (cantidad, duplicados Y rango -a
    diferencia de atrasos_numeros/distribucion_pares_impares, esta
    métrica sí depende del rango) vive en la receta
    (`_calcular_distribucion_altos_bajos`), no aquí -si falla,
    propaga `ResultadoHistoricoInconsistenteError` (misma DominioError
    ya usada por Etapa Y, generalizada en Etapa Z con un tipo cerrado),
    manejada de forma controlada por `manejar_error_dominio` en
    `main.py` (500, vía `_STATUS_POR_EXCEPCION` -sin necesitar ningún
    handler nuevo)."""
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "distribucion-altos-bajos", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_altos_bajos.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)
    rango_min, rango_max = juego_dominio.number_range
    cantidad_numeros = juego_dominio.numbers_to_pick

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_altos_bajos",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros},
    )

    vm = distribucion_altos_bajos_a_vm(resultado, rango_min, rango_max, cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_altos_bajos.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/{juego_slug}/distribucion-pares-consecutivos")
def distribucion_pares_consecutivos(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AA: séptima visualización -distribución de pares
    consecutivos, sobre números principales de los 3 juegos
    soportados (sin superbalota, sin ColorLoto). `rango_min`/`rango_max`/
    `cantidad_numeros` vienen de `juego_dominio`, nunca hardcodeados.

    Validación defensiva completa (cantidad, duplicados Y rango) en la
    receta (`_calcular_distribucion_pares_consecutivos`), no aquí -si
    falla, propaga `ResultadoHistoricoInconsistenteError` (500,
    manejada por el mecanismo genérico ya existente, sin handler
    nuevo). Doble defensa deliberada: el motor también valida rango
    internamente (`_validar_rango`), pero Application valida primero
    para garantizar siempre una respuesta controlada."""
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "distribucion-pares-consecutivos", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_pares_consecutivos.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)
    rango_min, rango_max = juego_dominio.number_range
    cantidad_numeros = juego_dominio.numbers_to_pick

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_pares_consecutivos",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros},
    )

    vm = distribucion_pares_consecutivos_a_vm(resultado, rango_min, rango_max, cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_pares_consecutivos.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/{juego_slug}/distribucion-racha-maxima")
def distribucion_racha_maxima(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AB: octava visualización -longitud de la racha máxima de
    números consecutivos por sorteo, sobre números principales de los
    3 juegos soportados (sin superbalota, sin ColorLoto).
    `rango_min`/`rango_max`/`cantidad_numeros` vienen de
    `juego_dominio`, nunca hardcodeados.

    Distinta de `distribucion_pares_consecutivos` (Etapa AA): pares
    consecutivos cuenta ENLACES adyacentes (una racha de longitud 3
    aporta 2 pares); racha máxima mide la LONGITUD del bloque más
    largo (la misma racha de 3 aporta "3"). Dominio 1..K, nunca 0 -un
    sorteo válido siempre tiene al menos una racha de longitud 1.

    Validación defensiva completa (cantidad, duplicados Y rango) en
    la receta -mismo patrón exacto de `distribucion_pares_consecutivos`,
    incluida la doble defensa deliberada con la validación de rango
    ya existente en el motor."""
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "distribucion-racha-maxima", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/distribucion_racha_maxima.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)
    rango_min, rango_max = juego_dominio.number_range
    cantidad_numeros = juego_dominio.numbers_to_pick

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_racha_maxima",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros},
    )

    vm = distribucion_racha_maxima_a_vm(resultado, rango_min, rango_max, cantidad_numeros, juego)
    tiene_sorteos = vm["total_sorteos"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/distribucion_racha_maxima.html",
        context={**contexto_base, "estadistica": vm, "tiene_sorteos": tiene_sorteos},
    )


@router.get("/estadisticas/{juego_slug}/repeticiones-entre-sorteos")
def repeticiones_entre_sorteos(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: _CorteOpcional = None,
    db: Session = Depends(get_db),
    juego_repository: JuegoRepository = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    calcular_estadistica: CalcularYPersistirEstadistica = Depends(get_calcular_y_persistir_estadistica),
):
    """Etapa AC: novena visualización -cuántos números principales
    coinciden entre cada par de sorteos numéricamente consecutivos
    (numero_sorteo_actual == numero_sorteo_anterior + 1, nunca por
    posición, fecha ni adyacencia tras ordenar), sobre los 3 juegos
    soportados (sin superbalota, sin ColorLoto).
    `rango_min`/`rango_max`/`cantidad_numeros` vienen de
    `juego_dominio`, nunca hardcodeados.

    `FrecuenciaObservada.total_sorteos` aquí es la cantidad de
    TRANSICIONES VÁLIDAS, no de sorteos -el View Model la presenta
    como "Transiciones analizadas", nunca "Sorteos analizados".

    Validación defensiva completa (cantidad, duplicados Y rango) en
    la receta -mismo patrón exacto de las 3 métricas recientes,
    incluida la doble defensa deliberada con la validación de rango
    ya existente en el motor."""
    _resolver_codigo(juego_slug)
    db_conectada = _verificar_conexion(db)

    navegacion = construir_navegacion_estadisticas(
        juego_slug, "repeticiones-entre-sorteos", CAPACIDAD_SUPERBALOTA_POR_SLUG,
        _nombres_reales(juego_repository, db_conectada), hasta_numero_sorteo=hasta_numero_sorteo,
    )
    juego_nombre_actual = next(j["nombre"] for j in navegacion["juegos_nav"] if j["activo"])
    contexto_base = {
        "request": request, "active_page": "estadisticas",
        "estado_db": "Conectado a PostgreSQL" if db_conectada else "Sin conexión a BD",
        "db_conectada": db_conectada,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        "juego_nombre_actual": juego_nombre_actual,
        **navegacion,
    }

    if not db_conectada:
        return templates.TemplateResponse(
            request=request, name="estadisticas/repeticiones_entre_sorteos.html",
            context={**contexto_base, "estadistica": None},
        )

    juego, juego_dominio = _resolver_juego(juego_slug, juego_repository, game_factory)
    rango_min, rango_max = juego_dominio.number_range
    cantidad_numeros = juego_dominio.numbers_to_pick

    resultado = calcular_estadistica.ejecutar(
        juego_id=juego.id,
        tipo_estadistica="distribucion_repeticiones_entre_sorteos",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros_metrica={"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros},
    )

    vm = distribucion_repeticiones_entre_sorteos_a_vm(resultado, rango_min, rango_max, cantidad_numeros, juego)
    tiene_transiciones = vm["total_transiciones"] > 0

    return templates.TemplateResponse(
        request=request, name="estadisticas/repeticiones_entre_sorteos.html",
        context={**contexto_base, "estadistica": vm, "tiene_transiciones": tiene_transiciones},
    )
