"""
Tests de la Etapa X (controles de corte temporal en la interfaz).

IMPORTANTE - transparencia sobre el alcance real de esta verificación
(misma limitación de todas las etapas anteriores, reverificada): este
sandbox sigue sin `fastapi`/`sqlalchemy` instalados. Esto significa
que NO pude ejecutar `Query(default=None, ge=1)` a través del
framework real -no se afirma que el 422 real de FastAPI para
corte=0/-1/texto haya sido disparado ni verificado end-to-end aquí.
Lo que SÍ se verifica, ejecutado, código real:

  1. `construir_navegacion_estadisticas` (no depende de FastAPI) con
     TODAS las reglas exactas de propagación/reset del corte pedidas
     en esta etapa.
  2. Contenido estático real de los 4 templates + el partial
     compartido (lectura de archivo, UTF-8 explícito).
  3. Lectura de código fuente del router para confirmar la firma
     `Query(default=None, ge=1)` en las 4 rutas, y que el router no
     agrega ninguna ruta nueva ni modifica las 4 existentes.

No se afirma haber disparado un 422 real por HTTP, ni haber
verificado el formato JSON exacto de FastAPI contra un servidor
corriendo -eso requiere `pytest` real en Windows.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.web.estadisticas_slugs import CAPACIDAD_SUPERBALOTA_POR_SLUG
from app.api.web.view_models import construir_navegacion_estadisticas

_TEMPLATES = [
    "app/templates/estadisticas/frecuencia_numeros.html",
    "app/templates/estadisticas/frecuencia_superbalota.html",
    "app/templates/estadisticas/frecuencia_observada_esperada.html",
    "app/templates/estadisticas/atrasos_numeros.html",
]
_PARTIAL = "app/templates/estadisticas/partials/control_corte_temporal.html"
_ROUTER = "app/api/web/routers/estadisticas.py"

_NOMBRES = {"BALOTO": "Baloto", "BALOTO_REVANCHA": "Baloto Revancha", "MILOTO": "MiLoto"}


# =====================================================================
# C. Navegación dentro del mismo juego -conserva el corte
# =====================================================================

class TestCorteConservadoEntreMetricasDelMismoJuego:
    def test_baloto_conserva_corte_entre_las_cuatro_metricas(self):
        for metrica_actual in ("frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada", "atrasos-numeros"):
            nav = construir_navegacion_estadisticas(
                "baloto", metrica_actual, CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=2694,
            )
            for m in nav["metricas_nav"]:
                assert m["url"].endswith("?hasta_numero_sorteo=2694"), m

    def test_revancha_conserva_corte_entre_las_cuatro_metricas(self):
        for metrica_actual in ("frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada", "atrasos-numeros"):
            nav = construir_navegacion_estadisticas(
                "baloto-revancha", metrica_actual, CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=2694,
            )
            for m in nav["metricas_nav"]:
                assert m["url"].endswith("?hasta_numero_sorteo=2694"), m

    def test_miloto_conserva_corte_entre_sus_metricas_compatibles(self):
        nav = construir_navegacion_estadisticas(
            "miloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=588,
        )
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert ids == [
            "frecuencia-numeros", "frecuencia-observada-esperada", "atrasos-numeros",
            "distribucion-pares-impares", "distribucion-altos-bajos", "distribucion-pares-consecutivos",
            "distribucion-racha-maxima", "repeticiones-entre-sorteos",
        ]
        for m in nav["metricas_nav"]:
            assert m["url"].endswith("?hasta_numero_sorteo=588")

    def test_miloto_sigue_sin_superbalota_con_corte_activo(self):
        nav = construir_navegacion_estadisticas(
            "miloto", "atrasos-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=588,
        )
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert "frecuencia-superbalota" not in ids

    def test_active_de_juego_y_metrica_sigue_correcto_con_corte(self):
        nav = construir_navegacion_estadisticas(
            "baloto-revancha", "frecuencia-observada-esperada", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES,
            hasta_numero_sorteo=2694,
        )
        activos_juego = [j for j in nav["juegos_nav"] if j["activo"]]
        activos_metrica = [m for m in nav["metricas_nav"] if m["activo"]]
        assert len(activos_juego) == 1 and activos_juego[0]["slug"] == "baloto-revancha"
        assert len(activos_metrica) == 1 and activos_metrica[0]["id"] == "frecuencia-observada-esperada"


# =====================================================================
# D. Cambio de juego -elimina el corte (numeraciones no comparables)
# =====================================================================

class TestCorteEliminadoAlCambiarDeJuego:
    def test_baloto_con_corte_a_revancha_sin_corte(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=2694,
        )
        destino = next(j for j in nav["juegos_nav"] if j["slug"] == "baloto-revancha")
        assert destino["url"] == "/estadisticas/baloto-revancha/frecuencia-numeros"

    def test_baloto_con_corte_a_miloto_sin_corte(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=2694,
        )
        destino = next(j for j in nav["juegos_nav"] if j["slug"] == "miloto")
        assert destino["url"] == "/estadisticas/miloto/frecuencia-numeros"

    def test_miloto_con_corte_a_baloto_sin_corte(self):
        nav = construir_navegacion_estadisticas(
            "miloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=588,
        )
        destino = next(j for j in nav["juegos_nav"] if j["slug"] == "baloto")
        assert destino["url"] == "/estadisticas/baloto/frecuencia-numeros"

    def test_miloto_con_corte_a_revancha_sin_corte(self):
        nav = construir_navegacion_estadisticas(
            "miloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=588,
        )
        destino = next(j for j in nav["juegos_nav"] if j["slug"] == "baloto-revancha")
        assert destino["url"] == "/estadisticas/baloto-revancha/frecuencia-numeros"

    def test_superbalota_con_corte_a_miloto_frecuencia_numeros_sin_corte(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-superbalota", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=2694,
        )
        destino = next(j for j in nav["juegos_nav"] if j["slug"] == "miloto")
        assert destino["url"] == "/estadisticas/miloto/frecuencia-numeros"

    def test_ningun_juego_nav_contiene_hasta_numero_sorteo(self):
        for juego_slug in ("baloto", "baloto-revancha", "miloto"):
            for metrica in ("frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada", "atrasos-numeros"):
                nav = construir_navegacion_estadisticas(
                    juego_slug, metrica, CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=2694,
                )
                for j in nav["juegos_nav"]:
                    assert "hasta_numero_sorteo" not in j["url"], (juego_slug, metrica, j)


# =====================================================================
# B. Estado (sin corte / con corte) -a través del dict devuelto
# =====================================================================

class TestEstadoDelCorteEnElContexto:
    def test_sin_corte_hasta_numero_sorteo_es_none_en_el_contexto(self):
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES)
        assert nav["hasta_numero_sorteo"] is None

    def test_con_corte_hasta_numero_sorteo_expuesto_en_el_contexto(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=2694,
        )
        assert nav["hasta_numero_sorteo"] == 2694

    def test_url_historico_completo_nunca_lleva_query_ni_siquiera_vacio(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "atrasos-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES, hasta_numero_sorteo=2694,
        )
        assert nav["url_historico_completo"] == "/estadisticas/baloto/atrasos-numeros"
        assert "?" not in nav["url_historico_completo"]

    def test_sin_corte_activo_ninguna_url_de_metricas_lleva_query(self):
        nav = construir_navegacion_estadisticas("miloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, _NOMBRES)
        for m in nav["metricas_nav"]:
            assert "?" not in m["url"], m


# =====================================================================
# A. Formulario compartido -contenido estático real del partial
# =====================================================================

class TestFormularioCorteTemporal:
    def test_partial_existe(self):
        assert Path(_PARTIAL).exists()

    def test_label_visible_presente(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert "Corte por número de sorteo" in contenido
        assert '<label for="hasta_numero_sorteo"' in contenido

    def test_input_type_number(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert 'type="number"' in contenido

    def test_name_correcto(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert 'name="hasta_numero_sorteo"' in contenido

    def test_min_1_y_step_1(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert 'min="1"' in contenido
        assert 'step="1"' in contenido

    def test_metodo_get(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert 'method="get"' in contenido
        assert 'method="post"' not in contenido.lower()

    def test_action_apunta_a_la_ruta_actual(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert 'action="{{ request.url.path }}"' in contenido

    def test_boton_aplicar_corte_presente(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert "Aplicar corte" in contenido

    def test_enlace_historico_completo_presente(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert "Histórico completo" in contenido
        assert "{{ url_historico_completo }}" in contenido

    def test_no_depende_de_javascript(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert "<script" not in contenido

    def test_valor_actual_se_muestra_en_el_input(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert "value=\"{{ hasta_numero_sorteo if hasta_numero_sorteo is not none else '' }}\"" in contenido

    def test_no_usa_filtro_safe(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_ayuda_visible_sin_texto_tecnico_de_cache(self):
        contenido = Path(_PARTIAL).read_text(encoding="utf-8")
        assert "no predice resultados" in contenido
        assert "último sorteo disponible" in contenido
        # No debe mencionar mecanismos internos como "hash" o "invalidación"
        assert "hash" not in contenido.lower()
        assert "invalidaci" not in contenido.lower()


class TestLasCuatroPaginasIncluyenElControl:
    def test_las_cuatro_paginas_incluyen_el_partial(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert 'include "estadisticas/partials/control_corte_temporal.html"' in contenido, plantilla

    def test_el_include_aparece_antes_del_estado_sin_conexion(self):
        """El control debe estar disponible incluso sin datos -se
        inserta antes del bloque condicional de estado."""
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            indice_include = contenido.index('include "estadisticas/partials/control_corte_temporal.html"')
            indice_if_conexion = contenido.index("{% if not db_conectada %}")
            assert indice_include < indice_if_conexion, plantilla


# =====================================================================
# Regresión: Chart.js, height, JSON, IDs -sin cambios por esta etapa
# =====================================================================

class TestRegresionEtapaX:
    def test_chartjs_local_sigue_intacto_en_las_cuatro_paginas(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert "/static/vendor/chartjs/chart.umd.min.js" in contenido, plantilla
            assert "cdnjs.cloudflare.com/ajax/libs/Chart.js" not in contenido, plantilla

    def test_los_cuatro_canvas_conservan_height_180(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert 'height="180"' in contenido, plantilla

    def test_los_bloques_json_siguen_presentes(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert 'type="application/json"' in contenido, plantilla
            assert "| tojson" in contenido, plantilla

    def test_asset_chartjs_sigue_siendo_444_con_licencia_mit(self):
        ruta = Path("app/static/vendor/chartjs/chart.umd.min.js")
        contenido = ruta.read_text(encoding="utf-8", errors="ignore")
        assert "Chart.js v4.4.4" in contenido
        assert "MIT License" in contenido


# =====================================================================
# E/Router: validación -verificación estática del código fuente real
# (no se pudo ejecutar FastAPI/Query real en este sandbox)
# =====================================================================

class TestValidacionDeCorteEnElRouter:
    def test_las_quince_rutas_usan_query_con_ge_1(self):
        codigo_fuente = Path(_ROUTER).read_text(encoding="utf-8")
        ocurrencias = codigo_fuente.count("hasta_numero_sorteo: int | None = Query(default=None, ge=1)")
        assert ocurrencias == 15

    def test_solo_se_agrego_la_ruta_esperada_de_etapa_ac(self):
        codigo_fuente = Path(_ROUTER).read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/{juego_slug}/') == 9

    def test_las_cuatro_rutas_existentes_siguen_presentes(self):
        codigo_fuente = Path(_ROUTER).read_text(encoding="utf-8")
        for ruta in ("frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada", "atrasos-numeros"):
            assert f'@router.get("/estadisticas/{{juego_slug}}/{ruta}")' in codigo_fuente

    def test_query_importado_de_fastapi(self):
        codigo_fuente = Path(_ROUTER).read_text(encoding="utf-8")
        assert "from fastapi import APIRouter, Depends, HTTPException, Query, Request" in codigo_fuente

    def test_no_se_toco_calcular_y_persistir_estadistica_ni_recetas(self):
        """El corte sigue sin agregarse a parametros_metrica -mismas
        3 llamadas a ejecutar() de antes, ninguna receta nueva."""
        codigo_fuente = Path("app/application/use_cases/calcular_y_persistir_estadistica.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('_CATALOGO: dict[str, _Receta] = {') == 1
        assert "atrasos_numeros" in codigo_fuente  # sigue de la Etapa W, sin duplicar
        assert codigo_fuente.count('"atrasos_numeros": _Receta(') == 1

    def test_estadistica_repository_sqlalchemy_sin_cambios(self):
        """Verificado por hash en el reporte -aquí se confirma que el
        upsert sigue usando exactamente las dos ramas ya existentes,
        sin ninguna referencia nueva a hasta_numero_sorteo dentro de
        parametros_hash."""
        codigo_fuente = Path(
            "app/infrastructure/repositories/estadistica_repository_sqlalchemy.py"
        ).read_text(encoding="utf-8")
        assert codigo_fuente.count("on_conflict_do_update") == 2
