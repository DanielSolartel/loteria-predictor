"""agrega hasta_numero_sorteo y parametros_hash a estadisticas

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-09

Contexto (Etapa Q/R del motor estadístico): `estadisticas` existe
desde la Fase 1 (migración 0001) pero nunca fue escrita por ningún
caso de uso -confirmado por inspección, cero referencias a
`EstadisticaORM` fuera de `models.py` en todo el historial del
proyecto. La tabla está garantizadamente vacía en cualquier entorno
real, así que esta migración es aditiva pura, sin necesidad de
backfill de datos existentes.

`hasta_numero_sorteo` sale de `parametros` (JSONB) y se vuelve
columna propia: es el campo central de invalidación de cache y de la
garantía anti-fuga del motor -necesita ser filtrable/indexable en SQL
directamente, no enterrado en un blob JSONB.

`parametros_hash`: SHA-256 hexadecimal (64 caracteres) de los
parámetros canonicalizados (ver
`app/application/interfaces/estadistica_repository.py::calcular_parametros_hash`),
necesario porque PostgreSQL no garantiza unicidad estable sobre JSONB
por igualdad de contenido (orden de claves, representación de
floats) sin normalizar antes.

Unicidad con NULL -decisión central de esta migración: un UNIQUE
convencional sobre (juego_id, tipo_estadistica, hasta_numero_sorteo,
parametros_hash) NO habría bloqueado duplicados cuando
hasta_numero_sorteo es NULL (verificado explícitamente antes de
implementar: PostgreSQL, igual que SQLite, nunca considera NULL=NULL
en una restricción UNIQUE, así que múltiples filas NULL "distintas"
pasarían la restricción). Se usan DOS índices únicos PARCIALES en su
lugar:
  - uq_estadisticas_con_corte: cubre hasta_numero_sorteo IS NOT NULL,
    con los 4 campos completos.
  - uq_estadisticas_sin_corte: cubre hasta_numero_sorteo IS NULL, con
    los 3 campos restantes (el corte ya está fijo a NULL por el WHERE,
    no hace falta incluirlo en las columnas del índice).
Cada fila cae en uno de los dos índices, nunca en ambos -juntos dan
la unicidad completa pedida, incluyendo el caso NULL.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("estadisticas", sa.Column("hasta_numero_sorteo", sa.Integer(), nullable=True))
    op.add_column("estadisticas", sa.Column("parametros_hash", sa.CHAR(64), nullable=True))

    op.create_index(
        "ix_estadisticas_juego_tipo_corte",
        "estadisticas",
        ["juego_id", "tipo_estadistica", "hasta_numero_sorteo"],
    )

    op.create_index(
        "uq_estadisticas_con_corte",
        "estadisticas",
        ["juego_id", "tipo_estadistica", "hasta_numero_sorteo", "parametros_hash"],
        unique=True,
        postgresql_where=sa.text("hasta_numero_sorteo IS NOT NULL"),
    )
    op.create_index(
        "uq_estadisticas_sin_corte",
        "estadisticas",
        ["juego_id", "tipo_estadistica", "parametros_hash"],
        unique=True,
        postgresql_where=sa.text("hasta_numero_sorteo IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_estadisticas_sin_corte", table_name="estadisticas")
    op.drop_index("uq_estadisticas_con_corte", table_name="estadisticas")
    op.drop_index("ix_estadisticas_juego_tipo_corte", table_name="estadisticas")
    op.drop_column("estadisticas", "parametros_hash")
    op.drop_column("estadisticas", "hasta_numero_sorteo")
