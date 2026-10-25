"""Genera las respuestas SINTETICAS que usan las pruebas de componentes del frontend (Fase 9.1).

    python -m tests.generar_respuestas_fase9 ../frontend/src/pruebas/respuestas

Cada archivo es una respuesta real de la API publica de esta base sobre el
escenario de `tests/fase9_api_sintetica.py` (sin PostgreSQL ni datos reales):
`{"escenario", "url", "estado", "cuerpo"}`. Los errores (401, 404, 422, 429,
500 y 503) tambien los produce la propia API, con proveedores sustituidos.
Nombre: `<juego o global>--<tipo>[--<variante>].json`.
"""
from __future__ import annotations

import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")


VALORES_DE_FORMATO = (None, 0, -0.0, 1, 7, -3, 2.5, 0.125, 0.375, 2.675, 1.005, 12.345, -12.345, 0.04, -0.04, 0.05,
                      0.00005, 0.0001, 0.12345678, 3.14159, 100, 100.25, 1234567.891, -0.00004)
TEXTOS_DE_FORMATO = ("texto", "asintotico", "permutacion_exacta", "permutacion_monte_carlo", "otro")
FORMATOS = ("entero", "texto", "dec1", "dec2", "dec3", "pct", "pp", "p", "tipo_p", "desconocido")


def casos_de_formato() -> dict:
    """Salida de `formatear` de la consola HTMX para valores y formatos fijos: la
    misma tabla la comprueba Vitest contra `formatear` del frontend. Con formato
    `texto` o `tipo_p` un numero se muestra con `str` (Python) o `String` (JS):
    solo entran los numeros en que ambos coinciden."""
    from app.api.web.routers.estadisticas_descriptivas import formatear
    from app.application.estadisticas.descriptivas import ETIQUETAS_TIPO_P_VALUE

    casos = []
    for formato in FORMATOS:
        for valor in (*VALORES_DE_FORMATO, *TEXTOS_DE_FORMATO):
            if formato in ("texto", "tipo_p") and isinstance(valor, float) and valor not in (2.5, 12.345, 3.14159, 100.25):
                continue
            casos.append({"valor": valor, "formato": formato, "esperado": formatear(valor, formato)})
    return {"origen": "app.api.web.routers.estadisticas_descriptivas.formatear",
            "etiquetas_tipo_p": dict(ETIQUETAS_TIPO_P_VALUE), "casos": casos}


def main(argv: list[str] | None = None) -> int:
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import OperationalError

    from app.api.publica import dependencias as d
    from app.api.publica.configuracion import ConfiguracionPublica, leer_claves
    from app.api.publica.seguridad import generar_clave, huella
    from tests import fase9_api_sintetica as f9
    from tests.unit import fixtures_fase4 as f4

    salida = Path((argv or sys.argv[1:])[0])
    salida.mkdir(parents=True, exist_ok=True)
    for viejo in salida.glob("*.json"):
        viejo.unlink()
    clave = generar_clave()
    claves = leer_claves(f"pruebas:sha256:{huella(clave)}")
    raiz = Path(tempfile.mkdtemp(prefix="f9-respuestas-"))
    datos = f9.preparar(raiz / "a")
    app = f9.crear(raiz / "a", ConfiguracionPublica(claves=claves, fichas_por_minuto=100_000,
                                                    fichas_por_minuto_ip=100_000), preparada=datos)
    c, h = TestClient(app), {"X-API-Key": clave}

    def guardar(nombre: str, url: str, cliente=c, cabeceras=h) -> dict:
        r = cliente.get(url, headers=cabeceras)
        muestra = {"escenario": f9.ESCENARIO, "url": url, "estado": r.status_code, "cuerpo": r.json()}
        if "retry-after" in r.headers:
            muestra["retry_after"] = r.headers["retry-after"]
        (salida / f"{nombre}.json").write_text(json.dumps(muestra, ensure_ascii=False, indent=1) + "\n",
                                               encoding="utf-8")
        return muestra["cuerpo"]

    guardar("global--juegos", "/api/v1/juegos")
    guardar("global--salud", "/api/v1/salud")
    guardar("global--estado", "/api/v1/estado")
    for j in JUEGOS:
        guardar(f"{j}--juego", f"/api/v1/juegos/{j}")
        guardar(f"{j}--indice", f"/api/v1/juegos/{j}/estadisticas")
        guardar(f"{j}--predicciones", f"/api/v1/juegos/{j}/predicciones")
        guardar(f"{j}--simulaciones", f"/api/v1/juegos/{j}/simulaciones")
    for j in ("BALOTO", "MILOTO", "COLORLOTO"):
        guardar(f"{j}--resumen", f"/api/v1/juegos/{j}/estadisticas/resumen")
        pagina = guardar(f"{j}--sorteos", f"/api/v1/juegos/{j}/sorteos?por_pagina=3")
        guardar(f"{j}--sorteo", f"/api/v1/juegos/{j}/sorteos/{pagina['sorteos'][0]['numero_sorteo']}")
    guardar("BALOTO--sorteos--vacio", "/api/v1/juegos/BALOTO/sorteos?numero_desde=999999")
    guardar("BALOTO--resumen--sin_sorteos", "/api/v1/juegos/BALOTO/estadisticas/resumen?hasta_numero_sorteo=1")
    guardar("BALOTO--panel", "/api/v1/juegos/BALOTO/estadisticas/panel")
    guardar("COLORLOTO--panel", "/api/v1/juegos/COLORLOTO/estadisticas/panel")
    for metrica in ("frecuencia-numeros-por-anio", "pruebas-uniformidad", "correlaciones",
                    "comparacion-frecuencia-numeros-por-ventana", "independencia-pares", "distribucion-sumas"):
        guardar(f"BALOTO--metrica--{metrica}", f"/api/v1/juegos/BALOTO/estadisticas/{metrica}")
    for m in guardar("COLORLOTO--indice", "/api/v1/juegos/COLORLOTO/estadisticas")["metricas"]:
        guardar(f"COLORLOTO--metrica--{m['metrica']}", f"/api/v1/juegos/COLORLOTO/estadisticas/{m['metrica']}")
    sims = c.get("/api/v1/juegos/COLORLOTO/simulaciones", headers=h).json()["simulaciones"]
    for s in sims:
        guardar(f"COLORLOTO--simulacion--{s['integridad']}", f"/api/v1/simulaciones/{s['id']}")

    # Errores producidos por la propia API.
    guardar("global--error--401", "/api/v1/juegos", cabeceras={})
    guardar("global--error--404", "/api/v1/juegos/QUINELA")
    guardar("global--error--422", "/api/v1/juegos/BALOTO/sorteos?pagina=0")
    vacio = f4.entorno(raiz / "sin-config")  # un centro de predicciones sin configuracion
    sin = f9.crear(raiz / "a", ConfiguracionPublica(claves=claves, fichas_por_minuto=100_000,
                                                    fichas_por_minuto_ip=100_000), preparada=datos)
    sin.dependency_overrides[d.centro_de_predicciones] = lambda: vacio.centro()
    guardar("BALOTO_REVANCHA--predicciones--sin_configuracion", "/api/v1/juegos/BALOTO_REVANCHA/predicciones",
            cliente=TestClient(sin))
    escasa = f9.crear(raiz / "a", ConfiguracionPublica(claves=claves, fichas_por_minuto=5, fichas_por_minuto_ip=100_000),
                      preparada=datos)
    cliente_escaso = TestClient(escasa)
    cliente_escaso.get("/api/v1/juegos/BALOTO/estadisticas/panel", headers=h)  # coste 5: agota la cuota
    guardar("global--error--429", "/api/v1/juegos", cliente=cliente_escaso)

    @contextmanager
    def lectura_caida():
        raise OperationalError("SELECT 1", {}, Exception("base sintetica caida"))
        yield

    def sesion_caida():
        raise OperationalError("SELECT 1", {}, Exception("base sintetica caida"))
        yield
    caida = f9.crear(raiz / "a", ConfiguracionPublica(claves=claves, fichas_por_minuto=100_000,
                                                      fichas_por_minuto_ip=100_000), preparada=datos)
    caida.dependency_overrides[d.sesion_de_lectura] = sesion_caida
    guardar("global--error--503", "/api/v1/juegos/BALOTO/sorteos", cliente=TestClient(caida))
    rota = f9.crear(raiz / "a", ConfiguracionPublica(claves=claves, fichas_por_minuto=100_000,
                                                     fichas_por_minuto_ip=100_000), preparada=datos)

    def fallar():
        raise RuntimeError("fallo sintetico")
    rota.dependency_overrides[d.listar_juegos] = fallar
    guardar("global--error--500", "/api/v1/juegos", cliente=TestClient(rota, raise_server_exceptions=False))
    (salida.parent / "formatos.json").write_text(json.dumps(casos_de_formato(), ensure_ascii=False, indent=1) + "\n",
                                                 encoding="utf-8")
    print(f"respuestas: {len(list(salida.glob('*.json')))} archivos en {salida.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
