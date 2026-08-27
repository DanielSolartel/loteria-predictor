"""agrega el juego BALOTO (clasico), faltante desde la Fase 1

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-06

Contexto (ver ARCHITECTURE.md / informe de revisión arquitectónica):
la Fase 1 solo modeló "BALOTO_REVANCHA" -el resultado principal de
Baloto clásico nunca se guardó. Esta migración agrega el juego que
faltaba. No se toca el esquema de `sorteos` ni de ninguna tabla
relacionada: Baloto y Revancha se modelan como juegos independientes
(mismo patrón que MiLoto/ColorLoto), relacionados por
`numero_sorteo` -no por una columna o tabla nueva. Es una migración
puramente de datos.
"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    op.bulk_insert(
        juegos_table,
        [
            {
                "id": uuid.uuid4(), "codigo": "BALOTO", "nombre": "Baloto",
                "rango_min": 1, "rango_max": 43, "cantidad_numeros": 5,
                "tiene_superbalota": True, "superbalota_min": 1, "superbalota_max": 16,
                "tiene_color": False, "permite_repeticion": False, "activo": True,
            },
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM sorteos WHERE juego_id IN (SELECT id FROM juegos WHERE codigo = 'BALOTO')")
    op.execute("DELETE FROM juegos WHERE codigo = 'BALOTO'")
