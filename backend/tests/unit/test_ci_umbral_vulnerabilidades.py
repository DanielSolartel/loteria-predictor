"""Fase 10 (E10.3, v2): umbral de vulnerabilidades del CI.

- Informes REALES de `npm audit --json` (fixtures `tests/fixtures/e103`: el lock con vitest 3.2.7 de v1 y el de
  v2 con vitest 4.1.12) y variantes sinteticas derivadas de ellos.
- La aceptacion de una excepcion es solo MODELADA en archivos temporales: ninguna se acepta de verdad.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import ci_umbral_vulnerabilidades as u

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "e103"
NPM_V1 = json.loads((FIX / "npm-audit-vitest3.json").read_text(encoding="utf-8"))
NPM_V2 = json.loads((FIX / "npm-audit-vitest4.json").read_text(encoding="utf-8"))
TINYPOOL = ("GHSA-5gmw-xhrv-c9v3", "GHSA-85c8-ppgw-ccpr")


def _excepcion(aviso, **extra):
    return {"id": aviso, "paquete": "tinypool", "artefacto": "frontend-npm", "caduca": "2026-12-31", **extra}


def _aceptada(aviso, **extra):  # MODELO de prueba, no una aceptacion real
    return _excepcion(aviso, estado="aceptada", aceptada_por="MODELO_DE_PRUEBA", fecha_aceptacion="2026-11-01",
                      **extra)


def _correr(tmp_path, informe, excepciones=(), formato="npm", artefacto="frontend-npm", hoy="2026-11-03",
            texto=None):
    ruta, exc = tmp_path / "informe.json", tmp_path / "exc.json"
    ruta.write_text(texto if texto is not None else json.dumps(informe), encoding="utf-8")
    exc.write_text(json.dumps({"excepciones": list(excepciones)}), encoding="utf-8")
    return u.main([str(ruta), "--formato", formato, "--artefacto", artefacto, "--excepciones", str(exc), "--hoy", hoy])


def _grype(*avisos):
    return {"descriptor": {"name": "grype", "version": "0.121.0"}, "source": {"type": "sbom"}, "matches": [
        {"vulnerability": {"id": a, "severity": s}, "artifact": {"name": p, "version": "1.0", "type": "deb"},
         "matchDetails": []} for a, p, s in avisos]}


# --- informes reales ---------------------------------------------------------------------------------

def test_informe_real_v2_sin_criticos_es_correcto(tmp_path):
    assert u.hallazgos_npm(NPM_V2) == [("GHSA-g3hv-75wg-m249", "minimatch", "moderate")]
    assert _correr(tmp_path, NPM_V2) == 0


def test_informe_real_v1_con_criticos_de_tinypool_falla(tmp_path):
    graves = [f for f in u.hallazgos_npm(NPM_V1) if f[2] == "critical"]
    assert sorted(f[0] for f in graves) == sorted(TINYPOOL) and {f[1] for f in graves} == {"tinypool"}
    assert _correr(tmp_path, NPM_V1) == 1


# --- excepciones: solo una aceptacion explicita las activa -------------------------------------------

@pytest.mark.parametrize("estado", [None, "pendiente_de_aceptacion", "rechazada", "retirada_por_actualizacion",
                                    "Aceptada", "aceptado", ""])
def test_excepcion_no_aceptada_no_se_activa(tmp_path, estado):
    extra = {} if estado is None else {"estado": estado}
    assert _correr(tmp_path, NPM_V1, [_excepcion(a, **extra, aceptada_por="x", fecha_aceptacion="2026-11-01")
                                      for a in TINYPOOL]) == 1


@pytest.mark.parametrize("cambio", [{"aceptada_por": None}, {"aceptada_por": " "}, {"fecha_aceptacion": None},
                                    {"fecha_aceptacion": "2026-11-04"}, {"fecha_aceptacion": "ayer"},
                                    {"caduca": "2026-11-02"}, {"artefacto": "imagen-api"}, {"paquete": "vitest"},
                                    {"id": "GHSA-*"}])
def test_aceptacion_incompleta_futura_caducada_o_de_otro_alcance_no_se_activa(tmp_path, cambio):
    assert _correr(tmp_path, NPM_V1, [{**_aceptada(a), **cambio} for a in TINYPOOL]) == 1


def test_aceptacion_modelada_cubre_solo_sus_avisos(tmp_path):
    assert _correr(tmp_path, NPM_V1, [_aceptada(a) for a in TINYPOOL]) == 0
    assert _correr(tmp_path, NPM_V1, [_aceptada(TINYPOOL[0])]) == 1
    assert _correr(tmp_path, NPM_V1, [_aceptada(a) for a in TINYPOOL], hoy="2027-01-01") == 1


def test_excepciones_versionadas_no_estan_aceptadas():
    datos = json.loads(u.EXCEPCIONES.read_text(encoding="utf-8"))["excepciones"]
    assert datos and not any(e.get("estado") == "aceptada" for e in datos)
    assert all(e.get("aceptada_por") is None and e.get("fecha_aceptacion") is None for e in datos)
    assert all({"id", "paquete", "artefacto", "caduca", "motivo", "estado"} <= set(e) for e in datos)


# --- informes incoherentes, incompletos o ajenos: nunca limpios --------------------------------------

def _variante(cambiar):
    d = copy.deepcopy(NPM_V1)
    cambiar(d)
    return d


@pytest.mark.parametrize("cambiar", [
    lambda d: d.update(vulnerabilities={}),  # metadata declara 2 criticos sin detalles
    lambda d: d["metadata"]["vulnerabilities"].update(critical=0, total=4),  # detalles sin recuento
    lambda d: d["vulnerabilities"].pop("tinypool"),  # vitest hereda de un paquete ausente
    lambda d: d["vulnerabilities"]["tinypool"].update(severity="moderate"),  # severidad incoherente
    lambda d: d["vulnerabilities"]["vitest"].update(severity="moderate"),  # herencia no resuelta
    lambda d: d["vulnerabilities"]["tinypool"].update(via=[]),
    lambda d: d["vulnerabilities"]["tinypool"]["via"][0].update(severity="grave"),
    lambda d: d["vulnerabilities"]["minimatch"].update(name="otro"),
    lambda d: d.pop("auditReportVersion"),
    lambda d: d.update(auditReportVersion=1),
    lambda d: d["metadata"].pop("vulnerabilities"),
    lambda d: d.update(error={"code": "ENOLOCK", "summary": "sin lock"}),
])
def test_informe_npm_incoherente_falla(tmp_path, cambiar):
    assert _correr(tmp_path, _variante(cambiar)) == 1


def test_informe_npm_vacio_coherente_es_correcto(tmp_path):
    limpio = {"auditReportVersion": 2, "vulnerabilities": {}, "metadata": {"vulnerabilities": {
        "info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 0, "total": 0}, "dependencies": {}}}
    assert _correr(tmp_path, limpio) == 0
    limpio["metadata"]["vulnerabilities"]["critical"] = 1
    assert _correr(tmp_path, limpio) == 1


@pytest.mark.parametrize("texto", ["", "no json", "{}", "[]", '{"matches": []}', "null"])
def test_informe_ausente_vacio_o_ajeno_falla(tmp_path, texto):
    assert _correr(tmp_path, None, texto=texto) == 1
    assert _correr(tmp_path, None, texto=texto, formato="grype", artefacto="imagen-api") == 1


def test_informe_inexistente_falla(tmp_path):
    assert u.main([str(tmp_path / "no.json"), "--formato", "grype", "--artefacto", "imagen-api"]) == 1


# --- grype --------------------------------------------------------------------------------------------

def test_grype_moderados_correcto_y_graves_fallan(tmp_path):
    assert _correr(tmp_path, _grype(("CVE-1", "libx", "Medium"), ("CVE-2", "liby", "Negligible")),
                   formato="grype", artefacto="imagen-api") == 0
    for sev in ("High", "Critical"):
        assert _correr(tmp_path, _grype(("CVE-3", "openssl", sev)), formato="grype", artefacto="imagen-api") == 1


@pytest.mark.parametrize("cambiar", [
    lambda d: d["descriptor"].update(name="otro"), lambda d: d["descriptor"].pop("version"),
    lambda d: d.update(matches={}), lambda d: d["matches"][0]["vulnerability"].update(severity="grave"),
    lambda d: d["matches"][0]["vulnerability"].pop("id"), lambda d: d["matches"][0]["artifact"].pop("version"),
    lambda d: d["matches"].append("texto"),
])
def test_grype_mal_formado_falla(tmp_path, cambiar):
    d = _grype(("CVE-1", "libx", "Medium"))
    cambiar(d)
    assert _correr(tmp_path, d, formato="grype", artefacto="imagen-api") == 1
