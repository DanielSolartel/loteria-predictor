"""Fase 10 (E10.2): perfil PRIVADO de la API publica. Frontera (IP exacta del socket y `Host`), semaforo de
las consultas de coste 5 retenido mientras el trabajo sigue en su hilo, `statement_timeout` como 503
controlado, opciones del motor neutras por defecto y reglas del punto de entrada privado (secretos en
archivos, almacenes presentes, sin root). Claves y datos SINTETICOS; sin PostgreSQL (ver
`tests/postgres_e102.py`)."""
from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.publica import aplicacion, perfil_privado
from app.api.publica import dependencias as d
from app.api.publica.configuracion import (ConfiguracionNoValida, desde_settings, leer_clientes, leer_hosts,
                                           validar)
from app.api.publica.errores import ErrorPublico
from app.api.publica.recursos import LimiteDeCostosas
from app.core.config import Settings
from app.infrastructure.db.session import opciones_del_motor
from tests.unit.api_publica import fixtures_api_publica as fx

PASARELA = ("172.30.2.10", 40000)
HOST_API = "172.30.2.20:8010"


def _api(**extra):
    conf, claves = fx.configuracion("pasarela", **extra)
    return aplicacion.crear_app(conf), claves["pasarela"]


# ---------------------------------------------------------------------------
# Frontera privada
# ---------------------------------------------------------------------------

def test_frontera_admite_solo_la_pasarela_con_el_host_exacto():
    app, clave = _api(hosts=frozenset({HOST_API}), clientes=frozenset({PASARELA[0]}))
    bueno = TestClient(app, base_url=f"http://{HOST_API}", client=PASARELA)
    assert bueno.get("/api/v1/salud").status_code == 200
    otro = TestClient(app, base_url=f"http://{HOST_API}", client=("172.30.2.99", 1))
    r = otro.get("/api/v1/salud", headers={"X-Forwarded-For": PASARELA[0], "Forwarded": f"for={PASARELA[0]}"})
    assert r.status_code == 403 and r.json()["error"]["codigo"] == "cliente_no_permitido"
    assert r.headers["cache-control"] == "no-store" and len(r.headers["x-request-id"]) == 32
    r = TestClient(app, base_url="http://api.otra:8010", client=PASARELA).get("/api/v1/estado",
                                                                             headers={"X-API-Key": clave})
    assert r.status_code == 403 and r.json()["error"]["codigo"] == "host_no_permitido"


def test_frontera_rechaza_host_repetido():
    app, _ = _api(hosts=frozenset({HOST_API}), clientes=frozenset({PASARELA[0]}))
    estado, _, cuerpo = _asgi(app, [(b"host", HOST_API.encode()), (b"host", HOST_API.encode())], PASARELA)
    assert estado == 403 and b"host_no_permitido" in cuerpo


def _asgi(app, cabeceras, client):
    import anyio

    mensajes = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        mensajes.append(m)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
             "path": "/api/v1/salud", "raw_path": b"/api/v1/salud", "query_string": b"", "root_path": "",
             "headers": cabeceras, "client": client, "server": ("172.30.2.20", 8010)}
    anyio.run(app, scope, receive, send)
    inicio = next(m for m in mensajes if m["type"] == "http.response.start")
    return inicio["status"], inicio["headers"], b"".join(m.get("body", b"") for m in mensajes
                                                          if m["type"] == "http.response.body")


def test_sin_frontera_el_modo_local_no_cambia():
    app, clave = _api()
    c = TestClient(app, base_url="http://cualquiera:1", client=("10.0.0.5", 1))
    assert c.get("/api/v1/salud").status_code == 200
    assert app.state.costosas.concurrencia == 0


@pytest.mark.parametrize("texto", ["*.prueba:8010", "api", "api:0", "api:99999", "API_X:1"])
def test_hosts_exactos(texto):
    with pytest.raises(ConfiguracionNoValida):
        leer_hosts(texto)


@pytest.mark.parametrize("texto", ["172.30.2.0/24", "0.0.0.0", "::", "pasarela", "224.0.0.1"])
def test_clientes_exactos(texto):
    with pytest.raises(ConfiguracionNoValida):
        leer_clientes(texto)


def test_hosts_y_clientes_van_juntos_y_limites_acotados():
    conf, _ = fx.configuracion("x")
    for cambio in ({"hosts": frozenset({HOST_API})}, {"clientes": frozenset({PASARELA[0]})},
                   {"concurrencia_costosas": -1}, {"concurrencia_costosas": 65}, {"espera_costosas": 0},
                   {"espera_costosas": 31}):
        with pytest.raises(ConfiguracionNoValida):
            validar(conf.__class__(**{**conf.__dict__, **cambio}))


def test_desde_settings_lee_los_ajustes_nuevos_con_valores_neutros():
    neutros = desde_settings(Settings(_env_file=None, api_publica_claves=""))
    assert (neutros.hosts, neutros.clientes, neutros.concurrencia_costosas) == (frozenset(), frozenset(), 0)
    privado = desde_settings(Settings(_env_file=None, api_publica_hosts=HOST_API, api_publica_clientes=PASARELA[0],
                                      api_publica_concurrencia_costosas=2, api_publica_espera_costosas=0.25))
    assert privado.hosts == frozenset({HOST_API}) and privado.clientes == frozenset({PASARELA[0]})
    assert (privado.concurrencia_costosas, privado.espera_costosas) == (2, 0.25)


# ---------------------------------------------------------------------------
# Consultas de coste 5: semaforo retenido en el hilo
# ---------------------------------------------------------------------------

class _ResumenBloqueado:
    def __init__(self):
        self.dentro, self.salir, self.terminadas = threading.Event(), threading.Event(), 0

    def ejecutar(self, *a, **kw):
        self.dentro.set()
        self.salir.wait(10)
        self.terminadas += 1
        raise ErrorPublico(404, "no_encontrado", "sintetico")


def test_costosas_ocupadas_responden_503_y_el_hueco_vuelve_al_terminar():
    app, clave = _api(concurrencia_costosas=1, espera_costosas=0.2)
    falso = _ResumenBloqueado()
    app.dependency_overrides[d.consultar_resumen] = lambda: falso
    c = TestClient(app, client=fx.LOCAL)
    ruta, cabeceras = "/api/v1/juegos/BALOTO/estadisticas/resumen", {"X-API-Key": clave}
    resultado = {}
    hilo = threading.Thread(target=lambda: resultado.setdefault("r", c.get(ruta, headers=cabeceras)))
    hilo.start()
    assert falso.dentro.wait(5)
    r = c.get(ruta, headers=cabeceras)
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "consultas_ocupadas"
    assert r.headers["retry-after"] == "1" and app.state.costosas.rechazos == 1
    # Una consulta ligera no usa el semaforo
    assert c.get("/api/v1/estado", headers=cabeceras).status_code == 200
    falso.salir.set()
    hilo.join(10)
    assert resultado["r"].status_code == 404 and app.state.costosas.en_curso == 0
    assert c.get(ruta, headers=cabeceras).status_code == 404  # el hueco ya esta libre


def test_el_hueco_no_se_libera_mientras_el_trabajo_sigue_en_su_hilo():
    """Modelo de una desconexion: la peticion se abandona, pero el hilo sigue; la capacidad vuelve solo
    cuando la funcion termina de verdad."""
    limite, salir, dentro = LimiteDeCostosas(1, 0.05), threading.Event(), threading.Event()

    def trabajo():
        dentro.set()
        salir.wait(10)
        return "fin"

    hilo = threading.Thread(target=lambda: limite.ejecutar(trabajo))
    hilo.start()
    assert dentro.wait(5) and limite.en_curso == 1
    with pytest.raises(ErrorPublico) as ocupado:
        limite.ejecutar(lambda: "no")
    assert ocupado.value.estado == 503
    time.sleep(0.1)
    assert limite.en_curso == 1  # sigue ocupado: nada lo liberó antes de tiempo
    salir.set()
    hilo.join(5)
    assert limite.en_curso == 0 and limite.ejecutar(lambda: "si") == "si"


def test_el_parametro_interno_no_aparece_en_el_openapi():
    app, _ = _api()
    texto = json.dumps(app.openapi())
    assert "_peticion_de_consulta_costosa" not in texto


# ---------------------------------------------------------------------------
# statement_timeout -> 503 controlado
# ---------------------------------------------------------------------------

class _Cancelada(Exception):
    sqlstate = "57014"


class _Caida(Exception):
    sqlstate = "08006"


def test_consulta_cancelada_por_tiempo_es_503_controlado_y_otro_fallo_de_base_sigue_igual():
    app, clave = _api()

    def lanzar(origen):
        class Lector:
            def ejecutar(self, *a, **kw):
                raise OperationalError("SELECT secreto", {}, origen)
        return lambda: Lector()

    c = TestClient(app, client=fx.LOCAL)
    app.dependency_overrides[d.consultar_resumen] = lanzar(_Cancelada("canceling statement due to statement timeout"))
    r = c.get("/api/v1/juegos/BALOTO/estadisticas/resumen", headers={"X-API-Key": clave})
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "consulta_cancelada"
    assert r.headers["retry-after"] == "5" and "SELECT" not in r.text and "statement" not in r.text
    app.dependency_overrides[d.consultar_resumen] = lanzar(_Caida("server closed the connection"))
    r = c.get("/api/v1/juegos/BALOTO/estadisticas/resumen", headers={"X-API-Key": clave})
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "base_no_disponible"
    assert "retry-after" not in r.headers


# ---------------------------------------------------------------------------
# Opciones del motor
# ---------------------------------------------------------------------------

def _ajustes(url="postgresql+psycopg://u:p@h/prueba", **extra):
    base = {"database_url": url, "base_tiempo_maximo_consulta_ms": 0, "base_tiempo_maximo_inactiva_ms": 0,
            "base_pool_tamano": 0, "base_pool_desborde": 0, "base_pool_espera_s": 0.0}
    return SimpleNamespace(**{**base, **extra})


def test_motor_por_defecto_identico_al_de_siempre():
    assert opciones_del_motor(_ajustes()) == {"pool_pre_ping": True, "future": True}
    assert opciones_del_motor(_ajustes("sqlite:///x.sqlite")) == {"pool_pre_ping": True, "future": True}
    assert opciones_del_motor(Settings(_env_file=None)) == {"pool_pre_ping": True, "future": True}


def test_motor_privado_fija_tiempos_y_pool():
    o = opciones_del_motor(_ajustes(base_tiempo_maximo_consulta_ms=1500, base_tiempo_maximo_inactiva_ms=5000,
                                    base_pool_tamano=4, base_pool_desborde=2, base_pool_espera_s=2.5))
    assert o["connect_args"] == {"options": "-c statement_timeout=1500 -c idle_in_transaction_session_timeout=5000"}
    assert (o["pool_size"], o["max_overflow"], o["pool_timeout"]) == (4, 2, 2.5)


@pytest.mark.parametrize("extra", [{"base_tiempo_maximo_consulta_ms": -1}, {"base_pool_tamano": -1},
                                   {"base_pool_espera_s": -1.0}])
def test_motor_rechaza_negativos(extra):
    with pytest.raises(ValueError):
        opciones_del_motor(_ajustes(**extra))


def test_motor_rechaza_tiempos_fuera_de_postgresql():
    with pytest.raises(ValueError):
        opciones_del_motor(_ajustes("sqlite:///x.sqlite", base_tiempo_maximo_consulta_ms=100))


# ---------------------------------------------------------------------------
# Punto de entrada privado: secretos en archivos y condiciones
# ---------------------------------------------------------------------------

def _secretos(tmp_path):
    url, claves = tmp_path / "url", tmp_path / "claves"
    url.write_text("postgresql+psycopg://lector:sintetica@172.30.3.30:5432/loteria_prueba\n", encoding="ascii")
    claves.write_text("# rotacion\npasarela-1:sha256:" + "a" * 64 + "\n\npasarela-2:sha256:" + "b" * 64 + "\n",
                      encoding="ascii")
    return {"DATABASE_URL_ARCHIVO": str(url), "API_PUBLICA_CLAVES_ARCHIVO": str(claves)}


def test_cargar_secretos_desde_archivos(tmp_path):
    entorno = _secretos(tmp_path)
    perfil_privado.cargar_secretos(entorno)
    assert entorno["DATABASE_URL"].startswith("postgresql+psycopg://lector:")
    assert entorno["API_PUBLICA_CLAVES"] == "pasarela-1:sha256:" + "a" * 64 + ",pasarela-2:sha256:" + "b" * 64


@pytest.mark.parametrize("caso", ["en_entorno", "sin_archivo", "inexistente", "vacio", "no_ascii", "dos_urls"])
def test_cargar_secretos_cerrado_ante_el_fallo(tmp_path, caso):
    entorno = _secretos(tmp_path)
    if caso == "en_entorno":
        entorno["API_PUBLICA_CLAVES"] = "x:sha256:" + "c" * 64
    elif caso == "sin_archivo":
        del entorno["DATABASE_URL_ARCHIVO"]
    elif caso == "inexistente":
        entorno["DATABASE_URL_ARCHIVO"] = str(tmp_path / "no")
    elif caso == "vacio":
        (tmp_path / "claves").write_text("# nada\n\n", encoding="ascii")
    elif caso == "no_ascii":
        (tmp_path / "url").write_bytes("postgresql://lector:contraseña@h/p".encode())
    elif caso == "dos_urls":
        (tmp_path / "url").write_text("postgresql://a@h/p\npostgresql://b@h/p\n", encoding="ascii")
    with pytest.raises(perfil_privado.PerfilPrivadoNoValido) as error:
        perfil_privado.cargar_secretos(entorno)
    assert "sintetica" not in str(error.value) and "contraseña" not in str(error.value)


def _almacenes(tmp_path):
    rutas = {}
    for nombre in perfil_privado.ALMACENES_DE_CONSULTA:
        (tmp_path / nombre).mkdir()
        rutas[nombre] = str(tmp_path / nombre)
    return rutas


def _settings_privados(tmp_path, **extra):
    valores = {"database_url": "postgresql+psycopg://lector:sintetica@h/loteria_prueba",
               "base_tiempo_maximo_consulta_ms": 1500, "base_tiempo_maximo_inactiva_ms": 5000,
               **_almacenes(tmp_path), **extra}
    return SimpleNamespace(**valores)


def _conf_privada(**extra):
    conf, _ = fx.configuracion("pasarela", hosts=frozenset({HOST_API}), clientes=frozenset({PASARELA[0]}),
                               concurrencia_costosas=2)
    return conf.__class__(**{**conf.__dict__, **extra})


def test_comprobar_admite_el_perfil_completo(tmp_path):
    perfil_privado.comprobar(_settings_privados(tmp_path), _conf_privada(), es_root=False)


@pytest.mark.parametrize("cambio,texto", [
    ({"conf": {"claves": ()}}, "sin huellas"),
    ({"settings": {"database_url": "sqlite:///x"}}, "PostgreSQL"),
    ({"conf": {"hosts": frozenset(), "clientes": frozenset()}}, "API_PUBLICA_HOSTS"),
    ({"conf": {"cors_origenes": ("https://x.prueba",)}}, "CORS"),
    ({"conf": {"concurrencia_costosas": 0}}, "CONCURRENCIA"),
    ({"settings": {"base_tiempo_maximo_consulta_ms": 0}}, "BASE_TIEMPO"),
    ({"settings": {"base_tiempo_maximo_inactiva_ms": 0}}, "BASE_TIEMPO"),
    ({"settings": {"directorio_pronosticos_experimentales": "/no/existe"}}, "DIRECTORIO_PRONOSTICOS"),
    ({"root": True}, "root"),
])
def test_comprobar_no_arranca_si_falta_una_condicion(tmp_path, cambio, texto):
    settings = _settings_privados(tmp_path, **cambio.get("settings", {}))
    with pytest.raises(perfil_privado.PerfilPrivadoNoValido) as error:
        perfil_privado.comprobar(settings, _conf_privada(**cambio.get("conf", {})), es_root=cambio.get("root", False))
    assert texto in str(error.value) and "sintetica" not in str(error.value)


def test_un_almacen_que_es_archivo_no_cuenta_como_presente(tmp_path):
    settings = _settings_privados(tmp_path)
    falso = tmp_path / "falso"
    falso.write_text("", encoding="ascii")
    settings.directorio_carteras_modelos = str(falso)
    with pytest.raises(perfil_privado.PerfilPrivadoNoValido, match="DIRECTORIO_CARTERAS_MODELOS"):
        perfil_privado.comprobar(settings, _conf_privada(), es_root=False)


# ---------------------------------------------------------------------------
# DAT-07: importar la API no crea almacenes (hallazgo de la verificacion con montaje de solo lectura)
# ---------------------------------------------------------------------------

def test_importar_la_api_publica_no_crea_carpetas_en_el_directorio_de_trabajo(tmp_path):
    """Antes de E10.2, `app.api.dependencies` construia `HtmlFileStorage()` al importarse y creaba
    `storage/html` en el directorio actual: con la raiz de solo lectura la API privada no arrancaba."""
    import os
    import subprocess
    import sys

    entorno = {k: v for k, v in os.environ.items() if not k.startswith(("DIRECTORIO_", "API_PUBLICA_"))}
    entorno.update({"PYTHONPATH": str(fx.BACKEND), "PYTHONDONTWRITEBYTECODE": "1",
                    "DATABASE_URL": "sqlite:///" + (tmp_path / "sin_uso.sqlite").as_posix()})
    r = subprocess.run([sys.executable, "-B", "-c", "import app.api.publica.aplicacion, app.api.dependencies"],
                       cwd=tmp_path, env=entorno, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_el_registro_de_conectores_se_crea_una_sola_vez_al_pedirlo(tmp_path, monkeypatch):
    from app.api import dependencies as dep

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dep, "_connector_registry", None)
    primero = dep.get_connector_registry()
    assert (tmp_path / "storage" / "html").is_dir()  # la aplicacion local la sigue creando al usarla
    assert dep.get_connector_registry() is primero
