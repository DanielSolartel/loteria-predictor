"""
Tests de ListarSorteos: paginación, orden y filtros.

Escenario central: reproduce el reporte real ("MiLoto tiene 583
sorteos en la base de datos pero la vista solo mostraba ~100, sin
forma de ver el resto"). Antes de este fix, `ListarSorteos` nunca
recibía `offset`/`limite` distintos del valor por defecto -el bug
estaba en la capa de presentación, no en el repositorio (que ya
usaba LIMIT/OFFSET real). Estos tests verifican el caso de uso, que
es lo que consume el router; el uso real de LIMIT/OFFSET a nivel SQL
se verifica indirectamente porque `FakeSorteoRepository` implementa
la misma paginación en memoria con la misma interfaz.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest

from app.application.exceptions import JuegoNoEncontradoError
from app.application.use_cases.listar_sorteos import ListarSorteos, ListarSorteosInput
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.combination import Combination
from tests.unit.fakes import FakeJuegoRepository, FakeSorteoRepository


def _juego_miloto() -> Juego:
    return Juego(
        id=uuid.uuid4(), codigo="MILOTO", nombre="MiLoto", rango_min=1, rango_max=39,
        cantidad_numeros=5, tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=False, permite_repeticion=False, activo=True,
    )


def _sembrar_583_sorteos(sorteo_repo: FakeSorteoRepository, juego: Juego) -> date:
    base_fecha = date(2020, 1, 1)
    for n in range(1, 584):
        sorteo_repo.guardar(Sorteo(
            id=None, juego_id=juego.id, numero_sorteo=n, fecha=base_fecha + timedelta(days=n),
            dia_semana="lunes", resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
    return base_fecha


class TestPaginacionEscenarioReal:
    """Reproduce exactamente el reporte del usuario: 583 sorteos de
    MiLoto, verificando que se puedan navegar TODOS, no solo los
    primeros ~100."""

    def test_pagina_1_trae_exactamente_el_tamano_pedido(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", limite=100, offset=0))

        assert r.total == 583
        assert len(r.sorteos) == 100

    def test_ultima_pagina_trae_el_resto_exacto(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", limite=100, offset=500))

        assert len(r.sorteos) == 83  # 583 - 500

    def test_se_pueden_navegar_los_583_sin_huecos_ni_duplicados(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        vistos: set[int] = set()
        offset = 0
        while True:
            r = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", limite=100, offset=offset))
            if not r.sorteos:
                break
            vistos.update(s.numero_sorteo for s in r.sorteos)
            offset += 100

        assert vistos == set(range(1, 584))

    def test_tamanos_de_pagina_25_50_100_250_dan_el_numero_correcto_de_paginas(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        for tamano, filas_esperadas_ultima_pagina in [(25, 8), (50, 33), (100, 83), (250, 83)]:
            total_visto = 0
            offset = 0
            ultima_pagina_filas = 0
            while True:
                r = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", limite=tamano, offset=offset))
                if not r.sorteos:
                    break
                ultima_pagina_filas = len(r.sorteos)
                total_visto += len(r.sorteos)
                offset += tamano
            assert total_visto == 583, f"tamano={tamano}"
            assert ultima_pagina_filas == filas_esperadas_ultima_pagina, f"tamano={tamano}"


class TestOrdenamiento:
    def test_orden_por_defecto_numero_sorteo_descendente(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", limite=5, offset=0))
        assert [s.numero_sorteo for s in r.sorteos] == [583, 582, 581, 580, 579]

    def test_orden_numero_sorteo_ascendente(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(
            codigo_juego="MILOTO", orden_campo="numero_sorteo", orden_direccion="asc", limite=5, offset=0,
        ))
        assert [s.numero_sorteo for s in r.sorteos] == [1, 2, 3, 4, 5]

    def test_orden_por_fecha_ascendente_y_descendente(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        asc = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", orden_campo="fecha", orden_direccion="asc", limite=3, offset=0))
        desc = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", orden_campo="fecha", orden_direccion="desc", limite=3, offset=0))

        assert [s.numero_sorteo for s in asc.sorteos] == [1, 2, 3]
        assert [s.numero_sorteo for s in desc.sorteos] == [583, 582, 581]

    def test_orden_invalido_lanza_error_claro(self):
        from app.application.interfaces.sorteo_repository import FiltroSorteos

        with pytest.raises(ValueError):
            FiltroSorteos(orden_campo="campo_inexistente")


class TestFiltros:
    def test_filtro_numero_exacto(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", numero_desde=250, numero_hasta=250, limite=10, offset=0))

        assert r.total == 1
        assert r.sorteos[0].numero_sorteo == 250

    def test_filtro_rango_de_numeros(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", numero_desde=100, numero_hasta=150, limite=100, offset=0))

        assert r.total == 51
        assert all(100 <= s.numero_sorteo <= 150 for s in r.sorteos)

    def test_filtro_rango_de_fechas(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        base_fecha = _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(
            codigo_juego="MILOTO",
            desde=base_fecha + timedelta(days=10), hasta=base_fecha + timedelta(days=20),
            limite=100, offset=0,
        ))

        assert r.total == 11

    def test_filtro_sin_resultados_no_falla(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(codigo_juego="MILOTO", numero_desde=9000, numero_hasta=9999, limite=100, offset=0))

        assert r.total == 0
        assert r.sorteos == []

    def test_combinacion_filtro_orden_y_paginacion(self):
        juego = _juego_miloto()
        juego_repo = FakeJuegoRepository(juegos=[juego])
        sorteo_repo = FakeSorteoRepository()
        _sembrar_583_sorteos(sorteo_repo, juego)
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        r = caso_uso.ejecutar(ListarSorteosInput(
            codigo_juego="MILOTO", numero_desde=1, numero_hasta=50,
            orden_campo="numero_sorteo", orden_direccion="asc", limite=10, offset=10,
        ))

        assert [s.numero_sorteo for s in r.sorteos] == list(range(11, 21))
        assert r.total == 50

    def test_juego_inexistente_lanza_error_claro(self):
        juego_repo = FakeJuegoRepository(juegos=[])
        sorteo_repo = FakeSorteoRepository()
        caso_uso = ListarSorteos(juego_repo, sorteo_repo)

        with pytest.raises(JuegoNoEncontradoError):
            caso_uso.ejecutar(ListarSorteosInput(codigo_juego="INEXISTENTE"))
