"""Fase 8 v2, F8-SEC-01: un fallo inesperado se convierte DENTRO de la entrada
publica en un 500 sanitizado. No llega al servidor (que imprimiria su traza y
su mensaje), conserva `X-Request-ID` coherente con el cuerpo y `no-store`, se
anota una sola vez en el monitoreo y no registra mensaje, traza ni entradas.
Los manejadores especificos siguen igual y las cancelaciones y salidas del
proceso no se capturan."""
from __future__ import annotations

import asyncio
import logging
import re

import pytest
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from app.api.publica import dependencias as d
from app.api.publica.monitoreo import MiddlewarePublico
from app.application.exceptions import DominioError
from tests.unit.api_publica import fixtures_api_publica as fa

CANARIO = "F8_CANARIO_SINTETICO /home/operador/.env DATABASE_URL=postgresql://u:p@host/db"
URL = "/api/v1/juegos/MILOTO/simulaciones"
PLANTILLA = "/api/v1/juegos/{codigo}/simulaciones"


def _que_falla(excepcion: BaseException):
    def falla():
        raise excepcion
    return falla


def _fugas(caplog) -> dict[str, bool]:
    texto = caplog.text + "".join(str(x.args) for x in caplog.records)
    return {"canario": "F8_CANARIO" in texto or "postgresql" in texto, "traza": "Traceback" in texto,
            "exc_info": any(x.exc_info for x in caplog.records)}


def test_el_error_inesperado_no_llega_al_servidor_y_conserva_correlacion(tmp_path, caplog):
    a = fa.api(tmp_path)
    a.app.dependency_overrides[d.simulaciones] = _que_falla(RuntimeError(CANARIO))
    with caplog.at_level(logging.DEBUG):  # todos los registradores, no solo app.api.publica
        r = a.cliente(raise_server_exceptions=True).get(URL, headers=a.cabeceras())  # v1: llegaba al servidor
    cuerpo = r.json()
    assert r.status_code == 500 and set(cuerpo) == {"error"} and cuerpo["error"]["codigo"] == "error_interno"
    assert re.fullmatch("[0-9a-f]{32}", r.headers["X-Request-ID"])
    assert cuerpo["error"]["solicitud"] == r.headers["X-Request-ID"] and r.headers["Cache-Control"] == "no-store"
    assert "F8_CANARIO" not in r.text and "postgresql" not in r.text
    fugas = _fugas(caplog)
    assert not any(fugas.values()), fugas
    assert f"error_interno=RuntimeError solicitud={r.headers['X-Request-ID']}" in caplog.text


def test_el_error_inesperado_se_anota_una_sola_vez(tmp_path):
    a = fa.api(tmp_path)
    a.app.dependency_overrides[d.simulaciones] = _que_falla(RuntimeError(CANARIO))
    assert a.cliente(raise_server_exceptions=False).get(URL, headers=a.cabeceras()).status_code == 500
    estado = a.app.state.monitor.resumen()
    fila = next(r for r in estado["rutas"] if r["ruta"] == PLANTILLA)
    assert (fila["solicitudes"], fila["errores_5xx"], estado["por_clase"]) == (1, 1, {"5xx": 1})


@pytest.mark.parametrize("excepcion, estado, codigo", [
    (DominioError(CANARIO), 500, "error_interno"),
    (OperationalError("SELECT 1", {}, Exception(CANARIO)), 503, "base_no_disponible"),
])
def test_los_manejadores_especificos_se_conservan(tmp_path, caplog, excepcion, estado, codigo):
    a = fa.api(tmp_path)
    a.app.dependency_overrides[d.simulaciones] = _que_falla(excepcion)
    with caplog.at_level(logging.DEBUG):
        r = a.cliente().get(URL, headers=a.cabeceras())
    assert r.status_code == estado and r.json()["error"]["codigo"] == codigo
    assert r.json()["error"]["solicitud"] == r.headers["X-Request-ID"] and r.headers["Cache-Control"] == "no-store"
    fugas = _fugas(caplog)
    assert not any(fugas.values()), fugas
    assert f"={type(excepcion).__name__} solicitud={r.headers['X-Request-ID']}" in caplog.text


@pytest.mark.parametrize("excepcion", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
def test_cancelaciones_y_salidas_del_proceso_no_se_capturan(tmp_path, excepcion):
    a = fa.api(tmp_path)
    solicitud = Request({"type": "http", "app": a.app, "method": "GET", "path": "/api/v1/juegos", "headers": [],
                         "query_string": b"", "client": fa.LOCAL})

    async def siguiente(_):
        raise excepcion()

    with pytest.raises(excepcion):
        asyncio.run(MiddlewarePublico(a.app).dispatch(solicitud, siguiente))
