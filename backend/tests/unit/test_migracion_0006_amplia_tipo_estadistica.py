"""Pruebas del esquema físico de `estadisticas.tipo_estadistica`.

Etapa AE-27 (corrección obligatoria): la validación HTTP real contra
PostgreSQL descubrió que `estadisticas.tipo_estadistica` -declarada
como `varchar(50)` desde la migración 0001- no admite el
identificador real de AE-27,
`frecuencia_pares_numero_color_por_dia_semana_colorloto` (54
caracteres), y que la aplicación fallaba con
`psycopg.errors.StringDataRightTruncation` al intentar persistir
cualquier resultado de esa etapa.

Ninguna prueba anterior del proyecto detectaba esto: todas las
pruebas de `test_estadistica_repository.py` y
`test_calcular_y_persistir_estadistica.py` usan un repositorio en
memoria (`_EstadisticaRepositoryEnMemoria`/`fakes.py`) que almacena
`tipo_estadistica` como un `str` de Python sin ninguna restricción de
longitud -el dominio real de la aplicación (identificadores de
Python, sin límite práctico) y el dominio físico de PostgreSQL
(`varchar(50)`) nunca se compararon en ninguna prueba. Este archivo
cierra ese hueco: valida directamente los metadatos de
`EstadisticaORM` (columna real de SQLAlchemy) contra el catálogo real
de identificadores (`_CATALOGO`), sin necesidad de una conexión a
PostgreSQL -SQLAlchemy expone la longitud declarada de la columna sin
ejecutar ningún SQL.

No hay PostgreSQL disponible en este sandbox (confirmado: sin
binario `psql`/`postgres`, sin servidor, sin el driver `psycopg`
instalado) -estas pruebas NO ejecutan `alembic upgrade`/`downgrade`
contra una base real, solo verifican los metadatos del modelo
SQLAlchemy y la lógica/encadenamiento de la migración por inspección
estática del código real. La ejecución real de la migración contra
PostgreSQL queda pendiente para el entorno del usuario.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from app.infrastructure.db.models import EstadisticaORM
from app.application.use_cases.calcular_y_persistir_estadistica import _CATALOGO

_MIGRACIONES_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"
_IDENTIFICADOR_AE27 = "frecuencia_pares_numero_color_por_dia_semana_colorloto"


class TestModeloTipoEstadisticaCapacidad:
    def test_columna_tipo_estadistica_es_varchar_100(self):
        columna = EstadisticaORM.__table__.columns["tipo_estadistica"]
        assert columna.type.length == 100

    def test_columna_sigue_no_nula_e_indexada(self):
        columna = EstadisticaORM.__table__.columns["tipo_estadistica"]
        assert columna.nullable is False
        assert columna.index is True

    def test_identificador_ae27_mide_54_caracteres(self):
        assert len(_IDENTIFICADOR_AE27) == 54

    def test_identificador_ae27_cabe_en_la_columna_sin_truncar(self):
        columna = EstadisticaORM.__table__.columns["tipo_estadistica"]
        assert len(_IDENTIFICADOR_AE27) <= columna.type.length

    def test_identificador_ae27_habria_excedido_el_limite_anterior(self):
        """Documenta el defecto real: con el límite original (50),
        el identificador de AE-27 NO cabía -esta es la condición que
        causaba el StringDataRightTruncation real en PostgreSQL."""
        limite_anterior = 50
        assert len(_IDENTIFICADOR_AE27) > limite_anterior

    def test_todos_los_tipo_estadistica_registrados_caben_en_la_columna(self):
        columna = EstadisticaORM.__table__.columns["tipo_estadistica"]
        excedidos = [clave for clave in _CATALOGO if len(clave) > columna.type.length]
        assert excedidos == [], f"identificadores que exceden la capacidad de la columna: {excedidos}"

    def test_identificador_ae27_esta_registrado_en_el_catalogo_real(self):
        assert _IDENTIFICADOR_AE27 in _CATALOGO

    def test_ningun_otro_identificador_alcanza_el_limite_de_100(self):
        """Confirma que 100 deja margen real -ningún identificador
        actual se acerca al nuevo límite, a diferencia del límite
        anterior (50), que ya no tenía ningún margen antes de AE-27
        (el segundo más largo, de AE-21, medía exactamente 50)."""
        mas_largo = max(len(clave) for clave in _CATALOGO)
        assert mas_largo == 63
        assert mas_largo < 100

    def test_identificador_ae31_es_ahora_el_mas_largo_del_catalogo(self):
        """AE-31 (\"comparacion_frecuencia_pares_numero_color_por_ventana_colorloto\",
        63 caracteres) desplaza a AE-27 (54 caracteres) como el
        identificador más largo real -confirmado real, nunca por
        aritmética textual."""
        identificador_ae31 = "comparacion_frecuencia_pares_numero_color_por_ventana_colorloto"
        assert len(identificador_ae31) == 63
        assert identificador_ae31 in _CATALOGO
        assert identificador_ae31 == max(_CATALOGO, key=len)
        columna = EstadisticaORM.__table__.columns["tipo_estadistica"]
        assert len(identificador_ae31) <= columna.type.length


class TestMigracion0006AmpliaTipoEstadistica:
    _ARCHIVO = _MIGRACIONES_DIR / "0006_amplia_tipo_estadistica.py"

    def test_archivo_de_migracion_existe(self):
        assert self._ARCHIVO.exists()

    def test_down_revision_es_0005_la_head_real_de_ae26(self):
        codigo_fuente = self._ARCHIVO.read_text(encoding="utf-8")
        assert re.search(r'^revision = "0006"', codigo_fuente, re.MULTILINE)
        assert re.search(r'^down_revision = "0005"', codigo_fuente, re.MULTILINE)

    def test_0006_es_la_unica_head_del_arbol_de_migraciones(self):
        revisiones = {}
        for archivo in _MIGRACIONES_DIR.glob("*.py"):
            codigo_fuente = archivo.read_text(encoding="utf-8")
            rev = re.search(r'^revision = "(\w+)"', codigo_fuente, re.MULTILINE).group(1)
            down = re.search(r'^down_revision = (None|"(\w+)")', codigo_fuente, re.MULTILINE)
            revisiones[rev] = down.group(2) if down.group(2) else None
        apuntadas = {d for d in revisiones.values() if d}
        heads = [r for r in revisiones if r not in apuntadas]
        assert heads == ["0006"]

    def test_upgrade_amplia_de_50_a_100_sin_tocar_indices(self):
        codigo_fuente = self._ARCHIVO.read_text(encoding="utf-8")
        arbol = ast.parse(codigo_fuente)
        funcion_upgrade = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
        cuerpo = ast.dump(funcion_upgrade)
        assert "alter_column" in cuerpo
        assert "drop_index" not in codigo_fuente[codigo_fuente.index("def upgrade"):codigo_fuente.index("def downgrade")]
        assert "create_index" not in codigo_fuente[codigo_fuente.index("def upgrade"):codigo_fuente.index("def downgrade")]
        assert "String(50)" in codigo_fuente
        assert "String(100)" in codigo_fuente

    def test_downgrade_verifica_precondicion_antes_de_reducir(self):
        codigo_fuente = self._ARCHIVO.read_text(encoding="utf-8")
        bloque_downgrade = codigo_fuente[codigo_fuente.index("def downgrade"):]
        assert "length(tipo_estadistica) > 50" in bloque_downgrade
        assert "RuntimeError" in bloque_downgrade
        assert "alter_column" in bloque_downgrade

    def test_migracion_0005_no_fue_modificada_sus_indices_permanecen(self):
        codigo_fuente = (_MIGRACIONES_DIR / "0005_estadisticas_corte_y_hash.py").read_text(encoding="utf-8")
        for nombre_indice in ["ix_estadisticas_juego_tipo_corte", "uq_estadisticas_con_corte", "uq_estadisticas_sin_corte"]:
            assert nombre_indice in codigo_fuente

    def test_migracion_0001_original_no_fue_modificada(self):
        """La migración histórica que creó la columna en varchar(50)
        permanece intacta -la corrección es aditiva (migración 0006),
        nunca una reescritura del historial ya aplicado."""
        codigo_fuente = (_MIGRACIONES_DIR / "0001_initial_schema.py").read_text(encoding="utf-8")
        assert 'sa.Column("tipo_estadistica", sa.String(50), nullable=False)' in codigo_fuente


class TestContratosFuncionalesAE22aAE27Intactos:
    """Confirma que la corrección física de AE-27 no alteró ningún
    contrato funcional previo -ni de las propias recetas AE-22 a
    AE-27, ni de sus identificadores de `tipo_estadistica`."""

    def test_treintayseis_recetas_registradas(self):
        assert len(_CATALOGO) == 43

    def test_identificadores_ae22_a_ae27_sin_cambios(self):
        esperados = {
            "frecuencia_colores_por_anio_colorloto",
            "frecuencia_colores_por_mes_colorloto",
            "frecuencia_colores_por_dia_semana_colorloto",
            "frecuencia_pares_numero_color_por_anio_colorloto",
            "frecuencia_pares_numero_color_por_mes_colorloto",
            "frecuencia_pares_numero_color_por_dia_semana_colorloto",
        }
        assert esperados.issubset(set(_CATALOGO.keys()))
