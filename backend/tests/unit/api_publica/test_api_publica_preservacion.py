"""Fase 8: las consultas publicas preservan historicos, simulaciones, modelos y
almacenes; no entrenan, simulan, generan, sincronizan ni recuperan trabajos.
El estado de cuotas y monitoreo vive solo en memoria del proceso."""
from __future__ import annotations

import pytest

from app.api.publica import aplicacion
from app.application.use_cases.carteras import CarterasDeModelos
from app.application.use_cases.predicciones import CentroDePredicciones
from app.application.use_cases.simulaciones import SimulacionesFase7
from app.core.config import get_settings
from app.infrastructure.db import session as db_session
from tests.unit import fixtures_fase4 as f4
from tests.unit.api_publica import fixtures_api_publica as fa

ESCRITORES = {SimulacionesFase7: ("iniciar", "ejecutar", "ahora", "recuperar", "abortar"),
              CentroDePredicciones: ("iniciar", "ejecutar", "ahora", "explicar", "abortar"),
              CarterasDeModelos: ("iniciar", "ejecutar", "ahora", "recuperar", "abortar", "configurar")}


def _consultas(a, ident: str, clave: str | None) -> list[str]:
    urls = ["/api/v1/salud", "/api/v1/estado", "/api/v1/juegos", "/api/v1/juegos/COLORLOTO",
            "/api/v1/juegos/BALOTO/sorteos?por_pagina=100&orden=numero_asc", "/api/v1/juegos/COLORLOTO/sorteos/1",
            "/api/v1/juegos/MILOTO/estadisticas", "/api/v1/juegos/MILOTO/estadisticas/resumen",
            "/api/v1/juegos/COLORLOTO/estadisticas/panel", "/api/v1/juegos/COLORLOTO/estadisticas/correlaciones",
            "/api/v1/juegos/MILOTO/predicciones", "/api/v1/juegos/MILOTO/simulaciones", f"/api/v1/simulaciones/{ident}",
            "/api/v1/juegos/BALOTO/predicciones"]
    if clave:
        urls.append(f"/api/v1/juegos/MILOTO/predicciones?cartera={clave}")
    return urls


def _bloquear_escritores(monkeypatch):
    llamadas = []
    for clase, metodos in ESCRITORES.items():
        for metodo in metodos:
            def prohibido(*a, _n=f"{clase.__name__}.{metodo}", **k):
                llamadas.append(_n)
                raise AssertionError(f"una consulta publica llamo a {_n}")
            monkeypatch.setattr(clase, metodo, prohibido)
    return llamadas


def test_las_consultas_no_escriben_ni_lanzan_trabajos(tmp_path, monkeypatch):
    entorno4 = f4.entorno(tmp_path / "f4")
    entorno4.configurar("MILOTO", "uniforme")
    centro = entorno4.centro()
    centro.ahora("MILOTO")
    clave = centro.consultar("MILOTO")["prediccion"]["clave"]
    a = fa.api(tmp_path, centro=centro, fichas_por_minuto=10_000)
    ident = a.entorno.servicio().ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]["resultado"]
    filas, almacenes, simulaciones = fa.filas(a.entorno), fa.arbol(entorno4.raiz), fa.arbol(a.entorno.raiz)
    llamadas = _bloquear_escritores(monkeypatch)
    c = a.cliente()
    for _ in range(2):
        for url in _consultas(a, ident, clave):
            r = c.get(url, headers=a.cabeceras())
            assert r.status_code == 200, (url, r.status_code, r.text[:200])
    assert llamadas == []
    assert fa.filas(a.entorno) == filas
    assert fa.arbol(entorno4.raiz) == almacenes and fa.arbol(a.entorno.raiz) == simulaciones
    assert a.app.state.monitor.resumen()["solicitudes"] == 2 * len(_consultas(a, ident, clave))


def _arbol_completo(raiz):
    return sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*"))


@pytest.fixture
def directorios_temporales(tmp_path, monkeypatch):
    raiz = tmp_path / "almacenes"
    raiz.mkdir()
    for nombre in ("PRONOSTICOS_EXPERIMENTALES", "OPERACION", "LABORATORIO_MODELOS", "CARTERAS_MODELOS",
                   "RESULTADOS_MODELOS", "PREDICCIONES_MODELOS", "AUTOMATIZACION", "SIMULACIONES"):
        monkeypatch.setenv(f"DIRECTORIO_{nombre}", str(raiz / nombre.lower()))
    get_settings.cache_clear()
    yield raiz
    get_settings.cache_clear()


def test_cableado_predeterminado_no_crea_ni_toca_almacenes(tmp_path, monkeypatch, directorios_temporales):
    """Sin sustituir dependencias: sesion propia de solo lectura sobre la base
    sintetica y casos de uso con sus almacenes predeterminados (vacios)."""
    e = fa.f7.entorno(tmp_path / "datos")
    monkeypatch.setattr(db_session, "SessionLocal", e.sesiones)
    conf, claves = fa.configuracion("pruebas", fichas_por_minuto=10_000)
    app = aplicacion.crear_app(conf)
    llamadas = _bloquear_escritores(monkeypatch)
    filas = fa.filas(e)
    c = fa.TestClient(app)
    cabeceras = {"X-API-Key": claves["pruebas"]}
    for url in ("/api/v1/juegos", "/api/v1/juegos/BALOTO", "/api/v1/juegos/BALOTO/sorteos",
                "/api/v1/juegos/BALOTO/estadisticas/panel", "/api/v1/juegos/BALOTO/estadisticas/resumen"):
        assert c.get(url, headers=cabeceras).status_code == 200, url
    # Las lecturas de predicciones y simulaciones usan `SET TRANSACTION READ ONLY` sin variante SQLite:
    # aqui pueden informar base no disponible; con PostgreSQL lo cubre tests/postgres_fase8.py.
    for url in ("/api/v1/juegos/MILOTO/predicciones", "/api/v1/juegos/MILOTO/simulaciones",
                "/api/v1/simulaciones/00000000-0000-0000-0000-000000000000", "/api/v1/estado"):
        assert c.get(url, headers=cabeceras).status_code in (200, 404, 503), url
    assert llamadas == [] and fa.filas(e) == filas
    assert _arbol_completo(directorios_temporales) == []  # ni archivos ni carpetas nuevas
