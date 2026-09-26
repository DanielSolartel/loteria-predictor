#!/usr/bin/env python3
"""AE-50, validada: CLI local, sin conexion y de solo lectura que
valida el formato y la coherencia interna de una o dos evidencias JSON
de AE-49.

No es prueba de autenticidad ni de procedencia, no consulta la base de
datos, no recalcula estadisticas y no ejecuta Monte Carlo. Los
archivos se leen en modo binario y nunca se modifican.

Uso (desde backend):
    python -m scripts.verificar_evidencia_montecarlo EVIDENCIA [EVIDENCIA_2]

Con dos rutas, cada archivo se valida por separado; si alguno falla se
devuelve el codigo de ese fallo (primero el del primer archivo). Solo
si ambos son validos se comparan sus bytes reales (no sus huellas):
identicos -> 0 (informe con `archivos_identicos`), distintos -> 6. El
SHA-256 de cada archivo es solo informativo. La igualdad de bytes no
demuestra por si sola la reproducibilidad del proceso.

Codigos: 0 valida; 1 fallo inesperado; 2 argumentos invalidos;
3 ilegible (no UTF-8, no JSON o NaN/Infinity); 4 formato invalido;
5 incoherencia interna; 6 dos evidencias validas pero distintas.
"""
from __future__ import annotations

import argparse
import sys

from scripts.comparacion_estado_prediccion import serializar_reporte
from scripts.verificacion_evidencia_montecarlo import (
    VerificacionEvidenciaError,
    construir_informe,
    validar_evidencia,
)

EXIT_VALIDA = 0
EXIT_FALLO_INESPERADO = 1
EXIT_ARGUMENTOS_INVALIDOS = 2
EXIT_ILEGIBLE = 3
EXIT_INVALIDA = 4
EXIT_INCOHERENTE = 5
EXIT_ARCHIVOS_DISTINTOS = 6


class _ArgumentosInvalidosError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ArgumentosInvalidosError(message)


def _error(etiqueta: str, mensaje) -> None:
    print(f"ERROR [{etiqueta}]: {mensaje}", file=sys.stderr)


def _leer_bytes(ruta: str) -> bytes:
    try:
        with open(ruta, "rb") as archivo:
            return archivo.read()
    except OSError as error:
        raise _LecturaFallidaError(f"No se pudo leer '{ruta}': {error}") from error


class _LecturaFallidaError(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description="Validacion de formato y coherencia interna de evidencias AE-49 (AE-50)")
    parser.add_argument("evidencias", nargs="+", metavar="EVIDENCIA")
    try:
        argumentos = parser.parse_args([] if argv is None else argv)
        if len(argumentos.evidencias) > 2:
            raise _ArgumentosInvalidosError("se admiten una o dos evidencias")
    except _ArgumentosInvalidosError as error:
        _error(f"codigo {EXIT_ARGUMENTOS_INVALIDOS}", error)
        return EXIT_ARGUMENTOS_INVALIDOS

    contenidos, resumenes = [], []
    try:
        for ruta in argumentos.evidencias:
            try:
                contenido = _leer_bytes(ruta)
                resumenes.append(validar_evidencia(contenido))
                contenidos.append(contenido)
            except _LecturaFallidaError as error:
                _error(f"codigo {EXIT_ILEGIBLE}", error)
                return EXIT_ILEGIBLE
            except VerificacionEvidenciaError as error:
                _error(f"codigo {error.codigo_salida}", f"'{ruta}': {error}")
                return error.codigo_salida
    except Exception as error:
        _error("inesperado", f"{type(error).__name__}: {error}")
        return EXIT_FALLO_INESPERADO

    bytes_identicos = None
    if len(contenidos) == 2:
        # Comparacion efectiva de los bytes leidos; el SHA-256 es solo informativo.
        bytes_identicos = contenidos[0] == contenidos[1]
        if not bytes_identicos:
            _error(f"codigo {EXIT_ARCHIVOS_DISTINTOS}",
                   "las dos evidencias son validas por separado pero sus bytes difieren")
            return EXIT_ARCHIVOS_DISTINTOS

    contenido = serializar_reporte(construir_informe(resumenes, bytes_identicos=bytes_identicos))
    sys.stdout.flush()
    sys.stdout.buffer.write(contenido)
    sys.stdout.buffer.flush()
    return EXIT_VALIDA


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
