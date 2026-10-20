"""Aceptación ML: cinco familias reales por cuatro juegos y consumidores.

Sólo históricos y almacenes sintéticos. Los modelos se ajustan de verdad;
los guardianes de ``fit`` se activan DESPUÉS del registro. La demostración
reutiliza el recorrido, pero no se ejecuta al importar este módulo.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import inspect
import io
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import modelos_registrados as mr
from app.application.interfaces.laboratorio_store import GuardadoModelo
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from tests.unit import fixtures_fase4 as f4

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
NUMERICOS = ("xgboost_binario", "lightgbm_binario", "red_neuronal_binaria",
             "bayes_jerarquico_binario", "markov_apariciones")
PARES = ("xgboost_poisson", "lightgbm_poisson", "red_neuronal_poisson",
         "bayes_jerarquico_pares", "markov_pares")
FAMILIAS = ("xgboost", "lightgbm", "red_neuronal", "bayes", "markov")
PROTOCOLO = le.Protocolo(bloques=2, perfil="reducido")
PLAZO_PROCESO = 90
PREFIJO_FIXTURE = "m "
CARPETA_CONCURRENCIA = "ml ruta"


def modelos(juego):
    return PARES if juego == "COLORLOTO" else NUMERICOS


def _prohibido(*args, **kwargs):
    raise AssertionError("un consumidor de la versión congelada llamó a entrenamiento")


@contextlib.contextmanager
def sin_entrenamiento():
    """Impide tanto el reajuste por la fachada como los ``fit`` concretos.

    Importar clases no ajusta modelos. Incluye las dos API nativas de train,
    para detectar una recarga que disimulara un nuevo entrenamiento.
    """
    with contextlib.ExitStack() as pila:
        pila.enter_context(patch.object(lm, "ajustar_candidato", _prohibido))
        modulos = ("sklearn.pipeline", "sklearn.calibration", "sklearn.linear_model",
                   "sklearn.ensemble", "sklearn.neural_network",
                   "app.application.ml.laboratorio_boosts_redes",
                   "app.application.ml.laboratorio_bayes_markov", "xgboost", "lightgbm")
        vistas = set()
        for nombre in modulos:
            modulo = importlib.import_module(nombre)
            for valor in vars(modulo).values():
                if inspect.isclass(valor) and hasattr(valor, "fit") and id(valor) not in vistas:
                    vistas.add(id(valor))
                    pila.enter_context(patch.object(valor, "fit", _prohibido))
            if nombre in ("xgboost", "lightgbm"):
                pila.enter_context(patch.object(modulo, "train", _prohibido))
        yield


def preparar(raiz, juego):
    """Una comparación común y cinco versiones reales para el juego pedido."""
    e = f4.entorno(Path(raiz), {j: 190 for j in JUEGOS})
    lab, carteras = e.laboratorio(), e.carteras()
    carteras.configurar(juego, "uniforme_paleta" if juego == "COLORLOTO" else "uniforme", 2, "libre", 17)
    vigente = carteras.configuracion_vigente(juego).artefacto
    comparacion = lab.comparar_ahora([juego], PROTOCOLO, corte=e.corte(juego))["juegos"][juego]
    assert comparacion["estado"] in ("terminado", "parcial"), comparacion
    informe = lab.experimento(comparacion["experimento"]).artefacto
    assert len(informe["candidatos"]) == len(lm.candidatos_del_juego(juego)) == 11
    candidatos = {c["id"]: c for c in informe["candidatos"]}
    comunes = informe["muestra_comun"]["objetivos"]
    versiones = {}
    for modelo in modelos(juego):
        candidato = candidatos[modelo]
        assert candidato["estado"] == "completo", candidato
        assert [f["objetivo"] for f in candidato["por_objetivo"]] == comunes
        assert {"log_loss", "brier"} <= candidato["agregado"].keys()
        final = lab.entrenar_ahora(comparacion["experimento"], modelo)["juegos"][juego]
        assert final["estado"] == "terminado" and final["numero"] == 1, final
        versiones[modelo] = final
    assert carteras.configuracion_vigente(juego).artefacto == vigente
    return {"e": e, "lab": lab, "carteras": carteras, "informe": informe,
            "experimento": comparacion["experimento"], "versiones": versiones}


def _recargar(almacen, clave, experimento):
    store = LaboratorioFileStore(Path(almacen))
    guardado = store.obtener_modelo(clave)
    assert isinstance(guardado, GuardadoModelo)
    informe = store.obtener_experimento(experimento).artefacto
    contenido = store.leer_estimador(guardado)
    with sin_entrenamiento():
        control = mr.control_recargado(guardado.artefacto, contenido, informe)
    assert control["sha256_probabilidades"] == guardado.artefacto["control"]["sha256_probabilidades"]
    return {"pid": os.getpid(), "clave": clave, "control": control, "sin_fit": True}


def recargar_en_otro_proceso(datos, modelo):
    r = datos["versiones"][modelo]
    comando = [sys.executable, "-m", "tests.unit.test_ml_cinco_flujo", "--recargar",
               str(datos["e"].directorio), r["modelo_registrado"], datos["experimento"]]
    proceso = subprocess.run(comando, capture_output=True, text=True, timeout=PLAZO_PROCESO,
                             cwd=Path(__file__).resolve().parents[2], check=False)
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    resultado = json.loads(proceso.stdout)
    assert resultado["pid"] != os.getpid() and resultado["sin_fit"]
    return resultado


def recorrido(datos, juego, modelo, *, web=True):
    """Registro → reinicio sin fit → elección explícita → explicación/evidencia."""
    from scripts import laboratorio_modelos as cli_lab
    from scripts import predicciones as cli_pred

    e, lab, carteras = datos["e"], datos["lab"], datos["carteras"]
    r = datos["versiones"][modelo]
    clave = r["modelo_registrado"]
    recarga = recargar_en_otro_proceso(datos, modelo)
    with sin_entrenamiento():
        assert lab.verificar_modelo(clave)["reproduccion"]["exacta"]
        pronostico_laboratorio = lab.generar_con_modelo(clave)
        assert lab.verificar_pronostico(pronostico_laboratorio.identificador)["mismo_entorno"]
        repetido = lab.entrenar_ahora(datos["experimento"], modelo)["juegos"][juego]
        assert repetido["estado"] == "reutilizado" and repetido["modelo_registrado"] == clave
        carteras.configurar(juego, modelo, 2, "libre", 17, registrado=clave)
        configuracion = carteras.configuracion_vigente(juego).artefacto
        centro = e.centro(carteras)
        generada = centro.ahora(juego)["prediccion"]
        assert generada["estado"] == "exito" and generada["explicacion"]["estado"] == "guardada", generada
        consultada = centro.consultar(juego)["prediccion"]
        assert consultada["modelo"]["id"] == modelo
        assert consultada["linea_del_artefacto"]["registrado"]["clave"] == clave
        assert consultada["reproduccion"]["exacta"] and len(consultada["combinaciones"]) == 2
        assert consultada["proyeccion"]["columnas"]["nivel_confianza"] is None
        repetida = centro.ahora(juego)["prediccion"]
        assert repetida["cartera"]["clave"] == generada["cartera"]["clave"]
        cinco = centro.ahora(juego, "cinco")["prediccion"]
        assert cinco["solicitud"]["combinaciones"] == 5
        assert carteras.configuracion_vigente(juego).artefacto == configuracion
        # El resultado observado pertenece a una emisión anterior, nunca se
        # presenta como predicción una generación posterior al resultado.
        e.anadir(juego, e.siguiente(juego, semilla=51))
        vista = e.centro(carteras).consultar(juego, generada["cartera"]["clave"])["prediccion"]
        assert vista["explicacion"] is not None
        fiabilidad = centro.fiabilidad(juego)
        assert fiabilidad["lineas"] and fiabilidad["metodo"]["version"] == "fase4-fiabilidad-1"
        seguimiento = [v for l in fiabilidad["lineas"] for v in l["evaluaciones"] if v["tipo"] == "seguimiento"]
        assert any(v["muestra"]["sorteos"] >= 1 for v in seguimiento)
        salida, errores = io.StringIO(), io.StringIO()
        assert cli_lab.ejecutar(["verificar", "--modelo", clave], laboratorio_factory=lambda: lab,
                               salida=salida, errores=errores) == 0, errores.getvalue()
        salida, errores = io.StringIO(), io.StringIO()
        assert cli_pred.ejecutar(["consultar", "--juego", juego], centro_factory=lambda: centro,
                                salida=salida, errores=errores) == 0, errores.getvalue()
        assert json.loads(salida.getvalue())["prediccion"]["modelo"]["id"] == modelo
        antes = f4.arbol(e.raiz)
        centro.indice()
        centro.consultar(juego)
        centro.fiabilidad(juego)
        if web:
            slug = juego.lower().replace("_", "-")
            with f4.cliente(e, carteras=carteras, laboratorio=lab, centro=centro) as cliente:
                from app.api import dependencies as dep
                from app.main import app
                app.dependency_overrides[dep.get_resultados] = lambda: e.centro_de_resultados(carteras)
                ficha = cliente.get(f"/laboratorio/modelo/{clave}")
                assert ficha.status_code == 200 and "AUTORIZA_EVALUACION = False" in ficha.text
                for url in (f"/predicciones/{slug}", f"/predicciones/{slug}/fiabilidad",
                            f"/api/predicciones/{juego}", "/api/laboratorio/modelos",
                            f"/api/laboratorio/modelos/{clave}", "/resultados"):
                    respuesta = cliente.get(url)
                    assert respuesta.status_code == 200, (url, respuesta.text)
                api = cliente.get(f"/api/laboratorio/modelos/{clave}").json()
                assert api["resumen"]["numero"] == 1
        assert f4.arbol(e.raiz) == antes
    return {"juego": juego, "modelo": modelo, "clave": clave, "sin_fit": recarga["sin_fit"],
            "estado": "completo", "combinaciones": 2, "alternativa": 5,
            "seguimiento_observado": True, "configuracion_conservada": True}


@pytest.fixture(scope="module")
def laboratorios(tmp_path_factory):
    cache = {}

    def obtener(juego):
        if juego not in cache:
            cache[juego] = preparar(tmp_path_factory.mktemp(PREFIJO_FIXTURE + str(JUEGOS.index(juego))), juego)
        return cache[juego]
    yield obtener
    f4.limpiar()


@pytest.mark.parametrize("juego,indice", [(j, i) for j in JUEGOS for i in range(5)])
def test_cinco_familias_cuatro_juegos_recorrido_real(laboratorios, juego, indice):
    recorrido(laboratorios(juego), juego, modelos(juego)[indice])



@pytest.mark.parametrize("juego", JUEGOS)
def test_informe_ampliado_muestra_todas_las_familias_sin_escrituras(laboratorios, juego):
    datos = laboratorios(juego)
    e = datos["e"]
    antes = f4.arbol(e.raiz)
    try:
        with f4.cliente(e, laboratorio=datos["lab"], carteras=datos["carteras"]) as cliente:
            respuesta = cliente.get("/laboratorio/experimentos/" + datos["experimento"])
            assert respuesta.status_code == 200
            for entrada in lm.candidatos_del_juego(juego):
                assert entrada.nombre in respuesta.text
        assert f4.arbol(e.raiz) == antes
    finally:
        f4.limpiar()

def _escritor(raiz, artefacto, contenido, inicio, cola):
    try:
        assert inicio.wait(20)
        publicado = LaboratorioFileStore(Path(raiz)).guardar_modelo(artefacto, contenido)
        cola.put(("publicado", publicado.identificador))
    except FileExistsError:
        cola.put(("reutilizado", artefacto["clave"]))
    except BaseException as error:
        cola.put(("error", repr(error)))


def _lector(raiz, inicio, terminar, cola, listo, primera_lectura):
    consultas = 0
    try:
        store = LaboratorioFileStore(Path(raiz))
        listo.set()
        assert inicio.wait(20)
        limite = time.monotonic() + PLAZO_PROCESO
        while not terminar.is_set() and time.monotonic() < limite:
            for modelo in store.modelos("BALOTO"):
                assert isinstance(modelo, GuardadoModelo), modelo
                assert mr.sha256(store.leer_estimador(modelo)) == modelo.artefacto["estimador"]["sha256"]
            consultas += 1
            primera_lectura.set()
            time.sleep(0.002)
        cola.put(("lector", consultas))
    except BaseException as error:
        cola.put(("error", repr(error)))


@pytest.mark.parametrize("modelo", NUMERICOS)
def test_publicacion_nuevo_formato_con_dos_escritores_y_lectores(laboratorios, tmp_path, modelo):
    datos = laboratorios("BALOTO")
    store = datos["e"].almacen_laboratorio
    original = store.obtener_modelo(datos["versiones"][modelo]["modelo_registrado"])
    contenido = store.leer_estimador(original)
    raiz = tmp_path / CARPETA_CONCURRENCIA
    contexto = multiprocessing.get_context("spawn")
    inicio, terminar, cola = contexto.Event(), contexto.Event(), contexto.Queue()
    escritores = [contexto.Process(target=_escritor, args=(str(raiz), original.artefacto, contenido, inicio, cola))
                   for _ in range(2)]
    listo, primera_lectura = contexto.Event(), contexto.Event()
    lector = contexto.Process(target=_lector, args=(str(raiz), inicio, terminar, cola, listo, primera_lectura))
    procesos = [lector, *escritores]
    try:
        lector.start()
        assert listo.wait(PLAZO_PROCESO)
        inicio.set()
        assert primera_lectura.wait(PLAZO_PROCESO)
        for proceso in escritores:
            proceso.start()
        for proceso in escritores:
            proceso.join(PLAZO_PROCESO)
            assert not proceso.is_alive() and proceso.exitcode == 0
        terminar.set()
        lector.join(PLAZO_PROCESO)
        assert not lector.is_alive() and lector.exitcode == 0
        mensajes = [cola.get(timeout=5) for _ in procesos]
        assert sorted(m[0] for m in mensajes) == ["lector", "publicado", "reutilizado"], mensajes
        assert next(v for k, v in mensajes if k == "lector") >= 1
        finales = LaboratorioFileStore(raiz).modelos("BALOTO")
        assert len(finales) == 1 and isinstance(finales[0], GuardadoModelo)
        assert finales[0].identificador == original.identificador
        assert LaboratorioFileStore(raiz).leer_estimador(finales[0]) == contenido
        assert list(raiz.rglob("*.mljson")), "las familias nuevas deben usar el formato versionado nuevo"
        assert not list(raiz.rglob("*.tmp"))
    finally:
        terminar.set()
        for proceso in procesos:
            if proceso.pid is not None:
                if proceso.is_alive():
                    proceso.terminate()
                proceso.join(5)
        cola.close()
        cola.join_thread()


def test_catalogo_conserva_seis_recetas_y_agrega_cinco_por_juego():
    for juego in JUEGOS:
        entradas = lm.candidatos_del_juego(juego)
        ids = [e.id for e in entradas]
        assert len(ids) == len(set(ids)) == 11
        assert set(modelos(juego)) <= set(ids)
        assert len([i for i in ids if i not in modelos(juego)]) == 6
        assert all(lm.registrable(lm.CATALOGO[i]) for i in modelos(juego))
    assert not lm.FAMILIAS_FUTURAS


if __name__ == "__main__":
    analizador = argparse.ArgumentParser()
    analizador.add_argument("--recargar", nargs=3, required=True)
    argumentos = analizador.parse_args()
    print(json.dumps(_recargar(*argumentos.recargar), ensure_ascii=False))
