"""
Conector de Baloto (clásico).

Comparte el listado (`/resultados`) con `BalotoRevanchaConnector`
-la misma página trae ambas familias- pero cada uno filtra su propia
mitad. El detalle sí requiere una petición propia: verificado contra
el sitio real que `/resultados-baloto/{id}` no incluye el resultado
de Revancha (ni viceversa), así que no hay forma de obtener ambos
resultados con una sola descarga de detalle -pero si en el futuro el
sitio cambia y los une, el único lugar a tocar es `_url_detalle` aquí
y en `BalotoRevanchaConnector`.
"""
from __future__ import annotations

from app.application.interfaces.draw_source_connector import DrawDetail, DrawSummary
from app.infrastructure.connectors.base_connector import BaseConnector
from app.infrastructure.parsers import baloto_revancha_parser as parser

_BASE_URL = "https://baloto.com"


class BalotoConnector(BaseConnector):
    storage_prefix = "baloto_clasico"

    @property
    def game_code(self) -> str:
        return "BALOTO"

    def _url_listado(self, pagina: int) -> str:
        return f"{_BASE_URL}/resultados?page={pagina}"

    def _url_detalle(self, draw_id: str) -> str:
        return f"{_BASE_URL}/resultados-baloto/{draw_id}"

    def _parsear_pagina_listado(self, html: str) -> tuple[list[DrawSummary], bool]:
        return parser.parsear_listado_baloto(html)

    def _parsear_pagina_detalle(self, html: str, draw_id: str, url: str) -> DrawDetail:
        return parser.parsear_detalle(html, draw_id, url, etiqueta="Baloto")
