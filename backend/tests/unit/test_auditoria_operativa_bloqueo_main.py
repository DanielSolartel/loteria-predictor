"""`main()` de extremo a extremo con dobles de infraestructura -Etapa AE-42 (correccion).

Nunca se conecta a PostgreSQL: se sustituyen el motor, la conexion, la
sesion y, segun la prueba, los repositorios o el caso de uso de AE-41.
Las verificaciones reales de `transaction_read_only` y de revision
Alembic (derivada del directorio `alembic/` local) si se ejecutan."""
from __future__ import annotations

import json
from uuid import uuid4

from app.application.ml.tipos import (
    EstadoAutorizacionOperativaML,
    EstadoElegibilidadReaperturaML,
    ReporteAutorizacionOperativaML,
    ReporteElegibilidadReaperturaML,
    ResumenDisponibilidadHoldout,
)
from app.domain.entities.juego import Juego
from scripts import auditoria_operativa_bloqueo as script

REPO_JUEGO = "app.infrastructure.repositories.juego_repository_sqlalchemy.JuegoRepositorySQLAlchemy"
REPO_DISP = (
    "app.infrastructure.repositories.disponibilidad_holdout_repository_sqlalchemy."
    "DisponibilidadHoldoutRepositorySQLAlchemy"
)


class _Resultado:
    def __init__(self, valor):
        self._valor = valor

    def scalar(self):
        return self._valor


class _FakeConexion:
    def __init__(self):
        self.sentencias = []
        self.cerrada = False

    def execute(self, stmt):
        self.sentencias.append(str(stmt))
        return _Resultado(None)

    def close(self):
        self.cerrada = True


class _FakeEngine:
    def __init__(self):
        self.conexion = _FakeConexion()

    def connect(self):
        return self.conexion


def _preparar(monkeypatch, revision="0006"):
    """Sustituye motor y sesion; la sesion solo responde las dos consultas
    auxiliares de metadatos y falla ante cualquier otra."""
    engine = _FakeEngine()
    consultas = []

    class _FakeSession:
        def __init__(self, bind=None):
            self.bind = bind

        def execute(self, stmt):
            sql = str(stmt)
            consultas.append(sql)
            if "transaction_read_only" in sql:
                return _Resultado("on")
            if "alembic_version" in sql:
                return _Resultado(revision)
            raise AssertionError(f"consulta no esperada en la sesion: {sql}")

        def close(self):
            pass

    monkeypatch.setattr("app.infrastructure.db.session.engine", engine)
    monkeypatch.setattr(script, "Session", _FakeSession)
    return engine, consultas


def _juego(codigo):
    return Juego(
        id=uuid4(), codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43, cantidad_numeros=5,
        tiene_superbalota=True, superbalota_min=1, superbalota_max=16, tiene_color=False,
        permite_repeticion=False, activo=True,
    )


class _FakeJuegoRepo:
    def __init__(self, session):
        self._juegos = {c: _juego(c) for c in ("BALOTO", "BALOTO_REVANCHA")}

    def obtener_por_codigo(self, codigo):
        return self._juegos.get(codigo)


def _fake_disponibilidad(totales):
    class _FakeDisponibilidad:
        def __init__(self, session):
            pass

        def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
            total, minimo, maximo = totales[codigo_juego]
            return ResumenDisponibilidadHoldout(
                juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
                total_registros=total, total_numeros_distintos=total,
                numero_sorteo_minimo=minimo, numero_sorteo_maximo=maximo,
            )

    return _FakeDisponibilidad


def _elegibilidad(juego, estado):
    return ReporteElegibilidadReaperturaML(
        juego_codigo=juego, estado=estado, proximo_holdout_inicio=2706,
        minimo_sorteos_nuevos_requeridos=100, total_sorteos_nuevos=0,
        numero_sorteo_minimo=None, numero_sorteo_maximo=None,
        numero_sorteo_objetivo_minimo=2805, numeracion_contigua=True,
    )


def _caso_autorizacion_falso(fabrica_reporte):
    class _Caso:
        def __init__(self, caso_uso_elegibilidad):
            pass

        def ejecutar(self, codigo_juego):
            return fabrica_reporte(codigo_juego)

    return _Caso


class TestMainExtremoAExtremo:
    def test_autorizado_y_numeracion_invalida_sale_0_con_bloqueo_global(self, monkeypatch, tmp_path):
        # Casos de uso REALES de AE-40/41; solo los repositorios son dobles.
        # BALOTO: 2706..2805 contiguo -> autorizado; REVANCHA: hueco -> numeracion invalida.
        engine, consultas = _preparar(monkeypatch)
        monkeypatch.setattr(REPO_JUEGO, _FakeJuegoRepo)
        monkeypatch.setattr(REPO_DISP, _fake_disponibilidad(
            {"BALOTO": (100, 2706, 2805), "BALOTO_REVANCHA": (99, 2706, 2805)}
        ))
        salida = tmp_path / "ae42.json"
        assert script.main(["--salida", str(salida)]) == script.EXIT_OK
        reporte = json.loads(salida.read_text(encoding="utf-8"))
        assert reporte["estado_global"] == "bloqueado_numeracion_invalida"
        assert reporte["autorizacion_para_prerregistro_detectada"] is True
        assert reporte["auditoria_correcta"] is True
        assert reporte["resultados"]["BALOTO"]["estado"] == "autorizado_para_prerregistro"
        assert reporte["resultados"]["BALOTO_REVANCHA"]["estado"] == "bloqueado_numeracion_invalida"
        assert engine.conexion.sentencias == ["BEGIN TRANSACTION READ ONLY", "ROLLBACK"]
        assert engine.conexion.cerrada is True
        assert consultas == ["SHOW transaction_read_only", "SELECT version_num FROM alembic_version"]

    def test_elegibilidad_anidada_de_otro_juego_sale_5_sin_json(self, monkeypatch, tmp_path, capsys):
        engine, _ = _preparar(monkeypatch)

        def fabrica(codigo_juego):
            otro = "BALOTO_REVANCHA" if codigo_juego == "BALOTO" else "BALOTO"
            return ReporteAutorizacionOperativaML(
                juego_codigo=codigo_juego, estado=EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES,
                motivo="x", reporte_elegibilidad=_elegibilidad(
                    otro, EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES,
                ),
            )

        monkeypatch.setattr(script, "EvaluarAutorizacionOperativaML", _caso_autorizacion_falso(fabrica))
        salida = tmp_path / "ae42.json"
        assert script.main(["--salida", str(salida)]) == script.EXIT_REPORTE_INCONSISTENTE
        assert list(tmp_path.iterdir()) == []
        assert "ROLLBACK" in engine.conexion.sentencias
        assert not any("COMMIT" in s.upper() for s in engine.conexion.sentencias)
        assert "codigo 5" in capsys.readouterr().err

    def test_estado_exterior_incoherente_con_ae40_sale_5_sin_json(self, monkeypatch, tmp_path):
        engine, _ = _preparar(monkeypatch)

        def fabrica(codigo_juego):
            return ReporteAutorizacionOperativaML(
                juego_codigo=codigo_juego, estado=EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO,
                motivo="x", reporte_elegibilidad=_elegibilidad(
                    codigo_juego, EstadoElegibilidadReaperturaML.NO_ELEGIBLE_DATOS_INSUFICIENTES,
                ),
            )

        monkeypatch.setattr(script, "EvaluarAutorizacionOperativaML", _caso_autorizacion_falso(fabrica))
        salida = tmp_path / "ae42.json"
        assert script.main(["--salida", str(salida)]) == script.EXIT_REPORTE_INCONSISTENTE
        assert list(tmp_path.iterdir()) == []
        assert "ROLLBACK" in engine.conexion.sentencias

    def test_revision_alembic_incompatible_sale_3_sin_json(self, monkeypatch, tmp_path):
        engine, consultas = _preparar(monkeypatch, revision="0005")
        salida = tmp_path / "ae42.json"
        assert script.main(["--salida", str(salida)]) == script.EXIT_REVISION_ALEMBIC_INESPERADA
        assert list(tmp_path.iterdir()) == []
        assert "ROLLBACK" in engine.conexion.sentencias
        assert consultas == ["SHOW transaction_read_only", "SELECT version_num FROM alembic_version"]


class TestRevisionAlembicEsperada:
    def test_revision_esperada_derivada_de_alembic_local(self):
        # Refleja el conjunto actual de migraciones (0001..0006); una
        # migracion nueva exigiria revisar esta prueba deliberadamente.
        assert script.obtener_revision_alembic_esperada() == "0006"
