"""Pruebas estructurales (AST) de AE-43, validada: pureza de los
tres modulos nuevos, ausencia de ciclos al importar `tipos.py`, y
confirmacion de que ningun router, caso de uso ni script conecta la
inferencia o el resolvedor con datos reales."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_BACKEND = Path(__file__).resolve().parents[3]
DIRECTORIO_ML = RAIZ_BACKEND / "app" / "application" / "ml"
MODULOS_NUEVOS = ("ventanas_temporales", "inferencia", "prediccion_bloqueada")
PROHIBIDOS = {
    "sklearn", "numpy", "scipy", "pandas", "sqlalchemy", "fastapi", "jinja2",
    "random", "time", "psycopg", "requests",
}
PREFIJOS_APP_PERMITIDOS = ("app.application.ml", "app.application.estadisticas.tipos")


def _importaciones(ruta: Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.append(nodo.module or "")
    return modulos


@pytest.mark.parametrize("modulo", MODULOS_NUEVOS)
def test_modulos_nuevos_son_puros(modulo):
    for importado in _importaciones(DIRECTORIO_ML / f"{modulo}.py"):
        raiz = importado.split(".")[0]
        assert raiz not in PROHIBIDOS, f"{modulo} importa {importado}"
        if raiz == "app":
            assert importado.startswith(PREFIJOS_APP_PERMITIDOS), f"{modulo} importa {importado}"


def test_ventanas_temporales_solo_usa_la_biblioteca_estandar():
    for importado in _importaciones(DIRECTORIO_ML / "ventanas_temporales.py"):
        assert importado.split(".")[0] in {"__future__", "enum"}, importado


@pytest.mark.parametrize("modulo", MODULOS_NUEVOS)
def test_modulos_nuevos_no_consultan_el_reloj(modulo):
    arbol = ast.parse((DIRECTORIO_ML / f"{modulo}.py").read_text(encoding="utf-8"))
    atributos = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    assert not atributos & {"now", "utcnow", "today", "time"}


def test_importar_tipos_en_proceso_limpio_no_provoca_ciclos():
    for modulo in ("app.application.ml.tipos", "app.application.ml.ventanas_temporales",
                   "app.application.ml.inferencia", "app.application.ml.prediccion_bloqueada"):
        resultado = subprocess.run(
            [sys.executable, "-c", f"import {modulo}"], cwd=RAIZ_BACKEND, capture_output=True, text=True,
        )
        assert resultado.returncode == 0, resultado.stderr


def test_nada_fuera_de_ml_conecta_los_modulos_nuevos():
    directorios = [RAIZ_BACKEND / "app", RAIZ_BACKEND / "scripts"]
    nombres = {f"app.application.ml.{m}" for m in MODULOS_NUEVOS}
    for directorio in directorios:
        for ruta in directorio.rglob("*.py"):
            if ruta.parent == DIRECTORIO_ML:
                continue
            for importado in _importaciones(ruta):
                assert importado not in nombres, f"{ruta} importa {importado}"


def test_solo_modelo_py_importa_sklearn_en_application_ml():
    importadores = {
        ruta.name for ruta in DIRECTORIO_ML.glob("*.py")
        if any(i.split(".")[0] == "sklearn" for i in _importaciones(ruta))
    }
    assert importadores == {"modelo.py"}
