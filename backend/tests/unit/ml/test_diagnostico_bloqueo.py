"""Tests de `application/ml/diagnostico_bloqueo.py` -Etapa AE-46,
validada. Los reportes de AE-41 se construyen con las funciones
REALES de `reapertura.py` y `autorizacion_operativa.py` a partir de
resumenes sinteticos de metadatos -nunca PostgreSQL ni resultados."""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from app.application.ml.autorizacion_operativa import (
    construir_reporte_bloqueado_por_numeracion_invalida,
    evaluar_autorizacion_operativa_desde_elegibilidad,
)
from app.application.ml.diagnostico_bloqueo import (
    CONDICIONES_SIN_MECANISMO_AE46,
    CondicionDesbloqueoML,
    DiagnosticoBloqueoInvalidoError,
    DiagnosticoBloqueoJuego,
    EstadoCondicionDesbloqueo,
    ProgresoSorteosNuevos,
    diagnosticar_bloqueo,
)
from app.application.ml.prediccion_bloqueada import resolver_prediccion
from app.application.ml.reapertura import evaluar_elegibilidad_reapertura_ml
from app.application.ml.tipos import (
    DecisionContinuidadML,
    EstadoPrediccionML,
    ReporteAutorizacionOperativaML,
    ResumenDisponibilidadHoldout,
)

NO_GO = DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE
EXPLORATORIA = DecisionContinuidadML.EVIDENCIA_EXPLORATORIA_DE_MEJORA
C = CondicionDesbloqueoML
ARCHIVO = Path(__file__).resolve().parents[3] / "app" / "application" / "ml" / "diagnostico_bloqueo.py"


def _autorizacion(total: int, juego: str = "BALOTO", minimo=2706, maximo=None) -> ReporteAutorizacionOperativaML:
    if maximo is None:
        maximo = 2705 + total if total else None
    resumen = ResumenDisponibilidadHoldout(
        juego_codigo=juego, desde_numero_sorteo=2706, total_registros=total, total_numeros_distintos=total,
        numero_sorteo_minimo=minimo if total else None, numero_sorteo_maximo=maximo,
    )
    return evaluar_autorizacion_operativa_desde_elegibilidad(evaluar_elegibilidad_reapertura_ml(resumen))


def _invalida(juego: str = "BALOTO") -> ReporteAutorizacionOperativaML:
    return construir_reporte_bloqueado_por_numeracion_invalida(juego, "hueco sintetico en la numeracion")


def _cumplidas(diagnostico: DiagnosticoBloqueoJuego) -> dict:
    return {c.condicion: c.cumplida for c in diagnostico.condiciones}


class TestProgreso:
    @pytest.mark.parametrize("total, faltantes", [(0, 100), (8, 92), (99, 1), (100, 0), (130, 0)])
    def test_progreso_desde_el_reporte_de_ae40(self, total, faltantes):
        diagnostico = diagnosticar_bloqueo(_autorizacion(total), NO_GO)
        p = diagnostico.progreso
        assert p.evaluable is True
        assert p.desde_numero_sorteo == 2706
        assert p.total_sorteos_nuevos == total
        assert p.minimo_requerido == 100
        assert p.faltantes == faltantes
        assert p.numero_sorteo_objetivo_minimo == 2805

    def test_estado_actual_informado_ocho_de_cien(self):
        diagnostico = diagnosticar_bloqueo(_autorizacion(8), NO_GO)
        assert diagnostico.progreso.faltantes == 92
        detalle = next(c.detalle for c in diagnostico.condiciones if c.condicion is C.MINIMO_SORTEOS_NUEVOS)
        assert "8" in detalle and "100" in detalle and "92" in detalle and "2805" in detalle

    def test_numeracion_invalida_no_es_evaluable(self):
        p = diagnosticar_bloqueo(_invalida(), NO_GO).progreso
        assert p.evaluable is False
        assert p.desde_numero_sorteo == 2706
        assert (p.total_sorteos_nuevos, p.minimo_requerido, p.faltantes, p.numero_sorteo_objetivo_minimo) == (None,) * 4

    @pytest.mark.parametrize("cambios", [
        {"faltantes": 5},
        {"total_sorteos_nuevos": -1},
        {"minimo_requerido": None},
    ])
    def test_progreso_evaluable_incoherente_se_rechaza(self, cambios):
        base = dict(evaluable=True, desde_numero_sorteo=2706, total_sorteos_nuevos=8, minimo_requerido=100,
                    faltantes=92, numero_sorteo_objetivo_minimo=2805)
        base.update(cambios)
        with pytest.raises(ValueError):
            ProgresoSorteosNuevos(**base)

    def test_progreso_no_evaluable_con_cifras_se_rechaza(self):
        with pytest.raises(ValueError):
            ProgresoSorteosNuevos(evaluable=False, desde_numero_sorteo=2706, total_sorteos_nuevos=8,
                                  minimo_requerido=None, faltantes=None, numero_sorteo_objetivo_minimo=None)


class TestCondiciones:
    def test_orden_y_conjunto_cerrado(self):
        diagnostico = diagnosticar_bloqueo(_autorizacion(8), NO_GO)
        assert [c.condicion for c in diagnostico.condiciones] == list(CondicionDesbloqueoML)
        assert set(CondicionDesbloqueoML) == {
            C.NUMERACION_HOLDOUT_VALIDA, C.MINIMO_SORTEOS_NUEVOS, C.EVIDENCIA_CIENTIFICA_AE39,
            C.PROTOCOLO_PROSPECTIVO_PRERREGISTRADO, C.EVALUACION_PROSPECTIVA_POSITIVA,
        }
        assert CONDICIONES_SIN_MECANISMO_AE46 == {C.PROTOCOLO_PROSPECTIVO_PRERREGISTRADO, C.EVALUACION_PROSPECTIVA_POSITIVA}

    def test_estado_actual_informado(self):
        diagnostico = diagnosticar_bloqueo(_autorizacion(8), NO_GO)
        assert _cumplidas(diagnostico) == {
            C.NUMERACION_HOLDOUT_VALIDA: True, C.MINIMO_SORTEOS_NUEVOS: False, C.EVIDENCIA_CIENTIFICA_AE39: False,
            C.PROTOCOLO_PROSPECTIVO_PRERREGISTRADO: False, C.EVALUACION_PROSPECTIVA_POSITIVA: False,
        }
        assert diagnostico.condiciones_pendientes == (
            C.MINIMO_SORTEOS_NUEVOS, C.EVIDENCIA_CIENTIFICA_AE39,
            C.PROTOCOLO_PROSPECTIVO_PRERREGISTRADO, C.EVALUACION_PROSPECTIVA_POSITIVA,
        )

    def test_alcanzar_cien_sorteos_no_desbloquea(self):
        diagnostico = diagnosticar_bloqueo(_autorizacion(100), NO_GO)
        cumplidas = _cumplidas(diagnostico)
        assert cumplidas[C.MINIMO_SORTEOS_NUEVOS] is True
        assert cumplidas[C.EVIDENCIA_CIENTIFICA_AE39] is False
        assert diagnostico.desbloqueable is False
        assert diagnostico.estado is EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO

    def test_numeracion_invalida(self):
        diagnostico = diagnosticar_bloqueo(_invalida(), NO_GO)
        cumplidas = _cumplidas(diagnostico)
        assert cumplidas[C.NUMERACION_HOLDOUT_VALIDA] is False
        assert cumplidas[C.MINIMO_SORTEOS_NUEVOS] is False
        detalle = next(c.detalle for c in diagnostico.condiciones if c.condicion is C.NUMERACION_HOLDOUT_VALIDA)
        assert "hueco sintetico" in detalle

    def test_ni_siquiera_con_todo_lo_evaluable_cumplido_se_desbloquea(self):
        diagnostico = diagnosticar_bloqueo(_autorizacion(100), EXPLORATORIA)
        cumplidas = _cumplidas(diagnostico)
        assert all(cumplidas[c] for c in CondicionDesbloqueoML if c not in CONDICIONES_SIN_MECANISMO_AE46)
        assert not any(cumplidas[c] for c in CONDICIONES_SIN_MECANISMO_AE46)
        assert diagnostico.desbloqueable is False
        assert diagnostico.estado is EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT
        detalle = next(c.detalle for c in diagnostico.condiciones if c.condicion is C.EVIDENCIA_CIENTIFICA_AE39)
        assert "exploratoria" in detalle


class TestCoherenciaConAE43:
    @pytest.mark.parametrize("autorizacion", [_autorizacion(0), _autorizacion(8), _autorizacion(99),
                                              _autorizacion(100), _invalida()])
    @pytest.mark.parametrize("decision", list(DecisionContinuidadML))
    def test_estado_y_motivos_coinciden_con_resolver_prediccion(self, autorizacion, decision):
        diagnostico = diagnosticar_bloqueo(autorizacion, decision)
        reporte = resolver_prediccion(autorizacion, decision)
        assert (diagnostico.estado, diagnostico.motivos) == (reporte.estado, reporte.motivos)
        assert diagnostico.juego_codigo == reporte.juego_codigo
        assert diagnostico.desbloqueable is False


def _base() -> DiagnosticoBloqueoJuego:
    return diagnosticar_bloqueo(_autorizacion(8), NO_GO)


def _condiciones(**invertir) -> tuple:
    """Condiciones del diagnostico real (8 de 100, NO-GO) con SOLO las
    indicadas invertidas -cada rechazo se debe a esa causa."""
    return tuple(
        dataclasses.replace(c, cumplida=not c.cumplida) if invertir.get(c.condicion.name) else c
        for c in _base().condiciones
    )


def _diagnostico(**cambios) -> DiagnosticoBloqueoJuego:
    return dataclasses.replace(_base(), **cambios)


class TestInvariantes:
    def test_desbloqueable_true_se_rechaza(self):
        with pytest.raises(ValueError):
            _diagnostico(desbloqueable=True)

    @pytest.mark.parametrize("nombre", [c.name for c in CONDICIONES_SIN_MECANISMO_AE46])
    def test_condicion_sin_mecanismo_cumplida_se_rechaza(self, nombre):
        with pytest.raises(ValueError):
            _diagnostico(condiciones=_condiciones(**{nombre: True}))

    def test_condiciones_incompletas_o_desordenadas_se_rechazan(self):
        completas = _condiciones()
        with pytest.raises(ValueError):
            _diagnostico(condiciones=completas[:-1])
        with pytest.raises(ValueError):
            _diagnostico(condiciones=tuple(reversed(completas)))

    @pytest.mark.parametrize("nombre", ["NUMERACION_HOLDOUT_VALIDA", "MINIMO_SORTEOS_NUEVOS", "EVIDENCIA_CIENTIFICA_AE39"])
    def test_condicion_incoherente_con_progreso_o_motivos_se_rechaza(self, nombre):
        with pytest.raises(ValueError):
            _diagnostico(condiciones=_condiciones(**{nombre: True}))

    def test_base_sin_cambios_es_valida(self):
        assert _diagnostico(condiciones=_condiciones()) == _base()

    def test_detalle_vacio_se_rechaza(self):
        with pytest.raises(ValueError):
            EstadoCondicionDesbloqueo(C.MINIMO_SORTEOS_NUEVOS, False, "  ")

    def test_estado_distinto_del_primer_motivo_se_rechaza(self):
        with pytest.raises(ValueError):
            _diagnostico(estado=EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO)

    def test_no_tiene_campos_predictivos(self):
        campos = {f.name for f in dataclasses.fields(DiagnosticoBloqueoJuego)}
        prohibidos = {"combinaciones", "numeros_fuertes", "numeros_debiles", "probabilidades", "nivel_confianza"}
        assert not campos & prohibidos


class TestEntradas:
    def test_juego_no_autorizado(self):
        with pytest.raises(DiagnosticoBloqueoInvalidoError, match="MILOTO"):
            diagnosticar_bloqueo(_invalida("MILOTO"), NO_GO)

    def test_tipos_incorrectos(self):
        with pytest.raises(DiagnosticoBloqueoInvalidoError):
            diagnosticar_bloqueo({"juego_codigo": "BALOTO"}, NO_GO)
        with pytest.raises(DiagnosticoBloqueoInvalidoError):
            diagnosticar_bloqueo(_autorizacion(8), "no_go_sin_evidencia_suficiente")

    def test_determinismo(self):
        assert diagnosticar_bloqueo(_autorizacion(8), NO_GO) == diagnosticar_bloqueo(_autorizacion(8), NO_GO)


class TestPureza:
    def test_solo_biblioteca_estandar_y_modulos_de_ml(self):
        arbol = ast.parse(ARCHIVO.read_text(encoding="utf-8"))
        permitidos_ml = {
            "app.application.ml.tipos", "app.application.ml.prediccion_bloqueada",
            "app.application.ml.reapertura", "app.application.ml.ventanas_temporales",
        }
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                if nodo.module.startswith("app"):
                    assert nodo.module in permitidos_ml, nodo.module
                else:
                    assert nodo.module.split(".")[0] in {"__future__", "dataclasses", "enum"}, nodo.module
            elif isinstance(nodo, ast.Import):
                pytest.fail(f"import directo no permitido: {[a.name for a in nodo.names]}")
