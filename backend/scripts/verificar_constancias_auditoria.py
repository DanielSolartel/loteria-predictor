#!/usr/bin/env python3
"""AE-80, validada localmente como trabajo preparatorio: verificacion
offline y de solo lectura de constancias firmadas de una auditoria cruzada
AE-79.

Uso (desde `backend`):

  python -m scripts.verificar_constancias_auditoria EXPEDIENTE EXPEDIENTE [...]
         --politica POLITICA --politica-auditoria POLITICA_AUDITORIA
         [--capturas CAPTURAS ...]
         --politica-constancias POLITICA_CONSTANCIAS
         [--constancias CONSTANCIAS ...]
         [--huella-politica-constancias SHA256] [--huella-constancia SHA256 ...]
         [--formato texto|json] [--salida-json RUTA]

Recalcula la auditoria AE-79 con el auditor real (nunca acepta un informe
aportado) y la coteja con cada directorio `constancias-auditoria/1` (hasta
8) y con POLITICA_CONSTANCIAS (`politica-constancias-de-prueba/1`), que
suministra quien verifica. La huella de una constancia es el SHA-256 de su
`datos.json`; una huella copiada de los propios archivos no es una
publicacion independiente.

Codigos de salida (ninguno autoriza evaluacion; prioridad 1, 3, 4, 5, 0):
  0  las constancias cabeza admitidas coinciden con la auditoria recalculada;
  1  constancias firmadas presentadas que se contradicen (bifurcacion,
     vinculo roto o desacuerdo), sin adjudicar cual es cierta;
  2  uso incorrecto (argumentos, numero de entradas, directorio repetido,
     huella mal formada o salida no admitida);
  3  la lectura endurecida rechazo al menos una entrada o se supero el
     limite agregado;
  4  una constancia, firma, politica o huella esperada no coincide;
  5  no hay ninguna constancia admitida que cotejar.

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
from scripts.auditar_expedientes_cruzados import _Cargador, _huella, _LimiteAgregado


def _salida(informe: dict, formato: str) -> None:
    if formato == "json":
        sys.stdout.write(ca.informe_json(informe).decode("utf-8"))
    else:
        sys.stdout.write(ca.resumen_legible(informe))


def _uso(mensaje: str) -> int:
    sys.stderr.write(mensaje + "\n")
    return ca.CODIGOS_DE_SALIDA["uso_incorrecto"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verificacion offline de constancias de auditoria (AE-80)")
    parser.add_argument("expedientes", nargs="+")
    parser.add_argument("--politica", required=True)
    parser.add_argument("--politica-auditoria", required=True)
    parser.add_argument("--capturas", action="append", default=[])
    parser.add_argument("--politica-constancias", required=True)
    parser.add_argument("--constancias", action="append", default=[])
    parser.add_argument("--huella-politica-constancias", type=_huella)
    parser.add_argument("--huella-constancia", type=_huella, action="append", default=[])
    parser.add_argument("--formato", choices=("texto", "json"), default="texto")
    parser.add_argument("--salida-json")
    args = parser.parse_args(argv)

    if not ac.MINIMO_DE_EXPEDIENTES <= len(args.expedientes) <= ac.MAXIMO_DE_EXPEDIENTES:
        return _uso(f"hacen falta entre {ac.MINIMO_DE_EXPEDIENTES} y {ac.MAXIMO_DE_EXPEDIENTES} expedientes")
    if len(args.capturas) > ac.MAXIMO_DE_CONJUNTOS_DE_CAPTURAS:
        return _uso(f"como maximo {ac.MAXIMO_DE_CONJUNTOS_DE_CAPTURAS} directorios de capturas")
    if len(args.constancias) > ca.MAXIMO_DE_CONJUNTOS_DE_CONSTANCIAS:
        return _uso(f"como maximo {ca.MAXIMO_DE_CONJUNTOS_DE_CONSTANCIAS} directorios de constancias")
    auditados = [Path(p).resolve() for p in (*args.expedientes, args.politica, args.politica_auditoria,
                                             *args.capturas, args.politica_constancias, *args.constancias)]
    if len(auditados) != len(set(auditados)):
        return _uso("un mismo directorio aparece dos veces")
    destino = None
    if args.salida_json:
        destino = Path(args.salida_json).resolve()
        if any(destino == d or destino.is_relative_to(d) for d in auditados):
            return _uso("la salida JSON debe quedar fuera de todos los directorios auditados")
        if destino.exists():
            return _uso("la salida JSON ya existe; no se sobrescribe")
    referencias = ca.ReferenciasDeConstancias(politica_de_constancias=args.huella_politica_constancias,
                                              constancias=frozenset(args.huella_constancia))

    cargar = _Cargador()
    try:
        politica = cargar(Path(args.politica))
        politica_auditoria = cargar(Path(args.politica_auditoria))
        expedientes = [cargar(Path(p)) for p in args.expedientes]
        capturas = [cargar(Path(p)) for p in args.capturas]
        politica_constancias = cargar(Path(args.politica_constancias))
        constancias = [cargar(Path(p)) for p in args.constancias]
    except _LimiteAgregado:
        informe = ca.informe_de_lectura_rechazada("entradas", "limite_agregado_superado")
    else:
        informe = ca.verificar(expedientes=expedientes, politica_del_verificador=politica,
                               politica_de_auditoria=politica_auditoria, capturas=capturas,
                               politica_de_constancias=politica_constancias, constancias=constancias,
                               referencias=referencias)
    _salida(informe, args.formato)
    if destino is not None:
        with open(destino, "xb") as flujo:
            flujo.write(ca.informe_json(informe))
    return ca.codigo_de_salida(informe)


if __name__ == "__main__":
    sys.exit(main())
