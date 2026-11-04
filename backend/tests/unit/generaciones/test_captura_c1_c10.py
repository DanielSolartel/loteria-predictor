"""E10.4: escenarios C1-C10 de la enmienda 01 (seccion 3.5) como pruebas de COMPORTAMIENTO sobre PostgreSQL real
y los almacenes de la aplicacion, con artefactos de los productores reales (`conftest.plantilla`).

Los escritores se simulan con las primitivas REALES (transacciones de otra conexion, `CerrojoPorJuego`,
advisory de `operacion_advisory`, `AlmacenAutomatizacion`, `CarterasFileStore`) en el instante exacto de la
captura que marca cada escenario (`fase`). Ningun escenario pausa ni toca Fase 6 real.
"""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.unit.generaciones.conftest import BACKEND, admin, requiere_pg

pytestmark = requiere_pg


def _capturar(f, destino, *, fase=lambda _: None, intentos=1, espera=0.0, plazo=60.0, alcance="publicacion"):
    from app.infrastructure.generaciones import captura
    return captura.capturar(f["fuente"], destino, f["firma"], fase=fase, intentos=intentos, espera=espera,
                            plazo=plazo, alcance=alcance)


def _rechazo(f, destino, **opciones):
    from app.infrastructure.generaciones import captura
    with pytest.raises(captura.CapturaRechazada) as error:
        _capturar(f, destino, **opciones)
    _sin_generacion(destino)
    return error.value.motivos


def _sin_generacion(destino: Path) -> None:
    hay = [p.name for p in destino.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "alertas"]
    assert hay == [], f"quedo una generacion sellada: {hay}"
    assert not list(destino.glob(".preparando-*")), "quedo una preparacion"
    assert list((destino / "alertas").glob("captura_rechazada-*.json")), "sin alerta captura_rechazada"


def _conexion(f, autocommit=False):
    from app.infrastructure.generaciones import base_logica as bl
    return bl.conectar(f["url"], autocommit=autocommit)


def _en(fase_objetivo, accion):
    hecho = []

    def fase(nombre):
        if nombre == fase_objetivo and not hecho:
            hecho.append(nombre)
            accion()
    return fase


def _conexiones_de(base: str) -> int:
    with admin() as c:
        return c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                         (base,)).fetchone()[0]


# --- C1: una transaccion iniciada ANTES de la instantanea confirma DESPUES ---------------------------------------
def test_c1_transaccion_anterior_que_confirma_despues_se_detecta_por_las_versiones(fuente, tmp_path):
    escritor = _conexion(fuente)
    estado = {}

    def antes_de_la_instantanea():  # t1: ya paso la evidencia de t0; escribe y queda SIN confirmar
        escritor.execute("UPDATE sorteos SET fuente = 'c1' WHERE id = (SELECT id FROM sorteos ORDER BY id LIMIT 1)")

    def despues_de_la_instantanea():  # confirma despues de t2
        escritor.commit()
        estado["confirmada"] = True

    fases = {"t1": antes_de_la_instantanea, "volcado": despues_de_la_instantanea}
    motivos = _rechazo(fuente, tmp_path / "g", fase=lambda n: fases.pop(n, lambda: None)())
    escritor.close()
    assert estado == {"confirmada": True}
    assert motivos[-1]["motivo"] == "base_cambio_durante_la_captura" and "sorteos" in motivos[-1]["detalle"]


def test_c1_transaccion_con_escritura_abierta_en_t0_se_rechaza(fuente, tmp_path):
    escritor = _conexion(fuente)
    escritor.execute("UPDATE juegos SET nombre = nombre WHERE codigo = 'MILOTO'")  # asigna xid; sin confirmar
    try:
        motivos = _rechazo(fuente, tmp_path / "g")
    finally:
        escritor.rollback()
        escritor.close()
    assert motivos[-1]["motivo"] == "escritores_activos_en_t0"
    assert any("transaccion con escritura sin terminar" in e for e in motivos[-1]["detalle"])


# --- C2: un cambio que NO altera recuentos ni maximos de id --------------------------------------------------------
def test_c2_cambio_sin_variar_recuentos_ni_maximos_se_detecta(fuente, tmp_path):
    def contar(c):
        return c.execute("SELECT count(*), max(id::text), max(numero_sorteo) FROM sorteos").fetchone(), \
            c.execute("SELECT count(*), max(id::text) FROM colores").fetchone()

    with _conexion(fuente, autocommit=True) as c:
        antes = contar(c)

    def editar():
        with _conexion(fuente, autocommit=True) as c:
            c.execute("UPDATE sorteos SET fecha = fecha + 0, dia_semana = dia_semana WHERE numero_sorteo = "
                      "(SELECT min(numero_sorteo) FROM sorteos)")  # mismo contenido: solo una version nueva
            c.execute("UPDATE colores SET nombre = nombre || '' WHERE id = (SELECT min(id::text)::uuid FROM colores)")
    motivos = _rechazo(fuente, tmp_path / "g", fase=_en("copia", editar))
    with _conexion(fuente, autocommit=True) as c:
        despues = contar(c)
    assert antes == despues  # recuentos, maximos de id y de sorteo iguales (y aqui hasta el contenido)
    assert motivos[-1]["motivo"] == "base_cambio_durante_la_captura"
    assert set(motivos[-1]["detalle"]) >= {"sorteos", "colores"}


# --- C3: la observacion final es INDEPENDIENTE de la instantanea congelada ------------------------------------------
def test_c3_la_instantanea_congelada_no_ve_el_cambio_y_la_observacion_final_si(fuente):
    import psycopg

    from app.infrastructure.generaciones import base_logica as bl

    congelada = _conexion(fuente)
    congelada.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    congelada.read_only = True
    antes = {n: h.versiones for n, h in bl.huellas(congelada).items()}
    with _conexion(fuente, autocommit=True) as c:
        c.execute("UPDATE sorteos SET fuente = 'c3' WHERE id = (SELECT id FROM sorteos ORDER BY id LIMIT 1)")
    misma = {n: h.versiones for n, h in bl.huellas(congelada).items()}
    congelada.rollback()
    congelada.close()
    with _conexion(fuente) as nueva:
        final = {n: h.versiones for n, h in bl.huellas(nueva).items()}
    assert misma == antes  # una "observacion final" dentro de la misma instantanea no ve nada (F10-CAP-01)
    assert final["sorteos"] != antes["sorteos"]  # la observacion independiente (otra transaccion) si


def test_c3_la_captura_rechaza_un_cambio_confirmado_tras_la_instantanea(fuente, tmp_path):
    def confirmar():
        with _conexion(fuente, autocommit=True) as c:
            c.execute("INSERT INTO sincronizaciones (id, juego_id, conector, iniciado_en, estado) "
                      "SELECT gen_random_uuid(), id, 'c3', now(), 'ok' FROM juegos LIMIT 1")
    motivos = _rechazo(fuente, tmp_path / "g", fase=_en("coherencia", confirmar))
    assert motivos[-1]["motivo"] == "base_cambio_durante_la_captura" and "sincronizaciones" in motivos[-1]["detalle"]


# --- C4: trabajo de un proceso trabajador o de la CLI YA iniciado --------------------------------------------------
def test_c4_trabajador_con_cerrojo_tomado_rechaza_con_espera_acotada(fuente, tmp_path):
    from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego

    cerrojos = CerrojoPorJuego(fuente["almacenes"]["carteras"] / "operacion").adquirir(["BALOTO"], "20261104T000002Z-c4c4c4c6")
    inicio = time.monotonic()
    try:
        motivos = _rechazo(fuente, tmp_path / "g", intentos=3, espera=0.2, plazo=30)
    finally:
        cerrojos.liberar()
    assert [m["motivo"] for m in motivos] == ["escritores_activos_en_t0"] * 3  # tres intentos, ninguno sellado
    assert any("cerrojo de juego tomado" in e for e in motivos[0]["detalle"])
    assert time.monotonic() - inicio < 30  # espera acotada


def test_c4_la_espera_acotada_sella_cuando_el_trabajo_termina(fuente, tmp_path):
    from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego

    cerrojos = CerrojoPorJuego(fuente["almacenes"]["laboratorio"] / "operacion").adquirir(["MILOTO"], "20261104T000001Z-c4c4c4c5")
    esperas = []

    def dormir(segundos):  # el trabajo termina durante la primera espera
        esperas.append(segundos)
        cerrojos.liberar()

    from app.infrastructure.generaciones import captura
    g = captura.capturar(fuente["fuente"], tmp_path / "g", fuente["firma"], intentos=2, espera=1.5, plazo=60,
                         dormir=dormir)
    manifiesto = json.loads((g / "manifiesto.json").read_text())
    assert esperas == [1.5] and manifiesto["captura"]["intento"] == 2


def test_c4_ciclo_de_fase6_con_advisory_de_sesion_rechaza(fuente, tmp_path):
    from app.infrastructure.operacion_advisory import clave_de_juego

    ciclo = _conexion(fuente, autocommit=True)
    juego = ciclo.execute("SELECT id FROM juegos WHERE codigo = 'BALOTO'").fetchone()[0]
    ciclo.execute("SELECT pg_advisory_lock(%s)", (clave_de_juego(juego),))  # lo que hace `proteger_ciclo`
    try:
        motivos = _rechazo(fuente, tmp_path / "g")
    finally:
        ciclo.close()
    assert motivos[-1]["motivo"] == "escritores_activos_en_t0"
    assert any(f"advisory {clave_de_juego(juego)}" in e for e in motivos[-1]["detalle"])


def test_c4_ejecucion_de_la_cli_en_curso_rechaza(fuente, tmp_path):
    from app.infrastructure.storage.operacion_file_store import RegistroEjecucionesArchivo

    RegistroEjecucionesArchivo(fuente["almacenes"]["operacion"]).guardar(
        {"id": "20261104T000000Z-c4c4c4c4", "estado": "en_curso", "juegos": {"BALOTO": {"estado": "en_curso"}}})
    motivos = _rechazo(fuente, tmp_path / "g")
    assert any("ejecucion en_curso" in e for e in motivos[-1]["detalle"])


# --- C5: configuracion mutable durante la captura -------------------------------------------------------------------
@pytest.mark.parametrize("cambio", ["actualizar_configuracion", "guardar_estado", "configuracion_de_carteras"])
def test_c5_configuracion_mutable_durante_la_captura_se_detecta(fuente, tmp_path, cambio):
    from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
    from app.infrastructure.storage.carteras_file_store import CarterasFileStore

    def escribir():
        if cambio == "configuracion_de_carteras":
            store = CarterasFileStore(fuente["almacenes"]["carteras"])
            vigente = store.configuraciones("BALOTO")[0].artefacto
            store.guardar_configuracion("BALOTO", lambda v: _nueva_version(vigente, v))
            return
        almacen = AlmacenAutomatizacion(fuente["almacenes"]["automatizacion"])
        if cambio == "actualizar_configuracion":
            almacen.actualizar_configuracion({"pausada": True})
        else:
            almacen.guardar_estado("BALOTO", {"estado": "comprobado_c5"})
    motivos = _rechazo(fuente, tmp_path / "g", fase=_en("copia", escribir))
    assert motivos[-1]["motivo"] == "archivos_cambiaron_durante_la_captura"


def _nueva_version(vigente: dict, version: int) -> dict:
    """Una version nueva de la configuracion con el MISMO constructor que `CarterasDeModelos.configurar`."""
    from app.application.ml import carteras_artefactos as ca
    return ca.componer(ca.cuerpo_de_configuracion("BALOTO", version, vigente["modelo"]["id"], vigente["perfil"],
                                                  vigente["cantidad"], vigente["diversidad"], vigente["semilla"] + 1),
                       "registro", {"guardada_en": "2026-11-04T00:00:00+00:00", "origen": "prueba_c5",
                                    "nota": "configuracion explicita; versiones anteriores inmutables"})


# --- C6: fallos a mitad (disco, conexion, proceso) ------------------------------------------------------------------
@pytest.mark.parametrize("fase_fallida", ["t0", "t1", "instantanea", "volcado", "copia", "coherencia", "t4"])
def test_c6_fallo_intermedio_sin_generacion_ni_conexiones_ni_cerrojo(fuente, tmp_path, fase_fallida):
    def fallar(nombre):
        if nombre == fase_fallida:
            raise OSError(28, "No space left on device (simulado)")
    motivos = _rechazo(fuente, tmp_path / "g", fase=fallar)
    assert motivos[-1]["motivo"] == "fallo_intermedio" and "No space left" in motivos[-1]["detalle"]
    assert _conexiones_de(fuente["base"]) == 0  # la instantanea exportada y las conexiones terminaron
    g = _capturar(fuente, tmp_path / "g")  # el cerrojo propio quedo libre: la siguiente captura sella
    assert (g / "manifiesto.json").is_file()


def test_c6_conexion_cortada_a_mitad(fuente, tmp_path):
    def cortar():
        with admin() as c:
            c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND "
                      "pid <> pg_backend_pid()", (fuente["base"],))
    motivos = _rechazo(fuente, tmp_path / "g", fase=_en("volcado", cortar))
    assert motivos[-1]["motivo"] == "fallo_intermedio"


def test_c6_proceso_terminado_con_sigkill(fuente, tmp_path):
    marca = tmp_path / "en-la-copia"
    guion = f"""
import sys, time
from pathlib import Path
sys.path.insert(0, {str(BACKEND)!r})
from app.infrastructure.generaciones import captura
fuente = captura.Fuente({fuente['url']!r}, {{k: Path(v) for k, v in {dict((k, str(v)) for k, v in fuente['almacenes'].items())!r}.items()}})
def fase(n):
    if n == "copia":
        Path({str(marca)!r}).write_text("x"); time.sleep(120)
captura.capturar(fuente, Path({str(tmp_path / 'g')!r}), Path({str(fuente['firma'])!r}), intentos=1, fase=fase)
"""
    proceso = subprocess.Popen([sys.executable, "-B", "-c", guion], cwd=BACKEND)
    for _ in range(600):
        if marca.exists() or proceso.poll() is not None:
            break
        time.sleep(0.1)
    assert marca.exists(), "el proceso no llego a la copia"
    proceso.send_signal(signal.SIGKILL)
    proceso.wait()
    destino = tmp_path / "g"
    assert [p.name for p in destino.iterdir() if not p.name.startswith(".")] == []  # nada sellado
    for _ in range(100):  # PostgreSQL cierra las sesiones del proceso muerto (y su instantanea exportada)
        if _conexiones_de(fuente["base"]) == 0:
            break
        time.sleep(0.1)
    assert _conexiones_de(fuente["base"]) == 0
    g = _capturar(fuente, destino)  # el cerrojo del sistema se libero y la preparacion huerfana se descarta
    assert (g / "manifiesto.json").is_file() and not list(destino.glob(".preparando-*"))


# --- C7: cartera integra con objetivo = corte + 1 y su explicacion --------------------------------------------------
def test_c7_cartera_con_objetivo_corte_mas_uno_y_su_explicacion_se_publican(fuente, tmp_path):
    g = _capturar(fuente, tmp_path / "g")
    coherencia = json.loads((g / "coherencia.json").read_text())
    with _conexion(fuente, autocommit=True) as c:
        ultimo = c.execute("SELECT max(numero_sorteo) FROM sorteos s JOIN juegos j ON j.id = s.juego_id "
                           "WHERE j.codigo = 'BALOTO'").fetchone()[0]
    pendientes = [a for a in coherencia["artefactos"] if a["juego"] == "BALOTO" and a["objetivo"] == ultimo + 1]
    familias = {a["familia"] for a in pendientes}
    assert {"cartera", "explicacion"} <= familias
    cartera = next(a for a in pendientes if a["familia"] == "cartera")
    assert cartera["corte"] == ultimo and cartera["historico"] == "coincide"
    origen = next(fuente["almacenes"]["carteras"].glob(f"carteras/BALOTO/*/{ultimo + 1}-{cartera['clave']}.json"))
    copia = g / "archivos" / "carteras" / origen.relative_to(fuente["almacenes"]["carteras"])
    assert copia.read_bytes() == origen.read_bytes()  # publicada byte a byte
    explicacion = next(a for a in pendientes if a["familia"] == "explicacion")
    assert list((g / "archivos" / "predicciones" / "explicaciones" / "BALOTO").glob(f"*-{explicacion['clave']}.json"))


# --- C8 y C9: historico de entrada ausente -> rechazo entero, nunca un filtrado --------------------------------------
def _borrar_sorteo(c, juego: str, numero: int) -> None:
    sid = c.execute("SELECT s.id FROM sorteos s JOIN juegos j ON j.id = s.juego_id WHERE j.codigo = %s "
                    "AND numero_sorteo = %s", (juego, numero)).fetchone()[0]
    for tabla in ("sorteo_numeros", "sorteo_superbalota", "sorteo_color_numero"):
        c.execute(f"DELETE FROM {tabla} WHERE sorteo_id = %s", (sid,))
    c.execute("DELETE FROM sorteos WHERE id = %s", (sid,))


def _corte_de_una_cartera(fuente, juego: str) -> int:
    from app.infrastructure.storage.carteras_file_store import CarterasFileStore, Guardado

    store = CarterasFileStore(fuente["almacenes"]["carteras"])
    return next(e.artefacto["datos"]["corte"] for linea in store.lineas(juego) for e in store.carteras(juego, linea)
                if isinstance(e, Guardado))


def test_c7_borrar_solo_el_sorteo_objetivo_no_rechaza_el_objetivo_no_se_limita(fuente, tmp_path):
    """El sorteo OBJETIVO de las emisiones de MILOTO (corte + 1) no es historico de entrada: sin el, la captura
    se sella y las emisiones quedan pendientes; nada se filtra."""
    corte = _corte_de_una_cartera(fuente, "MILOTO")
    with _conexion(fuente, autocommit=True) as c:
        ultimo = c.execute("SELECT max(numero_sorteo) FROM sorteos s JOIN juegos j ON j.id = s.juego_id "
                           "WHERE j.codigo = 'MILOTO'").fetchone()[0]
        assert ultimo == corte + 1  # el preparador anade el objetivo despues de emitir
        _borrar_sorteo(c, "MILOTO", ultimo)
    g = _capturar(fuente, tmp_path / "g")
    coherencia = json.loads((g / "coherencia.json").read_text())
    milo = [a for a in coherencia["artefactos"] if a["juego"] == "MILOTO" and a.get("objetivo") == corte + 1]
    assert milo and coherencia["rechazos"] == []  # emisiones con objetivo ya ausente: publicadas


def test_c8_c9_historico_de_entrada_ausente_rechaza_entera_sin_filtrar(fuente, tmp_path):
    from app.infrastructure.generaciones import archivos as ar

    corte = _corte_de_una_cartera(fuente, "MILOTO")
    with _conexion(fuente, autocommit=True) as c:  # se borra el sorteo `corte` que declaran las carteras
        _borrar_sorteo(c, "MILOTO", corte)
    foto = ar.fotografiar(fuente["almacenes"])
    motivos = _rechazo(fuente, tmp_path / "g")
    rechazo = motivos[-1]
    assert rechazo["motivo"] == "coherencia_cruzada"
    ausentes = [d for d in rechazo["detalle"] if d["motivo"] == "historico_de_entrada_ausente"]
    assert ausentes and all(d["juego"] == "MILOTO" and d["corte"] == corte for d in ausentes)
    assert {d["familia"] for d in ausentes} >= {"cartera", "explicacion"}
    assert ar.fotografiar(fuente["almacenes"]) == foto  # C9: no se borro ni se filtro nada en la fuente
    assert len(motivos) == 1  # no reintentable: el mismo estado daria el mismo rechazo


def test_c8_menos_sorteos_que_los_declarados_hasta_el_corte_rechaza(fuente, tmp_path):
    """El corte sigue en la base pero falta un sorteo intermedio que el artefacto declaro haber usado."""
    corte = _corte_de_una_cartera(fuente, "COLORLOTO")
    with _conexion(fuente, autocommit=True) as c:
        intermedio = c.execute("SELECT min(numero_sorteo) FROM sorteos s JOIN juegos j ON j.id = s.juego_id "
                               "WHERE j.codigo = 'COLORLOTO'").fetchone()[0]
        _borrar_sorteo(c, "COLORLOTO", intermedio)
    motivos = _rechazo(fuente, tmp_path / "g")
    ausentes = [d for d in motivos[-1]["detalle"] if d["motivo"] == "historico_de_entrada_ausente"]
    assert ausentes and all(d["juego"] == "COLORLOTO" for d in ausentes)
    assert any(d["sorteos_en_la_captura_hasta_el_corte"] < (d["sorteos_declarados"] or 0) for d in ausentes)
    assert corte >= intermedio


# --- C10: control positivo sin escritores -> generacion sellada que supera DAT-04 ----------------------------------
def test_c10_control_positivo_sellado_verificado_e_importado(fuente, tmp_path):
    from app.infrastructure.generaciones import importacion as im
    from app.infrastructure.generaciones.verificacion import verificar
    from tests.unit.generaciones.conftest import borrar_base, url_de

    g = _capturar(fuente, tmp_path / "g")
    manifiesto = verificar(g, fuente["publica"])
    assert manifiesto["coherencia"]["rechazos"] == 0 and manifiesto["coherencia"]["ilegibles"] == 0
    import secrets

    from psycopg import sql
    from sqlalchemy.engine import make_url

    clave = secrets.token_hex(16)  # generada en cada ejecucion: ningun literal de credencial en el repositorio
    with admin() as c:
        if c.execute("SELECT 1 FROM pg_roles WHERE rolname = 'e104_lector_prueba'").fetchone() is None:
            c.execute("CREATE ROLE e104_lector_prueba LOGIN NOSUPERUSER")
            c.execute("ALTER ROLE e104_lector_prueba SET default_transaction_read_only = on")
        c.execute(sql.SQL("ALTER ROLE e104_lector_prueba PASSWORD {}").format(sql.Literal(clave)))
    lector = make_url(url_de("postgres")).set(username="e104_lector_prueba", password=clave)
    destino = im.Destino(tmp_path / "srv", url_de("postgres"), lector.render_as_string(hide_password=False),
                         "e104_lector_prueba")
    try:
        informe = im.importar(g, fuente["publica"], destino)
        assert informe["resultado"] == "aceptada" and informe["consultas"]["fallos"] == []
        from app.infrastructure.generaciones import consultas
        assert consultas.requisitos_de_demostracion(informe["consultas"]) == []  # la plantilla no esta vacia
    finally:
        borrar_base(im.nombre_base(manifiesto["id"], True))
        borrar_base(im.nombre_base(manifiesto["id"], False))
