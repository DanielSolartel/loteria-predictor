"""
Producto 4 -laboratorio de modelos: instantanea del historico y variables
causales.

INSTANTANEA. Una comparacion trabaja sobre una copia congelada y validada
del historico de UN juego hasta un corte (`Instantanea`). Se valida con las
reglas del dominio (Baloto y Revancha: 5 numeros distintos de 1..43 y
superbalota 1..16; MiLoto: 5 numeros distintos de 1..39, sin superbalota;
ColorLoto: 6 pares numero 1..7 y color, con repeticion) y se serializa de
forma canonica (`sorteos_canonicos`), igual que la huella de Productos 1-2:
el mismo historico da la misma huella y se puede reconstruir sin la base.

VARIABLES (version `VERSION_VARIABLES`). Para el objetivo en la posicion
`i` del historico ordenado, todas se calculan SOLO con los sorteos
`0..i-1` (prefijo estrictamente anterior): nunca con el objetivo ni con
nada posterior. Se calculan una vez con sumas acumuladas del prefijo.

- Numeros (Baloto, Revancha, MiLoto), una fila por candidato y sorteo:
  frecuencia en las ventanas de 5, 10 y 20 sorteos previos, frecuencia
  acumulada previa, aparicion en el sorteo inmediatamente anterior, atraso
  (sorteos desde la ultima aparicion) y `nunca_aparecio` (1 si el candidato
  no aparecio en ningun sorteo previo; entonces el atraso vale el numero de
  sorteos previos, el maximo observable). La identidad del candidato es una
  categoria (columna 0), nunca una magnitud. Etiqueta: aparicion (0/1).
- ColorLoto, una fila por par (numero, color) y sorteo: conteo medio por
  sorteo en ventanas de 5, 10 y 20, conteo medio acumulado, conteo en el
  sorteo anterior (0..6), atraso y `nunca_aparecio` del par. Identidad
  categorica del par. Etiqueta: numero de apariciones del par en el sorteo
  objetivo (0..6), sin reducirla a 0/1. Los pares candidatos de un objetivo
  son los 7 numeros por los colores de la paleta observada antes de el.

Modulo puro: sin reloj, red, base de datos ni escritura.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np

from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico
from app.application.ml import pronostico_colorloto as pcl
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.pronostico_experimental import huella_del_historico as huella_numerica

VERSION_VARIABLES = "producto4-variables-1"
CALENTAMIENTO = 20
"""Sorteos previos que necesita un objetivo para tener sus ventanas completas."""
VENTANAS = (5, 10, 20)
NOMBRES_VARIABLES_NUMEROS = ("candidato", "frecuencia_ventana_5", "frecuencia_ventana_10", "frecuencia_ventana_20",
                             "frecuencia_acumulada", "aparecio_en_sorteo_anterior", "atraso", "nunca_aparecio")
NOMBRES_VARIABLES_COLORLOTO = ("par", "conteo_medio_ventana_5", "conteo_medio_ventana_10", "conteo_medio_ventana_20",
                               "conteo_medio_acumulado", "conteo_en_sorteo_anterior", "atraso", "nunca_aparecio")


@dataclass(frozen=True)
class ReglasDelJuego:
    codigo: str
    rango: tuple[int, int]
    cantidad: int
    superbalota: tuple[int, int] | None
    colores: bool = False

    @property
    def candidatos(self) -> tuple[int, ...]:
        return tuple(range(self.rango[0], self.rango[1] + 1))

    def como_dict(self) -> dict:
        return {"rango": list(self.rango), "cantidad": self.cantidad,
                "superbalota": list(self.superbalota) if self.superbalota else None,
                "multiconjunto_de_pares_numero_color": self.colores,
                "repeticion": self.colores}


REGLAS = {
    "BALOTO": ReglasDelJuego("BALOTO", (1, 43), 5, (1, 16)),
    "BALOTO_REVANCHA": ReglasDelJuego("BALOTO_REVANCHA", (1, 43), 5, (1, 16)),
    "MILOTO": ReglasDelJuego("MILOTO", (1, 39), 5, None),
    "COLORLOTO": ReglasDelJuego("COLORLOTO", pcl.NUMEROS, pcl.BALOTAS, None, colores=True),
}
JUEGOS = tuple(REGLAS)


class HistoricoNoValidoError(ValueError):
    """El historico no cumple las reglas del juego o no es coherente."""


@dataclass(frozen=True)
class Instantanea:
    """Historico congelado y validado de un juego, ordenado por sorteo."""

    reglas: ReglasDelJuego
    sorteos: tuple

    @property
    def codigo(self) -> str:
        return self.reglas.codigo

    @property
    def corte(self) -> int:
        return self.sorteos[-1].numero_sorteo

    def __len__(self) -> int:
        return len(self.sorteos)

    def huella(self) -> str:
        return (pcl.huella_del_historico(self.sorteos) if self.reglas.colores
                else huella_numerica(self.sorteos))

    def paleta(self, hasta: int | None = None) -> tuple[str, ...]:
        """Colores observados en los sorteos de posicion < `hasta` (todos si None)."""
        if not self.reglas.colores:
            return ()
        return pcl.paleta_del_corte(self.sorteos[:hasta] if hasta is not None else self.sorteos)

    def procedencia(self) -> dict:
        numeros = [r.numero_sorteo for r in self.sorteos]
        presentes = set(numeros)
        huecos = [n for n in range(numeros[0], numeros[-1] + 1) if n not in presentes]
        return {"sorteos": len(numeros), "primer_sorteo": numeros[0], "primera_fecha": self.sorteos[0].fecha.isoformat(),
                "ultimo_sorteo": numeros[-1], "ultima_fecha": self.sorteos[-1].fecha.isoformat(), "corte": numeros[-1],
                "huecos": {"cantidad": len(huecos), "primeros": huecos[:20]}, "sha256_historico": self.huella()}


def validar_instantanea(codigo: str, historico: Sequence, hasta: int | None = None) -> Instantanea:
    """Ordena y valida con las reglas del juego. Rechaza (no corrige ni
    filtra en silencio) sorteos posteriores al corte pedido."""
    if codigo not in REGLAS:
        raise HistoricoNoValidoError(f"juego no admitido por el laboratorio: {codigo!r}")
    reglas = REGLAS[codigo]
    try:
        ordenado = validar_y_ordenar_historico(list(historico), codigo)
    except ValueError as error:
        raise HistoricoNoValidoError(str(error)) from error
    if not ordenado:
        raise HistoricoNoValidoError(f"{codigo} no tiene sorteos hasta el corte")
    if hasta is not None and ordenado[-1].numero_sorteo > hasta:
        raise HistoricoNoValidoError(f"el historico trae sorteos posteriores al corte {hasta}")
    lo, hi = reglas.rango
    for r in ordenado:
        if reglas.colores:
            if not isinstance(r, ResultadoColorLoto) or len(r.pares) != reglas.cantidad:
                raise HistoricoNoValidoError(f"sorteo {r.numero_sorteo}: se esperaban {reglas.cantidad} pares")
            for n, c in r.pares:
                if not lo <= n <= hi or not isinstance(c, str) or not c:
                    raise HistoricoNoValidoError(f"sorteo {r.numero_sorteo}: par no valido ({n!r}, {c!r})")
            continue
        if not isinstance(r, ResultadoNumerico) or len(r.numeros) != reglas.cantidad or \
                len(set(r.numeros)) != reglas.cantidad:
            raise HistoricoNoValidoError(f"sorteo {r.numero_sorteo}: se esperaban {reglas.cantidad} numeros distintos")
        if any(not lo <= n <= hi for n in r.numeros):
            raise HistoricoNoValidoError(f"sorteo {r.numero_sorteo}: numeros fuera de [{lo}, {hi}]")
        if reglas.superbalota is None:
            if r.superbalota is not None:
                raise HistoricoNoValidoError(f"sorteo {r.numero_sorteo}: {codigo} no tiene superbalota")
        elif r.superbalota is None or not reglas.superbalota[0] <= r.superbalota <= reglas.superbalota[1]:
            raise HistoricoNoValidoError(f"sorteo {r.numero_sorteo}: superbalota ausente o fuera de rango")
    return Instantanea(reglas, tuple(ordenado))


# ---------------------------------------------------------------------------
# Serializacion canonica (para guardar y reconstruir sin la base)
# ---------------------------------------------------------------------------

def sorteos_canonicos(instantanea: Instantanea) -> list:
    if instantanea.reglas.colores:
        return [[r.numero_sorteo, r.fecha.isoformat(), sorted([n, c] for n, c in r.pares)] for r in instantanea.sorteos]
    return [[r.numero_sorteo, r.fecha.isoformat(), list(r.numeros), r.superbalota] for r in instantanea.sorteos]


_DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")


def instantanea_desde_canonicos(codigo: str, filas: Sequence) -> Instantanea:
    """Reconstruye la instantanea guardada (validandola otra vez)."""
    historico = []
    for fila in filas:
        fecha = date.fromisoformat(fila[1])
        if codigo == "COLORLOTO":
            historico.append(ResultadoColorLoto(int(fila[0]), fecha, _DIAS[fecha.weekday()],
                                                tuple((int(n), str(c)) for n, c in fila[2])))
        else:
            historico.append(ResultadoNumerico(int(fila[0]), fecha, _DIAS[fecha.weekday()],
                                               tuple(int(n) for n in fila[2]),
                                               None if fila[3] is None else int(fila[3])))
    return validar_instantanea(codigo, historico)


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

def codigo_de_par(numero: int, color: str) -> float:
    """Identificador numerico estable de un par (solo identidad: no depende de
    la paleta, del orden de aparicion ni de sorteos posteriores)."""
    return float(numero * 10 ** 7 + int(hashlib.sha256(color.encode("utf-8")).hexdigest()[:6], 16))


@dataclass(frozen=True)
class Filas:
    """Filas candidato-sorteo de varios objetivos. `X[:, 0]` es la identidad
    categorica (candidato o par); el resto, variables numericas."""

    objetivos: np.ndarray       # numero de sorteo objetivo de cada fila
    posiciones: np.ndarray      # posicion del objetivo en la instantanea
    candidatos: tuple           # candidato (int) o par (numero, color) de cada fila
    X: np.ndarray
    y: np.ndarray               # 0/1 (numeros) o conteo 0..6 (ColorLoto); NaN si el objetivo no existe

    def __len__(self) -> int:
        return len(self.objetivos)

    def seleccionar(self, mascara) -> "Filas":
        indices = np.flatnonzero(mascara)
        return Filas(self.objetivos[indices], self.posiciones[indices], tuple(self.candidatos[i] for i in indices),
                     self.X[indices], self.y[indices])

    def de_posiciones(self, posiciones) -> "Filas":
        return self.seleccionar(np.isin(self.posiciones, list(posiciones)))


def _matriz(instantanea: Instantanea, columnas: list) -> np.ndarray:
    """Conteo de cada columna (candidato o par) en cada sorteo."""
    indice = {c: j for j, c in enumerate(columnas)}
    A = np.zeros((len(instantanea), len(columnas)), dtype=float)
    for i, r in enumerate(instantanea.sorteos):
        for elemento in (r.pares if instantanea.reglas.colores else r.numeros):
            A[i, indice[tuple(elemento) if instantanea.reglas.colores else elemento]] += 1
    return A


class Variables:
    """Variables causales de todos los objetivos de una instantanea, y del
    objetivo siguiente al corte (posicion `len(instantanea)`)."""

    def __init__(self, instantanea: Instantanea):
        self.instantanea = instantanea
        reglas = instantanea.reglas
        if reglas.colores:
            colores = sorted({c for r in instantanea.sorteos for _, c in r.pares})
            self.columnas = [(n, c) for n in reglas.candidatos for c in colores]
        else:
            self.columnas = list(reglas.candidatos)
        A = _matriz(instantanea, self.columnas)
        self._A = A
        self._S = np.vstack([np.zeros((1, A.shape[1])), np.cumsum(A, axis=0)])
        n = len(instantanea)
        ultima = np.full(A.shape[1], -1, dtype=int)
        self._ultima_antes = np.empty((n + 1, A.shape[1]), dtype=int)
        for i in range(n + 1):
            self._ultima_antes[i] = ultima
            if i < n:
                ultima = np.where(A[i] > 0, i, ultima)
        self._memo: dict = {}

    def memo(self, clave: str, calcular):
        """Resultado derivado de la instantanea, calculado una sola vez."""
        if clave not in self._memo:
            self._memo[clave] = calcular()
        return self._memo[clave]

    def de_ajuste(self, posicion_de_corte: int) -> Filas:
        """Filas de los objetivos de posicion CALENTAMIENTO..posicion_de_corte-1,
        cada uno con sus candidatos de entonces (paleta previa a cada objetivo)."""
        todas = self.memo("ajuste", lambda: self.filas(range(CALENTAMIENTO, len(self.instantanea))))
        return todas.seleccionar(todas.posiciones < posicion_de_corte)

    def _candidatos_de(self, posicion: int, paleta: tuple | None) -> list[int]:
        if not self.instantanea.reglas.colores:
            return list(range(len(self.columnas)))
        permitida = set(self.instantanea.paleta(posicion) if paleta is None else paleta)
        return [j for j, (_, c) in enumerate(self.columnas) if c in permitida]

    def filas(self, posiciones, paleta: tuple | None = None) -> Filas:
        """Filas de los objetivos en `posiciones` (cada una >= CALENTAMIENTO).
        La posicion `len(instantanea)` es el objetivo siguiente al corte (sin
        etiqueta). `paleta` (ColorLoto) fija los pares candidatos; por defecto,
        la paleta observada antes de cada objetivo."""
        colores = self.instantanea.reglas.colores
        objetivos, pos, cands, X, y = [], [], [], [], []
        n = len(self.instantanea)
        for i in posiciones:
            if i < CALENTAMIENTO or i > n:
                raise ValueError(f"posicion de objetivo fuera de rango: {i}")
            numero = self.instantanea.sorteos[i].numero_sorteo if i < n else self.instantanea.corte + 1
            previo = self._S[i]
            for j in self._candidatos_de(i, paleta):
                ventanas = [(previo[j] - self._S[i - w][j]) / w for w in VENTANAS]
                ultima = self._ultima_antes[i][j]
                nunca = ultima < 0
                c = self.columnas[j]
                identidad = codigo_de_par(*c) if colores else float(c)
                X.append([identidad, *ventanas, previo[j] / i, self._A[i - 1][j],
                          float(i if nunca else i - 1 - ultima), 1.0 if nunca else 0.0])
                y.append(self._A[i][j] if i < n else np.nan)
                objetivos.append(numero)
                pos.append(i)
                cands.append(c)
        return Filas(np.asarray(objetivos, dtype=int), np.asarray(pos, dtype=int), tuple(cands),
                     np.asarray(X, dtype=float).reshape(-1, 8), np.asarray(y, dtype=float))
