from __future__ import annotations

from app.application.interfaces.draw_source_connector import DrawDetail, DrawSummary
from app.infrastructure.connectors.base_connector import BaseConnector
from app.infrastructure.parsers import colorloto_parser as parser

_BASE_URL = "https://baloto.com"


class ColorLotoConnector(BaseConnector):
    storage_prefix = "colorloto"

    @property
    def game_code(self) -> str:
        return "COLORLOTO"

    def _url_listado(self, pagina: int) -> str:
        if pagina == 1:
            return f"{_BASE_URL}/colorloto/resultados"
        return f"{_BASE_URL}/colorloto/resultados?page={pagina}"

    def _url_detalle(self, draw_id: str) -> str:
        return f"{_BASE_URL}/colorloto/resultados/{draw_id}"

    def _parsear_pagina_listado(self, html: str) -> tuple[list[DrawSummary], bool]:
        return parser.parsear_listado(html)

    def _parsear_pagina_detalle(self, html: str, draw_id: str, url: str) -> DrawDetail:
        return parser.parsear_detalle(html, draw_id, url)
