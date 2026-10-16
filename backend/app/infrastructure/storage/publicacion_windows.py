"""Reemplazo atomico de un JSON completo en Windows, sin MoveFileExW.

FileRenameInfoEx es la clase *Win32* 22. Sus flags REPLACE_IF_EXISTS y
POSIX_SEMANTICS permiten sustituir un destino abierto por lectores que
comparten DELETE. Un lector que niega ese acceso sigue pudiendo bloquear.
No se degrada a os.replace si el sistema o volumen rechaza esta capacidad.
"""
from __future__ import annotations

import ctypes
import errno
import logging
import ntpath
import os
import platform
import threading
from contextlib import suppress
from pathlib import Path

# Tipos del SDK, no c_ulong/c_wchar del host POSIX (alli pueden medir 8/4).
_DWORD = ctypes.c_uint32
_HANDLE = ctypes.c_void_p
_WCHAR = ctypes.c_uint16
_WINDOWS = os.name == "nt"
_API = "SetFileInformationByHandle(FileRenameInfoEx)"
_CLASE_RENOMBRADO = 22
_FLAGS_RENOMBRADO = 0x1 | 0x2
_SIN_CAPACIDAD = frozenset({1, 50, 120})  # INVALID_FUNCTION, NOT_SUPPORTED, CALL_NOT_IMPLEMENTED
_estado_cierre = threading.local()
_log = logging.getLogger(__name__)


class _UnionReemplazo(ctypes.Union):
    _fields_ = [("ReplaceIfExists", ctypes.c_uint8), ("Flags", _DWORD)]


class _InfoRenombrado(ctypes.Structure):
    _anonymous_ = ("opcion",)
    _fields_ = [("opcion", _UnionReemplazo), ("RootDirectory", _HANDLE),
                ("FileNameLength", _DWORD), ("FileName", _WCHAR * 1)]


def diseno_abi() -> dict:
    """Diseno efectivo; fuera de Windows es solo un modelo, no una ABI nativa."""
    return {"nativo_windows": _WINDOWS, "puntero_bytes": ctypes.sizeof(_HANDLE),
            "DWORD_bytes": ctypes.sizeof(_DWORD), "WCHAR_bytes": ctypes.sizeof(_WCHAR),
            "union_bytes": ctypes.sizeof(_UnionReemplazo),
            "RootDirectory_offset": _InfoRenombrado.RootDirectory.offset,
            "FileNameLength_offset": _InfoRenombrado.FileNameLength.offset,
            "FileName_offset": _InfoRenombrado.FileName.offset,
            "sizeof": ctypes.sizeof(_InfoRenombrado), "alineacion": ctypes.alignment(_InfoRenombrado)}


def _validar_abi_nativa() -> None:
    bits = ctypes.sizeof(_HANDLE)
    esperado = {4: (4, 8, 12, 16, 4), 8: (8, 16, 20, 24, 8)}.get(bits)
    real = (_InfoRenombrado.RootDirectory.offset, _InfoRenombrado.FileNameLength.offset,
            _InfoRenombrado.FileName.offset, ctypes.sizeof(_InfoRenombrado), ctypes.alignment(_InfoRenombrado))
    if real != esperado or ctypes.sizeof(ctypes.c_wchar) != 2 or ctypes.sizeof(_DWORD) != 4:
        raise RuntimeError(f"ABI Windows de FILE_RENAME_INFO no admitida: {diseno_abi()}")


if _WINDOWS:  # pragma: no cover - la llamada al kernel solo puede validarse en Windows
    _validar_abi_nativa()
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _crear_archivo_windows = _kernel32.CreateFileW
    _crear_archivo_windows.argtypes = (ctypes.c_wchar_p, _DWORD, _DWORD, ctypes.c_void_p,
                                      _DWORD, _DWORD, _HANDLE)
    _crear_archivo_windows.restype = _HANDLE
    _cerrar_handle_windows = _kernel32.CloseHandle
    _cerrar_handle_windows.argtypes = (_HANDLE,)
    _cerrar_handle_windows.restype = ctypes.c_int32
    _renombrar_windows = _kernel32.SetFileInformationByHandle
    _renombrar_windows.argtypes = (_HANDLE, ctypes.c_int32, ctypes.c_void_p, _DWORD)
    _renombrar_windows.restype = ctypes.c_int32
    _ruta_volumen_windows = _kernel32.GetVolumePathNameW
    _ruta_volumen_windows.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, _DWORD)
    _ruta_volumen_windows.restype = ctypes.c_int32
    _informacion_volumen_windows = _kernel32.GetVolumeInformationW
    _informacion_volumen_windows.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, _DWORD,
        ctypes.POINTER(_DWORD), ctypes.POINTER(_DWORD), ctypes.POINTER(_DWORD), ctypes.c_wchar_p, _DWORD)
    _informacion_volumen_windows.restype = ctypes.c_int32
    _ultimo_error_windows = ctypes.get_last_error
    _winerror = ctypes.WinError

_HANDLE_INVALIDO = ctypes.c_void_p(-1).value


class PublicacionAtomicaNoDisponibleError(OSError):
    """La API/capacidad requerida no esta disponible; no se ha publicado."""


def _ruta_destino_absoluta(destino: Path) -> str:
    # No resolve/realpath: se reemplaza el nombre, sin seguir un enlace de destino.
    return os.path.abspath(os.fspath(destino))


def _buffer_renombrado(ruta: str):
    """FILE_RENAME_INFO del SDK: union DWORD, HANDLE, longitud en bytes y UTF-16.

    La longitud excluye el NUL. Se reserva ademas el terminador y, como minimo,
    sizeof(FILE_RENAME_INFO). Los caracteres no BMP ocupan dos unidades UTF-16.
    """
    if not isinstance(ruta, str) or "\0" in ruta or not ntpath.isabs(ruta) or not ntpath.splitdrive(ruta)[0]:
        raise ValueError("FileRenameInfoEx necesita una ruta Win32 absoluta sin NUL")
    texto = ruta.encode("utf-16-le", errors="surrogatepass")
    longitud = _InfoRenombrado.FileName.offset + len(texto) + 2
    if longitud > 0xFFFFFFFF:
        raise OverflowError("Buffer FileRenameInfoEx mayor que DWORD")
    buffer = ctypes.create_string_buffer(max(ctypes.sizeof(_InfoRenombrado), longitud))
    cabecera = _InfoRenombrado.from_buffer(buffer)
    cabecera.Flags = _FLAGS_RENOMBRADO
    cabecera.RootDirectory = None
    cabecera.FileNameLength = len(texto)
    ctypes.memmove(ctypes.addressof(buffer) + _InfoRenombrado.FileName.offset, texto, len(texto))
    return buffer


def _error_api(codigo: int, etapa: str, longitud: int) -> OSError:
    original = _winerror(codigo)
    detalle = f"{_API}: {etapa}; clase {_CLASE_RENOMBRADO}, flags {_FLAGS_RENOMBRADO}, buffer {longitud} bytes"
    if etapa == "renombrar" and codigo in _SIN_CAPACIDAD:
        error = PublicacionAtomicaNoDisponibleError(errno.ENOTSUP, detalle + "; capacidad no disponible, sin degradacion a MoveFileExW")
        error.winerror = codigo
        error.__cause__ = original
        return error
    if codigo == 87:
        detalle += "; parametros rechazados: revisar buffer/ABI, clase, flags y soporte; no demuestra por si solo falta de capacidad"
    original.add_note(detalle)
    return original


def publicar(origen: Path, destino: Path) -> None:
    """Renombra el temporal cerrado y completo; cierra siempre su HANDLE propio.

    Los errores conservan winerror para el reintento acotado del registro. No
    se abre el destino para escribir, no se borra y no se usa una API alternativa.
    """
    if not _WINDOWS:
        raise OSError(errno.ENOSYS, _API + " solo se utiliza en Windows")
    buffer = _buffer_renombrado(_ruta_destino_absoluta(destino))
    handle = _crear_archivo_windows(os.fspath(origen), 0x00010000, 0x7, None, 3, 0x80, None)  # DELETE, SHARE_ALL, OPEN_EXISTING
    if handle == _HANDLE_INVALIDO:
        raise _error_api(_ultimo_error_windows(), "abrir temporal con DELETE", len(buffer))
    confirmado = False
    primario = None
    try:
        if not _renombrar_windows(handle, _CLASE_RENOMBRADO, buffer, len(buffer)):
            # Capturar antes de CloseHandle o de cualquier consulta de diagnostico.
            raise _error_api(_ultimo_error_windows(), "renombrar", len(buffer))
        confirmado = True
    except BaseException as error:
        primario = error
        raise
    finally:
        cierre = None
        try:
            if not _cerrar_handle_windows(handle):
                cierre = _winerror(_ultimo_error_windows())
        except OSError as error:
            cierre = error
        if cierre is not None:
            incidencia = {"api": "CloseHandle", "winerror": getattr(cierre, "winerror", None),
                          "errno": cierre.errno, "publicacion_confirmada": confirmado}
            previa = getattr(_estado_cierre, "incidencia", None)
            if previa is None:
                _estado_cierre.incidencia = {**incidencia, "total": 1}
            else:
                previa["total"] += 1
            if primario is not None:
                primario.incidencia_cierre = incidencia
                primario.add_note(f"Fallo secundario de cierre del HANDLE propio: {incidencia}")
            # Si ya se renombro no se puede informar que no se publico ni
            # reintentar un commit consumado. El diagnostico y el log lo exponen;
            # el paso focal rechaza acreditar una ejecucion con este incidente.
            with suppress(Exception):  # ni un fallo del logger sustituye el error inicial
                _log.warning("Fallo de cierre del HANDLE propio: %s", incidencia)


def diagnostico(carpeta: Path) -> dict:
    """Solo metadatos del volumen sintetico; no abre sus JSON ni seriales del disco."""
    salida = {"api": _API, "clase": _CLASE_RENOMBRADO, "flags": _FLAGS_RENOMBRADO,
              "plataforma": platform.platform(), "abi": diseno_abi(), "fallback": False,
              "incidencia_cierre": getattr(_estado_cierre, "incidencia", None)}
    if not _WINDOWS:
        return {**salida, "volumen": {"estado": "no_es_windows_modelo_portable"}}
    raiz = ctypes.create_unicode_buffer(32768)
    if not _ruta_volumen_windows(os.path.abspath(os.fspath(carpeta)), raiz, len(raiz)):
        return {**salida, "volumen": {"error_win32": _ultimo_error_windows(), "etapa": "GetVolumePathNameW"}}
    nombre = ctypes.create_unicode_buffer(256)
    flags = _DWORD()
    if not _informacion_volumen_windows(raiz.value, None, 0, None, None, ctypes.byref(flags), nombre, len(nombre)):
        return {**salida, "volumen": {"raiz": raiz.value, "error_win32": _ultimo_error_windows(), "etapa": "GetVolumeInformationW"}}
    salida["volumen"] = {"raiz": raiz.value, "sistema_archivos": nombre.value, "flags": flags.value,
                          "anuncia_posix_unlink_rename": bool(flags.value & 0x400),
                          "nota": "el anuncio no sustituye el control real de publicacion con handle retenido"}
    return salida
