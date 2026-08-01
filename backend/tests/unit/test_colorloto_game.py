import math

import pytest

from app.domain.games.colorloto import ColorLotoGame
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination

PALETA_OFICIAL = [
    Color(codigo="AMARILLO", nombre="Amarillo"),
    Color(codigo="AZUL", nombre="Azul"),
    Color(codigo="ROJO", nombre="Rojo"),
    Color(codigo="VERDE", nombre="Verde"),
    Color(codigo="BLANCO", nombre="Blanco"),
    Color(codigo="NEGRO", nombre="Negro"),
]


class TestColorLotoGame:
    def setup_method(self):
        self.game = ColorLotoGame(colors=PALETA_OFICIAL)

    def test_requiere_al_menos_un_color_activo(self):
        with pytest.raises(ValueError):
            ColorLotoGame(colors=[Color(codigo="ROJO", nombre="Rojo", activo=False)])

    def test_sample_space_size_combinaciones_con_repeticion(self):
        # 7 numeros x 6 colores = 42 pares posibles; C(42+6-1, 6)
        esperado = math.comb(42 + 6 - 1, 6)
        assert self.game.sample_space_size() == esperado

    def test_combinacion_valida_permite_numero_repetido(self):
        rojo = PALETA_OFICIAL[2]
        pares = tuple(ColorNumberPair(numero=5, color=rojo) for _ in range(6))
        combinacion = Combination(pares=pares)
        resultado = self.game.validate_draw(combinacion)
        assert resultado.is_valid

    def test_combinacion_valida_permite_color_repetido_numero_distinto(self):
        rojo = PALETA_OFICIAL[2]
        pares = tuple(ColorNumberPair(numero=n, color=rojo) for n in range(1, 7))
        combinacion = Combination(pares=pares)
        assert self.game.validate_draw(combinacion).is_valid

    def test_rechaza_cantidad_incorrecta_de_balotas(self):
        rojo = PALETA_OFICIAL[2]
        pares = tuple(ColorNumberPair(numero=1, color=rojo) for _ in range(5))
        combinacion = Combination(pares=pares)
        resultado = self.game.validate_draw(combinacion)
        assert not resultado.is_valid

    def test_rechaza_numero_fuera_de_rango_1_7(self):
        rojo = PALETA_OFICIAL[2]
        pares = tuple(ColorNumberPair(numero=8, color=rojo) for _ in range(6))
        combinacion = Combination(pares=pares)
        resultado = self.game.validate_draw(combinacion)
        assert not resultado.is_valid
        assert any("fuera de rango" in e for e in resultado.errors)

    def test_rechaza_color_no_vigente(self):
        color_retirado = Color(codigo="MORADO", nombre="Morado")
        pares = tuple(ColorNumberPair(numero=1, color=color_retirado) for _ in range(6))
        combinacion = Combination(pares=pares)
        resultado = self.game.validate_draw(combinacion)
        assert not resultado.is_valid
        assert any("no vigente" in e for e in resultado.errors)

    def test_paleta_reducida_cambia_espacio_muestral(self):
        # Confirma que la paleta es inyectable: con menos colores el
        # espacio muestral se recalcula, no queda hardcodeado a 6.
        juego_reducido = ColorLotoGame(colors=PALETA_OFICIAL[:3])
        assert juego_reducido.sample_space_size() != self.game.sample_space_size()

    def test_generar_combinacion_aleatoria_es_valida(self):
        for _ in range(30):
            combinacion = self.game.generate_random_combination()
            assert self.game.validate_draw(combinacion).is_valid

    def test_game_code(self):
        assert self.game.game_code == "COLORLOTO"
