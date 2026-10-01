"""Producto 1, correcciones del flujo real (regresiones escritas antes de
corregir):

1. Clasificacion temporal: simulacion retrospectiva si el objetivo ya
   figura en la base; pronostico sobre el ultimo dato disponible si el
   objetivo es el siguiente al ultimo sorteo cargado (sin afirmar que es
   futuro); aviso visible de historico desactualizado.
2. Idempotencia: mismo juego, corte, historico, configuracion y version
   devuelven el primer artefacto (sin reentrenar ni cambiar su fecha);
   un historico corregido crea otra version sin sobrescribir.
3. Acceso: el entrenamiento y la verificacion solo se disparan desde la
   propia maquina, con token del formulario y sin origen ajeno.

Historicos sinteticos."""
from __future__ import annotations

import dataclasses
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.application.ml import pronostico_experimental as pe
from app.application.use_cases.pronostico_experimental import GenerarPronosticoExperimental
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx

CONFIG = pe.ConfiguracionExperimental(tamano_bloque=10, bloques_de_evaluacion=2, minimo_objetivos_de_entrenamiento=40)
LOCAL = ("127.0.0.1", 50000)


def _reloj(dia: int):
    return lambda: datetime(2026, 10, dia, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def entorno(tmp_path):
    historicos = {"BALOTO": fx.historico_numerico("BALOTO", 130),
                  "BALOTO_REVANCHA": fx.historico_numerico("BALOTO_REVANCHA", 130)}
    juegos, resultados, colores = fx.repositorios(historicos, colorloto=[])
    almacen = PronosticoExperimentalFileStore(tmp_path / "pronosticos")
    return juegos, resultados, colores, almacen, historicos


def _caso(entorno, reloj=_reloj(1)):
    juegos, resultados, _, almacen, _ = entorno
    return GenerarPronosticoExperimental(juegos, resultados, almacen, reloj=reloj, configuracion=CONFIG)


def _archivos(entorno, codigo="BALOTO"):
    carpeta = entorno[3]._carpeta(codigo)
    return sorted(p.name for p in carpeta.glob("*.json")) if carpeta.is_dir() else []


# ---------------------------------------------------------------------------
# 1. Clasificacion temporal
# ---------------------------------------------------------------------------

def test_objetivo_en_la_base_es_simulacion_retrospectiva(entorno):
    g = _caso(entorno).ejecutar("BALOTO", hasta_numero_sorteo=2200)
    c = g.artefacto["generacion"]["clasificacion_temporal"]
    assert c["tipo"] == "simulacion_retrospectiva"
    assert c["objetivo"] == 2201 and c["objetivo_en_la_base"] is True and c["ultimo_sorteo_disponible"] == 2210
    real = next(r for r in entorno[4]["BALOTO"] if r.numero_sorteo == 2201)
    observado = c["resultado_observado"]
    assert observado["numeros"] == list(real.numeros)
    assert observado["aciertos_numeros_sugeridos"] == len(set(real.numeros)
                                                         & set(g.artefacto["pronostico"]["numeros_sugeridos"]))
    assert g.artefacto["datos"]["corte"] == 2200


def test_objetivo_siguiente_al_ultimo_dato_no_se_llama_futuro(entorno):
    g = _caso(entorno).ejecutar("BALOTO")
    c = g.artefacto["generacion"]["clasificacion_temporal"]
    assert c["tipo"] == "pronostico_sobre_el_ultimo_dato_disponible"
    assert c["objetivo_en_la_base"] is False and c["ultimo_sorteo_disponible"] == 2210
    assert "siguiente al ultimo sorteo cargado" in c["descripcion"]
    assert "no prueba que el sorteo no se haya celebrado" in c["descripcion"]
    assert "futuro" not in json.dumps(g.artefacto, ensure_ascii=False).lower()


def test_objetivo_ausente_con_sorteos_posteriores(entorno):
    juegos, resultados, _, _, historicos = entorno
    baloto = juegos.obtener_por_codigo("BALOTO").id
    resultados.numericos[baloto] = [r for r in historicos["BALOTO"] if r.numero_sorteo != 2201]
    g = _caso(entorno).ejecutar("BALOTO", hasta_numero_sorteo=2200)
    c = g.artefacto["generacion"]["clasificacion_temporal"]
    assert c["tipo"] == "objetivo_no_cargado_con_sorteos_posteriores" and c["objetivo_en_la_base"] is False


def test_historico_desactualizado_produce_aviso(entorno):
    ultima = entorno[4]["BALOTO"][-1].fecha
    viejo = _caso(entorno, reloj=lambda: datetime.combine(ultima + timedelta(days=40), datetime.min.time(),
                                                           tzinfo=timezone.utc)).ejecutar("BALOTO")
    f = viejo.artefacto["generacion"]["frescura"]
    assert f["estado"] == "desactualizado" and f["dias_desde_el_ultimo_sorteo"] == 40
    assert "desactualizado" in f["mensaje"]


def test_historico_al_dia_sin_aviso(entorno):
    ultima = entorno[4]["BALOTO"][-1].fecha
    g = _caso(entorno, reloj=lambda: datetime.combine(ultima + timedelta(days=2), datetime.min.time(),
                                                       tzinfo=timezone.utc)).ejecutar("BALOTO")
    assert g.artefacto["generacion"]["frescura"]["estado"] == "al_dia"


# ---------------------------------------------------------------------------
# 2. Idempotencia y versiones
# ---------------------------------------------------------------------------

def test_dos_ejecuciones_identicas_devuelven_el_primer_artefacto(entorno, monkeypatch):
    primero = _caso(entorno, reloj=_reloj(1)).ejecutar("BALOTO")
    assert primero.reutilizado is False
    llamadas = []
    original = pe.generar_pronostico
    monkeypatch.setattr(pe, "generar_pronostico", lambda *a, **k: llamadas.append(1) or original(*a, **k))
    segundo = _caso(entorno, reloj=_reloj(9)).ejecutar("BALOTO")
    assert segundo.reutilizado is True and llamadas == []
    assert segundo.identificador == primero.identificador and segundo.artefacto == primero.artefacto
    assert segundo.artefacto["generacion"]["generado_en"] == "2026-10-01T12:00:00+00:00"
    assert len(_archivos(entorno)) == 1


def test_historico_corregido_crea_otra_version_para_el_mismo_objetivo(entorno):
    juegos, resultados, _, almacen, historicos = entorno
    v1 = _caso(entorno, reloj=_reloj(1)).ejecutar("BALOTO")
    baloto = juegos.obtener_por_codigo("BALOTO").id
    corregido = dataclasses.replace(historicos["BALOTO"][5], numeros=(1, 2, 3, 4, 5))
    resultados.numericos[baloto] = [*historicos["BALOTO"][:5], corregido, *historicos["BALOTO"][6:]]
    v2 = _caso(entorno, reloj=_reloj(2)).ejecutar("BALOTO")
    assert v2.identificador != v1.identificador and v2.reutilizado is False
    assert v2.artefacto["pronostico"]["objetivo"] == v1.artefacto["pronostico"]["objetivo"]
    assert len(_archivos(entorno)) == 2
    from app.application.use_cases.pronostico_experimental import ConsultarPronosticosExperimentales
    r = ConsultarPronosticosExperimentales(almacen).resumen("BALOTO")
    assert [(g.identificador, g.version, g.versiones) for g in r.guardados] == [
        (v2.identificador, 2, 2), (v1.identificador, 1, 2)]
    assert r.ultimo.identificador == v2.identificador


def test_alteracion_sigue_detectandose(entorno):
    g = _caso(entorno).ejecutar("BALOTO")
    ruta = next(entorno[3]._carpeta("BALOTO").glob("*.json"))
    datos = json.loads(ruta.read_bytes())
    datos["generacion"]["generado_en"] = "2020-01-01T00:00:00+00:00"
    ruta.write_bytes(json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode() + b"\n")
    from app.application.interfaces.pronostico_experimental_store import PronosticoIlegible
    assert isinstance(entorno[3].obtener("BALOTO", g.identificador), PronosticoIlegible)
    with pytest.raises(Exception):
        _caso(entorno).ejecutar("BALOTO")
    assert ruta.read_bytes().count(b"2020-01-01") == 1


# ---------------------------------------------------------------------------
# Pantallas: clasificacion, versiones y doble clic
# ---------------------------------------------------------------------------

def _cliente(entorno, reloj=_reloj(1), client=LOCAL):
    juegos, resultados, colores, almacen, _ = entorno
    return fx.cliente(juegos, resultados, colores, almacen, reloj=reloj, configuracion=CONFIG, client=client)


@pytest.fixture
def limpiar():
    yield
    from app.main import app
    app.dependency_overrides = {}


def _token(c, slug="baloto") -> str:
    m = re.search(r'name="token_local" value="([^"]+)"', c.get(f"/pronosticos/{slug}").text)
    assert m, "el formulario debe llevar el token local"
    return m.group(1)


def test_doble_clic_web_devuelve_el_mismo_pronostico(entorno, limpiar):
    c = _cliente(entorno)
    token = _token(c)
    r1 = c.post("/pronosticos/baloto/generar", data={"token_local": token}, follow_redirects=False)
    r2 = c.post("/pronosticos/baloto/generar", data={"token_local": token}, follow_redirects=False)
    assert r1.status_code == r2.status_code == 303
    assert r1.headers["location"].split("&")[0] == r2.headers["location"].split("&")[0]
    assert len(_archivos(entorno)) == 1
    assert "ya existía" in c.get(r2.headers["location"]).text


def test_pantallas_y_api_muestran_la_clasificacion(entorno, limpiar):
    c = _cliente(entorno)
    token = _token(c)
    replay = c.post("/pronosticos/baloto/generar", data={"token_local": token, "hasta_numero_sorteo": "2200"},
                    follow_redirects=False).headers["location"]
    texto = c.get(replay).text
    assert "Simulación retrospectiva" in texto and "Resultado observado" in texto
    actual = c.post("/pronosticos/baloto/generar", data={"token_local": token},
                    follow_redirects=False).headers["location"]
    texto = c.get(actual).text
    assert "siguiente al último sorteo cargado" in texto and "desactualizado" in texto.lower()
    assert "futuro" not in texto.lower()
    j = c.get("/api/pronosticos/BALOTO").json()
    tipos = {g["clasificacion_temporal"] for g in j["guardados"]}
    assert tipos == {"simulacion_retrospectiva", "pronostico_sobre_el_ultimo_dato_disponible"}
    assert j["ultimo"]["estado_actual"]["clasificacion_temporal"]["tipo"] in tipos
    assert j["ultimo"]["estado_actual"]["frescura"]["estado"] == "desactualizado"


def test_pantalla_de_versiones(entorno, limpiar):
    juegos, resultados, _, _, historicos = entorno
    c = _cliente(entorno)
    token = _token(c)
    v1 = c.post("/pronosticos/baloto/generar", data={"token_local": token}, follow_redirects=False).headers["location"]
    baloto = juegos.obtener_por_codigo("BALOTO").id
    resultados.numericos[baloto] = [dataclasses.replace(historicos["BALOTO"][0], numeros=(1, 2, 3, 4, 5)),
                                    *historicos["BALOTO"][1:]]
    v2 = c.post("/pronosticos/baloto/generar", data={"token_local": token}, follow_redirects=False).headers["location"]
    assert v1 != v2
    assert "versión 2 de 2" in c.get(v2).text.lower()
    assert "versión 1 de 2" in c.get(v1).text.lower()


# ---------------------------------------------------------------------------
# 3. Acceso al entrenamiento y a la verificacion
# ---------------------------------------------------------------------------

def test_peticion_externa_no_puede_entrenar(entorno, limpiar):
    externo = _cliente(entorno, client=("203.0.113.7", 40000))
    token = _token(_cliente(entorno))
    r = externo.post("/pronosticos/baloto/generar", data={"token_local": token}, follow_redirects=False)
    assert r.status_code == 403 and _archivos(entorno) == []


@pytest.mark.parametrize("cabeceras", [
    {"Origin": "http://sitio-ajeno.example"},
    {"Sec-Fetch-Site": "cross-site"},
    {"Host": "atacante.example"},
    {"Referer": "http://sitio-ajeno.example/pagina"},
])
def test_origen_ajeno_no_puede_entrenar(entorno, limpiar, cabeceras):
    c = _cliente(entorno)
    token = _token(c)
    r = c.post("/pronosticos/baloto/generar", data={"token_local": token}, headers=cabeceras, follow_redirects=False)
    assert r.status_code == 403 and _archivos(entorno) == []


def test_sin_token_o_con_token_falso_no_entrena(entorno, limpiar):
    c = _cliente(entorno)
    assert c.post("/pronosticos/baloto/generar", data={}, follow_redirects=False).status_code == 403
    assert c.post("/pronosticos/baloto/generar", data={"token_local": "x" * 43},
                  follow_redirects=False).status_code == 403
    assert _archivos(entorno) == []


def test_mismo_origen_local_puede_entrenar(entorno, limpiar):
    c = _cliente(entorno)
    token = _token(c)
    r = c.post("/pronosticos/baloto/generar", data={"token_local": token},
               headers={"Origin": "http://localhost:8000", "Sec-Fetch-Site": "same-origin"}, follow_redirects=False)
    assert r.status_code == 303


def test_verificar_por_get_no_reentrena(entorno, limpiar, monkeypatch):
    g = _caso(entorno).ejecutar("BALOTO")
    llamadas = []
    monkeypatch.setattr(pe, "generar_pronostico", lambda *a, **k: llamadas.append(1))
    c = _cliente(entorno)
    r = c.get(f"/pronosticos/baloto/verificar?id={g.identificador}")
    assert r.status_code == 200 and llamadas == [] and 'name="token_local"' in r.text
    externo = _cliente(entorno, client=("203.0.113.7", 40000))
    token = re.search(r'name="token_local" value="([^"]+)"', r.text).group(1)
    assert externo.post("/pronosticos/baloto/verificar", data={"id": g.identificador, "token_local": token}
                        ).status_code == 403 and llamadas == []


def test_verificar_por_post_local(entorno, limpiar):
    g = _caso(entorno).ejecutar("BALOTO")
    c = _cliente(entorno)
    token = _token(c)
    r = c.post("/pronosticos/baloto/verificar", data={"id": g.identificador, "token_local": token})
    assert r.status_code == 200 and "Huella de reproducción idéntica: <strong>sí" in r.text


def test_un_entrenamiento_a_la_vez(entorno, limpiar):
    from app.api.web import proteccion_local
    c = _cliente(entorno)
    token = _token(c)
    assert proteccion_local.CERROJO_DE_ENTRENAMIENTO.acquire(blocking=False)
    try:
        r = c.post("/pronosticos/baloto/generar", data={"token_local": token}, follow_redirects=False)
        assert r.status_code == 429
    finally:
        proteccion_local.CERROJO_DE_ENTRENAMIENTO.release()
    assert _archivos(entorno) == []


def test_comando_muestra_clasificacion_y_reutiliza(entorno):
    import contextlib
    import io

    from scripts import pronostico_experimental as cli
    juegos, resultados, _, almacen, _ = entorno

    @contextlib.contextmanager
    def repos():
        yield juegos, resultados

    def correr(argv, dia):
        salida = io.StringIO()
        codigo = cli.ejecutar(argv, repositorios=repos, almacen_factory=lambda: almacen, reloj=_reloj(dia),
                              configuracion=CONFIG, salida=salida, errores=io.StringIO())
        return codigo, json.loads(salida.getvalue())

    codigo, replay = correr(["entrenar", "--juego", "BALOTO", "--hasta-sorteo", "2200"], 1)
    assert codigo == 0 and replay["clasificacion_temporal"]["tipo"] == "simulacion_retrospectiva"
    assert replay["reutilizado"] is False and replay["frescura"]["estado"] == "desactualizado"
    codigo, otra_vez = correr(["entrenar", "--juego", "BALOTO", "--hasta-sorteo", "2200"], 5)
    assert otra_vez["reutilizado"] is True and otra_vez["identificador"] == replay["identificador"]
    assert otra_vez["generado_en"] == replay["generado_en"] and len(_archivos(entorno)) == 1
    codigo, actual = correr(["entrenar", "--juego", "BALOTO"], 1)
    assert actual["clasificacion_temporal"]["tipo"] == "pronostico_sobre_el_ultimo_dato_disponible"
    codigo, lista = correr(["listar", "--juego", "BALOTO"], 1)
    assert [g["clasificacion_temporal"]["tipo"] for g in lista["guardados"]] == [
        "pronostico_sobre_el_ultimo_dato_disponible", "simulacion_retrospectiva"]
