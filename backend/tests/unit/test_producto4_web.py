"""Producto 4: pantallas y API del laboratorio (GET de solo lectura, POST
locales protegidos, progreso, ocupado, estados visibles y coherencia entre
HTML, API y comando)."""
from __future__ import annotations

import io
import json
import re

import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from scripts import laboratorio_modelos as cli
from tests.unit import fixtures_producto4 as f4


@pytest.fixture
def entorno(tmp_path):
    e = f4.entorno(tmp_path, {"BALOTO": 120, "BALOTO_REVANCHA": 120})
    yield e
    f4.limpiar()


def _archivos(e):
    return sorted(str(p.relative_to(e.directorio)) for p in e.directorio.rglob("*") if p.is_file()) \
        if e.directorio.exists() else []


def _comparar(c, tok, juego="miloto", bloques="1"):
    return c.post("/laboratorio/comparar", data={"juego": juego, "bloques": bloques, "token_local": tok},
                  follow_redirects=False)


def test_get_no_entrena_ni_escribe(entorno, monkeypatch):
    c = f4.cliente(entorno)
    tok = f4.token(c)
    r = _comparar(c, tok)
    clave = re.search(r"/laboratorio/experimentos/([0-9a-f]{64})", c.get(r.headers["location"]).text).group(1)
    g = c.post(f"/laboratorio/experimentos/{clave}/generar", data={"modelo": "hgb_clasificador", "token_local": tok},
               follow_redirects=False)
    pronostico = g.headers["location"].split("/")[-1]
    antes = _archivos(entorno)
    monkeypatch.setattr(le, "evaluar", lambda *a, **k: pytest.fail("un GET no debe entrenar"))
    monkeypatch.setattr(lm, "ajustar_candidato", lambda *a, **k: pytest.fail("un GET no debe ajustar"))
    for url in ["/laboratorio", "/laboratorio/miloto", "/laboratorio/baloto", "/laboratorio/colorloto",
                f"/laboratorio/experimentos/{clave}", r.headers["location"], r.headers["location"] + "/estado",
                f"/laboratorio/pronosticos/{pronostico}", "/laboratorio/miloto/seguimiento",
                "/api/laboratorio/catalogo", "/api/laboratorio/MILOTO", f"/api/laboratorio/experimentos/{clave}",
                f"/api/laboratorio/pronosticos/{pronostico}", "/api/laboratorio/MILOTO/seguimiento",
                "/api/laboratorio/ejecuciones", "/api/laboratorio/MILOTO/experimentos"]:
        assert c.get(url).status_code == 200, url
    assert _archivos(entorno) == antes


def test_post_protegido_y_sin_efecto_si_se_rechaza(entorno):
    c = f4.cliente(entorno)
    assert _comparar(c, "token-falso").status_code == 403
    ajeno = c.post("/laboratorio/comparar", data={"juego": "miloto", "token_local": f4.token(c)},
                   headers={"Origin": "http://evil.example"})
    assert ajeno.status_code == 403
    remoto = f4.cliente(entorno, client=("192.168.1.20", 5000))
    assert _comparar(remoto, f4.token(c)).status_code == 403
    assert _archivos(entorno) == []
    assert _comparar(c, f4.token(c), juego="otro").status_code == 422
    assert c.post("/laboratorio/comparar", data={"juego": "miloto", "bloques": "9", "token_local": f4.token(c)}
                  ).status_code == 422


def test_progreso_ocupado_y_resultado(entorno):
    pendientes = []
    c = f4.cliente(entorno, lanzador=lambda funcion, inicio: pendientes.append((funcion, inicio)))
    tok = f4.token(c)
    r = _comparar(c, tok)
    assert r.status_code == 303
    progreso = c.get(r.headers["location"])
    assert "En curso" in progreso.text and 'hx-trigger="every 2s"' in progreso.text
    ocupado = _comparar(c, tok)
    assert ocupado.status_code == 409 and "Ya hay una comparación en curso para MiLoto" in ocupado.text
    assert "MiLoto" in c.get("/laboratorio").text and "Comparación en curso" in c.get("/laboratorio").text
    funcion, inicio = pendientes.pop()
    funcion(inicio)  # el trabajo en segundo plano termina
    final = c.get(r.headers["location"]).text
    assert "Terminada." in final and "abrir el informe" in final and "every 2s" not in final


def test_fallo_al_lanzar_libera_y_responde_500(entorno):
    def roto(funcion, inicio):
        raise RuntimeError("can't start new thread")
    c = f4.cliente(entorno, lanzador=roto)
    tok = f4.token(c)
    assert _comparar(c, tok).status_code == 500
    lab = entorno.laboratorio()
    assert lab.recientes()[0]["estado"] == "interrumpida"
    ok = f4.cliente(entorno)
    assert _comparar(ok, tok).status_code == 303


def test_informe_generacion_y_resultado_existente(entorno):
    c = f4.cliente(entorno)
    tok = f4.token(c)
    r = _comparar(c, tok, juego="baloto", bloques="2")
    clave = re.search(r"/laboratorio/experimentos/([0-9a-f]{64})", c.get(r.headers["location"]).text).group(1)
    informe = c.get(f"/laboratorio/experimentos/{clave}").text
    assert any(x in informe for x in ("Menor pérdida en esta evaluación", "La uniforme fue mejor", "Empate"))
    assert "Comparación incompleta para estos candidatos" in informe  # AE-36 sin muestra en un bloque
    assert "Generar pronóstico con este modelo" in informe and "Superbalota (aparte)" in informe
    assert "Diagnóstico de calibración" in informe and "<svg" in informe
    g = c.post(f"/laboratorio/experimentos/{clave}/generar", data={"modelo": "logistica_regularizada",
                                                                    "token_local": tok}, follow_redirects=False)
    pagina = c.get(g.headers["location"]).text
    assert "Sugerencia" in pagina and "Ranking completo" in pagina and "no es la probabilidad del premio mayor" in pagina
    otra = c.post(f"/laboratorio/experimentos/{clave}/generar", data={"modelo": "logistica_regularizada",
                                                                       "token_local": tok}, follow_redirects=True)
    assert "Resultado ya existente" in otra.text
    uniforme = c.post(f"/laboratorio/experimentos/{clave}/generar", data={"modelo": "uniforme", "token_local": tok})
    assert uniforme.status_code == 422 and "referencia sin pronostico propio" in uniforme.text


def test_estados_visibles_muestra_insuficiente_base_y_corte_superado(tmp_path):
    e = f4.entorno(tmp_path, {"MILOTO": 55})
    c = f4.cliente(e)
    assert "Muestra insuficiente" in c.get("/laboratorio").text
    assert "Muestra insuficiente" in c.get("/laboratorio/miloto").text
    e2 = f4.entorno(tmp_path / "b")
    c2 = f4.cliente(e2)
    tok = f4.token(c2)
    r = _comparar(c2, tok)
    clave = re.search(r"/laboratorio/experimentos/([0-9a-f]{64})", c2.get(r.headers["location"]).text).group(1)
    e2.anadir("MILOTO", e2.siguiente("MILOTO", 2))
    texto = c2.get(f"/laboratorio/experimentos/{clave}").text
    assert "La base avanzó desde este corte (2 sorteo(s) nuevo(s)" in texto and "Iniciar comparación nueva" in texto
    e2.base_caida = True
    caida = f4.cliente(e2, conectada=False)
    assert "Base no disponible" in caida.get("/laboratorio").text
    assert "Base de datos no disponible" in caida.get(f"/laboratorio/experimentos/{clave}").text
    f4.limpiar()


def test_api_cli_y_html_muestran_las_mismas_cifras(entorno):
    c = f4.cliente(entorno)
    tok = f4.token(c)
    r = _comparar(c, tok)
    clave = re.search(r"/laboratorio/experimentos/([0-9a-f]{64})", c.get(r.headers["location"]).text).group(1)
    api = c.get(f"/api/laboratorio/experimentos/{clave}").json()["informe"]
    salida = io.StringIO()
    assert cli.ejecutar(["consultar", "--id", clave], laboratorio_factory=entorno.laboratorio, salida=salida,
                        errores=io.StringIO()) == 0
    assert json.loads(salida.getvalue())["informe"] == api
    html = c.get(f"/laboratorio/experimentos/{clave}").text
    for fila in api["resumen"]["ranking"]:
        c_ = next(x for x in api["candidatos"] if x["id"] == fila["id"])
        assert "%.5f" % c_["agregado"]["log_loss"] in html and "%+.5f" % c_["agregado"]["diferencia_log_loss"] in html
    assert c.get("/api/laboratorio/experimentos/" + "0" * 64).status_code == 404
    assert c.get("/api/laboratorio/XX").status_code == 404
