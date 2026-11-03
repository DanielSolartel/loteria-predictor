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
    # E101-CI-01: campos nuevos de omisiones de plataforma; los conteos anteriores se siguen comprobando.
    assert m.contar(_junit(tmp_path, ["pasa"] * 7, extra=otra), "linux") == {
        "pasados": 7, "omitidos": 0, "fallidos": 0, "errores": 0, "otras_omitidas": 0,
        "omisiones_plataforma": [], "omisiones_repetidas": 0, "omisiones_ambiguas": 0, "plataforma": "linux"}


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


# ---------------------------------------------------------------------------------------------------------------
# E101-CI-01 (E10.1): omisiones de plataforma admitidas solo por identidad, motivo y plataforma exactos.
ACL_MOD = "tests.unit.seguridad_consola.test_permisos_windows_nativo"
ACL_MOTIVO = "ensayo nativo de ACL: requiere Windows"
ACL = [(ACL_MOD, n, ACL_MOTIVO) for n in ("test_nativo_crear_deja_propietario_y_dacl_solo_del_usuario",
                                          "test_nativo_ace_amplia_posterior_cierra_y_al_retirarla_vuelve",
                                          "test_nativo_directorio_preexistente_no_se_modifica")]
POSIX = [("tests.unit.seguridad_consola.test_almacen_y_credenciales",
          "test_permisos_del_propietario_y_permisos_abiertos_cierran",
          "permisos POSIX; en Windows: test_permisos_windows_nativo.py (v2)"),
         ("tests.unit.seguridad_consola.test_regresiones_v2",
          "test_posix_directorio_preexistente_amplio_se_rechaza_sin_cambiarlo", "permisos POSIX"),
         ("tests.unit.seguridad_consola.test_regresiones_v2",
          "test_posix_cambio_posterior_de_permisos_y_enlace_cierran", "permisos POSIX")]
CONDICIONAL = [(ACL_MOD, "test_nativo_directorio_preexistente_no_se_modifica",
                "la carpeta temporal ya es exclusiva del usuario; el caso no es aplicable aquí")]
AJENA = [("tests.unit.test_generalizacion_juegos", "test_http", "could not import httpx")]


def _omisiones(omisiones, *, con=""):
    """Casos omitidos con la forma que escribe pytest (`type="pytest.skip"`, motivo exacto en `message`)."""
    return "".join(f'<testcase classname="{m}" name="{n}" time="0.000"><skipped type="pytest.skip" '
                   f'message="{motivo}">x</skipped>{con}</testcase>' for m, n, motivo in omisiones)


def _ejecutar(tmp_path, monkeypatch, capsys, plataforma, estados, omisiones, modo, *, con=""):
    monkeypatch.setattr("sys.platform", plataforma)
    m = _script()
    resumen = tmp_path / "resumen.md"
    codigo = m.main([_junit(tmp_path, estados, extra=_omisiones(omisiones, con=con)), "--modo", modo,
                     "--resumen", str(resumen)])
    salida = capsys.readouterr().out
    assert resumen.read_text(encoding="utf-8").strip() == salida.strip()  # el resumen escrito coincide
    return codigo, salida


@pytest.mark.parametrize("plataforma, estados, omisiones, modo, estado", [
    ("linux", ["pasa"] * 7, ACL, "exigir", "SUPERADOS 7/7"),
    ("linux", ["pasa"] * 7, ACL, "permitir_omision", "SUPERADOS 7/7"),  # el modo no decide la plataforma
    ("win32", ["pasa"] * 7, POSIX, "permitir_omision", "SUPERADOS 7/7"),
    ("win32", ["pasa"] * 7, POSIX + CONDICIONAL, "permitir_omision", "SUPERADOS 7/7"),
    ("win32", ["omite"] * 7, POSIX, "permitir_omision", "OMITIDOS 7/7"),
])
def test_e101_ci_omisiones_de_plataforma_admitidas_e_informadas(tmp_path, monkeypatch, capsys, plataforma, estados,
                                                                omisiones, modo, estado):
    codigo, salida = _ejecutar(tmp_path, monkeypatch, capsys, plataforma, estados, omisiones, modo)
    assert codigo == 0 and estado in salida.splitlines()[0]
    pasados = 7 if estados[0] == "pasa" else 0
    assert f"{pasados} pasados, {7 - pasados} omitidos, 0 fallidos, 0 errores de 7 esperados" in salida
    assert f"{len(omisiones)} omisiones de plataforma ({plataforma}) aparte, no cuentan como superadas" in salida
    detalle = salida.splitlines()[1:]
    assert detalle == [f"omision de plataforma ({plataforma}): {m}::{n} - {motivo}" for m, n, motivo in omisiones]
    if estado.startswith("OMITIDOS"):
        assert "no cuentan como superados" in salida and "SUPERADOS" not in salida


def test_e101_ci_resumen_de_estado_con_recuento_aunque_no_haya_omisiones(tmp_path, monkeypatch, capsys):
    codigo, salida = _ejecutar(tmp_path, monkeypatch, capsys, "linux", ["pasa"] * 7, [], "exigir")
    assert codigo == 0 and salida.strip().splitlines() == [
        "contrastes_openssl: SUPERADOS 7/7 (7 pasados, 0 omitidos, 0 fallidos, 0 errores de 7 esperados; "
        "0 omisiones de plataforma (linux) aparte, no cuentan como superadas)"]


def test_e101_ci_las_omisiones_de_plataforma_no_se_suman_a_los_contrastes(tmp_path):
    m = _script()
    cuenta = m.contar(_junit(tmp_path, ["pasa"] * 7, extra=_omisiones(ACL)), "linux")
    assert (cuenta["pasados"], cuenta["omitidos"], cuenta["otras_omitidas"]) == (7, 0, 0)
    assert [(o["modulo"], o["prueba"], o["motivo"]) for o in cuenta["omisiones_plataforma"]] == ACL
    assert m.dictamen(cuenta, "exigir")[0] == 0
    cuenta = m.contar(_junit(tmp_path, ["pasa"] * 6, extra=_omisiones(ACL)), "linux")
    assert m.dictamen(cuenta, "exigir")[0] == 1  # tres omisiones no completan los siete contrastes


@pytest.mark.parametrize("plataforma, estados, omisiones, modo, fragmento", [
    ("linux", ["pasa"] * 7, POSIX, "exigir", "3 pruebas ajenas omitidas"),           # plataforma equivocada
    ("win32", ["pasa"] * 7, ACL, "permitir_omision", "3 pruebas ajenas omitidas"),   # «requiere Windows» en Windows
    ("darwin", ["pasa"] * 7, ACL, "exigir", "3 pruebas ajenas omitidas"),            # plataforma sin lista
    ("linux", ["pasa"] * 7, ACL + AJENA, "exigir", "1 pruebas ajenas omitidas"),
    ("win32", ["pasa"] * 7, POSIX + AJENA, "permitir_omision", "1 pruebas ajenas omitidas"),
    ("linux", ["pasa"] * 7, [(ACL_MOD, ACL[0][1], "could not import httpx")], "exigir", "1 pruebas ajenas omitidas"),
    ("linux", ["pasa"] * 7, [(ACL_MOD, ACL[0][1], ACL_MOTIVO + " ")], "exigir", "1 pruebas ajenas omitidas"),
    ("linux", ["pasa"] * 7, [(ACL_MOD, "test_otro", ACL_MOTIVO)], "exigir", "1 pruebas ajenas omitidas"),
    ("win32", ["pasa"] * 7, [("tests.unit.otro", POSIX[0][1], POSIX[0][2])], "permitir_omision",
     "1 pruebas ajenas omitidas"),
    ("linux", ["pasa"] * 7, [("tests.unit.seguridad_consola.test_permisos_windows_nativo.Clase", ACL[0][1], ACL_MOTIVO)],
     "exigir", "1 pruebas ajenas omitidas"),
    ("win32", ["pasa"] * 7, [(CONDICIONAL[0][0], POSIX[1][1], CONDICIONAL[0][2])], "permitir_omision",
     "1 pruebas ajenas omitidas"),                                                  # motivo condicional en otra prueba
    ("linux", ["pasa"] * 7, CONDICIONAL, "exigir", "1 pruebas ajenas omitidas"),     # condicional solo en Windows
    ("linux", ["pasa"] * 7, ACL + [ACL[0]], "exigir", "1 omisiones de plataforma repetidas"),
    ("linux", ["omite"] * 7, ACL, "exigir", "INCOMPLETOS"),
    ("win32", ["pasa"] * 6 + ["omite"], POSIX, "permitir_omision", "INCOMPLETOS"),
    ("linux", ["pasa"] * 6, ACL, "exigir", "se encontraron 6 casos"),
    ("win32", ["pasa"] * 8, POSIX, "permitir_omision", "se encontraron 8 casos"),
    ("linux", ["pasa"] * 6 + ["error"], ACL, "exigir", "FALLAN"),
    ("win32", ["pasa"] * 6 + ["falla"], POSIX, "permitir_omision", "FALLAN"),
    ("linux", [], ACL, "exigir", "se encontraron 0 casos"),
])
def test_e101_ci_omisiones_indebidas_y_contrastes_incorrectos_se_rechazan(tmp_path, monkeypatch, capsys, plataforma,
                                                                         estados, omisiones, modo, fragmento):
    codigo, salida = _ejecutar(tmp_path, monkeypatch, capsys, plataforma, estados, omisiones, modo)
    assert codigo == 1 and fragmento in salida
    assert "SUPERADOS" not in salida and "OMITIDOS" not in salida


@pytest.mark.parametrize("con", ['<failure message="x"/>', '<error message="x"/>'])
def test_e101_ci_omision_legitima_con_fallo_o_error_es_ambigua(tmp_path, monkeypatch, capsys, con):
    codigo, salida = _ejecutar(tmp_path, monkeypatch, capsys, "win32", ["pasa"] * 7, [POSIX[0]], "permitir_omision",
                               con=con)
    assert codigo == 1 and "1 pruebas omitidas con fallo o error" in salida and "SUPERADOS" not in salida


def test_e101_ci_plataforma_efectiva_y_no_nombre_del_xml_ni_texto_del_motivo(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.platform", "win32")
    m = _script()
    ruta = tmp_path / "resultados-linux.xml"  # el nombre no decide
    ruta.write_text(Path(_junit(tmp_path, ["pasa"] * 7, extra=_omisiones(ACL))).read_text(encoding="utf-8"),
                    encoding="utf-8")
    assert m.main([str(ruta), "--modo", "exigir"]) == 1 and "3 pruebas ajenas omitidas" in capsys.readouterr().out
    assert m.contar(str(ruta))["plataforma"] == "win32"
    assert m.contar(str(ruta), "linux")["otras_omitidas"] == 0


def test_e101_ci_lista_de_omisiones_coincide_con_las_pruebas_reales():
    """La lista admitida reproduce los `skipif`/`pytest.skip` exactos de las pruebas de E10.1."""
    m = _script()
    base = BACKEND / "tests" / "unit" / "seguridad_consola"
    nativo = (base / "test_permisos_windows_nativo.py").read_text(encoding="utf-8")
    assert 'reason="ensayo nativo de ACL: requiere Windows"' in nativo
    assert 'pytest.skip("la carpeta temporal ya es exclusiva del usuario; el caso no es aplicable aquí")' in nativo
    assert 'reason="permisos POSIX; en Windows: test_permisos_windows_nativo.py (v2)"' in (
        base / "test_almacen_y_credenciales.py").read_text(encoding="utf-8")
    assert (base / "test_regresiones_v2.py").read_text(encoding="utf-8").count('reason="permisos POSIX")') == 2
    for plataforma, omisiones in (("linux", ACL), ("win32", POSIX + CONDICIONAL)):
        assert {(mo, n): motivo for mo, n, motivo in omisiones} == m.OMISIONES_PLATAFORMA[plataforma]
    for (modulo, prueba) in {**m.OMISIONES_PLATAFORMA["linux"], **m.OMISIONES_PLATAFORMA["win32"]}:
        fuente = (BACKEND / (modulo.replace(".", "/") + ".py")).read_text(encoding="utf-8")
        assert f"def {prueba}(" in fuente, (modulo, prueba)
