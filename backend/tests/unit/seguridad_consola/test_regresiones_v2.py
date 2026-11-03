"""E10.1 v2: regresiones NUEVAS de los hallazgos de la auditoría de v1.

E101-SEC-01 permisos (contrato de la política Windows con descriptores sintéticos y POSIX real), E101-SEC-02
admisión y presesión de un solo uso (hilos y procesos, flujo real), E101-ROB-01 entradas HTTP malformadas,
E101-OBS-01 retención por ambas vías de auditoría y E101-VAL-01 ayudante del procedimiento nativo.
Linux NO acredita ACL reales de Windows: eso queda en `test_permisos_windows_nativo.py` y el protocolo.
"""
from __future__ import annotations

import collections
import concurrent.futures
import json
import multiprocessing
import os
import sqlite3
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seguridad_consola import almacen as al
from app.seguridad_consola import credenciales as cr
from app.seguridad_consola import permisos as pe
from app.seguridad_consola.consola import COOKIE_PRESESION, COOKIE_SESION, host_local_valido
from tests import consola_sesion as cs
from tests import ensayo_e101_buscar_secreto as buscar

USUARIO_SID = "S-1-5-21-1111111111-2222222222-3333333333-1001"
OTRO_SID = "S-1-5-21-1111111111-2222222222-3333333333-1002"
TODOS, ADMINISTRADORES, USUARIOS, AUTENTICADOS, CREADOR = "S-1-1-0", "S-1-5-32-544", "S-1-5-32-545", "S-1-5-11", "S-1-3-0"
FA = 0x1F01FF


@pytest.fixture
def restaurar_app():
    previo, sustituciones = getattr(app.state, "almacen_seguridad", None), dict(app.dependency_overrides)
    yield
    app.state.almacen_seguridad = previo
    app.dependency_overrides.clear()
    app.dependency_overrides.update(sustituciones)


def _ace(sid, tipo=pe.ACCESS_ALLOWED_ACE_TYPE, banderas=0, mascara=FA):
    return pe.Ace(tipo, banderas, mascara, sid)


def _desc(*aces, propietario=USUARIO_SID, dacl=True):
    return pe.DescriptorWindows(propietario, dacl, tuple(aces))


# =============================================================================== E101-SEC-01 · política
@pytest.mark.parametrize("descriptor,motivo", [
    (_desc(_ace(USUARIO_SID)), None),
    (_desc(_ace(USUARIO_SID), _ace(pe.SID_SISTEMA)), None),
    (_desc(_ace(TODOS, tipo=pe.ACCESS_DENIED_ACE_TYPE), _ace(USUARIO_SID)), None),
    (_desc(_ace(USUARIO_SID), _ace(TODOS, mascara=0x120089)), "principal_no_admitido"),
    (_desc(_ace(USUARIO_SID), _ace(ADMINISTRADORES)), "principal_no_admitido"),
    (_desc(_ace(USUARIO_SID), _ace(USUARIOS)), "principal_no_admitido"),
    (_desc(_ace(USUARIO_SID), _ace(AUTENTICADOS)), "principal_no_admitido"),
    (_desc(_ace(USUARIO_SID), _ace(CREADOR, banderas=0x0B)), "principal_no_admitido"),
    (_desc(_ace(USUARIO_SID), _ace(TODOS, banderas=pe.INHERIT_ONLY_ACE)), "principal_no_admitido"),
    (_desc(_ace(USUARIO_SID), _ace(OTRO_SID)), "principal_no_admitido"),
    (_desc(_ace(USUARIO_SID), propietario=ADMINISTRADORES), "propietario_no_admitido"),
    (_desc(_ace(USUARIO_SID), propietario=OTRO_SID), "propietario_no_admitido"),
    (_desc(_ace(USUARIO_SID), propietario=None), "propietario_no_admitido"),
    (_desc(dacl=False), "dacl_nula"),
    (_desc(_ace(USUARIO_SID), pe.Ace(0x5, 0, FA, None)), "ace_no_interpretable"),
    (_desc(_ace(None)), "ace_no_interpretable"),
    (_desc(_ace("no-es-un-sid")), "ace_no_interpretable"),
    (_desc(), "sin_acceso_del_propietario"),
    (_desc(_ace(USUARIO_SID, banderas=pe.INHERIT_ONLY_ACE)), "sin_acceso_del_propietario"),
    (_desc(_ace(USUARIO_SID, mascara=0)), "sin_acceso_del_propietario"),
])
def test_politica_windows_de_principales(descriptor, motivo):
    assert pe.evaluar_descriptor(descriptor, USUARIO_SID) == motivo


def test_politica_windows_sin_usuario_determinado_cierra():
    assert pe.evaluar_descriptor(_desc(_ace(USUARIO_SID)), None) == "usuario_no_determinado"
    assert pe.evaluar_descriptor(_desc(_ace(USUARIO_SID)), "x") == "usuario_no_determinado"


class WindowsSimulado:
    """Sustituye SOLO la lectura/escritura nativa de descriptores; la política y el almacén son los reales."""

    def __init__(self, monkeypatch):
        self.descriptores: dict[str, pe.DescriptorWindows | Exception] = {}
        self.aplicados: list[str] = []
        self.por_defecto = _desc(_ace(USUARIO_SID), _ace(ADMINISTRADORES), _ace(USUARIOS))  # herencia típica
        monkeypatch.setattr(pe, "es_windows", lambda: True)
        monkeypatch.setattr(pe, "sid_actual", lambda: USUARIO_SID)
        monkeypatch.setattr(pe, "leer_descriptor", self.leer)
        monkeypatch.setattr(pe, "aplicar_descriptor", self.aplicar)

    def leer(self, ruta):
        valor = self.descriptores.get(str(ruta), self.por_defecto)
        if isinstance(valor, Exception):
            raise valor
        return valor

    def aplicar(self, ruta, usuario, *, directorio):
        self.aplicados.append(str(ruta))
        self.descriptores[str(ruta)] = _desc(_ace(usuario, banderas=0x03 if directorio else 0))

    def fijar(self, ruta, descriptor):
        self.descriptores[str(ruta)] = descriptor


def _crear_windows(sim, carpeta):
    archivo = carpeta / "seguridad.sqlite3"
    s = al.AlmacenSeguridad.crear(archivo, parametros=cs.PARAMETROS_PRUEBA, minimos=cs.PARAMETROS_PRUEBA)
    s.crear_cuenta("admin", cs.CONTRASENA_PRUEBA, "administrador")
    return s, archivo


def test_windows_simulado_crear_fija_y_verifica_archivo_y_directorio_nuevos(monkeypatch, tmp_path):
    sim = WindowsSimulado(monkeypatch)
    s, archivo = _crear_windows(sim, tmp_path / "nuevo")
    assert sim.aplicados == [str(archivo.parent), str(archivo)]
    s.comprobar()


def test_windows_simulado_apertura_rechaza_dacl_amplia_propietario_y_cambio_posterior(monkeypatch, tmp_path):
    sim = WindowsSimulado(monkeypatch)
    s, archivo = _crear_windows(sim, tmp_path / "nuevo")
    s.comprobar()
    for ruta in (archivo, archivo.parent):  # cambio posterior en el archivo o en el directorio
        bueno = sim.leer(ruta)
        sim.fijar(ruta, _desc(_ace(USUARIO_SID), _ace(TODOS, mascara=0x120089)))
        with pytest.raises(al.ConsolaNoDisponible) as e:
            al.AlmacenSeguridad(archivo).comprobar()
        assert e.value.motivo == "permisos"
        sim.fijar(ruta, _desc(_ace(USUARIO_SID), propietario=ADMINISTRADORES))
        with pytest.raises(al.ConsolaNoDisponible) as e:
            s.comprobar()
        assert e.value.motivo == "permisos"
        sim.fijar(ruta, bueno)
        s.comprobar()


@pytest.mark.parametrize("fallo", [OSError(5, "acceso denegado"), ValueError("sid_no_valido"),
                                   _desc(_ace(USUARIO_SID), pe.Ace(0x5, 0, FA, None))])
def test_windows_simulado_lectura_fallida_o_no_interpretable_cierra(monkeypatch, tmp_path, fallo):
    sim = WindowsSimulado(monkeypatch)
    s, archivo = _crear_windows(sim, tmp_path / "nuevo")
    sim.fijar(archivo, fallo)
    with pytest.raises(al.ConsolaNoDisponible) as e:
        s.comprobar()
    assert e.value.motivo == "permisos_no_verificables"


def test_windows_simulado_usuario_no_determinable_cierra(monkeypatch, tmp_path):
    sim = WindowsSimulado(monkeypatch)
    s, _ = _crear_windows(sim, tmp_path / "nuevo")
    monkeypatch.setattr(pe, "sid_actual", lambda: (_ for _ in ()).throw(OSError(1, "token")))
    with pytest.raises(al.ConsolaNoDisponible) as e:
        s.comprobar()
    assert e.value.motivo == "permisos_no_verificables"


def test_windows_simulado_directorio_preexistente_no_se_modifica(monkeypatch, tmp_path):
    sim = WindowsSimulado(monkeypatch)
    existente = tmp_path / "existente"
    existente.mkdir()
    with pytest.raises(al.OperacionRechazada, match="no se modifica"):
        al.AlmacenSeguridad.crear(existente / "seguridad.sqlite3", parametros=cs.PARAMETROS_PRUEBA)
    assert sim.aplicados == [] and list(existente.iterdir()) == []
    sim.fijar(existente, _desc(_ace(USUARIO_SID, banderas=0x03)))  # ya restringido por su dueño: se admite
    al.AlmacenSeguridad.crear(existente / "seguridad.sqlite3", parametros=cs.PARAMETROS_PRUEBA)
    assert sim.aplicados == [str(existente / "seguridad.sqlite3")]  # solo el archivo nuevo


def test_windows_simulado_aplicacion_incompleta_no_deja_almacen(monkeypatch, tmp_path):
    sim = WindowsSimulado(monkeypatch)
    monkeypatch.setattr(pe, "aplicar_descriptor", lambda ruta, usuario, directorio: sim.aplicados.append(str(ruta)))
    with pytest.raises(al.OperacionRechazada):
        al.AlmacenSeguridad.crear(tmp_path / "nuevo" / "seguridad.sqlite3", parametros=cs.PARAMETROS_PRUEBA)
    assert not (tmp_path / "nuevo" / "seguridad.sqlite3").exists()


@pytest.mark.skipif(os.name == "nt", reason="permisos POSIX")
def test_posix_directorio_preexistente_amplio_se_rechaza_sin_cambiarlo(tmp_path):
    existente = tmp_path / "existente"
    existente.mkdir()
    os.chmod(existente, 0o755)
    with pytest.raises(al.OperacionRechazada, match="no se modifica"):
        al.AlmacenSeguridad.crear(existente / "seguridad.sqlite3", parametros=cs.PARAMETROS_PRUEBA)
    assert existente.stat().st_mode & 0o777 == 0o755 and list(existente.iterdir()) == []
    os.chmod(existente, 0o700)
    al.AlmacenSeguridad.crear(existente / "seguridad.sqlite3", parametros=cs.PARAMETROS_PRUEBA)


@pytest.mark.skipif(os.name == "nt", reason="permisos POSIX")
def test_posix_cambio_posterior_de_permisos_y_enlace_cierran(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    s.comprobar()
    os.chmod(s.archivo.parent, 0o750)
    with pytest.raises(al.ConsolaNoDisponible) as e:
        s.comprobar()
    assert e.value.motivo == "permisos"
    os.chmod(s.archivo.parent, 0o700)
    s.comprobar()
    enlace = s.archivo.parent / "enlace.sqlite3"
    enlace.symlink_to(s.archivo)
    with pytest.raises(al.ConsolaNoDisponible) as e:
        al.AlmacenSeguridad(enlace).comprobar()
    assert e.value.motivo == "permisos"


def test_http_permisos_no_verificables_da_503_sin_detalles(monkeypatch, restaurar_app, tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    app.state.almacen_seguridad = s
    monkeypatch.setattr(pe, "es_windows", lambda: True)
    monkeypatch.setattr(pe, "sid_actual", lambda: USUARIO_SID)
    monkeypatch.setattr(pe, "leer_descriptor", lambda ruta: (_ for _ in ()).throw(OSError(5, "denegado")))
    r = TestClient(app, base_url="http://localhost:8000", client=cs.LOCAL).get("/acceso")
    assert r.status_code == 503 and "No se pudieron verificar los permisos" in r.text
    assert str(tmp_path) not in r.text and "OSError" not in r.text


# =============================================================================== E101-SEC-02 · admisión
def _concurrentes(s, presesiones, contrasena, *, usuarios=None, demora=0.3):
    """Flujo real de `autenticar` desde varios hilos; la verificación se hace lenta para solaparlos."""
    original, cerrojo = cr.verificar, threading.Lock()
    estado = {"llamadas": 0, "en_curso": 0, "maximo": 0}
    salida = threading.Barrier(len(presesiones))

    def lenta(*a, **k):
        with cerrojo:
            estado["llamadas"] += 1
            estado["en_curso"] += 1
            estado["maximo"] = max(estado["maximo"], estado["en_curso"])
        try:
            time.sleep(demora)
            return original(*a, **k)
        finally:
            with cerrojo:
                estado["en_curso"] -= 1

    def uno(i):
        salida.wait(timeout=10)
        return s.autenticar((usuarios or ["admin"] * len(presesiones))[i], contrasena, presesiones[i], "127.0.0.1")[0]

    cr.verificar = lenta
    try:
        with concurrent.futures.ThreadPoolExecutor(len(presesiones)) as pool:
            resultados = list(pool.map(uno, range(len(presesiones))))
    finally:
        cr.verificar = original
    return collections.Counter(resultados), estado


def _filas(s, tabla):
    with sqlite3.connect(s.archivo) as c:
        return c.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]


def test_hilos_misma_cuenta_una_sola_verificacion_en_curso(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    resultados, estado = _concurrentes(s, [s.crear_presesion() for _ in range(8)], "incorrecta-larga-1")
    assert estado["llamadas"] == 1 and resultados == {"credenciales": 1, "espera": 7}
    with sqlite3.connect(s.archivo) as c:
        assert c.execute("SELECT fallos FROM intentos").fetchall() == [(1,)]
    assert _filas(s, "admisiones") == 0 and _filas(s, "presesiones") == 0  # todas consumidas, ninguna reserva


def test_hilos_misma_presesion_un_solo_acceso(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    p = s.crear_presesion()
    resultados, estado = _concurrentes(s, [p] * 8, cs.CONTRASENA_PRUEBA)
    assert resultados == {"ok": 1, "presesion": 7} and estado["llamadas"] == 1
    assert _filas(s, "sesiones") == 1
    assert s.autenticar("admin", cs.CONTRASENA_PRUEBA, p, "l")[0] == "presesion"  # tampoco después


def test_hilos_limite_global_de_verificaciones(tmp_path):
    s = cs.almacen_de_prueba(tmp_path, cuentas=(("ana", "lector"), ("bea", "lector"), ("eva", "lector"), ("admin", "administrador")))
    usuarios = ["ana", "bea", "eva", "fantasma"]
    resultados, estado = _concurrentes(s, [s.crear_presesion() for _ in usuarios], "incorrecta-larga-1",
                                       usuarios=usuarios, demora=0.6)
    assert estado["maximo"] <= al.MAX_VERIFICACIONES_EN_CURSO and estado["llamadas"] == al.MAX_VERIFICACIONES_EN_CURSO
    assert resultados["espera"] == len(usuarios) - al.MAX_VERIFICACIONES_EN_CURSO


def test_control_positivo_accesos_validos_sucesivos_y_umbral_secuencial(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    for _ in range(3):
        assert s.autenticar("admin", cs.CONTRASENA_PRUEBA, s.crear_presesion(), "l")[0] == "ok"
    assert _filas(s, "admisiones") == 0


def test_reserva_se_libera_si_la_verificacion_falla_por_excepcion(tmp_path, monkeypatch):
    s = cs.almacen_de_prueba(tmp_path)

    def rota(*a, **k):
        raise RuntimeError("fallo interno simulado")

    monkeypatch.setattr(cr, "verificar", rota)
    with pytest.raises(RuntimeError):
        s.autenticar("admin", cs.CONTRASENA_PRUEBA, s.crear_presesion(), "l")
    assert _filas(s, "admisiones") == 0
    monkeypatch.undo()
    assert s.autenticar("admin", cs.CONTRASENA_PRUEBA, s.crear_presesion(), "l")[0] == "ok"


def test_reserva_de_un_proceso_terminado_caduca(tmp_path):
    reloj = {"t": 1_000_000.0}
    s = cs.almacen_de_prueba(tmp_path, reloj=lambda: reloj["t"])
    with sqlite3.connect(s.archivo) as c:  # reserva huérfana, como la de un proceso que murió verificando
        c.execute("INSERT INTO admisiones VALUES ('huerfana', ?, ?)", (s.clave_intento("admin"), reloj["t"] + al.ADMISION_DURACION))
    assert s.autenticar("admin", cs.CONTRASENA_PRUEBA, s.crear_presesion(), "l")[0] == "espera"
    reloj["t"] += al.ADMISION_DURACION + 1
    assert s.autenticar("admin", cs.CONTRASENA_PRUEBA, s.crear_presesion(), "l")[0] == "ok"
    assert _filas(s, "admisiones") == 0


def test_cuenta_cambiada_durante_la_verificacion_no_obtiene_sesion(tmp_path, monkeypatch):
    s = cs.almacen_de_prueba(tmp_path, cuentas=(("admin", "administrador"), ("otro", "administrador")))
    original = cr.verificar

    def con_cambio(*a, **k):
        al.AlmacenSeguridad(s.archivo, parametros=cs.PARAMETROS_PRUEBA).cambiar_contrasena("admin", "nueva-contrasena-larga")
        return original(*a, **k)

    monkeypatch.setattr(cr, "verificar", con_cambio)
    assert s.autenticar("admin", cs.CONTRASENA_PRUEBA, s.crear_presesion(), "l")[0] == "credenciales"
    assert _filas(s, "sesiones") == 0


def _hijo_acceso(archivo, usuario, contrasena, presesion, barrera, demora, cola):
    from app.seguridad_consola import almacen as al_hijo
    from app.seguridad_consola import credenciales as cr_hijo
    from tests import consola_sesion as cs_hijo
    s = al_hijo.AlmacenSeguridad(archivo, parametros=cs_hijo.PARAMETROS_PRUEBA, minimos=cs_hijo.PARAMETROS_PRUEBA)
    original, llamadas = cr_hijo.verificar, [0]

    def lenta(*a, **k):
        llamadas[0] += 1
        time.sleep(demora)
        return original(*a, **k)

    cr_hijo.verificar = lenta
    barrera.wait(timeout=120)
    cola.put((s.autenticar(usuario, contrasena, presesion, "127.0.0.1")[0], llamadas[0]))


def _procesos(s, presesiones, contrasena):
    ctx = multiprocessing.get_context("spawn")
    barrera, cola = ctx.Barrier(len(presesiones)), ctx.Queue()
    hijos = [ctx.Process(target=_hijo_acceso, args=(str(s.archivo), "admin", contrasena, p, barrera, 1.5, cola))
             for p in presesiones]
    for h in hijos:
        h.start()
    for h in hijos:
        h.join(240)
    assert all(h.exitcode == 0 for h in hijos)
    filas = [cola.get(timeout=10) for _ in hijos]
    return collections.Counter(r for r, _ in filas), sum(n for _, n in filas)


def test_procesos_misma_cuenta_una_sola_verificacion(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    resultados, llamadas = _procesos(s, [s.crear_presesion() for _ in range(4)], "incorrecta-larga-1")
    assert llamadas == 1 and resultados == {"credenciales": 1, "espera": 3}
    assert _filas(s, "admisiones") == 0


def test_procesos_misma_presesion_un_solo_acceso(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    p = s.crear_presesion()
    resultados, llamadas = _procesos(s, [p] * 4, cs.CONTRASENA_PRUEBA)
    assert resultados == {"ok": 1, "presesion": 3} and llamadas == 1 and _filas(s, "sesiones") == 1


def test_http_presesion_reutilizada_tras_acceso_correcto(restaurar_app):
    s = cs.almacen_de_prueba()
    app.state.almacen_seguridad = s
    c = TestClient(app, base_url="http://localhost:8000", client=cs.LOCAL)
    pagina = c.get("/acceso")
    token = cs._CSRF_ACCESO.search(pagina.text).group(1)
    presesion = c.cookies.get(COOKIE_PRESESION)
    datos = {"csrf_token": token, "usuario": "admin", "contrasena": cs.CONTRASENA_PRUEBA, "siguiente": "/"}
    assert c.post("/acceso", data=datos, follow_redirects=False).status_code == 303
    otro = TestClient(app, base_url="http://localhost:8000", client=cs.LOCAL)
    otro.cookies.set(COOKIE_PRESESION, presesion)
    r = otro.post("/acceso", data=datos, follow_redirects=False)
    assert r.status_code == 400 and COOKIE_SESION not in r.cookies


# =============================================================================== E101-ROB-01 · HTTP
@pytest.mark.parametrize("host,valido", [("localhost", True), ("localhost:8000", True), ("LOCALHOST:8000", True),
                                         ("127.0.0.1:8000", True), ("[::1]:8000", True), ("[::1]", True),
                                         ("[", False), ("[::1", False), ("localhost:", False), ("localhost:abc", False),
                                         ("localhost:0", False), ("localhost:99999", False), ("localhost.", False),
                                         ("evil.example", False), ("localhost@evil", False), ("127.0.0.1.evil", False),
                                         ("", False), ("l" * 70, False), ("localhost:8000 ", False)])
def test_gramatica_de_host(host, valido):
    assert host_local_valido(host) is valido


@pytest.mark.parametrize("host,estado", [("[", 403), ("[::1", 403), ("localhost:abc", 403), ("localhost:99999", 403),
                                         ("localhost:8000", 200), ("127.0.0.1:8000", 200), ("[::1]:8000", 200)])
def test_http_host_malformado_rechazado_y_variantes_legitimas(restaurar_app, host, estado):
    app.state.almacen_seguridad = cs.almacen_de_prueba()
    c = TestClient(app, base_url="http://localhost:8000", client=cs.LOCAL, raise_server_exceptions=False)
    assert c.get("/acceso", headers={"Host": host}, follow_redirects=False).status_code == estado


@pytest.mark.parametrize("valor", [b"\xff", "ñ".encode("utf-8"), b"A" * 5000, b"abc", b""])
def test_http_cookie_de_presesion_malformada_da_4xx_sin_sesion(restaurar_app, valor):
    s = cs.almacen_de_prueba()
    app.state.almacen_seguridad = s
    c = TestClient(app, base_url="http://localhost:8000", client=cs.LOCAL, raise_server_exceptions=False)
    cabeceras = httpx.Headers([(b"cookie", COOKIE_PRESESION.encode("ascii") + b"=" + valor)])
    r = c.post("/acceso", data={"csrf_token": "0" * 64, "usuario": "admin", "contrasena": cs.CONTRASENA_PRUEBA},
               headers=cabeceras, follow_redirects=False)
    assert 400 <= r.status_code < 500 and _filas(s, "sesiones") == 0
    assert c.get("/acceso", headers=cabeceras).status_code == 200  # control positivo: formulario nuevo


@pytest.mark.parametrize("valor", [b"\xff", b"A" * 5000, "ñ".encode("utf-8")])
def test_http_cookie_de_sesion_malformada_no_da_500(restaurar_app, valor):
    app.state.almacen_seguridad = cs.almacen_de_prueba()
    c = TestClient(app, base_url="http://localhost:8000", client=cs.LOCAL, raise_server_exceptions=False)
    cabeceras = httpx.Headers([(b"cookie", COOKIE_SESION.encode("ascii") + b"=" + valor)])
    assert c.get("/", headers=cabeceras, follow_redirects=False).status_code == 303
    assert c.get("/api/juegos", headers=cabeceras).status_code == 401


def test_http_referer_no_interpretable_da_403_y_control_positivo(restaurar_app):
    from app.api import dependencies as dep
    app.dependency_overrides[dep.get_gestionar_paleta_colores] = lambda: object()  # sin base de datos
    c = cs.cliente_autenticado(app, "administrador", raise_server_exceptions=False)
    assert c.post("/colores", data={"codigo": "ZZ"}, headers={"Referer": "http://["}).status_code == 403
    r = c.post("/colores", data={"codigo": "ZZ"}, headers={"Referer": "http://localhost:8000/colores"})
    assert r.status_code not in (403, 500)  # pasa el origen; después decide la validación de la ruta


def test_derivar_csrf_exige_identificador_valido():
    for malo in ("ÿ" * 43, "a" * 42, "a" * 65, "", None):
        with pytest.raises(ValueError):
            al.derivar_csrf(malo, "acceso")
    assert len(al.derivar_csrf("a" * 43, "acceso")) == 64


# =============================================================================== E101-OBS-01 · retención
def test_retencion_en_accesos_salidas_y_operaciones_de_cuentas(monkeypatch, tmp_path):
    monkeypatch.setattr(al, "MAX_AUDITORIA", 20)
    s = cs.almacen_de_prueba(tmp_path)
    for i in range(60):
        s.autenticar(f"ausente{i:03d}", "incorrecta-larga-1", s.crear_presesion(), "l")
        assert _filas(s, "auditoria") <= 20
    for i in range(10):
        resultado, sid = s.autenticar("admin", cs.CONTRASENA_PRUEBA, s.crear_presesion(), "l")
        assert resultado == "ok"
        s.cerrar_sesion(sid, "admin")
        s.crear_cuenta(f"cuenta{i:02d}", cs.CONTRASENA_PRUEBA, "lector", actor="prueba")
        s.cambiar_rol(f"cuenta{i:02d}", "operador", actor="prueba")
        s.revocar_sesiones(actor="prueba")
        assert _filas(s, "auditoria") <= 20
    ultimos = s.auditoria(4)
    assert [e["evento"] for e in ultimos] == ["sesiones_revocadas", "rol_cambiado", "cuenta_creada", "salida"]


def test_retencion_conserva_atomicidad_con_la_operacion(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    antes = _filas(s, "auditoria")
    with pytest.raises(al.OperacionRechazada):
        s.crear_cuenta("admin", cs.CONTRASENA_PRUEBA, "lector")  # duplicada: ni cuenta ni evento
    with pytest.raises(al.OperacionRechazada):
        s.cambiar_rol("admin", "lector")  # último administrador: ni cambio ni evento
    assert _filas(s, "auditoria") == antes and s.cuentas()[0]["rol"] == "administrador"


def test_almacen_de_esquema_v1_queda_cerrado(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    with sqlite3.connect(s.archivo) as c:
        c.execute("UPDATE meta SET valor = '1' WHERE clave = 'esquema'")
    with pytest.raises(al.ConsolaNoDisponible) as e:
        s.comprobar()
    assert e.value.motivo == "esquema"


# =============================================================================== E101-VAL-01 · ayudante nativo
def test_buscar_secreto_entrada_oculta_y_solo_booleanos(monkeypatch, capsys, tmp_path):
    secreto = "sintetica-de-ensayo-123"
    (tmp_path / "utf8.txt").write_text(f"x {secreto} y", encoding="utf-8")
    (tmp_path / "utf16.txt").write_bytes(f"x {secreto} y".encode("utf-16-le"))
    (tmp_path / "limpio.txt").write_text("nada", encoding="utf-8")
    monkeypatch.setattr(buscar.getpass, "getpass", lambda *_a, **_k: secreto)
    argumentos = []
    for nombre in ("utf8.txt", "utf16.txt", "limpio.txt"):
        argumentos += ["--archivo", str(tmp_path / nombre)]
    assert buscar.main(argumentos) == 1
    salida = capsys.readouterr().out
    datos = json.loads(salida)
    assert datos["apariciones"] == 2 and [f["aparece"] for f in datos["archivos"]] == [True, True, False]
    assert secreto not in salida and str(tmp_path) not in salida
    assert buscar.main(["--archivo", str(tmp_path / "limpio.txt")]) == 0
    capsys.readouterr()
    assert buscar.main(["--archivo", str(tmp_path / "no-existe.txt")]) == 2
    monkeypatch.setattr(buscar.getpass, "getpass", lambda *_a, **_k: "corta")
    assert buscar.main(["--archivo", str(tmp_path / "limpio.txt")]) == 2


def test_buscar_secreto_no_acepta_la_contrasena_como_argumento():
    with pytest.raises(SystemExit) as e:
        buscar.main(["--archivo", "x", "--secreto", "abc"])
    assert e.value.code == 2


def test_procedimiento_nativo_no_pide_contrasenas_en_comandos_y_es_autocontenido():
    from pathlib import Path
    import re
    texto = (Path(__file__).resolve().parents[3] / "docs" / "fase10_e101_windows_brave.md").read_text(encoding="utf-8")
    bloques = re.findall(r"```powershell\n(.*?)```", texto, flags=re.S)
    assert bloques
    codigo = "\n".join(bloques)
    assert "CONTRASENA-ESCRITA" not in texto and "Select-String" not in codigo
    assert all("lp_consola_sesion" in l for l in codigo.splitlines() if ".Contains(" in l)  # solo literales no secretos
    assert not re.search(r"(?i)--contrasena(?!-stdin)|-contrasena\s|Read-Host", codigo)
    prologo = next(b for b in bloques if "PRÓLOGO E10.1 v2" in b)
    for variable in ("$Backend", "$Python", "$Prueba", "$Almacen"):
        assert f"{variable} = [string]$Cfg." in prologo
    assert "ConvertFrom-Json" in prologo and "$LASTEXITCODE" in prologo and "Is64BitProcess" in prologo
    usan = [b for b in bloques if "PRÓLOGO" not in b and "$ConfigA" not in b]
    assert all("$BackendA" not in b for b in usan)  # solo el bloque A usa sus variables propias
    assert texto.count("Pegue el **prólogo**") >= 1 and "--user-data-dir" in codigo
    assert "Get-FileHash" not in codigo
    for linea in codigo.splitlines():  # llamadas nativas directas: con comprobación de código en la misma línea o la siguiente
        if linea.lstrip().startswith("& $Python"):
            siguiente = codigo.splitlines()[codigo.splitlines().index(linea) + 1]
            assert "$LASTEXITCODE" in linea or "$LASTEXITCODE" in siguiente
