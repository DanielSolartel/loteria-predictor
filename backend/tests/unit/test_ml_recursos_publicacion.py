"""Recursos de bibliotecas tardías y publicación .mljson con presupuesto Win32.

Las rutas se miden con un presupuesto portable; no acredita el kernel Windows.
El aislamiento sí usa procesos spawn y los dos motores nativos reales en CPU.
"""
from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from tests.unit.test_ml_cinco_flujo import NUMERICOS, laboratorios  # fixture real, sin dobles de ML
from tests.unit.test_producto5_rutas import _presupuesto

BACKEND = Path(__file__).resolve().parents[2]


def _nativos_tardios(cola):
    from app.infrastructure.recursos_ml import limitar_trabajador
    import numpy as np
    anteriores = {n: os.environ.get(n) for n in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
    limite = limitar_trabajador(2)
    try:
        import xgboost as xgb
        import lightgbm as lgb
        from threadpoolctl import threadpool_info
        X = np.arange(256, dtype=float).reshape(64, 4) / 256
        y = (np.arange(64) % 3 == 0).astype(float)
        xgb.train({"objective": "binary:logistic", "max_depth": 2, "nthread": 1, "seed": 42},
                  xgb.DMatrix(X, label=y, nthread=1), num_boost_round=2)
        lgb.train({"objective": "binary", "num_threads": 1, "verbosity": -1, "seed": 42,
                   "min_data_in_leaf": 2, "force_col_wise": True}, lgb.Dataset(X, label=y), num_boost_round=2)
        motores = [{"api": i["internal_api"], "hilos": i["num_threads"]} for i in threadpool_info()]
        assert motores and all(i["hilos"] <= 2 for i in motores), motores
        assert os.environ["OMP_NUM_THREADS"] == "2"
    finally:
        limite.close()
    assert {n: os.environ.get(n) for n in anteriores} == anteriores
    cola.put({"pid": os.getpid(), "motores": motores, "entorno_restaurado": True})


def _servidor():
    import numpy as np
    from threadpoolctl import threadpool_info
    np.ones((16, 16)) @ np.ones((16, 16))
    def perfil():
        return sorted((i["filepath"], i["num_threads"]) for i in threadpool_info())
    antes, variables = perfil(), {n: os.environ.get(n) for n in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
    contexto = multiprocessing.get_context("spawn")
    cola = contexto.Queue()
    hijo = contexto.Process(target=_nativos_tardios, args=(cola,))
    hijo.start()
    muestras = 0
    try:
        plazo = time.monotonic() + 90
        while hijo.is_alive() and time.monotonic() < plazo:
            assert perfil() == antes
            muestras += 1
            hijo.join(.01)
        assert not hijo.is_alive() and hijo.exitcode == 0
        resultado = cola.get(timeout=5)
        assert resultado["pid"] != os.getpid() and resultado["entorno_restaurado"]
        assert perfil() == antes and {n: os.environ.get(n) for n in variables} == variables
        assert any(n > 2 for _, n in antes)
        print(json.dumps({"muestras_servidor": muestras, "hijo": resultado, "servidor_intacto": True}))
    finally:
        if hijo.is_alive():
            hijo.kill()
        hijo.join(5)
        cola.close()
        cola.join_thread()


def test_motores_nativos_tardios_limitados_sin_alterar_servidor():
    env = {**os.environ, "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "PYTHONPATH": str(BACKEND)}
    r = subprocess.run([sys.executable, "-m", "tests.unit.test_ml_recursos_publicacion"],
                       cwd=BACKEND, env=env, capture_output=True, text=True, timeout=110)
    assert r.returncode == 0, r.stdout + r.stderr
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    assert datos["servidor_intacto"] and datos["muestras_servidor"] > 0


@pytest.mark.parametrize("modelo", NUMERICOS)
def test_publicar_mljson_y_nuevos_ids_en_limite_259(laboratorios, tmp_path, monkeypatch, modelo):
    datos = laboratorios("BALOTO_REVANCHA")
    fuente = datos["e"].almacen_laboratorio
    original = fuente.obtener_modelo(datos["versiones"][modelo]["modelo_registrado"])
    contenido = fuente.leer_estimador(original)
    store = LaboratorioFileStore(tmp_path)
    estimadores = tmp_path / "modelos" / "BALOTO_REVANCHA" / "estimadores"
    destino = estimadores / (original.artefacto["estimador"]["sha256"] + ".mljson")
    presupuesto = _presupuesto(monkeypatch, tmp_path, estimadores)
    presupuesto.desplazamiento = 259 - len(os.path.normpath(str(destino)))
    publicado = store.guardar_modelo(original.artefacto, contenido)
    assert presupuesto.longitud(destino) == 259 and destino.read_bytes() == contenido
    assert publicado.numero == 1 and store.leer_estimador(store.obtener_modelo(publicado.identificador)) == contenido
    assert not presupuesto.rechazadas and not store.temporales()
    temporales = [p for p in presupuesto.creados if p.suffix == ".tmp"]
    assert temporales and all(presupuesto.longitud(p) <= 259 for p in temporales)
    assert all(len(p.name) == 33 for p in temporales)
    assert (tmp_path / "modelos" / "BALOTO_REVANCHA" / (modelo + "-000001.version")).is_file()


def test_interrupcion_mljson_conserva_temporal_y_reintento_no_sobrescribe(laboratorios, tmp_path, monkeypatch):
    datos = laboratorios("BALOTO_REVANCHA")
    fuente = datos["e"].almacen_laboratorio
    original = fuente.obtener_modelo(datos["versiones"][NUMERICOS[0]]["modelo_registrado"])
    contenido = fuente.leer_estimador(original)
    store = LaboratorioFileStore(tmp_path)
    enlazar = os.link
    class Interrupcion(BaseException):
        pass
    with monkeypatch.context() as m:
        def interrumpir(origen, destino, *a, **k):
            if Path(destino).suffix == ".json":
                raise Interrupcion()
            return enlazar(origen, destino, *a, **k)
        m.setattr(os, "link", interrumpir)
        with pytest.raises(Interrupcion):
            store.guardar_modelo(original.artefacto, contenido)
    assert store.modelos("BALOTO_REVANCHA") == []
    temporales = {n: (tmp_path / n).read_bytes() for n in store.temporales()}
    assert len(temporales) == 1
    estimadores = list(tmp_path.rglob("*.mljson"))
    assert len(estimadores) == 1 and estimadores[0].read_bytes() == contenido
    publicado = store.guardar_modelo(original.artefacto, contenido)
    assert publicado.numero == 2 and store.leer_estimador(publicado) == contenido
    assert {n: (tmp_path / n).read_bytes() for n in store.temporales()} == temporales
    antes = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        store.guardar_modelo(original.artefacto, contenido)
    assert {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == antes


if __name__ == "__main__":
    _servidor()
