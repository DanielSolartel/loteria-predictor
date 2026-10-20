"""ML real CPU: cuatro juegos, preparación causal y persistencia sin fit."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from threadpoolctl import threadpool_limits

from app.application.ml import laboratorio_boosts_redes as br
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from tests.unit import fixtures_producto4 as f4

CASOS = [(j, f) for j in lv.JUEGOS for f in ("xgboost", "lightgbm", "red_neuronal")]


def _id(juego, familia):
    return familia + ("_poisson" if juego == "COLORLOTO" else "_binaria" if familia == "red_neuronal" else "_binario")


def _receta(juego, familia):
    return {"id": _id(juego, familia), "parametros": {"num_boost_round": 12, "hidden_layer_sizes": [6],
                                                     "max_iter": 300, "semilla": 42}}


def _datos(juego):
    inst = lv.validar_instantanea(juego, f4.historico(juego, 110))
    var = lv.Variables(inst)
    filas = var.de_ajuste(100)
    if juego == "COLORLOTO":
        return filas.X, filas.y, {}, var.filas([100]), inst
    objetivos = sorted(set(filas.objetivos.tolist()))
    base, cal = lm.division_de_calibracion(objetivos)
    mask = np.isin(filas.objetivos, cal)
    return filas.X[~mask], filas.y[~mask], {"X_calibracion": filas.X[mask], "y_calibracion": filas.y[mask]}, \
        var.filas([100]), inst


@pytest.fixture(scope="module")
def ajustes():
    out = {}
    with threadpool_limits(1):
        for juego, familia in CASOS:
            X, y, cal, objetivo, inst = _datos(juego)
            modelo = br.ajustar_boost_red(_receta(juego, familia), X, y, **cal)
            out[juego, familia] = (modelo, objetivo, X, y, cal, inst)
    return out


@pytest.mark.parametrize("juego,familia", CASOS)
def test_ajuste_real_cuatro_juegos_y_contrato_probabilistico(ajustes, juego, familia):
    modelo, objetivo, _, _, _, inst = ajustes[juego, familia]
    if juego == "COLORLOTO":
        crudas = modelo.predict(objetivo.X)
        salida = lm.normalizar_intensidades(crudas)
        assert (crudas >= 0).all() and np.isfinite(crudas).all()
        assert abs(salida.sum() - 1) < 1e-12
        assert len(salida) == 7 * len(inst.paleta(100))
    else:
        p = modelo.predict_proba(objetivo.X)
        assert np.allclose(p.sum(axis=1), 1, rtol=0, atol=1e-15)
        salida = lm.ajustar_cardinalidad(p[:, 1], 5)
        assert abs(salida.sum() - 5) < 1e-9
        assert (salida > 0).all() and (salida < 1).all()
        assert modelo.calibracion is not None
    assert modelo.componentes_de_inferencia()[0]["paso"] == "preparacion_de_variables"
    assert not hasattr(modelo, "fit")
    if familia == "xgboost":
        assert type(modelo.modelo).__module__.startswith("xgboost")
        assert modelo.parametros["nthread"] == 1
    elif familia == "lightgbm":
        assert type(modelo.modelo).__module__.startswith("lightgbm")
        assert modelo.parametros["num_threads"] == 1
    else:
        assert modelo.parametros["solver"] == "lbfgs"
        assert modelo.parametros["early_stopping"] is False
        assert modelo.parametros["loss"] == ("poisson" if juego == "COLORLOTO" else "log_loss")


@pytest.mark.parametrize("juego,familia", CASOS)
def test_recarga_proceso_nuevo_sin_ningun_entrenamiento(ajustes, juego, familia, tmp_path):
    modelo, objetivo, *_ = ajustes[juego, familia]
    archivo = tmp_path / "modelo con espacios.json"
    archivo.write_text(json.dumps({"modelo": modelo.to_dict(), "X": objetivo.X.tolist()}), encoding="utf-8")
    codigo = '''import json, sys
from pathlib import Path
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, OneHotEncoder
import xgboost, lightgbm
from app.application.ml.laboratorio_boosts_redes import deserializar_boost_red

def prohibido(*a, **k):
    raise AssertionError("recarga o inferencia intentó entrenar")
for cls in (MLPClassifier, MLPRegressor, LogisticRegression, StandardScaler, OneHotEncoder):
    cls.fit = prohibido
xgboost.train = prohibido
lightgbm.train = prohibido
entrada = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
modelo = deserializar_boost_red(entrada["modelo"])
antes = modelo.to_dict()
p = modelo.predict_proba(entrada["X"]) if modelo.binario else modelo.predict(entrada["X"])
assert antes == modelo.to_dict(), "inferir cambió parámetros congelados"
print(json.dumps(p.tolist()))
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    r = subprocess.run([sys.executable, "-c", codigo, str(archivo)], check=True, capture_output=True,
                       text=True, env=env, timeout=45)
    p = modelo.predict_proba(objetivo.X) if modelo.binario else modelo.predict(objetivo.X)
    assert np.array_equal(np.asarray(json.loads(r.stdout)), p)


@pytest.mark.parametrize("familia", ("xgboost", "lightgbm", "red_neuronal"))
def test_preparacion_solo_base_y_calibracion_separada(ajustes, familia):
    modelo, objetivo, X, y, cal, _ = ajustes["MILOTO", familia]
    np.testing.assert_allclose(modelo.preparacion.media, X[:, 1:].mean(axis=0), rtol=0, atol=1e-13)
    assert np.array_equal(modelo.preparacion.categorias, np.unique(X[:, 0]))
    cambiado = cal["X_calibracion"].copy()
    cambiado[:, 0] = 999999  # categoría nueva exclusivamente en CAL: ignorada por preparación
    cambiado[:, 1:] += 5
    with threadpool_limits(1):
        otro = br.ajustar_boost_red(_receta("MILOTO", familia), X, y, X_calibracion=cambiado,
                                   y_calibracion=cal["y_calibracion"])
    assert modelo.preparacion.to_dict() == otro.preparacion.to_dict()
    assert modelo.to_dict()["contenido"] == otro.to_dict()["contenido"]  # BASE no usa CAL
    assert 999999 not in otro.preparacion.categorias
    congelado = modelo.to_dict()
    entrada = objetivo.X.copy()
    entrada[:, 1:] *= 1.01
    modelo.predict_proba(entrada)
    assert congelado == modelo.to_dict()


@pytest.mark.parametrize("juego", ("MILOTO", "COLORLOTO"))
@pytest.mark.parametrize("familia", ("xgboost", "lightgbm", "red_neuronal"))
def test_integridad_interna_rechazada_antes_carga_nativa(ajustes, juego, familia, monkeypatch):
    modelo = ajustes[juego, familia][0]
    d = modelo.to_dict()
    d["contenido"] += "ALTERADO"
    def prohibido(*a, **k):
        raise AssertionError("carga nativa antes de comprobar integridad")
    if familia == "xgboost":
        import xgboost
        monkeypatch.setattr(xgboost, "Booster", prohibido)
    elif familia == "lightgbm":
        import lightgbm
        monkeypatch.setattr(lightgbm, "Booster", prohibido)
    with pytest.raises(br.ModeloBoostRedError, match="integridad"):
        br.deserializar_boost_red(d)


@pytest.mark.parametrize("juego", ("MILOTO", "COLORLOTO"))
@pytest.mark.parametrize("familia", ("xgboost", "lightgbm", "red_neuronal"))
def test_preparacion_invalida_rechazada_antes_carga_nativa(ajustes, juego, familia, monkeypatch):
    d = ajustes[juego, familia][0].to_dict()
    d["preparacion"]["escala"][0] = 0
    if familia == "xgboost":
        import xgboost
        monkeypatch.setattr(xgboost, "Booster", lambda *a, **k: pytest.fail("carga nativa prematura"))
    elif familia == "lightgbm":
        import lightgbm
        monkeypatch.setattr(lightgbm, "Booster", lambda *a, **k: pytest.fail("carga nativa prematura"))
    with pytest.raises(br.ModeloBoostRedError, match="preparación"):
        br.deserializar_boost_red(d)


@pytest.mark.parametrize("familia", ("xgboost", "lightgbm"))
def test_importancias_son_ganancias_nativas_totales_sin_normalizar(ajustes, familia):
    modelo = ajustes["MILOTO", familia][0]
    d = modelo.valores_globales(lv.NOMBRES_VARIABLES_NUMEROS)
    assert d["tipo"] == "ganancia_total_de_particiones"
    assert len(d["columnas"]) == len(d["valores"]) == len(modelo.preparacion.categorias) + 7
    if familia == "xgboost":
        raw = modelo.modelo.get_score(importance_type="total_gain")
        esperado = [float(raw.get(f"f{i}", 0)) for i in range(len(d["columnas"]))]
    else:
        esperado = modelo.modelo.feature_importance(importance_type="gain").tolist()
    assert d["valores"] == esperado
    assert sum(esperado) > 0  # datos sintéticos, valores originales del backend


def test_red_no_fabrica_importancias_globales(ajustes):
    d = ajustes["MILOTO", "red_neuronal"][0].valores_globales(lv.NOMBRES_VARIABLES_NUMEROS)
    assert "no ofrece" in d["motivo"] and "valores" not in d


@pytest.mark.parametrize("juego", ("MILOTO", "COLORLOTO"))
def test_mlp_numpy_reproduce_estimador_real_sklearn(juego, monkeypatch):
    registrados = []
    original = br._ajuste_controlado
    def observar(estimador, X, y):
        ajustado = original(estimador, X, y)
        if type(ajustado).__name__.startswith("MLP"):
            registrados.append(ajustado)
        return ajustado
    monkeypatch.setattr(br, "_ajuste_controlado", observar)
    X, y, cal, objetivo, _ = _datos(juego)
    with threadpool_limits(1):
        modelo = br.ajustar_boost_red(_receta(juego, "red_neuronal"), X, y, **cal)
    Z = modelo.preparacion.transformar(objetivo.X)
    esperado = registrados[0].predict(Z) if juego == "COLORLOTO" else registrados[0].predict_proba(Z)[:, 1]
    np.testing.assert_allclose(modelo._crudas(objetivo.X), esperado, rtol=2e-15, atol=1e-15)


def test_importar_modulo_no_importa_bibliotecas_nativas():
    r = subprocess.run([sys.executable, "-c", "import sys; import app.application.ml.laboratorio_boosts_redes; "
                        "assert 'xgboost' not in sys.modules; assert 'lightgbm' not in sys.modules"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("clave,valor", [("version", "otra"), ("candidato_id", "alias_falso"),
                                       ("calibracion", None), ("formato", "pickle")])
def test_contrato_incompleto_o_version_invalida(ajustes, clave, valor):
    d = ajustes["MILOTO", "xgboost"][0].to_dict()
    d[clave] = valor
    with pytest.raises(br.ModeloBoostRedError):
        br.deserializar_boost_red(d)


@pytest.mark.parametrize("familia", ("xgboost", "lightgbm", "red_neuronal"))
def test_sin_dos_clases_no_hay_uniforme_encubierta(familia):
    X, y, cal, _, _ = _datos("MILOTO")
    with pytest.raises(br.ModeloBoostRedError) as exc:
        br.ajustar_boost_red(_receta("MILOTO", familia), X, np.zeros(len(y)), **cal)
    assert exc.value.estado == "clase_insuficiente"


def test_no_convergencia_neuronal_es_estado_explicito(monkeypatch):
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.neural_network import MLPClassifier
    def falla(*a, **k):
        import warnings
        warnings.warn("presupuesto agotado", ConvergenceWarning)
    monkeypatch.setattr(MLPClassifier, "fit", falla)
    X, y, cal, _, _ = _datos("MILOTO")
    with pytest.raises(br.ModeloBoostRedError) as exc:
        br.ajustar_boost_red(_receta("MILOTO", "red_neuronal"), X, y, **cal)
    assert exc.value.estado == "no_converge"


@pytest.mark.parametrize("juego", ("MILOTO", "COLORLOTO"))
@pytest.mark.parametrize("familia", ("xgboost", "lightgbm", "red_neuronal"))
def test_dimensiones_del_formato_rechazadas_antes_del_cargador(ajustes, juego, familia, monkeypatch):
    d = ajustes[juego, familia][0].to_dict()
    if familia == "xgboost":
        cuerpo = json.loads(d["contenido"])
        cuerpo["learner"]["learner_model_param"]["num_feature"] = "999"
        d["contenido"] = json.dumps(cuerpo)
        import xgboost
        monkeypatch.setattr(xgboost, "Booster", lambda *a, **k: pytest.fail("carga nativa prematura"))
    elif familia == "lightgbm":
        lineas = d["contenido"].splitlines()
        d["contenido"] = "\n".join("max_feature_idx=999" if a.startswith("max_feature_idx=") else a for a in lineas)
        import lightgbm
        monkeypatch.setattr(lightgbm, "Booster", lambda *a, **k: pytest.fail("carga nativa prematura"))
    else:
        cuerpo = json.loads(d["contenido"])
        cuerpo["pesos"][0].pop()
        d["contenido"] = json.dumps(cuerpo)
    d["sha256_contenido"] = hashlib.sha256(d["contenido"].encode()).hexdigest()
    with pytest.raises(br.ModeloBoostRedError, match="dimensi"):
        br.deserializar_boost_red(d)


@pytest.mark.parametrize("familia", ("xgboost", "lightgbm"))
def test_fallo_nativo_no_se_etiqueta_como_otro_modelo(familia, monkeypatch):
    if familia == "xgboost":
        import xgboost as biblioteca
    else:
        import lightgbm as biblioteca
    def falla(*a, **k):
        raise RuntimeError("fallo nativo inducido")
    monkeypatch.setattr(biblioteca, "train", falla)
    X, y, cal, _, _ = _datos("MILOTO")
    with pytest.raises(br.ModeloBoostRedError, match="fallo nativo inducido") as exc:
        br.ajustar_boost_red(_receta("MILOTO", familia), X, y, **cal)
    assert exc.value.estado == "fallo_de_ajuste"
