"""Producto 2: pronosticos de MiLoto y ColorLoto en casos de uso, web,
API y comando; comparacion de pronosticos guardados con resultados
observados para los cuatro juegos; compatibilidad de artefactos v1.

Historicos sinteticos. Ninguna prueba usa la base real."""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.application.ml import pronostico_colorloto as pc
from app.application.ml import pronostico_experimental as pe
from app.application.ml import pronostico_miloto as pm
from app.application.use_cases.pronostico_experimental import (
    CompararConResultadosObservados,
    ConsultarPronosticosExperimentales,
    GenerarPronosticoExperimental,
    PronosticoExperimentalNoDisponibleError,
    VerificarPronosticoExperimental,
)
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx

RAIZ = Path(__file__).resolve().parents[2]
RELOJ = lambda: datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)  # noqa: E731
CONFIGS = {"BALOTO": pe.ConfiguracionExperimental(tamano_bloque=10, bloques_de_evaluacion=2,
                                                   minimo_objetivos_de_entrenamiento=40),
           "BALOTO_REVANCHA": pe.ConfiguracionExperimental(tamano_bloque=10, bloques_de_evaluacion=2,
                                                           minimo_objetivos_de_entrenamiento=40),
           "MILOTO": pm.ConfiguracionMiLoto(), "COLORLOTO": pc.ConfiguracionColorLoto()}
LOCAL = ("127.0.0.1", 50000)


@pytest.fixture
def entorno(tmp_path):
    historicos = {"BALOTO": fx.historico_numerico("BALOTO", 130), "BALOTO_REVANCHA": fx.historico_numerico(
        "BALOTO_REVANCHA", 130), "MILOTO": fx.historico_numerico("MILOTO", 84, primero=1)}
    color = fx.historico_colorloto(60)
    juegos, resultados, colores = fx.repositorios(historicos, colorloto=color)
    almacen = PronosticoExperimentalFileStore(tmp_path / "pronosticos")
    return juegos, resultados, colores, almacen, {**historicos, "COLORLOTO": color}


def _generar(entorno, codigo, hasta=None, reloj=RELOJ):
    juegos, resultados, _, almacen, _ = entorno
    return GenerarPronosticoExperimental(juegos, resultados, almacen, reloj=reloj,
                                         configuraciones=CONFIGS).ejecutar(codigo, hasta_numero_sorteo=hasta)


# ---------------------------------------------------------------------------
# Casos de uso y almacen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("codigo,objetivo", [("MILOTO", 85), ("COLORLOTO", 61)])
def test_generar_guardar_e_idempotencia(entorno, codigo, objetivo):
    g = _generar(entorno, codigo)
    a = g.artefacto
    assert a["esquema"] == "pronostico-experimental/2" and a["pronostico"]["objetivo"] == objetivo
    assert a["generacion"]["clasificacion_temporal"]["tipo"] == "pronostico_sobre_el_ultimo_dato_disponible"
    assert a["generacion"]["secuencia_en_el_objetivo"] == 1 and pe.artefacto_integro(a)
    otra = _generar(entorno, codigo, reloj=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert otra.reutilizado and otra.identificador == g.identificador and otra.artefacto == a
    assert len(list(entorno[3]._carpeta(codigo).glob("*.json"))) == 1


def test_simulacion_retrospectiva_colorloto_con_resultado(entorno):
    g = _generar(entorno, "COLORLOTO", hasta=50)
    c = g.artefacto["generacion"]["clasificacion_temporal"]
    real = next(r for r in entorno[4]["COLORLOTO"] if r.numero_sorteo == 51)
    assert c["tipo"] == "simulacion_retrospectiva" and c["resultado_observado"]["pares"] == [list(p) for p in real.pares]


def test_miloto_datos_insuficientes(entorno):
    with pytest.raises(PronosticoExperimentalNoDisponibleError, match="[Dd]atos insuficientes"):
        _generar(entorno, "MILOTO", hasta=25)


def test_correccion_del_historico_crea_otra_version(entorno):
    juegos, resultados, _, almacen, historicos = entorno
    v1 = _generar(entorno, "MILOTO")
    mid = juegos.obtener_por_codigo("MILOTO").id
    resultados.numericos[mid] = [dataclasses.replace(historicos["MILOTO"][3], numeros=(1, 2, 3, 4, 5)),
                                 *[r for r in historicos["MILOTO"] if r.numero_sorteo != 4]]
    v2 = _generar(entorno, "MILOTO")
    assert v2.identificador != v1.identificador and v2.artefacto["generacion"]["version_anterior"] == v1.identificador
    versiones = [(g.identificador, g.version) for g in ConsultarPronosticosExperimentales(almacen).resumen("MILOTO").guardados]
    assert versiones == [(v2.identificador, 2), (v1.identificador, 1)]


def test_verificar_reproduccion_miloto_y_colorloto(entorno):
    juegos, resultados, _, almacen, _ = entorno
    for codigo in ("MILOTO", "COLORLOTO"):
        g = _generar(entorno, codigo)
        r = VerificarPronosticoExperimental(juegos, resultados, almacen).ejecutar(codigo, g.identificador)
        assert r["huella_exacta"] and r["mismos_datos"] and r["maxima_diferencia_de_probabilidad"] == 0.0


# ---------------------------------------------------------------------------
# Resultados observados (cuatro juegos)
# ---------------------------------------------------------------------------

def _comparar(entorno, codigo):
    juegos, resultados, _, almacen, _ = entorno
    return CompararConResultadosObservados(almacen, juegos, resultados).ejecutar(codigo)


@pytest.mark.parametrize("codigo,hasta", [("BALOTO", 2200), ("BALOTO_REVANCHA", 2200), ("MILOTO", 60),
                                          ("COLORLOTO", 50)])
def test_resultado_observado_y_coincidencias(entorno, codigo, hasta):
    g = _generar(entorno, codigo, hasta=hasta)
    bytes_antes = {p: p.read_bytes() for p in entorno[3]._carpeta(codigo).iterdir()}
    filas = _comparar(entorno, codigo)
    assert len(filas) == 1 and filas[0]["identificador"] == g.identificador
    c = filas[0]["comparacion"]
    real = next(r for r in entorno[4][codigo] if r.numero_sorteo == hasta + 1)
    assert c["estado"] == "observado" and c["objetivo"] == hasta + 1 and c["fecha"] == real.fecha.isoformat()
    assert c["emision"] == "reconstruccion_retrospectiva"
    if codigo == "COLORLOTO":
        sugeridos = [(f["numero"], f["color"]) for f in g.artefacto["pronostico"]["pares"]]
        assert c["coincidencias"]["pares"] == pc.coincidencias(sugeridos, real.pares)
        assert c["resultado"]["pares"] == [list(p) for p in real.pares]
    else:
        assert c["coincidencias"]["numeros"] == len(set(real.numeros) & set(g.artefacto["pronostico"]["numeros_sugeridos"]))
        assert c["resultado"]["numeros"] == list(real.numeros)
    if codigo.startswith("BALOTO"):
        assert c["coincidencias"]["superbalota"] == (real.superbalota == g.artefacto["superbalota"]["pronostico"]["sugerida"])
    assert c["discrepancias"] == []
    assert c["historico_hasta_el_corte"]["estado"] == "coincide"
    assert {p: p.read_bytes() for p in entorno[3]._carpeta(codigo).iterdir()} == bytes_antes


def test_pendiente_y_luego_observado(entorno):
    juegos, resultados, _, _, historicos = entorno
    g = _generar(entorno, "MILOTO")
    c = _comparar(entorno, "MILOTO")[0]["comparacion"]
    assert c["estado"] == "pendiente" and "85" in c["motivo"]
    assert c["emision"] == "emitido_sin_el_resultado_en_la_base_local"
    assert "no acredita" in c["nota_sobre_fechas"]
    nuevo = dataclasses.replace(historicos["MILOTO"][-1], numero_sorteo=85,
                                fecha=historicos["MILOTO"][-1].fecha.replace(year=2030), numeros=(1, 2, 3, 4, 5))
    resultados.numericos[juegos.obtener_por_codigo("MILOTO").id] = [*historicos["MILOTO"], nuevo]
    c = _comparar(entorno, "MILOTO")[0]["comparacion"]
    assert c["estado"] == "observado" and c["emision"] == "emitido_sin_el_resultado_en_la_base_local"
    assert c["coincidencias"]["numeros"] == len({1, 2, 3, 4, 5} & set(g.artefacto["pronostico"]["numeros_sugeridos"]))


def test_no_corresponde_por_hueco(entorno):
    juegos, resultados, _, _, historicos = entorno
    _generar(entorno, "MILOTO", hasta=60)
    resultados.numericos[juegos.obtener_por_codigo("MILOTO").id] = [r for r in historicos["MILOTO"]
                                                                     if r.numero_sorteo != 61]
    c = _comparar(entorno, "MILOTO")[0]["comparacion"]
    assert c["estado"] == "no_corresponde" and "hueco" in c["motivo"]


def test_correccion_del_historico_se_informa(entorno):
    juegos, resultados, _, _, historicos = entorno
    _generar(entorno, "COLORLOTO", hasta=50)
    corregido = [dataclasses.replace(r, pares=((1, "ROJO"),) * 6) if r.numero_sorteo in (10, 51) else r
                 for r in historicos["COLORLOTO"]]
    resultados.colorloto[juegos.obtener_por_codigo("COLORLOTO").id] = corregido
    c = _comparar(entorno, "COLORLOTO")[0]["comparacion"]
    assert {d["tipo"] for d in c["discrepancias"]} == {"historico_hasta_el_corte_cambio", "resultado_observado_cambio"}
    assert c["historico_hasta_el_corte"]["estado"] == "cambio"


@pytest.mark.parametrize("codigo,hasta", [("BALOTO", 2200), ("MILOTO", 60), ("COLORLOTO", 50)])
def test_observado_sin_historico_hasta_el_corte(entorno, codigo, hasta):
    """El objetivo figura en el historico actual, pero no queda ningun
    sorteo hasta el corte: no se puede verificar la entrada del artefacto.
    Se informa como no disponible, no como coincidencia ni como cambio."""
    juegos, resultados, _, almacen, historicos = entorno
    g = _generar(entorno, codigo, hasta=hasta)
    bytes_antes = {p: p.read_bytes() for p in almacen._carpeta(codigo).iterdir()}
    posteriores = [r for r in historicos[codigo] if r.numero_sorteo > hasta]
    destino = resultados.colorloto if codigo == "COLORLOTO" else resultados.numericos
    destino[juegos.obtener_por_codigo(codigo).id] = posteriores
    c = _comparar(entorno, codigo)[0]["comparacion"]
    assert c["estado"] == "observado" and c["objetivo"] == hasta + 1
    assert c["historico_hasta_el_corte"]["estado"] == "no_disponible"
    assert "no esta disponible" in c["historico_hasta_el_corte"]["motivo"]
    assert c["discrepancias"] == []  # ni coincidencia ni cambio demostrado
    assert {p: p.read_bytes() for p in almacen._carpeta(codigo).iterdir()} == bytes_antes
    assert g.artefacto == almacen.obtener(codigo, g.identificador).artefacto


def test_sin_historico_cargado_no_corresponde_y_no_verificable(entorno):
    juegos, resultados, _, _, _ = entorno
    _generar(entorno, "MILOTO", hasta=60)
    resultados.numericos[juegos.obtener_por_codigo("MILOTO").id] = []
    c = _comparar(entorno, "MILOTO")[0]["comparacion"]
    assert c["estado"] == "no_corresponde" and c["historico_hasta_el_corte"]["estado"] == "no_disponible"


def test_web_y_api_informan_corte_no_verificable(cliente, entorno):
    juegos, resultados, _, _, historicos = entorno
    _generar(entorno, "COLORLOTO", hasta=50)
    resultados.colorloto[juegos.obtener_por_codigo("COLORLOTO").id] = [
        r for r in historicos["COLORLOTO"] if r.numero_sorteo > 50]
    r = cliente.get("/api/resultados-observados/COLORLOTO").json()
    assert r["pronosticos"][0]["comparacion"]["historico_hasta_el_corte"]["estado"] == "no_disponible"
    j = cliente.get("/api/pronosticos/COLORLOTO").json()
    assert j["ultimo"]["resultado_observado"]["historico_hasta_el_corte"]["estado"] == "no_disponible"
    texto = cliente.get("/pronosticos/colorloto").text
    assert "No se puede verificar la entrada" in texto
    assert "El histórico hasta el corte cambió" not in texto


# ---------------------------------------------------------------------------
# Web, API y comando
# ---------------------------------------------------------------------------

@pytest.fixture
def cliente(entorno):
    juegos, resultados, colores, almacen, _ = entorno
    c = fx.cliente(juegos, resultados, colores, almacen, reloj=RELOJ, configuraciones=CONFIGS, client=LOCAL)
    yield c
    from app.main import app
    app.dependency_overrides = {}


def _token(c, slug):
    return re.search(r'name="token_local" value="([^"]+)"', c.get(f"/pronosticos/{slug}").text).group(1)


def test_indice_muestra_los_cuatro_juegos(cliente):
    texto = cliente.get("/pronosticos").text
    for nombre, slug in (("Baloto", "baloto"), ("Baloto Revancha", "baloto-revancha"), ("MiLoto", "miloto"),
                         ("ColorLoto", "colorloto")):
        assert nombre in texto and f'href="/pronosticos/{slug}"' in texto


@pytest.mark.parametrize("slug,textos", [
    ("miloto", ("frecuencia_con_contraccion_a_la_uniforme", "Referencia uniforme", "5/39", "Resultados observados",
                "Objetivos evaluados")),
    ("colorloto", ("pares_multinomial_con_suavizado_aditivo", "Log Loss por balota", "Coincidencias de pares", "Paleta del corte",
                   "Resultados observados", "multiconjunto")),
])
def test_generar_desde_la_web_y_detalle(cliente, slug, textos):
    r = cliente.post(f"/pronosticos/{slug}/generar", data={"token_local": _token(cliente, slug)}, follow_redirects=False)
    assert r.status_code == 303, r.text[:300]
    detalle = cliente.get(r.headers["location"]).text
    for texto in (*textos, "experimental", "Corte de datos", "versión 1 de 1"):
        assert texto in detalle, texto
    assert "futuro" not in detalle.lower()


def test_post_externo_rechazado_para_los_nuevos_juegos(entorno):
    juegos, resultados, colores, almacen, _ = entorno
    local = fx.cliente(juegos, resultados, colores, almacen, reloj=RELOJ, configuraciones=CONFIGS, client=LOCAL)
    token = _token(local, "miloto")
    externo = fx.cliente(juegos, resultados, colores, almacen, reloj=RELOJ, configuraciones=CONFIGS,
                         client=("203.0.113.9", 4000))
    try:
        for slug in ("miloto", "colorloto"):
            assert externo.post(f"/pronosticos/{slug}/generar", data={"token_local": token}).status_code == 403
            assert local.post(f"/pronosticos/{slug}/generar", data={"token_local": token},
                              headers={"Origin": "http://otro.example"}).status_code == 403
        assert not any(almacen._directorio.rglob("*.json"))
    finally:
        from app.main import app
        app.dependency_overrides = {}


def test_datos_insuficientes_en_la_web(cliente, entorno):
    r = cliente.post("/pronosticos/miloto/generar", data={"token_local": _token(cliente, "miloto"),
                                                         "hasta_numero_sorteo": "20"})
    assert r.status_code == 422 and "atos insuficientes" in r.text


def test_api_json_y_resultados_observados(cliente, entorno):
    g = _generar(entorno, "COLORLOTO", hasta=50)
    j = cliente.get("/api/pronosticos/COLORLOTO").json()
    assert j["estado_de_uso"] == "experimental_no_acreditado" and j["ultimo"]["identificador"] == g.identificador
    r = cliente.get("/api/resultados-observados/COLORLOTO").json()
    assert r["juego"] == "COLORLOTO" and r["pronosticos"][0]["comparacion"]["estado"] == "observado"
    for codigo in ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"):
        assert cliente.get(f"/api/resultados-observados/{codigo}").status_code == 200
    assert cliente.get("/api/resultados-observados/QUINA").status_code == 404
    assert cliente.get("/api/pronosticos/QUINA").status_code == 404


def test_detalle_web_y_api_muestran_resultado_observado_y_correccion(cliente, entorno):
    juegos, resultados, _, _, historicos = entorno
    g = _generar(entorno, "COLORLOTO", hasta=50)
    resultados.colorloto[juegos.obtener_por_codigo("COLORLOTO").id] = [
        dataclasses.replace(r, pares=((1, "ROJO"),) * 6) if r.numero_sorteo == 51 else r for r in historicos["COLORLOTO"]]
    texto = cliente.get("/pronosticos/colorloto").text
    for esperado in ("Resultados observados", "reconstrucción retrospectiva", "1 ROJO · 1 ROJO",
                     "El resultado del objetivo cambió desde que se generó", "no acredita anterioridad"):
        assert esperado in texto, esperado
    j = cliente.get(f"/api/pronosticos/COLORLOTO/{g.identificador}").json()
    assert j["resultado_observado"]["estado"] == "observado"
    assert j["resultado_observado"]["coincidencias"]["pares"] == pc.coincidencias(
        [(f["numero"], f["color"]) for f in g.artefacto["pronostico"]["pares"]], ((1, "ROJO"),) * 6)
    assert "Resultados observados" in cliente.get("/pronosticos/baloto").text


def test_resultados_observados_sin_base(cliente, entorno):
    from sqlalchemy.exc import OperationalError

    from app.api import dependencies as dep
    from app.main import app

    juegos, resultados, _, almacen, _ = entorno
    _generar(entorno, "MILOTO")

    class Caido:
        def obtener_por_codigo(self, codigo):
            raise OperationalError("SELECT 1", {}, ConnectionError("sin PostgreSQL"))

    app.dependency_overrides[dep.get_comparar_resultados] = lambda: CompararConResultadosObservados(
        almacen, Caido(), resultados)
    app.dependency_overrides[dep.get_consultar_pronosticos] = lambda: ConsultarPronosticosExperimentales(almacen)
    assert cliente.get("/api/resultados-observados/MILOTO").status_code == 503
    texto = cliente.get("/pronosticos/miloto").text
    assert "no se puede consultar el resultado de los objetivos" in texto and "Objetivo: sorteo 85" in texto
    assert cliente.get("/api/pronosticos/MILOTO").json()["ultimo"]["resultado_observado"] is None


def _comando(entorno, argv):
    from scripts import pronostico_experimental as cli
    juegos, resultados, _, almacen, _ = entorno

    @contextlib.contextmanager
    def repos():
        yield juegos, resultados

    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(argv, repositorios=repos, almacen_factory=lambda: almacen, reloj=RELOJ,
                          configuraciones=CONFIGS, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def test_comando_cuatro_juegos_y_resultados(entorno):
    codigo, out, err = _comando(entorno, ["entrenar", "--juego", "todos"])
    assert codigo == 0, err
    assert [d["juego"] for d in json.loads(out)] == ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"]
    codigo, out, _ = _comando(entorno, ["resultados", "--juego", "MILOTO"])
    assert codigo == 0 and json.loads(out)["pronosticos"][0]["comparacion"]["estado"] == "pendiente"
    codigo, _, err = _comando(entorno, ["entrenar", "--juego", "COLORLOTO", "--hasta-sorteo", "10"])
    assert codigo == 4 and "atos insuficientes" in err
    assert _comando(entorno, ["entrenar", "--juego", "QUINA"])[0] == 2


@pytest.mark.parametrize("codigo", ["MILOTO", "COLORLOTO"])
def test_comando_corte_retrospectivo_sale_del_historico_real(entorno, codigo):
    """El corte para comprobar un resultado observado se obtiene del
    historico cargado: al menos 30 sorteos hasta el corte y un objetivo
    (corte + 1) que existe. Luego el pronostico de ese corte queda
    `observado`."""
    juegos, resultados, _, _, historicos = entorno
    codigo_salida, out, err = _comando(entorno, ["corte-retrospectivo", "--juego", codigo])
    assert codigo_salida == 0, err
    d = json.loads(out)
    numeros = [r.numero_sorteo for r in historicos[codigo]]
    assert d["objetivo"] == d["corte"] + 1 and d["objetivo"] in numeros
    assert d["sorteos_hasta_el_corte"] == sum(1 for n in numeros if n <= d["corte"]) >= d["minimo"] == 30
    real = next(r for r in historicos[codigo] if r.numero_sorteo == d["objetivo"])
    assert d["fecha_objetivo"] == real.fecha.isoformat()
    assert _comando(entorno, ["entrenar", "--juego", codigo, "--hasta-sorteo", str(d["corte"])])[0] == 0
    codigo_salida, out, _ = _comando(entorno, ["resultados", "--juego", codigo])
    fila = next(f for f in json.loads(out)["pronosticos"] if f["corte"] == d["corte"])
    assert codigo_salida == 0 and fila["comparacion"]["estado"] == "observado"


def test_comando_corte_retrospectivo_salta_huecos_y_exige_minimo(entorno):
    juegos, resultados, _, _, historicos = entorno
    mid = juegos.obtener_por_codigo("MILOTO").id
    resultados.numericos[mid] = [r for r in historicos["MILOTO"] if r.numero_sorteo not in (84, 83)]
    d = json.loads(_comando(entorno, ["corte-retrospectivo", "--juego", "MILOTO"])[1])
    assert (d["corte"], d["objetivo"]) == (81, 82)
    resultados.numericos[mid] = historicos["MILOTO"][:30]
    codigo_salida, _, err = _comando(entorno, ["corte-retrospectivo", "--juego", "MILOTO"])
    assert codigo_salida == 4 and "no hay un corte" in err


# ---------------------------------------------------------------------------
# Impresion
# ---------------------------------------------------------------------------

def _bloque_impresion() -> str:
    css = (RAIZ / "app" / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    inicio = css.index("@media print {")
    return css[inicio:]


def _tarjetas(html: str) -> list[tuple[str, str]]:
    """(clases, contenido hasta la siguiente tarjeta) de cada stat-card."""
    trozos = re.split(r'(<div class="card stat-card[^"]*">)', html)
    return [(re.search(r'class="([^"]*)"', trozos[i]).group(1), trozos[i + 1]) for i in range(1, len(trozos) - 1, 2)]


def test_css_permite_fragmentar_tarjetas_largas_al_imprimir():
    """Con `break-inside: avoid` en todas las tarjetas, la del pronostico (39
    o 42 filas de ranking) no cabia en la primera pagina y el navegador la
    empujaba entera a la segunda, dejando la primera casi vacia. Las
    tarjetas largas deben poder fragmentarse; filas, avisos y titulos no."""
    impresion = _bloque_impresion()
    regla = re.search(r"body\.producto1-impresion \.stat-card\.impresion-fragmentable \{([^}]*)\}", impresion)
    assert regla and "break-inside: auto" in regla.group(1) and "page-break-inside: auto" in regla.group(1)
    assert impresion.index(".stat-card.impresion-fragmentable") > impresion.index("break-inside: avoid")
    evitar = re.search(r"(body\.producto1-impresion [^{]*)\{\s*break-inside: avoid;", impresion).group(1)
    assert "body.producto1-impresion tr" in evitar and "body.producto1-impresion .alert" in evitar
    assert "table-header-group" in impresion


@pytest.mark.parametrize("slug,ranking,filas", [("miloto", "Ranking de números", 39),
                                                 ("colorloto", "Ranking de pares", 42),
                                                 ("baloto", "Ranking de números", 43)])
def test_tarjetas_largas_del_detalle_son_fragmentables(cliente, entorno, slug, ranking, filas):
    codigo = {"miloto": "MILOTO", "colorloto": "COLORLOTO", "baloto": "BALOTO"}[slug]
    _generar(entorno, codigo, hasta={"MILOTO": 60, "COLORLOTO": 50, "BALOTO": 2200}[codigo])
    _generar(entorno, codigo)
    html = cliente.get(f"/pronosticos/{slug}").text
    assert '<body class="producto1-impresion">' in html
    largas = {"pronostico": ranking, "evaluacion": "Rendimiento histórico", "observados": "Resultados observados",
              "versiones": "Pronósticos guardados"}
    tarjetas = _tarjetas(html)
    for nombre, marca in largas.items():
        clases = [c for c, contenido in tarjetas if marca in contenido.split("</h6>")[0] or
                  (nombre == "pronostico" and marca in contenido)]
        assert clases and all("impresion-fragmentable" in c for c in clases), (nombre, clases)
    cuerpo_ranking = html.split(ranking, 1)[1].split("</tbody>", 1)[0]
    assert cuerpo_ranking.count("<tr") == filas + 1  # cabecera + filas completas
    assert "solo-impresion-bloque" in html


def test_sugerencia_se_imprime_antes_de_los_avisos(cliente, entorno):
    """En Carta horizontal, con historico desactualizado y resultado
    observado, los avisos largos desplazaban la combinacion de ColorLoto
    (y los numeros de MiLoto) a la segunda pagina. Al imprimir, la
    sugerencia va justo despues del objetivo; los avisos se conservan y
    la pantalla no cambia (solo `order` dentro de @media print)."""
    impresion = _bloque_impresion()
    for clase, orden in ((".impresion-cabecera", "-2"), (".impresion-sugerencia", "-1")):
        regla = re.search(r"body\.producto1-impresion " + re.escape(clase) + r" \{([^}]*)\}", impresion)
        assert regla and f"order: {orden};" in regla.group(1), clase
    pantalla = (RAIZ / "app" / "static" / "css" / "styles.css").read_text(encoding="utf-8").split("@media print {")[0]
    assert "impresion-sugerencia" not in pantalla and "impresion-cabecera" not in pantalla
    juegos, resultados, _, _, historicos = entorno
    for codigo, slug, hasta, marca in (("COLORLOTO", "colorloto", 50, "Combinación más probable"),
                                       ("MILOTO", "miloto", 60, "numero-bolita")):
        _generar(entorno, codigo, hasta=hasta)
        html = cliente.get(f"/pronosticos/{slug}").text
        tarjeta = html.split('<div class="card stat-card impresion-fragmentable p-3 h-100">', 1)[1]
        cabecera = tarjeta.index('class="d-flex justify-content-between impresion-cabecera"')
        sugerencia = tarjeta.index('<div class="impresion-sugerencia">')
        avisos = tarjeta.index("Simulación retrospectiva")  # el aviso sigue presente
        assert cabecera < avisos < sugerencia  # en el HTML (pantalla) el orden no cambia
        assert marca in tarjeta[sugerencia:sugerencia + 2500]
        assert tarjeta.count('class="impresion-sugerencia"') == 1


def test_h100_no_fija_la_altura_al_imprimir(cliente, entorno):
    """`h-100` fijaba la altura de la tarjeta a la de su columna, calculada
    antes de fragmentar: al imprimir, la tarjeta del ranking (y las del
    indice y las estadisticas) crecia mas que esa caja y la siguiente se
    pintaba encima (Trazabilidad tapaba las filas 38 y 39 de MiLoto en Carta
    vertical). Al imprimir, toda tarjeta `h-100` de producto toma la altura
    de su contenido; en pantalla `h-100` no cambia."""
    impresion = _bloque_impresion()
    regla = re.search(r"body\.producto1-impresion \.stat-card\.h-100 \{([^}]*)\}", impresion)
    assert regla and "height: auto !important;" in regla.group(1)
    pantalla = (RAIZ / "app" / "static" / "css" / "styles.css").read_text(encoding="utf-8").split("@media print {")[0]
    assert ".h-100" not in pantalla
    _generar(entorno, "MILOTO", hasta=60)
    _generar(entorno, "COLORLOTO", hasta=50)
    for url in ("/pronosticos", "/pronosticos/miloto", "/pronosticos/colorloto", "/estadisticas/colorloto/resumen"):
        html = cliente.get(url).text
        assert '<body class="producto1-impresion">' in html, url
        assert re.search(r'class="card stat-card[^"]*\bh-100\b', html), url  # la regla tiene a quien aplicarse


# ---------------------------------------------------------------------------
# Compatibilidad
# ---------------------------------------------------------------------------

def test_modulo_v1_y_almacen_sin_cambios():
    """El modulo de la linea v1 y la interfaz del almacen se conservan byte a
    byte. La implementacion del almacen cambio en Producto 3 (issue #83:
    publicacion con temporal y `os.link`); su compatibilidad con los
    artefactos existentes se prueba en `test_producto3_almacen.py`."""
    huellas = {
        "app/application/ml/pronostico_experimental.py":
            "5bd9bb544d6ae3ffe350b035370b37f3b96217a648c5ee6f0d276a61f5cfd17c",
        "app/application/interfaces/pronostico_experimental_store.py":
            "45ce749b6c162ae4f91eb288e1a7761d4584bb3b33b79a3a362d36c349c691d0",
    }
    for ruta, sha in huellas.items():
        contenido = (RAIZ / ruta).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(contenido).hexdigest() == sha, ruta


def test_artefacto_v1_se_lee_igual_y_se_compara(entorno):
    g = _generar(entorno, "BALOTO", hasta=2200)
    assert g.artefacto["esquema"] == "pronostico-experimental/1"
    ruta = next(entorno[3]._carpeta("BALOTO").glob("*.json"))
    antes = ruta.read_bytes()
    _comparar(entorno, "BALOTO")
    ConsultarPronosticosExperimentales(entorno[3]).resumen("BALOTO")
    assert ruta.read_bytes() == antes


def test_estructura_sin_nombres_reservados():
    archivos = [RAIZ / "app" / "api" / "web" / "routers" / "producto.py",
                RAIZ / "app" / "api" / "rest" / "routers" / "producto.py",
                RAIZ / "scripts" / "pronostico_experimental.py",
                *(RAIZ / "app" / "templates" / "producto").glob("*.html")]
    for ruta in archivos:
        texto = ruta.read_text(encoding="utf-8")
        for prohibido in ("resolver_estado_prediccion", "diagnostico_bloqueo", "registro_prospectivo",
                          "autorizacion_operativa", "reapertura", "prediccion_bloqueada"):
            assert prohibido not in texto, (ruta, prohibido)
