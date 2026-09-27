"""Tests de `scripts/explorar_inferencia_prospectiva.py` -Etapa AE-54,
validada: CLI sin base de datos que ejecuta el banco exploratorio con
parametros fijos. Las pruebas inyectan parametros minimos sustituyendo
la constante del modulo; nunca ejecutan la exploracion completa."""
from __future__ import annotations

import dataclasses
import hashlib
import os
from pathlib import Path

import pytest

from app.application.simulaciones import exploracion_inferencia_prospectiva as ex
from scripts import explorar_inferencia_prospectiva as cli
from scripts.comparacion_estado_prediccion import serializar_reporte

REDUCIDOS = dataclasses.replace(ex.PARAMETROS_AE54, n=12, b=39, r_e=2, r_l=1, calentamiento_l=25)


@pytest.fixture
def reducidos(monkeypatch):
    monkeypatch.setattr(ex, "PARAMETROS_AE54", REDUCIDOS)
    return serializar_reporte(ex.ejecutar_exploracion(REDUCIDOS))


def test_stdout_son_los_bytes_del_reporte(reducidos, capsysbinary):
    assert cli.main([]) == cli.EXIT_OK == 0
    salida = capsysbinary.readouterr()
    assert salida.out == reducidos
    assert b"duracion_s=" in salida.err and b"exploratorio" in salida.err


def test_salida_nueva_con_los_mismos_bytes(reducidos, tmp_path, capsysbinary):
    destino = tmp_path / "exploracion.json"
    assert cli.main(["--salida", str(destino)]) == 0
    salida = capsysbinary.readouterr()
    assert destino.read_bytes() == salida.out == reducidos
    assert hashlib.sha256(reducidos).hexdigest().encode() in salida.err


def test_destino_existente_codigo_9_sin_ejecutar(reducidos, tmp_path, capsysbinary, monkeypatch):
    destino = tmp_path / "previo.json"
    destino.write_bytes(b"previo")
    antes = (destino.read_bytes(), os.stat(destino).st_mtime_ns)
    monkeypatch.setattr(ex, "ejecutar_exploracion", lambda p: pytest.fail("no debe ejecutar"))
    assert cli.main(["--salida", str(destino)]) == cli.EXIT_RUTA_SALIDA_NO_PERMITIDA == 9
    assert (destino.read_bytes(), os.stat(destino).st_mtime_ns) == antes
    assert capsysbinary.readouterr().out == b""


def test_destino_que_aparece_durante_la_ejecucion_codigo_8(reducidos, tmp_path, capsysbinary, monkeypatch):
    destino = tmp_path / "carrera.json"
    real = ex.ejecutar_exploracion

    def crea_destino(parametros):
        destino.write_bytes(b"otro proceso")
        return real(parametros)

    monkeypatch.setattr(ex, "ejecutar_exploracion", crea_destino)
    assert cli.main(["--salida", str(destino)]) == cli.EXIT_FALLO_ESCRITURA == 8
    assert destino.read_bytes() == b"otro proceso"
    assert capsysbinary.readouterr().out == b""


@pytest.mark.parametrize("argumentos", [["--semilla", "1"], ["--r", "10"], ["extra"], ["--salida"]])
def test_argumentos_invalidos_codigo_2(argumentos, capsysbinary, monkeypatch):
    monkeypatch.setattr(ex, "ejecutar_exploracion", lambda p: pytest.fail("no debe ejecutar"))
    assert cli.main(argumentos) == cli.EXIT_ARGUMENTOS_INVALIDOS == 2
    assert capsysbinary.readouterr().out == b""


def test_fallo_inesperado_codigo_1(capsysbinary, monkeypatch):
    def falla(parametros):
        raise RuntimeError("fallo sintetico")

    monkeypatch.setattr(ex, "ejecutar_exploracion", falla)
    assert cli.main([]) == cli.EXIT_FALLO_INESPERADO == 1
    assert capsysbinary.readouterr().out == b""


def test_estructura_sin_base_de_datos():
    import ast

    texto = Path(cli.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in texto
    for prohibido in ("sqlalchemy", "engine", "Session", "connect(", "commit("):
        assert prohibido not in texto, prohibido
    modulos = {n.module for n in ast.walk(ast.parse(texto)) if isinstance(n, ast.ImportFrom)}
    assert modulos == {"__future__", "app.application.simulaciones", "scripts.comparacion_estado_prediccion"}, modulos
