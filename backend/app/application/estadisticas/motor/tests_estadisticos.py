"""
Motor de tests estadísticos — infraestructura de inferencia (Etapa J,
Paso 12, primera mitad).

A diferencia de todo el resto del motor (que solo describe lo
ocurrido), este módulo hace INFERENCIA: determina si una desviación
observada es compatible con el azar, con el rigor que el proyecto
exige desde el enunciado original -nunca declarar "significativo" un
resultado aislado cuando se testean muchos números/pares a la vez,
sin corrección por comparaciones múltiples.

No recibe `ResultadoNumerico` ni `ResultadoColorLoto`, y no conoce
`hasta_numero_sorteo` ni `corte_temporal.py`: opera exclusivamente
sobre magnitudes YA CALCULADAS por otros módulos del motor
(`FrecuenciaObservada`, `ProbabilidadTeorica`), que ya aplicaron el
corte temporal antes de producir esos valores. La garantía anti-fuga
se hereda intacta de quien produjo esos datos -no hay filtrado que
duplicar aquí.

Única dependencia externa del motor completo: `scipy.stats` (más su
base `numpy`), aprobada explícitamente para esta etapa. El estadístico
chi-cuadrado en sí es aritmética simple, pero convertirlo en un
p-value exige la función de distribución acumulada chi-cuadrado -no
es aritmética elemental, y reimplementarla a mano habría arriesgado
exactamente el tipo de error numérico sutil que este proyecto ha
evitado sistemáticamente al no reimplementar combinatoria/probabilidad
ambigua en otros módulos.

Advertencia estadística central de este módulo: un resultado
"significativo" en un sorteo genuinamente aleatorio NO implica ventaja
explotable -puede ser ruido esperado por comparaciones múltiples (con
39-43 números o cientos de pares testeados a la vez, algunos p-values
bajos aparecen por puro azar), o en el peor caso indicaría un sesgo
mecánico del sorteo físico -una pregunta operativa/regulatoria, no una
señal de apuesta. `significativo` es estructuralmente imposible de
poner en True sin pasar primero por una corrección explícita: ninguna
función de este módulo puede "atajar" esa regla.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from scipy import stats

from app.application.estadisticas.motor.frecuencia import frecuencia_relativa_esperada
from app.application.estadisticas.tipos import (
    FrecuenciaObservada,
    ProbabilidadTeorica,
    ResultadoTestEstadistico,
)


def _validar_p_values(resultados: Sequence[ResultadoTestEstadistico], etiqueta: str) -> None:
    for r in resultados:
        if r.p_value is None:
            raise ValueError(
                f"{etiqueta}: '{r.nombre_test}' sobre {r.elementos} tiene p_value=None "
                f"-no se puede corregir un test que no calculó su p-value."
            )
        if not (0.0 <= r.p_value <= 1.0):
            raise ValueError(
                f"{etiqueta}: '{r.nombre_test}' sobre {r.elementos} tiene p_value={r.p_value}, "
                f"fuera del rango válido [0,1]."
            )


def chi_cuadrado_bondad_ajuste(
    observados: Sequence[FrecuenciaObservada], probabilidad_esperada: ProbabilidadTeorica,
) -> ResultadoTestEstadistico:
    """UN solo test sobre la distribución COMPLETA (no un test por
    categoría): ¿son las frecuencias observadas de las N categorías
    compatibles con la frecuencia esperada uniforme
    `probabilidad_esperada` aplicada por igual a todas?

        estadistico = sum((O_i - E_i)^2 / E_i)   para i en 1..N
        E_i = probabilidad_esperada.probabilidad * total_sorteos  (igual para todo i)
        grados_libertad = N - 1

    p_value vía la distribución chi-cuadrado de SciPy
    (`scipy.stats.chi2.sf`), nunca reimplementada a mano.

    ValueError si: menos de 2 categorías (no hay grados de libertad
    para testear nada); las categorías no comparten el mismo
    total_sorteos (señal de que `observados` no describe
    consistentemente un solo conjunto de sorteos); total_sorteos == 0
    (no hay datos); probabilidad_esperada fuera de (0,1] (una
    probabilidad <=0 produce E_i=0, división indefinida)."""
    if len(observados) < 2:
        raise ValueError(
            f"chi_cuadrado_bondad_ajuste: se requieren al menos 2 categorías, se recibieron {len(observados)}"
        )

    totales = {f.total_sorteos for f in observados}
    if len(totales) > 1:
        raise ValueError(
            f"chi_cuadrado_bondad_ajuste: las categorías tienen total_sorteos inconsistente entre sí: "
            f"{sorted(totales)} -no describen el mismo conjunto de sorteos."
        )
    total_sorteos = totales.pop()
    if total_sorteos == 0:
        raise ValueError("chi_cuadrado_bondad_ajuste: total_sorteos es 0 -no hay datos que testear.")

    if not (0.0 < probabilidad_esperada.probabilidad <= 1.0):
        raise ValueError(
            f"chi_cuadrado_bondad_ajuste: probabilidad_esperada.probabilidad="
            f"{probabilidad_esperada.probabilidad} debe estar en (0,1]."
        )

    esperado_por_categoria = probabilidad_esperada.probabilidad * total_sorteos
    estadistico = sum(
        (f.apariciones - esperado_por_categoria) ** 2 / esperado_por_categoria for f in observados
    )
    grados_libertad = len(observados) - 1
    p_value = float(stats.chi2.sf(estadistico, grados_libertad))

    return ResultadoTestEstadistico(
        nombre_test="chi2_bondad_ajuste",
        elementos=("*",),
        estadistico=estadistico,
        grados_libertad=grados_libertad,
        p_value=p_value,
        p_value_ajustado=None,
        metodo_correccion=None,
        alpha=None,
        significativo=None,
    )


def chi_cuadrado_uniformidad(
    observados: Sequence[FrecuenciaObservada], extraidos_por_sorteo: int, *, sin_reemplazo: bool,
) -> ResultadoTestEstadistico:
    """Fase 5: ¿son las apariciones de las N categorías compatibles con un sorteo uniforme?
    Reutiliza `chi_cuadrado_bondad_ajuste` con la probabilidad por sorteo K/N
    (`frecuencia_relativa_esperada`) y, si el sorteo extrae K valores DISTINTOS (sin reemplazo),
    corrige el estadístico.

    Con K de N sin reemplazo, cada sorteo aporta exactamente K apariciones correlacionadas
    negativamente entre sí: bajo H0 y cuando crece el número de sorteos, X = sum((O_i - E_i)^2 / E_i)
    tiende a (N-K)/(N-1) * chi2(N-1), no a chi2(N-1) (covarianza de la hipergeométrica multivariante).
    El estadístico corregido X * (N-1)/(N-K) tiene como distribución límite chi2(N-1); sin la
    corrección el test es conservador (Baloto, K=5 de N=43: X se infla por 42/38). Con K=1
    (superbalota) el factor es 1. Con reemplazo (balotas independientes de ColorLoto, multinomial), no
    hay corrección.

    El p-value es ASINTÓTICO en los dos casos: sale de esa chi2(N-1) límite. El factor corrige la
    escala del estadístico, pero no convierte el contraste en una prueba exacta para una muestra
    finita; con frecuencias esperadas pequeñas (< 5) la aproximación es poco fiable y quien presenta
    el resultado debe avisarlo.

    `estadistico` es el corregido; `grados_libertad` = N-1. Descriptivo: un p-value bajo no indica
    qué valores saldrán, y uno alto no prueba que el sorteo sea uniforme."""
    n = len(observados)
    if extraidos_por_sorteo <= 0:
        raise ValueError(f"chi_cuadrado_uniformidad: extraidos_por_sorteo debe ser positivo ({extraidos_por_sorteo})")
    if sin_reemplazo and extraidos_por_sorteo >= n:
        raise ValueError(
            f"chi_cuadrado_uniformidad: sin reemplazo se requieren mas categorias ({n}) que extraidos ({extraidos_por_sorteo})")
    probabilidad = frecuencia_relativa_esperada(extraidos_por_sorteo, n)
    base = chi_cuadrado_bondad_ajuste(
        observados, ProbabilidadTeorica(valor="*", probabilidad=probabilidad,
                                        metodo=f"K/N = {extraidos_por_sorteo}/{n}"))
    if not sin_reemplazo:
        return base
    estadistico = base.estadistico * (n - 1) / (n - extraidos_por_sorteo)
    return dataclasses.replace(base, nombre_test="chi2_uniformidad_sin_reemplazo", estadistico=estadistico,
                               p_value=float(stats.chi2.sf(estadistico, base.grados_libertad)))


def intervalo_confianza_proporcion(
    apariciones: int, total_sorteos: int, nivel_confianza: float = 0.95,
) -> tuple[float, float]:
    """Intervalo de confianza de Wilson score para una proporción
    observada (apariciones/total_sorteos). Se prefiere sobre la
    aproximación normal simple porque permanece bien definido y
    dentro de [0,1] incluso en los extremos (apariciones=0 o
    apariciones=total_sorteos), donde la aproximación normal produce
    límites inválidos (negativos o mayores a 1).

    Fórmula (z = cuantil normal para el nivel de confianza pedido,
    vía scipy.stats.norm.ppf; p_hat = apariciones/total_sorteos):

        centro = (p_hat + z^2/(2n)) / (1 + z^2/n)
        margen = z/(1 + z^2/n) * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))
        intervalo = (centro - margen, centro + margen)

    ValueError si: total_sorteos <= 0; apariciones < 0 o > total_sorteos;
    nivel_confianza fuera de (0,1)."""
    if total_sorteos <= 0:
        raise ValueError(f"intervalo_confianza_proporcion: total_sorteos debe ser positivo, se recibió {total_sorteos}")
    if apariciones < 0 or apariciones > total_sorteos:
        raise ValueError(
            f"intervalo_confianza_proporcion: apariciones={apariciones} debe estar en [0,{total_sorteos}]"
        )
    if not (0.0 < nivel_confianza < 1.0):
        raise ValueError(
            f"intervalo_confianza_proporcion: nivel_confianza={nivel_confianza} debe estar en (0,1)"
        )

    n = total_sorteos
    p_hat = apariciones / n
    z = float(stats.norm.ppf(1 - (1 - nivel_confianza) / 2))
    z2 = z * z

    centro = (p_hat + z2 / (2 * n)) / (1 + z2 / n)
    margen = (z / (1 + z2 / n)) * ((p_hat * (1 - p_hat) / n) + (z2 / (4 * n * n))) ** 0.5

    limite_inferior = max(0.0, centro - margen)
    limite_superior = min(1.0, centro + margen)
    return (limite_inferior, limite_superior)


def aplicar_correccion_bonferroni(
    resultados: Sequence[ResultadoTestEstadistico], alpha: float = 0.05,
) -> list[ResultadoTestEstadistico]:
    """p_value_ajustado = min(1, p_value * m), donde m es la cantidad
    de tests en `resultados`. significativo = p_value_ajustado < alpha
    -nunca se deriva del p_value crudo. Devuelve una lista NUEVA de
    objetos NUEVOS (dataclasses.replace, ya que ResultadoTestEstadistico
    es frozen); nunca muta `resultados` ni sus elementos.

    Lista vacía -> [] (cero tests que corregir es un resultado
    honesto, no una operación indefinida)."""
    if not resultados:
        return []
    _validar_p_values(resultados, "aplicar_correccion_bonferroni")

    m = len(resultados)
    corregidos = []
    for r in resultados:
        p_ajustado = min(1.0, r.p_value * m)
        corregidos.append(
            dataclasses.replace(
                r, p_value_ajustado=p_ajustado, metodo_correccion="bonferroni",
                alpha=alpha, significativo=p_ajustado < alpha,
            )
        )
    return corregidos


def aplicar_correccion_benjamini_hochberg(
    resultados: Sequence[ResultadoTestEstadistico], alpha: float = 0.05,
) -> list[ResultadoTestEstadistico]:
    """Procedimiento de Benjamini-Hochberg (control de la tasa de
    falsos descubrimientos): ordena los p-values ascendente,
    calcula el ajuste crudo p_(i) * m / i para cada posición i
    (1-indexado), y MONOTONIZA tomando el mínimo acumulado desde el
    final hacia el principio (q_(i) = min(ajuste_crudo(i), q_(i+1))),
    garantizando que los p-values ajustados nunca decrezcan al
    alejarse del extremo más significativo. Empates en el p-value se
    manejan naturalmente por el propio procedimiento de monotonización,
    sin necesitar una rama especial.

    Devuelve una lista NUEVA, en el MISMO ORDEN que `resultados`
    (no en el orden ordenado internamente) -nunca muta la entrada.

    Lista vacía -> []."""
    if not resultados:
        return []
    _validar_p_values(resultados, "aplicar_correccion_benjamini_hochberg")

    m = len(resultados)
    indices_ordenados = sorted(range(m), key=lambda i: resultados[i].p_value)

    ajustes_crudos = [0.0] * m
    for posicion, indice_original in enumerate(indices_ordenados):
        rango = posicion + 1  # 1-indexado
        ajustes_crudos[posicion] = resultados[indice_original].p_value * m / rango

    ajustes_monotonizados = [0.0] * m
    minimo_acumulado = 1.0
    for posicion in range(m - 1, -1, -1):
        minimo_acumulado = min(minimo_acumulado, ajustes_crudos[posicion])
        ajustes_monotonizados[posicion] = minimo_acumulado

    p_ajustado_por_indice_original: dict[int, float] = {}
    for posicion, indice_original in enumerate(indices_ordenados):
        p_ajustado_por_indice_original[indice_original] = min(1.0, ajustes_monotonizados[posicion])

    corregidos = []
    for i, r in enumerate(resultados):
        p_ajustado = p_ajustado_por_indice_original[i]
        corregidos.append(
            dataclasses.replace(
                r, p_value_ajustado=p_ajustado, metodo_correccion="benjamini_hochberg",
                alpha=alpha, significativo=p_ajustado < alpha,
            )
        )
    return corregidos
