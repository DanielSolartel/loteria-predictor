"""Fase 9.4: GET públicos sobre lectores reales y almacenes SINTÉTICOS.

La preparación compartida publica versiones y carteras reales una sola vez.
Las consultas se contrastan con los lectores de Fase 3 / Productos 5 y 6;
después de preparar se prohíben escrituras, ajustes, inferencias y trabajadores.
No se consulta PostgreSQL ni un almacén operativo.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import re
import shutil
import tempfile
from pathlib import Path, PureWindowsPath

import pytest

from app.api.publica import aplicacion
from app.api.publica import dependencias as d
from app.api.publica import esquemas_guardados as eg
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import carteras_artefactos as ca
from app.application.ml import modelos_registrados as mr
from app.application.ml import resultados_procedencias as rp
from app.application.use_cases.carteras import CarterasDeModelos
from app.application.use_cases.consultas_guardadas import ConsultasGuardadas
from app.application.use_cases.laboratorio import LaboratorioDeModelos
from app.application.use_cases.predicciones import CentroDePredicciones
from app.application.use_cases.resultados import CentroDeResultados, Filtros
from app.core.config import get_settings
from app.infrastructure.db import session as db_session
from app.infrastructure.storage.carteras_file_store import CarterasFileStore
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from app.infrastructure.storage.predicciones_file_store import PrediccionesFileStore
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from app.infrastructure.storage.resultados_file_store import ResultadosFileStore
from tests import fase94_api_sintetica as f94
from tests.unit import fixtures_fase4 as f4
from tests.unit.api_publica import fixtures_api_publica as fa

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
GRUPOS = ("modelos-guardados", "carteras-guardadas", "resultados")


@pytest.fixture(scope="module")
def escenario():
    # Almacenes propios bajo TEMP, sin los niveles y nombres de casos de
    # pytest. TEMP/TMP y la configuración de pytest permanecen intactos.
    with tempfile.TemporaryDirectory(prefix="s ") as temporal:
        raiz = Path(temporal)
        datos = f94.preparar(raiz / "a")
        conf, claves = fa.configuracion("pruebas", fichas_por_minuto=100_000)
        app = f94.crear(raiz / "a", configuracion=conf, preparada=datos)
        try:
            yield datos, fa.Api(app, claves, datos["e7"])
        finally:
            datos["e7"].engine.dispose()


@pytest.fixture
def raiz_copia_corta():
    with tempfile.TemporaryDirectory(prefix="c ") as temporal:
        yield Path(temporal)


def _url(juego: str, grupo: str, clave: str | None = None) -> str:
    return f"/api/v1/juegos/{juego}/{grupo}" + (f"/{clave}" if clave else "")


def _copia(escenario, tmp_path):
    datos, a = escenario
    e4 = datos["e4"]
    destino = tmp_path
    assert not any(destino.iterdir()), "La copia requiere una raíz propia vacía"
    shutil.copytree(e4.raiz, destino, dirs_exist_ok=True)
    otro = dataclasses.replace(e4, directorio=destino / e4.directorio.relative_to(e4.raiz))
    cu = ConsultasGuardadas(otro.almacen_laboratorio, otro.carteras(), otro.centro_de_resultados())
    return otro, cu, a


@pytest.mark.parametrize("juego", JUEGOS)
def test_modelos_son_versiones_publicadas_no_catalogo_de_candidatos(escenario, juego):
    datos, a = escenario
    r = a.get(_url(juego, "modelos-guardados"))
    assert r.status_code == 200, r.text
    salida = r.json()
    reales = datos["e4"].almacen_laboratorio.modelos(juego)
    assert salida["total"] == len(reales) and salida["juego"] == juego
    assert {v["clave"] for v in salida["elementos"]} == {g.identificador for g in reales}
    assert len(salida["elementos"]) < len(lm.candidatos_del_juego(juego))
    assert all(v["estado"] == "disponible" for v in salida["elementos"])
    for item in salida["elementos"]:
        guardado = next(g for g in reales if g.identificador == item["clave"])
        resumen = mr.resumen(guardado.artefacto)
        assert (item["modelo"], item["numero"], item["corte"], item["perfil"], item["linea"]) == (
            resumen["modelo"], resumen["numero"], resumen["corte"], resumen["perfil"], resumen["linea"])
        assert item["familia"] == guardado.artefacto["identidad"]["modelo"]["familia"]


@pytest.mark.parametrize("juego", JUEGOS)
def test_ficha_modelo_conserva_identidad_y_corte_de_entrenamiento(escenario, juego):
    datos, a = escenario
    g = datos["modelos"][juego][0]
    r = a.get(_url(juego, "modelos-guardados", g.identificador))
    assert r.status_code == 200, r.text
    f = r.json()
    original = g.artefacto
    assert f["modelo"]["clave"] == original["clave"] and f["modelo"]["numero"] == g.numero
    assert f["modelo"]["corte"] == original["identidad"]["corte"]
    assert f["modelo"]["corte"] < datos["e4"].cargados(juego)[-1].numero_sorteo
    assert f["periodo"] == original["identidad"]["periodo"]
    assert f["variables"] == original["identidad"]["variables"]["nombres"]
    assert f["sha256_historico"] == original["datos"]["sha256_historico"]
    assert f["experimento"] == original["procedencia"]["experimento"]
    assert f["estado_de_uso"] == "experimental_no_acreditado"
    assert not ({"estimador", "componentes", "identidad", "publicacion", "sello"} & set(f))


def test_modelos_paginados_y_filtrados_sin_confundir_versiones(escenario):
    datos, a = escenario
    base = _url("BALOTO", "modelos-guardados")
    uno, dos = (a.get(base, params={"pagina": p, "por_pagina": 1}).json() for p in (1, 2))
    assert uno["total"] == dos["total"] == 2 and uno["paginas"] == dos["paginas"] == 2
    assert uno["elementos"][0]["clave"] != dos["elementos"][0]["clave"]
    modelo = datos["modelos"]["BALOTO"][0].modelo
    filtrado = a.get(base, params={"modelo": modelo, "perfil": "reducido"}).json()
    assert filtrado["total"] == 2 and all(x["modelo"] == modelo for x in filtrado["elementos"])
    vacio = a.get(base, params={"modelo": "modelo_no_registrado"})
    assert vacio.status_code == 200 and vacio.json()["elementos"] == []


@pytest.mark.parametrize("juego", JUEGOS)
def test_carteras_y_fichas_son_las_guardadas_por_producto5(escenario, juego):
    datos, a = escenario
    s = datos["e4"].carteras()
    reales = [g for linea in s.lineas(juego) for g in s.carteras_de_linea(juego, linea)]
    r = a.get(_url(juego, "carteras-guardadas"))
    assert r.status_code == 200, r.text
    listado = r.json()
    assert listado["total"] == len(reales) and listado["lineas"] == sorted(s.lineas(juego))
    assert {x["clave"] for x in listado["elementos"]} == {g.identificador for g in reales}
    for item in listado["elementos"]:
        g = s.cartera(item["clave"])
        artefacto = g.artefacto
        ficha = a.get(_url(juego, "carteras-guardadas", item["clave"]))
        assert ficha.status_code == 200, ficha.text
        f = ficha.json()
        assert f["cartera"]["clave"] == g.identificador and f["cartera"]["linea"] == g.linea
        assert f["cartera"]["objetivo"] == g.objetivo and f["cartera"]["corte"] == artefacto["datos"]["corte"]
        registrado = artefacto["identidad"]["modelo"].get("registrado")
        assert f["cartera"]["registrado"] == (None if registrado is None else {
            "clave": registrado["clave"], "numero": registrado["numero"]})
        assert f["sha256_historico"] == artefacto["datos"]["sha256_historico"]
        assert f["parametros"]["semilla"] == artefacto["identidad"]["cartera"]["semilla"]
        assert len(f["combinaciones"]) == f["cartera"]["cantidad"]
        assert f["combinaciones"] == [{
            "linea": c["linea"], "origen": c["origen"], "numeros": c.get("numeros", []),
            "superbalota": c.get("superbalota"),
            "pares": [{"numero": p[0], "color": p[1]} for p in c.get("pares", [])],
        } for c in artefacto["cartera"]["combinaciones"]]
        for combinacion in f["combinaciones"]:
            if juego == "COLORLOTO":
                assert combinacion["numeros"] == [] and combinacion["superbalota"] is None
                assert len(combinacion["pares"]) == 6
                assert all(isinstance(p["numero"], int) and p["color"] for p in combinacion["pares"])
            else:
                assert len(combinacion["numeros"]) == 5 and combinacion["pares"] == []
                assert (combinacion["superbalota"] is not None) == (juego != "MILOTO")


@pytest.mark.parametrize("juego", JUEGOS)
def test_carteras_filtran_objetivo_linea_y_paginan(escenario, juego):
    _, a = escenario
    base = _url(juego, "carteras-guardadas")
    todo = a.get(base).json()
    filas = todo["elementos"]
    assert len(filas) >= 2
    objetivo = min(f["objetivo"] for f in filas)
    linea = filas[0]["linea"]
    f = a.get(base, params={"linea": linea, "desde": objetivo, "hasta": objetivo,
                            "por_pagina": 1, "pagina": 1})
    assert f.status_code == 200, f.text
    assert all(x["linea"] == linea and x["objetivo"] == objetivo for x in f.json()["elementos"])
    assert f.json()["total"] == sum(x["linea"] == linea and x["objetivo"] == objetivo for x in filas)
    assert a.get(base, params={"desde": max(x["objetivo"] for x in filas) + 1}).json()["elementos"] == []


@pytest.mark.parametrize("juego", JUEGOS)
def test_resultados_paginacion_filtros_y_cifras_salen_del_centro_existente(escenario, juego):
    datos, a = escenario
    centro = datos["e4"].centro_de_resultados()
    fuente = centro.consultar(juego, Filtros(procedencias=("carteras",)), pagina=1, por_pagina=1)
    r = a.get(_url(juego, "resultados"), params={"procedencia": "carteras", "por_pagina": 1})
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["historial"]["total"] == fuente["historial"]["total"]
    assert (f["historial"]["pagina"], f["historial"]["paginas"], f["historial"]["por_pagina"]) == (
        fuente["historial"]["pagina"], fuente["historial"]["paginas"], fuente["historial"]["por_pagina"])
    assert f["seleccion"] == fuente["seleccion"]
    # La proyección pública omite la serie de las gráficas y añade opcionales
    # nulos del contrato; todas las cifras publicadas siguen siendo las reales.
    assert f["resumenes"] == {k: eg.ResumenResultadoGuardado.model_validate(v).model_dump(mode="json")
                              for k, v in fuente["resumenes"].items()}
    assert f["comparacion"] == eg.ComparacionResultadosGuardados.model_validate(fuente["comparacion"]).model_dump(mode="json")
    assert f["politica"] == fuente["politica"] and f["nota_seguimiento"] == fuente["nota_seguimiento"]
    assert f["unidades"] == fuente["unidades"]
    for x, y in zip(f["historial"]["filas"], fuente["historial"]["filas"]):
        for campo in ("identificador", "tipo", "objetivo", "integridad", "historico", "resultado_estado",
                      "estado", "aciertos", "de", "metricas", "superbalota"):
            assert x[campo] == y[campo], campo
        motivo = y.get("motivo")
        if motivo is None or re.fullmatch(r"[a-z0-9_:]+", motivo):
            assert x["motivo"] == motivo
        else:
            assert x["motivo"] == "emision_no_admitida; consulte los estados de integridad, histórico y resultado"
    linea = f["seleccion"][0]
    detalle = a.get(_url(juego, "resultados"), params={"procedencia": "carteras", "linea": linea,
                                                      "objetivo": fuente["historial"]["filas"][0]["objetivo"]})
    assert detalle.status_code == 200
    assert detalle.json()["seleccion"] == [linea]
    assert all(x["clave_linea"] == linea for x in detalle.json()["historial"]["filas"])


@pytest.mark.parametrize("juego", JUEGOS)
def test_resultado_pendiente_no_es_cero_y_corte_no_acredita_anterioridad(escenario, juego):
    _, a = escenario
    f = a.get(_url(juego, "resultados"), params={"procedencia": "carteras"}).json()
    pendientes = [x for x in f["historial"]["filas"] if x["estado"] == "pendiente"]
    assert pendientes
    assert all(x["resultado_estado"] == "pendiente" and x["aciertos"] is None and x["metricas"] is None
               and x["resultado"] is None for x in pendientes)
    assert "anterioridad" in f["nota"].lower() or "disponibilidad" in f["nota"].lower()


@pytest.mark.parametrize("tipo", ["seguimiento", "retrospectiva"])
def test_emision_legacy_sin_clasificacion_se_conserva_excluida_en_ambas_vistas(escenario, raiz_copia_corta, monkeypatch, tipo):
    e4, cu, a = _copia(escenario, raiz_copia_corta)
    original = escenario[0]["carteras"]["MILOTO"][0]
    ruta = next((e4.raiz / "carteras").rglob("*" + original.identificador + ".json"))
    artefacto = copy.deepcopy(original.artefacto)
    generacion = {k: v for k, v in artefacto["generacion"].items() if k != "clasificacion_temporal"}
    legacy = ca.componer(ca.cuerpo_de(artefacto), "generacion", generacion)
    ruta.write_bytes(ca.json_canonico(legacy))
    assert ca.integro(legacy)
    assert e4.carteras().cartera(original.identificador).artefacto == legacy
    filtros = Filtros(procedencias=("carteras",), tipo=tipo, objetivo=original.objetivo)
    fuente = cu._resultados.consultar("MILOTO", filtros)
    assert len(fuente["historial"]["filas"]) == 1
    esperada = fuente["historial"]["filas"][0]
    assert esperada["tipo"] == "sin_clasificacion" and esperada["estado"] == "excluido"
    llamadas = _bloquear(monkeypatch)
    antes = f4.arbol(e4.raiz)
    a.app.dependency_overrides[d.consultas_guardadas] = lambda: cu
    try:
        r = a.get(_url("MILOTO", "resultados"), params={"procedencia": "carteras", "tipo": tipo,
                                                       "objetivo": original.objetivo})
        assert r.status_code == 200
        f = r.json()
        assert len(f["historial"]["filas"]) == 1
        fila = f["historial"]["filas"][0]
        assert fila["tipo"] == "sin_clasificacion" and fila["estado"] == "excluido"
        assert fila["motivo"] == esperada["motivo"] == "sin_clasificacion_temporal_al_generar"
        assert fila["metricas"] is None and fila["superbalota"] is None
        assert f["resumenes"][fila["clave_linea"]]["incluidos"] == 0
        assert f["resumenes"][fila["clave_linea"]]["excluidos"] == 1
        assert f4.arbol(e4.raiz) == antes and llamadas == []
    finally:
        a.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


@pytest.mark.parametrize("grupo", ("modelos-guardados", "carteras-guardadas"))
def test_identidad_existente_de_otro_juego_es_rechazada(escenario, grupo):
    datos, a = escenario
    clave = datos["modelos" if grupo == "modelos-guardados" else "carteras"]["BALOTO"][0].identificador
    r = a.get(_url("MILOTO", grupo, clave))
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "no_encontrado"


@pytest.mark.parametrize("grupo", ("modelos-guardados", "carteras-guardadas"))
@pytest.mark.parametrize("clave", ["0" * 64, "f" * 64])
def test_identidad_ausente_es_estado_explicito(escenario, grupo, clave):
    _, a = escenario
    r = a.get(_url("BALOTO", grupo, clave))
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "no_encontrado"


@pytest.mark.parametrize("grupo", GRUPOS)
@pytest.mark.parametrize("parametros", [{"pagina": 0}, {"pagina": 10001}, {"por_pagina": 0},
                                        {"por_pagina": 101}, {"pagina": "abc"}])
def test_paginacion_no_valida_se_rechaza(escenario, grupo, parametros):
    _, a = escenario
    r = a.get(_url("BALOTO", grupo), params=parametros)
    assert r.status_code == 422 and r.json()["error"]["codigo"] == "parametro_no_valido"


@pytest.mark.parametrize("grupo,parametros", [
    ("modelos-guardados", {"perfil": "inventado"}),
    ("modelos-guardados", {"modelo": "../secreto"}),
    ("carteras-guardadas", {"desde": 10, "hasta": 1}),
    ("carteras-guardadas", {"desde": 0}),
    ("carteras-guardadas", {"linea": "../secreto"}),
    ("resultados", {"tipo": "simulacion"}),
    ("resultados", {"procedencia": "inventada"}),
    ("resultados", {"desde": 10, "hasta": 1}),
    ("resultados", {"objetivo": 0}),
    ("resultados", {"linea": "carteras:otra-linea"}),
])
def test_filtros_no_validos_no_se_interpretan_como_consultas_amplias(escenario, grupo, parametros):
    _, a = escenario
    r = a.get(_url("BALOTO", grupo), params=parametros)
    assert r.status_code == 422 and r.json()["error"]["codigo"] in ("parametro_no_valido", "no_valido")


@pytest.mark.parametrize("grupo", GRUPOS)
def test_juego_desconocido_es_404(escenario, grupo):
    _, a = escenario
    r = a.get(_url("QUINIELA", grupo))
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "no_encontrado"


@pytest.mark.parametrize("grupo", ("modelos-guardados", "carteras-guardadas"))
@pytest.mark.parametrize("clave", ["abc", "A" * 64, "g" * 64, "1" * 65])
def test_clave_no_canonica_es_422(escenario, grupo, clave):
    _, a = escenario
    r = a.get(_url("BALOTO", grupo, clave))
    assert r.status_code == 422 and r.json()["error"]["codigo"] == "parametro_no_valido"


def test_artefactos_alterados_se_informan_sin_repararlos(escenario, raiz_copia_corta):
    e4, cu, a = _copia(escenario, raiz_copia_corta)
    originales = {}
    for patron in ("modelos/BALOTO/*.json", "carteras/BALOTO/**/*.json"):
        # Los almacenes están separados: se busca el modelo y una cartera publicada.
        raiz = e4.directorio if patron.startswith("modelos") else e4.raiz / "carteras"
        ruta = next(raiz.glob(patron))
        originales[ruta] = ruta.read_bytes()
        ruta.write_bytes(originales[ruta] + b" ")
    antes = f4.arbol(e4.raiz)
    a.app.dependency_overrides[d.consultas_guardadas] = lambda: cu
    try:
        for grupo in ("modelos-guardados", "carteras-guardadas"):
            r = a.get(_url("BALOTO", grupo))
            assert r.status_code == 200
            alterado = next(x for x in r.json()["elementos"] if x["estado"] == "alterado")
            ficha = a.get(_url("BALOTO", grupo, alterado["clave"]))
            assert ficha.status_code == 409 and ficha.json()["error"]["codigo"] == "alterado"
        assert f4.arbol(e4.raiz) == antes
    finally:
        a.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


def test_modelo_incompatible_canonico_con_huellas_validas_no_se_deserializa(escenario, raiz_copia_corta, monkeypatch):
    e4, cu, a = _copia(escenario, raiz_copia_corta)
    store = e4.almacen_laboratorio
    g = store.modelos("MILOTO")[0]
    contenido = store.leer_estimador(g)
    cuerpo = copy.deepcopy(mr.cuerpo_de(g.artefacto))
    cuerpo["identidad"]["entorno"]["scikit-learn"] = "0.0.0"
    cuerpo["clave"] = mr.huella(cuerpo["identidad"])
    artefacto = mr.componer(cuerpo, {"terminado_en": "2026-10-27T00:00:00+00:00"})
    nuevo = store.guardar_modelo(artefacto, contenido)
    assert mr.integro(nuevo.artefacto) and mr.compatibilidad(nuevo.artefacto)["compatible"] is False
    monkeypatch.setattr(mr, "cargar_estimador", lambda *a, **k: pytest.fail("GET no carga un estimador"))
    monkeypatch.setattr(mr, "deserializar_estimador", lambda *a, **k: pytest.fail("GET no deserializa"))
    antes = f4.arbol(e4.raiz)
    a.app.dependency_overrides[d.consultas_guardadas] = lambda: cu
    try:
        r = a.get(_url("MILOTO", "modelos-guardados", nuevo.identificador))
        assert r.status_code == 200 and r.json()["modelo"]["estado"] == "incompatible"
        listado = a.get(_url("MILOTO", "modelos-guardados")).json()["elementos"]
        assert next(x for x in listado if x["clave"] == nuevo.identificador)["estado"] == "incompatible"
        assert f4.arbol(e4.raiz) == antes
    finally:
        a.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


def test_estimador_ausente_no_es_un_modelo_disponible_ni_se_reconstruye(escenario, raiz_copia_corta, monkeypatch):
    e4, cu, a = _copia(escenario, raiz_copia_corta)
    g = e4.almacen_laboratorio.modelos("MILOTO")[0]
    estimador = next((e4.directorio / "modelos" / "MILOTO" / "estimadores").glob(
        g.artefacto["estimador"]["sha256"] + ".*"))
    estimador.unlink()
    antes = f4.arbol(e4.raiz)
    llamadas = _bloquear(monkeypatch)
    a.app.dependency_overrides[d.consultas_guardadas] = lambda: cu
    try:
        listado = a.get(_url("MILOTO", "modelos-guardados"))
        assert listado.status_code == 200
        item = next(x for x in listado.json()["elementos"] if x["clave"] == g.identificador)
        assert item["estado"] == "alterado"
        assert a.get(_url("MILOTO", "modelos-guardados", g.identificador)).status_code == 409
        assert not estimador.exists() and f4.arbol(e4.raiz) == antes and llamadas == []
    finally:
        a.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


@pytest.mark.parametrize("defecto", ["familia_ausente", "familia_tipo_no_valido"])
def test_manifiesto_canonico_sin_metadatos_necesarios_tiene_estado_explicito(escenario, raiz_copia_corta, monkeypatch, defecto):
    e4, cu, a = _copia(escenario, raiz_copia_corta)
    store = e4.almacen_laboratorio
    original = store.modelos("MILOTO")[0]
    cuerpo = copy.deepcopy(mr.cuerpo_de(original.artefacto))
    if defecto == "familia_ausente":
        del cuerpo["identidad"]["modelo"]["familia"]
    else:
        cuerpo["identidad"]["modelo"]["familia"] = []
    cuerpo["clave"] = mr.huella(cuerpo["identidad"])
    incompleto = store.guardar_modelo(mr.componer(cuerpo, {}), store.leer_estimador(original))
    # El lector real acredita canon, reserva y bytes, no la completitud de la
    # proyección nueva. Esta ausencia no debe convertirse en un error 500.
    assert mr.integro(incompleto.artefacto)
    assert store.obtener_modelo(incompleto.identificador).identificador == incompleto.identificador
    llamadas = _bloquear(monkeypatch)
    antes = f4.arbol(e4.raiz)
    a.app.dependency_overrides[d.consultas_guardadas] = lambda: cu
    try:
        cliente = a.cliente(raise_server_exceptions=False)
        listado = cliente.get(_url("MILOTO", "modelos-guardados"), headers=a.cabeceras())
        assert listado.status_code == 200
        item = next(f for f in listado.json()["elementos"] if f["clave"] == incompleto.identificador)
        assert item["estado"] == "alterado" and item["motivo"] == "artefacto_alterado_o_incompleto"
        ficha = cliente.get(_url("MILOTO", "modelos-guardados", incompleto.identificador), headers=a.cabeceras())
        assert ficha.status_code == 409 and ficha.json()["error"]["codigo"] == "alterado"
        assert f4.arbol(e4.raiz) == antes and llamadas == []
    finally:
        a.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


def test_cartera_historica_no_se_reetiqueta_al_cambiar_configuracion(escenario, raiz_copia_corta, monkeypatch):
    e4, cu, a = _copia(escenario, raiz_copia_corta)
    clave = escenario[0]["carteras"]["MILOTO"][0].identificador
    a.app.dependency_overrides[d.consultas_guardadas] = lambda: cu
    try:
        anterior = a.get(_url("MILOTO", "carteras-guardadas", clave))
        assert anterior.status_code == 200 and anterior.json()["cartera"]["registrado"] is not None
        e4.configurar("MILOTO", "uniforme", cantidad=7, semilla=1)
        archivos = f4.arbol(e4.raiz)
        llamadas = _bloquear(monkeypatch)
        posterior = a.get(_url("MILOTO", "carteras-guardadas", clave))
        assert posterior.status_code == 200 and posterior.json() == anterior.json()
        assert posterior.json()["cartera"]["modelo"] != "uniforme"
        assert posterior.json()["parametros"]["cantidad"] != 7
        assert posterior.json()["parametros"]["semilla"] != 1
        assert f4.arbol(e4.raiz) == archivos and llamadas == []
    finally:
        a.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


def test_linea_real_de_mas_de_80_caracteres_se_puede_filtrar(escenario, raiz_copia_corta):
    e4, cu, a = _copia(escenario, raiz_copia_corta)
    resultado = e4.carteras().ahora("cartera", ["COLORLOTO"], {
        "modelo": "actual_multinomial_suavizada", "perfil": "reducido", "cantidad": 20,
        "diversidad": "limitada", "semilla": 4294967295,
    })["juegos"]["COLORLOTO"]
    assert resultado["estado"] == "terminado", resultado
    g = e4.carteras().cartera(resultado["resultado"])
    assert len(g.linea) > 80
    a.app.dependency_overrides[d.consultas_guardadas] = lambda: cu
    try:
        r = a.get(_url("COLORLOTO", "carteras-guardadas"), params={"linea": g.linea})
        assert r.status_code == 200 and r.json()["total"] == 1
        assert r.json()["elementos"][0]["clave"] == g.identificador
        # La línea de una cartera incluye cantidad, diversidad y semilla. El
        # lector de Producto 6 agrupa su vector por la identidad del MODELO;
        # confundir ambas identidades no debe ampliar silenciosamente el filtro.
        r = a.get(_url("COLORLOTO", "resultados"), params={"linea": "carteras:" + g.linea})
        assert r.status_code == 422 and r.json()["error"]["codigo"] == "no_valido"
        linea_del_vector = rp.clave_de_linea("carteras", rp.linea_de_modelo_de_cartera(g.artefacto)["id"])
        r = a.get(_url("COLORLOTO", "resultados"), params={"linea": linea_del_vector})
        assert r.status_code == 200 and r.json()["seleccion"] == [linea_del_vector]
        assert all(f["clave_linea"] == linea_del_vector for f in r.json()["historial"]["filas"])
    finally:
        a.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


def test_presupuesto_portable_de_almacenes_y_copias(escenario, raiz_copia_corta):
    """Aritmética de rutas reales; no equivale a una ejecución en Windows."""
    datos, _ = escenario
    e4, _, _ = _copia(escenario, raiz_copia_corta)
    # La línea más larga del caso anterior se produce con el constructor real.
    linea = ca.linea_de("COLORLOTO", "actual_multinomial_suavizada", "reducido", 20,
                        "limitada", 4294967295)["id"]
    referencia = PureWindowsPath("C:/Users/operador.local/AppData/Local/Temp")
    colecciones = [(datos["e4"].raiz.parent.parent, "s abcdefgh"),
                   (raiz_copia_corta, "c abcdefgh")]
    for origen, nombre in colecciones:
        rutas = [p.relative_to(origen) for p in origen.rglob("*") if p.is_file()]
        assert rutas
        longitudes = [len(str(referencia / nombre / PureWindowsPath(*r.parts))) for r in rutas]
        assert max(longitudes) <= 259, (nombre, max(longitudes))
    representativa = (referencia / "c abcdefgh" / "carteras" / "carteras" /
                      "COLORLOTO" / linea / ("99999999999999999999-" + "a" * 64 + ".json"))
    assert len(str(representativa)) <= 259
    assert " " in str(representativa)


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize("grupo", GRUPOS)
def test_rutas_nuevas_no_ofrecen_operaciones_de_escritura(escenario, metodo, grupo):
    _, a = escenario
    r = getattr(a.cliente(), metodo)(_url("MILOTO", grupo), headers=a.cabeceras())
    assert r.status_code == 405 and r.headers["allow"] == "GET"
    assert r.json()["error"]["codigo"] == "metodo_no_permitido"


def test_base_caida_conserva_guardados_y_no_inventa_observaciones(escenario):
    datos, a = escenario
    datos["e4"].base_caida = True
    try:
        for juego in JUEGOS:
            assert a.get(_url(juego, "modelos-guardados")).status_code == 200
            assert a.get(_url(juego, "carteras-guardadas")).status_code == 200
            r = a.get(_url(juego, "resultados"))
            assert r.status_code == 200, r.text
            f = r.json()
            assert f["base"]["estado"] == "no_disponible" and f["base"]["ultimo_sorteo"] is None
            assert all(x["estado"] == "sin_base" and x["resultado_estado"] == "sin_base" and x["aciertos"] is None
                       and x["metricas"] is None for x in f["historial"]["filas"])
            assert "connection to server" not in r.text and "Connection refused" not in r.text
    finally:
        datos["e4"].base_caida = False


def test_error_de_una_procedencia_no_expone_detalles_internos(escenario, monkeypatch):
    datos, a = escenario
    def falla(*args):
        raise OSError("/home/operador/secreto/.env postgresql://usuario:clave@host/real")
    monkeypatch.setattr(datos["guardados"]._resultados._carteras, "lineas", falla)
    r = a.get(_url("MILOTO", "resultados"))
    assert r.status_code == 200
    procedencia = r.json()["procedencias"]["carteras"]
    assert procedencia["estado"] == "error" and procedencia["error"] == "No se pudo leer esta procedencia"
    assert "secreto" not in r.text and "postgresql" not in r.text and "Traceback" not in r.text


def test_filas_y_proyeccion_no_publican_cargas_ejecutables_ni_rutas(escenario, monkeypatch):
    datos, a = escenario
    centro = datos["guardados"]._resultados
    original = centro.consultar
    def con_detalle_interno(*args, **kwargs):
        vista = original(*args, **kwargs)
        vista["historial"]["filas"][0]["motivo"] = "/home/operador/secreto/.env postgresql://usuario:clave@host/real"
        return vista
    monkeypatch.setattr(centro, "consultar", con_detalle_interno)
    r = a.get(_url("MILOTO", "resultados"))
    assert r.status_code == 200
    assert r.json()["historial"]["filas"][0]["motivo"] == \
        "emision_no_admitida; consulte los estados de integridad, histórico y resultado"
    assert "secreto" not in r.text and "postgresql" not in r.text
    for juego in JUEGOS:
        for grupo in GRUPOS:
            respuesta = a.get(_url(juego, grupo))
            assert str(datos["e4"].raiz) not in respuesta.text
            if grupo == "resultados":
                continue
            for item in respuesta.json()["elementos"]:
                ficha = a.get(_url(juego, grupo, item["clave"]))
                texto = json.dumps(ficha.json())
                for clave in ("estimador", "componentes", "identidad", "sello", "contenido", "congelado"):
                    assert f'"{clave}":' not in texto


@pytest.mark.parametrize("grupo,coste", [("modelos-guardados", 2), ("carteras-guardadas", 2), ("resultados", 5)])
def test_autenticacion_cabeceras_y_coste_de_cada_consulta(escenario, grupo, coste):
    datos, _ = escenario
    capacidad = max(5, coste + 1)
    conf, claves = fa.configuracion("pruebas", fichas_por_minuto=capacidad)
    app = f94.crear(datos["e4"].raiz, configuracion=conf, preparada=datos)
    a = fa.Api(app, claves, datos["e7"])
    ruta = _url("MILOTO", grupo)
    assert a.cliente().get(ruta).status_code == 401
    catalogo = a.get("/api/v1/juegos")
    assert catalogo.status_code == 200
    r = a.get(ruta)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store" and r.headers["x-request-id"]
    assert int(r.headers["x-ratelimit-remaining"]) == capacidad - 1 - coste
    for _ in range(capacidad // coste + 1):
        limite = a.get(ruta)
        if limite.status_code == 429:
            break
    assert limite.status_code == 429 and int(limite.headers["retry-after"]) > 0
    assert limite.json()["error"]["codigo"] == "limite_excedido"


@pytest.mark.parametrize("grupo", GRUPOS)
def test_error_inesperado_del_proveedor_sanitizado(escenario, grupo):
    _, a = escenario
    def falla():
        raise OSError("/home/operador/secreto/.env postgresql://usuario:clave@host/real")
    a.app.dependency_overrides[d.consultas_guardadas] = falla
    try:
        r = a.cliente(raise_server_exceptions=False).get(_url("BALOTO", grupo), headers=a.cabeceras())
        assert r.status_code == 500 and r.json()["error"]["codigo"] == "error_interno"
        assert "secreto" not in r.text and "postgresql" not in r.text and "Traceback" not in r.text
    finally:
        a.app.dependency_overrides[d.consultas_guardadas] = lambda: escenario[0]["guardados"]


def _bloquear(monkeypatch):
    llamadas = []
    prohibidos = {
        CarterasDeModelos: ("iniciar", "ejecutar", "ahora", "recuperar", "abortar", "configurar"),
        LaboratorioDeModelos: ("iniciar", "ejecutar", "comparar_ahora", "entrenar_ahora", "generar", "generar_con_modelo"),
        CentroDePredicciones: ("iniciar", "ejecutar", "ahora", "explicar", "abortar"),
        CentroDeResultados: ("guardar_informe", "usar_configuracion"),
        mr: ("entrenar", "cargar_estimador", "deserializar_estimador", "predecir_congelado", "control_recargado"),
        lm: ("ajustar_candidato", "_ajustar"),
        CerrojoPorJuego: ("adquirir",),
    }
    for almacen in (LaboratorioFileStore, CarterasFileStore, ResultadosFileStore, PrediccionesFileStore,
                    PronosticoExperimentalFileStore, RegistroEjecucionesArchivo):
        prohibidos[almacen] = tuple(n for n in vars(almacen) if n.startswith("guardar") or n == "_publicar")
    for objeto, nombres in prohibidos.items():
        for nombre in nombres:
            if not hasattr(objeto, nombre):
                continue
            def no(*a, _nombre=f"{getattr(objeto, '__name__', type(objeto).__name__)}.{nombre}", **k):
                llamadas.append(_nombre)
                raise AssertionError(f"GET invocó {_nombre}")
            monkeypatch.setattr(objeto, nombre, no)
    return llamadas


def test_gets_no_escriben_entrenan_infieren_deserializan_ni_lanzan_trabajos(escenario, monkeypatch):
    datos, a = escenario
    antes = f4.arbol(datos["e4"].raiz), fa.arbol(datos["e7"].raiz), fa.filas(datos["e7"])
    llamadas = _bloquear(monkeypatch)
    for juego in JUEGOS:
        for grupo in GRUPOS:
            r = a.get(_url(juego, grupo))
            assert r.status_code == 200, (grupo, r.text)
            if grupo != "resultados":
                for item in r.json()["elementos"]:
                    assert a.get(_url(juego, grupo, item["clave"])).status_code == 200
        assert a.get(_url(juego, "resultados"), params={"tipo": "retrospectiva", "desde": 1}).status_code == 200
    assert llamadas == []
    assert (f4.arbol(datos["e4"].raiz), fa.arbol(datos["e7"].raiz), fa.filas(datos["e7"])) == antes


def test_proveedores_predeterminados_no_crean_almacenes_al_inicializar(tmp_path, monkeypatch):
    raiz = tmp_path / "almacenes"
    raiz.mkdir()
    for nombre in fa.DIRECTORIOS:
        monkeypatch.setenv(f"DIRECTORIO_{nombre}", str(raiz / nombre.lower()))
    get_settings.cache_clear()
    try:
        e7 = fa.f7.entorno(tmp_path / "datos")
        monkeypatch.setattr(db_session, "SessionLocal", e7.sesiones)
        llamadas = _bloquear(monkeypatch)
        conf, claves = fa.configuracion("pruebas", fichas_por_minuto=10_000)
        app = aplicacion.crear_app(conf)
        a = fa.Api(app, claves, e7)
        filas = fa.filas(e7)
        for juego in JUEGOS:
            for grupo in GRUPOS:
                r = a.get(_url(juego, grupo))
                assert r.status_code == 200, (grupo, r.text)
                if grupo != "resultados":
                    assert r.json()["total"] == 0 and r.json()["elementos"] == []
                else:
                    assert r.json()["historial"]["total"] == 0
        assert llamadas == [] and fa.filas(e7) == filas
        assert list(raiz.rglob("*")) == []
    finally:
        get_settings.cache_clear()
