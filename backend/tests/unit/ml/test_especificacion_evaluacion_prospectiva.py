"""Tests de `app/application/ml/especificacion_evaluacion_prospectiva.py`
-Etapa AE-53, validada: contrato preparatorio de una futura
evaluacion prospectiva (especificacion candidata con decisiones
pendientes, validacion de la secuencia de objetivos y metricas por
sorteo). Todo sintetico: numeros y probabilidades construidos a mano,
nunca PostgreSQL, datos reales ni predicciones reales."""
from __future__ import annotations

import ast
import copy
import json
import math
from pathlib import Path

import pytest

from app.application.ml import especificacion_evaluacion_prospectiva as ep
from app.application.ml.baselines import baseline_uniforme
from app.application.ml.metricas import evaluar
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52
from app.application.ml.tipos import FilaCandidato

ARCHIVO = Path(ep.__file__)
RAIZ_BACKEND = ARCHIVO.resolve().parents[3]
CORTE = 2713
"""Corte sintetico: solo fija la forma de la ventana, no es un corte real."""


# ---------------------------------------------------------------------------
# Especificacion candidata
# ---------------------------------------------------------------------------

class TestEspecificacion:
    def test_estado_candidata_no_aprobada_y_grupos_separados(self):
        especificacion = ep.ESPECIFICACION_CANDIDATA_AE53
        assert especificacion["estado"] == "candidata_no_aprobada"
        assert set(especificacion) == {"esquema", "etapa", "estado", "fijado_por_ae52", "propuestas", "pendientes", "nota"}

    def test_fijado_por_ae52_es_la_constante_vigente(self):
        assert ep.ESPECIFICACION_CANDIDATA_AE53["fijado_por_ae52"] == REGLAS_EVALUACION_AE52
        assert ep.ESPECIFICACION_CANDIDATA_AE53["fijado_por_ae52"] is not REGLAS_EVALUACION_AE52

    def test_propuestas_no_aprobadas(self):
        propuestas = ep.ESPECIFICACION_CANDIDATA_AE53["propuestas"]
        assert set(propuestas) == {"horizonte", "omisiones", "referencia_secundaria"}
        for nombre, propuesta in propuestas.items():
            assert set(propuesta) == {"valor_propuesto", "estado"}, nombre
            assert propuesta["estado"] == "propuesta_no_aprobada", nombre
        assert propuestas["horizonte"]["valor_propuesto"]["objetivos"] == 100
        assert propuestas["horizonte"]["valor_propuesto"]["objetivos"] == REGLAS_EVALUACION_AE52[
            "minimo_sorteos_resueltos_por_juego"]
        assert propuestas["omisiones"]["valor_propuesto"] == "cualquier_omision_en_el_horizonte_no_evaluable"

    def test_pendientes_sin_valor(self):
        pendientes = ep.ESPECIFICACION_CANDIDATA_AE53["pendientes"]
        assert set(pendientes) == {
            "unidad_y_metodo_inferencial", "tratamiento_dependencia_serial", "nivel_y_umbral", "efecto_minimo",
            "multiplicidad_entre_juegos", "mecanismo_de_sellado_temporal_externo",
        }
        for nombre, pendiente in pendientes.items():
            assert pendiente == {"valor": None, "estado": "pendiente"}, nombre

    def test_ningun_estado_aprobado_ni_claves_de_inferencia(self):
        texto = json.dumps(ep.ESPECIFICACION_CANDIDATA_AE53, ensure_ascii=False)
        assert '"aprobada"' not in texto and '"aprobado"' not in texto
        for prohibido in ("bootstrap", "intervalo", "p_valor", "cumplido", "signos", "veredicto", "GO"):
            assert prohibido not in json.dumps(ep.ESPECIFICACION_CANDIDATA_AE53["propuestas"]), prohibido

    def test_huella_canonica_estable_y_sensible(self):
        huella = ep.huella_especificacion()
        assert len(huella) == 64 and all(c in "0123456789abcdef" for c in huella)
        assert huella == ep.huella_especificacion(copy.deepcopy(ep.ESPECIFICACION_CANDIDATA_AE53))
        assert ep.serializar_especificacion().endswith(b"\n") and b"\r" not in ep.serializar_especificacion()
        alterada = copy.deepcopy(ep.ESPECIFICACION_CANDIDATA_AE53)
        alterada["propuestas"]["horizonte"]["valor_propuesto"]["objetivos"] = 99
        assert ep.huella_especificacion(alterada) != huella
        alterada = copy.deepcopy(ep.ESPECIFICACION_CANDIDATA_AE53)
        alterada["pendientes"]["efecto_minimo"]["valor"] = 0.0
        assert ep.huella_especificacion(alterada) != huella

    def test_nota_precisa_que_la_huella_no_es_un_sello_temporal(self):
        for fragmento in ("no prueba cuando se fijo", "no aprueba", "NO-GO de AE-39"):
            assert fragmento in ep.ESPECIFICACION_CANDIDATA_AE53["nota"], fragmento

    def test_no_cierra_los_pendientes_de_ae52(self):
        assert len(PENDIENTES_BORRADOR_AE52) == 7
        assert "regla_estadistica_de_decision" in PENDIENTES_BORRADOR_AE52
        assert "mecanismo_de_sellado_temporal_externo" in PENDIENTES_BORRADOR_AE52


# ---------------------------------------------------------------------------
# Secuencia de objetivos: resueltos, pendientes, futuros y omisiones
# ---------------------------------------------------------------------------

def _validar(ultimo, prediccion, resultado, corte=CORTE):
    return ep.validar_secuencia_objetivos(
        corte=corte, ultimo_sorteo_ocurrido=ultimo,
        objetivos_con_prediccion=prediccion, objetivos_con_resultado=resultado,
    )


class TestSecuencia:
    def test_ventana_exacta_y_reglas_propuestas(self):
        informe = _validar(CORTE, [], [])
        assert (informe.ventana_desde, informe.ventana_hasta, informe.horizonte) == (2714, 2813, 100)
        assert informe.reglas_aplicadas == {"horizonte": "propuesta_no_aprobada", "omisiones": "propuesta_no_aprobada"}

    def test_sin_sorteos_ocurridos_todo_es_futuro_no_omision(self):
        informe = _validar(CORTE, [], [])
        assert informe.estado == "incompleta"
        assert informe.omisiones == () and informe.resueltos == ()
        assert informe.futuros == tuple(range(2714, 2814))

    @pytest.mark.parametrize("resueltos", [0, 50, 99])
    def test_resueltos_sin_huecos_incompleta(self, resueltos):
        objetivos = list(range(2714, 2714 + resueltos))
        informe = _validar(CORTE + resueltos, objetivos, objetivos)
        assert informe.estado == "incompleta"
        assert informe.omisiones == ()
        assert len(informe.resueltos) == resueltos
        assert len(informe.futuros) == 100 - resueltos

    def test_cien_resueltos_completa(self):
        objetivos = list(range(2714, 2814))
        informe = _validar(2813, objetivos, objetivos)
        assert informe.estado == "completa"
        assert informe.resueltos == tuple(objetivos) and informe.futuros == () and informe.omisiones == ()

    def test_prediccion_futura_sin_resultado_es_futuro_no_omision(self):
        informe = _validar(2716, [2714, 2715, 2716, 2717, 2718], [2714, 2715, 2716])
        assert informe.estado == "incompleta"
        assert informe.omisiones == ()
        assert informe.futuros[:2] == (2717, 2718)

    def test_prediccion_de_un_sorteo_ocurrido_sin_resultado_es_resultado_pendiente(self):
        informe = _validar(2716, [2714, 2715, 2716], [2714, 2715])
        assert informe.estado == "incompleta"
        assert informe.resultado_pendiente == (2716,)
        assert informe.omisiones == ()

    def test_sorteo_ocurrido_sin_prediccion_es_omision(self):
        informe = _validar(2716, [2714, 2716], [2714, 2716])
        assert informe.estado == "no_evaluable_por_omision"
        assert informe.omisiones == (2715,)
        assert "2715" in informe.motivo

    def test_omision_con_el_resto_completo_sigue_no_evaluable(self):
        objetivos = [n for n in range(2714, 2814) if n != 2800]
        informe = _validar(2813, objetivos, objetivos)
        assert informe.estado == "no_evaluable_por_omision"
        assert informe.omisiones == (2800,)

    def test_objetivos_fuera_de_horizonte_no_extienden_la_ventana(self):
        objetivos = [n for n in range(2714, 2820) if n != 2750]
        informe = _validar(2819, objetivos, objetivos)
        assert informe.ventana_hasta == 2813
        assert informe.fuera_de_horizonte == tuple(range(2814, 2820))
        assert informe.estado == "no_evaluable_por_omision" and informe.omisiones == (2750,)

    def test_informe_inmutable(self):
        informe = _validar(CORTE, [], [])
        with pytest.raises(Exception):
            informe.estado = "completa"

    @pytest.mark.parametrize("argumentos", [
        dict(ultimo=2716, prediccion=[2713], resultado=[]),              # objetivo <= corte
        dict(ultimo=2716, prediccion=[2714, 2714], resultado=[]),        # duplicado
        dict(ultimo=2716, prediccion=[2714], resultado=[2714, 2714]),    # duplicado
        dict(ultimo=2716, prediccion=[True], resultado=[]),              # bool
        dict(ultimo=2716, prediccion=[2714.0], resultado=[]),            # no entero
        dict(ultimo=2716, prediccion=[2714], resultado=[2715]),          # resultado sin prediccion
        dict(ultimo=2716, prediccion=[2717], resultado=[2717]),          # resultado de un sorteo no ocurrido
        dict(ultimo=2712, prediccion=[], resultado=[]),                  # ultimo ocurrido anterior al corte
        dict(ultimo=True, prediccion=[], resultado=[]),
    ])
    def test_entradas_invalidas_se_rechazan(self, argumentos):
        with pytest.raises(ep.EspecificacionProspectivaError):
            _validar(argumentos["ultimo"], argumentos["prediccion"], argumentos["resultado"])

    def test_corte_no_entero(self):
        with pytest.raises(ep.EspecificacionProspectivaError):
            _validar(2716, [], [], corte="2713")


# ---------------------------------------------------------------------------
# Metricas por sorteo con las definiciones actuales
# ---------------------------------------------------------------------------

NUMEROS = (3, 11, 19, 27, 40)
"""Numeros sinteticos de un sorteo construido a mano."""


def _probabilidades_concentradas(numeros=NUMEROS, alta=0.5, baja=0.05):
    return [alta if n in numeros else baja for n in range(1, 44)]


def _filas(numeros, objetivo=2714):
    return [FilaCandidato(
        codigo_juego="BALOTO", sorteo_objetivo=objetivo, calculado_hasta_sorteo=objetivo - 1, numero_candidato=n,
        etiqueta=1 if n in numeros else 0, frecuencia_acumulada=0.0, frecuencia_ventana_10=0.0,
        frecuencia_ventana_20=0.0, frecuencia_ventana_50=0.0, sorteos_desde_ultima_aparicion=None,
        aparecio_en_sorteo_anterior=0,
    ) for n in range(1, 44)]


class TestMetricasPorSorteo:
    def test_coincide_con_las_definiciones_actuales(self):
        probabilidades = _probabilidades_concentradas()
        resultado = ep.metricas_por_sorteo("BALOTO", 2714, probabilidades, NUMEROS)
        assert resultado.estrategia == evaluar(_filas(NUMEROS), probabilidades)
        assert resultado.uniforme == baseline_uniforme(_filas(NUMEROS), 1, 43, 5).metricas
        assert resultado.estrategia.total_sorteos == resultado.uniforme.total_sorteos == 1
        assert resultado.estrategia.total_filas == 43

    def test_uniforme_analitica_en_log_loss_y_brier(self):
        resultado = ep.metricas_por_sorteo("BALOTO_REVANCHA", 2714, [5 / 43] * 43, NUMEROS)
        p = 5 / 43
        assert resultado.uniforme.log_loss == pytest.approx(-(5 * math.log(p) + 38 * math.log(1 - p)) / 43, abs=1e-12)
        assert resultado.uniforme.brier_score == pytest.approx((5 * (1 - p) ** 2 + 38 * p ** 2) / 43, abs=1e-12)
        assert resultado.diferencias["log_loss"] == pytest.approx(0.0, abs=1e-12)
        assert resultado.diferencias["brier_score"] == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.parametrize("numeros, aciertos", [((1, 2, 3, 4, 5), 5), ((1, 2, 30, 31, 32), 2), ((10, 20, 30, 40, 41), 0)])
    def test_p5_de_la_uniforme_es_la_del_boleto_1_a_5(self, numeros, aciertos):
        resultado = ep.metricas_por_sorteo("BALOTO", 2714, _probabilidades_concentradas(), numeros)
        assert resultado.uniforme.precision_en_5 == aciertos / 5

    def test_p5_y_r5_coinciden_en_cada_sorteo(self):
        for numeros in ((1, 2, 3, 4, 5), NUMEROS, (6, 7, 8, 9, 43)):
            resultado = ep.metricas_por_sorteo("BALOTO", 2714, _probabilidades_concentradas(), numeros)
            assert resultado.estrategia.precision_en_5 == resultado.estrategia.recall_en_5
            assert resultado.uniforme.precision_en_5 == resultado.uniforme.recall_en_5

    def test_discrepancia_forzada_entre_p5_y_r5_se_rechaza(self, monkeypatch):
        from app.application.ml import metricas

        real = metricas.calcular_precision_recall_en_5
        monkeypatch.setattr(metricas, "calcular_precision_recall_en_5",
                            lambda filas, probs: (real(filas, probs)[0], 0.123))
        with pytest.raises(ep.EspecificacionProspectivaError, match="Recall@5"):
            ep.metricas_por_sorteo("BALOTO", 2714, _probabilidades_concentradas(), NUMEROS)

    def test_diferencias_orientadas_uniforme_menos_estrategia(self):
        resultado = ep.metricas_por_sorteo("BALOTO", 2714, _probabilidades_concentradas(), NUMEROS)
        for metrica in ("log_loss", "brier_score", "precision_en_5"):
            assert resultado.diferencias[metrica] == getattr(resultado.uniforme, metrica) - getattr(resultado.estrategia, metrica)
        assert resultado.diferencias["log_loss"] > 0
        assert set(resultado.diferencias) == {"log_loss", "brier_score", "precision_en_5"}

    @pytest.mark.parametrize("probabilidades", [
        [0.1] * 42, [0.1] * 44, [float("nan")] + [0.1] * 42, [0.0] + [0.1] * 42, [1.0] + [0.1] * 42,
        [True] + [0.1] * 42, [1] * 43, "0.1",
    ])
    def test_probabilidades_invalidas(self, probabilidades):
        with pytest.raises(ep.EspecificacionProspectivaError):
            ep.metricas_por_sorteo("BALOTO", 2714, probabilidades, NUMEROS)

    @pytest.mark.parametrize("numeros", [(1, 1, 2, 3, 4), (0, 1, 2, 3, 4), (1, 2, 3, 4, 44), (1, 2, 3, 4), (1, 2, 3, 4, 5, 6),
                                         (1, 2, 3, 4, True)])
    def test_numeros_invalidos(self, numeros):
        with pytest.raises(ep.EspecificacionProspectivaError):
            ep.metricas_por_sorteo("BALOTO", 2714, _probabilidades_concentradas(), numeros)

    @pytest.mark.parametrize("juego", ["MILOTO", "COLORLOTO", "baloto"])
    def test_juego_no_autorizado(self, juego):
        with pytest.raises(ep.EspecificacionProspectivaError):
            ep.metricas_por_sorteo(juego, 2714, _probabilidades_concentradas(), NUMEROS)

    def test_resultado_de_un_solo_sorteo_sin_agregados(self):
        resultado = ep.metricas_por_sorteo("BALOTO", 2714, _probabilidades_concentradas(), NUMEROS)
        assert resultado.codigo_juego == "BALOTO" and resultado.sorteo_objetivo == 2714
        publicos = {n for n in dir(ep) if not n.startswith("_")}
        for prohibido in ("agregar", "promedio", "bootstrap", "intervalo", "signos", "decidir", "evaluar_regla"):
            assert not any(prohibido in n.lower() for n in publicos), prohibido


# ---------------------------------------------------------------------------
# Estructura: puro, sin inferencia ni conexion con el registro o la base
# ---------------------------------------------------------------------------

def _importaciones():
    salida = []
    for nodo in ast.walk(ast.parse(ARCHIVO.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            salida.extend((alias.name, None) for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            salida.extend((nodo.module or "", alias.name) for alias in nodo.names)
    return salida


def test_modulo_puro_sin_inferencia_ni_conexiones():
    for modulo, nombre in _importaciones():
        raiz = modulo.split(".")[0]
        assert raiz not in {"sklearn", "numpy", "scipy", "pandas", "sqlalchemy", "fastapi", "random", "time",
                            "datetime", "os", "pathlib", "statistics"}, modulo
        for prohibido in ("incertidumbre", "inferencia", "prediccion_bloqueada", "resolver_estado_prediccion",
                          "diagnostico_bloqueo", "modelo", "infrastructure", "scripts"):
            assert prohibido not in modulo, modulo
        if modulo.endswith("registro_prospectivo"):
            assert nombre == "REGLAS_EVALUACION_AE52", nombre
        assert not (nombre or "").startswith("_"), (modulo, nombre)


def test_sin_bootstrap_signos_intervalos_ni_veredictos():
    texto = ARCHIVO.read_text(encoding="utf-8")
    arbol = ast.parse(texto)
    nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)} | {
        n.name for n in ast.walk(arbol) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    for prohibido in ("bootstrap", "percentil", "signos", "intervalo", "comb", "cumplido", "DecisionContinuidadML"):
        assert not any(prohibido.lower() in n.lower() for n in nombres), prohibido


def test_nada_fuera_de_ml_lo_usa():
    raiz = RAIZ_BACKEND / "app"
    rutas = [*(raiz / "api").rglob("*.py"), raiz / "main.py", *(raiz / "templates").rglob("*.html"),
             *(RAIZ_BACKEND / "scripts").rglob("*.py"), *(raiz / "application" / "use_cases").rglob("*.py")]
    for ruta in rutas:
        assert "especificacion_evaluacion_prospectiva" not in ruta.read_text(encoding="utf-8"), ruta
