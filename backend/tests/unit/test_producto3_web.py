"""Producto 3: panel diario, rendimiento, ejecuciones y API. Se prueba el
comportamiento (GET sin efectos, POST protegido, progreso persistente,
estados de error legibles y la coincidencia JSON = tabla = grafica)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.application.use_cases.pronostico_experimental import JUEGOS, GenerarPronosticoExperimental
from tests.unit import fixtures_producto3 as f3

NOMBRES = ("Baloto", "Baloto Revancha", "MiLoto", "ColorLoto")


@pytest.fixture
def entorno(tmp_path):
    return f3.entorno(tmp_path)


@pytest.fixture
def cliente(entorno):
    c = f3.cliente(entorno)
    yield c
    f3.limpiar()


def _token(c):
    return re.search(r'name="token_local" value="([^"]+)"', c.get("/operacion").text).group(1)


def _sin_efectos(entorno):
    assert entorno.abiertos == [] and entorno.importador.llamadas == []
    assert not any(entorno.almacen._directorio.rglob("*.json"))


def test_get_no_sincroniza_ni_genera(cliente, entorno):
    for url in ("/operacion", "/rendimiento", "/rendimiento?juego=MILOTO", "/api/operacion/panel",
                "/api/operacion/ejecuciones", "/api/rendimiento/COLORLOTO"):
        assert cliente.get(url).status_code == 200, url
    _sin_efectos(entorno)


def test_panel_cuatro_juegos_enlaces_y_menu(cliente, entorno):
    texto = cliente.get("/operacion").text
    assert '<body class="producto1-impresion">' in texto
    for nombre in NOMBRES:
        assert f"<h5 class=\"mb-0\">{nombre}</h5>" in texto
    for slug, codigo in (("baloto", "BALOTO"), ("miloto", "MILOTO"), ("colorloto", "COLORLOTO")):
        assert f'href="/pronosticos/{slug}"' in texto and f'href="/estadisticas/{slug}/resumen"' in texto
        assert f'href="/rendimiento?juego={codigo}"' in texto
    assert texto.count('name="modo" value="actualizar"') == 5 and texto.count('name="modo" value="local"') == 5
    assert 'href="/operacion"' in texto and 'href="/rendimiento"' in texto  # menu
    assert 'href="/pronosticos"' in texto and 'href="/importacion"' in texto  # el menu existente se conserva
    assert "Todavía no hay pronósticos guardados." in texto
    dashboard = (Path(__file__).resolve().parents[2] / "app" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    assert '<a href="/operacion"' in dashboard and '<a href="/pronosticos"' in dashboard


def test_post_protegido_no_ejecuta(entorno):
    try:
        token = _token(f3.cliente(entorno))
        externo = f3.cliente(entorno, client=("203.0.113.9", 4000))
        assert externo.post("/operacion/ejecutar", data={"juego": "todos", "modo": "local",
                                                          "token_local": token}).status_code == 403
        local = f3.cliente(entorno)
        assert local.post("/operacion/ejecutar", data={"juego": "todos", "modo": "local"}).status_code == 403
        assert local.post("/operacion/ejecutar", data={"juego": "todos", "modo": "local", "token_local": token},
                          headers={"Origin": "http://otro.example"}).status_code == 403
        assert local.post("/operacion/ejecutar", data={"juego": "QUINA", "modo": "local",
                                                       "token_local": token}).status_code == 422
        _sin_efectos(entorno)
    finally:
        f3.limpiar()


def test_ejecutar_todos_con_datos_locales_y_ver_el_resultado(cliente, entorno):
    r = cliente.post("/operacion/ejecutar", data={"juego": "todos", "modo": "local", "token_local": _token(cliente)},
                     follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/operacion/ejecuciones/")
    identificador = r.headers["location"].rsplit("/", 1)[1]
    detalle = cliente.get(r.headers["location"]).text
    assert "Completada: todos los juegos terminaron bien." in detalle and "hx-trigger" not in detalle
    assert detalle.count("· nuevo") == 4  # cuatro pronosticos nuevos
    assert entorno.importador.llamadas == [] and {m for _, m in entorno.abiertos} == {"local"}
    panel = cliente.get("/operacion").text
    assert "Todavía no hay pronósticos guardados." not in panel and f"/operacion/ejecuciones/{identificador}" in panel
    assert "pronóstico nuevo" in panel and "Resultado:</strong>\n            pendiente" in panel
    # El progreso es persistente: otra instancia (p. ej. tras reiniciar uvicorn) lo lee igual.
    otro = f3.cliente(entorno)
    assert otro.get(f"/api/operacion/ejecuciones/{identificador}").json()["estado"] == "exito"


def test_ejecucion_activa_muestra_en_curso_y_no_se_duplica(entorno):
    pendientes = []
    c = f3.cliente(entorno, lanzador=lambda funcion, inicio: pendientes.append((funcion, inicio)))
    try:
        token = _token(c)
        r = c.post("/operacion/ejecutar", data={"juego": "MILOTO", "modo": "local", "token_local": token},
                   follow_redirects=False)
        assert r.status_code == 303
        identificador = r.headers["location"].rsplit("/", 1)[1]
        en_curso = c.get(r.headers["location"]).text
        assert "En curso." in en_curso and f'hx-get="/operacion/ejecuciones/{identificador}/estado"' in en_curso
        segundo = c.post("/operacion/ejecutar", data={"juego": "todos", "modo": "actualizar", "token_local": token})
        assert segundo.status_code == 409 and f"/operacion/ejecuciones/{identificador}" in segundo.text
        assert "Ejecución en curso" in c.get("/operacion").text
        funcion, inicio = pendientes.pop()
        funcion(inicio)
        assert "Completada" in c.get(f"/operacion/ejecuciones/{identificador}/estado").text
        assert entorno.importador.llamadas == []
    finally:
        f3.limpiar()


def test_estados_de_error_legibles_por_tarjeta(cliente, entorno):
    GenerarPronosticoExperimental(entorno.juegos, entorno.resultados, entorno.almacen, reloj=f3.RELOJ,
                                  configuraciones=f3.CONFIGS).ejecutar("MILOTO")
    ruta = next((entorno.almacen._directorio / "MILOTO").glob("*.json"))
    ruta.write_bytes(ruta.read_bytes()[:-3])  # alterado
    original = entorno.resultados.listar_resultados_colorloto

    def caida(*_a, **_k):
        raise ConnectionError("connection to server failed: Connection refused")

    entorno.resultados.listar_resultados_colorloto = caida
    entorno.resultados.colorloto.clear()
    texto = cliente.get("/operacion").text
    assert "artefacto(s) alterado(s) o ilegible(s)" in texto
    assert "No se pudo leer el historico: Sin conexion con la base de datos." in texto
    assert "Traceback" not in texto and texto.count("tarjeta-juego") == 4
    entorno.resultados.listar_resultados_colorloto = original
    vacio = cliente.get("/operacion").text
    assert "No hay sorteos cargados para este juego." in vacio


def test_registro_ilegible_y_ejecucion_inexistente(cliente, entorno):
    carpeta = entorno.directorio_operacion / "ejecuciones"
    carpeta.mkdir(parents=True)
    (carpeta / "20261001T000000Z-deadbeef.json").write_text("{roto", encoding="utf-8")
    assert "registro ilegible" in cliente.get("/operacion").text
    assert cliente.get("/operacion/ejecuciones/20261001T000000Z-00000000").status_code == 404
    assert cliente.get("/operacion/ejecuciones/no-valido").status_code == 404
    assert cliente.get("/api/operacion/ejecuciones/no-valido").status_code == 404


def _preparar_rendimiento(entorno):
    for hasta in (60, 61, 62):
        GenerarPronosticoExperimental(entorno.juegos, entorno.resultados, entorno.almacen, reloj=f3.RELOJ,
                                      configuraciones=f3.CONFIGS).ejecutar("MILOTO", hasta_numero_sorteo=hasta)
    GenerarPronosticoExperimental(entorno.juegos, entorno.resultados, entorno.almacen, reloj=f3.RELOJ,
                                  configuraciones=f3.CONFIGS).ejecutar("MILOTO")


@pytest.mark.parametrize("emision", ["todas", "retrospectiva", "seguimiento"])
def test_rendimiento_json_tabla_y_grafica_coinciden(cliente, entorno, emision):
    _preparar_rendimiento(entorno)
    j = cliente.get(f"/api/rendimiento/MILOTO?emision={emision}").json()
    html = cliente.get(f"/rendimiento?juego=MILOTO&emision={emision}").text
    tabla = html.split("<h6>Objetivos</h6>", 1)[1].split("</table>", 1)[0]
    assert tabla.count("<tr>") - 1 == len(j["filas"])
    for tipo, agg in j["por_tipo"].items():
        bloque = html.split(f'id="tipo-{tipo}"', 1)[1].split('<div class="card stat-card', 1)[0]
        assert f"incluidos {agg['incluidos']} · pendientes {agg['pendientes']} · excluidos {agg['excluidos']}" in bloque
        assert bloque.count("<circle") == len(agg["serie"])
        serie_html = bloque.split('<div class="solo-impresion-bloque">', 1)[1] if agg["serie"] else ""
        assert serie_html.count("<tr><td>") == len(agg["serie"])
    assert set(j["por_tipo"]) == ({"retrospectiva", "seguimiento"} if emision == "todas" else {emision})
    if emision == "seguimiento":
        assert [f["objetivo"] for f in j["filas"]] == [85] and j["por_tipo"]["seguimiento"]["pendientes"] == 1


def test_api_rendimiento_y_ejecuciones_errores(cliente, entorno):
    assert cliente.get("/api/rendimiento/QUINA").status_code == 404
    assert cliente.get("/api/rendimiento/MILOTO?emision=favorable").status_code == 422
    assert cliente.get("/rendimiento?juego=QUINA").status_code == 404
    assert cliente.get("/api/operacion/ejecuciones/20261001T000000Z-00000000").status_code == 404
    panel = cliente.get("/api/operacion/panel").json()
    assert [t["codigo"] for t in panel["juegos"]] == list(JUEGOS)
