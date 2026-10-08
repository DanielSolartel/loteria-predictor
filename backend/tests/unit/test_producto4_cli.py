"""Producto 4: comando `python -m scripts.laboratorio_modelos` (JSON
parseable, codigos documentados, rutas sin credenciales y aislamiento frente
a variables heredadas de Productos 2 y 3)."""
from __future__ import annotations

import io
import json

import pytest

from scripts import laboratorio_modelos as cli
from tests.unit import fixtures_producto4 as f4


@pytest.fixture
def entorno(tmp_path):
    return f4.entorno(tmp_path)


def _corre(entorno, *argumentos):
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(list(argumentos), laboratorio_factory=entorno.laboratorio, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def test_recorrido_y_codigos(entorno):
    codigo, salida, _ = _corre(entorno, "catalogo")
    assert codigo == 0 and set(json.loads(salida)["juegos"]) == {"BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"}
    codigo, salida, errores = _corre(entorno, "comparar", "--juego", "MILOTO", "--bloques", "1", "--perfil", "reducido")
    final = json.loads(salida)
    assert codigo == 0 and final["estado"] == "exito" and "Comparando" in errores  # avisos fuera de stdout
    clave = final["juegos"]["MILOTO"]["experimento"]
    codigo, salida, _ = _corre(entorno, "generar", "--experimento", clave, "--modelo", "logistica_regularizada")
    pronostico = json.loads(salida)
    assert codigo == 0 and pronostico["reutilizado"] is False
    codigo, salida, _ = _corre(entorno, "generar", "--experimento", clave, "--modelo", "logistica_regularizada")
    assert codigo == 0 and json.loads(salida)["identificador"] == pronostico["identificador"]
    assert json.loads(salida)["reutilizado"] is True
    codigo, salida, _ = _corre(entorno, "verificar", "--pronostico", pronostico["identificador"])
    assert codigo == 0 and json.loads(salida)["reproduccion"]["huella_exacta"] is True
    codigo, salida, _ = _corre(entorno, "seguimiento", "--juego", "MILOTO")
    assert codigo == 0 and pronostico["linea"] in json.loads(salida)["lineas"]
    codigo, salida, _ = _corre(entorno, "consultar", "--id", final["id"])
    assert codigo == 0 and json.loads(salida)["estado"] == "exito"
    assert _corre(entorno, "experimentos", "--juego", "MILOTO")[0] == 0


@pytest.mark.parametrize("argumentos,codigo,nombre", [
    (["consultar", "--id", "0" * 64], 2, "no_encontrado"),
    (["generar", "--experimento", "0" * 64, "--modelo", "hgb_clasificador"], 2, "no_encontrado"),
    (["comparar", "--juego", "XX"], 2, None),
    (["comparar", "--juego", "BALOTO", "--bloques", "7"], 2, None),
])
def test_errores_esperados_con_codigo_estable(entorno, argumentos, codigo, nombre):
    obtenido, salida, errores = _corre(entorno, *argumentos)
    assert obtenido == codigo and "Traceback" not in errores
    if nombre:
        assert f"ERROR [codigo {codigo}] {nombre}:" in errores and salida == ""


def test_muestra_insuficiente_base_caida_activa_y_alterado(tmp_path):
    corta = f4.entorno(tmp_path / "a", {"MILOTO": 55})
    codigo, salida, _ = _corre(corta, "comparar", "--juego", "MILOTO")
    assert codigo == 4 and json.loads(salida)["juegos"]["MILOTO"]["estado"] == "muestra_insuficiente"
    assert _corre(corta, "diagnostico", "--juego", "MILOTO")[0] == 4
    caida = f4.entorno(tmp_path / "b")
    caida.base_caida = True
    codigo, salida, _ = _corre(caida, "comparar", "--juego", "COLORLOTO")
    assert codigo == 3 and json.loads(salida)["juegos"]["COLORLOTO"]["estado"] == "base_no_disponible"
    ocupada = f4.entorno(tmp_path / "c")
    lab = ocupada.laboratorio()
    inicio = lab.iniciar_comparacion(["MILOTO"])
    try:
        codigo, salida, _ = _corre(ocupada, "comparar", "--juego", "MILOTO")
        assert codigo == 6 and json.loads(salida)["activas"] == {"MILOTO": inicio.ejecucion["id"]}
    finally:
        inicio.cerrojos.liberar()
    codigo, salida, _ = _corre(ocupada, "comparar", "--juego", "MILOTO", "--bloques", "1", "--perfil", "reducido")
    clave = json.loads(salida)["juegos"]["MILOTO"]["experimento"]
    ruta = next((ocupada.directorio / "experimentos" / "MILOTO").glob("*.json"))
    ruta.write_bytes(ruta.read_bytes()[:-5])
    codigo, salida, errores = _corre(ocupada, "verificar", "--experimento", clave)
    assert codigo == 8 and json.loads(salida)["integridad"] == "alterado"


def test_rutas_aisladas_sin_credenciales_y_escrituras_en_producto4(tmp_path, monkeypatch):
    from app.api import dependencies as dep
    from app.core.config import get_settings

    p2 = tmp_path / "producto2" / "storage"
    p3 = tmp_path / "producto3" / "storage"
    p4 = tmp_path / "producto4" / "storage"
    for raiz in (p2, p3):
        (raiz / "pronosticos" / "MILOTO").mkdir(parents=True)
        (raiz / "pronosticos" / "MILOTO" / "previo.json").write_bytes(b'{"no": "tocar"}')
    monkeypatch.setenv("DIRECTORIO_PRONOSTICOS_EXPERIMENTALES", str(p2 / "pronosticos"))  # heredada de Producto 2
    monkeypatch.setenv("DIRECTORIO_OPERACION", str(p3 / "operacion"))                   # heredada de Producto 3
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://usuario:secreto@localhost/base")
    monkeypatch.setenv("DIRECTORIO_PRONOSTICOS_EXPERIMENTALES", str(p4 / "pronosticos"))  # overrides de Producto 4
    monkeypatch.setenv("DIRECTORIO_OPERACION", str(p4 / "operacion"))
    monkeypatch.setenv("DIRECTORIO_LABORATORIO_MODELOS", str(p4 / "laboratorio"))
    get_settings.cache_clear()
    try:
        salida = io.StringIO()
        assert cli.ejecutar(["rutas"], salida=salida, errores=io.StringIO()) == 0
        texto = salida.getvalue()
        rutas = json.loads(texto)
        assert rutas["directorio_laboratorio_modelos"] == str((p4 / "laboratorio").resolve())
        assert all(str(p4.resolve()) in v for k, v in rutas.items() if k != "directorio_de_trabajo")
        assert "secreto" not in texto and "postgresql" not in texto
        e = f4.entorno(tmp_path / "datos")
        lab = dep.get_laboratorio()
        lab._abrir = e.abrir
        lab.comparar_ahora(["MILOTO"], cli.le.Protocolo(bloques=1, perfil="reducido"))
        assert list((p4 / "laboratorio" / "experimentos" / "MILOTO").glob("*.json"))
        for raiz in (p2, p3):
            assert (raiz / "pronosticos" / "MILOTO" / "previo.json").read_bytes() == b'{"no": "tocar"}'
            assert not (raiz / "laboratorio").exists() and not (raiz.parent / "laboratorio").exists()
    finally:
        get_settings.cache_clear()
