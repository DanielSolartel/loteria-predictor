"""Tests de la Etapa AE-79, validada localmente como trabajo preparatorio:
comando de solo lectura `scripts/auditar_expedientes_cruzados.py` sobre
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

from tests.unit.ml import fixtures_auditoria_cruzada as fa
from tests.unit.ml import fixtures_expediente_portable as fp

RAIZ = Path(__file__).resolve().parents[3]
BACKEND = RAIZ / "backend"


def _script():
    ruta = BACKEND / "scripts" / "auditar_expedientes_cruzados.py"
    especificacion = importlib.util.spec_from_file_location("auditar_expedientes_cruzados", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _ac():
    return importlib.import_module("app.application.ml.auditoria_cruzada")


def _preparar(raiz: Path, expedientes: dict, capturas=()):
    """Escribe politicas, expedientes y (si hay) un directorio de capturas;
    devuelve los argumentos del comando."""
    fp.escribir(raiz / "politica", fa.politica_del_verificador())
    fp.escribir(raiz / "politica_auditoria", fa.politica_de_auditoria())
    rutas = [fp.escribir(raiz / nombre, archivos) for nombre, archivos in expedientes.items()]
    argumentos = [*rutas, "--politica", raiz / "politica", "--politica-auditoria", raiz / "politica_auditoria"]
    if capturas:
        argumentos += ["--capturas", fp.escribir(raiz / "capturas", _ac().componer_capturas(list(capturas)))]
    return argumentos


def _ejecutar(s, capsys, *argumentos):
    codigo = s.main([str(a) for a in argumentos])
    return codigo, capsys.readouterr()


def _huella_directorio(directorio: Path) -> dict:
    return {p.relative_to(directorio).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directorio.rglob("*")) if p.is_file()}


def test_ae79_compatibles_sale_con_0_escribe_json_fuera_y_no_toca_nada(tmp_path, capsys):
    s = _script()
    e1, e2 = fa.e1(), fa.e2()
    argumentos = _preparar(tmp_path / "entrada", {"e1": e1, "e2": e2}, [fa.capturar(e1, "a"), fa.capturar(e2, "b")])
    antes = _huella_directorio(tmp_path / "entrada")
    destino = tmp_path / "salida" / "informe.json"
    destino.parent.mkdir()
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", destino)
    assert codigo == 0
    assert "Entre expedientes: compatibles" in salida.out and "AUTORIZA_EVALUACION = False" in salida.out
    assert "Autorizacion operativa: DENEGADA" in salida.out
    informe = json.loads(destino.read_bytes())
    assert informe["resultado"] == "sin_contradiccion_detectable"
    assert _huella_directorio(tmp_path / "entrada") == antes
    texto = destino.read_text(encoding="utf-8")
    assert str(tmp_path) not in texto and str(tmp_path).replace("\\", "\\\\") not in texto
    assert "PRIVATE" not in texto
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", destino)
    assert codigo == 2 and "ya existe" in salida.err


def test_ae79_conflicto_firmado_sale_con_1(tmp_path, capsys):
    s = _script()
    e1, e2, e3 = fa.e1(), fa.e2(), fa.e3()
    a1 = fa.capturar(e1, "a")
    argumentos = _preparar(tmp_path, {"e1": e1, "e2": e2, "e3": e3},
                           [a1, fa.capturar(e2, "b"), fa.capturar(e2, "a", 2, a1), fa.capturar(e3, "c")])
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    informe = json.loads(salida.out)
    assert codigo == 1 and informe["resultado"] == "contradiccion_comprobada"
    assert {"discrepancia_entre_firmantes", "omision_comprobable"} <= set(informe["entre_expedientes"]["motivos"])
    assert all(f["ae78"]["resultado"] == "sin_rechazos" for f in informe["expedientes"])


def test_ae79_manifiesto_sustituido_sale_con_4_y_huellas_externas(tmp_path, capsys):
    s = _script()
    e1, e2, sustituto = fa.e1(), fa.e2(), fa.e2_sin_un_sello()
    b1 = fa.capturar(e2, "b")
    argumentos = _preparar(tmp_path, {"e1": e1, "e2": sustituto}, [fa.capturar(e1, "a"), b1])
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json", "--huella-manifiesto", fa.sha(e2),
                               "--huella-politica", fa.sha256_politica())
    informe = json.loads(salida.out)
    assert codigo == 4 and informe["resultado"] == "evidencia_no_coincide"
    estados = {c["objeto"]: c["estado"] for c in informe["procedencia"]["comprobaciones"]}
    assert estados == {"politica_del_verificador": "coincide", "manifiesto": "no_coincide"}
    assert "politica_de_auditoria" in informe["procedencia"]["faltan"]


def test_ae79_lectura_rechazada_de_un_expediente_sale_con_3_y_evalua_los_demas(tmp_path, capsys):
    s = _script()
    e1, e2, e3 = fa.e1(), fa.e2(), fa.e3()
    argumentos = _preparar(tmp_path, {"e1": e1, "e2": e2, "e3": e3})
    (tmp_path / "e3" / "acuses" / "intruso.bin").write_bytes(b"no declarado")
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    informe = json.loads(salida.out)
    assert codigo == 3 and informe["resultado"] == "lectura_rechazada"
    rechazado = next(f for f in informe["expedientes"] if f["lectura"]["estado"] == "rechazada")
    assert rechazado == {"nombre": "e3", "lectura": {"estado": "rechazada", "motivos": ["archivo_no_declarado"]}}
    assert sum(1 for f in informe["expedientes"] if "ae78" in f) == 2


def _enlazar(destino: Path, enlace: Path, s, monkeypatch):
    """Enlace real si el sistema lo permite; si no, la consulta del cargador
    de AE-78 lo ve como enlace (misma ruta de rechazo)."""
    try:
        os.symlink(destino, enlace)
        return "real"
    except (OSError, NotImplementedError):
        enlace.write_bytes(b"x")
        cargador = importlib.import_module("scripts.verificar_expediente_recepcion")
        original = cargador._es_enlace
        monkeypatch.setattr(cargador, "_es_enlace", lambda p: p == enlace or original(p))
        return "simulado"


def test_ae79_enlace_en_un_directorio_de_capturas(tmp_path, capsys, monkeypatch):
    s = _script()
    e1, e2 = fa.e1(), fa.e2()
    argumentos = _preparar(tmp_path, {"e1": e1, "e2": e2}, [fa.capturar(e1, "a")])
    (tmp_path / "fuera.txt").write_bytes(b"fuera")
    _enlazar(tmp_path / "fuera.txt", tmp_path / "capturas" / "capturas" / "enlace.bin", s, monkeypatch)
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    informe = json.loads(salida.out)
    assert codigo == 3
    assert informe["conjuntos_de_capturas"] == [{"nombre": "capturas", "lectura": {
        "estado": "rechazada", "motivos": ["enlace_simbolico"]}}]


def test_ae79_uso_incorrecto(tmp_path, capsys):
    s = _script()
    e1, e2 = fa.e1(), fa.e2()
    argumentos = _preparar(tmp_path, {"e1": e1, "e2": e2})
    politicas = argumentos[2:]
    codigo, salida = _ejecutar(s, capsys, tmp_path / "e1", *politicas)
    assert codigo == 2 and "entre 2 y 8" in salida.err
    codigo, salida = _ejecutar(s, capsys, *([tmp_path / "e1"] * 9), *politicas)
    assert codigo == 2
    codigo, salida = _ejecutar(s, capsys, tmp_path / "e1", tmp_path / "e1", *politicas)
    assert codigo == 2 and "dos veces" in salida.err
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", tmp_path / "e1" / "informe.json")
    assert codigo == 2 and "fuera" in salida.err
    assert not (tmp_path / "e1" / "informe.json").exists()
    try:
        _ejecutar(s, capsys, *argumentos, "--huella-politica", "no-hex")
    except SystemExit as salida_argparse:
        assert salida_argparse.code == 2
    else:
        raise AssertionError("argparse debia rechazar la huella")


def test_ae79_limite_agregado(tmp_path, capsys, monkeypatch):
    s = _script()
    e1, e2 = fa.e1(), fa.e2()
    argumentos = _preparar(tmp_path, {"e1": e1, "e2": e2})
    total_e1 = sum(len(v) for v in e1.values())
    monkeypatch.setattr(s.ac, "BYTES_AGREGADOS", total_e1 * 2)
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    informe = json.loads(salida.out)
    assert codigo == 3 and informe["lectura"] == {"estado": "rechazada", "objeto": "entradas",
                                                  "motivos": ["limite_agregado_superado"]}
    monkeypatch.setattr(s.ac, "BYTES_AGREGADOS", 64 << 20)
    monkeypatch.setattr(s.ac, "ARCHIVOS_AGREGADOS", 60)
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"]["motivos"] == ["limite_agregado_superado"]


def test_ae79_json_independiente_del_orden_de_los_argumentos(tmp_path, capsys):
    s = _script()
    e1, e2, e3 = fa.e1(), fa.e2(), fa.e3()
    argumentos = _preparar(tmp_path, {"e1": e1, "e2": e2, "e3": e3},
                           [fa.capturar(e1, "a"), fa.capturar(e3, "c")])
    _, uno = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    reordenados = [argumentos[2], argumentos[0], argumentos[1], *argumentos[3:]]
    _, dos = _ejecutar(s, capsys, *reordenados, "--formato", "json")
    assert uno.out == dos.out and uno.out.endswith("\n")


def test_ae79_demostracion_con_el_comando_real(tmp_path):
    demostracion = importlib.import_module("tests.demostracion_auditoria_cruzada")
    resultados = demostracion.ejecutar(tmp_path)
    assert [(r["escenario"], r["codigo"], r["estado"]) for r in resultados] == [
        ("dos_capturas_compatibles", 0, "compatibles"),
        ("tercera_captura_extiende_la_historia", 0, "progresion_demostrable"),
        ("conflicto_firmado_solo_visible_en_la_auditoria_cruzada", 1, "contradiccion_comprobada"),
        ("protocolos_distintos_incomparables", 0, "incomparables"),
        ("manifiesto_sustituido_frente_a_captura_firmada", 4, "compatibles"),
    ]
    assert all(r["correcto"] for r in resultados)


def test_ae79_script_de_solo_lectura_y_puro():
    texto = (BACKEND / "scripts" / "auditar_expedientes_cruzados.py").read_text(encoding="utf-8")
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


def test_ae79_seleccion_windows_y_workflow():
    seleccion = (BACKEND / "tests" / "seleccion_windows.txt").read_text(encoding="utf-8").split()
    for prueba in ("tests/unit/ml/test_auditoria_cruzada.py", "tests/unit/test_auditar_expedientes_cruzados_script.py",
                   "tests/unit/ml/test_expediente_portable.py", "tests/unit/test_verificar_expediente_recepcion_script.py",
                   "tests/unit/ml/test_sello_temporal_r0.py"):
        assert prueba in seleccion, prueba
    assert len(seleccion) == len(set(seleccion))
    workflow = (RAIZ / ".github" / "workflows" / "validacion-python-314.yml").read_text(encoding="utf-8")
    assert workflow.count("python -m tests.demostracion_auditoria_cruzada") == 2
    assert "name: Linux - suite completa" in workflow
    assert "name: Windows - seleccion de tests/seleccion_windows.txt" in workflow
    assert "--modo exigir" in workflow and "--modo permitir_omision" in workflow
    assert workflow.count("scripts/ci_contrastes_openssl.py") == 2
