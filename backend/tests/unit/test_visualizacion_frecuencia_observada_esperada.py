"""
Tests de la tercera visualización (comparación frecuencia observada
vs. esperada de números principales de Baloto).

Verificación previa e independiente (antes de escribir estos tests):
dataset de juguete rango 1..5, K=2, 4 sorteos, filtrado y contado
manualmente con `collections.Counter` -sin usar el orquestador ni el
motor- confirmó que el número 1 aparece 3/4=0.75 de frecuencia
observada, K/N esperado=2/5=0.4, diferencia=+0.35. Se comparó también
contra `construir_tabla_frecuencia` real, coincidiendo exactamente.

IMPORTANTE - transparencia sobre el alcance real de esta verificación
(misma limitación de las Etapas R-V, reverificada en este sandbox):
sigue sin PostgreSQL, `sqlalchemy` o `fastapi` instalados aquí. La
ruta HTTP en sí no pudo importarse ni ejecutarse. Lo que SÍ se
verifica, de verdad, ejecutado: `tabla_frecuencia_numeros_a_vm`
(código real de producción, no depende de fastapi/sqlalchemy) y el
flujo lógico completo (`CalcularYPersistirEstadistica.ejecutar(...)`
seguido de `tabla_frecuencia_numeros_a_vm(...)`), reconstruido con
los mismos componentes reales + fakes de los puertos -mismo
precedente honesto que R, S, T, U y V. Todas las lecturas de
templates usan `encoding="utf-8"` explícito desde el inicio (lección
de la corrección de encoding anterior).
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.web.view_models import tabla_frecuencia_numeros_a_vm
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
_CANTIDAD_NUMEROS = BalotoGame().numbers_to_pick  # fuente de verdad real, nunca "5" a mano


def _num(numero_sorteo: int, numeros: tuple[int, ...]) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=None,
    )


# Dataset de referencia (verificado independientemente con Counter,
# rango de juguete 1..5, K=2): el número 1 aparece 3/4 veces.
_DATASET = [
    _num(1, (1, 2)),
    _num(2, (1, 3)),
    _num(3, (1, 4)),
    _num(4, (2, 5)),
]


def _fila(valor: str, apariciones: int, total_sorteos: int, probabilidad: float, metodo: str, diferencia: float) -> dict:
    return {
        "valor": valor, "apariciones": apariciones,
        "frecuencia_observada": {
            "valor": valor, "apariciones": apariciones, "total_sorteos": total_sorteos,
            "frecuencia_relativa": (apariciones / total_sorteos) if total_sorteos else 0.0,
        },
        "probabilidad_teorica": {"valor": valor, "probabilidad": probabilidad, "metodo": metodo},
        "diferencia": diferencia,
    }


def _estadistica_calculada_fake(filas: list[dict], hasta_numero_sorteo=None, calculado_en=None) -> EstadisticaCalculada:
    return EstadisticaCalculada(
        id=uuid4(), juego_id=uuid4(), tipo_estadistica="tabla_frecuencia_numeros",
        hasta_numero_sorteo=hasta_numero_sorteo,
        parametros={"rango_min": 1, "rango_max": 5, "cantidad_numeros": 2},
        parametros_hash="x", resultado={"filas": filas}, calculado_en=calculado_en, valido_hasta=None,
    )


# =====================================================================
# 1. tabla_frecuencia_numeros_a_vm -código real de producción
# =====================================================================

class TestTablaFrecuenciaNumerosAVm:
    def test_ordena_numericamente_no_por_frecuencia(self):
        filas = [
            _fila("30", 5, 10, 0.4, "K/N = 2/5", 0.1),
            _fila("2", 1, 10, 0.4, "K/N = 2/5", -0.3),
            _fila("9", 9, 10, 0.4, "K/N = 2/5", 0.5),
        ]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert [f["valor"] for f in vm["filas"]] == ["2", "9", "30"]

    def test_alineacion_labels_observada_teorica(self):
        filas = [
            _fila("30", 5, 10, 0.4, "K/N = 2/5", 0.1),
            _fila("2", 1, 10, 0.4, "K/N = 2/5", -0.3),
        ]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["chart_labels"] == ["2", "30"]
        assert vm["chart_observada"] == [0.1, 0.5]
        assert vm["chart_teorica"] == [0.4, 0.4]

    def test_ambas_series_usan_la_misma_unidad_proporcion(self):
        """chart_observada y chart_teorica deben estar en [0,1], la
        misma unidad -nunca apariciones absolutas contra probabilidad."""
        filas = [_fila("1", 7, 10, 0.4, "K/N = 2/5", 0.3)]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 5, 2, _JUEGO_BALOTO)
        assert 0.0 <= vm["chart_observada"][0] <= 1.0
        assert 0.0 <= vm["chart_teorica"][0] <= 1.0
        assert vm["chart_observada"][0] == 0.7  # frecuencia_relativa, no "apariciones" cruda

    def test_conserva_rango_y_cantidad_numeros(self):
        filas = [_fila("1", 1, 1, 0.4, "K/N = 2/5", 0.6)]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["rango_min"] == 1
        assert vm["rango_max"] == 43
        assert vm["cantidad_numeros"] == 5

    def test_conserva_hasta_numero_sorteo(self):
        filas = [_fila("1", 1, 1, 0.4, "K/N = 2/5", 0.6)]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas, hasta_numero_sorteo=100), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["hasta_numero_sorteo"] == 100

    def test_serializa_calculado_en_como_isoformat(self):
        momento = datetime(2024, 6, 15, 10, 30, tzinfo=timezone.utc)
        filas = [_fila("1", 1, 1, 0.4, "K/N = 2/5", 0.6)]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas, calculado_en=momento), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["calculado_en"] == momento.isoformat()

    def test_total_sorteos_correcto(self):
        filas = [_fila("1", 3, 7, 0.4, "K/N = 2/5", 0.028)]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["total_sorteos"] == 7

    def test_filas_vacias_no_falla(self):
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake([]), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["filas"] == []
        assert vm["chart_labels"] == []
        assert vm["total_sorteos"] == 0
        assert vm["metodo_teorico"] == "K/N = 5/43"  # reconstruido a partir de los parametros dados

    def test_no_muta_el_resultado_original(self):
        filas = [
            _fila("30", 5, 10, 0.4, "K/N = 2/5", 0.1),
            _fila("2", 1, 10, 0.4, "K/N = 2/5", -0.3),
        ]
        import copy
        copia_filas = copy.deepcopy(filas)
        tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert filas == copia_filas

    def test_valores_no_observados_conservan_frecuencia_cero(self):
        filas = [_fila("7", 0, 5, 0.4, "K/N = 2/5", -0.4)]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        assert vm["chart_observada"][0] == 0.0

    def test_diferencia_positiva_negativa_y_cero_se_conservan(self):
        filas = [
            _fila("1", 7, 10, 0.4, "K/N = 2/5", 0.3),   # positiva
            _fila("2", 4, 10, 0.4, "K/N = 2/5", 0.0),   # cero
            _fila("3", 1, 10, 0.4, "K/N = 2/5", -0.3),  # negativa
        ]
        vm = tabla_frecuencia_numeros_a_vm(_estadistica_calculada_fake(filas), 1, 43, 5, _JUEGO_BALOTO)
        por_valor = {f["valor"]: f["diferencia"] for f in vm["filas"]}
        assert por_valor["1"] > 0
        assert por_valor["2"] == 0
        assert por_valor["3"] < 0


# =====================================================================
# 2. Flujo lógico completo: CalcularYPersistirEstadistica ->
#    tabla_frecuencia_numeros_a_vm, reconstruido con fakes.
# =====================================================================

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


def _parametros(rango_min=1, rango_max=5, cantidad_numeros=2) -> dict:
    return {"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}


class TestFlujoLogicoCompletoDeLaRuta:
    def test_pipeline_completo_hasta_el_view_model(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "tabla_frecuencia_numeros", parametros_metrica=_parametros(),
        )
        vm = tabla_frecuencia_numeros_a_vm(resultado, 1, 5, 2, _JUEGO_BALOTO)

        assert vm["total_sorteos"] == 4  # verificado independientemente arriba
        indice_1 = vm["chart_labels"].index("1")
        assert vm["chart_observada"][indice_1] == 0.75
        assert vm["chart_teorica"][indice_1] == 0.4

    def test_anti_fuga_temporal(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros(),
        )
        vm = tabla_frecuencia_numeros_a_vm(resultado, 1, 5, 2, _JUEGO_BALOTO)
        assert vm["total_sorteos"] == 3  # S4 (posterior al corte) excluido

    def test_cache_funciona_segunda_llamada_no_recalcula(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        parametros = _parametros()

        primera = orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", parametros_metrica=parametros)
        cantidad_tras_primera = len(estadistica_repo._filas)
        segunda = orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", parametros_metrica=parametros)

        assert len(estadistica_repo._filas) == cantidad_tras_primera
        assert primera.id == segunda.id

    def test_sin_sorteos_produce_estado_valido_sin_datos(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", parametros_metrica=_parametros())
        vm = tabla_frecuencia_numeros_a_vm(resultado, 1, 5, 2, _JUEGO_BALOTO)
        assert vm["total_sorteos"] == 0
        assert (vm["total_sorteos"] > 0) is False


# =====================================================================
# 3. Contenido estático de los 3 templates -no requiere fastapi/Jinja2
# =====================================================================

class TestTemplateObservadaEsperadaContenido:
    def test_template_referencia_chartjs_por_cdn(self):
        contenido = open("app/templates/estadisticas/frecuencia_observada_esperada.html", encoding="utf-8").read()
        assert "chart.umd.min.js" in contenido
        assert "new Chart(" in contenido

    def test_template_usa_tojson(self):
        contenido = open("app/templates/estadisticas/frecuencia_observada_esperada.html", encoding="utf-8").read()
        assert "tojson" in contenido

    def test_template_maneja_estado_sin_conexion_y_sin_datos(self):
        contenido = open("app/templates/estadisticas/frecuencia_observada_esperada.html", encoding="utf-8").read()
        assert "db_conectada" in contenido
        assert "tiene_sorteos" in contenido

    def test_template_incluye_aviso_no_predictivo(self):
        contenido = open("app/templates/estadisticas/frecuencia_observada_esperada.html", encoding="utf-8").read()
        assert "no aumenta ni reduce" in contenido.lower() or "no es una predicción" in contenido.lower()

    def test_template_menciona_proximo_sorteo(self):
        contenido = open("app/templates/estadisticas/frecuencia_observada_esperada.html", encoding="utf-8").read()
        assert "próximo sorteo" in contenido or "siguiente sorteo" in contenido


class TestNavegacionEntreLasTresPantallas:
    """Actualizado por la generalización a 3 juegos: ver
    `test_generalizacion_juegos.py::TestNavegacionDosNiveles` para la
    cobertura detallada de la navegación dinámica real."""

    def test_frecuencia_numeros_usa_navegacion_dinamica(self):
        contenido = open("app/templates/estadisticas/frecuencia_numeros.html", encoding="utf-8").read()
        assert "juegos_nav" in contenido and "metricas_nav" in contenido

    def test_frecuencia_superbalota_usa_navegacion_dinamica(self):
        contenido = open("app/templates/estadisticas/frecuencia_superbalota.html", encoding="utf-8").read()
        assert "juegos_nav" in contenido and "metricas_nav" in contenido

    def test_frecuencia_observada_esperada_usa_navegacion_dinamica(self):
        contenido = open("app/templates/estadisticas/frecuencia_observada_esperada.html", encoding="utf-8").read()
        assert "juegos_nav" in contenido and "metricas_nav" in contenido
