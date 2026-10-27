"""Fase 9.3: explicacion guardada, clasificacion de candidatos y fiabilidad
observada en la API publica. Cada respuesta se compara con el caso de uso de la
Fase 4 (`CentroDePredicciones.consultar` y `.fiabilidad`) sobre el escenario
SINTETICO de `tests/fase9_api_sintetica.py` (cuatro juegos, version registrada,
series de Producto 6 sinteticas): la API proyecta campos publicos y no
recalcula, genera, entrena, infiere, importa ni escribe."""
from __future__ import annotations

import json

import pytest

from app.api.publica import dependencias as d
from app.api.publica import esquemas as e
from app.application.use_cases.laboratorio import EjecutorEnEsteProceso
from app.application.use_cases.predicciones import CentroDePredicciones
from app.application.use_cases.resultados import CentroDeResultados
from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso
from tests import fase9_api_sintetica as f9
from tests.unit import fixtures_fase4 as f4
from tests.unit.api_publica import fixtures_api_publica as fa

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")


@pytest.fixture(scope="module")
def escenario(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("f93")
    datos = f9.preparar(raiz / "a")
    centro = f9.centro_sintetico(datos)
    a = fa.api(raiz, centro=centro, entorno=datos["e7"], fichas_por_minuto=100_000)
    return datos, centro, a


def _sin_nulos_nuevos(api, uso, ruta: str = "") -> None:
    """Cada campo del caso de uso llega igual (en profundidad); los que anade el
    modelo publico (campos opcionales del contrato) llegan nulos."""
    if isinstance(uso, dict):
        assert isinstance(api, dict), ruta
        for clave, valor in uso.items():
            _sin_nulos_nuevos(api[clave], valor, f"{ruta}.{clave}")
        assert all(api[k] is None for k in set(api) - set(uso)), ruta
    elif isinstance(uso, list):
        assert isinstance(api, list) and len(api) == len(uso), ruta
        for i, (x, y) in enumerate(zip(api, uso)):
            _sin_nulos_nuevos(x, y, f"{ruta}[{i}]")
    else:
        assert api == uso, ruta


def _metrica_esperada(m: dict) -> dict:
    salida = {k: m.get(k) for k in e.MetricaDeFiabilidad.model_fields}
    salida["semilla"] = None if m.get("semilla") is None else str(m["semilla"])
    return salida


# ---------------------------------------------------------------------------
# Prediccion: rankings y explicacion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("juego", JUEGOS)
def test_rankings_y_explicacion_son_los_del_caso_de_uso(escenario, juego):
    _, centro, a = escenario
    r = a.get(f"/api/v1/juegos/{juego}/predicciones")
    assert r.status_code == 200
    p, uso = r.json()["prediccion"], centro.consultar(juego)["prediccion"]
    assert p["clave"] == uso["clave"] and p["corte"] == uso["datos"]["corte"]
    _sin_nulos_nuevos(p["rankings"], uso["rankings"], "rankings")  # mismos rankings, sin recalcular
    assert p["linea_de_modelo"] == uso["linea_de_modelo"]
    assert p["explicaciones_ilegibles"] == uso["explicaciones_ilegibles"]
    x, ux = p["explicacion"], uso["explicacion"]
    assert (x is None) == (ux is None) and p["explicacion_disponible"] == (ux is not None)
    if ux is not None:
        assert set(x) == set(e.Explicacion.model_fields)  # sin sello, contexto, juego ni rankings repetidos
        for clave in ("clave", "esquema", "version", "cartera", "avisos", "generacion", "variables"):
            assert x[clave] == ux[clave], clave
        _sin_nulos_nuevos(x["importancias"], ux["importancias"])
        for clave in ("modelo", "nombre", "version_de_la_receta", "perfil", "salida", "objetivo", "corte", "familia"):
            assert x["metodo"][clave] == ux["metodo"][clave], clave
        assert x["metodo"]["entrenamiento"]["estimador"] == ux["metodo"]["entrenamiento"]["estimador"]
        assert p["reproduccion"]["exacta"] is True and p["reproduccion"]["distintos"] == []


def test_baloto_registrada_superbalota_aparte_importancias_y_cortes_separados(escenario):
    datos, centro, a = escenario
    p = a.get("/api/v1/juegos/BALOTO/predicciones").json()["prediccion"]
    assert p["rankings"]["superbalota"]["universo"] == 16 and p["rankings"]["pares"] is None
    assert len(p["rankings"]["numeros"]["fuertes"]) == 10 and p["rankings"]["numeros"]["universo"] == 43
    x = p["explicacion"]
    assert x["importancias"]["estado"] == "disponible" and x["importancias"]["valores"]
    entrenamiento = x["metodo"]["entrenamiento"]["corte_de_entrenamiento"]
    assert entrenamiento == datos["e4"].corte("BALOTO") < p["corte"] == x["metodo"]["corte"]  # registrada antes
    assert x["metodo"]["registrado"]["corte_de_entrenamiento"] == entrenamiento
    assert p["registrado"] == {"clave": x["metodo"]["registrado"]["clave"], "numero": 1}


def test_colorloto_pares_numero_color_y_superbalota_ausente(escenario):
    _, _, a = escenario
    rk = a.get("/api/v1/juegos/COLORLOTO/predicciones").json()["prediccion"]["rankings"]
    assert rk["superbalota"] is None
    assert all(isinstance(f["candidato"], list) and isinstance(f["candidato"][0], int)
               and isinstance(f["candidato"][1], str) for f in rk["pares"]["todos"])
    assert all(f["multiplicidad_esperada"] is not None for f in rk["pares"]["todos"])
    assert all(isinstance(f["candidato"], int) for f in rk["numeros"]["todos"])
    assert all(isinstance(f["candidato"], str) for f in rk["colores"]["todos"])


def test_sin_explicacion_lo_informa_y_no_la_genera(escenario):
    datos, _, a = escenario
    antes = fa.arbol(datos["e4"].raiz)
    p = a.get("/api/v1/juegos/BALOTO_REVANCHA/predicciones").json()["prediccion"]
    assert p["explicacion"] is None and p["explicacion_disponible"] is False and p["reproduccion"] is None
    assert p["explicaciones_ilegibles"] == [] and p["rankings"]["numeros"]["todos"]
    assert fa.arbol(datos["e4"].raiz) == antes


def test_explicacion_alterada_no_se_muestra_y_se_informa_su_motivo(escenario):
    datos, _, a = escenario
    archivo = sorted((datos["e4"].raiz / "predicciones" / "explicaciones" / "MILOTO").glob("*.json"))[0]
    original = archivo.read_bytes()
    alterada = json.loads(original)
    alterada["importancias"]["motivo"] = "otro"
    from app.application.ml.registro_prospectivo import serializar_entrada
    archivo.write_bytes(serializar_entrada(alterada))
    try:
        r = a.get("/api/v1/juegos/MILOTO/predicciones")
        assert r.status_code == 200
        p = r.json()["prediccion"]
        assert p["explicacion"] is None and p["explicacion_disponible"] is False
        assert p["explicaciones_ilegibles"] == [{"clave": archivo.stem.split("-", 1)[1], "motivo": "contenido_alterado"}]
        assert p["rankings"] is not None  # la clasificacion sigue saliendo de la cartera verificada
    finally:
        archivo.write_bytes(original)


# ---------------------------------------------------------------------------
# Fiabilidad
# ---------------------------------------------------------------------------

def _compara_evaluacion(api: dict, uso: dict) -> None:
    assert api["tipo"] == uso["tipo"] and api["estado"] == uso["estado"] and api["motivo"] == uso.get("motivo")
    muestra = uso.get("muestra")
    if muestra is None:
        assert api["muestra"] is None
    else:
        for clave, valor in muestra.items():
            assert api["muestra"][clave] == valor, clave
    assert set(api["componentes"]) == set(uso.get("componentes") or {})
    for nombre, c in (uso.get("componentes") or {}).items():
        ac = api["componentes"][nombre]
        if "metricas" not in c:
            assert (ac["estado"], ac["motivo"], ac["metricas"]) == (c["estado"], c["motivo"], None)
            continue
        assert ac["sorteos"] == c["sorteos"] and ac["extremos"] == c.get("extremos")
        assert {k: v for k, v in ac["metricas"].items()} == {k: _metrica_esperada(m) for k, m in c["metricas"].items()}


@pytest.mark.parametrize("juego", JUEGOS)
@pytest.mark.parametrize("con_corte", [False, True])
def test_fiabilidad_es_la_del_caso_de_uso_con_y_sin_corte(escenario, juego, con_corte):
    _, centro, a = escenario
    hasta = centro.consultar(juego)["prediccion"]["datos"]["corte"] if con_corte else None
    r = a.get(f"/api/v1/juegos/{juego}/fiabilidad" + (f"?hasta={hasta}" if hasta else ""))
    assert r.status_code == 200
    f, uso = r.json(), centro.fiabilidad(juego, hasta=hasta)
    assert f["hasta"] == hasta and f["metodo"] == uso["metodo"] and f["contexto"] == uso["contexto"]
    assert f["estado_de_uso"] == "experimental_no_acreditado" and f["aviso"] == uso["aviso"]
    assert f["contexto"]["AUTORIZA_EVALUACION"] is False and f["contexto"]["no_go_ae39"] == "vigente"
    assert f["configuracion"] == uso["configuracion"]["estado"]
    assert f["base"] == {k: uso["base"][k] for k in ("estado", "ultimo_sorteo", "fecha", "sorteos")}
    assert [l["linea"] for l in f["lineas"]] == [l["linea"] for l in uso["lineas"]]
    for la, lu in zip(f["lineas"], uso["lineas"]):
        assert (la["papel"], la["nombre"], la["estimador"]) == (lu["papel"], lu["nombre"], lu["estimador"])
        assert [x["tipo"] for x in la["evaluaciones"]] == ["seguimiento", "retrospectiva"]
        for ea, eu in zip(la["evaluaciones"], lu["evaluaciones"]):
            _compara_evaluacion(ea, eu)
    _compara_evaluacion(f["receta"], uso["receta"])
    assert f["receta"]["tipo"] == "evaluacion_de_receta"


def test_la_evidencia_al_corte_de_cada_cartera_excluye_los_resultados_posteriores(escenario):
    _, _, a = escenario
    historial = a.get("/api/v1/juegos/BALOTO/predicciones").json()["historial"]
    assert [h["corte"] for h in historial] == sorted((h["corte"] for h in historial), reverse=True)
    todos = a.get("/api/v1/juegos/BALOTO/fiabilidad").json()["lineas"][0]["evaluaciones"][0]["muestra"]
    vistos = []
    for h in historial:
        p = a.get(f"/api/v1/juegos/BALOTO/predicciones?cartera={h['clave']}").json()["prediccion"]
        assert p["clave"] == h["clave"] and p["corte"] == h["corte"]
        m = a.get(f"/api/v1/juegos/BALOTO/fiabilidad?hasta={p['corte']}").json()["lineas"][0]["evaluaciones"][0]["muestra"]
        assert m["hasta"] == p["corte"] and m["periodo"][1] <= p["corte"]
        vistos.append(m["sorteos"])
    assert vistos == sorted(vistos, reverse=True) and len(set(vistos)) == len(vistos)  # cada corte, su evidencia
    assert todos["sorteos"] >= vistos[0] and todos["pendientes"] == 1  # el objetivo de la ultima, pendiente


def test_estados_diferencias_de_signo_intervalos_y_exclusiones(escenario):
    _, _, a = escenario
    f = a.get("/api/v1/juegos/BALOTO/fiabilidad").json()
    carteras, laboratorio = f["lineas"]
    seg, ret = carteras["evaluaciones"]
    dll = seg["componentes"]["numeros"]["metricas"]["diferencia_log_loss"]
    assert seg["estado"] == "estimable" and dll["media"] > 0 and dll["intervalo"][0] > 0
    assert "mayor pérdida" in dll["lectura"] and "No acredita ventaja futura" in dll["lectura"]
    assert {"estado": "excluido", "motivo": "vectores_fuente_distintos_en_el_objetivo", "emisiones": 2} in \
        seg["muestra"]["exclusiones"]
    assert set(seg["componentes"]) == {"numeros", "superbalota"}
    corta = ret["componentes"]["numeros"]["metricas"]["diferencia_log_loss"]
    assert ret["estado"] == "muestra_insuficiente" and corta["intervalo"] is None and corta["semilla"] is None
    menor = laboratorio["evaluaciones"][0]["componentes"]["numeros"]["metricas"]["diferencia_log_loss"]
    assert menor["media"] < 0 and menor["intervalo"][1] < 0 and "menor pérdida" in menor["lectura"]
    cruza = laboratorio["evaluaciones"][1]["componentes"]["numeros"]["metricas"]["diferencia_log_loss"]
    assert cruza["intervalo"][0] < 0 < cruza["intervalo"][1] and "incluye 0" in cruza["lectura"]
    assert isinstance(dll["semilla"], str) and int(dll["semilla"]) >= 0
    assert f["receta"]["componentes"]["superbalota"]["estado"] == "no_disponible"
    nulo = a.get("/api/v1/juegos/COLORLOTO/fiabilidad").json()["lineas"][0]["evaluaciones"][0]
    assert set(nulo["componentes"]) == {"pares"}
    assert nulo["componentes"]["pares"]["metricas"]["diferencia_log_loss"]["intervalo"] == [0.0, 0.0]
    pendiente = a.get("/api/v1/juegos/BALOTO_REVANCHA/fiabilidad").json()["lineas"][0]["evaluaciones"][0]
    assert pendiente["estado"] == "sin_resultados" and pendiente["muestra"]["pendientes"] == 1
    sin = a.get("/api/v1/juegos/MILOTO/fiabilidad?hasta=87").json()["lineas"][0]["evaluaciones"][0]
    assert sin["estado"] == "sin_datos" and sin["componentes"] == {}
    texto = json.dumps(f, ensure_ascii=False).lower()
    assert "nivel_confianza" not in texto and "probabilidad de premio" not in texto


def test_base_caida_informa_sin_base_sin_su_motivo(escenario):
    datos, _, a = escenario
    datos["e4"].base_caida = True
    try:
        r = a.get("/api/v1/juegos/MILOTO/fiabilidad")
        p = a.get("/api/v1/juegos/MILOTO/predicciones")
    finally:
        datos["e4"].base_caida = False
    assert r.status_code == 200 and p.status_code == 200
    f = r.json()
    assert f["base"] == {"estado": "no_disponible", "ultimo_sorteo": None, "fecha": None, "sorteos": None}
    assert f["lineas"][0]["evaluaciones"][0]["estado"] == "sin_base"
    for texto in (r.text, p.text):
        assert "Connection refused" not in texto and "connection to server" not in texto
    assert p.json()["prediccion"]["clave"]  # lo guardado se sigue consultando


def test_un_fallo_de_calculo_no_expone_el_detalle_interno(escenario, monkeypatch):
    datos, centro, a = escenario
    series = {j: [dict(x) for x in filas] for j, filas in datos["series"].items()}
    roto = dict(series["COLORLOTO"][0], metricas={"log_loss": 1.0})  # falta brier: KeyError interno
    series["COLORLOTO"][0] = roto
    otro = datos["e4"].centro()
    otro._resultados = f9.ResultadosConSeries(otro._resultados, series)
    a.app.dependency_overrides[d.centro_de_predicciones] = lambda: otro
    try:
        f = a.get("/api/v1/juegos/COLORLOTO/fiabilidad").json()
    finally:
        a.app.dependency_overrides[d.centro_de_predicciones] = lambda: centro
    ev = f["lineas"][0]["evaluaciones"][0]
    assert ev["estado"] == "fallo_de_calculo" and ev["motivo"] == "no se pudieron calcular las cifras; el detalle queda en " \
                                                                   "la consola local"
    assert "brier" not in json.dumps(ev)


@pytest.mark.parametrize("consulta", ["hasta=0", "hasta=-3", "hasta=abc", "hasta=1.5"])
def test_corte_no_valido_es_422_sin_tocar_el_caso_de_uso(escenario, monkeypatch, consulta):
    _, _, a = escenario
    llamadas = []
    monkeypatch.setattr(CentroDePredicciones, "fiabilidad", lambda *x, **k: llamadas.append(x))
    r = a.get(f"/api/v1/juegos/BALOTO/fiabilidad?{consulta}")
    assert r.status_code == 422 and r.json()["error"]["codigo"] == "parametro_no_valido" and llamadas == []


def test_juego_desconocido_es_404(escenario):
    _, _, a = escenario
    r = a.get("/api/v1/juegos/QUINELA/fiabilidad")
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "no_encontrado"


def test_cuesta_tres_fichas_y_sin_clave_es_401(tmp_path):
    e4 = f4.entorno(tmp_path / "f4")
    e4.configurar("MILOTO", "uniforme")
    a = fa.api(tmp_path, centro=e4.centro(), fichas_por_minuto=5)
    assert a.get("/api/v1/juegos/MILOTO/fiabilidad").status_code == 200
    r = a.get("/api/v1/juegos/MILOTO/fiabilidad")
    assert r.status_code == 429 and r.json()["error"]["codigo"] == "limite_excedido" and int(r.headers["retry-after"]) > 0
    assert a.cliente().get("/api/v1/juegos/MILOTO/fiabilidad").status_code == 401


def test_sin_configuracion_responde_sin_lineas(tmp_path):
    a = fa.api(tmp_path, centro=f4.entorno(tmp_path / "f4").centro())
    f = a.get("/api/v1/juegos/BALOTO/fiabilidad").json()
    assert f["configuracion"] == "sin_configuracion" and f["lineas"] == [] and f["registrado"] is None
    assert f["receta"]["estado"] == "sin_datos" and f["receta"]["muestra"] is None


def test_proyeccion_publica_sin_campos_internos_ni_motivos_de_la_base(escenario):
    datos, centro, a = escenario
    f = a.get("/api/v1/juegos/BALOTO/fiabilidad").json()
    assert set(f) == set(e.Fiabilidad.model_fields)
    assert set(f["base"]) == {"estado", "ultimo_sorteo", "fecha", "sorteos"}
    assert set(f["registrado"]) == {"clave", "numero", "estado"}
    assert "lineas_disponibles" not in f and "linea_consultada" not in f
    p = a.get("/api/v1/juegos/BALOTO/predicciones").json()["prediccion"]
    assert set(p) == set(e.Prediccion.model_fields)
    for texto in (json.dumps(f), json.dumps(p)):
        assert str(datos["e4"].raiz) not in texto and "Traceback" not in texto


def test_tamano_de_las_respuestas_frente_al_limite_de_la_pasarela(escenario):
    from app.pasarela.cliente import MAXIMO_BYTES

    _, _, a = escenario
    for j in JUEGOS:
        for url in (f"/api/v1/juegos/{j}/predicciones?historial=50", f"/api/v1/juegos/{j}/fiabilidad"):
            assert len(a.get(url).content) < MAXIMO_BYTES / 20, url


def test_las_consultas_no_escriben_ni_ejecutan_trabajadores(escenario, monkeypatch):
    datos, centro, a = escenario
    llamadas = []
    for clase, metodos in ((CentroDePredicciones, ("iniciar", "ejecutar", "ahora", "explicar", "abortar")),
                           (EjecutorEnEsteProceso, ("explicacion_registrada",)),
                           (EjecutorEnProceso, ("explicacion_registrada",)),
                           (CentroDeResultados, ("guardar_informe", "usar_configuracion"))):
        for metodo in metodos:
            def prohibido(*x, _n=f"{clase.__name__}.{metodo}", **k):
                llamadas.append(_n)
                raise AssertionError(_n)
            monkeypatch.setattr(clase, metodo, prohibido)
    almacenes, filas = fa.arbol(datos["e4"].raiz), fa.filas(datos["e7"])
    for j in JUEGOS:
        historial = a.get(f"/api/v1/juegos/{j}/predicciones").json()["historial"]
        for h in historial:
            p = a.get(f"/api/v1/juegos/{j}/predicciones?cartera={h['clave']}").json()["prediccion"]
            assert a.get(f"/api/v1/juegos/{j}/fiabilidad?hasta={p['corte']}").status_code == 200
        assert a.get(f"/api/v1/juegos/{j}/fiabilidad").status_code == 200
    assert llamadas == []
    assert fa.arbol(datos["e4"].raiz) == almacenes and fa.filas(datos["e7"]) == filas
