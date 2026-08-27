"""
Caso de uso: GestionarPaletaColores.

Cumple directamente el requisito de que la arquitectura permita
modificar la paleta de ColorLoto si Coljuegos actualiza las reglas,
sin perder la validez de los sorteos históricos. Retirar un color no
lo borra: se cierra su vigencia (`vigente_hasta`), y los sorteos
pasados que lo usaron siguen siendo consultables y estadísticamente
correctos.

Invalidación de caché (Etapa AE-4P): las únicas dos operaciones
mutantes reales de este caso de uso (`agregar_color`, `retirar_color`
-confirmado por inspección exhaustiva del código; no existen métodos
para editar código/nombre/activo ni para reactivar un color) pueden
cambiar el universo temporal de colores que determinan
`frecuencia_colores_colorloto` y `frecuencia_pares_colorloto` para
CUALQUIER corte histórico, incluso sin que cambie ningún sorteo. Por
eso, tras una mutación exitosa, se invalidan TODAS las estadísticas
cacheadas del juego -incluidos TODOS los cortes temporales, no solo
los posteriores a un sorteo concreto (a diferencia del patrón usado
en RegistrarSorteo/EditarSorteo/EliminarSorteo, que solo invalidan
`desde_numero_sorteo` en adelante porque un sorteo nuevo no puede
afectar cachés de cortes anteriores a él -una paleta modificada SÍ
puede afectar cualquier corte, incluidos los más antiguos, porque el
universo temporal se resuelve contra la fecha de cada escenario, no
contra el momento en que se edita la paleta).

`desde_numero_sorteo=0` para `invalidar_por_juego`: cualquier corte
real (`hasta_numero_sorteo`) es siempre un entero positivo (todo
sorteo empieza en `numero_sorteo=1`), así que la condición SQL
`hasta_numero_sorteo >= 0` es verdadera para TODO corte existente,
capturando -junto al `IS NULL` ya cubierto por el propio método- la
totalidad de las cachés del juego, sin excepción.

Invalidación EXCLUSIVAMENTE después de que la operación de
`ColorRepository` retorna con éxito -nunca antes, mismo patrón ya
validado en `RegistrarSorteo`/`EditarSorteo`/`EliminarSorteo`. Si
`guardar`/`cerrar_vigencia` lanza una excepción (p.ej. color
duplicado, o `cerrar_vigencia` sin color vigente con ese código), la
línea de invalidación nunca se ejecuta. Ambos repositorios
(`ColorRepository` y `EstadisticaRepository`) comparten la misma
sesión SQLAlchemy inyectada por request (`get_db`): el commit final
ocurre una sola vez, al terminar el request sin excepción -si algo
falla en cualquier punto, `db.rollback()` revierte tanto la mutación
de color como la invalidación juntas, sin necesitar ninguna unidad de
trabajo explícita adicional (confirmado inspeccionando
`app/infrastructure/db/session.py`). `listar_paleta_vigente` es
estrictamente de lectura y nunca invalida nada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.estadistica_repository import EstadisticaRepository
from app.domain.value_objects.color import Color


@dataclass
class AgregarColorInput:
    juego_id: UUID
    codigo: str
    nombre: str
    vigente_desde: date


@dataclass
class RetirarColorInput:
    juego_id: UUID
    codigo: str
    vigente_hasta: date


class GestionarPaletaColores:
    def __init__(self, color_repository: ColorRepository, estadistica_repository: EstadisticaRepository):
        self._colores = color_repository
        self._estadisticas = estadistica_repository

    def agregar_color(self, datos: AgregarColorInput) -> Color:
        nuevo = Color(
            codigo=datos.codigo,
            nombre=datos.nombre,
            activo=True,
            vigente_desde=datos.vigente_desde,
            vigente_hasta=None,
        )
        color_guardado = self._colores.guardar(datos.juego_id, nuevo)

        # Invalidación SOLO tras un guardado exitoso -mismo criterio
        # que RegistrarSorteo. Todos los cortes (incluido el histórico
        # completo), no solo desde cierto sorteo.
        self._estadisticas.invalidar_por_juego(datos.juego_id, desde_numero_sorteo=0)

        return color_guardado

    def retirar_color(self, datos: RetirarColorInput) -> None:
        self._colores.cerrar_vigencia(datos.juego_id, datos.codigo, datos.vigente_hasta)

        # Invalidación SOLO tras un cierre de vigencia exitoso -si
        # cerrar_vigencia lanza (código inexistente/ya retirado), esta
        # línea nunca se ejecuta.
        self._estadisticas.invalidar_por_juego(datos.juego_id, desde_numero_sorteo=0)

    def listar_paleta_vigente(self, juego_id: UUID, en_fecha: date | None = None) -> list[Color]:
        return self._colores.listar_vigentes(juego_id, en_fecha)
