"""esquema inicial: juegos, sorteos y tablas relacionadas

Revision ID: 0001
Revises:
Create Date: 2026-07-31
"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "juegos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("rango_min", sa.Integer, nullable=False),
        sa.Column("rango_max", sa.Integer, nullable=False),
        sa.Column("cantidad_numeros", sa.Integer, nullable=False),
        sa.Column("tiene_superbalota", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("superbalota_min", sa.Integer, nullable=True),
        sa.Column("superbalota_max", sa.Integer, nullable=True),
        sa.Column("tiene_color", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("permite_repeticion", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("codigo", name="uq_juegos_codigo"),
    )

    op.create_table(
        "sorteos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("juego_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("juegos.id"), nullable=False),
        sa.Column("numero_sorteo", sa.Integer, nullable=False),
        sa.Column("fecha", sa.Date, nullable=False),
        sa.Column("dia_semana", sa.String(15), nullable=False),
        sa.Column("fuente", sa.String(100), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("juego_id", "numero_sorteo", name="uq_sorteo_juego_numero"),
    )
    op.create_index("ix_sorteos_juego_id", "sorteos", ["juego_id"])
    op.create_index("ix_sorteos_fecha", "sorteos", ["fecha"])

    op.create_table(
        "sorteo_numeros",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sorteo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sorteos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("posicion", sa.Integer, nullable=False),
        sa.UniqueConstraint("sorteo_id", "posicion", name="uq_sorteo_numero_posicion"),
    )
    op.create_index("ix_sorteo_numeros_sorteo_id", "sorteo_numeros", ["sorteo_id"])
    op.create_index("ix_sorteo_numeros_numero", "sorteo_numeros", ["numero"])

    op.create_table(
        "sorteo_superbalota",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sorteo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sorteos.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("numero", sa.Integer, nullable=False),
    )
    op.create_index("ix_sorteo_superbalota_numero", "sorteo_superbalota", ["numero"])

    op.create_table(
        "colores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("juego_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("juegos.id"), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(50), nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("vigente_desde", sa.Date, nullable=True),
        sa.Column("vigente_hasta", sa.Date, nullable=True),
        sa.UniqueConstraint("juego_id", "codigo", "vigente_desde", name="uq_color_vigencia"),
    )
    op.create_index("ix_colores_juego_id", "colores", ["juego_id"])

    op.create_table(
        "sorteo_color_numero",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sorteo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sorteos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("color_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("colores.id"), nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("posicion", sa.Integer, nullable=False),
        sa.UniqueConstraint("sorteo_id", "posicion", name="uq_sorteo_color_numero_posicion"),
    )
    op.create_index("ix_sorteo_color_numero_sorteo_id", "sorteo_color_numero", ["sorteo_id"])
    op.create_index("ix_sorteo_color_numero_color_id", "sorteo_color_numero", ["color_id"])
    op.create_index("ix_sorteo_color_numero_numero", "sorteo_color_numero", ["numero"])

    op.create_table(
        "estadisticas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("juego_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("juegos.id"), nullable=False),
        sa.Column("tipo_estadistica", sa.String(50), nullable=False),
        sa.Column("parametros", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("resultado", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("calculado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("valido_hasta", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_estadisticas_juego_id", "estadisticas", ["juego_id"])
    op.create_index("ix_estadisticas_tipo", "estadisticas", ["tipo_estadistica"])

    op.create_table(
        "modelos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("juego_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("juegos.id"), nullable=False),
        sa.Column("nombre_modelo", sa.String(60), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("hiperparametros", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("metodo_validacion", sa.String(50), nullable=True),
        sa.Column("entrenado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_modelos_juego_id", "modelos", ["juego_id"])

    op.create_table(
        "metricas_modelo",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("modelo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("modelos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre_metrica", sa.String(30), nullable=False),
        sa.Column("valor", sa.Numeric, nullable=False),
        sa.Column("calculado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_metricas_modelo_modelo_id", "metricas_modelo", ["modelo_id"])
    op.create_index("ix_metricas_modelo_nombre", "metricas_modelo", ["nombre_metrica"])

    op.create_table(
        "predicciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("juego_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("juegos.id"), nullable=False),
        sa.Column("modelo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("modelos.id"), nullable=False),
        sa.Column("fecha_generacion", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sorteo_objetivo", sa.Integer, nullable=False),
        sa.Column("combinaciones", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("numeros_fuertes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("numeros_debiles", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("probabilidades", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("explicacion", sa.Text, nullable=False, server_default=""),
        sa.Column("nivel_confianza", sa.Numeric, nullable=True),
    )
    op.create_index("ix_predicciones_juego_id", "predicciones", ["juego_id"])
    op.create_index("ix_predicciones_modelo_id", "predicciones", ["modelo_id"])

    op.create_table(
        "simulaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("juego_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("juegos.id"), nullable=False),
        sa.Column("num_iteraciones", sa.Integer, nullable=False),
        sa.Column("parametros", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("resultado_resumen", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("ejecutado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("duracion_ms", sa.Integer, nullable=True),
    )
    op.create_index("ix_simulaciones_juego_id", "simulaciones", ["juego_id"])

    # --- Seed: los 3 juegos base definidos en el dominio ---
    juegos_table = sa.table(
        "juegos",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("codigo", sa.String),
        sa.column("nombre", sa.String),
        sa.column("rango_min", sa.Integer),
        sa.column("rango_max", sa.Integer),
        sa.column("cantidad_numeros", sa.Integer),
        sa.column("tiene_superbalota", sa.Boolean),
        sa.column("superbalota_min", sa.Integer),
        sa.column("superbalota_max", sa.Integer),
        sa.column("tiene_color", sa.Boolean),
        sa.column("permite_repeticion", sa.Boolean),
        sa.column("activo", sa.Boolean),
    )

    miloto_id = uuid.uuid4()
    revancha_id = uuid.uuid4()
    colorloto_id = uuid.uuid4()

    op.bulk_insert(
        juegos_table,
        [
            {
                "id": miloto_id, "codigo": "MILOTO", "nombre": "MiLoto",
                "rango_min": 1, "rango_max": 39, "cantidad_numeros": 5,
                "tiene_superbalota": False, "superbalota_min": None, "superbalota_max": None,
                "tiene_color": False, "permite_repeticion": False, "activo": True,
            },
            {
                "id": revancha_id, "codigo": "BALOTO_REVANCHA", "nombre": "Baloto Revancha",
                "rango_min": 1, "rango_max": 43, "cantidad_numeros": 5,
                "tiene_superbalota": True, "superbalota_min": 1, "superbalota_max": 16,
                "tiene_color": False, "permite_repeticion": False, "activo": True,
            },
            {
                "id": colorloto_id, "codigo": "COLORLOTO", "nombre": "ColorLoto",
                "rango_min": 1, "rango_max": 7, "cantidad_numeros": 6,
                "tiene_superbalota": False, "superbalota_min": None, "superbalota_max": None,
                "tiene_color": True, "permite_repeticion": True, "activo": True,
            },
        ],
    )

    colores_table = sa.table(
        "colores",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("juego_id", postgresql.UUID(as_uuid=True)),
        sa.column("codigo", sa.String),
        sa.column("nombre", sa.String),
        sa.column("activo", sa.Boolean),
        sa.column("vigente_desde", sa.Date),
        sa.column("vigente_hasta", sa.Date),
    )
    paleta_colorloto = [
        ("AMARILLO", "Amarillo"), ("AZUL", "Azul"), ("ROJO", "Rojo"),
        ("VERDE", "Verde"), ("BLANCO", "Blanco"), ("NEGRO", "Negro"),
    ]
    op.bulk_insert(
        colores_table,
        [
            {
                "id": uuid.uuid4(), "juego_id": colorloto_id, "codigo": codigo, "nombre": nombre,
                "activo": True, "vigente_desde": "2024-08-15", "vigente_hasta": None,
            }
            for codigo, nombre in paleta_colorloto
        ],
    )


def downgrade() -> None:
    op.drop_table("simulaciones")
    op.drop_table("predicciones")
    op.drop_table("metricas_modelo")
    op.drop_table("modelos")
    op.drop_table("estadisticas")
    op.drop_table("sorteo_color_numero")
    op.drop_table("colores")
    op.drop_table("sorteo_superbalota")
    op.drop_table("sorteo_numeros")
    op.drop_table("sorteos")
    op.drop_table("juegos")
