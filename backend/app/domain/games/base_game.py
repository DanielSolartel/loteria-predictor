"""
LotteryGame: puerto central del dominio.

Ningún otro módulo del sistema (estadística, ML, simulación, API)
debe conocer las reglas concretas de MiLoto, Baloto Revancha o
ColorLoto. Todos dependen únicamente de esta interfaz. Esto es lo
que permite, más adelante, añadir un cuarto o quinto juego sin tocar
nada fuera de `domain/games`.

Nota de diseño: `theoretical_probability` calcula la probabilidad
bajo el supuesto de azar uniforme (el diseño declarado del sorteo).
No debe confundirse con probabilidades "estimadas" por un modelo de
ML -esas viven en la capa de aplicación/infraestructura de ML, que
todavía no construimos-. Aquí solo vive la verdad matemática del
diseño del juego.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.value_objects.combination import Combination
    from app.domain.value_objects.validation_result import ValidationResult


class LotteryGame(ABC):
    @property
    @abstractmethod
    def game_code(self) -> str:
        """Identificador estable del juego, p.ej. 'MILOTO'."""

    @abstractmethod
    def sample_space_size(self) -> int:
        """Tamaño del espacio muestral total de combinaciones posibles."""

    @abstractmethod
    def validate_draw(self, combination: "Combination") -> "ValidationResult":
        """Valida que una combinación cumpla las reglas del juego
        (rangos válidos, cantidad correcta de elementos, unicidad
        donde corresponda, etc.)."""

    @abstractmethod
    def theoretical_probability(self, combination: "Combination") -> float:
        """Probabilidad teórica bajo azar uniforme de que esta
        combinación exacta sea el resultado de un sorteo."""

    @abstractmethod
    def generate_random_combination(self) -> "Combination":
        """Genera una combinación aleatoria válida bajo las reglas
        del juego. Se usa como baseline de comparación para modelos
        de ML y como generador para simulaciones Monte Carlo."""

    @abstractmethod
    def combination_space_dimensions(self) -> dict:
        """Metadatos estructurales del espacio de combinaciones
        (rangos, cantidad de elementos, si tiene superbalota/color).
        El motor estadístico los usa para saber qué calcular sin
        tener if/else por juego."""
