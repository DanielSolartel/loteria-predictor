"""Fase 9.4: frontera cerrada de las consultas de artefactos guardados.

El destino falso observa únicamente el reenvío HTTP. La lectura de almacenes
reales y su proyección se prueban en test_api_publica_guardados.py.
"""
from __future__ import annotations

import pytest

from tests.unit.pasarela import fixtures_pasarela as fp


@pytest.fixture
def entorno(tmp_path):
    with fp.destino_falso() as destino:
        yield destino, fp.pasarela(destino.destino, fp.dist(tmp_path), fp.clave_sintetica())


@pytest.mark.parametrize("ruta,consulta,codigo", [
    ("modelos-guardados", "modelo=x&modelo=y", "parametro_repetido"),
    ("modelos-guardados", "entrenar=true", "parametro_no_admitido"),
    ("modelos-guardados", "perfil=reducido%20otro", "parametro_no_valido"),
    ("carteras-guardadas", "linea=a&linea=b", "parametro_repetido"),
    ("carteras-guardadas", "generar=true", "parametro_no_admitido"),
    ("carteras-guardadas", "desde=", "parametro_no_valido"),
    ("resultados", "procedencia=carteras&procedencia=operacion", "parametro_repetido"),
    ("resultados", "guardar=true", "parametro_no_admitido"),
    ("resultados", "linea=" + "a" * 161, "parametro_no_valido"),
    ("modelos-guardados/" + "a" * 64, "pagina=1", "parametro_no_admitido"),
    ("carteras-guardadas/" + "a" * 64, "hasta=1", "parametro_no_admitido"),
])
def test_rechaza_consultas_ajenas_antes_del_destino(entorno, ruta, consulta, codigo):
    destino, app = entorno
    respuesta = fp.cliente(app).get(f"/api/v1/juegos/BALOTO/{ruta}?{consulta}")
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == codigo
    assert destino.recibidas == []
    assert respuesta.headers["cache-control"] == "no-store"
    assert len(respuesta.headers["x-request-id"]) == 32


@pytest.mark.parametrize("recurso", ["modelos-guardados", "carteras-guardadas"])
@pytest.mark.parametrize("clave", ["a" * 63, "a" * 65, "A" * 64, "../secreto", "x" * 64])
def test_claves_no_canonicas_no_se_reenvian(entorno, recurso, clave):
    destino, app = entorno
    respuesta = fp.cliente(app).get(f"/api/v1/juegos/BALOTO/{recurso}/{clave}")
    assert respuesta.status_code in (400, 404)
    assert destino.recibidas == []


@pytest.mark.parametrize("recurso", ["modelos-guardados", "carteras-guardadas", "resultados"])
def test_conserva_cuota_y_reintento_explicito(entorno, recurso):
    destino, app = entorno
    destino.json(429, {"error": {"codigo": "limite_excedido", "mensaje": "Límite excedido", "solicitud": "d" * 32}},
                 **{"Retry-After": "37"})
    cliente = fp.cliente(app)
    respuesta = cliente.get(f"/api/v1/juegos/MILOTO/{recurso}")
    assert respuesta.status_code == 429 and respuesta.headers["retry-after"] == "37"
    assert len(destino.recibidas) == 1  # la pasarela no reintenta automáticamente
    assert respuesta.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("recurso", ["modelos-guardados", "carteras-guardadas", "resultados"])
def test_no_acepta_escrituras_en_las_rutas_nuevas(entorno, recurso):
    destino, app = entorno
    for metodo in ("post", "put", "patch", "delete"):
        respuesta = getattr(fp.cliente(app), metodo)(f"/api/v1/juegos/MILOTO/{recurso}")
        assert respuesta.status_code == 405
    assert destino.recibidas == []


def test_lineas_guardadas_largas_sin_ampliar_otros_parametros(entorno):
    from app.application.ml import carteras_artefactos as ca
    from app.infrastructure.storage.carteras_file_store import _LINEA

    destino, app = entorno
    # Identidad producida por la receta existente; no una cadena arbitraria.
    linea = ca.linea_de("BALOTO", "actual_logistica_ae36", "reducido", 20, "limitada", 4294967295,
                        {"clave": "b" * 64, "numero": 1234567890})["id"]
    assert len(linea) > 80 and _LINEA.fullmatch(linea)
    cliente = fp.cliente(app)
    for recurso, valor in (("carteras-guardadas", linea), ("resultados", "carteras:" + linea)):
        url = f"/api/v1/juegos/BALOTO/{recurso}?linea={valor}"
        assert cliente.get(url).status_code == 200
        assert destino.recibidas[-1].ruta == url.replace(":", "%3A")
    antes = len(destino.recibidas)
    respuesta = cliente.get("/api/v1/juegos/BALOTO/modelos-guardados?modelo=" + "a" * 81)
    assert respuesta.status_code == 422 and len(destino.recibidas) == antes
