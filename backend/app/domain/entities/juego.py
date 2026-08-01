"""
Entidad Juego.

Representa la fila de catálogo en la tabla `juegos`. Es la
contraparte persistente de una implementación de `LotteryGame`: la
entidad `Juego` se guarda en base de datos, mientras que
`LotteryGame` (MiLotoGame, etc.) es la clase de dominio que sabe
*razonar* con esas reglas. Un caso de uso típico lee un `Juego` desde
el repositorio y construye la instancia correcta de `LotteryGame` a
partir de su `codigo` (ver `GameFactory` en application/use_cases).
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass
class Juego:
    id: UUID | None
    codigo: str
    nombre: str
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    tiene_superbalota: bool
    superbalota_min: int | None
    superbalota_max: int | None
    tiene_color: bool
    permite_repeticion: bool
    activo: bool = True
