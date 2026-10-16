"""Contrato portable del adaptador Win32 del lector de ejecuciones.

Los dobles de CreateFileW y msvcrt verifican acceso, comparticion y propiedad
del recurso. Los descriptores de los casos integrados son reales. Esto no
ejecuta un kernel Windows: la compatibilidad de reemplazo con handles reales
se comprueba ademas en las regresiones de publicacion de la misma bateria.
"""
from __future__ import annotations

import ast
import ctypes
from ctypes import wintypes
import errno
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from app.infrastructure.storage import operacion_file_store as ofs


ID = "20261013T135713Z-dc2deb60"


def _error_windows(codigo):
    clase = FileNotFoundError if codigo in {2, 3} else PermissionError if codigo in {5, 32, 33} else OSError
    error = clase(errno.ENOENT if codigo in {2, 3} else errno.EACCES, "error sintetico de apertura")
    error.winerror = codigo
    return error


def _api(monkeypatch, *, crear=None, convertir=None, cerrar=None, codigo_error=32):
    llamadas = {"crear": [], "convertir": [], "cerrar": []}
    # Un valor mayor que 32 bits permite descubrir conversiones truncadas.
    handle = (1 << 42) + 123

    def apertura(*args):
        llamadas["crear"].append(args)
        return handle if crear is None else crear(*args)

    def conversion(*args):
        llamadas["convertir"].append(args)
        return 47 if convertir is None else convertir(*args)

    def cierre(valor):
        llamadas["cerrar"].append(valor)
        return True if cerrar is None else cerrar(valor)

    monkeypatch.setattr(ofs, "_crear_archivo_windows", apertura, raising=False)
    monkeypatch.setattr(ofs, "_cerrar_handle_windows", cierre, raising=False)
    monkeypatch.setattr(ofs, "_HANDLE_INVALIDO", ctypes.c_void_p(-1).value, raising=False)
    monkeypatch.setattr(ofs, "msvcrt", SimpleNamespace(open_osfhandle=conversion), raising=False)
    monkeypatch.setattr(ofs, "ctypes", SimpleNamespace(WinError=_error_windows,
                                                     get_last_error=lambda: codigo_error), raising=False)
    monkeypatch.setattr(ofs.os, "O_BINARY", getattr(os, "O_BINARY", 0x8000), raising=False)
    monkeypatch.setattr(ofs.os, "O_NOINHERIT", getattr(os, "O_NOINHERIT", 0x80), raising=False)
    return llamadas, handle


def test_lector_win32_solo_lee_y_comparte_reemplazo_sin_truncar_el_handle(tmp_path, monkeypatch):
    llamadas, handle = _api(monkeypatch)
    ruta = tmp_path / "registro con ñ.json"
    descriptor = ofs._descriptor_lectura_windows(ruta, os.O_RDONLY)
    assert descriptor == 47
    assert llamadas["crear"] == [(str(ruta), 0x80000000, 7, None, 3, 0x80, None)]
    assert llamadas["convertir"] == [(handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)]
    assert llamadas["cerrar"] == []  # ya pertenece al descriptor; no hay doble cierre


@pytest.mark.parametrize("cierre_falla", [False, True])
def test_conversion_fallida_cierra_el_handle_y_conserva_el_error_original(tmp_path, monkeypatch, cierre_falla):
    original = OSError(errno.EMFILE, "sin descriptores")

    def convertir(*_):
        raise original

    def cerrar(_):
        if cierre_falla:
            raise OSError(errno.EIO, "fallo secundario de cierre")

    llamadas, handle = _api(monkeypatch, convertir=convertir, cerrar=cerrar)
    with pytest.raises(OSError) as capturado:
        ofs._descriptor_lectura_windows(tmp_path / "registro.json", os.O_RDONLY)
    assert capturado.value is original
    assert llamadas["cerrar"] == [handle]


@pytest.mark.parametrize("codigo", [2, 3, 5, 32, 33, 87])
def test_createfile_fallido_preserva_winerror_sin_convertir_ni_cerrar_handle_invalido(tmp_path, monkeypatch, codigo):
    llamadas, _ = _api(monkeypatch, crear=lambda *_: ctypes.c_void_p(-1).value, codigo_error=codigo)
    with pytest.raises(OSError) as capturado:
        ofs._descriptor_lectura_windows(tmp_path / "registro.json", os.O_RDONLY)
    assert capturado.value.winerror == codigo
    assert isinstance(capturado.value, FileNotFoundError) == (codigo in {2, 3})
    assert llamadas["convertir"] == [] and llamadas["cerrar"] == []


@pytest.mark.parametrize("contenido,esperado", [
    ('{"id":"' + ID + '","mensaje":"señal"}\r\n', "señal"),
    ("{json incompleto", "ilegible"),
    (b"\xff", "ilegible"),
])
def test_flujo_windows_cierra_descriptor_real_al_leer_o_fallar_json_y_utf8(tmp_path, monkeypatch, contenido, esperado):
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    ruta.parent.mkdir()
    ruta.write_bytes(contenido.encode("utf-8") if isinstance(contenido, str) else contenido)
    descriptores = []

    def convertir(*_):
        descriptor = os.open(ruta, os.O_RDONLY | os.O_BINARY)
        descriptores.append(descriptor)
        return descriptor

    llamadas, _ = _api(monkeypatch, convertir=convertir)
    monkeypatch.setattr(ofs, "_WINDOWS", True)
    respuesta = ofs.RegistroEjecucionesArchivo(tmp_path).obtener(ID)
    assert respuesta.get("estado", respuesta.get("mensaje")) == esperado
    assert len(descriptores) == 1 and llamadas["cerrar"] == []
    with pytest.raises(OSError) as capturado:
        os.fstat(descriptores[0])
    assert capturado.value.errno == errno.EBADF
    assert ruta.read_bytes() == (contenido.encode("utf-8") if isinstance(contenido, str) else contenido)


@pytest.mark.parametrize("codigo,esperado,reintentos", [(2, None, 0), (32, "exito", 1), (87, "ilegible", 0)])
def test_error_nativo_de_apertura_conserva_contrato_del_registro(tmp_path, monkeypatch, codigo, esperado, reintentos):
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    ruta.parent.mkdir()
    ruta.write_text('{"id":"' + ID + '","estado":"exito"}', encoding="utf-8")
    intentos = []
    descriptores = []
    invalid = ctypes.c_void_p(-1).value

    def crear(*_):
        intentos.append(None)
        return invalid if len(intentos) == 1 or codigo != 32 else (1 << 42) + 123

    def convertir(*_):
        descriptor = os.open(ruta, os.O_RDONLY | os.O_BINARY)
        descriptores.append(descriptor)
        return descriptor

    _api(monkeypatch, crear=crear, convertir=convertir, codigo_error=codigo)
    monkeypatch.setattr(ofs, "_WINDOWS", True)
    esperas = []
    registro = ofs.RegistroEjecucionesArchivo(tmp_path, espera=esperas.append)
    respuesta = registro.obtener(ID)
    assert (None if respuesta is None else respuesta["estado"]) == esperado
    assert registro.reintentos == reintentos and len(esperas) == reintentos
    assert len(intentos) == reintentos + 1
    for descriptor in descriptores:
        with pytest.raises(OSError) as capturado:
            os.fstat(descriptor)
        assert capturado.value.errno == errno.EBADF


def test_enlace_ctypes_usa_handle_del_ancho_del_puntero_y_last_error(monkeypatch):
    """Ejecuta las declaraciones reales del bloque Win32 con DLL doble.

    Permite revisar el ABI tambien en Linux sin fingir una ejecucion nativa ni
    cambiar os.name, cargar kernel32 o contaminar la otra rama de los cerrojos.
    """
    crear, cerrar = SimpleNamespace(), SimpleNamespace()
    cargas = []

    def cargar(nombre, **kwargs):
        cargas.append((nombre, kwargs))
        return SimpleNamespace(CreateFileW=crear, CloseHandle=cerrar)

    ctypes_doble = SimpleNamespace(WinDLL=cargar, wintypes=wintypes, c_void_p=ctypes.c_void_p)
    arbol = ast.parse(Path(ofs.__file__).read_text(encoding="utf-8"))
    bloque = next(n for n in arbol.body if isinstance(n, ast.If) and
                  isinstance(n.test, ast.Name) and n.test.id == "_WINDOWS")
    declaraciones = ast.Module(body=bloque.body, type_ignores=[])
    contexto = {"errno": errno}
    with monkeypatch.context() as cambios:
        cambios.setitem(sys.modules, "ctypes", ctypes_doble)
        cambios.setitem(sys.modules, "msvcrt", SimpleNamespace())
        exec(compile(declaraciones, ofs.__file__, "exec"), contexto)
    assert cargas == [("kernel32", {"use_last_error": True})]
    assert crear.restype is wintypes.HANDLE
    assert crear.argtypes == (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    assert ctypes.sizeof(crear.restype) == ctypes.sizeof(ctypes.c_void_p)
    assert cerrar.argtypes == (wintypes.HANDLE,) and cerrar.restype is wintypes.BOOL
    assert contexto["_HANDLE_INVALIDO"] == ctypes.c_void_p(-1).value
