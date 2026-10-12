"""Fase 3 -Random Forest y Extra Trees en el laboratorio: catalogo,
coherencia de probabilidades y conteos, seleccion de parametros separada de
la evaluacion final, ausencia de fuga temporal, incidencias por candidato,
metricas secundarias, limite de tiempo del trabajador y conservacion de las
comparaciones de Producto 5. Datos sinteticos; nada es real."""
from __future__ import annotations

import dataclasses
import time

import numpy as np
import pytest

from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_ensemble as ce
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from tests.unit import fixtures_producto4 as f4

BOSQUES = {"BALOTO": ("random_forest_clasificador", "extra_trees_clasificador"),
           "BALOTO_REVANCHA": ("random_forest_clasificador", "extra_trees_clasificador"),
           "MILOTO": ("random_forest_clasificador", "extra_trees_clasificador"),
           "COLORLOTO": ("random_forest_poisson", "extra_trees_poisson")}


def test_catalogo_ampliado_conserva_las_entradas_anteriores_y_la_uniforme():
    for codigo, bosques in BOSQUES.items():
        ids = [e.id for e in lm.candidatos_del_juego(codigo)]
        assert ids[-2:] == list(bosques)  # al final: el orden anterior no cambia
        assert ids[:-2] == list(ce.CANDIDATOS_DE_COMPARACION[codigo])
        assert any(lm.CATALOGO[i].familia == "uniforme" for i in ids)
        assert any(lm.CATALOGO[i].familia == "estrategia_actual" for i in ids)
    for i in ("random_forest_clasificador", "extra_trees_clasificador", "random_forest_poisson", "extra_trees_poisson"):
        e = lm.CATALOGO[i]
        assert e.tipo == "modelo_nuevo" and e.familia == "bosques" and lm.registrable(e)
        assert e.parametros["rejilla"] == {"max_depth": [4, 8], "min_samples_leaf": [20, 80]}
    assert lm.CATALOGO["random_forest_poisson"].parametros["criterion"] == "poisson"
    assert lm.CATALOGO["random_forest_clasificador"].parametros["bootstrap"] is True
    assert lm.CATALOGO["extra_trees_clasificador"].parametros["bootstrap"] is False


def test_las_familias_futuras_no_se_declaran_implementadas():
    assert set(lm.FAMILIAS_FUTURAS) == {"xgboost", "lightgbm", "redes_neuronales", "bayesianos", "markov"}
    familias = {e.familia for e in lm.CATALOGO.values()} | {e.id for e in lm.CATALOGO.values()}
    assert not familias & set(lm.FAMILIAS_FUTURAS)
    assert all("extension futura" in texto for texto in lm.FAMILIAS_FUTURAS.values())


@pytest.mark.parametrize("codigo,n", [("BALOTO", 110), ("MILOTO", 87), ("COLORLOTO", 90)])
def test_coherencia_de_probabilidades_y_conteos(codigo, n):
    instantanea = lv.validar_instantanea(codigo, f4.historico(codigo, n))
    v = lv.Variables(instantanea)
    filas = v.filas([len(instantanea)])
    for modelo in BOSQUES[codigo]:
        ajustado = lm.ajustar_candidato(lm.CATALOGO[modelo], instantanea, v, len(instantanea), "reducido")
        p = ajustado.predecir(filas)
        assert np.all(np.isfinite(p)) and np.all((p > 0) & (p < 1))
        if codigo == "COLORLOTO":  # distribucion de pares: suma 1; 6 balotas con multiplicidad
            assert abs(p.sum() - 1) < 1e-12 and len(p) == 7 * len(instantanea.paleta())
            assert "seleccion" in ajustado.detalle and ajustado.detalle["seleccion"]["criterio"] == "Log Loss por balota"
        else:  # marginales de aparicion: suman la cantidad del sorteo
            assert abs(p.sum() - instantanea.reglas.cantidad) < lm.TOLERANCIA_CARDINALIDAD * 10
            assert ajustado.detalle["objetivos_base"][2] >= 20 and ajustado.detalle["objetivos_de_calibracion"][2] >= 10
        assert ajustado.parametros["max_depth"] in (4, 8) and "rejilla" not in ajustado.parametros


@pytest.fixture
def espia_de_seleccion(monkeypatch):
    registros = []
    monkeypatch.setattr(lm, "OBSERVADOR_DE_SELECCION", lambda modelo, corte, ajuste, validacion: registros.append(
        {"modelo": modelo, "corte": corte, "ajuste": list(ajuste), "validacion": list(validacion)}))
    ajustes = []
    monkeypatch.setattr(lm, "OBSERVADOR_DE_AJUSTE", lambda modelo, corte, base, calibracion, filas: ajustes.append(
        {"modelo": modelo, "corte": corte, "base": list(base), "calibracion": list(calibracion)}))
    return registros, ajustes


def test_seleccion_separada_de_la_calibracion_y_de_la_evaluacion_final(espia_de_seleccion):
    registros, ajustes = espia_de_seleccion
    instantanea = lv.validar_instantanea("MILOTO", f4.historico("MILOTO", 87))
    entradas = [lm.CATALOGO[i] for i in ("uniforme", *BOSQUES["MILOTO"])]
    informe, _ = le.evaluar(instantanea, entradas, le.Protocolo(perfil="reducido"))
    bloques = informe["muestra_comun"]["bloques"]
    assert len(registros) == 2 * len(bloques)
    for r in registros:
        bloque = next(b for b in bloques if b["posicion_de_ajuste"] == r["corte"])
        ajuste = next(a for a in ajustes if a["modelo"] == r["modelo"] and a["corte"] == r["corte"])
        assert max(r["ajuste"]) < min(r["validacion"])                 # validacion posterior al ajuste interno
        assert set(r["ajuste"]) | set(r["validacion"]) == set(ajuste["base"])  # todo dentro del bloque base
        assert max(r["validacion"]) < min(ajuste["calibracion"])       # la calibracion queda fuera de la seleccion
        assert max(ajuste["calibracion"]) < min(bloque["objetivos"])   # y todo antes del bloque evaluado
        assert len(r["validacion"]) >= lm.OBJETIVOS_DE_VALIDACION
    for c in informe["candidatos"]:
        if c["familia"] == "bosques":
            for b in c["bloques"]:
                sel = b["ajuste"]["seleccion"]
                assert sel["elegidos"] in [p["parametros"] for p in sel["puntos"]]
                assert min(sel["puntos"], key=lambda p: p["log_loss"])["parametros"] == sel["elegidos"]


def test_seleccion_en_colorloto_tambien_es_anterior_al_bloque(espia_de_seleccion):
    registros, _ = espia_de_seleccion
    instantanea = lv.validar_instantanea("COLORLOTO", f4.historico("COLORLOTO", 90))
    entradas = [lm.CATALOGO[i] for i in ("uniforme_paleta", *BOSQUES["COLORLOTO"])]
    informe, _ = le.evaluar(instantanea, entradas, le.Protocolo(perfil="reducido"))
    for r in registros:
        primer_objetivo = next(b for b in informe["muestra_comun"]["bloques"]
                               if b["posicion_de_ajuste"] == r["corte"])["todos"][0]
        assert max(r["validacion"]) < primer_objetivo and max(r["ajuste"]) < min(r["validacion"])


def test_sin_fuga_temporal_cambiar_el_bloque_evaluado_no_cambia_el_ajuste_anterior():
    original = f4.historico("BALOTO", 110)
    a = lv.validar_instantanea("BALOTO", original)
    t = 90
    cambiado = list(original)
    for i in range(t, len(original)):  # el objetivo y todo lo posterior
        cambiado[i] = dataclasses.replace(original[i], numeros=(1, 2, 3, 4, 5))
    b = lv.validar_instantanea("BALOTO", cambiado)
    va, vb = lv.Variables(a), lv.Variables(b)
    for modelo in BOSQUES["BALOTO"]:
        pa = lm.ajustar_candidato(lm.CATALOGO[modelo], a, va, t, "reducido").predecir(va.filas([t]))
        pb = lm.ajustar_candidato(lm.CATALOGO[modelo], b, vb, t, "reducido").predecir(vb.filas([t]))
        assert np.array_equal(pa, pb), modelo


def test_incidencias_por_candidato_sin_bloquear_a_los_demas():
    instantanea = lv.validar_instantanea("BALOTO", f4.historico("BALOTO", 70))
    entradas = lm.candidatos_del_juego("BALOTO")
    informe, _ = le.evaluar(instantanea, entradas, le.Protocolo(bloques=2, perfil="reducido"))
    estados = {c["id"]: c["estado"] for c in informe["candidatos"]}
    assert estados["actual_logistica_ae36"] == "no_disponible"  # AE-36 necesita 150 sorteos: muestra insuficiente
    assert estados["random_forest_clasificador"] == "completo" and estados["extra_trees_clasificador"] == "completo"
    ae36 = next(c for c in informe["candidatos"] if c["id"] == "actual_logistica_ae36")
    assert {i["estado"] for i in ae36["incidencias"]} == {"muestra_insuficiente"}
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        lm.ajustar_candidato(lm.CATALOGO["random_forest_clasificador"], instantanea, lv.Variables(instantanea), 40)
    assert error.value.estado == "muestra_insuficiente"


def test_seleccion_sin_clases_se_informa_como_fallo_de_ajuste():
    instantanea = lv.validar_instantanea("BALOTO", f4.historico("BALOTO", 110))
    filas = lv.Variables(instantanea).de_ajuste(80)
    sin_apariciones = dataclasses.replace(filas, y=np.zeros_like(filas.y))
    entrada = lm.CATALOGO["random_forest_clasificador"]
    objetivos = sorted(set(filas.objetivos.tolist()))
    with pytest.raises(lm.CandidatoNoDisponible) as error:
        lm._seleccionar(entrada, lm.parametros_de(entrada, "reducido"), sin_apariciones, objetivos, 80, 5)
    assert error.value.estado == "fallo_de_ajuste"


def test_metricas_secundarias_derivadas_de_los_aciertos():
    candidato = {"por_objetivo": [{"aciertos": 1, "filas": 43}, {"aciertos": 0, "filas": 43},
                                  {"aciertos": 2, "filas": 43}]}
    s = le.metricas_secundarias(candidato, colores=False, cantidad=5)
    assert s["precision_en_k"] == s["exhaustividad_en_k"] == s["f1_en_k"] == round(3 / 15, 6)
    assert s["exactitud"] == round((3 * 43 - 30 + 6) / (3 * 43), 6)
    c = le.metricas_secundarias({"por_objetivo": [{"aciertos": 2, "filas": 42}]}, colores=True, cantidad=1)
    assert c["k"] == 6 and c["precision_en_k"] == round(2 / 6, 6) and c["exactitud"] is None
    assert le.metricas_secundarias({"por_objetivo": []}, False, 5) is None


def test_la_comparacion_de_producto_5_no_cambia_con_los_bosques():
    for codigo in lv.JUEGOS:
        instantanea = lv.validar_instantanea(codigo, f4.historico(codigo, 90 if codigo != "MILOTO" else 87))
        identidad = ca.identidad_de_comparacion(instantanea, ce.ProtocoloCarteras(perfil="reducido"))
        ids = [c["id"] for c in identidad["candidatos"]]
        assert ids == [*ce.CANDIDATOS_DE_COMPARACION[codigo], ce.ID_ENSEMBLE]
        assert not any(i in ids for i in BOSQUES[codigo])
        # los bosques si se pueden usar para generar carteras
        assert set(BOSQUES[codigo]) <= set(ce.modelos_de_cartera(codigo))


def test_el_trabajador_del_laboratorio_respeta_su_tiempo_maximo():
    from app.application.interfaces.ejecutor_laboratorio import TiempoAgotadoError
    from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso

    ejecutor = EjecutorEnProceso(tiempo_maximo=3)
    inicio = time.monotonic()
    with pytest.raises(TiempoAgotadoError):
        ejecutor.ejecutar_tarea({"tipo": "dormir", "segundos": 120})
    assert time.monotonic() - inicio < 60 and ejecutor.activos == 0
