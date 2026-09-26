"""Tests de `scripts/auditar_evidencia_montecarlo.py` -Etapa AE-51,
validada: CLI que audita una evidencia AE-49 frente al historico
actual en una transaccion READ ONLY verificada con ROLLBACK.
Conexion, sesion y repositorios fake con historicos sinteticos:
nunca PostgreSQL ni evidencia real."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import auditar_evidencia_montecarlo as cli
from scripts import auditoria_evidencia_montecarlo as aud
from scripts.auditoria_operativa_bloqueo import FalloAuditoriaOperativaError
from scripts.comparacion_estado_prediccion import serializar_reporte
from tests.unit.simulaciones import evidencia_auditable as ea
from tests.unit.simulaciones import sinteticos

RAIZ_BACKEND = Path(cli.__file__).resolve().parents[1]


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


def _preparar_main(monkeypatch, historicos=None, juegos=None, revision="0006", resultados=None):
    conexion, sesiones, orden = _ConexionFake(), [], []

    def crear_sesion(bind):
        sesiones.append(_SesionFake(bind))
        return sesiones[-1]

    def verificar_lectura(sesion):
        assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY"]
        orden.append("solo_lectura")

    def verificar_revision(sesion):
        assert orden == ["solo_lectura"]
        orden.append("revision")
        return revision

    def crear_repositorios(sesion):
        assert orden == ["solo_lectura", "revision"]
        orden.append("consulta")
        return (juegos or sinteticos.JuegoRepositoryFake(),
                resultados or sinteticos.ResultadosRepositoryFake(historicos))

    monkeypatch.setattr(cli, "_abrir_conexion", lambda: conexion)
    monkeypatch.setattr(cli, "Session", crear_sesion)
    monkeypatch.setattr(cli, "verificar_transaccion_solo_lectura", verificar_lectura)
    monkeypatch.setattr(cli, "verificar_revision_alembic", verificar_revision)
    monkeypatch.setattr(cli, "_crear_repositorios", crear_repositorios)
    return conexion, sesiones, orden


def _conexion_prohibida(monkeypatch):
    def fallar():
        raise AssertionError("no deberia abrirse la conexion")

    monkeypatch.setattr(cli, "_abrir_conexion", fallar)


def _escribir(tmp_path, contenido: bytes, nombre="sim.json") -> Path:
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    return ruta


def _huella_y_mtime(ruta: Path):
    return hashlib.sha256(ruta.read_bytes()).hexdigest(), os.stat(ruta).st_mtime_ns


# ---------------------------------------------------------------------------
# Coincide / no coincide
# ---------------------------------------------------------------------------

def test_coincide_codigo_0_con_solo_lectura_y_rollback(monkeypatch, capsysbinary, tmp_path):
    ruta = _escribir(tmp_path, ea.evidencia_auditable())
    antes = _huella_y_mtime(ruta)
    conexion, sesiones, orden = _preparar_main(monkeypatch)
    assert cli.main([str(ruta)]) == cli.EXIT_COINCIDE == 0
    salida = capsysbinary.readouterr()
    informe = json.loads(salida.out)
    assert informe["resultado"] == "coincide"
    assert salida.err == b""
    assert orden == ["solo_lectura", "revision", "consulta"]
    assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"]
    assert conexion.cerrada and sesiones[0].cerrada
    assert _huella_y_mtime(ruta) == antes


def test_stdout_son_los_bytes_canonicos_del_informe(monkeypatch, capsysbinary, tmp_path):
    contenido = ea.evidencia_auditable()
    ruta = _escribir(tmp_path, contenido)
    _preparar_main(monkeypatch)
    cli.main([str(ruta)])
    salida = capsysbinary.readouterr().out
    resumen, reporte = aud.leer_evidencia_validada(contenido)
    juegos = aud.auditar_contra_historico(reporte, sinteticos.JuegoRepositoryFake(),
                                          sinteticos.ResultadosRepositoryFake())
    assert salida == serializar_reporte(aud.construir_informe_auditoria(resumen, reporte, juegos, "0006"))


def test_datos_actuales_distintos_codigo_10_con_informe(monkeypatch, capsysbinary, tmp_path):
    ruta = _escribir(tmp_path, ea.evidencia_auditable())
    cambiado = [dataclasses.replace(r, numeros=(1, 2, 3, 4, 5)) if r.numero_sorteo == 2400 else r
                for r in sinteticos.historico_revancha()]
    conexion, _, _ = _preparar_main(monkeypatch, historicos={
        sinteticos.ID_BALOTO: sinteticos.historico_baloto(), sinteticos.ID_REVANCHA: cambiado,
    })
    assert cli.main([str(ruta)]) == cli.EXIT_NO_COINCIDE == 10
    salida = capsysbinary.readouterr()
    informe = json.loads(salida.out)
    assert informe["resultado"] == "no_coincide"
    assert [j["huella_coincide"] for j in informe["juegos"]] == [True, False]
    assert b"no coincide" in salida.err
    assert conexion.sentencias[-1] == "ROLLBACK"


def test_revision_actual_distinta_no_cambia_el_resultado(monkeypatch, capsysbinary, tmp_path):
    ruta = _escribir(tmp_path, ea.evidencia_auditable(revision="0006"))
    _preparar_main(monkeypatch, revision="0007")
    assert cli.main([str(ruta)]) == 0
    informe = json.loads(capsysbinary.readouterr().out)
    assert informe["misma_revision_alembic"] is False


# ---------------------------------------------------------------------------
# AE-50 antes de conectar
# ---------------------------------------------------------------------------

def _invalida() -> bytes:
    reporte = ea.copia(ea.reporte_auditable())
    reporte["parametros"]["semilla"] = 1
    return serializar_reporte(reporte)


def _incoherente() -> bytes:
    reporte = ea.copia(ea.reporte_auditable())
    reporte["juegos"][0]["estadisticas"][0]["p_valor_empirico"] = 0.003
    return serializar_reporte(reporte)


@pytest.mark.parametrize("fabricar, codigo", [
    (lambda: b"{roto", 3), (lambda: b"NaN", 3), (_invalida, 4), (_incoherente, 5),
])
def test_evidencia_rechazada_por_ae50_sin_abrir_conexion(monkeypatch, capsysbinary, tmp_path, fabricar, codigo):
    ruta = _escribir(tmp_path, fabricar())
    _conexion_prohibida(monkeypatch)
    assert cli.main([str(ruta)]) == codigo
    salida = capsysbinary.readouterr()
    assert salida.out == b"" and b"ERROR" in salida.err


def test_archivo_inexistente_codigo_3_sin_conexion(monkeypatch, capsysbinary, tmp_path):
    _conexion_prohibida(monkeypatch)
    assert cli.main([str(tmp_path / "no-existe.json")]) == cli.EXIT_ILEGIBLE == 3
    assert capsysbinary.readouterr().out == b""


@pytest.mark.parametrize("argumentos", [[], ["a.json", "b.json"], ["--semilla", "1"], ["--salida", "x.json"]])
def test_argumentos_invalidos_codigo_2_sin_conexion(monkeypatch, capsysbinary, argumentos):
    _conexion_prohibida(monkeypatch)
    assert cli.main(argumentos) == cli.EXIT_ARGUMENTOS_INVALIDOS == 2
    assert capsysbinary.readouterr().out == b""


# ---------------------------------------------------------------------------
# Conexion, transaccion e historico actual
# ---------------------------------------------------------------------------

def test_fallo_de_conexion_codigo_6(monkeypatch, capsysbinary, tmp_path):
    ruta = _escribir(tmp_path, ea.evidencia_auditable())

    def fallar():
        raise OSError("sin servidor")

    monkeypatch.setattr(cli, "_abrir_conexion", fallar)
    assert cli.main([str(ruta)]) == cli.EXIT_FALLO_CONEXION == 6
    assert capsysbinary.readouterr().out == b""


@pytest.mark.parametrize("codigo_ae42, esperado", [(3, 7), (4, 8)])
def test_revision_o_solo_lectura_fallidas_se_reasignan(monkeypatch, capsysbinary, tmp_path, codigo_ae42, esperado):
    ruta = _escribir(tmp_path, ea.evidencia_auditable())
    conexion, _, _ = _preparar_main(monkeypatch)

    def fallar(sesion):
        raise FalloAuditoriaOperativaError("fallo sintetico", codigo_ae42)

    monkeypatch.setattr(cli, "verificar_transaccion_solo_lectura", fallar)
    assert cli.main([str(ruta)]) == esperado
    assert capsysbinary.readouterr().out == b""
    assert conexion.sentencias[-1] == "ROLLBACK" and conexion.cerrada


def test_historico_actual_fuera_de_contrato_codigo_9(monkeypatch, capsysbinary, tmp_path):
    ruta = _escribir(tmp_path, ea.evidencia_auditable())
    conexion, _, _ = _preparar_main(monkeypatch, historicos={
        sinteticos.ID_BALOTO: sinteticos.historico_baloto()[:-1],
        sinteticos.ID_REVANCHA: sinteticos.historico_revancha(),
    })
    assert cli.main([str(ruta)]) == cli.EXIT_HISTORICO_INVALIDO == 9
    assert capsysbinary.readouterr().out == b""
    assert conexion.sentencias[-1] == "ROLLBACK"


def test_parametros_de_bd_distintos_codigo_9(monkeypatch, capsysbinary, tmp_path):
    ruta = _escribir(tmp_path, ea.evidencia_auditable())
    juegos = sinteticos.JuegoRepositoryFake({
        "BALOTO": sinteticos.juego("BALOTO", sinteticos.ID_BALOTO, rango_max=45),
        "BALOTO_REVANCHA": sinteticos.juego("BALOTO_REVANCHA", sinteticos.ID_REVANCHA),
    })
    _preparar_main(monkeypatch, juegos=juegos)
    assert cli.main([str(ruta)]) == 9
    assert capsysbinary.readouterr().out == b""


def test_fallo_inesperado_codigo_1_sin_informe_parcial(monkeypatch, capsysbinary, tmp_path):
    ruta = _escribir(tmp_path, ea.evidencia_auditable())
    conexion, _, _ = _preparar_main(
        monkeypatch, resultados=sinteticos.ResultadosRepositoryFake(fallar_en=sinteticos.ID_REVANCHA))
    assert cli.main([str(ruta)]) == cli.EXIT_FALLO_INESPERADO == 1
    assert capsysbinary.readouterr().out == b""
    assert conexion.sentencias[-1] == "ROLLBACK"


def test_codigos_de_salida():
    assert (cli.EXIT_COINCIDE, cli.EXIT_FALLO_INESPERADO, cli.EXIT_ARGUMENTOS_INVALIDOS, cli.EXIT_ILEGIBLE,
            cli.EXIT_INVALIDA, cli.EXIT_INCOHERENTE, cli.EXIT_FALLO_CONEXION, cli.EXIT_REVISION_ALEMBIC_INESPERADA,
            cli.EXIT_TRANSACCION_NO_SOLO_LECTURA, cli.EXIT_HISTORICO_INVALIDO,
            cli.EXIT_NO_COINCIDE) == tuple(range(11))


# ---------------------------------------------------------------------------
# Proceso real y estructura
# ---------------------------------------------------------------------------

_PROGRAMA_SUBPROCESO = r'''
import sys
from scripts import auditar_evidencia_montecarlo as cli
from tests.unit import test_auditar_evidencia_montecarlo_script as t
from tests.unit.simulaciones import sinteticos

conexion = t._ConexionFake()
cli._abrir_conexion = lambda: conexion
cli.Session = t._SesionFake
cli.verificar_transaccion_solo_lectura = lambda sesion: None
cli.verificar_revision_alembic = lambda sesion: "0006"
cli._crear_repositorios = lambda sesion: (sinteticos.JuegoRepositoryFake(), sinteticos.ResultadosRepositoryFake())
codigo = cli.main(sys.argv[1:])
assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"], conexion.sentencias
sys.exit(codigo)
'''


def test_proceso_hijo_stdout_bytes(tmp_path):
    ruta = _escribir(tmp_path, ea.evidencia_auditable())
    proceso = subprocess.run(
        [sys.executable, "-c", _PROGRAMA_SUBPROCESO, str(ruta)],
        cwd=RAIZ_BACKEND, env={**os.environ, "PYTHONPATH": str(RAIZ_BACKEND)}, capture_output=True, timeout=120,
    )
    assert proceso.returncode == 0, proceso.stderr
    assert b"\r" not in proceso.stdout and proceso.stderr == b""
    assert json.loads(proceso.stdout)["resultado"] == "coincide"


def test_cli_sin_escrituras_ni_ml_con_guarda_main():
    texto = Path(cli.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in texto
    for prohibido in ("commit(", ".add(", "INSERT", "UPDATE", "DELETE", "SimulacionORM", "app.application.ml",
                      "comparar_juego", "simular_historia", "resolver_estado_prediccion", "diagnostico_bloqueo",
                      "diagnosticar_estado_prediccion", '"w"', '"wb"', "write_bytes"):
        assert prohibido not in texto, prohibido


def test_nada_en_app_menciona_ae51():
    raiz = RAIZ_BACKEND / "app"
    for ruta in [*raiz.rglob("*.py"), *(raiz / "templates").rglob("*.html")]:
        contenido = ruta.read_text(encoding="utf-8")
        for nombre in ("auditoria_evidencia_montecarlo", "auditar_evidencia_montecarlo"):
            assert nombre not in contenido, (ruta, nombre)
