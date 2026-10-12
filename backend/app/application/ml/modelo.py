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


# =====================================================================
# Etapa AE-37, validada -version generalizada y parametrizable de
# las funciones anteriores, para soportar ablacion de features
# (conjuntos `completo`/`frecuencias`) y busqueda de `C` sobre
# validacion interna. Las funciones de AE-36 anteriores en este
# archivo permanecen sin cambios y siguen siendo las que usa el caso
# de uso original de AE-36.
# =====================================================================

NOMBRES_FEATURES_FRECUENCIAS: tuple[str, ...] = (
    "frecuencia_acumulada",
    "frecuencia_ventana_10",
    "frecuencia_ventana_20",
    "frecuencia_ventana_50",
    "numero_candidato",
)
"""Conjunto `frecuencias` de AE-37: excluye unicamente las dos
features de recencia (`sorteos_desde_ultima_aparicion`,
`aparecio_en_sorteo_anterior`) del conjunto `completo` de AE-36 -
mismas cuatro frecuencias mas la identidad del candidato."""


def _filas_a_matriz_generalizada(filas: Sequence[FilaCandidato], incluir_recencia: bool) -> list[list[float]]:
    """Igual que `_filas_a_matriz`, pero omite las dos columnas de
    recencia cuando `incluir_recencia` es `False` -nunca cambia el
    orden relativo de las columnas que si se incluyen."""
    if incluir_recencia:
        return _filas_a_matriz(filas)
    return [[f.frecuencia_acumulada, f.frecuencia_ventana_10, f.frecuencia_ventana_20,
              f.frecuencia_ventana_50, float(f.numero_candidato)] for f in filas]


def construir_pipeline_generalizado(semilla: int, C: float, incluir_recencia: bool) -> Pipeline:
    """Igual que `construir_pipeline`, pero con `C` parametrizado y
    con el indice de la columna one-hot de `numero_candidato`
    ajustado segun `incluir_recencia` -indice 6 en el conjunto
    `completo` (7 columnas), indice 4 en el conjunto `frecuencias` (5
    columnas, ver `NOMBRES_FEATURES_FRECUENCIAS`)."""
    indice_candidato = 6 if incluir_recencia else 4
    columnas = ColumnTransformer(
        transformers=[("numero_candidato_onehot", OneHotEncoder(handle_unknown="ignore"), [indice_candidato])],
        remainder="passthrough",
    )
    return Pipeline([
        ("columnas", columnas),
        ("clf", LogisticRegression(solver="lbfgs", max_iter=2000, random_state=semilla, C=C)),
    ])


def entrenar_modelo_generalizado(
    filas_ajuste: Sequence[FilaCandidato], semilla: int, C: float, incluir_recencia: bool,
) -> Pipeline:
    """Ajusta un pipeline NO calibrado directamente sobre
    `filas_ajuste` -usado por la seleccion interna de AE-37, donde
    cada candidato se entrena una vez por iteracion sobre el ajuste
    interno y se compara en la validacion interna sin calibrar
    todavia; la calibracion solo se aplica a la configuracion ya
    seleccionada, sobre el entrenamiento externo completo (ver
    `entrenar_modelo_calibrado_generalizado`)."""
    X = _filas_a_matriz_generalizada(filas_ajuste, incluir_recencia)
    y = _etiquetas(filas_ajuste)
    pipeline = construir_pipeline_generalizado(semilla, C, incluir_recencia)
    pipeline.fit(X, y)
    return pipeline


def predecir_probabilidades_pipeline(
    pipeline: Pipeline, filas: Sequence[FilaCandidato], incluir_recencia: bool,
) -> list[float]:
    X = _filas_a_matriz_generalizada(filas, incluir_recencia)
    proba = pipeline.predict_proba(X)
    clases = list(pipeline.classes_)
    indice_clase_1 = clases.index(1)
    return [float(fila[indice_clase_1]) for fila in proba]


def entrenar_modelo_calibrado_generalizado(
    filas_entrenamiento_completo: Sequence[FilaCandidato], semilla: int, C: float, incluir_recencia: bool,
    proporcion_calibracion: float = 0.2,
) -> ModeloEntrenado:
    """Igual disciplina exacta que `entrenar_modelo_calibrado` de
    AE-36 (bloque base/calibracion por sorteo completo,
    `PredefinedSplit` explicito, nunca CV aleatoria), pero con `C` e
    `incluir_recencia` parametrizados -usado para reentrenar la
    configuracion ya seleccionada sobre todo el entrenamiento externo
    de un bloque, antes de evaluarla una unica vez en el bloque
    externo."""
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

    X = _filas_a_matriz_generalizada(filas_ordenadas, incluir_recencia)
    y = _etiquetas(filas_ordenadas)

    division = PredefinedSplit(test_fold)
    base_pipeline = construir_pipeline_generalizado(semilla, C, incluir_recencia)
    hiperparametros = {"solver": "lbfgs", "max_iter": 2000, "C": C, "penalty": "l2 (por defecto)", "incluir_recencia": incluir_recencia}

    calibrado = CalibratedClassifierCV(base_pipeline, method="sigmoid", cv=division)
    calibrado.fit(X, y)

    return ModeloEntrenado(
        pipeline_calibrado=calibrado,
        semilla=semilla,
        hiperparametros=hiperparametros,
        frontera_base_calibracion=frontera_base_calibracion,
    )


def predecir_probabilidades_generalizado(
    modelo: ModeloEntrenado, filas: Sequence[FilaCandidato], incluir_recencia: bool,
) -> list[float]:
    X = _filas_a_matriz_generalizada(filas, incluir_recencia)
    proba = modelo.pipeline_calibrado.predict_proba(X)
    clases = list(modelo.pipeline_calibrado.classes_)
    indice_clase_1 = clases.index(1)
    return [float(fila[indice_clase_1]) for fila in proba]


import sklearn as _sklearn_modulo

VERSION_SKLEARN: str = _sklearn_modulo.__version__
"""Version real de scikit-learn instalada -expuesta aqui para que
ningun otro modulo de `application/ml` ni ningun caso de uso necesite
importar `sklearn` directamente solo para leer la version; `modelo.py`
sigue siendo el unico archivo del paquete con una dependencia real de
scikit-learn. Correccion arquitectonica de mantenimiento heredada de
AE-36 (Etapa AE-37): `evaluacion.py` importaba `sklearn` directamente
solo para esto mismo -contradiciendo la propia documentacion de
AE-36 ("modelo.py es el UNICO archivo del paquete que importa
scikit-learn")- y ahora importa `VERSION_SKLEARN` desde aqui en su
lugar, sin cambiar el valor devuelto ni el comportamiento de AE-36."""


# =====================================================================
# Etapa AE-38, validada -comparacion exploratoria prerregistrada
# entre Regresion Logistica y Random Forest, bajo el mismo protocolo
# de evaluacion temporal anidada que AE-37. Funciones agnosticas de
# familia: reciben un identificador de familia y un diccionario de
# hiperparametros, nunca hardcodean el tipo de modelo. Las funciones
# de AE-36/AE-37 anteriores en este archivo permanecen sin cambios.
# =====================================================================

from sklearn.ensemble import RandomForestClassifier

FAMILIA_LOGISTICA = "logistica"
FAMILIA_RANDOM_FOREST = "random_forest"
FAMILIAS_VALIDAS = (FAMILIA_LOGISTICA, FAMILIA_RANDOM_FOREST)


def _construir_estimador_base(familia: str, hiperparametros: dict, semilla: int):
    """Construye el estimador base (sin calibrar, sin columnas) para
    la familia indicada -unico lugar de todo `application/ml` donde
    se elige entre `LogisticRegression` y `RandomForestClassifier`.
    Rechaza explicitamente cualquier familia desconocida, nunca cae
    en un valor por defecto silencioso."""
    if familia == FAMILIA_LOGISTICA:
        return LogisticRegression(
            solver="lbfgs", max_iter=2000, random_state=semilla, C=hiperparametros["C"],
        )
    if familia == FAMILIA_RANDOM_FOREST:
        return RandomForestClassifier(
            n_estimators=hiperparametros["n_estimators"],
            max_depth=hiperparametros["max_depth"],
            random_state=semilla,
            n_jobs=1,
        )
    raise ValueError(f"Familia desconocida: {familia!r} -se esperaba una de {FAMILIAS_VALIDAS}")


def construir_pipeline_familia(familia: str, hiperparametros: dict, semilla: int, incluir_recencia: bool) -> Pipeline:
    """Igual disciplina de columnas que `construir_pipeline_generalizado`
    -identidad one-hot del candidato en el indice correcto segun
    `incluir_recencia`, el resto de columnas sin transformar- pero con
    el estimador base elegido por familia, nunca hardcodeado."""
    indice_candidato = 6 if incluir_recencia else 4
    columnas = ColumnTransformer(
        transformers=[("numero_candidato_onehot", OneHotEncoder(handle_unknown="ignore"), [indice_candidato])],
        remainder="passthrough",
    )
    estimador = _construir_estimador_base(familia, hiperparametros, semilla)
    return Pipeline([("columnas", columnas), ("clf", estimador)])


def entrenar_modelo_familia(
    filas_ajuste: Sequence[FilaCandidato], familia: str, hiperparametros: dict, semilla: int, incluir_recencia: bool,
) -> Pipeline:
    """Ajusta un pipeline NO calibrado directamente sobre
    `filas_ajuste` -usado por la seleccion interna de AE-38, misma
    disciplina exacta que `entrenar_modelo_generalizado` de AE-37,
    generalizada por familia."""
    X = _filas_a_matriz_generalizada(filas_ajuste, incluir_recencia)
    y = _etiquetas(filas_ajuste)
    pipeline = construir_pipeline_familia(familia, hiperparametros, semilla, incluir_recencia)
    pipeline.fit(X, y)
    return pipeline


def entrenar_modelo_calibrado_familia(
    filas_entrenamiento_completo: Sequence[FilaCandidato], familia: str, hiperparametros: dict, semilla: int,
    incluir_recencia: bool, proporcion_calibracion: float = 0.2,
) -> ModeloEntrenado:
    """Misma disciplina exacta de calibracion cronologica que
    `entrenar_modelo_calibrado_generalizado` de AE-37 (bloque
    base/calibracion por sorteo completo, `PredefinedSplit` explicito,
    nunca CV aleatoria) -generalizada por familia, para que la
    comparacion entre Regresion Logistica y Random Forest sea
    metodologicamente equivalente."""
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

    X = _filas_a_matriz_generalizada(filas_ordenadas, incluir_recencia)
    y = _etiquetas(filas_ordenadas)

    division = PredefinedSplit(test_fold)
    base_pipeline = construir_pipeline_familia(familia, hiperparametros, semilla, incluir_recencia)
    hiperparametros_registrados = dict(hiperparametros)
    hiperparametros_registrados["familia"] = familia
    hiperparametros_registrados["incluir_recencia"] = incluir_recencia

    calibrado = CalibratedClassifierCV(base_pipeline, method="sigmoid", cv=division)
    calibrado.fit(X, y)

    return ModeloEntrenado(
        pipeline_calibrado=calibrado,
        semilla=semilla,
        hiperparametros=hiperparametros_registrados,
        frontera_base_calibracion=frontera_base_calibracion,
    )


# =====================================================================
# Producto 4 -laboratorio de modelos. Construccion de los estimadores de
# scikit-learn de las familias nuevas (este sigue siendo el unico modulo de
# `application/ml` que importa scikit-learn). Las recetas, la evaluacion y
# las transformaciones de probabilidad viven en `laboratorio_modelos.py`.
# Las funciones anteriores de este archivo no cambian.
# =====================================================================

def transformador_laboratorio(familia: str) -> ColumnTransformer:
    """Columna 0 = identidad categorica (candidato o par); 1..7 numericas.
    Lineal: OneHot (ignora categorias no vistas) + StandardScaler ajustado
    solo con las filas de ajuste. Arboles: OrdinalEncoder (no vista = ausente)
    y categoria nativa del boosting."""
    from sklearn.preprocessing import OrdinalEncoder, StandardScaler

    if familia == "lineal":
        return ColumnTransformer([("identidad", OneHotEncoder(handle_unknown="ignore"), [0]),
                                  ("numericas", StandardScaler(), list(range(1, 8)))])
    return ColumnTransformer([("identidad", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=float("nan"),
                                                           encoded_missing_value=float("nan")), [0])],
                             remainder="passthrough")


BOSQUES_DEL_LABORATORIO = ("random_forest_clasificador", "extra_trees_clasificador", "random_forest_poisson",
                           "extra_trees_poisson")
"""Fase 3: Random Forest y Extra Trees del laboratorio (clasificacion para los
numeros; regresion con criterio de Poisson para los pares de ColorLoto)."""


def _bosque_laboratorio(modelo: str, parametros: dict):
    from sklearn.ensemble import (
        ExtraTreesClassifier,
        ExtraTreesRegressor,
        RandomForestClassifier,
        RandomForestRegressor,
    )

    clase = {"random_forest_clasificador": RandomForestClassifier, "extra_trees_clasificador": ExtraTreesClassifier,
             "random_forest_poisson": RandomForestRegressor, "extra_trees_poisson": ExtraTreesRegressor}[modelo]
    return clase(n_estimators=parametros["n_estimators"], max_depth=parametros["max_depth"],
                 min_samples_leaf=parametros["min_samples_leaf"], max_features=parametros["max_features"],
                 bootstrap=parametros["bootstrap"], criterion=parametros["criterion"],
                 random_state=parametros["random_state"], n_jobs=parametros["n_jobs"])


def estimador_laboratorio(modelo: str, parametros: dict):
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    from sklearn.linear_model import PoissonRegressor

    if modelo in BOSQUES_DEL_LABORATORIO:
        return _bosque_laboratorio(modelo, parametros)
    if modelo == "logistica_regularizada":
        return LogisticRegression(C=parametros["C"], solver=parametros["solver"], max_iter=parametros["max_iter"],
                                  random_state=parametros["semilla"])
    if modelo == "poisson_regularizado":
        return PoissonRegressor(alpha=parametros["alpha"], max_iter=parametros["max_iter"])
    arbol = {k: parametros[k] for k in ("max_iter", "max_depth", "max_leaf_nodes", "min_samples_leaf",
                                        "learning_rate", "l2_regularization", "early_stopping", "random_state")}
    if modelo == "hgb_clasificador":
        return HistGradientBoostingClassifier(categorical_features=[0], **arbol)
    if modelo == "hgb_poisson":
        return HistGradientBoostingRegressor(loss="poisson", categorical_features=[0], **arbol)
    raise ValueError(f"modelo del laboratorio desconocido: {modelo!r}")


def pipeline_laboratorio(familia: str, modelo: str, parametros: dict) -> Pipeline:
    return Pipeline([("variables", transformador_laboratorio(familia)),
                     ("estimador", estimador_laboratorio(modelo, parametros))])


def calibrador_cronologico(pipeline: Pipeline, en_calibracion: Sequence[bool]) -> CalibratedClassifierCV:
    """Sigmoide con `PredefinedSplit`: ajuste base con las filas marcadas
    False y calibracion con las marcadas True (bloque posterior)."""
    return CalibratedClassifierCV(pipeline, method="sigmoid",
                                  cv=PredefinedSplit([0 if c else -1 for c in en_calibracion]))


def ajustar_registrando_convergencia(estimador, X, y) -> list[str]:
    """Ajusta y devuelve los avisos de convergencia registrados (localmente,
    sin silenciarlos de forma global); los demas avisos se vuelven a emitir."""
    import warnings

    from sklearn.exceptions import ConvergenceWarning

    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always", ConvergenceWarning)
        estimador.fit(X, y)
    for aviso in avisos:
        if not issubclass(aviso.category, ConvergenceWarning):
            warnings.warn_explicit(aviso.message, aviso.category, aviso.filename, aviso.lineno)
    return [str(a.message)[:200] for a in avisos if issubclass(a.category, ConvergenceWarning)]


def componentes_de_inferencia(estimador) -> list[dict]:
    """Descripcion legible de los componentes de inferencia serializados de
    un modelo registrado (Fase 3): preparacion de variables, estimador y
    calibracion."""
    salida = []
    base = estimador
    if isinstance(estimador, CalibratedClassifierCV):
        calibrado = estimador.calibrated_classifiers_[0]
        base = calibrado.estimator
        salida.append({"paso": "calibracion", "clase": type(calibrado.calibrators[0]).__name__,
                       "detalle": "sigmoide ajustada solo con el bloque cronologico de calibracion"})
    if isinstance(base, Pipeline):
        for nombre, paso in base.steps:
            if nombre == "variables" and hasattr(paso, "transformers_"):
                partes = ", ".join(f"{n}: {type(t).__name__ if not isinstance(t, str) else t}"
                                   for n, t, _ in paso.transformers_)
                salida.insert(0, {"paso": "preparacion_de_variables", "clase": type(paso).__name__,
                                  "detalle": partes})
            elif nombre == "columnas" and hasattr(paso, "transformers_"):
                salida.insert(0, {"paso": "preparacion_de_variables", "clase": type(paso).__name__,
                                  "detalle": "identidad del candidato en One-Hot (AE-36)"})
            else:
                salida.insert(len(salida) - (1 if salida and salida[-1]["paso"] == "calibracion" else 0),
                              {"paso": "estimador", "clase": type(paso).__name__, "detalle": nombre})
    return salida
