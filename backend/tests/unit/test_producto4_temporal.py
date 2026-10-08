"""Producto 4: causalidad temporal del laboratorio.

- alterar todos los resultados desde el objetivo t no cambia variables,
  parametros ni probabilidades calculadas antes de conocer t (un observador
  espia registra que objetivos vio cada ajuste y cada calibracion);
- particion por sorteo (base anterior a calibracion, ambas anteriores al
  bloque; ninguna fila de un objetivo en dos particiones);
- actualizacion secuencial dentro del bloque;
- escalado y codificacion ajustados solo con el entrenamiento;
- independencia entre juegos."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from tests.unit import fixtures_producto4 as f4

NUEVOS_NUMEROS = ("logistica_regularizada", "hgb_clasificador")
NUEVOS_PARES = ("poisson_regularizado", "hgb_poisson")


def _alterado_desde(historico, posicion, semilla=777):
    """Copia con TODOS los resultados desde `posicion` sustituidos."""
    otros = f4.historico("COLORLOTO" if hasattr(historico[0], "pares") else "BALOTO", len(historico), semilla)
    salida = list(historico)
    for i in range(posicion, len(historico)):
        campo = "pares" if hasattr(historico[i], "pares") else "numeros"
        salida[i] = dataclasses.replace(historico[i], **{campo: getattr(otros[i], campo)})
    return salida


@pytest.fixture
def espia(monkeypatch):
    vistos = []

    def observar(modelo, posicion_de_corte, base, calibracion, filas):
        vistos.append({"modelo": modelo, "corte": posicion_de_corte, "base": list(base),
                       "calibracion": list(calibracion), "posiciones": set(filas.posiciones.tolist()),
                       "objetivos": set(filas.objetivos.tolist())})
    monkeypatch.setattr(lm, "OBSERVADOR_DE_AJUSTE", observar)
    return vistos


@pytest.mark.parametrize("codigo,modelos", [("BALOTO", NUEVOS_NUMEROS), ("COLORLOTO", NUEVOS_PARES)])
def test_alterar_desde_t_no_cambia_lo_calculado_antes_de_conocer_t(codigo, modelos, espia):
    n, t = (160, 150) if codigo == "BALOTO" else (90, 80)
    original = f4.historico(codigo, n)
    alterado = _alterado_desde(original, t)
    a, b = lv.validar_instantanea(codigo, original), lv.validar_instantanea(codigo, alterado)
    va, vb = lv.Variables(a), lv.Variables(b)
    antes = range(lv.CALENTAMIENTO, t + 1)  # las variables del propio objetivo t solo usan el pasado
    fa, fb = va.filas(antes), vb.filas(antes)
    assert np.array_equal(fa.X, fb.X)
    assert not np.array_equal(va.filas([t]).y, vb.filas([t]).y) or codigo == "COLORLOTO"
    for modelo in modelos:
        pa = lm.ajustar_candidato(lm.CATALOGO[modelo], a, va, t).predecir(va.filas([t]))
        pb = lm.ajustar_candidato(lm.CATALOGO[modelo], b, vb, t).predecir(vb.filas([t]))
        assert np.array_equal(pa, pb), modelo
    for registro in espia:
        assert max(registro["posiciones"]) < registro["corte"]
    n_numero_t = a.sorteos[t].numero_sorteo
    assert all(max(r["objetivos"]) < n_numero_t for r in espia)


def test_particion_por_sorteo_y_orden_base_calibracion_bloque(espia):
    instantanea = lv.validar_instantanea("MILOTO", f4.historico("MILOTO", 87))
    informe, _ = le.evaluar(instantanea, lm.candidatos_del_juego("MILOTO"), le.Protocolo())
    bloques = informe["muestra_comun"]["bloques"]
    binarios = [r for r in espia if r["calibracion"]]
    assert len(binarios) == 2 * len(bloques)  # dos modelos binarios por bloque
    for r, b in zip(sorted(binarios, key=lambda r: r["corte"]), [b for b in bloques for _ in range(2)]):
        assert set(r["base"]).isdisjoint(r["calibracion"])
        assert max(r["base"]) < min(r["calibracion"])
        assert max(r["calibracion"]) < min(b["objetivos"])  # calibracion anterior al bloque evaluado
        assert set(r["objetivos"]).isdisjoint(b["objetivos"])
        assert len(r["base"]) >= 20 and len(r["calibracion"]) >= 10


def test_causalidad_secuencial_dentro_del_bloque():
    original = f4.historico("BALOTO", 160)
    a = lv.validar_instantanea("BALOTO", original)
    cambiado = list(original)
    cambiado[152] = dataclasses.replace(original[152], numeros=tuple(n for n in range(1, 44)
                                                                     if n not in original[152].numeros)[:5])
    b = lv.validar_instantanea("BALOTO", cambiado)
    va, vb = lv.Variables(a), lv.Variables(b)
    for modelo in NUEVOS_NUMEROS:
        ma = lm.ajustar_candidato(lm.CATALOGO[modelo], a, va, 150)
        mb = lm.ajustar_candidato(lm.CATALOGO[modelo], b, vb, 150)  # mismos parametros: ajuste anterior al bloque
        for posicion in (150, 151, 152):  # el propio resultado de 152 no afecta su prediccion
            assert np.array_equal(ma.predecir(va.filas([posicion])), mb.predecir(vb.filas([posicion])))
        assert not np.array_equal(ma.predecir(va.filas([155])), mb.predecir(vb.filas([155])))  # el pasado si


def test_escalado_y_codificacion_solo_con_el_entrenamiento(monkeypatch):
    historico = f4.historico("COLORLOTO", 90)
    cambiado = list(historico)
    cambiado[75] = dataclasses.replace(historico[75], pares=((2, "MORADO"), *historico[75].pares[1:]))
    instantanea = lv.validar_instantanea("COLORLOTO", cambiado)
    variables = lv.Variables(instantanea)
    vistos = []
    original = lm._ajustar
    monkeypatch.setattr(lm, "_ajustar", lambda estimador, X, y, **k: vistos.append(len(X)) or original(estimador, X, y, **k))
    ajustado = lm.ajustar_candidato(lm.CATALOGO["poisson_regularizado"], instantanea, variables, 60)
    columnas = ajustado.estimador.named_steps["variables"]
    entrenamiento = variables.de_ajuste(60)
    assert vistos == [len(entrenamiento)]
    assert np.allclose(columnas.named_transformers_["numericas"].mean_, entrenamiento.X[:, 1:].mean(axis=0))
    codigos = set(columnas.named_transformers_["identidad"].categories_[0].tolist())
    assert lv.codigo_de_par(2, "MORADO") not in codigos  # el color posterior no entra al codificador
    p = ajustado.predecir(variables.filas([80]))
    assert np.all(np.isfinite(p)) and abs(p.sum() - 1) < 1e-12
    binario = lm.ajustar_candidato(lm.CATALOGO["logistica_regularizada"], lv.validar_instantanea(
        "MILOTO", f4.historico("MILOTO", 87)), lv.Variables(lv.validar_instantanea("MILOTO", f4.historico("MILOTO", 87))), 60)
    base = binario.detalle["objetivos_base"]
    interno = binario.estimador.calibrated_classifiers_[0].estimator.named_steps["variables"]
    filas_base = lv.Variables(lv.validar_instantanea("MILOTO", f4.historico("MILOTO", 87))).de_ajuste(60)
    filas_base = filas_base.seleccionar((filas_base.objetivos >= base[0]) & (filas_base.objetivos <= base[1]))
    assert np.allclose(interno.named_transformers_["numericas"].mean_, filas_base.X[:, 1:].mean(axis=0))


def test_baloto_y_revancha_son_independientes(tmp_path):
    e = f4.entorno(tmp_path, {"BALOTO": 120, "BALOTO_REVANCHA": 120})
    lab = e.laboratorio()
    protocolo = le.Protocolo(bloques=2, perfil="reducido")
    r1 = lab.comparar_ahora(["BALOTO_REVANCHA"], protocolo)["juegos"]["BALOTO_REVANCHA"]
    informe = lab.experimento(r1["experimento"]).artefacto
    numeros = {s[0] for s in informe["historico"]["sorteos"]}
    revancha = {r.numero_sorteo for r in e.cargados("BALOTO_REVANCHA")}
    assert numeros == revancha
    bytes_antes = (e.directorio / "experimentos" / "BALOTO_REVANCHA" / f"{r1['experimento']}.json").read_bytes()
    e.anadir("BALOTO", e.siguiente("BALOTO", 5))  # Baloto cambia; Revancha no
    r2 = lab.comparar_ahora(["BALOTO", "BALOTO_REVANCHA"], protocolo)["juegos"]["BALOTO_REVANCHA"]
    assert r2["estado"] == "reutilizado" and r2["experimento"] == r1["experimento"]
    assert (e.directorio / "experimentos" / "BALOTO_REVANCHA" / f"{r1['experimento']}.json").read_bytes() == bytes_antes
