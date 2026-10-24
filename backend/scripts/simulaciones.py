#!/usr/bin/env python3
"""Fase 7: simulaciones bajo el mecanismo uniforme de cada juego desde la linea
de comandos (el mismo caso de uso que `/simulaciones`).

Uso (desde `backend`, con `DATABASE_URL` apuntando a la base):

  python -m scripts.simulaciones catalogo
  python -m scripts.simulaciones diagnostico --juego MILOTO
  python -m scripts.simulaciones simular --juego BALOTO --iteraciones 10000 [--semilla 20261023] [--corte 2700]
  python -m scripts.simulaciones listar [--juego COLORLOTO] [--limite 20]
  python -m scripts.simulaciones ver --id <uuid>
  python -m scripts.simulaciones exportar --id <uuid> --formato csv
  python -m scripts.simulaciones verificar --id <uuid> [--reproducir]
  python -m scripts.simulaciones consultar --id <ejecucion>
  python -m scripts.simulaciones ejecuciones --limite 10
  python -m scripts.simulaciones recuperar
  python -m scripts.simulaciones rutas

Ordenes:
- `catalogo`: iteraciones admitidas (100, 1000, 10000, 100000, 1000000),
  semilla predeterminada, algoritmo y estadisticas fijadas por juego.
- `diagnostico`: corte, sorteos, frescura y simulaciones guardadas de un juego.
- `simular`: lee el historico hasta el corte (por defecto, el ultimo sorteo
  cargado), simula en el proceso trabajador (progreso por la salida de
  errores) y publica UNA fila completa en la tabla `simulaciones`. Misma
  identidad -> reutiliza la fila existente sin simular.
- `listar`/`ver`: filas de la Fase 7 con su integridad verificada.
- `exportar`: JSON o CSV UTF-8 (sin formulas) derivados de la fila, por la
  salida estandar.
- `verificar`: integridad de la fila y coincidencia del historico hasta el
  corte con la base actual; con `--reproducir`, vuelve a simular y compara la
  huella del contenido (puede tardar lo mismo que la simulacion).
- `rutas`: rutas efectivas; nunca `DATABASE_URL` ni `.env`.

Solo `simular` escribe (una fila en `simulaciones` y el progreso en
`DIRECTORIO_SIMULACIONES`); `recuperar` solo marca ejecuciones interrumpidas
en ese registro. Ninguna orden importa sorteos ni entrena modelos.

Salida: JSON UTF-8 por la salida estandar (CSV en `exportar --formato csv`);
avisos y errores por la de errores, con `ERROR [codigo N] <codigo>: <mensaje>`.

Codigos de salida:
  0 exito (terminado o reutilizado; verificacion completa)
  2 uso incorrecto, parametro no valido o identificador no encontrado
  3 base de datos o almacen no disponibles
  4 muestra insuficiente o historico no valido
  5 verificacion parcial (historico cambiado o reproduccion no aplicable)
  6 ya hay una simulacion activa para el juego
  7 fallo (o ejecucion interrumpida)
  8 fila alterada
  9 tiempo agotado del proceso trabajador
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

from app.application.fase7 import motor as fm
from app.application.use_cases.operacion_diaria import EjecucionActivaError, identificador_valido, mensaje_legible
from app.application.use_cases.simulaciones import JUEGOS, SimulacionesError

(EXIT_OK, EXIT_USO, EXIT_CONEXION, EXIT_MUESTRA, EXIT_PARCIAL, EXIT_ACTIVA, EXIT_FALLO, EXIT_ALTERADO,
 EXIT_TIEMPO) = (0, 2, 3, 4, 5, 6, 7, 8, 9)
CODIGO_POR_ERROR = {"no_encontrado": EXIT_USO, "no_valido": EXIT_USO, "alterado": EXIT_ALTERADO,
                    "base_no_disponible": EXIT_CONEXION, "tiempo_agotado": EXIT_TIEMPO,
                    "fallo_del_trabajador": EXIT_FALLO}
CODIGO_POR_ESTADO_DEL_JUEGO = {"terminado": EXIT_OK, "reutilizado": EXIT_OK, "muestra_insuficiente": EXIT_MUESTRA,
                               "historico_no_valido": EXIT_MUESTRA, "base_no_disponible": EXIT_CONEXION,
                               "tiempo_agotado": EXIT_TIEMPO, "alterado": EXIT_ALTERADO, "no_valido": EXIT_USO,
                               "fallo": EXIT_FALLO}


def simulaciones_reales():
    from app.api.dependencies import get_simulaciones

    return get_simulaciones()


def rutas_resueltas() -> dict:
    from app.core.config import get_settings

    ajustes = get_settings()
    return {"directorio_de_trabajo": str(Path.cwd().resolve()),
            "directorio_simulaciones": str(Path(ajustes.directorio_simulaciones).resolve()),
            "resultados": "tabla simulaciones de la base configurada (fuente canonica)",
            "tiempo_maximo_trabajador_simulaciones": ajustes.tiempo_maximo_trabajador_simulaciones}


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


def _juego(valor: str) -> str:
    codigo = valor.strip().upper().replace("-", "_")
    if codigo not in JUEGOS:
        raise argparse.ArgumentTypeError(f"juego admitido: {', '.join(JUEGOS)}")
    return codigo


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulaciones bajo el mecanismo uniforme (Fase 7)")
    sub = parser.add_subparsers(dest="orden", required=True)
    sub.add_parser("catalogo", help="iteraciones, semilla, algoritmo y estadisticas fijadas")
    p = sub.add_parser("diagnostico", help="corte, sorteos y simulaciones guardadas de un juego")
    p.add_argument("--juego", type=_juego, required=True)
    p = sub.add_parser("simular", help="simula un juego y publica el resultado en la tabla simulaciones")
    p.add_argument("--juego", type=_juego, required=True)
    p.add_argument("--iteraciones", type=int, default=fm.ITERACIONES_PREDETERMINADAS,
                   help="100, 1000, 10000, 100000 o 1000000")
    p.add_argument("--semilla", type=int, default=fm.SEMILLA_PREDETERMINADA)
    p.add_argument("--corte", type=int, default=None, help="ultimo sorteo incluido (por defecto, el ultimo cargado)")
    p = sub.add_parser("listar", help="simulaciones guardadas")
    p.add_argument("--juego", type=_juego, default=None)
    p.add_argument("--limite", type=int, default=20)
    p = sub.add_parser("ver", help="una simulacion guardada (verificada)")
    p.add_argument("--id", required=True)
    p = sub.add_parser("exportar", help="JSON o CSV derivados de una simulacion")
    p.add_argument("--id", required=True)
    p.add_argument("--formato", choices=("json", "csv"), default="json")
    p = sub.add_parser("verificar", help="integridad, base actual y, si se pide, reproduccion")
    p.add_argument("--id", required=True)
    p.add_argument("--reproducir", action="store_true")
    p = sub.add_parser("consultar", help="progreso de una ejecucion")
    p.add_argument("--id", required=True)
    p = sub.add_parser("ejecuciones", help="trabajos recientes")
    p.add_argument("--limite", type=int, default=20)
    sub.add_parser("recuperar", help="marca como interrumpidas las ejecuciones cuyo proceso murio")
    sub.add_parser("rutas", help="rutas resueltas (sin credenciales)")
    return parser


def ejecutar(argv: list[str] | None, *, simulaciones_factory: Callable = simulaciones_reales, salida=sys.stdout,
             errores=sys.stderr) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as salida_argparse:
        return EXIT_USO if salida_argparse.code else EXIT_OK
    if args.orden == "rutas":
        _imprimir(rutas_resueltas(), salida)
        return EXIT_OK
    try:
        servicio = simulaciones_factory()
        return _orden(args, servicio, salida, errores)
    except SimulacionesError as error:
        return _error(errores, CODIGO_POR_ERROR.get(error.codigo, EXIT_FALLO), error.codigo, str(error))
    except EjecucionActivaError as error:
        _imprimir({"estado": "en_curso_en_otra_ejecucion", "activas": error.activas}, salida)
        return _error(errores, EXIT_ACTIVA, "activa", str(error))
    except OSError as error:
        return _error(errores, EXIT_CONEXION, "almacen_no_disponible", mensaje_legible(error))


def _progreso(errores):
    ultimo = {"fase": None, "decil": -1}

    def mostrar(ejecucion: dict) -> None:
        for r in ejecucion.get("juegos", {}).values():
            fase = r.get("fase")
            if fase == "simulando" and r.get("de"):
                decil = int(10 * r.get("hechas", 0) / r["de"])
                if decil != ultimo["decil"]:
                    errores.write(f"  {r['juego']}: {r.get('hechas', 0)}/{r['de']} iteraciones\n")
                    ultimo["decil"] = decil
            elif fase != ultimo["fase"]:
                errores.write(f"  {r['juego']}: {fase}\n")
            ultimo["fase"] = fase
    return mostrar


def _simular(args, servicio, salida, errores) -> int:
    inicio = servicio.iniciar(args.juego, args.iteraciones, args.semilla, args.corte, "comando")
    errores.write(f"simulacion: {args.juego}, {args.iteraciones} iteraciones (puede tardar)...\n")
    inicio.observador = _progreso(errores)
    final = servicio.ejecutar(inicio)
    _imprimir(final, salida)
    r = final["juegos"][args.juego]
    codigo = CODIGO_POR_ESTADO_DEL_JUEGO.get(r["estado"], EXIT_FALLO)
    if codigo:
        errores.write(f"AVISO [codigo {codigo}]: simulacion {r['estado']}: {r.get('mensaje')}\n")
    return codigo


def _verificacion(r: dict, salida, errores) -> int:
    _imprimir(r, salida)
    base = (r.get("base") or {}).get("estado")
    reproduccion = (r.get("reproduccion") or {}).get("estado")
    if base == "base_no_disponible":
        return _error(errores, EXIT_CONEXION, "base_no_disponible", r["base"].get("mensaje", ""))
    if base != "coincide" or reproduccion not in (None, "reproducida"):
        errores.write("AVISO [codigo 5]: historico actual distinto, reproduccion no aplicable o huella distinta\n")
        return EXIT_PARCIAL
    return EXIT_OK


def _orden(args, servicio, salida, errores) -> int:
    if args.orden == "catalogo":
        _imprimir(servicio.catalogo(), salida)
        return EXIT_OK
    if args.orden == "diagnostico":
        d = servicio.diagnostico(args.juego)
        _imprimir(d, salida)
        return {"disponible": EXIT_OK, "base_no_disponible": EXIT_CONEXION, "sin_datos": EXIT_MUESTRA,
                "muestra_insuficiente": EXIT_MUESTRA, "historico_no_valido": EXIT_MUESTRA}.get(d["estado"], EXIT_FALLO)
    if args.orden == "simular":
        return _simular(args, servicio, salida, errores)
    if args.orden == "listar":
        if not 1 <= args.limite <= 200:
            return _error(errores, EXIT_USO, "no_valido", "--limite debe estar entre 1 y 200")
        _imprimir({"simulaciones": servicio.listar(args.juego, args.limite)}, salida)
        return EXIT_OK
    if args.orden == "ver":
        _imprimir(servicio.obtener(args.id), salida)
        return EXIT_OK
    if args.orden == "exportar":
        _escribir(servicio.exportar_csv(args.id) if args.formato == "csv" else servicio.exportar_json(args.id), salida)
        return EXIT_OK
    if args.orden == "verificar":
        return _verificacion(servicio.verificar(args.id, reproducir=args.reproducir), salida, errores)
    if args.orden == "consultar":
        e = servicio.consultar_ejecucion(args.id) if identificador_valido(args.id) else None
        if e is None:
            return _error(errores, EXIT_USO, "no_encontrado", f"ejecucion no encontrada: {args.id}")
        _imprimir(e, salida)
        return EXIT_OK
    if args.orden == "ejecuciones":
        _imprimir({"ejecuciones": servicio.recientes(max(1, min(args.limite, 200)))}, salida)
        return EXIT_OK
    if args.orden == "recuperar":
        _imprimir({"interrumpidas_marcadas": servicio.recuperar()}, salida)
        return EXIT_OK
    return _error(errores, EXIT_USO, "no_valido", f"orden desconocida: {args.orden}")


def main(argv: list[str] | None = None) -> int:
    return ejecutar(argv)


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        sys.exit(main())
