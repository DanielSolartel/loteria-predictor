"""
Evaluacion temporal anidada y ablacion controlada -Etapa AE-37,
validada.

Unico modulo que orquesta el protocolo completo de AE-37: particion
en bloques externos, seleccion determinista sobre validacion interna,
reentrenamiento calibrado de la configuracion ganadora sobre todo el
entrenamiento externo, y evaluacion unica sobre el bloque externo.
Permanece puro -no importa SQLAlchemy, FastAPI ni Jinja2; solo
`modelo.py` importa scikit-learn, y este modulo solo llama a las
funciones ya expuestas por `modelo.py`, nunca a scikit-learn
directamente."""
from __future__ import annotations

from app.application.ml.baselines import evaluar_todos_los_baselines
from app.application.ml.metricas import evaluar
from app.application.ml.modelo import (
    entrenar_modelo_calibrado_generalizado,
    entrenar_modelo_generalizado,
    predecir_probabilidades_generalizado,
    predecir_probabilidades_pipeline,
)
from app.application.ml.tipos import (
    ConfiguracionCandidata,
    ConfiguracionSeleccionada,
    DatasetSupervisado,
    DiferenciaFrenteAUniforme,
    FilaCandidato,
    FronteraBloqueExterno,
    FronteraBloqueInterno,
    ResultadoBloqueExterno,
    ResultadoExternoModelo,
    ResultadoInternoCandidato,
)
from app.application.estadisticas.tipos import ResultadoNumerico

TAMANO_ENTRENAMIENTO_INICIAL_EXTERNO = 100
TAMANO_BLOQUE_VALIDACION_EXTERNO = 20
TAMANO_VALIDACION_INTERNA = 20
PROPORCION_CALIBRACION = 0.20
SEMILLA_AE37 = 42

CANDIDATOS_PREREGISTRADOS: tuple[ConfiguracionCandidata, ...] = (
    ConfiguracionCandidata(identificador="completo_C_0_1", conjunto_features="completo", incluye_recencia=True, C=0.1),
    ConfiguracionCandidata(identificador="completo_C_1", conjunto_features="completo", incluye_recencia=True, C=1.0),
    ConfiguracionCandidata(identificador="completo_C_10", conjunto_features="completo", incluye_recencia=True, C=10.0),
    ConfiguracionCandidata(identificador="frecuencias_C_0_1", conjunto_features="frecuencias", incluye_recencia=False, C=0.1),
    ConfiguracionCandidata(identificador="frecuencias_C_1", conjunto_features="frecuencias", incluye_recencia=False, C=1.0),
    ConfiguracionCandidata(identificador="frecuencias_C_10", conjunto_features="frecuencias", incluye_recencia=False, C=10.0),
)
"""Las seis configuraciones preregistradas de AE-37 -nunca se agregan
ni retiran candidatos despues de observar resultados. Orden fijo:
determina el desempate final por identificador ascendente."""


class BloqueExternoParcialError(ValueError):
    """Un bloque externo parcial (con menos de
    `TAMANO_BLOQUE_VALIDACION_EXTERNO` sorteos) nunca se descarta en
    silencio -Etapa AE-37 exige bloques externos completos; si
    aparece uno parcial, se informa explicitamente con esta
    excepcion en vez de desaparecer sin evidencia."""


def _filas_por_sorteo(filas: tuple[FilaCandidato, ...]) -> dict[int, tuple[FilaCandidato, ...]]:
    agrupado: dict[int, list[FilaCandidato]] = {}
    for f in filas:
        agrupado.setdefault(f.sorteo_objetivo, []).append(f)
    return {s: tuple(fs) for s, fs in agrupado.items()}


def construir_bloques_externos(dataset: DatasetSupervisado) -> tuple[tuple[int, ...], ...]:
    """Divide `dataset.sorteos_objetivo` en bloques externos
    consecutivos de `TAMANO_BLOQUE_VALIDACION_EXTERNO`, despues de
    reservar los primeros `TAMANO_ENTRENAMIENTO_INICIAL_EXTERNO` como
    entrenamiento inicial. Nunca descarta un bloque parcial en
    silencio -lo rechaza explicitamente con
    `BloqueExternoParcialError`, informando exactamente cuantos
    sorteos quedaron sin bloque completo."""
    sorteos = dataset.sorteos_objetivo
    if len(sorteos) <= TAMANO_ENTRENAMIENTO_INICIAL_EXTERNO:
        raise ValueError(
            f"Se requieren mas de {TAMANO_ENTRENAMIENTO_INICIAL_EXTERNO} sorteos elegibles para el "
            f"entrenamiento inicial externo, hay {len(sorteos)}"
        )

    restantes = sorteos[TAMANO_ENTRENAMIENTO_INICIAL_EXTERNO:]
    total_restantes = len(restantes)
    num_bloques_completos = total_restantes // TAMANO_BLOQUE_VALIDACION_EXTERNO
    sobrante = total_restantes % TAMANO_BLOQUE_VALIDACION_EXTERNO

    if sobrante != 0:
        raise BloqueExternoParcialError(
            f"{sobrante} sorteos no forman un bloque externo completo de "
            f"{TAMANO_BLOQUE_VALIDACION_EXTERNO} -rechazado explicitamente, nunca descartado en silencio "
            f"({num_bloques_completos} bloques completos disponibles)"
        )

    bloques = tuple(
        restantes[i * TAMANO_BLOQUE_VALIDACION_EXTERNO:(i + 1) * TAMANO_BLOQUE_VALIDACION_EXTERNO]
        for i in range(num_bloques_completos)
    )
    return bloques


def _seleccionar_configuracion(
    filas_ajuste: tuple[FilaCandidato, ...], filas_validacion: tuple[FilaCandidato, ...], semilla: int,
) -> ConfiguracionSeleccionada:
    """Entrena cada uno de los seis candidatos preregistrados
    exclusivamente sobre `filas_ajuste`, los compara exclusivamente
    sobre `filas_validacion`, y selecciona el ganador por Log Loss
    interno -> Brier Score interno -> identificador ascendente. Nunca
    mira el bloque externo."""
    resultados: list[ResultadoInternoCandidato] = []
    for candidato in CANDIDATOS_PREREGISTRADOS:
        pipeline = entrenar_modelo_generalizado(filas_ajuste, semilla, candidato.C, candidato.incluye_recencia)
        probs = predecir_probabilidades_pipeline(pipeline, filas_validacion, candidato.incluye_recencia)
        metricas = evaluar(filas_validacion, probs)
        resultados.append(ResultadoInternoCandidato(configuracion=candidato, metricas=metricas))

    def _clave_ordenamiento(r: ResultadoInternoCandidato) -> tuple[float, float, str]:
        return (r.metricas.log_loss, r.metricas.brier_score, r.configuracion.identificador)

    ganador = min(resultados, key=_clave_ordenamiento)

    empatados_log_loss = [r for r in resultados if r.metricas.log_loss == ganador.metricas.log_loss]
    if len(empatados_log_loss) == 1:
        criterio = "log_loss"
    else:
        empatados_brier = [r for r in empatados_log_loss if r.metricas.brier_score == ganador.metricas.brier_score]
        criterio = "brier_score" if len(empatados_brier) == 1 else "identificador_ascendente"

    return ConfiguracionSeleccionada(
        configuracion=ganador.configuracion,
        resultados_internos=tuple(resultados),
        criterio_desempate=criterio,
    )


def evaluar_bloques_externos(
    dataset: DatasetSupervisado, historico_ordenado: list[ResultadoNumerico], semilla: int = SEMILLA_AE37,
) -> tuple[ResultadoBloqueExterno, ...]:
    """Ejecuta el protocolo completo de AE-37 sobre los 18 bloques
    externos esperados (para los datos reales conocidos): seleccion
    interna, reentrenamiento calibrado de la configuracion ganadora
    sobre todo el entrenamiento externo, evaluacion unica sobre el
    bloque externo, y comparacion contra los cuatro baselines -sobre
    exactamente las mismas filas externas."""
    bloques_sorteos = construir_bloques_externos(dataset)
    por_sorteo = _filas_por_sorteo(dataset.filas)

    resultados: list[ResultadoBloqueExterno] = []
    sorteos_todos = dataset.sorteos_objetivo

    for indice_bloque, sorteos_bloque in enumerate(bloques_sorteos):
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

        modelo_final = entrenar_modelo_calibrado_generalizado(
            filas_entrenamiento_externo, semilla, ganador.C, ganador.incluye_recencia, PROPORCION_CALIBRACION,
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

        resultados.append(ResultadoBloqueExterno(
            frontera_externa=frontera_externa,
            frontera_interna=frontera_interna,
            seleccion=seleccion,
            resultado_modelo=ResultadoExternoModelo(configuracion=ganador, metricas=metricas_externas),
            baselines_externos=baselines_externos,
            diferencia_vs_uniforme=DiferenciaFrenteAUniforme(
                diferencia_log_loss=diff_log_loss, diferencia_brier_score=diff_brier, resultado=resultado_comparacion,
            ),
        ))

    return tuple(resultados)
