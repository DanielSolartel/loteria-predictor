"""
Corte temporal — filtrado defensivo por `hasta_numero_sorteo`.

Extraído a su propio módulo tras la Etapa F: la misma función privada
(`_filtrar_por_corte`) se había reimplementado de forma idéntica en
`atrasos.py` y `recencia.py`, y `distribuciones.py` iba a ser la
tercera copia. Es el mecanismo central de la garantía anti-fuga de
información -mientras más lugares lo reimplementen por separado,
mayor el riesgo de que una futura edición corrija uno y deje los
demás desincronizados. Con tres usos confirmados, se consolida aquí.

`atrasos.py` y `recencia.py` fueron actualizados para importar esta
función en vez de su copia privada -es la única modificación a
archivos existentes en la Etapa F, y está motivada exclusivamente por
esta consolidación.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def filtrar_por_corte_temporal(resultados: Sequence[T], hasta_numero_sorteo: int | None) -> list[T]:
    """Filtra DEFENSIVAMENTE por numero_sorteo <= hasta_numero_sorteo
    -no confía en que el llamador ya cortó bien, porque un error aquí
    corrompería silenciosamente la garantía anti-fuga central del
    motor estadístico. Nunca muta `resultados`: siempre construye una
    lista nueva. Si `hasta_numero_sorteo` es None, devuelve una copia
    de todos los resultados sin filtrar."""
    if hasta_numero_sorteo is None:
        return list(resultados)
    return [r for r in resultados if r.numero_sorteo <= hasta_numero_sorteo]
