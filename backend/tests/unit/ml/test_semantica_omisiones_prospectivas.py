"""Tests de `app/application/ml/semantica_omisiones_prospectivas.py`
-Etapa AE-58, validada: semantica de omisiones prospectivas. Todo
sintetico: numeros de sorteo construidos a mano y, para comparar con
AE-52, un registro en memoria con historicos generados por formulas y
salidas fabricadas. Sin datos reales, PostgreSQL, entrenamiento ni
predicciones reales. No aprueban ni recomiendan ninguna alternativa ante
una omision y nunca autorizan una evaluacion."""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
from pathlib import Path

import pytest

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import registro_prospectivo as rp
from app.application.ml import semantica_omisiones_prospectivas as so
from app.application.ml.especificacion_evaluacion_prospectiva import (
    ESPECIFICACION_CANDIDATA_AE53,
    EspecificacionProspectivaError,
    validar_secuencia_objetivos,
)
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52
from tests.unit.simulaciones import sinteticos

ARCHIVO = Path(so.__file__)
RAIZ_BACKEND = ARCHIVO.resolve().parents[3]
C = 2713
VENTANA = tuple(range(C + 1, C + 101))


def _analizar(ultimo, prediccion, resultado, corte=C):
    return so.analizar_omisiones(corte=corte, ultimo_sorteo_ocurrido=ultimo,
                                 objetivos_con_prediccion=prediccion, objetivos_con_resultado=resultado)


def _por_alternativa(informe):
    return {c.alternativa: c for c in informe.consecuencias}


def _resumen(informe):
    return {c.alternativa: (c.recuento_hipotetico, c.estado_recuento_hipotetico, c.relacion_con_reglas_ae52)
            for c in informe.consecuencias}


_C4_PREDICCION = [o for o in range(C + 1, C + 102) if o != C + 50]


def _caso(nombre):
    return {
        "C1": (C + 100, list(VENTANA), list(VENTANA)[:97]),
        "C2": (C + 60, list(range(C + 1, C + 62)), list(range(C + 1, C + 61))),
        "C4": (C + 101, _C4_PREDICCION, _C4_PREDICCION),
        "C5": (C + 60, list(range(C + 1, C + 51)), list(range(C + 1, C + 51))),
        "cien": (C + 100, list(VENTANA), list(VENTANA)),
    }[nombre]


# ---------------------------------------------------------------------------
# Hechos: objetivo, prediccion registrada, sorteo ocurrido, resultado resuelto
# ---------------------------------------------------------------------------

class TestHechos:
    def test_c1_resultados_pendientes(self):
        informe = _analizar(*_caso("C1"))
        assert informe.objetivos == VENTANA
        assert informe.predicciones_registradas == VENTANA
        assert informe.sorteos_ocurridos_en_ventana == VENTANA
        assert informe.resultados_resueltos == VENTANA[:97]
        assert informe.omisiones_en_ventana == ()
        assert informe.resueltos_consecutivos_desde_el_corte == 97
        assert informe.cien_consecutivos_desde_el_corte is False
        assert informe.total_resueltos_descriptivo == 97
        assert informe.faltantes_como_en_resumen_ae52 == 3
        assert informe.estado_segun_propuesta_ae53 == "incompleta"

    def test_c2_objetivos_futuros(self):
        informe = _analizar(*_caso("C2"))
        assert informe.sorteos_ocurridos_en_ventana == tuple(range(C + 1, C + 61))
        assert informe.omisiones_en_ventana == ()
        assert informe.resueltos_consecutivos_desde_el_corte == 60
        assert informe.faltantes_como_en_resumen_ae52 == 40
        assert informe.estado_segun_propuesta_ae53 == "incompleta"
        assert informe.secuencia_ae53.futuros == tuple(range(C + 61, C + 101))

    def test_c4_omision_con_resultados_posteriores(self):
        informe = _analizar(*_caso("C4"))
        assert informe.omisiones_en_ventana == (C + 50,)
        assert C + 101 in informe.resultados_resueltos
        assert informe.total_resueltos_descriptivo == 100
        assert informe.faltantes_como_en_resumen_ae52 == 0
        assert informe.resueltos_consecutivos_desde_el_corte == 49
        assert informe.cien_consecutivos_desde_el_corte is False
        assert informe.estado_segun_propuesta_ae53 == "no_evaluable_por_omision"

    def test_c5_omisiones_finales_solo_visibles_con_el_ultimo_sorteo(self):
        informe = _analizar(*_caso("C5"))
        assert informe.omisiones_en_ventana == tuple(range(C + 51, C + 61))
        assert informe.faltantes_como_en_resumen_ae52 == 50
        assert informe.estado_segun_propuesta_ae53 == "no_evaluable_por_omision"

    def test_consecutivos_sin_tope_mas_alla_de_la_ventana(self):
        objetivos = list(range(C + 1, C + 106))
        informe = _analizar(C + 105, objetivos, objetivos)
        assert informe.resueltos_consecutivos_desde_el_corte == 105
        assert informe.total_resueltos_descriptivo == 105
        assert informe.cien_consecutivos_desde_el_corte is True

    def test_secuencia_ae53_es_la_llamada_directa(self):
        for nombre in ("C1", "C2", "C4", "C5", "cien"):
            ultimo, prediccion, resultado = _caso(nombre)
            directo = validar_secuencia_objetivos(corte=C, ultimo_sorteo_ocurrido=ultimo,
                                                  objetivos_con_prediccion=prediccion,
                                                  objetivos_con_resultado=resultado)
            informe = _analizar(ultimo, prediccion, resultado)
            assert informe.secuencia_ae53 == directo
            assert informe.estado_segun_propuesta_ae53 == directo.estado


# ---------------------------------------------------------------------------
# Consecuencias de cada alternativa en los tres momentos
# ---------------------------------------------------------------------------

class TestMomentos:
    @pytest.mark.parametrize("nombre", ["C1", "C2"])
    def test_pendientes_o_futuros_sin_omision(self, nombre):
        informe = _analizar(*_caso(nombre))
        resueltos = informe.total_resueltos_descriptivo
        assert _resumen(informe) == {a: (resueltos, "puede_alcanzar_100", "sin_conflicto_conocido")
                                     for a in so.ALTERNATIVAS_OMISION}

    def test_cien_consecutivos_desde_el_corte(self):
        informe = _analizar(*_caso("cien"))
        assert informe.cien_consecutivos_desde_el_corte is True
        assert informe.estado_segun_propuesta_ae53 == "completa"
        assert _resumen(informe) == {a: (100, "alcanza_100_hipotetico", "sin_conflicto_conocido")
                                     for a in so.ALTERNATIVAS_OMISION}
        for consecuencia in informe.consecuencias:
            assert consecuencia.conjunto_hipotetico_contado == VENTANA

    def test_omision_y_resultados_posteriores_que_suman_cien(self):
        informe = _analizar(*_caso("C4"))
        assert _resumen(informe) == {
            "no_evaluable": (99, "no_puede_alcanzar_100", "sin_conflicto_conocido"),
            "ventana_fija_sin_ampliar": (99, "no_puede_alcanzar_100", "incompatible_con_minimo"),
            "ampliar_ventana": (100, "alcanza_100_hipotetico", "no_establecida_requiere_interpretacion"),
            "reemplazar_objetivo": (100, "alcanza_100_hipotetico", "incompatible_con_sin_sustitucion"),
        }
        alternativas = _por_alternativa(informe)
        esperado = tuple(o for o in range(C + 1, C + 102) if o != C + 50)
        assert alternativas["ampliar_ventana"].conjunto_hipotetico_contado == esperado
        assert alternativas["reemplazar_objetivo"].conjunto_hipotetico_contado == esperado
        assert alternativas["no_evaluable"].conjunto_hipotetico_contado == tuple(o for o in VENTANA if o != C + 50)

    def test_omision_sin_resultados_suficientes(self):
        informe = _analizar(*_caso("C5"))
        resumen = _resumen(informe)
        assert resumen["no_evaluable"] == (50, "no_puede_alcanzar_100", "sin_conflicto_conocido")
        assert resumen["ventana_fija_sin_ampliar"] == (50, "no_puede_alcanzar_100", "incompatible_con_minimo")
        assert resumen["ampliar_ventana"] == (50, "puede_alcanzar_100", "no_establecida_requiere_interpretacion")
        assert resumen["reemplazar_objetivo"] == (50, "puede_alcanzar_100", "incompatible_con_sin_sustitucion")

    def test_ampliar_y_reemplazar_cuentan_como_maximo_cien(self):
        objetivos = [o for o in range(C + 1, C + 111) if o != C + 50]
        informe = _analizar(C + 110, objetivos, objetivos)
        alternativas = _por_alternativa(informe)
        assert alternativas["ampliar_ventana"].conjunto_hipotetico_contado == tuple(objetivos[:100])
        assert alternativas["reemplazar_objetivo"].recuento_hipotetico == 100


# ---------------------------------------------------------------------------
# Entradas: invariante de AE-52 y errores heredados de AE-53
# ---------------------------------------------------------------------------

class TestEntradas:
    def test_c3_prediccion_mas_alla_del_siguiente_sorteo_se_rechaza(self):
        with pytest.raises(so.SemanticaOmisionesError, match="AE-52"):
            _analizar(C, list(VENTANA), [])

    def test_prediccion_del_siguiente_sorteo_se_admite(self):
        informe = _analizar(C + 10, list(range(C + 1, C + 12)), list(range(C + 1, C + 11)))
        assert informe.secuencia_ae53.futuros[0] == C + 11

    def test_misma_entrada_que_ae53_acepta_c3_sin_rechazo(self):
        # El dominio de AE-53 es mas amplio que los estados posibles de AE-52.
        informe = validar_secuencia_objetivos(corte=C, ultimo_sorteo_ocurrido=C,
                                              objetivos_con_prediccion=list(VENTANA), objetivos_con_resultado=[])
        assert len(informe.futuros) == 100

    @pytest.mark.parametrize("argumentos", [
        dict(ultimo=C + 3, prediccion=[C], resultado=[]),
        dict(ultimo=C + 3, prediccion=[C + 1, C + 1], resultado=[]),
        dict(ultimo=C + 3, prediccion=[C + 1], resultado=[C + 2]),
        dict(ultimo=C + 3, prediccion=[True], resultado=[]),
        dict(ultimo=C - 1, prediccion=[], resultado=[]),
    ])
    def test_errores_de_ae53_se_propagan(self, argumentos):
        with pytest.raises(EspecificacionProspectivaError):
            _analizar(argumentos["ultimo"], argumentos["prediccion"], argumentos["resultado"])


# ---------------------------------------------------------------------------
# Coherencia con el resumen de AE-52 (registro sintetico en memoria)
# ---------------------------------------------------------------------------

def _registro_sintetico(objetivos):
    estrategia = {
        "nombre": "estrategia_sintetica", "descripcion": "estrategia sintetica solo para pruebas",
        "huella_codigo": "a" * 64, "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
        "entorno": {"python": "3.x", "scikit_learn": "0.0"},
    }
    protocolo = rp.construir_protocolo(protocolo_id="sintetico-ae58", estrategia=estrategia,
                                       cortes={"BALOTO": C, "BALOTO_REVANCHA": C}, pendientes=[], sintetico=True)
    entradas = [rp.serializar_entrada(protocolo)]
    for objetivo in objetivos:
        prediccion = rp.nueva_prediccion(rp.validar_registro(entradas), "BALOTO", objetivo,
                                         sinteticos.historico(2081, objetivo - 1, a=7, b=9, c=5), [0.1] * 43)
        entradas.append(rp.serializar_entrada(prediccion))
        resultado = rp.nuevo_resultado(rp.validar_registro(entradas), "BALOTO", objetivo, (1, 2, 3, 4, 5))
        entradas.append(rp.serializar_entrada(resultado))
    return rp.resumir_registro(rp.validar_registro(entradas))["juegos"][0]


def test_c4_coincide_con_el_recuento_descriptivo_de_ae52():
    juego = _registro_sintetico(_C4_PREDICCION)
    informe = _analizar(*_caso("C4"))
    assert juego["codigo"] == "BALOTO"
    assert juego["resultados_incorporados"] == informe.total_resueltos_descriptivo == 100
    assert juego["faltantes"] == informe.faltantes_como_en_resumen_ae52 == 0
    assert juego["omisiones"] == [C + 50] == list(informe.omisiones_en_ventana)
    assert informe.cien_consecutivos_desde_el_corte is False


def test_ae52_exige_la_entrada_hasta_el_sorteo_anterior():
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        estrategia = {
            "nombre": "estrategia_sintetica", "descripcion": "sintetica", "huella_codigo": "a" * 64,
            "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
            "entorno": {"python": "3.x", "scikit_learn": "0.0"},
        }
        protocolo = rp.construir_protocolo(protocolo_id="sintetico-ae58", estrategia=estrategia,
                                           cortes={"BALOTO": C, "BALOTO_REVANCHA": C}, pendientes=[], sintetico=True)
        estado = rp.validar_registro([rp.serializar_entrada(protocolo)])
        rp.nueva_prediccion(estado, "BALOTO", C + 5, sinteticos.historico(2081, C, a=7, b=9, c=5), [0.1] * 43)


# ---------------------------------------------------------------------------
# Vocabulario cerrado: sin aprobaciones ni autorizaciones
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre", ["C1", "C2", "C4", "C5", "cien"])
def test_vocabulario_cerrado_y_sin_autorizacion(nombre):
    informe = _analizar(*_caso(nombre))
    assert informe.decision == "sin_decidir"
    assert informe.autoriza_evaluacion is False
    assert informe.estado_segun_propuesta_ae53 in ("completa", "incompleta", "no_evaluable_por_omision")
    assert tuple(c.alternativa for c in informe.consecuencias) == so.ALTERNATIVAS_OMISION
    for consecuencia in informe.consecuencias:
        assert consecuencia.origen in so.ORIGENES
        assert consecuencia.estado_recuento_hipotetico in so.ESTADOS_RECUENTO
        assert consecuencia.relacion_con_reglas_ae52 in so.RELACIONES_AE52
        assert consecuencia.autoriza_evaluacion is False
    origenes = {c.alternativa: c.origen for c in informe.consecuencias}
    assert origenes == {"no_evaluable": "propuesta_ae53_no_aprobada", "ventana_fija_sin_ampliar": "sin_decidir",
                        "ampliar_ventana": "sin_decidir", "reemplazar_objetivo": "sin_decidir"}


def test_vocabularios_exactos():
    assert so.ALTERNATIVAS_OMISION == ("no_evaluable", "ventana_fija_sin_ampliar", "ampliar_ventana",
                                       "reemplazar_objetivo")
    assert so.ORIGENES == ("propuesta_ae53_no_aprobada", "sin_decidir")
    assert so.ESTADOS_RECUENTO == ("alcanza_100_hipotetico", "no_puede_alcanzar_100", "puede_alcanzar_100")
    assert so.RELACIONES_AE52 == ("incompatible_con_minimo", "incompatible_con_sin_sustitucion",
                                  "no_establecida_requiere_interpretacion", "sin_conflicto_conocido")


def test_separa_fijado_propuesto_y_sin_decidir():
    informe = _analizar(*_caso("C4"))
    assert informe.fijado_por_ae52 == ("minimo_sorteos_resueltos_por_juego", "sin_agregados_antes_del_minimo",
                                       "sorteos_consecutivos_sin_sustitucion")
    assert informe.propuesto_por_ae53 == ("horizonte", "omisiones")
    assert informe.sin_decidir == ("ampliar_equivale_a_sustituir", "serie_consecutiva_posterior_al_corte",
                                   "tratamiento_de_omisiones")


def test_informes_inmutables():
    informe = _analizar(*_caso("C4"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        informe.decision = "otra"
    with pytest.raises(dataclasses.FrozenInstanceError):
        informe.consecuencias[0].autoriza_evaluacion = True


# ---------------------------------------------------------------------------
# R9 de AE-56: condicion necesaria, no suficiente (solo cambia el mensaje)
# ---------------------------------------------------------------------------

def test_r9_mensaje_y_comportamiento():
    informe = dr.validar_especificacion_diseno({"ventana": {"objetivos": 99, "analisis": 1}})
    assert informe.estado == "incoherente"
    assert informe.violaciones == ("R9 ventana.objetivos: entero >= 100 (condicion necesaria, no suficiente, "
                                   "del minimo de AE-52 de 100 resueltos; sin reduccion retroactiva)",)
    informe = dr.validar_especificacion_diseno({"ventana": {"objetivos": 100, "analisis": 1}})
    assert informe.coincide_con_propuesta_ae53 == ("ventana",)


# ---------------------------------------------------------------------------
# Constantes intactas y aislamiento
# ---------------------------------------------------------------------------

def test_constantes_intactas():
    antes = json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                       sort_keys=True)
    for nombre in ("C1", "C4", "cien"):
        _analizar(*_caso(nombre))
    assert json.dumps([REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53, list(PENDIENTES_BORRADOR_AE52)],
                      sort_keys=True) == antes
    assert len(PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"


def test_modulo_puro_y_aislado():
    arbol = ast.parse(ARCHIVO.read_text(encoding="utf-8"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add(nodo.module or "")
    assert modulos <= {"__future__", "collections.abc", "dataclasses",
                       "app.application.ml.especificacion_evaluacion_prospectiva",
                       "app.application.ml.registro_prospectivo"}, modulos


def test_no_expuesto_en_la_web_ni_en_scripts():
    raiz = RAIZ_BACKEND / "app"
    rutas = [*(raiz / "api").rglob("*.py"), raiz / "main.py", *(raiz / "templates").rglob("*.html"),
             *(RAIZ_BACKEND / "scripts").rglob("*.py")]
    for ruta in rutas:
        assert "semantica_omisiones_prospectivas" not in ruta.read_text(encoding="utf-8"), ruta


# ---------------------------------------------------------------------------
# Divergencias de la base de AE-52 / AE-53: explicitas, nunca filtradas
# ---------------------------------------------------------------------------

def test_base_actual_verificada_sin_divergencias():
    so.verificar_base_ae52_ae53()


@pytest.mark.parametrize("clave", ["minimo_sorteos_resueltos_por_juego", "sin_agregados_antes_del_minimo",
                                   "sorteos_consecutivos_sin_sustitucion"])
def test_regla_ae52_ausente_se_detecta(monkeypatch, clave):
    reglas = {k: v for k, v in REGLAS_EVALUACION_AE52.items() if k != clave}
    monkeypatch.setattr(so, "REGLAS_EVALUACION_AE52", reglas)
    with pytest.raises(so.BaseDivergenteError, match=clave):
        _analizar(*_caso("C1"))


@pytest.mark.parametrize("clave, valor", [("minimo_sorteos_resueltos_por_juego", 99),
                                          ("minimo_sorteos_resueltos_por_juego", 100.0),
                                          ("sin_agregados_antes_del_minimo", False),
                                          ("sorteos_consecutivos_sin_sustitucion", 1)])
def test_regla_ae52_con_otro_valor_se_detecta(monkeypatch, clave, valor):
    monkeypatch.setattr(so, "REGLAS_EVALUACION_AE52", {**REGLAS_EVALUACION_AE52, clave: valor})
    with pytest.raises(so.BaseDivergenteError, match=clave):
        _analizar(*_caso("C1"))


def _especificacion_con(clave, propuesta):
    especificacion = copy.deepcopy(ESPECIFICACION_CANDIDATA_AE53)
    if propuesta is None:
        del especificacion["propuestas"][clave]
    else:
        especificacion["propuestas"][clave] = propuesta
    return especificacion


@pytest.mark.parametrize("clave", ["horizonte", "omisiones"])
@pytest.mark.parametrize("cambio", ["ausente", "aprobada", "otro_valor"])
def test_propuesta_ae53_ausente_aprobada_o_distinta_se_detecta(monkeypatch, clave, cambio):
    original = ESPECIFICACION_CANDIDATA_AE53["propuestas"][clave]
    propuesta = {"ausente": None,
                 "aprobada": {**original, "estado": "aprobada"},
                 "otro_valor": {**original, "valor_propuesto": "otro"}}[cambio]
    monkeypatch.setattr(so, "ESPECIFICACION_CANDIDATA_AE53", _especificacion_con(clave, propuesta))
    with pytest.raises(so.BaseDivergenteError, match=clave):
        _analizar(*_caso("C1"))


def test_la_divergencia_es_un_error_de_semantica():
    assert issubclass(so.BaseDivergenteError, so.SemanticaOmisionesError)
