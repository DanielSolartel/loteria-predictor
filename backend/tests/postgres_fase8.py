"""Fase 8: verificacion de la API publica sobre un PostgreSQL DE PRUEBAS (no es
una prueba de pytest; SQLite no acredita `SET TRANSACTION READ ONLY`).

Se niega a correr si `DATABASE_URL` no apunta a una base cuyo nombre contenga
`prueba` o si hay sorteos que no sean `fixture_sintetica`. Si no hay sorteos,
carga historicos SINTETICOS; publica una simulacion sintetica para tener una
fila que leer. Las claves se generan en este proceso y nunca se imprimen.

Comprueba con el cableado PREDETERMINADO (sin sustituir dependencias):
 A. todas las consultas responden 200 (juegos, sorteos, estadisticas,
    predicciones con almacenes vacios, simulaciones y estado con base disponible);
    A2: un historico inconsistente (ColorLoto sintetico frente a la paleta sembrada)
    responde 409 `historico_no_valido` (contrato vigente) sin el motivo interno;
 B. la sesion de la API publica es de solo lectura (PostgreSQL rechaza escribir);
 C. ninguna consulta cambia filas (todas las tablas) ni crea archivos;
 D. 24 solicitudes HTTP simultaneas con cuota 10 -> exactamente 10 x 200 y 14 x 429;
 E. ninguna escritura: POST/PUT/PATCH/DELETE devuelven 404/405 y nada cambia;
 F. un proceso Uvicorn real con el arranque soportado de `docs/fase8_api_publica.md`
    (`--no-access-log --no-proxy-headers`), configurado por entorno, responde
    200/401/401/404/404 y sus registros no contienen la clave, su huella ni una
    clave enviada en la URL.

Uso (desde `backend`, con DATABASE_URL de la base de PRUEBAS):
  python tests/postgres_fase8.py
Salida: JSON; codigo 0 solo si A-F se cumplen.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _negarse(motivo: str) -> int:
    sys.stderr.write(f"NEGADO: {motivo}\n")
    return 2


def _arbol(raiz: Path) -> list:
    return sorted((str(p.relative_to(raiz)), hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "")
                  for p in raiz.rglob("*"))


def main() -> int:
    from sqlalchemy import text

    from app.infrastructure.db import session as dbs

    if "prueba" not in (dbs.engine.url.database or "") or dbs.engine.dialect.name != "postgresql":
        return _negarse("DATABASE_URL debe apuntar a un PostgreSQL de pruebas (nombre con 'prueba')")
    with dbs.SessionLocal() as s:
        if s.execute(text("SELECT count(*) FROM sorteos WHERE fuente IS DISTINCT FROM 'fixture_sintetica'")).scalar_one():
            return _negarse("la base tiene sorteos que no son sinteticos")
        revision = s.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        total = s.execute(text("SELECT count(*) FROM sorteos")).scalar_one()
        version = s.execute(text("SHOW server_version")).scalar_one()
    almacenes = Path(tempfile.mkdtemp(prefix="f8-almacenes-"))
    for nombre in ("PRONOSTICOS_EXPERIMENTALES", "OPERACION", "LABORATORIO_MODELOS", "CARTERAS_MODELOS",
                   "RESULTADOS_MODELOS", "PREDICCIONES_MODELOS", "AUTOMATIZACION", "SIMULACIONES"):
        os.environ[f"DIRECTORIO_{nombre}"] = str(almacenes / nombre.lower())
    from app.core.config import get_settings

    get_settings.cache_clear()
    from tests.unit.simulaciones import fixtures_fase7 as f7

    if total == 0:
        with dbs.SessionLocal() as s:
            for j, datos in f7.historicos({"BALOTO": 645, "BALOTO_REVANCHA": 645, "MILOTO": 97, "COLORLOTO": 229}).items():
                f7.guardar_sorteos(s, j, datos)
            s.commit()
    from fastapi.testclient import TestClient
    import httpx

    from app.api import dependencies as dep
    from app.api.publica import aplicacion
    from app.api.publica import dependencias as d
    from app.api.publica.configuracion import ConfiguracionPublica, leer_claves
    from app.api.publica.seguridad import generar_clave, huella

    simulacion = dep.get_simulaciones().ahora("MILOTO", 100, 20261024, origen="prueba_fase8")["juegos"]["MILOTO"]
    clave = generar_clave()
    entrada = f"pg:sha256:{huella(clave)}"
    resultados: dict = {"postgresql": version, "alembic_revision": revision, "comprobaciones": {}}
    ok = resultados["comprobaciones"]

    def filas() -> dict:
        with dbs.engine.connect() as c:
            tablas = [r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))]
            return {t: hashlib.sha256(json.dumps(sorted(map(str, c.execute(text(f'SELECT * FROM "{t}"')).all())))
                                      .encode()).hexdigest() for t in sorted(tablas)}

    app = aplicacion.crear_app(ConfiguracionPublica(claves=leer_claves(entrada), fichas_por_minuto=10_000,
                                                    fichas_por_minuto_ip=100_000))
    c = TestClient(app)
    h = {"X-API-Key": clave}
    antes_filas, antes_arbol = filas(), _arbol(almacenes)

    # A. consultas con el cableado predeterminado
    urls = ["/api/v1/salud", "/api/v1/juegos", "/api/v1/juegos/COLORLOTO", "/api/v1/juegos/BALOTO/sorteos?por_pagina=50",
            "/api/v1/juegos/MILOTO/sorteos?orden=numero_asc&por_pagina=1", "/api/v1/juegos/BALOTO/estadisticas",
            "/api/v1/juegos/BALOTO/estadisticas/resumen", "/api/v1/juegos/BALOTO/estadisticas/panel",
            "/api/v1/juegos/COLORLOTO/estadisticas/resumen",
            "/api/v1/juegos/BALOTO/estadisticas/frecuencia-numeros-por-anio", "/api/v1/juegos/MILOTO/predicciones",
            "/api/v1/juegos/MILOTO/simulaciones", f"/api/v1/simulaciones/{simulacion['resultado']}", "/api/v1/estado"]
    codigos = {u: c.get(u, headers=h).status_code for u in urls}
    detalle = c.get(f"/api/v1/simulaciones/{simulacion['resultado']}", headers=h).json()
    estado = c.get("/api/v1/estado", headers=h).json()
    ok["A_consultas_cableado_predeterminado"] = (all(v == 200 for v in codigos.values())
                                                 and detalle["integridad"] == "verificada" and estado["base"] == "disponible")
    resultados["A_codigos"] = codigos
    # A2. Los sorteos sinteticos de ColorLoto son anteriores a la vigencia de la paleta que siembran las
    # migraciones: el caso de uso los rechaza como historico inconsistente. Desde la Fase 9 la API responde
    # el 409 `historico_no_valido` que declara su OpenAPI (antes, 500 generico), sin el motivo interno.
    # Fase 10 (E10.3): esta verificacion pasa a ejecutarse en el CI; la expectativa de 500 estaba desfasada
    # (la base 375fc8ca tambien responde 409).
    inconsistente = c.get("/api/v1/juegos/COLORLOTO/estadisticas/panel", headers=h)
    ok["A2_historico_inconsistente_sin_detalles"] = (inconsistente.status_code == 409
                                                     and inconsistente.json()["error"]["codigo"] == "historico_no_valido"
                                                     and "paleta" not in inconsistente.text
                                                     and "numero_sorteo" not in inconsistente.text)

    # B. la sesion de la API publica es de solo lectura
    sesiones = d.sesion_de_lectura()
    try:
        next(sesiones).execute(text("CREATE TABLE f8_intento_de_escritura (x integer)"))
        ok["B_sesion_de_solo_lectura"] = False
    except Exception as error:  # noqa: BLE001 - se informa el tipo
        ok["B_sesion_de_solo_lectura"] = "read-only" in str(error)
    finally:
        sesiones.close()

    # D. concurrencia real sobre PostgreSQL
    app_d = aplicacion.crear_app(ConfiguracionPublica(claves=leer_claves(entrada), fichas_por_minuto=10,
                                                      fichas_por_minuto_ip=100_000))

    async def carrera():
        transporte = httpx.ASGITransport(app=app_d, client=("127.0.0.1", 1))
        async with httpx.AsyncClient(transport=transporte, base_url="http://t") as cli:
            return await asyncio.gather(*(cli.get("/api/v1/juegos", headers=h) for _ in range(24)))
    respuestas = asyncio.run(carrera())
    estados = sorted(r.status_code for r in respuestas)
    ok["D_concurrencia_429"] = (estados == [200] * 10 + [429] * 14
                                and all(int(r.headers["Retry-After"]) >= 1 for r in respuestas if r.status_code == 429))
    resultados["D_estados"] = {"200": estados.count(200), "429": estados.count(429)}

    # E. ninguna escritura
    escrituras = []
    for metodo in ("post", "put", "patch", "delete"):
        for url in ("/api/v1/juegos", "/api/sorteos", f"/api/sorteos/{simulacion['resultado']}", "/simulaciones/simular"):
            escrituras.append(getattr(c, metodo)(url, headers=h).status_code)
    ok["E_sin_escrituras"] = all(s in (404, 405) for s in escrituras)

    # C. nada cambio
    ok["C_preserva_filas_y_almacenes"] = filas() == antes_filas and _arbol(almacenes) == antes_arbol

    # F. proceso Uvicorn real con el arranque soportado de la guia, configurado por entorno
    from tests.unit.api_publica import fixtures_api_publica as fa

    registro = Path(tempfile.mkdtemp(prefix="f8-uvicorn-")) / "uvicorn.log"
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("UVICORN_") and k != "FORWARDED_ALLOW_IPS"}
    entorno.update({"API_PUBLICA_CLAVES": entrada, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"})
    argumentos = fa.arranque_documentado()
    with fa.proceso_uvicorn(argumentos, entorno, registro) as base, httpx.Client(base_url=base, trust_env=False,
                                                                                 timeout=10) as real:
        reales = [real.get("/api/v1/juegos", headers=h).status_code,
                  real.get("/api/v1/juegos", headers={"X-API-Key": generar_clave()}).status_code,
                  real.get("/api/v1/juegos", params={"api_key": clave}).status_code,
                  real.get("/api/sorteos?codigo_juego=BALOTO", headers=h).status_code,
                  real.post("/api/sorteos", headers=h, json={}).status_code]
    texto = registro.read_text(encoding="utf-8", errors="replace")
    lineas = [linea for linea in texto.splitlines() if "app.api.publica api_publica" in linea]
    ok["F_uvicorn_real"] = (reales == [200, 401, 401, 404, 404] and clave not in texto and huella(clave) not in texto
                            and "api_key" not in texto and len(lineas) >= 5
                            and any("clave=pg" in linea for linea in lineas))
    resultados["F_codigos"] = reales
    resultados["F_lineas_de_monitoreo"] = len(lineas)
    resultados["F_opciones_de_arranque"] = [a for a in argumentos if a.startswith("--no-")]

    resultados["instante"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(resultados, indent=1, sort_keys=True))
    return 0 if all(ok.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
