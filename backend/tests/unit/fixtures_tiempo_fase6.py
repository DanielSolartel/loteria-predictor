"""Metadatos temporales representables, sin sleeps o desempates por nombre."""
import os

MARCA_BASE = 1_700_000_000_000_000_000
PASO = 2_000_000_000


def fijar_marca(ruta, orden):
    # Segundos pares desde una fecha representable por FILETIME. Separar
    # dos segundos evita depender de nanosegundos que el FS puede redondear.
    # Se comprueba el dato efectivamente recuperado, no solo el argumento.
    marca = MARCA_BASE + orden * PASO
    os.utime(ruta, ns=(marca, marca))
    assert ruta.stat().st_mtime_ns == marca
    return marca
