"""Tests de las funciones generalizadas de `application/ml/modelo.py`
-Etapa AE-37. Cubren ablacion de features y parametrizacion de `C`;
las funciones originales de AE-36 en el mismo archivo ya estan
cubiertas por `test_modelo.py` y no se repiten aqui."""
from __future__ import annotations

from datetime import date, timedelta
import math
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.modelo import (
    NOMBRES_FEATURES_FRECUENCIAS,
    construir_pipeline_generalizado,
    entrenar_modelo_calibrado_generalizado,
    entrenar_modelo_generalizado,
    predecir_probabilidades_generalizado,
    predecir_probabilidades_pipeline,
)


def _historico_sintetico(n_sorteos: int, semilla: int = 21) -> list[ResultadoNumerico]:
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


class TestAblacionFeatures:
    def test_conjunto_frecuencias_tiene_cinco_features(self):
        assert len(NOMBRES_FEATURES_FRECUENCIAS) == 5
        assert "sorteos_desde_ultima_aparicion" not in NOMBRES_FEATURES_FRECUENCIAS
        assert "aparecio_en_sorteo_anterior" not in NOMBRES_FEATURES_FRECUENCIAS
        assert "numero_candidato" in NOMBRES_FEATURES_FRECUENCIAS

    def test_pipeline_completo_vs_frecuencias_columnas_distintas(self):
        pipe_completo = construir_pipeline_generalizado(semilla=42, C=1.0, incluir_recencia=True)
        pipe_frecuencias = construir_pipeline_generalizado(semilla=42, C=1.0, incluir_recencia=False)
        assert pipe_completo is not pipe_frecuencias

    def test_entrenamiento_completo_produce_probabilidades_validas(self, dataset_sintetico):
        filas_ajuste = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 150)
        filas_val = tuple(f for f in dataset_sintetico.filas if 150 < f.sorteo_objetivo <= 160)
        pipeline = entrenar_modelo_generalizado(filas_ajuste, semilla=42, C=1.0, incluir_recencia=True)
        probs = predecir_probabilidades_pipeline(pipeline, filas_val, incluir_recencia=True)
        assert len(probs) == len(filas_val)
        assert all(math.isfinite(p) for p in probs)
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_entrenamiento_frecuencias_produce_probabilidades_validas(self, dataset_sintetico):
        filas_ajuste = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 150)
        filas_val = tuple(f for f in dataset_sintetico.filas if 150 < f.sorteo_objetivo <= 160)
        pipeline = entrenar_modelo_generalizado(filas_ajuste, semilla=42, C=10.0, incluir_recencia=False)
        probs = predecir_probabilidades_pipeline(pipeline, filas_val, incluir_recencia=False)
        assert len(probs) == len(filas_val)
        assert all(math.isfinite(p) for p in probs)
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_reproducibilidad_misma_semilla_mismo_c_mismo_conjunto(self, dataset_sintetico):
        filas_ajuste = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 150)
        filas_val = tuple(f for f in dataset_sintetico.filas if 150 < f.sorteo_objetivo <= 160)
        p1 = entrenar_modelo_generalizado(filas_ajuste, semilla=42, C=1.0, incluir_recencia=True)
        p2 = entrenar_modelo_generalizado(filas_ajuste, semilla=42, C=1.0, incluir_recencia=True)
        probs1 = predecir_probabilidades_pipeline(p1, filas_val, incluir_recencia=True)
        probs2 = predecir_probabilidades_pipeline(p2, filas_val, incluir_recencia=True)
        assert probs1 == probs2


class TestModeloCalibradoGeneralizado:
    def test_frontera_precede_al_entrenamiento_completo(self, dataset_sintetico):
        filas_entrenamiento = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 170)
        modelo = entrenar_modelo_calibrado_generalizado(filas_entrenamiento, semilla=42, C=0.1, incluir_recencia=False)
        assert modelo.frontera_base_calibracion < 170

    def test_probabilidades_finitas_y_en_rango(self, dataset_sintetico):
        filas_entrenamiento = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 170)
        filas_test = tuple(f for f in dataset_sintetico.filas if 170 < f.sorteo_objetivo <= 190)
        modelo = entrenar_modelo_calibrado_generalizado(filas_entrenamiento, semilla=42, C=1.0, incluir_recencia=True)
        probs = predecir_probabilidades_generalizado(modelo, filas_test, incluir_recencia=True)
        assert all(math.isfinite(p) for p in probs)
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_hiperparametros_registran_incluir_recencia(self, dataset_sintetico):
        filas_entrenamiento = tuple(f for f in dataset_sintetico.filas if f.sorteo_objetivo <= 170)
        modelo = entrenar_modelo_calibrado_generalizado(filas_entrenamiento, semilla=42, C=10.0, incluir_recencia=False)
        assert modelo.hiperparametros["incluir_recencia"] is False
        assert modelo.hiperparametros["C"] == 10.0


class TestAislamientoDeScikitLearn:
    """Prueba estructural real basada en AST -Etapa AE-37- que
    recorre todos los archivos Python de `application/ml/` y falla
    si cualquier archivo DISTINTO de `modelo.py` importa scikit-learn,
    directa o indirectamente, mediante `ast.Import`/`ast.ImportFrom`
    -nunca una coincidencia de texto superficial. Corrige un defecto
    real: `evaluacion.py` importaba `sklearn` directamente para leer
    `sklearn.__version__`, contradiciendo la propia documentacion de
    AE-36."""

    @staticmethod
    def _importa_sklearn(ruta) -> bool:
        import ast as ast_modulo
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                if any(alias.name == "sklearn" or alias.name.startswith("sklearn.") for alias in nodo.names):
                    return True
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module and (nodo.module == "sklearn" or nodo.module.startswith("sklearn.")):
                    return True
        return False

    def test_solo_modelo_py_importa_sklearn_en_application_ml(self):
        import pathlib
        directorio_ml = pathlib.Path("app/application/ml")
        archivos_con_sklearn = [
            f.name for f in sorted(directorio_ml.glob("*.py"))
            if self._importa_sklearn(f)
        ]
        assert archivos_con_sklearn == ["modelo.py"]
        assert len(archivos_con_sklearn) == 1

    def test_evaluacion_no_importa_sklearn_directamente(self):
        import pathlib
        ruta = pathlib.Path("app/application/ml/evaluacion.py")
        assert not self._importa_sklearn(ruta)

    def test_evaluacion_obtiene_version_sklearn_desde_modelo(self):
        import inspect
        from app.application.ml import evaluacion as modulo_evaluacion
        codigo_fuente = inspect.getsource(modulo_evaluacion)
        assert "from app.application.ml.modelo import" in codigo_fuente
        assert "VERSION_SKLEARN" in codigo_fuente
        assert "import sklearn" not in codigo_fuente

    def test_evaluar_juego_devuelve_la_version_correcta(self):
        from datetime import date, timedelta
        import random
        from app.application.estadisticas.tipos import ResultadoNumerico
        from app.application.ml.evaluacion import evaluar_juego
        from app.application.ml.modelo import VERSION_SKLEARN
        import sklearn as sklearn_real

        rng = random.Random(55)
        base = date(2020, 1, 1)
        hist = [
            ResultadoNumerico(
                numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
                numeros=tuple(sorted(rng.sample(range(1, 44), 5))), superbalota=rng.randint(1, 16),
            )
            for n in range(1, 251)
        ]
        reporte = evaluar_juego(hist, 1, 43, 5, "BALOTO", semilla=42)
        assert reporte.version_sklearn == VERSION_SKLEARN == sklearn_real.__version__
