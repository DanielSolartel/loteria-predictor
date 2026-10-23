"""Calendario operativo de Fase 6, independiente de red, BD y ML.

Las horas describen el sorteo/transmisión según las páginas oficiales
consultadas; no prometen hora de publicación del resultado. Desde el inicio
de la ventana se bloquea emitir automáticamente para ese evento, aunque el
resultado todavía no figure en la base local. El reloj no demuestra que un
sorteo se haya celebrado: esa confirmación es un dato independiente.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ZONA = "America/Bogota"
CONSULTA_FUENTES = "2026-10-20"
MAX_DIAS_CONSULTA = 370
JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")


class CalendarioNoDisponibleError(ValueError):
    """Falta calendario verificado, zona IANA o evento dentro del límite."""


def zona_bogota() -> ZoneInfo:
    try:
        return ZoneInfo(ZONA)
    except ZoneInfoNotFoundError as error:
        raise CalendarioNoDisponibleError(
            "No está disponible America/Bogota. Instale la base IANA tzdata "
            "en el entorno operativo validado; no se sustituye por la zona del equipo."
        ) from error


def _instante_con_zona(ahora: datetime) -> datetime:
    if not isinstance(ahora, datetime) or ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("El reloj debe devolver datetime con zona explícita.")
    return ahora.astimezone(timezone.utc)


def _hora_valida(hora: time) -> bool:
    return isinstance(hora, time) and hora.tzinfo is None


@dataclass(frozen=True)
class ExcepcionCalendario:
    """Cambio explícito: hora=None cancela; una hora puede añadir otro día.

    La referencia y el motivo quedan unidos al evento. Una reprogramación
    sin verificar puede mostrarse, pero nunca autoriza emisión automática.
    """
    fecha: date
    hora_local: time | None = None
    hora_fin_local: time | None = None
    motivo: str = ""
    fuente_url: str = ""
    verificada: bool = False

    def __post_init__(self):
        if type(self.verificada) is not bool:
            raise ValueError("La verificación de la excepción debe ser booleana.")
        if not isinstance(self.fecha, date) or isinstance(self.fecha, datetime):
            raise ValueError("La excepción debe identificar una fecha local.")
        if not self.motivo.strip() or not self.fuente_url.strip():
            raise ValueError("La excepción requiere motivo y referencia comprobable.")
        if self.hora_local is None:
            if self.hora_fin_local is not None:
                raise ValueError("Una cancelación no tiene hora final.")
        elif not _hora_valida(self.hora_local) or (
            self.hora_fin_local is not None and (
                not _hora_valida(self.hora_fin_local) or self.hora_fin_local < self.hora_local
            )
        ):
            raise ValueError("Horas locales de la excepción inválidas.")


@dataclass(frozen=True)
class CalendarioJuego:
    codigo: str
    dias_semana: tuple[int, ...]
    hora_local: time
    fuente_url: str
    verificado: bool = True
    zona: str = ZONA
    hora_fin_local: time | None = None
    horarios_por_dia: tuple[tuple[int, time, time], ...] = ()
    excepciones: tuple[ExcepcionCalendario, ...] = ()
    observaciones: str = ""

    def __post_init__(self):
        if type(self.verificado) is not bool:
            raise ValueError("La verificación del calendario debe ser booleana.")
        object.__setattr__(self, "dias_semana", tuple(self.dias_semana))
        object.__setattr__(self, "horarios_por_dia", tuple(tuple(fila) for fila in self.horarios_por_dia))
        object.__setattr__(self, "excepciones", tuple(self.excepciones))
        if any(not isinstance(e, ExcepcionCalendario) for e in self.excepciones):
            raise ValueError("Las excepciones deben ser entradas explícitas de calendario.")
        if self.codigo not in JUEGOS or self.zona != ZONA:
            raise ValueError("Juego o zona del calendario no admitidos.")
        if not self.dias_semana or len(set(self.dias_semana)) != len(self.dias_semana):
            raise ValueError("Días de semana vacíos o repetidos.")
        if any(type(d) is not int or not 0 <= d <= 6 for d in self.dias_semana):
            raise ValueError("Días de semana: lunes=0, domingo=6.")
        if not _hora_valida(self.hora_local) or (
            self.hora_fin_local is not None and (
                not _hora_valida(self.hora_fin_local) or self.hora_fin_local < self.hora_local
            )
        ):
            raise ValueError("Horas locales del calendario inválidas.")
        vistos = set()
        for dia, inicio, fin in self.horarios_por_dia:
            if dia not in self.dias_semana or dia in vistos or not _hora_valida(inicio) or not _hora_valida(fin) or fin < inicio:
                raise ValueError("Horario particular de día inválido o repetido.")
            vistos.add(dia)
        if len({e.fecha for e in self.excepciones}) != len(self.excepciones):
            raise ValueError("No se admiten dos excepciones para una misma fecha.")
        if not self.fuente_url.strip():
            raise ValueError("El calendario requiere una fuente.")


@dataclass(frozen=True)
class EventoProgramado:
    juego: str
    fecha_local: date
    instante: datetime
    fin_ventana: datetime
    fuente_url: str
    excepcional: bool = False
    fuente_verificada: bool = True
    nota: str = ""

    @property
    def inicio_utc(self) -> datetime:
        return self.instante

    @property
    def fin_utc(self) -> datetime:
        return self.fin_ventana

    def como_dict(self) -> dict:
        zona = zona_bogota()
        return {"juego": self.juego, "fecha_local": self.fecha_local.isoformat(),
                "inicio_utc": self.instante.isoformat(), "fin_ventana_utc": self.fin_ventana.isoformat(),
                "inicio_local": self.instante.astimezone(zona).isoformat(), "zona": ZONA,
                "fuente_url": self.fuente_url, "fuente_verificada": self.fuente_verificada,
                "excepcional": self.excepcional, "nota": self.nota}


def calendario_defecto() -> dict[str, CalendarioJuego]:
    """Fuentes oficiales contrastadas, sin excepciones oficiales inventadas.

    Baloto/Revancha: lunes, miércoles, sábado 23:00–23:15.
    MiLoto: lunes, martes, jueves, viernes 22:00–22:15.
    ColorLoto: lunes 23:40; jueves 23:00. Horas America/Bogota.
    """
    baloto = "https://baloto.com/que-es-baloto"
    return {
        "BALOTO": CalendarioJuego("BALOTO", (0, 2, 5), time(23), baloto, hora_fin_local=time(23, 15)),
        "BALOTO_REVANCHA": CalendarioJuego("BALOTO_REVANCHA", (0, 2, 5), time(23), baloto, hora_fin_local=time(23, 15)),
        "MILOTO": CalendarioJuego("MILOTO", (0, 1, 3, 4), time(22),
            "https://baloto.com/miloto/que-es-miloto/", hora_fin_local=time(22, 15),
            observaciones="La página específica y el pie coinciden en 22:00–22:15; un bloque de la portada dice 23:00–23:15. Se conserva esa discrepancia y el corte más temprano."),
        "COLORLOTO": CalendarioJuego("COLORLOTO", (0, 3), time(23), "https://baloto.com/colorloto",
            horarios_por_dia=((0, time(23, 40), time(23, 40)), (3, time(23), time(23)))),
    }


def evento_en_fecha(calendario: CalendarioJuego, fecha_local: date) -> EventoProgramado | None:
    if not isinstance(fecha_local, date) or isinstance(fecha_local, datetime):
        raise ValueError("Se requiere fecha local, no instante.")
    excepcion = next((e for e in calendario.excepciones if e.fecha == fecha_local), None)
    if excepcion is not None:
        if excepcion.hora_local is None:
            return None
        inicio = excepcion.hora_local
        fin = excepcion.hora_fin_local or inicio
        fuente = excepcion.fuente_url
        verificada = calendario.verificado and excepcion.verificada
        nota = excepcion.motivo
    elif fecha_local.weekday() not in calendario.dias_semana:
        return None
    else:
        inicio = calendario.hora_local
        fin = calendario.hora_fin_local or inicio
        for dia, otra_inicio, otra_fin in calendario.horarios_por_dia:
            if dia == fecha_local.weekday():
                inicio, fin = otra_inicio, otra_fin
                break
        fuente, verificada, nota = calendario.fuente_url, calendario.verificado, calendario.observaciones
    zona = zona_bogota()
    return EventoProgramado(calendario.codigo, fecha_local,
        datetime.combine(fecha_local, inicio, zona).astimezone(timezone.utc),
        datetime.combine(fecha_local, fin, zona).astimezone(timezone.utc),
        fuente, excepcion is not None, verificada, nota)


def eventos(calendario: CalendarioJuego, desde: date, hasta: date) -> tuple[EventoProgramado, ...]:
    if not isinstance(desde, date) or isinstance(desde, datetime) or not isinstance(hasta, date) or isinstance(hasta, datetime):
        raise ValueError("El rango debe usar fechas locales.")
    dias = (hasta - desde).days
    if not 0 <= dias <= MAX_DIAS_CONSULTA:
        raise ValueError(f"Rango permitido: cero a {MAX_DIAS_CONSULTA} días.")
    out = []
    for desplazamiento in range(dias + 1):
        evento = evento_en_fecha(calendario, desde + timedelta(days=desplazamiento))
        if evento is not None:
            out.append(evento)
    return tuple(out)


def proximo_evento(calendario: CalendarioJuego, ahora: datetime, incluir_actual: bool = False) -> EventoProgramado:
    utc = _instante_con_zona(ahora)
    local = utc.astimezone(zona_bogota()).date()
    for evento in eventos(calendario, local, local + timedelta(days=MAX_DIAS_CONSULTA)):
        if evento.instante > utc or (incluir_actual and evento.instante == utc):
            return evento
    raise CalendarioNoDisponibleError("Sin evento próximo dentro del horizonte acotado.")


def ultimo_evento(calendario: CalendarioJuego, ahora: datetime) -> EventoProgramado:
    utc = _instante_con_zona(ahora)
    local = utc.astimezone(zona_bogota()).date()
    anteriores = [e for e in eventos(calendario, local - timedelta(days=MAX_DIAS_CONSULTA), local) if e.instante <= utc]
    if not anteriores:
        raise CalendarioNoDisponibleError("Sin evento anterior dentro del horizonte acotado.")
    return anteriores[-1]


def clasificar(evento: EventoProgramado, ahora: datetime, *, resultado_validado: bool = False,
               celebracion_confirmada: bool = False, error_consulta: bool = False) -> str:
    utc = _instante_con_zona(ahora)
    if error_consulta:
        return "fallo_consulta"
    if resultado_validado:
        return "resultado_detectado_validado"
    if celebracion_confirmada:
        return "celebrado_resultado_no_publicado"
    if utc < evento.instante:
        return "sorteo_previsto"
    return "horario_alcanzado_sin_confirmar"


def admisible_emitir(calendario: CalendarioJuego, objetivo_fecha: date, ahora: datetime, *,
                     resultado_conocido: bool = False) -> bool:
    utc = _instante_con_zona(ahora)
    evento = evento_en_fecha(calendario, objetivo_fecha)
    # Una cancelación sin verificar tampoco autoriza a saltar directamente
    # a otro día y presentar como cierta una cronología todavía dudosa.
    return bool(not resultado_conocido and evento is not None and calendario.verificado
                and all(e.verificada for e in calendario.excepciones)
                and evento.fuente_verificada and utc < evento.instante)
