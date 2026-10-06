#!/usr/bin/env python3
"""Productos 1 y 2: entrenar, guardar, consultar y comparar con los
resultados observados los pronosticos experimentales de Baloto, Baloto
Revancha, MiLoto y ColorLoto desde la linea de comandos.

Uso (desde `backend`, con `DATABASE_URL` apuntando a la base real):

  python -m scripts.pronostico_experimental entrenar --juego MILOTO [--hasta-sorteo N]
  python -m scripts.pronostico_experimental entrenar --juego todos
  python -m scripts.pronostico_experimental listar --juego COLORLOTO
  python -m scripts.pronostico_experimental verificar --juego BALOTO --id SHA256
  python -m scripts.pronostico_experimental resultados --juego todos
  python -m scripts.pronostico_experimental corte-retrospectivo --juego MILOTO

Juegos: BALOTO, BALOTO_REVANCHA, MILOTO, COLORLOTO (o `todos`).

`entrenar` lee el historico en una transaccion PostgreSQL de solo lectura
(`BEGIN TRANSACTION READ ONLY` y `ROLLBACK`), entrena, evalua walk-forward
frente a la referencia uniforme del juego y guarda el artefacto JSON en
`storage/pronosticos/<JUEGO>/` sin sobrescribir ninguno (Baloto y Revancha
con el esquema `pronostico-experimental/1`; MiLoto y ColorLoto con
`pronostico-experimental/2`). Si ya existe un artefacto con la misma
entrada (juego, corte, historico, configuracion y version), lo devuelve
sin reentrenar (`"reutilizado": true`). La salida indica la clasificacion
temporal del objetivo y la frescura del historico. Con `--juego todos`, un
juego sin datos suficientes no impide los demas: su entrada lleva `error`
y el codigo de salida es 4.
`verificar` recalcula un artefacto guardado (reentrena) y compara.
`resultados` compara, en lectura, cada pronostico guardado con su sorteo
objetivo en la base (`observado`, `pendiente` o `no_corresponde`).
`corte-retrospectivo` (MILOTO o COLORLOTO) lee la base y propone un corte
existente con al menos 30 sorteos hasta el y cuyo objetivo (corte + 1)
tambien esta cargado, para comprobar un resultado observado sin suponer
numeros de sorteo.

Codigos de salida: 0 correcto; 2 uso incorrecto (juego no admitido,
argumentos); 3 fallo de conexion o de lectura; 4 datos insuficientes,
juego no registrado o pronostico no disponible. Ninguno acredita ventaja
predictiva: el estado es `experimental_no_acreditado`.
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
    CompararConResultadosObservados,
    ConsultarPronosticosExperimentales,
    GenerarPronosticoExperimental,
    PronosticoExperimentalNoDisponibleError,
    VerificarPronosticoExperimental,
    configuracion_por_defecto,
    elegir_corte_retrospectivo,
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
    p = a["pronostico"]
    agregado = a["evaluacion_walk_forward"]["agregado"]
    salida = {
        "identificador": guardado.identificador,
        "juego": a["juego"],
        "esquema": a["esquema"],
        "estado_de_uso": a["estado_de_uso"],
        "objetivo": p["objetivo"],
        "corte": a["datos"]["corte"],
        "datos": {k: a["datos"][k] for k in ("total_sorteos", "primer_sorteo", "ultimo_sorteo", "primera_fecha",
                                             "ultima_fecha", "sha256_historico")},
        "walk_forward": {"modelo": agregado["modelo"], "referencia_uniforme": agregado["referencia_uniforme"],
                         "veredicto": agregado["comparacion"]["veredicto"]},
        "huella_de_reproduccion": a["huella_de_reproduccion"],
        "generado_en": a["generacion"]["generado_en"],
        "clasificacion_temporal": a["generacion"].get("clasificacion_temporal"),
        "frescura": a["generacion"].get("frescura"),
        "version": guardado.version, "versiones": guardado.versiones,
        "reutilizado": guardado.reutilizado,
    }
    if "pares" in p:
        salida["pares_sugeridos"] = [[f["numero"], f["color"]] for f in p["pares"]]
        salida["paleta"] = p["paleta"]
    else:
        salida["numeros_sugeridos"] = p["numeros_sugeridos"]
        salida["superbalota_sugerida"] = a["superbalota"]["pronostico"]["sugerida"] if a.get("superbalota") else None
    if "decision_ae39" in a["contexto"]:
        salida["decision_ae39"] = a["contexto"]["decision_ae39"]
    else:
        salida["decision_previa"] = a["contexto"]["decision_previa"]
        salida["estrategia"] = a["estrategia"]["nombre"]
        salida["muestra"] = a["evaluacion_walk_forward"]["muestra"]
    return salida


def _imprimir(objeto, salida) -> None:
    salida.write(json.dumps(objeto, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def ejecutar(argv: list[str] | None, *, repositorios: Callable = repositorios_reales,
             almacen_factory: Callable = almacen_real, reloj: Callable[[], datetime] | None = None,
             configuracion=None, configuraciones=None,
             salida=sys.stdout, errores=sys.stderr) -> int:
    parser = argparse.ArgumentParser(description="Pronostico experimental de Baloto, Revancha, MiLoto y ColorLoto")
    sub = parser.add_subparsers(dest="orden", required=True)
    p_entrenar = sub.add_parser("entrenar", help="entrena, evalua y guarda un pronostico nuevo")
    p_entrenar.add_argument("--juego", required=True, choices=[*JUEGOS, "todos"])
    p_entrenar.add_argument("--hasta-sorteo", type=int)
    p_listar = sub.add_parser("listar", help="lista los pronosticos guardados")
    p_listar.add_argument("--juego", required=True, choices=list(JUEGOS))
    p_verificar = sub.add_parser("verificar", help="recalcula un pronostico guardado y compara")
    p_verificar.add_argument("--juego", required=True, choices=list(JUEGOS))
    p_verificar.add_argument("--id", required=True)
    p_resultados = sub.add_parser("resultados", help="compara los pronosticos guardados con los resultados observados")
    p_resultados.add_argument("--juego", required=True, choices=[*JUEGOS, "todos"])
    p_corte = sub.add_parser("corte-retrospectivo",
                             help="propone, desde la base, un corte existente con objetivo cargado")
    p_corte.add_argument("--juego", required=True, choices=["MILOTO", "COLORLOTO"])
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

    todos = args.juego == "todos"
    juegos = list(JUEGOS) if todos else [args.juego]
    resultados, codigo_de_salida = [], EXIT_OK
    try:
        with repositorios() as (juego_repo, resultados_repo):
            for codigo in juegos:
                try:
                    if args.orden == "entrenar":
                        kwargs = {} if reloj is None else {"reloj": reloj}
                        caso = GenerarPronosticoExperimental(juego_repo, resultados_repo, almacen, **kwargs,
                                                             configuracion=configuracion,
                                                             configuraciones=configuraciones)
                        resultados.append(_resumen(caso.ejecutar(codigo, hasta_numero_sorteo=args.hasta_sorteo)))
                    elif args.orden == "corte-retrospectivo":
                        configuracion_juego = (configuraciones or {}).get(codigo) or configuracion_por_defecto(codigo)
                        resultados.append(elegir_corte_retrospectivo(juego_repo, resultados_repo, codigo,
                                                                     configuracion_juego))
                    elif args.orden == "resultados":
                        filas = CompararConResultadosObservados(almacen, juego_repo, resultados_repo).ejecutar(codigo)
                        resultados.append({"juego": codigo, "estado_de_uso": "experimental_no_acreditado",
                                           "pronosticos": filas})
                    else:
                        resultados.append(VerificarPronosticoExperimental(juego_repo, resultados_repo, almacen)
                                          .ejecutar(codigo, args.id))
                except (PronosticoExperimentalNoDisponibleError, JuegoNoEncontradoError) as error:
                    errores.write(f"ERROR [codigo {EXIT_NO_DISPONIBLE}] {codigo}: {error}\n")
                    if not todos:
                        return EXIT_NO_DISPONIBLE
                    resultados.append({"juego": codigo, "error": str(error), "codigo_de_salida": EXIT_NO_DISPONIBLE})
                    codigo_de_salida = EXIT_NO_DISPONIBLE
    except Exception as error:  # conexion, credenciales o esquema de la base
        errores.write(f"ERROR [codigo {EXIT_CONEXION}]: {type(error).__name__}: {error}\n")
        return EXIT_CONEXION
    _imprimir(resultados if todos else resultados[0], salida)
    return codigo_de_salida


def main(argv: list[str] | None = None) -> int:
    return ejecutar(argv, reloj=lambda: datetime.now(timezone.utc))


if __name__ == "__main__":
    sys.exit(main())
