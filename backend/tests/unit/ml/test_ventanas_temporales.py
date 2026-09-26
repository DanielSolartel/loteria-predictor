"""Tests de `application/ml/ventanas_temporales.py` -Etapa AE-43,
validada. Fronteras exactas de los tramos temporales y coherencia
con las constantes ya validadas de AE-36/37/38/39/40 -una sola
verdad, sin redefiniciones divergentes."""
from __future__ import annotations

import pytest

from app.application.ml.ventanas_temporales import (
    FIN_CONTRATO_AE36,
    FIN_DESARROLLO,
    INICIO_HISTORICO_REAL,
    INICIO_HOLDOUT,
    MAXIMO_CORTE_INFERENCIA_AE43,
    MAXIMO_OBJETIVO_INFERENCIA_AE43,
    TramoTemporalML,
    clasificar_sorteo,
)


class TestFronteras:
    @pytest.mark.parametrize("numero, tramo", [
        (1, TramoTemporalML.ANTERIOR_AL_HISTORICO),
        (2080, TramoTemporalML.ANTERIOR_AL_HISTORICO),
        (2081, TramoTemporalML.DESARROLLO),
        (2589, TramoTemporalML.DESARROLLO),
        (2590, TramoTemporalML.DESARROLLO),
        (2591, TramoTemporalML.CONSUMIDO_AE36),
        (2705, TramoTemporalML.CONSUMIDO_AE36),
        (2706, TramoTemporalML.HOLDOUT),
        (2713, TramoTemporalML.HOLDOUT),
        (99999, TramoTemporalML.HOLDOUT),
    ])
    def test_clasificacion_exacta(self, numero, tramo):
        assert clasificar_sorteo(numero) is tramo

    @pytest.mark.parametrize("valor", [True, False, 2590.0, "2590", None])
    def test_rechaza_valores_no_enteros_y_bool(self, valor):
        with pytest.raises(ValueError):
            clasificar_sorteo(valor)

    def test_tramos_cerrados(self):
        assert {t.name for t in TramoTemporalML} == {
            "ANTERIOR_AL_HISTORICO", "DESARROLLO", "CONSUMIDO_AE36", "HOLDOUT",
        }


class TestTopesDerivados:
    def test_topes_de_inferencia_ae43(self):
        assert MAXIMO_OBJETIVO_INFERENCIA_AE43 == FIN_DESARROLLO == 2590
        assert MAXIMO_CORTE_INFERENCIA_AE43 == 2589

    def test_tramos_contiguos(self):
        assert INICIO_HISTORICO_REAL == 2081
        assert FIN_CONTRATO_AE36 + 1 == INICIO_HOLDOUT


class TestCoherenciaConEtapasValidadas:
    def test_desarrollo_coincide_con_ae37_y_ae38(self):
        from app.application.use_cases import comparar_familias_ml_probabilidad_numeros as ae38
        from app.application.use_cases import evaluar_robustez_ml_probabilidad_numeros as ae37
        assert FIN_DESARROLLO == ae37.CORTE_DESARROLLO_AE37 == ae38.CORTE_DESARROLLO_AE38

    def test_tramo_consumido_coincide_con_ae37_y_ae38(self):
        from app.application.use_cases import comparar_familias_ml_probabilidad_numeros as ae38
        from app.application.use_cases import evaluar_robustez_ml_probabilidad_numeros as ae37
        for modulo in (ae37, ae38):
            assert modulo.HOLDOUT_CONSUMIDO_INICIO == FIN_DESARROLLO + 1
            assert modulo.HOLDOUT_CONSUMIDO_FIN == FIN_CONTRATO_AE36

    def test_contrato_coincide_con_corte_congelado_de_ae36(self):
        from app.application.use_cases.evaluar_baseline_ml_probabilidad_numeros import CORTE_CONTRATO_AE36
        assert FIN_CONTRATO_AE36 == CORTE_CONTRATO_AE36

    def test_inicio_holdout_coincide_con_ae37_ae38_ae39_ae40(self):
        from app.application.ml import incertidumbre, reapertura
        from app.application.use_cases import comparar_familias_ml_probabilidad_numeros as ae38
        from app.application.use_cases import evaluar_robustez_ml_probabilidad_numeros as ae37
        assert INICIO_HOLDOUT == incertidumbre.PROXIMO_HOLDOUT_INICIO == reapertura.PROXIMO_HOLDOUT_INICIO
        assert INICIO_HOLDOUT == ae37.PROXIMO_HOLDOUT_INICIO == ae38.PROXIMO_HOLDOUT_INICIO
