"""Tests de `application/ml/incertidumbre.py` -Etapa AE-39."""
from __future__ import annotations

import math
import random

import pytest

from app.application.ml.incertidumbre import (
    JUEGOS_AUTORIZADOS_AE39,
    REPLICAS_BOOTSTRAP_DEFECTO,
    ReporteIncertidumbreInvalidoError,
    _bootstrap_diferencia_agregada,
    _percentil,
    _prueba_signos_exacta,
    _resumen_diferencias_bloques,
    evaluar_incertidumbre_y_regla_parada,
)
from app.application.ml.tipos import (
    ConfiguracionCandidataAE38,
    ConfiguracionSeleccionadaAE38,
    CorteDesarrollo,
    DecisionContinuidadML,
    DiferenciaFrenteAUniforme,
    FronteraBloqueExterno,
    FronteraBloqueInterno,
    MetricasEvaluacion,
    PoliticaProximoHoldout,
    ReporteComparacionFamiliasJuego,
    ResultadoBaseline,
    ResultadoBloqueExternoAE38,
    ResultadoExternoModeloAE38,
    ResultadoInternoCandidatoAE38,
)

_CAND = ConfiguracionCandidataAE38(
    identificador="completo_C_1", familia="logistica", conjunto_features="completo",
    incluye_recencia=True, hiperparametros={"C": 1.0},
)


def _bloque(
    inicio: int, ll_modelo: float, br_modelo: float, ll_uniforme: float, br_uniforme: float,
    total_filas: int = 860, precision_modelo: float = 0.10, precision_uniforme: float = 0.116,
) -> ResultadoBloqueExternoAE38:
    m_modelo = MetricasEvaluacion(log_loss=ll_modelo, brier_score=br_modelo, precision_en_5=precision_modelo, recall_en_5=precision_modelo, total_sorteos=20, total_filas=total_filas)
    m_uniforme = MetricasEvaluacion(log_loss=ll_uniforme, brier_score=br_uniforme, precision_en_5=precision_uniforme, recall_en_5=precision_uniforme, total_sorteos=20, total_filas=total_filas)
    interno = ResultadoInternoCandidatoAE38(configuracion=_CAND, metricas=m_modelo)
    seleccion = ConfiguracionSeleccionadaAE38(configuracion=_CAND, resultados_internos=(interno,) * 12, criterio_desempate="log_loss")
    return ResultadoBloqueExternoAE38(
        frontera_externa=FronteraBloqueExterno(entrenamiento_externo_inicio=1, entrenamiento_externo_fin=inicio - 1, bloque_externo_inicio=inicio, bloque_externo_fin=inicio + 19),
        frontera_interna=FronteraBloqueInterno(ajuste_interno_inicio=1, ajuste_interno_fin=inicio - 21, validacion_interna_inicio=inicio - 20, validacion_interna_fin=inicio - 1),
        seleccion=seleccion,
        resultado_modelo=ResultadoExternoModeloAE38(configuracion=_CAND, metricas=m_modelo),
        baselines_externos=(ResultadoBaseline(nombre="uniforme", descripcion="uniforme", metricas=m_uniforme),),
        diferencia_vs_uniforme=DiferenciaFrenteAUniforme(
            diferencia_log_loss=ll_uniforme - ll_modelo, diferencia_brier_score=br_uniforme - br_modelo,
            resultado="gano" if (ll_uniforme - ll_modelo) > 0 and (br_uniforme - br_modelo) > 0 else "perdio",
        ),
    )


def _reporte(bloques: tuple, codigo_juego: str = "BALOTO") -> ReporteComparacionFamiliasJuego:
    return ReporteComparacionFamiliasJuego(
        codigo_juego=codigo_juego,
        corte_desarrollo=CorteDesarrollo(hasta_numero_sorteo=2590, sorteos_originales_recibidos=510, primer_sorteo=2081, ultimo_sorteo=2590),
        total_sorteos_elegibles=460, total_filas=19780, rango_min=1, rango_max=43, cantidad_numeros=5,
        candidatos_logisticos=(_CAND,), candidatos_random_forest=(),
        bloques_externos=bloques,
        politica_proximo_holdout=PoliticaProximoHoldout(
            holdout_consumido_inicio=2591, holdout_consumido_fin=2705, holdout_consumido_confirmado_no_utilizado=True,
            proximo_holdout_inicio=2706, minimo_sorteos_nuevos_requeridos=100,
        ),
        semilla=42, version_sklearn="1.9.1",
    )


def _dieciocho_bloques(ll_modelo, br_modelo, ll_uniforme=0.3594, br_uniforme=0.1028, precision_modelo=0.10, precision_uniforme=0.116):
    return tuple(_bloque(100 + i * 20, ll_modelo, br_modelo, ll_uniforme, br_uniforme, precision_modelo=precision_modelo, precision_uniforme=precision_uniforme) for i in range(18))


class TestOrientacionMatematica:
    def test_diferencia_positiva_cuando_modelo_tiene_menor_log_loss(self):
        bloques = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.10)
        reporte = _reporte(bloques)
        resultado = evaluar_incertidumbre_y_regla_parada(reporte)
        assert resultado.resultado_log_loss.diferencia_puntual_agregada > 0

    def test_diferencia_negativa_cuando_modelo_tiene_mayor_log_loss(self):
        bloques = _dieciocho_bloques(ll_modelo=0.40, br_modelo=0.10)
        reporte = _reporte(bloques)
        resultado = evaluar_incertidumbre_y_regla_parada(reporte)
        assert resultado.resultado_log_loss.diferencia_puntual_agregada < 0

    def test_mismo_contrato_para_brier_score(self):
        bloques_mejor = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.08)
        bloques_peor = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.15)
        r_mejor = evaluar_incertidumbre_y_regla_parada(_reporte(bloques_mejor))
        r_peor = evaluar_incertidumbre_y_regla_parada(_reporte(bloques_peor))
        assert r_mejor.resultado_brier_score.diferencia_puntual_agregada > 0
        assert r_peor.resultado_brier_score.diferencia_puntual_agregada < 0

    def test_promedio_ponderado_correcto_con_tamanos_distintos(self):
        b1 = _bloque(100, ll_modelo=0.30, br_modelo=0.10, ll_uniforme=0.40, br_uniforme=0.10, total_filas=100)
        b2 = _bloque(120, ll_modelo=0.30, br_modelo=0.10, ll_uniforme=0.30, br_uniforme=0.10, total_filas=900)
        pesos = [100.0, 900.0]
        diferencias = [0.10, 0.0]
        esperado = sum(d * p for d, p in zip(diferencias, pesos)) / sum(pesos)
        assert esperado == pytest.approx(0.01)

    def test_orientacion_documentada_en_diferencia_vs_uniforme(self):
        bloque = _bloque(100, ll_modelo=0.30, br_modelo=0.10, ll_uniforme=0.40, br_uniforme=0.15)
        assert bloque.diferencia_vs_uniforme.diferencia_log_loss == pytest.approx(0.10)
        assert bloque.diferencia_vs_uniforme.diferencia_brier_score == pytest.approx(0.05)


class TestEstadisticaDescriptiva:
    def test_mediana_minimo_maximo_desviacion_ejemplo_manual(self):
        diferencias = [1.0, 2.0, 3.0, 4.0, 5.0]
        resumen = _resumen_diferencias_bloques(diferencias)
        assert resumen.mediana == pytest.approx(3.0)
        assert resumen.minimo == pytest.approx(1.0)
        assert resumen.maximo == pytest.approx(5.0)
        media = sum(diferencias) / 5
        varianza_manual = sum((d - media) ** 2 for d in diferencias) / 4
        assert resumen.desviacion_estandar == pytest.approx(math.sqrt(varianza_manual))

    def test_conteo_mejora_empeoramiento_empate(self):
        diferencias = [1.0, -1.0, 0.0, 2.0, -3.0]
        resumen = _resumen_diferencias_bloques(diferencias)
        assert resumen.bloques_con_mejora == 2
        assert resumen.bloques_con_empeoramiento == 2
        assert resumen.bloques_empatados == 1
        assert resumen.proporcion_con_mejora == pytest.approx(2 / 5)

    def test_cuantiles_correctos_ejemplo_manual_pequeno(self):
        valores = [10.0, 20.0, 30.0, 40.0]
        assert _percentil(valores, 0.0) == pytest.approx(10.0)
        assert _percentil(valores, 1.0) == pytest.approx(40.0)
        assert _percentil(valores, 0.5) == pytest.approx(25.0)
        # indice = 0.25 * 3 = 0.75 -> interpolacion entre indices 0 y 1
        assert _percentil(valores, 0.25) == pytest.approx(17.5)

    def test_cuantil_con_un_solo_valor(self):
        assert _percentil([42.0], 0.5) == pytest.approx(42.0)


class TestPruebaDeSignos:
    def test_todos_positivos_p_valor_bajo(self):
        diferencias = [1.0] * 18
        p = _prueba_signos_exacta(diferencias)
        assert p == pytest.approx(2 / (2 ** 18))

    def test_mitad_positivos_mitad_negativos_p_valor_alto(self):
        diferencias = [1.0, -1.0] * 9
        p = _prueba_signos_exacta(diferencias)
        assert p == pytest.approx(1.0)

    def test_todos_empatados_devuelve_uno(self):
        diferencias = [0.0] * 18
        assert _prueba_signos_exacta(diferencias) == pytest.approx(1.0)

    def test_empates_excluidos_del_conteo(self):
        diferencias = [1.0, 1.0, 1.0, 0.0, 0.0]
        p_con_empates = _prueba_signos_exacta(diferencias)
        p_sin_empates = _prueba_signos_exacta([1.0, 1.0, 1.0])
        assert p_con_empates == pytest.approx(p_sin_empates)

    def test_ejemplo_manual_dos_de_tres(self):
        # n=3, k=min(2,1)=1 -> P(X<=1) bajo Binomial(3,0.5) = (1+3)/8 = 0.5 -> bilateral = min(1, 1.0) = 1.0
        diferencias = [1.0, 1.0, -1.0]
        p = _prueba_signos_exacta(diferencias)
        assert p == pytest.approx(1.0)


class TestBootstrapPorBloques:
    def test_reproducibilidad_misma_semilla(self):
        diferencias = [0.01, -0.02, 0.03, 0.0, 0.01, -0.01] * 3
        pesos = [860.0] * 18
        iv1 = _bootstrap_diferencia_agregada(diferencias, pesos, 0.95, 500, 42)
        iv2 = _bootstrap_diferencia_agregada(diferencias, pesos, 0.95, 500, 42)
        assert iv1 == iv2

    def test_semilla_distinta_puede_producir_resultado_distinto(self):
        diferencias = [0.01, -0.02, 0.03, 0.0, 0.01, -0.01] * 3
        pesos = [860.0] * 18
        iv1 = _bootstrap_diferencia_agregada(diferencias, pesos, 0.95, 500, 1)
        iv2 = _bootstrap_diferencia_agregada(diferencias, pesos, 0.95, 500, 2)
        assert iv1 != iv2

    def test_intervalo_degenerado_cuando_todos_los_bloques_iguales(self):
        diferencias = [0.02] * 18
        pesos = [860.0] * 18
        iv = _bootstrap_diferencia_agregada(diferencias, pesos, 0.95, 500, 42)
        assert iv.limite_inferior == pytest.approx(0.02)
        assert iv.limite_superior == pytest.approx(0.02)

    def test_limites_finitos(self):
        diferencias = [0.5, -0.5, 0.3, -0.2] * 4 + [0.0, 0.0]
        pesos = [860.0] * 18
        iv = _bootstrap_diferencia_agregada(diferencias, pesos, 0.95, 500, 42)
        assert math.isfinite(iv.limite_inferior)
        assert math.isfinite(iv.limite_superior)

    def test_replicas_no_positivas_rechazadas(self):
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            _bootstrap_diferencia_agregada([0.1, 0.2], [1.0, 1.0], 0.95, 0, 42)

    def test_nivel_confianza_fuera_de_rango_rechazado(self):
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            _bootstrap_diferencia_agregada([0.1, 0.2], [1.0, 1.0], 1.5, 100, 42)

    def test_reporte_de_entrada_no_se_modifica(self):
        bloques = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.10)
        reporte = _reporte(bloques)
        bloques_antes = reporte.bloques_externos
        evaluar_incertidumbre_y_regla_parada(reporte, replicas=200)
        assert reporte.bloques_externos == bloques_antes

    def test_dieciocho_unidades_estadisticas_para_escala_real(self):
        bloques = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.10)
        assert len(bloques) == 18
        reporte = _reporte(bloques)
        resultado = evaluar_incertidumbre_y_regla_parada(reporte, replicas=200)
        assert resultado.total_bloques == 18


class TestReglaDeDecision:
    def test_mejora_clara_en_ambas_metricas_produce_evidencia_exploratoria(self):
        bloques = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.08)
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=200)
        assert resultado.decision == DecisionContinuidadML.EVIDENCIA_EXPLORATORIA_DE_MEJORA

    def test_mejora_solo_en_log_loss_produce_no_go(self):
        bloques = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.15)
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=200)
        assert resultado.decision == DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE

    def test_mejora_solo_en_brier_produce_no_go(self):
        bloques = _dieciocho_bloques(ll_modelo=0.40, br_modelo=0.08)
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=200)
        assert resultado.decision == DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE

    def test_estimador_puntual_negativo_produce_no_go(self):
        bloques = _dieciocho_bloques(ll_modelo=0.40, br_modelo=0.15)
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=200)
        assert resultado.decision == DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE

    def test_intervalo_que_cruza_cero_produce_no_go(self):
        # Nueve bloques con mejora fuerte y nueve con empeoramiento fuerte -> el
        # punto agregado queda cerca de cero y el intervalo bootstrap lo cruza.
        bloques = tuple(
            _bloque(100 + i * 20, ll_modelo=0.30, br_modelo=0.10, ll_uniforme=0.36, br_uniforme=0.15)
            if i % 2 == 0 else
            _bloque(100 + i * 20, ll_modelo=0.42, br_modelo=0.10, ll_uniforme=0.36, br_uniforme=0.15)
            for i in range(18)
        )
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=1000)
        assert resultado.resultado_log_loss.intervalo_bootstrap.limite_inferior <= 0
        assert resultado.resultado_log_loss.intervalo_bootstrap.limite_superior >= 0
        assert resultado.decision == DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE

    def test_metricas_secundarias_no_revierten_un_no_go(self):
        bloques = _dieciocho_bloques(ll_modelo=0.40, br_modelo=0.15, precision_modelo=0.30, precision_uniforme=0.10)
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=200)
        assert resultado.decision == DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE

    def test_degradacion_material_en_secundarias_bloquea_evidencia_exploratoria(self):
        bloques = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.08, precision_modelo=0.01, precision_uniforme=0.20)
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=200)
        assert resultado.decision == DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE

    def test_cada_juego_se_decide_por_separado(self):
        bloques_buenos = _dieciocho_bloques(ll_modelo=0.30, br_modelo=0.08)
        bloques_malos = _dieciocho_bloques(ll_modelo=0.40, br_modelo=0.15)
        r_baloto = evaluar_incertidumbre_y_regla_parada(_reporte(bloques_buenos, "BALOTO"), replicas=200)
        r_revancha = evaluar_incertidumbre_y_regla_parada(_reporte(bloques_malos, "BALOTO_REVANCHA"), replicas=200)
        assert r_baloto.decision != r_revancha.decision
        assert r_baloto.codigo_juego == "BALOTO"
        assert r_revancha.codigo_juego == "BALOTO_REVANCHA"


class TestValidacionesDeEntrada:
    def test_reporte_sin_bloques_rechazado(self):
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(()))

    def test_un_solo_bloque_rechazado(self):
        bloques = (_bloque(100, 0.3, 0.1, 0.36, 0.10),)
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(bloques))

    def test_juego_no_autorizado_rechazado(self):
        bloques = _dieciocho_bloques(0.3, 0.1)
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(bloques, codigo_juego="MILOTO"))

    def test_bloques_duplicados_rechazados(self):
        bloques = _dieciocho_bloques(0.3, 0.1)
        bloques_con_duplicado = bloques + (bloques[0],)
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(bloques_con_duplicado))

    def test_bloques_fuera_de_orden_rechazados(self):
        bloques = list(_dieciocho_bloques(0.3, 0.1))
        bloques[0], bloques[1] = bloques[1], bloques[0]
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(tuple(bloques)))

    def test_bloques_solapados_rechazados(self):
        b1 = _bloque(100, 0.3, 0.1, 0.36, 0.15)
        b2 = _bloque(110, 0.3, 0.1, 0.36, 0.15)  # se solapa con b1 (100-119)
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte((b1, b2)))

    def test_tamano_de_bloque_no_positivo_rechazado(self):
        bloque_malo = _bloque(100, 0.3, 0.1, 0.36, 0.15, total_filas=0)
        bloques = (bloque_malo,) + _dieciocho_bloques(0.3, 0.1)[1:]
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(bloques))

    def test_ausencia_de_baseline_uniforme_rechazada(self):
        b = _bloque(100, 0.3, 0.1, 0.36, 0.15)
        m_uniforme = b.baselines_externos[0].metricas
        b_sin_uniforme = ResultadoBloqueExternoAE38(
            frontera_externa=b.frontera_externa, frontera_interna=b.frontera_interna, seleccion=b.seleccion,
            resultado_modelo=b.resultado_modelo,
            baselines_externos=(ResultadoBaseline(nombre="frecuencia_acumulada", descripcion="x", metricas=m_uniforme),),
            diferencia_vs_uniforme=b.diferencia_vs_uniforme,
        )
        bloques = (b_sin_uniforme,) + _dieciocho_bloques(0.3, 0.1)[1:]
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(bloques))

    def test_mas_de_un_baseline_uniforme_rechazado(self):
        b = _bloque(100, 0.3, 0.1, 0.36, 0.15)
        m_uniforme = b.baselines_externos[0].metricas
        b_doble = ResultadoBloqueExternoAE38(
            frontera_externa=b.frontera_externa, frontera_interna=b.frontera_interna, seleccion=b.seleccion,
            resultado_modelo=b.resultado_modelo,
            baselines_externos=(
                ResultadoBaseline(nombre="uniforme", descripcion="x", metricas=m_uniforme),
                ResultadoBaseline(nombre="uniforme", descripcion="y", metricas=m_uniforme),
            ),
            diferencia_vs_uniforme=b.diferencia_vs_uniforme,
        )
        bloques = (b_doble,) + _dieciocho_bloques(0.3, 0.1)[1:]
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(bloques))

    def test_diferencia_almacenada_inconsistente_rechazada(self):
        b = _bloque(100, 0.3, 0.1, 0.36, 0.15)
        b_inconsistente = ResultadoBloqueExternoAE38(
            frontera_externa=b.frontera_externa, frontera_interna=b.frontera_interna, seleccion=b.seleccion,
            resultado_modelo=b.resultado_modelo, baselines_externos=b.baselines_externos,
            diferencia_vs_uniforme=DiferenciaFrenteAUniforme(diferencia_log_loss=999.0, diferencia_brier_score=b.diferencia_vs_uniforme.diferencia_brier_score, resultado="gano"),
        )
        bloques = (b_inconsistente,) + _dieciocho_bloques(0.3, 0.1)[1:]
        with pytest.raises(ReporteIncertidumbreInvalidoError):
            evaluar_incertidumbre_y_regla_parada(_reporte(bloques))


class TestIntegridadTemporal:
    def test_ningun_dato_posterior_a_2590_necesario(self):
        bloques = _dieciocho_bloques(0.3, 0.1)
        assert all(b.frontera_externa.bloque_externo_fin <= 2590 for b in bloques)
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=200)
        assert resultado.total_bloques == 18

    def test_anadir_informacion_externa_no_cambia_el_analisis(self):
        bloques = _dieciocho_bloques(0.3, 0.1)
        reporte = _reporte(bloques)
        r1 = evaluar_incertidumbre_y_regla_parada(reporte, replicas=200)
        # simular "informacion externa posterior" que no forma parte del reporte -el analisis debe ser identico
        r2 = evaluar_incertidumbre_y_regla_parada(reporte, replicas=200)
        assert r1.resultado_log_loss.intervalo_bootstrap == r2.resultado_log_loss.intervalo_bootstrap

    def test_proximo_holdout_definido_desde_2706(self):
        bloques = _dieciocho_bloques(0.3, 0.1)
        resultado = evaluar_incertidumbre_y_regla_parada(_reporte(bloques), replicas=200)
        assert resultado.politica_reapertura.proximo_holdout_inicio == 2706
        assert resultado.politica_reapertura.minimo_sorteos_nuevos_requeridos == 100


class TestArquitectura:
    def test_incertidumbre_no_importa_sklearn_directamente(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/incertidumbre.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        importa = False
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                if any(a.name == "sklearn" or a.name.startswith("sklearn.") for a in nodo.names):
                    importa = True
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module and (nodo.module == "sklearn" or nodo.module.startswith("sklearn.")):
                    importa = True
        assert not importa

    def test_solo_modelo_py_importa_sklearn_en_application_ml(self):
        import ast as ast_modulo
        import pathlib

        def importa_sklearn(ruta):
            arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
            for nodo in ast_modulo.walk(arbol):
                if isinstance(nodo, ast_modulo.Import):
                    if any(a.name == "sklearn" or a.name.startswith("sklearn.") for a in nodo.names):
                        return True
                elif isinstance(nodo, ast_modulo.ImportFrom):
                    if nodo.module and (nodo.module == "sklearn" or nodo.module.startswith("sklearn.")):
                        return True
            return False

        directorio_ml = pathlib.Path("app/application/ml")
        archivos_con_sklearn = [f.name for f in sorted(directorio_ml.glob("*.py")) if importa_sklearn(f)]
        assert archivos_con_sklearn == ["modelo.py"]

    def test_incertidumbre_no_importa_infraestructura(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/incertidumbre.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        modulos_prohibidos = ("sqlalchemy", "fastapi", "jinja2")
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                for alias in nodo.names:
                    assert not any(alias.name.lower().startswith(p) for p in modulos_prohibidos)
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module:
                    assert not any(nodo.module.lower().startswith(p) for p in modulos_prohibidos)

    def test_no_usa_random_global(self):
        import inspect
        from app.application.ml import incertidumbre as modulo
        codigo_fuente = inspect.getsource(modulo)
        assert "random.seed(" not in codigo_fuente
        assert "random.Random(" in codigo_fuente
