"""Estado privado POSIX, ligado a un descriptor y con un único escritor.

No borra generaciones, bases, claves ni contenedores. Los planes se conservan.
"""
from __future__ import annotations

import contextlib
import os
import re
import secrets
import stat
from pathlib import Path

from .modelo import Plan, Rechazo, canonico, hexadecimal, json_estricto


class Almacen:
    def __init__(self, ruta: Path, *, crear: bool = False):
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
            raise Rechazo("control_requiere_posix")
        self.ruta = ruta.absolute()
        # Abrir cada componente impide redirigir el control con un enlace en un ancestro.
        descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for numero, parte in enumerate(self.ruta.parts[1:]):
                ultimo = numero == len(self.ruta.parts) - 2
                if parte in (".", ".."):
                    raise Rechazo("ruta_de_control")
                if ultimo and crear:
                    try:
                        os.mkdir(parte, 0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                nuevo = os.open(parte, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = nuevo
            st = os.fstat(descriptor)
            if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700:
                raise Rechazo("control_no_es_privado")
            self.fd = descriptor
            descriptor = -1
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        self.bloqueado = False

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def _nombre(nombre: str):
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,90}", nombre):
            raise Rechazo("nombre_de_control")

    def _archivo(self, nombre: str, flags: int, modo: int = 0o600) -> int:
        self._nombre(nombre)
        fd = os.open(nombre, flags | os.O_NOFOLLOW | os.O_NONBLOCK, modo, dir_fd=self.fd)
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1
                or stat.S_IMODE(st.st_mode) != 0o600):
            os.close(fd)
            raise Rechazo("archivo_de_control_no_privado")
        return fd

    @contextlib.contextmanager
    def exclusivo(self):
        import fcntl
        if self.bloqueado:
            raise Rechazo("bloqueo_reentrante")
        fd = self._archivo("bloqueo", os.O_RDWR | os.O_CREAT)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Rechazo("otra_operacion_en_curso") from error
            self.bloqueado = True
            yield self
        finally:
            self.bloqueado = False
            os.close(fd)

    def leer(self, nombre: str, predeterminado=None):
        try:
            fd = self._archivo(nombre, os.O_RDONLY)
        except FileNotFoundError:
            return predeterminado
        with os.fdopen(fd, "rb") as entrada:
            return json_estricto(entrada.read(262145))

    def escribir(self, nombre: str, valor: object):
        if not self.bloqueado:
            raise Rechazo("escritura_sin_bloqueo")
        self._nombre(nombre)
        datos = canonico(valor)
        if len(datos) > 262144:
            raise Rechazo("estado_demasiado_grande")
        temporal = "tmp-" + secrets.token_hex(16)
        fd = self._archivo(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            with os.fdopen(fd, "wb") as salida:
                salida.write(datos)
                salida.flush()
                os.fsync(salida.fileno())
            # No seguir ni sustituir silenciosamente un enlace preexistente.
            try:
                anterior = self._archivo(nombre, os.O_RDONLY)
            except FileNotFoundError:
                pass
            else:
                os.close(anterior)
            os.replace(temporal, nombre, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try:
                os.unlink(temporal, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def inicializar(self) -> dict:
        ausente = object()
        estado = self.leer("estado.json", ausente)
        if estado is ausente:
            estado = {"formato": "control-e105/1", "propietario": secrets.token_hex(16),
                      "raiz": {"dispositivo": os.fstat(self.fd).st_dev, "inodo": os.fstat(self.fd).st_ino},
                      "activa": None, "anterior": None, "pendiente": None, "acceso": "cerrado",
                      "secuencia": 0, "eventos": [],
                      "contadores": {"activadas": 0, "rechazadas": 0, "revertidas": 0, "bloqueadas": 0}}
            self.escribir("estado.json", estado)
        self.validar(estado)
        return estado

    def validar(self, e: object):
        campos = {"formato", "propietario", "raiz", "activa", "anterior", "pendiente", "acceso", "secuencia", "eventos",
                  "contadores"}
        if not isinstance(e, dict) or set(e) != campos or e["formato"] != "control-e105/1":
            raise Rechazo("estado_no_valido")
        if e["raiz"] != {"dispositivo": os.fstat(self.fd).st_dev, "inodo": os.fstat(self.fd).st_ino}:
            raise Rechazo("estado_de_otra_raiz")
        if (not isinstance(e["contadores"], dict)
                or set(e["contadores"]) != {"activadas", "rechazadas", "revertidas", "bloqueadas"}
                or any(type(v) is not int or v < 0 for v in e["contadores"].values())):
            raise Rechazo("contadores_no_validos")
        if (not hexadecimal(e["propietario"], 32) or type(e["secuencia"]) is not int or e["secuencia"] < 0
                or e["acceso"] not in ("cerrado", "abierto", "mantenimiento", "sin_verificar")
                or not isinstance(e["eventos"], list) or len(e["eventos"]) > 100):
            raise Rechazo("estado_no_valido")
        for referencia in (e["activa"], e["anterior"]):
            if referencia is not None:
                self.plan(referencia)
        for evento in e["eventos"]:
            if (not isinstance(evento, dict) or set(evento) != {"n", "en", "tipo", "fase"}
                    or type(evento["n"]) is not int or not isinstance(evento["en"], str)
                    or len(evento["en"]) > 40 or evento["tipo"] not in {
                        "paso", "activacion_iniciada", "activacion_completada", "activacion_fallida",
                        "activacion_revertida", "recuperacion_pendiente", "recuperacion_iniciada"}):
                raise Rechazo("evento_no_valido")
        p = e["pendiente"]
        if p is None and e["acceso"] != ("abierto" if e["activa"] else "cerrado"):
            raise Rechazo("estado_sin_transaccion_incoherente")
        if p is not None:
            if (not isinstance(p, dict) or set(p) != {"candidata", "anterior", "fase", "corte_iniciado"}
                    or p["fase"] not in {"preparar", "arrancar", "validar", "cerrar", "drenar", "detener",
                                        "publicar", "abrir", "sonda", "revertir"}
                    or type(p["corte_iniciado"]) is not bool or p["anterior"] != e["activa"]):
                raise Rechazo("transaccion_no_valida")
            self.plan(p["candidata"])
            if p["candidata"] == p["anterior"]:
                raise Rechazo("transaccion_no_valida")

    def guardar_plan(self, plan: Plan):
        nombre = "p-" + plan.id + ".json"
        ausente = object()
        existente = self.leer(nombre, ausente)
        if existente is not ausente and existente != plan.objeto():
            raise Rechazo("plan_ya_existe_distinto")
        if existente is ausente:
            self.escribir(nombre, plan.objeto())

    def plan(self, referencia: str) -> Plan:
        if not hexadecimal(referencia, 64):
            raise Rechazo("referencia_no_valida")
        p = Plan.de(self.leer("p-" + referencia + ".json"))
        if p.id != referencia:
            raise Rechazo("plan_alterado")
        return p
