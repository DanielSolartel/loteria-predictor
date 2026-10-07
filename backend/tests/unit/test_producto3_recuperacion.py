"""Producto 3: recuperacion de ejecuciones y cerrojos frente a fallos.

1. Una ejecucion cuyo cierre global no llego a escribirse (disco lleno,
   proceso muerto despues de terminar los juegos) no puede quedar «en curso»
   para siempre: sin un trabajador vivo se informa como interrumpida.
2. Un fallo al adquirir los cerrojos no puede dejar bloqueos tomados.

Fallos inyectados de forma determinista; procesos coordinados con eventos."""
from __future__ import annotations

import errno
import json
import multiprocessing
import os
import pathlib

import pytest

from app.infrastructure.storage import operacion_file_store as modulo
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from tests.unit import fixtures_producto3 as f3

ESPERA = 30
FINALES = ("exito", "parcial", "fallo")


@pytest.fixture
def entorno(tmp_path):
    return f3.entorno(tmp_path)


class RegistroQueFallaAlCerrar(RegistroEjecucionesArchivo):
    """Falla (sin espacio) al escribir el estado global final."""

    def guardar(self, ejecucion):
        if ejecucion.get("estado") in FINALES:
            raise OSError(errno.ENOSPC, "No space left on device")
        super().guardar(ejecucion)


def _operacion(entorno, registro=None):
    op = entorno.operacion()
    if registro is not None:
        op._registro = registro
    return op


def _bytes_registro(entorno, identificador):
    return (entorno.directorio_operacion / "ejecuciones" / f"{identificador}.json").read_bytes()


# ---------------------------------------------------------------------------
# 1. Cierre global incompleto
# ---------------------------------------------------------------------------

def test_cierre_global_no_escrito_se_informa_como_interrumpida(entorno):
    op = _operacion(entorno, RegistroQueFallaAlCerrar(entorno.directorio_operacion))
    inicio = op.iniciar(["MILOTO"], "local", "prueba")
    with pytest.raises(OSError):
        op.ejecutar(inicio)
    identificador = inicio.ejecucion["id"]
    normal = entorno.operacion()  # otra instancia, como otra peticion o el comando
    antes = _bytes_registro(entorno, identificador)
    consultada = normal.consultar(identificador)
    assert consultada["estado"] == "interrumpida"
    assert consultada["juegos"]["MILOTO"]["estado"] == "ok"  # el resultado del juego se conserva
    assert consultada["juegos"]["MILOTO"]["pronostico"]["identificador"]
    assert _bytes_registro(entorno, identificador) == antes  # consultar es de solo lectura
    assert normal.activa("MILOTO") is None
    assert normal.recuperar() == [identificador]
    anotada = json.loads(_bytes_registro(entorno, identificador))
    assert anotada["estado"] == "interrumpida" and anotada["finalizada_en"]
    assert anotada["juegos"]["MILOTO"]["estado"] == "ok"  # no se convierte en exito ni se pierde
    assert normal.recuperar() == []  # idempotente
    nueva = normal.ejecutar_ahora(["MILOTO"], "local", "prueba")
    assert nueva["estado"] == "exito" and nueva["juegos"]["MILOTO"]["pronostico"]["reutilizado"] is True
    assert len(list((entorno.almacen._directorio / "MILOTO").glob("*.json"))) == 1


def test_trabajador_posterior_del_mismo_juego_no_reactiva_el_registro_antiguo(entorno):
    op = _operacion(entorno, RegistroQueFallaAlCerrar(entorno.directorio_operacion))
    viejo = op.iniciar(["MILOTO"], "local", "prueba")
    with pytest.raises(OSError):
        op.ejecutar(viejo)
    normal = entorno.operacion()
    nuevo = normal.iniciar(["MILOTO"], "local", "prueba")  # activo, aun sin ejecutar
    try:
        assert normal.consultar(nuevo.ejecucion["id"])["estado"] == "en_curso"
        assert normal.consultar(viejo.ejecucion["id"])["estado"] == "interrumpida"
        assert normal.activa("MILOTO") == nuevo.ejecucion["id"]
    finally:
        nuevo.cerrojos.liberar()


def _trabajador_detenido_antes_del_cierre(directorio, listo, nunca):
    """Proceso independiente: termina el juego y se detiene justo antes de
    escribir el cierre global (como si muriera en ese intervalo)."""
    entorno = f3.entorno(pathlib.Path(directorio))

    class Registro(RegistroEjecucionesArchivo):
        def guardar(self, ejecucion):
            if ejecucion.get("estado") in FINALES:
                listo.put(ejecucion["id"])
                nunca.wait(ESPERA)
            super().guardar(ejecucion)

    op = entorno.operacion()
    op._registro = Registro(entorno.directorio_operacion)
    op.ejecutar_ahora(["MILOTO"], "local", "proceso")


def test_ejecucion_viva_sigue_en_curso_y_su_muerte_es_interrupcion(tmp_path):
    contexto = multiprocessing.get_context("spawn")
    listo, nunca = contexto.Queue(), contexto.Event()
    proceso = contexto.Process(target=_trabajador_detenido_antes_del_cierre, args=(str(tmp_path), listo, nunca))
    proceso.start()
    try:
        identificador = listo.get(timeout=60)
        op = f3.entorno(tmp_path).operacion()
        viva = op.consultar(identificador)
        assert viva["estado"] == "en_curso"  # todos los juegos terminaron, pero el trabajador sigue vivo
        assert viva["juegos"]["MILOTO"]["estado"] == "ok"
        assert op.recuperar() == []  # recuperar no toca una ejecucion viva
        assert op.consultar(identificador)["estado"] == "en_curso"
    finally:
        proceso.kill()
        proceso.join(ESPERA)
    assert op.consultar(identificador)["estado"] == "interrumpida"
    assert op.recuperar() == [identificador]


def test_fallo_al_lanzar_el_hilo_libera_y_no_queda_activa(entorno):
    def lanzador_roto(funcion, inicio):
        raise RuntimeError("can't start new thread")

    c = f3.cliente(entorno, lanzador=lanzador_roto)
    try:
        token = c.get("/operacion").text.split('name="token_local" value="', 1)[1].split('"', 1)[0]
        r = c.post("/operacion/ejecutar", data={"juego": "MILOTO", "modo": "local", "token_local": token})
        assert r.status_code == 500 and "No se pudo iniciar" in r.text
        op = entorno.operacion()
        assert op.activa("MILOTO") is None
        ejecuciones = op.recientes()
        assert len(ejecuciones) == 1 and ejecuciones[0]["estado"] == "interrumpida"
        assert ejecuciones[0]["juegos"]["MILOTO"]["estado"] == "pendiente"
        ok = f3.cliente(entorno)
        r = ok.post("/operacion/ejecutar", data={"juego": "MILOTO", "modo": "local", "token_local": token},
                    follow_redirects=False)
        assert r.status_code == 303
    finally:
        f3.limpiar()


# ---------------------------------------------------------------------------
# 2. Cerrojos seguros frente a excepciones
# ---------------------------------------------------------------------------

def _escritura_que_falla(monkeypatch, nombres_que_fallan):
    original = pathlib.Path.write_text

    def escribir(self, *args, **kwargs):
        if self.name in nombres_que_fallan:
            raise OSError(errno.ENOSPC, "No space left on device")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "write_text", escribir)


def _libres_en_otro_proceso(directorio, codigos):
    contexto = multiprocessing.get_context("spawn")
    cola = contexto.Queue()
    proceso = contexto.Process(target=_proceso_adquirir, args=(str(directorio), list(codigos), cola))
    proceso.start()
    resultado = cola.get(timeout=60)
    proceso.join(60)
    return resultado


def _proceso_adquirir(directorio, codigos, cola):
    cerrojos = CerrojoPorJuego(directorio).adquirir(codigos, "20261001T000000Z-0000aaaa")
    if isinstance(cerrojos, dict):
        cola.put(("ocupados", cerrojos))
    else:
        cerrojos.liberar()
        cola.put(("ok", None))


def test_falla_escribir_activo_tras_tomar_un_cerrojo(tmp_path, monkeypatch):
    cerrojo = CerrojoPorJuego(tmp_path)
    _escritura_que_falla(monkeypatch, {"MILOTO.activo"})
    with pytest.raises(OSError):
        cerrojo.adquirir(["MILOTO"], "20261001T000000Z-00000001")
    monkeypatch.undo()
    assert cerrojo.ocupado("MILOTO") is False
    otra = cerrojo.adquirir(["MILOTO"], "20261001T000000Z-00000002")
    assert not isinstance(otra, dict)
    otra.liberar()
    assert _libres_en_otro_proceso(tmp_path, ["MILOTO"]) == ("ok", None)


def test_falla_el_activo_del_segundo_juego_tras_tomar_varios(tmp_path, monkeypatch):
    cerrojo = CerrojoPorJuego(tmp_path)
    _escritura_que_falla(monkeypatch, {"MILOTO.activo"})
    with pytest.raises(OSError):
        cerrojo.adquirir(["BALOTO", "MILOTO", "COLORLOTO"], "20261001T000000Z-00000001")
    monkeypatch.undo()
    assert not any(cerrojo.ocupado(c) for c in ("BALOTO", "MILOTO", "COLORLOTO"))
    assert not (tmp_path / "cerrojos" / "BALOTO.activo").exists()  # no queda informacion de un propietario falso
    assert _libres_en_otro_proceso(tmp_path, ["BALOTO", "MILOTO", "COLORLOTO"]) == ("ok", None)
    todos = cerrojo.adquirir(["BALOTO", "MILOTO", "COLORLOTO"], "20261001T000000Z-00000002")
    assert not isinstance(todos, dict)
    todos.liberar()


def test_falla_la_apertura_de_un_juego_tras_tomar_otro(tmp_path, monkeypatch):
    cerrojo = CerrojoPorJuego(tmp_path)
    original = os.open

    def abrir(ruta, *args, **kwargs):
        if str(ruta).endswith("MILOTO.lock"):
            raise PermissionError(errno.EACCES, "Acceso denegado", str(ruta))
        return original(ruta, *args, **kwargs)

    monkeypatch.setattr(modulo.os, "open", abrir)
    with pytest.raises(PermissionError):
        cerrojo.adquirir(["BALOTO", "MILOTO"], "20261001T000000Z-00000001")
    monkeypatch.undo()
    assert cerrojo.ocupado("BALOTO") is False
    assert _libres_en_otro_proceso(tmp_path, ["BALOTO"]) == ("ok", None)


def test_error_ajeno_a_la_contencion_no_se_presenta_como_ocupado(tmp_path, monkeypatch):
    cerrojo = CerrojoPorJuego(tmp_path)

    def bloquear_roto(descriptor):
        raise OSError(errno.EBADF, "Bad file descriptor")

    monkeypatch.setattr(modulo, "_bloqueo_del_sistema", bloquear_roto)
    with pytest.raises(OSError) as error:
        cerrojo.adquirir(["MILOTO"], "20261001T000000Z-00000001")
    assert error.value.errno == errno.EBADF


def test_exclusion_legitima_se_mantiene_sin_tocar_al_propietario(tmp_path):
    cerrojo = CerrojoPorJuego(tmp_path)
    propietario = cerrojo.adquirir(["MILOTO"], "20261001T000000Z-0000000a")
    try:
        segundo = cerrojo.adquirir(["BALOTO", "MILOTO"], "20261001T000000Z-0000000b")
        assert segundo == {"MILOTO": "20261001T000000Z-0000000a"}
        assert cerrojo.ocupado("BALOTO") is False  # todos o ninguno
        assert (tmp_path / "cerrojos" / "MILOTO.activo").read_text(encoding="ascii").strip() == \
            "20261001T000000Z-0000000a"
        assert _libres_en_otro_proceso(tmp_path, ["MILOTO"])[0] == "ocupados"
    finally:
        propietario.liberar()
