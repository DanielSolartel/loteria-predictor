"""Tests de `ResolverEstadoPrediccion` -Etapa AE-44, validada.

Se construyen las clases REALES de AE-40/41 con repositorios fake de
metadatos sinteticos -nunca PostgreSQL, nunca resultados de sorteos.
Todas las combinaciones deben terminar en un estado bloqueado."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

import pytest

from app.application.exceptions import DominioError, JuegoNoEncontradoError
from app.application.ml.prediccion_bloqueada import DISCLAIMER_PERMANENTE
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import (
    DecisionContinuidadML,
    EstadoPrediccionML,
    ResumenDisponibilidadHoldout,
)
from app.application.use_cases import resolver_estado_prediccion as modulo_ae44
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML
from app.application.use_cases.resolver_estado_prediccion import (
    DECISIONES_CONTINUIDAD_AE39,
    DecisionContinuidadAusenteError,
    JuegoNoAutorizadoParaEstadoPrediccionError,
    ResolverEstadoPrediccion,
)
from app.domain.entities.juego import Juego
from tests.unit.fakes import FakeJuegoRepository

NUMERACION = EstadoPrediccionML.BLOQUEADO_NUMERACION_INVALIDA
DATOS = EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES
NO_GO = EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO
SIN_HOLDOUT = EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT
JUEGOS = ("BALOTO", "BALOTO_REVANCHA")
RAIZ_BACKEND = Path(__file__).resolve().parents[2]
ARCHIVO_CASO_USO = RAIZ_BACKEND / "app" / "application" / "use_cases" / "resolver_estado_prediccion.py"


def _juego(codigo: str) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43, cantidad_numeros=5,
        tiene_superbalota=True, superbalota_min=1, superbalota_max=16, tiene_color=False,
        permite_repeticion=False, activo=True,
    )


class _FakeDisponibilidadRepo:
    """Solo metadatos sinteticos: conteos y minimo/maximo desde 2706."""

    def __init__(self, total=0, minimo=None, maximo=None, distintos=None):
        self._total = total
        self._minimo = minimo
        self._maximo = maximo
        self._distintos = total if distintos is None else distintos

    def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
        return ResumenDisponibilidadHoldout(
            juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
            total_registros=self._total, total_numeros_distintos=self._distintos,
            numero_sorteo_minimo=self._minimo, numero_sorteo_maximo=self._maximo,
        )


def _caso(codigo: str, disponibilidad: _FakeDisponibilidadRepo) -> ResolverEstadoPrediccion:
    elegibilidad = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[_juego(codigo)]), disponibilidad)
    return ResolverEstadoPrediccion(EvaluarAutorizacionOperativaML(elegibilidad))


class _AutorizacionQueFalla:
    def ejecutar(self, codigo_juego):
        raise AssertionError("no deberia consultarse AE-41")


ESCENARIOS = {
    "sin_sorteos": (_FakeDisponibilidadRepo(total=0), DATOS, (DATOS, NO_GO, SIN_HOLDOUT)),
    "ocho_sorteos_2706_2713": (_FakeDisponibilidadRepo(total=8, minimo=2706, maximo=2713), DATOS, (DATOS, NO_GO, SIN_HOLDOUT)),
    "noventa_y_nueve": (_FakeDisponibilidadRepo(total=99, minimo=2706, maximo=2804), DATOS, (DATOS, NO_GO, SIN_HOLDOUT)),
    "cien_2706_2805": (_FakeDisponibilidadRepo(total=100, minimo=2706, maximo=2805), NO_GO, (NO_GO, SIN_HOLDOUT)),
    "hueco_en_numeracion": (_FakeDisponibilidadRepo(total=8, minimo=2706, maximo=2714), NUMERACION, (NUMERACION, NO_GO, SIN_HOLDOUT)),
    "inicio_distinto_de_2706": (_FakeDisponibilidadRepo(total=8, minimo=2707, maximo=2714), NUMERACION, (NUMERACION, NO_GO, SIN_HOLDOUT)),
}


class TestEstados:
    @pytest.mark.parametrize("escenario", list(ESCENARIOS))
    @pytest.mark.parametrize("codigo", JUEGOS)
    def test_todos_los_escenarios_terminan_bloqueados(self, escenario, codigo):
        disponibilidad, estado, motivos = ESCENARIOS[escenario]
        reporte = _caso(codigo, disponibilidad).ejecutar(codigo)

        assert reporte.juego_codigo == codigo
        assert reporte.estado is estado
        assert reporte.motivos == motivos
        assert reporte.combinaciones == () and reporte.numeros_fuertes == ()
        assert reporte.numeros_debiles == () and reporte.probabilidades == ()
        assert reporte.nivel_confianza is None
        assert not (reporte.resultados_observados or reporte.modelos_entrenados
                    or reporte.predicciones_generadas or reporte.holdout_consumido)
        assert reporte.disclaimer == DISCLAIMER_PERMANENTE

    def test_determinismo(self):
        disponibilidad = _FakeDisponibilidadRepo(total=8, minimo=2706, maximo=2713)
        assert _caso("BALOTO", disponibilidad).ejecutar("BALOTO") == _caso("BALOTO", disponibilidad).ejecutar("BALOTO")


class TestRegistroDecisionesAE39:
    def test_claves_exactas_y_ambas_no_go(self):
        assert set(DECISIONES_CONTINUIDAD_AE39) == set(JUEGOS_AUTORIZADOS_AE40)
        assert all(d is DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE for d in DECISIONES_CONTINUIDAD_AE39.values())

    def test_registro_inmutable(self):
        assert isinstance(DECISIONES_CONTINUIDAD_AE39, MappingProxyType)
        with pytest.raises(TypeError):
            DECISIONES_CONTINUIDAD_AE39["BALOTO"] = DecisionContinuidadML.EVIDENCIA_EXPLORATORIA_DE_MEJORA

    def test_procedencia_documentada(self):
        documentacion = modulo_ae44.__doc__ + (modulo_ae44.PROCEDENCIA_DECISIONES_AE39 or "")
        for dato in ("AE-39", "-0.000136584231", "-0.000026473413", "-0.000647734500", "-0.000137653795", "2081..2590"):
            assert dato in documentacion

    def test_clave_ausente_lanza_error_explicito_sin_consultar_ae41(self, monkeypatch):
        incompleto = MappingProxyType({"BALOTO": DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE})
        monkeypatch.setattr(modulo_ae44, "DECISIONES_CONTINUIDAD_AE39", incompleto)
        with pytest.raises(DecisionContinuidadAusenteError, match="BALOTO_REVANCHA"):
            ResolverEstadoPrediccion(_AutorizacionQueFalla()).ejecutar("BALOTO_REVANCHA")

    def test_el_codigo_nunca_usa_get_ni_valor_por_defecto_sobre_el_registro(self):
        arbol = ast.parse(ARCHIVO_CASO_USO.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr in ("get", "setdefault"):
                pytest.fail(f"uso de .{nodo.func.attr}() en la linea {nodo.lineno}")


class TestAislamientoYOrden:
    @pytest.mark.parametrize("codigo", ["MILOTO", "COLORLOTO"])
    def test_juegos_no_autorizados_se_rechazan_sin_consultar(self, codigo):
        with pytest.raises(JuegoNoAutorizadoParaEstadoPrediccionError, match=codigo):
            ResolverEstadoPrediccion(_AutorizacionQueFalla()).ejecutar(codigo)

    def test_juego_autorizado_inexistente_propaga_juego_no_encontrado(self):
        elegibilidad = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[]), _FakeDisponibilidadRepo())
        with pytest.raises(JuegoNoEncontradoError):
            ResolverEstadoPrediccion(EvaluarAutorizacionOperativaML(elegibilidad)).ejecutar("BALOTO")

    def test_reporte_de_otro_juego_se_rechaza(self):
        class AutorizacionDeOtroJuego:
            def ejecutar(self, codigo_juego):
                otro = "BALOTO_REVANCHA" if codigo_juego == "BALOTO" else "BALOTO"
                elegibilidad = EvaluarElegibilidadReaperturaML(
                    FakeJuegoRepository(juegos=[_juego(otro)]),
                    _FakeDisponibilidadRepo(total=8, minimo=2706, maximo=2713),
                )
                return EvaluarAutorizacionOperativaML(elegibilidad).ejecutar(otro)

        with pytest.raises(DominioError, match="BALOTO_REVANCHA"):
            ResolverEstadoPrediccion(AutorizacionDeOtroJuego()).ejecutar("BALOTO")

    def test_constructor_solo_recibe_el_caso_de_uso_de_ae41(self):
        parametros = set(inspect.signature(ResolverEstadoPrediccion.__init__).parameters) - {"self"}
        assert parametros == {"caso_uso_autorizacion"}


class TestEstructura:
    PROHIBIDOS = {"sklearn", "numpy", "scipy", "pandas", "sqlalchemy", "fastapi", "jinja2", "random", "time"}
    MODULOS_PROHIBIDOS = {
        "app.application.interfaces.resultados_historicos_repository",
        "app.application.ml.modelo", "app.application.ml.dataset",
        "app.application.ml.inferencia", "app.application.ml.features",
    }

    @staticmethod
    def _importaciones(ruta: Path) -> list[str]:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        salida: list[str] = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                salida.extend(a.name for a in nodo.names)
            elif isinstance(nodo, ast.ImportFrom):
                salida.append(nodo.module or "")
        return salida

    def test_caso_de_uso_no_importa_ml_pesado_ni_resultados(self):
        importaciones = self._importaciones(ARCHIVO_CASO_USO)
        for importado in importaciones:
            assert importado.split(".")[0] not in self.PROHIBIDOS, importado
            assert importado not in self.MODULOS_PROHIBIDOS, importado

    def test_ningun_router_plantilla_ni_script_lo_expone(self):
        rutas = [*(RAIZ_BACKEND / "app" / "api").rglob("*.py"), *(RAIZ_BACKEND / "scripts").rglob("*.py"),
                 RAIZ_BACKEND / "app" / "main.py"]
        for ruta in rutas:
            assert "resolver_estado_prediccion" not in ruta.read_text(encoding="utf-8"), ruta
        for plantilla in (RAIZ_BACKEND / "app" / "templates").rglob("*.html"):
            assert "resolver_estado_prediccion" not in plantilla.read_text(encoding="utf-8"), plantilla

    def test_solo_modelo_py_importa_sklearn_en_application_ml(self):
        directorio = RAIZ_BACKEND / "app" / "application" / "ml"
        importadores = {
            ruta.name for ruta in directorio.glob("*.py")
            if any(i.split(".")[0] == "sklearn" for i in self._importaciones(ruta))
        }
        assert importadores == {"modelo.py"}
