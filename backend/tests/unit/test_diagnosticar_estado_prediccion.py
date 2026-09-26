"""Tests de `DiagnosticarEstadoPrediccion` -Etapa AE-46, validada.

Se construyen las clases REALES de AE-40/41 con repositorios fake de
metadatos sinteticos -nunca PostgreSQL, nunca resultados de sorteos.
El diagnostico debe coincidir en estado y motivos con AE-44 y nunca
declarar un juego desbloqueable."""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

import pytest

from app.application.exceptions import DominioError, JuegoNoEncontradoError
from app.application.ml.diagnostico_bloqueo import CondicionDesbloqueoML
from app.application.ml.tipos import DecisionContinuidadML, EstadoPrediccionML, ResumenDisponibilidadHoldout
from app.application.use_cases import resolver_estado_prediccion as modulo_ae44
from app.application.use_cases.diagnosticar_estado_prediccion import DiagnosticarEstadoPrediccion
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML
from app.application.use_cases.resolver_estado_prediccion import (
    DecisionContinuidadAusenteError,
    JuegoNoAutorizadoParaEstadoPrediccionError,
    ResolverEstadoPrediccion,
)
from app.domain.entities.juego import Juego
from tests.unit.fakes import FakeJuegoRepository

JUEGOS = ("BALOTO", "BALOTO_REVANCHA")
RAIZ_BACKEND = Path(__file__).resolve().parents[2]
ARCHIVO_CASO_USO = RAIZ_BACKEND / "app" / "application" / "use_cases" / "diagnosticar_estado_prediccion.py"
ARCHIVO_ML = RAIZ_BACKEND / "app" / "application" / "ml" / "diagnostico_bloqueo.py"


def _juego(codigo: str) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43, cantidad_numeros=5,
        tiene_superbalota=True, superbalota_min=1, superbalota_max=16, tiene_color=False,
        permite_repeticion=False, activo=True,
    )


class _FakeDisponibilidadRepo:
    """Solo metadatos sinteticos: conteos y minimo/maximo desde 2706."""

    def __init__(self, total=0, minimo=None, maximo=None):
        self._total, self._minimo, self._maximo = total, minimo, maximo
        self.llamadas = 0

    def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
        self.llamadas += 1
        return ResumenDisponibilidadHoldout(
            juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
            total_registros=self._total, total_numeros_distintos=self._total,
            numero_sorteo_minimo=self._minimo, numero_sorteo_maximo=self._maximo,
        )


def _autorizacion(codigo: str, disponibilidad) -> EvaluarAutorizacionOperativaML:
    return EvaluarAutorizacionOperativaML(
        EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[_juego(codigo)]), disponibilidad)
    )


class _AutorizacionQueFalla:
    def ejecutar(self, codigo_juego):
        raise AssertionError("no deberia consultarse AE-41")


ESCENARIOS = {
    "sin_sorteos": lambda: _FakeDisponibilidadRepo(total=0),
    "ocho_2706_2713": lambda: _FakeDisponibilidadRepo(total=8, minimo=2706, maximo=2713),
    "noventa_y_nueve": lambda: _FakeDisponibilidadRepo(total=99, minimo=2706, maximo=2804),
    "cien_2706_2805": lambda: _FakeDisponibilidadRepo(total=100, minimo=2706, maximo=2805),
    "hueco": lambda: _FakeDisponibilidadRepo(total=8, minimo=2706, maximo=2714),
}


class TestCoherenciaConAE44:
    @pytest.mark.parametrize("escenario", list(ESCENARIOS))
    @pytest.mark.parametrize("codigo", JUEGOS)
    def test_estado_y_motivos_coinciden_con_resolver_estado_prediccion(self, escenario, codigo):
        diagnostico = DiagnosticarEstadoPrediccion(_autorizacion(codigo, ESCENARIOS[escenario]())).ejecutar(codigo)
        reporte = ResolverEstadoPrediccion(_autorizacion(codigo, ESCENARIOS[escenario]())).ejecutar(codigo)
        assert diagnostico.juego_codigo == codigo
        assert (diagnostico.estado, diagnostico.motivos) == (reporte.estado, reporte.motivos)
        assert diagnostico.desbloqueable is False

    def test_una_sola_consulta_de_metadatos_por_ejecucion(self):
        disponibilidad = _FakeDisponibilidadRepo(total=8, minimo=2706, maximo=2713)
        DiagnosticarEstadoPrediccion(_autorizacion("BALOTO", disponibilidad)).ejecutar("BALOTO")
        assert disponibilidad.llamadas == 1


class TestEstadoActualInformado:
    @pytest.mark.parametrize("codigo", JUEGOS)
    def test_ocho_de_cien_con_no_go(self, codigo):
        diagnostico = DiagnosticarEstadoPrediccion(_autorizacion(codigo, ESCENARIOS["ocho_2706_2713"]())).ejecutar(codigo)
        assert diagnostico.estado is EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES
        assert diagnostico.progreso.total_sorteos_nuevos == 8
        assert diagnostico.progreso.faltantes == 92
        assert diagnostico.condiciones_pendientes == (
            CondicionDesbloqueoML.MINIMO_SORTEOS_NUEVOS,
            CondicionDesbloqueoML.EVIDENCIA_CIENTIFICA_AE39,
            CondicionDesbloqueoML.PROTOCOLO_PROSPECTIVO_PRERREGISTRADO,
            CondicionDesbloqueoML.EVALUACION_PROSPECTIVA_POSITIVA,
        )

    def test_cien_sorteos_sigue_bloqueado_por_no_go(self):
        diagnostico = DiagnosticarEstadoPrediccion(_autorizacion("BALOTO", ESCENARIOS["cien_2706_2805"]())).ejecutar("BALOTO")
        assert diagnostico.progreso.faltantes == 0
        assert CondicionDesbloqueoML.MINIMO_SORTEOS_NUEVOS not in diagnostico.condiciones_pendientes
        assert CondicionDesbloqueoML.EVIDENCIA_CIENTIFICA_AE39 in diagnostico.condiciones_pendientes
        assert diagnostico.estado is EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO


class TestReutilizacionDelRegistroAE44:
    def test_usa_el_registro_de_ae44_sin_copia(self):
        arbol = ast.parse(ARCHIVO_CASO_USO.read_text(encoding="utf-8"))
        asignaciones = [n.targets[0].id for n in ast.walk(arbol)
                        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)]
        assert "DECISIONES_CONTINUIDAD_AE39" not in asignaciones

    def test_clave_ausente_lanza_error_sin_consultar_ae41(self, monkeypatch):
        incompleto = MappingProxyType({"BALOTO": DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE})
        monkeypatch.setattr(modulo_ae44, "DECISIONES_CONTINUIDAD_AE39", incompleto)
        with pytest.raises(DecisionContinuidadAusenteError, match="BALOTO_REVANCHA"):
            DiagnosticarEstadoPrediccion(_AutorizacionQueFalla()).ejecutar("BALOTO_REVANCHA")

    def test_nunca_usa_get_ni_setdefault(self):
        arbol = ast.parse(ARCHIVO_CASO_USO.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr in ("get", "setdefault"):
                pytest.fail(f"uso de .{nodo.func.attr}() en la linea {nodo.lineno}")


class TestAislamiento:
    @pytest.mark.parametrize("codigo", ["MILOTO", "COLORLOTO"])
    def test_juegos_no_autorizados_se_rechazan_sin_consultar(self, codigo):
        with pytest.raises(JuegoNoAutorizadoParaEstadoPrediccionError, match=codigo):
            DiagnosticarEstadoPrediccion(_AutorizacionQueFalla()).ejecutar(codigo)

    def test_juego_inexistente_propaga_juego_no_encontrado(self):
        elegibilidad = EvaluarElegibilidadReaperturaML(FakeJuegoRepository(juegos=[]), _FakeDisponibilidadRepo())
        with pytest.raises(JuegoNoEncontradoError):
            DiagnosticarEstadoPrediccion(EvaluarAutorizacionOperativaML(elegibilidad)).ejecutar("BALOTO")

    def test_reporte_de_otro_juego_se_rechaza(self):
        class AutorizacionDeOtroJuego:
            def ejecutar(self, codigo_juego):
                return _autorizacion("BALOTO_REVANCHA", ESCENARIOS["ocho_2706_2713"]()).ejecutar("BALOTO_REVANCHA")

        with pytest.raises(DominioError, match="BALOTO_REVANCHA"):
            DiagnosticarEstadoPrediccion(AutorizacionDeOtroJuego()).ejecutar("BALOTO")

    def test_constructor_solo_recibe_el_caso_de_uso_de_ae41(self):
        parametros = set(inspect.signature(DiagnosticarEstadoPrediccion.__init__).parameters) - {"self"}
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

    @pytest.mark.parametrize("ruta", [ARCHIVO_CASO_USO, ARCHIVO_ML])
    def test_no_importa_ml_pesado_ni_resultados(self, ruta):
        for importado in self._importaciones(ruta):
            assert importado.split(".")[0] not in self.PROHIBIDOS, importado
            assert importado not in self.MODULOS_PROHIBIDOS, importado

    def test_ningun_router_plantilla_script_ni_main_lo_expone(self):
        rutas = [*(RAIZ_BACKEND / "app" / "api").rglob("*.py"), *(RAIZ_BACKEND / "scripts").rglob("*.py"),
                 RAIZ_BACKEND / "app" / "main.py"]
        for ruta in rutas:
            contenido = ruta.read_text(encoding="utf-8")
            assert "diagnosticar_estado_prediccion" not in contenido, ruta
            assert "diagnostico_bloqueo" not in contenido, ruta
        for plantilla in (RAIZ_BACKEND / "app" / "templates").rglob("*.html"):
            contenido = plantilla.read_text(encoding="utf-8")
            assert "diagnostico_bloqueo" not in contenido and "diagnosticar_estado_prediccion" not in contenido
