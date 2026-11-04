"""Fase 10 (E10.3): coherencia del lock de Python, de las imagenes y del workflow de seguridad (solo lectura de
archivos del repositorio; sin red)."""
from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
RAIZ = BACKEND.parent
_ENTRADA = re.compile(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)(?: ; ([^\\]+))? \\$")


def _nombre(texto: str) -> str:
    return re.split(r"[<>=!~;\[ ]", texto.strip(), maxsplit=1)[0].lower().replace("_", "-")


def _requisitos(ruta: Path) -> list[str]:
    return [l.strip() for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def _lock(ruta: Path) -> dict[str, dict]:
    paquetes, actual = {}, None
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.startswith("#") or not linea.strip():
            continue
        if not linea.startswith(" "):
            m = _ENTRADA.match(linea)
            assert m, f"{ruta.name}: entrada sin fijar o con otro formato: {linea}"
            actual = m.group(1).lower()
            paquetes[actual] = {"version": m.group(2), "marcador": m.group(3), "hashes": []}
        else:
            h = re.fullmatch(r"\s+--hash=sha256:([0-9a-f]{64})(?: \\)?", linea)
            assert h and actual, f"{ruta.name}: linea no admitida: {linea}"
            paquetes[actual]["hashes"].append(h.group(1))
    return paquetes


def test_cada_paquete_de_cada_lock_esta_fijado_y_con_hash():
    for nombre in ("requirements.lock", "requirements-servicio.lock", "requirements-auditoria.lock"):
        paquetes = _lock(BACKEND / nombre)
        assert paquetes and all(p["hashes"] for p in paquetes.values()), nombre


def test_el_lock_cubre_requirements_txt_y_las_pruebas_con_las_mismas_versiones_fijadas():
    lock = _lock(BACKEND / "requirements.lock")
    for requisito in _requisitos(BACKEND / "requirements.txt") + _requisitos(BACKEND / "requirements-pruebas.in"):
        nombre = _nombre(requisito)
        assert nombre in lock, requisito
        fijada = re.search(r"==\s*([^;\s]+)", requisito)
        if fijada:
            assert lock[nombre]["version"] == fijada.group(1), requisito
    assert lock["tzdata"]["marcador"] == "sys_platform == 'win32'"


def test_el_lock_de_servicio_es_requirements_txt_sin_herramientas_de_pruebas():
    servicio = _requisitos(BACKEND / "requirements-servicio.in")
    esperado = [r for r in _requisitos(BACKEND / "requirements.txt") if not _nombre(r).startswith("pytest")]
    assert servicio == esperado
    completo, imagen = _lock(BACKEND / "requirements.lock"), _lock(BACKEND / "requirements-servicio.lock")
    assert not {"pytest", "pytest-cov", "httpx"} & set(imagen)
    assert all(completo[n]["version"] == p["version"] for n, p in imagen.items())  # mismas versiones acreditadas


def test_imagenes_con_bases_por_digest_y_sin_secretos_en_la_construccion():
    dockerfile = (RAIZ / "despliegue/imagenes/Dockerfile").read_text(encoding="utf-8")
    bases = re.findall(r"^ARG \w+_IMAGEN=(\S+)$", dockerfile, re.M)
    assert len(bases) == 2 and all(re.search(r"@sha256:[0-9a-f]{64}$", b) for b in bases)
    assert "requirements-servicio.lock" in dockerfile and "--require-hashes" in dockerfile
    assert re.findall(r"^USER (\S+)", dockerfile, re.M) == ["10001:10001", "10001:10001"]
    assert not re.search(r"^(ENV|ARG) .*(CLAVE|SECRETO|PASSWORD|DATABASE_URL=)", dockerfile, re.M)
    ignorado = (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "*" in ignorado and ignorado.index("*") < ignorado.index("!backend/app/")  # todo fuera salvo lo listado
    for patron in ("**/.env", "**/*.privado.*", "backend/storage/", "backend/privado/", "**/*.sqlite"):
        assert patron in ignorado
    compose = (RAIZ / "despliegue/consulta-privada/compose.yml").read_text(encoding="utf-8")
    assert all("@sha256:" in i for i in re.findall(r"image: (docker\.io/\S+)", compose))


def test_workflow_de_seguridad_fija_acciones_por_sha_y_no_tolera_fallos():
    texto = (RAIZ / ".github/workflows/seguridad-consulta-privada.yml").read_text(encoding="utf-8")
    usos = re.findall(r"uses: (\S+)", texto)
    assert usos and all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u) for u in usos)
    assert "continue-on-error:" not in texto and "secrets." not in texto
    assert all("@sha256:" in v for v in re.findall(r"^  (?:SYFT|GRYPE|GITLEAKS): (\S+)$", texto, re.M))
    for existente in ("validacion-python-314.yml", "validacion-frontend.yml"):
        assert (RAIZ / ".github/workflows" / existente).is_file()
    assert '-path "/srv/*storage*"' not in texto  # v2 (F1023-CI-01): ya no confunde codigo con datos
    assert "comprobar_contenido_imagen.py" in texto


def test_todas_las_acciones_remotas_de_todos_los_workflows_van_por_sha():
    """v2 (F1023-CI-02): tambien los workflows existentes; sin etiquetas ni ramas mutables."""
    flujos = sorted((RAIZ / ".github/workflows").glob("*.yml"))
    assert {f.name for f in flujos} >= {"validacion-python-314.yml", "validacion-frontend.yml",
                                        "seguridad-consulta-privada.yml"}
    for flujo in flujos:
        usos = re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", flujo.read_text(encoding="utf-8"), re.M)
        assert usos, flujo.name
        for uso in usos:
            assert uso.startswith("./") or re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", uso), (flujo.name, uso)
