"""Aislamiento adversarial del ajuste ML y comparación común de los juegos.

Se sustituyen TODOS los resultados desde el objetivo del corte, incluida una
paleta nueva de ColorLoto. Se contrasta el estado persistible completo: incluye
preparación, escalado, calibración, posterior y transiciones, según la familia.
"""
from __future__ import annotations

import dataclasses
import pickle

import numpy as np
import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from tests.unit import fixtures_producto4 as f4
from tests.unit.test_ml_cinco_flujo import JUEGOS, PROTOCOLO, modelos


def _estado(estimador):
    for nombre in ("to_dict", "como_dict", "a_dict"):
        exportar = getattr(estimador, nombre, None)
        if callable(exportar):
            return pickle.dumps(exportar(), protocol=5)
    return pickle.dumps(estimador, protocol=5)


def _cambio_futuro(juego, original, corte):
    nuevos = f4.historico(juego, len(original), semilla=947)
    cambiado = list(original)
    for i in range(corte, len(original)):
        if juego == "COLORLOTO":
            pares = tuple((n, "FUTURO_MORADO") for n, _ in nuevos[i].pares)
            cambiado[i] = dataclasses.replace(original[i], pares=pares)
        else:
            cambiado[i] = dataclasses.replace(original[i], numeros=nuevos[i].numeros,
                                               superbalota=nuevos[i].superbalota)
    return cambiado


@pytest.mark.parametrize("juego,indice", [(j, i) for j in JUEGOS for i in range(5)])
def test_futuro_no_altera_preparacion_calibracion_posterior_transiciones_ni_pronostico(monkeypatch, juego, indice):
    corte = 140
    original = f4.historico(juego, 190)
    cambiado = _cambio_futuro(juego, original, corte)
    a, b = (lv.validar_instantanea(juego, h) for h in (original, cambiado))
    va, vb = lv.Variables(a), lv.Variables(b)
    fa, fb = va.filas([corte]), vb.filas([corte])
    assert np.array_equal(fa.X, fb.X)
    assert fa.candidatos == fb.candidatos
    observaciones = []

    def observar(modelo, posicion, base, calibracion, filas):
        observaciones.append((posicion, list(base), list(calibracion), list(filas.posiciones)))

    monkeypatch.setattr(lm, "OBSERVADOR_DE_AJUSTE", observar)
    entrada = lm.CATALOGO[modelos(juego)[indice]]
    ma = lm.ajustar_candidato(entrada, a, va, corte, "reducido")
    mb = lm.ajustar_candidato(entrada, b, vb, corte, "reducido")
    assert ma.parametros == mb.parametros
    assert ma.detalle == mb.detalle
    assert _estado(ma.estimador) == _estado(mb.estimador)
    congelado = _estado(ma.estimador)
    pa, pb = ma.predecir(fa), mb.predecir(fb)
    assert np.array_equal(pa, pb)
    assert _estado(ma.estimador) == congelado
    assert np.all(np.isfinite(pa)) and np.all((pa > 0) & (pa < 1))
    assert abs(float(pa.sum()) - (1 if juego == "COLORLOTO" else 5)) < 1e-9
    for posicion, base, calibracion, filas in observaciones:
        assert posicion == corte and max(filas) < corte
        assert set(base).isdisjoint(calibracion)
        if calibracion:
            assert max(base) < min(calibracion)
            assert max(calibracion) < a.sorteos[corte].numero_sorteo
    assert observaciones, "el contrato temporal debe ser observable"
    if juego == "COLORLOTO":
        assert "FUTURO_MORADO" not in a.paleta(corte)
        assert "FUTURO_MORADO" in b.paleta()
        assert all("FUTURO_MORADO" not in str(c) for c in fa.candidatos)


@pytest.mark.parametrize("juego", JUEGOS)
def test_cinco_modelos_se_comparan_con_uniforme_en_los_mismos_objetivos_y_bloques(juego):
    instantanea = lv.validar_instantanea(juego, f4.historico(juego, 190))
    uniforme = next(e for e in lm.candidatos_del_juego(juego) if e.familia == "uniforme")
    entradas = [uniforme, *(lm.CATALOGO[i] for i in modelos(juego))]
    informe, _ = le.evaluar(instantanea, entradas, PROTOCOLO)
    esperados = informe["muestra_comun"]["objetivos"]
    bloques = [b["objetivos"] for b in informe["muestra_comun"]["bloques"]]
    assert len(informe["candidatos"]) == 6 and len(bloques) == 2
    for candidato in informe["candidatos"]:
        assert candidato["estado"] == "completo", candidato
        assert [f["objetivo"] for f in candidato["por_objetivo"]] == esperados
        assert [b["objetivos"] for b in candidato["bloques"]] == bloques
        assert np.isfinite(candidato["agregado"]["log_loss"])
        assert np.isfinite(candidato["agregado"]["brier"])
