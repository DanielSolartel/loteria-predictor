"""E10.1: flujos HTTP reales de la consola (`app.main:app`) con almacén de prueba y cuentas temporales."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seguridad_consola import almacen as al
from app.seguridad_consola.consola import COOKIE_PRESESION, COOKIE_SESION
from tests import consola_sesion as cs

BASE = "http://localhost:8000"


@pytest.fixture(autouse=True)
def _estado_aislado():
    """Restaura el almacén inyectado y las sustituciones de esta app compartida (no desactiva nada)."""
    previo, sustituciones = getattr(app.state, "almacen_seguridad", None), dict(app.dependency_overrides)
    yield
    app.state.almacen_seguridad = previo
    app.dependency_overrides.clear()
    app.dependency_overrides.update(sustituciones)


def _anonimo(client=cs.LOCAL, **kw):
    return TestClient(app, base_url=BASE, client=client, **kw)


def _token_acceso(c) -> str:
    return re.search(r'name="csrf_token" value="([0-9a-f]{64})"', c.get("/acceso").text).group(1)


# ------------------------------------------------------------------ fallo cerrado
def test_sin_almacen_ninguna_ruta_de_negocio_ni_el_acceso_atienden(tmp_path):
    app.state.almacen_seguridad = al.AlmacenSeguridad(tmp_path / "no-existe" / "seguridad.sqlite3")
    c = _anonimo()
    for ruta in ("/", "/sorteos", "/automatizacion", "/acceso"):
        r = c.get(ruta, follow_redirects=False)
        assert r.status_code == 503 and 'data-consola-codigo="consola_no_disponible"' in r.text
        assert "Traceback" not in r.text and str(tmp_path) not in r.text
    assert c.get("/api/juegos").json()["codigo"] == "consola_no_disponible"
    assert c.post("/sorteos", data={}).status_code == 503
    assert not (tmp_path / "no-existe").exists()


def test_almacen_corrupto_cierra_la_consola(tmp_path):
    almacen = cs.almacen_de_prueba(tmp_path)
    app.state.almacen_seguridad = almacen
    almacen.archivo.write_bytes(b"x" * 4096)
    assert _anonimo().get("/").status_code == 503


# ------------------------------------------------------------------ límite local
@pytest.mark.parametrize("cliente", [("10.8.0.2", 5000), ("100.64.0.7", 5000), ("192.168.1.20", 5000), ("203.0.113.9", 5000)])
def test_cliente_remoto_o_vpn_rechazado_aunque_tenga_sesion(cliente):
    c = cs.cliente_autenticado(app, "administrador", client=cliente)
    for metodo, ruta in (("GET", "/"), ("GET", "/static/js/consola_csrf.js"), ("POST", "/automatizacion/pausar"),
                         ("GET", "/acceso")):
        assert c.request(metodo, ruta, follow_redirects=False).status_code == 403


@pytest.mark.parametrize("cabecera", ["X-Forwarded-For", "Forwarded", "X-Real-IP", "X-Forwarded-Host"])
def test_cabeceras_de_reenvio_rechazadas_incluso_desde_loopback(cabecera):
    c = cs.cliente_autenticado(app, "administrador")
    assert c.get("/", headers={cabecera: "127.0.0.1"}).status_code == 403


@pytest.mark.parametrize("host", ["evil.example", "localhost.evil.example", "192.168.1.5:8000"])
def test_host_no_local_rechazado(host):
    c = cs.cliente_autenticado(app, "administrador")
    assert c.get("/", headers={"Host": host}).status_code == 403


def test_estaticos_y_acceso_legitimos_funcionan():
    cs.cliente_autenticado(app, "lector")  # provisiona
    c = _anonimo()
    assert c.get("/static/js/consola_csrf.js").status_code == 200
    assert c.get("/static/css/styles.css").status_code == 200
    r = c.get("/acceso")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"


def test_documentacion_interna_no_se_publica():
    c = cs.cliente_autenticado(app, "administrador")
    for ruta in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        assert c.get(ruta).status_code == 404


# ------------------------------------------------------------------ acceso y salida
def test_acceso_correcto_renueva_identificador_y_cookies_seguras():
    almacen = cs.almacen_de_prueba(cuentas=(("ana", "operador"),))
    app.state.almacen_seguridad = almacen
    c = _anonimo()
    token = _token_acceso(c)
    presesion = c.cookies.get(COOKIE_PRESESION)
    r = c.post("/acceso", data={"csrf_token": token, "usuario": "ana", "contrasena": cs.CONTRASENA_PRUEBA,
                                "siguiente": "/sorteos"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/sorteos"
    galletas = r.headers.get_list("set-cookie")
    sesion = next(g for g in galletas if g.startswith(COOKIE_SESION + "="))
    assert "httponly" in sesion.lower() and "samesite=strict" in sesion.lower() and "path=/" in sesion.lower()
    assert "secure" not in sesion.lower()  # HTTP local soportado: no se finge TLS
    sid = c.cookies.get(COOKIE_SESION)
    assert sid and sid != presesion and al.identificador_valido(sid)
    assert len(al._hash(sid)) == 64 and c.get("/").status_code == 200


def test_mismo_mensaje_para_usuario_inexistente_y_contrasena_incorrecta():
    app.state.almacen_seguridad = cs.almacen_de_prueba(cuentas=(("ana", "lector"),))
    textos = []
    for usuario in ("ana", "nadie"):
        c = _anonimo()
        r = c.post("/acceso", data={"csrf_token": _token_acceso(c), "usuario": usuario, "contrasena": "mala-contrasena-x"})
        assert r.status_code == 401 and COOKIE_SESION not in r.headers.get("set-cookie", "")
        textos.append(re.search(r"data-acceso-mensaje>([^<]+)<", r.text).group(1))
    assert textos[0] == textos[1] == "Usuario o contraseña no válidos."


def test_bloqueo_tras_intentos_fallidos_y_respuesta_429():
    almacen = cs.almacen_de_prueba(cuentas=(("ana", "lector"),))
    app.state.almacen_seguridad = almacen
    c = _anonimo()
    r = c.post("/acceso", data={"csrf_token": _token_acceso(c), "usuario": "ana", "contrasena": "mala-contrasena-x"})
    assert r.status_code == 401
    r = c.post("/acceso", data={"csrf_token": _token_acceso(c), "usuario": "ana", "contrasena": cs.CONTRASENA_PRUEBA})
    assert r.status_code == 429 and r.headers["retry-after"] and "Demasiados intentos" in r.text


@pytest.mark.parametrize("caso", ["sin_token", "token_incorrecto", "sin_presesion", "token_de_otra_presesion", "origen_ajeno"])
def test_csrf_de_presesion(caso):
    app.state.almacen_seguridad = cs.almacen_de_prueba(cuentas=(("ana", "lector"),))
    c, otro = _anonimo(), _anonimo()
    token = _token_acceso(c)
    datos = {"csrf_token": token, "usuario": "ana", "contrasena": cs.CONTRASENA_PRUEBA}
    cabeceras = {}
    if caso == "sin_token":
        datos.pop("csrf_token")
    elif caso == "token_incorrecto":
        datos["csrf_token"] = "0" * 64
    elif caso == "sin_presesion":
        c.cookies.clear()
    elif caso == "token_de_otra_presesion":
        datos["csrf_token"] = _token_acceso(otro)
    else:
        cabeceras = {"Origin": "http://evil.example"}
    r = c.post("/acceso", data=datos, headers=cabeceras, follow_redirects=False)
    assert r.status_code == 403 and c.cookies.get(COOKIE_SESION) is None


def test_salida_invalida_la_sesion_en_el_servidor():
    c = cs.cliente_autenticado(app, "lector")
    sid = c.cookies.get(COOKIE_SESION)
    assert c.post("/salir", follow_redirects=False).status_code == 303
    robada = _anonimo()
    robada.cookies.set(COOKIE_SESION, sid)
    assert robada.get("/", follow_redirects=False).status_code == 303  # al acceso


def test_salida_exige_csrf():
    c = cs.cliente_autenticado(app, "lector")
    assert c.post("/salir", headers={"X-CSRF-Token": "x" * 64}, follow_redirects=False).status_code == 403
    assert c.get("/").status_code == 200


@pytest.mark.parametrize("siguiente,esperado", [("/sorteos?juego=x", "/sorteos?juego=x"), ("//evil.example", "/"),
                                                 ("http://evil.example", "/"), ("/\\evil.example", "/"), ("/acceso", "/")])
def test_siguiente_solo_rutas_propias(siguiente, esperado):
    app.state.almacen_seguridad = cs.almacen_de_prueba(cuentas=(("ana", "lector"),))
    c = _anonimo()
    r = c.post("/acceso", data={"csrf_token": _token_acceso(c), "usuario": "ana", "contrasena": cs.CONTRASENA_PRUEBA,
                                "siguiente": siguiente}, follow_redirects=False)
    assert r.headers["location"] == esperado


# ------------------------------------------------------------------ sin sesión, caducidad y revocación
def test_sin_sesion_redirige_html_htmx_y_rest():
    cs.cliente_autenticado(app, "lector")
    c = _anonimo()
    r = c.get("/carteras?x=1", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/acceso?siguiente=%2Fcarteras%3Fx%3D1"
    r = c.get("/sorteos", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code == 401 and r.headers["hx-redirect"].startswith("/acceso")
    assert c.get("/api/juegos").status_code == 401


def test_sesion_caducada_y_revocada_por_cli():
    reloj = type("R", (), {"t": 1_800_000_000.0, "__call__": lambda s: s.t})()
    almacen = cs.almacen_de_prueba(cuentas=(("ana", "operador"),), reloj=reloj)
    c = cs.cliente_autenticado(app, "operador", usuario="ana", almacen=almacen)
    assert c.get("/").status_code == 200
    reloj.t += al.INACTIVIDAD + 1
    assert c.get("/", follow_redirects=False).status_code == 303
    c = cs.cliente_autenticado(app, "operador", usuario="ana", almacen=almacen)
    otra_instancia = al.AlmacenSeguridad(almacen.archivo, parametros=cs.PARAMETROS_PRUEBA, minimos=cs.PARAMETROS_PRUEBA)
    otra_instancia.revocar_sesiones("ana")  # como la CLI, desde otra conexión
    assert c.get("/", follow_redirects=False).status_code == 303


def test_sesion_persiste_tras_reiniciar_el_almacen():
    c = cs.cliente_autenticado(app, "lector")
    app.state.almacen_seguridad = al.AlmacenSeguridad(c.almacen.archivo, parametros=cs.PARAMETROS_PRUEBA,
                                                      minimos=cs.PARAMETROS_PRUEBA)
    assert c.get("/").status_code == 200


def test_cambio_de_rol_se_aplica_sin_conservar_privilegios():
    almacen = cs.almacen_de_prueba(cuentas=(("admin", "administrador"), ("ana", "administrador")))
    c = cs.cliente_autenticado(app, "administrador", usuario="ana", almacen=almacen)
    almacen.cambiar_rol("ana", "lector")
    assert c.get("/", follow_redirects=False).status_code == 303  # sesión revocada
    c = cs.cliente_autenticado(app, "lector", usuario="ana", almacen=almacen)
    assert c.post("/automatizacion/comprobar", data={"juego": "todos"}).status_code == 403


# ------------------------------------------------------------------ CSRF de sesión y origen
@pytest.mark.parametrize("caso", ["ausente", "incorrecto", "de_otra_sesion", "en_la_url", "origen_ajeno", "sec_fetch_cross"])
def test_csrf_de_sesion_en_escrituras(caso):
    almacen = cs.almacen_de_prueba(cuentas=(("admin", "administrador"), ("ana", "administrador")))
    c = cs.cliente_autenticado(app, "administrador", almacen=almacen)
    otra = cs.cliente_autenticado(app, "administrador", usuario="ana", almacen=almacen)
    cabeceras, url = {}, "/colores"
    if caso == "ausente":
        c.csrf = None
    elif caso == "incorrecto":
        cabeceras["X-CSRF-Token"] = "f" * 64
    elif caso == "de_otra_sesion":
        cabeceras["X-CSRF-Token"] = otra.csrf
    elif caso == "en_la_url":
        url, token, c.csrf = f"/colores?csrf_token={c.csrf}", c.csrf, None
    elif caso == "origen_ajeno":
        cabeceras["Origin"] = "http://evil.example"
    else:
        cabeceras["Sec-Fetch-Site"] = "cross-site"
    r = c.post(url, data={"codigo": "ZZ", "nombre": "Prueba"}, headers=cabeceras)
    assert r.status_code == 403
    assert all(e["evento"] != "escritura_negocio" for e in almacen.auditoria(20))


def test_formulario_con_campo_csrf_tambien_vale():
    c = cs.cliente_autenticado(app, "administrador")
    token, c.csrf = c.csrf, None
    r = c.post("/automatizacion/desconocida", data={"csrf_token": token, "juego": "todos"})
    assert r.status_code == 422  # pasó el CSRF; la acción desconocida no se despacha


def test_interfaz_muestra_identidad_csrf_y_salida():
    c = cs.cliente_autenticado(app, "operador")
    html = c.get("/").text
    assert 'data-consola-usuario="operadora"' in html and f'content="{c.csrf}"' in html
    assert '<script src="/static/js/consola_csrf.js" defer></script>' in html and 'action="/salir"' in html
    assert "<body>" in html  # el <body> de las páginas no cambia (pruebas de impresión de Productos 1-2)
    js = c.get("/static/js/consola_csrf.js").text
    assert "htmx:configRequest" in js and "X-CSRF-Token" in js and 'name = "csrf_token"' in js
