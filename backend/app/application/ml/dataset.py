"""
Construccion del dataset supervisado -Etapa AE-36, validada.

Unico punto del modulo `ml` que decide que sorteo es "objetivo" y
que construye el corte `calculado_hasta_sorteo` antes de pasarlo a
`features.py`. Toda la disciplina anti-fuga vive aqui: ninguna
funcion de `features.py` ve jamas el sorteo objetivo ni nada
posterior a el."""
from __future__ import annotations

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.features import (
    aparecio_en_sorteo_anterior,
    frecuencia_en_ventana,
    frecuencia_historica,
    sorteos_desde_ultima_aparicion,
)
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.tipos import DatasetSupervisado, FilaCandidato

PERIODO_CALENTAMIENTO_MINIMO = 50
"""Cantidad minima de sorteos previos exigida antes de que un sorteo
pueda ser objetivo -Etapa AE-36. Sorteos con menos de este historico
previo nunca entran al dataset, ni como objetivo ni para calcular
features de otro sorteo mas adelante (si son mas antiguos, si
participan como historico previo de sorteos posteriores)."""

TAMANOS_VENTANA = (10, 20, 50)


def construir_dataset_binario(
    historico: list[ResultadoNumerico], rango_min: int, rango_max: int,
    cantidad_numeros: int, codigo_juego: str,
) -> DatasetSupervisado:
    """Construye el dataset (sorteo_objetivo, numero_candidato) para
    UN juego -nunca mezcla juegos. Rechaza explicitamente (no
    corrige) un historico duplicado, desordenado o temporalmente
    inconsistente -ver `historico_util.validar_y_ordenar_historico`.

    Para cada sorteo objetivo (desde el primero con al menos
    `PERIODO_CALENTAMIENTO_MINIMO` sorteos previos) y cada numero
    candidato en `[rango_min, rango_max]`: las features se calculan
    EXCLUSIVAMENTE con el prefijo del historico estrictamente
    anterior al objetivo (`historico_ordenado[:indice_objetivo]`) -el
    propio objetivo y cualquier sorteo posterior quedan fuera de ese
    prefijo por construccion, nunca por un filtro adicional que
    pudiera fallar.

    Invariante de conservacion verificado antes de devolver: cada
    sorteo objetivo aporta exactamente `cantidad_numeros` etiquetas
    positivas y `(rango_max - rango_min + 1) - cantidad_numeros`
    negativas, sin candidatos duplicados ni fuera de rango -si el
    propio historico ya fue validado por `RegistrarSorteo` esto
    nunca deberia fallar, pero se verifica aqui de todas formas como
    segunda capa defensiva, mismo criterio que el resto del
    proyecto."""
    historico_ordenado = validar_y_ordenar_historico(historico, codigo_juego)

    filas: list[FilaCandidato] = []
    sorteos_objetivo: list[int] = []

    for indice_objetivo in range(len(historico_ordenado)):
        if indice_objetivo < PERIODO_CALENTAMIENTO_MINIMO:
            continue

        objetivo = historico_ordenado[indice_objetivo]
        historico_previo = historico_ordenado[:indice_objetivo]
        calculado_hasta_sorteo = historico_previo[-1].numero_sorteo

        numeros_del_objetivo = set(objetivo.numeros)
        if len(numeros_del_objetivo) != cantidad_numeros:
            raise ValueError(
                f"Sorteo objetivo {objetivo.numero_sorteo} de {codigo_juego} tiene "
                f"{len(numeros_del_objetivo)} numeros distintos, se esperaban {cantidad_numeros}"
            )

        positivas_de_este_sorteo = 0
        negativas_de_este_sorteo = 0

        for numero_candidato in range(rango_min, rango_max + 1):
            etiqueta = 1 if numero_candidato in numeros_del_objetivo else 0
            if etiqueta == 1:
                positivas_de_este_sorteo += 1
            else:
                negativas_de_este_sorteo += 1

            fila = FilaCandidato(
                codigo_juego=codigo_juego,
                sorteo_objetivo=objetivo.numero_sorteo,
                calculado_hasta_sorteo=calculado_hasta_sorteo,
                numero_candidato=numero_candidato,
                etiqueta=etiqueta,
                frecuencia_acumulada=frecuencia_historica(historico_previo, numero_candidato),
                frecuencia_ventana_10=frecuencia_en_ventana(historico_previo, numero_candidato, 10),
                frecuencia_ventana_20=frecuencia_en_ventana(historico_previo, numero_candidato, 20),
                frecuencia_ventana_50=frecuencia_en_ventana(historico_previo, numero_candidato, 50),
                sorteos_desde_ultima_aparicion=sorteos_desde_ultima_aparicion(historico_previo, numero_candidato),
                aparecio_en_sorteo_anterior=aparecio_en_sorteo_anterior(historico_previo, numero_candidato),
            )
            filas.append(fila)

        if positivas_de_este_sorteo != cantidad_numeros:
            raise ValueError(
                f"Sorteo objetivo {objetivo.numero_sorteo}: {positivas_de_este_sorteo} positivas, "
                f"se esperaban {cantidad_numeros}"
            )
        tamano_rango = rango_max - rango_min + 1
        if negativas_de_este_sorteo != tamano_rango - cantidad_numeros:
            raise ValueError(
                f"Sorteo objetivo {objetivo.numero_sorteo}: {negativas_de_este_sorteo} negativas, "
                f"se esperaban {tamano_rango - cantidad_numeros}"
            )

        sorteos_objetivo.append(objetivo.numero_sorteo)

    return DatasetSupervisado(
        codigo_juego=codigo_juego,
        rango_min=rango_min,
        rango_max=rango_max,
        cantidad_numeros=cantidad_numeros,
        filas=tuple(filas),
        sorteos_objetivo=tuple(sorteos_objetivo),
    )
