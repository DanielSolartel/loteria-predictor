"""Producto 5: almacen, identidad, idempotencia, concurrencia y recuperacion.

- la clave de entrada se calcula antes del trabajo costoso: repetir devuelve
  lo guardado sin entrenar ni simular;
- un artefacto alterado con la misma clave no se sobrescribe;
- temporales y reservas huerfanas no son resultados;
- orden de emision sellado por linea y objetivo;
- carreras entre procesos reales (spawn) para carteras y configuraciones;
- un trabajo interrumpido se reconoce, libera su cerrojo y no deja nada a
  medio publicar; tiempo agotado y cartera parcial no publican nada;
- configuraciones versionadas inmutables; una version vigente alterada no
  cae a otra anterior."""
from __future__ import annotations

import json
import multiprocessing
import pathlib

import pytest

from app.application.interfaces.ejecutor_carteras import TiempoAgotadoError
from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_simulacion as cs
from app.application.ml import laboratorio_modelos as lm
from app.application.use_cases.carteras import CarterasError, EjecutorCarterasEnEsteProceso
from app.application.use_cases.operacion_diaria import EjecucionActivaError
from app.infrastructure.storage.carteras_file_store import CarterasFileStore, Guardado, Ilegible
from tests.unit import fixtures_producto5 as f5

ESPERA = 120
CARTERA = {"modelo": "logistica_regularizada", "perfil": "reducido", "cantidad": 5, "semilla": 42,
           "diversidad": "limitada"}


@pytest.fixture
def entorno(tmp_path):
    return f5.entorno(tmp_path, {"BALOTO": 70, "BALOTO_REVANCHA": 70, "MILOTO": 70, "COLORLOTO": 70})


def _cartera(servicio, juego="MILOTO", **cambios):
    r = servicio.ahora("cartera", [juego], {**CARTERA, **cambios})["juegos"][juego]
    assert r["estado"] in ("terminado", "reutilizado"), f5.detalle(r)
    return r


def _ruta(e, guardado):
    return next((e.directorio / "carteras" / guardado.juego / guardado.linea).glob(f"*-{guardado.identificador}.json"))


def _contar_ajustes(monkeypatch):
    llamadas = []
    original = lm.ajustar_candidato
    monkeypatch.setattr(lm, "ajustar_candidato", lambda *a, **k: llamadas.append(a[0].id) or original(*a, **k))
    return llamadas


def test_repetir_la_misma_entrada_reutiliza_sin_entrenar_ni_simular(entorno, monkeypatch):
    s = entorno.carteras()
    llamadas = _contar_ajustes(monkeypatch)
    primera = _cartera(s)
    assert primera["estado"] == "terminado" and llamadas
    llamadas.clear()
    segunda = _cartera(s)
    assert segunda["estado"] == "reutilizado" and segunda["resultado"] == primera["resultado"] and llamadas == []
    simulaciones = []
    original = cs.simular
    monkeypatch.setattr(cs, "simular", lambda *a, **k: simulaciones.append(1) or original(*a, **k))
    parametros = {"cartera": primera["resultado"], "simulaciones": 1000, "semilla": 3}
    a = s.ahora("simulacion", ["MILOTO"], parametros)["juegos"]["MILOTO"]
    assert a["estado"] == "terminado" and simulaciones == [1], f5.detalle(a)
    b = s.ahora("simulacion", ["MILOTO"], parametros)["juegos"]["MILOTO"]
    assert b["estado"] == "reutilizado" and b["resultado"] == a["resultado"] and simulaciones == [1], f5.detalle(b)
    llamadas.clear()
    protocolo = {"protocolo": {"bloques": 1, "perfil": "reducido"}}
    c1 = s.ahora("comparacion", ["MILOTO"], protocolo)["juegos"]["MILOTO"]
    llamadas.clear()
    c2 = s.ahora("comparacion", ["MILOTO"], protocolo)["juegos"]["MILOTO"]
    assert c2["estado"] == "reutilizado" and c2["resultado"] == c1["resultado"] and llamadas == [], f5.detalle(c2)


def test_la_clave_de_entrada_se_conoce_antes_del_trabajo_costoso(entorno):
    s = entorno.carteras()
    r = _cartera(s)
    guardado = s.cartera(r["resultado"])
    instantanea = ca.instantanea_de(guardado.artefacto)
    identidad = ca.identidad_de_cartera(instantanea, CARTERA["modelo"], CARTERA["perfil"], 5, 42, "limitada")
    assert ca.huella(identidad) == r["resultado"] == guardado.artefacto["clave_de_entrada"]
    assert "pesos" not in json.dumps(identidad) and "probabilidades" not in json.dumps(identidad)

    class Prohibido(EjecutorCarterasEnEsteProceso):
        def fuente(self, *a, **k):
            raise AssertionError("no debe recalcular lo ya guardado")
    final = entorno.carteras(ejecutor=Prohibido()).ahora("cartera", ["MILOTO"], CARTERA)
    assert final["estado"] == "exito", f5.detalle(final)


def test_una_cartera_alterada_con_la_misma_clave_no_se_sobrescribe(entorno):
    s = entorno.carteras()
    r = _cartera(s)
    ruta = _ruta(entorno, s.cartera(r["resultado"]))
    ruta.write_bytes(ruta.read_bytes().replace(b'"cartera"', b'"cartera" ', 1))
    alterado = ruta.read_bytes()
    otra = s.ahora("cartera", ["MILOTO"], CARTERA)["juegos"]["MILOTO"]
    assert otra["estado"] == "fallo" and "no se sobrescribe" in otra["mensaje"], f5.detalle(otra)
    assert ruta.read_bytes() == alterado
    assert isinstance(entorno.almacen.obtener_cartera(r["resultado"]), Ilegible)
    with pytest.raises(CarterasError) as error:
        s.cartera(r["resultado"])
    assert error.value.codigo == "alterado"
    assert s.verificar_cartera(r["resultado"])["integridad"] == "alterado"


def test_temporales_y_reservas_huerfanas_no_son_resultados(entorno):
    s = entorno.carteras()
    r = _cartera(s)
    g = s.cartera(r["resultado"])
    carpeta = _ruta(entorno, g).parent
    # temporal huerfano con el nombre actual (el anterior, de 91 caracteres, quedaba al limite de rutas de
    # Windows en esta carpeta; test_producto5_rutas.py cubre los dos nombres)
    (carpeta / ".publicacion.0123456789abcdef.tmp").write_bytes(b'{"a medio')
    (carpeta / f"{g.objetivo}-000009.secuencia").write_text("e" * 64 + "\n")
    almacen = entorno.almacen
    assert [e.identificador for e in almacen.carteras("MILOTO", g.linea)] == [g.identificador]
    assert len(almacen.temporales()) == 1 and almacen.obtener_cartera("f" * 64) is None
    assert almacen.obtener_cartera("e" * 64) is None


def test_orden_de_emision_por_linea_y_objetivo(entorno):
    s = entorno.carteras()
    primera = s.cartera(_cartera(s)["resultado"])
    juego = entorno.juegos.obtener_por_codigo("MILOTO")
    sorteos = entorno.cargados("MILOTO")
    corregido = sorteos[5].__class__(sorteos[5].numero_sorteo, sorteos[5].fecha, sorteos[5].dia_semana,
                                     (2, 3, 4, 5, 6), None)
    entorno.resultados.numericos[juego.id] = [*sorteos[:5], corregido, *sorteos[6:]]  # correccion de la base
    segunda = s.cartera(_cartera(s)["resultado"])
    assert segunda.identificador != primera.identificador
    assert (segunda.linea, segunda.objetivo) == (primera.linea, primera.objetivo)
    assert (primera.secuencia, segunda.secuencia) == (1, 2)
    assert segunda.artefacto["generacion"]["version_anterior"] == primera.identificador
    listado = entorno.almacen.carteras("MILOTO", primera.linea)
    assert [(e.identificador, e.version, e.versiones) for e in listado] == [
        (segunda.identificador, 2, 2), (primera.identificador, 1, 2)]


def _guardar_en_proceso(directorio, ruta_artefacto, tipo, barrera, cola):
    almacen = CarterasFileStore(directorio)
    artefacto = json.loads(pathlib.Path(ruta_artefacto).read_text(encoding="utf-8"))
    barrera.wait(ESPERA)
    try:
        if tipo == "cartera":
            g = almacen.guardar_cartera(artefacto)
        else:
            g = almacen.guardar_configuracion("MILOTO", lambda v: ca.componer(
                ca.cuerpo_de_configuracion("MILOTO", v, "uniforme", "predeterminado", 3, "libre", artefacto["semilla"]),
                "registro", {"guardada_en": "2026-10-07T00:00:00+00:00"}))
        cola.put(("ok", g.identificador, g.secuencia if tipo == "cartera" else g.artefacto["version"]))
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
    s = entorno.carteras()
    g = s.cartera(_cartera(s)["resultado"])
    sin_orden = {k: v for k, v in g.artefacto.items() if k != "sello"}
    sin_orden["generacion"] = {k: v for k, v in g.artefacto["generacion"].items()
                               if k not in ("secuencia_en_la_linea", "version_anterior")}
    original = {**sin_orden, "sello": ca.huella(sin_orden)}
    destino = tmp_path / "otro_almacen"
    ruta = tmp_path / "cartera.json"
    ruta.write_text(json.dumps(original), encoding="utf-8")
    resultados = _carrera(destino, [ruta, ruta], "cartera")
    assert [r[0] for r in resultados] == ["existe", "ok"]  # misma entrada: un solo archivo
    almacen = CarterasFileStore(destino)
    assert [e.identificador for e in almacen.carteras("MILOTO", g.linea)] == [g.identificador]
    # el proceso que pierde el enlace puede haber ganado antes la reserva 1: el ganador queda con la 2 y la
    # reserva del perdedor se retira. La secuencia ordena; no cuenta emisiones.
    primera = almacen.carteras("MILOTO", g.linea)[0].secuencia
    assert primera in (1, 2) and not list((destino / "carteras" / "MILOTO" / g.linea).glob("*.tmp"))
    rutas = []
    for i in (1, 2):  # entradas distintas, misma linea y objetivo
        cuerpo = {k: v for k, v in original.items() if k not in ca.VOLATILES[ca.ESQUEMA_CARTERA]}
        cuerpo["identidad"] = {**cuerpo["identidad"], "prueba": i}
        cuerpo["clave_de_entrada"] = ca.huella(cuerpo["identidad"])
        r = tmp_path / f"c{i}.json"
        r.write_text(json.dumps(ca.componer(cuerpo, "generacion", {"generado_en": "x"})), encoding="utf-8")
        rutas.append(r)
    resultados = _carrera(destino, rutas, "cartera")
    # dos secuencias distintas, ambas posteriores a la primera emision de la linea
    assert [r[0] for r in resultados] == ["ok", "ok"]
    segunda, tercera = sorted(r[2] for r in resultados)
    assert primera < segunda < tercera
    listado = almacen.carteras("MILOTO", g.linea)
    assert all(isinstance(e, Guardado) for e in listado) and [e.secuencia for e in listado] == [tercera, segunda, primera]
    assert [(e.version, e.versiones) for e in listado] == [(3, 3), (2, 3), (1, 3)]
    assert almacen.temporales() == []
    semillas = []
    for i in (1, 2):
        r = tmp_path / f"s{i}.json"
        r.write_text(json.dumps({"semilla": i}), encoding="utf-8")
        semillas.append(r)
    resultados = _carrera(destino, semillas, "configuracion")
    assert sorted(r[2] for r in resultados) == [1, 2]  # cada escritor toma su propia version
    assert [e.artefacto["version"] for e in almacen.configuraciones("MILOTO")] == [2, 1]


class _Bloqueado(EjecutorCarterasEnEsteProceso):
    def __init__(self, listo, nunca):
        self.listo, self.nunca = listo, nunca

    def fuente(self, *a, **k):
        self.listo.put("calculando")
        self.nunca.wait(ESPERA)
        return super().fuente(*a, **k)


def _generar_y_morir(directorio, listo, nunca):
    """Proceso independiente que se detiene a mitad de la generacion."""
    from tests.unit import fixtures_producto5 as f
    e = f.entorno(pathlib.Path(directorio), {"MILOTO": 70})
    e.carteras(ejecutor=_Bloqueado(listo, nunca)).ahora("cartera", ["MILOTO"], CARTERA)


def test_trabajo_interrumpido_se_recupera_y_no_deja_nada_a_medio_publicar(tmp_path):
    contexto = multiprocessing.get_context("spawn")
    listo, nunca = contexto.Queue(), contexto.Event()
    proceso = contexto.Process(target=_generar_y_morir, args=(str(tmp_path), listo, nunca))
    proceso.start()
    try:
        assert listo.get(timeout=ESPERA) == "calculando"
        e = f5.entorno(tmp_path, {"MILOTO": 70})
        s = e.carteras()
        viva = s.recientes()[0]
        assert viva["estado"] == "en_curso" and viva["juegos"]["MILOTO"]["fase"] == "fuente"
        assert s.recuperar() == []
        with pytest.raises(EjecucionActivaError):
            s.iniciar("cartera", ["MILOTO"], CARTERA)
    finally:
        proceso.kill()
        proceso.join(ESPERA)
    assert s.consultar_ejecucion(viva["id"])["estado"] == "interrumpida"
    assert s.recuperar() == [viva["id"]]
    assert s.consultar_ejecucion(viva["id"])["juegos"]["MILOTO"]["estado"] == "interrumpido"
    assert e.almacen.lineas("MILOTO") == [] and e.almacen.temporales() == []
    otra = s.ahora("cartera", ["MILOTO"], CARTERA)
    assert otra["estado"] == "exito", f5.detalle(otra)  # el cerrojo quedo libre


def test_tiempo_agotado_y_fallo_del_trabajador_no_publican(entorno):
    class Agotado(EjecutorCarterasEnEsteProceso):
        def fuente(self, *a, **k):
            raise TiempoAgotadoError("el trabajo supero el tiempo maximo de 300 s y se detuvo")
    final = entorno.carteras(ejecutor=Agotado()).ahora("cartera", ["MILOTO"], CARTERA)
    assert final["estado"] == "fallo" and final["juegos"]["MILOTO"]["estado"] == "tiempo_agotado", f5.detalle(final)
    assert "300 s" in final["juegos"]["MILOTO"]["mensaje"] and entorno.almacen.lineas("MILOTO") == []
    repetida = entorno.carteras().ahora("cartera", ["MILOTO"], CARTERA)
    assert repetida["estado"] == "exito", f5.detalle(repetida)


def test_cartera_parcial_no_se_publica(entorno, monkeypatch):
    class Concentrado(EjecutorCarterasEnEsteProceso):
        def fuente(self, instantanea, modelo, perfil, avance=None):
            salida = super().fuente(instantanea, modelo, perfil, avance)
            pesos = [1.0 if c <= 7 else 1e-9 for c in salida["candidatos"]]
            return {**salida, "probabilidades": [5 * p / sum(pesos) for p in pesos]}
    final = entorno.carteras(ejecutor=Concentrado()).ahora("cartera", ["MILOTO"], {**CARTERA, "cantidad": 20})
    r = final["juegos"]["MILOTO"]
    assert final["estado"] == "parcial" and r["estado"] == "parcial"
    assert r["obtenidas"] < r["solicitadas"] == 20 and "no se relajo" in r["mensaje"]
    assert entorno.almacen.lineas("MILOTO") == []
    with pytest.raises(ValueError):
        cuerpo = {"esquema": ca.ESQUEMA_CARTERA, "clave_de_entrada": "a" * 64, "juego": "MILOTO",
                  "linea": {"id": "x-v1-n5-libre-s1"}, "cartera": {"estado": "parcial", "objetivo": 1}}
        entorno.almacen.guardar_cartera(ca.componer(cuerpo, "generacion", {}))


def test_muestra_insuficiente_para_generar_con_el_ensemble(tmp_path):
    e = f5.entorno(tmp_path, {"MILOTO": 59})
    r = e.carteras().ahora("cartera", ["MILOTO"], {**CARTERA, "modelo": "ensemble_temporal"})["juegos"]["MILOTO"]
    assert r["estado"] == "muestra_insuficiente" and "60" in r["mensaje"]
    r = e.carteras().ahora("comparacion", ["MILOTO"], {"protocolo": {"perfil": "reducido"}})["juegos"]["MILOTO"]
    assert r["estado"] == "muestra_insuficiente" and "70 sorteos" in r["mensaje"]
    assert e.almacen.lineas("MILOTO") == [] and e.almacen.comparaciones("MILOTO") == []


def test_configuraciones_versionadas_y_vigente_alterada_sin_retroceder(entorno):
    s = entorno.carteras()
    assert s.configuracion_vigente("BALOTO") is None
    v1 = s.configurar("BALOTO", "uniforme", 3, "libre", 1)
    v2 = s.configurar("BALOTO", "ensemble_temporal", 5, "limitada", 42, perfil="reducido")
    assert (v1.artefacto["version"], v2.artefacto["version"]) == (1, 2)
    assert s.configuracion_vigente("BALOTO").artefacto["linea"] == "ensemble_temporal-v1-n5-limitada-s42-reducido"
    ruta_v1 = entorno.directorio / "configuraciones" / "BALOTO" / "000001.json"
    bytes_v1 = ruta_v1.read_bytes()
    with pytest.raises(CarterasError):
        s.configurar("BALOTO", "nada", 5, "libre", 1)
    with pytest.raises(CarterasError):
        s.configurar("BALOTO", "uniforme", 21, "libre", 1)
    assert ruta_v1.read_bytes() == bytes_v1 and len(s.configuraciones("BALOTO")) == 2
    ruta_v2 = entorno.directorio / "configuraciones" / "BALOTO" / "000002.json"
    ruta_v2.write_bytes(ruta_v2.read_bytes().replace(b'"cantidad":5', b'"cantidad":6'))
    with pytest.raises(CarterasError) as error:
        s.configuracion_vigente("BALOTO")
    assert error.value.codigo == "alterado" and "no se usa una version anterior" in str(error.value)
    final = s.ahora("carteras_configuradas", ["BALOTO", "MILOTO"])
    assert final["juegos"]["BALOTO"]["estado"] == "fallo" and "alterada" in final["juegos"]["BALOTO"]["mensaje"]
    assert final["juegos"]["MILOTO"]["estado"] == "sin_configuracion"
    assert entorno.almacen.lineas("BALOTO") == []


def test_carteras_configuradas_usan_la_version_vigente(entorno):
    s = entorno.carteras()
    s.configurar("MILOTO", "uniforme", 3, "libre", 1)
    s.configurar("MILOTO", "logistica_regularizada", 4, "limitada", 9, perfil="reducido")
    final = s.ahora("carteras_configuradas", ["MILOTO", "COLORLOTO"])
    r = final["juegos"]["MILOTO"]
    assert r["estado"] == "terminado", f5.detalle(final)
    assert r["configuracion"] == {"version": 2, "linea": "logistica_regularizada-v1-n4-limitada-s9-reducido"}
    g = s.cartera(r["resultado"])
    assert g.artefacto["generacion"]["configuracion"]["version"] == 2 and len(g.artefacto["cartera"]["combinaciones"]) == 4
    assert final["juegos"]["COLORLOTO"]["estado"] == "sin_configuracion" and final["estado"] == "parcial", \
        f5.detalle(final)
    otra = s.ahora("carteras_configuradas", ["MILOTO"])
    assert otra["juegos"]["MILOTO"]["estado"] == "reutilizado", f5.detalle(otra)
