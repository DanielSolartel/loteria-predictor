import uuid
from datetime import date

import pytest

from app.application.exceptions import (
    JuegoNoEncontradoError,
    SorteoDuplicadoError,
    SorteoInvalidoError,
)
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput
from app.domain.entities.juego import Juego
from app.domain.value_objects.color import Color
from app.domain.value_objects.combination import Combination
from tests.unit.fakes import FakeColorRepository, FakeJuegoRepository, FakeSorteoRepository


def _crear_miloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto",
        rango_min=1, rango_max=39, cantidad_numeros=5,
        tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


@pytest.fixture
def contexto():
    miloto = _crear_miloto()
    juego_repo = FakeJuegoRepository(juegos=[miloto])
    sorteo_repo = FakeSorteoRepository()
    color_repo = FakeColorRepository()
    factory = GameFactory(color_repository=color_repo)
    caso_uso = RegistrarSorteo(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=factory
    )
    return caso_uso, miloto, sorteo_repo


class TestRegistrarSorteo:
    def test_registra_sorteo_valido(self, contexto):
        caso_uso, miloto, sorteo_repo = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="MILOTO",
            numero_sorteo=100,
            fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
            fuente="csv_historico",
        )
        sorteo = caso_uso.ejecutar(entrada)

        assert sorteo.id is not None
        assert sorteo.dia_semana == "jueves"  # 2026-07-30 es jueves
        assert sorteo_repo.contar_por_juego(miloto.id) == 1

    def test_rechaza_juego_inexistente(self, contexto):
        caso_uso, _, _ = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="INEXISTENTE",
            numero_sorteo=1,
            fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        )
        with pytest.raises(JuegoNoEncontradoError):
            caso_uso.ejecutar(entrada)

    def test_rechaza_combinacion_invalida_para_el_juego(self, contexto):
        caso_uso, _, _ = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="MILOTO",
            numero_sorteo=1,
            fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 99)),  # 99 fuera de rango
        )
        with pytest.raises(SorteoInvalidoError):
            caso_uso.ejecutar(entrada)

    def test_rechaza_sorteo_duplicado(self, contexto):
        caso_uso, _, _ = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="MILOTO",
            numero_sorteo=50,
            fecha=date(2026, 7, 20),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        )
        caso_uso.ejecutar(entrada)

        entrada_duplicada = RegistrarSorteoInput(
            codigo_juego="MILOTO",
            numero_sorteo=50,
            fecha=date(2026, 7, 27),
            resultado=Combination(numeros=(6, 7, 8, 9, 10)),
        )
        with pytest.raises(SorteoDuplicadoError):
            caso_uso.ejecutar(entrada_duplicada)


def test_game_factory_construye_colorloto_con_paleta_vigente():
    juego_id = uuid.uuid4()
    colorloto = Juego(
        id=juego_id, codigo="COLORLOTO", nombre="ColorLoto",
        rango_min=1, rango_max=7, cantidad_numeros=6,
        tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=True, permite_repeticion=True, activo=True,
    )
    paleta = [Color(codigo="ROJO", nombre="Rojo"), Color(codigo="AZUL", nombre="Azul")]
    color_repo = FakeColorRepository(colores_por_juego={juego_id: paleta})
    factory = GameFactory(color_repository=color_repo)

    lottery_game = factory.crear(colorloto)

    assert lottery_game.game_code == "COLORLOTO"
    assert {c.codigo for c in lottery_game.colors} == {"ROJO", "AZUL"}
