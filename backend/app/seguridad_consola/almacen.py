"""Almacén privado de seguridad de la consola local (Fase 10, E10.1).

Un archivo SQLite propio (biblioteca estándar `sqlite3`) con cuentas, sesiones, presesiones, intentos y
auditoría. Está separado de PostgreSQL operativo (no hay migraciones de la base de Fase 6), de Git
(`backend/privado/` está en `.gitignore`) y de los almacenes publicables de `storage/`.

- **Sin efectos al importar:** abrir el almacén nunca crea el archivo (`mode=rw`). Solo
  `AlmacenSeguridad.crear` (CLI `scripts.consola_cuentas`) crea el directorio y el archivo.
- **Coordinación entre procesos:** cada escritura es una transacción `BEGIN IMMEDIATE` de SQLite, que
  bloquea a los demás escritores (servidor o CLI) a nivel de archivo, con `busy_timeout`.
- **Secretos:** de cada sesión y presesión se guarda solo el SHA-256 de su identificador; de cada
  contraseña, su hash scrypt. El token CSRF no se guarda: se deriva con HMAC del identificador de la
  sesión, que solo conoce el navegador que la posee.
- **Fallo cerrado:** archivo ausente, ilegible, con otro esquema, con permisos no admitidos o imposibles de
  verificar (POSIX y Windows, archivo y directorio, en cada apertura: `permisos.py`) o sin ninguna cuenta
  activa → `ConsolaNoDisponible`. La consola responde 503 y no sirve datos ni acciones.
- **Admisión de accesos (v2):** la presesión se consume y la verificación se reserva en una sola transacción
  `BEGIN IMMEDIATE`, antes del hash costoso. Como mucho una verificación en curso por usuario normalizado y
  `MAX_VERIFICACIONES_EN_CURSO` en total; las reservas caducan (`ADMISION_DURACION`) si un proceso muere.
- **Retención (v2):** la auditoría se poda en la misma transacción de cada evento, por cualquiera de sus vías.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.seguridad_consola import credenciales as cr
from app.seguridad_consola import permisos

ROLES = ("lector", "operador", "administrador")
NIVEL = {r: i for i, r in enumerate(ROLES)}
USUARIO = re.compile(r"[a-z][a-z0-9_.-]{2,31}")
APLICACION = "loteria-predictor/consola-local"
ESQUEMA = 2  # v2: tabla `admisiones`

INACTIVIDAD = 30 * 60
ABSOLUTA = 12 * 3600
TOQUE_MINIMO = 60
PRESESION_DURACION = 10 * 60
MAX_PRESESIONES = 200
MAX_SESIONES_POR_CUENTA = 5
MAX_AUDITORIA = 20_000
MAX_INTENTOS = 5_000
FALLOS_PARA_BLOQUEO = 5
VENTANA_FALLOS = 15 * 60
BLOQUEO = 15 * 60
ESPERA_MAXIMA = 30
MAX_VERIFICACIONES_EN_CURSO = 2  # en todo el almacén (todas las cuentas y procesos)
ADMISION_DURACION = 30  # s; una reserva no liberada (proceso terminado) deja de contar


class ConsolaNoDisponible(Exception):
    """La consola no puede atender: el motivo es un código estable, sin rutas ni secretos."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


class OperacionRechazada(ValueError):
    """Una operación de cuentas no se permite (mensaje para la CLI, sin secretos)."""


@dataclass(frozen=True)
class Sesion:
    usuario: str
    rol: str
    csrf: str
    expira_inactividad: float
    expira_absoluta: float


def _hash(valor: str) -> str:
    return hashlib.sha256(valor.encode("ascii", "strict")).hexdigest()


def identificador_valido(valor: str | None) -> bool:
    return isinstance(valor, str) and re.fullmatch(r"[A-Za-z0-9_-]{43,64}", valor) is not None


def derivar_csrf(identificador: str, proposito: str) -> str:
    """Solo para identificadores con forma válida (ASCII acotado); los demás se rechazan antes (ValueError)."""
    if not identificador_valido(identificador):
        raise ValueError("identificador_no_valido")
    return hmac.new(identificador.encode("ascii"), ("csrf:" + proposito).encode("ascii"), hashlib.sha256).hexdigest()


def texto_seguro(valor, maximo: int = 120) -> str:
    """Texto apto para registros y auditoría: sin controles ni saltos de línea, acotado."""
    s = "".join(c if c.isprintable() and c not in "\r\n\t" else "?" for c in str(valor))
    return s[:maximo]


_ESQUEMA_SQL = """
CREATE TABLE meta (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE cuentas (
    id INTEGER PRIMARY KEY, usuario TEXT NOT NULL UNIQUE, hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('lector','operador','administrador')),
    activa INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1,
    creada REAL NOT NULL, actualizada REAL NOT NULL);
CREATE TABLE sesiones (
    id_hash TEXT PRIMARY KEY, cuenta INTEGER NOT NULL REFERENCES cuentas(id) ON DELETE CASCADE,
    version INTEGER NOT NULL, creada REAL NOT NULL, ultimo_uso REAL NOT NULL, expira REAL NOT NULL);
CREATE INDEX sesiones_cuenta ON sesiones(cuenta);
CREATE TABLE presesiones (id_hash TEXT PRIMARY KEY, creada REAL NOT NULL, expira REAL NOT NULL);
CREATE TABLE intentos (clave TEXT PRIMARY KEY, fallos INTEGER NOT NULL, primero REAL NOT NULL,
    siguiente REAL NOT NULL, bloqueado_hasta REAL NOT NULL, actualizado REAL NOT NULL);
CREATE TABLE auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, en TEXT NOT NULL, usuario TEXT NOT NULL,
    evento TEXT NOT NULL, detalle TEXT NOT NULL, resultado TEXT NOT NULL);
CREATE TABLE admisiones (id TEXT PRIMARY KEY, clave TEXT NOT NULL, expira REAL NOT NULL);
CREATE INDEX admisiones_clave ON admisiones(clave);
"""


def _restringir(ruta: Path, *, directorio: bool) -> None:
    try:
        permisos.restringir(ruta, directorio=directorio)
    except permisos.ErrorPermisos as error:
        raise OperacionRechazada(f"No se pudieron dejar los permisos solo para el propietario ({error.motivo}); "
                                 "el almacén no se usa.") from error


class AlmacenSeguridad:
    def __init__(self, archivo: str | os.PathLike, *, parametros: cr.ParametrosScrypt = cr.PRODUCCION,
                 minimos: cr.ParametrosScrypt = cr.PRODUCCION, reloj=time.time):
        self.archivo = Path(archivo)
        self.parametros = parametros
        self.minimos = minimos
        self._reloj = reloj
        self._ficticio: str | None = None

    # ------------------------------------------------------------------ apertura
    @classmethod
    def crear(cls, archivo: str | os.PathLike, **kw) -> "AlmacenSeguridad":
        """Crea el directorio (si falta) y el archivo con permisos del propietario. Nunca reemplaza uno existente."""
        ruta = Path(archivo)
        if ruta.exists():
            raise OperacionRechazada("El almacén de seguridad ya existe; no se reemplaza.")
        directorio = ruta.parent
        if directorio.exists():
            # Un directorio que ya existía no se modifica: debe cumplir ya la política del propietario.
            try:
                permisos.verificar(directorio, directorio=True)
            except permisos.ErrorPermisos as error:
                raise OperacionRechazada(f"El directorio del almacén ya existe y sus permisos no son solo del "
                                         f"propietario ({error.motivo}); no se modifica. Use un directorio nuevo.") from error
        else:
            directorio.parent.mkdir(parents=True, exist_ok=True)
            directorio.mkdir(mode=0o700)  # falla si otro proceso lo crea a la vez
            _restringir(directorio, directorio=True)
        descriptor = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
        os.close(descriptor)
        try:
            _restringir(ruta, directorio=False)
            conexion = sqlite3.connect(ruta, isolation_level=None)
            try:
                conexion.executescript(_ESQUEMA_SQL)
                conexion.execute("INSERT INTO meta VALUES ('aplicacion', ?), ('esquema', ?)", (APLICACION, str(ESQUEMA)))
            finally:
                conexion.close()
        except BaseException:
            ruta.unlink(missing_ok=True)  # solo el archivo que este proceso acaba de crear
            raise
        return cls(ruta, **kw)

    def _conectar(self) -> sqlite3.Connection:
        if not self.archivo.is_file():
            raise ConsolaNoDisponible("no_provisionada")
        try:
            permisos.verificar(self.archivo.parent, directorio=True)
            permisos.verificar(self.archivo, directorio=False)
        except permisos.ErrorPermisos as error:
            raise ConsolaNoDisponible("permisos" if error.verificable else "permisos_no_verificables") from error
        try:
            conexion = sqlite3.connect(self.archivo.resolve().as_uri() + "?mode=rw", uri=True, timeout=5,
                                       isolation_level=None)
            conexion.execute("PRAGMA busy_timeout = 5000")
            conexion.execute("PRAGMA foreign_keys = ON")
            meta = dict(conexion.execute("SELECT clave, valor FROM meta").fetchall())
        except sqlite3.Error as error:
            raise ConsolaNoDisponible("corrupta") from error
        if meta.get("aplicacion") != APLICACION or meta.get("esquema") != str(ESQUEMA):
            conexion.close()
            raise ConsolaNoDisponible("esquema")
        return conexion

    @contextmanager
    def _lectura(self):
        conexion = self._conectar()
        try:
            yield conexion
        except sqlite3.Error as error:
            raise ConsolaNoDisponible("corrupta") from error
        finally:
            conexion.close()

    @contextmanager
    def _escritura(self):
        conexion = self._conectar()
        try:
            conexion.execute("BEGIN IMMEDIATE")
            try:
                yield conexion
            except BaseException:
                conexion.execute("ROLLBACK")
                raise
            conexion.execute("COMMIT")
        except sqlite3.Error as error:
            raise ConsolaNoDisponible("corrupta") from error
        finally:
            conexion.close()

    def comprobar(self) -> None:
        """Lanza `ConsolaNoDisponible` si la consola no puede atender (incluido: sin cuentas activas)."""
        with self._lectura() as c:
            if c.execute("SELECT count(*) FROM cuentas WHERE activa = 1").fetchone()[0] == 0:
                raise ConsolaNoDisponible("sin_cuentas")

    # ------------------------------------------------------------------ auditoría
    def auditar(self, usuario: str, evento: str, detalle: str, resultado: str, conexion=None) -> None:
        fila = (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._reloj())), texto_seguro(usuario, 40),
                texto_seguro(evento, 40), texto_seguro(detalle, 200), texto_seguro(resultado, 40))
        if conexion is not None:  # dentro de la transacción de la operación auditada (atómico con ella)
            self._insertar_auditoria(conexion, fila)
            return
        with self._escritura() as c:
            self._insertar_auditoria(c, fila)

    @staticmethod
    def _insertar_auditoria(c, fila) -> None:
        """Inserta y aplica la retención en la misma transacción, por cualquiera de las vías de `auditar`."""
        cursor = c.execute("INSERT INTO auditoria (en, usuario, evento, detalle, resultado) VALUES (?,?,?,?,?)", fila)
        c.execute("DELETE FROM auditoria WHERE id <= ?", (cursor.lastrowid - MAX_AUDITORIA,))

    def auditoria(self, limite: int = 50) -> list[dict]:
        with self._lectura() as c:
            filas = c.execute("SELECT en, usuario, evento, detalle, resultado FROM auditoria ORDER BY id DESC LIMIT ?",
                              (max(1, min(limite, 1000)),)).fetchall()
        return [dict(zip(("en", "usuario", "evento", "detalle", "resultado"), f)) for f in filas]

    # ------------------------------------------------------------------ cuentas (CLI)
    @staticmethod
    def _validar_usuario(usuario: str) -> str:
        if not isinstance(usuario, str) or not USUARIO.fullmatch(usuario):
            raise OperacionRechazada("Usuario no válido: 3-32 caracteres, minúsculas, dígitos, '_', '.' o '-', "
                                     "empezando por letra.")
        return usuario

    @staticmethod
    def _validar_rol(rol: str) -> str:
        if rol not in ROLES:
            raise OperacionRechazada(f"Rol no válido; use uno de: {', '.join(ROLES)}.")
        return rol

    def _cuenta(self, c, usuario: str):
        fila = c.execute("SELECT id, rol, activa FROM cuentas WHERE usuario = ?", (usuario,)).fetchone()
        if fila is None:
            raise OperacionRechazada("La cuenta no existe.")
        return fila

    def _administradores_activos(self, c, excluir: int | None = None) -> int:
        return c.execute("SELECT count(*) FROM cuentas WHERE activa = 1 AND rol = 'administrador' AND id IS NOT ?",
                         (excluir,)).fetchone()[0]

    def crear_cuenta(self, usuario: str, contrasena: str, rol: str, *, actor: str = "cli") -> None:
        usuario, rol = self._validar_usuario(usuario), self._validar_rol(rol)
        codificado = cr.crear_hash(contrasena, self.parametros)
        ahora = self._reloj()
        with self._escritura() as c:
            if c.execute("SELECT 1 FROM cuentas WHERE usuario = ?", (usuario,)).fetchone():
                raise OperacionRechazada("La cuenta ya existe.")
            c.execute("INSERT INTO cuentas (usuario, hash, rol, activa, version, creada, actualizada) "
                      "VALUES (?,?,?,1,1,?,?)", (usuario, codificado, rol, ahora, ahora))
            self.auditar(actor, "cuenta_creada", f"usuario={usuario} rol={rol}", "ok", c)

    def cambiar_contrasena(self, usuario: str, contrasena: str, *, actor: str = "cli") -> None:
        usuario = self._validar_usuario(usuario)
        codificado = cr.crear_hash(contrasena, self.parametros)
        with self._escritura() as c:
            ident, _rol, _activa = self._cuenta(c, usuario)
            c.execute("UPDATE cuentas SET hash = ?, version = version + 1, actualizada = ? WHERE id = ?",
                      (codificado, self._reloj(), ident))
            c.execute("DELETE FROM sesiones WHERE cuenta = ?", (ident,))
            self.auditar(actor, "contrasena_cambiada", f"usuario={usuario}", "ok", c)

    def cambiar_rol(self, usuario: str, rol: str, *, actor: str = "cli") -> None:
        usuario, rol = self._validar_usuario(usuario), self._validar_rol(rol)
        with self._escritura() as c:
            ident, anterior, activa = self._cuenta(c, usuario)
            if anterior == "administrador" and rol != "administrador" and activa and \
                    self._administradores_activos(c, excluir=ident) == 0:
                raise OperacionRechazada("Es el único administrador activo; cree otro antes de cambiar su rol.")
            c.execute("UPDATE cuentas SET rol = ?, version = version + 1, actualizada = ? WHERE id = ?",
                      (rol, self._reloj(), ident))
            c.execute("DELETE FROM sesiones WHERE cuenta = ?", (ident,))
            self.auditar(actor, "rol_cambiado", f"usuario={usuario} {anterior}->{rol}", "ok", c)

    def desactivar(self, usuario: str, *, actor: str = "cli") -> None:
        usuario = self._validar_usuario(usuario)
        with self._escritura() as c:
            ident, rol, activa = self._cuenta(c, usuario)
            if rol == "administrador" and activa and self._administradores_activos(c, excluir=ident) == 0:
                raise OperacionRechazada("Es el único administrador activo; cree otro antes de desactivarlo.")
            c.execute("UPDATE cuentas SET activa = 0, version = version + 1, actualizada = ? WHERE id = ?",
                      (self._reloj(), ident))
            c.execute("DELETE FROM sesiones WHERE cuenta = ?", (ident,))
            self.auditar(actor, "cuenta_desactivada", f"usuario={usuario}", "ok", c)

    def activar(self, usuario: str, *, actor: str = "cli") -> None:
        usuario = self._validar_usuario(usuario)
        with self._escritura() as c:
            ident, _rol, _activa = self._cuenta(c, usuario)
            c.execute("UPDATE cuentas SET activa = 1, version = version + 1, actualizada = ? WHERE id = ?",
                      (self._reloj(), ident))
            self.auditar(actor, "cuenta_activada", f"usuario={usuario}", "ok", c)

    def revocar_sesiones(self, usuario: str | None = None, *, actor: str = "cli") -> int:
        with self._escritura() as c:
            if usuario is None:
                n = c.execute("DELETE FROM sesiones").rowcount
            else:
                ident, _rol, _activa = self._cuenta(c, self._validar_usuario(usuario))
                n = c.execute("DELETE FROM sesiones WHERE cuenta = ?", (ident,)).rowcount
            self.auditar(actor, "sesiones_revocadas", f"usuario={usuario or '*'} total={n}", "ok", c)
        return n

    def cuentas(self) -> list[dict]:
        with self._lectura() as c:
            filas = c.execute("SELECT usuario, rol, activa, (SELECT count(*) FROM sesiones s WHERE s.cuenta = cuentas.id) "
                              "FROM cuentas ORDER BY usuario").fetchall()
        return [{"usuario": u, "rol": r, "activa": bool(a), "sesiones": n} for u, r, a, n in filas]

    # ------------------------------------------------------------------ presesiones (formulario de acceso)
    def crear_presesion(self) -> str:
        identificador = secrets.token_urlsafe(32)
        ahora = self._reloj()
        with self._escritura() as c:
            c.execute("DELETE FROM presesiones WHERE expira < ?", (ahora,))
            c.execute("INSERT INTO presesiones VALUES (?,?,?)", (_hash(identificador), ahora, ahora + PRESESION_DURACION))
            c.execute("DELETE FROM presesiones WHERE id_hash IN (SELECT id_hash FROM presesiones ORDER BY creada DESC "
                      "LIMIT -1 OFFSET ?)", (MAX_PRESESIONES,))
        return identificador

    def presesion_valida(self, identificador: str | None) -> bool:
        if not identificador_valido(identificador):
            return False
        with self._lectura() as c:
            fila = c.execute("SELECT expira FROM presesiones WHERE id_hash = ?", (_hash(identificador),)).fetchone()
        return fila is not None and fila[0] >= self._reloj()

    # ------------------------------------------------------------------ intentos
    @staticmethod
    def clave_intento(usuario: str) -> str:
        return "u:" + hashlib.sha256(usuario.strip().lower().encode("utf-8", "replace")).hexdigest()

    def espera_requerida(self, claves: list[str]) -> int:
        """Segundos que faltan para admitir un intento (0 si se admite)."""
        ahora = self._reloj()
        with self._lectura() as c:
            espera = 0.0
            for clave in claves:
                fila = c.execute("SELECT siguiente, bloqueado_hasta FROM intentos WHERE clave = ?", (clave,)).fetchone()
                if fila:
                    espera = max(espera, fila[0] - ahora, fila[1] - ahora)
        return int(espera + 0.999) if espera > 0 else 0

    def _registrar_fallo(self, c, clave: str, ahora: float) -> None:
        fila = c.execute("SELECT fallos, primero FROM intentos WHERE clave = ?", (clave,)).fetchone()
        fallos, primero = (1, ahora) if fila is None or ahora - fila[1] > VENTANA_FALLOS else (fila[0] + 1, fila[1])
        siguiente = ahora + min(2 ** (fallos - 1), ESPERA_MAXIMA)
        bloqueado = ahora + BLOQUEO if fallos >= FALLOS_PARA_BLOQUEO else 0.0
        c.execute("INSERT INTO intentos VALUES (?,?,?,?,?,?) ON CONFLICT(clave) DO UPDATE SET fallos = excluded.fallos, "
                  "primero = excluded.primero, siguiente = excluded.siguiente, bloqueado_hasta = excluded.bloqueado_hasta, "
                  "actualizado = excluded.actualizado", (clave, fallos, primero, siguiente, bloqueado, ahora))
        c.execute("DELETE FROM intentos WHERE actualizado < ? AND bloqueado_hasta < ?", (ahora - 86400, ahora))
        c.execute("DELETE FROM intentos WHERE clave IN (SELECT clave FROM intentos ORDER BY actualizado DESC "
                  "LIMIT -1 OFFSET ?)", (MAX_INTENTOS,))

    # ------------------------------------------------------------------ autenticación
    def autenticar(self, usuario: str, contrasena: str, presesion: str, cliente: str) -> tuple[str, str | None]:
        """Devuelve (resultado, identificador de sesión nueva o None). Resultados: `ok`, `credenciales`
        (usuario o contraseña no válidos), `espera` (limitación de intentos o verificación ya en curso) o
        `presesion`.

        v2 (E101-SEC-02). Fases:
        1. Admisión, en UNA transacción `BEGIN IMMEDIATE` (serializa solicitudes y procesos): se consume la
           presesión (borrado condicionado: solo una solicitud la obtiene), se comprueban espera y bloqueo, y
           se reserva la verificación si no hay otra en curso para el mismo usuario ni se supera el máximo
           global. Sin reserva no se calcula ningún hash.
        2. Verificación scrypt fuera de la transacción (no bloquea a los demás).
        3. Resolución, en otra transacción: se libera la reserva y se registra el fallo o se crea la sesión
           (si la cuenta cambió durante la verificación, no se crea). La reserva se libera también si la
           verificación falla por excepción; si el proceso muere, caduca a los `ADMISION_DURACION` s.
        """
        ahora = self._reloj()
        usuario_texto = usuario if isinstance(usuario, str) else ""
        # Limitación por usuario normalizado (exista o no la cuenta). No se limita por cliente: en la consola
        # todos los clientes son loopback y un bloqueo por cliente dejaría fuera a todas las cuentas.
        clave = self.clave_intento(usuario_texto)
        visible = usuario_texto if USUARIO.fullmatch(usuario_texto) else "(no válido)"
        if not identificador_valido(presesion):
            self.auditar(visible, "acceso", "presesion ausente o no válida", "rechazado")
            return "presesion", None
        reserva = secrets.token_hex(16)
        with self._escritura() as c:
            if c.execute("DELETE FROM presesiones WHERE id_hash = ? AND expira >= ?",
                         (_hash(presesion), ahora)).rowcount != 1:
                self.auditar(visible, "acceso", "presesion ausente, caducada o ya usada", "rechazado", c)
                return "presesion", None
            fila = c.execute("SELECT siguiente, bloqueado_hasta FROM intentos WHERE clave = ?", (clave,)).fetchone()
            if fila and max(fila[0], fila[1]) > ahora:
                self.auditar(visible, "acceso", "limitación de intentos", "bloqueado", c)
                return "espera", None
            c.execute("DELETE FROM admisiones WHERE expira < ?", (ahora,))
            propias = c.execute("SELECT count(*) FROM admisiones WHERE clave = ?", (clave,)).fetchone()[0]
            total = c.execute("SELECT count(*) FROM admisiones").fetchone()[0]
            if propias >= 1 or total >= MAX_VERIFICACIONES_EN_CURSO:
                self.auditar(visible, "acceso", "verificación ya en curso", "bloqueado", c)
                return "espera", None
            c.execute("INSERT INTO admisiones VALUES (?,?,?)", (reserva, clave, ahora + ADMISION_DURACION))
            cuenta = c.execute("SELECT id, hash, version FROM cuentas WHERE usuario = ? AND activa = 1",
                               (usuario_texto,)).fetchone()
        resuelta = False
        try:
            if cuenta is None:
                if self._ficticio is None:
                    self._ficticio = cr.hash_ficticio(self.parametros)
                cr.verificar(contrasena or "", self._ficticio, self.minimos)
                correcta = False
            else:
                correcta = cr.verificar(contrasena or "", cuenta[1], self.minimos)
            ahora = self._reloj()
            with self._escritura() as c:
                c.execute("DELETE FROM admisiones WHERE id = ?", (reserva,))
                resuelta = True
                vigente = cuenta is not None and c.execute(
                    "SELECT 1 FROM cuentas WHERE id = ? AND version = ? AND activa = 1", (cuenta[0], cuenta[2])).fetchone()
                if not correcta or not vigente:
                    self._registrar_fallo(c, clave, ahora)
                    self.auditar(visible, "acceso", "credenciales no válidas", "rechazado", c)
                    return "credenciales", None
                c.execute("DELETE FROM intentos WHERE clave = ?", (clave,))
                identificador = secrets.token_urlsafe(32)
                c.execute("INSERT INTO sesiones VALUES (?,?,?,?,?,?)",
                          (_hash(identificador), cuenta[0], cuenta[2], ahora, ahora, ahora + ABSOLUTA))
                c.execute("DELETE FROM sesiones WHERE cuenta = ? AND id_hash IN (SELECT id_hash FROM sesiones "
                          "WHERE cuenta = ? ORDER BY creada DESC LIMIT -1 OFFSET ?)",
                          (cuenta[0], cuenta[0], MAX_SESIONES_POR_CUENTA))
                c.execute("DELETE FROM sesiones WHERE expira < ? OR ultimo_uso < ?", (ahora, ahora - INACTIVIDAD))
                self.auditar(visible, "acceso", "sesión iniciada", "ok", c)
            return "ok", identificador
        finally:
            if not resuelta:  # excepción durante la verificación: la reserva no queda ocupada
                try:
                    with self._escritura() as c:
                        c.execute("DELETE FROM admisiones WHERE id = ?", (reserva,))
                except ConsolaNoDisponible:
                    pass  # caduca sola a los ADMISION_DURACION s

    def sesion(self, identificador: str | None) -> Sesion | None:
        """Sesión vigente con el rol ACTUAL de su cuenta; None si no existe, caducó, la cuenta está inactiva o
        su versión cambió (contraseña, rol o desactivación)."""
        if not identificador_valido(identificador):
            return None
        ahora = self._reloj()
        clave = _hash(identificador)
        with self._lectura() as c:
            fila = c.execute("SELECT s.ultimo_uso, s.expira, s.version, k.version, k.activa, k.usuario, k.rol "
                             "FROM sesiones s JOIN cuentas k ON k.id = s.cuenta WHERE s.id_hash = ?", (clave,)).fetchone()
        if fila is None:
            return None
        ultimo, expira, version_sesion, version_cuenta, activa, usuario, rol = fila
        if not activa or version_sesion != version_cuenta or ahora > expira or ahora - ultimo > INACTIVIDAD:
            with self._escritura() as c:
                c.execute("DELETE FROM sesiones WHERE id_hash = ?", (clave,))
            return None
        if ahora - ultimo >= TOQUE_MINIMO:
            with self._escritura() as c:
                c.execute("UPDATE sesiones SET ultimo_uso = ? WHERE id_hash = ?", (ahora, clave))
            ultimo = ahora
        return Sesion(usuario, rol, derivar_csrf(identificador, "sesion"), ultimo + INACTIVIDAD, expira)

    def cerrar_sesion(self, identificador: str | None, usuario: str) -> None:
        if not identificador_valido(identificador):
            return
        with self._escritura() as c:
            c.execute("DELETE FROM sesiones WHERE id_hash = ?", (_hash(identificador),))
            self.auditar(usuario, "salida", "sesión cerrada", "ok", c)


def rol_suficiente(rol: str, requerido: str) -> bool:
    return rol in NIVEL and requerido in NIVEL and NIVEL[rol] >= NIVEL[requerido]


BACKEND = Path(__file__).resolve().parents[2]


def ruta_predeterminada(directorio: str | Path) -> Path:
    """Archivo del almacén. Una ruta relativa se interpreta desde `backend/` (no desde el directorio actual), para
    que la CLI y el servidor usen siempre el mismo archivo."""
    carpeta = Path(directorio)
    return (carpeta if carpeta.is_absolute() else BACKEND / carpeta) / "seguridad.sqlite3"


def plataforma() -> str:
    return sys.platform
