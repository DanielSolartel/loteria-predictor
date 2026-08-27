"""
Utilidades compartidas por todos los parsers de Baloto.

Antes de este módulo, `_parsear_fecha`, `_MESES` y
`_extraer_tabla_premios` estaban duplicados idénticos en los tres
parsers (baloto_revancha, miloto, colorloto) -detectado en revisión
técnica antes de cerrar la Fase 2. Un cambio en el formato de fecha
del sitio, o en la estructura de la tabla de premios, habría
requerido editar 3 archivos en vez de 1.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from app.application.interfaces.draw_source_connector import CategoriaPremio

logger = logging.getLogger("importacion")

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

_RE_FECHA = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.IGNORECASE)


def parsear_fecha(texto: str) -> date | None:
    m = _RE_FECHA.search(texto.lower())
    if not m:
        return None
    dia, mes_txt, anio = m.groups()
    mes = MESES.get(mes_txt)
    if mes is None:
        return None
    return date(int(anio), mes, int(dia))


def extraer_tabla_premios(soup: BeautifulSoup) -> tuple[CategoriaPremio, ...]:
    """Busca la primera <table> del documento y la interpreta como
    tabla de premios por categoría (ACIERTOS / PREMIO TOTAL /
    GANADORES / PREMIO POR GANADOR). Es la misma estructura en los
    cuatro juegos (MiLoto, Baloto, Baloto Revancha, ColorLoto)
    -confirmado contra el sitio real."""
    categorias: list[CategoriaPremio] = []
    tabla = soup.find("table")
    if tabla is None:
        logger.warning(
            "[DATOS_INCOMPLETOS] No se encontró ninguna etiqueta <table> en el HTML para extraer la "
            "tabla de premios -posible cambio de estructura, o el sorteo simplemente "
            "no publica desglose de premios."
        )
        return ()

    for fila in tabla.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in fila.find_all(["td", "th"])]
        celdas = [c for c in celdas if c]
        if len(celdas) < 4:
            continue
        categoria, premio_total, ganadores_txt, premio_ganador = celdas[:4]
        if categoria.strip().upper() == "ACIERTOS" and premio_total.strip().upper() == "PREMIO TOTAL":
            continue  # fila de encabezado
        try:
            ganadores = int(re.sub(r"[.,]", "", ganadores_txt))
        except ValueError:
            ganadores = None
        categorias.append(
            CategoriaPremio(
                categoria=categoria, premio_total=premio_total or None,
                ganadores=ganadores, premio_por_ganador=premio_ganador or None,
            )
        )
    return tuple(categorias)
