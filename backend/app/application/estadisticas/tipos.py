"""
Vocabulario compartido del módulo de estadísticas.

Cada categoría de magnitud (frecuencia observada, probabilidad
teórica, estimación estadística, métrica de asociación, feature
candidata) es un dataclass DISTINTO -no hay forma de que una función
devuelva "frecuencia" donde se espera "probabilidad" sin que el
chequeo de tipos lo señale. Estas estructuras las usa tanto el motor
(este módulo) como, más adelante, la capa de features para ML -por
diseño, no hay que reescribirlas.

Este módulo es deliberadamente independiente de SQLAlchemy, HTTP y
cualquier detalle de infraestructura: solo tipos de datos puros
(dataclasses, Protocol). El futuro puerto de lectura masiva
(`ResultadosHistoricosRepository`) importará `ResultadoNumerico` y
`ResultadoColorLoto` desde aquí, no al revés.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


class TieneMetadatosSorteo(Protocol):
    """Lo mínimo que `generales.py` necesita de un resultado, sin
    importar si es un sorteo numérico (MiLoto/Baloto/Revancha) o de
    ColorLoto -evita que generales.py dependa de cuál DTO concreto le
    llega."""

    numero_sorteo: int
    fecha: date
    dia_semana: str


@dataclass(frozen=True)
class ResultadoNumerico:
    """Fila plana para MiLoto, Baloto y Baloto Revancha. Nunca
    contiene Combination ni value objects de dominio anidados -el
    motor trabaja con tuplas simples, no con entidades."""

    numero_sorteo: int
    fecha: date
    dia_semana: str
    numeros: tuple[int, ...]
    superbalota: int | None


@dataclass(frozen=True)
class ResultadoColorLoto:
    numero_sorteo: int
    fecha: date
    dia_semana: str
    pares: tuple[tuple[int, str], ...]  # (numero, color_codigo), en orden de posición


@dataclass(frozen=True)
class FrecuenciaObservada:
    """Un CONTEO histórico. Nunca una probabilidad -nunca se debe
    presentar como evidencia de la probabilidad de que un valor
    aparezca en el siguiente sorteo."""

    valor: str  # "17", "ROJO", "5-ROJO", "2024", "lunes", etc.
    apariciones: int
    total_sorteos: int
    frecuencia_relativa: float  # apariciones / total_sorteos (0.0 si total_sorteos == 0)


@dataclass(frozen=True)
class ProbabilidadTeorica:
    """Derivada matemáticamente de las reglas del juego. Nunca de
    datos observados."""

    valor: str  # "*" cuando aplica por igual a todo el pool (caso del Paso 4)
    probabilidad: float
    metodo: str  # p.ej. "K/N = 5/39" -trazabilidad del cálculo


@dataclass(frozen=True)
class FilaFrecuencia:
    """Fila del ranking del Paso 4: Número | Apariciones | Frecuencia
    | Esperada | Diferencia. Combina una FrecuenciaObservada y una
    ProbabilidadTeorica SIN fusionarlas -ambas quedan accesibles por
    separado, nunca como un solo campo ambiguo."""

    valor: str
    apariciones: int
    frecuencia_observada: FrecuenciaObservada
    probabilidad_teorica: ProbabilidadTeorica
    diferencia: float  # frecuencia_relativa - probabilidad_teorica.probabilidad


@dataclass(frozen=True)
class FeatureCandidata:
    """Valor explícitamente marcado como insumo para un futuro
    modelo. `calculado_hasta_sorteo` es obligatorio -es el mecanismo
    central anti-fuga de información."""

    nombre: str
    valor: float
    calculado_hasta_sorteo: int
    ventana: str  # "historico_completo" | "ultimos_10" | ...


@dataclass(frozen=True)
class ResumenGeneral:
    juego_codigo: str
    total_sorteos: int
    primer_sorteo_numero: int | None
    primer_sorteo_fecha: date | None
    ultimo_sorteo_numero: int | None
    ultimo_sorteo_fecha: date | None
    numero_sorteo_minimo: int | None
    numero_sorteo_maximo: int | None


@dataclass(frozen=True)
class ReporteHuecos:
    total_esperado: int  # numero_sorteo_maximo - minimo + 1 (0 si no hay datos)
    total_presente: int
    huecos: tuple[int, ...]
    porcentaje_cobertura: float  # 0.0 si no hay datos (nunca 100% por defecto)


@dataclass(frozen=True)
class ReporteConsistenciaTemporal:
    """Verifica que `fecha` crezca monótonamente con `numero_sorteo`.
    NO corrige nada -solo reporta. Debe invocarse antes de cualquier
    otro cálculo del motor; las demás funciones no repiten este
    chequeo."""

    es_consistente: bool
    problemas: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MetricaAsociacion:
    """Coocurrencia entre 2 o 3 elementos dentro del mismo sorteo
    (Paso 11). `frecuencia_esperada` y `lift` son None cuando la
    combinatoria del juego no permite derivarlos sin ambigüedad -ver
    ColorLoto en `motor/coocurrencia.py`, donde la fórmula de
    repetición del dominio está documentada como un supuesto sin
    verificar, y no se reimplementa aquí para no arriesgar un número
    aparentemente preciso pero conceptualmente incorrecto.

    Deliberadamente NO incluye `chi2`/`p_value`/`significativo`: eso
    es responsabilidad del Paso 12 (tests estadísticos), que además
    debe aplicar corrección por comparaciones múltiples antes de que
    cualquier campo pueda llamarse honestamente "significativo" -
    mezclarlo aquí habría anticipado un rigor que este paso todavía
    no tiene."""

    elementos: tuple[str, ...]  # ("12","27") o ("12","27","33"), orden canónico ascendente
    soporte: int  # apariciones conjuntas, conteo crudo -NUNCA una probabilidad
    total_sorteos: int
    frecuencia_relativa: float  # soporte / total_sorteos
    frecuencia_esperada: float | None  # bajo independencia; None si es ambiguo (ColorLoto)
    lift: float | None  # frecuencia_relativa / frecuencia_esperada; None si no aplica


@dataclass(frozen=True)
class ResultadoTestEstadistico:
    """Resultado de una prueba de hipótesis (Paso 12). Deliberadamente
    un tipo INDEPENDIENTE de MetricaAsociacion -no todo test opera
    sobre un par/trío (la bondad de ajuste testea una distribución
    completa, no una combinación), y fusionarlos habría forzado
    campos irrelevantes en uno u otro caso.

    `p_value_ajustado`, `metodo_correccion`, `alpha` y `significativo`
    quedan en None hasta que se llame explícitamente a
    `aplicar_correccion_bonferroni`/`aplicar_correccion_benjamini_hochberg`
    -`significativo` NUNCA se deriva de `p_value` crudo, solo de
    `p_value_ajustado`. Con muchos números/pares testeados a la vez,
    algunos p-values bajos aparecerán por puro azar; declarar
    "significativo" sin corregir sería exactamente el error que este
    diseño impide estructuralmente."""

    nombre_test: str  # "chi2_bondad_ajuste" | "chi2_independencia"
    elementos: tuple[str, ...]  # sobre qué se testea, p.ej. ("*",) para toda la distribución, o ("12","27")
    estadistico: float
    grados_libertad: int | None
    p_value: float | None
    p_value_ajustado: float | None
    metodo_correccion: str | None  # "bonferroni" | "benjamini_hochberg" | None
    alpha: float | None
    significativo: bool | None  # SOLO True si p_value_ajustado < alpha


@dataclass(frozen=True)
class IntervalosHistoricos:
    """Estadísticos descriptivos sobre TODOS los intervalos entre
    apariciones consecutivas de un valor (Paso 6, segunda mitad) -a
    diferencia de `AtrasoObservado` (que solo mira la última
    aparición respecto a un corte), este tipo resume la serie
    completa de intervalos históricos: qué tan grande fue el mayor
    hueco, cuál es el intervalo típico, etc. Sigue siendo puramente
    descriptivo -un intervalo promedio bajo no implica que el
    próximo intervalo vaya a ser corto.

    minimo se incluye junto con maximo/promedio/mediana porque
    completa la misma información básica que un resumen de
    distribución (igual criterio que min/max en `DistribucionSumas`,
    Etapa F) -no es una adición arbitraria: sin él, alguien viendo
    solo el máximo y el promedio no podría saber si alguna vez hubo
    una racha muy corta entre apariciones.

    Con menos de 2 apariciones no hay ningún intervalo que calcular
    -todos los estadísticos quedan en None (nunca 0, que sería un
    valor real posible si algún día se permitiera medir intervalos de
    longitud cero, lo cual nunca ocurre: dos apariciones en el mismo
    sorteo no producen un intervalo de 0, ver `intervalos` abajo)."""

    valor: str
    cantidad_apariciones: int
    cantidad_intervalos: int  # cantidad_apariciones - 1 si >= 1 aparición, 0 si hay 0
    intervalo_minimo: int | None
    intervalo_maximo: int | None
    intervalo_promedio: float | None
    intervalo_mediana: float | None
    intervalos: tuple[int, ...]  # lista completa, en orden cronológico; () si hay menos de 2 apariciones
