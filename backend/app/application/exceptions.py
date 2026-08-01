"""
Excepciones de la capa de aplicación.

Se distinguen de errores de validación esperados (que se comunican
con `ValidationResult`, no con excepciones) porque estas representan
condiciones que impiden completar el caso de uso por completo:
datos duplicados, juego inexistente, etc. La capa API las traduce a
códigos HTTP apropiados (409, 404, 422).
"""
from __future__ import annotations


class DominioError(Exception):
    """Base de todas las excepciones de dominio/aplicación."""


class JuegoNoEncontradoError(DominioError):
    def __init__(self, codigo_o_id: str):
        super().__init__(f"Juego no encontrado: {codigo_o_id}")


class JuegoNoSoportadoError(DominioError):
    def __init__(self, codigo: str):
        super().__init__(f"No existe implementación de LotteryGame para el código '{codigo}'")


class SorteoNoEncontradoError(DominioError):
    def __init__(self, sorteo_id: str):
        super().__init__(f"Sorteo no encontrado: {sorteo_id}")


class SorteoDuplicadoError(DominioError):
    def __init__(self, juego_id: str, numero_sorteo: int):
        super().__init__(
            f"Ya existe un sorteo para juego_id={juego_id} numero_sorteo={numero_sorteo}"
        )


class SorteoInvalidoError(DominioError):
    def __init__(self, errores: tuple[str, ...]):
        self.errores = errores
        super().__init__(f"Sorteo inválido: {'; '.join(errores)}")


class ColorNoVigenteError(DominioError):
    def __init__(self, codigo: str):
        super().__init__(f"El color '{codigo}' no está vigente para este juego")
