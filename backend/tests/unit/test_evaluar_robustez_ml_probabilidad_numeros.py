"""Tests de `EvaluarRobustezMLProbabilidadNumeros` -Etapa AE-37."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.use_cases.evaluar_robustez_ml_probabilidad_numeros import (
    CORTE_DESARROLLO_AE37,
    EvaluarRobustezMLProbabilidadNumeros,
    JuegoNoAutorizadoParaMLError,
    ResultadoPosteriorAlCorteError,
)
from app.application.use_cases.game_factory import GameFactory
from app.application.exceptions import JuegoNoEncontradoError
from app.domain.entities.juego import Juego
from tests.unit.fakes import FakeColorRepository, FakeJuegoRepository


def _historico_sintetico(n_sorteos: int, semilla: int, inicio_numero_sorteo: int = 2081) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    return [
        ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=tuple(sorted(rng.sample(range(1, 44), 5))), superbalota=rng.randint(1, 16),
        )
        for n in range(inicio_numero_sorteo, inicio_numero_sorteo + n_sorteos)
    ]


class _RepoQueRegistraElCorte:
    def __init__(self, historico: list[ResultadoNumerico]):
        self._historico = historico
        self.ultimo_hasta_numero_sorteo = "NO_LLAMADO"

    def listar_resultados_numericos(self, juego_id, hasta_numero_sorteo=None):
        self.ultimo_hasta_numero_sorteo = hasta_numero_sorteo
        if hasta_numero_sorteo is None:
            return self._historico
        return [r for r in self._historico if r.numero_sorteo <= hasta_numero_sorteo]

    def listar_resultados_colorloto(self, juego_id, hasta_numero_sorteo=None):
        return []


class _RepoQueIgnoraElCorte:
    def __init__(self, historico: list[ResultadoNumerico]):
        self._historico = historico

    def listar_resultados_numericos(self, juego_id, hasta_numero_sorteo=None):
        return self._historico

    def listar_resultados_colorloto(self, juego_id, hasta_numero_sorteo=None):
        return []


def _juego(codigo: str, rango_min: int, rango_max: int, cantidad_numeros: int, tiene_superbalota: bool) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=rango_min, rango_max=rango_max,
        cantidad_numeros=cantidad_numeros, tiene_superbalota=tiene_superbalota,
        superbalota_min=1 if tiene_superbalota else None, superbalota_max=16 if tiene_superbalota else None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


class TestCorteYRepositorio:
    def test_se_pide_exactamente_hasta_2590(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        hist = _historico_sintetico(510, semilla=1)
        repo = _RepoQueRegistraElCorte(hist)
        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[baloto]), repo, GameFactory(FakeColorRepository()),
        )
        caso_uso.ejecutar("BALOTO", semilla=7)
        assert repo.ultimo_hasta_numero_sorteo == CORTE_DESARROLLO_AE37 == 2590

    def test_corte_registrado_en_el_reporte(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        hist = _historico_sintetico(510, semilla=1)
        repo = _RepoQueRegistraElCorte(hist)
        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[baloto]), repo, GameFactory(FakeColorRepository()),
        )
        reporte = caso_uso.ejecutar("BALOTO", semilla=7)
        assert reporte.corte_desarrollo.hasta_numero_sorteo == 2590
        assert reporte.corte_desarrollo.ultimo_sorteo == 2590

    def test_repositorio_que_ignora_el_corte_provoca_error_explicito(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        hist_con_fuga = _historico_sintetico(570, semilla=1)
        repo = _RepoQueIgnoraElCorte(hist_con_fuga)
        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[baloto]), repo, GameFactory(FakeColorRepository()),
        )
        with pytest.raises(ResultadoPosteriorAlCorteError):
            caso_uso.ejecutar("BALOTO")

    def test_miloto_rechazado_antes_de_consultar_el_repositorio(self):
        class RepoQueFalla:
            def obtener_por_codigo(self, codigo):
                raise AssertionError("no deberia consultarse el repositorio para un juego no autorizado")

        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            RepoQueFalla(), _RepoQueRegistraElCorte([]), GameFactory(FakeColorRepository()),
        )
        with pytest.raises(JuegoNoAutorizadoParaMLError):
            caso_uso.ejecutar("MILOTO")

    def test_colorloto_rechazado_antes_de_consultar_el_repositorio(self):
        class RepoQueFalla:
            def obtener_por_codigo(self, codigo):
                raise AssertionError("no deberia consultarse el repositorio para un juego no autorizado")

        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            RepoQueFalla(), _RepoQueRegistraElCorte([]), GameFactory(FakeColorRepository()),
        )
        with pytest.raises(JuegoNoAutorizadoParaMLError):
            caso_uso.ejecutar("COLORLOTO")

    def test_juego_autorizado_pero_inexistente(self):
        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[]), _RepoQueRegistraElCorte([]), GameFactory(FakeColorRepository()),
        )
        with pytest.raises(JuegoNoEncontradoError):
            caso_uso.ejecutar("BALOTO")

    def test_baloto_y_revancha_permanecen_separados(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        revancha = _juego("BALOTO_REVANCHA", 1, 43, 5, True)
        hist_baloto = _historico_sintetico(510, semilla=1)
        hist_revancha = _historico_sintetico(510, semilla=2)

        class RepoPorJuego:
            def __init__(self):
                self.mapa = {baloto.id: hist_baloto, revancha.id: hist_revancha}
            def listar_resultados_numericos(self, juego_id, hasta_numero_sorteo=None):
                hist = self.mapa[juego_id]
                return [r for r in hist if hasta_numero_sorteo is None or r.numero_sorteo <= hasta_numero_sorteo]
            def listar_resultados_colorloto(self, juego_id, hasta_numero_sorteo=None):
                return []

        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[baloto, revancha]), RepoPorJuego(), GameFactory(FakeColorRepository()),
        )
        reporte_baloto = caso_uso.ejecutar("BALOTO", semilla=7)
        reporte_revancha = caso_uso.ejecutar("BALOTO_REVANCHA", semilla=7)
        assert reporte_baloto.codigo_juego == "BALOTO"
        assert reporte_revancha.codigo_juego == "BALOTO_REVANCHA"


class TestReporteCompleto:
    def test_reporte_incluye_politica_de_proximo_holdout(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        hist = _historico_sintetico(510, semilla=1)
        repo = _RepoQueRegistraElCorte(hist)
        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[baloto]), repo, GameFactory(FakeColorRepository()),
        )
        reporte = caso_uso.ejecutar("BALOTO", semilla=7)
        assert reporte.politica_proximo_holdout.holdout_consumido_inicio == 2591
        assert reporte.politica_proximo_holdout.holdout_consumido_fin == 2705
        assert reporte.politica_proximo_holdout.holdout_consumido_confirmado_no_utilizado is True
        assert reporte.politica_proximo_holdout.proximo_holdout_inicio == 2706
        assert reporte.politica_proximo_holdout.minimo_sorteos_nuevos_requeridos == 100

    def test_reporte_incluye_seis_candidatos_preregistrados(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        hist = _historico_sintetico(510, semilla=1)
        repo = _RepoQueRegistraElCorte(hist)
        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[baloto]), repo, GameFactory(FakeColorRepository()),
        )
        reporte = caso_uso.ejecutar("BALOTO", semilla=7)
        assert len(reporte.candidatos_preregistrados) == 6

    def test_reporte_incluye_dieciocho_bloques_externos(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        hist = _historico_sintetico(510, semilla=1)
        repo = _RepoQueRegistraElCorte(hist)
        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[baloto]), repo, GameFactory(FakeColorRepository()),
        )
        reporte = caso_uso.ejecutar("BALOTO", semilla=7)
        assert len(reporte.bloques_externos) == 18

    def test_no_escribe_en_ningun_repositorio(self):
        import inspect
        firma = inspect.signature(EvaluarRobustezMLProbabilidadNumeros.__init__)
        nombres_parametros = set(firma.parameters.keys()) - {"self"}
        assert nombres_parametros == {"juego_repository", "resultados_historicos_repository", "game_factory"}

    def test_version_sklearn_proviene_de_modelo(self):
        baloto = _juego("BALOTO", 1, 43, 5, True)
        hist = _historico_sintetico(510, semilla=1)
        repo = _RepoQueRegistraElCorte(hist)
        caso_uso = EvaluarRobustezMLProbabilidadNumeros(
            FakeJuegoRepository(juegos=[baloto]), repo, GameFactory(FakeColorRepository()),
        )
        reporte = caso_uso.ejecutar("BALOTO", semilla=7)
        from app.application.ml.modelo import VERSION_SKLEARN
        assert reporte.version_sklearn == VERSION_SKLEARN
