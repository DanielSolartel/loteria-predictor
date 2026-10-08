"""
Producto 5 -construccion de carteras de combinaciones.

UNA CARTERA es un conjunto ORDENADO de combinaciones validas para un mismo
juego, corte, objetivo y receta. No es un resultado real del sorteo ni una
lista de numeros garantizados.

REGLAS DEL DOMINIO (las de `laboratorio_variables.REGLAS`):
- Baloto y Revancha: 5 numeros distintos de 1 a 43 y una superbalota de 1 a
  16 por combinacion. La identidad de la combinacion incluye la superbalota;
  ademas se informa si dos lineas repiten los cinco numeros principales.
- MiLoto: 5 numeros distintos de 1 a 39, sin superbalota.
- ColorLoto: 6 pares numero-color de la paleta del corte, con repeticion
  (multiconjunto). Repetir un par dentro de una combinacion es valido;
  repetir la combinacion completa en la cartera no.
Numeros y multiconjuntos se canonizan (ordenados) para detectar duplicados.

PARAMETROS: cantidad 1-20 (por defecto 5), semilla (por defecto 42) y
diversidad `libre` (solo sin duplicados completos) o `limitada`: dos
combinaciones numericas comparten como maximo `LIMITE_NUMEROS_COMPARTIDOS`
(3) numeros principales; dos de ColorLoto, como maximo
`LIMITE_COINCIDENCIAS_COLORLOTO` (4) coincidencias con multiplicidad. La
superbalota no cuenta para ese limite.

CONSTRUCCION (determinista para la misma entrada):
1. la primera combinacion es la sugerencia principal del modelo cuando la
   tiene (5 numeros de mayor marginal con desempate por numero y la
   superbalota mas probable; en ColorLoto el multiconjunto mas probable). La
   referencia uniforme no tiene sugerencia, ni un vector fuente constante
   (p. ej. el modelo combinado con peso 1 para la uniforme): sus empates se
   romperian por numero y la «sugerencia» seria 1-2-3-4-5. Entonces todas las
   lineas se muestrean;
2. las demas se muestrean con generadores LOCALES (PCG64 a partir de
   `SeedSequence([semilla, 5, 1, juego])`, con un flujo hijo para los numeros
   o pares y otro para la superbalota). No se toca el estado aleatorio
   global;
   - numeros: muestreo secuencial ponderado sin reemplazo con las marginales
     normalizadas como pesos (claves de Gumbel: los 5 mayores de
     log(peso) + Gumbel). ESTE MECANISMO NO CONSERVA las marginales originales
     como probabilidades de inclusion de la muestra ni identifica la
     distribucion conjunta real del juego: es una regla de construccion;
   - ColorLoto: 6 extracciones con reemplazo de la distribucion de pares
     (contrato multinomial de Producto 2);
   - superbalota: extraccion de la estrategia separada de Producto 1;
3. cada candidato se acepta en orden si no repite una combinacion completa y
   cumple la diversidad pedida frente a TODAS las ya aceptadas;
4. presupuesto fijo de `PRESUPUESTO_DE_INTENTOS` candidatos. Si se agota, la
   cartera queda PARCIAL (solicitadas, obtenidas e intentos): no se relaja la
   diversidad ni se completan huecos con duplicados.

DIVERSIDAD es una propiedad de construccion, no una mejora predictiva. Las
metricas de cartera (cobertura, frecuencia de uso y coincidencias entre
lineas) describen la cartera; no se multiplican marginales para presentar
una probabilidad del premio mayor.

Modulo puro.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from itertools import combinations

import numpy as np

from app.application.ml import laboratorio_variables as lv
from app.application.ml import pronostico_colorloto as pcl

VERSION_CONSTRUCCION = "producto5-cartera-1"
ALGORITMO_RNG = "numpy PCG64 con SeedSequence([semilla, 5, flujo, juego]); hijos 0 = numeros/pares, 1 = superbalota"
FLUJO_CONSTRUCCION = 1
FLUJO_SIMULACION = 2
JUEGO_INDICE = {"BALOTO": 1, "BALOTO_REVANCHA": 2, "MILOTO": 3, "COLORLOTO": 4}
CANTIDAD_PREDETERMINADA = 5
CANTIDAD_MAXIMA = 20
SEMILLA_PREDETERMINADA = 42
SEMILLA_MAXIMA = 2**32 - 1
DIVERSIDADES = ("libre", "limitada")
LIMITE_NUMEROS_COMPARTIDOS = 3
LIMITE_COINCIDENCIAS_COLORLOTO = 4
PRESUPUESTO_DE_INTENTOS = 5000


class ParametrosNoValidos(ValueError):
    pass


def validar_parametros(cantidad, semilla, diversidad) -> tuple[int, int, str]:
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or not 1 <= cantidad <= CANTIDAD_MAXIMA:
        raise ParametrosNoValidos(f"la cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}")
    if isinstance(semilla, bool) or not isinstance(semilla, int) or not 0 <= semilla <= SEMILLA_MAXIMA:
        raise ParametrosNoValidos(f"la semilla debe ser un entero entre 0 y {SEMILLA_MAXIMA}")
    if diversidad not in DIVERSIDADES:
        raise ParametrosNoValidos(f"diversidad admitida: {', '.join(DIVERSIDADES)}")
    return cantidad, semilla, diversidad


def flujos(semilla: int, flujo: int, juego: str, escenario: int = 0) -> tuple[np.random.Generator, np.random.Generator]:
    """Dos generadores locales e independientes (numeros/pares y superbalota).
    `escenario` separa los flujos de simulacion de cada escenario."""
    raiz = np.random.SeedSequence([semilla, 5, flujo, JUEGO_INDICE[juego], escenario])
    principal, superbalota = raiz.spawn(2)
    return np.random.Generator(np.random.PCG64(principal)), np.random.Generator(np.random.PCG64(superbalota))


def pesos_normalizados(probabilidades: Sequence[float]) -> np.ndarray:
    p = np.asarray(probabilidades, dtype=float)
    if p.ndim != 1 or not np.all(np.isfinite(p)) or np.any(p <= 0):
        raise ParametrosNoValidos("el vector fuente debe ser finito y positivo")
    return p / p.sum()


def muestrear_sin_reemplazo(rng: np.random.Generator, pesos: np.ndarray, k: int, filas: int | None = None) -> np.ndarray:
    """Indices de `k` elementos por fila: muestreo secuencial ponderado sin
    reemplazo (claves de Gumbel). Consume exactamente `filas * len(pesos)`
    variables de Gumbel, en orden, asi que el resultado no depende de como se
    reparta en lotes."""
    tamano = (len(pesos),) if filas is None else (filas, len(pesos))
    claves = np.log(pesos) + rng.gumbel(size=tamano)
    orden = np.argsort(-claves, axis=-1, kind="stable")
    return orden[..., :k]


def muestrear_con_reemplazo(rng: np.random.Generator, pesos: np.ndarray, k: int, filas: int | None = None) -> np.ndarray:
    """Indices de `k` extracciones con reemplazo por fila (multinomial)."""
    tamano = k if filas is None else (filas, k)
    return rng.choice(len(pesos), size=tamano, replace=True, p=pesos)


def compartidos(a, b, colores: bool) -> int:
    """Numeros principales compartidos (sin superbalota) o coincidencias con
    multiplicidad de pares."""
    if colores:
        return pcl.coincidencias(a["pares"], b["pares"])
    return len(set(a["numeros"]) & set(b["numeros"]))


def identidad_de_combinacion(c: dict, colores: bool) -> tuple:
    if colores:
        return tuple(sorted(tuple(p) for p in c["pares"]))
    return (tuple(sorted(c["numeros"])), c.get("superbalota"))


def fuente_informativa(fuente: dict) -> bool:
    """Falso si todas las probabilidades del vector fuente son iguales: no hay
    sugerencia que no dependa del desempate por numero."""
    p = np.asarray(fuente["probabilidades"], dtype=float)
    return bool(np.ptp(p) > 1e-12)


def sugerencia(fuente: dict, reglas: lv.ReglasDelJuego) -> dict:
    """Sugerencia principal del modelo (la misma regla que Producto 4)."""
    if reglas.colores:
        dist = {tuple(c): p for c, p in zip(fuente["candidatos"], fuente["probabilidades"])}
        return {"pares": [list(p) for p in pcl.multiconjunto_mas_probable(dist)]}
    marginal = dict(zip(fuente["candidatos"], fuente["probabilidades"]))
    orden = sorted(marginal, key=lambda c: (-marginal[c], c))
    salida = {"numeros": sorted(orden[:reglas.cantidad])}
    if reglas.superbalota:
        sb = dict(zip(fuente["superbalota"]["candidatos"], fuente["superbalota"]["probabilidades"]))
        salida["superbalota"] = min(sb, key=lambda c: (-sb[c], c))
    return salida


def construir(fuente: dict, juego: str, *, con_sugerencia: bool, cantidad: int, semilla: int,
              diversidad: str) -> dict:
    """Combinaciones de la cartera en orden de aceptacion, con su estado."""
    cantidad, semilla, diversidad = validar_parametros(cantidad, semilla, diversidad)
    reglas = lv.REGLAS[juego]
    colores = reglas.colores
    limite = LIMITE_COINCIDENCIAS_COLORLOTO if colores else LIMITE_NUMEROS_COMPARTIDOS
    pesos = pesos_normalizados(fuente["probabilidades"])
    candidatos = [tuple(c) for c in fuente["candidatos"]] if colores else list(fuente["candidatos"])
    if reglas.superbalota:
        sb_candidatos = list(fuente["superbalota"]["candidatos"])
        sb_pesos = pesos_normalizados(fuente["superbalota"]["probabilidades"])
    rng, rng_sb = flujos(semilla, FLUJO_CONSTRUCCION, juego)
    aceptadas: list[dict] = []
    vistas: set = set()
    rechazos = Counter()
    intentos = 0

    def admitir(c: dict, origen: str) -> bool:
        identidad = identidad_de_combinacion(c, colores)
        if identidad in vistas:
            rechazos["duplicada"] += 1
            return False
        if diversidad == "limitada" and any(compartidos(c, a, colores) > limite for a in aceptadas):
            rechazos["diversidad"] += 1
            return False
        vistas.add(identidad)
        aceptadas.append({"linea": len(aceptadas) + 1, **c, "origen": origen})
        return True

    if con_sugerencia:
        admitir(sugerencia(fuente, reglas), "sugerencia_del_modelo")
    while len(aceptadas) < cantidad and intentos < PRESUPUESTO_DE_INTENTOS:
        intentos += 1
        if colores:
            indices = muestrear_con_reemplazo(rng, pesos, reglas.cantidad)
            candidata = {"pares": sorted([list(candidatos[i]) for i in indices])}
        else:
            indices = muestrear_sin_reemplazo(rng, pesos, reglas.cantidad)
            candidata = {"numeros": sorted(int(candidatos[i]) for i in indices)}
            if reglas.superbalota:
                candidata["superbalota"] = int(sb_candidatos[int(muestrear_con_reemplazo(rng_sb, sb_pesos, 1)[0])])
        admitir(candidata, "muestreo_ponderado")
    estado = "completa" if len(aceptadas) == cantidad else "parcial"
    salida = {"estado": estado, "solicitadas": cantidad, "obtenidas": len(aceptadas), "intentos": intentos,
              "presupuesto_de_intentos": PRESUPUESTO_DE_INTENTOS, "rechazos": dict(sorted(rechazos.items())),
              "combinaciones": aceptadas}
    if estado == "parcial":
        salida["motivo"] = (f"se agoto el presupuesto de {PRESUPUESTO_DE_INTENTOS} intentos con {len(aceptadas)} de "
                            f"{cantidad} combinaciones que cumplen la diversidad {diversidad}; no se relajo la "
                            "restriccion ni se completo con duplicados")
    return salida


def metricas_de_cartera(combinaciones: list[dict], juego: str, fuente: dict) -> dict:
    """Cobertura, frecuencia de uso y coincidencias entre lineas."""
    reglas = lv.REGLAS[juego]
    colores = reglas.colores
    if colores:
        dominio = [tuple(c) for c in fuente["candidatos"]]
        uso = Counter(tuple(p) for c in combinaciones for p in c["pares"])
        presencia = Counter(tuple(p) for c in combinaciones for p in {tuple(x) for x in c["pares"]})
        claves = sorted(uso)
        frecuencia = [{"par": list(k), "apariciones": uso[k], "lineas": presencia[k]} for k in claves]
        cubiertos = len(uso)
    else:
        dominio = list(reglas.candidatos)
        uso = Counter(n for c in combinaciones for n in c["numeros"])
        frecuencia = [{"numero": n, "lineas": uso[n]} for n in sorted(uso)]
        cubiertos = len(uso)
    pares_de_lineas = []
    for a, b in combinations(combinaciones, 2):
        pares_de_lineas.append({"lineas": [a["linea"], b["linea"]], "compartidos": compartidos(a, b, colores)})
    valores = [p["compartidos"] for p in pares_de_lineas]
    salida = {"cobertura": {"cubiertos": cubiertos, "dominio": len(dominio),
                            "fraccion": round(cubiertos / len(dominio), 6),
                            "unidad": "pares numero-color de la paleta" if colores else "numeros principales"},
              "frecuencia_de_uso": frecuencia,
              "coincidencias_entre_lineas": {
                  "definicion": ("coincidencias con multiplicidad de pares" if colores else
                                 "numeros principales compartidos (la superbalota no cuenta)"),
                  "pares_de_lineas": pares_de_lineas,
                  "maximo": max(valores) if valores else None, "minimo": min(valores) if valores else None,
                  "media": round(sum(valores) / len(valores), 6) if valores else None}}
    if colores:
        salida["repeticiones_dentro_de_lineas"] = [
            {"linea": c["linea"],
             "pares_repetidos": [list(p) for p, m in sorted(Counter(tuple(x) for x in c["pares"]).items()) if m > 1]}
            for c in combinaciones if len({tuple(x) for x in c["pares"]}) < len(c["pares"])]
    if reglas.superbalota:
        grupos: dict = {}
        for c in combinaciones:
            grupos.setdefault(tuple(c["numeros"]), []).append(c["linea"])
        salida["lineas_que_repiten_los_cinco_principales"] = [g for g in grupos.values() if len(g) > 1]
        salida["frecuencia_de_superbalota"] = [{"superbalota": s, "lineas": m} for s, m in
                                               sorted(Counter(c["superbalota"] for c in combinaciones).items())]
    return salida


NOTA_CONSTRUCCION = ("Muestreo secuencial ponderado sin reemplazo (numeros) o multinomial con reemplazo (ColorLoto) "
                     "a partir del vector fuente: es una regla de construccion. No conserva las marginales como "
                     "probabilidades de inclusion ni identifica la distribucion conjunta real del juego. La "
                     "diversidad es una propiedad de construccion, no una mejora predictiva.")
