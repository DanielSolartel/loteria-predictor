"""Fase 6: horario de CONSULTA automática por juego, en America/Bogota y separado del calendario de sorteo.

`operacion_calendario` describe el sorteo y cierra la emisión (`admisible_emitir`): eso no cambia. Este
módulo solo decide cuándo la tarea programada puede INICIAR una consulta automática de cada juego.
Empezar a consultar más tarde nunca amplía el plazo para emitir: el bloqueo sigue siendo el del sorteo.

Una sola representación validada (`PoliticaHorario`) produce las dos piezas que deben coincidir:
- la admisión del núcleo (`decidir`), que el ciclo programado revalida antes de cada juego;
- el plan del Programador de tareas (`plan_windows`): disparadores semanales y su huella. La tarea pasa
  esa huella al ciclo (`--plan`) y el núcleo rechaza cualquier invocación programada cuya huella no sea la
  de la política vigente, así que una política cambiada después de registrar la tarea no reactiva nada.

Reglas:
- franja [inicio, fin), inicio inclusivo y fin exclusivo, en hora local de Bogotá. Si fin <= inicio termina
  el día siguiente y sigue perteneciendo al sorteo del día de inicio;
- oportunidades cada `intervalo_minutos` contadas desde el inicio de la franja (la última es la anterior al
  fin); una ejecución que empieza a tiempo puede terminar después: la franja limita INICIOS;
- recuperación: una sola oportunidad a la hora `recuperacion` del día siguiente al sorteo, y solo para el
  evento que siga pendiente;
- una oportunidad perdida (equipo apagado, suspendido o sin sesión) no se recupera a otra hora: el
  pendiente espera a la siguiente oportunidad permitida.

Las horas de la propuesta inicial son una propuesta operativa configurable (auditoría del 25 de octubre de
2026), no horas oficiales de publicación de resultados ni una programación instalada.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from app.application.operacion_calendario import JUEGOS, ZONA, CalendarioJuego, zona_bogota

VERSION = 1
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
DIAS_WINDOWS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
ANCLA = date(2026, 1, 5)
"""Lunes desde el que se cuentan las semanas de los disparadores (fijo: la huella no depende de hoy)."""
MAXIMO_FRANJA = timedelta(hours=12)
ESTADOS_QUE_REQUIEREN_OPERADOR = frozenset({
    "revision_pendiente", "modelo_no_congelado", "calendario_no_verificado", "generacion_bloqueada",
    "sin_corte_admisible", "reintentos_agotados"})
"""Estados de un juego que repetir la consulta no resuelve: el evento deja de consultarse hasta el siguiente."""
_HORA = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


class PoliticaNoValida(ValueError):
    """Política de horario vacía, ambigua o inválida: nunca se sustituye por sondeo continuo."""


@dataclass(frozen=True)
class Franja:
    juego: str
    dia: int  # día del sorteo que origina la franja; lunes=0
    inicio: time
    fin: time  # si fin <= inicio, del día siguiente

    @property
    def duracion(self) -> timedelta:
        inicio = timedelta(hours=self.inicio.hour, minutes=self.inicio.minute)
        fin = timedelta(hours=self.fin.hour, minutes=self.fin.minute)
        return fin - inicio if fin > inicio else fin + timedelta(days=1) - inicio


@dataclass(frozen=True)
class PoliticaHorario:
    franjas: tuple[Franja, ...]
    intervalo_minutos: int = 15
    recuperacion: time | None = time(9)
    zona: str = ZONA
    version: int = VERSION

    def __post_init__(self):
        _validar(self)

    @property
    def intervalo(self) -> timedelta:
        return timedelta(minutes=self.intervalo_minutos)

    def franjas_de(self, juego: str) -> tuple[Franja, ...]:
        return tuple(f for f in self.franjas if f.juego == juego)


@dataclass(frozen=True)
class Ventana:
    juego: str
    tipo: str  # "franja" | "recuperacion"
    fecha_sorteo: date
    inicio: datetime  # UTC
    fin: datetime  # UTC, exclusivo

    def oportunidades(self, intervalo: timedelta) -> list[datetime]:
        salida, t = [], self.inicio
        while t < self.fin:
            salida.append(t)
            t += intervalo
        return salida


@dataclass(frozen=True)
class Decision:
    juego: str
    admitido: bool
    motivo: str
    detalle: str
    ventana: Ventana | None = None
    oportunidad: datetime | None = None  # inicio UTC del slot vigente
    hasta: datetime | None = None  # espera por fallo o Retry-After

    def registro(self) -> dict:
        """Lo que el estado del juego guarda de una oportunidad programada usada."""
        return {"origen": "programado", "tipo": self.ventana.tipo, "evento": self.ventana.fecha_sorteo.isoformat(),
                "oportunidad": self.oportunidad.isoformat()}


# ---------------------------------------------------------------------------
# Validación y representación
# ---------------------------------------------------------------------------

def _hora_exacta(valor) -> bool:
    return isinstance(valor, time) and valor.tzinfo is None and valor.second == 0 and valor.microsecond == 0


def _semana(f: Franja) -> tuple[timedelta, timedelta]:
    """Intervalo [inicio, fin) de la franja medido desde el lunes 00:00 de una semana."""
    inicio = timedelta(days=f.dia, hours=f.inicio.hour, minutes=f.inicio.minute)
    return inicio, inicio + f.duracion


def _se_solapan(a: tuple[timedelta, timedelta], b: tuple[timedelta, timedelta]) -> bool:
    semana = timedelta(days=7)
    return any(a[0] < b[1] + k * semana and b[0] + k * semana < a[1] for k in (-1, 0, 1))


def _validar(p: PoliticaHorario) -> None:
    if p.version != VERSION or p.zona != ZONA:
        raise PoliticaNoValida(f"Versión o zona no admitidas: la política se expresa en {ZONA}, versión {VERSION}.")
    if type(p.intervalo_minutos) is not int or not 5 <= p.intervalo_minutos <= 60:
        raise PoliticaNoValida("El intervalo debe ser un entero de 5 a 60 minutos.")
    if not isinstance(p.franjas, tuple) or not p.franjas:
        raise PoliticaNoValida("La política no tiene franjas: no se programa ninguna consulta automática.")
    vistas = set()
    for f in p.franjas:
        if not isinstance(f, Franja) or f.juego not in JUEGOS or type(f.dia) is not int or not 0 <= f.dia <= 6:
            raise PoliticaNoValida("Franja con juego o día no admitidos.")
        if not _hora_exacta(f.inicio) or not _hora_exacta(f.fin) or f.inicio == f.fin:
            raise PoliticaNoValida("Las franjas usan horas locales exactas (HH:MM) con inicio distinto del fin.")
        if f.duracion > MAXIMO_FRANJA:
            raise PoliticaNoValida("Una franja no puede durar más de 12 horas.")
        if (f.juego, f.dia) in vistas:
            raise PoliticaNoValida("Dos franjas para el mismo juego y día del sorteo son ambiguas.")
        vistas.add((f.juego, f.dia))
    if p.recuperacion is not None and not _hora_exacta(p.recuperacion):
        raise PoliticaNoValida("La recuperación usa una hora local exacta (HH:MM).")
    for juego in JUEGOS:
        intervalos = [_semana(f) for f in p.franjas_de(juego)]
        if p.recuperacion is not None:
            r = timedelta(hours=p.recuperacion.hour, minutes=p.recuperacion.minute)
            intervalos += [(timedelta(days=(f.dia + 1) % 7) + r, timedelta(days=(f.dia + 1) % 7) + r + p.intervalo)
                           for f in p.franjas_de(juego)]
        unicos = sorted(set(intervalos))
        for i, a in enumerate(unicos):
            if any(_se_solapan(a, b) for b in unicos[i + 1:]):
                raise PoliticaNoValida(f"Franjas o recuperación solapadas para {juego}: la oportunidad sería ambigua.")
    zona = zona_bogota()
    desfases = {datetime.combine(ANCLA + timedelta(days=d), time(12), zona).utcoffset() for d in range(0, 3 * 366, 7)}
    if len(desfases) != 1:
        raise PoliticaNoValida("La zona tiene cambios de hora: el plan semanal no puede expresarla con un desfase fijo.")


def validar_con_calendario(p: PoliticaHorario, calendarios: dict[str, CalendarioJuego]) -> None:
    """Cada franja nace de un día de sorteo del juego y empieza después de la hora de ese sorteo
    (los dos calendarios siguen separados: este solo comprueba que no se contradicen)."""
    for f in p.franjas:
        c = calendarios.get(f.juego)
        if c is None or f.dia not in c.dias_semana:
            raise PoliticaNoValida(f"{f.juego} no tiene sorteo el {DIAS[f.dia]}: la franja no corresponde a un evento.")
        hora = next((inicio for dia, inicio, _ in c.horarios_por_dia if dia == f.dia), c.hora_local)
        if f.inicio <= hora:
            raise PoliticaNoValida(f"La franja de {f.juego} del {DIAS[f.dia]} empieza antes o a la hora del sorteo.")


def _hhmm(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _hora(texto, que: str) -> time:
    if not isinstance(texto, str) or not _HORA.fullmatch(texto):
        raise PoliticaNoValida(f"{que} debe ser una hora HH:MM.")
    return time(int(texto[:2]), int(texto[3:]))


def como_dict(p: PoliticaHorario) -> dict:
    return {"version": p.version, "zona": p.zona, "intervalo_minutos": p.intervalo_minutos,
            "recuperacion": None if p.recuperacion is None else _hhmm(p.recuperacion),
            "franjas": [{"juego": f.juego, "dia": DIAS[f.dia], "inicio": _hhmm(f.inicio), "fin": _hhmm(f.fin)}
                        for f in p.franjas]}


def desde_dict(valor) -> PoliticaHorario:
    """Lectura estricta: claves exactas, tipos exactos y valores admitidos."""
    if not isinstance(valor, dict) or set(valor) != {"version", "zona", "intervalo_minutos", "recuperacion", "franjas"}:
        raise PoliticaNoValida("La política de horario tiene claves ausentes o ajenas.")
    if type(valor["version"]) is not int or type(valor["intervalo_minutos"]) is not int:
        raise PoliticaNoValida("Versión e intervalo deben ser enteros.")
    if not isinstance(valor["franjas"], list) or len(valor["franjas"]) > 50:
        raise PoliticaNoValida("Las franjas deben ser una lista acotada.")
    franjas = []
    for f in valor["franjas"]:
        if not isinstance(f, dict) or set(f) != {"juego", "dia", "inicio", "fin"} or f["dia"] not in DIAS:
            raise PoliticaNoValida("Franja con claves o día no admitidos.")
        franjas.append(Franja(f["juego"], DIAS.index(f["dia"]), _hora(f["inicio"], "El inicio"), _hora(f["fin"], "El fin")))
    recuperacion = None if valor["recuperacion"] is None else _hora(valor["recuperacion"], "La recuperación")
    return PoliticaHorario(tuple(franjas), valor["intervalo_minutos"], recuperacion, valor["zona"], valor["version"])


def propuesta_inicial() -> PoliticaHorario:
    """Propuesta configurable del auditor (25 de octubre de 2026) para el entorno aislado; no son horas
    oficiales de publicación. Fin del día siguiente; recuperación a las 09:00 solo para pendientes."""
    def franjas(juego, dias, inicio, fin):
        return [Franja(juego, d, inicio, fin) for d in dias]
    return PoliticaHorario(tuple(
        franjas("MILOTO", (0, 1, 3, 4), time(22, 30), time(2))
        + franjas("BALOTO", (0, 2, 5), time(23, 30), time(2, 30))
        + franjas("BALOTO_REVANCHA", (0, 2, 5), time(23, 30), time(2, 30))
        + franjas("COLORLOTO", (0,), time(23, 50), time(2, 30))
        + franjas("COLORLOTO", (3,), time(23, 15), time(2, 30))))


# ---------------------------------------------------------------------------
# Ventanas, oportunidades y admisión
# ---------------------------------------------------------------------------

def _utc(fecha: date, hora: time) -> datetime:
    return datetime.combine(fecha, hora, zona_bogota()).astimezone(timezone.utc)


def ventanas(p: PoliticaHorario, juego: str, desde: date, hasta: date) -> list[Ventana]:
    """Franjas y recuperaciones de los sorteos con fecha local en [desde, hasta], en orden de inicio."""
    salida = []
    for i in range((hasta - desde).days + 1):
        fecha = desde + timedelta(days=i)
        for f in p.franjas_de(juego):
            if f.dia != fecha.weekday():
                continue
            inicio = _utc(fecha, f.inicio)
            salida.append(Ventana(juego, "franja", fecha, inicio, inicio + f.duracion))
            if p.recuperacion is not None:
                r = _utc(fecha + timedelta(days=1), p.recuperacion)
                salida.append(Ventana(juego, "recuperacion", fecha, r, r + p.intervalo))
    return sorted(salida, key=lambda v: v.inicio)


def _instante(valor) -> datetime | None:
    if not valor:
        return None
    d = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
    if d.tzinfo is None:
        raise ValueError("Instante operativo sin zona horaria.")
    return d.astimezone(timezone.utc)


def _local(ahora: datetime) -> date:
    if not isinstance(ahora, datetime) or ahora.tzinfo is None:
        raise ValueError("El reloj debe devolver datetime con zona explícita.")
    return ahora.astimezone(zona_bogota()).date()


def ventana_vigente(p: PoliticaHorario, juego: str, ahora: datetime) -> Ventana | None:
    hoy = _local(ahora)
    return next((v for v in ventanas(p, juego, hoy - timedelta(days=2), hoy) if v.inicio <= ahora < v.fin), None)


def proxima_oportunidad(p: PoliticaHorario, juego: str, ahora: datetime, *, incluir_recuperacion: bool = False
                        ) -> tuple[datetime, Ventana] | None:
    """Siguiente inicio de slot posterior a `ahora` (la recuperación solo si se pide: es para pendientes)."""
    hoy = _local(ahora)
    for v in ventanas(p, juego, hoy - timedelta(days=2), hoy + timedelta(days=8)):
        if v.tipo == "recuperacion" and not incluir_recuperacion:
            continue
        for t in v.oportunidades(p.intervalo):
            if t > ahora:
                return t, v
    return None


def estado_del_evento(estado: dict, ventana: Ventana, p: PoliticaHorario) -> str:
    """completo | requiere_operador | pendiente para el sorteo de `ventana`.

    Completo solo si el último ciclo terminó «correcto» (resultado validado, conciliación y predicción
    publicada o reutilizada) con un resultado de la fecha del sorteo o posterior. Un bloqueo que pide al
    operador cuenta si se registró desde el inicio de la franja de ese sorteo."""
    fecha = estado.get("fecha_ultimo_sorteo")
    if estado.get("estado") == "correcto" and fecha and date.fromisoformat(str(fecha)[:10]) >= ventana.fecha_sorteo:
        return "completo"
    franja = next(f for f in p.franjas_de(ventana.juego) if f.dia == ventana.fecha_sorteo.weekday())
    comprobado = _instante(estado.get("ultima_comprobacion"))
    if (estado.get("estado") in ESTADOS_QUE_REQUIEREN_OPERADOR and comprobado is not None
            and comprobado >= _utc(ventana.fecha_sorteo, franja.inicio)):
        return "requiere_operador"
    return "pendiente"


def decidir(p: PoliticaHorario, juego: str, ahora: datetime, estado: dict, *, max_reintentos: int) -> Decision:
    """Admisión de una consulta PROGRAMADA de `juego` en `ahora`, solo con el estado guardado (sin red ni BD)."""
    v = ventana_vigente(p, juego, ahora)
    if v is None:
        siguiente = proxima_oportunidad(p, juego, ahora)
        detalle = ("Fuera de horario; próxima franja " + siguiente[0].isoformat()) if siguiente else "Sin franjas."
        return Decision(juego, False, "fuera_de_horario", detalle)
    slot = v.oportunidades(p.intervalo)[(ahora - v.inicio) // p.intervalo]
    if int(estado.get("fallos_consecutivos", 0)) >= max_reintentos:
        return Decision(juego, False, "reintentos_agotados", "Intentos agotados: use Recuperar de forma explícita; "
                        "la recuperación programada no los rearma.", v, slot)
    situacion = estado_del_evento(estado, v, p)
    if situacion == "completo":
        return Decision(juego, False, "evento_completo", "Resultado del sorteo procesado y predicción siguiente "
                        "publicada; no se repite la consulta de este evento.", v, slot)
    if situacion == "requiere_operador":
        return Decision(juego, False, "requiere_operador", "El último ciclo de este evento quedó en un estado que "
                        "requiere una acción explícita; repetir la consulta no lo resuelve.", v, slot)
    usado = (estado.get("horario") or {}).get("oportunidad")
    if usado == slot.isoformat():
        return Decision(juego, False, "oportunidad_usada", "La consulta de este slot ya se hizo.", v, slot)
    hasta = _instante(estado.get("proxima_consulta"))
    if estado.get("error") and hasta is not None and ahora < hasta:
        return Decision(juego, False, "espera_reintento", "Espera progresiva o Retry-After hasta " + hasta.isoformat()
                        + "; se reintenta en la primera oportunidad permitida posterior.", v, slot, hasta)
    return Decision(juego, True, "admitido", f"Oportunidad {v.tipo} del sorteo del {v.fecha_sorteo.isoformat()}.",
                    v, slot)


def confirmar(p: PoliticaHorario, admitida: Decision, ahora: datetime, estado: dict, *,
              max_reintentos: int) -> Decision:
    """Confirmación de una admisión programada en el borde de la consulta al proveedor.

    La preparación (recursos, instantánea, configuración) ocurre después de `decidir`. Solo se consulta si,
    con el reloj de ese momento, sigue admitido el MISMO slot de la misma ventana. Si cerró la franja o la
    recuperación, o el reloj pasó al slot siguiente, no se inicia la consulta y ese otro slot no se consume
    por la demora: el evento queda pendiente para su propia oportunidad."""
    if not admitida.admitido or admitida.ventana is None or admitida.oportunidad is None:
        raise ValueError("Solo se confirma una admisión programada.")
    vigente = decidir(p, admitida.juego, ahora, estado, max_reintentos=max_reintentos)
    if vigente.admitido and vigente.ventana == admitida.ventana and vigente.oportunidad == admitida.oportunidad:
        return vigente
    fin = min(admitida.oportunidad + p.intervalo, admitida.ventana.fin)
    if ahora < fin:  # mismo slot abierto, pero otra condición de `decidir` ya no admite: se informa esa
        return vigente
    return Decision(admitida.juego, False, "cierre_antes_de_consultar",
                    f"La preparación terminó a las {ahora.isoformat()}, después del cierre del slot admitido "
                    f"({admitida.oportunidad.isoformat()} a {fin.isoformat()}): no se inicia la consulta. El evento "
                    "sigue pendiente para la siguiente oportunidad permitida.", admitida.ventana, admitida.oportunidad)


# ---------------------------------------------------------------------------
# Plan del Programador de tareas
# ---------------------------------------------------------------------------

def _duracion_iso(td: timedelta) -> str:
    minutos = int(td.total_seconds() // 60)
    h, m = divmod(minutos, 60)
    return "PT" + (f"{h}H" if h else "") + (f"{m}M" if m or not h else "")


def plan_windows(p: PoliticaHorario) -> dict:
    """Disparadores semanales (`CalendarTrigger`) que abren el ciclo programado SOLO en los slots de la
    política: una repetición por franja agrupada (mismo inicio y duración) y un disparo de recuperación.
    `StartBoundary` lleva el desfase fijo de Bogotá. La duración de repetición acaba un minuto después del
    último slot, así que el fin exclusivo de la franja no dispara."""
    desfase = datetime.combine(ANCLA, time(12), zona_bogota()).strftime("%z")
    desfase = desfase[:3] + ":" + desfase[3:]
    grupos: dict[tuple, dict] = {}
    for f in p.franjas:
        n = len(Ventana(f.juego, "franja", ANCLA, datetime(2026, 1, 1, tzinfo=timezone.utc),
                        datetime(2026, 1, 1, tzinfo=timezone.utc) + f.duracion).oportunidades(p.intervalo))
        ultimo = (n - 1) * p.intervalo
        clave = (f.inicio, ultimo)
        g = grupos.setdefault(clave, {"dias": set(), "juegos": set()})
        g["dias"].add(f.dia)
        g["juegos"].add(f.juego)
    disparadores = []
    for (inicio, ultimo), g in sorted(grupos.items(), key=lambda x: (x[0][0], x[0][1])):
        disparadores.append({
            "tipo": "franja", "inicio": f"{ANCLA.isoformat()}T{_hhmm(inicio)}:00{desfase}",
            "dias": [DIAS_WINDOWS[d] for d in sorted(g["dias"])],
            "intervalo": _duracion_iso(p.intervalo) if ultimo else None,
            "duracion": _duracion_iso(ultimo + timedelta(minutes=1)) if ultimo else None,
            "juegos": [j for j in JUEGOS if j in g["juegos"]]})
    if p.recuperacion is not None:
        dias = sorted({(f.dia + 1) % 7 for f in p.franjas})
        disparadores.append({"tipo": "recuperacion", "inicio": f"{ANCLA.isoformat()}T{_hhmm(p.recuperacion)}:00{desfase}",
                             "dias": [DIAS_WINDOWS[d] for d in dias], "intervalo": None, "duracion": None,
                             "juegos": [j for j in JUEGOS if p.franjas_de(j)]})
    texto = texto_plan(disparadores)
    return {"version": VERSION, "zona": p.zona, "desfase": desfase, "politica": como_dict(p),
            "disparadores": disparadores, "texto": texto, "huella": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
            "xml_disparadores": xml_disparadores(disparadores)}


def texto_plan(disparadores: list[dict]) -> str:
    """Texto canónico que firma el plan; `fase6_tarea.ps1` lo recompone con el mismo formato."""
    lineas = [f"LP6-HORARIO/{VERSION}|{ZONA}"]
    for d in disparadores:
        lineas.append("|".join((d["tipo"], d["inicio"], ",".join(d["dias"]), d["intervalo"] or "-",
                                d["duracion"] or "-")))
    return "\n".join(lineas) + "\n"


def huella_plan(p: PoliticaHorario) -> str:
    return plan_windows(p)["huella"]


def xml_disparadores(disparadores: list[dict]) -> str:
    """Contenido de `<Triggers>` del XML de la tarea, en el orden del plan."""
    partes = []
    for d in disparadores:
        repeticion = (f"<Repetition><Interval>{d['intervalo']}</Interval><Duration>{d['duracion']}</Duration>"
                      "<StopAtDurationEnd>false</StopAtDurationEnd></Repetition>") if d["intervalo"] else ""
        dias = "".join(f"<{n} />" for n in d["dias"])
        partes.append(f"<CalendarTrigger>{repeticion}<StartBoundary>{d['inicio']}</StartBoundary><Enabled>true</Enabled>"
                      f"<ScheduleByWeek><DaysOfWeek>{dias}</DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek>"
                      "</CalendarTrigger>")
    return "".join(partes)


def disparos(plan: dict, desde: date, hasta: date) -> list[datetime]:
    """Instantes UTC en que el plan abriría el ciclo entre dos fechas locales (simulación del Programador
    para comprobar la concordancia con el núcleo; no acredita el Programador real de Windows)."""
    salida = []
    for d in plan["disparadores"]:
        inicio = datetime.fromisoformat(d["inicio"])
        intervalo = _desde_iso(d["intervalo"]) if d["intervalo"] else None
        duracion = _desde_iso(d["duracion"]) if d["duracion"] else None
        for i in range((hasta - desde).days + 1):
            fecha = desde + timedelta(days=i)
            if DIAS_WINDOWS[fecha.weekday()] not in d["dias"]:
                continue
            base = datetime.combine(fecha, inicio.timetz())
            t = base
            while True:
                salida.append(t.astimezone(timezone.utc))
                if intervalo is None:
                    break
                t += intervalo
                if t >= base + duracion:
                    break
    return sorted(salida)


def _desde_iso(texto: str) -> timedelta:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", texto)
    if not m:
        raise PoliticaNoValida("Duración ISO no admitida en el plan.")
    return timedelta(hours=int(m.group(1) or 0), minutes=int(m.group(2) or 0))


def de_configuracion(configuracion: dict) -> PoliticaHorario | None:
    """La política de una configuración operativa: None si es de la versión 1 (sin horario)."""
    if configuracion.get("version") == 1:
        return None
    return desde_dict(configuracion.get("horario"))
