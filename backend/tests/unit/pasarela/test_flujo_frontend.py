"""Fase 9.1: el workflow del frontend es independiente del de Python, minimo y reproducible."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FLUJO = REPO / ".github" / "workflows" / "validacion-frontend.yml"
PYTHON = REPO / ".github" / "workflows" / "validacion-python-314.yml"
FRONTEND = REPO / "frontend"


def test_workflow_del_frontend_minimo_sin_secretos_y_completo():
    texto = FLUJO.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in texto
    for prohibido in ("secrets.", "deploy", "curl ", "wget ", "|| true", "continue-on-error", "npm install",
                      "pull_request_target", "write-all"):
        assert prohibido not in texto, prohibido
    assert texto.count("npm ci --no-audit --no-fund --ignore-scripts") == 2
    for paso in ("npm run tipos:comprobar", "npm run typecheck", "npx vitest run", "npm run build", "npm run canario",
                 "npx playwright install --with-deps chromium", "tests/unit/pasarela"):
        assert paso in texto, paso
    for escenario in ("normal", "cuota", "api_caida", "sin_clave", "clave_incorrecta", "vite", "cuota_fiabilidad"):
        assert f"python -m tests.recorrido_fase9 --escenario {escenario}" in texto, escenario
    assert 'node: ["22", "24"]' in texto and "cache-dependency-path: frontend/package-lock.json" in texto


def test_el_workflow_de_python_no_cambia_de_alcance():
    texto = PYTHON.read_text(encoding="utf-8")
    assert "frontend" not in texto and "npm" not in texto


def test_versiones_exactas_y_lock_presente():
    paquete = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8"))
    assert paquete["engines"]["node"] == ">=22.12.0"
    for grupo in ("dependencies", "devDependencies"):
        for nombre, version in paquete[grupo].items():
            assert version[0].isdigit(), f"{nombre}: version no exacta {version}"
            assert lock["packages"][f"node_modules/{nombre}"]["version"] == version, nombre
    assert lock["lockfileVersion"] == 3
