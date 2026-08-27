"""
Registro de conectores.

Equivalente a `GameFactory` pero para el origen de datos: dado un
código de juego, devuelve el `DrawSourceConnector` configurado que
le corresponde. Es el único lugar del sistema que sabe qué conector
concreto usa cada juego -`SincronizarSorteos` solo recibe la interfaz.
Reemplazar Baloto Revancha por una futura API oficial es cambiar una
línea aquí, no tocar el caso de uso.
"""
from __future__ import annotations

from app.application.interfaces.draw_source_connector import DrawSourceConnector
from app.application.interfaces.html_storage import HtmlStorage
from app.core.config import get_settings
from app.infrastructure.connectors.baloto_connector import BalotoConnector
from app.infrastructure.connectors.baloto_revancha_connector import BalotoRevanchaConnector
from app.infrastructure.connectors.colorloto_connector import ColorLotoConnector
from app.infrastructure.connectors.manual_connector import ManualConnector
from app.infrastructure.connectors.miloto_connector import MiLotoConnector


class ConnectorRegistry:
    def __init__(self, html_storage: HtmlStorage):
        self._html_storage = html_storage
        max_paginas_absoluto = get_settings().max_paginas_absoluto_conectores
        self._conectores: dict[str, DrawSourceConnector] = {
            "BALOTO": BalotoConnector(
                html_storage=html_storage, max_paginas_absoluto=max_paginas_absoluto
            ),
            "BALOTO_REVANCHA": BalotoRevanchaConnector(
                html_storage=html_storage, max_paginas_absoluto=max_paginas_absoluto
            ),
            "MILOTO": MiLotoConnector(
                html_storage=html_storage, max_paginas_absoluto=max_paginas_absoluto
            ),
            "COLORLOTO": ColorLotoConnector(
                html_storage=html_storage, max_paginas_absoluto=max_paginas_absoluto
            ),
        }

    def obtener(self, codigo_juego: str) -> DrawSourceConnector:
        return self._conectores.get(codigo_juego, ManualConnector(codigo_juego))
