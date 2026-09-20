"""Tests de `DisponibilidadHoldoutRepositorySQLAlchemy` -Etapa AE-40.

Mismo precedente honesto que `test_resultados_historicos_repository.py`:
este sandbox no tiene PostgreSQL real disponible. En vez de simular el
repositorio, se COMPILA la sentencia SQL real generada por la unica
funcion de PRODUCCION que la construye
(`construir_consulta_disponibilidad_holdout`, importada directamente
de `app.infrastructure.repositories.disponibilidad_holdout_repository_sqlalchemy`
-nunca reconstruida aqui) usando `sqlalchemy` real, que si esta
instalado en este entorno, y se inspecciona el texto SQL resultante.
Una prueba adicional demuestra, con una sesion fake que captura el
objeto recibido en `execute`, que el metodo del repositorio ejecuta
exactamente esa misma sentencia -nunca una copia paralela- por lo
que estas pruebas fallarian genuinamente si la consulta de
produccion cambiara o quedara defectuosa."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.interfaces.disponibilidad_holdout_repository import DisponibilidadHoldoutRepository
from app.application.ml.tipos import ResumenDisponibilidadHoldout
from app.infrastructure.repositories.disponibilidad_holdout_repository_sqlalchemy import (
    DisponibilidadHoldoutRepositorySQLAlchemy,
    construir_consulta_disponibilidad_holdout,
)


def _compilar(juego_id, desde_numero_sorteo=2706) -> str:
    stmt = construir_consulta_disponibilidad_holdout(juego_id, desde_numero_sorteo)
    return str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()


class TestConsultaSQLRealDeProduccion:
    """Compila la UNICA funcion de produccion que construye la
    sentencia -nunca una reconstruccion paralela dentro de las
    pruebas."""

    def test_proyecta_solo_agregados(self):
        sql = _compilar(uuid4())
        assert "count(" in sql
        assert "min(" in sql
        assert "max(" in sql

    def test_filtra_por_juego(self):
        juego_id = uuid4()
        sql = _compilar(juego_id)
        assert "juego_id" in sql
        assert str(juego_id).replace("-", "") in sql.replace("-", "")

    def test_filtra_numero_sorteo_mayor_igual_2706(self):
        sql = _compilar(uuid4(), desde_numero_sorteo=2706)
        assert "numero_sorteo >= 2706" in sql

    def test_no_proyecta_columnas_con_numeros_ganadores(self):
        sql = _compilar(uuid4())
        for columna_prohibida in ("numeros", "superbalota", "color", "fecha", "dia_semana"):
            assert columna_prohibida not in sql

    def test_no_hace_join_con_tablas_de_resultado(self):
        sql = _compilar(uuid4())
        assert "join" not in sql

    def test_consulta_es_de_solo_lectura_select_unicamente(self):
        sql = _compilar(uuid4())
        assert sql.strip().startswith("select")
        for palabra_prohibida in ("insert", "update", "delete", "commit"):
            assert palabra_prohibida not in sql

    def test_implementacion_no_define_metodos_de_escritura(self):
        import inspect
        metodos = [n for n, _ in inspect.getmembers(DisponibilidadHoldoutRepositorySQLAlchemy, predicate=inspect.isfunction)]
        assert not any(m in metodos for m in ("guardar", "insertar", "actualizar", "eliminar", "commit", "flush"))

    def test_implementacion_no_importa_modulos_ml_innecesarios(self):
        import ast as ast_modulo
        import pathlib
        ruta = pathlib.Path("app/infrastructure/repositories/disponibilidad_holdout_repository_sqlalchemy.py")
        arbol = ast_modulo.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast_modulo.walk(arbol):
            if isinstance(nodo, ast_modulo.Import):
                for alias in nodo.names:
                    assert not alias.name.startswith("sklearn")
            elif isinstance(nodo, ast_modulo.ImportFrom):
                if nodo.module:
                    assert not nodo.module.startswith("sklearn")


class _FakeSessionCapturaStatement:
    """Sesion fake que captura el objeto `Select` que
    `obtener_resumen_disponibilidad` le pasa a `execute` -nunca
    ejecuta SQL real, nunca se conecta a PostgreSQL."""

    def __init__(self, fila_resultado):
        self._fila = fila_resultado
        self.statement_capturado = None

    def execute(self, stmt):
        self.statement_capturado = stmt

        class _Resultado:
            def __init__(self, fila):
                self._fila = fila
            def one(self):
                return self._fila

        return _Resultado(self._fila)


class TestElMetodoDelRepositorioUsaLaFuncionDeProduccion:
    def test_statement_ejecutado_es_identico_al_construido_por_la_funcion_de_produccion(self):
        juego_id = uuid4()
        fake_session = _FakeSessionCapturaStatement((5, 5, 2706, 2710))
        repo = DisponibilidadHoldoutRepositorySQLAlchemy(fake_session)
        repo.obtener_resumen_disponibilidad(juego_id, "BALOTO", 2706)

        stmt_esperado = construir_consulta_disponibilidad_holdout(juego_id, 2706)
        sql_capturado = str(fake_session.statement_capturado.compile(compile_kwargs={"literal_binds": True}))
        sql_esperado = str(stmt_esperado.compile(compile_kwargs={"literal_binds": True}))
        assert sql_capturado == sql_esperado

    def test_metodo_devuelve_conteos_minimo_y_maximo_correctos(self):
        juego_id = uuid4()
        fake_session = _FakeSessionCapturaStatement((45, 45, 2706, 2750))
        repo = DisponibilidadHoldoutRepositorySQLAlchemy(fake_session)
        resumen = repo.obtener_resumen_disponibilidad(juego_id, "BALOTO", 2706)
        assert resumen.total_registros == 45
        assert resumen.total_numeros_distintos == 45
        assert resumen.numero_sorteo_minimo == 2706
        assert resumen.numero_sorteo_maximo == 2750
        assert resumen.juego_codigo == "BALOTO"

    def test_metodo_maneja_ausencia_de_filas(self):
        juego_id = uuid4()
        fake_session = _FakeSessionCapturaStatement((0, 0, None, None))
        repo = DisponibilidadHoldoutRepositorySQLAlchemy(fake_session)
        resumen = repo.obtener_resumen_disponibilidad(juego_id, "BALOTO", 2706)
        assert resumen.total_registros == 0
        assert resumen.numero_sorteo_minimo is None
        assert resumen.numero_sorteo_maximo is None


class _FakeDisponibilidadHoldoutRepository(DisponibilidadHoldoutRepository):
    """Fake que implementa el puerto real -verifica el CONTRATO
    completo (agregacion, tipos devueltos) independientemente de
    SQLAlchemy."""

    def __init__(self, historico_por_juego: dict):
        self._historico = historico_por_juego

    def obtener_resumen_disponibilidad(self, juego_id, codigo_juego, desde_numero_sorteo):
        numeros = sorted(n for n in self._historico.get(juego_id, []) if n >= desde_numero_sorteo)
        total = len(numeros)
        return ResumenDisponibilidadHoldout(
            juego_codigo=codigo_juego, desde_numero_sorteo=desde_numero_sorteo,
            total_registros=total, total_numeros_distintos=len(set(numeros)),
            numero_sorteo_minimo=min(numeros) if numeros else None,
            numero_sorteo_maximo=max(numeros) if numeros else None,
        )


class TestContratoDelPuertoContraFake:
    def test_agregacion_correcta_con_datos_contiguos(self):
        juego_id = uuid4()
        historico = {juego_id: list(range(2706, 2756))}
        repo = _FakeDisponibilidadHoldoutRepository(historico)
        resumen = repo.obtener_resumen_disponibilidad(juego_id, "BALOTO", 2706)
        assert resumen.total_registros == 50
        assert resumen.total_numeros_distintos == 50
        assert resumen.numero_sorteo_minimo == 2706
        assert resumen.numero_sorteo_maximo == 2755

    def test_agregacion_correcta_sin_datos(self):
        juego_id = uuid4()
        repo = _FakeDisponibilidadHoldoutRepository({juego_id: []})
        resumen = repo.obtener_resumen_disponibilidad(juego_id, "BALOTO", 2706)
        assert resumen.total_registros == 0
        assert resumen.numero_sorteo_minimo is None
        assert resumen.numero_sorteo_maximo is None

    def test_filtro_desde_numero_sorteo_excluye_anteriores(self):
        juego_id = uuid4()
        historico = {juego_id: [2591, 2600, 2705] + list(range(2706, 2726))}
        repo = _FakeDisponibilidadHoldoutRepository(historico)
        resumen = repo.obtener_resumen_disponibilidad(juego_id, "BALOTO", 2706)
        assert resumen.total_registros == 20
        assert resumen.numero_sorteo_minimo == 2706
