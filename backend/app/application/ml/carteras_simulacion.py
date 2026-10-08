"""
Producto 5 -simulacion Monte Carlo de una cartera guardada.

Compara la cartera ELEGIDA con una cartera UNIFORME guardada (mismo juego,
objetivo, cantidad de combinaciones y diversidad). Dentro de cada escenario,
ambas se enfrentan EXACTAMENTE a los mismos sorteos sinteticos. Las
combinaciones de una cartera no son ensayos independientes del mismo
sorteo: por cada sorteo compartido se mide el MEJOR resultado de la cartera
(maximo de aciertos entre sus lineas).

ESCENARIOS (separados; sus supuestos van en el resultado):
1. `sorteos_uniformes`: 5 numeros principales uniformes sin reemplazo y
   superbalota uniforme aparte (independiente de los numeros); ColorLoto: 6
   extracciones uniformes con reemplazo sobre la paleta congelada del corte.
2. `muestreo_ponderado`: HIPOTESIS construida con las probabilidades del
   modelo fuente de la cartera elegida. Numeros: muestreo secuencial
   ponderado sin reemplazo con las marginales normalizadas como pesos (no es
   una distribucion conjunta aprendida). Superbalota: estrategia separada de
   Producto 1, independiente de los numeros por supuesto. ColorLoto: 6
   extracciones con reemplazo de la distribucion de pares (suposicion
   multinomial de Producto 2). Aqui la cartera elegida se evalua con un
   mecanismo relacionado con el modelo que la construyo: una ventaja simulada
   NO es una confirmacion independiente ni una probabilidad real de acertar
   un sorteo futuro.

METRICAS por escenario y cartera: distribucion de aciertos por combinacion
(denominador simulaciones x lineas), distribucion del maximo de la cartera
(0-5 en numeros, 0-6 con multiplicidad en ColorLoto; denominador:
simulaciones), frecuencia simulada de alcanzar al menos 2, 3, 4 o 5 (y 6 en
ColorLoto), superbalota por separado (al menos una linea con la superbalota
del sorteo, y el maximo de principales entre las lineas que la aciertan),
diferencias emparejadas frente a la uniforme y medias descriptivas. Todas
son FRECUENCIAS SIMULADAS: cero apariciones en M simulaciones no significa
que el evento sea imposible.

CONTROLES EXACTOS (escenario de sorteos uniformes, numeros): distribucion
hipergeometrica de una combinacion, tamano del espacio de combinaciones y,
por enumeracion de TODOS los sorteos posibles, la distribucion exacta del
maximo de cada cartera (superbalota aparte, 1/16 por valor). Los eventos
raros se leen en esos valores exactos, no en un cero Monte Carlo.

REPRODUCCION: flujos PCG64 separados y versionados por escenario
(`SeedSequence([semilla, 5, 2, juego, escenario])`, un hijo para numeros o
pares y otro para la superbalota), distintos del flujo de construccion. Cada
variable aleatoria se genera en orden y los lotes solo reparten ese orden,
asi que el resultado no depende del tamano de lote (se registra igualmente).
No se guardan los sorteos sinteticos: solo resumenes y trazabilidad. La
simulacion no reentrena ningun modelo: usa el vector fuente congelado en la
cartera. Sin dinero, premios ni retorno.

Modulo puro.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from itertools import combinations

import numpy as np

from app.application.ml import carteras_construccion as cc
from app.application.ml import laboratorio_variables as lv

VERSION_SIMULACION = "producto5-simulacion-1"
SIMULACIONES_PREDETERMINADAS = 10_000
SIMULACIONES_MINIMAS = 1_000
SIMULACIONES_MAXIMAS = 50_000
TAMANO_DE_LOTE = 2_000
ESCENARIOS = ("sorteos_uniformes", "muestreo_ponderado")
SEMILLA_PREDETERMINADA = 42


class SimulacionNoValida(ValueError):
    pass


def validar(simulaciones, semilla) -> tuple[int, int]:
    if isinstance(simulaciones, bool) or not isinstance(simulaciones, int) or \
            not SIMULACIONES_MINIMAS <= simulaciones <= SIMULACIONES_MAXIMAS:
        raise SimulacionNoValida(f"las simulaciones deben estar entre {SIMULACIONES_MINIMAS} y {SIMULACIONES_MAXIMAS}")
    if isinstance(semilla, bool) or not isinstance(semilla, int) or not 0 <= semilla <= cc.SEMILLA_MAXIMA:
        raise SimulacionNoValida(f"la semilla debe ser un entero entre 0 y {cc.SEMILLA_MAXIMA}")
    return simulaciones, semilla


def supuestos(escenario: str, juego: str) -> dict:
    reglas = lv.REGLAS[juego]
    if escenario == "sorteos_uniformes":
        principal = ("6 extracciones uniformes con reemplazo sobre los pares de la paleta congelada del corte"
                     if reglas.colores else f"{reglas.cantidad} numeros uniformes sin reemplazo de "
                                            f"{reglas.rango[0]}..{reglas.rango[1]}")
        sb = "uniforme 1..16, independiente de los numeros" if reglas.superbalota else None
    else:
        principal = ("6 extracciones con reemplazo de la distribucion de pares del modelo fuente (suposicion "
                     "multinomial de Producto 2)" if reglas.colores else
                     "muestreo secuencial ponderado sin reemplazo con las marginales del modelo fuente como pesos; "
                     "es una hipotesis construida con pesos, no una distribucion conjunta aprendida")
        sb = ("estrategia separada de Producto 1 (frecuencia con suavizado de Laplace); independiente de los numeros "
              "por supuesto" if reglas.superbalota else None)
    salida = {"escenario": escenario, "numeros_o_pares": principal, "superbalota": sb}
    if escenario == "muestreo_ponderado":
        salida["advertencia"] = ("la cartera elegida se evalua con un mecanismo relacionado con el modelo que la "
                                 "construyo: una ventaja simulada no es una confirmacion independiente ni una "
                                 "probabilidad real de acertar un sorteo futuro")
    return salida


# ---------------------------------------------------------------------------
# Representacion de carteras
# ---------------------------------------------------------------------------

def _indices_de_cartera(combinaciones: list[dict], candidatos: list, colores: bool):
    """Numeros: matriz (C, 5) de indices; ColorLoto: conteos (C, P)."""
    if colores:
        indice = {tuple(c): j for j, c in enumerate(candidatos)}
        conteos = np.zeros((len(combinaciones), len(candidatos)), dtype=np.int8)
        for i, c in enumerate(combinaciones):
            for p in c["pares"]:
                conteos[i, indice[tuple(p)]] += 1
        return conteos
    indice = {c: j for j, c in enumerate(candidatos)}
    return np.array([[indice[n] for n in c["numeros"]] for c in combinaciones], dtype=np.int64)


def _aciertos(sorteos: np.ndarray, cartera: np.ndarray, n_candidatos: int, colores: bool) -> np.ndarray:
    """(B, C) aciertos de cada linea en cada sorteo (multiplicidad en ColorLoto)."""
    filas = sorteos.shape[0]
    if colores:
        conteos = np.zeros((filas, n_candidatos), dtype=np.int8)
        for j in range(sorteos.shape[1]):
            np.add.at(conteos, (np.arange(filas), sorteos[:, j]), 1)
        return np.minimum(conteos[:, None, :], cartera[None, :, :]).sum(axis=2).astype(np.int64)
    presentes = np.zeros((filas, n_candidatos), dtype=bool)
    presentes[np.arange(filas)[:, None], sorteos] = True
    return presentes[:, cartera].sum(axis=2).astype(np.int64)


class _Acumulador:
    def __init__(self, k_max: int, lineas: int, con_sb: bool):
        self.k_max = k_max
        self.por_combinacion = np.zeros(k_max + 1, dtype=np.int64)
        self.maximo = np.zeros(k_max + 1, dtype=np.int64)
        self.suma_maximo = 0
        self.lineas = lineas
        self.con_sb = con_sb
        self.sb_alguna = 0
        self.maximo_con_sb = np.zeros(k_max + 2, dtype=np.int64)  # ultimo: ninguna linea acierta la superbalota

    def sumar(self, aciertos: np.ndarray, sb_aciertos: np.ndarray | None) -> np.ndarray:
        self.por_combinacion += np.bincount(aciertos.ravel(), minlength=self.k_max + 1)
        maximo = aciertos.max(axis=1)
        self.maximo += np.bincount(maximo, minlength=self.k_max + 1)
        self.suma_maximo += int(maximo.sum())
        if sb_aciertos is not None:
            alguna = sb_aciertos.any(axis=1)
            self.sb_alguna += int(alguna.sum())
            enmascarado = np.where(sb_aciertos, aciertos, -1).max(axis=1)
            enmascarado = np.where(enmascarado < 0, self.k_max + 1, enmascarado)
            self.maximo_con_sb += np.bincount(enmascarado, minlength=self.k_max + 2)
        return maximo

    def resultado(self, simulaciones: int, umbrales: tuple[int, ...]) -> dict:
        salida = {
            "aciertos_por_combinacion": {"conteos": self.por_combinacion.tolist(),
                                         "denominador": simulaciones * self.lineas,
                                         "definicion": "aciertos de cada linea en cada sorteo simulado"},
            "maximo_de_la_cartera": {"conteos": self.maximo.tolist(), "denominador": simulaciones,
                                     "definicion": "mejor resultado de la cartera en cada sorteo simulado"},
            "al_menos": {str(t): {"conteo": int(self.maximo[t:].sum()), "denominador": simulaciones,
                                  "frecuencia_simulada": round(float(self.maximo[t:].sum()) / simulaciones, 6)}
                         for t in umbrales},
            "media_del_maximo": round(self.suma_maximo / simulaciones, 6),
            "media_de_aciertos_por_combinacion": round(
                float((self.por_combinacion * np.arange(self.k_max + 1)).sum()) / (simulaciones * self.lineas), 6)}
        if self.con_sb:
            salida["superbalota"] = {
                "definicion": ("al menos una linea con la superbalota del sorteo; y, entre las lineas que la "
                               "aciertan, el maximo de aciertos de numeros principales"),
                "al_menos_una_linea": {"conteo": self.sb_alguna, "denominador": simulaciones,
                                       "frecuencia_simulada": round(self.sb_alguna / simulaciones, 6)},
                "maximo_principal_entre_lineas_con_superbalota": {
                    "conteos": self.maximo_con_sb[:-1].tolist(), "sin_superbalota": int(self.maximo_con_sb[-1]),
                    "denominador": simulaciones}}
        return salida


def simular(juego: str, fuente: dict, elegida: list[dict], uniforme: list[dict], simulaciones: int, semilla: int,
            lote: int = TAMANO_DE_LOTE, avance: Callable[..., None] | None = None) -> dict:
    """Resultados de los dos escenarios para las dos carteras."""
    simulaciones, semilla = validar(simulaciones, semilla)
    if len(elegida) != len(uniforme):
        raise SimulacionNoValida("las dos carteras deben tener el mismo numero de combinaciones")
    avance = avance or (lambda *a, **k: None)
    reglas = lv.REGLAS[juego]
    colores = reglas.colores
    candidatos = [tuple(c) for c in fuente["candidatos"]] if colores else list(fuente["candidatos"])
    n = len(candidatos)
    k_max = reglas.cantidad
    umbrales = tuple(range(2, k_max + 1))
    carteras = {"elegida": elegida, "uniforme": uniforme}
    matrices = {k: _indices_de_cartera(v, candidatos, colores) for k, v in carteras.items()}
    sb_lineas = ({k: np.array([c["superbalota"] for c in v], dtype=np.int64) for k, v in carteras.items()}
                 if reglas.superbalota else None)
    pesos_modelo = cc.pesos_normalizados(fuente["probabilidades"])
    pesos_uniformes = np.full(n, 1.0 / n)
    if reglas.superbalota:
        sb_candidatos = np.array(fuente["superbalota"]["candidatos"], dtype=np.int64)
        sb_modelo = cc.pesos_normalizados(fuente["superbalota"]["probabilidades"])
        sb_uniforme = np.full(len(sb_candidatos), 1.0 / len(sb_candidatos))
    resultados = {}
    for e, escenario in enumerate(ESCENARIOS, start=1):
        rng, rng_sb = cc.flujos(semilla, cc.FLUJO_SIMULACION, juego, e)
        pesos = pesos_uniformes if escenario == "sorteos_uniformes" else pesos_modelo
        acumuladores = {k: _Acumulador(k_max, len(v), bool(reglas.superbalota)) for k, v in carteras.items()}
        emparejado = np.zeros((k_max + 1, k_max + 1), dtype=np.int64)
        hechas = 0
        while hechas < simulaciones:
            b = min(lote, simulaciones - hechas)
            if colores:
                sorteos = cc.muestrear_con_reemplazo(rng, pesos, reglas.cantidad, filas=b)
            else:
                sorteos = cc.muestrear_sin_reemplazo(rng, pesos, reglas.cantidad, filas=b)
            sb_sorteo = None
            if reglas.superbalota:
                p_sb = sb_uniforme if escenario == "sorteos_uniformes" else sb_modelo
                sb_sorteo = sb_candidatos[cc.muestrear_con_reemplazo(rng_sb, p_sb, 1, filas=b)[:, 0]]
            maximos = {}
            for k in carteras:
                aciertos = _aciertos(sorteos, matrices[k], n, colores)
                sb_aciertos = None if sb_sorteo is None else sb_sorteo[:, None] == sb_lineas[k][None, :]
                maximos[k] = acumuladores[k].sumar(aciertos, sb_aciertos)
            np.add.at(emparejado, (maximos["elegida"], maximos["uniforme"]), 1)
            hechas += b
            avance("lote", escenario=escenario, simulaciones=hechas, de=simulaciones)
        por_cartera = {k: a.resultado(simulaciones, umbrales) for k, a in acumuladores.items()}
        # filas = maximo de la elegida, columnas = maximo de la uniforme en el mismo sorteo
        elegida_mayor = int(np.tril(emparejado, -1).sum())
        uniforme_mayor = int(np.triu(emparejado, 1).sum())
        diferencia_media = (acumuladores["elegida"].suma_maximo - acumuladores["uniforme"].suma_maximo) / simulaciones
        resultados[escenario] = {
            "supuestos": supuestos(escenario, juego), "simulaciones_efectivas": simulaciones,
            "carteras": por_cartera,
            "emparejado": {
                "definicion": "maximo de la cartera elegida frente al de la uniforme en el MISMO sorteo simulado",
                "denominador": simulaciones,
                "elegida_mayor": elegida_mayor, "iguales": int(np.trace(emparejado)),
                "uniforme_mayor": uniforme_mayor,
                "diferencia_media_del_maximo": round(diferencia_media, 6),
                "tabla": emparejado.tolist(),
                "diferencia_en_al_menos": {
                    str(t): por_cartera["elegida"]["al_menos"][str(t)]["conteo"]
                    - por_cartera["uniforme"]["al_menos"][str(t)]["conteo"] for t in umbrales}}}
    return resultados


# ---------------------------------------------------------------------------
# Controles exactos (sorteos uniformes)
# ---------------------------------------------------------------------------

def hipergeometrica(n: int, k: int) -> list[float]:
    """P(aciertos = a) de UNA combinacion de k numeros frente a k extraidos
    uniformemente sin reemplazo de n."""
    total = math.comb(n, k)
    return [math.comb(k, a) * math.comb(n - k, k - a) / total for a in range(k + 1)]


if hasattr(np, "bitwise_count"):
    def _popcount(x: np.ndarray) -> np.ndarray:
        return np.bitwise_count(x).astype(np.int64)
else:  # pragma: no cover - NumPy < 2.0
    _TABLA = np.array([bin(i).count("1") for i in range(256)], dtype=np.int64)

    def _popcount(x: np.ndarray) -> np.ndarray:
        bytes_ = x.view(np.uint8).reshape(*x.shape, 8)
        return _TABLA[bytes_].sum(axis=-1)


def _todas_las_mascaras(n: int, k: int) -> np.ndarray:
    pesos = (np.uint64(1) << np.arange(n, dtype=np.uint64))
    indices = np.fromiter((i for c in combinations(range(n), k) for i in c), dtype=np.int64,
                          count=math.comb(n, k) * k).reshape(-1, k)
    return np.bitwise_or.reduce(pesos[indices], axis=1)


def maximo_exacto_uniforme(combinaciones: list[list[int]], n: int, k: int, mascaras: np.ndarray | None = None) -> dict:
    """Distribucion EXACTA del maximo de aciertos de una cartera de numeros
    frente a todos los sorteos posibles de k entre 1..n (enumeracion)."""
    mascaras = _todas_las_mascaras(n, k) if mascaras is None else mascaras
    maximo = np.zeros(len(mascaras), dtype=np.int64)
    for c in combinaciones:
        m = np.uint64(0)
        for numero in c:
            m |= np.uint64(1) << np.uint64(numero - 1)
        maximo = np.maximum(maximo, _popcount(mascaras & m))
    conteos = np.bincount(maximo, minlength=k + 1)
    total = len(mascaras)
    return {"espacio": total, "conteos": conteos.tolist(),
            "probabilidades": [float(c) / total for c in conteos],
            "al_menos": {str(t): float(conteos[t:].sum()) / total for t in range(2, k + 1)}}


def controles_exactos(juego: str, elegida: list[dict], uniforme: list[dict]) -> dict | None:
    """Solo numeros, bajo sorteos uniformes. ColorLoto no tiene control exacto
    en esta version (se dice asi)."""
    reglas = lv.REGLAS[juego]
    if reglas.colores:
        return {"disponible": False, "motivo": ("sin control exacto para ColorLoto en esta version: el espacio de "
                                                "multiconjuntos con probabilidades multinomiales no se enumera")}
    n = reglas.rango[1] - reglas.rango[0] + 1
    k = reglas.cantidad
    mascaras = _todas_las_mascaras(n, k)
    salida = {"disponible": True, "escenario": "sorteos_uniformes",
              "espacio_de_combinaciones": math.comb(n, k),
              "hipergeometrica_una_combinacion": {"probabilidades": hipergeometrica(n, k),
                                                  "definicion": f"aciertos de una combinacion de {k} frente a {k} "
                                                                f"extraidos uniformemente de {n}"},
              "maximo_exacto": {"elegida": maximo_exacto_uniforme([c["numeros"] for c in elegida], n, k, mascaras),
                                "uniforme": maximo_exacto_uniforme([c["numeros"] for c in uniforme], n, k, mascaras)}}
    if reglas.superbalota:
        valores = reglas.superbalota[1] - reglas.superbalota[0] + 1
        salida["espacio_con_superbalota"] = math.comb(n, k) * valores
        salida["superbalota"] = {"probabilidad_por_linea": 1 / valores,
                                 "al_menos_una_linea": {
                                     "elegida": len({c["superbalota"] for c in elegida}) / valores,
                                     "uniforme": len({c["superbalota"] for c in uniforme}) / valores},
                                 "definicion": "superbalota uniforme e independiente de los numeros"}
    return salida
