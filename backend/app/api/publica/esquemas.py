"""Contratos de respuesta de la API publica v1 (pydantic). Los listados llevan su
paginacion o limite explicito; los objetos anidados de estadisticas y
simulaciones conservan la forma del caso de uso que los produce."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

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
    titulo: str
    grupo: str
    origen: Literal["fase5", "anterior"] = Field(
        description="fase5: página del catálogo de la Fase 5; anterior: receta de la consola (Fase 9.2)")
    parametro: Literal["anio", "mes", "dia_semana", "ventana", "color"] | None = Field(
        description="Único filtro opcional que admite la métrica, además de hasta_numero_sorteo")
    paginada: bool = Field(description="Si admite `pagina` (100 filas por página en su tabla)")


class IndiceDeEstadisticas(BaseModel):
    juego: str
    resumen: str
    panel: str
    metricas: list[MetricaDisponible] = Field(description="Solo las métricas aplicables al juego con página")


class Estadisticas(BaseModel):
    """Salida del caso de uso de la Fase 5 (`juego`, `muestra` y `grupos`)."""
    model_config = ConfigDict(extra="allow")
    juego: dict[str, Any]
    muestra: dict[str, Any]


class _Abierto(BaseModel):
    model_config = ConfigDict(extra="allow")


class ColumnaDeMetrica(_Abierto):
    clave: str
    etiqueta: str
    formato: str = Field(description="entero, texto, dec1, dec2, dec3, pct, pp, p, tipo_p o color")
    unidad: str


class Paginacion(BaseModel):
    pagina: int
    por_pagina: int
    total_filas: int
    total_paginas: int


class TablaDeMetrica(_Abierto):
    id: str
    titulo: str
    columnas: list[ColumnaDeMetrica]
    filas: list[dict[str, Any]] = Field(description="Valores por clave de columna; puede traer claves adicionales")
    nota: str | None
    paginacion: Paginacion | None = Field(description="Solo en las tablas paginadas; las demás van completas")


class IndicadorDeMetrica(_Abierto):
    etiqueta: str
    valor: Any
    unidad: str
    formato: str


class OpcionDeSelector(_Abierto):
    valor: str | int | float
    etiqueta: str | int | float
    sorteos: int | None


class SelectorDeMetrica(_Abierto):
    parametro: str
    valor: str | int | float | None
    etiqueta: str | int | float | None
    opciones: list[OpcionDeSelector]


class ContenidoDeMetrica(_Abierto):
    slug: str
    titulo: str
    grupo: str
    origen: Literal["fase5", "anterior"]
    parametro: str | None
    estado: str = Field(description="ok, sin_datos, insuficiente o sin_sorteos_en_el_periodo")
    motivo: str | None
    indicadores: list[IndicadorDeMetrica]
    tablas: list[TablaDeMetrica]
    grafica: dict[str, Any] | None
    notas: list[str]
    selector: SelectorDeMetrica | None


class RespuestaDeMetrica(BaseModel):
    """Una métrica del juego (Fase 5 o anterior) sobre la muestra hasta el corte."""
    juego: dict[str, Any]
    muestra: dict[str, Any]
    metrica: ContenidoDeMetrica


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


# ---------------------------------------------------------------------------
# Fase 9.3: clasificacion de candidatos, explicacion guardada y fiabilidad
# (contratos de la Fase 4). Los campos no declarados se descartan: cada modelo
# es la proyeccion publica de lo que devuelve el caso de uso.
# ---------------------------------------------------------------------------

class FilaDeRanking(BaseModel):
    posicion: int
    candidato: int | str | list[int | str] = Field(description="Número, color o par [número, color] (ColorLoto)")
    probabilidad: float = Field(description="Probabilidad emitida por el modelo (unidad en la sección)")
    uniforme: float = Field(description="Referencia uniforme del mismo universo y unidad")
    diferencia: float = Field(description="probabilidad − uniforme")
    razon: float | None = Field(description="probabilidad / uniforme")
    multiplicidad_esperada: float | None = Field(None, description="Solo ColorLoto: balotas × probabilidad por balota")


class SeccionDeRanking(BaseModel):
    todos: list[FilaDeRanking] = Field(description="Universo completo, de mayor a menor probabilidad")
    fuertes: list[FilaDeRanking] | None = None
    debiles: list[FilaDeRanking] | None = None
    universo: int
    por_extremo: int | None = None
    empate_en_el_limite: dict[str, bool] | None = None
    nota_empates: str | None = None
    suma: float | None = None
    unidad: str
    denominador: str
    nota: str | None = None
    estrategia: str | None = None


class Rankings(BaseModel):
    """Clasificación de candidatos del vector fuente congelado (la de la explicación guardada o la
    determinista de la cartera). La superbalota y, en ColorLoto, números y colores van aparte."""
    aviso: str
    objetivo: int
    corte: int
    numeros: SeccionDeRanking
    superbalota: SeccionDeRanking | None = None
    pares: SeccionDeRanking | None = None
    colores: SeccionDeRanking | None = None


class LineaDeModelo(BaseModel):
    id: str
    modelo: str
    version: str
    perfil: str
    nombre: str


class VersionRegistradaDeLaCartera(BaseModel):
    clave: str
    numero: int


class CarteraDeLaExplicacion(BaseModel):
    clave: str
    linea: str
    objetivo: int
    corte: int = Field(description="Corte de entrada de la cartera")
    sha256_historico: str | None = None
    sha256_fuente: str


class VariablesDelMetodo(BaseModel):
    version: str
    nombres: list[str]
    descripcion: str | None = None


class TransformacionDelMetodo(BaseModel):
    tipo: str
    detalle: str | None = None
    delta: float | None = None
    epsilon: float | None = None
    tolerancia: float | None = None


class PesoDeComponente(BaseModel):
    componente: str
    peso: float


class EntrenamientoDelMetodo(BaseModel):
    estimador: str
    corte_de_entrenamiento: int | None = Field(None, description="Solo versiones registradas: corte del ajuste congelado")
    periodo: dict[str, Any] | None = None
    parametros_ajustados: dict[str, Any] | None = None
    detalle: Any = None


class RegistradoDelMetodo(BaseModel):
    clave: str
    numero: int
    corte_de_entrenamiento: int | None = None
    sha256_estimador: str | None = None


class MetodoDeLaExplicacion(BaseModel):
    modelo: str
    nombre: str
    version_de_la_receta: str
    perfil: str
    salida: str
    objetivo: int
    corte: int = Field(description="Corte de entrada del vector fuente (calculado hasta este sorteo)")
    familia: str
    tipo: str | None = None
    variables: VariablesDelMetodo | None = None
    transformacion: TransformacionDelMetodo | None = None
    parametros: dict[str, Any] | None = None
    pesos: list[PesoDeComponente] | None = None
    entrenamiento: EntrenamientoDelMetodo | None = None
    registrado: RegistradoDelMetodo | None = None


class VariablesDeCandidatos(BaseModel):
    version: str
    nombres: list[str]
    por_candidato: dict[str, list[float]] = Field(description="Valores por candidato (`n` o `n|COLOR`) en el orden de `nombres`")
    usadas_por_el_modelo: bool
    calculado_hasta_sorteo: int
    nota: str | None = None


class ResumenDeImportancia(BaseModel):
    minimo: float
    maximo: float
    media_absoluta: float


class ImportanciaDeVariable(BaseModel):
    variable: str
    valor: float | None
    columnas: int
    es_identidad: bool
    resumen: ResumenDeImportancia | None = None


class Importancias(BaseModel):
    estado: Literal["disponible", "no_disponible"]
    motivo: str | None = None
    tipo: str | None = None
    descripcion: str | None = None
    estimador: str | None = None
    calibrado: bool | None = None
    valores: list[ImportanciaDeVariable] | None = None
    aviso: str | None = None


class GeneracionDeLaExplicacion(BaseModel):
    generado_en: str | None = None
    origen: str | None = None
    nota: str | None = None


class Explicacion(BaseModel):
    """Explicación guardada (Fase 4) de la cartera, verificada por su almacén. La API no la genera."""
    clave: str
    esquema: str
    version: str
    cartera: CarteraDeLaExplicacion
    metodo: MetodoDeLaExplicacion
    variables: VariablesDeCandidatos | None
    importancias: Importancias
    avisos: list[str]
    generacion: GeneracionDeLaExplicacion | None


class ExplicacionIlegible(BaseModel):
    clave: str
    motivo: str = Field(description="Código fijo del almacén (p. ej. contenido_alterado)")


class Reproduccion(BaseModel):
    exacta: bool
    distintos: list[str] = Field(default_factory=list)
    motivo: str | None = None
    nota: str | None = None


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
    rankings: Rankings | None
    observado: dict[str, Any] | None
    frente_a_la_base: dict[str, Any] | None
    explicacion_disponible: bool
    linea_de_modelo: LineaDeModelo | None = Field(None, description="Línea de modelo de Producto 6 (vector fuente)")
    registrado: VersionRegistradaDeLaCartera | None = Field(None, description="Versión registrada que usó la cartera")
    explicacion: Explicacion | None = Field(None, description="Explicación guardada vigente; null si no hay ninguna")
    explicaciones_ilegibles: list[ExplicacionIlegible] = Field(default_factory=list)
    reproduccion: Reproduccion | None = Field(
        None, description="Rankings y variables recalculados desde la cartera y comparados con la explicación")


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


class FuenteDelMetodo(BaseModel):
    cita: str
    doi: str | None
    uso: str


class PresentacionDelMetodo(BaseModel):
    umbral_absoluto_proximo_a_cero: float
    criterio: str
    formato: str


class MetodoDeFiabilidad(BaseModel):
    version: str
    unidad: str
    estimacion: str
    incertidumbre: str
    minimo_para_intervalo: int
    supuestos: str
    limitaciones: list[str]
    extremos: dict[str, int] = Field(description="Candidatos por sorteo en cada extremo, por componente")
    presentacion: PresentacionDelMetodo
    fuentes: list[FuenteDelMetodo]


class MetricaDeFiabilidad(BaseModel):
    estado: str = Field(description="estimable, muestra_insuficiente, sin_datos, no_disponible o fallo_de_calculo")
    n: int | None = None
    media: float | None = None
    intervalo: list[float] | None = Field(None, description="Percentiles bootstrap [inferior, superior]; null sin intervalo")
    motivo: str | None = None
    etiqueta: str | None = None
    lectura: str | None = None
    bloque: int | None = None
    remuestreos: int | None = None
    nivel: float | None = None
    semilla: str | None = Field(None, description="Semilla del bootstrap en texto decimal (hasta 60 bits)")
    error_estandar_bootstrap: float | None = None


class ExtremoObservado(BaseModel):
    candidatos_por_sorteo: int
    observado: float
    esperado: float
    razon_observado_esperado: float | None


class ExtremosDeFiabilidad(BaseModel):
    fuertes: ExtremoObservado | None = None
    debiles: ExtremoObservado | None = None


class ComponenteDeFiabilidad(BaseModel):
    estado: str | None = Field(None, description="Solo si el componente no tiene cifras (p. ej. no_disponible)")
    motivo: str | None = None
    sorteos: int | None = None
    metricas: dict[str, MetricaDeFiabilidad] | None = None
    extremos: ExtremosDeFiabilidad | None = None
    identidad_remuestreo: dict[str, str] | None = None


class ExclusionDeFiabilidad(BaseModel):
    estado: str
    motivo: str
    emisiones: int


class MuestraDeFiabilidad(BaseModel):
    sorteos: int | None = Field(None, description="Sorteos incluidos en las cifras")
    periodo: list[int] | None = None
    hasta: int | None = Field(None, description="Solo objetivos hasta este sorteo; null = todos los resultados")
    emisiones: int | None = None
    pendientes: int | None = Field(None, description="Emisiones sin resultado observado en la base consultada")
    sin_base: int | None = None
    exclusiones: list[ExclusionDeFiabilidad] = Field(default_factory=list)
    estado_del_candidato: str | None = None
    excluidos_de_la_muestra_comun: int | None = None


class EvaluacionDeFiabilidad(BaseModel):
    tipo: Literal["seguimiento", "retrospectiva", "evaluacion_de_receta"]
    descripcion: str | None = None
    estado: str = Field(description="estimable, muestra_insuficiente, sin_resultados, sin_base, excluidas, sin_datos, "
                                    "no_disponible o fallo_de_calculo")
    motivo: str | None = None
    muestra: MuestraDeFiabilidad | None = None
    componentes: dict[str, ComponenteDeFiabilidad] = Field(default_factory=dict)
    origen: str | None = Field(None, description="Solo la receta: de qué informe del laboratorio sale")
    informe: str | None = None
    corte_del_informe: int | None = None
    clasificacion_componentes: dict[str, str] | None = None


class LineaDeFiabilidad(BaseModel):
    linea: str = Field(description="procedencia:línea de Producto 6")
    papel: str
    nombre: str
    estimador: str
    evaluaciones: list[EvaluacionDeFiabilidad] = Field(description="Seguimiento y retrospectiva, por separado")


class VersionRegistradaDeLaConfiguracion(BaseModel):
    clave: str
    numero: int
    estado: str = Field(description="compatible, incompatible, alterado o no_encontrado")


class BaseDeFiabilidad(BaseModel):
    estado: str = Field(description="consultada o no_disponible")
    ultimo_sorteo: int | None = None
    fecha: str | None = None
    sorteos: int | None = None


class Fiabilidad(BaseModel):
    """Rendimiento observado e incertidumbre de la Fase 4 (lectura de emisiones congeladas y de
    informes del laboratorio). No es una puntuación de confianza ni una probabilidad de premio."""
    juego: str
    nombre: str
    estado_de_uso: str
    aviso: str
    contexto: dict[str, Any]
    configuracion: str = Field(description="Estado de la configuración del juego (p. ej. vigente o sin_configuracion)")
    registrado: VersionRegistradaDeLaConfiguracion | None
    base: BaseDeFiabilidad
    hasta: int | None = Field(description="Solo objetivos hasta este sorteo; null = todos los resultados observados. "
                                         "No acredita disponibilidad temporal al generar una cartera.")
    metodo: MetodoDeFiabilidad
    lineas: list[LineaDeFiabilidad]
    receta: EvaluacionDeFiabilidad


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
