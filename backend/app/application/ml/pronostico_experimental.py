"""
Pronostico experimental de Baloto y Baloto Revancha -Producto 1.

Linea reproducible sobre el historico real:

    historico (hasta un corte) -> variables conocidas antes de cada
    objetivo -> entrenamiento -> evaluacion walk-forward frente a la
    referencia uniforme -> artefacto versionado -> pronostico
    experimental del siguiente sorteo (corte + 1).

Reutiliza sin cambios el dataset sin fuga, las features y el modelo de
AE-36 (regresion logistica calibrada, semilla 42), las metricas del
repositorio (Log Loss, Brier y Precision@5, cuyos aciertos top-5 son
`5 * Precision@5`) y la referencia uniforme `cantidad/rango`. La
superbalota es un objetivo separado, con su propia estrategia (conteo
con suavizado de Laplace) y su propia referencia uniforme `1/16`.

CONTRATO DE USO EXPERIMENTAL. El bloqueo operativo de AE-41 y el NO-GO de
AE-39 impiden entrenar o predecir bajo los contratos existentes. Este
modulo no los modifica: define un estado distinto y explicito,
`experimental_no_acreditado`, autorizado por el propietario para
consultar pronosticos con fines exploratorios. Un pronostico de este
estado no es un resultado acreditado, no es evidencia prospectiva ni
prerregistro de AE-52, no cambia el NO-GO de AE-39 ni el estado de
AE-41, y `AUTORIZA_EVALUACION` sigue siendo `False`. Si el modelo pierde
frente a la referencia uniforme, el artefacto lo dice y el flujo sigue
funcionando.

IDENTIDAD. `clave_de_entrada` resume juego, reglas, corte, SHA-256 del
historico usado, configuracion, version de la linea y versiones de
scikit-learn y NumPy. Es el identificador del artefacto: repetir la misma
entrada devuelve el artefacto ya guardado (sin reentrenar); un historico
corregido produce otra clave y otra version para el mismo objetivo.

CLASIFICACION TEMPORAL. `clasificar_objetivo` distingue la simulacion
retrospectiva (el objetivo ya figura en la base), el pronostico sobre el
ultimo dato disponible (el objetivo es el siguiente al ultimo sorteo
cargado, lo que no prueba que el sorteo no se haya celebrado) y el
objetivo no cargado con sorteos posteriores (un hueco).

El modulo es puro: no lee el reloj, no accede a la red ni a la base de
datos y no escribe archivos. La fecha de generacion la aporta quien
persiste el artefacto, y una fecha del sistema no prueba anterioridad.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from importlib import metadata
from types import MappingProxyType

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.baselines import baseline_uniforme
from app.application.ml.dataset import PERIODO_CALENTAMIENTO_MINIMO, TAMANOS_VENTANA, construir_dataset_binario
from app.application.ml.features import (
    aparecio_en_sorteo_anterior,
    frecuencia_en_ventana,
    frecuencia_historica,
    sorteos_desde_ultima_aparicion,
)
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.metricas import evaluar
from app.application.ml.modelo import NOMBRES_FEATURES, entrenar_modelo_calibrado, predecir_probabilidades
from app.application.ml.propuesta_inferencia_prospectiva import AUTORIZA_EVALUACION
from app.application.ml.registro_prospectivo import EntradaRegistroInvalidaError, hash_entrada, serializar_entrada
from app.application.ml.tipos import FilaCandidato
from app.application.ml.ventanas_temporales import INICIO_HOLDOUT

ESQUEMA_ARTEFACTO = "pronostico-experimental/1"
ESTADO_DE_USO = "experimental_no_acreditado"
JUEGOS_DEL_PRONOSTICO = ("BALOTO", "BALOTO_REVANCHA")
ESTRATEGIA_NUMEROS = "logistica_calibrada_ae36"
ESTRATEGIA_SUPERBALOTA = "frecuencia_con_suavizado_de_laplace"
VERSION_DE_LA_LINEA = "producto1-1"
"""Cambia si cambian las features, el modelo, las metricas o la forma
del artefacto; los artefactos ya guardados conservan su version."""

CONTRATO_DE_USO_EXPERIMENTAL = MappingProxyType({
    "estado": ESTADO_DE_USO,
    "autorizado_por": "propietario del proyecto, Producto 1",
    "permite": (
        "entrenar con el historico real de Baloto y Revancha hasta un corte",
        "evaluar walk-forward frente a la referencia uniforme",
        "generar, conservar y consultar un pronostico experimental del siguiente sorteo",
    ),
    "no_permite": (
        "presentar el pronostico como ventaja predictiva acreditada ni como recomendacion de apuesta",
        "modificar el NO-GO de AE-39 ni el estado operativo de AE-41",
        "cambiar AUTORIZA_EVALUACION, que sigue en False",
        "contar el pronostico como evidencia prospectiva o prerregistro de AE-52",
    ),
    "consecuencias": (
        "los sorteos desde 2706, reservados como holdout desde AE-39, se leen como historico; "
        "un pronostico experimental que los usa no los convierte en evidencia confirmatoria",
        "la fecha de generacion es la del reloj local de quien genera y no prueba anterioridad",
    ),
})


class PronosticoExperimentalError(ValueError):
    """Entrada no admitida: juego, configuracion, corte o historico."""


@dataclass(frozen=True)
class ConfiguracionExperimental:
    """Parametros fijados; forman parte del artefacto."""

    semilla: int = 42
    proporcion_calibracion: float = 0.2
    tamano_bloque: int = 20
    bloques_de_evaluacion: int = 10
    minimo_objetivos_de_entrenamiento: int = 100
    decimales: int = 12

    def __post_init__(self) -> None:
        for nombre in ("semilla", "tamano_bloque", "bloques_de_evaluacion", "minimo_objetivos_de_entrenamiento",
                       "decimales"):
            valor = getattr(self, nombre)
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < (0 if nombre == "semilla" else 1):
                raise PronosticoExperimentalError(f"{nombre} invalido: {valor!r}")
        if not 0 < self.proporcion_calibracion < 0.5:
            raise PronosticoExperimentalError(f"proporcion_calibracion invalida: {self.proporcion_calibracion!r}")


@dataclass(frozen=True)
class FilaDeInferencia:
    """Fila sin etiqueta del objetivo `corte + 1`, con las mismas
    features que `dataset.py` calcula para las filas etiquetadas."""

    codigo_juego: str
    sorteo_objetivo: int
    calculado_hasta_sorteo: int
    numero_candidato: int
    frecuencia_acumulada: float
    frecuencia_ventana_10: float
    frecuencia_ventana_20: float
    frecuencia_ventana_50: float
    sorteos_desde_ultima_aparicion: int | None
    aparecio_en_sorteo_anterior: int


# ---------------------------------------------------------------------------
# Historico
# ---------------------------------------------------------------------------

def _validar_historico(historico, codigo_juego, rango_min, rango_max, cantidad_numeros, rango_superbalota,
                       hasta_numero_sorteo):
    if codigo_juego not in JUEGOS_DEL_PRONOSTICO:
        raise PronosticoExperimentalError(
            f"'{codigo_juego}' no admite pronostico experimental; solo {', '.join(JUEGOS_DEL_PRONOSTICO)}")
    ordenado = validar_y_ordenar_historico(historico, codigo_juego)
    if not ordenado:
        raise PronosticoExperimentalError(f"{codigo_juego} no tiene sorteos en el historico")
    if hasta_numero_sorteo is not None:
        posteriores = [r.numero_sorteo for r in ordenado if r.numero_sorteo > hasta_numero_sorteo]
        if posteriores:
            raise PronosticoExperimentalError(
                f"El historico contiene sorteos posteriores al corte {hasta_numero_sorteo}: {posteriores[:5]}")
    for r in ordenado:
        if len(r.numeros) != cantidad_numeros or len(set(r.numeros)) != cantidad_numeros:
            raise PronosticoExperimentalError(
                f"Sorteo {r.numero_sorteo}: se esperaban {cantidad_numeros} numeros distintos")
        if any(n < rango_min or n > rango_max for n in r.numeros):
            raise PronosticoExperimentalError(f"Sorteo {r.numero_sorteo}: numeros fuera de [{rango_min}, {rango_max}]")
        if r.superbalota is not None and rango_superbalota is not None and not (
                rango_superbalota[0] <= r.superbalota <= rango_superbalota[1]):
            raise PronosticoExperimentalError(f"Sorteo {r.numero_sorteo}: superbalota fuera de rango")
    return ordenado


def huella_del_historico(ordenado: Sequence[ResultadoNumerico]) -> str:
    """SHA-256 de la serializacion canonica de AE-52 de los sorteos
    usados (numero, fecha, numeros y superbalota)."""
    contenido = serializar_entrada({"sorteos": [
        [r.numero_sorteo, r.fecha.isoformat(), list(r.numeros), r.superbalota] for r in ordenado]})
    return hash_entrada(contenido)


def _procedencia(ordenado: Sequence[ResultadoNumerico], corte: int) -> dict:
    numeros = [r.numero_sorteo for r in ordenado]
    presentes = set(numeros)
    huecos = [n for n in range(numeros[0], numeros[-1] + 1) if n not in presentes]
    return {
        "total_sorteos": len(ordenado),
        "primer_sorteo": numeros[0], "primera_fecha": ordenado[0].fecha.isoformat(),
        "ultimo_sorteo": numeros[-1], "ultima_fecha": ordenado[-1].fecha.isoformat(),
        "corte": corte,
        "huecos": {"cantidad": len(huecos), "primeros": huecos[:20]},
        "sorteos_desde_el_holdout_de_ae39": sum(1 for n in numeros if n >= INICIO_HOLDOUT),
        "sha256_historico": huella_del_historico(ordenado),
    }


# ---------------------------------------------------------------------------
# Particion walk-forward y filas
# ---------------------------------------------------------------------------

def bloques_walk_forward(objetivos: Sequence[int], configuracion: ConfiguracionExperimental) -> list[tuple[int, ...]]:
    """Ultimos `bloques_de_evaluacion` bloques consecutivos de
    `tamano_bloque` objetivos, en orden cronologico; cada bloque tiene
    antes al menos `minimo_objetivos_de_entrenamiento` objetivos."""
    tamano, bloques = configuracion.tamano_bloque, []
    fin = len(objetivos)
    while len(bloques) < configuracion.bloques_de_evaluacion:
        inicio = fin - tamano
        if inicio < configuracion.minimo_objetivos_de_entrenamiento:
            break
        bloques.append(tuple(objetivos[inicio:fin]))
        fin = inicio
    return list(reversed(bloques))


def filas_de_entrenamiento(filas: Sequence[FilaCandidato], primer_objetivo_evaluado: int) -> list[FilaCandidato]:
    """Filas cuyo objetivo es estrictamente anterior al primer objetivo
    evaluado. Sus features usan solo sorteos anteriores a su propio
    objetivo (`dataset.py`), asi que ningun sorteo del bloque evaluado
    ni posterior entra al entrenamiento."""
    return [f for f in filas if f.sorteo_objetivo < primer_objetivo_evaluado]


def filas_de_inferencia(ordenado: Sequence[ResultadoNumerico], codigo_juego: str, rango_min: int,
                        rango_max: int) -> list[FilaDeInferencia]:
    """Filas del objetivo `ultimo + 1`, calculadas con todo `ordenado`."""
    corte = ordenado[-1].numero_sorteo
    v10, v20, v50 = TAMANOS_VENTANA
    return [FilaDeInferencia(
        codigo_juego=codigo_juego, sorteo_objetivo=corte + 1, calculado_hasta_sorteo=corte, numero_candidato=n,
        frecuencia_acumulada=frecuencia_historica(ordenado, n),
        frecuencia_ventana_10=frecuencia_en_ventana(ordenado, n, v10),
        frecuencia_ventana_20=frecuencia_en_ventana(ordenado, n, v20),
        frecuencia_ventana_50=frecuencia_en_ventana(ordenado, n, v50),
        sorteos_desde_ultima_aparicion=sorteos_desde_ultima_aparicion(ordenado, n),
        aparecio_en_sorteo_anterior=aparecio_en_sorteo_anterior(ordenado, n),
    ) for n in range(rango_min, rango_max + 1)]


# ---------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------

def _r(valor: float, decimales: int) -> float:
    if not math.isfinite(valor):
        raise PronosticoExperimentalError("metrica no finita")
    return round(float(valor), decimales)


def _metricas_numeros(metricas, decimales: int) -> dict:
    return {"log_loss": _r(metricas.log_loss, decimales), "brier": _r(metricas.brier_score, decimales),
            "precision_en_5": _r(metricas.precision_en_5, decimales),
            "aciertos_top5_por_sorteo": _r(5 * metricas.precision_en_5, decimales),
            "sorteos": metricas.total_sorteos, "filas": metricas.total_filas}


def _comparacion(modelo: dict, referencia: dict) -> dict:
    """Menor Log Loss y menor Brier son mejores; mas aciertos top-5 es
    mejor. Sin pruebas de significancia: es una descripcion."""
    def lado(menor_es_mejor, a, b):
        if a == b:
            return "empate"
        return "modelo" if (a < b) == menor_es_mejor else "referencia_uniforme"
    resultado = {"log_loss": lado(True, modelo["log_loss"], referencia["log_loss"]),
                 "brier": lado(True, modelo["brier"], referencia["brier"]),
                 "aciertos_top5": lado(False, modelo["aciertos_top5_por_sorteo"],
                                       referencia["aciertos_top5_por_sorteo"])}
    principales = (resultado["log_loss"], resultado["brier"])
    resultado["veredicto"] = (
        "el_modelo_supera_a_la_referencia_en_log_loss_y_brier" if principales == ("modelo", "modelo")
        else "el_modelo_no_supera_a_la_referencia_uniforme")
    return resultado


def _superbalota(ordenado, rango, objetivos_evaluados, decimales) -> dict | None:
    if rango is None:
        return None
    lo, hi = rango
    clases = list(range(lo, hi + 1))
    k = len(clases)
    previos: Counter = Counter()
    vistos = 0
    evaluados = set(objetivos_evaluados)
    perdida = brier = aciertos = 0.0
    perdida_u = brier_u = aciertos_u = 0.0
    n = 0
    for r in ordenado:
        if r.numero_sorteo in evaluados and r.superbalota is not None:
            p = {c: (previos[c] + 1) / (vistos + k) for c in clases}
            perdida += -math.log(p[r.superbalota])
            brier += sum((p[c] - (1.0 if c == r.superbalota else 0.0)) ** 2 for c in clases)
            aciertos += 1.0 if min(clases, key=lambda c: (-p[c], c)) == r.superbalota else 0.0
            perdida_u += math.log(k)
            brier_u += (1 - 1 / k) ** 2 + (k - 1) * (1 / k) ** 2
            aciertos_u += 1.0 if r.superbalota == clases[0] else 0.0
            n += 1
        if r.superbalota is not None:
            previos[r.superbalota] += 1
            vistos += 1
    pronostico = {c: (previos[c] + 1) / (vistos + k) for c in clases}
    ranking = sorted(clases, key=lambda c: (-pronostico[c], c))
    modelo = referencia = None
    if n:
        modelo = {"log_loss": _r(perdida / n, decimales), "brier": _r(brier / n, decimales),
                  "aciertos_top1": _r(aciertos / n, decimales), "sorteos": n}
        referencia = {"log_loss": _r(perdida_u / n, decimales), "brier": _r(brier_u / n, decimales),
                      "aciertos_top1": _r(aciertos_u / n, decimales), "sorteos": n}
    veredicto = None
    if modelo is not None:
        veredicto = ("la_estrategia_supera_a_la_referencia_en_log_loss_y_brier"
                     if modelo["log_loss"] < referencia["log_loss"] and modelo["brier"] < referencia["brier"]
                     else "la_estrategia_no_supera_a_la_referencia_uniforme")
    return {
        "objetivo": "superbalota (objetivo separado de los numeros principales)",
        "estrategia": ESTRATEGIA_SUPERBALOTA, "rango": [lo, hi],
        "parametros": {"suavizado": 1, "historico": "todos los sorteos anteriores al objetivo"},
        "evaluacion_walk_forward": {"estrategia": modelo, "referencia_uniforme": referencia, "veredicto": veredicto},
        "pronostico": {
            "ranking": [{"superbalota": c, "probabilidad": _r(pronostico[c], decimales),
                         "probabilidad_uniforme": _r(1 / k, decimales)} for c in ranking],
            "sugerida": ranking[0],
        },
    }


# ---------------------------------------------------------------------------
# Linea completa
# ---------------------------------------------------------------------------

def _version(paquete: str) -> str:
    try:
        return metadata.version(paquete)
    except metadata.PackageNotFoundError:
        return "desconocida"


def clave_de_entrada(historico: Sequence[ResultadoNumerico], *, codigo_juego: str, rango_min: int, rango_max: int,
                     cantidad_numeros: int, rango_superbalota: tuple[int, int] | None,
                     hasta_numero_sorteo: int | None = None,
                     configuracion: ConfiguracionExperimental = ConfiguracionExperimental()) -> str:
    """Identificador determinista de una ejecucion, calculable sin
    entrenar: mismo juego, reglas, corte, historico, configuracion y
    versiones -> misma clave."""
    ordenado = _validar_historico(historico, codigo_juego, rango_min, rango_max, cantidad_numeros,
                                  rango_superbalota, hasta_numero_sorteo)
    entrada = {
        "esquema": ESQUEMA_ARTEFACTO, "version_de_la_linea": VERSION_DE_LA_LINEA, "juego": codigo_juego,
        "reglas": [rango_min, rango_max, cantidad_numeros, list(rango_superbalota) if rango_superbalota else None],
        "corte": ordenado[-1].numero_sorteo, "sha256_historico": huella_del_historico(ordenado),
        "configuracion": asdict(configuracion),
        "entorno": {"scikit-learn": _version("scikit-learn"), "numpy": _version("numpy")},
    }
    return hash_entrada(serializar_entrada(entrada))


TIPOS_TEMPORALES = ("simulacion_retrospectiva", "pronostico_sobre_el_ultimo_dato_disponible",
                    "objetivo_no_cargado_con_sorteos_posteriores")


def clasificar_objetivo(objetivo: int, disponibles: Sequence[ResultadoNumerico], *,
                        numeros_sugeridos: Sequence[int], superbalota_sugerida: int | None) -> dict:
    """Clasifica el objetivo frente a TODO el historico cargado (sin el
    corte pedido). Nunca afirma que un sorteo es futuro: solo puede
    decir si ya figura en la base o si es el siguiente al ultimo cargado."""
    if not disponibles:
        raise PronosticoExperimentalError("no hay sorteos cargados para clasificar el objetivo")
    ordenado = sorted(disponibles, key=lambda r: r.numero_sorteo)
    ultimo = ordenado[-1]
    observado = next((r for r in ordenado if r.numero_sorteo == objetivo), None)
    base = {"objetivo": objetivo, "objetivo_en_la_base": observado is not None,
            "ultimo_sorteo_disponible": ultimo.numero_sorteo, "ultima_fecha_disponible": ultimo.fecha.isoformat()}
    if observado is not None:
        return {**base, "tipo": "simulacion_retrospectiva",
                "descripcion": (f"Simulacion retrospectiva: el sorteo objetivo {objetivo} ya figura en la base. El "
                                "pronostico usa solo datos hasta el corte y se compara con el resultado observado."),
                "resultado_observado": {
                    "numeros": list(observado.numeros), "superbalota": observado.superbalota,
                    "aciertos_numeros_sugeridos": len(set(observado.numeros) & set(numeros_sugeridos)),
                    "acierto_superbalota": (None if observado.superbalota is None or superbalota_sugerida is None
                                            else observado.superbalota == superbalota_sugerida)}}
    if objetivo > ultimo.numero_sorteo:
        return {**base, "tipo": "pronostico_sobre_el_ultimo_dato_disponible",
                "descripcion": (f"Pronostico experimental sobre el ultimo dato disponible: el objetivo {objetivo} es "
                                f"el siguiente al ultimo sorteo cargado ({ultimo.numero_sorteo}, "
                                f"{ultimo.fecha.isoformat()}). Esto no prueba que el sorteo no se haya celebrado: "
                                "no hay evidencia de calendario ni de que el historico este actualizado."),
                "resultado_observado": None}
    return {**base, "tipo": "objetivo_no_cargado_con_sorteos_posteriores",
            "descripcion": (f"El objetivo {objetivo} no figura en la base, pero hay sorteos posteriores cargados "
                            f"(hasta {ultimo.numero_sorteo}): es una simulacion retrospectiva sobre un hueco del "
                            "historico, sin resultado observado para comparar."),
            "resultado_observado": None}


def generar_pronostico(historico: Sequence[ResultadoNumerico], *, codigo_juego: str, rango_min: int,
                       rango_max: int, cantidad_numeros: int, rango_superbalota: tuple[int, int] | None,
                       hasta_numero_sorteo: int | None = None, decisiones_ae39: Mapping[str, str] | None = None,
                       configuracion: ConfiguracionExperimental = ConfiguracionExperimental()) -> dict:
    """Cuerpo determinista del artefacto (sin fecha de generacion). El
    `historico` debe llegar ya recortado al corte: un sorteo posterior
    se rechaza, nunca se filtra en silencio."""
    if AUTORIZA_EVALUACION is not False:
        raise PronosticoExperimentalError("AUTORIZA_EVALUACION debe seguir en False")
    ordenado = _validar_historico(historico, codigo_juego, rango_min, rango_max, cantidad_numeros,
                                  rango_superbalota, hasta_numero_sorteo)
    corte = ordenado[-1].numero_sorteo
    dataset = construir_dataset_binario(ordenado, rango_min, rango_max, cantidad_numeros, codigo_juego)
    bloques = bloques_walk_forward(dataset.sorteos_objetivo, configuracion)
    minimo = (PERIODO_CALENTAMIENTO_MINIMO + configuracion.minimo_objetivos_de_entrenamiento
              + configuracion.tamano_bloque)
    if not bloques:
        raise PronosticoExperimentalError(
            f"Historico insuficiente para {codigo_juego}: {len(ordenado)} sorteos; hacen falta al menos {minimo} "
            f"({PERIODO_CALENTAMIENTO_MINIMO} de calentamiento, "
            f"{configuracion.minimo_objetivos_de_entrenamiento} objetivos de entrenamiento y un bloque de "
            f"{configuracion.tamano_bloque})")
    d = configuracion.decimales
    por_bloque, filas_eval, probs_eval = [], [], []
    for bloque in bloques:
        entrenamiento = filas_de_entrenamiento(dataset.filas, bloque[0])
        evaluadas = [f for f in dataset.filas if bloque[0] <= f.sorteo_objetivo <= bloque[-1]]
        if max(f.sorteo_objetivo for f in entrenamiento) >= bloque[0]:
            raise PronosticoExperimentalError("fuga temporal: entrenamiento con objetivos del bloque evaluado")
        modelo = entrenar_modelo_calibrado(entrenamiento, semilla=configuracion.semilla,
                                           proporcion_calibracion=configuracion.proporcion_calibracion)
        probabilidades = predecir_probabilidades(modelo, evaluadas)
        metricas_modelo = _metricas_numeros(evaluar(evaluadas, probabilidades), d)
        metricas_uniforme = _metricas_numeros(
            baseline_uniforme(evaluadas, rango_min, rango_max, cantidad_numeros).metricas, d)
        por_bloque.append({
            "objetivos": [bloque[0], bloque[-1]],
            "entrenamiento": {"objetivos": [entrenamiento[0].sorteo_objetivo, entrenamiento[-1].sorteo_objetivo],
                              "sorteos_objetivo": len({f.sorteo_objetivo for f in entrenamiento})},
            "modelo": metricas_modelo, "referencia_uniforme": metricas_uniforme,
            "comparacion": _comparacion(metricas_modelo, metricas_uniforme),
        })
        filas_eval.extend(evaluadas)
        probs_eval.extend(probabilidades)
    agregado_modelo = _metricas_numeros(evaluar(filas_eval, probs_eval), d)
    agregado_uniforme = _metricas_numeros(baseline_uniforme(filas_eval, rango_min, rango_max,
                                                            cantidad_numeros).metricas, d)
    final = entrenar_modelo_calibrado(dataset.filas, semilla=configuracion.semilla,
                                      proporcion_calibracion=configuracion.proporcion_calibracion)
    inferencia = filas_de_inferencia(ordenado, codigo_juego, rango_min, rango_max)
    probabilidades = predecir_probabilidades(final, inferencia)
    uniforme = cantidad_numeros / (rango_max - rango_min + 1)
    ranking = sorted(zip(inferencia, probabilidades), key=lambda par: (-par[1], par[0].numero_candidato))
    objetivos_evaluados = [t for b in bloques for t in b]
    cuerpo = {
        "esquema": ESQUEMA_ARTEFACTO,
        "clave_de_entrada": clave_de_entrada(ordenado, codigo_juego=codigo_juego, rango_min=rango_min,
                                             rango_max=rango_max, cantidad_numeros=cantidad_numeros,
                                             rango_superbalota=rango_superbalota, configuracion=configuracion),
        "estado_de_uso": ESTADO_DE_USO,
        "contrato_de_uso": {clave: list(v) if isinstance(v, tuple) else v
                            for clave, v in CONTRATO_DE_USO_EXPERIMENTAL.items()},
        "juego": codigo_juego,
        "version_de_la_linea": VERSION_DE_LA_LINEA,
        "estrategia": {
            "numeros": ESTRATEGIA_NUMEROS,
            "features": list(NOMBRES_FEATURES),
            "hiperparametros": dict(final.hiperparametros),
            "calibracion": "sigmoid con PredefinedSplit: bloque tardio de cada entrenamiento",
            "referencia": "uniforme cantidad_numeros/tamano_rango",
        },
        "configuracion": asdict(configuracion),
        "datos": _procedencia(ordenado, corte),
        "entrenamiento_final": {
            "objetivos": [dataset.sorteos_objetivo[0], dataset.sorteos_objetivo[-1]],
            "sorteos_objetivo": len(dataset.sorteos_objetivo),
            "calentamiento": PERIODO_CALENTAMIENTO_MINIMO,
            "frontera_base_calibracion": final.frontera_base_calibracion,
        },
        "evaluacion_walk_forward": {
            "bloques": por_bloque,
            "agregado": {"modelo": agregado_modelo, "referencia_uniforme": agregado_uniforme,
                         "comparacion": _comparacion(agregado_modelo, agregado_uniforme)},
            "definiciones": "Log Loss y Brier sobre todas las filas candidato-sorteo (menor es mejor); "
                            "aciertos top-5 = 5 * Precision@5 con desempate por numero ascendente "
                            "(app/application/ml/metricas.py)",
        },
        "pronostico": {
            "objetivo": corte + 1,
            "calculado_hasta_sorteo": corte,
            "numeros_sugeridos": sorted(f.numero_candidato for f, _ in ranking[:cantidad_numeros]),
            "ranking": [{"numero": f.numero_candidato, "probabilidad": _r(p, d), "probabilidad_uniforme": _r(uniforme, d)}
                        for f, p in ranking],
            "nota": "probabilidad marginal de aparicion de cada numero estimada por el modelo; no es una garantia",
        },
        "superbalota": _superbalota(ordenado, rango_superbalota, objetivos_evaluados, d),
        "contexto": {
            "decision_ae39": dict(decisiones_ae39 or {}).get(codigo_juego, "no_go_sin_evidencia_suficiente"),
            "AUTORIZA_EVALUACION": AUTORIZA_EVALUACION,
            "estado_operativo_ae41": "sin cambios; este pronostico usa el contrato experimental",
            "resultado_acreditado": False,
        },
        "entorno": {"scikit-learn": _version("scikit-learn"), "numpy": _version("numpy")},
    }
    return cuerpo


def huella_de_reproduccion(cuerpo: dict) -> str:
    """SHA-256 de la serializacion canonica de AE-52 del cuerpo (sin la
    fecha de generacion). Dos ejecuciones con el mismo historico, la
    misma configuracion y las mismas versiones dan la misma huella."""
    try:
        return hash_entrada(serializar_entrada(cuerpo))
    except EntradaRegistroInvalidaError as error:
        raise PronosticoExperimentalError(str(error)) from error


def componer_artefacto(cuerpo: dict, *, generado_en: str, clasificacion_temporal: dict | None = None,
                       frescura: dict | None = None) -> dict:
    """Artefacto persistible: cuerpo, huella de reproduccion, los datos de
    la generacion (fecha declarada, clasificacion temporal y frescura del
    historico en ese momento) y un sello SHA-256 de todo lo anterior."""
    artefacto = {**cuerpo, "huella_de_reproduccion": huella_de_reproduccion(cuerpo),
                 "generacion": {"generado_en": generado_en,
                                "nota": "reloj local de quien genero el artefacto; no prueba anterioridad",
                                "clasificacion_temporal": clasificacion_temporal, "frescura": frescura}}
    return {**artefacto, "sello": sello(artefacto)}


def con_orden_de_emision(artefacto: Mapping, *, secuencia: int, version_anterior: str | None) -> dict:
    """Copia del artefacto con su orden de emision dentro del objetivo
    (asignado por el almacen al guardarlo) y un sello nuevo que lo cubre.
    El orden nunca se deduce de fechas, nombres ni del sistema de archivos."""
    generacion = {**artefacto["generacion"], "secuencia_en_el_objetivo": secuencia,
                  "version_anterior": version_anterior}
    nuevo = {k: v for k, v in artefacto.items() if k != "sello"}
    nuevo["generacion"] = generacion
    return {**nuevo, "sello": sello(nuevo)}


def sello(artefacto: Mapping) -> str:
    """SHA-256 canonico del artefacto sin su propio sello: detecta una
    alteracion de cualquier campo, incluida la fecha de generacion."""
    return huella_de_reproduccion({k: v for k, v in artefacto.items() if k != "sello"})


def artefacto_integro(artefacto: Mapping) -> bool:
    try:
        return (artefacto.get("sello") == sello(artefacto)
                and artefacto.get("huella_de_reproduccion") == huella_de_reproduccion(cuerpo_del_artefacto(artefacto)))
    except (PronosticoExperimentalError, AttributeError, TypeError):
        return False


def cuerpo_del_artefacto(artefacto: Mapping) -> dict:
    return {k: v for k, v in artefacto.items() if k not in ("huella_de_reproduccion", "generacion", "sello")}


def comprobar_reproduccion(artefacto: Mapping, cuerpo_recalculado: dict) -> dict:
    """Compara un artefacto guardado con un recalculo: huella exacta y,
    si difiere (otra plataforma u otras versiones), la mayor diferencia
    de probabilidad del ranking."""
    guardado = cuerpo_del_artefacto(artefacto)
    exacta = huella_de_reproduccion(guardado) == huella_de_reproduccion(cuerpo_recalculado)
    a = {f["numero"]: f["probabilidad"] for f in guardado["pronostico"]["ranking"]}
    b = {f["numero"]: f["probabilidad"] for f in cuerpo_recalculado["pronostico"]["ranking"]}
    diferencia = max(abs(a[n] - b.get(n, math.inf)) for n in a) if set(a) == set(b) else math.inf
    return {"huella_exacta": exacta,
            "mismos_datos": guardado["datos"]["sha256_historico"] == cuerpo_recalculado["datos"]["sha256_historico"],
            "mismos_numeros_sugeridos": guardado["pronostico"]["numeros_sugeridos"]
            == cuerpo_recalculado["pronostico"]["numeros_sugeridos"],
            "maxima_diferencia_de_probabilidad": diferencia}
