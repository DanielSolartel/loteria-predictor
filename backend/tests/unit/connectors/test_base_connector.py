"""
Tests de BaseConnector usando un conector de prueba mínimo (sin red,
sin BeautifulSoup real) para verificar la lógica compartida:
descubrimiento automático de páginas, parada en sincronización
incremental, y tolerancia a que un sorteo individual falle sin
detener el resto.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.interfaces.draw_source_connector import DrawDetail, DrawSummary
from app.infrastructure.connectors.base_connector import BaseConnector, ConectorFetchError


class _FakeHtmlStorage:
    def __init__(self):
        self.guardados = {}

    def guardar(self, prefijo, draw_id, html):
        self.guardados[(prefijo, draw_id)] = html
        return "fake_path"

    def leer(self, prefijo, draw_id):
        return self.guardados.get((prefijo, draw_id))

    def listar(self, prefijo):
        return [k[1] for k in self.guardados if k[0] == prefijo]


class _ConectorDePrueba(BaseConnector):
    """3 páginas simuladas con 2 sorteos cada una, numerados 6..1
    (descendente, como el sitio real). El detalle del sorteo 3
    siempre falla, para probar tolerancia a fallos."""

    storage_prefix = "prueba"

    @property
    def game_code(self) -> str:
        return "PRUEBA"

    def _url_listado(self, pagina: int) -> str:
        return f"listado://{pagina}"

    def _url_detalle(self, draw_id: str) -> str:
        return f"detalle://{draw_id}"

    def _parsear_pagina_listado(self, html: str):
        # html aquí es literalmente el número de página, inyectado por _get
        pagina = int(html)
        paginas = {
            1: ([DrawSummary("6", 6, date(2026, 1, 6)), DrawSummary("5", 5, date(2026, 1, 5))], True),
            2: ([DrawSummary("4", 4, date(2026, 1, 4)), DrawSummary("3", 3, date(2026, 1, 3))], True),
            3: ([DrawSummary("2", 2, date(2026, 1, 2)), DrawSummary("1", 1, date(2026, 1, 1))], False),
        }
        return paginas.get(pagina, ([], False))

    def _parsear_pagina_detalle(self, html: str, draw_id: str, url: str) -> DrawDetail:
        if draw_id == "3":
            raise ValueError("fallo simulado de parseo para el sorteo 3")
        return DrawDetail(draw_id=draw_id, numero_sorteo=int(draw_id), fecha=date(2026, 1, int(draw_id)))


def _conector():
    c = _ConectorDePrueba(html_storage=_FakeHtmlStorage(), pausa_entre_peticiones=0)
    c._get = lambda url: url.split("://")[1]  # devuelve el número de página/draw_id como "html"
    return c


class TestFetchDraws:
    def test_descubre_todas_las_paginas_sin_limite_conocido(self):
        c = _conector()
        resumenes = c.fetch_draws(ultimo_conocido=None)
        assert [r.numero_sorteo for r in resumenes] == [6, 5, 4, 3, 2, 1]

    def test_se_detiene_al_encontrar_el_ultimo_conocido(self):
        c = _conector()
        resumenes = c.fetch_draws(ultimo_conocido=4)
        # Solo deben quedar los sorteos mas nuevos que el 4: 5 y 6
        assert sorted(r.numero_sorteo for r in resumenes) == [5, 6]

    def test_respeta_max_paginas(self):
        c = _conector()
        resumenes = c.fetch_draws(ultimo_conocido=None, max_paginas=1)
        assert [r.numero_sorteo for r in resumenes] == [6, 5]


class TestSync:
    def test_tolera_fallo_de_un_sorteo_sin_detener_el_resto(self):
        c = _conector()
        resultado = c.sync(ultimo_conocido=None)
        assert len(resultado.draws) == 5  # todos menos el 3
        assert len(resultado.fallidos) == 1
        assert resultado.fallidos[0].draw_id == "3"
        assert "fallo simulado" in resultado.fallidos[0].error

    def test_sincronizacion_incremental_solo_trae_lo_nuevo(self):
        c = _conector()
        resultado = c.sync(ultimo_conocido=4)
        numeros = sorted(d.numero_sorteo for d in resultado.draws)
        assert numeros == [5, 6]

    def test_guarda_html_de_cada_detalle_obtenido(self):
        c = _conector()
        c.sync(ultimo_conocido=4)
        # se guardaron los HTML de los sorteos 5 y 6 (el detalle "3" fallo antes de guardar)
        assert ("prueba", "6") in c._html_storage.guardados
        assert ("prueba", "5") in c._html_storage.guardados


class TestHealthCheck:
    def test_disponible_cuando_la_peticion_funciona(self):
        c = _conector()
        salud = c.health_check()
        assert salud.disponible is True

    def test_no_disponible_cuando_falla_la_peticion(self):
        c = _conector()
        def _falla(url):
            raise ConectorFetchError("origen caido")
        c._get = _falla
        salud = c.health_check()
        assert salud.disponible is False
        assert "origen caido" in salud.mensaje


class TestReintentos:
    def test_agota_reintentos_y_lanza_error_claro(self):
        import requests

        c = _ConectorDePrueba(html_storage=_FakeHtmlStorage(), pausa_entre_peticiones=0, max_reintentos=2)

        llamadas = {"n": 0}

        class _SesionFalsa:
            def get(self, url, timeout):
                llamadas["n"] += 1
                raise requests.exceptions.ConnectionError("conexión rechazada")

        c._session = _SesionFalsa()

        with pytest.raises(ConectorFetchError):
            c._get("http://origen-inalcanzable.test")

        assert llamadas["n"] == 2  # respeta max_reintentos
