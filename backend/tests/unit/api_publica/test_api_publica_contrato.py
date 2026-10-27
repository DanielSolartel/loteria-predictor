"""Fase 8: inventario de rutas (solo GET, sin web, estaticos ni REST interno),
intentos de escritura, OpenAPI con autenticacion y ejemplos, formato de
errores, monitoreo acotado y separacion respecto a la aplicacion local."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from app.api.publica import aplicacion
from app.api.publica import dependencias as d
from app.api.publica.configuracion import ConfiguracionPublica
from tests.unit.api_publica import fixtures_api_publica as fa

DOC = Path(__file__).resolve().parents[3] / "docs" / "fase8_api_publica.md"
CONSULTAS = ["/api/v1/juegos", "/api/v1/juegos/{codigo}", "/api/v1/juegos/{codigo}/sorteos",
             "/api/v1/juegos/{codigo}/sorteos/{numero_sorteo}", "/api/v1/juegos/{codigo}/estadisticas",
             "/api/v1/juegos/{codigo}/estadisticas/resumen", "/api/v1/juegos/{codigo}/estadisticas/panel",
             "/api/v1/juegos/{codigo}/estadisticas/{metrica}", "/api/v1/juegos/{codigo}/predicciones",
             "/api/v1/juegos/{codigo}/fiabilidad",  # Fase 9.3
             "/api/v1/juegos/{codigo}/simulaciones", "/api/v1/simulaciones/{identificador}", "/api/v1/estado"]


@pytest.fixture
def a(tmp_path):
    return fa.api(tmp_path)


def _planas(rutas):
    """Rutas efectivas: FastAPI reciente envuelve cada `include_router` en un
    objeto perezoso con `original_router`; las versiones anteriores las aplanan."""
    for r in rutas:
        interno = getattr(r, "original_router", None)
        if interno is not None:
            yield from _planas(interno.routes)
        else:
            yield r


def _rutas(app) -> dict[str, set[str]]:
    rutas: dict[str, set[str]] = {}
    for r in _planas(app.routes):
        rutas.setdefault(r.path, set()).update(getattr(r, "methods", None) or {"MOUNT"})
    return rutas


def test_inventario_solo_get_bajo_api_v1(a):
    rutas = _rutas(a.app)
    propias = {p: m for p, m in rutas.items() if p not in ("/api/v1/openapi.json", "/api/v1/docs")}
    assert set(propias) == {*CONSULTAS, "/api/v1/salud"}
    assert all(m == {"GET"} for m in propias.values()), propias
    assert all(p.startswith("/api/v1/") for p in rutas)
    assert not any(isinstance(m, set) and "MOUNT" in m for m in rutas.values())  # sin /static ni montajes


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_ninguna_escritura_ni_ruta_alternativa(a, metodo):
    c = a.cliente()
    antes = fa.filas(a.entorno)
    sorteo = str(uuid.uuid4())
    for url in ("/api/v1/juegos", "/api/v1/juegos/BALOTO/sorteos", f"/api/v1/simulaciones/{sorteo}",
                "/api/sorteos", f"/api/sorteos/{sorteo}", "/api/v1/sorteos", "/simulaciones/simular", "/sorteos/nuevo",
                "/operacion/ejecutar", "/api/simulaciones", "/importacion/sincronizar", "/api/v1/juegos/BALOTO/simular"):
        r = getattr(c, metodo)(url, headers=a.cabeceras())
        assert r.status_code in (404, 405), (metodo, url, r.status_code)
        assert r.json()["error"]["codigo"] in ("no_encontrado", "metodo_no_permitido")
    assert fa.filas(a.entorno) == antes


def test_rutas_internas_y_web_no_existen_en_la_entrada_publica(a):
    c = a.cliente()
    for url in ("/", "/sorteos", "/api/sorteos?codigo_juego=BALOTO", "/api/juegos", "/api/simulaciones",
                "/api/predicciones", "/api/estadisticas/BALOTO/panel", "/static/css/styles.css", "/docs",
                "/openapi.json", "/simulaciones", "/automatizacion"):
        assert c.get(url, headers=a.cabeceras()).status_code == 404, url


def test_la_aplicacion_local_conserva_sus_contratos():
    from app.main import app as local

    rutas = _rutas(local)
    assert "POST" in rutas["/api/sorteos"] and "DELETE" in rutas["/api/sorteos/{sorteo_id}"]
    assert "/api/juegos" in rutas and "/static" in rutas and "/simulaciones" in rutas
    assert not any(p.startswith("/api/v1") for p in rutas)


def test_openapi_con_autenticacion_ejemplos_y_errores(a):
    doc = a.cliente().get("/api/v1/openapi.json").json()
    esquema = doc["components"]["securitySchemes"]["ClaveDeAPI"]
    assert esquema == {**esquema, "type": "apiKey", "in": "header", "name": "X-API-Key"}
    assert set(doc["paths"]) == {*CONSULTAS, "/api/v1/salud"}
    for ruta, operaciones in doc["paths"].items():
        assert set(operaciones) == {"get"}, ruta
        op = operaciones["get"]
        if ruta == "/api/v1/salud":
            assert "security" not in op
            continue
        assert op["security"] == [{"ClaveDeAPI": []}], ruta
        for estado in ("401", "429", "503"):
            assert op["responses"][estado]["content"]["application/json"]["schema"]["$ref"].endswith("ErrorRespuesta")
    esquemas = doc["components"]["schemas"]
    for nombre in ("ErrorRespuesta", "Juego", "Sorteo", "Predicciones", "Salud"):
        assert esquemas[nombre].get("examples"), nombre
    assert "experimental_no_acreditado" in doc["info"]["description"]
    assert "AUTORIZA_EVALUACION = False" in doc["info"]["description"]
    assert a.cliente().get("/api/v1/docs").status_code == 200


def test_documentacion_desactivable(tmp_path):
    a = fa.api(tmp_path, documentacion=False)
    c = a.cliente()
    assert c.get("/api/v1/docs").status_code == 404 and c.get("/api/v1/openapi.json").status_code == 404
    assert c.get("/api/v1/salud").status_code == 200


def test_la_matriz_documentada_coincide_con_las_rutas(a):
    texto = DOC.read_text(encoding="utf-8")
    for ruta in (*CONSULTAS, "/api/v1/salud"):
        assert f"`{ruta.removeprefix('/api/v1')}`" in texto, ruta
    for frase in ("por proceso", "Retry-After", "X-API-Key", "Revocar", "Sustituir", "CORS"):
        assert frase in texto, frase


def test_errores_coherentes_sin_eco_de_la_entrada(a):
    c = a.cliente()
    for url, estado, codigo in (("/no-existe", 404, "no_encontrado"), ("/api/v1/juegos/QUINELA", 404, "no_encontrado"),
                                ("/api/v1/juegos/BALOTO/sorteos?pagina=%3Cscript%3E", 422, "parametro_no_valido")):
        r = c.get(url, headers=a.cabeceras())
        cuerpo = r.json()
        assert r.status_code == estado and set(cuerpo) == {"error"} and cuerpo["error"]["codigo"] == codigo
        assert cuerpo["error"]["solicitud"] == r.headers["X-Request-ID"] and re.fullmatch("[0-9a-f]{32}", r.headers["X-Request-ID"])
        assert r.headers["Cache-Control"] == "no-store" and "<script>" not in r.text and "input" not in r.text
    r = c.delete("/api/v1/juegos", headers=a.cabeceras())
    assert r.status_code == 405 and r.headers["allow"] == "GET"


def test_error_inesperado_sin_traza_ni_mensaje_interno(a):
    def falla():
        raise RuntimeError("/home/operador/secreto/.env DATABASE_URL=postgresql://u:p@host/db")
    a.app.dependency_overrides[d.simulaciones] = falla
    r = a.cliente(raise_server_exceptions=False).get("/api/v1/juegos/MILOTO/simulaciones", headers=a.cabeceras())
    assert r.status_code == 500 and r.json()["error"]["codigo"] == "error_interno"
    assert "secreto" not in r.text and "postgresql" not in r.text and "Traceback" not in r.text


def test_monitoreo_por_plantilla_y_acotado(tmp_path):
    a = fa.api(tmp_path, fichas_por_minuto=10_000)
    c = a.cliente()
    for i in range(300):
        c.get(f"/inventada/{i}")
        c.get(f"/api/v1/juegos/BALOTO/sorteos/{1000 + i}", headers=a.cabeceras())
    estado = c.get("/api/v1/estado", headers=a.cabeceras()).json()
    rutas = {(r["metodo"], r["ruta"]): r for r in estado["rutas"]}
    assert rutas[("GET", "sin_ruta")]["solicitudes"] == 300 and rutas[("GET", "sin_ruta")]["errores_4xx"] == 300
    plantilla = rutas[("GET", "/api/v1/juegos/{codigo}/sorteos/{numero_sorteo}")]
    assert plantilla["solicitudes"] == 300 and plantilla["latencia_maxima_ms"] >= plantilla["latencia_media_ms"] > 0
    assert len(estado["rutas"]) <= 3 and estado["solicitudes"] == 600 and estado["por_clase"]["4xx"] >= 300
    assert estado["claves_configuradas"] == 1 and estado["base"] == "disponible" and estado["api"] == "v1"
    assert "pruebas" not in str(estado)  # ni identificadores de clave ni IP en el monitoreo


def test_salud_sin_clave_y_sin_datos_internos(a):
    r = a.cliente().get("/api/v1/salud")
    assert r.status_code == 200 and r.json() == {"estado": "ok", "api": "v1"}
    cerrada = aplicacion.crear_app(ConfiguracionPublica(claves=()))
    assert fa.TestClient(cerrada).get("/api/v1/salud").json() == {"estado": "ok", "api": "v1"}
