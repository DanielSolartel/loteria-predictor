#!/usr/bin/env python3
"""AE-51, validada: CLI que audita una evidencia JSON de AE-49 frente
al historico actual 2081..2705 de BALOTO y BALOTO_REVANCHA en PostgreSQL.

1. Valida el archivo con AE-50 antes de abrir la conexion.
2. Abre una transaccion READ ONLY, la verifica (AE-42), comprueba la
   revision Alembic y lee solo hasta 2705; termina siempre con ROLLBACK.
3. Compara huella normalizada de entrada, totales y estadisticas
   observadas (`scripts/auditoria_evidencia_montecarlo.py`).

No repite Monte Carlo, no escribe nada y no prueba la procedencia
historica del archivo. El resultado es exploratorio y no modifica el
NO-GO de AE-39.

Uso (desde backend): python -m scripts.auditar_evidencia_montecarlo EVIDENCIA

Codigos: 0 coincide; 1 fallo inesperado; 2 argumentos invalidos;
3/4/5 evidencia rechazada por AE-50 (ilegible, formato invalido,
incoherencia interna); 6 conexion; 7 revision Alembic inesperada;
8 transaccion no READ ONLY; 9 historico actual o parametros fuera del
contrato de AE-49; 10 no coincide (el informe se publica igualmente en
stdout).
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.simulaciones.montecarlo_uniforme import EntradaSimulacionInvalidaError
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
    ResultadosHistoricosRepositorySQLAlchemy,
)
from scripts.auditoria_evidencia_montecarlo import (
    auditar_contra_historico,
    construir_informe_auditoria,
    leer_evidencia_validada,
)
from scripts.auditoria_operativa_bloqueo import (
    EXIT_REVISION_ALEMBIC_INESPERADA as _AE42_REVISION,
    EXIT_TRANSACCION_NO_SOLO_LECTURA as _AE42_SOLO_LECTURA,
    FalloAuditoriaOperativaError,
    verificar_revision_alembic,
    verificar_transaccion_solo_lectura,
)
from scripts.comparacion_estado_prediccion import serializar_reporte
from scripts.verificacion_evidencia_montecarlo import VerificacionEvidenciaError

EXIT_COINCIDE = 0
EXIT_FALLO_INESPERADO = 1
EXIT_ARGUMENTOS_INVALIDOS = 2
EXIT_ILEGIBLE = 3
EXIT_INVALIDA = 4
EXIT_INCOHERENTE = 5
EXIT_FALLO_CONEXION = 6
EXIT_REVISION_ALEMBIC_INESPERADA = 7
EXIT_TRANSACCION_NO_SOLO_LECTURA = 8
EXIT_HISTORICO_INVALIDO = 9
EXIT_NO_COINCIDE = 10

_CODIGOS_AE42 = {
    _AE42_REVISION: EXIT_REVISION_ALEMBIC_INESPERADA,
    _AE42_SOLO_LECTURA: EXIT_TRANSACCION_NO_SOLO_LECTURA,
}
"""AE-42 usa 3 y 4, que aqui ya significan fallos de AE-50."""


class _ArgumentosInvalidosError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ArgumentosInvalidosError(message)


def _error(etiqueta: str, mensaje) -> None:
    print(f"ERROR [{etiqueta}]: {mensaje}", file=sys.stderr)


def _abrir_conexion():
    from app.infrastructure.db.session import engine

    return engine.connect()


def _crear_repositorios(session: Session):
    return JuegoRepositorySQLAlchemy(session), ResultadosHistoricosRepositorySQLAlchemy(session)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description="Auditoria AE-51 de una evidencia AE-49 frente al historico actual (solo lectura)")
    parser.add_argument("evidencia", metavar="EVIDENCIA")
    try:
        argumentos = parser.parse_args([] if argv is None else argv)
    except _ArgumentosInvalidosError as error:
        _error(f"codigo {EXIT_ARGUMENTOS_INVALIDOS}", error)
        return EXIT_ARGUMENTOS_INVALIDOS

    try:
        with open(argumentos.evidencia, "rb") as archivo:
            contenido = archivo.read()
    except OSError as error:
        _error(f"codigo {EXIT_ILEGIBLE}", f"No se pudo leer '{argumentos.evidencia}': {error}")
        return EXIT_ILEGIBLE
    try:
        resumen, reporte = leer_evidencia_validada(contenido)
    except VerificacionEvidenciaError as error:
        _error(f"codigo {error.codigo_salida}", error)
        return error.codigo_salida

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
            juego_repository, resultados_repository = _crear_repositorios(session)
            juegos = auditar_contra_historico(reporte, juego_repository, resultados_repository)
        finally:
            session.close()
            conexion.execute(text("ROLLBACK"))
    except FalloAuditoriaOperativaError as error:
        codigo = _CODIGOS_AE42.get(error.codigo_salida, EXIT_FALLO_INESPERADO)
        _error(f"codigo {codigo}", error)
        return codigo
    except EntradaSimulacionInvalidaError as error:
        _error(f"codigo {EXIT_HISTORICO_INVALIDO}", error)
        return EXIT_HISTORICO_INVALIDO
    except Exception as error:
        _error("inesperado", f"{type(error).__name__}: {error}")
        return EXIT_FALLO_INESPERADO
    finally:
        conexion.close()

    informe = construir_informe_auditoria(resumen, reporte, juegos, revision)
    sys.stdout.flush()
    sys.stdout.buffer.write(serializar_reporte(informe))
    sys.stdout.buffer.flush()
    if informe["resultado"] != "coincide":
        _error(f"codigo {EXIT_NO_COINCIDE}", "la evidencia no coincide con el historico actual (ver informe)")
        return EXIT_NO_COINCIDE
    return EXIT_COINCIDE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
