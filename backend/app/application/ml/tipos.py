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


# =====================================================================
# Etapa AE-39, validada -cuantificacion de incertidumbre y regla
# de parada cientifica. Tipos anadidos de forma compatible: ningun
# tipo de AE-36/AE-37/AE-38 anterior en este archivo fue modificado.
# =====================================================================

from enum import Enum


class DecisionContinuidadML(Enum):
    """Conjunto CERRADO de decisiones posibles sobre si continuar
    expandiendo familias de modelos -Etapa AE-39. Nunca un string de
    decision libre, y nunca incluye un estado positivo ambiguo como
    'aprobado', 'predictivo' o 'listo_para_produccion': la unica
    decision positiva posible es exploratoria, nunca confirmatoria."""

    EVIDENCIA_EXPLORATORIA_DE_MEJORA = "evidencia_exploratoria_de_mejora"
    NO_GO_SIN_EVIDENCIA_SUFICIENTE = "no_go_sin_evidencia_suficiente"


@dataclass(frozen=True)
class IntervaloBootstrap:
    """Intervalo de confianza no parametrico por bootstrap de
    bloques completos -nunca de filas candidato-sorteo. Limite
    inferior y superior, ambos deben ser finitos; `nivel_confianza`
    debe estar en `(0,1)`; `replicas` debe ser positivo."""
    limite_inferior: float
    limite_superior: float
    nivel_confianza: float
    replicas: int
    semilla: int

    def __post_init__(self) -> None:
        for nombre, valor in (("limite_inferior", self.limite_inferior), ("limite_superior", self.limite_superior)):
            if valor != valor or valor in (float("inf"), float("-inf")):
                raise ValueError(f"{nombre} no es finito: {valor}")
        if not (0.0 < self.nivel_confianza < 1.0):
            raise ValueError(f"nivel_confianza debe estar en (0,1), recibido {self.nivel_confianza}")
        if self.replicas <= 0:
            raise ValueError(f"replicas debe ser positivo, recibido {self.replicas}")
        if self.limite_inferior > self.limite_superior:
            raise ValueError(
                f"limite_inferior ({self.limite_inferior}) no puede ser mayor que "
                f"limite_superior ({self.limite_superior})"
            )


@dataclass(frozen=True)
class ResumenDiferenciasBloques:
    """Analisis descriptivo secundario de las diferencias por bloque
    (orientacion `uniforme - modelo`, positivo = mejora del modelo)
    para UNA metrica -nunca reemplaza al bootstrap ni a la regla de
    decision, solo la complementa. `valor_p_signos` proviene de una
    prueba de signos exacta bilateral, excluyendo unicamente los
    empates exactos."""
    bloques_con_mejora: int
    bloques_con_empeoramiento: int
    bloques_empatados: int
    proporcion_con_mejora: float
    mediana: float
    minimo: float
    maximo: float
    desviacion_estandar: float
    valor_p_signos: float

    def __post_init__(self) -> None:
        for nombre, valor in (
            ("mediana", self.mediana), ("minimo", self.minimo), ("maximo", self.maximo),
            ("desviacion_estandar", self.desviacion_estandar), ("valor_p_signos", self.valor_p_signos),
        ):
            if valor != valor or valor in (float("inf"), float("-inf")):
                raise ValueError(f"{nombre} no es finito: {valor}")
        if not (0.0 <= self.proporcion_con_mejora <= 1.0):
            raise ValueError(f"proporcion_con_mejora fuera de [0,1]: {self.proporcion_con_mejora}")
        if not (0.0 <= self.valor_p_signos <= 1.0):
            raise ValueError(f"valor_p_signos fuera de [0,1]: {self.valor_p_signos}")


@dataclass(frozen=True)
class ResultadoIncertidumbreMetrica:
    """Resultado completo de incertidumbre para UNA metrica
    principal (Log Loss o Brier Score): estimador puntual agregado
    (promedio ponderado por `total_filas` de cada bloque), intervalo
    bootstrap, y resumen descriptivo por bloques."""
    nombre_metrica: str
    diferencia_puntual_agregada: float
    intervalo_bootstrap: IntervaloBootstrap
    resumen_bloques: ResumenDiferenciasBloques

    def __post_init__(self) -> None:
        if self.diferencia_puntual_agregada != self.diferencia_puntual_agregada or self.diferencia_puntual_agregada in (float("inf"), float("-inf")):
            raise ValueError(f"diferencia_puntual_agregada no es finita: {self.diferencia_puntual_agregada}")


@dataclass(frozen=True)
class PoliticaReaperturaML:
    """Politica de reapertura del desarrollo predictivo -Etapa
    AE-39, representada como tipo cerrado en vez de strings
    dispersos. Una decision NO-GO nunca demuestra imposibilidad
    matematica de predecir; solo que no existe evidencia suficiente
    en el protocolo evaluado."""
    proximo_holdout_inicio: int
    minimo_sorteos_nuevos_requeridos: int
    requiere_hipotesis_nueva_prerregistrada: bool = True


@dataclass(frozen=True)
class ReporteIncertidumbreJuego:
    """Reporte completo en memoria de AE-39 para un juego -nunca se
    persiste. Puramente derivado de un `ReporteComparacionFamiliasJuego`
    ya construido (de AE-38); nunca reentrena Regresion Logistica ni
    Random Forest, nunca invoca el caso de uso costoso de AE-38."""
    codigo_juego: str
    total_bloques: int
    resultado_log_loss: ResultadoIncertidumbreMetrica
    resultado_brier_score: ResultadoIncertidumbreMetrica
    precision_en_5_modelo_agregada: float
    recall_en_5_modelo_agregada: float
    precision_en_5_uniforme_agregada: float
    recall_en_5_uniforme_agregada: float
    decision: DecisionContinuidadML
    politica_reapertura: PoliticaReaperturaML
    semilla: int
    resumen: str = ""


# =====================================================================
# Etapa AE-40, validada -gate operativo de elegibilidad para la
# reapertura del holdout de Machine Learning. Tipos anadidos de
# forma compatible: ningun tipo de AE-36/AE-37/AE-38/AE-39 anterior
# en este archivo fue modificado.
# =====================================================================

class EstadoElegibilidadReaperturaML(Enum):
    """Conjunto CERRADO de estados posibles del gate de AE-40. Nunca
    un string de estado libre. `ELEGIBLE_PARA_PRERREGISTRO` nunca
    significa GO, evidencia predictiva, autorizacion para entrenar,
    autorizacion para mirar resultados, ni autorizacion para
    desplegar -unicamente que existen suficientes sorteos nuevos
    para que una etapa futura pueda prerregistrar un protocolo antes
    de observar sus resultados."""

    NO_ELEGIBLE_DATOS_INSUFICIENTES = "no_elegible_datos_insuficientes"
    ELEGIBLE_PARA_PRERREGISTRO = "elegible_para_prerregistro"


@dataclass(frozen=True)
class ResumenDisponibilidadHoldout:
    """Resumen minimo de disponibilidad del holdout -exclusivamente
    metadatos (conteos y numeros de sorteo), nunca numeros ganadores,
    superbalota, fecha como senal, colores, features ni targets.
    Producido por `DisponibilidadHoldoutRepository` y consumido por
    la funcion pura de AE-40; `numero_sorteo_minimo`/`maximo` son
    `None` unicamente cuando `total_registros == 0`."""
    juego_codigo: str
    desde_numero_sorteo: int
    total_registros: int
    total_numeros_distintos: int
    numero_sorteo_minimo: int | None
    numero_sorteo_maximo: int | None


@dataclass(frozen=True)
class ReporteElegibilidadReaperturaML:
    """Reporte completo, inmutable y serializable del gate de AE-40
    para un juego -nunca se persiste, nunca contiene resultados
    observados. Los tres campos booleanos finales son invariantes
    fijas de esta etapa (`False` siempre): AE-40 nunca observa
    resultados, nunca entrena modelos, y nunca consume el holdout."""
    juego_codigo: str
    estado: EstadoElegibilidadReaperturaML
    proximo_holdout_inicio: int
    minimo_sorteos_nuevos_requeridos: int
    total_sorteos_nuevos: int
    numero_sorteo_minimo: int | None
    numero_sorteo_maximo: int | None
    numero_sorteo_objetivo_minimo: int
    numeracion_contigua: bool
    resultados_observados: bool = False
    modelos_entrenados: bool = False
    holdout_consumido: bool = False

    def __post_init__(self) -> None:
        if self.resultados_observados is not False:
            raise ValueError("resultados_observados debe ser siempre False en AE-40 -invariante fija")
        if self.modelos_entrenados is not False:
            raise ValueError("modelos_entrenados debe ser siempre False en AE-40 -invariante fija")
        if self.holdout_consumido is not False:
            raise ValueError("holdout_consumido debe ser siempre False en AE-40 -invariante fija")


# =====================================================================
# Etapa AE-41, validada -bloqueo operativo centralizado del
# desarrollo predictivo. Tipos anadidos de forma compatible: ningun
# tipo de AE-36/AE-37/AE-38/AE-39/AE-40 anterior en este archivo fue
# modificado.
# =====================================================================

class EstadoAutorizacionOperativaML(Enum):
    """Conjunto CERRADO de estados posibles de la politica de
    autorizacion operativa de AE-41. Nunca un string de estado
    libre. `AUTORIZADO_PARA_PRERREGISTRO` nunca significa
    autorizacion para entrenar, para observar resultados, para
    predecir ni para desplegar -unicamente que una etapa futura,
    independiente, podria iniciar un prerregistro tras validacion
    humana expresa."""

    BLOQUEADO_DATOS_INSUFICIENTES = "bloqueado_datos_insuficientes"
    BLOQUEADO_NUMERACION_INVALIDA = "bloqueado_numeracion_invalida"
    AUTORIZADO_PARA_PRERREGISTRO = "autorizado_para_prerregistro"


@dataclass(frozen=True)
class ReporteAutorizacionOperativaML:
    """Reporte completo, inmutable y serializable de la politica de
    bloqueo operativo de AE-41 para un juego -nunca se persiste,
    nunca contiene resultados observados. Los cuatro campos
    booleanos finales son invariantes fijas de esta etapa (`False`
    siempre): AE-41 nunca observa resultados, nunca construye
    datasets ni entrena modelos, nunca genera predicciones, y nunca
    consume el holdout. `reporte_elegibilidad` es `None`
    UNICAMENTE cuando `estado == BLOQUEADO_NUMERACION_INVALIDA`
    -en ese caso el gate de AE-40 no llego a producir un reporte
    normal, porque detecto una inconsistencia estructural."""
    juego_codigo: str
    estado: EstadoAutorizacionOperativaML
    motivo: str
    reporte_elegibilidad: ReporteElegibilidadReaperturaML | None
    resultados_observados: bool = False
    modelos_entrenados: bool = False
    predicciones_generadas: bool = False
    holdout_consumido: bool = False

    def __post_init__(self) -> None:
        if self.resultados_observados is not False:
            raise ValueError("resultados_observados debe ser siempre False en AE-41 -invariante fija")
        if self.modelos_entrenados is not False:
            raise ValueError("modelos_entrenados debe ser siempre False en AE-41 -invariante fija")
        if self.predicciones_generadas is not False:
            raise ValueError("predicciones_generadas debe ser siempre False en AE-41 -invariante fija")
        if self.holdout_consumido is not False:
            raise ValueError("holdout_consumido debe ser siempre False en AE-41 -invariante fija")
        if self.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA:
            if self.reporte_elegibilidad is not None:
                raise ValueError(
                    "reporte_elegibilidad debe ser None cuando estado es BLOQUEADO_NUMERACION_INVALIDA "
                    "-el gate de AE-40 no llego a producir un reporte normal"
                )
        else:
            if self.reporte_elegibilidad is None:
                raise ValueError(
                    f"reporte_elegibilidad no puede ser None cuando estado es {self.estado} "
                    "-el gate de AE-40 si produjo un reporte normal"
                )


# =====================================================================
# Etapa AE-43, validada -nucleo puro de inferencia bloqueada. Tipos
# anadidos de forma compatible: ningun tipo de AE-36..AE-42 anterior
# en este archivo fue modificado. Sin ciclo de importacion:
# `ventanas_temporales` solo depende de la biblioteca estandar.
# =====================================================================

from app.application.ml.ventanas_temporales import MAXIMO_OBJETIVO_INFERENCIA_AE43


@dataclass(frozen=True)
class FilaCandidatoInferencia:
    """Una fila de inferencia (sorteo_objetivo, numero_candidato) SIN
    etiqueta: mismos campos y tipos que `FilaCandidato` salvo
    `etiqueta`, y ningun campo derivado del resultado del objetivo.
    En AE-43 el objetivo nunca sale de DESARROLLO (`<= 2590`)."""
    codigo_juego: str
    sorteo_objetivo: int
    calculado_hasta_sorteo: int
    numero_candidato: int
    frecuencia_acumulada: float
    frecuencia_ventana_10: float
    frecuencia_ventana_20: float
    frecuencia_ventana_50: float
    sorteos_desde_ultima_aparicion: int | None  # None = nunca observado hasta este punto
    aparecio_en_sorteo_anterior: int  # 0 o 1

    def __post_init__(self) -> None:
        if self.sorteo_objetivo != self.calculado_hasta_sorteo + 1:
            raise ValueError(
                f"sorteo_objetivo ({self.sorteo_objetivo}) debe ser calculado_hasta_sorteo + 1 "
                f"({self.calculado_hasta_sorteo + 1})"
            )
        if self.sorteo_objetivo > MAXIMO_OBJETIVO_INFERENCIA_AE43:
            raise ValueError(
                f"sorteo_objetivo ({self.sorteo_objetivo}) fuera de DESARROLLO -AE-43 solo admite "
                f"objetivos <= {MAXIMO_OBJETIVO_INFERENCIA_AE43}"
            )
        if self.aparecio_en_sorteo_anterior not in (0, 1):
            raise ValueError(f"aparecio_en_sorteo_anterior debe ser 0 o 1, recibido {self.aparecio_en_sorteo_anterior}")


@dataclass(frozen=True)
class FilasInferenciaJuego:
    """Todas las filas de inferencia de UN juego para UN sorteo
    objetivo: exactamente un candidato por numero del rango, en orden
    ascendente. Nunca se persiste ni contiene resultados."""
    codigo_juego: str
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    sorteo_objetivo: int
    calculado_hasta_sorteo: int
    total_sorteos_historico: int
    filas: tuple[FilaCandidatoInferencia, ...]

    def __post_init__(self) -> None:
        candidatos = [f.numero_candidato for f in self.filas]
        if candidatos != list(range(self.rango_min, self.rango_max + 1)):
            raise ValueError("filas debe contener exactamente un candidato por numero del rango, en orden ascendente")
        for f in self.filas:
            if (f.codigo_juego, f.sorteo_objetivo, f.calculado_hasta_sorteo) != (
                self.codigo_juego, self.sorteo_objetivo, self.calculado_hasta_sorteo,
            ):
                raise ValueError("todas las filas deben compartir juego, sorteo objetivo y corte")


class EstadoPrediccionML(Enum):
    """Conjunto CERRADO de estados del resolvedor de AE-43. Todos son
    de bloqueo: no existe ningun estado habilitado. Anadir uno exigira
    una etapa futura con evidencia prospectiva real. El orden de
    declaracion es la prioridad (el primero prevalece)."""

    BLOQUEADO_NUMERACION_INVALIDA = "bloqueado_numeracion_invalida"
    BLOQUEADO_DATOS_INSUFICIENTES = "bloqueado_datos_insuficientes"
    BLOQUEADO_NO_GO_CIENTIFICO = "bloqueado_no_go_cientifico"
    BLOQUEADO_SIN_EVALUACION_HOLDOUT = "bloqueado_sin_evaluacion_holdout"


@dataclass(frozen=True)
class ReportePrediccionJuego:
    """Reporte del resolvedor de AE-43 para un juego. Sus campos
    reflejan la tabla `predicciones`, pero en AE-43 las salidas
    predictivas son SIEMPRE vacias: el invariante se verifica aqui,
    no solo en el resolvedor. `estado` es el motivo de mayor
    prioridad; `motivos` los lista todos, en orden de prioridad, para
    que ningun bloqueo quede oculto tras otro."""
    juego_codigo: str
    estado: EstadoPrediccionML
    motivos: tuple[EstadoPrediccionML, ...]
    explicacion: str
    disclaimer: str
    combinaciones: tuple = ()
    numeros_fuertes: tuple = ()
    numeros_debiles: tuple = ()
    probabilidades: tuple = ()
    nivel_confianza: float | None = None
    resultados_observados: bool = False
    modelos_entrenados: bool = False
    predicciones_generadas: bool = False
    holdout_consumido: bool = False

    def __post_init__(self) -> None:
        for nombre in ("combinaciones", "numeros_fuertes", "numeros_debiles", "probabilidades"):
            if len(getattr(self, nombre)) != 0:
                raise ValueError(f"{nombre} debe estar vacio en AE-43 -ningun estado habilita predicciones")
        if self.nivel_confianza is not None:
            raise ValueError("nivel_confianza debe ser None en AE-43")
        for nombre in ("resultados_observados", "modelos_entrenados", "predicciones_generadas", "holdout_consumido"):
            if getattr(self, nombre) is not False:
                raise ValueError(f"{nombre} debe ser siempre False en AE-43 -invariante fija")
        if not self.disclaimer.strip():
            raise ValueError("disclaimer es obligatorio")
        if not self.motivos:
            raise ValueError("motivos no puede estar vacio")
        orden = list(EstadoPrediccionML)
        if list(self.motivos) != sorted(set(self.motivos), key=orden.index):
            raise ValueError("motivos debe estar en orden de prioridad y sin duplicados")
        if self.estado is not self.motivos[0]:
            raise ValueError("estado debe ser el motivo de mayor prioridad")
