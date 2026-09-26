"""AE-49, validada: referencia Monte Carlo EXPLORATORIA bajo azar
uniforme (primera etapa de la Fase 6).

Analisis exploratorio sobre datos reutilizados: el rango principal
`2081..2705` es el contrato congelado de AE-36 y ya fue examinado en
AE-36 a AE-39. No es confirmatorio, no esta prerregistrado, no es
evidencia prospectiva ni predictiva, no genera combinaciones ni
recomendaciones y no modifica el NO-GO de AE-39.

Pregunta, para BALOTO y BALOTO_REVANCHA por separado: ¿son
compatibles cuatro estadisticas descriptivas fijadas de antemano con
su distribucion bajo azar uniforme? La distribucion nula se obtiene
simulando historicos con el mismo mecanismo de sorteo (5 numeros sin
reemplazo + superbalota) y la MISMA numeracion observada, huecos
incluidos. Esto evita la chi-cuadrado clasica con gl = N-1, mal
calibrada sin reemplazo (bajo azar uniforme E[S] = n - k, no n - 1).

- Rango fijo 2081..2705, sin opcion para cambiarlo. `2591..2705`
  (consumido en AE-36) se incluye sin analizarlo por separado;
  `2706` en adelante no se lee, no se simula ni entra en la huella.
- Familia fija de 8 comparaciones (2 juegos x 4 estadisticas) con
  Bonferroni. El ajuste cubre solo estas ocho comparaciones, no la
  seleccion ni la inspeccion previa de datos y analisis.
- Reproducibilidad: generador que solo usa `Random(semilla).random()`
  (secuencia garantizada por Python para una semilla entera),
  aritmetica exacta con `int`/`Fraction` (sin `sum()` de floats, que
  cambio en Python 3.12) y conversion a float solo al construir el
  reporte. La identidad de bytes entre versiones se verifica con una
  prueba SHA-256 de referencia, no se da por supuesta.

Modulo puro: sin SQLAlchemy, sin `app.application.ml` y sin
escrituras."""
from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from random import Random

from app.application.estadisticas.motor.frecuencia import calcular_frecuencia_numeros, calcular_frecuencia_superbalota
from app.application.estadisticas.motor.repeticiones import calcular_repeticiones_entre_sorteos
from app.application.estadisticas.motor.tests_estadisticos import aplicar_correccion_bonferroni
from app.application.estadisticas.tipos import ResultadoNumerico, ResultadoTestEstadistico
from app.domain.games.standard_number_game import StandardNumberGame
from app.domain.value_objects.combination import Combination

RANGO_PRINCIPAL_AE49 = (2081, 2705)
"""Contrato congelado de AE-36 (`INICIO_HISTORICO_REAL..FIN_CONTRATO_AE36`
de `ml/ventanas_temporales.py`). Se duplica aqui para no importar
`app.application.ml`; una prueba verifica que coinciden."""
JUEGOS_AE49 = ("BALOTO", "BALOTO_REVANCHA")
ESTADISTICAS_AE49 = (
    "dispersion_frecuencia_numeros",
    "rango_frecuencia_numeros",
    "media_repeticiones_entre_sorteos",
    "dispersion_frecuencia_superbalota",
)
TAMANO_FAMILIA_AE49 = 8
ALPHA_AE49 = 0.05
SEMILLA_AE49 = 20260926
ITERACIONES_AE49 = 10_000
GENERADOR_AE49 = "ae49-fisher-yates-random-v1"
ESQUEMA_AE49 = "simulacion-azar-uniforme/1.0"
CARACTER_AE49 = "exploratorio_sobre_datos_reutilizados"
_PREFIJO_HUELLA = "ae49-entrada-v1"
_ESTADISTICAS_ENTERAS = frozenset({"rango_frecuencia_numeros"})

NOTA_AE49 = (
    "Analisis exploratorio sobre datos reutilizados: el rango 2081..2705 ya fue examinado en AE-36 a AE-39. "
    "Referencia descriptiva bajo azar uniforme: no es confirmatorio, no esta prerregistrado, "
    "no es evidencia prospectiva ni predictiva, no genera combinaciones ni recomendaciones "
    "y no modifica el NO-GO de AE-39."
)
FRASES_NEGATIVAS_DISCLAIMER = (
    "no es confirmatorio",
    "no genera combinaciones ni recomendaciones",
    "no es evidencia prospectiva ni predictiva",
)
"""Unicas frases negativas fijas que las pruebas descuentan antes de
rechazar cualquier texto de confirmacion o recomendacion."""
TEXTO_TRAMOS = (
    "Incluye 2591..2705 (consumido como test final de AE-36) sin analizarlo por separado. "
    "2706 en adelante no se lee, no se simula y no entra en la huella: no es un holdout ciego "
    "y este analisis no lo convierte en uno."
)
COBERTURA_AJUSTE = (
    "Bonferroni cubre solo estas ocho comparaciones de esta ejecucion; no corrige la seleccion ni la "
    "inspeccion previa de datos y analisis en AE-36 a AE-39. supera_umbral_exploratorio=true senala una "
    "discrepancia descriptiva a revisar, no un hallazgo establecido; false no demuestra aleatoriedad."
)


class EntradaSimulacionInvalidaError(ValueError):
    """El historico o los parametros del juego no cumplen el contrato
    fijo de AE-49. Nunca se filtra ni se completa en silencio."""


@dataclass(frozen=True)
class ParametrosJuego:
    codigo: str
    rango_min: int
    rango_max: int
    cantidad_numeros: int
    superbalota_min: int
    superbalota_max: int


@dataclass(frozen=True)
class ValoresEstadisticos:
    """Cada estadistica como numerador entero sobre un denominador
    entero. Los denominadores dependen solo de la numeracion y de la
    cantidad de superbalotas, asi que son identicos en el historico
    observado y en cada historico simulado."""

    numeradores: tuple[int, ...]
    denominadores: tuple[int, ...]
    total_sorteos: int
    total_transiciones: int
    total_superbalotas: int

    def como_fracciones(self) -> tuple[Fraction, ...]:
        return tuple(Fraction(n, d) for n, d in zip(self.numeradores, self.denominadores))


@dataclass(frozen=True)
class ComparacionEstadistica:
    nombre: str
    observado: Fraction
    media: Fraction
    varianza: Fraction
    referencia: Fraction | None
    percentil: Fraction
    p_valor: Fraction


@dataclass(frozen=True)
class ResultadoJuego:
    codigo: str
    total_sorteos: int
    total_transiciones: int
    total_superbalotas: int
    entrada_sha256: str
    comparaciones: tuple[ComparacionEstadistica, ...]


def parametros_desde_dominio(codigo: str, juego: StandardNumberGame) -> ParametrosJuego:
    if not juego.has_superballot or juego.superballot_range is None:
        raise EntradaSimulacionInvalidaError(f"'{codigo}' no tiene superbalota; AE-49 solo cubre Baloto y Revancha")
    rango_min, rango_max = juego.number_range
    superbalota_min, superbalota_max = juego.superballot_range
    return ParametrosJuego(codigo, rango_min, rango_max, juego.numbers_to_pick, superbalota_min, superbalota_max)


def verificar_rango_principal(historico: Sequence[ResultadoNumerico], juego: StandardNumberGame) -> list[ResultadoNumerico]:
    """Exige exactamente `2081..2705`: sin huecos, duplicados ni sorteos
    fuera del rango, y cada sorteo valido segun el dominio (incluida la
    superbalota). Los mensajes nunca incluyen numeros ganadores."""
    desde, hasta = RANGO_PRINCIPAL_AE49
    ordenados = sorted(historico, key=lambda r: r.numero_sorteo)
    numeracion = [r.numero_sorteo for r in ordenados]
    if numeracion != list(range(desde, hasta + 1)):
        detalle = f"{len(numeracion)} sorteos" + (
            f", primero {numeracion[0]}, ultimo {numeracion[-1]}" if numeracion else ""
        )
        raise EntradaSimulacionInvalidaError(
            f"El historico no es exactamente {desde}..{hasta} sin huecos ni duplicados ({detalle})"
        )
    invalidos = []
    for resultado in ordenados:
        try:
            valido = juego.validate_draw(
                Combination(numeros=tuple(resultado.numeros), superbalota=resultado.superbalota)
            ).is_valid
        except ValueError:
            valido = False
        if not valido:
            invalidos.append(resultado.numero_sorteo)
    if invalidos:
        raise EntradaSimulacionInvalidaError(
            f"Sorteos que no cumplen las reglas del juego: {invalidos[:10]}"
            + (f" y {len(invalidos) - 10} mas" if len(invalidos) > 10 else "")
        )
    return ordenados


def huella_entrada(codigo: str, historico: Sequence[ResultadoNumerico]) -> str:
    """SHA-256 de la entrada normalizada: exactamente los campos que
    afectan al calculo (numeracion, numeros ordenados y superbalota).
    `fecha` y `dia_semana` quedan fuera a proposito."""
    lineas = [_PREFIJO_HUELLA, codigo]
    for resultado in sorted(historico, key=lambda r: r.numero_sorteo):
        numeros = ",".join(str(n) for n in sorted(resultado.numeros))
        lineas.append(f"{resultado.numero_sorteo}:{numeros}:{resultado.superbalota}")
    return hashlib.sha256(("\n".join(lineas) + "\n").encode("utf-8")).hexdigest()


def semilla_por_juego(semilla: int, codigo: str) -> int:
    """Semilla independiente por juego, estable entre procesos (nunca
    `hash()`, que depende de PYTHONHASHSEED)."""
    return int.from_bytes(hashlib.sha256(f"{semilla}:{codigo}".encode("utf-8")).digest()[:8], "big")


def _indice_uniforme(rng: Random, tamano: int) -> int:
    """`floor(random() * tamano)`: sesgo <= tamano / 2**53, documentado."""
    return int(rng.random() * tamano)


def _muestra_sin_reemplazo(rng: Random, tamano: int, cantidad: int) -> list[int]:
    """Fisher-Yates parcial propio: no depende de `Random.sample`, cuya
    implementacion Python no garantiza entre versiones."""
    poblacion = list(range(tamano))
    for i in range(cantidad):
        j = i + _indice_uniforme(rng, tamano - i)
        poblacion[i], poblacion[j] = poblacion[j], poblacion[i]
    return poblacion[:cantidad]


def simular_historia(rng: Random, historico: Sequence[ResultadoNumerico], params: ParametrosJuego) -> list[ResultadoNumerico]:
    """Un historico bajo azar uniforme con la misma numeracion (y por
    tanto las mismas transiciones) y superbalota donde la hay."""
    tamano = params.rango_max - params.rango_min + 1
    tamano_superbalota = params.superbalota_max - params.superbalota_min + 1
    simulado = []
    for resultado in historico:
        indices = _muestra_sin_reemplazo(rng, tamano, params.cantidad_numeros)
        numeros = tuple(sorted(params.rango_min + i for i in indices))
        superbalota = None
        if resultado.superbalota is not None:
            superbalota = params.superbalota_min + _indice_uniforme(rng, tamano_superbalota)
        simulado.append(ResultadoNumerico(
            numero_sorteo=resultado.numero_sorteo, fecha=resultado.fecha, dia_semana=resultado.dia_semana,
            numeros=numeros, superbalota=superbalota,
        ))
    return simulado


def _suma_de_cuadrados_centrados(conteos: Sequence[int], escala: int, centro: int) -> int:
    total = 0
    for conteo in conteos:
        total += (escala * conteo - centro) ** 2
    return total


def calcular_estadisticas(historico: Sequence[ResultadoNumerico], params: ParametrosJuego) -> ValoresEstadisticos:
    """Las cuatro estadisticas con el motor existente, solo sobre sus
    campos enteros (`apariciones`, `total_sorteos`):
      1. Σ(Oᵢ−E)²/E con E = T·k/n  ->  Σ(n·Oᵢ − T·k)² / (n·T·k)
      2. maxᵢ Oᵢ − minᵢ Oᵢ
      3. coincidencias totales / transiciones estrictas N→N+1
      4. Σ(Oⱼ−E)²/E con E = T_sb/m ->  Σ(m·Oⱼ − T_sb)² / (m·T_sb)"""
    n = params.rango_max - params.rango_min + 1
    k = params.cantidad_numeros
    frecuencias = calcular_frecuencia_numeros(historico, params.rango_min, params.rango_max)
    conteos = [fila.apariciones for fila in frecuencias]
    total = frecuencias[0].total_sorteos
    repeticiones = calcular_repeticiones_entre_sorteos(historico, params.rango_min, params.rango_max, k)
    transiciones = repeticiones[0].total_sorteos
    coincidencias = 0
    for fila in repeticiones:
        coincidencias += int(fila.valor) * fila.apariciones
    superbalotas = calcular_frecuencia_superbalota(historico, params.superbalota_min, params.superbalota_max)
    m = params.superbalota_max - params.superbalota_min + 1
    total_superbalotas = superbalotas[0].total_sorteos
    if total == 0 or transiciones == 0 or total_superbalotas == 0:
        raise EntradaSimulacionInvalidaError("Historico sin sorteos, transiciones o superbalotas suficientes")
    return ValoresEstadisticos(
        numeradores=(
            _suma_de_cuadrados_centrados(conteos, n, total * k),
            max(conteos) - min(conteos),
            coincidencias,
            _suma_de_cuadrados_centrados([fila.apariciones for fila in superbalotas], m, total_superbalotas),
        ),
        denominadores=(n * total * k, 1, transiciones, m * total_superbalotas),
        total_sorteos=total,
        total_transiciones=transiciones,
        total_superbalotas=total_superbalotas,
    )


def _referencias(params: ParametrosJuego) -> tuple[Fraction | None, ...]:
    n = params.rango_max - params.rango_min + 1
    k = params.cantidad_numeros
    m = params.superbalota_max - params.superbalota_min + 1
    return (Fraction(n - k), None, Fraction(k * k, n), Fraction(m - 1))


def comparar_juego(historico: Sequence[ResultadoNumerico], params: ParametrosJuego, *, semilla: int,
                   iteraciones: int) -> ResultadoJuego:
    """Compara lo observado con `iteraciones` historicos simulados.
    p bilateral = min(1, 2·min(p_sup, p_inf)), con p_sup = (1+#{sim ≥ obs})/(1+B)
    y p_inf = (1+#{sim ≤ obs})/(1+B): nunca 0. Todo exacto (int/Fraction)."""
    validar_iteraciones(iteraciones)
    observados = calcular_estadisticas(historico, params)
    rng = Random(semilla)
    simulados: list[list[int]] = [[] for _ in ESTADISTICAS_AE49]
    for _ in range(iteraciones):
        valores = calcular_estadisticas(simular_historia(rng, historico, params), params)
        if valores.denominadores != observados.denominadores:
            raise RuntimeError("Un historico simulado cambio los denominadores: la numeracion no se conservo")
        for indice, numerador in enumerate(valores.numeradores):
            simulados[indice].append(numerador)

    comparaciones = []
    referencias = _referencias(params)
    for indice, nombre in enumerate(ESTADISTICAS_AE49):
        observado = observados.numeradores[indice]
        denominador = observados.denominadores[indice]
        mayores_o_iguales = menores_o_iguales = menores = total = total_cuadrados = 0
        for valor in simulados[indice]:
            mayores_o_iguales += valor >= observado
            menores_o_iguales += valor <= observado
            menores += valor < observado
            total += valor
            total_cuadrados += valor * valor
        iguales = menores_o_iguales - menores
        varianza = (
            Fraction(iteraciones * total_cuadrados - total * total, iteraciones * (iteraciones - 1) * denominador ** 2)
            if iteraciones > 1 else Fraction(0)
        )
        p_superior = Fraction(1 + mayores_o_iguales, 1 + iteraciones)
        p_inferior = Fraction(1 + menores_o_iguales, 1 + iteraciones)
        comparaciones.append(ComparacionEstadistica(
            nombre=nombre,
            observado=Fraction(observado, denominador),
            media=Fraction(total, iteraciones * denominador),
            varianza=varianza,
            referencia=referencias[indice],
            percentil=Fraction(2 * menores + iguales, 2 * iteraciones),
            p_valor=min(Fraction(1), 2 * min(p_superior, p_inferior)),
        ))
    return ResultadoJuego(
        codigo=params.codigo,
        total_sorteos=observados.total_sorteos,
        total_transiciones=observados.total_transiciones,
        total_superbalotas=observados.total_superbalotas,
        entrada_sha256=huella_entrada(params.codigo, historico),
        comparaciones=tuple(comparaciones),
    )


def validar_iteraciones(iteraciones) -> None:
    if isinstance(iteraciones, bool) or not isinstance(iteraciones, int) or iteraciones < 1:
        raise ValueError(f"iteraciones debe ser un entero >= 1, se recibio {iteraciones!r}")


def _valor_json(nombre: str, valor: Fraction):
    return int(valor) if nombre in _ESTADISTICAS_ENTERAS else float(valor)


def construir_reporte(revision_alembic: str, resultados: Sequence[ResultadoJuego], *, semilla: int,
                      iteraciones: int) -> dict:
    """Aplica Bonferroni UNA sola vez sobre las 8 comparaciones de la
    ejecucion (funcion existente del motor) y construye el JSON. Es el
    unico punto donde los valores exactos pasan a float."""
    if [r.codigo for r in resultados] != list(JUEGOS_AE49):
        raise ValueError(f"Se esperaban exactamente los juegos {JUEGOS_AE49} en orden")
    pruebas = [
        ResultadoTestEstadistico(
            nombre_test=f"montecarlo_{resultado.codigo}_{c.nombre}", elementos=("*",),
            estadistico=float(c.observado), grados_libertad=None, p_value=float(c.p_valor),
            p_value_ajustado=None, metodo_correccion=None, alpha=None, significativo=None,
        )
        for resultado in resultados for c in resultado.comparaciones
    ]
    if len(pruebas) != TAMANO_FAMILIA_AE49:
        raise ValueError(f"La familia debe tener exactamente {TAMANO_FAMILIA_AE49} comparaciones")
    ajustadas = iter(aplicar_correccion_bonferroni(pruebas, alpha=ALPHA_AE49))

    juegos = []
    for resultado in resultados:
        estadisticas = []
        for c in resultado.comparaciones:
            ajustada = next(ajustadas)
            estadisticas.append({
                "nombre": c.nombre,
                "observado": _valor_json(c.nombre, c.observado),
                "media_simulada": float(c.media),
                "desviacion_simulada": math.sqrt(float(c.varianza)),
                "referencia_analitica": None if c.referencia is None else float(c.referencia),
                "percentil_observado": float(c.percentil),
                "p_valor_empirico": ajustada.p_value,
                "p_valor_ajustado_bonferroni": ajustada.p_value_ajustado,
                "supera_umbral_exploratorio": bool(ajustada.significativo),
            })
        juegos.append({
            "codigo": resultado.codigo,
            "total_sorteos": resultado.total_sorteos,
            "total_transiciones": resultado.total_transiciones,
            "total_superbalotas": resultado.total_superbalotas,
            "entrada_sha256": resultado.entrada_sha256,
            "estadisticas": estadisticas,
        })
    return {
        "esquema": ESQUEMA_AE49,
        "caracter": CARACTER_AE49,
        "alembic_revision": revision_alembic,
        "parametros": {
            "semilla": semilla, "iteraciones": iteraciones, "generador": GENERADOR_AE49,
            "estadisticas": list(ESTADISTICAS_AE49),
        },
        "rango_principal": {"desde": RANGO_PRINCIPAL_AE49[0], "hasta": RANGO_PRINCIPAL_AE49[1], "tramos": TEXTO_TRAMOS},
        "familia_comparaciones": {
            "metodo": "bonferroni", "tamano": TAMANO_FAMILIA_AE49, "alcance": "ocho_comparaciones_de_esta_ejecucion",
            "alpha": ALPHA_AE49, "cobertura": COBERTURA_AJUSTE,
        },
        "juegos": juegos,
        "nota": NOTA_AE49,
    }
