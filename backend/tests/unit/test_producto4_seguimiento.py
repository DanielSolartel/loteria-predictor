"""Producto 4: seguimiento de los pronosticos del laboratorio por linea de
modelo y objetivo (primera emision sellada, tipos separados, historico
cambiado o no disponible, sin elegir despues la version mas acertada)."""
from __future__ import annotations

import dataclasses

import pytest

from app.application.ml import laboratorio_evaluacion as le
from tests.unit import fixtures_producto4 as f4

REDUCIDO = le.Protocolo(bloques=1, perfil="reducido")


@pytest.fixture
def entorno(tmp_path):
    return f4.entorno(tmp_path)


def _comparar(lab, juego="MILOTO", corte=None):
    return lab.comparar_ahora([juego], REDUCIDO, corte=corte)["juegos"][juego]["experimento"]


def _corregir(entorno, juego, posicion):
    j = entorno.juegos.obtener_por_codigo(juego)
    datos = entorno.cargados(juego)
    r = datos[posicion]
    nuevos = tuple(n for n in range(1, 40) if n not in r.numeros)[:5]
    entorno.resultados.numericos[j.id] = [*datos[:posicion], dataclasses.replace(r, numeros=nuevos),
                                          *datos[posicion + 1:]]


def test_lineas_separadas_tipos_e_interseccion(entorno):
    lab = entorno.laboratorio()
    clave = _comparar(lab)
    a = lab.generar(clave, "logistica_regularizada")
    b = lab.generar(clave, "hgb_clasificador")
    assert a.artefacto["generacion"]["clasificacion_temporal"]["tipo"] == "pronostico_sobre_el_ultimo_dato_disponible"
    pendiente = lab.seguimiento("MILOTO")
    assert {f["estado"] for s in pendiente["lineas"].values() for f in s["filas"]} == {"pendiente"}
    corte = entorno.cargados("MILOTO")[-3].numero_sorteo  # el objetivo corte + 1 ya esta cargado
    retro = lab.generar(_comparar(lab, corte=corte), "logistica_regularizada")
    assert retro.artefacto["generacion"]["clasificacion_temporal"]["tipo"] == "simulacion_retrospectiva"
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    s = lab.seguimiento("MILOTO")
    la_ = s["lineas"][a.linea]
    assert la_["por_tipo"]["seguimiento"]["incluidos"] == 1 and la_["por_tipo"]["retrospectiva"]["incluidos"] == 1
    assert s["lineas"][b.linea]["por_tipo"]["seguimiento"]["incluidos"] == 1
    assert s["comparacion"]["objetivos_comunes"] == [a.objetivo]
    assert s["comparacion"]["totales"] == {a.linea: 1, b.linea: 1}
    fila = next(f for f in la_["filas"] if f["objetivo"] == a.objetivo)
    observado = entorno.cargados("MILOTO")[-1]
    assert fila["coincidencias"]["numeros"] == len(set(observado.numeros) & set(a.artefacto["pronostico"]["numeros_sugeridos"]))
    assert fila["metricas"]["log_loss"] > 0 and "superbalota" not in fila["metricas"]
    assert lab.generar(clave, "logistica_regularizada").artefacto == a.artefacto  # el pronostico no cambia


def test_primera_emision_no_evaluable_se_excluye_sin_avanzar_a_otra(entorno):
    lab = entorno.laboratorio()
    primera = lab.generar(_comparar(lab), "logistica_regularizada")
    _corregir(entorno, "MILOTO", 10)  # el historico hasta el corte cambia
    segunda = lab.generar(_comparar(lab), "logistica_regularizada")
    assert segunda.objetivo == primera.objetivo and segunda.secuencia == 2
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    fila = lab.seguimiento("MILOTO")["lineas"][primera.linea]["filas"][0]
    assert fila["identificador"] == primera.identificador and fila["versiones"] == 2
    assert fila["estado"] == "excluido" and fila["motivo"] == "historico_hasta_el_corte_cambio"


def test_historico_no_disponible_se_distingue_del_cambio(entorno):
    lab = entorno.laboratorio()
    g = lab.generar(_comparar(lab), "logistica_regularizada")
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    j = entorno.juegos.obtener_por_codigo("MILOTO")
    entorno.resultados.numericos[j.id] = [r for r in entorno.cargados("MILOTO") if r.numero_sorteo > g.artefacto["datos"]["corte"]]
    fila = lab.seguimiento("MILOTO")["lineas"][g.linea]["filas"][0]
    assert fila["estado"] == "excluido" and fila["motivo"] == "historico_hasta_el_corte_no_disponible"


def test_archivo_ilegible_hace_ambiguo_el_orden(entorno):
    lab = entorno.laboratorio()
    primera = lab.generar(_comparar(lab), "logistica_regularizada")
    _corregir(entorno, "MILOTO", 12)
    segunda = lab.generar(_comparar(lab), "logistica_regularizada")
    ruta = next((entorno.directorio / "pronosticos" / "MILOTO" / primera.linea).glob(f"*-{primera.identificador}.json"))
    ruta.write_bytes(ruta.read_bytes()[:-10])
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    s = lab.seguimiento("MILOTO")["lineas"][primera.linea]
    fila = next(f for f in s["filas"] if f["objetivo"] == segunda.objetivo)
    assert fila["estado"] == "excluido" and fila["motivo"] == "orden_ambiguo_por_archivo_ilegible"
    assert s["objetivos_ambiguos"] == 1


def test_sin_base_el_seguimiento_lo_indica(entorno):
    lab = entorno.laboratorio()
    g = lab.generar(_comparar(lab), "hgb_clasificador")
    entorno.base_caida = True
    s = lab.seguimiento("MILOTO")
    assert s["base"] == "no_disponible" and s["lineas"][g.linea]["filas"][0]["estado"] == "sin_base"


def test_colorloto_y_superbalota_en_el_seguimiento(entorno):
    lab = entorno.laboratorio()
    color = lab.generar(_comparar(lab, "COLORLOTO"), "poisson_regularizado")
    baloto = lab.generar(_comparar(lab, "BALOTO"), "hgb_clasificador")
    assert len(color.artefacto["pronostico"]["pares"]) == 6
    assert baloto.artefacto["superbalota"]["estrategia"] == "frecuencia_con_suavizado_de_laplace"
    for juego in ("COLORLOTO", "BALOTO"):
        entorno.anadir(juego, entorno.siguiente(juego))
    fila_c = lab.seguimiento("COLORLOTO")["lineas"][color.linea]["filas"][0]
    assert fila_c["estado"] == "incluido" and 0 <= fila_c["coincidencias"]["pares"] <= 6
    fila_b = lab.seguimiento("BALOTO")["lineas"][baloto.linea]["filas"][0]
    assert fila_b["estado"] == "incluido" and "superbalota" in fila_b["metricas"]
