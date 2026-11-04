"""Evidencia VIVA de escritores durante la captura (E10.4). Solo observa: no toma, prueba ni libera ningun
cerrojo, advisory ni archivo de Fase 6 ni de los trabajadores.

Archivos (en todas las raices observadas, publicables y operativas):
- `cerrojos/<JUEGO>.activo`: lo escribe `CerrojoPorJuego.adquirir` al tomar el cerrojo de un juego y lo
  borra al liberarlo (Productos 3-5, Fase 4, Fase 6 `ciclos/` y Fase 7);
- `cerrojos/ejecuciones/<id>.lock`: lo mantiene cada ejecucion hasta que su trabajador termina;
- `ejecuciones/<id>.json` con `estado = en_curso` (registro de ejecuciones). Una ejecucion interrumpida
  sigue `en_curso` hasta que alguien la cierra: la captura la trata igual (no puede distinguirla sin probar el
  cerrojo, cosa que no hace) y lo declara.

PostgreSQL (vistas vivas, no la instantanea):
- `pg_locks` con `locktype = advisory` en la base: el ciclo de Fase 6 (advisory de SESION por juego) y las
  escrituras CRUD (advisory de TRANSACCION por juego) de `operacion_advisory`;
- `pg_stat_activity` con `backend_xid` asignado (otra transaccion que YA escribio y no ha terminado). Para ver
  las sesiones de otros roles el rol de captura necesita `pg_read_all_stats`; sin el, la captura se rechaza.
"""
from __future__ import annotations

import json
from pathlib import Path

LIMITE = 50


def en_archivos(raices: dict[str, Path]) -> list[str]:
    evidencia = []
    for nombre, raiz in sorted(raices.items()):
        if not raiz.is_dir():
            continue
        for ruta in sorted(raiz.rglob("*")):
            partes = ruta.relative_to(raiz).parts
            if "cerrojos" in partes:
                if ruta.suffix == ".activo" and ruta.is_file():
                    evidencia.append(f"{nombre}/{ruta.relative_to(raiz).as_posix()}: cerrojo de juego tomado")
                elif ruta.suffix == ".lock" and ruta.parent.name == "ejecuciones" and ruta.is_file():
                    evidencia.append(f"{nombre}/{ruta.relative_to(raiz).as_posix()}: ejecucion con trabajador")
            elif ruta.parent.name == "ejecuciones" and ruta.suffix == ".json" and ruta.is_file():
                try:
                    estado = json.loads(ruta.read_text(encoding="utf-8")).get("estado")
                except (OSError, ValueError, AttributeError):
                    estado = "ilegible"
                if estado in ("en_curso", "ilegible"):
                    evidencia.append(f"{nombre}/{ruta.relative_to(raiz).as_posix()}: ejecucion {estado}")
            if len(evidencia) >= LIMITE:
                return evidencia
    return evidencia


def visibilidad_suficiente(conexion) -> bool:
    return bool(conexion.execute(
        "SELECT rolsuper OR pg_has_role(current_user, 'pg_read_all_stats', 'USAGE') FROM pg_roles "
        "WHERE rolname = current_user").fetchone()[0])


def en_base(conexion) -> list[str]:
    evidencia = []
    for classid, objid, pid, modo, concedido in conexion.execute(
            "SELECT classid, objid, pid, mode, granted FROM pg_locks WHERE locktype = 'advisory' AND "
            "database = (SELECT oid FROM pg_database WHERE datname = current_database()) "
            "AND pid IS DISTINCT FROM pg_backend_pid() ORDER BY pid").fetchall():
        clave = (int(classid) << 32) | int(objid)
        if clave >= 1 << 63:
            clave -= 1 << 64
        evidencia.append(f"advisory {clave} ({modo}, {'tomado' if concedido else 'en espera'}) pid {pid}")
    for pid, estado, xid in conexion.execute(
            "SELECT pid, state, backend_xid::text FROM pg_stat_activity WHERE datname = current_database() "
            "AND pid <> pg_backend_pid() AND backend_xid IS NOT NULL ORDER BY pid").fetchall():
        evidencia.append(f"transaccion con escritura sin terminar pid {pid} ({estado}, xid {xid})")
    return evidencia[:LIMITE]
