"""Contrastes científicos independientes, estado congelado y carga sin fit.

Todo el histórico es sintético. Ningún contraste acredita independencia o
ventaja predictiva de los sorteos reales.
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import betaln, gammaln

from app.application.ml import laboratorio_bayes_markov as bm
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from tests.unit import fixtures_producto4 as f4


def _X(identidades, anteriores=None):
    X = np.zeros((len(identidades), 8))
    X[:, 0] = identidades
    if anteriores is not None:
        X[:, 5] = anteriores
    return X


@pytest.fixture(scope="module")
def ajustes():
    salida = {}
    for juego in lv.JUEGOS:
        i = lv.validar_instantanea(juego, f4.historico(juego, 110))
        v = lv.Variables(i)
        f = v.filas(range(20, 90), paleta=i.paleta(90) if i.reglas.colores else None)
        for familia in ("bayes", "markov"):
            identidad = (("bayes_jerarquico_pares" if i.reglas.colores else "bayes_jerarquico_binario")
                         if familia == "bayes" else ("markov_pares" if i.reglas.colores else "markov_apariciones"))
            m = bm.ajustar_bayes_markov(identidad, f.X, f.y, reglas=i.reglas, candidatos=f.candidatos)
            salida[(juego, familia)] = (m, v.filas([90, 100]), i.reglas)
    return salida


@pytest.mark.parametrize("juego", lv.JUEGOS)
@pytest.mark.parametrize("familia", ["bayes", "markov"])
def test_ajuste_real_por_juego_predictivas_validas_y_parametros_congelados(ajustes, juego, familia):
    m, filas, reglas = ajustes[(juego, familia)]
    antes = json.dumps(m.to_dict(), sort_keys=True)
    p = lm.inferir(m, "distribucion_de_pares" if reglas.colores else "marginales_de_aparicion", filas, 5)
    assert np.all(np.isfinite(p)) and np.all((p > 0) & (p < 1))
    for posicion in np.unique(filas.posiciones):
        assert p[filas.posiciones == posicion].sum() == pytest.approx(1 if reglas.colores else 5, abs=1e-9)
    assert json.dumps(m.to_dict(), sort_keys=True) == antes
    assert m.componentes_de_inferencia()[0]["paso"] == "estimador"
    assert "no define" in m.valores_globales(lv.NOMBRES_VARIABLES_NUMEROS)["motivo"]


@pytest.mark.parametrize("universo", [39, 43])
def test_cuadratura_contra_integracion_adaptativa_independiente(universo):
    X = _X([1] * 9 + [2] * 7)
    y = np.asarray([1, 1] + [0] * 7 + [1] * 4 + [0] * 3)
    m = bm.BayesJerarquicoBinario(universo).fit(X, y)
    s, n, k = np.asarray([2, 4]), np.asarray([9, 7]), 20
    def densidad(mu):
        if not 0 < mu < 1:
            return 0.
        logp = 4 * math.log(mu) + (universo - 6) * math.log1p(-mu)
        logp += sum(betaln(s + k * mu, n - s + k * (1 - mu)) - betaln(k * mu, k * (1 - mu)))
        return math.exp(logp + 25)  # constante arbitraria cancelada
    z = quad(densidad, 0, 1, epsabs=1e-12, epsrel=1e-12)[0]
    media_mu = quad(lambda u: u * densidad(u), 0, 1, epsabs=1e-12, epsrel=1e-12)[0] / z
    segundo_mu = quad(lambda u: u * u * densidad(u), 0, 1, epsabs=1e-12, epsrel=1e-12)[0] / z
    np.testing.assert_allclose(m.medias, (s + k * media_mu) / (n + k), atol=1e-12, rtol=0)
    assert m.media_mu == pytest.approx(media_mu, abs=1e-12)
    assert m.segundo_mu == pytest.approx(segundo_mu, abs=1e-12)
    assert np.all(m.segundos > m.medias ** 2)  # no se almacena sólo un punto
    assert m.diagnostico["convergio"] and m.diagnostico["error_refinamiento"] <= 1e-9


def test_jerarquia_comparte_informacion_y_candidato_nuevo_integra_mu():
    X = _X([1] * 10 + [2] * 10)
    a = bm.BayesJerarquicoBinario().fit(X, [1] + [0] * 9 + [0] * 10)
    b = bm.BayesJerarquicoBinario().fit(X, [1] + [0] * 9 + [1] * 10)
    assert b.medias[0] > a.medias[0]  # otros candidatos alteran μ, no son Betas independientes
    assert b.predict_proba(_X([999]))[0, 1] == b.media_mu


def test_agotar_presupuesto_no_se_declara_convergencia():
    with pytest.raises(bm.InferenciaNoConvergente, match="sin refinamiento"):
        bm.BayesJerarquicoBinario(max_nodos=32).fit(_X([1, 1, 2, 2]), [1, 0, 0, 0])


def _color_pequeno():
    pares = [(n, "rojo") for n in range(1, 8)]
    X = _X([lv.codigo_de_par(*p) for p in pares])
    return bm.BayesJerarquicoPares(pares).fit(X, [6, 0, 0, 0, 0, 0, 0]), X


def test_posterior_color_exacta_conserva_seis_repeticiones():
    m, X = _color_pequeno()
    np.testing.assert_array_equal(m.cuentas, [[6, 0, 0, 0, 0, 0, 0], [0] * 7])
    np.testing.assert_array_equal(m.alfa_color, [7, 1])
    np.testing.assert_array_equal(m.beta_numero[0], [7, 1, 1, 1, 1, 1, 1])
    np.testing.assert_allclose(m.predict(X), 6 * (7 / 8) * np.asarray([7, 1, 1, 1, 1, 1, 1]) / 13)
    assert m.diagnostico["inferencia"] == "exacta"


def test_predictiva_conjunta_integrada_no_es_multinomial_plugin():
    m, X = _color_pequeno()
    pares = [(1, "rojo")] * 6
    integrada = math.exp(m.log_predictiva_conjunta(pares))
    esperada = math.prod((7 + j) / (8 + j) for j in range(6)) * math.prod((7 + j) / (13 + j) for j in range(6))
    assert integrada == pytest.approx(esperada, abs=1e-15)
    plugin = (m.predict(X)[0] / 6) ** 6
    assert abs(integrada - plugin) > 1e-3


def test_predictiva_conjunta_suma_masa_del_color_incluyendo_reserva():
    m, _ = _color_pequeno()
    masa = sum(math.exp(m.log_predictiva_conjunta([(n, "rojo") for n in multiconjunto]))
               for multiconjunto in itertools.combinations_with_replacement(range(1, 8), 6))
    assert masa == pytest.approx(7 / 13, abs=2e-13)
    # E[q_rojo**6] = (7)_6/(8)_6; el resto es masa con OTROS.
    assert masa != pytest.approx((7 / 8) ** 6)


def test_color_nuevo_reparte_reserva_sin_crecer_posterior_y_por_objetivo():
    m, X = _color_pequeno()
    antes = json.dumps(m.to_dict(), sort_keys=True)
    azul = _X([lv.codigo_de_par(n, "azul") for n in range(1, 8)])
    verde = _X([lv.codigo_de_par(n, "verde") for n in range(1, 8)])
    a = np.vstack([X, azul])
    b = np.vstack([X, azul, verde])
    resultado = m.predict_para_objetivos(np.vstack([a, b]), [1] * len(a) + [2] * len(b))
    np.testing.assert_array_equal(resultado[:len(a)], m.predict(a))
    np.testing.assert_array_equal(resultado[len(a):], m.predict(b))
    assert m.predict(azul).sum() == pytest.approx(6 / 8)
    assert m.predict(np.vstack([azul, verde])).sum() == pytest.approx(6 / 8)
    assert json.dumps(m.to_dict(), sort_keys=True) == antes


@pytest.mark.parametrize("clase,universo", [(bm.MarkovApariciones, 43), (bm.MarkovPares, 7)])
def test_transicion_dirigida_anterior_a_objetivo_y_no_transpuesta(clase, universo):
    m = clase(universo, fuerza=10).fit(_X([1, 1, 1, 1], [0, 0, 0, 1]), [1, 1, 0, 0])
    assert m.cuentas[0, 0, 1] == 2 and m.cuentas[0, 1, 0] == 1
    assert m.cuentas.sum() == 4
    esperada = (np.asarray([1, 2] + [0] * (m.estados - 2)) + 10 * m.prior) / 13
    np.testing.assert_allclose(m.transiciones[0, 0], esperada, rtol=0, atol=2e-16)
    esperado = esperada @ np.arange(m.estados)
    salida = m.predict(_X([1], [0]))[0] if m.estados == 7 else m.predict_proba(_X([1], [0]))[0, 1]
    assert salida == pytest.approx(esperado)


@pytest.mark.parametrize("clase,universo", [(bm.MarkovApariciones, 39), (bm.MarkovPares, 14)])
def test_estado_sin_observaciones_candidato_nuevo_y_estado_fuera_de_espacio_usan_prior(clase, universo):
    m = clase(universo).fit(_X([1, 1], [0, 0]), [0, 1])
    X = _X([1, 999, 1, 1], [1, 0, -1, 7])
    salida = m.predict(X) if m.estados == 7 else m.predict_proba(X)[:, 1]
    base = 6 / universo if m.estados == 7 else 5 / universo
    np.testing.assert_allclose(salida, base, rtol=0, atol=2e-16)
    assert m.diagnostico["orden"] == 1


def test_markov_color_estado_seis_no_se_convierte_en_binario():
    m = bm.MarkovPares(7).fit(_X([1, 1], [6, 6]), [6, 5])
    assert m.cuentas[0, 6, 6] == m.cuentas[0, 6, 5] == 1
    assert m.cuentas[0, 1].sum() == 0
    assert m.predict(_X([1], [6]))[0] == pytest.approx((11 + 10 * 6 / 7) / 12)


@pytest.mark.parametrize("familia", ["bayes_bin", "bayes_color", "markov_bin", "markov_color"])
def test_carga_proceso_nuevo_prohibe_todo_fit_y_conserva_salida(tmp_path, familia):
    if familia == "bayes_color":
        m, X = _color_pequeno()
    elif familia == "bayes_bin":
        X = _X([1, 1, 2, 2])
        m = bm.BayesJerarquicoBinario().fit(X, [0, 1, 0, 0])
    else:
        X = _X([1, 1, 2, 2], [0, 1, 1, 0])
        clase = bm.MarkovPares if familia == "markov_color" else bm.MarkovApariciones
        m = clase().fit(X, [0, 1, 0, 1])
    original = m.predict(X) if "color" in familia else m.predict_proba(X)
    archivo = tmp_path / "estimador con espacios.json"
    archivo.write_text(json.dumps({"modelo": m.to_dict(), "X": X.tolist()}), encoding="utf-8")
    codigo = """
import json,sys
from app.application.ml import laboratorio_bayes_markov as bm
def prohibido(*a,**k): raise AssertionError('fit prohibido en carga e inferencia')
for cls in (bm.BayesJerarquicoBinario,bm.BayesJerarquicoPares,bm.MarkovApariciones,bm.MarkovPares): cls.fit=prohibido
d=json.load(open(sys.argv[1],encoding='utf-8')); m=bm.deserializar_bayes_markov(d['modelo'])
p=m.predict(d['X']) if sys.argv[2]=='color' else m.predict_proba(d['X'])
print(json.dumps(p.tolist()))
"""
    r = subprocess.run([sys.executable, "-c", codigo, str(archivo), "color" if "color" in familia else "bin"],
                       check=True, capture_output=True, text=True, timeout=30, env=dict(os.environ))
    np.testing.assert_array_equal(np.asarray(json.loads(r.stdout)), original)


@pytest.mark.parametrize("juego,familia", [("BALOTO", "bayes"), ("COLORLOTO", "bayes"),
                                         ("BALOTO", "markov"), ("COLORLOTO", "markov")])
def test_carga_rechaza_parametros_y_arrays_incompatibles(ajustes, juego, familia):
    m = ajustes[(juego, familia)][0]
    d = copy.deepcopy(m.to_dict())
    d["identidades"] = d["identidades"][:-1]
    with pytest.raises(ValueError):
        bm.deserializar_bayes_markov(d)


@pytest.mark.parametrize("clase", [bm.BayesJerarquicoBinario, bm.MarkovApariciones, bm.MarkovPares])
def test_etiquetas_fuera_de_espacio_no_se_aceptan(clase):
    with pytest.raises(ValueError):
        clase().fit(_X([1, 1]), [0, 8])


def test_carga_rechaza_version_y_clase_desconocida():
    with pytest.raises(ValueError):
        bm.deserializar_bayes_markov({"version": "futura", "clase": "BayesJerarquicoBinario"})


def test_no_hay_lectura_entrenamiento_ni_escritura_en_inferencia(ajustes, monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("inferencia no puede ajustar ni escribir")
    for clase in (bm.BayesJerarquicoBinario, bm.BayesJerarquicoPares, bm.MarkovApariciones, bm.MarkovPares):
        monkeypatch.setattr(clase, "fit", prohibido)
    monkeypatch.setattr(Path, "write_bytes", prohibido)
    monkeypatch.setattr(Path, "write_text", prohibido)
    for m, filas, reglas in ajustes.values():
        antes = json.dumps(m.to_dict(), sort_keys=True)
        nuevo = bm.deserializar_bayes_markov(json.loads(antes))
        lm.inferir(nuevo, "distribucion_de_pares" if reglas.colores else "marginales_de_aparicion", filas, 5)
        assert json.dumps(nuevo.to_dict(), sort_keys=True) == antes
