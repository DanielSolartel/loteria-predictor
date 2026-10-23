"""Calendario y anterioridad: reloj fijo, sin proveedor, BD ni ML reales."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.application import operacion_calendario as cal


def instante(texto):
    return datetime.fromisoformat(texto)


@pytest.mark.parametrize("codigo,dias,hora", [
    ("BALOTO", (0, 2, 5), time(23)),
    ("BALOTO_REVANCHA", (0, 2, 5), time(23)),
    ("MILOTO", (0, 1, 3, 4), time(22)),
    ("COLORLOTO", (0, 3), time(23)),
])
def test_calendarios_de_fuentes_oficiales_con_zona_y_dias(codigo, dias, hora):
    c = cal.calendario_defecto()[codigo]
    assert c.dias_semana == dias and c.hora_local == hora and c.verificado
    assert c.zona == "America/Bogota" and c.fuente_url.startswith("https://baloto.com/")


def test_revancha_conserva_identidad_aunque_comparte_fecha_con_baloto():
    calendarios = cal.calendario_defecto()
    b = cal.evento_en_fecha(calendarios["BALOTO"], date(2026, 10, 19))
    r = cal.evento_en_fecha(calendarios["BALOTO_REVANCHA"], date(2026, 10, 19))
    assert b.instante == r.instante
    assert b.juego == "BALOTO" and r.juego == "BALOTO_REVANCHA" and b != r


@pytest.mark.parametrize("fecha,inicio_utc", [
    (date(2026, 10, 19), "2026-10-20T04:40:00+00:00"),
    (date(2026, 10, 22), "2026-10-23T04:00:00+00:00"),
])
def test_colorloto_tiene_hora_distinta_lunes_y_jueves(fecha, inicio_utc):
    e = cal.evento_en_fecha(cal.calendario_defecto()["COLORLOTO"], fecha)
    assert e.instante == instante(inicio_utc) and e.fin_ventana == e.instante


def test_miloto_utiliza_pagina_especifica_y_conserva_discrepancia_portada():
    c = cal.calendario_defecto()["MILOTO"]
    e = cal.evento_en_fecha(c, date(2026, 10, 20))
    assert e.instante == instante("2026-10-21T03:00:00+00:00")
    assert e.fin_ventana == instante("2026-10-21T03:15:00+00:00")
    assert "23:00" in c.observaciones and "22:00" in c.observaciones
    assert e.fuente_url.endswith("/miloto/que-es-miloto/")


def test_dia_sin_sorteo_no_crea_evento_ni_autoriza_emitir():
    c = cal.calendario_defecto()["BALOTO"]
    assert cal.evento_en_fecha(c, date(2026, 10, 20)) is None
    assert not cal.admisible_emitir(c, date(2026, 10, 20), instante("2026-10-20T12:00:00+00:00"))


def test_limite_utc_no_se_confunde_con_fecha_de_bogota():
    c = cal.calendario_defecto()["BALOTO"]
    antes = instante("2026-10-20T03:59:59+00:00")
    e = cal.proximo_evento(c, antes)
    assert e.fecha_local == date(2026, 10, 19)
    assert e.instante == instante("2026-10-20T04:00:00+00:00")
    assert cal.admisible_emitir(c, e.fecha_local, antes)
    assert not cal.admisible_emitir(c, e.fecha_local, e.instante)
    assert cal.ultimo_evento(c, e.instante) == e
    assert cal.proximo_evento(c, e.instante).fecha_local == date(2026, 10, 21)
    assert cal.proximo_evento(c, e.instante, incluir_actual=True) == e


def test_publicacion_tardia_con_bd_atrasada_no_reabre_plazo():
    c = cal.calendario_defecto()["MILOTO"]
    objetivo = date(2026, 10, 20)
    despues = instante("2026-10-21T03:01:00+00:00")
    # Aún dentro de la ventana oficial: ya no es seguro emitir.
    assert not cal.admisible_emitir(c, objetivo, despues, resultado_conocido=False)
    e = cal.evento_en_fecha(c, objetivo)
    assert cal.clasificar(e, despues) == "horario_alcanzado_sin_confirmar"
    assert cal.clasificar(e, despues, celebracion_confirmada=True) == "celebrado_resultado_no_publicado"


def test_resultado_conocido_bloquea_incluso_antes_de_hora_prevista():
    c = cal.calendario_defecto()["BALOTO"]
    antes = instante("2026-10-19T20:00:00+00:00")
    assert not cal.admisible_emitir(c, date(2026, 10, 19), antes, resultado_conocido=True)


def test_estado_consulta_no_confunde_error_con_evento_futuro_o_publicado():
    c = cal.calendario_defecto()["BALOTO"]
    e = cal.evento_en_fecha(c, date(2026, 10, 19))
    antes = e.instante - timedelta(seconds=1)
    assert cal.clasificar(e, antes) == "sorteo_previsto"
    assert cal.clasificar(e, antes, error_consulta=True) == "fallo_consulta"
    assert cal.clasificar(e, e.instante, resultado_validado=True) == "resultado_detectado_validado"
    assert cal.clasificar(e, e.fin_ventana + timedelta(days=2)) == "horario_alcanzado_sin_confirmar"


def test_excepciones_cancelan_y_reprograman_sin_mutar_calendario_original():
    base = cal.calendario_defecto()["BALOTO"]
    cancelar = cal.ExcepcionCalendario(date(2026, 10, 19), motivo="Aplazamiento comunicado",
        fuente_url="https://baloto.com/aviso-controlado", verificada=True)
    mover = cal.ExcepcionCalendario(date(2026, 10, 20), time(21), time(21, 15),
        motivo="Fecha excepcional controlada", fuente_url="https://baloto.com/aviso-controlado", verificada=True)
    ajustado = replace(base, excepciones=(cancelar, mover))
    assert cal.evento_en_fecha(ajustado, cancelar.fecha) is None
    e = cal.evento_en_fecha(ajustado, mover.fecha)
    assert e.excepcional and e.fuente_verificada and e.nota == mover.motivo
    assert e.instante == instante("2026-10-21T02:00:00+00:00")
    assert cal.evento_en_fecha(base, cancelar.fecha) is not None
    assert cal.evento_en_fecha(base, mover.fecha) is None
    assert cal.proximo_evento(ajustado, instante("2026-10-19T10:00:00+00:00")) == e


def test_excepcion_sin_verificar_se_muestra_pero_no_autoriza_emision():
    base = cal.calendario_defecto()["BALOTO"]
    e = cal.ExcepcionCalendario(date(2026, 10, 20), time(21), motivo="Pendiente de contrastar",
        fuente_url="referencia-operador:aviso")
    c = replace(base, excepciones=(e,))
    assert not cal.evento_en_fecha(c, e.fecha).fuente_verificada
    assert not cal.admisible_emitir(c, e.fecha, instante("2026-10-20T20:00:00+00:00"))


def test_cancelacion_no_verificada_no_permite_saltar_al_evento_siguiente():
    base = cal.calendario_defecto()["BALOTO"]
    e = cal.ExcepcionCalendario(date(2026, 10, 19), motivo="Aviso pendiente",
        fuente_url="referencia-operador:cancelacion")
    c = replace(base, excepciones=(e,))
    siguiente = cal.proximo_evento(c, instante("2026-10-19T20:00:00+00:00"))
    assert siguiente.fecha_local == date(2026, 10, 21)
    assert not cal.admisible_emitir(c, siguiente.fecha_local, instante("2026-10-19T20:00:00+00:00"))


def test_colecciones_del_calendario_quedan_congeladas_con_configuracion_externa():
    dias = [0, 2, 5]
    c = replace(cal.calendario_defecto()["BALOTO"], dias_semana=dias)
    dias.clear()
    assert c.dias_semana == (0, 2, 5)


def test_calendario_no_verificado_bloquea_sin_usar_zona_local_del_equipo():
    c = replace(cal.calendario_defecto()["BALOTO"], verificado=False)
    assert not cal.admisible_emitir(c, date(2026, 10, 19), instante("2026-10-19T20:00:00-05:00"))


def test_recuperacion_de_varios_eventos_es_acotada_ordenada_y_no_depende_de_numero():
    c = cal.calendario_defecto()["BALOTO"]
    pasados = cal.eventos(c, date(2026, 10, 12), date(2026, 10, 20))
    assert [e.fecha_local for e in pasados] == [date(2026, 10, d) for d in (12, 14, 17, 19)]
    assert tuple(sorted(e.instante for e in pasados)) == tuple(e.instante for e in pasados)
    # No se inventa una numeración a partir del calendario.
    assert all("numero_sorteo" not in e.como_dict() for e in pasados)
    with pytest.raises(ValueError, match="Rango permitido"):
        cal.eventos(c, date(2024, 1, 1), date(2026, 1, 1))
    with pytest.raises(ValueError, match="Rango permitido"):
        cal.eventos(c, date(2026, 1, 2), date(2026, 1, 1))


@pytest.mark.parametrize("funcion", [
    lambda c, ahora: cal.proximo_evento(c, ahora),
    lambda c, ahora: cal.ultimo_evento(c, ahora),
    lambda c, ahora: cal.admisible_emitir(c, date(2026, 10, 19), ahora),
    lambda c, ahora: cal.clasificar(cal.evento_en_fecha(c, date(2026, 10, 19)), ahora),
])
def test_reloj_sin_zona_se_rechaza(funcion):
    with pytest.raises(ValueError, match="zona explícita"):
        funcion(cal.calendario_defecto()["BALOTO"], datetime(2026, 10, 19, 20))


def test_sin_base_iana_hay_bloqueo_accionable_sin_fallback_silencioso(monkeypatch):
    def falta(nombre):
        raise cal.ZoneInfoNotFoundError(nombre)
    monkeypatch.setattr(cal, "ZoneInfo", falta)
    with pytest.raises(cal.CalendarioNoDisponibleError, match="tzdata"):
        cal.evento_en_fecha(cal.calendario_defecto()["BALOTO"], date(2026, 10, 19))


def test_evento_serializado_conserva_fecha_local_y_fuente_sin_promesa_publicacion():
    e = cal.evento_en_fecha(cal.calendario_defecto()["COLORLOTO"], date(2026, 10, 19))
    d = e.como_dict()
    assert d["fecha_local"] == "2026-10-19" and d["inicio_local"].endswith("-05:00")
    assert d["zona"] == "America/Bogota" and d["fuente_verificada"]
    assert "publicacion" not in d
    with pytest.raises(FrozenInstanceError):
        e.juego = "MILOTO"


@pytest.mark.parametrize("cambio", [
    {"dias_semana": (True, 2)}, {"dias_semana": (0, 0)},
    {"hora_local": time(23, tzinfo=timezone.utc)}, {"hora_fin_local": time(21)},
    {"zona": "UTC"}, {"fuente_url": ""}, {"horarios_por_dia": ((1, time(21), time(21)),)},
    {"verificado": "false"},
])
def test_configuracion_calendario_invalida_se_rechaza(cambio):
    with pytest.raises(ValueError):
        replace(cal.calendario_defecto()["BALOTO"], **cambio)


def test_excepciones_requieren_evidencia_y_no_duplican_fecha():
    with pytest.raises(ValueError, match="motivo y referencia"):
        cal.ExcepcionCalendario(date(2026, 10, 19), time(23))
    e = cal.ExcepcionCalendario(date(2026, 10, 19), time(22), motivo="Caso controlado", fuente_url="fuente:controlada")
    with pytest.raises(ValueError, match="dos excepciones"):
        replace(cal.calendario_defecto()["BALOTO"], excepciones=(e, e))
