"""Producto 3: comando de operacion diaria. Mismo caso de uso que la web;
codigos de salida distintos para exito, parcial, ejecucion activa y fallo."""
from __future__ import annotations

import ast
import contextlib
import io
import json
from pathlib import Path

import pytest

from scripts import operacion_diaria as cli
from tests.unit import fixtures_producto3 as f3

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def entorno(tmp_path):
    return f3.entorno(tmp_path)


def _comando(entorno, argv, operacion=None):
    operacion = operacion or entorno.operacion()

    @contextlib.contextmanager
    def repos():
        yield entorno.juegos, entorno.resultados

    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(argv, operacion_factory=lambda: operacion, repositorios=repos,
                          almacen_factory=lambda: entorno.almacen, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def test_exito_local_y_consulta(entorno):
    codigo, out, err = _comando(entorno, ["ejecutar", "--juego", "todos", "--modo", "local"])
    assert codigo == 0 and err == ""
    e = json.loads(out)
    assert e["estado"] == "exito" and e["origen"] == "comando" and entorno.importador.llamadas == []
    codigo, out, _ = _comando(entorno, ["consultar", "--id", e["id"]])
    assert codigo == 0 and json.loads(out)["id"] == e["id"]
    codigo, out, _ = _comando(entorno, ["ejecuciones", "--limite", "5"])
    assert codigo == 0 and json.loads(out)["ejecuciones"][0]["id"] == e["id"]


def test_parcial_no_devuelve_cero(entorno):
    entorno.importador.fallar["COLORLOTO"] = "origen inaccesible"
    codigo, out, err = _comando(entorno, ["ejecutar", "--juego", "todos", "--modo", "actualizar"])
    assert codigo == cli.EXIT_PARCIAL == 5
    assert json.loads(out)["juegos"]["COLORLOTO"]["estado"] == "fallo" and "COLORLOTO" in err


def test_fallo_total(entorno):
    entorno.base_caida.add("MILOTO")
    codigo, out, _ = _comando(entorno, ["ejecutar", "--juego", "MILOTO", "--modo", "local"])
    assert codigo == cli.EXIT_FALLO == 7 and json.loads(out)["estado"] == "fallo"


def test_ejecucion_ya_activa(entorno):
    op = entorno.operacion()
    inicio = op.iniciar(["BALOTO"], "local", "web")
    try:
        codigo, out, err = _comando(entorno, ["ejecutar", "--juego", "todos", "--modo", "local"], operacion=op)
        assert codigo == cli.EXIT_ACTIVA == 6 and json.loads(out)["activas"] == {"BALOTO": inicio.ejecucion["id"]}
        assert not any(entorno.almacen._directorio.rglob("*.json"))
    finally:
        inicio.cerrojos.liberar()


def test_uso_incorrecto_y_no_encontrada(entorno):
    assert _comando(entorno, ["ejecutar", "--juego", "QUINA", "--modo", "local"])[0] == 2
    assert _comando(entorno, ["ejecutar", "--juego", "BALOTO", "--modo", "sincronizar"])[0] == 2
    assert _comando(entorno, ["consultar", "--id", "20261001T000000Z-00000000"])[0] == 2


def test_rendimiento_json_y_recuperar(entorno):
    _comando(entorno, ["ejecutar", "--juego", "MILOTO", "--modo", "local"])
    codigo, out, _ = _comando(entorno, ["rendimiento", "--juego", "MILOTO", "--emision", "seguimiento"])
    datos = json.loads(out)
    assert codigo == 0 and datos["por_tipo"]["seguimiento"]["pendientes"] == 1
    codigo, out, _ = _comando(entorno, ["recuperar"])
    assert codigo == 0 and json.loads(out) == {"interrumpidas_marcadas": []}

    @contextlib.contextmanager
    def caida():
        raise ConnectionError("connection to server failed: Connection refused")
        yield  # pragma: no cover

    errores = io.StringIO()
    assert cli.ejecutar(["rendimiento", "--juego", "MILOTO"], repositorios=caida, almacen_factory=lambda: entorno.almacen,
                        salida=io.StringIO(), errores=errores) == cli.EXIT_CONEXION
    assert "Sin conexion" in errores.getvalue()


def test_el_comando_reutiliza_el_caso_de_uso_y_no_tiene_programador():
    texto = (RAIZ / "scripts" / "operacion_diaria.py").read_text(encoding="utf-8")
    arbol = ast.parse(texto)
    importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "get_operacion_diaria" in importados  # la misma fabrica que la web
    assert "schedule" not in texto and "while True" not in texto and "sleep(" not in texto


def test_demostracion_sintetica_completa(capsys):
    from tests import demostracion_producto3 as demo
    assert demo.main() == 0
    salida = capsys.readouterr().out
    assert salida.count("[OK]") == 6 and "[FALLO]" not in salida and "ninguna cifra corresponde" in salida


def test_variables_heredadas_de_producto2_y_overrides_de_producto3(tmp_path, monkeypatch):
    """La sesion de PowerShell del operador puede traer las rutas de Producto 2.
    Tras fijar las de Producto 3, la configuracion resuelve solo esas y las
    escrituras van al destino aislado; Producto 2 no se toca."""
    from app.api import dependencies as dep
    from app.core.config import get_settings

    p2 = tmp_path / "loteria-predictor-producto2" / "backend" / "storage"
    p3 = tmp_path / "loteria-predictor-producto3" / "backend" / "storage"
    (p2 / "pronosticos" / "MILOTO").mkdir(parents=True)
    testigo = p2 / "pronosticos" / "MILOTO" / ("85-" + "0" * 64 + ".json")
    testigo.write_bytes(b'{"de producto 2": true}')
    antes = {p: p.read_bytes() for p in p2.rglob("*") if p.is_file()}
    monkeypatch.setenv("DIRECTORIO_PRONOSTICOS_EXPERIMENTALES", str(p2 / "pronosticos"))  # heredada
    monkeypatch.setenv("DIRECTORIO_OPERACION", str(p2 / "operacion"))
    monkeypatch.setenv("DIRECTORIO_PRONOSTICOS_EXPERIMENTALES", str(p3 / "pronosticos"))  # override de Producto 3
    monkeypatch.setenv("DIRECTORIO_OPERACION", str(p3 / "operacion"))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://usuario:secreto@localhost/base")
    get_settings.cache_clear()
    try:
        salida = io.StringIO()
        assert cli.ejecutar(["rutas"], salida=salida, errores=io.StringIO()) == 0
        rutas = json.loads(salida.getvalue())
        assert rutas["directorio_pronosticos_experimentales"] == str((p3 / "pronosticos").resolve())
        assert rutas["directorio_operacion"] == str((p3 / "operacion").resolve())
        assert "secreto" not in salida.getvalue() and "postgresql" not in salida.getvalue()
        operacion = dep.get_operacion_diaria()
        e = f3.entorno(tmp_path / "datos")
        operacion._abrir = e.abrir  # repositorios sinteticos; almacen, registro y cerrojos de la configuracion
        final = operacion.ejecutar_ahora(["MILOTO"], "local", "prueba")
        assert final["estado"] == "exito"
        assert list((p3 / "pronosticos" / "MILOTO").glob("*.json"))
        assert (p3 / "operacion" / "ejecuciones" / f"{final['id']}.json").is_file()
        assert {p: p.read_bytes() for p in p2.rglob("*") if p.is_file()} == antes  # Producto 2 intacto
        assert not (p2 / "operacion").exists()
    finally:
        get_settings.cache_clear()
