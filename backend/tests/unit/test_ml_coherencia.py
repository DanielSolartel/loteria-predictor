"""Receta frente al estado real: entrada pública y manifiestos completos.

Cada mutación conserva JSON canónico y recalcula las huellas interior,
exterior y del manifiesto. La incompatibilidad no es un fallo de integridad.
Los modelos de partida se ajustan con las bibliotecas reales.
"""
import copy
import json
from unittest.mock import patch

import numpy as np
import pytest

from app.application.ml import laboratorio_artefactos as la
from app.application.ml import modelos_registrados as mr
from tests.unit.test_ml_cinco_flujo import laboratorios, sin_entrenamiento


def version(laboratorios, juego, modelo):
    d = laboratorios(juego)
    g = d["e"].almacen_laboratorio.obtener_modelo(d["versiones"][modelo]["modelo_registrado"])
    return g.artefacto, d["e"].almacen_laboratorio.leer_estimador(g)


def mutar(a, contenido, cambiar):
    a, d = copy.deepcopy(a), json.loads(contenido)
    cambiar(d["estimador"])
    e = d["estimador"]
    if "contenido" in e:
        e["sha256_contenido"] = mr.sha256(e["contenido"].encode("utf-8"))
    b = la.serializar_entrada(d)
    a["estimador"].update(bytes=len(b), sha256=mr.sha256(b))
    a = mr.componer(mr.cuerpo_de(a), a["publicacion"])
    assert mr.integro(a) and mr.compatibilidad(a)["compatible"]
    assert la.serializar_entrada(json.loads(b)) == b
    return a, b


@pytest.mark.parametrize("juego", ["BALOTO", "COLORLOTO"])
@pytest.mark.parametrize("campo", ["alpha", "arquitectura"])
def test_mlp_receta_y_matrices_por_entrada_publica(laboratorios, juego, campo):
    modelo = "red_neuronal_poisson" if juego == "COLORLOTO" else "red_neuronal_binaria"
    a, b = version(laboratorios, juego, modelo)
    def cambiar(e):
        if campo == "alpha":
            e["parametros"]["alpha"] = 999
        else:
            m = json.loads(e["contenido"])
            m["pesos"][0] = np.asarray(m["pesos"][0])[:, :1].tolist()
            m["pesos"][1] = m["pesos"][1][:1]
            m["sesgos"][0] = m["sesgos"][0][:1]
            e["contenido"] = json.dumps(m, sort_keys=True, separators=(",", ":"))
    a, b = mutar(a, b, cambiar)
    with pytest.raises(mr.ModeloRegistradoError, match="receta|arquitectura"):
        mr.cargar_estimador(a, b)


@pytest.mark.parametrize("familia", ["xgboost", "lightgbm"])
@pytest.mark.parametrize("juego", ["BALOTO", "COLORLOTO"])
def test_parametros_nativos_antes_del_cargador_real(laboratorios, juego, familia):
    modelo = familia + ("_poisson" if juego == "COLORLOTO" else "_binario")
    a, b = version(laboratorios, juego, modelo)
    a, b = mutar(a, b, lambda e: e["parametros"].update(max_depth=99))
    # Espías sobre los cargadores verdaderos: no se reemplaza la deserialización.
    if familia == "xgboost":
        import xgboost as lib
        original = lib.Booster.load_model
        with patch.object(lib.Booster, "load_model", autospec=True, side_effect=original) as cargar:
            with pytest.raises(mr.ModeloRegistradoError, match="receta"):
                mr.cargar_estimador(a, b)
            cargar.assert_not_called()
    else:
        import lightgbm as lib
        with patch.object(lib, "Booster", wraps=lib.Booster) as cargar:
            with pytest.raises(mr.ModeloRegistradoError, match="receta"):
                mr.cargar_estimador(a, b)
            cargar.assert_not_called()


@pytest.mark.parametrize("familia", ["xgboost", "lightgbm"])
@pytest.mark.parametrize("juego", ["BALOTO", "COLORLOTO"])
@pytest.mark.parametrize("campo", ["dimension", "objetivo", "preparacion"])
def test_contenido_nativo_incompatible_no_invoca_loader(laboratorios, juego, familia, campo):
    modelo = familia + ("_poisson" if juego == "COLORLOTO" else "_binario")
    a, b = version(laboratorios, juego, modelo)
    def cambiar(e):
        if campo == "preparacion":
            e["preparacion"]["categorias"][0] = -999
        elif familia == "xgboost":
            nativo = json.loads(e["contenido"])
            learner = nativo["learner"]
            if campo == "dimension":
                learner["learner_model_param"]["num_feature"] = "999"
            else:
                learner["objective"]["name"] = "reg:squarederror"
            e["contenido"] = json.dumps(nativo)
        elif campo == "dimension":
            e["contenido"] = "\n".join("max_feature_idx=999" if s.startswith("max_feature_idx=") else s
                                         for s in e["contenido"].splitlines())
        else:
            e["contenido"] = "\n".join("objective=regression" if s.startswith("objective=") else s
                                         for s in e["contenido"].splitlines())
    a, b = mutar(a, b, cambiar)
    if familia == "xgboost":
        import xgboost as lib
        with patch.object(lib.Booster, "load_model", autospec=True, side_effect=lib.Booster.load_model) as cargar:
            with pytest.raises(mr.ModeloRegistradoError):
                mr.cargar_estimador(a, b)
            cargar.assert_not_called()
    else:
        import lightgbm as lib
        with patch.object(lib, "Booster", wraps=lib.Booster) as cargar:
            with pytest.raises(mr.ModeloRegistradoError):
                mr.cargar_estimador(a, b)
            cargar.assert_not_called()


@pytest.mark.parametrize("campo", ["universo", "kappa", "tolerancia", "max_nodos", "identidades"])
def test_bayes_numerico_receta_y_reglas_publicas(laboratorios, campo):
    a, b = version(laboratorios, "BALOTO", "bayes_jerarquico_binario")
    def cambiar(e):
        if campo == "identidades":
            e[campo][0] = 999
        else:
            e[campo] = {"universo": 39, "kappa": 99, "tolerancia": 1e-3, "max_nodos": 256}[campo]
    a, b = mutar(a, b, cambiar)
    with pytest.raises(mr.ModeloRegistradoError, match="receta|reglas|soporte"):
        mr.cargar_estimador(a, b)


@pytest.mark.parametrize("juego", ["BALOTO", "COLORLOTO"])
@pytest.mark.parametrize("campo", ["deterministic", "force_col_wise", "objective"])
def test_parametros_del_texto_lightgbm_antes_de_cargar(laboratorios, juego, campo):
    modelo = "lightgbm_poisson" if juego == "COLORLOTO" else "lightgbm_binario"
    a, b = version(laboratorios, juego, modelo)
    def cambiar(e):
        original = "regression" if campo == "objective" else "0"
        lineas = e["contenido"].splitlines()
        assert any(s.startswith("[" + campo + ": ") for s in lineas)
        e["contenido"] = "\n".join("[" + campo + ": " + original + "]" if s.startswith("[" + campo + ": ") else s
                                     for s in lineas)
    a, b = mutar(a, b, cambiar)
    import lightgbm as lib
    with patch.object(lib, "Booster", wraps=lib.Booster) as cargar:
        with pytest.raises(mr.ModeloRegistradoError):
            mr.cargar_estimador(a, b)
        cargar.assert_not_called()


@pytest.mark.parametrize("juego", ["BALOTO", "COLORLOTO"])
@pytest.mark.parametrize("familia", ["xgboost", "lightgbm"])
def test_dimension_de_salida_nativa_precede_al_loader(laboratorios, juego, familia):
    modelo = familia + ("_poisson" if juego == "COLORLOTO" else "_binario")
    a, b = version(laboratorios, juego, modelo)
    def cambiar(e):
        if familia == "xgboost":
            n = json.loads(e["contenido"])
            n["learner"]["learner_model_param"]["num_target"] = "2"
            e["contenido"] = json.dumps(n)
        else:
            e["contenido"] = e["contenido"].replace("num_class=1\n", "num_class=2\n")
    a, b = mutar(a, b, cambiar)
    # No pasamos intencionadamente un formato de salida incompatible a código
    # nativo: el deserializador real debe detenerse antes de este punto.
    if familia == "xgboost":
        import xgboost as lib
        with patch.object(lib.Booster, "load_model", side_effect=AssertionError("loader nativo alcanzado")) as cargar:
            with pytest.raises(mr.ModeloRegistradoError):
                mr.cargar_estimador(a, b)
            cargar.assert_not_called()
    else:
        import lightgbm as lib
        with patch.object(lib, "Booster", side_effect=AssertionError("loader nativo alcanzado")) as cargar:
            with pytest.raises(mr.ModeloRegistradoError):
                mr.cargar_estimador(a, b)
            cargar.assert_not_called()


@pytest.mark.parametrize("juego", ["BALOTO", "COLORLOTO"])
@pytest.mark.parametrize("campo", ["universo", "fuerza", "identidades"])
def test_markov_parametros_y_soporte_publicos(laboratorios, juego, campo):
    a, b = version(laboratorios, juego, "markov_pares" if juego == "COLORLOTO" else "markov_apariciones")
    def cambiar(e):
        if campo == "identidades":
            e[campo][0] = 999
            return
        if campo == "fuerza":
            e[campo] = 99
        else:
            e[campo] += 7
            e["p"] = (1 if juego == "COLORLOTO" else 5) / e[campo]
            import math
            e["prior"] = [math.comb(e["estados"] - 1, k) * e["p"] ** k * (1-e["p"]) ** (e["estados"]-1-k)
                          for k in range(e["estados"])]
        total = np.asarray(e["cuentas"]) + e["fuerza"] * np.asarray(e["prior"])
        e["transiciones"] = (total / total.sum(axis=2, keepdims=True)).tolist()
    a, b = mutar(a, b, cambiar)
    with pytest.raises(mr.ModeloRegistradoError, match="receta|reglas|soporte"):
        mr.cargar_estimador(a, b)


def test_bayes_pares_identidad_codificada_publica(laboratorios):
    a, b = version(laboratorios, "COLORLOTO", "bayes_jerarquico_pares")
    a, b = mutar(a, b, lambda e: e["identidades"].__setitem__(0, 999))
    with pytest.raises(mr.ModeloRegistradoError, match="reglas|soporte"):
        mr.cargar_estimador(a, b)


@pytest.mark.parametrize("juego", ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"])
def test_artefactos_validos_recargan_por_entrada_publica_sin_fit(laboratorios, juego):
    from tests.unit.test_ml_cinco_flujo import modelos
    for modelo in modelos(juego):
        a, b = version(laboratorios, juego, modelo)
        with sin_entrenamiento():
            assert mr.cargar_estimador(a, b) is not None
