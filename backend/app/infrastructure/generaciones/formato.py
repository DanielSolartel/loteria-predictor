"""Formato comun de las generaciones (E10.4).

Un paquete de generacion es una carpeta:

    manifiesto.json      JSON canonico (claves ordenadas, sin espacios, UTF-8, LF final)
    manifiesto.firma     firma Ed25519 del manifiesto (hex, una linea)
    coherencia.json      detalle de la coherencia cruzada por artefacto (huella en el manifiesto)
    base/<tabla>.jsonl   filas de cada tabla, una por linea, en el orden de su clave primaria
    archivos/<almacen>/  copia exacta de los almacenes publicables (o de todos en un respaldo)

El manifiesto lista TODOS los demas archivos con su tamano y SHA-256: un archivo de mas, de menos o distinto
invalida el paquete. Ningun enlace simbolico ni ruta fuera del paquete se admite.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath

FORMATO = "generacion-e104/1"
FORMATO_RESPALDO = "respaldo-e104/1"
MANIFIESTO, FIRMA, COHERENCIA = "manifiesto.json", "manifiesto.firma", "coherencia.json"
BLOQUE = 1024 * 1024
_COMPONENTE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,199}$")
_ID = re.compile(r"^[0-9a-f]{32}$")


class GeneracionNoValida(ValueError):
    """El paquete o la generacion no cumple el formato, la integridad o la coherencia."""


def canonico(valor) -> bytes:
    return (json.dumps(valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            + "\n").encode("utf-8")


def sha256_bytes(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def sha256_archivo(ruta: Path) -> tuple[int, str]:
    h, total = hashlib.sha256(), 0
    with open(ruta, "rb") as f:
        while bloque := f.read(BLOQUE):
            h.update(bloque)
            total += len(bloque)
    return total, h.hexdigest()


def es_id(valor: str) -> bool:
    return bool(_ID.fullmatch(valor or ""))


def ruta_relativa_segura(texto: str) -> PurePosixPath:
    """Ruta relativa POSIX sin `..`, absolutas, barras invertidas ni nombres ocultos (los almacenes solo usan
    nombres ocultos para sus temporales, que nunca se copian)."""
    if not texto or "\\" in texto or texto.startswith("/") or "\x00" in texto:
        raise GeneracionNoValida(f"ruta no admitida: {texto!r}")
    ruta = PurePosixPath(texto)
    for parte in ruta.parts:
        if parte in (".", "..") or not _COMPONENTE.fullmatch(parte):
            raise GeneracionNoValida(f"ruta no admitida: {texto!r}")
    return ruta


def escribir_exclusivo(ruta: Path, datos: bytes) -> None:
    """Crea el archivo (falla si existe), escribe, vacia y sincroniza."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "xb") as f:
        f.write(datos)
        f.flush()
        os.fsync(f.fileno())


def leer_canonico(ruta: Path, maximo: int = 64 * 1024 * 1024) -> dict:
    datos = ruta.read_bytes()
    if len(datos) > maximo:
        raise GeneracionNoValida(f"{ruta.name}: demasiado grande")
    try:
        valor = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise GeneracionNoValida(f"{ruta.name}: JSON no valido") from error
    if not isinstance(valor, dict) or canonico(valor) != datos:
        raise GeneracionNoValida(f"{ruta.name}: no es JSON canonico")
    return valor


def sincronizar_carpeta(carpeta: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(carpeta, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
