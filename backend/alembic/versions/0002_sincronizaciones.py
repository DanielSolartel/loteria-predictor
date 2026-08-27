"""agrega tabla sincronizaciones (módulo de adquisición de datos)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sincronizaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("juego_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("juegos.id"), nullable=False),
        sa.Column("conector", sa.String(60), nullable=False),
        sa.Column("iniciado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("sorteos_nuevos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sorteos_fallidos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sorteos_duplicados", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sorteos_incompletos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_sorteos_encontrados", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duracion_ms", sa.Integer, nullable=True),
        sa.Column("ultimo_sorteo_importado", sa.Integer, nullable=True),
        sa.Column("detalle_errores", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.create_index("ix_sincronizaciones_juego_id", "sincronizaciones", ["juego_id"])


def downgrade() -> None:
    op.drop_table("sincronizaciones")
