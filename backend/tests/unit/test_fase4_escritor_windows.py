"""Contrato del escritor Win32 y una publicacion real con lector retenido.

Los dobles comprueban el enlace, los bytes y los recursos; no ejecutan el
kernel Windows ni certifican su ABI. El ultimo caso usa el registro y lector
reales: su rama Windows debe superar el control retenido con la API nueva;
la misma prueba en POSIX solo acredita la semantica POSIX, sin omisiones.
"""
from __future__ import annotations

import ast
import ctypes
import errno
import json
import os
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from app.infrastructure.storage import operacion_file_store as ofs
from app.infrastructure.storage import publicacion_windows as pw


ID = "20261013T135713Z-dc2deb60"
RUTA_WIN = "C:\\sintetico\\señal-😀.json"


def _error_windows(codigo):
    error = OSError(errno.EACCES if codigo in {5, 32, 33} else errno.EINVAL,
                    "fallo Win32 sintetico")
    error.winerror = codigo
    return error


def _doble_api(monkeypatch, *, codigo=32, abrir_falla=False, renombrar_falla=False,
               cerrar_falla=False, cerrar_devuelve_cero=False, al_abrir=None, al_renombrar=None):
    """Doble portable: no cambia os.name ni carga DLL, y nunca abre un lector."""
    handle = (1 << 42) + 123 if ctypes.sizeof(ctypes.c_void_p) == 8 else 123
    estado = {"traza": [], "crear": [], "renombrar": [], "cerrar": [],
              "codigo": codigo, "errores": [], "handle": handle}

    def crear(*args):
        estado["traza"].append("CreateFileW")
        estado["crear"].append(args)
        if al_abrir is not None:
            al_abrir(*args)
        return pw._HANDLE_INVALIDO if abrir_falla else handle

    def renombrar(*args):
        estado["traza"].append("SetFileInformationByHandle")
        estado["codigo"] = codigo
        h, clase, buffer, longitud = args
        estado["renombrar"].append((h, clase, bytes(buffer), longitud))
        if al_renombrar is not None:
            return al_renombrar(*args)
        return 0 if renombrar_falla else 1

    def ultimo_error():
        estado["traza"].append("GetLastError")
        return estado["codigo"]

    def winerror(valor):
        error = _error_windows(valor)
        estado["errores"].append(error)
        return error

    def cerrar(valor):
        estado["traza"].append("CloseHandle")
        estado["cerrar"].append(valor)
        estado["codigo"] = 6  # un cierre no debe destruir el error del renombrado
        if cerrar_falla:
            raise OSError(errno.EIO, "fallo secundario sintetico al cerrar")
        return 0 if cerrar_devuelve_cero else 1

    monkeypatch.setattr(pw, "_WINDOWS", True)
    monkeypatch.setattr(pw, "_crear_archivo_windows", crear, raising=False)
    monkeypatch.setattr(pw, "_renombrar_windows", renombrar, raising=False)
    monkeypatch.setattr(pw, "_ultimo_error_windows", ultimo_error, raising=False)
    monkeypatch.setattr(pw, "_winerror", winerror, raising=False)
    monkeypatch.setattr(pw, "_cerrar_handle_windows", cerrar, raising=False)
    # Aislar tambien el estado de diagnostico: las incidencias del doble nunca
    # deben contaminar la evidencia nativa de la prueba real de este modulo.
    monkeypatch.setattr(pw, "_estado_cierre", SimpleNamespace(incidencia=None))
    monkeypatch.setattr(pw, "_ruta_volumen_windows", lambda *_: 0, raising=False)
    monkeypatch.setattr(pw, "_ruta_destino_absoluta", lambda _: RUTA_WIN)
    return estado


def _prohibir_replace(monkeypatch):
    def prohibido(*_):
        pytest.fail("La rama Windows no puede degradarse a os.replace/MoveFileExW")
    monkeypatch.setattr(pw.os, "replace", prohibido)


@pytest.mark.parametrize("ruta", [
    "C:\\registro\\señal-😀.json",
    "\\\\servidor\\recurso\\señal-😀.json",
    "\\\\?\\C:\\registro\\señal-😀.json",
    "\\\\?\\UNC\\servidor\\recurso\\señal-😀.json",
])
def test_buffer_tiene_flags_sdk_offsets_y_longitud_utf16_sin_incluir_nul(ruta):
    """Offsets de SDK y unidades de dos bytes; c_wchar POSIX no es WCHAR."""
    puntero = ctypes.sizeof(ctypes.c_void_p)
    root, longitud, nombre, minimo = {4: (4, 8, 12, 16), 8: (8, 16, 20, 24)}[puntero]
    buffer = pw._buffer_renombrado(ruta)
    datos = bytes(buffer)
    texto = ruta.encode("utf-16-le")
    assert struct.unpack_from("<I", datos, 0)[0] == 3
    assert datos[root:root + puntero] == b"\0" * puntero
    assert struct.unpack_from("<I", datos, longitud)[0] == len(texto)
    assert len(texto) != len(ruta) * 2  # el emoji necesita un par sustituto
    assert datos[nombre:nombre + len(texto)] == texto
    assert datos[nombre + len(texto):nombre + len(texto) + 2] == b"\0\0"
    assert len(buffer) >= max(minimo, nombre + len(texto) + 2)
    assert datos[nombre:nombre + len(texto)].decode("utf-16-le") == ruta


def test_modelo_ctypes_usa_anchuras_windows_y_abi_nativa_solo_se_acredita_en_windows():
    diseno = pw.diseno_abi()
    puntero = ctypes.sizeof(ctypes.c_void_p)
    root, longitud, nombre, tamano, alineacion = {
        4: (4, 8, 12, 16, 4), 8: (8, 16, 20, 24, 8),
    }[puntero]
    assert diseno["puntero_bytes"] == puntero
    assert diseno["DWORD_bytes"] == 4 and diseno["WCHAR_bytes"] == 2
    assert diseno["union_bytes"] == 4
    assert (diseno["RootDirectory_offset"], diseno["FileNameLength_offset"],
            diseno["FileName_offset"], diseno["sizeof"], diseno["alineacion"]) == (
                root, longitud, nombre, tamano, alineacion)
    assert diseno["nativo_windows"] == (os.name == "nt")
    if os.name == "nt":
        pw._validar_abi_nativa()  # ABI real del proceso Windows que ejecuta el focal
        assert ctypes.sizeof(ctypes.c_wchar) == 2
    else:
        assert pw.diagnostico(Path("."))["volumen"]["estado"] == "no_es_windows_modelo_portable"


def test_declaraciones_reales_enlazan_windll_last_error_y_handle_del_ancho_del_puntero():
    """Ejecuta declaraciones con DLL doble: no equivale a cargar kernel32."""
    nombres = ("CreateFileW", "CloseHandle", "SetFileInformationByHandle",
               "GetVolumePathNameW", "GetVolumeInformationW")
    funciones = {nombre: SimpleNamespace() for nombre in nombres}
    traza = []

    def cargar(nombre, **opciones):
        traza.append((nombre, opciones))
        return SimpleNamespace(**funciones)

    get_error = lambda: 32
    constructor_error = _error_windows
    ctypes_doble = SimpleNamespace(**{nombre: getattr(ctypes, nombre) for nombre in (
        "c_wchar_p", "c_void_p", "c_int32", "POINTER")}, WinDLL=cargar,
        get_last_error=get_error, WinError=constructor_error)
    contexto = dict(vars(pw))
    contexto["ctypes"] = ctypes_doble
    contexto["_validar_abi_nativa"] = lambda: traza.append("validar_abi")
    arbol = ast.parse(Path(pw.__file__).read_text(encoding="utf-8"))
    bloque = next(n for n in arbol.body if isinstance(n, ast.If) and
                  isinstance(n.test, ast.Name) and n.test.id == "_WINDOWS")
    exec(compile(ast.Module(body=bloque.body, type_ignores=[]), pw.__file__, "exec"), contexto)
    assert traza == ["validar_abi", ("kernel32", {"use_last_error": True})]
    crear = funciones["CreateFileW"]
    assert crear.argtypes == (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                             ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
    assert crear.restype is ctypes.c_void_p
    assert ctypes.sizeof(crear.restype) == ctypes.sizeof(ctypes.c_void_p)
    renombrar = funciones["SetFileInformationByHandle"]
    assert renombrar.argtypes == (ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32)
    assert renombrar.restype is ctypes.c_int32
    assert funciones["CloseHandle"].argtypes == (ctypes.c_void_p,)
    assert funciones["CloseHandle"].restype is ctypes.c_int32
    assert contexto["_ultimo_error_windows"] is get_error
    assert contexto["_winerror"] is constructor_error


def test_api_publica_con_delete_share_all_clase_win32_22_y_cierra_su_handle(monkeypatch):
    estado = _doble_api(monkeypatch)
    _prohibir_replace(monkeypatch)
    origen = Path("temporal-propio.tmp")
    pw.publicar(origen, Path("definitivo.json"))
    assert estado["crear"] == [(str(origen), 0x10000, 7, None, 3, 0x80, None)]
    h, clase, datos, longitud = estado["renombrar"][0]
    assert h == estado["handle"] and clase == 22 and longitud == len(datos)
    assert struct.unpack_from("<I", datos)[0] == 3
    assert estado["cerrar"] == [h]
    assert estado["traza"] == ["CreateFileW", "SetFileInformationByHandle", "CloseHandle"]
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert h > 0xFFFFFFFF  # se descubre una conversion truncada a DWORD


@pytest.mark.parametrize("codigo", [1, 50, 120])
def test_capacidad_no_disponible_es_explicita_y_nunca_degrada(monkeypatch, codigo):
    estado = _doble_api(monkeypatch, codigo=codigo, renombrar_falla=True)
    _prohibir_replace(monkeypatch)
    with pytest.raises(pw.PublicacionAtomicaNoDisponibleError) as capturado:
        pw.publicar(Path("temporal.tmp"), Path("definitivo.json"))
    error = capturado.value
    assert error.errno == errno.ENOTSUP and error.winerror == codigo
    assert error.__cause__ is estado["errores"][0]
    assert "sin degradacion" in str(error) and "FileRenameInfoEx" in str(error)
    assert estado["traza"] == ["CreateFileW", "SetFileInformationByHandle", "GetLastError", "CloseHandle"]
    assert estado["cerrar"] == [estado["handle"]]


@pytest.mark.parametrize("cerrar_falla", [False, True])
@pytest.mark.parametrize("codigo", [5, 32, 33, 87, 24, 122])
def test_error_de_renombrado_preserva_winerror_antes_del_cierre_y_error_primario(monkeypatch, codigo, cerrar_falla):
    estado = _doble_api(monkeypatch, codigo=codigo, renombrar_falla=True, cerrar_falla=cerrar_falla)
    _prohibir_replace(monkeypatch)
    with pytest.raises(OSError) as capturado:
        pw.publicar(Path("temporal.tmp"), Path("definitivo.json"))
    error = capturado.value
    assert error is estado["errores"][0] and error.winerror == codigo
    assert not isinstance(error, pw.PublicacionAtomicaNoDisponibleError)
    notas = " ".join(error.__notes__)
    assert "clase 22" in notas and "flags 3" in notas and "buffer " in notas
    if codigo == 87:
        assert "parametros" in notas and "no demuestra por si solo" in notas
    assert estado["traza"] == ["CreateFileW", "SetFileInformationByHandle", "GetLastError", "CloseHandle"]
    assert estado["cerrar"] == [estado["handle"]] and estado["codigo"] == 6


@pytest.mark.parametrize("codigo", [5, 32, 87])
def test_apertura_fallida_preserva_winerror_sin_renombrar_ni_cerrar_handle_invalido(monkeypatch, codigo):
    estado = _doble_api(monkeypatch, codigo=codigo, abrir_falla=True)
    _prohibir_replace(monkeypatch)
    with pytest.raises(OSError) as capturado:
        pw.publicar(Path("temporal.tmp"), Path("definitivo.json"))
    assert capturado.value is estado["errores"][0] and capturado.value.winerror == codigo
    assert estado["traza"] == ["CreateFileW", "GetLastError"]
    assert estado["renombrar"] == [] and estado["cerrar"] == []


@pytest.mark.parametrize("renombrar_falla", [False, True])
def test_closehandle_bool_falso_es_visible_y_no_repite_una_publicacion_confirmada(monkeypatch, caplog, renombrar_falla):
    estado = _doble_api(monkeypatch, codigo=32, renombrar_falla=renombrar_falla,
                        cerrar_devuelve_cero=True)
    _prohibir_replace(monkeypatch)
    if renombrar_falla:
        with pytest.raises(OSError) as capturado:
            pw.publicar(Path("temporal.tmp"), Path("definitivo.json"))
        assert capturado.value is estado["errores"][0]
        assert capturado.value.winerror == 32  # el CloseHandle falla luego con 6
        assert any("Fallo secundario de cierre" in nota for nota in capturado.value.__notes__)
    else:
        pw.publicar(Path("temporal.tmp"), Path("definitivo.json"))
    diagnostico = pw.diagnostico(Path("sintetico"))
    incidencia = diagnostico["incidencia_cierre"]
    assert incidencia["api"] == "CloseHandle" and incidencia["winerror"] == 6
    assert incidencia["publicacion_confirmada"] is (not renombrar_falla)
    assert "Fallo de cierre del HANDLE propio" in caplog.text
    assert estado["cerrar"] == [estado["handle"]] and len(estado["renombrar"]) == 1
    esperado = ["CreateFileW", "SetFileInformationByHandle"]
    if renombrar_falla:
        esperado.append("GetLastError")
    esperado += ["CloseHandle", "GetLastError"]
    # diagnostico consulta tambien el volumen doble, sin abrir archivos/handles.
    assert estado["traza"] == esperado + ["GetLastError"]


def test_publicacion_exitosa_posterior_no_oculta_incidente_de_cierre_anterior(monkeypatch):
    _doble_api(monkeypatch, cerrar_devuelve_cero=True)
    pw.publicar(Path("temporal-1.tmp"), Path("definitivo.json"))
    pw.publicar(Path("temporal-2.tmp"), Path("definitivo.json"))
    incidencia = dict(pw.diagnostico(Path("sintetico"))["incidencia_cierre"])
    assert incidencia["total"] == 2 and incidencia["publicacion_confirmada"] is True
    monkeypatch.setattr(pw, "_cerrar_handle_windows", lambda _: 1)
    pw.publicar(Path("temporal.tmp"), Path("definitivo.json"))
    assert pw.diagnostico(Path("sintetico"))["incidencia_cierre"] == incidencia


@pytest.mark.parametrize("ruta", ["relativo.json", "\\sin-unidad.json", "C:relativo.json", "C:\\con\0nul.json"])
def test_ruta_invalida_es_error_de_construccion_antes_de_toda_llamada_win32(monkeypatch, ruta):
    estado = _doble_api(monkeypatch)
    monkeypatch.setattr(pw, "_ruta_destino_absoluta", lambda _: ruta)
    _prohibir_replace(monkeypatch)
    with pytest.raises(ValueError):
        pw.publicar(Path("temporal.tmp"), Path("definitivo.json"))
    assert estado["traza"] == []


def test_fallo_al_reservar_buffer_no_abre_handles_ni_se_confunde_con_capacidad(monkeypatch):
    estado = _doble_api(monkeypatch)
    original = MemoryError("reserva sintetica imposible")

    def fallar(*_):
        raise original

    monkeypatch.setattr(pw.ctypes, "create_string_buffer", fallar)
    with pytest.raises(MemoryError) as capturado:
        pw.publicar(Path("temporal.tmp"), Path("definitivo.json"))
    assert capturado.value is original and estado["traza"] == []


@pytest.mark.parametrize("cierre_bool_falso", [False, True])
def test_guardar_elige_api_nueva_con_temporal_completo_sincronizado_y_cerrado(tmp_path, monkeypatch, caplog, cierre_bool_falso):
    """La operacion de nombres del doble es explicita, no evidencia Windows."""
    registro = ofs.RegistroEjecucionesArchivo(tmp_path)
    real_replace, real_open, real_fsync = os.replace, open, os.fsync
    flujos, fsyncs, origenes = [], [], []
    esperado = {"id": ID, "n": 1, "mensaje": "señal-😀"}

    def observar_apertura(*args, **kwargs):
        flujo = real_open(*args, **kwargs)
        flujos.append(flujo)
        return flujo

    def observar_fsync(descriptor):
        os.fstat(descriptor)
        fsyncs.append(descriptor)
        return real_fsync(descriptor)

    def al_abrir(origen, *_):
        assert len(flujos) == 1 and flujos[0].closed and len(fsyncs) == 1
        assert json.loads(Path(origen).read_text(encoding="utf-8")) == esperado
        origenes.append(Path(origen))

    def al_renombrar(*_):
        # Simula un kernel exitoso; la prueba real retenida de abajo no usa doble.
        real_replace(origenes[-1], tmp_path / "ejecuciones" / f"{ID}.json")
        return 1

    estado = _doble_api(monkeypatch, al_abrir=al_abrir, al_renombrar=al_renombrar,
                        cerrar_devuelve_cero=cierre_bool_falso)
    monkeypatch.setattr(ofs, "_WINDOWS", True)
    monkeypatch.setattr(ofs, "open", observar_apertura, raising=False)
    monkeypatch.setattr(ofs.os, "fsync", observar_fsync)
    _prohibir_replace(monkeypatch)
    registro.guardar(esperado)
    assert json.loads((tmp_path / "ejecuciones" / f"{ID}.json").read_text(encoding="utf-8")) == esperado
    assert len(estado["renombrar"]) == 1 and estado["cerrar"] == [estado["handle"]]
    assert len(estado["crear"]) == 1 and registro.reintentos == 0
    if cierre_bool_falso:
        assert pw.diagnostico(tmp_path)["incidencia_cierre"]["publicacion_confirmada"] is True
        assert "Fallo de cierre del HANDLE propio" in caplog.text
    assert list((tmp_path / "ejecuciones").glob("*.tmp")) == []


def test_construccion_invalida_al_guardar_no_abre_handle_y_cierra_temporal_sin_tocar_anteriores(tmp_path, monkeypatch):
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    ruta.parent.mkdir()
    ruta.write_bytes(b'{"n":0}\n')
    ajeno = ruta.parent / f".{ID}.deadcafe.tmp"
    ajeno.write_bytes(b"temporal ajeno\x00\xff")
    antes = {p.name: p.read_bytes() for p in ruta.parent.iterdir()}
    estado = _doble_api(monkeypatch)
    monkeypatch.setattr(pw, "_ruta_destino_absoluta", lambda _: "C:relativo.json")
    monkeypatch.setattr(ofs, "_WINDOWS", True)
    real_open, flujos = open, []

    def observar_apertura(*args, **kwargs):
        flujo = real_open(*args, **kwargs)
        flujos.append(flujo)
        return flujo

    monkeypatch.setattr(ofs, "open", observar_apertura, raising=False)
    registro = ofs.RegistroEjecucionesArchivo(tmp_path, espera=lambda _: pytest.fail("no es un bloqueo"))
    with pytest.raises(ValueError):
        registro.guardar({"id": ID, "n": 1})
    assert len(flujos) == 1 and flujos[0].closed
    assert estado["traza"] == [] and registro.reintentos == 0
    assert {p.name: p.read_bytes() for p in ruta.parent.iterdir()} == antes


@pytest.mark.parametrize("etapa,codigo", [("abrir", 5), ("abrir", 32), ("renombrar", 5),
                                            ("renombrar", 32), ("renombrar", 87),
                                            ("renombrar", 50)])
def test_guardar_rama_windows_fallida_conserva_json_y_solo_limpia_temporal_propio(tmp_path, monkeypatch, etapa, codigo):
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    ruta.parent.mkdir()
    antes = ('{ "id": "' + ID + '", "n": 0, "mensaje": "señal anterior" }\n').encode("utf-8")
    ruta.write_bytes(antes)
    ajeno = ruta.parent / f".{ID}.deadcafe.tmp"
    ajeno.write_bytes(b"temporal anterior ajeno\x00\xff")
    otro = ruta.parent / "otro.json"
    otro.write_bytes(b"registro ajeno")
    original = {p.name: p.read_bytes() for p in ruta.parent.iterdir()}
    estado = _doble_api(monkeypatch, codigo=codigo,
                        abrir_falla=etapa == "abrir", renombrar_falla=etapa == "renombrar")
    monkeypatch.setattr(ofs, "_WINDOWS", True)
    _prohibir_replace(monkeypatch)
    ahora = [0.0]
    esperas = []

    def esperar(segundos):
        esperas.append(segundos)
        ahora[0] += segundos

    registro = ofs.RegistroEjecucionesArchivo(tmp_path, espera=esperar, reloj=lambda: ahora[0])
    transitorio = codigo in {5, 32}
    with pytest.raises(ofs.ReemplazoBloqueadoError if transitorio else OSError) as capturado:
        registro.guardar({"id": ID, "n": 1})
    if transitorio:
        assert capturado.value.__cause__.winerror == codigo
        assert 0 < sum(esperas) <= ofs.LIMITE_DE_REEMPLAZO
        assert len(estado["crear"]) == registro.reintentos + 1 > 1
    else:
        assert capturado.value.winerror == codigo
        assert len(estado["crear"]) == 1 and esperas == [] and registro.reintentos == 0
        assert isinstance(capturado.value, pw.PublicacionAtomicaNoDisponibleError) == (codigo == 50)
    assert {p.name: p.read_bytes() for p in ruta.parent.iterdir()} == original
    assert len(estado["cerrar"]) == (0 if etapa == "abrir" else len(estado["crear"]))


def test_guardar_error_primario_y_cierre_fallido_no_adquiere_mas_handles(tmp_path, monkeypatch):
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    ruta.parent.mkdir()
    antes = b'{"n":0}\n'
    ruta.write_bytes(antes)
    estado = _doble_api(monkeypatch, codigo=32, renombrar_falla=True, cerrar_devuelve_cero=True)
    monkeypatch.setattr(ofs, "_WINDOWS", True)
    _prohibir_replace(monkeypatch)
    registro = ofs.RegistroEjecucionesArchivo(tmp_path, espera=lambda _: pytest.fail("no adquirir mas handles"))
    with pytest.raises(OSError) as capturado:
        registro.guardar({"id": ID, "n": 1})
    assert capturado.value is estado["errores"][0] and capturado.value.winerror == 32
    assert capturado.value.incidencia_cierre["winerror"] == 6
    assert capturado.value.incidencia_cierre["publicacion_confirmada"] is False
    assert len(estado["crear"]) == len(estado["renombrar"]) == len(estado["cerrar"]) == 1
    assert registro.reintentos == 0 and ruta.read_bytes() == antes
    assert sorted(p.name for p in ruta.parent.iterdir()) == [ruta.name]


def test_publicacion_real_unicode_con_lector_cooperante_retenido_ve_objetos_distintos(tmp_path):
    """En Windows llama al kernel real; el verde POSIX no certifica Windows."""
    carpeta = tmp_path / "señal-😀"
    carpeta.mkdir()
    registro = ofs.RegistroEjecucionesArchivo(carpeta)
    ruta = carpeta / "ejecuciones" / f"{ID}.json"
    datos = {"nativo_windows": os.name == "nt", "ruta_unicode_bmp_y_no_bmp": True,
             "error": None, "nuevo": None, "retenido": None, "descriptor_cerrado": False}
    primario = None
    try:
        registro.guardar({"id": ID, "n": 0, "mensaje": "anterior-ñ"})
        assert ofs.diagnostico_publicacion(carpeta).get("incidencia_cierre") is None
        with ofs._abrir_lectura_registro(ruta) as retenido:
            descriptor = retenido.fileno()
            assert json.load(retenido)["n"] == 0
            registro.guardar({"id": ID, "n": 1, "mensaje": "nuevo-😀"})
            assert not retenido.closed  # no cerrar el lector para conseguir publicar
            assert registro.obtener(ID) == {"id": ID, "n": 1, "mensaje": "nuevo-😀"}
            datos["nuevo"] = 1
            retenido.seek(0)
            assert json.load(retenido) == {"id": ID, "n": 0, "mensaje": "anterior-ñ"}
            datos["retenido"] = 0
        with pytest.raises(OSError) as cerrado:
            os.fstat(descriptor)
        assert cerrado.value.errno == errno.EBADF
        datos["descriptor_cerrado"] = True
        assert list(ruta.parent.glob("*.tmp")) == []
        soporte = ofs.diagnostico_publicacion(carpeta)
        assert soporte.get("incidencia_cierre") is None
        if os.name == "nt":
            assert soporte["api"] == "SetFileInformationByHandle(FileRenameInfoEx)"
            assert soporte["clase"] == 22 and soporte["flags"] == 3
            assert soporte["abi"]["nativo_windows"] is True and soporte["fallback"] is False
        else:
            assert soporte["api"] == "os.replace (POSIX)"
            assert soporte["volumen"]["estado"] == "semantica_POSIX; no valida Windows"
    except BaseException as error:
        primario = error
        datos["error"] = repr(error)
        raise
    finally:
        # Registrar API/volumen tambien si el primer guardar falla. Solo son
        # metadatos de tmp_path y datos sinteticos, sin almacenes del operador.
        try:
            datos["soporte"] = ofs.diagnostico_publicacion(carpeta)
        except Exception as error_diagnostico:
            datos["soporte"] = {"error_diagnostico": repr(error_diagnostico)}
        evidencia = os.environ.get("FASE4_EVIDENCIA")
        if evidencia:
            try:
                Path(evidencia).mkdir(parents=True, exist_ok=True)
                (Path(evidencia) / "soporte_publicacion_unicode_retenido_real.json").write_text(
                    json.dumps(datos, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            except OSError as error_evidencia:
                if primario is None:
                    raise
                primario.add_note(f"No se pudo guardar evidencia sintetica: {error_evidencia!r}")
