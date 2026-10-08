#!/usr/bin/env python3
"""Producto 5: modelo combinado, carteras y simulacion desde la linea de
comandos (los mismos casos de uso que `/carteras`).

Uso (desde `backend`, con `DATABASE_URL` apuntando a la base):

  python -m scripts.carteras_modelos catalogo
  python -m scripts.carteras_modelos diagnostico --juego MILOTO
  python -m scripts.carteras_modelos comparar --juego todos [--bloques 6]
  python -m scripts.carteras_modelos comparar --juego BALOTO --corte 2700 --bloques 3
  python -m scripts.carteras_modelos configurar --juego BALOTO --modelo ensemble_temporal --cantidad 5 \
      --diversidad limitada --semilla 42
  python -m scripts.carteras_modelos configuracion --juego BALOTO
  python -m scripts.carteras_modelos generar --juego BALOTO --modelo ensemble_temporal [--cantidad 5] \
      [--diversidad libre] [--semilla 42] [--corte 2700]
  python -m scripts.carteras_modelos generar --juego todos --configuradas
  python -m scripts.carteras_modelos simular --cartera <clave> [--simulaciones 10000] [--semilla 42]
  python -m scripts.carteras_modelos consultar --id <ejecucion o clave>
  python -m scripts.carteras_modelos exportar --cartera <clave> --formato csv
  python -m scripts.carteras_modelos verificar --cartera <clave>    (o --comparacion / --simulacion)
  python -m scripts.carteras_modelos seguimiento --juego MILOTO [--linea <linea>] [--tipo seguimiento]
  python -m scripts.carteras_modelos ejecuciones --limite 10
  python -m scripts.carteras_modelos recuperar
  python -m scripts.carteras_modelos rutas

Ordenes:
- `catalogo`: modelos por juego, modelo combinado, protocolo, parametros de
  cartera y de simulacion.
- `diagnostico`: corte, objetivo, frescura, requisitos y configuracion vigente.
- `comparar`: compara el modelo combinado con los candidatos de Producto 4
  sobre la muestra comun (corte opcional, solo con un juego; `--bloques`
  1..6). Una entrada identica reutiliza la comparacion guardada.
- `configurar`: guarda una version nueva e inmutable de la configuracion.
- `generar`: una cartera con parametros explicitos, o la de la configuracion
  vigente de cada juego (`--configuradas`). Misma entrada -> la misma cartera.
- `simular`: simula una cartera guardada frente a la cartera uniforme del
  mismo juego, objetivo, tamano, diversidad y semilla.
- `consultar`: progreso de una ejecucion o artefacto por su clave.
- `exportar`: CSV UTF-8 (sin formulas) o JSON canonico de una cartera o de
  una simulacion, por la salida estandar.
- `verificar`: integridad, reproduccion y coincidencia con la base actual,
  por separado (recalcula; no guarda).
- `seguimiento`: aciertos observados por linea (primera emision sellada).
- `rutas`: rutas de almacenamiento efectivas; nunca `DATABASE_URL` ni `.env`.

`catalogo`, `diagnostico`, `configuracion`, `consultar`, `exportar`,
`verificar`, `seguimiento`, `ejecuciones` y `rutas` no escriben en ningun
almacen ni en PostgreSQL. Ninguna orden importa sorteos (eso sigue en
Producto 3).

Salida: JSON UTF-8 por la salida estandar (CSV en `exportar --formato csv`);
avisos y errores por la de errores, con `ERROR [codigo N] <codigo>: <mensaje>`.

Codigos de salida:
  0 exito
  2 uso incorrecto, parametro no valido o identificador no encontrado
  3 base de datos o almacen no disponibles
  4 muestra insuficiente o modelo que no se pudo ajustar
  5 resultado parcial: algun juego sin terminar bien (cartera parcial no
    publicada, sin configuracion, comparacion incompleta) o verificacion sin
    reproduccion exacta o con el historico cambiado
  6 ya hay un trabajo de carteras activo para alguno de los juegos
  7 fallo (ningun juego termino, o ejecucion interrumpida)
  8 archivo alterado o ilegible
  9 tiempo agotado del proceso trabajador
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

from app.application.interfaces.carteras_store import GuardadoCarteras
from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_construccion as cc
from app.application.ml import carteras_ensemble as ce
from app.application.ml import carteras_simulacion as cs
from app.application.use_cases.carteras import JUEGOS, CarterasError
from app.application.use_cases.operacion_diaria import EjecucionActivaError, identificador_valido, mensaje_legible

(EXIT_OK, EXIT_USO, EXIT_CONEXION, EXIT_MUESTRA, EXIT_PARCIAL, EXIT_ACTIVA, EXIT_FALLO, EXIT_ALTERADO,
 EXIT_TIEMPO) = (0, 2, 3, 4, 5, 6, 7, 8, 9)
CODIGO_POR_ERROR = {"no_encontrado": EXIT_USO, "no_valido": EXIT_USO, "alterado": EXIT_ALTERADO,
                    "no_disponible": EXIT_FALLO, "muestra_insuficiente": EXIT_MUESTRA, "parcial": EXIT_PARCIAL,
                    "sin_configuracion": EXIT_PARCIAL, "base_no_disponible": EXIT_CONEXION,
                    "tiempo_agotado": EXIT_TIEMPO, "fallo_del_trabajador": EXIT_FALLO}
CODIGO_POR_ESTADO = {"exito": EXIT_OK, "parcial": EXIT_PARCIAL, "fallo": EXIT_FALLO, "interrumpida": EXIT_FALLO}
# Si TODOS los juegos terminan igual, el codigo es el de ese estado.
CODIGO_SI_TODOS = {"muestra_insuficiente": EXIT_MUESTRA, "base_no_disponible": EXIT_CONEXION,
                   "tiempo_agotado": EXIT_TIEMPO, "sin_configuracion": EXIT_PARCIAL, "parcial": EXIT_PARCIAL}


def carteras_reales():
    from app.api.dependencies import get_carteras

    return get_carteras()


def rutas_resueltas() -> dict:
    from app.core.config import get_settings

    ajustes = get_settings()
    return {"directorio_de_trabajo": str(Path.cwd().resolve()),
            "directorio_pronosticos_experimentales": str(Path(ajustes.directorio_pronosticos_experimentales).resolve()),
            "directorio_operacion": str(Path(ajustes.directorio_operacion).resolve()),
            "directorio_laboratorio_modelos": str(Path(ajustes.directorio_laboratorio_modelos).resolve()),
            "directorio_carteras_modelos": str(Path(ajustes.directorio_carteras_modelos).resolve()),
            "tiempo_maximo_trabajador_carteras": ajustes.tiempo_maximo_trabajador_carteras}


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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Modelo combinado, carteras y simulacion (Producto 5)")
    sub = parser.add_subparsers(dest="orden", required=True)
    sub.add_parser("catalogo", help="modelos, protocolo y parametros")
    p = sub.add_parser("diagnostico", help="corte, objetivo y requisitos de un juego")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p = sub.add_parser("comparar", help="compara el modelo combinado en un juego o en todos")
    p.add_argument("--juego", required=True, choices=[*JUEGOS, "todos"])
    p.add_argument("--corte", type=int)
    p.add_argument("--bloques", type=int, default=ce.MAXIMO_BLOQUES, choices=range(1, ce.MAXIMO_BLOQUES + 1))
    p.add_argument("--perfil", default="predeterminado", choices=["predeterminado", "reducido"])
    p = sub.add_parser("configurar", help="guarda una version nueva de la configuracion de un juego")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p.add_argument("--modelo", required=True)
    p.add_argument("--cantidad", type=int, default=cc.CANTIDAD_PREDETERMINADA)
    p.add_argument("--diversidad", default="libre", choices=list(cc.DIVERSIDADES))
    p.add_argument("--semilla", type=int, default=cc.SEMILLA_PREDETERMINADA)
    p.add_argument("--perfil", default="predeterminado", choices=["predeterminado", "reducido"])
    p = sub.add_parser("configuracion", help="configuracion vigente y versiones de un juego")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p = sub.add_parser("generar", help="genera una cartera (o las configuradas)")
    p.add_argument("--juego", required=True, choices=[*JUEGOS, "todos"])
    p.add_argument("--configuradas", action="store_true")
    p.add_argument("--modelo")
    p.add_argument("--cantidad", type=int, default=cc.CANTIDAD_PREDETERMINADA)
    p.add_argument("--diversidad", default="libre", choices=list(cc.DIVERSIDADES))
    p.add_argument("--semilla", type=int, default=cc.SEMILLA_PREDETERMINADA)
    p.add_argument("--perfil", default="predeterminado", choices=["predeterminado", "reducido"])
    p.add_argument("--corte", type=int)
    p = sub.add_parser("simular", help="simula una cartera guardada frente a la uniforme")
    p.add_argument("--cartera", required=True)
    p.add_argument("--simulaciones", type=int, default=cs.SIMULACIONES_PREDETERMINADAS)
    p.add_argument("--semilla", type=int, default=cc.SEMILLA_PREDETERMINADA)
    p = sub.add_parser("consultar", help="progreso de una ejecucion o artefacto por su clave")
    p.add_argument("--id", required=True)
    p = sub.add_parser("exportar", help="CSV o JSON de una cartera o de una simulacion")
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--cartera")
    grupo.add_argument("--simulacion")
    p.add_argument("--formato", default="csv", choices=["csv", "json"])
    p = sub.add_parser("verificar", help="integridad, reproduccion y coincidencia con la base")
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--comparacion")
    grupo.add_argument("--cartera")
    grupo.add_argument("--simulacion")
    p = sub.add_parser("seguimiento", help="aciertos observados por linea")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p.add_argument("--linea")
    p.add_argument("--tipo", default="seguimiento", choices=["seguimiento", "retrospectiva"])
    p = sub.add_parser("ejecuciones", help="trabajos recientes")
    p.add_argument("--limite", type=int, default=10)
    sub.add_parser("recuperar", help="marca como interrumpidos los trabajos cuyo proceso murio")
    sub.add_parser("rutas", help="rutas de almacenamiento resueltas (sin credenciales)")
    return parser


def ejecutar(argv: list[str] | None, *, carteras_factory: Callable = carteras_reales, salida=sys.stdout,
             errores=sys.stderr) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as salida_argparse:
        return EXIT_USO if salida_argparse.code else EXIT_OK
    if args.orden == "rutas":
        _imprimir(rutas_resueltas(), salida)
        return EXIT_OK
    try:
        servicio = carteras_factory()
        return _orden(args, servicio, salida, errores)
    except CarterasError as error:
        return _error(errores, CODIGO_POR_ERROR.get(error.codigo, EXIT_FALLO), error.codigo, str(error))
    except EjecucionActivaError as error:
        _imprimir({"estado": "en_curso_en_otra_ejecucion", "activas": error.activas}, salida)
        return _error(errores, EXIT_ACTIVA, "activa", str(error))
    except OSError as error:
        return _error(errores, EXIT_CONEXION, "almacen_no_disponible", mensaje_legible(error))


def _trabajo(servicio, tipo: str, juegos: list[str], parametros: dict, salida, errores) -> int:
    inicio = servicio.iniciar(tipo, juegos, parametros, "comando")
    errores.write(f"{tipo}: {', '.join(juegos)} (puede tardar)...\n")
    final = servicio.ejecutar(inicio)
    _imprimir(final, salida)
    codigo = CODIGO_POR_ESTADO.get(final["estado"], EXIT_FALLO)
    estados = {r["estado"] for r in final["juegos"].values()}
    if len(estados) == 1 and next(iter(estados)) in CODIGO_SI_TODOS:
        codigo = CODIGO_SI_TODOS[next(iter(estados))]
    if codigo:
        problemas = {j: r["estado"] for j, r in final["juegos"].items() if r["estado"] not in ("terminado", "reutilizado")}
        errores.write(f"AVISO [codigo {codigo}]: trabajo {final['estado']}; juegos con incidencias: "
                      f"{json.dumps(problemas, ensure_ascii=False)}\n")
    return codigo


def _artefacto_por_clave(servicio, clave: str) -> dict:
    for tipo in ("comparacion", "cartera", "simulacion"):
        try:
            guardado = getattr(servicio, tipo)(clave)
        except CarterasError as error:
            if error.codigo == "no_encontrado":
                continue
            raise
        return {"tipo": tipo, "artefacto": guardado.artefacto}
    raise CarterasError("no_encontrado", f"no hay ejecucion ni artefacto con la clave {clave}")


def _verificacion(r: dict, salida, errores) -> int:
    _imprimir(r, salida)
    if r["integridad"] != "correcta":
        return _error(errores, EXIT_ALTERADO, "alterado", r.get("motivo", "archivo alterado"))
    reproduccion = r.get("reproduccion") or {}
    base = r.get("base_actual") or {}
    coincide = base.get("historico_hasta_el_corte", "coincide") in ("coincide", "no_disponible")
    if not reproduccion.get("huella_exacta") or not coincide:
        errores.write("AVISO [codigo 5]: verificacion sin reproduccion exacta o con el historico actual distinto\n")
        return EXIT_PARCIAL
    return EXIT_OK


def _orden(args, servicio, salida, errores) -> int:
    if args.orden == "catalogo":
        _imprimir(servicio.catalogo(), salida)
        return EXIT_OK
    if args.orden == "diagnostico":
        d = servicio.diagnostico(args.juego)
        _imprimir(d, salida)
        return {"disponible": EXIT_OK, "base_no_disponible": EXIT_CONEXION, "sin_datos": EXIT_MUESTRA}.get(
            d["estado"], EXIT_FALLO)
    if args.orden == "comparar":
        juegos = list(JUEGOS) if args.juego == "todos" else [args.juego]
        parametros = {"protocolo": {"bloques": args.bloques, "perfil": args.perfil}, "corte": args.corte}
        return _trabajo(servicio, "comparacion", juegos, parametros, salida, errores)
    if args.orden == "configurar":
        g = servicio.configurar(args.juego, args.modelo, args.cantidad, args.diversidad, args.semilla, args.perfil,
                                origen="comando")
        _imprimir({"version": g.artefacto["version"], "configuracion": g.artefacto}, salida)
        return EXIT_OK
    if args.orden == "configuracion":
        vigente = servicio.configuracion_vigente(args.juego)
        _imprimir({"juego": args.juego, "vigente": vigente.artefacto if vigente else None,
                   "versiones": [e.artefacto if isinstance(e, GuardadoCarteras) else
                                 {"version": e.identificador, "estado": "ilegible", "motivo": e.motivo}
                                 for e in servicio.configuraciones(args.juego)]}, salida)
        return EXIT_OK
    if args.orden == "generar":
        juegos = list(JUEGOS) if args.juego == "todos" else [args.juego]
        if args.configuradas:
            if args.modelo or args.corte is not None:
                return _error(errores, EXIT_USO, "no_valido", "--configuradas no admite --modelo ni --corte")
            return _trabajo(servicio, "carteras_configuradas", juegos, {}, salida, errores)
        if not args.modelo or len(juegos) != 1:
            return _error(errores, EXIT_USO, "no_valido", "indica un juego y --modelo (o usa --configuradas)")
        parametros = {"modelo": args.modelo, "perfil": args.perfil, "cantidad": args.cantidad,
                      "diversidad": args.diversidad, "semilla": args.semilla, "corte": args.corte}
        return _trabajo(servicio, "cartera", juegos, parametros, salida, errores)
    if args.orden == "simular":
        juego = servicio.cartera(args.cartera).juego
        parametros = {"cartera": args.cartera, "simulaciones": args.simulaciones, "semilla": args.semilla}
        return _trabajo(servicio, "simulacion", [juego], parametros, salida, errores)
    if args.orden == "consultar":
        if identificador_valido(args.id):
            e = servicio.consultar_ejecucion(args.id)
            if e is None:
                return _error(errores, EXIT_USO, "no_encontrado", f"ejecucion no encontrada: {args.id}")
            _imprimir(e, salida)
            return EXIT_OK
        _imprimir(_artefacto_por_clave(servicio, args.id), salida)
        return EXIT_OK
    if args.orden == "exportar":
        guardado = servicio.cartera(args.cartera) if args.cartera else servicio.simulacion(args.simulacion)
        if args.formato == "json":
            _escribir(ca.json_canonico(guardado.artefacto).decode("utf-8"), salida)  # ya termina en salto de linea
        elif args.cartera:
            _escribir(ca.csv_de_cartera(guardado.artefacto), salida)
        else:
            _escribir(ca.csv_de_simulacion(guardado.artefacto), salida)
        return EXIT_OK
    if args.orden == "verificar":
        if args.comparacion:
            return _verificacion(servicio.verificar_comparacion(args.comparacion), salida, errores)
        if args.cartera:
            return _verificacion(servicio.verificar_cartera(args.cartera), salida, errores)
        return _verificacion(servicio.verificar_simulacion(args.simulacion), salida, errores)
    if args.orden == "seguimiento":
        _imprimir(servicio.seguimiento(args.juego, args.linea, args.tipo), salida)
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
