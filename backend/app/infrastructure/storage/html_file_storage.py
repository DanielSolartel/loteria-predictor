from __future__ import annotations

import re
from pathlib import Path

from app.application.interfaces.html_storage import HtmlStorage

_DRAW_ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]+$")


class HtmlFileStorage(HtmlStorage):
    def __init__(self, base_dir: str = "storage/html"):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _ruta(self, prefijo: str, draw_id: str) -> Path:
        # Defensa en profundidad: draw_id siempre es numérico en la
        # práctica (viene de un regex \d+ en los parsers), pero se
        # valida explícitamente antes de construir una ruta de
        # archivo -un conector futuro mal escrito no debería poder
        # escapar de storage/html/ vía "../" en el draw_id.
        if not _DRAW_ID_VALIDO.match(draw_id) or not _DRAW_ID_VALIDO.match(prefijo):
            raise ValueError(f"draw_id o prefijo con caracteres no permitidos: {prefijo!r}, {draw_id!r}")
        return self._base_dir / f"{prefijo}_{draw_id}.html"

    def guardar(self, prefijo: str, draw_id: str, html: str) -> str:
        ruta = self._ruta(prefijo, draw_id)
        ruta.write_text(html, encoding="utf-8")
        return str(ruta)

    def leer(self, prefijo: str, draw_id: str) -> str | None:
        ruta = self._ruta(prefijo, draw_id)
        if not ruta.exists():
            return None
        return ruta.read_text(encoding="utf-8")

    def listar(self, prefijo: str) -> list[str]:
        patron = f"{prefijo}_*.html"
        draw_ids = []
        for archivo in self._base_dir.glob(patron):
            nombre = archivo.stem  # p.ej. "baloto_2689"
            draw_ids.append(nombre[len(prefijo) + 1:])
        return sorted(draw_ids)
