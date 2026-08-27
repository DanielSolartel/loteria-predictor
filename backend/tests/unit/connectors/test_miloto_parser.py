import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.infrastructure.parsers import miloto_parser as parser

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"


class TestParsearListado:
    def test_extrae_los_3_sorteos_de_la_pagina(self):
        html = (FIXTURES / "miloto_listado_pagina1.html").read_text(encoding="utf-8")
        resumenes, _, hay_siguiente = parser.parsear_listado(html)
        assert len(resumenes) == 3
        assert hay_siguiente is True

    def test_el_listado_trae_los_5_numeros_completos(self):
        """Requisito clave: MiLoto no depende del detalle (roto en el
        sitio real) para el dato mínimo, porque el listado ya trae
        fecha + los 5 números completos."""
        html = (FIXTURES / "miloto_listado_pagina1.html").read_text(encoding="utf-8")
        _, numeros_por_draw, _ = parser.parsear_listado(html)
        assert numeros_por_draw["580"] == (17, 19, 21, 28, 33)
        assert numeros_por_draw["579"] == (1, 27, 28, 33, 35)

    def test_el_dia_de_la_fecha_no_contamina_los_numeros(self):
        """Regresión: el día '30' de '30 de Julio' no debe colarse
        como si fuera un número del sorteo."""
        html = (FIXTURES / "miloto_listado_pagina1.html").read_text(encoding="utf-8")
        _, numeros_por_draw, _ = parser.parsear_listado(html)
        assert 30 not in numeros_por_draw["580"]


class TestParsearDetalleRoto:
    def test_detecta_que_el_detalle_no_corresponde_al_sorteo_pedido(self):
        """Reproduce el bug confirmado contra el sitio real: la ruta
        de detalle de MiLoto devuelve el contenido genérico de
        Baloto/Revancha en vez del sorteo de MiLoto solicitado."""
        html = (FIXTURES / "miloto_detalle_roto_580.html").read_text(encoding="utf-8")
        _, coincide = parser.parsear_detalle(html, "580", "url")
        assert coincide is False

    def test_deja_advertencia_explicita_del_problema(self):
        html = (FIXTURES / "miloto_detalle_roto_580.html").read_text(encoding="utf-8")
        detalle, _ = parser.parsear_detalle(html, "580", "url")
        assert len(detalle.advertencias) == 1
        assert "enrutamiento" in detalle.advertencias[0]
