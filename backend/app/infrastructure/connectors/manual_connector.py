"""
ManualConnector.

La entrada manual ya está resuelta por el formulario web del MVP
(`RegistrarSorteo` invocado directamente desde `api/web/routers/sorteos.py`)
-no necesita pasar por `SincronizarSorteos`. Este conector existe
únicamente para que el registro de conectores sea uniforme (todo
juego tiene un conector, aunque sea trivial) y para dejar un punto
de extensión documentado si en el futuro se quiere, por ejemplo,
importar un lote manual vía este mismo mecanismo.
"""
from __future__ import annotations

from app.application.interfaces.draw_source_connector import (
    DrawDetail,
    DrawSourceConnector,
    DrawSummary,
    HealthStatus,
    SyncFetchResult,
)


class ManualConnector(DrawSourceConnector):
    def __init__(self, codigo_juego: str):
        self._codigo_juego = codigo_juego

    @property
    def game_code(self) -> str:
        return self._codigo_juego

    def fetch_draws(
        self, ultimo_conocido: int | None = None, max_paginas: int | None = None
    ) -> list[DrawSummary]:
        return []

    def fetch_draw_detail(self, draw_id: str) -> DrawDetail:
        raise NotImplementedError(
            "ManualConnector no obtiene detalles automáticamente; usa el formulario "
            "de registro manual en /sorteos/nuevo."
        )

    def sync(
        self, ultimo_conocido: int | None = None, max_paginas: int | None = None
    ) -> SyncFetchResult:
        return SyncFetchResult()

    def health_check(self) -> HealthStatus:
        return HealthStatus(disponible=True, latencia_ms=0.0, mensaje="Entrada manual, sin origen externo")
