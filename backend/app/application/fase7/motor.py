"""Fase 7 -simulador Monte Carlo bajo el mecanismo uniforme de cada juego.

Pregunta, por juego y corte: ¿son compatibles unas pocas estadisticas
descriptivas, fijadas de antemano, con su distribucion cuando los sorteos
se generan con el mecanismo uniforme del juego? Es una comparacion
EXPLORATORIA: no es confirmatoria, no es evidencia prospectiva ni
predictiva, no genera combinaciones ni recomendaciones y no modifica el
NO-GO de AE-39 ni `AUTORIZA_EVALUACION = False`.

MECANISMO (reglas de `laboratorio_variables.REGLAS`):
- BALOTO y BALOTO_REVANCHA: 5 numeros distintos de 1..43 y superbalota
  1..16 aparte, independiente de los numeros.
- MILOTO: 5 numeros distintos de 1..39, sin superbalota.
- COLORLOTO: 6 balotas, cada una un par (numero 1..7, color de la paleta
  del corte) extraido uniformemente CON reemplazo: los pares pueden
  repetirse y se cuentan con multiplicidad (supuesto multinomial de
  Productos 2 y 5; el dominio documenta que el reglamento debe
  confirmarlo).
Cada historico simulado conserva la numeracion observada (huecos
incluidos), asi que las transiciones estrictas N->N+1 son las mismas.

ESTADISTICAS (`FAMILIAS`): fijadas en el diseno de la Fase 7 antes de
observar ningun resultado, cada una con su patron del motor de Fase 5 y
su media analitica exacta bajo el mecanismo. Son ENTERAS sobre un
denominador que solo depende de la numeracion, identico en lo observado y
en cada simulacion: las comparaciones (>=, <=) son exactas. Lo observado
se calcula con las funciones del motor de Fase 5 y se contrasta, en cada
ejecucion, con la version vectorizada que usan las simulaciones.

GENERADOR Y DETERMINISMO: `PCG64(SeedSequence([semilla, 7, juego]))`.
Cada iteracion consume exactamente `H * (k + s)` dobles de `random()` en
orden (H sorteos, k numeros o balotas, s = 1 con superbalota), asi que el
resultado NO depende del tamano de lote: los lotes solo reparten esa
secuencia. Seleccion sin reemplazo: el t-esimo indice es
`floor(u * (n - t))` entre los restantes (la semantica de Fisher-Yates de
AE-49); sesgo <= n / 2**53 por la conversion de dobles, documentado. La
identidad de bytes se garantiza para la misma version de NumPy (se registra
en la identidad); entre versiones se comprueba, no se supone.

P-VALORES: bilateral empirico con correccion +1, nunca 0:
p = min(1, 2 * min(p_sup, p_inf)), p_sup = (1 + #{sim >= obs}) / (1 + B),
p_inf = (1 + #{sim <= obs}) / (1 + B). Bonferroni (funcion del motor) UNA
vez sobre las comparaciones de ESE juego y esa ejecucion; no corrige otros
juegos, cortes ni ejecuciones. Con B = 100 el p minimo (2/101) ajustado no
puede bajar de 0,05: se informa como `umbral_alcanzable = false`.

MEMORIA: acumulacion en flujo (conteos, sumas y sumas de cuadrados
enteras exactas); nunca se guardan todas las replicas. Cada lote reserva
como mucho `DOBLES_POR_LOTE` uniformes y sus derivados.

Modulo puro: sin SQLAlchemy, sin red y sin escrituras."""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import product

import numpy as np

from app.application.estadisticas.motor.consecutivos import calcular_distribucion_pares_consecutivos
from app.application.estadisticas.motor.distribuciones import (
    calcular_distribucion_sumas,
    calcular_maximo_repeticion_color_por_sorteo,
)
from app.application.estadisticas.motor.frecuencia import (
    calcular_frecuencia_colores,
    calcular_frecuencia_numeros,
    calcular_frecuencia_numeros_colorloto,
    calcular_frecuencia_pares_numero_color,
    calcular_frecuencia_superbalota,
)
from app.application.estadisticas.motor.repeticiones import (
    calcular_repeticiones_entre_sorteos,
    calcular_repeticiones_entre_sorteos_colorloto,
)
from app.application.estadisticas.motor.tests_estadisticos import aplicar_correccion_bonferroni
from app.application.estadisticas.tipos import ResultadoTestEstadistico
from app.application.ml import laboratorio_variables as lv

VERSION_MOTOR = "fase7-simulacion-1"
ITERACIONES_ADMITIDAS = (100, 1_000, 10_000, 100_000, 1_000_000)
ITERACIONES_PREDETERMINADAS = 10_000
SEMILLA_PREDETERMINADA = 20261023
SEMILLA_MAXIMA = 2**32 - 1
ALPHA = 0.05
FLUJO_FASE7 = 7
JUEGO_INDICE = {"BALOTO": 1, "BALOTO_REVANCHA": 2, "MILOTO": 3, "COLORLOTO": 4}
DOBLES_POR_LOTE = 2_000_000
"""Limite de uniformes por lote (~16 MB); el lote efectivo se registra pero
no forma parte de la identidad porque no cambia el resultado."""
GENERADOR = "numpy.random.PCG64"
ALGORITMO_SELECCION = "seleccion-secuencial-floor-u-por-restantes-v1"
NOTA = ("Comparacion exploratoria de estadisticas descriptivas fijadas de antemano con su distribucion bajo el "
        "mecanismo uniforme del juego. No es confirmatoria, no es evidencia prospectiva ni predictiva, no genera "
        "combinaciones ni recomendaciones y no modifica el NO-GO de AE-39.")
COBERTURA_AJUSTE = ("Bonferroni cubre solo las comparaciones de este juego en esta ejecucion; no corrige otros juegos, "
                    "cortes, semillas ni ejecuciones, ni la eleccion de mirar estos datos. supera_umbral_exploratorio="
                    "true senala una discrepancia descriptiva a revisar, no un hallazgo establecido; false no demuestra "
                    "aleatoriedad.")


class SimulacionFase7NoValida(ValueError):
    """Parametros o historico que no cumplen el contrato de la Fase 7.
    Nunca se corrige ni se filtra en silencio."""


class MuestraInsuficienteFase7(SimulacionFase7NoValida):
    """El historico no permite definir todas las estadisticas fijadas."""


# ---------------------------------------------------------------------------
# Estadisticas fijadas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DefinicionEstadistica:
    nombre: str
    descripcion: str
    motor_fase5: str
    justificacion: str


_DISP = "Σ(m·Oᵢ − N)² / (m·N): dispersion de los conteos frente a su valor esperado bajo uniformidad"
NUMERICAS = (
    DefinicionEstadistica("dispersion_frecuencia_numeros", f"{_DISP}, sobre los numeros principales",
                          "frecuencia.calcular_frecuencia_numeros",
                          "uniformidad marginal de los numeros (patron de frecuencias de Fase 5); media n - k"),
    DefinicionEstadistica("rango_frecuencia_numeros", "max Oᵢ − min Oᵢ de los numeros principales",
                          "frecuencia.calcular_frecuencia_numeros",
                          "numeros extremos ('calientes' y 'frios'); sin media analitica cerrada"),
    DefinicionEstadistica("media_repeticiones_entre_sorteos",
                          "coincidencias de numeros con el sorteo N-1, solo en transiciones estrictas N-1 -> N",
                          "repeticiones.calcular_repeticiones_entre_sorteos",
                          "dependencia serial entre sorteos consecutivos; media k²/n"),
    DefinicionEstadistica("media_suma", "media de la suma de los numeros principales de cada sorteo",
                          "distribuciones.calcular_distribucion_sumas",
                          "sesgo hacia numeros altos o bajos (distribucion de sumas); media k(n+1)/2"),
    DefinicionEstadistica("media_pares_consecutivos", "media de pares (v, v+1) presentes en un mismo sorteo",
                          "consecutivos.calcular_distribucion_pares_consecutivos",
                          "estructura dentro del sorteo (consecutivos); media k(k-1)/n"),
)
SUPERBALOTA = (
    DefinicionEstadistica("dispersion_frecuencia_superbalota", f"{_DISP}, sobre la superbalota (pool aparte)",
                          "frecuencia.calcular_frecuencia_superbalota",
                          "uniformidad de la superbalota, nunca mezclada con los numeros; media m - 1"),
)
COLORLOTO = (
    DefinicionEstadistica("dispersion_frecuencia_pares", f"{_DISP}, sobre los pares numero-color con multiplicidad",
                          "frecuencia.calcular_frecuencia_pares_numero_color",
                          "uniformidad del par como unidad (multinomial); media P - 1"),
    DefinicionEstadistica("dispersion_frecuencia_numeros", f"{_DISP}, sobre los numeros 1..7 con multiplicidad",
                          "frecuencia.calcular_frecuencia_numeros_colorloto",
                          "uniformidad marginal del numero; media 6"),
    DefinicionEstadistica("dispersion_frecuencia_colores", f"{_DISP}, sobre los colores con multiplicidad",
                          "frecuencia.calcular_frecuencia_colores",
                          "uniformidad marginal del color; media c - 1"),
    DefinicionEstadistica("media_repeticiones_entre_sorteos",
                          "interseccion de multiconjuntos de numeros con el sorteo N-1 (transiciones estrictas)",
                          "repeticiones.calcular_repeticiones_entre_sorteos_colorloto",
                          "dependencia serial con multiplicidad; media exacta por enumeracion binomial"),
    DefinicionEstadistica("media_maximo_repeticion_color",
                          "media de la mayor cantidad de balotas de un mismo color en un sorteo",
                          "distribuciones.calcular_maximo_repeticion_color_por_sorteo",
                          "agrupamiento de colores dentro del sorteo; media exacta por enumeracion multinomial"),
)


def familia(juego: str) -> tuple[DefinicionEstadistica, ...]:
    reglas = _reglas(juego)
    if reglas.colores:
        return COLORLOTO
    return NUMERICAS + (SUPERBALOTA if reglas.superbalota else ())


def _reglas(juego: str) -> lv.ReglasDelJuego:
    if juego not in JUEGO_INDICE:
        raise SimulacionFase7NoValida(f"juego no admitido: {juego!r}; admitidos: {', '.join(JUEGO_INDICE)}")
    return lv.REGLAS[juego]


def validar_parametros(iteraciones, semilla) -> tuple[int, int]:
    if isinstance(iteraciones, bool) or not isinstance(iteraciones, int) or iteraciones not in ITERACIONES_ADMITIDAS:
        raise SimulacionFase7NoValida("iteraciones admitidas: " + ", ".join(f"{i:_}".replace("_", ".")
                                                                            for i in ITERACIONES_ADMITIDAS))
    if isinstance(semilla, bool) or not isinstance(semilla, int) or not 0 <= semilla <= SEMILLA_MAXIMA:
        raise SimulacionFase7NoValida(f"la semilla debe ser un entero entre 0 y {SEMILLA_MAXIMA}")
    return iteraciones, semilla


# ---------------------------------------------------------------------------
# Historico como arreglos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Historico:
    """Instantanea validada en forma de arreglos. `valores`: (H, k) indices
    0..n-1 (numeros - rango_min, o indice del par en ColorLoto); `superbalota`:
    (H,) indices 0..m-1 o None; `transiciones`: mascara (H-1,) de N->N+1."""

    juego: str
    reglas: lv.ReglasDelJuego
    paleta: tuple[str, ...]
    numeracion: np.ndarray
    valores: np.ndarray
    superbalota: np.ndarray | None
    transiciones: np.ndarray
    instantanea: lv.Instantanea

    @property
    def sorteos(self) -> int:
        return int(self.valores.shape[0])

    @property
    def n(self) -> int:
        """Tamano del universo simulado por balota (numeros o pares)."""
        if self.reglas.colores:
            return (self.reglas.rango[1] - self.reglas.rango[0] + 1) * len(self.paleta)
        return self.reglas.rango[1] - self.reglas.rango[0] + 1

    @property
    def k(self) -> int:
        return self.reglas.cantidad

    @property
    def numeros(self) -> int:
        """Numeros distintos por balota (rango del juego)."""
        return self.reglas.rango[1] - self.reglas.rango[0] + 1

    @property
    def m(self) -> int | None:
        return None if self.reglas.superbalota is None else self.reglas.superbalota[1] - self.reglas.superbalota[0] + 1

    @property
    def dobles_por_iteracion(self) -> int:
        return self.sorteos * (self.k + (1 if self.reglas.superbalota else 0))


def preparar(juego: str, sorteos: Sequence, corte: int | None = None) -> Historico:
    """Valida con las reglas del juego (rechaza sorteos posteriores al corte
    y cualquier sorteo que no cumpla las reglas) y exige un historico que
    defina todas las estadisticas: al menos 2 sorteos y 1 transicion."""
    reglas = _reglas(juego)
    try:
        instantanea = lv.validar_instantanea(juego, list(sorteos), corte)
    except lv.HistoricoNoValidoError as error:
        raise SimulacionFase7NoValida(str(error)) from error
    if corte is not None and instantanea.corte != corte:
        raise SimulacionFase7NoValida(f"el corte {corte} no es el ultimo sorteo del historico leido")
    numeracion = np.array([r.numero_sorteo for r in instantanea.sorteos], dtype=np.int64)
    transiciones = np.diff(numeracion) == 1
    if len(numeracion) < 2 or not transiciones.any():
        raise MuestraInsuficienteFase7(
            f"{juego} necesita al menos 2 sorteos y una transicion N->N+1 para definir las estadisticas fijadas "
            f"({len(numeracion)} sorteos, {int(transiciones.sum())} transiciones)")
    lo = reglas.rango[0]
    if reglas.colores:
        paleta = instantanea.paleta()
        indice = {c: j for j, c in enumerate(paleta)}
        valores = np.array([[(n - lo) * len(paleta) + indice[c] for n, c in r.pares] for r in instantanea.sorteos],
                           dtype=np.int64)
        superbalota = None
    else:
        paleta = ()
        valores = np.array([[n - lo for n in r.numeros] for r in instantanea.sorteos], dtype=np.int64)
        superbalota = (np.array([r.superbalota - reglas.superbalota[0] for r in instantanea.sorteos], dtype=np.int64)
                       if reglas.superbalota else None)
    return Historico(juego, reglas, paleta, numeracion, valores, superbalota, transiciones, instantanea)


def descripcion_historico(h: Historico) -> dict:
    p = h.instantanea.procedencia()
    return {"sorteos": h.sorteos, "primer_sorteo": p["primer_sorteo"], "ultimo_sorteo": p["ultimo_sorteo"],
            "primera_fecha": p["primera_fecha"], "ultima_fecha": p["ultima_fecha"], "huecos": p["huecos"]["cantidad"],
            "transiciones": int(h.transiciones.sum()), "sha256": p["sha256_historico"]}


def reglas_y_mecanismo(h: Historico) -> dict:
    r = h.reglas
    if r.colores:
        mecanismo = (f"{r.cantidad} extracciones uniformes con reemplazo sobre los {h.n} pares (numero "
                     f"{r.rango[0]}..{r.rango[1]} x {len(h.paleta)} colores de la paleta del corte); multiplicidad "
                     "permitida (supuesto multinomial de Productos 2 y 5)")
    else:
        mecanismo = f"{r.cantidad} numeros distintos uniformes de {r.rango[0]}..{r.rango[1]} sin reemplazo"
        if r.superbalota:
            mecanismo += f"; superbalota uniforme {r.superbalota[0]}..{r.superbalota[1]}, aparte e independiente"
    return {"rango": list(r.rango), "cantidad": r.cantidad,
            "superbalota": list(r.superbalota) if r.superbalota else None,
            "pares_numero_color_con_multiplicidad": r.colores, "paleta": list(h.paleta), "mecanismo": mecanismo,
            "numeracion": "la observada, huecos incluidos; transiciones estrictas N-1 -> N"}


def algoritmo() -> dict:
    return {"generador": GENERADOR, "numpy": np.__version__,
            "semilla_derivada": f"SeedSequence([semilla, {FLUJO_FASE7}, indice_del_juego])",
            "indice_del_juego": dict(JUEGO_INDICE),
            "consumo": "H*(k+s) dobles de random() por iteracion, en orden (numeros o balotas y despues superbalota)",
            "seleccion_sin_reemplazo": ALGORITMO_SELECCION,
            "seleccion_detalle": "t-esimo indice floor(u*(n-t)) entre los restantes; sesgo <= n/2**53",
            "superbalota_y_pares": "floor(u*m) e floor(u*P): uniforme con el mismo sesgo acotado",
            "p_valor": "bilateral empirico +1: min(1, 2*min((1+#sim>=obs)/(1+B), (1+#sim<=obs)/(1+B)))",
            "percentil": "(2*#sim<obs + #sim==obs) / (2*B)", "familia": "bonferroni por juego y ejecucion",
            "alpha": ALPHA}


# ---------------------------------------------------------------------------
# Estadisticas vectorizadas (un lote de historicos)
# ---------------------------------------------------------------------------

def _popcount(x: np.ndarray) -> np.ndarray:
    return np.bitwise_count(x).astype(np.int64)


def _indice(u: np.ndarray, tamano: int) -> np.ndarray:
    """`floor(u * tamano)` para u en [0, 1): truncar es floor con u >= 0, y el
    producto redondeado nunca alcanza `tamano` (u <= 1 - 2**-53)."""
    return (u * tamano).astype(np.int32)


def _seleccion_sin_reemplazo(u: np.ndarray, n: int) -> np.ndarray:
    """(..., k) uniformes -> (..., k) indices distintos de 0..n-1. El t-esimo
    es el elemento `floor(u_t * (n - t))` de los que aun no se eligieron:
    se recorre la lista ordenada de los ya elegidos (r += r >= c) y despues
    se inserta el nuevo con una red de comparacion e intercambio."""
    k = u.shape[-1]
    elegidos = np.empty(u.shape, dtype=np.int64)
    ordenados: list[np.ndarray] = []
    for t in range(k):
        r = _indice(u[..., t], n - t)
        for c in ordenados:
            r += r >= c
        elegidos[..., t] = r
        insertados, mayor = [], r
        for c in ordenados:
            insertados.append(np.minimum(c, mayor))
            mayor = np.maximum(c, mayor)
        ordenados = insertados + [mayor]
    return elegidos


def _conteos(valores: np.ndarray, categorias: int) -> np.ndarray:
    """(B, ...) indices -> (B, categorias) conteos por fila."""
    b = valores.shape[0]
    plano = valores.reshape(b, -1) + (np.arange(b, dtype=np.int64) * categorias)[:, None]
    return np.bincount(plano.ravel(), minlength=b * categorias).reshape(b, categorias)


def _dispersion(conteos: np.ndarray) -> np.ndarray:
    categorias = conteos.shape[1]
    total = conteos.sum(axis=1, keepdims=True)
    return ((categorias * conteos - total) ** 2).sum(axis=1)


def estadisticas_de_lote(h: Historico, valores: np.ndarray, superbalota: np.ndarray | None) -> np.ndarray:
    """(B, H, k) valores [y (B, H) superbalota] -> (B, E) numeradores enteros
    en el orden de `familia(juego)`."""
    transiciones = h.transiciones
    if h.reglas.colores:
        c = len(h.paleta)
        numeros = valores // c
        colores = valores % c
        pares = _conteos(valores, h.n)
        por_numero = _conteos(numeros, h.numeros)
        por_color = _conteos(colores, c)
        b, hh, k = valores.shape
        por_sorteo = _conteos(numeros.reshape(b * hh, k), h.numeros).reshape(b, hh, h.numeros)
        repeticiones = np.minimum(por_sorteo[:, :-1, :], por_sorteo[:, 1:, :]).sum(axis=2)
        color_sorteo = _conteos(colores.reshape(b * hh, k), c).reshape(b, hh, c)
        return np.stack([_dispersion(pares), _dispersion(por_numero), _dispersion(por_color),
                         (repeticiones * transiciones).sum(axis=1), color_sorteo.max(axis=2).sum(axis=1)], axis=1)
    conteos = _conteos(valores, h.n)
    mascaras = (np.left_shift(np.uint64(1), valores.astype(np.uint64))).sum(axis=2, dtype=np.uint64)
    repeticiones = _popcount(mascaras[:, :-1] & mascaras[:, 1:])
    consecutivos = _popcount(mascaras & (mascaras >> np.uint64(1)))
    columnas = [_dispersion(conteos), conteos.max(axis=1) - conteos.min(axis=1),
                (repeticiones * transiciones).sum(axis=1),
                valores.sum(axis=(1, 2)) + valores.shape[1] * valores.shape[2] * h.reglas.rango[0],
                consecutivos.sum(axis=1)]
    if superbalota is not None:
        columnas.append(_dispersion(_conteos(superbalota, h.m)))
    return np.stack(columnas, axis=1)


def denominadores(h: Historico) -> tuple[int, ...]:
    hh, t = h.sorteos, int(h.transiciones.sum())
    if h.reglas.colores:
        total = hh * h.k
        return (h.n * total, h.numeros * total, len(h.paleta) * total, t, hh)
    salida = (h.n * hh * h.k, 1, t, hh, hh)
    return salida + ((h.m * hh,) if h.reglas.superbalota else ())


def observadas_con_el_motor(h: Historico) -> tuple[int, ...]:
    """Numeradores observados calculados con las funciones del motor de
    Fase 5 (definiciones de referencia)."""
    sorteos = h.instantanea.sorteos
    lo, hi = h.reglas.rango
    k = h.k

    def dispersion(filas) -> int:
        conteos = [f.apariciones for f in filas]
        total, m = sum(conteos), len(conteos)
        return sum((m * o - total) ** 2 for o in conteos)

    def total_tabulado(filas) -> int:
        return sum(int(f.valor) * f.apariciones for f in filas)

    if h.reglas.colores:
        paleta = list(h.paleta)
        pares = calcular_frecuencia_pares_numero_color(sorteos, lo, hi, paleta)
        if len(pares) != h.n:
            raise RuntimeError("el universo de pares del motor no coincide con el simulado")
        return (dispersion(pares), dispersion(calcular_frecuencia_numeros_colorloto(sorteos, lo, hi)),
                dispersion(calcular_frecuencia_colores(sorteos, paleta)),
                total_tabulado(calcular_repeticiones_entre_sorteos_colorloto(sorteos, lo, hi, k)),
                total_tabulado(calcular_maximo_repeticion_color_por_sorteo(sorteos, k)))
    frecuencias = calcular_frecuencia_numeros(sorteos, lo, hi)
    conteos = [f.apariciones for f in frecuencias]
    sumas = calcular_distribucion_sumas(sorteos)
    suma_total = round(sumas.media * sumas.total_sorteos)
    if abs(sumas.media * sumas.total_sorteos - suma_total) > 1e-6:
        raise RuntimeError("la media de sumas del motor no corresponde a un total entero")
    salida = (dispersion(frecuencias), max(conteos) - min(conteos),
              total_tabulado(calcular_repeticiones_entre_sorteos(sorteos, lo, hi, k)), suma_total,
              total_tabulado(calcular_distribucion_pares_consecutivos(sorteos, lo, hi, k)))
    if h.reglas.superbalota:
        salida += (dispersion(calcular_frecuencia_superbalota(sorteos, *h.reglas.superbalota)),)
    return salida


def observadas(h: Historico) -> tuple[int, ...]:
    """Lo observado con el motor de Fase 5, contrastado con la version
    vectorizada aplicada al historico real: si difieren, es un defecto y
    se detiene (nunca se publica)."""
    del_motor = observadas_con_el_motor(h)
    vectorizadas = tuple(int(v) for v in estadisticas_de_lote(
        h, h.valores[None, ...], None if h.superbalota is None else h.superbalota[None, ...])[0])
    if del_motor != vectorizadas:
        raise RuntimeError(f"estadisticas observadas inconsistentes: motor {del_motor} != vectorizadas {vectorizadas}")
    return del_motor


# ---------------------------------------------------------------------------
# Referencias analiticas exactas
# ---------------------------------------------------------------------------

def _binomial(n: int, p: Fraction) -> list[Fraction]:
    return [math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(n + 1)]


@lru_cache(maxsize=None)
def media_repeticiones_multiconjunto(balotas: int, valores: int) -> Fraction:
    """E[Σᵥ min(Aᵥ, Bᵥ)] con A, B multinomiales independientes (balotas
    uniformes con reemplazo): valores · E[min(X, Y)], X, Y ~ Bin(balotas, 1/valores)."""
    f = _binomial(balotas, Fraction(1, valores))
    return valores * sum(f[i] * f[j] * min(i, j) for i in range(balotas + 1) for j in range(balotas + 1))


@lru_cache(maxsize=None)
def media_maximo_multiplicidad(balotas: int, categorias: int) -> Fraction:
    """E[max multiplicidad] de `balotas` extracciones uniformes con reemplazo
    entre `categorias` (enumeracion exacta de todas las secuencias)."""
    total = Counter(max(Counter(s).values()) for s in product(range(categorias), repeat=balotas))
    return Fraction(sum(v * c for v, c in total.items()), categorias**balotas)


def referencias(h: Historico) -> tuple[Fraction | None, ...]:
    if h.reglas.colores:
        c = len(h.paleta)
        return (Fraction(h.n - 1), Fraction(h.numeros - 1), Fraction(c - 1),
                media_repeticiones_multiconjunto(h.k, h.numeros),
                media_maximo_multiplicidad(h.k, c))
    n, k = h.n, h.k
    salida = (Fraction(n - k), None, Fraction(k * k, n), Fraction(k * (n + 1), 2), Fraction(k * (k - 1), n))
    return salida + ((Fraction(h.m - 1),) if h.reglas.superbalota else ())


# ---------------------------------------------------------------------------
# Simulacion
# ---------------------------------------------------------------------------

def generador(semilla: int, juego: str) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([semilla, FLUJO_FASE7, JUEGO_INDICE[juego]])))


def tamano_de_lote(h: Historico, iteraciones: int) -> int:
    return max(1, min(iteraciones, DOBLES_POR_LOTE // h.dobles_por_iteracion))


def simular_lote(h: Historico, rng: np.random.Generator, b: int) -> np.ndarray:
    """(b, E) numeradores de b historicos simulados; consume exactamente
    b * H * (k + s) dobles."""
    s = 1 if h.reglas.superbalota else 0
    u = rng.random((b, h.sorteos, h.k + s))
    if h.reglas.colores:
        valores = _indice(u, h.n).astype(np.int64)
        superbalota = None
    else:
        valores = _seleccion_sin_reemplazo(u[..., :h.k], h.n)
        superbalota = _indice(u[..., h.k], h.m).astype(np.int64) if s else None
    return estadisticas_de_lote(h, valores, superbalota)


class Acumulador:
    """Conteos frente a lo observado y momentos enteros exactos, en flujo."""

    def __init__(self, observado: Sequence[int]):
        self.observado = np.array(observado, dtype=np.int64)
        e = len(observado)
        self.iteraciones = 0
        self.mayores_o_iguales = [0] * e
        self.menores_o_iguales = [0] * e
        self.menores = [0] * e
        self.suma = [0] * e
        self.suma_cuadrados = [0] * e
        self.minimo: list[int | None] = [None] * e
        self.maximo: list[int | None] = [None] * e

    def sumar(self, valores: np.ndarray) -> None:
        self.iteraciones += int(valores.shape[0])
        for j in range(valores.shape[1]):
            v = valores[:, j]
            o = self.observado[j]
            self.mayores_o_iguales[j] += int((v >= o).sum())
            self.menores_o_iguales[j] += int((v <= o).sum())
            self.menores[j] += int((v < o).sum())
            lista = v.tolist()
            self.suma[j] += sum(lista)
            self.suma_cuadrados[j] += sum(x * x for x in lista)
            minimo, maximo = int(v.min()), int(v.max())
            self.minimo[j] = minimo if self.minimo[j] is None else min(self.minimo[j], minimo)
            self.maximo[j] = maximo if self.maximo[j] is None else max(self.maximo[j], maximo)


def simular(h: Historico, iteraciones: int, semilla: int, *, lote: int | None = None,
            avance: Callable[..., None] | None = None) -> tuple[Acumulador, dict]:
    """Simula `iteraciones` historicos y acumula sus estadisticas. Devuelve
    el acumulador y los metadatos del procesamiento (no forman parte del
    resultado cientifico)."""
    iteraciones, semilla = validar_parametros(iteraciones, semilla)
    lote = tamano_de_lote(h, iteraciones) if lote is None else int(lote)
    if lote < 1:
        raise SimulacionFase7NoValida("el tamano de lote debe ser >= 1")
    avance = avance or (lambda *a, **k: None)
    acumulador = Acumulador(observadas(h))
    rng = generador(semilla, h.juego)
    hechas = lotes = 0
    while hechas < iteraciones:
        b = min(lote, iteraciones - hechas)
        acumulador.sumar(simular_lote(h, rng, b))
        hechas += b
        lotes += 1
        avance("simulando", hechas=hechas, de=iteraciones)
    return acumulador, {"lote": lote, "lotes": lotes, "dobles_por_iteracion": h.dobles_por_iteracion,
                        "dobles_por_lote_maximo": lote * h.dobles_por_iteracion}


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

def _fraccion(valor: Fraction) -> str:
    return f"{valor.numerator}/{valor.denominator}"


def construir_contenido(h: Historico, acumulador: Acumulador, iteraciones: int) -> dict:
    """Resultado cientifico determinista: valores exactos (enteros y
    fracciones `a/b`) y su lectura en coma flotante. Bonferroni con la
    funcion del motor sobre las comparaciones de este juego."""
    definiciones = familia(h.juego)
    dens = denominadores(h)
    refs = referencias(h)
    b = iteraciones
    if acumulador.iteraciones != b:
        raise RuntimeError("el acumulador no tiene todas las iteraciones pedidas")
    exactos = []
    for j, d in enumerate(definiciones):
        den = dens[j]
        obs = int(acumulador.observado[j])
        suma, cuadrados = acumulador.suma[j], acumulador.suma_cuadrados[j]
        iguales = acumulador.menores_o_iguales[j] - acumulador.menores[j]
        p_sup = Fraction(1 + acumulador.mayores_o_iguales[j], 1 + b)
        p_inf = Fraction(1 + acumulador.menores_o_iguales[j], 1 + b)
        exactos.append({
            "observado": Fraction(obs, den), "media": Fraction(suma, b * den),
            "varianza": Fraction(b * cuadrados - suma * suma, b * (b - 1) * den * den) if b > 1 else Fraction(0),
            "percentil": Fraction(2 * acumulador.menores[j] + iguales, 2 * b),
            "p_valor": min(Fraction(1), 2 * min(p_sup, p_inf)), "iguales": iguales})
    pruebas = [ResultadoTestEstadistico(nombre_test=f"fase7_{h.juego}_{d.nombre}", elementos=("*",),
                                        estadistico=float(x["observado"]), grados_libertad=None,
                                        p_value=float(x["p_valor"]), p_value_ajustado=None, metodo_correccion=None,
                                        alpha=None, significativo=None)
               for d, x in zip(definiciones, exactos)]
    ajustadas = aplicar_correccion_bonferroni(pruebas, alpha=ALPHA)
    m = len(definiciones)
    p_minimo = min(Fraction(1), Fraction(2, 1 + b))
    estadisticas = []
    for j, (d, x, a) in enumerate(zip(definiciones, exactos, ajustadas)):
        ajustado = min(Fraction(1), x["p_valor"] * m)
        if (ajustado < Fraction(ALPHA).limit_denominator(100)) != a.significativo:
            raise RuntimeError("Bonferroni exacto y del motor no coinciden")
        ref = refs[j]
        estadisticas.append({
            "nombre": d.nombre, "descripcion": d.descripcion, "motor_fase5": d.motor_fase5,
            "observado": {"numerador": int(acumulador.observado[j]), "denominador": dens[j],
                          "exacto": _fraccion(x["observado"]), "valor": float(x["observado"])},
            "simulado": {"suma_numeradores": acumulador.suma[j], "suma_cuadrados_numeradores": acumulador.suma_cuadrados[j],
                         "minimo_numerador": acumulador.minimo[j], "maximo_numerador": acumulador.maximo[j],
                         "mayores_o_iguales": acumulador.mayores_o_iguales[j],
                         "menores_o_iguales": acumulador.menores_o_iguales[j], "menores": acumulador.menores[j],
                         "iguales": x["iguales"], "media_exacta": _fraccion(x["media"]), "media": float(x["media"]),
                         "varianza_exacta": _fraccion(x["varianza"]),
                         "desviacion": math.sqrt(float(x["varianza"]))},
            "referencia_analitica": None if ref is None else {"exacta": _fraccion(ref), "valor": float(ref)},
            "percentil_observado": {"exacto": _fraccion(x["percentil"]), "valor": float(x["percentil"])},
            "p_valor_empirico": {"exacto": _fraccion(x["p_valor"]), "valor": a.p_value},
            "p_valor_ajustado_bonferroni": {"exacto": _fraccion(ajustado), "valor": a.p_value_ajustado},
            "supera_umbral_exploratorio": bool(a.significativo)})
    return {"juego": h.juego, "iteraciones": b, "estadisticas": estadisticas,
            "familia": {"metodo": "bonferroni", "tamano": m, "alpha": ALPHA,
                        "alcance": "comparaciones_de_este_juego_en_esta_ejecucion", "cobertura": COBERTURA_AJUSTE,
                        "p_minimo_alcanzable": _fraccion(p_minimo),
                        "umbral_alcanzable": min(Fraction(1), p_minimo * m) < Fraction(1, 20)},
            "alguna_supera_umbral_exploratorio": any(e["supera_umbral_exploratorio"] for e in estadisticas),
            "nota": NOTA}


def calcular(juego: str, sorteos_canonicos: Sequence, iteraciones: int, semilla: int, *, lote: int | None = None,
             avance: Callable[..., None] | None = None) -> dict:
    """Punto de entrada comun del proceso trabajador y del ejecutor en el
    mismo proceso: reconstruye y valida el historico canonico (ya cortado),
    simula y construye el contenido."""
    import time

    try:
        instantanea = lv.instantanea_desde_canonicos(juego, sorteos_canonicos)
    except lv.HistoricoNoValidoError as error:
        raise SimulacionFase7NoValida(str(error)) from error
    h = preparar(juego, instantanea.sorteos)
    inicio = time.perf_counter()
    acumulador, procesamiento = simular(h, iteraciones, semilla, lote=lote, avance=avance)
    contenido = construir_contenido(h, acumulador, iteraciones)
    return {"contenido": contenido, "procesamiento": procesamiento, "historico_sha256": h.instantanea.huella(),
            "duracion_ms": int(round((time.perf_counter() - inicio) * 1000))}


def definicion_de_familia(juego: str) -> list[dict]:
    return [{"nombre": d.nombre, "descripcion": d.descripcion, "motor_fase5": d.motor_fase5,
             "justificacion": d.justificacion} for d in familia(juego)]
