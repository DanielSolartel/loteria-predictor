"""
Entidades de la capa analítica: Modelo, MetricaModelo, Prediccion,
Simulacion, Estadistica.

Se agrupan en un solo módulo porque son entidades pequeñas y
fuertemente relacionadas (todas cuelgan de `juego_id` y algunas de
`modelo_id`), y porque en esta fase (Fase 1) son principalmente
contenedores de datos -su lógica real (cómo se calcula una métrica,
cómo se genera una predicción) llega en fases posteriores con los
motores de estadística/ML/simulación. Mantenerlas separadas en
cinco archivos de ~15 líneas cada uno no aportaría claridad todavía.

Todas usan campos `dict` para las cargas flexibles (equivalentes a
JSONB en Postgres) porque la forma exacta de esos datos evoluciona
con cada modelo o tipo de estadística sin requerir migraciones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class Modelo:
    id: UUID | None
    juego_id: UUID
    nombre_modelo: str
    version: str
    hiperparametros: dict = field(default_factory=dict)
    metodo_validacion: str | None = None
    entrenado_en: datetime | None = None
    activo: bool = True


@dataclass
class MetricaModelo:
    id: UUID | None
    modelo_id: UUID
    nombre_metrica: str          # 'accuracy', 'f1', 'brier_score', etc.
    valor: float
    calculado_en: datetime | None = None


@dataclass
class Prediccion:
    id: UUID | None
    juego_id: UUID
    modelo_id: UUID
    fecha_generacion: datetime
    sorteo_objetivo: int
    combinaciones: list[dict] = field(default_factory=list)
    numeros_fuertes: list[dict] = field(default_factory=list)
    numeros_debiles: list[dict] = field(default_factory=list)
    probabilidades: dict = field(default_factory=dict)
    explicacion: str = ""
    nivel_confianza: float | None = None

    def __post_init__(self) -> None:
        if self.nivel_confianza is not None and not (0.0 <= self.nivel_confianza <= 1.0):
            raise ValueError("nivel_confianza debe estar entre 0 y 1")


@dataclass
class Simulacion:
    id: UUID | None
    juego_id: UUID
    num_iteraciones: int
    parametros: dict = field(default_factory=dict)
    resultado_resumen: dict = field(default_factory=dict)
    ejecutado_en: datetime | None = None
    duracion_ms: int | None = None

    def __post_init__(self) -> None:
        if self.num_iteraciones <= 0:
            raise ValueError("num_iteraciones debe ser positivo")


@dataclass
class Estadistica:
    id: UUID | None
    juego_id: UUID
    tipo_estadistica: str        # 'frecuencia', 'intervalo', 'correlacion', etc.
    parametros: dict = field(default_factory=dict)
    resultado: dict = field(default_factory=dict)
    calculado_en: datetime | None = None
    valido_hasta: datetime | None = None
