"""Contratos de respuesta de la API publica v1 (pydantic). Los listados llevan su
paginacion o limite explicito; los objetos anidados de estadisticas y
simulaciones conservan la forma del caso de uso que los produce."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ESTADO_DE_USO = "experimental_no_acreditado"


class ErrorDetalle(BaseModel):
    codigo: str = Field(description="Código estable del error")
    mensaje: str
    solicitud: str | None = Field(None, description="Identificador de la solicitud (cabecera X-Request-ID)")
    detalles: list[dict[str, Any]] | None = None


class ErrorRespuesta(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"error": {
        "codigo": "no_autenticado", "mensaje": "Clave de API ausente o no válida",
        "solicitud": "5f0c8a3e9b2d4c1e8f7a6b5c4d3e2f10"}}]})
    error: ErrorDetalle


class Salud(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"estado": "ok", "api": "v1"}]})
    estado: str
    api: str


class Juego(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "codigo": "BALOTO", "nombre": "Baloto", "rango_min": 1, "rango_max": 43, "cantidad_numeros": 5,
        "tiene_superbalota": True, "superbalota_min": 1, "superbalota_max": 16, "tiene_color": False,
        "permite_repeticion": False}]})
    codigo: str
    nombre: str
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    tiene_superbalota: bool
    superbalota_min: int | None
    superbalota_max: int | None
    tiene_color: bool
    permite_repeticion: bool


class JuegoDetalle(Juego):
    espacio_muestral: int
    dimensiones: dict[str, Any]


class Juegos(BaseModel):
    juegos: list[Juego]


class Par(BaseModel):
    numero: int
    color_codigo: str
    color_nombre: str


class Sorteo(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "numero_sorteo": 2715, "fecha": "2026-10-22", "dia_semana": "miercoles", "numeros": [3, 11, 19, 27, 40],
        "superbalota": 7, "pares": []}]})
    numero_sorteo: int
    fecha: date
    dia_semana: str
    numeros: list[int]
    superbalota: int | None
    pares: list[Par]


class PaginaDeSorteos(BaseModel):
    juego: str
    pagina: int
    por_pagina: int
    total: int = Field(description="Sorteos que cumplen los filtros")
    paginas: int
    sorteos: list[Sorteo]


class MetricaDisponible(BaseModel):
    metrica: str
    parametro: str | None = Field(description="Parámetro opcional que admite: anio, mes, dia_semana o ventana")


class IndiceDeEstadisticas(BaseModel):
    juego: str
    resumen: str
    panel: str
    metricas: list[MetricaDisponible]


class Estadisticas(BaseModel):
    """Salida del caso de uso de la Fase 5 (`juego`, `muestra` y `grupos` o `metrica`)."""
    model_config = ConfigDict(extra="allow")
    juego: dict[str, Any]
    muestra: dict[str, Any]


class Resumen(BaseModel):
    """Salida del caso de uso de resumen por juego (Producto 1)."""
    model_config = ConfigDict(extra="allow")
    codigo_juego: str
    nombre: str
    total_sorteos: int


class BaseDelJuego(BaseModel):
    estado: str
    corte: int | None = None
    sorteos: int | None = None
    ultima_fecha: str | None = None
    objetivo: int | None = None


class ModeloDeLaPrediccion(BaseModel):
    id: str | None = None
    nombre: str | None = None
    familia: str | None = None
    tipo: str | None = None
    version: str | None = None


class Prediccion(BaseModel):
    clave: str
    integridad: str
    linea: str
    objetivo: int
    corte: int | None
    sha256_historico: str | None
    generado_en: str | None
    clasificacion_temporal: dict[str, Any] | None
    modelo: ModeloDeLaPrediccion
    combinaciones: list[dict[str, Any]]
    rankings: dict[str, Any] | None
    observado: dict[str, Any] | None
    frente_a_la_base: dict[str, Any] | None
    explicacion_disponible: bool


class PrediccionGuardada(BaseModel):
    clave: str
    linea: str | None = None
    objetivo: int | None = None
    corte: int | None = None
    generado_en: str | None = None
    tipo: str | None = None
    ilegible: str | None = None


class Predicciones(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "juego": "MILOTO", "nombre": "MiLoto", "estado_de_uso": ESTADO_DE_USO,
        "aviso": "Predicciones experimentales: ...", "contexto": {"uso": ESTADO_DE_USO, "AUTORIZA_EVALUACION": False,
                                                              "no_go_ae39": "vigente"},
        "configuracion": "vigente", "base": {"estado": "disponible", "corte": 87, "sorteos": 87,
                                            "ultima_fecha": "2021-09-17", "objetivo": 88},
        "prediccion": None, "historial": [], "historial_total": 0}]})
    juego: str
    nombre: str
    estado_de_uso: str
    aviso: str
    contexto: dict[str, Any]
    configuracion: str = Field(description="Estado de la configuración del juego (p. ej. vigente o sin_configuracion)")
    base: BaseDelJuego
    prediccion: Prediccion | None
    historial: list[PrediccionGuardada]
    historial_total: int


class SimulacionResumen(BaseModel):
    id: str
    juego: str | None
    clave: str | None
    corte: int | None
    iteraciones: int | None
    semilla: int | None
    ejecutado_en: str | None
    duracion_ms: int | None
    integridad: str = Field(description="verificada o alterada")
    motivo: str | None
    alguna_supera_umbral_exploratorio: bool | None


class Simulaciones(BaseModel):
    juego: str
    limite: int
    estado_de_uso: str
    simulaciones: list[SimulacionResumen]


class Simulacion(BaseModel):
    id: str
    juego: str
    num_iteraciones: int
    ejecutado_en: str | None
    duracion_ms: int | None
    integridad: str
    estado_de_uso: str
    parametros: dict[str, Any] = Field(description="Identidad completa; `clave` = SHA-256 canónico del resto")
    contenido: dict[str, Any] = Field(description="Resultado científico determinista")
    contenido_sha256: str


class Ruta(BaseModel):
    metodo: str
    ruta: str
    solicitudes: int
    errores_4xx: int
    errores_5xx: int
    latencia_media_ms: float
    latencia_maxima_ms: float


class EstadoDelServicio(BaseModel):
    api: str
    iniciado_en: str
    segundos_activo: float
    base: str = Field(description="disponible o no_disponible")
    solicitudes: int
    por_clase: dict[str, int]
    rutas: list[Ruta]
    limites: dict[str, Any]
    claves_configuradas: int
