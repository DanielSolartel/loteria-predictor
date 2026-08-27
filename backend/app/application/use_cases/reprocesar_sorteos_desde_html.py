"""
Caso de uso: ReprocesarSorteosDesdeHtml.

Objetivo explícito: poder reconstruir la base de datos completa
usando únicamente los archivos de `storage/html/`, sin volver a
depender del sitio oficial. La garantía de que esto produce el
MISMO resultado que sincronizar en vivo viene de reutilizar,
literalmente, las mismas piezas:

  - El parseo es `BaseConnector.reprocesar_html`, que llama al mismo
    hook `_parsear_pagina_detalle` que usa `fetch_draw_detail`
    durante una sincronización normal -no existe una segunda
    implementación de parseo para el caso "reprocesado".
  - La traducción a `Combination` es `draw_detail_a_combination`,
    el mismo mapper que usa `SincronizarSorteos`.
  - La validación de reglas de negocio y la persistencia son
    `RegistrarSorteo`/`EditarSorteo`, sin excepciones.

Semántica de upsert: si el sorteo no existe todavía, se crea
(`RegistrarSorteo`); si ya existe, se sobrescribe con lo que dice el
HTML (`EditarSorteo`) -útil para corregir datos después de arreglar
un bug de parser, sin tener que borrar manualmente primero.
"""
from __future__ import annotations

import logging

from dataclasses import dataclass, field

from app.application.exceptions import (
    JuegoNoEncontradoError,
    SorteoDuplicadoError,
    SorteoInvalidoError,
)
from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.estadistica_repository import EstadisticaRepository
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.application.interfaces.unit_of_work import UnitOfWork
from app.application.mappers.draw_detail_mapper import draw_detail_a_combination
from app.application.use_cases.editar_sorteo import EditarSorteo, EditarSorteoInput
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput


@dataclass
class ResultadoReproceso:
    draw_id: str
    numero_sorteo: int | None
    accion: str  # "creado" | "actualizado" | "fallido"
    error: str | None = None
    incompleto: bool = False


@dataclass
class ReporteReproceso:
    codigo_juego: str
    total_html_disponibles: int
    creados: int = 0
    actualizados: int = 0
    fallidos: int = 0
    incompletos: int = 0
    detalle: list[ResultadoReproceso] = field(default_factory=list)


class ReprocesarSorteosDesdeHtml:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        sorteo_repository: SorteoRepository,
        color_repository: ColorRepository,
        game_factory: GameFactory,
        obtener_conector,
        unit_of_work: UnitOfWork,
        estadistica_repository: EstadisticaRepository,
    ):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository
        self._colores = color_repository
        self._game_factory = game_factory
        self._obtener_conector = obtener_conector
        self._unit_of_work = unit_of_work
        self._estadisticas = estadistica_repository
        self._logger = logging.getLogger("importacion")  # mismo logger configurado por infraestructura; ver nota de arquitectura

    def _reprocesar_un_draw_id(self, codigo_juego: str, draw_id: str) -> ResultadoReproceso:
        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)

        conector = self._obtener_conector(codigo_juego)
        if not hasattr(conector, "reprocesar_html"):
            raise ValueError(
                f"El conector de '{codigo_juego}' no admite reprocesamiento desde HTML "
                f"(no guarda copia local de las páginas -p.ej. CsvConnector/ManualConnector)."
            )

        try:
            draw = conector.reprocesar_html(draw_id)
        except Exception as e:
            return ResultadoReproceso(draw_id=draw_id, numero_sorteo=None, accion="fallido", error=str(e))

        colores_vigentes = (
            {c.codigo: c for c in self._colores.listar_vigentes(juego.id)} if juego.tiene_color else {}
        )

        try:
            combinacion = draw_detail_a_combination(draw, juego, colores_vigentes)
        except ValueError as e:
            return ResultadoReproceso(draw_id=draw_id, numero_sorteo=draw.numero_sorteo, accion="fallido", error=str(e))

        registrar = RegistrarSorteo(
            self._juegos, self._sorteos, self._game_factory, estadistica_repository=self._estadisticas,
        )
        try:
            registrar.ejecutar(
                RegistrarSorteoInput(
                    codigo_juego=codigo_juego, numero_sorteo=draw.numero_sorteo, fecha=draw.fecha,
                    resultado=combinacion, fuente="reprocesado_desde_html",
                )
            )
            self._unit_of_work.confirmar()
            return ResultadoReproceso(
                draw_id=draw_id, numero_sorteo=draw.numero_sorteo, accion="creado",
                incompleto=bool(draw.advertencias),
            )
        except SorteoDuplicadoError:
            # Ya existe -upsert: se sobrescribe con lo que dice el HTML.
            existente = self._sorteos.obtener_por_numero(juego.id, draw.numero_sorteo)
            if existente is None:  # no debería pasar, pero no rompemos el lote por esto
                return ResultadoReproceso(
                    draw_id=draw_id, numero_sorteo=draw.numero_sorteo, accion="fallido",
                    error="Se reportó duplicado pero no se pudo localizar el sorteo existente",
                )
            editar = EditarSorteo(
                self._juegos, self._sorteos, self._game_factory, estadistica_repository=self._estadisticas,
            )
            try:
                editar.ejecutar(
                    EditarSorteoInput(
                        sorteo_id=existente.id, fecha=draw.fecha, resultado=combinacion,
                        fuente="reprocesado_desde_html",
                    )
                )
                self._unit_of_work.confirmar()
                return ResultadoReproceso(
                    draw_id=draw_id, numero_sorteo=draw.numero_sorteo, accion="actualizado",
                    incompleto=bool(draw.advertencias),
                )
            except SorteoInvalidoError as e:
                return ResultadoReproceso(
                    draw_id=draw_id, numero_sorteo=draw.numero_sorteo, accion="fallido",
                    error="; ".join(e.errores),
                )
        except SorteoInvalidoError as e:
            return ResultadoReproceso(
                draw_id=draw_id, numero_sorteo=draw.numero_sorteo, accion="fallido",
                error="; ".join(e.errores),
            )

    def ejecutar_uno(self, codigo_juego: str, draw_id: str) -> ResultadoReproceso:
        return self._reprocesar_un_draw_id(codigo_juego, draw_id)

    def ejecutar_todos(self, codigo_juego: str) -> ReporteReproceso:
        conector = self._obtener_conector(codigo_juego)
        if not hasattr(conector, "listar_html_disponibles"):
            raise ValueError(f"El conector de '{codigo_juego}' no tiene HTML almacenado para listar.")

        draw_ids = conector.listar_html_disponibles()
        reporte = ReporteReproceso(codigo_juego=codigo_juego, total_html_disponibles=len(draw_ids))

        self._logger.info("Reprocesamiento desde HTML iniciado: juego=%s, %d archivo(s)", codigo_juego, len(draw_ids))

        for draw_id in draw_ids:
            try:
                resultado = self._reprocesar_un_draw_id(codigo_juego, draw_id)
            except Exception as e:
                # Catch-all deliberado, igual que en SincronizarSorteos:
                # un fallo inesperado en UN archivo no debe abortar el
                # resto del lote. Lo ya confirmado con
                # unit_of_work.confirmar() en iteraciones previas sigue
                # durable pase lo que pase aquí.
                self._logger.error("Error inesperado reprocesando draw_id=%s (%s): %s", draw_id, codigo_juego, e)
                resultado = ResultadoReproceso(draw_id=draw_id, numero_sorteo=None, accion="fallido", error=str(e))

            reporte.detalle.append(resultado)
            if resultado.accion == "creado":
                reporte.creados += 1
            elif resultado.accion == "actualizado":
                reporte.actualizados += 1
            else:
                reporte.fallidos += 1
                self._logger.warning("Reproceso fallido para draw_id=%s (%s): %s", draw_id, codigo_juego, resultado.error)
            if resultado.incompleto:
                reporte.incompletos += 1

        self._logger.info(
            "Reprocesamiento finalizado: juego=%s creados=%d actualizados=%d fallidos=%d incompletos=%d",
            codigo_juego, reporte.creados, reporte.actualizados, reporte.fallidos, reporte.incompletos,
        )
        return reporte
