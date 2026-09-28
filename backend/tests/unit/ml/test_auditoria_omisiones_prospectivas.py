"""Tests de la Etapa AE-59, validada: auditoria de la semantica de
omisiones prospectivas (AE-58). Regresiones de los defectos comprobados
en `app/application/ml/semantica_omisiones_prospectivas.py`, escritas
antes de corregirlos:

- H1: `ampliar_ventana` y `reemplazar_objetivo` saltaban resultados
  pendientes como si fueran omisiones;
- H2: `verificar_base_ae52_ae53` no detectaba cambios del estado global,
  de la estructura de las propuestas ni de la copia `fijado_por_ae52` de
  la especificacion candidata de AE-53, ni tipos no dict.

Todo sintetico: numeros de sorteo construidos a mano. Sin datos reales,
PostgreSQL, entrenamiento ni predicciones reales. No aprueban ninguna
alternativa ante omisiones ni la propuesta de AE-53, y nunca autorizan
una evaluacion."""
from __future__ import annotations

import copy
import json

import pytest

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import semantica_omisiones_prospectivas as so
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52

C = 2713
W = tuple(range(C + 1, C + 101))


def _analizar(ultimo, prediccion, resultado, corte=C):
    return so.analizar_omisiones(corte=corte, ultimo_sorteo_ocurrido=ultimo,
                                 objetivos_con_prediccion=prediccion, objetivos_con_resultado=resultado)


def _resumen(informe):
    return {c.alternativa: (c.recuento_hipotetico, c.estado_recuento_hipotetico, c.relacion_con_reglas_ae52)
            for c in informe.consecuencias}


def _conjuntos(informe):
    return {c.alternativa: c.conjunto_hipotetico_contado for c in informe.consecuencias}


def _ventana_ingenua(corte, ultimo, predicciones):
    """Referencia lenta, solo para intervalos pequenos: recorre sorteo a
    sorteo y salta las omisiones (sorteos ocurridos sin prediccion)."""
    ventana, sorteo = [], corte + 1
    while len(ventana) < 100:
        if sorteo > ultimo or sorteo in predicciones:
            ventana.append(sorteo)
        sorteo += 1
    return tuple(ventana)


# ---------------------------------------------------------------------------
# H1: un resultado pendiente no es una omision
# ---------------------------------------------------------------------------

class TestH1PendientesNoSonOmisiones:
    def test_h1a_pendiente_sin_omision_las_cuatro_coinciden(self):
        prediccion = list(range(C + 1, C + 102))
        informe = _analizar(C + 101, prediccion, [o for o in prediccion if o != C + 50])
        assert informe.omisiones_en_ventana == ()
        assert informe.secuencia_ae53.resultado_pendiente == (C + 50,)
        assert _resumen(informe) == {a: (99, "puede_alcanzar_100", "sin_conflicto_conocido")
                                     for a in so.ALTERNATIVAS_OMISION}
        esperado = tuple(o for o in W if o != C + 50)
        assert set(_conjuntos(informe).values()) == {esperado}
        assert C + 101 not in _conjuntos(informe)["ampliar_ventana"]

    def test_h1b_omision_y_pendiente(self):
        prediccion = [o for o in range(C + 1, C + 103) if o != C + 50]
        informe = _analizar(C + 102, prediccion, [o for o in prediccion if o != C + 60])
        assert informe.omisiones_en_ventana == (C + 50,)
        assert _resumen(informe) == {
            "no_evaluable": (98, "no_puede_alcanzar_100", "sin_conflicto_conocido"),
            "ventana_fija_sin_ampliar": (98, "no_puede_alcanzar_100", "incompatible_con_minimo"),
            "ampliar_ventana": (99, "puede_alcanzar_100", "no_establecida_requiere_interpretacion"),
            "reemplazar_objetivo": (99, "puede_alcanzar_100", "incompatible_con_sin_sustitucion"),
        }
        ampliada = tuple(o for o in W if o != C + 50) + (C + 101,)
        assert so._ventana_ampliada(C, C + 102, set(prediccion)) == ampliada
        esperado = tuple(o for o in ampliada if o != C + 60)
        assert _conjuntos(informe)["ampliar_ventana"] == esperado == _conjuntos(informe)["reemplazar_objetivo"]
        assert C + 102 not in esperado and C + 101 in esperado and len(esperado) == 99

    def test_omision_con_futuros_la_ventana_ampliada_llega_a_sorteos_no_ocurridos(self):
        prediccion = [o for o in range(C + 1, C + 101) if o != C + 50]
        informe = _analizar(C + 100, prediccion, prediccion)
        assert so._ventana_ampliada(C, C + 100, set(prediccion)) == tuple(o for o in W if o != C + 50) + (C + 101,)
        assert _resumen(informe)["ampliar_ventana"] == (99, "puede_alcanzar_100",
                                                        "no_establecida_requiere_interpretacion")

    def test_ultimo_sorteo_muy_distante_y_pocas_predicciones(self):
        ultimo = C + 10 ** 12
        prediccion = [C + 1, C + 2, C + 3]
        ventana = so._ventana_ampliada(C, ultimo, set(prediccion))
        assert ventana == (C + 1, C + 2, C + 3) + tuple(range(ultimo + 1, ultimo + 98))
        assert len(ventana) == 100
        informe = _analizar(ultimo, prediccion, prediccion)
        assert informe.omisiones_en_ventana == tuple(range(C + 4, C + 101))
        assert informe.total_resueltos_descriptivo == 3
        assert informe.faltantes_como_en_resumen_ae52 == 97
        assert informe.resueltos_consecutivos_desde_el_corte == 3
        assert _resumen(informe) == {
            "no_evaluable": (3, "no_puede_alcanzar_100", "sin_conflicto_conocido"),
            "ventana_fija_sin_ampliar": (3, "no_puede_alcanzar_100", "incompatible_con_minimo"),
            "ampliar_ventana": (3, "puede_alcanzar_100", "no_establecida_requiere_interpretacion"),
            "reemplazar_objetivo": (3, "puede_alcanzar_100", "incompatible_con_sin_sustitucion"),
        }

    @pytest.mark.parametrize("semilla", range(12))
    def test_ventana_ampliada_equivale_al_recorrido_ingenuo(self, semilla):
        ultimo = C + 40 + 20 * semilla
        prediccion = {o for o in range(C + 1, ultimo + 2) if (o * (semilla + 3)) % 7 != 0}
        assert so._ventana_ampliada(C, ultimo, prediccion) == _ventana_ingenua(C, ultimo, prediccion)


def _casos_sin_omision():
    casos = []
    for pendientes in ((), (C + 1,), (C + 50,), (C + 100,), (C + 3, C + 77)):
        for ultimo in (C + 100, C + 105, C + 130):
            prediccion = list(range(C + 1, ultimo + 2))
            casos.append((ultimo, prediccion, [o for o in prediccion if o <= ultimo and o not in pendientes]))
    for ultimo in (C, C + 10, C + 60):
        prediccion = list(range(C + 1, ultimo + 2))
        casos.append((ultimo, prediccion, [o for o in prediccion if o <= ultimo]))
    return casos


@pytest.mark.parametrize("ultimo, prediccion, resultado", _casos_sin_omision())
def test_sin_omision_las_cuatro_alternativas_coinciden(ultimo, prediccion, resultado):
    informe = _analizar(ultimo, prediccion, resultado)
    assert informe.omisiones_en_ventana == ()
    firmas = {(c.conjunto_hipotetico_contado, c.recuento_hipotetico, c.estado_recuento_hipotetico,
               c.relacion_con_reglas_ae52) for c in informe.consecuencias}
    assert len(firmas) == 1
    (conjunto, _, _, relacion), = firmas
    assert set(conjunto) <= set(W)
    assert relacion == "sin_conflicto_conocido"


# ---------------------------------------------------------------------------
# Casos de AE-58 que no cambian
# ---------------------------------------------------------------------------

def test_casos_de_ae58_sin_cambios():
    c4 = [o for o in range(C + 1, C + 102) if o != C + 50]
    assert _resumen(_analizar(C + 101, c4, c4)) == {
        "no_evaluable": (99, "no_puede_alcanzar_100", "sin_conflicto_conocido"),
        "ventana_fija_sin_ampliar": (99, "no_puede_alcanzar_100", "incompatible_con_minimo"),
        "ampliar_ventana": (100, "alcanza_100_hipotetico", "no_establecida_requiere_interpretacion"),
        "reemplazar_objetivo": (100, "alcanza_100_hipotetico", "incompatible_con_sin_sustitucion"),
    }
    c5 = list(range(C + 1, C + 51))
    assert _resumen(_analizar(C + 60, c5, c5))["ampliar_ventana"] == (50, "puede_alcanzar_100",
                                                                       "no_establecida_requiere_interpretacion")
    assert _resumen(_analizar(C + 100, list(W), list(W))) == {
        a: (100, "alcanza_100_hipotetico", "sin_conflicto_conocido") for a in so.ALTERNATIVAS_OMISION}
    tope = [o for o in range(C + 1, C + 111) if o != C + 50]
    informe = _analizar(C + 110, tope, tope)
    assert _conjuntos(informe)["ampliar_ventana"] == tuple(tope[:100])
    assert informe.total_resueltos_descriptivo == 109
    assert informe.faltantes_como_en_resumen_ae52 == 0


# ---------------------------------------------------------------------------
# H2: divergencias de estado, estructura y tipo de la base
# ---------------------------------------------------------------------------

def _con_especificacion(monkeypatch, cambio):
    especificacion = copy.deepcopy(ESPECIFICACION_CANDIDATA_AE53)
    cambio(especificacion)
    monkeypatch.setattr(so, "ESPECIFICACION_CANDIDATA_AE53", especificacion)


class TestH2VerificacionDeLaBase:
    def test_base_actual_pasa(self):
        so.verificar_base_ae52_ae53()

    def test_h2a_estado_global_de_la_especificacion(self, monkeypatch):
        _con_especificacion(monkeypatch, lambda e: e.__setitem__("estado", "aprobada"))
        with pytest.raises(so.BaseDivergenteError, match="candidata_no_aprobada"):
            so.verificar_base_ae52_ae53()

    @pytest.mark.parametrize("clave", ["horizonte", "omisiones"])
    def test_h2b_clave_extra_en_una_propuesta(self, monkeypatch, clave):
        _con_especificacion(monkeypatch, lambda e: e["propuestas"][clave].__setitem__("aprobada_por", "operador"))
        with pytest.raises(so.BaseDivergenteError, match=clave):
            so.verificar_base_ae52_ae53()

    @pytest.mark.parametrize("clave", ["horizonte", "omisiones"])
    def test_h2b_propuesta_sin_estado(self, monkeypatch, clave):
        _con_especificacion(monkeypatch, lambda e: e["propuestas"][clave].pop("estado"))
        with pytest.raises(so.BaseDivergenteError, match=clave):
            so.verificar_base_ae52_ae53()

    @pytest.mark.parametrize("cambio", [
        lambda f: f.__setitem__("minimo_sorteos_resueltos_por_juego", 50),
        lambda f: f.__setitem__("sorteos_consecutivos_sin_sustitucion", 1),
        lambda f: f.pop("sin_agregados_antes_del_minimo"),
        lambda f: f.__setitem__("regla_nueva", True),
    ])
    def test_h2c_copia_fijado_por_ae52_divergente(self, monkeypatch, cambio):
        _con_especificacion(monkeypatch, lambda e: cambio(e["fijado_por_ae52"]))
        with pytest.raises(so.BaseDivergenteError, match="fijado_por_ae52"):
            so.verificar_base_ae52_ae53()

    @pytest.mark.parametrize("valor", [None, [], "especificacion"])
    def test_h2e_especificacion_no_dict(self, monkeypatch, valor):
        monkeypatch.setattr(so, "ESPECIFICACION_CANDIDATA_AE53", valor)
        with pytest.raises(so.BaseDivergenteError):
            so.verificar_base_ae52_ae53()

    @pytest.mark.parametrize("valor", [None, [], "reglas"])
    def test_h2e_reglas_no_dict(self, monkeypatch, valor):
        monkeypatch.setattr(so, "REGLAS_EVALUACION_AE52", valor)
        with pytest.raises(so.BaseDivergenteError):
            so.verificar_base_ae52_ae53()

    def test_la_divergencia_impide_el_analisis(self, monkeypatch):
        _con_especificacion(monkeypatch, lambda e: e.__setitem__("estado", "aprobada"))
        with pytest.raises(so.BaseDivergenteError):
            _analizar(C + 100, list(W), list(W))


# ---------------------------------------------------------------------------
# Invariantes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ultimo, prediccion, resultado", [
    (C + 101, list(range(C + 1, C + 102)), [o for o in range(C + 1, C + 102) if o != C + 50]),
    (C + 10 ** 12, [C + 1, C + 2, C + 3], [C + 1, C + 2, C + 3]),
    (C + 100, list(W), list(W)),
])
def test_sin_decision_ni_autorizacion(ultimo, prediccion, resultado):
    informe = _analizar(ultimo, prediccion, resultado)
    assert informe.decision == "sin_decidir"
    assert informe.autoriza_evaluacion is False
    assert all(c.autoriza_evaluacion is False for c in informe.consecuencias)
    assert all(c.origen in so.ORIGENES and c.estado_recuento_hipotetico in so.ESTADOS_RECUENTO
               and c.relacion_con_reglas_ae52 in so.RELACIONES_AE52 for c in informe.consecuencias)


def test_constantes_intactas():
    antes = json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                       sort_keys=True)
    _analizar(C + 101, list(range(C + 1, C + 102)), list(range(C + 1, C + 101)))
    assert json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                      sort_keys=True) == antes
    assert len(PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"
