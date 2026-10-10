"""
Motor de correlaciones (Fase 5): Pearson, Spearman y chi-cuadrado de independencia.

Completa el componente «correlaciones (Chi cuadrado, Pearson, Spearman)» de la Fase 5 con tres
preguntas descriptivas, todas sobre el histórico ya cortado:

  - Correlación serial de la suma: ¿la suma de los números principales de un sorteo se parece a
    la del sorteo inmediatamente anterior? Pares (suma_anterior, suma_actual) solo en transiciones
    estrictas N -> N+1 (la misma regla de `repeticiones.py`: un hueco de numeración no se compara).
  - Estabilidad entre mitades: ¿los números más frecuentes en la primera mitad de la muestra lo son
    también en la segunda? Correlación de las apariciones por número entre las dos mitades
    (primera mitad = los floor(T/2) sorteos más antiguos).
  - ColorLoto, número x color: chi-cuadrado de independencia sobre la tabla de contingencia de
    balotas (cada balota cuenta, con multiplicidad), bajo el supuesto de balotas independientes.

Bajo un sorteo uniforme e independiente las dos correlaciones se esperan cercanas a 0 y el
chi-cuadrado sin estructura. Un coeficiente distinto de 0 o un p-value bajo en UNA muestra no indica
qué saldrá en el próximo sorteo; con varias pruebas a la vez, alguno saldrá bajo por azar. Nada de
este módulo es una señal predictiva.

Coeficientes y p-values son cosas distintas:
  - Los coeficientes de Pearson y Spearman (SciPy) son descriptivos y se publican siempre que se
    puedan calcular.
  - El p-value NO es el de SciPy: el de `spearmanr` es una aproximación para muestras grandes y el de
    `pearsonr` supone pares independientes y normales. Aquí la muestra de las mitades son 7, 39 o 43
    categorías (números), no los sorteos.
  - Estabilidad entre mitades: contraste de permutación bilateral. Bajo H0 (sorteos independientes
    entre sí y simétricos respecto de los números: ningún número tiene un papel distinto), el vector
    de apariciones de la segunda mitad es independiente del de la primera (sorteos distintos) y su
    distribución no cambia al reordenar los números (intercambiable). Condicionado a la primera mitad,
    todas las ordenaciones de la segunda son igual de probables, así que la distribución de
    permutación del coeficiente es su distribución nula. Con hasta `MAXIMO_PERMUTACION_EXACTA`
    categorías (ColorLoto, 7) se enumeran todas: p = (ordenaciones con |r| >= |r observado|) / n!.
    Con más (Baloto 43, MiLoto 39), Monte Carlo: B ordenaciones aleatorias y p = (1 + k) / (1 + B);
    la observada cuenta como una más, por lo que p nunca es 0 y, con ordenaciones aleatorias, P(p <= a)
    <= a bajo H0. La semilla fija (`SEMILLA_MONTE_CARLO`) lo hace reproducible a costa de usar siempre
    la misma realización; la desviación típica de Monte Carlo respecto del p exacto es <= 0,005.
  - Correlación serial: las transiciones N -> N+1 comparten sorteos (el N+1 de un par es el N del
    siguiente), así que los pares no son independientes. Ni el p-value de SciPy ni una permutación de
    pares están justificados para esa dependencia: no se publica p-value, solo el coeficiente.
  - Número x color: `chi2_contingency` da un p-value asintótico (no exacto para una muestra finita).

Un cálculo que no se puede hacer (menos de 3 pares, serie constante, tabla degenerada) devuelve
coeficiente y p-value None con su motivo, nunca 0.
"""
from __future__ import annotations

import functools
import itertools
import math
import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.frecuencia import (
    calcular_frecuencia_numeros,
    calcular_frecuencia_numeros_colorloto,
)
from app.application.estadisticas.motor.repeticiones import _transiciones_validas
from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico, ResultadoTestEstadistico

MINIMO_PARES = 3
"""Con menos de 3 pares un coeficiente no describe nada (con 2 puntos siempre vale +-1)."""
MAXIMO_PERMUTACION_EXACTA = 8
"""Hasta 8 pares se enumeran las n! ordenaciones (8! = 40 320); con más, Monte Carlo."""
PERMUTACIONES_MONTE_CARLO = 9999
SEMILLA_MONTE_CARLO = 5
TOLERANCIA = 1e-12
"""Margen al comparar |r| de una ordenación con el observado (errores de redondeo de coma flotante)."""
CONTRASTE_EXACTO = "permutacion_exacta"
CONTRASTE_MONTE_CARLO = "permutacion_monte_carlo"
SIN_COEFICIENTE = "sin coeficiente no hay p-value"
MOTIVO_SERIAL_SIN_P_VALUE = "las transiciones N → N+1 comparten sorteos: los pares no son independientes"
"""Detalle en la docstring del módulo: ni el p-value de SciPy ni una permutación de pares están justificados."""


@dataclass(frozen=True)
class Correlacion:
    metodo: str  # "pearson" | "spearman"
    coeficiente: float | None  # descriptivo (SciPy)
    p_value: float | None  # bilateral, H0: coeficiente = 0; None si no hay un contraste justificado
    n: int  # pares usados
    motivo: str | None = None  # por qué no hay coeficiente; None si se calculó
    contraste: str | None = None  # CONTRASTE_EXACTO | CONTRASTE_MONTE_CARLO | None (sin p-value)
    permutaciones: int | None = None  # ordenaciones evaluadas: n! (exacta) o B (Monte Carlo)
    motivo_p_value: str | None = None  # cómo se obtuvo el p-value y sus límites, o por qué no hay


@dataclass(frozen=True)
class CorrelacionSerialSumas:
    total_sorteos: int
    transiciones: int  # pares N -> N+1 usados
    excluidas_por_hueco: int  # sorteos consecutivos en la lista cuya numeración no es consecutiva
    pearson: Correlacion
    spearman: Correlacion


@dataclass(frozen=True)
class EstabilidadEntreMitades:
    total_sorteos: int
    sorteos_primera: int
    sorteos_segunda: int
    primera: tuple[int, int] | None  # (primer, último numero_sorteo) de la primera mitad
    segunda: tuple[int, int] | None
    categorias: int
    pearson: Correlacion
    spearman: Correlacion


@dataclass(frozen=True)
class IndependenciaNumeroColor:
    total_sorteos: int
    total_balotas: int
    numeros: tuple[str, ...]  # filas usadas (sin las que no tienen ninguna balota)
    colores: tuple[str, ...]  # columnas usadas
    observado: tuple[tuple[int, ...], ...]
    esperado: tuple[tuple[float, ...], ...]
    esperado_minimo: float | None
    excluidos: tuple[str, ...]  # números o colores sin ninguna balota en la muestra
    resultado: ResultadoTestEstadistico | None
    motivo: str | None = None


@functools.lru_cache(maxsize=8)
def ordenaciones_monte_carlo(n: int, cantidad: int, semilla: int = SEMILLA_MONTE_CARLO) -> np.ndarray:
    """`cantidad` ordenaciones aleatorias de range(n), una por fila (solo lectura).

    Fisher-Yates con `random.Random(semilla).random()`: Python garantiza la misma secuencia de
    `random()` para la misma semilla entre versiones, y el generador de NumPy no garantiza su flujo
    entre versiones. Mismas entradas, mismo p-value en Linux y en Windows. (`int(random() * (i + 1))`
    tiene un sesgo menor que 2**-53 por elección, despreciable frente al error de Monte Carlo.)"""
    rng = random.Random(semilla)
    filas = []
    for _ in range(cantidad):
        indices = list(range(n))
        for i in range(n - 1, 0, -1):
            j = int(rng.random() * (i + 1))
            indices[i], indices[j] = indices[j], indices[i]
        filas.append(indices)
    ordenaciones = np.array(filas, dtype=np.intp).reshape(cantidad, n)
    ordenaciones.setflags(write=False)
    return ordenaciones


@functools.lru_cache(maxsize=MAXIMO_PERMUTACION_EXACTA + 1)
def _todas_las_ordenaciones(n: int) -> np.ndarray:
    ordenaciones = np.array(list(itertools.permutations(range(n))), dtype=np.intp).reshape(-1, n)
    ordenaciones.setflags(write=False)
    return ordenaciones


def _extremos(a: np.ndarray, b: np.ndarray, ordenaciones: np.ndarray) -> int:
    """Ordenaciones de `b` con |r| frente a `a` >= |r observado| (con la observada, si está entre ellas).
    r de Pearson sobre las series dadas (valores para Pearson, rangos promedio para Spearman)."""
    a = a - a.mean()
    b = b - b.mean()
    escala = math.sqrt(float(a @ a) * float(b @ b))
    observado = abs(float(a @ b)) / escala
    nulos = np.abs(b[ordenaciones] @ a) / escala
    return int(np.count_nonzero(nulos >= observado - TOLERANCIA))


def correlacionar(
    x: Sequence[float], y: Sequence[float], *, motivo_sin_p_value: str | None = None,
    maximo_exacto: int = MAXIMO_PERMUTACION_EXACTA, permutaciones: int = PERMUTACIONES_MONTE_CARLO,
    semilla: int = SEMILLA_MONTE_CARLO,
) -> tuple[Correlacion, Correlacion]:
    """Pearson y Spearman de dos series del mismo largo: coeficiente descriptivo de SciPy y p-value
    bilateral por permutación de `y` frente a `x` (exacta con n <= `maximo_exacto`; si no, Monte Carlo
    con `permutaciones` ordenaciones y `semilla`). Las mismas ordenaciones sirven a los dos métodos.

    El contraste supone que, bajo H0, `y` es intercambiable e independiente de `x`: quien llama debe
    poder justificarlo. Si no puede (pares dependientes), pasa `motivo_sin_p_value` y solo se
    calculan los coeficientes."""
    if len(x) != len(y):
        raise ValueError(f"correlacionar: series de largo distinto ({len(x)} y {len(y)})")
    n = len(x)
    motivo = None
    if n < MINIMO_PARES:
        motivo = f"se necesitan al menos {MINIMO_PARES} pares y hay {n}"
    elif len(set(x)) < 2 or len(set(y)) < 2:
        motivo = "una de las series es constante: la correlación no está definida"
    if motivo:
        return tuple(Correlacion(m, None, None, n, motivo, motivo_p_value=SIN_COEFICIENTE)
                     for m in ("pearson", "spearman"))
    coeficientes = (float(stats.pearsonr(x, y).statistic), float(stats.spearmanr(x, y).statistic))
    if motivo_sin_p_value:
        return tuple(Correlacion(m, c, None, n, motivo_p_value=motivo_sin_p_value)
                     for m, c in zip(("pearson", "spearman"), coeficientes))
    if n <= maximo_exacto:
        ordenaciones, contraste = _todas_las_ordenaciones(n), CONTRASTE_EXACTO
        total = len(ordenaciones)
        como = (f"permutación exacta: se enumeran las {n}! = {total} ordenaciones de una serie frente a la otra; "
                "supone que, bajo H0, todas son igual de probables")
    else:
        ordenaciones, contraste = ordenaciones_monte_carlo(n, permutaciones, semilla), CONTRASTE_MONTE_CARLO
        total = permutaciones
        como = (f"permutación Monte Carlo: {permutaciones} ordenaciones aleatorias con semilla fija {semilla} "
                f"(reproducible); p = (1 + k)/(1 + {permutaciones}), con k las ordenaciones al menos tan extremas; "
                "aproxima el p exacto de permutación con desviación típica <= 0,005 y supone que, bajo H0, "
                "todas las ordenaciones son igual de probables")
    series = ((np.asarray(x, dtype=float), np.asarray(y, dtype=float)),
              (stats.rankdata(x), stats.rankdata(y)))
    resultado = []
    for metodo, coeficiente, (a, b) in zip(("pearson", "spearman"), coeficientes, series):
        k = _extremos(a, b, ordenaciones)
        p = k / total if contraste == CONTRASTE_EXACTO else (1 + k) / (1 + total)
        resultado.append(Correlacion(metodo, coeficiente, p, n, contraste=contraste,
                                     permutaciones=total, motivo_p_value=como))
    return tuple(resultado)


def _serial(historico: Sequence, suma: Callable[[object], int]) -> CorrelacionSerialSumas:
    ordenados = sorted(historico, key=lambda r: r.numero_sorteo)
    transiciones = _transiciones_validas(ordenados)
    pearson, spearman = correlacionar([suma(a) for a, _ in transiciones], [suma(b) for _, b in transiciones],
                                      motivo_sin_p_value=MOTIVO_SERIAL_SIN_P_VALUE)
    return CorrelacionSerialSumas(total_sorteos=len(ordenados), transiciones=len(transiciones),
                                  excluidas_por_hueco=max(0, len(ordenados) - 1 - len(transiciones)),
                                  pearson=pearson, spearman=spearman)


def calcular_correlacion_serial_sumas(
    resultados: Sequence[ResultadoNumerico], hasta_numero_sorteo: int | None = None,
) -> CorrelacionSerialSumas:
    """Suma de los números principales (nunca la superbalota) del sorteo N frente al N+1."""
    return _serial(filtrar_por_corte_temporal(resultados, hasta_numero_sorteo), lambda r: sum(r.numeros))


def calcular_correlacion_serial_sumas_colorloto(
    resultados: Sequence[ResultadoColorLoto], hasta_numero_sorteo: int | None = None,
) -> CorrelacionSerialSumas:
    """Suma de los 6 números de ColorLoto (con repetición, ignorando el color) del sorteo N frente al N+1."""
    return _serial(filtrar_por_corte_temporal(resultados, hasta_numero_sorteo),
                   lambda r: sum(n for n, _ in r.pares))


def _mitades(historico: Sequence, frecuencias: Callable[[Sequence], list]) -> EstabilidadEntreMitades:
    ordenados = sorted(historico, key=lambda r: r.numero_sorteo)
    mitad = len(ordenados) // 2
    primera, segunda = ordenados[:mitad], ordenados[mitad:]
    f1, f2 = frecuencias(primera), frecuencias(segunda)
    if [f.valor for f in f1] != [f.valor for f in f2]:
        raise ValueError("_mitades: las dos mitades no tienen las mismas categorías")
    if not primera:
        motivo = "se necesitan sorteos en las dos mitades de la muestra"
        pearson = Correlacion("pearson", None, None, len(f1), motivo, motivo_p_value=SIN_COEFICIENTE)
        spearman = Correlacion("spearman", None, None, len(f1), motivo, motivo_p_value=SIN_COEFICIENTE)
    else:
        pearson, spearman = correlacionar([f.apariciones for f in f1], [f.apariciones for f in f2])
    rango = (lambda parte: (parte[0].numero_sorteo, parte[-1].numero_sorteo) if parte else None)
    return EstabilidadEntreMitades(total_sorteos=len(ordenados), sorteos_primera=len(primera),
                                   sorteos_segunda=len(segunda), primera=rango(primera), segunda=rango(segunda),
                                   categorias=len(f1), pearson=pearson, spearman=spearman)


def calcular_estabilidad_frecuencia_numeros(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> EstabilidadEntreMitades:
    """Apariciones de cada número de [rango_min, rango_max] en la primera mitad frente a la segunda
    (reutiliza calcular_frecuencia_numeros en cada mitad). La muestra del p-value son los números
    (categorías), no los sorteos: permutación exacta o Monte Carlo según `correlacionar`."""
    return _mitades(filtrar_por_corte_temporal(resultados, hasta_numero_sorteo),
                    lambda parte: calcular_frecuencia_numeros(parte, rango_min, rango_max))


def calcular_estabilidad_frecuencia_numeros_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int,
    hasta_numero_sorteo: int | None = None,
) -> EstabilidadEntreMitades:
    """Igual que la numérica, con las balotas de ColorLoto (cada balota cuenta)."""
    return _mitades(filtrar_por_corte_temporal(resultados, hasta_numero_sorteo),
                    lambda parte: calcular_frecuencia_numeros_colorloto(parte, rango_min, rango_max))


def calcular_independencia_numero_color(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int, colores: Sequence[str],
    hasta_numero_sorteo: int | None = None,
) -> IndependenciaNumeroColor:
    """Chi-cuadrado de independencia (SciPy `chi2_contingency`, sin corrección de Yates) entre el
    número y el color de cada balota; el p-value es asintótico (distribución chi-cuadrado límite), no
    exacto para una muestra finita, y poco fiable si alguna celda espera menos de 5 balotas. Filas: números de [rango_min, rango_max]; columnas: `colores`
    más los observados fuera de esa lista. Un número o color sin ninguna balota en la muestra se
    excluye (su frecuencia esperada sería 0) y se informa en `excluidos`."""
    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    balotas = [(n, c) for r in historico for n, c in r.pares]
    fuera = sorted({n for n, _ in balotas if not (rango_min <= n <= rango_max)})
    if fuera:
        raise ValueError(f"calcular_independencia_numero_color: números fuera de [{rango_min},{rango_max}]: {fuera}")
    todos_colores = list(colores) + sorted({c for _, c in balotas} - set(colores))
    conteo = Counter(balotas)
    filas_n = [n for n in range(rango_min, rango_max + 1) if any(conteo[(n, c)] for c in todos_colores)]
    cols_c = [c for c in todos_colores if any(conteo[(n, c)] for n in range(rango_min, rango_max + 1))]
    excluidos = tuple([str(n) for n in range(rango_min, rango_max + 1) if n not in filas_n]
                      + [c for c in todos_colores if c not in cols_c])
    observado = tuple(tuple(conteo[(n, c)] for c in cols_c) for n in filas_n)
    base = dict(total_sorteos=len(historico), total_balotas=len(balotas), numeros=tuple(str(n) for n in filas_n),
                colores=tuple(cols_c), observado=observado, excluidos=excluidos)
    if len(filas_n) < 2 or len(cols_c) < 2:
        return IndependenciaNumeroColor(**base, esperado=(), esperado_minimo=None, resultado=None,
                                        motivo="se necesitan al menos 2 números y 2 colores con balotas")
    prueba = stats.chi2_contingency(observado, correction=False)
    esperado = tuple(tuple(float(v) for v in fila) for fila in prueba.expected_freq)
    resultado = ResultadoTestEstadistico(
        nombre_test="chi2_independencia", elementos=("numero", "color"), estadistico=float(prueba.statistic),
        grados_libertad=int(prueba.dof), p_value=float(prueba.pvalue), p_value_ajustado=None,
        metodo_correccion=None, alpha=None, significativo=None)
    return IndependenciaNumeroColor(**base, esperado=esperado, esperado_minimo=min(v for f in esperado for v in f),
                                    resultado=resultado)
