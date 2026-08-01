"""
Value Objects: Color y ColorNumberPair

`Color` no es un Enum fijo en código a propósito: Coljuegos puede
modificar la paleta de ColorLoto en el futuro (agregar/retirar
colores), y un Enum obligaría a un despliegue de código para eso.
Por eso `Color` es un Value Object que se hidrata desde la tabla
`colores` en infraestructura, con vigencia temporal (vigente_desde /
vigente_hasta) para no romper el histórico si la paleta cambia.

`ColorNumberPair` modela la unidad atómica de una balota de
ColorLoto: un número (1-7) ligado a un color. Se modela como un solo
Value Object -no como dos campos sueltos- porque estadísticamente el
par es lo relevante (frecuencia del par "rojo-5", no solo de "rojo"
o de "5" por separado).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Color:
    codigo: str          # p.ej. "ROJO" - identificador estable, no cambia aunque cambie el nombre visible
    nombre: str           # p.ej. "Rojo" - nombre de despliegue, puede traducirse o ajustarse
    activo: bool = True
    vigente_desde: date | None = None
    vigente_hasta: date | None = None

    def esta_vigente_en(self, fecha: date) -> bool:
        if self.vigente_desde and fecha < self.vigente_desde:
            return False
        if self.vigente_hasta and fecha > self.vigente_hasta:
            return False
        return True


@dataclass(frozen=True)
class ColorNumberPair:
    numero: int
    color: Color

    def __post_init__(self) -> None:
        if self.numero < 1:
            raise ValueError("El número de una balota de ColorLoto debe ser >= 1")
