"""Fase 4 - centro de predicciones en la web, la API y el comando: paginas de
los cuatro juegos, estados visibles, acciones protegidas, GET sin escritura,
misma respuesta que el caso de uso y reglas de impresion acotadas a sus
clases. Datos sinteticos; nada es real."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from app.application.ml import laboratorio_artefactos as la
from app.infrastructure.storage.operacion_file_store import RegistroEjecucionesArchivo
from scripts import predicciones as cli
from tests.unit import fixtures_fase4 as f4

APP = Path(__file__).resolve().parents[2] / "app"


@pytest.fixture
def entorno(tmp_path):
    e = f4.entorno(tmp_path)
    yield e
    f4.limpiar()


def _preparado(e, registrar=False):
    lab = e.laboratorio()
    if registrar:
        r = e.registrar(lab, "BALOTO", "random_forest_clasificador")
        e.configurar("BALOTO", "random_forest_clasificador", registrado=r["modelo_registrado"])
    else:
        e.configurar("BALOTO", "logistica_regularizada")
    e.configurar("MILOTO", "logistica_regularizada")
    e.configurar("COLORLOTO", "uniforme_paleta", cantidad=4)
    carteras = e.carteras()
    centro = e.centro(carteras)
    return lab, carteras, centro, f4.cliente(e, carteras=carteras, laboratorio=lab, centro=centro)


def _cli(centro, *argv):
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(list(argv), centro_factory=lambda: centro, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------

def test_flujo_web_generar_y_consultar_los_juegos(entorno):
    _, _, centro, c = _preparado(entorno, registrar=True)
    token = f4.token(c)
    for slug in ("baloto", "miloto", "colorloto"):
        r = c.post(f"/predicciones/{slug}/generar", data={"token_local": token, "cantidad": "configuracion"},
                   follow_redirects=False)
        assert r.status_code == 303
        progreso = c.get(r.headers["location"]).text
        assert "explicación guardada" in progreso or "guardada" in progreso
    baloto = c.get("/predicciones/baloto").text
    for texto in ("Experimental, no acreditado", "AUTORIZA_EVALUACION = False", "Elección del operador",
                  "versión registrada 1", "Corte de entrenamiento", "Corte de entrada", "Combinaciones (3)",
                  "sugerencia del modelo", "línea muestreada", "Números más probables (10 de 43)",
                  "uniforme = 5/43", "Superbalota (sección separada; 16 superbalotas; uniforme = 1/16)",
                  "Importancias o coeficientes globales", "RandomForestClassifier", "Por qué está cada candidato",
                  "Fiabilidad disponible en el corte", "Proyección a la tabla", "nivel_confianza",
                  "Cartera original (Producto 5)", "Ficha de la versión registrada (Fase 3)",
                  "reproducción de rankings y variables: exacta"):
        assert texto in baloto, texto
    colorloto = c.get("/predicciones/colorloto").text
    for texto in ("Pares más probables (10 de 42 pares número-color)", "Números por separado (7 números)",
                  "Colores por separado (6 colores de la paleta del corte)", "En 6 balotas",
                  "no es la probabilidad de que el par aparezca al menos una vez", "Hay candidatos con la misma",
                  "no aplica: la referencia uniforme"):
        assert texto in colorloto, texto
    assert re.search(r'class="color-swatch color-amarillo"[^>]*></span>1 <span class="small">amarillo', colorloto)
    assert "10 de 7" not in colorloto
    fiabilidad = c.get("/predicciones/baloto/fiabilidad").text
    for texto in ("Qué se mide y qué no", "Probabilidad emitida", "Rendimiento observado", "Incertidumbre",
                  "fase4-fiabilidad-1", "Künsch", "Evaluación de la receta (informe del laboratorio)",
                  "Seguimiento", "Retrospectiva", "Consultar (no escribe)"):
        assert texto in fiabilidad, texto
    indice = c.get("/predicciones").text
    assert indice.count('href="/predicciones/') >= 8 and "Generar cinco combinaciones" in indice


def test_estados_vacio_sin_configuracion_base_caida_e_incompatible(entorno, monkeypatch):
    lab, _, centro, c = _preparado(entorno, registrar=True)
    revancha = c.get("/predicciones/baloto-revancha").text
    assert "no tiene una configuración guardada" in revancha and 'href="/carteras/baloto-revancha"' in revancha
    vacio = c.get("/predicciones/miloto").text
    assert "Todavía no hay predicciones" in vacio or "todavía no hay" in vacio.lower()
    centro.ahora("MILOTO")
    entorno.base_caida = True
    caida = c.get("/predicciones/miloto")
    assert caida.status_code == 200 and "base no disponible" in caida.text.lower()
    assert "Combinaciones (3)" in caida.text  # lo guardado se sigue mostrando
    entorno.base_caida = False
    real = la.entorno()
    monkeypatch.setattr(la, "entorno", lambda: {**real, "scikit-learn": "0.1"})
    assert "incompatible" in c.get("/predicciones/baloto").text
    r = c.post("/predicciones/baloto/generar", data={"token_local": f4.token(c), "cantidad": "configuracion"})
    assert r.status_code == 409 and "no se puede cargar en este entorno" in r.text
    assert c.get("/predicciones/noexiste").status_code == 404
    assert c.get("/predicciones/miloto?cartera=" + "0" * 64).status_code == 404
    assert c.get("/predicciones/miloto/fiabilidad?linea=x:y").status_code == 422


def test_resultado_pendiente_y_resultado_observado(entorno):
    _, _, centro, c = _preparado(entorno)
    centro.ahora("MILOTO")
    assert "resultado pendiente" in c.get("/predicciones/miloto").text
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    texto = c.get("/predicciones/miloto").text
    assert "Aciertos observados" in texto


# ---------------------------------------------------------------------------
# Acciones protegidas y GET sin escritura
# ---------------------------------------------------------------------------

def test_acciones_exigen_token_y_maquina_local_y_no_escriben_si_se_rechazan(entorno):
    _, _, centro, c = _preparado(entorno)
    antes = f4.arbol(entorno.raiz)
    r = c.post("/predicciones/miloto/generar", data={"cantidad": "configuracion"})
    assert r.status_code == 403 and "Acción rechazada" in r.text
    ajeno = f4.cliente(entorno, client=("203.0.113.9", 4000), centro=centro)
    r = ajeno.post("/predicciones/miloto/generar", data={"token_local": f4.token(c), "cantidad": "configuracion"})
    assert r.status_code == 403
    assert f4.arbol(entorno.raiz) == antes
    c = f4.cliente(entorno, centro=centro)
    token = f4.token(c)
    assert c.post("/predicciones/miloto/generar", data={"token_local": token, "cantidad": "siete"}).status_code == 422
    clave = centro.ahora("MILOTO")["prediccion"]["cartera"]["clave"]
    despues = f4.arbol(entorno.raiz)
    r = c.post("/predicciones/baloto/explicar", data={"token_local": token, "cartera": clave})
    assert r.status_code == 422 and f4.arbol(entorno.raiz) == despues  # otro juego: no escribe
    r = c.post("/predicciones/miloto/explicar", data={"token_local": token, "cartera": clave}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/predicciones/miloto?cartera={clave}#explicacion"


def test_ningun_get_escribe(entorno):
    _, _, centro, c = _preparado(entorno, registrar=True)
    p = centro.ahora("BALOTO")["prediccion"]
    centro.ahora("COLORLOTO")
    entorno.anadir("BALOTO", entorno.siguiente("BALOTO"))
    antes = f4.arbol(entorno.raiz)
    urls = ["/predicciones", f"/predicciones/ejecuciones/{p['id']}", f"/predicciones/ejecuciones/{p['id']}/estado",
            "/api/predicciones", "/api/predicciones/BALOTO/fiabilidad?hasta=2200"]
    for slug, codigo in (("baloto", "BALOTO"), ("baloto-revancha", "BALOTO_REVANCHA"), ("miloto", "MILOTO"),
                         ("colorloto", "COLORLOTO")):
        urls += [f"/predicciones/{slug}", f"/predicciones/{slug}/fiabilidad", f"/api/predicciones/{codigo}",
                 f"/api/predicciones/{codigo}/fiabilidad"]
    for url in urls:
        assert c.get(url).status_code == 200, url
    assert f4.arbol(entorno.raiz) == antes


def test_si_el_lanzador_falla_la_generacion_termina_interrumpida_y_se_puede_reintentar(entorno):
    """Regresion: si no se puede lanzar el trabajo (p. ej. no se crea el hilo), el registro del centro no queda
    «en curso»: termina interrumpido con su motivo y su fecha, la pagina de estado deja de consultar, sus GET no
    escriben, el cerrojo queda libre y un nuevo intento funciona."""
    _, carteras, centro, _ = _preparado(entorno)

    def falla(funcion, inicio):
        raise RuntimeError("can't start new thread")

    c = f4.cliente(entorno, lanzador=falla, centro=centro, carteras=carteras)
    datos = {"token_local": f4.token(c), "cantidad": "configuracion"}
    r = c.post("/predicciones/miloto/generar", data=datos, follow_redirects=False)
    assert r.status_code == 500 and "No se pudo iniciar el trabajo" in r.text
    (propio,) = RegistroEjecucionesArchivo(entorno.raiz / "predicciones" / "operacion").listar()
    e = centro.ejecucion(propio["id"])
    assert e["cartera"]["estado"] == "interrumpida" and e["cartera"]["finalizada_en"]
    p = e["prediccion"]
    assert (p["estado"], p["fase"]) == ("interrumpida", "interrumpida") and p["finalizada_en"]
    assert "No se pudo iniciar el trabajo" in p["mensaje"] and "can't start new thread" in p["mensaje"]
    antes = f4.arbol(entorno.raiz)
    for url in (f"/predicciones/ejecuciones/{p['id']}", f"/predicciones/ejecuciones/{p['id']}/estado"):
        texto = c.get(url).text
        assert "Interrumpido." in texto and "No se pudo iniciar el trabajo: can" in texto, url
        assert "start new thread" in texto and p["finalizada_en"][:19].replace("T", " ") in texto, url
        assert "hx-get" not in texto and "hx-trigger" not in texto, url  # deja de consultar
    assert f4.arbol(entorno.raiz) == antes
    c = f4.cliente(entorno, centro=centro, carteras=carteras)  # lanzador que funciona: nuevo intento
    r = c.post("/predicciones/miloto/generar", data={**datos, "token_local": f4.token(c)}, follow_redirects=False)
    assert r.status_code == 303
    nuevo = r.headers["location"].rsplit("/", 1)[1]
    assert nuevo != p["id"] and centro.ejecucion(nuevo)["prediccion"]["estado"] == "exito"
    assert centro.ejecucion(p["id"])["prediccion"] == p  # el intento fallido se conserva tal cual


# ---------------------------------------------------------------------------
# API y comando: el mismo caso de uso
# ---------------------------------------------------------------------------

def test_api_devuelve_lo_mismo_que_el_caso_de_uso(entorno):
    _, _, centro, c = _preparado(entorno)
    centro.ahora("MILOTO")
    redondo = lambda x: json.loads(json.dumps(x, default=str))  # noqa: E731
    assert c.get("/api/predicciones/MILOTO").json() == redondo(centro.consultar("MILOTO"))
    assert c.get("/api/predicciones/MILOTO/fiabilidad").json() == redondo(centro.fiabilidad("MILOTO"))
    assert [j["juego"] for j in c.get("/api/predicciones").json()["juegos"]] == ["BALOTO", "BALOTO_REVANCHA",
                                                                                  "MILOTO", "COLORLOTO"]
    assert c.get("/api/predicciones/XX").status_code == 404
    assert c.get("/api/predicciones/MILOTO?cartera=" + "f" * 64).status_code == 404
    assert c.get("/api/predicciones/MILOTO/fiabilidad?hasta=0").status_code == 422
    assert c.post("/api/predicciones/MILOTO").status_code == 405  # la API no escribe


def test_comando_codigos_de_salida_y_misma_respuesta(entorno):
    _, carteras, centro, _ = _preparado(entorno)
    codigo, salida, _ = _cli(centro, "generar", "--juego", "MILOTO")
    assert codigo == cli.EXIT_OK and json.loads(salida)["prediccion"]["estado"] == "exito"
    codigo, salida, _ = _cli(centro, "consultar", "--juego", "MILOTO")
    assert codigo == 0 and json.loads(salida) == json.loads(json.dumps(centro.consultar("MILOTO"), default=str))
    codigo, salida, _ = _cli(centro, "generar", "--juego", "MILOTO", "--cinco")
    assert codigo == 0 and json.loads(salida)["prediccion"]["solicitud"]["combinaciones"] == 5
    assert _cli(centro, "generar", "--juego", "BALOTO_REVANCHA")[0] == cli.EXIT_SIN_CONFIGURACION
    assert _cli(centro, "explicar", "--cartera", "f" * 64)[0] == cli.EXIT_USO
    assert _cli(centro, "fiabilidad", "--juego", "MILOTO", "--hasta", "0")[0] == cli.EXIT_USO
    assert _cli(centro, "ejecucion", "--id", "nada")[0] == cli.EXIT_USO
    assert _cli(centro)[0] == cli.EXIT_USO
    codigo, salida, _ = _cli(centro, "rutas")
    rutas = json.loads(salida)
    assert codigo == 0 and rutas["directorio_predicciones_modelos"].endswith("predicciones")
    assert "DATABASE_URL" not in salida and "postgresql" not in salida.lower()
    # Otra ejecucion activa para el juego: no se inicia nada y se informa.
    inicio = carteras.iniciar("cartera", ["MILOTO"], {"modelo": "uniforme", "cantidad": 2, "diversidad": "libre",
                                                       "semilla": 1, "perfil": "reducido"}, "prueba")
    try:
        codigo, salida, errores = _cli(centro, "generar", "--juego", "MILOTO")
        assert codigo == cli.EXIT_ACTIVA and json.loads(salida)["estado"] == "en_curso_en_otra_ejecucion"
    finally:
        carteras.abortar(inicio, "prueba")
    # Explicacion alterada en disco: no se sobrescribe y el comando lo dice (codigo 8).
    archivo = sorted((entorno.raiz / "predicciones" / "explicaciones" / "MILOTO").glob("*.json"))[0]
    archivo.write_bytes(archivo.read_bytes().replace(b'"MILOTO"', b'"MILOTX"', 1))
    historial = json.loads(_cli(centro, "consultar", "--juego", "MILOTO")[1])["historial"]
    clave_cartera = next(h["clave"] for h in historial if h["clave"].startswith(archivo.name[:16]))
    codigo, _, errores = _cli(centro, "explicar", "--cartera", clave_cartera)
    assert codigo == cli.EXIT_ALTERADO and "no se sobrescribe" in errores


# ---------------------------------------------------------------------------
# Navegacion, rutas e impresion
# ---------------------------------------------------------------------------

def test_navegacion_y_rutas_sin_colisiones():
    import importlib
    import pkgutil

    import app.api.rest.routers as rest
    import app.api.web.routers as web
    import app.main  # noqa: F401  (incluye todos los routers)

    por_modulo = {}
    for paquete in (web, rest):
        for m in pkgutil.iter_modules(paquete.__path__):
            modulo = importlib.import_module(f"{paquete.__name__}.{m.name}")
            if hasattr(modulo, "router"):
                por_modulo[modulo.__name__] = [r.path for r in modulo.router.routes]
    propias = por_modulo["app.api.web.routers.predicciones"] + por_modulo["app.api.rest.routers.predicciones"]
    assert len(propias) == len(set(propias)) == 10
    assert all(r.startswith(("/predicciones", "/api/predicciones")) for r in propias)
    ajenas = [r for nombre, rutas in por_modulo.items() if not nombre.endswith(".predicciones") for r in rutas
              if r.startswith(("/predicciones", "/api/predicciones"))]
    assert ajenas == []
    # Las rutas fijas van antes que `/predicciones/{slug}` (no quedan tapadas).
    web_propias = por_modulo["app.api.web.routers.predicciones"]
    assert web_propias.index("/predicciones/ejecuciones/{identificador}") < web_propias.index("/predicciones/{slug}")
    base = (APP / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'href="/predicciones"' in base and "Centro de predicciones" in base
    assert base.index("Centro de predicciones") < base.index("Próximamente")


def test_reglas_de_impresion_acotadas_a_las_paginas_del_centro():
    css = (APP / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    inicio = css.index("@media print")
    reglas = [l.strip() for l in css.splitlines() if "predicciones-" in l and l.strip().endswith(("{", ","))]
    en_pantalla = [l for l in reglas if css.index(l) < inicio]
    assert all(re.fullmatch(r"(svg)?\.predicciones-[a-z-]+ \{.*", l) or l.startswith(".predicciones-")
               for l in en_pantalla)
    impresas = [l for l in reglas if css.index(l) > inicio]
    assert impresas and all(l.startswith("body.producto1-impresion ") for l in impresas)
    for regla in ("body.producto1-impresion .stat-card.predicciones-fragmentable {",
                  "body.producto1-impresion .predicciones-tarjeta {", "body.producto1-impresion .predicciones-cabecera {",
                  "body.producto1-impresion svg.predicciones-grafica {"):
        assert regla in css, regla
    ajenas = [p for p in (APP / "templates").rglob("*.html")
              if "predicciones" not in p.parts and re.search(r'class="[^"]*\bpredicciones-', p.read_text(encoding="utf-8"))]
    assert ajenas == []
    for p in (APP / "templates" / "predicciones").glob("*.html"):
        texto = p.read_text(encoding="utf-8")
        if not p.name.startswith("_"):
            assert 'class="producto1-impresion"' in texto, p.name
        assert "<script" not in texto and "cdn" not in texto.lower() and "h-100" not in texto, p.name


def test_graficas_acompanadas_de_tablas_y_escalas_por_cifra(entorno):
    from app.api.web.routers import predicciones as web

    g = web.intervalos({"a": {"media": 0.01, "intervalo": [0.0, 0.02]}, "b": {"media": -3.0, "intervalo": None},
                        "c": {"media": None}})
    assert [f["metrica"] for f in g["filas"]] == ["a", "b"]
    assert g["filas"][0]["limite"] == pytest.approx(0.023) and g["filas"][1]["limite"] == pytest.approx(3.45)
    assert g["filas"][1]["x1"] is None and g["filas"][0]["x1"] == pytest.approx(g["cero"])
    b = web.barras_ranking([{"candidato": "AZUL", "probabilidad": 0.2, "uniforme": 1 / 6},
                            {"candidato": [1, "ROJO"], "probabilidad": 0.1, "uniforme": 1 / 6}])
    assert [x["etiqueta"] for x in b["barras"]] == ["azul", "1 rojo"]
    _, _, centro, c = _preparado(entorno)
    centro.ahora("MILOTO")
    texto = c.get("/predicciones/miloto").text
    assert texto.count("<svg") == texto.count("Barra: probabilidad emitida") == 2
    assert texto.count("<table") >= 6
