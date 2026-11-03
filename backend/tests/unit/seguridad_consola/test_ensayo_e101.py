"""E10.1: el backend de ensayo del protocolo Windows/Brave funciona con servicios sustituidos y cero ciclos."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.web import proteccion_local
from app.main import app
from app.seguridad_consola.almacen import AlmacenSeguridad, ruta_predeterminada
from tests import consola_sesion as cs
from tests import ensayo_consola_e101 as ensayo


@pytest.fixture
def restaurar():
    previo, sustituciones = getattr(app.state, "almacen_seguridad", None), dict(app.dependency_overrides)
    yield
    app.state.almacen_seguridad = previo
    app.dependency_overrides.clear()
    app.dependency_overrides.update(sustituciones)


def test_ensayo_sin_almacen_no_arranca(restaurar, tmp_path):
    from app.seguridad_consola.almacen import ConsolaNoDisponible
    with pytest.raises(ConsolaNoDisponible):
        ensayo.preparar(tmp_path / "vacio")
    assert not (tmp_path / "vacio").exists()


def test_ensayo_roles_y_acciones_sustituidas(restaurar, tmp_path, capsys):
    almacen = AlmacenSeguridad.crear(ruta_predeterminada(tmp_path / "seg"))  # parámetros de producción
    for usuario, rol in (("operadora", "operador"), ("lectora", "lector")):
        almacen.crear_cuenta(usuario, cs.CONTRASENA_PRUEBA, rol, actor="prueba")
    ensayo.preparar(tmp_path / "seg")
    from app.api.automatizacion_dependencies import get_automatizacion
    servicio = app.dependency_overrides[get_automatizacion]()
    c = TestClient(app, base_url="http://127.0.0.1:8765", client=cs.LOCAL)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/acceso")
    assert cs.iniciar_sesion(c, "operadora").status_code == 303
    assert c.get("/").status_code == 200
    panel = c.get("/automatizacion")
    assert panel.status_code == 200 and 'action="/automatizacion/pausar"' not in panel.text
    csrf = cs.derivar_csrf(c.cookies.get("lp_consola_sesion"), "sesion")
    datos = {"token_local": proteccion_local.token_local(), "juego": "todos", "csrf_token": csrf}
    assert c.post("/automatizacion/comprobar", data=datos, follow_redirects=False).status_code == 303
    assert c.post("/automatizacion/pausar", data=datos, follow_redirects=False).status_code == 403
    assert servicio.acciones == [] and "lanzamiento SUSTITUIDO" in capsys.readouterr().out
    r = c.post("/colores", data={"codigo": "ZZ", "nombre": "Prueba"}, headers={"X-CSRF-Token": csrf, "HX-Request": "true"})
    assert r.status_code == 403  # histórico: administrador


@pytest.mark.parametrize("rol,visibles", [("lector", set()), ("operador", {"comprobar"}),
                                          ("administrador", {"comprobar", "pausar", "reanudar", "recuperar"})])
def test_panel_muestra_solo_las_acciones_del_rol(restaurar, tmp_path, rol, visibles):
    almacen = AlmacenSeguridad.crear(ruta_predeterminada(tmp_path / "seg"))
    almacen.crear_cuenta("cuenta", cs.CONTRASENA_PRUEBA, rol, actor="prueba")
    ensayo.preparar(tmp_path / "seg")
    c = TestClient(app, base_url="http://localhost:8000", client=cs.LOCAL)
    assert cs.iniciar_sesion(c, "cuenta").status_code == 303
    html = c.get("/automatizacion").text
    presentes = {a for a in ("comprobar", "pausar", "reanudar", "recuperar") if f'action="/automatizacion/{a}"' in html}
    assert presentes == visibles
    assert ("data-acciones-restringidas" in html) == (rol != "administrador")
