import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.infrastructure.parsers import baloto_revancha_parser as parser

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"


class TestParsearListadoRevancha:
    def test_extrae_solo_filas_de_revancha(self):
        html = (FIXTURES / "baloto_listado_pagina1.html").read_text(encoding="utf-8")
        resumenes, _ = parser.parsear_listado_revancha(html)
        assert len(resumenes) == 2

    def test_detecta_pagina_siguiente(self):
        html = (FIXTURES / "baloto_listado_pagina1.html").read_text(encoding="utf-8")
        _, hay_siguiente = parser.parsear_listado_revancha(html)
        assert hay_siguiente is True

    def test_detecta_ausencia_de_pagina_siguiente(self):
        html = (FIXTURES / "baloto_listado_ultima_pagina.html").read_text(encoding="utf-8")
        _, hay_siguiente = parser.parsear_listado_revancha(html)
        assert hay_siguiente is False

    def test_extrae_fecha_y_numero_de_sorteo_correctos(self):
        html = (FIXTURES / "baloto_listado_pagina1.html").read_text(encoding="utf-8")
        resumenes, _ = parser.parsear_listado_revancha(html)
        assert resumenes[0].draw_id == "2684"
        assert resumenes[0].numero_sorteo == 2684
        assert resumenes[0].fecha == date(2026, 7, 18)


class TestParsearListadoBaloto:
    """Regresión de la revisión arquitectónica: antes del fix, el
    listado de Baloto clásico ni siquiera se intentaba extraer -las
    filas se descartaban por completo. Estos tests prueban que la
    MISMA página de listado (un solo recorrido de paginación) permite
    extraer ambas familias."""

    def test_extrae_solo_filas_de_baloto_clasico(self):
        html = (FIXTURES / "baloto_listado_pagina1.html").read_text(encoding="utf-8")
        resumenes, _ = parser.parsear_listado_baloto(html)
        assert len(resumenes) == 2

    def test_numeros_de_sorteo_coinciden_con_los_de_revancha_del_mismo_sorteo(self):
        """Baloto y Revancha del sorteo 2684 deben tener el MISMO
        numero_sorteo -es la clave de la relación entre ambos."""
        html = (FIXTURES / "baloto_listado_pagina1.html").read_text(encoding="utf-8")
        baloto, _ = parser.parsear_listado_baloto(html)
        revancha, _ = parser.parsear_listado_revancha(html)
        assert {r.numero_sorteo for r in baloto} == {r.numero_sorteo for r in revancha} == {2683, 2684}

    def test_baloto_y_revancha_no_se_mezclan_entre_si(self):
        html = (FIXTURES / "baloto_listado_pagina1.html").read_text(encoding="utf-8")
        baloto, _ = parser.parsear_listado_baloto(html)
        revancha, _ = parser.parsear_listado_revancha(html)
        draw_ids_baloto = {r.draw_id for r in baloto}
        draw_ids_revancha = {r.draw_id for r in revancha}
        # mismos numero_sorteo, pero son objetos/filas distintas -no
        # se cuenta el mismo <a> dos veces ni se confunde una familia
        # con la otra
        assert draw_ids_baloto == draw_ids_revancha  # los draw_id (numero_sorteo como texto) coinciden
        assert len(baloto) == len(revancha) == 2


class TestParsearDetalle:
    def _detalle(self, etiqueta="BalotoRevancha"):
        html = (FIXTURES / "baloto_detalle_2684.html").read_text(encoding="utf-8")
        return parser.parsear_detalle(html, "2684", "https://baloto.com/resultados-revancha/2684", etiqueta=etiqueta)

    def test_numero_sorteo_y_fecha(self):
        d = self._detalle()
        assert d.numero_sorteo == 2684
        assert d.fecha == date(2026, 7, 18)

    def test_numeros_y_superbalota(self):
        d = self._detalle()
        assert d.numeros == (5, 6, 31, 32, 34)
        assert d.superbalota == 8

    def test_totales(self):
        d = self._detalle()
        assert d.total_ganadores == 31860
        assert d.total_premiacion == "$125.481.300"
        assert d.nuevo_acumulado == "8.200 MILLONES"

    def test_tabla_de_premios_completa(self):
        d = self._detalle()
        assert len(d.categorias_premio) == 8
        assert d.categorias_premio[0].categoria == "5 + SB"
        assert d.categorias_premio[2].ganadores == 6
        assert d.categorias_premio[5].ganadores == 2262

    def test_sin_advertencias_en_detalle_bien_formado(self):
        assert self._detalle().advertencias == ()

    def test_parsear_detalle_es_agnostico_a_la_etiqueta(self):
        """parsear_detalle produce el mismo resultado sin importar si
        se le dice 'Baloto' o 'BalotoRevancha' -la etiqueta es solo
        para logs, ambas familias comparten la misma estructura real
        de página (verificado contra el sitio en vivo)."""
        d_revancha = self._detalle(etiqueta="BalotoRevancha")
        d_baloto = self._detalle(etiqueta="Baloto")
        assert d_revancha.numeros == d_baloto.numeros
        assert d_revancha.superbalota == d_baloto.superbalota
