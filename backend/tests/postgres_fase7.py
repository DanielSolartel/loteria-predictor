"""Fase 7: verificacion sobre un PostgreSQL DE PRUEBAS (no es una prueba de
pytest; SQLite no acredita lo que se comprueba aqui).

Se niega a correr si:
- `DATABASE_URL` no apunta a una base cuyo nombre contenga `prueba`, o
- la base contiene algun sorteo cuya fuente no sea `fixture_sintetica`.
Asi nunca toca la base real. Si los juegos no tienen sorteos, carga historicos
SINTETICOS; despues BORRA la tabla `simulaciones` de esa base de pruebas.

Comprueba con las dependencias reales (`get_simulaciones`, proceso trabajador
`spawn`, sesiones y transacciones de produccion):
 A. publicacion, ida y vuelta por JSONB con integridad verificada y
    reutilizacion; el contenido coincide con el calculo en este proceso;
 B. la lectura es una transaccion de solo lectura (PostgreSQL rechaza INSERT);
 C. 8 publicadores concurrentes de la misma identidad -> exactamente 1 fila;
 D. (informativo) la misma carrera sin el advisory, para ver que importa;
 E. el recurso de la clave retenido por otro -> espera acotada y error
    explicito (`lock_timeout`);
 F. el advisory de datos por juego de la Fase 6 no bloquea la publicacion;
 G. una fila alterada no se sirve ni se sobrescribe;
 H. el comando (`simular`, `listar`, `verificar --reproducir`) en procesos nuevos;
 I. la web lanza en segundo plano (hilo + trabajador) y se sigue el progreso;
 J. una comprobacion por fila con JSONB real: la fila de otro juego, un
    `resultado_resumen` lista y unos `parametros` lista no derriban el
    listado ni el panel ni se atribuyen a la base.

Uso (desde `backend`, con DATABASE_URL de la base de PRUEBAS y una carpeta
temporal en DIRECTORIO_SIMULACIONES):
  python tests/postgres_fase7.py
Salida: JSON por la salida estandar; codigo 0 solo si A-C y E-J se cumplen.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _negarse(motivo: str) -> int:
    sys.stderr.write(f"NEGADO: {motivo}\n")
    return 2


def main() -> int:
    from sqlalchemy import text

    from app.infrastructure.db import session as dbs

    if "prueba" not in (dbs.engine.url.database or "") or dbs.engine.dialect.name != "postgresql":
        return _negarse("DATABASE_URL debe apuntar a un PostgreSQL de pruebas (nombre con 'prueba')")
    with dbs.SessionLocal() as s:
        ajenos = s.execute(text("SELECT count(*) FROM sorteos WHERE fuente IS DISTINCT FROM 'fixture_sintetica'")
                           ).scalar_one()
        if ajenos:
            return _negarse(f"la base tiene {ajenos} sorteos que no son sinteticos")
        revision = s.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        total = s.execute(text("SELECT count(*) FROM sorteos")).scalar_one()
    if not os.environ.get("DIRECTORIO_SIMULACIONES"):
        return _negarse("define DIRECTORIO_SIMULACIONES en una carpeta temporal")
    from tests.unit.simulaciones import fixtures_fase7 as f7

    if total == 0:
        with dbs.SessionLocal() as s:
            for j, datos in f7.historicos({"BALOTO": 645, "BALOTO_REVANCHA": 645, "MILOTO": 97,
                                           "COLORLOTO": 229}).items():
                f7.guardar_sorteos(s, j, datos)
            s.commit()
    with dbs.engine.begin() as c:
        c.execute(text("DELETE FROM simulaciones"))
        version = c.execute(text("SHOW server_version")).scalar_one()

    from app.api import dependencies as dep
    from app.application.interfaces.simulaciones_repository import PublicacionConcurrenteError
    from app.application.ml import laboratorio_variables as lv
    from app.application.fase7 import artefacto as fa
    from app.application.fase7 import motor as fm
    from app.application.use_cases.simulaciones import SimulacionesError
    from app.domain.entities.analitica import Simulacion
    from app.infrastructure.operacion_advisory import clave_de_juego
    from app.infrastructure.repositories import simulaciones_repository_sqlalchemy as rs

    resultados: dict = {"postgresql": version, "alembic_revision": revision, "comprobaciones": {}}
    ok = resultados["comprobaciones"]
    servicio = dep.get_simulaciones()

    def contar(clave):
        with dbs.SessionLocal() as s:
            return s.execute(text("SELECT count(*) FROM simulaciones WHERE parametros ->> 'clave' = :c"),
                             {"c": clave}).scalar_one()

    # A. publicacion, JSONB, reutilizacion y determinismo frente al proceso local
    primera = servicio.ahora("MILOTO", 1_000, 7)["juegos"]["MILOTO"]
    segunda = servicio.ahora("MILOTO", 1_000, 7)["juegos"]["MILOTO"]
    fila = servicio.obtener(primera["resultado"])
    from app.application.use_cases.laboratorio import leer_historico

    with dep.abrir_lectura_de_simulaciones() as lectura:
        canonicos = lv.sorteos_canonicos(lv.validar_instantanea("MILOTO", leer_historico(lectura, "MILOTO")))
    local = fa.sha256(fm.calcular("MILOTO", canonicos, 1_000, 7)["contenido"])
    ok["A_publicacion_jsonb_y_reutilizacion"] = (
        primera["estado"] == "terminado" and segunda["estado"] == "reutilizado"
        and segunda["resultado"] == primera["resultado"] and fila["integridad"] == "verificada"
        and fila["resultado_resumen"]["contenido_sha256"] == local and contar(primera["clave"]) == 1)

    # B. lectura de solo lectura
    try:
        with dep.abrir_lectura_de_simulaciones() as lectura:
            lectura.simulaciones_repository._session.execute(text(
                "INSERT INTO simulaciones (id, juego_id, num_iteraciones, parametros, resultado_resumen) "
                "SELECT gen_random_uuid(), id, 1, '{}', '{}' FROM juegos LIMIT 1"))
        ok["B_lectura_solo_lectura"] = False
    except Exception as error:
        ok["B_lectura_solo_lectura"] = "read-only" in str(error)

    # Una fila nueva (identidad distinta) para las carreras
    def fila_nueva(semilla):
        h = fm.preparar("MILOTO", lv.instantanea_desde_canonicos("MILOTO", canonicos).sorteos)
        p = fa.parametros(fa.identidad(h, 100, semilla))
        c = fm.calcular("MILOTO", canonicos, 100, semilla)
        with dbs.SessionLocal() as s:
            juego_id = s.execute(text("SELECT id FROM juegos WHERE codigo = 'MILOTO'")).scalar_one()
        return Simulacion(None, juego_id, 100, p, fa.resultado(p, c["contenido"], c["procesamiento"]), duracion_ms=1), \
            p["clave"]

    def carrera(simulacion, clave, n=8):
        barrera, salida, errores = threading.Barrier(n), [], []

        def publicar():
            s = dbs.SessionLocal()
            try:
                barrera.wait()
                f, creada = rs.SimulacionesRepositorySQLAlchemy(s).publicar(simulacion, clave)
                s.commit()
                salida.append((str(f.id), creada))
            except Exception as error:  # noqa: BLE001 - se informa
                errores.append(repr(error))
                s.rollback()
            finally:
                s.close()
        hilos = [threading.Thread(target=publicar) for _ in range(n)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        return salida, errores

    # C. 8 publicadores concurrentes
    sim, clave = fila_nueva(101)
    salida, errores = carrera(sim, clave)
    ok["C_concurrencia_una_fila"] = (not errores and sum(c for _, c in salida) == 1 and len({i for i, _ in salida}) == 1
                                     and contar(clave) == 1)
    resultados["C_detalle"] = {"publicadores": len(salida), "creadas": sum(c for _, c in salida), "errores": errores}

    # D. (informativo) la misma carrera sin el advisory
    sim, clave = fila_nueva(102)
    original = rs.SimulacionesRepositorySQLAlchemy._tomar_recurso
    rs.SimulacionesRepositorySQLAlchemy._tomar_recurso = lambda self, clave: None
    try:
        salida, errores = carrera(sim, clave)
    finally:
        rs.SimulacionesRepositorySQLAlchemy._tomar_recurso = original
    resultados["D_sin_advisory_informativo"] = {"filas_con_la_misma_clave": contar(clave), "errores": errores}
    with dbs.engine.begin() as c:
        c.execute(text("DELETE FROM simulaciones WHERE parametros ->> 'clave' = :c"), {"c": clave})

    # E. recurso retenido -> espera acotada y error explicito
    sim, clave = fila_nueva(103)
    retenedor = dbs.SessionLocal()
    retenedor.execute(text("SELECT pg_advisory_xact_lock(:r)"), {"r": rs.recurso_de_clave(clave)})
    inicio = time.monotonic()
    s = dbs.SessionLocal()
    try:
        rs.SimulacionesRepositorySQLAlchemy(s).publicar(sim, clave)
        ok["E_espera_acotada"] = False
    except PublicacionConcurrenteError:
        espera = time.monotonic() - inicio
        resultados["E_espera_s"] = round(espera, 2)
        ok["E_espera_acotada"] = 9.0 <= espera <= 20.0 and contar(clave) == 0
    finally:
        s.rollback()
        s.close()
        retenedor.rollback()
        retenedor.close()

    # F. el advisory de datos de la Fase 6 no bloquea la publicacion
    with dbs.SessionLocal() as s:
        juego_id = s.execute(text("SELECT id FROM juegos WHERE codigo = 'MILOTO'")).scalar_one()
    datos = dbs.engine.connect()
    datos.execute(text("SELECT pg_advisory_lock(:k)"), {"k": clave_de_juego(juego_id)})
    try:
        inicio = time.monotonic()
        with dbs.SessionLocal() as s:
            _, creada = rs.SimulacionesRepositorySQLAlchemy(s).publicar(sim, clave)
            s.commit()
        ok["F_independiente_del_advisory_de_datos"] = creada and time.monotonic() - inicio < 5
    finally:
        datos.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": clave_de_juego(juego_id)})
        datos.close()

    # G. fila alterada
    with dbs.engine.begin() as c:
        c.execute(text("UPDATE simulaciones SET resultado_resumen = jsonb_set(resultado_resumen, '{contenido,nota}', "
                       "'\"alterada\"') WHERE id = :i"), {"i": primera["resultado"]})
    try:
        servicio.obtener(primera["resultado"])
        servida = True
    except SimulacionesError as error:
        servida = error.codigo != "alterado"
    repetida = servicio.ahora("MILOTO", 1_000, 7)["juegos"]["MILOTO"]
    ok["G_alterada_no_se_sirve_ni_sobrescribe"] = (not servida and repetida["estado"] == "alterado"
                                                   and contar(primera["clave"]) == 1)

    # H. comando en procesos nuevos
    def comando(*argv):
        r = subprocess.run([sys.executable, "-B", "-m", "scripts.simulaciones", *argv], cwd=BACKEND,
                           capture_output=True, text=True, timeout=1800)
        return r.returncode, r.stdout
    codigo, salida = comando("simular", "--juego", "COLORLOTO", "--iteraciones", "10000")
    ident = json.loads(salida)["juegos"]["COLORLOTO"]["resultado"] if codigo == 0 else None
    codigos = [codigo, comando("listar", "--juego", "COLORLOTO")[0],
               comando("verificar", "--id", ident or "x", "--reproducir")[0],
               comando("simular", "--juego", "COLORLOTO", "--iteraciones", "10000")[0]]
    ok["H_comando"] = codigos == [0, 0, 0, 0]
    resultados["H_codigos"] = codigos

    # I. la web lanza en segundo plano con el lanzador real
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app, base_url="http://localhost:8000", client=("127.0.0.1", 5555))
    tok = c.get("/simulaciones").text.split('name="token_local" value="', 1)[1].split('"', 1)[0]
    r = c.post("/simulaciones/simular", data={"token_local": tok, "juego": "baloto", "iteraciones": 10000},
               follow_redirects=False)
    eid = r.headers["location"].rsplit("/", 1)[1]
    sondeos, limite = 0, time.monotonic() + 600
    while time.monotonic() < limite:
        e = c.get(f"/api/simulaciones/ejecuciones/{eid}").json()
        sondeos += 1
        if e["estado"] != "en_curso":
            break
        time.sleep(0.5)
    rb = e["juegos"]["BALOTO"]
    ok["I_web_en_segundo_plano"] = (r.status_code == 303 and e["estado"] == "exito" and rb["estado"] == "terminado"
                                    and c.get(f"/simulaciones/resultados/{rb['resultado']}").status_code == 200)
    resultados["I_sondeos"] = sondeos

    # J. una comprobacion por fila con JSONB real
    def publicada(semilla):
        simulacion, clave_ = fila_nueva(semilla)
        with dbs.SessionLocal() as s:
            f, _ = rs.SimulacionesRepositorySQLAlchemy(s).publicar(simulacion, clave_)
            s.commit()
        return str(f.id)

    def lectura_de(ident):
        try:
            servicio.obtener(ident)
            return "servida"
        except SimulacionesError as error:
            return error.codigo
    otro, lista, sin_objeto = publicada(104), publicada(105), publicada(106)
    with dbs.engine.begin() as c:
        c.execute(text("UPDATE simulaciones SET juego_id = (SELECT id FROM juegos WHERE codigo = 'BALOTO') "
                       "WHERE id = :i"), {"i": otro})
        c.execute(text("UPDATE simulaciones SET resultado_resumen = '[1]'::jsonb WHERE id = :i"), {"i": lista})
        c.execute(text("UPDATE simulaciones SET parametros = '[1]'::jsonb WHERE id = :i"), {"i": sin_objeto})
    baloto = {x["id"]: x["integridad"] for x in servicio.listar("BALOTO")}
    miloto = {x["id"]: x["integridad"] for x in servicio.listar("MILOTO")}
    diagnostico = servicio.diagnostico("MILOTO")["estado"]
    lecturas = [lectura_de(otro), lectura_de(lista), lectura_de(sin_objeto)]
    ok["J_comprobacion_por_fila"] = (baloto.get(otro) == "alterada" and miloto.get(lista) == "alterada"
                                     and sin_objeto not in miloto and "verificada" in miloto.values()
                                     and diagnostico == "disponible"
                                     and lecturas == ["alterado", "alterado", "no_encontrado"])
    resultados["J_detalle"] = {"otro_juego_en_listado": baloto.get(otro),
                               "resultado_lista_en_listado": miloto.get(lista),
                               "parametros_lista_listados": sin_objeto in miloto, "diagnostico_miloto": diagnostico,
                               "lecturas": lecturas}

    with dbs.SessionLocal() as s:
        resultados["filas_finales"] = s.execute(text("SELECT count(*) FROM simulaciones")).scalar_one()
    resultados["instante"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(resultados, indent=1, sort_keys=True))
    exigidas = [k for k in ok if not k.startswith("D_")]
    return 0 if all(ok[k] for k in exigidas) else 1


if __name__ == "__main__":
    sys.exit(main())
