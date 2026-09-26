"""AE-45, validada; ampliada en AE-47, validada: consulta manual y de
solo lectura del bloqueo de AE-44 con el diagnostico de AE-46 (esquema
JSON 1.1). Todo es sintetico: fakes de conexion, sesion, resolvedor,
diagnosticador y repositorios de metadatos -nunca PostgreSQL."""
from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.ml.autorizacion_operativa import evaluar_autorizacion_operativa_desde_elegibilidad
from app.application.ml.diagnostico_bloqueo import diagnosticar_bloqueo
from app.application.ml.reapertura import evaluar_elegibilidad_reapertura_ml
from app.application.ml.tipos import (
    DecisionContinuidadML,
    EstadoPrediccionML,
    ReportePrediccionJuego,
    ResumenDisponibilidadHoldout,
)
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML
from app.domain.entities.juego import Juego
from scripts import consultar_estado_prediccion as cli
from scripts.auditoria_operativa_bloqueo import FalloAuditoriaOperativaError
from tests.unit.fakes import FakeJuegoRepository


DATOS = EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES
NO_GO = EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO
SIN_EVALUACION = EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT
CAMPOS_PREDICTIVOS = {"combinaciones", "probabilidades", "nivel_confianza", "numeros_fuertes", "numeros_debiles"}


def _reporte(codigo: str) -> ReportePrediccionJuego:
    return ReportePrediccionJuego(
        juego_codigo=codigo,
        estado=DATOS,
        motivos=(DATOS, NO_GO, SIN_EVALUACION),
        explicacion="Bloqueado por datos, NO-GO y ausencia de evaluacion prospectiva.",
        disclaimer="Analisis estadistico, no garantia.",
    )


def _autorizacion_sintetica(codigo: str, total: int = 8):
    resumen = ResumenDisponibilidadHoldout(
        juego_codigo=codigo, desde_numero_sorteo=2706, total_registros=total, total_numeros_distintos=total,
        numero_sorteo_minimo=2706 if total else None, numero_sorteo_maximo=2705 + total if total else None,
    )
    return evaluar_autorizacion_operativa_desde_elegibilidad(evaluar_elegibilidad_reapertura_ml(resumen))


def _diagnostico(codigo: str):
    return diagnosticar_bloqueo(_autorizacion_sintetica(codigo), DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE)


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


class _Diagnosticador:
    def __init__(self, fallar_en: str | None = None, transformar=None):
        self.llamadas: list[str] = []
        self.fallar_en = fallar_en
        self.transformar = transformar

    def ejecutar(self, codigo: str):
        self.llamadas.append(codigo)
        if codigo == self.fallar_en:
            raise RuntimeError("fallo sintetico de AE-46")
        diagnostico = _diagnostico(codigo)
        return self.transformar(diagnostico) if self.transformar else diagnostico


# ---------------------------------------------------------------------------
# Esquema 1.1 y ausencia de salidas predictivas
# ---------------------------------------------------------------------------

def test_json_estable_para_dos_juegos_sin_campos_predictivos():
    resolver, diagnosticador = _Resolver(), _Diagnosticador()
    reporte = cli.construir_reporte(resolver, diagnosticador, "0006")

    assert resolver.llamadas == ["BALOTO", "BALOTO_REVANCHA"]
    assert diagnosticador.llamadas == ["BALOTO", "BALOTO_REVANCHA"]
    assert reporte == cli.construir_reporte(_Resolver(), _Diagnosticador(), "0006")
    assert reporte["esquema"] == "1.1" == cli.ESQUEMA_JSON
    assert reporte["alembic_revision"] == "0006"
    assert [r["codigo"] for r in reporte["juegos"]] == resolver.llamadas
    for juego in reporte["juegos"]:
        assert juego["estado"] == DATOS.value
        assert juego["motivos"] == [DATOS.value, NO_GO.value, SIN_EVALUACION.value]
        assert juego["disclaimer"]
        assert "explicacion" in juego
        assert not (CAMPOS_PREDICTIVOS & juego.keys())
    assert json.loads(json.dumps(reporte)) == reporte


def test_esquema_1_1_incluye_progreso_y_condiciones_pendientes():
    reporte = cli.construir_reporte(_Resolver(), _Diagnosticador(), "0006")
    for juego in reporte["juegos"]:
        assert set(juego) == {
            "codigo", "estado", "motivos", "explicacion", "disclaimer",
            "progreso", "condiciones_pendientes", "desbloqueable",
        }
        assert juego["progreso"] == {
            "evaluable": True, "desde_numero_sorteo": 2706, "total_sorteos_nuevos": 8,
            "minimo_requerido": 100, "faltantes": 92, "numero_sorteo_objetivo_minimo": 2805,
        }
        assert juego["condiciones_pendientes"] == [
            "minimo_sorteos_nuevos", "evidencia_cientifica_ae39",
            "protocolo_prospectivo_prerregistrado", "evaluacion_prospectiva_positiva",
        ]
        assert juego["desbloqueable"] is False


def test_json_serializado_no_contiene_ninguna_clave_predictiva_anidada():
    reporte = cli.construir_reporte(_Resolver(), _Diagnosticador(), "0006")

    def claves(objeto):
        if isinstance(objeto, dict):
            for clave, valor in objeto.items():
                yield clave
                yield from claves(valor)
        elif isinstance(objeto, list):
            for valor in objeto:
                yield from claves(valor)

    assert not (CAMPOS_PREDICTIVOS & set(claves(reporte)))


# ---------------------------------------------------------------------------
# Errores sin reporte parcial y coherencia entre diagnostico y reporte
# ---------------------------------------------------------------------------

def test_segundo_juego_falla_y_no_devuelve_reporte_parcial():
    resolver = _Resolver(fallar_en="BALOTO_REVANCHA")
    with pytest.raises(cli.FalloConsultaEstadoError, match="BALOTO_REVANCHA") as exc:
        cli.construir_reporte(resolver, _Diagnosticador(), "0006")
    assert exc.value.codigo_salida == cli.EXIT_FALLO_EVALUANDO_JUEGO
    assert resolver.llamadas == ["BALOTO", "BALOTO_REVANCHA"]


def test_fallo_del_diagnostico_en_el_segundo_juego_no_devuelve_reporte_parcial():
    with pytest.raises(cli.FalloConsultaEstadoError, match="BALOTO_REVANCHA") as exc:
        cli.construir_reporte(_Resolver(), _Diagnosticador(fallar_en="BALOTO_REVANCHA"), "0006")
    assert exc.value.codigo_salida == cli.EXIT_FALLO_EVALUANDO_JUEGO


def test_reporte_de_otro_juego_se_rechaza():
    with pytest.raises(cli.FalloConsultaEstadoError, match="BALOTO_REVANCHA") as exc:
        cli.construir_reporte(_Resolver(cambiar_juego="BALOTO_REVANCHA"), _Diagnosticador(), "0006")
    assert exc.value.codigo_salida == cli.EXIT_REPORTE_INCONSISTENTE


def test_no_se_acepta_un_reporte_que_no_sea_del_tipo_bloqueado():
    class _ResolverDefectuoso:
        def ejecutar(self, codigo):
            return {"juego_codigo": codigo, "estado": "habilitado"}

    with pytest.raises(cli.FalloConsultaEstadoError) as exc:
        cli.construir_reporte(_ResolverDefectuoso(), _Diagnosticador(), "0006")
    assert exc.value.codigo_salida == cli.EXIT_REPORTE_INCONSISTENTE


@pytest.mark.parametrize("transformar, descripcion", [
    (lambda d: {"juego_codigo": d.juego_codigo}, "tipo"),
    (lambda d: _diagnostico("BALOTO_REVANCHA") if d.juego_codigo == "BALOTO" else d, "juego"),
    (lambda d: dataclasses.replace(
        diagnosticar_bloqueo(_autorizacion_sintetica(d.juego_codigo, total=100),
                             DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE)), "estado"),
    (lambda d: diagnosticar_bloqueo(_autorizacion_sintetica(d.juego_codigo),
                                    DecisionContinuidadML.EVIDENCIA_EXPLORATORIA_DE_MEJORA), "motivos"),
])
def test_diagnostico_incoherente_con_el_reporte_se_rechaza_sin_json(transformar, descripcion):
    with pytest.raises(cli.FalloConsultaEstadoError) as exc:
        cli.construir_reporte(_Resolver(), _Diagnosticador(transformar=transformar), "0006")
    assert exc.value.codigo_salida == cli.EXIT_REPORTE_INCONSISTENTE, descripcion


# ---------------------------------------------------------------------------
# Una sola consulta agregada de AE-41 por juego, compartida
# ---------------------------------------------------------------------------

def _juego(codigo: str) -> Juego:
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43, cantidad_numeros=5,
        tiene_superbalota=True, superbalota_min=1, superbalota_max=16, tiene_color=False,
        permite_repeticion=False, activo=True,
    )


class _DisponibilidadQueCuenta:
    """Metadatos sinteticos (8 sorteos 2706..2713); cuenta las consultas
    agregadas por juego."""

    def __init__(self):
        self.consultas: dict[str, int] = {}

    def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
        self.consultas[codigo_juego] = self.consultas.get(codigo_juego, 0) + 1
        return ResumenDisponibilidadHoldout(
            juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
            total_registros=8, total_numeros_distintos=8, numero_sorteo_minimo=2706, numero_sorteo_maximo=2713,
        )


def _autorizacion_real(disponibilidad) -> EvaluarAutorizacionOperativaML:
    juegos = FakeJuegoRepository(juegos=[_juego("BALOTO"), _juego("BALOTO_REVANCHA")])
    return EvaluarAutorizacionOperativaML(EvaluarElegibilidadReaperturaML(juegos, disponibilidad))


def test_una_sola_consulta_agregada_por_juego_con_los_casos_de_uso_reales():
    disponibilidad = _DisponibilidadQueCuenta()
    resolver, diagnosticador = cli._crear_consultas_desde(_autorizacion_real(disponibilidad))
    reporte = cli.construir_reporte(resolver, diagnosticador, "0006")

    assert disponibilidad.consultas == {"BALOTO": 1, "BALOTO_REVANCHA": 1}
    for juego in reporte["juegos"]:
        assert juego["estado"] == DATOS.value
        assert juego["progreso"]["faltantes"] == 92
        assert juego["desbloqueable"] is False


def test_el_adaptador_comparte_el_mismo_reporte_de_ae41():
    disponibilidad = _DisponibilidadQueCuenta()
    adaptador = cli._AutorizacionUnaVezPorJuego(_autorizacion_real(disponibilidad))
    primero = adaptador.ejecutar("BALOTO")
    assert adaptador.ejecutar("BALOTO") is primero
    adaptador.ejecutar("BALOTO_REVANCHA")
    assert disponibilidad.consultas == {"BALOTO": 1, "BALOTO_REVANCHA": 1}


def test_el_adaptador_no_guarda_fallos():
    class _AutorizacionQueFallaUnaVez:
        def __init__(self):
            self.llamadas = 0

        def ejecutar(self, codigo):
            self.llamadas += 1
            if self.llamadas == 1:
                raise RuntimeError("fallo sintetico")
            return _autorizacion_sintetica(codigo)

    interna = _AutorizacionQueFallaUnaVez()
    adaptador = cli._AutorizacionUnaVezPorJuego(interna)
    with pytest.raises(RuntimeError):
        adaptador.ejecutar("BALOTO")
    assert adaptador.ejecutar("BALOTO").juego_codigo == "BALOTO"
    assert interna.llamadas == 2


# ---------------------------------------------------------------------------
# main(): solo lectura, revision Alembic, ROLLBACK y codigos de salida
# ---------------------------------------------------------------------------

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


def _preparar_main(monkeypatch, resolver, diagnosticador=None):
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

    def crear_consultas(sesion):
        assert orden == ["solo_lectura", "revision"]
        orden.append("consultas")
        return resolver, diagnosticador or _Diagnosticador()

    monkeypatch.setattr(cli, "_abrir_conexion", lambda: conexion)
    monkeypatch.setattr(cli, "Session", crear_sesion)
    monkeypatch.setattr(cli, "verificar_transaccion_solo_lectura", verificar_lectura)
    monkeypatch.setattr(cli, "verificar_revision_alembic", verificar_revision)
    monkeypatch.setattr(cli, "_crear_consultas", crear_consultas)
    return conexion, sesiones, orden


def test_main_verifica_solo_lectura_antes_de_evaluar_y_revierte(monkeypatch, capsys):
    resolver = _Resolver()
    conexion, sesiones, orden = _preparar_main(monkeypatch, resolver)

    assert cli.main() == cli.EXIT_OK
    salida = json.loads(capsys.readouterr().out)
    assert salida["esquema"] == "1.1"
    assert [j["codigo"] for j in salida["juegos"]] == resolver.llamadas
    assert orden == ["solo_lectura", "revision", "consultas"]
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


def test_main_diagnostico_incoherente_no_emite_json_y_revierte(monkeypatch, capsys):
    incoherente = _Diagnosticador(transformar=lambda d: diagnosticar_bloqueo(
        _autorizacion_sintetica(d.juego_codigo, total=100), DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE))
    conexion, sesiones, _ = _preparar_main(monkeypatch, _Resolver(), incoherente)

    assert cli.main() == cli.EXIT_REPORTE_INCONSISTENTE
    salida = capsys.readouterr()
    assert salida.out == ""
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


def test_codigos_de_salida_sin_cambios():
    assert (cli.EXIT_OK, cli.EXIT_FALLO_INESPERADO, cli.EXIT_FALLO_CONEXION, cli.EXIT_REVISION_ALEMBIC_INESPERADA,
            cli.EXIT_TRANSACCION_NO_SOLO_LECTURA, cli.EXIT_REPORTE_INCONSISTENTE,
            cli.EXIT_FALLO_EVALUANDO_JUEGO) == (0, 1, 2, 3, 4, 5, 6)


# ---------------------------------------------------------------------------
# Estructura: sin modulos predictivos, sin resultados, sin exposicion web
# ---------------------------------------------------------------------------

def _importados() -> set[str]:
    arbol = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    return {nodo.module for nodo in ast.walk(arbol) if isinstance(nodo, ast.ImportFrom)}


def test_script_no_importa_resultados_ni_modulos_predictivos():
    importados = _importados()
    assert "app.application.use_cases.resolver_estado_prediccion" in importados
    assert "app.application.use_cases.diagnosticar_estado_prediccion" in importados
    prohibidos = {
        "app.application.ml.inferencia", "app.application.ml.modelo",
        "app.application.ml.dataset", "app.application.ml.prediccion_bloqueada",
        "app.application.ml.features",
    }
    assert not (prohibidos & importados)
    assert not any(nombre and "resultados_historicos" in nombre for nombre in importados)


def test_ninguna_ruta_web_plantilla_ni_main_expone_la_consulta():
    raiz = Path(cli.__file__).resolve().parents[1]
    rutas = [*(raiz / "app" / "api").rglob("*.py"), raiz / "app" / "main.py"]
    for ruta in rutas:
        contenido = ruta.read_text(encoding="utf-8")
        assert "consultar_estado_prediccion" not in contenido, ruta
        assert "diagnosticar_estado_prediccion" not in contenido, ruta
    for plantilla in (raiz / "app" / "templates").rglob("*.html"):
        assert "consultar_estado_prediccion" not in plantilla.read_text(encoding="utf-8"), plantilla


# ===========================================================================
# AE-48, validada: --salida (evidencia con huella SHA-256) y --comparar
# (esquema 1.2 descriptivo). Pruebas anadidas; las anteriores no cambian.
# ===========================================================================

import hashlib  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

RAIZ_BACKEND = Path(cli.__file__).resolve().parents[1]
PATRON_HUELLA = re.compile(r"^SHA-256 ([0-9a-f]{64})  (.+)  \((\d+) bytes\)$")


def _anterior_valido(tmp_path) -> Path:
    """Archivo 1.1 real generado por el propio script con fakes sinteticos."""
    ruta = tmp_path / "evidencia-anterior.json"
    reporte = cli.construir_reporte(_Resolver(), _Diagnosticador(), "0006")
    ruta.write_bytes(cli.serializar_reporte(reporte))
    return ruta


def _huella_y_mtime(ruta: Path):
    return hashlib.sha256(ruta.read_bytes()).hexdigest(), os.stat(ruta).st_mtime_ns


def _conexion_prohibida(monkeypatch):
    def fallar():
        raise AssertionError("no deberia abrirse la conexion")

    monkeypatch.setattr(cli, "_abrir_conexion", fallar)


def test_ae48_sin_flags_salida_identica_a_ae47(monkeypatch, capsys):
    _preparar_main(monkeypatch, _Resolver())
    assert cli.main([]) == cli.EXIT_OK
    salida = capsys.readouterr()
    reporte = cli.construir_reporte(_Resolver(), _Diagnosticador(), "0006")
    assert salida.out == json.dumps(reporte, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert json.loads(salida.out)["esquema"] == "1.1"
    assert "comparacion" not in json.loads(salida.out)
    assert salida.err == ""


_PROGRAMA_SUBPROCESO = r'''
import sys
from scripts import consultar_estado_prediccion as cli
from tests.unit import test_consultar_estado_prediccion_script as t

conexion = t._ConexionFake()
cli._abrir_conexion = lambda: conexion
cli.Session = t._SesionFake
cli.verificar_transaccion_solo_lectura = lambda sesion: None
cli.verificar_revision_alembic = lambda sesion: "0006"
cli._crear_consultas = lambda sesion: (t._Resolver(), t._Diagnosticador())
codigo = cli.main(sys.argv[1:])
assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"], conexion.sentencias
sys.exit(codigo)
'''


def _ejecutar_proceso(*argumentos) -> subprocess.CompletedProcess:
    entorno = {**os.environ, "PYTHONPATH": str(RAIZ_BACKEND)}
    return subprocess.run(
        [sys.executable, "-c", _PROGRAMA_SUBPROCESO, *argumentos],
        cwd=RAIZ_BACKEND, env=entorno, capture_output=True, timeout=120,
    )


def test_ae48_salida_stdout_del_proceso_archivo_y_huella_coinciden(tmp_path):
    destino = tmp_path / "evidencia.json"
    proceso = _ejecutar_proceso("--salida", str(destino))

    assert proceso.returncode == cli.EXIT_OK, proceso.stderr
    guardado = destino.read_bytes()
    assert proceso.stdout == guardado
    assert b"\r" not in guardado
    lineas_err = proceso.stderr.decode("utf-8").strip().splitlines()
    assert len(lineas_err) == 1
    coincidencia = PATRON_HUELLA.match(lineas_err[0])
    assert coincidencia, lineas_err
    assert coincidencia.group(1) == hashlib.sha256(guardado).hexdigest()
    assert int(coincidencia.group(3)) == len(guardado)
    reporte = json.loads(proceso.stdout.decode("utf-8"))
    assert reporte["esquema"] == "1.1"
    assert coincidencia.group(1).encode() not in proceso.stdout


def test_ae48_salida_en_proceso_mismos_bytes(monkeypatch, capsysbinary, tmp_path):
    _preparar_main(monkeypatch, _Resolver())
    destino = tmp_path / "evidencia.json"
    assert cli.main(["--salida", str(destino)]) == cli.EXIT_OK
    capturado = capsysbinary.readouterr()
    assert capturado.out == destino.read_bytes()
    assert hashlib.sha256(destino.read_bytes()).hexdigest().encode() in capturado.err


def test_ae48_comparar_produce_esquema_1_2_descriptivo(monkeypatch, capsys, tmp_path):
    anterior = _anterior_valido(tmp_path)
    antes = _huella_y_mtime(anterior)
    _preparar_main(monkeypatch, _Resolver())

    assert cli.main(["--comparar", str(anterior)]) == cli.EXIT_OK
    reporte = json.loads(capsys.readouterr().out)
    assert reporte["esquema"] == "1.2"
    assert set(reporte) == {"esquema", "alembic_revision", "juegos", "comparacion"}
    comparacion = reporte["comparacion"]
    assert comparacion["esquema_anterior"] == "1.1"
    assert comparacion["nota"] == cli.comparacion_estado_prediccion.NOTA_COMPARACION
    assert [j["variacion_sorteos_nuevos"] for j in comparacion["juegos"]] == [0, 0]
    assert all(j["desbloqueable"] is False for j in reporte["juegos"])
    assert _huella_y_mtime(anterior) == antes


def test_ae48_comparar_no_copia_la_comparacion_de_un_anterior_1_2(monkeypatch, capsys, tmp_path):
    base = cli.construir_reporte(_Resolver(), _Diagnosticador(), "0006")
    anterior_1_2 = cli.anadir_comparacion(base, base)
    anterior_1_2["comparacion"]["nota"] = cli.comparacion_estado_prediccion.NOTA_COMPARACION
    ruta = tmp_path / "anterior-1-2.json"
    ruta.write_bytes(cli.serializar_reporte(anterior_1_2))
    _preparar_main(monkeypatch, _Resolver())

    assert cli.main(["--comparar", str(ruta)]) == cli.EXIT_OK
    reporte = json.loads(capsys.readouterr().out)
    assert reporte["comparacion"]["esquema_anterior"] == "1.2"
    assert "comparacion" not in json.dumps(reporte["comparacion"])


@pytest.mark.parametrize("contenido", [
    b"{no es json",
    b'{"esquema": "1.1", "alembic_revision": "0006", "juegos": []}',
    b'{"esquema": "9.9"}',
])
def test_ae48_anterior_invalido_codigo_7_sin_abrir_conexion(monkeypatch, capsys, tmp_path, contenido):
    ruta = tmp_path / "anterior.json"
    ruta.write_bytes(contenido)
    _conexion_prohibida(monkeypatch)
    assert cli.main(["--comparar", str(ruta)]) == cli.EXIT_ARCHIVO_ANTERIOR_INVALIDO == 7
    salida = capsys.readouterr()
    assert salida.out == "" and "anterior" in salida.err.lower()
    assert ruta.read_bytes() == contenido


def test_ae48_anterior_con_desbloqueable_true_se_rechaza(monkeypatch, tmp_path):
    reporte = cli.construir_reporte(_Resolver(), _Diagnosticador(), "0006")
    reporte["juegos"][0]["desbloqueable"] = True
    ruta = tmp_path / "anterior.json"
    ruta.write_bytes(cli.serializar_reporte(reporte))
    _conexion_prohibida(monkeypatch)
    assert cli.main(["--comparar", str(ruta)]) == cli.EXIT_ARCHIVO_ANTERIOR_INVALIDO


def _casos_misma_ruta(tmp_path, anterior: Path):
    casos = {
        "literal": str(anterior),
        "relativa_y_absoluta": os.path.relpath(anterior),
        "con_punto_punto": os.path.join(str(tmp_path), "x", "..", anterior.name),
    }
    enlace_simbolico = tmp_path / "enlace-simbolico.json"
    try:
        os.symlink(anterior, enlace_simbolico)
        casos["enlace_simbolico"] = str(enlace_simbolico)
    except (OSError, NotImplementedError):
        pass
    enlace_duro = tmp_path / "enlace-duro.json"
    try:
        os.link(anterior, enlace_duro)
        casos["enlace_duro"] = str(enlace_duro)
    except (OSError, NotImplementedError):
        pass
    return casos


def test_ae48_salida_igual_a_comparar_codigo_9_sin_modificar_el_anterior(monkeypatch, capsys, tmp_path):
    anterior = _anterior_valido(tmp_path)
    casos = _casos_misma_ruta(tmp_path, anterior)
    assert {"literal", "relativa_y_absoluta", "con_punto_punto"} <= set(casos)
    _conexion_prohibida(monkeypatch)
    for nombre, salida in casos.items():
        antes = _huella_y_mtime(anterior)
        assert cli.main(["--comparar", str(anterior), "--salida", salida]) == cli.EXIT_RUTA_SALIDA_NO_PERMITIDA == 9, nombre
        capturado = capsys.readouterr()
        assert capturado.out == "", nombre
        assert _huella_y_mtime(anterior) == antes, nombre


def test_ae48_salida_existente_o_directorio_inexistente_codigo_9(monkeypatch, capsys, tmp_path):
    existente = tmp_path / "ya-existe.json"
    existente.write_bytes(b"evidencia previa")
    _conexion_prohibida(monkeypatch)
    assert cli.main(["--salida", str(existente)]) == cli.EXIT_RUTA_SALIDA_NO_PERMITIDA
    assert existente.read_bytes() == b"evidencia previa"
    assert cli.main(["--salida", str(tmp_path / "no-existe" / "x.json")]) == cli.EXIT_RUTA_SALIDA_NO_PERMITIDA
    assert capsys.readouterr().out == ""


def test_ae48_destino_que_aparece_antes_de_publicar_codigo_8(monkeypatch, capsys, tmp_path):
    destino = tmp_path / "evidencia.json"
    _preparar_main(monkeypatch, _Resolver())
    modulo = cli.comparacion_estado_prediccion
    publicar_real = modulo._publicar_exclusivo

    def intruso_y_publicar(temporal, ruta_destino):
        Path(ruta_destino).write_bytes(b"escrito por otro proceso")
        publicar_real(temporal, ruta_destino)

    monkeypatch.setattr(modulo, "_publicar_exclusivo", intruso_y_publicar)
    assert cli.main(["--salida", str(destino)]) == cli.EXIT_FALLO_ESCRITURA_SALIDA == 8
    salida = capsys.readouterr()
    assert salida.out == ""
    assert destino.read_bytes() == b"escrito por otro proceso"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["evidencia.json"]


def test_ae48_rollback_y_orden_se_conservan_con_flags(monkeypatch, capsys, tmp_path):
    anterior = _anterior_valido(tmp_path)
    conexion, sesiones, orden = _preparar_main(monkeypatch, _Resolver())
    assert cli.main(["--comparar", str(anterior), "--salida", str(tmp_path / "nueva.json")]) == cli.EXIT_OK
    assert orden == ["solo_lectura", "revision", "consultas"]
    assert conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"]
    assert conexion.cerrada and sesiones[0].cerrada
    capsys.readouterr()


def test_ae48_codigos_nuevos_y_anteriores():
    assert (cli.EXIT_ARCHIVO_ANTERIOR_INVALIDO, cli.EXIT_FALLO_ESCRITURA_SALIDA,
            cli.EXIT_RUTA_SALIDA_NO_PERMITIDA) == (7, 8, 9)
    assert cli.EXIT_REPORTE_INCONSISTENTE == 5 and cli.EXIT_FALLO_EVALUANDO_JUEGO == 6


def test_ae48_anterior_1_2_con_misma_revision_incoherente_codigo_7(monkeypatch, capsys, tmp_path):
    base = cli.construir_reporte(_Resolver(), _Diagnosticador(), "0006")
    anterior_1_2 = cli.anadir_comparacion(base, base)
    assert anterior_1_2["comparacion"]["misma_revision_alembic"] is True
    anterior_1_2["comparacion"]["revision_alembic_anterior"] = "0005"
    ruta = tmp_path / "anterior-1-2.json"
    ruta.write_bytes(cli.serializar_reporte(anterior_1_2))
    _conexion_prohibida(monkeypatch)

    assert cli.main(["--comparar", str(ruta)]) == cli.EXIT_ARCHIVO_ANTERIOR_INVALIDO == 7
    salida = capsys.readouterr()
    assert salida.out == "" and "misma_revision_alembic" in salida.err


def test_ae48_fallo_al_releer_tras_publicar_codigo_8_sin_json_ni_traceback(monkeypatch, capsys, tmp_path):
    destino = tmp_path / "evidencia.json"
    _preparar_main(monkeypatch, _Resolver())
    modulo = cli.comparacion_estado_prediccion
    publicar_real = modulo._publicar_exclusivo

    def open_que_falla(*args, **kwargs):
        raise OSError(5, "fallo sintetico de relectura")

    def publicar_y_romper_la_relectura(temporal, ruta_destino):
        publicar_real(temporal, ruta_destino)
        monkeypatch.setattr(modulo, "open", open_que_falla, raising=False)

    monkeypatch.setattr(modulo, "_publicar_exclusivo", publicar_y_romper_la_relectura)
    assert cli.main(["--salida", str(destino)]) == cli.EXIT_FALLO_ESCRITURA_SALIDA == 8
    salida = capsys.readouterr()
    assert salida.out == ""
    assert "Traceback" not in salida.err and "releer" in salida.err
    assert "SHA-256" not in salida.err
    assert destino.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["evidencia.json"]
