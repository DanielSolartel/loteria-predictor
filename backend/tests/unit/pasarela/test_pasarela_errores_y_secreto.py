"""Fase 9.1, pasarela: errores propios sanitizados (con solicitud y no-store),
fallos inesperados que no llegan al servidor, cancelaciones no capturadas y
un canario de clave ausente de respuestas, cabeceras y registros."""
from __future__ import annotations

import asyncio
import json
import logging

import pytest

from app.pasarela import aplicacion
from tests.unit.pasarela import fixtures_pasarela as fp


@pytest.fixture
def entorno(tmp_path):
    with fp.destino_falso() as d:
        clave = fp.clave_sintetica()
        yield d, fp.pasarela(d.destino, fp.dist(tmp_path), clave), clave


def test_sin_clave_valida_responde_503_y_sirve_la_spa(tmp_path):
    with fp.destino_falso() as d:
        cerrada = fp.pasarela(d.destino, fp.dist(tmp_path), "corta")
        c = fp.cliente(cerrada)
        r = c.get("/api/v1/juegos")
        assert r.status_code == 503 and r.json()["error"]["codigo"] == "pasarela_no_configurada"
        assert c.get("/").status_code == 200 and d.recibidas == []


def test_fallo_inesperado_sanitizado_sin_llegar_al_servidor(entorno, monkeypatch, caplog):
    _, app, clave = entorno

    def falla(*_):
        raise RuntimeError("CANARIO_INTERNO /home/operador/.env " + clave)
    monkeypatch.setattr(aplicacion.rutas, "buscar", falla)
    with caplog.at_level(logging.DEBUG):
        r = fp.cliente(app).get("/api/v1/juegos")  # raise_server_exceptions=True: no escapa
    cuerpo = r.json()["error"]
    assert r.status_code == 500 and cuerpo["codigo"] == "error_interno"
    assert r.headers["x-request-id"] == cuerpo["solicitud"] and r.headers["cache-control"] == "no-store"
    texto = r.text + caplog.text + "".join(str(x.args) for x in caplog.records)
    assert "CANARIO_INTERNO" not in texto and clave not in texto and "Traceback" not in texto
    assert all(x.exc_info is None for x in caplog.records)
    assert f"error_interno=RuntimeError solicitud={cuerpo['solicitud']}" in caplog.text


@pytest.mark.parametrize("excepcion", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
def test_cancelaciones_y_salidas_no_se_capturan(entorno, monkeypatch, excepcion):
    _, app, _ = entorno

    def falla(*_):
        raise excepcion()
    monkeypatch.setattr(aplicacion.rutas, "buscar", falla)
    with pytest.raises(excepcion):
        fp.crudo(app, b"/api/v1/juegos")


def test_canario_ausente_de_respuestas_cabeceras_y_registros(entorno, caplog):
    d, app, clave = entorno
    huella_parcial = clave[4:20]
    c = fp.cliente(app)
    with caplog.at_level(logging.DEBUG):
        respuestas = [c.get(u) for u in ("/", "/assets/app-1.js", "/pasarela/configuracion", "/api/v1/salud",
                                          "/api/v1/juegos?x=1", "/api/v1/docs", "/assets/no.js")]
        d.json(401, {"error": {"codigo": "no_autenticado", "mensaje": "Clave de API ausente o no válida",
                               "solicitud": "f" * 32}})
        respuestas.append(c.get("/api/v1/juegos"))
        respuestas.append(c.get(f"/api/v1/juegos?api_key={clave}"))  # una clave por error en la URL: 422 local
    for r in respuestas:
        assert clave not in r.text and huella_parcial not in r.text
        assert clave not in json.dumps(dict(r.headers))
    assert respuestas[-1].status_code == 422 and d.recibidas[-1].ruta == "/api/v1/juegos"
    servidor = [x for x in caplog.records if not x.name.startswith(("httpx", "httpcore"))]  # sin el cliente de pruebas
    texto = "\n".join(x.getMessage() for x in servidor)
    assert clave not in texto and "api_key" not in texto and "?" not in texto
    lineas = [x.getMessage() for x in caplog.records if x.name == "app.pasarela"]
    assert len(lineas) == len(respuestas) and all(m.startswith("pasarela GET ") for m in lineas)
