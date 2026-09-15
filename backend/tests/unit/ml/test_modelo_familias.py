"""Tests de las funciones de familia (Logistica/Random Forest) de
`application/ml/modelo.py` -Etapa AE-38."""
from __future__ import annotations

from datetime import date, timedelta
import math
import random
import inspect

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.modelo import (
    FAMILIA_LOGISTICA,
    FAMILIA_RANDOM_FOREST,
    FAMILIAS_VALIDAS,
    construir_pipeline_familia,
    entrenar_modelo_calibrado_familia,
    entrenar_modelo_familia,
    predecir_probabilidades_generalizado,
    predecir_probabilidades_pipeline,
)


def _historico_sintetico(n_sorteos: int, semilla: int = 31) -> list[ResultadoNumerico]:
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
def dataset_sintetico():
    hist = _historico_sintetico(200)
    return construir_dataset_binario(hist, 1, 43, 5, "BALOTO")


class TestFamiliasValidas:
    def test_dos_familias_exactas(self):
        assert FAMILIAS_VALIDAS == (FAMILIA_LOGISTICA, FAMILIA_RANDOM_FOREST)

    def test_familia_desconocida_rechazada_en_entrenamiento(self, dataset_sintetico):
        filas_ajuste = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 150)
        with pytest.raises(ValueError):
            entrenar_modelo_familia(filas_ajuste, "xgboost", {}, semilla=42, incluir_recencia=True)

    def test_familia_desconocida_rechazada_en_pipeline(self):
        with pytest.raises(ValueError):
            construir_pipeline_familia("red_neuronal", {}, semilla=42, incluir_recencia=True)


class TestRandomForestDeterminismo:
    def test_random_state_fijo_en_estimador(self):
        from app.application.ml.modelo import _construir_estimador_base
        estimador = _construir_estimador_base(FAMILIA_RANDOM_FOREST, {"n_estimators": 100, "max_depth": 5}, semilla=42)
        assert estimador.random_state == 42

    def test_n_jobs_uno_en_estimador(self):
        from app.application.ml.modelo import _construir_estimador_base
        estimador = _construir_estimador_base(FAMILIA_RANDOM_FOREST, {"n_estimators": 100, "max_depth": 5}, semilla=42)
        assert estimador.n_jobs == 1

    def test_hiperparametros_aplicados(self):
        from app.application.ml.modelo import _construir_estimador_base
        estimador = _construir_estimador_base(FAMILIA_RANDOM_FOREST, {"n_estimators": 300, "max_depth": None}, semilla=42)
        assert estimador.n_estimators == 300
        assert estimador.max_depth is None


class TestEntrenamientoAmbasFamilias:
    def test_logistica_produce_probabilidades_validas(self, dataset_sintetico):
        filas_ajuste = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 150)
        filas_val = tuple(f for f in dataset_sintetico.filas if 150 < f.sorteo_objetivo <= 160)
        pipeline = entrenar_modelo_familia(filas_ajuste, FAMILIA_LOGISTICA, {"C": 1.0}, semilla=42, incluir_recencia=True)
        probs = predecir_probabilidades_pipeline(pipeline, filas_val, incluir_recencia=True)
        assert all(math.isfinite(p) for p in probs)
        assert all(0.0 < p < 1.0 for p in probs)

    def test_random_forest_produce_probabilidades_validas(self, dataset_sintetico):
        filas_ajuste = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 150)
        filas_val = tuple(f for f in dataset_sintetico.filas if 150 < f.sorteo_objetivo <= 160)
        pipeline = entrenar_modelo_familia(filas_ajuste, FAMILIA_RANDOM_FOREST, {"n_estimators": 100, "max_depth": 5}, semilla=42, incluir_recencia=False)
        probs = predecir_probabilidades_pipeline(pipeline, filas_val, incluir_recencia=False)
        assert all(math.isfinite(p) for p in probs)
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_reproducibilidad_random_forest(self, dataset_sintetico):
        filas_ajuste = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 150)
        filas_val = tuple(f for f in dataset_sintetico.filas if 150 < f.sorteo_objetivo <= 160)
        p1 = entrenar_modelo_familia(filas_ajuste, FAMILIA_RANDOM_FOREST, {"n_estimators": 100, "max_depth": 5}, semilla=42, incluir_recencia=True)
        p2 = entrenar_modelo_familia(filas_ajuste, FAMILIA_RANDOM_FOREST, {"n_estimators": 100, "max_depth": 5}, semilla=42, incluir_recencia=True)
        probs1 = predecir_probabilidades_pipeline(p1, filas_val, incluir_recencia=True)
        probs2 = predecir_probabilidades_pipeline(p2, filas_val, incluir_recencia=True)
        assert probs1 == probs2


class TestCalibracionAmbasFamilias:
    def test_calibracion_logistica(self, dataset_sintetico):
        filas_entrenamiento = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 170)
        filas_test = tuple(f for f in dataset_sintetico.filas if 170 < f.sorteo_objetivo <= 190)
        modelo = entrenar_modelo_calibrado_familia(filas_entrenamiento, FAMILIA_LOGISTICA, {"C": 1.0}, semilla=42, incluir_recencia=True)
        probs = predecir_probabilidades_generalizado(modelo, filas_test, incluir_recencia=True)
        assert all(math.isfinite(p) for p in probs)
        assert all(0.0 <= p <= 1.0 for p in probs)
        assert modelo.frontera_base_calibracion < 170

    def test_calibracion_random_forest(self, dataset_sintetico):
        filas_entrenamiento = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 170)
        filas_test = tuple(f for f in dataset_sintetico.filas if 170 < f.sorteo_objetivo <= 190)
        modelo = entrenar_modelo_calibrado_familia(filas_entrenamiento, FAMILIA_RANDOM_FOREST, {"n_estimators": 100, "max_depth": 5}, semilla=42, incluir_recencia=False)
        probs = predecir_probabilidades_generalizado(modelo, filas_test, incluir_recencia=False)
        assert all(math.isfinite(p) for p in probs)
        assert all(0.0 <= p <= 1.0 for p in probs)
        assert modelo.frontera_base_calibracion < 170

    def test_hiperparametros_registrados_incluyen_familia(self, dataset_sintetico):
        filas_entrenamiento = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 170)
        modelo = entrenar_modelo_calibrado_familia(filas_entrenamiento, FAMILIA_RANDOM_FOREST, {"n_estimators": 200, "max_depth": 10}, semilla=42, incluir_recencia=True)
        assert modelo.hiperparametros["familia"] == FAMILIA_RANDOM_FOREST
        assert modelo.hiperparametros["n_estimators"] == 200
        assert modelo.hiperparametros["max_depth"] == 10


class TestAislamientoScikitLearn:
    def test_comparacion_familias_no_importa_sklearn_directamente(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/comparacion_familias.py")
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
