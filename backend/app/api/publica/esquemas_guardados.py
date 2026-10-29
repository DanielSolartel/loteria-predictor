"""Proyecciones cerradas de las consultas guardadas (Fase 9.4)."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class PaginaGuardada(BaseModel):
    juego: str
    estado_de_uso: Literal["experimental_no_acreditado"] = "experimental_no_acreditado"
    pagina: int
    paginas: int
    por_pagina: int
    total: int


class ReferenciaRegistrada(BaseModel):
    clave: str
    numero: int


class ModeloGuardado(BaseModel):
    clave: str
    juego: str
    estado: Literal["disponible", "incompatible", "alterado"]
    motivo: str | None = None
    modelo: str | None = None
    nombre: str | None = None
    familia: str | None = None
    perfil: str | None = None
    version_receta: str | None = None
    numero: int | None = None
    corte: int | None = None
    sorteos: int | None = None
    entrenado_en: str | None = None
    linea: str | None = None


class ModelosGuardados(PaginaGuardada):
    elementos: list[ModeloGuardado]
    modelo: str | None = None
    perfil: str | None = None
    nota: str


class PeriodoGuardado(BaseModel):
    primer_sorteo: int
    ultimo_sorteo: int
    primera_fecha: str
    ultima_fecha: str
    sorteos: int


class EvaluacionGuardada(BaseModel):
    estado: str | None = None
    veredicto: str | None = None
    corte: int | None = None
    objetivos: int | None = None
    muestra_pequena: bool | None = None
    log_loss: float | None = None
    log_loss_uniforme: float | None = None
    nota: str


class FichaModeloGuardado(BaseModel):
    juego: str
    estado_de_uso: Literal["experimental_no_acreditado"] = "experimental_no_acreditado"
    modelo: ModeloGuardado
    periodo: PeriodoGuardado
    sha256_historico: str
    variables: list[str]
    semilla: int
    hilos: int
    objetivo_estadistico: str
    contrato_de_inferencia: str
    experimento: str
    evaluacion: EvaluacionGuardada
    nota: str


class CarteraGuardada(BaseModel):
    clave: str
    juego: str
    estado: Literal["disponible", "alterado"]
    motivo: str | None = None
    linea: str | None = None
    objetivo: int | None = None
    corte: int | None = None
    modelo: str | None = None
    nombre: str | None = None
    version_receta: str | None = None
    perfil: str | None = None
    version: int | None = None
    versiones: int | None = None
    cantidad: int | None = None
    generado_en: str | None = None
    registrado: ReferenciaRegistrada | None = None


class CarterasGuardadas(PaginaGuardada):
    elementos: list[CarteraGuardada]
    lineas: list[str]
    linea: str | None = None
    desde: int | None = None
    hasta: int | None = None
    incidencias_sin_objetivo: int = 0
    nota: str


class ParGuardado(BaseModel):
    numero: int
    color: str


class CombinacionGuardada(BaseModel):
    linea: int
    origen: str
    numeros: list[int]
    superbalota: int | None = None
    pares: list[ParGuardado]


class ParametrosCarteraGuardada(BaseModel):
    cantidad: int
    semilla: int
    diversidad: str
    version: str
    algoritmo_rng: str
    presupuesto_de_intentos: int


class FichaCarteraGuardada(BaseModel):
    juego: str
    estado_de_uso: Literal["experimental_no_acreditado"] = "experimental_no_acreditado"
    cartera: CarteraGuardada
    combinaciones: list[CombinacionGuardada]
    parametros: ParametrosCarteraGuardada
    sha256_historico: str
    clasificacion_temporal: str | None = None
    nota_temporal: str
    nota: str


class BaseResultadosGuardados(BaseModel):
    estado: str
    motivo: str | None = None
    ultimo_sorteo: int | None = None
    fecha: str | None = None
    sorteos: int | None = None


class ProcedenciaGuardada(BaseModel):
    nombre: str
    elegida: bool
    estado: str
    lineas: int
    emisiones: int
    ilegibles: int
    error: str | None = None


class LineaResultadoGuardado(BaseModel):
    clave: str
    procedencia: str
    linea: str
    nombre: str
    modelo: str | None = None
    version: str | None = None
    perfil: str | None = None
    registrado: ReferenciaRegistrada | None = None


class PerdidaGuardada(BaseModel):
    modelo: float
    uniforme: float
    diferencia: float
    objetivos: int | None = None
    veredicto: str


class AciertosGuardados(BaseModel):
    suma: int
    promedio: float
    de: int
    objetivos: int
    distribucion: dict[str, int]


class SuperbalotaAgregada(BaseModel):
    aciertos: int
    objetivos: int
    log_loss: PerdidaGuardada
    brier: PerdidaGuardada


class ResumenResultadoGuardado(BaseModel):
    objetivos: int
    incluidos: int
    pendientes: int
    excluidos: int
    sin_base: int
    excluidos_por_motivo: dict[str, int]
    muestra_pequena: bool
    aciertos: AciertosGuardados | None
    perdidas: dict[str, PerdidaGuardada] | None
    superbalota: SuperbalotaAgregada | None


class ResultadoGuardado(BaseModel):
    numeros: list[int] = Field(default_factory=list)
    superbalota: int | None = None
    pares: list[ParGuardado] = Field(default_factory=list)


class SuperbalotaResultadoGuardado(BaseModel):
    acierto: bool
    log_loss: float
    log_loss_uniforme: float
    brier: float
    brier_uniforme: float


class EmisionGuardada(BaseModel):
    juego: str
    procedencia: str
    linea: str
    clave_linea: str
    objetivo: int
    tipo: str | None
    identificador: str | None
    versiones: int | None
    integridad: str
    historico: str | None
    resultado_estado: str | None
    estado: Literal["incluido", "pendiente", "excluido", "sin_base"]
    motivo: str | None
    fecha_sorteo: str | None
    resultado: ResultadoGuardado | None
    aciertos: int | None
    de: int | None
    metricas: dict[str, float] | None
    superbalota: SuperbalotaResultadoGuardado | None


class HistorialResultadosGuardados(BaseModel):
    filas: list[EmisionGuardada]
    total: int
    pagina: int
    paginas: int
    por_pagina: int


class ExclusionComparacionGuardada(BaseModel):
    objetivo: int
    linea: str | None
    motivo: str


class ClasificacionGuardada(BaseModel):
    linea: str
    log_loss: float
    uniforme: float
    diferencia: float
    veredicto: str


class ComparacionResultadosGuardados(BaseModel):
    tipo: str
    lineas: list[str]
    totales_individuales: dict[str, int]
    objetivos_comunes: list[int]
    fuera_de_la_muestra_comun: list[ExclusionComparacionGuardada]
    por_linea: dict[str, ResumenResultadoGuardado]
    uniforme: dict[str, dict[str, float]] | None
    clasificacion: list[ClasificacionGuardada]
    estado: str
    motivo: str | None
    signo: str
    muestra_pequena: bool | None = None


class FiltrosResultadosGuardados(BaseModel):
    procedencia: str | None
    linea: str | None
    tipo: str
    desde: int | None
    hasta: int | None
    objetivo: int | None


class ResultadosGuardados(BaseModel):
    juego: str
    estado_de_uso: Literal["experimental_no_acreditado"] = "experimental_no_acreditado"
    filtros: FiltrosResultadosGuardados
    base: BaseResultadosGuardados
    procedencias: dict[str, ProcedenciaGuardada]
    lineas: list[LineaResultadoGuardado]
    seleccion: list[str]
    resumenes: dict[str, ResumenResultadoGuardado]
    comparacion: ComparacionResultadosGuardados
    historial: HistorialResultadosGuardados
    sin_resultados_de_seguimiento: bool
    politica: str
    nota_seguimiento: str
    signo: str
    unidades: dict[str, str]
    nota: str
