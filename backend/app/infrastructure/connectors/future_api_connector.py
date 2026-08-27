"""
FutureApiConnector.

Placeholder que demuestra el punto de extensión: si Coljuegos/Baloto
publica una API oficial en el futuro, esta clase se implementa igual
que los demás conectores (mismo puerto) y se registra en
`infrastructure/connectors/registry.py` sin tocar `SincronizarSorteos`
ni ningún otro caso de uso.
"""
from __future__ import annotations

from app.application.interfaces.draw_source_connector import (
    DrawDetail,
    DrawSourceConnector,
    DrawSummary,
    HealthStatus,
    SyncFetchResult,
)


class FutureApiConnector(DrawSourceConnector):
    def __init__(self, codigo_juego: str, base_url: str | None = None, api_key: str | None = None):
        self._codigo_juego = codigo_juego
        self._base_url = base_url
        self._api_key = api_key

    @property
    def game_code(self) -> str:
        return self._codigo_juego

    def fetch_draws(
        self, ultimo_conocido: int | None = None, max_paginas: int | None = None
    ) -> list[DrawSummary]:
        raise NotImplementedError("FutureApiConnector: pendiente de API oficial.")

    def fetch_draw_detail(self, draw_id: str) -> DrawDetail:
        raise NotImplementedError("FutureApiConnector: pendiente de API oficial.")

    def sync(
        self, ultimo_conocido: int | None = None, max_paginas: int | None = None
    ) -> SyncFetchResult:
        raise NotImplementedError("FutureApiConnector: pendiente de API oficial.")

    def health_check(self) -> HealthStatus:
        return HealthStatus(disponible=False, latencia_ms=None, mensaje="No implementado aún")
