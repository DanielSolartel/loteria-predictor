"""Registro personal de apuestas de escritorio, en un archivo del perfil local."""
from __future__ import annotations

from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import stat


class AlmacenApuestasError(RuntimeError):
    pass


class ApuestasSQLite:
    def __init__(self, archivo: Path):
        self._archivo = archivo.absolute()

    def _existe(self) -> bool:
        existe = False
        for sufijo in ("", "-journal", "-wal", "-shm"):
            ruta = self._archivo.with_name(self._archivo.name + sufijo)
            try:
                estado = ruta.lstat()
            except FileNotFoundError:
                continue
            except OSError as error:
                raise AlmacenApuestasError("Ruta de apuestas no disponible") from error
            atributos = getattr(estado, "st_file_attributes", 0)
            if not stat.S_ISREG(estado.st_mode) or atributos & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise AlmacenApuestasError("Ruta de apuestas no válida")
            if not sufijo:
                existe = True
        return existe

    @contextmanager
    def _conexion(self, modo: str):
        uri = self._archivo.as_uri() + f"?mode={modo}"
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None,
                                        autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL)) as db, db:
                db.execute("BEGIN IMMEDIATE" if modo == "rwc" else "BEGIN")
                yield db
        except (sqlite3.Error, OSError, ValueError) as error:
            raise AlmacenApuestasError("Registro de apuestas no disponible") from error

    @staticmethod
    def _hay_registro(db: sqlite3.Connection) -> bool:
        # Una lectura puede coincidir con la primera transacción, antes de que se publique la tabla.
        return db.execute("SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'apuestas'").fetchone() is not None

    def buscar(self, identificador: str) -> dict | None:
        if not self._existe():
            return None
        with self._conexion("ro") as db:
            if not self._hay_registro(db):
                return None
            fila = db.execute("SELECT datos FROM apuestas WHERE id = ?", (identificador,)).fetchone()
            return json.loads(fila[0]) if fila else None

    def guardar(self, apuesta: dict) -> dict:
        self._existe()
        with self._conexion("rwc") as db:
            db.execute("CREATE TABLE IF NOT EXISTS apuestas (id TEXT PRIMARY KEY, registrada_en TEXT NOT NULL, datos TEXT NOT NULL)")
            db.execute("""
                INSERT INTO apuestas (id, registrada_en, datos) VALUES (?, ?, ?)
                ON CONFLICT(id) DO NOTHING
            """, (apuesta["id"], apuesta["registrada_en"], json.dumps(apuesta, ensure_ascii=False)))
            fila = db.execute("SELECT datos FROM apuestas WHERE id = ?", (apuesta["id"],)).fetchone()
            return json.loads(fila[0])

    def listar(self, pagina: int, por_pagina: int) -> tuple[list[dict], int]:
        if not self._existe():
            return [], 0
        with self._conexion("ro") as db:
            if not self._hay_registro(db):
                return [], 0
            total = db.execute("SELECT count(*) FROM apuestas").fetchone()[0]
            filas = db.execute("""
                SELECT datos FROM apuestas ORDER BY registrada_en DESC, id DESC LIMIT ? OFFSET ?
            """, (por_pagina, (pagina - 1) * por_pagina))
            return [json.loads(fila[0]) for fila in filas], total
