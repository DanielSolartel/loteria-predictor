"""Fase 5 (estadísticas descriptivas): páginas, panel, API, navegación e impresión.

Aplicación FastAPI real con repositorios en memoria (sin PostgreSQL) e históricos SINTÉTICOS."""
from __future__ import annotations

import re
from datetime import date, timedelta
from html import unescape
from pathlib import Path

import pytest
from tests import consola_sesion
from sqlalchemy.exc import OperationalError

from app.api import dependencies as dep
from app.api.web.navegacion_descriptivas import juegos_nav, navegacion_fase5, reglas_estaticas
from app.api.web.routers.estadisticas_descriptivas import formatear
from app.application.estadisticas import descriptivas as de
from app.application.use_cases.consultar_estadisticas_descriptivas import ConsultarEstadisticasDescriptivas
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx

RAIZ = Path(__file__).resolve().parents[2]
JUEGOS = {"baloto": "BALOTO", "baloto-revancha": "BALOTO_REVANCHA", "miloto": "MILOTO", "colorloto": "COLORLOTO"}


def _cliente(tmp_path, *, conectada=True, numericos=None, colorloto=None, consultar=None):
    hoy = date.today()
    inicio = hoy - timedelta(days=3 * 149 + 2)
    if numericos is None:
        numericos = {"BALOTO": fx.historico_numerico("BALOTO", 150, inicio=inicio),
                     "BALOTO_REVANCHA": fx.historico_numerico("BALOTO_REVANCHA", 150, inicio=inicio),
                     "MILOTO": fx.historico_numerico("MILOTO", 90, primero=531, inicio=inicio)}
    if colorloto is None:
        colorloto = fx.historico_colorloto(100, inicio=inicio)
    juegos, resultados, colores = fx.repositorios(numericos, colorloto=colorloto)
    c = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(tmp_path), conectada=conectada)
    from app.main import app

    app.dependency_overrides[dep.get_consultar_estadisticas_descriptivas] = (
        consultar or (lambda: ConsultarEstadisticasDescriptivas(juegos, resultados, colores)))

    def prohibido():
        raise AssertionError("la Fase 5 no usa la caché persistida de estadísticas")

    app.dependency_overrides[dep.get_calcular_y_persistir_estadistica] = prohibido
    return c


@pytest.fixture
def cliente(tmp_path):
    c = _cliente(tmp_path)
    yield c
    from app.main import app
    app.dependency_overrides = {}


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def _paginas():
    for slug, codigo in JUEGOS.items():
        for m in de.metricas_nuevas(reglas_estaticas(slug)):
            yield slug, codigo, m


# --- páginas y API ----------------------------------------------------------------------------------

def test_cada_pagina_nueva_responde_y_coincide_con_la_api(cliente):
    for slug, codigo, m in _paginas():
        r = cliente.get(f"/estadisticas/{slug}/{m.slug}")
        assert r.status_code == 200, (slug, m.slug, r.text[:300])
        assert '<body class="producto1-impresion">' in r.text
        api = cliente.get(f"/api/estadisticas/{codigo}/descriptivas/{m.slug}")
        assert api.status_code == 200, (codigo, m.slug)
        datos = api.json()
        assert datos["metrica"]["estado"] == "ok" and datos["muestra"]["total_sorteos"] > 0
        texto = _texto(r.text)
        assert m.titulo in texto
        for t in datos["metrica"]["tablas"]:  # cada celda de la primera fila aparece con su formato
            assert t["titulo"] in texto, (m.slug, t["titulo"])
            for col in t["columnas"]:
                valor = formatear(t["filas"][0][col["clave"]], col["formato"])
                assert valor in texto, (slug, m.slug, col["clave"], valor)


def test_la_grafica_tiene_una_barra_por_valor_de_su_tabla(cliente):
    r = cliente.get("/estadisticas/baloto/distribucion-decenas")
    datos = cliente.get("/api/estadisticas/BALOTO/descriptivas/distribucion-decenas").json()["metrica"]
    tabla = next(t for t in datos["tablas"] if t["id"] == datos["grafica"]["tabla"])
    svg = r.text.split('<svg class="descriptivas-grafica', 1)[1].split("</svg>", 1)[0]
    assert svg.count("<rect") == len([f for f in tabla["filas"] if f[datos["grafica"]["valor"]] is not None]) == 5
    assert 'role="img"' in r.text.split('<svg class="descriptivas-grafica', 1)[1][:200]
    assert f"Mismos valores en la tabla «{tabla['titulo']}»" in r.text


def test_panel_de_los_cuatro_juegos_y_sus_enlaces(cliente, tmp_path):
    from app.main import app

    tolerante = consola_sesion.cliente_de_consola(app, raise_server_exceptions=False)  # E10.1: sesión explícita
    for slug, codigo in JUEGOS.items():
        r = cliente.get(f"/estadisticas/{slug}/panel?hasta_numero_sorteo=2150")
        assert r.status_code == 200
        api = cliente.get(f"/api/estadisticas/{codigo}/panel?hasta_numero_sorteo=2150").json()
        entradas = [e for g in api["grupos"] for e in g["metricas"]]
        texto = _texto(r.text)
        for e in entradas:
            assert e["titulo"] in texto
            if not e["aplica"]:
                assert "No aplica" in texto
                continue
            enlace = f'/estadisticas/{slug}/{e["slug"]}?hasta_numero_sorteo=2150'
            assert f'href="{enlace}"' in r.text, enlace
            destino = (cliente if e["nueva"] else tolerante).get(enlace)
            # las páginas anteriores las atiende su router (aquí sin su repositorio SQL): nunca 404
            assert destino.status_code != 404, enlace
            if e["nueva"]:
                assert destino.status_code == 200, enlace


def test_corte_vacio_y_parametros_validos(cliente):
    assert cliente.get("/estadisticas/baloto/distribucion-sumas?hasta_numero_sorteo=").status_code == 200
    assert cliente.get("/estadisticas/miloto/frecuencia-numeros-por-mes?mes=3").status_code == 200
    assert cliente.get("/estadisticas/colorloto/frecuencia-numeros-por-dia-semana?dia_semana=martes").status_code == 200
    r = cliente.get("/estadisticas/baloto/frecuencia-numeros-por-anio?anio=1999")
    assert r.status_code == 200 and "No hay sorteos en 1999" in r.text


@pytest.mark.parametrize("url", [
    "/estadisticas/baloto/distribucion-sumas?hasta_numero_sorteo=0",
    "/estadisticas/baloto/distribucion-sumas?hasta_numero_sorteo=-3",
    "/estadisticas/baloto/distribucion-sumas?hasta_numero_sorteo=texto",
    "/estadisticas/baloto/frecuencia-numeros-por-mes?mes=13",
    "/estadisticas/baloto/frecuencia-numeros-por-dia-semana?dia_semana=funday",
    "/estadisticas/miloto/comparacion-frecuencia-numeros-por-ventana?ventana=7",
    "/estadisticas/miloto/comparacion-frecuencia-numeros-por-ventana?ventana=20.0",
    "/api/estadisticas/BALOTO/descriptivas/distribucion-sumas?anio=2025",
    "/api/estadisticas/BALOTO/descriptivas/comparacion-frecuencia-numeros-por-ventana?ventana=7",
    "/api/estadisticas/BALOTO/panel?hasta_numero_sorteo=0",
])
def test_parametros_invalidos_422(cliente, url):
    assert cliente.get(url).status_code == 422, url


@pytest.mark.parametrize("url", [
    "/estadisticas/quini/panel",
    "/estadisticas/miloto/atrasos-superbalota",
    "/estadisticas/colorloto/repeticion-superbalota",
    "/estadisticas/colorloto/distribucion-decenas",
    "/estadisticas/colorloto/independencia-pares",
    "/api/estadisticas/QUINI/panel",
    "/api/estadisticas/MILOTO/descriptivas/frecuencia-superbalota-por-anio",
    "/api/estadisticas/COLORLOTO/descriptivas/distribucion-sumas",
    "/api/estadisticas/BALOTO/descriptivas/no-existe",
])
def test_lo_que_no_aplica_responde_404_con_motivo(cliente, url):
    r = cliente.get(url)
    assert r.status_code == 404, url
    if "miloto/atrasos" in url or "MILOTO" in url:
        assert "no tiene superbalota" in r.json()["detail"]
    if "COLORLOTO/descriptivas/distribucion-sumas" in url:
        assert "/estadisticas/colorloto/distribucion-sumas" in r.json()["detail"]


def test_sin_base_de_datos_la_pagina_lo_dice_y_la_api_responde_503(tmp_path):
    c = _cliente(tmp_path, conectada=False)
    try:
        for url in ("/estadisticas/baloto/panel", "/estadisticas/colorloto/pruebas-uniformidad"):
            r = c.get(url)
            assert r.status_code == 200 and "Sin conexión a la base de datos" in r.text and "<table" not in r.text
    finally:
        from app.main import app
        app.dependency_overrides = {}

    class SinBase:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, nombre):
            def fallo(*a, **k):
                raise OperationalError("SELECT", {}, Exception("sin base"))
            return fallo

    c = _cliente(tmp_path, consultar=lambda: SinBase())
    try:
        assert c.get("/api/estadisticas/BALOTO/panel").status_code == 503
        assert c.get("/api/estadisticas/BALOTO/descriptivas/distribucion-sumas").status_code == 503
    finally:
        from app.main import app
        app.dependency_overrides = {}


def test_juego_sin_sorteos_no_muestra_ceros(tmp_path):
    c = _cliente(tmp_path, numericos={}, colorloto=[])
    try:
        r = c.get("/estadisticas/miloto/panel")
        assert r.status_code == 200 and "No hay sorteos cargados para este juego" in r.text
        r = c.get("/estadisticas/miloto/distribucion-sumas")
        assert r.status_code == 200 and "No hay sorteos hasta el corte indicado" in r.text and "<table" not in r.text
        assert c.get("/api/estadisticas/MILOTO/descriptivas/distribucion-sumas").json()["metrica"]["estado"] == "sin_datos"
    finally:
        from app.main import app
        app.dependency_overrides = {}


# --- navegación ---------------------------------------------------------------------------------------

def test_navegacion_conserva_el_corte_dentro_del_juego_y_no_entre_juegos():
    nav = navegacion_fase5("baloto", 2600, "distribucion-sumas")
    assert nav["panel"] == "/estadisticas/baloto/panel?hasta_numero_sorteo=2600"
    activa = [m for m in nav["metricas"] if m["activa"]]
    assert [m["slug"] for m in activa] == ["distribucion-sumas"]
    assert all(m["url"].endswith("?hasta_numero_sorteo=2600") for m in nav["metricas"])
    destinos = {j["slug"]: j["url"] for j in juegos_nav("atrasos-superbalota", "baloto")}
    assert destinos == {"baloto": "/estadisticas/baloto/atrasos-superbalota",
                        "baloto-revancha": "/estadisticas/baloto-revancha/atrasos-superbalota",
                        "miloto": "/estadisticas/miloto/panel", "colorloto": "/estadisticas/colorloto/panel"}
    assert {j["slug"]: j["url"] for j in juegos_nav("distribucion-sumas", "miloto")}["colorloto"] == \
        "/estadisticas/colorloto/distribucion-sumas"  # página anterior de ColorLoto


def test_paginas_anteriores_enlazan_la_fase5_sin_tocar_sus_pestanas():
    plantillas = RAIZ / "app" / "templates" / "estadisticas"
    numericas = [p for p in plantillas.glob("*.html") if "{% for m in metricas_nav %}" in p.read_text(encoding="utf-8")]
    assert len(numericas) == 12
    for p in numericas:
        assert '{% include "descriptivas/_navegacion.html" %}' in p.read_text(encoding="utf-8"), p.name
    colorloto = (plantillas / "partials" / "navegacion_colorloto.html").read_text(encoding="utf-8")
    assert colorloto.count('<li class="nav-item">') == 31 and '{% include "descriptivas/_navegacion.html" %}' in colorloto


def test_resumen_indice_y_menu_enlazan_el_panel(cliente):
    assert 'href="/estadisticas/miloto/panel?hasta_numero_sorteo=560"' in cliente.get(
        "/estadisticas/miloto/resumen?hasta_numero_sorteo=560").text
    assert 'href="/estadisticas/colorloto/panel"' in cliente.get("/estadisticas/colorloto/resumen").text
    indice = cliente.get("/estadisticas").text
    assert all(f'href="/estadisticas/{s}/panel"' in indice for s in JUEGOS)
    assert 'href="/estadisticas/baloto/panel"' in (RAIZ / "app" / "templates" / "base.html").read_text(encoding="utf-8")


def test_navegacion_de_la_pagina_nueva(cliente):
    r = cliente.get("/estadisticas/baloto-revancha/repeticion-superbalota?hasta_numero_sorteo=2150")
    assert 'href="/estadisticas/baloto-revancha/panel?hasta_numero_sorteo=2150"' in r.text
    assert 'href="/estadisticas/miloto/panel"' in r.text  # MiLoto no tiene superbalota: va a su panel, sin corte
    assert 'aria-current="page">Repetición de superbalota' in r.text


# --- impresión ------------------------------------------------------------------------------------------

def test_reglas_de_impresion_de_la_fase5_acotadas_a_sus_clases():
    css = (RAIZ / "app" / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    impresion = css[css.index("@media print"):]
    for regla in ("body.producto1-impresion .descriptivas-nav {\n        display: none;",
                  "body.producto1-impresion .descriptivas-cabecera {", "body.producto1-impresion svg.descriptivas-grafica {"):
        assert regla in impresion, regla
    usados = set()
    for p in (RAIZ / "app" / "templates").rglob("*.html"):
        usados |= {(p.parent.name, c) for c in re.findall(r"descriptivas-[a-z]+", p.read_text(encoding="utf-8"))}
    assert {carpeta for carpeta, _ in usados} == {"descriptivas"}
