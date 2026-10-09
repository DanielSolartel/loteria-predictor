"""Producto 6: comparacion directa, evolucion, calibracion y carteras (modulos
puros, con filas sinteticas).

- interseccion exacta de los objetivos admitidos de TODAS las lineas
  elegidas; una linea sin muestra deja «sin muestra comun» (no se retira);
  universos incompatibles fuera con su motivo; la uniforme visible cuando gana;
- diferencia = modelo - uniforme y su acumulado sobre la misma serie;
- calibracion con intervalos fijos, limites 0 y 1, intervalos vacios None,
  pares repetidos de ColorLoto (multiplicidad / 6) y los dos denominadores;
- carteras comparadas solo con el mismo numero de combinaciones."""
from __future__ import annotations

import math

import pytest

from app.application.ml import resultados_calibracion as rc
from app.application.ml import resultados_evaluacion as re_
from app.application.ml import resultados_procedencias as rp


def _fila(linea: str, objetivo: int, log_loss: float, uniforme: float = 0.4, *, estado="incluido", tipo="seguimiento",
          universo="numeros:39", motivo=None, aciertos=None, superbalota=None):
    return {"clave_linea": linea, "objetivo": objetivo, "tipo": tipo, "estado": estado, "motivo": motivo,
            "aciertos": aciertos, "de": 5 if aciertos is not None else None, "superbalota": superbalota,
            "universo": {"clave": universo}, "congelado": None,
            "metricas": {"log_loss": log_loss, "log_loss_uniforme": uniforme, "brier": log_loss / 4,
                         "brier_uniforme": uniforme / 4} if estado == "incluido" else None}


def test_interseccion_exacta_de_las_lineas_elegidas():
    filas = {"a": [_fila("a", o, 0.3) for o in (1, 2, 3, 4)],
             "b": [_fila("b", o, 0.5) for o in (2, 3, 5)],
             "c": [_fila("c", o, 0.45) for o in (1, 2, 3)]}
    c = re_.comparar(["a", "b", "c"], filas, "MILOTO", "seguimiento")
    assert c["estado"] == "con_muestra_comun" and c["objetivos_comunes"] == [2, 3]
    assert c["totales_individuales"] == {"a": 4, "b": 3, "c": 3}
    fuera = {(f["objetivo"], f["linea"]) for f in c["fuera_de_la_muestra_comun"]}
    assert fuera == {(1, "b"), (4, "b"), (4, "c"), (5, "a"), (5, "c")}
    assert all(f["motivo"] == "sin_emision_de_la_linea_para_el_objetivo" for f in c["fuera_de_la_muestra_comun"])
    assert all(a["incluidos"] == 2 for a in c["por_linea"].values())
    orden = [f["linea"] for f in c["clasificacion"]]
    assert orden == ["a", "uniforme", "c", "b"]  # la uniforme visible y por delante de las peores
    b = next(f for f in c["clasificacion"] if f["linea"] == "b")
    assert b["veredicto"] == "la_uniforme_fue_mejor" and math.isclose(b["diferencia"], 0.1)
    # solo dos lineas elegidas: otra interseccion
    assert re_.comparar(["a", "c"], filas, "MILOTO", "seguimiento")["objetivos_comunes"] == [1, 2, 3]


def test_linea_elegida_sin_muestra_no_se_retira():
    filas = {"a": [_fila("a", 1, 0.3)], "b": [_fila("b", 1, 0.3, estado="pendiente")], "c": []}
    c = re_.comparar(["a", "b", "c"], filas, "MILOTO", "seguimiento")
    assert c["estado"] == "sin_muestra_comun" and c["clasificacion"] == [] and c["por_linea"] == {}
    assert "b" in c["motivo"] and "c" in c["motivo"]
    motivos = {f["linea"]: f["motivo"] for f in c["fuera_de_la_muestra_comun"]}
    assert motivos == {"b": "pendiente", "c": "sin_emision_de_la_linea_para_el_objetivo"}
    assert re_.comparar(["a"], filas, "MILOTO", "seguimiento")["motivo"].startswith("elige al menos dos")


def test_universos_incompatibles_y_tipos_separados():
    filas = {"a": [_fila("a", 1, 0.3), _fila("a", 2, 0.3)],
             "b": [_fila("b", 1, 0.3, universo="pares:42:x"), _fila("b", 2, 0.3, tipo="retrospectiva")]}
    c = re_.comparar(["a", "b"], filas, "COLORLOTO", "seguimiento")
    assert c["estado"] == "sin_muestra_comun"
    motivos = {(f["objetivo"], f["linea"]): f["motivo"] for f in c["fuera_de_la_muestra_comun"]}
    assert motivos[(1, None)].startswith("universos_incompatibles")
    assert motivos[(2, "b")] == "emision_de_tipo_retrospectiva"


def test_empate_por_debajo_de_la_precision_de_almacenamiento():
    assert re_.veredicto(-2e-11) == "empate" and re_.veredicto(5e-10) == "empate"
    assert re_.veredicto(-1e-6) == "menor_perdida_que_la_uniforme_en_esta_muestra"
    assert re_.veredicto(1e-6) == "la_uniforme_fue_mejor"
    filas = {"a": [_fila("a", 1, 0.4 - 2e-11)], "b": [_fila("b", 1, 0.5)]}
    c = re_.comparar(["a", "b"], filas, "MILOTO", "seguimiento")
    assert [f["linea"] for f in c["clasificacion"]] == ["uniforme", "a", "b"]


def test_agregado_serie_y_acumulado_con_el_mismo_denominador():
    filas = [_fila("a", o, ll, 0.4, aciertos=k) for o, ll, k in ((3, 0.5, 1), (1, 0.3, 0), (2, 0.35, 2))]
    filas.append(_fila("a", 4, 0, estado="excluido", motivo="historico_hasta_el_corte_cambio"))
    filas.append(_fila("a", 5, 0, estado="pendiente"))
    a = re_.agregado(filas, "MILOTO")
    assert (a["objetivos"], a["incluidos"], a["excluidos"], a["pendientes"]) == (5, 3, 1, 1)
    assert a["excluidos_por_motivo"] == {"historico_hasta_el_corte_cambio": 1}
    assert [p["objetivo"] for p in a["serie"]] == [1, 2, 3]
    assert math.isclose(a["serie"][-1]["acumulada"], sum(p["diferencia"] for p in a["serie"]))
    assert math.isclose(a["perdidas"]["log_loss"]["diferencia"], a["serie"][-1]["acumulada"] / 3)
    assert a["aciertos"] == {"suma": 3, "promedio": 1.0, "de": 5, "objetivos": 3,
                             "distribucion": {"0": 1, "1": 1, "2": 1}}
    assert a["muestra_pequena"] is True and a["superbalota"] is None


def test_superbalota_se_agrega_aparte():
    sb = {"acierto": True, "log_loss": 2.0, "log_loss_uniforme": 2.7, "brier": 0.8, "brier_uniforme": 0.9}
    a = re_.agregado([_fila("a", 1, 0.3, superbalota=sb)], "BALOTO")
    assert a["perdidas"]["log_loss"]["modelo"] == 0.3
    assert a["superbalota"]["aciertos"] == 1 and a["superbalota"]["log_loss"]["modelo"] == 2.0


# ---------------------------------------------------------------------------
# Calibracion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("p, indice", [(0.0, 0), (0.0099, 0), (0.01, 1), (0.125, 7), (0.4999, 10), (0.5, 11),
                                       (1.0, 11)])
def test_intervalos_fijos_y_limites(p, indice):
    assert rc.intervalo_de(p) == indice


def test_probabilidad_fuera_de_rango():
    with pytest.raises(rc.ProbabilidadFueraDeRango):
        rc.intervalo_de(1.0000001)
    with pytest.raises(rc.ProbabilidadFueraDeRango):
        rc.intervalo_de(-0.1)


def _numeros(objetivo, probabilidades, salieron):
    candidatos = list(range(1, len(probabilidades) + 1))
    return {"objetivo": objetivo, "estado": "incluido",
            "congelado": {"tipo": "numeros", "candidatos": candidatos, "probabilidad": probabilidades},
            "resultado": {"numeros": salieron, "superbalota": None}}


def test_calibracion_vacios_none_y_dos_denominadores():
    filas = [_numeros(1, [0.12, 0.12, 0.6, 0.0], [3]), _numeros(2, [0.12, 0.13, 0.6, 1.0], [1, 4])]
    d = rc.diagnostico(filas)["diagnosticos"]["numeros"]
    assert (d["predicciones"], d["objetivos"]) == (8, 2)
    por = {(i["desde"], i["hasta"]): i for i in d["intervalos"]}
    assert por[(0.1, 0.125)]["predicciones"] == 3 and por[(0.1, 0.125)]["objetivos"] == 2
    assert math.isclose(por[(0.1, 0.125)]["valor_observado_medio"], 1 / 3)
    assert por[(0.5, 1.0)]["predicciones"] == 3 and por[(0.5, 1.0)]["incluye_hasta"] is True
    assert por[(0.0, 0.01)]["predicciones"] == 1 and por[(0.0, 0.01)]["valor_observado_medio"] == 0.0
    vacio = por[(0.3, 0.5)]
    assert vacio["predicciones"] == 0 and vacio["probabilidad_media"] is None and vacio["valor_observado_medio"] is None
    assert d["muestra_pequena"] is True
    assert "superbalota" not in rc.diagnostico(filas)["diagnosticos"]
    # solo emisiones incluidas
    assert rc.diagnostico([{**filas[0], "estado": "excluido"}])["diagnosticos"] == {}


def test_calibracion_de_colorloto_con_pares_repetidos():
    candidatos = [[1, "AZUL"], [1, "ROJO"], [2, "AZUL"]]
    fila = {"objetivo": 7, "estado": "incluido",
            "congelado": {"tipo": "pares", "candidatos": candidatos, "probabilidad": [0.5, 0.3, 0.2]},
            "resultado": {"pares": [[1, "AZUL"], [1, "AZUL"], [2, "AZUL"], [3, "VERDE"], [4, "ROJO"], [5, "ROJO"]]}}
    obs = dict((tuple(c), y) for c, (_, y) in zip(candidatos, rc.observaciones(fila)["pares"]))
    assert obs == {(1, "AZUL"): 2 / 6, (1, "ROJO"): 0.0, (2, "AZUL"): 1 / 6}
    d = rc.diagnostico([fila])["diagnosticos"]["pares"]
    assert "fracción de balotas" in d["etiqueta_observado"] and "al menos una vez" in d["etiqueta_observado"]


def test_superbalota_en_diagnostico_separado():
    fila = _numeros(1, [0.5, 0.5], [1])
    fila["congelado"]["superbalota"] = {"candidatos": [1, 2, 3, 4], "probabilidad": [0.25] * 4, "sugerida": 1}
    fila["resultado"]["superbalota"] = 3
    d = rc.diagnostico([fila])["diagnosticos"]
    assert set(d) == {"numeros", "superbalota"} and d["superbalota"]["predicciones"] == 4
    assert d["numeros"]["predicciones"] == 2


# ---------------------------------------------------------------------------
# Carteras
# ---------------------------------------------------------------------------

def _cartera(cantidad, maximos):
    return {"metadatos": {"cantidad": cantidad},
            "filas": [{"objetivo": o, "tipo": "seguimiento", "estado": "incluido", "aciertos": {"maximo": m}}
                      for o, m in maximos.items()]}


def test_carteras_solo_con_el_mismo_numero_de_combinaciones():
    carteras = {"veinte": _cartera(20, {1: 3, 2: 2}), "una": _cartera(1, {1: 1, 2: 0}),
                "veinte_b": _cartera(20, {2: 1, 3: 2}), "vacia": _cartera(20, {})}
    c = re_.comparar_carteras(carteras, list(carteras), "seguimiento")
    grupos = {g["combinaciones_por_cartera"]: g for g in c["grupos"]}
    assert set(grupos) == {1, 20}
    assert grupos[1]["estado"] == "una_sola_cartera" and grupos[1]["maximos"] == {}
    assert grupos[20]["lineas"] == ["veinte", "veinte_b", "vacia"]  # la cartera sin objetivos no se retira
    assert grupos[20]["estado"] == "sin_muestra_comun"
    sin_vacia = re_.comparar_carteras(carteras, ["veinte", "veinte_b"], "seguimiento")["grupos"][0]
    assert sin_vacia["objetivos_comunes"] == [2] and sin_vacia["maximos"] == {"veinte": [2], "veinte_b": [1]}


def test_resumen_de_cartera():
    r = re_.resumen_de_cartera(_cartera(5, {1: 2, 2: 2, 3: 0})["filas"])
    assert r["maximos"] == {0: 1, 2: 2} and math.isclose(r["maximo_medio"], 4 / 3) and r["muestra_pequena"]


def test_universo_del_congelado():
    assert rp.universo_de({"tipo": "numeros", "candidatos": list(range(1, 40))})["clave"] == "numeros:39"
    pares = rp.universo_de({"tipo": "pares", "candidatos": [[1, "AZUL"], [1, "ROJO"]]})
    assert pares["clave"].startswith("pares:2:") and "2 colores" in pares["descripcion"]
