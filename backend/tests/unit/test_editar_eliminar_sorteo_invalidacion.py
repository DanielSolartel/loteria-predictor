"""
Tests de `EditarSorteo` y `EliminarSorteo` (previamente sin cobertura
de tests dedicada -esta corrección los agrega, incluyendo su
invalidación de caché estadístico).
"""
from __future__ import annotations

import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from app.application.exceptions import SorteoInvalidoError, SorteoNoEncontradoError
from app.application.interfaces.estadistica_repository import EstadisticaCalculada
from app.application.use_cases.editar_sorteo import EditarSorteo, EditarSorteoInput
from app.application.use_cases.eliminar_sorteo import EliminarSorteo
from app.application.use_cases.game_factory import GameFactory
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.combination import Combination
from tests.unit.fakes import (
    FakeColorRepository,
    FakeEstadisticaRepository,
    FakeJuegoRepository,
    FakeSorteoRepository,
)


def _crear_miloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto",
        rango_min=1, rango_max=39, cantidad_numeros=5,
        tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


def _precargar_sorteo(sorteo_repo, juego_id, numero_sorteo=100, numeros=(1, 2, 3, 4, 5)) -> Sorteo:
    sorteo = Sorteo(
        id=None, juego_id=juego_id, numero_sorteo=numero_sorteo, fecha=date(2026, 7, 30),
        dia_semana="jueves", resultado=Combination(numeros=numeros), fuente="test",
    )
    return sorteo_repo.guardar(sorteo)


def _precargar_estadistica(estadistica_repo, juego_id, hasta_numero_sorteo=None, tipo="frecuencia_numeros"):
    return estadistica_repo.guardar(EstadisticaCalculada(
        id=None, juego_id=juego_id, tipo_estadistica=tipo, hasta_numero_sorteo=hasta_numero_sorteo,
        parametros={}, parametros_hash="", resultado={}, calculado_en=None, valido_hasta=None,
    ))


@pytest.fixture
def contexto_editar():
    miloto = _crear_miloto()
    juego_repo = FakeJuegoRepository(juegos=[miloto])
    sorteo_repo = FakeSorteoRepository()
    color_repo = FakeColorRepository()
    estadistica_repo = FakeEstadisticaRepository()
    factory = GameFactory(color_repository=color_repo)
    sorteo = _precargar_sorteo(sorteo_repo, miloto.id, numero_sorteo=100)
    caso_uso = EditarSorteo(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=factory,
        estadistica_repository=estadistica_repo,
    )
    return caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo


@pytest.fixture
def contexto_eliminar():
    miloto = _crear_miloto()
    sorteo_repo = FakeSorteoRepository()
    estadistica_repo = FakeEstadisticaRepository()
    sorteo = _precargar_sorteo(sorteo_repo, miloto.id, numero_sorteo=100)
    caso_uso = EliminarSorteo(sorteo_repository=sorteo_repo, estadistica_repository=estadistica_repo)
    return caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo


class TestEditarSorteoInvalidaCacheEstadistico:
    def test_edicion_exitosa_invalida_desde_n(self, contexto_editar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_editar
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None)
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=100)
        caso_uso.ejecutar(EditarSorteoInput(
            sorteo_id=sorteo.id, fecha=date(2026, 7, 30), resultado=Combination(numeros=(6, 7, 8, 9, 10)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is None
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 100, {}) is None

    def test_conserva_cortes_anteriores(self, contexto_editar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_editar
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=50)
        caso_uso.ejecutar(EditarSorteoInput(
            sorteo_id=sorteo.id, fecha=date(2026, 7, 30), resultado=Combination(numeros=(6, 7, 8, 9, 10)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 50, {}) is not None

    def test_no_afecta_otro_juego(self, contexto_editar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_editar
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None)
        caso_uso.ejecutar(EditarSorteoInput(
            sorteo_id=sorteo.id, fecha=date(2026, 7, 30), resultado=Combination(numeros=(6, 7, 8, 9, 10)),
        ))
        assert estadistica_repo.buscar_vigente(otro_juego_id, "frecuencia_numeros", None, {}) is not None

    def test_edicion_rechazada_no_invalida(self, contexto_editar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_editar
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None)
        with pytest.raises(SorteoInvalidoError):
            caso_uso.ejecutar(EditarSorteoInput(
                sorteo_id=sorteo.id, fecha=date(2026, 7, 30), resultado=Combination(numeros=(1, 2, 3, 4, 999)),
            ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is not None

    def test_edicion_sorteo_no_encontrado_no_invalida(self, contexto_editar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_editar
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None)
        with pytest.raises(SorteoNoEncontradoError):
            caso_uso.ejecutar(EditarSorteoInput(
                sorteo_id=uuid.uuid4(), fecha=date(2026, 7, 30), resultado=Combination(numeros=(1, 2, 3, 4, 5)),
            ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is not None


class TestEliminarSorteoInvalidaCacheEstadistico:
    def test_obtiene_juego_id_y_numero_sorteo_antes_de_eliminar(self, contexto_eliminar):
        """Verificación indirecta: si el caso de uso NO hubiera
        capturado juego_id/numero_sorteo antes de borrar, no podría
        invalidar correctamente (el sorteo ya no existiria para
        consultarlo) -este test demuestra que sí lo logra."""
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_eliminar
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=100)
        caso_uso.ejecutar(sorteo.id)
        assert sorteo_repo.obtener_por_id(sorteo.id) is None  # realmente se elimino
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 100, {}) is None  # y se invalido

    def test_eliminacion_exitosa_invalida_desde_n(self, contexto_eliminar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_eliminar
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None)
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=100)
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=200)
        caso_uso.ejecutar(sorteo.id)
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is None
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 100, {}) is None
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 200, {}) is None

    def test_conserva_cortes_anteriores(self, contexto_eliminar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_eliminar
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=50)
        caso_uso.ejecutar(sorteo.id)
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 50, {}) is not None

    def test_no_afecta_otro_juego(self, contexto_eliminar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_eliminar
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None)
        caso_uso.ejecutar(sorteo.id)
        assert estadistica_repo.buscar_vigente(otro_juego_id, "frecuencia_numeros", None, {}) is not None

    def test_sorteo_inexistente_no_invalida(self, contexto_eliminar):
        caso_uso, miloto, sorteo, sorteo_repo, estadistica_repo = contexto_eliminar
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None)
        with pytest.raises(SorteoNoEncontradoError):
            caso_uso.ejecutar(uuid.uuid4())
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is not None
