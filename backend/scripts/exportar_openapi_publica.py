"""Exporta el OpenAPI de la API publica `/api/v1` (Fase 8) para el frontend (Fase 9.1).

    python -m scripts.exportar_openapi_publica ../frontend/src/api/openapi.json
    python -m scripts.exportar_openapi_publica ../frontend/src/api/openapi.json --comprobar

Construye la aplicacion publica con la configuracion CERRADA (sin claves): no
lee ni consulta ninguna base de datos ni configuracion operativa. Escribe JSON
con sangria de 2 espacios y salto de linea final. `--comprobar` no escribe:
sale con 1 si el archivo difiere del OpenAPI actual (la version de FastAPI
instalada puede cambiar detalles; la prueba de deriva compara solo la parte
contractual que usa el frontend).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_OK, EXIT_DISTINTO = 0, 1


def openapi_publico() -> dict:
    from app.api.publica.aplicacion import crear_app
    from app.api.publica.configuracion import ConfiguracionPublica

    return crear_app(ConfiguracionPublica(claves=())).openapi()


def texto(documento: dict) -> str:
    return json.dumps(documento, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("salida", type=Path)
    p.add_argument("--comprobar", action="store_true")
    args = p.parse_args(argv)
    actual = texto(openapi_publico())
    if args.comprobar:
        igual = args.salida.exists() and args.salida.read_text(encoding="utf-8") == actual
        print("openapi: igual" if igual else "openapi: DISTINTO")
        return EXIT_OK if igual else EXIT_DISTINTO
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(actual, encoding="utf-8")
    print(f"openapi escrito: {len(actual.encode())} bytes")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
