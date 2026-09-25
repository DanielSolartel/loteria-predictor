"""Tests del corte congelado de `EvaluarBaselineMLProbabilidadNumeros`
-mantenimiento posterior a AE-42, PROVISIONAL.

El caso de uso de AE-36 consultaba el historico completo sin
`hasta_numero_sorteo`: con sorteos cargados desde `2706`, una nueva
ejecucion desplazaba el test final de `2591..2705` a `2597..2713`,
evaluando contra etiquetas del holdout. Todos los historicos de este
archivo son sinteticos -numeracion `2081..2713` elegida solo para
reproducir la forma del caso real, nunca resultados reales."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.evaluacion import evaluar_juego
from app.application.use_cases import evaluar_baseline_ml_probabilidad_numeros as modulo_ae36
from app.application.use_cases.evaluar_baseline_ml_probabilidad_numeros import (
    EvaluarBaselineMLProbabilidadNumeros,
    JuegoNoAutorizadoParaMLError,
)
from app.application.use_cases.game_factory import GameFactory
from app.domain.entities.juego import Juego
from tests.unit.fakes import FakeColorRepository, FakeJuegoRepository

PRIMER_SORTEO = 2081
ULTIMO_SORTEO_CONTRATO_AE36 = 2705
ULTIMO_SORTEO_CON_HOLDOUT = 2713


def _historico_sintetico(desde: int, hasta: int, semilla: int = 55) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    return [
        ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=tuple(sorted(rng.sample(range(1, 44), 5))), superbalota=rng.randint(1, 16),
        )
        for n in range(desde, hasta + 1)
    ]


def _juego(codigo: str) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43,
        cantidad_numeros=5, tiene_superbalota=True, superbalota_min=1, superbalota_max=16,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


class _RepoQueRespetaCorte:
    """Simula el filtro SQL real (`numero_sorteo <= corte`) y registra
    cada corte solicitado."""

    def __init__(self, historico_por_juego: dict):
        self._historico = historico_por_juego
        self.cortes_solicitados: list[int | None] = []

    def listar_resultados_numericos(self, juego_id, hasta_numero_sorteo=None):
        self.cortes_solicitados.append(hasta_numero_sorteo)
        historico = self._historico.get(juego_id, [])
        if hasta_numero_sorteo is None:
            return list(historico)
        return [r for r in historico if r.numero_sorteo <= hasta_numero_sorteo]

    def listar_resultados_colorloto(self, juego_id, hasta_numero_sorteo=None):
        return []


class _RepoQueIgnoraCorte:
    """Simula un repositorio defectuoso que ignora el corte."""

    def __init__(self, historico_por_juego: dict):
        self._historico = historico_por_juego

    def listar_resultados_numericos(self, juego_id, hasta_numero_sorteo=None):
        return list(self._historico.get(juego_id, []))

    def listar_resultados_colorloto(self, juego_id, hasta_numero_sorteo=None):
        return []


def _caso_de_uso(juego: Juego, repo) -> EvaluarBaselineMLProbabilidadNumeros:
    return EvaluarBaselineMLProbabilidadNumeros(
        FakeJuegoRepository(juegos=[juego]), repo, GameFactory(FakeColorRepository()),
    )


class TestConstanteCorteContratoAE36:
    def test_corte_congelado_en_2705(self):
        assert getattr(modulo_ae36, "CORTE_CONTRATO_AE36", None) == ULTIMO_SORTEO_CONTRATO_AE36


class TestCorteSolicitadoEnConsulta:
    @pytest.mark.parametrize("codigo", ["BALOTO", "BALOTO_REVANCHA"])
    def test_solicita_corte_2705_y_test_final_termina_en_2705(self, codigo):
        juego = _juego(codigo)
        repo = _RepoQueRespetaCorte(
            {juego.id: _historico_sintetico(PRIMER_SORTEO, ULTIMO_SORTEO_CON_HOLDOUT)}
        )
        reporte = _caso_de_uso(juego, repo).ejecutar(codigo, semilla=42)

        assert repo.cortes_solicitados == [ULTIMO_SORTEO_CONTRATO_AE36]
        assert reporte.total_sorteos_originales == ULTIMO_SORTEO_CONTRATO_AE36 - PRIMER_SORTEO + 1
        assert reporte.limites.test_inicio == 2591
        assert reporte.limites.test_fin == ULTIMO_SORTEO_CONTRATO_AE36


class TestRechazoDefensivo:
    @pytest.mark.parametrize("codigo", ["BALOTO", "BALOTO_REVANCHA"])
    def test_repositorio_que_ignora_corte_detiene_antes_de_evaluar(self, codigo, monkeypatch):
        error = getattr(modulo_ae36, "ResultadoPosteriorAlCorteError", None)
        assert error is not None, "falta ResultadoPosteriorAlCorteError en el caso de uso de AE-36"

        llamadas = []
        monkeypatch.setattr(modulo_ae36, "evaluar_juego", lambda *a, **k: llamadas.append(a))

        juego = _juego(codigo)
        repo = _RepoQueIgnoraCorte(
            {juego.id: _historico_sintetico(PRIMER_SORTEO, ULTIMO_SORTEO_CON_HOLDOUT)}
        )
        with pytest.raises(error) as excinfo:
            _caso_de_uso(juego, repo).ejecutar(codigo)

        assert llamadas == []
        mensaje = str(excinfo.value)
        assert codigo in mensaje and "2706" in mensaje and "2705" in mensaje

    def test_un_solo_sorteo_posterior_basta_para_rechazar(self, monkeypatch):
        error = getattr(modulo_ae36, "ResultadoPosteriorAlCorteError", None)
        assert error is not None
        monkeypatch.setattr(modulo_ae36, "evaluar_juego", lambda *a, **k: pytest.fail("no debe evaluarse"))

        juego = _juego("BALOTO")
        historico = _historico_sintetico(PRIMER_SORTEO, ULTIMO_SORTEO_CONTRATO_AE36)
        historico.append(_historico_sintetico(2706, 2706, semilla=9)[0])
        with pytest.raises(error):
            _caso_de_uso(juego, _RepoQueIgnoraCorte({juego.id: historico})).ejecutar("BALOTO")


class TestInvarianciaAnteSorteosPosteriores:
    def test_mismo_reporte_con_o_sin_sorteos_desde_2706(self):
        juego = _juego("BALOTO")
        contrato = _historico_sintetico(PRIMER_SORTEO, ULTIMO_SORTEO_CONTRATO_AE36)
        con_holdout = _historico_sintetico(PRIMER_SORTEO, ULTIMO_SORTEO_CON_HOLDOUT)
        assert con_holdout[: len(contrato)] == contrato

        reporte_contrato = _caso_de_uso(juego, _RepoQueRespetaCorte({juego.id: contrato})).ejecutar("BALOTO")
        reporte_holdout = _caso_de_uso(juego, _RepoQueRespetaCorte({juego.id: con_holdout})).ejecutar("BALOTO")

        assert reporte_holdout == reporte_contrato


class TestRegresionesSinCambio:
    def test_historico_hasta_2705_produce_el_mismo_reporte_que_la_funcion_pura(self):
        juego = _juego("BALOTO_REVANCHA")
        historico = _historico_sintetico(PRIMER_SORTEO, ULTIMO_SORTEO_CONTRATO_AE36, semilla=88)
        reporte = _caso_de_uso(juego, _RepoQueRespetaCorte({juego.id: historico})).ejecutar(
            "BALOTO_REVANCHA", semilla=42,
        )
        assert reporte == evaluar_juego(historico, 1, 43, 5, "BALOTO_REVANCHA", semilla=42)

    @pytest.mark.parametrize("codigo", ["MILOTO", "COLORLOTO"])
    def test_juegos_no_autorizados_se_rechazan_antes_de_consultar(self, codigo):
        class RepoQueFalla:
            def obtener_por_codigo(self, codigo):
                raise AssertionError("no deberia consultarse")

            def listar_resultados_numericos(self, *a, **k):
                raise AssertionError("no deberia consultarse")

        caso = EvaluarBaselineMLProbabilidadNumeros(RepoQueFalla(), RepoQueFalla(), GameFactory(FakeColorRepository()))
        with pytest.raises(JuegoNoAutorizadoParaMLError):
            caso.ejecutar(codigo)
