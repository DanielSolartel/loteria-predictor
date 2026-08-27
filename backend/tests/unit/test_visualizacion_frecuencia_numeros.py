"""
Tests de la Etapa U (visualización de frecuencia de números de Baloto).

IMPORTANTE - transparencia sobre el alcance real de esta verificación
(limitación más severa que en R/S/T, reverificada en este sandbox):
sigue sin PostgreSQL, sin `sqlalchemy` instalado, Y ADEMÁS sin
`fastapi` instalado. Esto significa que
`app/api/web/routers/estadisticas.py` y `app/main.py` (ambos importan
`fastapi`) NO PUDIERON IMPORTARSE en este entorno, ni mucho menos
ejecutarse como una aplicación HTTP real. No se afirma en ningún
punto haber levantado la aplicación ni haber accedido a la ruta por
HTTP/navegador.

Lo que SÍ se verifica, de verdad, ejecutado:

  1. `frecuencia_numeros_a_vm` (`view_models.py`) -no depende de
     fastapi ni sqlalchemy, se importa y ejecuta directamente, código
     de producción real, contra un dataset verificado
     independientemente con `collections.Counter` antes de escribir
     estos tests.

  2. El FLUJO LÓGICO completo que la ruta ejecutaría
     (`CalcularYPersistirEstadistica.ejecutar(...)` seguido de
     `frecuencia_numeros_a_vm(...)`), reconstruido explícitamente con
     los mismos componentes reales (el caso de uso real de la Etapa
     T, ya verificado sin necesitar fastapi/sqlalchemy) más fakes de
     los dos puertos -mismo precedente honesto que R, S y T. Esto
     confirma que la INTEGRACIÓN de datos entre el caso de uso y el
     view model es correcta, aunque el decorador de FastAPI y el
     manejo HTTP en sí no se ejecutaron.

No se afirma cobertura de: el decorador `@router.get(...)`, el
manejo de sesión HTTP, la respuesta HTML final, ni el renderizado de
Jinja2 -ninguno de estos pudo ejecutarse sin `fastapi` instalado.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.web.view_models import frecuencia_numeros_a_vm
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

_FECHA_BASE = date(2024, 1, 1)
_RANGO_MIN, _RANGO_MAX = BalotoGame().number_range
_JUEGO_BALOTO = Juego(
    id=None, codigo="BALOTO", nombre="Baloto", rango_min=_RANGO_MIN, rango_max=_RANGO_MAX,
    cantidad_numeros=5, tiene_superbalota=True, superbalota_min=1, superbalota_max=16,
    tiene_color=False, permite_repeticion=False, activo=True,
)


def _num(numero_sorteo: int, numeros: tuple[int, ...]) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=None,
    )


_DATASET = [
    _num(1, (5, 10, 15, 20, 25)),
    _num(2, (5, 11, 16, 21, 26)),
    _num(3, (5, 10, 17, 22, 27)),
]


def _estadistica_calculada_fake(filas: list[dict], hasta_numero_sorteo=None, calculado_en=None) -> EstadisticaCalculada:
    return EstadisticaCalculada(
        id=uuid4(), juego_id=uuid4(), tipo_estadistica="frecuencia_numeros",
        hasta_numero_sorteo=hasta_numero_sorteo, parametros={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        parametros_hash="x", resultado={"filas": filas}, calculado_en=calculado_en, valido_hasta=None,
    )


class TestFrecuenciaNumerosAVm:
    def test_ordena_numericamente_no_por_frecuencia(self):
        filas = [
            {"valor": "30", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "17", "apariciones": 9, "total_sorteos": 10, "frecuencia_relativa": 0.9},
        ]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert [f["valor"] for f in vm["filas"]] == ["2", "17", "30"]

    def test_chart_labels_y_valores_en_el_mismo_orden(self):
        filas = [
            {"valor": "30", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert vm["chart_labels"] == ["2", "30"]
        assert vm["chart_valores"] == [1, 5]

    def test_incluye_numeros_con_frecuencia_cero(self):
        filas = [
            {"valor": "1", "apariciones": 0, "total_sorteos": 5, "frecuencia_relativa": 0.0},
            {"valor": "2", "apariciones": 3, "total_sorteos": 5, "frecuencia_relativa": 0.6},
        ]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert vm["chart_valores"][vm["chart_labels"].index("1")] == 0

    def test_total_sorteos_y_rango_correctos(self):
        filas = [{"valor": "1", "apariciones": 2, "total_sorteos": 7, "frecuencia_relativa": 0.28}]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert vm["total_sorteos"] == 7
        assert vm["rango_min"] == 1
        assert vm["rango_max"] == 43

    def test_hasta_numero_sorteo_se_conserva(self):
        filas = [{"valor": "1", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas, hasta_numero_sorteo=100), 1, 43, _JUEGO_BALOTO)
        assert vm["hasta_numero_sorteo"] == 100

    def test_calculado_en_serializado_como_isoformat(self):
        momento = datetime(2024, 6, 15, 10, 30, tzinfo=timezone.utc)
        filas = [{"valor": "1", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas, calculado_en=momento), 1, 43, _JUEGO_BALOTO)
        assert vm["calculado_en"] == momento.isoformat()

    def test_calculado_en_none_si_no_hay_dato(self):
        filas = [{"valor": "1", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas, calculado_en=None), 1, 43, _JUEGO_BALOTO)
        assert vm["calculado_en"] is None

    def test_lista_de_filas_vacia_no_falla(self):
        vm = frecuencia_numeros_a_vm(_estadistica_calculada_fake([]), 1, 43, _JUEGO_BALOTO)
        assert vm["filas"] == []
        assert vm["chart_labels"] == []
        assert vm["total_sorteos"] == 0

    def test_no_muta_el_resultado_original(self):
        filas = [
            {"valor": "30", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        copia_filas = [dict(f) for f in filas]
        frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, _JUEGO_BALOTO)
        assert filas == copia_filas


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
        guardada = EstadisticaCalculada(
            id=uuid4(), juego_id=entrada.juego_id, tipo_estadistica=entrada.tipo_estadistica,
            hasta_numero_sorteo=entrada.hasta_numero_sorteo, parametros=entrada.parametros,
            parametros_hash=calcular_parametros_hash(entrada.parametros), resultado=entrada.resultado,
            calculado_en=datetime.now(timezone.utc), valido_hasta=entrada.valido_hasta,
        )
        self._filas.append(guardada)
        return guardada

    def buscar_vigente(self, juego_id, tipo_estadistica, hasta_numero_sorteo, parametros):
        hash_calculado = calcular_parametros_hash(parametros)
        for fila in self._filas:
            if (
                fila.juego_id == juego_id and fila.tipo_estadistica == tipo_estadistica
                and fila.hasta_numero_sorteo == hasta_numero_sorteo and fila.parametros_hash == hash_calculado
            ):
                return fila
        return None

    def invalidar_por_juego(self, juego_id, desde_numero_sorteo=None) -> int:
        raise NotImplementedError

    def listar_por_juego_y_tipo(self, juego_id, tipo_estadistica):
        raise NotImplementedError


class TestFlujoLogicoCompletoDeLaRuta:
    def test_pipeline_completo_hasta_el_view_model(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=2,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        vm = frecuencia_numeros_a_vm(resultado, _RANGO_MIN, _RANGO_MAX, _JUEGO_BALOTO)

        assert vm["total_sorteos"] == 2
        indice_5 = vm["chart_labels"].index("5")
        assert vm["chart_valores"][indice_5] == 2

    def test_numero_43_nunca_observado_aparece_con_cero(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=2,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        vm = frecuencia_numeros_a_vm(resultado, _RANGO_MIN, _RANGO_MAX, _JUEGO_BALOTO)
        indice_43 = vm["chart_labels"].index("43")
        assert vm["chart_valores"][indice_43] == 0

    def test_anti_fuga_sorteo_posterior_al_corte_nunca_participa(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=2,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        vm = frecuencia_numeros_a_vm(resultado, _RANGO_MIN, _RANGO_MAX, _JUEGO_BALOTO)
        indice_17 = vm["chart_labels"].index("17")
        assert vm["chart_valores"][indice_17] == 0

    def test_cache_funciona_segunda_llamada_no_recalcula(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}

        primera = orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=2, parametros_metrica=parametros)
        cantidad_guardadas_tras_primera = len(estadistica_repo._filas)
        segunda = orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=2, parametros_metrica=parametros)

        assert len(estadistica_repo._filas) == cantidad_guardadas_tras_primera
        assert primera.id == segunda.id

    def test_sin_sorteos_produce_estado_valido_sin_datos(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        vm = frecuencia_numeros_a_vm(resultado, _RANGO_MIN, _RANGO_MAX, _JUEGO_BALOTO)
        assert vm["total_sorteos"] == 0
        assert (vm["total_sorteos"] > 0) is False


class TestTemplateContieneChartJs:
    def test_template_referencia_chartjs_por_cdn(self):
        contenido = open("app/templates/estadisticas/frecuencia_numeros.html", encoding="utf-8").read()
        assert "chart.umd.min.js" in contenido
        assert "new Chart(" in contenido

    def test_template_usa_tojson_para_pasar_datos_sin_concatenacion_insegura(self):
        contenido = open("app/templates/estadisticas/frecuencia_numeros.html", encoding="utf-8").read()
        assert "tojson" in contenido

    def test_template_maneja_estado_sin_conexion_y_sin_datos(self):
        contenido = open("app/templates/estadisticas/frecuencia_numeros.html", encoding="utf-8").read()
        assert "db_conectada" in contenido
        assert "tiene_sorteos" in contenido
