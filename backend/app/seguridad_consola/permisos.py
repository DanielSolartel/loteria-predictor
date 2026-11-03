"""Permisos del almacén privado de la consola (Fase 10, E10.1 v2, hallazgo E101-SEC-01).

Se comprueban **al crear y en cada apertura**, para el archivo y para su directorio. Si no se pueden leer
o interpretar, el acceso se cierra (`ErrorPermisos(verificable=False)`); nunca se supone que son correctos.

Política de principales aceptados
---------------------------------
- POSIX: propietario = usuario efectivo del proceso; ningún permiso para grupo ni otros (`mode & 0o077 == 0`);
  el archivo es regular y el directorio es un directorio (no se aceptan enlaces simbólicos).
- Windows (descriptor leído con `GetNamedSecurityInfoW`, sin interpretar texto de `icacls`):
  - propietario = SID del usuario del proceso (no el grupo Administradores ni otro);
  - DACL presente y no nula (una DACL nula o ausente concede todo a todos);
  - cada ACE de concesión (`ACCESS_ALLOWED`) solo para el usuario del proceso o `LocalSystem` (S-1-5-18);
    `LocalSystem` se admite porque el sistema operativo ya tiene acceso total a los archivos locales y
    herramientas del propio sistema (p. ej. copias de sombra) lo usan. No se admiten Administradores,
    Usuarios, Usuarios autenticados, Todos, CREATOR OWNER ni ningún otro SID, tampoco heredado ni
    `INHERIT_ONLY` (afectaría a los archivos que SQLite crea en el directorio);
  - las ACE de denegación (`ACCESS_DENIED`) solo restringen y se aceptan;
  - cualquier otro tipo de ACE (objeto, callback, etc.) no se interpreta y cierra el acceso;
  - el usuario del proceso debe tener al menos una concesión efectiva.
- Al crear, solo se fijan permisos en lo que crea el propio proceso (directorio nuevo y archivo nuevo):
  propietario = usuario y DACL protegida (sin herencia) con una única concesión al usuario. Un directorio
  que ya existía **no se modifica**: si no cumple la política, la creación se rechaza.
"""
from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

SID_SISTEMA = "S-1-5-18"
ACCESS_ALLOWED_ACE_TYPE = 0x0
ACCESS_DENIED_ACE_TYPE = 0x1
INHERIT_ONLY_ACE = 0x08
_SID = re.compile(r"S-1-[0-9]+(-[0-9]+)+")


class ErrorPermisos(Exception):
    """Permisos no admitidos (`verificable=True`) o imposibles de verificar (`verificable=False`)."""

    def __init__(self, motivo: str, *, verificable: bool = True):
        super().__init__(motivo)
        self.motivo, self.verificable = motivo, verificable


@dataclass(frozen=True)
class Ace:
    tipo: int
    banderas: int
    mascara: int
    sid: str | None


@dataclass(frozen=True)
class DescriptorWindows:
    propietario: str | None
    dacl_presente: bool  # False: DACL ausente o nula
    aces: tuple[Ace, ...]


def es_windows() -> bool:
    return os.name == "nt"


# ---------------------------------------------------------------------------- política (pura, probada en Linux)
def evaluar_descriptor(descriptor: DescriptorWindows, usuario: str | None) -> str | None:
    """None si el descriptor cumple la política; si no, un motivo estable (sin rutas ni SID)."""
    if not isinstance(usuario, str) or not _SID.fullmatch(usuario):
        return "usuario_no_determinado"
    if descriptor.propietario != usuario:
        return "propietario_no_admitido"
    if not descriptor.dacl_presente:
        return "dacl_nula"
    concede_al_usuario = False
    for ace in descriptor.aces:
        if ace.tipo == ACCESS_DENIED_ACE_TYPE:
            continue
        if ace.tipo != ACCESS_ALLOWED_ACE_TYPE or not isinstance(ace.sid, str) or not _SID.fullmatch(ace.sid):
            return "ace_no_interpretable"
        if ace.sid == usuario:
            concede_al_usuario = concede_al_usuario or (not ace.banderas & INHERIT_ONLY_ACE and ace.mascara != 0)
        elif ace.sid != SID_SISTEMA:
            return "principal_no_admitido"
    return None if concede_al_usuario else "sin_acceso_del_propietario"


def motivo_posix(ruta: Path, *, directorio: bool) -> str | None:
    st = os.lstat(ruta)
    if stat.S_ISLNK(st.st_mode):
        return "enlace_simbolico"
    if directorio != stat.S_ISDIR(st.st_mode) or (not directorio and not stat.S_ISREG(st.st_mode)):
        return "tipo_no_admitido"
    if hasattr(os, "geteuid") and st.st_uid != os.geteuid():
        return "propietario_no_admitido"
    if st.st_mode & 0o077:
        return "permisos_amplios"
    return None


# ---------------------------------------------------------------------------- operaciones
def verificar(ruta: Path, *, directorio: bool) -> None:
    """Lanza `ErrorPermisos` si `ruta` no cumple la política o no se puede verificar."""
    if not es_windows():
        try:
            motivo = motivo_posix(Path(ruta), directorio=directorio)
        except OSError as error:
            raise ErrorPermisos("lectura_fallida", verificable=False) from error
    else:
        try:
            usuario = sid_actual()
            descriptor = leer_descriptor(Path(ruta))
        except (OSError, ValueError, AttributeError) as error:
            raise ErrorPermisos("lectura_fallida", verificable=False) from error
        motivo = evaluar_descriptor(descriptor, usuario)
        if motivo in ("usuario_no_determinado", "ace_no_interpretable"):
            raise ErrorPermisos(motivo, verificable=False)
    if motivo is not None:
        raise ErrorPermisos(motivo)


def restringir(ruta: Path, *, directorio: bool) -> None:
    """Solo para lo que acaba de crear este proceso: propietario y acceso exclusivo del usuario. Después
    verifica el resultado (una aplicación incompleta no se da por buena)."""
    if not es_windows():
        os.chmod(ruta, 0o700 if directorio else 0o600)
    else:
        try:
            aplicar_descriptor(Path(ruta), sid_actual(), directorio=directorio)
        except (OSError, ValueError, AttributeError) as error:
            raise ErrorPermisos("aplicacion_fallida", verificable=False) from error
    verificar(ruta, directorio=directorio)


# ---------------------------------------------------------------------------- Windows (ctypes, advapi32)
# Solo se cargan en Windows. No se ejecutan en Linux: su validación es nativa (protocolo Windows).
SE_FILE_OBJECT = 1
OWNER_SECURITY_INFORMATION = 0x1
DACL_SECURITY_INFORMATION = 0x4
PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
TOKEN_QUERY = 0x8
TOKEN_USER_CLASE = 1
ACL_SIZE_INFORMATION_CLASE = 2
SDDL_REVISION_1 = 1


def _api():
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    vp, pvp, dw, b = ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD, wintypes.BOOL
    firmas = {
        (advapi32, "GetNamedSecurityInfoW"): (dw, [wintypes.LPCWSTR, dw, dw, pvp, pvp, pvp, pvp, pvp]),
        (advapi32, "SetNamedSecurityInfoW"): (dw, [wintypes.LPWSTR, dw, dw, vp, vp, vp, vp]),
        (advapi32, "GetSecurityDescriptorDacl"): (b, [vp, ctypes.POINTER(b), pvp, ctypes.POINTER(b)]),
        (advapi32, "GetSecurityDescriptorOwner"): (b, [vp, pvp, ctypes.POINTER(b)]),
        (advapi32, "GetAclInformation"): (b, [vp, vp, dw, dw]),
        (advapi32, "GetAce"): (b, [vp, dw, pvp]),
        (advapi32, "IsValidSid"): (b, [vp]),
        (advapi32, "ConvertSidToStringSidW"): (b, [vp, pvp]),
        (advapi32, "ConvertStringSecurityDescriptorToSecurityDescriptorW"): (b, [wintypes.LPCWSTR, dw, pvp, vp]),
        (advapi32, "OpenProcessToken"): (b, [wintypes.HANDLE, dw, ctypes.POINTER(wintypes.HANDLE)]),
        (advapi32, "GetTokenInformation"): (b, [wintypes.HANDLE, dw, vp, dw, ctypes.POINTER(dw)]),
        (kernel32, "GetCurrentProcess"): (wintypes.HANDLE, []),
        (kernel32, "CloseHandle"): (b, [wintypes.HANDLE]),
        (kernel32, "LocalFree"): (vp, [vp]),
    }
    api = {}
    for (dll, nombre), (resultado, argumentos) in firmas.items():
        funcion = getattr(dll, nombre)
        funcion.restype, funcion.argtypes = resultado, argumentos
        api[nombre] = funcion
    return ctypes, wintypes, api


def _comprobar(ok, contexto: str) -> None:
    if not ok:
        import ctypes
        raise OSError(ctypes.get_last_error(), contexto)


def _sid_texto(ctypes, api, psid) -> str:
    if not psid or not api["IsValidSid"](psid):
        raise ValueError("sid_no_valido")
    salida = ctypes.c_void_p()
    _comprobar(api["ConvertSidToStringSidW"](psid, ctypes.byref(salida)), "ConvertSidToStringSidW")
    try:
        return ctypes.wstring_at(salida.value)
    finally:
        api["LocalFree"](salida)


def sid_actual() -> str:
    """SID del usuario del token del proceso (no del grupo ni de la sesión)."""
    ctypes, wintypes, api = _api()
    token = wintypes.HANDLE()
    _comprobar(api["OpenProcessToken"](api["GetCurrentProcess"](), TOKEN_QUERY, ctypes.byref(token)), "OpenProcessToken")
    try:
        necesario = wintypes.DWORD()
        api["GetTokenInformation"](token, TOKEN_USER_CLASE, None, 0, ctypes.byref(necesario))
        if necesario.value == 0:
            raise OSError(ctypes.get_last_error(), "GetTokenInformation")
        bufer = ctypes.create_string_buffer(necesario.value)
        _comprobar(api["GetTokenInformation"](token, TOKEN_USER_CLASE, bufer, necesario, ctypes.byref(necesario)),
                   "GetTokenInformation")
        psid = ctypes.c_void_p.from_buffer(bufer).value  # TOKEN_USER.User.Sid es el primer campo
        return _sid_texto(ctypes, api, psid)
    finally:
        api["CloseHandle"](token)


def leer_descriptor(ruta: Path) -> DescriptorWindows:
    ctypes, wintypes, api = _api()
    propietario, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    codigo = api["GetNamedSecurityInfoW"](str(ruta), SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
                                          ctypes.byref(propietario), None, ctypes.byref(dacl), None,
                                          ctypes.byref(descriptor))
    if codigo != 0:
        raise OSError(codigo, "GetNamedSecurityInfoW")
    try:
        presente, por_defecto, dacl_sd = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
        _comprobar(api["GetSecurityDescriptorDacl"](descriptor, ctypes.byref(presente), ctypes.byref(dacl_sd),
                                                    ctypes.byref(por_defecto)), "GetSecurityDescriptorDacl")
        sid_propietario = _sid_texto(ctypes, api, propietario.value) if propietario.value else None
        if not presente.value or not dacl_sd.value:
            return DescriptorWindows(sid_propietario, False, ())

        class TamanoAcl(ctypes.Structure):
            _fields_ = [("AceCount", wintypes.DWORD), ("AclBytesInUse", wintypes.DWORD),
                        ("AclBytesFree", wintypes.DWORD)]

        tamano = TamanoAcl()
        _comprobar(api["GetAclInformation"](dacl_sd, ctypes.byref(tamano), ctypes.sizeof(tamano),
                                            ACL_SIZE_INFORMATION_CLASE), "GetAclInformation")
        aces = []
        for indice in range(tamano.AceCount):
            pace = ctypes.c_void_p()
            _comprobar(api["GetAce"](dacl_sd, indice, ctypes.byref(pace)), "GetAce")
            tipo = ctypes.c_ubyte.from_address(pace.value).value
            banderas = ctypes.c_ubyte.from_address(pace.value + 1).value
            if tipo in (ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE):
                mascara = wintypes.DWORD.from_address(pace.value + 4).value
                sid = _sid_texto(ctypes, api, pace.value + 8)
            else:  # otro tipo: no se interpreta (la política lo rechaza)
                mascara, sid = 0, None
            aces.append(Ace(tipo, banderas, mascara, sid))
        return DescriptorWindows(sid_propietario, True, tuple(aces))
    finally:
        api["LocalFree"](descriptor)


def aplicar_descriptor(ruta: Path, usuario: str, *, directorio: bool) -> None:
    """Propietario = usuario y DACL protegida con una única concesión de control total al usuario."""
    if not _SID.fullmatch(usuario or ""):
        raise ValueError("sid_no_valido")
    ctypes, wintypes, api = _api()
    herencia = "OICI" if directorio else ""
    sddl = f"O:{usuario}D:P(A;{herencia};FA;;;{usuario})"
    descriptor = ctypes.c_void_p()
    _comprobar(api["ConvertStringSecurityDescriptorToSecurityDescriptorW"](sddl, SDDL_REVISION_1,
                                                                           ctypes.byref(descriptor), None),
               "ConvertStringSecurityDescriptorToSecurityDescriptorW")
    try:
        propietario, por_defecto = ctypes.c_void_p(), wintypes.BOOL()
        _comprobar(api["GetSecurityDescriptorOwner"](descriptor, ctypes.byref(propietario), ctypes.byref(por_defecto)),
                   "GetSecurityDescriptorOwner")
        presente, dacl = wintypes.BOOL(), ctypes.c_void_p()
        _comprobar(api["GetSecurityDescriptorDacl"](descriptor, ctypes.byref(presente), ctypes.byref(dacl),
                                                    ctypes.byref(por_defecto)), "GetSecurityDescriptorDacl")
        codigo = api["SetNamedSecurityInfoW"](str(ruta), SE_FILE_OBJECT,
                                              OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
                                              | PROTECTED_DACL_SECURITY_INFORMATION,
                                              propietario, None, dacl, None)
        if codigo != 0:
            raise OSError(codigo, "SetNamedSecurityInfoW")
    finally:
        api["LocalFree"](descriptor)
