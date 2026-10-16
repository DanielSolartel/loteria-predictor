"""Fase 4 (v3) - publicacion del progreso en el registro de ejecuciones
compartido (Productos 3 y 5, laboratorio y centro de predicciones).

La v3.2 Windows fallo incluso con lectores que compartian eliminacion:
`os.replace` usa MoveFileExW y ese permiso del lector no resuelve la limitacion
del destino abierto. Estas pruebas interceptan la primitiva comun de publicacion,
por lo que los errores inyectados cubren tambien el escritor nuevo de Windows.
No se identifica un handle concreto a partir de un WinError 5.
La publicacion sigue siendo atomica, sobre un temporal completo con
flush y fsync, pero reintenta de forma acotada SOLO los bloqueos
transitorios; un error permanente se propaga sin esperar.

Las simulaciones son portables. Las pruebas de bloqueo real usan el
sistema de verdad en todas las plataformas, sin omitirse: en Windows exigen
el bloqueo y el reintento (o el fallo inmediato si el destino es de solo
lectura); en POSIX comprueban que alli no hay bloqueo. Lo que pasa en Linux
no se atribuye a Windows."""
from __future__ import annotations

import errno
import json
import os
import platform
import re
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from app.infrastructure.storage import operacion_file_store as ofs
from app.infrastructure.storage.operacion_file_store import RegistroEjecucionesArchivo

ID = "20261013T135713Z-dc2deb60"
WINDOWS = os.name == "nt"


def _medicion(nombre: str, datos: dict) -> None:
    """Si el script de Windows lo pide (variable FASE4_EVIDENCIA con una carpeta), guarda alli las mediciones
    reales de la prueba en JSON. Sin la variable no escribe nada fuera de tmp_path."""
    carpeta = os.environ.get("FASE4_EVIDENCIA")
    if carpeta:
        Path(carpeta).mkdir(parents=True, exist_ok=True)
        (Path(carpeta) / f"{nombre}.json").write_text(json.dumps(datos, sort_keys=True), encoding="utf-8")


def _soporte_publicacion(carpeta: Path) -> dict:
    """Contexto de la API/volumen, sin leer ni alterar un registro de usuario."""
    try:
        return ofs.diagnostico_publicacion(carpeta)
    except Exception as error:
        # La evidencia del entorno tampoco debe ocultar el error del publicador.
        return {"error_diagnostico_publicacion": repr(error)}


@pytest.fixture(autouse=True)
def _guardar_soporte_antes_de_la_prueba(tmp_path, request):
    """Preserva contexto incluso si falla el primer guardar, antes de un finally."""
    if os.environ.get("FASE4_EVIDENCIA"):
        nombre = re.sub(r"[^a-zA-Z0-9_.-]", "_", request.node.name)
        _medicion("soporte_publicacion_" + nombre, _soporte_publicacion(tmp_path))


def _windows(errno_: int, mensaje: str, winerror: int) -> PermissionError:
    """PermissionError con `winerror`, como lo crea Windows (en Linux el atributo se fija a mano)."""
    error = PermissionError(errno_, mensaje, None, winerror)
    if getattr(error, "winerror", None) != winerror:
        error.winerror = winerror
    return error


class _Tiempo:
    """Reloj y espera simulados: nunca duerme de verdad."""

    def __init__(self):
        self.ahora = 0.0
        self.esperas: list[float] = []

    def reloj(self) -> float:
        return self.ahora

    def espera(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.ahora += segundos


def _registro(tmp_path, tiempo: _Tiempo | None = None, **extra) -> RegistroEjecucionesArchivo:
    if tiempo is None:
        return RegistroEjecucionesArchivo(tmp_path, **extra)
    return RegistroEjecucionesArchivo(tmp_path, espera=tiempo.espera, reloj=tiempo.reloj, **extra)


def _temporales(tmp_path) -> list[str]:
    carpeta = tmp_path / "ejecuciones"
    return sorted(p.name for p in carpeta.iterdir() if p.name.endswith(".tmp")) if carpeta.is_dir() else []


def _publicacion_que_falla(monkeypatch, errores: list[BaseException]):
    """Intercepta la publicacion comun, tambien en la rama real de Windows."""
    real = ofs._publicar_temporal
    llamadas = []

    def falso(origen, destino):
        llamadas.append((str(origen), str(destino)))
        if errores:
            raise errores.pop(0)
        return real(origen, destino)

    monkeypatch.setattr(ofs, "_publicar_temporal", falso)
    return llamadas


# ---------------------------------------------------------------------------
# Bloqueos transitorios: reintento acotado (simulacion portable)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_un_bloqueo_transitorio_del_reemplazo_se_reintenta_y_publica(tmp_path, monkeypatch, winerror):
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    registro.guardar({"id": ID, "estado": "en_curso", "fase": "construccion"})
    llamadas = _publicacion_que_falla(monkeypatch, [_windows(13, "Access is denied", winerror) for _ in range(3)])
    registro.guardar({"id": ID, "estado": "en_curso", "fase": "terminado"})
    assert len(llamadas) == 4 and registro.reintentos == 3
    assert registro.obtener(ID)["fase"] == "terminado"
    assert _temporales(tmp_path) == []
    assert tiempo.esperas == sorted(tiempo.esperas) and 0 < sum(tiempo.esperas) < 1  # espera breve y creciente


def test_un_bloqueo_que_no_se_suelta_agota_un_limite_acotado_y_falla_sin_publicar(tmp_path, monkeypatch):
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    registro.guardar({"id": ID, "estado": "en_curso", "fase": "construccion"})
    antes = (tmp_path / "ejecuciones" / f"{ID}.json").read_bytes()
    llamadas = _publicacion_que_falla(monkeypatch, [_windows(13, "Access is denied", 5) for _ in range(10_000)])
    with pytest.raises(PermissionError) as error:
        registro.guardar({"id": ID, "estado": "en_curso", "fase": "terminado"})
    assert "siguio bloqueado" in str(error.value) and f"{ID}.json" in str(error.value)
    assert isinstance(error.value.__cause__, PermissionError)  # el error original no se pierde
    assert 3 < len(llamadas) < 200 and sum(tiempo.esperas) <= ofs.LIMITE_DE_REEMPLAZO  # acotado
    assert (tmp_path / "ejecuciones" / f"{ID}.json").read_bytes() == antes  # nunca se escribe el definitivo a medias
    assert _temporales(tmp_path) == []


# ---------------------------------------------------------------------------
# Errores permanentes: sin reintentos
# ---------------------------------------------------------------------------

def test_un_destino_de_solo_lectura_es_permanente_y_no_se_reintenta(tmp_path, monkeypatch):
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    registro.guardar({"id": ID, "estado": "en_curso"})
    monkeypatch.setattr(ofs, "_solo_lectura", lambda ruta: True)
    llamadas = _publicacion_que_falla(monkeypatch, [_windows(13, "Access is denied", 5) for _ in range(5)])
    with pytest.raises(PermissionError):
        registro.guardar({"id": ID, "estado": "exito"})
    assert len(llamadas) == 1 and tiempo.esperas == [] and registro.reintentos == 0
    assert registro.obtener(ID)["estado"] == "en_curso" and _temporales(tmp_path) == []


@pytest.mark.parametrize("error", [OSError(errno.ENOSPC, "No space left on device"),
                                   PermissionError(errno.EACCES, "Permission denied"),
                                   OSError(errno.EROFS, "Read-only file system")])
def test_los_errores_sin_bloqueo_de_windows_se_propagan_al_primer_intento(tmp_path, monkeypatch, error):
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    llamadas = _publicacion_que_falla(monkeypatch, [error])
    with pytest.raises(OSError) as capturado:
        registro.guardar({"id": ID, "estado": "en_curso"})
    assert capturado.value is error and len(llamadas) == 1 and tiempo.esperas == []
    assert registro.obtener(ID) is None and _temporales(tmp_path) == []


def test_un_fallo_al_escribir_el_temporal_no_toca_el_definitivo(tmp_path, monkeypatch):
    registro = _registro(tmp_path, _Tiempo())
    registro.guardar({"id": ID, "estado": "en_curso", "fase": "construccion"})
    antes = (tmp_path / "ejecuciones" / f"{ID}.json").read_bytes()

    def fsync_que_falla(_):
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(ofs.os, "fsync", fsync_que_falla)
    with pytest.raises(OSError):
        registro.guardar({"id": ID, "estado": "exito"})
    assert (tmp_path / "ejecuciones" / f"{ID}.json").read_bytes() == antes and _temporales(tmp_path) == []


@pytest.mark.parametrize("fase", ["escritura", "publicacion", "exito"])
def test_la_limpieza_no_toca_otro_registro_ni_un_temporal_previo(tmp_path, monkeypatch, fase):
    """Una actualizacion solo puede limpiar el temporal que ella misma creo."""
    registro = _registro(tmp_path, _Tiempo())
    otro_id = "20261013T135713Z-ea2cebb0"
    registro.guardar({"id": ID, "n": 0})
    registro.guardar({"id": otro_id, "n": 8})
    carpeta = tmp_path / "ejecuciones"
    previo = carpeta / f".{ID}.deadcafe.tmp"
    previo.write_bytes(b"temporal previo ajeno: conservar\x00\xff")
    antes = {p.name: p.read_bytes() for p in carpeta.iterdir()}

    if fase == "escritura":
        def fsync_que_falla(_):
            raise OSError(errno.EIO, "escritura sintetica fallida")
        monkeypatch.setattr(ofs.os, "fsync", fsync_que_falla)
    elif fase == "publicacion":
        _publicacion_que_falla(monkeypatch, [OSError(errno.ENOSPC, "publicacion sintetica fallida")])

    if fase == "exito":
        registro.guardar({"id": ID, "n": 1})
        assert registro.obtener(ID) == {"id": ID, "n": 1}
    else:
        with pytest.raises(OSError):
            registro.guardar({"id": ID, "n": 1})
        assert (carpeta / f"{ID}.json").read_bytes() == antes[f"{ID}.json"]
    assert set(p.name for p in carpeta.iterdir()) == set(antes)
    assert (carpeta / f"{otro_id}.json").read_bytes() == antes[f"{otro_id}.json"]
    assert previo.read_bytes() == antes[previo.name]


# ---------------------------------------------------------------------------
# Lectores: un bloqueo pasajero no convierte el registro en «ilegible»
# ---------------------------------------------------------------------------

def test_un_lector_reintenta_un_bloqueo_transitorio_y_no_escribe(tmp_path, monkeypatch):
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    registro.guardar({"id": ID, "estado": "en_curso", "fase": "construccion"})
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    antes = ruta.read_bytes()
    real = ofs._abrir_lectura_registro
    fallos = [_windows(13, "The process cannot access the file", 32)]

    def lectura(archivo):
        if archivo == ruta and fallos:
            raise fallos.pop(0)
        return real(archivo)

    monkeypatch.setattr(ofs, "_abrir_lectura_registro", lectura)
    assert registro.obtener(ID) == {"id": ID, "estado": "en_curso", "fase": "construccion"}
    assert registro.reintentos == 1 and tiempo.esperas == [ofs._PRIMERA_ESPERA]
    assert ruta.read_bytes() == antes and _temporales(tmp_path) == []


def test_un_lector_bloqueado_agota_su_limite_sin_tocar_el_json(tmp_path, monkeypatch):
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    registro.guardar({"id": ID, "n": 0})
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    antes = ruta.read_bytes()

    def lectura(archivo):
        raise _windows(errno.EACCES, "lector bloqueado por otro", 32)

    monkeypatch.setattr(ofs, "_abrir_lectura_registro", lectura)
    assert registro.obtener(ID)["estado"] == "ilegible"
    assert registro.reintentos > 0 and 0 < tiempo.ahora <= ofs.LIMITE_DE_LECTURA
    assert ruta.read_bytes() == antes and _temporales(tmp_path) == []


def test_un_lector_con_un_error_permanente_informa_ilegible_sin_esperar(tmp_path, monkeypatch):
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    registro.guardar({"id": ID, "estado": "en_curso"})
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"

    def lectura(archivo):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(ofs, "_abrir_lectura_registro", lectura)
    assert registro.obtener(ID)["estado"] == "ilegible" and tiempo.esperas == []


# ---------------------------------------------------------------------------
# Concurrencia real: lectores cooperantes y contencion externa se distinguen.
# ---------------------------------------------------------------------------

LECTOR_EXTERNO = r"""
import json, os, sys, time
from pathlib import Path
from app.infrastructure.storage.operacion_file_store import RegistroEjecucionesArchivo
carpeta, identificador, parar, listo, final_visto = sys.argv[1:]
registro = RegistroEjecucionesArchivo(carpeta)
datos = {"lecturas": 0, "errores": [], "coherentes": True, "ordenadas": True,
         "primero": None, "ultimo": None, "reintentos": 0}
limite = time.monotonic() + 120
final_reportado = False
try:
    while not os.path.exists(parar):
        if time.monotonic() >= limite:
            raise TimeoutError("lector externo agoto su limite propio")
        estado = registro.obtener(identificador)
        n = estado.get("n") if isinstance(estado, dict) else None
        if not isinstance(n, int) or estado != {"id": identificador, "n": n} or not 0 <= n <= 120:
            datos["coherentes"] = False
            raise AssertionError("lectura externa incoherente: " + repr(estado))
        if datos["ultimo"] is not None and n < datos["ultimo"]:
            datos["ordenadas"] = False
            raise AssertionError("el lector externo retrocedio")
        if datos["primero"] is None:
            datos["primero"] = n
        datos["ultimo"] = n
        datos["lecturas"] += 1
        if datos["lecturas"] == 1:
            Path(listo).write_text("primera lectura coherente", encoding="ascii")
        if n == 120 and not final_reportado:
            Path(final_visto).write_text("estado final coherente", encoding="ascii")
            final_reportado = True
except BaseException as error:
    datos["errores"].append(repr(error))
    raise
finally:
    datos["reintentos"] = registro.reintentos
    print(json.dumps(datos, sort_keys=True), flush=True)
"""

LECTOR_RETENIDO = r"""
import json, sys, time
from pathlib import Path
from app.infrastructure.storage import operacion_file_store as ofs
carpeta, identificador, soltar, listo, cerrado, modo = sys.argv[1:]
ruta = Path(carpeta) / "ejecuciones" / (identificador + ".json")
datos = {"modo": modo, "lecturas": 0, "errores": [], "cerrado": False}
try:
    abrir = ofs._abrir_lectura_registro if modo == "cooperante" else lambda p: p.open("r", encoding="utf-8")
    with abrir(ruta) as flujo:
        datos["inicial"] = json.loads(flujo.read())
        datos["lecturas"] += 1
        Path(listo).write_text("handle abierto", encoding="ascii")
        limite = time.monotonic() + 20
        while not Path(soltar).exists():
            if time.monotonic() >= limite:
                raise TimeoutError("lector retenido agoto su limite propio")
            time.sleep(0.002)
        flujo.seek(0)
        datos["retenido_despues"] = json.loads(flujo.read())
        datos["lecturas"] += 1
    datos["cerrado"] = True
    Path(cerrado).write_text("handle cerrado", encoding="ascii")
    datos["final"] = ofs.RegistroEjecucionesArchivo(carpeta).obtener(identificador)
    datos["lecturas"] += 1
except BaseException as error:
    datos["errores"].append(repr(error))
    raise
finally:
    print(json.dumps(datos, sort_keys=True), flush=True)
"""


def _proceso(codigo: str, *argumentos: object) -> subprocess.Popen:
    """Solo inicia el Python de esta prueba; no utiliza configuraciones ni datos reales."""
    backend = str(Path(ofs.__file__).resolve().parents[3])
    entorno = dict(os.environ)
    entorno["PYTHONPATH"] = backend + (os.pathsep + entorno["PYTHONPATH"] if entorno.get("PYTHONPATH") else "")
    return subprocess.Popen([sys.executable, "-c", codigo, *(str(a) for a in argumentos)],
                            cwd=backend, env=entorno, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _esperar_archivo(ruta: Path, proceso: subprocess.Popen, segundos: float = 10) -> None:
    limite = time.monotonic() + segundos
    while not ruta.exists():
        assert proceso.poll() is None, "el proceso propio termino antes de dar la senal"
        assert time.monotonic() < limite, f"el proceso propio no dio la senal {ruta.name}"
        time.sleep(0.002)


def _cerrar_proceso(proceso: subprocess.Popen, soltar: Path) -> tuple[dict, list[str]]:
    """Cierre acotado exclusivamente del hijo propio; no oculta la excepcion de la prueba."""
    problemas = []
    try:
        soltar.write_text("fin", encoding="ascii")
    except OSError as error:
        problemas.append("senal de cierre: " + repr(error))
    salida = error_texto = ""
    try:
        salida, error_texto = proceso.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        problemas.append("el proceso propio no termino tras la senal; se termino")
        try:
            proceso.terminate()
        except OSError as error:
            problemas.append("terminate del proceso propio: " + repr(error))
        try:
            salida, error_texto = proceso.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            problemas.append("el proceso propio necesito kill")
            try:
                proceso.kill()
                salida, error_texto = proceso.communicate(timeout=3)
            except (OSError, subprocess.TimeoutExpired) as error:
                problemas.append("recogida tras kill del proceso propio: " + repr(error))
    except OSError as error:
        problemas.append("recogida del proceso propio: " + repr(error))
    datos = {"codigo_salida": proceso.returncode, "stderr": error_texto, "stdout": salida}
    try:
        datos.update(json.loads(salida))
    except (ValueError, TypeError) as error:
        problemas.append("diagnostico del proceso propio no es JSON: " + repr(error))
    return datos, problemas


def _diagnostico_final(nombre: str, datos: dict, problemas: list[str],
                       excepcion: BaseException | None, carpeta: Path) -> None:
    """La medicion se intenta tambien al fallar; un problema de cierre no sustituye el fallo inicial."""
    publicador = _soporte_publicacion(carpeta)
    incidencia_cierre = publicador.get("incidencia_cierre")
    if incidencia_cierre is not None:
        problemas.append("cierre de HANDLE del publicador: " + repr(incidencia_cierre))
    datos.update({"plataforma": sys.platform, "sistema": platform.platform(), "python": sys.version,
                  "fallo_inicial": repr(excepcion) if excepcion is not None else None,
                  "errno_inicial": getattr(excepcion, "errno", None),
                  "winerror_inicial": getattr(excepcion, "winerror", None),
                  "notas_error_inicial": list(getattr(excepcion, "__notes__", [])),
                  "problemas_de_cierre": problemas,
                  "publicador": publicador})
    try:
        _medicion(nombre, datos)
    except OSError as error:
        problemas.append("no se pudo guardar la medicion: " + repr(error))
    if problemas:
        if excepcion is not None:
            if hasattr(excepcion, "add_note"):
                excepcion.add_note("; ".join(problemas))
        else:
            raise AssertionError("; ".join(problemas))


def test_concurrencia_real_lectores_en_hilos_y_en_otro_proceso_mientras_se_publica(tmp_path):
    """120 publicaciones completas ante cuatro lectores reales sin pausas.

    Los tres hilos usan instancias distintas; el cuarto lector es otro proceso.
    Los lectores cooperantes no deben negar el reemplazo. La contencion de un
    externo que lo niega se verifica aparte con coordinacion determinista.
    """
    inicio = time.monotonic()
    limite_global = inicio + 90

    def reloj_acotado():
        ahora = time.monotonic()
        if ahora > limite_global:
            raise TimeoutError("la prueba de 120 publicaciones agoto su limite propio de 90 s")
        return ahora

    registro = RegistroEjecucionesArchivo(tmp_path, reloj=reloj_acotado)
    registro.guardar({"id": ID, "n": 0})
    lectores = [RegistroEjecucionesArchivo(tmp_path) for _ in range(3)]
    parar, listo, final_visto = (tmp_path / n for n in ("parar", "listo", "final_visto"))
    externo = _proceso(LECTOR_EXTERNO, tmp_path, ID, parar, listo, final_visto)
    vistos = [{"lecturas": 0, "primero": None, "ultimo": None, "coherentes": True, "ordenadas": True}
              for _ in range(3)]
    errores: list[list[str]] = [[], [], []]
    preparados = [threading.Event() for _ in range(3)]
    finales_vistos = [threading.Event() for _ in range(3)]
    fin = threading.Event()
    publicadas = objetivo = 0
    inicio_publicacion = None
    datos_externos = {}
    hilos = []

    def lector(i: int) -> None:
        try:
            while not fin.is_set():
                estado = lectores[i].obtener(ID)
                n = estado.get("n") if isinstance(estado, dict) else None
                if not isinstance(n, int) or estado != {"id": ID, "n": n} or not 0 <= n <= 120:
                    vistos[i]["coherentes"] = False
                    raise AssertionError("lectura incoherente: " + repr(estado))
                if vistos[i]["ultimo"] is not None and n < vistos[i]["ultimo"]:
                    vistos[i]["ordenadas"] = False
                    raise AssertionError("el lector retrocedio")
                if vistos[i]["primero"] is None:
                    vistos[i]["primero"] = n
                vistos[i]["ultimo"] = n
                vistos[i]["lecturas"] += 1
                preparados[i].set()
                if n == 120:
                    finales_vistos[i].set()
        except BaseException as error:
            errores[i].append(repr(error))
            preparados[i].set()

    try:
        _esperar_archivo(listo, externo)
        hilos = [threading.Thread(target=lector, args=(i,), name=f"f4v33-lector-{i}", daemon=True)
                 for i in range(3)]
        for hilo in hilos:
            hilo.start()
        for preparado in preparados:
            assert preparado.wait(5), "un lector propio no inicio"
        assert errores == [[], [], []]
        inicio_publicacion = time.monotonic()
        for objetivo in range(1, 121):
            reloj_acotado()
            registro.guardar({"id": ID, "n": objetivo})
            publicadas = objetivo
        for final in finales_vistos:
            assert final.wait(5), "un lector propio no observo el estado final"
        _esperar_archivo(final_visto, externo, 5)
        assert registro.obtener(ID) == {"id": ID, "n": 120}
        assert _temporales(tmp_path) == []
    finally:
        excepcion = sys.exc_info()[1]
        fin.set()
        problemas = []
        limite = time.monotonic() + 5
        for hilo in hilos:
            if hilo.ident is not None:
                hilo.join(timeout=max(0, limite - time.monotonic()))
            if hilo.is_alive():
                problemas.append("hilo propio no termino: " + hilo.name)
        datos_externos, problemas_hijo = _cerrar_proceso(externo, parar)
        problemas.extend(problemas_hijo)
        fin_tiempo = time.monotonic()
        _diagnostico_final("concurrencia", {
            "publicaciones": publicadas, "publicacion_intentada": objetivo,
            "objetivo_publicaciones": 120, "duracion_s": round(fin_tiempo - inicio, 6),
            "duracion_publicacion_s": (round(fin_tiempo - inicio_publicacion, 6)
                                        if inicio_publicacion is not None else None),
            "reintentos_del_escritor": registro.reintentos,
            "lecturas_del_otro_proceso": datos_externos.get("lecturas", 0),
            "errores_del_otro_proceso": len(datos_externos.get("errores", [])),
            "lectores_hilos": [{"lector": i, **vistos[i], "errores": errores[i],
                                "reintentos": lectores[i].reintentos,
                                "hilo_vivo": hilos[i].is_alive() if len(hilos) > i else False}
                               for i in range(3)],
            "lector_externo": datos_externos,
        }, problemas, excepcion, tmp_path)
    assert publicadas == 120
    assert errores == [[], [], []]
    assert all(v["lecturas"] > 0 and v["coherentes"] and v["ordenadas"] and v["ultimo"] == 120
               for v in vistos)
    assert datos_externos["codigo_salida"] == 0, datos_externos
    assert datos_externos["lecturas"] > 0 and datos_externos["errores"] == []
    assert datos_externos["coherentes"] and datos_externos["ordenadas"]
    assert datos_externos["ultimo"] == 120
    assert registro.obtener(ID) == {"id": ID, "n": 120}
    assert _temporales(tmp_path) == []


def test_ventanas_periodicas_de_3_y_2_ms_no_garantizan_un_reintento_libre(tmp_path, monkeypatch):
    """Experimento portable: todas las esperas del backoff son multiplos de 5 ms.

    Un externo puede dejar 2 ms libres cada 5 ms y aun asi negar todos los
    intentos del escritor. No se usa esta simulacion como evidencia Windows.
    """
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    registro.guardar({"id": ID, "n": 0})
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    antes = ruta.read_bytes()
    real = ofs._publicar_temporal
    fases = []

    def reemplazar(origen, destino):
        fase_ms = round(tiempo.ahora * 1000) % 5
        fases.append(fase_ms)
        if fase_ms < 3:
            raise _windows(errno.EACCES, "externo periodico sin FILE_SHARE_DELETE", 5)
        return real(origen, destino)

    monkeypatch.setattr(ofs, "_publicar_temporal", reemplazar)
    try:
        with pytest.raises(ofs.ReemplazoBloqueadoError):
            registro.guardar({"id": ID, "n": 1})
        assert len(fases) > 3 and set(fases) == {0}
        assert sum(tiempo.esperas) <= ofs.LIMITE_DE_REEMPLAZO
        assert ruta.read_bytes() == antes and _temporales(tmp_path) == []
    finally:
        _diagnostico_final("ventanas_periodicas_simuladas", {
            "tipo": "simulacion_portable_no_windows", "fases_de_intento_ms": fases,
            "apertura_ms": 3, "ventana_libre_ms": 2,
            "reintentos_del_escritor": registro.reintentos,
            "tiempo_simulado_s": tiempo.ahora,
        }, [], sys.exc_info()[1], tmp_path)


@pytest.mark.parametrize("modo", ["cooperante", "ordinario"])
def test_handle_de_otro_proceso_distingue_lector_cooperante_de_apertura_ordinaria(tmp_path, modo):
    """Control nativo A/B: mismo handle retenido, distinta comparticion.

    En Windows se exige FileRenameInfoEx con flags 3 y apertura cooperante:
    compartir eliminacion no bastaba con MoveFileExW (fallo nativo v3.2).
    Path.open niega eliminacion y conserva el control negativo. La semantica
    exige que los handles existentes compartan eliminacion (CPython #90161 y
    https://discuss.python.org/t/adding-atomicwrite-in-stdlib/11899/16).
    El reloj inyectado evita consumir 10 s en el control bloqueante, sin cambiar
    el limite ni sustituir la primitiva nativa de publicacion.
    En POSIX ambas aperturas permiten publicar y se documenta esa diferencia.
    """
    tiempo = _Tiempo()
    registro = _registro(tmp_path, tiempo)
    registro.guardar({"id": ID, "n": 0})
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    antes = ruta.read_bytes()
    soltar, listo, cerrado = (tmp_path / n for n in ("soltar", "listo", "cerrado"))
    externo = _proceso(LECTOR_RETENIDO, tmp_path, ID, soltar, listo, cerrado, modo)
    inicio = time.monotonic()
    publicado = False
    datos_externos = {}
    lectura_nueva_mientras_retenido = None
    try:
        _esperar_archivo(listo, externo)
        if WINDOWS and modo == "ordinario":
            with pytest.raises(ofs.ReemplazoBloqueadoError):
                registro.guardar({"id": ID, "n": 1})
            assert 0 < registro.reintentos < 200
            assert ruta.read_bytes() == antes
            assert 0 < tiempo.ahora <= ofs.LIMITE_DE_REEMPLAZO
        else:
            registro.guardar({"id": ID, "n": 1})
            publicado = True
            assert registro.reintentos == 0
            lectura_nueva_mientras_retenido = registro.obtener(ID)
            assert lectura_nueva_mientras_retenido == {"id": ID, "n": 1}
        assert not cerrado.exists(), "el escritor debia intentar publicar mientras seguia abierto"
        assert _temporales(tmp_path) == []
    finally:
        excepcion = sys.exc_info()[1]
        datos_externos, problemas = _cerrar_proceso(externo, soltar)
        _diagnostico_final("handle_retenido_" + modo, {
            "modo": modo, "publicaciones": int(publicado), "publicacion_intentada": 1,
            "lectura_nueva_mientras_retenido": lectura_nueva_mientras_retenido,
            "duracion_s": round(time.monotonic() - inicio, 6),
            "tiempo_simulado_de_reintentos_s": tiempo.ahora,
            "reintentos_del_escritor": registro.reintentos, "lector_externo": datos_externos,
        }, problemas, excepcion, tmp_path)
    assert datos_externos["codigo_salida"] == 0, datos_externos
    assert datos_externos["errores"] == [] and datos_externos["cerrado"]
    assert datos_externos["inicial"] == {"id": ID, "n": 0}
    assert datos_externos["retenido_despues"] == {"id": ID, "n": 0}
    assert datos_externos["final"] == {"id": ID, "n": int(publicado)}
    if not publicado:
        assert ruta.read_bytes() == antes
    else:
        assert registro.obtener(ID) == {"id": ID, "n": 1}
    assert _temporales(tmp_path) == []


def test_bloqueo_real_externo_se_libera_solo_al_observar_un_reintento(tmp_path):
    """Contencion real sin acertar ventanas de sleep: el retry autoriza cerrar el handle."""
    soltar, listo, cerrado = (tmp_path / n for n in ("soltar", "listo", "cerrado"))
    externo = None
    liberado_por_reintento = False

    def espera(segundos):
        nonlocal liberado_por_reintento
        liberado_por_reintento = True
        soltar.write_text("se observo reintento", encoding="ascii")
        _esperar_archivo(cerrado, externo, 5)
        time.sleep(segundos)

    registro = RegistroEjecucionesArchivo(tmp_path, espera=espera)
    registro.guardar({"id": ID, "n": 0})
    externo = _proceso(LECTOR_RETENIDO, tmp_path, ID, soltar, listo, cerrado, "ordinario")
    inicio = time.monotonic()
    publicado = False
    datos_externos = {}
    try:
        _esperar_archivo(listo, externo)
        registro.guardar({"id": ID, "n": 1})
        publicado = True
        assert registro.obtener(ID) == {"id": ID, "n": 1}
        assert _temporales(tmp_path) == []
        assert liberado_por_reintento is WINDOWS
        assert (registro.reintentos > 0) is WINDOWS
    finally:
        excepcion = sys.exc_info()[1]
        datos_externos, problemas = _cerrar_proceso(externo, soltar)
        _diagnostico_final("externo_liberado_tras_reintento", {
            "publicaciones": int(publicado), "publicacion_intentada": 1,
            "duracion_s": round(time.monotonic() - inicio, 6),
            "liberado_por_reintento": liberado_por_reintento,
            "reintentos_del_escritor": registro.reintentos, "lector_externo": datos_externos,
        }, problemas, excepcion, tmp_path)
    assert datos_externos["codigo_salida"] == 0 and datos_externos["errores"] == [], datos_externos
    assert registro.obtener(ID) == {"id": ID, "n": 1} and _temporales(tmp_path) == []


def test_bloqueo_real_destino_abierto_por_otro_se_publica_al_soltarse(tmp_path):
    """Se conserva el bloqueo por otro hilo; se libera tras observar retry, sin temporizador."""
    abierto, soltar, cerrado = threading.Event(), threading.Event(), threading.Event()
    errores_hilo = []

    def espera(segundos):
        soltar.set()
        assert cerrado.wait(5), "el lector propio no cerro el handle"
        time.sleep(segundos)

    registro = RegistroEjecucionesArchivo(tmp_path, espera=espera)
    registro.guardar({"id": ID, "fase": "construccion"})
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"

    def otro():
        try:
            with open(ruta, "rb"):
                abierto.set()
                assert soltar.wait(10), "no se libero el lector propio"
        except BaseException as error:
            errores_hilo.append(repr(error))
            abierto.set()
        finally:
            cerrado.set()

    hilo = threading.Thread(target=otro, name="f4v33-destino-abierto", daemon=True)
    hilo.start()
    inicio = time.monotonic()
    publicado = False
    try:
        assert abierto.wait(5) and not errores_hilo
        registro.guardar({"id": ID, "fase": "terminado"})
        publicado = True
        assert (registro.reintentos > 0) is WINDOWS
        assert registro.obtener(ID)["fase"] == "terminado" and _temporales(tmp_path) == []
    finally:
        excepcion = sys.exc_info()[1]
        soltar.set()
        hilo.join(5)
        problemas = ["el hilo propio sigue vivo"] if hilo.is_alive() else []
        _diagnostico_final("destino_abierto", {
            "publicaciones": int(publicado), "publicacion_intentada": 1,
            "reintentos_del_escritor": registro.reintentos, "errores_del_lector": errores_hilo,
            "espera_s": round(time.monotonic() - inicio, 6),
        }, problemas, excepcion, tmp_path)
    assert errores_hilo == []

def test_bloqueo_real_destino_de_solo_lectura(tmp_path):
    """Destino con el atributo de solo lectura. En Windows es un error permanente: falla al primer intento, sin
    esperar, y el JSON conserva su estado; en POSIX renombrar no depende de ese permiso y se publica."""
    registro = RegistroEjecucionesArchivo(tmp_path)
    registro.guardar({"id": ID, "estado": "en_curso"})
    ruta = tmp_path / "ejecuciones" / f"{ID}.json"
    os.chmod(ruta, stat.S_IREAD)  # en Windows, FILE_ATTRIBUTE_READONLY
    try:
        inicio = time.monotonic()
        if WINDOWS:
            with pytest.raises(PermissionError):
                registro.guardar({"id": ID, "estado": "exito"})
            assert json.loads(ruta.read_text(encoding="utf-8"))["estado"] == "en_curso"
        else:
            registro.guardar({"id": ID, "estado": "exito"})
            assert json.loads(ruta.read_text(encoding="utf-8"))["estado"] == "exito"
        assert time.monotonic() - inicio < 1 and registro.reintentos == 0 and _temporales(tmp_path) == []
    finally:
        os.chmod(ruta, stat.S_IREAD | stat.S_IWRITE)
