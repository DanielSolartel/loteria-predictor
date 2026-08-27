"""
Logging del módulo de importación.

Un único logger nombrado "importacion", configurado una sola vez,
usado por todos los conectores y por `SincronizarSorteos`. El
archivo rotativo permite que "Ver logs" en el dashboard simplemente
lea las últimas N líneas sin preocuparse por que el archivo crezca
sin límite.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_PATH = Path("storage/logs/sync.log")
_configurado = False


def get_import_logger() -> logging.Logger:
    global _configurado
    logger = logging.getLogger("importacion")

    if not _configurado:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.setLevel(logging.INFO)

        formato = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        file_handler = RotatingFileHandler(_LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formato)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formato)
        logger.addHandler(console_handler)

        _configurado = True

    return logger


def leer_ultimas_lineas(n: int = 200) -> list[str]:
    if not _LOG_PATH.exists():
        return []
    with open(_LOG_PATH, encoding="utf-8") as f:
        lineas = f.readlines()
    return lineas[-n:]
