"""
Caso de uso: ListarSorteos.

Convierte los criterios de consulta (fecha, número, orden,
paginación) en un `FiltroSorteos` y delega en el repositorio, que
ejecuta la paginación con LIMIT/OFFSET real en PostgreSQL -en ningún
punto de este caso de uso se cargan todos los sorteos de un juego en
memoria para después recortar en Python. El total también se calcula
con una consulta `COUNT` separada (respetando los mismos filtros),
para poder mostrar "Mostrando X-Y de Z" sin materializar Z filas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import FiltroSorteos, SorteoRepository
from app.domain.entities.sorteo import Sorteo


@dataclass
class ListarSorteosInput:
    codigo_juego: str
    desde: date | None = None
    hasta: date | None = None
    numero_desde: int | None = None
    numero_hasta: int | None = None
    orden_campo: str = "fecha"
    orden_direccion: str = "desc"
    limite: int = 100
    offset: int = 0


@dataclass
class ListarSorteosOutput:
    sorteos: list[Sorteo]
    total: int  # respeta los filtros activos; es el total que importa para paginar


class ListarSorteos:
    def __init__(self, juego_repository: JuegoRepository, sorteo_repository: SorteoRepository):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository

    def ejecutar(self, datos: ListarSorteosInput) -> ListarSorteosOutput:
        juego = self._juegos.obtener_por_codigo(datos.codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(datos.codigo_juego)

        filtro = FiltroSorteos(
            desde=datos.desde,
            hasta=datos.hasta,
            numero_desde=datos.numero_desde,
            numero_hasta=datos.numero_hasta,
            orden_campo=datos.orden_campo,
            orden_direccion=datos.orden_direccion,
            limite=datos.limite,
            offset=datos.offset,
        )

        sorteos = self._sorteos.listar_por_juego(juego.id, filtro)  # type: ignore[arg-type]
        total = self._sorteos.contar_por_juego(juego.id, filtro)  # type: ignore[arg-type]

        return ListarSorteosOutput(sorteos=sorteos, total=total)
