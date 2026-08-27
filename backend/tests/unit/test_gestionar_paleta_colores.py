"""
Tests de GestionarPaletaColores -Etapa AE-4P.

No existía ningún test de este caso de uso antes de esta etapa
(confirmado por auditoría exhaustiva previa) -este archivo cubre
tanto el comportamiento ya existente (agregar/retirar color) como la
invalidación de caché de estadísticas que se agrega en esta etapa.

Reutiliza FakeColorRepository y FakeEstadisticaRepository de
tests/unit/fakes.py sin duplicar su lógica.
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.application.use_cases.gestionar_paleta_colores import (
    AgregarColorInput,
    GestionarPaletaColores,
    RetirarColorInput,
)
from app.domain.value_objects.color import Color
from tests.unit.fakes import FakeColorRepository, FakeEstadisticaRepository


class _ColorRepositoryQueFalla:
    """Fake mínimo dedicado a simular un fallo del repositorio de
    colores ANTES de completar la operación -para probar que una
    mutación fallida nunca invalida caché."""

    def guardar(self, juego_id, color):
        raise RuntimeError("fallo simulado del repositorio de colores")

    def cerrar_vigencia(self, juego_id, codigo, hasta):
        raise RuntimeError("fallo simulado del repositorio de colores")

    def listar_vigentes(self, juego_id, en_fecha=None):
        return []

    def listar_todos(self, juego_id):
        return []


def _espiar_invalidaciones(estadistica_repo: FakeEstadisticaRepository) -> list[tuple]:
    """Envuelve invalidar_por_juego para registrar cada llamada
    (juego_id, desde_numero_sorteo) sin alterar su comportamiento
    real -mismo patrón de espía ya usado extensamente en el proyecto
    para motores y recetas."""
    llamadas: list[tuple] = []
    original = estadistica_repo.invalidar_por_juego

    def espia(juego_id, desde_numero_sorteo=None):
        llamadas.append((juego_id, desde_numero_sorteo))
        return original(juego_id, desde_numero_sorteo=desde_numero_sorteo)

    estadistica_repo.invalidar_por_juego = espia
    return llamadas


class TestConstructorYComposicion:
    def test_constructor_acepta_ambos_repositorios(self):
        color_repo = FakeColorRepository()
        estadistica_repo = FakeEstadisticaRepository()
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)
        assert gestionar is not None


class TestAgregarColorInvalidaCache:
    def test_operacion_exitosa_invalida_una_vez_con_el_juego_id_correcto(self):
        juego_id = uuid4()
        color_repo = FakeColorRepository()
        estadistica_repo = FakeEstadisticaRepository()
        llamadas = _espiar_invalidaciones(estadistica_repo)
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)

        gestionar.agregar_color(AgregarColorInput(juego_id=juego_id, codigo="MORADO", nombre="Morado", vigente_desde=date(2024, 1, 1)))

        assert len(llamadas) == 1
        assert llamadas[0][0] == juego_id

    def test_invalidacion_cubre_historico_completo_y_cortes_concretos(self):
        from tests.unit.fakes import EstadisticaCalculada

        juego_id = uuid4()
        color_repo = FakeColorRepository()
        estadistica_repo = FakeEstadisticaRepository()

        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_colores_colorloto",
            hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6},
            parametros_hash="", resultado={"filas": []}, calculado_en=None, valido_hasta=None,
        ))
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="frecuencia_colores_colorloto",
            hasta_numero_sorteo=100, parametros={"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6},
            parametros_hash="", resultado={"filas": []}, calculado_en=None, valido_hasta=None,
        ))

        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)
        gestionar.agregar_color(AgregarColorInput(juego_id=juego_id, codigo="MORADO", nombre="Morado", vigente_desde=date(2024, 1, 1)))

        assert estadistica_repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}) is None
        assert estadistica_repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", 100, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}) is None

    def test_ninguna_estadistica_de_otro_juego_es_invalidada(self):
        from tests.unit.fakes import EstadisticaCalculada

        juego_a, juego_b = uuid4(), uuid4()
        color_repo = FakeColorRepository()
        estadistica_repo = FakeEstadisticaRepository()
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_b, tipo_estadistica="frecuencia_colores_colorloto",
            hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6},
            parametros_hash="", resultado={"v": "juego_b"}, calculado_en=None, valido_hasta=None,
        ))

        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)
        gestionar.agregar_color(AgregarColorInput(juego_id=juego_a, codigo="MORADO", nombre="Morado", vigente_desde=date(2024, 1, 1)))

        vigente_b = estadistica_repo.buscar_vigente(juego_b, "frecuencia_colores_colorloto", None, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6})
        assert vigente_b is not None
        assert vigente_b.resultado == {"v": "juego_b"}

    def test_fallo_del_repositorio_antes_de_guardar_no_invalida(self):
        juego_id = uuid4()
        color_repo = _ColorRepositoryQueFalla()
        estadistica_repo = FakeEstadisticaRepository()
        llamadas = _espiar_invalidaciones(estadistica_repo)
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)

        with pytest.raises(RuntimeError):
            gestionar.agregar_color(AgregarColorInput(juego_id=juego_id, codigo="MORADO", nombre="Morado", vigente_desde=date(2024, 1, 1)))

        assert llamadas == []


class TestRetirarColorInvalidaCache:
    def test_operacion_exitosa_invalida_una_vez_con_el_juego_id_correcto(self):
        juego_id = uuid4()
        color_repo = FakeColorRepository({juego_id: [Color(codigo="ROJO", nombre="Rojo", activo=True)]})
        estadistica_repo = FakeEstadisticaRepository()
        llamadas = _espiar_invalidaciones(estadistica_repo)
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)

        gestionar.retirar_color(RetirarColorInput(juego_id=juego_id, codigo="ROJO", vigente_hasta=date(2024, 6, 1)))

        assert len(llamadas) == 1
        assert llamadas[0][0] == juego_id

    def test_operacion_fallida_por_codigo_inexistente_no_invalida(self):
        juego_id = uuid4()
        color_repo = FakeColorRepository({juego_id: [Color(codigo="ROJO", nombre="Rojo", activo=True)]})
        estadistica_repo = FakeEstadisticaRepository()
        llamadas = _espiar_invalidaciones(estadistica_repo)
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)

        with pytest.raises(ValueError):
            gestionar.retirar_color(RetirarColorInput(juego_id=juego_id, codigo="INEXISTENTE", vigente_hasta=date(2024, 6, 1)))

        assert llamadas == []

    def test_fallo_del_repositorio_no_invalida(self):
        juego_id = uuid4()
        color_repo = _ColorRepositoryQueFalla()
        estadistica_repo = FakeEstadisticaRepository()
        llamadas = _espiar_invalidaciones(estadistica_repo)
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)

        with pytest.raises(RuntimeError):
            gestionar.retirar_color(RetirarColorInput(juego_id=juego_id, codigo="ROJO", vigente_hasta=date(2024, 6, 1)))

        assert llamadas == []


class TestListarPaletaVigenteNoInvalida:
    def test_operacion_de_lectura_nunca_invalida(self):
        juego_id = uuid4()
        color_repo = FakeColorRepository({juego_id: [Color(codigo="ROJO", nombre="Rojo", activo=True)]})
        estadistica_repo = FakeEstadisticaRepository()
        llamadas = _espiar_invalidaciones(estadistica_repo)
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)

        gestionar.listar_paleta_vigente(juego_id)

        assert llamadas == []


class TestIntegracionAE2AE3NoReutilizanCacheTrasMutacionDePaleta:
    """Confirma end-to-end (con CalcularYPersistirEstadistica real, no
    solo GestionarPaletaColores aislado) que una mutación de paleta
    invalida efectivamente la caché que AE-2/AE-3 consultarían."""

    def test_frecuencia_colores_no_reutiliza_cache_tras_agregar_color(self):
        from datetime import date as _date
        from app.application.use_cases.calcular_y_persistir_estadistica import CalcularYPersistirEstadistica
        from tests.unit.test_calcular_y_persistir_estadistica import (
            _cl, _col, _PALETA_COLORLOTO, _PARES_VALIDOS, _PARAMS_COLORLOTO,
            _HistoricoRepositoryEnMemoriaConEspia, _ColorRepositoryEnMemoriaConEspia,
        )

        juego_id = uuid4()
        paleta_inicial = list(_PALETA_COLORLOTO)
        historico_repo = _HistoricoRepositoryEnMemoriaConEspia({}, datos_colorloto={juego_id: [_cl(1, _PARES_VALIDOS, _date(2024, 1, 1))]})
        color_repo_calculo = _ColorRepositoryEnMemoriaConEspia({juego_id: paleta_inicial})
        estadistica_repo = FakeEstadisticaRepository()
        orquestador = CalcularYPersistirEstadistica(historico_repo, estadistica_repo, color_repository=color_repo_calculo)

        primer_resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        primeras_categorias = {f["valor"] for f in primer_resultado.resultado["filas"]}
        assert "MORADO" not in primeras_categorias

        # Mutación de paleta: agrega MORADO (vigente hoy) al MISMO
        # almacén subyacente que usa color_repo_calculo, e invalida la
        # caché de estadísticas del juego a través de
        # GestionarPaletaColores -exactamente el flujo real.
        color_repo_gestion = FakeColorRepository({juego_id: paleta_inicial})
        gestionar = GestionarPaletaColores(color_repository=color_repo_gestion, estadistica_repository=estadistica_repo)
        gestionar.agregar_color(AgregarColorInput(juego_id=juego_id, codigo="MORADO", nombre="Morado", vigente_desde=_date(2020, 1, 1)))

        # El repositorio de colores usado por el ORQUESTADOR debe
        # reflejar la paleta actualizada -mismo almacén subyacente,
        # actualizado directamente para simular la consistencia real
        # de una única tabla `colores` en producción.
        color_repo_calculo._colores[juego_id] = list(color_repo_gestion._colores[juego_id])

        segundo_resultado = orquestador.ejecutar(juego_id, "frecuencia_colores_colorloto", parametros_metrica=dict(_PARAMS_COLORLOTO))
        segundas_categorias = {f["valor"] for f in segundo_resultado.resultado["filas"]}
        assert "MORADO" in segundas_categorias


class TestInvalidacionCubreAtrasosColoresColorLotoEtapaAE5:
    """Complementa (sin duplicar) el test end-to-end ya existente
    para frecuencia_colores_colorloto -mismo mecanismo genérico
    invalidar_por_juego, agnóstico de tipo_estadistica, confirmado
    directamente sobre la nueva receta de AE-5."""

    def test_agregar_color_invalida_cache_de_atrasos_colores(self):
        from tests.unit.fakes import EstadisticaCalculada

        juego_id = uuid4()
        params_con_marcador = {
            "rango_min": 1, "rango_max": 7, "cantidad_numeros": 6,
            "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1",
        }
        color_repo = FakeColorRepository()
        estadistica_repo = FakeEstadisticaRepository()
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="atrasos_colores_colorloto",
            hasta_numero_sorteo=None, parametros=params_con_marcador, parametros_hash="",
            resultado={"filas": []}, calculado_en=None, valido_hasta=None,
        ))
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)
        gestionar.agregar_color(AgregarColorInput(juego_id=juego_id, codigo="MORADO", nombre="Morado", vigente_desde=date(2024, 1, 1)))

        assert estadistica_repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", None, params_con_marcador) is None

    def test_retirar_color_invalida_cache_de_atrasos_colores(self):
        from tests.unit.fakes import EstadisticaCalculada

        juego_id = uuid4()
        params_con_marcador = {
            "rango_min": 1, "rango_max": 7, "cantidad_numeros": 6,
            "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1",
        }
        color_repo = FakeColorRepository({juego_id: [Color(codigo="ROJO", nombre="Rojo", activo=True)]})
        estadistica_repo = FakeEstadisticaRepository()
        estadistica_repo.guardar(EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica="atrasos_colores_colorloto",
            hasta_numero_sorteo=100, parametros=params_con_marcador, parametros_hash="",
            resultado={"filas": []}, calculado_en=None, valido_hasta=None,
        ))
        gestionar = GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)
        gestionar.retirar_color(RetirarColorInput(juego_id=juego_id, codigo="ROJO", vigente_hasta=date(2024, 6, 1)))

        assert estadistica_repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", 100, params_con_marcador) is None
