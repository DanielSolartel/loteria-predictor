"""Tests de `application/ml/modelo.py` -Etapa AE-36. Estos tests SI
importan scikit-learn -unico archivo de pruebas de `ml` que lo hace,
mismo criterio de aislamiento que `modelo.py` en el codigo de
produccion."""
from __future__ import annotations

from datetime import date, timedelta
import math
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.modelo import entrenar_modelo_calibrado, predecir_probabilidades
from app.application.ml.particion import construir_particion_walk_forward


def _historico_sintetico(n_sorteos: int, semilla: int = 99) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    return [
        ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=tuple(sorted(rng.sample(range(1, 44), 5))), superbalota=rng.randint(1, 16),
        )
        for n in range(1, n_sorteos + 1)
    ]


@pytest.fixture(scope="module")
def particion_sintetica():
    hist = _historico_sintetico(200)
    ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
    return construir_particion_walk_forward(ds)


class TestEntrenarModeloCalibrado:
    def test_frontera_de_calibracion_precede_al_test(self, particion_sintetica):
        filas_entrenamiento = tuple(
            f for f in particion_sintetica.filas_entrenamiento_por_bloque[-1]
        )
        modelo = entrenar_modelo_calibrado(filas_entrenamiento, semilla=42)
        assert modelo.frontera_base_calibracion < particion_sintetica.limites.test_inicio

    def test_muy_pocos_sorteos_falla_explicitamente(self):
        from app.application.ml.tipos import FilaCandidato

        filas = tuple(
            FilaCandidato(
                codigo_juego="BALOTO", sorteo_objetivo=100, calculado_hasta_sorteo=99,
                numero_candidato=i, etiqueta=1 if i <= 5 else 0, frecuencia_acumulada=0.1,
                frecuencia_ventana_10=0.1, frecuencia_ventana_20=0.1, frecuencia_ventana_50=0.1,
                sorteos_desde_ultima_aparicion=5, aparecio_en_sorteo_anterior=0,
            )
            for i in range(1, 44)
        )
        with pytest.raises(ValueError):
            entrenar_modelo_calibrado(filas, semilla=42)


class TestPredecirProbabilidades:
    def test_todas_finitas_y_en_rango(self, particion_sintetica):
        filas_entrenamiento = particion_sintetica.filas_entrenamiento_por_bloque[-1]
        modelo = entrenar_modelo_calibrado(filas_entrenamiento, semilla=42)
        probs = predecir_probabilidades(modelo, particion_sintetica.filas_test_final)
        assert len(probs) == len(particion_sintetica.filas_test_final)
        assert all(math.isfinite(p) for p in probs)
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_reproducibilidad_misma_semilla_mismo_resultado(self, particion_sintetica):
        filas_entrenamiento = particion_sintetica.filas_entrenamiento_por_bloque[-1]
        modelo_a = entrenar_modelo_calibrado(filas_entrenamiento, semilla=42)
        modelo_b = entrenar_modelo_calibrado(filas_entrenamiento, semilla=42)
        probs_a = predecir_probabilidades(modelo_a, particion_sintetica.filas_test_final)
        probs_b = predecir_probabilidades(modelo_b, particion_sintetica.filas_test_final)
        assert probs_a == probs_b

    def test_el_test_final_no_participo_en_entrenamiento_ni_calibracion(self, particion_sintetica):
        """Verificacion indirecta pero real: el conjunto de
        entrenamiento pasado a `entrenar_modelo_calibrado` nunca
        incluye ningun sorteo del test final -si lo incluyera, esta
        asercion fallaria."""
        filas_entrenamiento = particion_sintetica.filas_entrenamiento_por_bloque[-1]
        sorteos_entrenamiento = {f.sorteo_objetivo for f in filas_entrenamiento}
        sorteos_test = {f.sorteo_objetivo for f in particion_sintetica.filas_test_final}
        assert not (sorteos_entrenamiento & sorteos_test)
