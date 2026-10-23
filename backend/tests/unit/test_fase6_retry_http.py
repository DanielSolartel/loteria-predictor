"""Contratos HTTP reales con sesión controlada, sin red ni esperas.

Se ejercita BaseConnector._get y requests.Response.raise_for_status: la
respuesta del proveedor debe llegar al planificador, no solo su texto.
"""
from __future__ import annotations

import pytest
import requests

from app.infrastructure.connectors.base_connector import ConectorFetchError
from tests.unit.connectors.test_base_connector import _ConectorDePrueba, _FakeHtmlStorage


class SesionControlada:
    def __init__(self, respuestas):
        self.headers = {}
        self.respuestas = iter(respuestas)
        self.llamadas = []

    def get(self, url, timeout):
        self.llamadas.append((url, timeout))
        return next(self.respuestas)


def respuesta(status, retry_after=None):
    r = requests.Response()
    r.status_code = status
    r.url = "https://fixture.invalid/resultados"
    r._content = b"respuesta sintetica"
    r.encoding = "utf-8"
    if retry_after is not None:
        r.headers["Retry-After"] = retry_after
    return r


def conector(respuestas):
    sesion = SesionControlada(respuestas)
    c = _ConectorDePrueba(_FakeHtmlStorage(), session=sesion,
                         max_reintentos=3, pausa_entre_peticiones=0)
    return c, sesion


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("retry_after", ["3600", "Wed, 21 Oct 2026 15:00:00 GMT"])
def test_retry_after_interrumpe_sin_reconsultar_y_conserva_respuesta(status, retry_after, monkeypatch):
    original = respuesta(status, retry_after)
    c, sesion = conector([original, respuesta(200)])
    esperas = []
    monkeypatch.setattr("app.infrastructure.connectors.base_connector.time.sleep", esperas.append)
    with pytest.raises(ConectorFetchError) as fallo:
        c._get(original.url)
    assert len(sesion.llamadas) == 1
    assert esperas == []
    assert fallo.value.response is original
    assert fallo.value.response.headers["Retry-After"] == retry_after
    assert isinstance(fallo.value.__cause__, requests.exceptions.HTTPError)


def test_error_http_terminal_conserva_respuesta_sin_reintentar():
    original = respuesta(404)
    c, sesion = conector([original])
    with pytest.raises(ConectorFetchError) as fallo:
        c._get(original.url)
    assert len(sesion.llamadas) == 1
    assert fallo.value.response is original


def test_agotamiento_5xx_sin_retry_after_conserva_ultimo_http_error():
    respuestas = [respuesta(503) for _ in range(3)]
    c, sesion = conector(respuestas)
    with pytest.raises(ConectorFetchError) as fallo:
        c._get(respuestas[0].url)
    assert len(sesion.llamadas) == 3
    assert fallo.value.response is respuestas[-1]
    assert isinstance(fallo.value.__cause__, requests.exceptions.HTTPError)


def test_5xx_sin_retry_after_conserva_recuperacion_historica():
    c, sesion = conector([respuesta(503), respuesta(200)])
    assert c._get("https://fixture.invalid/resultados") == "respuesta sintetica"
    assert len(sesion.llamadas) == 2
