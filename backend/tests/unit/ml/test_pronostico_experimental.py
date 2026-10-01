"""Producto 1: linea de pronostico experimental de Baloto y Revancha.

Reproducibilidad, ausencia de fuga temporal, comparacion con la
referencia uniforme usando las metricas del repositorio, superbalota
como objetivo separado, contrato de uso experimental y limites. Los
historicos son sinteticos (fixtures), nunca sorteos reales."""
from __future__ import annotations

import ast
import dataclasses
import math
from pathlib import Path

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml import pronostico_experimental as pe
from app.application.ml.baselines import baseline_uniforme
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.metricas import evaluar
from app.application.ml.modelo import entrenar_modelo_calibrado, predecir_probabilidades
from tests.unit import fixtures_producto1 as fx

RAIZ_BACKEND = Path(__file__).resolve().parents[3]
CONFIG = pe.ConfiguracionExperimental(tamano_bloque=10, bloques_de_evaluacion=3, minimo_objetivos_de_entrenamiento=40)


def _generar(historico, codigo="BALOTO", configuracion=CONFIG, **kwargs):
    return pe.generar_pronostico(historico, codigo_juego=codigo, rango_min=1, rango_max=43, cantidad_numeros=5,
                                 rango_superbalota=(1, 16), configuracion=configuracion, **kwargs)


@pytest.fixture(scope="module")
def historico():
    return fx.historico_numerico("BALOTO", 160)


@pytest.fixture(scope="module")
def cuerpo(historico):
    return _generar(historico)


def test_cuerpo_completo_y_contrato_experimental(cuerpo):
    assert cuerpo["esquema"] == "pronostico-experimental/1"
    assert cuerpo["estado_de_uso"] == "experimental_no_acreditado"
    assert cuerpo["contexto"] == {"decision_ae39": "no_go_sin_evidencia_suficiente", "AUTORIZA_EVALUACION": False,
                                  "estado_operativo_ae41": "sin cambios; este pronostico usa el contrato experimental",
                                  "resultado_acreditado": False}
    contrato = cuerpo["contrato_de_uso"]
    assert any("NO-GO de AE-39" in t for t in contrato["no_permite"])
    assert any("AUTORIZA_EVALUACION" in t for t in contrato["no_permite"])
    assert any("no prueba anterioridad" in t for t in contrato["consecuencias"])
    p = cuerpo["pronostico"]
    assert p["objetivo"] == 2081 + 160 and p["calculado_hasta_sorteo"] == 2240
    assert len(p["ranking"]) == 43 and sorted(f["numero"] for f in p["ranking"]) == list(range(1, 44))
    assert p["numeros_sugeridos"] == sorted(f["numero"] for f in p["ranking"][:5])
    probs = [f["probabilidad"] for f in p["ranking"]]
    assert probs == sorted(probs, reverse=True) and all(0 < x < 1 for x in probs)
    assert {f["probabilidad_uniforme"] for f in p["ranking"]} == {round(5 / 43, 12)}
    assert cuerpo["datos"]["corte"] == 2240 and cuerpo["datos"]["total_sorteos"] == 160
    assert cuerpo["configuracion"]["semilla"] == 42 and cuerpo["estrategia"]["numeros"] == "logistica_calibrada_ae36"


def test_reproducible_misma_huella(historico, cuerpo):
    otra = _generar(list(reversed(historico)))
    assert pe.huella_de_reproduccion(otra) == pe.huella_de_reproduccion(cuerpo)
    distinta = _generar(historico, configuracion=dataclasses.replace(CONFIG, semilla=7))
    assert distinta["configuracion"]["semilla"] == 7
    assert pe.huella_de_reproduccion(distinta) != pe.huella_de_reproduccion(cuerpo)


def test_walk_forward_bloques_y_entrenamiento_estrictamente_anterior(cuerpo):
    bloques = cuerpo["evaluacion_walk_forward"]["bloques"]
    assert [b["objetivos"] for b in bloques] == [[2211, 2220], [2221, 2230], [2231, 2240]]
    for b in bloques:
        assert b["entrenamiento"]["objetivos"][1] == b["objetivos"][0] - 1
        assert b["entrenamiento"]["objetivos"][0] == 2081 + 50
    assert cuerpo["entrenamiento_final"]["objetivos"] == [2131, 2240]


def test_ningun_dato_posterior_entra_al_entrenamiento_de_un_objetivo_anterior(historico):
    """Alterar todos los sorteos desde el primer objetivo de un bloque
    no cambia ni una fila de su entrenamiento."""
    dataset = construir_dataset_binario(historico, 1, 43, 5, "BALOTO")
    primer = 2211
    alterado = [r if r.numero_sorteo < primer else dataclasses.replace(r, numeros=(1, 2, 3, 4, 5), superbalota=16)
                for r in historico]
    dataset_alterado = construir_dataset_binario(alterado, 1, 43, 5, "BALOTO")
    original = pe.filas_de_entrenamiento(dataset.filas, primer)
    modificado = pe.filas_de_entrenamiento(dataset_alterado.filas, primer)
    assert original == modificado and original
    assert max(f.sorteo_objetivo for f in original) < primer
    assert max(f.calculado_hasta_sorteo for f in original) < primer


def test_bloques_evaluados_no_dependen_de_sorteos_posteriores(historico):
    """El rendimiento de un bloque es el mismo si se agregan sorteos
    posteriores: solo cambia la cantidad de bloques recientes."""
    corto = _generar(historico[:150])
    largo = _generar(historico)
    bloque = [b for b in largo["evaluacion_walk_forward"]["bloques"] if b["objetivos"] == [2221, 2230]][0]
    assert [b for b in corto["evaluacion_walk_forward"]["bloques"] if b["objetivos"] == [2221, 2230]][0] == bloque


def test_pronostico_final_solo_con_el_historico_hasta_el_corte(historico):
    hasta = 2200
    recortado = [r for r in historico if r.numero_sorteo <= hasta]
    con_corte = _generar(recortado, hasta_numero_sorteo=hasta)
    assert con_corte["pronostico"]["objetivo"] == hasta + 1 and con_corte["datos"]["corte"] == hasta
    with pytest.raises(pe.PronosticoExperimentalError, match="posteriores al corte"):
        _generar(historico, hasta_numero_sorteo=hasta)


def test_metricas_con_las_definiciones_del_repositorio(historico, cuerpo):
    """Recalculo independiente del primer bloque con dataset, modelo,
    `metricas.evaluar` y `baseline_uniforme`."""
    dataset = construir_dataset_binario(historico, 1, 43, 5, "BALOTO")
    entrenamiento = pe.filas_de_entrenamiento(dataset.filas, 2211)
    evaluadas = [f for f in dataset.filas if 2211 <= f.sorteo_objetivo <= 2220]
    modelo = entrenar_modelo_calibrado(entrenamiento, semilla=42, proporcion_calibracion=0.2)
    m = evaluar(evaluadas, predecir_probabilidades(modelo, evaluadas))
    u = baseline_uniforme(evaluadas, 1, 43, 5).metricas
    bloque = cuerpo["evaluacion_walk_forward"]["bloques"][0]
    assert bloque["modelo"]["log_loss"] == round(m.log_loss, 12)
    assert bloque["modelo"]["brier"] == round(m.brier_score, 12)
    assert bloque["modelo"]["aciertos_top5_por_sorteo"] == round(5 * m.precision_en_5, 12)
    assert bloque["referencia_uniforme"]["log_loss"] == round(u.log_loss, 12)
    p = 5 / 43
    assert math.isclose(u.log_loss, -(p * math.log(p) + (1 - p) * math.log(1 - p)), rel_tol=1e-9)
    assert bloque["modelo"]["sorteos"] == 10 and bloque["modelo"]["filas"] == 430


def test_comparacion_y_veredicto_cuando_el_modelo_pierde():
    m = {"log_loss": 0.40, "brier": 0.11, "aciertos_top5_por_sorteo": 0.6}
    u = {"log_loss": 0.36, "brier": 0.10, "aciertos_top5_por_sorteo": 0.5}
    c = pe._comparacion(m, u)
    assert c == {"log_loss": "referencia_uniforme", "brier": "referencia_uniforme", "aciertos_top5": "modelo",
                 "veredicto": "el_modelo_no_supera_a_la_referencia_uniforme"}
    assert pe._comparacion(u, m)["veredicto"] == "el_modelo_supera_a_la_referencia_en_log_loss_y_brier"


def test_el_flujo_sigue_aunque_el_modelo_pierda(cuerpo):
    veredicto = cuerpo["evaluacion_walk_forward"]["agregado"]["comparacion"]["veredicto"]
    assert veredicto in ("el_modelo_no_supera_a_la_referencia_uniforme",
                         "el_modelo_supera_a_la_referencia_en_log_loss_y_brier")
    assert cuerpo["pronostico"]["numeros_sugeridos"]


def test_superbalota_objetivo_separado_con_su_referencia(historico, cuerpo):
    sb = cuerpo["superbalota"]
    assert sb["rango"] == [1, 16] and sb["estrategia"] == "frecuencia_con_suavizado_de_laplace"
    probs = [f["probabilidad"] for f in sb["pronostico"]["ranking"]]
    assert math.isclose(sum(probs), 1.0, abs_tol=1e-9) and sb["pronostico"]["sugerida"] == sb["pronostico"]["ranking"][0]["superbalota"]
    w = sb["evaluacion_walk_forward"]
    assert w["estrategia"]["sorteos"] == 30
    assert w["referencia_uniforme"]["log_loss"] == round(math.log(16), 12)
    assert w["referencia_uniforme"]["brier"] == round(1 - 1 / 16, 12)
    # Recalculo manual: cada objetivo evaluado usa solo superbalotas anteriores.
    perdidas = []
    for objetivo in range(2211, 2241):
        previos = [r.superbalota for r in historico if r.numero_sorteo < objetivo]
        real = next(r for r in historico if r.numero_sorteo == objetivo).superbalota
        perdidas.append(-math.log((previos.count(real) + 1) / (len(previos) + 16)))
    assert w["estrategia"]["log_loss"] == round(sum(perdidas) / len(perdidas), 12)
    # Los numeros principales no dependen de la superbalota.
    sin_sb = [dataclasses.replace(r, superbalota=None) for r in historico]
    otro = _generar(sin_sb)
    assert otro["pronostico"] == cuerpo["pronostico"] and otro["superbalota"]["evaluacion_walk_forward"]["estrategia"] is None


def test_historico_insuficiente_y_entradas_invalidas(historico):
    with pytest.raises(pe.PronosticoExperimentalError, match="Historico insuficiente"):
        _generar(historico[:95])
    with pytest.raises(pe.PronosticoExperimentalError, match="no tiene sorteos"):
        _generar([])
    for codigo in ("MILOTO", "COLORLOTO"):
        with pytest.raises(pe.PronosticoExperimentalError, match="no admite pronostico experimental"):
            _generar(historico, codigo=codigo)
    malo = [*historico[:-1], dataclasses.replace(historico[-1], numeros=(1, 2, 3, 4, 44))]
    with pytest.raises(pe.PronosticoExperimentalError, match="fuera de"):
        _generar(malo)
    duplicado = [*historico, historico[-1]]
    with pytest.raises(ValueError):
        _generar(duplicado)
    with pytest.raises(pe.PronosticoExperimentalError):
        pe.ConfiguracionExperimental(tamano_bloque=0)
    with pytest.raises(pe.PronosticoExperimentalError):
        pe.ConfiguracionExperimental(proporcion_calibracion=0.9)


def test_artefacto_huella_y_comprobacion(cuerpo, historico):
    artefacto = pe.componer_artefacto(cuerpo, generado_en="2026-10-01T00:00:00+00:00")
    assert artefacto["huella_de_reproduccion"] == pe.huella_de_reproduccion(cuerpo)
    assert "no prueba anterioridad" in artefacto["generacion"]["nota"]
    assert pe.cuerpo_del_artefacto(artefacto) == cuerpo
    r = pe.comprobar_reproduccion(artefacto, _generar(historico))
    assert r == {"huella_exacta": True, "mismos_datos": True, "mismos_numeros_sugeridos": True,
                 "maxima_diferencia_de_probabilidad": 0.0}
    cambiado = [*historico[:-1], dataclasses.replace(historico[-1], numeros=(1, 2, 3, 4, 5))]
    r = pe.comprobar_reproduccion(artefacto, _generar(cambiado))
    assert r["mismos_datos"] is False and r["huella_exacta"] is False


def test_huella_del_historico_cambia_con_un_dato():
    h = fx.historico_numerico("BALOTO", 3)
    otro = [*h[:2], dataclasses.replace(h[2], superbalota=(h[2].superbalota % 16) + 1)]
    assert pe.huella_del_historico(h) != pe.huella_del_historico(otro)
    assert len(pe.huella_del_historico(h)) == 64


def test_revancha_independiente_de_baloto():
    baloto = fx.historico_numerico("BALOTO", 160)
    revancha = fx.historico_numerico("BALOTO_REVANCHA", 160)
    a = _generar(baloto)
    b = _generar(revancha, codigo="BALOTO_REVANCHA")
    assert b["juego"] == "BALOTO_REVANCHA" and a["datos"]["sha256_historico"] != b["datos"]["sha256_historico"]


def test_modulo_puro_sin_reloj_red_ni_sklearn_directo():
    ruta = RAIZ_BACKEND / "app" / "application" / "ml" / "pronostico_experimental.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos = {a.name.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
    modulos |= {(n.module or "").split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
    assert not modulos & {"sklearn", "numpy", "socket", "urllib", "requests", "sqlalchemy", "time", "datetime",
                          "random", "pickle", "fastapi"}
    atributos = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    assert not atributos & {"now", "utcnow", "today", "write_bytes", "write_text"}
    assert not [n for n in ast.walk(arbol) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "open"]


def test_no_modifica_estado_operativo_ni_no_go():
    """El contrato experimental no toca AE-39, AE-41 ni AUTORIZA_EVALUACION."""
    from app.application.ml.propuesta_inferencia_prospectiva import AUTORIZA_EVALUACION
    from app.application.ml.tipos import DecisionContinuidadML
    from app.application.use_cases.resolver_estado_prediccion import DECISIONES_CONTINUIDAD_AE39

    assert AUTORIZA_EVALUACION is False
    assert set(DECISIONES_CONTINUIDAD_AE39.values()) == {DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE}
    for nombre in ("autorizacion_operativa.py", "reapertura.py", "prediccion_bloqueada.py", "inferencia.py"):
        texto = (RAIZ_BACKEND / "app" / "application" / "ml" / nombre).read_text(encoding="utf-8")
        assert "pronostico_experimental" not in texto, nombre


def test_resultado_real_no_se_inventa():
    """Las fixtures se declaran sinteticas y el modulo no contiene datos."""
    assert "SINTETICAS" in (RAIZ_BACKEND / "tests" / "unit" / "fixtures_producto1.py").read_text(encoding="utf-8")
    assert isinstance(fx.historico_numerico("BALOTO", 1)[0], ResultadoNumerico)
