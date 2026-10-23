"""Revisiones persistidas: núcleo/almacén/cerrojos reales, puertos controlados.

No consulta proveedor o BD ni ejecuta inferencia ML. La publicación simulada
permite observar la admisión de un histórico sin cambiar modelos históricos.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os

import pytest

from tests.unit.fixtures_tiempo_fase6 import fijar_marca

from app.application.use_cases.operacion_automatica import OperacionAutomatica
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion

AHORA = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def _huella(valor):
    return hashlib.sha256(json.dumps(valor, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _revision(almacen, numero=80, juego="BALOTO"):
    antes = {"numero_sorteo": numero, "fecha": "2026-08-31", "numeros": [1, 2, 3, 4, 5],
             "superbalota": 1, "pares": []}
    propuesta = {**antes, "numeros": [1, 2, 3, 4, 6]}
    identidad = {"juego": juego, "numero_sorteo": numero, "antes": antes, "propuesta": propuesta}
    revision = {"clave": _huella(identidad), **identidad, "estado": "pendiente",
                "huellas": {"antes": _huella(antes), "propuesta": _huella(propuesta),
                            "html": hashlib.sha256(b"fixture fuente controlada").hexdigest()},
                "fuente_url": "https://baloto.com/", "detectada_en": AHORA.isoformat()}
    return almacen.guardar_revision(revision)


class PuertoControlado:
    def __init__(self, primero=1):
        self.primero = primero
        self.importados = self.reconciliaciones = 0
        self.generaciones = []
        self.recientes = []

    @contextmanager
    def por_juego(self, codigo):
        assert codigo == "BALOTO"
        yield self

    def instantanea(self):
        ultimo = 101 if self.importados else 100
        return {"primer_sorteo": self.primero, "ultimo_sorteo": ultimo,
                "fecha": "2026-10-17", "sorteos": ultimo - self.primero + 1, "huecos": 0}

    def configuracion(self):
        return {"juego": "BALOTO", "version": 1,
                "modelo": {"registrado": {"clave": "a" * 64}}}

    def sincronizar(self, **parametros):
        assert parametros["reconciliar_ultimos"] <= 100
        self.importados = 1
        return {"estado": "completado", "nuevos": 1, "pendientes_revision": self.recientes}

    def reconciliar(self):
        self.reconciliaciones += 1
        return {"estado": "completado"}

    def generar(self, **parametros):
        self.generaciones.append(deepcopy(parametros))
        return {"estado": "exito", "cartera": "b" * 64}


def _crear(tmp_path, primero=1):
    almacen = AlmacenAutomatizacion(tmp_path / "operacion")
    almacen.guardar_configuracion({"activada": True, "pausada": False})
    puerto = PuertoControlado(primero)
    servicio = OperacionAutomatica(almacen, puerto, reloj=lambda: AHORA)
    return servicio, almacen, puerto


def _emitir(servicio):
    return servicio.ciclo(["BALOTO"], forzar=True)["juegos"]["BALOTO"]


def _evidencia(almacen):
    return {p.relative_to(almacen.directorio).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for carpeta in ("r", "d") for p in (almacen.directorio / carpeta).glob("*.json")}


def test_revision_antigua_fuera_de_ventana_impide_emitir_pero_importa_y_reconcilia(tmp_path):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    original = _evidencia(almacen)
    salida = _emitir(servicio)
    assert salida["estado"] == "revision_pendiente"
    assert salida["revisiones_pendientes"] == [revision["clave"]]
    assert puerto.importados == puerto.reconciliaciones == 1
    assert puerto.generaciones == []
    assert servicio.panel()["revisiones"] == [revision]
    assert _evidencia(almacen) == original


def test_revision_fuera_de_100_del_panel_y_de_1000_no_se_olvida(tmp_path):
    servicio, almacen, puerto = _crear(tmp_path)
    pendiente = _revision(almacen)
    fijar_marca(almacen.directorio / "r" / (pendiente["clave"] + ".json"), 1)
    # Más que ambos límites de presentación del almacén. Son propuestas
    # de otro corte; solo la antigua dentro de este histórico debe bloquear.
    for i in range(1001):
        otra = _revision(almacen, numero=1000 + i)
        fijar_marca(almacen.directorio / "r" / (otra["clave"] + ".json"), i + 2)
    assert pendiente not in servicio.panel()["revisiones"]
    assert len(servicio.panel()["revisiones"]) == 100
    original = _evidencia(almacen)
    salida = _emitir(servicio)
    assert salida["estado"] == "revision_pendiente"
    assert salida["revisiones_pendientes"] == [pendiente["clave"]]
    assert puerto.generaciones == [] and _evidencia(almacen) == original


@pytest.mark.parametrize("estado", ["aceptada", "rechazada"])
def test_decision_explicita_resuelve_bloqueo_sin_reescribir_propuesta(tmp_path, estado):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    assert _emitir(servicio)["estado"] == "revision_pendiente"
    decision = {"estado": estado, "nota": "Fuente revisada explícitamente en fixture",
                "en": AHORA.isoformat()}
    if estado == "aceptada":
        decision["propuesta_sha256"] = _huella(revision["propuesta"])
    almacen.guardar_decision_revision(revision["clave"], decision)
    evidencia = _evidencia(almacen)
    assert _emitir(servicio)["estado"] == "correcto"
    assert len(puerto.generaciones) == 1
    assert almacen.revision(revision["clave"]) == revision
    assert almacen.revisiones_pendientes("BALOTO", 1, 101) == []
    assert servicio.panel()["revisiones"] == []
    assert _evidencia(almacen) == evidencia


@pytest.mark.parametrize("juego,numero", [("COLORLOTO", 80), ("BALOTO", 39), ("BALOTO", 102)])
def test_revision_ajena_a_juego_o_corte_no_bloquea(tmp_path, juego, numero):
    servicio, almacen, puerto = _crear(tmp_path, primero=40)
    revision = _revision(almacen, numero, juego)
    assert _emitir(servicio)["estado"] == "correcto"
    assert len(puerto.generaciones) == 1
    assert almacen.revision(revision["clave"]) == revision
    # Continúa pendiente en su propio ámbito, sin contaminar este corte.
    assert revision in servicio.panel()["revisiones"]


@pytest.mark.parametrize("numero", [40, 101])
def test_ambos_extremos_del_historico_estan_incluidos(tmp_path, numero):
    servicio, almacen, puerto = _crear(tmp_path, primero=40)
    revision = _revision(almacen, numero)
    salida = _emitir(servicio)
    assert salida["estado"] == "revision_pendiente"
    assert salida["revisiones_pendientes"] == [revision["clave"]]
    assert puerto.generaciones == []


def test_decision_desconocida_no_resuelve_y_se_conservan_ambas(tmp_path):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    anterior = almacen.guardar_decision_revision(revision["clave"], {"estado": "rechazada", "nota": "Decisión previa"})
    previa = almacen.decisiones_revision(revision["clave"])[0]
    fijar_marca(almacen.directorio / "d" / (anterior["clave"] + ".json"), 1)
    posterior = almacen.guardar_decision_revision(revision["clave"], {"estado": "observacion", "nota": "No es decisión terminal"})
    fijar_marca(almacen.directorio / "d" / (posterior["clave"] + ".json"), 2)
    original = _evidencia(almacen)
    assert _emitir(servicio)["estado"] == "revision_pendiente"
    assert previa in almacen.decisiones_revision(revision["clave"])
    assert servicio.panel()["revisiones"] == [revision]
    assert puerto.generaciones == [] and _evidencia(almacen) == original


@pytest.mark.parametrize("estado", ["aceptada", "rechazada"])
def test_decision_persistida_prevalece_sobre_lista_reciente_desfasada(tmp_path, estado):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    almacen.guardar_decision_revision(revision["clave"], {"estado": estado, "nota": "Decisión explícita fixture"})
    puerto.recientes = [revision["clave"]]
    assert _emitir(servicio)["estado"] == "correcto"
    assert len(puerto.generaciones) == 1


def test_discrepancia_reciente_no_persistida_sigue_bloqueando(tmp_path):
    servicio, _, puerto = _crear(tmp_path)
    puerto.recientes = ["f" * 64]
    assert _emitir(servicio)["estado"] == "revision_pendiente"
    assert puerto.generaciones == []


def test_contenido_revision_alterado_falla_cerrado(tmp_path):
    servicio, almacen, puerto = _crear(tmp_path)
    revision = _revision(almacen)
    ruta = almacen.directorio / "r" / (revision["clave"] + ".json")
    ruta.write_text(json.dumps({**revision, "clave": "f" * 64}), encoding="utf-8")
    salida = _emitir(servicio)
    assert salida["estado"] == "fallo" and salida["error"]["tipo"] == "ValueError"
    assert puerto.generaciones == []


def test_consulta_vacia_es_solo_lectura_y_valida_intervalo(tmp_path):
    almacen = AlmacenAutomatizacion(tmp_path / "no existe")
    assert almacen.revisiones_pendientes("BALOTO", 1, None) == []
    assert almacen.revisiones_pendientes("BALOTO", None, 100) == []
    assert not almacen.directorio.exists()
    with pytest.raises(ValueError):
        almacen.revisiones_pendientes("BALOTO", 101, 100)
