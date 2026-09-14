"""
Tipos puros de AE-36 -Etapa AE-36, validada, primer baseline de
Machine Learning.

Ningun tipo de este modulo importa SQLAlchemy, FastAPI, Jinja2 ni
ningun elemento de infraestructura -mismo criterio ya establecido
por `application/estadisticas/tipos.py` para el motor estadistico
puro. Estos tipos describen exclusivamente la forma del dataset
supervisado, los limites temporales, las metricas y el reporte de
evaluacion; no calculan nada por si mismos.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LimitesTemporales:
    """Fronteras cronologicas de un experimento, registradas con
    numeros de sorteo reales -nunca indices de arreglo- para que el
    reporte final sea auditable sin volver a ejecutar nada.

    `calentamiento_hasta`: ultimo numero de sorteo consumido
    exclusivamente para construir features del primer sorteo
    elegible (nunca aparece como objetivo).
    `entrenamiento_bloques`: lista de (inicio, fin) de cada bloque de
    entrenamiento walk-forward, expansiva -cada bloque incluye todos
    los sorteos objetivo desde el primero elegible.
    `calibracion`: sorteos objetivo usados para calibrar (siempre
    posteriores a los usados para entrenar el clasificador base de
    esa misma iteracion).
    `validacion_bloques`: bloques de validacion walk-forward
    correspondientes, uno por cada iteracion de entrenamiento.
    `test_inicio`/`test_fin`: frontera del 20% final, nunca tocada
    hasta que toda decision de AE-36 este fijada.
    """
    primer_sorteo_elegible: int
    calentamiento_hasta: int
    entrenamiento_bloques: tuple[tuple[int, int], ...]
    validacion_bloques: tuple[tuple[int, int], ...]
    test_inicio: int
    test_fin: int


@dataclass(frozen=True)
class FilaCandidato:
    """Una fila del dataset supervisado: un (sorteo_objetivo,
    numero_candidato). Nunca contiene el resultado del sorteo
    objetivo dentro de sus features -solo en `etiqueta`, y solo para
    filas de entrenamiento/evaluacion, nunca visible al calcular
    features de otras filas."""
    codigo_juego: str
    sorteo_objetivo: int
    calculado_hasta_sorteo: int
    numero_candidato: int
    etiqueta: int  # 0 o 1
    frecuencia_acumulada: float
    frecuencia_ventana_10: float
    frecuencia_ventana_20: float
    frecuencia_ventana_50: float
    sorteos_desde_ultima_aparicion: int | None  # None = nunca observado hasta este punto
    aparecio_en_sorteo_anterior: int  # 0 o 1

    def __post_init__(self) -> None:
        if self.calculado_hasta_sorteo >= self.sorteo_objetivo:
            raise ValueError(
                f"calculado_hasta_sorteo ({self.calculado_hasta_sorteo}) debe ser "
                f"< sorteo_objetivo ({self.sorteo_objetivo}) -fuga temporal detectada"
            )
        if self.etiqueta not in (0, 1):
            raise ValueError(f"etiqueta debe ser 0 o 1, recibido {self.etiqueta}")


@dataclass(frozen=True)
class DatasetSupervisado:
    """Conjunto completo de filas candidato-etiqueta de un juego,
    mas los metadatos de dominio necesarios para reconstruir
    identidades sin rederivar constantes."""
    codigo_juego: str
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    filas: tuple[FilaCandidato, ...]
    sorteos_objetivo: tuple[int, ...]  # orden ascendente, sin duplicados


@dataclass(frozen=True)
class MetricasEvaluacion:
    """Metricas de un modelo o baseline sobre un bloque de filas.
    Todas las probabilidades ya deben estar en [0,1] y ser finitas
    antes de construir esta instancia -ver validacion en
    `metricas.py`."""
    log_loss: float
    brier_score: float
    precision_en_5: float
    recall_en_5: float
    total_sorteos: int
    total_filas: int

    def __post_init__(self) -> None:
        for nombre, valor in (("log_loss", self.log_loss), ("brier_score", self.brier_score)):
            if valor != valor or valor in (float("inf"), float("-inf")):  # NaN check sin depender de math
                raise ValueError(f"{nombre} no es finito: {valor}")
        for nombre, valor in (("precision_en_5", self.precision_en_5), ("recall_en_5", self.recall_en_5)):
            if not (0.0 <= valor <= 1.0):
                raise ValueError(f"{nombre} fuera de [0,1]: {valor}")


@dataclass(frozen=True)
class ResultadoBaseline:
    nombre: str
    descripcion: str
    metricas: MetricasEvaluacion


@dataclass(frozen=True)
class ReporteEvaluacionJuego:
    """Reporte completo en memoria de un experimento AE-36 para un
    juego. Nunca se persiste -solo existe durante la ejecucion del
    caso de uso y se devuelve al llamador."""
    codigo_juego: str
    total_sorteos_originales: int
    total_sorteos_elegibles: int
    total_filas: int
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    limites: LimitesTemporales
    features_utilizadas: tuple[str, ...]
    hiperparametros: dict = field(default_factory=dict)
    version_sklearn: str = ""
    semilla: int = 0
    metricas_modelo: MetricasEvaluacion | None = None
    baselines: tuple[ResultadoBaseline, ...] = field(default_factory=tuple)
    resumen: str = ""
