"""Coherencia del reporte de auditoria -Etapa AE-42 (correccion).

Reproducen dos defectos del parche provisional invalidado (SHA-256
5960e20901844a04d46bae9596dd445dcc249b95082e8e51a2c6140fb85debbd):
(1) el estado global daba prioridad a una autorizacion detectada sobre
el bloqueo por numeracion invalida; (2) no se comprobaba la identidad
ni la coherencia de estado entre el reporte exterior de AE-41 y el
reporte de elegibilidad anidado de AE-40."""
from __future__ import annotations

import pytest

from app.application.ml.auditoria_operativa_bloqueo import (
    ReporteAutorizacionInconsistenteError,
    construir_reporte_auditoria_operativa,
)
from app.application.ml.tipos import (
    EstadoAutorizacionOperativaML,
    EstadoElegibilidadReaperturaML,
    ReporteAutorizacionOperativaML,
    ReporteElegibilidadReaperturaML,
)

INSTANTE = "2026-09-24T00:00:00+00:00"
NO_ELEGIBLE = EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES
ELEGIBLE = EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO
BLOQUEADO = EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES
AUTORIZADO = EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO
NUMERACION = EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA


def _elegibilidad(juego, estado, total, minimo=None, maximo=None):
    return ReporteElegibilidadReaperturaML(
        juego_codigo=juego, estado=estado, proximo_holdout_inicio=2706,
        minimo_sorteos_nuevos_requeridos=100, total_sorteos_nuevos=total,
        numero_sorteo_minimo=minimo, numero_sorteo_maximo=maximo,
        numero_sorteo_objetivo_minimo=2805, numeracion_contigua=True,
    )


def _bloqueado(juego):
    return ReporteAutorizacionOperativaML(
        juego_codigo=juego, estado=BLOQUEADO, motivo="0 sorteos",
        reporte_elegibilidad=_elegibilidad(juego, NO_ELEGIBLE, 0),
    )


def _autorizado(juego):
    return ReporteAutorizacionOperativaML(
        juego_codigo=juego, estado=AUTORIZADO, motivo="100 sorteos",
        reporte_elegibilidad=_elegibilidad(juego, ELEGIBLE, 100, 2706, 2805),
    )


def _numeracion_invalida(juego):
    return ReporteAutorizacionOperativaML(
        juego_codigo=juego, estado=NUMERACION, motivo="hueco", reporte_elegibilidad=None,
    )


class TestPrioridadDelBloqueoPorNumeracionInvalida:
    """Defecto 1: el bloqueo por numeracion invalida debe prevalecer en el
    estado global; la autorizacion del otro juego es solo informativa."""

    def test_baloto_autorizado_revancha_numeracion_invalida(self):
        r = construir_reporte_auditoria_operativa(
            _autorizado("BALOTO"), _numeracion_invalida("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r["estado_global"] == "bloqueado_numeracion_invalida"
        assert r["autorizacion_para_prerregistro_detectada"] is True
        assert r["resultados"]["BALOTO"]["estado"] == "autorizado_para_prerregistro"
        assert r["resultados"]["BALOTO_REVANCHA"]["estado"] == "bloqueado_numeracion_invalida"

    def test_baloto_numeracion_invalida_revancha_autorizado(self):
        r = construir_reporte_auditoria_operativa(
            _numeracion_invalida("BALOTO"), _autorizado("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r["estado_global"] == "bloqueado_numeracion_invalida"
        assert r["autorizacion_para_prerregistro_detectada"] is True
        assert r["resultados"]["BALOTO"]["estado"] == "bloqueado_numeracion_invalida"
        assert r["resultados"]["BALOTO_REVANCHA"]["estado"] == "autorizado_para_prerregistro"


class TestIdentidadDelReporteAnidado:
    """Defecto 2a: el reporte de elegibilidad anidado debe pertenecer al
    mismo juego que el reporte exterior."""

    def test_reporte_baloto_con_elegibilidad_anidada_de_revancha(self):
        exterior = ReporteAutorizacionOperativaML(
            juego_codigo="BALOTO", estado=BLOQUEADO, motivo="x",
            reporte_elegibilidad=_elegibilidad("BALOTO_REVANCHA", NO_ELEGIBLE, 0),
        )
        with pytest.raises(ReporteAutorizacionInconsistenteError, match="anidado corresponde a"):
            construir_reporte_auditoria_operativa(exterior, _bloqueado("BALOTO_REVANCHA"), INSTANTE)

    def test_reporte_revancha_con_elegibilidad_anidada_de_baloto(self):
        exterior = ReporteAutorizacionOperativaML(
            juego_codigo="BALOTO_REVANCHA", estado=BLOQUEADO, motivo="x",
            reporte_elegibilidad=_elegibilidad("BALOTO", NO_ELEGIBLE, 0),
        )
        with pytest.raises(ReporteAutorizacionInconsistenteError, match="anidado corresponde a"):
            construir_reporte_auditoria_operativa(_bloqueado("BALOTO"), exterior, INSTANTE)


class TestCoherenciaDeEstadoConAE40:
    """Defecto 2b: el estado exterior de AE-41 debe coincidir con la
    traduccion del estado de elegibilidad anidado de AE-40."""

    def test_exterior_bloqueado_con_elegibilidad_anidada_elegible(self):
        exterior = ReporteAutorizacionOperativaML(
            juego_codigo="BALOTO", estado=BLOQUEADO, motivo="x",
            reporte_elegibilidad=_elegibilidad("BALOTO", ELEGIBLE, 100, 2706, 2805),
        )
        with pytest.raises(ReporteAutorizacionInconsistenteError, match="incoherente"):
            construir_reporte_auditoria_operativa(exterior, _bloqueado("BALOTO_REVANCHA"), INSTANTE)

    def test_exterior_autorizado_con_elegibilidad_anidada_no_elegible(self):
        exterior = ReporteAutorizacionOperativaML(
            juego_codigo="BALOTO_REVANCHA", estado=AUTORIZADO, motivo="x",
            reporte_elegibilidad=_elegibilidad("BALOTO_REVANCHA", NO_ELEGIBLE, 0),
        )
        with pytest.raises(ReporteAutorizacionInconsistenteError, match="incoherente"):
            construir_reporte_auditoria_operativa(_bloqueado("BALOTO"), exterior, INSTANTE)


class TestDefensaEnProfundidadContraInvariantesEludidas:
    """`ReporteAutorizacionOperativaML.__post_init__` ya impide estas
    combinaciones al construirse normalmente; aqui se fuerzan con
    `object.__setattr__` para comprobar que la auditoria no depende solo
    de esa invariante."""

    def test_exterior_numeracion_invalida_con_reporte_anidado(self):
        exterior = _numeracion_invalida("BALOTO")
        object.__setattr__(exterior, "reporte_elegibilidad", _elegibilidad("BALOTO", NO_ELEGIBLE, 0))
        with pytest.raises(ReporteAutorizacionInconsistenteError, match="incoherente"):
            construir_reporte_auditoria_operativa(exterior, _bloqueado("BALOTO_REVANCHA"), INSTANTE)

    def test_exterior_bloqueado_sin_reporte_anidado(self):
        exterior = _bloqueado("BALOTO_REVANCHA")
        object.__setattr__(exterior, "reporte_elegibilidad", None)
        with pytest.raises(ReporteAutorizacionInconsistenteError, match="sin reporte de elegibilidad anidado"):
            construir_reporte_auditoria_operativa(_bloqueado("BALOTO"), exterior, INSTANTE)
