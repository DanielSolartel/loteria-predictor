"""
Excepciones de la capa de aplicación.

Se distinguen de errores de validación esperados (que se comunican
con `ValidationResult`, no con excepciones) porque estas representan
condiciones que impiden completar el caso de uso por completo:
datos duplicados, juego inexistente, etc. La capa API las traduce a
códigos HTTP apropiados (409, 404, 422).
"""
from __future__ import annotations

from enum import Enum


class TipoInconsistenciaHistorica(Enum):
    """Conjunto CERRADO de razones por las que un histórico puede ser
    rechazado antes de calcular una estadística -nunca un string de
    razón libre: cualquier tipo nuevo debe agregarse aquí
    explícitamente, no interpolarse desde quien llama."""

    CANTIDAD = "cantidad"
    DUPLICADOS = "duplicados"
    RANGO = "rango"
    SUPERBALOTA_AUSENTE = "superbalota_ausente"
    RANGO_SUPERBALOTA = "rango_superbalota"
    CANTIDAD_PARES_COLORLOTO = "cantidad_pares_colorloto"
    RANGO_NUMERO_COLORLOTO = "rango_numero_colorloto"
    COLOR_COLORLOTO_INVALIDO = "color_colorloto_invalido"


class DominioError(Exception):
    """Base de todas las excepciones de dominio/aplicación."""


class OperacionConcurrenteError(DominioError):
    """Otra operacion mantiene el recurso del juego; no se cambia el dato."""


class JuegoNoEncontradoError(DominioError):
    def __init__(self, codigo_o_id: str):
        super().__init__(f"Juego no encontrado: {codigo_o_id}")


class JuegoNoSoportadoError(DominioError):
    def __init__(self, codigo: str):
        super().__init__(f"No existe implementación de LotteryGame para el código '{codigo}'")


class SorteoNoEncontradoError(DominioError):
    def __init__(self, sorteo_id: str):
        super().__init__(f"Sorteo no encontrado: {sorteo_id}")


class SorteoDuplicadoError(DominioError):
    def __init__(self, juego_id: str, numero_sorteo: int):
        super().__init__(
            f"Ya existe un sorteo para juego_id={juego_id} numero_sorteo={numero_sorteo}"
        )


class SorteoInvalidoError(DominioError):
    def __init__(self, errores: tuple[str, ...]):
        self.errores = errores
        super().__init__(f"Sorteo inválido: {'; '.join(errores)}")


class ColorNoVigenteError(DominioError):
    def __init__(self, codigo: str):
        super().__init__(f"El color '{codigo}' no está vigente para este juego")


class ConectorNoDisponibleError(DominioError):
    """Envuelve cualquier fallo del origen externo (red, timeout,
    HTML inesperado) en una excepción de dominio, para que la capa
    web no tenga que conocer excepciones de infraestructura
    (ConectorFetchError vive en infrastructure/connectors y la
    aplicación no debe importar de ahí)."""

    def __init__(self, detalle: str):
        super().__init__(f"El origen de datos no está disponible: {detalle}")


class TipoEstadisticaNoSoportadoError(DominioError):
    """El orquestador de estadísticas (CalcularYPersistirEstadistica)
    no tiene ninguna receta registrada para el tipo_estadistica
    pedido -nunca cae silenciosamente en otra métrica."""

    def __init__(self, tipo_estadistica: str):
        super().__init__(f"No existe una receta de cálculo para tipo_estadistica='{tipo_estadistica}'")


class JuegoSinSuperbalotaError(DominioError):
    """El juego consultado no tiene superbalota
    (`has_superballot=False` o `superballot_range=None` en el
    dominio) -nunca se inventa un rango por defecto para una métrica
    de superbalota sobre un juego que no la tiene."""

    def __init__(self, codigo: str):
        super().__init__(f"El juego '{codigo}' no tiene superbalota configurada")


class ResultadoHistoricoInconsistenteError(DominioError):
    """Un `ResultadoNumerico` del histórico no es consistente con lo
    que la receta necesita para calcular sin sesgo -inconsistencia de
    integridad detectada al calcular una estadística, nunca al
    escribir un sorteo nuevo (eso ya lo cubre
    `StandardNumberGame.validate_draw`, un camino distinto). Tres
    tipos posibles, cerrados mediante `TipoInconsistenciaHistorica`
    -nunca una razón de texto libre interpolada en el mensaje, para
    que el conjunto de mensajes posibles quede completamente acotado
    y auditable:

      - CANTIDAD: `len(numeros) != cantidad_numeros` (Etapa Y).
      - DUPLICADOS: `len(set(numeros)) != len(numeros)` (Etapa Z).
      - RANGO: algún número fuera de `[rango_min, rango_max]` (Etapa Z).

    Compatibilidad: la firma posicional `(numeros_sorteo,
    cantidad_esperada)` -exactamente la que ya usaban la receta y los
    tests de Etapa Y- sigue produciendo el mismo tipo (CANTIDAD) y el
    mismo mensaje exacto para listas pequeñas. Los otros dos tipos se
    construyen con `por_duplicados`/`por_rango`, nunca pasando un
    string de razón arbitrario al constructor principal.

    Nunca expone la lista real de `numeros` mal formados (el
    registro corrupto en sí) -solo identificadores (`numero_sorteo`)
    y metadatos pequeños (cantidad/rango esperados). Para listas
    largas de sorteos afectados, trunca a una muestra limitada más el
    total, en vez de listar todos los identificadores sin límite."""

    _MUESTRA_MAXIMA = 10

    def __init__(
        self, numeros_sorteo: list[int], cantidad_esperada: int | None = None, *,
        tipo: TipoInconsistenciaHistorica = TipoInconsistenciaHistorica.CANTIDAD,
        rango_min: int | None = None, rango_max: int | None = None,
    ):
        self.numeros_sorteo = numeros_sorteo
        self.cantidad_esperada = cantidad_esperada
        self.tipo = tipo
        self.rango_min = rango_min
        self.rango_max = rango_max
        super().__init__(self._construir_mensaje())

    @classmethod
    def por_duplicados(cls, numeros_sorteo: list[int]) -> "ResultadoHistoricoInconsistenteError":
        return cls(numeros_sorteo, tipo=TipoInconsistenciaHistorica.DUPLICADOS)

    @classmethod
    def por_rango(
        cls, numeros_sorteo: list[int], rango_min: int, rango_max: int,
    ) -> "ResultadoHistoricoInconsistenteError":
        return cls(
            numeros_sorteo, tipo=TipoInconsistenciaHistorica.RANGO,
            rango_min=rango_min, rango_max=rango_max,
        )

    @classmethod
    def por_superbalota_ausente(cls, numeros_sorteo: list[int]) -> "ResultadoHistoricoInconsistenteError":
        """Superbalota `None` para un sorteo de un juego que la
        requiere -confirmado por auditoría que esto NUNCA puede
        surgir de una operación legítima del sistema (registro,
        sincronización, edición siempre exigen la superbalota vía
        `StandardNumberGame.validate_draw`): es siempre y
        exclusivamente evidencia de corrupción histórica, nunca un
        estado de negocio válido -de ahí el rechazo total, no una
        exclusión silenciosa."""
        return cls(numeros_sorteo, tipo=TipoInconsistenciaHistorica.SUPERBALOTA_AUSENTE)

    @classmethod
    def por_rango_superbalota(
        cls, numeros_sorteo: list[int], rango_min: int, rango_max: int,
    ) -> "ResultadoHistoricoInconsistenteError":
        """Superbalota presente pero fuera de
        `juego_dominio.superballot_range` -tipo separado de `RANGO`
        (que es exclusivamente para números principales) para no
        mezclar ambas semánticas bajo el mismo tipo cerrado."""
        return cls(
            numeros_sorteo, tipo=TipoInconsistenciaHistorica.RANGO_SUPERBALOTA,
            rango_min=rango_min, rango_max=rango_max,
        )

    @classmethod
    def por_cantidad_pares_colorloto(
        cls, numeros_sorteo: list[int], cantidad_esperada: int,
    ) -> "ResultadoHistoricoInconsistenteError":
        """Sorteo de ColorLoto con una cantidad de pares número-color
        distinta de la esperada -tipo separado de `CANTIDAD` (números
        principales) para no mezclar ambos dominios bajo el mismo
        tipo cerrado. Reutiliza el campo real `cantidad_esperada`
        (el mismo ya usado por el constructor posicional de
        `CANTIDAD`), nunca `rango_min`/`rango_max`."""
        return cls(numeros_sorteo, cantidad_esperada, tipo=TipoInconsistenciaHistorica.CANTIDAD_PARES_COLORLOTO)

    @classmethod
    def por_rango_numero_colorloto(
        cls, numeros_sorteo: list[int], rango_min: int, rango_max: int,
    ) -> "ResultadoHistoricoInconsistenteError":
        """Número de un par de ColorLoto fuera de
        `juego_dominio.number_range` -tipo separado de `RANGO`
        (números principales de juegos con `Combination` estándar)."""
        return cls(
            numeros_sorteo, tipo=TipoInconsistenciaHistorica.RANGO_NUMERO_COLORLOTO,
            rango_min=rango_min, rango_max=rango_max,
        )

    @classmethod
    def por_color_colorloto_invalido(cls, numeros_sorteo: list[int]) -> "ResultadoHistoricoInconsistenteError":
        """Color de un par de ColorLoto que no existe en el catálogo
        del juego, o que no estaba vigente en la fecha del sorteo
        -mensaje seguro: nunca expone el código de color corrupto
        real, solo el `numero_sorteo` afectado."""
        return cls(numeros_sorteo, tipo=TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO)

    def _muestra_segura(self) -> str:
        total = len(self.numeros_sorteo)
        if total <= self._MUESTRA_MAXIMA:
            return f"numero_sorteo={self.numeros_sorteo}"
        muestra = self.numeros_sorteo[: self._MUESTRA_MAXIMA]
        return f"total_afectados={total}, numero_sorteo(muestra)={muestra}"

    def _construir_mensaje(self) -> str:
        muestra = self._muestra_segura()
        if self.tipo is TipoInconsistenciaHistorica.CANTIDAD:
            # Mensaje EXACTO al de Etapa Y para listas pequeñas -no se
            # debilita ni se reformula, los tests existentes de Etapa
            # Y siguen esperando este texto literal.
            return f"Sorteo(s) con cantidad de números distinta de {self.cantidad_esperada} (esperada): {muestra}"
        if self.tipo is TipoInconsistenciaHistorica.DUPLICADOS:
            return f"Sorteo(s) con números duplicados: {muestra}"
        if self.tipo is TipoInconsistenciaHistorica.RANGO:
            return f"Sorteo(s) con números fuera del rango [{self.rango_min},{self.rango_max}]: {muestra}"
        if self.tipo is TipoInconsistenciaHistorica.SUPERBALOTA_AUSENTE:
            return f"Sorteo(s) sin superbalota registrada: {muestra}"
        if self.tipo is TipoInconsistenciaHistorica.RANGO_SUPERBALOTA:
            return f"Sorteo(s) con superbalota fuera del rango [{self.rango_min},{self.rango_max}]: {muestra}"
        if self.tipo is TipoInconsistenciaHistorica.CANTIDAD_PARES_COLORLOTO:
            return f"Sorteo(s) de ColorLoto con cantidad de pares distinta de {self.cantidad_esperada} (esperada): {muestra}"
        if self.tipo is TipoInconsistenciaHistorica.RANGO_NUMERO_COLORLOTO:
            return f"Sorteo(s) de ColorLoto con número fuera del rango [{self.rango_min},{self.rango_max}]: {muestra}"
        if self.tipo is TipoInconsistenciaHistorica.COLOR_COLORLOTO_INVALIDO:
            return f"Sorteo(s) de ColorLoto con color no vigente en la paleta: {muestra}"
        raise AssertionError(f"tipo de inconsistencia no manejado: {self.tipo}")  # defensivo, conjunto cerrado
