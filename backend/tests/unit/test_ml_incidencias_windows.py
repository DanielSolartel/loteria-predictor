"""Regresiones de rutas de evidencia y diagnóstico numérico (portables)."""
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import shutil
import zipfile

import pytest

from tests import ejecutar_ml_windows as supervisor
from tests.unit.test_fase4_publicacion_registro import _medicion
from tests.unit.test_producto5_rutas import _presupuesto

DESCARGAS = PureWindowsPath(r"C:\Users\danie\Downloads\ml-cierre-v2-2dd5878b63884dc98421c3ad796a86a3\ml-cierre-evidencia-c7863fc6cef140c7945e7d28580ef430\validacion-windows")
CASOS = (
    "test_un_bloqueo_que_no_se_suelta_agota_un_limite_acotado_y_falla_sin_publicar",
    "test_los_errores_sin_bloqueo_de_windows_se_propagan_al_primer_intento_error0_",
    "test_los_errores_sin_bloqueo_de_windows_se_propagan_al_primer_intento_error1_",
    "test_los_errores_sin_bloqueo_de_windows_se_propagan_al_primer_intento_error2_",
    "test_concurrencia_real_lectores_en_hilos_y_en_otro_proceso_mientras_se_publica",
    "test_handle_de_otro_proceso_distingue_lector_cooperante_de_apertura_ordinaria_cooperante_",
    "test_handle_de_otro_proceso_distingue_lector_cooperante_de_apertura_ordinaria_ordinario_",
)


def _inventario_textual(codigo):
    """El contrato de texto admite CRLF sin cambiar los bytes de la fuente."""
    return [{"ruta": p.relative_to(codigo).as_posix(), "tipo": "texto",
             "despues": hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
            for p in sorted(codigo.rglob("*.py"))]


@pytest.mark.parametrize("salto", ["\n", "\r\n"], ids=["LF", "CRLF"])
@pytest.mark.parametrize("estado", ["canonico", "hash_crudo", "alterado"])
def test_espejo_textual_conserva_bytes_y_rechaza_cambios(tmp_path, salto, estado):
    codigo = tmp_path / "codigo"
    codigo.mkdir()
    origen = codigo / "fixture.py"
    contenido = ("# Texto público: ñ.\nvalor = 1\n").replace("\n", salto).encode("utf-8")
    origen.write_bytes(contenido)
    filas = _inventario_textual(codigo)
    if estado == "hash_crudo":
        filas[0]["despues"] = hashlib.sha256(contenido).hexdigest()
    elif estado == "alterado":
        origen.write_bytes(contenido.replace(b"valor = 1", b"valor = 2"))
    originales = origen.read_bytes()
    destino = tmp_path / "espejo"
    if estado == "alterado" or (estado == "hash_crudo" and salto == "\r\n"):
        with pytest.raises(ValueError, match="El código no coincide con el manifiesto"):
            supervisor._preparar_espejo(codigo, {"inventario_publico": filas}, destino)
        assert not destino.exists()
    else:
        assert supervisor._preparar_espejo(codigo, {"inventario_publico": filas}, destino) == 1
        assert (destino / "fixture.py").read_bytes() == originales
    assert origen.read_bytes() == originales


@pytest.mark.parametrize("caso", CASOS)
def test_mediciones_validas_bajo_descargas_largas(tmp_path, monkeypatch, caso):
    raiz = tmp_path / "publicacion-fase4"
    p = _presupuesto(monkeypatch, raiz, raiz)
    p.desplazamiento = len(str(DESCARGAS / "publicacion-fase4")) - len(str(raiz))
    monkeypatch.setenv("FASE4_EVIDENCIA", str(raiz))
    node = "tests/unit/test_fase4_publicacion_registro.py::" + caso + " (setup)"
    monkeypatch.setenv("PYTEST_CURRENT_TEST", node)
    nombre = "soporte_publicacion_" + caso
    datos = {"api": "real", "completo": {"flags": [22, 3], "observaciones": [1, 2, 3]}}
    _medicion(nombre, datos)
    archivo, = raiz.iterdir()
    assert p.longitud(archivo) <= 259 and not p.rechazadas
    leido = json.loads(archivo.read_text())
    assert leido.pop("_medicion") == {"nombre": nombre, "prueba": node}
    assert leido == datos


def test_mediciones_se_archivan_completas_antes_de_limpieza(tmp_path, monkeypatch):
    temporal = tmp_path / "m 12345678"
    m = supervisor.rutas_temporales(temporal)["mediciones"]
    monkeypatch.setenv("FASE4_EVIDENCIA", str(m))
    for caso in CASOS:
        _medicion(caso, {"caso": caso, "datos": list(range(25))})
    originales = {p.name: p.read_bytes() for p in m.iterdir()}
    evidencia = tmp_path / "Downloads" / "extraccion larga" / "validacion-windows"
    evidencia.mkdir(parents=True)
    resultado = supervisor._conservar_mediciones(m, evidencia)
    assert len(str(DESCARGAS / resultado["archivo"])) <= 259
    assert resultado["cantidad"] == len(CASOS)
    with zipfile.ZipFile(evidencia / resultado["archivo"]) as z:
        assert z.testzip() is None
        assert {n: z.read(n) for n in z.namelist()} == originales
        for e in resultado["archivos"]:
            assert hashlib.sha256(z.read(e["ruta"])).hexdigest() == e["sha256"]


def test_matriz_numerica_real_en_proceso_aislado(tmp_path):
    salida = tmp_path / "matriz.json"
    env_antes = dict(os.environ)
    p = subprocess.run([sys.executable, "-m", "tests.diagnostico_ml_numerico", "--salida", str(salida)],
                       cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    d = json.loads(salida.read_text())
    assert d["repeticion_2_hilos_exacta"]
    assert set(d["ajustes"]) == {"1a", "2a", "2b"}
    assert set(d["inferencias"]) == {k + "-" + str(h) for k in ("1a", "2a", "2b") for h in (1, 2)}
    assert d["paquetes"]["xgboost-cpu"]
    assert dict(os.environ) == env_antes


@pytest.mark.parametrize("fallo_archivo", [False, True])
def test_supervisor_conserva_mediciones_al_fallar_pytest(tmp_path, monkeypatch, fallo_archivo):
    codigo = tmp_path / "codigo"
    pruebas = ("test_fase4_publicacion_registro", "test_producto4_aislamiento", "test_ml_incidencias_windows",
               "test_ml_registro", "test_ml_cinco_flujo", "test_ml_recursos_publicacion")
    for i, nombre in enumerate(pruebas):
        p = codigo / "backend/tests/unit" / (nombre + ".py")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("""import os
from pathlib import Path
def test_fallo_controlado():
    d = Path(os.environ['FASE4_EVIDENCIA']); d.mkdir(parents=True)
    (d / 'medicion.json').write_bytes(b'{"medicion_completa":[1,2,3]}')
    assert False, 'fallo deliberado del ensayo aislado'
""" if i == 0 else "# Fixture sin pruebas adicionales.\n", encoding="utf-8")
    # Doble explícito del diagnóstico, solo para este ensayo del supervisor.
    (codigo / "backend/tests/__init__.py").write_text("", encoding="utf-8")
    (codigo / "backend/tests/diagnostico_ml_numerico.py").write_text(
        "print('doble del diagnostico: ensayo de error de pytest')\n", encoding="utf-8")
    filas = _inventario_textual(codigo)
    mf = tmp_path / "manifiesto.json"
    mf.write_text(json.dumps({"version": "ml-cinco-familias-1", "base": "90e6ab06b2a188fde9416fb0aac9e7366b7b04a6",
                              "inventario_publico": filas}), encoding="utf-8")
    if fallo_archivo:
        def fallar(*args):
            raise OSError("archivo de evidencia bloqueado deliberadamente")
        monkeypatch.setattr(supervisor, "_conservar_mediciones", fallar)
    antes = dict(os.environ)
    evidencia = tmp_path / "Downloads" / "extraccion larga" / "validacion-windows"
    assert supervisor.validar(codigo, mf, evidencia, 90, "focal") == 1
    r = json.loads((evidencia / "resultado-validacion.json").read_text(encoding="utf-8"))
    assert "Falló pytest-focal" in r["error"] and r["junit"]["fallidas"] == 1
    assert [p["nombre"] for p in r["pasos"]] == ["diagnostico-numerico", "pytest-focal"]
    assert r["pasos"][0]["codigo"] == 0 and dict(os.environ) == antes
    if fallo_archivo:
        temporal = Path(r["temporal_pendiente"])
        assert (temporal / "e/medicion.json").read_bytes() == b'{"medicion_completa":[1,2,3]}'
        assert "bloqueado" in r["error_mediciones"]
        shutil.rmtree(temporal)
    else:
        with zipfile.ZipFile(evidencia / r["mediciones"]["archivo"]) as z:
            assert z.read("medicion.json") == b'{"medicion_completa":[1,2,3]}'


def _diagnostico_con_estimadores_simulados(reproducible, modulo="tests.diagnostico_ml_numerico"):
    """Solo duplica el ajustador; analizar/main y sus seis inferencias son reales.

    No acredita ML real: fuerza el camino negativo de conservación de evidencia
    sin depender de que una biblioteca numérica varíe en una CPU determinada.
    """
    return '''import json
from pathlib import Path
import runpy
import sys
import numpy as np
from app.application.ml import laboratorio_modelos as lm

traza = {"ajustes": 0, "predict": 0, "predecir": 0}
class EstimadorSimulado:
    def __init__(self, peso):
        self.peso = peso
    def to_dict(self):
        return {"contenido": {"pesos": [[self.peso]], "sesgos": [0.25]},
                "preparacion": {"columnas": ["variable_sintetica"], "media": [0.5]}}
    def predict(self, X):
        traza["predict"] += 1
        return np.full((len(X), 1), self.peso, dtype=float)
class AjusteSimulado:
    def __init__(self, peso):
        self.estimador = EstimadorSimulado(peso)
    def predecir(self, filas):
        traza["predecir"] += 1
        return np.full((len(filas.X), 1), self.estimador.peso / 10.0, dtype=float)
def ajustar_simulado(*args, **kwargs):
    traza["ajustes"] += 1
    peso = 2.0 if traza["ajustes"] == 3 and not REPRODUCIBLE else 1.0
    return AjusteSimulado(peso)
lm.ajustar_candidato = ajustar_simulado
salida = Path(sys.argv[sys.argv.index("--salida") + 1])
try:
    runpy.run_module(MODULO_REAL, run_name="__main__")
finally:
    salida.with_suffix(".dobles.json").write_text(json.dumps(traza), encoding="utf-8")
'''.replace("REPRODUCIBLE", repr(reproducible)).replace("MODULO_REAL", repr(modulo))


def _comprobar_matriz_simulada(salida, reproducible):
    matriz = json.loads(salida.read_text(encoding="utf-8"))
    assert matriz["repeticion_2_hilos_exacta"] is reproducible
    assert set(matriz["ajustes"]) == {"1a", "2a", "2b"}
    assert set(matriz["inferencias"]) == {k + "-" + str(h) for k in ("1a", "2a", "2b") for h in (1, 2)}
    for etiqueta, ajuste in matriz["ajustes"].items():
        peso = 2.0 if etiqueta == "2b" and not reproducible else 1.0
        assert ajuste["estado"]["contenido"] == {"pesos": [[peso]], "sesgos": [0.25]}
        assert ajuste["estado"]["preparacion"] == {"columnas": ["variable_sintetica"], "media": [0.5]}
        for campo, estado in (("sha256_pesos", "contenido"), ("sha256_preparacion", "preparacion")):
            contenido = json.dumps(ajuste["estado"][estado], sort_keys=True, allow_nan=False).encode()
            assert ajuste[campo] == hashlib.sha256(contenido).hexdigest()
        for hilos in (1, 2):
            inferencia = matriz["inferencias"][etiqueta + "-" + str(hilos)]
            assert inferencia["crudas"] and inferencia["probabilidades"]
            assert all(fila == [peso] for fila in inferencia["crudas"])
            assert all(fila == [peso / 10.0] for fila in inferencia["probabilidades"])
    assert json.loads(salida.with_suffix(".dobles.json").read_text(encoding="utf-8")) == {
        "ajustes": 3, "predict": 6, "predecir": 6,
    }
    return matriz


@pytest.mark.parametrize("reproducible", [False, True])
def test_diagnostico_guarda_matriz_antes_del_resultado_cli(tmp_path, reproducible):
    backend = Path(__file__).resolve().parents[2]
    runner = tmp_path / "doble.py"
    runner.write_text(_diagnostico_con_estimadores_simulados(reproducible), encoding="utf-8")
    salida = tmp_path / "matriz.json"
    entorno = os.environ.copy()
    entorno["PYTHONPATH"] = str(backend)
    antes = dict(os.environ)
    proceso = subprocess.run([sys.executable, str(runner), "--salida", str(salida)], cwd=backend,
                             env=entorno, capture_output=True, text=True, timeout=90)
    assert proceso.returncode == (0 if reproducible else 1), proceso.stdout + proceso.stderr
    _comprobar_matriz_simulada(salida, reproducible)
    assert dict(os.environ) == antes
    assert '"repeticion_2_hilos_exacta": ' + str(reproducible).lower() in proceso.stdout
    if not reproducible:
        assert "dos hilos" in proceso.stderr


def test_supervisor_retiene_matriz_no_reproducible_y_detiene_la_focal(tmp_path, monkeypatch):
    backend = Path(__file__).resolve().parents[2]
    codigo = tmp_path / "c"
    # Copia pública mínima, sin datos ni configuración. El módulo auxiliar
    # conserva íntegro el analizar/main real; el wrapper solo instala el doble.
    for origen in (backend / "app").rglob("*.py"):
        destino = codigo / "backend" / origen.relative_to(backend)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(origen.read_bytes())
    pruebas = codigo / "backend/tests"
    (pruebas / "unit").mkdir(parents=True)
    for nombre in ("__init__.py", "unit/__init__.py", "unit/fixtures_producto4.py",
                   "unit/fixtures_producto1.py", "unit/fakes.py"):
        origen = backend / "tests" / nombre
        (pruebas / nombre).write_bytes(origen.read_bytes())
    (pruebas / "_diagnostico_real.py").write_bytes((backend / "tests/diagnostico_ml_numerico.py").read_bytes())
    (pruebas / "diagnostico_ml_numerico.py").write_text(
        _diagnostico_con_estimadores_simulados(False, "tests._diagnostico_real"), encoding="utf-8")
    filas = _inventario_textual(codigo)
    manifiesto = tmp_path / "mf.json"
    manifiesto.write_text(json.dumps({"version": "ml-cinco-familias-1",
        "base": "90e6ab06b2a188fde9416fb0aac9e7366b7b04a6", "inventario_publico": filas}), encoding="utf-8")
    temporales = []
    preparar = supervisor._preparar_espejo
    def registrar_espejo(worktree, mf, destino):
        temporales.append(destino.parent)
        return preparar(worktree, mf, destino)
    monkeypatch.setattr(supervisor, "_preparar_espejo", registrar_espejo)
    evidencia = tmp_path / "e"
    antes = dict(os.environ)
    assert supervisor.validar(codigo, manifiesto, evidencia, 90, "focal") == 1
    resultado = json.loads((evidencia / "resultado-validacion.json").read_text(encoding="utf-8"))
    assert resultado["estado"] == "error" and resultado["codigo"] == 1
    assert "Falló diagnostico-numerico" in resultado["error"]
    assert [p["nombre"] for p in resultado["pasos"]] == ["diagnostico-numerico"]
    paso, = resultado["pasos"]
    assert paso["codigo"] == 1 and not paso["plazo_agotado"]
    _comprobar_matriz_simulada(evidencia / "matriz-numerica.json", False)
    assert "dos hilos" in (evidencia / paso["log"]).read_text(encoding="utf-8")
    assert not (evidencia / "pytest-focal.log").exists()
    assert not (evidencia / "resultados-windows-focal.xml").exists()
    assert not (evidencia / "pip-check.log").exists()
    assert "temporal_pendiente" not in resultado and not resultado["avisos_limpieza"]
    assert len(temporales) == 1 and not temporales[0].exists()
    with zipfile.ZipFile(evidencia / resultado["mediciones"]["archivo"]) as z:
        assert z.testzip() is None
    assert dict(os.environ) == antes


@pytest.mark.parametrize("escenario", ["pytest", "archivo", "matriz"])
def test_supervisor_con_fixtures_crlf(tmp_path, monkeypatch, escenario):
    """Repite los tres caminos con CRLF solo en sus archivos sintéticos .py."""
    escribir_texto = Path.write_text
    escritas = []

    def escribir_crlf(ruta, contenido, encoding=None, errors=None, newline=None):
        if ruta.suffix == ".py" and ruta.is_relative_to(tmp_path):
            newline = "\r\n"
            escritas.append(ruta)
        return escribir_texto(ruta, contenido, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "write_text", escribir_crlf)
    if escenario == "matriz":
        test_supervisor_retiene_matriz_no_reproducible_y_detiene_la_focal(tmp_path, monkeypatch)
    else:
        test_supervisor_conserva_mediciones_al_fallar_pytest(tmp_path, monkeypatch, escenario == "archivo")
    assert escritas
    for ruta in escritas:
        contenido = ruta.read_bytes()
        assert b"\n" not in contenido.replace(b"\r\n", b"")
