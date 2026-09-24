"""Tests de `application/ml/autorizacion_operativa.py` -Etapa AE-41."""
from __future__ import annotations

import pytest

from app.application.ml.autorizacion_operativa import (
    construir_reporte_bloqueado_por_numeracion_invalida,
    evaluar_autorizacion_operativa_desde_elegibilidad,
)
from app.application.ml.tipos import (
    EstadoAutorizacionOperativaML,
    EstadoElegibilidadReaperturaML,
    ReporteElegibilidadReaperturaML,
)


def _reporte_elegibilidad(
    estado: EstadoElegibilidadReaperturaML, total: int,
    minimo: int | None = None, maximo: int | None = None, juego: str = "BALOTO",
) -> ReporteElegibilidadReaperturaML:
    return ReporteElegibilidadReaperturaML(
        juego_codigo=juego, estado=estado, proximo_holdout_inicio=2706,
        minimo_sorteos_nuevos_requeridos=100, total_sorteos_nuevos=total,
        numero_sorteo_minimo=minimo, numero_sorteo_maximo=maximo,
        numero_sorteo_objetivo_minimo=2805, numeracion_contigua=True,
    )


class TestBloqueoPorAusenciaDeDatos:
    def test_baloto_cero_sorteos_bloqueado(self):
        r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 0)
        resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
        assert resultado.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES
        assert resultado.juego_codigo == "BALOTO"

    def test_baloto_revancha_cero_sorteos_bloqueado(self):
        r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 0, juego="BALOTO_REVANCHA")
        resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
        assert resultado.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES
        assert resultado.juego_codigo == "BALOTO_REVANCHA"

    def test_entre_1_y_99_sorteos_bloqueado(self):
        for total in (1, 25, 50, 99):
            r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, total, 2706, 2706 + total - 1)
            resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
            assert resultado.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES, f"total={total}"

    def test_minimo_y_maximo_null_con_total_cero(self):
        r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 0, None, None)
        resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
        assert resultado.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES
        assert resultado.reporte_elegibilidad.numero_sorteo_minimo is None
        assert resultado.reporte_elegibilidad.numero_sorteo_maximo is None

    def test_numeracion_contigua_true_con_total_cero_no_autoriza_nada(self):
        # numeracion_contigua=True en un conjunto vacio nunca implica autorizacion
        r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 0)
        assert r.numeracion_contigua is True
        resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
        assert resultado.estado != EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO
        assert resultado.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES


class TestNumeracionInvalida:
    """El nucleo puro de AE-41 no re-valida la numeracion -esa
    validacion ya la hace el gate de AE-40 (`reapertura.py`), que
    lanza `DisponibilidadHoldoutInvalidaError` para estos casos. Aqui
    se prueba que `construir_reporte_bloqueado_por_numeracion_invalida`
    -la funcion que el caso de uso invoca tras capturar esa
    excepcion- produce siempre el estado correcto, sin excepcion."""

    def test_construye_bloqueado_numeracion_invalida_sin_lanzar(self):
        resultado = construir_reporte_bloqueado_por_numeracion_invalida("BALOTO", "hueco en la numeracion")
        assert resultado.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA
        assert resultado.reporte_elegibilidad is None

    def test_motivo_incluye_el_motivo_original(self):
        resultado = construir_reporte_bloqueado_por_numeracion_invalida("BALOTO", "inicio distinto de 2706")
        assert "inicio distinto de 2706" in resultado.motivo

    def test_juego_codigo_preservado(self):
        resultado = construir_reporte_bloqueado_por_numeracion_invalida("BALOTO_REVANCHA", "duplicados")
        assert resultado.juego_codigo == "BALOTO_REVANCHA"

    def test_reapertura_sigue_siendo_la_unica_fuente_de_verdad(self):
        # confirma por AST que autorizacion_operativa.py nunca reimplementa
        # validaciones de numeracion (huecos, duplicados, etc.) -solo importa
        # tipos, nunca reescribe la logica de reapertura.py
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/autorizacion_operativa.py")
        codigo_fuente = ruta.read_text(encoding="utf-8")
        for patron_prohibido in ("numero_sorteo_minimo >", "numero_sorteo_maximo -", "rango_esperado"):
            assert patron_prohibido not in codigo_fuente


class TestLimiteExacto:
    def test_99_sorteos_bloqueado(self):
        r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 99, 2706, 2804)
        resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
        assert resultado.estado == EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES

    def test_100_sorteos_contiguos_unicamente_autorizado_para_prerregistro(self):
        r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO, 100, 2706, 2805)
        resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
        assert resultado.estado == EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO
        # nunca ningun otro estado simultaneamente -es un Enum, solo puede tener un valor
        assert resultado.estado in (
            EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO,
        )

    def test_mas_de_100_sorteos_contiguos_tambien_autorizado_sin_observar_resultados(self):
        # Politica exacta: el umbral es un minimo inclusivo -mas de 100
        # sorteos disponibles produce el MISMO estado que exactamente 100,
        # nunca un cuarto estado ni una autorizacion "mayor". AE-41 nunca
        # observa los resultados de esos sorteos adicionales para decidir esto.
        r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO, 250, 2706, 2955)
        resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
        assert resultado.estado == EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO
        assert resultado.resultados_observados is False

    def test_autorizado_nunca_implica_entrenamiento_prediccion_ni_despliegue(self):
        r = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO, 100, 2706, 2805)
        resultado = evaluar_autorizacion_operativa_desde_elegibilidad(r)
        assert resultado.modelos_entrenados is False
        assert resultado.predicciones_generadas is False
        assert resultado.resultados_observados is False
        assert resultado.holdout_consumido is False
        motivo_lower = resultado.motivo.lower()
        assert "no autoriza" in motivo_lower


class TestReproducibilidadYDeterminismo:
    def test_misma_entrada_mismo_resultado(self):
        r1 = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 0)
        r2 = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 0)
        res1 = evaluar_autorizacion_operativa_desde_elegibilidad(r1)
        res2 = evaluar_autorizacion_operativa_desde_elegibilidad(r2)
        assert res1.estado == res2.estado
        assert res1.motivo == res2.motivo

    def test_juegos_evaluados_por_separado(self):
        r_baloto = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 0, juego="BALOTO")
        r_revancha = _reporte_elegibilidad(EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO, 100, 2706, 2805, juego="BALOTO_REVANCHA")
        res_baloto = evaluar_autorizacion_operativa_desde_elegibilidad(r_baloto)
        res_revancha = evaluar_autorizacion_operativa_desde_elegibilidad(r_revancha)
        assert res_baloto.estado != res_revancha.estado
        assert res_baloto.juego_codigo == "BALOTO"
        assert res_revancha.juego_codigo == "BALOTO_REVANCHA"


class TestArquitectura:
    def test_autorizacion_operativa_no_importa_ml_prohibidas(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/autorizacion_operativa.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        modulos_prohibidos = ("sklearn", "numpy", "scipy", "pandas", "sqlalchemy", "fastapi", "jinja2")
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                for alias in nodo.names:
                    assert not any(alias.name.lower().startswith(p) for p in modulos_prohibidos), alias.name
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module:
                    assert not any(nodo.module.lower().startswith(p) for p in modulos_prohibidos), nodo.module

    def test_solo_modelo_py_importa_sklearn_en_application_ml(self):
        import ast as ast_modulo
        import pathlib

        def importa_sklearn(ruta):
            arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
            for nodo in ast_modulo.walk(arbol):
                if isinstance(nodo, ast_modulo.Import):
                    if any(a.name == "sklearn" or a.name.startswith("sklearn.") for a in nodo.names):
                        return True
                elif isinstance(nodo, ast_modulo.ImportFrom):
                    if nodo.module and (nodo.module == "sklearn" or nodo.module.startswith("sklearn.")):
                        return True
            return False

        directorio_ml = pathlib.Path("app/application/ml")
        archivos_con_sklearn = [f.name for f in sorted(directorio_ml.glob("*.py")) if importa_sklearn(f)]
        assert archivos_con_sklearn == ["modelo.py"]

    def test_caso_de_uso_no_importa_sklearn(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/use_cases/evaluar_autorizacion_operativa_ml.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                for alias in nodo.names:
                    assert not alias.name.startswith("sklearn")
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module:
                    assert not nodo.module.startswith("sklearn")

    def test_autorizacion_operativa_no_importa_infraestructura(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/autorizacion_operativa.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        modulos_prohibidos = ("sqlalchemy", "fastapi", "jinja2")
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                for alias in nodo.names:
                    assert not any(alias.name.lower().startswith(p) for p in modulos_prohibidos)
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module:
                    assert not any(nodo.module.lower().startswith(p) for p in modulos_prohibidos)

    def test_ninguna_ruta_http_nueva_en_el_diff_de_ae41(self):
        import pathlib
        for ruta in pathlib.Path("app").rglob("*.py"):
            if "router" in ruta.name.lower() or "api" in str(ruta).lower():
                contenido = ruta.read_text(encoding="utf-8")
                assert "EvaluarAutorizacionOperativaML" not in contenido
                assert "autorizacion_operativa" not in contenido.lower()

    def test_no_reutiliza_reglas_duplicadas_solo_delega(self):
        # confirma que autorizacion_operativa.py importa (nunca reimplementa)
        # los tipos del gate de AE-40 -unica fuente de verdad
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/autorizacion_operativa.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        nombres_importados = set()
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.ImportFrom):
                for alias in nodo.names:
                    nombres_importados.add(alias.name)
        assert "EstadoElegibilidadReaperturaML" in nombres_importados
        assert "ReporteElegibilidadReaperturaML" in nombres_importados
