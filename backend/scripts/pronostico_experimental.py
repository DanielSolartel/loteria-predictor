#!/usr/bin/env python3
"""Producto 1: entrenar, guardar y consultar pronosticos experimentales
de Baloto y Baloto Revancha desde la linea de comandos.

Uso (desde `backend`, con `DATABASE_URL` apuntando a la base real):

  python -m scripts.pronostico_experimental entrenar --juego BALOTO [--hasta-sorteo N]
  python -m scripts.pronostico_experimental entrenar --juego todos
  python -m scripts.pronostico_experimental listar --juego BALOTO_REVANCHA
  python -m scripts.pronostico_experimental verificar --juego BALOTO --id SHA256

`entrenar` lee el historico en una transaccion PostgreSQL de solo lectura
(`BEGIN TRANSACTION READ ONLY` y `ROLLBACK`), entrena, evalua walk-forward
frente a la referencia uniforme y guarda el artefacto JSON en
`storage/pronosticos/<JUEGO>/` sin sobrescribir ninguno. Si ya existe un
artefacto con la misma entrada (juego, corte, historico, configuracion y
version), lo devuelve sin reentrenar (`"reutilizado": true`). La salida
indica la clasificacion temporal del objetivo (simulacion retrospectiva o
pronostico sobre el ultimo dato disponible) y la frescura del historico.
`verificar` recalcula un artefacto guardado (reentrena) y compara su
huella de reproduccion.

Codigos de salida: 0 correcto; 2 uso incorrecto; 3 fallo de conexion o de
lectura; 4 historico insuficiente o pronostico no disponible. Ninguno
acredita ventaja predictiva: el estado es `experimental_no_acreditado`.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone

from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado
from app.application.use_cases.pronostico_experimental import (
    JUEGOS,
    ConsultarPronosticosExperimentales,
    GenerarPronosticoExperimental,
    PronosticoExperimentalNoDisponibleError,
    VerificarPronosticoExperimental,
)

EXIT_OK, EXIT_USO, EXIT_CONEXION, EXIT_NO_DISPONIBLE = 0, 2, 3, 4


@contextlib.contextmanager
def repositorios_reales():
    """Repositorios sobre una transaccion de solo lectura que termina en
    ROLLBACK: el script nunca escribe en PostgreSQL."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.infrastructure.db.session import engine
    from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
    from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
        ResultadosHistoricosRepositorySQLAlchemy,
    )

    conexion = engine.connect()
    try:
        conexion.execute(text("BEGIN TRANSACTION READ ONLY"))
        session = Session(bind=conexion)
        try:
            yield JuegoRepositorySQLAlchemy(session), ResultadosHistoricosRepositorySQLAlchemy(session)
        finally:
            session.close()
            conexion.execute(text("ROLLBACK"))
    finally:
        conexion.close()


def almacen_real():
    from app.core.config import get_settings
    from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore

    return PronosticoExperimentalFileStore(get_settings().directorio_pronosticos_experimentales)


def _resumen(guardado: PronosticoGuardado) -> dict:
    a = guardado.artefacto
    agregado = a["evaluacion_walk_forward"]["agregado"]
    return {
        "identificador": guardado.identificador,
        "juego": a["juego"],
        "estado_de_uso": a["estado_de_uso"],
        "objetivo": a["pronostico"]["objetivo"],
        "corte": a["datos"]["corte"],
        "datos": {k: a["datos"][k] for k in ("total_sorteos", "primer_sorteo", "ultimo_sorteo", "primera_fecha",
                                             "ultima_fecha", "sha256_historico")},
        "numeros_sugeridos": a["pronostico"]["numeros_sugeridos"],
        "superbalota_sugerida": a["superbalota"]["pronostico"]["sugerida"] if a.get("superbalota") else None,
        "walk_forward": {"modelo": agregado["modelo"], "referencia_uniforme": agregado["referencia_uniforme"],
                         "veredicto": agregado["comparacion"]["veredicto"]},
        "decision_ae39": a["contexto"]["decision_ae39"],
        "huella_de_reproduccion": a["huella_de_reproduccion"],
        "generado_en": a["generacion"]["generado_en"],
        "clasificacion_temporal": a["generacion"].get("clasificacion_temporal"),
        "frescura": a["generacion"].get("frescura"),
        "version": guardado.version, "versiones": guardado.versiones,
        "reutilizado": guardado.reutilizado,
    }


def _imprimir(objeto, salida) -> None:
    salida.write(json.dumps(objeto, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def ejecutar(argv: list[str] | None, *, repositorios: Callable = repositorios_reales,
             almacen_factory: Callable = almacen_real, reloj: Callable[[], datetime] | None = None,
             configuracion=None,
             salida=sys.stdout, errores=sys.stderr) -> int:
    parser = argparse.ArgumentParser(description="Pronostico experimental de Baloto y Revancha (Producto 1)")
    sub = parser.add_subparsers(dest="orden", required=True)
    p_entrenar = sub.add_parser("entrenar", help="entrena, evalua y guarda un pronostico nuevo")
    p_entrenar.add_argument("--juego", required=True, choices=[*JUEGOS, "todos"])
    p_entrenar.add_argument("--hasta-sorteo", type=int)
    p_listar = sub.add_parser("listar", help="lista los pronosticos guardados")
    p_listar.add_argument("--juego", required=True, choices=list(JUEGOS))
    p_verificar = sub.add_parser("verificar", help="recalcula un pronostico guardado y compara")
    p_verificar.add_argument("--juego", required=True, choices=list(JUEGOS))
    p_verificar.add_argument("--id", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as salida_argparse:
        return EXIT_USO if salida_argparse.code else EXIT_OK
    if getattr(args, "hasta_sorteo", None) is not None and args.hasta_sorteo < 1:
        errores.write("--hasta-sorteo debe ser positivo\n")
        return EXIT_USO
    almacen = almacen_factory()

    if args.orden == "listar":
        r = ConsultarPronosticosExperimentales(almacen).resumen(args.juego)
        _imprimir({"juego": args.juego, "guardados": [_resumen(g) for g in r.guardados],
                   "ilegibles": [{"identificador": e.identificador, "motivo": e.motivo} for e in r.ilegibles]}, salida)
        return EXIT_OK

    juegos = list(JUEGOS) if args.orden == "entrenar" and args.juego == "todos" else [args.juego]
    resultados = []
    try:
        with repositorios() as (juego_repo, resultados_repo):
            for codigo in juegos:
                if args.orden == "entrenar":
                    kwargs = {} if reloj is None else {"reloj": reloj}
                    if configuracion is not None:
                        kwargs["configuracion"] = configuracion
                    caso = GenerarPronosticoExperimental(juego_repo, resultados_repo, almacen, **kwargs)
                    resultados.append(_resumen(caso.ejecutar(codigo, hasta_numero_sorteo=args.hasta_sorteo)))
                else:
                    resultados.append(VerificarPronosticoExperimental(juego_repo, resultados_repo, almacen)
                                      .ejecutar(codigo, args.id))
    except (PronosticoExperimentalNoDisponibleError, JuegoNoEncontradoError) as error:
        errores.write(f"ERROR [codigo {EXIT_NO_DISPONIBLE}]: {error}\n")
        return EXIT_NO_DISPONIBLE
    except Exception as error:  # conexion, credenciales o esquema de la base
        errores.write(f"ERROR [codigo {EXIT_CONEXION}]: {type(error).__name__}: {error}\n")
        return EXIT_CONEXION
    _imprimir(resultados if len(resultados) > 1 else resultados[0], salida)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    return ejecutar(argv, reloj=lambda: datetime.now(timezone.utc))


if __name__ == "__main__":
    sys.exit(main())
