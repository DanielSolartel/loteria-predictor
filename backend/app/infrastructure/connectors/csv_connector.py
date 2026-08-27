"""
CsvConnector.

Implementa exactamente el mismo puerto `DrawSourceConnector` que los
conectores de scraping, pero leyendo de un archivo CSV local. Existe
para demostrar -y dejar realmente disponible- que `SincronizarSorteos`
no sabe ni le importa si el origen es HTML remoto o un archivo local:
solo depende de la interfaz. Formato esperado (columnas mínimas):

    draw_id,numero_sorteo,fecha,numeros,superbalota,colores
    2689,2689,2026-07-29,"01-07-11-26-27",11,
    205,205,2026-07-30,"7-1-6-4-3-7",,"ROJO-AZUL-VERDE-AMARILLO-NEGRO-BLANCO"

`numeros` y `colores` separados por guiones, en el MISMO orden
(`colores[i]` es el color de `numeros[i]`) -mismo formato paralelo
que usa `DrawDetail` internamente, para ColorLoto. Para juegos sin
color, la columna `colores` se deja vacía. `numeros`/`superbalota`/
`colores` pueden ir vacías según el juego.
"""
from __future__ import annotations

import csv
import time
from datetime import date, datetime
from pathlib import Path

from app.application.interfaces.draw_source_connector import (
    DrawDetail,
    DrawFetchError,
    DrawSourceConnector,
    DrawSummary,
    HealthStatus,
    SyncFetchResult,
)


class CsvConnector(DrawSourceConnector):
    def __init__(self, ruta_csv: str, codigo_juego: str):
        self._ruta = Path(ruta_csv)
        self._codigo_juego = codigo_juego

    @property
    def game_code(self) -> str:
        return self._codigo_juego

    def _leer_filas(self) -> list[dict]:
        if not self._ruta.exists():
            return []
        with open(self._ruta, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def fetch_draws(
        self, ultimo_conocido: int | None = None, max_paginas: int | None = None
    ) -> list[DrawSummary]:
        resumenes = []
        for fila in self._leer_filas():
            numero_sorteo = int(fila["numero_sorteo"])
            if ultimo_conocido is not None and numero_sorteo <= ultimo_conocido:
                continue
            resumenes.append(
                DrawSummary(
                    draw_id=fila["draw_id"],
                    numero_sorteo=numero_sorteo,
                    fecha=datetime.strptime(fila["fecha"], "%Y-%m-%d").date(),
                )
            )
        return resumenes

    def fetch_draw_detail(self, draw_id: str) -> DrawDetail:
        for fila in self._leer_filas():
            if fila["draw_id"] == draw_id:
                return self._fila_a_detalle(fila)
        raise ValueError(f"draw_id '{draw_id}' no encontrado en {self._ruta}")

    def _fila_a_detalle(self, fila: dict) -> DrawDetail:
        numeros = tuple(int(n) for n in fila.get("numeros", "").split("-") if n.strip())
        superbalota = int(fila["superbalota"]) if fila.get("superbalota", "").strip() else None

        colores_txt = fila.get("colores", "").strip()
        colores: tuple[str | None, ...] = ()
        if colores_txt:
            colores = tuple(c.strip() or None for c in colores_txt.split("-"))
            if len(colores) != len(numeros):
                raise ValueError(
                    f"CSV inconsistente en draw_id={fila['draw_id']}: {len(numeros)} número(s) "
                    f"pero {len(colores)} color(es) -deben tener la misma cantidad."
                )

        return DrawDetail(
            draw_id=fila["draw_id"],
            numero_sorteo=int(fila["numero_sorteo"]),
            fecha=datetime.strptime(fila["fecha"], "%Y-%m-%d").date(),
            numeros=numeros,
            superbalota=superbalota,
            colores=colores,
            fuente_url=str(self._ruta),
        )

    def sync(
        self, ultimo_conocido: int | None = None, max_paginas: int | None = None
    ) -> SyncFetchResult:
        inicio = time.time()
        draws: list[DrawDetail] = []
        fallidos: list[DrawFetchError] = []

        for resumen in self.fetch_draws(ultimo_conocido):
            try:
                draws.append(self.fetch_draw_detail(resumen.draw_id))
            except Exception as e:
                fallidos.append(
                    DrawFetchError(draw_id=resumen.draw_id, numero_sorteo=resumen.numero_sorteo, error=str(e))
                )
                continue

        return SyncFetchResult(
            draws=draws, fallidos=fallidos, paginas_recorridas=1,
            duracion_ms=int((time.time() - inicio) * 1000),
        )

    def health_check(self) -> HealthStatus:
        if self._ruta.exists() and self._ruta.is_file():
            return HealthStatus(disponible=True, latencia_ms=0.0, mensaje=f"Archivo disponible: {self._ruta}")
        return HealthStatus(disponible=False, latencia_ms=None, mensaje=f"Archivo no encontrado: {self._ruta}")
