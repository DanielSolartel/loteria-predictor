"""Fase 5 (estadísticas descriptivas): catálogo, denominadores, cortes y estados del caso de uso.

Históricos SINTÉTICOS (fixtures de Producto 1 y sorteos construidos aquí); no son datos reales."""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.application.estadisticas import descriptivas as de
from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico
from app.application.exceptions import JuegoNoEncontradoError, ResultadoHistoricoInconsistenteError
from app.application.use_cases.consultar_estadisticas_descriptivas import ConsultarEstadisticasDescriptivas
from app.domain.value_objects.color import Color
from tests.unit import fixtures_producto1 as fx

BALOTO = de.ReglasJuego("BALOTO", "Baloto", "numeros", (1, 43), 5, (1, 16))
MILOTO = de.ReglasJuego("MILOTO", "MiLoto", "numeros", (1, 39), 5, None)
COLORLOTO = de.ReglasJuego("COLORLOTO", "ColorLoto", "colorloto", (1, 7), 6, None, fx.COLORES, True)
HOY = date(2026, 10, 9)


def _num(n, numeros, sb=None, fecha=date(2025, 3, 3), dia="lunes"):
    return ResultadoNumerico(n, fecha, dia, tuple(numeros), sb)


def _tabla(contenido, tabla_id="") -> dict:
    return next(t for t in contenido["tablas"] if not tabla_id or t["id"] == tabla_id)


def _fila(tabla: dict, valor: str) -> dict:
    return next(f for f in tabla["filas"] if f["valor"] == valor)


# --- catálogo ----------------------------------------------------------------------------------

def test_catalogo_cubre_las_paginas_anteriores_de_cada_juego():
    """Las 12 visualizaciones numéricas y las 31 de ColorLoto anteriores figuran en el panel como
    páginas anteriores (no nuevas): el panel enlaza todo y no duplica ninguna."""
    from app.api.web.routers import estadisticas as anterior

    rutas = [r.path for r in anterior.router.routes]
    colorloto = {p.rsplit("/", 1)[1] for p in rutas if p.startswith("/estadisticas/colorloto/")}
    numericas = {p.rsplit("/", 1)[1] for p in rutas if p.startswith("/estadisticas/{juego_slug}/")}
    assert len(colorloto) == 31 and len(numericas) == 12
    for reglas, esperadas in ((COLORLOTO, colorloto), (BALOTO, numericas)):
        en_catalogo = {m.slug for m in de.CATALOGO if m.aplica(reglas) and not m.es_nueva(reglas)}
        assert en_catalogo == esperadas, esperadas ^ en_catalogo


def test_metricas_nuevas_por_juego_y_las_que_no_aplican_tienen_motivo():
    assert len(de.metricas_nuevas(BALOTO)) == 18
    assert len(de.metricas_nuevas(MILOTO)) == 11  # sin las 7 de superbalota
    assert {m.slug for m in de.metricas_nuevas(COLORLOTO)} == {
        "frecuencia-numeros-por-anio", "frecuencia-numeros-por-mes", "frecuencia-numeros-por-dia-semana",
        "pruebas-uniformidad", "correlaciones"}
    for reglas in (MILOTO, COLORLOTO):
        for m in de.CATALOGO:
            if not m.aplica(reglas) and m.construir is not None:
                assert m.motivo_no_aplica is not None and m.motivo_no_aplica(reglas), (reglas.codigo, m.slug)


@pytest.mark.parametrize("reglas,historico", [
    (BALOTO, fx.historico_numerico("BALOTO", 120)),
    (MILOTO, fx.historico_numerico("MILOTO", 60, primero=531)),
    (COLORLOTO, fx.historico_colorloto(80)),
])
def test_cada_metrica_nueva_es_json_y_su_grafica_es_una_columna_de_su_tabla(reglas, historico):
    for m in de.metricas_nuevas(reglas):
        c = de.construir_metrica(m.slug, reglas, historico)
        json.dumps(c)
        assert c["estado"] == "ok", (m.slug, c["motivo"])
        if c["grafica"]:
            tabla = _tabla(c, c["grafica"]["tabla"])
            claves = [col["clave"] for col in tabla["columnas"]]
            assert c["grafica"]["valor"] in claves and c["grafica"]["etiqueta"] in claves, m.slug
        for t in c["tablas"]:
            claves = {col["clave"] for col in t["columnas"]}
            assert all(set(f) >= claves for f in t["filas"]), (m.slug, t["id"])


def test_metrica_que_no_es_nueva_para_el_juego_se_rechaza():
    with pytest.raises(ValueError):
        de.construir_metrica("distribucion-sumas", COLORLOTO, [])  # página anterior de ColorLoto
    with pytest.raises(ValueError):
        de.construir_metrica("atrasos-superbalota", MILOTO, [])  # MiLoto no tiene superbalota


# --- denominadores a mano --------------------------------------------------------------------------

def test_decenas_porcentaje_de_numeros_extraidos_y_franja_corta_de_miloto():
    sorteos = [_num(1, (1, 2, 11, 31, 39)), _num(2, (3, 12, 21, 32, 38))]
    c = de.construir_metrica("distribucion-decenas", MILOTO, sorteos)
    t = _tabla(c)
    assert [f["valor"] for f in t["filas"]] == ["1-10", "11-20", "21-30", "31-39"]
    ultima = _fila(t, "31-39")  # 31, 39, 32, 38: 4 de 10 números extraídos
    assert ultima["numeros"] == 9 and ultima["apariciones"] == 4
    assert ultima["pct_extraidos"] == pytest.approx(40.0) and ultima["pct_esperado"] == pytest.approx(100 * 9 / 39)
    assert ultima["por_sorteo"] == pytest.approx(2.0)


def test_sumas_sin_superbalota_y_media_esperada():
    sorteos = [_num(1, (1, 2, 3, 4, 5), 16), _num(2, (39, 40, 41, 42, 43), 16)]  # 15 y 205
    c = de.construir_metrica("distribucion-sumas", BALOTO, sorteos)
    ind = {i["etiqueta"]: i["valor"] for i in c["indicadores"]}
    assert ind["Media"] == pytest.approx(110.0) and ind["Media esperada bajo azar uniforme"] == pytest.approx(110.0)
    hist = _tabla(c, "histograma")
    assert _fila(hist, "10-19")["sorteos"] == 1 and _fila(hist, "200-209")["sorteos"] == 1
    assert sum(f["sorteos"] for f in hist["filas"]) == 2 and _fila(hist, "10-19")["pct"] == pytest.approx(50.0)


def test_frecuencia_por_anio_porcentaje_de_sorteos_del_periodo_frente_a_la_muestra():
    sorteos = [_num(1, (1, 2, 3, 4, 5), 1, date(2024, 5, 6)), _num(2, (1, 6, 7, 8, 9), 2, date(2025, 5, 5)),
               _num(3, (2, 6, 10, 11, 12), 3, date(2025, 5, 12))]
    c = de.construir_metrica("frecuencia-numeros-por-anio", BALOTO, sorteos, {"anio": 2025})
    uno = _fila(_tabla(c), "1")  # 2025: 1 de 2 sorteos; muestra: 2 de 3
    assert uno["pct_periodo"] == pytest.approx(50.0) and uno["pct_muestra"] == pytest.approx(200 / 3)
    assert uno["diferencia"] == pytest.approx(50.0 - 200 / 3)
    assert c["selector"]["valor"] == "2025" and [o["sorteos"] for o in c["selector"]["opciones"]] == [1, 2]
    por_defecto = de.construir_metrica("frecuencia-numeros-por-anio", BALOTO, sorteos)
    assert por_defecto["selector"]["valor"] == "2025"  # año del último sorteo de la muestra
    vacio = de.construir_metrica("frecuencia-numeros-por-anio", BALOTO, sorteos, {"anio": 1999})
    assert vacio["estado"] == "sin_sorteos_en_el_periodo" and not vacio["tablas"]


def test_superbalota_por_dia_y_ordenacion_de_los_dias():
    sorteos = [_num(1, (1, 2, 3, 4, 5), 7, date(2025, 5, 7), "miercoles"),
               _num(2, (1, 2, 3, 4, 6), 7, date(2025, 5, 10), "sabado"),
               _num(3, (1, 2, 3, 4, 7), 9, date(2025, 5, 14), "miercoles")]
    c = de.construir_metrica("frecuencia-superbalota-por-dia-semana", BALOTO, sorteos, {"dia_semana": "miercoles"})
    siete = _fila(_tabla(c), "7")
    assert siete["apariciones"] == 1 and siete["pct_periodo"] == pytest.approx(50.0)
    assert [o["valor"] for o in c["selector"]["opciones"]] == ["miercoles", "sabado"]
    assert c["selector"]["etiqueta"] == "miércoles" and len(_tabla(c)["filas"]) == 16


def test_colorloto_por_mes_en_balotas_por_sorteo():
    sorteos = [ResultadoColorLoto(1, date(2025, 2, 4), "martes", ((5, "ROJO"),) * 6),
               ResultadoColorLoto(2, date(2025, 3, 4), "martes", ((5, "AZUL"), (1, "ROJO")) * 3)]
    c = de.construir_metrica("frecuencia-numeros-por-mes", COLORLOTO, sorteos, {"mes": 2})
    cinco = _fila(_tabla(c), "5")
    assert cinco["apariciones"] == 6 and cinco["por_sorteo"] == pytest.approx(6.0)
    assert cinco["por_sorteo_muestra"] == pytest.approx(4.5) and c["grafica"]["referencia"] == pytest.approx(6 / 7)


def test_ventana_ultimos_sorteos_y_diferencia_en_puntos():
    sorteos = [_num(i, (1, 2, 3, 4, 5) if i <= 15 else (6, 7, 8, 9, 10), 1) for i in range(1, 21)]
    c = de.construir_metrica("comparacion-frecuencia-numeros-por-ventana", BALOTO, sorteos, {"ventana": 5})
    seis, uno = _fila(_tabla(c), "6"), _fila(_tabla(c), "1")
    assert seis["pct_ventana"] == pytest.approx(100.0) and seis["pct_muestra"] == pytest.approx(25.0)
    assert seis["diferencia"] == pytest.approx(75.0) and uno["diferencia"] == pytest.approx(-75.0)
    with pytest.raises(ValueError):
        de.construir_metrica("comparacion-frecuencia-numeros-por-ventana", BALOTO, sorteos, {"ventana": 7})


def test_atrasos_y_repeticion_de_superbalota_con_su_denominador():
    sorteos = [_num(1, (1, 2, 3, 4, 5), 3), _num(2, (1, 2, 3, 4, 6), 3), _num(3, (1, 2, 3, 4, 7), 5),
               _num(5, (1, 2, 3, 4, 8), 5)]
    atrasos = _tabla(de.construir_metrica("atrasos-superbalota", BALOTO, sorteos))
    assert _fila(atrasos, "3")["atraso"] == 3 and _fila(atrasos, "5")["atraso"] == 0
    assert _fila(atrasos, "1")["atraso"] is None  # nunca observada: None, no 0
    rep = de.construir_metrica("repeticion-superbalota", BALOTO, sorteos)
    t = _tabla(rep)  # transiciones válidas: 1->2 (igual), 2->3 (distinta); 3->5 es un hueco
    assert [f["transiciones"] for f in t["filas"]] == [1, 1]
    assert _fila(t, "Igual a la del sorteo anterior")["esperado"] == pytest.approx(100 / 16)
    assert {i["etiqueta"]: i["valor"] for i in rep["indicadores"]}["Excluidas por hueco de numeración"] == 1


def test_intervalos_con_referencia_n_sobre_k_y_valores_sin_intervalo():
    sorteos = [_num(1, (1, 2, 3, 4, 5)), _num(4, (1, 6, 7, 8, 9)), _num(6, (1, 2, 10, 11, 12))]
    c = de.construir_metrica("intervalos-historicos-numeros", BALOTO, sorteos)
    uno, dos, cuarenta = (_fila(_tabla(c), v) for v in ("1", "2", "40"))
    assert uno["intervalos"] == 2 and uno["minimo"] == 2 and uno["maximo"] == 3 and uno["promedio"] == 2.5
    assert dos["promedio"] == 5 and cuarenta["promedio"] is None and cuarenta["apariciones"] == 0
    assert c["grafica"]["referencia"] == pytest.approx(43 / 5)
    assert any("hueco" in n for n in c["notas"])  # 2, 3, 5 no están cargados


def test_pruebas_de_uniformidad_separan_superbalota_y_usan_balotas_en_colorloto():
    c = de.construir_metrica("pruebas-uniformidad", BALOTO, fx.historico_numerico("BALOTO", 200))
    resumen = _tabla(c, "resumen")
    assert [f["valor"] for f in resumen["filas"]] == ["Números principales", "Superbalota"]
    assert resumen["filas"][0]["grados_libertad"] == 42 and resumen["filas"][1]["grados_libertad"] == 15
    assert _fila(_tabla(c, "numeros"), "1")["esperado"] == pytest.approx(200 * 5 / 43)
    cl = de.construir_metrica("pruebas-uniformidad", COLORLOTO, fx.historico_colorloto(70))
    filas = _tabla(cl, "resumen")["filas"]
    assert [f["valor"] for f in filas] == ["Números (balotas)", "Colores (balotas)", "Pares número-color (balotas)"]
    assert [f["esperado"] for f in filas] == pytest.approx([70 * 6 / 7, 70.0, 10.0])
    inestable = de.ReglasJuego("COLORLOTO", "ColorLoto", "colorloto", (1, 7), 6, None, fx.COLORES, False)
    filas = _tabla(de.construir_metrica("pruebas-uniformidad", inestable, fx.historico_colorloto(70)), "resumen")["filas"]
    assert filas[0]["p_value"] is not None and filas[1]["p_value"] is None and "paleta" in filas[1]["motivo"]


def test_independencia_marca_significativos_solo_tras_corregir():
    c = de.construir_metrica("independencia-pares", MILOTO, fx.historico_numerico("MILOTO", 80, primero=531))
    ind = {i["etiqueta"]: i["valor"] for i in c["indicadores"]}
    assert ind["Pruebas (pares posibles)"] == 741  # C(39, 2)
    t = _tabla(c)
    assert len(t["filas"]) == de.FILAS_INDEPENDENCIA
    assert all(f["p_ajustado"] >= f["p_value"] for f in t["filas"])
    assert [f["p_value"] for f in t["filas"]] == sorted(f["p_value"] for f in t["filas"])


def test_correlaciones_numericas_y_numero_color():
    c = de.construir_metrica("correlaciones", BALOTO, fx.historico_numerico("BALOTO", 100))
    filas = _tabla(c, "correlaciones")["filas"]
    assert [f["metodo"] for f in filas] == ["Pearson", "Spearman", "Pearson", "Spearman"]
    assert filas[0]["n"] == 99 and filas[2]["n"] == 43
    assert all(-1 <= f["coeficiente"] <= 1 for f in filas)
    cl = de.construir_metrica("correlaciones", COLORLOTO, fx.historico_colorloto(100))
    contingencia = _tabla(cl, "contingencia")
    assert len(contingencia["filas"]) == 7 and len(contingencia["columnas"]) == 1 + 6
    assert any(i["etiqueta"] == "χ² número × color" for i in cl["indicadores"])


# --- estados sin datos o insuficientes -------------------------------------------------------------

@pytest.mark.parametrize("reglas", [BALOTO, MILOTO, COLORLOTO])
def test_historico_vacio_nunca_inventa_ceros(reglas):
    for m in de.metricas_nuevas(reglas):
        c = de.construir_metrica(m.slug, reglas, [])
        assert c["estado"] == "sin_datos" and not c["tablas"] and not c["indicadores"], m.slug
    for grupo in de.construir_panel(reglas, []):
        for e in grupo["metricas"]:
            assert e["estado"] in ("sin_datos", "no_aplica") and not e["indicadores"], e["slug"]


def test_un_solo_sorteo_es_insuficiente_para_intervalos_correlaciones_y_repeticion():
    uno = [_num(1, (1, 2, 3, 4, 5), 1)]
    assert de.construir_metrica("intervalos-historicos-numeros", BALOTO, uno)["estado"] == "insuficiente"
    assert de.construir_metrica("correlaciones", BALOTO, uno)["estado"] == "insuficiente"
    assert de.construir_metrica("repeticion-superbalota", BALOTO, uno)["estado"] == "insuficiente"


def test_panel_agrupa_todo_y_explica_lo_que_no_aplica():
    grupos = de.construir_panel(MILOTO, fx.historico_numerico("MILOTO", 60, primero=531))
    assert [g["clave"] for g in grupos] == [g for g, _ in de.GRUPOS]
    entradas = {e["slug"]: e for g in grupos for e in g["metricas"]}
    assert entradas["frecuencia-superbalota"]["aplica"] is False and "superbalota" in entradas["frecuencia-superbalota"]["motivo"]
    assert entradas["distribucion-sumas"]["nueva"] is True and entradas["frecuencia-numeros"]["nueva"] is False
    assert all(e["indicadores"] for e in entradas.values() if e["aplica"]), \
        [s for s, e in entradas.items() if e["aplica"] and not e["indicadores"]]


# --- caso de uso: corte, integridad, paleta y lectura sin escritura ----------------------------------

def _consultar(numericos=None, colorloto=None, colores=None):
    juegos, resultados, repo_colores = fx.repositorios(numericos or {}, colorloto=colorloto)
    if colores is not None:
        repo_colores._colores[fx.juego("COLORLOTO").id] = colores
    return ConsultarEstadisticasDescriptivas(juegos, resultados, repo_colores), resultados


def test_el_corte_se_aplica_antes_de_calcular_y_la_muestra_lo_refleja():
    historico = [_num(2081, (1, 2, 3, 4, 5), 1), _num(2082, (1, 2, 3, 4, 6), 1), _num(2083, (40, 41, 42, 43, 7), 16)]
    consultar, _ = _consultar({"BALOTO": historico})
    r = consultar.metrica("BALOTO", "frecuencia-numeros-por-anio", hoy=HOY, hasta_numero_sorteo=2082)
    assert r["muestra"]["total_sorteos"] == 2 and r["muestra"]["total_sorteos_sin_corte"] == 3
    assert _fila(_tabla(r["metrica"]), "43")["apariciones"] == 0  # el sorteo 2083 queda fuera
    panel = consultar.panel("BALOTO", hoy=HOY, hasta_numero_sorteo=2082)
    assert panel["muestra"]["periodo"]["ultimo_sorteo"] == 2082


def test_historico_inconsistente_rechaza_el_calculo_completo():
    consultar, _ = _consultar({"BALOTO": [_num(1, (1, 2, 3, 4, 5), 1), _num(2, (1, 1, 3, 4, 5), 1)]})
    with pytest.raises(ResultadoHistoricoInconsistenteError):
        consultar.metrica("BALOTO", "distribucion-sumas", hoy=HOY)
    consultar, _ = _consultar({"BALOTO": [_num(1, (1, 2, 3, 4, 5), None)]})
    with pytest.raises(ResultadoHistoricoInconsistenteError):
        consultar.panel("BALOTO", hoy=HOY)


def test_juego_no_registrado():
    juegos, resultados, colores = fx.repositorios(juegos=("BALOTO",))
    with pytest.raises(JuegoNoEncontradoError):
        ConsultarEstadisticasDescriptivas(juegos, resultados, colores).panel("MILOTO", hoy=HOY)


def test_paleta_de_colorloto_estable_o_cambiante():
    sorteos = fx.historico_colorloto(20, inicio=date(2025, 1, 1))
    consultar, _ = _consultar(colorloto=sorteos)
    r = consultar.metrica("COLORLOTO", "pruebas-uniformidad", hoy=HOY)
    assert r["juego"]["paleta_estable"] is True and sorted(r["juego"]["colores"]) == sorted(fx.COLORES)
    cambiante = [Color(c, c.title()) for c in fx.COLORES if c != "NEGRO"] + [
        Color("NEGRO", "Negro", vigente_desde=date(2025, 1, 20))]
    antes = ResultadoColorLoto(1, date(2025, 1, 6), "lunes", ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"),
                                                               (5, "BLANCO"), (6, "AMARILLO")))
    despues = ResultadoColorLoto(2, date(2025, 2, 3), "lunes", ((1, "NEGRO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"),
                                                                (5, "BLANCO"), (7, "AMARILLO")))
    consultar, _ = _consultar(colorloto=[antes, despues], colores=cambiante)
    r = consultar.metrica("COLORLOTO", "pruebas-uniformidad", hoy=HOY)
    assert r["juego"]["paleta_estable"] is False
    assert _tabla(r["metrica"], "resumen")["filas"][1]["p_value"] is None


def test_solo_lee_una_vez_el_historico_y_no_usa_la_cache():
    consultar, resultados = _consultar({"MILOTO": fx.historico_numerico("MILOTO", 40, primero=531)})
    consultar.panel("MILOTO", hoy=HOY, hasta_numero_sorteo=560)
    assert resultados.consultas == [(fx.juego("MILOTO").id, None)]  # una consulta, el corte se aplica en memoria
