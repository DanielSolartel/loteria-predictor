"""Registro nuevo: manifiestos antes de native load; formatos históricos intactos."""
from __future__ import annotations

import copy
import json

import pytest
from threadpoolctl import threadpool_limits

from app.application.interfaces.laboratorio_store import GuardadoModelo
from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import modelos_registrados as mr
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from tests.unit import fixtures_producto4 as f4


@pytest.fixture(scope="module")
def nueva_version():
    ins = lv.validar_instantanea("BALOTO", f4.historico("BALOTO", 120))
    entrada = lm.CATALOGO["xgboost_binario"]
    protocolo = le.Protocolo(bloques=1, perfil="reducido")
    entradas = [lm.CATALOGO["uniforme"], entrada]
    identidad = la.identidad_del_experimento(ins, entradas, protocolo)
    with threadpool_limits(limits=1):
        evaluacion, _ = le.evaluar(ins, entradas, protocolo)
        informe = la.componer(la.cuerpo_del_experimento(ins, identidad, evaluacion), "ejecucion", {})
        entrenado = mr.entrenar(informe, entrada)
    identidad = mr.identidad_del_modelo(informe, entrada)
    cuerpo = mr.cuerpo_del_modelo(informe, entrada, identidad, entrenado)
    return mr.componer(cuerpo, {"numero": 1}), entrenado["contenido"], informe


def _resellar(artefacto):
    return mr.componer(mr.cuerpo_de(artefacto), artefacto["publicacion"])


def test_formato_nuevo_y_control_congelado(nueva_version, tmp_path, monkeypatch):
    artefacto, contenido, informe = nueva_version
    assert artefacto["identidad"]["registro"] == mr.VERSION_REGISTRO_ML
    assert artefacto["estimador"]["formato"] == mr.FORMATO_ML
    assert json.loads(contenido)["esquema"] == mr.ESQUEMA_ESTIMADOR_ML
    store = LaboratorioFileStore(tmp_path / "r ml")
    guardado = store.guardar_modelo(artefacto, contenido)
    assert isinstance(guardado, GuardadoModelo)
    assert len(list(tmp_path.rglob("*.mljson"))) == 1
    assert not list(tmp_path.rglob("*.pkl"))
    from app.application.ml import laboratorio_boosts_redes as br
    monkeypatch.setattr(br, "ajustar_boost_red", lambda *a, **k: pytest.fail("inferir no debe ajustar"))
    recargado = mr.cargar_estimador(guardado.artefacto, store.leer_estimador(guardado))
    ins = la.instantanea_del_experimento(informe)
    candidatos, p = mr.predecir_congelado(recargado, guardado.artefacto["identidad"], ins)
    assert mr.control_de(candidatos, p)["sha256_probabilidades"] == artefacto["control"]["sha256_probabilidades"]
    assert not store.huerfanos()


@pytest.mark.parametrize("campo", ["version", "formato", "sha256_contenido", "preparacion"])
def test_estado_interno_alterado_se_rechaza(nueva_version, campo):
    artefacto, contenido, _ = nueva_version
    a = copy.deepcopy(artefacto)
    d = json.loads(contenido)
    d["estimador"].pop(campo)
    b = la.serializar_entrada(d)
    a["estimador"].update({"sha256": mr.sha256(b), "bytes": len(b)})
    with pytest.raises(mr.ModeloRegistradoError):
        mr.cargar_estimador(_resellar(a), b)


@pytest.mark.parametrize("cambio", ["integridad", "version", "receta", "procedencia", "variables", "formato"])
def test_guardas_preceden_al_cargador_nativo(nueva_version, monkeypatch, cambio):
    artefacto, contenido, _ = nueva_version
    a = copy.deepcopy(artefacto)
    if cambio == "integridad":
        a["sello"] = "0" * 64
    elif cambio == "version":
        a["identidad"]["entorno"]["xgboost"] = "0.0.0"
    elif cambio == "receta":
        a["identidad"]["modelo"]["parametros"]["num_boost_round"] = 999
    elif cambio == "procedencia":
        a["procedencia"]["experimento"] = "0" * 64
    elif cambio == "variables":
        a["identidad"]["variables"]["version"] = "futuro"
    elif cambio == "formato":
        a["estimador"]["formato"] = mr.FORMATO_DEL_ESTIMADOR
    if cambio != "integridad":
        # La clave se recalcula para no confundir integridad con compatibilidad.
        a["clave"] = mr.huella(a["identidad"])
        a = _resellar(a)
    from app.application.ml import laboratorio_boosts_redes as br
    monkeypatch.setattr(br, "deserializar_boost_red", lambda *args: pytest.fail("no debe llegar a native load"))
    with pytest.raises(mr.ModeloRegistradoError):
        mr.cargar_estimador(a, contenido)


def test_bytes_y_tamano_antes_del_cargador(nueva_version, monkeypatch):
    artefacto, contenido, _ = nueva_version
    from app.application.ml import laboratorio_boosts_redes as br
    monkeypatch.setattr(br, "deserializar_boost_red", lambda *args: pytest.fail("bytes alterados"))
    with pytest.raises(mr.ModeloRegistradoError, match="alterado"):
        mr.cargar_estimador(artefacto, contenido + b" ")


def test_identidad_interna_incorrecta_antes_del_cargador(nueva_version, monkeypatch):
    artefacto, contenido, _ = nueva_version
    d = json.loads(contenido)
    d["estimador"]["candidato_id"] = "xgboost_poisson"
    b = la.serializar_entrada(d)
    a = copy.deepcopy(artefacto)
    a["estimador"].update({"sha256": mr.sha256(b), "bytes": len(b)})
    from app.application.ml import laboratorio_boosts_redes as br
    monkeypatch.setattr(br, "deserializar_boost_red", lambda *args: pytest.fail("identidad incompatible"))
    with pytest.raises(mr.ModeloRegistradoError):
        mr.cargar_estimador(_resellar(a), b)


def test_control_exige_su_informe(nueva_version):
    artefacto, contenido, informe = nueva_version
    otro = copy.deepcopy(informe)
    otro["clave"] = "0" * 64
    with pytest.raises(mr.ModeloRegistradoError, match="procedencia"):
        mr.control_recargado(artefacto, contenido, otro)


def test_manifiesto_incompleto_es_estado_explicito(nueva_version):
    artefacto, contenido, _ = nueva_version
    a = copy.deepcopy(artefacto)
    a["identidad"].pop("variables")
    a["clave"] = mr.huella(a["identidad"])
    a = _resellar(a)
    assert mr.compatibilidad(a)["compatible"] is False
    with pytest.raises(mr.ModeloRegistradoError, match="incompatible"):
        mr.cargar_estimador(a, contenido)


def test_pickle_no_admite_el_modulo_nuevo():
    import pickle
    from app.application.ml.laboratorio_boosts_redes import Preparacion
    contenido = pickle.dumps(Preparacion, protocol=5)
    with pytest.raises(mr.ModeloRegistradoError, match="no_admitido"):
        mr.deserializar_estimador(contenido, mr.sha256(contenido), len(contenido))


def test_entorno_historico_no_incluye_bibliotecas_nuevas():
    assert "xgboost" not in la.entorno()
    assert "lightgbm" not in la.entorno()
    assert la.entorno_ml((lm.CATALOGO["logistica_regularizada"],)) == la.entorno()
    assert "xgboost" in la.entorno_ml((lm.CATALOGO["xgboost_binario"],))


@pytest.mark.parametrize("campo", ["control", "componentes", "entrenamiento", "datos", "procedencia", "contexto"])
def test_secciones_obligatorias_antes_de_native(nueva_version, monkeypatch, campo):
    artefacto, contenido, _ = nueva_version
    a = copy.deepcopy(artefacto)
    a.pop(campo)
    a = _resellar(a)
    from app.application.ml import laboratorio_boosts_redes as br
    monkeypatch.setattr(br, "deserializar_boost_red", lambda *args: pytest.fail("manifest incompleto no debe cargar"))
    assert mr.compatibilidad(a)["compatible"] is False
    with pytest.raises(mr.ModeloRegistradoError, match="incompatible"):
        mr.cargar_estimador(a, contenido)
