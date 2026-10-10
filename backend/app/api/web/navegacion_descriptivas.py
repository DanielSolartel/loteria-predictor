"""
Navegación de las estadísticas descriptivas de la Fase 5 (sin FastAPI ni base de datos).

Qué métricas aplican a cada juego se decide con las reglas del DOMINIO (`BalotoGame`, `MiLotoGame`,
`ColorLotoGame`...), las mismas que usa el caso de uso: la navegación nunca ofrece una página que
responda 404. La usan el router de la Fase 5 y, como función global de Jinja, las páginas anteriores
de `/estadisticas/...` (fila «Más estadísticas» y enlace al panel).

El corte (`hasta_numero_sorteo`) se conserva dentro del mismo juego y NUNCA al cambiar de juego: la
numeración de sorteos no es comparable entre juegos (mismo criterio que la Etapa X).
"""
from __future__ import annotations

from urllib.parse import urlencode

from app.application.estadisticas.descriptivas import POR_SLUG, ReglasJuego, metricas_nuevas
from app.application.use_cases.consultar_resumen_juego import SLUG_A_CODIGO_RESUMEN
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from app.domain.games.colorloto import BALLS_TO_PICK, NUMBER_RANGE
from app.domain.games.miloto import MiLotoGame

NOMBRES = {"BALOTO": "Baloto", "BALOTO_REVANCHA": "Baloto Revancha", "MILOTO": "MiLoto", "COLORLOTO": "ColorLoto"}
_CLASES = {"baloto": BalotoGame, "baloto-revancha": BalotoRevanchaGame, "miloto": MiLotoGame}


def reglas_estaticas(slug_juego: str) -> ReglasJuego | None:
    """Reglas del dominio sin consultar la base (la paleta de ColorLoto no hace falta para navegar)."""
    codigo = SLUG_A_CODIGO_RESUMEN.get(slug_juego)
    if codigo is None:
        return None
    if codigo == "COLORLOTO":
        return ReglasJuego(codigo, NOMBRES[codigo], "colorloto", tuple(NUMBER_RANGE), BALLS_TO_PICK)
    clase = _CLASES[slug_juego]
    return ReglasJuego(codigo, NOMBRES[codigo], "numeros", tuple(clase.number_range), clase.numbers_to_pick,
                       tuple(clase.superballot_range) if clase.has_superballot else None)


def url_estadistica(slug_juego: str, metrica: str, hasta_numero_sorteo: int | None = None, **extra) -> str:
    consulta = {k: v for k, v in {**extra, "hasta_numero_sorteo": hasta_numero_sorteo}.items() if v is not None}
    base = f"/estadisticas/{slug_juego}/{metrica}"
    return f"{base}?{urlencode(consulta)}" if consulta else base


def navegacion_fase5(slug_juego: str, hasta_numero_sorteo: int | None = None, activa: str | None = None) -> dict:
    """Panel y métricas nuevas del juego, con el corte del juego actual."""
    reglas = reglas_estaticas(slug_juego)
    if reglas is None:
        return {"panel": None, "metricas": []}
    return {"panel": url_estadistica(slug_juego, "panel", hasta_numero_sorteo),
            "panel_activo": activa == "panel",
            "metricas": [{"slug": m.slug, "titulo": m.titulo, "activa": m.slug == activa,
                          "url": url_estadistica(slug_juego, m.slug, hasta_numero_sorteo)}
                         for m in metricas_nuevas(reglas)]}


def juegos_nav(metrica: str, slug_actual: str) -> list[dict]:
    """Los cuatro juegos: la misma métrica si existe para ese juego (nueva o anterior), si no su panel.
    Sin corte: al cambiar de juego se vuelve al histórico completo."""
    salida = []
    for slug, codigo in SLUG_A_CODIGO_RESUMEN.items():
        destino = "panel"
        definicion = POR_SLUG.get(metrica)
        if definicion is not None and definicion.aplica(reglas_estaticas(slug)):
            destino = metrica
        salida.append({"slug": slug, "nombre": NOMBRES[codigo], "activo": slug == slug_actual,
                       "url": url_estadistica(slug, destino)})
    return salida
