"""Fase 3 -integracion del registro de modelos con la interfaz, la API, el
comando, la seleccion explicita de Producto 5/6 y la operacion diaria de
carteras. Datos sinteticos; nada es real."""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import re

import pytest

from app.application.ml import carteras_artefactos as ca
from app.application.ml import laboratorio_modelos as lm
from app.application.use_cases.carteras import CarterasError
from scripts import carteras_modelos as cli_carteras
from scripts import laboratorio_modelos as cli
from tests.unit import fixtures_fase3 as f3


@pytest.fixture
def entorno(tmp_path):
    e = f3.entorno(tmp_path)
    yield e
    f3.limpiar()


def _arbol(raiz) -> dict:
    return {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raiz.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------
# Interfaz web
# ---------------------------------------------------------------------------

def test_flujo_web_comparar_entrenar_ficha_verificar_generar_y_resultados(entorno):
    lab = entorno.laboratorio()
    c = f3.cliente(entorno, laboratorio=lab)
    token = f3.token(c)
    r = lab.comparar_ahora(["BALOTO"], f3.PROTOCOLO, corte=entorno.corte("BALOTO"))["juegos"]["BALOTO"]
    informe = c.get(f"/laboratorio/experimentos/{r['experimento']}").text
    assert "Entrenar y guardar versión" in informe and "Métricas secundarias" in informe
    assert "Cómo se ordena" in informe and "Random Forest (clasificacion)" in informe
    respuesta = c.post(f"/laboratorio/experimentos/{r['experimento']}/entrenar",
                       data={"modelo": "random_forest_clasificador", "token_local": token}, follow_redirects=False)
    assert respuesta.status_code == 303
    progreso = c.get(respuesta.headers["location"]).text
    assert "Entrenar y guardar un modelo" in progreso and "versión nueva guardada" in progreso
    clave = re.search(r"/laboratorio/modelo/([0-9a-f]{64})", progreso).group(1)
    ficha = c.get(f"/laboratorio/modelo/{clave}").text
    for texto in ("Finalización técnica", "Ventaja predictiva: no acreditada", "Evaluación asociada",
                  "Componentes de inferencia guardados", "Contrato de inferencia", "Selección interna",
                  "Pronóstico de control", "AUTORIZA_EVALUACION = False"):
        assert texto in ficha, texto
    verificacion = c.post(f"/laboratorio/modelo/{clave}/verificar", data={"token_local": token}).text
    assert "reproduce exactamente el control" in verificacion
    generado = c.post(f"/laboratorio/modelo/{clave}/generar", data={"token_local": token, "corte": ""},
                      follow_redirects=False)
    assert generado.status_code == 303
    pronostico = c.get(generado.headers["location"]).text
    assert "versión registrada 1" in pronostico and "sin reentrenar" in pronostico
    seguimiento = c.get("/laboratorio/baloto/seguimiento?linea=random_forest_clasificador-v1-reg1-reducido")
    assert seguimiento.status_code == 200
    listado = c.get("/laboratorio/modelos?juego=baloto").text
    assert "v1" in listado and "compatible" in listado and "Familias del roadmap que aún no existen" in listado


def test_los_get_son_de_solo_lectura(entorno):
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "COLORLOTO")
    c = f3.cliente(entorno, laboratorio=lab)
    antes = _arbol(entorno.directorio.parent)
    for url in ("/laboratorio", "/laboratorio/colorloto", "/laboratorio/modelos", "/laboratorio/modelos?juego=colorloto",
                f"/laboratorio/modelo/{r['modelo_registrado']}", "/api/laboratorio/modelos",
                f"/api/laboratorio/modelos/{r['modelo_registrado']}", f"/laboratorio/experimentos/{r['experimento']}",
                f"/carteras/colorloto?modelo=extra_trees_poisson&registrado={r['modelo_registrado']}"):
        assert c.get(url).status_code == 200, url
    assert _arbol(entorno.directorio.parent) == antes


def test_estados_visibles_de_error(entorno):
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "MILOTO")
    c = f3.cliente(entorno, laboratorio=lab)
    token = f3.token(c)
    anterior = c.post(f"/laboratorio/modelo/{r['modelo_registrado']}/generar",
                      data={"token_local": token, "corte": str(entorno.corte("MILOTO", 20))})
    assert anterior.status_code == 422 and "ya vio esos resultados" in anterior.text
    assert c.get("/laboratorio/modelo/" + "0" * 64).status_code == 404
    referencia = c.post(f"/laboratorio/experimentos/{r['experimento']}/entrenar",
                        data={"modelo": "actual_frecuencia_contraida", "token_local": token})
    assert referencia.status_code == 422 and "no tiene un estimador" in referencia.text
    sin_token = c.post(f"/laboratorio/modelo/{r['modelo_registrado']}/generar", data={"corte": ""})
    assert sin_token.status_code == 403
    objeto = next((entorno.directorio / "modelos" / "MILOTO" / "estimadores").glob("*.pkl"))
    objeto.write_bytes(b"alterado")
    assert c.get(f"/laboratorio/modelo/{r['modelo_registrado']}").status_code == 409
    assert "estimador alterado" in c.get("/laboratorio/modelos?juego=miloto").text


# ---------------------------------------------------------------------------
# API y comando (mismos casos de uso)
# ---------------------------------------------------------------------------

def test_api_y_comando_devuelven_lo_mismo_que_el_caso_de_uso(entorno):
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "BALOTO_REVANCHA")
    c = f3.cliente(entorno, laboratorio=lab)
    api = c.get("/api/laboratorio/modelos?juego=BALOTO_REVANCHA").json()
    assert api["juegos"]["BALOTO_REVANCHA"]["versiones"][0]["clave"] == r["modelo_registrado"]
    ficha = c.get(f"/api/laboratorio/modelos/{r['modelo_registrado']}").json()
    assert ficha["resumen"]["numero"] == 1 and ficha["proyeccion"]["modelos"]["version"] == "v1"
    salida = io.StringIO()
    assert cli.ejecutar(["modelos", "--juego", "BALOTO_REVANCHA"], laboratorio_factory=lambda: lab, salida=salida,
                        errores=io.StringIO()) == 0
    assert json.loads(salida.getvalue())["juegos"]["BALOTO_REVANCHA"]["versiones"] == api["juegos"]["BALOTO_REVANCHA"]["versiones"]
    salida = io.StringIO()
    assert cli.ejecutar(["verificar", "--modelo", r["modelo_registrado"]], laboratorio_factory=lambda: lab,
                        salida=salida, errores=io.StringIO()) == 0
    salida = io.StringIO()
    assert cli.ejecutar(["generar-con-modelo", "--clave", r["modelo_registrado"]], laboratorio_factory=lambda: lab,
                        salida=salida, errores=io.StringIO()) == 0
    generado = json.loads(salida.getvalue())
    assert generado["linea"] == "extra_trees_clasificador-v1-reg1-reducido" and not generado["reutilizado"]
    salida = io.StringIO()
    assert cli.ejecutar(["entrenar", "--experimento", r["experimento"], "--modelo", "extra_trees_clasificador"],
                        laboratorio_factory=lambda: lab, salida=salida, errores=io.StringIO()) == 0
    assert next(iter(json.loads(salida.getvalue())["juegos"].values()))["estado"] == "reutilizado"
    errores = io.StringIO()
    assert cli.ejecutar(["generar-con-modelo", "--clave", r["modelo_registrado"], "--corte",
                         str(entorno.corte("BALOTO_REVANCHA", 30))], laboratorio_factory=lambda: lab,
                        salida=io.StringIO(), errores=errores) == cli.EXIT_USO
    assert "corte_no_valido" in errores.getvalue()


def test_comando_codigos_de_incompatible_y_alterado(entorno, monkeypatch):
    from app.application.ml import laboratorio_artefactos as la

    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "MILOTO")
    real = la.entorno()
    monkeypatch.setattr(la, "entorno", lambda: {**real, "numpy": "1.0.0"})
    assert cli.ejecutar(["verificar", "--modelo", r["modelo_registrado"]], laboratorio_factory=lambda: lab,
                        salida=io.StringIO(), errores=io.StringIO()) == cli.EXIT_INCOMPATIBLE
    monkeypatch.setattr(la, "entorno", lambda: real)
    objeto = next((entorno.directorio / "modelos" / "MILOTO" / "estimadores").glob("*.pkl"))
    objeto.write_bytes(b"x")
    assert cli.ejecutar(["verificar", "--modelo", r["modelo_registrado"]], laboratorio_factory=lambda: lab,
                        salida=io.StringIO(), errores=io.StringIO()) == cli.EXIT_ALTERADO


# ---------------------------------------------------------------------------
# Seleccion explicita (Producto 5 y 6) y operacion diaria de carteras
# ---------------------------------------------------------------------------

def test_comparar_y_entrenar_no_cambian_la_configuracion_vigente(entorno):
    lab, carteras = entorno.laboratorio(), entorno.carteras()
    carteras.configurar("BALOTO", "logistica_regularizada", 3, "libre", 7, "reducido")
    antes = carteras.configuracion_vigente("BALOTO").artefacto
    entorno.registrar(lab, "BALOTO")
    assert carteras.configuracion_vigente("BALOTO").artefacto == antes
    assert len(carteras.configuraciones("BALOTO")) == 1


def test_configuracion_sin_version_registrada_conserva_su_forma(entorno):
    cuerpo = ca.cuerpo_de_configuracion("BALOTO", 1, "hgb_clasificador", "predeterminado", 3, "libre", 7)
    assert cuerpo["modelo"] == {"id": "hgb_clasificador", "version": "1"}
    assert cuerpo["linea"] == "hgb_clasificador-v1-n3-libre-s7"


def test_carteras_configuradas_usan_el_modelo_congelado_sin_reentrenar(entorno, monkeypatch):
    lab, carteras = entorno.laboratorio(), entorno.carteras()
    r = entorno.registrar(lab, "COLORLOTO")
    g = carteras.configurar("COLORLOTO", "extra_trees_poisson", 3, "libre", 11, registrado=r["modelo_registrado"])
    modelo = g.artefacto["modelo"]
    assert modelo["registrado"]["clave"] == r["modelo_registrado"] and modelo["registrado"]["numero"] == 1
    assert g.artefacto["perfil"] == "reducido"  # el de la version registrada
    assert g.artefacto["linea"] == "extra_trees_poisson-v1-reg1-n3-libre-s11-reducido"

    def prohibido(*args, **kwargs):
        raise AssertionError("la operacion diaria no debe reentrenar una version registrada")
    monkeypatch.setattr(lm, "ajustar_candidato", prohibido)
    final = carteras.ahora("carteras_configuradas", ["COLORLOTO"])
    resultado = final["juegos"]["COLORLOTO"]
    assert resultado["estado"] == "terminado", resultado
    cartera = carteras.cartera(resultado["resultado"]).artefacto
    assert cartera["identidad"]["modelo"]["registrado"]["clave"] == r["modelo_registrado"]
    assert cartera["fuente"]["detalle"]["modelo_registrado"] == r["modelo_registrado"]
    assert cartera["modelo"]["registrado"]["numero"] == 1
    verificacion = carteras.verificar_cartera(resultado["resultado"])
    assert verificacion["reproduccion"]["huella_exacta"] is True


def test_configurar_rechaza_versiones_de_otro_juego_o_modelo_e_incompatibles(entorno, monkeypatch):
    from app.application.ml import laboratorio_artefactos as la

    lab, carteras = entorno.laboratorio(), entorno.carteras()
    r = entorno.registrar(lab, "MILOTO")
    with pytest.raises(CarterasError) as error:
        carteras.configurar("BALOTO", "random_forest_clasificador", 3, "libre", 7, registrado=r["modelo_registrado"])
    assert error.value.codigo == "no_valido"
    with pytest.raises(CarterasError) as error:
        carteras.configurar("MILOTO", "hgb_clasificador", 3, "libre", 7, registrado=r["modelo_registrado"])
    assert error.value.codigo == "no_valido"
    with pytest.raises(CarterasError) as error:
        carteras.configurar("MILOTO", "random_forest_clasificador", 3, "libre", 7, registrado="f" * 64)
    assert error.value.codigo == "no_encontrado"
    real = la.entorno()
    monkeypatch.setattr(la, "entorno", lambda: {**real, "scikit-learn": "0.1"})
    with pytest.raises(CarterasError) as error:
        carteras.configurar("MILOTO", "random_forest_clasificador", 3, "libre", 7, registrado=r["modelo_registrado"])
    assert error.value.codigo == "incompatible"
    assert carteras.configuraciones("MILOTO") == []


def test_configurar_desde_la_web_y_el_comando_con_version_registrada(entorno):
    lab, carteras = entorno.laboratorio(), entorno.carteras()
    r = entorno.registrar(lab, "BALOTO")
    c = f3.cliente(entorno, laboratorio=lab, carteras=carteras)
    token = f3.token(c)
    formulario = c.get(f"/carteras/baloto?modelo=random_forest_clasificador&registrado={r['modelo_registrado']}").text
    assert f'value="{r["modelo_registrado"]}" selected' in formulario and "No se guarda nada" in formulario
    assert carteras.configuraciones("BALOTO") == []  # preseleccionar no guarda
    respuesta = c.post("/carteras/baloto/configurar", data={"modelo": "random_forest_clasificador", "cantidad": 2,
                                                            "diversidad": "libre", "semilla": 5,
                                                            "registrado": r["modelo_registrado"],
                                                            "token_local": token}, follow_redirects=False)
    assert respuesta.status_code == 303
    assert carteras.configuracion_vigente("BALOTO").artefacto["modelo"]["registrado"]["numero"] == 1
    assert "modelo registrado v1" in c.get("/carteras/baloto").text
    salida = io.StringIO()
    assert cli_carteras.ejecutar(["configurar", "--juego", "BALOTO", "--modelo", "random_forest_clasificador",
                                  "--cantidad", "2", "--semilla", "6", "--registrado", r["modelo_registrado"]],
                                 carteras_factory=lambda: carteras, salida=salida, errores=io.StringIO()) == 0
    assert json.loads(salida.getvalue())["configuracion"]["modelo"]["registrado"]["clave"] == r["modelo_registrado"]


def test_usar_configuracion_de_producto_6_conserva_la_version_registrada(entorno):
    from app.application.use_cases.resultados import CentroDeResultados
    from app.infrastructure.storage.carteras_file_store import CarterasFileStore
    from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
    from app.infrastructure.storage.resultados_file_store import ResultadosFileStore

    lab, carteras = entorno.laboratorio(), entorno.carteras()
    r = entorno.registrar(lab, "MILOTO")
    final = carteras.ahora("cartera", ["MILOTO"], {"modelo": "random_forest_clasificador", "perfil": "reducido",
                                                   "cantidad": 2, "diversidad": "libre", "semilla": 3,
                                                   "registrado": r["modelo_registrado"]})
    linea = final["juegos"]["MILOTO"]["linea"]
    assert linea == "random_forest_clasificador-v1-reg1-n2-libre-s3-reducido"
    raiz = entorno.directorio.parent
    centro = CentroDeResultados(PronosticoExperimentalFileStore(raiz / "p"), entorno.almacen_laboratorio,
                                CarterasFileStore(raiz / "carteras"), ResultadosFileStore(raiz / "r"), entorno.abrir,
                                carteras_servicio=lambda: carteras)
    propuesta = centro.propuesta_de_configuracion("MILOTO", linea)
    assert propuesta["propuesta"]["registrado"]["clave"] == r["modelo_registrado"] and propuesta["compatible"]
    usada = centro.usar_configuracion("MILOTO", linea)
    assert usada["estado"] == "guardada" and usada["linea"] == "random_forest_clasificador-v1-reg1-n2-libre-s3-reducido"
    assert carteras.configuracion_vigente("MILOTO").artefacto["modelo"]["registrado"]["clave"] == r["modelo_registrado"]


def test_la_linea_registrada_tiene_nombre_propio_en_producto_6(entorno):
    from app.application.ml import resultados_procedencias as rp

    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "BALOTO")
    g = lab.generar_con_modelo(r["modelo_registrado"])
    assert "versión registrada 1" in rp.linea_de_laboratorio(g.artefacto)["nombre"]


# ---------------------------------------------------------------------------
# Contrato de inferencia de extremo a extremo
# ---------------------------------------------------------------------------

def test_generar_con_corte_de_entrada_no_usa_el_objetivo_ni_sorteos_posteriores(entorno):
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "BALOTO", atras=6)
    corte_entrada = entorno.corte("BALOTO", 3)
    a = lab.generar_con_modelo(r["modelo_registrado"], corte_entrada)
    # se corrigen en la base el objetivo y todo lo posterior: el mismo pronostico (misma entrada)
    juego = entorno.juegos.obtener_por_codigo("BALOTO")
    entorno.resultados.numericos[juego.id] = [
        dataclasses.replace(x, numeros=(1, 2, 3, 4, 5)) if x.numero_sorteo > corte_entrada else x
        for x in entorno.resultados.numericos[juego.id]]
    b = lab.generar_con_modelo(r["modelo_registrado"], corte_entrada)
    assert b.reutilizado and b.identificador == a.identificador
    assert a.artefacto["pronostico"]["objetivo"] == corte_entrada + 1
    # la generacion clasifica el objetivo como ya cargado (retrospectiva), sin cambiar la prediccion
    assert a.artefacto["generacion"]["clasificacion_temporal"]["tipo"] == "simulacion_retrospectiva"


def test_entrenar_y_generar_en_el_proceso_trabajador_real(entorno):
    from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso

    ejecutor = EjecutorEnProceso(tiempo_maximo=600)
    lab = entorno.laboratorio(ejecutor=ejecutor)
    r = entorno.registrar(lab, "MILOTO")
    assert r["estado"] == "terminado"
    g = lab.generar_con_modelo(r["modelo_registrado"])
    v = lab.verificar_modelo(r["modelo_registrado"])
    assert v["reproduccion"]["exacta"] and g.artefacto["identidad"]["modelo_registrado"]["numero"] == 1
    assert ejecutor.lanzados >= 4 and ejecutor.activos == 0  # comparar, entrenar, generar y verificar
