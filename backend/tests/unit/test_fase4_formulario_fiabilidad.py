"""Regresiones de consultas reales de Fiabilidad, solo con datos sintéticos.

El formulario se vuelve a enviar a partir de los campos del HTML; los
informes se construyen con el serializador real del laboratorio. Ningún GET
debe modificar configuraciones, informes, carteras ni explicaciones.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest

from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.use_cases.predicciones import SLUGS
from tests.unit import fixtures_fase4 as f4


class _Formulario(HTMLParser):
    def __init__(self, texto):
        super().__init__()
        self.hasta = None
        self.lineas = []
        self.feed(texto)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("name") == "hasta":
            self.hasta = a.get("value", "")
        if tag == "option" and "selected" in a:
            self.lineas.append(a.get("value", ""))

    def parametros(self):
        assert self.hasta is not None and len(self.lineas) == 1
        return {"hasta": self.hasta, "linea": self.lineas[0]}


@pytest.fixture
def entorno(tmp_path):
    e = f4.entorno(tmp_path)
    yield e
    f4.limpiar()


def _consulta_preparada(e, juego):
    uniforme = "uniforme_paleta" if juego == "COLORLOTO" else "uniforme"
    modelo = "actual_multinomial_suavizada" if juego == "COLORLOTO" else "logistica_regularizada"
    # La URL nativa usa la línea sin sufijo de perfil. El fixture general
    # elige «reducido» por defecto, de modo que aquí se solicita el contrato
    # predeterminado de la uniforme explícitamente (no requiere entrenar).
    e.configurar(juego, uniforme, perfil=None)
    centro = e.centro()
    centro.ahora(juego)
    e.configurar(juego, modelo)
    cliente = f4.cliente(e, centro=centro)
    linea = "carteras:" + uniforme + "-v1"
    assert linea in centro.fiabilidad(juego)["lineas_disponibles"]
    return centro, cliente, linea


@pytest.mark.parametrize("juego", SLUGS)
def test_formulario_conserva_linea_y_corte_y_consulta_aditiva(entorno, juego):
    centro, cliente, adicional = _consulta_preparada(entorno, juego)
    web = f"/predicciones/{SLUGS[juego]}/fiabilidad"
    api = f"/api/predicciones/{juego}/fiabilidad"
    antes = f4.arbol(entorno.raiz)
    configuracion = centro.fiabilidad(juego)["configuracion"]
    lineas_base = [l["linea"] for l in centro.fiabilidad(juego)["lineas"]]
    corte = entorno.corte(juego)
    for parametros, seleccion, limite in (({}, None, None), ({"hasta": "", "linea": ""}, None, None),
                                         ({"hasta": "", "linea": adicional}, adicional, None),
                                         ({"hasta": str(corte), "linea": adicional}, adicional, corte)):
        respuesta = cliente.get(web, params=parametros)
        assert respuesta.status_code == 200, respuesta.text
        campos = _Formulario(respuesta.text).parametros()
        assert campos == {"hasta": "" if limite is None else str(limite), "linea": seleccion or ""}
        datos = cliente.get(api, params=parametros)
        assert datos.status_code == 200, datos.text
        datos = datos.json()
        assert datos["hasta"] == limite and datos["linea_consultada"] == seleccion
        esperadas = lineas_base + ([adicional] if seleccion and adicional not in lineas_base else [])
        assert [l["linea"] for l in datos["lineas"]] == esperadas
        assert datos["configuracion"] == json.loads(json.dumps(configuracion))
        # Consulta repetida con los campos realmente presentes en el formulario.
        repetida = cliente.get(web, params=campos)
        assert repetida.status_code == 200 and _Formulario(repetida.text).parametros() == campos
        assert cliente.get(api, params=campos).json() == datos
    assert f4.arbol(entorno.raiz) == antes


@pytest.mark.parametrize("juego", SLUGS)
@pytest.mark.parametrize("invalido", ("no-es-un-entero", " ", "1e2", "1.5", "0", "-1"))
def test_corte_no_vacio_invalido_se_rechaza_en_ambas_interfaces(entorno, juego, invalido):
    centro = entorno.centro()
    cliente = f4.cliente(entorno, centro=centro)
    antes = f4.arbol(entorno.raiz)
    for ruta in (f"/predicciones/{SLUGS[juego]}/fiabilidad", f"/api/predicciones/{juego}/fiabilidad"):
        respuesta = cliente.get(ruta, params={"hasta": invalido, "linea": ""})
        assert respuesta.status_code == 422
    assert f4.arbol(entorno.raiz) == antes


@pytest.mark.parametrize("juego", SLUGS)
def test_linea_desconocida_no_se_convierte_en_consulta_por_defecto(entorno, juego):
    cliente = f4.cliente(entorno)
    antes = f4.arbol(entorno.raiz)
    for ruta in (f"/predicciones/{SLUGS[juego]}/fiabilidad", f"/api/predicciones/{juego}/fiabilidad"):
        respuesta = cliente.get(ruta, params={"hasta": "", "linea": "carteras:desconocida-v1"})
        assert respuesta.status_code == 422 and "desconocida" in respuesta.text
    assert f4.arbol(entorno.raiz) == antes


def _informe_serializado(e, juego, modelo):
    """Métricas sintéticas; identidad, reglas, cuerpo y sello del producto real."""
    instantanea = lv.validar_instantanea(juego, e.historicos[juego])
    referencia = "uniforme_paleta" if juego == "COLORLOTO" else "uniforme"
    entradas = [lm.CATALOGO[modelo], lm.CATALOGO[referencia]]
    identidad = la.identidad_del_experimento(instantanea, entradas, le.Protocolo(bloques=2, perfil="reducido"))
    objetivos = [r.numero_sorteo for r in instantanea.sorteos[-40:]]
    filas = [{"objetivo": o, "diferencia_log_loss": (-1 if i % 3 else 1) * (i + 1) / 10000,
              "brier": 0.1 + (-1 if i % 2 else 1) * (i + 1) / 100000} for i, o in enumerate(objetivos)]
    evaluacion = {"muestra_comun": {"excluidos": []}, "candidatos": [
        {"id": modelo, "version": lm.CATALOGO[modelo].version, "familia": "modelo_nuevo", "estado": "completo",
         "por_objetivo": filas},
        {"id": referencia, "version": "1", "familia": "uniforme", "estado": "completo",
         "por_objetivo": [{"objetivo": o, "brier": 0.1} for o in objetivos]}]}
    if lv.REGLAS[juego].superbalota:
        evaluacion["superbalota"] = {"agregado": {}}
    informe = la.componer(la.cuerpo_del_experimento(instantanea, identidad, evaluacion), "ejecucion", {})
    assert la.integro(informe)
    return json.loads(json.dumps(informe))


@pytest.mark.parametrize("juego", SLUGS)
def test_informe_serializado_llega_con_componente_real_al_caso_api_y_html(entorno, juego):
    modelo = "actual_multinomial_suavizada" if juego == "COLORLOTO" else "logistica_regularizada"
    entorno.configurar(juego, modelo)
    informe = _informe_serializado(entorno, juego, modelo)
    assert "colores" not in informe["identidad"]["reglas"]
    centro = entorno.centro()
    # La frontera del almacén entrega el artefacto serializado e íntegro, sin entrenar.
    centro._modelos = SimpleNamespace(experimentos=lambda codigo: [SimpleNamespace(artefacto=informe)])
    cliente = f4.cliente(entorno, centro=centro)
    antes = f4.arbol(entorno.raiz)
    informe_antes = json.dumps(informe, sort_keys=True)
    receta = centro.fiabilidad(juego)["receta"]
    principal = "pares" if juego == "COLORLOTO" else "numeros"
    componentes = {principal} | ({"superbalota"} if lv.REGLAS[juego].superbalota else set())
    assert receta["estado"] == "estimable" and set(receta["componentes"]) == componentes
    api = cliente.get(f"/api/predicciones/{juego}/fiabilidad", params={"hasta": "", "linea": ""})
    assert api.status_code == 200 and api.json()["receta"] == receta
    html = cliente.get(f"/predicciones/{SLUGS[juego]}/fiabilidad", params={"hasta": "", "linea": ""})
    assert html.status_code == 200
    assert ("Pares número-color" if principal == "pares" else "Números principales") in html.text
    if principal == "pares":
        assert "Números principales" not in html.text
        assert informe["identidad"]["reglas"]["multiconjunto_de_pares_numero_color"] is True
        assert informe["identidad"]["reglas"]["repeticion"] is True
    assert json.dumps(informe, sort_keys=True) == informe_antes and f4.arbol(entorno.raiz) == antes


@pytest.mark.parametrize("cantidad", (1, 2))
def test_fiabilidad_presenta_sorteo_en_singular_y_plural(entorno, cantidad):
    entorno.configurar("MILOTO", "uniforme")
    centro = entorno.centro()
    for i in range(cantidad):
        centro.ahora("MILOTO")
        entorno.anadir("MILOTO", entorno.siguiente("MILOTO", semilla=700 + i))
    antes = f4.arbol(entorno.raiz)
    respuesta = f4.cliente(entorno, centro=centro).get("/predicciones/miloto/fiabilidad")
    assert respuesta.status_code == 200
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", respuesta.text))
    assert f"Números principales · {cantidad} {'sorteo' if cantidad == 1 else 'sorteos'}" in texto
    assert "1 sorteos" not in texto
    assert f4.arbol(entorno.raiz) == antes
