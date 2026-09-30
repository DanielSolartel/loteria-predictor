"""Tests de la Etapa AE-78, validada localmente como trabajo preparatorio:
comando de solo lectura `scripts/verificar_expediente_recepcion.py` sobre
expedientes en disco.

Sobre la base fallan porque el script, su modulo y la seleccion o el nombre
del job de Windows no existen todavia. Los enlaces simbolicos se prueban de
verdad cuando el sistema permite crearlos; si no (Windows sin privilegio),
se prueba la misma deteccion sustituyendo la consulta al sistema, sin omitir
la prueba."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from tests.unit.ml import fixtures_expediente_portable as fp

RAIZ = Path(__file__).resolve().parents[3]
BACKEND = RAIZ / "backend"


def _script():
    ruta = BACKEND / "scripts" / "verificar_expediente_recepcion.py"
    especificacion = importlib.util.spec_from_file_location("verificar_expediente_recepcion", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _modulo():
    return importlib.import_module("app.application.ml.expediente_portable")


def _preparar(tmp_path, nombre="integro", archivos=None):
    m = _modulo()
    expediente = fp.escribir(tmp_path / "expediente", archivos or m.componer_expediente(**fp.escenario(nombre)))
    politica = fp.escribir(tmp_path / "politica", fp.politica(m))
    return expediente, politica


def _huella_directorio(directorio: Path) -> dict:
    return {p.relative_to(directorio).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directorio.rglob("*")) if p.is_file()}


def _ejecutar(s, capsys, *argumentos):
    codigo = s.main([str(a) for a in argumentos])
    return codigo, capsys.readouterr()


def test_ae78_expediente_integro_sale_con_0_y_autorizacion_denegada(tmp_path, capsys):
    s = _script()
    expediente, politica = _preparar(tmp_path)
    antes = _huella_directorio(expediente)
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica)
    assert codigo == 0
    assert "Autorizacion operativa: DENEGADA" in salida.out and "no autoriza evaluacion" in salida.out
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--formato", "json")
    assert codigo == 0
    informe = json.loads(salida.out)
    assert informe["resultado_de_la_auditoria"] == "sin_rechazos"
    assert informe["secciones"]["autorizacion_operativa"]["AUTORIZA_EVALUACION"] is False
    assert _huella_directorio(expediente) == antes


def test_ae78_informe_json_a_archivo_fuera_del_expediente(tmp_path, capsys):
    s = _script()
    expediente, politica = _preparar(tmp_path)
    destino = tmp_path / "informe.json"
    codigo, _ = _ejecutar(s, capsys, expediente, "--politica", politica, "--salida-json", destino)
    assert codigo == 0 and json.loads(destino.read_bytes())["esquema"] == "informe-expediente-recepcion/1"
    primero = destino.read_bytes()
    destino.unlink()
    _ejecutar(s, capsys, expediente, "--politica", politica, "--salida-json", destino)
    assert destino.read_bytes() == primero
    for dentro in (expediente / "informe.json", politica / "informe.json"):
        codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--salida-json", dentro)
        assert codigo == 2 and "fuera del expediente" in salida.err
        assert not dentro.exists()
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--salida-json", destino)
    assert codigo == 2 and "ya existe" in salida.err
    assert destino.read_bytes() == primero


@pytest.mark.parametrize("nombre", ["acuse_alterado", "sello_de_otro_acuse", "objetivo_omitido",
                                    "vistas_contradictorias"])
def test_ae78_escenarios_con_rechazos_salen_con_1(tmp_path, capsys, nombre):
    s = _script()
    expediente, politica = _preparar(tmp_path, nombre)
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--formato", "json")
    assert codigo == 1
    informe = json.loads(salida.out)
    assert informe["resultado_de_la_auditoria"] == "con_rechazos"
    assert informe["secciones"]["autorizacion_operativa"]["estado"] == "denegada"


def test_ae78_pieza_o_manifiesto_alterados_en_disco_salen_con_3(tmp_path, capsys):
    s = _script()
    expediente, politica = _preparar(tmp_path)
    manifiesto = json.loads((expediente / "manifiesto.json").read_bytes())
    pieza = expediente.joinpath(*manifiesto["piezas"]["declaracion_r0"].split("/"))
    pieza.write_bytes(pieza.read_bytes().replace(b"valor", b"VALOR", 1))
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--formato", "json")
    assert codigo == 3
    informe = json.loads(salida.out)
    assert informe["lectura"] == {"estado": "rechazada", "motivos": ["sha256_incorrecto"], "objeto": "expediente"}
    assert informe["secciones"] == {}
    otro, politica2 = _preparar(tmp_path / "b")
    (otro / "manifiesto.json").write_bytes((otro / "manifiesto.json").read_bytes().replace(b'",', b'", ', 1))
    codigo, salida = _ejecutar(s, capsys, otro, "--politica", politica2)
    assert codigo == 3 and "manifiesto_no_canonico" in salida.out and "DENEGADA" in salida.out


def test_ae78_ruta_maliciosa_y_archivos_no_declarados(tmp_path, capsys):
    s = _script()
    m = _modulo()
    archivos = m.componer_expediente(**fp.escenario())
    manifiesto = json.loads(archivos["manifiesto.json"])
    original = manifiesto["piezas"]["declaracion_r0"]
    manifiesto["piezas"]["declaracion_r0"] = "../fuera.json"
    for entrada in manifiesto["archivos"]:
        if entrada["ruta"] == original:
            entrada["ruta"] = "../fuera.json"
    datos = archivos.pop(original)
    from app.application.ml import registro_prospectivo as rp
    archivos["manifiesto.json"] = rp.serializar_entrada(manifiesto)
    expediente, politica = _preparar(tmp_path, archivos=archivos)
    (tmp_path / "fuera.json").write_bytes(datos)
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"]["motivos"] == ["ruta_invalida"]
    limpio, politica2 = _preparar(tmp_path / "c")
    (limpio / "acuses" / "intruso.bin").write_bytes(b"no declarado")
    codigo, salida = _ejecutar(s, capsys, limpio, "--politica", politica2, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"]["motivos"] == ["archivo_no_declarado"]


def _enlazar(destino: Path, enlace: Path, s, monkeypatch, *, directorio=False):
    """Crea un enlace real si el sistema lo permite; si no, hace que la
    consulta del script lo vea como enlace (misma ruta de rechazo)."""
    try:
        os.symlink(destino, enlace, target_is_directory=directorio)
        return "real"
    except (OSError, NotImplementedError):
        if directorio:
            enlace.mkdir()
        else:
            enlace.write_bytes(b"x")
        original = s._es_enlace
        monkeypatch.setattr(s, "_es_enlace", lambda p: p == enlace or original(p))
        return "simulado"


def test_ae78_enlaces_simbolicos_se_rechazan(tmp_path, capsys, monkeypatch):
    s = _script()
    expediente, politica = _preparar(tmp_path)
    (tmp_path / "secreto.txt").write_bytes(b"fuera")
    _enlazar(tmp_path / "secreto.txt", expediente / "acuses" / "enlace.bin", s, monkeypatch)
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"]["motivos"] == ["enlace_simbolico"]
    otro, politica2 = _preparar(tmp_path / "d")
    (tmp_path / "d" / "carpeta").mkdir()
    _enlazar(tmp_path / "d" / "carpeta", otro / "subcarpeta", s, monkeypatch, directorio=True)
    codigo, salida = _ejecutar(s, capsys, otro, "--politica", politica2, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"]["motivos"] == ["enlace_simbolico"]


def test_ae78_enlace_simulado_cuando_el_sistema_no_permite_crearlos(tmp_path, capsys, monkeypatch):
    """La rama que usaria Windows sin privilegio para enlaces: se ejerce
    tambien en Linux forzando el fallo de os.symlink."""
    s = _script()
    expediente, politica = _preparar(tmp_path)

    def sin_privilegio(*_args, **_kwargs):
        raise OSError("sin privilegio para crear enlaces")

    monkeypatch.setattr(os, "symlink", sin_privilegio)
    assert _enlazar(tmp_path, expediente / "acuses" / "enlace.bin", s, monkeypatch) == "simulado"
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"]["motivos"] == ["enlace_simbolico"]


def test_ae78_directorio_inexistente_politica_ilegible_y_uso(tmp_path, capsys):
    s = _script()
    expediente, politica = _preparar(tmp_path)
    codigo, salida = _ejecutar(s, capsys, tmp_path / "no-existe", "--politica", politica, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"]["motivos"] == ["directorio_invalido"]
    (politica / "politica.json").write_bytes(b"{}\n")
    codigo, salida = _ejecutar(s, capsys, expediente, "--politica", politica, "--formato", "json")
    informe = json.loads(salida.out)
    assert codigo == 3 and informe["lectura"]["objeto"] == "politica"
    with pytest.raises(SystemExit) as salida_uso:
        s.main([str(expediente)])
    assert salida_uso.value.code == 2


def test_ae78_limites_de_tamano_en_disco(tmp_path, capsys):
    s = _script()
    expediente, politica = _preparar(tmp_path)
    m = _modulo()
    with pytest.raises(m.ExpedienteIlegible) as error:
        s.cargar_directorio(expediente, limites=m.Limites(bytes_por_archivo=64))
    assert error.value.motivo == "archivo_demasiado_grande"
    with pytest.raises(m.ExpedienteIlegible) as error:
        s.cargar_directorio(expediente, limites=m.Limites(archivos=3))
    assert error.value.motivo == "demasiados_archivos"
    cargados = s.cargar_directorio(expediente)
    assert set(cargados) == set(_huella_directorio(expediente))
    assert cargados["manifiesto.json"] == (expediente / "manifiesto.json").read_bytes()


def test_ae78_script_de_solo_lectura_sin_red_ni_deserializacion_ejecutable():
    texto = (BACKEND / "scripts" / "verificar_expediente_recepcion.py").read_text(encoding="utf-8")
    arbol = ast.parse(texto)
    prohibidos = {"socket", "urllib", "requests", "http", "subprocess", "pickle", "marshal", "shelve", "yaml",
                  "random", "secrets", "time", "datetime", "shutil", "tempfile"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"unlink", "rmdir", "rename", "replace", "chmod", "write_text", "mkdir",
                                     "now", "today", "utcnow"}, nodo.attr
    assert texto.count("open(") == 2 and '"rb"' in texto and '"xb"' in texto


def test_ae78_seleccion_windows_y_nombre_duradero_del_job():
    rutas = [l for l in (BACKEND / "tests" / "seleccion_windows.txt").read_text(encoding="utf-8").splitlines() if l]
    assert "tests/unit/ml/test_expediente_portable.py" in rutas
    assert "tests/unit/test_verificar_expediente_recepcion_script.py" in rutas
    assert len(rutas) == len(set(rutas))
    flujo = (RAIZ / ".github" / "workflows" / "validacion-python-314.yml").read_text(encoding="utf-8")
    assert "name: Windows - seleccion de tests/seleccion_windows.txt" in flujo
    assert "seleccion AE-52 a AE-76" not in flujo
    assert "name: Linux - suite completa" in flujo
    assert "--modo exigir" in flujo and "--modo permitir_omision" in flujo
    assert "actions/checkout@v4" in flujo and "actions/setup-python@v5" in flujo
