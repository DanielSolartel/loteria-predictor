"""Cuentas de la consola local (Fase 10, E10.1). Solo en el equipo, desde `backend/`.

    python -m scripts.consola_cuentas crear --usuario daniel --rol administrador
    python -m scripts.consola_cuentas cambiar-contrasena --usuario daniel
    python -m scripts.consola_cuentas cambiar-rol --usuario ana --rol operador
    python -m scripts.consola_cuentas desactivar --usuario ana        (y `activar`)
    python -m scripts.consola_cuentas revocar-sesiones [--usuario ana]
    python -m scripts.consola_cuentas listar | auditoria [--limite 50] | comprobar

- La contraseña se pide sin eco (dos veces) o se lee de la entrada estándar con `--contrasena-stdin`;
  nunca como argumento, en la URL ni en los registros.
- `crear` crea el almacén si no existe (directorio y archivo solo para el propietario), después de comprobar
  que Git ignora su ruta. Nunca reemplaza un almacén existente.
- Cambiar contraseña, rol o desactivar invalida las sesiones de esa cuenta. No se puede retirar el último
  administrador activo.
- Recuperar el acceso es crear otra cuenta administrativa o cambiar la contraseña desde aquí: la web no tiene
  alta ni recuperación.

`--directorio` permite un almacén de ensayo (por ejemplo, en una carpeta temporal); por defecto se usa
`CONSOLA_SEGURIDAD_DIRECTORIO` (`privado/consola`). Códigos: 0 correcto, 1 rechazado, 2 uso no válido.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

from app.core.config import get_settings
from app.seguridad_consola.almacen import (
    ROLES, AlmacenSeguridad, ConsolaNoDisponible, OperacionRechazada, ruta_predeterminada,
)
from app.seguridad_consola.credenciales import ContrasenaNoValida, validar_contrasena

EXIT_OK, EXIT_RECHAZADO = 0, 1


def _raiz_git(ruta: Path) -> Path | None:
    for carpeta in (ruta, *ruta.parents):
        if (carpeta / ".git").exists():
            return carpeta
    return None


def comprobar_exclusion_git(archivo: Path) -> None:
    """Rechaza crear el almacén dentro de un repositorio Git si Git no ignora su ruta."""
    absoluto = archivo.resolve()
    existente = next((c for c in absoluto.parents if c.exists()), absoluto.anchor)
    raiz = _raiz_git(Path(existente))
    if raiz is None or not absoluto.is_relative_to(raiz):
        return
    try:
        r = subprocess.run(["git", "-C", str(raiz), "check-ignore", "-q", "--no-index", str(absoluto.relative_to(raiz))],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise OperacionRechazada("No se pudo comprobar con Git que el almacén queda excluido; no se crea.") from error
    if r.returncode == 1:
        raise OperacionRechazada("Git no ignora la ruta del almacén; añádala a .gitignore antes de crearlo.")
    if r.returncode != 0:
        raise OperacionRechazada("No se pudo comprobar con Git que el almacén queda excluido; no se crea.")


def _leer_contrasena(desde_stdin: bool) -> str:
    if desde_stdin:
        linea = sys.stdin.readline()
        contrasena = linea[:-1] if linea.endswith("\n") else linea
        contrasena = contrasena[:-1] if contrasena.endswith("\r") else contrasena
    else:
        contrasena = getpass.getpass("Contraseña nueva: ")
        if getpass.getpass("Repita la contraseña: ") != contrasena:
            raise OperacionRechazada("Las contraseñas no coinciden.")
    validar_contrasena(contrasena)
    return contrasena


def _archivo(argumentos) -> Path:
    return ruta_predeterminada(argumentos.directorio or get_settings().consola_seguridad_directorio)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cuentas de la consola local (solo en este equipo)")
    p.add_argument("--directorio", help="Directorio del almacén (por defecto, CONSOLA_SEGURIDAD_DIRECTORIO)")
    sub = p.add_subparsers(dest="orden", required=True)
    for nombre in ("crear", "cambiar-contrasena"):
        s = sub.add_parser(nombre)
        s.add_argument("--usuario", required=True)
        s.add_argument("--contrasena-stdin", action="store_true", help="Leer la contraseña de la entrada estándar")
        if nombre == "crear":
            s.add_argument("--rol", required=True, choices=ROLES)
    s = sub.add_parser("cambiar-rol")
    s.add_argument("--usuario", required=True)
    s.add_argument("--rol", required=True, choices=ROLES)
    for nombre in ("desactivar", "activar"):
        sub.add_parser(nombre).add_argument("--usuario", required=True)
    sub.add_parser("revocar-sesiones").add_argument("--usuario")
    sub.add_parser("listar")
    sub.add_parser("auditoria").add_argument("--limite", type=int, default=50)
    sub.add_parser("comprobar")
    a = p.parse_args(argv)
    archivo = _archivo(a)
    actor = "cli:" + (os.environ.get("USERNAME") or os.environ.get("USER") or "local")
    try:
        if a.orden == "crear":
            contrasena = _leer_contrasena(a.contrasena_stdin)
            if archivo.exists():
                almacen = AlmacenSeguridad(archivo)
            else:
                comprobar_exclusion_git(archivo)
                almacen = AlmacenSeguridad.crear(archivo)
                print("Almacén de seguridad creado (solo para el propietario).")
            almacen.crear_cuenta(a.usuario, contrasena, a.rol, actor=actor)
            print(f"Cuenta creada: {a.usuario} ({a.rol}).")
        elif a.orden == "comprobar":
            almacen = AlmacenSeguridad(archivo)
            try:
                almacen.comprobar()
                estado = {"estado": "disponible"}
            except ConsolaNoDisponible as error:
                estado = {"estado": "no_disponible", "motivo": error.motivo}
            print(json.dumps(estado, ensure_ascii=False))
            return EXIT_OK if estado["estado"] == "disponible" else EXIT_RECHAZADO
        else:
            almacen = AlmacenSeguridad(archivo)
            if a.orden == "cambiar-contrasena":
                almacen.cambiar_contrasena(a.usuario, _leer_contrasena(a.contrasena_stdin), actor=actor)
                print(f"Contraseña cambiada; sesiones de {a.usuario} revocadas.")
            elif a.orden == "cambiar-rol":
                almacen.cambiar_rol(a.usuario, a.rol, actor=actor)
                print(f"Rol de {a.usuario}: {a.rol}; sus sesiones quedan revocadas.")
            elif a.orden == "desactivar":
                almacen.desactivar(a.usuario, actor=actor)
                print(f"Cuenta {a.usuario} desactivada; sus sesiones quedan revocadas.")
            elif a.orden == "activar":
                almacen.activar(a.usuario, actor=actor)
                print(f"Cuenta {a.usuario} activada.")
            elif a.orden == "revocar-sesiones":
                print(f"Sesiones revocadas: {almacen.revocar_sesiones(a.usuario, actor=actor)}.")
            elif a.orden == "listar":
                print(json.dumps(almacen.cuentas(), ensure_ascii=False, indent=2))
            elif a.orden == "auditoria":
                print(json.dumps(almacen.auditoria(a.limite), ensure_ascii=False, indent=2))
    except (OperacionRechazada, ContrasenaNoValida) as error:
        print(f"Rechazado: {error}", file=sys.stderr)
        return EXIT_RECHAZADO
    except ConsolaNoDisponible as error:
        print(f"Almacén no disponible: {error.motivo}", file=sys.stderr)
        return EXIT_RECHAZADO
    except (KeyboardInterrupt, EOFError):
        print("Cancelado.", file=sys.stderr)
        return EXIT_RECHAZADO
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
