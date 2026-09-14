"""
Validacion y normalizacion del historico -Etapa AE-36, validada.

Rechaza explicitamente historicos duplicados, desordenados o
temporalmente inconsistentes -nunca los corrige en silencio (ver
invariante anti-fuga #8). El resto del pipeline de AE-36 asume que
recibio un historico ya validado por esta funcion."""
from __future__ import annotations

from collections.abc import Sequence

from app.application.estadisticas.tipos import ResultadoNumerico


class HistoricoInconsistenteError(ValueError):
    """Excepcion propia y pequena de AE-36 -nunca reutiliza
    `ResultadoHistoricoInconsistenteError` del motor estadistico
    (esa excepcion tiene su propio enum CERRADO de razones,
    reservado exclusivamente para el motor de estadisticas
    descriptivas; mezclar dominios aqui violaria ese contrato)."""


def validar_y_ordenar_historico(
    historico: Sequence[ResultadoNumerico], codigo_juego: str,
) -> list[ResultadoNumerico]:
    """Rechaza duplicados de `numero_sorteo` y cualquier
    inconsistencia entre el orden de `numero_sorteo` y el orden de
    `fecha` -nunca corrige en silencio. Devuelve una lista NUEVA
    ordenada ascendente por `numero_sorteo` (nunca muta la entrada);
    el orden de llegada de `historico` nunca afecta el resultado."""
    numeros_sorteo = [r.numero_sorteo for r in historico]
    if len(numeros_sorteo) != len(set(numeros_sorteo)):
        raise HistoricoInconsistenteError(
            f"Historico de {codigo_juego} contiene numero_sorteo duplicado"
        )

    ordenado = sorted(historico, key=lambda r: r.numero_sorteo)

    for anterior, actual in zip(ordenado, ordenado[1:]):
        if actual.fecha < anterior.fecha:
            raise HistoricoInconsistenteError(
                f"Historico de {codigo_juego} tiene fecha ({actual.fecha}) anterior a un "
                f"numero_sorteo mayor ({anterior.numero_sorteo} -> {actual.numero_sorteo}); "
                "orden cronologico inconsistente"
            )

    return ordenado
