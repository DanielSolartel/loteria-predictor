"""Fase 7: identidad, integridad y repositorio de la tabla `simulaciones`
(SQLite aislado; el advisory de PostgreSQL se comprueba aparte con
`tests/postgres_fase7.py`). Exportaciones derivadas de la fila."""
from __future__ import annotations

import copy
import csv
import io
import json
import uuid

import pytest

from app.application.fase7 import artefacto as fa
from app.application.fase7 import motor as fm
from app.domain.entities.analitica import Simulacion
from app.infrastructure.db.models import SimulacionORM
from app.infrastructure.operacion_advisory import clave_de_juego
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.simulaciones_repository_sqlalchemy import (
    SimulacionesRepositorySQLAlchemy,
    recurso_de_clave,
)
from tests.unit.simulaciones import fixtures_fase7 as f7


def _fila(e, juego="MILOTO", iteraciones=100, semilla=1):
    h = fm.preparar(juego, e.historicos[juego])
    p = fa.parametros(fa.identidad(h, iteraciones, semilla))
    calculado = fm.calcular(juego, [[r.numero_sorteo, r.fecha.isoformat(), list(r.numeros), r.superbalota]
                                    for r in h.instantanea.sorteos] if juego != "COLORLOTO" else
                            [[r.numero_sorteo, r.fecha.isoformat(), sorted([n, c] for n, c in r.pares)]
                             for r in h.instantanea.sorteos], iteraciones, semilla)
    resumen = fa.resultado(p, calculado["contenido"], {**calculado["procesamiento"], "duracion_ms": 5})
    with e.sesiones() as s:
        juego_id = JuegoRepositorySQLAlchemy(s).obtener_por_codigo(juego).id
    return Simulacion(None, juego_id, iteraciones, p, resumen, duracion_ms=5), p["clave"]


def test_identidad_cubre_lo_que_determina_el_resultado(tmp_path):
    e = f7.entorno(tmp_path)
    h = fm.preparar("BALOTO", e.historicos["BALOTO"])
    base = fa.parametros(fa.identidad(h, 1_000, 7))
    assert set(base) >= {"esquema", "version_motor", "juego", "corte", "historico", "reglas", "algoritmo",
                         "iteraciones", "semilla", "estadisticas", "familia", "estado_de_uso", "clave"}
    assert base["historico"]["sha256"] == h.instantanea.huella() and base["algoritmo"]["numpy"]
    assert base["estado_de_uso"] == "experimental_no_acreditado"
    claves = {base["clave"], fa.parametros(fa.identidad(h, 10_000, 7))["clave"],
              fa.parametros(fa.identidad(h, 1_000, 8))["clave"],
              fa.parametros(fa.identidad(fm.preparar("BALOTO", e.historicos["BALOTO"][:-1]), 1_000, 7))["clave"],
              fa.parametros(fa.identidad(fm.preparar("BALOTO_REVANCHA", e.historicos["BALOTO_REVANCHA"]), 1_000, 7))[
                  "clave"]}
    assert len(claves) == 5
    assert fa.parametros(fa.identidad(h, 1_000, 7)) == base  # determinista
    assert "lote" not in json.dumps(base)  # el lote no forma parte de la identidad


def test_verificacion_detecta_cada_alteracion(tmp_path):
    e = f7.entorno(tmp_path)
    fila, _ = _fila(e)
    fa.verificar(fila.parametros, fila.resultado_resumen, fila.num_iteraciones)
    casos = []
    p = copy.deepcopy(fila.parametros); p["semilla"] = 2; casos.append((p, fila.resultado_resumen, 100, "clave"))
    r = copy.deepcopy(fila.resultado_resumen); r["contenido"]["estadisticas"][0]["observado"]["valor"] += 1
    casos.append((fila.parametros, r, 100, "contenido"))
    r = copy.deepcopy(fila.resultado_resumen); r["ejecucion"]["lote"] = 1
    casos.append((fila.parametros, r, 100, "integridad"))
    r = copy.deepcopy(fila.resultado_resumen); r["clave"] = "0" * 64
    casos.append((fila.parametros, r, 100, "otra identidad"))
    casos.append((fila.parametros, fila.resultado_resumen, 1000, "num_iteraciones"))
    p = copy.deepcopy(fila.parametros); p["esquema"] = "otro"; casos.append((p, fila.resultado_resumen, 100, "esquema"))
    for parametros, resultado, iteraciones, motivo in casos:
        with pytest.raises(fa.ArtefactoSimulacionError, match=motivo):
            fa.verificar(parametros, resultado, iteraciones)


def test_publicar_inserta_una_fila_completa_y_es_idempotente(tmp_path):
    e = f7.entorno(tmp_path)
    fila, clave = _fila(e)
    with e.sesiones() as s:
        publicada, creada = SimulacionesRepositorySQLAlchemy(s).publicar(fila, clave)
        s.commit()
    assert creada and publicada.id is not None and publicada.ejecutado_en is not None
    with e.sesiones() as s:
        otra, creada2 = SimulacionesRepositorySQLAlchemy(s).publicar(fila, clave)
        s.commit()
    assert not creada2 and otra.id == publicada.id
    filas = e.filas()
    assert len(filas) == 1 and filas[0]["num_iteraciones"] == 100 and filas[0]["parametros"]["clave"] == clave
    fa.verificar(filas[0]["parametros"], filas[0]["resultado_resumen"], filas[0]["num_iteraciones"])
    with e.sesiones() as s:
        repo = SimulacionesRepositorySQLAlchemy(s)
        assert [f.id for f in repo.por_clave(fila.juego_id, clave)] == [publicada.id]
        assert repo.por_clave(uuid.uuid4(), clave) == [] and repo.por_clave(fila.juego_id, "f" * 64) == []
        assert repo.obtener(publicada.id).parametros == fila.parametros
        with pytest.raises(ValueError):
            repo.publicar(fila, "0" * 64)


def test_listar_solo_filas_de_la_fase7_y_un_rollback_no_publica(tmp_path):
    e = f7.entorno(tmp_path)
    fila, clave = _fila(e)
    with e.sesiones() as s:
        s.add(SimulacionORM(juego_id=fila.juego_id, num_iteraciones=5, parametros={"otro": 1}, resultado_resumen={}))
        s.commit()
    with e.sesiones() as s:
        SimulacionesRepositorySQLAlchemy(s).publicar(fila, clave)
        s.rollback()  # una publicacion deshecha no deja nada
    with e.sesiones() as s:
        assert SimulacionesRepositorySQLAlchemy(s).listar() == []
        SimulacionesRepositorySQLAlchemy(s).publicar(fila, clave)
        s.commit()
    with e.sesiones() as s:
        repo = SimulacionesRepositorySQLAlchemy(s)
        assert [f.parametros["clave"] for f in repo.listar()] == [clave]
        assert repo.listar(uuid.uuid4()) == [] and len(repo.listar(fila.juego_id, 1)) == 1
    assert len(e.filas()) == 2  # la fila ajena se conserva intacta


def test_recurso_advisory_propio_y_distinto_del_de_datos():
    clave = "a" * 64
    assert recurso_de_clave(clave) == recurso_de_clave(clave)
    assert -(2**63) <= recurso_de_clave(clave) < 2**63
    assert recurso_de_clave(clave) != recurso_de_clave("b" * 64)
    assert recurso_de_clave(clave) != clave_de_juego(clave)


def test_exportaciones_derivadas_de_la_fila(tmp_path):
    e = f7.entorno(tmp_path)
    fila, clave = _fila(e, "BALOTO")
    d = {"id": "x", "juego": "BALOTO", "num_iteraciones": 100, "ejecutado_en": "2026-10-23T12:00:00",
         "duracion_ms": 5, "parametros": fila.parametros, "resultado_resumen": fila.resultado_resumen}
    exportada = json.loads(fa.json_de_exportacion(d))
    assert exportada["derivado_de"] == "tabla simulaciones"
    assert exportada["parametros"] == fila.parametros and exportada["resultado_resumen"] == fila.resultado_resumen
    filas = list(csv.reader(io.StringIO(fa.csv_de_exportacion(d))))
    assert filas[0][:7] == ["id", "clave", "juego", "corte", "iteraciones", "semilla", "estadistica"]
    assert [f[6] for f in filas[1:]] == [x.nombre for x in fm.familia("BALOTO")]
    assert all(f[1] == clave for f in filas[1:])
    assert fa._celda("=1+1") == "'=1+1" and fa._celda("@x") == "'@x" and fa._celda(3.5) == "3.5"
