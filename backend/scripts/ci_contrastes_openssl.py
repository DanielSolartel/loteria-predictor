#!/usr/bin/env python3
"""AE-76, validada localmente como trabajo preparatorio: estado real de los
contrastes con `openssl ts -verify`.

Lee el informe JUnit de pytest y cuenta los casos parametrizados de
`test_g1_contraste_con_openssl_ts_verify` (AE-75). Nunca presenta una
omision como exito:

  --modo exigir            todos los casos esperados deben haber pasado.
  --modo permitir_omision  todos pasaron, o todos se omitieron (sin
                           OpenSSL en PATH); en ese caso informa
                           OMITIDOS y no los cuenta como superados.

Cualquier fallo, error, mezcla de pasados y omitidos o numero distinto de
casos termina con codigo 1. Tambien falla si hay pruebas omitidas fuera de
esos contrastes: una omision ajena (por ejemplo, una dependencia de pruebas
ausente) no puede pasar por exito. Solo biblioteca estandar; sin red.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

PRUEBA = "test_g1_contraste_con_openssl_ts_verify"
MODULO = "test_sello_temporal_r0"
ESPERADOS = 7


def contar(ruta_junit: str) -> dict:
    """Cuenta pasados, omitidos, fallidos y con error de los contrastes."""
    cuenta = {"pasados": 0, "omitidos": 0, "fallidos": 0, "errores": 0, "otras_omitidas": 0}
    for caso in ET.parse(ruta_junit).getroot().iter("testcase"):
        if not caso.get("name", "").startswith(PRUEBA + "[") or MODULO not in caso.get("classname", ""):
            cuenta["otras_omitidas"] += caso.find("skipped") is not None
            continue
        if caso.find("failure") is not None:
            cuenta["fallidos"] += 1
        elif caso.find("error") is not None:
            cuenta["errores"] += 1
        elif caso.find("skipped") is not None:
            cuenta["omitidos"] += 1
        else:
            cuenta["pasados"] += 1
    return cuenta


def dictamen(cuenta: dict, modo: str, esperados: int = ESPERADOS) -> tuple[int, str]:
    """(codigo de salida, linea de estado) sin tratar omisiones como exito."""
    total = sum(v for k, v in cuenta.items() if k != "otras_omitidas")
    detalle = (f"{cuenta['pasados']} pasados, {cuenta['omitidos']} omitidos, {cuenta['fallidos']} fallidos, "
               f"{cuenta['errores']} errores de {esperados} esperados")
    if cuenta.get("otras_omitidas"):
        return 1, f"contrastes_openssl: ERROR, {cuenta['otras_omitidas']} pruebas ajenas omitidas ({detalle})"
    if total != esperados:
        return 1, f"contrastes_openssl: ERROR, se encontraron {total} casos ({detalle})"
    if cuenta["fallidos"] or cuenta["errores"]:
        return 1, f"contrastes_openssl: FALLAN ({detalle})"
    if cuenta["pasados"] == esperados:
        return 0, f"contrastes_openssl: SUPERADOS {esperados}/{esperados} ({detalle})"
    if modo == "permitir_omision" and cuenta["omitidos"] == esperados:
        return 0, (f"contrastes_openssl: OMITIDOS {esperados}/{esperados} sin OpenSSL en PATH; no cuentan como "
                   f"superados ({detalle})")
    return 1, f"contrastes_openssl: INCOMPLETOS ({detalle})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("junit")
    parser.add_argument("--modo", choices=("exigir", "permitir_omision"), required=True)
    parser.add_argument("--esperados", type=int, default=ESPERADOS)
    parser.add_argument("--resumen", help="archivo al que anadir la linea de estado (p. ej. GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)
    codigo, linea = dictamen(contar(args.junit), args.modo, args.esperados)
    print(linea)
    if args.resumen:
        with open(args.resumen, "a", encoding="utf-8") as resumen:
            resumen.write(linea + "\n")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
