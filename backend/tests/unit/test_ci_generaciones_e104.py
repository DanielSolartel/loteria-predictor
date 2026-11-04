"""E10.4: el trabajo `generaciones` del CI ejecuta C1-C10 con PostgreSQL real y la demostracion completa, sin
debilitar nada (sin `continue-on-error`, acciones e imagen por SHA/digest, informes sin secretos siempre)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[3]
FLUJO = RAIZ / ".github" / "workflows" / "seguridad-consulta-privada.yml"


def _trabajo() -> dict:
    return yaml.safe_load(FLUJO.read_text(encoding="utf-8"))["jobs"]["generaciones"]


def test_postgres_de_servicio_fijado_por_digest():
    servicio = _trabajo()["services"]["postgres"]
    assert re.search(r"postgres:16-alpine@sha256:[0-9a-f]{64}$", servicio["image"])
    assert servicio["ports"] == ["127.0.0.1:5432:5432"]


def test_ejecuta_c1_c10_con_postgres_y_la_demostracion():
    pasos = _trabajo()["steps"]
    texto = "\n".join(str(p.get("run", "")) for p in pasos)
    pruebas = next(p for p in pasos if "tests/unit/generaciones" in str(p.get("run", "")))
    assert pruebas["env"]["E104_PG_SUPERUSUARIO_URL"].startswith("postgresql://postgres:")
    assert "despliegue/generaciones/demostracion_e104.py" in texto
    for sql in ("consulta-privada/postgres/roles.sql", "generaciones/postgres/rol-captura.sql",
                "generaciones/postgres/roles.sql"):
        assert sql in texto and (RAIZ / "despliegue" / sql).is_file()
    assert "--require-hashes" in texto and "pip check" in texto
    assert all("continue-on-error" not in p for p in pasos)


def test_las_contrasenas_se_generan_y_enmascaran_y_las_url_van_en_archivos():
    roles = next(p for p in _trabajo()["steps"] if str(p.get("name", "")).startswith("Roles"))["run"]
    assert roles.count("openssl rand -hex 24") == 4 and "::add-mask::" in roles
    assert 'chmod 600 "$s"/*' in roles and "mkdir -m 700" in roles


def test_informes_publicados_siempre_y_sin_la_carpeta_de_secretos():
    subida = next(p for p in _trabajo()["steps"] if str(p.get("uses", "")).startswith("actions/upload-artifact@"))
    assert "always()" in str(subida["if"])
    rutas = [l.strip() for l in subida["with"]["path"].splitlines() if l.strip()]
    assert rutas == ["${{ runner.temp }}/e104-junit.xml", "${{ runner.temp }}/e104-demostracion/demostracion.json"]
    assert not any("secretos" in r for r in rutas)


def test_el_rol_importador_puede_marcar_sus_bases_sin_ser_superusuario():
    """E104-IMP-01: la propiedad se acredita con ajustes de base propios; sin este permiso (PostgreSQL >= 15)
    un rol no superusuario no puede guardarlos y toda importacion se rechazaria."""
    roles = (RAIZ / "despliegue" / "generaciones" / "postgres" / "roles.sql").read_text(encoding="utf-8")
    assert "GRANT SET ON PARAMETER loteria.importacion, loteria.restauracion TO generaciones_importador;" in roles
    assert "SUPERUSER CREATEDB" not in roles.replace("NOSUPERUSER CREATEDB", "")
