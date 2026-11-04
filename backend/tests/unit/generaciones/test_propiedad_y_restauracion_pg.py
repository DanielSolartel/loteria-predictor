"""E10.4 v2: regresiones de E104-IMP-01, E104-RES-05 y E104-PLA-04 sobre PostgreSQL REAL aislado.

Usan las interfaces de la v1 (`importar`, `Destino`, `activar`, `respaldar`, `restaurar`, `capturar`) para que
FALLEN sobre la v1 por el comportamiento auditado: borrar por su nombre una base ajena o aceptada en otra raiz,
dejar una base restaurada tras un fallo de la copia final, bloquear la repeticion de una restauracion fallida o
seguir bloqueado mas alla del plazo. Las bases ajenas se crean con otro rol duena; todas son `prueba_e104_*`,
`prep_*`, `pub_*` o `rest_*` de esta prueba y se borran al terminar.
"""
from __future__ import annotations

import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.unit.generaciones.conftest import BACKEND, admin, requiere_pg, url_de

pytestmark = requiere_pg


def _bases(patron: str) -> list[str]:
    with admin() as c:
        return [f[0] for f in c.execute("SELECT datname FROM pg_database WHERE datname LIKE %s ORDER BY 1",
                                        (patron,)).fetchall()]


def _duena(nombre: str) -> str | None:
    with admin() as c:
        fila = c.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s", (nombre,)).fetchone()
    return fila[0] if fila else None


def _borrar(*patrones: str) -> None:
    with admin() as c:
        for patron in patrones:
            for (nombre,) in c.execute("SELECT datname FROM pg_database WHERE datname LIKE %s", (patron,)).fetchall():
                c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (nombre,))
                c.execute(f'DROP DATABASE "{nombre}"')


def _rol(nombre: str, *opciones: str) -> str:
    from psycopg import sql

    clave = secrets.token_hex(16)  # generada en cada ejecucion
    with admin() as c:
        if c.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (nombre,)).fetchone() is None:
            c.execute(f"CREATE ROLE {nombre} LOGIN NOSUPERUSER {' '.join(opciones)}")
        c.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(nombre), sql.Literal(clave)))
    return clave


def _url_rol(nombre: str, clave: str) -> str:
    from sqlalchemy.engine import make_url
    return make_url(url_de("postgres")).set(username=nombre, password=clave).render_as_string(hide_password=False)


@pytest.fixture
def lector():
    clave = _rol("e104_lector_prueba")
    with admin() as c:
        c.execute("ALTER ROLE e104_lector_prueba SET default_transaction_read_only = on")
    return _url_rol("e104_lector_prueba", clave)


def _destino(raiz: Path, lector: str):
    from app.infrastructure.generaciones import importacion as im
    return im.Destino(raiz, url_de("postgres"), lector, "e104_lector_prueba")


def _capturar(f, destino: Path, **opciones):
    from app.infrastructure.generaciones import captura
    return captura.capturar(f["fuente"], destino, f["firma"], intentos=1, espera=0.0, **opciones)


@pytest.fixture
def g1(fuente, tmp_path):
    from app.infrastructure.generaciones.verificacion import verificar

    paquete = _capturar(fuente, tmp_path / "capturas")
    gid = verificar(paquete, fuente["publica"])["id"]
    yield paquete, gid
    _borrar(f"prep_{gid}%", f"pub_{gid}", f"rest_{gid}")


def _rechazo(paquete, publica, destino, **opciones):
    from app.infrastructure.generaciones import importacion as im
    try:
        im.importar(paquete, publica, destino, **opciones)
    except im.ImportacionRechazada as error:
        return error
    return None


# --- E104-IMP-01 ---------------------------------------------------------------------------------------------
def test_imp01_base_aceptada_y_activa_en_otra_raiz_no_se_borra(fuente, g1, tmp_path, lector):
    from app.infrastructure.generaciones import importacion as im

    paquete, gid = g1
    raiz_a = tmp_path / "srv-A"
    assert im.importar(paquete, fuente["publica"], _destino(raiz_a, lector))["resultado"] == "aceptada"
    im.activar(raiz_a, gid, fuente["publica"], url_de("postgres"))
    activa = (raiz_a / "activa.json").read_bytes()

    def cortar(fase):
        if fase == "base_creada":
            raise OSError("fallo sintetico en la otra raiz")
    rechazo = _rechazo(paquete, fuente["publica"], _destino(tmp_path / "srv-B", lector), fase=cortar)
    assert rechazo is not None
    assert _bases(f"pub_{gid}") == [f"pub_{gid}"]  # la base aceptada y ACTIVA de A sigue alli
    with admin() as c:
        im.verificar_publicada(raiz_a / "generaciones" / gid, fuente["publica"], c)
    assert (raiz_a / "activa.json").read_bytes() == activa
    assert rechazo.paso == "restos" and "generacion_aceptada_en_otra_raiz" in rechazo.motivo


def test_imp01_bases_ajenas_con_nombre_de_preparacion_no_se_borran(fuente, g1, tmp_path, lector):
    """Bases de otro duenno con los nombres de preparacion (el de la v1 y uno con el prefijo de la v2)."""
    from app.infrastructure.generaciones import importacion as im

    paquete, gid = g1
    _rol("e104_ajeno_prueba", "CREATEDB")
    ajenas = [f"prep_{gid}", f"prep_{gid}_{'0' * 16}"]
    with admin() as c:
        for nombre in ajenas:
            c.execute(f'CREATE DATABASE "{nombre}" OWNER e104_ajeno_prueba')
    try:
        informe = im.importar(paquete, fuente["publica"], _destino(tmp_path / "srv", lector))
        assert [n for n in ajenas if _duena(n) == "e104_ajeno_prueba"] == ajenas  # intactas
        assert informe["resultado"] == "aceptada"
        assert informe.get("bases_ajenas_intactas") == [ajenas[1]]
    finally:
        _borrar(*ajenas)


def test_imp01_importaciones_simultaneas_desde_raices_distintas_se_excluyen(fuente, g1, tmp_path, lector):
    """Mientras A prepara la base, B (otra raiz del mismo servidor, mismo id) intenta importar."""
    from app.infrastructure.generaciones import importacion as im

    paquete, gid = g1
    segunda = {}

    def en_a(fase):
        if fase == "esquema" and not segunda:
            segunda["rechazo"] = _rechazo(paquete, fuente["publica"], _destino(tmp_path / "srv-B", lector))
            segunda["bases"] = _bases(f"prep_{gid}%")
    informe = im.importar(paquete, fuente["publica"], _destino(tmp_path / "srv-A", lector), fase=en_a)
    assert informe["resultado"] == "aceptada"  # A no perdio su preparacion
    assert segunda["rechazo"] is not None and segunda["rechazo"].paso == "exclusion"
    assert len(segunda["bases"]) == 1  # B no borro ni creo nada mientras A preparaba
    assert not (tmp_path / "srv-B" / "generaciones" / gid).exists()


def test_imp01_carpeta_de_preparacion_ajena_no_se_borra(fuente, g1, tmp_path, lector):
    paquete, gid = g1
    raiz = tmp_path / "srv"
    ajena = raiz / "preparacion" / gid
    ajena.mkdir(parents=True)
    (ajena / "de-otro.txt").write_text("no es del importador")
    rechazo = _rechazo(paquete, fuente["publica"], _destino(raiz, lector))
    assert (ajena / "de-otro.txt").read_text() == "no es del importador"
    assert rechazo is not None and rechazo.paso == "restos" and "sin_prueba_de_propiedad" in rechazo.motivo
    assert _bases(f"prep_{gid}%") == [] and _bases(f"pub_{gid}") == []


def test_imp01_restos_propios_tras_sigkill_se_recuperan_y_la_activa_se_conserva(fuente, g1, tmp_path, lector):
    from app.infrastructure.generaciones import importacion as im

    paquete, gid = g1
    raiz = tmp_path / "srv"
    im.importar(paquete, fuente["publica"], _destino(raiz, lector))
    im.activar(raiz, gid, fuente["publica"], url_de("postgres"))
    activa = (raiz / "activa.json").read_bytes()
    g2 = _capturar(fuente, tmp_path / "capturas-2")
    try:
        urls = tmp_path / "urls"
        urls.mkdir(mode=0o700)
        (urls / "admin").write_text(url_de("postgres"))
        (urls / "lector").write_text(lector)
        for u in urls.iterdir():
            u.chmod(0o600)
        orden = [sys.executable, "-B", "-m", "scripts.generaciones", "importar", "--paquete", str(g2),
                 "--clave-publica", str(fuente["publica"]), "--raiz", str(raiz), "--url-admin-archivo",
                 str(urls / "admin"), "--url-lector-archivo", str(urls / "lector"), "--rol-lector", "e104_lector_prueba"]
        proceso = subprocess.Popen(orden, cwd=BACKEND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(1200):
            if (raiz / "preparacion" / g2.name / "archivos").exists() or proceso.poll() is not None:
                break
            time.sleep(0.05)
        proceso.send_signal(signal.SIGKILL)
        proceso.wait()
        assert _bases(f"prep_{g2.name}%"), "el corte debia dejar restos propios"
        informe = im.importar(g2, fuente["publica"], _destino(raiz, lector))
        assert informe["resultado"] == "aceptada"
        assert informe.get("restos_recuperados")
        assert _bases(f"prep_{g2.name}%") == [] and not (raiz / "preparacion" / g2.name).exists()
        assert (raiz / "activa.json").read_bytes() == activa
        with admin() as c:
            im.verificar_publicada(raiz / "generaciones" / gid, fuente["publica"], c)
    finally:
        _borrar(f"prep_{g2.name}%", f"pub_{g2.name}")


# --- E104-RES-05 ---------------------------------------------------------------------------------------------
@pytest.fixture
def respaldo(fuente, tmp_path):
    from app.infrastructure.generaciones import respaldo as rp

    paquete = _capturar(fuente, tmp_path / "capturas-respaldo", alcance="respaldo")
    rp.generar_claves(tmp_path / "r.pem", tmp_path / "r.pub")
    catalogo = rp.respaldar(paquete, tmp_path / "r.pub", tmp_path / "respaldos")
    base = f"rest_prueba_{secrets.token_hex(6)}"
    yield {"archivo": tmp_path / "respaldos" / catalogo["archivo"], "privada": tmp_path / "r.pem", "base": base,
           "publica": fuente["publica"]}
    _borrar(base)


def _restaurar(r, destino, **opciones):
    from app.infrastructure.generaciones import respaldo as rp
    return rp.restaurar(r["archivo"], r["privada"], r["publica"], destino, url_de("postgres"), r["base"], **opciones)


def test_res05_fallo_de_la_copia_final_no_deja_base_ni_carpeta_utilizable(respaldo, tmp_path):
    from app.infrastructure.generaciones import respaldo as rp

    destino = tmp_path / "restauracion"
    with patch.object(rp.ar, "copiar_verificado", side_effect=OSError("disco sintetico sin espacio")):
        with pytest.raises(Exception):  # noqa: B017 - lo que importa es lo que queda
            _restaurar(respaldo, destino)
    assert _bases(respaldo["base"]) == []
    assert not destino.exists()


def test_res05_repetir_tras_un_fallo_de_la_copia_final_recupera_y_restaura(respaldo, tmp_path):
    from app.infrastructure.generaciones import respaldo as rp

    destino = tmp_path / "restauracion"
    original = rp.ar.copiar_verificado
    llamadas = []

    def falla_una_vez(*a, **k):
        if not llamadas:
            llamadas.append(1)
            raise OSError("disco sintetico sin espacio")
        return original(*a, **k)

    with patch.object(rp.ar, "copiar_verificado", side_effect=falla_una_vez):
        with pytest.raises(Exception):  # noqa: B017
            _restaurar(respaldo, destino)
    r = _restaurar(respaldo, destino)
    assert r.base == respaldo["base"] and _bases(respaldo["base"]) == [respaldo["base"]]
    assert rp.comprobar_restauracion(destino)["estado"] == "completa"


def test_res05_fallo_de_la_limpieza_queda_fallida_con_diagnostico_y_se_recupera(respaldo, tmp_path):
    from app.infrastructure.generaciones import respaldo as rp

    destino = tmp_path / "restauracion"
    with patch.object(rp.ar, "copiar_verificado", side_effect=OSError("disco sintetico")), \
            patch.object(rp.ar, "borrar_propia", side_effect=OSError("limpieza sintetica")):
        with pytest.raises(rp.RestauracionFallida) as error:
            _restaurar(respaldo, destino)
    assert error.value.diagnostico["base_borrada"] is True and error.value.diagnostico["carpeta_borrada"] is False
    assert any("carpeta" in p for p in error.value.diagnostico["pendiente"])
    assert rp.estado_de_restauracion(destino)["estado"] == "fallida"
    with pytest.raises(Exception, match="fallida"):
        rp.comprobar_restauracion(destino)  # nunca se presenta como utilizable
    assert _bases(respaldo["base"]) == []
    assert _restaurar(respaldo, destino).base == respaldo["base"]  # repetir la recupera
    assert rp.comprobar_restauracion(destino)["estado"] == "completa"


@pytest.mark.parametrize("fase", ["base_creada", "filas_cargadas"])
def test_res05_fallo_en_la_base_limpia_solo_lo_propio(respaldo, tmp_path, fase):
    from app.infrastructure.generaciones import respaldo as rp

    def cortar(nombre):
        if nombre == fase:
            raise OSError(f"fallo sintetico en {fase}")
    with pytest.raises(rp.RestauracionFallida):
        _restaurar(respaldo, tmp_path / "restauracion", fase=cortar)
    assert _bases(respaldo["base"]) == [] and not (tmp_path / "restauracion").exists()


def test_res05_destino_ajeno_y_base_ajena_no_se_tocan(respaldo, tmp_path):
    from app.infrastructure.generaciones import respaldo as rp

    ajeno = tmp_path / "ajeno"
    ajeno.mkdir()
    (ajeno / "dato.txt").write_text("de otro")
    with pytest.raises(rp.GeneracionNoValida, match="no es una restauracion propia"):
        _restaurar(respaldo, ajeno)
    assert (ajeno / "dato.txt").read_text() == "de otro"
    _rol("e104_ajeno_prueba", "CREATEDB")
    with admin() as c:
        c.execute(f'CREATE DATABASE "{respaldo["base"]}" OWNER e104_ajeno_prueba')
    with pytest.raises(rp.GeneracionNoValida, match="ya existe"):
        _restaurar(respaldo, tmp_path / "nuevo")
    assert _duena(respaldo["base"]) == "e104_ajeno_prueba" and not (tmp_path / "nuevo").exists()


def test_res05_comparte_la_exclusion_del_servidor_con_el_importador(respaldo, tmp_path):
    from app.infrastructure.generaciones import base_logica as bl
    from app.infrastructure.generaciones import importacion as im
    from app.infrastructure.generaciones import respaldo as rp

    with bl.conectar(url_de("postgres"), autocommit=True) as otro, im.Exclusion(otro):
        with pytest.raises(im.ImportacionRechazada) as error:
            _restaurar(respaldo, tmp_path / "restauracion")
    assert error.value.paso == "exclusion" and not (tmp_path / "restauracion").exists()
    assert _bases(respaldo["base"]) == []
    assert rp.ESTADO == "RESTAURACION.json"


# --- E104-PLA-04 ---------------------------------------------------------------------------------------------
def _conexiones_de(base: str) -> int:
    with admin() as c:
        return c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                         (base,)).fetchone()[0]


def test_pla04_consulta_bloqueada_por_un_cerrojo_termina_dentro_del_plazo(fuente, tmp_path):
    """Tras la instantanea, otra sesion (sin escribir) toma un cerrojo exclusivo sobre `sorteos` y lo retiene
    25 s: el volcado queda bloqueado en esa consulta. Con un plazo de 3 s la captura debe cortarse sola."""
    from app.infrastructure.generaciones import base_logica as bl
    from app.infrastructure.generaciones import captura

    tomado, soltar = threading.Event(), threading.Event()

    def retener():
        with bl.conectar(fuente["url"]) as c:
            c.execute("SET lock_timeout = '25s'")  # acota la prueba si la captura no corta sola (v1: interbloqueo)
            try:
                c.execute("LOCK TABLE sorteos IN ACCESS EXCLUSIVE MODE")
            except Exception:  # noqa: BLE001 - no obtuvo el cerrojo en 25 s
                c.rollback()
                return
            tomado.set()
            soltar.wait(25.0)
            c.rollback()

    hilo = threading.Thread(target=retener, daemon=True)

    def fase(nombre):
        if nombre == "instantanea" and not hilo.is_alive():
            hilo.start()
            tomado.wait(10.0)

    inicio = time.monotonic()
    try:
        with pytest.raises(captura.CapturaRechazada) as error:
            _capturar(fuente, tmp_path / "c", plazo=3.0, fase=fase)
        duracion = time.monotonic() - inicio
    finally:
        soltar.set()
        hilo.join(30.0)
    assert duracion < 12, duracion
    assert tomado.is_set()
    assert error.value.motivos[-1]["motivo"] == "plazo_total_agotado", error.value.motivos
    time.sleep(0.5)
    assert _conexiones_de(fuente["base"]) == 0  # nada quedo abierto
    assert not list((tmp_path / "c").glob(".preparando-*"))


def test_pla04_copia_lenta_se_corta_al_vencer_y_no_se_sella(fuente, tmp_path):
    from app.infrastructure.generaciones import captura

    original = captura.ar.copiar_verificado

    def lenta(*a, **k):
        time.sleep(0.3)
        return original(*a, **k)

    inicio = time.monotonic()
    with patch.object(captura.ar, "copiar_verificado", side_effect=lenta):
        with pytest.raises(captura.CapturaRechazada) as error:
            _capturar(fuente, tmp_path / "c", plazo=4.0)
    duracion = time.monotonic() - inicio
    assert error.value.motivos[-1]["motivo"] == "plazo_total_agotado"
    assert duracion < 10, duracion
    assert not [p for p in (tmp_path / "c").iterdir() if p.is_dir() and not p.name.startswith(".")
                and p.name != "alertas"]
    time.sleep(0.5)
    assert _conexiones_de(fuente["base"]) == 0
