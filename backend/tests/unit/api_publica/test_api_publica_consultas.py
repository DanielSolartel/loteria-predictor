"""Fase 8: contratos de las consultas con datos sinteticos. Cada respuesta sale
del caso de uso existente (se compara con su llamada directa) y respeta los
limites de los listados."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.publica import dependencias as d
from app.api.publica import esquemas as e
from app.application.fase7 import artefacto as fa7
from tests.unit import fixtures_fase4 as f4
from tests.unit.api_publica import fixtures_api_publica as fa

JUEGOS = ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"]


@pytest.fixture
def a(tmp_path):
    return fa.api(tmp_path)


def test_juegos_y_detalle_sin_identificadores_internos(a):
    r = a.get("/api/v1/juegos").json()
    assert [j["codigo"] for j in r["juegos"]] == JUEGOS
    assert all(set(j) == set(e.Juego.model_fields) for j in r["juegos"])
    detalle = a.get("/api/v1/juegos/COLORLOTO").json()
    assert detalle["tiene_color"] and detalle["permite_repeticion"] and detalle["espacio_muestral"] > 0
    assert "id" not in detalle and "juego_id" not in json.dumps(r)
    for malo in ("QUINELA", "baloto"):
        respuesta = a.get(f"/api/v1/juegos/{malo}")
        assert respuesta.status_code == 404 and respuesta.json()["error"]["codigo"] == "no_encontrado"


def test_sorteos_paginados_ordenados_y_filtrados(a):
    total = len(a.entorno.historicos["BALOTO"])
    p1 = a.get("/api/v1/juegos/BALOTO/sorteos?por_pagina=7").json()
    assert (p1["total"], p1["pagina"], p1["por_pagina"], p1["paginas"]) == (total, 1, 7, -(-total // 7))
    numeros = [s["numero_sorteo"] for s in p1["sorteos"]]
    assert len(numeros) == 7 and numeros == sorted(numeros, reverse=True)
    p2 = a.get("/api/v1/juegos/BALOTO/sorteos?por_pagina=7&pagina=2").json()
    assert not set(numeros) & {s["numero_sorteo"] for s in p2["sorteos"]}
    asc = a.get("/api/v1/juegos/BALOTO/sorteos?orden=numero_asc&por_pagina=100").json()["sorteos"]
    assert [s["numero_sorteo"] for s in asc] == sorted(r.numero_sorteo for r in a.entorno.historicos["BALOTO"])
    assert set(asc[0]) == set(e.Sorteo.model_fields) and asc[0]["superbalota"] is not None
    n0 = asc[0]["numero_sorteo"]
    filtrados = a.get(f"/api/v1/juegos/BALOTO/sorteos?numero_desde={n0}&numero_hasta={n0 + 2}").json()
    assert filtrados["total"] == 3
    fecha = asc[3]["fecha"]
    assert a.get(f"/api/v1/juegos/BALOTO/sorteos?hasta={fecha}").json()["total"] == 4
    vacia = a.get(f"/api/v1/juegos/BALOTO/sorteos?pagina=999").json()
    assert vacia["sorteos"] == [] and vacia["total"] == total


@pytest.mark.parametrize("consulta", ["por_pagina=101", "por_pagina=0", "pagina=0", "pagina=10001", "pagina=abc",
                                      "orden=azar", "desde=2021-13-01", "numero_desde=0",
                                      "desde=2022-01-02&hasta=2022-01-01", "numero_desde=10&numero_hasta=9"])
def test_parametros_de_sorteos_no_validos(a, consulta):
    r = a.get(f"/api/v1/juegos/BALOTO/sorteos?{consulta}")
    assert r.status_code == 422 and r.json()["error"]["codigo"] == "parametro_no_valido"


def test_un_sorteo_por_numero_y_pares_de_colorloto(a):
    ultimo = a.entorno.historicos["COLORLOTO"][-1]
    s = a.get(f"/api/v1/juegos/COLORLOTO/sorteos/{ultimo.numero_sorteo}").json()
    assert s["numero_sorteo"] == ultimo.numero_sorteo and s["fecha"] == ultimo.fecha.isoformat()
    assert len(s["pares"]) == 6 and all(set(p) == {"numero", "color_codigo", "color_nombre"} for p in s["pares"])
    assert a.get("/api/v1/juegos/COLORLOTO/sorteos/999999").status_code == 404
    assert a.get("/api/v1/juegos/COLORLOTO/sorteos/0").status_code == 422


def _directo(a, nombre):
    sesion = fa.sesiones_de(a.entorno)()
    db = next(sesion)
    try:
        return {"resumen": d.consultar_resumen, "panel": d.consultar_estadisticas}[nombre](db)
    finally:
        sesion.close()


def test_estadisticas_reutilizan_los_casos_de_uso(a):
    indice = a.get("/api/v1/juegos/COLORLOTO/estadisticas").json()
    metricas = {m["metrica"]: m["parametro"] for m in indice["metricas"]}
    assert "frecuencia-numeros-por-anio" in metricas and "correlaciones" in metricas
    hoy = date.today()
    resumen = a.get("/api/v1/juegos/BALOTO/estadisticas/resumen?hasta_numero_sorteo=2120").json()
    assert resumen == json.loads(json.dumps(_directo(a, "resumen").ejecutar("BALOTO", hoy=hoy, hasta_numero_sorteo=2120),
                                            default=str))
    panel = a.get("/api/v1/juegos/MILOTO/estadisticas/panel").json()
    assert panel == json.loads(json.dumps(_directo(a, "panel").panel("MILOTO", hoy=hoy), default=str))
    metrica = a.get("/api/v1/juegos/BALOTO/estadisticas/frecuencia-numeros-por-anio?anio=2021").json()
    esperado = _directo(a, "panel").metrica("BALOTO", "frecuencia-numeros-por-anio", hoy=hoy,
                                            hasta_numero_sorteo=None, parametros={"anio": 2021})
    assert metrica == json.loads(json.dumps(esperado, default=str))


@pytest.mark.parametrize("url,estado", [
    ("/api/v1/juegos/BALOTO/estadisticas/inventada", 404),
    ("/api/v1/juegos/MILOTO/estadisticas/frecuencia-superbalota-por-anio", 404),
    ("/api/v1/juegos/BALOTO/estadisticas/frecuencia-numeros-por-anio?mes=2", 422),
    ("/api/v1/juegos/BALOTO/estadisticas/frecuencia-numeros-por-mes?mes=13", 422),
    ("/api/v1/juegos/BALOTO/estadisticas/panel?hasta_numero_sorteo=0", 422),
    ("/api/v1/juegos/QUINELA/estadisticas/panel", 404)])
def test_estadisticas_errores(a, url, estado):
    assert a.get(url).status_code == estado


def test_simulaciones_guardadas_listado_detalle_e_integridad(a):
    servicio = a.entorno.servicio()
    ident = servicio.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]["resultado"]
    servicio.ahora("MILOTO", 100, 2)
    listado = a.get("/api/v1/juegos/MILOTO/simulaciones?limite=1").json()
    assert listado["limite"] == 1 and len(listado["simulaciones"]) == 1
    assert len(a.get("/api/v1/juegos/MILOTO/simulaciones").json()["simulaciones"]) == 2
    assert a.get("/api/v1/juegos/BALOTO/simulaciones").json()["simulaciones"] == []
    detalle = a.get(f"/api/v1/simulaciones/{ident}").json()
    assert detalle["integridad"] == "verificada" and detalle["contenido_sha256"] == fa7.sha256(detalle["contenido"])
    assert detalle["parametros"]["clave"] == fa7.sha256({k: v for k, v in detalle["parametros"].items() if k != "clave"})
    assert "ejecucion" not in detalle and "entorno" not in json.dumps(detalle) and "resultado_resumen" not in detalle
    with a.entorno.engine.begin() as c:  # fila alterada
        c.execute(text("UPDATE simulaciones SET num_iteraciones = 999 WHERE id = :i"), {"i": ident.replace("-", "")})
    alterada = a.get(f"/api/v1/simulaciones/{ident}")
    assert alterada.status_code == 409 and alterada.json()["error"]["codigo"] == "alterado"
    marcas = {s["id"]: s["integridad"] for s in a.get("/api/v1/juegos/MILOTO/simulaciones").json()["simulaciones"]}
    assert marcas[ident] == "alterada"


@pytest.mark.parametrize("ident,estado", [("00000000-0000-0000-0000-000000000000", 404), ("no-es-uuid", 422),
                                          ("../../etc", 404)])
def test_simulacion_inexistente_o_no_valida(a, ident, estado):
    assert a.get(f"/api/v1/simulaciones/{ident}").status_code == estado


def test_codigo_no_previsto_de_un_caso_de_uso_es_error_interno_sin_mensaje(a):
    from app.application.use_cases.simulaciones import SimulacionesError

    class Servicio:
        def listar(self, *_):
            raise SimulacionesError("fallo_del_trabajador", "detalle interno /ruta/privada")
    a.app.dependency_overrides[d.simulaciones] = Servicio
    r = a.get("/api/v1/juegos/MILOTO/simulaciones")
    assert r.status_code == 500 and r.json()["error"]["codigo"] == "error_interno" and "privada" not in r.text


@pytest.mark.parametrize("limite", [0, 51])
def test_limite_de_simulaciones(a, limite):
    assert a.get(f"/api/v1/juegos/MILOTO/simulaciones?limite={limite}").status_code == 422


def test_predicciones_guardadas(tmp_path):
    entorno = f4.entorno(tmp_path / "f4")
    a = fa.api(tmp_path, centro=entorno.centro())
    sin = a.get("/api/v1/juegos/MILOTO/predicciones").json()
    assert sin["prediccion"] is None and sin["historial"] == [] and sin["configuracion"] != "vigente"
    assert sin["estado_de_uso"] == "experimental_no_acreditado" and sin["contexto"]["AUTORIZA_EVALUACION"] is False
    entorno.configurar("MILOTO", "uniforme")
    centro = entorno.centro()
    centro.ahora("MILOTO")
    centro.ahora("MILOTO")  # reutiliza la misma cartera
    r = a.get("/api/v1/juegos/MILOTO/predicciones").json()
    directo = centro.consultar("MILOTO")["prediccion"]
    p = r["prediccion"]
    assert r["configuracion"] == "vigente" and p["clave"] == directo["clave"] and p["integridad"] == "correcta"
    assert p["combinaciones"] == json.loads(json.dumps(directo["combinaciones"])) and p["explicacion_disponible"]
    assert p["corte"] == directo["datos"]["corte"] and p["modelo"]["id"] == "uniforme"
    assert set(p) == set(e.Prediccion.model_fields) and "enlaces" not in json.dumps(r)
    assert r["historial_total"] == len(r["historial"]) >= 1
    explicita = a.get(f"/api/v1/juegos/MILOTO/predicciones?cartera={p['clave']}&historial=0").json()
    assert explicita["prediccion"]["clave"] == p["clave"] and explicita["historial"] == []
    otra = a.get(f"/api/v1/juegos/BALOTO/predicciones?cartera={p['clave']}")  # cartera de otro juego
    assert otra.status_code == 422 and otra.json()["error"]["codigo"] == "no_valido"
    assert a.get(f"/api/v1/juegos/MILOTO/predicciones?cartera={'0' * 64}").status_code == 404
    for malo in ("cartera=xyz", "cartera=../../x", "historial=51", "historial=-1"):
        assert a.get(f"/api/v1/juegos/MILOTO/predicciones?{malo}").status_code == 422


def test_base_no_disponible_sin_detalles_internos(tmp_path):
    a = fa.api(tmp_path, base="no_disponible")

    def caida():
        raise OperationalError("SELECT 1", {}, Exception("could not connect to server at 10.1.2.3 password=secreto"))
        yield

    @contextmanager
    def lectura_caida():
        raise OperationalError("SELECT 1", {}, Exception("could not connect to server at 10.1.2.3"))
        yield
    a.app.dependency_overrides[d.sesion_de_lectura] = caida
    a.app.dependency_overrides[d.simulaciones] = lambda: a.entorno.servicio(abrir_lectura=lectura_caida)
    for url in ("/api/v1/juegos", "/api/v1/juegos/BALOTO/sorteos", "/api/v1/juegos/BALOTO/estadisticas/panel",
                "/api/v1/juegos/MILOTO/simulaciones"):
        r = a.get(url)
        assert r.status_code == 503 and r.json()["error"]["codigo"] == "base_no_disponible", url
        assert "10.1.2.3" not in r.text and "secreto" not in r.text and "connect" not in r.text
    estado = a.get("/api/v1/estado")
    assert estado.status_code == 200 and estado.json()["base"] == "no_disponible"
