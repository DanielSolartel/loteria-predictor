"""Producto 4: muestra comun, ranking y metricas del evaluador comparadas con
un calculo independiente."""
from __future__ import annotations

import math

import numpy as np
import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import pronostico_colorloto as pcl
from tests.unit import fixtures_producto4 as f4


def _instantanea(codigo, n):
    return lv.validar_instantanea(codigo, f4.historico(codigo, n))


def test_todos_los_completos_se_miden_sobre_los_mismos_objetivos():
    instantanea = _instantanea("MILOTO", 87)
    informe, _ = le.evaluar(instantanea, lm.candidatos_del_juego("MILOTO"), le.Protocolo())
    objetivos = informe["muestra_comun"]["objetivos"]
    assert objetivos == [r.numero_sorteo for r in instantanea.sorteos[50:]]
    for c in informe["candidatos"]:
        assert [f["objetivo"] for f in c["por_objetivo"]] == objetivos
        assert c["agregado"]["sorteos"] == len(objetivos) and c["agregado"]["filas"] == 39 * len(objetivos)
    uniformes = {c["agregado"]["uniforme"]["log_loss"] for c in informe["candidatos"]}
    assert len(uniformes) == 1  # la misma referencia para todos


def test_un_candidato_parcial_no_obtiene_el_primer_puesto(monkeypatch):
    """La receta de AE-36 no alcanza su muestra minima en el primer bloque; aunque
    sus cifras parciales fueran perfectas, no entra en el ranking."""
    instantanea = _instantanea("BALOTO", 160)
    original = lm.ajustar_candidato

    def tramposo(entrada, *args, **kwargs):
        ajustado = original(entrada, *args, **kwargs)
        if entrada.id == "actual_logistica_ae36":
            ajustado._predecir = lambda f: np.where(f.y == 1, 0.99, 0.01)
        return ajustado
    monkeypatch.setattr(lm, "ajustar_candidato", tramposo)
    informe, _ = le.evaluar(instantanea, lm.candidatos_del_juego("BALOTO"), le.Protocolo(bloques=2))
    ae36 = next(c for c in informe["candidatos"] if c["id"] == "actual_logistica_ae36")
    assert ae36["estado"] == "parcial" and ae36["incidencias"][0]["estado"] == "muestra_insuficiente"
    assert ae36["agregado"]["log_loss"] < min(c["agregado"]["log_loss"] for c in informe["candidatos"]
                                              if c["estado"] == "completo")
    ranking = informe["resumen"]["ranking"]
    assert "actual_logistica_ae36" not in [r["id"] for r in ranking]
    assert [x["id"] for x in informe["resumen"]["incompletos"]] == ["actual_logistica_ae36"]
    assert "veredicto" not in ae36


def test_metricas_de_numeros_frente_a_un_calculo_independiente():
    instantanea = _instantanea("MILOTO", 87)
    posicion = 30
    objetivo = instantanea.sorteos[posicion]
    candidatos = list(range(1, 40))
    rng = np.random.default_rng(3)
    p = rng.uniform(0.02, 0.4, 39)
    y = np.array([1.0 if c in objetivo.numeros else 0.0 for c in candidatos])
    filas = lv.Filas(np.full(39, objetivo.numero_sorteo), np.full(39, posicion), tuple(candidatos),
                     np.zeros((39, 8)), y)
    m = le.metricas_por_objetivo(instantanea, filas, p)[objetivo.numero_sorteo]
    q = np.clip(p, 1e-6, 1 - 1e-6)
    assert m["log_loss"] == pytest.approx(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)), abs=1e-12)
    assert m["brier"] == pytest.approx(np.mean((p - y) ** 2), abs=1e-12)
    top = sorted(candidatos, key=lambda c: (-p[c - 1], c))[:5]
    assert m["aciertos"] == len(set(top) & set(objetivo.numeros))


def test_agregado_desde_observaciones_con_bloques_desiguales():
    instantanea = _instantanea("MILOTO", 87)
    informe, _ = le.evaluar(instantanea, lm.candidatos_del_juego("MILOTO"), le.Protocolo())
    c = next(c for c in informe["candidatos"] if c["id"] == "hgb_clasificador")
    tamanos = [len(b["objetivos"]) for b in c["bloques"]]
    assert tamanos == [10, 10, 10, 7]
    por_objetivo = [f["log_loss"] for f in c["por_objetivo"]]
    assert c["agregado"]["log_loss"] == pytest.approx(sum(por_objetivo) / len(por_objetivo), abs=1e-11)
    medias_de_bloque = [b["metricas"]["log_loss"] for b in c["bloques"]]
    assert c["agregado"]["log_loss"] != pytest.approx(sum(medias_de_bloque) / len(medias_de_bloque), abs=1e-12)
    ponderada = sum(m * t for m, t in zip(medias_de_bloque, tamanos)) / sum(tamanos)
    assert c["agregado"]["log_loss"] == pytest.approx(ponderada, abs=1e-10)
    diferencias = [f["diferencia_log_loss"] for f in c["por_objetivo"]]
    assert c["agregado"]["diferencia_log_loss"] == pytest.approx(sum(diferencias) / len(diferencias), abs=1e-11)


def test_superbalota_aparte_con_estado_fijado_al_inicio_del_bloque():
    instantanea = _instantanea("BALOTO", 120)
    informe, _ = le.evaluar(instantanea, [lm.CATALOGO["uniforme"]], le.Protocolo(bloques=1))
    sb = informe["superbalota"]
    bloque = informe["muestra_comun"]["bloques"][0]
    previos = instantanea.sorteos[:bloque["posicion_de_ajuste"]]
    conteo = {c: sum(1 for r in previos if r.superbalota == c) for c in range(1, 17)}
    perdidas = [-math.log((conteo[instantanea.sorteos[i].superbalota] + 1) / (len(previos) + 16))
                for i in range(bloque["posicion_de_ajuste"], bloque["posicion_de_ajuste"] + 10)]
    assert sb["log_loss"] == pytest.approx(sum(perdidas) / 10, abs=1e-11)
    assert sb["log_loss_uniforme"] == pytest.approx(math.log(16), abs=1e-11)
    assert sb["estrategia"] == "frecuencia_con_suavizado_de_laplace"
    assert all("superbalota" not in str(c["agregado"]) for c in informe["candidatos"])
    miloto, _ = le.evaluar(_instantanea("MILOTO", 70), [lm.CATALOGO["uniforme"]], le.Protocolo(bloques=1))
    assert "superbalota" not in miloto  # MiLoto no recibe una superbalota ficticia


def test_metricas_de_colorloto_con_multiconjuntos_repetidos():
    dist = {(1, "ROJO"): 0.3, (2, "AZUL"): 0.2, (3, "VERDE"): 0.5}
    observado = [(1, "ROJO"), (1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (3, "VERDE"), (3, "VERDE")]
    m = pcl.metricas_de_objetivo(dist, observado)
    multinomial = math.factorial(6) / (math.factorial(2) * math.factorial(1) * math.factorial(3)) * \
        0.3 ** 2 * 0.2 * 0.5 ** 3
    assert m["log_loss_multiconjunto"] == pytest.approx(-math.log(multinomial), abs=1e-12)
    assert m["log_loss_por_balota"] == pytest.approx(-(2 * math.log(0.3) + math.log(0.2) + 3 * math.log(0.5)) / 6)
    cuadrados = sum(v * v for v in dist.values())
    assert m["brier_por_balota"] == pytest.approx(sum(cuadrados - 2 * dist[b] + 1 for b in observado) / 6)
    sugerido = pcl.multiconjunto_mas_probable(dist)
    assert len(sugerido) == 6 and len(set(sugerido)) < 6  # admite repeticiones
    assert m["coincidencias_de_pares_por_sorteo"] == sum(
        min(sugerido.count(par), observado.count(par)) for par in dist)


def test_resumen_dice_la_uniforme_fue_mejor_empate_o_incompleta():
    base = {"agregado": {"diferencia_log_loss": 0.0}, "estado": "completo", "incidencias": [], "tipo": "referencia",
            "nombre": "u", "veredicto": "referencia"}
    uniforme = {**base, "id": "uniforme", "familia": "uniforme", "agregado": {"log_loss": 0.4, "diferencia_log_loss": 0.0}}
    peor = {**base, "id": "m", "familia": "lineal", "tipo": "modelo_nuevo",
            "agregado": {"log_loss": 0.41, "diferencia_log_loss": 0.01}, "veredicto": "la_uniforme_fue_mejor"}
    igual = {**peor, "id": "n", "agregado": {"log_loss": 0.4, "diferencia_log_loss": 0.0}, "veredicto": "empate"}
    mejor = {**peor, "id": "o", "agregado": {"log_loss": 0.39, "diferencia_log_loss": -0.01},
             "veredicto": "menor_perdida_que_la_uniforme_en_esta_evaluacion"}
    assert le.resumen([uniforme, peor])["estado"] == "la_uniforme_fue_mejor"
    assert le.resumen([uniforme, igual])["estado"] == "empate"
    assert le.resumen([uniforme, mejor, peor])["estado"] == "menor_perdida_en_esta_evaluacion"
    assert le.resumen([uniforme, {**peor, "estado": "parcial"}])["estado"] == "comparacion_incompleta"
