"""
Caso de uso: ValidarIntegridadDatos.

No revalida las reglas de cada combinación -eso ya lo garantiza
`LotteryGame.validate_draw` en el momento de guardar (ver
`RegistrarSorteo`/`EditarSorteo`), así que no hay forma de que exista
un sorteo inválido en la base. Lo que sí puede pasar, y es lo que
este caso de uso detecta, es que falten sorteos en la secuencia
(huecos de numeración) porque una sincronización falló para algunos
números -información útil para decidir si conviene reimportar algo.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository


@dataclass
class ReporteIntegridad:
    juego_codigo: str
    total_sorteos: int
    numero_sorteo_minimo: int | None
    numero_sorteo_maximo: int | None
    huecos: list[int]  # números de sorteo esperados y no encontrados en el rango [min, max]


class ValidarIntegridadDatos:
    def __init__(self, juego_repository: JuegoRepository, sorteo_repository: SorteoRepository):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository

    def ejecutar(self, codigo_juego: str) -> ReporteIntegridad:
        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)

        numeros = sorted(self._sorteos.listar_numeros_sorteo(juego.id))
        if not numeros:
            return ReporteIntegridad(
                juego_codigo=codigo_juego, total_sorteos=0,
                numero_sorteo_minimo=None, numero_sorteo_maximo=None, huecos=[],
            )

        minimo, maximo = numeros[0], numeros[-1]
        presentes = set(numeros)
        huecos = [n for n in range(minimo, maximo + 1) if n not in presentes]

        return ReporteIntegridad(
            juego_codigo=codigo_juego, total_sorteos=len(numeros),
            numero_sorteo_minimo=minimo, numero_sorteo_maximo=maximo, huecos=huecos,
        )
