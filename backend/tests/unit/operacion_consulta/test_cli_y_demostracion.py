from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from despliegue.operacion_consulta.modelo import canonico
from .conftest import RAIZ


def cli(control, *args, entorno=None):
    env = os.environ.copy()
    for clave in list(env):
        if clave.startswith(("DATABASE_URL", "API_PUBLICA_", "PASARELA_", "GENERACION_", "DIRECTORIO_", "E104_")):
            env.pop(clave)
    env.update(PYTHONPATH=str(RAIZ / "backend"), PYTHONDONTWRITEBYTECODE="1")
    env.update(entorno or {})
    r = subprocess.run([sys.executable, "-B", "-m", "despliegue.operacion_consulta", "--control", str(control),
                        *args], cwd=RAIZ, env=env, capture_output=True, timeout=10)
    return r


def test_cli_inicializa_renderiza_y_audita_sin_invocar_docker(tmp_path, plan):
    control = tmp_path / "control-cli"
    p = tmp_path / "plan.json"
    p.write_bytes(canonico(plan.objeto()))
    trampas = tmp_path / "bin"
    trampas.mkdir()
    marcador = tmp_path / "docker-invocado"
    trampa = trampas / "docker"
    trampa.write_text("#!/bin/sh\nprintf invocado > '" + str(marcador) + "'\nexit 99\n")
    trampa.chmod(0o700)
    env = {"PATH": str(trampas)}
    assert cli(control, "inicializar", entorno=env).returncode == 0
    r = cli(control, "renderizar", "--plan", str(p), entorno=env)
    assert r.returncode == 0 and json.loads(r.stdout)["resultado"] == "renderizado_sin_ejecutar"
    r = cli(control, "auditar", entorno=env)
    assert r.returncode == 3 and not json.loads(r.stdout)["produccion_autorizada"]
    assert not marcador.exists()
    assert cli(control, "estado", entorno=env).returncode == 0


def test_cli_rechaza_produccion_sin_mostrar_entrada_ni_invocar_runtime(tmp_path, plan):
    control = tmp_path / "control-cli"
    assert cli(control, "inicializar").returncode == 0
    v = plan.objeto()
    v["modo"] = "SECRETO-SINTETICO"
    p = tmp_path / "plan.json"
    p.write_bytes(canonico(v))
    r = cli(control, "activar", "--plan", str(p), "--confirmar-ensayo", entorno={"PATH": "/inexistente"})
    assert r.returncode == 2 and b"SECRETO" not in r.stdout + r.stderr
    assert json.loads(r.stdout)["codigo"] == r.returncode
    r = cli(control, "activar", "--plan", str(p))
    assert r.returncode == 2 and not list(control.glob("r-*"))


def test_cli_senales_y_calendario_sin_servicio(tmp_path):
    control = tmp_path / "control-cli"
    assert cli(control, "inicializar").returncode == 0
    assert cli(control, "registrar", "--tipo", "contacto_pc").returncode == 0
    assert cli(control, "registrar", "--tipo", "captura_rechazada").returncode == 0
    calendario = tmp_path / "calendario.json"
    calendario.write_bytes(canonico({"MILOTO": {"fecha_sorteo_esperado": "2026-11-05",
                                               "resultado_esperado_antes_de": "2026-11-06T01:00:00-05:00"}}))
    assert cli(control, "calendario", "--archivo", str(calendario)).returncode == 0
    r = cli(control, "observar")
    assert r.returncode == 0 and not json.loads(r.stdout)["servicio_verificado"]
    assert "captura_sin_verificar" in json.loads(r.stdout)["alertas"]
    r = cli(control, "recuperar", "--confirmar-ensayo")
    assert r.returncode == 0 and json.loads(r.stdout)["resultado"] == "sin_transaccion"


def test_demostracion_http_con_lector_abierto_y_reversion():
    from despliegue.operacion_consulta.demostracion import ejecutar
    r = ejecutar()
    assert r["codigo"] == 0 and r["aprobados"] == 8
    assert r["transporte"] == "HTTP_loopback_real" and r["docker_postgresql_nginx"] == "no_ejecutados"
