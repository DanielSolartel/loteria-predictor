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

E10.1 (E101-CI-01): unica excepcion, las omisiones de plataforma de la consola
local enumeradas en OMISIONES_PLATAFORMA. Se admiten solo con modulo y prueba
exactos, motivo exacto y la plataforma efectiva del proceso (`sys.platform`),
nunca por el modo, el nombre del XML ni por palabras del motivo. Se informan
aparte (recuento e identidad), no cuentan como superadas ni se suman a los
contrastes. Una identidad repetida, o una omision que ademas trae fallo o
error, es un ERROR.
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

PRUEBA = "test_g1_contraste_con_openssl_ts_verify"
MODULO = "test_sello_temporal_r0"
ESPERADOS = 7

_ACL = "tests.unit.seguridad_consola.test_permisos_windows_nativo"
_ALMACEN = "tests.unit.seguridad_consola.test_almacen_y_credenciales"
_REGRESIONES = "tests.unit.seguridad_consola.test_regresiones_v2"
#: plataforma efectiva -> {(modulo, prueba): motivo exacto}. Fuente: los `skipif`/`pytest.skip` de esas pruebas.
OMISIONES_PLATAFORMA = {
    "linux": {
        (_ACL, "test_nativo_crear_deja_propietario_y_dacl_solo_del_usuario"): "ensayo nativo de ACL: requiere Windows",
        (_ACL, "test_nativo_ace_amplia_posterior_cierra_y_al_retirarla_vuelve"): "ensayo nativo de ACL: requiere Windows",
        (_ACL, "test_nativo_directorio_preexistente_no_se_modifica"): "ensayo nativo de ACL: requiere Windows",
    },
    "win32": {
        (_ALMACEN, "test_permisos_del_propietario_y_permisos_abiertos_cierran"):
            "permisos POSIX; en Windows: test_permisos_windows_nativo.py (v2)",
        (_REGRESIONES, "test_posix_directorio_preexistente_amplio_se_rechaza_sin_cambiarlo"): "permisos POSIX",
        (_REGRESIONES, "test_posix_cambio_posterior_de_permisos_y_enlace_cierran"): "permisos POSIX",
        # Condicional: solo si la carpeta temporal ya es exclusiva del usuario (caso no aplicable).
        (_ACL, "test_nativo_directorio_preexistente_no_se_modifica"):
            "la carpeta temporal ya es exclusiva del usuario; el caso no es aplicable aquí",
    },
}


def contar(ruta_junit: str, plataforma: str | None = None) -> dict:
    """Cuenta pasados, omitidos, fallidos y con error de los contrastes, y clasifica las demas omisiones."""
    plataforma = sys.platform if plataforma is None else plataforma
    admitidas = OMISIONES_PLATAFORMA.get(plataforma, {})
    cuenta = {"pasados": 0, "omitidos": 0, "fallidos": 0, "errores": 0, "otras_omitidas": 0,
              "omisiones_plataforma": [], "omisiones_repetidas": 0, "omisiones_ambiguas": 0, "plataforma": plataforma}
    vistas = set()
    for caso in ET.parse(ruta_junit).getroot().iter("testcase"):
        if not caso.get("name", "").startswith(PRUEBA + "[") or MODULO not in caso.get("classname", ""):
            omision = caso.find("skipped")
            if omision is None:
                continue
            identidad = (caso.get("classname", ""), caso.get("name", ""))
            motivo = omision.get("message", "")
            if caso.find("failure") is not None or caso.find("error") is not None:
                cuenta["omisiones_ambiguas"] += 1
            elif admitidas.get(identidad) != motivo:
                cuenta["otras_omitidas"] += 1
            elif identidad in vistas:
                cuenta["omisiones_repetidas"] += 1
            else:
                vistas.add(identidad)
                cuenta["omisiones_plataforma"].append({"modulo": identidad[0], "prueba": identidad[1], "motivo": motivo})
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
    total = sum(cuenta[k] for k in ("pasados", "omitidos", "fallidos", "errores"))
    plataforma = len(cuenta.get("omisiones_plataforma", []))
    detalle = (f"{cuenta['pasados']} pasados, {cuenta['omitidos']} omitidos, {cuenta['fallidos']} fallidos, "
               f"{cuenta['errores']} errores de {esperados} esperados; {plataforma} omisiones de plataforma "
               f"({cuenta.get('plataforma', sys.platform)}) aparte, no cuentan como superadas")
    if cuenta.get("otras_omitidas"):
        return 1, f"contrastes_openssl: ERROR, {cuenta['otras_omitidas']} pruebas ajenas omitidas ({detalle})"
    if cuenta.get("omisiones_repetidas"):
        return 1, f"contrastes_openssl: ERROR, {cuenta['omisiones_repetidas']} omisiones de plataforma repetidas ({detalle})"
    if cuenta.get("omisiones_ambiguas"):
        return 1, (f"contrastes_openssl: ERROR, {cuenta['omisiones_ambiguas']} pruebas omitidas con fallo o error "
                   f"({detalle})")
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


def lineas_de_plataforma(cuenta: dict) -> list[str]:
    """Detalle de cada omision de plataforma admitida (identidad y motivo exactos)."""
    return [f"omision de plataforma ({cuenta.get('plataforma', sys.platform)}): {o['modulo']}::{o['prueba']} "
            f"- {o['motivo']}" for o in cuenta.get("omisiones_plataforma", [])]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("junit")
    parser.add_argument("--modo", choices=("exigir", "permitir_omision"), required=True)
    parser.add_argument("--esperados", type=int, default=ESPERADOS)
    parser.add_argument("--resumen", help="archivo al que anadir la linea de estado (p. ej. GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)
    cuenta = contar(args.junit)
    codigo, linea = dictamen(cuenta, args.modo, args.esperados)
    texto = "\n".join([linea, *lineas_de_plataforma(cuenta)])
    print(texto)
    if args.resumen:
        with open(args.resumen, "a", encoding="utf-8") as resumen:
            resumen.write(texto + "\n")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
