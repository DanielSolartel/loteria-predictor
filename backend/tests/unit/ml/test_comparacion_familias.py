"""Tests de `application/ml/comparacion_familias.py` -Etapa AE-38.
La mayoria de las pruebas usan una escala sintetica reducida (190
sorteos, 2 bloques externos) para mantener el tiempo de ejecucion
razonable dado el coste de Random Forest; una unica prueba dedicada
confirma la escala real completa (510 sorteos, 18 bloques)."""
from __future__ import annotations

from datetime import date, timedelta
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.comparacion_familias import (
    CANDIDATOS_LOGISTICOS_AE38,
    CANDIDATOS_PREREGISTRADOS_AE38,
    CANDIDATOS_RANDOM_FOREST_AE38,
    evaluar_bloques_externos_ae38,
)


def _historico_sintetico(n_sorteos: int, semilla: int, inicio_numero_sorteo: int = 2081) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    return [
        ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=tuple(sorted(rng.sample(range(1, 44), 5))), superbalota=rng.randint(1, 16),
        )
        for n in range(inicio_numero_sorteo, inicio_numero_sorteo + n_sorteos)
    ]


class TestCandidatosPreregistradosAE38:
    def test_doce_candidatos_totales(self):
        assert len(CANDIDATOS_PREREGISTRADOS_AE38) == 12

    def test_seis_logisticos_seis_random_forest(self):
        assert len(CANDIDATOS_LOGISTICOS_AE38) == 6
        assert len(CANDIDATOS_RANDOM_FOREST_AE38) == 6

    def test_random_forest_maximo_seis(self):
        assert len(CANDIDATOS_RANDOM_FOREST_AE38) <= 6

    def test_identificadores_unicos(self):
        ids = [c.identificador for c in CANDIDATOS_PREREGISTRADOS_AE38]
        assert len(ids) == len(set(ids))

    def test_candidatos_logisticos_identicos_a_ae37(self):
        ids_ae38 = {c.identificador for c in CANDIDATOS_LOGISTICOS_AE38}
        assert ids_ae38 == {
            "completo_C_0_1", "completo_C_1", "completo_C_10",
            "frecuencias_C_0_1", "frecuencias_C_1", "frecuencias_C_10",
        }

    def test_random_forest_random_state_42_via_semilla(self):
        from app.application.ml.modelo import _construir_estimador_base
        for c in CANDIDATOS_RANDOM_FOREST_AE38:
            estimador = _construir_estimador_base(c.familia, c.hiperparametros, semilla=42)
            assert estimador.random_state == 42
            assert estimador.n_jobs == 1

    def test_grid_random_forest_finita_y_documentada(self):
        combinaciones = {(c.hiperparametros["n_estimators"], c.hiperparametros["max_depth"]) for c in CANDIDATOS_RANDOM_FOREST_AE38}
        assert combinaciones == {(100, 5), (200, 10), (300, None)}

    def test_tres_completo_tres_frecuencias_en_random_forest(self):
        completo = [c for c in CANDIDATOS_RANDOM_FOREST_AE38 if c.conjunto_features == "completo"]
        frecuencias = [c for c in CANDIDATOS_RANDOM_FOREST_AE38 if c.conjunto_features == "frecuencias"]
        assert len(completo) == 3
        assert len(frecuencias) == 3


@pytest.fixture(scope="module")
def dataset_pequena_escala():
    hist = _historico_sintetico(190, semilla=41)
    hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
    ds = construir_dataset_binario(hist_ordenado, 1, 43, 5, "BALOTO")
    return ds, hist_ordenado


@pytest.fixture(scope="module")
def resultados_pequena_escala(dataset_pequena_escala):
    ds, hist_ordenado = dataset_pequena_escala
    return evaluar_bloques_externos_ae38(ds, hist_ordenado, semilla=42)


class TestProtocoloPequenaEscala:
    def test_dos_bloques_evaluados(self, resultados_pequena_escala):
        assert len(resultados_pequena_escala) == 2

    def test_doce_resultados_internos_por_bloque(self, resultados_pequena_escala):
        for b in resultados_pequena_escala:
            assert len(b.seleccion.resultados_internos) == 12

    def test_seleccion_puede_ser_de_cualquier_familia(self, resultados_pequena_escala):
        familias_posibles = {"logistica", "random_forest"}
        for b in resultados_pequena_escala:
            assert b.seleccion.configuracion.familia in familias_posibles

    def test_cuatro_baselines_por_bloque(self, resultados_pequena_escala):
        for b in resultados_pequena_escala:
            assert len(b.baselines_externos) == 4

    def test_probabilidades_validas(self, resultados_pequena_escala):
        import math
        for b in resultados_pequena_escala:
            assert math.isfinite(b.resultado_modelo.metricas.log_loss)
            assert math.isfinite(b.resultado_modelo.metricas.brier_score)

    def test_seleccionado_tiene_menor_o_igual_log_loss_interno(self, resultados_pequena_escala):
        for b in resultados_pequena_escala:
            log_losses = [r.metricas.log_loss for r in b.seleccion.resultados_internos]
            seleccionado_ll = next(
                r.metricas.log_loss for r in b.seleccion.resultados_internos
                if r.configuracion.identificador == b.seleccion.configuracion.identificador
            )
            assert seleccionado_ll == min(log_losses)

    def test_reproducibilidad(self, dataset_pequena_escala, resultados_pequena_escala):
        ds, hist_ordenado = dataset_pequena_escala
        r2 = evaluar_bloques_externos_ae38(ds, hist_ordenado, semilla=42)
        assert all(
            a.seleccion.configuracion.identificador == b.seleccion.configuracion.identificador
            and a.resultado_modelo.metricas == b.resultado_modelo.metricas
            for a, b in zip(resultados_pequena_escala, r2)
        )

    def test_bloques_no_se_solapan(self, resultados_pequena_escala):
        rangos = [
            set(range(b.frontera_externa.bloque_externo_inicio, b.frontera_externa.bloque_externo_fin + 1))
            for b in resultados_pequena_escala
        ]
        assert not (rangos[0] & rangos[1])


class TestAntiFugaAE38:
    def test_alterar_bloque_externo_no_cambia_su_propia_seleccion(self, dataset_pequena_escala, resultados_pequena_escala):
        ds, hist_ordenado = dataset_pequena_escala
        bloque0_sorteos = set(range(
            resultados_pequena_escala[0].frontera_externa.bloque_externo_inicio,
            resultados_pequena_escala[0].frontera_externa.bloque_externo_fin + 1,
        ))
        hist_alterado = [
            ResultadoNumerico(numero_sorteo=r.numero_sorteo, fecha=r.fecha, dia_semana="lunes", numeros=(39, 40, 41, 42, 43), superbalota=1)
            if r.numero_sorteo in bloque0_sorteos else r
            for r in hist_ordenado
        ]
        hist_alt_ordenado = validar_y_ordenar_historico(hist_alterado, "BALOTO")
        ds_alt = construir_dataset_binario(hist_alt_ordenado, 1, 43, 5, "BALOTO")
        r_alterado = evaluar_bloques_externos_ae38(ds_alt, hist_alt_ordenado, semilla=42)
        assert resultados_pequena_escala[0].seleccion.configuracion.identificador == r_alterado[0].seleccion.configuracion.identificador

    def test_validacion_interna_siempre_posterior_al_ajuste(self, resultados_pequena_escala):
        for b in resultados_pequena_escala:
            assert b.frontera_interna.validacion_interna_inicio > b.frontera_interna.ajuste_interno_fin

    def test_frontera_interna_nunca_toca_el_bloque_externo(self, resultados_pequena_escala):
        for b in resultados_pequena_escala:
            assert b.frontera_interna.validacion_interna_fin < b.frontera_externa.bloque_externo_inicio


class TestEscalaRealEstructura:
    """Confirma la estructura completa a escala real (510 sorteos,
    18 bloques) usando exclusivamente `construir_bloques_externos`
    -funcion pura, reutilizada sin cambios de AE-37, sin entrenar
    ningun modelo- dado el coste computacional de ejecutar doce
    candidatos (incluidos seis de Random Forest con hasta 300
    arboles) en cada uno de 18 bloques con entrenamiento expansivo.
    El protocolo completo de seleccion/calibracion/evaluacion ya
    queda demostrado a escala reducida en `TestProtocoloPequenaEscala`
    y `TestAntiFugaAE38`, sobre los mismos doce candidatos."""

    def test_dieciocho_bloques_a_escala_real(self):
        from app.application.ml.comparacion_familias import construir_bloques_externos
        hist = _historico_sintetico(510, semilla=2001)
        hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
        ds = construir_dataset_binario(hist_ordenado, 1, 43, 5, "BALOTO")
        assert len(ds.sorteos_objetivo) == 460

        bloques = construir_bloques_externos(ds)
        assert len(bloques) == 18
        assert bloques[0][0] == 2231
        assert bloques[-1][-1] == 2590
