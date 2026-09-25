"""Tests del script de auditoria operativa -`scripts/auditoria_operativa_bloqueo.py`,
Etapa AE-42."""
from __future__ import annotations

import json
import os
import tempfile
from uuid import uuid4

import pytest

from app.application.ml.tipos import ResumenDisponibilidadHoldout
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML
from app.domain.entities.juego import Juego
from scripts.auditoria_operativa_bloqueo import (
    EXIT_FALLO_EVALUANDO_JUEGO,
    EXIT_REPORTE_INCONSISTENTE,
    EXIT_TRANSACCION_NO_SOLO_LECTURA,
    FalloAuditoriaOperativaError,
    escribir_reporte_atomico,
    ejecutar_auditoria_con_sesion,
    verificar_transaccion_solo_lectura,
)

INSTANTE = "2026-09-24T00:00:00+00:00"


def _juego(codigo: str) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43, cantidad_numeros=5,
        tiene_superbalota=True, superbalota_min=1, superbalota_max=16, tiene_color=False,
        permite_repeticion=False, activo=True,
    )


class _FakeJuegoRepo:
    def __init__(self, juegos):
        self._por_codigo = {j.codigo: j for j in juegos}

    def obtener_por_codigo(self, codigo):
        return self._por_codigo.get(codigo)


class _FakeDisponibilidadRepo0:
    def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
        return ResumenDisponibilidadHoldout(
            juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
            total_registros=0, total_numeros_distintos=0, numero_sorteo_minimo=None, numero_sorteo_maximo=None,
        )


def _caso_autorizacion_normal():
    baloto = _juego("BALOTO")
    revancha = _juego("BALOTO_REVANCHA")
    caso_elegibilidad = EvaluarElegibilidadReaperturaML(_FakeJuegoRepo([baloto, revancha]), _FakeDisponibilidadRepo0())
    return EvaluarAutorizacionOperativaML(caso_elegibilidad)


class TestOrquestacionComprobable:
    def test_ambos_juegos_bloqueados_produce_reporte_completo(self):
        reporte = ejecutar_auditoria_con_sesion(_caso_autorizacion_normal(), INSTANTE)
        assert reporte["estado_global"] == "bloqueado_datos_insuficientes"
        assert set(reporte["resultados"].keys()) == {"BALOTO", "BALOTO_REVANCHA"}

    def test_invoca_el_caso_de_uso_real_de_produccion(self):
        # el fake unicamente reemplaza los REPOSITORIOS -EvaluarAutorizacionOperativaML
        # y EvaluarElegibilidadReaperturaML son las clases reales de produccion,
        # nunca una reimplementacion en el script.
        caso = _caso_autorizacion_normal()
        assert isinstance(caso, EvaluarAutorizacionOperativaML)
        assert isinstance(caso._caso_uso_elegibilidad, EvaluarElegibilidadReaperturaML)
        reporte = ejecutar_auditoria_con_sesion(caso, INSTANTE)
        assert reporte["auditoria_correcta"] is True

    def test_excepcion_al_consultar_el_segundo_juego_detiene_todo(self):
        class DisponibilidadRepoFallaSegundo:
            def __init__(self):
                self.llamadas = 0
            def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
                self.llamadas += 1
                if self.llamadas == 2:
                    raise RuntimeError("fallo simulado")
                return ResumenDisponibilidadHoldout(
                    juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
                    total_registros=0, total_numeros_distintos=0, numero_sorteo_minimo=None, numero_sorteo_maximo=None,
                )
        baloto = _juego("BALOTO")
        revancha = _juego("BALOTO_REVANCHA")
        caso_elegibilidad = EvaluarElegibilidadReaperturaML(_FakeJuegoRepo([baloto, revancha]), DisponibilidadRepoFallaSegundo())
        caso_autorizacion = EvaluarAutorizacionOperativaML(caso_elegibilidad)
        with pytest.raises(FalloAuditoriaOperativaError) as exc_info:
            ejecutar_auditoria_con_sesion(caso_autorizacion, INSTANTE)
        assert exc_info.value.codigo_salida == EXIT_FALLO_EVALUANDO_JUEGO

    def test_estructura_inconsistente_propaga_codigo_correcto(self):
        # simulamos una inconsistencia real: un caso de uso que devuelve
        # dos veces el mismo juego (defecto hipotetico de infraestructura)
        from app.application.ml.tipos import EstadoAutorizacionOperativaML, ReporteAutorizacionOperativaML, ReporteElegibilidadReaperturaML, EstadoElegibilidadReaperturaML

        class CasoAutorizacionQueMezcla:
            def ejecutar(self, codigo_juego):
                return ReporteAutorizacionOperativaML(
                    juego_codigo="BALOTO", estado=EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES,
                    motivo="x", reporte_elegibilidad=ReporteElegibilidadReaperturaML(
                        juego_codigo="BALOTO", estado=EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES,
                        proximo_holdout_inicio=2706, minimo_sorteos_nuevos_requeridos=100, total_sorteos_nuevos=0,
                        numero_sorteo_minimo=None, numero_sorteo_maximo=None, numero_sorteo_objetivo_minimo=2805,
                        numeracion_contigua=True,
                    ),
                )
        with pytest.raises(FalloAuditoriaOperativaError) as exc_info:
            ejecutar_auditoria_con_sesion(CasoAutorizacionQueMezcla(), INSTANTE)
        assert exc_info.value.codigo_salida == EXIT_REPORTE_INCONSISTENTE

    def test_orquestacion_no_abre_conexion_ni_sesion_por_su_cuenta(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("scripts/auditoria_operativa_bloqueo.py")
        codigo_fuente = ruta.read_text(encoding="utf-8")
        # create_engine/Session solo deben aparecer en main(), nunca dentro
        # de ejecutar_auditoria_con_sesion
        arbol = ast_modulo.parse(codigo_fuente)
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.FunctionDef) and nodo.name == "ejecutar_auditoria_con_sesion":
                cuerpo_fuente = ast_modulo.unparse(nodo)
                assert "create_engine" not in cuerpo_fuente
                assert "Session(" not in cuerpo_fuente


class TestTransaccionSoloLectura:
    def test_transaction_read_only_on_pasa(self):
        class FakeResult:
            def scalar(self):
                return "on"
        class FakeSession:
            def execute(self, stmt):
                return FakeResult()
        verificar_transaccion_solo_lectura(FakeSession())  # no debe lanzar

    def test_transaction_read_only_off_falla_codigo_correcto(self):
        class FakeResult:
            def scalar(self):
                return "off"
        class FakeSession:
            def execute(self, stmt):
                return FakeResult()
        with pytest.raises(FalloAuditoriaOperativaError) as exc_info:
            verificar_transaccion_solo_lectura(FakeSession())
        assert exc_info.value.codigo_salida == EXIT_TRANSACCION_NO_SOLO_LECTURA

    def test_nunca_hace_commit_flush_de_sesion_ni_escritura_sql(self):
        import pathlib
        codigo_fuente = pathlib.Path("scripts/auditoria_operativa_bloqueo.py").read_text(encoding="utf-8")
        # "f.flush()" es un flush de archivo (escritura atomica del JSON
        # externo, nunca de una sesion de base de datos) -se excluye
        # explicitamente; session.commit()/session.flush() si estan prohibidos.
        for palabra_prohibida in ("session.commit(", "session.flush(", "conexion.commit(", "INSERT INTO", "UPDATE ", "DELETE FROM"):
            assert palabra_prohibida not in codigo_fuente
        assert "ROLLBACK" in codigo_fuente


class TestSalidaAtomicaNuncaIncompleta:
    def test_escritura_normal_produce_json_valido(self):
        tmpdir = tempfile.mkdtemp()
        ruta = os.path.join(tmpdir, "auditoria.json")
        escribir_reporte_atomico({"x": 1}, ruta)
        with open(ruta) as f:
            assert json.load(f) == {"x": 1}

    def test_fallo_durante_serializacion_no_deja_archivo_destino(self):
        tmpdir = tempfile.mkdtemp()
        ruta = os.path.join(tmpdir, "auditoria.json")
        class NoSerializable:
            pass
        with pytest.raises(TypeError):
            escribir_reporte_atomico({"x": NoSerializable()}, ruta)
        assert not os.path.exists(ruta)

    def test_fallo_no_deja_temporales_residuales(self):
        tmpdir = tempfile.mkdtemp()
        ruta = os.path.join(tmpdir, "auditoria.json")
        class NoSerializable:
            pass
        with pytest.raises(TypeError):
            escribir_reporte_atomico({"x": NoSerializable()}, ruta)
        assert os.listdir(tmpdir) == []

    def test_escritura_exitosa_no_deja_temporales(self):
        tmpdir = tempfile.mkdtemp()
        ruta = os.path.join(tmpdir, "auditoria.json")
        escribir_reporte_atomico({"x": 1}, ruta)
        assert os.listdir(tmpdir) == ["auditoria.json"]


class TestGarantiasNegativas:
    def test_script_no_importa_sklearn(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("scripts/auditoria_operativa_bloqueo.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                for alias in nodo.names:
                    assert not alias.name.startswith("sklearn")
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module:
                    assert not nodo.module.startswith("sklearn")

    def test_no_importa_resultados_historicos_repository(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("scripts/auditoria_operativa_bloqueo.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        nombres_importados = set()
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.ImportFrom):
                for alias in nodo.names:
                    nombres_importados.add(alias.name)
        assert "ResultadosHistoricosRepository" not in nombres_importados

    def test_no_hay_tareas_periodicas_ni_disparadores_automaticos(self):
        import pathlib
        codigo_fuente = pathlib.Path("scripts/auditoria_operativa_bloqueo.py").read_text(encoding="utf-8")
        for prohibido in ("import schedule", "import celery", "from celery", "APScheduler", "@app.on_event", "BackgroundTasks", "crontab"):
            assert prohibido not in codigo_fuente

    def test_no_agrega_rutas_ni_endpoints_ni_plantillas(self):
        import pathlib
        for ruta in pathlib.Path("app").rglob("*.py"):
            if "router" in ruta.name.lower() or "api" in str(ruta).lower():
                contenido = ruta.read_text(encoding="utf-8")
                assert "auditoria_operativa" not in contenido.lower()

    def test_solo_ejecuta_por_peticion_explicita_tiene_main_guard(self):
        import pathlib
        codigo_fuente = pathlib.Path("scripts/auditoria_operativa_bloqueo.py").read_text(encoding="utf-8")
        assert 'if __name__ == "__main__":' in codigo_fuente


class TestFirmaYEstructura:
    def test_firma_de_ejecutar_auditoria_con_sesion(self):
        import inspect
        from scripts.auditoria_operativa_bloqueo import ejecutar_auditoria_con_sesion as funcion
        firma = inspect.signature(funcion)
        assert list(firma.parameters.keys()) == ["caso_autorizacion", "instante_utc"]

    def test_codigos_de_salida_todos_distintos_de_cero_salvo_ok(self):
        from scripts import auditoria_operativa_bloqueo as modulo
        codigos = [
            modulo.EXIT_FALLO_INESPERADO, modulo.EXIT_FALLO_CONEXION,
            modulo.EXIT_REVISION_ALEMBIC_INESPERADA, modulo.EXIT_TRANSACCION_NO_SOLO_LECTURA,
            modulo.EXIT_REPORTE_INCONSISTENTE, modulo.EXIT_FALLO_EVALUANDO_JUEGO,
        ]
        assert modulo.EXIT_OK == 0
        assert all(c != 0 for c in codigos)
        assert len(set(codigos)) == len(codigos)
