"""
Implementaciones fake en memoria de los puertos de la capa de
aplicación. Permiten testear casos de uso sin levantar PostgreSQL,
lo cual es exactamente el punto de tener las interfaces en
application/interfaces: la lógica de orquestación no debería
requerir infraestructura real para probarse.
"""
from __future__ import annotations

import uuid
from datetime import date

from app.application.interfaces.color_repository import ColorRepository
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

    def listar_por_juego(
        self,
        juego_id: uuid.UUID,
        desde: date | None = None,
        hasta: date | None = None,
        limite: int = 100,
        offset: int = 0,
    ) -> list[Sorteo]:
        resultado = [s for s in self._sorteos.values() if s.juego_id == juego_id]
        if desde:
            resultado = [s for s in resultado if s.fecha >= desde]
        if hasta:
            resultado = [s for s in resultado if s.fecha <= hasta]
        resultado.sort(key=lambda s: s.fecha, reverse=True)
        return resultado[offset: offset + limite]

    def contar_por_juego(self, juego_id: uuid.UUID) -> int:
        return sum(1 for s in self._sorteos.values() if s.juego_id == juego_id)

    def ultimo_sorteo(self, juego_id: uuid.UUID) -> Sorteo | None:
        candidatos = [s for s in self._sorteos.values() if s.juego_id == juego_id]
        if not candidatos:
            return None
        return max(candidatos, key=lambda s: s.numero_sorteo)

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


class FakeColorRepository(ColorRepository):
    def __init__(self, colores_por_juego: dict[uuid.UUID, list[Color]] | None = None):
        self._colores = colores_por_juego or {}

    def listar_vigentes(self, juego_id: uuid.UUID, en_fecha: date | None = None) -> list[Color]:
        return [c for c in self._colores.get(juego_id, []) if c.activo]

    def guardar(self, juego_id: uuid.UUID, color: Color) -> Color:
        self._colores.setdefault(juego_id, []).append(color)
        return color

    def cerrar_vigencia(self, juego_id: uuid.UUID, codigo: str, hasta: date) -> None:
        for i, c in enumerate(self._colores.get(juego_id, [])):
            if c.codigo == codigo:
                self._colores[juego_id][i] = Color(
                    codigo=c.codigo, nombre=c.nombre, activo=c.activo,
                    vigente_desde=c.vigente_desde, vigente_hasta=hasta,
                )
