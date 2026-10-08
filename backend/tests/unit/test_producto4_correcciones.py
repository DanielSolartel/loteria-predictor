"""Producto 4: regresiones de la revision de la primera entrega.

1. `ajustar_cardinalidad` debe rechazar `+inf`, `-inf` y `NaN` antes de
   recortar (el recorte convertia un infinito en un extremo finito y la salida
   no valida pasaba como una prediccion normal).
2. Dos ajustes solapados no pueden cambiar los hilos de las bibliotecas
   numericas del proceso que los llama: `threadpool_limits` es de proceso,
   asi que un limite tomado por el laboratorio en el proceso web alteraba el
   entorno numerico compartido con Producto 3. Se comprueba en un proceso
   aislado, con eventos y tiempos maximos acotados."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from tests.unit import fixtures_producto4 as f4

BACKEND = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("valor", [float("inf"), float("-inf"), float("nan")])
def test_cardinalidad_rechaza_valores_no_finitos_antes_de_recortar(valor):
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        lm.ajustar_cardinalidad([valor] + [5 / 43] * 42, 5)
    assert error.value.estado == "salida_invalida"


def test_cardinalidad_conserva_los_extremos_finitos_y_el_orden():
    extremas = np.array([1.0] * 6 + [0.0] * 37)
    a = lm.ajustar_cardinalidad(extremas, 5)
    assert a.max() < 1 and a.min() > 0 and abs(a.sum() - 5) <= lm.TOLERANCIA_CARDINALIDAD
    crudas = np.linspace(0.01, 0.6, 43)
    b = lm.ajustar_cardinalidad(crudas, 5)
    assert np.array_equal(np.argsort(-b, kind="stable"), np.argsort(-crudas, kind="stable"))
    assert np.array_equal(b, lm.ajustar_cardinalidad(crudas, 5))


@pytest.mark.parametrize("valor", [float("inf"), float("-inf")])
def test_infinito_del_estimador_antes_del_ajuste_es_salida_invalida(valor):
    instantanea = lv.validar_instantanea("MILOTO", f4.historico("MILOTO", 87))
    variables = lv.Variables(instantanea)
    ajustado = lm.ajustar_candidato(lm.CATALOGO["logistica_regularizada"], instantanea, variables, 70)
    original = ajustado.estimador.predict_proba

    def con_infinito(X):
        p = original(X)
        p[0, 1] = valor
        return p
    ajustado.estimador.predict_proba = con_infinito
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        ajustado.predecir(variables.filas([70]))
    assert error.value.estado == "salida_invalida"


SONDA = textwrap.dedent("""
    import json, threading
    import numpy as np
    from threadpoolctl import threadpool_info
    from app.application.ml import laboratorio_modelos as lm

    ESPERA = 30
    def hilos():
        return sorted((i["internal_api"], i["num_threads"]) for i in threadpool_info())

    class Espia:
        def __init__(self, dentro, salir):
            self.dentro, self.salir = dentro, salir
        def fit(self, X, y):
            self.dentro.set()
            assert self.salir.wait(ESPERA)
            return self

    eventos = {k: (threading.Event(), threading.Event()) for k in "AB"}
    fallos = []
    def ajustar(clave):
        try:
            lm._ajustar(Espia(*eventos[clave]), np.zeros((2, 1)), np.zeros(2))
        except BaseException as error:
            fallos.append(repr(error))
    observado = {"antes": hilos()}
    a = threading.Thread(target=ajustar, args=("A",)); a.start()
    assert eventos["A"][0].wait(ESPERA); observado["A_dentro"] = hilos()
    b = threading.Thread(target=ajustar, args=("B",)); b.start()
    assert eventos["B"][0].wait(ESPERA); observado["A_y_B_dentro"] = hilos()
    eventos["A"][1].set(); a.join(ESPERA); observado["A_fuera_B_dentro"] = hilos()
    eventos["B"][1].set(); b.join(ESPERA); observado["despues"] = hilos()
    print(json.dumps({"observado": observado, "fallos": fallos}))
""")


def test_ajustes_solapados_no_cambian_los_hilos_del_proceso_que_los_llama():
    entorno = {**os.environ, "OPENBLAS_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "PYTHONPATH": str(BACKEND)}
    r = subprocess.run([sys.executable, "-c", SONDA], cwd=BACKEND, env=entorno, capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    observado = datos["observado"]
    assert not datos["fallos"]
    assert any(n > lm.HILOS for _, n in observado["antes"]), "la sonda necesita un punto de partida mayor que HILOS"
    for momento, valor in observado.items():
        assert valor == observado["antes"], (momento, observado)


def test_reproduccion_no_comparable_da_null_y_no_un_infinito():
    from app.application.ml import laboratorio_artefactos as la

    guardado = {"esquema": la.ESQUEMA_EXPERIMENTO, "candidatos": [{"id": "m", "por_objetivo": [{"objetivo": 1, "log_loss": 0.3}]}]}
    otro = {"candidatos": [{"id": "m", "por_objetivo": [{"objetivo": 2, "log_loss": 0.3}]}]}
    r = la.comparar_reproduccion(guardado, otro)
    assert r["maxima_diferencia_de_log_loss"] is None and r["huella_exacta"] is False
    json.dumps(r, allow_nan=False)  # JSON valido (sin Infinity)
