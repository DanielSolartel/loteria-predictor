"""
Producto 4 -catalogo de modelos del laboratorio y sus recetas.

Cada entrada del catalogo tiene identidad y version estables, juegos
admitidos, familia, variables, parametros fijados, requisitos de muestra y
una explicacion breve. Hay dos clases de entrada, siempre rotuladas:

- REFERENCIAS (no son modelos nuevos de aprendizaje automatico): la
  uniforme del juego y la estrategia actual de cada juego, adaptada sin
  cambiar su receta (logistica calibrada de AE-36 para Baloto y Revancha;
  frecuencia contraida hacia la uniforme para MiLoto; multinomial con
  suavizado aditivo para ColorLoto). Conservan sus probabilidades
  originales: no se les aplica ninguna transformacion nueva.
- MODELOS NUEVOS, que aprenden de las variables causales de
  `laboratorio_variables`:
  - numeros (Baloto, Revancha, MiLoto): regresion logistica regularizada y
    HistGradientBoostingClassifier, ambos con calibracion sigmoide sobre un
    bloque cronologico posterior al de ajuste (`PredefinedSplit`, nunca una
    division aleatoria) y despues el AJUSTE DE CARDINALIDAD;
  - ColorLoto: PoissonRegressor regularizado y HistGradientBoostingRegressor
    con perdida poisson, que aprenden intensidades de conteo de cada par y
    se NORMALIZAN a una distribucion de pares. Sin calibracion sigmoide.

AJUSTE DE CARDINALIDAD (numeros, solo modelos nuevos). Cada sorteo tiene
exactamente 5 numeros, asi que la suma de las probabilidades marginales de
aparicion debe ser 5. Una probabilidad cruda no finita (NaN o +-inf) se
rechaza ANTES de recortar (`salida_invalida`). Tras la calibracion, cada
probabilidad se recorta a
[EPSILON, 1 - EPSILON] (EPSILON = 1e-6, el mismo de `metricas.py`), se pasa
a logit y se busca por biseccion determinista (200 iteraciones sobre
[-60, 60]) el desplazamiento comun `s` de logits con
sum recorte(sigmoide(logit + s)) = 5, donde el recorte a
[EPSILON, 1 - EPSILON] forma parte de la funcion (continua y monotona). La sigmoide nunca supera 1. Se comprueba que el
resultado es finito, esta en (0, 1) y suma 5 con tolerancia 1e-9. La
calibracion previa no garantiza que la salida final este calibrada: el
informe evalua y diagnostica la salida final. El producto de cinco
marginales NO es la probabilidad del premio mayor.

NORMALIZACION DE POISSON (ColorLoto). Intensidades lambda >= 0 por par;
p(par) = (lambda + DELTA) / sum(lambda + DELTA), con DELTA = 1e-6 fijo
(protege de una intensidad nula; no se eligio mirando la evaluacion). La
combinacion se mide y se genera con la suposicion multinomial de Producto
2: las 6 balotas son independientes e identicamente distribuidas
condicionadas a esa distribucion estimada. Es una suposicion de diseno;
el modelo Poisson no la demuestra y no es la predictiva Dirichlet-
multinomial.

ESTADOS EXPLICITOS. Un ajuste que no converge (aviso de convergencia
registrado localmente, sin silenciar avisos de forma global), que no tiene
las clases necesarias, que produce valores no finitos o que no alcanza su
muestra minima lanza `CandidatoNoDisponible` con su estado; nunca se
sustituye por la uniforme conservando la etiqueta del modelo.

BOSQUES (Fase 3). Random Forest y Extra Trees con las mismas variables:
- numeros: clasificadores de aparicion con la misma calibracion sigmoide
  cronologica y el mismo ajuste de cardinalidad que los modelos binarios;
- ColorLoto: regresores con criterio de Poisson sobre el CONTEO de cada par
  numero-color por sorteo (0 a 6, con multiplicidad), cuya intensidad se
  normaliza igual que la de los modelos Poisson. Se conserva la
  representacion por pares y la suposicion multinomial de Producto 2.
SELECCION DE PARAMETROS (solo bosques). Cada ajuste elige `max_depth` y
`min_samples_leaf` de una rejilla fija con una validacion cronologica
INTERNA: los ultimos max(10, 25 %) objetivos del bloque base (numeros) o del
ajuste (ColorLoto) validan cada punto ajustado con los objetivos anteriores;
gana la menor Log Loss (empate: primer punto de la rejilla). Despues se
reajusta con el punto elegido sobre todo el bloque base (y se calibra con el
bloque de calibracion). Solo usa objetivos anteriores al corte de ajuste:
nunca el bloque que se evalua. Las recetas anteriores conservan sus
parametros fijos (asi se siguen reproduciendo los informes guardados).

Hilos: estas funciones NO cambian los hilos de las bibliotecas numericas del
proceso que las llama (el limite de threadpoolctl es de proceso: tomado en el
proceso web alteraria el entorno numerico compartido con Producto 3). El
laboratorio las ejecuta en un proceso trabajador dedicado
(`app/infrastructure/laboratorio_trabajador.py`), que fija `HILOS` solo para
si mismo.
"""
from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np

from app.application.ml import laboratorio_variables as lv
from app.application.ml import pronostico_colorloto as pcl
from app.application.ml import pronostico_miloto as pml
from app.application.ml.dataset import PERIODO_CALENTAMIENTO_MINIMO, construir_dataset_binario
from app.application.ml.modelo import (
    ajustar_registrando_convergencia,
    calibrador_cronologico,
    entrenar_modelo_calibrado,
    pipeline_laboratorio,
    predecir_probabilidades,
)
from app.application.ml.pronostico_experimental import ConfiguracionExperimental, filas_de_inferencia

EPSILON = 1e-6
DELTA_POISSON = 1e-6
TOLERANCIA_CARDINALIDAD = 1e-9
HILOS = 2
SEMILLA = 42
OBSERVADOR_DE_AJUSTE = None
"""Gancho opcional (pruebas): `f(id, posicion_de_corte, objetivos_base,
objetivos_de_calibracion, filas)` antes de cada ajuste de un modelo nuevo."""
OBSERVADOR_DE_SELECCION = None
"""Gancho opcional (pruebas): `f(id, posicion_de_corte, objetivos_de_seleccion,
objetivos_de_validacion)` antes de la seleccion interna de un bosque."""
OBJETIVOS_DE_VALIDACION = 10
"""Minimo de objetivos de la validacion interna de la seleccion (bosques)."""
PERFILES = ("predeterminado", "reducido")
"""`reducido` solo baja las iteraciones del boosting (pruebas de integracion);
forma parte de la identidad de la receta y del experimento."""


class CandidatoNoDisponible(Exception):
    """Estado explicito de un candidato que no puede producir una prediccion
    valida: `muestra_insuficiente`, `no_converge`, `clase_insuficiente`,
    `salida_invalida` o `fallo_de_ajuste`."""

    def __init__(self, estado: str, motivo: str):
        self.estado = estado
        self.motivo = motivo
        super().__init__(f"{estado}: {motivo}")


@dataclass(frozen=True)
class EntradaCatalogo:
    id: str
    version: str
    nombre: str
    tipo: str               # "referencia" o "modelo_nuevo"
    familia: str
    juegos: tuple[str, ...]
    salida: str             # "marginales_de_aparicion" o "distribucion_de_pares"
    variables: str
    parametros: MappingProxyType
    requisitos: MappingProxyType
    explicacion: str
    transformacion: str
    genera_pronostico: bool = True

    def como_dict(self, perfil: str = "predeterminado") -> dict:
        return {"id": self.id, "version": self.version, "nombre": self.nombre, "tipo": self.tipo,
                "familia": self.familia, "juegos": list(self.juegos), "salida": self.salida,
                "variables": self.variables, "parametros": parametros_de(self, perfil),
                "requisitos": dict(self.requisitos), "explicacion": self.explicacion,
                "transformacion": self.transformacion, "genera_pronostico": self.genera_pronostico}


NUMERICOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO")
_P_ARBOL = {"max_iter": 80, "max_depth": 3, "max_leaf_nodes": 7, "min_samples_leaf": 20, "learning_rate": 0.1,
            "l2_regularization": 1.0, "early_stopping": False, "random_state": SEMILLA}
_REQ_NUEVO_BINARIO = {"calentamiento": lv.CALENTAMIENTO, "objetivos_de_ajuste": 30, "objetivos_base": 20,
                      "objetivos_de_calibracion": 10}
_REQ_NUEVO_CONTEO = {"calentamiento": lv.CALENTAMIENTO, "objetivos_de_ajuste": 30}
_VARS_NUM = "candidato (categoria), " + ", ".join(lv.NOMBRES_VARIABLES_NUMEROS[1:]) + f" [{lv.VERSION_VARIABLES}]"
_VARS_COL = "par (categoria), " + ", ".join(lv.NOMBRES_VARIABLES_COLORLOTO[1:]) + f" [{lv.VERSION_VARIABLES}]"
_CARD = ("calibracion sigmoide cronologica y ajuste de cardinalidad: desplazamiento comun de logits por "
         "biseccion para que las marginales sumen 5 (epsilon 1e-6)")
_NORM = "intensidades Poisson normalizadas: p = (lambda + 1e-6) / suma; sin calibracion sigmoide"
SELECCION_DESCRIPCION = ("rejilla fija; validacion cronologica interna con los ultimos max(10, 25%) objetivos del bloque base "
              "(numeros) o del ajuste (ColorLoto); criterio Log Loss; empate: primer punto")
_P_BOSQUE = {"n_estimators": 100, "max_features": "sqrt", "random_state": SEMILLA, "n_jobs": 1,
             "rejilla": {"max_depth": [4, 8], "min_samples_leaf": [20, 80]}, "seleccion": SELECCION_DESCRIPCION}

CATALOGO = MappingProxyType({e.id: e for e in (
    EntradaCatalogo(
        "uniforme", "1", "Referencia uniforme", "referencia", "uniforme", NUMERICOS, "marginales_de_aparicion",
        "ninguna", MappingProxyType({"probabilidad": "cantidad / tamano del rango"}), MappingProxyType({}),
        "Todas los numeros con la misma probabilidad (5/43 o 5/39). Es la referencia de cada comparacion.",
        "ninguna", genera_pronostico=False),
    EntradaCatalogo(
        "actual_logistica_ae36", "producto1-1", "Estrategia actual: logistica calibrada de AE-36", "referencia",
        "estrategia_actual", ("BALOTO", "BALOTO_REVANCHA"), "marginales_de_aparicion",
        "frecuencias 10/20/50, acumulada, atraso, sorteo anterior e identidad del candidato (AE-36)",
        MappingProxyType({"C": 1.0, "solver": "lbfgs", "max_iter": 2000, "semilla": SEMILLA,
                          "proporcion_calibracion": 0.2, "calibracion": "sigmoide con PredefinedSplit"}),
        MappingProxyType({"calentamiento": PERIODO_CALENTAMIENTO_MINIMO,
                          "objetivos_de_ajuste": ConfiguracionExperimental().minimo_objetivos_de_entrenamiento}),
        "La linea de Producto 1 sin cambios: aprende la aparicion de cada numero con sus propias variables.",
        "ninguna (probabilidades originales de la receta)"),
    EntradaCatalogo(
        "actual_frecuencia_contraida", pml.VERSION_DE_LA_LINEA, "Estrategia actual: frecuencia contraida",
        "referencia", "estrategia_actual", ("MILOTO",), "marginales_de_aparicion", "conteos previos",
        MappingProxyType({"fuerza_previa": pml.ConfiguracionMiLoto().fuerza_previa}),
        MappingProxyType({"sorteos_previos": pml.ConfiguracionMiLoto().minimo_sorteos_de_entrenamiento}),
        "La linea de Producto 2 sin cambios: frecuencia de aparicion contraida hacia 5/39. Es una formula, no un "
        "modelo nuevo de aprendizaje automatico.", "ninguna (probabilidades originales de la receta)"),
    EntradaCatalogo(
        "logistica_regularizada", "1", "Regresion logistica regularizada", "modelo_nuevo", "lineal", NUMERICOS,
        "marginales_de_aparicion", _VARS_NUM,
        MappingProxyType({"C": 1.0, "solver": "lbfgs", "max_iter": 1000, "semilla": SEMILLA,
                          "escalado": "StandardScaler ajustado solo con el bloque base",
                          "candidato": "OneHotEncoder (ignora categorias no vistas)"}),
        MappingProxyType(_REQ_NUEVO_BINARIO),
        "Aprende la probabilidad de que cada numero aparezca a partir de sus frecuencias recientes, su atraso y su "
        "identidad, con penalizacion L2.", _CARD),
    EntradaCatalogo(
        "hgb_clasificador", "1", "Gradient boosting de arboles (clasificacion)", "modelo_nuevo", "arboles",
        NUMERICOS, "marginales_de_aparicion", _VARS_NUM,
        MappingProxyType({**_P_ARBOL, "candidato": "categoria nativa (OrdinalEncoder; no vista = ausente)"}),
        MappingProxyType(_REQ_NUEVO_BINARIO),
        "Arboles pequenos y regularizados que combinan las mismas variables de forma no lineal. No aprende la "
        "superbalota.", _CARD),
    EntradaCatalogo(
        "uniforme_paleta", "1", "Referencia uniforme sobre la paleta", "referencia", "uniforme", ("COLORLOTO",),
        "distribucion_de_pares", "ninguna", MappingProxyType({"probabilidad": "1 / (7 x colores de la paleta)"}),
        MappingProxyType({}), "Todos los pares numero-color de la paleta del corte con la misma probabilidad.",
        "ninguna", genera_pronostico=False),
    EntradaCatalogo(
        "actual_multinomial_suavizada", pcl.VERSION_DE_LA_LINEA, "Estrategia actual: multinomial suavizada",
        "referencia", "estrategia_actual", ("COLORLOTO",), "distribucion_de_pares", "conteos previos de pares",
        MappingProxyType({"alfa": pcl.ConfiguracionColorLoto().alfa}),
        MappingProxyType({"sorteos_previos": pcl.ConfiguracionColorLoto().minimo_sorteos_de_entrenamiento}),
        "La linea de Producto 2 sin cambios (pares_multinomial_con_suavizado_aditivo): media a posteriori de una "
        "Dirichlet como estimacion puntual de una multinomial. Es una formula, no un modelo nuevo.",
        "ninguna (probabilidades originales de la receta)"),
    EntradaCatalogo(
        "poisson_regularizado", "1", "Regresion de Poisson regularizada", "modelo_nuevo", "lineal", ("COLORLOTO",),
        "distribucion_de_pares", _VARS_COL,
        MappingProxyType({"alpha": 1.0, "max_iter": 1000, "escalado": "StandardScaler ajustado solo con el ajuste",
                          "par": "OneHotEncoder (ignora categorias no vistas)"}),
        MappingProxyType(_REQ_NUEVO_CONTEO),
        "Aprende cuantas veces aparece cada par numero-color por sorteo (0 a 6) a partir de sus conteos recientes.",
        _NORM),
    EntradaCatalogo(
        "hgb_poisson", "1", "Gradient boosting de arboles (conteos Poisson)", "modelo_nuevo", "arboles",
        ("COLORLOTO",), "distribucion_de_pares", _VARS_COL,
        MappingProxyType({**_P_ARBOL, "loss": "poisson", "par": "categoria nativa (no vista = ausente)"}),
        MappingProxyType(_REQ_NUEVO_CONTEO),
        "Arboles pequenos con perdida de Poisson que aprenden la intensidad de conteo de cada par.", _NORM),
    # Fase 3: bosques (al final, para no cambiar el orden de las entradas anteriores)
    EntradaCatalogo(
        "random_forest_clasificador", "1", "Random Forest (clasificacion)", "modelo_nuevo", "bosques", NUMERICOS,
        "marginales_de_aparicion", _VARS_NUM,
        MappingProxyType({**_P_BOSQUE, "bootstrap": True, "criterion": "gini",
                          "candidato": "codigo ordinal (no visto = ausente)"}),
        MappingProxyType(_REQ_NUEVO_BINARIO),
        "Promedia muchos arboles entrenados con remuestreos de los objetivos de ajuste y subconjuntos de variables. "
        "Profundidad y hoja minima se eligen con una validacion cronologica interna. No aprende la superbalota.",
        _CARD),
    EntradaCatalogo(
        "extra_trees_clasificador", "1", "Extra Trees (clasificacion)", "modelo_nuevo", "bosques", NUMERICOS,
        "marginales_de_aparicion", _VARS_NUM,
        MappingProxyType({**_P_BOSQUE, "bootstrap": False, "criterion": "gini",
                          "candidato": "codigo ordinal (no visto = ausente)"}),
        MappingProxyType(_REQ_NUEVO_BINARIO),
        "Como Random Forest, pero con cortes elegidos al azar en cada variable (mas variedad, menos varianza). "
        "Profundidad y hoja minima se eligen con una validacion cronologica interna. No aprende la superbalota.",
        _CARD),
    EntradaCatalogo(
        "random_forest_poisson", "1", "Random Forest (conteos Poisson)", "modelo_nuevo", "bosques", ("COLORLOTO",),
        "distribucion_de_pares", _VARS_COL,
        MappingProxyType({**_P_BOSQUE, "bootstrap": True, "criterion": "poisson",
                          "par": "codigo ordinal del par (no visto = ausente)"}),
        MappingProxyType(_REQ_NUEVO_CONTEO),
        "Regresion con criterio de Poisson sobre cuantas veces aparece cada par numero-color en un sorteo (0 a 6, con "
        "repeticion): el objetivo es un conteo no negativo. La intensidad se normaliza a una distribucion de pares.",
        _NORM),
    EntradaCatalogo(
        "extra_trees_poisson", "1", "Extra Trees (conteos Poisson)", "modelo_nuevo", "bosques", ("COLORLOTO",),
        "distribucion_de_pares", _VARS_COL,
        MappingProxyType({**_P_BOSQUE, "bootstrap": False, "criterion": "poisson",
                          "par": "codigo ordinal del par (no visto = ausente)"}),
        MappingProxyType(_REQ_NUEVO_CONTEO),
        "Extra Trees con criterio de Poisson sobre el conteo de cada par numero-color por sorteo; la intensidad se "
        "normaliza a una distribucion de pares.", _NORM),
)})

FAMILIAS_FUTURAS = MappingProxyType({
    "xgboost": "Gradient boosting de XGBoost: extension futura (dependencia nueva; HistGradientBoosting cubre el "
               "boosting de arboles).",
    "lightgbm": "LightGBM: extension futura (dependencia nueva).",
    "redes_neuronales": "Redes neuronales: extension futura; con unos cientos de sorteos por juego el riesgo de "
                        "sobreajuste es alto.",
    "bayesianos": "Modelos bayesianos jerarquicos: extension futura (la multinomial suavizada de ColorLoto es una "
                  "estimacion puntual Dirichlet, no un modelo bayesiano completo).",
    "markov": "Cadenas de Markov sobre transiciones entre sorteos: extension futura.",
})
"""Familias del ROADMAP que NO estan implementadas. Se listan para no
declararlas hechas; no forman parte del catalogo ni de ninguna comparacion."""


def candidatos_del_juego(codigo: str) -> list[EntradaCatalogo]:
    return [e for e in CATALOGO.values() if codigo in e.juegos]


def parametros_de(entrada: EntradaCatalogo, perfil: str) -> dict:
    parametros = dict(entrada.parametros)
    if perfil == "reducido" and entrada.familia == "arboles":
        parametros["max_iter"] = 10
    if perfil == "reducido" and entrada.familia == "bosques":
        parametros["n_estimators"] = 10
        parametros["rejilla"] = {"max_depth": [4, 8], "min_samples_leaf": [20]}
    return parametros


def registrable(entrada: EntradaCatalogo) -> bool:
    """Se puede guardar como modelo entrenado (Fase 3): tiene parametros
    aprendidos por un estimador. Las uniformes y las formulas de conteo
    (frecuencia contraida, multinomial suavizada) se recalculan en cada
    pronostico y no tienen estimador que congelar."""
    return entrada.tipo == "modelo_nuevo" or entrada.id == "actual_logistica_ae36"


def puntos_de_rejilla(rejilla: dict) -> list[dict]:
    """Puntos de la rejilla en orden estable (claves ordenadas, valores en su orden)."""
    claves = sorted(rejilla)
    return [dict(zip(claves, valores)) for valores in itertools.product(*(rejilla[k] for k in claves))]


def parametros_concretos(parametros: dict, punto: dict | None = None) -> dict:
    """Parametros que recibe el estimador: sin la rejilla ni los textos, con el punto elegido."""
    concretos = {k: v for k, v in parametros.items() if k not in ("rejilla", "seleccion", "candidato", "par")}
    return {**concretos, **(punto or {})}


# ---------------------------------------------------------------------------
# Transformaciones de probabilidad
# ---------------------------------------------------------------------------

def _sigmoide(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def ajustar_cardinalidad(probabilidades: Sequence[float], cantidad: int) -> np.ndarray:
    """Desplazamiento comun de logits por biseccion determinista para que las
    marginales sumen `cantidad`. Ver el docstring del modulo."""
    crudas = np.asarray(probabilidades, dtype=float)
    if not np.all(np.isfinite(crudas)) or not 0 < cantidad < len(crudas):  # antes del recorte: +-inf no pasan
        raise CandidatoNoDisponible("salida_invalida", "probabilidades no finitas o cardinalidad imposible")
    p = np.clip(crudas, EPSILON, 1 - EPSILON)
    z = np.log(p) - np.log1p(-p)

    def masa(desplazamiento: float) -> np.ndarray:
        return np.clip(_sigmoide(z + desplazamiento), EPSILON, 1 - EPSILON)
    bajo, alto = -60.0, 60.0
    for _ in range(200):
        medio = (bajo + alto) / 2
        if masa(medio).sum() < cantidad:
            bajo = medio
        else:
            alto = medio
    final = masa((bajo + alto) / 2)
    if not np.all(np.isfinite(final)) or abs(final.sum() - cantidad) > TOLERANCIA_CARDINALIDAD:
        raise CandidatoNoDisponible("salida_invalida", f"el ajuste de cardinalidad no alcanzo {cantidad}")
    return final


def normalizar_intensidades(intensidades: Sequence[float]) -> np.ndarray:
    lam = np.asarray(intensidades, dtype=float)
    if not np.all(np.isfinite(lam)) or np.any(lam < 0):
        raise CandidatoNoDisponible("salida_invalida", "intensidades no finitas o negativas")
    lam = lam + DELTA_POISSON
    return lam / lam.sum()


# ---------------------------------------------------------------------------
# Ajuste y prediccion
# ---------------------------------------------------------------------------

@dataclass
class Prediccion:
    """Probabilidades de un candidato para las filas de un conjunto de
    objetivos: marginales (numeros) o distribucion de pares por objetivo."""

    probabilidades: np.ndarray
    estado_del_ajuste: dict = field(default_factory=dict)


def _ajustar(estimador, X, y):
    """Un aviso de convergencia (registrado en `modelo.py`, no silenciado
    globalmente) convierte el ajuste en `no_converge`."""
    try:
        convergencia = ajustar_registrando_convergencia(estimador, X, y)
    except ValueError as error:
        raise CandidatoNoDisponible("fallo_de_ajuste", str(error)[:300]) from error
    if convergencia:
        raise CandidatoNoDisponible("no_converge", convergencia[0])
    return estimador


def division_de_calibracion(objetivos: Sequence[int]) -> tuple[list[int], list[int]]:
    """(base, calibracion) por sorteo completo y en orden cronologico: la
    calibracion son los ultimos max(10, round(0.2 N)) objetivos."""
    ordenados = sorted(set(objetivos))
    n_cal = max(_REQ_NUEVO_BINARIO["objetivos_de_calibracion"], round(0.2 * len(ordenados)))
    return ordenados[:len(ordenados) - n_cal], ordenados[len(ordenados) - n_cal:]


class Ajustado:
    """Candidato ya ajustado con datos anteriores a un corte de ajuste."""

    def __init__(self, entrada: EntradaCatalogo, predecir, detalle: dict, estimador=None,
                 parametros: dict | None = None):
        self.entrada = entrada
        self._predecir = predecir
        self.detalle = detalle
        self.estimador = estimador
        """Estimador ajustado (modelos nuevos: scikit-learn; AE-36: `ModeloEntrenado`).
        Es lo que el registro de modelos (Fase 3) congela."""
        self.parametros = parametros
        """Parametros concretos con los que se ajusto el estimador (con el punto
        elegido por la seleccion interna, si la hubo)."""

    def predecir(self, filas: lv.Filas) -> np.ndarray:
        """Probabilidad final de cada fila (marginal o de par normalizada por
        objetivo). Valida finitud y rango."""
        p = np.asarray(self._predecir(filas), dtype=float)
        if p.shape != (len(filas),) or not np.all(np.isfinite(p)) or np.any(p <= 0) or np.any(p >= 1):
            raise CandidatoNoDisponible("salida_invalida", "probabilidades no finitas o fuera de (0, 1)")
        return p


def _por_objetivo(filas: lv.Filas, funcion):
    """Aplica `funcion(valores de un objetivo) -> valores` objetivo a objetivo."""
    def aplicar(valores):
        salida = np.empty(len(filas))
        for objetivo in np.unique(filas.posiciones):
            m = filas.posiciones == objetivo
            salida[m] = funcion(valores[m])
        return salida
    return aplicar


def ajustar_candidato(entrada: EntradaCatalogo, instantanea: lv.Instantanea, variables: lv.Variables,
                      posicion_de_corte: int, perfil: str = "predeterminado") -> Ajustado:
    """Ajusta el candidato SOLO con objetivos de posicion < `posicion_de_corte`
    (y, para las referencias, con los sorteos de esas posiciones)."""
    reglas = instantanea.reglas
    previos = instantanea.sorteos[:posicion_de_corte]
    if entrada.familia == "uniforme":
        masa = 1 if reglas.colores else reglas.cantidad  # 1 balota por par, o 5 numeros por sorteo
        return Ajustado(entrada, lambda f: _por_objetivo(f, lambda v: np.full(len(v), masa / len(v)))(
            np.zeros(len(f))), {})
    if entrada.id == "actual_frecuencia_contraida":
        minimo = entrada.requisitos["sorteos_previos"]
        if len(previos) < minimo:
            raise CandidatoNoDisponible("muestra_insuficiente", f"la receta necesita {minimo} sorteos previos; hay "
                                        f"{len(previos)}")
        p = pml.probabilidades_de_inclusion(previos, pml.ConfiguracionMiLoto())
        return Ajustado(entrada, lambda f: np.array([p[c] for c in f.candidatos]),
                        {"estado": "conteos fijados al inicio del bloque", "sorteos_previos": len(previos)})
    if entrada.id == "actual_multinomial_suavizada":
        minimo = entrada.requisitos["sorteos_previos"]
        if len(previos) < minimo:
            raise CandidatoNoDisponible("muestra_insuficiente", f"la receta necesita {minimo} sorteos previos; hay "
                                        f"{len(previos)}")
        d = pcl.distribucion_de_pares(previos, pcl.ConfiguracionColorLoto())

        def predecir_multinomial(f):
            if any(tuple(c) not in d for c in f.candidatos):
                raise CandidatoNoDisponible("salida_invalida", "par fuera de la paleta del ajuste")
            return _por_objetivo(f, lambda v: v / v.sum())(np.array([d[tuple(c)] for c in f.candidatos]))
        return Ajustado(entrada, predecir_multinomial,
                        {"estado": "conteos fijados al inicio del bloque", "sorteos_previos": len(previos)})
    if entrada.id == "actual_logistica_ae36":
        return _ajustar_ae36(entrada, instantanea, variables, posicion_de_corte)
    return _ajustar_nuevo(entrada, instantanea, variables, posicion_de_corte, perfil)


def _ajustar_ae36(entrada, instantanea, variables, posicion_de_corte) -> Ajustado:
    reglas = instantanea.reglas
    minimo = entrada.requisitos["objetivos_de_ajuste"]
    disponibles = posicion_de_corte - PERIODO_CALENTAMIENTO_MINIMO
    if disponibles < minimo:
        raise CandidatoNoDisponible("muestra_insuficiente", f"la receta de AE-36 necesita {PERIODO_CALENTAMIENTO_MINIMO} "
                                    f"sorteos de calentamiento y {minimo} objetivos de ajuste; hay {max(disponibles, 0)}")
    datos = variables.memo("dataset_ae36", lambda: construir_dataset_binario(
        list(instantanea.sorteos), reglas.rango[0], reglas.rango[1], reglas.cantidad, reglas.codigo))
    corte_numero = instantanea.sorteos[posicion_de_corte].numero_sorteo if posicion_de_corte < len(instantanea) \
        else instantanea.corte + 1
    entrenamiento = [f for f in datos.filas if f.sorteo_objetivo < corte_numero]
    configuracion = ConfiguracionExperimental()
    try:
        modelo = entrenar_modelo_calibrado(entrenamiento, semilla=configuracion.semilla,
                                           proporcion_calibracion=configuracion.proporcion_calibracion)
    except ValueError as error:
        raise CandidatoNoDisponible("fallo_de_ajuste", str(error)[:300]) from error
    por_clave = variables.memo("claves_ae36", lambda: {(f.sorteo_objetivo, f.numero_candidato): f for f in datos.filas})
    inferencia = variables.memo("inferencia_ae36", lambda: {
        (fi.sorteo_objetivo, fi.numero_candidato): fi
        for fi in filas_de_inferencia(list(instantanea.sorteos), reglas.codigo, *reglas.rango)})

    def predecir(f: lv.Filas):
        filas = [por_clave.get((int(o), int(c))) or inferencia[(int(o), int(c))]
                 for o, c in zip(f.objetivos, f.candidatos)]
        return np.array(predecir_probabilidades(modelo, filas))
    objetivos = sorted({f.sorteo_objetivo for f in entrenamiento})
    return Ajustado(entrada, predecir, {"objetivos_de_ajuste": [objetivos[0], objetivos[-1], len(objetivos)],
                                        "frontera_base_calibracion": modelo.frontera_base_calibracion},
                    modelo, dict(entrada.parametros))


def inferir(estimador, salida: str, filas: lv.Filas, cantidad: int) -> np.ndarray:
    """Probabilidad final de cada fila con un estimador YA ajustado (sin
    reajustar nada): numeros -> probabilidad de la clase 1 y ajuste de
    cardinalidad por objetivo; pares -> intensidad normalizada por objetivo.
    La usan la evaluacion, los pronosticos y los modelos registrados
    recargados (Fase 3), asi que las tres aplican la misma transformacion."""
    if salida == "distribucion_de_pares":
        return _por_objetivo(filas, normalizar_intensidades)(estimador.predict(filas.X))
    indice = list(estimador.classes_).index(1)
    crudas = estimador.predict_proba(filas.X)[:, indice]
    return _por_objetivo(filas, lambda v: ajustar_cardinalidad(v, cantidad))(crudas)


def division_de_seleccion(objetivos: Sequence[int]) -> tuple[list[int], list[int]]:
    """(ajuste, validacion) internos de la seleccion, por sorteo completo y en
    orden cronologico: la validacion son los ultimos max(10, round(0.25 N))."""
    ordenados = sorted(set(objetivos))
    n_val = max(OBJETIVOS_DE_VALIDACION, round(0.25 * len(ordenados)))
    return ordenados[:len(ordenados) - n_val], ordenados[len(ordenados) - n_val:]


def _perdida_de_validacion(salida: str, filas: lv.Filas, p: np.ndarray) -> float:
    """Log Loss binaria media por fila (numeros) o Log Loss por balota (pares)."""
    p = np.clip(p, EPSILON, 1 - EPSILON)
    if salida == "distribucion_de_pares":
        return float(-(filas.y * np.log(p)).sum() / filas.y.sum())
    return float(-np.mean(filas.y * np.log(p) + (1 - filas.y) * np.log1p(-p)))


def _seleccionar(entrada: EntradaCatalogo, parametros: dict, filas: lv.Filas, objetivos: list[int],
                 posicion_de_corte: int, cantidad: int) -> tuple[dict, dict]:
    """Elige el punto de la rejilla con objetivos ANTERIORES al corte de ajuste
    (`objetivos`: base de los binarios o ajuste de los conteos)."""
    ajuste, validacion = division_de_seleccion(objetivos)
    if len(ajuste) < OBJETIVOS_DE_VALIDACION:
        raise CandidatoNoDisponible("muestra_insuficiente", f"la seleccion interna necesita {OBJETIVOS_DE_VALIDACION} "
                                    f"objetivos de ajuste antes de su validacion; hay {len(ajuste)}")
    if OBSERVADOR_DE_SELECCION is not None:
        OBSERVADOR_DE_SELECCION(entrada.id, posicion_de_corte, ajuste, validacion)
    filas_ajuste = filas.seleccionar(np.isin(filas.objetivos, ajuste))
    filas_validacion = filas.seleccionar(np.isin(filas.objetivos, validacion))
    puntos = []
    for punto in puntos_de_rejilla(parametros["rejilla"]):
        modelo = pipeline_laboratorio(entrada.familia, entrada.id, parametros_concretos(parametros, punto))
        y = filas_ajuste.y if entrada.salida == "distribucion_de_pares" else filas_ajuste.y.astype(int)
        try:
            if entrada.salida != "distribucion_de_pares" and len(set(y.tolist())) < 2:
                raise CandidatoNoDisponible("clase_insuficiente", "el ajuste interno no tiene las dos clases")
            _ajustar(modelo, filas_ajuste.X, y)
            perdida = _perdida_de_validacion(entrada.salida, filas_validacion,
                                             inferir(modelo, entrada.salida, filas_validacion, cantidad))
        except CandidatoNoDisponible as error:
            puntos.append({"parametros": punto, "estado": error.estado, "log_loss": None})
            continue
        puntos.append({"parametros": punto, "estado": "evaluado", "log_loss": round(perdida, 12)})
    evaluados = [p for p in puntos if p["estado"] == "evaluado"]
    if not evaluados:
        raise CandidatoNoDisponible("fallo_de_ajuste", "ningun punto de la rejilla se pudo ajustar en la seleccion")
    elegido = min(evaluados, key=lambda p: p["log_loss"])  # min devuelve el primero ante empate
    return elegido["parametros"], {
        "objetivos_de_seleccion": [ajuste[0], ajuste[-1], len(ajuste)],
        "objetivos_de_validacion": [validacion[0], validacion[-1], len(validacion)],
        "criterio": "Log Loss por balota" if entrada.salida == "distribucion_de_pares" else "Log Loss por fila",
        "puntos": puntos, "elegidos": elegido["parametros"]}


def _ajustar_nuevo(entrada, instantanea, variables, posicion_de_corte, perfil) -> Ajustado:
    reglas = instantanea.reglas
    requisitos = entrada.requisitos
    posiciones = list(range(lv.CALENTAMIENTO, posicion_de_corte))
    if len(posiciones) < requisitos["objetivos_de_ajuste"]:
        raise CandidatoNoDisponible(
            "muestra_insuficiente", f"hacen falta {requisitos['calentamiento']} sorteos de calentamiento y "
            f"{requisitos['objetivos_de_ajuste']} objetivos de ajuste; hay {max(len(posiciones), 0)} objetivos")
    filas = variables.de_ajuste(posicion_de_corte)
    numeros = [instantanea.sorteos[i].numero_sorteo for i in posiciones]
    detalle = {"objetivos_de_ajuste": [numeros[0], numeros[-1], len(numeros)]}
    parametros = parametros_de(entrada, perfil)
    concretos = parametros_concretos(parametros) if "rejilla" in parametros else parametros
    if entrada.salida == "distribucion_de_pares":
        if "rejilla" in parametros:
            punto, detalle["seleccion"] = _seleccionar(entrada, parametros, filas, numeros, posicion_de_corte,
                                                       reglas.cantidad)
            concretos = parametros_concretos(parametros, punto)
        modelo = pipeline_laboratorio(entrada.familia, entrada.id, concretos)
        if OBSERVADOR_DE_AJUSTE is not None:
            OBSERVADOR_DE_AJUSTE(entrada.id, posicion_de_corte, sorted(set(filas.objetivos.tolist())), [], filas)
        modelo = _ajustar(modelo, filas.X, filas.y)
        return Ajustado(entrada, lambda f: inferir(modelo, entrada.salida, f, reglas.cantidad), detalle, modelo,
                        concretos)
    y = filas.y.astype(int)
    if len(set(y.tolist())) < 2:
        raise CandidatoNoDisponible("clase_insuficiente", "el ajuste no tiene apariciones y ausencias")
    base, calibracion = division_de_calibracion(numeros)
    if len(base) < requisitos["objetivos_base"] or len(calibracion) < requisitos["objetivos_de_calibracion"]:
        raise CandidatoNoDisponible("muestra_insuficiente", "base o calibracion por debajo de su minimo")
    en_calibracion = np.isin(filas.objetivos, calibracion)
    if len(set(y[en_calibracion].tolist())) < 2 or len(set(y[~en_calibracion].tolist())) < 2:
        raise CandidatoNoDisponible("clase_insuficiente", "base o calibracion sin las dos clases")
    if "rejilla" in parametros:  # la calibracion queda fuera de la seleccion
        punto, detalle["seleccion"] = _seleccionar(entrada, parametros, filas, base, posicion_de_corte,
                                                   reglas.cantidad)
        concretos = parametros_concretos(parametros, punto)
    modelo = pipeline_laboratorio(entrada.familia, entrada.id, concretos)
    if OBSERVADOR_DE_AJUSTE is not None:
        OBSERVADOR_DE_AJUSTE(entrada.id, posicion_de_corte, base, calibracion, filas)
    calibrado = calibrador_cronologico(modelo, en_calibracion.tolist())
    calibrado = _ajustar(calibrado, filas.X, y)
    detalle.update({"objetivos_base": [base[0], base[-1], len(base)],
                    "objetivos_de_calibracion": [calibracion[0], calibracion[-1], len(calibracion)]})
    return Ajustado(entrada, lambda f: inferir(calibrado, entrada.salida, f, reglas.cantidad), detalle, calibrado,
                    concretos)


def probabilidades_superbalota(previos: Sequence, rango: tuple[int, int]) -> dict:
    """Estrategia separada de Producto 1 (`frecuencia_con_suavizado_de_laplace`)."""
    clases = range(rango[0], rango[1] + 1)
    conteo = {c: 0 for c in clases}
    vistos = 0
    for r in previos:
        if r.superbalota is not None:
            conteo[r.superbalota] += 1
            vistos += 1
    return {c: (conteo[c] + 1) / (vistos + len(conteo)) for c in clases}
