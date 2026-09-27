"""Tests de `app/application/ml/diseno_regla_prospectiva.py` -Etapa
AE-56, validada: contrato de coherencia del diseno de una regla
prospectiva. Todo sintetico: especificaciones candidatas construidas a
mano; sin datos reales, PostgreSQL, entrenamiento ni predicciones. El
validador solo comprueba la consistencia de los campos declarados: no
aprueba, no verifica supuestos, procedencia ni validez inferencial."""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import math
from pathlib import Path

import pytest

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52

ARCHIVO = Path(dr.__file__)
RAIZ_BACKEND = ARCHIVO.resolve().parents[3]


def _p1(**cambios):
    """Candidata sintetica completa para P1 (solo para probar coherencia)."""
    candidata = {
        "pregunta": "P1",
        "direccion": "mejora",
        "nivel_unilateral": 0.025,
        "metodo": {"familia": "t_media_varianza_hac", "parametros": {"kernel": "bartlett", "ancho_banda": 4}},
        "supuestos_declarados": ["estacionariedad_en_covarianza", "ancho_banda_adecuado"],
        "metricas_principales": {"metricas": ["log_loss", "brier_score"], "combinacion": "conjuncion"},
        "secundaria": {"metricas": ["precision_en_5"], "papel": "descriptiva"},
        "multiplicidad": {"afirmacion_conjunta_juegos": False},
        "ventana": {"objetivos": 100, "analisis": 1},
        "efecto_minimo": {"valor": 0.3, "unidad": "sigma"},
        "sellado_declarado": "rfc3161",
        "fuente_hora_oficial_declarada": "acta oficial del sorteo",
    }
    candidata.update(cambios)
    return candidata


def _p2(**cambios):
    candidata = _p1(pregunta="P2", direccion="no_direccional",
                    metodo={"familia": "contraste_condicional",
                            "parametros": {"funcion_prueba": ["constante", "d_t_menos_1"]}},
                    supuestos_declarados=["memoria_limitada_o_parametros_congelados", "aproximacion_asintotica"])
    del candidata["nivel_unilateral"]
    candidata["nivel_contraste"] = 0.05
    candidata.update(cambios)
    return candidata


def _sin(candidata, *rutas):
    candidata = copy.deepcopy(candidata)
    for ruta in rutas:
        nodo = candidata
        *padres, hoja = ruta.split(".")
        for parte in padres:
            nodo = nodo[parte]
        del nodo[hoja]
    return candidata


def _con(candidata, ruta, valor):
    candidata = copy.deepcopy(candidata)
    nodo = candidata
    *padres, hoja = ruta.split(".")
    for parte in padres:
        nodo = nodo[parte]
    nodo[hoja] = valor
    return candidata


def _validar(candidata):
    return dr.validar_especificacion_diseno(candidata)


# ---------------------------------------------------------------------------
# Catalogo profundamente inmutable y canonico
# ---------------------------------------------------------------------------

def _sin_mutables(valor):
    if isinstance(valor, (set, list, dict)):
        return False
    if isinstance(valor, tuple):
        return all(_sin_mutables(v) for v in valor)
    if dataclasses.is_dataclass(valor):
        return all(_sin_mutables(getattr(valor, f.name)) for f in dataclasses.fields(valor))
    return valor is None or isinstance(valor, str)


class TestCatalogo:
    def test_categorias_ordenadas_validas_y_multiples(self):
        assert dr.CATEGORIAS == tuple(sorted(dr.CATEGORIAS))
        for dimension in dr.DIMENSIONES_AE56:
            assert dimension.categorias and dimension.categorias == tuple(sorted(set(dimension.categorias)))
            assert set(dimension.categorias) <= set(dr.CATEGORIAS)
            assert dimension.base == "inferencia_propia" or dimension.base.startswith("lit:")
        assert any(len(d.categorias) > 1 for d in dr.DIMENSIONES_AE56)

    def test_profundamente_inmutable(self):
        assert isinstance(dr.DIMENSIONES_AE56, tuple)
        for dimension in dr.DIMENSIONES_AE56:
            assert _sin_mutables(dimension), dimension.id
            with pytest.raises(dataclasses.FrozenInstanceError):
                dimension.categorias = ("pendiente_bloqueado",)
        with pytest.raises(TypeError):
            dr.SUPUESTOS_POR_FAMILIA["remuestreo_iid_media"] = ()
        assert all(isinstance(v, tuple) and v == tuple(sorted(v)) for v in dr.SUPUESTOS_POR_FAMILIA.values())

    @pytest.mark.parametrize("cambio", [
        dict(categorias=("supuesto_no_verificable", "justificable_antes_de_datos")),
        dict(categorias=("justificable_antes_de_datos", "justificable_antes_de_datos")),
        dict(categorias=("aprobada",)), dict(categorias=()), dict(base="opinion"),
    ])
    def test_dimension_invalida(self, cambio):
        base = dr.DIMENSIONES_AE56[0]
        with pytest.raises(dr.DisenoReglaInvalidoError):
            dataclasses.replace(base, **cambio)

    def test_dependencias_sin_ciclos(self):
        ids = {d.id for d in dr.DIMENSIONES_AE56}
        grafo = {d.id: set(d.depende_de) for d in dr.DIMENSIONES_AE56}
        assert all(dep <= ids for dep in grafo.values())
        visitados, en_curso = set(), set()

        def visitar(nodo):
            assert nodo not in en_curso, f"ciclo en {nodo}"
            if nodo in visitados:
                return
            en_curso.add(nodo)
            for dep in grafo[nodo]:
                visitar(dep)
            en_curso.discard(nodo)
            visitados.add(nodo)

        for nodo in grafo:
            visitar(nodo)

    def test_cubre_los_pendientes_de_ae52_y_ae53(self):
        fuentes = {f for d in dr.DIMENSIONES_AE56 for f in d.fuentes}
        for pendiente in PENDIENTES_BORRADOR_AE52:
            assert f"ae52:pendiente:{pendiente}" in fuentes, pendiente
        for pendiente in ESPECIFICACION_CANDIDATA_AE53["pendientes"]:
            assert f"ae53:pendiente:{pendiente}" in fuentes, pendiente

    def test_huella_canonica_estable_y_sensible(self):
        huella = dr.huella_diseno()
        assert len(huella) == 64 and huella == dr.huella_diseno()
        alterado = (dataclasses.replace(dr.DIMENSIONES_AE56[0], descripcion="otra"),) + dr.DIMENSIONES_AE56[1:]
        assert dr.huella_diseno(alterado) != huella
        assert dr.serializar_catalogo().endswith(b"\n") and b"\r" not in dr.serializar_catalogo()


# ---------------------------------------------------------------------------
# Entradas canonicas, bool y no finitos
# ---------------------------------------------------------------------------

class TestCanonicidad:
    def test_misma_huella_con_otro_orden_de_claves(self):
        a = _p1()
        b = dict(reversed(list(_p1().items())))
        assert _validar(a).huella == _validar(b).huella is not None

    @pytest.mark.parametrize("candidata", [
        [("pregunta", "P1")], "P1", None,
        _p1(supuestos_declarados={"estacionariedad_en_covarianza"}),
        _p1(sellado_declarado=b"rfc3161"),
        _p1(fuente_hora_oficial_declarada=object()),
        {1: "P1"},
        _p1(metodo={"familia": "t_media_varianza_hac", "parametros": {2: 4}}),
    ])
    def test_tipos_no_canonicos_se_rechazan(self, candidata):
        with pytest.raises(dr.DisenoReglaInvalidoError):
            _validar(candidata)

    @pytest.mark.parametrize("ruta, valor", [
        ("metodo.parametros.ancho_banda", True), ("ventana.objetivos", True), ("ventana.analisis", False),
        ("nivel_unilateral", True),
    ])
    def test_bool_donde_se_espera_numero_es_incoherente(self, ruta, valor):
        informe = _validar(_con(_p1(), ruta, valor))
        assert informe.estado == "incoherente"

    def test_bool_en_bloques_y_replicas(self):
        base = _p1(metodo={"familia": "remuestreo_bloques_media",
                           "parametros": {"replicas": 999, "semilla": 1, "variante": "circular", "longitud_bloque": 5}},
                   supuestos_declarados=list(dr.SUPUESTOS_POR_FAMILIA["remuestreo_bloques_media"]))
        assert _validar(base).estado == "coherente_no_aprobada"
        for campo in ("longitud_bloque", "replicas"):
            assert _validar(_con(base, f"metodo.parametros.{campo}", True)).estado == "incoherente"

    @pytest.mark.parametrize("ruta", ["nivel_unilateral", "efecto_minimo.valor"])
    @pytest.mark.parametrize("valor", [math.nan, math.inf, -math.inf])
    def test_no_finitos_incoherentes_y_sin_huella(self, ruta, valor):
        informe = _validar(_con(_p1(), ruta, valor))
        assert informe.estado == "incoherente"
        assert informe.huella is None
        assert any("no finito" in v for v in informe.violaciones)

    def test_potencia_no_finita_sin_huella(self):
        informe = _validar(_p1(potencia_objetivo=math.nan))
        assert informe.estado == "incoherente" and informe.huella is None

    def test_campo_desconocido_es_incoherente(self):
        assert _validar(_p1(nivel_aprobado=True)).estado == "incoherente"


# ---------------------------------------------------------------------------
# Ausencia frente a contradiccion
# ---------------------------------------------------------------------------

class TestAusenciaFrenteAContradiccion:
    def test_candidata_vacia_incompleta(self):
        informe = _validar({})
        assert informe.estado == "incompleta"
        assert informe.violaciones == ()
        assert {"pregunta", "direccion", "metodo.familia", "ventana"} <= set(informe.sin_decidir)

    @pytest.mark.parametrize("ruta", ["supuestos_declarados", "fuente_hora_oficial_declarada", "sellado_declarado",
                                      "efecto_minimo.unidad", "ventana", "secundaria.papel", "nivel_unilateral"])
    def test_ausencia_es_incompleta(self, ruta):
        informe = _validar(_sin(_p1(), ruta))
        assert informe.estado == "incompleta", informe.violaciones
        assert informe.violaciones == ()

    def test_none_es_sin_decidir(self):
        assert _validar(_p1(pregunta=None)).estado == "incompleta"

    def test_falta_longitud_de_bloque_es_incompleta(self):
        candidata = _p1(metodo={"familia": "remuestreo_bloques_media",
                                "parametros": {"replicas": 999, "semilla": 1, "variante": "circular"}},
                        supuestos_declarados=list(dr.SUPUESTOS_POR_FAMILIA["remuestreo_bloques_media"]))
        informe = _validar(candidata)
        assert informe.estado == "incompleta" and "metodo.parametros.longitud_bloque" in informe.sin_decidir

    def test_supuestos_declarados_incompletos_son_incoherentes(self):
        informe = _validar(_p1(supuestos_declarados=["estacionariedad_en_covarianza"]))
        assert informe.estado == "incoherente"

    def test_afirmacion_conjunta_sin_correccion_incompleta_y_correccion_invalida_incoherente(self):
        sin = _validar(_p1(multiplicidad={"afirmacion_conjunta_juegos": True}))
        assert sin.estado == "incompleta" and "multiplicidad.correccion" in sin.sin_decidir
        invalida = _validar(_p1(multiplicidad={"afirmacion_conjunta_juegos": True, "correccion": "ninguna"}))
        assert invalida.estado == "incoherente"
        valida = _validar(_p1(multiplicidad={"afirmacion_conjunta_juegos": True, "correccion": "holm"}))
        assert valida.estado == "coherente_no_aprobada"

    def test_unidad_ausente_incompleta_e_invalida_incoherente(self):
        assert _validar(_sin(_p1(), "efecto_minimo.unidad")).estado == "incompleta"
        assert _validar(_con(_p1(), "efecto_minimo.unidad", "puntos")).estado == "incoherente"

    def test_contradiccion_mas_ausencia_prioriza_incoherente_y_lista_ambas(self):
        informe = _validar(_sin(_p1(direccion="no_direccional"), "sellado_declarado"))
        assert informe.estado == "incoherente"
        assert informe.violaciones and "sellado_declarado" in informe.sin_decidir


# ---------------------------------------------------------------------------
# Reglas R1-R12 (campos presentes y contradictorios)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("candidata", [
    _p1(pregunta="P3"),                                                    # R1
    _p1(pregunta="P4"),                                                    # R1
    _p1(direccion="no_direccional"),                                       # R2
    _p1(nivel_contraste=0.05),                                             # R2 campo de P2 en P1
    _p1(nivel_unilateral=0.5),                                             # R2 rango
    _p2(direccion="mejora"),                                               # R2
    _p2(nivel_unilateral=0.025),                                           # R2 campo de P1 en P2
    _p2(nivel_contraste=1.0),                                              # R2 rango
    _p1(metodo={"familia": "contraste_condicional", "parametros": {"funcion_prueba": ["constante"]}},
        supuestos_declarados=list(dr.SUPUESTOS_POR_FAMILIA["contraste_condicional"])),  # R3
    _p2(metodo={"familia": "t_media_sin_autocorrelacion"},
        supuestos_declarados=["sin_autocorrelacion_de_d_t"]),              # R3
    _p1(metodo={"familia": "familia_inventada"}),                          # R3
    _p1(metodo={"familia": "t_media_varianza_hac", "parametros": {"kernel": "bartlett", "ancho_banda": -1}}),  # R4
    _p1(metodo={"familia": "t_media_varianza_hac", "parametros": {"kernel": "", "ancho_banda": 4}}),           # R4
    _p1(metodo={"familia": "t_media_varianza_hac", "parametros": {"kernel": "bartlett", "ancho_banda": 4, "extra": 1}}),
    _p2(metodo={"familia": "contraste_condicional", "parametros": {"funcion_prueba": 2}}),                   # R4
    _p2(metodo={"familia": "contraste_condicional", "parametros": {"funcion_prueba": []}}),                  # R4
    _p2(metodo={"familia": "contraste_condicional", "parametros": {"funcion_prueba": ["constante", "constante"]}}),
    _p2(metodo={"familia": "contraste_condicional", "parametros": {"funcion_prueba": ["constante", ""]}}),
    _p1(supuestos_declarados=["ancho_banda_adecuado"]),                    # R5
    _p1(metricas_principales={"metricas": ["log_loss"], "combinacion": "conjuncion"}),                       # R6
    _p1(metricas_principales={"metricas": ["log_loss", "brier_score"], "combinacion": "disyuncion"}),        # R6
    _p1(secundaria={"metricas": ["precision_en_5", "recall_en_5"], "papel": "descriptiva"}),                 # R7
    _p1(secundaria={"metricas": ["recall_en_5"], "papel": "descriptiva"}),                                   # R7
    _p1(multiplicidad={"afirmacion_conjunta_juegos": "si"}),                                                 # R8
    _p1(ventana={"objetivos": 99, "analisis": 1}),                                                           # R9
    _p1(ventana={"objetivos": 100, "analisis": 0}),                                                          # R9
    _p1(ventana={"objetivos": 100.0, "analisis": 1}),                                                        # R9
    _p2(efecto_minimo={"valor": 0.3, "unidad": "sigma", "calculado_con": "emd_ae55"}, potencia_objetivo=0.8),  # R10
    _p1(efecto_minimo={"valor": 0.3, "unidad": "sigma", "calculado_con": "emd_ae55"}, potencia_objetivo=0.02),  # R10
    _p1(efecto_minimo={"valor": 0.0, "unidad": "sigma"}),                                                    # R10
    _p1(efecto_minimo={"valor": -0.1, "unidad": "sigma"}),                                                   # R10
    _p1(potencia_objetivo=1.0),                                                                              # R10
    _p1(sellado_declarado="commit_firmado"),                                                                 # R11
    _p1(sellado_declarado="  "),                                                                             # R11
    _p1(fuente_hora_oficial_declarada=""),                                                                   # R12
    _p1(fuente_hora_oficial_declarada=5),                                                                    # R12
])
def test_reglas_incoherentes(candidata):
    informe = _validar(candidata)
    assert informe.estado == "incoherente", candidata
    assert informe.violaciones


# ---------------------------------------------------------------------------
# Distinciones del contrato
# ---------------------------------------------------------------------------

class TestDistinciones:
    def test_propuesta_exacta_de_ae53(self):
        informe = _validar(_p1())
        assert informe.estado == "coherente_no_aprobada"
        assert informe.coincide_con_propuesta_ae53 == ("ventana",)
        assert informe.alternativas_sin_aprobar == ()

    def test_ventana_mayor_es_alternativa_sin_aprobar(self):
        informe = _validar(_p1(ventana={"objetivos": 120, "analisis": 1}))
        assert informe.estado == "coherente_no_aprobada"
        assert informe.coincide_con_propuesta_ae53 == ()
        assert "ventana" in informe.alternativas_sin_aprobar

    def test_varios_analisis_exigen_decision_adicional(self):
        informe = _validar(_p1(ventana={"objetivos": 100, "analisis": 2}))
        assert informe.estado == "incompleta"
        assert informe.decisiones_adicionales_requeridas == ("analisis_repetidos_y_control_de_error",)
        assert "ventana" in informe.alternativas_sin_aprobar and informe.coincide_con_propuesta_ae53 == ()

    def test_referencia_al_banco_ae54_no_decide(self):
        a = _validar(_p1())
        b = _validar(_con(_p1(), "metodo.referencia_banco_ae54", "M3b"))
        assert (a.estado, a.violaciones, a.sin_decidir) == (b.estado, b.violaciones, b.sin_decidir)
        assert _validar(_con(_p1(), "metodo.referencia_banco_ae54", "M9")).estado == "incoherente"

    def test_p2_sin_emd_admite_cualquier_potencia_en_0_1(self):
        assert _validar(_p2(potencia_objetivo=0.01)).estado == "coherente_no_aprobada"

    def test_emd_ae55_en_p1_exige_potencia_en_su_dominio(self):
        sin_potencia = _p1(efecto_minimo={"valor": 0.28, "unidad": "sigma", "calculado_con": "emd_ae55"})
        assert _validar(sin_potencia).estado == "incompleta"
        assert _validar({**sin_potencia, "potencia_objetivo": 0.8}).estado == "coherente_no_aprobada"

    def test_emd_ae55_exige_familia_de_media(self):
        candidata = _p1(metodo={"familia": "contraste_condicional", "parametros": {"funcion_prueba": ["constante"]}},
                        efecto_minimo={"valor": 0.28, "unidad": "sigma", "calculado_con": "emd_ae55"},
                        potencia_objetivo=0.8)
        assert _validar(candidata).estado == "incoherente"

    def test_sellado_y_hora_solo_declarados(self):
        informe = _validar(_p1(sellado_declarado="rfc3161"))
        assert informe.estado == "coherente_no_aprobada"
        for no_verificado in ("sellado", "token", "manifiesto", "hora_oficial", "custodia", "anterioridad",
                              "procedencia", "supuestos", "autorizacion", "validez_inferencial"):
            assert no_verificado in informe.no_verifica

    def test_p2_completa_coherente(self):
        assert _validar(_p2()).estado == "coherente_no_aprobada"


# ---------------------------------------------------------------------------
# Estados, bloqueos e invariantes
# ---------------------------------------------------------------------------

class TestEstadosEInvariantes:
    def test_estados_cerrados_sin_aprobado(self):
        assert dr.ESTADOS == ("coherente_no_aprobada", "incoherente", "incompleta")
        for candidata in (_p1(), _p2(), {}, _p1(pregunta="P3")):
            informe = _validar(candidata)
            assert informe.estado in dr.ESTADOS
            assert "aprobad" not in informe.estado.replace("no_aprobada", "")

    def test_bloqueos_de_la_base_documentada(self):
        informe = _validar(_p1())
        assert informe.bloqueos_de_la_base_documentada[:3] == (
            "no_go_ae39", "ae41_bloqueado_datos_insuficientes", "ae46_desbloqueable_false")
        assert informe.bloqueos_de_la_base_documentada[3:] == tuple(PENDIENTES_BORRADOR_AE52)

    def test_informe_inmutable(self):
        informe = _validar(_p1())
        with pytest.raises(dataclasses.FrozenInstanceError):
            informe.estado = "aprobada"
        assert all(isinstance(getattr(informe, c), tuple) for c in (
            "violaciones", "sin_decidir", "decisiones_adicionales_requeridas", "coincide_con_propuesta_ae53",
            "alternativas_sin_aprobar", "no_verifica", "bloqueos_de_la_base_documentada"))

    def test_no_modifica_ae52_ae53_ni_la_candidata(self):
        antes = json.dumps([list(PENDIENTES_BORRADOR_AE52), REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53],
                           sort_keys=True)
        candidata = _p1()
        copia = copy.deepcopy(candidata)
        for c in (candidata, _p2(), {}, _p1(pregunta="P3")):
            _validar(c)
        assert json.dumps([list(PENDIENTES_BORRADOR_AE52), REGLAS_EVALUACION_AE52, ESPECIFICACION_CANDIDATA_AE53],
                          sort_keys=True) == antes
        assert candidata == copia
        assert len(PENDIENTES_BORRADOR_AE52) == 7 and "regla_estadistica_de_decision" in PENDIENTES_BORRADOR_AE52


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------

def test_modulo_puro_y_aislado():
    modulos = set()
    for nodo in ast.walk(ast.parse(ARCHIVO.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add(nodo.module or "")
    permitidos = {"__future__", "copy", "dataclasses", "hashlib", "json", "math", "types", "collections.abc",
                  "app.application.ml.registro_prospectivo", "app.application.ml.especificacion_evaluacion_prospectiva"}
    assert modulos <= permitidos, modulos - permitidos


def test_no_expuesto_en_la_web_ni_en_scripts():
    raiz = RAIZ_BACKEND / "app"
    rutas = [*(raiz / "api").rglob("*.py"), raiz / "main.py", *(raiz / "templates").rglob("*.html"),
             *(RAIZ_BACKEND / "scripts").rglob("*.py")]
    for ruta in rutas:
        assert "diseno_regla_prospectiva" not in ruta.read_text(encoding="utf-8"), ruta


# ---------------------------------------------------------------------------
# Regresiones v2: valores canonicos con tipo invalido nunca lanzan
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("candidata", [
    {"metricas_principales": {"metricas": ["log_loss", 1], "combinacion": "conjuncion"}},
    {"metodo": {"referencia_banco_ae54": []}},
    {"multiplicidad": {"afirmacion_conjunta_juegos": True, "correccion": []}},
    {"efecto_minimo": {"valor": 1, "unidad": []}},
    {"pregunta": "P1", "nivel_unilateral": 10 ** 400},
])
def test_casos_auditados_son_incoherentes_sin_excepcion(candidata):
    informe = _validar(candidata)
    assert informe.estado == "incoherente"
    assert informe.violaciones


def test_entero_enorme_es_finito_y_conserva_huella():
    informe = _validar(_p1(efecto_minimo={"valor": 10 ** 400, "unidad": "sigma"}))
    assert informe.estado == "coherente_no_aprobada"
    assert informe.huella is not None
    assert _validar(_p1(nivel_unilateral=-(10 ** 400))).estado == "incoherente"
    assert _validar(_p1(potencia_objetivo=10 ** 400)).estado == "incoherente"


_VALORES_RAROS = ([], {}, [1], ["x", 2], {"a": 1}, {"a": []}, 10 ** 400, -(10 ** 400), True, False, 0, -1, 1.5, "",
                  "texto", [None], [[]])


def _rutas(nodo, prefijo=()):
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            yield prefijo + (clave,)
            yield from _rutas(valor, prefijo + (clave,))
    elif isinstance(nodo, list):
        for i, valor in enumerate(nodo):
            yield prefijo + (i,)
            yield from _rutas(valor, prefijo + (i,))


def _sustituir(candidata, ruta, valor):
    candidata = copy.deepcopy(candidata)
    nodo = candidata
    for parte in ruta[:-1]:
        nodo = nodo[parte]
    nodo[ruta[-1]] = valor
    return candidata


_EMD_P1 = _p1(efecto_minimo={"valor": 0.28, "unidad": "sigma", "calculado_con": "emd_ae55"}, potencia_objetivo=0.8,
              multiplicidad={"afirmacion_conjunta_juegos": True, "correccion": "holm"},
              secundaria={"metricas": ["precision_en_5"], "papel": "descriptiva", "tolerancia": 0.02})
_BLOQUES = _p1(metodo={"familia": "remuestreo_bloques_media", "referencia_banco_ae54": "M2a",
                       "parametros": {"replicas": 999, "semilla": 1, "variante": "circular", "longitud_bloque": 5}},
               supuestos_declarados=list(dr.SUPUESTOS_POR_FAMILIA["remuestreo_bloques_media"]))


@pytest.mark.parametrize("base", [_p1(), _p2(), _EMD_P1, _BLOQUES], ids=["p1", "p2", "emd", "bloques"])
def test_barrido_de_valores_canonicos_no_lanza(base):
    for ruta in _rutas(base):
        for valor in _VALORES_RAROS:
            informe = _validar(_sustituir(base, ruta, valor))
            assert informe.estado in dr.ESTADOS, (ruta, valor)
            assert informe.huella is not None, (ruta, valor)


@pytest.mark.parametrize("clave", sorted(dr._CLAVES))
def test_barrido_de_campos_raiz_no_lanza(clave):
    for valor in _VALORES_RAROS:
        informe = _validar({clave: valor})
        assert informe.estado in dr.ESTADOS, (clave, valor)
        assert _validar(_p1(**{clave: valor})).estado in dr.ESTADOS, (clave, valor)


@pytest.mark.parametrize("ruta", [("pregunta",), ("metodo", "parametros", "semilla"), ("efecto_minimo", "valor")])
def test_entero_no_serializable_es_incoherente_sin_huella(ruta):
    """Un entero con 4300 o mas digitos decimales no se serializa: como un
    no finito, da incoherente y huella None, sin ValueError."""
    for valor in (10 ** 4300, -(10 ** 4300), 10 ** 5000):
        informe = _validar(_sustituir(_BLOQUES, ruta, valor))
        assert informe.estado == "incoherente", valor
        assert informe.huella is None
        assert any("no serializable" in v for v in informe.violaciones)
    limite = 10 ** 4300 - 1
    assert _validar(_sustituir(_BLOQUES, ("metodo", "parametros", "semilla"), limite)).huella is not None


def test_anidamiento_excesivo_se_rechaza_sin_recursion():
    anidado = []
    for _ in range(dr.PROFUNDIDAD_MAXIMA_CANDIDATA + 1):
        anidado = [anidado]
    with pytest.raises(dr.DisenoReglaInvalidoError, match="anidamiento"):
        _validar({"secundaria": {"tolerancia": anidado}})
    muy_anidado = []
    for _ in range(5000):
        muy_anidado = {"a": muy_anidado}
    with pytest.raises(dr.DisenoReglaInvalidoError, match="anidamiento"):
        _validar({"metodo": muy_anidado})
    admitido = []
    for _ in range(dr.PROFUNDIDAD_MAXIMA_CANDIDATA - 2):
        admitido = [admitido]
    assert _validar({"secundaria": {"tolerancia": admitido}}).estado == "incoherente"
