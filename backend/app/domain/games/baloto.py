"""
Baloto (clásico): 5 números distintos entre 1 y 43 + 1 superbalota
entre 1 y 16.

Mecánica idéntica a Baloto Revancha (misma clase base
`StandardNumberGame`), pero es un sorteo regulatoriamente distinto
-tiene su propio reglamento y su propio acumulado. Baloto y Revancha
comparten fecha y número de sorteo oficial (el mismo evento produce
ambos resultados la misma noche), pero cada uno se modela como su
propio `Juego`/`LotteryGame` -ver docs/decisiones/baloto_revancha.md
para la justificación completa de por qué no se fusionan en una sola
entidad.
"""
from __future__ import annotations

from app.domain.games.standard_number_game import StandardNumberGame


class BalotoGame(StandardNumberGame):
    number_range = (1, 43)
    numbers_to_pick = 5
    has_superballot = True
    superballot_range = (1, 16)

    @property
    def game_code(self) -> str:
        return "BALOTO"
