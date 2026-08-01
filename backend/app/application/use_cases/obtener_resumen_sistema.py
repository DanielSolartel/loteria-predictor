"""
Caso de uso: ObtenerResumenSistema.

Agrega métricas simples across todos los juegos activos, para el
dashboard. Vive en la capa de aplicación -no en el router- porque
"sumar sorteos de todos los juegos activos" y "encontrar la fecha
más reciente" es lógica de negocio, aunque sea sencilla; el router
web no debe calcularla directamente.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository


@dataclass
class ResumenSistema:
    total_sorteos: int
    ultima_actualizacion: date | None


class ObtenerResumenSistema:
    def __init__(self, juego_repository: JuegoRepository, sorteo_repository: SorteoRepository):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository

    def ejecutar(self) -> ResumenSistema:
        total = 0
        fechas: list[date] = []
        for juego in self._juegos.listar_activos():
            total += self._sorteos.contar_por_juego(juego.id)  # type: ignore[arg-type]
            ultimo = self._sorteos.ultimo_sorteo(juego.id)  # type: ignore[arg-type]
            if ultimo:
                fechas.append(ultimo.fecha)

        return ResumenSistema(
            total_sorteos=total,
            ultima_actualizacion=max(fechas) if fechas else None,
        )
