"""Fase 10 (E10.2): verificacion del perfil privado sobre un PostgreSQL DE PRUEBAS (no es una prueba de pytest).

Complementa `tests/postgres_fase8.py` (que debe ejecutarse antes, con el rol propietario, y deja historicos
SINTETICOS cargados). Exige dos URL de la MISMA base de pruebas (nombre con «prueba»), creada con
`despliegue/consulta-privada/postgres/roles.sql` y migrada por el propietario:

- `DATABASE_URL`: rol PROPIETARIO (escritura: bloqueos de prueba y sesion de escritura de siempre);
- `E102_URL_LECTOR`: rol LECTOR de la API privada.

Comprueba:
 P1. el rol lector no escribe: INSERT -> 25006 (solo lectura por defecto); sin ella, INSERT/UPDATE/DELETE/
     CREATE/TRUNCATE -> 42501; SELECT permitido;
 P2. limites PROPIOS del rol (sin opciones de la aplicacion): `statement_timeout` (57014) e
     `idle_in_transaction_session_timeout` (sesion terminada);
 P3. opciones del motor de la API (`BASE_*`): una consulta lenta se cancela y la MISMA conexion del pool
     vuelve sana (ROLLBACK); una transaccion inactiva se termina y el pool la sustituye;
 P4. API privada en proceso con el rol lector (cableado predeterminado, almacenes vacios de solo lectura):
     200; con la tabla `sorteos` bloqueada, 503 `consulta_cancelada` / `consultas_ocupadas` con Retry-After;
     al liberar, 200 de nuevo; ninguna fila cambia y no se crea ningun archivo;
 P5. la sesion de escritura de siempre (consola/CLI/Fase 6: `opciones_del_motor` sin `BASE_*`) no recibe
     limites: `statement_timeout` 0 y escribe y confirma.
Salida: JSON; codigo 0 solo si P1-P5 se cumplen. No imprime URL ni claves.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _negarse(motivo: str) -> int:
    sys.stderr.write(f"NEGADO: {motivo}\n")
    return 2


def _psycopg(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _sqlstate(conectar, sentencias) -> str:
    import psycopg

    try:
        with psycopg.connect(conectar, autocommit=True) as c:
            for s in sentencias:
                c.execute(s)
        return "permitido"
    except psycopg.Error as error:
        return error.sqlstate or type(error).__name__


def main() -> int:
    propietario, lector = os.environ.get("DATABASE_URL", ""), os.environ.get("E102_URL_LECTOR", "")
    if not propietario or not lector:
        return _negarse("faltan DATABASE_URL (propietario) o E102_URL_LECTOR (lector)")
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    for url in (propietario, lector):
        u = make_url(url)
        if u.get_backend_name() != "postgresql" or "prueba" not in (u.database or ""):
            return _negarse("las dos URL deben ser de un PostgreSQL de pruebas (nombre con 'prueba')")
    if make_url(propietario).database != make_url(lector).database:
        return _negarse("propietario y lector deben apuntar a la misma base")
    import psycopg

    dueno, solo = _psycopg(propietario), _psycopg(lector)
    with psycopg.connect(dueno) as c:
        if c.execute("SELECT count(*) FROM sorteos WHERE fuente IS DISTINCT FROM 'fixture_sintetica'").fetchone()[0]:
            return _negarse("la base tiene sorteos que no son sinteticos")
        if not c.execute("SELECT count(*) FROM sorteos").fetchone()[0]:
            return _negarse("sin historicos: ejecute antes tests/postgres_fase8.py")
    ok: dict[str, bool] = {}
    detalles: dict = {}

    # P1 -------------------------------------------------------------------------------------------------
    insertar = "INSERT INTO juegos(codigo, nombre) VALUES ('E102', 'e102')"
    sin_ro = "SET default_transaction_read_only = off"
    p1 = {"insert": _sqlstate(solo, [insertar]), "insert_sin_solo_lectura": _sqlstate(solo, [sin_ro, insertar]),
          "update": _sqlstate(solo, [sin_ro, "UPDATE sorteos SET fuente = fuente"]),
          "delete": _sqlstate(solo, [sin_ro, "DELETE FROM simulaciones"]),
          "create": _sqlstate(solo, [sin_ro, "CREATE TABLE e102 (x int)"]),
          "truncate": _sqlstate(solo, [sin_ro, "TRUNCATE sorteos"]),
          "select": _sqlstate(solo, ["SELECT count(*) FROM sorteos"])}
    detalles["P1"] = p1
    ok["P1_rol_lector_sin_escritura"] = (p1["insert"] == "25006" and p1["select"] == "permitido"
                                        and all(p1[k] == "42501" for k in ("insert_sin_solo_lectura", "update",
                                                                          "delete", "create", "truncate")))

    # P2 -------------------------------------------------------------------------------------------------
    lenta = _sqlstate(solo, ["SELECT pg_sleep(3)"])
    try:
        with psycopg.connect(solo) as c:
            c.execute("SELECT 1")
            time.sleep(6.5)
            c.execute("SELECT 1")
        inactiva = "permitido"
    except psycopg.Error as error:
        inactiva = error.sqlstate or type(error).__name__
    detalles["P2"] = {"consulta_lenta": lenta, "inactiva_en_transaccion": inactiva}
    ok["P2_limites_del_rol"] = lenta == "57014" and inactiva != "permitido"

    # Entorno de la API privada ANTES de importar `app`: el motor del modulo de sesion se crea al importarlo.
    almacenes = Path(tempfile.mkdtemp(prefix="e102-almacenes-"))
    for nombre in ("laboratorio", "carteras", "predicciones", "pronosticos"):
        (almacenes / nombre).mkdir()
    for raiz, carpetas, archivos in os.walk(almacenes):
        os.chmod(raiz, 0o555)
    os.environ.update({
        "DATABASE_URL": lector, "BASE_TIEMPO_MAXIMO_CONSULTA_MS": "1500", "BASE_TIEMPO_MAXIMO_INACTIVA_MS": "5000",
        "BASE_POOL_TAMANO": "4", "BASE_POOL_DESBORDE": "0", "BASE_POOL_ESPERA_S": "3",
        "API_PUBLICA_HOSTS": "api.e102.prueba:8010", "API_PUBLICA_CLIENTES": "10.0.0.10",
        "API_PUBLICA_CONCURRENCIA_COSTOSAS": "1", "API_PUBLICA_ESPERA_COSTOSAS": "0.3",
        "API_PUBLICA_FICHAS_POR_MINUTO": "1000", "API_PUBLICA_FICHAS_POR_MINUTO_IP": "1000",
        "DIRECTORIO_LABORATORIO_MODELOS": str(almacenes / "laboratorio"),
        "DIRECTORIO_CARTERAS_MODELOS": str(almacenes / "carteras"),
        "DIRECTORIO_PREDICCIONES_MODELOS": str(almacenes / "predicciones"),
        "DIRECTORIO_PRONOSTICOS_EXPERIMENTALES": str(almacenes / "pronosticos"),
        "DIRECTORIO_RESULTADOS_MODELOS": str(almacenes / "no-publicado" / "resultados"),
        "DIRECTORIO_SIMULACIONES": str(almacenes / "no-publicado" / "simulaciones")})
    # P3 -------------------------------------------------------------------------------------------------
    from app.infrastructure.db.session import opciones_del_motor

    ajustes = SimpleNamespace(database_url=lector, base_tiempo_maximo_consulta_ms=500,
                              base_tiempo_maximo_inactiva_ms=1000, base_pool_tamano=1, base_pool_desborde=0,
                              base_pool_espera_s=2.0)
    motor = create_engine(lector, **opciones_del_motor(ajustes))
    try:
        with motor.connect() as c:
            pid = c.execute(text("SELECT pg_backend_pid()")).scalar_one()
            try:
                c.execute(text("SELECT pg_sleep(2)"))
                cancelada = "permitido"
            except Exception as error:  # noqa: BLE001 - se informa el SQLSTATE
                cancelada = getattr(getattr(error, "orig", None), "sqlstate", type(error).__name__)
            c.rollback()
            misma = c.execute(text("SELECT pg_backend_pid()")).scalar_one() == pid
            tiempo = c.execute(text("SHOW statement_timeout")).scalar_one()
        with motor.connect() as c:
            c.execute(text("SELECT 1"))
            time.sleep(1.5)
            try:
                c.execute(text("SELECT 1"))
                terminada = "permitido"
            except Exception as error:  # noqa: BLE001
                terminada = type(error).__name__
        with motor.connect() as c:
            sustituida = c.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        motor.dispose()
    detalles["P3"] = {"cancelada": cancelada, "misma_conexion_sana": misma, "statement_timeout": tiempo,
                      "inactiva": terminada, "pool_la_sustituye": sustituida}
    ok["P3_opciones_del_motor"] = (cancelada == "57014" and misma and tiempo == "500ms" and terminada != "permitido"
                                   and sustituida)

    # P4 -------------------------------------------------------------------------------------------------
    from app.api.publica.seguridad import generar_clave, huella

    clave = generar_clave()
    os.environ["API_PUBLICA_CLAVES"] = f"pasarela:sha256:{huella(clave)}"
    from app.core.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.api.publica import aplicacion, perfil_privado

    app = aplicacion.crear_app()
    perfil_privado.comprobar(get_settings(), app.state.configuracion, es_root=False)
    cliente = TestClient(app, base_url="http://api.e102.prueba:8010", client=("10.0.0.10", 40000))
    cabeceras = {"X-API-Key": clave}
    ruta = "/api/v1/juegos/BALOTO/estadisticas/resumen"

    def filas() -> dict:
        with psycopg.connect(dueno) as c:
            tablas = [r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")]
            return {t: c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in sorted(tablas)}

    antes = filas()
    normal = cliente.get(ruta, headers=cabeceras)
    bloqueada = threading.Event()

    def bloquear(segundos: float):
        with psycopg.connect(dueno) as c:
            c.execute("LOCK TABLE sorteos IN ACCESS EXCLUSIVE MODE")
            bloqueada.set()
            time.sleep(segundos)
            c.rollback()

    hilo = threading.Thread(target=bloquear, args=(4.0,))
    hilo.start()
    bloqueada.wait(10)
    with concurrent.futures.ThreadPoolExecutor(2) as hilos:
        respuestas = list(hilos.map(lambda _: cliente.get(ruta, headers=cabeceras), range(2)))
    hilo.join()
    codigos = sorted(f"{r.status_code}:{r.json()['error']['codigo']}" for r in respuestas if r.status_code != 200)
    tras = cliente.get(ruta, headers=cabeceras)
    despues = filas()
    archivos = sorted(str(p.relative_to(almacenes)) for p in almacenes.rglob("*"))
    detalles["P4"] = {"normal": normal.status_code, "bloqueada": codigos,
                      "retry_after": [r.headers.get("retry-after") for r in respuestas],
                      "tras_liberar": tras.status_code, "filas_iguales": antes == despues, "archivos": archivos}
    ok["P4_api_privada"] = (normal.status_code == 200 and codigos == ["503:consulta_cancelada",
                                                                      "503:consultas_ocupadas"]
                            and all(r.headers.get("retry-after") for r in respuestas) and tras.status_code == 200
                            and antes == despues and archivos == ["carteras", "laboratorio", "predicciones",
                                                                  "pronosticos"])

    # P5 -------------------------------------------------------------------------------------------------
    normales = SimpleNamespace(database_url=propietario, base_tiempo_maximo_consulta_ms=0,
                               base_tiempo_maximo_inactiva_ms=0, base_pool_tamano=0, base_pool_desborde=0,
                               base_pool_espera_s=0.0)
    opciones = opciones_del_motor(normales)
    motor = create_engine(propietario, **opciones)
    nombre = "e102_" + hashlib.sha256(os.urandom(8)).hexdigest()[:8]
    try:
        with motor.begin() as c:
            tiempo = c.execute(text("SHOW statement_timeout")).scalar_one()
            c.execute(text(f"CREATE TABLE {nombre} (x int)"))
            c.execute(text(f"INSERT INTO {nombre} VALUES (1)"))
        with motor.begin() as c:
            confirmada = c.execute(text(f"SELECT count(*) FROM {nombre}")).scalar_one()
            c.execute(text(f"DROP TABLE {nombre}"))
    finally:
        motor.dispose()
    detalles["P5"] = {"opciones": sorted(opciones), "statement_timeout": tiempo, "escritura_confirmada": confirmada}
    ok["P5_sesion_de_escritura_sin_cambios"] = (opciones == {"pool_pre_ping": True, "future": True} and tiempo == "0"
                                                and confirmada == 1)

    with psycopg.connect(dueno) as c:
        version = c.execute("SHOW server_version").fetchone()[0]
    print(json.dumps({"postgres": version, "ok": ok, "detalles": detalles, "todo_correcto": all(ok.values())},
                     ensure_ascii=False, indent=1))
    return 0 if all(ok.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
