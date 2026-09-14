"""
Orquestacion pura de un experimento completo -Etapa AE-36,
validada. Unico punto de `application/ml` que ensambla dataset,
particion, baselines y modelo en un `ReporteEvaluacionJuego`. Sigue
sin importar SQLAlchemy/FastAPI/Jinja2 -recibe el historico ya
obtenido por el llamador (el caso de uso, en `use_cases/`).

Correccion arquitectonica de mantenimiento (Etapa AE-37): este
archivo importaba `sklearn` directamente solo para leer
`sklearn.__version__`, contradiciendo la propia documentacion de
AE-36 ("`modelo.py` es el UNICO archivo del paquete que importa
scikit-learn"). Ahora importa `VERSION_SKLEARN` desde `modelo.py` en
su lugar -mismo valor devuelto, mismo comportamiento, ningun cambio
funcional de AE-36."""
from __future__ import annotations

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.baselines import evaluar_todos_los_baselines
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.metricas import evaluar
from app.application.ml.modelo import (
    NOMBRES_FEATURES,
    VERSION_SKLEARN,
    entrenar_modelo_calibrado,
    predecir_probabilidades,
)
from app.application.ml.particion import construir_particion_walk_forward
from app.application.ml.tipos import ReporteEvaluacionJuego


def evaluar_juego(
    historico: list[ResultadoNumerico], rango_min: int, rango_max: int,
    cantidad_numeros: int, codigo_juego: str, semilla: int = 42,
) -> ReporteEvaluacionJuego:
    """Ejecuta el experimento completo de AE-36 para UN juego:
    construye el dataset, particiona cronologicamente, entrena y
    calibra el modelo sobre el 80% previo al test, evalua modelo y
    los cuatro baselines EXCLUSIVAMENTE sobre el test final -nunca
    reentrena ni recalibra con esas filas."""
    historico_ordenado = validar_y_ordenar_historico(historico, codigo_juego)
    dataset = construir_dataset_binario(historico_ordenado, rango_min, rango_max, cantidad_numeros, codigo_juego)
    particion = construir_particion_walk_forward(dataset)

    filas_entrenamiento_completo = tuple(
        f for f in dataset.filas if f.sorteo_objetivo < particion.limites.test_inicio
    )

    modelo = entrenar_modelo_calibrado(filas_entrenamiento_completo, semilla=semilla)
    probabilidades_test = predecir_probabilidades(modelo, particion.filas_test_final)
    metricas_modelo = evaluar(particion.filas_test_final, probabilidades_test)

    baselines = evaluar_todos_los_baselines(
        particion.filas_test_final, historico_ordenado, rango_min, rango_max, cantidad_numeros,
    )

    mejor_baseline = min(baselines, key=lambda b: b.metricas.log_loss)
    if metricas_modelo.log_loss < mejor_baseline.metricas.log_loss:
        resumen = (
            f"El modelo obtuvo Log Loss {metricas_modelo.log_loss:.4f}, mejor que el mejor baseline "
            f"({mejor_baseline.nombre}: {mejor_baseline.metricas.log_loss:.4f}) sobre este conjunto de test. "
            "Esto es una observacion puntual sobre este experimento, no una prueba de capacidad predictiva "
            "generalizable ni una recomendacion de apuesta."
        )
    else:
        resumen = (
            f"El modelo obtuvo Log Loss {metricas_modelo.log_loss:.4f}, igual o peor que el mejor baseline "
            f"({mejor_baseline.nombre}: {mejor_baseline.metricas.log_loss:.4f}) sobre este conjunto de test. "
            "Este es un resultado cientifico valido: no hay evidencia de que el modelo aporte senal sobre "
            "los baselines honestos en este experimento."
        )

    return ReporteEvaluacionJuego(
        codigo_juego=codigo_juego,
        total_sorteos_originales=len(historico_ordenado),
        total_sorteos_elegibles=len(dataset.sorteos_objetivo),
        total_filas=len(dataset.filas),
        rango_min=rango_min,
        rango_max=rango_max,
        cantidad_numeros=cantidad_numeros,
        limites=particion.limites,
        features_utilizadas=NOMBRES_FEATURES,
        hiperparametros=modelo.hiperparametros,
        version_sklearn=VERSION_SKLEARN,
        semilla=semilla,
        metricas_modelo=metricas_modelo,
        baselines=baselines,
        resumen=resumen,
    )
