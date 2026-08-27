"""agrega indice compuesto (juego_id, fecha) en sorteos

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01

Detectado en la auditoría de rendimiento previa al cierre de Fase 2:
`listar_por_juego` filtra por `juego_id` y ordena por `fecha`, pero
solo existían índices separados para cada columna (Postgres no puede
combinarlos tan eficientemente como un índice compuesto que cubra
ambas a la vez).
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_sorteos_juego_fecha", "sorteos", ["juego_id", "fecha"])


def downgrade() -> None:
    op.drop_index("ix_sorteos_juego_fecha", table_name="sorteos")
