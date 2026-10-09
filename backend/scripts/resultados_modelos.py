#!/usr/bin/env python3
"""Producto 6: centro de resultados y evaluacion continua de modelos desde la
linea de comandos (el mismo caso de uso que `/resultados` y `/api/resultados`).

Uso (desde `backend`, con `DATABASE_URL` apuntando a la base):

  python -m scripts.resultados_modelos indice
  python -m scripts.resultados_modelos consultar --juego MILOTO [--tipo seguimiento] [--procedencia laboratorio] \
      [--linea <procedencia:linea> ...] [--desde 80] [--hasta 90] [--objetivo 85] [--cartera <linea> ...] \
      [--pagina 1] [--por-pagina 25]
  python -m scripts.resultados_modelos exportar --juego MILOTO --formato csv   (mismos filtros)
  python -m scripts.resultados_modelos guardar --juego MILOTO                  (mismos filtros)
  python -m scripts.resultados_modelos informes --juego MILOTO
  python -m scripts.resultados_modelos informe --clave <clave>
  python -m scripts.resultados_modelos verificar --clave <clave>
  python -m scripts.resultados_modelos configuracion --juego COLORLOTO --linea <linea de cartera>
  python -m scripts.resultados_modelos configurar --juego COLORLOTO --linea <linea de cartera>
  python -m scripts.resultados_modelos rutas

Ordenes:
- `indice`: ultimo resultado cargado, emisiones de seguimiento incluidas,
  pendientes y excluidas, y procedencias de los cuatro juegos.
- `consultar`: resumen por linea, comparacion directa sobre la muestra comun,
  evolucion, calibracion, carteras y una pagina del historial. `--procedencia`,
  `--linea` y `--cartera` se pueden repetir.
- `exportar`: CSV UTF-8 (sin formulas) o JSON canonico del conjunto filtrado
  COMPLETO (no solo una pagina), por la salida estandar.
- `guardar`: guarda una fotografia verificable de la consulta (misma
  fotografia -> el mismo informe; nunca se sobrescribe).
- `informes`, `informe`: informes guardados de un juego / uno por su clave.
- `verificar`: integridad del archivo, reproduccion del calculo congelado y
  coincidencia con la consulta actual, por separado (no guarda).
- `configuracion`: vista previa de «usar esta configuracion» (lectura).
- `configurar`: guarda la configuracion de esa cartera como version nueva con
  el caso de uso de Producto 5 (idempotente; no entrena ni genera carteras).
- `rutas`: rutas de almacenamiento efectivas; nunca `DATABASE_URL` ni `.env`.

Solo `guardar` y `configurar` escriben, cada una en su almacen. Ninguna orden
entrena, importa sorteos ni inicia trabajadores.

Salida: JSON UTF-8 por la salida estandar (CSV en `exportar --formato csv`);
avisos y errores por la de errores, con `ERROR [codigo N] <codigo>: <mensaje>`
o `AVISO [codigo N]: <mensaje>`.

Codigos de salida:
  0 exito
  2 uso incorrecto, filtro no valido o identificador no encontrado
  3 base de datos o almacen no disponibles (lo guardado se muestra igual)
  5 resultado parcial: informe guardado con limitaciones, informe con partes no
    verificables (formato anterior), o la consulta actual cambio, no esta
    disponible o no es comparable (no es una alteracion del archivo)
  7 la reproduccion del calculo congelado no es exacta
  8 archivo alterado o ilegible
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

from app.application.ml import resultados_informes as ri
from app.application.use_cases.operacion_diaria import mensaje_legible
from app.application.use_cases.resultados import JUEGOS, MAXIMO_POR_PAGINA, POR_PAGINA, Filtros, ResultadosError

EXIT_OK, EXIT_USO, EXIT_CONEXION, EXIT_PARCIAL, EXIT_REPRODUCCION, EXIT_ALTERADO = 0, 2, 3, 5, 7, 8
CODIGO_POR_ERROR = {"no_encontrado": EXIT_USO, "no_valido": EXIT_USO, "alterado": EXIT_ALTERADO,
                    "no_disponible": EXIT_CONEXION, "base_no_disponible": EXIT_CONEXION}


def centro_real():
    from app.api.dependencies import get_carteras, get_resultados

    return get_resultados(get_carteras())


def rutas_resueltas() -> dict:
    from app.core.config import get_settings

    ajustes = get_settings()
    return {"directorio_de_trabajo": str(Path.cwd().resolve()),
            "directorio_pronosticos_experimentales": str(Path(ajustes.directorio_pronosticos_experimentales).resolve()),
            "directorio_laboratorio_modelos": str(Path(ajustes.directorio_laboratorio_modelos).resolve()),
            "directorio_carteras_modelos": str(Path(ajustes.directorio_carteras_modelos).resolve()),
            "directorio_resultados_modelos": str(Path(ajustes.directorio_resultados_modelos).resolve())}


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


def _filtros_de_linea(p: argparse.ArgumentParser) -> None:
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p.add_argument("--procedencia", action="append", choices=["operacion", "laboratorio", "carteras"])
    p.add_argument("--linea", action="append", help="procedencia:linea (repetible)")
    p.add_argument("--tipo", default="seguimiento", choices=["seguimiento", "retrospectiva"])
    p.add_argument("--desde", type=int)
    p.add_argument("--hasta", type=int)
    p.add_argument("--objetivo", type=int)
    p.add_argument("--cartera", action="append", help="linea de cartera (repetible)")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Centro de resultados y evaluacion continua de modelos (Producto 6)")
    sub = parser.add_subparsers(dest="orden", required=True)
    sub.add_parser("indice", help="los cuatro juegos")
    p = sub.add_parser("consultar", help="consulta filtrada de un juego")
    _filtros_de_linea(p)
    p.add_argument("--pagina", type=int, default=1)
    p.add_argument("--por-pagina", type=int, default=POR_PAGINA)
    p = sub.add_parser("exportar", help="CSV o JSON del conjunto filtrado completo")
    _filtros_de_linea(p)
    p.add_argument("--formato", default="csv", choices=["csv", "json"])
    p = sub.add_parser("guardar", help="guarda una fotografia verificable de la consulta")
    _filtros_de_linea(p)
    p = sub.add_parser("informes", help="informes guardados de un juego")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p = sub.add_parser("informe", help="un informe guardado por su clave")
    p.add_argument("--clave", required=True)
    p = sub.add_parser("verificar", help="integridad, reproduccion y coincidencia con la consulta actual")
    p.add_argument("--clave", required=True)
    for orden, ayuda in (("configuracion", "vista previa de usar la configuracion de una cartera"),
                         ("configurar", "guarda la configuracion de una cartera (version nueva)")):
        p = sub.add_parser(orden, help=ayuda)
        p.add_argument("--juego", required=True, choices=list(JUEGOS))
        p.add_argument("--linea", required=True, help="linea de cartera")
    sub.add_parser("rutas", help="rutas de almacenamiento resueltas (sin credenciales)")
    return parser


def _filtros(args) -> Filtros:
    return Filtros(tuple(args.procedencia or ()) or Filtros().procedencias, tuple(args.linea or ()), args.tipo,
                   args.desde, args.hasta, args.objetivo, tuple(args.cartera or ())).validar()


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
    except ResultadosError as error:
        return _error(errores, CODIGO_POR_ERROR.get(error.codigo, EXIT_USO), error.codigo, str(error))
    except OSError as error:
        return _error(errores, EXIT_CONEXION, "almacen_no_disponible", mensaje_legible(error))


def _sin_base(vista: dict, errores) -> int:
    if vista["base"]["estado"] != "consultada":
        return _aviso(errores, EXIT_CONEXION, f"base no disponible ({vista['base']['motivo']}): se muestra lo guardado "
                                              "sin resultados observados")
    return EXIT_OK


def _orden(args, centro, salida, errores) -> int:
    if args.orden == "indice":
        datos = centro.indice()
        _imprimir(datos, salida)
        caidas = [j["juego"] for j in datos["juegos"] if j["base"]["estado"] != "consultada"]
        return _aviso(errores, EXIT_CONEXION, "base no disponible para " + ", ".join(caidas)) if caidas else EXIT_OK
    if args.orden == "consultar":
        if not 1 <= args.por_pagina <= MAXIMO_POR_PAGINA or args.pagina < 1:
            return _error(errores, EXIT_USO, "no_valido", f"--pagina >= 1 y --por-pagina entre 1 y {MAXIMO_POR_PAGINA}")
        vista = centro.consultar(args.juego, _filtros(args), pagina=args.pagina, por_pagina=args.por_pagina)
        _imprimir(vista, salida)
        return _sin_base(vista, errores)
    if args.orden == "exportar":
        filtros = _filtros(args)
        if args.formato == "json":
            datos = centro.exportar_json(args.juego, filtros)
            _escribir(ri.json_canonico(datos).decode("utf-8"), salida)  # ya termina en salto de linea
            return _sin_base(datos, errores)
        _escribir(centro.exportar_csv(args.juego, filtros), salida)
        return EXIT_OK
    if args.orden == "guardar":
        r = centro.guardar_informe(args.juego, _filtros(args), "comando")
        _imprimir(r, salida)
        if r["estado"] != "completo":
            return _aviso(errores, EXIT_PARCIAL, "informe guardado con limitaciones: " + "; ".join(r["limitaciones"]))
        return EXIT_OK
    if args.orden == "informes":
        _imprimir({"juego": args.juego, "informes": centro.informes(args.juego)}, salida)
        return EXIT_OK
    if args.orden == "informe":
        _escribir(ri.json_canonico(centro.informe(args.clave)).decode("utf-8"), salida)
        return EXIT_OK
    if args.orden == "verificar":
        r = centro.verificar_informe(args.clave)
        _imprimir(r, salida)
        if r["integridad"] != "correcta":
            return _error(errores, EXIT_ALTERADO, "alterado", r.get("motivo") or "archivo alterado")
        reproduccion = r["reproduccion"]
        if reproduccion["estado"] == "no_exacta":
            return _error(errores, EXIT_REPRODUCCION, "reproduccion_no_exacta",
                          "el calculo congelado no se reproduce con las funciones actuales: "
                          + ", ".join(sorted({d["motivo"] for d in reproduccion["diferencias"]})))
        avisos = []
        if reproduccion["estado"] == "parcial":
            avisos.append("partes no verificables: " + ", ".join(p for p, v in reproduccion["partes"].items()
                                                                  if v == "no_verificable"))
        estado = r["base_actual"]["estado"]
        if estado != "coincide":
            avisos.append({"cambio": "la consulta actual cambió", "no_disponible": "la base no está disponible",
                           "no_comparable": "la consulta actual no es comparable"}.get(estado, estado))
        if avisos:
            return _aviso(errores, EXIT_PARCIAL, "informe integro; " + "; ".join(avisos)
                          + " (no es una alteracion del archivo)")
        return EXIT_OK
    if args.orden == "configuracion":
        _imprimir(centro.propuesta_de_configuracion(args.juego, args.linea), salida)
        return EXIT_OK
    if args.orden == "configurar":
        _imprimir(centro.usar_configuracion(args.juego, args.linea, "comando"), salida)
        return EXIT_OK
    return _error(errores, EXIT_USO, "no_valido", f"orden desconocida: {args.orden}")


def main(argv: list[str] | None = None) -> int:
    return ejecutar(argv)


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        sys.exit(main())
