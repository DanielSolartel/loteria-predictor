"""
Parser de MiLoto.

A diferencia de Baloto Revancha, aquí el listado
(https://baloto.com/miloto/resultados/) ya trae fecha + los 5
números completos por fila -así que es la fuente primaria de los
datos mínimos requeridos. El detalle
(https://baloto.com/miloto/resultados-miloto/{id}/) se intenta para
obtener el desglose de premios, pero verificado contra el sitio real
esa ruta actualmente devuelve el contenido genérico de
Baloto/Revancha en vez del detalle de MiLoto (parece un problema de
enrutamiento del sitio). Por eso `parsear_detalle` valida que el
número de sorteo extraído coincida con el `draw_id` solicitado; si
no coincide, marca una advertencia y el conector usa como resultado
únicamente los datos ya capturados del listado, sin abortar el
sorteo.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from app.application.interfaces.draw_source_connector import DrawDetail, DrawSummary
from app.infrastructure.parsers.common import extraer_tabla_premios, parsear_fecha

logger = logging.getLogger("importacion")

_RE_DRAW_ID = re.compile(r"/miloto/resultados-miloto/(\d+)")
_RE_SORTEO_NUM = re.compile(r"sorteo\s*#?\s*([\d.]+)", re.IGNORECASE)


def parsear_listado(html: str) -> tuple[list[DrawSummary], dict[str, tuple[int, ...]], bool]:
    """Devuelve (resúmenes, {draw_id: (5 números)}, hay_pagina_siguiente).
    El diccionario de números es la razón por la que este parser no
    tiene la misma firma que el de Baloto Revancha: es la fuente
    primaria de datos para MiLoto, no un extra."""
    soup = BeautifulSoup(html, "html.parser")
    resumenes: list[DrawSummary] = []
    numeros_por_draw: dict[str, tuple[int, ...]] = {}

    for link in soup.find_all("a", href=_RE_DRAW_ID):
        m = _RE_DRAW_ID.search(link.get("href", ""))
        if not m:
            continue
        draw_id = m.group(1)

        fila = link.find_parent("tr")
        if fila is None:
            continue

        texto_fila = fila.get_text(" ", strip=True)
        fecha = parsear_fecha(texto_fila)
        if fecha is None:
            continue

        celdas = fila.find_all("td")
        numeros: tuple[int, ...] = ()
        for celda in celdas:
            texto_celda = celda.get_text(" ", strip=True)
            if re.fullmatch(r"(\d{1,2}\s*-\s*){4}\d{1,2}", texto_celda):
                numeros = tuple(int(n) for n in re.findall(r"\d{1,2}", texto_celda))
                break

        resumenes.append(DrawSummary(draw_id=draw_id, numero_sorteo=int(draw_id), fecha=fecha))
        if len(numeros) == 5:
            numeros_por_draw[draw_id] = numeros
        else:
            logger.warning(
                "[DATOS_INCOMPLETOS] MiLoto: no se pudieron extraer los 5 números del sorteo %s desde el "
                "listado (fuente primaria para este juego) -posible cambio de "
                "estructura en la celda de resultado. Fila analizada: %r",
                draw_id, texto_fila[:120],
            )

    hay_siguiente = soup.find("a", string=re.compile(r"Siguiente", re.IGNORECASE)) is not None
    if not resumenes:
        logger.warning(
            "[ERROR_ESTRUCTURA_HTML] MiLoto: la página de listado no arrojó ningún sorteo reconocible. Posible "
            "cambio de estructura en la tabla de resultados o en el patrón de enlaces "
            "'/miloto/resultados-miloto/{id}'."
        )
    return resumenes, numeros_por_draw, hay_siguiente


def parsear_detalle(html: str, draw_id: str, fuente_url: str) -> tuple[DrawDetail, bool]:
    """Devuelve (detalle_extraido, coincide_con_draw_id). Cuando
    `coincide_con_draw_id` es False, el conector debe descartar este
    resultado y usar el respaldo obtenido del listado."""
    soup = BeautifulSoup(html, "html.parser")
    texto_completo = soup.get_text(" ", strip=True)
    advertencias: list[str] = []

    m_sorteo = _RE_SORTEO_NUM.search(texto_completo)
    numero_extraido = int(m_sorteo.group(1).replace(".", "")) if m_sorteo else None
    coincide = numero_extraido == int(draw_id)
    if not coincide:
        advertencias.append(
            f"El detalle devuelto no corresponde al sorteo {draw_id} "
            f"(se extrajo #{numero_extraido}); posible problema de enrutamiento del sitio."
        )

    fecha = parsear_fecha(texto_completo) or date.today()
    categorias = extraer_tabla_premios(soup) if coincide else ()

    return (
        DrawDetail(
            draw_id=draw_id,
            numero_sorteo=int(draw_id),
            fecha=fecha,
            categorias_premio=categorias,
            html_crudo=html,
            fuente_url=fuente_url,
            advertencias=tuple(advertencias),
        ),
        coincide,
    )
