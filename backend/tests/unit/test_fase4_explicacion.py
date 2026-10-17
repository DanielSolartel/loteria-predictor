"""Fase 4 - rankings fuertes/debiles, papel de cada combinacion, importancias
globales del estimador persistido, integridad, reproduccion y proyeccion a la
tabla `predicciones` (`predicciones_explicacion`). Datos sinteticos; nada es
real."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import modelo as mdl
from app.application.ml import predicciones_explicacion as pe
from tests.unit import fixtures_fase4 as f4

NOMBRES = list(lv.NOMBRES_VARIABLES_NUMEROS)
INFORMATIVA = NOMBRES.index("frecuencia_acumulada")


@pytest.fixture(scope="module")
def generado(tmp_path_factory):
    """Una cartera con explicacion por juego: Baloto con version registrada
    (Random Forest), MiLoto con receta reajustada y ColorLoto uniforme."""
    e = f4.entorno(tmp_path_factory.mktemp("f4e"))
    lab = e.laboratorio()
    r = e.registrar(lab, "BALOTO", "random_forest_clasificador")
    e.configurar("BALOTO", "random_forest_clasificador", registrado=r["modelo_registrado"], cantidad=3)
    e.configurar("MILOTO", "logistica_regularizada", cantidad=3)
    e.configurar("COLORLOTO", "uniforme_paleta", cantidad=4)
    carteras = e.carteras()
    centro = e.centro(carteras)
    salida = {}
    for juego in ("BALOTO", "MILOTO", "COLORLOTO"):
        centro.ahora(juego)
        p = centro.consultar(juego)["prediccion"]
        salida[juego] = {"cartera": carteras.cartera(p["clave"]).artefacto, "explicacion": p["explicacion"], "detalle": p}
    yield salida
    f4.limpiar()


# ---------------------------------------------------------------------------
# Rankings: unidades y denominadores
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("juego,universo", [("BALOTO", 43), ("MILOTO", 39)])
def test_rankings_de_numeros_con_marginales_que_suman_cinco(generado, juego, universo):
    rk = pe.rankings(generado[juego]["cartera"]["fuente"], juego)
    n = rk["numeros"]
    assert n["universo"] == universo and n["por_extremo"] == 10 and len(n["todos"]) == universo
    assert n["suma"] == pytest.approx(5) and n["denominador"] == f"{universo} números; uniforme = 5/{universo}"
    assert "suman 5" in n["unidad"]
    p = [f["probabilidad"] for f in n["todos"]]
    assert p == sorted(p, reverse=True) and [f["posicion"] for f in n["todos"]] == list(range(1, universo + 1))
    assert n["fuertes"] == n["todos"][:10] and n["debiles"] == list(reversed(n["todos"][-10:]))
    for f in n["todos"]:
        assert f["uniforme"] == pytest.approx(5 / universo)
        assert f["diferencia"] == pytest.approx(f["probabilidad"] - 5 / universo)
        assert f["razon"] == pytest.approx(f["probabilidad"] / (5 / universo))
    assert rk["objetivo"] == generado[juego]["cartera"]["cartera"]["objetivo"]


def test_superbalota_en_seccion_aparte_con_su_propio_denominador(generado):
    rk = pe.rankings(generado["BALOTO"]["cartera"]["fuente"], "BALOTO")
    s = rk["superbalota"]
    assert s["universo"] == 16 and s["por_extremo"] == 4 and s["suma"] == pytest.approx(1)
    assert s["denominador"] == "16 superbalotas; uniforme = 1/16"
    assert {f["candidato"] for f in rk["numeros"]["todos"]} == set(range(1, 44))
    assert "superbalota" not in pe.rankings(generado["MILOTO"]["cartera"]["fuente"], "MILOTO")


def test_colorloto_pares_y_por_separado_numeros_y_colores_con_sus_denominadores(generado):
    rk = pe.rankings(generado["COLORLOTO"]["cartera"]["fuente"], "COLORLOTO")
    pares, numeros, colores = rk["pares"], rk["numeros"], rk["colores"]
    paleta = len(colores["todos"])
    assert pares["universo"] == 7 * paleta and pares["suma"] == pytest.approx(1)
    assert pares["denominador"] == f"{7 * paleta} pares número-color"
    assert all(f["multiplicidad_esperada"] == pytest.approx(6 * f["probabilidad"]) for f in pares["todos"])
    assert "no es la probabilidad de que el par aparezca al menos una vez" in pares["nota"]
    # Nunca 10 numeros en un universo de 7: los numeros se listan completos (7), sin extremos de 10.
    assert numeros["universo"] == 7 and len(numeros["todos"]) == 7 and "fuertes" not in numeros
    assert numeros["denominador"] == "7 números" and colores["universo"] == paleta
    assert sum(f["probabilidad"] for f in numeros["todos"]) == pytest.approx(1)
    assert sum(f["probabilidad"] for f in colores["todos"]) == pytest.approx(1)
    assert all(isinstance(f["candidato"], list) and len(f["candidato"]) == 2 for f in pares["todos"])


def test_empates_se_declaran_y_un_vector_ordenado_no_los_tiene(generado):
    uniforme = pe.rankings(generado["COLORLOTO"]["cartera"]["fuente"], "COLORLOTO")
    assert uniforme["pares"]["nota_empates"] == pe.NOTA_EMPATES
    assert uniforme["numeros"]["nota_empates"] == pe.NOTA_EMPATES_LISTA
    fuente = {"candidatos": list(range(1, 44)), "probabilidades": [5 * (44 - i) / 946 for i in range(1, 44)],
              "masa": 5, "objetivo": 10, "calculado_hasta_sorteo": 9}
    ordenado = pe.rankings(fuente, "BALOTO")["numeros"]
    assert ordenado["nota_empates"] is None and ordenado["empate_en_el_limite"] == {"fuertes": False, "debiles": False}
    assert [f["candidato"] for f in ordenado["fuertes"]] == list(range(1, 11))


# ---------------------------------------------------------------------------
# Combinaciones: sugerencia del modelo frente a lineas muestreadas
# ---------------------------------------------------------------------------

def test_lineas_muestreadas_no_heredan_marginales(generado):
    for juego in ("BALOTO", "MILOTO", "COLORLOTO"):
        cartera = generado[juego]["cartera"]
        filas = pe.combinaciones(cartera)
        assert len(filas) == len(cartera["cartera"]["combinaciones"])
        for fila, original in zip(filas, cartera["cartera"]["combinaciones"]):
            if original.get("origen") == "sugerencia_del_modelo":
                assert fila["papel"] == "sugerencia del modelo" and fila["probabilidades_de_sus_elementos"]
            else:
                assert fila["papel"] == "línea muestreada" and "probabilidades_de_sus_elementos" not in fila
                assert "no heredan las probabilidades" in fila["detalle"]
    sugerencia = pe.combinaciones(generado["BALOTO"]["cartera"])[0]
    fuente = generado["BALOTO"]["cartera"]["fuente"]
    p = dict(zip(fuente["candidatos"], fuente["probabilidades"]))
    assert sugerencia["probabilidades_de_sus_elementos"] == [pytest.approx(p[n]) for n in sugerencia["numeros"]]
    q = dict(zip(fuente["superbalota"]["candidatos"], fuente["superbalota"]["probabilidades"]))
    assert sugerencia["probabilidad_de_su_superbalota"] == pytest.approx(q[sugerencia["superbalota"]])
    assert sugerencia["unidad_de_los_elementos"] == "probabilidad marginal de aparición de cada número"


# ---------------------------------------------------------------------------
# Importancias globales del estimador persistido
# ---------------------------------------------------------------------------

def _datos(n=1500, semilla=3):
    rng = np.random.default_rng(semilla)
    X = rng.random((n, 8))
    X[:, 0] = rng.integers(1, 44, size=n)
    y = (X[:, INFORMATIVA] + 0.05 * rng.normal(size=n) > 0.6).astype(int)
    return X, y


def _calibrado(familia, modelo, parametros):
    X, y = _datos()
    calibracion = np.arange(len(y)) >= int(0.8 * len(y))
    est = mdl.calibrador_cronologico(mdl.pipeline_laboratorio(familia, modelo, parametros), calibracion)
    return est.fit(X, y)


def test_bosque_asocia_cada_importancia_a_su_variable():
    p = {**lm.parametros_de(lm.CATALOGO["random_forest_clasificador"], "reducido"), "max_depth": 6,
         "min_samples_leaf": 5}
    r = pe.importancias_globales(_calibrado("bosques", "random_forest_clasificador", p), NOMBRES)
    assert r["estado"] == "disponible" and r["tipo"] == "importancia_por_reduccion_de_impureza" and r["calibrado"]
    assert [v["variable"] for v in r["valores"]] == NOMBRES and all(v["columnas"] == 1 for v in r["valores"])
    assert sum(v["valor"] for v in r["valores"]) == pytest.approx(1)
    mayor = max(r["valores"], key=lambda v: v["valor"])
    assert mayor["variable"] == "frecuencia_acumulada" and mayor["valor"] > 0.5
    assert r["valores"][0]["es_identidad"] and "GLOBALES" in r["aviso"] and "no por qué un candidato" in r["aviso"]


def test_lineal_resume_la_identidad_one_hot_y_nombra_los_coeficientes():
    p = lm.parametros_de(lm.CATALOGO["logistica_regularizada"], "reducido")
    r = pe.importancias_globales(_calibrado("lineal", "logistica_regularizada", p), NOMBRES)
    assert r["estado"] == "disponible" and r["tipo"] == "coeficiente"
    identidad = r["valores"][0]
    assert identidad["variable"] == "candidato" and identidad["valor"] is None and identidad["columnas"] == 43
    assert set(identidad["resumen"]) == {"minimo", "maximo", "media_absoluta"}
    resto = {v["variable"]: v["valor"] for v in r["valores"][1:]}
    assert list(resto) == NOMBRES[1:]
    assert max(resto, key=lambda k: abs(resto[k])) == "frecuencia_acumulada" and resto["frecuencia_acumulada"] > 0


def test_boosting_sin_importancias_y_estructuras_no_reconocidas_quedan_no_disponibles():
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.linear_model import LogisticRegression

    p = lm.parametros_de(lm.CATALOGO["hgb_clasificador"], "reducido")
    hgb = pe.importancias_globales(_calibrado("arboles", "hgb_clasificador", p), NOMBRES)
    assert hgb["estado"] == "no_disponible" and hgb["estimador"] == "HistGradientBoostingClassifier"
    assert "no se calcula una importancia por permutación" in hgb["motivo"]
    X, y = _datos(300)
    assert pe.importancias_globales(LogisticRegression().fit(X, y), NOMBRES)["estado"] == "no_disponible"
    varios = CalibratedClassifierCV(mdl.pipeline_laboratorio("lineal", "logistica_regularizada",
                                                             lm.parametros_de(lm.CATALOGO["logistica_regularizada"],
                                                                              "reducido")), cv=3).fit(X, y)
    assert "varios clasificadores" in pe.importancias_globales(varios, NOMBRES)["motivo"]


def test_sin_estimador_persistido_se_dice_por_que_y_no_se_reajusta(generado):
    for juego, texto in (("COLORLOTO", "no aplica: la referencia uniforme"),
                         ("MILOTO", "se ajustó al generarla y no se conserva")):
        assert texto in pe.importancias_sin_estimador(generado[juego]["cartera"])["motivo"]
        assert generado[juego]["explicacion"]["importancias"]["estado"] == "no_disponible"
    fingida = {"linea": {"modelo": "actual_frecuencia_contraida"}}
    assert "cuenta frecuencias suavizadas" in pe.importancias_sin_estimador(fingida)["motivo"]
    fingida = {"linea": {"modelo": "ensemble_temporal"}}
    assert "pesos de la mezcla" in pe.importancias_sin_estimador(fingida)["motivo"]


def test_version_registrada_explica_con_el_estimador_persistido(generado):
    e = generado["BALOTO"]["explicacion"]
    assert e["importancias"]["estado"] == "disponible" and e["importancias"]["estimador"] == "RandomForestClassifier"
    assert [v["variable"] for v in e["importancias"]["valores"]] == NOMBRES
    metodo = e["metodo"]
    assert metodo["entrenamiento"]["estimador"].startswith("versión registrada congelada")
    assert metodo["registrado"]["numero"] == 1 and metodo["registrado"]["sha256_estimador"]
    assert metodo["variables"]["nombres"] == NOMBRES and metodo["transformacion"]["tipo"]


def test_variables_de_los_candidatos_solo_con_sorteos_hasta_el_corte(generado):
    cartera = generado["BALOTO"]["cartera"]
    va = generado["BALOTO"]["explicacion"]["variables"]
    assert va["calculado_hasta_sorteo"] == cartera["datos"]["corte"] and va["usadas_por_el_modelo"]
    assert va["nombres"] == NOMBRES[1:] and len(va["por_candidato"]) == 43
    assert all(len(v) == 7 for v in va["por_candidato"].values())
    assert generado["COLORLOTO"]["explicacion"]["variables"]["usadas_por_el_modelo"] is False
    assert pe.usa_variables_del_laboratorio("random_forest_clasificador")
    assert not pe.usa_variables_del_laboratorio("uniforme")
    assert not pe.usa_variables_del_laboratorio("actual_frecuencia_contraida")


# ---------------------------------------------------------------------------
# Integridad, reproduccion y proyeccion
# ---------------------------------------------------------------------------

def test_clave_independiente_de_la_generacion_y_sello_que_detecta_cambios(generado):
    a = generado["MILOTO"]["explicacion"]
    assert pe.integro(a)
    otra = pe.componer(pe.cuerpo_de(a), {"generado_en": "2030-01-01T00:00:00+00:00", "origen": "otro"})
    assert otra["clave"] == a["clave"] and otra["sello"] != a["sello"] and pe.integro(otra)
    alterada = copy.deepcopy(a)
    alterada["rankings"]["numeros"]["todos"][0]["probabilidad"] += 1e-9
    assert not pe.integro(alterada)
    sin_sello = copy.deepcopy(a)
    sin_sello["generacion"]["origen"] = "manipulado"
    assert not pe.integro(sin_sello)
    assert not pe.integro({**a, "esquema": "otro/1"})


def test_reproduccion_exacta_y_deteccion_de_diferencias(generado):
    for juego in ("BALOTO", "MILOTO", "COLORLOTO"):
        r = pe.reproducir(generado[juego]["explicacion"], generado[juego]["cartera"])
        assert r["exacta"] and r["distintos"] == []
    a = copy.deepcopy(generado["MILOTO"]["explicacion"])
    a["variables"]["por_candidato"]["1"][0] = 99.0
    assert pe.reproducir(a, generado["MILOTO"]["cartera"])["distintos"] == ["variables"]
    ajena = pe.reproducir(generado["MILOTO"]["explicacion"], generado["BALOTO"]["cartera"])
    assert ajena["exacta"] is False and "no es el de la explicación" in ajena["motivo"]


def test_proyeccion_a_la_tabla_predicciones_sin_escribirla_y_sin_nivel_de_confianza(generado):
    for juego in ("BALOTO", "COLORLOTO"):
        x = pe.proyeccion_tabla(generado[juego]["cartera"], generado[juego]["explicacion"])
        c = x["columnas"]
        assert x["escrita"] is False and x["tabla"] == "predicciones" and "RESERVADA" in x["decision"]
        assert c["nivel_confianza"] is None and "vacío a propósito" in x["notas"]["nivel_confianza"]
        principal = x and (generado[juego]["explicacion"]["rankings"].get("pares")
                           or generado[juego]["explicacion"]["rankings"]["numeros"])
        assert c["numeros_fuertes"] == [f["candidato"] for f in principal["fuertes"]]
        assert c["sorteo_objetivo"] == generado[juego]["cartera"]["cartera"]["objetivo"]
        assert generado[juego]["explicacion"]["clave"][:12] in c["explicacion"]
    assert "pares número-color" in pe.proyeccion_tabla(generado["COLORLOTO"]["cartera"], None)["notas"]["numeros_fuertes"]
    assert "reg1" in pe.proyeccion_tabla(generado["BALOTO"]["cartera"], None)["columnas"]["modelo"]


def test_explicacion_conserva_los_avisos_y_el_estado_de_uso(generado):
    a = generado["BALOTO"]["explicacion"]
    assert a["estado_de_uso"] == "experimental_no_acreditado" and a["contexto"]["AUTORIZA_EVALUACION"] is False
    assert a["esquema"] == pe.ESQUEMA and a["version"] == pe.VERSION
    assert any("no prueba que el modelo acierte" in x for x in a["avisos"])
    assert a["cartera"]["sha256_fuente"] == pe.huella(generado["BALOTO"]["cartera"]["fuente"])
