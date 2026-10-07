"""Producto 3: operacion diaria por juego (caso de uso comun a web y
comando). Repositorios en memoria, importador falso, reloj inyectado; sin
Internet ni PostgreSQL."""
from __future__ import annotations

import dataclasses
import json
import multiprocessing

import pytest

from app.application.use_cases.operacion_diaria import EjecucionActivaError, mensaje_legible
from app.application.use_cases.pronostico_experimental import JUEGOS
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego
from tests.unit import fixtures_producto3 as f3

ESPERA = 30


@pytest.fixture
def entorno(tmp_path):
    return f3.entorno(tmp_path)


def _bytes(entorno, codigo):
    return {p.name: p.read_bytes() for p in (entorno.almacen._directorio / codigo).glob("*.json")}


def test_datos_locales_cuatro_juegos_y_reutilizacion(entorno):
    op = entorno.operacion()
    primera = op.ejecutar_ahora(JUEGOS, "local", "prueba")
    assert primera["estado"] == "exito" and list(primera["juegos"]) == list(JUEGOS)
    assert entorno.importador.llamadas == []  # datos locales: nunca importa
    assert {m for _, m in entorno.abiertos} == {"local"}
    for codigo in JUEGOS:
        r = primera["juegos"][codigo]
        assert r["estado"] == "ok" and r["pronostico"]["reutilizado"] is False
        assert r["validacion"]["estado"] == "valido" and r["ultimo_antes"] == r["ultimo_despues"]
        assert [p["paso"] for p in r["pasos"]] == ["estado_inicial", "validacion", "resultados_observados",
                                                   "pronostico"]
        assert r["inicio"] and r["fin"]
    antes = {c: _bytes(entorno, c) for c in JUEGOS}
    segunda = op.ejecutar_ahora(JUEGOS, "local", "prueba")
    for codigo in JUEGOS:
        r = segunda["juegos"][codigo]
        assert r["pronostico"]["reutilizado"] is True
        assert r["pronostico"]["identificador"] == primera["juegos"][codigo]["pronostico"]["identificador"]
        assert _bytes(entorno, codigo) == antes[codigo]  # sin datos nuevos: el mismo artefacto, sin reescribir
    registrada = op.consultar(segunda["id"])
    assert registrada == json.loads(json.dumps(segunda))


def test_actualizar_incorpora_un_sorteo_y_genera_el_siguiente(entorno):
    op = entorno.operacion()
    op.ejecutar_ahora(["MILOTO"], "local", "prueba")
    entorno.importador.pendientes["MILOTO"] = entorno.siguiente("MILOTO")
    e = op.ejecutar_ahora(["MILOTO"], "actualizar", "prueba")
    r = e["juegos"]["MILOTO"]
    assert e["estado"] == "exito" and entorno.importador.llamadas == ["MILOTO"]
    assert r["sincronizacion"]["estado"] == "completado" and r["sincronizacion"]["sorteos_nuevos"] == 1
    assert r["sincronizacion"]["sorteos_corregidos"] is None  # el importador no lo informa; no se inventa
    assert r["ultimo_antes"]["ultimo_sorteo"] == 84 and r["ultimo_despues"]["ultimo_sorteo"] == 85
    assert r["pronostico"]["objetivo"] == 86 and r["pronostico"]["reutilizado"] is False
    assert r["resultados"]["observados"] == 1  # el pronostico del 85 ya tiene resultado


def test_un_juego_falla_al_actualizar_los_demas_completan_y_el_global_es_parcial(entorno):
    op = entorno.operacion()
    entorno.importador.fallar["MILOTO"] = "<html><body>502 Bad Gateway</body></html>"
    e = op.ejecutar_ahora(JUEGOS, "actualizar", "prueba")
    assert e["estado"] == "parcial"
    m = e["juegos"]["MILOTO"]
    assert m["estado"] == "fallo" and m["pronostico"] is None and m["validacion"] is None
    assert "no se genero con el historico anterior" in m["mensaje"] and "<html" not in json.dumps(e)
    assert _bytes(entorno, "MILOTO") == {}  # no genero con el historico anterior
    assert all(e["juegos"][c]["estado"] == "ok" for c in JUEGOS if c != "MILOTO")
    # Despues se puede usar explicitamente la accion con datos locales.
    local = op.ejecutar_ahora(["MILOTO"], "local", "prueba")
    assert local["estado"] == "exito" and local["juegos"]["MILOTO"]["pronostico"]["objetivo"] == 85


def test_todos_fallan_es_fallo_y_base_caida_es_legible(entorno):
    entorno.base_caida.update(JUEGOS)
    e = entorno.operacion().ejecutar_ahora(JUEGOS, "local", "prueba")
    assert e["estado"] == "fallo"
    assert {r["mensaje"] for r in e["juegos"].values()} == {"Sin conexion con la base de datos."}


def test_datos_insuficientes_es_un_estado_explicito(tmp_path):
    entorno = f3.entorno(tmp_path, colorloto=20)
    e = entorno.operacion().ejecutar_ahora(["COLORLOTO", "MILOTO"], "local", "prueba")
    assert e["estado"] == "parcial"
    c = e["juegos"]["COLORLOTO"]
    assert c["estado"] == "datos_insuficientes" and "atos insuficientes" in c["mensaje"] and c["pronostico"] is None


def test_correccion_del_historico_crea_version_sin_reescribir(entorno):
    op = entorno.operacion()
    v1 = op.ejecutar_ahora(["MILOTO"], "local", "prueba")["juegos"]["MILOTO"]["pronostico"]
    antes = _bytes(entorno, "MILOTO")
    mid = entorno.juegos.obtener_por_codigo("MILOTO").id
    entorno.resultados.numericos[mid] = [dataclasses.replace(r, numeros=(1, 2, 3, 4, 5)) if r.numero_sorteo == 4 else r
                                         for r in entorno.historicos["MILOTO"]]
    v2 = op.ejecutar_ahora(["MILOTO"], "local", "prueba")["juegos"]["MILOTO"]["pronostico"]
    assert v2["identificador"] != v1["identificador"] and v2["objetivo"] == v1["objetivo"]
    assert (v2["version"], v2["versiones"]) == (2, 2) and v2["reutilizado"] is False
    despues = _bytes(entorno, "MILOTO")
    assert all(despues[n] == b for n, b in antes.items())  # el anterior no se reescribe


def test_ranking_emitido_no_cambia_y_el_observado_si_al_corregir(entorno):
    op = entorno.operacion()
    r = op.ejecutar_ahora(["MILOTO"], "local", "prueba")["juegos"]["MILOTO"]["pronostico"]
    guardado = entorno.almacen.obtener("MILOTO", r["identificador"])
    ranking = guardado.artefacto["pronostico"]["ranking"]
    nuevo = entorno.siguiente("MILOTO")
    mid = entorno.juegos.obtener_por_codigo("MILOTO").id
    entorno.resultados.numericos[mid] = [*entorno.historicos["MILOTO"], *nuevo]
    from app.application.use_cases.pronostico_experimental import CompararConResultadosObservados
    comparar = CompararConResultadosObservados(entorno.almacen, entorno.juegos, entorno.resultados)
    fila = next(f for f in comparar.ejecutar("MILOTO") if f["identificador"] == r["identificador"])
    assert fila["comparacion"]["resultado"]["numeros"] == [1, 2, 3, 4, 5]
    corregido = dataclasses.replace(nuevo[0], numeros=(6, 7, 8, 9, 10))
    entorno.resultados.numericos[mid] = [*entorno.historicos["MILOTO"], corregido]
    fila2 = next(f for f in comparar.ejecutar("MILOTO") if f["identificador"] == r["identificador"])
    assert fila2["comparacion"]["resultado"]["numeros"] == [6, 7, 8, 9, 10]
    despues = entorno.almacen.obtener("MILOTO", r["identificador"])
    assert despues.artefacto["pronostico"]["ranking"] == ranking and despues.artefacto == guardado.artefacto


def test_ejecucion_activa_no_se_duplica_en_el_mismo_proceso(entorno):
    op = entorno.operacion()
    inicio = op.iniciar(["MILOTO"], "local", "web")
    with pytest.raises(EjecucionActivaError) as error:
        op.iniciar(["MILOTO", "BALOTO"], "local", "comando")
    assert error.value.activas == {"MILOTO": inicio.ejecucion["id"]}
    assert op.activa("MILOTO") == inicio.ejecucion["id"] and op.activa("BALOTO") is None
    otro = op.iniciar(["BALOTO"], "local", "comando")  # otro juego si puede
    otro.cerrojos.liberar()
    assert op.consultar(inicio.ejecucion["id"])["estado"] == "en_curso"
    final = op.ejecutar(inicio)
    assert final["estado"] == "exito" and op.activa("MILOTO") is None


def _proceso_con_cerrojo(directorio, identificador, listo, terminar):
    cerrojos = CerrojoPorJuego(directorio).adquirir(["MILOTO"], identificador)
    assert not isinstance(cerrojos, dict)
    listo.set()
    terminar.wait(ESPERA)


def test_otro_proceso_activo_bloquea_y_su_muerte_se_informa_como_interrumpida(entorno):
    op = entorno.operacion()
    # Simula una ejecucion iniciada por otro proceso (p. ej. el comando) que tiene el cerrojo.
    registro_inicio = op.iniciar(["MILOTO"], "local", "comando")
    identificador = registro_inicio.ejecucion["id"]
    registro_inicio.cerrojos.liberar()
    contexto = multiprocessing.get_context("spawn")
    listo, terminar = contexto.Event(), contexto.Event()
    proceso = contexto.Process(target=_proceso_con_cerrojo,
                               args=(str(entorno.directorio_operacion), identificador, listo, terminar))
    proceso.start()
    try:
        assert listo.wait(ESPERA)
        with pytest.raises(EjecucionActivaError) as error:
            op.iniciar(["MILOTO"], "actualizar", "web")
        assert error.value.activas == {"MILOTO": identificador}
        assert op.consultar(identificador)["estado"] == "en_curso"
    finally:
        proceso.kill()  # el proceso muere sin terminar: el sistema libera el cerrojo
        proceso.join(ESPERA)
    interrumpida = op.consultar(identificador)
    assert interrumpida["estado"] == "interrumpida" and "vuelva a ejecutar" in interrumpida["mensaje"]
    assert op.recuperar() == [identificador]
    assert op.consultar(identificador)["juegos"]["MILOTO"]["estado"] == "interrumpido"
    nueva = op.ejecutar_ahora(["MILOTO"], "local", "web")
    assert nueva["estado"] == "exito"
    otra = op.ejecutar_ahora(["MILOTO"], "local", "web")
    assert otra["juegos"]["MILOTO"]["pronostico"]["reutilizado"] is True  # sin publicaciones duplicadas
    assert len(_bytes(entorno, "MILOTO")) == 1


def test_registro_separado_y_sin_html_ni_credenciales(entorno):
    entorno.importador.fallar["BALOTO"] = ("<!DOCTYPE html><html><head><title>Error</title></head><body>"
                                           + "x" * 5000 + "</body></html>")
    e = entorno.operacion().ejecutar_ahora(["BALOTO"], "actualizar", "prueba")
    texto = (entorno.directorio_operacion / "ejecuciones" / f"{e['id']}.json").read_text(encoding="utf-8")
    assert "<html" not in texto and "<body" not in texto and len(texto) < 4000
    # El registro operativo vive fuera del almacen de pronosticos y no le anade nada.
    assert not (entorno.almacen._directorio / "BALOTO").exists()
    assert entorno.almacen._directorio not in (entorno.directorio_operacion / "ejecuciones").parents
    assert "postgresql" not in texto.lower()


def test_mensaje_legible_recorta_y_quita_html():
    assert mensaje_legible("<b>hola</b> mundo") == "hola mundo"
    assert mensaje_legible("x" * 1000).endswith("…") and len(mensaje_legible("x" * 1000)) == 301


class _SesionRegistrada:
    def __init__(self, registro):
        self.registro = registro
        registro.append(("abrir", id(self)))

    def execute(self, sentencia, *a, **k):
        self.registro.append(("execute", str(sentencia)))

    def commit(self):
        self.registro.append(("commit", id(self)))

    def rollback(self):
        self.registro.append(("rollback", id(self)))

    def close(self):
        self.registro.append(("close", id(self)))


def test_fabrica_real_sesion_propia_solo_lectura_en_local(monkeypatch):
    from app.api import dependencies as dep
    from app.application.use_cases.sincronizar_sorteos import SincronizarSorteos
    from app.infrastructure.db import session as db_session

    registro = []
    monkeypatch.setattr(db_session, "SessionLocal", lambda: _SesionRegistrada(registro))
    with dep.abrir_dependencias_de_operacion("MILOTO", "local") as local:
        assert local.sincronizar is None
    assert ("execute", "SET TRANSACTION READ ONLY") in registro
    assert [r[0] for r in registro if r[0] in ("commit", "rollback")] == ["rollback"]
    registro.clear()
    with dep.abrir_dependencias_de_operacion("MILOTO", "actualizar") as actualizar:
        assert actualizar.sincronizar.__self__.__class__ is SincronizarSorteos
    assert ("execute", "SET TRANSACTION READ ONLY") not in registro and registro[-2][0] == "commit"
    registro.clear()
    with dep.abrir_dependencias_de_operacion("BALOTO", "local"), dep.abrir_dependencias_de_operacion("MILOTO", "local"):
        pass
    sesiones = {r[1] for r in registro if r[0] == "abrir"}
    assert len(sesiones) == 2  # cada juego (o hilo) con su propia sesion


def test_consultar_no_crea_archivos(tmp_path):
    cerrojo = CerrojoPorJuego(tmp_path / "operacion")
    assert cerrojo.activa("MILOTO") is None and cerrojo.ocupado("BALOTO") is False
    assert not (tmp_path / "operacion").exists()
