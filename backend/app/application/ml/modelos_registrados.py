"""
Fase 3 -registro de modelos entrenados del laboratorio, por juego.

INFORME frente a MODELO REGISTRADO. Un informe del laboratorio
(`laboratorio-experimento/1`, Producto 4) guarda la receta, la instantanea del
historico y las metricas de una comparacion: se reproduce REENTRENANDO. Un
modelo registrado (`laboratorio-modelo/1`) guarda ademas el ESTIMADOR AJUSTADO
con todos sus componentes de inferencia y se RECARGA para predecir sin volver
a entrenar. Cada modelo registrado procede de un informe: su instantanea es
el periodo de entrenamiento y la evaluacion de ese candidato en el informe es
la evaluacion asociada (mide la receta con reajustes por bloque antes del
corte; el estimador congelado se ajusta despues con todo el historico hasta
el corte y su rendimiento propio se observa en el seguimiento de sus
pronosticos).

QUE SE GUARDA. Dos archivos por version:
- el ESTIMADOR serializado (pickle, protocolo 5): preparacion de variables
  (codificacion de la identidad y escalado ajustados), estimador y, en los
  binarios, la calibracion sigmoide cronologica. Su nombre es su SHA-256;
- el MANIFIESTO (JSON canonico AE-52, sellado): identidad, version, juego,
  objetivo estadistico, variables y su contrato, parametros (con el punto
  elegido por la seleccion interna), semilla, entorno, periodo de
  entrenamiento, corte, huella del historico, procedencia y evaluacion
  asociada, SHA-256 y tamano del estimador, transformaciones deterministas de
  probabilidad (ajuste de cardinalidad o normalizacion de Poisson, que son
  codigo versionado, no estado ajustado) y un pronostico de CONTROL del
  objetivo corte + 1 calculado antes de guardar.

IDENTIDAD (`clave`): SHA-256 canonico de receta, datos (juego, reglas, corte,
huella e intervalo del historico, paleta), entrenamiento (perfil, objetivos,
calibracion, seleccion, semilla, hilos), variables, transformaciones y
entorno. La procedencia (que informe la pidio) y la hora no forman parte de
ella: repetir la misma entrada desde otro informe reutiliza la version. Un
cambio en cualquiera de los componentes da otra clave y otra version
(numero consecutivo por juego y modelo). Nada se sobrescribe ni se borra.

CARGA VERIFICADA (antes de deserializar): ruta construida solo con juego y
clave validados; manifiesto canonico, sellado y en su sitio; entorno
compatible (misma version de scikit-learn, mismas versiones menores de
Python, NumPy y SciPy; mismas variables, transformaciones y registro); SHA-256
y tamano del estimador; y deserializacion RESTRINGIDA a una lista cerrada de
clases de scikit-learn, NumPy y la biblioteca estandar. Solo se cargan
modelos producidos por esta aplicacion; no se importan modelos externos.
Limite: la huella detecta alteraciones accidentales o inconsistentes, no
autentica frente a quien pueda reescribir el almacen entero.

CONTRATO DE INFERENCIA (modelo congelado): con un corte de entrada C mayor o
igual que el corte de entrenamiento, las variables del objetivo C + 1 se
calculan solo con los sorteos <= C (las mismas variables causales); los
parametros del estimador, de la calibracion y de la seleccion no cambian.
Un corte anterior al de entrenamiento se rechaza: el modelo ya vio esos
resultados.

Modulo puro salvo el ajuste y la prediccion de scikit-learn.
"""
from __future__ import annotations

import hashlib
import io
import json
import pickle
from collections.abc import Sequence

import numpy as np

from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml.pronostico_experimental import ESTADO_DE_USO

ESQUEMA_MODELO = "laboratorio-modelo/1"
VERSION_REGISTRO = "fase3-1"
FORMATO_DEL_ESTIMADOR = "pickle-protocolo-5-restringido"
FORMATO_ML = "json-nativo-ml-cinco-familias/1"
VERSION_REGISTRO_ML = "ml-cinco-familias-1"
ESQUEMA_ESTIMADOR_ML = "ml-cinco-familias/1"


def es_ml_ampliado(entrada) -> bool:
    return entrada.familia in lm.FAMILIAS_ML_AMPLIADAS


def formato_de(entrada) -> str:
    return FORMATO_ML if es_ml_ampliado(entrada) else FORMATO_DEL_ESTIMADOR


def extension_estimador(artefacto: dict) -> str:
    formato = artefacto["estimador"]["formato"]
    if formato == FORMATO_DEL_ESTIMADOR:
        return ".pkl"
    if formato == FORMATO_ML:
        return ".mljson"
    raise ModeloRegistradoError("incompatible", "formato de estimador desconocido")
VOLATILES_MODELO = ("huella_de_reproduccion", "publicacion", "sello")
CONTRATO_DE_INFERENCIA = (
    "Corte de entrada C >= corte de entrenamiento. Las variables del objetivo C + 1 se calculan solo con los "
    "sorteos <= C (variables causales " + lv.VERSION_VARIABLES + "); estimador, calibracion y parametros elegidos "
    "quedan congelados (no se reajustan). Un corte anterior al de entrenamiento se rechaza porque el modelo ya vio "
    "esos resultados.")
NOTA_EVALUACION = ("La evaluacion asociada es la del informe de procedencia: mide la receta con reajustes por bloque "
                   "antes del corte. El estimador congelado se ajusto despues con todo el historico hasta el corte; "
                   "su rendimiento propio se observa en el seguimiento de sus pronosticos. No acredita ventaja futura.")


class ModeloRegistradoError(ValueError):
    """Error esperado del registro con un estado estable: `no_registrable`,
    `alterado`, `incompatible`, `estimador_no_admitido`, `corte_no_valido`,
    `paleta_no_compatible` o `no_reproduce`."""

    def __init__(self, estado: str, motivo: str):
        self.estado = estado
        self.motivo = motivo
        super().__init__(f"{estado}: {motivo}")


# ---------------------------------------------------------------------------
# Identidad, cuerpo e integridad
# ---------------------------------------------------------------------------

def huella(objeto: dict) -> str:
    return la.huella(objeto)


def _transformacion(entrada: lm.EntradaCatalogo) -> dict:
    if entrada.id == "actual_logistica_ae36":
        return {"tipo": "ninguna", "detalle": "probabilidades originales de la receta de AE-36"}
    if entrada.salida == "distribucion_de_pares" and entrada.familia in ("bayesianos", "markov"):
        return {"tipo": "normalizacion_de_predictiva", "delta": lm.DELTA_POISSON,
                "detalle": "intensidades predictivas normalizadas por objetivo; no es predictiva conjunta integrada"}
    if entrada.salida == "distribucion_de_pares":
        return {"tipo": "normalizacion_de_poisson", "delta": lm.DELTA_POISSON,
                "detalle": "p = (lambda + delta) / suma por objetivo"}
    return {"tipo": "ajuste_de_cardinalidad", "epsilon": lm.EPSILON, "tolerancia": lm.TOLERANCIA_CARDINALIDAD,
            "detalle": "desplazamiento comun de logits por biseccion para que las marginales sumen la cantidad"}


def _variables(entrada: lm.EntradaCatalogo, colores: bool) -> dict:
    if entrada.id == "actual_logistica_ae36":
        return {"version": "ae36", "nombres": ["frecuencia_acumulada", "frecuencia_ventana_10",
                                                "frecuencia_ventana_20", "frecuencia_ventana_50",
                                                "sorteos_desde_ultima_aparicion", "aparecio_en_sorteo_anterior",
                                                "numero_candidato"],
                "descripcion": entrada.variables}
    nombres = lv.NOMBRES_VARIABLES_COLORLOTO if colores else lv.NOMBRES_VARIABLES_NUMEROS
    return {"version": lv.VERSION_VARIABLES, "nombres": list(nombres), "descripcion": entrada.variables}


def _entrenamiento(entrada: lm.EntradaCatalogo) -> dict:
    if entrada.id == "actual_logistica_ae36":
        return {"objetivos": "todos los objetivos de la instantanea tras el calentamiento de AE-36",
                "calibracion": "sigmoide con PredefinedSplit (ultimo 20 % de los objetivos)", "seleccion": "ninguna"}
    if entrada.familia in ("bayesianos", "markov"):
        return {"objetivos": f"todos los objetivos anteriores al corte desde la posicion {lv.CALENTAMIENTO}",
                "seleccion": "ninguna; hiperparametros fijados previamente", "calibracion": "ninguna",
                "paleta": "soporte observado antes del corte de ajuste; congelado despues"}
    salida = {"objetivos": f"todos los objetivos de la instantanea desde la posicion {lv.CALENTAMIENTO}",
              "seleccion": lm.SELECCION_DESCRIPCION if "rejilla" in entrada.parametros else "ninguna"}
    salida["calibracion"] = ("ninguna (conteos Poisson normalizados)" if entrada.salida == "distribucion_de_pares" else
                             "sigmoide cronologica: ultimos max(10, 20 %) objetivos del ajuste")
    return salida


def identidad_del_modelo(informe: dict, entrada: lm.EntradaCatalogo) -> dict:
    datos = informe["datos"]
    perfil = informe["identidad"]["protocolo"]["perfil"]
    return {"esquema": ESQUEMA_MODELO, "registro": VERSION_REGISTRO_ML if es_ml_ampliado(entrada) else VERSION_REGISTRO, "juego": informe["juego"],
            "reglas": informe["identidad"]["reglas"], "paleta_del_corte": informe["identidad"]["paleta_del_corte"],
            "corte": datos["corte"], "sha256_historico": datos["sha256_historico"],
            "periodo": {"primer_sorteo": datos["primer_sorteo"], "primera_fecha": datos["primera_fecha"],
                        "ultimo_sorteo": datos["ultimo_sorteo"], "ultima_fecha": datos["ultima_fecha"],
                        "sorteos": datos["sorteos"]},
            "variables": _variables(entrada, informe["juego"] == "COLORLOTO"),
            "modelo": {"id": entrada.id, "version": entrada.version, "tipo": entrada.tipo, "familia": entrada.familia,
                       "salida": entrada.salida, "parametros": lm.parametros_de(entrada, perfil)},
            "perfil": perfil, "entrenamiento": _entrenamiento(entrada), "transformacion": _transformacion(entrada),
            "semilla": lm.SEMILLA, "hilos": lm.HILOS, "formato_del_estimador": formato_de(entrada),
            "entorno": la.entorno_ml((entrada,))}


def _evaluacion_asociada(informe: dict, modelo: str) -> dict:
    candidato = next((c for c in informe["candidatos"] if c["id"] == modelo), None)
    uniforme = next((c for c in informe["candidatos"] if c["familia"] == "uniforme"), None)
    ranking = informe["resumen"]["ranking"]
    posicion = next((r["posicion"] for r in ranking if r["id"] == modelo), None)
    colores = informe["juego"] == "COLORLOTO"
    cantidad = informe["identidad"]["reglas"]["cantidad"]
    return {"experimento": informe["clave"], "corte": informe["datos"]["corte"],
            "estado": None if candidato is None else candidato["estado"],
            "veredicto": None if candidato is None else candidato.get("veredicto"),
            "agregado": None if candidato is None else candidato["agregado"],
            "incidencias": [] if candidato is None else candidato["incidencias"],
            "secundarias": None if candidato is None else le.metricas_secundarias(candidato, colores, cantidad),
            "secundarias_uniforme": None if uniforme is None else le.metricas_secundarias(uniforme, colores,
                                                                                           cantidad),
            "posicion_en_el_ranking": posicion, "candidatos_completos": len(ranking),
            "resumen_del_informe": informe["resumen"]["estado"],
            "objetivos": informe["muestra_comun"]["total_objetivos"],
            "muestra_pequena": informe["muestra_comun"]["muestra_pequena"], "nota": NOTA_EVALUACION}


def cuerpo_del_modelo(informe: dict, entrada: lm.EntradaCatalogo, identidad: dict, entrenado: dict) -> dict:
    """`entrenado`: resultado de `entrenar` (sin los bytes del estimador)."""
    return {"esquema": ESQUEMA_MODELO, "clave": huella(identidad), "identidad": identidad,
            "estado_de_uso": ESTADO_DE_USO, "contexto": la.contexto(), "juego": informe["juego"],
            "modelo": entrada.como_dict(identidad["perfil"]),
            "objetivo_estadistico": ("distribucion de los pares numero-color de cada balota (conteos con "
                                     "multiplicidad normalizados)" if entrada.salida == "distribucion_de_pares" else
                                     "probabilidad marginal de aparicion de cada numero en el sorteo siguiente"),
            "datos": {k: informe["datos"][k] for k in ("corte", "sha256_historico", "sorteos", "primer_sorteo",
                                                      "primera_fecha", "ultimo_sorteo", "ultima_fecha", "huecos")},
            "entrenamiento": {"detalle": entrenado["detalle"], "parametros_ajustados": entrenado["parametros"]},
            "componentes": entrenado["componentes"], "contrato_de_inferencia": CONTRATO_DE_INFERENCIA,
            "estimador": {"sha256": entrenado["sha256"], "bytes": entrenado["bytes"],
                          "formato": formato_de(entrada), "clase": entrenado["clase"]},
            "control": entrenado["control"],
            "procedencia": {"experimento": informe["clave"], "evaluacion": _evaluacion_asociada(informe, entrada.id)}}


def componer(cuerpo: dict, publicacion: dict) -> dict:
    artefacto = {**cuerpo, "huella_de_reproduccion": huella(cuerpo), "publicacion": publicacion}
    return {**artefacto, "sello": huella(artefacto)}


def cuerpo_de(artefacto: dict) -> dict:
    return {k: v for k, v in artefacto.items() if k not in VOLATILES_MODELO}


def integro(artefacto: dict) -> bool:
    try:
        return (artefacto.get("sello") == huella({k: v for k, v in artefacto.items() if k != "sello"})
                and artefacto.get("huella_de_reproduccion") == huella(cuerpo_de(artefacto))
                and artefacto.get("clave") == huella(artefacto["identidad"]))
    except (la.ArtefactoLaboratorioError, AttributeError, TypeError, KeyError):
        return False


def con_numero(artefacto: dict, numero: int) -> dict:
    """Numero de version (consecutivo por juego y modelo, reservado de forma
    exclusiva por el almacen), sellado dentro de `publicacion`."""
    sin_sello = {k: v for k, v in artefacto.items() if k != "sello"}
    sin_sello["publicacion"] = {**artefacto["publicacion"], "numero": numero}
    return {**sin_sello, "sello": huella(sin_sello)}


def numero_de(artefacto: dict) -> int:
    return int(artefacto["publicacion"]["numero"])


# ---------------------------------------------------------------------------
# Serializacion del estimador y carga restringida
# ---------------------------------------------------------------------------

_NUMPY_ADMITIDOS = {
    ("numpy", "dtype"), ("numpy", "ndarray"),
    ("numpy._core.multiarray", "_reconstruct"), ("numpy.core.multiarray", "_reconstruct"),
    ("numpy._core.multiarray", "scalar"), ("numpy.core.multiarray", "scalar"),
    ("numpy._core.numeric", "_frombuffer"), ("numpy.core.numeric", "_frombuffer"),
    ("numpy.random._pickle", "__bit_generator_ctor"), ("numpy.random._pickle", "__generator_ctor"),
    ("numpy.random._pickle", "__randomstate_ctor"), ("numpy.random._pcg64", "PCG64"),
    ("numpy.random._mt19937", "MT19937"), ("numpy.random.mtrand", "RandomState"),
    ("numpy.random.bit_generator", "SeedSequence"), ("numpy.random.bit_generator", "__pyx_unpickle_SeedSequence"),
}
_ESTANDAR_ADMITIDOS = {
    ("builtins", "slice"), ("builtins", "set"), ("builtins", "frozenset"), ("builtins", "complex"),
    ("builtins", "range"), ("builtins", "bytearray"), ("functools", "partial"), ("copyreg", "_reconstructor"),
    ("collections", "OrderedDict"),
}
_FUNCIONES_SKLEARN_ADMITIDAS = {("sklearn.utils.validation", "check_array")}


class _DeserializadorRestringido(pickle.Unpickler):
    """Solo clases de scikit-learn, tipos y reconstructores concretos de NumPy
    y unos pocos de la biblioteca estandar. Cualquier otro nombre se rechaza
    ANTES de importarlo o invocarlo."""

    def find_class(self, modulo: str, nombre: str):
        clave = (modulo, nombre)
        if clave in _NUMPY_ADMITIDOS or clave in _ESTANDAR_ADMITIDOS or clave in _FUNCIONES_SKLEARN_ADMITIDAS:
            return super().find_class(modulo, nombre)
        if modulo == "numpy" or modulo.startswith("numpy.dtypes"):
            objeto = super().find_class(modulo, nombre)
            if isinstance(objeto, type) and (issubclass(objeto, np.generic) or issubclass(objeto, np.dtype)):
                return objeto
        elif modulo == "sklearn" or modulo.startswith("sklearn."):
            objeto = super().find_class(modulo, nombre)
            if isinstance(objeto, type):
                return objeto
        raise pickle.UnpicklingError(f"nombre no admitido en un estimador registrado: {modulo}.{nombre}")


def serializar_estimador(estimador) -> bytes:
    return pickle.dumps(estimador, protocol=5)


def sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def deserializar_estimador(contenido: bytes, sha256_esperado: str, bytes_esperados: int | None = None):
    """Comprueba tamano y SHA-256 y deserializa con la lista cerrada."""
    if bytes_esperados is not None and len(contenido) != bytes_esperados:
        raise ModeloRegistradoError("alterado", "el tamano del estimador no coincide con el manifiesto")
    if sha256(contenido) != sha256_esperado:
        raise ModeloRegistradoError("alterado", "el SHA-256 del estimador no coincide con el manifiesto")
    try:
        return _DeserializadorRestringido(io.BytesIO(contenido)).load()
    except (pickle.UnpicklingError, AttributeError, ImportError, EOFError, ValueError, TypeError) as error:
        raise ModeloRegistradoError("estimador_no_admitido", str(error)[:300]) from error


def _envoltura_ml(estimador, identidad: dict, experimento: str) -> dict:
    return {"esquema": ESQUEMA_ESTIMADOR_ML, "identidad_sha256": huella(identidad),
            "experimento": experimento, "modelo": identidad["modelo"], "entorno": identidad["entorno"],
            "estimador": estimador.to_dict()}


def _cargar_ml(contenido: bytes, identidad: dict, experimento: str):
    try:
        datos = json.loads(contenido.decode("utf-8"))
        # canonical bytes reject duplicate keys, NaN, trailing ambiguities and external objects
        if la.serializar_entrada(datos) != contenido:
            raise ValueError("JSON no canonico")
        esperado = {"esquema": ESQUEMA_ESTIMADOR_ML, "identidad_sha256": huella(identidad),
                    "experimento": experimento, "modelo": identidad["modelo"], "entorno": identidad["entorno"]}
        if set(datos) != {*esperado, "estimador"} or any(datos[k] != v for k, v in esperado.items()):
            raise ValueError("envoltura, receta, entorno o procedencia no coinciden")
        if not isinstance(datos["estimador"], dict):
            raise ValueError("estado del estimador no es un objeto")
        candidato_id = datos["estimador"].get("candidato_id")
        if candidato_id is not None and candidato_id != identidad["modelo"]["id"]:
            raise ValueError("identidad interna del estimador no coincide con la receta")
        familia = identidad["modelo"]["familia"]
        clases_bm = {"bayes_jerarquico_binario": "BayesJerarquicoBinario", "bayes_jerarquico_pares": "BayesJerarquicoPares",
                     "markov_apariciones": "MarkovApariciones", "markov_pares": "MarkovPares"}
        if identidad["modelo"]["id"] in clases_bm and datos["estimador"].get("clase") != clases_bm[identidad["modelo"]["id"]]:
            raise ValueError("clase probabilistica no coincide con la receta")
        if familia in ("xgboost", "lightgbm", "redes_neuronales"):
            from app.application.ml.laboratorio_boosts_redes import deserializar_boost_red, validar_receta
            validar_receta(datos["estimador"], identidad["modelo"], identidad)
            estimador = deserializar_boost_red(datos["estimador"])
        elif familia in ("bayesianos", "markov"):
            from app.application.ml.laboratorio_bayes_markov import deserializar_bayes_markov, validar_receta
            validar_receta(datos["estimador"], identidad["modelo"], identidad)
            estimador = deserializar_bayes_markov(datos["estimador"])
        else:
            raise ValueError("familia no admitida por el formato nuevo")
        return estimador
    except (UnicodeError, ValueError, TypeError, KeyError, AttributeError, ImportError, RuntimeError) as error:
        raise ModeloRegistradoError("estimador_no_admitido", str(error)[:300]) from error


def cargar_estimador(artefacto: dict, contenido: bytes):
    """Manifiesto, receta, entorno, procedencia e integridad ANTES de cargar.
    El JSON nuevo nunca pasa por pickle y el cargador historico no se amplia.
    """
    if not integro(artefacto):
        raise ModeloRegistradoError("alterado", "manifiesto sin integridad coherente")
    compatible = compatibilidad(artefacto)
    if not compatible["compatible"]:
        raise ModeloRegistradoError("incompatible", "; ".join(compatible["motivos"]))
    try:
        estimador = artefacto["estimador"]
        if len(contenido) != estimador["bytes"] or sha256(contenido) != estimador["sha256"]:
            raise ModeloRegistradoError("alterado", "bytes o SHA-256 del estimador no coinciden")
        if estimador["formato"] == FORMATO_ML:
            return _cargar_ml(contenido, artefacto["identidad"], artefacto["procedencia"]["experimento"])
        return deserializar_estimador(contenido, estimador["sha256"], estimador["bytes"])
    except (KeyError, TypeError) as error:
        raise ModeloRegistradoError("incompatible", "manifiesto incompleto") from error


def componentes_de(estimador) -> list[dict]:
    """Descripcion legible de los componentes de inferencia serializados
    (la inspeccion de clases de scikit-learn vive en `modelo.py`)."""
    from app.application.ml.modelo import componentes_de_inferencia

    return componentes_de_inferencia(estimador)


# ---------------------------------------------------------------------------
# Entrenamiento (en el proceso trabajador) e inferencia congelada
# ---------------------------------------------------------------------------

def _estimador_a_congelar(entrada: lm.EntradaCatalogo, ajustado: lm.Ajustado):
    if entrada.id == "actual_logistica_ae36":
        return ajustado.estimador.pipeline_calibrado
    return ajustado.estimador


def predecir_congelado(estimador, identidad: dict, instantanea: lv.Instantanea) -> tuple[tuple, np.ndarray]:
    """(candidatos, probabilidades) del objetivo `instantanea.corte + 1` con el
    estimador congelado: variables solo con los sorteos de la instantanea."""
    modelo = identidad["modelo"]
    reglas = instantanea.reglas
    if modelo["id"] == "actual_logistica_ae36":
        from app.application.ml.modelo import ModeloEntrenado, predecir_probabilidades
        from app.application.ml.pronostico_experimental import filas_de_inferencia

        filas = filas_de_inferencia(list(instantanea.sorteos), reglas.codigo, *reglas.rango)
        envoltorio = ModeloEntrenado(estimador, lm.SEMILLA, {}, 0)
        p = np.asarray(predecir_probabilidades(envoltorio, filas), dtype=float)
        candidatos = tuple(f.numero_candidato for f in filas)
    else:
        filas = lv.Variables(instantanea).filas([len(instantanea)])
        p = lm.inferir(estimador, modelo["salida"], filas, reglas.cantidad)
        candidatos = filas.candidatos
    if p.shape != (len(candidatos),) or not np.all(np.isfinite(p)) or np.any(p <= 0) or np.any(p >= 1):
        raise lm.CandidatoNoDisponible("salida_invalida", "probabilidades no finitas o fuera de (0, 1)")
    return candidatos, p


def control_de(candidatos: Sequence, p: np.ndarray) -> dict:
    """Huella de las probabilidades de control (12 decimales) y las 5 primeras."""
    valores = [[list(c) if isinstance(c, tuple) else c, round(float(x), 12)] for c, x in zip(candidatos, p)]
    orden = sorted(valores, key=lambda v: (-v[1], str(v[0])))
    return {"sha256_probabilidades": huella({"probabilidades": valores}), "primeros": orden[:5],
            "candidatos": len(valores)}


def control_recargado(artefacto: dict, contenido: bytes, informe: dict) -> dict:
    """Recarga el estimador (comprobando SHA-256 y la lista cerrada) y recalcula
    el pronostico de control con la instantanea del informe de procedencia."""
    estimador = cargar_estimador(artefacto, contenido)
    if artefacto["identidad"].get("registro") == VERSION_REGISTRO_ML:
        if not la.integro(informe) or informe.get("clave") != artefacto["procedencia"]["experimento"]:
            raise ModeloRegistradoError("incompatible", "el informe de procedencia no coincide")
    instantanea = la.instantanea_del_experimento(informe)
    candidatos, p = predecir_congelado(estimador, artefacto["identidad"], instantanea)
    return {"objetivo": instantanea.corte + 1, **control_de(candidatos, p), "clase": type(estimador).__name__}


def entrenar(informe: dict, entrada: lm.EntradaCatalogo) -> dict:
    """Ajusta el candidato con TODA la instantanea del informe, serializa el
    estimador, lo RECARGA con la deserializacion restringida y comprueba que
    reproduce exactamente el pronostico de control. Se ejecuta en el proceso
    trabajador; no escribe nada."""
    if not lm.registrable(entrada):
        raise ModeloRegistradoError("no_registrable", f"{entrada.nombre} no tiene un estimador que guardar")
    instantanea = la.instantanea_del_experimento(informe)
    perfil = informe["identidad"]["protocolo"]["perfil"]
    variables = lv.Variables(instantanea)
    ajustado = lm.ajustar_candidato(entrada, instantanea, variables, len(instantanea), perfil)
    estimador = _estimador_a_congelar(entrada, ajustado)
    identidad = identidad_del_modelo(informe, entrada)
    candidatos, p = predecir_congelado(estimador, identidad, instantanea)
    if es_ml_ampliado(entrada):
        contenido = la.serializar_entrada(_envoltura_ml(estimador, identidad, informe["clave"]))
        recargado = _cargar_ml(contenido, identidad, informe["clave"])
    else:
        contenido = serializar_estimador(estimador)
        recargado = deserializar_estimador(contenido, sha256(contenido), len(contenido))
    digesto = sha256(contenido)
    candidatos_r, p_r = predecir_congelado(recargado, identidad, instantanea)
    control = control_de(candidatos, p)
    if control_de(candidatos_r, p_r) != control:
        raise ModeloRegistradoError("no_reproduce", "el estimador recargado no reproduce el pronostico de control")
    return {"contenido": contenido, "sha256": digesto, "bytes": len(contenido), "clase": type(estimador).__name__,
            "detalle": ajustado.detalle, "parametros": (getattr(estimador, "parametros", ajustado.parametros)
                if es_ml_ampliado(entrada) else ajustado.parametros),
            "componentes": componentes_de(estimador), "control": {"objetivo": instantanea.corte + 1, **control}}


# ---------------------------------------------------------------------------
# Compatibilidad
# ---------------------------------------------------------------------------

def _menor(version: str) -> str:
    return ".".join(str(version).split(".")[:2])


def compatibilidad(artefacto: dict) -> dict:
    """Comprueba, SIN deserializar, si este codigo y este entorno pueden cargar
    el estimador. Devuelve los motivos de incompatibilidad, si los hay."""
    try:
        identidad = artefacto["identidad"]
        entrada = lm.CATALOGO.get(identidad["modelo"]["id"])
        if entrada is not None and es_ml_ampliado(entrada):
            return _compatibilidad_ml(artefacto, entrada)
        guardado, actual = identidad["entorno"], la.entorno()
    except (KeyError, TypeError, AttributeError):
        return {"compatible": False, "motivos": ["manifiesto incompleto"], "entorno_guardado": {},
                "entorno_actual": la.entorno(), "mismo_entorno": False, "politica": "manifiesto completo"}
    motivos = []
    if identidad.get("registro") != VERSION_REGISTRO:
        motivos.append(f"registro {identidad.get('registro')} distinto de {VERSION_REGISTRO}")
    if identidad.get("formato_del_estimador") != FORMATO_DEL_ESTIMADOR:
        motivos.append("formato del estimador no admitido")
    if guardado.get("scikit-learn") != actual["scikit-learn"]:
        motivos.append(f"scikit-learn {guardado.get('scikit-learn')} (guardado) frente a {actual['scikit-learn']}")
    for paquete in ("python", "numpy", "scipy"):
        if _menor(guardado.get(paquete, "")) != _menor(actual[paquete]):
            motivos.append(f"{paquete} {guardado.get(paquete)} (guardado) frente a {actual[paquete]}")
    entrada = lm.CATALOGO.get(identidad["modelo"]["id"])
    if entrada is None or entrada.version != identidad["modelo"]["version"]:
        motivos.append(f"la receta {identidad['modelo']['id']} v{identidad['modelo']['version']} no esta en este "
                       "catalogo")
    else:
        if identidad["variables"] != _variables(entrada, artefacto["juego"] == "COLORLOTO"):
            motivos.append("las variables de este codigo no son las del modelo")
        if identidad["transformacion"] != _transformacion(entrada):
            motivos.append("la transformacion de probabilidades de este codigo no es la del modelo")
    return {"compatible": not motivos, "motivos": motivos, "entorno_guardado": guardado, "entorno_actual": actual,
            "mismo_entorno": guardado == actual,
            "politica": "misma version de scikit-learn y mismas versiones menores de Python, NumPy y SciPy; el "
                        "sistema operativo solo se informa"}


def _compatibilidad_ml(artefacto: dict, entrada) -> dict:
    actual = la.entorno_ml((entrada,))
    guardado = {}
    motivos = []
    try:
        identidad = artefacto["identidad"]
        guardado = identidad["entorno"]
        if identidad["registro"] != VERSION_REGISTRO_ML:
            motivos.append("version del registro nuevo no admitida")
        if identidad["formato_del_estimador"] != FORMATO_ML or artefacto["estimador"]["formato"] != FORMATO_ML:
            motivos.append("formato del estimador nuevo no admitido")
        for paquete, version in actual.items():
            if paquete != "sistema" and guardado.get(paquete) != version:
                motivos.append(f"{paquete}: {guardado.get(paquete)} frente a {version}; se requiere version exacta")
        if set(guardado) != set(actual):
            motivos.append("inventario de entorno incompleto o ajeno")
        if identidad["modelo"] != {"id": entrada.id, "version": entrada.version, "tipo": entrada.tipo,
                "familia": entrada.familia, "salida": entrada.salida,
                "parametros": lm.parametros_de(entrada, identidad["perfil"])}:
            motivos.append("receta nueva no coincide con el catalogo versionado")
        if identidad["variables"] != _variables(entrada, artefacto["juego"] == "COLORLOTO"):
            motivos.append("contrato de variables no coincide")
        if identidad["transformacion"] != _transformacion(entrada) or identidad["entrenamiento"] != _entrenamiento(entrada):
            motivos.append("transformacion o entrenamiento no coinciden")
        if artefacto["juego"] not in entrada.juegos or identidad["juego"] != artefacto["juego"]:
            motivos.append("juego no admitido por la receta")
        if artefacto["modelo"] != entrada.como_dict(identidad["perfil"]):
            motivos.append("descripcion de modelo no coincide con el catalogo")
        if not isinstance(artefacto["procedencia"]["experimento"], str) or len(artefacto["procedencia"]["experimento"]) != 64:
            motivos.append("procedencia no valida")
        if artefacto["esquema"] != ESQUEMA_MODELO or identidad["esquema"] != ESQUEMA_MODELO:
            motivos.append("esquema de manifiesto no admitido")
        if identidad["reglas"] != lv.REGLAS[artefacto["juego"]].como_dict():
            motivos.append("reglas del juego incompatibles")
        if identidad["semilla"] != lm.SEMILLA or identidad["hilos"] != lm.HILOS:
            motivos.append("presupuesto o semilla incompatibles")
        datos = artefacto["datos"]
        if datos["corte"] != identidad["corte"] or datos["sha256_historico"] != identidad["sha256_historico"]:
            motivos.append("datos y periodo de identidad no coinciden")
        if any(datos[k] != v for k, v in identidad["periodo"].items()):
            motivos.append("intervalo de entrenamiento incoherente")
        if not isinstance(identidad["paleta_del_corte"], list):
            motivos.append("paleta del corte incompleta")
        entrenamiento = artefacto["entrenamiento"]
        if not isinstance(entrenamiento["detalle"], dict) or not isinstance(entrenamiento["parametros_ajustados"], dict):
            motivos.append("detalle del entrenamiento incompleto")
        componentes = artefacto["componentes"]
        if not isinstance(componentes, list) or not componentes or any(
                not isinstance(c, dict) or not all(k in c for k in ("paso", "clase", "detalle")) for c in componentes):
            motivos.append("componentes de inferencia incompletos")
        control = artefacto["control"]
        if control["objetivo"] != identidad["corte"] + 1 or not isinstance(control["candidatos"], int) or control["candidatos"] < 1:
            motivos.append("objetivo o candidatos de control incompatibles")
        if len(control["sha256_probabilidades"]) != 64 or not isinstance(control["primeros"], list):
            motivos.append("control incompleto")
        if artefacto["procedencia"]["evaluacion"]["experimento"] != artefacto["procedencia"]["experimento"]:
            motivos.append("evaluacion y procedencia distintas")
        if artefacto["estado_de_uso"] != ESTADO_DE_USO or artefacto["contexto"]["AUTORIZA_EVALUACION"] is not False:
            motivos.append("estado experimental incompatible")
        for clave in ("sha256", "bytes", "clase"):
            artefacto["estimador"][clave]
    except (KeyError, TypeError, AttributeError, ValueError):
        motivos.append("manifiesto incompleto")
    return {"compatible": not motivos, "motivos": motivos, "entorno_guardado": guardado,
            "entorno_actual": actual, "mismo_entorno": guardado == actual,
            "politica": "versiones exactas de Python, NumPy, SciPy, scikit-learn y biblioteca nativa pertinente; "
                        "plataforma informativa, sin promesa de identidad entre plataformas"}


# ---------------------------------------------------------------------------
# Pronosticos con un modelo congelado
# ---------------------------------------------------------------------------

def linea_registrada(artefacto: dict) -> dict:
    identidad = artefacto["identidad"]
    m = identidad["modelo"]
    numero = numero_de(artefacto)
    sufijo = "" if identidad["perfil"] == "predeterminado" else f"-{identidad['perfil']}"
    return {"id": f"{m['id']}-v{m['version']}-reg{numero}{sufijo}", "modelo": m["id"], "version": m["version"],
            "perfil": identidad["perfil"], "tipo": m["tipo"], "juego": artefacto["juego"],
            "registrado": {"clave": artefacto["clave"], "numero": numero}}


def validar_corte_de_entrada(artefacto: dict, instantanea: lv.Instantanea) -> None:
    corte = artefacto["identidad"]["corte"]
    if instantanea.codigo != artefacto["juego"]:
        raise ModeloRegistradoError("corte_no_valido", "la instantanea es de otro juego")
    if instantanea.corte < corte:
        raise ModeloRegistradoError("corte_no_valido", f"el corte de entrada {instantanea.corte} es anterior al de "
                                                       f"entrenamiento {corte}: el modelo ya vio esos resultados")
    hasta = [r for r in instantanea.sorteos if r.numero_sorteo <= corte]
    if not hasta or lv.validar_instantanea(instantanea.codigo, hasta).huella() != artefacto["identidad"][
            "sha256_historico"]:
        raise ModeloRegistradoError("corte_no_valido", "el historico hasta el corte de entrenamiento no coincide con "
                                                       "el que uso el modelo (la base cambio)")


def identidad_del_pronostico_registrado(artefacto: dict, instantanea: lv.Instantanea) -> dict:
    identidad = artefacto["identidad"]
    m = identidad["modelo"]
    return {"esquema": la.ESQUEMA_PRONOSTICO, "implementacion": la.VERSION_IMPLEMENTACION,
            "juego": artefacto["juego"], "experimento": artefacto["procedencia"]["experimento"],
            "corte": instantanea.corte, "sha256_historico": instantanea.huella(),
            "version_de_variables": lv.VERSION_VARIABLES,
            "modelo": {"id": m["id"], "version": m["version"], "parametros": m["parametros"]},
            "modelo_registrado": {"clave": artefacto["clave"], "numero": numero_de(artefacto),
                                  "sha256_estimador": artefacto["estimador"]["sha256"],
                                  "corte_de_entrenamiento": identidad["corte"]},
            "ajuste": "ninguno: modelo registrado congelado (contrato de inferencia de la Fase 3)",
            "transformacion": identidad["transformacion"], "semilla": lm.SEMILLA,
            "entorno": la.entorno_ml((lm.CATALOGO[m["id"]],))}


def cuerpo_del_pronostico_registrado(artefacto: dict, estimador, instantanea: lv.Instantanea,
                                     decimales: int = 12) -> dict:
    """Pronostico del objetivo `instantanea.corte + 1` con el modelo congelado
    (sin reajustar). Mismo formato que los pronosticos del laboratorio, asi que
    el seguimiento y el centro de resultados lo leen igual."""
    validar_corte_de_entrada(artefacto, instantanea)
    candidatos, p = predecir_congelado(estimador, artefacto["identidad"], instantanea)
    if instantanea.reglas.colores:
        entrenados = set(artefacto["identidad"]["paleta_del_corte"])
        nuevos = sorted(set(instantanea.paleta()) - entrenados)
    else:
        nuevos = []
    identidad = identidad_del_pronostico_registrado(artefacto, instantanea)
    pronostico, superbalota = la.contenido_del_pronostico(instantanea, candidatos, p, decimales)
    evaluacion = artefacto["procedencia"]["evaluacion"]
    modelo = dict(artefacto["modelo"])
    modelo["registrado"] = {"clave": artefacto["clave"], "numero": numero_de(artefacto)}
    return {"esquema": la.ESQUEMA_PRONOSTICO, "clave_de_entrada": huella(identidad), "identidad": identidad,
            "linea": linea_registrada(artefacto), "estado_de_uso": ESTADO_DE_USO, "contexto": la.contexto(),
            "juego": artefacto["juego"], "experimento": artefacto["procedencia"]["experimento"], "modelo": modelo,
            "datos": {"corte": instantanea.corte, "sha256_historico": instantanea.huella(),
                      "sorteos": len(instantanea), "ultima_fecha": instantanea.sorteos[-1].fecha.isoformat()},
            "ajuste_final": {"modelo_registrado": artefacto["clave"], "numero": numero_de(artefacto),
                             "corte_de_entrenamiento": artefacto["identidad"]["corte"],
                             "sorteos_nuevos_desde_el_entrenamiento": sum(
                                 1 for r in instantanea.sorteos if r.numero_sorteo > artefacto["identidad"]["corte"]),
                             "colores_no_vistos_en_el_entrenamiento": nuevos},
            "pronostico": pronostico, "superbalota": superbalota,
            "evaluacion_del_experimento": None if evaluacion["estado"] is None else {
                "estado": evaluacion["estado"], "agregado": evaluacion["agregado"],
                "veredicto": evaluacion["veredicto"],
                "nota": "evaluacion de la receta en el informe de procedencia; no acredita ventaja futura"}}


def fuente_registrada(artefacto: dict, estimador, instantanea: lv.Instantanea) -> dict:
    """Vector fuente de Producto 5 (mismo formato que `carteras_ensemble.fuente`)
    con el modelo congelado, para una configuracion que lo elige."""
    validar_corte_de_entrada(artefacto, instantanea)
    reglas = instantanea.reglas
    candidatos, p = predecir_congelado(estimador, artefacto["identidad"], instantanea)
    d = 12
    salida = {"modelo": artefacto["identidad"]["modelo"]["id"], "objetivo": instantanea.corte + 1,
              "calculado_hasta_sorteo": instantanea.corte,
              "tipo": "distribucion_de_pares" if reglas.colores else "marginales_de_aparicion",
              "candidatos": [list(c) for c in candidatos] if reglas.colores else list(candidatos),
              "probabilidades": [round(float(x), d) for x in p],
              "masa": 1 if reglas.colores else reglas.cantidad,
              "detalle": {"modelo_registrado": artefacto["clave"], "numero": numero_de(artefacto),
                          "corte_de_entrenamiento": artefacto["identidad"]["corte"], "ajuste": "ninguno (congelado)"}}
    if reglas.colores:
        salida["paleta"] = list(instantanea.paleta())
    if reglas.superbalota:
        sb = lm.probabilidades_superbalota(instantanea.sorteos, reglas.superbalota)
        salida["superbalota"] = {"estrategia": "frecuencia_con_suavizado_de_laplace",
                                 "candidatos": sorted(sb), "probabilidades": [round(sb[c], d) for c in sorted(sb)],
                                 "nota": "objetivo separado; el modelo de los numeros no aprende la superbalota"}
    return salida


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def resumen(artefacto: dict) -> dict:
    identidad = artefacto["identidad"]
    evaluacion = artefacto["procedencia"]["evaluacion"]
    agregado = evaluacion.get("agregado") or {}
    return {"clave": artefacto["clave"], "numero": numero_de(artefacto), "juego": artefacto["juego"],
            "modelo": identidad["modelo"]["id"], "nombre": artefacto["modelo"]["nombre"],
            "version_de_la_receta": identidad["modelo"]["version"], "perfil": identidad["perfil"],
            "corte": identidad["corte"], "sorteos": identidad["periodo"]["sorteos"],
            "entrenado_en": artefacto["publicacion"].get("terminado_en"),
            "sistema": identidad["entorno"].get("sistema"), "experimento": artefacto["procedencia"]["experimento"],
            "evaluacion": evaluacion.get("estado"), "veredicto": evaluacion.get("veredicto"),
            "log_loss": agregado.get("log_loss"), "log_loss_uniforme": (agregado.get("uniforme") or {}).get("log_loss"),
            "diferencia_log_loss": agregado.get("diferencia_log_loss"), "linea": linea_registrada(artefacto)["id"]}


def proyeccion_a_tablas(artefacto: dict) -> dict:
    """Proyeccion del manifiesto a las columnas de las tablas `modelos` y
    `metricas_modelo` del esquema de la Fase 1 (no se escriben en PostgreSQL:
    el manifiesto sellado es la unica fuente de la version)."""
    identidad = artefacto["identidad"]
    evaluacion = artefacto["procedencia"]["evaluacion"]
    agregado = evaluacion.get("agregado") or {}
    metricas = []
    for nombre, valor in (("log_loss", agregado.get("log_loss")), ("brier", agregado.get("brier")),
                          ("log_loss_uniforme", (agregado.get("uniforme") or {}).get("log_loss")),
                          ("brier_uniforme", (agregado.get("uniforme") or {}).get("brier")),
                          ("diferencia_log_loss", agregado.get("diferencia_log_loss")),
                          ("diferencia_brier", agregado.get("diferencia_brier")),
                          ("precision_en_k", (evaluacion.get("secundarias") or {}).get("precision_en_k")),
                          ("exactitud", (evaluacion.get("secundarias") or {}).get("exactitud"))):
        if valor is not None:
            metricas.append({"nombre_metrica": nombre, "valor": valor})
    return {"modelos": {"nombre_modelo": f"{identidad['modelo']['id']}"[:60],
                        "version": f"v{numero_de(artefacto)}"[:20],
                        "hiperparametros": artefacto["entrenamiento"]["parametros_ajustados"],
                        "metodo_validacion": "walk_forward_6x10_reajuste_por_bloque"[:50],
                        "entrenado_en": artefacto["publicacion"].get("terminado_en"), "activo": None},
            "metricas_modelo": metricas,
            "nota": ("Proyeccion de solo lectura: las tablas de la Fase 1 no se escriben. «activo» queda sin valor "
                     "porque el modelo vigente lo decide la configuracion de carteras (Producto 5), no el registro.")}
