"""Identidad del CODIGO de una generacion (E104-GEN-02), calculable tambien en la imagen minima de la API.

- `huella_app(raiz)`: SHA-256 del listado canonico `[ruta relativa "app/...", sha256]` de los `.py`, `.mako` y
  `.sql` del paquete `app/` (sin `__pycache__`). La imagen de la API copia `backend/app` entero (`.dockerignore`
  solo excluye bytecode y carpetas `privado/`), asi que el proceso que arranca recalcula la huella SOBRE SUS
  PROPIOS ARCHIVOS cargados, sin necesitar `alembic/` ni el arbol del capturador.
- `REVISION_ESQUEMA`: la revision de Alembic que este codigo exige. La imagen no lleva las migraciones; una
  prueba del repositorio exige que sea la cabeza de `alembic/versions`, y al arrancar se contrasta con la tabla
  `alembic_version` de la base conectada (no con una etiqueta).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REVISION_ESQUEMA = "0006"
SUFIJOS = (".py", ".mako", ".sql")


def archivos_de(raiz_app: Path) -> list[list[str]]:
    filas = []
    for ruta in sorted(raiz_app.rglob("*")):
        if ruta.is_file() and not ruta.is_symlink() and "__pycache__" not in ruta.parts and ruta.suffix in SUFIJOS:
            filas.append(["app/" + ruta.relative_to(raiz_app).as_posix(),
                          hashlib.sha256(ruta.read_bytes()).hexdigest()])
    return filas


def huella_app(raiz_app: Path) -> tuple[str, int]:
    filas = archivos_de(raiz_app)
    datos = json.dumps(filas, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    return hashlib.sha256(datos).hexdigest(), len(filas)


def raiz_de_esta_app() -> Path:
    """Carpeta del paquete `app` que este proceso ha importado (la de la imagen, en la imagen)."""
    import app
    return Path(app.__file__).resolve().parent
