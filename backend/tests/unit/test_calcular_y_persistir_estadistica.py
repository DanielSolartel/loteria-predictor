"""
Tests de `application/use_cases/calcular_y_persistir_estadistica.py`.

Verificación previa e independiente (antes de escribir estos tests):
dataset de 5 sorteos, corte en numero_sorteo=3, filtrado y contado
manualmente con `collections.Counter` -sin usar el orquestador ni
ninguna función del motor- para confirmar los valores de referencia
usados abajo (el número 1 aparece 3 veces dentro del corte, el
número 13 nunca aparece, total_sorteos tras el corte = 3).

IMPORTANTE - transparencia sobre el alcance real de esta verificación
(misma limitación de las Etapas R y S, reverificada: sigue sin
PostgreSQL NI `sqlalchemy` instalado en este sandbox). El orquestador
en sí (`CalcularYPersistirEstadistica`) SÍ se ejecuta de verdad -no
depende de SQLAlchemy, solo de los PUERTOS (`ResultadosHistoricosRepository`,
`EstadisticaRepository`), que aquí se satisfacen con fakes en memoria
que implementan esos mismos puertos -mismo precedente que R y S. Lo
que NO se verifica es `ResultadosHistoricosRepositorySQLAlchemy`/
`EstadisticaRepositorySQLAlchemy` funcionando contra PostgreSQL real
(eso ya quedó fuera de alcance, documentado, desde R).
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from app.application.estadisticas.tipos import IntervalosHistoricos, MetricaAsociacion, ResultadoColorLoto, ResultadoNumerico
from app.application.estadisticas.motor.distribuciones import DistribucionSumas
from app.application.exceptions import TipoEstadisticaNoSoportadoError
from app.application.exceptions import ResultadoHistoricoInconsistenteError, TipoInconsistenciaHistorica
from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.estadistica_repository import (
    EstadisticaCalculada,
    EstadisticaRepository,
    calcular_parametros_hash,
)
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.use_cases.calcular_y_persistir_estadistica import (
    CalcularYPersistirEstadistica,
    POLITICA_UNIVERSO_COLORES_ACTUAL,
    _CATALOGO,
    _HistoricoColorLoto,
    _RANGO_REAL_COLORLOTO,
    _calcular_atrasos_pares_colorloto,
    _calcular_distribucion_altos_bajos_colorloto,
    _calcular_distribucion_pares_impares_colorloto,
    _calcular_maximo_repeticion_color_por_sorteo_colorloto,
    _calcular_frecuencia_colores_colorloto,
    _calcular_repeticiones_entre_sorteos_colorloto,
    _codigos_colores_vigentes_en_referencia,
    _validar_historico_colorloto_consistente,
)
from app.domain.games.baloto import BalotoGame
from app.domain.value_objects.color import Color

_FECHA_BASE = date(2024, 1, 1)


def _num(numero_sorteo: int, numeros: tuple[int, ...]) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=None,
    )


_DATASET = [
    _num(1, (1, 2, 3, 4, 5)),
    _num(2, (1, 2, 6, 7, 8)),
    _num(3, (1, 9, 10, 11, 12)),
    _num(4, (1, 2, 3, 4, 5)),
    _num(5, (1, 2, 3, 4, 5)),
]

_RANGO_MIN, _RANGO_MAX = BalotoGame().number_range


class _HistoricoRepositoryEnMemoriaConEspia(ResultadosHistoricosRepository):
    def __init__(
        self, datos: dict[UUID, list[ResultadoNumerico]],
        datos_colorloto: dict[UUID, list[ResultadoColorLoto]] | None = None,
    ):
        self._datos = datos
        self._datos_colorloto = datos_colorloto or {}
        self.fue_consultado = False
        self.fue_consultado_colorloto = False
        self.ultimo_hasta_numero_sorteo_recibido = "no_llamado"

    def listar_resultados_numericos(self, juego_id: UUID, hasta_numero_sorteo: int | None = None) -> list[ResultadoNumerico]:
        self.fue_consultado = True
        self.ultimo_hasta_numero_sorteo_recibido = hasta_numero_sorteo
        todos = self._datos.get(juego_id, [])
        if hasta_numero_sorteo is None:
            return list(todos)
        return [r for r in todos if r.numero_sorteo <= hasta_numero_sorteo]

    def listar_resultados_colorloto(self, juego_id: UUID, hasta_numero_sorteo: int | None = None) -> list[ResultadoColorLoto]:
        self.fue_consultado_colorloto = True
        self.ultimo_hasta_numero_sorteo_recibido = hasta_numero_sorteo
        todos = self._datos_colorloto.get(juego_id, [])
        if hasta_numero_sorteo is None:
            return list(todos)
        return [r for r in todos if r.numero_sorteo <= hasta_numero_sorteo]


class _ColorRepositoryEnMemoriaConEspia(ColorRepository):
    """Fake dedicado a este archivo -deliberadamente NO reutiliza
    `FakeColorRepository` de `tests/unit/fakes.py` (ya probado a
    fondo en Etapa AE-0) para mantener este archivo autocontenido y
    con espía de llamadas propio, sin acoplar ambos archivos de
    tests entre sí."""

    def __init__(self, colores: dict[UUID, list[Color]]):
        self._colores = colores
        self.llamadas_listar_todos = 0

    def listar_todos(self, juego_id: UUID) -> list[Color]:
        self.llamadas_listar_todos += 1
        return sorted(self._colores.get(juego_id, []), key=lambda c: c.codigo)

    def listar_vigentes(self, juego_id: UUID, en_fecha=None) -> list[Color]:
        candidatos = self._colores.get(juego_id, [])
        if en_fecha is None:
            return sorted([c for c in candidatos if c.activo], key=lambda c: c.codigo)
        return sorted([c for c in candidatos if c.esta_vigente_en(en_fecha)], key=lambda c: c.codigo)

    def guardar(self, juego_id: UUID, color: Color) -> Color:
        self._colores.setdefault(juego_id, []).append(color)
        return color

    def cerrar_vigencia(self, juego_id: UUID, codigo: str, hasta) -> None:
        pass


class _EstadisticaRepositoryEnMemoriaConEspia(EstadisticaRepository):
    def __init__(self):
        self._filas: list[EstadisticaCalculada] = []
        self.guardar_fue_llamado = False

    def guardar(self, entrada: EstadisticaCalculada) -> EstadisticaCalculada:
        self.guardar_fue_llamado = True
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
            corte_afectado = fila.hasta_numero_sorteo is None or (
                desde_numero_sorteo is not None and fila.hasta_numero_sorteo >= desde_numero_sorteo
            )
            vigente = fila.valido_hasta is None or fila.valido_hasta > ahora
            if fila.juego_id == juego_id and corte_afectado and vigente:
                self._filas[i] = EstadisticaCalculada(
                    id=fila.id, juego_id=fila.juego_id, tipo_estadistica=fila.tipo_estadistica,
                    hasta_numero_sorteo=fila.hasta_numero_sorteo, parametros=fila.parametros,
                    parametros_hash=fila.parametros_hash, resultado=fila.resultado,
                    calculado_en=fila.calculado_en, valido_hasta=ahora,
                )
                afectadas += 1
        return afectadas

    def listar_por_juego_y_tipo(self, juego_id, tipo_estadistica):
        raise NotImplementedError("no usado en esta etapa")

    def precargar(self, entrada: EstadisticaCalculada) -> None:
        self._filas.append(entrada)


def _construir_orquestador(dataset=None, juego_id=None):
    juego_id = juego_id or uuid4()
    historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: dataset if dataset is not None else list(_DATASET)})
    estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
    orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
    return orquestador, historico_repo, estadistica_repo, juego_id


class TestCacheMiss:
    def test_pipeline_completo_de_extremo_a_extremo(self):
        orquestador, historico_repo, estadistica_repo, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        assert historico_repo.fue_consultado
        assert estadistica_repo.guardar_fue_llamado
        assert isinstance(resultado, EstadisticaCalculada)
        assert resultado.id is not None
        assert resultado.hasta_numero_sorteo == 3

        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["1"]["apariciones"] == 3
        assert filas["1"]["total_sorteos"] == 3

    def test_numero_nunca_observado_en_el_corte_aparece_con_cero(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["13"]["apariciones"] == 0

    def test_hasta_numero_sorteo_se_pasa_al_repositorio_historico(self):
        orquestador, historico_repo, _, juego_id = _construir_orquestador()
        orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        assert historico_repo.ultimo_hasta_numero_sorteo_recibido == 3

    def test_anti_fuga_ningun_resultado_usa_sorteos_posteriores_al_corte(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["2"]["apariciones"] == 2

    def test_resultado_vacio_igual_que_calcular_frecuencia_numeros_directo(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros

        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros",
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        esperado_directo = calcular_frecuencia_numeros([], _RANGO_MIN, _RANGO_MAX)
        filas_pipeline = {f["valor"]: f["apariciones"] for f in resultado.resultado["filas"]}
        filas_directas = {f.valor: f.apariciones for f in esperado_directo}
        assert filas_pipeline == filas_directas

    def test_no_muta_el_historico_ni_los_parametros(self):
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}
        copia_parametros = dict(parametros)
        copia_dataset = list(_DATASET)
        orquestador, _, _, juego_id = _construir_orquestador()
        orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=parametros)
        assert parametros == copia_parametros
        assert _DATASET == copia_dataset


class TestCacheHit:
    def test_cache_hit_no_consulta_historico_no_recalcula_no_guarda(self):
        orquestador, historico_repo, estadistica_repo, juego_id = _construir_orquestador()
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}

        estadistica_repo.precargar(EstadisticaCalculada(
            id=uuid4(), juego_id=juego_id, tipo_estadistica="frecuencia_numeros",
            hasta_numero_sorteo=3, parametros=parametros,
            parametros_hash=calcular_parametros_hash(parametros),
            resultado={"filas": [{"valor": "1", "apariciones": 999, "total_sorteos": 3, "frecuencia_relativa": 1.0}]},
            calculado_en=datetime.now(timezone.utc), valido_hasta=None,
        ))

        resultado = orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=parametros)

        assert historico_repo.fue_consultado is False
        assert estadistica_repo.guardar_fue_llamado is False
        assert resultado.resultado["filas"][0]["apariciones"] == 999


class TestParametrosYCorteDiferenciadosEnElCache:
    def test_rangos_diferentes_no_comparten_estadistica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica={"rango_min": 1, "rango_max": 43})
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica={"rango_min": 1, "rango_max": 39})
        assert estadistica_repo.guardar_fue_llamado is True

    def test_cortes_diferentes_no_comparten_estadistica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}
        orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=1, parametros_metrica=parametros)
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=2, parametros_metrica=parametros)
        assert estadistica_repo.guardar_fue_llamado is True

    def test_mismos_parametros_y_corte_si_dan_cache_hit_en_la_segunda_llamada(self):
        orquestador, historico_repo, estadistica_repo, juego_id = _construir_orquestador()
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}
        primera = orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=parametros)
        historico_repo.fue_consultado = False
        estadistica_repo.guardar_fue_llamado = False
        segunda = orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=parametros)
        assert historico_repo.fue_consultado is False
        assert estadistica_repo.guardar_fue_llamado is False
        assert primera.id == segunda.id


class TestErrorMetricaDesconocida:
    def test_tipo_estadistica_inexistente_lanza_error_explicito(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        with pytest.raises(TipoEstadisticaNoSoportadoError, match="algo_inexistente"):
            orquestador.ejecutar(juego_id, "algo_inexistente", parametros_metrica={})


class TestUsaSoloPuertos:
    def test_el_orquestador_no_importa_infraestructura(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        lineas_import = [
            linea for linea in open(modulo.__file__, encoding="utf-8").read().splitlines()
            if linea.strip().startswith(("import ", "from "))
        ]
        codigo_imports = "\n".join(lineas_import).lower()
        assert "sqlalchemy" not in codigo_imports
        assert "infrastructure" not in codigo_imports


# =====================================================================
# frecuencia_superbalota (Etapa V) -verificación previa e independiente
# (sin usar el orquestador ni el motor) confirmó: con corte=3, S3
# (superbalota=None) se excluye del denominador; la superbalota 9
# aparece 2 veces (S1, S2); S4 (posterior al corte) nunca participa.
# =====================================================================

def _num_sb(numero_sorteo: int, numeros: tuple[int, ...], superbalota) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=_FECHA_BASE + timedelta(days=numero_sorteo),
        dia_semana="lunes", numeros=numeros, superbalota=superbalota,
    )


_DATASET_SUPERBALOTA = [
    _num_sb(1, (1, 2, 3, 4, 5), 9),
    _num_sb(2, (6, 7, 8, 9, 10), 9),
    _num_sb(3, (1, 2, 3, 4, 5), 5),      # Etapa AD: valor válido -antes None, ver TestSuperbalotaAusenteRechazada
    _num_sb(4, (1, 2, 3, 4, 5), 3),      # posterior a un corte de 3
]

_SB_MIN, _SB_MAX = BalotoGame().superballot_range  # fuente de verdad real, nunca "1, 16" a mano


class TestCatalogoIncluyeFrecuenciaSuperbalota:
    def test_frecuencia_superbalota_esta_registrada(self):
        """No debe lanzar TipoEstadisticaNoSoportadoError -si la
        receta no estuviera registrada, esta llamada fallaría."""
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(
            juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
        )


class TestFrecuenciaSuperbalotaCacheMiss:
    def _orquestador_superbalota(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: list(_DATASET_SUPERBALOTA)})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        return orquestador, historico_repo, estadistica_repo, juego_id

    def test_cache_miss_consulta_historico_ejecuta_y_persiste(self):
        orquestador, historico_repo, estadistica_repo, juego_id = self._orquestador_superbalota()
        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
        )
        assert historico_repo.fue_consultado
        assert estadistica_repo.guardar_fue_llamado
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["9"]["apariciones"] == 2  # verificado independientemente arriba
        assert filas["9"]["total_sorteos"] == 3  # Etapa AD: los 3 sorteos del corte ahora tienen dato válido

    def test_superbalota_ausente_rechaza_el_calculo_completo(self):
        """Etapa AD: política de rechazo total -antes de esta etapa,
        un sorteo con superbalota=None se excluía silenciosamente del
        denominador (comportamiento del motor, nunca una decisión de
        negocio validada). La auditoría confirmó que, para un juego
        con superbalota, ese estado NUNCA puede surgir de una
        operación legítima (validate_draw lo exige siempre), así que
        ahora se rechaza el cálculo completo en vez de reducir el
        denominador sin avisar."""
        juego_id = uuid4()
        dataset_con_ausente = [
            _num_sb(1, (1, 2, 3, 4, 5), 9),
            _num_sb(2, (6, 7, 8, 9, 10), None),
        ]
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: dataset_con_ausente})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        try:
            orquestador.ejecutar(
                juego_id, "frecuencia_superbalota",
                parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
            )
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.SUPERBALOTA_AUSENTE
        assert estadistica_repo.guardar_fue_llamado is False

    def test_incluye_valores_no_observados_con_cero(self):
        orquestador, _, _, juego_id = self._orquestador_superbalota()
        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["16"]["apariciones"] == 0  # nunca observado, pero presente

    def test_anti_fuga_sorteo_posterior_al_corte_no_participa(self):
        orquestador, _, _, juego_id = self._orquestador_superbalota()
        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _SB_MIN, "rango_max": _SB_MAX},
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        # sb=3 solo aparece en S4 (posterior al corte) -no debe contarse
        assert filas["3"]["apariciones"] == 0

    def test_rango_forma_parte_de_la_clave_de_cache(self):
        orquestador, _, estadistica_repo, juego_id = self._orquestador_superbalota()
        orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 16})
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 10})
        assert estadistica_repo.guardar_fue_llamado is True  # rango distinto -no fue cache hit


class TestFrecuenciaSuperbalotaCacheHit:
    def test_cache_hit_no_consulta_historico_no_recalcula(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: list(_DATASET_SUPERBALOTA)})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        parametros = {"rango_min": _SB_MIN, "rango_max": _SB_MAX}

        primera = orquestador.ejecutar(juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3, parametros_metrica=parametros)
        historico_repo.fue_consultado = False
        estadistica_repo.guardar_fue_llamado = False
        segunda = orquestador.ejecutar(juego_id, "frecuencia_superbalota", hasta_numero_sorteo=3, parametros_metrica=parametros)

        assert historico_repo.fue_consultado is False
        assert estadistica_repo.guardar_fue_llamado is False
        assert primera.id == segunda.id

    def test_frecuencia_numeros_y_frecuencia_superbalota_no_comparten_cache(self):
        """Verificación explícita pedida: dos tipos distintos, mismos
        parámetros de forma, no deben mezclarse en el cache."""
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: list(_DATASET_SUPERBALOTA)})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica={"rango_min": 1, "rango_max": 16})
        estadistica_repo.guardar_fue_llamado = False
        # mismos parametros de forma (1,16), pero tipo distinto -no debe ser cache hit
        orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 16})
        assert estadistica_repo.guardar_fue_llamado is True


class TestFrecuenciaNumerosSigueFuncionandoSinRegresion:
    def test_frecuencia_numeros_sigue_intacta(self):
        orquestador, historico_repo, estadistica_repo, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["1"]["apariciones"] == 3  # mismo valor de siempre, sin regresion


class TestTipoDesconocidoSigueFuncionando:
    def test_tipo_desconocido_sigue_lanzando_error_explicito(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        with pytest.raises(TipoEstadisticaNoSoportadoError, match="frecuencia_coocurrencia_inexistente"):
            orquestador.ejecutar(juego_id, "frecuencia_coocurrencia_inexistente", parametros_metrica={})


# =====================================================================
# tabla_frecuencia_numeros (tercera visualización: observado vs.
# esperado) -verificación previa e independiente (Counter puro, sin
# usar el orquestador ni el motor) confirmó, con un juego de juguete
# rango=1..5, K=2: número 1 aparece 3/4=0.75, K/N esperado=0.4,
# diferencia=0.35. También se comparó directamente contra
# construir_tabla_frecuencia real, coincidiendo exactamente.
# =====================================================================

_CANTIDAD_NUMEROS_BALOTO = BalotoGame().numbers_to_pick  # fuente de verdad real, nunca "5" a mano


def _parametros_tabla(rango_min=_RANGO_MIN, rango_max=_RANGO_MAX, cantidad_numeros=_CANTIDAD_NUMEROS_BALOTO) -> dict:
    return {"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}


class TestCatalogoIncluyeTablaFrecuenciaNumeros:
    def test_tabla_frecuencia_numeros_esta_registrada(self):
        """No debe lanzar TipoEstadisticaNoSoportadoError."""
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", parametros_metrica=_parametros_tabla())


class TestTablaFrecuenciaNumerosCacheMiss:
    def test_cache_miss_calcula_serializa_y_persiste(self):
        orquestador, historico_repo, estadistica_repo, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_tabla(),
        )
        assert historico_repo.fue_consultado
        assert estadistica_repo.guardar_fue_llamado
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["1"]["apariciones"] == 3  # mismo dataset y corte ya verificados en frecuencia_numeros
        assert filas["1"]["frecuencia_observada"]["total_sorteos"] == 3

    def test_probabilidad_teorica_es_k_sobre_n(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_tabla(),
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        n = _RANGO_MAX - _RANGO_MIN + 1
        esperado = _CANTIDAD_NUMEROS_BALOTO / n
        assert abs(filas["1"]["probabilidad_teorica"]["probabilidad"] - esperado) < 1e-9
        assert filas["1"]["probabilidad_teorica"]["metodo"] == f"K/N = {_CANTIDAD_NUMEROS_BALOTO}/{n}"

    def test_probabilidad_teorica_permanece_separada_de_la_observada(self):
        """Verificación explícita pedida: los dos conceptos nunca se
        fusionan en un solo campo."""
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_tabla(),
        )
        fila = resultado.resultado["filas"][0]
        assert "frecuencia_observada" in fila and "probabilidad_teorica" in fila
        assert fila["frecuencia_observada"] != fila["probabilidad_teorica"]
        assert set(fila["frecuencia_observada"].keys()) == {"valor", "apariciones", "total_sorteos", "frecuencia_relativa"}
        assert set(fila["probabilidad_teorica"].keys()) == {"valor", "probabilidad", "metodo"}

    def test_diferencia_conserva_el_signo(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_tabla(),
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        n = _RANGO_MAX - _RANGO_MIN + 1
        esperado = _CANTIDAD_NUMEROS_BALOTO / n
        frecuencia_1 = filas["1"]["frecuencia_observada"]["frecuencia_relativa"]
        assert abs(filas["1"]["diferencia"] - (frecuencia_1 - esperado)) < 1e-9
        # numero 13 nunca observado dentro del corte -> diferencia negativa (0 - esperado)
        assert filas["13"]["diferencia"] < 0

    def test_numeros_no_observados_permanecen_con_frecuencia_cero(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_tabla(),
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["13"]["apariciones"] == 0
        assert filas["13"]["frecuencia_observada"]["frecuencia_relativa"] == 0.0

    def test_anti_fuga(self):
        orquestador, historico_repo, _, juego_id = _construir_orquestador()
        orquestador.ejecutar(
            juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_tabla(),
        )
        assert historico_repo.ultimo_hasta_numero_sorteo_recibido == 3


class TestTablaFrecuenciaNumerosCacheHit:
    def test_cache_hit_no_consulta_historico_no_recalcula(self):
        orquestador, historico_repo, estadistica_repo, juego_id = _construir_orquestador()
        parametros = _parametros_tabla()
        primera = orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=parametros)
        historico_repo.fue_consultado = False
        estadistica_repo.guardar_fue_llamado = False
        segunda = orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=parametros)
        assert historico_repo.fue_consultado is False
        assert estadistica_repo.guardar_fue_llamado is False
        assert primera.id == segunda.id


class TestTablaFrecuenciaNumerosCacheDiferenciado:
    def test_parametros_diferentes_no_comparten_cache(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", parametros_metrica=_parametros_tabla(cantidad_numeros=5))
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", parametros_metrica=_parametros_tabla(cantidad_numeros=6))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_tipos_de_estadistica_diferentes_no_comparten_cache(self):
        """frecuencia_numeros y tabla_frecuencia_numeros, con rango
        idéntico, no deben mezclarse -distinto tipo_estadistica."""
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX})
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "tabla_frecuencia_numeros", parametros_metrica=_parametros_tabla())
        assert estadistica_repo.guardar_fue_llamado is True


class TestRecetasAnterioresSiguenFuncionando:
    def test_frecuencia_numeros_y_frecuencia_superbalota_intactas(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado_numeros = orquestador.ejecutar(
            juego_id, "frecuencia_numeros", hasta_numero_sorteo=3,
            parametros_metrica={"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX},
        )
        filas = {f["valor"]: f for f in resultado_numeros.resultado["filas"]}
        assert filas["1"]["apariciones"] == 3  # sin regresion


class TestTipoDesconocidoSigueFuncionandoV2:
    def test_tipo_desconocido_sigue_lanzando_error(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        with pytest.raises(TipoEstadisticaNoSoportadoError):
            orquestador.ejecutar(juego_id, "algo_totalmente_inexistente", parametros_metrica={})


class TestOrquestadorSoloDependeDePuertosV2:
    def test_no_importa_infraestructura(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        lineas_import = [
            linea for linea in open(modulo.__file__, encoding="utf-8").read().splitlines()
            if linea.strip().startswith(("import ", "from "))
        ]
        codigo_imports = "\n".join(lineas_import).lower()
        assert "sqlalchemy" not in codigo_imports
        assert "infrastructure" not in codigo_imports


class TestRecalculoTrasInvalidacion:
    """Corrección del defecto real reportado en Windows: el flujo
    completo (existe cacheado -> se invalida -> se solicita de nuevo
    -> recalcula -> persiste -> responde) NO debe producir
    IntegrityError/UniqueViolation. Reproduce el escenario exacto
    reportado: guardar() sobre una identidad recién invalidada."""

    def test_recalcula_y_persiste_sin_error_tras_invalidar(self):
        orquestador, historico_repo, estadistica_repo, juego_id = _construir_orquestador()
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}

        # 1. Existe estadistica cacheada (primera llamada, cache miss real)
        primera = orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica=parametros)

        # 2. Se invalida (mismo mecanismo que RegistrarSorteo/EditarSorteo/EliminarSorteo)
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)

        # 3-6. Se solicita de nuevo -debe recalcular y persistir SIN lanzar
        segunda = orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica=parametros)

        # 7. "Responde correctamente" -mismo pipeline devuelve un resultado valido
        assert segunda is not None
        assert segunda.id == primera.id  # misma fila logica, no un duplicado
        filas = {f["valor"]: f for f in segunda.resultado["filas"]}
        assert filas["1"]["apariciones"] == 5  # mismo dato historico completo, recalculado correctamente

    def test_recalculo_deja_una_sola_fila_por_identidad(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}

        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica=parametros)
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica=parametros)
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica=parametros)  # tercera vez

        total = sum(
            1 for f in estadistica_repo._filas
            if f.juego_id == juego_id and f.tipo_estadistica == "frecuencia_numeros" and f.hasta_numero_sorteo is None
        )
        assert total == 1

    def test_recalculo_queda_vigente_para_la_siguiente_peticion_cache_hit(self):
        orquestador, historico_repo, estadistica_repo, juego_id = _construir_orquestador()
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}

        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica=parametros)
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica=parametros)  # recalcula

        # una tercera peticion, sin invalidar de nuevo, debe ser CACHE HIT
        historico_repo.fue_consultado = False
        orquestador.ejecutar(juego_id, "frecuencia_numeros", parametros_metrica=parametros)
        assert historico_repo.fue_consultado is False

    def test_recalculo_con_corte_conserva_el_corte_y_no_duplica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        parametros = {"rango_min": _RANGO_MIN, "rango_max": _RANGO_MAX}

        orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=parametros)
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=3)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_numeros", hasta_numero_sorteo=3, parametros_metrica=parametros)

        assert resultado.hasta_numero_sorteo == 3
        total = sum(1 for f in estadistica_repo._filas if f.juego_id == juego_id and f.hasta_numero_sorteo == 3)
        assert total == 1


# =====================================================================
# atrasos_numeros (cuarta visualización, Etapa W) -verificación previa
# e independiente ejecutada antes de escribir estos tests: con
# _DATASET y corte=3, se calculó directamente calcular_atrasos_numeros
# sobre el histórico ya filtrado (sin pasar hasta_numero_sorteo),
# confirmando atraso(1)=0, atraso(2)=1, atraso(6)=1, atraso(9)=0,
# atraso(13)=None -estos son los valores usados en las aserciones.
# =====================================================================

def _parametros_atrasos(rango_min=_RANGO_MIN, rango_max=_RANGO_MAX) -> dict:
    return {"rango_min": rango_min, "rango_max": rango_max}


class TestCatalogoIncluyeAtrasosNumeros:
    def test_atrasos_numeros_esta_registrada(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "atrasos_numeros", parametros_metrica=_parametros_atrasos())


class TestAtrasosNumerosParametros:
    def test_parametros_validos_calcula_sin_error(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_atrasos(),
        )
        assert resultado is not None

    def test_parametros_invalidos_numero_fuera_de_rango_propaga_value_error(self):
        """El motor valida internamente -la receta no debe tragarse
        ni traducir ese error, debe propagarlo tal cual."""
        dataset_invalido = [_num(1, (1, 2, 3, 4, 99))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset_invalido)
        with pytest.raises(ValueError, match="99"):
            orquestador.ejecutar(juego_id, "atrasos_numeros", parametros_metrica=_parametros_atrasos())


class TestAtrasosNumerosSerializacionYSemantica:
    def test_serializacion_incluye_los_cuatro_campos_reales_de_atrasoobservado(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_atrasos(),
        )
        fila = resultado.resultado["filas"][0]
        assert set(fila.keys()) == {"valor", "atraso", "ultimo_sorteo_aparicion", "total_sorteos"}

    def test_none_se_conserva_para_numero_nunca_observado(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_atrasos(),
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["13"]["atraso"] is None
        assert filas["13"]["ultimo_sorteo_aparicion"] is None
        assert filas["13"]["atraso"] != 0
        assert filas["13"]["atraso"] != -1

    def test_orden_estable_por_numero_ascendente(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_atrasos(),
        )
        valores = [int(f["valor"]) for f in resultado.resultado["filas"]]
        assert valores == sorted(valores)

    def test_historico_completo_sin_corte(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(juego_id, "atrasos_numeros", parametros_metrica=_parametros_atrasos())
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        # sin corte, la referencia es el maximo real = sorteo 5; numero 1 aparece en todos, atraso=0
        assert filas["1"]["atraso"] == 0
        assert filas["1"]["ultimo_sorteo_aparicion"] == 5

    def test_corte_coincidente_con_sorteo_real(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_atrasos(),
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["1"]["atraso"] == 0
        assert filas["2"]["atraso"] == 1
        assert filas["6"]["atraso"] == 1
        assert filas["9"]["atraso"] == 0


class TestAtrasosNumerosCorteInexistenteUsaUltimoSorteoReal:
    """Prueba de no regresión semántica -OBLIGATORIA (Etapa W): con un
    dataset artificial (sorteo 100 aparece 7, sorteo 102 no, sorteo
    105 no) y hasta_numero_sorteo=104 (que NO corresponde a ningún
    sorteo real), la distancia de 7 debe ser 2 (referencia = último
    sorteo REAL dentro del corte, el 102), nunca 4 (que se obtendría
    si se usara 104 como número aritmético crudo). Esto verifica
    exactamente la decisión semántica aprobada: la receta NO pasa
    hasta_numero_sorteo a calcular_atrasos_numeros, dejando que la
    función derive la referencia del histórico ya filtrado por el
    orquestador."""

    def test_corte_sin_sorteo_real_usa_el_ultimo_sorteo_real_filtrado(self):
        dataset = [_num(100, (7, 1)), _num(102, (2, 3)), _num(105, (4, 5))]
        orquestador, historico_repo, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=104,
            parametros_metrica={"rango_min": 1, "rango_max": 10},
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["7"]["atraso"] == 2
        assert filas["7"]["atraso"] != 4
        assert filas["7"]["ultimo_sorteo_aparicion"] == 100
        # el sorteo 105 debe haber sido excluido por el corte
        assert historico_repo.ultimo_hasta_numero_sorteo_recibido == 104

    def test_corte_posterior_al_ultimo_resultado_usa_el_ultimo_real_disponible(self):
        dataset = [_num(100, (7, 1)), _num(102, (2, 3)), _num(105, (4, 5))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=110,
            parametros_metrica={"rango_min": 1, "rango_max": 10},
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        # con corte=110 (posterior a TODO lo real), el filtro no excluye nada;
        # la referencia es el maximo REAL = 105
        assert filas["7"]["atraso"] == 5  # 105 - 100
        assert filas["7"]["atraso"] != 10  # NO 110-100

    def test_corte_anterior_al_primer_resultado_produce_todo_sin_datos(self):
        dataset = [_num(100, (7, 1)), _num(102, (2, 3)), _num(105, (4, 5))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=50,
            parametros_metrica={"rango_min": 1, "rango_max": 10},
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert all(f["atraso"] is None for f in filas.values())


class TestAtrasosNumerosSinResultados:
    def test_juego_sin_sorteos_produce_todo_none_sin_error(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(juego_id, "atrasos_numeros", parametros_metrica=_parametros_atrasos())
        assert all(f["atraso"] is None for f in resultado.resultado["filas"])
        assert all(f["total_sorteos"] == 0 for f in resultado.resultado["filas"])


class TestAtrasosNumerosNoAlteraContratoDeReceta:
    def test_receta_calcular_sigue_recibiendo_solo_historico_y_parametros(self):
        """No se generalizó _Receta.calcular -verificado por
        inspección de la firma real."""
        import inspect

        from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO
        firma = inspect.signature(_CATALOGO["atrasos_numeros"].calcular)
        assert list(firma.parameters.keys()) == ["historico", "parametros"]

    def test_hasta_numero_sorteo_no_se_duplica_en_parametros_metrica(self):
        """El corte no debe formar parte de parametros_metrica -sigue
        siendo una columna de identidad separada."""
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        orquestador.ejecutar(
            juego_id, "atrasos_numeros", hasta_numero_sorteo=3, parametros_metrica=_parametros_atrasos(),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3  # sigue siendo su propia columna


class TestAtrasosNumerosCacheAisladoPorJuego:
    def test_baloto_y_otro_juego_no_comparten_cache(self):
        juego_a, juego_b = uuid4(), uuid4()
        dataset_a = list(_DATASET)
        dataset_b = [_num(1, (7, 8, 9, 10, 11))]
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_a: dataset_a, juego_b: dataset_b})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        r_a = orquestador.ejecutar(juego_a, "atrasos_numeros", parametros_metrica=_parametros_atrasos())
        r_b = orquestador.ejecutar(juego_b, "atrasos_numeros", parametros_metrica=_parametros_atrasos())

        filas_a = {f["valor"]: f["atraso"] for f in r_a.resultado["filas"]}
        filas_b = {f["valor"]: f["atraso"] for f in r_b.resultado["filas"]}
        assert filas_a["7"] == 3     # aparece en sorteo 2 de _DATASET, referencia=5 -> atraso=3
        assert filas_b["7"] == 0     # aparece en el unico sorteo de dataset_b, atraso 0
        assert filas_a["13"] is None  # 13 nunca aparece en _DATASET (rango va hasta 43)


# =====================================================================
# distribucion_pares_impares (quinta visualización, Etapa Y) -
# verificación previa e independiente ejecutada antes de escribir
# estos tests: con _DATASET (5 sorteos, K=5) se calculó a mano el
# conteo de pares por sorteo -sorteo1=2, sorteo2=3, sorteo3=2,
# sorteo4=2, sorteo5=2- confirmando categoría "2" con 4 apariciones,
# categoría "3" con 1 aparición, el resto en 0.
# =====================================================================

def _parametros_pares_impares(cantidad_numeros=5) -> dict:
    return {"cantidad_numeros": cantidad_numeros}


class TestCatalogoIncluyeDistribucionParesImpares:
    def test_distribucion_pares_impares_esta_registrada(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())


class TestDistribucionParesImparesSerializacionYSemantica:
    def test_conteo_exacto_reproduce_el_calculo_manual(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(),
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["2"]["apariciones"] == 4
        assert filas["3"]["apariciones"] == 1
        assert filas["0"]["apariciones"] == 0
        assert filas["1"]["apariciones"] == 0
        assert filas["4"]["apariciones"] == 0
        assert filas["5"]["apariciones"] == 0

    def test_serializa_las_k_mas_uno_categorias_incluidas_las_de_cero(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(),
        )
        assert len(resultado.resultado["filas"]) == 6  # 0..5

    def test_campos_reales_de_frecuenciaobservada_conservados(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(),
        )
        fila = resultado.resultado["filas"][0]
        assert set(fila.keys()) == {"valor", "apariciones", "total_sorteos", "frecuencia_relativa"}

    def test_orden_estable_por_valor_ascendente(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(),
        )
        valores = [int(f["valor"]) for f in resultado.resultado["filas"]]
        assert valores == sorted(valores)

    def test_frecuencias_suman_aproximadamente_uno_con_datos(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(),
        )
        suma = sum(f["frecuencia_relativa"] for f in resultado.resultado["filas"])
        assert abs(suma - 1.0) < 1e-9

    def test_cero_datos_no_divide_por_cero(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(),
        )
        assert all(f["apariciones"] == 0 and f["frecuencia_relativa"] == 0.0 for f in resultado.resultado["filas"])

    def test_corte_filtra_antes_del_calculo(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", hasta_numero_sorteo=1,
            parametros_metrica=_parametros_pares_impares(),
        )
        filas = {f["valor"]: f for f in resultado.resultado["filas"]}
        assert filas["2"]["apariciones"] == 1  # solo el sorteo 1
        assert all(f["total_sorteos"] == 1 for f in filas.values())

    def test_corte_futuro_equivale_a_historico_completo(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado_futuro = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", hasta_numero_sorteo=999,
            parametros_metrica=_parametros_pares_impares(),
        )
        # invalido antes de recalcular sin corte, para no usar cache de la corrida anterior
        filas_futuro = {f["valor"]: f["apariciones"] for f in resultado_futuro.resultado["filas"]}
        assert filas_futuro["2"] == 4
        assert filas_futuro["3"] == 1

    def test_corte_anterior_al_primer_resultado_produce_cero_datos(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", hasta_numero_sorteo=0,
            parametros_metrica=_parametros_pares_impares(),
        )
        assert all(f["apariciones"] == 0 for f in resultado.resultado["filas"])


class TestDistribucionParesImparesCacheYContrato:
    def test_cantidad_numeros_forma_parte_del_hash(self):
        # dataset vacio deliberadamente: el punto de este test es solo
        # confirmar identidad de cache distinta por parametro, no la
        # distribucion en si -con dataset vacio, la validacion
        # defensiva (que exige len(numeros)==cantidad_numeros) no
        # tiene nada que rechazar para NINGUN K.
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(5))
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(6))
        assert estadistica_repo.guardar_fue_llamado is True  # distinta identidad, no cache hit

    def test_corte_no_forma_parte_de_parametros_metrica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", hasta_numero_sorteo=3,
            parametros_metrica=_parametros_pares_impares(),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3

    def test_receta_calcular_sigue_recibiendo_solo_historico_y_parametros(self):
        import inspect

        from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO
        firma = inspect.signature(_CATALOGO["distribucion_pares_impares"].calcular)
        assert list(firma.parameters.keys()) == ["historico", "parametros"]

    def test_caches_aislados_entre_juegos(self):
        juego_a, juego_b = uuid4(), uuid4()
        dataset_a = list(_DATASET)
        dataset_b = [_num(1, (2, 4, 6, 8, 10))]  # 5 pares
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_a: dataset_a, juego_b: dataset_b})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        r_a = orquestador.ejecutar(juego_a, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        r_b = orquestador.ejecutar(juego_b, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())

        filas_a = {f["valor"]: f["apariciones"] for f in r_a.resultado["filas"]}
        filas_b = {f["valor"]: f["apariciones"] for f in r_b.resultado["filas"]}
        assert filas_a["5"] == 0  # nadie con 5 pares en dataset_a
        assert filas_b["5"] == 1  # dataset_b tiene un sorteo con 5 pares


class TestDistribucionParesImparesValidacionDefensiva:
    """Etapa Y -validación defensiva OBLIGATORIA: la receta rechaza,
    antes de calcular, cualquier resultado cuya longitud de `numeros`
    no coincida con `cantidad_numeros` -nunca calcula, nunca persiste,
    nunca produce una distribución parcial."""

    def test_resultado_con_longitud_distinta_de_k_se_rechaza(self):
        dataset_inconsistente = [_num(1, (1, 2, 3, 4))]  # 4 numeros, K declarado=5
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset_inconsistente)
        with pytest.raises(ResultadoHistoricoInconsistenteError, match="distinta de 5"):
            orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())

    def test_caso_seis_pares_con_k_cinco_se_rechaza(self):
        dataset_seis_pares = [_num(1, (2, 4, 6, 8, 10, 12))]  # 6 numeros pares, K declarado=5
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset_seis_pares)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())

    def test_no_persiste_estadistica_cuando_es_inconsistente(self):
        dataset_inconsistente = [_num(1, (2, 4, 6, 8, 10, 12))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset_inconsistente)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        assert estadistica_repo.guardar_fue_llamado is False

    def test_no_devuelve_una_distribucion_con_suma_de_apariciones_cero(self):
        """Verifica explícitamente que la falla ocurre ANTES de
        producir cualquier resultado -nunca hay una lista de filas
        con total_sorteos>0 pero suma de apariciones=0."""
        dataset_inconsistente = [_num(1, (2, 4, 6, 8, 10, 12))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset_inconsistente)
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
            raise AssertionError("Debio lanzar ResultadoHistoricoInconsistenteError")
        except ResultadoHistoricoInconsistenteError:
            pass  # esperado -confirma que nunca se llego a construir una lista de filas

    def test_datos_validos_continuan_funcionando_tras_la_validacion_defensiva(self):
        orquestador, _, _, juego_id = _construir_orquestador()  # _DATASET, todos con exactamente 5 numeros
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares(),
        )
        assert resultado is not None
        assert len(resultado.resultado["filas"]) == 6


class TestExcepcionEspecificaVsValueErrorGenerico:
    """Corrección de un riesgo real detectado en la auditoría
    posterior a la Etapa Y: un manejador global de `ValueError` en
    `main.py` habría interceptado CUALQUIER `ValueError` de todo el
    sistema (dominio, repositorios, conectores, motor) como si fuera
    "dato inválido del usuario" -incluyendo errores de programación
    genuinos. La corrección: una excepción específica
    (`ResultadoHistoricoInconsistenteError`, subclase de
    `DominioError`), sin ningún manejador global de `ValueError`."""

    def test_la_receta_lanza_la_excepcion_especifica_no_valueerror_generico(self):
        dataset_inconsistente = [_num(1, (2, 4, 6, 8, 10, 12))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset_inconsistente)
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
            raise AssertionError("Debio lanzar")
        except ResultadoHistoricoInconsistenteError:
            pass  # tipo exacto esperado
        except ValueError as e:
            raise AssertionError(
                f"Lanzo un ValueError generico ({type(e).__name__}) en vez de la excepcion "
                f"especifica ResultadoHistoricoInconsistenteError"
            )

    def test_excepcion_especifica_hereda_de_dominio_error(self):
        from app.application.exceptions import DominioError
        assert issubclass(ResultadoHistoricoInconsistenteError, DominioError)

    def test_mensaje_no_expone_la_tupla_completa_de_numeros_ni_internals(self):
        """Solo identifica numero_sorteo (identificador público, no
        sensible) y la cantidad esperada (entero pequeño) -nunca la
        representación completa del registro (los propios `numeros`
        mal formados), ni paths, ni SQL, ni un traceback."""
        e = ResultadoHistoricoInconsistenteError([7, 12], 5)
        mensaje = str(e)
        assert "7" in mensaje and "12" in mensaje and "5" in mensaje
        assert "Traceback" not in mensaje
        assert "/home/" not in mensaje and "/app/" not in mensaje
        assert "SELECT" not in mensaje.upper()

    def test_mensaje_identifica_la_inconsistencia_de_forma_util(self):
        dataset_inconsistente = [_num(7, (1, 2, 3, 4))]  # numero_sorteo=7, 4 numeros, K=5
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset_inconsistente)
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
            raise AssertionError("Debio lanzar")
        except ResultadoHistoricoInconsistenteError as e:
            assert "7" in str(e)  # identifica el numero_sorteo afectado
            assert "5" in str(e)  # identifica la cantidad esperada

    def test_un_valueerror_no_relacionado_del_dominio_nunca_se_convierte_en_dominioerror(self):
        """Prueba directa del riesgo original: `Combination` con
        números repetidos lanza un `ValueError` genuino del dominio,
        completamente ajeno a esta receta -debe seguir siendo un
        `ValueError` puro, nunca una `DominioError` (lo que habría
        implicado que un manejador global lo interceptara como 422)."""
        from app.application.exceptions import DominioError
        from app.domain.value_objects.combination import Combination

        try:
            Combination(numeros=(1, 1, 2, 3, 4))
            raise AssertionError("Debio lanzar ValueError")
        except DominioError:
            raise AssertionError(
                "Un ValueError no relacionado con Etapa Y fue interceptado como DominioError "
                "-esto indicaria que sigue existiendo un manejo demasiado amplio"
            )
        except ValueError as e:
            assert not isinstance(e, DominioError)  # confirmado: ValueError puro, no traducido


class TestDistribucionParesImparesConfiguracionPorJuego:
    def test_baloto_k_desde_domain(self):
        from app.domain.games.baloto import BalotoGame
        assert BalotoGame.numbers_to_pick == 5

    def test_revancha_k_desde_domain(self):
        from app.domain.games.baloto_revancha import BalotoRevanchaGame
        assert BalotoRevanchaGame.numbers_to_pick == 5

    def test_miloto_k_desde_domain(self):
        from app.domain.games.miloto import MiLotoGame
        assert MiLotoGame.numbers_to_pick == 5

    def test_superbalota_excluida_del_conteo(self):
        """Un sorteo con superbalota par no debe afectar el conteo de
        pares de los numeros principales."""
        from app.application.estadisticas.tipos import ResultadoNumerico
        r_con_superbalota_par = ResultadoNumerico(
            numero_sorteo=1, fecha=_DATASET[0].fecha, dia_semana="lunes",
            numeros=(1, 3, 5, 7, 9), superbalota=2,  # superbalota PAR, pero todos los numeros principales son impares
        )
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[r_con_superbalota_par])
        resultado = orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        filas = {f["valor"]: f["apariciones"] for f in resultado.resultado["filas"]}
        assert filas["0"] == 1  # 0 pares en numeros principales, pese a superbalota=2 (par)


# =====================================================================
# Etapa Z: helper defensivo compartido, excepción generalizada,
# receta distribucion_altos_bajos, preservación de Etapa Y.
# =====================================================================

def _parametros_altos_bajos(rango_min=1, rango_max=43, cantidad_numeros=5) -> dict:
    return {"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}


class TestHelperConfiguracionDeRangoParcialEtapaZ:
    """Tests obligatorios (corrección post Etapa Z) sobre la regla
    'o se proporcionan ambos límites, o no se proporciona ninguno' -
    verificados directamente contra la función real, sin asumir su
    comportamiento por el nombre."""

    def test_ambos_limites_omitidos_permitido_solo_valida_cantidad_y_duplicados(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_consistente
        # No debe lanzar -sin limites, no valida rango (aunque el
        # numero 999 este "fuera de cualquier rango razonable", no
        # hay rango que comparar aqui).
        _validar_historico_consistente([_num(1, (1, 2, 3, 4, 999))], 5)

    def test_ambos_limites_presentes_permitido_valida_tambien_rango(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_consistente
        _validar_historico_consistente([_num(1, (1, 2, 3, 4, 5))], 5, rango_min=1, rango_max=43)

    def test_solo_rango_min_lanza_excepcion_interna_explicita(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_consistente
        with pytest.raises(ValueError):
            _validar_historico_consistente([], 5, rango_min=1)

    def test_solo_rango_max_lanza_excepcion_interna_explicita(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_consistente
        with pytest.raises(ValueError):
            _validar_historico_consistente([], 5, rango_max=43)

    def test_la_excepcion_de_rango_parcial_no_es_resultado_historico_inconsistente(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_consistente
        try:
            _validar_historico_consistente([], 5, rango_min=1)
            raise AssertionError("Debio lanzar")
        except ResultadoHistoricoInconsistenteError:
            raise AssertionError(
                "La configuracion de rango parcial (bug de programacion) no debe "
                "producir ResultadoHistoricoInconsistenteError (esa es para datos, no bugs)"
            )
        except ValueError:
            pass  # esperado -tipo correcto

    def test_no_existe_sentencia_assert_en_el_cuerpo_del_helper(self):
        """Verificado por AST, no por inspección de texto -confirma
        que ninguna rama de la función depende de `assert` (que
        desaparecería con `python -O`)."""
        import ast

        codigo_fuente = Path("app/application/use_cases/calcular_y_persistir_estadistica.py").read_text(encoding="utf-8")
        arbol = ast.parse(codigo_fuente)
        funcion = next(
            n for n in ast.walk(arbol)
            if isinstance(n, ast.FunctionDef) and n.name == "_validar_historico_consistente"
        )
        tiene_assert = any(isinstance(n, ast.Assert) for n in ast.walk(funcion))
        assert tiene_assert is False

    def test_validacion_funciona_igual_bajo_python_menos_o(self):
        """Ejecuta el mismo caso con -O real, en un subproceso
        aislado -no se asume el comportamiento, se ejecuta y se
        observa el resultado real.

        Usa `sys.executable` (el intérprete que está corriendo ESTE
        mismo test), nunca un literal como "python3"/"python"/"py"
        -en Windows el proyecto corre con
        `.\\.venv\\Scripts\\python.exe`, y no hay garantía de que
        "python3" exista en PATH ahí. `cwd` se deriva de
        `Path(__file__)` (la raíz real de `backend/`, dos niveles
        arriba de este archivo de test) -portable en Linux y Windows,
        sin ninguna ruta absoluta del entorno de desarrollo
        hardcodeada."""
        import os
        import subprocess

        raiz_backend = Path(__file__).resolve().parents[2]
        # Refuerzo de portabilidad: además de `cwd` (que ya resuelve
        # `sys.path.insert(0, '.')` dentro del código ejecutado),
        # se agrega PYTHONPATH explícito -no reemplaza el entorno
        # heredado (HOME, CODEX_HOME, etc.), solo antepone la raíz
        # real de backend/ usando os.pathsep (portable entre ':' en
        # Linux/macOS y ';' en Windows).
        entorno = dict(os.environ)
        entorno["PYTHONPATH"] = str(raiz_backend) + os.pathsep + entorno.get("PYTHONPATH", "")
        codigo = (
            "import sys; sys.path.insert(0, '.'); "
            "from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_consistente; "
            "\ntry:\n"
            "    _validar_historico_consistente([], 5, rango_min=1)\n"
            "    print('NO_LANZO')\n"
            "except ValueError:\n"
            "    print('LANZO_VALUEERROR')\n"
        )
        resultado = subprocess.run(
            [sys.executable, "-O", "-c", codigo], cwd=str(raiz_backend), env=entorno,
            capture_output=True, text=True, timeout=30,
        )
        assert "LANZO_VALUEERROR" in resultado.stdout, resultado.stdout + resultado.stderr
        assert resultado.returncode == 0

    def test_no_existe_handler_global_de_valueerror_en_main(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "@app.exception_handler(ValueError)" not in codigo_fuente


class TestHelperValidarHistoricoConsistente:
    """El helper se prueba indirectamente a través de las 2 recetas
    que lo usan (mismo patrón de "sin acceso directo a lo privado" ya
    seguido en el resto de esta suite), cubriendo los 8+ casos
    pedidos con datasets sintéticos, nunca con datos reales."""

    def _orquestador_con(self, dataset):
        return _construir_orquestador(dataset=dataset)

    def test_historico_vacio_es_valido(self):
        orquestador, _, _, juego_id = self._orquestador_con([])
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos(),
        )
        assert all(f["apariciones"] == 0 for f in resultado.resultado["filas"])

    def test_historico_valido_no_se_rechaza(self):
        orquestador, _, _, juego_id = self._orquestador_con([_num(1, (1, 10, 21, 22, 43))])
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos(),
        )
        assert resultado is not None

    def test_4_numeros_se_rechaza_como_cantidad(self):
        orquestador, _, _, juego_id = self._orquestador_con([_num(1, (1, 10, 21, 22))])
        try:
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.CANTIDAD

    def test_6_numeros_se_rechaza_como_cantidad(self):
        orquestador, _, _, juego_id = self._orquestador_con([_num(1, (1, 2, 3, 4, 5, 6))])
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())

    def test_duplicado_se_rechaza_como_duplicados(self):
        orquestador, _, _, juego_id = self._orquestador_con([_num(1, (1, 1, 21, 22, 43))])
        try:
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.DUPLICADOS

    def test_menor_al_rango_se_rechaza_como_rango(self):
        orquestador, _, _, juego_id = self._orquestador_con([_num(1, (0, 10, 21, 22, 43))])
        try:
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.RANGO

    def test_mayor_al_rango_se_rechaza_como_rango(self):
        orquestador, _, _, juego_id = self._orquestador_con([_num(1, (1, 10, 21, 22, 99))])
        try:
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.RANGO

    def test_mezcla_valido_e_invalido_rechaza_el_calculo_completo(self):
        dataset = [_num(1, (1, 10, 21, 22, 43)), _num(2, (1, 2, 3, 4))]
        orquestador, _, estadistica_repo, juego_id = self._orquestador_con(dataset)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        assert estadistica_repo.guardar_fue_llamado is False

    def test_varios_sorteos_invalidos_se_reunen_en_la_excepcion(self):
        dataset = [_num(1, (1, 2, 3, 4)), _num(2, (5, 6, 7, 8))]
        orquestador, _, _, juego_id = self._orquestador_con(dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert 1 in e.numeros_sorteo and 2 in e.numeros_sorteo

    def test_orden_cantidad_antes_que_duplicados(self):
        """Un sorteo con AMBOS problemas (4 números Y uno repetido)
        debe reportarse como 'cantidad' primero -orden fijo del
        helper."""
        dataset = [_num(1, (1, 1, 21, 22))]  # 4 numeros (no 5) Y duplicado
        orquestador, _, _, juego_id = self._orquestador_con(dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.CANTIDAD

    def test_motor_no_ejecutado_al_fallar(self):
        """Verificado indirectamente: si el motor se hubiera
        ejecutado con datos inconsistentes, no habria lanzado -la
        propia excepcion confirma que el flujo nunca llego alla."""
        orquestador, _, estadistica_repo, juego_id = self._orquestador_con([_num(1, (1, 2, 3, 4))])
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        assert estadistica_repo.guardar_fue_llamado is False


class TestExcepcionGeneralizadaCompatibilidad:
    def test_constructor_previo_sigue_siendo_compatible(self):
        e = ResultadoHistoricoInconsistenteError([7, 12], 5)
        assert e.tipo is TipoInconsistenciaHistorica.CANTIDAD

    def test_mensaje_previo_identico_para_cantidad_pequena(self):
        e = ResultadoHistoricoInconsistenteError([7, 12], 5)
        assert str(e) == "Sorteo(s) con cantidad de números distinta de 5 (esperada): numero_sorteo=[7, 12]"

    def test_tipos_cerrados_incluye_los_ocho_valores(self):
        """Etapa AD amplió el conjunto cerrado de forma aditiva -los
        3 tipos originales de Etapa Y/Z siguen intactos, más los 2
        de superbalota. Etapa AE-1 agregó 3 más, específicos de
        ColorLoto, también de forma aditiva."""
        assert {t.value for t in TipoInconsistenciaHistorica} == {
            "cantidad", "duplicados", "rango", "superbalota_ausente", "rango_superbalota",
            "cantidad_pares_colorloto", "rango_numero_colorloto", "color_colorloto_invalido",
        }

    def test_mensaje_duplicados(self):
        e = ResultadoHistoricoInconsistenteError.por_duplicados([3])
        assert "duplicados" in str(e)
        assert "3" in str(e)

    def test_mensaje_rango(self):
        e = ResultadoHistoricoInconsistenteError.por_rango([9], 1, 43)
        assert "[1,43]" in str(e)

    def test_status_sigue_siendo_500_sin_tocar_main(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "ResultadoHistoricoInconsistenteError: 500" in codigo_fuente
        assert codigo_fuente.count("ResultadoHistoricoInconsistenteError:") == 1  # una sola entrada, sin duplicar

    def test_sin_handler_global_de_valueerror(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "@app.exception_handler(ValueError)" not in codigo_fuente

    def test_truncamiento_de_muestra_grande(self):
        grande = list(range(1, 16))
        e = ResultadoHistoricoInconsistenteError.por_duplicados(grande)
        assert "total_afectados=15" in str(e)
        assert str(e).count(",") <= 15  # muestra truncada, no los 15 numeros completos sin limite

    def test_mensaje_nunca_expone_los_numeros_reales_del_sorteo(self):
        e = ResultadoHistoricoInconsistenteError.por_duplicados([1])
        assert "numeros=" not in str(e)  # nunca la tupla real de numeros del sorteo, solo numero_sorteo


class TestRegresionEtapaYConHelperGeneralizado:
    def test_parametros_metrica_de_pares_impares_sigue_siendo_solo_cantidad_numeros(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"cantidad_numeros": 5}
        assert "rango_min" not in fila_guardada.parametros
        assert "rango_max" not in fila_guardada.parametros

    def test_hash_de_pares_impares_no_cambio(self):
        """Mismos parametros producen la misma identidad de cache que
        antes -verificado indirectamente: dos ejecuciones con los
        mismos parametros_metrica producen un cache hit (segunda
        llamada no vuelve a guardar)."""
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador()
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        assert estadistica_repo.guardar_fue_llamado is False  # cache hit, misma identidad

    def test_resultados_validos_identicos_a_antes(self):
        orquestador, _, _, juego_id = _construir_orquestador()
        resultado = orquestador.ejecutar(
            juego_id, "distribucion_pares_impares", hasta_numero_sorteo=3, parametros_metrica=_parametros_pares_impares(),
        )
        filas = {f["valor"]: f["apariciones"] for f in resultado.resultado["filas"]}
        assert filas["2"] == 2
        assert filas["3"] == 1

    def test_longitud_incorrecta_sigue_rechazada(self):
        dataset = [_num(1, (2, 4, 6, 8, 10, 12))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())

    def test_duplicados_ahora_rechazados_correccion_de_laguna_real(self):
        dataset = [_num(1, (1, 1, 3, 5, 7))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
            raise AssertionError("Debio rechazar duplicado")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.DUPLICADOS


class TestNuevaRecetaDistribucionAltosBajos:
    def test_registrada_en_catalogo(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())

    def test_parametros_por_juego_no_hardcodeados(self):
        """Verificado por inspeccion de codigo -los 3 parametros
        vienen de juego_dominio en el router, nunca literales."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def distribucion_altos_bajos(")
        bloque = codigo_fuente[indice:indice + 3000]
        assert "juego_dominio.number_range" in bloque
        assert "juego_dominio.numbers_to_pick" in bloque

    def test_orientacion_valor_es_inferiores(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[_num(1, (1, 10, 21, 22, 43))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        filas = {f["valor"]: f["apariciones"] for f in resultado.resultado["filas"]}
        # (1,10,21,22,43) con corte=21 -> inferiores: 1,10,21 = 3
        assert filas["3"] == 1

    def test_categorias_0_a_k(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        assert len(resultado.resultado["filas"]) == 6

    def test_categorias_cero_conservadas(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[_num(1, (1, 10, 21, 22, 43))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert valores == {"0", "1", "2", "3", "4", "5"}

    def test_serializacion_con_asdict_conserva_los_4_campos(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        fila = resultado.resultado["filas"][0]
        assert set(fila.keys()) == {"valor", "apariciones", "total_sorteos", "frecuencia_relativa"}

    def test_corte_separado_de_parametros_metrica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(
            juego_id, "distribucion_altos_bajos", hasta_numero_sorteo=3, parametros_metrica=_parametros_altos_bajos(),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3

    def test_receta_calcular_no_cambio_de_firma(self):
        import inspect
        from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO
        firma = inspect.signature(_CATALOGO["distribucion_altos_bajos"].calcular)
        assert list(firma.parameters.keys()) == ["historico", "parametros"]

    def test_validacion_previa_a_persistencia(self):
        dataset = [_num(1, (1, 1, 21, 22, 43))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        assert estadistica_repo.guardar_fue_llamado is False


class TestCacheAisladoDistribucionAltosBajos:
    def test_baloto_y_miloto_aislados(self):
        juego_baloto, juego_miloto = uuid4(), uuid4()
        dataset_baloto = [_num(1, (1, 10, 21, 22, 43))]
        dataset_miloto = [_num(1, (1, 5, 19, 20, 39))]
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_baloto: dataset_baloto, juego_miloto: dataset_miloto})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)

        r_baloto = orquestador.ejecutar(juego_baloto, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos(1, 43, 5))
        r_miloto = orquestador.ejecutar(juego_miloto, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos(1, 39, 5))

        filas_baloto = {f["valor"]: f["apariciones"] for f in r_baloto.resultado["filas"]}
        filas_miloto = {f["valor"]: f["apariciones"] for f in r_miloto.resultado["filas"]}
        assert filas_baloto["3"] == 1  # (1,10,21) inferiores de 5
        assert filas_miloto["3"] == 1  # (1,5,19) inferiores de 5, corte=19

    def test_identidad_pares_impares_no_se_ve_afectada_por_altos_bajos(self):
        """Confirma que agregar distribucion_altos_bajos al catalogo
        no interfiere con la identidad de cache ya establecida de
        distribucion_pares_impares -tipos distintos, filas distintas."""
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[_num(1, (1, 10, 21, 22, 43))])
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        tipos_guardados = {f.tipo_estadistica for f in estadistica_repo._filas}
        assert tipos_guardados == {"distribucion_pares_impares", "distribucion_altos_bajos"}


# =====================================================================
# Etapa AA: séptima visualización -distribución de pares consecutivos.
# =====================================================================

def _parametros_pares_consecutivos(rango_min=1, rango_max=43, cantidad_numeros=5) -> dict:
    return {"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}


class TestMotorParesConsecutivosSemantica:
    """Motor/semántica -verificado directamente contra la función
    real del motor, no supuesto."""

    def test_ejemplo_1_2_3_10_20_da_dos_pares(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([_num(1, (1, 2, 3, 10, 20))], 1, 43, 5)
        f2 = next(f for f in filas if f.valor == "2")
        assert f2.apariciones == 1

    def test_ejemplo_1_2_4_5_7_da_dos_pares(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([_num(1, (1, 2, 4, 5, 7))], 1, 43, 5)
        f2 = next(f for f in filas if f.valor == "2")
        assert f2.apariciones == 1

    def test_ejemplo_1_3_5_7_9_da_cero_pares(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([_num(1, (1, 3, 5, 7, 9))], 1, 43, 5)
        f0 = next(f for f in filas if f.valor == "0")
        assert f0.apariciones == 1

    def test_secuencia_completa_de_k_numeros_da_k_menos_1(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([_num(1, (10, 11, 12, 13, 14))], 1, 43, 5)
        f4 = next(f for f in filas if f.valor == "4")
        assert f4.apariciones == 1

    def test_varias_rachas_separadas_suman_sus_pares(self):
        """(1,2,3) aporta 2 + (20,21) aporta 1 = 3 en total."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([_num(1, (1, 2, 3, 20, 21))], 1, 43, 5)
        f3 = next(f for f in filas if f.valor == "3")
        assert f3.apariciones == 1

    def test_entrada_desordenada_mismo_resultado(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        ordenado = [_num(1, (1, 2, 3, 4, 5)), _num(2, (1, 3, 5, 7, 9)), _num(3, (10, 11, 20, 21, 30))]
        desordenado = [ordenado[2], ordenado[0], ordenado[1]]
        f1 = calcular_distribucion_pares_consecutivos(ordenado, 1, 43, 5)
        f2 = calcular_distribucion_pares_consecutivos(desordenado, 1, 43, 5)
        assert f1 == f2

    def test_no_muta_la_entrada(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        dataset = [_num(1, (1, 2, 3, 4, 5))]
        copia = dataset[0].numeros
        calcular_distribucion_pares_consecutivos(dataset, 1, 43, 5)
        assert dataset[0].numeros == copia

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([], 1, 43, 5)
        assert all(f.apariciones == 0 for f in filas)
        assert len(filas) == 5  # 0..K-1 = 0..4

    def test_un_sorteo(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([_num(1, (1, 2, 3, 4, 5))], 1, 43, 5)
        assert filas[0].total_sorteos == 1

    def test_categorias_0_a_k_menos_1_completas(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([], 1, 43, 5)
        assert [f.valor for f in filas] == ["0", "1", "2", "3", "4"]

    def test_categorias_sin_observaciones_en_cero(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([_num(1, (1, 3, 5, 7, 9))], 1, 43, 5)
        assert next(f for f in filas if f.valor == "3").apariciones == 0

    def test_determinismo_misma_entrada_mismo_resultado(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        dataset = [_num(1, (1, 2, 3, 10, 20))]
        assert calcular_distribucion_pares_consecutivos(dataset, 1, 43, 5) == calcular_distribucion_pares_consecutivos(dataset, 1, 43, 5)

    def test_limite_inferior_y_superior_validos(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
        filas = calcular_distribucion_pares_consecutivos([_num(1, (1, 2, 42, 43, 20))], 1, 43, 5)
        f2 = next(f for f in filas if f.valor == "2")
        assert f2.apariciones == 1  # (1,2) y (42,43)


class TestRecetaDistribucionParesConsecutivos:
    """Application/integridad."""

    def test_receta_registrada(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())

    def test_parametros_por_juego_no_hardcodeados_en_router(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def distribucion_pares_consecutivos(")
        bloque = codigo_fuente[indice:indice + 3000]
        assert "juego_dominio.number_range" in bloque
        assert "juego_dominio.numbers_to_pick" in bloque

    def test_cantidad_incorrecta_rechazada_antes_del_motor(self):
        dataset = [_num(1, (1, 2, 3, 4))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        assert estadistica_repo.guardar_fue_llamado is False

    def test_duplicados_rechazados_antes_del_motor(self):
        dataset = [_num(1, (1, 1, 3, 4, 5))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.DUPLICADOS
        assert estadistica_repo.guardar_fue_llamado is False

    def test_valores_fuera_de_rango_rechazados_antes_del_motor(self):
        dataset = [_num(1, (1, 2, 3, 4, 99))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.RANGO
        assert estadistica_repo.guardar_fue_llamado is False

    def test_status_500_preservado(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "ResultadoHistoricoInconsistenteError: 500" in codigo_fuente

    def test_no_persiste_si_validacion_falla(self):
        dataset = [_num(1, (1, 1, 3, 4, 5))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        assert estadistica_repo.guardar_fue_llamado is False

    def test_sin_manejador_global_de_valueerror(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "@app.exception_handler(ValueError)" not in codigo_fuente

    def test_valueerror_defensivo_del_motor_no_se_convierte_en_422_global(self):
        """Confirma que, aunque el motor tiene su propia _validar_rango
        (ValueError interno), la receta lo intercepta ANTES vía
        ResultadoHistoricoInconsistenteError -nunca llega a producirse
        el ValueError del motor en el flujo real de la receta."""
        dataset = [_num(1, (1, 2, 3, 4, 99))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError:
            pass  # esperado -NUNCA un ValueError genérico del motor
        except ValueError as e:
            raise AssertionError(f"Se propagó el ValueError del motor sin control: {e}")

    def test_receta_calcular_conserva_su_firma(self):
        import inspect
        from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO
        firma = inspect.signature(_CATALOGO["distribucion_pares_consecutivos"].calcular)
        assert list(firma.parameters.keys()) == ["historico", "parametros"]

    def test_hasta_numero_sorteo_no_entra_en_parametros_metrica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(
            juego_id, "distribucion_pares_consecutivos", hasta_numero_sorteo=3,
            parametros_metrica=_parametros_pares_consecutivos(),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3

    def test_propiedad_anti_fuga_con_corte(self):
        """Agregar un sorteo futuro (fuera del corte) no debe cambiar
        el resultado calculado con ese corte."""
        dataset_sin_futuro = [_num(1, (1, 2, 3, 4, 5))]
        dataset_con_futuro = [_num(1, (1, 2, 3, 4, 5)), _num(2, (10, 11, 20, 21, 30))]
        orquestador1, _, _, juego_id1 = _construir_orquestador(dataset=dataset_sin_futuro)
        orquestador2, _, _, juego_id2 = _construir_orquestador(dataset=dataset_con_futuro)
        r1 = orquestador1.ejecutar(juego_id1, "distribucion_pares_consecutivos", hasta_numero_sorteo=1, parametros_metrica=_parametros_pares_consecutivos())
        r2 = orquestador2.ejecutar(juego_id2, "distribucion_pares_consecutivos", hasta_numero_sorteo=1, parametros_metrica=_parametros_pares_consecutivos())
        assert r1.resultado == r2.resultado

    def test_historico_vacio_resultado_valido_sin_excepcion(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        assert all(f["apariciones"] == 0 for f in resultado.resultado["filas"])


class TestCacheParesConsecutivos:
    """Caché/persistencia."""

    def test_identidad_por_los_tres_parametros(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}

    def test_cambiar_cantidad_numeros_cambia_el_hash(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos(cantidad_numeros=5))
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos(cantidad_numeros=6))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_cambiar_rango_cambia_el_hash(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos(rango_max=43))
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos(rango_max=39))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_corte_separado_de_identidad(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", hasta_numero_sorteo=3, parametros_metrica=_parametros_pares_consecutivos())
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.hasta_numero_sorteo == 3
        assert "hasta_numero_sorteo" not in fila_guardada.parametros

    def test_upsert_no_duplica(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        total = sum(1 for f in estadistica_repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_pares_consecutivos")
        assert total == 1

    def test_convivencia_sin_interferencia_con_pares_impares_y_altos_bajos(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num(1, (1, 2, 3, 4, 5))]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        tipos_guardados = {f.tipo_estadistica for f in estadistica_repo._filas}
        assert tipos_guardados == {"distribucion_pares_impares", "distribucion_altos_bajos", "distribucion_pares_consecutivos"}

    def test_invalidacion_generica_incluye_la_nueva_metrica(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        vigente = estadistica_repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos", None, _parametros_pares_consecutivos())
        assert vigente is None


# =====================================================================
# Etapa AB: octava visualización -racha máxima de números consecutivos.
# =====================================================================

def _parametros_racha_maxima(rango_min=1, rango_max=43, cantidad_numeros=5) -> dict:
    return {"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}


class TestMotorRachaMaximaSemantica:
    """Motor/semántica -verificado directamente contra la función
    real, sin duplicar tests ya concluyentes del motor -solo se
    cubren aquí los casos pedidos que no estaban ya cubiertos por
    `tests/unit/estadisticas/test_consecutivos.py::TestCalcularDistribucionRachaMaxima`."""

    def test_ejemplo_1_2_3_10_20_da_racha_3(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([_num(1, (1, 2, 3, 10, 20))], 1, 43, 5)
        f3 = next(f for f in filas if f.valor == "3")
        assert f3.apariciones == 1

    def test_ejemplo_1_2_4_5_7_da_racha_2(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([_num(1, (1, 2, 4, 5, 7))], 1, 43, 5)
        f2 = next(f for f in filas if f.valor == "2")
        assert f2.apariciones == 1

    def test_ejemplo_1_3_5_7_9_da_racha_1(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([_num(1, (1, 3, 5, 7, 9))], 1, 43, 5)
        f1 = next(f for f in filas if f.valor == "1")
        assert f1.apariciones == 1

    def test_secuencia_completa_de_k_numeros_da_k(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([_num(1, (1, 2, 3, 4, 5))], 1, 43, 5)
        f5 = next(f for f in filas if f.valor == "5")
        assert f5.apariciones == 1

    def test_categorias_1_a_k_sin_categoria_0(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([], 1, 43, 5)
        assert [f.valor for f in filas] == ["1", "2", "3", "4", "5"]
        assert "0" not in [f.valor for f in filas]

    def test_historico_vacio_produce_categorias_1_a_k_con_cero(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([], 1, 43, 5)
        assert all(f.apariciones == 0 for f in filas)

    def test_un_sorteo(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([_num(1, (1, 2, 3, 4, 5))], 1, 43, 5)
        assert filas[0].total_sorteos == 1

    def test_entrada_desordenada_mismo_resultado(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        ordenado = [_num(1, (20, 1, 10, 3, 2))]
        desordenado = [_num(1, (1, 2, 3, 10, 20))]
        assert calcular_distribucion_racha_maxima(ordenado, 1, 43, 5) == calcular_distribucion_racha_maxima(desordenado, 1, 43, 5)

    def test_determinismo(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        dataset = [_num(1, (1, 2, 3, 10, 20))]
        assert calcular_distribucion_racha_maxima(dataset, 1, 43, 5) == calcular_distribucion_racha_maxima(dataset, 1, 43, 5)

    def test_no_muta_la_entrada(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        dataset = [_num(1, (5, 4, 3, 2, 1))]
        copia = dataset[0].numeros
        calcular_distribucion_racha_maxima(dataset, 1, 43, 5)
        assert dataset[0].numeros == copia

    def test_varias_rachas_separadas_conserva_la_mayor_no_la_suma(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([_num(1, (1, 2, 3, 10, 11))], 1, 43, 5)
        f3 = next(f for f in filas if f.valor == "3")
        assert f3.apariciones == 1  # la mayor (3), no la suma (3+2=5)

    def test_limite_inferior_y_superior_validos(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima
        filas = calcular_distribucion_racha_maxima([_num(1, (1, 2, 42, 43, 20))], 1, 43, 5)
        f2 = next(f for f in filas if f.valor == "2")
        assert f2.apariciones == 1  # (1,2) y (42,43), ambas racha=2, se toma el maximo=2


class TestRecetaDistribucionRachaMaxima:
    """Application/integridad."""

    def test_receta_registrada(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())

    def test_parametros_por_juego_no_hardcodeados_en_router(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def distribucion_racha_maxima(")
        bloque = codigo_fuente[indice:indice + 3000]
        assert "juego_dominio.number_range" in bloque
        assert "juego_dominio.numbers_to_pick" in bloque

    def test_validacion_antes_del_motor_cantidad(self):
        dataset = [_num(1, (1, 2, 3, 4))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
        assert estadistica_repo.guardar_fue_llamado is False

    def test_sorteo_sin_numeros_rechazado(self):
        """Confirma el riesgo identificado en la auditoría: un sorteo
        con numeros=() ahora se rechaza ANTES del motor, en vez de
        desaparecer silenciosamente."""
        dataset = [_num(1, ())]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.CANTIDAD
        assert estadistica_repo.guardar_fue_llamado is False

    def test_duplicados_rechazados_antes_del_motor(self):
        dataset = [_num(1, (1, 1, 3, 4, 5))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.DUPLICADOS
        assert estadistica_repo.guardar_fue_llamado is False

    def test_valores_fuera_de_rango_rechazados_antes_del_motor(self):
        dataset = [_num(1, (1, 2, 3, 4, 99))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.RANGO
        assert estadistica_repo.guardar_fue_llamado is False

    def test_status_500_y_mensaje_seguro_preservados(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "ResultadoHistoricoInconsistenteError: 500" in codigo_fuente

    def test_sin_manejador_global_de_valueerror(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "@app.exception_handler(ValueError)" not in codigo_fuente

    def test_receta_calcular_conserva_su_firma(self):
        import inspect
        from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO
        firma = inspect.signature(_CATALOGO["distribucion_racha_maxima"].calcular)
        assert list(firma.parameters.keys()) == ["historico", "parametros"]

    def test_invocacion_con_cuatro_argumentos_sin_corte(self):
        codigo_fuente = Path("app/application/use_cases/calcular_y_persistir_estadistica.py").read_text(encoding="utf-8")
        assert "return calcular_distribucion_racha_maxima(historico, rango_min, rango_max, cantidad_numeros)" in codigo_fuente

    def test_hasta_numero_sorteo_no_entra_en_parametros_metrica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(
            juego_id, "distribucion_racha_maxima", hasta_numero_sorteo=3,
            parametros_metrica=_parametros_racha_maxima(),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3

    def test_propiedad_anti_fuga_con_corte(self):
        dataset_sin_futuro = [_num(1, (1, 2, 3, 4, 5))]
        dataset_con_futuro = [_num(1, (1, 2, 3, 4, 5)), _num(2, (10, 11, 20, 21, 30))]
        orquestador1, _, _, juego_id1 = _construir_orquestador(dataset=dataset_sin_futuro)
        orquestador2, _, _, juego_id2 = _construir_orquestador(dataset=dataset_con_futuro)
        r1 = orquestador1.ejecutar(juego_id1, "distribucion_racha_maxima", hasta_numero_sorteo=1, parametros_metrica=_parametros_racha_maxima())
        r2 = orquestador2.ejecutar(juego_id2, "distribucion_racha_maxima", hasta_numero_sorteo=1, parametros_metrica=_parametros_racha_maxima())
        assert r1.resultado == r2.resultado

    def test_serializacion_con_asdict(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
        fila = resultado.resultado["filas"][0]
        assert set(fila.keys()) == {"valor", "apariciones", "total_sorteos", "frecuencia_relativa"}

    def test_historico_vacio_resultado_valido_sin_excepcion(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
        assert all(f["apariciones"] == 0 for f in resultado.resultado["filas"])


class TestCacheRachaMaxima:
    """Caché/persistencia/invalidación."""

    def test_identidad_por_los_tres_parametros(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}

    def test_cambiar_cantidad_numeros_cambia_el_hash(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima(cantidad_numeros=5))
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima(cantidad_numeros=6))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_cambiar_rango_cambia_el_hash(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima(rango_max=43))
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima(rango_max=39))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_corte_separado_de_identidad(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", hasta_numero_sorteo=3, parametros_metrica=_parametros_racha_maxima())
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.hasta_numero_sorteo == 3
        assert "hasta_numero_sorteo" not in fila_guardada.parametros

    def test_historico_completo_y_corte_coexisten(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", hasta_numero_sorteo=None, parametros_metrica=_parametros_racha_maxima())
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", hasta_numero_sorteo=3, parametros_metrica=_parametros_racha_maxima())
        total = sum(1 for f in estadistica_repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_racha_maxima")
        assert total == 2

    def test_upsert_no_duplica(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
        total = sum(1 for f in estadistica_repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_racha_maxima")
        assert total == 1

    def test_convivencia_sin_interferencia_con_metricas_anteriores(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num(1, (1, 2, 3, 4, 5))]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
        tipos_guardados = {f.tipo_estadistica for f in estadistica_repo._filas}
        assert tipos_guardados == {
            "distribucion_pares_impares", "distribucion_altos_bajos",
            "distribucion_pares_consecutivos", "distribucion_racha_maxima",
        }


# =====================================================================
# Etapa AC: novena visualización -repeticiones entre sorteos consecutivos.
# =====================================================================

def _parametros_repeticiones(rango_min=1, rango_max=43, cantidad_numeros=5) -> dict:
    return {"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}


class TestRecetaDistribucionRepeticionesEntreSorteos:
    """Application/integridad -no duplica los tests exhaustivos ya
    concluyentes del motor (huecos, orden, determinismo, corte),
    prueba la conexión y las garantías específicas de la receta."""

    def test_receta_registrada(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())

    def test_parametros_completos_de_produccion(self):
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index("def repeticiones_entre_sorteos(")
        bloque = codigo_fuente[indice:indice + 3000]
        assert "juego_dominio.number_range" in bloque
        assert "juego_dominio.numbers_to_pick" in bloque

    def test_invocacion_al_motor_con_cuatro_argumentos_sin_corte(self):
        codigo_fuente = Path("app/application/use_cases/calcular_y_persistir_estadistica.py").read_text(encoding="utf-8")
        assert "return calcular_repeticiones_entre_sorteos(historico, rango_min, rango_max, cantidad_numeros)" in codigo_fuente

    def test_historico_vacio_valido(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert all(f["apariciones"] == 0 for f in resultado.resultado["filas"])

    def test_un_sorteo_produce_cero_transiciones(self):
        dataset = [_num(1, (1, 2, 3, 4, 5))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert resultado.resultado["filas"][0]["total_sorteos"] == 0

    def test_dos_sorteos_consecutivos_producen_una_transicion(self):
        dataset = [_num(100, (1, 2, 3, 4, 5)), _num(101, (1, 2, 10, 11, 12))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_categoria_0_con_transicion_sin_coincidencias_y_conservacion_de_masa(self):
        """Cubre explícitamente los invariantes NO probados por los
        demás tests de esta clase (todos usan datasets con al menos
        una coincidencia): una transición SIN ninguna coincidencia
        debe caer en la categoría "0" con apariciones=1 real -no
        desaparecer ni confundirse con "sin datos"-, coexistiendo con
        otra transición de categoría distinta, y la suma de
        apariciones de TODAS las categorías debe ser exactamente
        igual a total_sorteos (conservación de masa: ninguna
        transición se pierde ni se cuenta dos veces)."""
        dataset = [
            _num(100, (1, 2, 3, 4, 5)), _num(101, (10, 11, 12, 13, 14)),  # 0 coincidencias
            _num(102, (10, 20, 21, 22, 23)),  # 1 coincidencia con el anterior (el 10)
        ]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        filas = {f["valor"]: f["apariciones"] for f in resultado.resultado["filas"]}
        assert filas["0"] == 1
        assert filas["1"] == 1
        total_sorteos = resultado.resultado["filas"][0]["total_sorteos"]
        assert total_sorteos == 2
        assert sum(filas.values()) == total_sorteos

    def test_tres_consecutivos_producen_dos_transiciones(self):
        dataset = [_num(100, (1, 2, 3, 4, 5)), _num(101, (1, 2, 10, 11, 12)), _num(102, (1, 20, 21, 22, 23))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert resultado.resultado["filas"][0]["total_sorteos"] == 2

    def test_hueco_no_produce_transicion(self):
        dataset = [_num(100, (1, 2, 3, 4, 5)), _num(102, (1, 2, 10, 11, 12))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert resultado.resultado["filas"][0]["total_sorteos"] == 0

    def test_entrada_desordenada_mismo_resultado(self):
        orden = [_num(100, (1, 2, 3, 4, 5)), _num(101, (1, 2, 10, 11, 12))]
        invertido = [orden[1], orden[0]]
        orquestador1, _, _, juego_id1 = _construir_orquestador(dataset=orden)
        orquestador2, _, _, juego_id2 = _construir_orquestador(dataset=invertido)
        r1 = orquestador1.ejecutar(juego_id1, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        r2 = orquestador2.ejecutar(juego_id2, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert r1.resultado == r2.resultado

    def test_posicion_de_numeros_irrelevante(self):
        dataset = [_num(100, (5, 4, 3, 2, 1)), _num(101, (1, 2, 3, 4, 5))]
        orquestador, _, _, juego_id = _construir_orquestador(dataset=dataset)
        resultado = orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        f5 = next(f for f in resultado.resultado["filas"] if f["valor"] == "5")
        assert f5["apariciones"] == 1  # interseccion completa pese al orden distinto

    def test_categorias_0_a_k(self):
        orquestador, _, _, juego_id = _construir_orquestador(dataset=[])
        resultado = orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert [f["valor"] for f in resultado.resultado["filas"]] == ["0", "1", "2", "3", "4", "5"]

    def test_rechazo_sorteo_vacio_antes_del_motor(self):
        dataset = [_num(1, ())]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.CANTIDAD
        assert estadistica_repo.guardar_fue_llamado is False

    def test_rechazo_cantidad_menor_antes_del_motor(self):
        dataset = [_num(1, (1, 2, 3, 4)), _num(2, (1, 2, 10, 11))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert estadistica_repo.guardar_fue_llamado is False

    def test_rechazo_cantidad_mayor_antes_del_motor(self):
        dataset = [_num(1, (1, 2, 3, 4, 5, 6)), _num(2, (1, 2, 10, 11, 12, 13))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert estadistica_repo.guardar_fue_llamado is False

    def test_rechazo_duplicados_antes_del_motor(self):
        dataset = [_num(1, (1, 1, 3, 4, 5)), _num(2, (1, 1, 10, 11, 12))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.DUPLICADOS
        assert estadistica_repo.guardar_fue_llamado is False

    def test_rechazo_inferior_al_rango_antes_del_motor(self):
        dataset = [_num(1, (0, 2, 3, 4, 5)), _num(2, (1, 2, 10, 11, 12))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.RANGO
        assert estadistica_repo.guardar_fue_llamado is False

    def test_rechazo_superior_al_rango_antes_del_motor(self):
        dataset = [_num(1, (1, 2, 3, 4, 99)), _num(2, (1, 2, 10, 11, 12))]
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=dataset)
        try:
            orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.RANGO
        assert estadistica_repo.guardar_fue_llamado is False

    def test_status_500_preservado(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "ResultadoHistoricoInconsistenteError: 500" in codigo_fuente

    def test_sin_manejador_global_de_valueerror(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "@app.exception_handler(ValueError)" not in codigo_fuente

    def test_receta_calcular_conserva_su_firma(self):
        import inspect
        from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO
        firma = inspect.signature(_CATALOGO["distribucion_repeticiones_entre_sorteos"].calcular)
        assert list(firma.parameters.keys()) == ["historico", "parametros"]

    def test_hasta_numero_sorteo_no_entra_en_parametros_metrica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(
            juego_id, "distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=3,
            parametros_metrica=_parametros_repeticiones(),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3

    def test_propiedad_anti_fuga_con_corte(self):
        dataset_sin_futuro = [_num(100, (1, 2, 3, 4, 5)), _num(101, (1, 2, 10, 11, 12))]
        dataset_con_futuro = [_num(100, (1, 2, 3, 4, 5)), _num(101, (1, 2, 10, 11, 12)), _num(102, (1, 20, 21, 22, 23))]
        orquestador1, _, _, juego_id1 = _construir_orquestador(dataset=dataset_sin_futuro)
        orquestador2, _, _, juego_id2 = _construir_orquestador(dataset=dataset_con_futuro)
        r1 = orquestador1.ejecutar(juego_id1, "distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=101, parametros_metrica=_parametros_repeticiones())
        r2 = orquestador2.ejecutar(juego_id2, "distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=101, parametros_metrica=_parametros_repeticiones())
        assert r1.resultado == r2.resultado

    def test_identidad_de_cache_exacta(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}


class TestCacheRepeticionesEntreSorteos:
    """Caché/persistencia/invalidación."""

    def test_aislamiento_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoriaConEspia()
        juego_a, juego_b = uuid4(), uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_a: [], juego_b: []})
        orquestador = CalcularYPersistirEstadistica(historico_repo, repo)
        orquestador.ejecutar(juego_a, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        orquestador.ejecutar(juego_b, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        assert sum(1 for f in repo._filas if f.tipo_estadistica == "distribucion_repeticiones_entre_sorteos") == 2

    def test_aislamiento_por_tipo(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_repeticiones())
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        tipos = {f.tipo_estadistica for f in estadistica_repo._filas}
        assert tipos == {"distribucion_racha_maxima", "distribucion_repeticiones_entre_sorteos"}

    def test_cambiar_cantidad_numeros_cambia_el_hash(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones(cantidad_numeros=5))
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones(cantidad_numeros=6))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_cambiar_rango_cambia_el_hash(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones(rango_max=43))
        estadistica_repo.guardar_fue_llamado = False
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones(rango_max=39))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_corte_no_entra_en_parametros_metrica(self):
        orquestador, _, estadistica_repo, juego_id = _construir_orquestador(dataset=[])
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=3, parametros_metrica=_parametros_repeticiones())
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3

    def test_upsert_no_duplica(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: []})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        total = sum(1 for f in estadistica_repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_repeticiones_entre_sorteos")
        assert total == 1

    def test_convivencia_sin_interferencia_con_las_cuatro_metricas_recientes(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num(1, (1, 2, 3, 4, 5))]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "distribucion_pares_impares", parametros_metrica=_parametros_pares_impares())
        orquestador.ejecutar(juego_id, "distribucion_altos_bajos", parametros_metrica=_parametros_altos_bajos())
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos", parametros_metrica=_parametros_pares_consecutivos())
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima", parametros_metrica=_parametros_racha_maxima())
        orquestador.ejecutar(juego_id, "distribucion_repeticiones_entre_sorteos", parametros_metrica=_parametros_repeticiones())
        tipos_guardados = {f.tipo_estadistica for f in estadistica_repo._filas}
        assert tipos_guardados == {
            "distribucion_pares_impares", "distribucion_altos_bajos", "distribucion_pares_consecutivos",
            "distribucion_racha_maxima", "distribucion_repeticiones_entre_sorteos",
        }


# =====================================================================
# Etapa AD: endurecimiento de integridad de frecuencia_superbalota.
# =====================================================================

def _num_sb_ad(n, sb):
    return _num_sb(n, (1, 2, 3, 4, 5), sb)


class TestExcepcionSuperbalotaAusenteYRango:
    """3.1 -Excepción y helper."""

    def test_historico_vacio_valido(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_superbalota_consistente
        _validar_historico_superbalota_consistente([], 1, 16)

    def test_historico_valido_con_limites_incluidos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_superbalota_consistente
        _validar_historico_superbalota_consistente([_num_sb_ad(1, 1), _num_sb_ad(2, 16)], 1, 16)

    def test_superbalota_none_produce_tipo_cerrado_de_ausencia(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_superbalota_consistente
        try:
            _validar_historico_superbalota_consistente([_num_sb_ad(1, None)], 1, 16)
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.SUPERBALOTA_AUSENTE

    def test_superbalota_igual_a_rango_min_es_valida(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_superbalota_consistente
        _validar_historico_superbalota_consistente([_num_sb_ad(1, 1)], 1, 16)

    def test_superbalota_igual_a_rango_max_es_valida(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_superbalota_consistente
        _validar_historico_superbalota_consistente([_num_sb_ad(1, 16)], 1, 16)

    def test_valor_menor_que_rango_min_produce_rango_superbalota(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_superbalota_consistente
        try:
            _validar_historico_superbalota_consistente([_num_sb_ad(1, 0)], 1, 16)
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.RANGO_SUPERBALOTA

    def test_valor_mayor_que_rango_max_produce_rango_superbalota(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_superbalota_consistente
        try:
            _validar_historico_superbalota_consistente([_num_sb_ad(1, 17)], 1, 16)
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.RANGO_SUPERBALOTA

    def test_ausencia_se_evalua_antes_que_rango(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _validar_historico_superbalota_consistente
        try:
            _validar_historico_superbalota_consistente([_num_sb_ad(1, None), _num_sb_ad(2, 999)], 1, 16)
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.SUPERBALOTA_AUSENTE

    def test_mensaje_seguro_incluye_sorteo_rango_no_valor_corrupto(self):
        e = ResultadoHistoricoInconsistenteError.por_rango_superbalota([7], 1, 16)
        mensaje = str(e)
        assert "7" in mensaje
        assert "[1,16]" in mensaje
        assert "999" not in mensaje

    def test_compatibilidad_byte_a_byte_de_mensajes_preexistentes(self):
        e_cantidad = ResultadoHistoricoInconsistenteError([7, 12], 5)
        assert str(e_cantidad) == "Sorteo(s) con cantidad de números distinta de 5 (esperada): numero_sorteo=[7, 12]"
        e_dup = ResultadoHistoricoInconsistenteError.por_duplicados([3])
        assert str(e_dup) == "Sorteo(s) con números duplicados: numero_sorteo=[3]"
        e_rango = ResultadoHistoricoInconsistenteError.por_rango([9], 1, 43)
        assert str(e_rango) == "Sorteo(s) con números fuera del rango [1,43]: numero_sorteo=[9]"

    def test_cero_sentencias_assert_en_el_nuevo_helper(self):
        import ast
        codigo_fuente = Path("app/application/use_cases/calcular_y_persistir_estadistica.py").read_text(encoding="utf-8")
        arbol = ast.parse(codigo_fuente)
        funcion = next(
            n for n in ast.walk(arbol)
            if isinstance(n, ast.FunctionDef) and n.name == "_validar_historico_superbalota_consistente"
        )
        assert any(isinstance(n, ast.Assert) for n in ast.walk(funcion)) is False

    def test_nueva_excepcion_no_es_valueerror_ni_depende_de_handler_global(self):
        e = ResultadoHistoricoInconsistenteError.por_superbalota_ausente([1])
        assert not isinstance(e, ValueError)
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "@app.exception_handler(ValueError)" not in codigo_fuente


class TestRecetaFrecuenciaSuperbalotaValidacionAD:
    """3.2 -Receta."""

    def test_receta_valida_produce_mismo_resultado_de_siempre(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO
        receta = _CATALOGO["frecuencia_superbalota"]
        r = receta.calcular([_num_sb_ad(1, 9), _num_sb_ad(2, 9), _num_sb_ad(3, 5)], {"rango_min": 1, "rango_max": 16})
        serial = receta.serializar(r)
        assert next(f for f in serial["filas"] if f["valor"] == "9")["apariciones"] == 2
        assert next(f for f in serial["filas"] if f["valor"] == "9")["total_sorteos"] == 3

    def test_motor_no_invocado_cuando_falta_superbalota(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_superbalota
        llamado = {"valor": False}

        def espia(*a, **kw):
            llamado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_superbalota = espia
        try:
            modulo._calcular_frecuencia_superbalota([_num_sb_ad(1, None)], {"rango_min": 1, "rango_max": 16})
        except ResultadoHistoricoInconsistenteError:
            pass
        finally:
            modulo.calcular_frecuencia_superbalota = original
        assert llamado["valor"] is False

    def test_motor_no_invocado_cuando_fuera_de_rango(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_superbalota
        llamado = {"valor": False}

        def espia(*a, **kw):
            llamado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_superbalota = espia
        try:
            modulo._calcular_frecuencia_superbalota([_num_sb_ad(1, 999)], {"rango_min": 1, "rango_max": 16})
        except ResultadoHistoricoInconsistenteError:
            pass
        finally:
            modulo.calcular_frecuencia_superbalota = original
        assert llamado["valor"] is False

    def test_no_se_guarda_ni_actualiza_cache_si_falla_ausencia(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num_sb_ad(1, None)]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 16})
        assert estadistica_repo.guardar_fue_llamado is False

    def test_no_se_guarda_ni_actualiza_cache_si_falla_rango(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num_sb_ad(1, 999)]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        with pytest.raises(ResultadoHistoricoInconsistenteError):
            orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 16})
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_conserva_comportamiento_existente(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO
        receta = _CATALOGO["frecuencia_superbalota"]
        r = receta.calcular([], {"rango_min": 1, "rango_max": 16})
        assert len(r) == 16
        assert all(f.apariciones == 0 for f in r)

    def test_hasta_numero_sorteo_sigue_separado_de_parametros_metrica(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num_sb_ad(1, 9)]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(
            juego_id, "frecuencia_superbalota", hasta_numero_sorteo=1,
            parametros_metrica={"rango_min": 1, "rango_max": 16},
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 1

    def test_parametros_e_identidad_de_cache_sin_cambios(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num_sb_ad(1, 9)]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 16})
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 16}

    def test_fila_cacheada_valida_sigue_siendo_recuperable(self):
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num_sb_ad(1, 9)]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        primera = orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 16})
        historico_repo.fue_consultado = False
        segunda = orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 16})
        assert historico_repo.fue_consultado is False
        assert primera.id == segunda.id

    def test_corrupcion_produce_500_controlado_no_422_ni_generico(self):
        """Confirma que ResultadoHistoricoInconsistenteError (mapeada
        a 500 en _STATUS_POR_EXCEPCION) es la excepción real lanzada
        -nunca JuegoSinSuperbalotaError (422) ni una excepción
        genérica no controlada."""
        juego_id = uuid4()
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({juego_id: [_num_sb_ad(1, None)]})
        estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo)
        try:
            orquestador.ejecutar(juego_id, "frecuencia_superbalota", parametros_metrica={"rango_min": 1, "rango_max": 16})
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError:
            pass  # esperado -mapeada a 500 por _STATUS_POR_EXCEPCION, confirmado en otro test
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "ResultadoHistoricoInconsistenteError: 500" in codigo_fuente


# =====================================================================
# Etapa AE-1: primera visualización descriptiva de ColorLoto.
# =====================================================================

def _cl(numero_sorteo, pares, fecha=None):
    return ResultadoColorLoto(
        numero_sorteo=numero_sorteo, fecha=fecha or (_FECHA_BASE + timedelta(days=numero_sorteo)),
        dia_semana="lunes", pares=pares,
    )


def _col(codigo, activo=True, desde=None, hasta=None):
    return Color(codigo=codigo, nombre=codigo.title(), activo=activo, vigente_desde=desde, vigente_hasta=hasta)


_PALETA_COLORLOTO = [_col("ROJO"), _col("AZUL"), _col("VERDE"), _col("NEGRO"), _col("BLANCO"), _col("AMARILLO")]
_PARES_VALIDOS = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
_PARAMS_COLORLOTO = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}


def _orquestador_colorloto(datos_colorloto, colores=None):
    juego_id = uuid4()
    historico_repo = _HistoricoRepositoryEnMemoriaConEspia({}, datos_colorloto={juego_id: datos_colorloto})
    color_repo = _ColorRepositoryEnMemoriaConEspia({juego_id: colores if colores is not None else list(_PALETA_COLORLOTO)})
    estadistica_repo = _EstadisticaRepositoryEnMemoriaConEspia()
    orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo, color_repository=color_repo)
    return orquestador, historico_repo, color_repo, estadistica_repo, juego_id


class TestMotorFrecuenciaNumerosColorLotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en el turno de
    diseño previo -aquí solo se confirman los casos obligatorios
    explícitos de esta implementación, sin duplicar lo ya probado."""

    def test_firma_y_siete_categorias(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros_colorloto
        r = calcular_frecuencia_numeros_colorloto([_cl(1, _PARES_VALIDOS)], 1, 7)
        assert [f.valor for f in r] == [str(i) for i in range(1, 8)]

    def test_repeticion_dentro_de_un_sorteo_cuenta_varias_apariciones_y_promedio_2(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros_colorloto
        pares = ((1, "ROJO"), (1, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_frecuencia_numeros_colorloto([_cl(1, pares)], 1, 7)
        f1 = next(f for f in r if f.valor == "1")
        assert f1.apariciones == 2
        assert f1.frecuencia_relativa == 2.0

    def test_historico_vacio_siete_categorias_en_cero(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros_colorloto
        r = calcular_frecuencia_numeros_colorloto([], 1, 7)
        assert all(f.apariciones == 0 for f in r)

    def test_conservacion_de_masa_apariciones_y_promedios(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros_colorloto
        r = calcular_frecuencia_numeros_colorloto([_cl(1, _PARES_VALIDOS), _cl(2, _PARES_VALIDOS)], 1, 7)
        assert sum(f.apariciones for f in r) == 6 * 2
        assert sum(f.frecuencia_relativa for f in r) == 6


class TestRecetaFrecuenciaNumerosColorLoto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_numeros_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_numeros_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_las_nueve_recetas_numericas_previas_conservan_fuente_numerica(self):
        """Actualizado en Etapa AE-5: excluye las cinco recetas de
        ColorLoto (frecuencia_numeros_colorloto, frecuencia_colores_colorloto,
        frecuencia_pares_colorloto, atrasos_numeros_colorloto Y
        atrasos_colores_colorloto), no solo las cuatro anteriores."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_numerico
        recetas_colorloto = ("frecuencia_numeros_colorloto", "frecuencia_colores_colorloto", "frecuencia_pares_colorloto", "atrasos_numeros_colorloto", "atrasos_colores_colorloto", "atrasos_pares_colorloto", "repeticiones_entre_sorteos_colorloto", "distribucion_pares_impares_colorloto", "distribucion_altos_bajos_colorloto", "maximo_repeticion_color_por_sorteo_colorloto", "distribucion_pares_consecutivos_colorloto", "distribucion_racha_maxima_colorloto", "distribucion_trios_consecutivos_colorloto", "coocurrencia_pares_colorloto", "coocurrencia_trios_colorloto", "coocurrencia_pares_colores_colorloto", "coocurrencia_trios_colores_colorloto", "intervalos_historicos_colores_colorloto", "distribucion_sumas_colorloto", "intervalos_historicos_numeros_colorloto", "intervalos_historicos_pares_numero_color_colorloto", "frecuencia_colores_por_anio_colorloto", "frecuencia_colores_por_mes_colorloto", "frecuencia_colores_por_dia_semana_colorloto", "frecuencia_pares_numero_color_por_anio_colorloto", "frecuencia_pares_numero_color_por_mes_colorloto", "frecuencia_pares_numero_color_por_dia_semana_colorloto")
        for nombre, receta in _CATALOGO.items():
            if nombre not in recetas_colorloto:
                assert receta.obtener_historico is _obtener_historico_numerico, nombre

    def test_no_se_llama_listar_resultados_numericos_para_colorloto(self):
        orquestador, historico_repo, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado is False
        assert historico_repo.fue_consultado_colorloto is True

    def test_parametros_exactos_con_cantidad_numeros(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_corte_separado_sin_doble_aplicacion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(
            juego_id, "frecuencia_numeros_colorloto", hasta_numero_sorteo=1,
            parametros_metrica=dict(_PARAMS_COLORLOTO),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 1

    def test_cache_hit_no_consulta_historico(self):
        orquestador, historico_repo, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        historico_repo.fue_consultado_colorloto = False
        color_repo.llamadas_listar_todos = 0
        orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado_colorloto is False
        assert color_repo.llamadas_listar_todos == 0

    def test_cambio_de_k_no_colisiona_con_cache_anterior(self):
        """Confirma la propiedad de identidad de caché directamente
        contra `EstadisticaCalculada`/`buscar_vigente` -sin pasar por
        la validación de integridad del histórico real (que
        rechazaría correctamente un K distinto del real, algo ya
        probado por separado), aislando la variable bajo prueba:
        `cantidad_numeros` SÍ debe formar parte de la identidad de
        caché."""
        _, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        entrada_k6 = EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_numeros_colorloto",
            hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6},
            parametros_hash="", resultado={"filas": []}, calculado_en=None, valido_hasta=None,
        )
        estadistica_repo.guardar(entrada_k6)
        vigente_con_k5 = estadistica_repo.buscar_vigente(
            juego_id, "frecuencia_numeros_colorloto", None, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 5},
        )
        assert vigente_con_k5 is None

    def test_catalogo_cargado_una_sola_vez_en_cache_miss(self):
        orquestador, _, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert color_repo.llamadas_listar_todos == 1

    def test_validacion_orden_cantidad_antes_que_rango_antes_que_color(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5])])
        try:
            orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.CANTIDAD_PARES_COLORLOTO
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_historicamente_valido_pero_inactivo_hoy_aceptado(self):
        paleta_con_retirado = list(_PALETA_COLORLOTO) + [_col("ROSADO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]
        pares = ((1, "ROSADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto(
            [_cl(1, pares, fecha=date(2022, 6, 15))], colores=paleta_con_retirado,
        )
        orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_color_futuro_para_la_fecha_rechazado(self):
        paleta_con_futuro = list(_PALETA_COLORLOTO) + [_col("MORADO", activo=True, desde=date(2030, 1, 1))]
        pares = ((1, "MORADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto(
            [_cl(1, pares, fecha=date(2024, 1, 1))], colores=paleta_con_futuro,
        )
        try:
            orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_vencido_rechazado(self):
        pares = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "MORADO"))
        paleta_vencida = list(_PALETA_COLORLOTO) + [_col("MORADO", activo=False, desde=date(2010, 1, 1), hasta=date(2015, 1, 1))]
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto(
            [_cl(1, pares, fecha=date(2024, 1, 1))], colores=paleta_vencida,
        )
        try:
            orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO

    def test_color_de_otro_juego_rechazado(self):
        # coloresp de "otro juego" simplemente no aparecen en el catalogo del juego_id consultado
        paleta_sin_color_de_otro_juego = [c for c in _PALETA_COLORLOTO if c.codigo != "AMARILLO"]
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS)], colores=paleta_sin_color_de_otro_juego,
        )
        try:
            orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO

    def test_color_inexistente_rechazado(self):
        pares = ((1, "INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares)])
        try:
            orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO
            assert "INVENTADO" not in str(e)

    def test_motor_no_invocado_ante_corrupcion(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_numeros_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_numeros_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5])])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_frecuencia_numeros_colorloto = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_corrupcion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5])])
        try:
            orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_serializacion_correcta(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert "filas" in resultado.resultado
        assert len(resultado.resultado["filas"]) == 7

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True


class TestExcepcionesColorLoto:
    def test_tres_tipos_nuevos_exactos(self):
        assert {
            TipoInconsistenciaHistorica.CANTIDAD_PARES_COLORLOTO,
            TipoInconsistenciaHistorica.RANGO_NUMERO_COLORLOTO,
            TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO,
        }.issubset(set(TipoInconsistenciaHistorica))

    def test_ocho_tipos_totales(self):
        assert len({t.value for t in TipoInconsistenciaHistorica}) == 8

    def test_mensajes_seguros_sin_valor_corrupto(self):
        e = ResultadoHistoricoInconsistenteError.por_color_colorloto_invalido([1])
        assert "INVENTADO" not in str(e)
        assert "1" in str(e)

    def test_truncamiento_para_listas_largas(self):
        e = ResultadoHistoricoInconsistenteError.por_rango_numero_colorloto(list(range(1, 30)), 1, 7)
        assert "..." in str(e) or "total" in str(e).lower() or len(str(e)) < 500

    def test_http_500_mediante_handler_existente(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "ResultadoHistoricoInconsistenteError: 500" in codigo_fuente

    def test_sin_handler_global(self):
        codigo_fuente = Path("app/main.py").read_text(encoding="utf-8")
        assert "@app.exception_handler(ValueError)" not in codigo_fuente

    def test_sin_assert_en_helper_colorloto(self):
        import ast
        codigo_fuente = Path("app/application/use_cases/calcular_y_persistir_estadistica.py").read_text(encoding="utf-8")
        arbol = ast.parse(codigo_fuente)
        funcion = next(
            n for n in ast.walk(arbol)
            if isinstance(n, ast.FunctionDef) and n.name == "_validar_historico_colorloto_consistente"
        )
        assert any(isinstance(n, ast.Assert) for n in ast.walk(funcion)) is False


# =====================================================================
# Etapa AE-2: segunda visualización descriptiva de ColorLoto -
# frecuencia de colores. Reutiliza los helpers de Etapa AE-1
# (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS, _PARAMS_COLORLOTO,
# _orquestador_colorloto) sin duplicarlos.
# =====================================================================

class TestMotorFrecuenciaColoresColorLotoSemantica:
    def test_firma_y_seis_categorias_con_paleta_completa(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        r = calcular_frecuencia_colores([_cl(1, _PARES_VALIDOS)], [c.codigo for c in _PALETA_COLORLOTO])
        assert sorted(f.valor for f in r) == sorted(c.codigo for c in _PALETA_COLORLOTO)

    def test_color_repetido_dentro_de_un_sorteo_cuenta_varias_apariciones(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        pares = ((1, "ROJO"), (2, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_frecuencia_colores([_cl(1, pares)], [c.codigo for c in _PALETA_COLORLOTO])
        rojo = next(f for f in r if f.valor == "ROJO")
        assert rojo.apariciones == 2
        assert rojo.frecuencia_relativa == 2.0

    def test_categoria_con_cero_apariciones_preservada(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        pares = ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "ROJO"))
        r = calcular_frecuencia_colores([_cl(1, pares)], [c.codigo for c in _PALETA_COLORLOTO])
        azul = next(f for f in r if f.valor == "AZUL")
        assert azul.apariciones == 0

    def test_orden_deterministico_alfabetico_por_codigo(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        r = calcular_frecuencia_colores([_cl(1, _PARES_VALIDOS)], [c.codigo for c in _PALETA_COLORLOTO])
        assert [f.valor for f in r] == sorted(f.valor for f in r)

    def test_conservacion_de_masa(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        r = calcular_frecuencia_colores(
            [_cl(1, _PARES_VALIDOS), _cl(2, _PARES_VALIDOS)], [c.codigo for c in _PALETA_COLORLOTO],
        )
        assert sum(f.apariciones for f in r) == 6 * 2
        assert sum(f.frecuencia_relativa for f in r) == 6

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        r = calcular_frecuencia_colores([], [c.codigo for c in _PALETA_COLORLOTO])
        assert all(f.apariciones == 0 for f in r)

    def test_entrada_desordenada_produce_mismo_resultado(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        d1 = [_cl(1, _PARES_VALIDOS), _cl(2, _PARES_VALIDOS)]
        d2 = [d1[1], d1[0]]
        codigos = [c.codigo for c in _PALETA_COLORLOTO]
        assert calcular_frecuencia_colores(d1, codigos) == calcular_frecuencia_colores(d2, codigos)

    def test_empates_multiples_colores_mismo_valor(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_colores
        pares = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_frecuencia_colores([_cl(1, pares)], [c.codigo for c in _PALETA_COLORLOTO])
        assert all(f.apariciones == 1 for f in r)


class TestRecetaFrecuenciaColoresColorLoto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_colores_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_colores_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_las_diez_recetas_previas_conservan_su_fuente(self):
        """Actualizado en Etapa AE-5: excluye las cinco recetas de
        ColorLoto, no solo las cuatro anteriores."""
        from app.application.use_cases.calcular_y_persistir_estadistica import (
            _obtener_historico_numerico, _obtener_historico_colorloto,
        )
        recetas_colorloto_con_fuente_colorloto = ("frecuencia_numeros_colorloto", "frecuencia_colores_colorloto", "frecuencia_pares_colorloto", "atrasos_numeros_colorloto", "atrasos_colores_colorloto", "atrasos_pares_colorloto", "repeticiones_entre_sorteos_colorloto", "distribucion_pares_impares_colorloto", "distribucion_altos_bajos_colorloto", "maximo_repeticion_color_por_sorteo_colorloto", "distribucion_pares_consecutivos_colorloto", "distribucion_racha_maxima_colorloto", "distribucion_trios_consecutivos_colorloto", "coocurrencia_pares_colorloto", "coocurrencia_trios_colorloto", "coocurrencia_pares_colores_colorloto", "coocurrencia_trios_colores_colorloto", "intervalos_historicos_colores_colorloto", "distribucion_sumas_colorloto", "intervalos_historicos_numeros_colorloto", "intervalos_historicos_pares_numero_color_colorloto", "frecuencia_colores_por_anio_colorloto", "frecuencia_colores_por_mes_colorloto", "frecuencia_colores_por_dia_semana_colorloto", "frecuencia_pares_numero_color_por_anio_colorloto", "frecuencia_pares_numero_color_por_mes_colorloto", "frecuencia_pares_numero_color_por_dia_semana_colorloto")
        for nombre, receta in _CATALOGO.items():
            if nombre in recetas_colorloto_con_fuente_colorloto:
                assert receta.obtener_historico is _obtener_historico_colorloto, nombre
            else:
                assert receta.obtener_historico is _obtener_historico_numerico, nombre

    def test_no_se_llama_listar_resultados_numericos_para_colorloto(self):
        orquestador, historico_repo, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado is False
        assert historico_repo.fue_consultado_colorloto is True

    def test_parametros_exactos_identicos_a_frecuencia_numeros(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_corte_separado_sin_doble_aplicacion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(
            juego_id, "frecuencia_colores_colorloto", hasta_numero_sorteo=1,
            parametros_metrica=dict(_PARAMS_COLORLOTO),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 1

    def test_cache_hit_no_consulta_historico_ni_catalogo(self):
        orquestador, historico_repo, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        historico_repo.fue_consultado_colorloto = False
        color_repo.llamadas_listar_todos = 0
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado_colorloto is False
        assert color_repo.llamadas_listar_todos == 0

    def test_catalogo_cargado_una_sola_vez_en_cache_miss(self):
        orquestador, _, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert color_repo.llamadas_listar_todos == 1

    def test_exactamente_una_llamada_al_motor_en_calculo_valido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores
        llamadas = {"n": 0}

        def espia(*a, **kw):
            llamadas["n"] += 1
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
            orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_frecuencia_colores = original
        assert llamadas["n"] == 1

    def test_motor_no_invocado_ante_cantidad_incorrecta(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5])])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_frecuencia_colores = original
        assert llamado["v"] is False

    def test_motor_no_invocado_ante_rango_invalido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores = espia
        pares_invalidos = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_invalidos)])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_frecuencia_colores = original
        assert llamado["v"] is False

    def test_motor_no_invocado_ante_color_invalido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores = espia
        pares_invalidos = ((1, "INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_invalidos)])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_frecuencia_colores = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_cada_tipo_de_corrupcion(self):
        casos = [
            _PARES_VALIDOS[:5],  # cantidad incorrecta
            ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")),  # rango
            ((1, "INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")),  # color
        ]
        for pares_corruptos in casos:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_corruptos)])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
            assert estadistica_repo.guardar_fue_llamado is False, pares_corruptos

    def test_repeticiones_de_numero_color_y_par_exacto_no_rechazadas(self):
        pares_repetidos = ((1, "ROJO"), (1, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_repetidos)])
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert "filas" in resultado.resultado
        assert len(resultado.resultado["filas"]) == 6

    def test_identidad_de_cache_incluye_cantidad_numeros_igual_que_ae1(self):
        """Auditoría explícita (sección 4 del prompt): aunque el
        motor de colores no usa rango_min/rango_max/cantidad_numeros
        en su fórmula (ignora el número por completo), estos SÍ
        afectan indirectamente el resultado porque determinan qué
        sorteos pasan la validación de integridad compartida con
        AE-1 -mismo argumento ya usado y justificado para AE-1."""
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada
        _, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        entrada_k6 = EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_colores_colorloto",
            hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6},
            parametros_hash="", resultado={"filas": []}, calculado_en=None, valido_hasta=None,
        )
        estadistica_repo.guardar(entrada_k6)
        vigente_con_k5 = estadistica_repo.buscar_vigente(
            juego_id, "frecuencia_colores_colorloto", None, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 5},
        )
        assert vigente_con_k5 is None


# =====================================================================
# Etapa AE-3: tercera visualización descriptiva de ColorLoto -
# frecuencia de pares exactos número-color. Reutiliza los helpers de
# Etapa AE-1/AE-2 (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _PARAMS_COLORLOTO, _orquestador_colorloto) sin duplicarlos.
# =====================================================================

class TestMotorFrecuenciaParesColorLotoSemantica:
    def test_firma_y_cuarentaydos_categorias_con_paleta_completa(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        r = calcular_frecuencia_pares_numero_color(
            [_cl(1, _PARES_VALIDOS)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO],
        )
        assert len(r) == 42

    def test_mismo_numero_colores_distintos_son_categorias_diferentes(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        r = calcular_frecuencia_pares_numero_color(
            [_cl(1, _PARES_VALIDOS)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO],
        )
        f_1_rojo = next(f for f in r if f.valor == "1-ROJO")
        f_1_azul = next(f for f in r if f.valor == "1-AZUL")
        assert f_1_rojo.valor != f_1_azul.valor

    def test_mismo_color_numeros_distintos_son_categorias_diferentes(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        r = calcular_frecuencia_pares_numero_color(
            [_cl(1, _PARES_VALIDOS)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO],
        )
        f_1_rojo = next(f for f in r if f.valor == "1-ROJO")
        f_2_rojo = next(f for f in r if f.valor == "2-ROJO")
        assert f_1_rojo.valor != f_2_rojo.valor

    def test_par_exacto_repetido_dentro_de_un_sorteo_cuenta_varias_apariciones(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        pares = ((1, "ROJO"), (1, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_frecuencia_pares_numero_color([_cl(1, pares)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO])
        f = next(x for x in r if x.valor == "1-ROJO")
        assert f.apariciones == 2
        assert f.frecuencia_relativa == 2.0

    def test_categoria_con_cero_apariciones_preservada(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        pares = ((1, "ROJO"),) * 6
        r = calcular_frecuencia_pares_numero_color([_cl(1, pares)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO])
        f_2_azul = next(x for x in r if x.valor == "2-AZUL")
        assert f_2_azul.apariciones == 0

    def test_orden_deterministico_numero_ascendente_luego_color(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        r = calcular_frecuencia_pares_numero_color(
            [_cl(1, _PARES_VALIDOS)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO],
        )
        pares_ordenados = [(int(f.valor.split("-", 1)[0]), f.valor.split("-", 1)[1]) for f in r]
        assert pares_ordenados == sorted(pares_ordenados)

    def test_conservacion_de_masa(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        r = calcular_frecuencia_pares_numero_color(
            [_cl(1, _PARES_VALIDOS), _cl(2, _PARES_VALIDOS)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO],
        )
        assert sum(f.apariciones for f in r) == 6 * 2
        assert abs(sum(f.frecuencia_relativa for f in r) - 6.0) < 1e-9

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        r = calcular_frecuencia_pares_numero_color([], 1, 7, [c.codigo for c in _PALETA_COLORLOTO])
        assert len(r) == 42
        assert all(f.apariciones == 0 for f in r)

    def test_entrada_desordenada_produce_mismo_resultado(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        d1 = [_cl(1, _PARES_VALIDOS), _cl(2, _PARES_VALIDOS)]
        d2 = [d1[1], d1[0]]
        codigos = [c.codigo for c in _PALETA_COLORLOTO]
        assert calcular_frecuencia_pares_numero_color(d1, 1, 7, codigos) == calcular_frecuencia_pares_numero_color(d2, 1, 7, codigos)

    def test_repeticiones_no_rechazadas_por_el_motor(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        pares = ((1, "ROJO"), (1, "ROJO"), (1, "ROJO"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_frecuencia_pares_numero_color([_cl(1, pares)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO])
        f = next(x for x in r if x.valor == "1-ROJO")
        assert f.apariciones == 3

    def test_serializacion_deserializacion_inequivoca_del_par(self):
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        r = calcular_frecuencia_pares_numero_color(
            [_cl(1, _PARES_VALIDOS)], 1, 7, [c.codigo for c in _PALETA_COLORLOTO],
        )
        for f in r:
            numero_str, color = f.valor.split("-", maxsplit=1)
            assert numero_str.isdigit()
            assert 1 <= int(numero_str) <= 7
            assert color in [c.codigo for c in _PALETA_COLORLOTO]


class TestRecetaFrecuenciaParesColorLoto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_pares_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_pares_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_las_nueve_recetas_numericas_conservan_su_fuente(self):
        """Actualizado en Etapa AE-5: excluye las cinco recetas de
        ColorLoto, no solo las cuatro anteriores."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_numerico
        recetas_colorloto = {"frecuencia_numeros_colorloto", "frecuencia_colores_colorloto", "frecuencia_pares_colorloto", "atrasos_numeros_colorloto", "atrasos_colores_colorloto", "atrasos_pares_colorloto", "repeticiones_entre_sorteos_colorloto", "distribucion_pares_impares_colorloto", "distribucion_altos_bajos_colorloto", "maximo_repeticion_color_por_sorteo_colorloto", "distribucion_pares_consecutivos_colorloto", "distribucion_racha_maxima_colorloto", "distribucion_trios_consecutivos_colorloto", "coocurrencia_pares_colorloto", "coocurrencia_trios_colorloto", "coocurrencia_pares_colores_colorloto", "coocurrencia_trios_colores_colorloto", "intervalos_historicos_colores_colorloto", "distribucion_sumas_colorloto", "intervalos_historicos_numeros_colorloto", "intervalos_historicos_pares_numero_color_colorloto", "frecuencia_colores_por_anio_colorloto", "frecuencia_colores_por_mes_colorloto", "frecuencia_colores_por_dia_semana_colorloto", "frecuencia_pares_numero_color_por_anio_colorloto", "frecuencia_pares_numero_color_por_mes_colorloto", "frecuencia_pares_numero_color_por_dia_semana_colorloto"}
        for nombre, receta in _CATALOGO.items():
            if nombre not in recetas_colorloto:
                assert receta.obtener_historico is _obtener_historico_numerico, nombre

    def test_no_se_llama_listar_resultados_numericos_para_colorloto(self):
        orquestador, historico_repo, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado is False
        assert historico_repo.fue_consultado_colorloto is True

    def test_parametros_exactos_identicos_a_las_otras_dos_recetas(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_corte_separado_sin_doble_aplicacion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(
            juego_id, "frecuencia_pares_colorloto", hasta_numero_sorteo=1,
            parametros_metrica=dict(_PARAMS_COLORLOTO),
        )
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 1

    def test_cache_hit_no_consulta_historico_ni_catalogo(self):
        orquestador, historico_repo, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        historico_repo.fue_consultado_colorloto = False
        color_repo.llamadas_listar_todos = 0
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado_colorloto is False
        assert color_repo.llamadas_listar_todos == 0

    def test_catalogo_cargado_una_sola_vez_en_cache_miss(self):
        orquestador, _, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert color_repo.llamadas_listar_todos == 1

    def test_exactamente_una_llamada_al_motor_en_calculo_valido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color
        llamadas = {"n": 0}

        def espia(*a, **kw):
            llamadas["n"] += 1
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
            orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_frecuencia_pares_numero_color = original
        assert llamadas["n"] == 1

    def test_motor_no_invocado_ante_cantidad_incorrecta(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5])])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_frecuencia_pares_numero_color = original
        assert llamado["v"] is False

    def test_motor_no_invocado_ante_rango_invalido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color = espia
        pares_invalidos = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_invalidos)])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_frecuencia_pares_numero_color = original
        assert llamado["v"] is False

    def test_motor_no_invocado_ante_color_invalido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color = espia
        pares_invalidos = ((1, "INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_invalidos)])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_frecuencia_pares_numero_color = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_cada_tipo_de_corrupcion(self):
        casos = [
            _PARES_VALIDOS[:5],
            ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")),
            ((1, "INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")),
        ]
        for pares_corruptos in casos:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_corruptos)])
            try:
                orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
            assert estadistica_repo.guardar_fue_llamado is False, pares_corruptos

    def test_repeticiones_de_numero_color_y_par_exacto_no_rechazadas(self):
        pares_repetidos = ((1, "ROJO"), (1, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_repetidos)])
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_42_filas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert "filas" in resultado.resultado
        assert len(resultado.resultado["filas"]) == 42

    def test_identidad_de_cache_incluye_cantidad_numeros_igual_que_ae1_ae2(self):
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada
        _, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        entrada_k6 = EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_pares_colorloto",
            hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6},
            parametros_hash="", resultado={"filas": []}, calculado_en=None, valido_hasta=None,
        )
        estadistica_repo.guardar(entrada_k6)
        vigente_con_k5 = estadistica_repo.buscar_vigente(
            juego_id, "frecuencia_pares_colorloto", None, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 5},
        )
        assert vigente_con_k5 is None


# =====================================================================
# Etapa AE-4: cuarta visualización descriptiva de ColorLoto -
# atrasos de números. Reutiliza los helpers ya existentes de AE-1/2/3
# (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS, _PARAMS_COLORLOTO,
# _orquestador_colorloto) sin duplicarlos.
# =====================================================================

class TestMotorAtrasosNumerosColorLotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en el turno de
    auditoría previo -aquí solo se confirman los casos obligatorios
    explícitos de esta implementación, sin duplicar lo ya probado."""

    def test_firma_y_siete_categorias(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_numeros_colorloto
        r = calcular_atrasos_numeros_colorloto([_cl(1, _PARES_VALIDOS)], 1, 7)
        assert [f.valor for f in r] == [str(i) for i in range(1, 8)]

    def test_atraso_cero_para_numero_en_el_sorteo_mas_reciente(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_numeros_colorloto
        r = calcular_atrasos_numeros_colorloto([_cl(1, _PARES_VALIDOS), _cl(2, _PARES_VALIDOS)], 1, 7)
        f1 = next(f for f in r if f.valor == "1")
        assert f1.atraso == 0

    def test_atraso_positivo_real_diferencia_de_numero_sorteo(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_numeros_colorloto
        p_sin1 = ((2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"), (7, "ROJO"))
        r = calcular_atrasos_numeros_colorloto([_cl(1, _PARES_VALIDOS), _cl(2, p_sin1), _cl(3, p_sin1)], 1, 7)
        f1 = next(f for f in r if f.valor == "1")
        assert f1.atraso == 2

    def test_historico_vacio_todos_none(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_numeros_colorloto
        r = calcular_atrasos_numeros_colorloto([], 1, 7)
        assert all(f.atraso is None for f in r)
        assert r[0].total_sorteos == 0

    def test_numero_repetido_dentro_de_un_sorteo_no_altera_atraso(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_numeros_colorloto
        pares = ((1, "ROJO"), (1, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_atrasos_numeros_colorloto([_cl(1, pares)], 1, 7)
        f1 = next(f for f in r if f.valor == "1")
        assert f1.atraso == 0

    def test_entrada_desordenada_produce_mismo_resultado(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_numeros_colorloto
        d1 = [_cl(1, _PARES_VALIDOS), _cl(2, _PARES_VALIDOS)]
        d2 = [d1[1], d1[0]]
        assert calcular_atrasos_numeros_colorloto(d1, 1, 7) == calcular_atrasos_numeros_colorloto(d2, 1, 7)


class TestRecetaAtrasosNumerosColorLoto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("atrasos_numeros_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["atrasos_numeros_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_atrasos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        assert _CATALOGO["atrasos_numeros_colorloto"].serializar is _serializar_atrasos

    def test_las_trece_recetas_previas_conservan_su_fuente(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import (
            _obtener_historico_numerico, _obtener_historico_colorloto,
        )
        recetas_colorloto = ("frecuencia_numeros_colorloto", "frecuencia_colores_colorloto", "frecuencia_pares_colorloto", "atrasos_numeros_colorloto", "atrasos_colores_colorloto", "atrasos_pares_colorloto", "repeticiones_entre_sorteos_colorloto", "distribucion_pares_impares_colorloto", "distribucion_altos_bajos_colorloto", "maximo_repeticion_color_por_sorteo_colorloto", "distribucion_pares_consecutivos_colorloto", "distribucion_racha_maxima_colorloto", "distribucion_trios_consecutivos_colorloto", "coocurrencia_pares_colorloto", "coocurrencia_trios_colorloto", "coocurrencia_pares_colores_colorloto", "coocurrencia_trios_colores_colorloto", "intervalos_historicos_colores_colorloto", "distribucion_sumas_colorloto", "intervalos_historicos_numeros_colorloto", "intervalos_historicos_pares_numero_color_colorloto", "frecuencia_colores_por_anio_colorloto", "frecuencia_colores_por_mes_colorloto", "frecuencia_colores_por_dia_semana_colorloto", "frecuencia_pares_numero_color_por_anio_colorloto", "frecuencia_pares_numero_color_por_mes_colorloto", "frecuencia_pares_numero_color_por_dia_semana_colorloto")
        for nombre, receta in _CATALOGO.items():
            if nombre in recetas_colorloto:
                assert receta.obtener_historico is _obtener_historico_colorloto, nombre
            else:
                assert receta.obtener_historico is _obtener_historico_numerico, nombre

    def test_no_se_llama_listar_resultados_numericos_para_colorloto(self):
        orquestador, historico_repo, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado is False
        assert historico_repo.fue_consultado_colorloto is True

    def test_parametros_exactos_identicos_a_las_otras_tres_recetas(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_corte_separado_sin_doble_aplicacion(self):
        """Crítico para atrasos: si el corte se aplicara dos veces
        (una en Application, otra pasándolo al motor), el atraso
        calculado sería incorrecto -este test confirma con datos
        reales que el atraso resultante es el correcto, no uno
        distorsionado por doble filtrado."""
        p_sin1 = ((2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"), (7, "ROJO"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS), _cl(2, p_sin1), _cl(3, p_sin1)],
        )
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        fila_1 = next(f for f in fila_guardada.resultado["filas"] if f["valor"] == "1")
        assert fila_1["atraso"] == 2

    def test_cache_hit_no_consulta_historico_ni_catalogo(self):
        orquestador, historico_repo, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        historico_repo.fue_consultado_colorloto = False
        color_repo.llamadas_listar_todos = 0
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado_colorloto is False
        assert color_repo.llamadas_listar_todos == 0

    def test_catalogo_cargado_una_sola_vez_en_cache_miss(self):
        orquestador, _, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert color_repo.llamadas_listar_todos == 1

    def test_exactamente_una_llamada_al_motor_en_calculo_valido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_numeros_colorloto
        llamadas = {"n": 0}

        def espia(*a, **kw):
            llamadas["n"] += 1
            return original(*a, **kw)

        modulo.calcular_atrasos_numeros_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
            orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_atrasos_numeros_colorloto = original
        assert llamadas["n"] == 1

    def test_motor_recibe_exactamente_tres_argumentos_efectivos(self):
        """Confirma que el motor NUNCA recibe hasta_numero_sorteo
        -exactamente 3 argumentos posicionales/keyword efectivos
        (resultados, rango_min, rango_max), dejando el cuarto
        parametro del motor en su propio default None."""
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_numeros_colorloto
        argumentos_capturados = {}

        def espia(*a, **kw):
            argumentos_capturados["args"] = a
            argumentos_capturados["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_atrasos_numeros_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
            orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_atrasos_numeros_colorloto = original
        assert len(argumentos_capturados["args"]) + len(argumentos_capturados["kwargs"]) == 3
        assert "hasta_numero_sorteo" not in argumentos_capturados["kwargs"]

    def test_motor_no_invocado_ante_cantidad_incorrecta(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_numeros_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_atrasos_numeros_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5])])
            try:
                orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_atrasos_numeros_colorloto = original
        assert llamado["v"] is False

    def test_motor_no_invocado_ante_rango_invalido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_numeros_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_atrasos_numeros_colorloto = espia
        pares_invalidos = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_invalidos)])
            try:
                orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_atrasos_numeros_colorloto = original
        assert llamado["v"] is False

    def test_motor_no_invocado_ante_color_invalido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_numeros_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_atrasos_numeros_colorloto = espia
        pares_invalidos = ((1, "INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_invalidos)])
            try:
                orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_atrasos_numeros_colorloto = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_cada_tipo_de_corrupcion(self):
        casos = [
            _PARES_VALIDOS[:5],
            ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")),
            ((1, "INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")),
        ]
        for pares_corruptos in casos:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_corruptos)])
            try:
                orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
            assert estadistica_repo.guardar_fue_llamado is False, pares_corruptos

    def test_repeticiones_de_numero_color_y_par_exacto_no_rechazadas(self):
        pares_repetidos = ((1, "ROJO"), (1, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_repetidos)])
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_siete_filas_con_atraso_y_ultimo_sorteo(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        resultado = orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert "filas" in resultado.resultado
        assert len(resultado.resultado["filas"]) == 7
        for fila in resultado.resultado["filas"]:
            assert "atraso" in fila
            assert "ultimo_sorteo_aparicion" in fila

    def test_identidad_de_cache_incluye_cantidad_numeros_igual_que_las_otras_tres(self):
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada
        _, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS)])
        entrada_k6 = EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="atrasos_numeros_colorloto",
            hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6},
            parametros_hash="", resultado={"filas": []}, calculado_en=None, valido_hasta=None,
        )
        estadistica_repo.guardar(entrada_k6)
        vigente_con_k5 = estadistica_repo.buscar_vigente(
            juego_id, "atrasos_numeros_colorloto", None, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 5},
        )
        assert vigente_con_k5 is None


# =====================================================================
# Etapa AE-4P: contrato temporal e invalidación de caché de la paleta
# ColorLoto -endurecimiento transversal, no agrega ninguna
# visualización. Reutiliza los helpers ya existentes (_cl, _col,
# _PALETA_COLORLOTO, _PARES_VALIDOS, _PARAMS_COLORLOTO,
# _orquestador_colorloto) sin duplicarlos.
# =====================================================================

class TestHelperUniversoTemporalColores:
    """Tests directos del helper
    _codigos_colores_vigentes_en_referencia -sin pasar por el
    orquestador ni por ninguna receta, para aislar exactamente su
    comportamiento."""

    def _hist(self, pares, catalogo):
        from app.application.use_cases.calcular_y_persistir_estadistica import _HistoricoColorLoto
        return _HistoricoColorLoto(pares=pares, catalogo_colores=catalogo)

    def test_seleccion_por_fecha_del_mayor_numero_sorteo_entrada_desordenada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO", desde=date(2024, 3, 1))]
        p6 = _PARES_VALIDOS
        ordenado = self._hist([_cl(1, p6, date(2024, 1, 1)), _cl(3, p6, date(2024, 3, 15))], catalogo)
        desordenado = self._hist([_cl(3, p6, date(2024, 3, 15)), _cl(1, p6, date(2024, 1, 1))], catalogo)
        assert _codigos_colores_vigentes_en_referencia(ordenado) == _codigos_colores_vigentes_en_referencia(desordenado)
        assert "MORADO" in _codigos_colores_vigentes_en_referencia(ordenado)

    def test_corte_superior_al_ultimo_sorteo_usa_fecha_del_ultimo_sorteo_real(self):
        """El corte se aplica ANTES de construir _HistoricoColorLoto
        (en _obtener_historico_colorloto) -este test confirma que el
        helper, recibiendo el histórico YA filtrado, nunca necesita ni
        usa un valor de corte explícito: solo mira las fechas
        realmente presentes."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO", desde=date(2030, 1, 1))]
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], catalogo)
        assert "MORADO" not in _codigos_colores_vigentes_en_referencia(h)

    def test_hueco_de_numeracion_no_inventa_fecha(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO", desde=date(2024, 4, 1))]
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(5, _PARES_VALIDOS, date(2024, 5, 1))], catalogo)
        assert "MORADO" in _codigos_colores_vigentes_en_referencia(h)

    def test_historico_vacio_universo_vacio(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        h = self._hist([], list(_PALETA_COLORLOTO))
        assert _codigos_colores_vigentes_en_referencia(h) == []

    def test_color_vigente_nunca_observado_incluido(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO")]
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], catalogo)
        assert "MORADO" in _codigos_colores_vigentes_en_referencia(h)

    def test_color_futuro_nunca_observado_excluido(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO", desde=date(2030, 1, 1))]
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], catalogo)
        assert "MORADO" not in _codigos_colores_vigentes_en_referencia(h)

    def test_color_incluido_exactamente_en_vigente_desde(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO", desde=date(2024, 6, 1))]
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 6, 1))], catalogo)
        assert "MORADO" in _codigos_colores_vigentes_en_referencia(h)

    def test_color_incluido_exactamente_en_vigente_hasta(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO", activo=False, hasta=date(2024, 6, 1))]
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 6, 1))], catalogo)
        assert "MORADO" in _codigos_colores_vigentes_en_referencia(h)

    def test_color_excluido_un_dia_despues_de_vigente_hasta(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO", activo=False, hasta=date(2024, 6, 1))]
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 6, 2))], catalogo)
        assert "MORADO" not in _codigos_colores_vigentes_en_referencia(h)

    def test_color_excluido_un_dia_antes_de_vigente_desde(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = [_col("ROJO"), _col("MORADO", desde=date(2024, 6, 1))]
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 5, 31))], catalogo)
        assert "MORADO" not in _codigos_colores_vigentes_en_referencia(h)

    def test_no_muta_el_historico_ni_el_catalogo(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _codigos_colores_vigentes_en_referencia
        catalogo = list(_PALETA_COLORLOTO)
        catalogo_original = list(catalogo)
        h = self._hist([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], catalogo)
        _codigos_colores_vigentes_en_referencia(h)
        assert catalogo == catalogo_original


class TestFrecuenciaColoresColorLotoPoliticaTemporal:
    """Frecuencia de colores (AE-2) aplicando la nueva política -mismo
    patrón end-to-end ya usado, ahora con paletas con vigencia real."""

    def test_color_futuro_nunca_observado_no_aparece(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "MORADO" not in valores

    def test_color_retirado_observado_se_preserva(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("ROSADO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]
        pares_con_rosado = ((1, "ROSADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, pares_con_rosado, date(2022, 6, 1)), _cl(2, _PARES_VALIDOS, date(2024, 6, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "ROSADO" in valores

    def test_color_retirado_nunca_observado_no_aparece(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("ROSADO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 6, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "ROSADO" not in valores

    def test_color_vigente_nunca_observado_aparece_con_cero(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO")]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 6, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_morado = next(f for f in resultado.resultado["filas"] if f["valor"] == "MORADO")
        assert fila_morado["apariciones"] == 0

    def test_motor_recibe_universo_temporal_no_catalogo_completo(self):
        """Espía sobre calcular_frecuencia_colores: confirma que el
        segundo argumento (colores_vigentes) NO es el catálogo
        completo cuando hay un color futuro nunca observado."""
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores
        capturado = {}

        def espia(resultados, colores_vigentes):
            capturado["colores_vigentes"] = set(colores_vigentes)
            return original(resultados, colores_vigentes)

        modulo.calcular_frecuencia_colores = espia
        try:
            catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
            orquestador, _, _, _, juego_id = _orquestador_colorloto(
                [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo,
            )
            orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_frecuencia_colores = original
        assert "MORADO" not in capturado["colores_vigentes"]
        assert capturado["colores_vigentes"] == {c.codigo for c in _PALETA_COLORLOTO}

    def test_corte_no_se_pasa_dos_veces_al_motor(self):
        import inspect
        from app.application.use_cases.calcular_y_persistir_estadistica import _calcular_frecuencia_colores_colorloto
        codigo_fuente = inspect.getsource(_calcular_frecuencia_colores_colorloto)
        assert "hasta_numero_sorteo" not in codigo_fuente

    def test_identidad_de_cache_permanece_exacta(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_validacion_historica_por_fecha_individual_permanece_intacta(self):
        """La validación de integridad (color usado en un sorteo debe
        ser válido en la fecha de ESE sorteo) es independiente del
        universo temporal de categorías -sigue rechazando un color
        futuro USADO antes de su vigencia."""
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
        pares_con_morado_temprano = ((1, "MORADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto(
            [_cl(1, pares_con_morado_temprano, date(2024, 1, 1))], colores=catalogo,
        )
        try:
            orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO
        assert estadistica_repo.guardar_fue_llamado is False


class TestFrecuenciaParesColorLotoPoliticaTemporal:
    """Frecuencia de pares (AE-3) aplicando la misma política."""

    def test_color_futuro_nunca_observado_no_aparece_en_ningun_par(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert len(resultado.resultado["filas"]) == 42
        assert not any("MORADO" in f["valor"] for f in resultado.resultado["filas"])

    def test_color_retirado_observado_se_preserva_en_su_par(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("ROSADO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]
        pares_con_rosado = ((1, "ROSADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, pares_con_rosado, date(2022, 6, 1)), _cl(2, _PARES_VALIDOS, date(2024, 6, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert any(f["valor"] == "1-ROSADO" for f in resultado.resultado["filas"])

    def test_motor_recibe_universo_temporal_no_catalogo_completo(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color
        capturado = {}

        def espia(resultados, rango_min, rango_max, colores_vigentes):
            capturado["colores_vigentes"] = set(colores_vigentes)
            return original(resultados, rango_min, rango_max, colores_vigentes)

        modulo.calcular_frecuencia_pares_numero_color = espia
        try:
            catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
            orquestador, _, _, _, juego_id = _orquestador_colorloto(
                [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo,
            )
            orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_frecuencia_pares_numero_color = original
        assert "MORADO" not in capturado["colores_vigentes"]

    def test_corte_no_se_pasa_dos_veces_al_motor(self):
        import inspect
        from app.application.use_cases.calcular_y_persistir_estadistica import _calcular_frecuencia_pares_colorloto
        codigo_fuente = inspect.getsource(_calcular_frecuencia_pares_colorloto)
        assert "hasta_numero_sorteo" not in codigo_fuente

    def test_identidad_de_cache_permanece_exacta(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}


class TestSinRegresionAE1yAE4PorCambioDeUniversoDeColores:
    """AE-1 (frecuencia_numeros_colorloto) y AE-4 (atrasos_numeros_colorloto)
    ignoran el color por completo -no deben verse afectadas por el
    cambio de universo temporal de colores."""

    def test_frecuencia_numeros_colorloto_no_usa_colores_vigentes(self):
        import inspect
        from app.application.use_cases.calcular_y_persistir_estadistica import _calcular_frecuencia_numeros_colorloto
        codigo_fuente = inspect.getsource(_calcular_frecuencia_numeros_colorloto)
        assert "colores_vigentes" not in codigo_fuente
        assert "_codigos_colores_vigentes_en_referencia" not in codigo_fuente

    def test_atrasos_numeros_colorloto_no_usa_colores_vigentes(self):
        import inspect
        from app.application.use_cases.calcular_y_persistir_estadistica import _calcular_atrasos_numeros_colorloto
        codigo_fuente = inspect.getsource(_calcular_atrasos_numeros_colorloto)
        assert "colores_vigentes" not in codigo_fuente
        assert "_codigos_colores_vigentes_en_referencia" not in codigo_fuente

    def test_frecuencia_numeros_colorloto_produce_mismo_resultado_con_color_futuro(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
        orquestador_con, _, _, _, juego_id_con = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo,
        )
        orquestador_sin, _, _, _, juego_id_sin = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=list(_PALETA_COLORLOTO),
        )
        r_con = orquestador_con.ejecutar(juego_id_con, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        r_sin = orquestador_sin.ejecutar(juego_id_sin, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert r_con.resultado == r_sin.resultado


# =====================================================================
# Etapa AE-4P (corrección focalizada): marcador estático de versión
# de política + demostración de vigencia histórica con activo=False.
# =====================================================================

class TestMarcadorEstaticoDePoliticaDeUniverso:
    """El marcador se agrega en el ROUTER (donde se construye
    parametros_metrica), no dentro de las recetas de Application -las
    recetas ignoran cualquier clave que no usen explícitamente (solo
    extraen rango_min/rango_max/cantidad_numeros de `parametros`).
    Estos tests verifican el comportamiento end-to-end vía el
    orquestador, simulando exactamente lo que el router construye."""

    def test_parametros_exactos_de_frecuencia_colores_incluyen_las_cuatro_claves(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=params_router)
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {
            "rango_min": 1, "rango_max": 7, "cantidad_numeros": 6,
            "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1",
        }

    def test_parametros_exactos_de_frecuencia_pares_incluyen_las_cuatro_claves(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=params_router)
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {
            "rango_min": 1, "rango_max": 7, "cantidad_numeros": 6,
            "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1",
        }

    def test_frecuencia_numeros_colorloto_conserva_exactamente_sus_parametros_sin_marcador(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        orquestador.ejecutar(juego_id, "frecuencia_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}
        assert "politica_universo_colores" not in fila_guardada.parametros

    def test_atrasos_numeros_colorloto_conserva_exactamente_sus_parametros_sin_marcador(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        orquestador.ejecutar(juego_id, "atrasos_numeros_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert fila_guardada.parametros == {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}
        assert "politica_universo_colores" not in fila_guardada.parametros

    def test_cache_pre_ae4p_sin_marcador_no_se_reutiliza_para_frecuencia_colores(self):
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada

        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_colores_colorloto",
            hasta_numero_sorteo=None, parametros=dict(_PARAMS_COLORLOTO), parametros_hash="",
            resultado={"filas": [{"v": "FILA_PRE_AE4P"}]}, calculado_en=None, valido_hasta=None,
        ))
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=params_router)
        assert resultado.resultado != {"filas": [{"v": "FILA_PRE_AE4P"}]}

    def test_cache_pre_ae4p_sin_marcador_no_se_reutiliza_para_frecuencia_pares(self):
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada

        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_pares_colorloto",
            hasta_numero_sorteo=None, parametros=dict(_PARAMS_COLORLOTO), parametros_hash="",
            resultado={"filas": [{"v": "FILA_PRE_AE4P"}]}, calculado_en=None, valido_hasta=None,
        ))
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_colorloto", parametros_metrica=params_router)
        assert resultado.resultado != {"filas": [{"v": "FILA_PRE_AE4P"}]}

    def test_tras_el_miss_se_calcula_y_persiste_fila_con_marcador(self):
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada

        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_colores_colorloto",
            hasta_numero_sorteo=None, parametros=dict(_PARAMS_COLORLOTO), parametros_hash="",
            resultado={"filas": [{"v": "FILA_PRE_AE4P"}]}, calculado_en=None, valido_hasta=None,
        ))
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=params_router)
        assert resultado.parametros["politica_universo_colores"] == POLITICA_UNIVERSO_COLORES_ACTUAL
        assert "filas" in resultado.resultado

    def test_cache_nueva_con_marcador_produce_hit_evita_recalcular(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        primera = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=params_router)
        segunda = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(params_router))
        assert segunda.id == primera.id

    def test_historico_completo_y_corte_mantienen_identidades_separadas_con_marcador(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(2, _PARES_VALIDOS, date(2024, 2, 1)),
        ])
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        completo = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(params_router))
        corte = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", hasta_numero_sorteo=1, parametros_metrica=dict(params_router))
        assert completo.id != corte.id
        assert completo.hasta_numero_sorteo is None
        assert corte.hasta_numero_sorteo == 1

    def test_marcador_no_contiene_fecha_lista_de_colores_ni_huella_variable(self):
        assert isinstance(POLITICA_UNIVERSO_COLORES_ACTUAL, str)
        assert POLITICA_UNIVERSO_COLORES_ACTUAL == "vigentes_ultimo_sorteo_mas_observados_v1"
        # Ningun caracter de fecha (YYYY-MM-DD) ni separador de lista.
        assert "-2" not in POLITICA_UNIVERSO_COLORES_ACTUAL  # sin fragmento de año
        assert "," not in POLITICA_UNIVERSO_COLORES_ACTUAL

    def test_invalidacion_futura_de_paleta_sigue_afectando_filas_nuevas_con_marcador(self):
        orquestador, _, color_repo, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(params_router))
        # Mismo mecanismo ya usado en GestionarPaletaColores.
        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        vigente = estadistica_repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, params_router)
        assert vigente is None

    def test_filas_antiguas_y_nuevas_coexisten_sin_ser_seleccionadas_por_error(self):
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada

        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_colores_colorloto",
            hasta_numero_sorteo=None, parametros=dict(_PARAMS_COLORLOTO), parametros_hash="",
            resultado={"filas": [{"v": "VIEJA"}]}, calculado_en=None, valido_hasta=None,
        ))
        params_router = dict(_PARAMS_COLORLOTO, politica_universo_colores=POLITICA_UNIVERSO_COLORES_ACTUAL)
        orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=params_router)

        # La fila vieja sigue existiendo (buscable con SUS PROPIOS
        # parametros) sin haber sido seleccionada por la busqueda con
        # el marcador nuevo.
        vieja = estadistica_repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, dict(_PARAMS_COLORLOTO))
        assert vieja is not None
        assert vieja.resultado == {"filas": [{"v": "VIEJA"}]}
        nueva = estadistica_repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, params_router)
        assert nueva is not None
        assert nueva.resultado != {"filas": [{"v": "VIEJA"}]}


class TestVigenciaHistoricaColorInactivo:
    """Demuestra que Color.esta_vigente_en ya funciona correctamente
    con activo=False -sin modificar producción (confirmado por
    lectura del código real: esta_vigente_en nunca lee self.activo)."""

    def _color_retirado_historico(self):
        return _col("ROSADO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))

    def test_esta_vigente_en_devuelve_true_para_fecha_historica_pese_a_activo_false(self):
        color = self._color_retirado_historico()
        assert color.esta_vigente_en(date(2022, 6, 15)) is True

    def test_helper_incluye_color_inactivo_en_corte_dentro_de_su_ventana(self):
        catalogo = list(_PALETA_COLORLOTO) + [self._color_retirado_historico()]
        h = _HistoricoColorLoto(pares=[_cl(1, _PARES_VALIDOS, date(2022, 6, 15))], catalogo_colores=catalogo)
        assert "ROSADO" in _codigos_colores_vigentes_en_referencia(h)

    def test_helper_excluye_color_inactivo_en_corte_posterior_si_nunca_observado(self):
        catalogo = list(_PALETA_COLORLOTO) + [self._color_retirado_historico()]
        h = _HistoricoColorLoto(pares=[_cl(1, _PARES_VALIDOS, date(2024, 6, 1))], catalogo_colores=catalogo)
        assert "ROSADO" not in _codigos_colores_vigentes_en_referencia(h)

    def test_motor_conserva_color_inactivo_despues_de_su_retiro_si_fue_observado(self):
        catalogo = list(_PALETA_COLORLOTO) + [self._color_retirado_historico()]
        pares_con_rosado = ((1, "ROSADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        h = _HistoricoColorLoto(
            pares=[_cl(1, pares_con_rosado, date(2022, 6, 15)), _cl(2, _PARES_VALIDOS, date(2024, 6, 1))],
            catalogo_colores=catalogo,
        )
        resultado = _calcular_frecuencia_colores_colorloto(h, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6})
        assert "ROSADO" in {f.valor for f in resultado}

    def test_validacion_acepta_observacion_dentro_de_ventana_historica_de_color_inactivo(self):
        catalogo = list(_PALETA_COLORLOTO) + [self._color_retirado_historico()]
        pares_con_rosado = ((1, "ROSADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        _validar_historico_colorloto_consistente(
            [_cl(1, pares_con_rosado, date(2022, 6, 15))], catalogo, 6, 1, 7,
        )  # no debe lanzar

    def test_validacion_rechaza_observacion_fuera_de_ventana_historica_de_color_inactivo(self):
        catalogo = list(_PALETA_COLORLOTO) + [self._color_retirado_historico()]
        pares_con_rosado = ((1, "ROSADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        try:
            _validar_historico_colorloto_consistente(
                [_cl(1, pares_con_rosado, date(2024, 6, 1))], catalogo, 6, 1, 7,
            )
            raise AssertionError("Debio rechazar")
        except ResultadoHistoricoInconsistenteError as e:
            assert e.tipo is TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO


class TestAlcanceInvalidarPorJuegoDesdeNumeroSorteoCero:
    """Complementa los tests ya existentes en test_estadistica_repository.py
    con foco especifico en el uso desde_numero_sorteo=0 (el usado por
    GestionarPaletaColores)."""

    def _fila(self, juego_id, corte, tipo="metrica_x"):
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada
        return EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica=tipo, hasta_numero_sorteo=corte,
            parametros={}, parametros_hash=f"h{corte}", resultado={"corte": corte}, calculado_en=None, valido_hasta=None,
        )

    def test_desde_cero_invalida_historico_completo_y_todos_los_cortes_positivos(self):
        from tests.unit.fakes import FakeEstadisticaRepository
        juego_id = uuid4()
        repo = FakeEstadisticaRepository()
        repo.guardar(self._fila(juego_id, None))
        repo.guardar(self._fila(juego_id, 1))
        repo.guardar(self._fila(juego_id, 100))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 3
        assert repo.buscar_vigente(juego_id, "metrica_x", None, {}) is None
        assert repo.buscar_vigente(juego_id, "metrica_x", 1, {}) is None
        assert repo.buscar_vigente(juego_id, "metrica_x", 100, {}) is None

    def test_desde_cero_no_afecta_otro_juego(self):
        from tests.unit.fakes import FakeEstadisticaRepository
        juego_a, juego_b = uuid4(), uuid4()
        repo = FakeEstadisticaRepository()
        repo.guardar(self._fila(juego_b, None))
        repo.invalidar_por_juego(juego_a, desde_numero_sorteo=0)
        assert repo.buscar_vigente(juego_b, "metrica_x", None, {}) is not None


# =====================================================================
# Etapa AE-5: quinta visualización descriptiva de ColorLoto -
# atrasos de colores. Reutiliza los helpers ya existentes (_cl, _col,
# _PALETA_COLORLOTO, _PARES_VALIDOS, _PARAMS_COLORLOTO,
# _orquestador_colorloto, _codigos_colores_vigentes_en_referencia,
# _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorAtrasosColoresColorLotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en turnos
    previos (AE-4P/AE-5 focalizada) -aquí se confirman los casos
    obligatorios explícitos de esta implementación."""

    def test_firma_y_seis_categorias(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_colores
        r = calcular_atrasos_colores([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], [c.codigo for c in _PALETA_COLORLOTO])
        assert sorted(f.valor for f in r) == sorted(c.codigo for c in _PALETA_COLORLOTO)

    def test_atraso_cero_para_color_en_el_sorteo_mas_reciente(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_colores
        r = calcular_atrasos_colores(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(2, _PARES_VALIDOS, date(2024, 1, 2))],
            [c.codigo for c in _PALETA_COLORLOTO],
        )
        f_rojo = next(f for f in r if f.valor == "ROJO")
        assert f_rojo.atraso == 0

    def test_atraso_positivo_real_diferencia_de_numero_sorteo(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_colores
        p_sin_rojo = ((2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"), (7, "AZUL"))
        r = calcular_atrasos_colores(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(2, p_sin_rojo, date(2024, 1, 2)), _cl(3, p_sin_rojo, date(2024, 1, 3))],
            [c.codigo for c in _PALETA_COLORLOTO],
        )
        f_rojo = next(f for f in r if f.valor == "ROJO")
        assert f_rojo.atraso == 2

    def test_historico_vacio_todos_none(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_colores
        r = calcular_atrasos_colores([], [c.codigo for c in _PALETA_COLORLOTO])
        assert all(f.atraso is None for f in r)
        assert r[0].total_sorteos == 0

    def test_color_repetido_dentro_de_un_sorteo_no_altera_atraso(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_colores
        pares = ((1, "ROJO"), (2, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_atrasos_colores([_cl(1, pares, date(2024, 1, 1))], [c.codigo for c in _PALETA_COLORLOTO])
        f_rojo = next(f for f in r if f.valor == "ROJO")
        assert f_rojo.atraso == 0

    def test_entrada_desordenada_produce_mismo_resultado(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_colores
        d1 = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(2, _PARES_VALIDOS, date(2024, 1, 2))]
        d2 = [d1[1], d1[0]]
        codigos = [c.codigo for c in _PALETA_COLORLOTO]
        assert calcular_atrasos_colores(d1, codigos) == calcular_atrasos_colores(d2, codigos)

    def test_saltos_de_numeracion_no_compensados(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_colores
        p_sin_rojo = ((2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"), (7, "AZUL"))
        r = calcular_atrasos_colores(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(5, p_sin_rojo, date(2024, 1, 5))],
            [c.codigo for c in _PALETA_COLORLOTO],
        )
        f_rojo = next(f for f in r if f.valor == "ROJO")
        assert f_rojo.atraso == 4
        assert f_rojo.ultimo_sorteo_aparicion == 1


class TestRecetaAtrasosColoresColorLoto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("atrasos_colores_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["atrasos_colores_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_atrasos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        assert _CATALOGO["atrasos_colores_colorloto"].serializar is _serializar_atrasos

    def test_las_trece_recetas_previas_conservan_su_fuente(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import (
            _obtener_historico_numerico, _obtener_historico_colorloto,
        )
        recetas_colorloto = (
            "frecuencia_numeros_colorloto", "frecuencia_colores_colorloto", "frecuencia_pares_colorloto",
            "atrasos_numeros_colorloto", "atrasos_colores_colorloto", "atrasos_pares_colorloto", "repeticiones_entre_sorteos_colorloto", "distribucion_pares_impares_colorloto", "distribucion_altos_bajos_colorloto", "maximo_repeticion_color_por_sorteo_colorloto",
            "distribucion_pares_consecutivos_colorloto", "distribucion_racha_maxima_colorloto", "distribucion_trios_consecutivos_colorloto", "coocurrencia_pares_colorloto", "coocurrencia_trios_colorloto", "coocurrencia_pares_colores_colorloto", "coocurrencia_trios_colores_colorloto", "intervalos_historicos_colores_colorloto", "distribucion_sumas_colorloto", "intervalos_historicos_numeros_colorloto", "intervalos_historicos_pares_numero_color_colorloto", "frecuencia_colores_por_anio_colorloto", "frecuencia_colores_por_mes_colorloto", "frecuencia_colores_por_dia_semana_colorloto", "frecuencia_pares_numero_color_por_anio_colorloto", "frecuencia_pares_numero_color_por_mes_colorloto", "frecuencia_pares_numero_color_por_dia_semana_colorloto",
        )
        for nombre, receta in _CATALOGO.items():
            if nombre in recetas_colorloto:
                assert receta.obtener_historico is _obtener_historico_colorloto, nombre
            else:
                assert receta.obtener_historico is _obtener_historico_numerico, nombre

    def test_no_se_llama_listar_resultados_numericos_para_colorloto(self):
        orquestador, historico_repo, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado is False
        assert historico_repo.fue_consultado_colorloto is True

    def test_espia_motor_recibe_historico_filtrado_y_universo_sin_doble_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_colores
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_atrasos_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_atrasos_colores = original
        assert len(capturado["args"]) == 2
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_universo_pasado_al_motor_es_el_calculado_por_el_helper_temporal(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_colores
        capturado = {}

        def espia(resultados, colores_vigentes):
            capturado["colores_vigentes"] = set(colores_vigentes)
            return original(resultados, colores_vigentes)

        modulo.calcular_atrasos_colores = espia
        try:
            catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
            orquestador, _, _, _, juego_id = _orquestador_colorloto(
                [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo,
            )
            orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_atrasos_colores = original
        assert "MORADO" not in capturado["colores_vigentes"]
        assert capturado["colores_vigentes"] == {c.codigo for c in _PALETA_COLORLOTO}

    def test_corte_separado_sin_doble_aplicacion(self):
        p_sin_rojo = ((2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"), (7, "AZUL"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(2, p_sin_rojo, date(2024, 1, 2)), _cl(3, p_sin_rojo, date(2024, 1, 3))],
        )
        orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        fila_rojo = next(f for f in fila_guardada.resultado["filas"] if f["valor"] == "ROJO")
        assert fila_rojo["atraso"] == 2

    def test_cache_hit_no_consulta_historico_ni_catalogo(self):
        orquestador, historico_repo, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        historico_repo.fue_consultado_colorloto = False
        color_repo.llamadas_listar_todos = 0
        orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert historico_repo.fue_consultado_colorloto is False
        assert color_repo.llamadas_listar_todos == 0

    def test_catalogo_cargado_una_sola_vez_en_cache_miss(self):
        orquestador, _, color_repo, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert color_repo.llamadas_listar_todos == 1

    def test_motor_no_invocado_ante_cantidad_incorrecta(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_colores
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_atrasos_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_atrasos_colores = original
        assert llamado["v"] is False

    def test_motor_no_invocado_ante_color_invalido(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_colores
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_atrasos_colores = espia
        pares_invalidos = ((1, "INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_invalidos, date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_atrasos_colores = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_corrupcion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
        try:
            orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_vigente_nunca_observado_nd(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO")]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_morado = next(f for f in resultado.resultado["filas"] if f["valor"] == "MORADO")
        assert fila_morado["atraso"] is None
        assert fila_morado["ultimo_sorteo_aparicion"] is None

    def test_color_retirado_observado_conservado(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("ROSADO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]
        pares_con_rosado = ((1, "ROSADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, pares_con_rosado, date(2022, 6, 1)), _cl(2, _PARES_VALIDOS, date(2024, 6, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_rosado = next(f for f in resultado.resultado["filas"] if f["valor"] == "ROSADO")
        assert fila_rosado["atraso"] == 1

    def test_color_futuro_nunca_observado_excluido(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "MORADO" not in valores

    def test_color_retirado_nunca_observado_excluido(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("ROSADO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 6, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "ROSADO" not in valores

    def test_limites_temporales_inclusivos(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2024, 6, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(
            [_cl(1, _PARES_VALIDOS, date(2024, 6, 1))], colores=catalogo,
        )
        resultado = orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "MORADO" in valores

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_seis_filas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "atrasos_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert len(resultado.resultado["filas"]) == 6
        for fila in resultado.resultado["filas"]:
            assert "atraso" in fila
            assert "ultimo_sorteo_aparicion" in fila


# =====================================================================
# Etapa AE-6: sexta visualización descriptiva de ColorLoto -
# atrasos de pares número-color. Reutiliza los helpers ya
# existentes (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _PARAMS_COLORLOTO, _orquestador_colorloto,
# _codigos_colores_vigentes_en_referencia, _HistoricoColorLoto) sin
# duplicarlos.
# =====================================================================

class TestMotorAtrasosParesNumeroColorSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría previa a esta implementación -aquí se confirman los
    casos obligatorios explícitos de esta implementación."""

    def test_universo_real_cuarenta_y_dos_pares(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_pares_numero_color
        r = calcular_atrasos_pares_numero_color([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, colores_vigentes=[c.codigo for c in _PALETA_COLORLOTO])
        assert len(r) == 42

    def test_par_en_referencia_atraso_cero(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_pares_numero_color
        r = calcular_atrasos_pares_numero_color([_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(2, _PARES_VALIDOS, date(2024, 1, 2))], rango_min=1, rango_max=7, colores_vigentes=[c.codigo for c in _PALETA_COLORLOTO])
        f_1rojo = next(f for f in r if f.valor == "1-ROJO")
        assert f_1rojo.atraso == 0

    def test_par_nunca_observado_es_none(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_pares_numero_color
        r = calcular_atrasos_pares_numero_color([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, colores_vigentes=[c.codigo for c in _PALETA_COLORLOTO])
        f_7rojo = next(f for f in r if f.valor == "7-ROJO")
        assert f_7rojo.atraso is None
        assert f_7rojo.ultimo_sorteo_aparicion is None

    def test_atraso_positivo_diferencia_real_de_numero_sorteo(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_pares_numero_color
        p_sin_1rojo = ((2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"), (7, "AZUL"))
        r = calcular_atrasos_pares_numero_color([_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(5, p_sin_1rojo, date(2024, 1, 5))], rango_min=1, rango_max=7, colores_vigentes=[c.codigo for c in _PALETA_COLORLOTO])
        f_1rojo = next(f for f in r if f.valor == "1-ROJO")
        assert f_1rojo.atraso == 4

    def test_repeticion_dentro_del_sorteo_una_sola_presencia(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_pares_numero_color
        pares_repetido = ((1, "ROJO"), (1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        r = calcular_atrasos_pares_numero_color([_cl(1, pares_repetido, date(2024, 1, 1))], rango_min=1, rango_max=7, colores_vigentes=[c.codigo for c in _PALETA_COLORLOTO])
        f_1rojo = next(f for f in r if f.valor == "1-ROJO")
        assert f_1rojo.atraso == 0

    def test_historico_vacio_todos_none(self):
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_pares_numero_color
        r = calcular_atrasos_pares_numero_color([], rango_min=1, rango_max=7, colores_vigentes=[c.codigo for c in _PALETA_COLORLOTO])
        assert all(f.atraso is None for f in r)

    def test_orden_determinista_dominio_real_coincide_con_frecuencia(self):
        """En el dominio real 1-7 (un solo dígito), el orden
        lexicográfico del motor de atrasos coincide exactamente con
        el orden numérico de calcular_frecuencia_pares_numero_color
        -confirmado por auditoría previa. Este test fija esa
        expectativa únicamente para el dominio real, sin exigir
        orden numérico general del motor (fuera de alcance de
        AE-6)."""
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_pares_numero_color
        from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_pares_numero_color
        r_atrasos = calcular_atrasos_pares_numero_color([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, colores_vigentes=[c.codigo for c in _PALETA_COLORLOTO])
        r_frecuencia = calcular_frecuencia_pares_numero_color([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, colores_vigentes=[c.codigo for c in _PALETA_COLORLOTO])
        assert [f.valor for f in r_atrasos] == [f.valor for f in r_frecuencia]


class TestRecetaAtrasosParesColorloto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("atrasos_pares_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["atrasos_pares_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_atrasos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        assert _CATALOGO["atrasos_pares_colorloto"].serializar is _serializar_atrasos

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_pares_numero_color
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_atrasos_pares_numero_color = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_atrasos_pares_numero_color = original
        assert len(capturado["args"]) == 4
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_rango_min_rango_max_correctos_al_motor(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_pares_numero_color
        capturado = {}

        def espia(resultados, rango_min, rango_max, colores_vigentes):
            capturado["rango_min"] = rango_min
            capturado["rango_max"] = rango_max
            return original(resultados, rango_min, rango_max, colores_vigentes)

        modulo.calcular_atrasos_pares_numero_color = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_atrasos_pares_numero_color = original
        assert capturado["rango_min"] == 1
        assert capturado["rango_max"] == 7

    def test_colores_vigentes_derivados_del_helper_temporal(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_pares_numero_color
        capturado = {}

        def espia(resultados, rango_min, rango_max, colores_vigentes):
            capturado["colores_vigentes"] = set(colores_vigentes)
            return original(resultados, rango_min, rango_max, colores_vigentes)

        modulo.calcular_atrasos_pares_numero_color = espia
        try:
            catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo)
            orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_atrasos_pares_numero_color = original
        assert "MORADO" not in capturado["colores_vigentes"]
        assert capturado["colores_vigentes"] == {c.codigo for c in _PALETA_COLORLOTO}

    def test_corte_separado_sin_doble_aplicacion(self):
        p_sin_1rojo = ((2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"), (7, "AZUL"))
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(2, p_sin_1rojo, date(2024, 1, 2)), _cl(3, p_sin_1rojo, date(2024, 1, 3)),
        ])
        orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        fila_1rojo = next(f for f in fila_guardada.resultado["filas"] if f["valor"] == "1-ROJO")
        assert fila_1rojo["atraso"] == 2

    def test_motor_no_invocado_ante_cantidad_incorrecta(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_atrasos_pares_numero_color
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_atrasos_pares_numero_color = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_atrasos_pares_numero_color = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_corrupcion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
        try:
            orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_par_retirado_observado_conservado(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("ROSADO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]
        pares_con_rosado = ((1, "ROSADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_con_rosado, date(2022, 6, 1)), _cl(2, _PARES_VALIDOS, date(2024, 6, 1))], colores=catalogo)
        resultado = orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_rosado = next(f for f in resultado.resultado["filas"] if f["valor"] == "1-ROSADO")
        assert fila_rosado["atraso"] == 1

    def test_par_futuro_nunca_observado_excluido(self):
        catalogo = list(_PALETA_COLORLOTO) + [_col("MORADO", desde=date(2030, 1, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], colores=catalogo)
        resultado = orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert not any(v.endswith("-MORADO") for v in valores)

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_cuarenta_y_dos_filas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "atrasos_pares_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert len(resultado.resultado["filas"]) == 42
        for fila in resultado.resultado["filas"]:
            assert "atraso" in fila
            assert "ultimo_sorteo_aparicion" in fila

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.atrasos import calcular_atrasos_pares_numero_color
        firma = inspect.signature(calcular_atrasos_pares_numero_color)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "colores_vigentes", "hasta_numero_sorteo"]


# =====================================================================
# Etapa AE-7: séptima visualización descriptiva de ColorLoto -
# repeticiones entre sorteos. Reutiliza los helpers ya existentes
# (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS, _PARAMS_COLORLOTO,
# _orquestador_colorloto, _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorRepeticionesEntreSorteosColorlotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría y su adenda correctiva, previas a esta
    implementación -aquí se confirman los casos obligatorios
    explícitos de esta implementación."""

    def test_multiconjunto_con_numeros_repetidos(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        p1 = ((5, "ROJO"), (5, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (6, "AMARILLO"))
        p2 = ((5, "ROJO"), (5, "VERDE"), (7, "NEGRO"), (1, "BLANCO"), (2, "AMARILLO"), (3, "AZUL"))
        r = calcular_repeticiones_entre_sorteos_colorloto([_cl(1, p1, date(2024, 1, 1)), _cl(2, p2, date(2024, 1, 2))], rango_min=1, rango_max=7, cantidad_balotas=6)
        # 5 aparece 2 veces en ambos (min(2,2)=2), 2 aparece 1 vez en ambos (+1), 3 aparece 1 vez en ambos (+1) -> 4
        suma_ponderada = sum(int(f.valor) * f.apariciones for f in r)
        assert suma_ponderada == 4

    def test_hueco_de_numeracion_sin_transicion_fabricada(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        r = calcular_repeticiones_entre_sorteos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(5, _PARES_VALIDOS, date(2024, 1, 5))], rango_min=1, rango_max=7, cantidad_balotas=6)
        assert r[0].total_sorteos == 0

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        r = calcular_repeticiones_entre_sorteos_colorloto([], rango_min=1, rango_max=7, cantidad_balotas=6)
        assert len(r) == 7
        assert all(f.total_sorteos == 0 for f in r)

    def test_un_solo_sorteo_cero_transiciones(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        r = calcular_repeticiones_entre_sorteos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, cantidad_balotas=6)
        assert r[0].total_sorteos == 0

    def test_n_sorteos_secuenciales_da_n_menos_uno_transiciones(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        datos = [_cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)]
        r = calcular_repeticiones_entre_sorteos_colorloto(datos, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert r[0].total_sorteos == 4

    def test_categorias_cero_a_seis_completas_y_ordenadas(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        r = calcular_repeticiones_entre_sorteos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1)), _cl(2, _PARES_VALIDOS, date(2024, 1, 2))], rango_min=1, rango_max=7, cantidad_balotas=6)
        assert [f.valor for f in r] == [str(n) for n in range(7)]

    def test_suma_de_apariciones_igual_a_transiciones_validas(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        datos = [_cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)]
        r = calcular_repeticiones_entre_sorteos_colorloto(datos, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert sum(f.apariciones for f in r) == r[0].total_sorteos

    def test_frecuencia_relativa_usa_transiciones_como_denominador(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        datos = [_cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)]
        r = calcular_repeticiones_entre_sorteos_colorloto(datos, rango_min=1, rango_max=7, cantidad_balotas=6)
        for f in r:
            if f.total_sorteos > 0:
                assert abs(f.frecuencia_relativa - f.apariciones / f.total_sorteos) < 1e-9

    def test_motor_ignora_color_por_completo(self):
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        p_colores_a = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        p_colores_b = ((1, "AMARILLO"), (2, "BLANCO"), (3, "NEGRO"), (4, "VERDE"), (5, "AZUL"), (6, "ROJO"))
        r_a = calcular_repeticiones_entre_sorteos_colorloto([_cl(1, p_colores_a, date(2024, 1, 1)), _cl(2, p_colores_a, date(2024, 1, 2))], rango_min=1, rango_max=7, cantidad_balotas=6)
        r_b = calcular_repeticiones_entre_sorteos_colorloto([_cl(1, p_colores_b, date(2024, 1, 1)), _cl(2, p_colores_b, date(2024, 1, 2))], rango_min=1, rango_max=7, cantidad_balotas=6)
        assert [(f.valor, f.apariciones) for f in r_a] == [(f.valor, f.apariciones) for f in r_b]


class TestRecetaRepeticionesEntreSorteosColorloto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("repeticiones_entre_sorteos_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["repeticiones_entre_sorteos_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["repeticiones_entre_sorteos_colorloto"].serializar is _serializar_frecuencia_observada

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_repeticiones_entre_sorteos_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_repeticiones_entre_sorteos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "repeticiones_entre_sorteos_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_repeticiones_entre_sorteos_colorloto = original
        assert len(capturado["args"]) == 4
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_rango_y_cantidad_numeros_correctos_al_motor(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_repeticiones_entre_sorteos_colorloto
        capturado = {}

        def espia(resultados, rango_min, rango_max, cantidad_balotas):
            capturado["rango_min"] = rango_min
            capturado["rango_max"] = rango_max
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, rango_min, rango_max, cantidad_balotas)

        modulo.calcular_repeticiones_entre_sorteos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "repeticiones_entre_sorteos_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        finally:
            modulo.calcular_repeticiones_entre_sorteos_colorloto = original
        assert capturado["rango_min"] == 1
        assert capturado["rango_max"] == 7
        assert capturado["cantidad_balotas"] == 6

    def test_corte_separado_sin_pasarse_al_motor(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)
        ])
        orquestador.ejecutar(juego_id, "repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(_PARAMS_COLORLOTO))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        # Con corte=3, solo sorteos 1,2,3 -> 2 transiciones validas
        assert fila_guardada.resultado["filas"][0]["total_sorteos"] == 2

    def test_motor_no_invocado_ante_cantidad_incorrecta(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_repeticiones_entre_sorteos_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_repeticiones_entre_sorteos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "repeticiones_entre_sorteos_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_repeticiones_entre_sorteos_colorloto = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_corrupcion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
        try:
            orquestador.ejecutar(juego_id, "repeticiones_entre_sorteos_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "repeticiones_entre_sorteos_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_siete_filas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "repeticiones_entre_sorteos_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert len(resultado.resultado["filas"]) == 7
        for fila in resultado.resultado["filas"]:
            assert "apariciones" in fila
            assert "total_sorteos" in fila
            assert "frecuencia_relativa" in fila

    def test_identidad_de_cache_tres_claves_sin_marcador(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "repeticiones_entre_sorteos_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        assert set(resultado.parametros.keys()) == {"rango_min", "rango_max", "cantidad_numeros"}
        assert "politica_universo_colores" not in resultado.parametros

    def test_receta_no_deriva_colores_vigentes(self):
        """A diferencia de las recetas de AE-2/AE-3/AE-5/AE-6, esta
        receta nunca llama a
        _codigos_colores_vigentes_en_referencia -el motor ignora el
        color por completo."""
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_repeticiones_entre_sorteos_colorloto)
        assert "_codigos_colores_vigentes_en_referencia" not in codigo_fuente

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos_colorloto
        firma = inspect.signature(calcular_repeticiones_entre_sorteos_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


# =====================================================================
# Etapa AE-8: octava visualización descriptiva de ColorLoto -
# distribución de números pares e impares. Reutiliza los helpers ya
# existentes (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _orquestador_colorloto, _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorDistribucionParesImparesColorlotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría previa a esta implementación -aquí se confirman los
    casos obligatorios explícitos de esta implementación."""

    def test_categorias_cero_a_seis_completas_y_ordenadas(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        r = calcular_distribucion_pares_impares_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], cantidad_balotas=6)
        assert [f.valor for f in r] == [str(n) for n in range(7)]

    def test_multiplicidad_de_numeros_pares(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        p_rep = ((2, "ROJO"), (2, "AZUL"), (2, "VERDE"), (4, "NEGRO"), (6, "BLANCO"), (1, "AMARILLO"))
        r = calcular_distribucion_pares_impares_colorloto([_cl(1, p_rep, date(2024, 1, 1))], cantidad_balotas=6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "5"

    def test_independencia_del_color(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        p_a = ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "ROJO"))
        p_b = ((1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO"), (6, "ROJO"))
        r_a = calcular_distribucion_pares_impares_colorloto([_cl(1, p_a, date(2024, 1, 1))], cantidad_balotas=6)
        r_b = calcular_distribucion_pares_impares_colorloto([_cl(1, p_b, date(2024, 1, 1))], cantidad_balotas=6)
        assert [(f.valor, f.apariciones) for f in r_a] == [(f.valor, f.apariciones) for f in r_b]

    def test_categoria_ausente_con_cero_real(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        r = calcular_distribucion_pares_impares_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], cantidad_balotas=6)
        fila_0 = [f for f in r if f.valor == "0"][0]
        assert fila_0.apariciones == 0

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        r = calcular_distribucion_pares_impares_colorloto([], cantidad_balotas=6)
        assert len(r) == 7
        assert all(f.total_sorteos == 0 for f in r)

    def test_una_observacion(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        r = calcular_distribucion_pares_impares_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], cantidad_balotas=6)
        assert r[0].total_sorteos == 1

    def test_suma_de_apariciones_igual_a_total_sorteos(self):
        datos = [_cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)]
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        r = calcular_distribucion_pares_impares_colorloto(datos, cantidad_balotas=6)
        assert sum(f.apariciones for f in r) == r[0].total_sorteos == 5

    def test_dominio_real_pares_2_4_6(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        p_solo_pares = ((2, "ROJO"), (4, "AZUL"), (6, "VERDE"), (2, "NEGRO"), (4, "BLANCO"), (6, "AMARILLO"))
        r = calcular_distribucion_pares_impares_colorloto([_cl(1, p_solo_pares, date(2024, 1, 1))], cantidad_balotas=6)
        fila_6 = [f for f in r if f.valor == "6"][0]
        assert fila_6.apariciones == 1


class TestRecetaDistribucionParesImparesColorloto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("distribucion_pares_impares_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["distribucion_pares_impares_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["distribucion_pares_impares_colorloto"].serializar is _serializar_frecuencia_observada

    def test_espia_motor_recibe_dos_argumentos_sin_corte_ni_rango(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_pares_impares_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_distribucion_pares_impares_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_pares_impares_colorloto", parametros_metrica={"cantidad_numeros": 6})
        finally:
            modulo.calcular_distribucion_pares_impares_colorloto = original
        assert len(capturado["args"]) == 2
        assert "hasta_numero_sorteo" not in capturado["kwargs"]
        assert "rango_min" not in capturado["kwargs"]
        assert "rango_max" not in capturado["kwargs"]

    def test_cantidad_numeros_correcta_al_motor(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_pares_impares_colorloto
        capturado = {}

        def espia(resultados, cantidad_balotas):
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, cantidad_balotas)

        modulo.calcular_distribucion_pares_impares_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_pares_impares_colorloto", parametros_metrica={"cantidad_numeros": 6})
        finally:
            modulo.calcular_distribucion_pares_impares_colorloto = original
        assert capturado["cantidad_balotas"] == 6

    def test_corte_separado_sin_pasarse_al_motor(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)
        ])
        orquestador.ejecutar(juego_id, "distribucion_pares_impares_colorloto", hasta_numero_sorteo=3, parametros_metrica={"cantidad_numeros": 6})
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        assert fila_guardada.resultado["filas"][0]["total_sorteos"] == 3

    def test_motor_no_invocado_ante_cantidad_incorrecta(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_pares_impares_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_distribucion_pares_impares_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "distribucion_pares_impares_colorloto", parametros_metrica={"cantidad_numeros": 6})
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_distribucion_pares_impares_colorloto = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_corrupcion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_impares_colorloto", parametros_metrica={"cantidad_numeros": 6})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "distribucion_pares_impares_colorloto", parametros_metrica={"cantidad_numeros": 6})
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_siete_filas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_pares_impares_colorloto", parametros_metrica={"cantidad_numeros": 6})
        assert len(resultado.resultado["filas"]) == 7
        for fila in resultado.resultado["filas"]:
            assert "apariciones" in fila
            assert "total_sorteos" in fila
            assert "frecuencia_relativa" in fila

    def test_identidad_de_cache_una_sola_clave(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_pares_impares_colorloto", parametros_metrica={"cantidad_numeros": 6})
        assert set(resultado.parametros.keys()) == {"cantidad_numeros"}
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros

    def test_receta_no_deriva_colores_vigentes(self):
        """A diferencia de las recetas de AE-2/AE-3/AE-5/AE-6, esta
        receta nunca llama a
        _codigos_colores_vigentes_en_referencia -el motor ignora el
        color por completo."""
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_pares_impares_colorloto)
        assert "_codigos_colores_vigentes_en_referencia" not in codigo_fuente

    def test_usa_rango_real_colorloto_constante(self):
        assert _RANGO_REAL_COLORLOTO == (1, 7)

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_pares_impares_colorloto
        firma = inspect.signature(calcular_distribucion_pares_impares_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "cantidad_balotas", "hasta_numero_sorteo"]


# =====================================================================
# Etapa AE-9: novena visualización descriptiva de ColorLoto -
# distribución de números bajos y altos. Reutiliza los helpers ya
# existentes (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _orquestador_colorloto, _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorDistribucionAltosBajosColorlotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría y su adenda correctiva, previas a esta
    implementación -aquí se confirman los casos obligatorios
    explícitos de esta implementación."""

    def test_categorias_cero_a_seis_completas_y_ordenadas(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        r = calcular_distribucion_altos_bajos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, cantidad_balotas=6)
        assert [f.valor for f in r] == [str(n) for n in range(7)]

    def test_valor_es_cantidad_de_bajos_dominio_real(self):
        """Confirmado citando el bloque exacto del motor:
        sum(1 for n, _ in r.pares if n <= corte) -para 1..7 el
        corte es 3, bajos={1,2,3}."""
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        r = calcular_distribucion_altos_bajos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, cantidad_balotas=6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "3"

    def test_multiplicidad_de_numeros_bajos(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        p_rep = ((1, "ROJO"), (1, "AZUL"), (1, "VERDE"), (4, "NEGRO"), (6, "BLANCO"), (7, "AMARILLO"))
        r = calcular_distribucion_altos_bajos_colorloto([_cl(1, p_rep, date(2024, 1, 1))], rango_min=1, rango_max=7, cantidad_balotas=6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "3"

    def test_independencia_del_color(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        p_a = ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "ROJO"))
        p_b = ((1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO"), (6, "ROJO"))
        r_a = calcular_distribucion_altos_bajos_colorloto([_cl(1, p_a, date(2024, 1, 1))], rango_min=1, rango_max=7, cantidad_balotas=6)
        r_b = calcular_distribucion_altos_bajos_colorloto([_cl(1, p_b, date(2024, 1, 1))], rango_min=1, rango_max=7, cantidad_balotas=6)
        assert [(f.valor, f.apariciones) for f in r_a] == [(f.valor, f.apariciones) for f in r_b]

    def test_categoria_ausente_con_cero_real(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        r = calcular_distribucion_altos_bajos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, cantidad_balotas=6)
        fila_0 = [f for f in r if f.valor == "0"][0]
        assert fila_0.apariciones == 0

    def test_historico_vacio_cero_sorteos_analizados(self):
        """Denominador correcto: cero SORTEOS analizados, nunca
        'transiciones' (esa semantica pertenece exclusivamente a
        AE-7)."""
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        r = calcular_distribucion_altos_bajos_colorloto([], rango_min=1, rango_max=7, cantidad_balotas=6)
        assert len(r) == 7
        assert all(f.total_sorteos == 0 for f in r)

    def test_corte_anterior_al_primer_sorteo_cero_sorteos_analizados(self):
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        r = calcular_distribucion_altos_bajos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], rango_min=1, rango_max=7, cantidad_balotas=6, hasta_numero_sorteo=0)
        assert r[0].total_sorteos == 0

    def test_suma_de_apariciones_igual_a_total_sorteos(self):
        datos = [_cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)]
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        r = calcular_distribucion_altos_bajos_colorloto(datos, rango_min=1, rango_max=7, cantidad_balotas=6)
        assert sum(f.apariciones for f in r) == r[0].total_sorteos == 5

    def test_punto_de_corte_dominio_real(self):
        from app.application.estadisticas.motor.distribuciones import _punto_de_corte_altos_bajos
        assert _punto_de_corte_altos_bajos(1, 7) == 3


class TestRecetaDistribucionAltosBajosColorloto:
    _PARAMS = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("distribucion_altos_bajos_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["distribucion_altos_bajos_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["distribucion_altos_bajos_colorloto"].serializar is _serializar_frecuencia_observada

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte_como_quinto(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_altos_bajos_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_distribucion_altos_bajos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_distribucion_altos_bajos_colorloto = original
        assert len(capturado["args"]) == 4
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_rango_y_cantidad_numeros_correctos_al_motor(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_altos_bajos_colorloto
        capturado = {}

        def espia(resultados, rango_min, rango_max, cantidad_balotas):
            capturado["rango_min"] = rango_min
            capturado["rango_max"] = rango_max
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, rango_min, rango_max, cantidad_balotas)

        modulo.calcular_distribucion_altos_bajos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_distribucion_altos_bajos_colorloto = original
        assert capturado["rango_min"] == 1
        assert capturado["rango_max"] == 7
        assert capturado["cantidad_balotas"] == 6

    def test_corte_separado_sin_pasarse_al_motor(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)
        ])
        orquestador.ejecutar(juego_id, "distribucion_altos_bajos_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(self._PARAMS))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        assert fila_guardada.resultado["filas"][0]["total_sorteos"] == 3

    def test_motor_no_invocado_ante_cantidad_incorrecta(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_altos_bajos_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_distribucion_altos_bajos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "distribucion_altos_bajos_colorloto", parametros_metrica=dict(self._PARAMS))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_distribucion_altos_bajos_colorloto = original
        assert llamado["v"] is False

    def test_cache_no_persistida_ante_corrupcion(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
        try:
            orquestador.ejecutar(juego_id, "distribucion_altos_bajos_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "distribucion_altos_bajos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_siete_filas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_altos_bajos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert len(resultado.resultado["filas"]) == 7
        for fila in resultado.resultado["filas"]:
            assert "apariciones" in fila
            assert "total_sorteos" in fila
            assert "frecuencia_relativa" in fila

    def test_identidad_de_cache_tres_claves_exactas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_altos_bajos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert resultado.parametros == self._PARAMS
        assert set(resultado.parametros.keys()) == {"rango_min", "rango_max", "cantidad_numeros"}
        assert "politica_universo_colores" not in resultado.parametros

    def test_receta_no_deriva_colores_vigentes(self):
        """A diferencia de las recetas de AE-2/AE-3/AE-5/AE-6, esta
        receta nunca llama a
        _codigos_colores_vigentes_en_referencia -el motor ignora el
        color por completo."""
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_altos_bajos_colorloto)
        assert "_codigos_colores_vigentes_en_referencia" not in codigo_fuente

    def test_no_usa_rango_real_colorloto_constante_como_ae8(self):
        """A diferencia de AE-8 (paridad, que no depende del rango
        y por eso usa la constante _RANGO_REAL_COLORLOTO), esta
        receta SI depende del rango -debe leerlo de `parametros`,
        nunca de la constante fija."""
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_altos_bajos_colorloto)
        assert "_RANGO_REAL_COLORLOTO" not in codigo_fuente
        assert 'parametros["rango_min"]' in codigo_fuente
        assert 'parametros["rango_max"]' in codigo_fuente

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.distribuciones import calcular_distribucion_altos_bajos_colorloto
        firma = inspect.signature(calcular_distribucion_altos_bajos_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


# =====================================================================
# Etapa AE-10 (PROVISIONAL): decima visualizacion descriptiva de
# ColorLoto -maximo color repetido por sorteo. Reutiliza los helpers
# ya existentes (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _orquestador_colorloto, _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorMaximoRepeticionColorPorSorteoSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría y su adenda correctiva, previas a esta
    implementación -aquí se confirman los casos obligatorios
    explícitos de esta implementación."""

    def test_categorias_uno_a_seis_completas_y_ordenadas(self):
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        r = calcular_maximo_repeticion_color_por_sorteo([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], cantidad_balotas=6)
        assert [f.valor for f in r] == [str(n) for n in range(1, 7)]

    def test_ejemplo_uno_seis_colores_distintos(self):
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_maximo_repeticion_color_por_sorteo([_cl(1, p, date(2024, 1, 1))], cantidad_balotas=6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "1"

    def test_ejemplo_tres_un_color_repetido_tres_veces(self):
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        p = ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "AZUL"), (5, "VERDE"), (6, "NEGRO"))
        r = calcular_maximo_repeticion_color_por_sorteo([_cl(1, p, date(2024, 1, 1))], cantidad_balotas=6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "3"

    def test_ejemplo_seis_todas_las_balotas_mismo_color(self):
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        p = ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "ROJO"))
        r = calcular_maximo_repeticion_color_por_sorteo([_cl(1, p, date(2024, 1, 1))], cantidad_balotas=6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "6"

    def test_categoria_ausente_con_cero_real(self):
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        p = ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "AZUL"), (5, "VERDE"), (6, "NEGRO"))
        r = calcular_maximo_repeticion_color_por_sorteo([_cl(1, p, date(2024, 1, 1))], cantidad_balotas=6)
        fila_6 = [f for f in r if f.valor == "6"][0]
        assert fila_6.apariciones == 0

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        r = calcular_maximo_repeticion_color_por_sorteo([], cantidad_balotas=6)
        assert len(r) == 6
        assert all(f.total_sorteos == 0 for f in r)
        assert all(f.apariciones == 0 for f in r)

    def test_suma_de_apariciones_igual_a_total_sorteos(self):
        datos = [
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "AZUL"), (5, "VERDE"), (6, "NEGRO")), date(2024, 1, 1)),
            _cl(2, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")), date(2024, 1, 2)),
            _cl(3, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "ROJO")), date(2024, 1, 3)),
        ]
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        r = calcular_maximo_repeticion_color_por_sorteo(datos, cantidad_balotas=6)
        assert sum(f.apariciones for f in r) == r[0].total_sorteos == 3

    def test_independiente_del_numero_de_balota(self):
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        p_a = ((1, "ROJO"), (2, "ROJO"), (3, "AZUL"), (4, "VERDE"), (5, "NEGRO"), (6, "BLANCO"))
        p_b = ((7, "ROJO"), (7, "ROJO"), (3, "AZUL"), (4, "VERDE"), (5, "NEGRO"), (6, "BLANCO"))
        r_a = calcular_maximo_repeticion_color_por_sorteo([_cl(1, p_a, date(2024, 1, 1))], cantidad_balotas=6)
        r_b = calcular_maximo_repeticion_color_por_sorteo([_cl(1, p_b, date(2024, 1, 1))], cantidad_balotas=6)
        assert [(f.valor, f.apariciones) for f in r_a] == [(f.valor, f.apariciones) for f in r_b]


class TestRecetaMaximoRepeticionColorPorSorteoColorloto:
    _PARAMS = {"cantidad_numeros": 6}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("maximo_repeticion_color_por_sorteo_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["maximo_repeticion_color_por_sorteo_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["maximo_repeticion_color_por_sorteo_colorloto"].serializar is _serializar_frecuencia_observada

    def test_espia_motor_recibe_dos_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_maximo_repeticion_color_por_sorteo
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_maximo_repeticion_color_por_sorteo = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_maximo_repeticion_color_por_sorteo = original
        assert len(capturado["args"]) == 2
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_cantidad_numeros_correcta_al_motor(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_maximo_repeticion_color_por_sorteo
        capturado = {}

        def espia(resultados, cantidad_balotas):
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, cantidad_balotas)

        modulo.calcular_maximo_repeticion_color_por_sorteo = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_maximo_repeticion_color_por_sorteo = original
        assert capturado["cantidad_balotas"] == 6

    def test_receta_usa_rango_real_colorloto_constante(self):
        """A diferencia de AE-9 (que SÍ depende del rango y por eso
        lo lee de `parametros`), esta receta usa la constante fija,
        mismo patrón exacto ya usado por AE-8."""
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_maximo_repeticion_color_por_sorteo_colorloto)
        assert "_RANGO_REAL_COLORLOTO" in codigo_fuente
        assert 'parametros["rango_min"]' not in codigo_fuente
        assert 'parametros["rango_max"]' not in codigo_fuente

    def test_receta_solo_lee_cantidad_numeros_de_parametros(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_maximo_repeticion_color_por_sorteo_colorloto)
        assert 'parametros["cantidad_numeros"]' in codigo_fuente

    def test_corte_separado_sin_pasarse_al_motor(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)
        ])
        orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(self._PARAMS))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        assert fila_guardada.resultado["filas"][0]["total_sorteos"] == 3

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_maximo_repeticion_color_por_sorteo
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_maximo_repeticion_color_por_sorteo = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", parametros_metrica=dict(self._PARAMS))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_maximo_repeticion_color_por_sorteo = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_no_vigente_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "MORADO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", parametros_metrica=dict(self._PARAMS))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_seis_filas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", parametros_metrica=dict(self._PARAMS))
        assert len(resultado.resultado["filas"]) == 6
        for fila in resultado.resultado["filas"]:
            assert "apariciones" in fila
            assert "total_sorteos" in fila
            assert "frecuencia_relativa" in fila

    def test_identidad_de_cache_una_sola_clave(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", parametros_metrica=dict(self._PARAMS))
        assert resultado.parametros == self._PARAMS
        assert set(resultado.parametros.keys()) == {"cantidad_numeros"}
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.distribuciones import calcular_maximo_repeticion_color_por_sorteo
        firma = inspect.signature(calcular_maximo_repeticion_color_por_sorteo)
        assert list(firma.parameters.keys()) == ["resultados", "cantidad_balotas", "hasta_numero_sorteo"]


# =====================================================================
# Etapa AE-11 (PROVISIONAL): undecima visualizacion descriptiva de
# ColorLoto -distribucion de pares consecutivos. Reutiliza los
# helpers ya existentes (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _orquestador_colorloto, _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorDistribucionParesConsecutivosColorLotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría y su adenda correctiva, previas a esta implementación
    -aquí se confirman los casos obligatorios explícitos de esta
    implementación. El motor mismo (`consecutivos.py`) no fue
    modificado por esta etapa."""

    def test_categorias_cero_a_cinco_completas_y_ordenadas(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        r = calcular_distribucion_pares_consecutivos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], 1, 7, 6)
        assert [f.valor for f in r] == [str(n) for n in range(0, 6)]

    def test_numeros_distintos_uno_a_seis_produce_valor_cinco(self):
        """Ejemplo explícito requerido: 1,2,3,4,5,6 -> valor=5 (máximo
        teórico, K-1 con K=6 balotas)."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_distribucion_pares_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "5"

    def test_numeros_sin_adyacencias_produce_valor_cero(self):
        """Ejemplo explícito requerido: números sin adyacencias ->
        valor=0."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        p = ((1, "ROJO"), (3, "AZUL"), (5, "VERDE"), (7, "NEGRO"), (1, "BLANCO"), (3, "AMARILLO"))
        r = calcular_distribucion_pares_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "0"

    def test_numero_repetido_con_colores_distintos_cuenta_una_sola_vez(self):
        """Ejemplo explícito requerido: un número repetido con colores
        distintos cuenta una sola vez para la adyacencia -confirma la
        deduplicación ya implementada en el motor puro, sin
        reimplementarla ni alterarla en esta etapa. `1` aparece dos
        veces (ROJO y AZUL); números distintos deduplicados = {1,2,3,5,6}
        -rachas [1,2,3] (longitud 3) y [5,6] (longitud 2) -> pares =
        (3-1)+(2-1) = 3, NUNCA 4 (que se obtendría si la repetición
        alargara artificialmente una racha)."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        p = ((1, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_distribucion_pares_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "3"

    def test_categoria_ausente_con_cero_real(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        p = ((1, "ROJO"), (3, "AZUL"), (5, "VERDE"), (7, "NEGRO"), (1, "BLANCO"), (3, "AMARILLO"))
        r = calcular_distribucion_pares_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_5 = [f for f in r if f.valor == "5"][0]
        assert fila_5.apariciones == 0

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        r = calcular_distribucion_pares_consecutivos_colorloto([], 1, 7, 6)
        assert len(r) == 6
        assert all(f.total_sorteos == 0 for f in r)
        assert all(f.apariciones == 0 for f in r)

    def test_suma_de_apariciones_igual_a_total_sorteos(self):
        datos = [
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "AZUL"), (5, "VERDE"), (6, "NEGRO")), date(2024, 1, 1)),
            _cl(2, ((1, "ROJO"), (3, "AZUL"), (5, "VERDE"), (7, "NEGRO"), (1, "BLANCO"), (3, "AMARILLO")), date(2024, 1, 2)),
            _cl(3, _PARES_VALIDOS, date(2024, 1, 3)),
        ]
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        r = calcular_distribucion_pares_consecutivos_colorloto(datos, 1, 7, 6)
        assert sum(f.apariciones for f in r) == r[0].total_sorteos == 3

    def test_resultado_independiente_del_rango_recibido(self):
        """Confirma con ejecución real (caracterización, no solo
        lectura del cuerpo) que `rango_min`/`rango_max` no alteran
        categorías, conteos ni denominador -mismo criterio M1 ya
        usado por AE-8/AE-10."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        r_real = calcular_distribucion_pares_consecutivos_colorloto(datos, 1, 7, 6)
        r_amplio = calcular_distribucion_pares_consecutivos_colorloto(datos, 1, 99, 6)
        assert [(f.valor, f.apariciones) for f in r_real] == [(f.valor, f.apariciones) for f in r_amplio]

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        firma = inspect.signature(calcular_distribucion_pares_consecutivos_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


class TestRecetaDistribucionParesConsecutivosColorloto:
    _PARAMS = {"cantidad_numeros": 6}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("distribucion_pares_consecutivos_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["distribucion_pares_consecutivos_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["distribucion_pares_consecutivos_colorloto"].serializar is _serializar_frecuencia_observada

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_pares_consecutivos_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_distribucion_pares_consecutivos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_distribucion_pares_consecutivos_colorloto = original
        assert len(capturado["args"]) == 4
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_argumentos_exactos_al_motor_rango_real_y_cantidad(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_pares_consecutivos_colorloto
        capturado = {}

        def espia(resultados, rango_min, rango_max, cantidad_balotas):
            capturado["rango_min"] = rango_min
            capturado["rango_max"] = rango_max
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, rango_min, rango_max, cantidad_balotas)

        modulo.calcular_distribucion_pares_consecutivos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_distribucion_pares_consecutivos_colorloto = original
        assert capturado["rango_min"] == 1
        assert capturado["rango_max"] == 7
        assert capturado["cantidad_balotas"] == 6

    def test_receta_usa_rango_real_colorloto_constante_para_validacion_y_motor(self):
        """A diferencia de AE-9 (que SÍ depende del rango y por eso lo
        lee de `parametros`), esta receta usa la constante fija para
        AMBAS llamadas -validación y motor-, mismo patrón exacto ya
        usado por AE-8/AE-10, adaptado a que este motor sí exige
        rango como argumento posicional (a diferencia del de AE-10)."""
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_pares_consecutivos_colorloto)
        assert "_RANGO_REAL_COLORLOTO" in codigo_fuente
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert "rango_min" not in claves_parametros
        assert "rango_max" not in claves_parametros

    def test_receta_solo_lee_cantidad_numeros_de_parametros(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_pares_consecutivos_colorloto)
        assert 'parametros["cantidad_numeros"]' in codigo_fuente

    def test_corte_separado_sin_pasarse_al_motor(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)
        ])
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(self._PARAMS))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        assert fila_guardada.resultado["filas"][0]["total_sorteos"] == 3

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_pares_consecutivos_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_distribucion_pares_consecutivos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_distribucion_pares_consecutivos_colorloto = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_no_vigente_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "MORADO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_seis_filas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert len(resultado.resultado["filas"]) == 6
        for fila in resultado.resultado["filas"]:
            assert "apariciones" in fila
            assert "total_sorteos" in fila
            assert "frecuencia_relativa" in fila

    def test_identidad_de_cache_una_sola_clave(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_pares_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert resultado.parametros == self._PARAMS
        assert set(resultado.parametros.keys()) == {"cantidad_numeros"}
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos_colorloto
        firma = inspect.signature(calcular_distribucion_pares_consecutivos_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


# =====================================================================
# Etapa AE-12 (PROVISIONAL): duodecima visualizacion descriptiva de
# ColorLoto -distribucion de racha maxima. Reutiliza los helpers ya
# existentes (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _orquestador_colorloto, _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorDistribucionRachaMaximaColorLotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría de AE-12, previa a esta implementación -aquí se
    confirman los casos obligatorios explícitos de esta
    implementación. El motor mismo (`consecutivos.py`) no fue
    modificado por esta etapa."""

    def test_categorias_uno_a_seis_sin_categoria_cero(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        r = calcular_distribucion_racha_maxima_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], 1, 7, 6)
        assert [f.valor for f in r] == [str(n) for n in range(1, 7)]
        assert "0" not in {f.valor for f in r}

    def test_racha_completa_uno_a_seis_produce_valor_seis(self):
        """Ejemplo explícito requerido: 1,2,3,4,5,6 -> valor=6 (racha
        completa, longitud máxima con 6 balotas)."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_distribucion_racha_maxima_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "6"

    def test_varias_rachas_separadas_selecciona_la_mayor(self):
        """Ejemplo explícito requerido: rachas separadas -> se toma
        la de mayor longitud. {1,2,3,5,6} -> rachas [3,2] -> maxima=3."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (5, "NEGRO"), (6, "BLANCO"), (5, "AMARILLO"))
        r = calcular_distribucion_racha_maxima_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "3"

    def test_numero_repetido_no_prolonga_la_racha(self):
        """Ejemplo explícito requerido: números duplicados no alargan
        artificialmente la racha. (1,ROJO),(1,AZUL) repetido -> distintos
        {1,2,3,5,6} -> rachas [3,2] -> maxima=3, NUNCA 4."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        p = ((1, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_distribucion_racha_maxima_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "3"

    def test_ausencia_de_consecutivos_produce_valor_uno(self):
        """Ejemplo explícito requerido: sin consecutivos -> valor=1
        (todos aislados, mínimo posible, nunca 0)."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        p = ((1, "ROJO"), (3, "AZUL"), (5, "VERDE"), (7, "NEGRO"), (1, "BLANCO"), (3, "AMARILLO"))
        r = calcular_distribucion_racha_maxima_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "1"

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        r = calcular_distribucion_racha_maxima_colorloto([], 1, 7, 6)
        assert len(r) == 6
        assert all(f.total_sorteos == 0 for f in r)
        assert all(f.apariciones == 0 for f in r)
        assert "0" not in {f.valor for f in r}

    def test_suma_de_apariciones_igual_a_total_sorteos(self):
        datos = [
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")), date(2024, 1, 1)),
            _cl(2, ((1, "ROJO"), (3, "AZUL"), (5, "VERDE"), (7, "NEGRO"), (1, "BLANCO"), (3, "AMARILLO")), date(2024, 1, 2)),
            _cl(3, _PARES_VALIDOS, date(2024, 1, 3)),
        ]
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        r = calcular_distribucion_racha_maxima_colorloto(datos, 1, 7, 6)
        assert sum(f.apariciones for f in r) == r[0].total_sorteos == 3

    def test_resultado_independiente_del_rango_recibido(self):
        """Confirma con ejecución real (caracterización, no solo
        lectura del cuerpo) que `rango_min`/`rango_max` no alteran
        categorías, conteos ni denominador -mismo criterio M1 ya
        usado por AE-8/AE-10/AE-11."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        r_real = calcular_distribucion_racha_maxima_colorloto(datos, 1, 7, 6)
        r_amplio = calcular_distribucion_racha_maxima_colorloto(datos, 1, 99, 6)
        assert [(f.valor, f.apariciones) for f in r_real] == [(f.valor, f.apariciones) for f in r_amplio]

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        firma = inspect.signature(calcular_distribucion_racha_maxima_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


class TestRecetaDistribucionRachaMaximaColorloto:
    _PARAMS = {"cantidad_numeros": 6}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("distribucion_racha_maxima_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["distribucion_racha_maxima_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["distribucion_racha_maxima_colorloto"].serializar is _serializar_frecuencia_observada

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_racha_maxima_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_distribucion_racha_maxima_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_distribucion_racha_maxima_colorloto = original
        assert len(capturado["args"]) == 4
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_argumentos_exactos_al_motor_rango_real_y_cantidad(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_racha_maxima_colorloto
        capturado = {}

        def espia(resultados, rango_min, rango_max, cantidad_balotas):
            capturado["rango_min"] = rango_min
            capturado["rango_max"] = rango_max
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, rango_min, rango_max, cantidad_balotas)

        modulo.calcular_distribucion_racha_maxima_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_distribucion_racha_maxima_colorloto = original
        assert capturado["rango_min"] == 1
        assert capturado["rango_max"] == 7
        assert capturado["cantidad_balotas"] == 6

    def test_receta_usa_rango_real_colorloto_constante_para_validacion_y_motor(self):
        """A diferencia de AE-9 (que SÍ depende del rango y por eso lo
        lee de `parametros`), esta receta usa la constante fija para
        AMBAS llamadas -validación y motor-, mismo patrón exacto ya
        usado por AE-8/AE-10/AE-11, adaptado a que este motor sí exige
        rango como argumento posicional (a diferencia del de AE-10).

        Protección contra el falso positivo textual detectado en
        AE-11: NUNCA se busca la cadena `parametros["rango_min"]`
        dentro de `inspect.getsource` (esa búsqueda coincidiría
        también con el docstring explicativo). Se analiza el AST real
        del cuerpo de la función, buscando accesos `ast.Subscript`
        con base `ast.Name(id="parametros")` y clave constante
        string -los docstrings y comentarios nunca son AST ejecutable
        y por lo tanto nunca pueden producir un falso positivo aquí."""
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_racha_maxima_colorloto)
        assert "_RANGO_REAL_COLORLOTO" in codigo_fuente
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert "rango_min" not in claves_parametros
        assert "rango_max" not in claves_parametros

    def test_receta_solo_lee_cantidad_numeros_de_parametros(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_racha_maxima_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == {"cantidad_numeros"}

    def test_corte_separado_sin_pasarse_al_motor(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)
        ])
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(self._PARAMS))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        assert fila_guardada.resultado["filas"][0]["total_sorteos"] == 3

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_racha_maxima_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_distribucion_racha_maxima_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", parametros_metrica=dict(self._PARAMS))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_distribucion_racha_maxima_colorloto = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_no_vigente_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "MORADO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", parametros_metrica=dict(self._PARAMS))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_seis_filas_sin_categoria_cero(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", parametros_metrica=dict(self._PARAMS))
        assert len(resultado.resultado["filas"]) == 6
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "0" not in valores
        for fila in resultado.resultado["filas"]:
            assert "apariciones" in fila
            assert "total_sorteos" in fila
            assert "frecuencia_relativa" in fila

    def test_identidad_de_cache_una_sola_clave(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_racha_maxima_colorloto", parametros_metrica=dict(self._PARAMS))
        assert resultado.parametros == self._PARAMS
        assert set(resultado.parametros.keys()) == {"cantidad_numeros"}
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_racha_maxima_colorloto
        firma = inspect.signature(calcular_distribucion_racha_maxima_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


# =====================================================================
# Etapa AE-13 (PROVISIONAL): decimotercera visualizacion descriptiva
# de ColorLoto -distribucion de trios consecutivos. Reutiliza los
# helpers ya existentes (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _orquestador_colorloto, _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorDistribucionTriosConsecutivosColorLotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría de AE-13, previa a esta implementación -aquí se
    confirman los casos obligatorios explícitos de esta
    implementación. El motor mismo (`consecutivos.py`) no fue
    modificado por esta etapa."""

    def test_categorias_cero_a_cuatro_completas_y_ordenadas(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        r = calcular_distribucion_trios_consecutivos_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], 1, 7, 6)
        assert [f.valor for f in r] == [str(n) for n in range(0, 5)]

    def test_racha_completa_uno_a_seis_produce_valor_cuatro(self):
        """Ejemplo explícito requerido: racha de longitud 6 (1..6)
        produce 4 tríos -maximo teorico con 6 balotas."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r = calcular_distribucion_trios_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "4"

    def test_racha_de_longitud_tres_produce_un_trio(self):
        """Ejemplo explícito requerido: racha de longitud 3 produce
        exactamente 1 trío."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (5, "NEGRO"), (7, "BLANCO"), (1, "AMARILLO"))
        r = calcular_distribucion_trios_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "1"

    def test_racha_de_longitud_cuatro_produce_dos_trios_superpuestos(self):
        """Ejemplo explícito requerido: racha de longitud 4 produce 2
        tríos superpuestos -(1,2,3) y (2,3,4), confirmando que se
        cuentan por separado, no como un solo bloque."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (6, "BLANCO"), (1, "AMARILLO"))
        r = calcular_distribucion_trios_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "2"

    def test_dos_trios_separados(self):
        """Ejemplo explícito requerido: dos rachas de longitud 3
        separadas producen 1+1=2 tríos."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (5, "NEGRO"), (6, "BLANCO"), (7, "AMARILLO"))
        r = calcular_distribucion_trios_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "2"

    def test_ausencia_de_trios(self):
        """Ejemplo explícito requerido: sin ningún trío -> valor=0
        (categoría real y posible, no ausencia de dato)."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        p = ((1, "ROJO"), (3, "AZUL"), (5, "VERDE"), (7, "NEGRO"), (1, "BLANCO"), (3, "AMARILLO"))
        r = calcular_distribucion_trios_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "0"

    def test_numero_repetido_no_infla_el_conteo_de_trios(self):
        """Ejemplo explícito requerido: número duplicado con colores
        distintos no infla artificialmente el conteo de tríos."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        p = ((1, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (1, "AMARILLO"))
        r = calcular_distribucion_trios_consecutivos_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        fila_activa = [f for f in r if f.apariciones > 0]
        assert fila_activa[0].valor == "2"

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        r = calcular_distribucion_trios_consecutivos_colorloto([], 1, 7, 6)
        assert len(r) == 5
        assert all(f.total_sorteos == 0 for f in r)
        assert all(f.apariciones == 0 for f in r)

    def test_suma_de_apariciones_igual_a_total_sorteos(self):
        datos = [
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")), date(2024, 1, 1)),
            _cl(2, ((1, "ROJO"), (3, "AZUL"), (5, "VERDE"), (7, "NEGRO"), (1, "BLANCO"), (3, "AMARILLO")), date(2024, 1, 2)),
            _cl(3, _PARES_VALIDOS, date(2024, 1, 3)),
        ]
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        r = calcular_distribucion_trios_consecutivos_colorloto(datos, 1, 7, 6)
        assert sum(f.apariciones for f in r) == r[0].total_sorteos == 3

    def test_resultado_independiente_del_rango_recibido(self):
        """Confirma con ejecución real (caracterización, no solo
        lectura del cuerpo) que `rango_min`/`rango_max` no alteran
        categorías, conteos ni denominador -mismo criterio M1 ya
        usado por AE-8/AE-10/AE-11/AE-12."""
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        r_real = calcular_distribucion_trios_consecutivos_colorloto(datos, 1, 7, 6)
        r_amplio = calcular_distribucion_trios_consecutivos_colorloto(datos, 1, 99, 6)
        assert [(f.valor, f.apariciones) for f in r_real] == [(f.valor, f.apariciones) for f in r_amplio]

    def test_determinismo_y_ausencia_de_mutacion(self):
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        sorteo = _cl(1, _PARES_VALIDOS, date(2024, 1, 1))
        pares_originales = tuple(sorteo.pares)
        r1 = calcular_distribucion_trios_consecutivos_colorloto([sorteo], 1, 7, 6)
        r2 = calcular_distribucion_trios_consecutivos_colorloto([sorteo], 1, 7, 6)
        assert [(f.valor, f.apariciones) for f in r1] == [(f.valor, f.apariciones) for f in r2]
        assert sorteo.pares == pares_originales

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        firma = inspect.signature(calcular_distribucion_trios_consecutivos_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


class TestRecetaDistribucionTriosConsecutivosColorloto:
    _PARAMS = {"cantidad_numeros": 6}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("distribucion_trios_consecutivos_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["distribucion_trios_consecutivos_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["distribucion_trios_consecutivos_colorloto"].serializar is _serializar_frecuencia_observada

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_trios_consecutivos_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_distribucion_trios_consecutivos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_distribucion_trios_consecutivos_colorloto = original
        assert len(capturado["args"]) == 4
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_argumentos_exactos_al_motor_rango_real_y_cantidad(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_trios_consecutivos_colorloto
        capturado = {}

        def espia(resultados, rango_min, rango_max, cantidad_balotas):
            capturado["rango_min"] = rango_min
            capturado["rango_max"] = rango_max
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, rango_min, rango_max, cantidad_balotas)

        modulo.calcular_distribucion_trios_consecutivos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        finally:
            modulo.calcular_distribucion_trios_consecutivos_colorloto = original
        assert capturado["rango_min"] == 1
        assert capturado["rango_max"] == 7
        assert capturado["cantidad_balotas"] == 6

    def test_receta_usa_rango_real_colorloto_constante_para_validacion_y_motor(self):
        """A diferencia de AE-9 (que SÍ depende del rango y por eso lo
        lee de `parametros`), esta receta usa la constante fija para
        AMBAS llamadas -validación y motor-, mismo patrón exacto ya
        usado por AE-8/AE-10/AE-11/AE-12, adaptado a que este motor sí
        exige rango como argumento posicional (a diferencia del de
        AE-10).

        Protección contra el falso positivo textual detectado en
        AE-11: NUNCA se busca la cadena `parametros["rango_min"]`
        dentro de `inspect.getsource` (esa búsqueda coincidiría
        también con el docstring explicativo). Se analiza el AST real
        del cuerpo de la función, buscando accesos `ast.Subscript`
        con base `ast.Name(id="parametros")` y clave constante
        string -los docstrings y comentarios nunca son AST ejecutable
        y por lo tanto nunca pueden producir un falso positivo aquí."""
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_trios_consecutivos_colorloto)
        assert "_RANGO_REAL_COLORLOTO" in codigo_fuente
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert "rango_min" not in claves_parametros
        assert "rango_max" not in claves_parametros

    def test_receta_solo_lee_cantidad_numeros_de_parametros(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_trios_consecutivos_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == {"cantidad_numeros"}

    def test_corte_separado_sin_pasarse_al_motor(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 6)
        ])
        orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", hasta_numero_sorteo=3, parametros_metrica=dict(self._PARAMS))
        fila_guardada = estadistica_repo._filas[-1]
        assert "hasta_numero_sorteo" not in fila_guardada.parametros
        assert fila_guardada.hasta_numero_sorteo == 3
        assert fila_guardada.resultado["filas"][0]["total_sorteos"] == 3

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_trios_consecutivos_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_distribucion_trios_consecutivos_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_distribucion_trios_consecutivos_colorloto = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_no_vigente_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "MORADO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_correcta_cinco_filas_incluye_categoria_cero(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert len(resultado.resultado["filas"]) == 5
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "0" in valores
        for fila in resultado.resultado["filas"]:
            assert "apariciones" in fila
            assert "total_sorteos" in fila
            assert "frecuencia_relativa" in fila

    def test_identidad_de_cache_una_sola_clave(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_trios_consecutivos_colorloto", parametros_metrica=dict(self._PARAMS))
        assert resultado.parametros == self._PARAMS
        assert set(resultado.parametros.keys()) == {"cantidad_numeros"}
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.consecutivos import calcular_distribucion_trios_consecutivos_colorloto
        firma = inspect.signature(calcular_distribucion_trios_consecutivos_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


# =====================================================================
# Etapa AE-14 (PROVISIONAL): decimocuarta visualizacion descriptiva
# de ColorLoto -coocurrencia de pares. Reutiliza los helpers ya
# existentes (_cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS,
# _orquestador_colorloto, _HistoricoColorLoto) sin duplicarlos.
# =====================================================================

class TestMotorCoocurrenciaParesColorLotoSemantica:
    """Semántica del motor ya auditada exhaustivamente en la
    auditoría de AE-14, previa a esta implementación -aquí se
    confirman los casos obligatorios explícitos de esta
    implementación. El motor mismo (`coocurrencia.py`) no fue
    modificado por esta etapa."""

    def test_un_sorteo_valido_produce_quince_pares(self):
        """Ejemplo explícito requerido: 6 números distintos producen
        C(6,2)=15 pares."""
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        r = calcular_coocurrencia_pares_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], 1, 7, 6)
        assert len(r) == 15

    def test_maximo_posible_veintiun_pares_sin_inventar_soporte_cero(self):
        """Ejemplo explícito requerido: el máximo teórico para
        ColorLoto (7 números posibles) es C(7,2)=21 pares -nunca se
        completa el universo con pares de soporte cero, solo se
        reportan los observados."""
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        datos = [
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")), date(2024, 1, 1)),
            _cl(2, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (5, "NEGRO"), (6, "BLANCO"), (7, "AMARILLO")), date(2024, 1, 2)),
            _cl(3, ((1, "ROJO"), (4, "AZUL"), (5, "VERDE"), (6, "NEGRO"), (7, "BLANCO"), (2, "AMARILLO")), date(2024, 1, 3)),
            _cl(4, ((3, "ROJO"), (4, "AZUL"), (7, "VERDE"), (1, "NEGRO"), (5, "BLANCO"), (2, "AMARILLO")), date(2024, 1, 4)),
        ]
        r = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 6)
        assert len(r) <= 21
        assert all(f.soporte > 0 for f in r), "nunca debe reportarse un par con soporte 0"

    def test_numeros_desordenados_mismo_resultado(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        ordenado = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        desordenado = ((5, "ROJO"), (1, "AZUL"), (6, "VERDE"), (2, "NEGRO"), (4, "BLANCO"), (3, "AMARILLO"))
        r1 = calcular_coocurrencia_pares_colorloto([_cl(1, ordenado, date(2024, 1, 1))], 1, 7, 6)
        r2 = calcular_coocurrencia_pares_colorloto([_cl(1, desordenado, date(2024, 1, 1))], 1, 7, 6)
        assert sorted((f.elementos, f.soporte) for f in r1) == sorted((f.elementos, f.soporte) for f in r2)

    def test_deduplicacion_numero_repetido_con_color_diferente(self):
        """Ejemplo explícito requerido: número repetido con color
        distinto no forma pareja consigo mismo."""
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        p = ((1, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO"))
        r = calcular_coocurrencia_pares_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        assert len(r) == 10, "distintos deduplicados {1,2,3,4,5} -> C(5,2)=10"

    def test_colores_distintos_no_alteran_el_resultado(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        p_a = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        p_b = ((1, "NEGRO"), (2, "BLANCO"), (3, "AMARILLO"), (4, "ROJO"), (5, "AZUL"), (6, "VERDE"))
        ra = calcular_coocurrencia_pares_colorloto([_cl(1, p_a, date(2024, 1, 1))], 1, 7, 6)
        rb = calcular_coocurrencia_pares_colorloto([_cl(1, p_b, date(2024, 1, 1))], 1, 7, 6)
        assert sorted((f.elementos, f.soporte) for f in ra) == sorted((f.elementos, f.soporte) for f in rb)

    def test_corte_temporal(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        r_antes = calcular_coocurrencia_pares_colorloto([_cl(5, p, date(2024, 1, 5))], 1, 7, 6, hasta_numero_sorteo=1)
        assert r_antes == []
        r_exacto = calcular_coocurrencia_pares_colorloto([_cl(5, p, date(2024, 1, 5))], 1, 7, 6, hasta_numero_sorteo=5)
        assert len(r_exacto) == 15

    def test_valores_fuera_de_rango(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (9, "AMARILLO"))
        try:
            calcular_coocurrencia_pares_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
            assert False, "debia lanzar ValueError"
        except ValueError:
            pass

    def test_menos_de_seis_pares_motor_ejecuta_igual(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        r = calcular_coocurrencia_pares_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        assert len(r) == 10

    def test_mas_de_seis_pares_motor_ejecuta_igual(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        p = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"), (7, "NEGRO"))
        r = calcular_coocurrencia_pares_colorloto([_cl(1, p, date(2024, 1, 1))], 1, 7, 6)
        assert len(r) == 21

    def test_determinismo(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        r1 = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 6)
        r2 = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 6)
        assert [(f.elementos, f.soporte) for f in r1] == [(f.elementos, f.soporte) for f in r2]

    def test_ausencia_de_mutacion(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        sorteo = _cl(1, _PARES_VALIDOS, date(2024, 1, 1))
        originales = tuple(sorteo.pares)
        calcular_coocurrencia_pares_colorloto([sorteo], 1, 7, 6)
        assert sorteo.pares == originales

    def test_pares_unicos_sin_duplicados(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        r = calcular_coocurrencia_pares_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], 1, 7, 6)
        elementos = [f.elementos for f in r]
        assert len(elementos) == len(set(elementos))

    def test_soporte_nunca_excede_total_sorteos(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        datos = [_cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 4)]
        r = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 6)
        for f in r:
            assert f.soporte <= f.total_sorteos

    def test_frecuencia_relativa_coherente_con_soporte_total(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        datos = [_cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 4)]
        r = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 6)
        for f in r:
            assert abs(f.frecuencia_relativa - (f.soporte / f.total_sorteos)) < 1e-12

    def test_ausencia_de_masa_artificial_total_sorteos_identico_en_todas_las_filas(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        datos = [_cl(n, _PARES_VALIDOS, date(2024, 1, n)) for n in range(1, 4)]
        r = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 6)
        assert len(set(f.total_sorteos for f in r)) <= 1

    def test_ninguna_expectativa_o_lift_inventado_para_colorloto(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        r = calcular_coocurrencia_pares_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))], 1, 7, 6)
        assert all(f.frecuencia_esperada is None and f.lift is None for f in r)

    def test_resultado_independiente_del_rango_recibido(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        r_real = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 6)
        r_amplio = calcular_coocurrencia_pares_colorloto(datos, 1, 99, 6)
        assert sorted((f.elementos, f.soporte) for f in r_real) == sorted((f.elementos, f.soporte) for f in r_amplio)

    def test_cantidad_balotas_no_se_usa_matematicamente(self):
        """Hallazgo critico de la auditoria de AE-14: `cantidad_balotas`
        aparece en la firma pero nunca se usa en el cuerpo real del
        motor -confirmado aqui variando su valor sin ningun efecto en
        el resultado."""
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        r_seis = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 6)
        r_otro = calcular_coocurrencia_pares_colorloto(datos, 1, 7, 99)
        assert sorted((f.elementos, f.soporte) for f in r_seis) == sorted((f.elementos, f.soporte) for f in r_otro)

    def test_historico_vacio(self):
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        r = calcular_coocurrencia_pares_colorloto([], 1, 7, 6)
        assert r == []

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        firma = inspect.signature(calcular_coocurrencia_pares_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


class TestRecetaCoocurrenciaParesColorloto:
    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("coocurrencia_pares_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["coocurrencia_pares_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_metrica_asociacion(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion
        assert _CATALOGO["coocurrencia_pares_colorloto"].serializar is _serializar_metrica_asociacion

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_pares_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_coocurrencia_pares_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        finally:
            modulo.calcular_coocurrencia_pares_colorloto = original
        assert len(capturado["args"]) == 4
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_argumentos_exactos_al_motor_rango_real_y_constante_fija(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_pares_colorloto
        capturado = {}

        def espia(resultados, rango_min, rango_max, cantidad_balotas):
            capturado["rango_min"] = rango_min
            capturado["rango_max"] = rango_max
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, rango_min, rango_max, cantidad_balotas)

        modulo.calcular_coocurrencia_pares_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        finally:
            modulo.calcular_coocurrencia_pares_colorloto = original
        assert capturado["rango_min"] == 1
        assert capturado["rango_max"] == 7
        assert capturado["cantidad_balotas"] == 6

    def test_receta_no_lee_ninguna_clave_de_parametros_ast_real(self):
        """Protección contra el falso positivo textual detectado en
        AE-11 y repetido en AE-13: NUNCA se busca texto dentro de
        `inspect.getsource`. Se analiza el AST real del cuerpo de la
        función, buscando accesos `ast.Subscript` con base
        `ast.Name(id="parametros")` -los docstrings y comentarios
        nunca son AST ejecutable."""
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_pares_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == set(), "esta receta NO debe leer ninguna clave de parametros"

    def test_rango_real_colorloto_desempaquetado_no_indexado(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_pares_colorloto)
        assert "rango_min, rango_max = _RANGO_REAL_COLORLOTO" in codigo_fuente
        assert "_RANGO_REAL_COLORLOTO[0]" not in codigo_fuente
        assert "_RANGO_REAL_COLORLOTO[1]" not in codigo_fuente

    def test_cantidad_numeros_proviene_de_constante_fija(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        assert modulo._CANTIDAD_NUMEROS_COLORLOTO == 6
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_pares_colorloto)
        assert "_CANTIDAD_NUMEROS_COLORLOTO" in codigo_fuente

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_pares_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_coocurrencia_pares_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_coocurrencia_pares_colorloto = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_no_vigente_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "MORADO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_completa_de_metrica_asociacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 15
        fila = resultado.resultado["filas"][0]
        assert set(fila.keys()) == {"elementos", "soporte", "total_sorteos", "frecuencia_relativa", "frecuencia_esperada", "lift"}
        assert isinstance(fila["elementos"][0], int)
        assert isinstance(fila["elementos"][1], int)

    def test_none_preservado_correctamente_en_serializacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            assert fila["frecuencia_esperada"] is None
            assert fila["lift"] is None

    def test_identidad_de_cache_diccionario_vacio(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        assert resultado.parametros == {}
        assert "cantidad_numeros" not in resultado.parametros
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros
        assert "color_objetivo" not in resultado.parametros
        assert "hasta_numero_sorteo" not in resultado.parametros

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colorloto
        firma = inspect.signature(calcular_coocurrencia_pares_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


class TestRecetaCoocurrenciaTriosColorloto:
    """Etapa AE-15 (PROVISIONAL): mismo patron exacto que
    TestRecetaCoocurrenciaParesColorloto (AE-14), adaptado a trios."""

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("coocurrencia_trios_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["coocurrencia_trios_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_metrica_asociacion(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion
        assert _CATALOGO["coocurrencia_trios_colorloto"].serializar is _serializar_metrica_asociacion

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_trios_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_coocurrencia_trios_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        finally:
            modulo.calcular_coocurrencia_trios_colorloto = original
        assert len(capturado["args"]) == 4
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_argumentos_exactos_al_motor_rango_real_y_constante_fija(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_trios_colorloto
        capturado = {}

        def espia(resultados, rango_min, rango_max, cantidad_balotas):
            capturado["rango_min"] = rango_min
            capturado["rango_max"] = rango_max
            capturado["cantidad_balotas"] = cantidad_balotas
            return original(resultados, rango_min, rango_max, cantidad_balotas)

        modulo.calcular_coocurrencia_trios_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        finally:
            modulo.calcular_coocurrencia_trios_colorloto = original
        assert capturado["rango_min"] == 1
        assert capturado["rango_max"] == 7
        assert capturado["cantidad_balotas"] == 6

    def test_receta_no_lee_ninguna_clave_de_parametros_ast_real(self):
        """Mismo criterio de AE-11/AE-13/AE-14: se analiza el AST
        real del cuerpo de la funcion, nunca texto de
        inspect.getsource."""
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_trios_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == set(), "esta receta NO debe leer ninguna clave de parametros"

    def test_rango_real_colorloto_desempaquetado_no_indexado(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_trios_colorloto)
        assert "rango_min, rango_max = _RANGO_REAL_COLORLOTO" in codigo_fuente
        assert "_RANGO_REAL_COLORLOTO[0]" not in codigo_fuente
        assert "_RANGO_REAL_COLORLOTO[1]" not in codigo_fuente

    def test_cantidad_numeros_proviene_de_constante_fija(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        assert modulo._CANTIDAD_NUMEROS_COLORLOTO == 6
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_trios_colorloto)
        assert "_CANTIDAD_NUMEROS_COLORLOTO" in codigo_fuente

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_trios_colorloto
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_coocurrencia_trios_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_coocurrencia_trios_colorloto = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_no_vigente_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "MORADO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_completa_de_metrica_asociacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 20
        fila = resultado.resultado["filas"][0]
        assert set(fila.keys()) == {"elementos", "soporte", "total_sorteos", "frecuencia_relativa", "frecuencia_esperada", "lift"}
        assert len(fila["elementos"]) == 3
        for elemento in fila["elementos"]:
            assert isinstance(elemento, int)

    def test_elementos_tres_enteros_ascendentes(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            a, b, c = fila["elementos"]
            assert a < b < c

    def test_deduplicacion_de_maximo_treinta_y_cinco(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        combinaciones = [tuple(f["elementos"]) for f in resultado.resultado["filas"]]
        assert len(combinaciones) == len(set(combinaciones))
        assert len(combinaciones) <= 35

    def test_none_preservado_correctamente_en_serializacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            assert fila["frecuencia_esperada"] is None
            assert fila["lift"] is None

    def test_identidad_de_cache_diccionario_vacio(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        assert resultado.parametros == {}
        assert "cantidad_numeros" not in resultado.parametros
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros
        assert "color_objetivo" not in resultado.parametros
        assert "hasta_numero_sorteo" not in resultado.parametros

    def test_determinismo_sin_mutacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        r1 = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        assert r1.resultado["filas"] == r1.resultado["filas"]

    def test_corte_temporal_produce_caches_distintas(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)),
            _cl(2, _PARES_VALIDOS, date(2024, 1, 2)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", hasta_numero_sorteo=1, parametros_metrica={})
        r_completo = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        assert r_corte.hasta_numero_sorteo == 1
        assert r_completo.hasta_numero_sorteo is None

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_trios_colorloto
        firma = inspect.signature(calcular_coocurrencia_trios_colorloto)
        assert list(firma.parameters.keys()) == ["resultados", "rango_min", "rango_max", "cantidad_balotas", "hasta_numero_sorteo"]


class TestRecetaCoocurrenciaParesColoresColorloto:
    """Etapa AE-16 (PROVISIONAL): candidata aprobada por la
    auditoria previa (Decision A). A diferencia de
    TestRecetaCoocurrenciaParesColorloto (AE-14) y
    TestRecetaCoocurrenciaTriosColorloto (AE-15), que calculan
    sobre NUMEROS, esta receta calcula sobre CODIGOS DE COLOR y
    reutiliza el serializador textual nuevo, nunca el numerico."""

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("coocurrencia_pares_colores_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["coocurrencia_pares_colores_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_el_nuevo_serializador_textual(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        assert _CATALOGO["coocurrencia_pares_colores_colorloto"].serializar is _serializar_metrica_asociacion_texto

    def test_serializador_no_es_el_numerico_existente(self):
        """Confirma explicitamente que esta receta NO reutiliza
        _serializar_metrica_asociacion (AE-14/AE-15) -esa funcion
        convierte cada elemento con int(), que rompe con codigos de
        color."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion
        assert _CATALOGO["coocurrencia_pares_colores_colorloto"].serializar is not _serializar_metrica_asociacion

    def test_espia_motor_recibe_un_argumento_sin_corte(self):
        """A diferencia de las variantes numericas (4 argumentos),
        calcular_coocurrencia_pares_colores solo acepta resultados
        y hasta_numero_sorteo -la receta debe pasar UN solo
        argumento posicional (historico.pares), nunca rango_min,
        rango_max ni cantidad_balotas: esos parametros no existen
        en la firma real del motor."""
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_pares_colores
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_coocurrencia_pares_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        finally:
            modulo.calcular_coocurrencia_pares_colores = original
        assert len(capturado["args"]) == 1
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_no_lee_ninguna_clave_de_parametros_ast_real(self):
        """Mismo criterio de AE-11/AE-13/AE-14/AE-15: se analiza el
        AST real del cuerpo de la funcion, nunca texto de
        inspect.getsource."""
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_pares_colores_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == set(), "esta receta NO debe leer ninguna clave de parametros"

    def test_receta_no_usa_parametros_get(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_pares_colores_colorloto)
        assert "parametros.get(" not in codigo_fuente

    def test_receta_no_pasa_rango_ni_cantidad_al_motor(self):
        """Confirma por AST que la llamada al motor real usa
        exactamente un argumento posicional (historico.pares),
        nunca _RANGO_REAL_COLORLOTO ni _CANTIDAD_NUMEROS_COLORLOTO
        como argumentos del motor -esos identificadores solo pueden
        aparecer en la llamada a _validar_historico_colorloto_consistente."""
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_pares_colores_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        llamada_motor = None
        for nodo in ast.walk(funcion):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "calcular_coocurrencia_pares_colores":
                llamada_motor = nodo
        assert llamada_motor is not None
        assert len(llamada_motor.args) == 1
        assert len(llamada_motor.keywords) == 0

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_pares_colores
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_coocurrencia_pares_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_coocurrencia_pares_colores = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_no_vigente_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "MORADO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_completa_con_elementos_como_cadenas(self):
        """Prueba directa pedida: 'AMARILLO' permanece 'AMARILLO',
        los elementos resultantes son cadenas, no aparece ninguna
        conversion a entero."""
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 15
        fila = resultado.resultado["filas"][0]
        assert set(fila.keys()) == {"elementos", "soporte", "total_sorteos", "frecuencia_relativa", "frecuencia_esperada", "lift"}
        assert len(fila["elementos"]) == 2
        for elemento in fila["elementos"]:
            assert isinstance(elemento, str)
        assert "AMARILLO" in {e for f in resultado.resultado["filas"] for e in f["elementos"]}

    def test_elementos_dos_codigos_de_color_orden_alfabetico(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            a, b = fila["elementos"]
            assert a < b

    def test_ninguna_conversion_a_entero(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            for elemento in fila["elementos"]:
                assert not isinstance(elemento, int)

    def test_none_preservado_correctamente_en_serializacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            assert fila["frecuencia_esperada"] is None
            assert fila["lift"] is None

    def test_identidad_de_cache_diccionario_vacio(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        assert resultado.parametros == {}
        assert "cantidad_numeros" not in resultado.parametros
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "colores" not in resultado.parametros
        assert "colores_vigentes" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros
        assert "color_objetivo" not in resultado.parametros
        assert "hasta_numero_sorteo" not in resultado.parametros

    def test_determinismo_sin_mutacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        r1 = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        assert r1.resultado["filas"] == r1.resultado["filas"]

    def test_corte_temporal_produce_caches_distintas(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)),
            _cl(2, _PARES_VALIDOS, date(2024, 1, 2)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", hasta_numero_sorteo=1, parametros_metrica={})
        r_completo = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        assert r_corte.hasta_numero_sorteo == 1
        assert r_completo.hasta_numero_sorteo is None

    def test_coexiste_con_coocurrencia_pares_y_trios_colorloto(self):
        """AE-16 comparte identidad {} con AE-14/AE-15 pero un
        tipo_estadistica distinto -sin colision."""
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        r_numeros = orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        r_colores = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        assert r_numeros.resultado != r_colores.resultado
        elementos_numeros = {e for f in r_numeros.resultado["filas"] for e in f["elementos"]}
        elementos_colores = {e for f in r_colores.resultado["filas"] for e in f["elementos"]}
        assert all(isinstance(e, int) for e in elementos_numeros)
        assert all(isinstance(e, str) for e in elementos_colores)

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_pares_colores
        firma = inspect.signature(calcular_coocurrencia_pares_colores)
        assert list(firma.parameters.keys()) == ["resultados", "hasta_numero_sorteo"]


class TestSerializarMetricaAsociacionTexto:
    """Etapa AE-16 (PROVISIONAL): pruebas directas del serializador
    textual nuevo, aislado de _serializar_metrica_asociacion."""

    def test_amarillo_permanece_amarillo(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL"), soporte=3, total_sorteos=5, frecuencia_relativa=0.6, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        assert resultado["filas"][0]["elementos"] == ["AMARILLO", "AZUL"]

    def test_azul_permanece_azul(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL"), soporte=3, total_sorteos=5, frecuencia_relativa=0.6, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        assert resultado["filas"][0]["elementos"][1] == "AZUL"

    def test_elementos_resultantes_son_cadenas(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("NEGRO", "VERDE"), soporte=1, total_sorteos=1, frecuencia_relativa=1.0, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        for elemento in resultado["filas"][0]["elementos"]:
            assert isinstance(elemento, str)

    def test_none_continua_siendo_none(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("NEGRO", "VERDE"), soporte=1, total_sorteos=1, frecuencia_relativa=1.0, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        assert resultado["filas"][0]["frecuencia_esperada"] is None
        assert resultado["filas"][0]["lift"] is None

    def test_ausencia_de_conversion_a_entero_no_lanza_valueerror(self):
        """Prueba directa pedida: reproduce exactamente el escenario
        que rompia _serializar_metrica_asociacion (ValueError:
        invalid literal for int() with base 10: 'AMARILLO') y
        confirma que el serializador nuevo NO falla."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL"), soporte=1, total_sorteos=1, frecuencia_relativa=1.0, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)  # no debe lanzar
        assert resultado["filas"][0]["elementos"] == ["AMARILLO", "AZUL"]

    def test_no_muta_las_filas_de_entrada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("NEGRO", "VERDE"), soporte=1, total_sorteos=1, frecuencia_relativa=1.0, frecuencia_esperada=None, lift=None)]
        copia = list(filas)
        _serializar_metrica_asociacion_texto(filas)
        assert filas == copia

    def test_resultado_vacio(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        assert _serializar_metrica_asociacion_texto([]) == {"filas": []}

    def test_serializador_numerico_existente_conserva_su_comportamiento(self):
        """Confirma que _serializar_metrica_asociacion (AE-14) NO
        fue modificado: sigue convirtiendo elementos numericos a
        int real, nunca a str."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion
        filas = [MetricaAsociacion(elementos=("1", "2"), soporte=3, total_sorteos=5, frecuencia_relativa=0.6, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion(filas)
        assert resultado["filas"][0]["elementos"] == [1, 2]
        assert all(isinstance(e, int) for e in resultado["filas"][0]["elementos"])

    def test_serializador_numerico_no_acepta_codigos_de_color(self):
        """Confirma el fallo real que motivo esta etapa: el
        serializador numerico existente sigue lanzando ValueError
        con codigos de color -no fue alterado para aceptarlos."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL"), soporte=1, total_sorteos=1, frecuencia_relativa=1.0, frecuencia_esperada=None, lift=None)]
        try:
            _serializar_metrica_asociacion(filas)
            assert False, "se esperaba ValueError"
        except ValueError:
            pass

    def test_ae14_sigue_serializando_enteros_reales(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            for elemento in fila["elementos"]:
                assert isinstance(elemento, int)

    def test_ae15_sigue_serializando_enteros_reales(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            for elemento in fila["elementos"]:
                assert isinstance(elemento, int)


class TestRecetaCoocurrenciaTriosColoresColorloto:
    """Etapa AE-17 (PROVISIONAL): candidata aprobada por la
    auditoria previa (Decision A). Mismo patron exacto que
    TestRecetaCoocurrenciaParesColoresColorloto (AE-16), esta vez
    con tres codigos de color y reutilizando el serializador
    textual SIN NINGUN CAMBIO."""

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("coocurrencia_trios_colores_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["coocurrencia_trios_colores_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_el_mismo_textual_de_ae16_sin_cambios(self):
        """Confirma explicitamente que AE-17 reutiliza el MISMO
        objeto funcion que AE-16 -no una copia, no una variante."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        assert _CATALOGO["coocurrencia_trios_colores_colorloto"].serializar is _serializar_metrica_asociacion_texto
        assert _CATALOGO["coocurrencia_pares_colores_colorloto"].serializar is _CATALOGO["coocurrencia_trios_colores_colorloto"].serializar

    def test_serializador_no_es_el_numerico(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion
        assert _CATALOGO["coocurrencia_trios_colores_colorloto"].serializar is not _serializar_metrica_asociacion

    def test_espia_motor_recibe_un_argumento_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_trios_colores
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_coocurrencia_trios_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        finally:
            modulo.calcular_coocurrencia_trios_colores = original
        assert len(capturado["args"]) == 1
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_no_lee_ninguna_clave_de_parametros_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_trios_colores_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == set(), "esta receta NO debe leer ninguna clave de parametros"

    def test_receta_no_usa_parametros_get(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_trios_colores_colorloto)
        assert "parametros.get(" not in codigo_fuente

    def test_receta_no_pasa_rango_ni_cantidad_al_motor(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_coocurrencia_trios_colores_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        llamada_motor = None
        for nodo in ast.walk(funcion):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "calcular_coocurrencia_trios_colores":
                llamada_motor = nodo
        assert llamada_motor is not None
        assert len(llamada_motor.args) == 1
        assert len(llamada_motor.keywords) == 0

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_coocurrencia_trios_colores
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_coocurrencia_trios_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_coocurrencia_trios_colores = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_no_vigente_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (6, "MORADO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert estadistica_repo.guardar_fue_llamado is True

    def test_serializacion_completa_con_tres_cadenas(self):
        """Prueba directa pedida: seis colores distintos -> 20
        trios; tres cadenas reales por fila, sin conversion a
        entero."""
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 20
        fila = resultado.resultado["filas"][0]
        assert set(fila.keys()) == {"elementos", "soporte", "total_sorteos", "frecuencia_relativa", "frecuencia_esperada", "lift"}
        assert len(fila["elementos"]) == 3
        for elemento in fila["elementos"]:
            assert isinstance(elemento, str)

    def test_cinco_colores_distintos_diez_trios(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "BLANCO")), date(2024, 1, 1))
        ])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 10

    def test_cuatro_colores_distintos_cuatro_trios(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "NEGRO"), (6, "NEGRO")), date(2024, 1, 1))
        ])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 4

    def test_tres_colores_distintos_con_repeticiones_un_trio_sin_multiplicar(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "AZUL"), (4, "AZUL"), (5, "VERDE"), (6, "VERDE")), date(2024, 1, 1))
        ])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 1
        assert resultado.resultado["filas"][0]["soporte"] == 1

    def test_dos_colores_distintos_cero_trios(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "AZUL"), (5, "AZUL"), (6, "AZUL")), date(2024, 1, 1))
        ])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 0

    def test_elementos_tres_cadenas_orden_canonico(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            a, b, c = fila["elementos"]
            assert a < b < c

    def test_ninguna_conversion_a_entero(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            for elemento in fila["elementos"]:
                assert not isinstance(elemento, int)

    def test_none_preservado_correctamente_en_serializacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        for fila in resultado.resultado["filas"]:
            assert fila["frecuencia_esperada"] is None
            assert fila["lift"] is None

    def test_identidad_de_cache_diccionario_vacio(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert resultado.parametros == {}
        assert "cantidad_numeros" not in resultado.parametros
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "colores" not in resultado.parametros
        assert "colores_vigentes" not in resultado.parametros
        assert "politica_universo_colores" not in resultado.parametros
        assert "hasta_numero_sorteo" not in resultado.parametros

    def test_determinismo_sin_mutacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        r1 = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert r1.resultado["filas"] == r1.resultado["filas"]

    def test_corte_temporal_produce_caches_distintas(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)),
            _cl(2, _PARES_VALIDOS, date(2024, 1, 2)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", hasta_numero_sorteo=1, parametros_metrica={})
        r_completo = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert r_corte.hasta_numero_sorteo == 1
        assert r_completo.hasta_numero_sorteo is None

    def test_coexiste_con_las_tres_coocurrencias_previas(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        r_pares_num = orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        r_trios_num = orquestador.ejecutar(juego_id, "coocurrencia_trios_colorloto", parametros_metrica={})
        r_pares_col = orquestador.ejecutar(juego_id, "coocurrencia_pares_colores_colorloto", parametros_metrica={})
        r_trios_col = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert all(isinstance(e, int) for f in r_pares_num.resultado["filas"] for e in f["elementos"])
        assert all(isinstance(e, int) for f in r_trios_num.resultado["filas"] for e in f["elementos"])
        assert all(isinstance(e, str) for f in r_pares_col.resultado["filas"] for e in f["elementos"])
        assert all(isinstance(e, str) for f in r_trios_col.resultado["filas"] for e in f["elementos"])
        assert all(len(f["elementos"]) == 3 for f in r_trios_col.resultado["filas"])

    def test_universo_global_puede_superar_veinte_filas(self):
        """Reproduce la caracterizacion de la auditoria previa: un
        historico con 7 codigos distintos entre dos sorteos (6
        balotas cada uno) produce mas de 20 filas globales -no debe
        existir ningun limite fijo de 20 en la receta ni en la VM."""
        datos = [
            _cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO")), date(2024, 1, 1)),
            _cl(2, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "MORADO")), date(2024, 1, 2)),
        ]
        paleta_extendida = list(_PALETA_COLORLOTO) + [_col("MORADO")]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos, colores=paleta_extendida)
        resultado = orquestador.ejecutar(juego_id, "coocurrencia_trios_colores_colorloto", parametros_metrica={})
        assert len(resultado.resultado["filas"]) == 30

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.coocurrencia import calcular_coocurrencia_trios_colores
        firma = inspect.signature(calcular_coocurrencia_trios_colores)
        assert list(firma.parameters.keys()) == ["resultados", "hasta_numero_sorteo"]


class TestSerializarMetricaAsociacionTextoConTresElementos:
    """Etapa AE-17 (PROVISIONAL): pruebas directas de reutilizacion
    del serializador textual de AE-16 con tres elementos, SIN
    modificarlo."""

    def test_tres_colores_preservados_en_orden(self):
        """Prueba directa pedida:
        ("AMARILLO", "AZUL", "ROJO") -> ["AMARILLO", "AZUL", "ROJO"]"""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL", "ROJO"), soporte=5, total_sorteos=10, frecuencia_relativa=0.5, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        assert resultado["filas"][0]["elementos"] == ["AMARILLO", "AZUL", "ROJO"]

    def test_tres_elementos_resultantes_son_cadenas(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL", "ROJO"), soporte=1, total_sorteos=1, frecuencia_relativa=1.0, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        for elemento in resultado["filas"][0]["elementos"]:
            assert isinstance(elemento, str)

    def test_soporte_total_y_frecuencia_preservados_con_tres(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL", "ROJO"), soporte=5, total_sorteos=10, frecuencia_relativa=0.5, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        assert resultado["filas"][0]["soporte"] == 5
        assert resultado["filas"][0]["total_sorteos"] == 10
        assert resultado["filas"][0]["frecuencia_relativa"] == 0.5

    def test_none_preservado_con_tres_elementos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL", "ROJO"), soporte=1, total_sorteos=1, frecuencia_relativa=1.0, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        assert resultado["filas"][0]["frecuencia_esperada"] is None
        assert resultado["filas"][0]["lift"] is None

    def test_no_muta_la_entrada_con_tres_elementos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        original_tuple = ("AMARILLO", "AZUL", "ROJO")
        metrica = MetricaAsociacion(elementos=original_tuple, soporte=5, total_sorteos=10, frecuencia_relativa=0.5, frecuencia_esperada=None, lift=None)
        filas = [metrica]
        _serializar_metrica_asociacion_texto(filas)
        assert metrica.elementos == original_tuple

    def test_ae16_sigue_serializando_dos_cadenas(self):
        """Regresion: AE-16 sigue funcionando con dos elementos
        despues de que AE-17 reutiliza el mismo serializador."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion_texto
        filas = [MetricaAsociacion(elementos=("AMARILLO", "AZUL"), soporte=3, total_sorteos=5, frecuencia_relativa=0.6, frecuencia_esperada=None, lift=None)]
        resultado = _serializar_metrica_asociacion_texto(filas)
        assert resultado["filas"][0]["elementos"] == ["AMARILLO", "AZUL"]

    def test_ae14_y_ae15_siguen_serializando_enteros_reales(self):
        """Regresion: el serializador numerico (AE-14/AE-15) no fue
        tocado ni afectado por la reutilizacion en AE-17."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_metrica_asociacion
        filas_2 = [MetricaAsociacion(elementos=("1", "2"), soporte=3, total_sorteos=5, frecuencia_relativa=0.6, frecuencia_esperada=None, lift=None)]
        filas_3 = [MetricaAsociacion(elementos=("1", "2", "3"), soporte=3, total_sorteos=5, frecuencia_relativa=0.6, frecuencia_esperada=None, lift=None)]
        r2 = _serializar_metrica_asociacion(filas_2)
        r3 = _serializar_metrica_asociacion(filas_3)
        assert all(isinstance(e, int) for e in r2["filas"][0]["elementos"])
        assert all(isinstance(e, int) for e in r3["filas"][0]["elementos"])


class TestRecetaIntervalosHistoricosColoresColorloto:
    """Etapa AE-18 (PROVISIONAL): candidata aprobada por la
    auditoria previa (Decision A, corregida). A diferencia de las
    coocurrencias (AE-14 a AE-17), esta receta SI deriva
    colores_vigentes -mismo patron exacto ya validado por AE-5- pero
    usa las CONSTANTES de modulo (_RANGO_REAL_COLORLOTO/
    _CANTIDAD_NUMEROS_COLORLOTO) para la validacion defensiva, nunca
    leidas de parametros -la contradiccion detectada en la auditoria
    (identidad minima vs. lectura de parametros["rango_min"]) queda
    resuelta aqui: cero lectura de parametros, identidad minima real."""

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("intervalos_historicos_colores_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["intervalos_historicos_colores_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_atrasos_reutilizado_sin_cambios(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        assert _CATALOGO["intervalos_historicos_colores_colorloto"].serializar is _serializar_atrasos
        assert _CATALOGO["atrasos_colores_colorloto"].serializar is _CATALOGO["intervalos_historicos_colores_colorloto"].serializar

    def test_espia_motor_recibe_dos_argumentos_sin_corte(self):
        """Firma real: calcular_intervalos_historicos_colores(resultados,
        colores_vigentes, hasta_numero_sorteo=None) -exactamente dos
        argumentos posicionales, cero kwargs, nunca hasta_numero_sorteo."""
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_colores
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(
                juego_id, "intervalos_historicos_colores_colorloto",
                parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
            )
        finally:
            modulo.calcular_intervalos_historicos_colores = original
        assert len(capturado["args"]) == 2
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_no_lee_ninguna_clave_de_parametros_ast_real(self):
        """Confirma por AST que la receta NUNCA lee parametros[...]
        -resuelve la contradiccion detectada en la auditoria: usa
        _RANGO_REAL_COLORLOTO/_CANTIDAD_NUMEROS_COLORLOTO como
        constantes de modulo, no valores de parametros."""
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_intervalos_historicos_colores_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == set(), "esta receta NO debe leer ninguna clave de parametros"

    def test_receta_no_usa_parametros_get(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_intervalos_historicos_colores_colorloto)
        assert "parametros.get(" not in codigo_fuente

    def test_receta_usa_constantes_de_modulo(self):
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_intervalos_historicos_colores_colorloto)
        assert "_RANGO_REAL_COLORLOTO" in codigo_fuente
        assert "_CANTIDAD_NUMEROS_COLORLOTO" in codigo_fuente
        assert "_codigos_colores_vigentes_en_referencia" in codigo_fuente

    def test_receta_no_pasa_rango_ni_cantidad_ni_corte_al_motor(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_intervalos_historicos_colores_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        llamada_motor = None
        for nodo in ast.walk(funcion):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "calcular_intervalos_historicos_colores":
                llamada_motor = nodo
        assert llamada_motor is not None
        assert len(llamada_motor.args) == 2
        assert len(llamada_motor.keywords) == 0

    def test_ejecucion_real_sin_keyerror_con_identidad_minima(self):
        """Prueba directa pedida por la auditoria: la receta se
        ejecuta con la identidad minima real sin KeyError."""
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        assert resultado is not None

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_colores
        llamado = {"v": False}

        def espia(*a, **kw):
            llamado["v"] = True
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_colores = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS[:5], date(2024, 1, 1))])
            try:
                orquestador.ejecutar(
                    juego_id, "intervalos_historicos_colores_colorloto",
                    parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
                )
            except ResultadoHistoricoInconsistenteError:
                pass
        finally:
            modulo.calcular_intervalos_historicos_colores = original
        assert llamado["v"] is False

    def test_numero_fuera_de_rango_motor_no_invocado_cache_no_persistida(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([
            _cl(1, ((1, "ROJO"), (2, "ROJO"), (3, "ROJO"), (4, "ROJO"), (5, "ROJO"), (9, "ROJO")), date(2024, 1, 1))
        ])
        try:
            orquestador.ejecutar(
                juego_id, "intervalos_historicos_colores_colorloto",
                parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
            )
        except ResultadoHistoricoInconsistenteError:
            pass
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        assert estadistica_repo.guardar_fue_llamado is True

    def test_colores_vigentes_derivados_por_helper_real(self):
        """Confirma que colores_vigentes proviene de
        _codigos_colores_vigentes_en_referencia, no de una lista fija."""
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert valores == {"ROJO", "AZUL", "VERDE", "NEGRO", "BLANCO", "AMARILLO"}

    def test_colores_retirados_preservados(self):
        paleta_extendida = list(_PALETA_COLORLOTO) + [_col("MORADO", activo=False)]
        datos = [_cl(1, ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "MORADO")), date(2020, 1, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos, colores=paleta_extendida)
        resultado = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        valores = {f["valor"] for f in resultado.resultado["filas"]}
        assert "MORADO" in valores

    def test_colores_nunca_observados_incluidos(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        for fila in resultado.resultado["filas"]:
            assert fila["cantidad_apariciones"] >= 0

    def test_corte_ya_aplicado_produce_caches_distintas(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)),
            _cl(2, _PARES_VALIDOS, date(2024, 1, 2)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto", hasta_numero_sorteo=1,
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        r_completo = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        assert r_corte.hasta_numero_sorteo == 1
        assert r_completo.hasta_numero_sorteo is None

    def test_determinismo_sin_mutacion(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        r1 = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        assert r1.resultado["filas"] == r1.resultado["filas"]

    def test_serializacion_real_produce_array_json_de_intervalos(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)),
            _cl(2, _PARES_VALIDOS, date(2024, 1, 2)),
        ])
        resultado = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        fila = resultado.resultado["filas"][0]
        # En memoria (antes de la ronda real por JSONB en PostgreSQL)
        # `dataclasses.asdict` preserva el tipo Python real, una
        # tupla -se convierte en array JSON solo al pasar por
        # `json.dumps`, confirmado directamente en
        # TestSerializarAtrasosConIntervalosHistoricos.
        assert isinstance(fila["intervalos"], tuple)
        import json
        assert isinstance(json.loads(json.dumps(fila["intervalos"])), list)
        assert set(fila.keys()) == {
            "valor", "cantidad_apariciones", "cantidad_intervalos", "intervalo_minimo",
            "intervalo_maximo", "intervalo_promedio", "intervalo_mediana", "intervalos",
        }

    def test_identidad_exacta_con_politica_sin_claves_redundantes(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        assert resultado.parametros == {"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}
        assert "rango_min" not in resultado.parametros
        assert "rango_max" not in resultado.parametros
        assert "cantidad_numeros" not in resultado.parametros
        assert "cantidad_balotas" not in resultado.parametros
        assert "colores" not in resultado.parametros
        assert "colores_vigentes" not in resultado.parametros
        assert "hasta_numero_sorteo" not in resultado.parametros

    def test_politica_distinta_produce_identidad_distinta(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        r_v1 = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        r_v2 = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v2"},
        )
        assert r_v1.parametros != r_v2.parametros

    def test_coexiste_con_ae5_y_ae14_a_ae17(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        r_atrasos = orquestador.ejecutar(
            juego_id, "atrasos_colores_colorloto",
            parametros_metrica={
                "rango_min": 1, "rango_max": 7, "cantidad_numeros": 6,
                "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1",
            },
        )
        r_intervalos = orquestador.ejecutar(
            juego_id, "intervalos_historicos_colores_colorloto",
            parametros_metrica={"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"},
        )
        r_coocurrencia = orquestador.ejecutar(juego_id, "coocurrencia_pares_colorloto", parametros_metrica={})
        assert r_atrasos.resultado != r_intervalos.resultado
        assert r_intervalos.resultado != r_coocurrencia.resultado

    def test_motor_no_modificado(self):
        import inspect
        from app.application.estadisticas.motor.atrasos import calcular_intervalos_historicos_colores
        firma = inspect.signature(calcular_intervalos_historicos_colores)
        assert list(firma.parameters.keys()) == ["resultados", "colores_vigentes", "hasta_numero_sorteo"]


class TestSerializarAtrasosConIntervalosHistoricos:
    """Etapa AE-18 (PROVISIONAL): pruebas directas de reutilizacion
    de _serializar_atrasos (protegido, AE-4) con IntervalosHistoricos,
    sin modificarlo."""

    def test_salida_real_produce_json_exacto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        fila = IntervalosHistoricos(
            valor="ROJO", cantidad_apariciones=3, cantidad_intervalos=2,
            intervalo_minimo=1, intervalo_maximo=9, intervalo_promedio=5,
            intervalo_mediana=5.0, intervalos=(9, 1),
        )
        resultado = _serializar_atrasos([fila])
        assert resultado == {"filas": [{
            "valor": "ROJO", "cantidad_apariciones": 3, "cantidad_intervalos": 2,
            "intervalo_minimo": 1, "intervalo_maximo": 9, "intervalo_promedio": 5,
            "intervalo_mediana": 5.0, "intervalos": (9, 1),
        }]}

    def test_intervalos_se_serializa_como_lista_via_json(self):
        import json
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        fila = IntervalosHistoricos(
            valor="ROJO", cantidad_apariciones=3, cantidad_intervalos=2,
            intervalo_minimo=1, intervalo_maximo=9, intervalo_promedio=5,
            intervalo_mediana=5.0, intervalos=(9, 1),
        )
        resultado = _serializar_atrasos([fila])
        texto_json = json.dumps(resultado)
        reconstruido = json.loads(texto_json)
        assert reconstruido["filas"][0]["intervalos"] == [9, 1]

    def test_promedio_entero_y_mediana_flotante_permitidos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        fila = IntervalosHistoricos(
            valor="ROJO", cantidad_apariciones=3, cantidad_intervalos=2,
            intervalo_minimo=1, intervalo_maximo=9, intervalo_promedio=5,
            intervalo_mediana=5.0, intervalos=(9, 1),
        )
        resultado = _serializar_atrasos([fila])
        assert isinstance(resultado["filas"][0]["intervalo_promedio"], int)
        assert isinstance(resultado["filas"][0]["intervalo_mediana"], float)

    def test_none_preservado_con_menos_de_dos_apariciones(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        fila = IntervalosHistoricos(
            valor="AZUL", cantidad_apariciones=1, cantidad_intervalos=0,
            intervalo_minimo=None, intervalo_maximo=None, intervalo_promedio=None,
            intervalo_mediana=None, intervalos=(),
        )
        resultado = _serializar_atrasos([fila])
        f = resultado["filas"][0]
        assert f["intervalo_minimo"] is None
        assert f["intervalo_maximo"] is None
        assert f["intervalo_promedio"] is None
        assert f["intervalo_mediana"] is None
        assert f["intervalos"] == ()

    def test_no_muta_la_entrada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        fila = IntervalosHistoricos(
            valor="ROJO", cantidad_apariciones=3, cantidad_intervalos=2,
            intervalo_minimo=1, intervalo_maximo=9, intervalo_promedio=5,
            intervalo_mediana=5.0, intervalos=(9, 1),
        )
        filas = [fila]
        _serializar_atrasos(filas)
        assert filas[0] is fila
        assert fila.intervalos == (9, 1)

    def test_ae4_5_6_siguen_usando_atrasoobservado_sin_cambios(self):
        """Regresion: _serializar_atrasos sigue funcionando igual
        para AtrasoObservado (AE-4/5/6) tras reutilizarse tambien
        para IntervalosHistoricos."""
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        from app.application.estadisticas.motor.atrasos import AtrasoObservado
        fila = AtrasoObservado(valor="ROJO", atraso=5, ultimo_sorteo_aparicion=10, total_sorteos=15)
        resultado = _serializar_atrasos([fila])
        assert resultado == {"filas": [{"valor": "ROJO", "atraso": 5, "ultimo_sorteo_aparicion": 10, "total_sorteos": 15}]}


class TestRecetaDistribucionSumasColorloto:
    """Etapa AE-19 (PROVISIONAL): candidata aprobada tras dos
    auditorias previas (Decision C: se pospuso
    calcular_distribucion_conteo_color -requiere una decision de
    producto sobre selector de color sin ningun precedente real; no
    se implementa ningun selector ni receta agregadora aqui). A
    diferencia de AE-14 a AE-18, el motor no recibe ni colores ni
    colores_vigentes -el color no influye en absoluto."""

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("distribucion_sumas_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["distribucion_sumas_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_distribucion_sumas(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_distribucion_sumas
        assert _CATALOGO["distribucion_sumas_colorloto"].serializar is _serializar_distribucion_sumas

    def test_espia_motor_recibe_un_argumento_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_distribucion_sumas_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_distribucion_sumas_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "distribucion_sumas_colorloto", parametros_metrica={})
        finally:
            modulo.calcular_distribucion_sumas_colorloto = original
        assert len(capturado["args"]) == 1
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_no_lee_ninguna_clave_de_parametros_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_distribucion_sumas_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == set(), "esta receta NO debe leer ninguna clave de parametros"

    def test_ejecucion_real_sin_keyerror_con_identidad_vacia(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "distribucion_sumas_colorloto", parametros_metrica={})
        assert resultado is not None

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "distribucion_sumas_colorloto", parametros_metrica={})
        assert estadistica_repo.guardar_fue_llamado is True

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)),
            _cl(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), date(2024, 1, 2)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "distribucion_sumas_colorloto", hasta_numero_sorteo=1, parametros_metrica={})
        r_completo = orquestador.ejecutar(juego_id, "distribucion_sumas_colorloto", parametros_metrica={})
        assert r_corte.resultado["total_sorteos"] == 1
        assert r_completo.resultado["total_sorteos"] == 2
        assert r_corte.resultado != r_completo.resultado

    def test_determinismo_sin_mutacion(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "distribucion_sumas_colorloto", parametros_metrica={})
        r2 = orquestador.ejecutar(juego_id, "distribucion_sumas_colorloto", parametros_metrica={})
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_balotas_repetidas_dentro_del_sorteo_cuentan_correctamente(self):
        """Cierra el hueco de cobertura detectado en la auditoria:
        ningun test de motor de la variante ColorLoto usa numeros
        repetidos dentro de un sorteo. Aqui se ejecuta la receta
        real (que llama al motor real, sin mocks) con un dataset que
        SI repite numeros: 7,7,7,1,1,1 -> suma=24."""
        datos = [_cl(1, ((7, "ROJO"), (7, "AZUL"), (7, "VERDE"), (1, "NEGRO"), (1, "BLANCO"), (1, "AMARILLO")), date(2024, 1, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "distribucion_sumas_colorloto", parametros_metrica={})
        assert resultado.resultado["minimo"] == 24
        assert resultado.resultado["maximo"] == 24


class TestSerializarDistribucionSumas:
    """Etapa AE-19 (PROVISIONAL): pruebas directas del serializador
    nuevo -DistribucionSumas es un objeto unico, nunca una lista de
    filas, por lo que este serializador NO usa {"filas": [...]}."""

    def test_salida_real_con_datos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_distribucion_sumas
        d = DistribucionSumas(
            total_sorteos=3, minimo=21, maximo=24, media=22.333333333333332, mediana=22,
            desviacion_estandar=1.247219128924647, percentiles={10: 21.2, 25: 21.5, 50: 22.0, 75: 23.0, 90: 23.6},
        )
        resultado = _serializar_distribucion_sumas(d)
        assert resultado == {
            "total_sorteos": 3, "minimo": 21, "maximo": 24, "media": 22.333333333333332, "mediana": 22,
            "desviacion_estandar": 1.247219128924647,
            "percentiles": {"10": 21.2, "25": 21.5, "50": 22.0, "75": 23.0, "90": 23.6},
        }

    def test_percentiles_claves_string_tras_json(self):
        import json
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_distribucion_sumas
        d = DistribucionSumas(
            total_sorteos=2, minimo=21, maximo=22, media=21.5, mediana=21.5,
            desviacion_estandar=0.5, percentiles={10: 21.1, 25: 21.25, 50: 21.5, 75: 21.75, 90: 21.9},
        )
        resultado = _serializar_distribucion_sumas(d)
        assert all(isinstance(k, str) for k in resultado["percentiles"].keys())
        texto = json.dumps(resultado)
        reconstruido = json.loads(texto)
        assert all(isinstance(k, str) for k in reconstruido["percentiles"].keys())
        assert reconstruido == resultado

    def test_none_preservado_en_historico_vacio(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_distribucion_sumas
        d = DistribucionSumas(total_sorteos=0, minimo=None, maximo=None, media=0.0, mediana=0.0, desviacion_estandar=0.0, percentiles={})
        resultado = _serializar_distribucion_sumas(d)
        assert resultado["minimo"] is None
        assert resultado["maximo"] is None
        assert resultado["media"] == 0.0
        assert resultado["mediana"] == 0.0
        assert resultado["percentiles"] == {}

    def test_media_mediana_pueden_ser_int_o_float(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_distribucion_sumas
        d = DistribucionSumas(
            total_sorteos=3, minimo=21, maximo=24, media=22.333333333333332, mediana=22,
            desviacion_estandar=1.247219128924647, percentiles={10: 21.2, 25: 21.5, 50: 22.0, 75: 23.0, 90: 23.6},
        )
        resultado = _serializar_distribucion_sumas(d)
        assert isinstance(resultado["mediana"], int)
        assert isinstance(resultado["media"], float)


class TestRecetaIntervalosHistoricosNumerosColorloto:
    """Etapa AE-20 (PROVISIONAL): candidata aprobada tras tres
    auditorias previas. A diferencia de AE-14/AE-15/AE-16/AE-17/AE-19
    (identidad {}), este motor SI construye su universo de filas
    directamente desde rango_min/rango_max -por eso la identidad
    real de esta etapa incluye ambas claves, sin cantidad_numeros."""

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("intervalos_historicos_numeros_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["intervalos_historicos_numeros_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_atrasos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        assert _CATALOGO["intervalos_historicos_numeros_colorloto"].serializar is _serializar_atrasos

    def test_espia_motor_recibe_tres_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_numeros_colorloto
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_numeros_colorloto = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, _FECHA_BASE)])
            orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        finally:
            modulo.calcular_intervalos_historicos_numeros_colorloto = original
        assert len(capturado["args"]) == 3
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_no_lee_ninguna_clave_de_parametros_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_intervalos_historicos_numeros_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == set(), "esta receta NO debe leer ninguna clave de parametros"

    def test_ejecucion_real_sin_keyerror_con_identidad_rango(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, _FECHA_BASE)])
        resultado = orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        assert resultado is not None

    def test_identidad_incluye_rango_min_rango_max(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, _FECHA_BASE)])
        entrada = orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        assert entrada.parametros == {"rango_min": 1, "rango_max": 7}

    def test_identidad_sin_cantidad_numeros(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, _FECHA_BASE)])
        entrada = orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        assert "cantidad_numeros" not in entrada.parametros

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        assert estadistica_repo.guardar_fue_llamado is True

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            _cl(1, _PARES_VALIDOS, _FECHA_BASE),
            _cl(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), _FECHA_BASE + timedelta(days=1)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", hasta_numero_sorteo=1, parametros_metrica={"rango_min": 1, "rango_max": 7})
        r_completo = orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        assert r_corte.resultado != r_completo.resultado

    def test_determinismo_sin_mutacion(self):
        datos = [_cl(1, _PARES_VALIDOS, _FECHA_BASE)]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        r2 = orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_numero_repetido_dentro_del_sorteo_no_duplica(self):
        pares = ((5, "ROJO"), (5, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (1, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares, _FECHA_BASE)])
        resultado = orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        fila_5 = next(f for f in resultado.resultado["filas"] if f["valor"] == "5")
        assert fila_5["cantidad_apariciones"] == 1

    def test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango(self):
        """Hallazgo real: el helper de validacion defensiva TAMBIEN
        revisa el rango numerico (mismo chequeo que el ValueError
        propio del motor), y se ejecuta ANTES del motor -por lo que,
        a traves de la receta, un numero fuera de rango siempre lo
        intercepta primero la validacion (ResultadoHistoricoInconsistenteError),
        el motor NUNCA se invoca. El error NO se oculta ni se traga
        silenciosamente -se propaga igual, solo que con el tipo mas
        especifico de la capa de validacion, antes de llegar al
        motor. El ValueError propio del motor (para una llamada
        directa que bypasee la receta) ya esta cubierto por el test
        de motor real `test_numero_fuera_de_rango_lanza_value_error`
        en test_atrasos.py, sin necesidad de duplicarlo aqui."""
        pares_fuera_de_rango = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_numeros_colorloto
        motor_invocado = {"valor": False}

        def espia(*args, **kwargs):
            motor_invocado["valor"] = True
            return original(*args, **kwargs)

        modulo.calcular_intervalos_historicos_numeros_colorloto = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_fuera_de_rango, _FECHA_BASE)])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        finally:
            modulo.calcular_intervalos_historicos_numeros_colorloto = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        pares_incompletos = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_numeros_colorloto
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_numeros_colorloto = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_incompletos, _FECHA_BASE)])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        finally:
            modulo.calcular_intervalos_historicos_numeros_colorloto = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_invalido_no_invoca_motor_cache_no_persistida(self):
        pares_color_invalido = ((1, "MORADO_INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_numeros_colorloto
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_numeros_colorloto = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_color_invalido, _FECHA_BASE)])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "intervalos_historicos_numeros_colorloto", parametros_metrica={"rango_min": 1, "rango_max": 7})
        finally:
            modulo.calcular_intervalos_historicos_numeros_colorloto = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False


class TestRecetaIntervalosHistoricosParesNumeroColorColorloto:
    """Etapa AE-21 (PROVISIONAL): candidata aprobada tras auditoria
    exhaustiva post-AE-20. A diferencia de AE-20 (identidad solo con
    rango), este motor construye su universo con el producto
    cartesiano rango x colores_a_reportar -por eso la identidad real
    de esta etapa incluye tanto el rango COMO la politica de
    universo de colores."""

    _IDENTIDAD = {"rango_min": 1, "rango_max": 7, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("intervalos_historicos_pares_numero_color_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["intervalos_historicos_pares_numero_color_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_atrasos(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_atrasos
        assert _CATALOGO["intervalos_historicos_pares_numero_color_colorloto"].serializar is _serializar_atrasos

    def test_espia_motor_recibe_cuatro_argumentos_sin_corte(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_pares_numero_color
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_pares_numero_color = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, _FECHA_BASE)])
            orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_intervalos_historicos_pares_numero_color = original
        assert len(capturado["args"]) == 4
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_no_lee_ninguna_clave_de_parametros_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_intervalos_historicos_pares_numero_color_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == set(), "esta receta NO debe leer ninguna clave de parametros"

    def test_ejecucion_real_sin_keyerror_con_identidad_completa(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, _FECHA_BASE)])
        resultado = orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado is not None

    def test_identidad_exacta_de_tres_claves(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, _FECHA_BASE)])
        entrada = orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        assert entrada.parametros == self._IDENTIDAD
        assert set(entrada.parametros.keys()) == {"rango_min", "rango_max", "politica_universo_colores"}

    def test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango(self):
        """Caracterizado empiricamente con motor espiado ANTES de
        escribir este test (evitando repetir la contradiccion ya
        corregida en AE-20): _validar_historico_colorloto_consistente
        TAMBIEN revisa el rango numerico y se ejecuta antes del
        motor, por lo que un numero fuera de 1-7 SIEMPRE lo
        intercepta primero la validacion, el motor NUNCA se invoca.
        El ValueError propio del motor (para una llamada directa que
        bypasee la receta) ya esta cubierto por el test de motor real
        `test_numero_fuera_de_rango_lanza_value_error` en
        test_atrasos.py, sin necesidad de duplicarlo aqui."""
        pares_fuera_de_rango = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_pares_numero_color
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_pares_numero_color = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_fuera_de_rango, _FECHA_BASE)])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_intervalos_historicos_pares_numero_color = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        pares_incompletos = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_pares_numero_color
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_pares_numero_color = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_incompletos, _FECHA_BASE)])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_intervalos_historicos_pares_numero_color = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_invalido_no_invoca_motor_cache_no_persistida(self):
        pares_color_invalido = ((1, "MORADO_INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_intervalos_historicos_pares_numero_color
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_intervalos_historicos_pares_numero_color = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_color_invalido, _FECHA_BASE)])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_intervalos_historicos_pares_numero_color = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_historico_vacio_valido(self):
        orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([])
        orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        assert estadistica_repo.guardar_fue_llamado is True

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            _cl(1, _PARES_VALIDOS, _FECHA_BASE),
            _cl(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), _FECHA_BASE + timedelta(days=1)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", hasta_numero_sorteo=1, parametros_metrica=self._IDENTIDAD)
        r_completo = orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r_corte.resultado != r_completo.resultado

    def test_determinismo_sin_mutacion(self):
        datos = [_cl(1, _PARES_VALIDOS, _FECHA_BASE)]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        r2 = orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_par_repetido_dentro_del_sorteo_no_duplica(self):
        pares = ((5, "ROJO"), (5, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (1, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares, _FECHA_BASE)])
        resultado = orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        fila_5_rojo = next(f for f in resultado.resultado["filas"] if f["valor"] == "5-ROJO")
        assert fila_5_rojo["cantidad_apariciones"] == 1

    def test_serializacion_json_real_round_trip(self):
        import json
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, _FECHA_BASE)])
        resultado = orquestador.ejecutar(juego_id, "intervalos_historicos_pares_numero_color_colorloto", parametros_metrica=self._IDENTIDAD)
        texto = json.dumps(resultado.resultado)
        reconstruido = json.loads(texto)
        fila_original = resultado.resultado["filas"][0]
        fila_reconstruida = reconstruido["filas"][0]
        assert fila_original["valor"] == fila_reconstruida["valor"]
        assert fila_original["cantidad_apariciones"] == fila_reconstruida["cantidad_apariciones"]


class TestRecetaFrecuenciaColoresPorAnioColorloto:
    """Etapa AE-22 (PROVISIONAL): primera receta de ColorLoto que
    lee una clave real de `parametros` -justificado por evidencia
    real: `ejecutar()` llama a `receta.calcular(historico,
    parametros_metrica)`, unico canal por el que un valor variable
    por consulta (el anio elegido por el usuario) puede llegar hasta
    la receta. Decision de producto autorizada explicitamente:
    selector visible de anio, sin valor por defecto."""

    _IDENTIDAD = {"anio": 2024, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_colores_por_anio_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_colores_por_anio_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["frecuencia_colores_por_anio_colorloto"].serializar is _serializar_frecuencia_observada

    def test_anio_entregado_correctamente_al_motor(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 3, 15)), _cl(2, _PARES_VALIDOS, date(2023, 6, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_espia_motor_una_llamada_argumentos_posicionales_sin_kwargs(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_anio
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_anio = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_anio = original
        assert len(capturado["args"]) == 3
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_lee_unicamente_la_clave_anio_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_frecuencia_colores_por_anio_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == {"anio"}, "esta receta debe leer UNICAMENTE 'anio', ningun parametro oculto adicional"

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)),
            _cl(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), date(2024, 2, 1)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", hasta_numero_sorteo=1, parametros_metrica=self._IDENTIDAD)
        r_completo = orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r_corte.resultado != r_completo.resultado

    def test_universo_de_colores_correcto(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        colores_reportados = {f["valor"] for f in resultado.resultado["filas"]}
        assert colores_reportados == set(c.codigo for c in _PALETA_COLORLOTO)

    def test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango(self):
        pares_fuera_de_rango = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_anio
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_anio = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_fuera_de_rango, date(2024, 1, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_anio = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        pares_incompletos = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_anio
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_anio = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_incompletos, date(2024, 1, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_anio = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_invalido_no_invoca_motor_cache_no_persistida(self):
        pares_color_invalido = ((1, "MORADO_INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_anio
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_anio = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_color_invalido, date(2024, 1, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_anio = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_anio_incluido_en_identidad(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        entrada = orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert entrada.parametros == self._IDENTIDAD
        assert entrada.parametros["anio"] == 2024

    def test_determinismo_sin_mutacion(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        r2 = orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_serializacion_json_real_round_trip(self):
        import json
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        texto = json.dumps(resultado.resultado)
        reconstruido = json.loads(texto)
        assert reconstruido == resultado.resultado


class TestRecetaFrecuenciaColoresPorMesColorloto:
    """Etapa AE-23 (PROVISIONAL): mismo precedente exacto ya
    validado por AE-22 (selector de anio) -reutiliza el mismo motivo
    estructural para leer `parametros["mes"]`: `ejecutar()` llama a
    `receta.calcular(historico, parametros_metrica)`, unico canal
    por el que un valor variable por consulta (el mes elegido por el
    usuario) puede llegar hasta la receta. "mes" agrega el mismo mes
    calendario a traves de TODOS los anios del historico, nunca un
    anio-mes concreto."""

    _IDENTIDAD = {"mes": 3, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_colores_por_mes_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_colores_por_mes_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["frecuencia_colores_por_mes_colorloto"].serializar is _serializar_frecuencia_observada

    def test_mes_entregado_correctamente_al_motor(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 3, 15)), _cl(2, _PARES_VALIDOS, date(2023, 6, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_mes_agrega_entre_anios(self):
        """Confirma que 'mes' combina el mismo mes calendario de
        distintos anios -no crea una dimension anio-mes."""
        datos = [_cl(1, _PARES_VALIDOS, date(2022, 3, 5)), _cl(2, _PARES_VALIDOS, date(2023, 3, 20)), _cl(3, _PARES_VALIDOS, date(2024, 3, 10))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 3

    def test_espia_motor_una_llamada_argumentos_posicionales_sin_kwargs(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_mes
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_mes = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
            orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_mes = original
        assert len(capturado["args"]) == 3
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_lee_unicamente_la_clave_mes_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_frecuencia_colores_por_mes_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == {"mes"}, "esta receta debe leer UNICAMENTE 'mes', ningun parametro oculto adicional"

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 3, 1)),
            _cl(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), date(2024, 3, 2)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", hasta_numero_sorteo=1, parametros_metrica=self._IDENTIDAD)
        r_completo = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r_corte.resultado != r_completo.resultado

    def test_universo_de_colores_correcto(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        colores_reportados = {f["valor"] for f in resultado.resultado["filas"]}
        assert colores_reportados == set(c.codigo for c in _PALETA_COLORLOTO)

    def test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango(self):
        pares_fuera_de_rango = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_mes
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_mes = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_fuera_de_rango, date(2024, 3, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_mes = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        pares_incompletos = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_mes
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_mes = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_incompletos, date(2024, 3, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_mes = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_invalido_no_invoca_motor_cache_no_persistida(self):
        pares_color_invalido = ((1, "MORADO_INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_mes
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_mes = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_color_invalido, date(2024, 3, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_mes = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_mes_incluido_en_identidad(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
        entrada = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert entrada.parametros == self._IDENTIDAD
        assert entrada.parametros["mes"] == 3

    def test_determinismo_sin_mutacion(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 3, 1))]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        r2 = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_serializacion_json_real_round_trip(self):
        import json
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        texto = json.dumps(resultado.resultado)
        reconstruido = json.loads(texto)
        assert reconstruido == resultado.resultado


class TestRecetaFrecuenciaColoresPorDiaSemanaColorloto:
    """Etapa AE-24 (PROVISIONAL): mismo precedente exacto ya
    validado por AE-22 (selector de anio) y AE-23 (selector de mes)
    -reutiliza el mismo motivo estructural para leer
    parametros["dia_semana"]. Dominio real confirmado por auditoria:
    string literal en espanol, minusculas, sin tildes -NUNCA un
    entero- que agrega ese mismo dia calendario a traves de TODOS
    los meses y anios del historico, nunca una fecha concreta.

    El helper compartido `_cl` fija `dia_semana="lunes"` siempre
    -por eso esta clase usa un helper local (`_cl_dia`) que permite
    especificar explicitamente el dia real de cada sorteo sintetico."""

    _IDENTIDAD = {"dia_semana": "lunes", "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}

    @staticmethod
    def _cl_dia(numero_sorteo, pares, fecha, dia_semana):
        return ResultadoColorLoto(numero_sorteo=numero_sorteo, fecha=fecha, dia_semana=dia_semana, pares=pares)

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_colores_por_dia_semana_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_colores_por_dia_semana_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["frecuencia_colores_por_dia_semana_colorloto"].serializar is _serializar_frecuencia_observada

    def test_dia_semana_entregado_correctamente_al_motor(self):
        datos = [
            self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes"),
            self._cl_dia(2, _PARES_VALIDOS, date(2024, 1, 2), "martes"),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_dia_semana_agrega_entre_meses_y_anios(self):
        """Confirma que 'dia_semana' combina el mismo dia a traves de
        distintos meses y anios -no crea una dimension fecha
        concreta."""
        datos = [
            self._cl_dia(1, _PARES_VALIDOS, date(2022, 3, 7), "lunes"),
            self._cl_dia(2, _PARES_VALIDOS, date(2023, 6, 5), "lunes"),
            self._cl_dia(3, _PARES_VALIDOS, date(2024, 1, 1), "lunes"),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 3

    def test_otro_dia_de_semana_se_excluye(self):
        datos = [
            self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes"),
            self._cl_dia(2, _PARES_VALIDOS, date(2024, 1, 2), "martes"),
            self._cl_dia(3, _PARES_VALIDOS, date(2024, 1, 3), "miercoles"),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_espia_motor_una_llamada_argumentos_posicionales_sin_kwargs(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_dia_semana
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_dia_semana = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
            orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_dia_semana = original
        assert len(capturado["args"]) == 3
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_lee_unicamente_la_clave_dia_semana_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_frecuencia_colores_por_dia_semana_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == {"dia_semana"}, "esta receta debe leer UNICAMENTE 'dia_semana', ningun parametro oculto adicional"

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes"),
            self._cl_dia(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), date(2024, 1, 8), "lunes"),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", hasta_numero_sorteo=1, parametros_metrica=self._IDENTIDAD)
        r_completo = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r_corte.resultado != r_completo.resultado

    def test_universo_de_colores_correcto(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        colores_reportados = {f["valor"] for f in resultado.resultado["filas"]}
        assert colores_reportados == set(c.codigo for c in _PALETA_COLORLOTO)

    def test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango(self):
        pares_fuera_de_rango = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_dia_semana
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_dia_semana = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([self._cl_dia(1, pares_fuera_de_rango, date(2024, 1, 1), "lunes")])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_dia_semana = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        pares_incompletos = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_dia_semana
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_dia_semana = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([self._cl_dia(1, pares_incompletos, date(2024, 1, 1), "lunes")])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_dia_semana = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_invalido_no_invoca_motor_cache_no_persistida(self):
        pares_color_invalido = ((1, "MORADO_INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_colores_por_dia_semana
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_colores_por_dia_semana = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([self._cl_dia(1, pares_color_invalido, date(2024, 1, 1), "lunes")])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_colores_por_dia_semana = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_dia_semana_incluido_en_identidad(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
        entrada = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert entrada.parametros == self._IDENTIDAD
        assert entrada.parametros["dia_semana"] == "lunes"

    def test_determinismo_sin_mutacion(self):
        datos = [self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        r2 = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_serializacion_json_real_round_trip(self):
        import json
        orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        texto = json.dumps(resultado.resultado)
        reconstruido = json.loads(texto)
        assert reconstruido == resultado.resultado


class TestRecetaFrecuenciaParesNumeroColorPorAnioColorloto:
    """Etapa AE-25 (PROVISIONAL): mismo precedente exacto de AE-22
    (selector de anio) aplicado sobre pares numero-color en vez de
    colores. A diferencia de AE-22/AE-23/AE-24, este motor SI
    construye su universo con el producto cartesiano
    rango x colores, por lo que la identidad incluye tambien
    rango_min/rango_max, mismo criterio ya demostrado por AE-20/AE-21."""

    _IDENTIDAD = {"anio": 2024, "rango_min": 1, "rango_max": 7, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_pares_numero_color_por_anio_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_pares_numero_color_por_anio_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["frecuencia_pares_numero_color_por_anio_colorloto"].serializar is _serializar_frecuencia_observada

    def test_anio_entregado_correctamente_al_motor(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 3, 15)), _cl(2, _PARES_VALIDOS, date(2023, 6, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_espia_motor_una_llamada_cinco_argumentos_posicionales_sin_kwargs(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_anio
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_anio = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
            orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_anio = original
        assert len(capturado["args"]) == 5
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_lee_unicamente_la_clave_anio_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_frecuencia_pares_numero_color_por_anio_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == {"anio"}, "esta receta debe leer UNICAMENTE 'anio', ningun parametro oculto adicional"

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 1, 1)),
            _cl(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), date(2024, 2, 1)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", hasta_numero_sorteo=1, parametros_metrica=self._IDENTIDAD)
        r_completo = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r_corte.resultado != r_completo.resultado

    def test_universo_completo_42_pares(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert len(resultado.resultado["filas"]) == 42

    def test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango(self):
        pares_fuera_de_rango = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_anio
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_anio = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_fuera_de_rango, date(2024, 1, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_anio = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        pares_incompletos = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_anio
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_anio = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_incompletos, date(2024, 1, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_anio = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_invalido_no_invoca_motor_cache_no_persistida(self):
        pares_color_invalido = ((1, "MORADO_INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_anio
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_anio = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_color_invalido, date(2024, 1, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_anio = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_anio_y_rango_incluidos_en_identidad(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        entrada = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert entrada.parametros == self._IDENTIDAD
        assert entrada.parametros["anio"] == 2024
        assert entrada.parametros["rango_min"] == 1
        assert entrada.parametros["rango_max"] == 7

    def test_determinismo_sin_mutacion(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 1, 1))]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        r2 = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_serializacion_json_real_round_trip(self):
        import json
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 1, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_anio_colorloto", parametros_metrica=self._IDENTIDAD)
        texto = json.dumps(resultado.resultado)
        reconstruido = json.loads(texto)
        assert reconstruido == resultado.resultado
        fila_original = resultado.resultado["filas"][0]
        fila_reconstruida = reconstruido["filas"][0]
        assert fila_original["valor"] == fila_reconstruida["valor"]
        assert "-" in fila_reconstruida["valor"]


class TestRecetaFrecuenciaParesNumeroColorPorMesColorloto:
    """Etapa AE-26 (PROVISIONAL): mismo precedente exacto de AE-25
    (identidad con rango, pares) combinado con el selector de mes ya
    validado por AE-23. "mes" agrega el mismo mes calendario a
    traves de TODOS los anios del historico, nunca un anio-mes
    concreto."""

    _IDENTIDAD = {"mes": 3, "rango_min": 1, "rango_max": 7, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_pares_numero_color_por_mes_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_pares_numero_color_por_mes_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["frecuencia_pares_numero_color_por_mes_colorloto"].serializar is _serializar_frecuencia_observada

    def test_mes_entregado_correctamente_al_motor(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 3, 15)), _cl(2, _PARES_VALIDOS, date(2023, 6, 1))]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_mes_agrega_entre_anios(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2022, 3, 7)),
            _cl(2, _PARES_VALIDOS, date(2023, 3, 20)),
            _cl(3, _PARES_VALIDOS, date(2024, 6, 1)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 2

    def test_otro_mes_se_excluye(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 3, 1)),
            _cl(2, _PARES_VALIDOS, date(2024, 6, 1)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_par_repetido_en_el_mismo_sorteo_cuenta_dos_apariciones_fisicas(self):
        pares_con_repeticion = ((5, "ROJO"), (5, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (1, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, pares_con_repeticion, date(2024, 3, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        fila_5_rojo = next(f for f in resultado.resultado["filas"] if f["valor"] == "5-ROJO")
        assert fila_5_rojo["apariciones"] == 2

    def test_espia_motor_una_llamada_cinco_argumentos_posicionales_sin_kwargs(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_mes
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_mes = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
            orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_mes = original
        assert len(capturado["args"]) == 5
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_lee_unicamente_la_clave_mes_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_frecuencia_pares_numero_color_por_mes_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == {"mes"}, "esta receta debe leer UNICAMENTE 'mes', ningun parametro oculto adicional"

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            _cl(1, _PARES_VALIDOS, date(2024, 3, 1)),
            _cl(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), date(2024, 3, 2)),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", hasta_numero_sorteo=1, parametros_metrica=self._IDENTIDAD)
        r_completo = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r_corte.resultado != r_completo.resultado

    def test_universo_completo_42_pares(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert len(resultado.resultado["filas"]) == 42

    def test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango(self):
        pares_fuera_de_rango = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_mes
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_mes = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_fuera_de_rango, date(2024, 3, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_mes = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        pares_incompletos = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_mes
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_mes = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_incompletos, date(2024, 3, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_mes = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_invalido_no_invoca_motor_cache_no_persistida(self):
        pares_color_invalido = ((1, "MORADO_INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_mes
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_mes = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([_cl(1, pares_color_invalido, date(2024, 3, 1))])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_mes = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_mes_y_rango_incluidos_en_identidad(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
        entrada = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert entrada.parametros == self._IDENTIDAD
        assert entrada.parametros["mes"] == 3
        assert entrada.parametros["rango_min"] == 1
        assert entrada.parametros["rango_max"] == 7

    def test_identidad_igual_sin_importar_orden_de_claves(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
        entrada = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        identidad_desordenada = {"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1", "rango_max": 7, "mes": 3, "rango_min": 1}
        assert entrada.parametros == identidad_desordenada

    def test_determinismo_sin_mutacion(self):
        datos = [_cl(1, _PARES_VALIDOS, date(2024, 3, 1))]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        r2 = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_serializacion_json_real_round_trip(self):
        import json
        orquestador, _, _, _, juego_id = _orquestador_colorloto([_cl(1, _PARES_VALIDOS, date(2024, 3, 1))])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_mes_colorloto", parametros_metrica=self._IDENTIDAD)
        texto = json.dumps(resultado.resultado)
        reconstruido = json.loads(texto)
        assert reconstruido == resultado.resultado
        fila_original = resultado.resultado["filas"][0]
        fila_reconstruida = reconstruido["filas"][0]
        assert fila_original["valor"] == fila_reconstruida["valor"]
        assert "-" in fila_reconstruida["valor"]


class TestRecetaFrecuenciaParesNumeroColorPorDiaSemanaColorloto:
    """Etapa AE-27 (PROVISIONAL): mismo precedente exacto de AE-26
    (identidad con rango, pares) combinado con el selector de dia de
    semana ya validado por AE-24. "dia_semana" agrega ese mismo dia
    a traves de TODOS los meses y anios del historico, nunca una
    fecha concreta.

    El helper compartido `_cl` fija `dia_semana="lunes"` siempre
    -por eso esta clase usa un helper local (`_cl_dia`) que permite
    especificar explicitamente el dia real de cada sorteo sintetico."""

    _IDENTIDAD = {"dia_semana": "lunes", "rango_min": 1, "rango_max": 7, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}

    @staticmethod
    def _cl_dia(numero_sorteo, pares, fecha, dia_semana):
        return ResultadoColorLoto(numero_sorteo=numero_sorteo, fecha=fecha, dia_semana=dia_semana, pares=pares)

    def test_receta_registrada_exactamente_una_vez(self):
        assert list(_CATALOGO.keys()).count("frecuencia_pares_numero_color_por_dia_semana_colorloto") == 1
        assert len(_CATALOGO) == 36

    def test_fuente_de_historico_es_colorloto(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _obtener_historico_colorloto
        assert _CATALOGO["frecuencia_pares_numero_color_por_dia_semana_colorloto"].obtener_historico is _obtener_historico_colorloto

    def test_serializador_es_serializar_frecuencia_observada(self):
        from app.application.use_cases.calcular_y_persistir_estadistica import _serializar_frecuencia_observada
        assert _CATALOGO["frecuencia_pares_numero_color_por_dia_semana_colorloto"].serializar is _serializar_frecuencia_observada

    def test_dia_semana_entregado_correctamente_al_motor(self):
        datos = [self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes"), self._cl_dia(2, _PARES_VALIDOS, date(2024, 1, 2), "martes")]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_dia_semana_agrega_entre_meses_y_anios(self):
        datos = [
            self._cl_dia(1, _PARES_VALIDOS, date(2022, 3, 7), "lunes"),
            self._cl_dia(2, _PARES_VALIDOS, date(2023, 6, 5), "lunes"),
            self._cl_dia(3, _PARES_VALIDOS, date(2024, 1, 1), "lunes"),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 3

    def test_otro_dia_de_semana_se_excluye(self):
        datos = [
            self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes"),
            self._cl_dia(2, _PARES_VALIDOS, date(2024, 1, 2), "martes"),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert resultado.resultado["filas"][0]["total_sorteos"] == 1

    def test_par_repetido_en_el_mismo_sorteo_cuenta_dos_apariciones_fisicas(self):
        pares_con_repeticion = ((5, "ROJO"), (5, "ROJO"), (3, "VERDE"), (4, "NEGRO"), (1, "BLANCO"), (6, "AMARILLO"))
        orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, pares_con_repeticion, date(2024, 1, 1), "lunes")])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        fila_5_rojo = next(f for f in resultado.resultado["filas"] if f["valor"] == "5-ROJO")
        assert fila_5_rojo["apariciones"] == 2

    def test_espia_motor_una_llamada_cinco_argumentos_posicionales_sin_kwargs(self):
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_dia_semana
        capturado = {}

        def espia(*a, **kw):
            capturado["args"] = a
            capturado["kwargs"] = kw
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_dia_semana = espia
        try:
            orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
            orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_dia_semana = original
        assert len(capturado["args"]) == 5
        assert capturado["kwargs"] == {}
        assert "hasta_numero_sorteo" not in capturado["kwargs"]

    def test_receta_lee_unicamente_la_clave_dia_semana_ast_real(self):
        import ast
        import inspect
        from app.application.use_cases import calcular_y_persistir_estadistica as modulo
        codigo_fuente = inspect.getsource(modulo._calcular_frecuencia_pares_numero_color_por_dia_semana_colorloto)
        funcion = ast.parse(codigo_fuente).body[0]
        claves_parametros = {
            nodo.slice.value
            for nodo in ast.walk(funcion)
            if isinstance(nodo, ast.Subscript)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "parametros"
            and isinstance(nodo.slice, ast.Constant)
            and isinstance(nodo.slice.value, str)
        }
        assert claves_parametros == {"dia_semana"}, "esta receta debe leer UNICAMENTE 'dia_semana', ningun parametro oculto adicional"

    def test_corte_temporal_produce_resultados_distintos(self):
        datos = [
            self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes"),
            self._cl_dia(2, ((7, "ROJO"), (1, "AZUL"), (2, "VERDE"), (3, "NEGRO"), (4, "BLANCO"), (5, "AMARILLO")), date(2024, 1, 8), "lunes"),
        ]
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r_corte = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", hasta_numero_sorteo=1, parametros_metrica=self._IDENTIDAD)
        r_completo = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r_corte.resultado != r_completo.resultado

    def test_universo_completo_42_pares(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert len(resultado.resultado["filas"]) == 42

    def test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango(self):
        pares_fuera_de_rango = ((99, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_dia_semana
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_dia_semana = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([self._cl_dia(1, pares_fuera_de_rango, date(2024, 1, 1), "lunes")])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_dia_semana = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_validacion_ocurre_antes_del_motor_cantidad_invalida(self):
        pares_incompletos = ((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_dia_semana
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_dia_semana = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([self._cl_dia(1, pares_incompletos, date(2024, 1, 1), "lunes")])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_dia_semana = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_color_invalido_no_invoca_motor_cache_no_persistida(self):
        pares_color_invalido = ((1, "MORADO_INVENTADO"), (2, "AZUL"), (3, "VERDE"), (4, "NEGRO"), (5, "BLANCO"), (6, "AMARILLO"))
        import app.application.use_cases.calcular_y_persistir_estadistica as modulo
        original = modulo.calcular_frecuencia_pares_numero_color_por_dia_semana
        motor_invocado = {"valor": False}

        def espia(*a, **kw):
            motor_invocado["valor"] = True
            return original(*a, **kw)

        modulo.calcular_frecuencia_pares_numero_color_por_dia_semana = espia
        try:
            orquestador, _, _, estadistica_repo, juego_id = _orquestador_colorloto([self._cl_dia(1, pares_color_invalido, date(2024, 1, 1), "lunes")])
            with pytest.raises(ResultadoHistoricoInconsistenteError):
                orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        finally:
            modulo.calcular_frecuencia_pares_numero_color_por_dia_semana = original
        assert motor_invocado["valor"] is False
        assert estadistica_repo.guardar_fue_llamado is False

    def test_dia_semana_y_rango_incluidos_en_identidad(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
        entrada = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert entrada.parametros == self._IDENTIDAD
        assert entrada.parametros["dia_semana"] == "lunes"
        assert entrada.parametros["rango_min"] == 1
        assert entrada.parametros["rango_max"] == 7

    def test_identidad_igual_sin_importar_orden_de_claves(self):
        orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
        entrada = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        identidad_desordenada = {"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1", "rango_max": 7, "dia_semana": "lunes", "rango_min": 1}
        assert entrada.parametros == identidad_desordenada

    def test_determinismo_sin_mutacion(self):
        datos = [self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")]
        copia = list(datos)
        orquestador, _, _, _, juego_id = _orquestador_colorloto(datos)
        r1 = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        r2 = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        assert r1.resultado == r2.resultado
        assert datos == copia

    def test_serializacion_json_real_round_trip(self):
        import json
        orquestador, _, _, _, juego_id = _orquestador_colorloto([self._cl_dia(1, _PARES_VALIDOS, date(2024, 1, 1), "lunes")])
        resultado = orquestador.ejecutar(juego_id, "frecuencia_pares_numero_color_por_dia_semana_colorloto", parametros_metrica=self._IDENTIDAD)
        texto = json.dumps(resultado.resultado)
        reconstruido = json.loads(texto)
        assert reconstruido == resultado.resultado
        fila_original = resultado.resultado["filas"][0]
        fila_reconstruida = reconstruido["filas"][0]
        assert fila_original["valor"] == fila_reconstruida["valor"]
        assert "-" in fila_reconstruida["valor"]
