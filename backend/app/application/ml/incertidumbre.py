"""
Cuantificacion de incertidumbre y regla de parada cientifica -Etapa
AE-39, validada.

Analisis puro, determinista y por juego de la incertidumbre de las
diferencias externas de AE-38 frente al baseline uniforme -nunca
reentrena Regresion Logistica ni Random Forest, nunca invoca el caso
de uso costoso de AE-38, nunca consulta repositorios ni lee archivos.
Recibe un `ReporteComparacionFamiliasJuego` ya construido y devuelve
un `ReporteIncertidumbreJuego` inmutable. Permanece puro -no importa
SQLAlchemy, FastAPI ni Jinja2; no importa scikit-learn -unico archivo
de `application/ml` con esa dependencia real es `modelo.py`, nunca
este modulo.

La unidad de remuestreo es el BLOQUE EXTERNO COMPLETO, nunca las
filas candidato-sorteo -18 bloques reales por juego, no 15480 filas;
las filas dentro de un bloque no son observaciones independientes."""
from __future__ import annotations

import math
import random
from collections.abc import Sequence

from app.application.ml.tipos import (
    DecisionContinuidadML,
    IntervaloBootstrap,
    PoliticaReaperturaML,
    ReporteComparacionFamiliasJuego,
    ReporteIncertidumbreJuego,
    ResultadoBloqueExternoAE38,
    ResultadoIncertidumbreMetrica,
    ResumenDiferenciasBloques,
)

JUEGOS_AUTORIZADOS_AE39 = frozenset({"BALOTO", "BALOTO_REVANCHA"})
"""Mismo conjunto cerrado exacto de AE-35/AE-36/AE-37/AE-38 -nunca se
mezclan Baloto y Baloto Revancha; cada juego se decide por separado."""

REPLICAS_BOOTSTRAP_DEFECTO = 10_000
SEMILLA_BOOTSTRAP_DEFECTO = 42
NIVEL_CONFIANZA_DEFECTO = 0.95
PROXIMO_HOLDOUT_INICIO = 2706
MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT = 100

TOLERANCIA_DIFERENCIA_ALMACENADA = 1e-9
"""Tolerancia numerica explicita para verificar que
`diferencia_vs_uniforme` de cada bloque coincide con
`uniforme.metricas - modelo.metricas` -nunca una comparacion de
igualdad exacta de punto flotante."""

TOLERANCIA_DEGRADACION_SECUNDARIA = 0.02
"""Tolerancia explicita, documentada, para el criterio de "ausencia
de degradacion material" en Precision@5/Recall@5 -Etapa AE-39: el
modelo puede quedar hasta 2 puntos porcentuales por debajo del
uniforme en cada metrica secundaria sin que eso, por si solo,
bloquee una decision `EVIDENCIA_EXPLORATORIA_DE_MEJORA` que ya
cumplio los cinco criterios anteriores (mas estrictos, sobre las
metricas principales); una degradacion mayor a esta tolerancia si
bloquea la decision positiva, nunca al reves -las metricas
secundarias nunca pueden CREAR una decision positiva por si solas."""


class ReporteIncertidumbreInvalidoError(ValueError):
    """Excepcion propia y pequena de AE-39 -nunca `assert` para
    validaciones publicas de dominio. Cubre: reporte sin bloques,
    menos de dos bloques, bloques duplicados/fuera de orden/
    solapados, metricas o diferencias no finitas, tamanos de bloque
    no positivos, diferencia almacenada inconsistente con las
    metricas, ausencia o duplicidad del baseline uniforme, juego no
    autorizado, y parametros de bootstrap invalidos."""


def _validar_reporte(reporte: ReporteComparacionFamiliasJuego) -> None:
    if reporte.codigo_juego not in JUEGOS_AUTORIZADOS_AE39:
        raise ReporteIncertidumbreInvalidoError(
            f"'{reporte.codigo_juego}' no esta autorizado para AE-39 -"
            f"unicamente {sorted(JUEGOS_AUTORIZADOS_AE39)}"
        )

    bloques = reporte.bloques_externos
    if len(bloques) == 0:
        raise ReporteIncertidumbreInvalidoError("El reporte no contiene ningun bloque externo")
    if len(bloques) < 2:
        raise ReporteIncertidumbreInvalidoError(
            f"Se requieren al menos 2 bloques externos para el bootstrap, hay {len(bloques)}"
        )

    inicios = [b.frontera_externa.bloque_externo_inicio for b in bloques]
    fines = [b.frontera_externa.bloque_externo_fin for b in bloques]

    if len(set(inicios)) != len(inicios):
        raise ReporteIncertidumbreInvalidoError("Bloques duplicados detectados (mismo inicio de bloque externo)")

    for i in range(len(bloques) - 1):
        if inicios[i + 1] <= inicios[i]:
            raise ReporteIncertidumbreInvalidoError(
                f"Bloques fuera de orden: el bloque {i + 1} inicia en {inicios[i + 1]}, "
                f"no estrictamente posterior al bloque {i} (inicio {inicios[i]})"
            )
        if inicios[i + 1] <= fines[i]:
            raise ReporteIncertidumbreInvalidoError(
                f"Bloques solapados: el bloque {i} termina en {fines[i]}, el bloque {i + 1} "
                f"inicia en {inicios[i + 1]}"
            )

    for i, b in enumerate(bloques):
        total_filas = b.resultado_modelo.metricas.total_filas
        if total_filas <= 0:
            raise ReporteIncertidumbreInvalidoError(f"El bloque {i} tiene un tamano no positivo: {total_filas}")

        ll_dif = b.diferencia_vs_uniforme.diferencia_log_loss
        br_dif = b.diferencia_vs_uniforme.diferencia_brier_score
        for nombre, valor in (("diferencia_log_loss", ll_dif), ("diferencia_brier_score", br_dif)):
            if valor != valor or valor in (float("inf"), float("-inf")):
                raise ReporteIncertidumbreInvalidoError(f"El bloque {i} tiene {nombre} no finita: {valor}")

        uniformes = [bl for bl in b.baselines_externos if bl.nombre == "uniforme"]
        if len(uniformes) == 0:
            raise ReporteIncertidumbreInvalidoError(f"El bloque {i} no contiene ningun baseline 'uniforme'")
        if len(uniformes) > 1:
            raise ReporteIncertidumbreInvalidoError(
                f"El bloque {i} contiene {len(uniformes)} baselines 'uniforme', se esperaba exactamente 1"
            )
        uniforme = uniformes[0]

        ll_esperada = uniforme.metricas.log_loss - b.resultado_modelo.metricas.log_loss
        br_esperada = uniforme.metricas.brier_score - b.resultado_modelo.metricas.brier_score
        if abs(ll_esperada - ll_dif) > TOLERANCIA_DIFERENCIA_ALMACENADA:
            raise ReporteIncertidumbreInvalidoError(
                f"El bloque {i}: diferencia_log_loss almacenada ({ll_dif}) no coincide con "
                f"uniforme-modelo ({ll_esperada}) dentro de la tolerancia {TOLERANCIA_DIFERENCIA_ALMACENADA}"
            )
        if abs(br_esperada - br_dif) > TOLERANCIA_DIFERENCIA_ALMACENADA:
            raise ReporteIncertidumbreInvalidoError(
                f"El bloque {i}: diferencia_brier_score almacenada ({br_dif}) no coincide con "
                f"uniforme-modelo ({br_esperada}) dentro de la tolerancia {TOLERANCIA_DIFERENCIA_ALMACENADA}"
            )


def _percentil(valores_ordenados: Sequence[float], q: float) -> float:
    """Percentil con interpolacion lineal entre los dos puntos de
    datos mas cercanos -mismo metodo que `numpy.percentile` con
    `interpolation='linear'` (su valor por defecto), reimplementado
    aqui explicitamente para no depender de NumPy. `q` en `[0,1]`."""
    n = len(valores_ordenados)
    if n == 1:
        return valores_ordenados[0]
    indice = q * (n - 1)
    indice_bajo = math.floor(indice)
    indice_alto = math.ceil(indice)
    if indice_bajo == indice_alto:
        return valores_ordenados[int(indice)]
    fraccion = indice - indice_bajo
    return valores_ordenados[indice_bajo] + (valores_ordenados[indice_alto] - valores_ordenados[indice_bajo]) * fraccion


def _bootstrap_diferencia_agregada(
    diferencias: Sequence[float], pesos: Sequence[float], nivel_confianza: float, replicas: int, semilla: int,
) -> IntervaloBootstrap:
    """Bootstrap no parametrico sobre bloques completos -remuestrea
    CON reemplazo el mismo numero de bloques que el reporte original
    en cada replica, usando exclusivamente una instancia local de
    `random.Random` (nunca el modulo global `random`, nunca
    paralelismo). Cada replica calcula el promedio ponderado por
    `total_filas` de los bloques efectivamente seleccionados en esa
    replica -nunca asume que todos los bloques tienen el mismo
    tamano."""
    if not (0.0 < nivel_confianza < 1.0):
        raise ReporteIncertidumbreInvalidoError(f"nivel_confianza debe estar en (0,1), recibido {nivel_confianza}")
    if replicas <= 0:
        raise ReporteIncertidumbreInvalidoError(f"replicas debe ser positivo, recibido {replicas}")

    n = len(diferencias)
    rng = random.Random(semilla)
    estimaciones: list[float] = []

    for _ in range(replicas):
        indices_muestra = [rng.randrange(n) for _ in range(n)]
        peso_total = sum(pesos[i] for i in indices_muestra)
        suma_ponderada = sum(diferencias[i] * pesos[i] for i in indices_muestra)
        estimaciones.append(suma_ponderada / peso_total)

    estimaciones.sort()
    alfa = 1.0 - nivel_confianza
    limite_inferior = _percentil(estimaciones, alfa / 2)
    limite_superior = _percentil(estimaciones, 1 - alfa / 2)

    return IntervaloBootstrap(
        limite_inferior=limite_inferior, limite_superior=limite_superior,
        nivel_confianza=nivel_confianza, replicas=replicas, semilla=semilla,
    )


def _prueba_signos_exacta(diferencias: Sequence[float]) -> float:
    """Prueba de signos exacta bilateral -excluye unicamente los
    empates exactos (`diferencia == 0.0`). Usa la distribucion
    binomial EXACTA bajo `p=0.5` mediante `math.comb`, nunca una
    aproximacion normal -apropiado dado el numero reducido de
    bloques (18 para los datos reales de AE-38). Devuelve `1.0`
    cuando todos los bloques estan empatados -sin evidencia de
    ningun signo, nunca una division por cero."""
    positivos = sum(1 for d in diferencias if d > 0)
    negativos = sum(1 for d in diferencias if d < 0)
    n = positivos + negativos
    if n == 0:
        return 1.0

    k = min(positivos, negativos)
    probabilidad_total = 2 ** n
    probabilidad_una_cola = sum(math.comb(n, i) for i in range(0, k + 1)) / probabilidad_total
    return min(1.0, 2 * probabilidad_una_cola)


def _resumen_diferencias_bloques(diferencias: Sequence[float]) -> ResumenDiferenciasBloques:
    mejora = sum(1 for d in diferencias if d > 0)
    empeoramiento = sum(1 for d in diferencias if d < 0)
    empate = sum(1 for d in diferencias if d == 0)
    n = len(diferencias)

    ordenados = sorted(diferencias)
    mediana = _percentil(ordenados, 0.5)
    media = sum(diferencias) / n
    if n > 1:
        varianza_muestral = sum((d - media) ** 2 for d in diferencias) / (n - 1)
        desviacion = math.sqrt(varianza_muestral)
    else:
        desviacion = 0.0

    return ResumenDiferenciasBloques(
        bloques_con_mejora=mejora,
        bloques_con_empeoramiento=empeoramiento,
        bloques_empatados=empate,
        proporcion_con_mejora=mejora / n,
        mediana=mediana,
        minimo=min(diferencias),
        maximo=max(diferencias),
        desviacion_estandar=desviacion,
        valor_p_signos=_prueba_signos_exacta(diferencias),
    )


def _analizar_metrica(
    nombre_metrica: str, diferencias: Sequence[float], pesos: Sequence[float],
    nivel_confianza: float, replicas: int, semilla: int,
) -> ResultadoIncertidumbreMetrica:
    total_peso = sum(pesos)
    diferencia_puntual = sum(d * p for d, p in zip(diferencias, pesos)) / total_peso
    intervalo = _bootstrap_diferencia_agregada(diferencias, pesos, nivel_confianza, replicas, semilla)
    resumen = _resumen_diferencias_bloques(diferencias)
    return ResultadoIncertidumbreMetrica(
        nombre_metrica=nombre_metrica, diferencia_puntual_agregada=diferencia_puntual,
        intervalo_bootstrap=intervalo, resumen_bloques=resumen,
    )


def _metrica_uniforme(bloque: ResultadoBloqueExternoAE38, atributo: str) -> float:
    uniforme = next(bl for bl in bloque.baselines_externos if bl.nombre == "uniforme")
    return getattr(uniforme.metricas, atributo)


def evaluar_incertidumbre_y_regla_parada(
    reporte: ReporteComparacionFamiliasJuego,
    nivel_confianza: float = NIVEL_CONFIANZA_DEFECTO,
    replicas: int = REPLICAS_BOOTSTRAP_DEFECTO,
    semilla: int = SEMILLA_BOOTSTRAP_DEFECTO,
) -> ReporteIncertidumbreJuego:
    """Unica funcion publica de AE-39. Recibe un
    `ReporteComparacionFamiliasJuego` YA CONSTRUIDO (de AE-38, por
    ejemplo mediante `CompararFamiliasMLProbabilidadNumeros`, nunca
    invocado aqui) y devuelve un `ReporteIncertidumbreJuego`
    inmutable -nunca vuelve a entrenar ningun modelo, nunca consulta
    repositorios, nunca lee archivos.

    Regla de decision prerregistrada: `EVIDENCIA_EXPLORATORIA_DE_MEJORA`
    unicamente si las seis condiciones se cumplen simultaneamente
    (diferencia puntual positiva y limite inferior del intervalo
    estrictamente mayor que cero, en Log Loss Y en Brier Score, mas
    ausencia de degradacion material en las metricas secundarias);
    en cualquier otro caso, `NO_GO_SIN_EVIDENCIA_SUFICIENTE` -si
    cualquiera de las dos metricas principales tiene un estimador
    puntual negativo, la decision es NO-GO sin importar las
    metricas secundarias."""
    _validar_reporte(reporte)

    bloques = reporte.bloques_externos
    pesos = [float(b.resultado_modelo.metricas.total_filas) for b in bloques]
    diferencias_log_loss = [b.diferencia_vs_uniforme.diferencia_log_loss for b in bloques]
    diferencias_brier = [b.diferencia_vs_uniforme.diferencia_brier_score for b in bloques]

    resultado_log_loss = _analizar_metrica("log_loss", diferencias_log_loss, pesos, nivel_confianza, replicas, semilla)
    resultado_brier = _analizar_metrica("brier_score", diferencias_brier, pesos, nivel_confianza, replicas, semilla)

    precision_modelo = sum(b.resultado_modelo.metricas.precision_en_5 for b in bloques) / len(bloques)
    recall_modelo = sum(b.resultado_modelo.metricas.recall_en_5 for b in bloques) / len(bloques)
    precision_uniforme = sum(_metrica_uniforme(b, "precision_en_5") for b in bloques) / len(bloques)
    recall_uniforme = sum(_metrica_uniforme(b, "recall_en_5") for b in bloques) / len(bloques)

    sin_degradacion_material = (
        precision_modelo >= precision_uniforme - TOLERANCIA_DEGRADACION_SECUNDARIA
        and recall_modelo >= recall_uniforme - TOLERANCIA_DEGRADACION_SECUNDARIA
    )

    condiciones_evidencia_exploratoria = (
        resultado_log_loss.diferencia_puntual_agregada > 0
        and resultado_brier.diferencia_puntual_agregada > 0
        and resultado_log_loss.intervalo_bootstrap.limite_inferior > 0
        and resultado_brier.intervalo_bootstrap.limite_inferior > 0
        and sin_degradacion_material
    )
    decision = (
        DecisionContinuidadML.EVIDENCIA_EXPLORATORIA_DE_MEJORA
        if condiciones_evidencia_exploratoria
        else DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE
    )

    politica_reapertura = PoliticaReaperturaML(
        proximo_holdout_inicio=PROXIMO_HOLDOUT_INICIO,
        minimo_sorteos_nuevos_requeridos=MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT,
    )

    resumen = (
        f"Analisis exploratorio de incertidumbre sobre {len(bloques)} bloques externos completos "
        f"(nunca {sum(int(p) for p in pesos)} filas candidato-sorteo tratadas como independientes). "
        f"Diferencia puntual (uniforme-modelo) Log Loss: {resultado_log_loss.diferencia_puntual_agregada:+.9f} "
        f"IC95%[{resultado_log_loss.intervalo_bootstrap.limite_inferior:+.9f}, "
        f"{resultado_log_loss.intervalo_bootstrap.limite_superior:+.9f}]. "
        f"Brier Score: {resultado_brier.diferencia_puntual_agregada:+.9f} "
        f"IC95%[{resultado_brier.intervalo_bootstrap.limite_inferior:+.9f}, "
        f"{resultado_brier.intervalo_bootstrap.limite_superior:+.9f}]. "
        f"Decision: {decision.value}. Resultado exploratorio, nunca confirmatorio; no autoriza "
        f"predicciones futuras ni recomendaciones de apuestas."
    )

    return ReporteIncertidumbreJuego(
        codigo_juego=reporte.codigo_juego,
        total_bloques=len(bloques),
        resultado_log_loss=resultado_log_loss,
        resultado_brier_score=resultado_brier,
        precision_en_5_modelo_agregada=precision_modelo,
        recall_en_5_modelo_agregada=recall_modelo,
        precision_en_5_uniforme_agregada=precision_uniforme,
        recall_en_5_uniforme_agregada=recall_uniforme,
        decision=decision,
        politica_reapertura=politica_reapertura,
        semilla=semilla,
        resumen=resumen,
    )
