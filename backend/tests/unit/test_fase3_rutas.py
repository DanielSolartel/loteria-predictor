"""Fase 3: publicacion del laboratorio dentro del presupuesto de rutas de Windows.

Primera ejecucion en Windows de la entrega de la Fase 3 (parche de 477419
bytes): 6 de las 60 pruebas focales fallaron. Cuatro trazas mostraban
temporales de 262 o 264 caracteres para destinos de 240 o 242: el publicador
del laboratorio formaba el temporal con el nombre final entero
(`.<nombre final>.<16 hex>.tmp`, 22 caracteres mas), y en Windows sin rutas
largas no se podia crear aunque el destino cupiera. Las otras dos (HTTP 500 y
codigo 3 de la linea de comandos) eran el mismo fallo al publicar el
pronostico de una version registrada, la ruta mas larga del almacen.

El laboratorio publica ahora con el temporal corto de Producto 5,
`.publicacion.<16 hex>.tmp` (33 caracteres), en la misma carpeta que el
destino. Estas pruebas SIMULAN el limite con el presupuesto de
`test_producto5_rutas` (operaciones de mas de 259 caracteres fallan como en
Windows); no son una ejecucion nativa de Windows. Comprueban tambien que el
contenido final es el esperado, que nada se sobrescribe, que los temporales
anteriores y nuevos se reconocen y se conservan, y que la lectura concurrente,
la interrupcion, el reintento, la exclusividad y la idempotencia no cambian.
Datos sinteticos; nada es real."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

import pytest

from app.application.interfaces.laboratorio_store import GuardadoModelo
from app.application.ml import modelos_registrados as mr
from app.application.ml.registro_prospectivo import serializar_entrada
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from scripts import laboratorio_modelos as cli
from tests.unit import fixtures_fase3 as f3
from tests.unit.test_fase3_registro import _informe, _version
from tests.unit.test_producto5_rutas import LIMITE, _presupuesto

JUEGO = "BALOTO_REVANCHA"  # el codigo de juego mas largo
TEMPORAL_NUEVO = re.compile(r"^\.publicacion\.[0-9a-f]{16}\.tmp$")
EXTRA_ANTERIOR = 22  # `.<nombre final>.<16 hex>.tmp` anade 22 caracteres al nombre final


@pytest.fixture(scope="module")
def versiones():
    informe = _informe(JUEGO, 100)
    return {"rf": _version(informe, "random_forest_clasificador"),
            "lineal": _version(informe, "logistica_regularizada")}


@pytest.fixture
def raiz_corta():
    """Carpeta temporal propia con una raiz corta: la carpeta temporal del sistema y el prefijo `f3t`. La de
    `tmp_path` en Windows (`%TEMP%\\pytest-of-<usuario>\\pytest-<N>\\<prueba>0`) anade unos 40 caracteres, y la
    prueba de temporales crea a proposito los nombres ANTERIORES con su longitud real (el del pronostico de una
    version registrada mide la carpeta + 170). Solo borra la carpeta que crea."""
    raiz = Path(tempfile.mkdtemp(prefix="f3t"))
    try:
        yield raiz
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


@pytest.fixture
def entorno(tmp_path):
    e = f3.entorno(tmp_path)
    yield e
    f3.limpiar()


def _medir(p, ruta: Path, objetivo: int) -> None:
    """Desplaza el presupuesto para que `ruta` mida `objetivo` caracteres."""
    p.desplazamiento = objetivo - len(os.path.normpath(str(ruta)))


def _temporales_publicados(p, raiz: Path) -> list[Path]:
    """Temporales de publicacion creados bajo `raiz` (fuera de `operacion`, que
    usa los del registro de ejecuciones de Producto 3)."""
    return [t for t in p.creados if t.suffix == ".tmp" and (raiz / "operacion") not in t.parents]


def _arbol(raiz: Path) -> dict:
    return {str(x.relative_to(raiz)): hashlib.sha256(x.read_bytes()).hexdigest()
            for x in sorted(raiz.rglob("*")) if x.is_file()}


# ---------------------------------------------------------------------------
# El publicador: destino admisible, temporal anterior demasiado largo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("final", [240, 242, LIMITE])
def test_destino_admisible_cuyo_temporal_anterior_no_cabe(tmp_path, monkeypatch, final):
    carpeta = tmp_path / "modelos" / JUEGO / "estimadores"
    ruta = carpeta / f"{'a' * 64}.pkl"
    p = _presupuesto(monkeypatch, tmp_path, carpeta)
    _medir(p, ruta, final)
    anterior = carpeta / f".{ruta.name}.{'0' * 16}.tmp"  # el nombre que fallaba en Windows
    assert p.longitud(ruta) == final <= LIMITE < p.longitud(anterior) == final + EXTRA_ANTERIOR
    contenido = b"estimador serializado " * 50
    LaboratorioFileStore._publicar(carpeta, ruta, contenido)
    assert p.rechazadas == []
    assert ruta.read_bytes() == contenido and [x.name for x in carpeta.iterdir()] == [ruta.name]
    temporales = _temporales_publicados(p, tmp_path)
    assert len(temporales) == 1 and temporales[0].parent == carpeta  # misma carpeta (mismo volumen)
    assert TEMPORAL_NUEVO.fullmatch(temporales[0].name) and p.longitud(temporales[0]) < p.longitud(ruta)
    with pytest.raises(FileNotFoundError):
        open(anterior, "xb")
    assert p.rechazadas == [(anterior.name, final + EXTRA_ANTERIOR)] and not anterior.exists()
    with pytest.raises(FileExistsError):  # un destino existente nunca se sobrescribe
        LaboratorioFileStore._publicar(carpeta, ruta, b"otros bytes")
    assert ruta.read_bytes() == contenido and [x.name for x in carpeta.iterdir()] == [ruta.name]


# ---------------------------------------------------------------------------
# El flujo de la Fase 3 con el presupuesto
# ---------------------------------------------------------------------------

def test_entrenar_y_guardar_con_el_presupuesto_de_rutas(entorno, monkeypatch):
    lab = entorno.laboratorio()
    r = lab.comparar_ahora([JUEGO], f3.PROTOCOLO, corte=entorno.corte(JUEGO))["juegos"][JUEGO]
    almacen = entorno.almacen_laboratorio
    carpeta = entorno.directorio / "modelos" / JUEGO
    estimadores = carpeta / "estimadores"
    p = _presupuesto(monkeypatch, entorno.directorio.parent, estimadores)
    _medir(p, estimadores / f"{'0' * 64}.pkl", 240)  # el estimador mide 240, como en la traza de Windows
    final = lab.entrenar_ahora(r["experimento"], "random_forest_clasificador")["juegos"][JUEGO]
    assert final["estado"] == "terminado", final
    assert p.rechazadas == []
    guardado = almacen.obtener_modelo(final["modelo_registrado"])
    assert isinstance(guardado, GuardadoModelo) and guardado.numero == 1
    estimador = estimadores / f"{guardado.artefacto['estimador']['sha256']}.pkl"
    manifiesto = carpeta / f"{guardado.identificador}.json"
    assert p.longitud(estimador) == 240 and estimador.read_bytes() == almacen.leer_estimador(guardado)
    assert manifiesto.read_bytes() == serializar_entrada(guardado.artefacto)
    temporales = _temporales_publicados(p, entorno.directorio)
    assert sorted({t.parent for t in temporales}) == sorted({estimadores, carpeta})
    assert all(TEMPORAL_NUEVO.fullmatch(t.name) for t in temporales)
    assert almacen.temporales() == [] and almacen.huerfanos() == [] and almacen.reservas_sin_modelo(JUEGO) == []
    otra = lab.entrenar_ahora(r["experimento"], "random_forest_clasificador")["juegos"][JUEGO]
    assert (otra["estado"], otra["numero"], otra["modelo_registrado"]) == ("reutilizado", 1, guardado.identificador)
    assert p.rechazadas == []


def test_generar_por_comando_y_por_la_web_con_el_presupuesto_de_rutas(entorno, monkeypatch):
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, JUEGO, "extra_trees_clasificador")
    clave = r["modelo_registrado"]
    almacen = entorno.almacen_laboratorio
    linea = mr.linea_registrada(almacen.obtener_modelo(clave).artefacto)["id"]
    carpeta = almacen._linea(JUEGO, linea)
    siguiente = entorno.historicos[JUEGO][-1].numero_sorteo + 1
    p = _presupuesto(monkeypatch, entorno.directorio.parent, carpeta)
    _medir(p, carpeta / f"{siguiente}-{'0' * 64}.json", 242)  # el pronostico mide 242, como en Windows
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(["generar-con-modelo", "--clave", clave], laboratorio_factory=lambda: lab,
                          salida=salida, errores=errores)
    assert codigo == cli.EXIT_OK, errores.getvalue()  # antes: codigo 3 (almacen no disponible)
    generado = json.loads(salida.getvalue())
    ruta = carpeta / f"{generado['objetivo']}-{generado['identificador']}.json"
    assert generado["linea"] == linea and p.longitud(ruta) == 242
    assert ruta.read_bytes() == serializar_entrada(almacen.obtener_pronostico(generado["identificador"]).artefacto)
    c = f3.cliente(entorno, laboratorio=lab)
    token = f3.token(c)
    corte = entorno.corte(JUEGO, 2)  # otra entrada: la web publica otro pronostico
    web = c.post(f"/laboratorio/modelo/{clave}/generar", data={"token_local": token, "corte": str(corte)},
                 follow_redirects=False)
    assert web.status_code == 303, web.text[:500]  # antes: HTTP 500
    publicados = [x for x in carpeta.iterdir() if x.suffix == ".json"]
    assert len(publicados) == 2 and all(p.longitud(x) <= LIMITE for x in publicados)
    assert p.rechazadas == [] and almacen.temporales() == []
    assert all(TEMPORAL_NUEVO.fullmatch(t.name) for t in _temporales_publicados(p, entorno.directorio))


# ---------------------------------------------------------------------------
# Temporales anteriores y nuevos
# ---------------------------------------------------------------------------

def test_temporales_anteriores_y_nuevos_se_reconocen_y_se_conservan(raiz_corta, versiones):
    almacen = LaboratorioFileStore(raiz_corta)
    guardado = almacen.guardar_modelo(*versiones["rf"])
    linea = "random_forest_clasificador-v1-reg1-reducido"
    creados = []
    for carpeta, final in ((raiz_corta / "modelos" / JUEGO, f"{'f' * 64}.json"),
                           (raiz_corta / "modelos" / JUEGO / "estimadores", f"{'f' * 64}.pkl"),
                           (raiz_corta / "experimentos" / JUEGO, f"{'f' * 64}.json"),
                           (raiz_corta / "pronosticos" / JUEGO / linea, f"2176-{'f' * 64}.json")):
        carpeta.mkdir(parents=True, exist_ok=True)
        # anterior (versiones previas o escrituras interrumpidas) y nuevo (otro escritor en curso)
        for nombre in (f".{final}.0123456789abcdef.tmp", ".publicacion.fedcba9876543210.tmp"):
            ruta = carpeta / nombre
            assert len(str(ruta)) <= LIMITE, f"la carpeta temporal del sistema es demasiado larga: {ruta}"
            ruta.write_bytes(b'{"a medio')
            creados.append(str(ruta.relative_to(raiz_corta)))
    assert almacen.temporales() == sorted(creados)
    assert almacen.huerfanos() == sorted(creados)  # el estimador lo cita su manifiesto: solo temporales
    assert [v.identificador for v in almacen.modelos(JUEGO)] == [guardado.identificador]
    assert almacen.reservas_sin_modelo(JUEGO) == [] and almacen.experimentos(JUEGO) == []
    assert almacen.pronosticos(JUEGO, linea) == [] and almacen.obtener_modelo("f" * 64) is None
    antes = {c: (raiz_corta / c).read_bytes() for c in creados}
    otra = almacen.guardar_modelo(*versiones["lineal"])  # publicar en las mismas carpetas no los toca
    assert otra.numero == 1 and almacen.temporales() == sorted(creados)
    assert {c: (raiz_corta / c).read_bytes() for c in creados} == antes


# ---------------------------------------------------------------------------
# Lectura concurrente, interrupcion, reintento, exclusividad e idempotencia
# ---------------------------------------------------------------------------

def _presupuesto_del_estimador(monkeypatch, raiz: Path):
    estimadores = raiz / "modelos" / JUEGO / "estimadores"
    p = _presupuesto(monkeypatch, raiz, estimadores)
    _medir(p, estimadores / f"{'0' * 64}.pkl", 240)
    return p


def test_un_lector_ve_la_ausencia_o_la_version_completa(tmp_path, monkeypatch, versiones):
    artefacto, contenido = versiones["rf"]
    almacen = LaboratorioFileStore(tmp_path)
    p = _presupuesto_del_estimador(monkeypatch, tmp_path)
    enlazar = os.link
    vistos = []

    def link(origen, destino, *args, **kwargs):
        if Path(destino).suffix == ".json":  # el manifiesto, ultimo paso
            assert TEMPORAL_NUEVO.fullmatch(Path(origen).name) and Path(origen).parent == Path(destino).parent
            completo = Path(origen).read_bytes()
            assert json.loads(completo)["clave"] == artefacto["clave"]  # el temporal ya esta completo
            vistos.append((almacen.obtener_modelo(artefacto["clave"]), almacen.modelos(JUEGO)))
            enlazar(origen, destino, *args, **kwargs)
            assert Path(destino).read_bytes() == completo
            return None
        return enlazar(origen, destino, *args, **kwargs)
    monkeypatch.setattr(os, "link", link)
    guardado = almacen.guardar_modelo(artefacto, contenido)
    assert vistos == [(None, [])]  # hasta el enlace del manifiesto, la version no existe para nadie
    assert isinstance(almacen.obtener_modelo(artefacto["clave"]), GuardadoModelo) and guardado.numero == 1
    assert p.rechazadas == [] and almacen.temporales() == []


class _Interrupcion(BaseException):
    """El proceso muere a mitad de la publicacion (no lo captura nadie)."""


def test_interrupcion_reintento_e_idempotencia_con_el_presupuesto(tmp_path, monkeypatch, versiones):
    artefacto, contenido = versiones["rf"]
    almacen = LaboratorioFileStore(tmp_path)
    p = _presupuesto_del_estimador(monkeypatch, tmp_path)
    enlazar = os.link
    with monkeypatch.context() as m:
        def morir(origen, destino, *args, **kwargs):
            if Path(destino).suffix == ".json":
                raise _Interrupcion()
            return enlazar(origen, destino, *args, **kwargs)
        m.setattr(os, "link", morir)
        with pytest.raises(_Interrupcion):
            almacen.guardar_modelo(artefacto, contenido)
    assert almacen.modelos(JUEGO) == [] and almacen.obtener_modelo(artefacto["clave"]) is None
    assert [(x.numero, x.estado) for x in almacen.reservas_sin_modelo(JUEGO)] == [(1, "sin_publicar")]
    interrumpido = almacen.temporales()
    assert len(interrumpido) == 1 and TEMPORAL_NUEVO.fullmatch(Path(interrumpido[0]).name)
    estimador = f"modelos/{JUEGO}/estimadores/{artefacto['estimador']['sha256']}.pkl"
    assert almacen.huerfanos() == [os.path.normpath(estimador), *interrumpido]
    guardado = almacen.guardar_modelo(artefacto, contenido)  # reintento: otro numero, mismo estimador
    assert guardado.numero == 2 and almacen.leer_estimador(guardado) == contenido
    assert [(x.numero, x.estado) for x in almacen.reservas_sin_modelo(JUEGO)] == [(1, "duplicada")]
    assert almacen.temporales() == interrumpido and (tmp_path / interrumpido[0]).exists()  # nunca se borra solo
    arbol = _arbol(tmp_path)
    with pytest.raises(FileExistsError):  # idempotencia: la misma entrada no crea otra version
        almacen.guardar_modelo(artefacto, contenido)
    assert _arbol(tmp_path) == arbol and p.rechazadas == []


def test_dos_escritores_de_la_misma_entrada_con_el_presupuesto(tmp_path, monkeypatch, versiones):
    artefacto, contenido = versiones["rf"]
    primero, segundo = LaboratorioFileStore(tmp_path), LaboratorioFileStore(tmp_path)
    p = _presupuesto_del_estimador(monkeypatch, tmp_path)
    enlazar = os.link
    ganador = []

    def adelantarse(origen, destino, *args, **kwargs):
        if Path(destino).suffix == ".json" and not ganador:  # el otro escritor publica justo antes
            monkeypatch.setattr(os, "link", enlazar)
            ganador.append(segundo.guardar_modelo(artefacto, contenido))
        return enlazar(origen, destino, *args, **kwargs)
    monkeypatch.setattr(os, "link", adelantarse)
    with pytest.raises(FileExistsError):
        primero.guardar_modelo(artefacto, contenido)
    versiones_publicadas = primero.modelos(JUEGO)
    assert [v.identificador for v in versiones_publicadas] == [artefacto["clave"]]
    assert versiones_publicadas[0].numero == ganador[0].numero == 2  # el 1 lo reservo el primero y lo retiro
    assert primero.reservas_sin_modelo(JUEGO) == [] and primero.temporales() == [] and p.rechazadas == []
    reservas = sorted(x.name for x in (tmp_path / "modelos" / JUEGO).iterdir() if x.suffix == ".version")
    assert reservas == ["random_forest_clasificador-000002.version"]
