"""Fase 7: motor de simulacion bajo el mecanismo uniforme (modulo puro).

Calculos contrastables (seleccion exactamente uniforme, referencias exactas,
coincidencia con el motor de Fase 5), reglas de los cuatro juegos
(superbalota aparte, multiplicidades numero-color), corte, reproducibilidad,
independencia del lote, limites, p-valores y memoria acotada. Historicos
sinteticos; ningun dato es real."""
from __future__ import annotations

import ast
import itertools
import math
import tracemalloc
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico
from app.application.fase7 import artefacto as fa
from app.application.fase7 import motor as fm
from tests.unit import fixtures_producto1 as fx

APP = Path(__file__).resolve().parents[3] / "app"


def _historico(juego: str, n: int, semilla: int = 1):
    if juego == "COLORLOTO":
        return fx.historico_colorloto(n, semilla=semilla)
    return fx.historico_numerico(juego, n, semilla=semilla, primero=530 if juego == "MILOTO" else 2081)


def _con_hueco(resultados, posicion: int):
    """Renumera desde `posicion` sumando 2: crea un hueco (una transicion menos)."""
    return [replace(r, numero_sorteo=r.numero_sorteo + 2) if i >= posicion else r for i, r in enumerate(resultados)]


# ---------------------------------------------------------------------------
# Contrato fijado
# ---------------------------------------------------------------------------

def test_familias_fijadas_por_juego_con_su_funcion_del_motor_de_fase5():
    numericas = ("dispersion_frecuencia_numeros", "rango_frecuencia_numeros", "media_repeticiones_entre_sorteos",
                 "media_suma", "media_pares_consecutivos")
    assert [d.nombre for d in fm.familia("BALOTO")] == [*numericas, "dispersion_frecuencia_superbalota"]
    assert [d.nombre for d in fm.familia("BALOTO_REVANCHA")] == [*numericas, "dispersion_frecuencia_superbalota"]
    assert [d.nombre for d in fm.familia("MILOTO")] == list(numericas)
    assert [d.nombre for d in fm.familia("COLORLOTO")] == [
        "dispersion_frecuencia_pares", "dispersion_frecuencia_numeros", "dispersion_frecuencia_colores",
        "media_repeticiones_entre_sorteos", "media_maximo_repeticion_color"]
    import importlib
    for juego in fm.JUEGO_INDICE:
        for d in fm.familia(juego):
            modulo, funcion = d.motor_fase5.split(".")
            assert callable(getattr(importlib.import_module(f"app.application.estadisticas.motor.{modulo}"), funcion))
            assert d.justificacion and d.descripcion


def test_iteraciones_y_semilla_admitidas():
    assert fm.ITERACIONES_ADMITIDAS == (100, 1_000, 10_000, 100_000, 1_000_000)
    for i in fm.ITERACIONES_ADMITIDAS:
        assert fm.validar_parametros(i, 0) == (i, 0)
    for malo in (0, 50, 999, 1001, 5_000, 2_000_000, True, "100", 100.0, None):
        with pytest.raises(fm.SimulacionFase7NoValida):
            fm.validar_parametros(malo, 1)
    for semilla in (-1, 2**32, True, "7", 1.5):
        with pytest.raises(fm.SimulacionFase7NoValida):
            fm.validar_parametros(100, semilla)
    assert fm.validar_parametros(100, 2**32 - 1) == (100, 2**32 - 1)
    with pytest.raises(fm.SimulacionFase7NoValida):
        fm.familia("LOTERIA_DE_BOGOTA")


# ---------------------------------------------------------------------------
# Mecanismo: seleccion exactamente uniforme
# ---------------------------------------------------------------------------

def _referencia(indices, n):
    """El j-esimo elemento de los que quedan, en Python puro."""
    restantes, salida = list(range(n)), []
    for j in indices:
        salida.append(restantes.pop(j))
    return salida


@pytest.mark.parametrize("n,k", [(6, 3), (7, 5), (9, 2)])
def test_seleccion_sin_reemplazo_es_exactamente_uniforme_sobre_los_subconjuntos(n, k):
    """Con indices exactamente uniformes, cada k-subconjunto sale k! veces:
    la seleccion no introduce sesgo propio (el unico es el de los dobles)."""
    tuplas = list(itertools.product(*[range(n - t) for t in range(k)]))
    u = np.array([[(j + 0.5) / (n - t) for t, j in enumerate(tupla)] for tupla in tuplas])
    elegidos = fm._seleccion_sin_reemplazo(u, n)
    assert [list(f) for f in elegidos] == [_referencia(t, n) for t in tuplas]
    conteo = Counter(frozenset(f.tolist()) for f in elegidos)
    assert all(len(set(f.tolist())) == k for f in elegidos)
    assert len(conteo) == math.comb(n, k) and set(conteo.values()) == {math.factorial(k)}


@pytest.mark.parametrize("tamano", [7, 16, 39, 42, 43, 64])
def test_indice_en_los_extremos_de_u_nunca_alcanza_el_tamano(tamano):
    u = np.array([0.0, np.nextafter(1.0, 0.0)])
    assert fm._indice(u, tamano).tolist() == [0, tamano - 1]


def test_seleccion_con_u_maximo_toma_los_mayores_restantes():
    u = np.full((2, 5), np.nextafter(1.0, 0.0))
    assert fm._seleccion_sin_reemplazo(u, 43).tolist() == [[42, 41, 40, 39, 38]] * 2


# ---------------------------------------------------------------------------
# Estadisticas: coincidencia con el motor de Fase 5
# ---------------------------------------------------------------------------

def _como_dtos(h: fm.Historico, valores: np.ndarray, superbalota: np.ndarray | None):
    """Un historico simulado (indices) como DTOs del motor, misma numeracion."""
    lo = h.reglas.rango[0]
    salida = []
    for i, r in enumerate(h.instantanea.sorteos):
        if h.reglas.colores:
            c = len(h.paleta)
            pares = tuple((int(v) // c + lo, h.paleta[int(v) % c]) for v in valores[i])
            salida.append(ResultadoColorLoto(r.numero_sorteo, r.fecha, r.dia_semana, pares))
        else:
            sb = None if superbalota is None else int(superbalota[i]) + h.reglas.superbalota[0]
            salida.append(ResultadoNumerico(r.numero_sorteo, r.fecha, r.dia_semana,
                                            tuple(sorted(int(v) + lo for v in valores[i])), sb))
    return salida


@pytest.mark.parametrize("juego", list(fm.JUEGO_INDICE))
def test_estadisticas_vectorizadas_coinciden_con_el_motor_en_historicos_simulados(juego):
    h = fm.preparar(juego, _con_hueco(_historico(juego, 35, semilla=4), 20))
    assert int(h.transiciones.sum()) == 33  # 35 sorteos, un hueco
    rng = np.random.Generator(np.random.PCG64(99))
    s = 1 if h.reglas.superbalota else 0
    u = rng.random((12, h.sorteos, h.k + s))
    if h.reglas.colores:
        valores, sb = fm._indice(u, h.n).astype(np.int64), None
    else:
        valores = fm._seleccion_sin_reemplazo(u[..., :h.k], h.n)
        sb = fm._indice(u[..., h.k], h.m).astype(np.int64) if s else None
    vectorizadas = fm.estadisticas_de_lote(h, valores, sb)
    for b in range(12):
        simulado = fm.preparar(juego, _como_dtos(h, valores[b], None if sb is None else sb[b]))
        assert tuple(int(x) for x in vectorizadas[b]) == fm.observadas_con_el_motor(simulado)


@pytest.mark.parametrize("juego", list(fm.JUEGO_INDICE))
def test_observadas_contrastan_motor_y_version_vectorizada(juego):
    h = fm.preparar(juego, _historico(juego, 50))
    assert fm.observadas(h) == fm.observadas_con_el_motor(h)


def test_superbalota_es_un_pool_aparte():
    base = _historico("BALOTO", 30)
    otra = [replace(r, superbalota=(r.superbalota % 16) + 1) for r in base]
    a, b = fm.observadas(fm.preparar("BALOTO", base)), fm.observadas(fm.preparar("BALOTO", otra))
    assert a[:5] == b[:5]  # los numeros no dependen de la superbalota
    assert fm.denominadores(fm.preparar("BALOTO", base))[5] == 16 * 30


def test_colorloto_cuenta_multiplicidades_numero_color():
    from datetime import date

    fx_ = [ResultadoColorLoto(1, date(2024, 8, 6), "martes", ((1, "ROJO"),) * 6),
           ResultadoColorLoto(2, date(2024, 8, 8), "jueves", ((1, "AZUL"),) * 3 + ((2, "ROJO"),) * 3),
           ResultadoColorLoto(3, date(2024, 8, 10), "sabado", ((3, "AZUL"), (4, "ROJO"), (5, "AZUL"), (6, "ROJO"),
                                                               (7, "AZUL"), (1, "ROJO")))]
    h = fm.preparar("COLORLOTO", fx_)
    assert h.paleta == ("AZUL", "ROJO") and h.n == 14
    obs = fm.observadas(h)
    pares = Counter(p for r in fx_ for p in r.pares)
    assert pares[(1, "ROJO")] == 7  # con multiplicidad
    assert obs[0] == sum((14 * pares.get((n, c), 0) - 18) ** 2 for n in range(1, 8) for c in h.paleta)
    assert obs[3] == 3 + 1  # 1->2: min(6, 3) del numero 1; 2->3: min(3, 1) del numero 1
    assert obs[4] == 6 + 3 + 3  # maximo de un mismo color por sorteo


# ---------------------------------------------------------------------------
# Referencias analiticas exactas
# ---------------------------------------------------------------------------

def test_referencias_exactas_por_juego():
    rb = fm.referencias(fm.preparar("BALOTO", _historico("BALOTO", 20)))
    assert rb == (Fraction(38), None, Fraction(25, 43), Fraction(110), Fraction(20, 43), Fraction(15))
    rm = fm.referencias(fm.preparar("MILOTO", _historico("MILOTO", 20)))
    assert rm == (Fraction(34), None, Fraction(25, 39), Fraction(100), Fraction(20, 39))
    rc = fm.referencias(fm.preparar("COLORLOTO", _historico("COLORLOTO", 60)))
    assert rc[:3] == (Fraction(41), Fraction(6), Fraction(5))


def test_referencias_de_multiconjunto_por_enumeracion_directa():
    for balotas, valores in ((2, 3), (3, 2), (6, 7)):
        if valores ** (2 * balotas) > 2_000_000:
            continue
        total = Fraction(0)
        for a in itertools.product(range(valores), repeat=balotas):
            for b in itertools.product(range(valores), repeat=balotas):
                total += sum((Counter(a) & Counter(b)).values())
        assert fm.media_repeticiones_multiconjunto(balotas, valores) == total / valores ** (2 * balotas)
    assert fm.media_maximo_multiplicidad(2, 2) == Fraction(3, 2)
    assert fm.media_maximo_multiplicidad(3, 2) == Fraction(9, 4)


@pytest.mark.parametrize("juego", list(fm.JUEGO_INDICE))
def test_medias_simuladas_compatibles_con_las_referencias(juego):
    h = fm.preparar(juego, _historico(juego, 40))
    contenido = fm.construir_contenido(h, fm.simular(h, 10_000, 5)[0], 10_000)
    for e in contenido["estadisticas"]:
        if e["referencia_analitica"] is None:
            continue
        error_estandar = e["simulado"]["desviacion"] / math.sqrt(10_000)
        assert abs(e["simulado"]["media"] - e["referencia_analitica"]["valor"]) < 5 * error_estandar, e["nombre"]


# ---------------------------------------------------------------------------
# Reproducibilidad, lote y corte
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("juego", list(fm.JUEGO_INDICE))
def test_resultado_independiente_del_tamano_de_lote(juego):
    h = fm.preparar(juego, _historico(juego, 30))
    contenidos = [fm.construir_contenido(h, fm.simular(h, 1_000, 11, lote=lote)[0], 1_000)
                  for lote in (1, 7, 64, 1_000, None)]
    assert all(c == contenidos[0] for c in contenidos)


def test_misma_semilla_mismo_contenido_y_otra_semilla_otro():
    h = fm.preparar("MILOTO", _historico("MILOTO", 30))
    a = fa.sha256(fm.construir_contenido(h, fm.simular(h, 1_000, 3)[0], 1_000))
    b = fa.sha256(fm.construir_contenido(h, fm.simular(h, 1_000, 3)[0], 1_000))
    c = fa.sha256(fm.construir_contenido(h, fm.simular(h, 1_000, 4)[0], 1_000))
    assert a == b != c


def test_huella_de_referencia_fijada():
    """Identidad de bytes: PCG64 + random() + floor/truncado IEEE. Si cambia
    (otra version de NumPy u otra plataforma), la prueba lo dice: no se supone."""
    r = fm.calcular("MILOTO", [[x.numero_sorteo, x.fecha.isoformat(), list(x.numeros), None]
                               for x in _historico("MILOTO", 40)], 1_000, fm.SEMILLA_PREDETERMINADA)
    assert fa.sha256(r["contenido"]) == HUELLA_REFERENCIA_MILOTO


def test_corte_aislado_y_sorteos_posteriores_rechazados():
    completo = _historico("BALOTO", 30)
    corte = completo[19].numero_sorteo
    h = fm.preparar("BALOTO", completo[:20], corte)
    assert h.instantanea.corte == corte and h.sorteos == 20
    with pytest.raises(fm.SimulacionFase7NoValida, match="posteriores al corte"):
        fm.preparar("BALOTO", completo, corte)
    with pytest.raises(fm.SimulacionFase7NoValida, match="no es el ultimo"):
        fm.preparar("BALOTO", completo[:15], corte)


def test_muestra_insuficiente_e_historico_no_valido():
    with pytest.raises(fm.MuestraInsuficienteFase7):
        fm.preparar("MILOTO", _historico("MILOTO", 1))
    dos_con_hueco = _con_hueco(_historico("MILOTO", 2), 1)
    with pytest.raises(fm.MuestraInsuficienteFase7, match="transicion"):
        fm.preparar("MILOTO", dos_con_hueco)
    malo = _historico("MILOTO", 5)
    malo[2] = replace(malo[2], numeros=(1, 2, 3, 4, 40))
    with pytest.raises(fm.SimulacionFase7NoValida):
        fm.preparar("MILOTO", malo)
    with pytest.raises(fm.SimulacionFase7NoValida):
        fm.preparar("BALOTO", [replace(r, superbalota=None) for r in _historico("BALOTO", 5)])


# ---------------------------------------------------------------------------
# P-valores, percentil y familia
# ---------------------------------------------------------------------------

def test_p_valor_percentil_y_bonferroni_exactos():
    h = fm.preparar("MILOTO", _historico("MILOTO", 20))
    obs = fm.observadas(h)
    a = fm.Acumulador(obs)
    valores = np.array([[o + d for o in obs] for d in (-1, 0, 0, 1, 2)] * 20, dtype=np.int64)
    a.sumar(valores)
    contenido = fm.construir_contenido(h, a, 100)
    e = contenido["estadisticas"][0]
    # 20 menores, 40 iguales, 40 mayores: p_sup = 81/101, p_inf = 61/101 -> p = min(1, 122/101) = 1
    assert e["simulado"]["menores"] == 20 and e["simulado"]["iguales"] == 40
    assert e["p_valor_empirico"]["exacto"] == "1/1" and e["percentil_observado"]["exacto"] == "2/5"
    assert e["p_valor_ajustado_bonferroni"]["exacto"] == "1/1"
    assert contenido["familia"]["p_minimo_alcanzable"] == "2/101"
    assert contenido["familia"]["umbral_alcanzable"] is False  # 5 x 2/101 > 0,05


def test_umbral_alcanzable_desde_mil_iteraciones():
    h = fm.preparar("BALOTO", _historico("BALOTO", 20))
    contenido = fm.construir_contenido(h, fm.simular(h, 1_000, 1)[0], 1_000)
    assert contenido["familia"]["umbral_alcanzable"] is True
    assert contenido["familia"]["tamano"] == 6 and all(
        0 < e["p_valor_empirico"]["valor"] <= 1 for e in contenido["estadisticas"])


def test_extremo_observado_da_el_p_minimo_y_supera_el_umbral():
    h = fm.preparar("MILOTO", _historico("MILOTO", 20))
    a = fm.Acumulador(fm.observadas(h))
    a.sumar(np.array([[o - 1 for o in fm.observadas(h)]] * 1_000, dtype=np.int64))
    e = fm.construir_contenido(h, a, 1_000)["estadisticas"][0]
    assert e["p_valor_empirico"]["exacto"] == "2/1001" and e["supera_umbral_exploratorio"] is True


# ---------------------------------------------------------------------------
# Memoria y procesamiento por lotes
# ---------------------------------------------------------------------------

def test_lotes_acotados_sin_reservar_todas_las_replicas(monkeypatch):
    tamanos = {"BALOTO": 645, "BALOTO_REVANCHA": 645, "MILOTO": 97, "COLORLOTO": 229}
    for juego, n in tamanos.items():
        h = fm.preparar(juego, _historico(juego, n))
        lote = fm.tamano_de_lote(h, 1_000_000)
        assert lote * h.dobles_por_iteracion <= fm.DOBLES_POR_LOTE and lote < 1_000_000
    h = fm.preparar("MILOTO", _historico("MILOTO", 97))
    pedidos = []
    original = fm.simular_lote
    monkeypatch.setattr(fm, "simular_lote", lambda h_, rng, b: pedidos.append(b) or original(h_, rng, b))
    _, meta = fm.simular(h, 10_000, 1, lote=999)
    assert max(pedidos) == 999 and sum(pedidos) == 10_000 and meta["lotes"] == len(pedidos) == 11


def test_pico_de_memoria_acotado_por_el_lote():
    h = fm.preparar("BALOTO", _historico("BALOTO", 645))
    tracemalloc.start()
    try:
        fm.simular(h, 10_000, 1)
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    # ~16 MB de uniformes por lote y sus derivados; nunca 10.000 replicas (310 MB solo en uniformes)
    assert pico < 160 * 2**20, pico


def test_avance_por_lote_hasta_el_total():
    h = fm.preparar("MILOTO", _historico("MILOTO", 30))
    vistos = []
    fm.simular(h, 1_000, 1, lote=300, avance=lambda fase, **d: vistos.append((fase, d["hechas"], d["de"])))
    assert vistos == [("simulando", 300, 1_000), ("simulando", 600, 1_000), ("simulando", 900, 1_000),
                      ("simulando", 1_000, 1_000)]


# ---------------------------------------------------------------------------
# Pureza
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("modulo", ["motor.py", "artefacto.py"])
def test_modulos_puros(modulo):
    arbol = ast.parse((APP / "application" / "fase7" / modulo).read_text(encoding="utf-8"))
    importados = {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
    prohibidos = {"sqlalchemy", "requests", "app.infrastructure", "subprocess", "socket",
                  "app.application.simulaciones.montecarlo_uniforme"}
    assert not {m for m in importados if m and any(m == p or m.startswith(p + ".") for p in prohibidos)}
    texto = ast.unparse(arbol)
    assert "open(" not in texto and ".write(" not in texto


HUELLA_REFERENCIA_MILOTO = "b62c9067b1ab650bf453d6c6fbe73fb3a7ae55341da53997b747a4cd03e5427f"
"""Calculada con NumPy 2.5.4 (Python 3.14.9) y comprobada igual con NumPy 2.4.6 (Python 3.11) en Linux."""
