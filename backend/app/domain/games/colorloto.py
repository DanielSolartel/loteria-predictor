"""
ColorLoto: 6 balotas, cada una es un par (número 1-7, color de una
paleta de 6 colores). Se permite repetir número y/o color entre las
6 balotas. El orden no importa para el premio mayor.

Confirmado contra fuentes oficiales (baloto.com/colorloto y cobertura
de prensa del lanzamiento, agosto 2024): "se deben elegir 6 números
del 1 al 7 y a cada uno ponerle un color... se pueden escoger balotas
del mismo color con diferente número, o balotas con el mismo número
pero diferente color". Paleta actual: amarillo, azul, rojo, verde,
blanco, negro.

Diseño clave: la paleta de colores NO está hardcodeada aquí. Se
inyecta en el constructor (`colors`) porque el reglamento puede
cambiarla; el juego solo necesita saber *cuántos* colores hay para
calcular el espacio muestral, no *cuáles* son. Quien construye este
objeto (un caso de uso / repositorio) es responsable de leer la
paleta vigente desde la tabla `colores`.

Supuesto a validar con el reglamento oficial completo (Acuerdo 02 de
2024, Coljuegos): se asume que el sorteo mismo también permite pares
repetidos (igual que la apuesta del jugador), por lo que el espacio
muestral se modela como combinaciones CON repetición de 6 elementos
tomados de (7 números x N colores) pares posibles, sin importar
orden. Si el reglamento define el sorteo físico como sin repetición
(6 balotas físicamente distintas extraídas sin reemplazo), este
cálculo deberá ajustarse -está aislado en `sample_space_size` y
`generate_random_combination`, así que el cambio no afecta al resto
del sistema.
"""
from __future__ import annotations

import math
import random

from app.domain.games.base_game import LotteryGame
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination
from app.domain.value_objects.validation_result import ValidationResult

NUMBER_RANGE = (1, 7)
BALLS_TO_PICK = 6


class ColorLotoGame(LotteryGame):
    def __init__(self, colors: list[Color]):
        colores_activos = [c for c in colors if c.activo]
        if not colores_activos:
            raise ValueError("ColorLotoGame requiere al menos un color activo")
        self._colors = colores_activos
        self._colors_by_code = {c.codigo: c for c in colores_activos}

    @property
    def game_code(self) -> str:
        return "COLORLOTO"

    @property
    def colors(self) -> list[Color]:
        return list(self._colors)

    def sample_space_size(self) -> int:
        n_pares = (NUMBER_RANGE[1] - NUMBER_RANGE[0] + 1) * len(self._colors)
        # Combinaciones con repetición: C(n + k - 1, k)
        return math.comb(n_pares + BALLS_TO_PICK - 1, BALLS_TO_PICK)

    def validate_draw(self, combination: Combination) -> ValidationResult:
        errores: list[str] = []
        pares = combination.pares
        lo, hi = NUMBER_RANGE

        if len(pares) != BALLS_TO_PICK:
            errores.append(f"Se esperaban {BALLS_TO_PICK} balotas, se recibieron {len(pares)}")

        for par in pares:
            if not (lo <= par.numero <= hi):
                errores.append(f"Número fuera de rango [{lo},{hi}]: {par.numero}")
            if par.color.codigo not in self._colors_by_code:
                errores.append(f"Color no vigente en la paleta actual: {par.color.codigo}")

        if combination.numeros or combination.superbalota is not None:
            errores.append("ColorLoto no usa 'numeros' ni 'superbalota', solo 'pares'")

        return ValidationResult.ok() if not errores else ValidationResult.fail(*errores)

    def theoretical_probability(self, combination: Combination) -> float:
        validacion = self.validate_draw(combination)
        if not validacion:
            return 0.0
        return 1.0 / self.sample_space_size()

    def generate_random_combination(self) -> Combination:
        lo, hi = NUMBER_RANGE
        pares = tuple(
            ColorNumberPair(numero=random.randint(lo, hi), color=random.choice(self._colors))
            for _ in range(BALLS_TO_PICK)
        )
        return Combination(pares=pares)

    def combination_space_dimensions(self) -> dict:
        return {
            "tipo": "colorloto",
            "rango_numeros": NUMBER_RANGE,
            "cantidad_balotas": BALLS_TO_PICK,
            "colores_disponibles": [c.codigo for c in self._colors],
            "permite_repeticion": True,
        }
