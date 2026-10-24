"""
Claves de la API publica (Fase 8). No conecta con la base ni escribe archivos.

  python -m scripts.api_publica_claves generar --id frontend
      Genera una clave nueva. Imprime la clave UNA vez (entregala al consumidor
      por un canal privado; no se guarda en ningun sitio) y la entrada
      `frontend:sha256:<huella>` para `API_PUBLICA_CLAVES`.
  python -m scripts.api_publica_claves huella --id frontend < clave.txt
      Calcula la entrada de una clave existente leida por la entrada estandar
      (nunca como argumento: no queda en el historial de la consola).
  python -m scripts.api_publica_claves comprobar
      Valida `API_PUBLICA_CLAVES` del entorno o `.env`: informa cuantas claves
      y sus identificadores, sin mostrar huellas. Codigo 3 si la API quedaria
      cerrada (configuracion ausente o no valida).

Sustituir: genera una clave con otro identificador, anadela a la lista,
reinicia la API, cambia el consumidor y quita la entrada anterior. Revocar:
quita su entrada y reinicia (la configuracion se lee al arrancar).

Codigos de salida: 0 correcto, 2 argumentos no validos, 3 configuracion no valida.
"""
from __future__ import annotations

import argparse
import re
import sys

from app.api.publica.configuracion import leer_claves
from app.api.publica.seguridad import formato_admitido, generar_clave, huella

EXIT_OK, EXIT_ARGUMENTOS, EXIT_CONFIGURACION = 0, 2, 3
_IDENTIFICADOR = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")


def _identificador(valor: str) -> str:
    if not _IDENTIFICADOR.fullmatch(valor):
        raise argparse.ArgumentTypeError("identificador: minusculas, digitos, '_' o '-' "
                                         "(1-32, empieza por letra o digito)")
    return valor


def main(argv: list[str] | None = None, *, entrada=None, salida=None, errores=None) -> int:
    entrada, salida, errores = entrada or sys.stdin, salida or sys.stdout, errores or sys.stderr
    parser = argparse.ArgumentParser(prog="python -m scripts.api_publica_claves", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="orden", required=True)
    for nombre in ("generar", "huella"):
        sub.add_parser(nombre).add_argument("--id", required=True, type=_identificador)
    sub.add_parser("comprobar")
    try:
        args = parser.parse_args(argv)
    except SystemExit as salida_argparse:
        return EXIT_OK if salida_argparse.code == 0 else EXIT_ARGUMENTOS
    if args.orden == "generar":
        clave = generar_clave()
        salida.write(f"clave (entregala una sola vez; no se guarda): {clave}\n")
        salida.write(f"entrada para API_PUBLICA_CLAVES: {args.id}:sha256:{huella(clave)}\n")
        return EXIT_OK
    if args.orden == "huella":
        clave = entrada.readline().strip()
        if not formato_admitido(clave):
            errores.write("la clave leida no tiene el formato admitido (32-256 caracteres ASCII visibles)\n")
            return EXIT_ARGUMENTOS
        salida.write(f"entrada para API_PUBLICA_CLAVES: {args.id}:sha256:{huella(clave)}\n")
        return EXIT_OK
    from app.core.config import Settings

    claves = leer_claves(Settings().api_publica_claves)
    if not claves:
        errores.write("API_PUBLICA_CLAVES falta o no es valida: la API publica rechazara todas las consultas (503)\n")
        return EXIT_CONFIGURACION
    salida.write(f"{len(claves)} clave(s) configurada(s): {', '.join(c.identificador for c in claves)}\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
