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


# =====================================================================
# Etapa AE-37, validada -evaluacion temporal anidada y ablacion
# controlada. Tipos anadidos de forma compatible: ningun tipo de
# AE-36 anterior en este archivo fue modificado.
# =====================================================================


@dataclass(frozen=True)
class ConfiguracionCandidata:
    """Una de las seis configuraciones logisticas preregistradas de
    AE-37 -nunca se agregan ni retiran candidatos despues de observar
    resultados. `incluye_recencia` distingue el conjunto `completo`
    (7 features) del conjunto `frecuencias` (5 features, sin
    `sorteos_desde_ultima_aparicion` ni `aparecio_en_sorteo_anterior`)."""
    identificador: str
    conjunto_features: str  # "completo" o "frecuencias"
    incluye_recencia: bool
    C: float

    def __post_init__(self) -> None:
        if self.conjunto_features not in ("completo", "frecuencias"):
            raise ValueError(f"conjunto_features debe ser 'completo' o 'frecuencias', recibido {self.conjunto_features!r}")
        if self.C <= 0:
            raise ValueError(f"C debe ser positivo, recibido {self.C}")


@dataclass(frozen=True)
class FronteraBloqueInterno:
    """Fronteras cronologicas, en numeros de sorteo reales, de una
    iteracion de seleccion interna dentro de un bloque externo:
    ajuste interno (donde se entrena cada candidato) y validacion
    interna (donde se comparan, siempre posterior al ajuste)."""
    ajuste_interno_inicio: int
    ajuste_interno_fin: int
    validacion_interna_inicio: int
    validacion_interna_fin: int


@dataclass(frozen=True)
class FronteraBloqueExterno:
    """Fronteras cronologicas, en numeros de sorteo reales, de un
    bloque externo completo: todo el entrenamiento externo expansivo
    previo, y el propio bloque externo de evaluacion final -nunca
    tocado hasta el paso 9 del protocolo."""
    entrenamiento_externo_inicio: int
    entrenamiento_externo_fin: int
    bloque_externo_inicio: int
    bloque_externo_fin: int


@dataclass(frozen=True)
class ResultadoInternoCandidato:
    """Metricas de UN candidato sobre la validacion interna de UNA
    iteracion -nunca sobre el bloque externo."""
    configuracion: ConfiguracionCandidata
    metricas: MetricasEvaluacion


@dataclass(frozen=True)
class ConfiguracionSeleccionada:
    """Resultado de la seleccion determinista: la configuracion
    ganadora de un bloque externo, junto con el criterio de
    desempate que se aplico -para que el reporte sea auditable sin
    volver a ejecutar la seleccion."""
    configuracion: ConfiguracionCandidata
    resultados_internos: tuple[ResultadoInternoCandidato, ...]
    criterio_desempate: str  # "log_loss" | "brier_score" | "identificador_ascendente"


@dataclass(frozen=True)
class ResultadoExternoModelo:
    """Metricas de la configuracion seleccionada sobre el bloque
    externo -evaluado una unica vez, nunca reutilizado para volver a
    seleccionar."""
    configuracion: ConfiguracionCandidata
    metricas: MetricasEvaluacion


@dataclass(frozen=True)
class DiferenciaFrenteAUniforme:
    """Comparacion del modelo seleccionado contra el baseline
    uniforme en UN bloque externo."""
    diferencia_log_loss: float  # uniforme - modelo; positivo = el modelo mejoro
    diferencia_brier_score: float
    resultado: str  # "gano" | "empato" | "perdio"


@dataclass(frozen=True)
class ResultadoBloqueExterno:
    """Resultado completo, auditable, de UN bloque externo: sus
    fronteras, la seleccion interna que lo produjo, el resultado del
    modelo seleccionado y de los cuatro baselines sobre el bloque
    externo, y la comparacion frente al uniforme."""
    frontera_externa: FronteraBloqueExterno
    frontera_interna: FronteraBloqueInterno
    seleccion: ConfiguracionSeleccionada
    resultado_modelo: ResultadoExternoModelo
    baselines_externos: tuple[ResultadoBaseline, ...]
    diferencia_vs_uniforme: DiferenciaFrenteAUniforme


@dataclass(frozen=True)
class CorteDesarrollo:
    """Registro explicito del corte de desarrollo de AE-37 -nunca
    una constante general del motor, especifica de esta etapa y
    estos datos."""
    hasta_numero_sorteo: int
    sorteos_originales_recibidos: int
    primer_sorteo: int | None
    ultimo_sorteo: int | None


@dataclass(frozen=True)
class PoliticaProximoHoldout:
    """Metadato de la politica del proximo holdout genuinamente
    futuro -nunca inspecciona ni carga las etiquetas futuras, solo
    documenta la politica preregistrada."""
    holdout_consumido_inicio: int
    holdout_consumido_fin: int
    holdout_consumido_confirmado_no_utilizado: bool
    proximo_holdout_inicio: int
    minimo_sorteos_nuevos_requeridos: int


@dataclass(frozen=True)
class ReporteRobustezJuego:
    """Reporte completo en memoria de un experimento AE-37 para un
    juego -nunca se persiste, igual que `ReporteEvaluacionJuego` de
    AE-36. No contiene ningun objeto de scikit-learn."""
    codigo_juego: str
    corte_desarrollo: CorteDesarrollo
    total_sorteos_elegibles: int
    total_filas: int
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    candidatos_preregistrados: tuple[ConfiguracionCandidata, ...]
    bloques_externos: tuple[ResultadoBloqueExterno, ...]
    politica_proximo_holdout: PoliticaProximoHoldout
    semilla: int = 0
    version_sklearn: str = ""
    resumen: str = ""


# =====================================================================
# Etapa AE-38, validada -comparacion exploratoria prerregistrada
# entre Regresion Logistica y Random Forest. Tipos anadidos de forma
# compatible: ningun tipo de AE-36/AE-37 anterior en este archivo fue
# modificado.
# =====================================================================


@dataclass(frozen=True)
class ConfiguracionCandidataAE38:
    """Un candidato preregistrado de AE-38 -logistico o Random
    Forest, nunca mas de seis por familia. `hiperparametros` es un
    diccionario cerrado y explicito, nunca un valor magico -para
    Regresion Logistica contiene `C`; para Random Forest,
    `n_estimators` y `max_depth`."""
    identificador: str
    familia: str  # "logistica" | "random_forest"
    conjunto_features: str  # "completo" o "frecuencias"
    incluye_recencia: bool
    hiperparametros: dict

    def __post_init__(self) -> None:
        if self.familia not in ("logistica", "random_forest"):
            raise ValueError(f"familia debe ser 'logistica' o 'random_forest', recibido {self.familia!r}")
        if self.conjunto_features not in ("completo", "frecuencias"):
            raise ValueError(f"conjunto_features debe ser 'completo' o 'frecuencias', recibido {self.conjunto_features!r}")


@dataclass(frozen=True)
class ResultadoInternoCandidatoAE38:
    """Metricas de UN candidato (de cualquier familia) sobre la
    validacion interna de UNA iteracion -nunca sobre el bloque
    externo."""
    configuracion: ConfiguracionCandidataAE38
    metricas: MetricasEvaluacion


@dataclass(frozen=True)
class ConfiguracionSeleccionadaAE38:
    """Resultado de la seleccion determinista entre TODOS los
    candidatos preregistrados de ambas familias -log loss interno,
    luego brier interno, luego identificador ascendente."""
    configuracion: ConfiguracionCandidataAE38
    resultados_internos: tuple[ResultadoInternoCandidatoAE38, ...]
    criterio_desempate: str


@dataclass(frozen=True)
class ResultadoExternoModeloAE38:
    """Metricas de la configuracion seleccionada (de cualquier
    familia) sobre el bloque externo -evaluado una unica vez."""
    configuracion: ConfiguracionCandidataAE38
    metricas: MetricasEvaluacion


@dataclass(frozen=True)
class ResultadoBloqueExternoAE38:
    """Resultado completo, auditable, de UN bloque externo de
    AE-38: sus fronteras (mismos tipos exactos de AE-37,
    `FronteraBloqueExterno`/`FronteraBloqueInterno`, reutilizados sin
    cambios), la seleccion interna entre ambas familias, el resultado
    del candidato seleccionado, los cuatro baselines, y la
    comparacion frente al uniforme."""
    frontera_externa: FronteraBloqueExterno
    frontera_interna: FronteraBloqueInterno
    seleccion: ConfiguracionSeleccionadaAE38
    resultado_modelo: ResultadoExternoModeloAE38
    baselines_externos: tuple[ResultadoBaseline, ...]
    diferencia_vs_uniforme: DiferenciaFrenteAUniforme


@dataclass(frozen=True)
class ReporteComparacionFamiliasJuego:
    """Reporte completo en memoria de un experimento AE-38 para un
    juego -nunca se persiste. No contiene ningun objeto de
    scikit-learn."""
    codigo_juego: str
    corte_desarrollo: CorteDesarrollo
    total_sorteos_elegibles: int
    total_filas: int
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    candidatos_logisticos: tuple[ConfiguracionCandidataAE38, ...]
    candidatos_random_forest: tuple[ConfiguracionCandidataAE38, ...]
    bloques_externos: tuple[ResultadoBloqueExternoAE38, ...]
    politica_proximo_holdout: PoliticaProximoHoldout
    semilla: int = 0
    version_sklearn: str = ""
    resumen: str = ""
