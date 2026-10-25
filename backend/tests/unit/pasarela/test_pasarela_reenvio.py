"""Fase 9.1, pasarela: cabeceras hacia y desde la API, errores contractuales,
Retry-After, respuestas inesperadas y limites de tamano, tiempo y concurrencia."""
from __future__ import annotations

import socket
import threading
import time

import anyio
import httpx
import pytest

from app.pasarela import cliente as cl
from app.pasarela.aplicacion import Pasarela
from tests.unit.pasarela import fixtures_pasarela as fp


@pytest.fixture
def entorno(tmp_path):
    with fp.destino_falso() as d:
        clave = fp.clave_sintetica()
        yield d, fp.pasarela(d.destino, fp.dist(tmp_path), clave), clave


def test_a_la_api_solo_van_la_clave_propia_y_las_cabeceras_necesarias(entorno):
    d, app, clave = entorno
    ajena = fp.clave_sintetica()
    r = fp.cliente(app).get("/api/v1/juegos", headers={
        "X-API-Key": ajena, "Authorization": "Bearer " + ajena, "Cookie": "sesion=" + ajena,
        "X-Forwarded-For": "8.8.8.8", "Referer": "http://127.0.0.1:8020/x", "User-Agent": "navegador",
        "Accept-Language": "es", "X-Otra": "1"}, cookies={"sesion": ajena})
    assert r.status_code == 200
    recibidas = d.recibidas[0].cabeceras
    assert set(recibidas) == {"host", "accept", "accept-encoding", "user-agent", "connection", "x-api-key"}
    assert recibidas["x-api-key"] == clave and recibidas["host"] == f"127.0.0.1:{d.puerto}"
    assert recibidas["user-agent"] == "loteria-pasarela/9.1" and recibidas["connection"] == "close"
    assert ajena not in str(recibidas)


def test_de_la_api_solo_vuelven_las_cabeceras_previstas(entorno):
    d, app, _ = entorno
    d.json(200, {"ok": True}, **{"X-Request-ID": "c" * 32, "X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "59",
                                 "Set-Cookie": "a=b", "Server": "uvicorn", "X-Powered-By": "py",
                                 "Access-Control-Allow-Origin": "*", "WWW-Authenticate": "ApiKey",
                                 "Location": "http://evil.example", "Cache-Control": "max-age=999"})
    r = fp.cliente(app).get("/api/v1/juegos")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert r.headers["x-request-id"] == "c" * 32 and r.headers["x-ratelimit-limit"] == "60"
    assert r.headers["x-ratelimit-remaining"] == "59" and r.headers["cache-control"] == "no-store"
    for ajena in ("set-cookie", "server", "x-powered-by", "access-control-allow-origin", "www-authenticate",
                  "location"):
        assert ajena not in r.headers


@pytest.mark.parametrize("estado, codigo", [(401, "no_autenticado"), (404, "no_encontrado"), (409, "alterado"),
                                            (422, "parametro_no_valido"), (500, "error_interno"),
                                            (503, "base_no_disponible"), (503, "no_configurada")])
def test_errores_contractuales_de_la_api_tal_cual(entorno, estado, codigo):
    d, app, _ = entorno
    cuerpo = {"error": {"codigo": codigo, "mensaje": "Mensaje de la API", "solicitud": "d" * 32}}
    d.json(estado, cuerpo, **{"X-Request-ID": "d" * 32})
    r = fp.cliente(app).get("/api/v1/juegos/BALOTO")
    assert r.status_code == estado and r.json() == cuerpo and r.headers["x-request-id"] == "d" * 32


def test_429_con_retry_after(entorno):
    d, app, _ = entorno
    d.json(429, {"error": {"codigo": "limite_excedido", "mensaje": "Límite", "solicitud": "e" * 32}},
           **{"Retry-After": "17", "X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "0"})
    r = fp.cliente(app).get("/api/v1/juegos")
    assert r.status_code == 429 and r.headers["retry-after"] == "17" and r.headers["x-ratelimit-remaining"] == "0"
    d.json(429, {"error": {"codigo": "limite_excedido", "mensaje": "x", "solicitud": "e" * 32}},
           **{"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})
    assert "retry-after" not in fp.cliente(app).get("/api/v1/juegos").headers  # solo segundos enteros


@pytest.mark.parametrize("estado, cabeceras, cuerpo", [
    (302, {"Location": "http://127.0.0.1:1/robo", "Content-Type": "application/json"}, b"{}"),
    (301, {"Location": "/api/v1/estado", "Content-Type": "application/json"}, b"{}"),
    (200, {"Content-Type": "text/html"}, b"<html>no</html>"),
    (200, {"Content-Type": "application/json"}, b"no es json"),
    (404, {"Content-Type": "application/json"}, b'{"detail": "Not Found"}'),
    (418, {"Content-Type": "application/json"}, b'{"error": {"codigo": "tetera"}}'),
    (204, {"Content-Type": "application/json"}, b""),
    (200, {}, b"{}")])
def test_respuestas_inesperadas_no_se_siguen_ni_se_muestran(entorno, estado, cabeceras, cuerpo):
    d, app, _ = entorno
    d.modo, d.estado, d.cabeceras, d.cuerpo = "ok", estado, cabeceras, cuerpo
    r = fp.cliente(app).get("/api/v1/juegos")
    assert r.status_code == 502 and r.json()["error"]["codigo"] == "respuesta_no_valida"
    assert "robo" not in r.text and "html" not in r.text and "Not Found" not in r.text
    assert len(d.recibidas) == 1  # sin seguir la redireccion


def test_limite_de_tamano_exacto(entorno, monkeypatch):
    d, app, _ = entorno
    monkeypatch.setattr(cl, "MAXIMO_BYTES", 1000)
    app.cliente = cl.ClienteDeLaApi(d.destino, consultar_=lambda *a: cl.consultar(*a, maximo=1000))
    d.modo, d.estado, d.cabeceras = "ok", 200, {"Content-Type": "application/json"}
    d.cuerpo = b'"' + b"a" * 998 + b'"'
    assert fp.cliente(app).get("/api/v1/juegos").status_code == 200
    d.cuerpo = b'"' + b"a" * 999 + b'"'
    r = fp.cliente(app).get("/api/v1/juegos")
    assert r.status_code == 502 and r.json()["error"]["codigo"] == "respuesta_demasiado_grande"


def test_api_caida_o_que_corta_la_conexion(entorno, tmp_path):
    d, app, clave = entorno
    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        puerto = libre.getsockname()[1]
    caida = fp.pasarela(fp.Destino("127.0.0.1", puerto), fp.dist(tmp_path / "otro"), clave)
    r = fp.cliente(caida).get("/api/v1/juegos")
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "api_no_disponible"
    assert str(puerto) not in r.text and "refused" not in r.text.lower()
    d.modo = "cortar"
    r = fp.cliente(app).get("/api/v1/juegos")
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "api_no_disponible"


def test_tiempo_por_operacion_y_tiempo_total(entorno):
    d, app, _ = entorno
    app.cliente = cl.ClienteDeLaApi(d.destino, consultar_=lambda *a: cl.consultar(*a, tiempo=0.3, tiempo_total=5))
    d.modo, d.espera = "ok", 1.0
    inicio = time.monotonic()
    r = fp.cliente(app).get("/api/v1/juegos")
    assert r.status_code == 504 and r.json()["error"]["codigo"] == "api_sin_respuesta"
    assert time.monotonic() - inicio < 2.5
    d.espera, d.modo = 0.0, "goteo"  # cada byte llega a tiempo; el total supera el limite
    app.cliente = cl.ClienteDeLaApi(d.destino, consultar_=lambda *a: cl.consultar(*a, tiempo=1, tiempo_total=0.5))
    inicio = time.monotonic()
    r = fp.cliente(app).get("/api/v1/juegos")
    assert r.status_code == 504 and time.monotonic() - inicio < 2.5


def test_concurrencia_acotada_y_conexiones_cerradas(entorno):
    d, app, _ = entorno
    app.cliente = cl.ClienteDeLaApi(d.destino, concurrencia=2, espera=0.3)
    d.modo = "bloquear"

    async def carrera():
        transporte = httpx.ASGITransport(app=app, client=fp.LOCAL)
        async with httpx.AsyncClient(transport=transporte, base_url=f"http://{fp.HOST}", timeout=20) as c:
            async def una():
                return await c.get("/api/v1/juegos")
            async with anyio.create_task_group() as grupo:
                resultados = []

                async def guardar():
                    resultados.append(await una())
                for _ in range(2):
                    grupo.start_soon(guardar)
                await anyio.sleep(0.2)  # las dos primeras ocupan los huecos
                tercera = await una()
                assert tercera.status_code == 503 and tercera.json()["error"]["codigo"] == "pasarela_ocupada"
                assert tercera.headers["retry-after"] == "1"
                d.bloqueo.set()
            return resultados
    resultados = anyio.run(carrera)
    assert [r.status_code for r in resultados] == [200, 200]
    d.modo, d.bloqueo = "ok", threading.Event()
    assert fp.cliente(app).get("/api/v1/juegos").status_code == 200
    limite = time.monotonic() + 3
    while d.abiertas and time.monotonic() < limite:
        time.sleep(0.05)
    assert d.abiertas == 0 and all(x.cabeceras["connection"] == "close" for x in d.recibidas)


def test_la_espera_corre_en_un_hilo_y_no_bloquea_el_bucle(entorno):
    d, app, _ = entorno
    d.espera = 0.5

    async def medir():
        transporte = httpx.ASGITransport(app=app, client=fp.LOCAL)
        async with httpx.AsyncClient(transport=transporte, base_url=f"http://{fp.HOST}") as c:
            latidos = 0

            async def latir():
                nonlocal latidos
                while True:
                    await anyio.sleep(0.05)
                    latidos += 1
            async with anyio.create_task_group() as grupo:
                grupo.start_soon(latir)
                r = await c.get("/api/v1/juegos")
                grupo.cancel_scope.cancel()
            return r.status_code, latidos
    estado, latidos = anyio.run(medir)
    assert estado == 200 and latidos >= 5
    assert isinstance(app, Pasarela)
