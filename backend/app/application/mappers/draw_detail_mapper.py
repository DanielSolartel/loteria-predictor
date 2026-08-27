"""
Mapper: DrawDetail (DTO de conector) -> Combination (value object de dominio).

Extraído a su propio módulo tras revisión técnica: tanto
`SincronizarSorteos` como `ReimportarSorteo` necesitaban esta misma
traducción, y antes `ReimportarSorteo` importaba una función privada
(`_draw_detail_a_combination`) directamente del módulo de otro caso
de uso -acoplamiento indebido entre dos casos de uso que no deberían
conocerse entre sí. Ahora ambos dependen de este mapper neutral, que
no le pertenece a ninguno de los dos.

Para ColorLoto, `DrawDetail.numeros` y `DrawDetail.colores` son
campos paralelos e independientes (ver el docstring de `DrawDetail`
para la razón de este diseño). Este mapper es el único lugar que los
combina en `ColorNumberPair`; si algún color no se pudo determinar,
lanza un error que dice EXACTAMENTE cuántos números se extrajeron y
cuántos colores faltan -nunca deja que el dominio reciba una lista
vacía sin explicación cuando en realidad los números sí se
conocían.
"""
from __future__ import annotations

from app.application.interfaces.draw_source_connector import DrawDetail
from app.domain.entities.juego import Juego
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination


def draw_detail_a_combination(
    draw: DrawDetail, juego: Juego, colores_vigentes: dict[str, Color]
) -> Combination:
    if juego.tiene_color:
        return Combination(pares=_construir_pares_color(draw, colores_vigentes))
    return Combination(numeros=draw.numeros, superbalota=draw.superbalota)


def _construir_pares_color(draw: DrawDetail, colores_vigentes: dict[str, Color]) -> tuple[ColorNumberPair, ...]:
    if not draw.numeros:
        raise ValueError(
            "No se pudo extraer ningún número de balota para este sorteo de ColorLoto "
            "-ver advertencias del parser para el diagnóstico exacto."
        )

    faltantes = [n for n, c in zip(draw.numeros, draw.colores) if c is None]
    if faltantes:
        raise ValueError(
            f"Se extrajeron {len(draw.numeros)} número(s) de balota "
            f"({', '.join(str(n) for n in draw.numeros)}), pero no se pudo determinar el "
            f"color de {len(faltantes)} de ellas (números sin color: "
            f"{', '.join(str(n) for n in faltantes)}). No se descarta el sorteo silenciosamente: "
            f"revisa storage/html/ para ese draw_id y ajusta el selector de color del parser."
        )

    pares = []
    for numero, color_codigo in zip(draw.numeros, draw.colores):
        color = colores_vigentes.get(color_codigo)
        if color is None:
            raise ValueError(f"Color '{color_codigo}' no está en la paleta vigente de ColorLoto")
        pares.append(ColorNumberPair(numero=numero, color=color))
    return tuple(pares)
