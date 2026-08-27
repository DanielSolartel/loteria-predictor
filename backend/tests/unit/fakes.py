"""
Implementaciones fake en memoria de los puertos de la capa de
aplicación. Permiten testear casos de uso sin levantar PostgreSQL,
lo cual es exactamente el punto de tener las interfaces en
application/interfaces: la lógica de orquestación no debería
requerir infraestructura real para probarse.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.estadistica_repository import (
    EstadisticaCalculada,
    EstadisticaRepository,
    calcular_parametros_hash,
)
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.sorteo_repository import SorteoRepository
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color


class FakeJuegoRepository(JuegoRepository):
    def __init__(self, juegos: list[Juego] | None = None):
        self._juegos = {j.id: j for j in (juegos or [])}
        self._por_codigo = {j.codigo: j for j in (juegos or [])}

    def obtener_por_codigo(self, codigo: str) -> Juego | None:
        return self._por_codigo.get(codigo)

    def obtener_por_id(self, juego_id: uuid.UUID) -> Juego | None:
        return self._juegos.get(juego_id)

    def listar_activos(self) -> list[Juego]:
        return [j for j in self._juegos.values() if j.activo]

    def guardar(self, juego: Juego) -> Juego:
        if juego.id is None:
            juego.id = uuid.uuid4()
        self._juegos[juego.id] = juego
        self._por_codigo[juego.codigo] = juego
        return juego


class FakeSorteoRepository(SorteoRepository):
    def __init__(self):
        self._sorteos: dict[uuid.UUID, Sorteo] = {}

    def guardar(self, sorteo: Sorteo) -> Sorteo:
        sorteo.id = uuid.uuid4()
        self._sorteos[sorteo.id] = sorteo
        return sorteo

    def obtener_por_id(self, sorteo_id: uuid.UUID) -> Sorteo | None:
        return self._sorteos.get(sorteo_id)

    def existe(self, juego_id: uuid.UUID, numero_sorteo: int) -> bool:
        return any(
            s.juego_id == juego_id and s.numero_sorteo == numero_sorteo
            for s in self._sorteos.values()
        )

    def listar_por_juego(self, juego_id: uuid.UUID, filtro) -> list[Sorteo]:
        resultado = [s for s in self._sorteos.values() if s.juego_id == juego_id]
        resultado = self._aplicar_filtros(resultado, filtro)

        campo = (lambda s: s.fecha) if filtro.orden_campo == "fecha" else (lambda s: s.numero_sorteo)
        # Desempate estable por numero_sorteo, igual que en SQLAlchemy.
        resultado.sort(key=lambda s: (campo(s), s.numero_sorteo), reverse=(filtro.orden_direccion == "desc"))

        return resultado[filtro.offset: filtro.offset + filtro.limite]

    def contar_por_juego(self, juego_id: uuid.UUID, filtro=None) -> int:
        resultado = [s for s in self._sorteos.values() if s.juego_id == juego_id]
        if filtro:
            resultado = self._aplicar_filtros(resultado, filtro)
        return len(resultado)

    @staticmethod
    def _aplicar_filtros(sorteos: list[Sorteo], filtro) -> list[Sorteo]:
        if filtro.desde:
            sorteos = [s for s in sorteos if s.fecha >= filtro.desde]
        if filtro.hasta:
            sorteos = [s for s in sorteos if s.fecha <= filtro.hasta]
        if filtro.numero_desde is not None:
            sorteos = [s for s in sorteos if s.numero_sorteo >= filtro.numero_desde]
        if filtro.numero_hasta is not None:
            sorteos = [s for s in sorteos if s.numero_sorteo <= filtro.numero_hasta]
        return sorteos

    def ultimo_sorteo(self, juego_id: uuid.UUID) -> Sorteo | None:
        candidatos = [s for s in self._sorteos.values() if s.juego_id == juego_id]
        if not candidatos:
            return None
        return max(candidatos, key=lambda s: s.numero_sorteo)

    def obtener_por_numero(self, juego_id: uuid.UUID, numero_sorteo: int) -> Sorteo | None:
        return next(
            (s for s in self._sorteos.values() if s.juego_id == juego_id and s.numero_sorteo == numero_sorteo),
            None,
        )

    def listar_numeros_sorteo(self, juego_id: uuid.UUID) -> list[int]:
        return [s.numero_sorteo for s in self._sorteos.values() if s.juego_id == juego_id]

    def actualizar(self, sorteo: Sorteo) -> Sorteo:
        from app.application.exceptions import SorteoNoEncontradoError

        if sorteo.id not in self._sorteos:
            raise SorteoNoEncontradoError(str(sorteo.id))
        self._sorteos[sorteo.id] = sorteo
        return sorteo

    def eliminar(self, sorteo_id: uuid.UUID) -> None:
        from app.application.exceptions import SorteoNoEncontradoError

        if sorteo_id not in self._sorteos:
            raise SorteoNoEncontradoError(str(sorteo_id))
        del self._sorteos[sorteo_id]


class FakeEstadisticaRepository(EstadisticaRepository):
    """Réplica fiel de EstadisticaRepositorySQLAlchemy -misma
    semántica de unicidad, vigencia e invalidación (incluida la
    corrección de `desde_numero_sorteo`: invalida histórico completo
    Y cualquier corte >= ese número, conserva cortes menores)."""

    def __init__(self):
        self._filas: list[EstadisticaCalculada] = []

    def guardar(self, entrada: EstadisticaCalculada) -> EstadisticaCalculada:
        """Réplica del upsert real: busca por identidad IGNORANDO
        valido_hasta (una fila invalidada sigue siendo la misma
        identidad reutilizable) -si existe, la reemplaza conservando
        el mismo id; si no, inserta una nueva."""
        hash_calculado = calcular_parametros_hash(entrada.parametros)
        for i, fila in enumerate(self._filas):
            if (
                fila.juego_id == entrada.juego_id
                and fila.tipo_estadistica == entrada.tipo_estadistica
                and fila.hasta_numero_sorteo == entrada.hasta_numero_sorteo
                and fila.parametros_hash == hash_calculado
            ):
                reemplazada = EstadisticaCalculada(
                    id=fila.id, juego_id=entrada.juego_id, tipo_estadistica=entrada.tipo_estadistica,
                    hasta_numero_sorteo=entrada.hasta_numero_sorteo, parametros=entrada.parametros,
                    parametros_hash=hash_calculado, resultado=entrada.resultado,
                    calculado_en=datetime.now(timezone.utc), valido_hasta=entrada.valido_hasta,
                )
                self._filas[i] = reemplazada
                return reemplazada

        guardada = EstadisticaCalculada(
            id=uuid.uuid4(), juego_id=entrada.juego_id, tipo_estadistica=entrada.tipo_estadistica,
            hasta_numero_sorteo=entrada.hasta_numero_sorteo, parametros=entrada.parametros,
            parametros_hash=hash_calculado, resultado=entrada.resultado,
            calculado_en=datetime.now(timezone.utc), valido_hasta=entrada.valido_hasta,
        )
        self._filas.append(guardada)
        return guardada

    def buscar_vigente(
        self, juego_id: uuid.UUID, tipo_estadistica: str, hasta_numero_sorteo: int | None, parametros: dict,
    ) -> EstadisticaCalculada | None:
        hash_calculado = calcular_parametros_hash(parametros)
        ahora = datetime.now(timezone.utc)
        for fila in self._filas:
            if (
                fila.juego_id == juego_id
                and fila.tipo_estadistica == tipo_estadistica
                and fila.hasta_numero_sorteo == hasta_numero_sorteo
                and fila.parametros_hash == hash_calculado
                and (fila.valido_hasta is None or fila.valido_hasta > ahora)
            ):
                return fila
        return None

    def invalidar_por_juego(self, juego_id: uuid.UUID, desde_numero_sorteo: int | None = None) -> int:
        ahora = datetime.now(timezone.utc)
        afectadas = 0
        nuevas_filas = []
        for fila in self._filas:
            corte_afectado = fila.hasta_numero_sorteo is None or (
                desde_numero_sorteo is not None and fila.hasta_numero_sorteo >= desde_numero_sorteo
            )
            vigente = fila.valido_hasta is None or fila.valido_hasta > ahora
            if fila.juego_id == juego_id and corte_afectado and vigente:
                fila = EstadisticaCalculada(
                    id=fila.id, juego_id=fila.juego_id, tipo_estadistica=fila.tipo_estadistica,
                    hasta_numero_sorteo=fila.hasta_numero_sorteo, parametros=fila.parametros,
                    parametros_hash=fila.parametros_hash, resultado=fila.resultado,
                    calculado_en=fila.calculado_en, valido_hasta=ahora,
                )
                afectadas += 1
            nuevas_filas.append(fila)
        self._filas = nuevas_filas
        return afectadas

    def listar_por_juego_y_tipo(self, juego_id: uuid.UUID, tipo_estadistica: str) -> list[EstadisticaCalculada]:
        filas = [f for f in self._filas if f.juego_id == juego_id and f.tipo_estadistica == tipo_estadistica]
        return sorted(filas, key=lambda f: f.calculado_en, reverse=True)


class FakeUnitOfWork:
    """No-op: para tests que no necesitan verificar la semántica de
    commit/rollback en sí, solo que el caso de uso funcione. Los
    tests que SÍ verifican la persistencia incremental real usan
    `_SorteoRepositoryTransaccional` + `_FakeUnitOfWork` propios en
    tests/unit/connectors/test_persistencia_incremental.py."""

    def confirmar(self) -> None:
        pass


class FakeColorRepository(ColorRepository):
    def __init__(self, colores_por_juego: dict[uuid.UUID, list[Color]] | None = None):
        self._colores = colores_por_juego or {}

    def listar_vigentes(self, juego_id: uuid.UUID, en_fecha: date | None = None) -> list[Color]:
        if en_fecha is None:
            # Paleta ACTUAL -mismo contrato exacto, sin cambios.
            return [c for c in self._colores.get(juego_id, []) if c.activo]
        # Paleta HISTÓRICA en en_fecha -NUNCA filtra por `activo`,
        # mismo criterio de correción aplicado a la implementación
        # SQLAlchemy real. Reutiliza `listar_todos` (una sola
        # "consulta" al almacén interno), igual que la implementación
        # SQLAlchemy real vía `_listar_por_vigencia_en` -nunca
        # duplica el acceso a `self._colores`.
        return [c for c in self.listar_todos(juego_id) if c.esta_vigente_en(en_fecha)]

    def listar_todos(self, juego_id: uuid.UUID) -> list[Color]:
        return sorted(self._colores.get(juego_id, []), key=lambda c: c.codigo)

    def guardar(self, juego_id: uuid.UUID, color: Color) -> Color:
        self._colores.setdefault(juego_id, []).append(color)
        return color

    def cerrar_vigencia(self, juego_id: uuid.UUID, codigo: str, hasta: date) -> None:
        """Extendido en Etapa AE-4P para replicar fielmente el
        comportamiento de ColorRepositorySQLAlchemy.cerrar_vigencia:
        `ValueError` si no hay un color vigente con ese código -antes
        el fake ignoraba silenciosamente un código inexistente, lo
        cual no permitía probar el caso real de "operación fallida no
        invalida caché"."""
        for i, c in enumerate(self._colores.get(juego_id, [])):
            if c.codigo == codigo and c.vigente_hasta is None:
                self._colores[juego_id][i] = Color(
                    codigo=c.codigo, nombre=c.nombre, activo=c.activo,
                    vigente_desde=c.vigente_desde, vigente_hasta=hasta,
                )
                return
        raise ValueError(f"No hay un color vigente con código '{codigo}' para este juego")


class FakeSincronizacionRepository:
    """No hereda de SincronizacionRepository con `ABC` estricto en el
    test para simplificar -implementa el mismo contrato en la
    práctica. Usado por los tests de SincronizarSorteos/ReimportarSorteo."""

    def __init__(self):
        self._items: dict[uuid.UUID, "EjecucionSincronizacion"] = {}

    def guardar(self, ejecucion):
        if ejecucion.id is None:
            ejecucion.id = uuid.uuid4()
        self._items[ejecucion.id] = ejecucion
        return ejecucion

    def obtener_ultima(self, juego_id: uuid.UUID):
        candidatos = [e for e in self._items.values() if e.juego_id == juego_id]
        return max(candidatos, key=lambda e: e.iniciado_en) if candidatos else None

    def listar_recientes(self, juego_id: uuid.UUID, limite: int = 20):
        candidatos = sorted(
            (e for e in self._items.values() if e.juego_id == juego_id),
            key=lambda e: e.iniciado_en, reverse=True,
        )
        return candidatos[:limite]
