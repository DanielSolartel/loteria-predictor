"""Perfil y bloqueo compartidos por el visor y su instalador."""

import errno
import json
import os
import secrets
from contextlib import contextmanager, suppress
from pathlib import Path

VERSION = "fase11-piloto-windows/1"
CARPETA_OPERATIVA = "LP11-Operativo"
VERSION_OPERATIVA = "fase11-operativo-windows/1"


class PerfilPilotoError(RuntimeError):
    pass


def _sin_enlace(ruta: Path) -> None:
    if ruta.is_symlink() or ruta.is_junction():
        raise PerfilPilotoError(f"La ruta {ruta.name} es un enlace.")


def _guardar(ruta: Path, datos: dict) -> None:
    temporal = ruta.with_name(f".{ruta.name}.{secrets.token_hex(4)}.tmp")
    try:
        with temporal.open("x", encoding="utf-8") as f:
            f.write(json.dumps(datos, ensure_ascii=False, indent=2) + "\n")
        temporal.replace(ruta)
    finally:
        temporal.unlink(missing_ok=True)


def _directorio_local(carpeta: str = "LP11", version: str = VERSION) -> Path:
    raiz = Path(os.environ["LOCALAPPDATA"]).resolve(strict=True) / carpeta
    identificacion = raiz / "perfil.json"
    esperado = {"piloto": version}
    try:
        raiz.mkdir(mode=0o700)
    except FileExistsError:
        _sin_enlace(raiz)
        _sin_enlace(identificacion)
        if json.loads(identificacion.read_text(encoding="utf-8")) != esperado:
            raise PerfilPilotoError(f"La carpeta local {carpeta} pertenece a otra aplicación o ensayo.")
    else:
        try:
            _guardar(identificacion, esperado)
        except BaseException:
            with suppress(OSError):
                raiz.rmdir()
            raise
    return raiz


@contextmanager
def _instancia_unica(directorio: Path):
    ruta = directorio / "instancia.lock"
    _sin_enlace(ruta)
    descriptor = os.open(ruta, os.O_RDWR | os.O_CREAT, 0o600)
    tomado = False
    try:
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            tomado = True
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
        yield tomado
    finally:
        try:
            if tomado and os.name == "nt":
                with suppress(OSError):
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(descriptor)
