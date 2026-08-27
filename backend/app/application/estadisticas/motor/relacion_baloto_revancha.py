"""
Relación estadística Baloto ↔ Revancha.

Nota importante sobre el origen de esta etapa: no corresponde a
ningún "Paso" explícito de `ROADMAP.md`. El roadmap solo menciona la
relación Baloto/Revancha como una decisión ARQUITECTÓNICA de la Fase
2 ("se relacionan por numero_sorteo sin cambios de esquema"), no como
un entregable estadístico de la Fase 5. Este módulo es una extensión
adicional del motor, justificada por reutilización real y una
pregunta estadística bien definida -no un requisito oficial.

Pregunta que responde: para sorteos de la MISMA noche (mismo
numero_sorteo, un juego = Baloto, el otro = Baloto Revancha, ambos
con reglas idénticas: 5 de 43 sin repetición + superbalota 1-16),
¿cuántos números coinciden, y coincide la superbalota?

`ResultadoNumerico` no lleva identificación de juego (deliberado,
confirmado en la inspección de la Etapa P -el motor es agnóstico al
juego por diseño). Por eso este módulo recibe DOS secuencias
separadas (`resultados_baloto`, `resultados_revancha`) y empareja
internamente por `numero_sorteo` -la única clave compartida entre
ambos juegos, confirmada por el mecanismo real de
`ObtenerSorteoConPareja` (capa de aplicación, `PAREJAS_DE_JUEGO`).

Emparejamiento = INNER JOIN por numero_sorteo: un sorteo presente
solo en una de las dos familias (sincronización parcial, o
simplemente porque una de las dos aún no se sincronizó) se EXCLUYE
-nunca se interpreta como "0 coincidencias" ni se inventa un
resultado. Mismo criterio que los huecos temporales en el resto del
motor: ausencia de dato no es un valor observado.

Conjuntos, no multiconjuntos: ni Baloto ni Revancha permiten
repetición interna (K=5 de N=43, sin reemplazo) -a diferencia de
ColorLoto, `set(numeros)` es exactamente correcto aquí, sin ninguna
pérdida de información posible.

Sin ninguna probabilidad teórica, frecuencia esperada, lift, ni test
de independencia -alcance deliberadamente limitado a frecuencia
descriptiva de coincidencias. Un test de independencia agregado o por
número queda reservado para una etapa de diseño futura separada.
"""
from __future__ import annotations

from collections.abc import Sequence

from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.tabulacion import tabular_conteo_por_sorteo
from app.application.estadisticas.tipos import FrecuenciaObservada, ResultadoNumerico


def _emparejar_por_numero_sorteo(
    resultados_baloto: Sequence[ResultadoNumerico], resultados_revancha: Sequence[ResultadoNumerico],
) -> list[tuple[ResultadoNumerico, ResultadoNumerico]]:
    """INNER JOIN por numero_sorteo -nunca por posición de la lista.
    Sorteos presentes en una sola de las dos familias se excluyen.
    No muta ninguna de las dos entradas: solo las indexa para el
    emparejamiento."""
    por_numero_sorteo_revancha = {r.numero_sorteo: r for r in resultados_revancha}
    parejas = []
    for baloto in resultados_baloto:
        revancha = por_numero_sorteo_revancha.get(baloto.numero_sorteo)
        if revancha is not None:
            parejas.append((baloto, revancha))
    return parejas


def calcular_coincidencias_baloto_revancha(
    resultados_baloto: Sequence[ResultadoNumerico], resultados_revancha: Sequence[ResultadoNumerico],
    cantidad_numeros: int, hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """Distribución de cuántos números coinciden entre Baloto y
    Revancha, para sorteos de la misma noche (mismo numero_sorteo),
    tabulado 0..cantidad_numeros. `hasta_numero_sorteo` se aplica
    independientemente a ambas secuencias, con el mismo valor -la
    clave de corte es la misma para ambos juegos."""
    baloto_filtrado = filtrar_por_corte_temporal(resultados_baloto, hasta_numero_sorteo)
    revancha_filtrado = filtrar_por_corte_temporal(resultados_revancha, hasta_numero_sorteo)

    parejas = _emparejar_por_numero_sorteo(baloto_filtrado, revancha_filtrado)
    conteos = [len(set(baloto.numeros) & set(revancha.numeros)) for baloto, revancha in parejas]

    return tabular_conteo_por_sorteo(conteos, cantidad_numeros, len(parejas))


def calcular_coincidencia_superbalota_baloto_revancha(
    resultados_baloto: Sequence[ResultadoNumerico], resultados_revancha: Sequence[ResultadoNumerico],
    hasta_numero_sorteo: int | None = None,
) -> list[FrecuenciaObservada]:
    """valor = "0" (superbalotas distintas) | "1" (misma superbalota),
    para sorteos de la misma noche. Una pareja donde cualquiera de las
    dos superbalotas es None se EXCLUYE -no cuenta como "0" ni "1"."""
    baloto_filtrado = filtrar_por_corte_temporal(resultados_baloto, hasta_numero_sorteo)
    revancha_filtrado = filtrar_por_corte_temporal(resultados_revancha, hasta_numero_sorteo)

    parejas = _emparejar_por_numero_sorteo(baloto_filtrado, revancha_filtrado)
    parejas_con_dato = [
        (baloto, revancha) for baloto, revancha in parejas
        if baloto.superbalota is not None and revancha.superbalota is not None
    ]
    conteos = [
        1 if baloto.superbalota == revancha.superbalota else 0
        for baloto, revancha in parejas_con_dato
    ]

    return tabular_conteo_por_sorteo(conteos, 1, len(parejas_con_dato))
