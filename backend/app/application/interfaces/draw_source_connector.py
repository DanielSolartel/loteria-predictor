"""
Puerto: DrawSourceConnector.

Contrato único que implementan todos los conectores de origen de
datos (scraping HTML, CSV, entrada manual, futura API oficial). La
capa de aplicación (`SincronizarSorteos`) solo conoce esta interfaz
-nunca sabe si detrás hay BeautifulSoup, un archivo CSV o una API
REST. Esto es lo que permite reemplazar el origen de datos sin tocar
el resto del sistema, tal como se pidió.

Diseño importante: `sync()` en el conector es responsabilidad
puramente de *obtención* de datos (crawlear, parsear, devolver DTOs
estructurados) -NUNCA persiste en PostgreSQL ni valida reglas de
juego. Esa orquestación de negocio (validar con `LotteryGame`,
llamar a `RegistrarSorteo`, registrar la ejecución de sincronización)
vive en el caso de uso `SincronizarSorteos`, en application/use_cases.
Esta separación es la que garantiza "no mezclar lógica de scraping
con lógica de negocio".
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class DrawSummary:
    """Resultado mínimo de listar sorteos: solo lo necesario para
    decidir si hay que descargar el detalle o si ya lo tenemos."""

    draw_id: str
    numero_sorteo: int
    fecha: date


@dataclass(frozen=True)
class CategoriaPremio:
    """Una fila de la tabla de premios por categoría de aciertos."""

    categoria: str
    premio_total: str | None
    ganadores: int | None
    premio_por_ganador: str | None


@dataclass(frozen=True)
class DrawDetail:
    """Resultado completo de un sorteo, tal como aparece en la
    página oficial -incluye todo lo que pidió el usuario, sin perder
    ningún dato disponible.

    `numeros` se reutiliza para TODOS los juegos, incluido ColorLoto
    (donde representa los 6 números de las balotas, en el mismo
    orden en que aparecen en el sorteo). `colores` es paralelo a
    `numeros` -mismo índice, mismo orden- y solo lo usa ColorLoto;
    puede tener huecos (`None`) cuando no se pudo determinar el
    color de una balota puntual, SIN que eso borre el número
    correspondiente. Antes de este diseño, un solo campo
    `pares_color: tuple[(numero, color)]` obligaba a que ambos datos
    existieran juntos o no existiera ninguno -un fallo de detección
    de color terminaba borrando también el número, que sí se había
    extraído correctamente. Ver docs/decisiones/colorloto_numeros_colores.md."""

    draw_id: str
    numero_sorteo: int
    fecha: date
    numeros: tuple[int, ...] = ()
    superbalota: int | None = None
    colores: tuple[str | None, ...] = ()  # paralelo a `numeros`; solo ColorLoto
    total_ganadores: int | None = None
    total_premiacion: str | None = None
    nuevo_acumulado: str | None = None
    categorias_premio: tuple[CategoriaPremio, ...] = ()
    html_crudo: str = ""
    fuente_url: str = ""
    advertencias: tuple[str, ...] = ()  # datos que no se pudieron extraer, sin abortar el sorteo


@dataclass(frozen=True)
class HealthStatus:
    disponible: bool
    latencia_ms: float | None
    mensaje: str


@dataclass
class DrawFetchError:
    draw_id: str
    numero_sorteo: int | None
    error: str


@dataclass
class SyncFetchResult:
    """Resultado de `sync()`: los sorteos obtenidos y los que
    fallaron, nunca una excepción que tumbe todo el proceso."""

    draws: list[DrawDetail] = field(default_factory=list)
    fallidos: list[DrawFetchError] = field(default_factory=list)
    paginas_recorridas: int = 0
    duracion_ms: int = 0


class DrawSourceConnector(ABC):
    @property
    @abstractmethod
    def game_code(self) -> str:
        """Código de juego que este conector alimenta, p.ej. 'MILOTO'."""

    @abstractmethod
    def fetch_draws(
        self, ultimo_conocido: int | None = None, max_paginas: int | None = None
    ) -> list[DrawSummary]:
        """Descubre sorteos disponibles en el origen. Si se indica
        `ultimo_conocido`, debe detenerse tan pronto como encuentre
        un sorteo ya conocido -no recorre todo el histórico en cada
        sincronización incremental. `max_paginas` es un límite de
        seguridad opcional para no recorrer el sitio completo de una
        sola vez (útil desde el panel de administración)."""

    @abstractmethod
    def fetch_draw_detail(self, draw_id: str) -> DrawDetail:
        """Obtiene el detalle completo de un sorteo específico."""

    @abstractmethod
    def sync(
        self, ultimo_conocido: int | None = None, max_paginas: int | None = None
    ) -> SyncFetchResult:
        """Orquesta fetch_draws + fetch_draw_detail para todos los
        sorteos nuevos. Debe tolerar que un sorteo individual falle
        sin detener el resto (se acumula en `fallidos`)."""

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Verifica si el origen de datos está disponible, sin
        descargar ni procesar sorteos."""
