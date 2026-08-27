"""
Tests de persistencia incremental (UnitOfWork).

El objetivo de este archivo es demostrar, no asumir, que la
corrección del problema de "una sola transacción gigante" funciona
de verdad. Para eso, `_SorteoRepositoryTransaccional` simula el
comportamiento real de una transacción de PostgreSQL:

  - Mientras no se llama a `confirmar()`, las escrituras son
    visibles dentro de la misma "sesión" (igual que Postgres ve sus
    propias escrituras no confirmadas -read-your-own-writes).
  - `confirmar()` mueve el estado actual a un punto "comprometido"
    (equivalente a un COMMIT real).
  - `simular_caida()` descarta todo lo escrito después del último
    punto comprometido (equivalente al `rollback()` que hace
    `get_db()` al capturar una excepción no manejada).

Con esto, un test puede forzar un fallo a mitad de un lote y
verificar, contra el estado "comprometido" (lo que sobreviviría a un
crash real), que únicamente se pierde lo que nunca se confirmó.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.interfaces.draw_source_connector import (
    DrawDetail,
    DrawSourceConnector,
    HealthStatus,
    SyncFetchResult,
)
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.reprocesar_sorteos_desde_html import ReprocesarSorteosDesdeHtml
from app.application.use_cases.sincronizar_sorteos import SincronizarSorteos
from app.domain.entities.juego import Juego
from app.domain.value_objects.combination import Combination
from tests.unit.fakes import FakeColorRepository, FakeEstadisticaRepository, FakeJuegoRepository, FakeSincronizacionRepository, FakeSorteoRepository


class _SorteoRepositoryTransaccional(FakeSorteoRepository):
    def __init__(self):
        super().__init__()
        self._comprometido: dict = {}

    def confirmar(self) -> None:
        self._comprometido = dict(self._sorteos)

    def simular_caida(self) -> None:
        """Simula lo que get_db() hace al capturar una excepción no
        manejada: rollback() de todo lo escrito desde el último
        commit real."""
        self._sorteos = dict(self._comprometido)

    def contar_comprometidos(self, juego_id: uuid.UUID) -> int:
        return sum(1 for s in self._comprometido.values() if s.juego_id == juego_id)

    def numeros_comprometidos(self, juego_id: uuid.UUID) -> set[int]:
        return {s.numero_sorteo for s in self._comprometido.values() if s.juego_id == juego_id}


class _EstadisticaRepositoryTransaccional(FakeEstadisticaRepository):
    """Mismo patrón que `_SorteoRepositoryTransaccional`: modela que
    la invalidación del caché estadístico comparte la MISMA sesión
    (y por tanto el mismo commit/rollback) que la escritura del
    sorteo -si `confirmar()` no se llamó, una `simular_caida()`
    también deshace las invalidaciones no confirmadas."""

    def __init__(self):
        super().__init__()
        self._comprometido: list = []

    def confirmar(self) -> None:
        self._comprometido = list(self._filas)

    def simular_caida(self) -> None:
        self._filas = list(self._comprometido)

    def vigente_comprometida(self, juego_id, tipo_estadistica, hasta_numero_sorteo, parametros) -> bool:
        """Consulta directamente sobre el estado COMPROMETIDO (lo que
        sobreviviría a un crash real), no sobre `self._filas` (que
        puede incluir escrituras aún no confirmadas)."""
        from datetime import datetime, timezone

        from app.application.interfaces.estadistica_repository import calcular_parametros_hash

        hash_calculado = calcular_parametros_hash(parametros)
        ahora = datetime.now(timezone.utc)
        return any(
            f.juego_id == juego_id and f.tipo_estadistica == tipo_estadistica
            and f.hasta_numero_sorteo == hasta_numero_sorteo and f.parametros_hash == hash_calculado
            and (f.valido_hasta is None or f.valido_hasta > ahora)
            for f in self._comprometido
        )


class _FakeUnitOfWork:
    def __init__(self, *repos_transaccionales):
        self._repos = repos_transaccionales

    def confirmar(self) -> None:
        for r in self._repos:
            r.confirmar()


class _ConectorConLoteFijo(DrawSourceConnector):
    """Devuelve una lista fija de DrawDetail predefinida por el test,
    simulando lo que ya descargó y parseó el conector real."""

    def __init__(self, draws: list[DrawDetail]):
        self._draws = draws

    @property
    def game_code(self):
        return "MILOTO"

    def fetch_draws(self, ultimo_conocido=None, max_paginas=None):
        return []

    def fetch_draw_detail(self, draw_id):
        raise NotImplementedError

    def sync(self, ultimo_conocido=None, max_paginas=None):
        return SyncFetchResult(draws=self._draws, fallidos=[], paginas_recorridas=1, duracion_ms=1)

    def health_check(self):
        return HealthStatus(True, 1.0, "ok")


def _juego_miloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto", rango_min=1, rango_max=39,
        cantidad_numeros=5, tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


def _draw_valido(n: int) -> DrawDetail:
    return DrawDetail(draw_id=str(n), numero_sorteo=n, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 5))


def _armar(juego, draws, sorteo_repo=None):
    juego_repo = FakeJuegoRepository(juegos=[juego])
    sorteo_repo = sorteo_repo or _SorteoRepositoryTransaccional()
    sync_repo = FakeSincronizacionRepository()
    color_repo = FakeColorRepository()
    estadistica_repo = _EstadisticaRepositoryTransaccional()
    factory = GameFactory(color_repository=color_repo)
    uow = _FakeUnitOfWork(sorteo_repo, estadistica_repo)
    conector = _ConectorConLoteFijo(draws)
    caso_uso = SincronizarSorteos(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
        color_repository=color_repo, game_factory=factory, obtener_conector=lambda c: conector,
        unit_of_work=uow, estadistica_repository=estadistica_repo,
    )
    return caso_uso, sorteo_repo, estadistica_repo


class TestPersistenciaIncrementalRealDuranteSincronizacion:
    """Demuestra -no asume- que cada sorteo sobrevive individualmente
    a un fallo posterior en el mismo lote, simulando un rollback real
    de PostgreSQL con `_SorteoRepositoryTransaccional`."""

    def test_1000_sorteos_un_crash_no_manejado_al_final_no_pierde_ninguno(self):
        """Caso central pedido explícitamente: procesa un lote grande
        (1000 sorteos válidos), simula que el proceso 'muere' justo
        después de procesar el último (p.ej. el guardado final del
        registro de ejecución falla) y confirma que TODOS los 1000
        ya confirmados individualmente sobreviven al rollback."""
        juego = _juego_miloto()
        draws = [_draw_valido(n) for n in range(1, 1001)]
        caso_uso, sorteo_repo, estadistica_repo = _armar(juego, draws)

        sync_repo_original_guardar = caso_uso._sincronizaciones.guardar
        llamadas = {"n": 0}

        def guardar_que_falla_la_segunda_vez(ejecucion):
            llamadas["n"] += 1
            if llamadas["n"] == 2:  # la primera es "en_progreso"; la segunda es "completado"
                raise ConnectionError("se perdió la conexión a la base de datos justo al final")
            return sync_repo_original_guardar(ejecucion)

        caso_uso._sincronizaciones.guardar = guardar_que_falla_la_segunda_vez

        with pytest.raises(ConnectionError):
            caso_uso.ejecutar("MILOTO")

        sorteo_repo.simular_caida()

        assert sorteo_repo.contar_comprometidos(juego.id) == 1000

    def test_falla_en_el_primer_sorteo_no_afecta_a_los_demas(self):
        juego = _juego_miloto()
        draws = [
            DrawDetail(draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 99)),
            *[_draw_valido(n) for n in range(2, 11)],
        ]
        caso_uso, sorteo_repo, estadistica_repo = _armar(juego, draws)

        reporte = caso_uso.ejecutar("MILOTO")
        sorteo_repo.simular_caida()

        assert reporte.ejecucion.sorteos_nuevos == 9
        assert sorteo_repo.contar_comprometidos(juego.id) == 9
        assert 1 not in sorteo_repo.numeros_comprometidos(juego.id)
        assert sorteo_repo.numeros_comprometidos(juego.id) == set(range(2, 11))

    def test_falla_en_un_sorteo_intermedio_no_afecta_a_los_demas(self):
        juego = _juego_miloto()
        draws = [
            *[_draw_valido(n) for n in range(1, 5)],
            DrawDetail(draw_id="5", numero_sorteo=5, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 99)),
            *[_draw_valido(n) for n in range(6, 11)],
        ]
        caso_uso, sorteo_repo, estadistica_repo = _armar(juego, draws)

        reporte = caso_uso.ejecutar("MILOTO")
        sorteo_repo.simular_caida()

        assert reporte.ejecucion.sorteos_nuevos == 9
        comprometidos = sorteo_repo.numeros_comprometidos(juego.id)
        assert 5 not in comprometidos
        assert comprometidos == (set(range(1, 11)) - {5})

    def test_falla_en_el_ultimo_sorteo_no_afecta_a_los_anteriores(self):
        juego = _juego_miloto()
        draws = [
            *[_draw_valido(n) for n in range(1, 10)],
            DrawDetail(draw_id="10", numero_sorteo=10, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 99)),
        ]
        caso_uso, sorteo_repo, estadistica_repo = _armar(juego, draws)

        reporte = caso_uso.ejecutar("MILOTO")
        sorteo_repo.simular_caida()

        assert reporte.ejecucion.sorteos_nuevos == 9
        assert sorteo_repo.numeros_comprometidos(juego.id) == set(range(1, 10))

    def test_duplicados_no_se_cuentan_como_error_ni_duplican_el_registro(self):
        juego = _juego_miloto()
        sorteo_repo = _SorteoRepositoryTransaccional()

        draws_primera = [_draw_valido(1)]
        caso_uso1, _, _ = _armar(juego, draws_primera, sorteo_repo=sorteo_repo)
        caso_uso1.ejecutar("MILOTO", forzar_completo=True)
        sorteo_repo.confirmar()

        draws_segunda = [_draw_valido(1), _draw_valido(2)]
        caso_uso2, _, _ = _armar(juego, draws_segunda, sorteo_repo=sorteo_repo)
        reporte = caso_uso2.ejecutar("MILOTO", forzar_completo=True)
        sorteo_repo.simular_caida()

        assert reporte.ejecucion.sorteos_duplicados == 1
        assert reporte.ejecucion.sorteos_fallidos == 0
        assert reporte.ejecucion.sorteos_nuevos == 1
        assert sorteo_repo.contar_comprometidos(juego.id) == 2

    def test_reanudacion_despues_de_un_fallo_retoma_desde_lo_realmente_comprometido(self):
        juego = _juego_miloto()
        sorteo_repo = _SorteoRepositoryTransaccional()

        draws_primera = [_draw_valido(n) for n in range(1, 6)]
        caso_uso1, _, _ = _armar(juego, draws_primera, sorteo_repo=sorteo_repo)
        caso_uso1.ejecutar("MILOTO", forzar_completo=True)
        sorteo_repo.simular_caida()

        assert sorteo_repo.contar_comprometidos(juego.id) == 5

        draws_segunda = [_draw_valido(n) for n in range(1, 9)]
        caso_uso2, _, _ = _armar(juego, draws_segunda, sorteo_repo=sorteo_repo)
        reporte2 = caso_uso2.ejecutar("MILOTO")
        sorteo_repo.simular_caida()

        assert reporte2.ejecucion.sorteos_nuevos == 3
        assert reporte2.ejecucion.sorteos_duplicados == 5
        assert sorteo_repo.numeros_comprometidos(juego.id) == set(range(1, 9))


class TestPersistenciaIncrementalRealDuranteReprocesamiento:
    def test_un_html_corrupto_a_mitad_del_lote_no_afecta_a_los_demas(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = _SorteoRepositoryTransaccional()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)
        estadistica_repo = _EstadisticaRepositoryTransaccional()
        uow = _FakeUnitOfWork(sorteo_repo, estadistica_repo)

        class ConectorConHtmlCorruptoAMitad:
            @property
            def game_code(self):
                return "MILOTO"

            def listar_html_disponibles(self):
                return [str(n) for n in range(1, 11)]

            def reprocesar_html(self, draw_id):
                if draw_id == "5":
                    raise ValueError("HTML corrupto")
                n = int(draw_id)
                return _draw_valido(n)

        caso_uso = ReprocesarSorteosDesdeHtml(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, color_repository=color_repo,
            game_factory=factory, obtener_conector=lambda c: ConectorConHtmlCorruptoAMitad(),
            unit_of_work=uow, estadistica_repository=estadistica_repo,
        )

        reporte = caso_uso.ejecutar_todos("MILOTO")
        sorteo_repo.simular_caida()

        assert reporte.creados == 9
        assert reporte.fallidos == 1
        assert 5 not in sorteo_repo.numeros_comprometidos(juego.id)
        assert sorteo_repo.numeros_comprometidos(juego.id) == (set(range(1, 11)) - {5})


class TestAtomicidadEscrituraEInvalidacion:
    """Demuestra -no asume- que la escritura del sorteo y la
    invalidación del caché estadístico comparten la misma
    transacción: si no se confirma, un rollback deshace ambas juntas;
    si se confirma, ambas sobreviven juntas."""

    def test_sin_confirmar_un_rollback_deshace_escritura_e_invalidacion_juntas(self):
        from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput

        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = _SorteoRepositoryTransaccional()
        estadistica_repo = _EstadisticaRepositoryTransaccional()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)

        # Precarga una estadística vigente y la CONFIRMA (simulando
        # que ya existía de antes, comprometida en un commit previo).
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego.id, tipo_estadistica="frecuencia_numeros", hasta_numero_sorteo=None,
            parametros={}, parametros_hash="", resultado={}, calculado_en=None, valido_hasta=None,
        ))
        estadistica_repo.confirmar()

        registrar = RegistrarSorteo(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=factory,
            estadistica_repository=estadistica_repo,
        )
        registrar.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=1, fecha=date(2026, 1, 1),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        # NO se llama confirmar() -simula un crash antes del commit.
        sorteo_repo.simular_caida()
        estadistica_repo.simular_caida()

        # Ni el sorteo ni la invalidación sobrevivieron: el sorteo no
        # esta comprometido, y la estadistica sigue vigente en el
        # estado comprometido (la invalidacion nunca se confirmo).
        assert sorteo_repo.contar_comprometidos(juego.id) == 0
        assert estadistica_repo.vigente_comprometida(juego.id, "frecuencia_numeros", None, {}) is True

    def test_confirmado_la_escritura_y_la_invalidacion_sobreviven_juntas(self):
        from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput

        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = _SorteoRepositoryTransaccional()
        estadistica_repo = _EstadisticaRepositoryTransaccional()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)
        uow = _FakeUnitOfWork(sorteo_repo, estadistica_repo)

        from app.application.interfaces.estadistica_repository import EstadisticaCalculada
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego.id, tipo_estadistica="frecuencia_numeros", hasta_numero_sorteo=None,
            parametros={}, parametros_hash="", resultado={}, calculado_en=None, valido_hasta=None,
        ))
        estadistica_repo.confirmar()

        registrar = RegistrarSorteo(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=factory,
            estadistica_repository=estadistica_repo,
        )
        registrar.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=1, fecha=date(2026, 1, 1),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        uow.confirmar()  # equivalente al commit real de get_db()
        sorteo_repo.simular_caida()  # aunque "caiga" despues, lo confirmado sobrevive
        estadistica_repo.simular_caida()

        assert sorteo_repo.contar_comprometidos(juego.id) == 1
        assert estadistica_repo.vigente_comprometida(juego.id, "frecuencia_numeros", None, {}) is False

    def test_sincronizacion_invalidaciones_confirmadas_alineadas_con_escrituras_confirmadas(self):
        """Reutiliza el escenario ya existente de HTML corrupto a
        mitad del lote: los 9 sorteos que sí se confirmaron también
        confirmaron su invalidación -la estadística precargada queda
        invalidada en el estado COMPROMETIDO, sin depender de que el
        sorteo 5 (fallido) haya hecho nada."""
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = _SorteoRepositoryTransaccional()
        estadistica_repo = _EstadisticaRepositoryTransaccional()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)
        uow = _FakeUnitOfWork(sorteo_repo, estadistica_repo)

        from app.application.interfaces.estadistica_repository import EstadisticaCalculada
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego.id, tipo_estadistica="frecuencia_numeros", hasta_numero_sorteo=None,
            parametros={}, parametros_hash="", resultado={}, calculado_en=None, valido_hasta=None,
        ))
        estadistica_repo.confirmar()

        class ConectorConHtmlCorruptoAMitad:
            @property
            def game_code(self):
                return "MILOTO"

            def listar_html_disponibles(self):
                return [str(n) for n in range(1, 11)]

            def reprocesar_html(self, draw_id):
                if draw_id == "5":
                    raise ValueError("HTML corrupto")
                return _draw_valido(int(draw_id))

        caso_uso = ReprocesarSorteosDesdeHtml(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, color_repository=color_repo,
            game_factory=factory, obtener_conector=lambda c: ConectorConHtmlCorruptoAMitad(),
            unit_of_work=uow, estadistica_repository=estadistica_repo,
        )
        reporte = caso_uso.ejecutar_todos("MILOTO")
        sorteo_repo.simular_caida()
        estadistica_repo.simular_caida()

        assert reporte.creados == 9
        assert sorteo_repo.contar_comprometidos(juego.id) == 9
        # la invalidacion del primer sorteo confirmado ya alcanza para
        # invalidar el historico completo -queda invalidada en el
        # estado comprometido, alineada con las escrituras que si se confirmaron.
        assert estadistica_repo.vigente_comprometida(juego.id, "frecuencia_numeros", None, {}) is False


class TestRollbackDelReemplazoTrasRecalculo:
    """Corrección del defecto real: un rollback tras
    guardar()+invalidar()+guardar() (recálculo) debe deshacer TODO lo
    no confirmado, sin dejar la fila reemplazada a medias."""

    def test_rollback_deshace_el_recalculo_no_confirmado(self):
        from app.application.interfaces.estadistica_repository import EstadisticaCalculada

        estadistica_repo = _EstadisticaRepositoryTransaccional()
        juego_id = _juego_miloto().id

        original = estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_numeros", hasta_numero_sorteo=None,
            parametros={"x": 1}, parametros_hash="", resultado={"v": "original"},
            calculado_en=None, valido_hasta=None,
        ))
        estadistica_repo.confirmar()  # esto SI queda comprometido

        estadistica_repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_numeros", hasta_numero_sorteo=None,
            parametros={"x": 1}, parametros_hash="", resultado={"v": "recalculada_sin_confirmar"},
            calculado_en=None, valido_hasta=None,
        ))
        # NO se llama confirmar() para el recalculo -simula un crash.
        estadistica_repo.simular_caida()

        # Lo comprometido sigue siendo la version ORIGINAL, vigente
        # -ni la invalidacion ni el recalculo no confirmados sobrevivieron.
        assert estadistica_repo.vigente_comprometida(juego_id, "frecuencia_numeros", None, {"x": 1}) is True
        fila_comprometida = next(f for f in estadistica_repo._comprometido if f.juego_id == juego_id)
        assert fila_comprometida.resultado == {"v": "original"}
        assert fila_comprometida.id == original.id
