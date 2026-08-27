"""
Tests del parser de ColorLoto.

Cubren el rediseño posterior a la auditoría de "números y colores
separados": la extracción primaria lee número Y color del MISMO
elemento (`div.balota-{color}`, estructura real confirmada por
inspección directa del sitio), y `DrawDetail.numeros`/`.colores` son
campos paralelos independientes -un fallo de color nunca vuelve a
borrar silenciosamente el número correspondiente.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.infrastructure.parsers import colorloto_parser as parser

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"


class TestParsearDetalleEstructuraRealCompleta:
    """Estructura HTML real confirmada:
    <div class="balota balota-blue nunito-medium">2</div>
    Número y color en el MISMO elemento -caso central que reportó el
    bug en producción."""

    def _detalle(self):
        html = (FIXTURES / "colorloto_detalle_estructura_real.html").read_text(encoding="utf-8")
        return parser.parsear_detalle(html, "206", "https://baloto.com/colorloto/resultados/206")

    def test_numero_sorteo_y_fecha(self):
        d = self._detalle()
        assert d.numero_sorteo == 206
        assert d.fecha == date(2026, 8, 3)

    def test_los_6_numeros_se_extraen_en_orden(self):
        d = self._detalle()
        assert d.numeros == (7, 1, 6, 4, 3, 7)

    def test_los_6_colores_se_extraen_en_el_mismo_orden_que_los_numeros(self):
        """El caso central: 'balota-red' -> ROJO, 'balota-blue' ->
        AZUL, etc, leídos del MISMO div que trae el número."""
        d = self._detalle()
        assert d.colores == ("ROJO", "AZUL", "VERDE", "AMARILLO", "NEGRO", "BLANCO")

    def test_sin_advertencias_cuando_la_extraccion_es_completa(self):
        assert self._detalle().advertencias == ()

    def test_totales_y_acumulado(self):
        d = self._detalle()
        assert d.total_ganadores == 655
        assert d.total_premiacion == "$10.598.600"
        assert d.nuevo_acumulado == "2.020 MILLONES"

    def test_tabla_de_premios(self):
        assert len(self._detalle().categorias_premio) == 3

    def test_el_bug_reportado_ya_no_ocurre_extremo_a_extremo(self):
        """Verificación directa del reporte: antes, con esta MISMA
        estructura real, el sistema registraba '6 balotas extraídas
        correctamente' y acto seguido fallaba con 'se esperaban 6
        balotas, se recibieron 0'. Con el rediseño, ambos números
        (extraídos y de colores) deben coincidir en 6."""
        d = self._detalle()
        assert len(d.numeros) == 6
        assert sum(1 for c in d.colores if c is not None) == 6


class TestParsearDetalleUnColorNoMapeado:
    """Regresión directa del defecto de arquitectura identificado: un
    fallo de color en UNA sola balota (aquí, una clase 'balota-purple'
    que no está en el diccionario de colores oficiales) NO debe borrar
    los 6 números, que sí se extrajeron correctamente."""

    def _detalle(self):
        html = (FIXTURES / "colorloto_detalle_un_color_no_mapeado.html").read_text(encoding="utf-8")
        return parser.parsear_detalle(html, "207", "url")

    def test_los_6_numeros_sobreviven_aunque_falte_un_color(self):
        d = self._detalle()
        assert d.numeros == (7, 1, 6, 4, 3, 7)

    def test_el_color_no_mapeado_queda_none_no_inventado(self):
        d = self._detalle()
        assert d.colores[2] is None  # el tercero: "balota-purple"

    def test_los_otros_5_colores_si_se_detectan(self):
        d = self._detalle()
        assert sum(1 for c in d.colores if c is not None) == 5

    def test_advertencia_dice_cuantos_numeros_y_cuantos_colores_faltan(self):
        d = self._detalle()
        advertencia = next((a for a in d.advertencias if "número" in a and "color" in a), None)
        assert advertencia is not None
        assert "6 número" in advertencia
        assert "1 de ellas" in advertencia


class TestParsearDetalleFallbackSinElementosBalota:
    """Si el sitio cambia y ya no usa 'div.balota-{color}' en
    absoluto, el respaldo (`_extraer_numeros_de_reserva`) debe
    recuperar al menos los números como dígitos aislados en el texto
    -sin color, con advertencia clara, pero sin perder el dato que sí
    se puede recuperar."""

    def _detalle(self):
        html = """
        <html><body>
        <h2>SORTEO #208</h2>
        <p>5 de Agosto de 2026</p>
        <div class="numeros-sin-clase-reconocible">
            <span>7</span><span>1</span><span>6</span><span>4</span><span>3</span><span>7</span>
        </div>
        </body></html>
        """
        return parser.parsear_detalle(html, "208", "url")

    def test_recupera_los_numeros_via_respaldo(self):
        d = self._detalle()
        assert d.numeros == (7, 1, 6, 4, 3, 7)

    def test_ningun_color_se_inventa_en_el_respaldo(self):
        d = self._detalle()
        assert all(c is None for c in d.colores)

    def test_advertencia_de_incompletos_sin_balotas_primarias(self):
        d = self._detalle()
        advertencia = next((a for a in d.advertencias if "número" in a and "color" in a), None)
        assert advertencia is not None
        assert "6 número" in advertencia and "6 de ellas" in advertencia


class TestParsearDetalleSinNadaReconocible:
    """Caso más severo: ni los elementos 'div.balota-{color}' ni
    dígitos aislados en el texto -indica un cambio de estructura real
    del sitio, no un dato puntual incompleto."""

    def _detalle(self):
        html = "<html><body><h2>SORTEO #999</h2><p>1 de Enero de 2027</p><p>Contenido completamente distinto</p></body></html>"
        return parser.parsear_detalle(html, "999", "url")

    def test_no_revienta_y_degrada_con_claridad(self):
        d = self._detalle()
        assert d.numeros == ()
        assert d.colores == ()

    def test_advertencia_explicita_de_cambio_de_estructura(self):
        d = self._detalle()
        assert any("CAMBIO DE ESTRUCTURA" in a for a in d.advertencias)


class TestExtraccionDeColorDesdeClaseCss:
    """Tests unitarios de la función de mapeo clase -> color, aislada
    del resto del parseo."""

    def test_mapea_los_6_colores_oficiales_desde_el_sufijo_de_clase(self):
        from bs4 import BeautifulSoup
        from app.infrastructure.parsers.colorloto_parser import _color_desde_elemento_balota

        casos = {
            "balota-red": "ROJO", "balota-blue": "AZUL", "balota-green": "VERDE",
            "balota-yellow": "AMARILLO", "balota-black": "NEGRO", "balota-white": "BLANCO",
        }
        for clase, esperado in casos.items():
            soup = BeautifulSoup(f'<div class="balota {clase} nunito-medium">1</div>', "html.parser")
            el = soup.find("div")
            assert _color_desde_elemento_balota(el) == esperado, clase

    def test_clase_no_reconocida_devuelve_none_sin_inventar(self):
        from bs4 import BeautifulSoup
        from app.infrastructure.parsers.colorloto_parser import _color_desde_elemento_balota

        soup = BeautifulSoup('<div class="balota balota-purple nunito-medium">1</div>', "html.parser")
        el = soup.find("div")
        assert _color_desde_elemento_balota(el) is None
