"""Orden de decisiones real; puertos de emisión controlados, sin ML/red reales."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
from tests.unit.test_fase6_revisiones import _crear, _revision, _emitir, _evidencia
from tests.unit.test_fase6_integracion import entorno, detalle
from tests.unit.fixtures_tiempo_fase6 import fijar_marca

def _marcar(almacen, decisiones, posiciones):
    for decision, posicion in zip(decisiones, posiciones, strict=True):
        fijar_marca(almacen.directorio / "d" / (decision["clave"] + ".json"), posicion)


def _guardar(almacen, clave, estado, en, nota):
    decision = {"estado": estado, "nota": nota}
    if en is not None:
        decision["en"] = en
    return almacen.guardar_decision_revision(clave, decision)


def test_en_con_zona_ordena_en_utc_aunque_mtime_este_invertido(tmp_path):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    primera = _guardar(almacen, revision["clave"], "rechazada", "2026-10-19T12:00:00+00:00", "Primera")
    ultima = _guardar(almacen, revision["clave"], "observacion", "2026-10-19T07:01:00-05:00", "Posterior")
    _marcar(almacen, [primera, ultima], [2, 1])
    original = _evidencia(almacen)
    assert almacen.decisiones_revision(revision["clave"])[0]["decision"] == ultima["decision"]
    assert almacen.revisiones_pendientes("BALOTO", 1, 101) == [revision]
    assert servicio.panel()["revisiones"] == [revision]
    assert _emitir(servicio)["estado"] == "revision_pendiente"
    assert not puerto.generaciones and _evidencia(almacen) == original


@pytest.mark.parametrize("invertir", [False, True])
def test_en_distinto_resuelve_mtime_empatado_sin_reescribir_historicos(tmp_path, invertir):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    datos = [("observacion", "2026-10-19T12:00:00+00:00", "Anterior"),
             ("rechazada", "2026-10-19T12:01:00+00:00", "Explícita posterior")]
    if invertir:
        datos.reverse()
    decisiones = [_guardar(almacen, revision["clave"], *d) for d in datos]
    _marcar(almacen, decisiones, [0, 0])
    original = _evidencia(almacen)
    reiniciado = AlmacenAutomatizacion(almacen.directorio)
    assert reiniciado.decisiones_revision(revision["clave"], limite=1)[0]["decision"]["estado"] == "rechazada"
    assert not reiniciado.revisiones_pendientes("BALOTO", 1, 101)
    assert servicio.panel()["revisiones"] == []
    assert _emitir(servicio)["estado"] == "correcto"
    assert len(puerto.generaciones) == 1 and _evidencia(almacen) == original


@pytest.mark.parametrize("en", [None, "fecha invalida", "2026-10-19T12:00:00"])
def test_legacy_sin_en_valido_conserva_orden_mtime_verificado_y_bytes(tmp_path, en):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    primera = _guardar(almacen, revision["clave"], "rechazada", "2099-10-19T12:00:00+00:00", "Terminal previa")
    ultima = _guardar(almacen, revision["clave"], "observacion", en, "Posterior sin fecha comparable")
    _marcar(almacen, [primera, ultima], [0, 1])
    original = _evidencia(almacen)
    consulta = AlmacenAutomatizacion(almacen.directorio).decisiones_revision(revision["clave"])
    assert consulta[0]["decision"] == ultima["decision"]
    assert not consulta[0].get("orden_ambiguo")
    assert servicio.panel()["revisiones"] == [revision]
    assert _emitir(servicio)["estado"] == "revision_pendiente"
    assert not puerto.generaciones and _evidencia(almacen) == original


@pytest.mark.parametrize("en", [None, "fecha invalida", "2026-10-19T12:00:00"])
@pytest.mark.parametrize("ultimo_estado", ["observacion", "aceptada"])
def test_empate_legacy_no_autoriza_por_hash_y_se_calcula_antes_del_limite(tmp_path, en, ultimo_estado):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    primera = _guardar(almacen, revision["clave"], "rechazada", None, "Terminal previa")
    otra = _guardar(almacen, revision["clave"], ultimo_estado, en, "Contenido distinto")
    _marcar(almacen, [primera, otra], [0, 0])
    original = _evidencia(almacen)
    consulta = almacen.decisiones_revision(revision["clave"])
    assert len(consulta) == 2 and all(d.get("orden_ambiguo") for d in consulta)
    assert almacen.decisiones_revision(revision["clave"], limite=1) == consulta[:1]
    assert almacen.revisiones_pendientes("BALOTO", 1, 101) == [revision]
    assert servicio.panel()["revisiones"] == [revision]
    assert _emitir(servicio)["estado"] == "revision_pendiente"
    assert not puerto.generaciones and _evidencia(almacen) == original


@pytest.mark.parametrize("estado", ["observacion", "aceptada", "rechazada"])
def test_en_empatado_es_ambiguo_aunque_mtime_separe_las_publicaciones(tmp_path, estado):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    primera = _guardar(almacen, revision["clave"], "rechazada", "2026-10-19T12:00:00+00:00", "A")
    otra = _guardar(almacen, revision["clave"], estado, "2026-10-19T07:00:00-05:00", "B")
    _marcar(almacen, [primera, otra], [0, 1])
    original = _evidencia(almacen)
    assert all(d.get("orden_ambiguo") for d in almacen.decisiones_revision(revision["clave"]))
    assert servicio.panel()["revisiones"] == [revision]
    assert _emitir(servicio)["estado"] == "revision_pendiente"
    assert not puerto.generaciones and _evidencia(almacen) == original


def test_decision_posterior_no_ambigua_resuelve_y_repeticion_es_inmutable(tmp_path):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    en = "2026-10-19T12:00:00+00:00"
    primeras = [_guardar(almacen, revision["clave"], estado, en, estado)
                for estado in ("aceptada", "rechazada")]
    _marcar(almacen, primeras, [0, 0])
    assert _emitir(servicio)["estado"] == "revision_pendiente"
    anteriores = _evidencia(almacen)
    ultima = _guardar(almacen, revision["clave"], "rechazada", "2026-10-19T12:01:00+00:00", "Resolución explícita")
    _marcar(almacen, [ultima], [0])
    assert not almacen.decisiones_revision(revision["clave"], limite=1)[0].get("orden_ambiguo")
    assert _emitir(servicio)["estado"] == "correcto" and len(puerto.generaciones) == 1
    assert all(_evidencia(almacen)[p] == b for p, b in anteriores.items())
    evidencia = _evidencia(almacen)
    assert almacen.guardar_decision_revision(revision["clave"], ultima["decision"]) == ultima
    assert _evidencia(almacen) == evidencia


def test_adaptador_no_da_por_rechazada_una_discrepancia_ambigua(tmp_path):
    t = entorno(tmp_path, registrar=False)
    ultimo = t.e.historicos["BALOTO"][-1]
    t.conector.detalles = {str(ultimo.numero_sorteo): detalle("BALOTO", replace(ultimo, superbalota=(ultimo.superbalota % 16) + 1))}
    with t.adaptador.por_juego("BALOTO") as dep:
        clave, = dep.sincronizar()["pendientes_revision"]
        en = "2026-10-20T12:00:00+00:00"
        rechazo = _guardar(t.registro, clave, "rechazada", en, "Rechazo")
        observacion = _guardar(t.registro, clave, "observacion", en, "Revisar")
        _marcar(t.registro, [rechazo, observacion], [1, 0])
        evidencia = _evidencia(t.registro)
        resultado = dep.sincronizar()
        assert resultado["pendientes_revision"] == [clave]
        assert resultado["revisiones_rechazadas"] == []
        assert _evidencia(t.registro) == evidencia


def test_aceptar_repite_solo_la_decision_vigente_no_una_aceptacion_obsoleta(tmp_path):
    t = entorno(tmp_path, registrar=False)
    ultimo = t.e.historicos["BALOTO"][-1]
    t.conector.detalles = {str(ultimo.numero_sorteo): detalle("BALOTO", replace(ultimo, superbalota=(ultimo.superbalota % 16) + 1))}
    with t.adaptador.por_juego("BALOTO") as dep:
        clave, = dep.sincronizar()["pendientes_revision"]
        propuesta = t.registro.revision(clave)
        dep.aplicar_revision(propuesta, "Fuente cotejada")
        t.reloj.instante += timedelta(minutes=1)
        _guardar(t.registro, clave, "observacion", t.reloj().isoformat(), "Revisión posterior")
        anteriores = _evidencia(t.registro)
        t.reloj.instante += timedelta(minutes=1)
        salida = dep.aplicar_revision(propuesta, "Fuente cotejada")
        assert not salida.get("reutilizada", False)
        assert len(t.registro.decisiones_revision(clave)) == 3
        assert all(_evidencia(t.registro)[p] == b for p, b in anteriores.items())
        assert not t.registro.revisiones_pendientes("BALOTO", 1, ultimo.numero_sorteo)
        evidencia = _evidencia(t.registro)
        assert dep.aplicar_revision(propuesta, "Fuente cotejada")["reutilizada"]
        assert _evidencia(t.registro) == evidencia
