"""AE-45, validada: consulta manual y de solo lectura del bloqueo de AE-44."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.application.ml.tipos import EstadoPrediccionML, ReportePrediccionJuego
from scripts import consultar_estado_prediccion as cli
from scripts.auditoria_operativa_bloqueo import FalloAuditoriaOperativaError


DATOS = EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES
NO_GO = EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO
SIN_EVALUACION = EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT


def _reporte(codigo: str) -> ReportePrediccionJuego:
    return ReportePrediccionJuego(
        juego_codigo=codigo,
        estado=DATOS,
        motivos=(DATOS, NO_GO, SIN_EVALUACION),
        explicacion="Bloqueado por datos, NO-GO y ausencia de evaluacion prospectiva.",
        disclaimer="Analisis estadistico, no garantia.",
    )


class _Resolver:
    def __init__(self, fallar_en: str | None = None, cambiar_juego: str | None = None):
        self.llamadas: list[str] = []
        self.fallar_en = fallar_en
        self.cambiar_juego = cambiar_juego

    def ejecutar(self, codigo: str) -> ReportePrediccionJuego:
        self.llamadas.append(codigo)
        if codigo == self.fallar_en:
            raise RuntimeError("fallo sintetico de AE-44")
        return _reporte(self.cambiar_juego or codigo)


def test_json_estable_para_dos_juegos_sin_campos_predictivos():
    resolver = _Resolver()
    reporte = cli.construir_reporte(resolver, "0006")

    assert resolver.llamadas == ["BALOTO", "BALOTO_REVANCHA"]
    assert reporte == cli.construir_reporte(_Resolver(), "0006")
    assert reporte["esquema"] == "1.0"
    assert reporte["alembic_revision"] == "0006"
    assert [r["codigo"] for r in reporte["juegos"]] == resolver.llamadas
    for juego in reporte["juegos"]:
        assert juego["estado"] == DATOS.value
        assert juego["motivos"] == [DATOS.value, NO_GO.value, SIN_EVALUACION.value]
        assert juego["disclaimer"]
        assert "explicacion" in juego
        assert not ({"combinaciones", "probabilidades", "nivel_confianza", "numeros_fuertes"} & juego.keys())
    assert json.loads(json.dumps(reporte)) == reporte


def test_segundo_juego_falla_y_no_devuelve_reporte_parcial():
    resolver = _Resolver(fallar_en="BALOTO_REVANCHA")
    with pytest.raises(cli.FalloConsultaEstadoError, match="BALOTO_REVANCHA") as exc:
        cli.construir_reporte(resolver, "0006")
    assert exc.value.codigo_salida == cli.EXIT_FALLO_EVALUANDO_JUEGO
    assert resolver.llamadas == ["BALOTO", "BALOTO_REVANCHA"]


def test_reporte_de_otro_juego_se_rechaza():
    with pytest.raises(cli.FalloConsultaEstadoError, match="BALOTO_REVANCHA") as exc:
        cli.construir_reporte(_Resolver(cambiar_juego="BALOTO_REVANCHA"), "0006")
    assert exc.value.codigo_salida == cli.EXIT_REPORTE_INCONSISTENTE


def test_no_se_acepta_un_reporte_que_no_sea_del_tipo_bloqueado():
    class _ResolverDefectuoso:
        def ejecutar(self, codigo):
            return {"juego_codigo": codigo, "estado": "habilitado"}

    with pytest.raises(cli.FalloConsultaEstadoError) as exc:
        cli.construir_reporte(_ResolverDefectuoso(), "0006")
    assert exc.value.codigo_salida == cli.EXIT_REPORTE_INCONSISTENTE


class _ConexionFake:
    def __init__(self):
        self.sentencias: list[str] = []
        self.cerrada = False

    def execute(self, sentencia):
        self.sentencias.append(str(sentencia))

    def close(self):
        self.cerrada = True


class _SesionFake:
    def __init__(self, bind):
        self.bind = bind
        self.cerrada = False

    def close(self):
        self.cerrada = True


def _preparar_main(monkeypatch, resolver):
    conexion = _ConexionFake()
    sesiones = []
    orden = []

    def crear_sesion(bind):
        sesion = _SesionFake(bind)
        sesiones.append(sesion)
        return sesion

    def verificar_lectura(sesion):
        assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY"]
        orden.append("solo_lectura")

    def verificar_revision(sesion):
        assert orden == ["solo_lectura"]
        orden.append("revision")
        return "0006"

    def crear_resolver(sesion):
        assert orden == ["solo_lectura", "revision"]
        orden.append("resolver")
        return resolver

    monkeypatch.setattr(cli, "_abrir_conexion", lambda: conexion)
    monkeypatch.setattr(cli, "Session", crear_sesion)
    monkeypatch.setattr(cli, "verificar_transaccion_solo_lectura", verificar_lectura)
    monkeypatch.setattr(cli, "verificar_revision_alembic", verificar_revision)
    monkeypatch.setattr(cli, "_crear_resolver", crear_resolver)
    return conexion, sesiones, orden


def test_main_verifica_solo_lectura_antes_de_evaluar_y_revierte(monkeypatch, capsys):
    resolver = _Resolver()
    conexion, sesiones, orden = _preparar_main(monkeypatch, resolver)

    assert cli.main() == cli.EXIT_OK
    salida = json.loads(capsys.readouterr().out)
    assert [j["codigo"] for j in salida["juegos"]] == resolver.llamadas
    assert orden == ["solo_lectura", "revision", "resolver"]
    assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"]
    assert conexion.cerrada and sesiones[0].cerrada


def test_main_fallo_segundo_juego_no_emite_json_y_revierte(monkeypatch, capsys):
    conexion, sesiones, _ = _preparar_main(monkeypatch, _Resolver(fallar_en="BALOTO_REVANCHA"))

    assert cli.main() == cli.EXIT_FALLO_EVALUANDO_JUEGO
    salida = capsys.readouterr()
    assert salida.out == ""
    assert "BALOTO_REVANCHA" in salida.err
    assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"]
    assert conexion.cerrada and sesiones[0].cerrada


def test_main_no_consulta_juegos_si_la_transaccion_no_es_solo_lectura(monkeypatch, capsys):
    conexion, sesiones, orden = _preparar_main(monkeypatch, _Resolver())

    def denegar(sesion):
        raise FalloAuditoriaOperativaError("solo lectura no confirmada", cli.EXIT_TRANSACCION_NO_SOLO_LECTURA)

    monkeypatch.setattr(cli, "verificar_transaccion_solo_lectura", denegar)
    assert cli.main() == cli.EXIT_TRANSACCION_NO_SOLO_LECTURA
    salida = capsys.readouterr()
    assert salida.out == "" and "solo lectura" in salida.err
    assert orden == []
    assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"]
    assert conexion.cerrada and sesiones[0].cerrada


def test_main_no_emite_json_si_la_revision_alembic_no_coincide(monkeypatch, capsys):
    conexion, sesiones, orden = _preparar_main(monkeypatch, _Resolver())

    def denegar(sesion):
        assert orden == ["solo_lectura"]
        raise FalloAuditoriaOperativaError("revision incompatible", cli.EXIT_REVISION_ALEMBIC_INESPERADA)

    monkeypatch.setattr(cli, "verificar_revision_alembic", denegar)
    assert cli.main() == cli.EXIT_REVISION_ALEMBIC_INESPERADA
    salida = capsys.readouterr()
    assert salida.out == "" and "revision incompatible" in salida.err
    assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"]
    assert conexion.cerrada and sesiones[0].cerrada


def test_fallo_de_conexion_sale_con_codigo_2_sin_reporte(monkeypatch, capsys):
    def denegar():
        raise ConnectionError("sin PostgreSQL")

    monkeypatch.setattr(cli, "_abrir_conexion", denegar)
    assert cli.main() == cli.EXIT_FALLO_CONEXION
    salida = capsys.readouterr()
    assert salida.out == "" and "sin PostgreSQL" in salida.err


def test_script_no_importa_resultados_ni_modulos_predictivos():
    ruta = Path(cli.__file__)
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    importados = {
        nodo.module for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom)
    }
    assert "app.application.use_cases.resolver_estado_prediccion" in importados
    prohibidos = {
        "app.application.ml.inferencia", "app.application.ml.modelo",
        "app.application.ml.dataset", "app.application.ml.prediccion_bloqueada",
    }
    assert not (prohibidos & importados)
    assert not any(nombre and "resultados_historicos" in nombre for nombre in importados)
