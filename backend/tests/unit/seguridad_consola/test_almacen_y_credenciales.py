"""E10.1: credenciales scrypt y almacén privado de seguridad (SQLite propio), con relojes inyectados y procesos reales."""
from __future__ import annotations

import multiprocessing
import os
import sqlite3
import sys

import pytest

from app.seguridad_consola import almacen as al
from app.seguridad_consola import credenciales as cr
from tests import consola_sesion as cs

P = cs.PARAMETROS_PRUEBA


class Reloj:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def _almacen(tmp_path, reloj=None, cuentas=(("admin", "administrador"),)):
    return cs.almacen_de_prueba(tmp_path, cuentas=cuentas, reloj=reloj)


# ------------------------------------------------------------------ credenciales
def test_hash_scrypt_con_sal_y_parametros_y_verificacion():
    h = cr.crear_hash("una contraseña larga", P)
    partes = h.split("$")
    assert partes[:5] == ["scrypt", "1", str(P.n), str(P.r), str(P.p)] and len(partes) == 7
    assert cr.verificar("una contraseña larga", h, P) and not cr.verificar("otra contraseña larga", h, P)
    assert cr.crear_hash("una contraseña larga", P) != h  # sal distinta
    assert "una contraseña" not in h


def test_produccion_usa_los_parametros_documentados_y_rechaza_hashes_debiles():
    assert (cr.PRODUCCION.n, cr.PRODUCCION.r, cr.PRODUCCION.p) == (2 ** 17, 8, 1)
    debil = cr.crear_hash("una contraseña larga", P)
    assert not cr.verificar("una contraseña larga", debil, cr.PRODUCCION)  # por debajo de los mínimos


@pytest.mark.parametrize("codificado", ["", "scrypt$1$x", "bcrypt$1$1024$8$1$AA==$AA==", "scrypt$1$1000$8$1$AA==$AA==",
                                        "scrypt$1$1024$8$1$no-base64$AA=="])
def test_hash_malformado_nunca_verifica(codificado):
    assert cr.verificar("una contraseña larga", codificado, P) is False


@pytest.mark.parametrize("contrasena", ["corta", " " * 20, "x" * 1025, "con\ncontrol-largo"])
def test_politica_de_contrasena(contrasena):
    with pytest.raises(cr.ContrasenaNoValida):
        cr.validar_contrasena(contrasena)


# ------------------------------------------------------------------ almacén: apertura y fallo cerrado
def test_abrir_no_crea_archivos_y_sin_almacen_no_hay_consola(tmp_path):
    archivo = tmp_path / "nada" / "seguridad.sqlite3"
    with pytest.raises(al.ConsolaNoDisponible) as e:
        al.AlmacenSeguridad(archivo).comprobar()
    assert e.value.motivo == "no_provisionada" and not archivo.exists() and not archivo.parent.exists()


def test_almacen_sin_cuentas_activas_esta_cerrado(tmp_path):
    a = al.AlmacenSeguridad.crear(tmp_path / "s" / "seguridad.sqlite3", parametros=P, minimos=P)
    with pytest.raises(al.ConsolaNoDisponible) as e:
        a.comprobar()
    assert e.value.motivo == "sin_cuentas"


def test_almacen_corrupto_o_ajeno_esta_cerrado(tmp_path):
    a = _almacen(tmp_path)
    a.archivo.write_bytes(b"esto no es una base sqlite" * 10)
    with pytest.raises(al.ConsolaNoDisponible) as e:
        a.comprobar()
    assert e.value.motivo == "corrupta"
    # E101-TEST-01 (v3): el archivo y su directorio nuevos se crean con el creador privado, que fija los permisos
    # admitidos (POSIX 0700/0600; DACL del propietario en Windows). Así la guarda de permisos no rechaza antes y el
    # caso llega a la tabla `meta`. Después solo se cambia la aplicación declarada.
    otro = tmp_path / "otro" / "seguridad.sqlite3"
    al.AlmacenSeguridad.crear(otro, parametros=P, minimos=P)
    al.permisos.verificar(otro.parent, directorio=True)  # precondición: permisos admitidos
    al.permisos.verificar(otro, directorio=False)
    c = sqlite3.connect(otro)
    try:
        assert c.execute("UPDATE meta SET valor = 'otra' WHERE clave = 'aplicacion'").rowcount == 1
        c.commit()
    finally:
        c.close()
    with pytest.raises(al.ConsolaNoDisponible) as e:
        al.AlmacenSeguridad(otro).comprobar()
    assert e.value.motivo == "esquema"


@pytest.mark.skipif(os.name == "nt", reason="permisos POSIX; en Windows: test_permisos_windows_nativo.py (v2)")
def test_permisos_del_propietario_y_permisos_abiertos_cierran(tmp_path):
    a = _almacen(tmp_path)
    assert oct(a.archivo.stat().st_mode & 0o777) == "0o600"
    assert oct(a.archivo.parent.stat().st_mode & 0o777) == "0o700"
    os.chmod(a.archivo, 0o644)
    with pytest.raises(al.ConsolaNoDisponible) as e:
        a.comprobar()
    assert e.value.motivo == "permisos"


def test_crear_nunca_reemplaza(tmp_path):
    a = _almacen(tmp_path)
    with pytest.raises(al.OperacionRechazada):
        al.AlmacenSeguridad.crear(a.archivo)


# ------------------------------------------------------------------ cuentas
def test_cuentas_validacion_y_ultimo_administrador(tmp_path):
    a = _almacen(tmp_path)
    for usuario in ("Admin", "ab", "1abc", "con espacio", "x" * 40):
        with pytest.raises(al.OperacionRechazada):
            a.crear_cuenta(usuario, cs.CONTRASENA_PRUEBA, "lector")
    with pytest.raises(al.OperacionRechazada):
        a.crear_cuenta("otra", cs.CONTRASENA_PRUEBA, "superusuario")
    with pytest.raises(al.OperacionRechazada):
        a.crear_cuenta("admin", cs.CONTRASENA_PRUEBA, "lector")
    with pytest.raises(al.OperacionRechazada):
        a.cambiar_rol("admin", "lector")
    with pytest.raises(al.OperacionRechazada):
        a.desactivar("admin")
    a.crear_cuenta("segundo", cs.CONTRASENA_PRUEBA, "administrador")
    a.cambiar_rol("admin", "lector")
    assert {c["usuario"]: c["rol"] for c in a.cuentas()} == {"admin": "lector", "segundo": "administrador"}
    assert all("hash" not in c for c in a.cuentas())


# ------------------------------------------------------------------ sesiones
def _entrar(a, usuario="admin", contrasena=cs.CONTRASENA_PRUEBA):
    return a.autenticar(usuario, contrasena, a.crear_presesion(), "127.0.0.1")


def test_sesion_se_guarda_como_hash_y_persiste_tras_reinicio(tmp_path):
    a = _almacen(tmp_path)
    resultado, sid = _entrar(a)
    assert resultado == "ok" and len(sid) >= 43
    filas = sqlite3.connect(a.archivo).execute("SELECT id_hash FROM sesiones").fetchall()
    assert filas == [(al._hash(sid),)] and sid not in str(filas)
    reiniciado = al.AlmacenSeguridad(a.archivo, parametros=P, minimos=P)
    s = reiniciado.sesion(sid)
    assert s.usuario == "admin" and s.rol == "administrador" and s.csrf == al.derivar_csrf(sid, "sesion")


def test_expiracion_por_inactividad_y_absoluta(tmp_path):
    reloj = Reloj()
    a = _almacen(tmp_path, reloj)
    _, sid = _entrar(a)
    reloj.t += al.INACTIVIDAD - 5
    assert a.sesion(sid) is not None  # toca y renueva la inactividad
    reloj.t += al.INACTIVIDAD - 5
    assert a.sesion(sid) is not None
    reloj.t += al.INACTIVIDAD + 1
    assert a.sesion(sid) is None and a.sesion(sid) is None  # caducada y borrada
    _, sid = _entrar(a)
    for _ in range(int(al.ABSOLUTA // (al.INACTIVIDAD - 60)) + 2):
        reloj.t += al.INACTIVIDAD - 60
        vigente = a.sesion(sid)
    assert vigente is None  # la absoluta no se renueva con la actividad


def test_revocacion_cambio_de_contrasena_rol_y_desactivacion(tmp_path):
    reloj = Reloj()
    a = _almacen(tmp_path, reloj, cuentas=(("admin", "administrador"), ("ana", "administrador")))
    otra = "otra-contrasena-larga"
    _, s = _entrar(a, "ana")
    a.revocar_sesiones("ana")
    assert a.sesion(s) is None
    _, s = _entrar(a, "ana")
    a.cambiar_contrasena("ana", otra)
    assert a.sesion(s) is None
    assert _entrar(a, "ana")[0] == "credenciales"  # la contraseña anterior ya no vale
    reloj.t += 5
    _, s = _entrar(a, "ana", otra)
    a.cambiar_rol("ana", "operador")
    assert a.sesion(s) is None
    _, s = _entrar(a, "ana", otra)
    assert a.sesion(s).rol == "operador"
    a.desactivar("ana")
    assert a.sesion(s) is None and _entrar(a, "ana", otra)[0] == "credenciales"


def test_rol_se_reevalua_en_cada_solicitud(tmp_path):
    a = _almacen(tmp_path, cuentas=(("admin", "administrador"), ("ana", "operador")))
    _, sid = _entrar(a, "ana")
    with sqlite3.connect(a.archivo) as c:  # cambio directo sin versión: el rol vigente sale de la cuenta
        c.execute("UPDATE cuentas SET rol = 'lector' WHERE usuario = 'ana'")
    assert a.sesion(sid).rol == "lector"


def test_presesion_caduca_y_es_de_un_solo_uso(tmp_path):
    reloj = Reloj()
    a = _almacen(tmp_path, reloj)
    pre = a.crear_presesion()
    reloj.t += al.PRESESION_DURACION + 1
    assert a.autenticar("admin", cs.CONTRASENA_PRUEBA, pre, "l") == ("presesion", None)
    pre = a.crear_presesion()
    assert a.autenticar("admin", cs.CONTRASENA_PRUEBA, pre, "l")[0] == "ok"
    assert a.autenticar("admin", cs.CONTRASENA_PRUEBA, pre, "l") == ("presesion", None)


def test_limitacion_de_intentos_progresiva_y_bloqueo_sin_revelar_usuarios(tmp_path):
    reloj = Reloj()
    a = _almacen(tmp_path, reloj)
    for usuario in ("admin", "inexistente"):
        esperas = []
        for _ in range(al.FALLOS_PARA_BLOQUEO):
            assert a.autenticar(usuario, "mala-contrasena-x", a.crear_presesion(), "l") == ("credenciales", None)
            esperas.append(a.espera_requerida([a.clave_intento(usuario)]))
            assert a.autenticar(usuario, cs.CONTRASENA_PRUEBA, a.crear_presesion(), "l") == ("espera", None)
            reloj.t += esperas[-1]
        assert esperas[:4] == [1, 2, 4, 8] and esperas[-1] > 300  # progresiva y, al quinto fallo, bloqueo
        reloj.t += al.BLOQUEO
    assert a.autenticar("admin", cs.CONTRASENA_PRUEBA, a.crear_presesion(), "l")[0] == "ok"


def test_crecimiento_acotado_de_presesiones_sesiones_y_auditoria(tmp_path, monkeypatch):
    a = _almacen(tmp_path)
    monkeypatch.setattr(al, "MAX_PRESESIONES", 5)
    for _ in range(12):
        a.crear_presesion()
    sesiones = [_entrar(a)[1] for _ in range(al.MAX_SESIONES_POR_CUENTA + 3)]
    with sqlite3.connect(a.archivo) as c:
        assert c.execute("SELECT count(*) FROM presesiones").fetchone()[0] <= 5 + al.MAX_SESIONES_POR_CUENTA + 3
        assert c.execute("SELECT count(*) FROM sesiones").fetchone()[0] == al.MAX_SESIONES_POR_CUENTA
    assert a.sesion(sesiones[0]) is None and a.sesion(sesiones[-1]) is not None
    monkeypatch.setattr(al, "MAX_AUDITORIA", 50)
    for i in range(300):
        a.auditar("x", "evento", str(i), "ok")
    with sqlite3.connect(a.archivo) as c:
        assert c.execute("SELECT count(*) FROM auditoria").fetchone()[0] <= 150


def test_auditoria_sin_secretos_y_sin_inyeccion(tmp_path):
    a = _almacen(tmp_path)
    _, sid = _entrar(a)
    a.autenticar("admin\nFALSO evento=ok", "mala-contrasena-x", a.crear_presesion(), "l")
    a.auditar("u", "e\r\nlinea", "<script>x</script>\n", "ok")
    volcado = a.archivo.read_bytes()
    texto = str(a.auditoria(100))
    assert cs.CONTRASENA_PRUEBA not in texto and sid not in texto and al._hash(sid) not in texto
    assert cs.CONTRASENA_PRUEBA.encode() not in volcado and sid.encode() not in volcado
    assert "\n" not in texto.replace("\\n", "") and "(no válido)" in texto


# ------------------------------------------------------------------ coordinación entre procesos (CLI / servidor)
def _proceso_escritor(archivo: str, inicio: int, n: int) -> None:
    sys.path.insert(0, os.getcwd())
    from app.seguridad_consola.almacen import AlmacenSeguridad
    a = AlmacenSeguridad(archivo, parametros=P, minimos=P)
    for i in range(inicio, inicio + n):
        a.crear_cuenta(f"cuenta{i:04d}", cs.CONTRASENA_PRUEBA, "lector", actor="proceso")


def test_escrituras_concurrentes_de_varios_procesos_son_atomicas(tmp_path):
    a = _almacen(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    procesos = [ctx.Process(target=_proceso_escritor, args=(str(a.archivo), k * 100, 15)) for k in range(3)]
    for p in procesos:
        p.start()
    sesiones = [_entrar(a)[1] for _ in range(10)]
    for p in procesos:
        p.join(120)
        assert p.exitcode == 0
    cuentas = {c["usuario"] for c in a.cuentas()}
    assert len(cuentas) == 1 + 45 and all(s for s in sesiones)
    with sqlite3.connect(a.archivo) as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("SELECT count(*) FROM auditoria WHERE evento = 'cuenta_creada'").fetchone()[0] == 46
