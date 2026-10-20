"""Matriz real de ajuste/inferencia 1/2 hilos, solo histórica sintética.

Ejecutar en un proceso de prueba independiente, nunca en el servidor. Una
diferencia entre recursos distintos se registra, no se oculta ni se exige.
La repetición con los mismos recursos sí debe ser exactamente igual.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys


def analizar():
    import numpy as np
    from threadpoolctl import threadpool_info
    from app.application.ml import laboratorio_evaluacion as le, laboratorio_modelos as lm, laboratorio_variables as lv
    from app.infrastructure.recursos_ml import limitar_trabajador
    from tests.unit import fixtures_producto4 as f4
    def sha(v):
        return hashlib.sha256(json.dumps(v, sort_keys=True, allow_nan=False).encode()).hexdigest()
    ins = lv.validar_instantanea("COLORLOTO", f4.historico("COLORLOTO", 90))
    var = lv.Variables(ins)
    b = le.muestra_comun(ins, le.Protocolo(bloques=1, perfil="reducido"))["bloques"][0]
    filas = var.filas(b["posiciones"], paleta=tuple(b["paleta"]))
    out = {"plataforma": platform.platform(), "python": sys.version, "datos": "sinteticos",
           "corte": b["posicion_de_ajuste"], "ajustes": {}, "inferencias": {}, "paquetes": {}}
    for n in ("numpy", "scipy", "scikit-learn", "xgboost-cpu", "lightgbm", "threadpoolctl"):
        try: out["paquetes"][n] = importlib.metadata.version(n)
        except importlib.metadata.PackageNotFoundError: out["paquetes"][n] = None
    for etiqueta, h in (("1a", 1), ("2a", lm.HILOS), ("2b", lm.HILOS)):
        with limitar_trabajador(h):
            a = lm.ajustar_candidato(lm.CATALOGO["red_neuronal_poisson"], ins, var,
                                     b["posicion_de_ajuste"], "reducido")
            estado = a.estimador.to_dict()
            out["ajustes"][etiqueta] = {"hilos": h, "estado": estado,
                "sha256_pesos": sha(estado["contenido"]), "sha256_preparacion": sha(estado["preparacion"]),
                "motores": threadpool_info()}
        for inferencia in (1, lm.HILOS):
            with limitar_trabajador(inferencia):
                raw = a.estimador.predict(filas.X)
                p = a.predecir(filas)
                out["inferencias"][etiqueta + "-" + str(inferencia)] = {
                    "crudas": raw.tolist(), "probabilidades": p.tolist(), "sha256": sha(p.tolist()),
                    "motores": threadpool_info()}
    out["ajuste_cambia_entre_1_y_2"] = out["ajustes"]["1a"]["sha256_pesos"] != out["ajustes"]["2a"]["sha256_pesos"]
    out["inferencia_cambia_con_estimador_fijo"] = {
        k: out["inferencias"][k + "-1"]["sha256"] != out["inferencias"][k + "-2"]["sha256"]
        for k in ("1a", "2a", "2b")}
    out["maxima_diferencia_inferencia"] = {}
    for k in ("1a", "2a", "2b"):
        p1 = np.asarray(out["inferencias"][k+"-1"]["probabilidades"])
        p2 = np.asarray(out["inferencias"][k+"-2"]["probabilidades"])
        out["maxima_diferencia_inferencia"][k] = float(np.max(np.abs(p1 - p2)))
    out["repeticion_2_hilos_exacta"] = (out["ajustes"]["2a"]["estado"] == out["ajustes"]["2b"]["estado"] and
        out["inferencias"]["2a-2"]["probabilidades"] == out["inferencias"]["2b-2"]["probabilidades"])
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, required=True)
    args = p.parse_args()
    out = analizar()
    args.salida.write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("ajustes", "inferencias")}))
    if not out["repeticion_2_hilos_exacta"]:
        print("El mismo contexto de dos hilos no se reprodujo exactamente; matriz conservada en " + str(args.salida),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
