"""
Registro de ejecuciones de la operacion diaria y cerrojos por juego
(Producto 3).

REGISTRO. Una ejecucion es un JSON en `<directorio>/ejecuciones/<id>.json`,
separado de los artefactos de pronostico. Solo lo escribe el trabajador que
la ejecuta; cada actualizacion se escribe en un temporal y se publica con
`os.replace` (aqui si se quiere sustituir: es el estado de una sola
ejecucion), asi que un lector nunca ve un estado a medio escribir. No
contiene credenciales ni respuestas HTML: los mensajes se recortan antes.

CERROJOS. Un archivo `<directorio>/cerrojos/<JUEGO>.lock` por juego,
bloqueado con el bloqueo del sistema operativo (`fcntl.flock` en POSIX,
`msvcrt.locking` en Windows) sin esperar. El bloqueo excluye tanto a otro
proceso (el comando frente al servidor) como a otro hilo del mismo proceso
(cada adquisicion abre su propio descriptor), y el sistema lo libera si el
proceso muere. Junto al cerrojo, `<JUEGO>.activo` guarda el identificador
de la ejecucion que lo tiene (solo informativo).

Ademas, cada ejecucion toma `<directorio>/cerrojos/ejecuciones/<id>.lock`
y lo mantiene hasta que su trabajador termina (despues de escribir, o de
intentar escribir, el cierre global). Una ejecucion registrada como
`en_curso` cuyo cerrojo de ejecucion no esta tomado no tiene trabajador:
se informa como interrumpida, aunque todos sus juegos hubieran terminado.

La adquisicion es «todos o ninguno» y segura frente a excepciones: si falla
una apertura, un bloqueo o la escritura informativa, se liberan los bloqueos
propios, se cierran sus descriptores y se borran solo los `.activo` escritos
por esta adquisicion; nunca se toca el de otro propietario. Solo la
contencion real (otro tiene el bloqueo) se informa como «ocupado»; cualquier
otro error del sistema operativo se propaga.
"""
from __future__ import annotations

import errno
import json
import os
import re
import secrets
from contextlib import suppress
from pathlib import Path

from app.application.use_cases.operacion_diaria import identificador_valido

_CODIGO = re.compile(r"^[A-Z][A-Z_]{1,29}$")

if os.name == "nt":  # pragma: no cover - solo en Windows
    import msvcrt

    # `msvcrt.locking` con LK_NBLCK falla con EACCES (o EDEADLOCK) si otro
    # tiene la region bloqueada.
    _CONTENCION = frozenset({errno.EACCES, getattr(errno, "EDEADLOCK", errno.EDEADLK)})

    def _bloqueo_del_sistema(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)

    def _desbloquear(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    # `flock` con LOCK_NB falla con EWOULDBLOCK (= EAGAIN) si otro lo tiene.
    _CONTENCION = frozenset({errno.EAGAIN, errno.EWOULDBLOCK})

    def _bloqueo_del_sistema(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _desbloquear(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _bloquear(descriptor: int) -> bool:
    """True si se tomo el bloqueo; False solo si otro lo tiene (contencion).
    Cualquier otro error del sistema operativo se propaga."""
    try:
        _bloqueo_del_sistema(descriptor)
        return True
    except OSError as error:
        if error.errno in _CONTENCION:
            return False
        raise


def _soltar(descriptor: int) -> None:
    try:
        with suppress(OSError):
            _desbloquear(descriptor)
    finally:
        with suppress(OSError):
            os.close(descriptor)


class RegistroEjecucionesArchivo:
    def __init__(self, directorio: str | Path):
        self._carpeta = Path(directorio) / "ejecuciones"

    def _ruta(self, identificador: str) -> Path:
        if not identificador_valido(identificador):
            raise ValueError(f"identificador de ejecucion no valido: {identificador!r}")
        return self._carpeta / f"{identificador}.json"

    def guardar(self, ejecucion: dict) -> None:
        self._carpeta.mkdir(parents=True, exist_ok=True)
        ruta = self._ruta(ejecucion["id"])
        temporal = self._carpeta / f".{ejecucion['id']}.{secrets.token_hex(4)}.tmp"
        with open(temporal, "x", encoding="utf-8") as flujo:
            json.dump(ejecucion, flujo, ensure_ascii=False, indent=1, sort_keys=True)
            flujo.flush()
            os.fsync(flujo.fileno())
        os.replace(temporal, ruta)

    def obtener(self, identificador: str) -> dict | None:
        if not identificador_valido(identificador):
            return None
        ruta = self._ruta(identificador)
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return {"id": identificador, "estado": "ilegible", "juegos": {}, "mensaje": "registro ilegible"}

    def listar(self, limite: int = 20) -> list[dict]:
        """Las mas recientes primero (el identificador empieza por la fecha)."""
        if not self._carpeta.is_dir():
            return []
        nombres = sorted((p.stem for p in self._carpeta.glob("*.json") if identificador_valido(p.stem)), reverse=True)
        return [e for e in (self.obtener(n) for n in nombres[:limite]) if e is not None]


class Cerrojos:
    """Cerrojos adquiridos para una ejecucion. `liberar(juego)` suelta un
    juego; `liberar()` suelta todos y el cerrojo de la ejecucion. Idempotente."""

    def __init__(self, tomados: dict[str, int], carpeta: Path, identificador: str,
                 ejecucion: tuple[int, Path] | None):
        self._tomados = tomados
        self._carpeta = carpeta
        self._identificador = identificador
        self._ejecucion = ejecucion

    @property
    def juegos(self) -> tuple[str, ...]:
        return tuple(self._tomados)

    def _liberar_juego(self, codigo: str) -> None:
        descriptor = self._tomados.pop(codigo, None)
        if descriptor is None:
            return
        activo = self._carpeta / f"{codigo}.activo"
        with suppress(OSError):
            if activo.read_text(encoding="ascii").strip() == self._identificador:
                activo.unlink()
        _soltar(descriptor)

    def liberar(self, codigo: str | None = None) -> None:
        if codigo:
            self._liberar_juego(codigo)
            return
        for c in list(self._tomados):
            self._liberar_juego(c)
        if self._ejecucion is not None:
            descriptor, ruta = self._ejecucion
            self._ejecucion = None
            _soltar(descriptor)
            with suppress(OSError):
                ruta.unlink()


class CerrojoPorJuego:
    def __init__(self, directorio: str | Path):
        self._carpeta = Path(directorio) / "cerrojos"

    def _abrir(self, codigo: str) -> int:
        if not _CODIGO.fullmatch(codigo):
            raise ValueError(f"codigo de juego no admitido: {codigo!r}")
        self._carpeta.mkdir(parents=True, exist_ok=True)
        return os.open(self._carpeta / f"{codigo}.lock", os.O_RDWR | os.O_CREAT, 0o644)

    def _ruta_ejecucion(self, identificador: str) -> Path:
        if not identificador_valido(identificador):
            raise ValueError(f"identificador de ejecucion no valido: {identificador!r}")
        return self._carpeta / "ejecuciones" / f"{identificador}.lock"

    def adquirir(self, codigos, identificador: str) -> Cerrojos | dict[str, str | None]:
        """Todos o ninguno. Devuelve `Cerrojos` o, si alguno esta ocupado,
        {juego: ejecucion activa (o None si no se pudo leer)}. Si falla
        cualquier paso, libera lo propio y propaga el error."""
        tomados: dict[str, int] = {}
        escritos: list[Path] = []
        ejecucion: tuple[int, Path] | None = None
        ocupados: dict[str, str | None] = {}
        try:
            for codigo in codigos:
                descriptor = self._abrir(codigo)
                try:
                    libre = _bloquear(descriptor)
                except BaseException:
                    os.close(descriptor)
                    raise
                if libre:
                    tomados[codigo] = descriptor
                else:
                    os.close(descriptor)
                    ocupados[codigo] = self._activa_declarada(codigo)
            if ocupados:
                for descriptor in tomados.values():
                    _soltar(descriptor)
                return ocupados
            ruta = self._ruta_ejecucion(identificador)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(ruta, os.O_RDWR | os.O_CREAT, 0o644)
            try:
                if not _bloquear(descriptor):
                    raise OSError(errno.EBUSY, f"el cerrojo de la ejecucion {identificador} ya esta tomado")
            except BaseException:
                os.close(descriptor)
                raise
            ejecucion = (descriptor, ruta)
            for codigo in tomados:
                activo = self._carpeta / f"{codigo}.activo"
                escritos.append(activo)
                activo.write_text(identificador + "\n", encoding="ascii")
        except BaseException:
            for activo in escritos:
                with suppress(OSError):
                    activo.unlink()
            for descriptor in tomados.values():
                _soltar(descriptor)
            if ejecucion is not None:
                _soltar(ejecucion[0])
                with suppress(OSError):
                    ejecucion[1].unlink()
            raise
        return Cerrojos(tomados, self._carpeta, identificador, ejecucion)

    def _activa_declarada(self, codigo: str) -> str | None:
        with suppress(OSError):
            valor = (self._carpeta / f"{codigo}.activo").read_text(encoding="ascii").strip()
            return valor if identificador_valido(valor) else None
        return None

    @staticmethod
    def _tomado(ruta: Path) -> bool:
        """True si otro tiene el bloqueo de `ruta`. Solo consulta: si el
        archivo no existe no crea nada."""
        try:
            descriptor = os.open(ruta, os.O_RDWR)
        except FileNotFoundError:
            return False
        try:
            if _bloquear(descriptor):
                with suppress(OSError):
                    _desbloquear(descriptor)
                return False
            return True
        finally:
            os.close(descriptor)

    def ocupado(self, codigo: str) -> bool:
        """True si otro (proceso o hilo) tiene el cerrojo del juego ahora."""
        if not _CODIGO.fullmatch(codigo):
            raise ValueError(f"codigo de juego no admitido: {codigo!r}")
        return self._tomado(self._carpeta / f"{codigo}.lock")

    def activa(self, codigo: str) -> str | None:
        return self._activa_declarada(codigo) if self.ocupado(codigo) else None

    def ejecucion_viva(self, identificador: str) -> bool:
        """True mientras el trabajador de la ejecucion mantiene su cerrojo."""
        return identificador_valido(identificador) and self._tomado(self._ruta_ejecucion(identificador))
