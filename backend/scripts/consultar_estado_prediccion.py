#!/usr/bin/env python3
"""AE-45, validada: consulta manual del estado bloqueado de AE-44.

Solo lee metadatos agregados de sorteos en una transaccion PostgreSQL
de solo lectura verificada. No se ejecuta al iniciar la aplicacion,
no tiene ruta web/API, no observa numeros ganadores y no persiste.
Publica un JSON por stdout solamente si ambos juegos se evaluaron y
sus reportes son coherentes. Un bloqueo valido termina con codigo 0.

Ejecutar desde backend: python -m scripts.consultar_estado_prediccion
"""
from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import EstadoPrediccionML, ReportePrediccionJuego
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML
from app.application.use_cases.resolver_estado_prediccion import ResolverEstadoPrediccion
from app.infrastructure.repositories.disponibilidad_holdout_repository_sqlalchemy import (
    DisponibilidadHoldoutRepositorySQLAlchemy,
)
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from scripts.auditoria_operativa_bloqueo import (
    FalloAuditoriaOperativaError,
    verificar_revision_alembic,
    verificar_transaccion_solo_lectura,
)

EXIT_OK = 0
EXIT_FALLO_INESPERADO = 1
EXIT_FALLO_CONEXION = 2
EXIT_REVISION_ALEMBIC_INESPERADA = 3
EXIT_TRANSACCION_NO_SOLO_LECTURA = 4
EXIT_REPORTE_INCONSISTENTE = 5
EXIT_FALLO_EVALUANDO_JUEGO = 6
ESTADOS_BLOQUEADOS_AE45 = frozenset({
    EstadoPrediccionML.BLOQUEADO_NUMERACION_INVALIDA,
    EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES,
    EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO,
    EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT,
})


class FalloConsultaEstadoError(Exception):
    def __init__(self, mensaje: str, codigo_salida: int):
        super().__init__(mensaje)
        self.codigo_salida = codigo_salida


def construir_reporte(resolver: ResolverEstadoPrediccion, revision_alembic: str) -> dict:
    """Consulta ambos juegos antes de construir el JSON, sin salida parcial."""
    juegos = []
    for codigo in sorted(JUEGOS_AUTORIZADOS_AE40):
        try:
            reporte = resolver.ejecutar(codigo)
        except Exception as error:
            raise FalloConsultaEstadoError(
                f"Error evaluando '{codigo}': {type(error).__name__}: {error}",
                EXIT_FALLO_EVALUANDO_JUEGO,
            ) from error

        if not isinstance(reporte, ReportePrediccionJuego):
            raise FalloConsultaEstadoError(
                f"Reporte inconsistente para '{codigo}': tipo inesperado",
                EXIT_REPORTE_INCONSISTENTE,
            )
        if reporte.juego_codigo != codigo:
            raise FalloConsultaEstadoError(
                f"Reporte inconsistente: '{reporte.juego_codigo}' devuelto para '{codigo}'",
                EXIT_REPORTE_INCONSISTENTE,
            )
        if reporte.estado not in ESTADOS_BLOQUEADOS_AE45 or any(
            motivo not in ESTADOS_BLOQUEADOS_AE45 for motivo in reporte.motivos
        ):
            raise FalloConsultaEstadoError(
                f"Reporte inconsistente para '{codigo}': estado no bloqueado",
                EXIT_REPORTE_INCONSISTENTE,
            )
        if (
            reporte.combinaciones or reporte.numeros_fuertes or reporte.numeros_debiles
            or reporte.probabilidades or reporte.nivel_confianza is not None
            or reporte.resultados_observados or reporte.modelos_entrenados
            or reporte.predicciones_generadas or reporte.holdout_consumido
        ):
            raise FalloConsultaEstadoError(
                f"Reporte inconsistente para '{codigo}': contiene salida predictiva",
                EXIT_REPORTE_INCONSISTENTE,
            )
        juegos.append({
            "codigo": codigo,
            "estado": reporte.estado.value,
            "motivos": [motivo.value for motivo in reporte.motivos],
            "explicacion": reporte.explicacion,
            "disclaimer": reporte.disclaimer,
        })

    return {"esquema": "1.0", "alembic_revision": revision_alembic, "juegos": juegos}


def _abrir_conexion():
    from app.infrastructure.db.session import engine

    return engine.connect()


def _crear_resolver(session: Session) -> ResolverEstadoPrediccion:
    elegibilidad = EvaluarElegibilidadReaperturaML(
        JuegoRepositorySQLAlchemy(session),
        DisponibilidadHoldoutRepositorySQLAlchemy(session),
    )
    return ResolverEstadoPrediccion(EvaluarAutorizacionOperativaML(elegibilidad))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consulta manual de bloqueo AE-45 (solo lectura)")
    parser.parse_args([] if argv is None else argv)
    try:
        conexion = _abrir_conexion()
    except Exception as error:
        print(f"ERROR [conexion]: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FALLO_CONEXION

    try:
        conexion.execute(text("BEGIN TRANSACTION READ ONLY"))
        session = Session(bind=conexion)
        try:
            verificar_transaccion_solo_lectura(session)
            revision = verificar_revision_alembic(session)
            reporte = construir_reporte(_crear_resolver(session), revision)
        finally:
            session.close()
            conexion.execute(text("ROLLBACK"))
    except FalloAuditoriaOperativaError as error:
        print(f"ERROR [codigo {error.codigo_salida}]: {error}", file=sys.stderr)
        return error.codigo_salida
    except FalloConsultaEstadoError as error:
        print(f"ERROR [codigo {error.codigo_salida}]: {error}", file=sys.stderr)
        return error.codigo_salida
    except Exception as error:
        print(f"ERROR [inesperado]: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FALLO_INESPERADO
    finally:
        conexion.close()

    print(json.dumps(reporte, indent=2, sort_keys=True, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
