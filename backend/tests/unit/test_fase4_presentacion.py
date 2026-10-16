"""Regresión del SVG: las cifras quedan fuera del área de barras y referencia.

Se renderiza la macro real con candidatos de los cuatro tipos representados;
no se oculta la referencia ni se eliminan valores de la gráfica o la tabla.
La revisión de paginación se hace además con Chromium y PDF sintéticos.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from jinja2 import Environment, FileSystemLoader

from app.api.web.routers.predicciones import barras_ranking


@pytest.mark.parametrize("candidato", [7, [3, "AZUL"], "VERDE"])
def test_cifras_svg_separadas_de_barras_y_referencia_uniforme(candidato):
    # Caso que cruzaba una etiqueta: el candidato queda ligeramente por debajo
    # de la referencia. El segundo fija el máximo sin mover la referencia.
    filas = [{"candidato": candidato, "probabilidad": p, "uniforme": .1,
              "posicion": i + 1, "diferencia": p - .1, "razon": p / .1}
             for i, p in enumerate((.098, .1))]
    app = Path(__file__).resolve().parents[2] / "app"
    env = Environment(loader=FileSystemLoader(app / "templates"), autoescape=True)
    macro = env.get_template("predicciones/_macros.html").module
    html = str(macro.ranking("Prueba", filas, barras_ranking(filas), "Probabilidad"))
    svg = ET.fromstring(html[html.index("<svg"):html.index("</svg>") + 6])
    referencia = float(svg.find("line").attrib["x1"])
    barras = svg.findall("rect")
    borde_derecho = max(float(b.attrib["x"]) + float(b.attrib["width"]) for b in barras)
    cifras = [t for t in svg.findall("text") if t.attrib.get("font-size") == "9"]
    assert len(cifras) == len(filas)
    for cifra, fila in zip(cifras, filas, strict=True):
        assert cifra.text == format(fila["probabilidad"], ".4f")
        # Columna a la derecha del gráfico. Una etiqueta de seis caracteres a
        # 9px cabe con holgura en los 45px reservados, sin cruzar la referencia.
        assert cifra.attrib.get("text-anchor") == "end"
        izquierda_conservadora = float(cifra.attrib["x"]) - 45
        assert izquierda_conservadora > max(referencia, borde_derecho)
    assert "stroke-dasharray" in svg.find("line").attrib
    assert html.count("0.098000") == 1 and html.count("0.100000") == 3
