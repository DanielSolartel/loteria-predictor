"""Fase 7 v2: regresiones de la auditoria de v1 (F1-F4) con datos sinteticos y
SQLite aislado. Sin hilos ni esperas: un punto de control determinista hace
que el trabajador escriba su cierre y suelte el cerrojo justo en el instante
que reproducian las sondas (entre la lectura del registro y la observacion
del cerrojo) o, en la recuperacion, mientras se toma el recurso.

- F1: una lectura antigua `en_curso` no se convierte en `interrumpida` si el
  trabajador ya cerro; con el trabajador vivo se sigue sondeando.
- F2: `recuperar` relee y valida bajo el cerrojo de la propia ejecucion y
  solo marca una interrupcion confirmada.
- F3: listado, panel, lectura individual y reutilizacion comprueban igual el
  `juego_id` de la fila frente al juego de su identidad.
- F4: tipos de `parametros`, `resultado_resumen` y `contenido` antes de
  usarlos; una fila alterada no derriba las demas ni se atribuye a la base."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from app.application.fase7 import artefacto as fa
from app.application.use_cases.simulaciones import SimulacionesError
from tests.unit.simulaciones import fixtures_fase7 as f7


@pytest.fixture
def e(tmp_path):
    entorno = f7.entorno(tmp_path, cargar=("MILOTO",))
    yield entorno
    f7.limpiar()
    entorno.engine.dispose()


def _cerrar_al_llamar(s, inicio, metodo="ejecucion_viva"):
    """La primera llamada a `metodo` del cerrojo ejecuta antes el trabajo
    completo (cierre persistido y cerrojos soltados) y despues la original."""
    original = getattr(s._cerrojo, metodo)
    control = {"final": None, "llamadas": 0}

    def punto_de_control(*a, **k):
        control["llamadas"] += 1
        if control["final"] is None:
            control["final"] = json.loads(json.dumps(s.ejecutar(inicio)))
        return original(*a, **k)
    setattr(s._cerrojo, metodo, punto_de_control)
    return control


def _codigo(lectura) -> str:
    try:
        lectura()
    except SimulacionesError as error:
        return error.codigo
    return "servida"


def _id_juego(e, codigo):
    with e.engine.connect() as c:
        return c.execute(text("SELECT id FROM juegos WHERE codigo = :c"), {"c": codigo}).scalar_one()


def _actualizar(e, ident, **columnas):
    asignaciones = ", ".join(f"{k} = :{k}" for k in columnas)
    valores = {k: (v if k == "juego_id" else json.dumps(v)) for k, v in columnas.items()}
    with e.engine.begin() as c:
        c.execute(text(f"UPDATE simulaciones SET {asignaciones} WHERE id = :i"), {**valores, "i": ident.hex})


def _fila(e, ident):
    return next(f for f in e.filas() if str(f["id"]) == ident)


def _resellar(parametros, resumen):
    """Recalcula clave y huellas como haria quien edita la fila a conciencia
    (las huellas no son una firma): solo la forma puede delatarla."""
    p = {k: v for k, v in parametros.items() if k != "clave"}
    p["clave"] = fa.sha256(p)
    r = {**resumen, "clave": p["clave"], "contenido_sha256": fa.sha256(resumen["contenido"])}
    cuerpo = {k: v for k, v in r.items() if k != "integridad_sha256"}
    r["integridad_sha256"] = fa.sha256({"parametros": p, "resultado": cuerpo})
    return p, r


# ---------------------------------------------------------------------------
# F1: lectura del progreso con cierre concurrente
# ---------------------------------------------------------------------------

def test_f1_consulta_con_cierre_tras_leer_el_registro_devuelve_el_cierre(e):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 1)
    control = _cerrar_al_llamar(s, inicio)
    vista = s.consultar_ejecucion(inicio.ejecucion["id"])
    final = control["final"]
    assert final["estado"] == "exito" and final["juegos"]["MILOTO"]["resultado"]
    assert vista["estado"] == "exito" and vista["juegos"]["MILOTO"] == final["juegos"]["MILOTO"]
    assert control["llamadas"] == 1  # la vida del trabajador se observa una sola vez


def test_f1_fragmento_web_tras_cierre_concurrente_ofrece_el_resultado(e):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 1)
    control = _cerrar_al_llamar(s, inicio)
    r = f7.cliente(e, servicio=s).get(f"/simulaciones/ejecuciones/{inicio.ejecucion['id']}/estado")
    resultado = control["final"]["juegos"]["MILOTO"]["resultado"]
    assert r.status_code == 200 and "Interrumpida." not in r.text and "Terminada." in r.text
    assert f'href="/simulaciones/resultados/{resultado}">abrir el resultado' in r.text
    assert len(e.filas()) == 1


def test_f1_recientes_con_cierre_concurrente_no_inventa_interrupcion(e):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 1)
    control = _cerrar_al_llamar(s, inicio)
    assert [x["estado"] for x in s.recientes()] == ["exito"]
    assert control["final"]["estado"] == "exito"


def test_f1_con_el_trabajador_vivo_se_sigue_sondeando(e):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 1)  # el trabajador mantiene sus cerrojos
    c = f7.cliente(e, servicio=s)
    url = f"/simulaciones/ejecuciones/{inicio.ejecucion['id']}/estado"
    vivo = c.get(url)
    assert "hx-get" in vivo.text and "Interrumpida." not in vivo.text
    s.ejecutar(inicio)
    cerrado = c.get(url)
    assert "hx-get" not in cerrado.text and "abrir el resultado" in cerrado.text


def test_f1_interrupcion_confirmada_tras_releer_y_sin_escribir(e):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 1)
    inicio.cerrojos.liberar()  # el trabajador murio sin escribir su cierre
    vista = s.consultar_ejecucion(inicio.ejecucion["id"])
    assert vista["estado"] == "interrumpida" and "No se publico nada parcial" in vista["mensaje"]
    assert s._registro.obtener(inicio.ejecucion["id"])["estado"] == "en_curso"  # la lectura no escribe


# ---------------------------------------------------------------------------
# F2: recuperacion bajo el recurso de la ejecucion
# ---------------------------------------------------------------------------

def test_f2_recuperar_no_sobrescribe_un_cierre_entre_lecturas(e):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 2)
    control = _cerrar_al_llamar(s, inicio)
    assert s.recuperar() == []
    persistida = s._registro.obtener(inicio.ejecucion["id"])
    assert control["final"]["estado"] == "exito"
    assert persistida == control["final"]  # cierre y referencia al resultado intactos
    assert len(e.filas()) == 1


def test_f2_recuperar_no_marca_una_ejecucion_cuyo_recurso_sigue_tomado(e):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 2)
    s._cerrojo.ejecucion_viva = lambda _identificador: False  # proyeccion antigua: la cree libre
    assert s.recuperar() == []
    assert s._registro.obtener(inicio.ejecucion["id"])["estado"] == "en_curso"
    final = s.ejecutar(inicio)
    assert final["estado"] == "exito" and s._registro.obtener(inicio.ejecucion["id"])["estado"] == "exito"


def test_f2_cierre_mientras_se_toma_el_recurso_se_conserva(e):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 2)
    s._cerrojo.ejecucion_viva = lambda _identificador: False
    control = _cerrar_al_llamar(s, inicio, "adquirir")
    assert s.recuperar() == []
    assert control["final"]["estado"] == "exito"
    assert s._registro.obtener(inicio.ejecucion["id"]) == control["final"]


def test_f2_recuperaciones_simultaneas_marcan_una_sola_vez(e):
    s, otra = e.servicio(), e.servicio()  # dos procesos sobre la misma carpeta
    inicio = s.iniciar("MILOTO", 100, 2)
    inicio.cerrojos.liberar()
    original, internas = s._registro.guardar, []

    def guardar(ejecucion):
        if not internas:  # la otra recuperacion llega mientras esta escribe
            internas.append(otra.recuperar())
        original(ejecucion)
    s._registro.guardar = guardar
    assert s.recuperar() == [inicio.ejecucion["id"]]
    assert internas == [[]]
    assert s._registro.obtener(inicio.ejecucion["id"])["estado"] == "interrumpida"


def test_f2_interrupcion_confirmada_se_marca_libera_el_recurso_y_no_toca_la_activa(e):
    s = e.servicio()
    muerta = s.iniciar("MILOTO", 100, 1)
    muerta.cerrojos.liberar()
    activa = s.iniciar("MILOTO", 100, 2)  # misma familia de juego, viva
    assert s.recuperar() == [muerta.ejecucion["id"]]
    g = s._registro.obtener(muerta.ejecucion["id"])
    assert g["estado"] == "interrumpida" and g["juegos"]["MILOTO"]["estado"] == "interrumpido" and g["finalizada_en"]
    assert not s._cerrojo.ejecucion_viva(muerta.ejecucion["id"])  # el recurso tomado para recuperar se suelta
    assert s._registro.obtener(activa.ejecucion["id"])["estado"] == "en_curso"
    assert s.recuperar() == []
    assert s.ejecutar(activa)["estado"] == "exito"


# ---------------------------------------------------------------------------
# F3: juego de la fila frente al de su identidad
# ---------------------------------------------------------------------------

def test_f3_listado_panel_y_lectura_marcan_la_fila_de_otro_juego(e):
    s = e.servicio()
    ident = s.ahora("MILOTO", 100, 3)["juegos"]["MILOTO"]["resultado"]
    _actualizar(e, _fila(e, ident)["id"], juego_id=_id_juego(e, "BALOTO"))
    for listado in (s.listar("BALOTO"), s.listar(), s.diagnostico("BALOTO")["simulaciones"]):
        assert [(x["id"], x["juego"], x["integridad"]) for x in listado] == [(ident, "BALOTO", "alterada")]
        assert "MILOTO" in listado[0]["motivo"] and listado[0]["alguna_supera_umbral_exploratorio"] is None
    assert s.listar("MILOTO") == []
    assert _codigo(lambda: s.obtener(ident)) == "alterado"


def test_f3_fila_alterada_no_expone_su_umbral_ni_su_identidad(e):
    s = e.servicio()
    ident = s.ahora("MILOTO", 100, 3)["juegos"]["MILOTO"]["resultado"]
    fila = _fila(e, ident)
    resumen = fila["resultado_resumen"]
    resumen["contenido"]["alguna_supera_umbral_exploratorio"] = True  # sin recalcular huellas
    _actualizar(e, fila["id"], resultado_resumen=resumen)
    x = s.listar("MILOTO")[0]
    assert x["integridad"] == "alterada" and x["alguna_supera_umbral_exploratorio"] is None
    assert x["clave"] is None and x["semilla"] is None and x["corte"] is None
    panel = f7.cliente(e, servicio=s).get("/simulaciones").text
    assert "alterada" in panel and "alguna supera" not in panel


# ---------------------------------------------------------------------------
# F4: tipos antes de acceder; sin derribar el panel ni culpar a la base
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("resumen", [[1], 7, "texto", True], ids=["lista", "entero", "texto", "booleano"])
def test_f4_resultado_que_no_es_objeto_no_derriba_listado_ni_panel(e, resumen):
    s = e.servicio()
    buena = s.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]["resultado"]
    mala = s.ahora("MILOTO", 100, 2)["juegos"]["MILOTO"]["resultado"]
    _actualizar(e, _fila(e, mala)["id"], resultado_resumen=resumen)
    listado = {x["id"]: x for x in s.listar("MILOTO")}
    assert listado[buena]["integridad"] == "verificada" and listado[mala]["integridad"] == "alterada"
    d = s.diagnostico("MILOTO")
    assert d["estado"] == "disponible" and len(d["simulaciones"]) == 2
    assert _codigo(lambda: s.obtener(mala)) == "alterado" and _codigo(lambda: s.obtener(buena)) == "servida"
    c = f7.cliente(e, servicio=s)
    assert c.get("/simulaciones").status_code == 200
    api = c.get("/api/simulaciones", params={"juego": "MILOTO"})
    assert api.status_code == 200 and len(api.json()["simulaciones"]) == 2
    assert c.get(f"/simulaciones/resultados/{mala}").status_code == 409


@pytest.mark.parametrize("contenido", [[1, 2], "texto", 3], ids=["lista", "texto", "entero"])
def test_f4_contenido_no_objeto_con_huellas_recalculadas(e, contenido):
    s = e.servicio()
    ident = s.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]["resultado"]
    fila = _fila(e, ident)
    parametros, resumen = _resellar(fila["parametros"], {**fila["resultado_resumen"], "contenido": contenido})
    with pytest.raises(fa.ArtefactoSimulacionError, match="contenido"):
        fa.verificar(parametros, resumen, 100)
    _actualizar(e, fila["id"], resultado_resumen=resumen)
    assert s.listar("MILOTO")[0]["integridad"] == "alterada"
    assert s.diagnostico("MILOTO")["estado"] == "disponible"
    assert _codigo(lambda: s.obtener(ident)) == "alterado"
    repetida = s.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]  # reutilizacion: misma comprobacion
    assert repetida["estado"] == "alterado" and len(e.filas()) == 1


@pytest.mark.parametrize("campo,valor", [("corte", "x"), ("semilla", [1]), ("historico", 5), ("algoritmo", "x")])
def test_f4_identidad_con_tipos_no_validos_se_marca_alterada(e, campo, valor):
    s = e.servicio()
    ident = s.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]["resultado"]
    fila = _fila(e, ident)
    parametros, resumen = _resellar({**fila["parametros"], campo: valor}, fila["resultado_resumen"])
    _actualizar(e, fila["id"], parametros=parametros, resultado_resumen=resumen)
    assert s.listar("MILOTO")[0]["integridad"] == "alterada"
    assert _codigo(lambda: s.obtener(ident)) == "alterado"
    assert _codigo(lambda: s.verificar(ident)) == "alterado"


@pytest.mark.parametrize("ruta,valor", [(("observado", "valor"), "x"), (("simulado",), [1]),
                                        (("referencia_analitica",), 0.5), (("supera_umbral_exploratorio",), "no")])
def test_f4_estadistica_con_tipos_no_validos_no_llega_a_la_ficha_ni_a_la_exportacion(e, ruta, valor):
    s = e.servicio()
    ident = s.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]["resultado"]
    fila = _fila(e, ident)
    resumen = fila["resultado_resumen"]
    destino = resumen["contenido"]["estadisticas"][0]
    for clave in ruta[:-1]:
        destino = destino[clave]
    destino[ruta[-1]] = valor
    parametros, resumen = _resellar(fila["parametros"], resumen)
    _actualizar(e, fila["id"], resultado_resumen=resumen)
    c = f7.cliente(e, servicio=s)
    for url in ("", "/exportar.csv", "/exportar.json"):
        assert c.get(f"/simulaciones/resultados/{ident}{url}").status_code == 409
    assert s.listar("MILOTO")[0]["integridad"] == "alterada"


@pytest.mark.parametrize("parametros", [[1], 7, "texto"], ids=["lista", "entero", "texto"])
def test_f4_parametros_que_no_son_objeto_no_se_atribuyen_a_la_base(e, parametros):
    s = e.servicio()
    ident = s.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]["resultado"]
    _actualizar(e, _fila(e, ident)["id"], parametros=parametros)
    assert s.listar("MILOTO") == []  # sin `clave` no es una fila de la Fase 7 (filtro SQL del listado)
    assert s.diagnostico("MILOTO")["estado"] == "disponible"
    assert _codigo(lambda: s.obtener(ident)) == "no_encontrado"


def test_f4_juego_de_la_identidad_no_textual_no_se_atribuye_a_la_base(e):
    s = e.servicio()
    ident = s.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]["resultado"]
    fila = _fila(e, ident)
    _actualizar(e, fila["id"], parametros={**fila["parametros"], "juego": [1]})
    assert _codigo(lambda: s.obtener(ident)) == "alterado"
    assert s.listar("MILOTO")[0]["integridad"] == "alterada"
