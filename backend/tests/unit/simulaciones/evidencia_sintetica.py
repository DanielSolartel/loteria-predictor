"""Evidencia AE-49 sintetica y valida para las pruebas de AE-50.

Se construye con la funcion real `construir_reporte` de AE-49 y la
serializacion real `serializar_reporte`, a partir de comparaciones
hechas a mano con `Fraction` coherentes con B = 10 000: no se ejecuta
ninguna simulacion Monte Carlo ni se usan datos reales.

Para cada estadistica se eligen `menores` (#sim < obs) e `iguales`
(#sim == obs); de ahi salen, igual que en AE-49, el percentil
(2·menores + iguales) / (2B) y el p bilateral
min(1, 2·min((1 + B − menores)/(B+1), (1 + menores + iguales)/(B+1)))."""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction

from app.application.simulaciones import montecarlo_uniforme as mc
from scripts.comparacion_estado_prediccion import serializar_reporte

B = mc.ITERACIONES_AE49


def comparacion(nombre, observado, referencia, menores, iguales, media, varianza):
    p_superior = Fraction(1 + B - menores, 1 + B)
    p_inferior = Fraction(1 + menores + iguales, 1 + B)
    return mc.ComparacionEstadistica(
        nombre=nombre, observado=observado, media=media, varianza=varianza, referencia=referencia,
        percentil=Fraction(2 * menores + iguales, 2 * B),
        p_valor=min(Fraction(1), 2 * min(p_superior, p_inferior)),
    )


def _juego(codigo, huella, extremo=False):
    comparaciones = (
        comparacion("dispersion_frecuencia_numeros", Fraction(3712, 100), Fraction(38), 3120, 0,
                    Fraction(3801, 100), Fraction(76)),
        comparacion("rango_frecuencia_numeros", Fraction(31), None, 5210, 412, Fraction(2987, 100), Fraction(21)),
        comparacion("media_repeticiones_entre_sorteos", Fraction(360, 624), Fraction(25, 43),
                    9990 if extremo else 4100, 0, Fraction(5813, 10000), Fraction(9, 10000)),
        comparacion("dispersion_frecuencia_superbalota", Fraction(1480, 100), Fraction(15), 4870, 0,
                    Fraction(1502, 100), Fraction(30)),
    )
    return mc.ResultadoJuego(
        codigo=codigo, total_sorteos=625, total_transiciones=624, total_superbalotas=625,
        entrada_sha256=huella, comparaciones=comparaciones,
    )


HUELLA_BALOTO = hashlib.sha256(b"sintetica-baloto").hexdigest()
HUELLA_REVANCHA = hashlib.sha256(b"sintetica-revancha").hexdigest()


def reporte_valido(revision="0006", huella_revancha=HUELLA_REVANCHA) -> dict:
    """Incluye una estadistica extrema (p crudo 22/10001 -> ajustado ~0.0176)
    para que `supera_umbral_exploratorio` sea true en un caso."""
    return mc.construir_reporte(
        revision,
        [_juego("BALOTO", HUELLA_BALOTO, extremo=True), _juego("BALOTO_REVANCHA", huella_revancha)],
        semilla=mc.SEMILLA_AE49, iteraciones=mc.ITERACIONES_AE49,
    )


def evidencia_valida(**kwargs) -> bytes:
    return serializar_reporte(reporte_valido(**kwargs))


def recodificar(reporte: dict) -> bytes:
    """Serializacion canonica de un reporte ya mutado: asi una mutacion
    de contenido no queda enmascarada por la comprobacion de forma."""
    return serializar_reporte(reporte)


def copia(reporte: dict) -> dict:
    return json.loads(json.dumps(reporte))
