import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.application.use_cases.generar_reporte_calidad_datos import GenerarReporteCalidadDatos
from app.domain.entities.juego import Juego
from app.domain.entities.sincronizacion import EjecucionSincronizacion
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.combination import Combination
from tests.unit.fakes import FakeJuegoRepository, FakeSincronizacionRepository, FakeSorteoRepository


def _juego_miloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto", rango_min=1, rango_max=39,
        cantidad_numeros=5, tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


class TestGenerarReporteCalidadDatos:
    def test_sin_sincronizaciones_previas_reporta_ceros_pero_no_falla(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()
        caso_uso = GenerarReporteCalidadDatos(juego_repo, sorteo_repo, sync_repo)

        reporte = caso_uso.ejecutar("MILOTO")

        assert reporte.ultima_sincronizacion_en is None
        assert reporte.total_importados == 0
        assert reporte.total_sorteos_almacenados == 0
        assert reporte.cobertura_porcentaje == 0.0

    def test_combina_la_ultima_sincronizacion_con_el_estado_real_de_la_bd(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()

        for numero in (1, 2, 3, 5):  # hueco intencional en el 4
            sorteo_repo.guardar(Sorteo(
                id=None, juego_id=juego.id, numero_sorteo=numero, fecha=date(2026, 1, numero),
                dia_semana="lunes", resultado=Combination(numeros=(1, 2, 3, 4, 5)),
            ))

        ejecucion = EjecucionSincronizacion(
            id=None, juego_id=juego.id, conector="MiLotoConnector",
            iniciado_en=datetime.now(timezone.utc), estado="completado",
            sorteos_nuevos=4, sorteos_fallidos=1, sorteos_duplicados=2,
            sorteos_incompletos=1, total_sorteos_encontrados=7, duracion_ms=1200,
        )
        sync_repo.guardar(ejecucion)

        caso_uso = GenerarReporteCalidadDatos(juego_repo, sorteo_repo, sync_repo)
        reporte = caso_uso.ejecutar("MILOTO")

        assert reporte.total_encontrados == 7
        assert reporte.total_importados == 4
        assert reporte.duplicados_detectados == 2
        assert reporte.sorteos_con_error == 1
        assert reporte.sorteos_incompletos == 1
        assert reporte.porcentaje_exito == round(100 * 4 / 7, 1)

        assert reporte.total_sorteos_almacenados == 4
        assert reporte.primer_sorteo == 1
        assert reporte.ultimo_sorteo == 5
        assert reporte.huecos == [4]
        assert reporte.cobertura_porcentaje == 80.0

    def test_cobertura_100_por_ciento_sin_huecos(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()

        for numero in (1, 2, 3):
            sorteo_repo.guardar(Sorteo(
                id=None, juego_id=juego.id, numero_sorteo=numero, fecha=date(2026, 1, numero),
                dia_semana="lunes", resultado=Combination(numeros=(1, 2, 3, 4, 5)),
            ))

        caso_uso = GenerarReporteCalidadDatos(juego_repo, sorteo_repo, sync_repo)
        reporte = caso_uso.ejecutar("MILOTO")

        assert reporte.cobertura_porcentaje == 100.0
        assert reporte.huecos == []


class TestObtenerEstadoImportacionNoBloqueaConHealthCheck:
    """Regresión: la carga inicial del panel no debe llamar a
    health_check() (una petición HTTP real) para no bloquear la
    página si el origen está lento o caído."""

    def test_ejecutar_con_verificar_salud_false_no_llama_al_conector(self):
        from app.application.use_cases.obtener_estado_importacion import ObtenerEstadoImportacion

        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()

        llamadas = {"n": 0}

        class ConectorQueCuenta:
            def health_check(self):
                llamadas["n"] += 1
                raise AssertionError("no debería llamarse durante la carga inicial del panel")

        caso_uso = ObtenerEstadoImportacion(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo,
            sincronizacion_repository=sync_repo, obtener_conector=lambda c: ConectorQueCuenta(),
        )

        estados = caso_uso.ejecutar(verificar_salud=False)

        assert llamadas["n"] == 0
        assert estados[0].salud is None

    def test_verificar_salud_de_si_llama_al_conector_puntualmente(self):
        from app.application.interfaces.draw_source_connector import HealthStatus
        from app.application.use_cases.obtener_estado_importacion import ObtenerEstadoImportacion

        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        sync_repo = FakeSincronizacionRepository()

        class ConectorSano:
            def health_check(self):
                return HealthStatus(True, 42.0, "ok")

        caso_uso = ObtenerEstadoImportacion(
            juego_repository=juego_repo, sorteo_repository=sorteo_repo,
            sincronizacion_repository=sync_repo, obtener_conector=lambda c: ConectorSano(),
        )

        salud = caso_uso.verificar_salud_de("MILOTO")
        assert salud.disponible is True
        assert salud.latencia_ms == 42.0
