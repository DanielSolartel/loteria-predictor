import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from app.application.exceptions import SorteoNoEncontradoError
from app.application.use_cases.obtener_sorteo_con_pareja import ObtenerSorteoConPareja
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.combination import Combination
from tests.unit.fakes import FakeJuegoRepository, FakeSorteoRepository


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


def _juego_miloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto", rango_min=1, rango_max=39,
        cantidad_numeros=5, tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


class TestObtenerSorteoConPareja:
    def test_baloto_con_revancha_ya_importada_trae_ambos(self):
        baloto, revancha = _juego_baloto(), _juego_revancha()
        juego_repo = FakeJuegoRepository(juegos=[baloto, revancha])
        sorteo_repo = FakeSorteoRepository()

        s_baloto = sorteo_repo.guardar(Sorteo(
            id=None, juego_id=baloto.id, numero_sorteo=2684, fecha=date(2026, 7, 18),
            dia_semana="sabado", resultado=Combination(numeros=(8, 17, 19, 24, 26), superbalota=9),
        ))
        sorteo_repo.guardar(Sorteo(
            id=None, juego_id=revancha.id, numero_sorteo=2684, fecha=date(2026, 7, 18),
            dia_semana="sabado", resultado=Combination(numeros=(5, 6, 31, 32, 34), superbalota=8),
        ))

        caso_uso = ObtenerSorteoConPareja(sorteo_repo, juego_repo)
        resultado = caso_uso.ejecutar(s_baloto.id)

        assert resultado.juego.codigo == "BALOTO"
        assert resultado.juego_pareja.codigo == "BALOTO_REVANCHA"
        assert resultado.sorteo_pareja is not None
        assert resultado.sorteo_pareja.resultado.numeros == (5, 6, 31, 32, 34)
        assert resultado.sorteo_pareja.resultado.superbalota == 8

    def test_revancha_con_baloto_ya_importado_trae_ambos_en_el_otro_sentido(self):
        baloto, revancha = _juego_baloto(), _juego_revancha()
        juego_repo = FakeJuegoRepository(juegos=[baloto, revancha])
        sorteo_repo = FakeSorteoRepository()

        sorteo_repo.guardar(Sorteo(
            id=None, juego_id=baloto.id, numero_sorteo=2684, fecha=date(2026, 7, 18),
            dia_semana="sabado", resultado=Combination(numeros=(8, 17, 19, 24, 26), superbalota=9),
        ))
        s_revancha = sorteo_repo.guardar(Sorteo(
            id=None, juego_id=revancha.id, numero_sorteo=2684, fecha=date(2026, 7, 18),
            dia_semana="sabado", resultado=Combination(numeros=(5, 6, 31, 32, 34), superbalota=8),
        ))

        caso_uso = ObtenerSorteoConPareja(sorteo_repo, juego_repo)
        resultado = caso_uso.ejecutar(s_revancha.id)

        assert resultado.juego.codigo == "BALOTO_REVANCHA"
        assert resultado.juego_pareja.codigo == "BALOTO"
        assert resultado.sorteo_pareja.resultado.numeros == (8, 17, 19, 24, 26)

    def test_baloto_sin_revancha_importada_todavia_no_falla(self):
        """Si solo se sincronizó una de las dos familias, la interfaz
        debe poder mostrarlo con claridad, no fallar."""
        baloto, revancha = _juego_baloto(), _juego_revancha()
        juego_repo = FakeJuegoRepository(juegos=[baloto, revancha])
        sorteo_repo = FakeSorteoRepository()

        s_baloto = sorteo_repo.guardar(Sorteo(
            id=None, juego_id=baloto.id, numero_sorteo=2684, fecha=date(2026, 7, 18),
            dia_semana="sabado", resultado=Combination(numeros=(8, 17, 19, 24, 26), superbalota=9),
        ))

        caso_uso = ObtenerSorteoConPareja(sorteo_repo, juego_repo)
        resultado = caso_uso.ejecutar(s_baloto.id)

        assert resultado.juego_pareja.codigo == "BALOTO_REVANCHA"
        assert resultado.sorteo_pareja is None  # aún no importado, pero no revienta

    def test_miloto_no_tiene_pareja_nunca(self):
        """Confirma que el caso de uso es transparente para juegos
        sin familia -no les agrega ningún comportamiento nuevo."""
        miloto = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[miloto])
        sorteo_repo = FakeSorteoRepository()

        s = sorteo_repo.guardar(Sorteo(
            id=None, juego_id=miloto.id, numero_sorteo=1, fecha=date(2026, 1, 1),
            dia_semana="lunes", resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))

        caso_uso = ObtenerSorteoConPareja(sorteo_repo, juego_repo)
        resultado = caso_uso.ejecutar(s.id)

        assert resultado.juego_pareja is None
        assert resultado.sorteo_pareja is None

    def test_sorteo_inexistente_lanza_error_claro(self):
        juego_repo = FakeJuegoRepository(juegos=[])
        sorteo_repo = FakeSorteoRepository()
        caso_uso = ObtenerSorteoConPareja(sorteo_repo, juego_repo)

        with pytest.raises(SorteoNoEncontradoError):
            caso_uso.ejecutar(uuid.uuid4())

    def test_no_confunde_sorteos_de_numero_distinto(self):
        """El emparejamiento es estrictamente por numero_sorteo -un
        Baloto #10 nunca debe emparejarse con una Revancha #11."""
        baloto, revancha = _juego_baloto(), _juego_revancha()
        juego_repo = FakeJuegoRepository(juegos=[baloto, revancha])
        sorteo_repo = FakeSorteoRepository()

        s_baloto = sorteo_repo.guardar(Sorteo(
            id=None, juego_id=baloto.id, numero_sorteo=10, fecha=date(2026, 1, 1),
            dia_semana="lunes", resultado=Combination(numeros=(1, 2, 3, 4, 5), superbalota=1),
        ))
        sorteo_repo.guardar(Sorteo(
            id=None, juego_id=revancha.id, numero_sorteo=11, fecha=date(2026, 1, 2),
            dia_semana="martes", resultado=Combination(numeros=(6, 7, 8, 9, 10), superbalota=2),
        ))

        caso_uso = ObtenerSorteoConPareja(sorteo_repo, juego_repo)
        resultado = caso_uso.ejecutar(s_baloto.id)

        assert resultado.sorteo_pareja is None
