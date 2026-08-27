"""
Test de integración: reimportación completa de la familia Baloto.

Simula lo que pediste validar explícitamente: sincronizar BALOTO y
BALOTO_REVANCHA (desde el mismo listado subyacente, como hace el
scraper real) y confirmar que:
  - cada sorteo termina con AMBOS resultados disponibles;
  - no hay duplicados;
  - el reporte de calidad/cobertura sigue funcionando, calculado por
    juego (igual que para MiLoto y ColorLoto).
"""
from __future__ import annotations

import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.application.interfaces.draw_source_connector import (
    DrawDetail,
    DrawSourceConnector,
    HealthStatus,
    SyncFetchResult,
)
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.generar_reporte_calidad_datos import GenerarReporteCalidadDatos
from app.application.use_cases.obtener_sorteo_con_pareja import ObtenerSorteoConPareja
from app.application.use_cases.sincronizar_sorteos import SincronizarSorteos
from app.domain.entities.juego import Juego
from tests.unit.fakes import (
    FakeColorRepository,
    FakeEstadisticaRepository,
    FakeJuegoRepository,
    FakeSincronizacionRepository,
    FakeSorteoRepository,
    FakeUnitOfWork,
)

_SORTEOS_OFICIALES = {
    2683: {"fecha": date(2026, 7, 15), "baloto": (2, 4, 8, 12, 24, 4), "revancha": (10, 22, 27, 30, 35, 16)},
    2684: {"fecha": date(2026, 7, 18), "baloto": (8, 17, 19, 24, 26, 9), "revancha": (5, 6, 31, 32, 34, 8)},
    2685: {"fecha": date(2026, 7, 22), "baloto": (1, 2, 3, 4, 5, 6), "revancha": (7, 8, 9, 10, 11, 12)},
}


class _ConectorFamiliaBaloto(DrawSourceConnector):
    def __init__(self, familia: str):
        self._familia = familia

    @property
    def game_code(self) -> str:
        return "BALOTO" if self._familia == "baloto" else "BALOTO_REVANCHA"

    def fetch_draws(self, ultimo_conocido=None, max_paginas=None):
        return []

    def fetch_draw_detail(self, draw_id):
        raise NotImplementedError

    def sync(self, ultimo_conocido=None, max_paginas=None):
        draws = []
        for numero, datos in _SORTEOS_OFICIALES.items():
            if ultimo_conocido is not None and numero <= ultimo_conocido:
                continue
            numeros_completos = datos[self._familia]
            draws.append(DrawDetail(
                draw_id=str(numero), numero_sorteo=numero, fecha=datos["fecha"],
                numeros=numeros_completos[:5], superbalota=numeros_completos[5],
            ))
        return SyncFetchResult(draws=draws, fallidos=[], paginas_recorridas=1, duracion_ms=5)

    def health_check(self):
        return HealthStatus(True, 1.0, "ok")


def _juego_baloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="BALOTO", nombre="Baloto", rango_min=1, rango_max=43,
        cantidad_numeros=5, tiene_superbalota=True, superbalota_min=1, superbalota_max=16,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


def _juego_revancha() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="BALOTO_REVANCHA", nombre="Baloto Revancha", rango_min=1, rango_max=43,
        cantidad_numeros=5, tiene_superbalota=True, superbalota_min=1, superbalota_max=16,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


class TestReimportacionCompletaFamiliaBaloto:
    def test_ambos_juegos_quedan_completamente_poblados_sin_duplicados(self):
        baloto, revancha = _juego_baloto(), _juego_revancha()
        juego_repo = FakeJuegoRepository(juegos=[baloto, revancha])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)
        uow = FakeUnitOfWork()

        conectores = {"BALOTO": _ConectorFamiliaBaloto("baloto"), "BALOTO_REVANCHA": _ConectorFamiliaBaloto("revancha")}

        sync_baloto = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
            color_repository=color_repo, game_factory=factory,
            obtener_conector=lambda c: conectores[c], unit_of_work=uow,
            estadistica_repository=FakeEstadisticaRepository(),
        )
        sync_revancha = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
            color_repository=color_repo, game_factory=factory,
            obtener_conector=lambda c: conectores[c], unit_of_work=uow,
            estadistica_repository=FakeEstadisticaRepository(),
        )

        rep_baloto = sync_baloto.ejecutar("BALOTO")
        rep_revancha = sync_revancha.ejecutar("BALOTO_REVANCHA")

        assert rep_baloto.ejecucion.sorteos_nuevos == 3
        assert rep_revancha.ejecucion.sorteos_nuevos == 3
        assert sorteo_repo.contar_por_juego(baloto.id) == 3
        assert sorteo_repo.contar_por_juego(revancha.id) == 3

        pareja_uc = ObtenerSorteoConPareja(sorteo_repo, juego_repo)
        for numero, datos in _SORTEOS_OFICIALES.items():
            s_baloto = sorteo_repo.obtener_por_numero(baloto.id, numero)
            s_revancha = sorteo_repo.obtener_por_numero(revancha.id, numero)
            assert s_baloto is not None and s_revancha is not None

            resultado = pareja_uc.ejecutar(s_baloto.id)
            assert resultado.sorteo_pareja is not None
            assert resultado.sorteo_pareja.id == s_revancha.id
            assert s_baloto.resultado.numeros != s_revancha.resultado.numeros

        assert sorteo_repo.contar_por_juego(baloto.id) + sorteo_repo.contar_por_juego(revancha.id) == 6

    def test_reimportar_de_nuevo_no_duplica_nada(self):
        baloto, revancha = _juego_baloto(), _juego_revancha()
        juego_repo = FakeJuegoRepository(juegos=[baloto, revancha])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)
        uow = FakeUnitOfWork()
        conectores = {"BALOTO": _ConectorFamiliaBaloto("baloto"), "BALOTO_REVANCHA": _ConectorFamiliaBaloto("revancha")}

        sync_baloto = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
            color_repository=color_repo, game_factory=factory,
            obtener_conector=lambda c: conectores[c], unit_of_work=uow,
            estadistica_repository=FakeEstadisticaRepository(),
        )

        sync_baloto.ejecutar("BALOTO", forzar_completo=True)
        reporte_2 = sync_baloto.ejecutar("BALOTO", forzar_completo=True)

        assert reporte_2.ejecucion.sorteos_nuevos == 0
        assert reporte_2.ejecucion.sorteos_duplicados == 3
        assert sorteo_repo.contar_por_juego(baloto.id) == 3

    def test_reporte_de_calidad_calcula_cobertura_por_juego_de_forma_independiente(self):
        baloto, revancha = _juego_baloto(), _juego_revancha()
        juego_repo = FakeJuegoRepository(juegos=[baloto, revancha])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)
        uow = FakeUnitOfWork()
        conectores = {"BALOTO": _ConectorFamiliaBaloto("baloto"), "BALOTO_REVANCHA": _ConectorFamiliaBaloto("revancha")}

        sync_baloto = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
            color_repository=color_repo, game_factory=factory,
            obtener_conector=lambda c: conectores[c], unit_of_work=uow,
            estadistica_repository=FakeEstadisticaRepository(),
        )
        sync_revancha = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
            color_repository=color_repo, game_factory=factory,
            obtener_conector=lambda c: conectores[c], unit_of_work=uow,
            estadistica_repository=FakeEstadisticaRepository(),
        )
        sync_baloto.ejecutar("BALOTO")
        sync_revancha.ejecutar("BALOTO_REVANCHA")

        reporte_uc = GenerarReporteCalidadDatos(juego_repo, sorteo_repo, sync_repo)
        rep_baloto = reporte_uc.ejecutar("BALOTO")
        rep_revancha = reporte_uc.ejecutar("BALOTO_REVANCHA")

        assert rep_baloto.total_sorteos_almacenados == 3
        assert rep_baloto.cobertura_porcentaje == 100.0
        assert rep_revancha.total_sorteos_almacenados == 3
        assert rep_revancha.cobertura_porcentaje == 100.0
