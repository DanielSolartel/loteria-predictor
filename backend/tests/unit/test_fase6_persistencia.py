"""Persistencia operativa real, aislada; no usa BD, proveedor o modelos reales."""
from __future__ import annotations

import hashlib
import json
import multiprocessing
import time
from pathlib import Path

import pytest

from tests.unit.fixtures_tiempo_fase6 import fijar_marca

from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
from app.infrastructure.storage import automatizacion_file_store as modulo
from tests.unit.test_producto5_rutas import _presupuesto

ID = "20261020T120000Z-01234567"
ID2 = "20261020T120000Z-89abcdef"
CLAVE = "a" * 64


def _revision():
    return {"clave": CLAVE, "juego": "COLORLOTO", "numero_sorteo": 223,
            "antes": {"pares": [[1, "AZUL"]] * 6},
            "propuesta": {"pares": [[2, "VERDE"]] * 6},
            "huellas": {"antes": "b" * 64, "propuesta": "c" * 64}, "estado": "pendiente"}


def _escribir(ruta, listo, empezar, cola, campo, base):
    try:
        a = AlmacenAutomatizacion(ruta)
        listo.set()
        assert empezar.wait(15)
        a.actualizar_configuracion({campo: True})
        for i in range(base, base + 30):
            a.guardar_estado("BALOTO", {"revision": i, "valores": [i] * 128, "texto": "ñ 😀"})
        cola.put(("ok", campo))
    except BaseException as e:
        cola.put(("error", repr(e)))
        raise


def _revision_concurrente(ruta, listo, empezar, cola):
    try:
        a = AlmacenAutomatizacion(ruta)
        listo.set()
        assert empezar.wait(15)
        r = a.guardar_revision(_revision())
        cola.put(hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest())
    except BaseException as e:
        cola.put(("error", repr(e)))
        raise


def _ciclo_interrumpido(ruta, listo, terminar):
    a = AlmacenAutomatizacion(ruta)
    cerrojos = a.adquirir(["BALOTO"], ID)
    assert not isinstance(cerrojos, dict)
    try:
        a.guardar_ejecucion({"id": ID, "estado": "en_curso", "pasos": [{"paso": "sincronizado"}]})
        listo.set()
        assert terminar.wait(30)
    finally:
        cerrojos.liberar()


def _terminar(procesos):
    for p in procesos:
        if p.is_alive():
            p.terminate()
        p.join(10)


def test_las_lecturas_no_crean_el_almacen_ni_cerrojos(tmp_path):
    ruta = tmp_path / "ausente"
    a = AlmacenAutomatizacion(ruta)
    c = a.configuracion()
    assert c["activada"] is False and c["pausada"] is True
    assert len(c["juegos"]) == 4 and c["politica"]["max_paginas"] == 3
    assert a.estado("MILOTO") == {"juego": "MILOTO", "estado": "sin_comprobar"}
    assert a.obtener_ejecucion(ID) is None and a.recientes() == []
    assert a.revision(CLAVE) is None and a.revisiones() == []
    assert a.decisiones_revision(CLAVE) == []
    assert not a.viva(ID) and a.activa("BALOTO") is None
    assert not ruta.exists()
    c["politica"]["max_paginas"] = 99
    assert a.configuracion()["politica"]["max_paginas"] == 3


def test_dos_escritores_y_lector_ven_estados_completos_y_no_pierden_flags(tmp_path):
    a = AlmacenAutomatizacion(tmp_path / "a")
    a.guardar_configuracion({"activada": False, "pausada": False})
    a.guardar_estado("BALOTO", {"revision": -1, "valores": [-1] * 128, "texto": "ñ 😀"})
    ctx = multiprocessing.get_context("spawn")
    empezar, cola = ctx.Event(), ctx.Queue()
    listos = [ctx.Event(), ctx.Event()]
    ps = [ctx.Process(target=_escribir, args=(str(a.directorio), listos[i], empezar, cola, campo, i * 100))
          for i, campo in enumerate(("activada", "pausada"))]
    try:
        for p in ps:
            p.start()
        assert all(e.wait(15) for e in listos)
        empezar.set()
        lecturas = 0
        limite = time.monotonic() + 20
        while any(p.is_alive() for p in ps) or lecturas < 10:
            assert time.monotonic() < limite
            e = a.estado("BALOTO")
            assert e["valores"] == [e["revision"]] * 128 and e["texto"] == "ñ 😀"
            lecturas += 1
        for p in ps:
            p.join(10)
            assert p.exitcode == 0
        assert {cola.get(timeout=5) for _ in ps} == {("ok", "activada"), ("ok", "pausada")}
        assert a.configuracion()["activada"] is True and a.configuracion()["pausada"] is True
        assert lecturas >= 10
        assert not list(a.directorio.rglob(".a-*.tmp"))
    finally:
        _terminar(ps)


def test_revision_duplicada_real_y_decisiones_inmutables(tmp_path):
    a = AlmacenAutomatizacion(tmp_path / "a")
    ctx = multiprocessing.get_context("spawn")
    empezar, cola = ctx.Event(), ctx.Queue()
    listos = [ctx.Event(), ctx.Event()]
    ps = [ctx.Process(target=_revision_concurrente, args=(str(a.directorio), listos[i], empezar, cola)) for i in range(2)]
    try:
        for p in ps:
            p.start()
        assert all(e.wait(15) for e in listos)
        empezar.set()
        for p in ps:
            p.join(15)
            assert p.exitcode == 0
        assert cola.get(timeout=5) == cola.get(timeout=5)
    finally:
        _terminar(ps)
    ruta = a.directorio / "r" / (CLAVE + ".json")
    original = ruta.read_bytes()
    assert len(list((a.directorio / "r").glob("*.json"))) == 1
    with pytest.raises(ValueError, match="No se sobrescribe"):
        a.guardar_revision({**_revision(), "propuesta": {"pares": [[3, "ROJO"]] * 6}})
    d1 = a.guardar_decision_revision(CLAVE, {"estado": "rechazada", "motivo": "fuente no confirmada"})
    assert a.guardar_decision_revision(CLAVE, {"estado": "rechazada", "motivo": "fuente no confirmada"}) == d1
    d2 = a.guardar_decision_revision(CLAVE, {"estado": "aceptada", "motivo": "revisión explícita posterior"})
    assert d1["clave"] != d2["clave"] and len(a.decisiones_revision(CLAVE)) == 2
    assert ruta.read_bytes() == original and a.revision(CLAVE)["estado"] == "pendiente"
    assert a.revisiones() == [_revision()]


def test_terminar_proceso_libera_cerrojo_sin_promover_estado_interrumpido(tmp_path):
    a = AlmacenAutomatizacion(tmp_path / "a")
    ctx = multiprocessing.get_context("spawn")
    listo, terminar = ctx.Event(), ctx.Event()
    p = ctx.Process(target=_ciclo_interrumpido, args=(str(a.directorio), listo, terminar))
    try:
        p.start()
        assert listo.wait(15)
        assert a.viva(ID)
        assert a.adquirir(["BALOTO"], ID2) == {"BALOTO": ID}
        antes = a.obtener_ejecucion(ID)
        p.terminate()
        p.join(10)
        assert not p.is_alive() and not a.viva(ID)
        assert a.obtener_ejecucion(ID) == antes
        assert antes["estado"] == "en_curso" and antes["pasos"] == [{"paso": "sincronizado"}]
        reserva = a.adquirir(["BALOTO"], ID2)
        assert not isinstance(reserva, dict)
        reserva.liberar()
    finally:
        _terminar([p])


def test_fallo_de_publicacion_conserva_anterior_y_temporales_historicos(tmp_path, monkeypatch):
    a = AlmacenAutomatizacion(tmp_path / "a")
    a.guardar_estado("MILOTO", {"estado": "correcto", "texto": "ñ 😀"})
    p = a.directorio / "e/MILOTO.json"
    original = p.read_bytes()
    historico = p.parent / ".a-historico.tmp"
    historico.write_bytes(b"historico intocable")
    def fallar(*_):
        raise OSError("fallo de publicación deliberado")
    monkeypatch.setattr(modulo.ofs, "_publicar_temporal", fallar)
    with pytest.raises(OSError, match="fallo de publicación"):
        a.guardar_estado("MILOTO", {"estado": "nuevo"})
    assert p.read_bytes() == original and historico.read_bytes() == b"historico intocable"
    assert [q.name for q in p.parent.glob("*.tmp")] == [historico.name]


def test_presupuesto_portable_windows_incluye_utf16_y_rutas_con_espacios(tmp_path, monkeypatch):
    # Presupuesto portable, no ejecución nativa Windows. Root sintética de
    # 167 UTF-16 chars y nombres físicos acotados incluso para decisiones.
    raiz = tmp_path / "datos con espacios 😀"
    p = _presupuesto(monkeypatch, raiz, raiz)
    raiz_texto = str(raiz)
    def longitud(ruta):
        import os
        if isinstance(ruta, int):
            return None
        s = os.path.normpath(os.fsdecode(os.fspath(ruta)))
        if s != raiz_texto and not s.startswith(raiz_texto + os.sep):
            return None
        return 167 + len(s[len(raiz_texto):].encode("utf-16-le")) // 2
    p.longitud = longitud
    a = AlmacenAutomatizacion(raiz)
    a.guardar_configuracion({"activada": True, "pausada": False})
    a.guardar_estado("COLORLOTO", {"estado": "pendiente", "texto": "Unicode BMP ñ y no BMP 😀"})
    a.guardar_ejecucion({"id": ID, "estado": "en_curso"})
    a.guardar_revision(_revision())
    a.guardar_decision_revision(CLAVE, {"estado": "rechazada"})
    cerrojos = a.adquirir(["BALOTO_REVANCHA"], ID)
    assert not isinstance(cerrojos, dict)
    assert a.viva(ID)
    cerrojos.liberar()
    assert a.estado("COLORLOTO")["texto"].endswith("😀")
    assert p.rechazadas == [] and p.creados
    assert max(p.longitud(q) for q in raiz.rglob("*")) <= 259


@pytest.mark.parametrize("conf", [
    {"activada": "true"}, {"pausada": 0}, {"version": 2}, {"juegos": ["OTRO"]},
    {"juegos": ["BALOTO", "BALOTO"]}, {"juegos": [{}]}, {"modelo": "elegido_silencioso"},
    {"politica": {"max_paginas": 1000}}, {"database_url": "no almacenar"},
    {"politica": {"reintento_inicial_segundos": float("nan")}},
])
def test_configuraciones_ajenas_o_no_finitas_se_rechazan_antes_de_escribir(tmp_path, conf):
    raiz = tmp_path / "ausente"
    with pytest.raises(ValueError):
        AlmacenAutomatizacion(raiz).guardar_configuracion(conf)
    assert not raiz.exists()


def test_ids_rutas_y_contenido_corrupto_no_se_aceptan_silenciosamente(tmp_path):
    a = AlmacenAutomatizacion(tmp_path / "a")
    with pytest.raises(ValueError):
        a.estado("../BALOTO")
    with pytest.raises(ValueError):
        a.revision("../revision")
    with pytest.raises(ValueError):
        a.guardar_ejecucion({"id": 1, "estado": "en_curso"})
    assert a.obtener_ejecucion(1) is None and not a.viva(1)
    assert not a.directorio.exists()
    a.guardar_estado("BALOTO", {"estado": "correcto"})
    (a.directorio / "e/BALOTO.json").write_bytes(b'{"estado": NaN}')
    with pytest.raises(ValueError, match="ilegible"):
        a.estado("BALOTO")


def test_actualizacion_parcial_de_politica_conserva_otros_limites(tmp_path):
    a = AlmacenAutomatizacion(tmp_path / "a")
    a.guardar_configuracion({"politica": {"reconciliar_ultimos": 25}})
    a.actualizar_configuracion({"politica": {"max_paginas": 4}})
    assert a.configuracion()["politica"]["reconciliar_ultimos"] == 25
    assert a.configuracion()["politica"]["max_paginas"] == 4


def test_decisiones_antiguas_se_filtran_por_revision_antes_de_limitar(tmp_path):
    """Otras revisiones no pueden borrar de la consulta una decisión tomada."""
    import os

    a = AlmacenAutomatizacion(tmp_path / "a")
    a.guardar_revision(_revision())
    primera = a.guardar_decision_revision(CLAVE, {"estado": "rechazada", "nota": "primera revisión"})
    segunda = a.guardar_decision_revision(CLAVE, {"estado": "aceptada", "nota": "revisión posterior"})
    otra = "b" * 64
    a.guardar_revision({**_revision(), "clave": otra, "numero_sorteo": 224})
    # Orden explícito representable y verificado al releer el FS.
    for i, d in enumerate((primera, segunda), start=1):
        fijar_marca(a.directorio / "d" / (d["clave"] + ".json"), i)
    for i in range(105):
        d = a.guardar_decision_revision(otra, {"estado": "rechazada", "nota": str(i)})
        fijar_marca(a.directorio / "d" / (d["clave"] + ".json"), 100 + i)
    antes = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in a.directorio.rglob("*.json")}
    reiniciada = AlmacenAutomatizacion(a.directorio)
    decisiones = reiniciada.decisiones_revision(CLAVE)
    assert decisiones == [{"revision": CLAVE, "decision": segunda["decision"]},
                           {"revision": CLAVE, "decision": primera["decision"]}]
    assert reiniciada.decisiones_revision(CLAVE, limite=1) == decisiones[:1]
    assert len(reiniciada.decisiones_revision(otra)) == 100
    assert {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in a.directorio.rglob("*.json")} == antes
