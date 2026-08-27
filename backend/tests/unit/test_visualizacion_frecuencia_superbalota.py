"""
Tests de la Etapa V (visualización de frecuencia de superbalota de
Baloto), actualizados en Etapa AD para reflejar la política de
integridad histórica endurecida.

Verificación previa e independiente (antes de escribir estos tests):
dataset de 4 sorteos con corte en numero_sorteo=3, filtrado y contado
manualmente con `collections.Counter` -sin usar el orquestador ni el
motor- para confirmar que la superbalota 9 aparece 2 veces (S1,S2)
dentro del corte, con total_sorteos=3 (los 3 sorteos del corte tienen
dato válido), y que S4 (posterior al corte) nunca participa. Se
comparó también contra `calcular_frecuencia_superbalota` real,
coincidiendo exactamente.

Etapa AD -endurecimiento de integridad: un histórico con
superbalota=None para un juego que la requiere ya NO se excluye
silenciosamente del denominador (comportamiento previo del motor,
nunca una decisión de negocio validada) -ahora
`_validar_historico_superbalota_consistente` rechaza el cálculo
completo antes de invocar el motor, ver
`TestFlujoLogicoCompletoDeLaRutaSuperbalota::test_superbalota_ausente_rechaza_el_calculo`.

IMPORTANTE - transparencia sobre el alcance real de esta verificación
(misma limitación de las Etapas R-U, reverificada en este sandbox):
sigue sin PostgreSQL, sin `sqlalchemy`, sin `fastapi` instalados. La
ruta HTTP en sí (`app/api/web/routers/estadisticas.py`) no pudo
importarse ni ejecutarse. Lo que SÍ se verifica, de verdad,
ejecutado: `frecuencia_superbalota_a_vm` (código real de producción,
no depende de fastapi/sqlalchemy) y el flujo lógico completo
(`CalcularYPersistirEstadistica.ejecutar(...)` seguido de
`frecuencia_superbalota_a_vm(...)`), reconstruido con los mismos
componentes reales + fakes de los puertos -mismo precedente honesto
que R, S, T y U.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.web.view_models import frecuencia_superbalota_a_vm
from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.interfaces.estadistica_repository import (
    EstadisticaCalculada,
    EstadisticaRepository,
    calcular_parametros_hash,
)
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.use_cases.calcular_y_persistir_estadistica import CalcularYPersistirEstadistica
from app.application.exceptions import ResultadoHistoricoInconsistenteError, TipoInconsistenciaHistorica
from app.domain.entities.juego import Juego
from app.domain.games.baloto import BalotoGame

_FECHA_BASE = date(2024, 1, 1)
_SB_MIN, _SB_MAX = BalotoGame().superballot_range  # fuente de verdad real, nunca "1, 16" a mano
_JUEGO_BALOTO = Juego(
    id=None, codigo="BALOTO", nombre="Baloto", rango_min=1, rango_max=43,
    cantidad_numeros=5, tiene_superbalota=True, superbalota_min=_SB_MIN, superbalota_max=_SB_MAX,
    tiene_color=False, permite_repeticion=False, activo=True,
)


def _num(numero_sorteo: int, numeros: tuple[int, ...], superbalota) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=superbalota,
    )


# Dataset verificado independientemente con Counter (ver docstring):
# la superbalota 9 aparece 2 veces dentro del corte=3; S4 es
# posterior al corte.
_DATASET = [
    _num(1, (1, 2, 3, 4, 5), 9),
    _num(2, (6, 7, 8, 9, 10), 9),
    _num(3, (1, 2, 3, 4, 5), 5),       # Etapa AD: valor válido -antes None
    _num(4, (1, 2, 3, 4, 5), 3),
]


def _estadistica_calculada_fake(filas: list[dict], hasta_numero_sorteo=None, calculado_en=None) -> EstadisticaCalculada:
    return EstadisticaCalculada(
        id=uuid4(), juego_id=uuid4(), tipo_estadistica="frecuencia_superbalota",
        hasta_numero_sorteo=hasta_numero_sorteo, parametros={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
        parametros_hash="x", resultado={"filas": filas}, calculado_en=calculado_en, valido_hasta=None,
    )


# =====================================================================
# 1. frecuencia_superbalota_a_vm -código real de producción, tests reales
# =====================================================================

class TestFrecuenciaSuperbalotaAVm:
    def test_ordena_numericamente_no_por_frecuencia(self):
        filas = [
            {"valor": "16", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
            {"valor": "9", "apariciones": 9, "total_sorteos": 10, "frecuencia_relativa": 0.9},
        ]
        vm = frecuencia_superbalota_a_vm(_estadistica_calculada_fake(filas), 1, 16, _JUEGO_BALOTO)
        assert [f["valor"] for f in vm["filas"]] == ["2", "9", "16"]

    def test_chart_labels_y_valores_en_el_mismo_orden(self):
        filas = [
            {"valor": "16", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        vm = frecuencia_superbalota_a_vm(_estadistica_calculada_fake(filas), 1, 16, _JUEGO_BALOTO)
        assert vm["chart_labels"] == ["2", "16"]
        assert vm["chart_valores"] == [1, 5]

    def test_total_sorteos_y_rango_correctos(self):
        filas = [{"valor": "1", "apariciones": 2, "total_sorteos": 7, "frecuencia_relativa": 0.28}]
        vm = frecuencia_superbalota_a_vm(_estadistica_calculada_fake(filas), 1, 16, _JUEGO_BALOTO)
        assert vm["total_sorteos"] == 7
        assert vm["rango_min"] == 1
        assert vm["rango_max"] == 16

    def test_hasta_numero_sorteo_se_conserva(self):
        filas = [{"valor": "1", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = frecuencia_superbalota_a_vm(_estadistica_calculada_fake(filas, hasta_numero_sorteo=100), 1, 16, _JUEGO_BALOTO)
        assert vm["hasta_numero_sorteo"] == 100

    def test_calculado_en_serializado_como_isoformat(self):
        momento = datetime(2024, 6, 15, 10, 30, tzinfo=timezone.utc)
        filas = [{"valor": "1", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = frecuencia_superbalota_a_vm(_estadistica_calculada_fake(filas, calculado_en=momento), 1, 16, _JUEGO_BALOTO)
        assert vm["calculado_en"] == momento.isoformat()

    def test_lista_de_filas_vacia_no_falla(self):
        vm = frecuencia_superbalota_a_vm(_estadistica_calculada_fake([]), 1, 16, _JUEGO_BALOTO)
        assert vm["filas"] == []
        assert vm["chart_labels"] == []
        assert vm["total_sorteos"] == 0

    def test_no_muta_el_resultado_original(self):
        filas = [
            {"valor": "16", "apariciones": 5, "total_sorteos": 10, "frecuencia_relativa": 0.5},
            {"valor": "2", "apariciones": 1, "total_sorteos": 10, "frecuencia_relativa": 0.1},
        ]
        copia_filas = [dict(f) for f in filas]
        frecuencia_superbalota_a_vm(_estadistica_calculada_fake(filas), 1, 16, _JUEGO_BALOTO)
        assert filas == copia_filas

    def test_rango_no_hardcodeado_usa_lo_que_se_le_pase(self):
        """El view model no asume 1-16 -respeta el rango recibido,
        que en producción viene de juego_dominio.superballot_range."""
        filas = [{"valor": "5", "apariciones": 1, "total_sorteos": 1, "frecuencia_relativa": 1.0}]
        vm = frecuencia_superbalota_a_vm(_estadistica_calculada_fake(filas), 3, 8, _JUEGO_BALOTO)
        assert vm["rango_min"] == 3
        assert vm["rango_max"] == 8


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


class TestFlujoLogicoCompletoDeLaRutaSuperbalota:
    def test_pipeline_completo_hasta_el_view_model(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
        )
        vm = frecuencia_superbalota_a_vm(resultado, _SB_MIN, _SB_MAX, _JUEGO_BALOTO)

        assert vm["total_sorteos"] == 3  # Etapa AD: los 3 sorteos del corte tienen dato válido
        indice_9 = vm["chart_labels"].index("9")
        assert vm["chart_valores"][indice_9] == 2

    def test_superbalota_ausente_rechaza_el_calculo(self):
        """Etapa AD: antes se excluía silenciosamente del denominador
        (comportamiento del motor, no una política de negocio
        validada); ahora se rechaza el cálculo completo, ya que la
        auditoría confirmó que ese estado nunca surge de una
        operación legítima para un juego con superbalota."""
        juego_id = uuid4()
        dataset_con_ausente = [_num(1, (1, 2, 3, 4, 5), 9), _num(2, (6, 7, 8, 9, 10), None)]
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: dataset_con_ausente})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        try:
            orquestador.ejecutar(
                juego_id, "frecuencia_superbalota",
                parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
            )
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.SUPERBALOTA_AUSENTE
        assert len(estadistica_repo._filas) == 0

    def test_anti_fuga_sorteo_posterior_al_corte_nunca_participa(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
        )
        vm = frecuencia_superbalota_a_vm(resultado, _SB_MIN, _SB_MAX, _JUEGO_BALOTO)
        # sb=3 solo aparece en S4 (posterior al corte)
        indice_3 = vm["chart_labels"].index("3")
        assert vm["chart_valores"][indice_3] == 0

    def test_cache_funciona_segunda_llamada_no_recalcula(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: list(_DATASET)})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        parametros = {"rango_min": _SB_MIN, "rango_max": _SB_MAX}

        primera = orquestador.ejecutar(juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3, parametros_metrica=parametros)
        cantidad_tras_primera = len(estadistica_repo._filas)
        segunda = orquestador.ejecutar(juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3, parametros_metrica=parametros)

        assert len(estadistica_repo._filas) == cantidad_tras_primera
        assert primera.id == segunda.id

    def test_sin_sorteos_produce_estado_valido_sin_datos(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoria({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoria()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
        )
        vm = frecuencia_superbalota_a_vm(resultado, _SB_MIN, _SB_MAX, _JUEGO_BALOTO)
        assert vm["total_sorteos"] == 0
        assert (vm["total_sorteos"] > 0) is False


class TestTemplateSuperbalotaContenido:
    """Verificación estática del contenido del template -no requiere
    fastapi/Jinja2 en ejecución, solo lectura del archivo."""

    def test_template_referencia_chartjs_por_cdn(self):
        contenido = open("app/templates/estadisticas/frecuencia_superbalota.html", encoding="utf-8").read()
        assert "chart.umd.min.js" in contenido
        assert "new Chart(" in contenido

    def test_template_usa_tojson(self):
        contenido = open("app/templates/estadisticas/frecuencia_superbalota.html", encoding="utf-8").read()
        assert "tojson" in contenido

    def test_template_maneja_estado_sin_conexion_y_sin_datos(self):
        contenido = open("app/templates/estadisticas/frecuencia_superbalota.html", encoding="utf-8").read()
        assert "db_conectada" in contenido
        assert "tiene_sorteos" in contenido

    def test_template_incluye_aviso_no_predictivo(self):
        contenido = open("app/templates/estadisticas/frecuencia_superbalota.html", encoding="utf-8").read()
        assert "predicción" in contenido or "no es una predicción" in contenido.lower()
        assert "histórica" in contenido.lower() or "histórico" in contenido.lower()

    def test_template_aclara_que_no_predice_el_proximo_sorteo(self):
        contenido = open("app/templates/estadisticas/frecuencia_superbalota.html", encoding="utf-8").read()
        assert "próximo sorteo" in contenido or "siguiente sorteo" in contenido


class TestNavegacionEntreVisualizaciones:
    """Actualizado por la generalización a 3 juegos: la navegación ya
    no es un href estático por página -es dinámica, construida en el
    servidor vía `juegos_nav`/`metricas_nav` (ver `view_models.py`).
    La cobertura detallada de esa navegación dinámica vive en
    `test_generalizacion_juegos.py::TestNavegacionDosNiveles`; aquí
    solo se confirma que el mecanismo dinámico sigue presente en el
    template (no una URL fija que ya no existe por diseño)."""

    def test_frecuencia_numeros_usa_navegacion_dinamica(self):
        contenido = open("app/templates/estadisticas/frecuencia_numeros.html", encoding="utf-8").read()
        assert "metricas_nav" in contenido
        assert 'href="{{ m.url }}"' in contenido

    def test_frecuencia_superbalota_usa_navegacion_dinamica(self):
        contenido = open("app/templates/estadisticas/frecuencia_superbalota.html", encoding="utf-8").read()
        assert "metricas_nav" in contenido
        assert 'href="{{ m.url }}"' in contenido
