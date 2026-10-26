"""Fase 9.2: páginas de las métricas anteriores en la API pública.

Con datos sintéticos (SQLite de la Fase 7), cada métrica anterior aplicable se
compara con la receta HTMX existente (`CalcularYPersistirEstadistica.ejecutar`,
con los mismos `parametros_metrica` que su ruta de la consola y una caché en
memoria) sobre la misma muestra y el mismo corte. La API no escribe la caché
`estadisticas` ni ninguna otra tabla, y no anuncia métricas que no aplican."""
from __future__ import annotations

import json
import math

import pytest
from sqlalchemy import text

from app.api.web.view_models import _deserializar_par_numero_color
from app.application.estadisticas.descriptivas import CATALOGO, ReglasJuego
from app.application.use_cases.calcular_y_persistir_estadistica import (
    POLITICA_UNIVERSO_COLORES_ACTUAL as POLITICA,
    CalcularYPersistirEstadistica,
)
from app.infrastructure.repositories.color_repository_sqlalchemy import ColorRepositorySQLAlchemy
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
    ResultadosHistoricosRepositorySQLAlchemy,
)
from tests.unit.api_publica import fixtures_api_publica as fa
from tests.unit.fakes import FakeEstadisticaRepository
from tests.unit.simulaciones import fixtures_fase7 as f7

NUMERICOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO")
RANGO = {"BALOTO": (1, 43), "BALOTO_REVANCHA": (1, 43), "MILOTO": (1, 39), "COLORLOTO": (1, 7)}
CANTIDAD = {"BALOTO": 5, "BALOTO_REVANCHA": 5, "MILOTO": 5, "COLORLOTO": 6}
SUPERBALOTA = {"BALOTO": (1, 16), "BALOTO_REVANCHA": (1, 16)}

# Receta y `parametros_metrica` de cada ruta HTMX (backend/app/api/web/routers/estadisticas.py),
# escritos aquí de forma independiente de la implementación de la API.
def _receta(codigo: str, slug: str, filtro=None) -> tuple[str, dict]:
    lo, hi = RANGO[codigo]
    k = CANTIDAD[codigo]
    rk = {"rango_min": lo, "rango_max": hi, "cantidad_numeros": k}
    if codigo != "COLORLOTO":
        r = {"rango_min": lo, "rango_max": hi}
        return {
            "frecuencia-numeros": ("frecuencia_numeros", r),
            "frecuencia-superbalota": ("frecuencia_superbalota",
                                       dict(zip(("rango_min", "rango_max"), SUPERBALOTA.get(codigo, (0, 0))))),
            "frecuencia-observada-esperada": ("tabla_frecuencia_numeros", rk),
            "atrasos-numeros": ("atrasos_numeros", r),
            "distribucion-pares-impares": ("distribucion_pares_impares", {"cantidad_numeros": k}),
            "distribucion-altos-bajos": ("distribucion_altos_bajos", rk),
            "distribucion-pares-consecutivos": ("distribucion_pares_consecutivos", rk),
            "distribucion-trios-consecutivos": ("distribucion_trios_consecutivos", rk),
            "distribucion-racha-maxima": ("distribucion_racha_maxima", rk),
            "repeticiones-entre-sorteos": ("distribucion_repeticiones_entre_sorteos", rk),
            "coocurrencia-pares": ("coocurrencia_pares", rk),
            "coocurrencia-trios": ("coocurrencia_trios", rk),
        }[slug]
    p = {"politica_universo_colores": POLITICA}
    rp = {"rango_min": lo, "rango_max": hi}
    periodo = {"anio": "anio", "mes": "mes", "dia-semana": "dia_semana"}
    for sufijo, clave in periodo.items():
        if slug == f"frecuencia-colores-por-{sufijo}":
            return f"frecuencia_colores_por_{clave}_colorloto", {clave: filtro, **p}
        if slug == f"frecuencia-pares-numero-color-por-{sufijo}":
            return f"frecuencia_pares_numero_color_por_{clave}_colorloto", {clave: filtro, **rp, **p}
    return {
        "frecuencia-numeros": ("frecuencia_numeros_colorloto", rk),
        "frecuencia-colores": ("frecuencia_colores_colorloto", {**rk, **p}),
        "frecuencia-pares-numero-color": ("frecuencia_pares_colorloto", {**rk, **p}),
        "atrasos-numeros": ("atrasos_numeros_colorloto", rk),
        "atrasos-colores": ("atrasos_colores_colorloto", {**rk, **p}),
        "atrasos-pares-numero-color": ("atrasos_pares_colorloto", {**rk, **p}),
        "repeticiones-entre-sorteos": ("repeticiones_entre_sorteos_colorloto", rk),
        "distribucion-pares-impares": ("distribucion_pares_impares_colorloto", {"cantidad_numeros": k}),
        "distribucion-altos-bajos": ("distribucion_altos_bajos_colorloto", rk),
        "maximo-repeticion-color": ("maximo_repeticion_color_por_sorteo_colorloto", {"cantidad_numeros": k}),
        "distribucion-pares-consecutivos": ("distribucion_pares_consecutivos_colorloto", {"cantidad_numeros": k}),
        "distribucion-racha-maxima": ("distribucion_racha_maxima_colorloto", {"cantidad_numeros": k}),
        "distribucion-trios-consecutivos": ("distribucion_trios_consecutivos_colorloto", {"cantidad_numeros": k}),
        "coocurrencia-pares": ("coocurrencia_pares_colorloto", {}),
        "coocurrencia-trios": ("coocurrencia_trios_colorloto", {}),
        "coocurrencia-pares-colores": ("coocurrencia_pares_colores_colorloto", {}),
        "coocurrencia-trios-colores": ("coocurrencia_trios_colores_colorloto", {}),
        "intervalos-historicos-colores": ("intervalos_historicos_colores_colorloto", p),
        "distribucion-sumas": ("distribucion_sumas_colorloto", {}),
        "intervalos-historicos-numeros": ("intervalos_historicos_numeros_colorloto", rp),
        "intervalos-historicos-pares-numero-color": ("intervalos_historicos_pares_numero_color_colorloto", {**rp, **p}),
        "distribucion-conteo-color": ("distribucion_conteo_color_colorloto",
                                      {"color_objetivo": filtro, "cantidad_balotas": k}),
        "comparacion-frecuencia-numeros-por-ventana": ("comparacion_frecuencia_numeros_por_ventana_colorloto",
                                                       {"ventana": filtro, **rp}),
        "comparacion-frecuencia-colores-por-ventana": ("comparacion_frecuencia_colores_por_ventana_colorloto",
                                                       {"ventana": filtro, **p}),
        "comparacion-frecuencia-pares-numero-color-por-ventana": (
            "comparacion_frecuencia_pares_numero_color_por_ventana_colorloto", {"ventana": filtro, **rp, **p}),
    }[slug]


def _reglas(codigo: str) -> ReglasJuego:
    if codigo == "COLORLOTO":
        return ReglasJuego("COLORLOTO", "ColorLoto", "colorloto", RANGO[codigo], 6, None, ("AZUL",))
    return ReglasJuego(codigo, codigo, "numeros", RANGO[codigo], 5, SUPERBALOTA.get(codigo))


def _anteriores(codigo: str) -> list[str]:
    reglas = _reglas(codigo)
    return [m.slug for m in CATALOGO if m.aplica(reglas) and not m.es_nueva(reglas)]


CASOS = [(c, s) for c in (*NUMERICOS, "COLORLOTO") for s in _anteriores(c)]
FILTRO = {"anio": "anio", "mes": "mes", "dia-semana": "dia_semana"}


@pytest.fixture(scope="module")
def a(tmp_path_factory):
    return fa.api(tmp_path_factory.mktemp("f92"), fichas_por_minuto=100_000)


def _corte(a, codigo: str) -> int:
    numeros = [r.numero_sorteo for r in a.entorno.historicos[codigo]]
    return numeros[len(numeros) * 2 // 3]


def _htmx(a, codigo: str, tipo: str, corte, parametros: dict) -> dict:
    """La receta de la ruta HTMX tal cual, con una caché en memoria (no toca la SQLite)."""
    with a.entorno.sesiones() as s:
        juego = JuegoRepositorySQLAlchemy(s).obtener_por_codigo(codigo)
        caso = CalcularYPersistirEstadistica(ResultadosHistoricosRepositorySQLAlchemy(s), FakeEstadisticaRepository(),
                                             ColorRepositorySQLAlchemy(s))
        return json.loads(json.dumps(caso.ejecutar(juego.id, tipo, corte, parametros).resultado, default=str))


def _paginas(a, url: str) -> tuple[dict, list[dict]]:
    """Primera respuesta y TODAS las filas de su tabla, recorriendo la paginación si existe."""
    primera = a.get(url).json()
    tabla = primera["metrica"]["tablas"][0]
    filas = list(tabla["filas"])
    paginacion = tabla.get("paginacion")
    if paginacion:
        separador = "&" if "?" in url else "?"
        for pagina in range(2, paginacion["total_paginas"] + 1):
            r = a.get(f"{url}{separador}pagina={pagina}")
            assert r.status_code == 200
            filas += r.json()["metrica"]["tablas"][0]["filas"]
        assert len(filas) == paginacion["total_filas"]
    return primera, filas


def _clave(fila: dict) -> str:
    if "numero" in fila and "color" in fila:
        return f"{fila['numero']}-{fila['color']}"
    if "color" in fila:
        return str(fila["color"])
    return str(fila["valor"])


def _elementos(fila: dict) -> tuple:
    claves = sorted(k for k in fila if k.startswith(("numero_", "color_")))
    return tuple(fila[k] for k in claves)


def _comparar(receta: dict, respuesta: dict, filas: list[dict]) -> None:
    """Mismas cifras de la receta HTMX en la respuesta pública (sin recalcular nada en la prueba)."""
    if "filas" not in receta:  # distribución de sumas: un objeto
        ind = {i["etiqueta"]: i["valor"] for i in respuesta["metrica"]["indicadores"]}
        assert (ind["Sorteos analizados"], ind["Mínimo"], ind["Máximo"]) == (
            receta["total_sorteos"], receta["minimo"], receta["maximo"])
        assert math.isclose(ind["Media"], receta["media"]) and math.isclose(ind["Mediana"], receta["mediana"])
        assert {f["percentil"]: f["valor"] for f in filas} == receta["percentiles"]
        return
    esperado = receta["filas"]
    assert len(filas) == len(esperado)
    if not esperado:
        return
    muestra = esperado[0]
    if "elementos" in muestra:
        assert sorted((_elementos(f), f["soporte"]) for f in filas) == sorted(
            (tuple(e["elementos"]), e["soporte"]) for e in esperado)
        orden = [(-f["soporte"], _elementos(f)) for f in filas]
        assert orden == sorted(orden), "orden de la consola: soporte descendente y elementos"
    elif "frecuencia_observada" in muestra:
        assert {f["valor"]: (f["apariciones"], f["diferencia"]) for f in filas} == {
            e["valor"]: (e["apariciones"], pytest.approx(100.0 * e["diferencia"])) for e in esperado}
    elif "frecuencia_historica" in muestra:
        assert {_clave(f): (f["apariciones_muestra"], f["apariciones_ventana"]) for f in filas} == {
            e["valor"]: (e["frecuencia_historica"]["apariciones"], e["frecuencia_reciente"]["apariciones"])
            for e in esperado}
    elif "cantidad_intervalos" in muestra:
        assert {_clave(f): (f["apariciones"], f["intervalos"], f["minimo"], f["maximo"]) for f in filas} == {
            e["valor"]: (e["cantidad_apariciones"], e["cantidad_intervalos"], e["intervalo_minimo"],
                         e["intervalo_maximo"]) for e in esperado}
    elif "atraso" in muestra:
        assert {_clave(f): (f["atraso"], f["ultimo_sorteo"]) for f in filas} == {
            e["valor"]: (e["atraso"], e["ultimo_sorteo_aparicion"]) for e in esperado}
    else:
        assert {_clave(f): f["apariciones"] for f in filas} == {e["valor"]: e["apariciones"] for e in esperado}


def test_indice_anuncia_las_paginas_aplicables_y_solo_esas(a):
    """30 en Baloto y Revancha, 22 en MiLoto y 36 en ColorLoto: las de la Fase 5 y las anteriores."""
    esperado = {"BALOTO": 30, "BALOTO_REVANCHA": 30, "MILOTO": 22, "COLORLOTO": 36}
    for codigo, cantidad in esperado.items():
        indice = a.get(f"/api/v1/juegos/{codigo}/estadisticas").json()
        reglas = _reglas(codigo)
        aplicables = [m.slug for m in CATALOGO if m.aplica(reglas)]
        assert [m["metrica"] for m in indice["metricas"]] == aplicables
        assert len(aplicables) == cantidad
        origen = {m["metrica"]: m["origen"] for m in indice["metricas"]}
        assert sorted(s for s, o in origen.items() if o == "anterior") == sorted(_anteriores(codigo))
        for m in indice["metricas"]:
            assert set(m) == {"metrica", "titulo", "grupo", "origen", "parametro", "paginada"}
    colorloto = {m["metrica"]: m for m in a.get("/api/v1/juegos/COLORLOTO/estadisticas").json()["metricas"]}
    assert colorloto["frecuencia-colores-por-anio"]["parametro"] == "anio"
    assert colorloto["distribucion-conteo-color"]["parametro"] == "color"
    assert colorloto["comparacion-frecuencia-colores-por-ventana"]["parametro"] == "ventana"
    baloto = {m["metrica"]: m for m in a.get("/api/v1/juegos/BALOTO/estadisticas").json()["metricas"]}
    assert baloto["coocurrencia-trios"]["paginada"] is True and baloto["coocurrencia-pares"]["paginada"] is False
    assert "frecuencia-colores" not in baloto and "independencia-pares" in baloto
    miloto = {m["metrica"] for m in a.get("/api/v1/juegos/MILOTO/estadisticas").json()["metricas"]}
    assert "frecuencia-superbalota" not in miloto


@pytest.mark.parametrize("codigo,slug", CASOS)
def test_metrica_anterior_igual_que_su_receta_htmx_con_y_sin_corte(a, codigo, slug):
    for corte in (None, _corte(a, codigo)):
        base = f"/api/v1/juegos/{codigo}/estadisticas/{slug}"
        url = base if corte is None else f"{base}?hasta_numero_sorteo={corte}"
        respuesta, filas = _paginas(a, url)
        m = respuesta["metrica"]
        assert (m["slug"], m["origen"], m["estado"]) == (slug, "anterior", "ok")
        assert respuesta["muestra"]["corte"]["hasta_numero_sorteo"] == corte
        elegido = m["selector"]["valor"] if m["selector"] else None
        if m["parametro"] == "anio" or m["parametro"] == "mes":
            elegido = int(elegido)
        elif m["parametro"] == "ventana":
            elegido = int(elegido)
        tipo, parametros = _receta(codigo, slug, elegido)
        _comparar(_htmx(a, codigo, tipo, corte, parametros), respuesta, filas)


@pytest.mark.parametrize("slug,parametro,valor", [
    ("frecuencia-colores-por-anio", "anio", lambda h: h[0].fecha.year),
    ("frecuencia-colores-por-mes", "mes", lambda h: h[len(h) // 2].fecha.month),
    ("frecuencia-pares-numero-color-por-dia-semana", "dia_semana", lambda h: h[0].dia_semana),
    ("comparacion-frecuencia-pares-numero-color-por-ventana", "ventana", lambda h: 10),
    ("distribucion-conteo-color", "color", lambda h: "ROJO")])
def test_filtros_de_colorloto_iguales_que_la_consola(a, slug, parametro, valor):
    """Un valor distinto del predeterminado (el del último sorteo), tomado de la muestra sintética."""
    valor = valor(a.entorno.historicos["COLORLOTO"])
    respuesta, filas = _paginas(a, f"/api/v1/juegos/COLORLOTO/estadisticas/{slug}?{parametro}={valor}")
    assert respuesta["metrica"]["estado"] == "ok"
    m = respuesta["metrica"]
    assert m["selector"]["parametro"] == parametro and m["selector"]["valor"] == str(valor)
    tipo, parametros = _receta("COLORLOTO", slug, valor)
    _comparar(_htmx(a, "COLORLOTO", tipo, None, parametros), respuesta, filas)


def test_colorloto_asocia_numero_y_color_como_la_consola(a):
    """Cada fila trae el número y el color en columnas separadas, deserializados como la consola."""
    respuesta, filas = _paginas(a, "/api/v1/juegos/COLORLOTO/estadisticas/frecuencia-pares-numero-color")
    columnas = {c["clave"]: c["formato"] for c in respuesta["metrica"]["tablas"][0]["columnas"]}
    assert columnas["numero"] == "entero" and columnas["color"] == "color"
    receta = _htmx(a, "COLORLOTO", "frecuencia_pares_colorloto", None,
                   {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6, "politica_universo_colores": POLITICA})
    consola = {_deserializar_par_numero_color(e["valor"]): e["apariciones"] for e in receta["filas"]}
    assert {(f["numero"], f["color"]): f["apariciones"] for f in filas} == consola
    # Comprobación directa sobre la muestra: balotas de cada (número, color) en los sorteos cargados.
    contado: dict = {}
    for r in a.entorno.historicos["COLORLOTO"]:
        for par in r.pares:
            contado[par] = contado.get(par, 0) + 1
    assert all(consola[par] == n for par, n in contado.items())


def test_coocurrencia_de_trios_paginada_sin_truncar(a):
    url = "/api/v1/juegos/BALOTO/estadisticas/coocurrencia-trios"
    primera = a.get(url).json()["metrica"]["tablas"][0]
    paginacion = primera["paginacion"]
    assert paginacion["pagina"] == 1 and paginacion["por_pagina"] == 100
    assert len(primera["filas"]) == min(100, paginacion["total_filas"])
    assert paginacion["total_paginas"] == max(1, math.ceil(paginacion["total_filas"] / 100))
    fuera = a.get(f"{url}?pagina={paginacion['total_paginas'] + 1}")
    assert fuera.status_code == 422 and fuera.json()["error"]["codigo"] == "parametro_no_valido"


@pytest.mark.parametrize("url,estado", [
    ("/api/v1/juegos/BALOTO/estadisticas/frecuencia-colores", 404),
    ("/api/v1/juegos/MILOTO/estadisticas/frecuencia-superbalota", 404),
    ("/api/v1/juegos/COLORLOTO/estadisticas/frecuencia-observada-esperada", 404),
    ("/api/v1/juegos/COLORLOTO/estadisticas/independencia-pares", 404),
    ("/api/v1/juegos/BALOTO/estadisticas/frecuencia-numeros?anio=2021", 422),
    ("/api/v1/juegos/BALOTO/estadisticas/coocurrencia-pares?pagina=2", 422),
    ("/api/v1/juegos/BALOTO/estadisticas/correlaciones?pagina=1", 422),
    ("/api/v1/juegos/BALOTO/estadisticas/frecuencia-numeros?color=ROJO", 422),
    ("/api/v1/juegos/COLORLOTO/estadisticas/distribucion-conteo-color?color=MORADO", 422),
    ("/api/v1/juegos/COLORLOTO/estadisticas/distribucion-conteo-color?color=rojo", 422),
    ("/api/v1/juegos/COLORLOTO/estadisticas/comparacion-frecuencia-colores-por-ventana?ventana=7", 422),
    ("/api/v1/juegos/COLORLOTO/estadisticas/frecuencia-colores-por-mes?mes=13", 422),
    ("/api/v1/juegos/COLORLOTO/estadisticas/frecuencia-colores-por-anio?mes=2", 422),
    ("/api/v1/juegos/BALOTO/estadisticas/coocurrencia-trios?pagina=0", 422)])
def test_aplicabilidad_y_parametros_por_metrica(a, url, estado):
    r = a.get(url)
    assert r.status_code == estado
    assert r.json()["error"]["codigo"] == ("no_encontrado" if estado == 404 else "parametro_no_valido")


def test_sin_sorteos_es_sin_datos_explicito(tmp_path):
    """Juegos sin sorteos cargados (o un corte anterior al primero): «sin_datos», sin tablas vacías que
    parezcan resultados; el corte se informa en la muestra."""
    a = fa.api(tmp_path, entorno=f7.entorno(tmp_path / "datos", cargar=("BALOTO",)))
    for codigo, slug in (("COLORLOTO", "frecuencia-colores"), ("COLORLOTO", "coocurrencia-trios-colores"),
                         ("COLORLOTO", "distribucion-sumas"), ("COLORLOTO", "distribucion-conteo-color"),
                         ("MILOTO", "coocurrencia-trios")):
        r = a.get(f"/api/v1/juegos/{codigo}/estadisticas/{slug}")
        m = r.json()["metrica"]
        assert r.status_code == 200 and m["estado"] == "sin_datos" and m["tablas"] == [] and m["motivo"]
    primero = a.entorno.historicos["BALOTO"][0].numero_sorteo
    r = a.get(f"/api/v1/juegos/BALOTO/estadisticas/atrasos-numeros?hasta_numero_sorteo={primero - 1}").json()
    assert r["metrica"]["estado"] == "sin_datos" and r["muestra"]["corte"]["hasta_numero_sorteo"] == primero - 1


def test_periodo_sin_sorteos_es_explicito(a):
    m = a.get("/api/v1/juegos/COLORLOTO/estadisticas/frecuencia-colores-por-anio?anio=1990").json()["metrica"]
    assert m["estado"] == "sin_sorteos_en_el_periodo" and m["selector"]["valor"] == "1990"


def test_consultar_metricas_anteriores_no_escribe(tmp_path):
    a = fa.api(tmp_path, fichas_por_minuto=100_000)
    antes = fa.filas(a.entorno)
    for codigo, slug in CASOS:
        assert a.get(f"/api/v1/juegos/{codigo}/estadisticas/{slug}").status_code == 200
    assert fa.filas(a.entorno) == antes
    assert antes["estadisticas"] == []


def test_coste_de_cuota_igual_que_las_demas_metricas(tmp_path):
    a = fa.api(tmp_path, fichas_por_minuto=12)
    assert a.get("/api/v1/juegos/COLORLOTO/estadisticas/frecuencia-colores").headers["x-ratelimit-remaining"] == "7"
    assert a.get("/api/v1/juegos/COLORLOTO/estadisticas/correlaciones").headers["x-ratelimit-remaining"] == "2"
    r = a.get("/api/v1/juegos/COLORLOTO/estadisticas/atrasos-colores")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_historico_no_valido_es_explicito_y_no_calcula(tmp_path):
    a = fa.api(tmp_path)
    with a.entorno.engine.begin() as c:  # un sorteo de BALOTO con un número fuera de rango, a propósito
        fila = c.execute(text("SELECT n.id FROM sorteo_numeros n JOIN sorteos s ON s.id = n.sorteo_id "
                              "JOIN juegos j ON j.id = s.juego_id WHERE j.codigo = 'BALOTO' "
                              "ORDER BY s.numero_sorteo, n.posicion LIMIT 1")).one()
        c.execute(text("UPDATE sorteo_numeros SET numero = 99 WHERE id = :i"), {"i": fila.id})
    antes = fa.filas(a.entorno)
    for url in ("/api/v1/juegos/BALOTO/estadisticas/coocurrencia-pares", "/api/v1/juegos/BALOTO/estadisticas/panel"):
        r = a.get(url)
        error = r.json()["error"]
        assert r.status_code == 409 and error["codigo"] == "historico_no_valido"
        assert "99" not in error["mensaje"] and "detalles" not in error
    assert fa.filas(a.entorno) == antes


def test_base_no_disponible_en_metrica_anterior(tmp_path):
    a = fa.api(tmp_path)

    def caida():
        from sqlalchemy.exc import OperationalError
        raise OperationalError("SELECT 1", {}, Exception("conexion rechazada"))
        yield  # pragma: no cover

    from app.api.publica import dependencias as d
    a.app.dependency_overrides[d.sesion_de_lectura] = caida
    r = a.get("/api/v1/juegos/COLORLOTO/estadisticas/frecuencia-colores")
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "base_no_disponible"
    assert "conexion" not in r.text
