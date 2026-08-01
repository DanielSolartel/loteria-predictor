from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.domain.entities.sorteo import Sorteo


@dataclass
class ListarSorteosInput:
    codigo_juego: str
    desde: date | None = None
    hasta: date | None = None
    limite: int = 100
    offset: int = 0


@dataclass
class ListarSorteosOutput:
    sorteos: list[Sorteo]
    total: int


class ListarSorteos:
    def __init__(self, juego_repository: JuegoRepository, sorteo_repository: SorteoRepository):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository

    def ejecutar(self, datos: ListarSorteosInput) -> ListarSorteosOutput:
        juego = self._juegos.obtener_por_codigo(datos.codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(datos.codigo_juego)

        sorteos = self._sorteos.listar_por_juego(
            juego_id=juego.id,  # type: ignore[arg-type]
            desde=datos.desde,
            hasta=datos.hasta,
            limite=datos.limite,
            offset=datos.offset,
        )
        total = self._sorteos.contar_por_juego(juego.id)  # type: ignore[arg-type]
        return ListarSorteosOutput(sorteos=sorteos, total=total)
