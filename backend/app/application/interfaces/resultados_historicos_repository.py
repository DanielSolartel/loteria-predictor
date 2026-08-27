"""
Puerto: ResultadosHistoricosRepository.

Único traductor del sistema entre el modelo de persistencia
(`SorteoORM` + `SorteoNumeroORM` + `SorteoSuperbalotaORM` /
`SorteoColorNumeroORM`) y los DTOs puros que consume el motor
estadístico (`ResultadoNumerico`/`ResultadoColorLoto`). No calcula
absolutamente nada -ninguna frecuencia, atraso, probabilidad,
distribución ni métrica de ningún tipo. Su única responsabilidad es:

    PostgreSQL -> DTO puro del motor

El motor estadístico sigue sin conocer este puerto ni ningún otro
elemento de infraestructura -las funciones de `motor/*.py` siguen
recibiendo `Sequence[ResultadoNumerico]`/`Sequence[ResultadoColorLoto]`
tal como lo han hecho desde la Etapa C.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico


class ResultadosHistoricosRepository(ABC):
    @abstractmethod
    def listar_resultados_numericos(
        self, juego_id: UUID, hasta_numero_sorteo: int | None = None,
    ) -> list[ResultadoNumerico]:
        """Histórico de un juego estándar (MiLoto/Baloto/Revancha),
        ordenado por numero_sorteo ASCENDENTE de forma determinista
        (nunca el orden accidental de PostgreSQL). Si
        `hasta_numero_sorteo` no es None, el filtro
        `numero_sorteo <= hasta_numero_sorteo` se aplica EN LA
        CONSULTA SQL -nunca se trae el histórico completo para
        filtrarlo después en Python. Lista vacía si el juego no
        tiene sorteos o no existe."""

    @abstractmethod
    def listar_resultados_colorloto(
        self, juego_id: UUID, hasta_numero_sorteo: int | None = None,
    ) -> list[ResultadoColorLoto]:
        """Igual que `listar_resultados_numericos`, para ColorLoto:
        cada `ResultadoColorLoto.pares` en orden de `posicion`,
        `color` como el código (`ColorORM.codigo`), nunca el nombre
        ni el id."""
