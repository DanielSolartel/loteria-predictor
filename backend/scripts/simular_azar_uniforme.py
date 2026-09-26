#!/usr/bin/env python3
"""AE-49, validada: referencia Monte Carlo exploratoria bajo azar
uniforme para BALOTO y BALOTO_REVANCHA (primera etapa de la Fase 6).

Analisis exploratorio sobre datos reutilizados (2081..2705, ya
examinado en AE-36 a AE-39): no es confirmatorio, no esta
prerregistrado, no es evidencia prospectiva ni predictiva y no
modifica el NO-GO de AE-39. Rango, semilla, iteraciones, estadisticas
y familia de comparaciones son fijos: el unico argumento es
`--salida RUTA`; cualquier otro termina con codigo 7 antes de abrir
la conexion.

Lee el historico en una transaccion PostgreSQL de solo lectura
verificada (AE-42), comprueba la revision Alembic y termina siempre
con ROLLBACK. No persiste nada y no tiene ruta web ni tarea
automatica. Con `--salida`, los mismos bytes van al archivo
(publicacion exclusiva de AE-48) y a stdout, y la huella SHA-256 solo
a stderr.

Ejecutar desde backend: python -m scripts.simular_azar_uniforme
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.simulaciones.montecarlo_uniforme import EntradaSimulacionInvalidaError
from app.application.use_cases.simular_referencia_azar_uniforme import SimularReferenciaAzarUniforme
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
    ResultadosHistoricosRepositorySQLAlchemy,
)
from scripts.auditoria_operativa_bloqueo import (
    FalloAuditoriaOperativaError,
    verificar_revision_alembic,
    verificar_transaccion_solo_lectura,
)
from scripts.comparacion_estado_prediccion import (
    EscrituraEvidenciaError,
    RutaSalidaNoPermitidaError,
    escribir_evidencia_atomica,
    serializar_reporte,
    validar_ruta_salida,
)

EXIT_OK = 0
EXIT_FALLO_INESPERADO = 1
EXIT_FALLO_CONEXION = 2
EXIT_REVISION_ALEMBIC_INESPERADA = 3
EXIT_TRANSACCION_NO_SOLO_LECTURA = 4
EXIT_ENTRADA_INVALIDA = 5
EXIT_FALLO_SIMULANDO = 6
EXIT_ARGUMENTOS_INVALIDOS = 7
EXIT_FALLO_ESCRITURA_SALIDA = 8
EXIT_RUTA_SALIDA_NO_PERMITIDA = 9


class _ArgumentosInvalidosError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """argparse termina con codigo 2 ante un error, que aqui significa
    fallo de conexion: se convierte en el codigo 7."""

    def error(self, message):
        raise _ArgumentosInvalidosError(message)


def _abrir_conexion():
    from app.infrastructure.db.session import engine

    return engine.connect()


def _crear_caso_uso(session: Session) -> SimularReferenciaAzarUniforme:
    """Siempre con la semilla y las iteraciones fijadas de AE-49."""
    return SimularReferenciaAzarUniforme(
        JuegoRepositorySQLAlchemy(session), ResultadosHistoricosRepositorySQLAlchemy(session),
    )


def _error(etiqueta: str, mensaje) -> None:
    print(f"ERROR [{etiqueta}]: {mensaje}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description="Referencia Monte Carlo exploratoria AE-49 (solo lectura)")
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

    try:
        conexion = _abrir_conexion()
    except Exception as error:
        _error("conexion", f"{type(error).__name__}: {error}")
        return EXIT_FALLO_CONEXION

    try:
        conexion.execute(text("BEGIN TRANSACTION READ ONLY"))
        session = Session(bind=conexion)
        try:
            verificar_transaccion_solo_lectura(session)
            revision = verificar_revision_alembic(session)
            caso_uso = _crear_caso_uso(session)
            try:
                reporte = caso_uso.ejecutar(revision)
            except EntradaSimulacionInvalidaError:
                raise
            except Exception as error:
                raise _FalloSimulandoError(f"{type(error).__name__}: {error}") from error
        finally:
            session.close()
            conexion.execute(text("ROLLBACK"))
    except FalloAuditoriaOperativaError as error:
        _error(f"codigo {error.codigo_salida}", error)
        return error.codigo_salida
    except EntradaSimulacionInvalidaError as error:
        _error(f"codigo {EXIT_ENTRADA_INVALIDA}", error)
        return EXIT_ENTRADA_INVALIDA
    except _FalloSimulandoError as error:
        _error(f"codigo {EXIT_FALLO_SIMULANDO}", error)
        return EXIT_FALLO_SIMULANDO
    except Exception as error:
        _error("inesperado", f"{type(error).__name__}: {error}")
        return EXIT_FALLO_INESPERADO
    finally:
        conexion.close()

    contenido = serializar_reporte(reporte)
    huella = None
    if argumentos.salida is not None:
        try:
            huella = escribir_evidencia_atomica(contenido, argumentos.salida)
        except EscrituraEvidenciaError as error:
            _error(f"codigo {EXIT_FALLO_ESCRITURA_SALIDA}", error)
            return EXIT_FALLO_ESCRITURA_SALIDA
    sys.stdout.flush()
    sys.stdout.buffer.write(contenido)
    sys.stdout.buffer.flush()
    if huella is not None:
        print(f"SHA-256 {huella}  {argumentos.salida}  ({len(contenido)} bytes)", file=sys.stderr)
    return EXIT_OK


class _FalloSimulandoError(Exception):
    pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
