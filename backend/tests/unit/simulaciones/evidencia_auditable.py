"""Evidencia AE-49 sintetica que corresponde a los historicos sinteticos
de `sinteticos.py`, para las pruebas de AE-51.

La huella de entrada y los valores `observado` se calculan con las
funciones reales de AE-49 (`huella_entrada`, `calcular_estadisticas`)
sobre esos historicos; los p-valores y percentiles se fabrican
coherentes con B = 10 000 (como en `evidencia_sintetica.py`), de modo
que la evidencia pasa AE-50 sin ejecutar ninguna simulacion. Nunca se
usan datos reales ni PostgreSQL."""
from __future__ import annotations

import json
from fractions import Fraction

from app.application.simulaciones import montecarlo_uniforme as mc
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from scripts.comparacion_estado_prediccion import serializar_reporte
from tests.unit.simulaciones import evidencia_sintetica as ev
from tests.unit.simulaciones import sinteticos

_DOMINIO = {"BALOTO": BalotoGame, "BALOTO_REVANCHA": BalotoRevanchaGame}
_REFERENCIAS = (Fraction(38), None, Fraction(25, 43), Fraction(15))
_POSICIONES = ((3120, 0), (5210, 412), (4100, 0), (4870, 0))


def _resultado(codigo: str, historico) -> mc.ResultadoJuego:
    params = mc.parametros_desde_dominio(codigo, _DOMINIO[codigo]())
    valores = mc.calcular_estadisticas(historico, params)
    comparaciones = tuple(
        ev.comparacion(nombre, observado, referencia, menores, iguales, Fraction(1), Fraction(1))
        for nombre, observado, referencia, (menores, iguales) in zip(
            mc.ESTADISTICAS_AE49, valores.como_fracciones(), _REFERENCIAS, _POSICIONES,
        )
    )
    return mc.ResultadoJuego(
        codigo=codigo, total_sorteos=valores.total_sorteos, total_transiciones=valores.total_transiciones,
        total_superbalotas=valores.total_superbalotas, entrada_sha256=mc.huella_entrada(codigo, historico),
        comparaciones=comparaciones,
    )


def reporte_auditable(revision: str = "0006", baloto=None, revancha=None) -> dict:
    baloto = sinteticos.historico_baloto() if baloto is None else baloto
    revancha = sinteticos.historico_revancha() if revancha is None else revancha
    return mc.construir_reporte(
        revision, [_resultado("BALOTO", baloto), _resultado("BALOTO_REVANCHA", revancha)],
        semilla=mc.SEMILLA_AE49, iteraciones=mc.ITERACIONES_AE49,
    )


def evidencia_auditable(**kwargs) -> bytes:
    return serializar_reporte(reporte_auditable(**kwargs))


def copia(reporte: dict) -> dict:
    return json.loads(json.dumps(reporte))
