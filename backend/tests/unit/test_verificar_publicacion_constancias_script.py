"""Tests de la Etapa AE-81, validada localmente como trabajo preparatorio:
comando de solo lectura `scripts/verificar_publicacion_constancias.py`
sobre directorios en disco, en Linux y en Windows.

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
import subprocess
import sys
from pathlib import Path

from app.application.ml import registro_prospectivo as rp
from tests.unit.ml import fixtures_expediente_portable as fp
from tests.unit.ml import fixtures_publicacion_constancias as fpc

RAIZ = Path(__file__).resolve().parents[3]
BACKEND = RAIZ / "backend"


def _script():
    ruta = BACKEND / "scripts" / "verificar_publicacion_constancias.py"
    especificacion = importlib.util.spec_from_file_location("verificar_publicacion_constancias", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _preparar(raiz: Path, **cambios) -> list:
    """Escribe las entradas de `fpc.entradas(**cambios)` y devuelve los
    argumentos del comando (sin `--formato`)."""
    e = fpc.entradas(**cambios)
    rutas = [fp.escribir(raiz / f"e{i}", x) for i, x in enumerate(e["expedientes"], start=1)]
    argumentos = [*rutas, "--politica", fp.escribir(raiz / "politica", e["politica_del_verificador"]),
                  "--politica-auditoria", fp.escribir(raiz / "politica_auditoria", e["politica_de_auditoria"]),
                  "--capturas", fp.escribir(raiz / "capturas", e["capturas"][0]),
                  "--politica-constancias", fp.escribir(raiz / "politica_constancias", e["politica_de_constancias"]),
                  "--constancias", fp.escribir(raiz / "constancias", e["constancias"][0]),
                  "--politica-publicadores", fp.escribir(raiz / "publicadores", e["politica_de_publicadores"]),
                  "--politica-monitores", fp.escribir(raiz / "monitores", e["politica_de_monitores"])]
    for nombre in ("checkpoints", "observaciones"):
        if e[nombre]:
            argumentos += [f"--{nombre}", fp.escribir(raiz / nombre, e[nombre][0])]
    if e["inventario"] is not None:
        argumentos += ["--inventario", fp.escribir(raiz / "inventario", e["inventario"])]
    return argumentos


def _ejecutar(s, capsys, *argumentos):
    codigo = s.main([str(a) for a in argumentos])
    return codigo, capsys.readouterr()


def _huella_directorio(directorio: Path) -> dict:
    return {p.relative_to(directorio).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directorio.rglob("*")) if p.is_file()}


def test_ae81_continuidad_sale_con_0_escribe_json_fuera_y_no_toca_nada(tmp_path, capsys):
    s = _script()
    argumentos = _preparar(tmp_path / "entrada")
    antes = _huella_directorio(tmp_path / "entrada")
    destino = tmp_path / "salida" / "informe.json"
    destino.parent.mkdir()
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", destino)
    assert codigo == 0 and "AUTORIZA_EVALUACION = False" in salida.out and salida.err == ""
    assert "progresion_demostrable_entre_lo_presentado" in salida.out
    informe = json.loads(destino.read_bytes())
    assert informe["resultado"] == "coincidente_con_lo_suministrado"
    assert informe["planos"]["autorizacion_operativa"] == {"estado": "denegada", "AUTORIZA_EVALUACION": False,
                                                           "r0_final": "no_se_promociona"}
    assert informe["planos"]["publicacion_externa"]["estado"] == "no_acreditada"
    assert _huella_directorio(tmp_path / "entrada") == antes
    texto = destino.read_text(encoding="utf-8")
    assert str(tmp_path) not in texto and str(tmp_path).replace("\\", "\\\\") not in texto and "PRIVATE" not in texto
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", destino)
    assert codigo == 2 and "ya existe" in salida.err


def test_ae81_codigos_1_4_5_y_6(tmp_path, capsys):
    s = _script()
    c1, c2, sust = fpc.c1(), fpc.c2(), fpc.c2_sustituto()
    obs = fpc.observacion
    casos = [
        ("bifurcacion", dict(checkpoints=[c1, c2, sust]), 1, "bifurcacion_firmada_del_publicador"),
        ("cabeza_omitida", dict(checkpoints=[c1, sust], observaciones=[obs(sust, "m1"), obs(sust, "m2")],
                                inventario_=fpc.inventario(checkpoints=[c1, sust])), 4, "cabeza_no_publicada"),
        ("predecesor", dict(checkpoints=[c2]), 5, "predecesor_no_presentado"),
        ("sin_inventario", dict(inventario_=None), 5, "inventario_no_aportado"),
        ("discrepancia", dict(observaciones=[obs(c2, "m1"), obs(sust, "m2")]), 6, "discrepancia_entre_monitores"),
    ]
    for nombre, cambios, esperado, motivo in casos:
        argumentos = _preparar(tmp_path / nombre, **cambios)
        codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
        informe = json.loads(salida.out)
        vistos = {m for grupo in informe["motivos"].values() for m in grupo}
        vistos |= {h["motivo"] for h in informe["hallazgos"]}
        assert codigo == esperado and motivo in vistos, (nombre, codigo, sorted(vistos))
        assert informe["planos"]["autorizacion_operativa"]["AUTORIZA_EVALUACION"] is False


def test_ae81_firma_alterada_en_disco_no_coincide(tmp_path, capsys):
    s = _script()
    argumentos = _preparar(tmp_path)
    firma = tmp_path / "checkpoints" / "checkpoints" / "002" / "firma.bin"
    datos = bytearray(firma.read_bytes())
    datos[0] ^= 1
    firma.write_bytes(bytes(datos))
    manifiesto_ruta = tmp_path / "checkpoints" / "checkpoints.json"
    manifiesto = json.loads(manifiesto_ruta.read_bytes())
    relativa = firma.relative_to(tmp_path / "checkpoints").as_posix()
    for entrada in manifiesto["archivos"]:
        if entrada["ruta"] == relativa:
            entrada["sha256"] = hashlib.sha256(bytes(datos)).hexdigest()
    manifiesto_ruta.write_bytes(rp.serializar_entrada(manifiesto))
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    informe = json.loads(salida.out)
    assert codigo == 4 and informe["resultado"] == "no_coincide"
    assert any(not f["admitida"] for f in informe["checkpoints"])


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


def test_ae81_rutas_hostiles_y_enlaces_son_lectura_rechazada(tmp_path, capsys, monkeypatch):
    s = _script()
    argumentos = _preparar(tmp_path / "a")
    manifiesto_ruta = tmp_path / "a" / "observaciones" / "observaciones.json"
    manifiesto = json.loads(manifiesto_ruta.read_bytes())
    manifiesto["observaciones"][0]["firma"] = "../../politica/politica.json"
    manifiesto_ruta.write_bytes(rp.serializar_entrada(manifiesto))
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    informe = json.loads(salida.out)
    assert codigo == 3 and informe["conjuntos"]["observaciones"][0]["lectura"]["motivos"] == ["ruta_invalida"]
    otro = _preparar(tmp_path / "b")
    (tmp_path / "fuera.bin").write_bytes(b"fuera")
    _enlazar(tmp_path / "fuera.bin", tmp_path / "b" / "checkpoints" / "checkpoints" / "enlace.bin", monkeypatch)
    codigo, salida = _ejecutar(s, capsys, *otro, "--formato", "json")
    assert codigo == 3
    assert json.loads(salida.out)["conjuntos"]["checkpoints"][0]["lectura"]["motivos"] == ["enlace_simbolico"]


def test_ae81_inventario_no_canonico_es_lectura_rechazada_sin_traceback(tmp_path):
    argumentos = _preparar(tmp_path)
    ruta = tmp_path / "inventario" / "inventario.json"
    ruta.write_bytes(ruta.read_bytes().replace(b'"naturaleza":', b'"naturaleza" :', 1))
    entorno = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONDONTWRITEBYTECODE": "1"}
    procesos = [subprocess.run([sys.executable, "-m", "scripts.verificar_publicacion_constancias",
                                *[str(a) for a in argumentos], "--formato", "json"], cwd=BACKEND, env=entorno,
                               capture_output=True, check=False) for _ in range(2)]
    for proceso in procesos:
        assert proceso.returncode == 3, proceso.stderr.decode("utf-8", "replace")
        assert proceso.stderr == b""
    assert procesos[0].stdout == procesos[1].stdout
    assert json.loads(procesos[0].stdout)["resultado"] == "lectura_rechazada"


def test_ae81_uso_incorrecto(tmp_path, capsys):
    s = _script()
    argumentos = _preparar(tmp_path)
    resto = argumentos[2:]
    codigo, salida = _ejecutar(s, capsys, tmp_path / "e1", *resto)
    assert codigo == 2 and "entre 2 y 8" in salida.err
    codigo, salida = _ejecutar(s, capsys, tmp_path / "e1", tmp_path / "e1", *resto)
    assert codigo == 2 and "dos veces" in salida.err
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--observaciones", tmp_path / "checkpoints")
    assert codigo == 2 and "dos veces" in salida.err
    nueve = [a for i in range(9) for a in ("--checkpoints", tmp_path / f"k{i}")]
    codigo, salida = _ejecutar(s, capsys, *argumentos, *nueve)
    assert codigo == 2 and "como maximo 8" in salida.err
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--salida-json", tmp_path / "inventario" / "x.json")
    assert codigo == 2 and "fuera" in salida.err
    assert not (tmp_path / "inventario" / "x.json").exists()


def test_ae81_limite_agregado(tmp_path, capsys, monkeypatch):
    s = _script()
    argumentos = _preparar(tmp_path)
    monkeypatch.setattr(s.ac, "ARCHIVOS_AGREGADOS", 70)
    codigo, salida = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    assert codigo == 3 and json.loads(salida.out)["lectura"] == {"estado": "rechazada", "objeto": "entradas",
                                                                 "motivos": ["limite_agregado_superado"]}


def test_ae81_json_independiente_del_orden_de_los_argumentos_y_de_la_ruta(tmp_path, capsys):
    s = _script()
    c1, c2 = fpc.c1(), fpc.c2()
    argumentos = _preparar(tmp_path / "a")
    _, uno = _ejecutar(s, capsys, *argumentos, "--formato", "json")
    _, dos = _ejecutar(s, capsys, argumentos[1], argumentos[0], *argumentos[2:], "--formato", "json")
    assert uno.out == dos.out and uno.out.endswith("\n")
    # Mismas piezas repartidas en dos directorios de checkpoints y en otro orden.
    pc = importlib.import_module("app.application.ml.publicacion_constancias")
    partidos = _preparar(tmp_path / "b", checkpoints=[c2, c1])
    i = partidos.index("--checkpoints")
    partidos[i:i + 2] = ["--checkpoints", fp.escribir(tmp_path / "b" / "k2", pc.componer_checkpoints([c2])),
                         "--checkpoints", fp.escribir(tmp_path / "b" / "k1", pc.componer_checkpoints([c1]))]
    codigo, tres = _ejecutar(s, capsys, *partidos, "--formato", "json")
    informe = json.loads(tres.out)
    assert codigo == 0 and len(informe["conjuntos"]["checkpoints"]) == 2
    assert json.loads(uno.out)["checkpoints"] == informe["checkpoints"]


def test_ae81_demostracion_con_el_comando_real(tmp_path):
    demostracion = importlib.import_module("tests.demostracion_publicacion_constancias")
    resultados = demostracion.ejecutar(tmp_path)
    assert [(r["escenario"], r["codigo"]) for r in resultados] == [
        ("continuidad_valida", 0), ("cabeza_omitida", 4), ("predecesor_omitido", 5),
        ("sustitucion_de_checkpoint", 4), ("firma_o_clave_incorrecta", 4), ("bifurcacion_del_publicador", 1),
        ("monitores_con_contenidos_incompatibles", 6), ("observaciones_compatibles_de_una_progresion", 0),
        ("inventario_incompleto", 5), ("referencias_no_proporcionadas", 5)]
    assert all(r["correcto"] for r in resultados)


def test_ae81_script_de_solo_lectura_y_puro():
    texto = (BACKEND / "scripts" / "verificar_publicacion_constancias.py").read_text(encoding="utf-8")
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


def test_ae81_seleccion_windows_y_workflow():
    seleccion = (BACKEND / "tests" / "seleccion_windows.txt").read_text(encoding="utf-8").split()
    for prueba in ("tests/unit/ml/test_publicacion_constancias.py",
                   "tests/unit/test_verificar_publicacion_constancias_script.py",
                   "tests/unit/ml/test_constancias_auditoria.py",
                   "tests/unit/test_verificar_constancias_auditoria_script.py"):
        assert prueba in seleccion, prueba
    assert len(seleccion) == len(set(seleccion))
    workflow = (RAIZ / ".github" / "workflows" / "validacion-python-314.yml").read_text(encoding="utf-8")
    assert workflow.count("python -m tests.demostracion_publicacion_constancias") == 2
    assert workflow.count("python -m tests.demostracion_constancias_auditoria") == 2
    assert "--modo exigir" in workflow and "--modo permitir_omision" in workflow
    assert workflow.count("scripts/ci_contrastes_openssl.py") == 2
