"""Fase 9.1, pasarela: solo los recursos compilados de `dist/`, fallback de la
SPA acotado, 404 para recursos inexistentes, nada fuera de `dist/` y
cabeceras de seguridad en todas las respuestas."""
from __future__ import annotations

import json
import os

import pytest

from app.pasarela.aplicacion import CSP, SEGURIDAD
from tests.unit.pasarela import fixtures_pasarela as fp


@pytest.fixture
def entorno(tmp_path):
    with fp.destino_falso() as d:
        carpeta = fp.dist(tmp_path)
        yield d, fp.pasarela(d.destino, carpeta, fp.clave_sintetica()), carpeta


@pytest.mark.parametrize("url", ["/", "/juegos", "/juegos/BALOTO", "/juegos/COLORLOTO/sorteos",
                                 "/juegos/MILOTO/estadisticas/frecuencia-numeros-por-anio",
                                 "/simulaciones/344d4a67-798a-4b2f-85fc-0f53dd183e99", "/servicio", "/no-existe"])
def test_rutas_de_la_spa_reciben_index(entorno, url):
    _, app, _ = entorno
    r = fp.cliente(app).get(url + "?pagina=2")
    assert r.status_code == 200 and r.text == fp.INDICE and r.headers["content-type"] == "text/html; charset=utf-8"


@pytest.mark.parametrize("url, tipo", [("/assets/app-1.js", "text/javascript; charset=utf-8"),
                                       ("/assets/app-1.css", "text/css; charset=utf-8"),
                                       ("/favicon.svg", "image/svg+xml")])
def test_recursos_compilados_con_su_tipo(entorno, url, tipo):
    _, app, carpeta = entorno
    r = fp.cliente(app).get(url)
    assert r.status_code == 200 and r.headers["content-type"] == tipo
    assert r.content == (carpeta / url.lstrip("/")).read_bytes()


@pytest.mark.parametrize("url", ["/assets/no-existe.js", "/assets/app-1.js.map", "/favicon.ico", "/robots.txt",
                                 "/index.php", "/assets", "/assets/sub", "/assets/app-1.exe", "/README.md"])
def test_recursos_inexistentes_o_no_admitidos_son_404_y_no_index(entorno, url):
    _, app, _ = entorno
    r = fp.cliente(app).get(url)
    assert r.status_code == 404 and fp.INDICE not in r.text and r.headers["cache-control"] == "no-store"


def _enlazar(destino, enlace, *, carpeta: bool) -> bool:
    """Enlace simbolico; en Windows sin privilegio para crearlos, una union (junction)
    para la carpeta. Un enlace de archivo que el sistema no permite no se crea."""
    try:
        os.symlink(destino, enlace, target_is_directory=carpeta)
        return True
    except OSError:
        if carpeta and os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(destino), str(enlace))
            return True
        return False


def test_nada_fuera_de_dist_ni_enlaces_que_salen(entorno, tmp_path):
    _, app, carpeta = entorno
    secreto = tmp_path / "fuera.js"
    secreto.write_text("FUERA_DE_DIST", encoding="utf-8")
    urls = ["/assets/carpeta/fuera.js"]
    assert _enlazar(tmp_path, carpeta / "assets" / "carpeta", carpeta=True)
    if _enlazar(secreto, carpeta / "assets" / "enlace.js", carpeta=False):
        urls.append("/assets/enlace.js")
    for url in urls:
        r = fp.cliente(app).get(url)
        assert r.status_code == 404 and "FUERA_DE_DIST" not in r.text, url
    for ruta in (b"/assets/../../fuera.js", b"/assets/%2e%2e/fuera.js", b"/.git/config", b"/assets/.oculto.js"):
        estado, _, cuerpo = fp.crudo(app, ruta)
        assert estado == 400 and b"FUERA_DE_DIST" not in cuerpo


def test_sin_compilar_la_spa_se_informa_sin_rutas(tmp_path):
    with fp.destino_falso() as d:
        app = fp.pasarela(d.destino, tmp_path / "no-existe", fp.clave_sintetica())
        r = fp.cliente(app).get("/juegos/BALOTO")
        assert r.status_code == 503 and r.json()["error"]["codigo"] == "frontend_no_compilado"
        assert str(tmp_path) not in r.text
        assert fp.cliente(app).get("/assets/app-1.js").status_code == 404
        assert fp.cliente(app).get("/api/v1/salud").status_code == 200


@pytest.mark.parametrize("url", ["/", "/assets/app-1.js", "/assets/no.js", "/api/v1/salud", "/api/v1/docs",
                                 "/pasarela/configuracion"])
def test_cabeceras_de_seguridad_en_todas_las_respuestas(entorno, url):
    _, app, _ = entorno
    r = fp.cliente(app).get(url)
    for nombre, valor in SEGURIDAD.items():
        assert r.headers[nombre] == valor, (url, nombre)
    assert "frame-ancestors 'none'" in CSP and "'unsafe-inline'" not in CSP and "*" not in CSP
    assert len(r.headers["x-request-id"]) == 32


def test_configuracion_publica_de_la_spa(tmp_path):
    with fp.destino_falso() as d:
        clave = fp.clave_sintetica()
        sin = fp.pasarela(d.destino, fp.dist(tmp_path / "a"), clave)
        assert fp.cliente(sin).get("/pasarela/configuracion").json() == {"consola_local": None, "api": "v1"}
        con = fp.pasarela(d.destino, fp.dist(tmp_path / "b"), clave, consola_local="http://127.0.0.1:8000/")
        r = fp.cliente(con).get("/pasarela/configuracion")
        assert r.json() == {"consola_local": "http://127.0.0.1:8000/", "api": "v1"}
        assert clave not in r.text and json.dumps(r.json()).count("http") == 1
