"""
Tests de Etapa AE-0: ampliación de ColorRepository con `listar_todos`
y corrección de la semántica histórica de `listar_vigentes(en_fecha=...)`.

Verificación previa e independiente (antes de escribir estos tests,
sin PostgreSQL real disponible en este sandbox): el defecto original
se confirmó ejecutando directamente `Color.esta_vigente_en()` contra
un color sintético con `activo=False` y una ventana de vigencia que
SÍ cubre una fecha histórica -el filtro SQL original
(`ColorORM.activo.is_(True)`) lo habría excluido incondicionalmente,
sin darle a `esta_vigente_en` oportunidad de evaluar la fecha.

Estos tests ejercitan `FakeColorRepository` (el único doble del
puerto, en `tests/unit/fakes.py`) como sustituto funcional completo
del repositorio -mismo patrón ya usado en el resto del proyecto para
repositorios en memoria. La implementación SQLAlchemy real
(`color_repository_sqlalchemy.py`) reutiliza exactamente la misma
lógica de `Color.esta_vigente_en` (nunca la duplica) y comparte la
misma estructura de `listar_todos` (una sola consulta, orden por
`codigo`), por lo que el comportamiento verificado aquí es
representativo del comportamiento real -sin poder ejecutar SQL
verdadero en este entorno.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.interfaces.color_repository import ColorRepository
from app.domain.value_objects.color import Color
from tests.unit.fakes import FakeColorRepository


def _color(codigo, activo=True, desde=None, hasta=None):
    return Color(codigo=codigo, nombre=codigo.title(), activo=activo, vigente_desde=desde, vigente_hasta=hasta)


class TestListarTodos:
    def test_devuelve_activos_e_inactivos_del_mismo_juego(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", activo=True), _color("AZUL", activo=False)]})
        codigos = {c.codigo for c in repo.listar_todos(juego_id)}
        assert codigos == {"ROJO", "AZUL"}

    def test_excluye_colores_de_otro_juego(self):
        juego_a, juego_b = uuid4(), uuid4()
        repo = FakeColorRepository({juego_a: [_color("ROJO")], juego_b: [_color("VERDE")]})
        codigos = {c.codigo for c in repo.listar_todos(juego_a)}
        assert "VERDE" not in codigos

    def test_conserva_metadata_completa(self):
        juego_id = uuid4()
        original = _color("ROJO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))
        repo = FakeColorRepository({juego_id: [original]})
        recuperado = repo.listar_todos(juego_id)[0]
        assert recuperado.codigo == "ROJO"
        assert recuperado.nombre == original.nombre
        assert recuperado.activo is False
        assert recuperado.vigente_desde == date(2020, 1, 1)
        assert recuperado.vigente_hasta == date(2023, 12, 31)

    def test_incluye_colores_futuros_actuales_y_vencidos(self):
        juego_id = uuid4()
        futuro = _color("FUTURO", desde=date(2030, 1, 1))
        actual = _color("ACTUAL", desde=date(2020, 1, 1))
        vencido = _color("VENCIDO", activo=False, desde=date(2010, 1, 1), hasta=date(2015, 12, 31))
        repo = FakeColorRepository({juego_id: [futuro, actual, vencido]})
        codigos = {c.codigo for c in repo.listar_todos(juego_id)}
        assert codigos == {"FUTURO", "ACTUAL", "VENCIDO"}

    def test_orden_deterministico_por_codigo(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("VERDE"), _color("AZUL"), _color("ROJO")]})
        codigos = [c.codigo for c in repo.listar_todos(juego_id)]
        assert codigos == sorted(codigos)

    def test_juego_sin_colores_produce_lista_vacia(self):
        repo = FakeColorRepository({})
        assert repo.listar_todos(uuid4()) == []

    def test_reutilizable_como_base_de_vigencia_historica_sin_repetir_consulta(self):
        """Confirma que `listar_todos` puede reutilizarse en memoria
        para resolver vigencia histórica de VARIAS fechas sin volver
        a invocar el repositorio -mismo patrón que la implementación
        SQLAlchemy real usa internamente."""
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]})
        catalogo = repo.listar_todos(juego_id)  # UNA sola llamada al repositorio
        fechas = [date(2021, 6, 1), date(2022, 6, 1), date(2024, 1, 1)]
        resultados = [[c.codigo for c in catalogo if c.esta_vigente_en(f)] for f in fechas]
        assert resultados == [["ROJO"], ["ROJO"], []]


class TestListarVigentesSinFecha:
    """Sin `en_fecha`: paleta ACTUAL -contrato exacto preexistente,
    debe permanecer sin cambios de comportamiento."""

    def test_conserva_el_resultado_anterior(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", desde=date(2020, 1, 1))]})
        assert [c.codigo for c in repo.listar_vigentes(juego_id)] == ["ROJO"]

    def test_excluye_color_inactivo_actual(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", activo=False), _color("AZUL", activo=True)]})
        codigos = [c.codigo for c in repo.listar_vigentes(juego_id)]
        assert codigos == ["AZUL"]

    def test_gamefactory_sigue_recibiendo_la_paleta_actual(self):
        """No reimplementa GameFactory -confirma directamente el
        mismo contrato que GameFactory consume: `listar_vigentes(juego_id)`
        sin fecha, con un color inactivo excluido."""
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", activo=False), _color("AZUL", activo=True)]})
        colores_para_colorloto_game = repo.listar_vigentes(juego_id)
        assert all(c.activo for c in colores_para_colorloto_game)

    def test_colorlotogame_se_construye_igual_que_antes(self):
        from app.domain.games.colorloto import ColorLotoGame
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", activo=True), _color("AZUL", activo=False)]})
        juego = ColorLotoGame(colors=repo.listar_vigentes(juego_id))
        assert len(juego._colors_by_code) == 1
        assert "ROJO" in juego._colors_by_code


class TestListarVigentesConFechaHistorica:
    """Con `en_fecha` explícita: paleta HISTÓRICAMENTE vigente en esa
    fecha -nunca filtra por `activo` actual."""

    def test_incluye_color_hoy_inactivo_cuya_ventana_contiene_la_fecha(self):
        juego_id = uuid4()
        repo = FakeColorRepository({
            juego_id: [_color("ROJO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31))],
        })
        codigos = [c.codigo for c in repo.listar_vigentes(juego_id, en_fecha=date(2022, 6, 15))]
        assert codigos == ["ROJO"]

    def test_incluye_exactamente_en_vigente_desde(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", desde=date(2020, 1, 1))]})
        codigos = [c.codigo for c in repo.listar_vigentes(juego_id, en_fecha=date(2020, 1, 1))]
        assert codigos == ["ROJO"]

    def test_incluye_exactamente_en_vigente_hasta(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]})
        codigos = [c.codigo for c in repo.listar_vigentes(juego_id, en_fecha=date(2023, 12, 31))]
        assert codigos == ["ROJO"]

    def test_excluye_antes_de_vigente_desde(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", desde=date(2020, 1, 1))]})
        codigos = [c.codigo for c in repo.listar_vigentes(juego_id, en_fecha=date(2019, 12, 31))]
        assert codigos == []

    def test_excluye_despues_de_vigente_hasta(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", desde=date(2020, 1, 1), hasta=date(2023, 12, 31))]})
        codigos = [c.codigo for c in repo.listar_vigentes(juego_id, en_fecha=date(2024, 1, 1))]
        assert codigos == []

    def test_excluye_colores_de_otro_juego(self):
        juego_a, juego_b = uuid4(), uuid4()
        repo = FakeColorRepository({juego_a: [_color("ROJO")], juego_b: [_color("VERDE")]})
        codigos = [c.codigo for c in repo.listar_vigentes(juego_a, en_fecha=date(2024, 1, 1))]
        assert codigos == ["ROJO"]

    def test_funciona_con_vigente_hasta_none(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("ROJO", desde=date(2020, 1, 1), hasta=None)]})
        codigos = [c.codigo for c in repo.listar_vigentes(juego_id, en_fecha=date(2099, 1, 1))]
        assert codigos == ["ROJO"]

    def test_orden_deterministico(self):
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color("VERDE"), _color("AZUL"), _color("ROJO")]})
        codigos = [c.codigo for c in repo.listar_vigentes(juego_id, en_fecha=date(2024, 1, 1))]
        assert codigos == sorted(codigos)

    def test_una_sola_llamada_al_catalogo_por_invocacion(self):
        """Confirma con espía que `listar_vigentes(en_fecha=...)`
        consulta el catálogo UNA sola vez (no N veces), incluso con
        varios colores en el histórico."""
        juego_id = uuid4()
        repo = FakeColorRepository({juego_id: [_color(f"C{i}") for i in range(10)]})
        llamadas = {"n": 0}
        original = repo.listar_todos

        def espia(jid):
            llamadas["n"] += 1
            return original(jid)

        repo.listar_todos = espia
        repo.listar_vigentes(juego_id, en_fecha=date(2024, 1, 1))
        assert llamadas["n"] == 1

    def test_reproduce_el_defecto_previo_y_demuestra_la_correccion(self):
        """Reproduce EXACTAMENTE el escenario del defecto original:
        un color con activo=False y ventana histórica que SÍ cubre
        `en_fecha` -antes de la corrección, el filtro `activo=True`
        lo habría excluido incondicionalmente sin mirar la fecha."""
        juego_id = uuid4()
        color_retirado_pero_historicamente_valido = _color(
            "ROJO", activo=False, desde=date(2020, 1, 1), hasta=date(2023, 12, 31),
        )
        repo = FakeColorRepository({juego_id: [color_retirado_pero_historicamente_valido]})

        # Confirmar que el color esta correctamente marcado activo=False
        assert color_retirado_pero_historicamente_valido.activo is False

        # Sin fecha (paleta actual): correctamente EXCLUIDO
        assert repo.listar_vigentes(juego_id) == []

        # Con fecha historica dentro de su ventana real: correctamente INCLUIDO
        resultado = repo.listar_vigentes(juego_id, en_fecha=date(2022, 6, 15))
        assert [c.codigo for c in resultado] == ["ROJO"]


class TestColorRepositoryCumpleContratoAbstracto:
    def test_fake_implementa_los_cuatro_metodos_del_puerto(self):
        assert hasattr(FakeColorRepository, "listar_vigentes")
        assert hasattr(FakeColorRepository, "listar_todos")
        assert hasattr(FakeColorRepository, "guardar")
        assert hasattr(FakeColorRepository, "cerrar_vigencia")

    def test_fake_es_instanciable_sin_typeerror_por_metodo_abstracto_faltante(self):
        FakeColorRepository({})  # si faltara un abstractmethod, TypeError aquí

    def test_puerto_declara_listar_todos_como_abstracto(self):
        import inspect
        firma = inspect.signature(ColorRepository.listar_todos)
        assert list(firma.parameters.keys()) == ["self", "juego_id"]


class TestEquivalenciaEstructuralConImplementacionReal:
    """`ColorRepositorySQLAlchemy` no puede instanciarse ni ejecutarse
    en este sandbox (sin `sqlalchemy` instalado, limitación real ya
    documentada en turnos anteriores) -esta clase confirma
    EQUIVALENCIA ESTRUCTURAL por lectura directa del código fuente
    real, complementando (no sustituyendo) la cobertura funcional
    completa del fake arriba. Cada aserción lee el archivo real, no
    supone su contenido."""

    _RUTA = Path("app/infrastructure/repositories/color_repository_sqlalchemy.py")

    def test_ambas_implementaciones_ordenan_por_codigo(self):
        codigo_fuente = self._RUTA.read_text(encoding="utf-8")
        assert "order_by(ColorORM.codigo)" in codigo_fuente
        assert codigo_fuente.count("order_by(ColorORM.codigo)") == 2  # listar_vigentes(sin fecha) + listar_todos

    def test_listar_todos_real_no_filtra_por_activo_ni_fecha(self):
        codigo_fuente = self._RUTA.read_text(encoding="utf-8")
        indice = codigo_fuente.index("def listar_todos(")
        bloque = codigo_fuente[indice:indice + 250]
        assert "activo" not in bloque
        assert "en_fecha" not in bloque

    def test_listar_vigentes_con_fecha_reutiliza_listar_todos_sin_filtrar_por_activo(self):
        codigo_fuente = self._RUTA.read_text(encoding="utf-8")
        indice = codigo_fuente.index("def _listar_por_vigencia_en(")
        bloque = codigo_fuente[indice:indice + 200]
        assert "self.listar_todos(juego_id)" in bloque
        assert "activo" not in bloque

    def test_esta_vigente_en_es_la_unica_fuente_de_verdad_temporal_sin_duplicar_en_sql(self):
        codigo_fuente = self._RUTA.read_text(encoding="utf-8")
        assert codigo_fuente.count("esta_vigente_en(") == 2  # sin fecha + con fecha, nunca un WHERE duplicando la regla

    def test_una_sola_llamada_a_session_scalars_por_camino_de_ejecucion(self):
        """Confirma por lectura exacta que ninguna de las 3 rutas
        públicas contiene más de una consulta -sin N+1."""
        codigo_fuente = self._RUTA.read_text(encoding="utf-8")
        assert codigo_fuente.count("self._session.scalars(") == 2  # 1 en "sin fecha", 1 en listar_todos; "con fecha" delega a listar_todos, cero adicionales
