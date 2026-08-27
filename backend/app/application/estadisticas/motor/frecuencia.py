"""
Motor de frecuencia (Paso 4).

Igual que `generales.py`: funciones puras, sin conocimiento de
infraestructura. La distinción entre frecuencia observada (conteo
histórico) y probabilidad teórica (derivada de las reglas del juego)
se mantiene ESTRUCTURALMENTE -son dataclasses distintos, nunca se
fusionan en un solo número. Ninguna función de este módulo debe
interpretarse como evidencia de la probabilidad de que un valor
aparezca en el siguiente sorteo: son estadística descriptiva de lo
ya ocurrido.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.application.estadisticas.tipos import (
    FeatureCandidata,
    FilaFrecuencia,
    FrecuenciaObservada,
    ProbabilidadTeorica,
    ResultadoColorLoto,
    ResultadoNumerico,
)


def frecuencia_relativa_esperada(k: int, n: int) -> float:
    """K/N: valor esperado de la frecuencia relativa
    (apariciones/total_sorteos) de un valor específico bajo azar
    uniforme, donde N es el tamaño del universo de valores posibles y
    K la cantidad de elementos elegidos por sorteo.

    Es la MISMA fórmula tanto si el sorteo elige sin repetición (K/N
    es la probabilidad clásica de selección: MiLoto, Baloto,
    superbalota con K=1) como si permite repetición dentro del
    sorteo (K/N es el valor esperado de conteo por sorteo: ColorLoto)
    -en ambos casos, por linealidad de la esperanza, el resultado es
    K/N. Ejemplo verificable a mano: ColorLoto colores, K=6 balotas,
    N=6 colores -> 1.0 (se espera cada color exactamente una vez por
    sorteo, en promedio).

    Lanza ValueError si n <= 0 (universo inválido)."""
    if n <= 0:
        raise ValueError(f"n debe ser positivo, se recibió n={n}")
    return k / n


def construir_tabla_frecuencia(
    frecuencias: Sequence[FrecuenciaObservada], k: int, n: int
) -> list[FilaFrecuencia]:
    """Une cada FrecuenciaObservada con la probabilidad teórica
    (misma para todo el pool, vía frecuencia_relativa_esperada) para
    producir la fila Número|Apariciones|Frecuencia|Esperada|
    Diferencia. Genérica: sirve para números, superbalota, colores y
    pares por igual -el llamador decide qué k/n corresponde."""
    esperada = frecuencia_relativa_esperada(k, n)
    metodo = f"K/N = {k}/{n}"

    filas = []
    for f in frecuencias:
        probabilidad_teorica = ProbabilidadTeorica(valor=f.valor, probabilidad=esperada, metodo=metodo)
        filas.append(
            FilaFrecuencia(
                valor=f.valor,
                apariciones=f.apariciones,
                frecuencia_observada=f,
                probabilidad_teorica=probabilidad_teorica,
                diferencia=f.frecuencia_relativa - esperada,
            )
        )
    return filas


def _validar_rango(valores: Sequence[int], rango_min: int, rango_max: int, etiqueta: str) -> None:
    fuera_de_rango = [v for v in valores if not (rango_min <= v <= rango_max)]
    if fuera_de_rango:
        raise ValueError(
            f"{etiqueta}: valores fuera del rango [{rango_min},{rango_max}]: {sorted(set(fuera_de_rango))}"
        )


def calcular_frecuencia_numeros(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int
) -> list[FrecuenciaObservada]:
    """Frecuencia de cada número del rango [rango_min, rango_max]
    dentro de los `numeros` principales -NUNCA incluye superbalota.
    Incluye TODOS los números del rango, incluso los que nunca
    aparecieron (apariciones=0), para que el ranking esté completo.
    Lanza ValueError si algún número del input cae fuera del rango
    (no corrige silenciosamente)."""
    total_sorteos = len(resultados)
    todos_los_numeros = [n for r in resultados for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_frecuencia_numeros")

    contador = Counter(todos_los_numeros)
    filas = []
    for numero in range(rango_min, rango_max + 1):
        apariciones = contador.get(numero, 0)
        frecuencia_relativa = (apariciones / total_sorteos) if total_sorteos else 0.0
        filas.append(
            FrecuenciaObservada(
                valor=str(numero), apariciones=apariciones,
                total_sorteos=total_sorteos, frecuencia_relativa=frecuencia_relativa,
            )
        )
    return filas


def calcular_frecuencia_superbalota(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int
) -> list[FrecuenciaObservada]:
    """Pool INDEPENDIENTE del principal -nunca se mezcla con
    calcular_frecuencia_numeros. `total_sorteos` cuenta solo los
    sorteos donde superbalota no es None (dato ausente se ignora, no
    se trata como 0 ni rompe el cálculo)."""
    superbalotas = [r.superbalota for r in resultados if r.superbalota is not None]
    _validar_rango(superbalotas, rango_min, rango_max, "calcular_frecuencia_superbalota")

    total_sorteos = len(superbalotas)
    contador = Counter(superbalotas)
    filas = []
    for numero in range(rango_min, rango_max + 1):
        apariciones = contador.get(numero, 0)
        frecuencia_relativa = (apariciones / total_sorteos) if total_sorteos else 0.0
        filas.append(
            FrecuenciaObservada(
                valor=str(numero), apariciones=apariciones,
                total_sorteos=total_sorteos, frecuencia_relativa=frecuencia_relativa,
            )
        )
    return filas


def calcular_frecuencia_numeros_colorloto(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int
) -> list[FrecuenciaObservada]:
    """Frecuencia del NÚMERO de la balota, ignorando su color. Cada
    balota de cada sorteo cuenta individualmente -un sorteo aporta
    hasta 6 conteos, no 1 (hay repetición permitida, así que
    frecuencia_relativa puede superar 1.0 para un número muy
    frecuente -es un valor esperado de conteo, no una probabilidad en
    [0,1]; ver docstring de frecuencia_relativa_esperada)."""
    total_sorteos = len(resultados)
    todos_los_numeros = [numero for r in resultados for numero, _ in r.pares]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_frecuencia_numeros_colorloto")

    contador = Counter(todos_los_numeros)
    filas = []
    for numero in range(rango_min, rango_max + 1):
        apariciones = contador.get(numero, 0)
        frecuencia_relativa = (apariciones / total_sorteos) if total_sorteos else 0.0
        filas.append(
            FrecuenciaObservada(
                valor=str(numero), apariciones=apariciones,
                total_sorteos=total_sorteos, frecuencia_relativa=frecuencia_relativa,
            )
        )
    return filas


def calcular_frecuencia_colores(
    resultados: Sequence[ResultadoColorLoto], colores_vigentes: Sequence[str]
) -> list[FrecuenciaObservada]:
    """Frecuencia del COLOR, ignorando el número. `colores_vigentes`
    se recibe desde afuera (vendrá de ColorRepository en la capa de
    orquestación) -el motor nunca conoce la paleta por su cuenta,
    igual que no conoce rangos de números por su cuenta. Un color
    presente en los datos pero ausente de `colores_vigentes` no hace
    perder el resto del cálculo: se agrega igual al resultado (nunca
    se descarta un dato silenciosamente), con su propio conteo."""
    total_sorteos = len(resultados)
    todos_los_colores = [color for r in resultados for _, color in r.pares]

    contador = Counter(todos_los_colores)
    colores_a_reportar = set(colores_vigentes) | set(contador.keys())

    filas = []
    for color in sorted(colores_a_reportar):
        apariciones = contador.get(color, 0)
        frecuencia_relativa = (apariciones / total_sorteos) if total_sorteos else 0.0
        filas.append(
            FrecuenciaObservada(
                valor=color, apariciones=apariciones,
                total_sorteos=total_sorteos, frecuencia_relativa=frecuencia_relativa,
            )
        )
    return filas


def calcular_frecuencia_pares_numero_color(
    resultados: Sequence[ResultadoColorLoto], rango_min: int, rango_max: int,
    colores_vigentes: Sequence[str],
) -> list[FrecuenciaObservada]:
    """Frecuencia del PAR (número, color) como unidad atómica (Paso
    13). valor = f"{numero}-{color_codigo}", p.ej. "5-ROJO". Incluye
    todas las combinaciones número×color del universo teórico
    (incluso con 0 apariciones), más cualquier par observado con un
    color fuera de `colores_vigentes` (nunca se pierde un dato)."""
    total_sorteos = len(resultados)
    todos_los_pares = [par for r in resultados for par in r.pares]
    _validar_rango([n for n, _ in todos_los_pares], rango_min, rango_max, "calcular_frecuencia_pares_numero_color")

    contador = Counter(todos_los_pares)
    colores_a_reportar = set(colores_vigentes) | {c for _, c in todos_los_pares}

    universo = {(n, c) for n in range(rango_min, rango_max + 1) for c in colores_a_reportar}
    universo |= set(todos_los_pares)  # nunca se pierde un par observado, aunque no esté en el universo teórico

    filas = []
    for numero, color in sorted(universo):
        apariciones = contador.get((numero, color), 0)
        frecuencia_relativa = (apariciones / total_sorteos) if total_sorteos else 0.0
        filas.append(
            FrecuenciaObservada(
                valor=f"{numero}-{color}", apariciones=apariciones,
                total_sorteos=total_sorteos, frecuencia_relativa=frecuencia_relativa,
            )
        )
    return filas


def frecuencia_a_feature(
    frecuencia: FrecuenciaObservada, calculado_hasta_sorteo: int, ventana: str = "historico_completo"
) -> FeatureCandidata:
    """Envuelve una FrecuenciaObservada como FeatureCandidata,
    marcando explícitamente el corte temporal usado. Es la respuesta
    concreta a cómo una frecuencia se convierte en variable de un
    futuro modelo: cualquier frecuencia que vaya a usarse después
    como feature pasa por aquí, nunca se usa el FrecuenciaObservada
    crudo directamente como feature."""
    return FeatureCandidata(
        nombre=frecuencia.valor,
        valor=frecuencia.frecuencia_relativa,
        calculado_hasta_sorteo=calculado_hasta_sorteo,
        ventana=ventana,
    )
