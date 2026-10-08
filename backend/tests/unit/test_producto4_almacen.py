"""Producto 4: identidad, idempotencia, reproduccion y almacen del
laboratorio (escritura atomica, carreras entre procesos reales, temporales,
orden de emision y recuperacion de una ejecucion interrumpida)."""
from __future__ import annotations

import json
import multiprocessing
import pathlib

import pytest

from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.use_cases.laboratorio import LaboratorioError
from app.infrastructure.storage.laboratorio_file_store import Guardado, Ilegible, LaboratorioFileStore
from tests.unit import fixtures_producto4 as f4

REDUCIDO = le.Protocolo(bloques=1, perfil="reducido")
ESPERA = 60


@pytest.fixture
def entorno(tmp_path):
    return f4.entorno(tmp_path)


def _experimento(lab, juego="MILOTO", protocolo=REDUCIDO, corte=None):
    r = lab.comparar_ahora([juego], protocolo, corte=corte)["juegos"][juego]
    assert r["estado"] in ("terminado", "reutilizado", "parcial"), r
    return r["experimento"]


def _ruta_experimento(e, juego, clave):
    return e.directorio / "experimentos" / juego / f"{clave}.json"


def test_repetir_la_misma_entrada_reutiliza_sin_reentrenar(entorno, monkeypatch):
    lab = entorno.laboratorio()
    clave = _experimento(lab)
    antes = _ruta_experimento(entorno, "MILOTO", clave).read_bytes()
    monkeypatch.setattr(le, "evaluar", lambda *a, **k: pytest.fail("no debe reentrenar"))
    r = lab.comparar_ahora(["MILOTO"], REDUCIDO)["juegos"]["MILOTO"]
    assert r["estado"] == "reutilizado" and r["experimento"] == clave
    assert _ruta_experimento(entorno, "MILOTO", clave).read_bytes() == antes
    monkeypatch.undo()
    g1 = lab.generar(clave, "hgb_clasificador")
    g2 = lab.generar(clave, "hgb_clasificador")
    assert g2.reutilizado and g2.identificador == g1.identificador and g2.artefacto == g1.artefacto


def test_cambiar_modelo_receta_corte_semilla_o_historico_cambia_la_identidad(entorno, monkeypatch):
    lab = entorno.laboratorio()
    base = _experimento(lab)
    informe = lab.experimento(base).artefacto
    claves = {base}
    claves.add(_experimento(lab, protocolo=le.Protocolo(bloques=1)))            # receta: perfil predeterminado
    claves.add(_experimento(lab, protocolo=le.Protocolo(bloques=2, perfil="reducido")))  # protocolo
    corte = entorno.cargados("MILOTO")[-2].numero_sorteo
    claves.add(_experimento(lab, corte=corte))                                  # corte
    monkeypatch.setattr(lm, "SEMILLA", 7)
    from app.application.ml import laboratorio_variables as lv
    instantanea = lv.validar_instantanea("MILOTO", entorno.cargados("MILOTO"))
    assert la.clave_del_experimento(la.identidad_del_experimento(
        instantanea, lm.candidatos_del_juego("MILOTO"), REDUCIDO)) != base       # semilla
    monkeypatch.undo()
    pronosticos = {la.huella(la.identidad_del_pronostico(informe, lm.CATALOGO[m]))
                   for m in ("logistica_regularizada", "hgb_clasificador", "actual_frecuencia_contraida")}
    assert len(pronosticos) == 3                                                 # modelo
    bytes_antes = _ruta_experimento(entorno, "MILOTO", base).read_bytes()
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    claves.add(_experimento(lab))                                                # historico
    assert len(claves) == 5
    assert _ruta_experimento(entorno, "MILOTO", base).read_bytes() == bytes_antes  # el anterior se conserva


def test_reproduccion_integridad_y_coincidencia_son_comprobaciones_distintas(entorno):
    lab = entorno.laboratorio()
    clave = _experimento(lab)
    v = lab.verificar_experimento(clave)
    assert v["integridad"] == "correcta" and v["reproduccion"]["huella_exacta"] is True
    assert v["base_actual"]["historico_hasta_el_corte"] == "coincide" and v["mismo_entorno"] is True
    corregido = entorno.cargados("MILOTO")
    juego = entorno.juegos.obtener_por_codigo("MILOTO")
    entorno.resultados.numericos[juego.id] = [*corregido[:10], corregido[10].__class__(
        corregido[10].numero_sorteo, corregido[10].fecha, corregido[10].dia_semana, (1, 2, 3, 4, 6), None),
        *corregido[11:]]
    v = lab.verificar_experimento(clave)  # la instantanea se reproduce, pero la base cambio
    assert v["reproduccion"]["huella_exacta"] is True and v["base_actual"]["historico_hasta_el_corte"] == "cambio"
    ruta = _ruta_experimento(entorno, "MILOTO", clave)
    datos = json.loads(ruta.read_bytes())
    datos["resumen"]["estado"] = "menor_perdida_en_esta_evaluacion"
    ruta.write_bytes(json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    assert lab.verificar_experimento(clave)["integridad"] == "alterado"
    with pytest.raises(LaboratorioError) as error:
        lab.generar(clave, "hgb_clasificador")
    assert error.value.codigo == "alterado"
    r = lab.comparar_ahora(["MILOTO"], REDUCIDO)["juegos"]["MILOTO"]  # el historico corregido: otra identidad
    assert r["experimento"] != clave and r["estado"] == "terminado"


def test_un_informe_alterado_con_la_misma_identidad_no_se_sobrescribe(entorno):
    lab = entorno.laboratorio()
    clave = _experimento(lab)
    ruta = _ruta_experimento(entorno, "MILOTO", clave)
    ruta.write_bytes(ruta.read_bytes().replace(b'"resumen"', b'"resumen" '))
    alterado = ruta.read_bytes()
    r = lab.comparar_ahora(["MILOTO"], REDUCIDO)["juegos"]["MILOTO"]
    assert r["estado"] == "fallo" and "no se sobrescribe" in r["mensaje"]
    assert ruta.read_bytes() == alterado
    assert isinstance(entorno.almacen.experimentos("MILOTO")[0], Ilegible)


def test_temporales_y_reservas_huerfanas_no_son_resultados(entorno):
    lab = entorno.laboratorio()
    clave = _experimento(lab)
    carpeta = _ruta_experimento(entorno, "MILOTO", clave).parent
    (carpeta / f".{'f' * 64}.json.0123456789abcdef.tmp").write_bytes(b'{"a medio')
    g = lab.generar(clave, "logistica_regularizada")
    linea = entorno.directorio / "pronosticos" / "MILOTO" / g.linea
    (linea / f"{g.objetivo}-000009.secuencia").write_text("e" * 64 + "\n")
    almacen = entorno.almacen
    assert [e.identificador for e in almacen.experimentos("MILOTO")] == [clave]
    assert len(almacen.temporales()) == 1
    assert [e.identificador for e in almacen.pronosticos("MILOTO", g.linea)] == [g.identificador]
    assert almacen.obtener_experimento("f" * 64) is None


def test_orden_de_emision_por_linea_y_objetivo_con_secuencia_sellada(entorno):
    lab = entorno.laboratorio()
    a = _experimento(lab)
    juego = entorno.juegos.obtener_por_codigo("MILOTO")
    sorteos = entorno.cargados("MILOTO")
    # el mismo objetivo con otro historico: una version posterior de la misma linea
    entorno.resultados.numericos[juego.id] = [*sorteos[:5], sorteos[5].__class__(
        sorteos[5].numero_sorteo, sorteos[5].fecha, sorteos[5].dia_semana, (2, 3, 4, 5, 6), None), *sorteos[6:]]
    b = _experimento(lab)
    g1 = lab.generar(a, "logistica_regularizada")
    g2 = lab.generar(b, "logistica_regularizada")
    assert g1.objetivo == g2.objetivo and g1.linea == g2.linea
    assert (g1.secuencia, g2.secuencia) == (1, 2)
    assert g2.artefacto["generacion"]["version_anterior"] == g1.identificador
    listado = entorno.almacen.pronosticos("MILOTO", g1.linea)
    assert [(e.identificador, e.version, e.versiones) for e in listado] == [
        (g2.identificador, 2, 2), (g1.identificador, 1, 2)]
    otra = lab.generar(a, "hgb_clasificador")
    assert otra.linea != g1.linea and otra.secuencia == 1  # otra linea: su propia secuencia


def _guardar_en_proceso(directorio, ruta_artefacto, tipo, barrera, cola):
    almacen = LaboratorioFileStore(directorio)
    artefacto = json.loads(pathlib.Path(ruta_artefacto).read_text(encoding="utf-8"))
    barrera.wait(ESPERA)
    try:
        g = almacen.guardar_experimento(artefacto) if tipo == "experimento" else almacen.guardar_pronostico(artefacto)
        cola.put(("ok", g.identificador, g.secuencia))
    except FileExistsError:
        cola.put(("existe", None, None))


def _carrera(directorio, rutas, tipo):
    contexto = multiprocessing.get_context("spawn")
    barrera, cola = contexto.Barrier(len(rutas)), contexto.Queue()
    procesos = [contexto.Process(target=_guardar_en_proceso, args=(str(directorio), str(r), tipo, barrera, cola))
                for r in rutas]
    for p in procesos:
        p.start()
    resultados = [cola.get(timeout=ESPERA) for _ in procesos]
    for p in procesos:
        p.join(ESPERA)
    return sorted(resultados, key=str)


def test_carreras_entre_procesos_reales(entorno, tmp_path):
    lab = entorno.laboratorio()
    clave = _experimento(lab)
    informe = lab.experimento(clave).artefacto
    destino = tmp_path / "otro_almacen"
    ruta = tmp_path / "informe.json"
    ruta.write_text(json.dumps(informe), encoding="utf-8")
    resultados = _carrera(destino, [ruta, ruta], "experimento")
    assert [r[0] for r in resultados] == ["existe", "ok"]  # misma entrada: un solo archivo
    assert list((destino / "experimentos" / "MILOTO").glob("*.json")) == [destino / "experimentos" / "MILOTO" /
                                                                          f"{clave}.json"]
    assert LaboratorioFileStore(destino).temporales() == []
    pronosticos = []
    for modelo, i in (("logistica_regularizada", 1), ("logistica_regularizada", 2)):
        cuerpo = la.cuerpo_del_pronostico(informe, lm.CATALOGO[modelo])
        cuerpo["identidad"] = {**cuerpo["identidad"], "prueba": i}  # entradas distintas, misma linea y objetivo
        cuerpo["clave_de_entrada"] = la.huella(cuerpo["identidad"])
        artefacto = la.componer(cuerpo, "generacion", {"generado_en": "2026-10-07T00:00:00+00:00",
                                                       "clasificacion_temporal": None})
        r = tmp_path / f"p{i}.json"
        r.write_text(json.dumps(artefacto), encoding="utf-8")
        pronosticos.append(r)
    resultados = _carrera(destino, pronosticos, "pronostico")
    assert [r[0] for r in resultados] == ["ok", "ok"] and sorted(r[2] for r in resultados) == [1, 2]
    almacen = LaboratorioFileStore(destino)
    linea = almacen.lineas("MILOTO")[0]
    assert all(isinstance(e, Guardado) for e in almacen.pronosticos("MILOTO", linea))
    assert almacen.temporales() == []


def _comparar_y_morir(directorio, listo, nunca):
    """Proceso independiente que se detiene a mitad de la comparacion."""
    from tests.unit import fixtures_producto4 as f
    e = f.entorno(pathlib.Path(directorio))
    original = le.evaluar

    def lento(*a, **k):
        listo.put("evaluando")
        nunca.wait(ESPERA)
        return original(*a, **k)
    le.evaluar = lento
    e.laboratorio().comparar_ahora(["MILOTO"], REDUCIDO)


def test_ejecucion_interrumpida_se_recupera_y_reutiliza_lo_publicado(tmp_path):
    contexto = multiprocessing.get_context("spawn")
    listo, nunca = contexto.Queue(), contexto.Event()
    proceso = contexto.Process(target=_comparar_y_morir, args=(str(tmp_path), listo, nunca))
    proceso.start()
    try:
        assert listo.get(timeout=ESPERA) == "evaluando"
        e = f4.entorno(tmp_path)
        lab = e.laboratorio()
        viva = lab.recientes()[0]
        assert viva["estado"] == "en_curso" and viva["juegos"]["MILOTO"]["fase"] == "obteniendo_datos"
        assert lab.recuperar() == []
    finally:
        proceso.kill()
        proceso.join(ESPERA)
    muerta = lab.consultar_ejecucion(viva["id"])
    assert muerta["estado"] == "interrumpida"
    assert lab.recuperar() == [viva["id"]]
    assert lab.consultar_ejecucion(viva["id"])["juegos"]["MILOTO"]["estado"] == "interrumpido"
    assert e.almacen.experimentos("MILOTO") == []  # nada a medio publicar
    r = lab.comparar_ahora(["MILOTO"], REDUCIDO)  # el cerrojo quedo libre
    assert r["estado"] == "exito"


def test_fallo_al_lanzar_y_cerrojos(entorno):
    lab = entorno.laboratorio()
    inicio = lab.iniciar_comparacion(["MILOTO"], REDUCIDO)
    from app.application.use_cases.operacion_diaria import EjecucionActivaError
    with pytest.raises(EjecucionActivaError):
        lab.iniciar_comparacion(["MILOTO", "COLORLOTO"], REDUCIDO)  # todos o ninguno
    otro = lab.iniciar_comparacion(["COLORLOTO"], REDUCIDO)
    otro.cerrojos.liberar()
    lab.abortar(inicio, "can't start new thread")
    assert lab.consultar_ejecucion(inicio.ejecucion["id"])["estado"] == "interrumpida"
    assert lab.comparar_ahora(["MILOTO"], REDUCIDO)["estado"] == "exito"
