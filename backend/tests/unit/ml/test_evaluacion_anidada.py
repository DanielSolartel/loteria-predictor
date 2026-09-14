"""Tests de `application/ml/evaluacion_anidada.py` -Etapa AE-37.
Concentra las pruebas anti-fuga interna/externa y de ablacion
adversarial del protocolo anidado completo."""
from __future__ import annotations

from datetime import date, timedelta
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.evaluacion_anidada import (
    CANDIDATOS_PREREGISTRADOS,
    TAMANO_BLOQUE_VALIDACION_EXTERNO,
    TAMANO_ENTRENAMIENTO_INICIAL_EXTERNO,
    TAMANO_VALIDACION_INTERNA,
    BloqueExternoParcialError,
    construir_bloques_externos,
    evaluar_bloques_externos,
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


_N_SORTEOS_REALES = 510


@pytest.fixture(scope="module")
def dataset_escala_real():
    hist = _historico_sintetico(_N_SORTEOS_REALES, semilla=2001)
    hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
    ds = construir_dataset_binario(hist_ordenado, 1, 43, 5, "BALOTO")
    return ds, hist_ordenado


@pytest.fixture(scope="module")
def resultados_escala_real(dataset_escala_real):
    ds, hist_ordenado = dataset_escala_real
    return evaluar_bloques_externos(ds, hist_ordenado, semilla=42)


class TestConstruirBloquesExternos:
    def test_460_elegibles_produce_18_bloques_completos(self, dataset_escala_real):
        ds, _ = dataset_escala_real
        assert len(ds.sorteos_objetivo) == 460
        bloques = construir_bloques_externos(ds)
        assert len(bloques) == 18
        assert all(len(b) == TAMANO_BLOQUE_VALIDACION_EXTERNO for b in bloques)
        assert sum(len(b) for b in bloques) == 360

    def test_bloque_parcial_se_rechaza_explicitamente(self):
        hist = _historico_sintetico(50 + 100 + 105, semilla=5)
        hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
        ds = construir_dataset_binario(hist_ordenado, 1, 43, 5, "BALOTO")
        with pytest.raises(BloqueExternoParcialError):
            construir_bloques_externos(ds)

    def test_historico_insuficiente_para_entrenamiento_inicial_falla(self):
        hist = _historico_sintetico(50 + 50, semilla=5)
        hist_ordenado = validar_y_ordenar_historico(hist, "BALOTO")
        ds = construir_dataset_binario(hist_ordenado, 1, 43, 5, "BALOTO")
        with pytest.raises(ValueError):
            construir_bloques_externos(ds)


class TestSeisCandidatosPreregistrados:
    def test_exactamente_seis_candidatos(self):
        assert len(CANDIDATOS_PREREGISTRADOS) == 6

    def test_tres_completos_tres_frecuencias(self):
        completos = [c for c in CANDIDATOS_PREREGISTRADOS if c.conjunto_features == "completo"]
        frecuencias = [c for c in CANDIDATOS_PREREGISTRADOS if c.conjunto_features == "frecuencias"]
        assert len(completos) == 3
        assert len(frecuencias) == 3

    def test_valores_de_c_correctos_en_cada_conjunto(self):
        cs_completo = sorted(c.C for c in CANDIDATOS_PREREGISTRADOS if c.conjunto_features == "completo")
        cs_frecuencias = sorted(c.C for c in CANDIDATOS_PREREGISTRADOS if c.conjunto_features == "frecuencias")
        assert cs_completo == [0.1, 1.0, 10.0]
        assert cs_frecuencias == [0.1, 1.0, 10.0]

    def test_identificadores_unicos(self):
        ids = [c.identificador for c in CANDIDATOS_PREREGISTRADOS]
        assert len(ids) == len(set(ids))

    def test_identificadores_esperados(self):
        ids = {c.identificador for c in CANDIDATOS_PREREGISTRADOS}
        assert ids == {
            "completo_C_0_1", "completo_C_1", "completo_C_10",
            "frecuencias_C_0_1", "frecuencias_C_1", "frecuencias_C_10",
        }


class TestProtocoloCompletoEscalaReal:
    def test_dieciocho_bloques_evaluados(self, resultados_escala_real):
        assert len(resultados_escala_real) == 18

    def test_reproducibilidad_dos_ejecuciones_identicas(self, dataset_escala_real):
        ds, hist_ordenado = dataset_escala_real
        r1 = evaluar_bloques_externos(ds, hist_ordenado, semilla=42)
        r2 = evaluar_bloques_externos(ds, hist_ordenado, semilla=42)
        assert all(
            a.seleccion.configuracion.identificador == b.seleccion.configuracion.identificador
            and a.resultado_modelo.metricas == b.resultado_modelo.metricas
            and a.diferencia_vs_uniforme == b.diferencia_vs_uniforme
            for a, b in zip(r1, r2)
        )

    def test_fronteras_expansivas_entre_bloques(self, resultados_escala_real):
        inicios = [b.frontera_externa.entrenamiento_externo_inicio for b in resultados_escala_real]
        fines = [b.frontera_externa.entrenamiento_externo_fin for b in resultados_escala_real]
        assert all(i == inicios[0] for i in inicios)
        assert all(fines[i] < fines[i + 1] for i in range(len(fines) - 1))

    def test_bloques_externos_nunca_se_solapan(self, resultados_escala_real):
        rangos = [
            set(range(b.frontera_externa.bloque_externo_inicio, b.frontera_externa.bloque_externo_fin + 1))
            for b in resultados_escala_real
        ]
        for i in range(len(rangos)):
            for j in range(i + 1, len(rangos)):
                assert not (rangos[i] & rangos[j])

    def test_ultimo_bloque_termina_exactamente_en_2590(self, resultados_escala_real):
        assert resultados_escala_real[-1].frontera_externa.bloque_externo_fin == 2590

    def test_cada_bloque_evalua_cuatro_baselines(self, resultados_escala_real):
        for b in resultados_escala_real:
            assert len(b.baselines_externos) == 4


class TestAntiFugaInterna:
    def test_validacion_interna_siempre_posterior_al_ajuste(self, resultados_escala_real):
        for b in resultados_escala_real:
            assert b.frontera_interna.validacion_interna_inicio > b.frontera_interna.ajuste_interno_fin

    def test_frontera_interna_dentro_del_entrenamiento_externo(self, resultados_escala_real):
        for b in resultados_escala_real:
            assert b.frontera_interna.ajuste_interno_inicio >= b.frontera_externa.entrenamiento_externo_inicio
            assert b.frontera_interna.validacion_interna_fin <= b.frontera_externa.entrenamiento_externo_fin

    def test_tamano_validacion_interna_correcto(self, dataset_escala_real):
        ds, hist_ordenado = dataset_escala_real
        resultados = evaluar_bloques_externos(ds, hist_ordenado, semilla=42)
        for b in resultados:
            tamano = b.frontera_interna.validacion_interna_fin - b.frontera_interna.validacion_interna_inicio + 1
            assert tamano == TAMANO_VALIDACION_INTERNA


class TestAntiFugaExterna:
    def test_frontera_externa_nunca_toca_el_bloque_externo_para_seleccion(self, resultados_escala_real):
        for b in resultados_escala_real:
            assert b.frontera_interna.validacion_interna_fin < b.frontera_externa.bloque_externo_inicio

    def test_alterar_etiquetas_de_un_bloque_externo_no_cambia_su_propia_seleccion(self, dataset_escala_real):
        ds, hist_ordenado = dataset_escala_real
        r_original = evaluar_bloques_externos(ds, hist_ordenado, semilla=42)

        bloque_objetivo = r_original[5]
        sorteos_bloque = set(range(
            bloque_objetivo.frontera_externa.bloque_externo_inicio,
            bloque_objetivo.frontera_externa.bloque_externo_fin + 1,
        ))
        hist_alterado = [
            ResultadoNumerico(numero_sorteo=r.numero_sorteo, fecha=r.fecha, dia_semana="lunes", numeros=(39, 40, 41, 42, 43), superbalota=1)
            if r.numero_sorteo in sorteos_bloque else r
            for r in hist_ordenado
        ]
        hist_alt_ordenado = validar_y_ordenar_historico(hist_alterado, "BALOTO")
        ds_alt = construir_dataset_binario(hist_alt_ordenado, 1, 43, 5, "BALOTO")
        r_alterado = evaluar_bloques_externos(ds_alt, hist_alt_ordenado, semilla=42)

        assert r_original[5].seleccion.configuracion.identificador == r_alterado[5].seleccion.configuracion.identificador

    def test_alterar_bloque_externo_no_afecta_bloques_anteriores(self, dataset_escala_real):
        ds, hist_ordenado = dataset_escala_real
        r_original = evaluar_bloques_externos(ds, hist_ordenado, semilla=42)

        bloque_objetivo = r_original[10]
        sorteos_bloque = set(range(
            bloque_objetivo.frontera_externa.bloque_externo_inicio,
            bloque_objetivo.frontera_externa.bloque_externo_fin + 1,
        ))
        hist_alterado = [
            ResultadoNumerico(numero_sorteo=r.numero_sorteo, fecha=r.fecha, dia_semana="lunes", numeros=(1, 2, 3, 4, 5), superbalota=1)
            if r.numero_sorteo in sorteos_bloque else r
            for r in hist_ordenado
        ]
        hist_alt_ordenado = validar_y_ordenar_historico(hist_alterado, "BALOTO")
        ds_alt = construir_dataset_binario(hist_alt_ordenado, 1, 43, 5, "BALOTO")
        r_alterado = evaluar_bloques_externos(ds_alt, hist_alt_ordenado, semilla=42)

        for i in range(10):
            assert r_original[i].seleccion.configuracion.identificador == r_alterado[i].seleccion.configuracion.identificador

    def test_intervalo_consumido_nunca_aparece_en_ningun_bloque(self, resultados_escala_real):
        for b in resultados_escala_real:
            assert b.frontera_externa.bloque_externo_fin <= 2590
            assert b.frontera_externa.entrenamiento_externo_fin <= 2590
            assert b.frontera_interna.validacion_interna_fin <= 2590


class TestSeleccionDeterminista:
    def test_criterio_de_desempate_registrado(self, resultados_escala_real):
        for b in resultados_escala_real:
            assert b.seleccion.criterio_desempate in ("log_loss", "brier_score", "identificador_ascendente")

    def test_seis_resultados_internos_por_bloque(self, resultados_escala_real):
        for b in resultados_escala_real:
            assert len(b.seleccion.resultados_internos) == 6

    def test_seleccionado_tiene_menor_o_igual_log_loss_interno(self, resultados_escala_real):
        for b in resultados_escala_real:
            log_losses = [r.metricas.log_loss for r in b.seleccion.resultados_internos]
            seleccionado_ll = next(
                r.metricas.log_loss for r in b.seleccion.resultados_internos
                if r.configuracion.identificador == b.seleccion.configuracion.identificador
            )
            assert seleccionado_ll == min(log_losses)
