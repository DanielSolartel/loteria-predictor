"""Producto 5: publicacion dentro del presupuesto de rutas de Windows.

En Windows sin rutas largas activadas, una ruta de mas de 259 caracteres
(MAX_PATH 260 con el nulo final) falla con `FileNotFoundError` [Errno 2]. El
temporal de la publicacion heredada de Producto 4 (`.<nombre final>.<16
hex>.tmp`) anade 23 caracteres al nombre final: en el primer fallo real, la
carpeta de la linea media 167 caracteres, el destino 240 (cabe) y el temporal
262 (no se pudo crear). Producto 5 publica con un temporal corto de longitud
constante, `.publicacion.<16 hex>.tmp` (33 caracteres), en la misma carpeta.

Estas pruebas SIMULAN ese presupuesto en cualquier sistema; no son una
ejecucion nativa de Windows. Cada ruta del almacen se mide como si la carpeta
de la linea midiera 167 caracteres, y las operaciones que pasan de 259 fallan
como en Windows. Por eso siguen siendo utiles con rutas largas activadas.
Ademas comprueban que:
- un lector ve la ausencia o el contenido completo, nunca un JSON a medias;
- un destino existente, valido o alterado, nunca se sobrescribe y
  `FileExistsError` se propaga;
- un fallo antes de publicar no deja un resultado final y el reintento sigue;
- los temporales con el nombre anterior y con el nuevo se reconocen como
  temporales y nunca se listan como resultados;
- comparaciones, simulaciones y configuraciones se guardan y se releen."""
from __future__ import annotations

import builtins
import errno
import io
import os
import re
from pathlib import Path

import pytest

from app.application.ml.registro_prospectivo import serializar_entrada
from app.infrastructure.storage import carteras_file_store as cfs
from tests.unit import fixtures_producto5 as f5

LIMITE = 259  # MAX_PATH (260) menos el nulo final
CARPETA_DEL_FALLO = 167  # carpeta de la linea en el primer fallo real de Windows
CARTERA = {"modelo": "logistica_regularizada", "perfil": "reducido", "cantidad": 5, "semilla": 42,
           "diversidad": "limitada"}
LINEA = "logistica_regularizada-v1-n5-limitada-s42-reducido"
TEMPORAL_NUEVO = re.compile(r"^\.publicacion\.[0-9a-f]{16}\.tmp$")


class Presupuesto:
    """Mide las rutas bajo `raiz` con un desplazamiento fijo y rechaza, como
    Windows sin rutas largas, las operaciones sobre rutas de mas de 259."""

    def __init__(self, raiz: Path, desplazamiento: int):
        self.raiz, self.desplazamiento = os.path.normpath(str(raiz)), desplazamiento
        self.rechazadas: list[tuple[str, int]] = []
        self.creados: list[Path] = []  # creaciones exclusivas admitidas

    def longitud(self, ruta) -> int | None:
        texto = os.path.normpath(os.fsdecode(os.fspath(ruta)))
        if texto != self.raiz and not texto.startswith(self.raiz + os.sep):
            return None
        return len(texto) + self.desplazamiento

    def comprobar(self, *rutas) -> None:
        for ruta in rutas:
            if isinstance(ruta, int):
                continue
            longitud = self.longitud(ruta)
            if longitud is not None and longitud > LIMITE:
                self.rechazadas.append((Path(ruta).name, longitud))
                raise FileNotFoundError(errno.ENOENT, "No such file or directory", os.fspath(ruta))


def _presupuesto(monkeypatch, raiz: Path, carpeta_de_la_linea: Path) -> Presupuesto:
    p = Presupuesto(raiz, CARPETA_DEL_FALLO - len(os.path.normpath(str(carpeta_de_la_linea))))
    abrir = builtins.open

    def abrir_con_presupuesto(archivo, mode="r", *args, **kwargs):
        p.comprobar(archivo)
        flujo = abrir(archivo, mode, *args, **kwargs)
        if "x" in mode and p.longitud(archivo) is not None:
            p.creados.append(Path(archivo))
        return flujo
    monkeypatch.setattr(builtins, "open", abrir_con_presupuesto)
    monkeypatch.setattr(io, "open", abrir_con_presupuesto)

    def envolver(nombre, posiciones):
        original = getattr(os, nombre)

        def envoltura(*args, **kwargs):
            p.comprobar(*(args[i] for i in posiciones if i < len(args)))
            return original(*args, **kwargs)
        monkeypatch.setattr(os, nombre, envoltura)
    for nombre, posiciones in (("open", (0,)), ("link", (0, 1)), ("mkdir", (0,)), ("rename", (0, 1)),
                               ("replace", (0, 1)), ("unlink", (0,)), ("remove", (0,)), ("rmdir", (0,)),
                               ("stat", (0,)), ("lstat", (0,)), ("scandir", (0,)), ("listdir", (0,))):
        envolver(nombre, posiciones)
    return p


def _temporales_de_resultados(p: Presupuesto, e) -> list[Path]:
    """Temporales creados para publicar resultados (fuera de `operacion`, donde
    el registro de ejecuciones de Producto 3 usa los suyos)."""
    return [t for t in p.creados if t.suffix == ".tmp" and (e.directorio / "operacion") not in t.parents]


def test_cartera_con_el_presupuesto_de_rutas_de_windows(tmp_path, monkeypatch):
    e = f5.entorno(tmp_path, {"MILOTO": 70})
    carpeta = e.almacen._linea("MILOTO", LINEA)
    p = _presupuesto(monkeypatch, tmp_path, carpeta)
    s = e.carteras()
    r = s.ahora("cartera", ["MILOTO"], CARTERA)["juegos"]["MILOTO"]
    assert r["estado"] == "terminado", f5.detalle(r)
    assert p.rechazadas == []
    g = s.cartera(r["resultado"])
    ruta = carpeta / f"{g.objetivo}-{g.identificador}.json"
    # el caso del fallo real: carpeta de 167, destino de 240; el temporal anterior mediria 262
    assert (p.longitud(carpeta), p.longitud(ruta)) == (CARPETA_DEL_FALLO, 240)
    temporales = _temporales_de_resultados(p, e)
    assert [t.parent for t in temporales] == [carpeta]  # misma carpeta (mismo volumen) que el destino
    assert all(TEMPORAL_NUEVO.fullmatch(t.name) and p.longitud(t) == 201 for t in temporales)
    assert ruta.read_bytes() == serializar_entrada(g.artefacto)
    assert e.almacen.temporales() == [] and [x.identificador for x in e.almacen.carteras("MILOTO", LINEA)] == \
        [g.identificador]
    anterior = carpeta / f".{ruta.name}.{'0' * 16}.tmp"  # el nombre que fallaba en Windows
    with pytest.raises(FileNotFoundError):
        open(anterior, "xb")
    assert p.rechazadas == [(anterior.name, 262)] and not anterior.exists()
    otra = s.ahora("cartera", ["MILOTO"], CARTERA)["juegos"]["MILOTO"]
    assert otra["estado"] == "reutilizado" and otra["resultado"] == g.identificador, f5.detalle(otra)


def test_comparacion_simulacion_y_configuracion_con_el_presupuesto(tmp_path, monkeypatch):
    e = f5.entorno(tmp_path, {"MILOTO": 70})
    p = _presupuesto(monkeypatch, tmp_path, e.almacen._linea("MILOTO", LINEA))
    s = e.carteras()
    cartera = s.ahora("cartera", ["MILOTO"], CARTERA)["juegos"]["MILOTO"]
    assert cartera["estado"] == "terminado", f5.detalle(cartera)
    c = s.ahora("comparacion", ["MILOTO"], {"protocolo": {"bloques": 1, "perfil": "reducido"}})["juegos"]["MILOTO"]
    assert c["estado"] == "terminado", f5.detalle(c)
    m = s.ahora("simulacion", ["MILOTO"], {"cartera": cartera["resultado"], "simulaciones": 1000,
                                           "semilla": 3})["juegos"]["MILOTO"]
    assert m["estado"] == "terminado", f5.detalle(m)
    v = s.configurar("MILOTO", "logistica_regularizada", 5, "limitada", 42, perfil="reducido")
    almacen = e.almacen
    for guardado, ruta in ((almacen.obtener_comparacion(c["resultado"]),
                            e.directorio / "comparaciones" / "MILOTO" / f"{c['resultado']}.json"),
                           (almacen.obtener_simulacion(m["resultado"]),
                            e.directorio / "simulaciones" / "MILOTO" / f"{m['resultado']}.json"),
                           (almacen.configuraciones("MILOTO")[0],
                            e.directorio / "configuraciones" / "MILOTO" / "000001.json")):
        assert isinstance(guardado, cfs.Guardado) and ruta.read_bytes() == serializar_entrada(guardado.artefacto)
    assert v.artefacto == almacen.configuraciones("MILOTO")[0].artefacto
    simulada = almacen.obtener_simulacion(m["resultado"]).artefacto
    uniforme = almacen.obtener_cartera(simulada["carteras"]["uniforme"]["clave"])
    assert isinstance(uniforme, cfs.Guardado)  # la cartera uniforme de referencia tambien se publica y relee
    temporales = _temporales_de_resultados(p, e)
    assert len(temporales) == 5 and all(TEMPORAL_NUEVO.fullmatch(t.name) for t in temporales)
    assert p.rechazadas == [] and almacen.temporales() == []


def test_un_lector_ve_la_ausencia_o_el_contenido_completo(tmp_path, monkeypatch):
    carpeta = tmp_path / "carteras" / "MILOTO" / LINEA
    ruta = carpeta / f"71-{'a' * 64}.json"
    contenido = serializar_entrada({"cartera": list(range(200)), "clave": "a" * 64})
    eventos = []
    sincronizar, enlazar = os.fsync, os.link

    def fsync(descriptor):
        eventos.append("fsync")
        return sincronizar(descriptor)

    def link(origen, destino, *args, **kwargs):
        eventos.append("link")
        assert not os.path.exists(destino)  # hasta el enlace, un lector ve la ausencia
        assert Path(origen).parent == carpeta and TEMPORAL_NUEVO.fullmatch(Path(origen).name)
        assert Path(origen).read_bytes() == contenido  # el temporal ya esta completo y sincronizado
        enlazar(origen, destino, *args, **kwargs)
        assert Path(destino).read_bytes() == contenido  # desde el enlace, el contenido completo
    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "link", link)
    cfs._publicar(carpeta, ruta, contenido)
    assert eventos[:2] == ["fsync", "link"]
    assert [x.name for x in carpeta.iterdir()] == [ruta.name] and ruta.read_bytes() == contenido


def test_un_destino_existente_nunca_se_sobrescribe(tmp_path):
    carpeta = tmp_path / "carpeta"
    carpeta.mkdir()
    ruta = carpeta / f"71-{'b' * 64}.json"
    for existente in (b'{"valido":1}\n', b'{"alterado"'):
        ruta.write_bytes(existente)
        reserva = carpeta / "71-000003.secuencia"
        reserva.write_text("b" * 64 + "\n", encoding="ascii")
        with pytest.raises(FileExistsError):
            cfs._publicar(carpeta, ruta, b'{"nuevo":1}\n', reserva)
        assert ruta.read_bytes() == existente  # ni sobrescrito ni truncado
        assert sorted(x.name for x in carpeta.iterdir()) == [ruta.name]  # sin temporal ni reserva propios


def test_un_fallo_antes_de_publicar_no_deja_resultado_y_el_reintento_sigue(tmp_path, monkeypatch):
    e = f5.entorno(tmp_path, {"MILOTO": 70})
    s = e.carteras()

    def sin_enlaces(*args, **kwargs):
        raise PermissionError(errno.EPERM, "Operation not permitted")
    monkeypatch.setattr(os, "link", sin_enlaces)  # sistema de archivos sin enlaces duros
    r = s.ahora("cartera", ["MILOTO"], CARTERA)["juegos"]["MILOTO"]
    # el mensaje del servicio se recorta a 300 caracteres: se comprueba su comienzo
    assert r["estado"] == "fallo" and r["mensaje"].startswith("no se pudo publicar con un enlace duro"), \
        f5.detalle(r)
    carpeta = e.almacen._linea("MILOTO", LINEA)
    assert e.almacen.carteras("MILOTO", LINEA) == [] and e.almacen.temporales() == []
    assert list(carpeta.iterdir()) == []  # ni resultado, ni temporal, ni reserva propios
    monkeypatch.undo()
    r = s.ahora("cartera", ["MILOTO"], CARTERA)["juegos"]["MILOTO"]
    assert r["estado"] == "terminado", f5.detalle(r)
    assert [x.secuencia for x in e.almacen.carteras("MILOTO", LINEA)] == [1]

    # fallo al escribir el temporal: queda un temporal huerfano, reconocido y nunca listado
    destino = carpeta / f"72-{'c' * 64}.json"

    def disco_lleno(descriptor):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(os, "fsync", disco_lleno)
    with pytest.raises(OSError):
        cfs._publicar(carpeta, destino, b'{"completo":1}\n')
    monkeypatch.undo()
    assert not destino.exists()
    huerfanos = e.almacen.temporales()
    assert len(huerfanos) == 1 and TEMPORAL_NUEVO.fullmatch(Path(huerfanos[0]).name)
    assert [x.identificador for x in e.almacen.carteras("MILOTO", LINEA)] == [r["resultado"]]
    cfs._publicar(carpeta, destino, b'{"completo":1}\n')
    assert destino.read_bytes() == b'{"completo":1}\n'


def test_temporales_anteriores_y_nuevos_no_son_resultados(tmp_path):
    e = f5.entorno(tmp_path, {"MILOTO": 70})
    # linea corta: el temporal ANTERIOR de una cartera (94 caracteres) solo cabe en Windows si la carpeta es corta
    corta = {"modelo": "uniforme", "cantidad": 1, "semilla": 1, "diversidad": "libre"}
    r = e.carteras().ahora("cartera", ["MILOTO"], corta)["juegos"]["MILOTO"]
    assert r["estado"] == "terminado", f5.detalle(r)
    almacen = e.almacen
    linea = almacen.lineas("MILOTO")[0]
    creados = []
    for carpeta, final in ((almacen._linea("MILOTO", linea), f"71-{'f' * 64}.json"),
                           (e.directorio / "comparaciones" / "MILOTO", f"{'f' * 64}.json"),
                           (e.directorio / "simulaciones" / "MILOTO", f"{'f' * 64}.json"),
                           (e.directorio / "configuraciones" / "MILOTO", "000001.json")):
        carpeta.mkdir(parents=True, exist_ok=True)
        for nombre in (f".{final}.0123456789abcdef.tmp", ".publicacion.fedcba9876543210.tmp"):
            (carpeta / nombre).write_bytes(b'{"a medio')
            creados.append(str((carpeta / nombre).relative_to(e.directorio)))
    assert almacen.temporales() == sorted(creados)
    assert [x.identificador for x in almacen.carteras("MILOTO", linea)] == [r["resultado"]]
    assert almacen.comparaciones("MILOTO") == [] and almacen.simulaciones("MILOTO") == []
    assert almacen.configuraciones("MILOTO") == []
    assert almacen.obtener_cartera("f" * 64) is None and almacen.obtener_comparacion("f" * 64) is None
    assert almacen.obtener_simulacion("f" * 64) is None
