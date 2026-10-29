"""Genera solo las muestras nuevas de Fase 9.4 con API y lectores reales.

No borra ni regenera las muestras anteriores. Todas las escrituras, ajustes y
emisiones pertenecen a la preparacion sintetica, nunca a las consultas GET.
Uso: python -m tests.generar_respuestas_fase94 ../frontend/src/pruebas/respuestas
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def main(argv=None):
    from fastapi.testclient import TestClient
    from app.api.publica.configuracion import ConfiguracionPublica, leer_claves
    from app.api.publica.seguridad import generar_clave, huella
    from tests import fase94_api_sintetica as f94
    from tests.unit.fixtures_fase4 import arbol

    salida = Path((argv or sys.argv[1:])[0])
    salida.mkdir(parents=True, exist_ok=True)
    clave = generar_clave()
    conf = ConfiguracionPublica(claves=leer_claves(f"f94:sha256:{huella(clave)}"),
                               fichas_por_minuto=100_000, fichas_por_minuto_ip=100_000)
    h = {"X-API-Key": clave}
    escritos = []
    with tempfile.TemporaryDirectory(prefix="f94-muestras-") as temporal:
        raiz = Path(temporal)
        def guardar(cliente, nombre, url, esperado=200):
            r = cliente.get(url, headers=h)
            assert r.status_code == esperado, (nombre, r.status_code, r.text)
            muestra = {"escenario": f94.ESCENARIO, "url": url, "estado": r.status_code, "cuerpo": r.json()}
            if "retry-after" in r.headers:
                muestra["retry_after"] = r.headers["retry-after"]
            (salida / f"{nombre}.json").write_text(json.dumps(muestra, ensure_ascii=False, indent=1) + "\n",
                                                 encoding="utf-8")
            escritos.append(nombre)
            return muestra["cuerpo"]
        datos = f94.preparar(raiz / "normal")
        foto = arbol(raiz / "normal")
        with TestClient(f94.crear(raiz / "normal", conf, preparada=datos)) as cliente:
            for j in f94.JUEGOS:
                base = f"/api/v1/juegos/{j}"
                guardar(cliente, f"{j}--modelos", base + "/modelos-guardados")
                guardar(cliente, f"{j}--modelo", base + "/modelos-guardados/" + datos["modelos"][j][-1].identificador)
                guardar(cliente, f"{j}--carteras", base + "/carteras-guardadas")
                guardar(cliente, f"{j}--cartera", base + "/carteras-guardadas/" + datos["carteras"][j][-1].identificador)
                guardar(cliente, f"{j}--resultados", base + "/resultados")
            for p in (1, 2):
                guardar(cliente, f"BALOTO--modelos--pagina-{p}",
                        f"/api/v1/juegos/BALOTO/modelos-guardados?pagina={p}&por_pagina=1")
                guardar(cliente, f"BALOTO--carteras--pagina-{p}",
                        f"/api/v1/juegos/BALOTO/carteras-guardadas?pagina={p}&por_pagina=1")
                guardar(cliente, f"BALOTO--resultados--pagina-{p}",
                        f"/api/v1/juegos/BALOTO/resultados?pagina={p}&por_pagina=1")
            guardar(cliente, "BALOTO--modelo--anterior", "/api/v1/juegos/BALOTO/modelos-guardados/" +
                    datos["modelos"]["BALOTO"][0].identificador)
            guardar(cliente, "BALOTO--cartera--anterior", "/api/v1/juegos/BALOTO/carteras-guardadas/" +
                    datos["carteras"]["BALOTO"][0].identificador)
        assert arbol(raiz / "normal") == foto
        for estado in ("vacio", "alterado", "incompatible"):
            datos = f94.preparar(raiz / estado, estado=estado)
            foto = arbol(raiz / estado)
            with TestClient(f94.crear(raiz / estado, conf, preparada=datos)) as cliente:
                guardar(cliente, f"BALOTO--modelos--{estado}", "/api/v1/juegos/BALOTO/modelos-guardados")
                if estado == "vacio":
                    guardar(cliente, "BALOTO--carteras--vacio", "/api/v1/juegos/BALOTO/carteras-guardadas")
                    guardar(cliente, "BALOTO--resultados--vacio", "/api/v1/juegos/BALOTO/resultados")
                elif estado == "alterado":
                    guardar(cliente, "BALOTO--modelo--alterado", "/api/v1/juegos/BALOTO/modelos-guardados/" +
                            datos["modelos"]["BALOTO"][-1].identificador, 409)
                    guardar(cliente, "COLORLOTO--carteras--alterado", "/api/v1/juegos/COLORLOTO/carteras-guardadas")
                    guardar(cliente, "COLORLOTO--cartera--alterado", "/api/v1/juegos/COLORLOTO/carteras-guardadas/" +
                            datos["carteras"]["COLORLOTO"][-1].identificador, 409)
                else:
                    guardar(cliente, "BALOTO--modelo--incompatible", "/api/v1/juegos/BALOTO/modelos-guardados/" +
                            datos["modelos"]["BALOTO"][-1].identificador)
            assert arbol(raiz / estado) == foto
    print(json.dumps({"muestras_nuevas": len(escritos), "archivos": escritos, "almacenes_intactos_tras_get": True},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
