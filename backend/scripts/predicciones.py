#!/usr/bin/env python3
"""Fase 4: centro de predicciones desde la linea de comandos (el mismo caso de
uso que `/predicciones` y `/api/predicciones`).

Uso (desde `backend`, con `DATABASE_URL` apuntando a la base):

  python -m scripts.predicciones indice
  python -m scripts.predicciones consultar --juego MILOTO [--cartera <clave>]
  python -m scripts.predicciones generar --juego MILOTO [--cinco]
  python -m scripts.predicciones explicar --cartera <clave>
  python -m scripts.predicciones fiabilidad --juego MILOTO [--linea <procedencia:linea>] [--hasta 90]
  python -m scripts.predicciones ejecucion --id <identificador>
  python -m scripts.predicciones rutas

Ordenes:
- `indice`: configuracion elegida, version registrada, base y ultima prediccion
  de los cuatro juegos.
- `consultar`: la prediccion mas reciente de la configuracion (o la cartera
  indicada) con combinaciones, numeros fuertes/debiles, explicacion,
  reproduccion, resultado observado y proyeccion a la tabla `predicciones`.
- `generar`: genera con la configuracion vigente de Producto 5 (mismo caso de
  uso, mismo cerrojo y misma identidad: una entrada ya generada se reutiliza) y
  publica su explicacion. `--cinco`: la misma configuracion con 5
  combinaciones, sin cambiar la configuracion. Una version registrada se carga
  con la carga restringida de la Fase 3; nunca se reentrena.
- `explicar`: publica (o reutiliza) la explicacion de una cartera guardada.
- `fiabilidad`: rendimiento observado e incertidumbre por linea y tipo de
  evaluacion, y la evaluacion de la receta en su informe del laboratorio.
  `--hasta`: solo evidencia con objetivo <= hasta.
- `ejecucion`: estado de una generacion iniciada.
- `rutas`: rutas de almacenamiento efectivas; nunca `DATABASE_URL` ni `.env`.

Solo `generar` y `explicar` escriben (cartera de Producto 5 y explicacion).
Ninguna orden cambia la configuracion, importa sorteos ni entrena una version
registrada.

Salida: JSON UTF-8 por la salida estandar; avisos y errores por la de errores,
con `ERROR [codigo N] <codigo>: <mensaje>` o `AVISO [codigo N]: <mensaje>`.

Codigos de salida:
  0 exito
  2 uso incorrecto, juego, linea o cartera no validos o no encontrados
  3 base de datos o almacen no disponibles (lo guardado se muestra igual; al
    generar: el almacen de operacion no pudo registrar el progreso, y lo ya
    publicado se conserva)
  4 sin configuracion vigente para el juego (eligela en Carteras)
  5 resultado parcial: cartera generada sin explicacion, o la generacion no
    produjo cartera (muestra insuficiente o fallo del juego)
  6 ya hay otra ejecucion en curso para ese juego (no se inicio nada)
  7 version registrada incompatible con este entorno, sin sorteos cargados o
    fallo del proceso trabajador
  8 artefacto alterado o ilegible
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

from app.application.use_cases.operacion_diaria import EjecucionActivaError, mensaje_legible
from app.application.use_cases.predicciones import JUEGOS, PrediccionesError

EXIT_OK, EXIT_USO, EXIT_CONEXION, EXIT_SIN_CONFIGURACION, EXIT_PARCIAL, EXIT_ACTIVA, EXIT_FALLO, EXIT_ALTERADO = (
    0, 2, 3, 4, 5, 6, 7, 8)
CODIGO_POR_ERROR = {"no_encontrado": EXIT_USO, "no_valido": EXIT_USO, "alterado": EXIT_ALTERADO,
                    "no_disponible": EXIT_FALLO, "base_no_disponible": EXIT_CONEXION,
                    "sin_configuracion": EXIT_SIN_CONFIGURACION, "incompatible": EXIT_FALLO,
                    "fallo_del_trabajador": EXIT_FALLO, "parcial": EXIT_PARCIAL}


def centro_real():
    from app.api.dependencies import get_carteras, get_predicciones

    return get_predicciones(get_carteras())


def rutas_resueltas() -> dict:
    from app.core.config import get_settings

    ajustes = get_settings()
    return {"directorio_de_trabajo": str(Path.cwd().resolve()),
            "directorio_laboratorio_modelos": str(Path(ajustes.directorio_laboratorio_modelos).resolve()),
            "directorio_carteras_modelos": str(Path(ajustes.directorio_carteras_modelos).resolve()),
            "directorio_resultados_modelos": str(Path(ajustes.directorio_resultados_modelos).resolve()),
            "directorio_predicciones_modelos": str(Path(ajustes.directorio_predicciones_modelos).resolve())}


def _escribir(texto: str, salida) -> None:
    buffer = getattr(salida, "buffer", None)
    if buffer is not None:
        buffer.write(texto.encode("utf-8"))
        buffer.flush()
    else:
        salida.write(texto)


def _imprimir(objeto, salida) -> None:
    _escribir(json.dumps(objeto, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n", salida)


def _error(errores, codigo: int, nombre: str, mensaje: str) -> int:
    errores.write(f"ERROR [codigo {codigo}] {nombre}: {mensaje}\n")
    return codigo


def _aviso(errores, codigo: int, mensaje: str) -> int:
    errores.write(f"AVISO [codigo {codigo}]: {mensaje}\n")
    return codigo


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Centro de predicciones explicables (Fase 4)")
    sub = parser.add_subparsers(dest="orden", required=True)
    sub.add_parser("indice", help="los cuatro juegos")
    p = sub.add_parser("consultar", help="prediccion de un juego (lectura)")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p.add_argument("--cartera", help="clave de una cartera concreta (por defecto, la mas reciente)")
    p = sub.add_parser("generar", help="genera con la configuracion vigente y explica (escribe)")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p.add_argument("--cinco", action="store_true", help="5 combinaciones sin cambiar la configuracion")
    p = sub.add_parser("explicar", help="publica la explicacion de una cartera guardada (escribe)")
    p.add_argument("--cartera", required=True)
    p = sub.add_parser("fiabilidad", help="rendimiento observado e incertidumbre (lectura)")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p.add_argument("--linea", help="otra linea de Resultados (procedencia:linea)")
    p.add_argument("--hasta", type=int, help="solo evidencia con objetivo <= hasta")
    p = sub.add_parser("ejecucion", help="estado de una generacion")
    p.add_argument("--id", required=True)
    sub.add_parser("rutas", help="rutas de almacenamiento resueltas (sin credenciales)")
    return parser


def ejecutar(argv: list[str] | None, *, centro_factory: Callable = centro_real, salida=sys.stdout,
             errores=sys.stderr) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as salida_argparse:
        return EXIT_USO if salida_argparse.code else EXIT_OK
    if args.orden == "rutas":
        _imprimir(rutas_resueltas(), salida)
        return EXIT_OK
    try:
        return _orden(args, centro_factory(), salida, errores)
    except PrediccionesError as error:
        return _error(errores, CODIGO_POR_ERROR.get(error.codigo, EXIT_USO), error.codigo, str(error))
    except EjecucionActivaError as error:
        _imprimir({"estado": "en_curso_en_otra_ejecucion", "activas": error.activas}, salida)
        return _error(errores, EXIT_ACTIVA, "activa", str(error))
    except OSError as error:
        return _error(errores, EXIT_CONEXION, "almacen_no_disponible", mensaje_legible(error))


def _base(base: dict, errores) -> int:
    if base.get("estado") in ("base_no_disponible", "no_disponible"):
        return _aviso(errores, EXIT_CONEXION, f"base no disponible ({base.get('mensaje') or base.get('motivo')}): "
                                              "se muestra lo guardado")
    return EXIT_OK


def _orden(args, centro, salida, errores) -> int:
    if args.orden == "indice":
        datos = centro.indice()
        _imprimir(datos, salida)
        caidas = [j["juego"] for j in datos["juegos"] if j["base"]["estado"] == "base_no_disponible"]
        return _aviso(errores, EXIT_CONEXION, "base no disponible para " + ", ".join(caidas)) if caidas else EXIT_OK
    if args.orden == "consultar":
        vista = centro.consultar(args.juego, args.cartera)
        _imprimir(vista, salida)
        return _base(vista["base"], errores)
    if args.orden == "generar":
        r = centro.ahora(args.juego, "cinco" if args.cinco else "configuracion", "comando")
        _imprimir(r, salida)
        p = r["prediccion"]
        if p["estado"] == "exito":
            return EXIT_OK
        if p["estado"] == "parcial":
            return _aviso(errores, EXIT_PARCIAL, "cartera generada sin explicacion: "
                                                 + str(p["explicacion"].get("motivo")))
        if p.get("codigo") == "almacen_no_disponible":
            return _aviso(errores, EXIT_CONEXION, "almacen no disponible: " + str(p.get("mensaje")))
        return _aviso(errores, EXIT_PARCIAL, "la generacion no produjo cartera: "
                                             + str((p.get("cartera") or {}).get("mensaje") or p.get("cartera")))
    if args.orden == "explicar":
        r = centro.explicar(args.cartera, "comando")
        _imprimir(r, salida)
        return EXIT_OK
    if args.orden == "fiabilidad":
        vista = centro.fiabilidad(args.juego, args.linea, args.hasta)
        _imprimir(vista, salida)
        return EXIT_OK if vista["base"]["estado"] == "consultada" else _aviso(
            errores, EXIT_CONEXION, f"base no disponible ({vista['base'].get('motivo')}): sin resultados observados")
    if args.orden == "ejecucion":
        r = centro.ejecucion(args.id)
        if r is None:
            return _error(errores, EXIT_USO, "no_encontrado", f"ejecucion desconocida: {args.id}")
        _imprimir(r, salida)
        return EXIT_OK
    return _error(errores, EXIT_USO, "no_valido", f"orden desconocida: {args.orden}")


def main(argv: list[str] | None = None) -> int:
    return ejecutar(argv)


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        sys.exit(main())
