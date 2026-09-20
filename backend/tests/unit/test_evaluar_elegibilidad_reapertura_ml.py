"""Tests de `EvaluarElegibilidadReaperturaML` -Etapa AE-40."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.exceptions import JuegoNoEncontradoError
from app.application.ml.reapertura import DisponibilidadHoldoutInvalidaError
from app.application.ml.tipos import EstadoElegibilidadReaperturaML, ResumenDisponibilidadHoldout
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import (
    EvaluarElegibilidadReaperturaML,
    JuegoNoAutorizadoParaReaperturaError,
)
from app.domain.entities.juego import Juego
from tests.unit.fakes import FakeJuegoRepository


def _juego(codigo: str) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43, cantidad_numeros=5,
        tiene_superbalota=True, superbalota_min=1, superbalota_max=16, tiene_color=False,
        permite_repeticion=False, activo=True,
    )


class _FakeDisponibilidadRepo:
    def __init__(self, total: int = 45, minimo: int | None = 2706, maximo: int | None = 2750):
        self.llamadas: list[tuple] = []
        self._total = total
        self._minimo = minimo
        self._maximo = maximo

    def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
        self.llamadas.append((juego_id, codigo_juego, desde_numero_sorteo))
        return ResumenDisponibilidadHoldout(
            juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
            total_registros=self._total, total_numeros_distintos=self._total,
            numero_sorteo_minimo=self._minimo, numero_sorteo_maximo=self._maximo,
        )


class _FakeDisponibilidadRepoConMezcla:
    """Simula un defecto de infraestructura: devuelve el resumen de
    un juego DISTINTO del solicitado, sin importar que codigo se le
    pase."""

    def __init__(self, juego_codigo_devuelto: str):
        self._juego_codigo_devuelto = juego_codigo_devuelto
        self.llamadas: list[tuple] = []

    def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
        self.llamadas.append((juego_id, codigo_juego, desde_numero_sorteo))
        return ResumenDisponibilidadHoldout(
            juego_codigo=self._juego_codigo_devuelto, desde_numero_sorteo=desde_numero_sorteo,
            total_registros=150, total_numeros_distintos=150,
            numero_sorteo_minimo=2706, numero_sorteo_maximo=2855,
        )


class _RepoQueFalla:
    def obtener_por_codigo(self, codigo):
        raise AssertionError("no deberia consultarse el repositorio de juegos para un codigo no autorizado")


class _DispQueFalla:
    def obtener_resumen_disponibilidad(self, *args, **kwargs):
        raise AssertionError("no deberia consultarse el repositorio de disponibilidad")


class TestAutorizacionDeJuegos:
    def test_baloto_autorizado(self):
        baloto = _juego("BALOTO")
        disp = _FakeDisponibilidadRepo()
        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[baloto]), disp)
        reporte = caso_uso.ejecutar("BALOTO")
        assert reporte.juego_codigo == "BALOTO"

    def test_baloto_revancha_autorizado(self):
        revancha = _juego("BALOTO_REVANCHA")
        disp = _FakeDisponibilidadRepo()
        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[revancha]), disp)
        reporte = caso_uso.ejecutar("BALOTO_REVANCHA")
        assert reporte.juego_codigo == "BALOTO_REVANCHA"

    def test_miloto_rechazado_antes_de_tocar_repositorios(self):
        caso_uso = EvaluarElegibilidadReaperturaML(_RepoQueFalla(), _DispQueFalla())
        with pytest.raises(JuegoNoAutorizadoParaReaperturaError):
            caso_uso.ejecutar("MILOTO")

    def test_colorloto_rechazado_antes_de_tocar_repositorios(self):
        caso_uso = EvaluarElegibilidadReaperturaML(_RepoQueFalla(), _DispQueFalla())
        with pytest.raises(JuegoNoAutorizadoParaReaperturaError):
            caso_uso.ejecutar("COLORLOTO")

    def test_codigo_inexistente(self):
        class RepoVacio:
            def obtener_por_codigo(self, codigo):
                return None
        caso_uso = EvaluarElegibilidadReaperturaML(RepoVacio(), _DispQueFalla())
        with pytest.raises(JuegoNoEncontradoError):
            caso_uso.ejecutar("BALOTO")


class TestMezclaDeJuegosRechazada:
    """Corrige el Defecto 1: el caso de uso debe rechazar explicitamente
    un resumen cuyo `juego_codigo` no coincide con el juego solicitado,
    en ambos sentidos."""

    def test_solicitar_baloto_recibir_resumen_de_revancha(self):
        baloto = _juego("BALOTO")
        disp = _FakeDisponibilidadRepoConMezcla("BALOTO_REVANCHA")
        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[baloto]), disp)
        with pytest.raises(DisponibilidadHoldoutInvalidaError) as exc_info:
            caso_uso.ejecutar("BALOTO")
        mensaje = str(exc_info.value)
        assert "BALOTO" in mensaje
        assert "BALOTO_REVANCHA" in mensaje

    def test_solicitar_revancha_recibir_resumen_de_baloto(self):
        revancha = _juego("BALOTO_REVANCHA")
        disp = _FakeDisponibilidadRepoConMezcla("BALOTO")
        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[revancha]), disp)
        with pytest.raises(DisponibilidadHoldoutInvalidaError) as exc_info:
            caso_uso.ejecutar("BALOTO_REVANCHA")
        mensaje = str(exc_info.value)
        assert "BALOTO_REVANCHA" in mensaje
        assert "BALOTO" in mensaje

    def test_mezcla_detiene_la_operacion_antes_de_producir_reporte(self):
        baloto = _juego("BALOTO")
        disp = _FakeDisponibilidadRepoConMezcla("BALOTO_REVANCHA")
        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[baloto]), disp)
        try:
            reporte = caso_uso.ejecutar("BALOTO")
            pytest.fail(f"se produjo un reporte pese a la mezcla: {reporte}")
        except DisponibilidadHoldoutInvalidaError:
            pass

    def test_resumen_coincidente_no_lanza_excepcion(self):
        baloto = _juego("BALOTO")
        disp = _FakeDisponibilidadRepo()
        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[baloto]), disp)
        reporte = caso_uso.ejecutar("BALOTO")
        assert reporte.juego_codigo == "BALOTO"


class TestContratoDelCasoDeUso:
    def test_repositorio_de_disponibilidad_invocado_exactamente_una_vez(self):
        baloto = _juego("BALOTO")
        disp = _FakeDisponibilidadRepo()
        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[baloto]), disp)
        caso_uso.ejecutar("BALOTO")
        assert len(disp.llamadas) == 1

    def test_argumentos_correctos_al_puerto_de_disponibilidad(self):
        baloto = _juego("BALOTO")
        disp = _FakeDisponibilidadRepo()
        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[baloto]), disp)
        caso_uso.ejecutar("BALOTO")
        juego_id, codigo_juego, desde = disp.llamadas[0]
        assert juego_id == baloto.id
        assert codigo_juego == "BALOTO"
        assert desde == 2706

    def test_nunca_invoca_repositorio_de_historicos_completos(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/use_cases/evaluar_elegibilidad_reapertura_ml.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        nombres_importados = set()
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.ImportFrom):
                for alias in nodo.names:
                    nombres_importados.add(alias.name)
        assert "ResultadosHistoricosRepository" not in nombres_importados
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Attribute):
                assert nodo.attr != "listar_resultados_numericos"

    def test_nunca_llama_a_casos_de_uso_de_ae36_37_38(self):
        import inspect
        from app.application.use_cases import evaluar_elegibilidad_reapertura_ml as modulo
        codigo_fuente = inspect.getsource(modulo)
        for nombre_prohibido in (
            "EvaluarBaselineMLProbabilidadNumeros", "EvaluarRobustezMLProbabilidadNumeros",
            "CompararFamiliasMLProbabilidadNumeros",
        ):
            assert nombre_prohibido not in codigo_fuente

    def test_no_persiste_nada_firma_del_constructor(self):
        import inspect
        firma = inspect.signature(EvaluarElegibilidadReaperturaML.__init__)
        nombres_parametros = set(firma.parameters.keys()) - {"self"}
        assert nombres_parametros == {"juego_repository", "disponibilidad_repository"}

    def test_reportes_separados_por_juego_no_se_mezclan(self):
        baloto = _juego("BALOTO")
        revancha = _juego("BALOTO_REVANCHA")

        class RepoDosJuegos:
            def __init__(self):
                self.mapa = {baloto.id: 40, revancha.id: 150}
            def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
                total = self.mapa[juego_id]
                maximo = desde_numero_sorteo + total - 1 if total > 0 else None
                minimo = desde_numero_sorteo if total > 0 else None
                return ResumenDisponibilidadHoldout(
                    juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
                    total_registros=total, total_numeros_distintos=total,
                    numero_sorteo_minimo=minimo, numero_sorteo_maximo=maximo,
                )

        caso_uso = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[baloto, revancha]), RepoDosJuegos())
        r_baloto = caso_uso.ejecutar("BALOTO")
        r_revancha = caso_uso.ejecutar("BALOTO_REVANCHA")
        assert r_baloto.estado == EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES
        assert r_revancha.estado == EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO
