"""Producto 6: web, API y comando sobre el mismo caso de uso.

- `/resultados` y `/resultados/{juego}` en los cuatro juegos, enlaces en la
  navegacion y en el panel diario;
- coincidencia entre HTML, JSON, comando, graficas y exportacion completa
  (no solo la pagina visible); CSV sin formulas;
- ningun GET escribe; los POST piden la maquina local y el token;
- «usar esta configuracion»: vista previa, version nueva con el caso de uso
  de Producto 5, idempotente y sin entrenar;
- seguimiento sin resultados: se dice y se ofrece retrospectiva, sin cambiar
  de tipo; «sin muestra comun» visible; la uniforme visible cuando gana;
- reglas de impresion limitadas a las clases `resultados-*`."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from urllib.parse import quote

import pytest

from app.api.web.routers import resultados as web
from app.application.use_cases import resultados as uc
from scripts import resultados_modelos as cli
from tests.unit import fixtures_producto6 as f6

APP = Path(__file__).resolve().parents[2] / "app"


@pytest.fixture
def entorno(tmp_path):
    e = f6.entorno(tmp_path)
    e.poblar(("MILOTO", "COLORLOTO"))
    yield e
    f6.limpiar()


def _cli(e, *argv):
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(list(argv), centro_factory=e.centro, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def test_paginas_de_los_cuatro_juegos_y_enlaces(entorno):
    c = f6.cliente(entorno)
    indice = c.get("/resultados")
    assert indice.status_code == 200
    for slug in ("baloto", "baloto-revancha", "miloto", "colorloto"):
        assert f'href="/resultados/{slug}"' in indice.text
        assert c.get(f"/resultados/{slug}").status_code == 200
    assert 'href="/resultados"' in c.get("/operacion").text  # panel diario
    assert 'href="/carteras"' in indice.text and "Resultados de los modelos" in indice.text
    assert c.get("/resultados/quiniela").status_code == 404
    assert "AUTORIZA_EVALUACION = False" in indice.text


def test_seguimiento_sin_resultados_ofrece_retrospectiva_sin_cambiar_de_tipo(entorno):
    c = f6.cliente(entorno)
    html = c.get("/resultados/miloto").text
    assert 'id="sin-seguimiento"' in html and "tipo=retrospectiva" in html
    assert '<option value="seguimiento" selected>' in html
    assert "Sin muestra común" in html  # todas las lineas pendientes: no hay clasificacion
    assert "Uniforme (referencia)" not in html


def test_html_json_comando_graficas_y_exportacion_coinciden(entorno):
    entorno.llega_el_resultado("COLORLOTO")
    c = f6.cliente(entorno)
    api = c.get("/api/resultados/COLORLOTO").json()
    codigo, salida, _ = _cli(entorno, "consultar", "--juego", "COLORLOTO")
    assert codigo == 0
    comando = json.loads(salida)
    for clave in ("seleccion", "resumenes", "comparacion", "calibracion", "evolucion", "historial", "carteras"):
        assert comando[clave] == api[clave], clave
    html = c.get("/resultados/colorloto").text
    for fila in api["comparacion"]["clasificacion"]:
        assert "%.5f" % fila["log_loss"] in html and "%+.5f" % fila["diferencia"] in html
    assert "Uniforme (referencia)" in html
    # la grafica usa exactamente los puntos de la serie (y la tabla, los mismos)
    g = web.grafica_de_evolucion(api["evolucion"], {})
    assert [[p["acumulada"] for p in t["puntos"]] for t in g["trazos"]] == [
        [p["acumulada"] for p in s] for s in api["evolucion"].values()]
    tabla = web.tabla_de_evolucion(api["evolucion"])
    assert [f["objetivo"] for f in tabla] == api["comparacion"]["objetivos_comunes"]
    for punto in g["trazos"][0]["puntos"]:
        assert "%+.5f" % punto["acumulada"] in html
    # calibracion: grafica solo con intervalos no vacios, tabla con todos
    for clave, cal in api["calibracion"].items():
        d = cal["diagnosticos"]["pares"]
        gc = web.grafica_de_calibracion(d)
        assert len(gc["puntos"]) == sum(1 for i in d["intervalos"] if i["predicciones"])
    assert html.count("<td>[") >= 12 * len(api["seleccion"])


def test_exportacion_completa_aunque_la_pagina_sea_parcial(entorno):
    entorno.llega_el_resultado("MILOTO")
    c = f6.cliente(entorno)
    consulta = c.get("/api/resultados/MILOTO", params={"por_pagina": 1}).json()
    total = consulta["historial"]["total"]
    assert total == 3 and len(consulta["historial"]["filas"]) == 1 and consulta["historial"]["paginas"] == 3
    paginas = [c.get("/api/resultados/MILOTO", params={"por_pagina": 1, "pagina": n}).json()["historial"]["filas"][0]
               for n in (1, 2, 3)]
    texto = c.get("/resultados/miloto/exportar.csv").text
    filas = list(csv.reader(io.StringIO(texto)))
    assert filas[0] == list(uc.COLUMNAS_CSV) and len(filas) == 1 + total
    assert all(len(f) == len(uc.COLUMNAS_CSV) for f in filas)
    assert {f[filas[0].index("identificador")] for f in filas[1:]} == {p["identificador"] for p in paginas}
    exportado = c.get("/resultados/miloto/exportar.json").json()
    assert len(exportado["emisiones"]) == total and "historial" not in exportado
    assert all("congelado" not in e for e in exportado["emisiones"])
    _, salida, _ = _cli(entorno, "exportar", "--juego", "MILOTO", "--formato", "csv")
    assert salida == texto


def test_csv_sin_formulas():
    assert uc._texto("=HIPERVINCULO(\"x\")") == "'=HIPERVINCULO(\"x\")"
    for inicio in ("+", "-", "@", "\t", "\r"):
        assert uc._texto(inicio + "a").startswith("'")
    assert uc._texto("normal") == "normal" and uc._texto(None) == ""
    assert uc._numero(0.1) == "0.1" and uc._numero(None) == "" and uc._numero(3) == "3"


def test_ningun_get_escribe(entorno):
    entorno.llega_el_resultado("MILOTO")
    centro = entorno.centro()
    clave = centro.guardar_informe("MILOTO")["clave"]
    linea = entorno.e5.almacen.lineas("MILOTO")[0]
    c = f6.cliente(entorno, centro=centro)
    antes = f6.foto(entorno.directorio)
    urls = ["/resultados", "/resultados/miloto", "/resultados/miloto?tipo=retrospectiva&pagina=2",
            "/resultados/miloto/exportar.csv", "/resultados/miloto/exportar.json", f"/resultados/informes/{clave}",
            f"/resultados/informes/{clave}/exportar.json", f"/resultados/miloto/configuracion?linea={quote(linea)}",
            "/api/resultados", "/api/resultados/MILOTO", "/api/resultados/MILOTO/exportar.csv",
            "/api/resultados/MILOTO/exportar.json", "/api/resultados/MILOTO/informes",
            f"/api/resultados/informes/{clave}", f"/api/resultados/MILOTO/configuracion?linea={quote(linea)}"]
    for url in urls:
        assert c.get(url).status_code == 200, url
    for orden in (["indice"], ["consultar", "--juego", "MILOTO"], ["informes", "--juego", "MILOTO"],
                  ["verificar", "--clave", clave], ["configuracion", "--juego", "MILOTO", "--linea", linea]):
        assert _cli(entorno, *orden)[0] == 0, orden
    assert f6.foto(entorno.directorio) == antes


@pytest.mark.parametrize("cambios", [{"token": "malo"}, {"client": ("10.0.0.5", 5000)},
                                     {"cabeceras": {"origin": "http://otro.example"}}])
def test_post_protegidos(entorno, cambios):
    c = f6.cliente(entorno, client=cambios.get("client", f6.LOCAL))
    # E10.1: la consola ya no sirve páginas a un cliente remoto; el token se lee desde un cliente local.
    local = f6.cliente(entorno) if "client" in cambios else c
    token = cambios.get("token") or local.get("/resultados/miloto").text.split('name="token_local" value="')[1][:43]
    linea = entorno.e5.almacen.lineas("MILOTO")[0]
    antes = f6.foto(entorno.directorio)
    cabeceras = cambios.get("cabeceras", {})
    for url, datos in (("/resultados/miloto/informes", {}), ("/resultados/miloto/configuracion", {"linea": linea}),
                       (f"/resultados/informes/{'0' * 64}/verificar", {})):
        r = c.post(url, data={"token_local": token, **datos}, headers=cabeceras)
        assert r.status_code == 403 and "Acción rechazada" in r.text, url
    assert f6.foto(entorno.directorio) == antes


def test_guardar_y_verificar_desde_la_web(entorno):
    entorno.llega_el_resultado("MILOTO")
    c = f6.cliente(entorno)
    token = f6.token(c)
    r = c.post("/resultados/miloto/informes", data={"token_local": token, "tipo": "seguimiento"},
               follow_redirects=False)
    assert r.status_code == 303
    clave = re.search(r"/resultados/informes/([0-9a-f]{64})", r.headers["location"]).group(1)
    pagina = c.get(r.headers["location"])
    assert clave in pagina.text and "Uniforme (referencia)" in pagina.text
    otra = c.post("/resultados/miloto/informes", data={"token_local": token}, follow_redirects=False)
    assert otra.headers["location"].endswith(f"{clave}?reutilizado=1")
    v = c.post(f"/resultados/informes/{clave}/verificar", data={"token_local": token})
    assert v.status_code == 200 and "Correcta" in v.text and "Exacta" in v.text
    assert "coincide con la consulta actual" in v.text
    assert c.get(f"/resultados/informes/{'0' * 64}").status_code == 404
    assert c.get("/resultados/miloto?desde=x").status_code == 422
    assert c.get("/resultados/miloto?desde=9&hasta=2").status_code == 422
    assert c.get("/api/resultados/MILOTO", params={"linea": "operacion:no-existe"}).status_code == 422


class EjecutorQueNoDebeUsarse:
    def __getattr__(self, nombre):
        raise AssertionError(f"«usar esta configuracion» no debe entrenar ni simular ({nombre})")


def test_usar_esta_configuracion_previa_version_e_idempotencia(entorno):
    servicio = entorno.e5.carteras(ejecutor=EjecutorQueNoDebeUsarse())
    centro = uc.CentroDeResultados(entorno.e3.almacen, entorno.e4.almacen, entorno.e5.almacen, entorno.informes,
                                   entorno.e4.abrir, carteras_servicio=lambda: servicio)
    c = f6.cliente(entorno, centro=centro)
    token = f6.token(c)
    linea = sorted(entorno.e5.almacen.lineas("COLORLOTO"))[0]
    previa = c.get(f"/resultados/colorloto/configuracion?linea={quote(linea)}")
    assert previa.status_code == 200 and "Guardar como configuración vigente" in previa.text
    for texto in ("uniforme_paleta", "libre", "42", linea):
        assert texto in previa.text
    carteras_antes = f6.foto(entorno.directorio / "carteras" / "carteras")
    r = c.post("/resultados/colorloto/configuracion", data={"token_local": token, "linea": linea})
    assert r.status_code == 200 and "Configuración guardada como versión 1" in r.text
    vigente = servicio.configuracion_vigente("COLORLOTO").artefacto
    assert (vigente["modelo"]["id"], vigente["linea"], vigente["cantidad"]) == ("uniforme_paleta", linea, 3)
    r = c.post("/resultados/colorloto/configuracion", data={"token_local": token, "linea": linea})
    assert "ya es la vigente" in r.text and len(servicio.configuraciones("COLORLOTO")) == 1
    assert f6.foto(entorno.directorio / "carteras" / "carteras") == carteras_antes
    assert c.get("/resultados/colorloto/configuracion?linea=no-existe").status_code == 404
    # el comando usa el mismo caso de uso
    codigo = cli.ejecutar(["configurar", "--juego", "COLORLOTO", "--linea", linea], centro_factory=lambda: centro,
                          salida=io.StringIO(), errores=io.StringIO())
    assert codigo == 0 and len(servicio.configuraciones("COLORLOTO")) == 1


def test_base_caida_en_pantalla_y_en_el_comando(entorno):
    entorno.e4.base_caida = True
    c = f6.cliente(entorno, conectada=False)
    assert "no se inventa un último resultado" in c.get("/resultados").text
    assert "la base no responde" in c.get("/resultados/miloto").text
    codigo, _, errores = _cli(entorno, "consultar", "--juego", "MILOTO")
    assert codigo == cli.EXIT_CONEXION and "base no disponible" in errores
    codigo, salida, errores = _cli(entorno, "guardar", "--juego", "MILOTO")
    assert codigo == cli.EXIT_PARCIAL and json.loads(salida)["estado"] == "parcial"


def test_codigos_del_comando(entorno):
    assert _cli(entorno, "consultar", "--juego", "MILOTO", "--desde", "9", "--hasta", "2")[0] == cli.EXIT_USO
    assert _cli(entorno, "informe", "--clave", "0" * 64)[0] == cli.EXIT_USO
    assert _cli(entorno, "orden-desconocida")[0] == cli.EXIT_USO
    codigo, salida, _ = _cli(entorno, "rutas")
    assert codigo == 0 and "directorio_resultados_modelos" in salida
    assert "DATABASE_URL" not in salida and "postgresql" not in salida.lower()
    clave = entorno.centro().guardar_informe("MILOTO")["clave"]
    ruta = next((entorno.directorio / "resultados").rglob(f"{clave}.json"))
    ruta.write_bytes(ruta.read_bytes().replace(b"MILOTO", b"MILOTX", 1))
    assert _cli(entorno, "verificar", "--clave", clave)[0] == cli.EXIT_ALTERADO


def test_reglas_de_impresion_limitadas_a_resultados():
    css = (APP / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    impresion = css[css.index("@media print"):]
    reglas = [l.strip() for l in css.splitlines() if "resultados-" in l and l.strip().endswith("{")]
    assert reglas and all(l.startswith("body.producto1-impresion") for l in reglas)
    # en pantalla, solo el ancho minimo de las paginas con tarjetas de resultados
    assert [l for l in reglas if css.index(l) < css.index("@media print")] == [
        "body.producto1-impresion .content-area:has(.resultados-tarjeta) {",
        "body.producto1-impresion .resultados-lectura {"]
    assert "resultados-" in impresion
    ajenas = [p for p in (APP / "templates").rglob("*.html")
              if "resultados" not in p.parts and re.search(r'class="[^"]*\bresultados-', p.read_text(encoding="utf-8"))]
    assert ajenas == []
    for p in (APP / "templates" / "resultados").glob("*.html"):
        texto = p.read_text(encoding="utf-8")
        assert "<script" not in texto and "cdn" not in texto.lower(), p.name  # la semantica no depende de recursos
