"""Producto 4: impresion de las paginas del laboratorio.

- Trazabilidad (informe y pronostico) y Parametros de las recetas (catalogo
  de cada juego) son desplegables cerrados en pantalla. Un `<details>` cerrado
  no imprime su contenido, asi que la plantilla genera el contenido una sola
  vez y lo muestra dos: en el desplegable y en una copia que solo aparece al
  imprimir (`laboratorio-solo-impresion`). Imprimir no entrena ni escribe.
- Las reglas nuevas usan solo clases `laboratorio-*`, que solo aparecen en
  templates/laboratorio/: ninguna otra pagina cambia.
- Al fragmentar paginas se conservan el ranking completo, las tablas con su
  cabecera y los objetivos exactos de cada candidato.

Comprobado ademas en Chromium con Bootstrap real (PDF Carta vertical y
horizontal); estas pruebas fijan la estructura que lo hace posible."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from tests.unit import fixtures_producto4 as f4

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
CSS = RAIZ_BACKEND / "app" / "static" / "css" / "styles.css"
PLANTILLAS = RAIZ_BACKEND / "app" / "templates"
CLASES = ("laboratorio-desplegable", "laboratorio-solo-impresion", "laboratorio-tarjeta", "laboratorio-cabecera",
          "laboratorio-receta")


@pytest.fixture(scope="module")
def paginas(tmp_path_factory):
    e = f4.entorno(tmp_path_factory.mktemp("impresion"))
    protocolo = le.Protocolo(bloques=2, perfil="reducido")
    claves = {j: e.laboratorio().comparar_ahora([j], protocolo)["juegos"][j]["experimento"]
              for j in ("BALOTO", "MILOTO", "COLORLOTO")}
    c = f4.cliente(e)
    tok = f4.token(c)
    modelos = {"BALOTO": "logistica_regularizada", "MILOTO": "hgb_clasificador", "COLORLOTO": "poisson_regularizado"}
    salida = {"entorno": e, "claves": claves, "cliente": c, "informe": {}, "pronostico": {}, "juego": {}, "api": {},
              "identificadores": {}}
    for j, clave in claves.items():
        g = c.post(f"/laboratorio/experimentos/{clave}/generar", data={"modelo": modelos[j], "token_local": tok},
                   follow_redirects=False)
        identificador = g.headers["location"].split("/")[-1].split("?")[0]
        salida["identificadores"][j] = identificador
        salida["informe"][j] = c.get(f"/laboratorio/experimentos/{clave}").text
        salida["pronostico"][j] = c.get(f"/laboratorio/pronosticos/{identificador}").text
        salida["api"][j] = (c.get(f"/api/laboratorio/experimentos/{clave}").json()["informe"],
                            c.get(f"/api/laboratorio/pronosticos/{identificador}").json()["pronostico"])
    for slug in ("baloto", "miloto", "colorloto"):
        salida["juego"][slug] = c.get(f"/laboratorio/{slug}").text
    salida["panel"] = c.get("/laboratorio").text
    yield salida
    f4.limpiar()


def _bloque_de_impresion(css: str) -> str:
    inicio = css.index("@media print")
    return css[inicio:css.index("\n}\n", inicio) + 3]


def _reglas(bloque: str) -> list[tuple[list[str], str]]:
    sin_comentarios = re.sub(r"/\*.*?\*/", "", bloque, flags=re.S)
    return [([s.strip() for s in sel.split(",") if s.strip()], cuerpo)
            for sel, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", sin_comentarios)]


def _desplegable(html: str) -> str:
    """El <details> del laboratorio, completo y sin atributo `open`."""
    inicio = html.index("<details", html.index("laboratorio-desplegable") - 120)
    apertura = html[inicio:html.index(">", inicio) + 1]
    assert "laboratorio-desplegable" in apertura and " open" not in apertura, apertura
    return html[inicio:html.index("</details>", inicio) + len("</details>")]


def _copia(html: str) -> str:
    """La copia que solo se imprime: fuera de cualquier <details>, hasta el final del bloque."""
    inicio = html.index('laboratorio-solo-impresion">')
    antes = html[:inicio]
    assert antes.count("<details") == antes.count("</details>"), "la copia imprimible no puede ir dentro de un <details>"
    return html[inicio:]


@pytest.mark.parametrize("tipo", ["informe", "pronostico"])
@pytest.mark.parametrize("juego", ["BALOTO", "MILOTO", "COLORLOTO"])
def test_trazabilidad_se_imprime_con_el_desplegable_cerrado(paginas, tipo, juego):
    html = paginas[tipo][juego]
    assert html.count("laboratorio-desplegable") == 1 and html.count('laboratorio-solo-impresion"') == 1
    detalle = _desplegable(html)
    assert "<summary><strong>Trazabilidad</strong></summary>" in detalle
    lista = re.search(r'<dl class="row mb-2 mt-2">.*?</dl>', detalle, re.S).group(0)
    copia = _copia(html)
    assert copia.startswith('laboratorio-solo-impresion"><strong>Trazabilidad</strong>')
    assert re.search(r'<dl class="row mb-2 mt-2">.*?</dl>', copia, re.S).group(0) == lista  # mismo texto
    informe, pronostico = paginas["api"][juego]
    for valor in (informe["datos"]["sha256_historico"], informe["identidad"]["entorno"]["numpy"]):
        assert valor in lista
    if tipo == "informe":
        assert paginas["claves"][juego] in lista and "Ejecución" in lista and "Perfil" in lista
    else:
        assert pronostico["experimento"] == paginas["claves"][juego] and pronostico["experimento"] in lista
        assert "Receta" in lista and "Ajuste final" in lista and "Orden de emisión" in lista
    # el boton de verificar sigue solo en el desplegable (los botones no se imprimen)
    assert "/verificar" in detalle and "/verificar" not in copia[:copia.index("</dl>")]


@pytest.mark.parametrize("slug", ["baloto", "miloto", "colorloto"])
def test_parametros_se_imprimen_con_el_desplegable_cerrado(paginas, slug):
    html = paginas["juego"][slug]
    detalle = _desplegable(html)
    assert '<summary class="text-muted">Parámetros de las recetas</summary>' in detalle
    copia = _copia(html)
    assert copia.startswith('laboratorio-solo-impresion"><div class="text-muted laboratorio-cabecera">'
                            'Parámetros de las recetas</div>')
    recetas = re.findall(r'<div class="mt-1 laboratorio-receta">.*?</span></div>', detalle, re.S)
    assert recetas and re.findall(r'<div class="mt-1 laboratorio-receta">.*?</span></div>', copia, re.S)[
        :len(recetas)] == recetas
    juego = slug.upper()
    entradas = lm.candidatos_del_juego(juego)
    assert len(recetas) == len(entradas)
    for entrada, receta in zip(entradas, recetas):
        assert f"<strong>{entrada.id} v{entrada.version}</strong>" in receta
        for k in lm.parametros_de(entrada, "predeterminado"):
            assert f"{k}=" in receta, (entrada.id, k)
        assert "Variables:" in receta and "Transformación:" in receta


def test_reglas_nuevas_acotadas_al_laboratorio(paginas):
    css = CSS.read_text(encoding="utf-8")
    assert css.count("@media print") == 1
    impresion = _bloque_de_impresion(css)
    nuevas = [(sel, cuerpo) for sel, cuerpo in _reglas(impresion) if any("laboratorio-" in s for s in sel)]
    assert {s for sel, _ in nuevas for s in sel} == {
        "body.producto1-impresion details.laboratorio-desplegable",
        "body.producto1-impresion .laboratorio-solo-impresion",
        "body.producto1-impresion .laboratorio-tarjeta",
        "body.producto1-impresion .laboratorio-cabecera",
        "body.producto1-impresion .laboratorio-receta"}
    for sel, _ in nuevas:  # cada selector termina en una clase del laboratorio
        assert all(re.search(r"\.laboratorio-[a-z-]+$", s) for s in sel), sel
    cuerpos = {sel[0].split()[-1]: re.sub(r"\s+", " ", cuerpo).strip() for sel, cuerpo in nuevas}
    assert cuerpos["details.laboratorio-desplegable"] == "display: none !important;"
    assert cuerpos[".laboratorio-solo-impresion"] == "display: block;"
    assert cuerpos[".laboratorio-tarjeta"] == "display: block;"
    assert "break-after: avoid;" in cuerpos[".laboratorio-cabecera"]
    assert "break-inside: avoid;" in cuerpos[".laboratorio-cabecera"]
    assert cuerpos[".laboratorio-receta"] == "break-inside: avoid; page-break-inside: avoid;"
    pantalla = re.sub(r"/\*.*?\*/", "", css[:css.index("@media print")], flags=re.S)
    assert [x.strip() for x in re.findall(r"[^{}]*laboratorio-[^{}]*\{[^{}]*\}", pantalla)] == [
        ".laboratorio-solo-impresion {\n    display: none;\n}"]
    # las clases solo aparecen en las plantillas del laboratorio
    for ruta in sorted(PLANTILLAS.rglob("*.html")):
        texto = ruta.read_text(encoding="utf-8")
        if ruta.parent.name != "laboratorio":
            assert not any(clase in texto for clase in CLASES), ruta
    # y las paginas ajenas no las reciben (cliente de las pruebas de Producto 1)
    from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
    from tests.unit import fixtures_producto1 as fx

    juegos, resultados, colores = fx.repositorios(
        {"BALOTO": fx.historico_numerico("BALOTO", 84), "MILOTO": fx.historico_numerico("MILOTO", 84, primero=1)},
        colorloto=fx.historico_colorloto(40))
    ajeno = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(paginas["entorno"].directorio.parent
                                                                                    / "ajeno"))
    try:
        for url in ("/estadisticas", "/estadisticas/baloto/resumen", "/estadisticas/colorloto/resumen", "/pronosticos",
                    "/operacion", "/rendimiento"):
            r = ajeno.get(url)
            assert r.status_code == 200 and '<body class="producto1-impresion">' in r.text, url
            assert not any(clase in r.text for clase in CLASES), url
        desconectado = fx.cliente(juegos, resultados, colores, PronosticoExperimentalFileStore(
            paginas["entorno"].directorio.parent / "ajeno"), conectada=False)
        r = desconectado.get("/")
        assert r.status_code == 200 and "<body>" in r.text and not any(clase in r.text for clase in CLASES)
    finally:
        f4.cliente(paginas["entorno"])  # restaura las dependencias del laboratorio para el resto del modulo


@pytest.mark.parametrize("juego", ["BALOTO", "MILOTO", "COLORLOTO"])
def test_pronostico_conserva_el_ranking_completo_y_la_sugerencia_primero(paginas, juego):
    html = paginas["pronostico"][juego]
    _, artefacto = paginas["api"][juego]
    p = artefacto["pronostico"]
    esperado = p["ranking_de_pares"] if juego == "COLORLOTO" else p["ranking"]
    tabla = html[html.index("Ranking completo"):]
    tabla = tabla[:tabla.index("</table>")]
    assert "<thead>" in tabla
    filas = re.findall(r"<tr><td>(\d+)</td><td>([^<]+)</td><td class=\"text-end\">([0-9.]+)</td>", tabla)
    assert [int(f[0]) for f in filas] == list(range(1, len(esperado) + 1))
    nombres = [f"{x['numero']} {x['color']}" if juego == "COLORLOTO" else str(x["numero"]) for x in esperado]
    assert [f[1] for f in filas] == nombres and len(set(nombres)) == len(nombres)
    probabilidades = [float(f[2]) for f in filas]
    assert probabilidades == sorted(probabilidades, reverse=True)
    if juego != "COLORLOTO":
        assert len(filas) == {"BALOTO": 43, "MILOTO": 39}[juego]  # todos los numeros del juego
    # la sugerencia va en la cabecera de la tarjeta, antes del ranking (al imprimir, primero)
    assert html.index('class="impresion-sugerencia') < html.index("Ranking completo")


@pytest.mark.parametrize("juego", ["BALOTO", "MILOTO", "COLORLOTO"])
def test_informe_conserva_tablas_y_objetivos_al_fragmentar(paginas, juego):
    html = paginas["informe"][juego]
    informe, _ = paginas["api"][juego]
    objetivos = [str(o) for o in informe["muestra_comun"]["objetivos"]]
    ranking = html[html.index("Ranking de candidatos"):]
    ranking = ranking[:ranking.index("</table>")]
    assert len(re.findall(r"<tr><td>\d+</td>", ranking)) == len(informe["resumen"]["ranking"])
    nuevos = [c for c in informe["candidatos"] if c["familia"] != "uniforme"]
    tarjetas = re.split(r'(?=<div class="card stat-card impresion-fragmentable laboratorio-tarjeta p-3 mb-3" '
                        r'id="candidato-)', html)[1:]
    assert len(tarjetas) == len(nuevos)
    for c, tarjeta in zip(nuevos, tarjetas):
        assert f'id="candidato-{c["id"]}"' in tarjeta
        # cabecera (titulo, explicacion, aviso) agrupada y seguida de su tabla de bloques
        cabecera = re.search(r'<div class="laboratorio-cabecera">\s*<h6>.*?</div>\s*<div class="tabla-desplazable">'
                             r'<table class="table table-sm small mb-2">\s*<thead>', tarjeta, re.S)
        assert cabecera and c["nombre"] in cabecera.group(0)
        impresa = re.search(r'<div class="solo-impresion-bloque"><table.*?</table>', tarjeta, re.S)
        if c["estado"] == "completo":
            assert impresa, c["id"]  # la tabla "Datos por objetivo" se imprime entera
        if impresa:
            impresa = impresa.group(0)
            assert "<thead>" in impresa
            filas = re.findall(r"<tr><td>(\d+)</td>", impresa)
            assert filas == [str(f["objetivo"]) for f in c["por_objetivo"]]
            if c["estado"] == "completo":
                assert filas == objetivos  # los objetivos exactos de la muestra comun, una vez cada uno
    # todas las tablas del informe tienen cabecera (se repite al fragmentar) y las tarjetas largas se fragmentan
    assert html.count("<table") == html.count("<thead>")
    assert html.count("impresion-fragmentable laboratorio-tarjeta") == len(nuevos) + 2
    css = _bloque_de_impresion(CSS.read_text(encoding="utf-8"))
    assert "body.producto1-impresion thead {\n        display: table-header-group;" in css
    assert "body.producto1-impresion .stat-card.impresion-fragmentable {\n        break-inside: auto;" in css


def test_mostrar_la_version_imprimible_no_entrena_ni_escribe(paginas, monkeypatch):
    c = f4.cliente(paginas["entorno"])
    raiz = paginas["entorno"].directorio
    antes = sorted((str(p.relative_to(raiz)), p.stat().st_size) for p in raiz.rglob("*") if p.is_file())
    monkeypatch.setattr(le, "evaluar", lambda *a, **k: pytest.fail("mostrar una pagina no debe entrenar"))
    monkeypatch.setattr(lm, "ajustar_candidato", lambda *a, **k: pytest.fail("mostrar una pagina no debe ajustar"))
    for j, clave in paginas["claves"].items():
        assert "laboratorio-solo-impresion" in c.get(f"/laboratorio/experimentos/{clave}").text
        assert "laboratorio-solo-impresion" in c.get(f"/laboratorio/pronosticos/{paginas['identificadores'][j]}").text
    for slug in paginas["juego"]:
        assert "laboratorio-solo-impresion" in c.get(f"/laboratorio/{slug}").text
    assert sorted((str(p.relative_to(raiz)), p.stat().st_size) for p in raiz.rglob("*") if p.is_file()) == antes
