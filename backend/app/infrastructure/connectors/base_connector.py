"""
BaseConnector.

Implementa `fetch_draws`, `sync` y `health_check` UNA sola vez
(patrón Template Method), porque la lógica de paginar, reintentar
con backoff, medir tiempos, guardar el HTML crudo y tolerar fallos
por sorteo es idéntica para MiLoto, Baloto Revancha y ColorLoto -lo
único que cambia entre ellos son las URLs y cómo se parsea el HTML
de cada uno. Esto evita triplicar la lógica de scraping (requisito
explícito de "no generes código duplicado").

Las subclases concretas (`BalotoRevanchaConnector`, etc.) solo
implementan:
  - `_url_listado(pagina)` / `_url_detalle(draw_id)`
  - `_parsear_pagina_listado(html)` -> (resúmenes, hay_siguiente)
  - `_parsear_pagina_detalle(html, draw_id, url)` -> DrawDetail

y delegan ese parseo a un módulo de `infrastructure/parsers`, nunca
a lógica embebida aquí -así el conector es "cómo llegar al dato" y
el parser es "qué significa el dato".
"""
from __future__ import annotations

import time
from abc import abstractmethod
from datetime import datetime, timezone

import requests

from app.application.interfaces.draw_source_connector import (
    DrawDetail,
    DrawFetchError,
    DrawSourceConnector,
    DrawSummary,
    HealthStatus,
    SyncFetchResult,
)
from app.application.interfaces.html_storage import HtmlStorage
from app.infrastructure.logging_config import get_import_logger

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SistemaPredictivoLoterias/1.0; "
        "+https://github.com/tu-usuario/loteria-predictor)"
    )
}


class ConectorFetchError(Exception):
    """Se agotaron los reintentos al pedir una URL."""


class BaseConnector(DrawSourceConnector):
    #: prefijo usado en el nombre de archivo del HTML guardado, p.ej. "baloto"
    storage_prefix: str = "generico"

    def __init__(
        self,
        html_storage: HtmlStorage,
        session: requests.Session | None = None,
        max_reintentos: int = 3,
        timeout_segundos: int = 15,
        pausa_entre_peticiones: float = 0.6,
        max_paginas_absoluto: int = 500,
    ):
        self._html_storage = html_storage
        self._session = session or requests.Session()
        self._session.headers.update(_HEADERS)
        self._max_reintentos = max_reintentos
        self._timeout = timeout_segundos
        self._pausa = pausa_entre_peticiones
        self._max_paginas_absoluto = max_paginas_absoluto
        self._logger = get_import_logger()
        self._ultimas_paginas_leidas = 0

    # ------------------------------------------------------------------
    # Ganchos que cada conector concreto debe implementar
    # ------------------------------------------------------------------
    @abstractmethod
    def _url_listado(self, pagina: int) -> str: ...

    @abstractmethod
    def _url_detalle(self, draw_id: str) -> str: ...

    @abstractmethod
    def _parsear_pagina_listado(self, html: str) -> tuple[list[DrawSummary], bool]:
        """-> (resúmenes de esta página, hay_pagina_siguiente)"""

    @abstractmethod
    def _parsear_pagina_detalle(self, html: str, draw_id: str, url: str) -> DrawDetail: ...

    # ------------------------------------------------------------------
    # HTTP con reintentos y backoff exponencial
    # ------------------------------------------------------------------
    def _get(self, url: str) -> str:
        ultimo_error: Exception | None = None
        for intento in range(1, self._max_reintentos + 1):
            try:
                respuesta = self._session.get(url, timeout=self._timeout)
                respuesta.raise_for_status()
                if self._pausa:
                    time.sleep(self._pausa)  # cortesía con el servidor origen
                return respuesta.text
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                ultimo_error = e
                espera = self._pausa * (2**intento)
                self._logger.warning(
                    "[ERROR_CONEXION] %s en %s (intento %d/%d): %s. Reintentando en %.1fs",
                    type(e).__name__, url, intento, self._max_reintentos, e, espera,
                )
                time.sleep(espera)
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                self._logger.error("[ERROR_HTTP] Código %s en %s", status, url)
                if status is not None and 400 <= status < 500:
                    raise ConectorFetchError(f"Error HTTP {status} en {url}") from e
                ultimo_error = e
                time.sleep(self._pausa * (2**intento))

        raise ConectorFetchError(
            f"Se agotaron los {self._max_reintentos} reintentos para {url}: {ultimo_error}"
        )

    # ------------------------------------------------------------------
    # Implementación compartida del puerto
    # ------------------------------------------------------------------
    def fetch_draws(self, ultimo_conocido: int | None = None, max_paginas: int | None = None) -> list[DrawSummary]:
        resumenes: list[DrawSummary] = []
        pagina = 1
        paginas_leidas = 0
        limite = min(max_paginas or self._max_paginas_absoluto, self._max_paginas_absoluto)

        while pagina <= limite:
            html = self._get(self._url_listado(pagina))
            paginas_leidas += 1
            pagina_resumenes, hay_siguiente = self._parsear_pagina_listado(html)

            if not pagina_resumenes:
                self._logger.info("Página %d sin sorteos reconocibles; se detiene el descubrimiento.", pagina)
                break

            detenerse = False
            for resumen in pagina_resumenes:
                if ultimo_conocido is not None and resumen.numero_sorteo <= ultimo_conocido:
                    detenerse = True
                    continue
                resumenes.append(resumen)

            if detenerse:
                self._logger.info(
                    "Se alcanzó el último sorteo conocido (#%s) en la página %d; "
                    "sincronización incremental detenida.", ultimo_conocido, pagina,
                )
                break
            if not hay_siguiente:
                break
            pagina += 1

        self._logger.info("%s: %d sorteo(s) nuevos descubiertos en %d página(s).",
                           self.game_code, len(resumenes), paginas_leidas)
        self._ultimas_paginas_leidas = paginas_leidas
        return resumenes

    def fetch_draw_detail(self, draw_id: str) -> DrawDetail:
        url = self._url_detalle(draw_id)
        html = self._get(url)
        self._html_storage.guardar(self.storage_prefix, draw_id, html)
        return self._parsear_pagina_detalle(html, draw_id, url)

    def reprocesar_html(self, draw_id: str) -> DrawDetail:
        """Reconstruye el `DrawDetail` de un sorteo a partir del HTML
        ya almacenado en disco, sin tocar la red. Llama al MISMO
        hook de parseo (`_parsear_pagina_detalle`) que usa
        `fetch_draw_detail` -por diseño, no existe una ruta de
        parseo alternativa para "reprocesar": es literalmente la
        misma función, solo que alimentada con HTML leído del disco
        en vez de recién descargado. Esto es lo que garantiza que
        reprocesar nunca produzca un resultado distinto al que se
        habría obtenido sincronizando en vivo con ese mismo HTML."""
        html = self._html_storage.leer(self.storage_prefix, draw_id)
        if html is None:
            raise ValueError(
                f"No hay HTML almacenado para draw_id='{draw_id}' (prefijo='{self.storage_prefix}'). "
                f"Solo se puede reprocesar lo que ya se descargó al menos una vez."
            )
        return self._parsear_pagina_detalle(html, draw_id, self._url_detalle(draw_id))

    def listar_html_disponibles(self) -> list[str]:
        """draw_id de todos los HTML almacenados para este conector.
        Es la lista de candidatos para una reconstrucción completa
        de la base de datos a partir de storage/html/."""
        return self._html_storage.listar(self.storage_prefix)

    def sync(self, ultimo_conocido: int | None = None, max_paginas: int | None = None) -> SyncFetchResult:
        inicio = time.time()
        resumenes = self.fetch_draws(ultimo_conocido, max_paginas=max_paginas)

        draws: list[DrawDetail] = []
        fallidos: list[DrawFetchError] = []

        for resumen in resumenes:
            try:
                detalle = self.fetch_draw_detail(resumen.draw_id)
                draws.append(detalle)
            except Exception as e:  # nunca detener toda la sincronización por un sorteo
                self._logger.error("[ERROR_OBTENCION] Fallo al importar sorteo %s (%s): %s", resumen.draw_id, self.game_code, e)
                fallidos.append(
                    DrawFetchError(draw_id=resumen.draw_id, numero_sorteo=resumen.numero_sorteo, error=str(e))
                )
                continue

        duracion_ms = int((time.time() - inicio) * 1000)
        return SyncFetchResult(
            draws=draws, fallidos=fallidos,
            paginas_recorridas=self._ultimas_paginas_leidas, duracion_ms=duracion_ms,
        )

    def health_check(self) -> HealthStatus:
        inicio = time.time()
        try:
            self._get(self._url_listado(1))
            return HealthStatus(
                disponible=True, latencia_ms=(time.time() - inicio) * 1000, mensaje="Origen disponible"
            )
        except Exception as e:
            return HealthStatus(disponible=False, latencia_ms=None, mensaje=str(e))
