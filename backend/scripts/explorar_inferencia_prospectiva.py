#!/usr/bin/env python3
"""AE-54, validada: ejecuta una vez el banco exploratorio sintetico de
metodos candidatos de inferencia con los parametros fijos del modulo.

Sin base de datos, sin red y sin datos reales. No tiene opciones de
parametros: solo `--salida RUTA`, un archivo nuevo donde se guardan los
bytes exactos del JSON (nunca se sobrescribe). El JSON no incluye
tiempos, para ser reproducible en el mismo entorno; la duracion se
informa en stderr. Los resultados son exploratorios: no aprueban una
regla prospectiva ni autorizan un GO.

Uso (desde backend): python -m scripts.explorar_inferencia_prospectiva [--salida RUTA]

Codigos: 0 correcto; 1 fallo inesperado; 2 argumentos invalidos;
8 fallo al escribir la salida; 9 ruta de salida no permitida.
"""
from __future__ import annotations

import argparse
import sys
import time

from app.application.simulaciones import exploracion_inferencia_prospectiva as exploracion
from scripts.comparacion_estado_prediccion import (
    EscrituraEvidenciaError,
    RutaSalidaNoPermitidaError,
    escribir_evidencia_atomica,
    serializar_reporte,
    validar_ruta_salida,
)

EXIT_OK = 0
EXIT_FALLO_INESPERADO = 1
EXIT_ARGUMENTOS_INVALIDOS = 2
EXIT_FALLO_ESCRITURA = 8
EXIT_RUTA_SALIDA_NO_PERMITIDA = 9


class _ArgumentosInvalidosError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ArgumentosInvalidosError(message)


def _error(etiqueta: str, mensaje) -> None:
    print(f"ERROR [{etiqueta}]: {mensaje}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description="Banco exploratorio sintetico AE-54 (sin base de datos)")
    parser.add_argument("--salida", help="Archivo nuevo donde guardar los bytes exactos del JSON")
    try:
        argumentos = parser.parse_args([] if argv is None else argv)
        if argumentos.salida is not None:
            validar_ruta_salida(argumentos.salida, None)
    except _ArgumentosInvalidosError as error:
        _error(f"codigo {EXIT_ARGUMENTOS_INVALIDOS}", error)
        return EXIT_ARGUMENTOS_INVALIDOS
    except RutaSalidaNoPermitidaError as error:
        _error(f"codigo {EXIT_RUTA_SALIDA_NO_PERMITIDA}", error)
        return EXIT_RUTA_SALIDA_NO_PERMITIDA

    inicio = time.perf_counter()
    try:
        reporte = exploracion.ejecutar_exploracion(exploracion.PARAMETROS_AE54)
    except Exception as error:
        _error("inesperado", f"{type(error).__name__}: {error}")
        return EXIT_FALLO_INESPERADO
    duracion = time.perf_counter() - inicio

    contenido = serializar_reporte(reporte)
    huella = None
    if argumentos.salida is not None:
        try:
            huella = escribir_evidencia_atomica(contenido, argumentos.salida)
        except EscrituraEvidenciaError as error:
            _error(f"codigo {EXIT_FALLO_ESCRITURA}", error)
            return EXIT_FALLO_ESCRITURA
    sys.stdout.flush()
    sys.stdout.buffer.write(contenido)
    sys.stdout.buffer.flush()
    print(f"AE-54 exploratorio sintetico: duracion_s={duracion:.1f}", file=sys.stderr)
    if huella is not None:
        print(f"SHA-256 {huella}  {argumentos.salida}  ({len(contenido)} bytes)", file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
