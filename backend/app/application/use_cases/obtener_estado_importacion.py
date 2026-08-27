"""
Caso de uso: ObtenerEstadoImportacion.

`verificar_salud=False` (usado por la carga inicial del panel web)
evita llamar a `conector.health_check()` -que es una petición HTTP
real al sitio origen- para no bloquear el renderizado de la página
con hasta N * timeout segundos si el origen está lento o caído. El
router web pide la salud de cada conector por separado, vía HTMX,
una vez que la página ya se muestra (ver `/importacion/salud/{codigo}`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.application.interfaces.draw_source_connector import DrawSourceConnector, HealthStatus
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sincronizacion_repository import SincronizacionRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.domain.entities.juego import Juego
from app.domain.entities.sincronizacion import EjecucionSincronizacion


@dataclass
class EstadoConector:
    juego: Juego
    salud: HealthStatus | None
    ultima_ejecucion: EjecucionSincronizacion | None
    total_sorteos_almacenados: int
    ultimo_sorteo_almacenado: int | None


class ObtenerEstadoImportacion:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        sorteo_repository: SorteoRepository,
        sincronizacion_repository: SincronizacionRepository,
        obtener_conector: Callable[[str], DrawSourceConnector],
    ):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository
        self._sincronizaciones = sincronizacion_repository
        self._obtener_conector = obtener_conector

    def ejecutar(self, verificar_salud: bool = True) -> list[EstadoConector]:
        estados = []
        for juego in self._juegos.listar_activos():
            salud = self._obtener_conector(juego.codigo).health_check() if verificar_salud else None
            ultimo = self._sorteos.ultimo_sorteo(juego.id)
            estados.append(
                EstadoConector(
                    juego=juego, salud=salud,
                    ultima_ejecucion=self._sincronizaciones.obtener_ultima(juego.id),
                    total_sorteos_almacenados=self._sorteos.contar_por_juego(juego.id),
                    ultimo_sorteo_almacenado=ultimo.numero_sorteo if ultimo else None,
                )
            )
        return estados

    def verificar_salud_de(self, codigo_juego: str) -> HealthStatus:
        return self._obtener_conector(codigo_juego).health_check()
