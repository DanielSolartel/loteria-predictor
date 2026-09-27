"""Tests de la Etapa AE-57, validada: auditoria del diseno prospectivo
(AE-52 a AE-56). Regresiones de los defectos verificables del validador
de AE-56 (`app/application/ml/diseno_regla_prospectiva.py`), escritas
antes de corregirlos. Todo sintetico: sin datos reales, PostgreSQL,
entrenamiento ni predicciones. No aprueban ninguna pregunta, metodo,
nivel, potencia, efecto, horizonte, tratamiento de omisiones ni regla
prospectiva."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52

ARCHIVO = Path(dr.__file__)
RAIZ_BACKEND = ARCHIVO.resolve().parents[3]

HUELLA_DISENO_BASE = "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"
"""`huella_diseno()` en la base de AE-57 (0bdaf0bc); AE-57 no cambia el catalogo."""


def _p1(**cambios):
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


def _sin(candidata, *claves):
    candidata = copy.deepcopy(candidata)
    for clave in claves:
        del candidata[clave]
    return candidata


def _validar(candidata):
    return dr.validar_especificacion_diseno(candidata)


_EMD = {"valor": 0.28, "unidad": "sigma", "calculado_con": "emd_ae55"}

REFERENCIAS = {
    "p1": (_p1(), "161960a86f61b26c0ed08567d6b93a8500db527b61402e050ea19bcad730d36e"),
    "p2": (_p2(), "59aca338fecdefe6d69e147926ced902a98b58642feb015fd08e57697428f154"),
    "emd": (_p1(efecto_minimo=dict(_EMD), potencia_objetivo=0.8,
                multiplicidad={"afirmacion_conjunta_juegos": True, "correccion": "holm"}),
            "0a760956d726aa00b23c9458012ea6b7e5c107e8e7b5e940a9ced38ef4fe4bdd"),
    "bloques": (_p1(metodo={"familia": "remuestreo_bloques_media", "referencia_banco_ae54": "M2a",
                            "parametros": {"replicas": 999, "semilla": 1, "variante": "circular",
                                           "longitud_bloque": 5}},
                    supuestos_declarados=["dependencia_debil", "estacionariedad", "memoria_menor_que_longitud_bloque"]),
                "b47d122d00a74be76a838bb7679e05827cb7cec8c870855b36a9c7679036944a"),
}
"""Candidatas pequenas de referencia y su huella en la base (calculada antes de corregir)."""


# ---------------------------------------------------------------------------
# D1-D4: un campo presente contradictorio es incoherente; la ausencia, incompleta
# ---------------------------------------------------------------------------

class TestD1SupuestosSinMetodo:
    @pytest.mark.parametrize("supuestos", [5, "texto", [1], ["", "x"], {"a": 1}])
    def test_tipo_invalido_sin_metodo_es_incoherente(self, supuestos):
        informe = _validar(_sin(_p1(), "metodo") | {"supuestos_declarados": supuestos})
        assert informe.estado == "incoherente"
        assert any(v.startswith("R5 supuestos_declarados") for v in informe.violaciones)

    def test_tipo_invalido_con_metodo_no_objeto_es_incoherente(self):
        informe = _validar(_p1(metodo=3, supuestos_declarados=5))
        assert any(v.startswith("R5 supuestos_declarados") for v in informe.violaciones)

    def test_lista_valida_sin_metodo_sigue_incompleta(self):
        informe = _validar(_sin(_p1(), "metodo"))
        assert informe.estado == "incompleta"
        assert "metodo.familia" in informe.sin_decidir

    def test_ausencia_de_ambos_sigue_incompleta(self):
        informe = _validar(_sin(_p1(), "metodo", "supuestos_declarados"))
        assert informe.estado == "incompleta"
        assert "supuestos_declarados" in informe.sin_decidir


class TestD2ParametrosSinFamilia:
    @pytest.mark.parametrize("parametros", [5, "x", [1], True])
    def test_parametros_no_objeto_sin_familia_es_incoherente(self, parametros):
        informe = _validar(_p1(metodo={"parametros": parametros}))
        assert informe.estado == "incoherente"
        assert any(v.startswith("R4 metodo.parametros") for v in informe.violaciones)

    def test_parametros_no_objeto_con_familia_invalida_se_senala(self):
        informe = _validar(_p1(metodo={"familia": "inventada", "parametros": 5}))
        assert any(v.startswith("R4 metodo.parametros") for v in informe.violaciones)

    def test_parametros_objeto_sin_familia_no_se_juzgan(self):
        informe = _validar(_p1(metodo={"parametros": {"replicas": -3, "cualquiera": 1}}))
        assert informe.estado == "incompleta"
        assert "metodo.familia" in informe.sin_decidir


class TestD3NivelesSinPregunta:
    @pytest.mark.parametrize("campo, valor", [
        ("nivel_unilateral", -1), ("nivel_unilateral", 0), ("nivel_unilateral", 0.5), ("nivel_unilateral", 0.9),
        ("nivel_contraste", 0), ("nivel_contraste", 1), ("nivel_contraste", 7), ("nivel_contraste", -0.1),
    ])
    @pytest.mark.parametrize("pregunta", [None, "P4", 5])
    def test_nivel_fuera_de_su_rango_es_incoherente(self, campo, valor, pregunta):
        candidata = _sin(_p1(), "pregunta", "nivel_unilateral") | {campo: valor}
        if pregunta is not None:
            candidata["pregunta"] = pregunta
        informe = _validar(candidata)
        assert informe.estado == "incoherente"
        assert any(v.startswith(f"R2 {campo}") for v in informe.violaciones)

    @pytest.mark.parametrize("campo, valor", [("nivel_unilateral", 0.025), ("nivel_unilateral", 0.49),
                                              ("nivel_contraste", 0.05), ("nivel_contraste", 0.9)])
    def test_nivel_en_rango_sin_pregunta_sigue_incompleta(self, campo, valor):
        informe = _validar(_sin(_p1(), "pregunta", "nivel_unilateral") | {campo: valor})
        assert informe.estado == "incompleta"
        assert "pregunta" in informe.sin_decidir


class TestD4UnidadDelEmd:
    def test_emd_ae55_en_unidad_de_metrica_es_incoherente(self):
        informe = _validar(_p1(efecto_minimo=dict(_EMD, unidad="unidad_de_metrica"), potencia_objetivo=0.8))
        assert informe.estado == "incoherente"
        assert any("sigma" in v and v.startswith("R10") for v in informe.violaciones)

    def test_emd_ae55_sin_unidad_sigue_incompleta(self):
        efecto = dict(_EMD)
        del efecto["unidad"]
        informe = _validar(_p1(efecto_minimo=efecto, potencia_objetivo=0.8))
        assert informe.estado == "incompleta"
        assert "efecto_minimo.unidad" in informe.sin_decidir

    def test_emd_ae55_en_sigma_sigue_coherente(self):
        assert _validar(_p1(efecto_minimo=dict(_EMD), potencia_objetivo=0.8)).estado == "coherente_no_aprobada"

    def test_unidad_de_metrica_sin_emd_sigue_coherente(self):
        informe = _validar(_p1(efecto_minimo={"valor": 0.01, "unidad": "unidad_de_metrica"}))
        assert informe.estado == "coherente_no_aprobada"


# ---------------------------------------------------------------------------
# D5-D6: limite de AE-57 para enteros (640 digitos decimales)
# ---------------------------------------------------------------------------

_DIGITOS_640 = 10 ** 640 - 1
_DIGITOS_641 = 10 ** 640


def test_limite_publico_de_640_digitos():
    assert dr.DIGITOS_MAXIMOS_ENTERO_CANDIDATA == 640
    assert sys.int_info.str_digits_check_threshold == 640


@pytest.mark.parametrize("valor", [_DIGITOS_640, -_DIGITOS_640], ids=["640", "-640"])
def test_entero_de_640_digitos_conserva_la_huella(valor):
    informe = _validar(_p1(metodo={"familia": "remuestreo_iid_media", "parametros": {"replicas": 9, "semilla": valor}},
                           supuestos_declarados=["independencia_de_d_t"]))
    assert informe.estado == "coherente_no_aprobada"
    assert informe.huella is not None


@pytest.mark.parametrize("valor", [_DIGITOS_641, -_DIGITOS_641, 10 ** 4299, 10 ** 4300, 10 ** 5000],
                         ids=["641", "-641", "4300", "4301", "5001"])
def test_entero_de_mas_de_640_digitos_es_incoherente_sin_huella(valor):
    informe = _validar(_p1(metodo={"familia": "remuestreo_iid_media", "parametros": {"replicas": 9, "semilla": valor}},
                           supuestos_declarados=["independencia_de_d_t"]))
    assert informe.estado == "incoherente"
    assert informe.huella is None
    assert informe.violaciones == ("metodo.parametros.semilla: entero con mas de 640 digitos decimales: "
                                   "fuera del limite de AE-57 para calcular la huella",)


_SUBPROCESO = """
import json, sys
from app.application.ml import diseno_regla_prospectiva as dr
salida = {}
for nombre, valor in (("640", 10 ** 640 - 1), ("641", 10 ** 640), ("1000", 10 ** 999)):
    informe = dr.validar_especificacion_diseno({"efecto_minimo": {"valor": valor, "unidad": "sigma"}})
    salida[nombre] = [informe.estado, informe.huella]
print(json.dumps(salida))
"""


def _en_subproceso(*opciones):
    resultado = subprocess.run([sys.executable, *opciones, "-c", _SUBPROCESO], cwd=RAIZ_BACKEND,
                               capture_output=True, text=True, timeout=120, check=False)
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


def test_resultado_independiente_de_int_max_str_digits():
    por_defecto = _en_subproceso()
    assert por_defecto["640"][0] == "incompleta" and por_defecto["640"][1] is not None
    for nombre in ("641", "1000"):
        assert por_defecto[nombre] == ["incoherente", None]
    assert _en_subproceso("-X", "int_max_str_digits=640") == por_defecto
    assert _en_subproceso("-X", "int_max_str_digits=0") == por_defecto


def test_textos_sin_umbral_de_4300_ni_no_serializable():
    texto = ARCHIVO.read_text(encoding="utf-8")
    assert "4300" not in texto
    assert "no serializable" not in texto


# ---------------------------------------------------------------------------
# D7: coincidencia PARCIAL con la propuesta de AE-53
# ---------------------------------------------------------------------------

class TestD7CoincidenciaParcial:
    def test_cien_objetivos_y_un_analisis_coinciden_solo_en_esos_dos_componentes(self):
        informe = _validar(_p1())
        assert informe.coincide_con_propuesta_ae53 == ("ventana",)
        assert informe.estado == "coherente_no_aprobada"
        propuesta = ESPECIFICACION_CANDIDATA_AE53["propuestas"]["horizonte"]
        assert propuesta["estado"] == "propuesta_no_aprobada"
        assert set(propuesta["valor_propuesto"]) == {"objetivos", "desde", "analisis"}

    @pytest.mark.parametrize("extra", [{"desde": "primer_objetivo_posterior_al_corte"},
                                       {"momento_analisis": "unico_al_completar_el_horizonte"}])
    def test_la_candidata_no_puede_declarar_inicio_ni_momento_del_analisis(self, extra):
        informe = _validar(_p1(ventana={"objetivos": 100, "analisis": 1, **extra}))
        assert informe.estado == "incoherente"
        assert any("ventana: campos desconocidos" in v for v in informe.violaciones)

    def test_docstring_declara_coincidencia_parcial(self):
        assert "parcial" in dr.InformeDiseno.__doc__
        assert "desde" in dr.InformeDiseno.__doc__


# ---------------------------------------------------------------------------
# Invariantes
# ---------------------------------------------------------------------------

def test_huella_del_catalogo_no_cambia():
    assert dr.huella_diseno() == HUELLA_DISENO_BASE


@pytest.mark.parametrize("nombre", sorted(REFERENCIAS))
def test_huellas_de_referencia_no_cambian(nombre):
    candidata, huella = REFERENCIAS[nombre]
    informe = _validar(candidata)
    assert informe.estado == "coherente_no_aprobada"
    assert informe.huella == huella


def test_sin_estado_aprobado_y_bloqueos_intactos():
    assert dr.ESTADOS == ("coherente_no_aprobada", "incoherente", "incompleta")
    assert dr.BLOQUEOS_DE_LA_BASE_DOCUMENTADA[3:] == PENDIENTES_BORRADOR_AE52
    assert len(PENDIENTES_BORRADOR_AE52) == 7
    assert REGLAS_EVALUACION_AE52["minimo_sorteos_resueltos_por_juego"] == 100
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"
