"""
Baloto Revancha: 5 números distintos entre 1 y 43 + 1 superbalota
entre 1 y 16.

Es un sorteo independiente de Baloto, aunque comparte mecánica
exacta. Por eso se modela como un `game_code` propio
("BALOTO_REVANCHA"), con su propia fila en la tabla `juegos` y sus
propios sorteos -nunca se mezcla con resultados de Baloto clásico,
aunque en el futuro se implemente `BalotoGame` reutilizando esta
misma clase base.
"""
from __future__ import annotations

from app.domain.games.standard_number_game import StandardNumberGame


class BalotoRevanchaGame(StandardNumberGame):
    number_range = (1, 43)
    numbers_to_pick = 5
    has_superballot = True
    superballot_range = (1, 16)

    @property
    def game_code(self) -> str:
        return "BALOTO_REVANCHA"
