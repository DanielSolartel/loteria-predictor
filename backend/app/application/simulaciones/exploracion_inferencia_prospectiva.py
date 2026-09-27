"""AE-54, validada: banco de exploracion sintetica de metodos
candidatos de inferencia para series de diferencias por sorteo.

Estudia, con n = 100 y escenarios de dependencia conocida, como
reaccionan varios metodos candidatos sobre `d_t` (uniforme - estrategia,
positivo a favor de la estrategia). Todas las hipotesis, niveles y
reglas de rechazo son EXPERIMENTALES y propias de este banco: no
aprueban ninguna regla prospectiva, no cierran
`regla_estadistica_de_decision`, no modifican el borrador de AE-52 ni
la especificacion de AE-53 y no cambian el NO-GO de AE-39 ni los
bloqueos de AE-41/AE-46. Los resultados son exploratorios: no
establecen el error tipo I real, la potencia del modelo ni un GO.

Escenarios:
- E1..E6: series construidas con media cero por construccion (la
  innovacion tiene soporte exactamente simetrico y los filtros son
  lineales o multiplicativos con un factor que solo depende del
  pasado); nunca se centra la muestra.
- L1, L2: sorteos uniformes sinteticos (5 de 43) con una estrategia fija
  o adaptativa; `d_t` se calcula con `metricas_por_sorteo` de AE-53.
  Como Log Loss y Brier son reglas estrictamente propias, la nula esta
  en el interior (`E[d] < 0`): sus frecuencias de rechazo no son
  tamanos.

Metodos: M1 bootstrap iid percentil, M2a/M2b bootstrap de bloques
circulares (l = 5 y 10), M3a Diebold-Mariano con la correccion
Harvey-Leybourne-Newbold a un paso, M3b Diebold-Mariano con varianza
HAC de Newey-West (Bartlett, m = 4) y M4 contraste condicional de
Giacomini-White con `h = (1, d_{t-1})`.

Reproducibilidad: solo `Random(semilla).random()`, semillas derivadas
con `semilla_por_juego` de AE-49 y sumas con `math.fsum`. Se espera la
misma salida byte a byte al repetir la ejecucion en el MISMO entorno
(misma version de Python y plataforma); no se promete igualdad entre
plataformas ni versiones.
"""
from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from app.application.ml.especificacion_evaluacion_prospectiva import metricas_por_sorteo
from app.application.simulaciones.montecarlo_uniforme import semilla_por_juego

ESQUEMA_AE54 = "exploracion-inferencia-prospectiva/1.0"
ESCENARIOS_E = ("E1", "E2", "E3", "E4", "E5", "E6")
ESCENARIOS_L = ("L1", "L2")
METRICAS_L = ("log_loss", "brier_score")
METODOS = ("M1", "M2a", "M2b", "M3a", "M3b", "M4")
ALFA_UNILATERAL = 0.025
T_CRITICO_99_0975 = 1.9842169515864174
"""Cuantil 0,975 de la t de Student con 99 grados de libertad (n - 1)."""
CHI2_2_095 = 5.991464547107979
"""Cuantil 0,95 de la chi-cuadrado con 2 grados de libertad."""
_RANGO, _CANTIDAD = 43, 5
_ESCALA = 2 ** 53
_RAIZ_3 = math.sqrt(3.0)

_DESCRIPCIONES = {
    "E1": "iid: d_t = z_t",
    "E2": "iid con colas pesadas: d_t = c_t * z_t, c_t = 5 con probabilidad 0,1 y 1 en otro caso",
    "E3": "AR(1) phi = 0,3: d_t = phi d_{t-1} + sqrt(1 - phi^2) z_t, calentamiento 200 desde 0",
    "E4": "AR(1) phi = 0,6: d_t = phi d_{t-1} + sqrt(1 - phi^2) z_t, calentamiento 200 desde 0",
    "E5": "MA de ventanas solapadas: d_t = (z_t + ... + z_{t-4}) / sqrt(5)",
    "E6": "heterocedastico sin autocorrelacion: d_t = sqrt(0,2 + 0,7 d_{t-1}^2) z_t, calentamiento 200 desde 0",
    "L1": "sorteos uniformes sinteticos 5 de 43; estrategia fija p = 0,9 * 5/43 + 0,1 * q",
    "L2": "sorteos uniformes sinteticos 5 de 43; estrategia adaptativa p_t = 0,9 * 5/43 + 0,1 * frecuencia en los 20 sorteos anteriores",
}
_HIPOTESIS = {
    **{e: {"media_cero_por_construccion": True, "nula_condicional_m4_verdadera": True} for e in ("E1", "E2", "E6")},
    **{e: {"media_cero_por_construccion": True, "nula_condicional_m4_verdadera": False} for e in ("E3", "E4", "E5")},
    **{e: {"media_cero_por_construccion": False, "nula_condicional_m4_verdadera": False} for e in ESCENARIOS_L},
}
_DEFINICION_METODOS = {
    "M1": "H0: E[d] <= 0 frente a E[d] > 0; bootstrap iid percentil; rechaza si el limite inferior > 0",
    "M2a": "H0: E[d] <= 0 frente a E[d] > 0; bootstrap de bloques circulares l = 5; rechaza si el limite inferior > 0",
    "M2b": "H0: E[d] <= 0 frente a E[d] > 0; bootstrap de bloques circulares l = 10; rechaza si el limite inferior > 0",
    "M3a": "H0: E[d] <= 0 frente a E[d] > 0; S = sqrt((n-1)/n) media / sqrt(gamma0/n); rechaza si S > t_{n-1;0,975}",
    "M3b": "H0: E[d] <= 0 frente a E[d] > 0; S = media / sqrt(V_NW/n), Bartlett m = 4; rechaza si S > t_{n-1;0,975}",
    "M4": "H0: E[d_t | pasado] = 0 (no direccional); GW con h = (1, d_{t-1}); rechaza si GW > chi2_{2;0,95}",
}
ALCANCE_AE54 = (
    "Banco exploratorio sintetico de AE-54. Las hipotesis, niveles y reglas de rechazo son experimentales y no "
    "aprueban ninguna regla prospectiva ni cierran regla_estadistica_de_decision. Las frecuencias de rechazo "
    "describen el comportamiento de cada metodo en escenarios construidos con n fijo; no establecen el error tipo I "
    "real, la cobertura real ni la potencia del modelo, y no autorizan un GO. En L la nula esta en el interior, asi "
    "que sus frecuencias no son tamanos; M4 contrasta una hipotesis condicional distinta de M1-M3. El intervalo "
    "bootstrap usa los estadisticos de orden (B+1)*0,025 y (B+1)*0,975. La reproduccion byte a byte solo se espera "
    "en el mismo entorno de ejecucion; no se promete igualdad entre plataformas ni versiones de Python. No usa "
    "datos reales, PostgreSQL ni predicciones reales, y el NO-GO de AE-39 sigue vigente."
)


class ParametrosExploracionError(ValueError):
    """Parametros o entradas invalidas del banco exploratorio."""


@dataclass(frozen=True)
class ParametrosExploracion:
    n: int
    b: int
    r_e: int
    r_l: int
    semilla: int
    longitudes_bloque: tuple[int, ...]
    ancho_banda: int
    calentamiento_ar: int
    calentamiento_l: int
    ventana_l2: int

    def __post_init__(self) -> None:
        enteros = (self.n, self.b, self.r_e, self.r_l, self.semilla, self.ancho_banda, self.calentamiento_ar,
                   self.calentamiento_l, self.ventana_l2, *self.longitudes_bloque)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in enteros):
            raise ParametrosExploracionError("Todos los parametros deben ser enteros")
        if self.n < 3 or self.r_e < 1 or self.r_l < 1 or self.b < 1 or (self.b + 1) % 40:
            raise ParametrosExploracionError("n >= 3, R >= 1 y B + 1 multiplo de 40")
        if not 1 <= self.ancho_banda < self.n or not all(1 <= l <= self.n for l in self.longitudes_bloque):
            raise ParametrosExploracionError("ancho de banda y longitudes de bloque fuera de rango")
        if len(self.longitudes_bloque) != 2 or self.ventana_l2 < 1 or self.calentamiento_l < self.ventana_l2:
            raise ParametrosExploracionError("dos longitudes de bloque y calentamiento de L >= ventana de L2")
        if self.calentamiento_ar < 0:
            raise ParametrosExploracionError("calentamiento_ar no puede ser negativo")


PARAMETROS_AE54 = ParametrosExploracion(
    n=100, b=999, r_e=2000, r_l=500, semilla=20261001, longitudes_bloque=(5, 10), ancho_banda=4,
    calentamiento_ar=200, calentamiento_l=100, ventana_l2=20,
)
"""Parametros fijados antes de ejecutar; solo del banco exploratorio."""


# ---------------------------------------------------------------------------
# Generadores
# ---------------------------------------------------------------------------

def innovacion_simetrica(rng) -> float:
    """`z = (2k + 1 - 2^53) / 2^53 * sqrt(3)` con `k = int(random() * 2^53)`:
    soporte exactamente simetrico respecto de 0 (media cero por
    construccion) y varianza aproximadamente 1."""
    k = int(rng.random() * _ESCALA)
    return (2 * k + 1 - _ESCALA) / _ESCALA * _RAIZ_3


def generar_serie_e(escenario: str, rng, n: int, calentamiento: int) -> list[float]:
    if escenario == "E1":
        return [innovacion_simetrica(rng) for _ in range(n)]
    if escenario == "E2":
        serie = []
        for _ in range(n):
            z = innovacion_simetrica(rng)
            serie.append((5.0 if rng.random() < 0.1 else 1.0) * z)
        return serie
    if escenario in ("E3", "E4", "E6"):
        phi = {"E3": 0.3, "E4": 0.6}.get(escenario)
        d, serie = 0.0, []
        for t in range(calentamiento + n):
            if phi is None:
                d = math.sqrt(0.2 + 0.7 * d * d) * innovacion_simetrica(rng)
            else:
                d = phi * d + math.sqrt(1 - phi * phi) * innovacion_simetrica(rng)
            if t >= calentamiento:
                serie.append(d)
        return serie
    if escenario == "E5":
        z = [innovacion_simetrica(rng) for _ in range(n + 4)]
        return [math.fsum(z[t:t + 5]) / math.sqrt(5) for t in range(n)]
    raise ParametrosExploracionError(f"Escenario desconocido: {escenario!r}")


def muestra_sin_reemplazo(rng, tamano: int, cantidad: int) -> list[int]:
    """Fisher-Yates parcial con `int(random() * m)`: mismo algoritmo que
    el generador (privado) de AE-49, reimplementado para no depender de
    un nombre privado; una prueba comprueba que coinciden."""
    poblacion = list(range(tamano))
    for i in range(cantidad):
        j = i + int(rng.random() * (tamano - i))
        poblacion[i], poblacion[j] = poblacion[j], poblacion[i]
    return poblacion[:cantidad]


def vector_l1(semilla: int) -> list[float]:
    """Estrategia fija de L1: `p = 0,9 * 5/43 + 0,1 * q`, con `q` sorteado
    una sola vez a partir de la semilla y normalizado a suma 5."""
    rng = Random(semilla_por_juego(semilla, "L1|q"))
    pesos = [rng.random() for _ in range(_RANGO)]
    total = math.fsum(pesos)
    return [0.9 * _CANTIDAD / _RANGO + 0.1 * _CANTIDAD * w / total for w in pesos]


def probabilidades_l2(sorteos_previos: Sequence[Sequence[int]], ventana: int) -> list[float]:
    """Estrategia adaptativa de L2 a partir SOLO de los sorteos previos:
    `p = 0,9 * 5/43 + 0,1 * frecuencia en los ultimos `ventana` sorteos`."""
    if len(sorteos_previos) < ventana:
        raise ParametrosExploracionError("No hay suficientes sorteos previos para la ventana de L2")
    conteo = [0] * _RANGO
    for sorteo in sorteos_previos[-ventana:]:
        for numero in sorteo:
            conteo[numero - 1] += 1
    return [0.9 * _CANTIDAD / _RANGO + 0.1 * c / ventana for c in conteo]


def generar_series_l(escenario: str, rng, n: int, calentamiento: int, ventana: int,
                     q: Sequence[float]) -> dict[str, list[float]]:
    """Diferencias uniforme - estrategia de Log Loss y Brier, por sorteo,
    con `metricas_por_sorteo` de AE-53 sobre sorteos uniformes sinteticos."""
    if escenario not in ESCENARIOS_L:
        raise ParametrosExploracionError(f"Escenario desconocido: {escenario!r}")
    sorteos = [sorted(i + 1 for i in muestra_sin_reemplazo(rng, _RANGO, _CANTIDAD)) for _ in range(calentamiento + n)]
    series = {metrica: [] for metrica in METRICAS_L}
    for t in range(calentamiento, calentamiento + n):
        p = list(q) if escenario == "L1" else probabilidades_l2(sorteos[:t], ventana)
        metricas = metricas_por_sorteo("BALOTO", t + 1, p, sorteos[t])
        for metrica in METRICAS_L:
            series[metrica].append(metricas.diferencias[metrica])
    return series


# ---------------------------------------------------------------------------
# Estadisticos y metodos candidatos
# ---------------------------------------------------------------------------

def media(x: Sequence[float]) -> float:
    return math.fsum(x) / len(x)


def autocovarianza(x: Sequence[float], k: int) -> float:
    m = media(x)
    return math.fsum((x[t] - m) * (x[t - k] - m) for t in range(k, len(x))) / len(x)


def autocorrelaciones(x: Sequence[float], retardos: int) -> list[float] | None:
    g0 = autocovarianza(x, 0)
    if g0 <= 0.0:
        return None
    return [autocovarianza(x, k) / g0 for k in range(1, retardos + 1)]


def limites_percentil(valores: Sequence[float]) -> tuple[float, float]:
    """Estadisticos de orden `(B+1)*0,025` y `(B+1)*0,975` (base 1) de
    las `B` medias bootstrap. Exige `B + 1` multiplo de 40."""
    b = len(valores)
    if (b + 1) % 40:
        raise ParametrosExploracionError("B + 1 debe ser multiplo de 40")
    ordenados = sorted(valores)
    return ordenados[(b + 1) // 40 - 1], ordenados[(b + 1) * 39 // 40 - 1]


def _resultado_bootstrap(medias: list[float]) -> dict:
    inferior, superior = limites_percentil(medias)
    return {"inferior": inferior, "superior": superior, "rechaza": inferior > 0.0}


def metodo_bootstrap_iid(x: Sequence[float], rng, b: int) -> dict:
    n = len(x)
    return _resultado_bootstrap([media([x[int(rng.random() * n)] for _ in range(n)]) for _ in range(b)])


def indices_bloques_circulares(rng, n: int, longitud: int) -> list[int]:
    """Concatena `ceil(n/l)` bloques de `l` indices consecutivos con
    envoltura circular e inicio uniforme en `0..n-1`; trunca a `n`."""
    indices = []
    for _ in range(-(-n // longitud)):
        inicio = int(rng.random() * n)
        indices.extend((inicio + j) % n for j in range(longitud))
    return indices[:n]


def metodo_bootstrap_bloques(x: Sequence[float], rng, b: int, longitud: int) -> dict:
    n = len(x)
    return _resultado_bootstrap([media([x[i] for i in indices_bloques_circulares(rng, n, longitud)]) for _ in range(b)])


def _resultado_t(estadistico: float | None) -> dict:
    if estadistico is None:
        return {"estadistico": None, "rechaza": False, "degenerado": True}
    return {"estadistico": estadistico, "rechaza": estadistico > T_CRITICO_99_0975, "degenerado": False}


def metodo_dm_hln(x: Sequence[float]) -> dict:
    n = len(x)
    g0 = autocovarianza(x, 0)
    if g0 <= 0.0:
        return _resultado_t(None)
    return _resultado_t(math.sqrt((n - 1) / n) * media(x) / math.sqrt(g0 / n))


def metodo_dm_hac(x: Sequence[float], ancho_banda: int) -> dict:
    n = len(x)
    varianza = autocovarianza(x, 0) + 2 * math.fsum(
        (1 - k / (ancho_banda + 1)) * autocovarianza(x, k) for k in range(1, ancho_banda + 1))
    if varianza <= 0.0:
        return _resultado_t(None)
    return _resultado_t(media(x) / math.sqrt(varianza / n))


def metodo_gw(x: Sequence[float]) -> dict:
    """GW = n' Zb' Omega^{-1} Zb con Z_t = (d_t, d_{t-1} d_t), t = 2..n,
    y Omega = (1/n') sum Z_t Z_t' (a un paso, sin HAC)."""
    z = [(x[t], x[t - 1] * x[t]) for t in range(1, len(x))]
    n = len(z)
    zb0 = math.fsum(c[0] for c in z) / n
    zb1 = math.fsum(c[1] for c in z) / n
    a = math.fsum(c[0] * c[0] for c in z) / n
    b = math.fsum(c[0] * c[1] for c in z) / n
    d = math.fsum(c[1] * c[1] for c in z) / n
    determinante = a * d - b * b
    if determinante <= 0.0:
        return {"estadistico": None, "rechaza": False, "singular": True}
    estadistico = n * (d * zb0 * zb0 - 2 * b * zb0 * zb1 + a * zb1 * zb1) / determinante
    return {"estadistico": estadistico, "rechaza": estadistico > CHI2_2_095, "singular": False}


def _aplicar_metodos(x: Sequence[float], parametros: ParametrosExploracion, clave: str) -> dict:
    def rng(metodo):
        return Random(semilla_por_juego(parametros.semilla, f"{clave}|{metodo}"))

    l_a, l_b = parametros.longitudes_bloque
    return {
        "M1": metodo_bootstrap_iid(x, rng("M1"), parametros.b),
        "M2a": metodo_bootstrap_bloques(x, rng("M2a"), parametros.b, l_a),
        "M2b": metodo_bootstrap_bloques(x, rng("M2b"), parametros.b, l_b),
        "M3a": metodo_dm_hln(x),
        "M3b": metodo_dm_hac(x, parametros.ancho_banda),
        "M4": metodo_gw(x),
    }


# ---------------------------------------------------------------------------
# Ejecucion y reporte
# ---------------------------------------------------------------------------

def _resumen(escenario: str, metrica: str | None, series: list[list[float]], resultados: list[dict]) -> dict:
    r = len(series)
    medias = [media(s) for s in series]
    media_de_medias = math.fsum(medias) / r
    dispersion = math.sqrt(math.fsum((m - media_de_medias) ** 2 for m in medias) / (r - 1)) if r > 1 else None
    acf = [a for a in (autocorrelaciones(s, 5) for s in series) if a is not None]
    autocorrelacion = [math.fsum(a[k] for a in acf) / len(acf) for k in range(5)] if acf else [None] * 5
    metodos = []
    for metodo in METODOS:
        casos = [res[metodo] for res in resultados]
        rechazos = sum(1 for c in casos if c["rechaza"])
        frecuencia = rechazos / r
        fila = {
            "id": metodo, "replicas": r, "rechazos": rechazos, "frecuencia": frecuencia,
            "error_mc": math.sqrt(frecuencia * (1 - frecuencia) / r),
            "casos_degenerados": sum(1 for c in casos if c.get("degenerado") or c.get("singular")),
        }
        if metodo in ("M1", "M2a", "M2b"):
            fila["anchura_media_intervalo"] = math.fsum(c["superior"] - c["inferior"] for c in casos) / r
        metodos.append(fila)
    return {
        "id": escenario, "metrica": metrica, "descripcion": _DESCRIPCIONES[escenario],
        "hipotesis": dict(_HIPOTESIS[escenario]),
        "diagnostico": {"media_de_medias": media_de_medias, "desviacion_de_medias": dispersion,
                        "autocorrelacion_media": autocorrelacion, "series_con_varianza_nula": r - len(acf)},
        "metodos": metodos,
    }


def ejecutar_exploracion(parametros: ParametrosExploracion) -> dict:
    """Ejecuta el banco completo con parametros fijos y devuelve el
    reporte exploratorio (sin tiempos, para que sea reproducible)."""
    escenarios = []
    for escenario in ESCENARIOS_E:
        series, resultados = [], []
        for replica in range(parametros.r_e):
            clave = f"{escenario}|{replica}"
            x = generar_serie_e(escenario, Random(semilla_por_juego(parametros.semilla, clave)), parametros.n,
                                parametros.calentamiento_ar)
            series.append(x)
            resultados.append(_aplicar_metodos(x, parametros, clave))
        escenarios.append(_resumen(escenario, None, series, resultados))
    q = vector_l1(parametros.semilla)
    for escenario in ESCENARIOS_L:
        por_metrica = {metrica: ([], []) for metrica in METRICAS_L}
        for replica in range(parametros.r_l):
            clave = f"{escenario}|{replica}"
            generadas = generar_series_l(escenario, Random(semilla_por_juego(parametros.semilla, clave)), parametros.n,
                                         parametros.calentamiento_l, parametros.ventana_l2, q)
            for metrica in METRICAS_L:
                x = generadas[metrica]
                por_metrica[metrica][0].append(x)
                por_metrica[metrica][1].append(_aplicar_metodos(x, parametros, f"{clave}|{metrica}"))
        for metrica in METRICAS_L:
            escenarios.append(_resumen(escenario, metrica, *por_metrica[metrica]))
    datos = dataclasses.asdict(parametros)
    datos["longitudes_bloque"] = list(parametros.longitudes_bloque)
    return {
        "esquema": ESQUEMA_AE54, "etapa": "AE-54", "caracter": "exploratorio_sintetico",
        "parametros": {**datos, "alfa_unilateral": ALFA_UNILATERAL, "t_critico_99_0975": T_CRITICO_99_0975,
                       "chi2_2_095": CHI2_2_095, "semillas": "semilla_por_juego(semilla, 'escenario|replica[|metrica]|metodo')"},
        "metodos": dict(_DEFINICION_METODOS),
        "escenarios": escenarios,
        "alcance": ALCANCE_AE54,
    }
