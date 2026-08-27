import uuid
from datetime import date

import pytest

from app.application.exceptions import (
    JuegoNoEncontradoError,
    SorteoDuplicadoError,
    SorteoInvalidoError,
)
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.registrar_sorteo import RegistrarSorteo, RegistrarSorteoInput
from app.domain.entities.juego import Juego
from app.domain.value_objects.color import Color
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


@pytest.fixture
def contexto():
    miloto = _crear_miloto()
    juego_repo = FakeJuegoRepository(juegos=[miloto])
    sorteo_repo = FakeSorteoRepository()
    color_repo = FakeColorRepository()
    estadistica_repo = FakeEstadisticaRepository()
    factory = GameFactory(color_repository=color_repo)
    caso_uso = RegistrarSorteo(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=factory,
        estadistica_repository=estadistica_repo,
    )
    return caso_uso, miloto, sorteo_repo, estadistica_repo


class TestRegistrarSorteo:
    def test_registra_sorteo_valido(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="MILOTO",
            numero_sorteo=100,
            fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
            fuente="csv_historico",
        )
        sorteo = caso_uso.ejecutar(entrada)

        assert sorteo.id is not None
        assert sorteo.dia_semana == "jueves"  # 2026-07-30 es jueves
        assert sorteo_repo.contar_por_juego(miloto.id) == 1

    def test_rechaza_juego_inexistente(self, contexto):
        caso_uso, _, _, _ = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="INEXISTENTE",
            numero_sorteo=1,
            fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        )
        with pytest.raises(JuegoNoEncontradoError):
            caso_uso.ejecutar(entrada)

    def test_rechaza_combinacion_invalida_para_el_juego(self, contexto):
        caso_uso, _, _, _ = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="MILOTO",
            numero_sorteo=1,
            fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 99)),  # 99 fuera de rango
        )
        with pytest.raises(SorteoInvalidoError):
            caso_uso.ejecutar(entrada)

    def test_rechaza_sorteo_duplicado(self, contexto):
        caso_uso, _, _, _ = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="MILOTO",
            numero_sorteo=50,
            fecha=date(2026, 7, 20),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        )
        caso_uso.ejecutar(entrada)

        entrada_duplicada = RegistrarSorteoInput(
            codigo_juego="MILOTO",
            numero_sorteo=50,
            fecha=date(2026, 7, 27),
            resultado=Combination(numeros=(6, 7, 8, 9, 10)),
        )
        with pytest.raises(SorteoDuplicadoError):
            caso_uso.ejecutar(entrada_duplicada)


def test_game_factory_construye_colorloto_con_paleta_vigente():
    juego_id = uuid.uuid4()
    colorloto = Juego(
        id=juego_id, codigo="COLORLOTO", nombre="ColorLoto",
        rango_min=1, rango_max=7, cantidad_numeros=6,
        tiene_superbalota=False, superbalota_min=None, superbalota_max=None,
        tiene_color=True, permite_repeticion=True, activo=True,
    )
    paleta = [Color(codigo="ROJO", nombre="Rojo"), Color(codigo="AZUL", nombre="Azul")]
    color_repo = FakeColorRepository(colores_por_juego={juego_id: paleta})
    factory = GameFactory(color_repository=color_repo)

    lottery_game = factory.crear(colorloto)

    assert lottery_game.game_code == "COLORLOTO"
    assert {c.codigo for c in lottery_game.colors} == {"ROJO", "AZUL"}


def _precargar_estadistica(estadistica_repo, juego_id, hasta_numero_sorteo=None, tipo="frecuencia_numeros", parametros=None):
    from app.application.interfaces.estadistica_repository import EstadisticaCalculada
    return estadistica_repo.guardar(EstadisticaCalculada(
        id=None, juego_id=juego_id, tipo_estadistica=tipo, hasta_numero_sorteo=hasta_numero_sorteo,
        parametros=parametros or {}, parametros_hash="", resultado={}, calculado_en=None, valido_hasta=None,
    ))


class TestRegistrarSorteoInvalidaCacheEstadistico:
    def test_escritura_exitosa_invalida_historico_completo(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None)
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is None

    def test_invalida_corte_igual_a_n(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=100)
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 100, {}) is None

    def test_invalida_corte_mayor_que_n(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=200)
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 200, {}) is None

    def test_conserva_corte_menor_que_n(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=50)
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", 50, {}) is not None

    def test_invalida_todos_los_tipos_del_mismo_juego(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="frecuencia_numeros")
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="frecuencia_superbalota")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is None
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_superbalota", None, {}) is None

    def test_no_afecta_otro_juego(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None)
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(otro_juego_id, "frecuencia_numeros", None, {}) is not None

    def test_duplicado_no_invalida(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        entrada = RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        )
        caso_uso.ejecutar(entrada)  # primera vez: OK, invalida (no hay nada precargado, resultado 0)
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None)
        with pytest.raises(SorteoDuplicadoError):
            caso_uso.ejecutar(entrada)  # segunda vez: duplicado, NO debe invalidar lo recien precargado
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is not None

    def test_sorteo_invalido_no_invalida(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None)
        entrada = RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=101, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 999)),  # fuera de rango 1-39 -> invalido
        )
        with pytest.raises(SorteoInvalidoError):
            caso_uso.ejecutar(entrada)
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros", None, {}) is not None


class TestInvalidacionIncluyeAtrasosNumerosEtapaW:
    """La invalidación por juego (ya corregida en la etapa anterior)
    es genérica por tipo_estadistica -no requiere ningún cambio para
    cubrir la receta nueva. Este test lo demuestra explícitamente
    para atrasos_numeros, la cuarta visualización."""

    def test_registrar_sorteo_invalida_atrasos_numeros_igual_que_las_demas(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="atrasos_numeros")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "atrasos_numeros", None, {}) is None

    def test_invalidacion_de_atrasos_numeros_no_afecta_otro_juego(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None, tipo="atrasos_numeros")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(otro_juego_id, "atrasos_numeros", None, {}) is not None


class TestInvalidacionIncluyeDistribucionParesImparesEtapaY:
    """Mismo mecanismo genérico de invalidación por juego (ya
    corregido en etapas anteriores) -no requiere ningún cambio para
    cubrir la receta nueva."""

    def test_registrar_sorteo_invalida_distribucion_pares_impares(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="distribucion_pares_impares")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "distribucion_pares_impares", None, {}) is None

    def test_invalidacion_de_distribucion_pares_impares_no_afecta_otro_juego(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None, tipo="distribucion_pares_impares")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(otro_juego_id, "distribucion_pares_impares", None, {}) is not None


class TestInvalidacionIncluyeDistribucionAltosBajosEtapaZ:
    def test_registrar_sorteo_invalida_distribucion_altos_bajos(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="distribucion_altos_bajos")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "distribucion_altos_bajos", None, {}) is None

    def test_invalidacion_de_altos_bajos_no_afecta_otro_juego(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None, tipo="distribucion_altos_bajos")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(otro_juego_id, "distribucion_altos_bajos", None, {}) is not None


class TestInvalidacionIncluyeDistribucionParesConsecutivosEtapaAA:
    def test_registrar_sorteo_invalida_distribucion_pares_consecutivos(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="distribucion_pares_consecutivos")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "distribucion_pares_consecutivos", None, {}) is None

    def test_invalidacion_de_pares_consecutivos_no_afecta_otro_juego(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None, tipo="distribucion_pares_consecutivos")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(otro_juego_id, "distribucion_pares_consecutivos", None, {}) is not None


class TestInvalidacionIncluyeDistribucionRachaMaximaEtapaAB:
    """Mismo mecanismo genérico de invalidación por juego (ya
    corregido en etapas anteriores) -no requiere ningún cambio para
    cubrir la receta nueva. La invalidación al editar/eliminar ya
    está cubierta genéricamente (agnóstica de tipo_estadistica) en
    `test_editar_eliminar_sorteo_invalidacion.py`, sin necesitar
    duplicación por cada receta nueva."""

    def test_registrar_sorteo_invalida_distribucion_racha_maxima(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="distribucion_racha_maxima")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "distribucion_racha_maxima", None, {}) is None

    def test_invalidacion_de_racha_maxima_no_afecta_otro_juego(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None, tipo="distribucion_racha_maxima")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(otro_juego_id, "distribucion_racha_maxima", None, {}) is not None


class TestInvalidacionIncluyeDistribucionRepeticionesEntreSorteosEtapaAC:
    """Mismo mecanismo genérico de invalidación por juego -no requiere
    ningún cambio para cubrir la receta nueva. Editar/eliminar ya
    cubiertos genéricamente (agnóstico de tipo_estadistica) en
    test_editar_eliminar_sorteo_invalidacion.py."""

    def test_registrar_sorteo_invalida_distribucion_repeticiones_entre_sorteos(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="distribucion_repeticiones_entre_sorteos")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "distribucion_repeticiones_entre_sorteos", None, {}) is None

    def test_invalidacion_no_afecta_otro_juego(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        otro_juego_id = uuid.uuid4()
        _precargar_estadistica(estadistica_repo, otro_juego_id, hasta_numero_sorteo=None, tipo="distribucion_repeticiones_entre_sorteos")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(otro_juego_id, "distribucion_repeticiones_entre_sorteos", None, {}) is not None


class TestInvalidacionIncluyeFrecuenciaNumerosColorLotoEtapaAE1:
    """Mismo mecanismo genérico de invalidación por juego -no requiere
    ningún cambio para cubrir la nueva receta de ColorLoto. No se
    construye un flujo completo de registro de ColorLoto (que
    requeriría fixtures específicos de `ColorNumberPair`) porque
    `invalidar_por_juego` ya está confirmado agnóstico de
    `tipo_estadistica` -esto demuestra la reutilización exacta con el
    mismo patrón ya usado 4 veces, sin duplicar cobertura."""

    def test_registrar_sorteo_invalida_frecuencia_numeros_colorloto(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="frecuencia_numeros_colorloto")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_numeros_colorloto", None, {}) is None


class TestInvalidacionIncluyeFrecuenciaColoresColorLotoEtapaAE2:
    """Mismo mecanismo genérico de invalidación por juego ya
    confirmado agnóstico de tipo_estadistica en Etapa AE-1 -no
    requiere ningún cambio para cubrir la nueva receta. No se
    duplica un flujo completo de registro de ColorLoto (ya
    justificado igual en AE-1)."""

    def test_registrar_sorteo_invalida_frecuencia_colores_colorloto(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="frecuencia_colores_colorloto")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_colores_colorloto", None, {}) is None


class TestInvalidacionIncluyeFrecuenciaParesColorLotoEtapaAE3:
    """Mismo mecanismo genérico de invalidación por juego ya
    confirmado agnóstico de tipo_estadistica en Etapa AE-1 -no
    requiere ningún cambio para cubrir la nueva receta."""

    def test_registrar_sorteo_invalida_frecuencia_pares_colorloto(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="frecuencia_pares_colorloto")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "frecuencia_pares_colorloto", None, {}) is None


class TestInvalidacionIncluyeAtrasosNumerosColorLotoEtapaAE4:
    """Mismo mecanismo genérico de invalidación por juego ya
    confirmado agnóstico de tipo_estadistica en Etapa AE-1 -no
    requiere ningún cambio para cubrir la nueva receta. Reutiliza la
    cobertura genérica existente de editar/eliminar sin duplicarla."""

    def test_registrar_sorteo_invalida_atrasos_numeros_colorloto(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="atrasos_numeros_colorloto")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "atrasos_numeros_colorloto", None, {}) is None


class TestInvalidacionIncluyeAtrasosColoresColorLotoEtapaAE5:
    """Mismo mecanismo genérico de invalidación por juego ya
    confirmado agnóstico de tipo_estadistica en Etapa AE-1 -no
    requiere ningún cambio para cubrir la nueva receta."""

    def test_registrar_sorteo_invalida_atrasos_colores_colorloto(self, contexto):
        caso_uso, miloto, sorteo_repo, estadistica_repo = contexto
        _precargar_estadistica(estadistica_repo, miloto.id, hasta_numero_sorteo=None, tipo="atrasos_colores_colorloto")
        caso_uso.ejecutar(RegistrarSorteoInput(
            codigo_juego="MILOTO", numero_sorteo=100, fecha=date(2026, 7, 30),
            resultado=Combination(numeros=(1, 2, 3, 4, 5)),
        ))
        assert estadistica_repo.buscar_vigente(miloto.id, "atrasos_colores_colorloto", None, {}) is None
