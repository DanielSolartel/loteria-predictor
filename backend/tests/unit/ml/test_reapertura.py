"""Tests de `application/ml/reapertura.py` -Etapa AE-40."""
from __future__ import annotations

import pytest

from app.application.ml.reapertura import (
    JUEGOS_AUTORIZADOS_AE40,
    NUMERO_SORTEO_OBJETIVO_MINIMO,
    DisponibilidadHoldoutInvalidaError,
    evaluar_elegibilidad_reapertura_ml,
)
from app.application.ml.incertidumbre import MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT, PROXIMO_HOLDOUT_INICIO
from app.application.ml.tipos import EstadoElegibilidadReaperturaML, ResumenDisponibilidadHoldout


def _resumen(
    total: int, minimo: int | None = None, maximo: int | None = None,
    desde: int = 2706, juego: str = "BALOTO",
) -> ResumenDisponibilidadHoldout:
    return ResumenDisponibilidadHoldout(
        juego_codigo=juego, desde_numero_sorteo=desde, total_registros=total,
        total_numeros_distintos=total, numero_sorteo_minimo=minimo, numero_sorteo_maximo=maximo,
    )


class TestConstantesPreregistradas:
    def test_proximo_holdout_inicio_2706(self):
        assert PROXIMO_HOLDOUT_INICIO == 2706

    def test_minimo_sorteos_nuevos_100(self):
        assert MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT == 100

    def test_numero_sorteo_objetivo_minimo_derivado_no_hardcodeado(self):
        assert NUMERO_SORTEO_OBJETIVO_MINIMO == PROXIMO_HOLDOUT_INICIO + MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT - 1
        assert NUMERO_SORTEO_OBJETIVO_MINIMO == 2805

    def test_dos_juegos_autorizados(self):
        assert JUEGOS_AUTORIZADOS_AE40 == frozenset({"BALOTO", "BALOTO_REVANCHA"})


class TestNucleoPuroCasosBasicos:
    def test_cero_sorteos_no_elegible(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(0))
        assert r.estado == EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES
        assert r.total_sorteos_nuevos == 0

    def test_un_sorteo_no_elegible(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(1, 2706, 2706))
        assert r.estado == EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES

    def test_noventa_y_nueve_sorteos_no_elegible(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(99, 2706, 2804))
        assert r.estado == EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES
        assert r.total_sorteos_nuevos == 99

    def test_exactamente_2706_2805_elegible(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(100, 2706, 2805))
        assert r.estado == EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO
        assert r.numero_sorteo_minimo == 2706
        assert r.numero_sorteo_maximo == 2805
        assert r.numero_sorteo_objetivo_minimo == 2805

    def test_ciento_uno_sorteos_contiguos_elegible(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(101, 2706, 2806))
        assert r.estado == EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO

    def test_misma_entrada_mismo_reporte(self):
        r1 = evaluar_elegibilidad_reapertura_ml(_resumen(150, 2706, 2855))
        r2 = evaluar_elegibilidad_reapertura_ml(_resumen(150, 2706, 2855))
        assert r1 == r2

    def test_juegos_evaluados_por_separado(self):
        r_baloto = evaluar_elegibilidad_reapertura_ml(_resumen(150, 2706, 2855, juego="BALOTO"))
        r_revancha = evaluar_elegibilidad_reapertura_ml(_resumen(50, 2706, 2755, juego="BALOTO_REVANCHA"))
        assert r_baloto.juego_codigo == "BALOTO"
        assert r_revancha.juego_codigo == "BALOTO_REVANCHA"
        assert r_baloto.estado != r_revancha.estado

    def test_reporte_inmutable(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(100, 2706, 2805))
        with pytest.raises(Exception):
            r.total_sorteos_nuevos = 999

    def test_constantes_reutilizadas_de_politica_reapertura(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(100, 2706, 2805))
        assert r.proximo_holdout_inicio == PROXIMO_HOLDOUT_INICIO
        assert r.minimo_sorteos_nuevos_requeridos == MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT

    def test_ningun_entrenamiento_ningun_resultado_observado_holdout_no_consumido(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(100, 2706, 2805))
        assert r.resultados_observados is False
        assert r.modelos_entrenados is False
        assert r.holdout_consumido is False

    def test_numeracion_contigua_confirmada_en_caso_valido(self):
        r = evaluar_elegibilidad_reapertura_ml(_resumen(100, 2706, 2805))
        assert r.numeracion_contigua is True


class TestValidacionesDeCoherenciaInterna:
    """El nucleo puro valida exclusivamente la coherencia INTERNA de
    un unico `ResumenDisponibilidadHoldout` -nunca compara contra un
    codigo de juego externo solicitado (eso es responsabilidad del
    caso de uso, ver `test_evaluar_elegibilidad_reapertura_ml.py`)."""

    def test_conteo_negativo_rechazado(self):
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(_resumen(-1))

    def test_total_distintos_negativo_rechazado(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=5, total_numeros_distintos=-5, numero_sorteo_minimo=2706, numero_sorteo_maximo=2710)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)

    def test_duplicados_total_distinto_de_distintos(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=101, total_numeros_distintos=100, numero_sorteo_minimo=2706, numero_sorteo_maximo=2805)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)

    def test_hueco_intermedio_rechazado(self):
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(_resumen(99, 2706, 2805))

    def test_ausencia_de_2706_rechazada(self):
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(_resumen(50, 2710, 2759))

    def test_minimo_incorrecto_anterior_al_corte(self):
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(_resumen(50, 2700, 2749))

    def test_maximo_incorrecto_inconsistente_con_conteo(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=50, total_numeros_distintos=50, numero_sorteo_minimo=2706, numero_sorteo_maximo=2800)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)

    def test_conteo_inconsistente_con_maximo_menos_corte_mas_uno(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=200, total_numeros_distintos=200, numero_sorteo_minimo=2706, numero_sorteo_maximo=2805)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)

    def test_numero_anterior_a_2706_presente(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=10, total_numeros_distintos=10, numero_sorteo_minimo=2705, numero_sorteo_maximo=2714)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)

    def test_valores_negativos_varios(self):
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(_resumen(-10, -10, -1))

    def test_booleano_usado_como_entero_rechazado(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=True, total_numeros_distintos=True, numero_sorteo_minimo=2706, numero_sorteo_maximo=2706)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)

    def test_none_incoherente_cuando_existen_filas(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=10, total_numeros_distintos=10, numero_sorteo_minimo=None, numero_sorteo_maximo=None)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)

    def test_none_incoherente_cuando_no_hay_filas(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=0, total_numeros_distintos=0, numero_sorteo_minimo=2706, numero_sorteo_maximo=2706)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)

    def test_juego_no_autorizado_rechazado(self):
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(_resumen(100, 2706, 2805, juego="MILOTO"))

    def test_minimo_mayor_que_maximo(self):
        r = ResumenDisponibilidadHoldout(juego_codigo="BALOTO", desde_numero_sorteo=2706, total_registros=5, total_numeros_distintos=5, numero_sorteo_minimo=2800, numero_sorteo_maximo=2706)
        with pytest.raises(DisponibilidadHoldoutInvalidaError):
            evaluar_elegibilidad_reapertura_ml(r)


class TestArquitectura:
    def test_reapertura_no_importa_ml_prohibidas(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/reapertura.py")
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
        ruta = pathlib.Path("app/application/use_cases/evaluar_elegibilidad_reapertura_ml.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                for alias in nodo.names:
                    assert not alias.name.startswith("sklearn")
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module:
                    assert not nodo.module.startswith("sklearn")

    def test_ninguna_ruta_http_nueva_en_el_diff_de_ae40(self):
        import pathlib
        for ruta in pathlib.Path("app").rglob("*.py"):
            if "router" in ruta.name.lower() or "api" in str(ruta).lower():
                contenido = ruta.read_text(encoding="utf-8")
                assert "EvaluarElegibilidadReaperturaML" not in contenido
                assert "reapertura" not in contenido.lower()
