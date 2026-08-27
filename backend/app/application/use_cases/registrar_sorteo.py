"""
Caso de uso: RegistrarSorteo.

Orquesta: buscar el juego -> construir su LotteryGame vía
GameFactory -> validar la combinación contra las reglas del juego ->
verificar que no exista duplicado -> persistir -> invalidar el caché
estadístico afectado.

La validación de reglas de negocio (rangos, cantidad de números,
colores vigentes) vive en `LotteryGame.validate_draw`, NUNCA aquí.
Este caso de uso solo orquesta; no reimplementa reglas de juego.

Invalidación de caché: ocurre EXCLUSIVAMENTE después de que
`sorteo_repository.guardar(...)` retorna con éxito -nunca antes. Si
la validación de dominio o la comprobación de duplicado fallan (ambas
ocurren antes de `guardar`), no se invalida nada -el histórico no
cambió, así que el caché sigue siendo válido. Es este mismo caso de
uso el que se reutiliza dentro de `SincronizarSorteos` y
`ReprocesarSorteosDesdeHtml` para cada sorteo nuevo -la invalidación
queda automáticamente incluida en el mismo commit incremental que
esos flujos ya hacen por sorteo, sin necesitar lógica adicional ahí."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from app.application.exceptions import (
    JuegoNoEncontradoError,
    SorteoDuplicadoError,
    SorteoInvalidoError,
)
from app.application.interfaces.estadistica_repository import EstadisticaRepository
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.application.use_cases.game_factory import GameFactory
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.combination import Combination

DIAS_SEMANA_ES = [
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
]


@dataclass
class RegistrarSorteoInput:
    codigo_juego: str
    numero_sorteo: int
    fecha: date
    resultado: Combination
    fuente: str | None = None


class RegistrarSorteo:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        sorteo_repository: SorteoRepository,
        game_factory: GameFactory,
        estadistica_repository: EstadisticaRepository,
    ):
        self._juegos = juego_repository
        self._sorteos = sorteo_repository
        self._game_factory = game_factory
        self._estadisticas = estadistica_repository

    def ejecutar(self, datos: RegistrarSorteoInput) -> Sorteo:
        juego = self._juegos.obtener_por_codigo(datos.codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(datos.codigo_juego)

        lottery_game = self._game_factory.crear(juego)
        validacion = lottery_game.validate_draw(datos.resultado)
        if not validacion:
            raise SorteoInvalidoError(validacion.errors)

        if self._sorteos.existe(juego.id, datos.numero_sorteo):  # type: ignore[arg-type]
            raise SorteoDuplicadoError(str(juego.id), datos.numero_sorteo)

        sorteo = Sorteo(
            id=None,
            juego_id=juego.id,  # type: ignore[arg-type]
            numero_sorteo=datos.numero_sorteo,
            fecha=datos.fecha,
            dia_semana=DIAS_SEMANA_ES[datos.fecha.weekday()],
            resultado=datos.resultado,
            fuente=datos.fuente,
            creado_en=datetime.now(timezone.utc),
        )
        sorteo_guardado = self._sorteos.guardar(sorteo)

        # Invalidación SOLO tras un guardado exitoso -si guardar()
        # lanza (p.ej. constraint de BD inesperado), esta línea nunca
        # se ejecuta.
        self._estadisticas.invalidar_por_juego(juego.id, desde_numero_sorteo=datos.numero_sorteo)  # type: ignore[arg-type]

        return sorteo_guardado
