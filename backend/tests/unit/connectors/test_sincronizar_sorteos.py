import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.draw_source_connector import (
    DrawDetail,
    DrawFetchError,
    DrawSourceConnector,
    HealthStatus,
    SyncFetchResult,
)
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.sincronizar_sorteos import SincronizarSorteos
from app.domain.entities.juego import Juego
from tests.unit.fakes import (
    FakeUnitOfWork,
    FakeColorRepository,
    FakeEstadisticaRepository,
    FakeJuegoRepository,
    FakeSincronizacionRepository,
    FakeSorteoRepository,
)


class _ConectorFake(DrawSourceConnector):
    """Conector de prueba: sync() devuelve un guion fijo de sorteos
    (algunos válidos, uno inválido, uno fallido en la obtención) para
    verificar que SincronizarSorteos maneja ambos tipos de fallo sin
    detenerse."""

    def __init__(self, respuesta: SyncFetchResult, ultimo_conocido_esperado: int | None = "no_verificar"):
        self._respuesta = respuesta
        self._ultimo_conocido_esperado = ultimo_conocido_esperado

    @property
    def game_code(self) -> str:
        return "MILOTO"

    def fetch_draws(self, ultimo_conocido=None, max_paginas=None):
        return []

    def fetch_draw_detail(self, draw_id):
        raise NotImplementedError

    def sync(self, ultimo_conocido=None, max_paginas=None) -> SyncFetchResult:
        if self._ultimo_conocido_esperado != "no_verificar":
            assert ultimo_conocido == self._ultimo_conocido_esperado, (
                f"se esperaba ultimo_conocido={self._ultimo_conocido_esperado}, "
                f"se recibió {ultimo_conocido}"
            )
        return self._respuesta

    def health_check(self) -> HealthStatus:
        return HealthStatus(True, 10.0, "ok")


def _juego_miloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto", rango_min=1, rango_max=39,
        cantidad_numeros=5, tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


def _armar_caso_de_uso(juego: Juego, conector: DrawSourceConnector):
    juego_repo = FakeJuegoRepository(juegos=[juego])
    sorteo_repo = FakeSorteoRepository()
    sync_repo = FakeSincronizacionRepository()
    color_repo = FakeColorRepository()
    factory = GameFactory(color_repository=color_repo)
    caso_uso = SincronizarSorteos(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo,
        sincronizacion_repository=sync_repo, color_repository=color_repo,
        game_factory=factory, obtener_conector=lambda codigo: conector,
        unit_of_work=FakeUnitOfWork(),
        estadistica_repository=FakeEstadisticaRepository(),
    )
    return caso_uso, sorteo_repo, sync_repo


class TestSincronizarSorteos:
    def test_importa_solo_los_sorteos_validos(self):
        juego = _juego_miloto()
        respuesta = SyncFetchResult(
            draws=[
                DrawDetail(draw_id="101", numero_sorteo=101, fecha=date(2026, 7, 1), numeros=(1, 2, 3, 4, 5)),
                DrawDetail(draw_id="102", numero_sorteo=102, fecha=date(2026, 7, 2), numeros=(1, 2, 3, 4, 99)),
                DrawDetail(draw_id="103", numero_sorteo=103, fecha=date(2026, 7, 3), numeros=(6, 7, 8, 9, 10)),
            ],
            fallidos=[DrawFetchError(draw_id="104", numero_sorteo=104, error="timeout simulado")],
            paginas_recorridas=2, duracion_ms=450,
        )
        caso_uso, sorteo_repo, _ = _armar_caso_de_uso(juego, _ConectorFake(respuesta, ultimo_conocido_esperado=None))

        reporte = caso_uso.ejecutar("MILOTO")

        assert reporte.ejecucion.sorteos_nuevos == 2
        assert sorteo_repo.contar_por_juego(juego.id) == 2

    def test_registra_ambos_tipos_de_fallo_por_separado(self):
        juego = _juego_miloto()
        respuesta = SyncFetchResult(
            draws=[DrawDetail(draw_id="102", numero_sorteo=102, fecha=date(2026, 7, 2), numeros=(1, 2, 3, 4, 99))],
            fallidos=[DrawFetchError(draw_id="104", numero_sorteo=104, error="timeout simulado")],
            paginas_recorridas=1, duracion_ms=100,
        )
        caso_uso, _, _ = _armar_caso_de_uso(juego, _ConectorFake(respuesta))

        reporte = caso_uso.ejecutar("MILOTO")

        etapas = {e["etapa"] for e in reporte.ejecucion.detalle_errores}
        assert etapas == {"obtencion", "validacion_dominio"}
        assert reporte.ejecucion.sorteos_fallidos == 2

    def test_estado_completado_cuando_hay_al_menos_un_exito(self):
        juego = _juego_miloto()
        respuesta = SyncFetchResult(
            draws=[DrawDetail(draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 5))],
            fallidos=[], paginas_recorridas=1, duracion_ms=10,
        )
        caso_uso, _, _ = _armar_caso_de_uso(juego, _ConectorFake(respuesta))
        reporte = caso_uso.ejecutar("MILOTO")
        assert reporte.ejecucion.estado == "completado"

    def test_propaga_ultimo_conocido_al_conector_para_incrementalidad(self):
        """Verifica el requisito central: la sincronización incremental
        realmente evita descargas duplicadas, pasando al conector el
        número del último sorteo ya almacenado."""
        juego = _juego_miloto()
        sorteo_repo = FakeSorteoRepository()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sync_repo = FakeSincronizacionRepository()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)

        # Sembrar un sorteo ya existente (numero_sorteo=50)
        from app.domain.entities.sorteo import Sorteo
        from app.domain.value_objects.combination import Combination
        sorteo_repo.guardar(Sorteo(
            id=None, juego_id=juego.id, numero_sorteo=50, fecha=date(2026, 6, 1), dia_semana="lunes",
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))

        conector = _ConectorFake(SyncFetchResult(), ultimo_conocido_esperado=50)
        caso_uso = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
            color_repository=color_repo, game_factory=factory, obtener_conector=lambda c: conector,
            unit_of_work=FakeUnitOfWork(),
            estadistica_repository=FakeEstadisticaRepository(),
        )
        caso_uso.ejecutar("MILOTO")  # las aserciones internas del conector fake validan el argumento

    def test_forzar_completo_ignora_el_ultimo_conocido(self):
        juego = _juego_miloto()
        sorteo_repo = FakeSorteoRepository()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        from app.domain.entities.sorteo import Sorteo
        from app.domain.value_objects.combination import Combination
        sorteo_repo.guardar(Sorteo(
            id=None, juego_id=juego.id, numero_sorteo=50, fecha=date(2026, 6, 1), dia_semana="lunes",
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)
        conector = _ConectorFake(SyncFetchResult(), ultimo_conocido_esperado=None)  # se espera None, no 50
        caso_uso = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo,
            sincronizacion_repository=FakeSincronizacionRepository(), color_repository=color_repo,
            game_factory=factory, obtener_conector=lambda c: conector,
            unit_of_work=FakeUnitOfWork(),
            estadistica_repository=FakeEstadisticaRepository(),
        )
        caso_uso.ejecutar("MILOTO", forzar_completo=True)

    def test_no_reimporta_sorteos_ya_existentes_en_corridas_sucesivas(self):
        """Simula dos sincronizaciones consecutivas: la segunda no
        debe reintroducir sorteos ya guardados en la primera."""
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)

        primera_respuesta = SyncFetchResult(
            draws=[DrawDetail(draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 5))],
            fallidos=[], paginas_recorridas=1, duracion_ms=10,
        )
        caso_uso1 = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
            color_repository=color_repo, game_factory=factory,
            obtener_conector=lambda c: _ConectorFake(primera_respuesta, ultimo_conocido_esperado=None),
            unit_of_work=FakeUnitOfWork(),
            estadistica_repository=FakeEstadisticaRepository(),
        )
        caso_uso1.ejecutar("MILOTO")
        assert sorteo_repo.contar_por_juego(juego.id) == 1

        # Segunda corrida: el conector fake exige que le llegue ultimo_conocido=1
        caso_uso2 = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, sincronizacion_repository=sync_repo,
            color_repository=color_repo, game_factory=factory,
            obtener_conector=lambda c: _ConectorFake(SyncFetchResult(), ultimo_conocido_esperado=1),
            unit_of_work=FakeUnitOfWork(),
            estadistica_repository=FakeEstadisticaRepository(),
        )
        caso_uso2.ejecutar("MILOTO")
        assert sorteo_repo.contar_por_juego(juego.id) == 1  # sigue habiendo 1, no se duplicó

    def test_juego_inexistente_lanza_error_claro(self):
        juego_repo = FakeJuegoRepository(juegos=[])
        sorteo_repo = FakeSorteoRepository()
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)
        caso_uso = SincronizarSorteos(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo,
            sincronizacion_repository=FakeSincronizacionRepository(), color_repository=color_repo,
            game_factory=factory, obtener_conector=lambda c: None,
            unit_of_work=FakeUnitOfWork(),
            estadistica_repository=FakeEstadisticaRepository(),
        )
        with pytest.raises(JuegoNoEncontradoError):
            caso_uso.ejecutar("INEXISTENTE")

    def test_fallo_total_del_conector_no_lanza_excepcion_sino_que_marca_fallida(self):
        """Si el conector explota por completo (p.ej. sitio caído),
        SincronizarSorteos no debe propagar la excepción -debe
        registrar la ejecución como fallida para que el dashboard lo
        muestre, sin tumbar el proceso que la invoca."""
        juego = _juego_miloto()

        class ConectorQueExplota(DrawSourceConnector):
            @property
            def game_code(self): return "MILOTO"
            def fetch_draws(self, ultimo_conocido=None, max_paginas=None): return []
            def fetch_draw_detail(self, draw_id): raise NotImplementedError
            def sync(self, ultimo_conocido=None, max_paginas=None):
                raise ConnectionError("origen totalmente inalcanzable")
            def health_check(self): return HealthStatus(False, None, "caído")

        caso_uso, _, sync_repo = _armar_caso_de_uso(juego, ConectorQueExplota())
        reporte = caso_uso.ejecutar("MILOTO")

        assert reporte.ejecucion.estado == "fallido"
        assert sync_repo.obtener_ultima(juego.id) is not None


class TestReimportarSorteoToleraFallosDeRed:
    """Regresión encontrada en la revisión técnica final: a diferencia
    de SincronizarSorteos, ReimportarSorteo no envolvía la llamada al
    conector -un fallo de red se propagaba como excepción de
    infraestructura sin capturar (500 sin manejar en la capa web)."""

    def test_fallo_de_conector_se_traduce_a_excepcion_de_dominio(self):
        import uuid
        from datetime import date

        from app.application.exceptions import ConectorNoDisponibleError
        from app.application.use_cases.reimportar_sorteo import ReimportarSorteo
        from app.domain.entities.sorteo import Sorteo
        from app.domain.value_objects.combination import Combination
        from app.domain.entities.juego import Juego

        juego = Juego(
            id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto", rango_min=1, rango_max=39,
            cantidad_numeros=5, tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
            tiene_color=False, permite_repeticion=False, activo=True,
        )
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        sorteo = sorteo_repo.guardar(Sorteo(
            id=None, juego_id=juego.id, numero_sorteo=1, fecha=date(2026, 1, 1), dia_semana="lunes",
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        color_repo = FakeColorRepository()
        factory = GameFactory(color_repository=color_repo)

        class ConectorQueFalla:
            def fetch_draw_detail(self, draw_id):
                raise ConnectionError("origen inalcanzable")

        caso_uso = ReimportarSorteo(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo, color_repository=color_repo,
            game_factory=factory, obtener_conector=lambda c: ConectorQueFalla(),
            estadistica_repository=FakeEstadisticaRepository(),
        )

        with pytest.raises(ConectorNoDisponibleError):
            caso_uso.ejecutar(sorteo.id)
