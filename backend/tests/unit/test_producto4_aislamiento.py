"""Producto 4: los entrenamientos y predicciones del laboratorio se ejecutan en
un proceso trabajador dedicado (`spawn`, igual en Windows) y el proceso que
atiende la web no cambia sus hilos numericos antes, durante ni despues.

El escenario de solapamiento corre en un proceso aislado que hace de proceso
web: dos comparaciones de juegos distintos lanzadas en hilos y forzadas a
solaparse con una barrera, generacion y verificacion, mientras un hilo
muestrea `threadpool_info()` del proceso. Tiempos maximos acotados."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.use_cases.laboratorio import LaboratorioError
from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso
from tests.unit import fixtures_producto4 as f4

BACKEND = Path(__file__).resolve().parents[2]
REDUCIDO = le.Protocolo(bloques=1, perfil="reducido")

ESCENARIO = textwrap.dedent("""
    import json, pathlib, sys, tempfile, threading, time
    from threadpoolctl import threadpool_info
    from app.application.ml import laboratorio_evaluacion as le
    from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso
    from tests.unit import fixtures_producto4 as f4

    ESPERA = 120
    def hilos():
        return sorted((i["internal_api"], i["num_threads"]) for i in threadpool_info())
    barrera = threading.Barrier(2)
    def juntos(proceso):
        barrera.wait(ESPERA)  # los dos trabajadores de comparacion vivos a la vez
    comparar = EjecutorEnProceso(al_lanzar=juntos)
    otros = EjecutorEnProceso()
    e = f4.entorno(pathlib.Path(tempfile.mkdtemp()))
    protocolo = le.Protocolo(bloques=1, perfil="reducido")
    antes = hilos()
    muestras, parar = [], threading.Event()
    def muestrear():
        while not parar.is_set():
            muestras.append(hilos()); time.sleep(0.01)
    monitor = threading.Thread(target=muestrear); monitor.start()
    resultados = {}
    def una(juego):
        resultados[juego] = e.laboratorio(ejecutor=comparar).comparar_ahora([juego], protocolo)
    hilos_comparacion = [threading.Thread(target=una, args=(j,)) for j in ("MILOTO", "COLORLOTO")]
    for h in hilos_comparacion: h.start()
    for h in hilos_comparacion: h.join(ESPERA)
    lab = e.laboratorio(ejecutor=otros)
    clave = resultados["MILOTO"]["juegos"]["MILOTO"]["experimento"]
    generado = lab.generar(clave, "hgb_clasificador")
    verif_exp = lab.verificar_experimento(clave)
    verif_pro = lab.verificar_pronostico(generado.identificador)
    parar.set(); monitor.join(ESPERA)
    print(json.dumps({"antes": antes, "despues": hilos(), "distintas": [m for m in muestras if m != antes],
                      "muestras": len(muestras), "maximo_simultaneo": comparar.maximo_simultaneo,
                      "lanzados": comparar.lanzados + otros.lanzados,
                      "estados": {j: r["estado"] for j, r in resultados.items()},
                      "generado": not generado.reutilizado,
                      "verificacion": [verif_exp["reproduccion"].get("huella_exacta"),
                                       verif_pro["reproduccion"].get("huella_exacta")]}))
""")


def test_comparaciones_solapadas_en_trabajadores_no_cambian_los_hilos_del_proceso_web():
    entorno = {**os.environ, "OPENBLAS_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "PYTHONPATH": str(BACKEND)}
    r = subprocess.run([sys.executable, "-c", ESCENARIO], cwd=BACKEND, env=entorno, capture_output=True, text=True,
                       timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    assert datos["estados"] == {"MILOTO": "exito", "COLORLOTO": "exito"}
    assert datos["maximo_simultaneo"] == 2  # dos trabajadores de comparacion vivos a la vez
    assert datos["lanzados"] >= 5  # 2 comparaciones, 1 generacion, 2 verificaciones
    assert datos["generado"] and datos["verificacion"] == [True, True]
    assert any(n > 2 for _, n in datos["antes"])
    assert datos["muestras"] > 10 and datos["distintas"] == [] and datos["despues"] == datos["antes"]


def _matar(proceso):
    proceso.kill()


def test_trabajador_interrumpido_no_publica_y_libera(tmp_path):
    e = f4.entorno(tmp_path)
    roto = e.laboratorio(ejecutor=EjecutorEnProceso(al_lanzar=_matar))
    final = roto.comparar_ahora(["MILOTO"], REDUCIDO)
    r = final["juegos"]["MILOTO"]
    assert final["estado"] == "fallo" and r["estado"] == "fallo"
    assert "proceso de entrenamiento" in r["mensaje"] and "sin resultado" in r["mensaje"]
    assert e.almacen.experimentos("MILOTO") == [] and e.almacen.temporales() == []
    assert roto.recientes()[0]["estado"] == "fallo"
    sano = e.laboratorio(ejecutor=EjecutorEnProceso())
    clave = sano.comparar_ahora(["MILOTO"], REDUCIDO)["juegos"]["MILOTO"]["experimento"]  # cerrojos libres
    with pytest.raises(LaboratorioError) as error:
        roto.generar(clave, "logistica_regularizada")
    assert error.value.codigo == "fallo_del_trabajador"
    assert roto.verificar_experimento(clave)["reproduccion"]["estado"] == "no_reproducible"
    assert e.almacen.lineas("MILOTO") == []


def test_los_errores_esperados_llegan_desde_el_trabajador(tmp_path):
    e = f4.entorno(tmp_path, {"MILOTO": 55})
    lab = e.laboratorio(ejecutor=EjecutorEnProceso())
    # la lectura (en este proceso) termina antes; el trabajador detecta la muestra insuficiente
    r = lab.comparar_ahora(["MILOTO"])["juegos"]["MILOTO"]
    assert r["estado"] == "muestra_insuficiente" and "Muestra insuficiente para MILOTO" in r["mensaje"]
    ejecutor = EjecutorEnProceso()
    instantanea = lv.validar_instantanea("MILOTO", e.cargados("MILOTO"))
    with pytest.raises(le.MuestraInsuficienteError) as error:
        ejecutor.evaluar(instantanea, [], le.Protocolo())
    assert error.value.codigo == "MILOTO"


def test_el_trabajador_y_el_proceso_actual_dan_el_mismo_informe(tmp_path):
    """Igualdad exacta con recursos equivalentes, sin alterar los del padre.

    La referencia llama directamente al evaluador en otro proceso de prueba:
    no reutiliza el ejecutor que se está contrastando ni cambia sus recetas.
    """
    from tests.ml_reproducibilidad import referencia_local
    instantanea = lv.validar_instantanea("COLORLOTO", f4.historico("COLORLOTO", 90))
    entradas = lm.candidatos_del_juego("COLORLOTO")
    avances = []
    en_trabajador, _ = EjecutorEnProceso().evaluar(instantanea, entradas, REDUCIDO,
                                                   avance=lambda fase, **d: avances.append((fase, d["candidato"])))
    local = referencia_local(instantanea, entradas, REDUCIDO, lm.HILOS)
    assert en_trabajador == local
    assert ("modelo", "hgb_poisson") in avances  # el progreso llega desde el trabajador
