"""Producto 1: presentacion de decenas, frecuencia de colores e impresion.

- «Números por decena»: porcentaje de TODOS los numeros extraidos
  (apariciones / (sorteos x numeros por sorteo) x 100), con el
  denominador visible; los campos existentes de la API se conservan.
- ColorLoto: la frecuencia de colores y de numeros se presenta como
  promedio de apariciones por sorteo, que puede superar 1.
- Impresion: reglas CSS solo dentro de `@media print`; el nombre del
  color queda como texto. La revision visual del PDF no se automatiza.
Historicos sinteticos."""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.application.estadisticas.resumen_juego import porcentaje_de_numeros_extraidos, resumen_juego_numerico
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx

RAIZ_BACKEND = Path(__file__).resolve().parents[2]


def test_ejemplos_reales_del_operador():
    assert round(porcentaje_de_numeros_extraidos(736, 636, 5), 1) == 23.1
    assert round(porcentaje_de_numeros_extraidos(105, 84, 5), 1) == 25.0
    assert porcentaje_de_numeros_extraidos(0, 0, 5) is None


@pytest.mark.parametrize("codigo,rango,n", [("BALOTO", (1, 43), 80), ("BALOTO_REVANCHA", (1, 43), 37),
                                            ("MILOTO", (1, 39), 84)])
def test_decenas_suman_100_y_conservan_los_campos_previos(codigo, rango, n):
    h = fx.historico_numerico(codigo, n, primero=1)
    r = resumen_juego_numerico(h, codigo_juego=codigo, nombre=codigo, rango=rango, cantidad_numeros=5,
                               rango_superbalota=None, hoy=date(2030, 1, 1))
    e = r["estadisticas"]
    dec = e["decenas_sobre_numeros_extraidos"]
    assert dec["denominador"] == {"sorteos": n, "numeros_por_sorteo": 5, "numeros_extraidos": n * 5}
    assert [f["valor"] for f in dec["filas"]] == [d["valor"] for d in e["decenas"]]
    total = 0.0
    for fila, previa in zip(dec["filas"], e["decenas"]):
        # Campos y significado previos intactos: `sorteos` = apariciones, `frecuencia_relativa` = por sorteo.
        assert fila["sorteos"] == previa["sorteos"] == fila["apariciones"]
        assert fila["frecuencia_relativa"] == previa["frecuencia_relativa"] == fila["apariciones"] / n
        assert fila["porcentaje_de_numeros_extraidos"] == pytest.approx(100 * fila["apariciones"] / (n * 5))
        assert 0 <= fila["porcentaje_de_numeros_extraidos"] <= 100
        total += round(fila["porcentaje_de_numeros_extraidos"], 1)
    assert sum(f["apariciones"] for f in dec["filas"]) == n * 5
    assert abs(total - 100.0) <= 0.05 * len(dec["filas"]) + 1e-9


def test_decenas_con_historico_vacio_o_corte_sin_sorteos():
    r = resumen_juego_numerico([], codigo_juego="MILOTO", nombre="MiLoto", rango=(1, 39), cantidad_numeros=5,
                               rango_superbalota=None, hoy=date(2030, 1, 1))
    assert r["estadisticas"] is None


@pytest.fixture
def cliente(tmp_path):
    hoy = date.today()
    inicio = hoy - timedelta(days=3 * 83 + 2)
    juegos, resultados, colores = fx.repositorios(
        {"BALOTO": fx.historico_numerico("BALOTO", 84, inicio=inicio),
         "MILOTO": fx.historico_numerico("MILOTO", 84, primero=1, inicio=inicio)},
        colorloto=fx.historico_colorloto(40, inicio=inicio))
    c = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(tmp_path))
    yield c
    from app.main import app
    app.dependency_overrides = {}


def _tabla_decenas(html: str) -> str:
    inicio = html.index("Números por decena")
    return html[inicio:html.index("</table>", inicio)]


@pytest.mark.parametrize("slug", ["baloto", "miloto"])
def test_pagina_decenas_muestra_porcentaje_de_numeros_extraidos(cliente, slug):
    r = cliente.get(f"/estadisticas/{slug}/resumen")
    assert r.status_code == 200
    tabla = _tabla_decenas(r.text)
    assert "84 sorteos × 5 números = 420 números extraídos" in tabla
    assert "% de los números extraídos" in tabla
    porcentajes = [float(x) for x in re.findall(r'<td class="text-end">(\d+\.\d)</td>', tabla)]
    assert porcentajes and all(p <= 100 for p in porcentajes)
    assert abs(sum(porcentajes) - 100.0) <= 0.05 * len(porcentajes) + 1e-9
    api = cliente.get(f"/api/estadisticas/{'BALOTO' if slug == 'baloto' else 'MILOTO'}/resumen").json()
    assert {"valor", "sorteos", "frecuencia_relativa"} <= set(api["estadisticas"]["decenas"][0])


def test_colorloto_promedio_por_sorteo_no_probabilidad(cliente):
    texto = cliente.get("/estadisticas/colorloto/resumen").text
    assert "Promedio de apariciones por sorteo" in texto and "no es una probabilidad" in texto.lower()
    assert "promedio por sorteo" in texto
    api = cliente.get("/api/estadisticas/COLORLOTO/resumen").json()
    fila = api["estadisticas"]["frecuencia_colores"]["todas"][0]
    assert set(fila) == {"valor", "apariciones", "frecuencia_relativa"}
    assert fila["frecuencia_relativa"] == fila["apariciones"] / 40


def test_colorloto_nombre_del_color_como_texto_para_imprimir(cliente):
    texto = cliente.get("/estadisticas/colorloto/resumen").text
    assert re.search(r'<span class="solo-impresion"> (amarillo|azul|rojo|verde|blanco|negro)</span>', texto)
    assert 'title="' in texto


def _bloque_de_impresion(css: str) -> str:
    inicio = css.index("@media print")
    return css[inicio:css.index("\n}\n", inicio) + 3]


def _selectores(bloque: str) -> list[str]:
    import re as _re
    sin_comentarios = _re.sub(r"/\*.*?\*/", "", bloque, flags=_re.S)
    cuerpo = sin_comentarios[sin_comentarios.index("{") + 1:]
    return [s.strip() for grupo in _re.findall(r"([^{}]+)\{", cuerpo) for s in grupo.split(",") if s.strip()]


def test_css_de_impresion_acotado_a_producto1():
    css = (RAIZ_BACKEND / "app" / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    assert css.count("@media print") == 1
    impresion = _bloque_de_impresion(css)
    selectores = _selectores(impresion)
    assert selectores and all(s.startswith("body.producto1-impresion ") for s in selectores), selectores
    assert "body.producto1-impresion details.detalle-bloques" in selectores
    assert not any(s.split()[-1] in ("details", "form", ".btn", "tr", "thead") and len(s.split()) == 1
                   for s in selectores)
    for regla in (".tabla-desplazable", "max-height: none", "overflow: visible", "print-color-adjust: exact",
                  ".solo-impresion", "display: inline", "break-inside: avoid", "table-header-group"):
        assert regla in impresion, regla
    pantalla = css[:css.index("@media print")]
    assert ".tabla-desplazable {\n    max-height: 32rem;\n    overflow-y: auto;\n}" in pantalla
    assert ".solo-impresion,\n.solo-impresion-bloque {\n    display: none;\n}" in pantalla


def test_solo_las_paginas_de_producto1_marcan_el_body(cliente, tmp_path):
    base = (RAIZ_BACKEND / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    assert "<body{% block clase_body %}{% endblock %}>" in base
    for ruta in sorted((RAIZ_BACKEND / "app" / "templates").rglob("*.html")):
        texto = ruta.read_text(encoding="utf-8")
        marcada = "producto1-impresion" in texto
        # Producto 3 anade sus paginas (panel diario y rendimiento) en `operacion/`, Producto 4 las del
        # laboratorio de modelos en `laboratorio/`, Producto 5 las de carteras y simulacion en `carteras/`,
        # Producto 6 las del centro de resultados en `resultados/`, la Fase 5 las estadisticas descriptivas
        # nuevas y el panel en `descriptivas/`, Fase 4 en `predicciones/`, Fase 6 en `automatizacion/` y Fase 7
        # en `simulaciones/`.
        es_pagina_producto1 = ruta.parent.name in ("producto", "operacion", "laboratorio", "carteras", "resultados",
                                                   "descriptivas", "predicciones", "automatizacion", "simulaciones") \
            and not ruta.name.startswith("_")
        assert marcada == es_pagina_producto1, ruta
    for url in ("/estadisticas", "/estadisticas/baloto/resumen", "/estadisticas/colorloto/resumen", "/pronosticos",
                "/operacion", "/rendimiento"):
        assert '<body class="producto1-impresion">' in cliente.get(url).text, url
    juegos, resultados, colores = fx.repositorios()
    ajeno = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(tmp_path), conectada=False)
    for url in ("/", "/estadisticas/baloto/frecuencia-numeros"):
        r = ajeno.get(url)
        assert r.status_code == 200 and "<body>" in r.text and "producto1-impresion" not in r.text, url


def test_pronostico_imprime_la_tabla_por_bloque_sin_javascript():
    plantilla = (RAIZ_BACKEND / "app" / "templates" / "producto" / "pronostico_detalle.html").read_text(encoding="utf-8")
    assert "{% set tabla_por_bloque %}" in plantilla and plantilla.count("{{ tabla_por_bloque }}") == 2
    assert '<div class="solo-impresion-bloque">' in plantilla and "<script>" not in plantilla
    assert plantilla.count("<details") == 1 and '<details class="detalle-bloques">' in plantilla
    css = (RAIZ_BACKEND / "app" / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    impresion = _bloque_de_impresion(css)
    assert "body.producto1-impresion details.detalle-bloques {\n        display: none !important;" in impresion
    assert "body.producto1-impresion .solo-impresion-bloque {" in impresion
