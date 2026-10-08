"""Producto 5: seguimiento observado de carteras.

- seguimiento (objetivo no cargado al generar), retrospectiva, pendiente y
  excluida, por separado;
- aciertos observados recalculados aqui con conjuntos y multiconjuntos;
- primera emision sellada por linea y objetivo; una version ilegible
  excluye el objetivo sin pasar a otra; historico hasta el corte cambiado o
  base no disponible;
- nunca se mezcla con simulaciones: simular no cambia el seguimiento."""
from __future__ import annotations

from collections import Counter

import pytest

from app.application.use_cases.carteras import CarterasError
from tests.unit import fixtures_producto5 as f5

CARTERA = {"modelo": "uniforme", "perfil": "reducido", "cantidad": 4, "semilla": 5, "diversidad": "libre"}


@pytest.fixture
def entorno(tmp_path):
    return f5.entorno(tmp_path, {"BALOTO": 70, "BALOTO_REVANCHA": 70, "MILOTO": 70, "COLORLOTO": 70})


def _generar(s, juego, **cambios):
    r = s.ahora("cartera", [juego], {**CARTERA, **cambios})["juegos"][juego]
    assert r["estado"] in ("terminado", "reutilizado"), r
    return s.cartera(r["resultado"])


def _aciertos(combinacion, resultado, colores):
    if colores:
        a, b = Counter(tuple(p) for p in combinacion["pares"]), Counter(tuple(p) for p in resultado.pares)
        return sum(min(a[k], b[k]) for k in a)
    return len(set(combinacion["numeros"]) & set(resultado.numeros))


@pytest.mark.parametrize("juego", ["BALOTO", "MILOTO", "COLORLOTO"])
def test_seguimiento_pendiente_y_despues_observado(entorno, juego):
    s = entorno.carteras()
    modelo = "uniforme_paleta" if juego == "COLORLOTO" else "uniforme"
    g = _generar(s, juego, modelo=modelo)
    linea = g.linea
    fila = s.seguimiento(juego)["lineas"][linea]["filas"][0]
    assert fila["estado"] == "pendiente" and fila["tipo"] == "seguimiento"
    assert s.seguimiento(juego)["lineas"][linea]["por_tipo"]["seguimiento"]["pendientes"] == 1
    nuevo = entorno.siguiente(juego)[0]
    entorno.anadir(juego, [nuevo])
    datos = s.seguimiento(juego)
    fila = datos["lineas"][linea]["filas"][0]
    assert fila["estado"] == "incluido" and fila["historico_hasta_el_corte"] == "coincide"
    colores = juego == "COLORLOTO"
    esperados = [_aciertos(c, nuevo, colores) for c in g.artefacto["cartera"]["combinaciones"]]
    assert [x["aciertos"] for x in fila["aciertos"]["por_linea"]] == esperados
    assert fila["aciertos"]["maximo"] == max(esperados)
    if juego == "BALOTO":
        sb = [c["superbalota"] == nuevo.superbalota for c in g.artefacto["cartera"]["combinaciones"]]
        assert [x["superbalota"] for x in fila["aciertos"]["por_linea"]] == sb
        assert fila["aciertos"]["superbalota_en_alguna_linea"] == any(sb)
    else:
        assert "superbalota_en_alguna_linea" not in fila["aciertos"]
    agg = datos["lineas"][linea]["por_tipo"]["seguimiento"]
    assert agg["incluidos"] == 1 and agg["maximos_observados"] == {max(esperados): 1}
    assert datos["lineas"][linea]["por_tipo"]["retrospectiva"]["objetivos"] == 0


def test_retrospectiva_separada_del_seguimiento(entorno):
    s = entorno.carteras()
    g = _generar(s, "MILOTO", corte=65)
    assert g.objetivo == 66
    clasificacion = g.artefacto["generacion"]["clasificacion_temporal"]
    assert clasificacion["tipo"] == "simulacion_retrospectiva" and clasificacion["objetivo_en_la_base"] is True
    datos = s.seguimiento("MILOTO", tipo="retrospectiva")
    fila = datos["lineas"][g.linea]["filas"][0]
    assert fila["tipo"] == "retrospectiva" and fila["estado"] == "incluido"
    agg = datos["lineas"][g.linea]["por_tipo"]
    assert agg["retrospectiva"]["incluidos"] == 1 and agg["seguimiento"]["objetivos"] == 0


def test_primera_emision_por_linea_e_ilegible_excluye_sin_sustituir(entorno):
    s = entorno.carteras()
    primera = _generar(s, "MILOTO")
    juego = entorno.juegos.obtener_por_codigo("MILOTO")
    sorteos = entorno.cargados("MILOTO")
    corregido = sorteos[3].__class__(sorteos[3].numero_sorteo, sorteos[3].fecha, sorteos[3].dia_semana,
                                     (1, 2, 3, 4, 5), None)
    entorno.resultados.numericos[juego.id] = [*sorteos[:3], corregido, *sorteos[4:]]
    segunda = _generar(s, "MILOTO")
    assert (primera.linea, primera.objetivo) == (segunda.linea, segunda.objetivo) and segunda.secuencia == 2
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    fila = s.seguimiento("MILOTO")["lineas"][primera.linea]["filas"][0]
    assert fila["identificador"] == primera.identificador and fila["versiones"] == 2
    # la primera emision se hizo con el historico anterior a la correccion: se excluye, no se usa la segunda
    assert fila["estado"] == "excluido" and fila["motivo"] == "historico_hasta_el_corte_cambio"
    ruta = next((entorno.directorio / "carteras" / "MILOTO" / primera.linea).glob(f"*-{primera.identificador}.json"))
    ruta.write_bytes(ruta.read_bytes().replace(b'"cartera"', b'"cartera" ', 1))
    fila = s.seguimiento("MILOTO")["lineas"][primera.linea]["filas"][0]
    assert fila["estado"] == "excluido" and fila["motivo"] == "orden_ambiguo_por_archivo_ilegible"
    assert "identificador" not in fila  # no se sustituye por la segunda version


def test_base_no_disponible_y_simulaciones_separadas(entorno):
    s = entorno.carteras()
    g = _generar(s, "BALOTO")
    entorno.anadir("BALOTO", entorno.siguiente("BALOTO"))
    antes = s.seguimiento("BALOTO")
    sim = s.ahora("simulacion", ["BALOTO"], {"cartera": g.identificador, "simulaciones": 1000, "semilla": 1})
    assert sim["estado"] == "exito"
    assert s.seguimiento("BALOTO") == antes  # simular no cambia lo observado
    texto = str(antes)
    assert "frecuencia_simulada" not in texto and "simulaciones" not in texto and "log_loss" not in texto
    assert "no se mezclan con frecuencias simuladas" in antes["lineas"][g.linea]["aviso"]
    entorno.base_caida = True
    caida = s.seguimiento("BALOTO")
    fila = caida["lineas"][g.linea]["filas"][0]
    assert caida["base"] == "no_disponible" and fila["estado"] == "sin_base"
    assert fila["historico_hasta_el_corte"] == "no_disponible"
    assert s.observado_de_cartera(g.artefacto)["estado"] == "sin_base"


def test_comparacion_entre_lineas_solo_con_objetivos_comunes_y_mismo_tamano(entorno):
    s = entorno.carteras()
    a = _generar(s, "MILOTO")
    b = _generar(s, "MILOTO", semilla=6)
    c = _generar(s, "MILOTO", cantidad=3)
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    datos = s.seguimiento("MILOTO")
    grupos = {g["combinaciones_por_cartera"]: g for g in datos["comparacion"]["grupos"]}
    assert set(grupos) == {3, 4}
    assert grupos[4]["lineas"] == sorted([a.linea, b.linea]) and grupos[4]["objetivos_comunes"] == [a.objetivo]
    assert grupos[3]["lineas"] == [c.linea] and grupos[3]["objetivos_comunes"] == []
    with pytest.raises(CarterasError):
        s.seguimiento("MILOTO", linea="no-v1-n1-libre-s1")
    with pytest.raises(CarterasError):
        s.seguimiento("MILOTO", tipo="otro")
