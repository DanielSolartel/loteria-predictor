"""
StandardNumberGame: clase intermedia abstracta.

Encapsula lo que MiLoto y Baloto Revancha tienen en común: elegir
`numbers_to_pick` números distintos de un rango [1, N], sin
reemplazo, sin importar el orden, con una superbalota opcional de un
rango independiente.

ColorLoto NO hereda de aquí: su espacio muestral permite repetición
y combina número+color como unidad, lo cual rompe el supuesto base
de "combinación clásica sin reemplazo" que esta clase encapsula.
Forzar esa herencia habría sido una abstracción incorrecta solo para
reutilizar código.
"""
from __future__ import annotations

import math
import random

from app.domain.games.base_game import LotteryGame
from app.domain.value_objects.combination import Combination
from app.domain.value_objects.validation_result import ValidationResult


class StandardNumberGame(LotteryGame):
    number_range: tuple[int, int]          # inclusive, p.ej. (1, 39)
    numbers_to_pick: int
    has_superballot: bool = False
    superballot_range: tuple[int, int] | None = None

    def sample_space_size(self) -> int:
        n = self.number_range[1] - self.number_range[0] + 1
        k = self.numbers_to_pick
        combinaciones = math.comb(n, k)
        if self.has_superballot and self.superballot_range:
            sb_n = self.superballot_range[1] - self.superballot_range[0] + 1
            return combinaciones * sb_n
        return combinaciones

    def validate_draw(self, combination: Combination) -> ValidationResult:
        errores: list[str] = []
        numeros = combination.numeros
        lo, hi = self.number_range

        if len(numeros) != self.numbers_to_pick:
            errores.append(
                f"Se esperaban {self.numbers_to_pick} números, se recibieron {len(numeros)}"
            )
        if len(set(numeros)) != len(numeros):
            errores.append("Los números no pueden repetirse")
        fuera_de_rango = [n for n in numeros if not (lo <= n <= hi)]
        if fuera_de_rango:
            errores.append(f"Números fuera de rango [{lo},{hi}]: {fuera_de_rango}")

        if self.has_superballot:
            if combination.superbalota is None:
                errores.append("Falta la superbalota, requerida para este juego")
            elif self.superballot_range:
                sb_lo, sb_hi = self.superballot_range
                if not (sb_lo <= combination.superbalota <= sb_hi):
                    errores.append(
                        f"Superbalota fuera de rango [{sb_lo},{sb_hi}]: {combination.superbalota}"
                    )
        elif combination.superbalota is not None:
            errores.append("Este juego no admite superbalota")

        return ValidationResult.ok() if not errores else ValidationResult.fail(*errores)

    def theoretical_probability(self, combination: Combination) -> float:
        validacion = self.validate_draw(combination)
        if not validacion:
            return 0.0
        return 1.0 / self.sample_space_size()

    def generate_random_combination(self) -> Combination:
        lo, hi = self.number_range
        numeros = tuple(sorted(random.sample(range(lo, hi + 1), self.numbers_to_pick)))
        superbalota = None
        if self.has_superballot and self.superballot_range:
            sb_lo, sb_hi = self.superballot_range
            superbalota = random.randint(sb_lo, sb_hi)
        return Combination(numeros=numeros, superbalota=superbalota)

    def combination_space_dimensions(self) -> dict:
        return {
            "tipo": "standard_number_game",
            "rango_numeros": self.number_range,
            "cantidad_numeros": self.numbers_to_pick,
            "tiene_superbalota": self.has_superballot,
            "rango_superbalota": self.superballot_range,
            "permite_repeticion": False,
        }
