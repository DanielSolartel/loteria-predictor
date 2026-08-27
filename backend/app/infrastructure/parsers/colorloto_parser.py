"""
Parser de ColorLoto.

Historial de esta versión (ver docs/decisiones/colorloto_numeros_colores.md
para el análisis completo): la extracción original buscaba número y
color por SEPARADO -números por un lado (texto), colores por otro
(heurística de estilo/clase sobre una lista de selectores genérica
que nunca coincidía con la estructura real). Cuando la búsqueda de
color fallaba, el código descartaba también el número correspondiente
-un fallo de UN dato (color) borraba silenciosamente el OTRO dato que
sí se había extraído bien (número), y el dominio terminaba recibiendo
"0 balotas" en vez de "6 números, colores no identificados".

Estructura real del HTML (confirmada por inspección directa del
usuario contra https://baloto.com/colorloto/resultados/206):

    <div class="balota balota-blue nunito-medium">2</div>

Número y color viven en el MISMO elemento -el número es el texto, el
color está en la clase `balota-{nombre}`. Por eso ahora se extraen
juntos, en una sola pasada por elemento (`_extraer_balotas`): esto
elimina por completo la posibilidad de desalinear números y colores
extraídos por separado, y hace que un fallo de color nunca pueda
volver a borrar un número ya conocido -`DrawDetail.numeros` y
`DrawDetail.colores` son campos paralelos independientes; un hueco en
`colores` dice explícitamente "no se pudo determinar el color de ESTA
balota", sin tocar el número.

Si en el futuro el sitio cambia esta estructura, `_extraer_balotas`
cae a un respaldo (`_extraer_numeros_de_reserva`) que recupera al
menos los números desde el texto de la página -degradando con
advertencias claras, nunca perdiendo silenciosamente lo que sí se
pudo extraer.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from app.application.interfaces.draw_source_connector import CategoriaPremio, DrawDetail, DrawSummary
from app.infrastructure.parsers.common import extraer_tabla_premios, parsear_fecha

logger = logging.getLogger("importacion")

_RE_DRAW_ID = re.compile(r"/colorloto/resultados/(\d+)")
_RE_SORTEO_NUM = re.compile(r"sorteo\s*#?\s*([\d.]+)", re.IGNORECASE)

# Punto único de ajuste si el sitio renombra sus colores. Las claves
# son el sufijo de la clase real `balota-{clave}` (confirmado:
# "blue", "red"; se asume el resto por el mismo patrón en inglés,
# ajustar aquí si algún color no coincide en producción).
_NOMBRE_CLASE_A_COLOR = {
    "yellow": "AMARILLO",
    "blue": "AZUL",
    "red": "ROJO",
    "green": "VERDE",
    "white": "BLANCO",
    "black": "NEGRO",
}
_RE_CLASE_BALOTA = re.compile(r"^balota-(\w+)$")


def _color_desde_elemento_balota(elemento) -> str | None:
    """Busca, entre las clases del elemento, una que matchee
    'balota-{color}' y traduce el sufijo a nuestro código interno.
    No inventa: si ninguna clase matchea, devuelve None."""
    for clase in elemento.get("class", []):
        m = _RE_CLASE_BALOTA.match(clase)
        if m:
            codigo = _NOMBRE_CLASE_A_COLOR.get(m.group(1).lower())
            if codigo:
                return codigo
    return None


def _extraer_balotas(soup: BeautifulSoup) -> list[tuple[int, str | None]]:
    """Extracción primaria: cada balota es un único elemento
    `div.balota-{color}` cuyo texto es el número. Número y color se
    leen del MISMO nodo -no hay forma de que queden desalineados."""
    balotas: list[tuple[int, str | None]] = []
    for el in soup.select('[class*="balota-"]'):
        texto = el.get_text(strip=True)
        if not re.fullmatch(r"[1-7]", texto or ""):
            continue
        color = _color_desde_elemento_balota(el)
        balotas.append((int(texto), color))
        if len(balotas) >= 6:
            break
    return balotas


def _extraer_numeros_de_reserva(soup: BeautifulSoup) -> list[int]:
    """Respaldo si `_extraer_balotas` no encuentra los elementos
    esperados (p.ej. el sitio cambió la clase). Recupera al menos los
    números como nodos de texto aislados de un solo dígito -sin
    color, que quedará como advertencia explícita más abajo."""
    return [int(t) for t in soup.stripped_strings if re.fullmatch(r"[1-7]", t)][:6]


def parsear_listado(html: str) -> tuple[list[DrawSummary], bool]:
    soup = BeautifulSoup(html, "html.parser")
    resumenes: list[DrawSummary] = []

    for link in soup.find_all("a", href=_RE_DRAW_ID):
        m = _RE_DRAW_ID.search(link.get("href", ""))
        if not m:
            continue
        draw_id = m.group(1)
        fila = link.find_parent("tr")
        fecha = parsear_fecha(fila.get_text(" ", strip=True)) if fila is not None else None
        if fecha is None:
            continue
        resumenes.append(DrawSummary(draw_id=draw_id, numero_sorteo=int(draw_id), fecha=fecha))

    hay_siguiente = soup.find("a", string=re.compile(r"Siguiente", re.IGNORECASE)) is not None
    if not resumenes:
        logger.warning(
            "[ERROR_ESTRUCTURA_HTML] ColorLoto: la página de listado no arrojó ningún sorteo "
            "reconocible. Posible cambio de estructura HTML en la tabla de resultados o en el "
            "patrón de enlaces '/colorloto/resultados/{id}'."
        )
    return resumenes, hay_siguiente


def parsear_detalle(html: str, draw_id: str, fuente_url: str) -> DrawDetail:
    soup = BeautifulSoup(html, "html.parser")
    texto_completo = soup.get_text(" ", strip=True)
    advertencias: list[str] = []

    m_sorteo = _RE_SORTEO_NUM.search(texto_completo)
    numero_sorteo = int(draw_id)
    if m_sorteo and int(m_sorteo.group(1).replace(".", "")) != numero_sorteo:
        advertencias.append("El número de sorteo extraído no coincide con el draw_id de la URL")

    fecha = parsear_fecha(texto_completo) or date.today()

    balotas = _extraer_balotas(soup)
    if len(balotas) < 6:
        if balotas:
            logger.warning(
                "[DATOS_INCOMPLETOS] ColorLoto %s: solo se encontraron %d/6 elementos "
                "'div.balota-{color}' -usando números de respaldo.", draw_id, len(balotas),
            )
        else:
            logger.error(
                "[ERROR_ESTRUCTURA_HTML] ColorLoto %s: no se encontró NINGÚN elemento "
                "'div.balota-{color}'. Posible cambio de estructura HTML -revisar "
                "storage/html/colorloto_%s.html y ajustar "
                "infrastructure/parsers/colorloto_parser.py::_extraer_balotas.", draw_id, draw_id,
            )
        numeros_respaldo = _extraer_numeros_de_reserva(soup)
        # Se completan las balotas ya encontradas (con su color, si lo
        # tenían) con los números de respaldo restantes, sin color.
        for n in numeros_respaldo:
            if len(balotas) >= 6:
                break
            balotas.append((n, None))

    numeros = tuple(n for n, _ in balotas)
    colores = tuple(c for _, c in balotas)

    faltantes = sum(1 for c in colores if c is None)
    if numeros and faltantes:
        advertencias.append(
            f"Se extrajeron {len(numeros)} número(s) de balota pero el color de {faltantes} "
            f"de ellas no se pudo determinar (números sin color: "
            f"{[n for n, c in zip(numeros, colores) if c is None]})."
        )
    if not numeros:
        advertencias.append(
            "No se pudo extraer ningún número de balota -ni desde los elementos "
            "'div.balota-{color}' esperados ni desde el respaldo de texto. Esto indica un "
            "CAMBIO DE ESTRUCTURA en el sitio, no un dato incompleto puntual."
        )

    m_ganadores = re.search(r"TOTAL\s+GANADORES\s*([\d.,]+)", texto_completo, re.IGNORECASE)
    total_ganadores = int(re.sub(r"[.,]", "", m_ganadores.group(1))) if m_ganadores else None

    m_premiacion = re.search(r"TOTAL\s+PREMIACI[OÓ]N\s*\$?\s*([\d.,]+)", texto_completo, re.IGNORECASE)
    total_premiacion = f"${m_premiacion.group(1)}" if m_premiacion else None

    m_acumulado = re.search(r"NUEVO ACUMULADO\s*\$?\s*([\d.,]+\s*MILLONES)", texto_completo, re.IGNORECASE)
    nuevo_acumulado = m_acumulado.group(1) if m_acumulado else None

    categorias = extraer_tabla_premios(soup)
    if not categorias:
        advertencias.append("No se pudo extraer la tabla de premios por categoría")

    return DrawDetail(
        draw_id=draw_id,
        numero_sorteo=numero_sorteo,
        fecha=fecha,
        numeros=numeros,
        colores=colores,
        total_ganadores=total_ganadores,
        total_premiacion=total_premiacion,
        nuevo_acumulado=nuevo_acumulado,
        categorias_premio=categorias,
        html_crudo=html,
        fuente_url=fuente_url,
        advertencias=tuple(advertencias),
    )
