"""Tests de `application/ml/prediccion_bloqueada.py` -Etapa AE-43,
validada. Los reportes de AE-41 se construyen con las funciones
REALES de `autorizacion_operativa.py` y `reapertura.py` a partir de
resumenes sinteticos de metadatos -nunca con PostgreSQL."""
from __future__ import annotations

import pytest

from app.application.ml.autorizacion_operativa import (
    construir_reporte_bloqueado_por_numeracion_invalida,
    evaluar_autorizacion_operativa_desde_elegibilidad,
)
from app.application.ml.prediccion_bloqueada import (
    DISCLAIMER_PERMANENTE,
    TOP_COMBINACIONES,
    TOP_NUMEROS,
    PrediccionNoAutorizadaError,
    resolver_prediccion,
)
from app.application.ml.reapertura import evaluar_elegibilidad_reapertura_ml
from app.application.ml.tipos import (
    DecisionContinuidadML,
    EstadoAutorizacionOperativaML,
    EstadoPrediccionML,
    ReporteAutorizacionOperativaML,
    ReportePrediccionJuego,
    ResumenDisponibilidadHoldout,
)

NUMERACION = EstadoPrediccionML.BLOQUEADO_NUMERACION_INVALIDA
DATOS = EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES
NO_GO = EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO
SIN_HOLDOUT = EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT


def _autorizacion(estado: EstadoAutorizacionOperativaML, juego: str = "BALOTO") -> ReporteAutorizacionOperativaML:
    if estado is EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA:
        return construir_reporte_bloqueado_por_numeracion_invalida(juego, "hueco sintetico en la numeracion")
    total = 8 if estado is EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES else 100
    resumen = ResumenDisponibilidadHoldout(
        juego_codigo=juego, desde_numero_sorteo=2706, total_registros=total,
        total_numeros_distintos=total, numero_sorteo_minimo=2706, numero_sorteo_maximo=2705 + total,
    )
    reporte = evaluar_autorizacion_operativa_desde_elegibilidad(evaluar_elegibilidad_reapertura_ml(resumen))
    assert reporte.estado is estado
    return reporte


ESPERADOS = {
    (EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA, DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE):
        (NUMERACION, (NUMERACION, NO_GO, SIN_HOLDOUT)),
    (EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA, DecisionContinuidadML.EVIDENCIA_EXPLORATORIA_DE_MEJORA):
        (NUMERACION, (NUMERACION, SIN_HOLDOUT)),
    (EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES, DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE):
        (DATOS, (DATOS, NO_GO, SIN_HOLDOUT)),
    (EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES, DecisionContinuidadML.EVIDENCIA_EXPLORATORIA_DE_MEJORA):
        (DATOS, (DATOS, SIN_HOLDOUT)),
    (EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO, DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE):
        (NO_GO, (NO_GO, SIN_HOLDOUT)),
    (EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO, DecisionContinuidadML.EVIDENCIA_EXPLORATORIA_DE_MEJORA):
        (SIN_HOLDOUT, (SIN_HOLDOUT,)),
}


def _sin_salidas_predictivas(reporte: ReportePrediccionJuego) -> bool:
    return (
        reporte.combinaciones == () and reporte.numeros_fuertes == () and reporte.numeros_debiles == ()
        and dict(reporte.probabilidades) == {} and reporte.nivel_confianza is None
        and not reporte.resultados_observados and not reporte.modelos_entrenados
        and not reporte.predicciones_generadas and not reporte.holdout_consumido
    )


class TestProductoCartesiano:
    def test_cubre_las_seis_combinaciones(self):
        assert len(ESPERADOS) == len(EstadoAutorizacionOperativaML) * len(DecisionContinuidadML) == 6

    @pytest.mark.parametrize("estado_ae41, decision", list(ESPERADOS))
    @pytest.mark.parametrize("juego", ["BALOTO", "BALOTO_REVANCHA"])
    def test_ninguna_combinacion_produce_salidas_predictivas(self, estado_ae41, decision, juego):
        reporte = resolver_prediccion(_autorizacion(estado_ae41, juego), decision)
        estado_esperado, motivos_esperados = ESPERADOS[(estado_ae41, decision)]
        assert reporte.juego_codigo == juego
        assert reporte.estado is estado_esperado
        assert reporte.motivos == motivos_esperados
        assert _sin_salidas_predictivas(reporte)
        assert reporte.disclaimer == DISCLAIMER_PERMANENTE

    def test_estado_actual_datos_insuficientes_mas_no_go(self):
        reporte = resolver_prediccion(
            _autorizacion(EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES),
            DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE,
        )
        assert reporte.estado is DATOS
        assert reporte.motivos == (DATOS, NO_GO, SIN_HOLDOUT)


class TestEstadosCerrados:
    def test_exactamente_cuatro_estados_todos_bloqueados(self):
        assert set(EstadoPrediccionML) == {NUMERACION, DATOS, NO_GO, SIN_HOLDOUT}
        for estado in EstadoPrediccionML:
            assert estado.name.startswith("BLOQUEADO_")
            nombre = estado.name.lower()
            assert "habilitado" not in nombre and "listo" not in nombre and not nombre.endswith("_go")

    def test_constantes_del_contrato_futuro(self):
        assert TOP_COMBINACIONES == 5 and TOP_NUMEROS == 10
        assert DISCLAIMER_PERMANENTE.strip()


def _reporte(**cambios) -> ReportePrediccionJuego:
    base = dict(juego_codigo="BALOTO", estado=DATOS, motivos=(DATOS, NO_GO, SIN_HOLDOUT),
                explicacion="bloqueado", disclaimer=DISCLAIMER_PERMANENTE)
    base.update(cambios)
    return ReportePrediccionJuego(**base)


class TestInvariantesDelReporte:
    def test_reporte_bloqueado_valido(self):
        assert _sin_salidas_predictivas(_reporte())

    @pytest.mark.parametrize("cambios", [
        {"combinaciones": ((1, 2, 3, 4, 5),)},
        {"numeros_fuertes": (7,)},
        {"numeros_debiles": (8,)},
        {"probabilidades": {1: 0.2}},
        {"nivel_confianza": 0.5},
        {"resultados_observados": True},
        {"modelos_entrenados": True},
        {"predicciones_generadas": True},
        {"holdout_consumido": True},
        {"disclaimer": ""},
        {"disclaimer": "   "},
        {"motivos": ()},
        {"motivos": (NO_GO, DATOS)},
        {"estado": NO_GO},
    ])
    def test_reporte_con_datos_confianza_banderas_o_sin_disclaimer_se_rechaza(self, cambios):
        with pytest.raises(ValueError):
            _reporte(**cambios)


class TestJuegoNoAutorizado:
    def test_juego_no_autorizado_se_rechaza(self):
        autorizacion = construir_reporte_bloqueado_por_numeracion_invalida("MILOTO", "sintetico")
        with pytest.raises(PrediccionNoAutorizadaError, match="MILOTO"):
            resolver_prediccion(autorizacion, DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE)

    def test_decision_debe_ser_el_enum_de_ae39(self):
        with pytest.raises(PrediccionNoAutorizadaError):
            resolver_prediccion(
                _autorizacion(EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES),
                "no_go_sin_evidencia_suficiente",
            )
