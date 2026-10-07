"""Producto 3 / issue #83: el almacen de pronosticos publica cada JSON
final solo cuando esta completo.

Antes, `guardar` creaba el JSON final con `open(ruta, "xb")` y escribia
despues: durante la escritura otro lector (la web, el comando) veia un
archivo final a medio escribir y lo informaba como alterado. Ahora el
contenido se escribe en un temporal de la misma carpeta y se publica con
`os.link` (crea el nombre final solo si no existe; nunca sobrescribe).

Coordinacion determinista con eventos y barreras (sin azar ni esperas
largas); hilos y procesos independientes."""
from __future__ import annotations

import builtins
import hashlib
import multiprocessing
import os
import threading
from pathlib import Path

import pytest

from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado, PronosticoIlegible
from app.application.ml import pronostico_experimental as pe
from app.application.ml.registro_prospectivo import serializar_entrada
from app.infrastructure.storage import pronostico_experimental_file_store as modulo
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore

ESPERA = 10  # segundos maximos de cada evento; nunca se alcanzan si el codigo es correcto


def artefacto(clave: str, objetivo: int = 85, juego: str = "MILOTO", relleno: int = 2000) -> dict:
    """Artefacto valido y pequeno (el almacen no entrena)."""
    cuerpo = {"esquema": "pronostico-experimental/2", "juego": juego, "clave_de_entrada": clave,
              "estado_de_uso": "experimental_no_acreditado",
              "pronostico": {"objetivo": objetivo, "ranking": list(range(relleno))}}
    return pe.componer_artefacto(cuerpo, generado_en="2026-10-01T12:00:00+00:00")


def clave(i: int) -> str:
    return hashlib.sha256(f"clave-{i}".encode()).hexdigest()


class _EscrituraPausada:
    """Envuelve el archivo que escribe el almacen: escribe la mitad, avisa y
    espera a que el lector termine antes de escribir el resto."""

    def __init__(self, flujo, a_medias: threading.Event, continuar: threading.Event):
        self._flujo, self._a_medias, self._continuar = flujo, a_medias, continuar

    def write(self, datos):
        mitad = len(datos) // 2
        self._flujo.write(datos[:mitad])
        self._flujo.flush()
        self._a_medias.set()
        assert self._continuar.wait(ESPERA)
        return mitad + self._flujo.write(datos[mitad:])

    def __getattr__(self, nombre):
        return getattr(self._flujo, nombre)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self._flujo.__exit__(*exc)


def test_regresion_83_un_lector_nunca_ve_un_json_final_a_medio_escribir(tmp_path, monkeypatch):
    almacen = PronosticoExperimentalFileStore(tmp_path)
    a_medias, continuar = threading.Event(), threading.Event()
    original = builtins.open

    def abrir(ruta, modo="r", *args, **kwargs):
        flujo = original(ruta, modo, *args, **kwargs)
        return _EscrituraPausada(flujo, a_medias, continuar) if "x" in modo and "b" in modo else flujo

    monkeypatch.setattr(modulo, "open", abrir, raising=False)
    errores = []
    escritor = threading.Thread(target=lambda: _capturar(errores, almacen.guardar, "MILOTO", artefacto(clave(1))))
    escritor.start()
    try:
        assert a_medias.wait(ESPERA), "el escritor no llego a la escritura"
        vistos = almacen.listar("MILOTO")
        obtenido = almacen.obtener("MILOTO", clave(1))
        finales = sorted(p.name for p in (tmp_path / "MILOTO").glob("*.json"))
    finally:
        continuar.set()
        escritor.join(ESPERA)
    assert not errores, errores
    # Mientras el escritor esta a medias no hay JSON final, ni ilegible ni parcial.
    assert vistos == [] and obtenido is None and finales == []
    final = almacen.listar("MILOTO")
    assert len(final) == 1 and isinstance(final[0], PronosticoGuardado) and final[0].identificador == clave(1)


def _capturar(errores, funcion, *args):
    try:
        funcion(*args)
    except BaseException as error:  # noqa: BLE001 - se informa en el hilo principal
        errores.append(repr(error))


def test_misma_clave_en_dos_hilos_un_solo_artefacto(tmp_path):
    almacen = PronosticoExperimentalFileStore(tmp_path)
    barrera = threading.Barrier(2)
    resultados = []

    def guardar():
        barrera.wait(ESPERA)
        try:
            resultados.append(almacen.guardar("MILOTO", artefacto(clave(1))).identificador)
        except FileExistsError:
            resultados.append("existe")

    hilos = [threading.Thread(target=guardar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(ESPERA)
    assert sorted(resultados) == sorted([clave(1), "existe"])
    assert [e.identificador for e in almacen.listar("MILOTO")] == [clave(1)]
    _sin_temporales(tmp_path)


def test_claves_distintas_secuencias_distintas_y_version_anterior(tmp_path):
    almacen = PronosticoExperimentalFileStore(tmp_path)
    barrera = threading.Barrier(3)
    errores = []

    def guardar(i):
        barrera.wait(ESPERA)
        _capturar(errores, almacen.guardar, "MILOTO", artefacto(clave(i)))

    hilos = [threading.Thread(target=guardar, args=(i,)) for i in range(3)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(ESPERA)
    assert not errores
    guardados = almacen.listar("MILOTO")
    secuencias = sorted(g.artefacto["generacion"]["secuencia_en_el_objetivo"] for g in guardados)
    assert len(set(secuencias)) == 3 and [g.version for g in guardados] == [3, 2, 1]
    assert all(isinstance(g, PronosticoGuardado) for g in guardados)
    _sin_temporales(tmp_path)


def test_interrupcion_antes_de_publicar_no_deja_json_final_y_luego_se_reutiliza(tmp_path, monkeypatch):
    almacen = PronosticoExperimentalFileStore(tmp_path)

    def corte(*_args, **_kwargs):
        raise KeyboardInterrupt("proceso interrumpido antes de publicar")

    monkeypatch.setattr(modulo.os, "link", corte)
    with pytest.raises(KeyboardInterrupt):
        almacen.guardar("MILOTO", artefacto(clave(1)))
    monkeypatch.undo()
    carpeta = tmp_path / "MILOTO"
    assert list(carpeta.glob("*.json")) == []
    temporales = almacen.temporales("MILOTO")
    assert len(temporales) == 1  # se conserva: puede pertenecer a una escritura activa; no es un error de integridad
    assert almacen.listar("MILOTO") == []
    guardado = almacen.guardar("MILOTO", artefacto(clave(1)))
    assert guardado.version == 1 and guardado.versiones == 1
    assert [e.identificador for e in almacen.listar("MILOTO")] == [clave(1)]
    assert almacen.temporales("MILOTO") == temporales  # nada se borra automaticamente


def test_publicacion_no_sobrescribe_un_destino_existente(tmp_path):
    """Si el nombre final ya existe (otro escritor lo publico, o es un
    ilegible antiguo), `guardar` falla y no lo toca."""
    almacen = PronosticoExperimentalFileStore(tmp_path)
    carpeta = tmp_path / "MILOTO"
    carpeta.mkdir(parents=True)
    ilegible = carpeta / f"85-{clave(1)}.json"
    ilegible.write_bytes(b"{no es json")
    with pytest.raises(FileExistsError):
        almacen.guardar("MILOTO", artefacto(clave(1)))
    assert ilegible.read_bytes() == b"{no es json"
    assert isinstance(almacen.listar("MILOTO")[0], PronosticoIlegible)
    _sin_temporales(tmp_path)


def test_bytes_de_artefactos_existentes_se_conservan(tmp_path):
    """Un artefacto antiguo (sin secuencia) escrito con los bytes canonicos
    se lee igual y sus bytes no cambian al guardar otra version."""
    almacen = PronosticoExperimentalFileStore(tmp_path)
    carpeta = tmp_path / "MILOTO"
    carpeta.mkdir(parents=True)
    antiguo = artefacto(clave(7))
    ruta = carpeta / f"85-{clave(7)}.json"
    ruta.write_bytes(serializar_entrada(antiguo))
    antes = ruta.read_bytes()
    nuevo = almacen.guardar("MILOTO", artefacto(clave(8)))
    assert ruta.read_bytes() == antes
    assert nuevo.artefacto["generacion"]["version_anterior"] == clave(7)
    assert [g.version for g in almacen.listar("MILOTO")] == [2, 1]
    publicado = (carpeta / f"85-{clave(8)}.json").read_bytes()
    assert publicado == serializar_entrada(nuevo.artefacto)


def _sin_temporales(raiz: Path):
    assert not [p for p in raiz.rglob("*") if p.name.endswith(".tmp")]


# ---------------------------------------------------------------------------
# Procesos independientes (comando y servidor a la vez)
# ---------------------------------------------------------------------------

def _proceso_guardar(directorio, numero, barrera, cola):
    almacen = PronosticoExperimentalFileStore(directorio)
    barrera.wait(ESPERA)
    try:
        cola.put(("ok", almacen.guardar("MILOTO", artefacto(clave(numero))).identificador))
    except FileExistsError:
        cola.put(("existe", clave(numero)))
    except BaseException as error:  # noqa: BLE001
        cola.put(("error", repr(error)))


def _lanzar(directorio, numeros):
    contexto = multiprocessing.get_context("spawn")
    barrera = contexto.Barrier(len(numeros))
    cola = contexto.Queue()
    procesos = [contexto.Process(target=_proceso_guardar, args=(str(directorio), n, barrera, cola)) for n in numeros]
    for p in procesos:
        p.start()
    salidas = [cola.get(timeout=60) for _ in procesos]
    for p in procesos:
        p.join(60)
        assert p.exitcode == 0
    return salidas


def test_dos_procesos_misma_clave_sin_sobrescribir_ni_duplicar(tmp_path):
    salidas = _lanzar(tmp_path, [1, 1])
    assert sorted(s[0] for s in salidas) == ["existe", "ok"], salidas
    almacen = PronosticoExperimentalFileStore(tmp_path)
    elementos = almacen.listar("MILOTO")
    assert [e.identificador for e in elementos] == [clave(1)] and isinstance(elementos[0], PronosticoGuardado)
    assert len(list((tmp_path / "MILOTO").glob("*.json"))) == 1
    _sin_temporales(tmp_path)


def test_dos_procesos_claves_distintas_ambas_publicadas(tmp_path):
    salidas = _lanzar(tmp_path, [1, 2])
    assert sorted(s[0] for s in salidas) == ["ok", "ok"], salidas
    almacen = PronosticoExperimentalFileStore(tmp_path)
    guardados = almacen.listar("MILOTO")
    assert {g.identificador for g in guardados} == {clave(1), clave(2)}
    assert sorted(g.artefacto["generacion"]["secuencia_en_el_objetivo"] for g in guardados) == [1, 2]
    _sin_temporales(tmp_path)


def test_primitiva_os_link_no_sobrescribe(tmp_path):
    """La primitiva elegida: `os.link` falla si el destino existe (Linux y
    NTFS), a diferencia de `os.replace`, que sobrescribe."""
    origen, destino = tmp_path / "a.tmp", tmp_path / "b.json"
    origen.write_bytes(b"nuevo")
    destino.write_bytes(b"existente")
    with pytest.raises(FileExistsError):
        os.link(origen, destino)
    assert destino.read_bytes() == b"existente"


def test_artefactos_antiguos_conservan_bytes_y_se_reproducen(tmp_path):
    """Artefactos reales escritos como los escribia el almacen anterior (con
    y sin secuencia) se leen, se verifican y conservan sus bytes."""
    from app.application.ml import pronostico_miloto as pm
    from app.application.use_cases import pronostico_experimental as uc
    from tests.unit import fixtures_producto1 as fx

    historico = fx.historico_numerico("MILOTO", 84, primero=1)
    juegos, resultados, _ = fx.repositorios({"MILOTO": historico})
    carpeta = tmp_path / "MILOTO"
    carpeta.mkdir(parents=True)
    rutas = []
    for i, hasta in enumerate((60, 61)):
        cuerpo = uc._cuerpo("MILOTO", resultados.listar_resultados_numericos(
            juegos.obtener_por_codigo("MILOTO").id, hasta_numero_sorteo=hasta), hasta, pm.ConfiguracionMiLoto())
        a = pe.componer_artefacto(cuerpo, generado_en="2026-10-01T12:00:00+00:00")
        if i == 1:  # uno con la secuencia sellada, como Producto 1/2
            a = pe.con_orden_de_emision(a, secuencia=1, version_anterior=None)
        ruta = carpeta / f"{hasta + 1}-{a['clave_de_entrada']}.json"
        ruta.write_bytes(serializar_entrada(a))
        rutas.append((ruta, ruta.read_bytes(), a["clave_de_entrada"]))
    almacen = PronosticoExperimentalFileStore(tmp_path)
    verificar = uc.VerificarPronosticoExperimental(juegos, resultados, almacen)
    for ruta, antes, clave_artefacto in rutas:
        resultado = verificar.ejecutar("MILOTO", clave_artefacto)
        assert resultado["huella_exacta"] and resultado["mismos_datos"]
        assert ruta.read_bytes() == antes
    almacen.guardar("MILOTO", artefacto(clave(3), objetivo=62))
    assert all(ruta.read_bytes() == antes for ruta, antes, _ in rutas)
