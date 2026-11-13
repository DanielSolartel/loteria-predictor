from concurrent.futures import ThreadPoolExecutor
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies as dep
from app.api.publica import dependencias as lecturas
from app.application.interfaces.carteras_store import GuardadoCarteras
from app.application.use_cases.carteras import CarterasError
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination
from app.escritorio import crear_app
from app.escritorio_apuestas import RUTA_APUESTAS


ORIGEN = "http://127.0.0.1:18021"
ARRANQUE = "sesion-de-ensayo"
SORTEO = 7001
MARKOV, LIGHTGBM, COLORLOTO = (c * 64 for c in "abc")


def _cartera(clave, juego, modelo, combinacion):
    return GuardadoCarteras(clave, juego, "cartera", {
        "modelo": {"nombre": modelo, "id": modelo, "version": "v1"},
        "cartera": {"objetivo": SORTEO, "combinaciones": [{"linea": 1, **combinacion}]},
    })


def _solicitud(cartera, *juegos, sorteo=SORTEO):
    return {"solicitud": str(uuid4()), "cartera": cartera, "linea": 1, "sorteo": sorteo, "juegos": list(juegos)}


def _entrar(c):
    respuesta = c.post("/escritorio/sesion", headers={"Origin": ORIGEN, "X-Arranque-Escritorio": ARRANQUE})
    assert respuesta.status_code == 204


def _registrar(c, solicitud):
    respuesta = c.post(RUTA_APUESTAS, json=solicitud, headers={"Origin": ORIGEN})
    assert respuesta.status_code == 201, respuesta.json()
    assert respuesta.json() == {"id": solicitud["solicitud"]}


def _apuestas(c):
    respuesta = c.get(RUTA_APUESTAS)
    assert respuesta.status_code == 200, respuesta.json()
    return {a["id"]: a for a in respuesta.json()["apuestas"]}


@pytest.fixture
def entorno_apuestas(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    archivo = tmp_path / "apuestas.sqlite3"
    juegos = {
        codigo: Juego(uuid4(), codigo, codigo, 1, 43, 6 if color else 5, not color, 1 if not color else None,
                      16 if not color else None, color, color)
        for codigo, color in (("BALOTO", False), ("BALOTO_REVANCHA", False), ("COLORLOTO", True))
    }
    rojo, azul = Color("ROJO", "Rojo"), Color("AZUL", "Azul")

    def sorteo(codigo, combinacion):
        return Sorteo(uuid4(), juegos[codigo].id, SORTEO, date(2026, 1, 7), "miercoles", combinacion)

    resultados = {
        (juegos["BALOTO"].id, SORTEO): sorteo("BALOTO", Combination((3, 14, 23, 31, 42), 11)),
        (juegos["BALOTO_REVANCHA"].id, SORTEO): sorteo("BALOTO_REVANCHA", Combination((4, 14, 19, 35, 41), 7)),
        (juegos["COLORLOTO"].id, SORTEO): sorteo("COLORLOTO", Combination(pares=(
            ColorNumberPair(1, rojo), ColorNumberPair(1, rojo), ColorNumberPair(1, rojo),
            ColorNumberPair(3, rojo), ColorNumberPair(4, azul), ColorNumberPair(5, azul),
        ))),
    }
    carteras = {
        MARKOV: _cartera(MARKOV, "BALOTO", "Markov de orden uno", {"numeros": [3, 8, 14, 27, 40], "superbalota": 9}),
        LIGHTGBM: _cartera(LIGHTGBM, "BALOTO_REVANCHA", "LightGBM CPU", {"numeros": [5, 13, 21, 35, 39], "superbalota": 15}),
        COLORLOTO: _cartera(COLORLOTO, "COLORLOTO", "Modelo de prueba", {"pares": [
            [1, "ROJO"], [1, "ROJO"], [2, "AZUL"], [2, "AZUL"], [6, "AZUL"], [7, "ROJO"],
        ]}),
    }

    def cartera(clave):
        if clave not in carteras:
            raise CarterasError("no_encontrado", "cartera ausente")
        return carteras[clave]

    def construir_carteras(*, consultar_actividad):
        assert not consultar_actividad
        return SimpleNamespace(cartera=cartera)

    monkeypatch.setattr(dep, "construir_carteras", construir_carteras)
    monkeypatch.setattr(dep, "get_juego_repository", lambda _: SimpleNamespace(obtener_por_codigo=juegos.get))
    monkeypatch.setattr(dep, "get_sorteo_repository", lambda _: SimpleNamespace(
        obtener_por_numero=lambda juego, numero: resultados.get((juego, numero)),
    ))

    def abrir():
        app = crear_app(frontend=tmp_path, automatizacion=tmp_path / "auto", fecha_referencia=None,
                         puerto=18021, arranque=ARRANQUE, apuestas=archivo)
        app.dependency_overrides[lecturas.sesion_de_lectura] = lambda: object()
        return TestClient(app, base_url=ORIGEN, client=("127.0.0.1", 12345))

    return SimpleNamespace(abrir=abrir, archivo=archivo, carteras=carteras, resultados=resultados, juegos=juegos)


def test_jugadas_guardadas_persisten_al_reabrir(entorno_apuestas):
    e = entorno_apuestas
    baloto = _solicitud(MARKOV, "BALOTO")
    revancha = _solicitud(LIGHTGBM, "BALOTO_REVANCHA")
    with e.abrir() as c:
        _entrar(c)
        _registrar(c, baloto)
        _registrar(c, revancha)
    e.carteras.clear()
    original = e.archivo.read_bytes()
    with e.abrir() as c:
        _entrar(c)
        guardadas = _apuestas(c)
    assert len(guardadas) == 2
    for solicitud, modelo, combinacion, acertados in (
        (baloto, "Markov de orden uno", [3, 8, 14, 27, 40], [3, 14]),
        (revancha, "LightGBM CPU", [5, 13, 21, 35, 39], [35]),
    ):
        guardada = guardadas[solicitud["solicitud"]]
        assert guardada["combinacion"]["numeros"] == combinacion
        assert guardada["origen"]["modelo"] == modelo
        assert guardada["origen"]["cartera"] == solicitud["cartera"]
        assert guardada["origen"]["linea"] == 1
        p, = guardada["participaciones"]
        assert (p["juego"], p["sorteo"], p["aciertos"]) == (solicitud["juegos"][0], SORTEO, len(acertados))
        assert p["numeros_acertados"] == acertados and p["superbalota"] is False
    assert e.archivo.read_bytes() == original


def test_cruce_simulado_mantiene_el_origen_y_evalua_cada_sorteo(entorno_apuestas):
    e = entorno_apuestas
    solicitud = _solicitud(MARKOV, "BALOTO", "BALOTO_REVANCHA")
    clave = (e.juegos["BALOTO_REVANCHA"].id, SORTEO)
    resultado_revancha = e.resultados.pop(clave)
    with e.abrir() as c:
        _entrar(c)
        _registrar(c, solicitud)
        apuesta, = _apuestas(c).values()
        assert apuesta["origen"]["juego"] == "BALOTO" and apuesta["origen"]["modelo"] == "Markov de orden uno"
        baloto, revancha = apuesta["participaciones"]
        assert baloto["aciertos"] == 2 and baloto["numeros_acertados"] == [3, 14]
        assert revancha["estado"] == "pendiente" and revancha["aciertos"] is None
        e.resultados[clave] = resultado_revancha
        apuesta, = _apuestas(c).values()
        _, revancha = apuesta["participaciones"]
        assert revancha["estado"] == "evaluada"
        assert revancha["aciertos"] == 1 and revancha["numeros_acertados"] == [14]


def test_reintentos_concurrentes_guardan_una_sola_jugada(entorno_apuestas):
    e = entorno_apuestas
    solicitud = _solicitud(MARKOV, "BALOTO")
    with e.abrir() as c:
        _entrar(c)
        with ThreadPoolExecutor(max_workers=4) as hilos:
            list(hilos.map(lambda _: _registrar(c, solicitud), range(4)))
        assert list(_apuestas(c)) == [solicitud["solicitud"]]
        respuesta = c.post(RUTA_APUESTAS, json={**solicitud, "sorteo": SORTEO + 1}, headers={"Origin": ORIGEN})
        assert respuesta.status_code == 409
        _registrar(c, _solicitud(MARKOV, "BALOTO"))
        assert len(_apuestas(c)) == 2


def test_guardado_exige_sesion_origen_y_una_linea_valida(entorno_apuestas):
    e = entorno_apuestas
    solicitud = _solicitud(MARKOV, "BALOTO")
    with e.abrir() as c:
        assert c.get(RUTA_APUESTAS).status_code == 401
        assert c.post(RUTA_APUESTAS, json=solicitud, headers={"Origin": ORIGEN}).status_code == 401
        _entrar(c)
        assert c.post(RUTA_APUESTAS, json=solicitud).status_code == 403
        assert c.post(RUTA_APUESTAS, json=solicitud, headers={"Origin": "https://externo.example"}).status_code == 403
        assert c.delete(RUTA_APUESTAS).status_code == 405
        for cambio in ({"combinacion": [1, 2, 3, 4, 5]}, {"juegos": ["MILOTO"]}, {"linea": 2},
                       {"juegos": ["BALOTO", "BALOTO"]}):
            assert c.post(RUTA_APUESTAS, json={**solicitud, **cambio}, headers={"Origin": ORIGEN}).status_code == 422
        assert _apuestas(c) == {} and not e.archivo.exists()


def test_colorloto_cuenta_pares_con_multiplicidad(entorno_apuestas):
    with entorno_apuestas.abrir() as c:
        _entrar(c)
        _registrar(c, _solicitud(COLORLOTO, "COLORLOTO"))
        apuesta, = _apuestas(c).values()
        p, = apuesta["participaciones"]
        assert p["aciertos"] == 2 and p["superbalota"] is None and p["numeros_acertados"] is None
