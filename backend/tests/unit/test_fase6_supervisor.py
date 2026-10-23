"""Contrato del supervisor con procesos/pytest reales y datos mínimos propios.

No son entrenamientos ML ni instalación nativa de tareas; las pruebas de fallo
inyectan errores solo en mediciones/limpieza de su temporal privado.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import sys
import zipfile

import pytest

from tests import ejecutar_fase6_windows as supervisor


def _inventario(codigo):
    filas = []
    for p in sorted(codigo.rglob("*.py")):
        b = p.read_bytes().replace(b"\r\n", b"\n")
        filas.append({"ruta": p.relative_to(codigo).as_posix(), "tipo": "texto",
                      "despues": {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}})
    return {"version": supervisor.VERSION, "base": supervisor.BASE, "inventario_publico": filas}


@pytest.mark.parametrize("salto", ["\n", "\r\n"], ids=["LF", "CRLF"])
@pytest.mark.parametrize("alterado", [False, True])
def test_espejo_f6_textual_conserva_bytes_y_rechaza_cambio(tmp_path, salto, alterado):
    codigo = tmp_path / "codigo"
    codigo.mkdir()
    origen = codigo / "publico.py"
    original = "# Documento público: ñ\nvalor = 1\n".replace("\n", salto).encode("utf-8")
    origen.write_bytes(original)
    mf = _inventario(codigo)
    if alterado:
        origen.write_bytes(original.replace(b"valor = 1", b"valor = 2"))
    antes = origen.read_bytes()
    espejo = tmp_path / "espejo"
    if alterado:
        with pytest.raises(ValueError, match="no coincide con el manifiesto"):
            supervisor._preparar_espejo(codigo, mf, espejo)
        assert not espejo.exists()
    else:
        assert supervisor._preparar_espejo(codigo, mf, espejo) == 1
        assert (espejo / origen.name).read_bytes() == original
    assert origen.read_bytes() == antes


def test_espejo_f6_rechaza_huella_cruda_de_crlf_antes_de_copiar(tmp_path):
    codigo = tmp_path / "codigo"
    codigo.mkdir()
    p = codigo / "a.py"
    p.write_bytes(b"valor = 1\r\n")
    mf = _inventario(codigo)
    mf["inventario_publico"][0]["despues"] = {"bytes": p.stat().st_size,
                                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match="no coincide con el manifiesto"):
        supervisor._preparar_espejo(codigo, mf, tmp_path / "copia")
    assert not (tmp_path / "copia").exists()
    assert p.read_bytes() == b"valor = 1\r\n"


@pytest.mark.parametrize("ruta", ["../.env", "backend/.env", "backend/storage/real.json", "backend//a.py"])
def test_espejo_f6_rechaza_rutas_privadas_o_no_canonicas(ruta):
    with pytest.raises(ValueError):
        supervisor._ruta_publica(ruta)


def test_supervisor_f6_presupuesto_temporal_y_mediciones_archivadas():
    temp = PureWindowsPath(r"C:\Users\danie\AppData\Local\Temp") / "f6 12345678"
    r = supervisor.rutas_temporales(temp)
    espejo = r["codigo"] / "backend/tests/unit/test_fase6_tarea_windows.py"
    modelo = r["sinteticos"] / dict(supervisor.ALMACENES_SINTETICOS)["LABORATORIO_MODELOS"] / "modelos/BALOTO/estimadores" / ("a" * 64 + ".mljson")
    medicion = r["mediciones"] / ("m-" + "f" * 64 + ".json")
    for p in (espejo, modelo, medicion):
        assert len(str(p).encode("utf-16-le")) // 2 <= 259
    assert r["pytest"] == temp
    assert " " in str(r["codigo"])


@pytest.mark.parametrize("bateria", ["dirigida", "focal", "regresiones", "completa"])
def test_supervisor_f6_etapas_no_inician_completa_por_implicacion(tmp_path, bateria):
    comandos = supervisor._comandos(bateria, tmp_path / "r.xml", tmp_path)
    pytest = comandos[0][1]
    assert "--basetemp" not in " ".join(pytest)
    assert "--junitxml=" + str(tmp_path / "r.xml") in pytest
    nombres = [n for n, c in comandos]
    if bateria == "completa":
        assert pytest[-1] == "tests" and "-k" not in pytest
        assert nombres == ["pytest-completa", "openssl-exigir", "demostracion-fase6", "pip-check"]
    else:
        assert "tests" not in pytest
        assert nombres == ["pytest-" + bateria, "pip-check"]


@pytest.mark.parametrize("escenario", ["pytest_falla", "archivo_falla", "limpieza_falla"])
def test_supervisor_f6_conserva_resultado_y_mediciones_al_fallar(tmp_path, monkeypatch, escenario):
    codigo = tmp_path / "c"
    pruebas = codigo / "backend/tests"
    pruebas.mkdir(parents=True)
    (pruebas / "__init__.py").write_text("", encoding="utf-8")
    caso = pruebas / "test_minimo.py"
    caso.write_text(
        "import os\nfrom pathlib import Path\n"
        "def test_control():\n"
        "    p = Path(os.environ['FASE4_EVIDENCIA'])\n"
        "    p.mkdir(parents=True, exist_ok=True)\n"
        "    (p / 'm-control.json').write_bytes(b'{\\\"prueba\\\":\\\"control\\\",\\\"datos\\\":[1,2,3]}')\n"
        + ("    assert True\n" if escenario == "limpieza_falla" else "    assert False, 'FALLO DELIBERADO'\n"),
        encoding="utf-8",
    )
    mf = tmp_path / "mf.json"
    mf.write_text(json.dumps(_inventario(codigo)), encoding="utf-8")
    evidencia = tmp_path / "descargas" / "extraccion con espacios" / "e"
    env_sha = lambda: hashlib.sha256(json.dumps(dict(os.environ), sort_keys=True).encode()).hexdigest()
    antes = env_sha()
    def comandos(bateria, junit, e):
        return [("pytest-focal", [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
                                  "tests/test_minimo.py", "--junitxml=" + str(junit)]),
                ("no-debe-ejecutarse", [sys.executable, "archivo-inexistente.py"])] if escenario != "limpieza_falla" else [
                    ("pytest-focal", [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
                                      "tests/test_minimo.py", "--junitxml=" + str(junit)])]
    monkeypatch.setattr(supervisor, "_comandos", comandos)
    if escenario == "archivo_falla":
        def archivo_falla(*a):
            raise OSError("FALLO ARCHIVO INYECTADO")
        monkeypatch.setattr(supervisor, "_conservar_mediciones", archivo_falla)
    if escenario == "limpieza_falla":
        def limpieza_falla(temporal):
            assert (evidencia / "resultado-validacion.json").exists()
            raise PermissionError("FALLO LIMPIEZA INYECTADO")
        monkeypatch.setattr(supervisor, "_limpiar_temporal", limpieza_falla)
    codigo_salida = supervisor.validar(codigo, mf, evidencia, 45, "focal")
    resultado = json.loads((evidencia / "resultado-validacion.json").read_text(encoding="utf-8"))
    assert codigo_salida == (0 if escenario == "limpieza_falla" else 1)
    assert len(resultado["pasos"]) == 1
    assert resultado["junit"]["fallidas"] == (0 if escenario == "limpieza_falla" else 1)
    assert (evidencia / resultado["pasos"][0]["log"]).exists()
    assert (evidencia / "resultados-focal.xml").exists()
    if escenario == "archivo_falla":
        pendiente = Path(resultado["temporal_pendiente"])
        assert (pendiente / "e/m-control.json").read_bytes() == b'{"prueba":"control","datos":[1,2,3]}'
        assert "FALLO ARCHIVO" in resultado["error_mediciones"]
        shutil.rmtree(pendiente)
    else:
        with zipfile.ZipFile(evidencia / resultado["mediciones"]["archivo"]) as z:
            assert z.testzip() is None and z.namelist() == ["m-control.json"]
            for f in resultado["mediciones"]["archivos"]:
                b = z.read(f["ruta"])
                assert len(b) == f["bytes"] and hashlib.sha256(b).hexdigest() == f["sha256"]
        if escenario == "limpieza_falla":
            assert resultado["estado"] == "aprobado" and resultado["codigo"] == 0
            assert resultado["estado_limpieza"] == "pendiente" and resultado["avisos_limpieza"]
            shutil.rmtree(Path(resultado["temporal_pendiente"]))
        else:
            assert resultado["estado_limpieza"] == "completa"
    assert env_sha() == antes


def test_supervisor_dirigida_incluye_solo_xml_limpieza_captura_y_supervisor(tmp_path):
    esperadas = ("tarea_windows", "xml_windows", "ensayo_limpieza_windows", "exportacion_windows", "supervisor")
    rutas = tuple("tests/unit/test_fase6_" + nombre + ".py" for nombre in esperadas)
    assert supervisor.DIRIGIDAS == rutas
    assert set(rutas) <= set(supervisor.FOCALES)
    comandos = supervisor._comandos("dirigida", tmp_path / "r.xml", tmp_path)
    assert tuple(comandos[0][1][-len(rutas):]) == rutas
    assert [nombre for nombre, _ in comandos] == ["pytest-dirigida", "pip-check"]
    assert all("demostracion" not in " ".join(comando) for _, comando in comandos)
