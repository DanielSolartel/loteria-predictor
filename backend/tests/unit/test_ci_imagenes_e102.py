"""PR #109 (CI109-03): el job `imagenes` de `seguridad-consulta-privada.yml` escanea y evalua SIEMPRE las dos
imagenes, acumula los fallos sin exito falso y publica los diagnosticos aunque el umbral falle.

Ademas de las propiedades estaticas del workflow, se EJECUTA el guion real del paso de grype (extraido del YAML)
con `bash -eo pipefail`, como en GitHub Actions, sustituyendo solo `docker` (no se ejecuta grype ni Docker) y con
el umbral real `ci_umbral_vulnerabilidades.py` y sus excepciones versionadas."""
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
    return yaml.safe_load(FLUJO.read_text(encoding="utf-8"))["jobs"]["imagenes"]["steps"]


def _paso(prefijo: str) -> dict:
    return next(p for p in _pasos() if str(p.get("name", "")).startswith(prefijo))


def test_publicacion_siempre_y_con_lista_explicita_de_archivos():
    subida = _paso("SBOM, informes de grype")
    assert "always()" in str(subida.get("if", "")) and subida["uses"].startswith("actions/upload-artifact@")
    rutas = [l.strip() for l in subida["with"]["path"].splitlines() if l.strip()]
    assert set(rutas) == {"imagenes.txt", "sbom/imagen-api.cdx.json", "sbom/imagen-pasarela.cdx.json",
                          "sbom/frontend-lock.cdx.json", "grype-api.json", "grype-pasarela.json"}
    assert not any(r.endswith("/") or "*" in r or r.endswith(".tar") for r in rutas)


def test_ningun_paso_del_job_tolera_errores():
    for p in _pasos():
        assert "continue-on-error" not in p, p.get("name")
        assert "|| true" not in str(p.get("run", "")), p.get("name")
    grype = _paso("Vulnerabilidades de las imagenes")
    assert "cancelled()" in str(grype.get("if", "")) and 'exit "$fallos"' in grype["run"]
    sbom = _paso("SBOM por artefacto")
    assert 'exit "$fallos"' in sbom["run"]


ESCENARIOS = {
    # objetivo -> lista de coincidencias, "falla" (grype no produce informe) o "invalido"
    "api_alto_pasarela_limpia": ({"api": [("CVE-SINT-1", "libejemplo", "High")], "pasarela": []}, 1),
    "ambas_limpias": ({"api": [("CVE-SINT-2", "libejemplo", "Low")], "pasarela": []}, 0),
    "grype_falla_en_api": ({"api": "falla", "pasarela": []}, 1),
    "informe_invalido_en_pasarela": ({"api": [], "pasarela": "invalido"}, 1),
    "critico_en_pasarela": ({"api": [], "pasarela": [("CVE-SINT-3", "libotra", "Critical")]}, 1),
}


@pytest.mark.skipif(BASH is None, reason="bash no disponible")
@pytest.mark.parametrize("escenario", sorted(ESCENARIOS))
def test_paso_de_grype_evalua_las_dos_imagenes_y_acumula(tmp_path, escenario):
    resultados, esperado = ESCENARIOS[escenario]
    for rel in ("backend/scripts/ci_umbral_vulnerabilidades.py", "despliegue/seguridad/excepciones-vulnerabilidades.json"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / rel, tmp_path / rel)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "resultados.json").write_text(json.dumps(resultados), encoding="utf-8")
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "open(os.environ['LLAMADAS'], 'a').write(' '.join(args) + '\\n')\n"
        "objetivo = next(a.split('imagen-')[1].split('.cdx')[0] for a in args if a.startswith('sbom:'))\n"
        "destino = args[args.index('--file') + 1].replace('/w/', os.getcwd() + '/')\n"
        "r = json.load(open(os.environ['RESULTADOS']))[objetivo]\n"
        "if r == 'falla':\n    sys.exit(1)\n"
        "if r == 'invalido':\n    json.dump({'descriptor': {'name': 'otro'}}, open(destino, 'w')); sys.exit(0)\n"
        "json.dump({'descriptor': {'name': 'grype', 'version': '0.121.0'}, 'matches': [\n"
        "    {'vulnerability': {'id': i, 'severity': s}, 'artifact': {'name': n, 'version': '1'}} for i, n, s in r]},\n"
        "    open(destino, 'w'))\n", encoding="utf-8")
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    guion = tmp_path / "paso.sh"
    guion.write_text(_paso("Vulnerabilidades de las imagenes")["run"], encoding="utf-8")
    resumen = tmp_path / "resumen.md"
    entorno = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "GRYPE": "grype-sustituto",
               "GITHUB_STEP_SUMMARY": str(resumen), "LLAMADAS": str(tmp_path / "llamadas.txt"),
               "RESULTADOS": str(tmp_path / "resultados.json")}
    r = subprocess.run([BASH, "--noprofile", "--norc", "-eo", "pipefail", str(guion)], cwd=tmp_path, env=entorno,
                       capture_output=True, text=True, timeout=120)
    llamadas = (tmp_path / "llamadas.txt").read_text(encoding="utf-8")
    assert "imagen-api.cdx.json" in llamadas and "imagen-pasarela.cdx.json" in llamadas, "no se intentaron las dos"
    assert (r.returncode == 0) == (esperado == 0), (escenario, r.returncode, r.stdout, r.stderr)
    texto = resumen.read_text(encoding="utf-8") if resumen.exists() else ""
    for objetivo, valor in resultados.items():
        if valor != "falla":
            assert (tmp_path / f"grype-{objetivo}.json").exists()
        if isinstance(valor, list):
            assert f"imagen-{objetivo}" in texto + r.stdout, f"no se evaluo imagen-{objetivo}"
