"""
Mappers del adaptador REST: entidad de dominio -> schema Pydantic.

Equivalente al `view_models.py` del adaptador web, pero produciendo
JSON en vez de contexto para Jinja2. Ambos adaptadores traducen las
mismas entidades de formas distintas, sin que el dominio sepa que
existen.
"""
from __future__ import annotations

from app.api.rest.schemas import (
    ColorNumberPairOut,
    ColorOut,
    JuegoConReglasOut,
    JuegoOut,
    SorteoOut,
)
from app.application.use_cases.consultar_juegos import JuegoConReglas
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color


def juego_to_schema(juego: Juego) -> JuegoOut:
    return JuegoOut(**juego.__dict__)


def juego_con_reglas_to_schema(datos: JuegoConReglas) -> JuegoConReglasOut:
    return JuegoConReglasOut(
        **datos.juego.__dict__,
        espacio_muestral=datos.espacio_muestral,
        dimensiones=datos.dimensiones,
    )


def sorteo_to_schema(sorteo: Sorteo) -> SorteoOut:
    return SorteoOut(
        id=sorteo.id,
        juego_id=sorteo.juego_id,
        numero_sorteo=sorteo.numero_sorteo,
        fecha=sorteo.fecha,
        dia_semana=sorteo.dia_semana,
        numeros=list(sorteo.resultado.numeros),
        superbalota=sorteo.resultado.superbalota,
        pares=[
            ColorNumberPairOut(numero=p.numero, color_codigo=p.color.codigo, color_nombre=p.color.nombre)
            for p in sorteo.resultado.pares
        ],
        fuente=sorteo.fuente,
    )


def color_to_schema(color: Color) -> ColorOut:
    return ColorOut(**color.__dict__)
