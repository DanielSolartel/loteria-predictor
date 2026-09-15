"""
Comparacion exploratoria prerregistrada entre Regresion Logistica y
Random Forest -Etapa AE-38, validada.

Reutiliza el mismo protocolo de evaluacion temporal anidada de AE-37
(`construir_bloques_externos`, `TAMANO_ENTRENAMIENTO_INICIAL_EXTERNO`,
`TAMANO_VALIDACION_INTERNA`, etc., importados sin cambios desde
`evaluacion_anidada.py`), generalizado para comparar candidatos de
ambas familias dentro de la misma seleccion interna. Nunca modifica
el comportamiento validado de AE-37 -`evaluar_bloques_externos`
permanece intacta y sigue siendo la funcion que usa el caso de uso
original de AE-37. Permanece puro -no importa SQLAlchemy, FastAPI ni
Jinja2; solo `modelo.py` importa scikit-learn."""
from __future__ import annotations

from app.application.ml.baselines import evaluar_todos_los_baselines
from app.application.ml.evaluacion_anidada import (
    TAMANO_ENTRENAMIENTO_INICIAL_EXTERNO,
    TAMANO_VALIDACION_INTERNA,
    construir_bloques_externos,
)
from app.application.ml.metricas import evaluar
from app.application.ml.modelo import (
    FAMILIA_LOGISTICA,
    FAMILIA_RANDOM_FOREST,
    entrenar_modelo_calibrado_familia,
    entrenar_modelo_familia,
    predecir_probabilidades_generalizado,
    predecir_probabilidades_pipeline,
)
from app.application.ml.tipos import (
    ConfiguracionCandidataAE38,
    ConfiguracionSeleccionadaAE38,
    DatasetSupervisado,
    DiferenciaFrenteAUniforme,
    FilaCandidato,
    FronteraBloqueExterno,
    FronteraBloqueInterno,
    ResultadoBloqueExternoAE38,
    ResultadoExternoModeloAE38,
    ResultadoInternoCandidatoAE38,
)
from app.application.estadisticas.tipos import ResultadoNumerico

PROPORCION_CALIBRACION = 0.20
SEMILLA_AE38 = 42

CANDIDATOS_LOGISTICOS_AE38: tuple[ConfiguracionCandidataAE38, ...] = (
    ConfiguracionCandidataAE38(identificador="completo_C_0_1", familia=FAMILIA_LOGISTICA, conjunto_features="completo", incluye_recencia=True, hiperparametros={"C": 0.1}),
    ConfiguracionCandidataAE38(identificador="completo_C_1", familia=FAMILIA_LOGISTICA, conjunto_features="completo", incluye_recencia=True, hiperparametros={"C": 1.0}),
    ConfiguracionCandidataAE38(identificador="completo_C_10", familia=FAMILIA_LOGISTICA, conjunto_features="completo", incluye_recencia=True, hiperparametros={"C": 10.0}),
    ConfiguracionCandidataAE38(identificador="frecuencias_C_0_1", familia=FAMILIA_LOGISTICA, conjunto_features="frecuencias", incluye_recencia=False, hiperparametros={"C": 0.1}),
    ConfiguracionCandidataAE38(identificador="frecuencias_C_1", familia=FAMILIA_LOGISTICA, conjunto_features="frecuencias", incluye_recencia=False, hiperparametros={"C": 1.0}),
    ConfiguracionCandidataAE38(identificador="frecuencias_C_10", familia=FAMILIA_LOGISTICA, conjunto_features="frecuencias", incluye_recencia=False, hiperparametros={"C": 10.0}),
)
"""Mismos seis candidatos logisticos prerregistrados exactos de
AE-37 -conservados sin cambios, mismos identificadores."""

CANDIDATOS_RANDOM_FOREST_AE38: tuple[ConfiguracionCandidataAE38, ...] = (
    ConfiguracionCandidataAE38(identificador="rf_completo_n100_d5", familia=FAMILIA_RANDOM_FOREST, conjunto_features="completo", incluye_recencia=True, hiperparametros={"n_estimators": 100, "max_depth": 5}),
    ConfiguracionCandidataAE38(identificador="rf_completo_n200_d10", familia=FAMILIA_RANDOM_FOREST, conjunto_features="completo", incluye_recencia=True, hiperparametros={"n_estimators": 200, "max_depth": 10}),
    ConfiguracionCandidataAE38(identificador="rf_completo_n300_dNone", familia=FAMILIA_RANDOM_FOREST, conjunto_features="completo", incluye_recencia=True, hiperparametros={"n_estimators": 300, "max_depth": None}),
    ConfiguracionCandidataAE38(identificador="rf_frecuencias_n100_d5", familia=FAMILIA_RANDOM_FOREST, conjunto_features="frecuencias", incluye_recencia=False, hiperparametros={"n_estimators": 100, "max_depth": 5}),
    ConfiguracionCandidataAE38(identificador="rf_frecuencias_n200_d10", familia=FAMILIA_RANDOM_FOREST, conjunto_features="frecuencias", incluye_recencia=False, hiperparametros={"n_estimators": 200, "max_depth": 10}),
    ConfiguracionCandidataAE38(identificador="rf_frecuencias_n300_dNone", familia=FAMILIA_RANDOM_FOREST, conjunto_features="frecuencias", incluye_recencia=False, hiperparametros={"n_estimators": 300, "max_depth": None}),
)
"""Exactamente seis candidatos de Random Forest -cuadricula pequena,
finita y fijada antes de ejecutar cualquier experimento sintetico:
tres niveles de profundidad (superficial/media/sin limite) cruzados
con tres tamanos de ensamble crecientes, replicados sobre ambos
conjuntos de features (`completo`/`frecuencias`), simetrico con los
seis candidatos logisticos. `random_state=42` y `n_jobs=1` siempre
-ver `modelo.py`."""

CANDIDATOS_PREREGISTRADOS_AE38: tuple[ConfiguracionCandidataAE38, ...] = (
    CANDIDATOS_LOGISTICOS_AE38 + CANDIDATOS_RANDOM_FOREST_AE38
)
"""Los doce candidatos preregistrados de AE-38 -seis logisticos mas
seis de Random Forest. Nunca se agregan ni retiran candidatos
despues de observar resultados."""


def _filas_por_sorteo(filas: tuple[FilaCandidato, ...]) -> dict[int, tuple[FilaCandidato, ...]]:
    agrupado: dict[int, list[FilaCandidato]] = {}
    for f in filas:
        agrupado.setdefault(f.sorteo_objetivo, []).append(f)
    return {s: tuple(fs) for s, fs in agrupado.items()}


def _entrenar_no_calibrado(candidato: ConfiguracionCandidataAE38, filas_ajuste, semilla: int):
    return entrenar_modelo_familia(
        filas_ajuste, candidato.familia, candidato.hiperparametros, semilla, candidato.incluye_recencia,
    )


def _seleccionar_configuracion(
    filas_ajuste: tuple[FilaCandidato, ...], filas_validacion: tuple[FilaCandidato, ...], semilla: int,
) -> ConfiguracionSeleccionadaAE38:
    """Entrena cada uno de los doce candidatos preregistrados (ambas
    familias) exclusivamente sobre `filas_ajuste`, los compara
    exclusivamente sobre `filas_validacion`, y selecciona el ganador
    por Log Loss interno -> Brier Score interno -> identificador
    ascendente. Nunca mira el bloque externo. Mismo criterio
    exacto de AE-37, generalizado a doce candidatos de dos familias."""
    resultados: list[ResultadoInternoCandidatoAE38] = []
    for candidato in CANDIDATOS_PREREGISTRADOS_AE38:
        pipeline = _entrenar_no_calibrado(candidato, filas_ajuste, semilla)
        probs = predecir_probabilidades_pipeline(pipeline, filas_validacion, candidato.incluye_recencia)
        metricas = evaluar(filas_validacion, probs)
        resultados.append(ResultadoInternoCandidatoAE38(configuracion=candidato, metricas=metricas))

    def _clave_ordenamiento(r: ResultadoInternoCandidatoAE38) -> tuple[float, float, str]:
        return (r.metricas.log_loss, r.metricas.brier_score, r.configuracion.identificador)

    ganador = min(resultados, key=_clave_ordenamiento)

    empatados_log_loss = [r for r in resultados if r.metricas.log_loss == ganador.metricas.log_loss]
    if len(empatados_log_loss) == 1:
        criterio = "log_loss"
    else:
        empatados_brier = [r for r in empatados_log_loss if r.metricas.brier_score == ganador.metricas.brier_score]
        criterio = "brier_score" if len(empatados_brier) == 1 else "identificador_ascendente"

    return ConfiguracionSeleccionadaAE38(
        configuracion=ganador.configuracion,
        resultados_internos=tuple(resultados),
        criterio_desempate=criterio,
    )


def evaluar_bloques_externos_ae38(
    dataset: DatasetSupervisado, historico_ordenado: list[ResultadoNumerico], semilla: int = SEMILLA_AE38,
) -> tuple[ResultadoBloqueExternoAE38, ...]:
    """Ejecuta el protocolo completo de AE-38 -identico al de AE-37
    en particion y disciplina anti-fuga (`construir_bloques_externos`
    reutilizada sin cambios), generalizado para comparar doce
    candidatos de dos familias en la seleccion interna, y reentrenar
    calibrado el ganador -de cualquier familia- sobre todo el
    entrenamiento externo antes de evaluarlo una unica vez en el
    bloque externo."""
    bloques_sorteos = construir_bloques_externos(dataset)
    por_sorteo = _filas_por_sorteo(dataset.filas)

    resultados: list[ResultadoBloqueExternoAE38] = []
    sorteos_todos = dataset.sorteos_objetivo

    for sorteos_bloque in bloques_sorteos:
        inicio_bloque_externo = sorteos_bloque[0]
        indice_en_todos = sorteos_todos.index(inicio_bloque_externo)
        sorteos_entrenamiento_externo = sorteos_todos[:indice_en_todos]

        sorteos_validacion_interna = sorteos_entrenamiento_externo[-TAMANO_VALIDACION_INTERNA:]
        sorteos_ajuste_interno = sorteos_entrenamiento_externo[:-TAMANO_VALIDACION_INTERNA]

        filas_ajuste = tuple(f for s in sorteos_ajuste_interno for f in por_sorteo[s])
        filas_validacion_interna = tuple(f for s in sorteos_validacion_interna for f in por_sorteo[s])
        filas_entrenamiento_externo = tuple(f for s in sorteos_entrenamiento_externo for f in por_sorteo[s])
        filas_bloque_externo = tuple(f for s in sorteos_bloque for f in por_sorteo[s])

        seleccion = _seleccionar_configuracion(filas_ajuste, filas_validacion_interna, semilla)
        ganador = seleccion.configuracion

        modelo_final = entrenar_modelo_calibrado_familia(
            filas_entrenamiento_externo, ganador.familia, ganador.hiperparametros, semilla,
            ganador.incluye_recencia, PROPORCION_CALIBRACION,
        )
        probs_externas = predecir_probabilidades_generalizado(modelo_final, filas_bloque_externo, ganador.incluye_recencia)
        metricas_externas = evaluar(filas_bloque_externo, probs_externas)

        baselines_externos = evaluar_todos_los_baselines(
            filas_bloque_externo, historico_ordenado, dataset.rango_min, dataset.rango_max, dataset.cantidad_numeros,
        )
        uniforme = next(b for b in baselines_externos if b.nombre == "uniforme")

        diff_log_loss = uniforme.metricas.log_loss - metricas_externas.log_loss
        diff_brier = uniforme.metricas.brier_score - metricas_externas.brier_score
        if diff_log_loss > 0 and diff_brier > 0:
            resultado_comparacion = "gano"
        elif diff_log_loss < 0 and diff_brier < 0:
            resultado_comparacion = "perdio"
        else:
            resultado_comparacion = "empato"

        frontera_interna = FronteraBloqueInterno(
            ajuste_interno_inicio=sorteos_ajuste_interno[0], ajuste_interno_fin=sorteos_ajuste_interno[-1],
            validacion_interna_inicio=sorteos_validacion_interna[0], validacion_interna_fin=sorteos_validacion_interna[-1],
        )
        frontera_externa = FronteraBloqueExterno(
            entrenamiento_externo_inicio=sorteos_entrenamiento_externo[0], entrenamiento_externo_fin=sorteos_entrenamiento_externo[-1],
            bloque_externo_inicio=sorteos_bloque[0], bloque_externo_fin=sorteos_bloque[-1],
        )

        resultados.append(ResultadoBloqueExternoAE38(
            frontera_externa=frontera_externa,
            frontera_interna=frontera_interna,
            seleccion=seleccion,
            resultado_modelo=ResultadoExternoModeloAE38(configuracion=ganador, metricas=metricas_externas),
            baselines_externos=baselines_externos,
            diferencia_vs_uniforme=DiferenciaFrenteAUniforme(
                diferencia_log_loss=diff_log_loss, diferencia_brier_score=diff_brier, resultado=resultado_comparacion,
            ),
        ))

    return tuple(resultados)
