"""Producto 6: adaptadores de las tres procedencias y reglas de admision.

- cruce de operacion diaria (Productos 1-3), laboratorio (Producto 4) y vector
  fuente de las carteras (Producto 5) sobre los mismos objetivos;
- metricas iguales a las funciones actuales de `rendimiento_observado`;
- primera emision sellada; una version posterior mas favorable nunca la
  sustituye, ni siquiera cuando la primera no es evaluable;
- el vector fuente se evalua una vez por objetivo aunque lo usen varias
  carteras, y vectores distintos excluyen el objetivo;
- estados separados: integridad, historico hasta el corte, resultado
  observado y admision (historico corregido, base inaccesible, artefacto
  ilegible, resultado fuera del universo, procedencia ausente);
- seguimiento, retrospectiva, simulaciones, numeros y superbalota separados."""
from __future__ import annotations

import copy
import dataclasses

import pytest

from app.application.interfaces.carteras_store import GuardadoCarteras
from app.application.interfaces.laboratorio_store import GuardadoLaboratorio, IlegibleLaboratorio
from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado
from app.application.ml import carteras_simulacion as cs
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import rendimiento_observado as rmet
from app.application.ml import resultados_procedencias as rp
from app.application.use_cases.resultados import Filtros
from tests.unit import fixtures_producto6 as f6


@pytest.fixture
def miloto(tmp_path):
    """MiLoto con artefactos de las tres procedencias para el objetivo 85 y su resultado ya cargado."""
    e = f6.entorno(tmp_path)
    e.poblar(("MILOTO",))
    e.llega_el_resultado("MILOTO")
    return e


def _por_procedencia(vista: dict) -> dict:
    salida: dict = {}
    for f in vista["emisiones_de_la_seleccion"]:
        salida.setdefault(f["procedencia"], []).append(f)
    return salida


def _numeros(e, juego="MILOTO"):
    return list(e.e4.cargados(juego)[-1].numeros)


# ---------------------------------------------------------------------------
# Cruce de procedencias y metricas
# ---------------------------------------------------------------------------

def test_cruce_de_las_tres_procedencias_con_metricas_de_las_funciones_actuales(miloto):
    v = miloto.centro().consultar("MILOTO", completa=True)
    filas = _por_procedencia(v)
    assert set(filas) == {"operacion", "laboratorio", "carteras"}
    assert [m["procedencia"] for m in v["lineas"]] == ["operacion", "laboratorio", "carteras"]
    assert v["comparacion"]["estado"] == "con_muestra_comun" and v["comparacion"]["objetivos_comunes"] == [85]
    fecha = miloto.e4.cargados("MILOTO")[-1].fecha.isoformat()
    assert {f["fecha_sorteo"] for f in v["emisiones_de_la_seleccion"]} == {fecha}
    numeros = _numeros(miloto)
    op = filas["operacion"][0]
    artefacto = next(g for g in miloto.e3.almacen.listar("MILOTO")).artefacto
    esperado = rmet.metricas_numeros(artefacto, numeros)
    assert op["estado"] == "incluido" and op["metricas"] == esperado
    lab = filas["laboratorio"][0]
    linea = miloto.e4.almacen.lineas("MILOTO")[0]
    a_lab = miloto.e4.almacen.pronosticos("MILOTO", linea)[0].artefacto
    assert lab["metricas"] == rmet.metricas_numeros(a_lab, numeros)
    # vector fuente: artefacto construido aqui a mano desde el vector guardado (sin renormalizar)
    car = filas["carteras"][0]
    lineas_c = miloto.e5.almacen.lineas("MILOTO")
    fuente = miloto.e5.almacen.carteras("MILOTO", lineas_c[0])[0].artefacto["fuente"]
    a_car = {"pronostico": {"objetivo": 85, "ranking": [
        {"numero": c, "probabilidad": p, "probabilidad_uniforme": 5 / len(fuente["candidatos"])}
        for c, p in zip(fuente["candidatos"], fuente["probabilidades"])]}}
    assert car["metricas"] == rmet.metricas_numeros(a_car, numeros)
    assert car["congelado"]["probabilidad"] == [p for _, p in sorted(zip(fuente["candidatos"],
                                                                          fuente["probabilidades"]))]


def test_vector_fuente_una_vez_por_objetivo_aunque_lo_usen_varias_carteras(miloto):
    v = miloto.centro().consultar("MILOTO", completa=True)
    car = _por_procedencia(v)["carteras"]
    assert len(car) == 1
    assert sorted(u["linea"] for u in car[0]["carteras"]) == sorted(miloto.e5.almacen.lineas("MILOTO"))
    clave = car[0]["clave_linea"]
    assert v["resumenes"][clave]["incluidos"] == 1
    assert v["carteras"]["relacion_modelo_carteras"] == {
        clave.split(":", 1)[1]: sorted(miloto.e5.almacen.lineas("MILOTO"))}
    # el vector no tiene sugerencia propia: sus aciertos son los de las carteras, en su seccion
    assert car[0]["aciertos"] is None
    assert all(c["resumen"]["incluidos"] == 1 for c in v["carteras"]["lineas"].values())


def test_vectores_fuente_distintos_en_el_objetivo_excluyen_sin_elegir(miloto):
    completo = miloto.e4.cargados("MILOTO")
    por_linea = {l: miloto.e5.almacen.carteras("MILOTO", l) for l in miloto.e5.almacen.lineas("MILOTO")}
    primera = sorted(por_linea)[0]
    g = por_linea[primera][0]
    otro = copy.deepcopy(g.artefacto)
    otro["fuente"]["probabilidades"] = list(reversed(otro["fuente"]["probabilidades"]))
    por_linea[primera] = [dataclasses.replace(g, artefacto=otro)]
    _, filas = rp.emisiones_carteras("MILOTO", rp.seguimientos_de_carteras(por_linea, completo), completo)
    assert len(filas) == 1
    assert filas[0]["estado"] == "excluido" and filas[0]["motivo"] == "vectores_fuente_distintos_en_el_objetivo"
    assert filas[0]["metricas"] is None and filas[0]["congelado"] is None


def test_vector_fuente_de_colorloto_como_distribucion_de_pares():
    candidatos = [[n, c] for n in (2, 1) for c in ("ROJO", "AZUL")]
    fuente = {"candidatos": candidatos, "probabilidades": [0.1, 0.2, 0.3, 0.4], "masa": 1}
    congelado = rp.congelado_de_fuente("COLORLOTO", fuente)
    assert congelado["candidatos"] == [[1, "AZUL"], [1, "ROJO"], [2, "AZUL"], [2, "ROJO"]]
    assert congelado["probabilidad"] == [0.4, 0.3, 0.2, 0.1]  # los valores guardados, solo reordenados
    assert congelado["probabilidad_uniforme"] == [0.25] * 4
    numeros = rp.congelado_de_fuente("MILOTO", {"candidatos": [3, 1, 2], "probabilidades": [0.5, 0.2, 0.3],
                                                "masa": 1})
    assert numeros["candidatos"] == [1, 2, 3] and numeros["probabilidad"] == [0.2, 0.3, 0.5]
    assert numeros["probabilidad_uniforme"] == [1 / 3] * 3


# ---------------------------------------------------------------------------
# Primera emision sellada, sin sustitucion
# ---------------------------------------------------------------------------

def _favorable(artefacto: dict, numeros) -> dict:
    a = copy.deepcopy(artefacto)
    for f in a["pronostico"]["ranking"]:
        f["probabilidad"] = 0.95 if f["numero"] in numeros else 0.01
    return a


def test_laboratorio_primera_emision_y_sin_sustitucion(miloto):
    completo = miloto.e4.cargados("MILOTO")
    numeros = _numeros(miloto)
    linea = miloto.e4.almacen.lineas("MILOTO")[0]
    g1 = miloto.e4.almacen.pronosticos("MILOTO", linea)[0]
    a2 = _favorable(g1.artefacto, numeros)
    a2["generacion"]["secuencia_en_la_linea"] = 2
    g2 = GuardadoLaboratorio("f" * 64, "MILOTO", a2, linea)
    _, filas = rp.emisiones_laboratorio("MILOTO", {linea: [g2, g1]}, completo)
    assert len(filas) == 1 and filas[0]["identificador"] == g1.identificador and filas[0]["versiones"] == 2
    assert filas[0]["metricas"]["log_loss"] == rmet.metricas_numeros(g1.artefacto, numeros)["log_loss"]
    assert filas[0]["metricas"]["log_loss"] > rmet.metricas_numeros(a2, numeros)["log_loss"]
    # la primera no es evaluable (historico cambiado): se excluye, sin pasar a la segunda
    a1 = copy.deepcopy(g1.artefacto)
    a1["datos"]["sha256_historico"] = "0" * 64
    _, filas = rp.emisiones_laboratorio("MILOTO", {linea: [g2, dataclasses.replace(g1, artefacto=a1)]}, completo)
    assert filas[0]["identificador"] == g1.identificador
    assert (filas[0]["estado"], filas[0]["motivo"]) == ("excluido", "historico_hasta_el_corte_cambio")
    # un archivo ilegible del objetivo hace ambiguo el orden: se excluye sin elegir
    ilegible = IlegibleLaboratorio("e" * 64, "MILOTO", "json_no_canonico", linea, 85)
    _, filas = rp.emisiones_laboratorio("MILOTO", {linea: [g2, g1, ilegible]}, completo)
    assert (filas[0]["estado"], filas[0]["integridad"]) == ("excluido", "orden_ambiguo")


def test_carteras_primera_emision_y_sin_sustitucion(miloto):
    completo = miloto.e4.cargados("MILOTO")
    numeros = _numeros(miloto)
    linea = sorted(miloto.e5.almacen.lineas("MILOTO"))[0]
    g1 = miloto.e5.almacen.carteras("MILOTO", linea)[0]
    a2 = copy.deepcopy(g1.artefacto)
    a2["fuente"]["probabilidades"] = [0.95 if c in numeros else 0.01 for c in a2["fuente"]["candidatos"]]
    a2["generacion"]["secuencia_en_la_linea"] = 2
    g2 = GuardadoCarteras("f" * 64, "MILOTO", "cartera", a2, linea)
    seg = rp.seguimientos_de_carteras({linea: [g2, g1]}, completo)
    _, filas = rp.emisiones_carteras("MILOTO", seg, completo)
    assert len(filas) == 1 and filas[0]["identificador"] == g1.identificador and filas[0]["estado"] == "incluido"
    a1 = copy.deepcopy(g1.artefacto)
    a1["datos"]["sha256_historico"] = "0" * 64
    seg = rp.seguimientos_de_carteras({linea: [g2, dataclasses.replace(g1, artefacto=a1)]}, completo)
    _, filas = rp.emisiones_carteras("MILOTO", seg, completo)
    assert filas[0]["identificador"] == g1.identificador
    assert (filas[0]["estado"], filas[0]["motivo"]) == ("excluido", "historico_hasta_el_corte_cambio")


def test_operacion_primera_emision_y_sin_sustitucion(miloto):
    completo = miloto.e4.cargados("MILOTO")
    numeros = _numeros(miloto)
    g1 = miloto.e3.almacen.listar("MILOTO")[0]
    assert g1.artefacto["generacion"]["secuencia_en_el_objetivo"] == 1
    a2 = _favorable(g1.artefacto, numeros)
    a2["generacion"]["secuencia_en_el_objetivo"] = 2
    g2 = PronosticoGuardado("f" * 64, "MILOTO", a2)
    _, filas = rp.emisiones_operacion("MILOTO", [g2, g1], {}, completo, "miloto")
    assert len(filas) == 1 and filas[0]["identificador"] == g1.identificador and filas[0]["versiones"] == 2
    assert filas[0]["metricas"] == rmet.metricas_numeros(g1.artefacto, numeros)
    a1 = copy.deepcopy(g1.artefacto)
    a1["datos"]["sha256_historico"] = "0" * 64
    _, filas = rp.emisiones_operacion("MILOTO", [g2, dataclasses.replace(g1, artefacto=a1)], {}, completo, "miloto")
    assert filas[0]["identificador"] == g1.identificador
    assert (filas[0]["estado"], filas[0]["motivo"]) == ("excluido", "historico_hasta_el_corte_cambio")


# ---------------------------------------------------------------------------
# Estados separados
# ---------------------------------------------------------------------------

def test_historico_corregido_excluye_en_las_tres_procedencias(miloto):
    juego = miloto.e4.juegos.obtener_por_codigo("MILOTO")
    lista = miloto.e4.resultados.numericos[juego.id]
    lista[10] = dataclasses.replace(lista[10], numeros=(1, 2, 3, 4, 39))
    v = miloto.centro().consultar("MILOTO", completa=True)
    for f in v["emisiones_de_la_seleccion"]:
        assert (f["integridad"], f["historico"], f["resultado_estado"]) == ("legible", "cambio", "observado")
        assert (f["estado"], f["motivo"]) == ("excluido", "historico_hasta_el_corte_cambio")
        assert f["metricas"] is None and f["congelado"] is None
    assert v["comparacion"]["estado"] == "sin_muestra_comun"


def test_base_inaccesible_no_es_cero_ni_pendiente_confirmado(miloto):
    miloto.e4.base_caida = True
    centro = miloto.centro()
    v = centro.consultar("MILOTO", completa=True)
    assert v["base"]["estado"] == "no_disponible" and v["base"]["ultimo_sorteo"] is None
    assert v["base"]["fecha"] is None
    for f in v["emisiones_de_la_seleccion"]:
        assert f["estado"] == "sin_base" and f["resultado_estado"] == "sin_base"
        assert f["aciertos"] is None and f["metricas"] is None
    for r in v["resumenes"].values():
        assert r["sin_base"] == 1 and r["pendientes"] == 0 and r["perdidas"] is None and r["aciertos"] is None
    assert all(j["base"]["ultimo_sorteo"] is None for j in centro.indice()["juegos"])


def test_resultado_fuera_del_universo_congelado_no_es_evaluable(tmp_path):
    e = f6.entorno(tmp_path)
    e.poblar(("COLORLOTO",))
    nuevo = e.e4.siguiente("COLORLOTO")[0]
    e.e4.anadir("COLORLOTO", [dataclasses.replace(nuevo, pares=((1, "MORADO"), *nuevo.pares[1:]))])
    v = e.centro().consultar("COLORLOTO", completa=True)
    assert {f["procedencia"] for f in v["emisiones_de_la_seleccion"]} == {"operacion", "laboratorio", "carteras"}
    for f in v["emisiones_de_la_seleccion"]:
        assert (f["estado"], f["motivo"]) == ("excluido", "resultado_no_evaluable_con_el_artefacto")
        assert f["resultado_estado"] == "observado" and f["historico"] == "coincide"


def test_artefacto_ilegible_y_procedencia_ausente_no_impiden_consultar_las_demas(miloto):
    archivo = next((miloto.directorio / "laboratorio" / "pronosticos").rglob("*.json"))
    archivo.write_bytes(archivo.read_bytes().replace(b'"objetivo"', b'"objetivo" ', 1))

    class CarterasCaidas:
        def lineas(self, juego):
            raise OSError("disco no disponible")

    e = miloto
    centro = f6.CentroDeResultados(e.e3.almacen, e.e4.almacen, CarterasCaidas(), e.informes, e.e4.abrir)
    v = centro.consultar("MILOTO", completa=True)
    assert v["procedencias"]["carteras"]["estado"] == "error" and "disco no disponible" in v["procedencias"][
        "carteras"]["error"]
    assert v["procedencias"]["laboratorio"]["ilegibles"] == 1
    filas = _por_procedencia(v)
    assert filas["operacion"][0]["estado"] == "incluido"
    lab = filas["laboratorio"][0]
    assert (lab["estado"], lab["integridad"], lab["motivo"]) == ("excluido", "orden_ambiguo",
                                                                 "orden_ambiguo_por_archivo_ilegible")


def test_sin_artefactos_de_una_procedencia(tmp_path):
    e = f6.entorno(tmp_path)
    e.poblar(("MILOTO",), laboratorio=False)
    v = e.centro().consultar("MILOTO")
    assert v["procedencias"]["laboratorio"]["estado"] == "sin_artefactos"
    assert [m["procedencia"] for m in v["lineas"]] == ["operacion", "carteras"]


# ---------------------------------------------------------------------------
# Separaciones
# ---------------------------------------------------------------------------

def test_retrospectiva_separada_y_sin_cambio_automatico_de_tipo(tmp_path):
    e = f6.entorno(tmp_path)
    lab = e.e4.laboratorio()
    ultimo = e.e4.cargados("MILOTO")[-1].numero_sorteo
    r = lab.comparar_ahora(["MILOTO"], le.Protocolo(bloques=1, perfil="reducido"), corte=ultimo - 1)
    lab.generar(r["juegos"]["MILOTO"]["experimento"], "logistica_regularizada")
    centro = e.centro()
    v = centro.consultar("MILOTO", completa=True)
    assert v["filtros"]["tipo"] == "seguimiento" and v["sin_resultados_de_seguimiento"] is True
    assert v["emisiones_de_la_seleccion"] == [] and v["comparacion"]["clasificacion"] == []
    r = centro.consultar("MILOTO", Filtros(tipo="retrospectiva"), completa=True)
    assert r["sin_resultados_de_seguimiento"] is False
    assert [(f["objetivo"], f["tipo"], f["estado"]) for f in r["emisiones_de_la_seleccion"]] == [
        (ultimo, "retrospectiva", "incluido")]


def test_simulaciones_no_entran_en_la_evaluacion(miloto):
    servicio = miloto.e5.carteras()
    antes = miloto.centro().consultar("MILOTO", completa=True)
    clave = miloto.e5.almacen.carteras("MILOTO", miloto.e5.almacen.lineas("MILOTO")[0])[0].identificador
    r = servicio.ahora("simulacion", ["MILOTO"], {"cartera": clave, "simulaciones": cs.SIMULACIONES_MINIMAS,
                                                  "semilla": 3})["juegos"]["MILOTO"]
    assert r["estado"] in ("terminado", "reutilizado"), r
    despues = miloto.centro().consultar("MILOTO", completa=True)
    assert despues["emisiones_de_la_seleccion"] == antes["emisiones_de_la_seleccion"]
    for linea, c in antes["carteras"]["lineas"].items():
        assert despues["carteras"]["lineas"][linea]["filas"] == c["filas"]
    # la cartera uniforme de referencia que guarda la simulacion es una cartera mas de Producto 5, emitida con el
    # objetivo ya cargado: retrospectiva, nunca seguimiento; la simulacion en si no es una emision
    nuevas = set(despues["carteras"]["lineas"]) - set(antes["carteras"]["lineas"])
    assert nuevas and all(despues["carteras"]["lineas"][l]["filas"] == [] for l in nuevas)
    todas = [f["identificador"] for f in despues["emisiones_de_la_seleccion"]]
    assert r["resultado"] not in todas


def test_superbalota_aparte_de_los_numeros(tmp_path):
    e = f6.entorno(tmp_path)
    e.poblar(("BALOTO",))
    e.llega_el_resultado("BALOTO")
    v = e.centro().consultar("BALOTO", completa=True)
    numeros = list(e.e4.cargados("BALOTO")[-1].numeros)
    for f in v["emisiones_de_la_seleccion"]:
        assert f["estado"] == "incluido"
        assert set(f["metricas"]) == {"log_loss", "log_loss_uniforme", "brier", "brier_uniforme", "filas"}
        assert f["superbalota"] is not None and {"acierto", "log_loss"} <= set(f["superbalota"])
        r = v["resumenes"][f["clave_linea"]]
        assert r["perdidas"]["log_loss"]["modelo"] == f["metricas"]["log_loss"]
        assert r["superbalota"]["log_loss"]["modelo"] == f["superbalota"]["log_loss"]
    op = next(f for f in v["emisiones_de_la_seleccion"] if f["procedencia"] == "operacion")
    artefacto = e.e3.almacen.listar("BALOTO")[0].artefacto
    assert op["metricas"] == rmet.metricas_numeros(artefacto, numeros)


def test_sin_clasificacion_temporal_se_muestra_excluida_en_ambas_vistas():
    filas = rp._cerrar([{"tipo": "sin_clasificacion", "estado": "incluido", "motivo": None, "metricas": {"x": 1},
                         "superbalota": None, "congelado": {"y": 1}}])
    assert filas[0]["estado"] == "excluido" and filas[0]["motivo"] == "sin_clasificacion_temporal_al_generar"
    assert filas[0]["metricas"] is None and filas[0]["congelado"] is None
    assert rp.de_tipo(filas[0], "seguimiento") and rp.de_tipo(filas[0], "retrospectiva")
    assert not rp.de_tipo({"tipo": "retrospectiva"}, "seguimiento")
