"""
Motor de tests de independencia (Etapa K, Paso 12 - segunda mitad).

Para cada par/trío del universo TEÓRICO COMPLETO (todas las C(N,2) o
C(N,3) combinaciones posibles, incluyendo las nunca observadas -ver
justificación abajo), testea si la coocurrencia observada es
compatible con lo que el propio mecanismo de sorteo sin reemplazo
predice bajo H0.

    H0: la frecuencia observada de la combinación es compatible con
        la frecuencia esperada bajo extracción uniforme sin reemplazo.
    H1: la frecuencia observada presenta una desviación incompatible
        con ese modelo.

Probabilidad teórica bajo H0 (K números elegidos de N, sin reemplazo):

    P(pareja) = K(K-1) / (N(N-1))
    P(trío)   = K(K-1)(K-2) / (N(N-1)(N-2))

Método: test binomial EXACTO (`scipy.stats.binomtest`,
`alternative="two-sided"`), no una aproximación chi-cuadrado. Razón:
el chi-cuadrado de bondad de ajuste asume una aproximación asintótica
que se degrada cuando la frecuencia esperada es pequeña (regla
práctica: E<5) -algo que ocurre con facilidad aquí, ya que P(pareja)/
P(trío) son fracciones pequeñas y no todo histórico tiene sorteos
suficientes para que E sea grande. El test binomial exacto no depende
de ninguna aproximación asintótica: es válido para cualquier tamaño
de E, sin necesidad de ninguna rama especial ni umbral que vigilar.

Universo completo, no solo lo observado: limitar el test a
combinaciones YA observadas introduciría sesgo de selección -una
combinación que NUNCA coocurrió (soporte=0) con una E moderada es
evidencia de desviación tan válida como una combinación con soporte
alto, y excluirla sesgaría el conjunto de hipótesis testeadas hacia
"lo que ya llamó la atención". Es una decisión deliberadamente
distinta al comportamiento descriptivo de `coocurrencia.py`
(`calcular_coocurrencia_pares`/`_trios`), que sigue reportando
únicamente lo observado -aquí, para inferencia, la completitud del
universo de hipótesis es un requisito de validez estadística, no una
preferencia de presentación.

ColorLoto: NO se implementa en esta etapa. Un test de independencia
exige una probabilidad teórica de coocurrencia bajo H0, y esa
probabilidad para ColorLoto depende de la misma combinatoria-con-
repetición que `probabilidad.py` (Etapa D) y `coocurrencia.py`
(Etapa I) ya se negaron a calcular -`ColorLotoGame.sample_space_size()`
documenta esa fórmula como un supuesto sin verificar contra el
reglamento oficial. Tercera vez que ColorLoto queda diferido por la
misma razón, de forma consistente.

`grados_libertad` queda en None en todos los resultados: un test
binomial exacto no tiene ese concepto, y forzar un valor sería
inventar información que no existe. `p_value_ajustado`,
`metodo_correccion`, `alpha` y `significativo` quedan en None -la
corrección por comparaciones múltiples (con hasta miles de tests
generados aquí) es responsabilidad exclusiva de
`aplicar_correccion_bonferroni`/`aplicar_correccion_benjamini_hochberg`
(Etapa J), nunca duplicada ni anticipada en este módulo.

Ningún resultado de este módulo implica capacidad predictiva. Incluso
con p_value_ajustado < alpha, eso solo significa que los datos
presentan evidencia contra el modelo nulo bajo los supuestos
establecidos -nunca "esta combinación tiene más probabilidad de salir
en el próximo sorteo".
"""
from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations

from scipy.stats import binomtest

from app.application.estadisticas.motor.coocurrencia import _contar_coocurrencias_crudo
from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.tipos import ResultadoNumerico, ResultadoTestEstadistico


def _validar_rango(valores: Sequence[int], rango_min: int, rango_max: int, etiqueta: str) -> None:
    fuera_de_rango = [v for v in valores if not (rango_min <= v <= rango_max)]
    if fuera_de_rango:
        raise ValueError(
            f"{etiqueta}: valores fuera del rango [{rango_min},{rango_max}]: {sorted(set(fuera_de_rango))}"
        )


def _validar_parametros_estructurales(
    rango_min: int, rango_max: int, cantidad_numeros: int, tamano_combinacion: int, etiqueta: str
) -> None:
    if rango_max < rango_min:
        raise ValueError(f"{etiqueta}: rango_max ({rango_max}) no puede ser menor que rango_min ({rango_min})")
    universo = rango_max - rango_min + 1
    if cantidad_numeros < tamano_combinacion:
        raise ValueError(
            f"{etiqueta}: cantidad_numeros ({cantidad_numeros}) debe ser >= {tamano_combinacion} "
            f"para poder formar combinaciones de {tamano_combinacion} elementos"
        )
    if universo < tamano_combinacion:
        raise ValueError(
            f"{etiqueta}: el universo [{rango_min},{rango_max}] tiene {universo} valores, "
            f"insuficiente para formar combinaciones de {tamano_combinacion} elementos"
        )
    if cantidad_numeros > universo:
        raise ValueError(
            f"{etiqueta}: cantidad_numeros ({cantidad_numeros}) no puede superar el tamaño "
            f"del universo ({universo})"
        )


def _probabilidad_teorica_coocurrencia(n: int, k: int, tamano_combinacion: int) -> float:
    """P(los `tamano_combinacion` elementos específicos caen todos en
    una selección aleatoria de k de n, sin reemplazo). K(K-1).../
    [N(N-1)...] -expandida directamente por claridad, algebraicamente
    equivalente a la forma C(N-t,K-t)/C(N,K) ya usada en
    coocurrencia.py."""
    numerador = 1
    denominador = 1
    for i in range(tamano_combinacion):
        numerador *= k - i
        denominador *= n - i
    return numerador / denominador


def _testear_universo(
    listas_de_numeros: list[list[int]], rango_min: int, rango_max: int, tamano_combinacion: int,
    probabilidad_teorica: float, total_sorteos: int, nombre_test: str,
) -> list[ResultadoTestEstadistico]:
    conteo_observado = _contar_coocurrencias_crudo(listas_de_numeros, tamano_combinacion)

    resultados = []
    for combinacion in combinations(range(rango_min, rango_max + 1), tamano_combinacion):
        soporte = conteo_observado.get(combinacion, 0)
        resultado_test = binomtest(soporte, total_sorteos, probabilidad_teorica, alternative="two-sided")
        resultados.append(
            ResultadoTestEstadistico(
                nombre_test=nombre_test,
                elementos=tuple(str(n) for n in combinacion),
                estadistico=float(soporte),
                grados_libertad=None,
                p_value=float(resultado_test.pvalue),
                p_value_ajustado=None,
                metodo_correccion=None,
                alpha=None,
                significativo=None,
            )
        )
    return resultados


def calcular_independencia_pares(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[ResultadoTestEstadistico]:
    """Un test binomial exacto por cada par del universo teórico
    completo C(N,2) -incluye pares con soporte=0. ValueError si
    total_sorteos==0 (no hay datos que testear), o si los parámetros
    estructurales son imposibles (rango/cantidad_numeros inválidos
    para formar pares)."""
    _validar_parametros_estructurales(rango_min, rango_max, cantidad_numeros, 2, "calcular_independencia_pares")

    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    if not historico:
        raise ValueError("calcular_independencia_pares: no hay sorteos que testear (0 resultados tras el corte)")

    todos_los_numeros = [n for r in historico for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_independencia_pares")

    universo = rango_max - rango_min + 1
    probabilidad_teorica = _probabilidad_teorica_coocurrencia(universo, cantidad_numeros, 2)

    listas = [list(r.numeros) for r in historico]
    return _testear_universo(
        listas, rango_min, rango_max, 2, probabilidad_teorica, len(historico), "binomial_exacto_independencia_par",
    )


def calcular_independencia_trios(
    resultados: Sequence[ResultadoNumerico], rango_min: int, rango_max: int, cantidad_numeros: int,
    hasta_numero_sorteo: int | None = None,
) -> list[ResultadoTestEstadistico]:
    """Igual que calcular_independencia_pares, para tríos: universo
    teórico completo C(N,3), probabilidad K(K-1)(K-2)/(N(N-1)(N-2))."""
    _validar_parametros_estructurales(rango_min, rango_max, cantidad_numeros, 3, "calcular_independencia_trios")

    historico = filtrar_por_corte_temporal(resultados, hasta_numero_sorteo)
    if not historico:
        raise ValueError("calcular_independencia_trios: no hay sorteos que testear (0 resultados tras el corte)")

    todos_los_numeros = [n for r in historico for n in r.numeros]
    _validar_rango(todos_los_numeros, rango_min, rango_max, "calcular_independencia_trios")

    universo = rango_max - rango_min + 1
    probabilidad_teorica = _probabilidad_teorica_coocurrencia(universo, cantidad_numeros, 3)

    listas = [list(r.numeros) for r in historico]
    return _testear_universo(
        listas, rango_min, rango_max, 3, probabilidad_teorica, len(historico), "binomial_exacto_independencia_trio",
    )
