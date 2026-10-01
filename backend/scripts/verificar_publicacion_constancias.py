#!/usr/bin/env python3
"""AE-81, validada localmente como trabajo preparatorio: verificacion
offline y de solo lectura de la publicacion sintetica y el monitoreo
cruzado de constancias AE-80.

Uso (desde `backend`):

  python -m scripts.verificar_publicacion_constancias EXPEDIENTE EXPEDIENTE [...]
         --politica POLITICA --politica-auditoria POLITICA_AUDITORIA
         [--capturas CAPTURAS ...]
         --politica-constancias POLITICA_CONSTANCIAS
         [--constancias CONSTANCIAS ...]
         --politica-publicadores POLITICA_ROL --politica-monitores POLITICA_ROL
         [--checkpoints CHECKPOINTS ...] [--observaciones OBSERVACIONES ...]
         [--inventario INVENTARIO] [--formato texto|json] [--salida-json RUTA]

Recalcula AE-79 y AE-80 con sus verificadores reales y vincula sus
cabezas con los checkpoints `checkpoints-publicacion/1` y las observaciones
`observaciones-monitor/1` (hasta 8 directorios de cada tipo). Las politicas
de rol (`politica-rol-de-prueba/1`) y el inventario esperado
(`inventario-esperado-de-prueba/1`) los suministra quien verifica.

Codigos de salida (ninguno autoriza evaluacion; prioridad 1, 3, 4, 6, 5, 0):
  0  lo presentado coincide con las referencias y el inventario suministrados;
  1  bytes firmados presentados que se contradicen;
  2  uso incorrecto;
  3  lectura rechazada, limite agregado superado o politicas de rol
     incompatibles;
  4  firma, clave, referencia, cabeza o inventario que no coincide;
  5  evidencia incompleta (referencias, predecesores o entradas esperadas);
  6  discrepancia entre actores sin contexto para probar una contradiccion.

Cada directorio se lee con la lectura endurecida de AE-78 y con el
presupuesto agregado de AE-79 compartido por todas las entradas. Solo lee:
el unico archivo que puede escribir es el informe de `--salida-json`, fuera
de todos los directorios auditados y sin sobrescribir. Sin red, reloj,
deserializacion ejecutable ni secretos.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.application.ml import auditoria_cruzada as ac
from app.application.ml import constancias_auditoria as ca
from app.application.ml import publicacion_constancias as pc
from scripts.auditar_expedientes_cruzados import _Cargador, _LimiteAgregado


def _salida(informe: dict, formato: str) -> None:
    if formato == "json":
        sys.stdout.write(pc.informe_json(informe).decode("utf-8"))
    else:
        sys.stdout.write(pc.resumen_legible(informe))


def _uso(mensaje: str) -> int:
    sys.stderr.write(mensaje + "\n")
    return pc.CODIGOS_DE_SALIDA["uso_incorrecto"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verificacion offline de publicacion de constancias (AE-81)")
    parser.add_argument("expedientes", nargs="+")
    parser.add_argument("--politica", required=True)
    parser.add_argument("--politica-auditoria", required=True)
    parser.add_argument("--capturas", action="append", default=[])
    parser.add_argument("--politica-constancias", required=True)
    parser.add_argument("--constancias", action="append", default=[])
    parser.add_argument("--politica-publicadores", required=True)
    parser.add_argument("--politica-monitores", required=True)
    parser.add_argument("--checkpoints", action="append", default=[])
    parser.add_argument("--observaciones", action="append", default=[])
    parser.add_argument("--inventario")
    parser.add_argument("--formato", choices=("texto", "json"), default="texto")
    parser.add_argument("--salida-json")
    args = parser.parse_args(argv)

    if not ac.MINIMO_DE_EXPEDIENTES <= len(args.expedientes) <= ac.MAXIMO_DE_EXPEDIENTES:
        return _uso(f"hacen falta entre {ac.MINIMO_DE_EXPEDIENTES} y {ac.MAXIMO_DE_EXPEDIENTES} expedientes")
    for nombre, lista, maximo in (("capturas", args.capturas, ac.MAXIMO_DE_CONJUNTOS_DE_CAPTURAS),
                                  ("constancias", args.constancias, ca.MAXIMO_DE_CONJUNTOS_DE_CONSTANCIAS),
                                  ("checkpoints", args.checkpoints, pc.MAXIMO_DE_CONJUNTOS),
                                  ("observaciones", args.observaciones, pc.MAXIMO_DE_CONJUNTOS)):
        if len(lista) > maximo:
            return _uso(f"como maximo {maximo} directorios de {nombre}")
    auditados = [Path(p).resolve() for p in (*args.expedientes, args.politica, args.politica_auditoria,
                                             *args.capturas, args.politica_constancias, *args.constancias,
                                             args.politica_publicadores, args.politica_monitores,
                                             *args.checkpoints, *args.observaciones,
                                             *([args.inventario] if args.inventario else []))]
    if len(auditados) != len(set(auditados)):
        return _uso("un mismo directorio aparece dos veces")
    destino = None
    if args.salida_json:
        destino = Path(args.salida_json).resolve()
        if any(destino == d or destino.is_relative_to(d) for d in auditados):
            return _uso("la salida JSON debe quedar fuera de todos los directorios auditados")
        if destino.exists():
            return _uso("la salida JSON ya existe; no se sobrescribe")

    cargar = _Cargador()
    try:
        entradas = {
            "politica_del_verificador": cargar(Path(args.politica)),
            "politica_de_auditoria": cargar(Path(args.politica_auditoria)),
            "expedientes": [cargar(Path(p)) for p in args.expedientes],
            "capturas": [cargar(Path(p)) for p in args.capturas],
            "politica_de_constancias": cargar(Path(args.politica_constancias)),
            "constancias": [cargar(Path(p)) for p in args.constancias],
            "politica_de_publicadores": cargar(Path(args.politica_publicadores)),
            "politica_de_monitores": cargar(Path(args.politica_monitores)),
            "checkpoints": [cargar(Path(p)) for p in args.checkpoints],
            "observaciones": [cargar(Path(p)) for p in args.observaciones],
            "inventario": cargar(Path(args.inventario)) if args.inventario else None,
        }
    except _LimiteAgregado:
        informe = pc.informe_de_lectura_rechazada("entradas", "limite_agregado_superado")
    else:
        informe = pc.verificar(**entradas)
    _salida(informe, args.formato)
    if destino is not None:
        with open(destino, "xb") as flujo:
            flujo.write(pc.informe_json(informe))
    return pc.codigo_de_salida(informe)


if __name__ == "__main__":
    sys.exit(main())
