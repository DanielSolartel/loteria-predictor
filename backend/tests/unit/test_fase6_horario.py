"""Fase 6: consultas automáticas limitadas por juego y franja (America/Bogota).

Reloj inyectado y proveedor sintético: ninguna prueba espera a una noche real, abre red, BD ni la
tarea de Windows. La concordancia del plan con el núcleo se comprueba simulando sus disparadores;
eso no acredita el Programador de tareas real (ver el protocolo nativo de la guía).
Semana de referencia: lunes 26 de octubre a domingo 1 de noviembre de 2026.
"""
from __future__ import annotations

import json
import os
import time as reloj_del_sistema
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from zoneinfo import ZoneInfo

import pytest

from app.api.automatizacion_dependencies import construir_automatizacion
from app.application import operacion_horario as h
from app.application.operacion_calendario import ExcepcionCalendario, calendario_defecto
from app.application.use_cases.operacion_automatica import JUEGOS, InvocacionProgramada, OperacionAutomatica
from app.core.config import Settings
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
from scripts.operacion_automatica import ejecutar

BOGOTA = ZoneInfo("America/Bogota")
POLITICA = h.propuesta_inicial()
PLAN = h.plan_windows(POLITICA)
MAXIMO = 8


def bogota(dia: int, hora: int, minuto: int = 0, segundo: int = 0, mes: int = 10) -> datetime:
    """Instante UTC de una hora local de Bogotá en la semana de referencia (dia = día de octubre)."""
    anio = 2026
    if mes == 10 and dia > 31:
        mes, dia = 11, dia - 31
    return datetime(anio, mes, dia, hora, minuto, segundo, tzinfo=BOGOTA).astimezone(timezone.utc)


def admitidos(ahora, estados=None):
    estados = estados or {}
    return [j for j in JUEGOS if h.decidir(POLITICA, j, ahora, estados.get(j, {}), max_reintentos=MAXIMO).admitido]


# ---------------------------------------------------------------------------
# Política: una sola representación validada
# ---------------------------------------------------------------------------

def test_propuesta_inicial_valida_coherente_con_el_calendario_y_estable():
    h.validar_con_calendario(POLITICA, calendario_defecto())
    assert h.desde_dict(h.como_dict(POLITICA)) == POLITICA
    assert h.como_dict(POLITICA)["recuperacion"] == "09:00" and POLITICA.intervalo_minutos == 15
    assert {(f.juego, h.DIAS[f.dia], h._hhmm(f.inicio), h._hhmm(f.fin)) for f in POLITICA.franjas} == {
        *(("MILOTO", d, "22:30", "02:00") for d in ("lunes", "martes", "jueves", "viernes")),
        *(("BALOTO", d, "23:30", "02:30") for d in ("lunes", "miercoles", "sabado")),
        *(("BALOTO_REVANCHA", d, "23:30", "02:30") for d in ("lunes", "miercoles", "sabado")),
        ("COLORLOTO", "lunes", "23:50", "02:30"), ("COLORLOTO", "jueves", "23:15", "02:30")}
    assert h.huella_plan(h.propuesta_inicial()) == PLAN["huella"]


def _dict(**cambios):
    d = h.como_dict(POLITICA)
    d.update(cambios)
    return d


@pytest.mark.parametrize("valor", [
    _dict(franjas=[]),  # vacía: no vuelve al sondeo continuo, se rechaza
    _dict(zona="America/Lima"), _dict(version=2), _dict(intervalo_minutos=4), _dict(intervalo_minutos=15.0),
    _dict(recuperacion="9:00"), _dict(recuperacion="01:00"),  # solapa con franjas que terminan a las 02:00/02:30
    _dict(franjas=[{"juego": "MILOTO", "dia": "lunes", "inicio": "22:30", "fin": "22:30"}]),
    _dict(franjas=[{"juego": "MILOTO", "dia": "lunes", "inicio": "22:30", "fin": "11:00"}]),  # más de 12 horas
    _dict(franjas=[{"juego": "MILOTO", "dia": "lunes", "inicio": "22:30", "fin": "02:00"}] * 2),
    _dict(franjas=[{"juego": "MILOTO", "dia": "lunes", "inicio": "22:30", "fin": "02:00"},
                   {"juego": "MILOTO", "dia": "martes", "inicio": "01:00", "fin": "03:00"}]),  # solapadas
    _dict(franjas=[{"juego": "MILOTO", "dia": "miércoles", "inicio": "22:30", "fin": "02:00"}]),
    _dict(franjas=[{"juego": "QUINELA", "dia": "lunes", "inicio": "22:30", "fin": "02:00"}]),
    _dict(franjas=[{"juego": "MILOTO", "dia": "lunes", "inicio": "24:00", "fin": "02:00"}]),
    _dict(franjas=[{"juego": "MILOTO", "dia": "lunes", "inicio": "22:30", "fin": "02:00", "extra": 1}]),
    {**_dict(), "ajena": True}, None, "politica"])
def test_politicas_vacias_ambiguas_o_invalidas_se_rechazan(valor):
    with pytest.raises(h.PoliticaNoValida):
        h.desde_dict(valor)


@pytest.mark.parametrize("franja", [
    {"juego": "MILOTO", "dia": "miercoles", "inicio": "22:30", "fin": "02:00"},  # sin sorteo de MiLoto
    {"juego": "BALOTO", "dia": "lunes", "inicio": "23:00", "fin": "02:00"},  # a la hora del sorteo
    {"juego": "COLORLOTO", "dia": "lunes", "inicio": "23:30", "fin": "02:00"}])  # antes de las 23:40
def test_franja_sin_sorteo_o_anterior_al_sorteo_se_rechaza(franja):
    with pytest.raises(h.PoliticaNoValida):
        h.validar_con_calendario(h.desde_dict(_dict(franjas=[franja])), calendario_defecto())


# ---------------------------------------------------------------------------
# Admisión con reloj inyectado
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ahora", [bogota(26, 17), bogota(26, 17, 30), bogota(32, 14), bogota(32, 17), bogota(32, 20),
                                   bogota(27, 14), bogota(28, 12)])
def test_lunes_por_la_tarde_y_domingo_por_la_tarde_sin_consultas_ni_disparos(ahora):
    assert admitidos(ahora) == []
    hora = ahora.replace(minute=0, second=0)
    assert not [t for t in h.disparos(PLAN, date(2026, 10, 25), date(2026, 11, 2)) if hora <= t < hora + timedelta(hours=1)]


def test_jueves_por_la_noche_miloto_y_colorloto_por_su_hora_de_inicio():
    assert admitidos(bogota(29, 22, 40)) == ["MILOTO"]  # ColorLoto empieza a las 23:15
    assert admitidos(bogota(29, 23, 20)) == ["MILOTO", "COLORLOTO"]
    for j in ("BALOTO", "BALOTO_REVANCHA"):
        assert h.decidir(POLITICA, j, bogota(29, 23, 20), {}, max_reintentos=MAXIMO).motivo == "fuera_de_horario"


def test_sabado_por_la_noche_solo_baloto_y_revancha():
    assert admitidos(bogota(31, 23, 45)) == ["BALOTO", "BALOTO_REVANCHA"]
    assert admitidos(bogota(31, 22, 45)) == []


def test_martes_de_madrugada_franjas_del_lunes_sin_cambiar_la_fecha_del_evento():
    ahora = bogota(27, 1, 0)
    assert admitidos(ahora) == list(JUEGOS)
    for j in JUEGOS:
        d = h.decidir(POLITICA, j, ahora, {}, max_reintentos=MAXIMO)
        assert d.ventana.fecha_sorteo == date(2026, 10, 26) and d.ventana.tipo == "franja"
    assert admitidos(bogota(27, 2, 10)) == ["BALOTO", "BALOTO_REVANCHA", "COLORLOTO"]  # MiLoto cerró a las 02:00


def test_domingo_de_madrugada_y_recuperacion_solo_lo_pendiente_del_sabado():
    assert admitidos(bogota(32, 1, 0)) == ["BALOTO", "BALOTO_REVANCHA"]
    completo = {"estado": "correcto", "fecha_ultimo_sorteo": "2026-10-31"}
    assert admitidos(bogota(32, 9, 5), {"BALOTO": completo}) == ["BALOTO_REVANCHA"]
    d = h.decidir(POLITICA, "BALOTO_REVANCHA", bogota(32, 9, 5), {}, max_reintentos=MAXIMO)
    assert (d.ventana.tipo, d.ventana.fecha_sorteo, d.oportunidad) == ("recuperacion", date(2026, 10, 31), bogota(32, 9))
    assert h.decidir(POLITICA, "BALOTO", bogota(32, 9, 5), completo, max_reintentos=MAXIMO).motivo == "evento_completo"
    # La recuperación es un único slot: a las 09:15 ya no hay oportunidad, tampoco para los pendientes.
    assert admitidos(bogota(32, 9, 15)) == []
    # No es un sondeo general: MiLoto y ColorLoto no tienen sorteo el sábado.
    assert h.decidir(POLITICA, "MILOTO", bogota(32, 9, 5), {}, max_reintentos=MAXIMO).motivo == "fuera_de_horario"


@pytest.mark.parametrize("ahora,juego,admitido,slot", [
    (bogota(29, 23, 15), "COLORLOTO", True, bogota(29, 23, 15)),
    (bogota(29, 23, 14, 59), "COLORLOTO", False, None),
    (bogota(30, 2, 29, 59), "COLORLOTO", True, bogota(30, 2, 15)),
    (bogota(30, 2, 30), "COLORLOTO", False, None),  # fin exclusivo
    (bogota(29, 22, 30), "MILOTO", True, bogota(29, 22, 30)),
    (bogota(30, 2, 0), "MILOTO", False, None),
    (bogota(30, 1, 59, 59), "MILOTO", True, bogota(30, 1, 45)),
    (bogota(30, 9, 0), "MILOTO", True, bogota(30, 9, 0)), (bogota(30, 8, 59, 59), "MILOTO", False, None)])
def test_limites_exactos_inicio_inclusivo_fin_exclusivo_y_slots_desde_el_inicio(ahora, juego, admitido, slot):
    d = h.decidir(POLITICA, juego, ahora, {}, max_reintentos=MAXIMO)
    assert d.admitido is admitido and (d.oportunidad == slot if admitido else True)


def test_zona_del_equipo_distinta_de_bogota_no_cambia_la_admision(monkeypatch):
    casos = [bogota(29, 23, 20), bogota(27, 1, 0), bogota(26, 17), bogota(32, 9, 5)]
    esperado = [admitidos(t) for t in casos]
    if hasattr(reloj_del_sistema, "tzset"):
        monkeypatch.setenv("TZ", "Asia/Tokyo")
        reloj_del_sistema.tzset()
    try:
        assert [admitidos(t) for t in casos] == esperado
        tokio = [t.astimezone(timezone(timedelta(hours=9))) for t in casos]  # mismo instante con otro desfase
        assert [admitidos(t) for t in tokio] == esperado
    finally:
        monkeypatch.delenv("TZ", raising=False)
        if hasattr(reloj_del_sistema, "tzset"):
            reloj_del_sistema.tzset()


def test_varias_franjas_simultaneas_en_orden_de_inicio():
    ahora = bogota(26, 23, 55)
    decisiones = {j: h.decidir(POLITICA, j, ahora, {}, max_reintentos=MAXIMO) for j in JUEGOS}
    orden = sorted(JUEGOS, key=lambda j: (decisiones[j].ventana.inicio, JUEGOS.index(j)))
    assert orden == ["MILOTO", "BALOTO", "BALOTO_REVANCHA", "COLORLOTO"]
    assert {j: d.oportunidad for j, d in decisiones.items()} == {
        "MILOTO": bogota(26, 23, 45), "BALOTO": bogota(26, 23, 45), "BALOTO_REVANCHA": bogota(26, 23, 45),
        "COLORLOTO": bogota(26, 23, 50)}


def test_estados_del_evento_reintentos_y_bloqueos():
    ahora = bogota(29, 23, 0)
    franja = bogota(29, 22, 30)
    def d(estado):
        return h.decidir(POLITICA, "MILOTO", ahora, estado, max_reintentos=MAXIMO)
    # Resultado aún no publicado: sigue pendiente; el mismo slot no se repite, el siguiente sí.
    retrasado = {"estado": "resultado_retrasado", "fecha_ultimo_sorteo": "2026-10-27", "ultima_comprobacion": ahora.isoformat(),
                 "horario": {"oportunidad": bogota(29, 23, 0).isoformat()}}
    assert d(retrasado).motivo == "oportunidad_usada"
    assert h.decidir(POLITICA, "MILOTO", bogota(29, 23, 15), retrasado, max_reintentos=MAXIMO).admitido
    # Resultado del jueves procesado y predicción siguiente publicada: no se repite.
    assert d({"estado": "correcto", "fecha_ultimo_sorteo": "2026-10-29"}).motivo == "evento_completo"
    # «Sin error» con el resultado anterior no es un evento completo.
    assert d({"estado": "correcto", "fecha_ultimo_sorteo": "2026-10-27"}).admitido
    # Huecos: la reparación continúa en las oportunidades siguientes; no se marca al día.
    assert d({"estado": "historico_incompleto", "fecha_ultimo_sorteo": "2026-10-29",
              "ultima_comprobacion": franja.isoformat()}).admitido
    # Revisión pendiente u otros bloqueos de este evento: no se repite y la recuperación tampoco los ignora.
    bloqueado = {"estado": "revision_pendiente", "ultima_comprobacion": (franja + timedelta(minutes=5)).isoformat()}
    assert d(bloqueado).motivo == "requiere_operador"
    assert h.decidir(POLITICA, "MILOTO", bogota(30, 9, 0), bloqueado, max_reintentos=MAXIMO).motivo == "requiere_operador"
    # Un bloqueo de un evento anterior no impide consultar el nuevo.
    assert d({**bloqueado, "ultima_comprobacion": bogota(27, 23, 0).isoformat()}).admitido
    # Caída de internet con espera progresiva o Retry-After: se espera a la primera oportunidad posterior.
    caida = {"estado": "fallo_consulta", "error": {"tipo": "ConnectError"}, "fallos_consecutivos": 2,
             "proxima_consulta": bogota(29, 23, 40).isoformat(), "ultima_comprobacion": franja.isoformat()}
    assert d(caida).motivo == "espera_reintento"
    assert h.decidir(POLITICA, "MILOTO", bogota(29, 23, 45), caida, max_reintentos=MAXIMO).admitido
    lejana = {**caida, "proxima_consulta": bogota(30, 5, 0).isoformat()}  # Retry-After más allá de la franja
    assert h.decidir(POLITICA, "MILOTO", bogota(30, 1, 45), lejana, max_reintentos=MAXIMO).motivo == "espera_reintento"
    assert h.decidir(POLITICA, "MILOTO", bogota(30, 9, 0), lejana, max_reintentos=MAXIMO).admitido
    # Intentos agotados: la recuperación de las 09:00 no los rearma.
    agotado = {**caida, "estado": "reintentos_agotados", "fallos_consecutivos": MAXIMO}
    assert h.decidir(POLITICA, "MILOTO", bogota(30, 9, 0), agotado, max_reintentos=MAXIMO).motivo == "reintentos_agotados"


def test_equipo_apagado_o_sin_sesion_no_recupera_a_una_hora_arbitraria():
    # Se perdieron la franja del lunes y la recuperación del martes: al encender el martes a las 14:00 no hay
    # consulta; el pendiente espera a la siguiente oportunidad (la franja del martes a las 22:30).
    pendiente = {"estado": "fallo_consulta", "fecha_ultimo_sorteo": "2026-10-23"}
    assert h.decidir(POLITICA, "MILOTO", bogota(27, 14), pendiente, max_reintentos=MAXIMO).motivo == "fuera_de_horario"
    siguiente, ventana = h.proxima_oportunidad(POLITICA, "MILOTO", bogota(27, 14))
    assert siguiente == bogota(27, 22, 30) and ventana.fecha_sorteo == date(2026, 10, 27)
    # Al reanudar a mitad de franja solo cuenta el slot vigente (una consulta, sin ponerse al día).
    d = h.decidir(POLITICA, "MILOTO", bogota(28, 0, 52), pendiente, max_reintentos=MAXIMO)
    assert d.admitido and d.oportunidad == bogota(28, 0, 45)


# ---------------------------------------------------------------------------
# Plan del Programador frente al selector del núcleo
# ---------------------------------------------------------------------------

def _oportunidades(desde: date, hasta: date) -> set[datetime]:
    todas = set()
    for j in JUEGOS:
        for v in h.ventanas(POLITICA, j, desde, hasta):
            todas.update(v.oportunidades(POLITICA.intervalo))
    return todas


def test_plan_y_nucleo_coinciden_slot_a_slot_durante_dos_semanas():
    desde, hasta = date(2026, 10, 26), date(2026, 11, 8)
    disparos = h.disparos(PLAN, desde, hasta)
    abiertos = {t for t in disparos if desde <= t.astimezone(BOGOTA).date() <= hasta}
    esperado = {t for t in _oportunidades(desde - timedelta(days=1), hasta) if desde <= t.astimezone(BOGOTA).date() <= hasta}
    assert abiertos == esperado
    # Cada disparo admite al menos un juego sin trabajo hecho, salvo que su evento ya esté completo.
    assert all(admitidos(t) for t in abiertos)
    # El fin exclusivo de una franja no es una oportunidad de ese juego (si hay disparo a esa hora,
    # es un slot de otro juego cuya franja sigue abierta).
    for v in (v for j in JUEGOS for v in h.ventanas(POLITICA, j, desde, hasta) if v.tipo == "franja"):
        assert v.fin not in v.oportunidades(POLITICA.intervalo)
        assert h.decidir(POLITICA, v.juego, v.fin, {}, max_reintentos=MAXIMO).ventana != v


def test_xml_del_plan_sin_inicio_de_sesion_ni_repeticion_sin_fin():
    raiz = ET.fromstring("<Triggers>" + PLAN["xml_disparadores"] + "</Triggers>")
    assert [n.tag for n in raiz] == ["CalendarTrigger"] * len(PLAN["disparadores"])
    assert raiz.find("LogonTrigger") is None and raiz.find("TimeTrigger") is None and raiz.find("BootTrigger") is None
    for n, d in zip(raiz, PLAN["disparadores"]):
        assert n.findtext("StartBoundary") == d["inicio"] and d["inicio"].endswith("-05:00")
        assert [x.tag for x in n.find("ScheduleByWeek/DaysOfWeek")] == d["dias"]
        assert n.findtext("ScheduleByWeek/WeeksInterval") == "1"
        rep = n.find("Repetition")
        if d["intervalo"]:
            assert (rep.findtext("Interval"), rep.findtext("Duration"), rep.findtext("StopAtDurationEnd")) == (
                d["intervalo"], d["duracion"], "false")
        else:
            assert rep is None
    assert [(d["tipo"], d["inicio"][11:16], d["dias"], d["duracion"]) for d in PLAN["disparadores"]] == [
        ("franja", "22:30", ["Monday", "Tuesday", "Thursday", "Friday"], "PT3H16M"),
        ("franja", "23:15", ["Thursday"], "PT3H1M"),
        ("franja", "23:30", ["Monday", "Wednesday", "Saturday"], "PT2H46M"),
        ("franja", "23:50", ["Monday"], "PT2H31M"),
        ("recuperacion", "09:00", ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], None)]
    assert PLAN["texto"].splitlines()[0] == "LP6-HORARIO/1|America/Bogota"
    otra = h.desde_dict(_dict(intervalo_minutos=20))
    assert h.huella_plan(otra) != PLAN["huella"]


# ---------------------------------------------------------------------------
# Ciclo programado del caso de uso
# ---------------------------------------------------------------------------

class Reloj:
    def __init__(self, ahora):
        self.ahora = ahora

    def __call__(self):
        return self.ahora


class Proveedor:
    """Adquisición y predicción sintéticas. `publicados[j]` = (último sorteo, fecha) que entrega la sincronización."""

    def __init__(self, cargados, publicados, *, errores=None, hook=None, revision=None, huecos=None):
        self.cargados, self.publicados = dict(cargados), dict(publicados)
        self.errores, self.hook = errores or {}, hook
        self.revision, self.huecos = revision or [], huecos or {}
        self.llamadas, self.emitidas = [], {}

    def paso(self, juego, paso):
        self.llamadas.append((juego, paso))
        if self.hook:
            self.hook(juego, paso)
        if (juego, paso) in self.errores:
            raise self.errores[(juego, paso)]

    def juegos_llamados(self):
        return list(dict.fromkeys(j for j, _ in self.llamadas))

    @contextmanager
    def por_juego(self, juego):
        self.paso(juego, "abrir")
        yield _Dep(self, juego)


class _Dep:
    def __init__(self, p, juego):
        self.p, self.juego = p, juego

    def instantanea(self):
        self.p.paso(self.juego, "instantanea")
        numero, fecha = self.p.cargados[self.juego]
        return {"ultimo_sorteo": numero, "fecha": fecha, "sorteos": numero, "primer_sorteo": 1,
                "huecos": self.p.huecos.get(self.juego, 0)}

    def configuracion(self):
        self.p.paso(self.juego, "configuracion")
        return {"juego": self.juego, "modelo": {"id": "simulado", "registrado": {"clave": "a" * 64, "numero": 1}}}

    def sincronizar(self, **_):
        self.p.paso(self.juego, "sincronizar")
        self.p.cargados[self.juego] = self.p.publicados[self.juego]
        return {"estado": "completado", "pendientes_revision": list(self.p.revision)}

    def reconciliar(self):
        self.p.paso(self.juego, "reconciliar")
        return {"estado": "correcto"}

    def generar(self, configuracion_congelada, objetivo, fecha_limite, ahora):
        self.p.paso(self.juego, "generar")
        assert ahora < fecha_limite
        clave = (self.juego, objetivo)
        reutilizado = clave in self.p.emitidas
        self.p.emitidas[clave] = fecha_limite
        return {"estado": "reutilizado" if reutilizado else "terminado", "clave": "%064x" % objetivo}


CARGADOS = {"BALOTO": (500, "2026-10-28"), "BALOTO_REVANCHA": (500, "2026-10-28"),
            "MILOTO": (700, "2026-10-27"), "COLORLOTO": (300, "2026-10-26")}
JUEVES = {**CARGADOS, "MILOTO": (701, "2026-10-29"), "COLORLOTO": (301, "2026-10-29")}


def _servicio(tmp_path, ahora, proveedor=None, *, version=2, calendarios=None, politica=POLITICA):
    almacen = AlmacenAutomatizacion(tmp_path / "operacion")
    conf = {"activada": True, "pausada": False}
    if version == 2:
        conf.update(version=2, horario=h.como_dict(politica))
    almacen.guardar_configuracion(conf)
    proveedor = proveedor or Proveedor(CARGADOS, JUEVES)
    reloj = Reloj(ahora)
    return OperacionAutomatica(almacen, proveedor, reloj=reloj, calendarios=calendarios), almacen, proveedor, reloj


def _programado(op, plan=PLAN["huella"]):
    return op.ciclo(programado=InvocacionProgramada(plan))


def _bytes(directorio):
    return {p.relative_to(directorio).as_posix(): p.read_bytes() for p in sorted(directorio.rglob("*")) if p.is_file()}


def test_jueves_por_la_noche_el_ciclo_solo_abre_recursos_de_miloto_y_colorloto(tmp_path):
    op, almacen, p, _ = _servicio(tmp_path, bogota(29, 23, 20))
    e = _programado(op)
    assert e["origen"] == "programado" and e["plan"] == PLAN["huella"] and e["estado"] == "exito"
    assert p.juegos_llamados() == ["MILOTO", "COLORLOTO"]
    assert e["horario"]["BALOTO"]["motivo"] == "fuera_de_horario"
    for j in ("MILOTO", "COLORLOTO"):
        r = almacen.estado(j)
        assert r["estado"] == "correcto" and r["horario"]["oportunidad"] == bogota(29, 23, 15).isoformat()
        assert r["horario"]["evento"] == "2026-10-29"
    # El resultado del jueves ya está procesado y la predicción siguiente publicada: no se repite el evento.
    p.llamadas.clear()
    op.reloj.ahora = bogota(29, 23, 30)
    assert _programado(op)["estado"] == "sin_consultas_debidas" and p.llamadas == []
    op.reloj.ahora = bogota(30, 9, 0)  # recuperación: nada pendiente
    assert _programado(op)["estado"] == "sin_consultas_debidas" and p.llamadas == []


def test_mismo_slot_dos_veces_e_idempotencia_de_la_publicacion(tmp_path):
    p = Proveedor(CARGADOS, {**CARGADOS})  # el resultado del jueves aún no se publica
    op, almacen, _, _ = _servicio(tmp_path, bogota(29, 22, 35), p)
    e = _programado(op)
    assert e["juegos"]["MILOTO"]["estado"] == "resultado_retrasado" and ("MILOTO", "generar") not in p.llamadas
    p.llamadas.clear()
    op.reloj.ahora = bogota(29, 22, 44)  # mismo slot (22:30): no se repite
    assert _programado(op)["horario"]["MILOTO"]["motivo"] == "oportunidad_usada" and p.llamadas == []
    p.publicados["MILOTO"] = (701, "2026-10-29")
    op.reloj.ahora = bogota(29, 22, 45)
    assert _programado(op)["juegos"]["MILOTO"]["estado"] == "correcto"
    assert list(p.emitidas) == [("MILOTO", 702)]
    # Una comprobación manual posterior reutiliza la predicción ya publicada.
    assert op.ciclo(juegos=["MILOTO"], forzar=True, origen="comando")["juegos"]["MILOTO"]["prediccion"]["estado"] == "reutilizado"


def test_cruce_del_fin_durante_un_ciclo_de_varios_juegos(tmp_path):
    """Martes 01:59: MiLoto (hasta 02:00) empieza a tiempo y termina después; los demás se revalidan
    con el reloj de su turno y no se inician porque sus franjas (hasta 02:30) ya cerraron."""
    p = Proveedor(CARGADOS, {**CARGADOS, "MILOTO": (701, "2026-10-26")})
    op, almacen, _, reloj = _servicio(tmp_path, bogota(27, 1, 59))
    op.adaptador = p

    def avanzar(juego, paso):
        if juego == "MILOTO" and paso == "reconciliar":
            reloj.ahora = bogota(27, 2, 31)  # la publicación de MiLoto sigue y termina fuera de franja
    p.hook = avanzar
    e = _programado(op)
    assert p.juegos_llamados() == ["MILOTO"]
    assert e["juegos"]["MILOTO"]["estado"] == "correcto" and ("MILOTO", "generar") in p.llamadas
    for j in ("BALOTO", "BALOTO_REVANCHA", "COLORLOTO"):
        assert e["juegos"][j]["estado"] == "omitido_horario" and e["juegos"][j]["horario"]["motivo"] == "fuera_de_horario"
        assert almacen.estado(j).get("horario") is None  # no consumió ninguna oportunidad
    assert e["estado"] == "exito"


def test_huecos_revision_caida_retry_after_e_intentos_agotados_en_el_ciclo(tmp_path):
    class Caida(RuntimeError):
        def __init__(self):
            super().__init__("sin conexion")
            self.response = type("R", (), {"status_code": 503, "headers": {"Retry-After": "3600"}})()
    p = Proveedor(CARGADOS, JUEVES, errores={("COLORLOTO", "sincronizar"): Caida()}, huecos={"MILOTO": 2})
    op, almacen, _, _ = _servicio(tmp_path, bogota(29, 23, 20), p)
    e = _programado(op)
    assert e["juegos"]["MILOTO"]["estado"] == "historico_incompleto"
    assert e["juegos"]["COLORLOTO"]["estado"] == "fallo_consulta"
    colorloto = almacen.estado("COLORLOTO")
    assert datetime.fromisoformat(colorloto["proxima_consulta"]) >= bogota(29, 23, 20) + timedelta(seconds=3600)
    p.llamadas.clear()
    op.reloj.ahora = bogota(29, 23, 30)
    siguiente = _programado(op)
    assert siguiente["horario"]["COLORLOTO"]["motivo"] == "espera_reintento"
    assert p.juegos_llamados() == ["MILOTO"]  # los huecos siguen reparándose en su franja
    # Revisión pendiente: el evento deja de consultarse y la recuperación tampoco lo reintenta.
    p.huecos.clear()
    p.revision = ["f" * 64]
    op.reloj.ahora = bogota(29, 23, 45)
    assert _programado(op)["juegos"]["MILOTO"]["estado"] == "revision_pendiente"
    p.llamadas.clear()
    for ahora in (bogota(30, 0, 0), bogota(30, 9, 0)):
        op.reloj.ahora = ahora
        assert _programado(op)["horario"]["MILOTO"]["motivo"] == "requiere_operador"
    assert "MILOTO" not in p.juegos_llamados()
    # Intentos agotados: la recuperación no los rearma.
    almacen.guardar_estado("COLORLOTO", {**almacen.estado("COLORLOTO"), "fallos_consecutivos": MAXIMO})
    op.reloj.ahora = bogota(30, 9, 0)
    r = _programado(op)
    assert r["horario"]["COLORLOTO"]["motivo"] == "reintentos_agotados" and "COLORLOTO" in r["reintentos_agotados"]
    assert almacen.estado("COLORLOTO")["fallos_consecutivos"] == MAXIMO


def test_empezar_mas_tarde_no_amplia_el_plazo_de_emision(tmp_path):
    """Lunes sin publicar hasta el martes 22:40 (franja del martes): el sorteo del martes ya empezó a las
    22:00 y la emisión para él queda bloqueada aunque la consulta sea admitida."""
    p = Proveedor(CARGADOS, {**CARGADOS, "MILOTO": (701, "2026-10-26")})
    op, _, _, _ = _servicio(tmp_path, bogota(27, 22, 40), p)
    r = _programado(op)["juegos"]["MILOTO"]
    assert r["estado"] == "resultado_retrasado" and r["fecha_objetivo"] == "2026-10-27"
    assert ("MILOTO", "generar") not in p.llamadas


@pytest.mark.parametrize("verificada,estado", [(True, "correcto"), (False, "resultado_retrasado")])
def test_calendario_excepcional_verificado_o_no(tmp_path, verificada, estado):
    """Las franjas son semanales: una excepción no las mueve. El plazo de emisión sigue el calendario de
    sorteo con su excepción; una excepción sin verificar bloquea la emisión (estado existente)."""
    calendarios = calendario_defecto()
    excepcion = ExcepcionCalendario(date(2026, 10, 30), time(21), time(21, 15), "Cambio sintético",
                                    "https://example.invalid/fuente", verificada)
    calendarios["MILOTO"] = calendarios["MILOTO"].__class__(**{**calendarios["MILOTO"].__dict__, "excepciones": (excepcion,)})
    op, almacen, p, _ = _servicio(tmp_path, bogota(29, 23, 20), calendarios=calendarios)
    r = _programado(op)["juegos"]["MILOTO"]
    assert r["estado"] == estado
    if verificada:  # el plazo de emisión sigue el calendario de sorteo con su excepción (viernes 21:00)
        assert p.emitidas[("MILOTO", 702)] == bogota(30, 21)
    else:  # sin emisión; la franja siguiente vuelve a comprobar (no es un evento completo)
        assert ("MILOTO", 702) not in p.emitidas and "no está verificado" in r["motivo"]
        op.reloj.ahora = bogota(29, 23, 45)
        assert _programado(op)["juegos"]["MILOTO"]["estado"] == "resultado_retrasado" and ("MILOTO", 702) not in p.emitidas


def test_configuracion_antigua_plan_divergente_u_origen_sin_plan_no_consultan(tmp_path):
    op, almacen, p, _ = _servicio(tmp_path, bogota(29, 23, 20), version=1)
    antes = _bytes(tmp_path / "operacion")
    assert _programado(op)["estado"] == "horario_no_configurado"
    assert p.llamadas == [] and _bytes(tmp_path / "operacion") == antes  # leer no migra
    assert op.panel()["horario"]["estado"] == "sin_migrar" and _bytes(tmp_path / "operacion") == antes
    # Compatibilidad: la comprobación manual de la versión 1 sigue funcionando como antes.
    assert op.ciclo(juegos=["MILOTO"], origen="comando")["juegos"]["MILOTO"]["estado"] == "correcto"
    op2, _, p2, _ = _servicio(tmp_path / "otra", bogota(29, 23, 20))
    assert _programado(op2, "0" * 64)["estado"] == "plan_divergente" and p2.llamadas == []
    with pytest.raises(ValueError):
        op2.ciclo(origen="programado")
    with pytest.raises(ValueError):
        InvocacionProgramada("no-es-una-huella")
    with pytest.raises(ValueError):
        op2.ciclo(juegos=["MILOTO"], programado=InvocacionProgramada(PLAN["huella"]))
    assert p2.llamadas == []


@pytest.mark.parametrize("conf", [
    {"version": 2}, {"version": 2, "horario": {"franjas": []}}, {"version": 1, "horario": h.como_dict(POLITICA)},
    {"version": 3, "horario": h.como_dict(POLITICA)},
    {"version": 2, "horario": {**h.como_dict(POLITICA), "franjas": []}}])
def test_configuracion_no_valida_se_rechaza_sin_volver_al_sondeo(tmp_path, conf):
    almacen = AlmacenAutomatizacion(tmp_path / "operacion")
    with pytest.raises(ValueError):
        almacen.guardar_configuracion({"activada": True, "pausada": False, **conf})
    (tmp_path / "operacion").mkdir(parents=True, exist_ok=True)
    (tmp_path / "operacion" / "configuracion.json").write_text(
        json.dumps({"activada": True, "pausada": False, "juegos": list(JUEGOS), **conf}), encoding="utf-8")
    p = Proveedor(CARGADOS, JUEVES)
    op = OperacionAutomatica(almacen, p, reloj=Reloj(bogota(29, 23, 20)))
    with pytest.raises(ValueError):
        _programado(op)
    assert p.llamadas == []


def test_panel_muestra_franjas_proxima_oportunidad_y_motivo_sin_escribir(tmp_path):
    op, almacen, p, _ = _servicio(tmp_path, bogota(26, 17))
    almacen.actualizar_configuracion({"juegos": ["BALOTO", "MILOTO", "COLORLOTO"]})
    antes = _bytes(tmp_path / "operacion")
    panel = op.panel()
    assert _bytes(tmp_path / "operacion") == antes and p.llamadas == []
    hz = panel["horario"]
    assert hz["estado"] == "valida" and hz["huella_plan"] == PLAN["huella"]
    assert hz["juegos"]["BALOTO_REVANCHA"]["habilitado_en_nucleo"] is False
    assert hz["juegos"]["BALOTO_REVANCHA"]["motivo"] == "deshabilitado"
    assert hz["juegos"]["MILOTO"]["motivo"] == "fuera_de_horario"
    assert hz["juegos"]["MILOTO"]["proxima_oportunidad"] == bogota(26, 22, 30).isoformat()
    assert hz["juegos"]["COLORLOTO"]["proxima_oportunidad"] == bogota(26, 23, 50).isoformat()
    assert {f["dia"] for f in hz["juegos"]["COLORLOTO"]["franjas"]} == {"lunes", "jueves"}


def test_panel_web_presenta_el_horario(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.automatizacion_dependencies import get_automatizacion, get_lanzador_automatizacion
    from app.api.web.routers import automatizacion

    op, _, _, _ = _servicio(tmp_path, bogota(29, 23, 20))
    app = FastAPI()
    app.include_router(automatizacion.router)
    app.dependency_overrides[get_automatizacion] = lambda: op
    app.dependency_overrides[get_lanzador_automatizacion] = lambda: (lambda f: None)
    texto = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 45000)).get("/automatizacion").text
    assert 'data-horario="valida"' in texto and "Horario de consulta automática" in texto
    assert 'data-juego-horario="MILOTO" data-motivo="admitido"' in texto
    assert 'data-juego-horario="BALOTO" data-motivo="fuera_de_horario"' in texto
    assert "jueves 23:15–02:30 (día siguiente)" in texto and PLAN["huella"] in texto


# ---------------------------------------------------------------------------
# CLI: modos explícitos, plan de la tarea y migración
# ---------------------------------------------------------------------------

class SinAcceso:
    def por_juego(self, codigo):
        raise AssertionError("Estas órdenes no abren recursos de un juego")


@pytest.fixture
def cli(tmp_path):
    backend = tmp_path / "worktree" / "backend"
    backend.mkdir(parents=True)
    ajustes = Settings(_env_file=None, directorio_automatizacion="storage/automatizacion",
                       database_url="postgresql+psycopg://u:MARCADOR_PRIVADO@127.0.0.1:1/pruebas")
    ruta = tmp_path / "operacion.json"

    def llamar(*args):
        out, err = StringIO(), StringIO()
        codigo = ejecutar(["--config", str(ruta), *args], ajustes=ajustes, backend=backend, salida=out, errores=err,
                          servicio_factory=lambda **kw: construir_automatizacion(**kw, adaptador=SinAcceso()))
        assert "MARCADOR_PRIVADO" not in out.getvalue() + err.getvalue()
        return codigo, out.getvalue(), err.getvalue()
    assert llamar("preparar", "--confirmar-destinos")[0] == 0
    assert llamar("reanudar")[0] == 0
    return backend, ruta, llamar


def test_cli_modos_explicitos_y_rechazos_sin_consultar(cli):
    backend, _, llamar = cli
    assert llamar("ciclo")[0] == 2  # la acción de la tarea anterior: no consulta
    assert llamar("ciclo", "--programado")[0] == 2
    assert llamar("ciclo", "--programado", "--plan", PLAN["huella"], "--juego", "MILOTO")[0] == 2
    assert llamar("ciclo", "--manual", "--plan", PLAN["huella"])[0] == 2
    codigo, out, _ = llamar("ciclo", "--programado", "--plan", PLAN["huella"])
    assert codigo == 4 and json.loads(out)["estado"] == "horario_no_configurado"
    assert llamar("horario", "plan")[0] == 2


def test_cli_migrar_es_explicito_idempotente_y_el_plan_coincide(cli, tmp_path):
    backend, _, llamar = cli
    store = backend / "storage" / "automatizacion" / "configuracion.json"
    v1 = store.read_bytes()
    assert json.loads(v1)["version"] == 1
    assert llamar("estado")[0] == 0 and store.read_bytes() == v1  # leer no migra
    assert llamar("horario", "migrar")[0] == 2 and store.read_bytes() == v1
    codigo, out, _ = llamar("horario", "migrar", "--confirmar")
    migrada = json.loads(out)
    assert codigo == 0 and migrada["estado"] == "migrada" and migrada["anterior"] == 1
    assert (migrada["activada"], migrada["pausada"]) == (True, False)  # no activa ni pausa nada
    assert migrada["huella_plan"] == PLAN["huella"]
    v2 = store.read_bytes()
    assert json.loads(llamar("horario", "migrar", "--confirmar")[1])["estado"] == "reutilizada" and store.read_bytes() == v2
    codigo, out, _ = llamar("horario", "plan")
    assert codigo == 0 and json.loads(out) == json.loads(json.dumps(PLAN))
    destino = tmp_path / "plan.json"
    assert llamar("horario", "plan", "--salida", str(destino))[0] == 0
    assert json.loads(destino.read_text(encoding="utf-8"))["huella"] == PLAN["huella"]
    assert llamar("horario", "plan", "--salida", str(destino))[0] == 3  # no sobrescribe
    assert store.read_bytes() == v2
