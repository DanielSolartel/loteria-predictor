"""E10.1: autorización por acción semántica y ausencia de efectos en solicitudes rechazadas.

Servicios SUSTITUIDOS con `dependency_overrides`: ningún ciclo de Fase 6, operación diaria, importación ni
escritura real se ejecuta. El lanzador sustituto solo registra; no ejecuta la función recibida.
"""
from __future__ import annotations

import pytest

from app.api import dependencies as dep
from app.api.web import proteccion_local
from app.api.automatizacion_dependencies import get_automatizacion, get_lanzador_automatizacion
from app.main import app
from tests import consola_sesion as cs


class Registro:
    def __init__(self):
        self.construcciones, self.llamadas, self.lanzadas = 0, [], []


@pytest.fixture
def registro():
    previo, sustituciones = getattr(app.state, "almacen_seguridad", None), dict(app.dependency_overrides)
    reg = Registro()

    class ServicioFalso:
        def __getattr__(self, nombre):
            def llamada(*a, **k):
                reg.llamadas.append(nombre)
                return None
            return llamada

    def construir():
        reg.construcciones += 1
        return ServicioFalso()

    def lanzador():
        reg.construcciones += 1
        return lambda funcion, *a: reg.lanzadas.append(funcion)  # no se ejecuta: cero ciclos reales

    app.dependency_overrides[get_automatizacion] = construir
    app.dependency_overrides[get_lanzador_automatizacion] = lanzador
    for proveedor in (dep.get_operacion_diaria, dep.get_lanzador_de_operacion, dep.get_sincronizar_sorteos,
                      dep.get_estado_importacion, dep.get_reimportar_sorteo, dep.get_reprocesar_desde_html,
                      dep.get_registrar_sorteo, dep.get_editar_sorteo, dep.get_eliminar_sorteo,
                      dep.get_gestionar_paleta_colores, dep.get_listar_juegos, dep.get_listar_sorteos,
                      dep.get_obtener_sorteo, dep.get_obtener_sorteo_con_pareja):
        app.dependency_overrides[proveedor] = construir

    class SesionProhibida:  # defensa adicional: ninguna prueba de este módulo usa una base real
        def __getattr__(self, nombre):
            raise AssertionError("acceso a base no permitido en estas pruebas")

    app.dependency_overrides[dep.get_db] = lambda: SesionProhibida()
    yield reg
    app.state.almacen_seguridad = previo
    app.dependency_overrides.clear()
    app.dependency_overrides.update(sustituciones)


def _cliente(rol):
    return cs.cliente_autenticado(app, rol)


def _token_local(_c):
    # El token local del proceso (defensa preexistente) se sigue exigiendo; se obtiene de su fuente.
    return proteccion_local.token_local()


ACCIONES = ("comprobar", "pausar", "reanudar", "recuperar")
PERMITIDAS = {"lector": set(), "operador": {"comprobar"}, "administrador": set(ACCIONES)}


@pytest.mark.parametrize("rol", ["lector", "operador", "administrador"])
@pytest.mark.parametrize("accion", ACCIONES)
def test_automatizacion_autoriza_cada_accion_por_separado(registro, rol, accion):
    c = _cliente(rol)
    token = _token_local(c)
    registro.construcciones = 0
    r = c.post(f"/automatizacion/{accion}", data={"token_local": token, "juego": "todos"}, follow_redirects=False)
    if accion in PERMITIDAS[rol]:
        assert r.status_code == 303 and registro.construcciones >= 1
        if accion == "comprobar":
            assert len(registro.lanzadas) == 1 and registro.llamadas == []  # lanzado al sustituto, nunca ejecutado
        else:
            assert registro.llamadas == [accion] and registro.lanzadas == []
    else:
        assert r.status_code == 403
        assert (registro.construcciones, registro.llamadas, registro.lanzadas) == (0, [], [])


@pytest.mark.parametrize("accion", ["detener", "PAUSAR", "pausar ", "ciclo", "instalar", "%2e%2e"])
def test_automatizacion_accion_desconocida_no_despacha_ni_para_administrador(registro, accion):
    c = _cliente("administrador")
    registro.construcciones = 0
    r = c.post(f"/automatizacion/{accion}", data={"token_local": _token_local(c), "juego": "todos"})
    assert r.status_code in (404, 422)
    assert (registro.construcciones, registro.llamadas, registro.lanzadas) == (0, [], [])


@pytest.mark.parametrize("rol,modo,permitido", [("operador", "local", True), ("operador", "actualizar", False),
                                               ("administrador", "actualizar", True), ("lector", "local", False),
                                               ("administrador", "otro", False)])
def test_operacion_diaria_autoriza_por_modo(registro, rol, modo, permitido):
    c = _cliente(rol)
    token = _token_local(c)
    registro.construcciones = 0
    r = c.post("/operacion/ejecutar", data={"juego": "todos", "modo": modo, "token_local": token}, follow_redirects=False)
    if permitido:
        assert r.status_code != 403 and registro.construcciones >= 1
    else:
        assert r.status_code in (403, 422) and registro.construcciones == 0 and registro.llamadas == []


# Las 13 escrituras que no tenían guarda local: sin sesión, sin rol o sin CSRF no construyen sus servicios.
SIN_GUARDA = [("POST", "/sorteos"), ("PUT", "/sorteos/00000000-0000-0000-0000-000000000001"),
              ("DELETE", "/sorteos/00000000-0000-0000-0000-000000000001"), ("POST", "/colores"), ("DELETE", "/colores/ZZ"),
              ("POST", "/importacion/sincronizar/MILOTO"), ("POST", "/importacion/reimportar-todo/MILOTO"),
              ("POST", "/importacion/reimportar-sorteo/00000000-0000-0000-0000-000000000001"),
              ("POST", "/importacion/reprocesar-html/MILOTO"), ("POST", "/api/sorteos"),
              ("DELETE", "/api/sorteos/00000000-0000-0000-0000-000000000001"), ("POST", "/api/colores"),
              ("DELETE", "/api/colores/ZZ")]


@pytest.mark.parametrize("metodo,ruta", SIN_GUARDA)
@pytest.mark.parametrize("situacion", ["sin_sesion", "lector", "operador", "sin_csrf"])
def test_escrituras_antes_abiertas_rechazadas_sin_efectos(registro, metodo, ruta, situacion):
    if situacion == "sin_sesion":
        cs.cliente_autenticado(app, "lector")
        from fastapi.testclient import TestClient
        c = TestClient(app, base_url="http://localhost:8000", client=cs.LOCAL)
        esperado = 401 if ruta.startswith("/api/") else (303, 401, 403)
    else:
        c = _cliente("administrador" if situacion == "sin_csrf" else situacion)
        if situacion == "sin_csrf":
            c.csrf = None
        esperado = 403
    registro.construcciones = 0
    r = c.request(metodo, ruta, data=None if ruta.startswith("/api/") else {"codigo_juego": "MILOTO"},
                  json={} if ruta.startswith("/api/") else None, follow_redirects=False)
    assert r.status_code in (esperado if isinstance(esperado, tuple) else (esperado,))
    assert registro.construcciones == 0 and registro.llamadas == []


@pytest.mark.parametrize("metodo,ruta", SIN_GUARDA)
def test_administrador_con_csrf_supera_la_autorizacion_de_esas_escrituras(registro, metodo, ruta):
    # Solo se comprueba que la autorización deja pasar y se construyen los servicios SUSTITUTOS; lo que haga
    # después la ruta con un sustituto vacío (p. ej. 422 de validación o 500) no forma parte de esta prueba.
    c = cs.cliente_autenticado(app, "administrador", raise_server_exceptions=False)
    registro.construcciones = 0
    r = c.request(metodo, ruta, data=None if ruta.startswith("/api/") else {"codigo_juego": "MILOTO"},
                  json={} if ruta.startswith("/api/") else None, follow_redirects=False)
    assert r.status_code not in (401, 403, 503)
    assert registro.construcciones >= 1 or r.status_code == 422  # 422: validación del cuerpo tras autorizar
