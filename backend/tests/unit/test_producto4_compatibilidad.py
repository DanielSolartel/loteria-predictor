"""Producto 4: compatibilidad con Productos 1-3.

El laboratorio escribe en su propio almacen: no reescribe artefactos de
Productos 1-3, no cambia su lectura (esquemas 1 y 2, sellos, secuencias) ni
la primera emision que selecciona `/rendimiento`, y la operacion diaria y su
panel siguen funcionando igual."""
from __future__ import annotations

import hashlib

import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.use_cases.rendimiento import ConsultarRendimiento
from app.core.config import Settings
from tests.unit import fixtures_producto3 as f3
from tests.unit import fixtures_producto4 as f4


def _huellas(directorio):
    return {str(p.relative_to(directorio)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directorio.rglob("*")) if p.is_file()}


@pytest.fixture
def productos(tmp_path):
    """Pronosticos de Productos 1-3 (operacion diaria real con fixtures) y un
    laboratorio sobre los mismos repositorios en memoria."""
    e3 = f3.entorno(tmp_path / "p3")
    final = e3.operacion().ejecutar_ahora(["BALOTO", "MILOTO", "COLORLOTO"], "local", "prueba")
    assert final["estado"] == "exito"
    lab = f4.Entorno(e3.juegos, e3.resultados, e3.historicos, tmp_path / "laboratorio").laboratorio()
    yield e3, lab
    f3.limpiar()


def test_el_laboratorio_no_toca_los_archivos_de_productos_1_a_3(productos):
    e3, lab = productos
    antes = _huellas(e3.almacen._directorio)
    operacion_antes = _huellas(e3.directorio_operacion)
    for juego in ("BALOTO", "MILOTO", "COLORLOTO"):
        r = lab.comparar_ahora([juego], le.Protocolo(bloques=1, perfil="reducido"))["juegos"][juego]
        modelo = {"COLORLOTO": "poisson_regularizado"}.get(juego, "logistica_regularizada")
        lab.generar(r["experimento"], modelo)
    assert _huellas(e3.almacen._directorio) == antes
    assert _huellas(e3.directorio_operacion) == operacion_antes
    for juego in ("BALOTO", "MILOTO", "COLORLOTO"):
        for g in e3.almacen.listar(juego):
            assert g.artefacto["esquema"] in ("pronostico-experimental/1", "pronostico-experimental/2")


def test_rendimiento_selecciona_la_misma_primera_emision(productos):
    e3, lab = productos
    consultar = ConsultarRendimiento(e3.almacen, e3.juegos, e3.resultados)
    antes = {j: consultar.ejecutar(j) for j in ("BALOTO", "MILOTO")}
    for juego in ("BALOTO", "MILOTO"):
        r = lab.comparar_ahora([juego], le.Protocolo(bloques=1, perfil="reducido"))["juegos"][juego]
        lab.generar(r["experimento"], "hgb_clasificador")  # mismo objetivo que el pronostico de Producto 3
    assert {j: consultar.ejecutar(j) for j in ("BALOTO", "MILOTO")} == antes


def test_la_operacion_diaria_y_su_panel_siguen_igual(productos, tmp_path):
    e3, lab = productos
    lab.comparar_ahora(["MILOTO"], le.Protocolo(bloques=1, perfil="reducido"))
    otra = e3.operacion().ejecutar_ahora(["MILOTO"], "local", "prueba")  # reutiliza su propio pronostico
    assert otra["estado"] == "exito" and otra["juegos"]["MILOTO"]["pronostico"]["reutilizado"] is True
    c = f3.cliente(e3)
    assert c.get("/operacion").status_code == 200 and c.get("/rendimiento?juego=MILOTO").status_code == 200
    assert "Laboratorio de modelos" in c.get("/operacion").text and "Laboratorio de modelos" in c.get("/pronosticos").text


def test_almacen_propio_por_defecto(monkeypatch):
    monkeypatch.delenv("DIRECTORIO_LABORATORIO_MODELOS", raising=False)
    ajustes = Settings(_env_file=None)
    assert ajustes.directorio_laboratorio_modelos == "storage/laboratorio"
    assert ajustes.directorio_laboratorio_modelos not in (ajustes.directorio_pronosticos_experimentales,
                                                          ajustes.directorio_operacion)


def test_almacen_propio_respeta_la_variable_de_entorno(monkeypatch, tmp_path):
    directorio = str(tmp_path / "laboratorio-configurado")
    monkeypatch.setenv("DIRECTORIO_LABORATORIO_MODELOS", directorio)
    ajustes = Settings(_env_file=None)
    assert ajustes.directorio_laboratorio_modelos == directorio
