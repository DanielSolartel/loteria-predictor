"""
Parser de la familia Baloto (Baloto clásico + Baloto Revancha).

Traduce HTML (ya descargado) a los DTOs de `DrawSourceConnector`. No
hace peticiones HTTP, no guarda nada, no conoce reintentos ni
paginación -solo BeautifulSoup entrando y un DTO saliendo. Esto es
lo que permite testearlo con HTML de ejemplo, sin red, y lo que
mantiene la lógica de "cómo se ve una página de Baloto" separada de
"cómo se recorre el sitio" (eso vive en el conector).

La página de listado de https://baloto.com/resultados mezcla filas
de Baloto clásico y de Revancha (dos loterías regulatoriamente
distintas -reglamentos y acumulados separados- que comparten fecha y
número de sorteo oficial, mostradas en la misma tabla). Se
distinguen por el link "resultados-baloto" vs "resultados-revancha".

`parsear_listado_baloto` / `parsear_listado_revancha` filtran cada
una su propia familia a partir de la MISMA página de listado -un solo
recorrido de páginas descubre ambas, sin duplicar el crawl de
paginación. El detalle sí requiere una petición por familia, porque
cada resultado vive en una URL propia
(`/resultados-baloto/{id}` vs `/resultados-revancha/{id}`) con su
propia tabla de premios -verificado contra el sitio real: ninguna de
las dos páginas de detalle incluye el resultado de la otra.
`parsear_detalle` es agnóstico a la familia (ambas comparten
exactamente la misma estructura de página) y lo usan los dos
conectores sin modificación.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from app.application.interfaces.draw_source_connector import DrawDetail, DrawSummary
from app.infrastructure.parsers.common import extraer_tabla_premios, parsear_fecha

logger = logging.getLogger("importacion")

_RE_DRAW_ID_BALOTO = re.compile(r"/resultados-baloto/(\d+)")
_RE_DRAW_ID_REVANCHA = re.compile(r"/resultados-revancha/(\d+)")
_RE_SORTEO_NUM = re.compile(r"sorteo\s*#?\s*([\d.]+)", re.IGNORECASE)


def _parsear_listado_generico(html: str, patron_draw_id: re.Pattern, etiqueta: str) -> tuple[list[DrawSummary], bool]:
    soup = BeautifulSoup(html, "html.parser")
    resumenes: list[DrawSummary] = []

    for link in soup.find_all("a", href=patron_draw_id):
        m = patron_draw_id.search(link.get("href", ""))
        if not m:
            continue
        draw_id = m.group(1)

        fila = link.find_parent("tr")
        fecha = None
        if fila is not None:
            fecha = parsear_fecha(fila.get_text(" ", strip=True))
        if fecha is None:
            continue

        resumenes.append(DrawSummary(draw_id=draw_id, numero_sorteo=int(draw_id), fecha=fecha))

    hay_siguiente = soup.find("a", string=re.compile(r"Siguiente", re.IGNORECASE)) is not None
    if not resumenes:
        logger.warning(
            "[ERROR_ESTRUCTURA_HTML] %s: la página de listado no arrojó ningún sorteo reconocible. "
            "Posible cambio de estructura en la tabla de resultados o en el patrón de "
            "enlaces '%s'.", etiqueta, patron_draw_id.pattern,
        )
    return resumenes, hay_siguiente


def parsear_listado_baloto(html: str) -> tuple[list[DrawSummary], bool]:
    """Devuelve (resúmenes de sorteos de Baloto clásico en esta página,
    hay_pagina_siguiente)."""
    return _parsear_listado_generico(html, _RE_DRAW_ID_BALOTO, "Baloto")


def parsear_listado_revancha(html: str) -> tuple[list[DrawSummary], bool]:
    """Devuelve (resúmenes de sorteos de Revancha en esta página,
    hay_pagina_siguiente)."""
    return _parsear_listado_generico(html, _RE_DRAW_ID_REVANCHA, "BalotoRevancha")


def _extraer_numeros_principales(soup: BeautifulSoup) -> list[int]:
    """Los 6 números grandes (5 principales + superbalota) aparecen
    como texto suelto de 2 dígitos justo debajo del encabezado del
    sorteo. Se buscan como nodos de texto cortos y puramente
    numéricos, en orden de aparición en el documento."""
    numeros: list[int] = []
    for texto in soup.stripped_strings:
        if re.fullmatch(r"\d{1,2}", texto):
            numeros.append(int(texto))
        if len(numeros) >= 6:
            break
    return numeros


def parsear_detalle(html: str, draw_id: str, fuente_url: str, etiqueta: str = "BalotoRevancha") -> DrawDetail:
    """Parsea una página de detalle de Baloto o de Revancha -ambas
    familias comparten exactamente la misma estructura de página, así
    que esta función es agnóstica a cuál es y la usan ambos
    conectores sin modificación. `etiqueta` solo se usa para
    identificar la familia en los mensajes de log."""
    soup = BeautifulSoup(html, "html.parser")
    advertencias: list[str] = []

    texto_completo = soup.get_text(" ", strip=True)

    m_sorteo = _RE_SORTEO_NUM.search(texto_completo)
    numero_sorteo = int(m_sorteo.group(1).replace(".", "")) if m_sorteo else int(draw_id)
    if m_sorteo and numero_sorteo != int(draw_id):
        advertencias.append(
            f"El número de sorteo extraído ({numero_sorteo}) no coincide con el draw_id "
            f"de la URL ({draw_id}); se usa el de la URL como identidad."
        )
        numero_sorteo = int(draw_id)

    fecha = parsear_fecha(texto_completo)
    if fecha is None:
        advertencias.append("No se pudo extraer la fecha del sorteo")

    numeros_todos = _extraer_numeros_principales(soup)
    if len(numeros_todos) == 0:
        mensaje = (
            f"No se encontró NINGÚN número en el sorteo {draw_id}. Esto indica un "
            f"CAMBIO DE ESTRUCTURA en el sitio (no un dato incompleto puntual) -revisar "
            f"infrastructure/parsers/baloto_revancha_parser.py::_extraer_numeros_principales "
            f"contra storage/html/baloto_{draw_id}.html."
        )
        advertencias.append(mensaje)
        logger.error("[ERROR_ESTRUCTURA_HTML] %s %s: %s", etiqueta, draw_id, mensaje)
        numeros = ()
        superbalota = None
    elif len(numeros_todos) < 6:
        mensaje = f"Se esperaban 6 números (5 + superbalota), se encontraron {len(numeros_todos)} (dato incompleto)"
        advertencias.append(mensaje)
        logger.warning("[DATOS_INCOMPLETOS] %s %s: %s", etiqueta, draw_id, mensaje)
        numeros = tuple(numeros_todos)
        superbalota = None
    else:
        numeros = tuple(numeros_todos[:5])
        superbalota = numeros_todos[5]

    total_ganadores = None
    m_gan = re.search(r"TOTAL\s+GANADORES\s*([\d.,]+)", texto_completo, re.IGNORECASE)
    if m_gan:
        try:
            total_ganadores = int(re.sub(r"[.,]", "", m_gan.group(1)))
        except ValueError:
            pass

    m_premiacion = re.search(r"TOTAL\s+PREMIACI[OÓ]N\s*\$?\s*([\d.,]+)", texto_completo, re.IGNORECASE)
    total_premiacion = f"${m_premiacion.group(1)}" if m_premiacion else None

    m_acumulado = re.search(r"ACUMULADO DEL SORTEO:?\s*\$?\s*([\d.,]+\s*MILLONES)", texto_completo, re.IGNORECASE)
    nuevo_acumulado = m_acumulado.group(1) if m_acumulado else None

    categorias = extraer_tabla_premios(soup)
    if not categorias:
        advertencias.append("No se pudo extraer la tabla de premios por categoría")

    if fecha is None:
        fecha = date.today()  # placeholder defensivo; el sorteo quedará marcado con advertencia

    return DrawDetail(
        draw_id=draw_id,
        numero_sorteo=numero_sorteo,
        fecha=fecha,
        numeros=numeros,
        superbalota=superbalota,
        total_ganadores=total_ganadores,
        total_premiacion=total_premiacion,
        nuevo_acumulado=nuevo_acumulado,
        categorias_premio=categorias,
        html_crudo=html,
        fuente_url=fuente_url,
        advertencias=tuple(advertencias),
    )
