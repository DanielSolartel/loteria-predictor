"""
Modelo: Regresion Logistica calibrada -Etapa AE-36, validada.

Unico modulo de `application/ml` que importa scikit-learn -el resto
del paquete permanece puro. Nunca usa `penalty="l2"` explicito: esa
forma esta deprecada desde scikit-learn 1.8 (confirmado real durante
el gate de compatibilidad de esta etapa) -L2 real se obtiene dejando
`penalty` en su valor por defecto."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import PredefinedSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer

from app.application.ml.tipos import FilaCandidato

SEMILLA_DEFECTO = 42

NOMBRES_FEATURES: tuple[str, ...] = (
    "frecuencia_acumulada",
    "frecuencia_ventana_10",
    "frecuencia_ventana_20",
    "frecuencia_ventana_50",
    "sorteos_desde_ultima_aparicion",
    "aparecio_en_sorteo_anterior",
    "numero_candidato",
)


def _filas_a_matriz(filas: Sequence[FilaCandidato]) -> list[list[float]]:
    """Traduce `FilaCandidato` a filas numericas puras -
    `sorteos_desde_ultima_aparicion=None` (nunca observado) se
    codifica como un valor centinela grande (mayor que cualquier
    atraso real posible), nunca como 0 ni como NaN, para que el
    modelo lo distinga claramente de "aparecio en el sorteo
    inmediatamente anterior" (atraso 0)."""
    centinela = 10_000
    return [
        [
            f.frecuencia_acumulada,
            f.frecuencia_ventana_10,
            f.frecuencia_ventana_20,
            f.frecuencia_ventana_50,
            float(f.sorteos_desde_ultima_aparicion if f.sorteos_desde_ultima_aparicion is not None else centinela),
            float(f.aparecio_en_sorteo_anterior),
            float(f.numero_candidato),
        ]
        for f in filas
    ]


def _etiquetas(filas: Sequence[FilaCandidato]) -> list[int]:
    return [f.etiqueta for f in filas]


def construir_pipeline(semilla: int = SEMILLA_DEFECTO) -> Pipeline:
    """Pipeline base: codifica `numero_candidato` (columna de indice
    6, ver `NOMBRES_FEATURES`) con One-Hot -es una IDENTIDAD
    categorica, no una magnitud continua- y dejа el resto de
    columnas numericas sin transformar; el escalado no es necesario
    para Regresion Logistica con estas features ya acotadas en
    magnitud. `penalty` se deja en su valor por defecto (L2 real,
    ver docstring del modulo). Semilla fija para reproducibilidad
    -`random_state` es la unica fuente de aleatoriedad del solver
    `lbfgs` (inicializacion), determinista en la practica pero fijada
    de todas formas."""
    columnas = ColumnTransformer(
        transformers=[("numero_candidato_onehot", OneHotEncoder(handle_unknown="ignore"), [6])],
        remainder="passthrough",
    )
    return Pipeline([
        ("columnas", columnas),
        ("clf", LogisticRegression(solver="lbfgs", max_iter=2000, random_state=semilla, C=1.0)),
    ])


@dataclass(frozen=True)
class ModeloEntrenado:
    pipeline_calibrado: CalibratedClassifierCV
    semilla: int
    hiperparametros: dict
    frontera_base_calibracion: int  # ultimo sorteo_objetivo usado como base, antes de calibracion


def entrenar_modelo_calibrado(
    filas_entrenamiento_completo: Sequence[FilaCandidato], semilla: int = SEMILLA_DEFECTO,
    proporcion_calibracion: float = 0.2,
) -> ModeloEntrenado:
    """Divide `filas_entrenamiento_completo` en un bloque BASE
    (temprano) y un bloque de CALIBRACION (tardio, siempre posterior
    cronologicamente al base) -por sorteo completo, nunca por fila
    individual- y entrena `CalibratedClassifierCV` con un
    `PredefinedSplit` explicito: el clasificador base se ajusta
    UNICAMENTE con las filas del bloque base, la calibracion
    UNICAMENTE con las filas del bloque de calibracion -nunca la
    estrategia de validacion cruzada aleatoria por defecto."""
    sorteos_ordenados = sorted({f.sorteo_objetivo for f in filas_entrenamiento_completo})
    if len(sorteos_ordenados) < 2:
        raise ValueError("Se necesitan al menos 2 sorteos distintos para separar base y calibracion")

    indice_corte = max(1, round(len(sorteos_ordenados) * (1 - proporcion_calibracion)))
    indice_corte = min(indice_corte, len(sorteos_ordenados) - 1)
    sorteos_base = set(sorteos_ordenados[:indice_corte])
    frontera_base_calibracion = sorteos_ordenados[indice_corte - 1]

    filas_ordenadas = sorted(filas_entrenamiento_completo, key=lambda f: (f.sorteo_objetivo, f.numero_candidato))
    test_fold = [-1 if f.sorteo_objetivo in sorteos_base else 0 for f in filas_ordenadas]
    if 0 not in test_fold:
        raise ValueError("El bloque de calibracion quedo vacio -ajusta proporcion_calibracion o el histórico")

    X = _filas_a_matriz(filas_ordenadas)
    y = _etiquetas(filas_ordenadas)

    division = PredefinedSplit(test_fold)
    base_pipeline = construir_pipeline(semilla)
    hiperparametros = {"solver": "lbfgs", "max_iter": 2000, "C": 1.0, "penalty": "l2 (por defecto)"}

    calibrado = CalibratedClassifierCV(base_pipeline, method="sigmoid", cv=division)
    calibrado.fit(X, y)

    return ModeloEntrenado(
        pipeline_calibrado=calibrado,
        semilla=semilla,
        hiperparametros=hiperparametros,
        frontera_base_calibracion=frontera_base_calibracion,
    )


def predecir_probabilidades(modelo: ModeloEntrenado, filas: Sequence[FilaCandidato]) -> list[float]:
    X = _filas_a_matriz(filas)
    proba = modelo.pipeline_calibrado.predict_proba(X)
    clases = list(modelo.pipeline_calibrado.classes_)
    indice_clase_1 = clases.index(1)
    return [float(fila[indice_clase_1]) for fila in proba]
