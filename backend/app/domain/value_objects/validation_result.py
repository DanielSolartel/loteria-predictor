"""
Value Object: ValidationResult

Resultado inmutable de validar un sorteo o una combinación contra las
reglas de un juego. No contiene lógica de negocio propia: es un DTO
interno del dominio que evita usar excepciones para flujos de
validación esperados (una combinación inválida no es un error del
sistema, es un resultado de negocio válido).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def ok() -> "ValidationResult":
        return ValidationResult(is_valid=True, errors=())

    @staticmethod
    def fail(*errors: str) -> "ValidationResult":
        return ValidationResult(is_valid=False, errors=tuple(errors))

    def __bool__(self) -> bool:
        return self.is_valid
