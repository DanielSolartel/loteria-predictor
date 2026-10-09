"""
Producto 6: diagnostico de calibracion de probabilidades YA EMITIDAS. Modulo
puro y descriptivo: no reentrena, no recalibra ni modifica artefactos, y no
hace pruebas de significacion ni intervalos de confianza.

Intervalos fijos (iguales para todos los juegos y lineas), cerrados por la
izquierda y abiertos por la derecha, salvo el ultimo, que incluye 1:
[0, 0.01), [0.01, 0.02), [0.02, 0.03), [0.03, 0.05), [0.05, 0.075),
[0.075, 0.1), [0.1, 0.125), [0.125, 0.15), [0.15, 0.2), [0.2, 0.3),
[0.3, 0.5), [0.5, 1]. Son finos donde caen las probabilidades de estos
juegos (pares de ColorLoto ~0.02, superbalota ~0.06, numeros ~0.12).

Valor observado por prediccion:
- numeros: 1 si el numero salio, 0 si no (frecuencia observada de aparicion);
- superbalota: 1 para la clase observada, 0 para las demas (diagnostico
  separado);
- ColorLoto: multiplicidad del par en el resultado / 6 balotas (fraccion de
  balotas; las repeticiones cuentan). NO es la probabilidad de que el par
  aparezca al menos una vez.

Cada intervalo informa predicciones, objetivos distintos, probabilidad media
y valor observado medio; un intervalo vacio da valores no disponibles (None),
nunca ceros. Se informan los dos tamanos: sorteos distintos y predicciones
por candidato. Las predicciones de un mismo sorteo no son ensayos
independientes.
"""
from __future__ import annotations

from collections import Counter

BORDES = (0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.125, 0.15, 0.2, 0.3, 0.5, 1.0)
MUESTRA_PEQUENA = 10
DEFINICION = ("Intervalos [a, b) cerrados por la izquierda y abiertos por la derecha; el último, [0.5, 1], incluye 1. "
              "Bordes: " + ", ".join(f"{b:g}" for b in BORDES) + ".")
ETIQUETAS = {"numeros": "frecuencia observada de aparición (0 o 1 por número y sorteo)",
             "superbalota": "frecuencia observada de la clase (0 o 1 por superbalota y sorteo)",
             "pares": "fracción de balotas observada: multiplicidad del par / 6 (no es «aparecer al menos una vez»)"}
AVISO_DEPENDENCIA = ("Las predicciones de un mismo sorteo no son ensayos independientes: el tamaño útil es el número de "
                     "sorteos distintos, no el de predicciones.")


class ProbabilidadFueraDeRango(ValueError):
    pass


def intervalo_de(p: float) -> int:
    """Indice del intervalo; los extremos 0 y 1 caen en el primero y el ultimo."""
    if not 0.0 <= p <= 1.0:
        raise ProbabilidadFueraDeRango(f"probabilidad fuera de [0, 1]: {p}")
    for i in range(len(BORDES) - 2, -1, -1):
        if p >= BORDES[i]:
            return i
    return 0


def _pares_observados(resultado: dict) -> Counter:
    return Counter(tuple(p) for p in resultado["pares"])


def observaciones(fila: dict) -> dict[str, list[tuple[float, float]]]:
    """(probabilidad, valor observado) por diagnostico para una emision incluida."""
    congelado, resultado = fila["congelado"], fila["resultado"]
    salida: dict[str, list] = {}
    if congelado["tipo"] == "pares":
        multiplicidad = _pares_observados(resultado)
        salida["pares"] = [(p, multiplicidad.get(tuple(c), 0) / 6)
                           for c, p in zip(congelado["candidatos"], congelado["probabilidad"])]
        return salida
    salieron = set(resultado["numeros"])
    salida["numeros"] = [(p, 1.0 if c in salieron else 0.0)
                         for c, p in zip(congelado["candidatos"], congelado["probabilidad"])]
    sb = congelado.get("superbalota")
    if sb and resultado.get("superbalota") is not None:
        salida["superbalota"] = [(p, 1.0 if c == resultado["superbalota"] else 0.0)
                                 for c, p in zip(sb["candidatos"], sb["probabilidad"])]
    return salida


def diagnostico(filas: list[dict]) -> dict:
    """Diagnostico por tipo de prediccion sobre las emisiones INCLUIDAS dadas."""
    incluidas = [f for f in filas if f["estado"] == "incluido" and f.get("congelado") and f.get("resultado")]
    acumulado: dict[str, list] = {}
    for f in incluidas:
        for nombre, pares in observaciones(f).items():
            acumulado.setdefault(nombre, []).extend((p, y, f["objetivo"]) for p, y in pares)
    salida = {"bordes": list(BORDES), "definicion": DEFINICION, "diagnosticos": {}, "aviso": AVISO_DEPENDENCIA}
    for nombre, datos in acumulado.items():
        cajas = [{"desde": BORDES[i], "hasta": BORDES[i + 1], "incluye_hasta": i == len(BORDES) - 2,
                  "predicciones": 0, "objetivos": set(), "suma_p": 0.0, "suma_y": 0.0}
                 for i in range(len(BORDES) - 1)]
        for p, y, objetivo in datos:
            c = cajas[intervalo_de(p)]
            c["predicciones"] += 1
            c["objetivos"].add(objetivo)
            c["suma_p"] += p
            c["suma_y"] += y
        intervalos = []
        for c in cajas:
            n = c["predicciones"]
            intervalos.append({"desde": c["desde"], "hasta": c["hasta"], "incluye_hasta": c["incluye_hasta"],
                               "predicciones": n, "objetivos": len(c["objetivos"]),
                               "probabilidad_media": c["suma_p"] / n if n else None,
                               "valor_observado_medio": c["suma_y"] / n if n else None})
        objetivos = len({o for _, _, o in datos})
        salida["diagnosticos"][nombre] = {
            "etiqueta_observado": ETIQUETAS[nombre], "objetivos": objetivos, "predicciones": len(datos),
            "probabilidad_media": sum(p for p, _, _ in datos) / len(datos),
            "valor_observado_medio": sum(y for _, y, _ in datos) / len(datos),
            "intervalos": intervalos, "muestra_pequena": objetivos < MUESTRA_PEQUENA}
    return salida
