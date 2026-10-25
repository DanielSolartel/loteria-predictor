"""Fase 9.1, pasarela: proceso separado que solo es cliente HTTP de `/api/v1`.
Sin casos de uso, dominio, repositorios, base de datos ni la aplicacion local;
la aplicacion local y la API publica no la montan."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PAQUETE = Path(__file__).resolve().parents[3] / "app" / "pasarela"
# `socket` (v2, F9-LIM-01): el cliente aplica el plazo total en cada operacion de su propio socket.
PERMITIDOS = {"__future__", "anyio", "dataclasses", "http", "ipaddress", "json", "logging", "pathlib", "pydantic",
              "pydantic_settings", "re", "socket", "starlette", "time", "urllib", "uuid", "app"}
PROPIOS = {"app.pasarela", "app.pasarela.rutas", "app.pasarela.cliente", "app.pasarela.configuracion"}


def _importados(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    nombres = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            nombres |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            nombres.add(n.module or "")
    return nombres


def test_solo_importa_biblioteca_estandar_starlette_anyio_pydantic_y_si_misma():
    archivos = sorted(PAQUETE.glob("*.py"))
    assert {a.name for a in archivos} == {"__init__.py", "aplicacion.py", "cliente.py", "configuracion.py", "rutas.py"}
    for archivo in archivos:
        for modulo in _importados(archivo):
            assert modulo.split(".")[0] in PERMITIDOS, (archivo.name, modulo)
            if modulo.startswith("app"):
                assert modulo in PROPIOS, (archivo.name, modulo)


def test_importarla_no_carga_casos_de_uso_ni_base_de_datos():
    import subprocess

    codigo = ("import sys; import app.pasarela.aplicacion; "
              "prohibidos = [m for m in sys.modules if m.startswith(('app.application', 'app.domain', "
              "'app.infrastructure', 'app.api', 'app.core', 'app.main', 'sqlalchemy', 'psycopg'))]; "
              "print(prohibidos); sys.exit(1 if prohibidos else 0)")
    r = subprocess.run([sys.executable, "-B", "-c", codigo], cwd=PAQUETE.parents[1], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stdout[-500:]


def test_ni_la_aplicacion_local_ni_la_api_publica_la_montan():
    raiz = PAQUETE.parent
    for archivo in [raiz / "main.py", *sorted((raiz / "api").rglob("*.py"))]:
        assert not any(m.startswith("app.pasarela") for m in _importados(archivo)), archivo
