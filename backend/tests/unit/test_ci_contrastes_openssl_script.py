"""Tests de la Etapa AE-76, validada localmente como trabajo preparatorio:
comprobador de los contrastes con
`openssl ts -verify` y workflow de validacion en Linux y Windows.

El comprobador nunca presenta omisiones como exitos; el workflow no usa
secretos ni despliega, y en Windows solo admite los siete contrastes
superados o los siete omitidos, con estado explicito. Sobre la base estos
tests fallan porque el script, la seleccion y el workflow no existen."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
BACKEND = RAIZ / "backend"
WORKFLOW = RAIZ / ".github" / "workflows" / "validacion-python-314.yml"
SELECCION = BACKEND / "tests" / "seleccion_windows.txt"


def _script():
    ruta = BACKEND / "scripts" / "ci_contrastes_openssl.py"
    especificacion = importlib.util.spec_from_file_location("ci_contrastes_openssl", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _junit(tmp_path, estados, *, extra=""):
    casos = []
    for i, estado in enumerate(estados):
        cuerpo = {"pasa": "", "omite": '<skipped message="sin OpenSSL en PATH"/>', "falla": '<failure message="x"/>',
                  "error": '<error message="x"/>'}[estado]
        casos.append(f'<testcase classname="tests.unit.ml.test_sello_temporal_r0" '
                     f'name="test_g1_contraste_con_openssl_ts_verify[opciones{i}-True]">{cuerpo}</testcase>')
    xml = f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{"".join(casos)}{extra}</testsuite></testsuites>'
    ruta = tmp_path / "r.xml"
    ruta.write_text(xml, encoding="utf-8")
    return str(ruta)


@pytest.mark.parametrize("estados, modo, codigo, fragmento", [
    (["pasa"] * 7, "exigir", 0, "SUPERADOS 7/7"),
    (["pasa"] * 7, "permitir_omision", 0, "SUPERADOS 7/7"),
    (["omite"] * 7, "exigir", 1, "INCOMPLETOS"),
    (["omite"] * 7, "permitir_omision", 0, "OMITIDOS 7/7"),
    (["pasa"] * 4 + ["omite"] * 3, "permitir_omision", 1, "INCOMPLETOS"),
    (["pasa"] * 6 + ["falla"], "permitir_omision", 1, "FALLAN"),
    (["pasa"] * 6 + ["error"], "exigir", 1, "FALLAN"),
    (["pasa"] * 6, "exigir", 1, "ERROR"),
    ([], "permitir_omision", 1, "ERROR"),
])
def test_ae76_comprobador_no_presenta_omisiones_como_exito(tmp_path, estados, modo, codigo, fragmento, capsys):
    m = _script()
    resumen = tmp_path / "resumen.md"
    assert m.main([_junit(tmp_path, estados), "--modo", modo, "--resumen", str(resumen)]) == codigo
    salida = capsys.readouterr().out
    assert fragmento in salida
    assert resumen.read_text(encoding="utf-8").strip() == salida.strip()
    if "OMITIDOS" in salida:
        assert "no cuentan como superados" in salida


def test_ae76_comprobador_ignora_otras_pruebas(tmp_path):
    m = _script()
    otra = ('<testcase classname="tests.unit.ml.test_otro" name="test_g1_contraste_con_openssl_ts_verify[x]"/>'
            '<testcase classname="tests.unit.ml.test_sello_temporal_r0" name="test_g1_bordes"/>')
    assert m.contar(_junit(tmp_path, ["pasa"] * 7, extra=otra)) == {"pasados": 7, "omitidos": 0, "fallidos": 0,
                                                                    "errores": 0, "otras_omitidas": 0}


def test_ae76_comprobador_falla_con_omisiones_ajenas(tmp_path, capsys):
    m = _script()
    ajena = ('<testcase classname="tests.unit.test_generalizacion_juegos" name="test_http">'
             '<skipped message="could not import httpx"/></testcase>')
    for modo in ("exigir", "permitir_omision"):
        assert m.main([_junit(tmp_path, ["pasa"] * 7, extra=ajena), "--modo", modo]) == 1
        assert "1 pruebas ajenas omitidas" in capsys.readouterr().out


def test_ae76_seleccion_windows_existe_y_cubre_lo_necesario():
    rutas = [linea for linea in SELECCION.read_text(encoding="utf-8").splitlines() if linea]
    assert len(rutas) == len(set(rutas))
    for ruta in rutas:
        assert (BACKEND / ruta).exists(), ruta
    for necesaria in ("tests/unit/ml/test_sello_temporal_r0.py", "tests/unit/ml/test_expediente_r0_recepcion.py",
                      "tests/unit/ml/test_registro_prospectivo.py", "tests/unit/ml/test_contrato_vinculo_r0.py",
                      "tests/unit/test_ci_contrastes_openssl_script.py"):
        assert necesaria in rutas


def test_ae76_workflow_minimo_sin_secretos_ni_despliegue():
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in texto
    for prohibido in ("secrets.", "deploy", "curl ", "wget ", "Invoke-WebRequest", "choco ", "--no-verify"):
        assert prohibido not in texto, prohibido
    assert texto.count('python-version: "3.14"') == 2
    assert "runs-on: ubuntu-24.04" in texto and "runs-on: windows-2025" in texto
    assert "python -m pip install -r requirements.txt" in texto and texto.count("python -m pip check") == 2
    assert "httpx==0.28.1" in texto
    assert "--modo exigir" in texto and "--modo permitir_omision" in texto
    assert "seleccion_windows.txt" in texto
    assert texto.count("--junitxml") == 2
    assert "|| true" not in texto and "continue-on-error" not in texto
