"""Producto 5: construccion de carteras.

- reglas de los cuatro juegos (rangos, superbalota, multiconjuntos de
  ColorLoto con repeticion, canonizacion);
- deduplicacion de combinaciones completas (en Baloto la superbalota forma
  parte de la identidad; se informan los cinco principales repetidos);
- diversidad limitada y agotamiento del presupuesto sin relajacion oculta;
- primera combinacion = sugerencia del modelo (la uniforme no tiene);
- misma semilla y entrada -> misma cartera; generadores locales que no tocan
  el estado aleatorio global; cambiar semilla, tamano, diversidad o receta
  cambia la identidad."""
from __future__ import annotations

import random
from collections import Counter
from itertools import combinations

import numpy as np
import pytest

from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_construccion as cc
from app.application.ml import carteras_ensemble as ce
from app.application.ml import laboratorio_variables as lv
from app.application.ml import pronostico_colorloto as pcl
from tests.unit import fixtures_producto4 as f4
from tests.unit.fixtures_producto5 import fuente_colorloto, fuente_numeros

def _construir(fuente, juego, **k):
    parametros = {"con_sugerencia": True, "cantidad": 5, "semilla": 42, "diversidad": "libre", **k}
    return cc.construir(fuente, juego, **parametros)


@pytest.mark.parametrize("juego", ["BALOTO", "BALOTO_REVANCHA", "MILOTO"])
def test_combinaciones_numericas_validas(juego):
    reglas = lv.REGLAS[juego]
    r = _construir(fuente_numeros(juego), juego, cantidad=20)
    assert r["estado"] == "completa" and r["obtenidas"] == 20
    identidades = set()
    for i, c in enumerate(r["combinaciones"], start=1):
        assert c["linea"] == i
        assert len(c["numeros"]) == 5 == len(set(c["numeros"])) and c["numeros"] == sorted(c["numeros"])
        assert all(reglas.rango[0] <= x <= reglas.rango[1] for x in c["numeros"])
        if reglas.superbalota:
            assert 1 <= c["superbalota"] <= 16
        else:
            assert "superbalota" not in c
        identidades.add(cc.identidad_de_combinacion(c, False))
    assert len(identidades) == 20


def test_combinaciones_de_colorloto_son_multiconjuntos_con_repeticion():
    pesos = np.ones(42)
    pesos[[0, 1]] = 60.0  # dos pares muy probables: repeticiones dentro de la linea
    fuente = fuente_colorloto(pesos)
    r = _construir(fuente, "COLORLOTO", cantidad=10)
    assert r["estado"] == "completa"
    validos = {tuple(c) for c in fuente["candidatos"]}
    for c in r["combinaciones"]:
        assert len(c["pares"]) == 6 and all(tuple(p) in validos for p in c["pares"])
        assert c["pares"] == sorted(c["pares"])
    assert any(max(Counter(tuple(p) for p in c["pares"]).values()) > 1 for c in r["combinaciones"])
    assert any(len({p[0] for p in c["pares"]}) < 6 for c in r["combinaciones"])  # mismo numero, otro color
    assert len({cc.identidad_de_combinacion(c, True) for c in r["combinaciones"]}) == 10
    m = cc.metricas_de_cartera(r["combinaciones"], "COLORLOTO", fuente)
    assert m["repeticiones_dentro_de_lineas"] and m["cobertura"]["dominio"] == 42
    assert sum(f["apariciones"] for f in m["frecuencia_de_uso"]) == 60


def test_identidad_de_baloto_incluye_la_superbalota_y_se_informan_los_principales_repetidos():
    pesos = np.full(43, 1e-6)
    pesos[[2, 9, 18, 27, 36]] = 1.0  # practicamente siempre los mismos cinco numeros
    r = _construir(fuente_numeros("BALOTO", pesos), "BALOTO", cantidad=6, con_sugerencia=False)
    assert r["estado"] == "completa"
    principales = {tuple(c["numeros"]) for c in r["combinaciones"]}
    assert principales == {(3, 10, 19, 28, 37)}
    assert len({c["superbalota"] for c in r["combinaciones"]}) == 6  # solo cambia la superbalota
    m = cc.metricas_de_cartera(r["combinaciones"], "BALOTO", fuente_numeros("BALOTO", pesos))
    assert m["lineas_que_repiten_los_cinco_principales"] == [[1, 2, 3, 4, 5, 6]]
    assert r["rechazos"].get("duplicada", 0) > 0  # las repeticiones completas se rechazan


def test_diversidad_limitada_respeta_el_limite_en_todos_los_pares():
    for juego, fuente, limite in (("BALOTO", fuente_numeros("BALOTO"), 3), ("MILOTO", fuente_numeros("MILOTO"), 3),
                                  ("COLORLOTO", fuente_colorloto(), 4)):
        r = _construir(fuente, juego, cantidad=20, diversidad="limitada")
        assert r["estado"] == "completa"
        colores = juego == "COLORLOTO"
        for a, b in combinations(r["combinaciones"], 2):
            assert cc.compartidos(a, b, colores) <= limite
        m = cc.metricas_de_cartera(r["combinaciones"], juego, fuente)
        assert m["coincidencias_entre_lineas"]["maximo"] <= limite
        assert len(m["coincidencias_entre_lineas"]["pares_de_lineas"]) == 190


def test_compartidos_de_colorloto_con_multiplicidad():
    a = {"pares": [[1, "AZUL"], [1, "AZUL"], [2, "ROJO"], [3, "VERDE"], [4, "NEGRO"], [5, "BLANCO"]]}
    b = {"pares": [[1, "AZUL"], [2, "ROJO"], [2, "ROJO"], [3, "VERDE"], [6, "NEGRO"], [7, "BLANCO"]]}
    assert cc.compartidos(a, b, True) == 3 == pcl.coincidencias(a["pares"], b["pares"])
    assert cc.compartidos(a, a, True) == 6


def test_agotamiento_del_presupuesto_sin_relajacion_oculta():
    pesos = np.full(39, 1e-9)
    pesos[:7] = 1.0  # casi todo el peso en 7 numeros: con diversidad limitada caben muy pocas lineas
    fuente = fuente_numeros("MILOTO", pesos)
    r = _construir(fuente, "MILOTO", cantidad=20, diversidad="limitada")
    assert r["estado"] == "parcial" and r["obtenidas"] < 20 and r["solicitadas"] == 20
    assert r["intentos"] == cc.PRESUPUESTO_DE_INTENTOS and r["rechazos"]["diversidad"] > 0
    assert "no se relajo" in r["motivo"]
    for a, b in combinations(r["combinaciones"], 2):
        assert len(set(a["numeros"]) & set(b["numeros"])) <= 3
    libre = _construir(fuente, "MILOTO", cantidad=20, diversidad="libre")
    assert libre["estado"] == "completa"  # sin diversidad se completa: la parcial no se debia a otra cosa


def test_la_primera_combinacion_es_la_sugerencia_del_modelo():
    instantanea = lv.validar_instantanea("BALOTO", f4.historico("BALOTO", 90))
    fuente = ce.fuente(instantanea, "logistica_regularizada", "reducido")
    r = _construir(fuente, "BALOTO")
    primera = r["combinaciones"][0]
    marginal = dict(zip(fuente["candidatos"], fuente["probabilidades"]))
    esperado = sorted(sorted(marginal, key=lambda c: (-marginal[c], c))[:5])
    sb = dict(zip(fuente["superbalota"]["candidatos"], fuente["superbalota"]["probabilidades"]))
    assert primera["origen"] == "sugerencia_del_modelo" and primera["numeros"] == esperado
    assert primera["superbalota"] == min(sb, key=lambda c: (-sb[c], c))
    assert all(c["origen"] == "muestreo_ponderado" for c in r["combinaciones"][1:])
    uniforme = _construir(fuente_numeros("BALOTO"), "BALOTO", con_sugerencia=False)
    assert all(c["origen"] == "muestreo_ponderado" for c in uniforme["combinaciones"])
    color = fuente_colorloto(np.arange(1, 43))
    rc = _construir(color, "COLORLOTO")
    dist = {tuple(c): p for c, p in zip(color["candidatos"], color["probabilidades"])}
    assert rc["combinaciones"][0]["pares"] == [list(p) for p in pcl.multiconjunto_mas_probable(dist)]


def test_parametros_validados():
    for cantidad, semilla, diversidad in ((0, 1, "libre"), (21, 1, "libre"), (5, -1, "libre"), (5, 2**32, "libre"),
                                          (5, 1, "otra"), (True, 1, "libre"), ("5", 1, "libre")):
        with pytest.raises(cc.ParametrosNoValidos):
            cc.validar_parametros(cantidad, semilla, diversidad)
    assert cc.validar_parametros(20, 2**32 - 1, "limitada") == (20, 2**32 - 1, "limitada")
    with pytest.raises(cc.ParametrosNoValidos):
        cc.pesos_normalizados([0.5, float("nan")])


def test_misma_semilla_misma_cartera_sin_tocar_el_rng_global():
    random.seed(1234)
    np.random.seed(4321)
    estado_python, estado_numpy = random.getstate(), np.random.get_state()
    fuente = fuente_numeros("BALOTO", np.arange(1, 44))
    a = _construir(fuente, "BALOTO", cantidad=10, diversidad="limitada")
    b = _construir(fuente, "BALOTO", cantidad=10, diversidad="limitada")
    assert a == b
    assert random.getstate() == estado_python
    actual = np.random.get_state()
    assert actual[0] == estado_numpy[0] and np.array_equal(actual[1], estado_numpy[1]) and actual[2:] == estado_numpy[2:]
    otra = _construir(fuente, "BALOTO", cantidad=10, diversidad="limitada", semilla=43)
    assert otra["combinaciones"][1:] != a["combinaciones"][1:]
    # los flujos de construccion y de simulacion son distintos, y tambien los de cada juego
    x = cc.flujos(42, cc.FLUJO_CONSTRUCCION, "BALOTO")[0].random(4)
    assert not np.array_equal(x, cc.flujos(42, cc.FLUJO_SIMULACION, "BALOTO", 1)[0].random(4))
    assert not np.array_equal(x, cc.flujos(42, cc.FLUJO_CONSTRUCCION, "BALOTO_REVANCHA")[0].random(4))
    assert not np.array_equal(x, cc.flujos(42, cc.FLUJO_CONSTRUCCION, "BALOTO")[1].random(4))


def test_el_muestreo_por_lotes_consume_el_mismo_orden():
    pesos = cc.pesos_normalizados(np.arange(1, 44))
    rng = cc.flujos(7, cc.FLUJO_SIMULACION, "BALOTO", 1)[0]
    todo = cc.muestrear_sin_reemplazo(rng, pesos, 5, filas=100)
    rng = cc.flujos(7, cc.FLUJO_SIMULACION, "BALOTO", 1)[0]
    partes = np.vstack([cc.muestrear_sin_reemplazo(rng, pesos, 5, filas=f) for f in (33, 33, 34)])
    assert np.array_equal(todo, partes)
    assert all(len(set(fila.tolist())) == 5 for fila in todo)


def test_cambiar_semilla_tamano_diversidad_o_receta_cambia_la_identidad():
    instantanea = lv.validar_instantanea("MILOTO", f4.historico("MILOTO", 70))
    base = dict(modelo="logistica_regularizada", perfil="reducido", cantidad=5, semilla=42, diversidad="libre")

    def clave(**cambios):
        p = {**base, **cambios}
        return ca.huella(ca.identidad_de_cartera(instantanea, p["modelo"], p["perfil"], p["cantidad"], p["semilla"],
                                                 p["diversidad"]))
    claves = [clave(), clave(semilla=43), clave(cantidad=6), clave(diversidad="limitada"),
              clave(modelo="hgb_clasificador"), clave(perfil="predeterminado"), clave(modelo=ce.ID_ENSEMBLE)]
    assert len(set(claves)) == len(claves)
    assert clave() == clave()  # la clave se calcula antes de entrenar y es estable
    otra = lv.validar_instantanea("MILOTO", f4.historico("MILOTO", 71))
    assert ca.huella(ca.identidad_de_cartera(otra, "logistica_regularizada", "reducido", 5, 42, "libre")) != clave()
    linea = ca.linea_de("MILOTO", "logistica_regularizada", "reducido", 5, "libre", 42)
    assert linea["id"] == "logistica_regularizada-v1-n5-libre-s42-reducido"
    assert ca.linea_de("MILOTO", "uniforme", "predeterminado", 3, "limitada", 7)["id"] == "uniforme-v1-n3-limitada-s7"


def test_cartera_completa_desde_el_vector_fuente_y_metricas():
    instantanea = lv.validar_instantanea("COLORLOTO", f4.historico("COLORLOTO", 70))
    identidad = ca.identidad_de_cartera(instantanea, "uniforme_paleta", "reducido", 8, 3, "limitada")
    fuente = ce.fuente(instantanea, "uniforme_paleta", "reducido")
    cuerpo = ca.cuerpo_de_cartera(instantanea, identidad, fuente)
    k = cuerpo["cartera"]
    assert k["estado"] == "completa" and k["objetivo"] == instantanea.corte + 1 and len(k["combinaciones"]) == 8
    assert k["combinaciones"][0]["origen"] == "muestreo_ponderado"  # la uniforme no tiene sugerencia
    assert "No conserva las marginales" in k["nota"] and "premio mayor" in k["aviso"]
    assert cuerpo["clave_de_entrada"] == ca.huella(identidad)
    assert cuerpo == ca.cuerpo_de_cartera(instantanea, identidad, fuente)
    csv = ca.csv_de_cartera(ca.componer(cuerpo, "generacion", {"generado_en": "x"}))
    assert csv.splitlines()[0].startswith("juego,corte,objetivo,modelo")
    assert len(csv.splitlines()) == 9


def test_csv_sin_formulas_ejecutables():
    assert ca._celda("=1+1") == "'=1+1" and ca._celda("+5") == "'+5" and ca._celda("-3") == "'-3"
    assert ca._celda("@x") == "'@x" and ca._celda("3 7 9") == "3 7 9" and ca._celda(None) == ""


def test_un_vector_fuente_constante_no_tiene_sugerencia():
    """El modelo combinado con peso 1 para la uniforme da marginales iguales: su
    «sugerencia» seria el desempate por numero (1-2-3-4-5). No se presenta como
    sugerencia: todas las lineas se muestrean y la cartera lo dice."""
    instantanea = lv.validar_instantanea("BALOTO", f4.historico("BALOTO", 70))
    constante = {**ce.fuente(instantanea, "uniforme"), "modelo": ce.ID_ENSEMBLE}
    assert not cc.fuente_informativa(constante)
    identidad = ca.identidad_de_cartera(instantanea, ce.ID_ENSEMBLE, "reducido", 5, 42, "libre")
    cuerpo = ca.cuerpo_de_cartera(instantanea, identidad, constante)
    k = cuerpo["cartera"]
    assert k["primera_combinacion"] == "sin_sugerencia_vector_fuente_constante"
    assert all(c["origen"] == "muestreo_ponderado" for c in k["combinaciones"])
    assert k["combinaciones"][0]["numeros"] != [1, 2, 3, 4, 5]
    informativa = ce.fuente(instantanea, "logistica_regularizada", "reducido")
    assert cc.fuente_informativa(informativa)
    otra = ca.cuerpo_de_cartera(instantanea, ca.identidad_de_cartera(instantanea, "logistica_regularizada", "reducido",
                                                                     5, 42, "libre"), informativa)
    assert otra["cartera"]["primera_combinacion"] == "sugerencia_del_modelo"
    assert otra["cartera"]["combinaciones"][0]["origen"] == "sugerencia_del_modelo"
    uniforme = ca.cuerpo_de_cartera(instantanea, ca.identidad_de_cartera(instantanea, "uniforme", "reducido", 5, 42,
                                                                         "libre"), ce.fuente(instantanea, "uniforme"))
    assert uniforme["cartera"]["primera_combinacion"] == "sin_sugerencia_modelo_uniforme"
