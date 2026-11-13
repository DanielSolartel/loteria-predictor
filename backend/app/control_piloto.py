from dataclasses import dataclass, field
from secrets import token_hex


@dataclass
class ControlVisor:
    identificador: str = field(default_factory=lambda: token_hex(6))
    puerto: int | None = None
    sesion: bool = False
    cierre_solicitado: bool = False
    consultas: set[str] = field(default_factory=set)
    juegos_con_cartera_consultada: set[str] = field(default_factory=set)

