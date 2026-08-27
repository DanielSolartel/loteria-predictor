"""
Caso de uso: ReimportarSorteo.

Reutiliza `EditarSorteo` (Fase 1) para la persistencia -este caso de
uso solo se encarga de volver a pedirle el detalle al conector
correspondiente y traducirlo, igual que `SincronizarSorteos` pero
para un único sorteo ya existente en vez de un lote de nuevos.
"""
from __future__ import annotations

import logging

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from app.application.exceptions import ConectorNoDisponibleError, JuegoNoEncontradoError, SorteoNoEncontradoError
from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.draw_source_connector import DrawSourceConnector
from app.application.interfaces.estadistica_repository import EstadisticaRepository
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.application.use_cases.editar_sorteo import EditarSorteo, EditarSorteoInput
from app.application.use_cases.game_factory import GameFactory
from app.application.mappers.draw_detail_mapper import draw_detail_a_combination
from app.domain.entities.sorteo import Sorteo


class ReimportarSorteo:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        sorteo_repository: SorteoRepository,
        color_repository: ColorRepository,
        game_factory: GameFactory,
        obtener_conector: Callable[[str], DrawSourceConnector],
        estadistica_repository: EstadisticaRepository,
    ):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository
        self._colores = color_repository
        self._game_factory = game_factory
        self._obtener_conector = obtener_conector
        self._estadisticas = estadistica_repository
        self._logger = logging.getLogger("importacion")  # mismo logger configurado por infraestructura; ver nota de arquitectura

    def ejecutar(self, sorteo_id: UUID) -> Sorteo:
        sorteo_actual = self._sorteos.obtener_por_id(sorteo_id)
        if sorteo_actual is None:
            raise SorteoNoEncontradoError(str(sorteo_id))

        juego = self._juegos.obtener_por_id(sorteo_actual.juego_id)
        if juego is None:
            raise JuegoNoEncontradoError(str(sorteo_actual.juego_id))

        conector = self._obtener_conector(juego.codigo)
        try:
            draw = conector.fetch_draw_detail(str(sorteo_actual.numero_sorteo))
        except Exception as e:
            self._logger.error("Reimportación de sorteo %s (%s) falló: %s", sorteo_actual.numero_sorteo, juego.codigo, e)
            raise ConectorNoDisponibleError(str(e)) from e

        colores_vigentes = (
            {c.codigo: c for c in self._colores.listar_vigentes(juego.id)} if juego.tiene_color else {}
        )
        combinacion = draw_detail_a_combination(draw, juego, colores_vigentes)

        editar = EditarSorteo(
            juego_repository=self._juegos, sorteo_repository=self._sorteos, game_factory=self._game_factory,
            estadistica_repository=self._estadisticas,
        )
        self._logger.info("Reimportando sorteo %s (%s)", sorteo_actual.numero_sorteo, juego.codigo)
        return editar.ejecutar(
            EditarSorteoInput(
                sorteo_id=sorteo_id, fecha=draw.fecha, resultado=combinacion,
                fuente=f"reimportado:{type(conector).__name__}",
            )
        )
