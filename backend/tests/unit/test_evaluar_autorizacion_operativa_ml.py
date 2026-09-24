"""Tests de `EvaluarAutorizacionOperativaML` -Etapa AE-41."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.exceptions import JuegoNoEncontradoError
from app.application.ml.tipos import EstadoAutorizacionOperativaML, ResumenDisponibilidadHoldout
from app.application.use_cases.evaluar_autorizacion_operativa_ml import (
    EvaluarAutorizacionOperativaML,
    JuegoNoAutorizadoParaAutorizacionOperativaError,
)
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML
from app.domain.entities.juego import Juego
from tests.unit.fakes import FakeJuegoRepository


def _juego(codigo: str) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43, cantidad_numeros=5,
        tiene_superbalota=True, superbalota_min=1, superbalota_max=16, tiene_color=False,
        permite_repeticion=False, activo=True,
    )


class _FakeDisponibilidadRepo:
    def __init__(self, total=0, minimo=None, maximo=None, juego_codigo_devuelto=None):
        self._total = total
        self._minimo = minimo
        self._maximo = maximo
        self._juego_codigo_devuelto = juego_codigo_devuelto
        self.llamadas = []

    def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
        self.llamadas.append((juego_id, codigo_juego, desde_numero_sorteo))
        codigo_final = self._juego_codigo_devuelto or codigo_juego
        return ResumenDisponibilidadHoldout(
            juego_codigo=codigo_final, desde_numero_sorteo=desde_numero_sorteo,
            total_registros=self._total, total_numeros_distintos=self._total,
            numero_sorteo_minimo=self._minimo, numero_sorteo_maximo=self._maximo,
        )


def _caso_autorizacion(juego_repo, disponibilidad_repo) -> EvaluarAutorizacionOperativaML:
    caso_elegibilidad = EvaluarElegibilidadReaperturaML(juego_repo, disponibilidad_repo)
    return EvaluarAutorizacionOperativaML(caso_elegibilidad)


class TestBloqueoPorAusenciaDeDatos:
    def test_baloto_cero_sorteos(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=0))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES

    def test_baloto_revancha_cero_sorteos(self):
        revancha = _juego("BALOTO_REVANCHA")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[revancha]), _FakeDisponibilidadRepo(total=0))
        r = caso.ejecutar("BALOTO_REVANCHA")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES

    def test_50_sorteos_bloqueado(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=50, minimo=2706, maximo=2755))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES


class TestNumeracionInvalida:
    def test_inicio_distinto_de_2706(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=50, minimo=2710, maximo=2759))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA
        assert r.reporte_elegibilidad is None

    def test_hueco_en_numeracion(self):
        baloto = _juego("BALOTO")
        # rango 2706..2805 implica 100, pero total=99 -> hueco
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=99, minimo=2706, maximo=2805))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA

    def test_conteo_inconsistente_con_rango(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=200, minimo=2706, maximo=2805))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA

    def test_resumen_internamente_inconsistente_minimo_mayor_que_maximo(self):
        baloto = _juego("BALOTO")

        class RepoInconsistente:
            def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
                return ResumenDisponibilidadHoldout(
                    juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
                    total_registros=5, total_numeros_distintos=5,
                    numero_sorteo_minimo=2800, numero_sorteo_maximo=2706,
                )

        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), RepoInconsistente())
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA

    def test_nunca_propaga_la_excepcion_como_crash(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=99, minimo=2706, maximo=2805))
        # no debe lanzar DisponibilidadHoldoutInvalidaError -debe devolver un reporte
        r = caso.ejecutar("BALOTO")
        assert r is not None
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA


class TestCorrespondenciaDeJuego:
    def test_solicitar_baloto_recibir_resumen_de_revancha(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=150, minimo=2706, maximo=2855, juego_codigo_devuelto="BALOTO_REVANCHA"))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA

    def test_solicitar_revancha_recibir_resumen_de_baloto(self):
        revancha = _juego("BALOTO_REVANCHA")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[revancha]), _FakeDisponibilidadRepo(total=150, minimo=2706, maximo=2855, juego_codigo_devuelto="BALOTO"))
        r = caso.ejecutar("BALOTO_REVANCHA")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA

    def test_codigo_desconocido_propaga_juego_no_encontrado(self):
        class RepoVacio:
            def obtener_por_codigo(self, codigo):
                return None
        caso = _caso_autorizacion(RepoVacio(), _FakeDisponibilidadRepo())
        with pytest.raises(JuegoNoEncontradoError):
            caso.ejecutar("BALOTO")

    def test_miloto_rechazado_antes_de_consultar_repositorios(self):
        class RepoQueFalla:
            def obtener_por_codigo(self, codigo):
                raise AssertionError("no deberia consultarse el repositorio de juegos")
        caso = _caso_autorizacion(RepoQueFalla(), _FakeDisponibilidadRepo())
        with pytest.raises(JuegoNoAutorizadoParaAutorizacionOperativaError):
            caso.ejecutar("MILOTO")

    def test_colorloto_rechazado_antes_de_consultar_repositorios(self):
        class RepoQueFalla:
            def obtener_por_codigo(self, codigo):
                raise AssertionError("no deberia consultarse el repositorio de juegos")
        caso = _caso_autorizacion(RepoQueFalla(), _FakeDisponibilidadRepo())
        with pytest.raises(JuegoNoAutorizadoParaAutorizacionOperativaError):
            caso.ejecutar("COLORLOTO")


class TestLimiteExacto:
    def test_99_sorteos_bloqueado(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=99, minimo=2706, maximo=2804))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES

    def test_100_sorteos_contiguos_autorizado(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=100, minimo=2706, maximo=2805))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO

    def test_mas_de_100_sorteos_tambien_autorizado_mismo_estado(self):
        baloto = _juego("BALOTO")
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), _FakeDisponibilidadRepo(total=300, minimo=2706, maximo=3005))
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO
        assert r.resultados_observados is False


class TestGarantiasNegativas:
    """Fakes que fallan si AE-41 intentara, en cualquier punto, leer
    numeros ganadores, construir datasets, entrenar, predecir o
    persistir."""

    def test_repositorio_de_disponibilidad_nunca_expone_numeros_ganadores(self):
        baloto = _juego("BALOTO")

        class RepoConGuardia:
            def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
                # simula un puerto correcto: solo metadatos, nunca resultados
                return ResumenDisponibilidadHoldout(
                    juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
                    total_registros=0, total_numeros_distintos=0,
                    numero_sorteo_minimo=None, numero_sorteo_maximo=None,
                )
            def listar_resultados_numericos(self, *a, **k):
                raise AssertionError("AE-41 nunca debe leer numeros ganadores")

        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), RepoConGuardia())
        r = caso.ejecutar("BALOTO")
        assert r.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES

    def test_caso_de_uso_no_tiene_metodos_de_entrenamiento_ni_prediccion(self):
        import inspect
        metodos = [n for n, _ in inspect.getmembers(EvaluarAutorizacionOperativaML, predicate=inspect.isfunction)]
        for prohibido in ("entrenar", "predecir", "construir_dataset", "extraer_features", "guardar", "persistir"):
            assert prohibido not in metodos

    def test_firma_del_constructor_unica_dependencia_es_el_caso_de_uso_de_ae40(self):
        import inspect
        firma = inspect.signature(EvaluarAutorizacionOperativaML.__init__)
        nombres_parametros = set(firma.parameters.keys()) - {"self"}
        assert nombres_parametros == {"caso_uso_elegibilidad"}

    def test_no_importa_construir_dataset_binario_ni_features(self):
        import ast as ast_modulo
        import pathlib
        for ruta in (
            pathlib.Path("app/application/ml/autorizacion_operativa.py"),
            pathlib.Path("app/application/use_cases/evaluar_autorizacion_operativa_ml.py"),
        ):
            arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
            nombres_importados = set()
            for nodo in ast_modulo.walk(arbol):
                if isinstance(nodo, ast_modulo.ImportFrom):
                    for alias in nodo.names:
                        nombres_importados.add(alias.name)
            for prohibido in ("construir_dataset_binario", "FilaCandidato", "entrenar_modelo_familia", "predecir_probabilidades_generalizado"):
                assert prohibido not in nombres_importados

    def test_no_importa_resultados_historicos_repository(self):
        import ast as ast_modulo
        import pathlib
        for ruta in (
            pathlib.Path("app/application/ml/autorizacion_operativa.py"),
            pathlib.Path("app/application/use_cases/evaluar_autorizacion_operativa_ml.py"),
        ):
            arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
            nombres_importados = set()
            for nodo in ast_modulo.walk(arbol):
                if isinstance(nodo, ast_modulo.ImportFrom):
                    for alias in nodo.names:
                        nombres_importados.add(alias.name)
            assert "ResultadosHistoricosRepository" not in nombres_importados


class TestContratoDelCasoDeUso:
    def test_delega_completamente_al_caso_de_uso_de_ae40_una_sola_llamada(self):
        baloto = _juego("BALOTO")
        disp = _FakeDisponibilidadRepo(total=0)
        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto]), disp)
        caso.ejecutar("BALOTO")
        assert len(disp.llamadas) == 1

    def test_decisiones_independientes_por_juego(self):
        baloto = _juego("BALOTO")
        revancha = _juego("BALOTO_REVANCHA")

        class RepoDosJuegos:
            def __init__(self):
                self.mapa = {baloto.id: 0, revancha.id: 100}
            def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
                total = self.mapa[juego_id]
                minimo = desde_numero_sorteo if total > 0 else None
                maximo = desde_numero_sorteo + total - 1 if total > 0 else None
                return ResumenDisponibilidadHoldout(
                    juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
                    total_registros=total, total_numeros_distintos=total,
                    numero_sorteo_minimo=minimo, numero_sorteo_maximo=maximo,
                )

        caso = _caso_autorizacion(FakeJuegoRepository(juegos=[baloto, revancha]), RepoDosJuegos())
        r_baloto = caso.ejecutar("BALOTO")
        r_revancha = caso.ejecutar("BALOTO_REVANCHA")
        assert r_baloto.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES
        assert r_revancha.estado == EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO

    def test_no_persiste_nada_no_modifica_tablas(self):
        import inspect
        from app.application.use_cases import evaluar_autorizacion_operativa_ml as modulo
        codigo_fuente = inspect.getsource(modulo)
        for palabra_prohibida in ("INSERT", "UPDATE", "DELETE", "commit(", "flush(", ".save(", ".guardar("):
            assert palabra_prohibida not in codigo_fuente
