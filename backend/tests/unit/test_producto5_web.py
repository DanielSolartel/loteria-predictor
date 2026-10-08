"""Producto 5: web, API y comando.

- los GET no escriben (bytes del almacen y del registro iguales);
- los POST exigen la propia maquina y el token local;
- progreso por juego, trabajo ocupado (409) y fallo al lanzar el hilo
  (interrumpida, cerrojo libre);
- paridad HTML / API / comando / CSV / JSON con los mismos artefactos;
- codigos de salida estables del comando."""
from __future__ import annotations

import hashlib
import io
import json
import re

import pytest

from app.application.interfaces.ejecutor_carteras import TiempoAgotadoError
from app.application.ml.registro_prospectivo import serializar_entrada
from app.application.use_cases.carteras import EjecutorCarterasEnEsteProceso
from scripts import carteras_modelos as cli
from tests.unit import fixtures_producto5 as f5

TAMANOS = {"BALOTO": 70, "BALOTO_REVANCHA": 70, "MILOTO": 70, "COLORLOTO": 70}
GENERAR = {"modelo": "logistica_regularizada", "cantidad": 5, "diversidad": "limitada", "semilla": 42}


@pytest.fixture
def entorno(tmp_path):
    return f5.entorno(tmp_path, TAMANOS)


@pytest.fixture
def cliente(entorno):
    servicio = entorno.carteras()
    c = f5.cliente(entorno, carteras=servicio)
    yield c, servicio
    f5.limpiar()


def _huellas(directorio):
    return {str(p.relative_to(directorio)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directorio.rglob("*")) if p.is_file()}


def _comando(servicio, *argv):
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(list(argv), carteras_factory=lambda: servicio, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def _publicar(c, token, slug="miloto", **datos):
    r = c.post("/carteras/generar", data={"juego": slug, **GENERAR, **datos, "token_local": token},
               follow_redirects=False)
    assert r.status_code == 303, r.text[:500]
    pagina = c.get(r.headers["location"]).text
    return re.search(r"/carteras/guardadas/([0-9a-f]{64})", pagina).group(1)


def test_los_get_no_escriben(cliente, entorno):
    c, s = cliente
    token = f5.token(c)
    clave = _publicar(c, token)
    s.ahora("simulacion", ["MILOTO"], {"cartera": clave, "simulaciones": 1000, "semilla": 1})
    s.ahora("comparacion", ["MILOTO"], {"protocolo": {"bloques": 1, "perfil": "reducido"}})
    simulacion = s.simulaciones_de_cartera(clave)[0].identificador
    comparacion = s.comparaciones("MILOTO")[0].identificador
    ejecucion = s.recientes(1)[0]["id"]
    antes = _huellas(entorno.directorio)
    rutas = ["/carteras", "/carteras/miloto", "/carteras/baloto", "/carteras/colorloto", "/carteras/baloto-revancha",
             f"/carteras/guardadas/{clave}", f"/carteras/guardadas/{clave}/exportar.csv",
             f"/carteras/guardadas/{clave}/exportar.json", f"/carteras/simulaciones/{simulacion}",
             f"/carteras/simulaciones/{simulacion}/exportar.csv", f"/carteras/comparaciones/{comparacion}",
             f"/carteras/ejecuciones/{ejecucion}", f"/carteras/ejecuciones/{ejecucion}/estado",
             "/carteras/miloto/seguimiento", "/api/carteras/catalogo", "/api/carteras/MILOTO",
             f"/api/carteras/guardadas/{clave}", f"/api/carteras/simulaciones/{simulacion}",
             f"/api/carteras/comparaciones/{comparacion}", "/api/carteras/MILOTO/lineas",
             "/api/carteras/MILOTO/configuracion", "/api/carteras/MILOTO/seguimiento", "/api/carteras/ejecuciones"]
    for ruta in rutas:
        assert c.get(ruta).status_code == 200, ruta
    assert _huellas(entorno.directorio) == antes


def test_los_post_exigen_la_propia_maquina_y_el_token(entorno):
    servicio = entorno.carteras()
    c = f5.cliente(entorno, carteras=servicio)
    try:
        token = f5.token(c)
        acciones = [("/carteras/generar", {"juego": "miloto", **GENERAR}), ("/carteras/comparar", {"juego": "todos"}),
                    ("/carteras/configuradas", {"juego": "todos"}), ("/carteras/miloto/configurar", GENERAR)]
        for ruta, datos in acciones:
            assert c.post(ruta, data=datos).status_code == 403  # sin token
            assert c.post(ruta, data={**datos, "token_local": "otro"}).status_code == 403
            r = c.post(ruta, data={**datos, "token_local": token}, headers={"Origin": "http://evil.example"})
            assert r.status_code == 403
        assert servicio.recientes() == [] and servicio.configuraciones("MILOTO") == []
        ajeno = f5.cliente(entorno, carteras=servicio, client=("10.0.0.5", 5000))
        assert ajeno.post("/carteras/generar", data={"juego": "miloto", **GENERAR, "token_local": token}).status_code == 403
    finally:
        f5.limpiar()


def test_progreso_ocupado_y_fallo_al_lanzar(entorno):
    servicio = entorno.carteras()
    pendientes = []
    c = f5.cliente(entorno, carteras=servicio, lanzador=lambda funcion, inicio: pendientes.append((funcion, inicio)))
    try:
        token = f5.token(c)
        r = c.post("/carteras/generar", data={"juego": "miloto", **GENERAR, "token_local": token}, follow_redirects=False)
        assert r.status_code == 303
        pagina = c.get(r.headers["location"]).text
        assert "En curso" in pagina and "hx-get" in pagina and "progreso-miloto" in pagina
        ocupado = c.post("/carteras/generar", data={"juego": "miloto", **GENERAR, "token_local": token})
        assert ocupado.status_code == 409 and "en curso" in ocupado.text
        funcion, inicio = pendientes.pop()
        funcion(inicio)  # el hilo termina
        final = c.get(r.headers["location"]).text
        assert "Terminado." in final and "abrir la cartera" in final and "hx-get" not in final
    finally:
        f5.limpiar()

    def falla(funcion, inicio):
        raise RuntimeError("can't start new thread")
    c = f5.cliente(entorno, carteras=servicio, lanzador=falla)
    try:
        token = f5.token(c)
        r = c.post("/carteras/generar", data={"juego": "colorloto", **GENERAR, "modelo": "uniforme_paleta",
                                               "token_local": token})
        assert r.status_code == 500 and "No se pudo iniciar" in r.text
        ultima = servicio.recientes(1)[0]
        assert ultima["estado"] == "interrumpida" and ultima["orden"] == ["COLORLOTO"]
        assert servicio.ahora("cartera", ["COLORLOTO"], {**GENERAR, "modelo": "uniforme_paleta"})["estado"] == "exito"
        invalido = c.post("/carteras/generar", data={"juego": "miloto", **GENERAR, "cantidad": 21, "token_local": token})
        assert invalido.status_code == 422 and servicio.recientes(1)[0]["orden"] == ["COLORLOTO"]
        assert c.get("/carteras/guardadas/" + "0" * 64).status_code == 404
        assert c.get("/carteras/nada").status_code == 404
        assert c.get("/carteras/ejecuciones/no-existe").status_code == 404
    finally:
        f5.limpiar()


def test_paridad_html_api_comando_csv_y_json(cliente, entorno):
    c, s = cliente
    token = f5.token(c)
    clave = _publicar(c, token, slug="baloto")
    guardado = s.cartera(clave)
    combinaciones = guardado.artefacto["cartera"]["combinaciones"]
    html = c.get(f"/carteras/guardadas/{clave}").text
    for combinacion in combinaciones:
        bolitas = "".join(f'<span class="numero-bolita">{n}</span>' for n in combinacion["numeros"])
        assert bolitas in html
    api = c.get(f"/api/carteras/guardadas/{clave}").json()
    assert api["cartera"] == guardado.artefacto
    codigo, salida, _ = _comando(s, "consultar", "--id", clave)
    assert codigo == 0 and json.loads(salida)["artefacto"] == guardado.artefacto
    csv_web = c.get(f"/carteras/guardadas/{clave}/exportar.csv")
    assert csv_web.headers["content-type"].startswith("text/csv") and "attachment" in csv_web.headers["content-disposition"]
    csv_api = c.get(f"/api/carteras/guardadas/{clave}/csv").text
    codigo, csv_cli, _ = _comando(s, "exportar", "--cartera", clave, "--formato", "csv")
    assert csv_web.text == csv_api == csv_cli and len(csv_cli.splitlines()) == 6
    json_web = c.get(f"/carteras/guardadas/{clave}/exportar.json").content
    ruta = next((entorno.directorio / "carteras" / "BALOTO").glob(f"*/*-{clave}.json"))
    assert json_web == serializar_entrada(guardado.artefacto) == ruta.read_bytes()
    codigo, json_cli, _ = _comando(s, "exportar", "--cartera", clave, "--formato", "json")
    assert json_cli.encode("utf-8") == json_web and json_web.endswith(b"}\n")
    codigo, salida, _ = _comando(s, "simular", "--cartera", clave, "--simulaciones", "1000")
    sim = json.loads(salida)["juegos"]["BALOTO"]["resultado"]
    assert codigo == 0 and c.get(f"/api/carteras/simulaciones/{sim}").json()["simulacion"] == s.simulacion(sim).artefacto
    assert c.get(f"/carteras/simulaciones/{sim}/exportar.csv").text == _comando(
        s, "exportar", "--simulacion", sim)[1] == c.get(f"/api/carteras/simulaciones/{sim}/csv").text


def test_configurar_desde_la_web_y_generar_las_configuradas(cliente, entorno):
    c, s = cliente
    token = f5.token(c)
    r = c.post("/carteras/miloto/configurar", data={**GENERAR, "token_local": token}, follow_redirects=False)
    assert r.status_code == 303 and s.configuracion_vigente("MILOTO").artefacto["version"] == 1
    assert "versión 1" in c.get("/carteras/miloto").text
    r = c.post("/carteras/configuradas", data={"juego": "todos", "token_local": token}, follow_redirects=False)
    pagina = c.get(r.headers["location"]).text
    assert "Configuración v1" in pagina and "sin configuración" in pagina
    assert pagina.count('class="card stat-card p-3 h-100"') == 4
    assert c.get("/api/carteras/MILOTO/configuracion").json()["vigente"]["version"] == 1


def test_codigos_de_salida_del_comando(entorno, tmp_path):
    s = entorno.carteras()
    assert _comando(s, "nada")[0] == 2
    assert _comando(s, "generar", "--juego", "MILOTO")[0] == 2  # falta --modelo
    assert _comando(s, "generar", "--juego", "MILOTO", "--modelo", "nada")[0] == 2
    assert _comando(s, "consultar", "--id", "f" * 64)[0] == 2
    corto = f5.entorno(tmp_path / "corto", {"MILOTO": 59}).carteras()
    assert _comando(corto, "generar", "--juego", "MILOTO", "--modelo", "ensemble_temporal")[0] == 4
    assert _comando(corto, "comparar", "--juego", "MILOTO", "--perfil", "reducido")[0] == 4
    assert _comando(s, "generar", "--juego", "todos", "--configuradas")[0] == 5  # ninguna configuracion
    codigo, salida, errores = _comando(s, "generar", "--juego", "MILOTO", "--modelo", "uniforme")
    assert codigo == 0 and "puede tardar" in errores
    clave = json.loads(salida)["juegos"]["MILOTO"]["resultado"]
    assert _comando(s, "verificar", "--cartera", clave)[0] == 0
    inicio = s.iniciar("cartera", ["MILOTO"], {**GENERAR, "modelo": "uniforme"})
    try:
        assert _comando(s, "generar", "--juego", "MILOTO", "--modelo", "uniforme")[0] == 6
    finally:
        inicio.cerrojos.liberar()

    class Agotado(EjecutorCarterasEnEsteProceso):
        def fuente(self, *a, **k):
            raise TiempoAgotadoError("el trabajo supero el tiempo maximo de 1 s y se detuvo")
    agotado = entorno.carteras(ejecutor=Agotado())
    assert _comando(agotado, "generar", "--juego", "MILOTO", "--modelo", "hgb_clasificador")[0] == 9
    ruta = next((entorno.directorio / "carteras" / "MILOTO").glob(f"*/*-{clave}.json"))
    ruta.write_bytes(ruta.read_bytes().replace(b'"cartera"', b'"cartera" ', 1))
    assert _comando(s, "verificar", "--cartera", clave)[0] == 8
    entorno.base_caida = True
    assert _comando(s, "generar", "--juego", "MILOTO", "--modelo", "uniforme", "--semilla", "3")[0] == 3
    codigo, salida, _ = _comando(s, "rutas")
    rutas = json.loads(salida)
    assert codigo == 0 and rutas["directorio_carteras_modelos"].endswith("carteras")
    assert "database_url" not in salida.lower() and "postgresql" not in salida.lower()
