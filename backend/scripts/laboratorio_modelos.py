#!/usr/bin/env python3
"""Producto 4: laboratorio de modelos desde la linea de comandos (los mismos
casos de uso que `/laboratorio`).

Uso (desde `backend`, con `DATABASE_URL` apuntando a la base):

  python -m scripts.laboratorio_modelos catalogo
  python -m scripts.laboratorio_modelos diagnostico --juego MILOTO
  python -m scripts.laboratorio_modelos comparar --juego todos
  python -m scripts.laboratorio_modelos comparar --juego BALOTO --corte 2700 --bloques 3
  python -m scripts.laboratorio_modelos consultar --id <ejecucion o clave de experimento>
  python -m scripts.laboratorio_modelos experimentos --juego BALOTO
  python -m scripts.laboratorio_modelos generar --experimento <clave> --modelo hgb_clasificador
  python -m scripts.laboratorio_modelos verificar --experimento <clave>
  python -m scripts.laboratorio_modelos verificar --pronostico <clave>
  python -m scripts.laboratorio_modelos seguimiento --juego MILOTO [--linea <linea>] [--tipo seguimiento]
  python -m scripts.laboratorio_modelos ejecuciones --limite 10
  python -m scripts.laboratorio_modelos recuperar
  python -m scripts.laboratorio_modelos rutas
  python -m scripts.laboratorio_modelos entrenar --experimento <clave> --modelo random_forest_clasificador
  python -m scripts.laboratorio_modelos modelos [--juego BALOTO]
  python -m scripts.laboratorio_modelos modelo --clave <clave del modelo registrado>
  python -m scripts.laboratorio_modelos verificar --modelo <clave del modelo registrado>
  python -m scripts.laboratorio_modelos generar-con-modelo --clave <clave> [--corte 2719]

Ordenes:
- `catalogo`: modelos, juegos, recetas, requisitos y protocolo.
- `diagnostico`: muestra, corte, frescura y disponibilidad de cada candidato.
- `comparar`: compara los candidatos de un juego o de todos sobre la muestra
  comun, con corte opcional (un sorteo cargado; solo con un juego) y
  `--bloques` 1..6. Escribe solo en el almacen del laboratorio. Una entrada
  identica reutiliza el informe guardado.
- `consultar`: progreso de una ejecucion o informe de un experimento.
- `generar`: pronostico con un candidato de un experimento (instantanea
  congelada del experimento). Misma entrada -> el mismo pronostico.
- `verificar`: integridad, reproduccion con la instantanea guardada y
  coincidencia con la base actual, por separado (reentrena; no guarda).
- `seguimiento`: resultados observados por linea de modelo.
- `rutas`: rutas de almacenamiento efectivas; nunca `DATABASE_URL` ni `.env`.
- Fase 3: `entrenar` entrena un candidato registrable de un informe con su
  instantanea y guarda la version (manifiesto + estimador); misma entrada ->
  la misma version. `modelos` y `modelo` consultan las versiones (sin cargar
  el estimador). `verificar --modelo` comprueba integridad, compatibilidad,
  carga restringida y el pronostico de control. `generar-con-modelo` recarga
  la version y pronostica el sorteo siguiente al corte de entrada (por
  defecto, el ultimo cargado; nunca anterior al de entrenamiento) sin
  reentrenar. Elegir una version para la operacion diaria se hace con
  `python -m scripts.carteras_modelos configurar ... --registrado <clave>`.

`catalogo`, `consultar`, `experimentos`, `verificar`, `seguimiento`,
`ejecuciones`, `modelos`, `modelo` y `rutas` no escriben en ningun almacen ni
en PostgreSQL.
Ninguna orden importa desde el origen oficial (eso sigue en Producto 3).

Salida: JSON UTF-8 por la salida estandar; avisos y errores por la de
errores, con `ERROR [codigo N] <codigo>: <mensaje>`.

Codigos de salida:
  0 exito
  2 uso incorrecto o identificador no encontrado
  3 base de datos o almacen no disponibles
  4 muestra insuficiente o modelo que no se pudo ajustar (no converge,
    clase insuficiente, salida no valida)
  5 resultado parcial: algun juego o candidato sin evaluacion completa, o una
    verificacion sin reproduccion exacta o con el historico cambiado
  6 ya hay una comparacion activa para alguno de los juegos
  7 fallo (ningun juego termino, o ejecucion interrumpida)
  8 archivo alterado o ilegible (tambien un estimador alterado o no admitido)
  9 modelo registrado incompatible con este entorno (no se carga)
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

from app.application.ml import laboratorio_evaluacion as le
from app.application.use_cases.laboratorio import JUEGOS, LaboratorioError
from app.application.use_cases.operacion_diaria import EjecucionActivaError, identificador_valido, mensaje_legible

EXIT_OK, EXIT_USO, EXIT_CONEXION, EXIT_MUESTRA, EXIT_PARCIAL, EXIT_ACTIVA, EXIT_FALLO, EXIT_ALTERADO = (
    0, 2, 3, 4, 5, 6, 7, 8)
EXIT_INCOMPATIBLE = 9
CODIGO_POR_ERROR = {"no_encontrado": EXIT_USO, "no_valido": EXIT_USO, "alterado": EXIT_ALTERADO,
                    "no_disponible": EXIT_FALLO, "muestra_insuficiente": EXIT_MUESTRA, "no_converge": EXIT_MUESTRA,
                    "clase_insuficiente": EXIT_MUESTRA, "salida_invalida": EXIT_MUESTRA,
                    "fallo_de_ajuste": EXIT_MUESTRA, "base_no_disponible": EXIT_CONEXION,
                    "incompatible": EXIT_INCOMPATIBLE, "corte_no_valido": EXIT_USO, "no_registrable": EXIT_USO,
                    "estimador_no_admitido": EXIT_ALTERADO, "no_reproduce": EXIT_FALLO, "tiempo_agotado": EXIT_FALLO,
                    "fallo_del_trabajador": EXIT_FALLO, "fallo": EXIT_FALLO}
CODIGO_POR_ESTADO = {"exito": EXIT_OK, "parcial": EXIT_PARCIAL, "fallo": EXIT_FALLO, "interrumpida": EXIT_FALLO}


def laboratorio_real():
    from app.api.dependencies import get_laboratorio

    return get_laboratorio()


def rutas_resueltas() -> dict:
    from app.core.config import get_settings

    ajustes = get_settings()
    return {"directorio_de_trabajo": str(Path.cwd().resolve()),
            "directorio_pronosticos_experimentales": str(Path(ajustes.directorio_pronosticos_experimentales).resolve()),
            "directorio_operacion": str(Path(ajustes.directorio_operacion).resolve()),
            "directorio_laboratorio_modelos": str(Path(ajustes.directorio_laboratorio_modelos).resolve()),
            "directorio_modelos_registrados": str((Path(ajustes.directorio_laboratorio_modelos) / "modelos").resolve())}


def _imprimir(objeto, salida) -> None:
    texto = json.dumps(objeto, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n"
    buffer = getattr(salida, "buffer", None)
    if buffer is not None:
        buffer.write(texto.encode("utf-8"))
        buffer.flush()
    else:
        salida.write(texto)


def _error(errores, codigo: int, nombre: str, mensaje: str) -> int:
    errores.write(f"ERROR [codigo {codigo}] {nombre}: {mensaje}\n")
    return codigo


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Laboratorio de modelos (Producto 4)")
    sub = parser.add_subparsers(dest="orden", required=True)
    sub.add_parser("catalogo", help="modelos, recetas y requisitos")
    p = sub.add_parser("diagnostico", help="muestra y disponibilidad de un juego")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p = sub.add_parser("comparar", help="compara los candidatos de un juego o de todos")
    p.add_argument("--juego", required=True, choices=[*JUEGOS, "todos"])
    p.add_argument("--corte", type=int)
    p.add_argument("--bloques", type=int, default=le.MAXIMO_BLOQUES, choices=range(1, le.MAXIMO_BLOQUES + 1))
    p.add_argument("--perfil", default="predeterminado", choices=["predeterminado", "reducido"])
    p = sub.add_parser("consultar", help="progreso de una ejecucion o informe de un experimento")
    p.add_argument("--id", required=True)
    p = sub.add_parser("experimentos", help="experimentos guardados de un juego")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p = sub.add_parser("generar", help="pronostico con un modelo de un experimento")
    p.add_argument("--experimento", required=True)
    p.add_argument("--modelo", required=True)
    p = sub.add_parser("verificar", help="integridad, reproduccion y coincidencia con la base")
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--experimento")
    grupo.add_argument("--pronostico")
    grupo.add_argument("--modelo", help="clave de un modelo registrado (Fase 3)")
    p = sub.add_parser("seguimiento", help="resultados observados por linea de modelo")
    p.add_argument("--juego", required=True, choices=list(JUEGOS))
    p.add_argument("--linea")
    p.add_argument("--tipo", default="seguimiento", choices=["seguimiento", "retrospectiva"])
    p = sub.add_parser("ejecuciones", help="comparaciones recientes")
    p.add_argument("--limite", type=int, default=10)
    sub.add_parser("recuperar", help="marca como interrumpidas las comparaciones cuyo proceso murio")
    sub.add_parser("rutas", help="rutas de almacenamiento resueltas (sin credenciales)")
    p = sub.add_parser("entrenar", help="entrena y guarda una version de un modelo de un experimento")
    p.add_argument("--experimento", required=True)
    p.add_argument("--modelo", required=True)
    p = sub.add_parser("modelos", help="versiones registradas (sin cargar estimadores)")
    p.add_argument("--juego", choices=list(JUEGOS))
    p = sub.add_parser("modelo", help="ficha de una version registrada")
    p.add_argument("--clave", required=True)
    p = sub.add_parser("generar-con-modelo", help="pronostico con una version registrada, sin reentrenar")
    p.add_argument("--clave", required=True)
    p.add_argument("--corte", type=int)
    return parser


def ejecutar(argv: list[str] | None, *, laboratorio_factory: Callable = laboratorio_real, salida=sys.stdout,
             errores=sys.stderr) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as salida_argparse:
        return EXIT_USO if salida_argparse.code else EXIT_OK
    if args.orden == "rutas":
        _imprimir(rutas_resueltas(), salida)
        return EXIT_OK
    try:
        lab = laboratorio_factory()
        return _orden(args, lab, salida, errores)
    except LaboratorioError as error:
        return _error(errores, CODIGO_POR_ERROR.get(error.codigo, EXIT_FALLO), error.codigo, str(error))
    except EjecucionActivaError as error:
        _imprimir({"estado": "en_curso_en_otra_ejecucion", "activas": error.activas}, salida)
        return _error(errores, EXIT_ACTIVA, "activa", str(error))
    except OSError as error:
        return _error(errores, EXIT_CONEXION, "almacen_no_disponible", mensaje_legible(error))


def _orden(args, lab, salida, errores) -> int:
    if args.orden == "catalogo":
        _imprimir(lab.catalogo(), salida)
        return EXIT_OK
    if args.orden == "diagnostico":
        d = lab.diagnostico(args.juego)
        _imprimir(d, salida)
        return {"disponible": EXIT_OK, "muestra_insuficiente": EXIT_MUESTRA, "base_no_disponible": EXIT_CONEXION,
                "sin_datos": EXIT_MUESTRA}.get(d["estado"], EXIT_FALLO)
    if args.orden == "comparar":
        juegos = list(JUEGOS) if args.juego == "todos" else [args.juego]
        try:
            protocolo = le.Protocolo(bloques=args.bloques, perfil=args.perfil)
        except ValueError as error:
            return _error(errores, EXIT_USO, "no_valido", str(error))
        errores.write(f"Comparando {', '.join(juegos)} (puede tardar)...\n")
        final = lab.comparar_ahora(juegos, protocolo, "comando", args.corte)
        _imprimir(final, salida)
        codigo = CODIGO_POR_ESTADO.get(final["estado"], EXIT_FALLO)
        estados = {r["estado"] for r in final["juegos"].values()}
        if estados == {"muestra_insuficiente"}:
            codigo = EXIT_MUESTRA
        elif estados == {"base_no_disponible"}:
            codigo = EXIT_CONEXION
        if codigo:
            problemas = {j: r["estado"] for j, r in final["juegos"].items() if r["estado"] not in ("terminado", "reutilizado")}
            errores.write(f"AVISO [codigo {codigo}]: comparacion {final['estado']}; juegos con incidencias: "
                          f"{json.dumps(problemas, ensure_ascii=False)}\n")
        return codigo
    if args.orden == "consultar":
        if identificador_valido(args.id):
            e = lab.consultar_ejecucion(args.id)
            if e is None:
                return _error(errores, EXIT_USO, "no_encontrado", f"ejecucion no encontrada: {args.id}")
            _imprimir(e, salida)
            return EXIT_OK
        informe = lab.experimento(args.id).artefacto
        _imprimir({"informe": informe, "base_actual": lab.estado_frente_a_la_base(informe)}, salida)
        return EXIT_OK
    if args.orden == "experimentos":
        _imprimir({"juego": args.juego, "experimentos": [
            {"clave": e.identificador, "corte": e.artefacto["datos"]["corte"], "resumen": e.artefacto["resumen"]["estado"],
             "terminado_en": e.artefacto["ejecucion"].get("terminado_en")} if hasattr(e, "artefacto")
            else {"clave": e.identificador, "estado": "ilegible", "motivo": e.motivo}
            for e in lab.experimentos(args.juego)]}, salida)
        return EXIT_OK
    if args.orden == "generar":
        g = lab.generar(args.experimento, args.modelo)
        _imprimir({"identificador": g.identificador, "reutilizado": g.reutilizado, "linea": g.linea,
                   "version": g.version, "versiones": g.versiones, "pronostico": g.artefacto}, salida)
        return EXIT_OK
    if args.orden == "verificar" and args.modelo:
        r = lab.verificar_modelo(args.modelo)
        _imprimir(r, salida)
        if r["integridad"] != "correcta":
            return _error(errores, EXIT_ALTERADO, "alterado", r.get("motivo", "modelo alterado"))
        if not r["compatibilidad"]["compatible"]:
            return _error(errores, EXIT_INCOMPATIBLE, "incompatible", "; ".join(r["compatibilidad"]["motivos"]))
        if (r.get("carga") or {}).get("estado") != "correcta":
            carga = r.get("carga") or {}
            return _error(errores, CODIGO_POR_ERROR.get(carga.get("estado"), EXIT_FALLO), carga.get("estado", "fallo"),
                          carga.get("motivo", "no se pudo cargar"))
        if not (r.get("reproduccion") or {}).get("exacta"):
            errores.write("AVISO [codigo 5]: el estimador recargado no reproduce el pronostico de control\n")
            return EXIT_PARCIAL
        return EXIT_OK
    if args.orden == "verificar":
        r = lab.verificar_experimento(args.experimento) if args.experimento else lab.verificar_pronostico(args.pronostico)
        _imprimir(r, salida)
        if r["integridad"] != "correcta":
            return _error(errores, EXIT_ALTERADO, "alterado", r.get("motivo", "archivo alterado"))
        reproduccion = r.get("reproduccion") or {}
        base = r.get("base_actual") or {}
        coincide = base.get("historico_hasta_el_corte", base.get("estado")) in ("coincide", None)
        if not reproduccion.get("huella_exacta") or not coincide:
            errores.write("AVISO [codigo 5]: verificacion sin reproduccion exacta o con el historico actual distinto\n")
            return EXIT_PARCIAL
        return EXIT_OK
    if args.orden == "seguimiento":
        _imprimir(lab.seguimiento(args.juego, args.linea, args.tipo), salida)
        return EXIT_OK
    if args.orden == "ejecuciones":
        _imprimir({"ejecuciones": lab.recientes(max(1, min(args.limite, 200)))}, salida)
        return EXIT_OK
    if args.orden == "recuperar":
        _imprimir({"interrumpidas_marcadas": lab.recuperar()}, salida)
        return EXIT_OK
    if args.orden == "entrenar":
        errores.write(f"Entrenando {args.modelo} con el experimento {args.experimento[:12]}... (puede tardar)\n")
        final = lab.entrenar_ahora(args.experimento, args.modelo, "comando")
        _imprimir(final, salida)
        r = next(iter(final["juegos"].values()))
        if r["estado"] in ("terminado", "reutilizado"):
            return EXIT_OK
        return _error(errores, CODIGO_POR_ERROR.get(r["estado"], EXIT_FALLO), r["estado"], r.get("mensaje") or "")
    if args.orden == "modelos":
        _imprimir({"juegos": {j: lab.modelos(j) for j in ([args.juego] if args.juego else JUEGOS)}}, salida)
        return EXIT_OK
    if args.orden == "modelo":
        _imprimir(lab.ficha_del_modelo(args.clave), salida)
        return EXIT_OK
    if args.orden == "generar-con-modelo":
        g = lab.generar_con_modelo(args.clave, args.corte, "comando")
        _imprimir({"identificador": g.identificador, "reutilizado": g.reutilizado, "linea": g.linea,
                   "objetivo": g.objetivo, "version": g.version, "versiones": g.versiones, "pronostico": g.artefacto},
                  salida)
        return EXIT_OK
    return _error(errores, EXIT_USO, "no_valido", f"orden desconocida: {args.orden}")


def main(argv: list[str] | None = None) -> int:
    return ejecutar(argv)


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        sys.exit(main())
