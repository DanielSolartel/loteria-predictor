"""Fase 8: limite de uso por proceso (cubeta de fichas): recarga, coste,
Retry-After, memoria acotada, concurrencia real (hilos y solicitudes HTTP
simultaneas) y separacion entre clave, IP e identidades rechazadas."""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.api.publica.limites import LimitadorDeCuota
from app.api.publica.seguridad import generar_clave
from tests.unit.api_publica import fixtures_api_publica as fa


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_cubeta_capacidad_recarga_coste_y_espera():
    reloj = Reloj()
    lim = LimitadorDeCuota(6, 10, reloj=reloj)  # 6 por minuto = 1 ficha cada 10 s
    assert [lim.consumir("a").permitida for _ in range(7)] == [True] * 6 + [False]
    rechazo = lim.consumir("a")
    assert not rechazo.permitida and rechazo.reintentar_en == 10 and rechazo.restantes == 0
    reloj.t += 10
    assert lim.consumir("a").permitida and not lim.consumir("a").permitida
    reloj.t += 600  # nunca supera la capacidad
    assert lim.consumir("a", 6).permitida and not lim.consumir("a", 1).permitida
    reloj.t += 25
    caro = lim.consumir("a", 5)
    assert not caro.permitida and caro.reintentar_en == 25  # faltan 2,5 fichas -> ceil(25 s)
    assert lim.consumir("b").permitida  # cada identidad tiene su cubeta
    assert lim.rechazos == 5


def test_identidades_acotadas_sin_crecimiento_ilimitado():
    lim = LimitadorDeCuota(60, 16, reloj=Reloj())
    for i in range(10_000):
        lim.consumir(f"inventada-{i}")
    assert lim.identidades == 16 and lim.descartes == 10_000 - 16


def test_concurrencia_con_hilos_respeta_exactamente_la_capacidad():
    lim = LimitadorDeCuota(50, 10, reloj=Reloj())  # reloj quieto: sin recarga durante la carrera
    barrera = threading.Barrier(32)

    def intentar(_):
        barrera.wait()
        return sum(lim.consumir("compartida").permitida for _ in range(10))
    with ThreadPoolExecutor(32) as grupo:
        permitidas = sum(grupo.map(intentar, range(32)))
    assert permitidas == 50 and lim.rechazos == 32 * 10 - 50


def _simultaneas(app, peticiones):
    async def correr():
        transporte = httpx.ASGITransport(app=app, client=("127.0.0.1", 40000))
        async with httpx.AsyncClient(transport=transporte, base_url="http://testserver") as c:
            return await asyncio.gather(*(c.get(url, headers=h) for url, h in peticiones))
    return asyncio.run(correr())


def test_solicitudes_http_simultaneas_429_con_retry_after(tmp_path):
    a = fa.api(tmp_path, fichas_por_minuto=10)
    a.app.state.limitador_por_clave._reloj = Reloj()  # sin recarga durante la carrera
    respuestas = _simultaneas(a.app, [("/api/v1/juegos", a.cabeceras())] * 40)
    codigos = sorted(r.status_code for r in respuestas)
    assert codigos == [200] * 10 + [429] * 30
    for r in respuestas:
        assert r.headers["X-RateLimit-Limit"] == "10" and r.headers["X-Request-ID"]
        if r.status_code == 429:
            assert r.json()["error"]["codigo"] == "limite_excedido" and int(r.headers["Retry-After"]) >= 1
            assert r.json()["error"]["solicitud"] == r.headers["X-Request-ID"]


def test_el_coste_de_las_estadisticas_y_la_recuperacion(tmp_path):
    a = fa.api(tmp_path, fichas_por_minuto=10)
    reloj = Reloj()
    a.app.state.limitador_por_clave._reloj = reloj
    c = a.cliente()
    panel = "/api/v1/juegos/BALOTO/estadisticas/panel"
    assert [c.get(panel, headers=a.cabeceras()).status_code for _ in range(3)] == [200, 200, 429]
    r = c.get("/api/v1/juegos", headers=a.cabeceras())
    assert r.status_code == 429 and r.headers["Retry-After"] == "6"  # 1 ficha a 10/min
    reloj.t += 6
    assert c.get("/api/v1/juegos", headers=a.cabeceras()).status_code == 200


def test_claves_inventadas_no_crean_estado_y_la_ip_frena_la_fuerza_bruta(tmp_path):
    a = fa.api(tmp_path, fichas_por_minuto_ip=20, max_clientes_ip=16)
    a.app.state.limitador_por_ip._reloj = Reloj()
    c = a.cliente()
    codigos = [c.get("/api/v1/juegos", headers={"X-API-Key": generar_clave()}).status_code for _ in range(30)]
    assert codigos == [401] * 20 + [429] * 10
    assert a.app.state.limitador_por_clave.identidades == 0
    assert c.get("/api/v1/salud").status_code == 429  # el limite por IP cubre tambien las rutas sin clave
    for i in range(200):  # muchos origenes: memoria acotada
        a.cliente(client=(f"10.0.{i // 250}.{i % 250}", 1)).get("/api/v1/salud")
    assert a.app.state.limitador_por_ip.identidades == 16


def test_cuota_independiente_por_clave(tmp_path):
    a = fa.api(tmp_path, "uno", "dos", fichas_por_minuto=5)
    a.app.state.limitador_por_clave._reloj = Reloj()
    assert [a.get("/api/v1/juegos", "uno").status_code for _ in range(6)] == [200] * 5 + [429]
    assert a.get("/api/v1/juegos", "dos").status_code == 200
    assert a.app.state.limitador_por_clave.identidades == 2


def test_el_estado_informa_que_el_limite_es_por_proceso(tmp_path):
    a = fa.api(tmp_path)
    limites = a.get("/api/v1/estado").json()["limites"]
    assert limites["alcance"] == "por_proceso" and limites["fichas_por_minuto_por_clave"] == 60
    assert limites["costes"] == {"ligera": 1, "listado": 2, "predicciones": 3, "estadisticas": 5}
