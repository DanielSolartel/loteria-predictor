"""
Caso de uso: ObtenerSorteoConPareja.

Baloto y Revancha se modelan como juegos independientes (ver
ARCHITECTURE.md, sección "Baloto y Revancha"), relacionados
únicamente por compartir `numero_sorteo` -el mismo evento oficial
produce ambos resultados la misma noche. Este caso de uso es el
único lugar del sistema que conoce esa relación: dado un sorteo de
cualquiera de las dos familias, busca su "pareja" (el sorteo del
mismo número en el juego relacionado) para que la interfaz pueda
mostrar ambos resultados juntos, dejando claro que pertenecen al
mismo sorteo.

Para MiLoto y ColorLoto (que no tienen pareja), `sorteo_pareja`
siempre es `None` -el caso de uso es completamente transparente para
el resto de los juegos, no les añade ningún comportamiento.

Es deliberado que la pareja pueda no existir todavía (`None`): si
solo se ha sincronizado una de las dos familias, la interfaz debe
poder mostrarlo con claridad ("Revancha: aún no importado") en vez
de fallar.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.exceptions import JuegoNoEncontradoError, SorteoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo

# Único lugar del sistema que sabe qué juego es "pareja" de cuál.
# Agregar una relación nueva en el futuro (si algún día se modela
# "Baloto Día" y "Baloto Noche", por ejemplo) es agregar una entrada
# aquí, no tocar el resto del sistema.
PAREJAS_DE_JUEGO: dict[str, str] = {
    "BALOTO": "BALOTO_REVANCHA",
    "BALOTO_REVANCHA": "BALOTO",
}


@dataclass
class SorteoConPareja:
    sorteo: Sorteo
    juego: Juego
    sorteo_pareja: Sorteo | None
    juego_pareja: Juego | None


class ObtenerSorteoConPareja:
    def __init__(self, sorteo_repository: SorteoRepository, juego_repository: JuegoRepository):
        self._sorteos = sorteo_repository
        self._juegos = juego_repository

    def ejecutar(self, sorteo_id: UUID) -> SorteoConPareja:
        sorteo = self._sorteos.obtener_por_id(sorteo_id)
        if sorteo is None:
            raise SorteoNoEncontradoError(str(sorteo_id))

        juego = self._juegos.obtener_por_id(sorteo.juego_id)
        if juego is None:
            raise JuegoNoEncontradoError(str(sorteo.juego_id))

        codigo_pareja = PAREJAS_DE_JUEGO.get(juego.codigo)
        juego_pareja: Juego | None = None
        sorteo_pareja: Sorteo | None = None

        if codigo_pareja:
            juego_pareja = self._juegos.obtener_por_codigo(codigo_pareja)
            if juego_pareja is not None:
                sorteo_pareja = self._sorteos.obtener_por_numero(juego_pareja.id, sorteo.numero_sorteo)  # type: ignore[arg-type]

        return SorteoConPareja(sorteo=sorteo, juego=juego, sorteo_pareja=sorteo_pareja, juego_pareja=juego_pareja)
