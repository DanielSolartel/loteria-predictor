"""Punto de entrada del perfil PRIVADO de la API publica (Fase 10, E10.2).

    `uvicorn app.api.publica.privada:app --host <IP interna> --port 8010 --workers 1 --no-access-log --no-proxy-headers`

Reglas y secretos en `perfil_privado.py`. Si el perfil no es valido, el proceso
termina con codigo 3 y un motivo sin secretos, sin servir ninguna consulta.
"""
from __future__ import annotations

import sys

from app.api.publica.perfil_privado import PerfilPrivadoNoValido, crear_app_privada

try:
    app = crear_app_privada()
except PerfilPrivadoNoValido as fallo:  # sin traza: el motivo ya es completo y no contiene secretos
    sys.stderr.write(f"api_publica privada: {fallo}\n")
    raise SystemExit(3) from None
