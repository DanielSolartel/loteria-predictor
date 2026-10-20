"""Cinco familias: XGBoost/LightGBM CPU reales y una MLP regularizada.

Solo fit/carga del formato correspondiente importa bibliotecas nativas. La
preparación y calibración se congelan; inferir nunca ajusta. La calibración
recibe del coordinador un bloque posterior a BASE y anterior a evaluación.
Los formatos nativos llevan integridad interna además del manifiesto exterior.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from app.application.ml import modelo as mdl

VERSION = "ml-boost-red/1"
IDS = ("xgboost_binario", "xgboost_poisson", "lightgbm_binario", "lightgbm_poisson",
       "red_neuronal_binaria", "red_neuronal_poisson")


class ModeloBoostRedError(ValueError):
    def __init__(self, motivo: str, estado: str = "fallo_de_ajuste"):
        self.estado = estado
        super().__init__(motivo)


def _matriz(X):
    A = np.asarray(X, dtype=float)
    if A.ndim != 2 or A.shape[1] != 8 or not np.isfinite(A).all():
        raise ModeloBoostRedError("se requieren ocho variables finitas", "salida_invalida")
    return A


def _vector(y, n):
    a = np.asarray(y, dtype=float)
    if a.shape != (n,) or not np.isfinite(a).all() or (a < 0).any():
        raise ModeloBoostRedError("etiquetas no negativas finitas requeridas", "salida_invalida")
    return a


def _sigmoide(z):
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1 / (1 + np.exp(-z[pos]))
    exp = np.exp(z[~pos])
    out[~pos] = exp / (1 + exp)
    return out


def _logit(p):
    a = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    return np.log(a) - np.log1p(-a)


def _ajuste_controlado(estimador, X, y):
    if mdl.ajustar_registrando_convergencia(estimador, X, y):
        raise ModeloBoostRedError("el ajuste agotó su presupuesto sin converger", "no_converge")
    return estimador


@dataclass
class Preparacion:
    categorias: np.ndarray
    media: np.ndarray
    escala: np.ndarray

    @classmethod
    def ajustar(cls, X):
        return cls(*mdl.preparar_variables_ml_adicionales(_matriz(X)))

    def transformar(self, X):
        A = _matriz(X)
        onehot = (A[:, :1] == self.categorias[None, :]).astype(float)
        return np.column_stack((onehot, (A[:, 1:] - self.media) / self.escala))

    def to_dict(self):
        return {"categorias": self.categorias.tolist(), "media": self.media.tolist(),
                "escala": self.escala.tolist()}

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict) or set(d) != {"categorias", "media", "escala"}:
            raise ModeloBoostRedError("preparación incompleta")
        cat, med, esc = (np.asarray(d[k], dtype=float) for k in ("categorias", "media", "escala"))
        if cat.ndim != 1 or not 1 <= len(cat) <= 4096 or len(set(cat.tolist())) != len(cat) or \
                med.shape != (7,) or esc.shape != (7,) or not all(np.isfinite(a).all() for a in (cat, med, esc)) or \
                not (esc > 0).all():
            raise ModeloBoostRedError("parámetros de preparación inválidos")
        return cls(cat, med, esc)


class EstimadorBoostRed:
    """Estimador congelado de ocho columnas raw; no expone fit ni partial_fit."""
    classes_ = np.array([0, 1])

    def __init__(self, candidato_id, preparacion, modelo, parametros, calibracion=None):
        self.candidato_id = candidato_id
        self.preparacion = preparacion
        self.modelo = modelo
        self.parametros = dict(parametros)
        self.calibracion = calibracion
        self.binario = candidato_id.endswith("binario") or candidato_id.endswith("binaria")
        self.familia = ("xgboost" if candidato_id.startswith("xgboost") else
                        "lightgbm" if candidato_id.startswith("lightgbm") else "redes_neuronales")

    def _crudas(self, X):
        A = self.preparacion.transformar(X)
        if self.familia == "xgboost":
            import xgboost as xgb
            pred = self.modelo.predict(xgb.DMatrix(A, nthread=1))
        elif self.familia == "lightgbm":
            pred = self.modelo.predict(A, num_threads=1)
        else:
            actual = A
            for W, b in zip(self.modelo["pesos"][:-1], self.modelo["sesgos"][:-1]):
                actual = np.tanh(actual @ W + b)
            z = (actual @ self.modelo["pesos"][-1] + self.modelo["sesgos"][-1]).ravel()
            pred = _sigmoide(z) if self.binario else np.exp(z)
        pred = np.asarray(pred, dtype=float).reshape(-1)
        if pred.shape != (len(A),) or not np.isfinite(pred).all() or (pred < 0).any() or \
                (self.binario and (pred > 1).any()):
            raise ModeloBoostRedError("salida no finita o fuera del dominio", "salida_invalida")
        return pred

    def predict_proba(self, X):
        if not self.binario:
            raise ModeloBoostRedError("el estimador de conteos produce intensidades")
        p = self._crudas(X)
        if self.calibracion is not None:
            p = _sigmoide(self.calibracion[0] * _logit(p) + self.calibracion[1])
        return np.column_stack((1 - p, p))

    def predict(self, X):
        return self._crudas(X) if not self.binario else (self.predict_proba(X)[:, 1] >= .5).astype(int)

    def componentes_de_inferencia(self):
        out = [{"paso": "preparacion_de_variables", "clase": "OneHotEncoder+StandardScaler",
                "detalle": "categorías, media y escala congeladas; ajuste exclusivo con BASE"},
               {"paso": "estimador", "clase": self.familia,
                "detalle": "modelo CPU nativo congelado" if self.familia != "redes_neuronales" else
                           "MLP tanh regularizada; matrices y sesgos congelados"}]
        if self.calibracion is not None:
            out.append({"paso": "calibracion", "clase": "SigmoideLogistica",
                        "detalle": "logit y sigmoide ajustados solo con el bloque cronológico de calibración"})
        return out

    def valores_globales(self, nombres):
        if self.familia == "redes_neuronales":
            return {"motivo": "la MLP no ofrece importancias globales comparables; sus pesos no equivalen a "
                              "contribuciones ni causalidad", "estimador": "MLP"}
        if len(nombres) != 8:
            return {"motivo": "no se pudieron asociar las ocho variables"}
        columnas = [(nombres[0], f"{nombres[0]}={int(c) if c.is_integer() else c}")
                    for c in self.preparacion.categorias]
        columnas += [(n, n) for n in nombres[1:]]
        if self.familia == "xgboost":
            ganancias = self.modelo.get_score(importance_type="total_gain")
            valores = [float(ganancias.get(f"f{i}", 0.)) for i in range(len(columnas))]
        else:
            valores = self.modelo.feature_importance(importance_type="gain").astype(float).tolist()
        return {"motivo": None, "estimador": self.familia, "calibrado": self.calibracion is not None,
                "tipo": "ganancia_total_de_particiones", "columnas": columnas, "valores": valores}

    importancias_globales = valores_globales

    def to_dict(self):
        if self.familia == "xgboost":
            formato, contenido = "xgboost-json", bytes(self.modelo.save_raw(raw_format="json")).decode("utf-8")
        elif self.familia == "lightgbm":
            formato, contenido = "lightgbm-texto", self.modelo.model_to_string()
        else:
            formato = "mlp-matrices-json"
            contenido = json.dumps({"pesos": [a.tolist() for a in self.modelo["pesos"]],
                                    "sesgos": [a.tolist() for a in self.modelo["sesgos"]]},
                                   sort_keys=True, separators=(",", ":"), allow_nan=False)
        return {"version": VERSION, "candidato_id": self.candidato_id, "preparacion": self.preparacion.to_dict(),
                "parametros": self.parametros, "calibracion": list(self.calibracion) if self.calibracion else None,
                "formato": formato, "contenido": contenido,
                "sha256_contenido": hashlib.sha256(contenido.encode("utf-8")).hexdigest()}

    como_dict = to_dict

    @classmethod
    def from_dict(cls, d):
        try:
            if not isinstance(d, dict) or d.get("version") != VERSION or d.get("candidato_id") not in IDS:
                raise ModeloBoostRedError("versión o identidad no admitida")
            identificador = d["candidato_id"]
            familia = identificador.split("_")[0]
            formato = {"xgboost": "xgboost-json", "lightgbm": "lightgbm-texto", "red": "mlp-matrices-json"}[familia]
            contenido = d["contenido"]
            if d["formato"] != formato or not isinstance(contenido, str) or \
                    hashlib.sha256(contenido.encode("utf-8")).hexdigest() != d["sha256_contenido"]:
                raise ModeloBoostRedError("integridad o formato nativo incorrecto")
            prep = Preparacion.from_dict(d["preparacion"])
            parametros = d["parametros"]
            if not isinstance(parametros, dict):
                raise ModeloBoostRedError("parámetros incompletos")
            calibracion = d["calibracion"]
            binario = identificador.endswith("binario") or identificador.endswith("binaria")
            if binario:
                if not isinstance(calibracion, list) or len(calibracion) != 2 or \
                        not np.isfinite(np.asarray(calibracion, dtype=float)).all():
                    raise ModeloBoostRedError("calibración binaria incompleta")
            elif calibracion is not None:
                raise ModeloBoostRedError("calibración inesperada para conteos")
            dimension = len(prep.categorias) + 7
            # Toda validación de la envoltura precede a la carga de código nativo.
            if familia == "xgboost":
                datos = json.loads(contenido)
                if int(datos["learner"]["learner_model_param"]["num_feature"]) != dimension:
                    raise ModeloBoostRedError("dimensión nativa incompatible")
                objetivo = datos["learner"]["objective"]["name"]
                if objetivo != ("binary:logistic" if binario else "count:poisson"):
                    raise ModeloBoostRedError("objetivo nativo incompatible")
                import xgboost as xgb
                modelo = xgb.Booster(params={"nthread": 1, "device": "cpu"})
                modelo.load_model(bytearray(contenido, "utf-8"))
                modelo.set_param({"nthread": 1, "device": "cpu"})
            elif familia == "lightgbm":
                lineas = contenido.splitlines()
                if f"max_feature_idx={dimension - 1}" not in lineas:
                    raise ModeloBoostRedError("dimensión nativa incompatible")
                if not any(a.startswith("objective=" + ("binary" if binario else "poisson")) for a in lineas):
                    raise ModeloBoostRedError("objetivo nativo incompatible")
                import lightgbm as lgb
                modelo = lgb.Booster(model_str=contenido)
            else:
                matrices = json.loads(contenido)
                pesos = [np.asarray(a, dtype=float) for a in matrices["pesos"]]
                sesgos = [np.asarray(a, dtype=float) for a in matrices["sesgos"]]
                if len(pesos) != 2 or len(sesgos) != 2 or pesos[0].ndim != 2 or \
                        pesos[0].shape[0] != dimension or not 1 <= pesos[0].shape[1] <= 128 or \
                        pesos[1].shape != (pesos[0].shape[1], 1) or \
                        any(b.shape != (W.shape[1],) for W, b in zip(pesos, sesgos)) or \
                        not all(np.isfinite(a).all() for a in pesos + sesgos):
                    raise ModeloBoostRedError("dimensiones o pesos neuronales inválidos")
                modelo = {"pesos": pesos, "sesgos": sesgos}
            return cls(identificador, prep, modelo, parametros, tuple(calibracion) if calibracion else None)
        except ModeloBoostRedError:
            raise
        except (KeyError, ValueError, TypeError, IndexError, OverflowError) as exc:
            raise ModeloBoostRedError("contrato del modelo incompleto o inválido") from exc

    desde_dict = from_dict


def deserializar_boost_red(d):
    return EstimadorBoostRed.from_dict(d)


def _parametros_efectivos(candidato_id, p):
    """Una única traducción de receta a parámetros reales de cada biblioteca."""
    semilla = int(p.get("semilla", p.get("random_state", 42)))
    binario = candidato_id.endswith("binario") or candidato_id.endswith("binaria")
    if candidato_id.startswith(("xgboost", "lightgbm")):
        rondas = int(p.get("num_boost_round", p.get("n_estimators", 60)))
        if not 1 <= rondas <= 1000:
            raise ModeloBoostRedError("presupuesto de rondas inválido")
        comunes = {"max_depth": int(p.get("max_depth", 3)),
                   "num_boost_round": rondas}
        if candidato_id.startswith("xgboost"):
            return {**comunes, "objective": "binary:logistic" if binario else "count:poisson",
                    "tree_method": "hist", "device": "cpu", "nthread": 1, "seed": semilla,
                    "eta": float(p.get("learning_rate", .08)), "lambda": float(p.get("regularizacion_L2", 5.)),
                    "min_child_weight": float(p.get("min_hoja", 20)), "verbosity": 0}
        return {**comunes, "objective": "binary" if binario else "poisson", "num_threads": 1,
                "deterministic": True, "force_col_wise": True, "seed": semilla,
                "feature_fraction_seed": semilla, "bagging_seed": semilla, "data_random_seed": semilla,
                "num_leaves": 7, "learning_rate": float(p.get("learning_rate", .08)),
                "lambda_l2": float(p.get("regularizacion_L2", 5.)),
                "min_data_in_leaf": int(p.get("min_hoja", 20)), "verbosity": -1}
    capas = tuple(p.get("hidden_layer_sizes", (12,)))
    if len(capas) != 1 or not 1 <= int(capas[0]) <= 128:
        raise ModeloBoostRedError("se requiere una capa oculta de 1 a 128 neuronas")
    return {"hidden_layer_sizes": capas, "activation": "tanh", "alpha": float(p.get("alpha", 10.)),
            "solver": "lbfgs", "max_iter": int(p.get("max_iter", 600)),
            "max_fun": int(p.get("max_fun", 20000)), "tol": float(p.get("tol", 1e-4)),
            "early_stopping": False, "random_state": semilla, "loss": "log_loss" if binario else "poisson"}


def validar_receta(d, receta, identidad=None):
    """Verifica parámetros y familia declarados ANTES de cualquier carga nativa.

    La procedencia, entorno e integridad exterior las comprueba el registro.
    Esta traducción también es la empleada al ajustar: no hay dos recetas.
    """
    try:
        identificador = receta["id"]
        if identificador not in IDS or d["candidato_id"] != identificador:
            raise ModeloBoostRedError("identidad distinta de la receta declarada")
        esperado = _parametros_efectivos(identificador, receta.get("parametros", {}))
        if json.dumps(d["parametros"], sort_keys=True, allow_nan=False) != \
                json.dumps(esperado, sort_keys=True, allow_nan=False):
            raise ModeloBoostRedError("parámetros efectivos distintos de la receta declarada")
        prep = Preparacion.from_dict(d["preparacion"])
        dimension = len(prep.categorias) + 7
        if identidad is not None:
            from app.application.ml import laboratorio_variables as lv
            reglas = lv.REGLAS[identidad["juego"]]
            soporte = (sorted(lv.codigo_de_par(n, c) for c in identidad["paleta_del_corte"]
                              for n in reglas.candidatos) if reglas.colores else list(reglas.candidatos))
            categorias = prep.categorias.tolist()
            # En pares, BASE puede preceder a la primera aparición de un color
            # del corte completo. Nunca se admite una categoría ajena al corte.
            if categorias != sorted(categorias) or not set(categorias) <= set(soporte) or \
                    (not reglas.colores and categorias != soporte):
                raise ModeloBoostRedError("soporte de preparación incompatible con reglas del juego")
        contenido = d["contenido"]
        if not isinstance(contenido, str) or hashlib.sha256(contenido.encode("utf-8")).hexdigest() != d["sha256_contenido"]:
            raise ModeloBoostRedError("integridad nativa incorrecta")
        if identificador.startswith("red_neuronal"):
            matrices = json.loads(contenido)
            pesos = [np.asarray(a, dtype=float) for a in matrices["pesos"]]
            sesgos = [np.asarray(a, dtype=float) for a in matrices["sesgos"]]
            oculta = esperado["hidden_layer_sizes"][0]
            if len(pesos) != 2 or len(sesgos) != 2 or \
                    [a.shape for a in pesos] != [(dimension, oculta), (oculta, 1)] or \
                    [a.shape for a in sesgos] != [(oculta,), (1,)] or \
                    not all(np.isfinite(a).all() for a in pesos + sesgos):
                raise ModeloBoostRedError("arquitectura neuronal distinta de la receta declarada")
        elif identificador.startswith("xgboost"):
            nativo = json.loads(contenido)["learner"]
            arboles = nativo["gradient_booster"]["model"]
            if int(nativo["learner_model_param"]["num_feature"]) != dimension or \
                    int(nativo["learner_model_param"]["num_target"]) != 1 or \
                    int(nativo["learner_model_param"]["num_class"]) != 0 or \
                    nativo["gradient_booster"]["name"] != "gbtree" or \
                    nativo["objective"]["name"] != esperado["objective"] or \
                    int(arboles["gbtree_model_param"]["num_trees"]) != esperado["num_boost_round"] or \
                    int(arboles["gbtree_model_param"]["num_parallel_tree"]) != 1 or \
                    len(arboles["trees"]) != esperado["num_boost_round"] or \
                    arboles["tree_info"] != [0] * esperado["num_boost_round"] or \
                    arboles["iteration_indptr"] != list(range(esperado["num_boost_round"] + 1)) or \
                    any(int(a["tree_param"]["num_feature"]) != dimension or
                        int(a["tree_param"]["size_leaf_vector"]) != 1 for a in arboles["trees"]):
                raise ModeloBoostRedError("dimensiones, objetivo o rondas nativas distintos de la receta")
        else:
            lineas = contenido.splitlines()
            if "num_class=1" not in lineas or "num_tree_per_iteration=1" not in lineas or \
                    f"max_feature_idx={dimension - 1}" not in lineas or \
                    not any(a.startswith("objective=") and a.split("=", 1)[1].split()[0] == esperado["objective"]
                            for a in lineas):
                raise ModeloBoostRedError("dimensiones u objetivo nativos distintos de la receta")
            # LightGBM guarda los parámetros efectivos en su formato textual.
            parametros = dict(a[1:-1].split(": ", 1) for a in lineas if a.startswith("[") and a.endswith("]") and ": " in a)
            for clave, valor in esperado.items():
                if clave == "num_boost_round":
                    continue  # el formato lo llama num_iterations
                if (parametros[clave] != valor if isinstance(valor, str) else float(parametros[clave]) != valor):
                    raise ModeloBoostRedError("parámetros nativos distintos de la receta declarada")
            # Puede terminar antes si no existe ninguna partición con ganancia;
            # el formato conserva num_iterations como presupuesto solicitado.
            if int(parametros["num_iterations"]) != esperado["num_boost_round"] or \
                    not 1 <= sum(a.startswith("Tree=") for a in lineas) <= esperado["num_boost_round"]:
                raise ModeloBoostRedError("rondas nativas distintas del presupuesto de la receta")
    except ModeloBoostRedError:
        raise
    except (KeyError, ValueError, TypeError, IndexError, OverflowError) as exc:
        raise ModeloBoostRedError("receta incompleta o inválida") from exc


def ajustar_boost_red(receta, X, y, *, X_calibracion=None, y_calibracion=None):
    """Ajuste real con receta explícita; BASE y CAL nunca se concatenan."""
    candidato_id = receta["id"]
    if candidato_id not in IDS:
        raise ModeloBoostRedError("candidato no reconocido")
    A = _matriz(X)
    etiquetas = _vector(y, len(A))
    binario = candidato_id.endswith("binario") or candidato_id.endswith("binaria")
    if not len(A):
        raise ModeloBoostRedError("BASE vacía", "muestra_insuficiente")
    if binario and set(etiquetas.tolist()) != {0., 1.}:
        raise ModeloBoostRedError("BASE requiere apariciones y ausencias", "clase_insuficiente")
    if binario:
        if X_calibracion is None or y_calibracion is None:
            raise ModeloBoostRedError("falta bloque cronológico de calibración", "muestra_insuficiente")
        C = _matriz(X_calibracion)
        yc = _vector(y_calibracion, len(C))
        if set(yc.tolist()) != {0., 1.}:
            raise ModeloBoostRedError("calibración requiere ambas clases", "clase_insuficiente")
    elif X_calibracion is not None or y_calibracion is not None:
        raise ModeloBoostRedError("los conteos no usan calibración sigmoide")
    prep = Preparacion.ajustar(A)
    Z = prep.transformar(A)
    p = dict(receta.get("parametros", {}))
    parametros = _parametros_efectivos(candidato_id, p)
    seed = int(p.get("semilla", p.get("random_state", 42)))
    try:
        if candidato_id.startswith("xgboost"):
            import xgboost as xgb
            ajuste = {k: v for k, v in parametros.items() if k != "num_boost_round"}
            modelo = xgb.train(ajuste, xgb.DMatrix(Z, label=etiquetas, nthread=1),
                               num_boost_round=parametros["num_boost_round"])
        elif candidato_id.startswith("lightgbm"):
            import lightgbm as lgb
            ajuste = {k: v for k, v in parametros.items() if k != "num_boost_round"}
            modelo = lgb.train(ajuste, lgb.Dataset(Z, label=etiquetas),
                               num_boost_round=parametros["num_boost_round"])
        else:
            ajuste = {k: v for k, v in parametros.items() if k != "loss"}
            estimador = mdl.construir_red_ml_adicional(binario, ajuste)
            _ajuste_controlado(estimador, Z, etiquetas)
            modelo = {"pesos": [a.copy() for a in estimador.coefs_],
                      "sesgos": [a.copy() for a in estimador.intercepts_]}
        resultado = EstimadorBoostRed(candidato_id, prep, modelo, parametros)
        if binario:
            logit = _logit(resultado._crudas(C)).reshape(-1, 1)
            cal = _ajuste_controlado(mdl.construir_calibrador_ml_adicional(seed), logit, yc)
            resultado.calibracion = (float(cal.coef_[0, 0]), float(cal.intercept_[0]))
        resultado.predict_proba(A[:1]) if binario else resultado.predict(A[:1])
        return resultado
    except ModeloBoostRedError:
        raise
    except Exception as exc:
        raise ModeloBoostRedError(f"fallo de ajuste real: {type(exc).__name__}: {str(exc)[:200]}") from exc
