"""Fase 9.1, pasarela: lista cerrada igual al OpenAPI versionado, rutas
ambiguas rechazadas, parametros acotados y validacion semantica en la API."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pasarela import rutas
from tests.unit.pasarela import fixtures_pasarela as fp

OPENAPI = Path(__file__).resolve().parents[4] / "frontend" / "src" / "api" / "openapi.json"


@pytest.fixture
def entorno(tmp_path):
    with fp.destino_falso() as d:
        yield d, fp.pasarela(d.destino, fp.dist(tmp_path), fp.clave_sintetica())


def test_la_lista_cerrada_es_el_openapi_versionado_sin_exclusiones_en_paths():
    doc = json.loads(OPENAPI.read_text(encoding="utf-8"))
    gets = {p for p, ops in doc["paths"].items() if "get" in ops}
    assert {p for p, ops in doc["paths"].items() if set(ops) != {"get"}} == set()
    assert {r.plantilla for r in rutas.RUTAS} == gets and rutas.EXCLUIDAS.isdisjoint(gets)
    for r in rutas.RUTAS:
        consulta = {p["name"] for p in doc["paths"][r.plantilla]["get"].get("parameters", []) if p["in"] == "query"}
        assert r.consulta == consulta, r.plantilla
        ruta = {p["name"] for p in doc["paths"][r.plantilla]["get"].get("parameters", []) if p["in"] == "path"}
        assert set(r.patron.groupindex) == ruta, r.plantilla


@pytest.mark.parametrize("url", ["/api/v1/docs", "/api/v1/openapi.json", "/api/sorteos", "/api/juegos",
                                 "/api/v2/juegos", "/api", "/api/v1", "/api/v1/juegos/BALOTO/simular",
                                 "/api/v1/sorteos", "/api/v1/juegos/baloto/sorteos/x1",
                                 "/api/v1/juegos/BALOTO/estadisticas/Mayus"])
def test_rutas_de_api_desconocidas_reciben_error_de_api(entorno, url):
    d, app = entorno
    r = fp.cliente(app).get(url)
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert r.json()["error"]["codigo"] == "ruta_no_disponible" and r.headers["cache-control"] == "no-store"
    assert d.recibidas == []


@pytest.mark.parametrize("ruta", [b"/api/v1/juegos/../estado", b"/api/v1/./juegos", b"/api/v1//juegos",
                                  b"/api/v1/juegos/", b"/api/v1/juegos%2FBALOTO", b"/api/v1/juegos/BALOTO%2e%2e",
                                  b"/api/v1/juegos\\BALOTO", b"/api/v1/juegos/BALOTO\x00", b"/api/v1/juegos/\x1b",
                                  b"/api/v1/juegos/BAL OTO", "/api/v1/juegos/BALOTÓ".encode(), b"/api/v1/%61pi",
                                  b"//api/v1/juegos", b"/api/v1/" + b"a" * 600])
def test_rutas_ambiguas_traversal_y_caracteres_raros(entorno, ruta):
    d, app = entorno
    estado, cabeceras, cuerpo = fp.crudo(app, ruta)
    assert estado == 400 and json.loads(cuerpo)["error"]["codigo"] == "ruta_no_valida"
    assert cabeceras["cache-control"] == "no-store" and len(cabeceras["x-request-id"]) == 32
    assert d.recibidas == []


@pytest.mark.parametrize("consulta, codigo", [
    (b"x=1", "parametro_no_admitido"), (b"pagina=1&pagina=2", "parametro_repetido"),
    (b"pagina=" + b"9" * 81, "parametro_no_valido"), (b"orden=fecha%20desc", "parametro_no_valido"),
    (b"orden=%00", "parametro_no_valido"), (b"desde=2021%2F01%2F01", "parametro_no_valido"),
    (b"pagina=", "parametro_no_valido"), (b"pagina", "parametro_no_valido"),
    (b"&".join(b"orden=%d" % i for i in range(20)), "parametro_no_valido"),
    (b"orden=" + b"a" * 80 + b"&desde=" + b"b" * 80 + b"&hasta=" + b"c" * 80 + b"&numero_desde=" + b"1" * 80
     + b"&numero_hasta=" + b"2" * 80 + b"&pagina=" + b"3" * 80 + b"&por_pagina=" + b"4" * 80, "consulta_demasiado_larga"),
    (b"pagina=%C3%A9", "parametro_no_valido")])
def test_parametros_acotados_en_nombre_tamano_y_multiplicidad(entorno, consulta, codigo):
    d, app = entorno
    estado, _, cuerpo = fp.crudo(app, b"/api/v1/juegos/BALOTO/sorteos", consulta=consulta)
    error = json.loads(cuerpo)["error"]
    assert estado == 422 and error["codigo"] == codigo
    assert consulta.decode("latin-1")[:20] not in json.dumps(error) or not consulta  # sin eco de la entrada
    assert d.recibidas == []


@pytest.mark.parametrize("consulta, codigo", [
    (b"color=ROJO&color=AZUL", "parametro_repetido"), (b"pagina=1&pagina=1", "parametro_repetido"),
    (b"color=ROJO%20AZUL", "parametro_no_valido"), (b"pagina=" + b"9" * 81, "parametro_no_valido"),
    (b"colores=ROJO", "parametro_no_admitido"), (b"por_pagina=500", "parametro_no_admitido")])
def test_filtros_de_metrica_de_la_9_2_acotados(entorno, consulta, codigo):
    """`color` y `pagina` (Fase 9.2) solo en la ruta de métrica, una vez y con caracteres admitidos; el
    tamaño de página no se elige desde el navegador (la API fija 100 filas)."""
    d, app = entorno
    estado, _, cuerpo = fp.crudo(app, b"/api/v1/juegos/COLORLOTO/estadisticas/distribucion-conteo-color", consulta=consulta)
    assert estado == 422 and json.loads(cuerpo)["error"]["codigo"] == codigo
    assert d.recibidas == []


@pytest.mark.parametrize("consulta, codigo", [
    (b"hasta=1&hasta=2", "parametro_repetido"), (b"hasta=2190%20", "parametro_no_valido"),
    (b"linea=carteras:uniforme-v1", "parametro_no_admitido"), (b"cartera=" + b"a" * 64, "parametro_no_admitido"),
    (b"hasta=" + b"9" * 81, "parametro_no_valido")])
def test_fiabilidad_de_la_9_3_solo_admite_hasta(entorno, consulta, codigo):
    """La ruta de fiabilidad (Fase 9.3) solo reenvia `hasta`, una vez y con caracteres admitidos; la
    linea de Producto 6 no se elige desde el navegador."""
    d, app = entorno
    estado, _, cuerpo = fp.crudo(app, b"/api/v1/juegos/BALOTO/fiabilidad", consulta=consulta)
    assert estado == 422 and json.loads(cuerpo)["error"]["codigo"] == codigo
    assert d.recibidas == []


def test_la_validacion_semantica_es_de_la_api(entorno):
    d, app = entorno
    d.json(422, {"error": {"codigo": "parametro_no_valido", "mensaje": "Parámetro no válido", "solicitud": "b" * 32,
                           "detalles": [{"ubicacion": ["query", "pagina"], "mensaje": "debe ser >= 1"}]}})
    r = fp.cliente(app).get("/api/v1/juegos/QUINELA/sorteos?pagina=0&orden=fecha_asc&desde=2021-13-40")
    assert r.status_code == 422 and r.json()["error"]["detalles"][0]["ubicacion"] == ["query", "pagina"]
    assert [x.ruta for x in d.recibidas] == ["/api/v1/juegos/QUINELA/sorteos?pagina=0&orden=fecha_asc&desde=2021-13-40"]


def test_cada_plantilla_se_reenvia_con_su_ruta_y_consulta(entorno):
    d, app = entorno
    c = fp.cliente(app)
    urls = ["/api/v1/salud", "/api/v1/estado", "/api/v1/juegos", "/api/v1/juegos/COLORLOTO",
            "/api/v1/juegos/BALOTO/sorteos?pagina=2&por_pagina=100&desde=2021-01-01&hasta=2021-12-31"
            "&numero_desde=2081&numero_hasta=2140&orden=numero_asc",
            "/api/v1/juegos/MILOTO/sorteos/530", "/api/v1/juegos/MILOTO/estadisticas",
            "/api/v1/juegos/MILOTO/estadisticas/resumen?hasta_numero_sorteo=560",
            "/api/v1/juegos/MILOTO/estadisticas/panel?hasta_numero_sorteo=560",
            "/api/v1/juegos/BALOTO/estadisticas/frecuencia-numeros-por-dia-semana?dia_semana=miercoles"
            "&hasta_numero_sorteo=2100",
            "/api/v1/juegos/COLORLOTO/estadisticas/distribucion-conteo-color?color=ROJO&hasta_numero_sorteo=40",
            "/api/v1/juegos/BALOTO/estadisticas/coocurrencia-trios?pagina=3&hasta_numero_sorteo=2100",
            "/api/v1/juegos/BALOTO/predicciones?cartera=" + "a" * 64 + "&historial=50",
            "/api/v1/juegos/BALOTO/fiabilidad?hasta=2190",
            "/api/v1/juegos/BALOTO/modelos-guardados?pagina=1&por_pagina=10&modelo=logistica&perfil=reducido",
            "/api/v1/juegos/BALOTO/modelos-guardados/" + "b" * 64,
            "/api/v1/juegos/COLORLOTO/carteras-guardadas?pagina=1&por_pagina=10&linea=uniforme_paleta-v1&desde=1&hasta=40",
            "/api/v1/juegos/COLORLOTO/carteras-guardadas/" + "c" * 64,
            "/api/v1/juegos/MILOTO/resultados?procedencia=carteras&linea=carteras%3Auniforme-v1&tipo=seguimiento"
            "&desde=1&hasta=80&objetivo=60&pagina=1&por_pagina=10",
            "/api/v1/juegos/BALOTO/simulaciones?limite=50",
            "/api/v1/simulaciones/344d4a67-798a-4b2f-85fc-0f53dd183e99"]
    for url in urls:
        assert c.get(url).status_code == 200, url
    assert [x.ruta for x in d.recibidas] == urls
    assert {rutas.buscar(u.split("?")[0]).plantilla for u in urls} == {r.plantilla for r in rutas.RUTAS}
