"""
Conector de MiLoto.

Ver el docstring de `infrastructure/parsers/miloto_parser.py` para
el detalle del problema confirmado en el sitio: la URL de detalle no
siempre devuelve el contenido de MiLoto. Este conector compensa
cacheando los números ya vistos en el listado (`_numeros_por_draw`)
y usándolos como respaldo si el detalle no coincide con el sorteo
pedido -así el dato mínimo requerido (fecha + 5 números) nunca se
pierde, aunque el desglose de premios pueda faltar para algunos
sorteos.
"""
from __future__ import annotations

from app.application.interfaces.draw_source_connector import DrawDetail, DrawSummary
from app.infrastructure.connectors.base_connector import BaseConnector
from app.infrastructure.parsers import miloto_parser as parser

_BASE_URL = "https://baloto.com"


class MiLotoConnector(BaseConnector):
    storage_prefix = "miloto"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._numeros_por_draw: dict[str, tuple[int, ...]] = {}

    @property
    def game_code(self) -> str:
        return "MILOTO"

    def fetch_draws(self, ultimo_conocido: int | None = None, max_paginas: int | None = None):
        # El conector vive durante todo el proceso (es un singleton en
        # el contenedor de DI), así que esta caché debe reiniciarse en
        # cada corrida -de lo contrario crece sin límite mientras dure
        # el servidor, acumulando entradas que solo sirven como
        # respaldo transitorio dentro de la sincronización actual.
        self._numeros_por_draw = {}
        return super().fetch_draws(ultimo_conocido, max_paginas)

    def _url_listado(self, pagina: int) -> str:
        if pagina == 1:
            return f"{_BASE_URL}/miloto/resultados/"
        return f"{_BASE_URL}/miloto/resultados/?page={pagina}"

    def _url_detalle(self, draw_id: str) -> str:
        return f"{_BASE_URL}/miloto/resultados-miloto/{draw_id}/"

    def _parsear_pagina_listado(self, html: str) -> tuple[list[DrawSummary], bool]:
        resumenes, numeros_por_draw, hay_siguiente = parser.parsear_listado(html)
        self._numeros_por_draw.update(numeros_por_draw)
        return resumenes, hay_siguiente

    def _parsear_pagina_detalle(self, html: str, draw_id: str, url: str) -> DrawDetail:
        detalle, coincide = parser.parsear_detalle(html, draw_id, url)

        numeros_respaldo = self._numeros_por_draw.get(draw_id, ())
        if not coincide or not detalle.numeros:
            if numeros_respaldo:
                detalle = DrawDetail(
                    draw_id=detalle.draw_id,
                    numero_sorteo=detalle.numero_sorteo,
                    fecha=detalle.fecha,
                    numeros=numeros_respaldo,
                    categorias_premio=detalle.categorias_premio if coincide else (),
                    html_crudo=detalle.html_crudo,
                    fuente_url=detalle.fuente_url,
                    advertencias=detalle.advertencias
                    + ("Se usaron los números del listado como respaldo del detalle.",),
                )
            else:
                detalle = DrawDetail(
                    draw_id=detalle.draw_id, numero_sorteo=detalle.numero_sorteo, fecha=detalle.fecha,
                    html_crudo=detalle.html_crudo, fuente_url=detalle.fuente_url,
                    advertencias=detalle.advertencias
                    + ("No se encontraron números ni en el detalle ni en el listado cacheado.",),
                )
        return detalle
