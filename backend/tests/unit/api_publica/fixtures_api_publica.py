"""FIXTURES SINTETICAS de la Fase 8 (API publica), solo para pruebas.

- Claves generadas en cada prueba (nunca fijas en el codigo).
- Juegos, sorteos, estadisticas y simulaciones: la base SQLite aislada de la
  Fase 7 (cuatro juegos e historicos sinteticos).
- Predicciones guardadas: el centro de la Fase 4 sobre almacenes temporales.
- Proceso Uvicorn real: el arranque documentado en la guia, tal cual, con
  SQLite y almacenes temporales.
Sin PostgreSQL ni Internet; ningun dato es real."""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.publica import aplicacion
from app.api.publica import dependencias as d
from app.api.publica.configuracion import ConfiguracionPublica, leer_claves
from app.api.publica.seguridad import generar_clave, huella
from tests.unit.simulaciones import fixtures_fase7 as f7

LOCAL = ("127.0.0.1", 50000)
BACKEND = Path(__file__).resolve().parents[3]
GUIA = BACKEND / "docs" / "fase8_api_publica.md"
OBJETIVO = "app.api.publica.aplicacion:app"
COMANDO = re.compile(r"(?:python -m )?uvicorn app\.api\.publica\.aplicacion:app[^`\n]*")
DIRECTORIOS = ("PRONOSTICOS_EXPERIMENTALES", "OPERACION", "LABORATORIO_MODELOS", "CARTERAS_MODELOS",
               "RESULTADOS_MODELOS", "PREDICCIONES_MODELOS", "AUTOMATIZACION", "SIMULACIONES")


def configuracion(*identificadores: str, **extra) -> tuple[ConfiguracionPublica, dict[str, str]]:
    claves = {i: generar_clave() for i in identificadores}
    texto = ",".join(f"{i}:sha256:{huella(c)}" for i, c in claves.items())
    return ConfiguracionPublica(claves=leer_claves(texto), **{"fichas_por_minuto_ip": 10_000, **extra}), claves


@dataclasses.dataclass
class Api:
    app: object
    claves: dict[str, str]
    entorno: f7.Entorno

    def cliente(self, *, client=LOCAL, raise_server_exceptions=True) -> TestClient:
        return TestClient(self.app, base_url="http://testserver", client=client,
                          raise_server_exceptions=raise_server_exceptions)

    def cabeceras(self, identificador: str = "pruebas") -> dict[str, str]:
        return {"X-API-Key": self.claves[identificador]}

    def get(self, url: str, identificador: str = "pruebas", **kw):
        return self.cliente().get(url, headers=self.cabeceras(identificador), **kw)


def sesiones_de(e: f7.Entorno):
    def sesion():
        s = e.sesiones()
        try:
            yield s
        finally:
            s.rollback()
            s.close()
    return sesion


def api(tmp_path: Path, *identificadores: str, entorno: f7.Entorno | None = None, centro=None,
        simulaciones=None, base: str = "disponible", **extra) -> Api:
    conf, claves = configuracion(*(identificadores or ("pruebas",)), **extra)
    e = entorno or f7.entorno(tmp_path / "datos")
    app = aplicacion.crear_app(conf)
    app.dependency_overrides = {d.sesion_de_lectura: sesiones_de(e), d.estado_de_la_base: lambda: base,
                                d.simulaciones: lambda: simulaciones or e.servicio()}
    if centro is not None:
        app.dependency_overrides[d.centro_de_predicciones] = lambda: centro
    return Api(app, claves, e)


def arbol(raiz: Path) -> dict[str, str]:
    if not raiz.exists():
        return {}
    return {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raiz.rglob("*")) if p.is_file() and p.suffix != ".sqlite"}


def arranque_documentado(objetivo: str = OBJETIVO) -> list[str]:
    """Argumentos de Uvicorn del paso «Arrancar» de la guia, tal cual. Solo
    cambian el puerto (0: lo elige el sistema) y, si se pide, la aplicacion."""
    linea = next(x for x in GUIA.read_text(encoding="utf-8").splitlines() if "Arrancar" in x and OBJETIVO in x)
    argumentos = shlex.split(COMANDO.search(linea).group(0))
    argumentos = argumentos[argumentos.index(OBJETIVO):]
    argumentos[0] = objetivo
    argumentos[argumentos.index("--port") + 1] = "0"
    return argumentos


def entorno_de_proceso(raiz: Path, **variables: str) -> dict[str, str]:
    """Entorno del proceso real: base SQLite y almacenes temporales; sin
    variables de Uvicorn ni de la API heredadas que cambien el arranque. Sin
    bufer de salida: en Windows `terminate()` no deja vaciarlo."""
    entorno = {k: v for k, v in os.environ.items()
               if not k.startswith(("UVICORN_", "API_PUBLICA_", "DIRECTORIO_")) and k != "FORWARDED_ALLOW_IPS"}
    entorno.update({"DATABASE_URL": "sqlite:///" + (raiz / "sin_uso.sqlite").as_posix(),
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
                    **{f"DIRECTORIO_{n}": str(raiz / "almacenes" / n.lower()) for n in DIRECTORIOS}, **variables})
    return entorno


@contextlib.contextmanager
def proceso_uvicorn(argumentos: list[str], entorno: dict[str, str], registro: Path, *, app_dir: Path | None = None):
    """`python -m uvicorn <argumentos>` desde `backend/`, con su salida en
    `registro`. Devuelve la URL base cuando escucha y siempre termina el proceso.
    Un fallo no muestra el registro (puede contener canarios)."""
    extra = ["--app-dir", str(app_dir)] if app_dir else []
    with open(registro, "wb") as salida:
        proceso = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", *argumentos, *extra], cwd=BACKEND,
                                   env=entorno, stdout=salida, stderr=subprocess.STDOUT)
    try:
        limite = time.monotonic() + 60
        while not (escucha := re.search(r"Uvicorn running on http://127\.0\.0\.1:(\d+)",
                                        registro.read_text(encoding="utf-8", errors="replace"))):
            if proceso.poll() is not None or time.monotonic() > limite:
                raise RuntimeError(f"Uvicorn no quedo escuchando (codigo {proceso.poll()})")
            time.sleep(0.05)
        yield f"http://127.0.0.1:{escucha.group(1)}"
    finally:
        if proceso.poll() is None:
            proceso.terminate()
        try:
            proceso.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.wait(timeout=15)


def filas(e: f7.Entorno) -> dict[str, list]:
    """Todas las filas de todas las tablas (para comprobar que una consulta no escribe)."""
    from sqlalchemy import text

    with e.engine.connect() as c:
        return {t.name: sorted(tuple(map(str, r)) for r in c.execute(text(f"SELECT * FROM {t.name}")))
                for t in f7.metadatos_sqlite().sorted_tables}
