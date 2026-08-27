"""
Tests de `resultados_historicos_repository_sqlalchemy.py` /
`resultados_historicos_repository.py`.

IMPORTANTE - transparencia sobre el alcance real de esta verificación
(misma limitación honesta que la Etapa R, ahora más severa):

Este sandbox NO tiene PostgreSQL disponible NI `sqlalchemy` instalado
(ni siquiera para importar -sin acceso a red para instalar el
paquete). Esto significa que `ResultadosHistoricosRepositorySQLAlchemy`
(la clase que sí importa `sqlalchemy`) no puede siquiera IMPORTARSE en
este entorno, y mucho menos ejecutarse contra una base de datos real.

Para poder verificar el código de PRODUCCIÓN real de todos modos (no
una copia/simulación), la lógica de mapeo ORM->DTO se extrajo a
`_mapeo_resultados_historicos.py`, sin ninguna dependencia de
SQLAlchemy -esas dos funciones (`a_resultado_numerico`,
`a_resultado_colorloto`) SÍ se prueban aquí de verdad, ejecutadas
contra objetos simulados con la misma forma que el ORM real (no
dobles del propio repositorio).

El CONTRATO del puerto completo (incluyendo el filtrado por
`hasta_numero_sorteo` "en SQL", que aquí se simula fielmente sobre una
lista en memoria dado que no hay motor SQL disponible) se verifica
contra un FAKE que implementa `ResultadosHistoricosRepository`, mismo
precedente que `test_estadistica_repository.py` (Etapa R) y
`_SorteoRepositoryTransaccional` (Fase 2). No se afirma en ningún
punto haber probado la clase SQLAlchemy real contra PostgreSQL.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.infrastructure.repositories._mapeo_resultados_historicos import (
    a_resultado_colorloto,
    a_resultado_numerico,
)


# =====================================================================
# 1. Mapeo puro ORM -> DTO -código real de producción, tests reales
# =====================================================================

@dataclass
class _NumeroFake:
    numero: int
    posicion: int


@dataclass
class _SuperbalotaFake:
    numero: int


@dataclass
class _ColorFake:
    codigo: str


@dataclass
class _ColorNumeroFake:
    numero: int
    posicion: int
    color: _ColorFake


@dataclass
class _SorteoFake:
    numero_sorteo: int
    fecha: date
    dia_semana: str
    numeros: list
    superbalota: object = None
    colores_numeros: list = field(default_factory=list)


class TestMapeoNumerico:
    def test_transformacion_correcta_todos_los_campos(self):
        sorteo = _SorteoFake(
            numero_sorteo=583, fecha=date(2024, 6, 15), dia_semana="sabado",
            numeros=[_NumeroFake(5, 1), _NumeroFake(17, 2), _NumeroFake(30, 3)],
            superbalota=_SuperbalotaFake(9),
        )
        r = a_resultado_numerico(sorteo)
        assert isinstance(r, ResultadoNumerico)
        assert r.numero_sorteo == 583
        assert r.fecha == date(2024, 6, 15)
        assert r.dia_semana == "sabado"
        assert r.numeros == (5, 17, 30)
        assert r.superbalota == 9

    def test_orden_por_posicion_no_por_orden_de_insercion(self):
        sorteo = _SorteoFake(
            numero_sorteo=1, fecha=date(2024, 1, 1), dia_semana="lunes",
            numeros=[_NumeroFake(numero=30, posicion=3), _NumeroFake(numero=5, posicion=1), _NumeroFake(numero=17, posicion=2)],
        )
        r = a_resultado_numerico(sorteo)
        assert r.numeros == (5, 17, 30)

    def test_superbalota_ausente_es_none(self):
        sorteo = _SorteoFake(numero_sorteo=1, fecha=date(2024, 1, 1), dia_semana="lunes", numeros=[_NumeroFake(1, 1)], superbalota=None)
        r = a_resultado_numerico(sorteo)
        assert r.superbalota is None

    def test_devuelve_tupla_no_lista(self):
        sorteo = _SorteoFake(numero_sorteo=1, fecha=date(2024, 1, 1), dia_semana="lunes", numeros=[_NumeroFake(1, 1)])
        r = a_resultado_numerico(sorteo)
        assert isinstance(r.numeros, tuple)


class TestMapeoColorLoto:
    def test_transformacion_correcta_pares_ordenados_por_posicion(self):
        sorteo = _SorteoFake(
            numero_sorteo=206, fecha=date(2024, 3, 1), dia_semana="viernes", numeros=[],
            colores_numeros=[
                _ColorNumeroFake(7, 6, _ColorFake("VERDE")),
                _ColorNumeroFake(1, 1, _ColorFake("ROJO")),
                _ColorNumeroFake(3, 2, _ColorFake("AZUL")),
            ],
        )
        r = a_resultado_colorloto(sorteo)
        assert isinstance(r, ResultadoColorLoto)
        assert r.numero_sorteo == 206
        assert r.fecha == date(2024, 3, 1)
        assert r.dia_semana == "viernes"
        assert r.pares == ((1, "ROJO"), (3, "AZUL"), (7, "VERDE"))

    def test_usa_el_codigo_del_color_no_el_nombre(self):
        sorteo = _SorteoFake(
            numero_sorteo=1, fecha=date(2024, 1, 1), dia_semana="lunes", numeros=[],
            colores_numeros=[_ColorNumeroFake(1, 1, _ColorFake("ROJO"))],
        )
        r = a_resultado_colorloto(sorteo)
        assert r.pares[0] == (1, "ROJO")

    def test_devuelve_tupla_de_tuplas(self):
        sorteo = _SorteoFake(
            numero_sorteo=1, fecha=date(2024, 1, 1), dia_semana="lunes", numeros=[],
            colores_numeros=[_ColorNumeroFake(1, 1, _ColorFake("ROJO"))],
        )
        r = a_resultado_colorloto(sorteo)
        assert isinstance(r.pares, tuple)
        assert isinstance(r.pares[0], tuple)


# =====================================================================
# 2. Contrato del puerto -verificado contra un FAKE en memoria que
#    simula fielmente el filtrado "en SQL" por hasta_numero_sorteo.
# =====================================================================

class _ResultadosHistoricosRepositoryEnMemoria(ResultadosHistoricosRepository):
    def __init__(self):
        self._numericos: dict[UUID, list[ResultadoNumerico]] = {}
        self._colorloto: dict[UUID, list[ResultadoColorLoto]] = {}

    def cargar_numericos(self, juego_id: UUID, resultados: list[ResultadoNumerico]) -> None:
        self._numericos[juego_id] = list(resultados)

    def cargar_colorloto(self, juego_id: UUID, resultados: list[ResultadoColorLoto]) -> None:
        self._colorloto[juego_id] = list(resultados)

    def listar_resultados_numericos(
        self, juego_id: UUID, hasta_numero_sorteo: int | None = None,
    ) -> list[ResultadoNumerico]:
        todos = self._numericos.get(juego_id, [])
        filtrados = todos if hasta_numero_sorteo is None else [
            r for r in todos if r.numero_sorteo <= hasta_numero_sorteo
        ]
        return sorted(filtrados, key=lambda r: r.numero_sorteo)

    def listar_resultados_colorloto(
        self, juego_id: UUID, hasta_numero_sorteo: int | None = None,
    ) -> list[ResultadoColorLoto]:
        todos = self._colorloto.get(juego_id, [])
        filtrados = todos if hasta_numero_sorteo is None else [
            r for r in todos if r.numero_sorteo <= hasta_numero_sorteo
        ]
        return sorted(filtrados, key=lambda r: r.numero_sorteo)


def _rn(numero_sorteo: int, numeros=(1, 2, 3), superbalota=None) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=numero_sorteo, fecha=date(2024, 1, 1), dia_semana="lunes",
        numeros=numeros, superbalota=superbalota,
    )


def _rcl(numero_sorteo: int, pares=((1, "ROJO"),)) -> ResultadoColorLoto:
    return ResultadoColorLoto(numero_sorteo=numero_sorteo, fecha=date(2024, 1, 1), dia_semana="lunes", pares=pares)


class TestListarResultadosNumericos:
    def test_juego_sin_sorteos(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        assert repo.listar_resultados_numericos(uuid4()) == []

    def test_un_solo_sorteo(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(1)])
        resultado = repo.listar_resultados_numericos(juego_id)
        assert len(resultado) == 1
        assert resultado[0].numero_sorteo == 1

    def test_corte_none_devuelve_todo(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(1), _rn(2), _rn(3)])
        assert len(repo.listar_resultados_numericos(juego_id, None)) == 3

    def test_corte_con_valor_filtra_correctamente(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(1), _rn(2), _rn(3), _rn(4)])
        resultado = repo.listar_resultados_numericos(juego_id, hasta_numero_sorteo=2)
        assert [r.numero_sorteo for r in resultado] == [1, 2]

    def test_anti_fuga_ningun_resultado_posterior_al_corte(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(1), _rn(2), _rn(3), _rn(4), _rn(5)])
        resultado = repo.listar_resultados_numericos(juego_id, hasta_numero_sorteo=3)
        assert all(r.numero_sorteo <= 3 for r in resultado)
        assert max(r.numero_sorteo for r in resultado) == 3

    def test_corte_exactamente_en_un_sorteo_existente(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(1), _rn(2), _rn(3)])
        resultado = repo.listar_resultados_numericos(juego_id, hasta_numero_sorteo=2)
        assert [r.numero_sorteo for r in resultado] == [1, 2]

    def test_corte_entre_dos_sorteos_hueco(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(100), _rn(105)])
        resultado = repo.listar_resultados_numericos(juego_id, hasta_numero_sorteo=102)
        assert [r.numero_sorteo for r in resultado] == [100]

    def test_corte_mayor_al_ultimo_sorteo_devuelve_todo(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(1), _rn(2)])
        resultado = repo.listar_resultados_numericos(juego_id, hasta_numero_sorteo=999)
        assert len(resultado) == 2

    def test_orden_ascendente_determinista_pese_a_carga_desordenada(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(3), _rn(1), _rn(2)])
        resultado = repo.listar_resultados_numericos(juego_id)
        assert [r.numero_sorteo for r in resultado] == [1, 2, 3]

    def test_juego_incorrecto_sin_resultados(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_numericos(juego_id, [_rn(1)])
        assert repo.listar_resultados_numericos(uuid4()) == []


class TestListarResultadosColorLoto:
    def test_juego_sin_sorteos(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        assert repo.listar_resultados_colorloto(uuid4()) == []

    def test_transformacion_y_orden(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_colorloto(juego_id, [_rcl(3), _rcl(1), _rcl(2)])
        resultado = repo.listar_resultados_colorloto(juego_id)
        assert [r.numero_sorteo for r in resultado] == [1, 2, 3]

    def test_corte_aplicado(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_colorloto(juego_id, [_rcl(1), _rcl(2), _rcl(3)])
        resultado = repo.listar_resultados_colorloto(juego_id, hasta_numero_sorteo=2)
        assert [r.numero_sorteo for r in resultado] == [1, 2]

    def test_pares_correctos(self):
        repo = _ResultadosHistoricosRepositoryEnMemoria()
        juego_id = uuid4()
        repo.cargar_colorloto(juego_id, [_rcl(1, pares=((5, "ROJO"), (7, "AZUL")))])
        resultado = repo.listar_resultados_colorloto(juego_id)
        assert resultado[0].pares == ((5, "ROJO"), (7, "AZUL"))
