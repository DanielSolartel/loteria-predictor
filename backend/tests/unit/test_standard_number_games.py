import math

import pytest

from app.domain.games.baloto_revancha import BalotoRevanchaGame
from app.domain.games.miloto import MiLotoGame
from app.domain.value_objects.combination import Combination


class TestMiLotoGame:
    def setup_method(self):
        self.game = MiLotoGame()

    def test_sample_space_size_es_c39_5(self):
        assert self.game.sample_space_size() == math.comb(39, 5)

    def test_combinacion_valida(self):
        combinacion = Combination(numeros=(1, 2, 3, 4, 5))
        resultado = self.game.validate_draw(combinacion)
        assert resultado.is_valid
        assert resultado.errors == ()

    def test_rechaza_numero_fuera_de_rango(self):
        combinacion = Combination(numeros=(1, 2, 3, 4, 40))
        resultado = self.game.validate_draw(combinacion)
        assert not resultado.is_valid
        assert any("fuera de rango" in e for e in resultado.errors)

    def test_rechaza_cantidad_incorrecta(self):
        combinacion = Combination(numeros=(1, 2, 3, 4))
        resultado = self.game.validate_draw(combinacion)
        assert not resultado.is_valid

    def test_rechaza_superbalota_no_soportada(self):
        combinacion = Combination(numeros=(1, 2, 3, 4, 5), superbalota=3)
        resultado = self.game.validate_draw(combinacion)
        assert not resultado.is_valid
        assert any("no admite superbalota" in e for e in resultado.errors)

    def test_probabilidad_teorica_es_uniforme(self):
        combinacion = Combination(numeros=(1, 2, 3, 4, 5))
        prob = self.game.theoretical_probability(combinacion)
        assert prob == pytest.approx(1 / math.comb(39, 5))

    def test_probabilidad_es_cero_si_invalida(self):
        combinacion = Combination(numeros=(1, 2, 3, 4, 40))
        assert self.game.theoretical_probability(combinacion) == 0.0

    def test_generar_combinacion_aleatoria_es_valida(self):
        for _ in range(50):
            combinacion = self.game.generate_random_combination()
            assert self.game.validate_draw(combinacion).is_valid

    def test_game_code(self):
        assert self.game.game_code == "MILOTO"


class TestBalotoRevanchaGame:
    def setup_method(self):
        self.game = BalotoRevanchaGame()

    def test_sample_space_size_incluye_superbalota(self):
        assert self.game.sample_space_size() == math.comb(43, 5) * 16

    def test_combinacion_valida_requiere_superbalota(self):
        combinacion = Combination(numeros=(1, 2, 3, 4, 5))
        resultado = self.game.validate_draw(combinacion)
        assert not resultado.is_valid
        assert any("Falta la superbalota" in e for e in resultado.errors)

    def test_combinacion_completa_es_valida(self):
        combinacion = Combination(numeros=(1, 2, 3, 4, 5), superbalota=10)
        resultado = self.game.validate_draw(combinacion)
        assert resultado.is_valid

    def test_rechaza_superbalota_fuera_de_rango(self):
        combinacion = Combination(numeros=(1, 2, 3, 4, 5), superbalota=17)
        resultado = self.game.validate_draw(combinacion)
        assert not resultado.is_valid

    def test_baloto_revancha_es_independiente_de_miloto(self):
        # Mismo tipo de combinación numérica pero game_code y rango distintos:
        # confirma que ambos juegos son entidades separadas, no la misma
        # instancia con distinta configuración compartida por error.
        assert self.game.game_code != MiLotoGame().game_code
        assert self.game.number_range != MiLotoGame().number_range
