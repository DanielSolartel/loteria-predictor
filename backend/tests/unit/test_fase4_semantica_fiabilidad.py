"""Fiabilidad v3.4: reglas serializadas, compatibilidad y lectura numérica.

Solo datos sintéticos. Los valores de compatibilidad se observaron en v3.3
antes de corregir la clasificación; cambiar una etiqueta no debe volver a
remuestrear la receta ni modificar informes o probabilidades congeladas.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import math

import pytest

from app.application.ml import carteras_ensemble as ce
from app.application.ml import laboratorio_variables as lv
from app.application.ml import predicciones_fiabilidad as pf
from app.application.ml import resultados_procedencias as rp
from tests.unit import fixtures_producto1 as fx


def _informe(juego):
    filas = [{"objetivo": 100 + i,
              "diferencia_log_loss": .004 * math.sin(i * .8) + .001 * (i % 5) - .002,
              "brier": .1 + .002 * math.cos(i * .7) + .0003 * (i % 4)} for i in range(47)]
    return json.loads(json.dumps({
        "clave": "a" * 64, "datos": {"corte": 99},
        "identidad": {"reglas": lv.REGLAS[juego].como_dict()},
        "muestra_comun": {"excluidos": []},
        "candidatos": [{"id": "modelo", "familia": "bosques", "estado": "completo", "por_objetivo": filas},
                       {"id": "uniforme", "familia": "uniforme", "estado": "completo",
                        "por_objetivo": [{"objetivo": 100 + i, "brier": .1} for i in range(47)]}]}))


# Semillas e intervalos registrados con el mismo fixture en v3.3. Las medias
# comunes son -5.912522863181439e-05 y 0.0005179277165672563 respectivamente.
HISTORICOS = {
    "BALOTO": ((852351445347918402, [-.000985916947201848, .001104235128548492]),
               (874505184791730782, [-.00015972369544911183, .0009800018323247019])),
    "BALOTO_REVANCHA": ((1134361348367417113, [-.0009861609636704343, .001090827239639339]),
                        (498771042064864952, [-.00015889141018511575, .0009682984707499483])),
    "MILOTO": ((1138470247357372509, [-.000985336002804127, .0011387517561177438]),
               (388023444597641172, [-.00014182024740309654, .0010368398812276097])),
    "COLORLOTO": ((1149427316843617309, [-.0009779648156094205, .0010993672635884724]),
                  (1065523286960871581, [-.00015135943690822336, .0010273516399622563])),
}


@pytest.mark.parametrize("juego", lv.JUEGOS)
def test_reglas_reales_corrigen_componente_sin_cambiar_semillas_datos_ni_intervalos(juego):
    informe = _informe(juego)
    antes = copy.deepcopy(informe)
    assert "colores" not in informe["identidad"]["reglas"]
    resultado = pf.evaluar_informe(informe, "modelo", (juego, informe["clave"], "modelo"))
    principal = "pares" if juego == "COLORLOTO" else "numeros"
    assert set(resultado["componentes"]) == {principal}
    componente = resultado["componentes"][principal]
    assert resultado["clasificacion_componentes"]["version"] == "fase4-componentes-receta-2"
    assert componente["identidad_remuestreo"]["version_metodo"] == "fase4-fiabilidad-1"
    assert componente["identidad_remuestreo"]["componente_semilla"] == "numeros"
    for metrica, media, historico in zip(
        ("diferencia_log_loss", "diferencia_brier"),
        (-5.912522863181439e-05, .0005179277165672563), HISTORICOS[juego], strict=True,
    ):
        dato = componente["metricas"][metrica]
        assert dato["n"] == 47 and dato["semilla"] == historico[0]
        # Tolerancia para diferencias de libm entre plataformas, muy inferior
        # a la precisión visible; las semillas se verifican exactamente.
        assert dato["media"] == pytest.approx(media, abs=1e-15, rel=0)
        assert dato["intervalo"] == pytest.approx(historico[1], abs=1e-15, rel=0)
    assert informe == antes
    acotado = pf.evaluar_informe(informe, "modelo", (juego, informe["clave"], "modelo"), hasta=146)
    assert acotado["componentes"] == resultado["componentes"]


@pytest.mark.parametrize("valor,texto", (
    (None, "—"), (0.0, "0.00000"), (-0.0, "0.00000"),
    (3.8857805861880479e-16, "3.8858e-16"),
    (-1.3877787807814457e-17, "-1.3878e-17"),
    (1e-12, "1.0000e-12"), (-1e-12, "-1.0000e-12"),
    (1e-10, "1.0000e-10"), (-.000001234567, "-1.2346e-06"),
    (.00004, "4.0000e-05"), (-.00004, "-4.0000e-05"),
    (.00005, "0.00005"), (-.00005, "-0.00005"), (.125, "0.12500"), (-2.5, "-2.50000"),
))
def test_cifras_no_nulas_conservan_magnitud_visible_tambien_en_los_limites(valor, texto):
    assert pf.formatear_cifra(valor) == texto


@pytest.mark.parametrize("metrica", pf.METRICAS)
@pytest.mark.parametrize("valor", (3.8857805861880479e-16, -3.8857805861880479e-16))
@pytest.mark.parametrize("intervalo,lectura", (
    (None, "Muestra insuficiente"), ([-1e-13, 1e-13], "El intervalo numérico incluye 0"),
    ([1e-17, 1e-13], "El intervalo numérico no incluye 0: está por encima"),
    ([-1e-13, -1e-17], "El intervalo numérico no incluye 0: está por debajo"),
))
def test_residuos_se_describen_sin_borrar_el_signo_ni_inferir_igualdad(metrica, valor, intervalo, lectura):
    texto = pf._lectura(metrica, valor, intervalo)
    assert "próxima a 0" in texto and "criterio de presentación, no igualdad matemática" in texto
    assert ("original positiva" if valor > 0 else "original negativa") in texto and lectura in texto
    assert "mayor pérdida" not in texto and "menor pérdida" not in texto
    assert "más aciertos" not in texto and "menos aciertos" not in texto
    if intervalo is not None:
        assert "ni relevancia estadística por sí solo" in texto


@pytest.mark.parametrize("metrica", pf.METRICAS)
@pytest.mark.parametrize("valor", (0.000001, -0.000001, .2, -.2))
def test_diferencias_pequenas_reales_y_materiales_conservan_su_sentido(metrica, valor):
    texto = pf._lectura(metrica, valor, None)
    sentido = ("mayor pérdida" if valor > 0 else "menor pérdida") if metrica.startswith("diferencia") else (
        "más aciertos" if valor > 0 else "menos aciertos")
    assert sentido in texto and "próxima a 0" not in texto and "Muestra insuficiente" in texto
    assert pf.formatear_cifra(valor) != "0.00000"
    con_intervalo = pf._lectura(metrica, valor, [-.3, .3])
    assert sentido in con_intervalo and "El intervalo numérico incluye 0" in con_intervalo


@pytest.mark.parametrize("metrica", pf.METRICAS)
@pytest.mark.parametrize("intervalo", (None, [0.0, 0.0], [-.2, .2]))
def test_cero_numerico_no_afirma_igualdad_de_todos_los_sorteos_ni_fuera_de_la_muestra(metrica, intervalo):
    texto = pf._lectura(metrica, 0.0, intervalo)
    assert "Media numérica 0 en esta muestra" in texto
    assert "ningún sorteo" not in texto and "sin diferencia" not in texto.lower()
    if intervalo is not None:
        assert "El intervalo numérico incluye 0" in texto


@pytest.mark.parametrize("metrica", pf.METRICAS)
@pytest.mark.parametrize("residuo", (3.8857805861880479e-16, -1.3877787807814457e-17))
def test_lectura_y_formato_no_reescriben_medias_originales_ni_intervalos(metrica, residuo):
    valores = [residuo] * 32
    antes = valores.copy()
    dato = pf.estimar(valores, ("sintetico",), metrica)
    assert dato["media"] == residuo and dato["intervalo"] == [residuo, residuo]
    assert dato["estado"] == "estimable" and "próxima a 0" in dato["lectura"]
    assert "e-" in pf.formatear_cifra(dato["media"])
    assert valores == antes


@pytest.mark.parametrize("juego", ("BALOTO", "BALOTO_REVANCHA"))
def test_uniforme_principal_mantiene_superbalota_con_laplace_y_deltas_propios(juego):
    # Historial sintético deliberadamente asimétrico: no se deduce una
    # superbalota uniforme a partir del nombre del modelo de los números.
    historico = [dataclasses.replace(r, superbalota=1) for r in fx.historico_numerico(juego, 70)]
    instantanea = lv.validar_instantanea(juego, historico)
    fuente = ce.fuente(instantanea, "uniforme", "reducido")
    antes = copy.deepcopy(fuente)
    sb = fuente["superbalota"]
    assert sb["estrategia"] == "frecuencia_con_suavizado_de_laplace"
    assert sb["probabilidades"][0] == pytest.approx(71 / 86, abs=1e-12)
    assert sb["probabilidades"][1:] == pytest.approx([1 / 86] * 15, abs=1e-12)
    congelado = rp.congelado_de_fuente(juego, fuente)
    resultado = {"numeros": [1, 2, 3, 4, 5], "superbalota": 1}
    metricas, superbalota = rp.metricas_de_congelado(juego, 2151, congelado, resultado)
    fila = {"tipo": "seguimiento", "estado": "incluido", "objetivo": 2151, "congelado": congelado,
            "resultado": resultado, "metricas": metricas, "superbalota": superbalota}
    componentes = pf.evaluar_emisiones([fila], "seguimiento", (juego, "carteras:uniforme-v1"))["componentes"]
    assert set(componentes) == {"numeros", "superbalota"}
    principal = componentes["numeros"]["metricas"]["diferencia_log_loss"]
    separado = componentes["superbalota"]["metricas"]["diferencia_log_loss"]
    assert abs(principal["media"]) < 1e-12
    assert separado["media"] < -1 and "menor pérdida" in separado["lectura"]
    assert fuente == antes
