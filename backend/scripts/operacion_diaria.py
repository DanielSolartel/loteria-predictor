#!/usr/bin/env python3
"""Producto 3: operacion diaria desde la linea de comandos (el mismo caso de
uso que el panel `/operacion`).

Uso (desde `backend`, con `DATABASE_URL` apuntando a la base):

  python -m scripts.operacion_diaria ejecutar --juego todos --modo local
  python -m scripts.operacion_diaria ejecutar --juego MILOTO --modo local
  python -m scripts.operacion_diaria ejecutar --juego todos --modo actualizar
  python -m scripts.operacion_diaria consultar --id 20261001T120000Z-0a1b2c3d
  python -m scripts.operacion_diaria ejecuciones --limite 10
  python -m scripts.operacion_diaria recuperar
  python -m scripts.operacion_diaria rendimiento --juego BALOTO --emision todas
  python -m scripts.operacion_diaria rutas

Ordenes:

- `ejecutar --modo local`: genera (o reutiliza) con el historico ya cargado,
  en una transaccion de solo lectura; no escribe sorteos.
- `ejecutar --modo actualizar`: importa antes los sorteos nuevos con la
  importacion incremental existente (escribe en la base, como el panel
  Importacion). Si la importacion de un juego falla, ese juego no se
  genera y el resultado es parcial o fallo.
- `consultar` y `ejecuciones`: leen el registro sin ejecutar nada.
- `recuperar`: marca como interrumpidas las ejecuciones cuyo proceso murio.
- `rendimiento`: resumen JSON (misma politica y filtros que la web).
- `rutas`: rutas absolutas de almacenamiento que resuelve la configuracion
  (variables de entorno y `.env`) desde el directorio actual. Solo imprime
  esas rutas: nunca `DATABASE_URL` ni el contenido de `.env`.

La salida es JSON por la salida estandar; los errores van a la de errores.
No hay programador interno: para ejecutarlo cada dia use el Programador de
tareas de Windows (ver `docs/producto3_windows.md`).

Codigos de salida:
  0 exito (todos los juegos terminaron bien; o consulta correcta)
  2 uso incorrecto o ejecucion no encontrada
  3 base de datos o registro no disponibles
  5 resultado parcial (algun juego fallo o no tuvo datos suficientes)
  6 ya hay una ejecucion activa para alguno de los juegos pedidos
  7 fallo (ningun juego termino bien, o la ejecucion fue interrumpida)
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from datetime import date

from app.application.use_cases.operacion_diaria import MODOS, EjecucionActivaError, mensaje_legible
from app.application.use_cases.pronostico_experimental import JUEGOS, PronosticoExperimentalNoDisponibleError
from app.application.use_cases.rendimiento import FILTROS_DE_EMISION, ConsultarRendimiento

EXIT_OK, EXIT_USO, EXIT_CONEXION, EXIT_PARCIAL, EXIT_ACTIVA, EXIT_FALLO = 0, 2, 3, 5, 6, 7
CODIGO_POR_ESTADO = {"exito": EXIT_OK, "parcial": EXIT_PARCIAL, "fallo": EXIT_FALLO, "interrumpida": EXIT_FALLO}


def operacion_real():
    from app.api.dependencies import get_operacion_diaria

    return get_operacion_diaria()


def almacen_real():
    from app.api.dependencies import get_almacen_pronosticos

    return get_almacen_pronosticos()


def repositorios_reales():
    from scripts.pronostico_experimental import repositorios_reales as abrir

    return abrir()


def rutas_resueltas() -> dict:
    """Rutas de almacenamiento efectivas (absolutas), sin ningun otro ajuste."""
    from pathlib import Path

    from app.core.config import get_settings

    ajustes = get_settings()
    return {"directorio_de_trabajo": str(Path.cwd().resolve()),
            "directorio_pronosticos_experimentales": str(Path(ajustes.directorio_pronosticos_experimentales).resolve()),
            "directorio_operacion": str(Path(ajustes.directorio_operacion).resolve())}


def _imprimir(objeto, salida) -> None:
    salida.write(json.dumps(objeto, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def _fecha(valor: str) -> date:
    return date.fromisoformat(valor)


def ejecutar(argv: list[str] | None, *, operacion_factory: Callable = operacion_real,
             repositorios: Callable = repositorios_reales, almacen_factory: Callable = almacen_real,
             salida=sys.stdout, errores=sys.stderr) -> int:
    parser = argparse.ArgumentParser(description="Operacion diaria de los pronosticos experimentales (Producto 3)")
    sub = parser.add_subparsers(dest="orden", required=True)
    p = sub.add_parser("ejecutar", help="genera (y opcionalmente actualiza) uno o todos los juegos")
    p.add_argument("--juego", required=True, choices=[*JUEGOS, "todos"])
    p.add_argument("--modo", required=True, choices=list(MODOS))
    p = sub.add_parser("consultar", help="estado de una ejecucion")
    p.add_argument("--id", required=True)
    p = sub.add_parser("ejecuciones", help="ejecuciones recientes")
    p.add_argument("--limite", type=int, default=10)
    sub.add_parser("recuperar", help="marca como interrumpidas las ejecuciones cuyo proceso murio")
    sub.add_parser("rutas", help="rutas de almacenamiento resueltas (sin credenciales)")
    p = sub.add_parser("rendimiento", help="resumen del rendimiento en JSON")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p.add_argument("--emision", default="todas", choices=list(FILTROS_DE_EMISION))
    p.add_argument("--desde", type=_fecha)
    p.add_argument("--hasta", type=_fecha)
    try:
        args = parser.parse_args(argv)
    except SystemExit as salida_argparse:
        return EXIT_USO if salida_argparse.code else EXIT_OK

    if args.orden == "rutas":
        _imprimir(rutas_resueltas(), salida)
        return EXIT_OK

    if args.orden == "rendimiento":
        try:
            with repositorios() as (juego_repo, resultados_repo):
                datos = ConsultarRendimiento(almacen_factory(), juego_repo, resultados_repo).ejecutar(
                    args.juego, emision=args.emision, desde=args.desde, hasta=args.hasta)
        except PronosticoExperimentalNoDisponibleError as error:
            errores.write(f"ERROR [codigo {EXIT_USO}]: {error}\n")
            return EXIT_USO
        except Exception as error:  # conexion o lectura
            errores.write(f"ERROR [codigo {EXIT_CONEXION}]: {mensaje_legible(error)}\n")
            return EXIT_CONEXION
        _imprimir(datos, salida)
        return EXIT_OK

    try:
        operacion = operacion_factory()
        if args.orden == "consultar":
            ejecucion = operacion.consultar(args.id)
            if ejecucion is None:
                errores.write(f"ERROR [codigo {EXIT_USO}]: ejecucion no encontrada: {args.id}\n")
                return EXIT_USO
            _imprimir(ejecucion, salida)
            return EXIT_OK
        if args.orden == "ejecuciones":
            _imprimir({"ejecuciones": operacion.recientes(max(1, min(args.limite, 200)))}, salida)
            return EXIT_OK
        if args.orden == "recuperar":
            _imprimir({"interrumpidas_marcadas": operacion.recuperar()}, salida)
            return EXIT_OK
        juegos = list(JUEGOS) if args.juego == "todos" else [args.juego]
        try:
            final = operacion.ejecutar_ahora(juegos, args.modo, "comando")
        except EjecucionActivaError as error:
            errores.write(f"ERROR [codigo {EXIT_ACTIVA}]: {error}; activas: {json.dumps(error.activas)}\n")
            _imprimir({"estado": "en_curso_en_otra_ejecucion", "activas": error.activas}, salida)
            return EXIT_ACTIVA
    except OSError as error:
        errores.write(f"ERROR [codigo {EXIT_CONEXION}]: {mensaje_legible(error)}\n")
        return EXIT_CONEXION
    _imprimir(final, salida)
    codigo = CODIGO_POR_ESTADO.get(final["estado"], EXIT_FALLO)
    if codigo:
        malos = {j: r["estado"] for j, r in final["juegos"].items() if r["estado"] != "ok"}
        errores.write(f"AVISO [codigo {codigo}]: ejecucion {final['estado']}; juegos con problemas: "
                      f"{json.dumps(malos, ensure_ascii=False)}\n")
    return codigo


def main(argv: list[str] | None = None) -> int:
    return ejecutar(argv)


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        sys.exit(main())
