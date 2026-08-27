"""
Caso de uso: GenerarReporteCalidadDatos.

Combina dos fuentes distintas, a propósito:

  1. La última `EjecucionSincronizacion` -qué pasó en la corrida más
     reciente (encontrados, importados, duplicados, fallidos,
     incompletos, tiempo).
  2. El estado real y actual de la tabla `sorteos` -rango histórico
     (primer/último sorteo) y cobertura (huecos en la numeración),
     calculado con `ValidarIntegridadDatos`.

La razón de no fusionar todo en `EjecucionSincronizacion` es que el
rango histórico y la cobertura son propiedades del estado actual de
los datos, no de una corrida puntual -siguen siendo válidas aunque
no se haya sincronizado nada recientemente, y este reporte debe
poder generarse en cualquier momento (no solo justo después de
sincronizar), ya que la Fase 3 (Estadísticas/ML) lo usará como
validación de calidad antes de entrenar modelos.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sincronizacion_repository import SincronizacionRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.application.use_cases.validar_integridad import ValidarIntegridadDatos


@dataclass
class ReporteCalidadDatos:
    juego_codigo: str

    ultima_sincronizacion_en: str | None
    total_encontrados: int
    total_importados: int
    duplicados_detectados: int
    sorteos_con_error: int
    sorteos_incompletos: int
    porcentaje_exito: float
    duracion_ms: int | None

    total_sorteos_almacenados: int
    primer_sorteo: int | None
    ultimo_sorteo: int | None
    huecos: list[int]
    cobertura_porcentaje: float


class GenerarReporteCalidadDatos:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        sorteo_repository: SorteoRepository,
        sincronizacion_repository: SincronizacionRepository,
    ):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository
        self._sincronizaciones = sincronizacion_repository
        self._validar_integridad = ValidarIntegridadDatos(juego_repository, sorteo_repository)

    def ejecutar(self, codigo_juego: str) -> ReporteCalidadDatos:
        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)

        integridad = self._validar_integridad.ejecutar(codigo_juego)
        rango = (
            (integridad.numero_sorteo_maximo - integridad.numero_sorteo_minimo + 1)
            if integridad.numero_sorteo_minimo is not None else 0
        )
        cobertura = (
            round(100.0 * (rango - len(integridad.huecos)) / rango, 2) if rango > 0 else 0.0
        )

        ultima = self._sincronizaciones.obtener_ultima(juego.id)

        return ReporteCalidadDatos(
            juego_codigo=codigo_juego,
            ultima_sincronizacion_en=ultima.iniciado_en.isoformat() if ultima else None,
            total_encontrados=ultima.total_sorteos_encontrados if ultima else 0,
            total_importados=ultima.sorteos_nuevos if ultima else 0,
            duplicados_detectados=ultima.sorteos_duplicados if ultima else 0,
            sorteos_con_error=ultima.sorteos_fallidos if ultima else 0,
            sorteos_incompletos=ultima.sorteos_incompletos if ultima else 0,
            porcentaje_exito=ultima.porcentaje_exito if ultima else 0.0,
            duracion_ms=ultima.duracion_ms if ultima else None,
            total_sorteos_almacenados=integridad.total_sorteos,
            primer_sorteo=integridad.numero_sorteo_minimo,
            ultimo_sorteo=integridad.numero_sorteo_maximo,
            huecos=integridad.huecos,
            cobertura_porcentaje=cobertura,
        )
