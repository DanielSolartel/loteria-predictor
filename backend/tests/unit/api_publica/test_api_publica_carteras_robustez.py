"""F94-ROB-01: metadatos incompletos con canon y lector de Producto 5 reales.

La preparación de cada defecto escribe sólo en una copia sintética propia,
antes de capturar las huellas. Los GET no deben reparar ni completar artefactos.
"""
from __future__ import annotations

import copy

import pytest

from app.api.publica import dependencias as d
from app.api.publica import esquemas_guardados as eg
from app.application.interfaces.carteras_store import GuardadoCarteras
from app.application.ml import carteras_artefactos as ca
from tests.unit import fixtures_fase4 as f4
from tests.unit.api_publica import fixtures_api_publica as fa
from tests.unit.api_publica.test_api_publica_guardados import (
    _bloquear, _copia, escenario, raiz_copia_corta,
)


def _recomponer(original, defecto):
    a = copy.deepcopy(original.artefacto)
    if defecto == "corte_ausente":
        del a["datos"]["corte"]
    elif defecto == "corte_texto":
        a["datos"]["corte"] = str(a["datos"]["corte"])
    elif defecto == "corte_booleano":
        a["datos"]["corte"] = True
    elif defecto == "nombre_ausente":
        del a["modelo"]["nombre"]
    elif defecto == "nombre_tipo_no_valido":
        a["modelo"]["nombre"] = []
    elif defecto == "fecha_tipo_no_valido":
        a["generacion"]["generado_en"] = []
    elif defecto == "sha_historico_ausente":
        del a["datos"]["sha256_historico"]
    elif defecto == "sha_historico_tipo_no_valido":
        a["datos"]["sha256_historico"] = []
    elif defecto == "clasificacion_tipo_no_valido":
        a["generacion"]["clasificacion_temporal"] = "clasificacion sintetica incompleta"
    elif defecto == "combinacion_tipo_no_valido":
        a["cartera"]["combinaciones"][0] = "combinacion sintetica incompleta"
    elif defecto == "nombre_unicode":
        a["modelo"]["nombre"] = "Modelo histórico — versión ámbar α"
    elif defecto == "fecha_ausente":
        del a["generacion"]["generado_en"]
    else:
        raise AssertionError("Defecto de prueba no reconocido")
    recompuesto = ca.componer(ca.cuerpo_de(a), "generacion", a["generacion"])
    assert ca.integro(recompuesto)
    # No se reasigna una identidad o versión de entrenamiento distinta.
    assert recompuesto["identidad"] == original.artefacto["identidad"]
    assert recompuesto["clave_de_entrada"] == original.identificador
    return recompuesto


@pytest.fixture
def copia(escenario, raiz_copia_corta, monkeypatch):
    e4, cu, api = _copia(escenario, raiz_copia_corta)
    api.app.dependency_overrides[d.consultas_guardadas] = lambda: cu
    try:
        llamadas = _bloquear(monkeypatch)
        # Esta lectura tampoco debe completar metadatos con la configuración
        # actual de Producto 5; sólo sirve el contenido del artefacto elegido.
        def no_configuracion(*args, **kwargs):
            pytest.fail("La proyección histórica consultó la configuración vigente")
        monkeypatch.setattr(cu._carteras, "configuracion_vigente", no_configuracion)
        yield e4, cu, api, llamadas
    finally:
        api.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


def _consultar_defecto(copia, juego, defecto):
    e4, cu, api, llamadas = copia
    cliente = api.cliente(raise_server_exceptions=False)
    url = f"/api/v1/juegos/{juego}/carteras-guardadas"
    cabeceras = api.cabeceras()
    anterior = cliente.get(url, headers=cabeceras)
    assert anterior.status_code == 200
    elementos = anterior.json()["elementos"]
    assert len(elementos) >= 2
    clave = elementos[0]["clave"]
    original = cu._carteras._almacen.obtener_cartera(clave)
    assert isinstance(original, GuardadoCarteras)
    sanas = {x["clave"]: x for x in elementos if x["clave"] != clave}
    ruta = next((e4.raiz / "carteras").rglob("*" + clave + ".json"))
    recompuesto = _recomponer(original, defecto)
    ruta.write_bytes(ca.json_canonico(recompuesto))
    leida = cu._carteras._almacen.obtener_cartera(clave)
    assert isinstance(leida, GuardadoCarteras)
    assert ca.integro(leida.artefacto)
    assert leida.identificador == original.identificador
    assert leida.linea == original.linea and leida.objetivo == original.objetivo
    assert leida.secuencia == original.secuencia
    antes, filas = f4.arbol(e4.raiz), fa.filas(api.entorno)
    listado = cliente.get(url, headers=cabeceras)
    ficha = cliente.get(url + "/" + clave, headers=cabeceras)
    # Una ficha sana sigue disponible incluso si la otra tiene metadatos malos.
    sana = cliente.get(url + "/" + next(iter(sanas)), headers=cabeceras)
    assert sana.status_code == 200
    assert sana.json()["cartera"] == sanas[next(iter(sanas))]
    assert llamadas == [] and f4.arbol(e4.raiz) == antes and fa.filas(api.entorno) == filas
    return original, recompuesto, listado, ficha, sanas


def _assert_listado_mixto(listado, original, sanas):
    assert listado.status_code == 200, listado.text
    datos = listado.json()
    eg.CarterasGuardadas.model_validate(datos)
    por_clave = {x["clave"]: x for x in datos["elementos"]}
    assert datos["total"] == len(sanas) + 1 and len(por_clave) == len(sanas) + 1
    assert all(por_clave[k] == v for k, v in sanas.items())
    item = por_clave[original.identificador]
    assert item["juego"] == original.juego and item["linea"] == original.linea
    assert item["objetivo"] == original.objetivo
    return item


@pytest.mark.parametrize("juego", ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"))
@pytest.mark.parametrize("defecto", ("corte_ausente", "nombre_ausente"))
def test_ausencia_de_metadatos_no_bloquea_carteras_sanas(copia, juego, defecto):
    original, _, listado, ficha, sanas = _consultar_defecto(copia, juego, defecto)
    item = _assert_listado_mixto(listado, original, sanas)
    if defecto == "nombre_ausente":
        assert item["estado"] == "disponible" and item["nombre"] is None
        assert ficha.status_code == 200, ficha.text
        eg.FichaCarteraGuardada.model_validate(ficha.json())
        assert ficha.json()["cartera"]["nombre"] is None
        assert ficha.json()["cartera"]["clave"] == original.identificador
        assert ficha.json()["cartera"]["corte"] == original.artefacto["datos"]["corte"]
    else:
        assert item["estado"] == "alterado" and item["corte"] is None
        assert item["modelo"] is None and item["nombre"] is None
        assert ficha.status_code == 409 and ficha.json()["error"]["codigo"] == "alterado"


@pytest.mark.parametrize("defecto", ("corte_texto", "corte_booleano", "nombre_tipo_no_valido", "fecha_tipo_no_valido"))
def test_tipo_de_metadato_no_valido_no_se_coacciona_ni_bloquea_el_listado(copia, defecto):
    original, _, listado, ficha, sanas = _consultar_defecto(copia, "MILOTO", defecto)
    item = _assert_listado_mixto(listado, original, sanas)
    assert item["estado"] == "alterado"
    assert item["corte"] is None and item["nombre"] is None
    assert ficha.status_code == 409 and ficha.json()["error"]["codigo"] == "alterado"


@pytest.mark.parametrize("defecto", ("sha_historico_ausente", "sha_historico_tipo_no_valido", "clasificacion_tipo_no_valido", "combinacion_tipo_no_valido"))
def test_contexto_necesario_de_la_ficha_incompleto_tiene_estado_explicito(copia, defecto):
    original, _, listado, ficha, sanas = _consultar_defecto(copia, "MILOTO", defecto)
    item = _assert_listado_mixto(listado, original, sanas)
    assert item["estado"] == "alterado"
    assert ficha.status_code == 409 and ficha.json()["error"]["codigo"] == "alterado"


@pytest.mark.parametrize("defecto", ("nombre_unicode", "fecha_ausente"))
def test_opcionales_y_texto_historico_valido_se_conservan(copia, defecto):
    original, recompuesto, listado, ficha, sanas = _consultar_defecto(copia, "COLORLOTO", defecto)
    item = _assert_listado_mixto(listado, original, sanas)
    assert item["estado"] == "disponible" and ficha.status_code == 200
    eg.FichaCarteraGuardada.model_validate(ficha.json())
    assert item["nombre"] == recompuesto["modelo"]["nombre"]
    assert item["generado_en"] == recompuesto["generacion"].get("generado_en")


@pytest.mark.parametrize("metodo,error,esperado,codigo", (
    ("lineas", OSError, 503, "no_disponible"),
    ("lineas", KeyError, 500, "error_interno"),
    ("carteras_de_linea", RuntimeError, 500, "error_interno"),
    ("obtener_cartera", OSError, 503, "no_disponible"),
    ("obtener_cartera", KeyError, 500, "error_interno"),
))
def test_errores_ajenos_a_metadatos_conservan_su_semantica(copia, monkeypatch, metodo, error, esperado, codigo):
    e4, cu, api, llamadas = copia
    clave = next(cu._carteras.carteras_de_linea("MILOTO", linea)[0].identificador
                 for linea in cu._carteras.lineas("MILOTO"))
    url = "/api/v1/juegos/MILOTO/carteras-guardadas"
    if metodo == "obtener_cartera":
        objeto = cu._carteras._almacen
        url += "/" + clave
    else:
        objeto = cu._carteras
    def falla(*args, **kwargs):
        raise error("f94-error-ajeno-de-prueba")
    monkeypatch.setattr(objeto, metodo, falla)
    antes, filas = f4.arbol(e4.raiz), fa.filas(api.entorno)
    r = api.cliente(raise_server_exceptions=False).get(url, headers=api.cabeceras())
    assert r.status_code == esperado and r.json()["error"]["codigo"] == codigo
    assert "f94-error-ajeno-de-prueba" not in r.text
    assert r.headers["cache-control"] == "no-store" and r.headers["x-request-id"]
    assert llamadas == [] and f4.arbol(e4.raiz) == antes and fa.filas(api.entorno) == filas
