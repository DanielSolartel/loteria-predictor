"""Fase 7: consumidores del caso de uso comun -web (`/simulaciones`), API
interna (`/api/simulaciones`) y comando `python -m scripts.simulaciones`-
con la aplicacion real y el caso de uso sintetico (SQLite aislado)."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from sqlalchemy import text

from scripts import simulaciones as cli
from tests.unit.simulaciones import fixtures_fase7 as f7

APP = Path(__file__).resolve().parents[3] / "app"


@pytest.fixture
def e(tmp_path):
    entorno = f7.entorno(tmp_path, cargar=("MILOTO", "BALOTO"))
    yield entorno
    f7.limpiar()


def _publicar(e, juego="MILOTO", iteraciones=100):
    return e.servicio().ahora(juego, iteraciones, 1)["juegos"][juego]["resultado"]


# ---------------------------------------------------------------------------
# Web
# ---------------------------------------------------------------------------

def test_panel_solo_lectura_con_los_cuatro_juegos(e):
    c = f7.cliente(e)
    antes = e.filas()
    r = c.get("/simulaciones")
    assert r.status_code == 200
    for nombre in ("Baloto", "Baloto Revancha", "MiLoto", "ColorLoto"):
        assert nombre in r.text
    assert "no es confirmatoria" in r.text.lower() and "AUTORIZA_EVALUACION = False" in r.text
    for i in ("100", "1.000", "10.000", "100.000", "1.000.000"):
        assert f">{i}</option>" in r.text
    assert 'href="/simulaciones"' in r.text and "nav-link active" in r.text
    assert e.filas() == antes and not e.operacion.exists()


def test_lanzar_seguir_abrir_y_exportar(e):
    c = f7.cliente(e)
    tok = f7.token(c)
    r = c.post("/simulaciones/simular", data={"token_local": tok, "juego": "miloto", "iteraciones": 1000,
                                              "semilla": "", "corte": ""}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/simulaciones/ejecuciones/")
    eid = r.headers["location"].rsplit("/", 1)[1]
    pagina = c.get(r.headers["location"])
    assert pagina.status_code == 200 and "abrir el resultado" in pagina.text
    estado = c.get(f"/simulaciones/ejecuciones/{eid}/estado")
    assert estado.status_code == 200 and "hx-get" not in estado.text  # terminada: deja de sondear
    fila = e.filas()[0]
    ident = str(fila["id"])
    resultado = c.get(f"/simulaciones/resultados/{ident}")
    assert resultado.status_code == 200
    for nombre in ("dispersion_frecuencia_numeros", "media_pares_consecutivos", fila["parametros"]["clave"]):
        assert nombre in resultado.text
    descarga = c.get(f"/simulaciones/resultados/{ident}/exportar.csv")
    assert descarga.status_code == 200 and "attachment" in descarga.headers["content-disposition"]
    assert len(list(csv.reader(io.StringIO(descarga.text)))) == 1 + 5
    exportada = json.loads(c.get(f"/simulaciones/resultados/{ident}/exportar.json").text)
    assert exportada["resultado_resumen"] == fila["resultado_resumen"]
    v = c.post(f"/simulaciones/resultados/{ident}/verificar", data={"token_local": tok})
    assert v.status_code == 200 and "coincide con el simulado" in v.text
    otra = c.post("/simulaciones/simular", data={"token_local": tok, "juego": "miloto", "iteraciones": 1000},
                  follow_redirects=True)
    assert "resultado ya existente" in otra.text and len(e.filas()) == 1


def test_post_protegido_y_parametros_no_validos(e):
    c = f7.cliente(e)
    assert c.post("/simulaciones/simular", data={"token_local": "x", "juego": "miloto", "iteraciones": 100}
                  ).status_code == 403
    ajena = f7.cliente(e, client=("10.0.0.8", 4000))
    assert ajena.post("/simulaciones/simular", data={"token_local": f7.token(c), "juego": "miloto",
                                                      "iteraciones": 100}).status_code == 403
    tok = f7.token(c)
    for datos in ({"juego": "miloto", "iteraciones": 5000}, {"juego": "quinela", "iteraciones": 100},
                  {"juego": "miloto", "iteraciones": 100, "semilla": "abc"},
                  {"juego": "miloto", "iteraciones": 100, "corte": "-4"}):
        r = c.post("/simulaciones/simular", data={"token_local": tok, **datos})
        assert r.status_code == 422, datos
    assert c.post(f"/simulaciones/resultados/{'0' * 32}/verificar", data={"token_local": "x"}).status_code == 403
    assert e.filas() == []


def test_simulacion_activa_responde_409(e):
    c = f7.cliente(e, lanzador=lambda funcion, inicio: None)  # queda en curso
    tok = f7.token(c)
    assert c.post("/simulaciones/simular", data={"token_local": tok, "juego": "miloto", "iteraciones": 100},
                  follow_redirects=False).status_code == 303
    r = c.post("/simulaciones/simular", data={"token_local": tok, "juego": "miloto", "iteraciones": 1000})
    assert r.status_code == 409 and "Ya hay una simulación en curso" in r.text


def test_no_se_pudo_lanzar_el_hilo(e):
    def falla(funcion, inicio):
        raise RuntimeError("sin hilos")
    c = f7.cliente(e, lanzador=falla)
    r = c.post("/simulaciones/simular", data={"token_local": f7.token(c), "juego": "miloto", "iteraciones": 100})
    assert r.status_code == 500
    assert e.servicio().recientes()[0]["estado"] == "interrumpida"
    e.servicio().iniciar("MILOTO", 100, 1).cerrojos.liberar()  # nada queda falsamente activo


def test_resultado_inexistente_o_alterado(e):
    ident = _publicar(e)
    c = f7.cliente(e)
    assert c.get("/simulaciones/resultados/no-uuid").status_code == 404
    assert c.get("/simulaciones/ejecuciones/no-valido").status_code == 404
    with e.engine.begin() as conn:
        conn.execute(text("UPDATE simulaciones SET num_iteraciones = 999"))
    assert c.get(f"/simulaciones/resultados/{ident}").status_code == 409
    assert c.get(f"/simulaciones/resultados/{ident}/exportar.csv").status_code == 409


def test_base_caida_responde_503_y_codigo_3(e):
    from contextlib import contextmanager

    from sqlalchemy.exc import OperationalError

    @contextmanager
    def caida():
        raise OperationalError("SELECT 1", {}, Exception("could not connect to server"))
        yield

    s = e.servicio(abrir_lectura=caida)
    c = f7.cliente(e, s, conectada=False)
    assert c.get("/simulaciones").status_code == 200  # el panel informa la base no disponible
    assert c.get("/api/simulaciones").status_code == 503
    assert c.get("/api/simulaciones/00000000-0000-0000-0000-000000000000").status_code == 503
    assert c.get("/simulaciones/resultados/00000000-0000-0000-0000-000000000000").status_code == 503
    assert _cli(e, "listar", servicio=s)[0] == cli.EXIT_CONEXION


# ---------------------------------------------------------------------------
# API interna
# ---------------------------------------------------------------------------

def test_api_interna_de_solo_lectura(e):
    ident = _publicar(e)
    c = f7.cliente(e)
    antes = e.filas()
    assert c.get("/api/simulaciones/catalogo").json()["iteraciones"] == [100, 1000, 10000, 100000, 1000000]
    assert {j["juego"] for j in c.get("/api/simulaciones/panel").json()["juegos"]} == set(f7.JUEGOS)
    lista = c.get("/api/simulaciones?juego=MILOTO").json()["simulaciones"]
    assert [x["id"] for x in lista] == [ident] and lista[0]["integridad"] == "verificada"
    assert c.get("/api/simulaciones?juego=BALOTO").json()["simulaciones"] == []
    assert c.get("/api/simulaciones?juego=QUINELA").status_code == 404
    fila = c.get(f"/api/simulaciones/{ident}").json()
    assert fila["integridad"] == "verificada" and fila["parametros"]["juego"] == "MILOTO"
    assert c.get(f"/api/simulaciones/{ident}/csv").text.startswith("id,clave,juego")
    assert json.loads(c.get(f"/api/simulaciones/{ident}/json").text)["id"] == ident
    assert c.get(f"/api/simulaciones/{ident}/verificacion").json()["base"]["estado"] == "coincide"
    ejecuciones = c.get("/api/simulaciones/ejecuciones").json()["ejecuciones"]
    assert c.get(f"/api/simulaciones/ejecuciones/{ejecuciones[0]['id']}").json()["estado"] == "exito"
    assert c.get("/api/simulaciones/ejecuciones/20261023T000000Z-00000000").status_code == 404
    assert c.get("/api/simulaciones/00000000-0000-0000-0000-000000000000").json()["detail"]["codigo"] == "no_encontrado"
    assert c.post("/api/simulaciones", json={}).status_code == 405  # simular no se expone aqui
    assert e.filas() == antes


# ---------------------------------------------------------------------------
# Comando
# ---------------------------------------------------------------------------

def _cli(e, *argv, servicio=None):
    salida, errores = io.StringIO(), io.StringIO()
    s = servicio or e.servicio()
    codigo = cli.ejecutar(list(argv), simulaciones_factory=lambda: s, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def test_comando_simular_reutilizar_listar_ver_exportar_y_verificar(e):
    codigo, salida, errores = _cli(e, "simular", "--juego", "MILOTO", "--iteraciones", "1000")
    assert codigo == 0, errores
    final = json.loads(salida)
    r = final["juegos"]["MILOTO"]
    assert r["estado"] == "terminado" and "1000/1000 iteraciones" in errores
    codigo, salida, _ = _cli(e, "simular", "--juego", "miloto", "--iteraciones", "1000")
    assert codigo == 0 and json.loads(salida)["juegos"]["MILOTO"]["estado"] == "reutilizado"
    codigo, salida, _ = _cli(e, "listar", "--juego", "MILOTO")
    assert codigo == 0 and [x["id"] for x in json.loads(salida)["simulaciones"]] == [r["resultado"]]
    assert _cli(e, "ver", "--id", r["resultado"])[0] == 0
    codigo, salida, _ = _cli(e, "exportar", "--id", r["resultado"], "--formato", "csv")
    assert codigo == 0 and salida.startswith("id,clave,juego")
    codigo, salida, _ = _cli(e, "verificar", "--id", r["resultado"], "--reproducir")
    assert codigo == 0 and json.loads(salida)["reproduccion"]["estado"] == "reproducida"
    assert _cli(e, "consultar", "--id", final["id"])[0] == 0
    assert _cli(e, "ejecuciones", "--limite", "5")[0] == 0
    codigo, salida, _ = _cli(e, "catalogo")
    assert codigo == 0 and json.loads(salida)["semilla_predeterminada"] == 20261023
    assert _cli(e, "diagnostico", "--juego", "MILOTO")[0] == 0
    assert _cli(e, "diagnostico", "--juego", "COLORLOTO")[0] == cli.EXIT_MUESTRA  # sin datos


def test_comando_codigos_de_salida(e):
    assert _cli(e, "simular", "--juego", "MILOTO", "--iteraciones", "5000")[0] == cli.EXIT_USO
    assert _cli(e, "simular", "--juego", "QUINELA")[0] == cli.EXIT_USO
    assert _cli(e, "ver", "--id", "no-uuid")[0] == cli.EXIT_USO
    assert _cli(e, "consultar", "--id", "x")[0] == cli.EXIT_USO
    assert _cli(e, "listar", "--limite", "0")[0] == cli.EXIT_USO
    assert _cli(e, "simular", "--juego", "COLORLOTO", "--iteraciones", "100")[0] == cli.EXIT_MUESTRA
    s = e.servicio()
    activa = s.iniciar("MILOTO", 100, 1)
    codigo, salida, errores = _cli(e, "simular", "--juego", "MILOTO", "--iteraciones", "100", servicio=s)
    assert codigo == cli.EXIT_ACTIVA and "en_curso_en_otra_ejecucion" in salida
    s.ejecutar(activa)
    with e.engine.begin() as conn:
        conn.execute(text("UPDATE simulaciones SET num_iteraciones = 1"))
    ident = str(e.filas()[0]["id"])
    assert _cli(e, "ver", "--id", ident)[0] == cli.EXIT_ALTERADO
    codigo, salida, _ = _cli(e, "rutas")
    assert codigo == 0 and "DATABASE_URL" not in salida and "postgresql" not in salida.lower()
    assert _cli(e)[0] == cli.EXIT_USO


def test_navegacion_y_rutas_propias():
    base = (APP / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'href="/simulaciones"' in base and "nav-link disabled\"><i class=\"bi bi-graph-up" not in base
    from app.api.rest.routers import simulaciones as rest
    from app.api.web.routers import simulaciones as web
    rutas = [r.path for r in web.router.routes] + [r.path for r in rest.router.routes]
    assert len(rutas) == len(set(rutas)) and all(r.startswith(("/simulaciones", "/api/simulaciones")) for r in rutas)
    assert all(m == {"GET"} for r in rest.router.routes for m in [r.methods])
