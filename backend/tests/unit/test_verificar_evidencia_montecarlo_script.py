"""Tests de `scripts/verificar_evidencia_montecarlo.py` -Etapa AE-50,
validada: CLI local, sin conexion y de solo lectura que valida el
formato y la coherencia interna de evidencias JSON de AE-49. Archivos
sinteticos en `tmp_path`: nunca PostgreSQL ni evidencia real."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import verificacion_evidencia_montecarlo as verif
from scripts import verificar_evidencia_montecarlo as cli
from scripts.comparacion_estado_prediccion import serializar_reporte
from tests.unit.simulaciones import evidencia_sintetica as ev

RAIZ_BACKEND = Path(cli.__file__).resolve().parents[1]


def _escribir(tmp_path, nombre, contenido: bytes) -> Path:
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    return ruta


def _huella_y_mtime(ruta: Path):
    return hashlib.sha256(ruta.read_bytes()).hexdigest(), os.stat(ruta).st_mtime_ns


def _informe_esperado(*contenidos: bytes) -> bytes:
    resumenes = [verif.validar_evidencia(c) for c in contenidos]
    if len(contenidos) == 2:
        assert contenidos[0] == contenidos[1]
        return serializar_reporte(verif.construir_informe(resumenes, bytes_identicos=True))
    return serializar_reporte(verif.construir_informe(resumenes))


def _invalida() -> bytes:
    reporte = ev.copia(ev.reporte_valido())
    reporte["parametros"]["semilla"] = 1
    return ev.recodificar(reporte)


def _incoherente() -> bytes:
    reporte = ev.copia(ev.reporte_valido())
    reporte["juegos"][0]["estadisticas"][0]["p_valor_empirico"] = 0.003
    return ev.recodificar(reporte)


# ---------------------------------------------------------------------------
# Un archivo
# ---------------------------------------------------------------------------

def test_un_archivo_valido_codigo_0(tmp_path, capsysbinary):
    ruta = _escribir(tmp_path, "evidencia.json", ev.evidencia_valida())
    antes = _huella_y_mtime(ruta)
    assert cli.main([str(ruta)]) == cli.EXIT_VALIDA == 0
    salida = capsysbinary.readouterr()
    assert salida.out == _informe_esperado(ev.evidencia_valida())
    assert salida.err == b""
    informe = json.loads(salida.out)
    assert informe["resultado"] == "formato_y_coherencia_interna_validos"
    assert informe["comparacion_de_archivos"] == "no_aplica"
    assert _huella_y_mtime(ruta) == antes


@pytest.mark.parametrize("contenido, codigo", [
    (b"{no es json", 3), (b"\xff\xfe", 3), (b"", 3),
    (None, 4),  # parametros distintos de los fijos de AE-49
    ("incoherente", 5),
])
def test_un_archivo_invalido_devuelve_su_codigo_sin_stdout(tmp_path, capsysbinary, contenido, codigo):
    if contenido is None:
        contenido = _invalida()
    elif contenido == "incoherente":
        contenido = _incoherente()
    ruta = _escribir(tmp_path, "evidencia.json", contenido)
    antes = _huella_y_mtime(ruta)
    assert cli.main([str(ruta)]) == codigo
    salida = capsysbinary.readouterr()
    assert salida.out == b"" and b"ERROR" in salida.err
    assert _huella_y_mtime(ruta) == antes


def test_archivo_inexistente_codigo_3(tmp_path, capsysbinary):
    assert cli.main([str(tmp_path / "no-existe.json")]) == cli.EXIT_ILEGIBLE == 3
    assert capsysbinary.readouterr().out == b""


def test_constante_nan_codigo_3(tmp_path, capsysbinary):
    contenido = ev.evidencia_valida().replace(b'"media_simulada": 38.01', b'"media_simulada": NaN', 1)
    assert cli.main([str(_escribir(tmp_path, "e.json", contenido))]) == 3
    assert capsysbinary.readouterr().out == b""


# ---------------------------------------------------------------------------
# Dos archivos: cada uno se valida por separado antes de compararlos
# ---------------------------------------------------------------------------

def test_dos_archivos_identicos_codigo_0(tmp_path, capsysbinary):
    a = _escribir(tmp_path, "a.json", ev.evidencia_valida())
    b = _escribir(tmp_path, "b.json", ev.evidencia_valida())
    assert cli.main([str(a), str(b)]) == 0
    salida = capsysbinary.readouterr()
    assert salida.out == _informe_esperado(ev.evidencia_valida(), ev.evidencia_valida())
    assert json.loads(salida.out)["comparacion_de_archivos"] == "archivos_identicos"


def test_dos_archivos_validos_que_difieren_codigo_6(tmp_path, capsysbinary):
    # Dos JSON canonicos y validos que difieren solo en un campo permitido.
    a = _escribir(tmp_path, "a.json", ev.evidencia_valida(revision="0006"))
    b = _escribir(tmp_path, "b.json", ev.evidencia_valida(revision="0007"))
    verif.validar_evidencia(a.read_bytes())
    verif.validar_evidencia(b.read_bytes())
    antes = (_huella_y_mtime(a), _huella_y_mtime(b))
    assert cli.main([str(a), str(b)]) == cli.EXIT_ARCHIVOS_DISTINTOS == 6
    salida = capsysbinary.readouterr()
    assert salida.out == b"" and b"ERROR" in salida.err
    assert (_huella_y_mtime(a), _huella_y_mtime(b)) == antes


def test_regresion_bytes_distintos_con_huella_forzada_igual_codigo_6(tmp_path, capsysbinary, monkeypatch):
    # Ambos archivos son canonicos y validos pero sus bytes difieren. Los
    # resumenes que ve el CLI se alteran para presentar el MISMO SHA-256:
    # la decision debe salir de comparar los bytes reales, no las huellas.
    a = _escribir(tmp_path, "a.json", ev.evidencia_valida(revision="0006"))
    b = _escribir(tmp_path, "b.json", ev.evidencia_valida(revision="0007"))
    validar_real = cli.validar_evidencia

    def validar_con_huella_forzada(contenido):
        resumen = validar_real(contenido)
        return {**resumen, "sha256": "0" * 64}

    monkeypatch.setattr(cli, "validar_evidencia", validar_con_huella_forzada)
    antes = (_huella_y_mtime(a), _huella_y_mtime(b))
    assert cli.main([str(a), str(b)]) == cli.EXIT_ARCHIVOS_DISTINTOS == 6
    salida = capsysbinary.readouterr()
    assert salida.out == b"" and b"ERROR" in salida.err
    assert (_huella_y_mtime(a), _huella_y_mtime(b)) == antes


def test_bytes_identicos_con_huella_forzada_distinta_codigo_0(tmp_path, capsysbinary, monkeypatch):
    # Caso simetrico: bytes identicos se informan como identicos aunque las
    # huellas de los resumenes se alteren; el SHA-256 es solo informativo.
    a = _escribir(tmp_path, "a.json", ev.evidencia_valida())
    b = _escribir(tmp_path, "b.json", ev.evidencia_valida())
    validar_real = cli.validar_evidencia
    huellas = iter(["1" * 64, "2" * 64])

    def validar_con_huella_forzada(contenido):
        return {**validar_real(contenido), "sha256": next(huellas)}

    monkeypatch.setattr(cli, "validar_evidencia", validar_con_huella_forzada)
    assert cli.main([str(a), str(b)]) == 0
    informe = json.loads(capsysbinary.readouterr().out)
    assert informe["comparacion_de_archivos"] == "archivos_identicos"


@pytest.mark.parametrize("primero, segundo, codigo", [
    ("ilegible", "valida", 3),
    ("valida", "invalida", 4),
    ("valida", "incoherente", 5),
    ("invalida", "incoherente", 4),
])
def test_con_dos_rutas_gana_el_fallo_individual(tmp_path, capsysbinary, primero, segundo, codigo):
    contenidos = {"valida": ev.evidencia_valida(), "ilegible": b"{roto", "invalida": _invalida(),
                  "incoherente": _incoherente()}
    a = _escribir(tmp_path, "a.json", contenidos[primero])
    b = _escribir(tmp_path, "b.json", contenidos[segundo])
    assert cli.main([str(a), str(b)]) == codigo
    assert capsysbinary.readouterr().out == b""


def test_un_byte_distinto_no_es_codigo_6_si_invalida_el_archivo(tmp_path, capsysbinary):
    original = ev.evidencia_valida()
    alterado = original.replace(b'"esquema": "simulacion', b'"esquema": "simulaciox', 1)
    assert len(alterado) == len(original) and alterado != original
    a = _escribir(tmp_path, "a.json", original)
    b = _escribir(tmp_path, "b.json", alterado)
    assert cli.main([str(a), str(b)]) in (3, 4, 5)
    assert capsysbinary.readouterr().out == b""


# ---------------------------------------------------------------------------
# Argumentos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("argumentos", [[], ["a", "b", "c"], ["--semilla", "1"], ["--salida", "x.json"]])
def test_argumentos_invalidos_codigo_2(capsysbinary, argumentos):
    assert cli.main(argumentos) == cli.EXIT_ARGUMENTOS_INVALIDOS == 2
    salida = capsysbinary.readouterr()
    assert salida.out == b"" and b"ERROR" in salida.err


def test_codigos_de_salida():
    assert (cli.EXIT_VALIDA, cli.EXIT_FALLO_INESPERADO, cli.EXIT_ARGUMENTOS_INVALIDOS, cli.EXIT_ILEGIBLE,
            cli.EXIT_INVALIDA, cli.EXIT_INCOHERENTE, cli.EXIT_ARCHIVOS_DISTINTOS) == tuple(range(7))


# ---------------------------------------------------------------------------
# Proceso real: bytes de stdout
# ---------------------------------------------------------------------------

def test_proceso_hijo_stdout_exacto(tmp_path):
    a = _escribir(tmp_path, "a.json", ev.evidencia_valida())
    b = _escribir(tmp_path, "b.json", ev.evidencia_valida())
    proceso = subprocess.run(
        [sys.executable, "-m", "scripts.verificar_evidencia_montecarlo", str(a), str(b)],
        cwd=RAIZ_BACKEND, env={**os.environ, "PYTHONPATH": str(RAIZ_BACKEND)}, capture_output=True, timeout=120,
    )
    assert proceso.returncode == 0, proceso.stderr
    assert proceso.stdout == _informe_esperado(ev.evidencia_valida(), ev.evidencia_valida())
    assert b"\r" not in proceso.stdout and proceso.stderr == b""


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------

def test_cli_sin_bd_ni_escritura_con_guarda_main():
    texto = Path(cli.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in texto
    for prohibido in ("sqlalchemy", "engine", "connect(", "commit(", '"w"', '"wb"', '"a"', "write_bytes",
                      "app.application.ml", "resolver_estado_prediccion", "diagnostico_bloqueo",
                      "diagnosticar_estado_prediccion"):
        assert prohibido not in texto, prohibido


def test_nada_en_app_web_ni_plantillas_menciona_ae50():
    raiz = RAIZ_BACKEND / "app"
    for ruta in [*raiz.rglob("*.py"), *(raiz / "templates").rglob("*.html")]:
        contenido = ruta.read_text(encoding="utf-8")
        for nombre in ("verificacion_evidencia_montecarlo", "verificar_evidencia_montecarlo"):
            assert nombre not in contenido, (ruta, nombre)
