"""Volcado LOGICO de PostgreSQL para las generaciones (E10.4), sin `pg_dump` ni dependencias nuevas.

Garantias en las que se apoya (documentacion de PostgreSQL 16):
- una transaccion `REPEATABLE READ` ve una instantanea fija de todos los datos confirmados al empezar
  ("Transaction Isolation"); `pg_export_snapshot()` permite que OTRA conexion importe exactamente esa
  instantanea con `SET TRANSACTION SNAPSHOT` ("Snapshot Synchronization Functions");
- cada version de fila lleva en la columna de sistema `xmin` el identificador de la transaccion que la creo
  ("System Columns"); toda insercion o actualizacion confirmada crea una version nueva (MVCC), y un borrado
  retira una version visible. Por eso dos lecturas de una tabla con el MISMO conjunto de (`xmin`, contenido)
  ven las mismas versiones de fila: ningun escritor confirmo cambios en ella entre ambas, aunque los recuentos,
  los maximos de `id` o el contenido final coincidan (C1, C2).

`row_to_json` da la representacion de texto de PostgreSQL de cada valor (fechas ISO con zona UTC fijada,
numericos exactos, flotantes de ida y vuelta exacta, JSONB, UUID); `json_populate_recordset` la convierte de
vuelta al tipo de la columna. La restauracion se comprueba recalculando la huella de contenido en el destino.

No se usa `pg_snapshot_xmax`, recuentos ni maximos de `id` como garantia (F10-CAP-01).
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.infrastructure.generaciones.formato import GeneracionNoValida, canonico, sha256_bytes

TABLA_ALEMBIC = "alembic_version"
LOTE = 500


def url_psycopg(url: str) -> str:
    """`postgresql+psycopg://` (SQLAlchemy) -> `postgresql://` (psycopg)."""
    for prefijo in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if url.startswith(prefijo):
            return "postgresql://" + url[len(prefijo):]
    return url


def conectar(url: str, *, limite: float | None = None, **opciones):
    """Conexion psycopg con zona UTC. Con `limite` (segundos restantes del plazo de la captura, E104-PLA-04): la
    conexion se abandona tras `connect_timeout` y cada sentencia o espera de cerrojo se cancela al vencer
    (`statement_timeout`, `lock_timeout`)."""
    import psycopg

    if limite is not None:
        if limite <= 0:
            raise TimeoutError("plazo agotado antes de conectar")
        opciones.setdefault("connect_timeout", max(1, int(limite)))
    conexion = psycopg.connect(url_psycopg(url), **opciones)
    if limite is not None:
        ms = max(1, int(limite * 1000))
        conexion.execute(f"SET statement_timeout = {ms}")
        conexion.execute(f"SET lock_timeout = {ms}")
    conexion.execute("SET TIME ZONE 'UTC'")
    conexion.execute("SET extra_float_digits = 1")
    if not opciones.get("autocommit"):
        conexion.commit()
    return conexion


@dataclass
class Tabla:
    nombre: str
    clave: list[str]
    columnas: list[str]
    depende_de: set[str] = field(default_factory=set)
    secuencias: dict[str, str] = field(default_factory=dict)  # columna -> secuencia


def _ident(nombre: str) -> str:
    return '"' + nombre.replace('"', '""') + '"'


def tablas(conexion) -> dict[str, Tabla]:
    """Tablas ordinarias del esquema `public` con su clave primaria, columnas, dependencias y secuencias."""
    filas = conexion.execute(
        "SELECT c.relname, c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY c.relname").fetchall()
    salida = {}
    for nombre, oid in filas:
        columnas = [r[0] for r in conexion.execute(
            "SELECT attname FROM pg_attribute WHERE attrelid = %s AND attnum > 0 AND NOT attisdropped "
            "ORDER BY attnum", (oid,)).fetchall()]
        clave = [r[0] for r in conexion.execute(
            "SELECT a.attname FROM pg_index i JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, orden) "
            "ON true JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum "
            "WHERE i.indrelid = %s AND i.indisprimary ORDER BY k.orden", (oid,)).fetchall()]
        depende = {r[0] for r in conexion.execute(
            "SELECT DISTINCT cf.relname FROM pg_constraint co JOIN pg_class cf ON cf.oid = co.confrelid "
            "WHERE co.conrelid = %s AND co.contype = 'f' AND co.confrelid <> co.conrelid", (oid,)).fetchall()}
        secuencias = {}
        for columna in columnas:
            secuencia = conexion.execute("SELECT pg_get_serial_sequence(%s, %s)",
                                         (f"public.{_ident(nombre)}", columna)).fetchone()[0]
            if secuencia:
                secuencias[columna] = secuencia
        salida[nombre] = Tabla(nombre, clave, columnas, depende, secuencias)
    return salida


def orden_de_carga(catalogo: dict[str, Tabla]) -> list[str]:
    """Orden topologico por claves foraneas (las referenciadas primero); falla ante un ciclo."""
    pendientes = {n: set(t.depende_de) & set(catalogo) for n, t in catalogo.items()}
    orden = []
    while pendientes:
        listas = sorted(n for n, d in pendientes.items() if not d)
        if not listas:
            raise GeneracionNoValida(f"dependencias circulares entre tablas: {sorted(pendientes)}")
        for n in listas:
            orden.append(n)
            del pendientes[n]
        for d in pendientes.values():
            d.difference_update(listas)
    return orden


def huella_esquema(conexion) -> str:
    """Columnas (tipo, nulabilidad, valor por defecto), restricciones e indices del esquema `public`."""
    columnas = conexion.execute(
        "SELECT table_name, column_name, ordinal_position, data_type, udt_name, is_nullable, column_default, "
        "character_maximum_length, numeric_precision, numeric_scale FROM information_schema.columns "
        "WHERE table_schema = 'public' ORDER BY table_name, ordinal_position").fetchall()
    restricciones = conexion.execute(
        "SELECT c.relname, co.conname, pg_get_constraintdef(co.oid) FROM pg_constraint co "
        "JOIN pg_class c ON c.oid = co.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' ORDER BY 1, 2").fetchall()
    indices = conexion.execute(
        "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2").fetchall()
    return sha256_bytes(canonico({"columnas": [list(map(_texto, f)) for f in columnas],
                                  "restricciones": [list(f) for f in restricciones],
                                  "indices": [list(f) for f in indices]}))


def _texto(valor):
    return None if valor is None else str(valor)


def _consulta_filas(tabla: Tabla, con_xmin: bool) -> str:
    orden = ", ".join(_ident(c) for c in tabla.clave) if tabla.clave else "row_to_json(t)::text"
    xmin = "t.xmin::text, " if con_xmin else ""
    return f"SELECT {xmin}row_to_json(t)::text FROM public.{_ident(tabla.nombre)} t ORDER BY {orden}"


@dataclass
class HuellaTabla:
    filas: int
    contenido: str      # SHA-256 de las lineas JSON (reproducible en el destino)
    versiones: str      # SHA-256 de (xmin, linea): identidad de las versiones de fila de ESTA base

    def como_dict(self) -> dict:
        return {"filas": self.filas, "sha256_contenido": self.contenido}


def recorrer_tabla(conexion, tabla: Tabla, *, con_xmin: bool = True, linea: Callable[[bytes], None] | None = None
                   ) -> HuellaTabla:
    contenido, versiones, n = hashlib.sha256(), hashlib.sha256(), 0
    with conexion.cursor(name=f"volcado_{tabla.nombre}") as cursor:
        cursor.itersize = 2000
        cursor.execute(_consulta_filas(tabla, con_xmin))
        for fila in cursor:
            texto = (fila[1] if con_xmin else fila[0]).encode("utf-8") + b"\n"
            contenido.update(texto)
            if con_xmin:
                versiones.update(fila[0].encode("ascii") + b"\t" + texto)
            if linea is not None:
                linea(texto)
            n += 1
    return HuellaTabla(n, contenido.hexdigest(), versiones.hexdigest() if con_xmin else "")


def huellas(conexion, catalogo: dict[str, Tabla] | None = None) -> dict[str, HuellaTabla]:
    """Huella de contenido y de versiones de TODAS las tablas en la transaccion actual de `conexion`."""
    catalogo = catalogo or tablas(conexion)
    return {n: recorrer_tabla(conexion, t) for n, t in sorted(catalogo.items())}


def volcar(conexion, destino: Path, catalogo: dict[str, Tabla]) -> dict[str, HuellaTabla]:
    """Escribe `<destino>/<tabla>.jsonl` desde la transaccion (instantanea) actual y devuelve las huellas."""
    destino.mkdir(parents=True, exist_ok=False)
    salida = {}
    for nombre, tabla in sorted(catalogo.items()):
        ruta = destino / f"{nombre}.jsonl"
        with open(ruta, "xb") as f:
            salida[nombre] = recorrer_tabla(conexion, tabla, linea=f.write)
            f.flush()
            os.fsync(f.fileno())
    return salida


def revision_alembic(conexion) -> str | None:
    existe = conexion.execute("SELECT to_regclass('public.alembic_version')").fetchone()[0]
    if existe is None:
        return None
    filas = conexion.execute("SELECT version_num FROM alembic_version").fetchall()
    return filas[0][0] if len(filas) == 1 else None


def ultimos_sorteos(conexion) -> dict[str, dict]:
    filas = conexion.execute(
        "SELECT j.codigo, count(s.id), max(s.numero_sorteo), max(s.fecha) FROM juegos j "
        "LEFT JOIN sorteos s ON s.juego_id = j.id GROUP BY j.codigo ORDER BY j.codigo").fetchall()
    return {c: {"sorteos": n, "ultimo_sorteo": u, "ultima_fecha": f.isoformat() if f else None} for c, n, u, f in filas}


def restaurar(conexion, origen: Path, manifiesto_base: dict, catalogo: dict[str, Tabla]) -> dict[str, HuellaTabla]:
    """Carga las filas de `origen/<tabla>.jsonl` en el destino YA migrado (misma huella de esquema), en orden
    de claves foraneas y en UNA transaccion; ajusta las secuencias al maximo cargado y comprueba que la huella
    de contenido recalculada en el destino es la del manifiesto. Cualquier diferencia: excepcion (sin confirmar)."""
    esperadas = manifiesto_base["tablas"]
    if set(esperadas) != set(catalogo):
        raise GeneracionNoValida("las tablas del paquete no coinciden con el esquema migrado")
    # Las migraciones siembran filas (juegos, paletas): el contenido autoritativo es el del paquete.
    sembradas = [n for n in sorted(catalogo) if n != TABLA_ALEMBIC]
    if sembradas:
        conexion.execute("TRUNCATE TABLE " + ", ".join(f"public.{_ident(n)}" for n in sembradas) + " RESTART IDENTITY")
    for nombre in orden_de_carga(catalogo):
        if nombre == TABLA_ALEMBIC:
            continue  # la crea y la rellena la migracion; se compara su contenido abajo
        tabla, lote = catalogo[nombre], []

        def vaciar():
            if lote:
                conexion.execute(f"INSERT INTO public.{_ident(nombre)} SELECT * FROM "
                                 f"json_populate_recordset(NULL::public.{_ident(nombre)}, %s::json)",
                                 ("[" + ",".join(lote) + "]",))
                lote.clear()

        with open(origen / f"{nombre}.jsonl", "rb") as f:
            for linea in f:
                lote.append(linea.decode("utf-8").rstrip("\n"))
                if len(lote) >= LOTE:
                    vaciar()
        vaciar()
        for columna, secuencia in tabla.secuencias.items():
            conexion.execute(f"SELECT setval(%s, COALESCE((SELECT max({_ident(columna)}) FROM "
                             f"public.{_ident(nombre)}), 1), (SELECT count(*) > 0 FROM public.{_ident(nombre)}))",
                             (secuencia,))
    obtenidas = {n: recorrer_tabla(conexion, t, con_xmin=False) for n, t in sorted(catalogo.items())}
    for nombre, huella in obtenidas.items():
        if huella.como_dict() != esperadas[nombre]:
            raise GeneracionNoValida(f"la tabla {nombre} restaurada no coincide con el manifiesto")
    return obtenidas


def huellas_de_archivos(origen: Path, catalogo_nombres) -> dict[str, dict]:
    """Recalcula la huella de contenido de cada `<tabla>.jsonl` (sin base): debe coincidir con el manifiesto."""
    salida = {}
    for nombre in sorted(catalogo_nombres):
        h, n = hashlib.sha256(), 0
        with open(origen / f"{nombre}.jsonl", "rb") as f:
            for linea in f:
                if not linea.endswith(b"\n"):
                    raise GeneracionNoValida(f"{nombre}.jsonl: linea sin terminar")
                json.loads(linea)
                h.update(linea)
                n += 1
        salida[nombre] = {"filas": n, "sha256_contenido": h.hexdigest()}
    return salida
