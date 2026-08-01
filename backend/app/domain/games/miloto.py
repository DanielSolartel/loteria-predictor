"""
MiLoto: 5 números distintos entre 1 y 39, sin superbalota.
"""
from __future__ import annotations

from app.domain.games.standard_number_game import StandardNumberGame


class MiLotoGame(StandardNumberGame):
    number_range = (1, 39)
    numbers_to_pick = 5
    has_superballot = False
    superballot_range = None

    @property
    def game_code(self) -> str:
        return "MILOTO"
