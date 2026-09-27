"""AE-55, validada: calculadora analitica de factibilidad de una regla
estadistica prospectiva con 100 sorteos por juego.

Cuantifica, bajo supuestos declarados y sin simulacion ni datos:

- el efecto minimo detectable (EMD) de una media de diferencias por
  sorteo, EXPRESADO EN UNIDADES DE SIGMA (desviacion tipica marginal de
  `d_t`), con aproximacion normal y un factor de inflacion de varianza
  de largo plazo `kappa` que es un supuesto (la formula AR(1) es solo
  una aproximacion bajo ese modelo);
- la distribucion exacta (hipergeometrica) de los aciertos del top-5
  bajo sorteos uniformes, distinguiendo E[aciertos] = 25/43 de
  E[P@5] = 5/43;
- la varianza exacta, bajo sorteos uniformes, de la diferencia pareada
  de aciertos entre dos tops segun su solape.

No conoce sigma, kappa, efectos ni potencia reales; no elige metodo,
nivel, efecto minimo ni regla de multiplicidad; no cierra
`regla_estadistica_de_decision` y no modifica el NO-GO de AE-39 ni los
bloqueos de AE-41/AE-46.
"""
from __future__ import annotations

import math
from fractions import Fraction
from statistics import NormalDist

_NORMAL = NormalDist()
N_AE55 = 100
ALFA_UNILATERAL_AE55 = 0.025
POTENCIAS_AE55 = (0.8, 0.9)
RHOS_AE55 = (0.3, 0.6)
SUPUESTOS_AE55 = (
    "aproximacion normal de la media de d_t",
    "sigma es la desviacion tipica marginal de d_t y es desconocida",
    "kappa = varianza de largo plazo / sigma^2 es un supuesto; (1+rho)/(1-rho) solo si d_t fuera AR(1) estacionario",
    "la media de la ventana es el objetivo; tratarla como parametro constante exige estacionariedad",
    "aciertos y diferencia pareada calculados bajo sorteos uniformes sin reemplazo y predicciones fijadas antes del sorteo",
)


class FactibilidadInvalidaError(ValueError):
    """Entrada invalida para la calculadora de factibilidad."""


def _entero(valor, nombre: str, minimo: int) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < minimo:
        raise FactibilidadInvalidaError(f"{nombre} debe ser un entero >= {minimo}")
    return valor


def _real(valor, nombre: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise FactibilidadInvalidaError(f"{nombre} debe ser un real finito")
    return float(valor)


def _probabilidad(valor, nombre: str, maximo: float = 1.0) -> float:
    valor = _real(valor, nombre)
    if not 0.0 < valor < maximo:
        raise FactibilidadInvalidaError(f"{nombre} debe estar en (0, {maximo})")
    return valor


def cuantil_normal(p: float) -> float:
    return _NORMAL.inv_cdf(_probabilidad(p, "p"))


# ---------------------------------------------------------------------------
# Potencia y efecto minimo detectable, en unidades de sigma
# ---------------------------------------------------------------------------

def inflacion_varianza_ar1(rho: float) -> float:
    """`(1 + rho) / (1 - rho)`: cociente entre la varianza de largo plazo
    y la marginal SOLO si `d_t` fuera un AR(1) estacionario."""
    rho = _real(rho, "rho")
    if not -1.0 < rho < 1.0:
        raise FactibilidadInvalidaError("rho debe estar en (-1, 1)")
    return (1 + rho) / (1 - rho)


def _comunes(n, alfa_unilateral, inflacion) -> tuple[int, float, float]:
    n = _entero(n, "n", 2)
    alfa = _probabilidad(alfa_unilateral, "alfa_unilateral", 0.5)
    inflacion = _real(inflacion, "inflacion")
    if inflacion <= 0.0:
        raise FactibilidadInvalidaError("inflacion debe ser positiva")
    return n, alfa, inflacion


def efecto_minimo_detectable(n: int, alfa_unilateral: float, potencia: float, inflacion: float) -> float:
    """EMD / sigma ~ (z_{1-alfa} + z_{potencia}) * sqrt(inflacion / n),
    con aproximacion normal. En unidades de sigma, nunca del problema.

    Dominio: `n >= 2`, `0 < alfa_unilateral < 0,5`, `alfa_unilateral <
    potencia < 1` e `inflacion > 0`; en ese dominio el EMD es positivo.
    Una potencia igual o inferior a alfa se rechaza: ya la alcanza un
    efecto nulo (o negativo), asi que no define un efecto detectable."""
    n, alfa, inflacion = _comunes(n, alfa_unilateral, inflacion)
    potencia = _probabilidad(potencia, "potencia")
    if potencia <= alfa:
        raise FactibilidadInvalidaError("potencia debe ser mayor que alfa_unilateral")
    return (_NORMAL.inv_cdf(1 - alfa) + _NORMAL.inv_cdf(potencia)) * math.sqrt(inflacion / n)


def potencia_aproximada(efecto_en_sigmas: float, n: int, alfa_unilateral: float, inflacion: float) -> float:
    """Potencia aproximada del contraste unilateral de la media para un
    efecto expresado en unidades de sigma."""
    n, alfa, inflacion = _comunes(n, alfa_unilateral, inflacion)
    efecto = _real(efecto_en_sigmas, "efecto_en_sigmas")
    return _NORMAL.cdf(efecto * math.sqrt(n / inflacion) - _NORMAL.inv_cdf(1 - alfa))


# ---------------------------------------------------------------------------
# Secundaria: aciertos del top bajo sorteos uniformes (exacto)
# ---------------------------------------------------------------------------

def distribucion_aciertos(rango: int, cantidad: int) -> dict:
    """Aciertos de un top de `cantidad` numeros cuando se extraen
    `cantidad` numeros de `rango` sin reemplazo: hipergeometrica exacta."""
    rango = _entero(rango, "rango", 1)
    cantidad = _entero(cantidad, "cantidad", 1)
    if cantidad > rango:
        raise FactibilidadInvalidaError("cantidad no puede superar el rango")
    total = math.comb(rango, cantidad)
    probabilidades = [Fraction(math.comb(cantidad, k) * math.comb(rango - cantidad, cantidad - k), total)
                      for k in range(cantidad + 1)]
    media = sum(k * p for k, p in enumerate(probabilidades))
    varianza = sum(k * k * p for k, p in enumerate(probabilidades)) - media * media
    return {"probabilidades": probabilidades, "media_aciertos": media, "varianza_aciertos": varianza,
            "media_precision": media / cantidad}


def varianza_diferencia_aciertos(rango: int, cantidad: int, solape: int) -> dict:
    """Varianza exacta de (aciertos del top A) - (aciertos del top B)
    cuando A y B tienen `cantidad` numeros y comparten `solape`:
    `2 (cantidad - solape) (V - C)`, con V la varianza de un indicador y
    C la covarianza de dos indicadores distintos. Con solape total (tops
    identicos) la diferencia es siempre 0 y se devuelve 0 exacto, sin
    evaluar C (que no esta definida si `rango = 1`)."""
    rango = _entero(rango, "rango", 1)
    cantidad = _entero(cantidad, "cantidad", 1)
    solape = _entero(solape, "solape", 0)
    if solape > cantidad or 2 * cantidad - solape > rango:
        raise FactibilidadInvalidaError("solape incompatible con cantidad y rango")
    if solape == cantidad:
        cero = Fraction(0)
        return {"solape": solape, "varianza_aciertos": cero, "varianza_precision": cero}
    p = Fraction(cantidad, rango)
    varianza_indicador = p * (1 - p)
    covarianza = Fraction(cantidad * (cantidad - 1), rango * (rango - 1)) - p * p
    varianza = 2 * (cantidad - solape) * (varianza_indicador - covarianza)
    return {"solape": solape, "varianza_aciertos": varianza, "varianza_precision": varianza / (cantidad * cantidad)}


# ---------------------------------------------------------------------------
# Tabla fija y descriptiva
# ---------------------------------------------------------------------------

def tabla_factibilidad() -> dict:
    """Malla fija de AE-55. Descriptiva: no aprueba nivel, potencia,
    efecto minimo ni tolerancia secundaria."""
    escenarios = [("sin_dependencia", 1.0)] + [(f"ar1_rho_{rho}", inflacion_varianza_ar1(rho)) for rho in RHOS_AE55]
    emd = [{"potencia": potencia, "escenario_dependencia": nombre, "inflacion": inflacion,
            "emd_en_sigmas": efecto_minimo_detectable(N_AE55, ALFA_UNILATERAL_AE55, potencia, inflacion)}
           for potencia in POTENCIAS_AE55 for nombre, inflacion in escenarios]
    aciertos = distribucion_aciertos(43, 5)
    return {
        "caracter": "analitico_bajo_supuestos",
        "n": N_AE55,
        "alfa_unilateral": ALFA_UNILATERAL_AE55,
        "supuestos": list(SUPUESTOS_AE55),
        "efecto_minimo_detectable": emd,
        "secundaria": {
            "rango": 43, "cantidad": 5,
            "probabilidades_aciertos": [str(p) for p in aciertos["probabilidades"]],
            "media_aciertos": str(aciertos["media_aciertos"]),
            "varianza_aciertos": str(aciertos["varianza_aciertos"]),
            "media_precision": str(aciertos["media_precision"]),
            "diferencia_pareada": [
                {"solape": fila["solape"], "varianza_aciertos": str(fila["varianza_aciertos"]),
                 "varianza_precision": str(fila["varianza_precision"]),
                 "varianza_precision_decimal": float(fila["varianza_precision"])}
                for fila in (varianza_diferencia_aciertos(43, 5, j) for j in range(6))
            ],
        },
    }
