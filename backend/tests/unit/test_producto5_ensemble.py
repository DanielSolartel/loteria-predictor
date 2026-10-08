"""Producto 5: modelo combinado (ensemble temporal).

- componentes realmente entrenados y pesos aprendidos en los cuatro juegos,
  incluida MiLoto corta (87 sorteos);
- la eleccion responde a las perdidas internas (un componente oraculo gana
  peso) y la malla mezcla predicciones ya calculadas: 66 mezclas sin 66
  reentrenamientos; desempate y pesos coinciden con un calculo independiente;
- particiones causales: espias de ajuste y calibracion, y alterar los
  resultados desde un objetivo no cambia su prediccion previa ni los pesos
  que se le aplican;
- finitud, masa 5 o 1, paleta causal, componentes fallidos y peso 1 para la
  uniforme;
- comparacion exterior sobre objetivos comunes, bloques desiguales ponderados
  por objetivo y candidatos parciales fuera del ranking."""
from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from app.application.ml import carteras_ensemble as ce
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from tests.unit import fixtures_producto4 as f4

REDUCIDO = ce.ProtocoloCarteras(bloques=3, perfil="reducido")
TAMANOS = {"BALOTO": 100, "BALOTO_REVANCHA": 90, "MILOTO": 87, "COLORLOTO": 90}


def _instantanea(codigo, n=None, historico=None):
    return lv.validar_instantanea(codigo, historico or f4.historico(codigo, n or TAMANOS[codigo]))


def _alterado_desde(codigo, historico, posicion, semilla=777):
    """Copia con TODOS los resultados desde `posicion` sustituidos por otros
    validos del mismo juego."""
    otros = f4.historico(codigo, len(historico), semilla)
    campo = "pares" if codigo == "COLORLOTO" else "numeros"
    salida = list(historico)
    for i in range(posicion, len(historico)):
        salida[i] = dataclasses.replace(historico[i], **{campo: getattr(otros[i], campo)})
    return salida


@pytest.fixture
def espia(monkeypatch):
    vistos = []

    def observar(modelo, posicion_de_corte, base, calibracion, filas):
        vistos.append({"modelo": modelo, "corte": posicion_de_corte, "base": list(base),
                       "calibracion": list(calibracion), "posiciones": set(filas.posiciones.tolist())})
    monkeypatch.setattr(lm, "OBSERVADOR_DE_AJUSTE", observar)
    return vistos


# ---------------------------------------------------------------------------
# Malla, desempate y mezcla
# ---------------------------------------------------------------------------

def test_malla_de_66_mezclas_convexas_en_orden_estable():
    malla = ce.malla()
    assert len(malla) == 66 == math.comb(12, 2)
    assert len(set(malla)) == 66 and all(sum(m) == 10 and min(m) >= 0 for m in malla)
    assert malla[0] == (10, 0, 0) and malla[1] == (9, 1, 0) and malla[2] == (9, 0, 1) and malla[-1] == (0, 0, 10)
    claves = [(-m[0], -m[1]) for m in malla]
    assert claves == sorted(claves)
    assert ce.pesos_de((3, 5, 2)) == [0.3, 0.5, 0.2]


def test_desempate_con_un_ejemplo_independiente():
    malla = ce.malla()
    indice = {m: i for i, m in enumerate(malla)}
    # todas iguales: gana la uniforme
    assert malla[ce.elegir_mezcla([0.5] * 66)["indice"]] == (10, 0, 0)
    # minimo unico
    perdidas = [1.0] * 66
    perdidas[indice[(2, 3, 5)]] = 0.4
    assert malla[ce.elegir_mezcla(perdidas)["indice"]] == (2, 3, 5)
    # empate exacto entre dos mezclas: mayor peso de la uniforme; despues mayor peso lineal
    perdidas = [1.0] * 66
    perdidas[indice[(1, 2, 7)]] = perdidas[indice[(3, 0, 7)]] = 0.4
    assert malla[ce.elegir_mezcla(perdidas)["indice"]] == (3, 0, 7)
    perdidas = [1.0] * 66
    perdidas[indice[(4, 1, 5)]] = perdidas[indice[(4, 6, 0)]] = 0.4
    assert malla[ce.elegir_mezcla(perdidas)["indice"]] == (4, 6, 0)
    # a la tolerancia del minimo: empatan; mas alla, no
    perdidas = [1.0] * 66
    perdidas[indice[(0, 0, 10)]] = 0.4
    perdidas[indice[(5, 5, 0)]] = 0.4 + ce.TOLERANCIA_DE_EMPATE / 2
    assert malla[ce.elegir_mezcla(perdidas)["indice"]] == (5, 5, 0)
    perdidas[indice[(5, 5, 0)]] = 0.4 + 10 * ce.TOLERANCIA_DE_EMPATE
    eleccion = ce.elegir_mezcla(perdidas)
    assert malla[eleccion["indice"]] == (0, 0, 10) and eleccion["empatadas"] == [indice[(0, 0, 10)]]
    # el orden de recorrido no decide: invertir la lista de perdidas con la malla invertida da la misma mezcla
    al_reves = ce.elegir_mezcla(list(reversed(perdidas)), list(reversed(malla)))
    assert list(reversed(malla))[al_reves["indice"]] == (0, 0, 10)
    with pytest.raises(ValueError):
        ce.elegir_mezcla([float("nan")] * 66)


def test_la_malla_mezcla_predicciones_ya_calculadas_sin_reentrenar(monkeypatch):
    instantanea = _instantanea("MILOTO")
    llamadas, mezclas = [], []
    original_ajustar, original_mezclar = lm.ajustar_candidato, ce.mezclar
    monkeypatch.setattr(lm, "ajustar_candidato", lambda e, *a, **k: llamadas.append((e.id, a[2])) or
                        original_ajustar(e, *a, **k))
    monkeypatch.setattr(ce, "mezclar", lambda p, n, *a: mezclas.append(tuple(n)) or original_mezclar(p, n, *a))
    variables = lv.Variables(instantanea)
    ajustes = ce.Ajustes(instantanea, variables, "reducido")
    componentes = [lm.CATALOGO[c] for c in ce.COMPONENTES["MILOTO"]]
    pesos = ce.aprender_pesos(instantanea, ajustes, componentes, 60, list(range(60, 70)), (), 12)
    assert sorted(llamadas) == sorted((c, 60) for c in ce.COMPONENTES["MILOTO"])  # un ajuste por componente
    assert mezclas == list(ce.MALLA) and len(pesos["perdidas"]) == 66
    assert ajustes.ajustes_realizados == 3


def test_pesos_y_perdidas_coinciden_con_un_calculo_independiente(monkeypatch):
    """Log Loss binaria media por sorteo calculada aqui con NumPy, mezcla por
    mezcla, y la regla de desempate aplicada a mano."""
    instantanea = _instantanea("BALOTO")
    capturado = {}
    original = ce._predicciones_componentes

    def capturar(ajustes, componentes, corte, filas):
        salida = original(ajustes, componentes, corte, filas)
        capturado.update(predicciones=salida[0], filas=filas)
        return salida
    monkeypatch.setattr(ce, "_predicciones_componentes", capturar)
    variables = lv.Variables(instantanea)
    ajustes = ce.Ajustes(instantanea, variables, "reducido")
    componentes = [lm.CATALOGO[c] for c in ce.COMPONENTES["BALOTO"]]
    posiciones = list(range(80, 90))
    resultado = ce.aprender_pesos(instantanea, ajustes, componentes, 80, posiciones, (), 12)
    P, filas = capturado["predicciones"], capturado["filas"]
    assert np.array_equal(filas.posiciones, np.repeat(posiciones, 43))
    for i in posiciones:  # etiquetas de las filas = resultado real del sorteo
        assert set(np.array(filas.candidatos)[(filas.posiciones == i) & (filas.y == 1)]) == set(
            instantanea.sorteos[i].numeros)
    independientes = []
    for i, j, k in ce.MALLA:
        p = np.clip((i * P[0] + j * P[1] + k * P[2]) / 10, 1e-15, 1 - 1e-15)
        perdida = -(filas.y * np.log(p) + (1 - filas.y) * np.log(1 - p))
        independientes.append(float(np.mean([perdida[filas.posiciones == pos].mean() for pos in posiciones])))
    guardadas = [x["log_loss"] for x in resultado["perdidas"]]
    assert np.allclose(guardadas, independientes, rtol=0, atol=1e-11)
    minimo = min(independientes)
    elegida = min((m for m, v in enumerate(independientes) if v <= minimo + ce.TOLERANCIA_DE_EMPATE),
                  key=lambda m: (-ce.MALLA[m][0], -ce.MALLA[m][1]))
    assert resultado["numeradores"] == list(ce.MALLA[elegida])
    assert resultado["pesos"] == dict(zip(ce.COMPONENTES["BALOTO"], [n / 10 for n in ce.MALLA[elegida]]))
    assert resultado["eligio_uniforme"] == (ce.MALLA[elegida][0] == 10)


def _oraculo(monkeypatch, componente):
    """Sustituye un componente por un oraculo que mira la etiqueta de la fila:
    mucho mejor que la uniforme. Solo para comprobar que los pesos responden a
    las perdidas internas."""
    original = lm.ajustar_candidato

    def ajustar(entrada, instantanea, variables, corte, perfil="predeterminado"):
        if entrada.id != componente:
            return original(entrada, instantanea, variables, corte, perfil)

        def predecir(filas):
            p = np.where(filas.y == 1, 0.9, 0.5 / 38.0)
            return p * (5 / np.array([p[filas.posiciones == x].sum() for x in filas.posiciones]))
        return lm.Ajustado(entrada, predecir, {"oraculo": True})
    monkeypatch.setattr(lm, "ajustar_candidato", ajustar)


def test_los_pesos_responden_a_las_perdidas_internas(monkeypatch):
    _oraculo(monkeypatch, "hgb_clasificador")
    cuerpo, _ = ce.evaluar(_instantanea("MILOTO"), REDUCIDO)
    for b in cuerpo["ensemble"]["bloques_internos"]:
        assert b["numeradores"] == [0, 0, 10] and b["eligio_uniforme"] is False
        assert b["log_loss_minima"] < b["perdidas"][0]["log_loss"]  # la uniforme pierde en el bloque interno
    ensemble = next(c for c in cuerpo["candidatos"] if c["id"] == ce.ID_ENSEMBLE)
    assert ensemble["veredicto"] == "menor_perdida_que_la_uniforme_en_esta_evaluacion"
    assert cuerpo["resumen"]["ranking"][0]["id"] in (ce.ID_ENSEMBLE, "hgb_clasificador")


# ---------------------------------------------------------------------------
# Entrenamiento real en los cuatro juegos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("codigo", ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"])
def test_componentes_entrenados_y_pesos_aprendidos_en_los_cuatro_juegos(codigo, espia):
    instantanea = _instantanea(codigo)
    cuerpo, tiempos = ce.evaluar(instantanea, REDUCIDO)
    muestra = cuerpo["muestra_comun"]
    if codigo == "MILOTO":  # MiLoto corta: 87 sorteos -> 27 objetivos exteriores (10, 10 y 7)
        assert [len(b["todos"]) for b in muestra["bloques"]] == [10, 10, 7] and muestra["total_objetivos"] == 27
    internos = cuerpo["ensemble"]["bloques_internos"]
    assert len(internos) == len(muestra["bloques"]) and all(b["estado"] == "pesos_aprendidos" for b in internos)
    for b in internos:
        assert len(b["perdidas"]) == 66 and all(math.isfinite(x["log_loss"]) for x in b["perdidas"])
        assert math.isclose(sum(b["pesos"].values()), 1.0) and list(b["pesos"]) == list(ce.COMPONENTES[codigo])
        assert b["log_loss_minima"] == min(x["log_loss"] for x in b["perdidas"])
        assert b["eligio_uniforme"] == (b["numeradores"][0] == 10)
    entrenados = {r["modelo"] for r in espia}
    assert set(ce.COMPONENTES[codigo][1:]) <= entrenados  # las dos familias se ajustaron de verdad
    assert cuerpo["ajustes_realizados"] > 0 and ce.ID_ENSEMBLE in tiempos
    ensemble = next(c for c in cuerpo["candidatos"] if c["id"] == ce.ID_ENSEMBLE)
    assert ensemble["estado"] == "completo"
    assert cuerpo["ensemble"]["bloques_que_eligieron_la_uniforme"] == sum(b["eligio_uniforme"] for b in internos)
    if cuerpo["ensemble"]["bloques_que_eligieron_la_uniforme"] == len(internos):
        assert ensemble["agregado"]["diferencia_log_loss"] == 0.0 and ensemble["veredicto"] == "empate"


# ---------------------------------------------------------------------------
# Causalidad
# ---------------------------------------------------------------------------

def test_espias_ajuste_y_calibracion_anteriores_al_bloque_interno(espia):
    instantanea = _instantanea("MILOTO")
    cuerpo, _ = ce.evaluar(instantanea, REDUCIDO)
    for registro in espia:
        assert max(registro["posiciones"]) < registro["corte"]
        if registro["calibracion"]:
            assert max(registro["base"]) < min(registro["calibracion"])
            assert max(registro["calibracion"]) < instantanea.sorteos[registro["corte"]].numero_sorteo
    cortes = {(r["modelo"], r["corte"]) for r in espia}
    for b in cuerpo["muestra_comun"]["bloques"]:
        interno = b["interno"]
        s_interno = interno["posicion_de_ajuste"]
        assert s_interno == b["posicion_de_ajuste"] - 10
        assert interno["todos"] == [instantanea.sorteos[i].numero_sorteo for i in range(s_interno, s_interno + 10)]
        for c in ("logistica_regularizada", "hgb_clasificador"):
            # pesos: componentes ajustados antes del bloque interno; exterior: reajustados antes del exterior
            assert (c, s_interno) in cortes and (c, b["posicion_de_ajuste"]) in cortes
    for b, i in zip(cuerpo["muestra_comun"]["bloques"], cuerpo["ensemble"]["bloques_internos"]):
        assert max(i["objetivos"]) < min(b["objetivos"])
        ajuste = i["ajustes_de_componentes"]["logistica_regularizada"]
        assert ajuste["objetivos_de_ajuste"][1] < min(i["objetivos"])
        assert ajuste["objetivos_de_calibracion"][1] < min(i["objetivos"])


def _exteriores(monkeypatch):
    """Espia de las mezclas validadas: (posiciones, probabilidades)."""
    vistas = []
    original = ce.validar_mezcla

    def validar(p, filas, colores, cantidad):
        vistas.append((filas.posiciones.copy(), np.array(p)))
        return original(p, filas, colores, cantidad)
    monkeypatch.setattr(ce, "validar_mezcla", validar)
    return vistas


@pytest.mark.parametrize("codigo", ["MILOTO", "COLORLOTO"])
def test_alterar_un_objetivo_no_cambia_su_prediccion_previa_ni_sus_pesos(codigo, monkeypatch):
    original = f4.historico(codigo, TAMANOS[codigo])
    t = 75  # dentro del segundo bloque exterior (70..79)
    a = _instantanea(codigo, historico=original)
    b = _instantanea(codigo, historico=_alterado_desde(codigo, original, t))
    assert a.sorteos[t] != b.sorteos[t]
    vistas = _exteriores(monkeypatch)
    cuerpo_a, _ = ce.evaluar(a, REDUCIDO)
    mezclas_a = list(vistas)
    vistas.clear()
    cuerpo_b, _ = ce.evaluar(b, REDUCIDO)
    mezclas_b = list(vistas)
    internos_a, internos_b = cuerpo_a["ensemble"]["bloques_internos"], cuerpo_b["ensemble"]["bloques_internos"]
    # bloques 1 y 2: sus pesos se eligieron con objetivos anteriores a t -> identicos
    for k in (0, 1):
        assert internos_a[k]["pesos"] == internos_b[k]["pesos"]
        assert internos_a[k]["perdidas"] == internos_b[k]["perdidas"]
    # prediccion exterior de cada objetivo <= t del bloque 2: identica (el resultado de t no entra en su prediccion)
    # orden de llamadas: 66 internas del bloque k y despues su exterior; la primera con minimo 70 es el exterior 2
    (pos_a, p_a) = next((pos, p) for pos, p in mezclas_a if min(pos) == 70)
    (pos_b, p_b) = next((pos, p) for pos, p in mezclas_b if min(pos) == 70)
    ma, mb = pos_a <= t, pos_b <= t
    assert set(pos_a[ma].tolist()) == set(range(70, t + 1))
    assert np.array_equal(pos_a[ma], pos_b[mb]) and np.array_equal(p_a[ma], p_b[mb])
    # las metricas anteriores a t no cambian; la de t, para un modelo no uniforme, si (su etiqueta es otra)
    obj_t = a.sorteos[t].numero_sorteo
    for modelo in (ce.ID_ENSEMBLE, ce.COMPONENTES[codigo][1]):
        fa = {f["objetivo"]: f for f in next(c for c in cuerpo_a["candidatos"] if c["id"] == modelo)["por_objetivo"]}
        fb = {f["objetivo"]: f for f in next(c for c in cuerpo_b["candidatos"] if c["id"] == modelo)["por_objetivo"]}
        assert all(fa[o] == fb[o] for o in fa if o < obj_t)
    assert fa[obj_t]["log_loss"] != fb[obj_t]["log_loss"]


def test_la_fuente_del_objetivo_siguiente_solo_usa_el_pasado():
    original = f4.historico("BALOTO", 100)
    a = _instantanea("BALOTO", historico=original[:90])
    c = _instantanea("BALOTO", historico=_alterado_desde("BALOTO", original, 85)[:90])
    fa, fc = ce.fuente(a, ce.ID_ENSEMBLE, "reducido"), ce.fuente(c, ce.ID_ENSEMBLE, "reducido")
    assert fa["detalle"]["bloque_interno"]["objetivos"] == list(range(2161, 2171))  # objetivos 81..90 (posiciones 80-89)
    assert fa["probabilidades"] != fc["probabilidades"]  # el pasado si cuenta


# ---------------------------------------------------------------------------
# Finitud, masa, paleta, fallos y peso 1 de la uniforme
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("codigo", ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"])
def test_vector_fuente_finito_con_masa_cinco_o_uno(codigo):
    instantanea = _instantanea(codigo, 70)
    f = ce.fuente(instantanea, ce.ID_ENSEMBLE, "reducido")
    p = np.array(f["probabilidades"])
    assert np.all(np.isfinite(p)) and np.all(p > 0) and np.all(p < 1)
    assert abs(p.sum() - (1 if codigo == "COLORLOTO" else 5)) < 1e-9
    assert f["objetivo"] == instantanea.corte + 1
    if codigo == "COLORLOTO":
        assert f["paleta"] == list(instantanea.paleta()) and {c[1] for c in f["candidatos"]} == set(instantanea.paleta())
        assert len(f["candidatos"]) == 7 * len(instantanea.paleta())
    else:
        assert len(f["candidatos"]) == instantanea.reglas.rango[1]
    assert ("superbalota" in f) == bool(instantanea.reglas.superbalota)
    if "superbalota" in f:
        assert abs(sum(f["superbalota"]["probabilidades"]) - 1) < 1e-9
        assert f["superbalota"]["estrategia"] == "frecuencia_con_suavizado_de_laplace"
    for b in ce.MALLA[::13]:  # cualquier mezcla convexa conserva la masa
        mezcla = ce.mezclar(np.vstack([p, p, p]), b)
        assert abs(mezcla.sum() - p.sum()) < 1e-12


def test_paleta_causal_en_colorloto():
    historico = f4.historico("COLORLOTO", 90)
    cambiado = list(historico)
    cambiado[74] = dataclasses.replace(historico[74], pares=((2, "MORADO"), *historico[74].pares[1:]))
    instantanea = _instantanea("COLORLOTO", historico=cambiado)
    muestra = ce.muestra_comun(instantanea, REDUCIDO)
    b2 = muestra["bloques"][1]  # exterior 70..79, interno 60..69
    assert "MORADO" not in b2["paleta"] and "MORADO" not in b2["interno"]["paleta"]
    assert any(x["objetivo"] == instantanea.sorteos[74].numero_sorteo and x["motivo"] ==
               "color_fuera_de_la_paleta_del_corte" for x in muestra["excluidos"])
    b3 = muestra["bloques"][2]  # exterior 80..89, interno 70..79: el color aparecio en el interno
    assert "MORADO" in b3["paleta"] and "MORADO" not in b3["interno"]["paleta"]
    assert any(x["parte"] == "interno" for x in b3["interno"]["excluidos"])
    cuerpo, _ = ce.evaluar(instantanea, REDUCIDO)
    assert all(b["estado"] == "pesos_aprendidos" for b in cuerpo["ensemble"]["bloques_internos"])


def test_componente_fallido_deja_el_ensemble_parcial_sin_sustituirlo(monkeypatch):
    original = lm.ajustar_candidato

    def ajustar(entrada, instantanea, variables, corte, perfil="predeterminado"):
        if entrada.id == "hgb_clasificador" and corte == 70:  # falla el interno del bloque 3 y el exterior del 2
            raise lm.CandidatoNoDisponible("no_converge", "fallo simulado")
        return original(entrada, instantanea, variables, corte, perfil)
    monkeypatch.setattr(lm, "ajustar_candidato", ajustar)
    cuerpo, _ = ce.evaluar(_instantanea("MILOTO"), REDUCIDO)
    ensemble = next(c for c in cuerpo["candidatos"] if c["id"] == ce.ID_ENSEMBLE)
    assert ensemble["estado"] == "parcial" and "veredicto" not in ensemble
    estados = [b["estado"] for b in ensemble["bloques"]]
    assert estados == ["evaluado", "componente_no_disponible", "componente_no_disponible"]
    internos = cuerpo["ensemble"]["bloques_internos"]
    assert internos[2]["estado"] == "no_converge" and internos[2]["componente"] == "hgb_clasificador"
    assert internos[1]["estado"] == "pesos_aprendidos"
    ranking = [f["id"] for f in cuerpo["resumen"]["ranking"]]
    assert ce.ID_ENSEMBLE not in ranking and "hgb_clasificador" not in ranking
    assert {x["id"] for x in cuerpo["resumen"]["incompletos"]} >= {ce.ID_ENSEMBLE, "hgb_clasificador"}
    assert ensemble["agregado"]["sorteos"] == ensemble["objetivos_evaluados"] == 10  # cifras parciales aparte
    # nunca se rellena con la uniforme conservando el nombre del ensemble: solo hay objetivos del bloque 1
    assert [f["objetivo"] for f in ensemble["por_objetivo"]] == cuerpo["muestra_comun"]["bloques"][0]["objetivos"]


def test_fuente_con_componente_fallido_no_se_sustituye(monkeypatch):
    original = lm.ajustar_candidato

    def ajustar(entrada, *a, **k):
        if entrada.id == "logistica_regularizada":
            raise lm.CandidatoNoDisponible("clase_insuficiente", "fallo simulado")
        return original(entrada, *a, **k)
    monkeypatch.setattr(lm, "ajustar_candidato", ajustar)
    with pytest.raises(ce.ComponenteNoDisponible) as error:
        ce.fuente(_instantanea("MILOTO", 70), ce.ID_ENSEMBLE, "reducido")
    assert error.value.componente == "logistica_regularizada" and error.value.estado == "clase_insuficiente"


def test_muestra_insuficiente_con_requisitos_explicitos():
    with pytest.raises(ce.MuestraInsuficienteCarteras) as error:
        ce.evaluar(_instantanea("MILOTO", 69), REDUCIDO)
    assert error.value.requeridos == 10 and "70 sorteos" in str(error.value)
    ce.evaluar(_instantanea("MILOTO", 70), ce.ProtocoloCarteras(bloques=1, perfil="reducido"))
    with pytest.raises(ce.MuestraInsuficienteCarteras) as error:
        ce.fuente(_instantanea("MILOTO", 59), ce.ID_ENSEMBLE, "reducido")
    assert error.value.requeridos == 60 and error.value.para == "generacion"
    for invalido in ({"bloques": 0}, {"bloques": 7}, {"tamano_bloque": 5}, {"perfil": "otro"}):
        with pytest.raises(ValueError):
            ce.ProtocoloCarteras(**invalido)


# ---------------------------------------------------------------------------
# Comparacion exterior
# ---------------------------------------------------------------------------

def test_comparacion_sobre_objetivos_comunes_con_bloques_desiguales():
    cuerpo, _ = ce.evaluar(_instantanea("MILOTO"), REDUCIDO)
    muestra = cuerpo["muestra_comun"]["objetivos"]
    completos = [c for c in cuerpo["candidatos"] if c["estado"] == "completo"]
    assert {c["id"] for c in completos} == {"uniforme", "actual_frecuencia_contraida", "logistica_regularizada",
                                            "hgb_clasificador", ce.ID_ENSEMBLE}
    for c in completos:
        assert [f["objetivo"] for f in c["por_objetivo"]] == muestra
        # media por OBJETIVO (27), no media de las medias de bloque (10, 10 y 7)
        por_objetivo = np.mean([f["log_loss"] for f in c["por_objetivo"]])
        assert abs(c["agregado"]["log_loss"] - por_objetivo) < 1e-11
        assert c["agregado"]["sorteos"] == 27
    hgb = next(c for c in completos if c["id"] == "hgb_clasificador")
    medias_de_bloque = np.mean([b["metricas"]["log_loss"] for b in hgb["bloques"]])
    assert abs(medias_de_bloque - hgb["agregado"]["log_loss"]) > 1e-9  # los bloques desiguales no pesan igual
    ranking = cuerpo["resumen"]["ranking"]
    assert [f["log_loss"] for f in ranking] == sorted(f["log_loss"] for f in ranking)
    uniforme = next(c for c in completos if c["id"] == "uniforme")
    for c in completos:
        assert c["agregado"]["uniforme"]["log_loss"] == uniforme["agregado"]["log_loss"]


def test_la_superbalota_queda_aparte_con_la_estrategia_de_producto_1():
    cuerpo, _ = ce.evaluar(_instantanea("BALOTO"), REDUCIDO)
    sb = cuerpo["superbalota"]
    assert sb["estrategia"] == "frecuencia_con_suavizado_de_laplace" and sb["sorteos"] == 30
    assert all("superbalota" not in str(b.get("pesos", {})) for b in cuerpo["ensemble"]["bloques_internos"])
    cuerpo_m, _ = ce.evaluar(_instantanea("MILOTO"), REDUCIDO)
    assert "superbalota" not in cuerpo_m


def test_comparacion_determinista_y_sin_reloj():
    instantanea = _instantanea("MILOTO")
    a, _ = ce.evaluar(instantanea, REDUCIDO)
    b, _ = ce.evaluar(instantanea, REDUCIDO)
    assert a == b
