"""E10.1: cobertura del registro de políticas frente a las rutas efectivas de `app.main:app`."""
from __future__ import annotations

import multiprocessing
import os
import sys

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.web.routers import acceso
from app.main import app
from app.seguridad_consola import politicas as pol
from app.seguridad_consola.consola import ErrorConsola, LimiteLocal, autorizar_consola, manejar_error_consola
from tests import consola_sesion as cs


def _rutas():
    return pol.rutas_de(app)


def test_toda_ruta_tiene_politica_y_toda_politica_tiene_ruta():
    claves = {(m, p) for tipo, m, p in _rutas() if tipo != "Mount" and m != "HEAD"}
    assert claves - set(pol.POLITICAS) == set(), "rutas sin política"
    assert set(pol.POLITICAS) - claves == set(), "políticas huérfanas"


def test_solo_rutas_fastapi_y_el_montaje_estatico():
    tipos = {(tipo, p) for tipo, _m, p in _rutas() if tipo != "APIRoute"}
    assert tipos == {("Mount", "/static")}, "una ruta fuera de APIRoute no pasaría por la dependencia global"
    assert pol.MONTAJES_ESTATICOS == ("/static",)


def test_dependencia_global_registrada_y_documentacion_desactivada():
    assert any(getattr(d, "dependency", None) is autorizar_consola for d in app.router.dependencies)
    assert app.docs_url is None and app.redoc_url is None and app.openapi_url is None
    assert any(m.cls is LimiteLocal for m in app.user_middleware)


def test_excepciones_de_autenticacion_exactas_y_sin_prefijos():
    excepciones = {k for k, v in pol.POLITICAS.items() if v.tipo != "rol"}
    assert excepciones == {("GET", "/acceso"), ("POST", "/acceso"), ("POST", "/salir")}
    assert pol.POLITICAS[("POST", "/salir")].tipo == "sesion"


def test_reconciliacion_de_las_39_escrituras_y_las_nuevas_de_autenticacion():
    escrituras = {k: v for k, v in pol.POLITICAS.items() if k[0] != "GET"}
    negocio = {k: v for k, v in escrituras.items() if v.tipo == "rol"}
    assert len(negocio) == 39 and len(escrituras) == 41
    for clave, politica in negocio.items():
        roles = set(politica.por_valor.values()) if politica.por_accion else {politica.rol}
        assert roles <= {"operador", "administrador"}, clave
        assert politica.efecto not in ("lectura", "lectura_con_cache", "exportacion"), clave


def test_gets_son_lecturas_justificadas():
    gets = {k: v for k, v in pol.POLITICAS.items() if k[0] == "GET" and v.tipo == "rol"}
    assert all(v.rol == "lector" and v.efecto in ("lectura", "lectura_con_cache", "exportacion") for v in gets.values())
    con_cache = [k for k, v in gets.items() if v.efecto == "lectura_con_cache"]
    assert con_cache and all(k[1].startswith("/estadisticas/") for k in con_cache)


def test_politicas_por_accion_exactas():
    auto = pol.POLITICAS[("POST", "/automatizacion/{accion}")]
    assert (auto.fuente, auto.parametro) == ("ruta", "accion")
    assert dict(auto.por_valor) == {"comprobar": "operador", "pausar": "administrador", "reanudar": "administrador",
                                    "recuperar": "administrador"}
    assert auto.rol_requerido({"accion": "detener"}, {}) is None
    op = pol.POLITICAS[("POST", "/operacion/ejecutar")]
    assert dict(op.por_valor) == {"local": "operador", "actualizar": "administrador"}
    assert op.rol_requerido({}, {}) is None


def test_ruta_de_negocio_sin_politica_se_deniega_incluso_al_administrador():
    """Misma composición que `app.main` (límite local, dependencia global, acceso), más una ruta sin política."""
    prueba = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, dependencies=[Depends(autorizar_consola)])
    prueba.add_exception_handler(ErrorConsola, manejar_error_consola)
    prueba.add_middleware(LimiteLocal)
    prueba.include_router(acceso.router)
    ejecutada = []

    @prueba.post("/nueva-escritura")
    def nueva():
        ejecutada.append(1)
        return {"ok": True}

    @prueba.get("/nueva-lectura")
    def nueva_lectura():
        ejecutada.append(2)
        return {"ok": True}

    almacen = cs.almacen_de_prueba(cuentas=(("admin", "administrador"),))
    c = cs.cliente_autenticado(prueba, "administrador", almacen=almacen)
    assert c.post("/nueva-escritura").status_code == 403
    assert c.get("/nueva-lectura").status_code == 403
    assert ejecutada == []
    assert any(e["evento"] == "acceso" for e in almacen.auditoria(10))


def _importar_sin_crear(directorio: str, cola) -> None:
    os.environ["CONSOLA_SEGURIDAD_DIRECTORIO"] = directorio
    sys.path.insert(0, os.getcwd())
    from fastapi.testclient import TestClient as Cliente
    from app.main import app as aplicacion
    estado = Cliente(aplicacion, base_url="http://localhost:8000", client=("127.0.0.1", 1)).get("/").status_code
    cola.put((estado, os.path.exists(directorio)))


def test_importar_y_atender_sin_almacen_no_crea_archivos(tmp_path):
    destino = tmp_path / "privado-de-prueba"
    ctx = multiprocessing.get_context("spawn")
    cola = ctx.Queue()
    p = ctx.Process(target=_importar_sin_crear, args=(str(destino), cola))
    p.start()
    p.join(180)
    assert p.exitcode == 0 and cola.get(timeout=5) == (503, False)


def test_api_publica_y_pasarela_no_montan_la_seguridad_de_la_consola():
    from app.api.publica.aplicacion import app as publica
    from app.pasarela.aplicacion import app as pasarela
    assert not any(m.cls is LimiteLocal for m in publica.user_middleware)
    assert not any(getattr(d, "dependency", None) is autorizar_consola for d in publica.router.dependencies)
    assert not hasattr(pasarela, "user_middleware") or not any(m.cls is LimiteLocal for m in pasarela.user_middleware)
    assert TestClient(publica).get("/api/v1/salud").json() == {"estado": "ok", "api": "v1"}
