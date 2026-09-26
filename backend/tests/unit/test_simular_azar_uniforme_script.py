"""Tests de `scripts/simular_azar_uniforme.py` -Etapa AE-49,
validada: consulta manual de solo lectura que publica la
referencia Monte Carlo exploratoria. Conexion, sesion y repositorios
fake con historicos sinteticos: nunca PostgreSQL ni resultados reales."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.application.simulaciones import montecarlo_uniforme as mc
from app.application.use_cases.simular_referencia_azar_uniforme import SimularReferenciaAzarUniforme
from scripts import simular_azar_uniforme as cli
from scripts.auditoria_operativa_bloqueo import FalloAuditoriaOperativaError
from scripts.comparacion_estado_prediccion import CLAVES_PREDICTIVAS, serializar_reporte
from tests.unit.simulaciones import sinteticos

RAIZ_BACKEND = Path(cli.__file__).resolve().parents[1]
PATRON_HUELLA = re.compile(r"^SHA-256 ([0-9a-f]{64})  (.+)  \((\d+) bytes\)$")
ITERACIONES_PRUEBA = 5


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


def _caso_sintetico(resultados=None):
    return SimularReferenciaAzarUniforme(
        sinteticos.JuegoRepositoryFake(), resultados or sinteticos.ResultadosRepositoryFake(),
        iteraciones=ITERACIONES_PRUEBA,
    )


def _preparar_main(monkeypatch, caso=None):
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
        return "0006"

    def crear_caso(sesion):
        assert orden == ["solo_lectura", "revision"]
        orden.append("consulta")
        return caso or _caso_sintetico()

    monkeypatch.setattr(cli, "_abrir_conexion", lambda: conexion)
    monkeypatch.setattr(cli, "Session", crear_sesion)
    monkeypatch.setattr(cli, "verificar_transaccion_solo_lectura", verificar_lectura)
    monkeypatch.setattr(cli, "verificar_revision_alembic", verificar_revision)
    monkeypatch.setattr(cli, "_crear_caso_uso", crear_caso)
    return conexion, sesiones, orden


def _conexion_prohibida(monkeypatch):
    def fallar():
        raise AssertionError("no deberia abrirse la conexion")

    monkeypatch.setattr(cli, "_abrir_conexion", fallar)


def _reporte_esperado() -> bytes:
    return serializar_reporte(_caso_sintetico().ejecutar("0006"))


# ---------------------------------------------------------------------------
# Flujo normal
# ---------------------------------------------------------------------------

def test_sin_flags_publica_el_json_en_stdout(monkeypatch, capsysbinary):
    conexion, sesiones, orden = _preparar_main(monkeypatch)
    assert cli.main([]) == cli.EXIT_OK == 0
    salida = capsysbinary.readouterr()
    assert salida.out == _reporte_esperado()
    assert salida.err == b""
    assert orden == ["solo_lectura", "revision", "consulta"]
    assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"]
    assert conexion.cerrada and sesiones[0].cerrada


def test_json_exploratorio_sin_claves_predictivas(monkeypatch, capsysbinary):
    _preparar_main(monkeypatch)
    cli.main([])
    reporte = json.loads(capsysbinary.readouterr().out.decode("utf-8"))
    assert reporte["caracter"] == "exploratorio_sobre_datos_reutilizados"
    assert reporte["nota"] == mc.NOTA_AE49

    def recorrer(nodo):
        if isinstance(nodo, dict):
            for clave, valor in nodo.items():
                assert clave not in CLAVES_PREDICTIVAS, clave
                recorrer(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                recorrer(valor)

    recorrer(reporte)


def test_salida_en_proceso_mismos_bytes_y_huella_en_stderr(monkeypatch, capsysbinary, tmp_path):
    _preparar_main(monkeypatch)
    destino = tmp_path / "sim.json"
    assert cli.main(["--salida", str(destino)]) == cli.EXIT_OK
    capturado = capsysbinary.readouterr()
    assert capturado.out == destino.read_bytes() == _reporte_esperado()
    coincidencia = PATRON_HUELLA.match(capturado.err.decode("utf-8").strip())
    assert coincidencia and coincidencia.group(1) == hashlib.sha256(destino.read_bytes()).hexdigest()


_PROGRAMA_SUBPROCESO = r'''
import sys
from scripts import simular_azar_uniforme as cli
from tests.unit import test_simular_azar_uniforme_script as t

conexion = t._ConexionFake()
cli._abrir_conexion = lambda: conexion
cli.Session = t._SesionFake
cli.verificar_transaccion_solo_lectura = lambda sesion: None
cli.verificar_revision_alembic = lambda sesion: "0006"
cli._crear_caso_uso = lambda sesion: t._caso_sintetico()
codigo = cli.main(sys.argv[1:])
assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"], conexion.sentencias
sys.exit(codigo)
'''


def test_salida_stdout_del_proceso_archivo_y_huella_coinciden(tmp_path):
    destino = tmp_path / "sim.json"
    proceso = subprocess.run(
        [sys.executable, "-c", _PROGRAMA_SUBPROCESO, "--salida", str(destino)],
        cwd=RAIZ_BACKEND, env={**os.environ, "PYTHONPATH": str(RAIZ_BACKEND)}, capture_output=True, timeout=300,
    )
    assert proceso.returncode == 0, proceso.stderr
    guardado = destino.read_bytes()
    assert proceso.stdout == guardado and b"\r" not in guardado
    lineas = proceso.stderr.decode("utf-8").strip().splitlines()
    assert len(lineas) == 1
    coincidencia = PATRON_HUELLA.match(lineas[0])
    assert coincidencia and coincidencia.group(1) == hashlib.sha256(guardado).hexdigest()
    assert int(coincidencia.group(3)) == len(guardado)


# ---------------------------------------------------------------------------
# Argumentos y rutas: siempre antes de abrir la conexion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("argumentos", [
    ["--semilla", "1"], ["--iteraciones", "5"], ["--hasta-numero-sorteo", "2706"],
    ["--desde-numero-sorteo", "2591"], ["extra"], ["--salida"],
])
def test_ningun_flag_de_rango_semilla_o_iteraciones_codigo_7(monkeypatch, capsysbinary, argumentos):
    _conexion_prohibida(monkeypatch)
    assert cli.main(argumentos) == cli.EXIT_ARGUMENTOS_INVALIDOS == 7
    salida = capsysbinary.readouterr()
    assert salida.out == b"" and b"ERROR" in salida.err


def test_salida_existente_o_directorio_inexistente_codigo_9(monkeypatch, capsysbinary, tmp_path):
    existente = tmp_path / "sim.json"
    existente.write_bytes(b"evidencia previa")
    _conexion_prohibida(monkeypatch)
    assert cli.main(["--salida", str(existente)]) == cli.EXIT_RUTA_SALIDA_NO_PERMITIDA == 9
    assert existente.read_bytes() == b"evidencia previa"
    assert cli.main(["--salida", str(tmp_path / "no-existe" / "x.json")]) == 9
    assert capsysbinary.readouterr().out == b""


def test_destino_que_aparece_antes_de_publicar_codigo_8(monkeypatch, capsysbinary, tmp_path):
    from scripts import comparacion_estado_prediccion as escritor

    _preparar_main(monkeypatch)
    destino = tmp_path / "sim.json"
    publicar_real = escritor._publicar_exclusivo

    def intruso_y_publicar(temporal, ruta_destino):
        Path(ruta_destino).write_bytes(b"escrito por otro proceso")
        publicar_real(temporal, ruta_destino)

    monkeypatch.setattr(escritor, "_publicar_exclusivo", intruso_y_publicar)
    assert cli.main(["--salida", str(destino)]) == cli.EXIT_FALLO_ESCRITURA_SALIDA == 8
    assert capsysbinary.readouterr().out == b""
    assert destino.read_bytes() == b"escrito por otro proceso"


# ---------------------------------------------------------------------------
# Errores con ROLLBACK y sin JSON
# ---------------------------------------------------------------------------

def test_historico_invalido_codigo_5_sin_json_con_rollback(monkeypatch, capsysbinary):
    historicos = {
        sinteticos.ID_BALOTO: sinteticos.historico_baloto()[:-1],
        sinteticos.ID_REVANCHA: sinteticos.historico_revancha(),
    }
    conexion, _, _ = _preparar_main(monkeypatch, _caso_sintetico(sinteticos.ResultadosRepositoryFake(historicos)))
    assert cli.main([]) == cli.EXIT_ENTRADA_INVALIDA == 5
    assert capsysbinary.readouterr().out == b""
    assert conexion.sentencias[-1] == "ROLLBACK" and conexion.cerrada


def test_fallo_simulando_codigo_6_sin_json_parcial(monkeypatch, capsysbinary):
    caso = _caso_sintetico(sinteticos.ResultadosRepositoryFake(fallar_en=sinteticos.ID_REVANCHA))
    conexion, _, _ = _preparar_main(monkeypatch, caso)
    assert cli.main([]) == cli.EXIT_FALLO_SIMULANDO == 6
    assert capsysbinary.readouterr().out == b""
    assert conexion.sentencias[-1] == "ROLLBACK"


def test_fallo_de_conexion_codigo_2(monkeypatch, capsysbinary):
    def fallar():
        raise OSError("sin servidor")

    monkeypatch.setattr(cli, "_abrir_conexion", fallar)
    assert cli.main([]) == cli.EXIT_FALLO_CONEXION == 2
    assert capsysbinary.readouterr().out == b""


def test_transaccion_no_solo_lectura_devuelve_su_codigo(monkeypatch, capsysbinary):
    conexion, _, _ = _preparar_main(monkeypatch)

    def no_solo_lectura(sesion):
        raise FalloAuditoriaOperativaError("transaccion no READ ONLY", 4)

    monkeypatch.setattr(cli, "verificar_transaccion_solo_lectura", no_solo_lectura)
    assert cli.main([]) == 4
    assert capsysbinary.readouterr().out == b""
    assert conexion.sentencias[-1] == "ROLLBACK"


def test_codigos_de_salida():
    assert (cli.EXIT_OK, cli.EXIT_FALLO_INESPERADO, cli.EXIT_FALLO_CONEXION, cli.EXIT_REVISION_ALEMBIC_INESPERADA,
            cli.EXIT_TRANSACCION_NO_SOLO_LECTURA, cli.EXIT_ENTRADA_INVALIDA, cli.EXIT_FALLO_SIMULANDO,
            cli.EXIT_ARGUMENTOS_INVALIDOS, cli.EXIT_FALLO_ESCRITURA_SALIDA,
            cli.EXIT_RUTA_SALIDA_NO_PERMITIDA) == tuple(range(10))


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------

def _texto_script() -> str:
    return Path(cli.__file__).read_text(encoding="utf-8")


def test_script_usa_las_constantes_sin_semilla_ni_iteraciones():
    arbol = ast.parse(_texto_script())
    funcion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "_crear_caso_uso")
    llamadas = [n for n in ast.walk(funcion)
                if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "SimularReferenciaAzarUniforme"]
    assert len(llamadas) == 1
    assert llamadas[0].keywords == [] and len(llamadas[0].args) == 2


def test_script_no_escribe_ni_importa_ml_ni_se_ejecuta_solo():
    texto = _texto_script()
    assert 'if __name__ == "__main__":' in texto
    for prohibido in (".add(", "commit(", "SimulacionORM", "INSERT", "UPDATE", "DELETE",
                      "resolver_estado_prediccion", "diagnostico_bloqueo", "diagnosticar_estado_prediccion",
                      "app.application.ml", "sklearn", "schedule", "celery", "BackgroundTasks"):
        assert prohibido not in texto, prohibido


def test_nada_en_web_main_ni_plantillas_expone_ae49():
    rutas = [*(RAIZ_BACKEND / "app" / "api").rglob("*.py"), RAIZ_BACKEND / "app" / "main.py"]
    plantillas = list((RAIZ_BACKEND / "app" / "templates").rglob("*.html"))
    for ruta in rutas + plantillas:
        contenido = ruta.read_text(encoding="utf-8")
        for nombre in ("montecarlo_uniforme", "simular_referencia_azar_uniforme", "simular_azar_uniforme",
                       "app.application.simulaciones"):
            assert nombre not in contenido, (ruta, nombre)
