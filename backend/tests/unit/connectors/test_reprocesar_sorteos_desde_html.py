import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.application.interfaces.draw_source_connector import DrawDetail
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.reprocesar_sorteos_desde_html import ReprocesarSorteosDesdeHtml
from app.domain.entities.juego import Juego
from tests.unit.fakes import (
    FakeColorRepository,
    FakeEstadisticaRepository,
    FakeJuegoRepository,
    FakeSorteoRepository,
    FakeUnitOfWork,
)


class _ConectorConHtmlFake:
    """Simula un BaseConnector real: expone reprocesar_html y
    listar_html_disponibles operando sobre un diccionario en memoria
    que hace las veces de storage/html/."""

    def __init__(self, html_por_draw_id: dict[str, DrawDetail]):
        self._html_por_draw_id = html_por_draw_id

    @property
    def game_code(self):
        return "MILOTO"

    def reprocesar_html(self, draw_id: str) -> DrawDetail:
        if draw_id not in self._html_por_draw_id:
            raise ValueError(f"No hay HTML para {draw_id}")
        return self._html_por_draw_id[draw_id]

    def listar_html_disponibles(self) -> list[str]:
        return list(self._html_por_draw_id.keys())


def _juego_miloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto", rango_min=1, rango_max=39,
        cantidad_numeros=5, tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


def _armar(juego, conector):
    juego_repo = FakeJuegoRepository(juegos=[juego])
    sorteo_repo = FakeSorteoRepository()
    color_repo = FakeColorRepository()
    factory = GameFactory(color_repository=color_repo)
    caso_uso = ReprocesarSorteosDesdeHtml(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, color_repository=color_repo,
        game_factory=factory, obtener_conector=lambda c: conector, unit_of_work=FakeUnitOfWork(),
        estadistica_repository=FakeEstadisticaRepository(),
    )
    return caso_uso, sorteo_repo


class TestReprocesarSorteosDesdeHtml:
    def test_crea_sorteos_nuevos_a_partir_del_html_almacenado(self):
        juego = _juego_miloto()
        conector = _ConectorConHtmlFake({
            "1": DrawDetail(draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 5)),
            "2": DrawDetail(draw_id="2", numero_sorteo=2, fecha=date(2026, 1, 2), numeros=(5, 6, 7, 8, 9)),
        })
        caso_uso, sorteo_repo = _armar(juego, conector)

        reporte = caso_uso.ejecutar_todos("MILOTO")

        assert reporte.total_html_disponibles == 2
        assert reporte.creados == 2
        assert reporte.actualizados == 0
        assert reporte.fallidos == 0
        assert sorteo_repo.contar_por_juego(juego.id) == 2

    def test_reprocesar_un_sorteo_ya_existente_lo_actualiza_no_lo_duplica(self):
        """Semántica de upsert: reprocesar dos veces el mismo HTML no
        debe crear un duplicado -debe sobrescribir con EditarSorteo."""
        juego = _juego_miloto()
        conector = _ConectorConHtmlFake({
            "1": DrawDetail(draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 5)),
        })
        caso_uso, sorteo_repo = _armar(juego, conector)

        primer_reporte = caso_uso.ejecutar_todos("MILOTO")
        assert primer_reporte.creados == 1

        segundo_reporte = caso_uso.ejecutar_todos("MILOTO")
        assert segundo_reporte.creados == 0
        assert segundo_reporte.actualizados == 1
        assert sorteo_repo.contar_por_juego(juego.id) == 1  # sigue habiendo solo 1, no se duplicó

    def test_usa_las_mismas_validaciones_de_dominio_que_la_sincronizacion_en_vivo(self):
        """Un HTML que produce números fuera de rango debe fallar
        exactamente igual que fallaría en SincronizarSorteos -misma
        instancia de LotteryGame, mismas reglas."""
        juego = _juego_miloto()
        conector = _ConectorConHtmlFake({
            "1": DrawDetail(draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 99)),
        })
        caso_uso, sorteo_repo = _armar(juego, conector)

        reporte = caso_uso.ejecutar_todos("MILOTO")

        assert reporte.fallidos == 1
        assert reporte.creados == 0
        assert sorteo_repo.contar_por_juego(juego.id) == 0

    def test_un_html_corrupto_no_detiene_el_resto_del_lote(self):
        juego = _juego_miloto()

        class ConectorConUnoCorrupto(_ConectorConHtmlFake):
            def reprocesar_html(self, draw_id):
                if draw_id == "corrupto":
                    raise ValueError("HTML corrupto, no se pudo parsear")
                return super().reprocesar_html(draw_id)

        conector = ConectorConUnoCorrupto({
            "1": DrawDetail(draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 5)),
            "corrupto": None,  # nunca se usa realmente, solo necesita estar en listar_html_disponibles
            "2": DrawDetail(draw_id="2", numero_sorteo=2, fecha=date(2026, 1, 2), numeros=(6, 7, 8, 9, 10)),
        })
        caso_uso, sorteo_repo = _armar(juego, conector)

        reporte = caso_uso.ejecutar_todos("MILOTO")

        assert reporte.total_html_disponibles == 3
        assert reporte.creados == 2  # los 2 buenos se procesaron igual
        assert reporte.fallidos == 1

    def test_marca_incompleto_cuando_el_draw_trae_advertencias_de_parseo(self):
        juego = _juego_miloto()
        conector = _ConectorConHtmlFake({
            "1": DrawDetail(
                draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 5),
                advertencias=("No se pudo extraer la tabla de premios",),
            ),
        })
        caso_uso, _ = _armar(juego, conector)

        reporte = caso_uso.ejecutar_todos("MILOTO")

        assert reporte.creados == 1
        assert reporte.incompletos == 1

    def test_ejecutar_uno_reprocesa_un_solo_draw_id_puntual(self):
        juego = _juego_miloto()
        conector = _ConectorConHtmlFake({
            "1": DrawDetail(draw_id="1", numero_sorteo=1, fecha=date(2026, 1, 1), numeros=(1, 2, 3, 4, 5)),
        })
        caso_uso, sorteo_repo = _armar(juego, conector)

        resultado = caso_uso.ejecutar_uno("MILOTO", "1")

        assert resultado.accion == "creado"
        assert sorteo_repo.contar_por_juego(juego.id) == 1
