"""
Puerto: EstadisticaRepository.

Persiste y recupera estadísticas ya calculadas -deliberadamente
"tonto": no importa nada de `app/application/estadisticas/motor/`,
no sabe qué es un `FrecuenciaObservada`, no decide qué estadística
calcular ni cuándo. Solo guarda/recupera `dict`s ya serializados. La
conversión entre dataclasses del motor y `dict` es responsabilidad
del orquestador (etapa T, todavía no implementada) -nunca de este
repositorio.

`EstadisticaCalculada` es el único tipo nuevo de esta etapa: el DTO
mínimo para representar una fila de la tabla `estadisticas`
(genérica desde la Fase 1, extendida en la Etapa R con
`hasta_numero_sorteo` y `parametros_hash`, ver migración 0005). No
existen tipos ORM específicos por métrica (`FrecuenciaObservadaORM`,
etc.) -la persistencia sigue siendo genérica, tal como se decidió en
la Etapa Q.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class EstadisticaCalculada:
    """Una fila de `estadisticas`, ya calculada y (opcionalmente)
    persistida. `id`/`calculado_en` son `None` antes de guardarse por
    primera vez -el repositorio los completa al guardar."""

    id: UUID | None
    juego_id: UUID
    tipo_estadistica: str
    hasta_numero_sorteo: int | None
    parametros: dict
    parametros_hash: str
    resultado: dict
    calculado_en: datetime | None
    valido_hasta: datetime | None


def calcular_parametros_hash(parametros: dict) -> str:
    """SHA-256 hexadecimal (64 caracteres) de `parametros`,
    canonicalizado de forma determinista: claves ordenadas
    (`sort_keys=True`), separadores fijos (sin espacios variables),
    UTF-8. `json.dumps(..., sort_keys=True)` ya maneja
    consistentemente listas, diccionarios anidados, booleanos,
    `None` y strings sin necesitar ningún tratamiento especial -no se
    usa `hash()` de Python (no determinista entre procesos/versiones,
    e inutilizable para persistencia). No muta `parametros`: `dumps`
    nunca modifica el diccionario original.

    NUNCA incluye `hasta_numero_sorteo` -es una columna independiente
    (ver EstadisticaCalculada), no parte de `parametros`."""
    canonico = json.dumps(parametros, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


class EstadisticaRepository(ABC):
    @abstractmethod
    def guardar(self, entrada: EstadisticaCalculada) -> EstadisticaCalculada:
        """Persiste `entrada`. Debe respetar la unicidad de base de
        datos (juego_id, tipo_estadistica, hasta_numero_sorteo,
        parametros_hash) -una violación debe propagarse, nunca
        silenciarse. No calcula nada, no invoca al motor estadístico."""

    @abstractmethod
    def buscar_vigente(
        self, juego_id: UUID, tipo_estadistica: str, hasta_numero_sorteo: int | None, parametros: dict,
    ) -> EstadisticaCalculada | None:
        """Busca por (juego_id, tipo_estadistica, hasta_numero_sorteo,
        hash de `parametros`), considerando vigente solo si
        valido_hasta es None o está en el futuro. None si no existe o
        está vencida -nunca lanza error por "no encontrado"."""

    @abstractmethod
    def invalidar_por_juego(self, juego_id: UUID, desde_numero_sorteo: int | None = None) -> int:
        """Marca como inválidas (valido_hasta = ahora) las
        estadísticas VIGENTES del juego dado que:
        - tienen histórico completo (hasta_numero_sorteo IS NULL) -sus
          datos siempre incluyen el sorteo mutado, así que siempre se
          invalidan;
        - o tienen un corte >= `desde_numero_sorteo` -esos datos
          incluyeron (o hubieran incluido) el sorteo mutado.

        Las estadísticas con corte < `desde_numero_sorteo` se
        CONSERVAN: sus datos nunca llegaron a ese sorteo, así que
        mutarlo no las afecta -son históricas congeladas por
        definición, no deuda de caché.

        Si `desde_numero_sorteo` es None, solo se invalida el
        histórico completo (comportamiento equivalente a pasar el
        menor numero_sorteo posible). Devuelve la cantidad de filas
        afectadas."""

    @abstractmethod
    def listar_por_juego_y_tipo(self, juego_id: UUID, tipo_estadistica: str) -> list[EstadisticaCalculada]:
        """Todas las estadísticas (vigentes o no) de ese juego y
        tipo, ordenadas por calculado_en descendente -la más reciente
        primero, mismo criterio que el resto del proyecto usa para
        listados históricos."""
