"""PR #109 (segundo CI): el paso de gitleaks del job `auditoria` ejecuta SIEMPRE los dos escaneos (historial y
arbol), deja un informe JSON redactado de cada uno FUERA del arbol escaneado, monta el repositorio de solo lectura,
deja el escaner sin red y termina en fallo ante cualquier hallazgo o error. Se publica siempre el informe.

Se EJECUTA el guion real del paso (extraido del YAML) con `bash -eo pipefail`, como en GitHub Actions, sustituyendo
solo `docker` por un registrador que simula el resultado de cada modo; no se ejecuta gitleaks."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[3]
FLUJO = RAIZ / ".github" / "workflows" / "seguridad-consulta-privada.yml"
BASH = shutil.which("bash")


def _pasos() -> list[dict]:
    return yaml.safe_load(FLUJO.read_text(encoding="utf-8"))["jobs"]["auditoria"]["steps"]


def _paso(prefijo: str) -> dict:
    return next(p for p in _pasos() if str(p.get("name", "")).startswith(prefijo))


def test_informes_redactados_publicados_siempre_desde_fuera_del_arbol():
    subida = _paso("Informes redactados de gitleaks")
    assert "always()" in str(subida.get("if", "")) and subida["uses"].startswith("actions/upload-artifact@")
    rutas = [l.strip() for l in subida["with"]["path"].splitlines() if l.strip()]
    assert len(rutas) == 2 and all(r.startswith("${{ runner.temp }}/") and r.endswith(".json") for r in rutas)
    for p in _pasos():
        assert "continue-on-error" not in p, p.get("name")


ESCENARIOS = {  # modo -> codigo simulado del escaner (1 = hallazgos, 2 = error), y codigo esperado del paso
    "limpio": ({"git": 0, "dir": 0}, 0),
    "historial_con_hallazgo": ({"git": 1, "dir": 0}, 1),
    "arbol_con_hallazgo": ({"git": 0, "dir": 1}, 1),
    "error_del_escaner": ({"git": 2, "dir": 0}, 1),
}


@pytest.mark.skipif(BASH is None, reason="bash no disponible")
@pytest.mark.parametrize("escenario", sorted(ESCENARIOS))
def test_paso_de_gitleaks_ejecuta_ambos_y_acumula(tmp_path, escenario):
    codigos, esperado = ESCENARIOS[escenario]
    repo, temp, bin_dir = tmp_path / "repo", tmp_path / "runner-temp", tmp_path / "bin"
    for d in (repo, temp, bin_dir):
        d.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "a = sys.argv[1:]\n"
        "open(os.environ['LLAMADAS'], 'a').write(json.dumps(a) + '\\n')\n"
        "modo = next(m for m in ('git', 'dir') if m in a)\n"
        "destino = a[a.index('--report-path') + 1]\n"
        "montajes = {a[i + 1].split(':')[1]: a[i + 1].split(':')[0] for i, x in enumerate(a) if x == '-v'}\n"
        "real = destino.replace('/informes', montajes['/informes'])\n"
        "json.dump([], open(real, 'w'))\n"
        "sys.exit(json.loads(os.environ['CODIGOS'])[modo])\n", encoding="utf-8")
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    guion = tmp_path / "paso.sh"
    guion.write_text(_paso("Secretos en el historial y en el arbol")["run"], encoding="utf-8")
    entorno = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "GITLEAKS": "gitleaks-sustituto",
               "RUNNER_TEMP": str(temp), "LLAMADAS": str(tmp_path / "llamadas.jsonl"), "CODIGOS": json.dumps(codigos)}
    r = subprocess.run([BASH, "--noprofile", "--norc", "-eo", "pipefail", str(guion)], cwd=repo, env=entorno,
                       capture_output=True, text=True, timeout=60)
    assert (r.returncode == 0) == (esperado == 0), (escenario, r.returncode, r.stdout, r.stderr)
    llamadas = [json.loads(l) for l in (tmp_path / "llamadas.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [next(m for m in ("git", "dir") if m in a) for a in llamadas] == ["git", "dir"]  # ambos, siempre
    for a in llamadas:
        assert a[:2] == ["run", "--rm"] and "--network" in a and a[a.index("--network") + 1] == "none"
        montajes = [a[i + 1] for i, x in enumerate(a) if x == "-v"]
        assert any(m.endswith(":/repo:ro") for m in montajes)  # repositorio de solo lectura
        assert "--redact" in a and a[a.index("--exit-code") + 1] == "1"
    for modo in ("git", "dir"):
        informe = temp / "gitleaks" / f"gitleaks-{modo}.json"
        assert informe.exists() and not str(informe).startswith(str(repo))  # fuera del arbol escaneado
    assert not any(repo.iterdir())  # nada escrito dentro del arbol
