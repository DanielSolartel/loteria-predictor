"""
Caso de uso: SincronizarSorteos.

Este es el punto donde se unen scraping y negocio, sin mezclarlos:
- Todo lo que es "cómo obtener los datos" vino ya resuelto del
  conector (`DrawSourceConnector.sync()`), que devuelve DTOs
  (`DrawDetail`) neutrales -sin HTML, sin HTTP, sin BeautifulSoup
  visible aquí.
- Todo lo que es "es esto un sorteo válido" lo decide `RegistrarSorteo`,
  reutilizado tal cual de la Fase 1 -este caso de uso no reimplementa
  ninguna regla de negocio, solo traduce `DrawDetail` a `Combination`
  y delega.
- La tolerancia a fallos se aplica en dos niveles: el conector ya
  tolera que un sorteo individual falle al descargar/parsear: aquí
  se tolera además que un sorteo bien descargado falle la validación
  de dominio (p.ej. colores no reconocidos en ColorLoto) -en ningún
  caso una falla individual detiene la sincronización completa.
"""
from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from app.application.exceptions import (
    JuegoNoEncontradoError,
    SorteoDuplicadoError,
    SorteoInvalidoError,
)
from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.draw_source_connector import DrawSourceConnector
from app.application.interfaces.estadistica_repository import EstadisticaRepository
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sincronizacion_repository import SincronizacionRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.application.interfaces.unit_of_work import UnitOfWork
from app.application.mappers.draw_detail_mapper import draw_detail_a_combination
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput
from app.domain.entities.juego import Juego
from app.domain.entities.sincronizacion import EjecucionSincronizacion


@dataclass
class ReporteSincronizacion:
    ejecucion: EjecucionSincronizacion
    advertencias_parseo: list[str]


class SincronizarSorteos:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        sorteo_repository: SorteoRepository,
        sincronizacion_repository: SincronizacionRepository,
        color_repository: ColorRepository,
        game_factory: GameFactory,
        obtener_conector: Callable[[str], DrawSourceConnector],
        unit_of_work: UnitOfWork,
        estadistica_repository: EstadisticaRepository,
    ):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository
        self._sincronizaciones = sincronizacion_repository
        self._colores = color_repository
        self._game_factory = game_factory
        self._obtener_conector = obtener_conector
        self._unit_of_work = unit_of_work
        self._estadisticas = estadistica_repository
        self._logger = logging.getLogger("importacion")  # mismo logger configurado por infraestructura; ver nota de arquitectura

    def ejecutar(
        self, codigo_juego: str, max_paginas: int | None = None, forzar_completo: bool = False
    ) -> ReporteSincronizacion:
        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)

        conector = self._obtener_conector(codigo_juego)

        ultimo_sorteo = None if forzar_completo else self._sorteos.ultimo_sorteo(juego.id)
        ultimo_numero = ultimo_sorteo.numero_sorteo if ultimo_sorteo else None

        ejecucion = EjecucionSincronizacion(
            id=None, juego_id=juego.id, conector=type(conector).__name__,
            iniciado_en=datetime.now(timezone.utc), estado="en_progreso",
            ultimo_sorteo_importado=ultimo_numero,
        )
        ejecucion = self._sincronizaciones.guardar(ejecucion)
        self._unit_of_work.confirmar()
        self._logger.info("Sincronización iniciada: juego=%s conector=%s ultimo_conocido=%s",
                           codigo_juego, type(conector).__name__, ultimo_numero)

        try:
            resultado_conector = conector.sync(ultimo_conocido=ultimo_numero, max_paginas=max_paginas)
        except Exception as e:
            self._logger.error("Sincronización de %s abortada: %s", codigo_juego, e)
            ejecucion.marcar_fallida(str(e), datetime.now(timezone.utc))
            ejecucion = self._sincronizaciones.guardar(ejecucion)
            self._unit_of_work.confirmar()
            return ReporteSincronizacion(ejecucion=ejecucion, advertencias_parseo=[])

        colores_vigentes = {}
        if juego.tiene_color:
            colores_vigentes = {c.codigo: c for c in self._colores.listar_vigentes(juego.id)}

        registrar_sorteo = RegistrarSorteo(
            juego_repository=self._juegos, sorteo_repository=self._sorteos, game_factory=self._game_factory,
            estadistica_repository=self._estadisticas,
        )

        errores: list[dict] = [
            {"draw_id": f.draw_id, "numero_sorteo": f.numero_sorteo, "error": f.error, "etapa": "obtencion"}
            for f in resultado_conector.fallidos
        ]
        advertencias_parseo: list[str] = []
        importados = 0
        duplicados = 0
        incompletos = 0
        ultimo_importado = ultimo_numero
        total_encontrados = len(resultado_conector.draws) + len(resultado_conector.fallidos)

        for draw in resultado_conector.draws:
            if draw.advertencias:
                incompletos += 1
                advertencias_parseo.extend(f"Sorteo {draw.numero_sorteo}: {a}" for a in draw.advertencias)
            try:
                combinacion = draw_detail_a_combination(draw, juego, colores_vigentes)
                registrar_sorteo.ejecutar(
                    RegistrarSorteoInput(
                        codigo_juego=codigo_juego, numero_sorteo=draw.numero_sorteo, fecha=draw.fecha,
                        resultado=combinacion, fuente=f"scraper:{type(conector).__name__}",
                    )
                )
                # Confirmación (commit) inmediata, sorteo a sorteo -NO
                # se espera al final del request. Si algo falla más
                # adelante en este mismo lote (sorteo 851 de 1000,
                # p.ej.), este sorteo ya quedó durable: un rollback
                # posterior no puede deshacerlo. Ver
                # docs/resiliencia_sincronizacion.md.
                self._unit_of_work.confirmar()
                importados += 1
                ultimo_importado = max(ultimo_importado or 0, draw.numero_sorteo)
            except SorteoDuplicadoError:
                self._logger.info("Sorteo %s (%s) ya existía, se omite (no es un error).", draw.numero_sorteo, codigo_juego)
                duplicados += 1
                continue
            except (SorteoInvalidoError, ValueError) as e:
                self._logger.warning("[VALIDACION_FALLIDA] Sorteo %s (%s) no se pudo registrar: %s", draw.numero_sorteo, codigo_juego, e)
                errores.append({
                    "draw_id": draw.draw_id, "numero_sorteo": draw.numero_sorteo,
                    "error": str(e), "etapa": "validacion_dominio",
                })
                continue  # tolerancia a fallos: nunca detener toda la sincronización
            except Exception as e:
                # Catch-all deliberado: incluso un error totalmente
                # inesperado (p.ej. un blip de conectividad a la BD en
                # ESTE sorteo puntual) no debe abortar el resto del
                # lote. Lo ya confirmado con unit_of_work.confirmar()
                # sigue durable pase lo que pase aquí.
                self._logger.error(
                    "[ERROR_INESPERADO] Error inesperado registrando sorteo %s (%s): %s", draw.numero_sorteo, codigo_juego, e
                )
                errores.append({
                    "draw_id": draw.draw_id, "numero_sorteo": draw.numero_sorteo,
                    "error": str(e), "etapa": "inesperado",
                })
                continue

        ejecucion.marcar_completada(
            sorteos_nuevos=importados, errores=errores, duracion_ms=resultado_conector.duracion_ms,
            ultimo_sorteo_importado=ultimo_importado, finalizado_en=datetime.now(timezone.utc),
            sorteos_duplicados=duplicados, sorteos_incompletos=incompletos,
            total_sorteos_encontrados=total_encontrados,
        )
        ejecucion = self._sincronizaciones.guardar(ejecucion)
        self._unit_of_work.confirmar()

        self._logger.info(
            "Sincronización finalizada: juego=%s nuevos=%d fallidos=%d duracion_ms=%d",
            codigo_juego, importados, len(errores), resultado_conector.duracion_ms,
        )
        return ReporteSincronizacion(ejecucion=ejecucion, advertencias_parseo=advertencias_parseo)
