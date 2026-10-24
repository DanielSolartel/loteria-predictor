"""Fase 8 v2, F8-OBS-01: el monitoreo acota tambien el metodo HTTP. Los metodos
no estandar cuentan juntos como `OTRO`, no se guardan ni se registran tal cual
y siguen recibiendo 405; los metodos estandar conservan su nombre."""
from __future__ import annotations

import logging

from tests.unit.api_publica import fixtures_api_publica as fa


def test_metodos_inventados_no_hacen_crecer_el_monitoreo(tmp_path, caplog):
    a = fa.api(tmp_path)
    c = a.cliente()
    entradas = []
    with caplog.at_level(logging.INFO, logger="app.api.publica"):
        for lote in (range(64), range(64, 128)):
            for i in lote:
                r = c.request(f"INVENTADO_{i}", "/api/v1/salud")
                assert r.status_code == 405 and r.headers["allow"] == "GET"
                assert r.json()["error"]["codigo"] == "metodo_no_permitido"
            entradas.append(len(a.app.state.monitor.resumen()["rutas"]))
    assert entradas == [1, 1]  # v1: 64 y 128
    fila = a.app.state.monitor.resumen()["rutas"][0]
    assert (fila["metodo"], fila["ruta"], fila["solicitudes"], fila["errores_4xx"]) == (
        "OTRO", "/api/v1/salud", 128, 128)
    assert "INVENTADO_" not in caplog.text and caplog.text.count("api_publica OTRO /api/v1/salud 405 ") == 128


def test_metodos_estandar_conservan_su_nombre(tmp_path):
    a = fa.api(tmp_path)
    c = a.cliente()
    estandar = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
    for metodo in estandar:
        c.request(metodo, "/api/v1/salud")
    assert {r["metodo"] for r in a.app.state.monitor.resumen()["rutas"]} == set(estandar)
    assert c.delete("/api/v1/salud").status_code == 405
