"""Fase 10 (E10.2): perfil PRIVADO de la pasarela. Ingreso fiable (IP exacta del proxy + secreto en tiempo
constante), identidad por persona acreditada por el proxy, cuotas por persona y agregada, y configuracion que
no arranca sin sus secretos. Datos y secretos SINTETICOS generados en cada prueba; sin red externa."""
from __future__ import annotations

import logging
import secrets

import pytest
from pydantic import SecretStr

from app.api.publica import rutas as rutas_api
from app.pasarela import privada, rutas
from app.pasarela.aplicacion import crear_app
from app.pasarela.configuracion import (AjustesPasarela, ConfiguracionNoValida, PerfilPrivado, desde_ajustes)
from tests.unit.pasarela import fixtures_pasarela as fx

PROXY = ("172.30.1.10", 41000)
OTRO = ("172.30.1.11", 41000)
HOST = "consulta.e102.prueba:8443"
ORIGEN = "https://consulta.e102.prueba:8443"


def _secreto() -> str:
    return secrets.token_hex(32)


def _app(destino, carpeta, *, persona=30, agregado=90, secreto=None):
    secreto = secreto or _secreto()
    perfil = PerfilPrivado(proxies=frozenset({PROXY[0]}), secreto=SecretStr(secreto), fichas_persona=persona,
                           fichas_agregadas=agregado, max_personas=8)
    conf = fx.configuracion(destino, carpeta, fx.clave_sintetica(), hosts=frozenset({HOST}),
                            origenes=frozenset({ORIGEN}), privado=perfil)
    return crear_app(conf), secreto


def _get(app, ruta, *, client=PROXY, cabeceras=None):
    return fx.crudo(app, ruta.encode(), client=client, cabeceras=cabeceras)


def _ingreso(secreto, identidad="invitado-a", **extra):
    return [("host", HOST), ("x-consulta-ingreso", secreto), ("x-consulta-identidad", identidad),
            *extra.get("mas", [])]


# ---------------------------------------------------------------------------
# Ingreso fiable e identidad
# ---------------------------------------------------------------------------

def test_privado_reenvia_solo_con_proxy_fiable_secreto_e_identidad(tmp_path):
    with fx.destino_falso() as api:
        app, secreto = _app(api.destino, fx.dist(tmp_path))
        estado, cabeceras, _ = _get(app, "/api/v1/estado", cabeceras=_ingreso(secreto))
        assert estado == 200 and cabeceras["x-ratelimit-limit"] == "30" and cabeceras["x-ratelimit-remaining"] == "29"
        recibida = api.recibidas[-1].cabeceras
        # La API recibe la clave del servidor; nunca la identidad ni el secreto del proxy.
        assert "x-consulta-identidad" not in recibida and "x-consulta-ingreso" not in recibida
        assert recibida["x-api-key"]


@pytest.mark.parametrize("caso", ["otro_cliente", "loopback", "sin_secreto", "secreto_erroneo", "secreto_repetido",
                                  "secreto_prefijo", "xff_falso"])
def test_privado_rechaza_un_ingreso_no_fiable_sin_reenviar(tmp_path, caso):
    with fx.destino_falso() as api:
        app, secreto = _app(api.destino, fx.dist(tmp_path))
        client, cabeceras = PROXY, _ingreso(secreto)
        if caso == "otro_cliente":
            client = OTRO
        elif caso == "loopback":
            client = ("127.0.0.1", 50000)
        elif caso == "sin_secreto":
            cabeceras = [c for c in cabeceras if c[0] != "x-consulta-ingreso"]
        elif caso == "secreto_erroneo":
            cabeceras = _ingreso(_secreto())
        elif caso == "secreto_repetido":
            cabeceras = _ingreso(secreto, mas=[("x-consulta-ingreso", secreto)])
        elif caso == "secreto_prefijo":
            cabeceras = _ingreso(secreto[:-1])
        elif caso == "xff_falso":  # un cliente no fiable que afirma venir del proxy por XFF/Forwarded
            client = OTRO
            cabeceras = _ingreso(secreto, mas=[("x-forwarded-for", PROXY[0]), ("forwarded", f"for={PROXY[0]}"),
                                               ("x-real-ip", PROXY[0])])
        for ruta in ("/api/v1/estado", "/", "/pasarela/configuracion"):
            estado, _, cuerpo = _get(app, ruta, client=client, cabeceras=cabeceras)
            assert estado == 403 and b'"ingreso_no_fiable"' in cuerpo and secreto.encode() not in cuerpo
        assert api.recibidas == []


@pytest.mark.parametrize("identidades", [[], ["Invitado-A"], ["a"], ["invitado a"], ["invitado-a", "invitado-b"],
                                         ["x" * 64], ["invitado-á"]])
def test_privado_rechaza_identidad_ausente_repetida_o_no_valida(tmp_path, identidades):
    with fx.destino_falso() as api:
        app, secreto = _app(api.destino, fx.dist(tmp_path))
        cabeceras = [("host", HOST), ("x-consulta-ingreso", secreto),
                     *[("x-consulta-identidad", i) for i in identidades]]
        estado, _, cuerpo = _get(app, "/api/v1/estado", cabeceras=cabeceras)
        assert estado == 403 and b'"identidad_no_verificada"' in cuerpo
        assert api.recibidas == []


def test_privado_exige_host_exacto_y_origen_https(tmp_path):
    with fx.destino_falso() as api:
        app, secreto = _app(api.destino, fx.dist(tmp_path))
        base = [c for c in _ingreso(secreto) if c[0] != "host"]
        for host in ("127.0.0.1:8020", "consulta.e102.prueba", "otro.prueba:8443"):
            estado, _, cuerpo = _get(app, "/api/v1/estado", cabeceras=[("host", host), *base])
            assert estado == 403 and b'"host_no_permitido"' in cuerpo
        for origen in ("http://consulta.e102.prueba:8443", "https://otro.prueba:8443"):
            estado, _, cuerpo = _get(app, "/api/v1/estado", cabeceras=[*_ingreso(secreto), ("origin", origen)])
            assert estado == 403 and b'"origen_no_permitido"' in cuerpo
        estado, _, _ = _get(app, "/api/v1/estado", cabeceras=[*_ingreso(secreto), ("origin", ORIGEN),
                                                             ("sec-fetch-site", "same-origin")])
        assert estado == 200 and len(api.recibidas) == 1


def test_privado_sirve_la_spa_solo_por_el_proxy(tmp_path):
    with fx.destino_falso() as api:
        app, secreto = _app(api.destino, fx.dist(tmp_path))
        estado, _, cuerpo = _get(app, "/", cabeceras=_ingreso(secreto))
        assert estado == 200 and b'id="raiz"' in cuerpo
        estado, _, _ = _get(app, "/", client=OTRO, cabeceras=_ingreso(secreto))
        assert estado == 403
        estado, _, cuerpo = _get(app, "/pasarela/configuracion", cabeceras=_ingreso(secreto))
        assert estado == 200 and b'"consola_local":null' in cuerpo.replace(b" ", b"")


def test_privado_registra_la_identidad_sin_secretos(tmp_path, caplog):
    with fx.destino_falso() as api, caplog.at_level(logging.INFO, logger="app.pasarela"):
        app, secreto = _app(api.destino, fx.dist(tmp_path))
        _get(app, "/api/v1/estado", cabeceras=_ingreso(secreto, "invitado-b"))
        _get(app, "/api/v1/estado", client=OTRO, cabeceras=_ingreso(secreto, "invitado-b"))
    texto = caplog.text
    assert "identidad=invitado-b" in texto and "identidad=-" in texto
    assert secreto not in texto and app.configuracion.clave.get_secret_value() not in texto


# ---------------------------------------------------------------------------
# Cuotas por persona y agregada
# ---------------------------------------------------------------------------

def test_cuota_por_persona_aislada_con_429_y_retry_after(tmp_path):
    with fx.destino_falso() as api:
        app, secreto = _app(api.destino, fx.dist(tmp_path), persona=10, agregado=100)
        ruta = "/api/v1/juegos/BALOTO/estadisticas/resumen"  # coste 5
        estados = [_get(app, ruta, cabeceras=_ingreso(secreto, "invitado-a"))[0] for _ in range(3)]
        assert estados[:2] == [200, 200] and estados[2] == 429
        estado, cabeceras, cuerpo = _get(app, ruta, cabeceras=_ingreso(secreto, "invitado-a"))
        assert estado == 429 and b'"limite_excedido"' in cuerpo and int(cabeceras["retry-after"]) >= 1
        assert cabeceras["x-ratelimit-remaining"] == "0"
        # B no se ve afectado por A
        assert [_get(app, ruta, cabeceras=_ingreso(secreto, "invitado-b"))[0] for _ in range(2)] == [200, 200]
        assert len(api.recibidas) == 4  # los rechazos no llegan a la API


def test_cuota_agregada_limita_la_suma_sin_consumir_la_de_la_persona(tmp_path):
    with fx.destino_falso() as api:
        app, secreto = _app(api.destino, fx.dist(tmp_path), persona=10, agregado=15)
        ruta = "/api/v1/juegos/BALOTO/estadisticas/panel"
        assert _get(app, ruta, cabeceras=_ingreso(secreto, "invitado-a"))[0] == 200
        assert _get(app, ruta, cabeceras=_ingreso(secreto, "invitado-b"))[0] == 200
        assert _get(app, ruta, cabeceras=_ingreso(secreto, "invitado-a"))[0] == 200  # agregado 15/15
        estado, cabeceras, cuerpo = _get(app, ruta, cabeceras=_ingreso(secreto, "invitado-b"))
        assert estado == 429 and b'"limite_agregado_excedido"' in cuerpo and int(cabeceras["retry-after"]) >= 1
        assert cabeceras["x-ratelimit-remaining"] == "5"  # el rechazo agregado no gasto la cuota de B
        assert len(api.recibidas) == 3


def test_cuotas_atomicas_recarga_y_memoria_acotada():
    instante = [0.0]
    cuotas = privada.CuotasDeConsulta(10, 15, 2, reloj=lambda: instante[0])
    assert cuotas.consumir("a", 5).permitida and cuotas.consumir("a", 5).permitida
    rechazo = cuotas.consumir("a", 5)
    assert not rechazo.permitida and rechazo.alcance == "persona" and rechazo.reintentar_en == 30
    assert cuotas.consumir("b", 5).permitida
    agregado = cuotas.consumir("b", 1)
    assert not agregado.permitida and agregado.alcance == "agregado" and agregado.restantes == 5
    instante[0] = 60.0  # un minuto: ambas cubetas vuelven a su capacidad
    assert cuotas.consumir("a", 5).permitida
    cuotas.consumir("c", 1)
    assert len(cuotas._personas) == 2  # acotado: "b" (la menos reciente) se descarto
    with pytest.raises(ValueError):
        privada.CuotasDeConsulta(10, 5, 2)


def test_costes_de_la_pasarela_coinciden_con_los_de_la_api():
    assert set(privada.COSTES) == {r.plantilla for r in rutas.RUTAS}

    def recorrer(router, prefijo=""):
        for r in router.routes:
            if hasattr(r, "original_router"):
                yield from recorrer(r.original_router, prefijo)
            elif hasattr(r, "dependant"):
                yield (r.path if r.path.startswith("/api/v1") else prefijo + r.path), r

    costes = {}
    for ruta, r in [*recorrer(rutas_api.router, "/api/v1"), *recorrer(rutas_api.publico)]:
        llamadas = [d.call for d in r.dependant.dependencies if getattr(d.call, "__name__", "") == "_acceso"]
        costes[ruta] = llamadas[0].__closure__[0].cell_contents if llamadas else None
    assert set(costes) == set(privada.COSTES)
    assert {k: v for k, v in costes.items() if v is not None} == \
        {k: v for k, v in privada.COSTES.items() if k != "/api/v1/salud"}
    assert costes["/api/v1/salud"] is None and privada.COSTES["/api/v1/salud"] == 1


# ---------------------------------------------------------------------------
# Configuracion: cerrada sin secretos ni valores exactos
# ---------------------------------------------------------------------------

def _ajustes(tmp_path, **extra) -> AjustesPasarela:
    secreto, clave = tmp_path / "secreto", tmp_path / "clave"
    secreto.write_text(_secreto() + "\n", encoding="ascii")
    clave.write_text(fx.clave_sintetica(), encoding="ascii")
    valores = {"perfil": "privado", "proxies_fiables": PROXY[0], "secreto_proxy_archivo": str(secreto),
               "clave_api_archivo": str(clave), "api_url": "http://172.30.2.20:8010", "hosts": HOST,
               "origenes": ORIGEN, **extra}
    return AjustesPasarela.model_construct(**{**AjustesPasarela().model_dump(), **valores,
                                              "clave_api": SecretStr(extra.get("clave_api", ""))})


def test_configuracion_privada_valida(tmp_path):
    conf = desde_ajustes(_ajustes(tmp_path))
    assert conf.privado.proxies == frozenset({PROXY[0]}) and conf.destino.url == "http://172.30.2.20:8010"
    assert conf.abierta and conf.consola_local is None and conf.hosts == frozenset({HOST})
    assert conf.privado.secreto.get_secret_value() not in repr(conf)
    assert conf.clave.get_secret_value() not in repr(conf)


@pytest.mark.parametrize("cambio", [
    {"proxies_fiables": ""}, {"proxies_fiables": "172.30.1.0/24"}, {"proxies_fiables": "0.0.0.0"},
    {"proxies_fiables": "proxy"}, {"secreto_proxy_archivo": ""}, {"secreto_proxy_archivo": "/no/existe"},
    {"clave_api_archivo": ""}, {"clave_api": "lpk_" + "x" * 40}, {"consola_local": "http://127.0.0.1:8000"},
    {"api_url": "http://api.interna:8010"}, {"api_url": "https://172.30.2.20:8010"}, {"api_url": "http://0.0.0.0:8010"},
    {"api_url": "http://172.30.2.20"}, {"hosts": "*.e102.prueba:8443"}, {"hosts": "consulta.e102.prueba"},
    {"hosts": ""}, {"origenes": "http://consulta.e102.prueba:8443"}, {"origenes": "https://*:8443"},
    {"fichas_persona_por_minuto": 4}, {"fichas_agregadas_por_minuto": 10, "fichas_persona_por_minuto": 30},
    {"max_personas": 1}, {"perfil": "publico"},
])
def test_configuracion_privada_no_arranca_si_falta_o_no_es_valida(tmp_path, cambio):
    with pytest.raises(ConfiguracionNoValida) as error:
        desde_ajustes(_ajustes(tmp_path, **cambio))
    assert "lpk_" not in str(error.value)


def test_configuracion_privada_rechaza_secreto_vacio_corto_o_igual_a_la_clave(tmp_path):
    for contenido in ("", "corto", "con espacio " * 4):
        (tmp_path / "s").write_text(contenido, encoding="ascii")
        with pytest.raises(ConfiguracionNoValida):
            desde_ajustes(_ajustes(tmp_path, secreto_proxy_archivo=str(tmp_path / "s")))
    clave = fx.clave_sintetica()
    (tmp_path / "s").write_text(clave, encoding="ascii")
    (tmp_path / "c").write_text(clave, encoding="ascii")
    with pytest.raises(ConfiguracionNoValida):
        desde_ajustes(_ajustes(tmp_path, secreto_proxy_archivo=str(tmp_path / "s"), clave_api_archivo=str(tmp_path / "c")))


def test_modo_local_sin_cambios_y_sin_ajustes_privados(tmp_path):
    local = desde_ajustes(AjustesPasarela.model_construct(**AjustesPasarela().model_dump()))
    assert local.privado is None and local.destino.url == "http://127.0.0.1:8010"
    for cambio in ({"proxies_fiables": PROXY[0]}, {"secreto_proxy_archivo": "x"}, {"clave_api_archivo": "x"}):
        with pytest.raises(ConfiguracionNoValida):
            desde_ajustes(AjustesPasarela.model_construct(**{**AjustesPasarela().model_dump(), **cambio}))
    with fx.destino_falso() as api:  # el modo local sigue exigiendo cliente loopback e ignora las cabeceras
        app = fx.pasarela(api.destino, fx.dist(tmp_path), fx.clave_sintetica())
        estado, _, cuerpo = fx.crudo(app, b"/api/v1/estado", client=PROXY,
                                     cabeceras=[("host", fx.HOST), ("x-consulta-identidad", "invitado-a")])
        assert estado == 403 and b'"cliente_no_local"' in cuerpo
        estado, cabeceras, _ = fx.crudo(app, b"/api/v1/estado")
        assert estado == 200 and app.cuotas is None


# ---------------------------------------------------------------------------
# v2 (F1023-LIM-01): la memoria acotada no olvida la deuda de una identidad
# ---------------------------------------------------------------------------

def _cuotas(persona=5, agregado=100, maximo=2):
    instante = [0.0]
    return privada.CuotasDeConsulta(persona, agregado, maximo, reloj=lambda: instante[0]), instante


def test_expulsar_no_reinicia_una_cuota_agotada():
    cuotas, instante = _cuotas()
    assert cuotas.consumir("invitado-a", 5).permitida and not cuotas.consumir("invitado-a", 1).permitida
    assert cuotas.consumir("invitado-b", 1).permitida
    nueva = cuotas.consumir("invitado-c", 1)  # A y B tienen deuda: no hay sitio para C
    assert not nueva.permitida and nueva.alcance == "capacidad" and nueva.reintentar_en == 12  # B: 1 ficha a 5/min
    otra = cuotas.consumir("invitado-a", 1)
    assert not otra.permitida and otra.alcance == "persona"  # A sigue agotada
    instante[0] = 60.0  # recarga legitima
    assert cuotas.consumir("invitado-a", 1).permitida


def test_solo_se_descarta_una_cubeta_recuperada_y_la_nueva_entra():
    cuotas, instante = _cuotas()
    cuotas.consumir("invitado-a", 5)
    cuotas.consumir("invitado-b", 1)
    instante[0] = 12.0  # B ya se recupero (1 ficha a 5/min); A aun debe
    assert cuotas.consumir("invitado-c", 1).permitida
    assert set(cuotas._personas) == {"invitado-a", "invitado-c"}
    assert not cuotas.consumir("invitado-a", 2).permitida  # la deuda de A no se olvido


def test_presion_de_muchas_identidades_respeta_cuotas_y_memoria():
    cuotas, instante = _cuotas(persona=5, agregado=1000, maximo=8)
    for t in range(0, 600, 3):  # 10 minutos con 40 identidades rotando
        instante[0] = float(t)
        for i in range(40):
            cuotas.consumir(f"invitado-{i}", 5)
        assert len(cuotas._personas) <= 8
    gastado = {}
    instante[0] = 1000.0
    for i in range(40):  # ninguna identidad seguida puede gastar mas de su capacidad sin recargar
        persona = f"invitado-{i}"
        while cuotas.consumir(persona, 1).permitida:
            gastado[persona] = gastado.get(persona, 0) + 1
            assert gastado[persona] <= 5


def test_equidad_y_agregado_con_identidades_seguidas():
    cuotas, _ = _cuotas(persona=10, agregado=15, maximo=4)
    assert cuotas.consumir("invitado-a", 10).permitida
    assert cuotas.consumir("invitado-b", 5).permitida
    rechazo = cuotas.consumir("invitado-b", 5)
    assert not rechazo.permitida and rechazo.alcance == "agregado"
    nueva = cuotas.consumir("invitado-c", 1)  # hay sitio (4): entra, pero el agregado esta agotado
    assert not nueva.permitida and nueva.alcance == "agregado"


def test_concurrencia_no_supera_cuota_ni_memoria():
    import threading

    cuotas = privada.CuotasDeConsulta(5, 1000, 3)
    admitidas: dict[str, int] = {}
    cerrojo = threading.Lock()

    def trabajo(persona):
        for _ in range(20):
            if cuotas.consumir(persona, 1).permitida:
                with cerrojo:
                    admitidas[persona] = admitidas.get(persona, 0) + 1

    hilos = [threading.Thread(target=trabajo, args=(f"invitado-{i % 6}",)) for i in range(24)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert len(cuotas._personas) <= 3
    assert all(n <= 6 for n in admitidas.values())  # 5 fichas + a lo sumo 1 de recarga durante la prueba
    assert sum(admitidas.values()) <= 3 * 5 + 3 + 3  # solo 3 identidades pueden haber entrado a la vez


def test_pasarela_responde_429_cuando_no_hay_sitio_para_otra_identidad(tmp_path):
    with fx.destino_falso() as api:
        perfil = PerfilPrivado(proxies=frozenset({PROXY[0]}), secreto=SecretStr(_secreto()), fichas_persona=5,
                               fichas_agregadas=100, max_personas=2)
        conf = fx.configuracion(api.destino, fx.dist(tmp_path), fx.clave_sintetica(), hosts=frozenset({HOST}),
                                origenes=frozenset({ORIGEN}), privado=perfil)
        app = crear_app(conf)
        secreto = perfil.secreto.get_secret_value()
        ruta = "/api/v1/juegos/BALOTO/estadisticas/resumen"  # coste 5
        assert _get(app, ruta, cabeceras=_ingreso(secreto, "invitado-a"))[0] == 200
        assert _get(app, "/api/v1/estado", cabeceras=_ingreso(secreto, "invitado-b"))[0] == 200
        estado, cabeceras, cuerpo = _get(app, ruta, cabeceras=_ingreso(secreto, "invitado-c"))
        assert estado == 429 and b'"limite_identidades_excedido"' in cuerpo and int(cabeceras["retry-after"]) >= 1
        assert len(api.recibidas) == 2
