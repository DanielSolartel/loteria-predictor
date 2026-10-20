"""Demostración sintética de veinte rutas ML (cinco familias, cuatro juegos).

No accede a PostgreSQL ni al histórico del operador. Ajusta algoritmos reales
con perfil reducido, compara con uniforme, registra, recarga en otro proceso
sin fit, genera/explica y observa resultados. No acredita ventaja predictiva.

Uso desde backend: ``python -m tests.demostracion_ml_cinco_familias``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import time
import traceback

from tests.unit.test_ml_cinco_flujo import JUEGOS, modelos, preparar, recorrido

PREFIJO_DEMOSTRACION = "d "


def main(argv=None):
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--salida", type=Path, help="JSON de evidencia fuera de los almacenes")
    argumentos = analizador.parse_args(argv)
    inicio = time.perf_counter()
    informe = {"datos": "sinteticos", "perfil": "reducido", "rutas": [], "fallos": [],
               "estado_de_uso": "experimental_no_acreditado", "AE-39": "NO-GO",
               "AUTORIZA_EVALUACION": False}
    with tempfile.TemporaryDirectory(prefix=PREFIJO_DEMOSTRACION) as temporal:
        for indice, juego in enumerate(JUEGOS):
            try:
                datos = preparar(Path(temporal) / str(indice), juego)
            except Exception:
                informe["fallos"].append({"juego": juego, "error": traceback.format_exc()})
                continue
            for modelo in modelos(juego):
                comienzo = time.perf_counter()
                try:
                    resultado = recorrido(datos, juego, modelo, web=False)
                    resultado["segundos"] = round(time.perf_counter() - comienzo, 3)
                    informe["rutas"].append(resultado)
                    print(f"[OK] {juego} {modelo}: registro, recarga sin fit, cartera, explicación y seguimiento", flush=True)
                except Exception:
                    informe["fallos"].append({"juego": juego, "modelo": modelo, "error": traceback.format_exc()})
                    print(f"[FALLO] {juego} {modelo}", flush=True)
    informe["segundos"] = round(time.perf_counter() - inicio, 3)
    informe["correctas"] = len(informe["rutas"])
    informe["esperadas"] = 20
    informe["estado"] = "correcto" if len(informe["rutas"]) == 20 and not informe["fallos"] else "fallo"
    if argumentos.salida:
        argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
        argumentos.salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if informe["estado"] == "correcto" else 1


if __name__ == "__main__":
    raise SystemExit(main())
