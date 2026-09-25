"""Tests de `application/ml/auditoria_operativa_bloqueo.py` -Etapa AE-42."""
from __future__ import annotations

import json

import pytest

from app.application.ml.auditoria_operativa_bloqueo import (
    VERSION_ESQUEMA_AUDITORIA_OPERATIVA,
    ReporteAutorizacionInconsistenteError,
    construir_reporte_auditoria_operativa,
)
from app.application.ml.tipos import (
    EstadoAutorizacionOperativaML,
    EstadoElegibilidadReaperturaML,
    ReporteAutorizacionOperativaML,
    ReporteElegibilidadReaperturaML,
)

INSTANTE = "2026-09-24T00:00:00+00:00"


def _elegibilidad(juego, estado, total, minimo=None, maximo=None):
    return ReporteElegibilidadReaperturaML(
        juego_codigo=juego, estado=estado, proximo_holdout_inicio=2706,
        minimo_sorteos_nuevos_requeridos=100, total_sorteos_nuevos=total,
        numero_sorteo_minimo=minimo, numero_sorteo_maximo=maximo,
        numero_sorteo_objetivo_minimo=2805, numeracion_contigua=True,
    )


def _autorizacion_bloqueada(juego, total=0, minimo=None, maximo=None):
    return ReporteAutorizacionOperativaML(
        juego_codigo=juego, estado=EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES,
        motivo=f"{total} sorteos nuevos", reporte_elegibilidad=_elegibilidad(
            juego, EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, total, minimo, maximo,
        ),
    )


def _autorizacion_autorizada(juego):
    return ReporteAutorizacionOperativaML(
        juego_codigo=juego, estado=EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO,
        motivo="100 sorteos", reporte_elegibilidad=_elegibilidad(
            juego, EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO, 100, 2706, 2805,
        ),
    )


def _autorizacion_numeracion_invalida(juego, motivo="hueco detectado"):
    return ReporteAutorizacionOperativaML(
        juego_codigo=juego, estado=EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA,
        motivo=motivo, reporte_elegibilidad=None,
    )


class TestAmbosBloqueadosPorCeroRegistros:
    def test_ambos_bloqueados_estado_global(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r["estado_global"] == "bloqueado_datos_insuficientes"
        assert r["auditoria_correcta"] is True
        assert r["autorizacion_para_prerregistro_detectada"] is False

    def test_metadatos_minimo_maximo_null_con_total_cero(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        meta = r["resultados"]["BALOTO"]["metadatos_disponibilidad"]
        assert meta["total_sorteos_nuevos"] == 0
        assert meta["numero_sorteo_minimo"] is None
        assert meta["numero_sorteo_maximo"] is None

    def test_ambos_juegos_presentes_en_resultados(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert set(r["resultados"].keys()) == {"BALOTO", "BALOTO_REVANCHA"}


class TestJuegosConEstadosDistintos:
    def test_baloto_autorizado_revancha_bloqueada(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_autorizada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r["resultados"]["BALOTO"]["estado"] == "autorizado_para_prerregistro"
        assert r["resultados"]["BALOTO_REVANCHA"]["estado"] == "bloqueado_datos_insuficientes"
        assert r["estado_global"] == "autorizado_para_prerregistro_detectado"

    def test_decisiones_independientes_nunca_mezcladas(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_autorizada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r["resultados"]["BALOTO"]["juego_codigo"] == "BALOTO"
        assert r["resultados"]["BALOTO_REVANCHA"]["juego_codigo"] == "BALOTO_REVANCHA"


class TestNumeracionInvalida:
    def test_baloto_numeracion_invalida(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_numeracion_invalida("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r["estado_global"] == "bloqueado_numeracion_invalida"
        assert r["resultados"]["BALOTO"]["metadatos_disponibilidad"] is None
        assert r["resultados"]["BALOTO"]["reporte_elegibilidad_disponible"] is False

    def test_revancha_numeracion_invalida(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_numeracion_invalida("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r["estado_global"] == "bloqueado_numeracion_invalida"
        assert r["resultados"]["BALOTO_REVANCHA"]["metadatos_disponibilidad"] is None

    def test_conserva_bloqueo_registra_ausencia_de_reporte_normal(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_numeracion_invalida("BALOTO", "inicio distinto de 2706"),
            _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert "inicio distinto de 2706" in r["resultados"]["BALOTO"]["motivo"]
        assert r["resultados"]["BALOTO"]["estado"] != "autorizado_para_prerregistro"


class TestPosibleElegibilidadFuturaSinAccionAutomatica:
    def test_ambos_autorizados_nunca_implica_entrenamiento_ni_prediccion(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_autorizada("BALOTO"), ReporteAutorizacionOperativaML(
                juego_codigo="BALOTO_REVANCHA", estado=EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO,
                motivo="x", reporte_elegibilidad=_elegibilidad(
                    "BALOTO_REVANCHA", EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO, 150, 2706, 2855,
                ),
            ), INSTANTE,
        )
        assert r["autorizacion_para_prerregistro_detectada"] is True
        for juego in ("BALOTO", "BALOTO_REVANCHA"):
            assert r["resultados"][juego]["resultados_observados"] is False
            assert r["resultados"][juego]["modelos_entrenados"] is False
            assert r["resultados"][juego]["predicciones_generadas"] is False
            assert r["resultados"][juego]["holdout_consumido"] is False

    def test_auditoria_correcta_nunca_se_confunde_con_autorizacion_concedida(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_autorizada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        # ambos campos existen de forma independiente y explicita
        assert "auditoria_correcta" in r
        assert "autorizacion_para_prerregistro_detectada" in r
        assert r["auditoria_correcta"] is True
        assert r["autorizacion_para_prerregistro_detectada"] is True


class TestMezclaDeJuegosYEstructuraInconsistente:
    def test_ambos_reportes_del_mismo_juego_rechazado(self):
        with pytest.raises(ReporteAutorizacionInconsistenteError):
            construir_reporte_auditoria_operativa(
                _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO"), INSTANTE,
            )

    def test_juego_no_autorizado_rechazado(self):
        r_mal = ReporteAutorizacionOperativaML(
            juego_codigo="MILOTO", estado=EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES,
            motivo="x", reporte_elegibilidad=_elegibilidad("MILOTO", EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES, 0),
        )
        with pytest.raises(ReporteAutorizacionInconsistenteError):
            construir_reporte_auditoria_operativa(r_mal, _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE)

    def test_no_produce_reporte_parcial_en_caso_de_inconsistencia(self):
        try:
            construir_reporte_auditoria_operativa(
                _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO"), INSTANTE,
            )
            pytest.fail("deberia haber lanzado ReporteAutorizacionInconsistenteError")
        except ReporteAutorizacionInconsistenteError:
            pass


class TestSerializacionSinDatosProhibidos:
    def test_json_serializable(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        texto = json.dumps(r)
        assert texto

    def test_sin_columnas_ni_datos_prohibidos(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        texto = json.dumps(r).lower()
        for prohibido in (
            "numeros_ganadores", "superbalota", "color", "fecha", "uuid", "password",
            "contrasena", "conexion", "postgresql://", "credencial", "feature", "target",
        ):
            assert prohibido not in texto, prohibido

    def test_sin_uuid_de_juego_ni_id_interno(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert "id" not in r["resultados"]["BALOTO"]
        assert "juego_id" not in r["resultados"]["BALOTO"]

    def test_esquema_versionado_y_estable(self):
        r = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r["version_esquema"] == VERSION_ESQUEMA_AUDITORIA_OPERATIVA
        assert r["etapa"] == "AE-42"
        assert r["proximo_holdout_inicio"] == 2706
        assert r["instante_utc"] == INSTANTE


class TestDeterminismoYReproducibilidad:
    def test_misma_entrada_mismo_resultado(self):
        r1 = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        r2 = construir_reporte_auditoria_operativa(
            _autorizacion_bloqueada("BALOTO"), _autorizacion_bloqueada("BALOTO_REVANCHA"), INSTANTE,
        )
        assert r1 == r2

    def test_nunca_consulta_el_reloj_del_sistema(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/auditoria_operativa_bloqueo.py")
        codigo_fuente = ruta.read_text(encoding="utf-8")
        assert "datetime.now" not in codigo_fuente
        assert "utcnow" not in codigo_fuente


class TestArquitectura:
    def test_no_importa_ml_prohibidas(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/auditoria_operativa_bloqueo.py")
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

    def test_no_reimplementa_reglas_de_ae40_41_solo_traduce(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/application/ml/auditoria_operativa_bloqueo.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        nombres_importados = set()
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.ImportFrom):
                for alias in nodo.names:
                    nombres_importados.add(alias.name)
        assert "ReporteAutorizacionOperativaML" in nombres_importados
        assert "EstadoAutorizacionOperativaML" in nombres_importados
