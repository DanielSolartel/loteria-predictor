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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_calcular_y_persistir_estadistica,
    get_game_factory,
    get_juego_repository,
)
from app.api.web.estadisticas_slugs import CAPACIDAD_SUPERBALOTA_POR_SLUG, resolver_codigo
from app.api.web.view_models import (
    atrasos_numeros_a_vm,
    atrasos_numeros_colorloto_a_vm,
    atrasos_colores_colorloto_a_vm,
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
from app.application.exceptions import JuegoNoEncontradoError, JuegoSinSuperbalotaError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.use_cases.calcular_y_persistir_estadistica import (
    POLITICA_UNIVERSO_COLORES_ACTUAL,
    CalcularYPersistirEstadistica,
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


@router.get("/estadisticas/colorloto/frecuencia-numeros")
def frecuencia_numeros_colorloto(
    request: Request,
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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


@router.get("/estadisticas/{juego_slug}/frecuencia-numeros")
def frecuencia_numeros(
    juego_slug: str,
    request: Request,
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
    hasta_numero_sorteo: int | None = Query(default=None, ge=1),
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
