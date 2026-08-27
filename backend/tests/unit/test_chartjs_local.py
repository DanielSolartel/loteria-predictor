"""
Tests de la carga LOCAL de Chart.js (corrección: `typeof Chart ===
"undefined"` en el navegador porque el recurso CDN no cargaba).

IMPORTANTE - transparencia sobre el alcance real de esta verificación:
este sandbox no tiene `fastapi` instalado (confirmado, sin acceso de
red para instalarlo) y no existe infraestructura de tests HTTP
(`TestClient`/`conftest.py`) en el proyecto -no pude agregar pruebas
reales vía `TestClient` como se pidió preferentemente. Estos tests
verifican el contenido REAL de los templates (lectura de archivo,
UTF-8 explícito) y la estructura REAL del directorio estático -no son
mocks que solo verifiquen llamadas, pero tampoco son pruebas HTTP end
to end.

El asset real `chart.umd.min.js` NO está incluido en este entorno -no
pudo descargarse de forma verificable (cdnjs, unpkg y GitHub raw
devolvieron 403 por la política de red de este sandbox) y,
explícitamente, no se fabricó un stub para simularlo. Por eso
`TestAssetLocalExiste` FALLARÁ hasta que coloques el archivo real
-ver `app/static/vendor/chartjs/README.md`. Esto es intencional y
esperado, no un error de la corrección.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_RUTA_ASSET = Path("app/static/vendor/chartjs/chart.umd.min.js")
_TEMPLATES = [
    "app/templates/estadisticas/frecuencia_numeros.html",
    "app/templates/estadisticas/frecuencia_superbalota.html",
    "app/templates/estadisticas/frecuencia_observada_esperada.html",
]
_CANVAS_ESPERADOS = {
    "app/templates/estadisticas/frecuencia_numeros.html": "grafica-frecuencia-numeros",
    "app/templates/estadisticas/frecuencia_superbalota.html": "grafica-frecuencia-superbalota",
    "app/templates/estadisticas/frecuencia_observada_esperada.html": "grafica-observada-esperada",
}
_DATOS_JSON_ESPERADOS = {
    "app/templates/estadisticas/frecuencia_numeros.html": "datos-frecuencia-numeros",
    "app/templates/estadisticas/frecuencia_superbalota.html": "datos-frecuencia-superbalota",
    "app/templates/estadisticas/frecuencia_observada_esperada.html": "datos-observada-esperada",
}


class TestAssetLocalExiste:
    """Estos tests FALLARÁN hasta que coloques el archivo real -ver
    `app/static/vendor/chartjs/README.md`. No se fabricó un stub para
    hacerlos pasar artificialmente."""

    def test_el_archivo_existe(self):
        assert _RUTA_ASSET.exists(), (
            f"Falta {_RUTA_ASSET} -ver app/static/vendor/chartjs/README.md para "
            "instrucciones de cómo obtenerlo (no se pudo descargar en este entorno)."
        )

    def test_el_contenido_no_esta_vacio(self):
        assert _RUTA_ASSET.exists(), "El archivo no existe todavía -ver README.md"
        assert _RUTA_ASSET.stat().st_size > 0

    def test_el_contenido_parece_chartjs_real(self):
        assert _RUTA_ASSET.exists(), "El archivo no existe todavía -ver README.md"
        contenido = _RUTA_ASSET.read_text(encoding="utf-8", errors="ignore")
        assert "Chart" in contenido
        assert len(contenido) > 10_000


class TestTemplatesReferencianAssetLocal:
    def test_las_tres_paginas_referencian_la_ruta_local(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert "/static/vendor/chartjs/chart.umd.min.js" in contenido, plantilla

    def test_ninguna_pagina_depende_de_cdnjs_para_chartjs(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert "cdnjs.cloudflare.com/ajax/libs/Chart.js" not in contenido, plantilla

    def test_referencia_local_aparece_antes_de_new_chart(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            indice_script = contenido.index("/static/vendor/chartjs/chart.umd.min.js")
            indice_new_chart = contenido.index("new Chart(")
            assert indice_script < indice_new_chart, plantilla

    def test_cada_pagina_conserva_su_canvas(self):
        for plantilla, canvas_id in _CANVAS_ESPERADOS.items():
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert f'id="{canvas_id}"' in contenido, plantilla

    def test_cada_pagina_conserva_su_bloque_json(self):
        for plantilla, json_id in _DATOS_JSON_ESPERADOS.items():
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert f'id="{json_id}"' in contenido, plantilla
            assert 'type="application/json"' in contenido, plantilla

    def test_los_datos_se_siguen_serializando_con_tojson(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert "| tojson" in contenido, plantilla

    def test_base_html_no_fue_modificado_para_esto(self):
        contenido = Path("app/templates/base.html").read_text(encoding="utf-8")
        assert "vendor/chartjs" not in contenido

    def test_bootstrap_y_htmx_de_base_html_siguen_via_cdn_sin_cambios(self):
        contenido = Path("app/templates/base.html").read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.3" in contenido
        assert "cdnjs.cloudflare.com/ajax/libs/htmx/1.9.12" in contenido


class TestEstructuraEstaticaCorrecta:
    def test_directorio_vendor_chartjs_existe(self):
        assert Path("app/static/vendor/chartjs").is_dir()

    def test_readme_de_instrucciones_presente(self):
        assert Path("app/static/vendor/chartjs/README.md").exists()
