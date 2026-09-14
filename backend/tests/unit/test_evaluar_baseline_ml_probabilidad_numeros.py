"""Tests de `EvaluarBaselineMLProbabilidadNumeros` -Etapa AE-36."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.use_cases.evaluar_baseline_ml_probabilidad_numeros import (
    JUEGOS_AUTORIZADOS_AE36,
    EvaluarBaselineMLProbabilidadNumeros,
    JuegoNoAutorizadoParaMLError,
)
from app.application.use_cases.game_factory import GameFactory
from app.application.exceptions import JuegoNoEncontradoError
from app.domain.entities.juego import Juego
from tests.unit.fakes import FakeColorRepository, FakeJuegoRepository


def _historico_sintetico(n_sorteos: int, semilla: int = 55, rango_max: int = 43) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    return [
        ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=tuple(sorted(rng.sample(range(1, rango_max + 1), 5))), superbalota=rng.randint(1, 16),
        )
        for n in range(1, n_sorteos + 1)
    ]


class _FakeResultadosHistoricosRepository:
    def __init__(self, historico_por_juego: dict):
        self._historico = historico_por_juego

    def listar_resultados_numericos(self, juego_id, hasta_numero_sorteo=None):
        return self._historico.get(juego_id, [])

    def listar_resultados_colorloto(self, juego_id, hasta_numero_sorteo=None):
        return []


def _juego(codigo: str, rango_min: int, rango_max: int, cantidad_numeros: int, tiene_superbalota: bool) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=rango_min, rango_max=rango_max,
        cantidad_numeros=cantidad_numeros, tiene_superbalota=tiene_superbalota,
        superbalota_min=1 if tiene_superbalota else None, superbalota_max=16 if tiene_superbalota else None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


class TestJuegosAutorizados:
    def test_conjunto_cerrado_exacto(self):
        assert JUEGOS_AUTORIZADOS_AE36 == frozenset({"BALOTO", "BALOTO_REVANCHA"})


class TestEvaluarBaselineMLProbabilidadNumeros:
    def _construir_caso_de_uso(self, juegos, historico_por_juego):
        juego_repo = FakeJuegoRepository(juegos=juegos)
        resultados_repo = _FakeResultadosHistoricosRepository(historico_por_juego)
        game_factory = GameFactory(FakeColorRepository())
        return EvaluarBaselineMLProbabilidadNumeros(juego_repo, resultados_repo, game_factory)

    def test_baloto_autorizado_produce_reporte(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        hist = _historico_sintetico(250)
        caso_uso = self._construir_caso_de_uso([baloto], {baloto.id: hist})
        reporte = caso_uso.ejecutar("BALOTO", semilla=7)
        assert reporte.codigo_juego == "BALOTO"
        assert reporte.rango_min == 1 and reporte.rango_max == 43

    def test_baloto_revancha_autorizado_produce_reporte(self):
        revancha = _juego("BALOTO_REVANCHA", 1, 43, 5, True)
        hist = _historico_sintetico(250, semilla=88)
        caso_uso = self._construir_caso_de_uso([revancha], {revancha.id: hist})
        reporte = caso_uso.ejecutar("BALOTO_REVANCHA", semilla=7)
        assert reporte.codigo_juego == "BALOTO_REVANCHA"

    def test_miloto_rechazado_explicitamente(self):
        miloto = _juego("MILOTO", 1, 39, 5, False)
        caso_uso = self._construir_caso_de_uso([miloto], {miloto.id: []})
        with pytest.raises(JuegoNoAutorizadoParaMLError):
            caso_uso.ejecutar("MILOTO")

    def test_colorloto_rechazado_explicitamente(self):
        caso_uso = self._construir_caso_de_uso([], {})
        with pytest.raises(JuegoNoAutorizadoParaMLError):
            caso_uso.ejecutar("COLORLOTO")

    def test_rechazo_de_miloto_ocurre_antes_de_consultar_el_repositorio(self):
        """El conjunto cerrado se verifica ANTES de tocar
        `JuegoRepository` -un codigo no autorizado nunca dispara ni
        siquiera una consulta al repositorio real."""

        class RepoQueFalla:
            def obtener_por_codigo(self, codigo):
                raise AssertionError("no deberia consultarse el repositorio para un juego no autorizado")

        caso_uso = EvaluarBaselineMLProbabilidadNumeros(
            RepoQueFalla(), _FakeResultadosHistoricosRepository({}), GameFactory(FakeColorRepository()),
        )
        with pytest.raises(JuegoNoAutorizadoParaMLError):
            caso_uso.ejecutar("MILOTO")

    def test_juego_autorizado_pero_inexistente_en_el_repositorio(self):
        caso_uso = self._construir_caso_de_uso([], {})
        with pytest.raises(JuegoNoEncontradoError):
            caso_uso.ejecutar("BALOTO")

    def test_no_persiste_nada_en_ningun_lado(self):
        """El reporte devuelto es puramente en memoria -no existe
        ningun repositorio de escritura en las dependencias del
        caso de uso, confirmado por su propia firma de constructor."""
        import inspect
        firma = inspect.signature(EvaluarBaselineMLProbabilidadNumeros.__init__)
        nombres_parametros = set(firma.parameters.keys()) - {"self"}
        assert nombres_parametros == {"juego_repository", "resultados_historicos_repository", "game_factory"}
