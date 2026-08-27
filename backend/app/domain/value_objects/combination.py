"""
Value Object: Combination

Representa una combinación candidata (jugable o predicha) para
cualquiera de los juegos soportados. Los tres campos son opcionales
porque cada juego usa un subconjunto distinto:

- MiLoto                    -> solo `numeros`
- Baloto / Baloto Revancha  -> `numeros` + `superbalota` (ambos comparten mecánica)
- ColorLoto                  -> solo `pares`

No se valida aquí si la combinación es correcta para un juego
específico: esa responsabilidad es de `LotteryGame.validate_draw` /
`LotteryGame` en general, para mantener a `Combination` como un DTO
puro sin acoplarse a reglas de un juego en particular.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.value_objects.color import ColorNumberPair


@dataclass(frozen=True)
class Combination:
    numeros: tuple[int, ...] = field(default_factory=tuple)
    superbalota: int | None = None
    pares: tuple[ColorNumberPair, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.numeros and len(set(self.numeros)) != len(self.numeros):
            raise ValueError("Los números de una combinación estándar no pueden repetirse")
