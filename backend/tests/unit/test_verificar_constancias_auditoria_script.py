"""Tests de la Etapa AE-80, validada localmente como trabajo preparatorio:
comando de solo lectura `scripts/verificar_constancias_auditoria.py` sobre
directorios en disco, en Linux y en Windows.

Sobre la base fallan porque el comando, su modulo, la demostracion, la
seleccion de Windows y el paso del workflow no existen todavia. La
demostracion se ejecuta con el comando real en procesos aparte. Los enlaces
simbolicos se prueban de verdad cuando el sistema permite crearlos; si no,
se sustituye la consulta al sistema, sin omitir la prueba."""
from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from app.application.ml import registro_prospectivo as rp
from tests.unit.ml import fixtures_constancias_auditoria as fc
from tests.unit.ml import fixtures_expediente_portable as fp

RAIZ = Path(__file__).resolve().parents[3]
BACKEND = RAIZ / "backend"


def _script():
    ruta = BACKEND / "scripts" / "verificar_constancias_auditoria.py"
    especificacion = importlib.util.spec_from_file_location("verificar_constancias_auditoria", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _ca():
    return importlib.import_module("app.application.ml.constancias_auditoria")


def _preparar(raiz: Path, estado: str, constancias=(), *, politica_constancias=None):
    entradas = fc.entradas(estado)
    fp.escribir(raiz / "politica", entradas["politica_del_verificador"])
    fp.escribir(raiz / "politica_auditoria", entradas["politica_de_auditoria"])
    fp.escribir(raiz / "politica_constancias", politica_constancias or fc.politica_de_constancias())
    rutas = [fp.escribir(raiz / f"e{i}", e) for i, e in enumerate(entradas["expedientes"], start=1)]
    argumentos = [*rutas, "--politica", raiz / "politica", "--politica-auditoria", raiz / "politica_auditoria",
                  "--capturas", fp.escribir(raiz / "capturas", entradas["capturas"][0]),
                  "--politica-constancias", raiz / "politica_constancias"]
    if constancias:
        argumentos += ["--constancias", fp.escribir(raiz / "constancias", _ca().componer_constancias(list(constancias)))]
    return argumentos


def _ejecutar(s, capsys, *argumentos):
    codigo = s.main([str(a) for a in argumentos])
    return codigo, capsys.readouterr()


def _huella_directorio(directorio: Path) -> dict:
    return {p.relative_to(directorio).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directorio.rglob("*")) if p.is_file()}


def test_ae80_continuidad_sale_con_0_escribe_json_fuera_y_no_toca_nada(tmp_path, capsys):
    s = _script()
    x1 = fc.constancia("s1")
    argumentos = _preparar(tmp_path / "entrada", "s2", [x1, fc.constancia("s2", "x", 2, x1)])
    antes = _huella_directorio(tmp_path / "entrada")
    destino = tmp_path / "salida" / "informe.json"
    destino.parent.mkdir()
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", destino)
    assert codigo == 0 and "Autorizacion operativa: DENEGADA" in salida.out
    assert "enlazada_desde_la_primera_entre_lo_presentado" in salida.out
    informe = json.loads(destino.read_bytes())
    assert informe["resultado"] == "constancia_y_auditoria_coincidentes"
    assert _huella_directorio(tmp_path / "entrada") == antes
    texto = destino.read_text(encoding="utf-8")
    assert str(tmp_path) not in texto and str(tmp_path).replace("\\", "\\\\") not in texto and "PRIVATE" not in texto
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", destino)
    assert codigo == 2 and "ya existe" in salida.err


def test_ae80_codigos_1_4_y_5(tmp_path, capsys):
    s = _script()
    x1 = fc.constancia("s1")
    bifurcacion = _preparar(tmp_path / "a", "s2", [x1, fc.constancia("s2", "x", 2, x1),
                                                   fc.constancia("s1", "x", 2, x1)])
    codigo, salida = _ejecutar(s, capsys, *bifurcacion, "--formato", "json")
    assert codigo == 1 and json.loads(salida.out)["entre_constancias"]["motivos"] == ["bifurcacion_firmada"]
    sustituido = _preparar(tmp_path / "b", "sustituido", [x1])
    codigo, salida = _ejecutar(s, capsys, *sustituido, "--formato", "json")
    assert codigo == 4 and "entrada_atestada_no_presentada" in json.loads(salida.out)["constancias"][0]["cotejo"]
    sin = _preparar(tmp_path / "c", "s1")
    codigo, salida = _ejecutar(s, capsys, *sin, "--formato", "json")
    assert codigo == 5 and json.loads(salida.out)["resultado"] == "sin_constancia_admitida"


def test_ae80_huellas_externas(tmp_path, capsys):
    s = _script()
    x1 = fc.constancia("s1")
    argumentos = _preparar(tmp_path, "s1", [x1])
    sha = hashlib.sha256(fc.politica_de_constancias()["politica_constancias.json"]).hexdigest()
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json", "--huella-politica-constancias", sha,
                               "--huella-constancia", fc.id_(x1))
    assert codigo == 0 and json.loads(salida.out)["procedencia"]["faltan"] == []
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json", "--huella-constancia", "0" * 64)
    assert codigo == 4


def _enlazar(destino: Path, enlace: Path, monkeypatch):
    try:
        os.symlink(destino, enlace)
        return "real"
    except (OSError, NotImplementedError):
        enlace.write_bytes(b"x")
        cargador = importlib.import_module("scripts.verificar_expediente_recepcion")
        original = cargador._es_enlace
        monkeypatch.setattr(cargador, "_es_enlace", lambda p: p == enlace or original(p))
        return "simulado"


def test_ae80_rutas_hostiles_y_enlaces_son_lectura_rechazada(tmp_path, capsys, monkeypatch):
    s = _script()
    argumentos = _preparar(tmp_path / "a", "s1", [fc.constancia("s1")])
    manifiesto_ruta = tmp_path / "a" / "constancias" / "constancias.json"
    manifiesto = json.loads(manifiesto_ruta.read_bytes())
    manifiesto["constancias"][0]["firma"] = "../../politica/politica.json"
    manifiesto_ruta.write_bytes(rp.serializar_entrada(manifiesto))
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    informe = json.loads(salida.out)
    assert codigo == 3 and informe["conjuntos_de_constancias"][0]["lectura"]["motivos"] == ["ruta_invalida"]
    otro = _preparar(tmp_path / "b", "s1", [fc.constancia("s1")])
    (tmp_path / "fuera.bin").write_bytes(b"fuera")
    _enlazar(tmp_path / "fuera.bin", tmp_path / "b" / "constancias" / "constancias" / "enlace.bin", monkeypatch)
    codigo, salida = _ejecutar(s, capsys, *otro, "--formato", "json")
    assert codigo == 3
    assert json.loads(salida.out)["conjuntos_de_constancias"][0]["lectura"]["motivos"] == ["enlace_simbolico"]


def test_ae80_constancia_firmada_con_alcance_mal_tipado_no_derriba_el_comando(tmp_path):
    """Regresion: una constancia canonica, firmada por una clave admitida,
    con un `alcance` de tipos mezclados recorre el comando real sin
    traceback, queda no admitida y sale con el codigo 4."""
    import subprocess
    import sys
    ca = _ca()
    pieza = ca.leer_constancia(fc.constancia("s1").datos)
    pieza["alcance"] = [["0" * 64, "canal", []], ["0" * 64, 7, []]]
    argumentos = _preparar(tmp_path, "s1", [fc.firmar(pieza, "x")])
    entorno = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONDONTWRITEBYTECODE": "1"}
    salidas = [subprocess.run([sys.executable, "-m", "scripts.verificar_constancias_auditoria",
                               *[str(a) for a in argumentos], "--formato", "json"],
                              cwd=BACKEND, env=entorno, capture_output=True, check=False) for _ in range(2)]
    for proceso in salidas:
        assert proceso.returncode == 4, proceso.stderr.decode("utf-8", "replace")
        assert b"Traceback" not in proceso.stderr and proceso.stderr == b""
    assert salidas[0].stdout == salidas[1].stdout
    informe = json.loads(salidas[0].stdout)
    fila = informe["constancias"][0]
    assert fila["admitida"] is False and fila["motivos"] == ["pieza_mal_formada"]
    assert informe["resultado"] == "constancia_no_coincide"


def _captura_no_estandar(literal: bytes):
    """Captura firmada de prueba con una constante JSON no estandar en sus
    bytes, construidos sin el serializador canonico."""
    from app.application.ml import expediente_r0_recepcion as ex
    datos = fc.fa.capturar(fc.fa.e1(), "a").datos
    assert datos.count(b'"secuencia":1,') == 1
    datos = datos.replace(b'"secuencia":1,', b'"secuencia":' + literal + b",")
    return ex.ObjetoFirmado(datos, fc.fa.clave_privada("a").sign(datos), fc.fa.clave_publica("a"))


@pytest.mark.parametrize("literal", [b"NaN", b"1e999"])
def test_ae80_comandos_ae79_y_ae80_con_captura_no_estandar_sin_traceback(tmp_path, literal):
    """Regresion del lector compartido de AE-76: el comando real de AE-79 y
    el de AE-80 emiten su informe y salen con el codigo de evidencia que no
    coincide, sin traceback y con stderr vacio."""
    import subprocess
    import sys
    ac = importlib.import_module("app.application.ml.auditoria_cruzada")
    argumentos = _preparar(tmp_path, "s1", [fc.constancia("s1")])
    capturas = tmp_path / "capturas_no_estandar"
    fp.escribir(capturas, ac.componer_capturas([*fc.capturas_s1(), _captura_no_estandar(literal)]))
    indice = argumentos.index("--capturas") + 1
    argumentos[indice] = capturas
    entorno = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONDONTWRITEBYTECODE": "1"}
    corte = argumentos.index("--politica-constancias")
    comandos = {"auditar_expedientes_cruzados": argumentos[:corte],
                "verificar_constancias_auditoria": argumentos}
    for modulo, args in comandos.items():
        salidas = [subprocess.run([sys.executable, "-m", f"scripts.{modulo}", *[str(a) for a in args],
                                   "--formato", "json"], cwd=BACKEND, env=entorno, capture_output=True,
                                  check=False) for _ in range(2)]
        for proceso in salidas:
            assert proceso.returncode == 4, (modulo, proceso.stderr.decode("utf-8", "replace"))
            assert proceso.stderr == b""
        assert salidas[0].stdout == salidas[1].stdout
        informe = json.loads(salidas[0].stdout)
        ae79 = informe if modulo == "auditar_expedientes_cruzados" else informe["informe_ae79"]
        assert any(c["lectura"]["motivos"] == ["pieza_ilegible"] for c in ae79["capturas"])


def _expediente_con(ruta_archivo: str, datos: bytes) -> dict:
    """E1 con un archivo sustituido y su entrada del manifiesto
    actualizada (tamano y SHA-256)."""
    archivos = {**fc.fa.e1(), ruta_archivo: datos}
    manifiesto = json.loads(archivos["manifiesto.json"])
    for entrada in manifiesto["archivos"]:
        if entrada["ruta"] == ruta_archivo:
            entrada.update(bytes=len(datos), sha256=hashlib.sha256(datos).hexdigest())
    archivos["manifiesto.json"] = rp.serializar_entrada(manifiesto)
    return archivos


def _con_nan(datos: bytes) -> bytes:
    import re
    nuevo = re.sub(rb'":(\d+)([,}])', rb'":NaN\2', datos, count=1)
    assert nuevo != datos
    return nuevo


def _ejecutar_real(modulo: str, argumentos: list) -> object:
    import subprocess
    import sys
    entorno = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-m", f"scripts.{modulo}", *[str(a) for a in argumentos],
                           "--formato", "json"], cwd=BACKEND, env=entorno, capture_output=True, check=False)


def test_ae80_comando_ae78_con_lectores_de_ae75_y_ae77_no_estandar(tmp_path):
    """Regresiones de AE-75 y AE-77 con el comando real de AE-78: un
    compromiso R0 o una declaracion del observador (firmada de nuevo) con
    NaN da un plano rechazado y codigo 1, sin traceback ni stderr."""
    from tests.unit.ml import fixtures_recepcion_por_objetivo as fo
    politica = fp.escribir(tmp_path / "politica", fc.fa.politica_del_verificador())
    e1 = fc.fa.e1()
    declaracion = _con_nan(e1["conjunto_esperado/datos.json"])
    firma = fo.clave_privada("observador").sign(declaracion)
    casos = {
        "compromiso_r0": _expediente_con("sellos_r0/baloto-2714/compromiso.json",
                                         _con_nan(e1["sellos_r0/baloto-2714/compromiso.json"])),
        "declaracion": _reemplazar_en(_expediente_con("conjunto_esperado/datos.json", declaracion),
                                      "conjunto_esperado/firma.bin", firma),
    }
    for nombre, archivos in casos.items():
        expediente = fp.escribir(tmp_path / nombre, archivos)
        proceso = _ejecutar_real("verificar_expediente_recepcion", [expediente, "--politica", politica])
        assert proceso.returncode == 1, (nombre, proceso.stderr.decode("utf-8", "replace"))
        assert proceso.stderr == b""
        informe = json.loads(proceso.stdout)
        assert informe["resultado_de_la_auditoria"] == "con_rechazos"


def _reemplazar_en(archivos: dict, ruta_archivo: str, datos: bytes) -> dict:
    archivos = {**archivos, ruta_archivo: datos}
    manifiesto = json.loads(archivos["manifiesto.json"])
    for entrada in manifiesto["archivos"]:
        if entrada["ruta"] == ruta_archivo:
            entrada.update(bytes=len(datos), sha256=hashlib.sha256(datos).hexdigest())
    archivos["manifiesto.json"] = rp.serializar_entrada(manifiesto)
    return archivos


def test_ae80_comandos_ae78_y_ae79_con_manifiesto_1e999(tmp_path):
    """Regresion de AE-78: un manifiesto con 1e999 es una lectura
    rechazada (codigo 3) en los comandos de AE-78 y AE-79, sin traceback."""
    import re
    e1 = dict(fc.fa.e1())
    e1["manifiesto.json"] = re.sub(rb'"bytes":\d+', b'"bytes":1e999', e1["manifiesto.json"], count=1)
    politica = fp.escribir(tmp_path / "politica", fc.fa.politica_del_verificador())
    auditoria = fp.escribir(tmp_path / "politica_auditoria", fc.fa.politica_de_auditoria())
    malo = fp.escribir(tmp_path / "e1", e1)
    bueno = fp.escribir(tmp_path / "e2", fc.fa.e2())
    proceso = _ejecutar_real("verificar_expediente_recepcion", [malo, "--politica", politica])
    assert proceso.returncode == 3 and proceso.stderr == b""
    assert json.loads(proceso.stdout)["lectura"]["motivos"] == ["manifiesto_ilegible"]
    proceso = _ejecutar_real("auditar_expedientes_cruzados", [malo, bueno, "--politica", politica,
                                                              "--politica-auditoria", auditoria])
    assert proceso.returncode == 3 and proceso.stderr == b""
    filas = json.loads(proceso.stdout)["expedientes"]
    assert {"nombre": "e1", "lectura": {"estado": "rechazada", "motivos": ["manifiesto_ilegible"]}} in filas


def test_ae80_uso_incorrecto(tmp_path, capsys):
    s = _script()
    argumentos = _preparar(tmp_path, "s1", [fc.constancia("s1")])
    resto = argumentos[2:]
    codigo, salida = _ejecutar(s, capsys, tmp_path / "e1", *resto)
    assert codigo == 2 and "entre 2 y 8" in salida.err
    codigo, salida = _ejecutar(s, capsys, tmp_path / "e1", tmp_path / "e1", *resto)
    assert codigo == 2 and "dos veces" in salida.err
    nueve = [a for i in range(9) for a in ("--constancias", tmp_path / f"k{i}")]
    codigo, salida = _ejecutar(s, capsys, *argumentos[:-2], *nueve)
    assert codigo == 2 and "como maximo 8" in salida.err
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", tmp_path / "constancias" / "x.json")
    assert codigo == 2 and "fuera" in salida.err
    try:
        _ejecutar(s, capsys, *argumentos, "--huella-constancia", "NO")
    except SystemExit as salida_argparse:
        assert salida_argparse.code == 2
    else:
        raise AssertionError("argparse debia rechazar la huella")


def test_ae80_limite_agregado(tmp_path, capsys, monkeypatch):
    s = _script()
    argumentos = _preparar(tmp_path, "s1", [fc.constancia("s1")])
    monkeypatch.setattr(s.ac, "ARCHIVOS_AGREGADOS", 70)
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"] == {"estado": "rechazada", "objeto": "entradas",
                                                                 "motivos": ["limite_agregado_superado"]}


def test_ae80_json_independiente_del_orden_de_los_argumentos(tmp_path, capsys):
    s = _script()
    x1 = fc.constancia("s1")
    argumentos = _preparar(tmp_path, "s1", [x1, fc.constancia("s1", "y")])
    _, uno = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    _, dos = _ejecutar(s, capsys, argumentos[1], argumentos[0], *argumentos[2:], "--formato", "json")
    assert uno.out == dos.out and uno.out.endswith("\n")


def test_ae80_demostracion_con_el_comando_real(tmp_path):
    demostracion = importlib.import_module("tests.demostracion_constancias_auditoria")
    resultados = demostracion.ejecutar(tmp_path)
    assert [(r["escenario"], r["codigo"]) for r in resultados] == [
        ("continuidad_valida", 0), ("informe_sustituido", 4), ("expediente_sustituido", 4),
        ("bifurcacion_firmada", 1), ("discrepancia_entre_firmantes", 1), ("predecesor_omitido", 0),
        ("clave_no_admitida", 4), ("politica_de_claves_incorrecta", 4)]
    assert all(r["correcto"] for r in resultados)


def test_ae80_script_de_solo_lectura_y_puro():
    texto = (BACKEND / "scripts" / "verificar_constancias_auditoria.py").read_text(encoding="utf-8")
    arbol = ast.parse(texto)
    llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "open"]
    assert len(llamadas) == 1 and ast.literal_eval(llamadas[0].args[1]) == "xb"
    atributos = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    assert not atributos & {"unlink", "rmdir", "replace", "rename", "mkdir", "write_bytes", "write_text", "now",
                            "today", "utcnow"}
    modulos = {a.name.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
    modulos |= {(n.module or "").split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
    assert not modulos & {"socket", "urllib", "requests", "http", "subprocess", "time", "datetime", "pickle"}


def test_ae80_seleccion_windows_y_workflow():
    seleccion = (BACKEND / "tests" / "seleccion_windows.txt").read_text(encoding="utf-8").split()
    for prueba in ("tests/unit/ml/test_constancias_auditoria.py",
                   "tests/unit/test_verificar_constancias_auditoria_script.py",
                   "tests/unit/ml/test_auditoria_cruzada.py", "tests/unit/test_auditar_expedientes_cruzados_script.py",
                   "tests/unit/ml/test_sello_temporal_r0.py"):
        assert prueba in seleccion, prueba
    assert len(seleccion) == len(set(seleccion))
    workflow = (RAIZ / ".github" / "workflows" / "validacion-python-314.yml").read_text(encoding="utf-8")
    assert workflow.count("python -m tests.demostracion_constancias_auditoria") == 2
    assert workflow.count("python -m tests.demostracion_auditoria_cruzada") == 2
    assert "--modo exigir" in workflow and "--modo permitir_omision" in workflow
    assert workflow.count("scripts/ci_contrastes_openssl.py") == 2
