"""Producto 1: orden de emision persistente de las versiones de un mismo
objetivo (regresion de la validacion Windows: con el mismo reloj, el
SHA-256 decidia el orden).

Las versiones se crean de forma que sus claves queden en orden
DESCENDENTE, el contrario al de creacion: ordenar por fecha y luego por
clave las numera al reves. El orden debe salir de la secuencia sellada en
cada artefacto, nunca del nombre, de `iterdir()` ni de fechas del sistema
de archivos. Historicos sinteticos."""
from __future__ import annotations

import dataclasses
import json
import re
import shutil
from datetime import datetime, timezone

import pytest

from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado, PronosticoIlegible
from app.application.ml import pronostico_experimental as pe
from app.application.use_cases.pronostico_experimental import (
    ConsultarPronosticosExperimentales,
    GenerarPronosticoExperimental,
)
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx

CONFIG = pe.ConfiguracionExperimental(tamano_bloque=10, bloques_de_evaluacion=2, minimo_objetivos_de_entrenamiento=40)
MISMO_RELOJ = lambda: datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)  # noqa: E731


def _clave(historico):
    return pe.clave_de_entrada(historico, codigo_juego="BALOTO", rango_min=1, rango_max=43, cantidad_numeros=5,
                               rango_superbalota=(1, 16), configuracion=CONFIG)


def _historicos_en_orden_descendente_de_clave(base, cantidad=3):
    """Variantes del historico (una correccion distinta cada una) cuyas
    claves, en orden de creacion, quedan en orden lexicografico
    descendente."""
    candidatos = [base]
    for i in range(1, 40):
        corregido = dataclasses.replace(base[i], numeros=tuple(sorted({1, 2, 3, 4, (i % 38) + 5})))
        candidatos.append([*base[:i], corregido, *base[i + 1:]])
    ordenados = sorted(candidatos, key=_clave, reverse=True)
    paso = len(ordenados) // cantidad
    elegidos = [ordenados[k * paso] for k in range(cantidad)]
    claves = [_clave(h) for h in elegidos]
    assert claves == sorted(claves, reverse=True) and len(set(claves)) == cantidad
    return elegidos


@pytest.fixture
def entorno(tmp_path):
    base = fx.historico_numerico("BALOTO", 130)
    juegos, resultados, colores = fx.repositorios({"BALOTO": base}, colorloto=[])
    almacen = PronosticoExperimentalFileStore(tmp_path / "pronosticos")
    return juegos, resultados, colores, almacen, base


def _emitir(entorno, historico):
    juegos, resultados, _, almacen, _ = entorno
    resultados.numericos[juegos.obtener_por_codigo("BALOTO").id] = historico
    return GenerarPronosticoExperimental(juegos, resultados, almacen, reloj=MISMO_RELOJ,
                                         configuracion=CONFIG).ejecutar("BALOTO")


def _versiones(almacen):
    return [(g.identificador, g.version, g.versiones)
            for g in ConsultarPronosticosExperimentales(almacen).resumen("BALOTO").guardados]


def test_tres_versiones_con_la_misma_fecha_siguen_el_orden_de_emision(entorno):
    h1, h2, h3 = _historicos_en_orden_descendente_de_clave(entorno[4])
    v1, v2, v3 = (_emitir(entorno, h) for h in (h1, h2, h3))
    assert {v.artefacto["generacion"]["generado_en"] for v in (v1, v2, v3)} == {"2026-10-01T12:00:00+00:00"}
    assert v1.identificador > v2.identificador > v3.identificador
    assert _versiones(entorno[3]) == [(v3.identificador, 3, 3), (v2.identificador, 2, 3), (v1.identificador, 1, 3)]
    assert [v.artefacto["generacion"]["secuencia_en_el_objetivo"] for v in (v1, v2, v3)] == [1, 2, 3]
    assert v1.artefacto["generacion"]["version_anterior"] is None
    assert v2.artefacto["generacion"]["version_anterior"] == v1.identificador
    assert v3.artefacto["generacion"]["version_anterior"] == v2.identificador
    assert all(pe.artefacto_integro(v.artefacto) for v in (v1, v2, v3))


def test_repetir_una_entrada_anterior_devuelve_su_version_sin_crear_otra(entorno):
    h1, h2, _ = _historicos_en_orden_descendente_de_clave(entorno[4])
    v1 = _emitir(entorno, h1)
    v2 = _emitir(entorno, h2)
    otra_vez = _emitir(entorno, h1)
    assert otra_vez.reutilizado is True and otra_vez.identificador == v1.identificador
    assert otra_vez.version == 1 and otra_vez.versiones == 2
    assert otra_vez.artefacto == v1.artefacto
    assert len(list(entorno[3]._carpeta("BALOTO").glob("*.json"))) == 2
    assert _versiones(entorno[3])[0] == (v2.identificador, 2, 2)


def test_la_correccion_no_reescribe_la_version_anterior(entorno):
    h1, h2, _ = _historicos_en_orden_descendente_de_clave(entorno[4])
    v1 = _emitir(entorno, h1)
    carpeta = entorno[3]._carpeta("BALOTO")
    antes = {p.name: p.read_bytes() for p in carpeta.iterdir()}
    _emitir(entorno, h2)
    for nombre, contenido in antes.items():
        assert (carpeta / nombre).read_bytes() == contenido
    assert entorno[3].obtener("BALOTO", v1.identificador).artefacto == v1.artefacto


def test_el_orden_se_conserva_al_reconstruir_el_almacen(entorno, tmp_path):
    h1, h2, h3 = _historicos_en_orden_descendente_de_clave(entorno[4])
    esperado = [v.identificador for v in reversed([_emitir(entorno, h) for h in (h1, h2, h3)])]
    origen = entorno[3]._carpeta("BALOTO")
    for nombre_destino, orden in (("inverso", True), ("directo", False)):
        destino = tmp_path / nombre_destino / "BALOTO"
        destino.mkdir(parents=True)
        for ruta in sorted(origen.iterdir(), key=lambda p: p.name, reverse=orden):
            shutil.copyfile(ruta, destino / ruta.name)  # fechas de archivo nuevas y en otro orden
        reconstruido = PronosticoExperimentalFileStore(tmp_path / nombre_destino)
        assert [i for i, _, _ in _versiones(reconstruido)] == esperado
    # Solo con los JSON (sin las reservas) el orden sigue saliendo del contenido sellado.
    solo_json = tmp_path / "solo_json" / "BALOTO"
    solo_json.mkdir(parents=True)
    for ruta in origen.glob("*.json"):
        shutil.copyfile(ruta, solo_json / ruta.name)
    assert [i for i, _, _ in _versiones(PronosticoExperimentalFileStore(tmp_path / "solo_json"))] == esperado


def test_alterar_la_secuencia_rompe_el_sello(entorno):
    h1, h2, _ = _historicos_en_orden_descendente_de_clave(entorno[4])
    _emitir(entorno, h1)
    v2 = _emitir(entorno, h2)
    ruta = next(entorno[3]._carpeta("BALOTO").glob(f"*-{v2.identificador}.json"))
    datos = json.loads(ruta.read_bytes())
    datos["generacion"]["secuencia_en_el_objetivo"] = 1
    ruta.write_bytes(json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode() + b"\n")
    assert isinstance(entorno[3].obtener("BALOTO", v2.identificador), PronosticoIlegible)


def test_reserva_ajena_de_la_secuencia_se_detecta(entorno):
    h1, h2, _ = _historicos_en_orden_descendente_de_clave(entorno[4])
    _emitir(entorno, h1)
    v2 = _emitir(entorno, h2)
    reserva = next(entorno[3]._carpeta("BALOTO").glob("*-000002.secuencia"))
    reserva.write_text("0" * 64 + "\n", encoding="ascii")
    elemento = entorno[3].obtener("BALOTO", v2.identificador)
    assert isinstance(elemento, PronosticoIlegible) and elemento.motivo == "secuencia_reservada_por_otra_clave"


def test_reserva_huerfana_no_desordena_las_versiones(entorno):
    """Si un proceso murio tras reservar la secuencia 2 sin escribir el
    artefacto, la siguiente version toma la 3 y sigue siendo la 2.a."""
    h1, h2, _ = _historicos_en_orden_descendente_de_clave(entorno[4])
    v1 = _emitir(entorno, h1)
    carpeta = entorno[3]._carpeta("BALOTO")
    objetivo = v1.artefacto["pronostico"]["objetivo"]
    (carpeta / f"{objetivo}-000002.secuencia").write_text("f" * 64 + "\n", encoding="ascii")
    v2 = _emitir(entorno, h2)
    assert v2.artefacto["generacion"]["secuencia_en_el_objetivo"] == 3
    assert _versiones(entorno[3]) == [(v2.identificador, 2, 2), (v1.identificador, 1, 2)]


def test_carrera_con_la_misma_clave_no_duplica_ni_deja_reservas(entorno):
    """Dos escritores con la misma entrada: el segundo `guardar` falla con
    FileExistsError y libera su reserva de secuencia."""
    juegos, resultados, _, almacen, base = entorno
    v1 = _emitir(entorno, base)
    cuerpo = pe.cuerpo_del_artefacto(v1.artefacto)
    otro = pe.componer_artefacto(cuerpo, generado_en="2026-10-02T00:00:00+00:00")
    with pytest.raises(FileExistsError):
        almacen.guardar("BALOTO", otro)
    carpeta = almacen._carpeta("BALOTO")
    assert sorted(re.sub(r"[0-9a-f]{64}", "H", p.name) for p in carpeta.iterdir()) == [
        f"{v1.artefacto['pronostico']['objetivo']}-000001.secuencia", f"{v1.artefacto['pronostico']['objetivo']}-H.json"]


def test_pagina_web_numera_por_secuencia(entorno):
    h1, h2, h3 = _historicos_en_orden_descendente_de_clave(entorno[4])
    v = [_emitir(entorno, h) for h in (h1, h2, h3)]
    juegos, resultados, colores, almacen, _ = entorno
    c = fx.cliente(juegos, resultados, colores, almacen, reloj=MISMO_RELOJ, configuracion=CONFIG,
                   client=("127.0.0.1", 50000))
    try:
        for i, g in enumerate(v, start=1):
            assert f"versión {i} de 3" in c.get(f"/pronosticos/baloto?id={g.identificador}").text.lower()
        assert "versión 3 de 3" in c.get("/pronosticos/baloto").text.lower()
    finally:
        from app.main import app
        app.dependency_overrides = {}


def test_resultado_es_pronostico_guardado(entorno):
    assert isinstance(_emitir(entorno, entorno[4]), PronosticoGuardado)


def test_artefacto_previo_sin_secuencia_sigue_siendo_la_version_1(entorno):
    """Artefactos generados con el parche anterior (sin secuencia) se
    conservan y quedan antes de cualquier version nueva del objetivo."""
    from app.application.ml.registro_prospectivo import serializar_entrada
    h1, h2, _ = _historicos_en_orden_descendente_de_clave(entorno[4])
    juegos, resultados, _, almacen, _ = entorno
    resultados.numericos[juegos.obtener_por_codigo("BALOTO").id] = h1
    from app.application.use_cases import pronostico_experimental as uc
    cuerpo = uc._cuerpo("BALOTO", h1, None, CONFIG)
    previo = pe.componer_artefacto(cuerpo, generado_en="2026-10-01T12:00:00+00:00")
    assert "secuencia_en_el_objetivo" not in previo["generacion"]
    carpeta = almacen._carpeta("BALOTO")
    carpeta.mkdir(parents=True)
    (carpeta / f"{previo['pronostico']['objetivo']}-{previo['clave_de_entrada']}.json").write_bytes(
        serializar_entrada(previo))
    assert _emitir(entorno, h1).reutilizado is True
    v2 = _emitir(entorno, h2)
    assert v2.artefacto["generacion"]["secuencia_en_el_objetivo"] == 2
    assert v2.artefacto["generacion"]["version_anterior"] == previo["clave_de_entrada"]
    assert _versiones(almacen) == [(v2.identificador, 2, 2), (previo["clave_de_entrada"], 1, 2)]


def test_escritores_concurrentes_obtienen_secuencias_distintas(entorno):
    import threading
    _, _, _, almacen, base = entorno
    from app.application.use_cases import pronostico_experimental as uc
    cuerpo = uc._cuerpo("BALOTO", base, None, CONFIG)
    artefactos = [pe.componer_artefacto({**cuerpo, "clave_de_entrada": f"{i:064x}"},
                                        generado_en="2026-10-01T12:00:00+00:00") for i in range(1, 9)]
    barrera = threading.Barrier(len(artefactos))
    errores = []

    def escribir(a):
        barrera.wait()
        try:
            almacen.guardar("BALOTO", a)
        except Exception as error:  # pragma: no cover - se informa abajo
            errores.append(error)

    hilos = [threading.Thread(target=escribir, args=(a,)) for a in artefactos]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == []
    guardados = ConsultarPronosticosExperimentales(almacen).resumen("BALOTO").guardados
    secuencias = sorted(g.artefacto["generacion"]["secuencia_en_el_objetivo"] for g in guardados)
    assert len(guardados) == 8 and secuencias == list(range(1, 9))
    assert sorted(g.version for g in guardados) == list(range(1, 9))
