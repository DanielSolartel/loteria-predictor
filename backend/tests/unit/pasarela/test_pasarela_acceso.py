"""Fase 9.1, pasarela: solo GET, cliente local, Host contra el DNS rebinding,
Origin y Fetch Metadata en `/api/v1` y `/pasarela`, CORS deshabilitado y modo
Vite habilitado de forma explicita, sin quitar controles."""
from __future__ import annotations

import json

import pytest

from tests.unit.pasarela import fixtures_pasarela as fp


@pytest.fixture
def entorno(tmp_path):
    with fp.destino_falso() as d:
        app = fp.pasarela(d.destino, fp.dist(tmp_path), fp.clave_sintetica())
        yield d, app


def _codigo(r) -> str:
    return r.json()["error"]["codigo"]


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "TRACE"])
def test_solo_get_y_sin_cors(entorno, metodo):
    d, app = entorno
    for url in ("/api/v1/juegos", "/", "/assets/app-1.js"):
        r = fp.cliente(app).request(metodo, url, headers={"Origin": fp.ORIGEN,
                                                          "Access-Control-Request-Method": "GET"})
        assert r.status_code == 405 and r.headers["allow"] == "GET"
        assert not any(k.lower().startswith("access-control-") for k in r.headers)
    assert d.recibidas == []


@pytest.mark.parametrize("cliente", [("10.0.0.7", 5000), ("192.168.1.3", 5000), ("8.8.8.8", 443)])
def test_cliente_que_no_es_local(entorno, cliente):
    d, app = entorno
    for url in ("/api/v1/juegos", "/", "/assets/app-1.js"):
        r = fp.cliente(app, client=cliente).get(url)
        assert r.status_code == 403 and _codigo(r) == "cliente_no_local"
    assert d.recibidas == []


@pytest.mark.parametrize("host", ["evil.example:8020", "127.0.0.1:9999", "127.0.0.1", "localhost",
                                  "127.0.0.1.nip.io:8020", "attacker.test"])
def test_host_de_rebinding_o_ajeno(entorno, host):
    d, app = entorno
    for url in ("/api/v1/juegos", "/", "/pasarela/configuracion"):
        r = fp.cliente(app, host=host).get(url)
        assert r.status_code == 403 and _codigo(r) == "host_no_permitido", (host, url)
    assert d.recibidas == []


def test_host_duplicado(entorno):
    _, app = entorno
    estado, _, cuerpo = fp.crudo(app, b"/api/v1/juegos", cabeceras=[("host", fp.HOST), ("host", "evil.example")])
    assert estado == 403 and json.loads(cuerpo)["error"]["codigo"] == "host_no_permitido"


@pytest.mark.parametrize("cabeceras", [{"Origin": "http://evil.example"}, {"Origin": "http://127.0.0.1:9999"},
                                       {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"},
                                       {"Sec-Fetch-Site": "same-site"},
                                       {"Origin": fp.ORIGEN, "Sec-Fetch-Site": "cross-site"}])
def test_origen_ajeno_o_fetch_metadata_ajeno(entorno, cabeceras):
    d, app = entorno
    for url in ("/api/v1/juegos", "/pasarela/configuracion"):
        r = fp.cliente(app).get(url, headers=cabeceras)
        assert r.status_code == 403 and _codigo(r) == "origen_no_permitido"
        assert "access-control-allow-origin" not in r.headers
    assert d.recibidas == []


@pytest.mark.parametrize("cabeceras", [{}, {"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors"},
                                       {"Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate"},
                                       {"Origin": fp.ORIGEN, "Sec-Fetch-Site": "same-origin"},
                                       {"Origin": "http://localhost:8020"}])
def test_mismo_origen_o_navegacion_directa(entorno, cabeceras):
    d, app = entorno
    r = fp.cliente(app).get("/api/v1/salud", headers=cabeceras)
    assert r.status_code == 200 and len(d.recibidas) == 1
    assert "access-control-allow-origin" not in r.headers


def test_x_forwarded_for_no_cambia_el_cliente(entorno):
    d, app = entorno
    r = fp.cliente(app, client=("10.0.0.7", 5000)).get("/api/v1/salud", headers={"X-Forwarded-For": "127.0.0.1"})
    assert r.status_code == 403 and d.recibidas == []


def test_modo_vite_exige_su_host_y_su_origen_configurados(tmp_path):
    vite_host, vite_origen = "127.0.0.1:5173", "http://127.0.0.1:5173"
    with fp.destino_falso() as d:
        sin_vite = fp.pasarela(d.destino, fp.dist(tmp_path / "a"), fp.clave_sintetica())
        r = fp.cliente(sin_vite, host=vite_host).get("/api/v1/salud", headers={"Sec-Fetch-Site": "same-origin"})
        assert r.status_code == 403 and _codigo(r) == "host_no_permitido"
        con_vite = fp.pasarela(d.destino, fp.dist(tmp_path / "b"), fp.clave_sintetica(),
                               hosts=frozenset({fp.HOST, vite_host}), origenes=frozenset({fp.ORIGEN, vite_origen}))
        ok = fp.cliente(con_vite, host=vite_host).get("/api/v1/salud", headers={"Sec-Fetch-Site": "same-origin",
                                                                                "Origin": vite_origen})
        assert ok.status_code == 200
        ajeno = fp.cliente(con_vite, host=vite_host).get("/api/v1/salud", headers={"Origin": "http://evil.example"})
        assert ajeno.status_code == 403 and _codigo(ajeno) == "origen_no_permitido"
        assert len(d.recibidas) == 1
