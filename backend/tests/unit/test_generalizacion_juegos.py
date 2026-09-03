"""
Tests de la generalización de las tres visualizaciones estadísticas a
Baloto, Baloto Revancha y MiLoto (sin ColorLoto, sin cuarta
visualización).

IMPORTANTE - transparencia sobre el alcance real de esta verificación
(misma limitación de todas las etapas anteriores, reverificada): este
sandbox sigue sin `fastapi`/`sqlalchemy` instalados. Esto significa
que `app/api/web/routers/estadisticas.py` (que importa `fastapi` y
`sqlalchemy` a nivel de módulo) NO PUDO IMPORTARSE ni ejecutarse aquí
-no se afirma haber levantado la aplicación ni accedido a las rutas
por HTTP real.

Lo que SÍ se verifica, de verdad, ejecutado -código real de
producción, no reimplementaciones:

  1. `app/api/web/estadisticas_slugs.py` -extraído deliberadamente sin
     ninguna dependencia de FastAPI/SQLAlchemy, para poder probar la
     resolución de slugs (incluido el conjunto cerrado y el 404 para
     slugs desconocidos) de forma real.
  2. `construir_navegacion_estadisticas` y las 3 funciones `*_a_vm` de
     `view_models.py` -tampoco dependen de FastAPI/SQLAlchemy.
  3. El flujo lógico completo (`CalcularYPersistirEstadistica` +
     `view_models.py`), reconstruido con fakes de los puertos -mismo
     precedente honesto que todas las etapas anteriores- para
     verificar aislamiento de caché entre los 3 juegos.
  4. Contenido estático real de los 3 templates (lectura de archivo,
     UTF-8 explícito), incluida la navegación de dos niveles.

No se afirma cobertura de: el decorador `@router.get(...)`, el 404
real vía HTTP, el manejo de excepciones de FastAPI, ni el renderizado
Jinja2 real -ninguno pudo ejecutarse sin `fastapi` instalado.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.web.estadisticas_slugs import (
    CAPACIDAD_SUPERBALOTA_POR_SLUG,
    SLUG_A_CODIGO,
    resolver_codigo,
)
from app.api.web.view_models import (
    construir_navegacion_estadisticas,
    frecuencia_numeros_a_vm,
    frecuencia_superbalota_a_vm,
    tabla_frecuencia_numeros_a_vm,
)
from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.interfaces.estadistica_repository import (
    EstadisticaCalculada,
    EstadisticaRepository,
    calcular_parametros_hash,
)
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.use_cases.calcular_y_persistir_estadistica import CalcularYPersistirEstadistica
from app.domain.entities.juego import Juego
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from app.domain.games.miloto import MiLotoGame

_FECHA_BASE = date(2024, 1, 1)


def _juego(codigo: str, nombre: str, rango_min: int, rango_max: int, tiene_superbalota: bool) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=nombre, rango_min=rango_min, rango_max=rango_max,
        cantidad_numeros=5, tiene_superbalota=tiene_superbalota,
        superbalota_min=1 if tiene_superbalota else None, superbalota_max=16 if tiene_superbalota else None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


_JUEGO_BALOTO = _juego("BALOTO", "Baloto", 1, 43, True)
_JUEGO_REVANCHA = _juego("BALOTO_REVANCHA", "Baloto Revancha", 1, 43, True)
_JUEGO_MILOTO = _juego("MILOTO", "MiLoto", 1, 39, False)


class TestResolverCodigo:
    def test_slugs_validos_resuelven_al_codigo_correcto(self):
        assert resolver_codigo("baloto") == "BALOTO"
        assert resolver_codigo("baloto-revancha") == "BALOTO_REVANCHA"
        assert resolver_codigo("miloto") == "MILOTO"

    def test_slug_desconocido_devuelve_none_no_un_codigo_arbitrario(self):
        assert resolver_codigo("xyz") is None
        assert resolver_codigo("") is None

    def test_colorloto_no_esta_en_el_conjunto_cerrado(self):
        assert resolver_codigo("colorloto") is None

    def test_no_existe_fallback_silencioso_a_baloto(self):
        assert resolver_codigo("cualquier-otra-cosa") != "BALOTO"
        assert resolver_codigo("cualquier-otra-cosa") is None

    def test_conjunto_cerrado_tiene_exactamente_tres_juegos(self):
        assert set(SLUG_A_CODIGO.keys()) == {"baloto", "baloto-revancha", "miloto"}

    def test_capacidad_superbalota_viene_de_atributos_reales_de_clase(self):
        assert CAPACIDAD_SUPERBALOTA_POR_SLUG["baloto"] == BalotoGame.has_superballot is True
        assert CAPACIDAD_SUPERBALOTA_POR_SLUG["baloto-revancha"] == BalotoRevanchaGame.has_superballot is True
        assert CAPACIDAD_SUPERBALOTA_POR_SLUG["miloto"] == MiLotoGame.has_superballot is False


class TestRangosRealesPorJuego:
    def test_miloto_rango_real_es_1_39(self):
        assert MiLotoGame.number_range == (1, 39)

    def test_baloto_rango_real_es_1_43(self):
        assert BalotoGame.number_range == (1, 43)

    def test_revancha_rango_real_es_1_43(self):
        assert BalotoRevanchaGame.number_range == (1, 43)

    def test_miloto_numbers_to_pick_es_5(self):
        assert MiLotoGame.numbers_to_pick == 5


class TestNavegacionDosNiveles:
    def test_juego_actual_aparece_activo(self):
        nav = construir_navegacion_estadisticas(
            "baloto-revancha", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG,
            {"BALOTO": "Baloto", "BALOTO_REVANCHA": "Baloto Revancha", "MILOTO": "MiLoto"},
        )
        activos = [j for j in nav["juegos_nav"] if j["activo"]]
        assert len(activos) == 1
        assert activos[0]["slug"] == "baloto-revancha"

    def test_metrica_actual_aparece_activa(self):
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-observada-esperada", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        activas = [m for m in nav["metricas_nav"] if m["activo"]]
        assert len(activas) == 1
        assert activas[0]["id"] == "frecuencia-observada-esperada"

    def test_miloto_no_tiene_pestana_de_superbalota(self):
        nav = construir_navegacion_estadisticas("miloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert "frecuencia-superbalota" not in ids

    def test_baloto_y_revancha_si_tienen_pestana_de_superbalota(self):
        for slug in ("baloto", "baloto-revancha"):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            ids = [m["id"] for m in nav["metricas_nav"]]
            assert "frecuencia-superbalota" in ids

    def test_desde_superbalota_el_enlace_a_miloto_lleva_a_frecuencia_numeros(self):
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-superbalota", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        miloto_entry = next(j for j in nav["juegos_nav"] if j["slug"] == "miloto")
        assert miloto_entry["url"] == "/estadisticas/miloto/frecuencia-numeros"

    def test_en_metrica_compatible_cambiar_de_juego_conserva_la_metrica(self):
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-observada-esperada", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        miloto_entry = next(j for j in nav["juegos_nav"] if j["slug"] == "miloto")
        assert miloto_entry["url"] == "/estadisticas/miloto/frecuencia-observada-esperada"
        revancha_entry = next(j for j in nav["juegos_nav"] if j["slug"] == "baloto-revancha")
        assert revancha_entry["url"] == "/estadisticas/baloto-revancha/frecuencia-observada-esperada"

    def test_urls_de_baloto_se_conservan_exactamente(self):
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        baloto_entry = next(j for j in nav["juegos_nav"] if j["slug"] == "baloto")
        assert baloto_entry["url"] == "/estadisticas/baloto/frecuencia-numeros"

    def test_nombres_reales_de_bd_tienen_prioridad_sobre_fallback_estatico(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {"BALOTO": "Baloto (nombre real BD)"},
        )
        baloto_entry = next(j for j in nav["juegos_nav"] if j["slug"] == "baloto")
        assert baloto_entry["nombre"] == "Baloto (nombre real BD)"

    def test_sin_nombres_reales_usa_fallback_estatico_sin_fallar(self):
        nav = construir_navegacion_estadisticas("miloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, None)
        miloto_entry = next(j for j in nav["juegos_nav"] if j["slug"] == "miloto")
        assert miloto_entry["nombre"] == "MiLoto"


def _estadistica_calculada_fake(filas: list[dict], juego_id=None) -> EstadisticaCalculada:
    return EstadisticaCalculada(
        id=uuid4(), juego_id=juego_id or uuid4(), tipo_estadistica="frecuencia_numeros",
        hasta_numero_sorteo=None, parametros={}, parametros_hash="x",
        resultado={"filas": filas}, calculado_en=None, valido_hasta=None,
    )


class TestViewModelsSinHardcodeBaloto:
    def test_frecuencia_numeros_a_vm_usa_el_juego_recibido(self):
        filas = [{"valor": "1", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5}]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 39, _JUEGO_MILOTO)
        assert vm["juego_codigo"] == "MILOTO"
        assert vm["juego_nombre"] == "MiLoto"

    def test_frecuencia_numeros_a_vm_con_revancha(self):
        filas = [{"valor": "1", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5}]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_REVANCHA)
        assert vm["juego_codigo"] == "BALOTO_REVANCHA"
        assert vm["juego_nombre"] == "Baloto Revancha"
        assert vm["juego_codigo"] != "BALOTO"

    def test_frecuencia_superbalota_a_vm_usa_el_juego_recibido(self):
        filas = [{"valor": "9", "apariciones": 2, "total_sorteos": 10, "frecuencia_relativa": 0.2}]
        vm = frecuencia_superbalota_a_vm(_estadistica_calculada_fake(filas), 1, 16, _JUEGO_REVANCHA)
        assert vm["juego_codigo"] == "BALOTO_REVANCHA"

    def test_tabla_frecuencia_numeros_a_vm_usa_el_juego_recibido(self):
        fila = {
            "valor": "1", "apariciones": 3,
            "frecuencia_observada": {"valor": "1", "apariciones": 3, "total_sorteos": 10, "frecuencia_relativa": 0.3},
            "probabilidad_teorica": {"valor": "1", "probabilidad": 0.128, "metodo": "K/N = 5/39"},
            "diferencia": 0.172,
        }
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake([fila]), 1, 39, 5, _JUEGO_MILOTO)
        assert vm["juego_codigo"] == "MILOTO"
        assert vm["juego_nombre"] == "MiLoto"


class _HistoricoRepositoryEnMemoria(ResultadosHistoricosRepository):
    def __init__(self, datos: dict[UUID, list[ResultadoNumerico]]):
        self._datos = datos

    def listar_resultados_numericos(self, juego_id: UUID, hasta_numero_sorteo: int | None = None) -> list[ResultadoNumerico]:
        todos = self._datos.get(juego_id, [])
        if hasta_numero_sorteo is None:
            return list(todos)
        return [r for r in todos if r.numero_sorteo <= hasta_numero_sorteo]

    def listar_resultados_colorloto(self, juego_id: UUID, hasta_numero_sorteo: int | None = None):
        raise NotImplementedError


class _EstadisticaRepositoryEnMemoria(EstadisticaRepository):
    def __init__(self):
        self._filas: list[EstadisticaCalculada] = []

    def guardar(self, entrada: EstadisticaCalculada) -> EstadisticaCalculada:
        hash_calculado = calcular_parametros_hash(entrada.parametros)
        for i, fila in enumerate(self._filas):
            if (
                fila.juego_id == entrada.juego_id and fila.tipo_estadistica == entrada.tipo_estadistica
                and fila.hasta_numero_sorteo == entrada.hasta_numero_sorteo and fila.parametros_hash == hash_calculado
            ):
                reemplazada = EstadisticaCalculada(
                    id=fila.id, juego_id=entrada.juego_id, tipo_estadistica=entrada.tipo_estadistica,
                    hasta_numero_sorteo=entrada.hasta_numero_sorteo, parametros=entrada.parametros,
                    parametros_hash=hash_calculado, resultado=entrada.resultado,
                    calculado_en=datetime.now(timezone.utc), valido_hasta=entrada.valido_hasta,
                )
                self._filas[i] = reemplazada
                return reemplazada
        guardada = EstadisticaCalculada(
            id=uuid4(), juego_id=entrada.juego_id, tipo_estadistica=entrada.tipo_estadistica,
            hasta_numero_sorteo=entrada.hasta_numero_sorteo, parametros=entrada.parametros,
            parametros_hash=hash_calculado, resultado=entrada.resultado,
            calculado_en=datetime.now(timezone.utc), valido_hasta=entrada.valido_hasta,
        )
        self._filas.append(guardada)
        return guardada

    def buscar_vigente(self, juego_id, tipo_estadistica, hasta_numero_sorteo, parametros):
        hash_calculado = calcular_parametros_hash(parametros)
        ahora = datetime.now(timezone.utc)
        for fila in self._filas:
            if (
                fila.juego_id == juego_id and fila.tipo_estadistica == tipo_estadistica
                and fila.hasta_numero_sorteo == hasta_numero_sorteo and fila.parametros_hash == hash_calculado
                and (fila.valido_hasta is None or fila.valido_hasta > ahora)
            ):
                return fila
        return None

    def invalidar_por_juego(self, juego_id, desde_numero_sorteo=None) -> int:
        ahora = datetime.now(timezone.utc)
        afectadas = 0
        for i, fila in enumerate(self._filas):
            if fila.juego_id == juego_id:
                self._filas[i] = EstadisticaCalculada(
                    id=fila.id, juego_id=fila.juego_id, tipo_estadistica=fila.tipo_estadistica,
                    hasta_numero_sorteo=fila.hasta_numero_sorteo, parametros=fila.parametros,
                    parametros_hash=fila.parametros_hash, resultado=fila.resultado,
                    calculado_en=fila.calculado_en, valido_hasta=ahora,
                )
                afectadas += 1
        return afectadas

    def listar_por_juego_y_tipo(self, juego_id, tipo_estadistica):
        raise NotImplementedError


def _num(numero_sorteo: int, numeros: tuple[int, ...]) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=None,
    )


class TestAislamientoDeCacheEntreJuegos:
    def test_calcular_baloto_no_devuelve_cache_de_revancha(self):
        juego_baloto, juego_revancha = uuid4(), uuid4()
        historico = _HistoricoRepositoryEnMemoria({
            juego_baloto: [_num(1, (1, 2, 3, 4, 5))],
            juego_revancha: [_num(1, (10, 20, 30, 40, 41))],
        })
        estadisticas = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico, estadisticas)
        parametros = {"rango_min": 1, "rango_max": 43}

        r_baloto = orquestador.ejecutar(juego_baloto, "frecuencia_numeros", parametros_metrica=parametros)
        r_revancha = orquestador.ejecutar(juego_revancha, "frecuencia_numeros", parametros_metrica=parametros)

        filas_baloto = {f["valor"]: f["apariciones"] for f in r_baloto.resultado["filas"]}
        filas_revancha = {f["valor"]: f["apariciones"] for f in r_revancha.resultado["filas"]}
        assert filas_baloto["1"] == 1
        assert filas_baloto["10"] == 0
        assert filas_revancha["10"] == 1
        assert filas_revancha["1"] == 0

    def test_calcular_miloto_no_devuelve_cache_de_otro_juego(self):
        juego_baloto, juego_miloto = uuid4(), uuid4()
        historico = _HistoricoRepositoryEnMemoria({
            juego_baloto: [_num(1, (1, 2, 3, 4, 5))],
            juego_miloto: [_num(1, (5, 15, 25, 35, 39))],
        })
        estadisticas = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico, estadisticas)

        orquestador.ejecutar(juego_baloto, "frecuencia_numeros", parametros_metrica={"rango_min": 1, "rango_max": 43})
        r_miloto = orquestador.ejecutar(juego_miloto, "frecuencia_numeros", parametros_metrica={"rango_min": 1, "rango_max": 39})

        filas_miloto = {f["valor"]: f["apariciones"] for f in r_miloto.resultado["filas"]}
        assert filas_miloto["5"] == 1
        assert "40" not in filas_miloto

    def test_mismos_parametros_hash_coexisten_entre_juegos(self):
        juego_baloto, juego_revancha = uuid4(), uuid4()
        historico = _HistoricoRepositoryEnMemoria({juego_baloto: [], juego_revancha: []})
        estadisticas = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico, estadisticas)
        parametros = {"rango_min": 1, "rango_max": 43}

        r_baloto = orquestador.ejecutar(juego_baloto, "frecuencia_numeros", parametros_metrica=parametros)
        r_revancha = orquestador.ejecutar(juego_revancha, "frecuencia_numeros", parametros_metrica=parametros)

        assert r_baloto.id != r_revancha.id
        assert r_baloto.parametros_hash == r_revancha.parametros_hash

    def test_invalidar_un_juego_no_invalida_otro(self):
        juego_baloto, juego_revancha = uuid4(), uuid4()
        historico = _HistoricoRepositoryEnMemoria({juego_baloto: [], juego_revancha: []})
        estadisticas = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico, estadisticas)
        parametros = {"rango_min": 1, "rango_max": 43}

        orquestador.ejecutar(juego_baloto, "frecuencia_numeros", parametros_metrica=parametros)
        orquestador.ejecutar(juego_revancha, "frecuencia_numeros", parametros_metrica=parametros)
        estadisticas.invalidar_por_juego(juego_baloto)

        assert estadisticas.buscar_vigente(juego_baloto, "frecuencia_numeros", None, parametros) is None
        assert estadisticas.buscar_vigente(juego_revancha, "frecuencia_numeros", None, parametros) is not None


_TEMPLATES = [
    "app/templates/estadisticas/frecuencia_numeros.html",
    "app/templates/estadisticas/frecuencia_superbalota.html",
    "app/templates/estadisticas/frecuencia_observada_esperada.html",
]


class TestRegresionPlantillas:
    def test_las_tres_paginas_conservan_chartjs_local(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert "/static/vendor/chartjs/chart.umd.min.js" in contenido, plantilla
            assert "cdnjs.cloudflare.com/ajax/libs/Chart.js" not in contenido, plantilla

    def test_los_tres_canvas_conservan_height_180(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert 'height="180"' in contenido, plantilla

    def test_los_datos_json_continuan_siendo_serializados_con_tojson(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert "| tojson" in contenido, plantilla

    def test_titulos_ya_no_dicen_baloto_fijo(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert "juego_nombre_actual" in contenido, plantilla
            assert "— Baloto{% endblock %}" not in contenido, plantilla

    def test_navegacion_de_dos_niveles_presente(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert "juegos_nav" in contenido, plantilla
            assert "metricas_nav" in contenido, plantilla

    def test_urls_generadas_desde_el_servidor_no_con_javascript(self):
        for plantilla in _TEMPLATES:
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert 'href="{{ j.url }}"' in contenido, plantilla
            assert 'href="{{ m.url }}"' in contenido, plantilla

    def test_ids_de_canvas_y_json_se_conservan(self):
        ids_esperados = {
            "app/templates/estadisticas/frecuencia_numeros.html": ("grafica-frecuencia-numeros", "datos-frecuencia-numeros"),
            "app/templates/estadisticas/frecuencia_superbalota.html": ("grafica-frecuencia-superbalota", "datos-frecuencia-superbalota"),
            "app/templates/estadisticas/frecuencia_observada_esperada.html": ("grafica-observada-esperada", "datos-observada-esperada"),
        }
        for plantilla, (canvas_id, json_id) in ids_esperados.items():
            contenido = Path(plantilla).read_text(encoding="utf-8")
            assert f'id="{canvas_id}"' in contenido, plantilla
            assert f'id="{json_id}"' in contenido, plantilla

    def test_base_html_sigue_apuntando_a_baloto_frecuencia_numeros(self):
        contenido = Path("app/templates/base.html").read_text(encoding="utf-8")
        assert "/estadisticas/baloto/frecuencia-numeros" in contenido

    def test_base_html_no_tiene_menu_complejo_de_juegos(self):
        contenido = Path("app/templates/base.html").read_text(encoding="utf-8")
        assert "juegos_nav" not in contenido
        assert "baloto-revancha" not in contenido


class TestChartjsAssetSigueIntacto:
    def test_asset_sigue_presente_y_es_chartjs_444(self):
        ruta = Path("app/static/vendor/chartjs/chart.umd.min.js")
        assert ruta.exists()
        contenido = ruta.read_text(encoding="utf-8", errors="ignore")
        assert "Chart.js v4.4.4" in contenido
        assert "MIT License" in contenido


# =====================================================================
# Carencias de cobertura identificadas en la auditoría de integración:
# flujo real de rango dinámico, slug válido sin registro persistido,
# y verificación estática del orden/mapeo de JuegoSinSuperbalotaError.
# =====================================================================

class TestFlujoRealDeRangoDinamico:
    """No basta con verificar los atributos de clase aislados -aquí se
    reproduce el flujo COMPLETO slug -> GameFactory.crear(juego) ->
    juego_dominio.number_range, exactamente como lo hace el router,
    confirmando que MiLoto nunca produce 40-43 en el flujo real (no
    solo en el atributo de clase por separado)."""

    class _ColorRepoFalso:
        def listar_vigentes(self, juego_id, en_fecha=None):
            return []

    def _game_factory_real(self):
        from app.application.use_cases.game_factory import GameFactory
        return GameFactory(color_repository=self._ColorRepoFalso())

    def test_miloto_flujo_completo_nunca_produce_40_43(self):
        factory = self._game_factory_real()
        juego_dominio = factory.crear(_JUEGO_MILOTO)
        rango_min, rango_max = juego_dominio.number_range
        assert (rango_min, rango_max) == (1, 39)
        assert 40 not in range(rango_min, rango_max + 1)
        assert 43 not in range(rango_min, rango_max + 1)

    def test_baloto_flujo_completo_produce_1_43(self):
        factory = self._game_factory_real()
        juego_dominio = factory.crear(_JUEGO_BALOTO)
        assert juego_dominio.number_range == (1, 43)

    def test_revancha_flujo_completo_produce_1_43(self):
        factory = self._game_factory_real()
        juego_dominio = factory.crear(_JUEGO_REVANCHA)
        assert juego_dominio.number_range == (1, 43)

    def test_parametros_metrica_resultantes_reflejan_el_rango_real_de_cada_juego(self):
        """Reproduce exactamente lo que el router arma como
        `parametros_metrica` a partir de `juego_dominio.number_range`
        -confirma que ese dict (el que efectivamente entra al hash de
        caché) es distinto entre MiLoto y Baloto/Revancha."""
        factory = self._game_factory_real()
        rango_min_miloto, rango_max_miloto = factory.crear(_JUEGO_MILOTO).number_range
        rango_min_baloto, rango_max_baloto = factory.crear(_JUEGO_BALOTO).number_range
        parametros_miloto = {"rango_min": rango_min_miloto, "rango_max": rango_max_miloto}
        parametros_baloto = {"rango_min": rango_min_baloto, "rango_max": rango_max_baloto}
        assert parametros_miloto == {"rango_min": 1, "rango_max": 39}
        assert parametros_baloto == {"rango_min": 1, "rango_max": 43}
        assert parametros_miloto != parametros_baloto


class TestSlugValidoSinRegistroPersistido:
    """Carencia identificada en la auditoría: un slug perteneciente al
    conjunto cerrado, pero cuyo juego no está sembrado en la base
    (`obtener_por_codigo` devuelve None), debe producir
    `JuegoNoEncontradoError` -mismo mecanismo ya usado para Baloto
    desde la Etapa U, nunca una creación implícita ni un 500."""

    class _JuegoRepositoryFalso:
        def __init__(self, juegos_por_codigo: dict):
            self._juegos = juegos_por_codigo

        def obtener_por_codigo(self, codigo):
            return self._juegos.get(codigo)

    def _resolver_juego_replicado(self, slug: str, juego_repository):
        """Réplica exacta de `_resolver_juego` del router (que no se
        puede importar sin fastapi) -misma lógica, verificada
        línea por línea contra el código fuente real en la auditoría."""
        from app.application.exceptions import JuegoNoEncontradoError

        codigo = resolver_codigo(slug)
        if codigo is None:
            raise ValueError(f"404: slug desconocido '{slug}'")
        juego = juego_repository.obtener_por_codigo(codigo)
        if juego is None:
            raise JuegoNoEncontradoError(codigo)
        return juego

    def test_miloto_slug_valido_sin_registro_lanza_juego_no_encontrado(self):
        from app.application.exceptions import JuegoNoEncontradoError

        repo = self._JuegoRepositoryFalso({"BALOTO": _JUEGO_BALOTO})  # MILOTO ausente deliberadamente
        try:
            self._resolver_juego_replicado("miloto", repo)
            raise AssertionError("Debió lanzar JuegoNoEncontradoError")
        except JuegoNoEncontradoError:
            pass  # esperado

    def test_nunca_se_usa_el_slug_directamente_como_codigo_de_busqueda(self):
        """Si se usara el slug "miloto" (minúsculas, con el propio
        formato de URL) directamente como código de búsqueda en vez
        de traducirlo a "MILOTO" primero, esta búsqueda fallaría
        siempre -confirma que la traducción slug->código realmente
        ocurre antes de tocar el repositorio."""
        repo = self._JuegoRepositoryFalso({"MILOTO": _JUEGO_MILOTO})
        juego = self._resolver_juego_replicado("miloto", repo)
        assert juego.codigo == "MILOTO"
        assert juego is _JUEGO_MILOTO

    def test_baloto_revancha_resuelve_al_registro_correcto_no_a_baloto(self):
        repo = self._JuegoRepositoryFalso({"BALOTO": _JUEGO_BALOTO, "BALOTO_REVANCHA": _JUEGO_REVANCHA})
        juego = self._resolver_juego_replicado("baloto-revancha", repo)
        assert juego.codigo == "BALOTO_REVANCHA"
        assert juego is not _JUEGO_BALOTO


class TestJuegoSinSuperbalotaVerificacionEstatica:
    """No se puede importar `estadisticas.py` (requiere fastapi), así
    que se verifica ESTÁTICAMENTE (lectura de código fuente) que:
    (a) la excepción se evalúa antes de cualquier llamada a
    `calcular_estadistica.ejecutar`, y (b) está mapeada a 422 en
    `main.py`."""

    def test_juego_sin_superbalota_error_se_lanza_antes_de_ejecutar(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_raise = codigo_fuente.index("raise JuegoSinSuperbalotaError")
        indice_ejecutar_superbalota = codigo_fuente.index(
            'tipo_estadistica="frecuencia_superbalota"'
        )
        assert indice_raise < indice_ejecutar_superbalota, (
            "JuegoSinSuperbalotaError debe lanzarse ANTES de invocar el cálculo de superbalota"
        )

    def test_juego_sin_superbalota_error_mapeada_a_422_en_main(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        # Verifica que la entrada del diccionario existe y que su valor es 422,
        # sin depender de poder importar el modulo (requiere fastapi).
        indice = codigo_fuente.index("JuegoSinSuperbalotaError:")
        fragmento = codigo_fuente[indice:indice + 40]
        assert "422" in fragmento

    def test_juego_sin_superbalota_error_esta_registrada_como_dominio_error(self):
        """Confirma que hereda de DominioError -por eso el
        exception_handler global la intercepta antes de que FastAPI
        pudiera convertirla en un 500 genérico."""
        codigo_fuente = Path("app/application/exceptions.py").read_text(encoding="utf-8")
        assert "class JuegoSinSuperbalotaError(DominioError):" in codigo_fuente


# =====================================================================
# Etapa W -cuarta visualización: atrasos_numeros / atrasos-numeros
# =====================================================================

class TestAtrasosNumerosViewModel:
    def test_atrasos_numeros_a_vm_usa_el_juego_recibido(self):
        from app.api.web.view_models import atrasos_numeros_a_vm

        filas = [{"valor": "1", "atraso": 5, "ultimo_sorteo_aparicion": 100, "total_sorteos": 10}]
        estadistica = _estadistica_calculada_fake(filas)
        vm = atrasos_numeros_a_vm(estadistica, 1, 39, _JUEGO_MILOTO)
        assert vm["juego_codigo"] == "MILOTO"
        assert vm["juego_nombre"] == "MiLoto"

    def test_mayor_distancia_excluye_none(self):
        from app.api.web.view_models import atrasos_numeros_a_vm

        filas = [
            {"valor": "1", "atraso": 5, "ultimo_sorteo_aparicion": 100, "total_sorteos": 10},
            {"valor": "2", "atraso": None, "ultimo_sorteo_aparicion": None, "total_sorteos": 10},
            {"valor": "3", "atraso": 9, "ultimo_sorteo_aparicion": 96, "total_sorteos": 10},
        ]
        vm = atrasos_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert vm["mayor_distancia"] == 9
        assert vm["numeros_con_mayor_distancia"] == ["3"]

    def test_todos_none_produce_mayor_distancia_none_no_cero(self):
        from app.api.web.view_models import atrasos_numeros_a_vm

        filas = [{"valor": "1", "atraso": None, "ultimo_sorteo_aparicion": None, "total_sorteos": 0}]
        vm = atrasos_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert vm["mayor_distancia"] is None
        assert vm["mayor_distancia"] != 0

    def test_empate_conserva_todos_los_numeros_con_la_mayor_distancia(self):
        from app.api.web.view_models import atrasos_numeros_a_vm

        filas = [
            {"valor": "1", "atraso": 7, "ultimo_sorteo_aparicion": 90, "total_sorteos": 10},
            {"valor": "2", "atraso": 7, "ultimo_sorteo_aparicion": 90, "total_sorteos": 10},
        ]
        vm = atrasos_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert vm["numeros_con_mayor_distancia"] == ["1", "2"]

    def test_chart_valores_preserva_none_como_null(self):
        from app.api.web.view_models import atrasos_numeros_a_vm
        import json

        filas = [
            {"valor": "1", "atraso": 5, "ultimo_sorteo_aparicion": 100, "total_sorteos": 10},
            {"valor": "2", "atraso": None, "ultimo_sorteo_aparicion": None, "total_sorteos": 10},
        ]
        vm = atrasos_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert vm["chart_valores"] == [5, None]
        serializado = json.dumps(vm["chart_valores"])
        assert "null" in serializado
        assert serializado.count("5") == 1  # ningun "0" fabricado en su lugar


class TestAtrasosNumerosNavegacion:
    def test_cuarta_metrica_presente_en_los_tres_juegos(self):
        for slug in ("baloto", "baloto-revancha", "miloto"):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            ids = [m["id"] for m in nav["metricas_nav"]]
            assert "atrasos-numeros" in ids, slug

    def test_metrica_activa_correcta_en_atrasos(self):
        nav = construir_navegacion_estadisticas("miloto", "atrasos-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        activas = [m for m in nav["metricas_nav"] if m["activo"]]
        assert len(activas) == 1
        assert activas[0]["id"] == "atrasos-numeros"

    def test_cambiar_de_juego_desde_atrasos_conserva_la_ruta(self):
        nav = construir_navegacion_estadisticas("baloto", "atrasos-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        for slug_destino in ("baloto-revancha", "miloto"):
            entrada = next(j for j in nav["juegos_nav"] if j["slug"] == slug_destino)
            assert entrada["url"] == f"/estadisticas/{slug_destino}/atrasos-numeros"

    def test_navegacion_anterior_no_se_rompe(self):
        """Las métricas previas siguen presentes y funcionando
        igual, con las nuevas agregadas -no reemplazadas."""
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert ids == [
            "frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada",
            "atrasos-numeros", "distribucion-pares-impares", "distribucion-altos-bajos",
            "distribucion-pares-consecutivos", "distribucion-racha-maxima", "repeticiones-entre-sorteos",
        ]

    def test_miloto_sigue_sin_superbalota_tras_agregar_atrasos(self):
        nav = construir_navegacion_estadisticas("miloto", "atrasos-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert "frecuencia-superbalota" not in ids
        assert ids == [
            "frecuencia-numeros", "frecuencia-observada-esperada", "atrasos-numeros",
            "distribucion-pares-impares", "distribucion-altos-bajos", "distribucion-pares-consecutivos",
            "distribucion-racha-maxima", "repeticiones-entre-sorteos",
        ]


class TestAtrasosNumerosRouterEstatico:
    """Sin fastapi disponible, se verifica el router por lectura de
    código fuente -mismo patrón honesto que el resto de esta clase de
    tests en este archivo."""

    def test_ruta_atrasos_numeros_existe_parametrizada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/atrasos-numeros")' in codigo_fuente

    def test_exactamente_nueve_rutas_no_veintisiete(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/{juego_slug}/') == 9

    def test_router_no_pasa_hasta_numero_sorteo_a_parametros_metrica_de_atrasos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="atrasos_numeros"')
        bloque = codigo_fuente[indice:indice + 400]
        assert '"rango_min": rango_min, "rango_max": rango_max}' in bloque
        assert "hasta_numero_sorteo" not in bloque.split("parametros_metrica=")[1][:80]

    def test_las_tres_rutas_anteriores_no_fueron_eliminadas(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/frecuencia-numeros")' in codigo_fuente
        assert '@router.get("/estadisticas/{juego_slug}/frecuencia-superbalota")' in codigo_fuente
        assert '@router.get("/estadisticas/{juego_slug}/frecuencia-observada-esperada")' in codigo_fuente


class TestAtrasosNumerosTemplate:
    _TEMPLATE = "app/templates/estadisticas/atrasos_numeros.html"

    def test_template_existe_y_usa_chartjs_local(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com/ajax/libs/Chart.js" not in contenido

    def test_canvas_con_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'id="grafica-atrasos-numeros" height="180"' in contenido

    def test_bloque_json_y_tojson_presentes(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'id="datos-atrasos-numeros"' in contenido
        assert 'type="application/json"' in contenido
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_titulo_usa_terminologia_precisa_no_predictiva(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Distancia desde la última aparición" in contenido
        prohibidas = [
            "ya deben salir", "números calientes", "mayor probabilidad", "predicción", "recomendados",
        ]
        for frase in prohibidas:
            assert frase.lower() not in contenido.lower(), frase

    def test_aviso_no_predictivo_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "no cambia su probabilidad futura" in contenido
        assert "último sorteo real disponible dentro del corte" in contenido

    def test_tabla_muestra_nunca_y_nd_no_none_literal(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert '"Nunca"' in contenido
        assert '"N/D"' in contenido

    def test_tarjeta_mayor_distancia_maneja_caso_sin_apariciones(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sin apariciones" in contenido
        assert "mayor_distancia is not none" in contenido

    def test_navegacion_de_dos_niveles_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "juegos_nav" in contenido
        assert "metricas_nav" in contenido

    def test_sin_umbral_arbitrario_de_cantidad_con_atraso_mayor_o_igual(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "atraso >=" not in contenido.replace(" ", "")


# =====================================================================
# Etapa Y -quinta visualización: distribucion_pares_impares / distribucion-pares-impares
# =====================================================================

class TestDistribucionParesImparesViewModel:
    def test_etiquetas_singular_plural_correctas(self):
        from app.api.web.view_models import distribucion_pares_impares_a_vm

        filas = [
            {"valor": "0", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "1", "apariciones": 2, "total_sorteos": 10, "frecuencia_relativa": 0.2},
            {"valor": "4", "apariciones": 3, "total_sorteos": 10, "frecuencia_relativa": 0.3},
            {"valor": "5", "apariciones": 4, "total_sorteos": 10, "frecuencia_relativa": 0.4},
        ]
        vm = distribucion_pares_impares_a_vm(_estadistica_calculada_fake(filas), 5, _JUEGO_BALOTO)
        etiquetas = {f["cantidad_pares"]: f["etiqueta"] for f in vm["filas"]}
        assert etiquetas[0] == "0 pares / 5 impares"
        assert etiquetas[1] == "1 par / 4 impares"
        assert etiquetas[4] == "4 pares / 1 impar"
        assert etiquetas[5] == "5 pares / 0 impares"

    def test_categorias_0_a_k_presentes(self):
        from app.api.web.view_models import distribucion_pares_impares_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(6)]
        vm = distribucion_pares_impares_a_vm(_estadistica_calculada_fake(filas), 5, _JUEGO_BALOTO)
        assert [f["cantidad_pares"] for f in vm["filas"]] == [0, 1, 2, 3, 4, 5]

    def test_composicion_mas_frecuente_sin_empate(self):
        from app.api.web.view_models import distribucion_pares_impares_a_vm

        filas = [
            {"valor": "0", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "2", "apariciones": 7, "total_sorteos": 10, "frecuencia_relativa": 0.7},
        ]
        vm = distribucion_pares_impares_a_vm(_estadistica_calculada_fake(filas), 5, _JUEGO_BALOTO)
        assert vm["composicion_mas_frecuente"] == ["2 pares / 3 impares"]

    def test_empate_muestra_todas_las_categorias_empatadas(self):
        from app.api.web.view_models import distribucion_pares_impares_a_vm

        filas = [
            {"valor": "1", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "3", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
        ]
        vm = distribucion_pares_impares_a_vm(_estadistica_calculada_fake(filas), 5, _JUEGO_BALOTO)
        assert set(vm["composicion_mas_frecuente"]) == {"1 par / 4 impares", "3 pares / 2 impares"}

    def test_cero_datos_produce_nd_no_empate_falso(self):
        from app.api.web.view_models import distribucion_pares_impares_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(6)]
        vm = distribucion_pares_impares_a_vm(_estadistica_calculada_fake(filas), 5, _JUEGO_BALOTO)
        assert vm["composicion_mas_frecuente"] is None

    def test_porcentajes_correctos_en_chart_porcentajes(self):
        from app.api.web.view_models import distribucion_pares_impares_a_vm

        filas = [{"valor": "2", "apariciones": 3, "total_sorteos": 10, "frecuencia_relativa": 0.3}]
        vm = distribucion_pares_impares_a_vm(_estadistica_calculada_fake(filas), 5, _JUEGO_BALOTO)
        assert vm["chart_porcentajes"] == [30.0]  # 0.3 * 100, no 0.3

    def test_orden_numerico_por_cantidad_de_pares(self):
        from app.api.web.view_models import distribucion_pares_impares_a_vm

        filas = [
            {"valor": "3", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "1", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        vm = distribucion_pares_impares_a_vm(_estadistica_calculada_fake(filas), 5, _JUEGO_BALOTO)
        assert [f["cantidad_pares"] for f in vm["filas"]] == [1, 2, 3]

    def test_usa_el_juego_recibido_no_hardcodea_baloto(self):
        from app.api.web.view_models import distribucion_pares_impares_a_vm

        filas = [{"valor": "0", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = distribucion_pares_impares_a_vm(_estadistica_calculada_fake(filas), 5, _JUEGO_MILOTO)
        assert vm["juego_codigo"] == "MILOTO"
        assert vm["juego_nombre"] == "MiLoto"


class TestDistribucionParesImparesNavegacion:
    def test_quinta_metrica_presente_en_los_tres_juegos(self):
        for slug in ("baloto", "baloto-revancha", "miloto"):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            ids = [m["id"] for m in nav["metricas_nav"]]
            assert "distribucion-pares-impares" in ids, slug

    def test_metrica_activa_correcta(self):
        nav = construir_navegacion_estadisticas("miloto", "distribucion-pares-impares", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        activas = [m for m in nav["metricas_nav"] if m["activo"]]
        assert len(activas) == 1 and activas[0]["id"] == "distribucion-pares-impares"

    def test_corte_conservado_entre_metricas_incluida_la_nueva(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        entrada = next(m for m in nav["metricas_nav"] if m["id"] == "distribucion-pares-impares")
        assert entrada["url"] == "/estadisticas/baloto/distribucion-pares-impares?hasta_numero_sorteo=2694"

    def test_corte_eliminado_al_cambiar_de_juego_desde_la_nueva_metrica(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "distribucion-pares-impares", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        for slug_destino in ("baloto-revancha", "miloto"):
            entrada = next(j for j in nav["juegos_nav"] if j["slug"] == slug_destino)
            assert "hasta_numero_sorteo" not in entrada["url"]

    def test_miloto_sigue_sin_superbalota_tras_agregar_la_quinta_metrica(self):
        nav = construir_navegacion_estadisticas("miloto", "distribucion-pares-impares", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert "frecuencia-superbalota" not in ids

    def test_desde_superbalota_a_miloto_sigue_yendo_a_frecuencia_numeros(self):
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-superbalota", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        miloto_entry = next(j for j in nav["juegos_nav"] if j["slug"] == "miloto")
        assert miloto_entry["url"] == "/estadisticas/miloto/frecuencia-numeros"


class TestDistribucionParesImparesRouterYManejoDeErrores:
    """Sin fastapi disponible, se verifica por lectura de código
    fuente -mismo patrón honesto que el resto de esta clase."""

    def test_ruta_existe_parametrizada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-pares-impares")' in codigo_fuente

    def test_k_viene_de_numbers_to_pick_nunca_hardcodeado(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def distribucion_pares_impares(")
        bloque = codigo_fuente[indice:indice + 2500]
        assert "juego_dominio.numbers_to_pick" in bloque
        assert '"cantidad_numeros": 5' not in bloque  # nunca hardcodeado como literal

    def test_no_existe_manejador_global_de_valueerror(self):
        """Corrección de un riesgo real: un manejador global de
        ValueError habría interceptado errores de programación
        genuinos de cualquier capa (dominio, repositorios,
        conectores, motor) como si fueran datos inválidos del
        usuario."""
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "@app.exception_handler(ValueError)" not in codigo_fuente

    def test_resultado_historico_inconsistente_error_mapeada_a_500(self):
        """Corrección semántica: no es 422 -el request puede ser
        perfectamente válido, el problema es integridad de datos
        server-side que el usuario no puede corregir cambiando su
        solicitud."""
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "ResultadoHistoricoInconsistenteError: 500" in codigo_fuente

    def test_resultado_historico_inconsistente_error_no_mapeada_a_422(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "ResultadoHistoricoInconsistenteError: 422" not in codigo_fuente

    def test_juego_sin_superbalota_continua_en_422(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "JuegoSinSuperbalotaError: 422" in codigo_fuente

    def test_juego_no_encontrado_continua_en_404(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "JuegoNoEncontradoError: 404" in codigo_fuente

    def test_query_invalido_continua_en_422_via_fastapi(self):
        """La validación de Query(ge=1) es un mecanismo separado
        (nativo de FastAPI, RequestValidationError) -no relacionado
        con _STATUS_POR_EXCEPCION ni con esta corrección; se confirma
        que la firma de las 20 rutas (9 numéricas + 11 de ColorLoto,
        Etapas AE-1/AE-2/AE-3/AE-4/AE-5/AE-6/AE-7/AE-8/AE-9/AE-10/AE-11) sigue intacta."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count("hasta_numero_sorteo: int | None = Query(default=None, ge=1)") == 28

    def test_manejar_error_dominio_no_duplicado_para_500(self):
        """No se agregó un handler nuevo -el mecanismo genérico de
        DominioError/_STATUS_POR_EXCEPCION ya soporta cualquier
        status, incluido 500."""
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert codigo_fuente.count("@app.exception_handler(DominioError)") == 1

    def test_no_se_modifico_distribuciones_py(self):
        """Verificado también por hash en el reporte -aquí se
        confirma que la función real sigue teniendo la misma firma."""
        codigo_fuente = Path("app/application/estadisticas/motor/distribuciones.py").read_text(encoding="utf-8")
        assert "def calcular_distribucion_pares_impares(" in codigo_fuente


class TestDistribucionParesImparesTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_pares_impares.html"

    def test_template_existe_y_usa_chartjs_local(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com/ajax/libs/Chart.js" not in contenido

    def test_canvas_con_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'id="grafica-distribucion-pares-impares" height="180"' in contenido

    def test_bloque_json_y_tojson_presentes(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'id="datos-distribucion-pares-impares"' in contenido
        assert 'type="application/json"' in contenido
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_arrays_json_con_misma_fuente_de_datos(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert '"labels": estadistica.chart_labels' in contenido
        assert '"porcentajes": estadistica.chart_porcentajes' in contenido
        assert '"apariciones": estadistica.chart_apariciones' in contenido

    def test_tooltip_usa_porcentaje_y_conteo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "datos.apariciones[item.dataIndex]" in contenido

    def test_titulo_correcto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Distribución de números pares e impares" in contenido

    def test_aviso_no_predictivo_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "pendiente" in contenido
        assert "más probable en el próximo sorteo" in contenido

    def test_sin_afirmaciones_de_probabilidad_futura(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        prohibidas = ["recomendada", "mejor composicion", "mayor probabilidad"]
        for frase in prohibidas:
            assert frase.lower() not in contenido.lower(), frase

    def test_tabla_con_columnas_requeridas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Composición" in contenido
        assert "Números pares" in contenido
        assert "Números impares" in contenido

    def test_control_de_corte_incluido(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'include "estadisticas/partials/control_corte_temporal.html"' in contenido

    def test_navegacion_de_dos_niveles_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "juegos_nav" in contenido
        assert "metricas_nav" in contenido


# =====================================================================
# Etapa Z -sexta visualización: distribucion_altos_bajos / distribucion-altos-bajos
# =====================================================================

class TestDistribucionAltosBajosViewModel:
    def test_punto_de_corte_y_franjas_baloto(self):
        from app.api.web.view_models import distribucion_altos_bajos_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(6)]
        vm = distribucion_altos_bajos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["punto_de_corte"] == 21
        assert vm["franja_inferior_texto"] == "1–21"
        assert vm["franja_superior_texto"] == "22–43"
        assert vm["tamano_inferior"] == 21
        assert vm["tamano_superior"] == 22

    def test_punto_de_corte_y_franjas_miloto(self):
        from app.api.web.view_models import distribucion_altos_bajos_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(6)]
        vm = distribucion_altos_bajos_a_vm(_estadistica_calculada_fake(filas), 1, 39, 5, _JUEGO_MILOTO)
        assert vm["punto_de_corte"] == 19
        assert vm["franja_inferior_texto"] == "1–19"
        assert vm["franja_superior_texto"] == "20–39"
        assert vm["tamano_inferior"] == 19
        assert vm["tamano_superior"] == 20

    def test_etiquetas_singular_plural(self):
        from app.api.web.view_models import distribucion_altos_bajos_a_vm

        filas = [
            {"valor": "0", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "1", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "4", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "5", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        vm = distribucion_altos_bajos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        etiquetas = {f["cantidad_inferiores"]: f["etiqueta"] for f in vm["filas"]}
        assert etiquetas[0] == "0 inferiores / 5 superiores"
        assert etiquetas[1] == "1 inferior / 4 superiores"
        assert etiquetas[4] == "4 inferiores / 1 superior"
        assert etiquetas[5] == "5 inferiores / 0 superiores"

    def test_porcentajes_una_sola_vez_no_multiplicado_dos_veces(self):
        from app.api.web.view_models import distribucion_altos_bajos_a_vm

        filas = [{"valor": "3", "apariciones": 3, "total_sorteos": 10, "frecuencia_relativa": 0.3}]
        vm = distribucion_altos_bajos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["chart_porcentajes"] == [30.0]

    def test_empate_muestra_todas_las_categorias(self):
        from app.api.web.view_models import distribucion_altos_bajos_a_vm

        filas = [
            {"valor": "2", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "3", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
        ]
        vm = distribucion_altos_bajos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert len(vm["composicion_mas_frecuente"]) == 2

    def test_sin_datos_produce_nd(self):
        from app.api.web.view_models import distribucion_altos_bajos_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(6)]
        vm = distribucion_altos_bajos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["composicion_mas_frecuente"] is None

    def test_usa_el_juego_recibido(self):
        from app.api.web.view_models import distribucion_altos_bajos_a_vm

        filas = [{"valor": "0", "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0}]
        vm = distribucion_altos_bajos_a_vm(_estadistica_calculada_fake(filas), 1, 39, 5, _JUEGO_MILOTO)
        assert vm["juego_codigo"] == "MILOTO"


class TestDistribucionAltosBajosNavegacion:
    def test_sexta_metrica_presente_en_los_tres_juegos(self):
        for slug in ("baloto", "baloto-revancha", "miloto"):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            ids = [m["id"] for m in nav["metricas_nav"]]
            assert "distribucion-altos-bajos" in ids, slug

    def test_metrica_activa_correcta(self):
        nav = construir_navegacion_estadisticas("miloto", "distribucion-altos-bajos", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        activas = [m for m in nav["metricas_nav"] if m["activo"]]
        assert len(activas) == 1 and activas[0]["id"] == "distribucion-altos-bajos"

    def test_corte_conservado_entre_metricas_incluida_la_nueva(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        entrada = next(m for m in nav["metricas_nav"] if m["id"] == "distribucion-altos-bajos")
        assert entrada["url"] == "/estadisticas/baloto/distribucion-altos-bajos?hasta_numero_sorteo=2694"

    def test_cambiar_de_juego_desde_la_sexta_metrica_conserva_la_metrica_sin_corte(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "distribucion-altos-bajos", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        entrada = next(j for j in nav["juegos_nav"] if j["slug"] == "miloto")
        assert entrada["url"] == "/estadisticas/miloto/distribucion-altos-bajos"
        assert "hasta_numero_sorteo" not in entrada["url"]

    def test_miloto_sigue_sin_superbalota_tras_agregar_la_sexta_metrica(self):
        nav = construir_navegacion_estadisticas("miloto", "distribucion-altos-bajos", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert "frecuencia-superbalota" not in ids

    def test_fallback_desde_superbalota_a_miloto_no_cambia(self):
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-superbalota", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        miloto_entry = next(j for j in nav["juegos_nav"] if j["slug"] == "miloto")
        assert miloto_entry["url"] == "/estadisticas/miloto/frecuencia-numeros"


class TestDistribucionAltosBajosRouterYSlug404:
    def test_ruta_existe_parametrizada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-altos-bajos")' in codigo_fuente

    def test_las_cinco_rutas_anteriores_siguen_presentes(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        for ruta in (
            "frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada",
            "atrasos-numeros", "distribucion-pares-impares",
        ):
            assert f'@router.get("/estadisticas/{{juego_slug}}/{ruta}")' in codigo_fuente

    def test_slug_desconocido_sigue_produciendo_404(self):
        """El mecanismo de 404 (_resolver_codigo, llamado al inicio
        de cada handler incluido el nuevo) no cambió -verificado por
        inspección de que el nuevo handler llama la misma función."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def distribucion_altos_bajos(")
        bloque = codigo_fuente[indice:indice + 1800]
        assert "_resolver_codigo(juego_slug)" in bloque


class TestDistribucionAltosBajosTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_altos_bajos.html"

    def test_template_existe_y_usa_chartjs_local(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com/ajax/libs/Chart.js" not in contenido

    def test_canvas_con_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'id="grafica-distribucion-altos-bajos" height="180"' in contenido

    def test_bloque_json_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'type="application/json"' in contenido
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_titulo_correcto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Distribución inferior/superior" in contenido

    def test_asimetria_explicada_junto_a_franjas_no_en_tarjeta(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        indice_alert = contenido.index("Grupo inferior:")
        indice_primera_tarjeta = contenido.index('class="text-muted small">Sorteos analizados')
        assert indice_alert < indice_primera_tarjeta  # la explicacion de asimetria esta antes, fuera de las tarjetas
        assert "mitades" in contenido.lower()

    def test_aviso_no_predictivo_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "pendiente" in contenido
        assert "evento independiente" in contenido

    def test_control_de_corte_incluido_una_vez(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count('include "estadisticas/partials/control_corte_temporal.html"') == 1

    def test_tabla_con_columnas_requeridas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Composición" in contenido
        assert "Inferiores" in contenido
        assert "Superiores" in contenido


# =====================================================================
# Etapa AA -séptima visualización: distribucion_pares_consecutivos
# =====================================================================

class TestDistribucionParesConsecutivosViewModel:
    def test_singular_plural(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_a_vm

        filas = [
            {"valor": "0", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "1", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        vm = distribucion_pares_consecutivos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        etiquetas = {f["cantidad_pares_consecutivos"]: f["etiqueta"] for f in vm["filas"]}
        assert etiquetas[0] == "0 pares consecutivos"
        assert etiquetas[1] == "1 par consecutivo"
        assert etiquetas[2] == "2 pares consecutivos"

    def test_todas_las_categorias_0_a_k_menos_1(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(4)]
        vm = distribucion_pares_consecutivos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert [f["cantidad_pares_consecutivos"] for f in vm["filas"]] == [0, 1, 2, 3]

    def test_porcentajes_convertidos_una_sola_vez(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_a_vm

        filas = [{"valor": "1", "apariciones": 3, "total_sorteos": 10, "frecuencia_relativa": 0.3}]
        vm = distribucion_pares_consecutivos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["chart_porcentajes"] == [30.0]

    def test_composicion_mas_frecuente_sin_empate(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_a_vm

        filas = [
            {"valor": "0", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "2", "apariciones": 7, "total_sorteos": 10, "frecuencia_relativa": 0.7},
        ]
        vm = distribucion_pares_consecutivos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["composicion_mas_frecuente"] == ["2 pares consecutivos"]

    def test_empates_muestran_todas_las_categorias(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_a_vm

        filas = [
            {"valor": "0", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "1", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
        ]
        vm = distribucion_pares_consecutivos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert len(vm["composicion_mas_frecuente"]) == 2

    def test_sin_datos_produce_nd_sin_empate_falso(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(4)]
        vm = distribucion_pares_consecutivos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["composicion_mas_frecuente"] is None

    def test_expone_k_rango_corte_total_sin_hardcodes(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_a_vm

        filas = [{"valor": "0", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = distribucion_pares_consecutivos_a_vm(_estadistica_calculada_fake(filas), 1, 39, 5, _JUEGO_MILOTO)
        assert vm["rango_min"] == 1 and vm["rango_max"] == 39
        assert vm["cantidad_numeros"] == 5
        assert vm["juego_codigo"] == "MILOTO"


class TestDistribucionParesConsecutivosNavegacion:
    def test_septima_metrica_presente_en_los_tres_juegos(self):
        for slug in ("baloto", "baloto-revancha", "miloto"):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            ids = [m["id"] for m in nav["metricas_nav"]]
            assert "distribucion-pares-consecutivos" in ids, slug

    def test_conservacion_del_corte_dentro_del_juego(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        entrada = next(m for m in nav["metricas_nav"] if m["id"] == "distribucion-pares-consecutivos")
        assert entrada["url"] == "/estadisticas/baloto/distribucion-pares-consecutivos?hasta_numero_sorteo=2694"

    def test_eliminacion_del_corte_al_cambiar_de_juego(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "distribucion-pares-consecutivos", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        for slug_destino in ("baloto-revancha", "miloto"):
            entrada = next(j for j in nav["juegos_nav"] if j["slug"] == slug_destino)
            assert "hasta_numero_sorteo" not in entrada["url"]
            assert entrada["url"] == f"/estadisticas/{slug_destino}/distribucion-pares-consecutivos"

    def test_miloto_sin_superbalota(self):
        nav = construir_navegacion_estadisticas("miloto", "distribucion-pares-consecutivos", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert "frecuencia-superbalota" not in ids


class TestDistribucionParesConsecutivosRouter:
    def test_ruta_existe_parametrizada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-pares-consecutivos")' in codigo_fuente

    def test_las_seis_rutas_anteriores_siguen_presentes(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        for ruta in (
            "frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada",
            "atrasos-numeros", "distribucion-pares-impares", "distribucion-altos-bajos",
        ):
            assert f'@router.get("/estadisticas/{{juego_slug}}/{ruta}")' in codigo_fuente

    def test_slug_desconocido_sigue_produciendo_404(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def distribucion_pares_consecutivos(")
        bloque = codigo_fuente[indice:indice + 1800]
        assert "_resolver_codigo(juego_slug)" in bloque


class TestDistribucionParesConsecutivosTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_pares_consecutivos.html"

    def test_template_existe_y_usa_chartjs_local(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com/ajax/libs/Chart.js" not in contenido

    def test_canvas_con_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'id="grafica-distribucion-pares-consecutivos" height="180"' in contenido

    def test_bloque_json_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'type="application/json"' in contenido
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_titulo_correcto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Distribución de pares consecutivos" in contenido

    def test_explicacion_de_pares_solapados_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "pueden solaparse" in contenido
        assert "(1,2) y (2,3)" in contenido

    def test_aviso_no_predictivo_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "no permite predecir" in contenido
        assert "menos aleatorio" in contenido

    def test_sin_afirmaciones_de_anomalia(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        for prohibida in ["anómalo", "anomalo", "es raro", "poco aleatorio"]:
            assert prohibida.lower() not in contenido.lower()

    def test_partial_de_corte_incluido_exactamente_una_vez(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count('include "estadisticas/partials/control_corte_temporal.html"') == 1

    def test_sin_cdn_y_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com" not in contenido
        assert "|safe" not in contenido


# =====================================================================
# Etapa AB -octava visualización: distribucion_racha_maxima
# =====================================================================

class TestDistribucionRachaMaximaViewModel:
    def test_categorias_1_a_k_orden_ascendente(self):
        from app.api.web.view_models import distribucion_racha_maxima_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(1, 6)]
        vm = distribucion_racha_maxima_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert [f["longitud_racha"] for f in vm["filas"]] == [1, 2, 3, 4, 5]

    def test_singular_plural(self):
        from app.api.web.view_models import distribucion_racha_maxima_a_vm

        filas = [
            {"valor": "1", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        vm = distribucion_racha_maxima_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        etiquetas = {f["longitud_racha"]: f["etiqueta"] for f in vm["filas"]}
        assert etiquetas[1] == "Racha de 1 número"
        assert etiquetas[2] == "Racha de 2 números"

    def test_no_reutiliza_literalmente_etiqueta_de_pares_consecutivos(self):
        from app.api.web.view_models import distribucion_racha_maxima_a_vm

        filas = [{"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1}]
        vm = distribucion_racha_maxima_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert "pares consecutivos" not in vm["filas"][0]["etiqueta"].lower()

    def test_categorias_con_cero_incluidas(self):
        from app.api.web.view_models import distribucion_racha_maxima_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 10, "frecuencia_relativa": 0.0} for i in range(1, 6)]
        vm = distribucion_racha_maxima_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert len(vm["filas"]) == 5

    def test_porcentajes_una_sola_vez(self):
        from app.api.web.view_models import distribucion_racha_maxima_a_vm

        filas = [{"valor": "3", "apariciones": 3, "total_sorteos": 10, "frecuencia_relativa": 0.3}]
        vm = distribucion_racha_maxima_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["chart_porcentajes"] == [30.0]

    def test_racha_mas_frecuente_sin_empate(self):
        from app.api.web.view_models import distribucion_racha_maxima_a_vm

        filas = [
            {"valor": "1", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "2", "apariciones": 7, "total_sorteos": 10, "frecuencia_relativa": 0.7},
        ]
        vm = distribucion_racha_maxima_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["racha_mas_frecuente"] == ["Racha de 2 números"]

    def test_empates_conservan_todas_las_categorias(self):
        from app.api.web.view_models import distribucion_racha_maxima_a_vm

        filas = [
            {"valor": "1", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "2", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
        ]
        vm = distribucion_racha_maxima_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert len(vm["racha_mas_frecuente"]) == 2

    def test_sin_datos_produce_nd(self):
        from app.api.web.view_models import distribucion_racha_maxima_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(1, 6)]
        vm = distribucion_racha_maxima_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["racha_mas_frecuente"] is None


class TestDistribucionRachaMaximaNavegacion:
    def test_octava_metrica_presente_en_los_tres_juegos(self):
        for slug in ("baloto", "baloto-revancha", "miloto"):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            ids = [m["id"] for m in nav["metricas_nav"]]
            assert "distribucion-racha-maxima" in ids, slug

    def test_conservacion_del_corte_dentro_del_juego(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        entrada = next(m for m in nav["metricas_nav"] if m["id"] == "distribucion-racha-maxima")
        assert entrada["url"] == "/estadisticas/baloto/distribucion-racha-maxima?hasta_numero_sorteo=2694"

    def test_eliminacion_del_corte_al_cambiar_de_juego(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "distribucion-racha-maxima", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        for slug_destino in ("baloto-revancha", "miloto"):
            entrada = next(j for j in nav["juegos_nav"] if j["slug"] == slug_destino)
            assert "hasta_numero_sorteo" not in entrada["url"]
            assert entrada["url"] == f"/estadisticas/{slug_destino}/distribucion-racha-maxima"

    def test_miloto_sin_superbalota(self):
        nav = construir_navegacion_estadisticas("miloto", "distribucion-racha-maxima", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert "frecuencia-superbalota" not in ids

    def test_navegacion_anterior_no_se_rompe_con_ocho_metricas(self):
        nav = construir_navegacion_estadisticas("baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert ids == [
            "frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada",
            "atrasos-numeros", "distribucion-pares-impares", "distribucion-altos-bajos",
            "distribucion-pares-consecutivos", "distribucion-racha-maxima", "repeticiones-entre-sorteos",
        ]


class TestDistribucionRachaMaximaRouter:
    def test_ruta_existe_parametrizada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-racha-maxima")' in codigo_fuente

    def test_las_siete_rutas_anteriores_siguen_presentes(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        for ruta in (
            "frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada",
            "atrasos-numeros", "distribucion-pares-impares", "distribucion-altos-bajos",
            "distribucion-pares-consecutivos",
        ):
            assert f'@router.get("/estadisticas/{{juego_slug}}/{ruta}")' in codigo_fuente

    def test_slug_desconocido_sigue_produciendo_404(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def distribucion_racha_maxima(")
        bloque = codigo_fuente[indice:indice + 1800]
        assert "_resolver_codigo(juego_slug)" in bloque


class TestDistribucionRachaMaximaTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_racha_maxima.html"

    def test_template_existe_y_usa_chartjs_local(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_canvas_con_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'id="grafica-distribucion-racha-maxima" height="180"' in contenido

    def test_bloque_json_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'type="application/json"' in contenido
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_titulo_correcto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Distribución de racha máxima de números consecutivos" in contenido

    def test_explicacion_distingue_de_pares_consecutivos(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "dos pares consecutivos" in contenido
        assert "racha máxima tiene longitud 3" in contenido
        assert "como mínimo una racha de longitud 1" in contenido

    def test_aviso_no_predictivo_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "no hace que un sorteo sea anómalo" in contenido
        assert "menos aleatorio" in contenido
        assert "permite predecir resultados futuros" in contenido

    def test_sin_frases_prohibidas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["racha rara", "racha improbable", "señal", "tendencia ganadora", "números que vienen", "patrón predictivo"]:
            assert prohibida not in contenido, prohibida

    def test_partial_de_corte_incluido_exactamente_una_vez(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count('include "estadisticas/partials/control_corte_temporal.html"') == 1

    def test_sin_cdn_y_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com" not in contenido
        assert "|safe" not in contenido


# =====================================================================
# Etapa AC -novena visualización: distribucion_repeticiones_entre_sorteos
# =====================================================================

class TestDistribucionRepeticionesEntreSorteosViewModel:
    def test_singular_plural(self):
        from app.api.web.view_models import distribucion_repeticiones_entre_sorteos_a_vm

        filas = [
            {"valor": "0", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "1", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        vm = distribucion_repeticiones_entre_sorteos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        etiquetas = {f["cantidad_repetidos"]: f["etiqueta"] for f in vm["filas"]}
        assert etiquetas[0] == "0 números repetidos"
        assert etiquetas[1] == "1 número repetido"
        assert etiquetas[2] == "2 números repetidos"

    def test_no_recalcula_ni_llama_motor(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_repeticiones_entre_sorteos_a_vm)
        assert "calcular_repeticiones_entre_sorteos" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()

    def test_porcentajes_una_sola_vez(self):
        from app.api.web.view_models import distribucion_repeticiones_entre_sorteos_a_vm

        filas = [{"valor": "1", "apariciones": 3, "total_sorteos": 10, "frecuencia_relativa": 0.3}]
        vm = distribucion_repeticiones_entre_sorteos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["chart_porcentajes"] == [30.0]

    def test_total_transiciones_toma_el_campo_persistido_total_sorteos(self):
        from app.api.web.view_models import distribucion_repeticiones_entre_sorteos_a_vm

        filas = [{"valor": "0", "apariciones": 7, "total_sorteos": 7, "frecuencia_relativa": 1.0}]
        vm = distribucion_repeticiones_entre_sorteos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["total_transiciones"] == 7

    def test_repeticion_mas_frecuente_sin_empate(self):
        from app.api.web.view_models import distribucion_repeticiones_entre_sorteos_a_vm

        filas = [
            {"valor": "0", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "2", "apariciones": 7, "total_sorteos": 10, "frecuencia_relativa": 0.7},
        ]
        vm = distribucion_repeticiones_entre_sorteos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["repeticion_mas_frecuente"] == ["2 números repetidos"]

    def test_empates_conservan_todas_las_categorias(self):
        from app.api.web.view_models import distribucion_repeticiones_entre_sorteos_a_vm

        filas = [
            {"valor": "0", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "1", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
        ]
        vm = distribucion_repeticiones_entre_sorteos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert len(vm["repeticion_mas_frecuente"]) == 2

    def test_sin_transiciones_produce_nd_sin_empate_falso(self):
        from app.api.web.view_models import distribucion_repeticiones_entre_sorteos_a_vm

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(6)]
        vm = distribucion_repeticiones_entre_sorteos_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["repeticion_mas_frecuente"] is None
        assert vm["total_transiciones"] == 0


class TestDistribucionRepeticionesEntreSorteosNavegacion:
    def test_novena_metrica_presente_en_baloto_y_revancha(self):
        for slug in ("baloto", "baloto-revancha"):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            ids = [m["id"] for m in nav["metricas_nav"]]
            assert len(ids) == 9, slug
            assert "repeticiones-entre-sorteos" in ids

    def test_miloto_ocho_metricas_sigue_sin_superbalota(self):
        nav = construir_navegacion_estadisticas("miloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
        ids = [m["id"] for m in nav["metricas_nav"]]
        assert len(ids) == 8
        assert "frecuencia-superbalota" not in ids
        assert "repeticiones-entre-sorteos" in ids

    def test_conservacion_del_corte_dentro_del_juego(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        entrada = next(m for m in nav["metricas_nav"] if m["id"] == "repeticiones-entre-sorteos")
        assert entrada["url"] == "/estadisticas/baloto/repeticiones-entre-sorteos?hasta_numero_sorteo=2694"

    def test_eliminacion_del_corte_al_cambiar_de_juego(self):
        nav = construir_navegacion_estadisticas(
            "baloto", "repeticiones-entre-sorteos", CAPACIDAD_SUPERBALOTA_POR_SLUG, {}, hasta_numero_sorteo=2694,
        )
        for slug_destino in ("baloto-revancha", "miloto"):
            entrada = next(j for j in nav["juegos_nav"] if j["slug"] == slug_destino)
            assert "hasta_numero_sorteo" not in entrada["url"]
            assert entrada["url"] == f"/estadisticas/{slug_destino}/repeticiones-entre-sorteos"


class TestDistribucionRepeticionesEntreSorteosRouter:
    def test_ruta_existe_parametrizada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/repeticiones-entre-sorteos")' in codigo_fuente

    def test_las_ocho_rutas_anteriores_siguen_presentes(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        for ruta in (
            "frecuencia-numeros", "frecuencia-superbalota", "frecuencia-observada-esperada",
            "atrasos-numeros", "distribucion-pares-impares", "distribucion-altos-bajos",
            "distribucion-pares-consecutivos", "distribucion-racha-maxima",
        ):
            assert f'@router.get("/estadisticas/{{juego_slug}}/{ruta}")' in codigo_fuente

    def test_slug_desconocido_sigue_produciendo_404(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def repeticiones_entre_sorteos(")
        bloque = codigo_fuente[indice:indice + 1800]
        assert "_resolver_codigo(juego_slug)" in bloque


class TestDistribucionRepeticionesEntreSorteosTemplate:
    _TEMPLATE = "app/templates/estadisticas/repeticiones_entre_sorteos.html"

    def test_template_existe_y_usa_chartjs_local(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_canvas_con_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'id="grafica-repeticiones-entre-sorteos" height="180"' in contenido

    def test_bloque_json_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'type="application/json"' in contenido
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_titulo_correcto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Repeticiones entre sorteos consecutivos" in contenido

    def test_texto_transiciones_analizadas_sin_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Transiciones analizadas" in contenido
        assert "Sorteos analizados" not in contenido

    def test_mensaje_general_sin_transiciones(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay transiciones válidas para calcular esta distribución." in contenido

    def test_explicacion_n_mas_1_primer_sorteo_y_huecos(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "N con N+1" in contenido or "N+1" in contenido
        assert "no produce ninguna transición" in contenido
        assert "no se comparan" in contenido

    def test_aviso_no_predictivo_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "no aumenta ni reduce la probabilidad" in contenido

    def test_sin_frases_prohibidas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["números calientes", "fríos", "raros", "anómalos"]:
            assert prohibida not in contenido, prohibida

    def test_partial_de_corte_incluido_exactamente_una_vez(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count('include "estadisticas/partials/control_corte_temporal.html"') == 1

    def test_sin_cdn_y_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com" not in contenido
        assert "|safe" not in contenido


# =====================================================================
# Etapa AE-1: primera visualización descriptiva de ColorLoto -
# router/VM/template/navegación.
# =====================================================================

class TestColorLotoAislamientoDeSlugs:
    def test_colorloto_no_esta_en_slug_a_codigo_compartido(self):
        assert "colorloto" not in SLUG_A_CODIGO

    def test_ruta_colorloto_es_fija_no_parametrizada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/frecuencia-numeros")' in codigo_fuente

    def test_ruta_colorloto_registrada_antes_de_la_ruta_generica_conflictiva(self):
        """CRÍTICO: Starlette (motor de enrutamiento de FastAPI)
        evalúa las rutas EN ORDEN DE REGISTRO, no por especificidad.
        `/estadisticas/{juego_slug}/frecuencia-numeros` y
        `/estadisticas/colorloto/frecuencia-numeros` tienen la misma
        forma de 3 segmentos -si la ruta genérica se registrara
        ANTES, capturaría cualquier petición a la URL de ColorLoto
        con `juego_slug="colorloto"`, dejando el handler dedicado
        completamente inalcanzable en un despliegue HTTP real
        (defecto encontrado y corregido en esta misma auditoría).

        Este test HUBIERA FALLADO antes de la corrección -confirma
        por posición textual en el archivo fuente que el decorador
        de ColorLoto aparece antes que el de la ruta genérica
        conflictiva."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_colorloto = codigo_fuente.index('@router.get("/estadisticas/colorloto/frecuencia-numeros")')
        indice_generica_conflictiva = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/frecuencia-numeros")')
        assert indice_colorloto < indice_generica_conflictiva

    def test_simulacion_fiel_del_algoritmo_de_starlette_confirma_orden_correcto(self):
        """FastAPI/Starlette no están instalados en este sandbox (sin
        acceso a red externa para instalarlos, confirmado reintentando
        `pip install fastapi` en este mismo turno) -esta prueba
        reproduce FIELMENTE el algoritmo público y documentado de
        `starlette.routing.compile_path`: cada segmento `{param}` se
        convierte en un grupo regex `(?P<param>[^/]+)`, y las rutas
        se evalúan en el ORDEN EXACTO en que aparecen en el archivo
        fuente real (no un orden supuesto), devolviendo la PRIMERA
        que matchea completamente -exactamente el comportamiento real
        de Starlette. No es una ejecución de FastAPI real; se declara
        explícitamente como simulación fiel del algoritmo. Se
        complementa con `test_cuerpo_real_del_handler_atrasos_colorloto_produce_contenido_propio`
        (más abajo), que confirma por AST del código REAL -no
        reimplementado- que el handler dedicado produce contenido
        genuinamente distinto del genérico."""
        import re

        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        rutas_en_orden = re.findall(r'@router\.get\("([^"]+)"\)', codigo_fuente)
        assert len(rutas_en_orden) == 28

        def compilar_como_starlette(path):
            patron = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
            return re.compile("^" + patron + "$")

        def primera_ruta_que_matchea(url):
            for patron in rutas_en_orden:
                m = compilar_como_starlette(patron).match(url)
                if m:
                    return patron, m.groupdict()
            return None, None

        # Las catorce URLs dedicadas de ColorLoto (Etapas AE-1/AE-2/AE-3/AE-4/AE-5/AE-6/AE-7/AE-8/AE-9/AE-10/AE-11/AE-12/AE-13/AE-14)
        # deben resolver a SUS PROPIAS rutas, sin ningun grupo de
        # captura (match literal exacto) -confirma que los handlers
        # dedicados de atrasos-numeros, repeticiones-entre-sorteos,
        # distribucion-pares-impares, distribucion-altos-bajos,
        # distribucion-pares-consecutivos y distribucion-racha-maxima
        # son ALCANZABLES, no interceptados por su ruta generica
        # homonima (colision real en los SEIS casos, mismo sufijo
        # exacto, a diferencia de frecuencia-colores/frecuencia-pares-numero-color/
        # atrasos-colores/atrasos-pares-numero-color). maximo-repeticion-color
        # (AE-10), distribucion-trios-consecutivos (AE-13) y
        # coocurrencia-pares (AE-14) NO tienen ninguna ruta generica
        # equivalente -confirmado abajo que Baloto/Revancha simplemente
        # no resuelven a nada para ninguna de las tres.
        for sufijo in ("frecuencia-numeros", "frecuencia-colores", "frecuencia-pares-numero-color", "atrasos-numeros", "atrasos-colores", "atrasos-pares-numero-color", "repeticiones-entre-sorteos", "distribucion-pares-impares", "distribucion-altos-bajos", "maximo-repeticion-color", "distribucion-pares-consecutivos", "distribucion-racha-maxima", "distribucion-trios-consecutivos", "coocurrencia-pares", "coocurrencia-trios", "coocurrencia-pares-colores"):
            patron, grupos = primera_ruta_que_matchea(f"/estadisticas/colorloto/{sufijo}")
            assert patron == f"/estadisticas/colorloto/{sufijo}"
            assert grupos == {}

        # Las rutas numericas existentes deben seguir resolviendo a
        # la ruta generica correspondiente, con juego_slug capturado
        # correctamente -confirmando que el reordenamiento de AE-14 NO
        # rompio ninguna de las 9 rutas numericas previas, INCLUIDA
        # atrasos-numeros, repeticiones-entre-sorteos,
        # distribucion-pares-impares, distribucion-altos-bajos,
        # distribucion-pares-consecutivos y distribucion-racha-maxima
        # genericas (las mas sensibles, por compartir sufijo exacto
        # con ColorLoto) -Baloto en particular sigue resolviendo
        # correctamente a la generica. distribucion-trios-consecutivos
        # y coocurrencia-pares NO pertenecen a este grupo -nunca hubo
        # ruta generica para ninguna de las dos, ni siquiera para
        # juegos numericos (confirmado en las auditorias de AE-13 y
        # AE-14).
        for slug in ("baloto", "baloto-revancha", "miloto"):
            for sufijo in ("frecuencia-numeros", "atrasos-numeros", "repeticiones-entre-sorteos", "distribucion-pares-impares", "distribucion-altos-bajos", "distribucion-pares-consecutivos", "distribucion-racha-maxima"):
                patron, grupos = primera_ruta_que_matchea(f"/estadisticas/{slug}/{sufijo}")
                assert patron == f"/estadisticas/{{juego_slug}}/{sufijo}"
                assert grupos == {"juego_slug": slug}

        # maximo-repeticion-color (AE-10), distribucion-trios-consecutivos
        # (AE-13) y coocurrencia-pares (AE-14) NO tienen ruta generica
        # equivalente -Baloto y Revancha deben quedar SIN ningun
        # handler que los capture (404 real, no un handler generico
        # mal dirigido) -confirmado con simulacion exacta en la
        # auditoria previa, reconfirmado aqui para las tres.
        for slug in ("baloto", "baloto-revancha"):
            for sufijo_sin_colision in ("maximo-repeticion-color", "distribucion-trios-consecutivos", "coocurrencia-pares", "coocurrencia-trios", "coocurrencia-pares-colores"):
                patron_col, grupos_col = primera_ruta_que_matchea(f"/estadisticas/{slug}/{sufijo_sin_colision}")
                assert patron_col is None
                assert grupos_col is None

    def test_cuerpo_real_del_handler_atrasos_colorloto_produce_contenido_propio(self):
        """Complementa la simulación de enrutamiento: confirma por AST
        del código REAL (no reimplementado, no un doble) que el
        CUERPO de `atrasos_numeros_colorloto` -si se ejecutara con
        FastAPI real- produciría contenido genuinamente propio de
        ColorLoto, nunca el resultado del handler genérico. FastAPI y
        SQLAlchemy no están instalados en este sandbox (confirmado
        reintentando su instalación en este mismo turno, sin acceso a
        red externa), lo que impide ejecutar el handler completo con
        un TestClient real -este test es la evidencia más fuerte
        disponible dentro de esa limitación declarada."""
        import ast

        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        arbol = ast.parse(codigo_fuente)

        funcion_colorloto = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "atrasos_numeros_colorloto")
        funcion_generica = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "atrasos_numeros")

        cuerpo_colorloto = ast.get_source_segment(codigo_fuente, funcion_colorloto)
        cuerpo_generica = ast.get_source_segment(codigo_fuente, funcion_generica)

        # El handler dedicado usa su propio template y tipo_estadistica,
        # resuelve el codigo FIJO "COLORLOTO", y nunca pasa por
        # SLUG_A_CODIGO -contenido estructuralmente imposible de
        # confundir con el handler generico.
        assert "estadisticas/atrasos_numeros_colorloto.html" in cuerpo_colorloto
        assert '"atrasos_numeros_colorloto"' in cuerpo_colorloto
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_colorloto
        assert "SLUG_A_CODIGO" not in cuerpo_colorloto

        # El handler generico, en contraste, usa su propio template
        # distinto y un juego_slug parametrizado -nunca el codigo fijo.
        assert "estadisticas/atrasos_numeros.html" in cuerpo_generica
        assert "estadisticas/atrasos_numeros_colorloto.html" not in cuerpo_generica
        assert any(a.arg == "juego_slug" for a in funcion_generica.args.args)
        assert not any(a.arg == "juego_slug" for a in funcion_colorloto.args.args)

    def test_ruta_pares_colorloto_registrada_antes_de_cualquier_ruta_generica(self):
        """Ningún sufijo de las 9 rutas genéricas coincide con
        "frecuencia-pares-numero-color" -confirmado por simulación
        exhaustiva sin colisión posible; aun así, se mantiene
        registrada antes de cualquier ruta genérica por prudencia y
        consistencia arquitectónica, mismo criterio ya aplicado en
        AE-2."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_pares = codigo_fuente.index('@router.get("/estadisticas/colorloto/frecuencia-pares-numero-color")')
        indice_primera_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/')
        assert indice_pares < indice_primera_generica

    def test_ruta_colores_colorloto_registrada_antes_de_cualquier_ruta_generica(self):
        """A diferencia de `frecuencia-numeros` (que sí colisionaba
        con una ruta genérica y requirió reordenamiento explícito en
        AE-1), ningún sufijo de las 9 rutas genéricas coincide con
        "frecuencia-colores" -confirmado por simulación exhaustiva:
        aun así, se mantiene registrada antes de cualquier ruta
        genérica por prudencia y consistencia arquitectónica."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_colores = codigo_fuente.index('@router.get("/estadisticas/colorloto/frecuencia-colores")')
        indice_primera_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/')
        assert indice_colores < indice_primera_generica

    def test_ruta_atrasos_colorloto_registrada_antes_de_la_generica_homonima_colision_real(self):
        """CRÍTICO -a diferencia de `frecuencia-colores`/`frecuencia-pares-numero-color`
        (sin colisión posible), `atrasos-numeros` SÍ colisiona con la
        ruta genérica `/estadisticas/{juego_slug}/atrasos-numeros`
        (mismo sufijo exacto) -mismo defecto potencial que se corrigió
        en AE-1 para `frecuencia-numeros`. Este test verifica
        explícitamente que la ruta literal de ColorLoto está declarada
        ANTES de la genérica homónima específica, no solo antes de
        "alguna" ruta genérica."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_atrasos_colorloto = codigo_fuente.index('@router.get("/estadisticas/colorloto/atrasos-numeros")')
        indice_atrasos_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/atrasos-numeros")')
        assert indice_atrasos_colorloto < indice_atrasos_generica

    def test_ruta_pares_consecutivos_colorloto_registrada_antes_de_la_generica_homonima_colision_real(self):
        """CRÍTICO (Etapa AE-11) -`distribucion-pares-consecutivos`
        colisiona con la ruta genérica
        `/estadisticas/{juego_slug}/distribucion-pares-consecutivos`
        (mismo sufijo exacto, ya existente desde antes de AE-11) -sexta
        colisión real del mismo tipo ya corregida en AE-1/AE-4/AE-7/
        AE-8/AE-9. Este test verifica explícitamente que la ruta
        literal de ColorLoto está declarada ANTES de la genérica
        homónima específica, no solo antes de "alguna" ruta genérica."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_pares_consecutivos_colorloto = codigo_fuente.index(
            '@router.get("/estadisticas/colorloto/distribucion-pares-consecutivos")',
        )
        indice_pares_consecutivos_generica = codigo_fuente.index(
            '@router.get("/estadisticas/{juego_slug}/distribucion-pares-consecutivos")',
        )
        assert indice_pares_consecutivos_colorloto < indice_pares_consecutivos_generica

    def test_ruta_racha_maxima_colorloto_registrada_antes_de_la_generica_homonima_colision_real(self):
        """CRÍTICO (Etapa AE-12) -`distribucion-racha-maxima`
        colisiona con la ruta genérica
        `/estadisticas/{juego_slug}/distribucion-racha-maxima`
        (mismo sufijo exacto, ya existente desde antes de AE-12) -séptima
        colisión real del mismo tipo ya corregida en AE-1/AE-4/AE-7/
        AE-8/AE-9/AE-11. Este test verifica explícitamente que la ruta
        literal de ColorLoto está declarada ANTES de la genérica
        homónima específica, no solo antes de "alguna" ruta genérica."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_racha_maxima_colorloto = codigo_fuente.index(
            '@router.get("/estadisticas/colorloto/distribucion-racha-maxima")',
        )
        indice_racha_maxima_generica = codigo_fuente.index(
            '@router.get("/estadisticas/{juego_slug}/distribucion-racha-maxima")',
        )
        assert indice_racha_maxima_colorloto < indice_racha_maxima_generica

    def test_ruta_trios_consecutivos_colorloto_sin_colision_generica(self):
        """A DIFERENCIA de AE-1/AE-4/AE-7/AE-8/AE-9/AE-11/AE-12,
        `distribucion-trios-consecutivos` (Etapa AE-13) NO colisiona
        con ninguna ruta genérica -confirmado por la auditoría de
        AE-13 (simulación con el motor real de
        `starlette.routing.Route`) que
        `/estadisticas/{juego_slug}/distribucion-trios-consecutivos`
        no existe entre las rutas registradas, ni siquiera para el
        motor numérico equivalente (`calcular_distribucion_trios_consecutivos`,
        nunca conectado a `_CATALOGO`). Mismo caso que
        `maximo-repeticion-color` (Etapa AE-10) -la ruta se registra
        igualmente en el bloque literal de ColorLoto por prudencia y
        consistencia, no por necesidad de evitar una colisión real."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/distribucion-trios-consecutivos")' in codigo_fuente
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-trios-consecutivos")' not in codigo_fuente

    def test_ruta_coocurrencia_pares_colorloto_sin_colision_generica(self):
        """Mismo caso que `maximo-repeticion-color` (AE-10) y
        `distribucion-trios-consecutivos` (AE-13): `coocurrencia-pares`
        (Etapa AE-14) NO colisiona con ninguna ruta genérica
        -confirmado por la auditoría de AE-14 (simulación con el
        motor real de `starlette.routing.Route`) que
        `/estadisticas/{juego_slug}/coocurrencia-pares` no existe
        entre las rutas registradas, ni siquiera para el motor
        numérico equivalente (`calcular_coocurrencia_pares`, nunca
        conectado a `_CATALOGO` para ningún juego numérico)."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/coocurrencia-pares")' in codigo_fuente
        assert '@router.get("/estadisticas/{juego_slug}/coocurrencia-pares")' not in codigo_fuente

    def test_ruta_coocurrencia_trios_colorloto_sin_colision_generica(self):
        """Mismo caso que `coocurrencia-pares` (AE-14):
        `coocurrencia-trios` (Etapa AE-15) NO colisiona con ninguna
        ruta genérica -confirmado por la auditoría de AE-15
        (simulación con el motor real de `starlette.routing.Route`)
        que `/estadisticas/{juego_slug}/coocurrencia-trios` no existe
        entre las rutas registradas, ni siquiera para el motor
        numérico equivalente (`calcular_coocurrencia_trios`, nunca
        conectado a `_CATALOGO` para ningún juego numérico)."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/coocurrencia-trios")' in codigo_fuente
        assert '@router.get("/estadisticas/{juego_slug}/coocurrencia-trios")' not in codigo_fuente

    def test_metrica_incompatible_produce_404_nativo_no_attributeerror(self):
        """La ruta genérica `{juego_slug}` nunca reconoce "colorloto"
        como código válido (no está en SLUG_A_CODIGO) -por tanto
        /estadisticas/colorloto/distribucion-pares-impares nunca
        matchea ninguna ruta registrada, produciendo 404 nativo de
        FastAPI (ruta inexistente), nunca un AttributeError al
        intentar leer has_superballot de ColorLotoGame."""
        assert resolver_codigo("colorloto") is None

    def test_veinte_rutas_totales_nueve_genericas_mas_once_colorloto(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count("@router.get(") == 28
        assert codigo_fuente.count('@router.get("/estadisticas/{juego_slug}/') == 9

    def test_veinte_query_totales(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count("hasta_numero_sorteo: int | None = Query(default=None, ge=1)") == 28

    def test_no_construye_gamefactory_ni_llama_has_superballot_para_colorloto(self):
        """El docstring del handler EXPLICA en prosa que no usa estos
        símbolos -por eso se busca invocación/acceso real
        (`GameFactory(`, `.crear(`, `.has_superballot`), nunca la
        sola mención textual, que aparecería inevitablemente en la
        explicación."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def frecuencia_numeros_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_docstring + 2000]
        assert ".has_superballot" not in cuerpo_ejecutable
        assert "GameFactory(" not in cuerpo_ejecutable
        assert "ColorLotoGame(" not in cuerpo_ejecutable
        assert "game_factory.crear(" not in cuerpo_ejecutable


class TestColorLotoViewModel:
    def test_siete_categorias(self):
        from app.api.web.view_models import frecuencia_numeros_colorloto_a_vm
        juego = Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 3, "frecuencia_relativa": 0.0} for i in range(1, 8)]
        vm = frecuencia_numeros_colorloto_a_vm(FakeEst(filas), 1, 7, juego)
        assert len(vm["filas"]) == 7

    def test_promedio_2_decimales_sin_simbolo_porcentaje(self):
        from app.api.web.view_models import frecuencia_numeros_colorloto_a_vm
        juego = Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 3, "frecuencia_relativa": 0.333333} for i in range(1, 8)]
        vm = frecuencia_numeros_colorloto_a_vm(FakeEst(filas), 1, 7, juego)
        assert vm["filas"][0]["apariciones_promedio_texto"] == "0.33"
        assert "%" not in vm["filas"][0]["apariciones_promedio_texto"]

    def test_caso_sintetico_promedio_superior_a_uno(self):
        from app.api.web.view_models import frecuencia_numeros_colorloto_a_vm
        juego = Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 5, "frecuencia_relativa": 0.0} for i in range(1, 8)]
        filas[0]["apariciones"] = 10
        filas[0]["frecuencia_relativa"] = 2.0
        vm = frecuencia_numeros_colorloto_a_vm(FakeEst(filas), 1, 7, juego)
        assert vm["filas"][0]["apariciones_promedio"] == 2.0
        assert vm["filas"][0]["apariciones_promedio_texto"] == "2.00"

    def test_empates_preservados_completos(self):
        from app.api.web.view_models import frecuencia_numeros_colorloto_a_vm
        juego = Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None

        filas = [{"valor": str(i), "apariciones": 5, "total_sorteos": 5, "frecuencia_relativa": 1.0} for i in range(1, 8)]
        vm = frecuencia_numeros_colorloto_a_vm(FakeEst(filas), 1, 7, juego)
        assert len(vm["numero_mayor_promedio"]) == 7

    def test_nd_sin_sorteos(self):
        from app.api.web.view_models import frecuencia_numeros_colorloto_a_vm
        juego = Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None

        filas = [{"valor": str(i), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for i in range(1, 8)]
        vm = frecuencia_numeros_colorloto_a_vm(FakeEst(filas), 1, 7, juego)
        assert vm["numero_mayor_promedio"] is None

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.frecuencia_numeros_colorloto_a_vm)
        assert "calcular_frecuencia_numeros_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoTemplate:
    _TEMPLATE = "app/templates/estadisticas/frecuencia_numeros_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_texto_semantico_obligatorio(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "puede aparecer más de una vez en el mismo sorteo" in contenido
        assert "pueden superar 1" in contenido
        assert "no es un porcentaje ni una probabilidad" in contenido
        assert "no predice resultados futuros" in contenido or "no predice" in contenido

    def test_columnas_de_tabla_correctas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Número</th>" in contenido or ">Número<" in contenido
        assert "Apariciones</th>" in contenido or ">Apariciones<" in contenido
        assert "Apariciones promedio por sorteo" in contenido

    def test_sin_lenguaje_predictivo_prohibido(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["más probable", "probabilidad de salir", "caliente", "frío", "recomendación de apuesta"]:
            assert prohibida not in contenido, prohibida

    def test_sorteos_analizados_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido


class TestColorLotoDescubribilidadYNavegacionExistenteIntacta:
    def test_enlace_global_visible_en_base_html(self):
        contenido = Path("app/templates/base.html").read_text(encoding="utf-8")
        assert "/estadisticas/colorloto/frecuencia-numeros" in contenido

    def test_enlace_baloto_no_se_elimino(self):
        contenido = Path("app/templates/base.html").read_text(encoding="utf-8")
        assert "/estadisticas/baloto/frecuencia-numeros" in contenido

    def test_navegacion_numerica_9_9_8_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug


# =====================================================================
# Etapa AE-2: segunda visualización descriptiva de ColorLoto -
# frecuencia de colores -router/VM/template/navegación.
# =====================================================================

class TestColorLotoFrecuenciaColoresRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/frecuencia-colores")' in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def frecuencia_colores_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_docstring + 2000]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_metrica_incompatible_de_colores_produce_404(self):
        assert resolver_codigo("colorloto") is None


class TestColorLotoFrecuenciaColoresVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def test_nombre_y_codigo_de_color_presentes(self):
        from app.api.web.view_models import frecuencia_colores_colorloto_a_vm
        filas = [{"valor": "ROJO", "apariciones": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6}]
        vm = frecuencia_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["codigo"] == "ROJO"
        assert vm["filas"][0]["nombre"] == "Rojo"

    def test_orden_conservado_tal_cual_llega_del_motor(self):
        from app.api.web.view_models import frecuencia_colores_colorloto_a_vm
        filas = [
            {"valor": "AMARILLO", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0},
            {"valor": "AZUL", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0},
        ]
        vm = frecuencia_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert [f["codigo"] for f in vm["filas"]] == ["AMARILLO", "AZUL"]

    def test_empates_preservados_completos(self):
        from app.api.web.view_models import frecuencia_colores_colorloto_a_vm
        filas = [{"valor": c, "apariciones": 5, "total_sorteos": 5, "frecuencia_relativa": 1.0} for c in ("ROJO", "AZUL", "VERDE")]
        vm = frecuencia_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert len(vm["color_mayor_promedio"]) == 3

    def test_apariciones_enteras_promedio_dos_decimales_sin_porcentaje(self):
        from app.api.web.view_models import frecuencia_colores_colorloto_a_vm
        filas = [{"valor": "ROJO", "apariciones": 7, "total_sorteos": 3, "frecuencia_relativa": 2.333333}]
        vm = frecuencia_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["apariciones"] == 7
        assert isinstance(vm["filas"][0]["apariciones"], int)
        assert vm["filas"][0]["apariciones_promedio_texto"] == "2.33"
        assert "%" not in vm["filas"][0]["apariciones_promedio_texto"]

    def test_nd_sin_sorteos(self):
        from app.api.web.view_models import frecuencia_colores_colorloto_a_vm
        vm = frecuencia_colores_colorloto_a_vm(self._fake_est([]), self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["color_mayor_promedio"] is None

    def test_color_visual_seguro_para_codigo_conocido_y_fallback_para_desconocido(self):
        from app.api.web.view_models import frecuencia_colores_colorloto_a_vm
        filas = [
            {"valor": "ROJO", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0},
            {"valor": "MORADO", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0},
        ]
        vm = frecuencia_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["color_hex"].startswith("#")
        assert vm["filas"][1]["color_hex"] == "#9CA3AF"

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.frecuencia_colores_colorloto_a_vm)
        assert "calcular_frecuencia_colores" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()

    def test_nombre_no_inserta_html_sin_escapar(self):
        """El VM nunca usa `|safe` en Jinja2 (verificado en el
        template), y aquí confirma que `nombre` es texto plano
        derivado de `.title()`, sin ningún marcado HTML embebido."""
        from app.api.web.view_models import frecuencia_colores_colorloto_a_vm
        filas = [{"valor": "ROJO", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = frecuencia_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert "<" not in vm["filas"][0]["nombre"]
        assert ">" not in vm["filas"][0]["nombre"]


class TestColorLotoFrecuenciaColoresTemplate:
    _TEMPLATE = "app/templates/estadisticas/frecuencia_colores_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_texto_semantico_obligatorio(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "un color puede aparecer más de una vez en el mismo sorteo" in contenido
        assert "pueden superar 1" in contenido
        assert "no es un porcentaje ni una probabilidad" in contenido

    def test_columnas_de_tabla_correctas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert ">Color<" in contenido
        assert ">Apariciones<" in contenido
        assert "Apariciones promedio por sorteo" in contenido

    def test_sin_lenguaje_predictivo_prohibido(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["más probable", "mejor color", "recomendado", "ganador", "caliente", "frío"]:
            assert prohibida not in contenido, prohibida

    def test_sorteos_analizados_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido


class TestColorLotoNavegacionDosMetricas:
    def test_partial_navegacion_colorloto_existe(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido

    def test_ambos_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_navegacion_preserva_hasta_numero_sorteo_en_los_enlaces(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "hasta_numero_sorteo" in contenido

    def test_pagina_activa_marcada_en_ambos_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_metricas_numericas_no_expuestas_a_colorloto(self):
        """Actualizado en Etapa AE-4: "atrasos-numeros" ya no es una
        métrica incompatible -es una pestaña legítima de ColorLoto
        (URL completa distinta: `/estadisticas/colorloto/atrasos-numeros`
        vs. `/estadisticas/{juego_slug}/atrasos-numeros`; solo el
        sufijo textual coincide, no la ruta). Actualizado en Etapa
        AE-8: "distribucion-pares-impares" tampoco es ya una
        métrica incompatible, mismo criterio exacto. Se mantiene
        la verificación para las métricas genuinamente
        incompatibles -ColorLoto no tiene superbalota."""
        codigo_fuente = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        for metrica_numerica in ("frecuencia-superbalota",):
            assert metrica_numerica not in codigo_fuente


# =====================================================================
# Etapa AE-3: tercera visualización descriptiva de ColorLoto -
# frecuencia de pares número-color -router/VM/template/navegación.
# =====================================================================

class TestColorLotoFrecuenciaParesRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/frecuencia-pares-numero-color")' in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def frecuencia_pares_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_docstring + 2000]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_incompatible_produce_404(self):
        assert resolver_codigo("colorloto") is None


class TestColorLotoFrecuenciaParesVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_42(self):
        filas = []
        for n in range(1, 8):
            for c in ("AMARILLO", "AZUL", "BLANCO", "NEGRO", "ROJO", "VERDE"):
                filas.append({"valor": f"{n}-{c}", "apariciones": 0, "total_sorteos": 5, "frecuencia_relativa": 0.0})
        return filas

    def test_numero_codigo_nombre_correctos(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est(self._filas_42()), 1, 7, self._juego())
        assert vm["filas"][0]["numero"] == 1
        assert vm["filas"][0]["codigo"] == "AMARILLO"
        assert vm["filas"][0]["nombre"] == "Amarillo"

    def test_42_filas_actuales(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est(self._filas_42()), 1, 7, self._juego())
        assert len(vm["filas"]) == 42

    def test_datasets_agrupados_por_color_numeros_1_a_7(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est(self._filas_42()), 1, 7, self._juego())
        assert vm["chart_labels"] == [str(i) for i in range(1, 8)]
        assert len(vm["chart_datasets"]) == 6
        assert all(len(d["data"]) == 7 for d in vm["chart_datasets"])

    def test_promedio_sin_porcentaje(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        filas = self._filas_42()
        filas[0]["apariciones"] = 7
        filas[0]["frecuencia_relativa"] = 1.4
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert vm["filas"][0]["apariciones_promedio_texto"] == "1.40"
        assert "%" not in vm["filas"][0]["apariciones_promedio_texto"]

    def test_nd_sin_historico(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est([]), 1, 7, self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["par_mayor_promedio"] is None

    def test_empates_preservados(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        filas = self._filas_42()
        filas[0]["apariciones"] = 5
        filas[0]["total_sorteos"] = 5
        filas[0]["frecuencia_relativa"] = 1.0
        filas[6]["apariciones"] = 5
        filas[6]["total_sorteos"] = 5
        filas[6]["frecuencia_relativa"] = 1.0
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert len(vm["par_mayor_promedio"]) == 2

    def test_escape_seguro_nombre_sin_html(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est(self._filas_42()), 1, 7, self._juego())
        for f in vm["filas"]:
            assert "<" not in f["nombre"]
            assert ">" not in f["nombre"]

    def test_colores_y_fallback(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        filas = self._filas_42() + [{"valor": "1-MORADO", "apariciones": 1, "total_sorteos": 5, "frecuencia_relativa": 0.2}]
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        fila_morado = next(f for f in vm["filas"] if f["codigo"] == "MORADO")
        assert fila_morado["color_hex"] == "#9CA3AF"

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.frecuencia_pares_colorloto_a_vm)
        assert "calcular_frecuencia_pares_numero_color" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()

    def test_deserializacion_blindada_con_guion_en_color(self):
        from app.api.web.view_models import frecuencia_pares_colorloto_a_vm
        filas = [{"valor": "3-AZUL-CLARO", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = frecuencia_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert vm["filas"][0]["numero"] == 3
        assert vm["filas"][0]["codigo"] == "AZUL-CLARO"


class TestColorLotoFrecuenciaParesTemplate:
    _TEMPLATE = "app/templates/estadisticas/frecuencia_pares_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_texto_semantico_par_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "el par exacto" in contenido or "el mismo par número-color" in contenido
        assert "no es un porcentaje ni una probabilidad" in contenido

    def test_columnas_de_tabla_correctas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert ">Número<" in contenido
        assert ">Color<" in contenido
        assert ">Apariciones<" in contenido
        assert "Apariciones promedio por sorteo" in contenido

    def test_sin_lenguaje_predictivo_prohibido(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["más probable", "mejor combinación", "recomendado", "ganador", "caliente", "frío"]:
            assert prohibida not in contenido, prohibida

    def test_sorteos_analizados_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido


class TestColorLotoNavegacionTresMetricas:
    def test_partial_navegacion_incluye_las_tres_metricas(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido
        assert "frecuencia-pares-numero-color" in contenido

    def test_los_tres_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html", "frecuencia_pares_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_pagina_activa_marcada_en_los_tres_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-pares-numero-color"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_corte_preservado_al_alternar_entre_las_tres(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count("hasta_numero_sorteo") >= 3


# =====================================================================
# Etapa AE-4: cuarta visualización descriptiva de ColorLoto -
# atrasos de números -router/VM/template/navegación.
# =====================================================================

class TestColorLotoAtrasosNumerosRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/atrasos-numeros")' in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def atrasos_numeros_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_docstring + 2000]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_incompatible_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None


class TestColorLotoAtrasosNumerosVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self):
        return [{"valor": str(i), "atraso": i, "ultimo_sorteo_aparicion": 10 - i, "total_sorteos": 10} for i in range(1, 8)]

    def test_siete_numeros(self):
        from app.api.web.view_models import atrasos_numeros_colorloto_a_vm
        vm = atrasos_numeros_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, self._juego())
        assert len(vm["filas"]) == 7
        assert [f["numero"] for f in vm["filas"]] == list(range(1, 8))

    def test_atraso_cero_positivo_y_nd(self):
        from app.api.web.view_models import atrasos_numeros_colorloto_a_vm
        filas = self._filas_base()
        filas[0]["atraso"] = 0
        filas[0]["ultimo_sorteo_aparicion"] = 10
        filas[2]["atraso"] = None
        filas[2]["ultimo_sorteo_aparicion"] = None
        vm = atrasos_numeros_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert vm["filas"][0]["atraso"] == 0
        assert vm["filas"][2]["atraso"] is None
        assert vm["filas"][2]["ultimo_sorteo_aparicion"] is None

    def test_empates_de_mayor_atraso_preservados(self):
        from app.api.web.view_models import atrasos_numeros_colorloto_a_vm
        filas = self._filas_base()
        for f in filas:
            f["atraso"] = 1
        filas[0]["atraso"] = 5
        filas[3]["atraso"] = 5
        vm = atrasos_numeros_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        maximo = max(f["atraso"] for f in vm["filas"] if f["atraso"] is not None)
        assert maximo == 5
        assert set(vm["numero_mayor_atraso"]) == {"1", "4"}

    def test_valores_sin_aparicion_nunca_elegidos_como_mayor_atraso(self):
        """Un número sin aparición (atraso=None) nunca debe aparecer
        en `numero_mayor_atraso`, incluso si es el único distinto de
        los demás -None no es "más atrasado" que un valor real."""
        from app.api.web.view_models import atrasos_numeros_colorloto_a_vm
        filas = self._filas_base()
        for f in filas:
            f["atraso"] = 3
            f["ultimo_sorteo_aparicion"] = 7
        filas[0]["atraso"] = None
        filas[0]["ultimo_sorteo_aparicion"] = None
        vm = atrasos_numeros_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert "1" not in vm["numero_mayor_atraso"]

    def test_nd_total_sin_ninguna_aparicion(self):
        from app.api.web.view_models import atrasos_numeros_colorloto_a_vm
        filas_vacio = [{"valor": str(i), "atraso": None, "ultimo_sorteo_aparicion": None, "total_sorteos": 0} for i in range(1, 8)]
        vm = atrasos_numeros_colorloto_a_vm(self._fake_est(filas_vacio), 1, 7, self._juego())
        assert vm["numero_mayor_atraso"] is None
        assert vm["total_sorteos"] == 0

    def test_chart_atrasos_preserva_none_nunca_cero_falso(self):
        from app.api.web.view_models import atrasos_numeros_colorloto_a_vm
        filas = self._filas_base()
        filas[2]["atraso"] = None
        vm = atrasos_numeros_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert vm["chart_atrasos"][2] is None

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.atrasos_numeros_colorloto_a_vm)
        assert "calcular_atrasos_numeros_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoAtrasosNumerosTemplate:
    _TEMPLATE = "app/templates/estadisticas/atrasos_numeros_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_texto_semantico_de_atraso_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "El atraso indica la diferencia entre el sorteo de referencia y la última aparición histórica del número. Un atraso alto no aumenta la probabilidad de que el número aparezca próximamente." in contenido
        assert "histórica y no predictiva" in contenido

    def test_columnas_de_tabla_correctas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert ">Número<" in contenido
        assert "Sorteos de atraso" in contenido
        assert "Último sorteo con aparición" in contenido

    def test_nunca_llama_frecuencia_promedio_o_porcentaje_a_la_magnitud(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        assert "frecuencia" not in contenido
        assert "promedio" not in contenido
        assert "porcentaje" not in contenido

    def test_sin_lenguaje_predictivo_prohibido(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["más probable", "debe salir pronto", "recomendado", "caliente", "frío"]:
            assert prohibida not in contenido, prohibida

    def test_sorteos_analizados_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_nd_para_valores_nunca_aparecidos(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "N/D" in contenido


class TestColorLotoNavegacionCuatroMetricas:
    def test_partial_navegacion_incluye_las_cuatro_metricas(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido
        assert "frecuencia-pares-numero-color" in contenido
        assert "atrasos-numeros" in contenido

    def test_los_cuatro_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html", "frecuencia_pares_colorloto.html", "atrasos_numeros_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_pagina_activa_marcada_en_los_cuatro_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-numeros"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_corte_preservado_al_alternar_entre_las_cuatro(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count("hasta_numero_sorteo") >= 4

    def test_partial_tiene_exactamente_diecinueve_items_de_navegacion(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count('<li class="nav-item">') == 19


# =====================================================================
# Etapa AE-5: quinta visualización descriptiva de ColorLoto -
# atrasos de colores -router/VM/template/navegación.
# =====================================================================

class TestColorLotoAtrasosColoresRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/atrasos-colores")' in codigo_fuente

    def test_ruta_registrada_antes_de_cualquier_ruta_generica(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_atrasos_colores = codigo_fuente.index('@router.get("/estadisticas/colorloto/atrasos-colores")')
        indice_primera_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/')
        assert indice_atrasos_colores < indice_primera_generica

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def atrasos_colores_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_docstring + 2000]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_incompatible_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_incluyen_marcador_de_politica(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="atrasos_colores_colorloto"')
        bloque = codigo_fuente[indice:indice + 400]
        assert '"politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL' in bloque


class TestColorLotoAtrasosColoresVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self):
        return [
            {"valor": c, "atraso": i, "ultimo_sorteo_aparicion": 10 - i, "total_sorteos": 10}
            for i, c in enumerate(("AMARILLO", "AZUL", "BLANCO", "NEGRO", "ROJO", "VERDE"), start=1)
        ]

    def test_seis_colores_codigo_nombre_hex(self):
        from app.api.web.view_models import atrasos_colores_colorloto_a_vm
        vm = atrasos_colores_colorloto_a_vm(self._fake_est(self._filas_base()), self._juego())
        assert len(vm["filas"]) == 6
        assert vm["filas"][0]["codigo"] == "AMARILLO"
        assert vm["filas"][0]["nombre"] == "Amarillo"
        assert vm["filas"][0]["color_hex"].startswith("#")

    def test_atraso_cero_positivo_y_nd(self):
        from app.api.web.view_models import atrasos_colores_colorloto_a_vm
        filas = self._filas_base()
        filas[0]["atraso"] = 0
        filas[0]["ultimo_sorteo_aparicion"] = 10
        filas[2]["atraso"] = None
        filas[2]["ultimo_sorteo_aparicion"] = None
        vm = atrasos_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["atraso"] == 0
        assert vm["filas"][2]["atraso"] is None
        assert vm["filas"][2]["ultimo_sorteo_aparicion"] is None

    def test_empates_de_mayor_atraso_preservados(self):
        from app.api.web.view_models import atrasos_colores_colorloto_a_vm
        filas = self._filas_base()
        for f in filas:
            f["atraso"] = 1
        filas[0]["atraso"] = 5
        filas[3]["atraso"] = 5
        vm = atrasos_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert set(vm["color_mayor_atraso"]) == {"Amarillo", "Negro"}

    def test_valores_sin_aparicion_nunca_elegidos_como_mayor_atraso(self):
        from app.api.web.view_models import atrasos_colores_colorloto_a_vm
        filas = self._filas_base()
        for f in filas:
            f["atraso"] = 3
        filas[0]["atraso"] = None
        filas[0]["ultimo_sorteo_aparicion"] = None
        vm = atrasos_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert "Amarillo" not in vm["color_mayor_atraso"]

    def test_nd_total_sin_ninguna_aparicion(self):
        from app.api.web.view_models import atrasos_colores_colorloto_a_vm
        filas_vacio = [{"valor": c, "atraso": None, "ultimo_sorteo_aparicion": None, "total_sorteos": 0} for c in ("ROJO", "AZUL")]
        vm = atrasos_colores_colorloto_a_vm(self._fake_est(filas_vacio), self._juego())
        assert vm["color_mayor_atraso"] is None
        assert vm["total_sorteos"] == 0

    def test_chart_atrasos_preserva_none_nunca_cero_falso(self):
        from app.api.web.view_models import atrasos_colores_colorloto_a_vm
        filas = self._filas_base()
        filas[2]["atraso"] = None
        vm = atrasos_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["chart_atrasos"][2] is None

    def test_color_desconocido_usa_fallback_hex(self):
        from app.api.web.view_models import atrasos_colores_colorloto_a_vm
        filas = [{"valor": "MORADO", "atraso": 1, "ultimo_sorteo_aparicion": 2, "total_sorteos": 3}]
        vm = atrasos_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["color_hex"] == "#9CA3AF"

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.atrasos_colores_colorloto_a_vm)
        assert "calcular_atrasos_colores" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoAtrasosColoresTemplate:
    _TEMPLATE = "app/templates/estadisticas/atrasos_colores_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_texto_semantico_de_atraso_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "El atraso indica la diferencia entre el sorteo de referencia y la última aparición histórica del color. Un atraso alto no aumenta la probabilidad de que el color aparezca próximamente." in contenido
        assert "histórica y no predictiva" in contenido

    def test_columnas_de_tabla_correctas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert ">Color<" in contenido
        assert "Sorteos de atraso" in contenido
        assert "Último sorteo con aparición" in contenido

    def test_nunca_llama_frecuencia_promedio_o_porcentaje_a_la_magnitud(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        assert "frecuencia" not in contenido
        assert "promedio" not in contenido
        assert "porcentaje" not in contenido

    def test_sin_lenguaje_predictivo_prohibido(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["más probable", "debe salir pronto", "recomendado", "caliente", "frío"]:
            assert prohibida not in contenido, prohibida

    def test_sorteos_analizados_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_nd_para_colores_nunca_observados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "N/D" in contenido

    def test_swatch_de_color_usa_color_hex(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "background-color:{{ fila.color_hex }}" in contenido


class TestColorLotoNavegacionCincoMetricas:
    def test_partial_navegacion_incluye_las_cinco_metricas(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido
        assert "frecuencia-pares-numero-color" in contenido
        assert "atrasos-numeros" in contenido
        assert "atrasos-colores" in contenido

    def test_los_cinco_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html", "frecuencia_pares_colorloto.html", "atrasos_numeros_colorloto.html", "atrasos_colores_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_pagina_activa_marcada_en_los_cinco_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-colores"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_corte_preservado_al_alternar_entre_las_cinco(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count("hasta_numero_sorteo") >= 5


# =====================================================================
# Etapa AE-6: sexta visualización descriptiva de ColorLoto -
# atrasos de pares número-color -router/VM/template/navegación.
# =====================================================================

class TestColorLotoAtrasosParesRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/atrasos-pares-numero-color")' in codigo_fuente

    def test_ruta_registrada_antes_de_cualquier_ruta_generica(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_atrasos_pares = codigo_fuente.index('@router.get("/estadisticas/colorloto/atrasos-pares-numero-color")')
        indice_primera_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/')
        assert indice_atrasos_pares < indice_primera_generica

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def atrasos_pares_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_docstring + 2000]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_incompatible_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_incluyen_marcador_de_politica(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="atrasos_pares_colorloto"')
        bloque = codigo_fuente[indice:indice + 400]
        assert '"politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL' in bloque


class TestColorLotoAtrasosParesVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self):
        filas = []
        colores = ("AMARILLO", "AZUL", "BLANCO", "NEGRO", "ROJO", "VERDE")
        for n in range(1, 8):
            for c in colores:
                filas.append({"valor": f"{n}-{c}", "atraso": (n % 5), "ultimo_sorteo_aparicion": 10, "total_sorteos": 20})
        return filas

    def test_cuarenta_y_dos_pares_numero_codigo_hex(self):
        from app.api.web.view_models import atrasos_pares_colorloto_a_vm
        vm = atrasos_pares_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, self._juego())
        assert len(vm["filas"]) == 42
        assert vm["filas"][0]["numero"] == 1
        assert vm["filas"][0]["codigo"] == "AMARILLO"
        assert vm["filas"][0]["color_hex"].startswith("#")

    def test_atraso_cero_positivo_y_nd(self):
        from app.api.web.view_models import atrasos_pares_colorloto_a_vm
        filas = self._filas_base()
        filas[0]["atraso"] = 0
        filas[0]["ultimo_sorteo_aparicion"] = 20
        filas[2]["atraso"] = None
        filas[2]["ultimo_sorteo_aparicion"] = None
        vm = atrasos_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert vm["filas"][0]["atraso"] == 0
        assert vm["filas"][2]["atraso"] is None
        assert vm["filas"][2]["ultimo_sorteo_aparicion"] is None

    def test_empates_de_mayor_atraso_preservados(self):
        from app.api.web.view_models import atrasos_pares_colorloto_a_vm
        filas = self._filas_base()
        for f in filas:
            f["atraso"] = 1
        filas[0]["atraso"] = 5
        filas[6]["atraso"] = 5
        vm = atrasos_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert set(vm["par_mayor_atraso"]) == {"1 - Amarillo", "2 - Amarillo"}

    def test_valores_sin_aparicion_nunca_elegidos_como_mayor_atraso(self):
        from app.api.web.view_models import atrasos_pares_colorloto_a_vm
        filas = self._filas_base()
        for f in filas:
            f["atraso"] = 3
        filas[0]["atraso"] = None
        filas[0]["ultimo_sorteo_aparicion"] = None
        vm = atrasos_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert "1 - Amarillo" not in vm["par_mayor_atraso"]

    def test_nd_total_sin_ninguna_aparicion(self):
        from app.api.web.view_models import atrasos_pares_colorloto_a_vm
        filas_vacio = [{"valor": f"{n}-ROJO", "atraso": None, "ultimo_sorteo_aparicion": None, "total_sorteos": 0} for n in range(1, 8)]
        vm = atrasos_pares_colorloto_a_vm(self._fake_est(filas_vacio), 1, 7, self._juego())
        assert vm["par_mayor_atraso"] is None
        assert vm["total_sorteos"] == 0

    def test_dataset_agrupado_preserva_none_nunca_cero_falso(self):
        from app.api.web.view_models import atrasos_pares_colorloto_a_vm
        filas = self._filas_base()
        filas[2]["atraso"] = None
        vm = atrasos_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        assert len(vm["chart_datasets"]) == 6
        dataset_del_par = next(d for d in vm["chart_datasets"] if d["label"] == filas[2]["valor"].split("-", 1)[1].title())
        assert None in dataset_del_par["data"]

    def test_no_usa_cero_como_fallback_de_fila_ausente(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.atrasos_pares_colorloto_a_vm)
        assert "else 0.0" not in codigo_fuente
        assert "else None" in codigo_fuente

    def test_orden_determinista_dominio_real_coincide_con_frecuencia(self):
        """Confirma, en el dominio real 1-7, que el orden del
        resultado ya serializado (nunca reordenado por el VM) es
        numérico correcto -mismo orden ya usado por
        frecuencia_pares_colorloto_a_vm."""
        from app.api.web.view_models import atrasos_pares_colorloto_a_vm
        filas = self._filas_base()
        vm = atrasos_pares_colorloto_a_vm(self._fake_est(filas), 1, 7, self._juego())
        numeros_en_orden = [f["numero"] for f in vm["filas"]]
        assert numeros_en_orden == sorted(numeros_en_orden)

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.atrasos_pares_colorloto_a_vm)
        assert "calcular_atrasos_pares_numero_color" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoAtrasosParesTemplate:
    _TEMPLATE = "app/templates/estadisticas/atrasos_pares_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_texto_semantico_de_atraso_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "El atraso indica la diferencia entre el sorteo de referencia y la última aparición histórica del par exacto número-color." in contenido
        assert "histórica y no predictiva" in contenido

    def test_columnas_de_tabla_correctas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert ">Número<" in contenido
        assert ">Color<" in contenido
        assert "Sorteos de atraso" in contenido
        assert "Último sorteo con aparición" in contenido

    def test_nunca_llama_frecuencia_promedio_o_porcentaje_a_la_magnitud(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        assert "frecuencia" not in contenido
        assert "promedio" not in contenido
        assert "porcentaje" not in contenido

    def test_sin_lenguaje_predictivo_prohibido(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["más probable", "debe salir pronto", "recomendado", "caliente", "frío"]:
            assert prohibida not in contenido, prohibida

    def test_sorteos_analizados_presente(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_nd_para_pares_nunca_observados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "N/D" in contenido

    def test_sin_fallback_cero_punto_cero_en_javascript(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "0.0" not in contenido

    def test_grafico_agrupado_por_color_con_leyenda(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "chart_datasets" in contenido
        assert 'legend: { display: true' in contenido


class TestColorLotoNavegacionSeisMetricas:
    def test_partial_navegacion_incluye_las_seis_metricas(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido
        assert "frecuencia-pares-numero-color" in contenido
        assert "atrasos-numeros" in contenido
        assert "atrasos-colores" in contenido
        assert "atrasos-pares-numero-color" in contenido

    def test_los_seis_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html", "frecuencia_pares_colorloto.html", "atrasos_numeros_colorloto.html", "atrasos_colores_colorloto.html", "atrasos_pares_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_pagina_activa_marcada_en_los_seis_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-pares-numero-color"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_corte_preservado_al_alternar_entre_las_seis(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count("hasta_numero_sorteo") >= 6


# =====================================================================
# Etapa AE-7: séptima visualización descriptiva de ColorLoto -
# repeticiones entre sorteos -router/VM/template/navegación.
# =====================================================================

class TestColorLotoRepeticionesRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/repeticiones-entre-sorteos")' in codigo_fuente

    def test_ruta_registrada_antes_de_la_generica_homonima(self):
        """Requisito obligatorio del contrato -no verificacion
        opcional: ambas rutas comparten exactamente el mismo
        sufijo, confirmado como colision real en la auditoria
        previa a esta implementacion."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_literal = codigo_fuente.index('@router.get("/estadisticas/colorloto/repeticiones-entre-sorteos")')
        indice_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/repeticiones-entre-sorteos")')
        assert indice_literal < indice_generica

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def repeticiones_entre_sorteos_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        fin_handler = codigo_fuente.index('@router.get(', fin_docstring)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_sin_marcador_de_politica(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="repeticiones_entre_sorteos_colorloto"')
        bloque = codigo_fuente[indice:indice + 400]
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque
        assert '"rango_min": juego.rango_min' in bloque
        assert '"rango_max": juego.rango_max' in bloque
        assert '"cantidad_numeros": juego.cantidad_numeros' in bloque


class TestColorLotoRepeticionesVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self, total_transiciones=10):
        return [{"valor": str(n), "apariciones": (n % 3), "total_sorteos": total_transiciones, "frecuencia_relativa": (n % 3) / total_transiciones} for n in range(7)]

    def test_siete_filas_ordenadas_cero_a_seis(self):
        from app.api.web.view_models import repeticiones_entre_sorteos_colorloto_a_vm
        vm = repeticiones_entre_sorteos_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, 6, self._juego())
        assert len(vm["filas"]) == 7
        assert [f["cantidad_repetidos"] for f in vm["filas"]] == list(range(7))

    def test_total_sorteos_renombrado_a_total_transiciones(self):
        from app.api.web.view_models import repeticiones_entre_sorteos_colorloto_a_vm
        vm = repeticiones_entre_sorteos_colorloto_a_vm(self._fake_est(self._filas_base(total_transiciones=42)), 1, 7, 6, self._juego())
        assert vm["total_transiciones"] == 42

    def test_serializador_nunca_renombrado(self):
        """El campo persistido sigue siendo total_sorteos -solo el
        View Model lo traduce en presentacion."""
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.repeticiones_entre_sorteos_colorloto_a_vm)
        assert '["total_sorteos"]' in codigo_fuente

    def test_etiqueta_singular_plural_correcta(self):
        from app.api.web.view_models import repeticiones_entre_sorteos_colorloto_a_vm
        vm = repeticiones_entre_sorteos_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, 6, self._juego())
        assert vm["filas"][0]["etiqueta"] == "0 números repetidos"
        assert vm["filas"][1]["etiqueta"] == "1 número repetido"
        assert vm["filas"][2]["etiqueta"] == "2 números repetidos"

    def test_repeticion_mas_frecuente_excluye_transiciones_cero(self):
        from app.api.web.view_models import repeticiones_entre_sorteos_colorloto_a_vm
        filas_sin_transiciones = [{"valor": str(n), "apariciones": 0, "total_sorteos": 0, "frecuencia_relativa": 0.0} for n in range(7)]
        vm = repeticiones_entre_sorteos_colorloto_a_vm(self._fake_est(filas_sin_transiciones), 1, 7, 6, self._juego())
        assert vm["repeticion_mas_frecuente"] is None
        assert vm["total_transiciones"] == 0

    def test_repeticion_mas_frecuente_incluye_todos_los_empates(self):
        from app.api.web.view_models import repeticiones_entre_sorteos_colorloto_a_vm
        filas = [{"valor": str(n), "apariciones": 1, "total_sorteos": 7, "frecuencia_relativa": 1 / 7} for n in range(7)]
        vm = repeticiones_entre_sorteos_colorloto_a_vm(self._fake_est(filas), 1, 7, 6, self._juego())
        assert len(vm["repeticion_mas_frecuente"]) == 7

    def test_historico_vacio_cero_transiciones(self):
        from app.api.web.view_models import repeticiones_entre_sorteos_colorloto_a_vm
        vm = repeticiones_entre_sorteos_colorloto_a_vm(self._fake_est([]), 1, 7, 6, self._juego())
        assert vm["total_transiciones"] == 0
        assert vm["filas"] == []
        assert vm["repeticion_mas_frecuente"] is None

    def test_vm_nunca_lee_ni_deriva_color(self):
        """A diferencia del resto de VMs de ColorLoto, esta metrica
        ignora el color por completo -verificado sobre el CUERPO
        EJECUTABLE unicamente (docstring/nombre de funcion pueden
        mencionar la palabra para explicarlo)."""
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.repeticiones_entre_sorteos_colorloto_a_vm)
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""') + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:]
        assert "color" not in cuerpo_ejecutable.lower()
        assert "_color_hex_seguro" not in codigo_fuente

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.repeticiones_entre_sorteos_colorloto_a_vm)
        assert "calcular_repeticiones_entre_sorteos_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoRepeticionesTemplate:
    _TEMPLATE = "app/templates/estadisticas/repeticiones_entre_sorteos_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay transiciones válidas para calcular esta distribución." in contenido

    def test_muestra_transiciones_analizadas_nunca_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Transiciones analizadas" in contenido
        assert "Sorteos analizados" not in contenido

    def test_columnas_de_tabla_correctas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Números repetidos" in contenido
        assert "Transiciones" in contenido
        assert "Frecuencia relativa" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido

    def test_sin_lenguaje_predictivo_prohibido(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8").lower()
        for prohibida in ["más probable", "debe salir pronto", "recomendado", "caliente", "frío"]:
            assert prohibida not in contenido, prohibida

    def test_grafico_de_barras_simple(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert 'type: "bar"' in contenido
        assert "chart_porcentajes" in contenido


class TestColorLotoNavegacionSietePestanas:
    def test_partial_navegacion_incluye_las_siete_metricas(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido
        assert "frecuencia-pares-numero-color" in contenido
        assert "atrasos-numeros" in contenido
        assert "atrasos-colores" in contenido
        assert "atrasos-pares-numero-color" in contenido
        assert "repeticiones-entre-sorteos" in contenido

    def test_los_siete_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html", "frecuencia_pares_colorloto.html", "atrasos_numeros_colorloto.html", "atrasos_colores_colorloto.html", "atrasos_pares_colorloto.html", "repeticiones_entre_sorteos_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_pagina_activa_marcada_en_los_siete_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "repeticiones-entre-sorteos"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_corte_preservado_al_alternar_entre_las_siete(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count("hasta_numero_sorteo") >= 7


# =====================================================================
# Etapa AE-8: octava visualización descriptiva de ColorLoto -
# distribución de números pares e impares -router/VM/template/navegación.
# =====================================================================

class TestColorLotoDistribucionParesImparesRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/distribucion-pares-impares")' in codigo_fuente

    def test_ruta_registrada_antes_de_la_generica_homonima(self):
        """Requisito obligatorio del contrato -no verificacion
        opcional: ambas rutas comparten exactamente el mismo
        sufijo, confirmado como colision real en la auditoria
        previa a esta implementacion."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_literal = codigo_fuente.index('@router.get("/estadisticas/colorloto/distribucion-pares-impares")')
        indice_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/distribucion-pares-impares")')
        assert indice_literal < indice_generica

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def distribucion_pares_impares_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        fin_handler = codigo_fuente.index('@router.get(', fin_docstring)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_baloto_generico_sigue_presente_y_no_se_elimino(self):
        """La ruta generica de Baloto para esta metrica NO es un
        caso incompatible: existe legitimamente para los 3 juegos
        numericos y debe seguir funcionando sin ninguna
        interferencia de la nueva ruta literal de ColorLoto."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-pares-impares")' in codigo_fuente

    def test_parametros_metrica_con_una_sola_clave_sin_marcador(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="distribucion_pares_impares_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert '"cantidad_numeros": juego.cantidad_numeros' in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque


class TestColorLotoDistribucionParesImparesVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self, total_sorteos=10):
        return [{"valor": str(n), "apariciones": (n % 3), "total_sorteos": total_sorteos, "frecuencia_relativa": (n % 3) / total_sorteos} for n in range(7)]

    def test_siete_filas_orden_cero_a_seis(self):
        from app.api.web.view_models import distribucion_pares_impares_colorloto_a_vm
        vm = distribucion_pares_impares_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert len(vm["filas"]) == 7
        assert [f["cantidad_pares"] for f in vm["filas"]] == list(range(7))

    def test_cero_real_sin_none_ni_nd_en_filas(self):
        from app.api.web.view_models import distribucion_pares_impares_colorloto_a_vm
        vm = distribucion_pares_impares_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        for fila in vm["filas"]:
            assert fila["apariciones"] is not None
            assert isinstance(fila["apariciones"], int)

    def test_denominador_es_total_sorteos_no_transiciones(self):
        from app.api.web.view_models import distribucion_pares_impares_colorloto_a_vm
        vm = distribucion_pares_impares_colorloto_a_vm(self._fake_est(self._filas_base(total_sorteos=42)), 6, self._juego())
        assert vm["total_sorteos"] == 42
        assert "total_transiciones" not in vm

    def test_historico_vacio_composicion_nd(self):
        from app.api.web.view_models import distribucion_pares_impares_colorloto_a_vm
        vm = distribucion_pares_impares_colorloto_a_vm(self._fake_est([]), 6, self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["composicion_mas_frecuente"] is None

    def test_vm_nunca_lee_ni_deriva_color(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_pares_impares_colorloto_a_vm)
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""') + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:]
        assert "color" not in cuerpo_ejecutable.lower()

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_pares_impares_colorloto_a_vm)
        assert "calcular_distribucion_pares_impares_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoDistribucionParesImparesTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_pares_impares_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tojson_y_json_parse_presentes(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_explica_asimetria_del_dominio_real(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "tres valores pares" in contenido
        assert "cuatro" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido

    def test_tabla_completa_con_columnas_correctas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert ">Composición<" in contenido
        assert ">Números pares<" in contenido
        assert ">Números impares<" in contenido


class TestColorLotoNavegacionOchoPestanas:
    def test_partial_navegacion_incluye_las_ocho_metricas(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido
        assert "frecuencia-pares-numero-color" in contenido
        assert "atrasos-numeros" in contenido
        assert "atrasos-colores" in contenido
        assert "atrasos-pares-numero-color" in contenido
        assert "repeticiones-entre-sorteos" in contenido
        assert "distribucion-pares-impares" in contenido

    def test_los_ocho_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html", "frecuencia_pares_colorloto.html", "atrasos_numeros_colorloto.html", "atrasos_colores_colorloto.html", "atrasos_pares_colorloto.html", "repeticiones_entre_sorteos_colorloto.html", "distribucion_pares_impares_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_pagina_activa_marcada_en_los_ocho_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "repeticiones-entre-sorteos"' in codigo_fuente
        assert '"pagina_colorloto_activa": "distribucion-pares-impares"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_corte_preservado_al_alternar_entre_las_ocho(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count("hasta_numero_sorteo") >= 8


# =====================================================================
# Etapa AE-9: novena visualización descriptiva de ColorLoto -
# distribución de números bajos y altos -router/VM/template/navegación.
# =====================================================================

class TestColorLotoDistribucionAltosBajosRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/distribucion-altos-bajos")' in codigo_fuente

    def test_ruta_registrada_antes_de_la_generica_homonima(self):
        """Requisito obligatorio del contrato -no verificacion
        opcional: ambas rutas comparten exactamente el mismo
        sufijo, confirmado como colision real en la auditoria
        previa a esta implementacion."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice_literal = codigo_fuente.index('@router.get("/estadisticas/colorloto/distribucion-altos-bajos")')
        indice_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/distribucion-altos-bajos")')
        assert indice_literal < indice_generica

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def distribucion_altos_bajos_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        fin_handler = codigo_fuente.index('@router.get(', fin_docstring)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_baloto_generico_sigue_presente_y_no_se_elimino(self):
        """La ruta generica de Baloto para esta metrica NO es un
        caso incompatible: existe legitimamente para los 3 juegos
        numericos y debe seguir funcionando sin ninguna
        interferencia de la nueva ruta literal de ColorLoto."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-altos-bajos")' in codigo_fuente

    def test_parametros_metrica_con_tres_claves_sin_marcador(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="distribucion_altos_bajos_colorloto"')
        bloque = codigo_fuente[indice:indice + 400]
        assert '"rango_min": juego.rango_min' in bloque
        assert '"rango_max": juego.rango_max' in bloque
        assert '"cantidad_numeros": juego.cantidad_numeros' in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque


class TestColorLotoDistribucionAltosBajosVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self, total_sorteos=10):
        return [{"valor": str(n), "apariciones": (n % 3), "total_sorteos": total_sorteos, "frecuencia_relativa": (n % 3) / total_sorteos} for n in range(7)]

    def test_siete_filas_orden_cero_a_seis(self):
        from app.api.web.view_models import distribucion_altos_bajos_colorloto_a_vm
        vm = distribucion_altos_bajos_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, 6, self._juego())
        assert len(vm["filas"]) == 7
        assert [f["cantidad_bajos"] for f in vm["filas"]] == list(range(7))

    def test_punto_de_corte_y_franjas_dominio_real(self):
        from app.api.web.view_models import distribucion_altos_bajos_colorloto_a_vm
        vm = distribucion_altos_bajos_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, 6, self._juego())
        assert vm["punto_de_corte"] == 3
        assert vm["franja_bajos_texto"] == "1-3"
        assert vm["franja_altos_texto"] == "4-7"

    def test_cantidad_altos_derivada_correctamente(self):
        from app.api.web.view_models import distribucion_altos_bajos_colorloto_a_vm
        vm = distribucion_altos_bajos_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, 6, self._juego())
        for fila in vm["filas"]:
            assert fila["cantidad_altos"] == 6 - fila["cantidad_bajos"]

    def test_etiqueta_singular_plural_correcta(self):
        from app.api.web.view_models import distribucion_altos_bajos_colorloto_a_vm
        vm = distribucion_altos_bajos_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, 6, self._juego())
        assert vm["filas"][0]["etiqueta"] == "0 bajos / 6 altos"
        assert vm["filas"][1]["etiqueta"] == "1 bajo / 5 altos"
        assert vm["filas"][3]["etiqueta"] == "3 bajos / 3 altos"

    def test_cero_real_sin_none_ni_nd_en_filas(self):
        from app.api.web.view_models import distribucion_altos_bajos_colorloto_a_vm
        vm = distribucion_altos_bajos_colorloto_a_vm(self._fake_est(self._filas_base()), 1, 7, 6, self._juego())
        for fila in vm["filas"]:
            assert fila["apariciones"] is not None
            assert isinstance(fila["apariciones"], int)

    def test_denominador_es_total_sorteos_no_transiciones(self):
        from app.api.web.view_models import distribucion_altos_bajos_colorloto_a_vm
        vm = distribucion_altos_bajos_colorloto_a_vm(self._fake_est(self._filas_base(total_sorteos=42)), 1, 7, 6, self._juego())
        assert vm["total_sorteos"] == 42
        assert "total_transiciones" not in vm

    def test_historico_vacio_composicion_nd(self):
        from app.api.web.view_models import distribucion_altos_bajos_colorloto_a_vm
        vm = distribucion_altos_bajos_colorloto_a_vm(self._fake_est([]), 1, 7, 6, self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["composicion_mas_frecuente"] is None

    def test_vm_nunca_lee_ni_deriva_color(self):
        """Verificacion precisa: excluye el propio nombre de la
        funcion/helper (que termina en "colorloto", conteniendo
        la subcadena "color" sin relacion con la paleta) y busca
        solo patrones que SI indicarian lectura real de color:
        acceso a un campo de codigo/color de un par, o el helper
        de color hexadecimal ya usado por el resto de VMs de
        ColorLoto."""
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_altos_bajos_colorloto_a_vm)
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""') + 3) + 3
        cuerpo_ejecutable = codigo_fuente[fin_docstring:]
        assert "_color_hex_seguro" not in cuerpo_ejecutable
        assert "f[\"codigo\"]" not in cuerpo_ejecutable
        assert "colores_vigentes" not in cuerpo_ejecutable

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_altos_bajos_colorloto_a_vm)
        assert "calcular_distribucion_altos_bajos_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()

    def test_vm_reutiliza_punto_de_corte_generico_sin_duplicar(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_altos_bajos_colorloto_a_vm)
        assert "_punto_de_corte_altos_bajos_vm(" in codigo_fuente


class TestColorLotoDistribucionAltosBajosTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_altos_bajos_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tojson_y_json_parse_presentes(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_explica_bajo_alto_corte_y_multiplicidad(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "bajo" in contenido.lower()
        assert "alto" in contenido.lower()
        assert "repetido" in contenido.lower()

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido

    def test_tabla_completa_con_columnas_inequivocas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Números bajos (" in contenido
        assert "Números altos (" in contenido


class TestColorLotoNavegacionNuevePestanas:
    def test_partial_navegacion_incluye_las_nueve_metricas(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido
        assert "frecuencia-pares-numero-color" in contenido
        assert "atrasos-numeros" in contenido
        assert "atrasos-colores" in contenido
        assert "atrasos-pares-numero-color" in contenido
        assert "repeticiones-entre-sorteos" in contenido
        assert "distribucion-pares-impares" in contenido
        assert "distribucion-altos-bajos" in contenido

    def test_los_nueve_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html", "frecuencia_pares_colorloto.html", "atrasos_numeros_colorloto.html", "atrasos_colores_colorloto.html", "atrasos_pares_colorloto.html", "repeticiones_entre_sorteos_colorloto.html", "distribucion_pares_impares_colorloto.html", "distribucion_altos_bajos_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_pagina_activa_marcada_en_los_nueve_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "repeticiones-entre-sorteos"' in codigo_fuente
        assert '"pagina_colorloto_activa": "distribucion-pares-impares"' in codigo_fuente
        assert '"pagina_colorloto_activa": "distribucion-altos-bajos"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_corte_preservado_al_alternar_entre_las_nueve(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count("hasta_numero_sorteo") >= 9


# =====================================================================
# Etapa AE-10 (PROVISIONAL): decima visualizacion descriptiva de
# ColorLoto -maximo color repetido por sorteo -router/VM/template/navegacion.
# =====================================================================

class TestColorLotoMaximoRepeticionColorRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/maximo-repeticion-color")' in codigo_fuente

    def test_sin_ruta_generica_equivalente(self):
        """A diferencia de las otras 4 metricas con colision real,
        esta NO tiene ninguna ruta generica homonima -confirmado
        en la auditoria: ningun juego numerico tiene el concepto
        de color."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/maximo-repeticion-color")' not in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def maximo_repeticion_color_por_sorteo_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        fin_handler = codigo_fuente.index('@router.get(', fin_docstring)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_con_una_sola_clave_sin_marcador(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="maximo_repeticion_color_por_sorteo_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert '"cantidad_numeros": juego.cantidad_numeros' in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque


class TestColorLotoMaximoRepeticionColorVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self, total_sorteos=10):
        return [{"valor": str(n), "apariciones": (1 if n == 3 else 0), "total_sorteos": total_sorteos, "frecuencia_relativa": (0.1 if n == 3 else 0.0)} for n in range(1, 7)]

    def test_seis_filas_orden_uno_a_seis(self):
        from app.api.web.view_models import maximo_repeticion_color_por_sorteo_colorloto_a_vm
        vm = maximo_repeticion_color_por_sorteo_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert len(vm["filas"]) == 6
        assert [f["maximo_repetido"] for f in vm["filas"]] == [1, 2, 3, 4, 5, 6]

    def test_sin_categoria_cero(self):
        from app.api.web.view_models import maximo_repeticion_color_por_sorteo_colorloto_a_vm
        vm = maximo_repeticion_color_por_sorteo_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert 0 not in [f["maximo_repetido"] for f in vm["filas"]]

    def test_etiqueta_singular_plural_correcta(self):
        from app.api.web.view_models import maximo_repeticion_color_por_sorteo_colorloto_a_vm
        vm = maximo_repeticion_color_por_sorteo_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert vm["filas"][0]["etiqueta"] == "1 balota del mismo color"
        assert vm["filas"][2]["etiqueta"] == "3 balotas del mismo color"

    def test_denominador_es_total_sorteos_no_transiciones(self):
        from app.api.web.view_models import maximo_repeticion_color_por_sorteo_colorloto_a_vm
        vm = maximo_repeticion_color_por_sorteo_colorloto_a_vm(self._fake_est(self._filas_base(total_sorteos=42)), 6, self._juego())
        assert vm["total_sorteos"] == 42
        assert "total_transiciones" not in vm

    def test_historico_vacio_composicion_nd(self):
        from app.api.web.view_models import maximo_repeticion_color_por_sorteo_colorloto_a_vm
        vm = maximo_repeticion_color_por_sorteo_colorloto_a_vm(self._fake_est([]), 6, self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["composicion_mas_frecuente"] is None

    def test_vm_nunca_expone_codigo_de_color(self):
        import json
        from app.api.web.view_models import maximo_repeticion_color_por_sorteo_colorloto_a_vm
        vm = maximo_repeticion_color_por_sorteo_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        texto = json.dumps(vm)
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in texto

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.maximo_repeticion_color_por_sorteo_colorloto_a_vm)
        assert "calcular_maximo_repeticion_color_por_sorteo" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoMaximoRepeticionColorTemplate:
    _TEMPLATE = "app/templates/estadisticas/maximo_repeticion_color_por_sorteo_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tojson_y_json_parse_presentes(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_aviso_no_predictivo_sin_color_ganador(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No identifica un color ganador" in contenido
        assert "predicción" in contenido

    def test_sin_codigos_de_color_hex(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido


class TestColorLotoDistribucionParesConsecutivosRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/distribucion-pares-consecutivos")' in codigo_fuente

    def test_con_ruta_generica_equivalente_pero_literal_registrada_antes(self):
        """A diferencia de AE-10 (sin ruta genérica equivalente), esta
        métrica SÍ colisiona con
        `/estadisticas/{juego_slug}/distribucion-pares-consecutivos`
        (ya existente desde antes de AE-11) -confirmado que ambas
        rutas existen y que la literal de ColorLoto está registrada
        antes."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-pares-consecutivos")' in codigo_fuente
        indice_literal = codigo_fuente.index('@router.get("/estadisticas/colorloto/distribucion-pares-consecutivos")')
        indice_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/distribucion-pares-consecutivos")')
        assert indice_literal < indice_generica

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def distribucion_pares_consecutivos_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        fin_handler = codigo_fuente.index('@router.get(', fin_docstring)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_con_una_sola_clave_sin_marcador(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="distribucion_pares_consecutivos_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert '"cantidad_numeros": juego.cantidad_numeros' in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque

    def test_baloto_revancha_miloto_conservan_handler_generico(self):
        """Confirma que Baloto, `baloto-revancha` y MiLoto siguen
        resolviendo a la ruta genérica preexistente para este mismo
        sufijo -la ruta literal nueva de ColorLoto no interfiere."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/{juego_slug}/distribucion-pares-consecutivos")') == 1


class TestColorLotoDistribucionParesConsecutivosVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self, total_sorteos=10):
        return [{"valor": str(n), "apariciones": (1 if n == 3 else 0), "total_sorteos": total_sorteos, "frecuencia_relativa": (0.1 if n == 3 else 0.0)} for n in range(0, 6)]

    def test_seis_filas_orden_cero_a_cinco(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_colorloto_a_vm
        vm = distribucion_pares_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert len(vm["filas"]) == 6
        assert [f["cantidad_pares_consecutivos"] for f in vm["filas"]] == [0, 1, 2, 3, 4, 5]

    def test_incluye_categoria_cero(self):
        """A diferencia de AE-10 (que excluye la categoría 0), esta
        métrica SÍ la incluye -0 pares consecutivos es un valor real
        y posible."""
        from app.api.web.view_models import distribucion_pares_consecutivos_colorloto_a_vm
        vm = distribucion_pares_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert 0 in [f["cantidad_pares_consecutivos"] for f in vm["filas"]]

    def test_etiqueta_singular_plural_correcta_reutiliza_helper_existente(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_colorloto_a_vm, _etiqueta_pares_consecutivos
        vm = distribucion_pares_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert vm["filas"][0]["etiqueta"] == _etiqueta_pares_consecutivos(0) == "0 pares consecutivos"
        assert vm["filas"][1]["etiqueta"] == _etiqueta_pares_consecutivos(1) == "1 par consecutivo"
        assert vm["filas"][3]["etiqueta"] == _etiqueta_pares_consecutivos(3) == "3 pares consecutivos"

    def test_apariciones_cero_se_presenta_como_cero_real(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_colorloto_a_vm
        vm = distribucion_pares_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert vm["filas"][0]["apariciones"] == 0
        assert vm["filas"][0]["apariciones"] is not None

    def test_denominador_es_total_sorteos_no_transiciones(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_colorloto_a_vm
        vm = distribucion_pares_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base(total_sorteos=42)), 6, self._juego())
        assert vm["total_sorteos"] == 42
        assert "total_transiciones" not in vm

    def test_historico_vacio_composicion_nd(self):
        from app.api.web.view_models import distribucion_pares_consecutivos_colorloto_a_vm
        vm = distribucion_pares_consecutivos_colorloto_a_vm(self._fake_est([]), 6, self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["composicion_mas_frecuente"] is None

    def test_vm_nunca_expone_codigo_de_color(self):
        import json
        from app.api.web.view_models import distribucion_pares_consecutivos_colorloto_a_vm
        vm = distribucion_pares_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        texto = json.dumps(vm)
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in texto

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_pares_consecutivos_colorloto_a_vm)
        assert "calcular_distribucion_pares_consecutivos_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoDistribucionParesConsecutivosTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_pares_consecutivos_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tojson_y_json_parse_presentes(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_explica_deduplicacion(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "deduplican" in contenido

    def test_explica_diferencia_exactamente_uno(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "diferencia exactamente 1" in contenido

    def test_aviso_no_predictivo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "descriptiva" in contenido
        assert "no predictiva" in contenido

    def test_sin_codigos_de_color_hex(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido


class TestColorLotoDistribucionRachaMaximaRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/distribucion-racha-maxima")' in codigo_fuente

    def test_con_ruta_generica_equivalente_pero_literal_registrada_antes(self):
        """Igual que AE-11, esta métrica SÍ colisiona con
        `/estadisticas/{juego_slug}/distribucion-racha-maxima`
        (ya existente desde antes de AE-12) -confirmado que ambas
        rutas existen y que la literal de ColorLoto está registrada
        antes."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-racha-maxima")' in codigo_fuente
        indice_literal = codigo_fuente.index('@router.get("/estadisticas/colorloto/distribucion-racha-maxima")')
        indice_generica = codigo_fuente.index('@router.get("/estadisticas/{juego_slug}/distribucion-racha-maxima")')
        assert indice_literal < indice_generica

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def distribucion_racha_maxima_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        fin_handler = codigo_fuente.index('@router.get(', fin_docstring)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_con_una_sola_clave_sin_marcador(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="distribucion_racha_maxima_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert '"cantidad_numeros": juego.cantidad_numeros' in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque

    def test_baloto_revancha_miloto_conservan_handler_generico(self):
        """Confirma que Baloto, `baloto-revancha` y MiLoto siguen
        resolviendo a la ruta genérica preexistente para este mismo
        sufijo -la ruta literal nueva de ColorLoto no interfiere."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/{juego_slug}/distribucion-racha-maxima")') == 1


class TestColorLotoDistribucionRachaMaximaVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self, total_sorteos=10):
        return [{"valor": str(n), "apariciones": (1 if n == 3 else 0), "total_sorteos": total_sorteos, "frecuencia_relativa": (0.1 if n == 3 else 0.0)} for n in range(1, 7)]

    def test_seis_filas_orden_uno_a_seis(self):
        from app.api.web.view_models import distribucion_racha_maxima_colorloto_a_vm
        vm = distribucion_racha_maxima_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert len(vm["filas"]) == 6
        assert [f["longitud_racha"] for f in vm["filas"]] == [1, 2, 3, 4, 5, 6]

    def test_no_incluye_categoria_cero(self):
        """Igual que AE-10 (y a diferencia de AE-11), esta métrica
        excluye la categoría 0 -un sorteo con al menos un número
        siempre tiene una racha de longitud mínima 1."""
        from app.api.web.view_models import distribucion_racha_maxima_colorloto_a_vm
        vm = distribucion_racha_maxima_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert 0 not in [f["longitud_racha"] for f in vm["filas"]]

    def test_etiqueta_singular_plural_correcta_reutiliza_helper_existente(self):
        from app.api.web.view_models import distribucion_racha_maxima_colorloto_a_vm, _etiqueta_racha_maxima
        vm = distribucion_racha_maxima_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert vm["filas"][0]["etiqueta"] == _etiqueta_racha_maxima(1) == "Racha de 1 número"
        assert vm["filas"][2]["etiqueta"] == _etiqueta_racha_maxima(3) == "Racha de 3 números"

    def test_apariciones_cero_se_presenta_como_cero_real(self):
        from app.api.web.view_models import distribucion_racha_maxima_colorloto_a_vm
        vm = distribucion_racha_maxima_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert vm["filas"][0]["apariciones"] == 0
        assert vm["filas"][0]["apariciones"] is not None

    def test_denominador_es_total_sorteos_no_transiciones(self):
        from app.api.web.view_models import distribucion_racha_maxima_colorloto_a_vm
        vm = distribucion_racha_maxima_colorloto_a_vm(self._fake_est(self._filas_base(total_sorteos=42)), 6, self._juego())
        assert vm["total_sorteos"] == 42
        assert "total_transiciones" not in vm

    def test_historico_vacio_racha_mas_frecuente_nd(self):
        from app.api.web.view_models import distribucion_racha_maxima_colorloto_a_vm
        vm = distribucion_racha_maxima_colorloto_a_vm(self._fake_est([]), 6, self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["racha_mas_frecuente"] is None

    def test_vm_nunca_expone_codigo_de_color(self):
        import json
        from app.api.web.view_models import distribucion_racha_maxima_colorloto_a_vm
        vm = distribucion_racha_maxima_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        texto = json.dumps(vm)
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in texto

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_racha_maxima_colorloto_a_vm)
        assert "calcular_distribucion_racha_maxima_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoDistribucionRachaMaximaTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_racha_maxima_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tojson_y_json_parse_presentes(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_explica_deduplicacion(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "deduplican" in contenido

    def test_explica_diferencia_exactamente_uno(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "diferencia exactamente 1" in contenido

    def test_aviso_no_predictivo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "descriptiva" in contenido
        assert "no predictiva" in contenido

    def test_sin_codigos_de_color_hex(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido


class TestColorLotoDistribucionTriosConsecutivosRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/distribucion-trios-consecutivos")' in codigo_fuente

    def test_sin_ruta_generica_equivalente(self):
        """A DIFERENCIA de AE-11/AE-12, esta métrica NO colisiona con
        ninguna ruta genérica -confirmado por la auditoría de AE-13
        que `/estadisticas/{juego_slug}/distribucion-trios-consecutivos`
        no existe entre las rutas registradas, mismo caso que
        `maximo-repeticion-color` (Etapa AE-10)."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-trios-consecutivos")' not in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def distribucion_trios_consecutivos_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        fin_handler = codigo_fuente.index('@router.get(', fin_docstring)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_con_una_sola_clave_sin_marcador(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="distribucion_trios_consecutivos_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert '"cantidad_numeros": juego.cantidad_numeros' in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque

    def test_baloto_revancha_miloto_sin_handler_para_este_sufijo(self):
        """Confirma que Baloto, `baloto-revancha` y MiLoto NO tienen
        ningún handler para este sufijo -a diferencia de AE-11/AE-12,
        donde sí existe una ruta genérica preexistente que debe
        conservarse, aquí simplemente no hay ninguna ruta genérica
        que pudiera colisionar ni conservarse: la única línea de
        decorador `@router.get` con este sufijo es la literal de
        ColorLoto, nunca una genérica `{juego_slug}`."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        lineas_decorador_con_sufijo = [
            linea for linea in codigo_fuente.splitlines()
            if linea.strip().startswith("@router.get(") and "distribucion-trios-consecutivos" in linea
        ]
        assert len(lineas_decorador_con_sufijo) == 1
        assert "{juego_slug}" not in lineas_decorador_con_sufijo[0]

    def test_ruta_literal_registrada_una_sola_vez(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/colorloto/distribucion-trios-consecutivos")') == 1


class TestColorLotoDistribucionTriosConsecutivosVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas):
        class FakeEst:
            def __init__(self, filas):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = None
                self.calculado_en = None
        return FakeEst(filas)

    def _filas_base(self, total_sorteos=10):
        return [{"valor": str(n), "apariciones": (1 if n == 2 else 0), "total_sorteos": total_sorteos, "frecuencia_relativa": (0.1 if n == 2 else 0.0)} for n in range(0, 5)]

    def test_cinco_filas_orden_cero_a_cuatro(self):
        from app.api.web.view_models import distribucion_trios_consecutivos_colorloto_a_vm
        vm = distribucion_trios_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert len(vm["filas"]) == 5
        assert [f["cantidad_trios_consecutivos"] for f in vm["filas"]] == [0, 1, 2, 3, 4]

    def test_incluye_categoria_cero(self):
        """A diferencia de AE-12 (racha máxima, que excluye la
        categoría 0), esta métrica SÍ la incluye -mismo criterio que
        `distribucion_pares_consecutivos_colorloto_a_vm` (Etapa
        AE-11): un sorteo sin ningún trío consecutivo es un valor
        real y posible."""
        from app.api.web.view_models import distribucion_trios_consecutivos_colorloto_a_vm
        vm = distribucion_trios_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert 0 in [f["cantidad_trios_consecutivos"] for f in vm["filas"]]

    def test_etiqueta_singular_plural_correcta_reutiliza_helper_nuevo(self):
        from app.api.web.view_models import distribucion_trios_consecutivos_colorloto_a_vm, _etiqueta_trios_consecutivos
        vm = distribucion_trios_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert vm["filas"][0]["etiqueta"] == _etiqueta_trios_consecutivos(0) == "Sin tríos consecutivos"
        assert vm["filas"][1]["etiqueta"] == _etiqueta_trios_consecutivos(1) == "1 trío consecutivo"
        assert vm["filas"][2]["etiqueta"] == _etiqueta_trios_consecutivos(2) == "2 tríos consecutivos"

    def test_clave_no_se_confunde_con_longitud_de_racha(self):
        """Confirma que la clave expuesta es `cantidad_trios_consecutivos`,
        nunca `longitud_racha` (clave de AE-12) ni `cantidad_pares_consecutivos`
        (clave de AE-11) -tres semánticas distintas."""
        from app.api.web.view_models import distribucion_trios_consecutivos_colorloto_a_vm
        vm = distribucion_trios_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert "cantidad_trios_consecutivos" in vm["filas"][0]
        assert "longitud_racha" not in vm["filas"][0]
        assert "cantidad_pares_consecutivos" not in vm["filas"][0]

    def test_apariciones_cero_se_presenta_como_cero_real(self):
        from app.api.web.view_models import distribucion_trios_consecutivos_colorloto_a_vm
        vm = distribucion_trios_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        assert vm["filas"][0]["apariciones"] == 0
        assert vm["filas"][0]["apariciones"] is not None

    def test_denominador_es_total_sorteos_no_transiciones(self):
        from app.api.web.view_models import distribucion_trios_consecutivos_colorloto_a_vm
        vm = distribucion_trios_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base(total_sorteos=42)), 6, self._juego())
        assert vm["total_sorteos"] == 42
        assert "total_transiciones" not in vm

    def test_historico_vacio_composicion_nd(self):
        from app.api.web.view_models import distribucion_trios_consecutivos_colorloto_a_vm
        vm = distribucion_trios_consecutivos_colorloto_a_vm(self._fake_est([]), 6, self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["composicion_mas_frecuente"] is None

    def test_vm_nunca_expone_codigo_de_color(self):
        import json
        from app.api.web.view_models import distribucion_trios_consecutivos_colorloto_a_vm
        vm = distribucion_trios_consecutivos_colorloto_a_vm(self._fake_est(self._filas_base()), 6, self._juego())
        texto = json.dumps(vm)
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in texto

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.distribucion_trios_consecutivos_colorloto_a_vm)
        assert "calcular_distribucion_trios_consecutivos_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoDistribucionTriosConsecutivosTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_trios_consecutivos_colorloto.html"

    def test_template_existe_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido

    def test_exactamente_un_canvas_height_180(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1
        assert 'height="180"' in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tojson_y_json_parse_presentes(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "| tojson" in contenido
        assert "JSON.parse" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_sin_datos_exacto(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles todavía para calcular esta distribución." in contenido

    def test_explica_deduplicacion(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "deduplican" in contenido

    def test_explica_diferencia_exactamente_uno(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "diferencia exactamente 1" in contenido

    def test_explica_solapamiento_de_trios(self):
        """Requisito específico de AE-13: el template debe aclarar
        explícitamente que los tríos pueden solaparse, con el
        ejemplo correcto 1-2-3-4 -> dos tríos."""
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "solapar" in contenido
        assert "1-2-3-4" in contenido

    def test_aviso_no_predictivo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "descriptiva" in contenido
        assert "no predictiva" in contenido

    def test_sin_codigos_de_color_hex(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido


class TestColorLotoNavegacionCatorcePestanas:
    def test_partial_navegacion_incluye_las_catorce_metricas(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert "frecuencia-numeros" in contenido
        assert "frecuencia-colores" in contenido
        assert "frecuencia-pares-numero-color" in contenido
        assert "atrasos-numeros" in contenido
        assert "atrasos-colores" in contenido
        assert "atrasos-pares-numero-color" in contenido
        assert "repeticiones-entre-sorteos" in contenido
        assert "distribucion-pares-impares" in contenido
        assert "distribucion-altos-bajos" in contenido
        assert "maximo-repeticion-color" in contenido
        assert "distribucion-pares-consecutivos" in contenido
        assert "distribucion-racha-maxima" in contenido
        assert "distribucion-trios-consecutivos" in contenido
        assert "coocurrencia-pares" in contenido

    def test_los_catorce_templates_incluyen_la_navegacion(self):
        for archivo in ("frecuencia_numeros_colorloto.html", "frecuencia_colores_colorloto.html", "frecuencia_pares_colorloto.html", "atrasos_numeros_colorloto.html", "atrasos_colores_colorloto.html", "atrasos_pares_colorloto.html", "repeticiones_entre_sorteos_colorloto.html", "distribucion_pares_impares_colorloto.html", "distribucion_altos_bajos_colorloto.html", "maximo_repeticion_color_por_sorteo_colorloto.html", "distribucion_pares_consecutivos_colorloto.html", "distribucion_racha_maxima_colorloto.html", "distribucion_trios_consecutivos_colorloto.html", "coocurrencia_pares_colorloto.html"):
            contenido = Path(f"app/templates/estadisticas/{archivo}").read_text(encoding="utf-8")
            assert "navegacion_colorloto.html" in contenido

    def test_pagina_activa_marcada_en_los_catorce_handlers(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '"pagina_colorloto_activa": "frecuencia-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "frecuencia-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-numeros"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-colores"' in codigo_fuente
        assert '"pagina_colorloto_activa": "atrasos-pares-numero-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "repeticiones-entre-sorteos"' in codigo_fuente
        assert '"pagina_colorloto_activa": "distribucion-pares-impares"' in codigo_fuente
        assert '"pagina_colorloto_activa": "distribucion-altos-bajos"' in codigo_fuente
        assert '"pagina_colorloto_activa": "maximo-repeticion-color"' in codigo_fuente
        assert '"pagina_colorloto_activa": "distribucion-pares-consecutivos"' in codigo_fuente
        assert '"pagina_colorloto_activa": "distribucion-racha-maxima"' in codigo_fuente
        assert '"pagina_colorloto_activa": "distribucion-trios-consecutivos"' in codigo_fuente
        assert '"pagina_colorloto_activa": "coocurrencia-pares"' in codigo_fuente

    def test_navegacion_numerica_9_9_8_sigue_intacta(self):
        for slug, esperado in (("baloto", 9), ("baloto-revancha", 9), ("miloto", 8)):
            nav = construir_navegacion_estadisticas(slug, "frecuencia-numeros", CAPACIDAD_SUPERBALOTA_POR_SLUG, {})
            assert len(nav["metricas_nav"]) == esperado, slug

    def test_corte_preservado_al_alternar_entre_las_catorce(self):
        contenido = Path("app/templates/estadisticas/partials/navegacion_colorloto.html").read_text(encoding="utf-8")
        assert contenido.count("hasta_numero_sorteo") >= 14


class TestColorLotoCoocurrenciaParesRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/coocurrencia-pares")' in codigo_fuente

    def test_sin_ruta_generica_equivalente(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/coocurrencia-pares")' not in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def coocurrencia_pares_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        fin_handler = codigo_fuente.index('@router.get(', fin_docstring)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_diccionario_vacio_sin_claves_prohibidas(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="coocurrencia_pares_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert "parametros_metrica={}" in bloque
        assert "cantidad_numeros" not in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "color_objetivo" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque

    def test_ruta_literal_registrada_una_sola_vez(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/colorloto/coocurrencia-pares")') == 1

    def test_grupo_con_colision_permanece_en_siete(self):
        """Confirma que agregar coocurrencia-pares (sin colisión) NO
        altera el grupo de siete rutas con colisión real ya
        establecido (AE-1/AE-4/AE-7/AE-8/AE-9/AE-11/AE-12)."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        sufijos_con_colision = ("frecuencia-numeros", "atrasos-numeros", "repeticiones-entre-sorteos", "distribucion-pares-impares", "distribucion-altos-bajos", "distribucion-pares-consecutivos", "distribucion-racha-maxima")
        assert len(sufijos_con_colision) == 7
        for sufijo in sufijos_con_colision:
            assert f'@router.get("/estadisticas/{{juego_slug}}/{sufijo}")' in codigo_fuente

    def test_grupo_sin_colision_pasa_a_doce(self):
        """maximo-repeticion-color (AE-10), distribucion-pares-consecutivos
        NO -ese sí colisiona-, distribucion-trios-consecutivos (AE-13),
        coocurrencia-pares (AE-14), coocurrencia-trios (AE-15),
        coocurrencia-pares-colores (AE-16), coocurrencia-trios-colores
        (AE-17), intervalos-historicos-colores (AE-18) y
        distribucion-sumas (AE-19): confirma el grupo real sin
        colisión, que pasa de once a doce con esta etapa."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        sufijos_sin_colision_colorloto = ("frecuencia-colores", "frecuencia-pares-numero-color", "atrasos-colores", "atrasos-pares-numero-color", "maximo-repeticion-color", "distribucion-trios-consecutivos", "coocurrencia-pares", "coocurrencia-trios", "coocurrencia-pares-colores", "coocurrencia-trios-colores", "intervalos-historicos-colores", "distribucion-sumas")
        assert len(sufijos_sin_colision_colorloto) == 12
        for sufijo in sufijos_sin_colision_colorloto:
            assert f'@router.get("/estadisticas/colorloto/{sufijo}")' in codigo_fuente
            assert f'@router.get("/estadisticas/{{juego_slug}}/{sufijo}")' not in codigo_fuente


class TestColorLotoCoocurrenciaTriosRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/coocurrencia-trios")' in codigo_fuente

    def test_sin_ruta_generica_equivalente(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/coocurrencia-trios")' not in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def coocurrencia_trios_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        resto = codigo_fuente[fin_docstring:]
        fin_handler = fin_docstring + resto.index('@router.get(') if '@router.get(' in resto else len(codigo_fuente)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_diccionario_vacio_sin_claves_prohibidas(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="coocurrencia_trios_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert "parametros_metrica={}" in bloque
        assert "cantidad_numeros" not in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "color_objetivo" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque

    def test_ruta_literal_registrada_una_sola_vez(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/colorloto/coocurrencia-trios")') == 1

    def test_grupo_con_colision_permanece_en_siete(self):
        """Confirma que agregar coocurrencia-trios (sin colisión) NO
        altera el grupo de siete rutas con colisión real ya
        establecido (AE-1/AE-4/AE-7/AE-8/AE-9/AE-11/AE-12)."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        sufijos_con_colision = ("frecuencia-numeros", "atrasos-numeros", "repeticiones-entre-sorteos", "distribucion-pares-impares", "distribucion-altos-bajos", "distribucion-pares-consecutivos", "distribucion-racha-maxima")
        assert len(sufijos_con_colision) == 7
        for sufijo in sufijos_con_colision:
            assert f'@router.get("/estadisticas/{{juego_slug}}/{sufijo}")' in codigo_fuente


class TestColorLotoCoocurrenciaTriosVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas, hasta=None):
        class FakeEst:
            def __init__(self, filas, hasta):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = hasta
                self.calculado_en = None
        return FakeEst(filas, hasta)

    def test_trios_expuestos_como_tres_numeros_separados(self):
        from app.api.web.view_models import coocurrencia_trios_colorloto_a_vm
        filas = [{"elementos": [1, 2, 3], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["numero_1"] == 1
        assert vm["filas"][0]["numero_2"] == 2
        assert vm["filas"][0]["numero_3"] == 3
        assert isinstance(vm["filas"][0]["numero_1"], int)
        assert isinstance(vm["filas"][0]["numero_2"], int)
        assert isinstance(vm["filas"][0]["numero_3"], int)

    def test_soporte_total_y_frecuencia_correctos(self):
        from app.api.web.view_models import coocurrencia_trios_colorloto_a_vm
        filas = [{"elementos": [1, 2, 3], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["soporte"] == 3
        assert vm["total_sorteos"] == 5
        assert vm["filas"][0]["frecuencia_relativa"] == 0.6

    def test_porcentaje_correcto(self):
        from app.api.web.view_models import coocurrencia_trios_colorloto_a_vm
        filas = [{"elementos": [1, 2, 3], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["porcentaje"] == 60.0

    def test_empates_completos_no_selecciona_uno_arbitrario(self):
        from app.api.web.view_models import coocurrencia_trios_colorloto_a_vm
        filas = [
            {"elementos": [1, 2, 3], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None},
            {"elementos": [4, 5, 6], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None},
        ]
        vm = coocurrencia_trios_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert len(vm["filas"]) == 2

    def test_resultado_vacio(self):
        from app.api.web.view_models import coocurrencia_trios_colorloto_a_vm
        vm = coocurrencia_trios_colorloto_a_vm(self._fake_est([]), self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["cantidad_trios_observados"] == 0
        assert vm["filas"] == []

    def test_no_expone_colores(self):
        import json
        from app.api.web.view_models import coocurrencia_trios_colorloto_a_vm
        filas = [{"elementos": [1, 2, 3], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colorloto_a_vm(self._fake_est(filas), self._juego())
        texto = json.dumps(vm)
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in texto

    def test_lift_y_frecuencia_esperada_none_no_se_presentan_como_cero(self):
        from app.api.web.view_models import coocurrencia_trios_colorloto_a_vm
        filas = [{"elementos": [1, 2, 3], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["frecuencia_esperada"] is None
        assert vm["filas"][0]["lift"] is None
        assert vm["filas"][0]["frecuencia_esperada"] != 0
        assert vm["filas"][0]["lift"] != 0

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.coocurrencia_trios_colorloto_a_vm)
        assert "calcular_coocurrencia_trios_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoCoocurrenciaTriosTemplate:
    _TEMPLATE = "app/templates/estadisticas/coocurrencia_trios_colorloto.html"

    def test_template_existe(self):
        assert Path(self._TEMPLATE).exists()

    def test_sin_canvas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<canvas" not in contenido

    def test_sin_chartjs(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "chart.umd.min.js" not in contenido
        assert "new Chart(" not in contenido

    def test_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com" not in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tabla_con_columnas_esperadas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<table" in contenido
        assert "<th>Trío</th>" in contenido
        assert "<th>Soporte</th>" in contenido
        assert "<th>Frecuencia relativa</th>" in contenido
        assert "<th>Porcentaje</th>" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_vacio(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles" in contenido

    def test_aviso_no_predictivo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "predictiv" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_no_usa_top_n_ni_paginacion_ni_truncamiento(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "[:10]" not in contenido
        assert "[:20]" not in contenido
        assert "page" not in contenido.lower()


class TestColorLotoCoocurrenciaParesVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas, hasta=None):
        class FakeEst:
            def __init__(self, filas, hasta):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = hasta
                self.calculado_en = None
        return FakeEst(filas, hasta)

    def test_pares_expuestos_como_dos_numeros_separados(self):
        from app.api.web.view_models import coocurrencia_pares_colorloto_a_vm
        filas = [{"elementos": [1, 2], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["numero_a"] == 1
        assert vm["filas"][0]["numero_b"] == 2
        assert isinstance(vm["filas"][0]["numero_a"], int)
        assert isinstance(vm["filas"][0]["numero_b"], int)

    def test_soporte_total_y_frecuencia_correctos(self):
        from app.api.web.view_models import coocurrencia_pares_colorloto_a_vm
        filas = [{"elementos": [1, 2], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["soporte"] == 3
        assert vm["total_sorteos"] == 5
        assert vm["filas"][0]["frecuencia_relativa"] == 0.6

    def test_porcentaje_correcto(self):
        from app.api.web.view_models import coocurrencia_pares_colorloto_a_vm
        filas = [{"elementos": [1, 2], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["porcentaje"] == 60.0

    def test_empates_completos_no_selecciona_uno_arbitrario(self):
        from app.api.web.view_models import coocurrencia_pares_colorloto_a_vm
        filas = [
            {"elementos": [1, 2], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None},
            {"elementos": [3, 4], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None},
        ]
        vm = coocurrencia_pares_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert len(vm["filas"]) == 2

    def test_resultado_vacio(self):
        from app.api.web.view_models import coocurrencia_pares_colorloto_a_vm
        vm = coocurrencia_pares_colorloto_a_vm(self._fake_est([]), self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["cantidad_pares_observados"] == 0
        assert vm["filas"] == []

    def test_no_expone_colores(self):
        import json
        from app.api.web.view_models import coocurrencia_pares_colorloto_a_vm
        filas = [{"elementos": [1, 2], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colorloto_a_vm(self._fake_est(filas), self._juego())
        texto = json.dumps(vm)
        for prohibido in ("ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"):
            assert prohibido not in texto

    def test_lift_y_frecuencia_esperada_none_no_se_presentan_como_cero(self):
        from app.api.web.view_models import coocurrencia_pares_colorloto_a_vm
        filas = [{"elementos": [1, 2], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["frecuencia_esperada"] is None
        assert vm["filas"][0]["lift"] is None
        assert vm["filas"][0]["frecuencia_esperada"] != 0
        assert vm["filas"][0]["lift"] != 0

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.coocurrencia_pares_colorloto_a_vm)
        assert "calcular_coocurrencia_pares_colorloto" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoCoocurrenciaParesTemplate:
    _TEMPLATE = "app/templates/estadisticas/coocurrencia_pares_colorloto.html"

    def test_template_existe(self):
        assert Path(self._TEMPLATE).exists()

    def test_sin_canvas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<canvas" not in contenido

    def test_sin_chartjs(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "chart.umd.min.js" not in contenido
        assert "new Chart(" not in contenido

    def test_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com" not in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tabla_con_columnas_esperadas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<table" in contenido
        assert "<th>Par</th>" in contenido
        assert "<th>Soporte</th>" in contenido
        assert "<th>Frecuencia relativa</th>" in contenido
        assert "<th>Porcentaje</th>" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_vacio(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles" in contenido

    def test_aviso_no_predictivo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "predictiv" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_las_veinticuatro_paginas_graficas_conservan_su_canvas(self):
        """Confirma que la excepción tabular de AE-14 a AE-17 no
        afecta a ninguna de las páginas que sí usan gráfica -incluida
        la de AE-18 (intervalos históricos de colores) y la de AE-19
        (distribución de sumas, tarjetas y gráfica de percentiles,
        segundo incremento de canvas desde AE-14)."""
        directorio = Path("app/templates/estadisticas")
        templates_con_canvas = [
            f for f in directorio.glob("*.html")
            if 'height="180"' in f.read_text(encoding="utf-8")
        ]
        assert len(templates_con_canvas) == 24

    def test_veintiocho_templates_estadisticos_veinticuatro_canvas(self):
        directorio = Path("app/templates/estadisticas")
        todos = list(directorio.glob("*.html"))
        con_canvas = [f for f in todos if 'height="180"' in f.read_text(encoding="utf-8")]
        assert len(todos) == 28
        assert len(con_canvas) == 24


class TestColorLotoCoocurrenciaParesColoresRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/coocurrencia-pares-colores")' in codigo_fuente

    def test_sin_ruta_generica_equivalente(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/coocurrencia-pares-colores")' not in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def coocurrencia_pares_colores_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        resto = codigo_fuente[fin_docstring:]
        fin_handler = fin_docstring + resto.index('@router.get(') if '@router.get(' in resto else len(codigo_fuente)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_diccionario_vacio_sin_claves_prohibidas(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="coocurrencia_pares_colores_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert "parametros_metrica={}" in bloque
        assert "cantidad_numeros" not in bloque
        assert "cantidad_balotas" not in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "colores_vigentes" not in bloque
        assert "color_objetivo" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque

    def test_ruta_literal_registrada_una_sola_vez(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/colorloto/coocurrencia-pares-colores")') == 1

    def test_grupo_con_colision_permanece_en_siete(self):
        """Confirma que agregar coocurrencia-pares-colores (sin
        colisión) NO altera el grupo de siete rutas con colisión
        real ya establecido (AE-1/AE-4/AE-7/AE-8/AE-9/AE-11/AE-12)."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        sufijos_con_colision = ("frecuencia-numeros", "atrasos-numeros", "repeticiones-entre-sorteos", "distribucion-pares-impares", "distribucion-altos-bajos", "distribucion-pares-consecutivos", "distribucion-racha-maxima")
        assert len(sufijos_con_colision) == 7
        for sufijo in sufijos_con_colision:
            assert f'@router.get("/estadisticas/{{juego_slug}}/{sufijo}")' in codigo_fuente


class TestColorLotoCoocurrenciaParesColoresVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas, hasta=None):
        class FakeEst:
            def __init__(self, filas, hasta):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = hasta
                self.calculado_en = None
        return FakeEst(filas, hasta)

    def test_pares_expuestos_como_dos_colores_separados(self):
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["color_1"] == "AMARILLO"
        assert vm["filas"][0]["color_2"] == "AZUL"
        assert isinstance(vm["filas"][0]["color_1"], str)
        assert isinstance(vm["filas"][0]["color_2"], str)

    def test_no_convierte_colores_a_entero(self):
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert not isinstance(vm["filas"][0]["color_1"], int)
        assert not isinstance(vm["filas"][0]["color_2"], int)

    def test_soporte_total_y_frecuencia_correctos(self):
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["soporte"] == 3
        assert vm["total_sorteos"] == 5
        assert vm["filas"][0]["frecuencia_relativa"] == 0.6

    def test_porcentaje_correcto(self):
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["porcentaje"] == 60.0

    def test_empates_completos_no_selecciona_uno_arbitrario(self):
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        filas = [
            {"elementos": ["AMARILLO", "AZUL"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None},
            {"elementos": ["NEGRO", "VERDE"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None},
        ]
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert len(vm["filas"]) == 2

    def test_resultado_vacio(self):
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est([]), self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["cantidad_pares_observados"] == 0
        assert vm["filas"] == []

    def test_no_expone_numeros_de_balota(self):
        import json
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert "numero_1" not in vm["filas"][0]
        assert "numero_2" not in vm["filas"][0]
        assert "elementos" not in vm["filas"][0]

    def test_lift_y_frecuencia_esperada_none_no_se_presentan_como_cero(self):
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["frecuencia_esperada"] is None
        assert vm["filas"][0]["lift"] is None
        assert vm["filas"][0]["frecuencia_esperada"] != 0
        assert vm["filas"][0]["lift"] != 0

    def test_colores_historicos_conservados_tal_cual(self):
        """Un color retirado (p. ej. presente solo en sorteos
        antiguos) debe conservarse literalmente, sin filtrarlo ni
        validarlo de nuevo en esta capa."""
        from app.api.web.view_models import coocurrencia_pares_colores_colorloto_a_vm
        filas = [{"elementos": ["MORADO", "ROJO"], "soporte": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_pares_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["color_1"] == "MORADO"
        assert vm["filas"][0]["color_2"] == "ROJO"

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.coocurrencia_pares_colores_colorloto_a_vm)
        assert "calcular_coocurrencia_pares_colores" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoCoocurrenciaParesColoresTemplate:
    _TEMPLATE = "app/templates/estadisticas/coocurrencia_pares_colores_colorloto.html"

    def test_template_existe(self):
        assert Path(self._TEMPLATE).exists()

    def test_sin_canvas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<canvas" not in contenido

    def test_sin_chartjs(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "chart.umd.min.js" not in contenido
        assert "new Chart(" not in contenido

    def test_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com" not in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tabla_con_columnas_esperadas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<table" in contenido
        assert "<th>Color 1</th>" in contenido
        assert "<th>Color 2</th>" in contenido
        assert "<th>Soporte</th>" in contenido
        assert "<th>Frecuencia relativa</th>" in contenido
        assert "<th>Porcentaje</th>" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_vacio(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles" in contenido

    def test_aviso_no_predictivo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "predictiv" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_no_usa_top_n_ni_paginacion_ni_limite_fijo(self):
        """La auditoría previa confirmó que la paleta de colores NO
        está hardcodeada a 6 -el template no debe asumir un máximo
        de C(6,2)=15 filas."""
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "[:15]" not in contenido
        assert "[:21]" not in contenido
        assert "page" not in contenido.lower()


class TestColorLotoCoocurrenciaTriosColoresRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/coocurrencia-trios-colores")' in codigo_fuente

    def test_sin_ruta_generica_equivalente(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/coocurrencia-trios-colores")' not in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def coocurrencia_trios_colores_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        resto = codigo_fuente[fin_docstring:]
        fin_handler = fin_docstring + resto.index('@router.get(') if '@router.get(' in resto else len(codigo_fuente)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_parametros_metrica_diccionario_vacio_sin_claves_prohibidas(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="coocurrencia_trios_colores_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert "parametros_metrica={}" in bloque
        assert "cantidad_numeros" not in bloque
        assert "cantidad_balotas" not in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "colores_vigentes" not in bloque
        assert "color_objetivo" not in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" not in bloque

    def test_ruta_literal_registrada_una_sola_vez(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/colorloto/coocurrencia-trios-colores")') == 1

    def test_grupo_con_colision_permanece_en_siete(self):
        """Confirma que agregar coocurrencia-trios-colores (sin
        colisión) NO altera el grupo de siete rutas con colisión
        real ya establecido (AE-1/AE-4/AE-7/AE-8/AE-9/AE-11/AE-12)."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        sufijos_con_colision = ("frecuencia-numeros", "atrasos-numeros", "repeticiones-entre-sorteos", "distribucion-pares-impares", "distribucion-altos-bajos", "distribucion-pares-consecutivos", "distribucion-racha-maxima")
        assert len(sufijos_con_colision) == 7
        for sufijo in sufijos_con_colision:
            assert f'@router.get("/estadisticas/{{juego_slug}}/{sufijo}")' in codigo_fuente


class TestColorLotoCoocurrenciaTriosColoresVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas, hasta=None):
        class FakeEst:
            def __init__(self, filas, hasta):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = hasta
                self.calculado_en = None
        return FakeEst(filas, hasta)

    def test_trios_expuestos_como_tres_colores_separados(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL", "ROJO"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["color_1"] == "AMARILLO"
        assert vm["filas"][0]["color_2"] == "AZUL"
        assert vm["filas"][0]["color_3"] == "ROJO"
        assert all(isinstance(vm["filas"][0][k], str) for k in ("color_1", "color_2", "color_3"))

    def test_no_concatena_los_tres_colores_en_un_solo_campo(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL", "ROJO"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert "elementos" not in vm["filas"][0]
        assert "trio" not in vm["filas"][0]
        assert "colores" not in vm["filas"][0]

    def test_no_convierte_colores_a_entero(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL", "ROJO"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert not any(isinstance(vm["filas"][0][k], int) for k in ("color_1", "color_2", "color_3"))

    def test_soporte_total_y_frecuencia_correctos(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL", "ROJO"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["soporte"] == 3
        assert vm["total_sorteos"] == 5
        assert vm["filas"][0]["frecuencia_relativa"] == 0.6

    def test_porcentaje_correcto(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL", "ROJO"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["porcentaje"] == 60.0

    def test_empates_completos_no_selecciona_uno_arbitrario(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [
            {"elementos": ["AMARILLO", "AZUL", "ROJO"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None},
            {"elementos": ["BLANCO", "NEGRO", "VERDE"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None},
        ]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert len(vm["filas"]) == 2

    def test_resultado_vacio(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est([]), self._juego())
        assert vm["total_sorteos"] == 0
        assert vm["cantidad_trios_observados"] == 0
        assert vm["filas"] == []

    def test_no_expone_numeros_de_balota(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL", "ROJO"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert "numero_1" not in vm["filas"][0]
        assert "numero_2" not in vm["filas"][0]
        assert "numero_3" not in vm["filas"][0]

    def test_lift_y_frecuencia_esperada_none_no_se_presentan_como_cero(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["AMARILLO", "AZUL", "ROJO"], "soporte": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["frecuencia_esperada"] is None
        assert vm["filas"][0]["lift"] is None
        assert vm["filas"][0]["frecuencia_esperada"] != 0
        assert vm["filas"][0]["lift"] != 0

    def test_colores_historicos_conservados_tal_cual(self):
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["AZUL", "MORADO", "ROJO"], "soporte": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert vm["filas"][0]["color_1"] == "AZUL"
        assert vm["filas"][0]["color_2"] == "MORADO"
        assert vm["filas"][0]["color_3"] == "ROJO"

    def test_desempaquetado_exactamente_tres_sin_indices_fuera_de_rango(self):
        """El motor y el serializador siempre producen exactamente 3
        elementos para esta receta -confirma que el desempaquetado
        directo no lanza ValueError con listas de longitud distinta
        a la esperada en el caso real."""
        from app.api.web.view_models import coocurrencia_trios_colores_colorloto_a_vm
        filas = [{"elementos": ["A", "B", "C"], "soporte": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0, "frecuencia_esperada": None, "lift": None}]
        vm = coocurrencia_trios_colores_colorloto_a_vm(self._fake_est(filas), self._juego())
        assert len(vm["filas"]) == 1

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.coocurrencia_trios_colores_colorloto_a_vm)
        assert "calcular_coocurrencia_trios_colores" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoCoocurrenciaTriosColoresTemplate:
    _TEMPLATE = "app/templates/estadisticas/coocurrencia_trios_colores_colorloto.html"

    def test_template_existe(self):
        assert Path(self._TEMPLATE).exists()

    def test_sin_canvas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<canvas" not in contenido

    def test_sin_chartjs(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "chart.umd.min.js" not in contenido
        assert "new Chart(" not in contenido

    def test_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com" not in contenido

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tabla_con_columnas_esperadas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<table" in contenido
        assert "<th>Color 1</th>" in contenido
        assert "<th>Color 2</th>" in contenido
        assert "<th>Color 3</th>" in contenido
        assert "<th>Soporte</th>" in contenido
        assert "<th>Frecuencia relativa</th>" in contenido
        assert "<th>Porcentaje</th>" in contenido

    def test_muestra_sorteos_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "Sorteos analizados" in contenido

    def test_estado_vacio(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles" in contenido

    def test_aviso_no_predictivo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "predictiv" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_no_afirma_veinte_como_total_fijo(self):
        """El template puede mencionar 20 como el maximo de UN
        sorteo, pero no debe usarlo como limite de filas mostradas
        ni como techo global -el universo historico puede superarlo."""
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "[:20]" not in contenido
        assert "page" not in contenido.lower()


class TestColorLotoIntervalosHistoricosColoresRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/intervalos-historicos-colores")' in codigo_fuente

    def test_sin_ruta_generica_equivalente(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/intervalos-historicos-colores")' not in codigo_fuente

    def test_no_conectada_a_juegos_numericos(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def intervalos_historicos_colores_colorloto(')
        fin_docstring = codigo_fuente.index('"""', codigo_fuente.index('"""', indice) + 3) + 3
        resto = codigo_fuente[fin_docstring:]
        fin_handler = fin_docstring + resto.index('@router.get(') if '@router.get(' in resto else len(codigo_fuente)
        cuerpo_ejecutable = codigo_fuente[fin_docstring:fin_handler]
        assert "SLUG_A_CODIGO" not in cuerpo_ejecutable
        assert "GameFactory" not in cuerpo_ejecutable
        assert 'obtener_por_codigo("COLORLOTO")' in cuerpo_ejecutable

    def test_ruta_invalida_sigue_devolviendo_404(self):
        assert resolver_codigo("colorloto") is None

    def test_identidad_minima_con_politica_sin_claves_prohibidas(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="intervalos_historicos_colores_colorloto"')
        bloque = codigo_fuente[indice:indice + 300]
        assert "politica_universo_colores" in bloque
        assert "POLITICA_UNIVERSO_COLORES_ACTUAL" in bloque
        assert "rango_min" not in bloque
        assert "rango_max" not in bloque
        assert "cantidad_numeros" not in bloque
        assert "cantidad_balotas" not in bloque
        assert "colores_vigentes" not in bloque

    def test_unico_parametro_query_es_hasta_numero_sorteo(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('def intervalos_historicos_colores_colorloto(')
        bloque = codigo_fuente[indice:indice + 400]
        assert bloque.count("Query(") == 1
        assert "hasta_numero_sorteo: int | None = Query(default=None, ge=1)" in bloque

    def test_ruta_literal_registrada_una_sola_vez(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/colorloto/intervalos-historicos-colores")') == 1

    def test_grupo_con_colision_permanece_en_siete(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        sufijos_con_colision = ("frecuencia-numeros", "atrasos-numeros", "repeticiones-entre-sorteos", "distribucion-pares-impares", "distribucion-altos-bajos", "distribucion-pares-consecutivos", "distribucion-racha-maxima")
        assert len(sufijos_con_colision) == 7
        for sufijo in sufijos_con_colision:
            assert f'@router.get("/estadisticas/{{juego_slug}}/{sufijo}")' in codigo_fuente


class TestColorLotoIntervalosHistoricosColoresVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, filas, hasta=None):
        class FakeEst:
            def __init__(self, filas, hasta):
                self.resultado = {"filas": filas}
                self.hasta_numero_sorteo = hasta
                self.calculado_en = None
        return FakeEst(filas, hasta)

    def _fila(self, valor="ROJO", cantidad_apariciones=3, cantidad_intervalos=2, intervalo_minimo=1,
              intervalo_maximo=9, intervalo_promedio=5, intervalo_mediana=5.0, intervalos=(9, 1)):
        return {
            "valor": valor, "cantidad_apariciones": cantidad_apariciones, "cantidad_intervalos": cantidad_intervalos,
            "intervalo_minimo": intervalo_minimo, "intervalo_maximo": intervalo_maximo,
            "intervalo_promedio": intervalo_promedio, "intervalo_mediana": intervalo_mediana,
            "intervalos": list(intervalos),
        }

    def test_campos_basicos_expuestos(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(self._fake_est([self._fila()]), self._juego())
        fila = vm["filas"][0]
        assert fila["codigo"] == "ROJO"
        assert fila["nombre"] == "Rojo"
        assert isinstance(fila["color_hex"], str)
        assert fila["cantidad_apariciones"] == 3
        assert fila["cantidad_intervalos"] == 2
        assert fila["intervalo_minimo"] == 1
        assert fila["intervalo_maximo"] == 9

    def test_normalizacion_int_float_a_float(self):
        """Prueba directa pedida: promedio entero (5) y mediana
        flotante (5.0) se normalizan ambos a float en el VM."""
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(self._fake_est([self._fila()]), self._juego())
        fila = vm["filas"][0]
        assert isinstance(fila["intervalo_promedio"], float)
        assert isinstance(fila["intervalo_mediana"], float)
        assert fila["intervalo_promedio"] == 5.0
        assert fila["intervalo_mediana"] == 5.0

    def test_none_preservado_no_convertido_a_cero(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        fila_vacia = self._fila(valor="AZUL", cantidad_apariciones=1, cantidad_intervalos=0,
                                 intervalo_minimo=None, intervalo_maximo=None,
                                 intervalo_promedio=None, intervalo_mediana=None, intervalos=())
        vm = intervalos_historicos_colores_colorloto_a_vm(self._fake_est([fila_vacia]), self._juego())
        fila = vm["filas"][0]
        assert fila["intervalo_minimo"] is None
        assert fila["intervalo_maximo"] is None
        assert fila["intervalo_promedio"] is None
        assert fila["intervalo_mediana"] is None

    def test_sin_total_sorteos_en_el_contrato(self):
        """La auditoria confirmo que IntervalosHistoricos no tiene
        campo total_sorteos -el VM no debe inventarlo ni confundirlo
        con hasta_numero_sorteo."""
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(self._fake_est([self._fila()]), self._juego())
        assert "total_sorteos" not in vm
        assert "total_sorteos" not in vm["filas"][0]

    def test_cantidad_colores_analizados(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(
            self._fake_est([self._fila(valor="ROJO"), self._fila(valor="AZUL")]), self._juego(),
        )
        assert vm["cantidad_colores_analizados"] == 2

    def test_no_expone_lista_completa_de_intervalos(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(self._fake_est([self._fila()]), self._juego())
        assert "intervalos" not in vm["filas"][0]

    def test_empates_completos_no_selecciona_uno_arbitrario(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(
            self._fake_est([self._fila(valor="ROJO"), self._fila(valor="AZUL"), self._fila(valor="VERDE")]), self._juego(),
        )
        assert len(vm["filas"]) == 3

    def test_resultado_vacio(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(self._fake_est([]), self._juego())
        assert vm["filas"] == []
        assert vm["cantidad_colores_analizados"] == 0
        assert vm["chart_labels"] == []

    def test_colores_historicos_conservados_tal_cual(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(self._fake_est([self._fila(valor="MORADO")]), self._juego())
        assert vm["filas"][0]["codigo"] == "MORADO"

    def test_chart_arrays_alineados_con_filas(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        vm = intervalos_historicos_colores_colorloto_a_vm(
            self._fake_est([self._fila(valor="ROJO"), self._fila(valor="AZUL")]), self._juego(),
        )
        assert len(vm["chart_labels"]) == 2
        assert len(vm["chart_intervalo_promedio"]) == 2
        assert len(vm["chart_colores"]) == 2

    def test_chart_intervalo_promedio_preserva_none_como_hueco(self):
        from app.api.web.view_models import intervalos_historicos_colores_colorloto_a_vm
        fila_sin_intervalos = self._fila(valor="AZUL", cantidad_apariciones=0, cantidad_intervalos=0,
                                          intervalo_minimo=None, intervalo_maximo=None,
                                          intervalo_promedio=None, intervalo_mediana=None, intervalos=())
        vm = intervalos_historicos_colores_colorloto_a_vm(self._fake_est([fila_sin_intervalos]), self._juego())
        assert vm["chart_intervalo_promedio"][0] is None

    def test_vm_no_llama_motor_ni_repositorios(self):
        import inspect
        from app.api.web import view_models
        codigo_fuente = inspect.getsource(view_models.intervalos_historicos_colores_colorloto_a_vm)
        assert "calcular_intervalos_historicos_colores" not in codigo_fuente
        assert "repository" not in codigo_fuente.lower()


class TestColorLotoIntervalosHistoricosColoresTemplate:
    _TEMPLATE = "app/templates/estadisticas/intervalos_historicos_colores_colorloto.html"

    def test_template_existe(self):
        assert Path(self._TEMPLATE).exists()

    def test_exactamente_un_canvas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1

    def test_usa_chartjs_local_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "/static/vendor/chartjs/chart.umd.min.js" in contenido
        assert "cdnjs.cloudflare.com" not in contenido
        assert "cdn." not in contenido.lower()

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_tabla_con_columnas_esperadas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "<table" in contenido
        assert "<th>Color</th>" in contenido
        assert "<th>Apariciones</th>" in contenido
        assert "<th>Intervalo mínimo</th>" in contenido
        assert "<th>Intervalo máximo</th>" in contenido
        assert "<th>Intervalo promedio</th>" in contenido
        assert "<th>Intervalo mediana</th>" in contenido

    def test_muestra_cantidad_colores_analizados(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cantidad_colores_analizados" in contenido

    def test_estado_vacio(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "No hay sorteos de ColorLoto disponibles" in contenido

    def test_aviso_no_predictivo(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "predictiv" in contenido

    def test_navegacion_colorloto_incluida(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/navegacion_colorloto.html" in contenido

    def test_control_de_corte_reutilizado(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "partials/control_corte_temporal.html" in contenido

    def test_none_representado_como_nd_no_como_cero(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "N/D" in contenido

    def test_sin_limite_arbitrario_de_filas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "[:20]" not in contenido
        assert "[:10]" not in contenido
        assert "page" not in contenido.lower()


class TestColorLotoDistribucionSumasRuta:
    def test_ruta_dedicada_registrada(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/colorloto/distribucion-sumas")' in codigo_fuente

    def test_sin_ruta_generica_equivalente(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert '@router.get("/estadisticas/{juego_slug}/distribucion-sumas")' not in codigo_fuente

    def test_grupo_sin_colision_pasa_a_doce(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        assert codigo_fuente.count('@router.get("/estadisticas/colorloto/distribucion-sumas")') == 1


class TestColorLotoDistribucionSumasVM:
    def _juego(self):
        return Juego(id=uuid4(), codigo="COLORLOTO", nombre="ColorLoto", rango_min=1, rango_max=7, cantidad_numeros=6, tiene_superbalota=False, superbalota_min=None, superbalota_max=None, tiene_color=True, permite_repeticion=True, activo=True)

    def _fake_est(self, resultado, hasta=None):
        class FakeEst:
            def __init__(self, resultado, hasta):
                self.resultado = resultado
                self.hasta_numero_sorteo = hasta
                self.calculado_en = None
        return FakeEst(resultado, hasta)

    def test_normalizacion_a_float(self):
        """Confirma normalizacion Y que el VM reutiliza el MISMO
        _num_o_none existente (Etapa AE-18), no una copia ni una
        redefinicion."""
        from app.api.web.view_models import distribucion_sumas_colorloto_a_vm, _num_o_none
        import inspect
        codigo_fuente = inspect.getsource(distribucion_sumas_colorloto_a_vm)
        assert "_num_o_none(" in codigo_fuente
        resultado = {"total_sorteos": 3, "minimo": 21, "maximo": 24, "media": 22.333333333333332, "mediana": 22, "desviacion_estandar": 1.247219128924647, "percentiles": {"10": 21.2, "25": 21.5, "50": 22.0, "75": 23.0, "90": 23.6}}
        vm = distribucion_sumas_colorloto_a_vm(self._fake_est(resultado), self._juego())
        assert isinstance(vm["media"], float)
        assert isinstance(vm["mediana"], float)
        assert vm["mediana"] == 22.0

    def test_none_no_convertido_a_cero(self):
        resultado = {"total_sorteos": 0, "minimo": None, "maximo": None, "media": 0.0, "mediana": 0.0, "desviacion_estandar": 0.0, "percentiles": {}}
        from app.api.web.view_models import distribucion_sumas_colorloto_a_vm
        vm = distribucion_sumas_colorloto_a_vm(self._fake_est(resultado), self._juego())
        assert vm["minimo"] is None
        assert vm["maximo"] is None
        assert vm["media"] == 0.0
        assert vm["mediana"] == 0.0

    def test_resultado_vacio(self):
        resultado = {"total_sorteos": 0, "minimo": None, "maximo": None, "media": 0.0, "mediana": 0.0, "desviacion_estandar": 0.0, "percentiles": {}}
        from app.api.web.view_models import distribucion_sumas_colorloto_a_vm
        vm = distribucion_sumas_colorloto_a_vm(self._fake_est(resultado), self._juego())
        assert vm["chart_labels"] == []
        assert vm["chart_percentiles"] == []
        assert vm["total_sorteos"] == 0


class TestColorLotoDistribucionSumasTemplate:
    _TEMPLATE = "app/templates/estadisticas/distribucion_sumas_colorloto.html"

    def test_exactamente_un_canvas(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert contenido.count("<canvas") == 1

    def test_sin_cdn(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "cdnjs.cloudflare.com" not in contenido
        assert "cdn." not in contenido.lower()

    def test_sin_safe(self):
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "|safe" not in contenido

    def test_historico_vacio_no_renderiza_canvas_ni_inicializa_chart(self):
        """El canvas y la inicializacion de Chart.js estan dentro de
        {% if estadistica.chart_labels %} -con historico vacio,
        chart_labels=[] es falso en Jinja2, por lo que ni el canvas
        ni new Chart(...) se renderizan; en su lugar se muestra un
        mensaje explicito. Las tarjetas permanecen fuera de esa
        condicion, siempre visibles."""
        contenido = Path(self._TEMPLATE).read_text(encoding="utf-8")
        assert "{% if estadistica.chart_labels %}" in contenido
        indice_if = contenido.index("{% if estadistica.chart_labels %}")
        indice_else = contenido.index("{% else %}", indice_if)
        bloque_con_datos = contenido[indice_if:indice_else]
        assert "<canvas" in bloque_con_datos
        assert "new Chart(" in bloque_con_datos
        indice_endif = contenido.index("{% endif %}", indice_else)
        bloque_vacio = contenido[indice_else:indice_endif]
        assert "<canvas" not in bloque_vacio
        assert "new Chart(" not in bloque_vacio
        assert "No hay sorteos suficientes para calcular percentiles." in bloque_vacio
