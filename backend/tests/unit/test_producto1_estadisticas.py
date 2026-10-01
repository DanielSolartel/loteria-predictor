"""Producto 1: resumen estadistico de los cuatro juegos y sus pantallas.

Reglas propias de cada juego (MiLoto 1..39 sin superbalota, Baloto y
Revancha 1..43 con superbalota 1..16, ColorLoto con colores), historial
vacio, datos antiguos, corte, y las rutas `/estadisticas` y
`/estadisticas/{slug}/resumen` con la aplicacion real y repositorios
fake (sin PostgreSQL). Historicos sinteticos."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.application.estadisticas.resumen_juego import resumen_juego_colorloto, resumen_juego_numerico
from app.application.use_cases.consultar_resumen_juego import ConsultarResumenJuego
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx


def _resumen(codigo, historico, hoy, **kw):
    juegos, resultados, colores = fx.repositorios({codigo: historico} if codigo != "COLORLOTO" else {},
                                                  colorloto=historico if codigo == "COLORLOTO" else None)
    return ConsultarResumenJuego(juegos, resultados, colores).ejecutar(codigo, hoy=hoy, **kw)


def _dia_siguiente(historico):
    return date.fromisoformat(historico[-1].fecha.isoformat()) + timedelta(days=1)


def test_miloto_respeta_su_rango_y_no_tiene_superbalota():
    h = fx.historico_numerico("MILOTO", 60, primero=1)
    r = _resumen("MILOTO", h, _dia_siguiente(h))
    assert r["reglas"] == {"tipo": "numeros", "rango": [1, 39], "cantidad_numeros": 5, "superbalota": None}
    valores = [f["valor"] for f in r["estadisticas"]["frecuencia_numeros"]["todas"]]
    assert valores == [str(n) for n in range(1, 40)]
    assert r["estadisticas"]["superbalota"] is None
    assert sum(f["apariciones"] for f in r["estadisticas"]["frecuencia_numeros"]["todas"]) == 60 * 5
    assert r["ultimo_resultado"]["superbalota"] is None
    assert all(int(a["valor"]) <= 39 for a in r["estadisticas"]["atrasos_numeros"]["mayores"])


@pytest.mark.parametrize("codigo", ["BALOTO", "BALOTO_REVANCHA"])
def test_baloto_y_revancha_43_numeros_y_superbalota(codigo):
    h = fx.historico_numerico(codigo, 80)
    r = _resumen(codigo, h, _dia_siguiente(h))
    assert r["reglas"]["rango"] == [1, 43] and r["reglas"]["superbalota"] == [1, 16]
    assert len(r["estadisticas"]["frecuencia_numeros"]["todas"]) == 43
    sb = r["estadisticas"]["superbalota"]
    assert [f["valor"] for f in sb["frecuencia"]["todas"]] == [str(n) for n in range(1, 17)]
    assert sum(f["apariciones"] for f in sb["frecuencia"]["todas"]) == 80
    assert r["ultimo_sorteo_disponible"] == {"numero_sorteo": 2160, "fecha": h[-1].fecha.isoformat()}
    assert r["periodo"]["primer_sorteo"] == 2081 and r["total_sorteos"] == 80
    pares = r["estadisticas"]["pares_impares"]
    assert [d["valor"] for d in pares] == [str(k) for k in range(6)] and sum(d["sorteos"] for d in pares) == 80


def test_colorloto_presenta_colores_numeros_1_a_7_y_pares():
    h = fx.historico_colorloto(40)
    r = _resumen("COLORLOTO", h, _dia_siguiente(h))
    assert r["reglas"]["tipo"] == "colorloto" and r["reglas"]["rango"] == [1, 7]
    assert r["reglas"]["colores"] == list(fx.COLORES) and r["reglas"]["cantidad_balotas"] == 6
    e = r["estadisticas"]
    assert {f["valor"] for f in e["frecuencia_colores"]["todas"]} == set(fx.COLORES)
    assert sum(f["apariciones"] for f in e["frecuencia_colores"]["todas"]) == 40 * 6
    assert [f["valor"] for f in e["frecuencia_numeros"]["todas"]] == [str(n) for n in range(1, 8)]
    assert len(e["frecuencia_pares"]["todas"]) == 7 * 6
    assert e["colores_fuera_de_la_paleta_vigente"] == []
    assert "superbalota" not in e and len(r["ultimo_resultado"]["pares"]) == 6


def test_colorloto_color_fuera_de_paleta_no_se_pierde():
    h = fx.historico_colorloto(5)
    h[-1] = h[-1].__class__(h[-1].numero_sorteo, h[-1].fecha, h[-1].dia_semana, ((1, "MORADO"),) + h[-1].pares[1:])
    r = _resumen("COLORLOTO", h, _dia_siguiente(h))
    assert r["estadisticas"]["colores_fuera_de_la_paleta_vigente"] == ["MORADO"]
    assert any(f["valor"] == "MORADO" for f in r["estadisticas"]["frecuencia_colores"]["todas"])


def test_historial_vacio_mensaje_claro():
    for codigo in ("BALOTO", "MILOTO", "COLORLOTO"):
        r = _resumen(codigo, [], date(2026, 10, 1))
        assert r["total_sorteos"] == 0 and r["estadisticas"] is None and r["periodo"] is None
        assert r["frescura"]["estado"] == "sin_datos" and "Sincroniza" in r["frescura"]["mensaje"]


def test_datos_antiguos_se_marcan_desactualizados():
    h = fx.historico_numerico("BALOTO", 10)
    r = _resumen("BALOTO", h, h[-1].fecha + timedelta(days=30))
    assert r["frescura"]["estado"] == "desactualizado" and r["frescura"]["dias_desde_el_ultimo_sorteo"] == 30
    assert "desactualizado" in r["frescura"]["mensaje"]
    assert _resumen("BALOTO", h, h[-1].fecha + timedelta(days=3))["frescura"]["estado"] == "al_dia"


def test_corte_aplicado_y_huecos():
    h = fx.historico_numerico("BALOTO", 30)
    con_hueco = [r for r in h if r.numero_sorteo not in (2090, 2091)]
    r = _resumen("BALOTO", con_hueco, _dia_siguiente(h), hasta_numero_sorteo=2100)
    assert r["corte"] == {"hasta_numero_sorteo": 2100, "descripcion": "hasta el sorteo 2100"}
    assert r["periodo"]["ultimo_sorteo"] == 2100 and r["total_sorteos"] == 18 and r["total_sorteos_sin_corte"] == 28
    assert r["huecos"]["cantidad"] == 2 and r["huecos"]["primeros"] == [2090, 2091]
    assert r["ultimo_sorteo_disponible"]["numero_sorteo"] == 2110


def test_funciones_puras_reciben_la_fecha():
    h = fx.historico_numerico("BALOTO", 3)
    r = resumen_juego_numerico(h, codigo_juego="BALOTO", nombre="Baloto", rango=(1, 43), cantidad_numeros=5,
                               rango_superbalota=(1, 16), hoy=date(2030, 1, 1))
    assert r["consultado_el"] == "2030-01-01"
    c = resumen_juego_colorloto([], nombre="ColorLoto", rango=(1, 7), cantidad_balotas=6, colores=[],
                                hoy=date(2030, 1, 1))
    assert c["estadisticas"] is None and c["reglas"]["colores"] == []


# ---------------------------------------------------------------------------
# Pantallas
# ---------------------------------------------------------------------------

@pytest.fixture
def cliente(tmp_path):
    hoy = date.today()
    inicio = hoy - timedelta(days=3 * 59 + 2)
    juegos, resultados, colores = fx.repositorios(
        {"BALOTO": fx.historico_numerico("BALOTO", 60, inicio=inicio),
         "BALOTO_REVANCHA": fx.historico_numerico("BALOTO_REVANCHA", 60, inicio=inicio),
         "MILOTO": fx.historico_numerico("MILOTO", 60, primero=1, inicio=date(2020, 1, 1))},
        colorloto=fx.historico_colorloto(30, inicio=inicio))
    c = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(tmp_path))
    yield c
    from app.main import app
    app.dependency_overrides = {}


def test_indice_muestra_los_cuatro_juegos(cliente):
    r = cliente.get("/estadisticas")
    assert r.status_code == 200
    for nombre in ("Baloto", "Baloto Revancha", "MiLoto", "ColorLoto"):
        assert nombre in r.text
    for slug in ("baloto", "baloto-revancha", "miloto", "colorloto"):
        assert f"/estadisticas/{slug}/resumen" in r.text
    assert "Desactualizado" in r.text and "Al día" in r.text
    assert 'href="/estadisticas"' in r.text and 'href="/pronosticos"' in r.text


@pytest.mark.parametrize("slug,esperado,prohibido", [
    ("baloto", "superbalota de 1 a 16", "con color"),
    ("baloto-revancha", "superbalota de 1 a 16", "con color"),
    ("miloto", "sin superbalota", "superbalota de 1 a 16"),
    ("colorloto", "Frecuencia de colores", "Superbalota"),
])
def test_resumen_por_juego(cliente, slug, esperado, prohibido):
    r = cliente.get(f"/estadisticas/{slug}/resumen")
    assert r.status_code == 200, r.text[:500]
    assert esperado in r.text and prohibido not in r.text
    assert "Corte aplicado" in r.text and "Último sorteo disponible" in r.text


def test_miloto_pagina_solo_numeros_1_a_39(cliente):
    r = cliente.get("/estadisticas/miloto/resumen")
    assert "Frecuencia de números (1–39)" in r.text and "1–43" not in r.text
    assert "desactualizado" in r.text.lower()


def test_resumen_con_corte_y_corte_vacio(cliente):
    r = cliente.get("/estadisticas/baloto/resumen?hasta_numero_sorteo=2100")
    assert r.status_code == 200 and "hasta el sorteo 2100" in r.text
    assert cliente.get("/estadisticas/baloto/resumen?hasta_numero_sorteo=").status_code == 200
    assert cliente.get("/estadisticas/baloto/resumen?hasta_numero_sorteo=0").status_code == 422
    r = cliente.get("/estadisticas/baloto/resumen?hasta_numero_sorteo=5")
    assert "No hay sorteos" in r.text


def test_slug_desconocido_404(cliente):
    assert cliente.get("/estadisticas/quina/resumen").status_code == 404


def test_rest_resumen(cliente):
    r = cliente.get("/api/estadisticas/MILOTO/resumen")
    assert r.status_code == 200 and r.json()["reglas"]["superbalota"] is None
    assert cliente.get("/api/estadisticas/QUINA/resumen").status_code == 404


def test_sin_base_de_datos_mensaje_claro(tmp_path):
    juegos, resultados, colores = fx.repositorios()
    c = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(tmp_path), conectada=False)
    try:
        r = c.get("/estadisticas")
        assert r.status_code == 200 and "Sin conexión a la base de datos" in r.text
        assert "Sin conexión" in c.get("/estadisticas/colorloto/resumen").text
    finally:
        from app.main import app
        app.dependency_overrides = {}


def test_juego_vacio_en_pantalla(tmp_path):
    juegos, resultados, colores = fx.repositorios()
    c = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(tmp_path))
    try:
        r = c.get("/estadisticas/colorloto/resumen")
        assert r.status_code == 200 and "No hay sorteos" in r.text
        assert "Sin datos" in c.get("/estadisticas").text
    finally:
        from app.main import app
        app.dependency_overrides = {}


def test_dashboard_enlaza_estadisticas_y_pronostico(tmp_path):
    juegos, resultados, colores = fx.repositorios()
    c = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(tmp_path), conectada=False)
    try:
        r = c.get("/")
        assert r.status_code == 200
        assert 'href="/estadisticas"' in r.text and 'href="/pronosticos"' in r.text
        assert "disponible en fases siguientes" not in r.text.split("Simulaciones y probabilidades")[0]
    finally:
        from app.main import app
        app.dependency_overrides = {}
