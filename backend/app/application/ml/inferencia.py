"""
Filas de inferencia sin etiqueta -Etapa AE-43, validada.

Construye, para UN juego y UN sorteo objetivo (`hasta_numero_sorteo
+ 1`), el mismo vector de features que `dataset.py` calcula para sus
filas etiquetadas, pero sin etiqueta. Es el formato que un modelo
futuro recibiria; AE-43 no lo conecta con ningun repositorio, caso
de uso ni modelo.

Solo admite DESARROLLO (`2081..2590`): objetivo `<= 2590` y corte
`<= 2589`. Cualquier sorteo recibido del tramo consumido de AE-36
(`2591..2705`) o del holdout (`>= 2706`) se RECHAZA con un error
explicito -nunca se filtra en silencio. El llamador decide que
historico pasar; esta funcion nunca recorta."""
from __future__ import annotations

from collections.abc import Sequence

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import PERIODO_CALENTAMIENTO_MINIMO, TAMANOS_VENTANA
from app.application.ml.features import (
    aparecio_en_sorteo_anterior,
    frecuencia_en_ventana,
    frecuencia_historica,
    sorteos_desde_ultima_aparicion,
)
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import FilaCandidatoInferencia, FilasInferenciaJuego
from app.application.ml.ventanas_temporales import (
    INICIO_HISTORICO_REAL,
    MAXIMO_CORTE_INFERENCIA_AE43,
    TramoTemporalML,
    clasificar_sorteo,
)


class CorteInferenciaInvalidoError(ValueError):
    """Excepcion propia de AE-43 -nunca `assert`. Cubre juego no
    autorizado, corte fuera de DESARROLLO, sorteos recibidos fuera de
    DESARROLLO o posteriores al corte, huecos, historico insuficiente
    y sorteos con numeros invalidos."""


def construir_filas_inferencia(
    historico: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
    cantidad_numeros: int, codigo_juego: str, hasta_numero_sorteo: int,
) -> FilasInferenciaJuego:
    """Filas de inferencia para el sorteo `hasta_numero_sorteo + 1`,
    calculadas EXCLUSIVAMENTE con `historico`, que debe terminar
    exactamente en `hasta_numero_sorteo` y ser contiguo."""
    if codigo_juego not in JUEGOS_AUTORIZADOS_AE40:
        raise CorteInferenciaInvalidoError(
            f"'{codigo_juego}' no esta autorizado -unicamente {sorted(JUEGOS_AUTORIZADOS_AE40)}"
        )

    if isinstance(hasta_numero_sorteo, bool) or not isinstance(hasta_numero_sorteo, int):
        raise CorteInferenciaInvalidoError(f"hasta_numero_sorteo debe ser int, recibido {hasta_numero_sorteo!r}")
    if hasta_numero_sorteo > MAXIMO_CORTE_INFERENCIA_AE43:
        raise CorteInferenciaInvalidoError(
            f"hasta_numero_sorteo {hasta_numero_sorteo} fuera de DESARROLLO -AE-43 solo admite cortes "
            f"<= {MAXIMO_CORTE_INFERENCIA_AE43} (objetivo <= {MAXIMO_CORTE_INFERENCIA_AE43 + 1})"
        )

    for r in historico:
        tramo = clasificar_sorteo(r.numero_sorteo)
        if tramo in (TramoTemporalML.CONSUMIDO_AE36, TramoTemporalML.HOLDOUT):
            raise CorteInferenciaInvalidoError(
                f"Sorteo {r.numero_sorteo} de {codigo_juego} pertenece al tramo {tramo.name} "
                f"-AE-43 no lo admite como feature ni como objetivo"
            )

    ordenado = validar_y_ordenar_historico(historico, codigo_juego)

    posteriores = [r.numero_sorteo for r in ordenado if r.numero_sorteo > hasta_numero_sorteo]
    if posteriores:
        raise CorteInferenciaInvalidoError(
            f"Historico de {codigo_juego} contiene sorteos posteriores al corte {hasta_numero_sorteo}: "
            f"{posteriores}"
        )

    if len(ordenado) < PERIODO_CALENTAMIENTO_MINIMO:
        raise CorteInferenciaInvalidoError(
            f"Historico de {codigo_juego} con {len(ordenado)} sorteos, se requieren al menos "
            f"{PERIODO_CALENTAMIENTO_MINIMO}"
        )
    if ordenado[0].numero_sorteo < INICIO_HISTORICO_REAL:
        raise CorteInferenciaInvalidoError(
            f"Historico de {codigo_juego} empieza en {ordenado[0].numero_sorteo}, antes de "
            f"{INICIO_HISTORICO_REAL} -fuera de DESARROLLO"
        )
    if ordenado[-1].numero_sorteo != hasta_numero_sorteo:
        raise CorteInferenciaInvalidoError(
            f"Historico de {codigo_juego} termina en {ordenado[-1].numero_sorteo}, se esperaba "
            f"exactamente el corte {hasta_numero_sorteo}"
        )
    for anterior, actual in zip(ordenado, ordenado[1:]):
        if actual.numero_sorteo != anterior.numero_sorteo + 1:
            raise CorteInferenciaInvalidoError(
                f"Historico de {codigo_juego} tiene un hueco entre {anterior.numero_sorteo} y "
                f"{actual.numero_sorteo}"
            )

    for r in ordenado:
        numeros = set(r.numeros)
        if len(numeros) != cantidad_numeros or len(r.numeros) != cantidad_numeros:
            raise CorteInferenciaInvalidoError(
                f"Sorteo {r.numero_sorteo} de {codigo_juego} tiene {len(r.numeros)} numeros, "
                f"se esperaban {cantidad_numeros} distintos"
            )
        if any(n < rango_min or n > rango_max for n in numeros):
            raise CorteInferenciaInvalidoError(
                f"Sorteo {r.numero_sorteo} de {codigo_juego} tiene numeros fuera de [{rango_min}, {rango_max}]"
            )

    v10, v20, v50 = TAMANOS_VENTANA
    filas = tuple(
        FilaCandidatoInferencia(
            codigo_juego=codigo_juego,
            sorteo_objetivo=hasta_numero_sorteo + 1,
            calculado_hasta_sorteo=hasta_numero_sorteo,
            numero_candidato=numero_candidato,
            frecuencia_acumulada=frecuencia_historica(ordenado, numero_candidato),
            frecuencia_ventana_10=frecuencia_en_ventana(ordenado, numero_candidato, v10),
            frecuencia_ventana_20=frecuencia_en_ventana(ordenado, numero_candidato, v20),
            frecuencia_ventana_50=frecuencia_en_ventana(ordenado, numero_candidato, v50),
            sorteos_desde_ultima_aparicion=sorteos_desde_ultima_aparicion(ordenado, numero_candidato),
            aparecio_en_sorteo_anterior=aparecio_en_sorteo_anterior(ordenado, numero_candidato),
        )
        for numero_candidato in range(rango_min, rango_max + 1)
    )

    return FilasInferenciaJuego(
        codigo_juego=codigo_juego,
        rango_min=rango_min,
        rango_max=rango_max,
        cantidad_numeros=cantidad_numeros,
        sorteo_objetivo=hasta_numero_sorteo + 1,
        calculado_hasta_sorteo=hasta_numero_sorteo,
        total_sorteos_historico=len(ordenado),
        filas=filas,
    )
