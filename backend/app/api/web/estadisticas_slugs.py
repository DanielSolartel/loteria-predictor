"""
Resolución de slug -> código de juego para las páginas estadísticas.

Sin ninguna dependencia de FastAPI/SQLAlchemy -extraído
deliberadamente del router para poder probar esta lógica de forma
aislada. Conjunto CERRADO: `resolver_codigo` nunca produce un valor
que no esté en `SLUG_A_CODIGO`; un slug desconocido devuelve `None`
(el router decide qué excepción HTTP lanzar con eso, esta función es
pura y no conoce FastAPI).

`CAPACIDAD_SUPERBALOTA_POR_SLUG` se deriva del atributo REAL de cada
clase de dominio (`LotteryGame.has_superballot`), nunca hardcodeado
aparte -si algún día cambiara la mecánica de un juego, este diccionario
lo reflejaría automáticamente sin tocarlo.
"""
from __future__ import annotations

from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from app.domain.games.miloto import MiLotoGame

SLUG_A_CODIGO: dict[str, str] = {
    "baloto": "BALOTO",
    "baloto-revancha": "BALOTO_REVANCHA",
    "miloto": "MILOTO",
}

CLASE_POR_SLUG: dict[str, type] = {
    "baloto": BalotoGame,
    "baloto-revancha": BalotoRevanchaGame,
    "miloto": MiLotoGame,
}

CAPACIDAD_SUPERBALOTA_POR_SLUG: dict[str, bool] = {
    slug: clase.has_superballot for slug, clase in CLASE_POR_SLUG.items()
}


def resolver_codigo(juego_slug: str) -> str | None:
    """None si `juego_slug` no pertenece al conjunto cerrado -el
    router es responsable de traducir eso en un 404 controlado."""
    return SLUG_A_CODIGO.get(juego_slug)
