from __future__ import annotations

from app.application.interfaces.draw_source_connector import DrawDetail, DrawSummary
from app.infrastructure.connectors.base_connector import BaseConnector
from app.infrastructure.parsers import baloto_revancha_parser as parser

_BASE_URL = "https://baloto.com"


class BalotoRevanchaConnector(BaseConnector):
    storage_prefix = "baloto"

    @property
    def game_code(self) -> str:
        return "BALOTO_REVANCHA"

    def _url_listado(self, pagina: int) -> str:
        return f"{_BASE_URL}/resultados?page={pagina}"

    def _url_detalle(self, draw_id: str) -> str:
        return f"{_BASE_URL}/resultados-revancha/{draw_id}"

    def _parsear_pagina_listado(self, html: str) -> tuple[list[DrawSummary], bool]:
        return parser.parsear_listado_revancha(html)

    def _parsear_pagina_detalle(self, html: str, draw_id: str, url: str) -> DrawDetail:
        return parser.parsear_detalle(html, draw_id, url, etiqueta="BalotoRevancha")
