"""amplia tipo_estadistica de varchar(50) a varchar(100)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-05

Contexto (Etapa AE-27, corrección obligatoria): la validación HTTP
real contra PostgreSQL descubrió que toda solicitud válida de AE-27
(frecuencia de pares número-color por día de semana) fallaba con

    psycopg.errors.StringDataRightTruncation:
    value too long for type character varying(50)

al intentar persistir en `EstadisticaRepositorySQLAlchemy.guardar()`.
El identificador real es
`frecuencia_pares_numero_color_por_dia_semana_colorloto` -54
caracteres- mientras la columna física `estadisticas.tipo_estadistica`
(creada en la migración 0001 como `sa.String(50)`) solo admite 50.

Auditoría real del inventario completo de `tipo_estadistica`
(`_CATALOGO` en `calcular_y_persistir_estadistica.py`, 36 claves
reales en el momento de esta corrección): la segunda cadena más
larga, `intervalos_historicos_pares_numero_color_colorloto` (Etapa
AE-21), mide exactamente 50 -el límite original ya no tenía ningún
margen incluso antes de AE-27. Ninguna otra columna, fixture ni DDL
del proyecto declara el límite `50` para este dominio; `String(50)`
en `models.py` y `sa.String(50)` en `0001_initial_schema.py` son las
dos únicas declaraciones físicas de esta columna en todo el proyecto.

Decisión: ampliar a `varchar(100)`. No es una cifra arbitraria: deja
más de 40 caracteres de margen sobre el máximo real actual (54) y
sobre el candidato futuro más largo ya existente como función de
motor sin conectar que sigue el patrón de nombres establecido
(`comparar_frecuencia_pares_numero_color_por_ventana_colorloto`, 60
caracteres, aún sin decisión de producto ni `tipo_estadistica`
asignado). 100 es además un tamaño convencional para columnas de
tipo/categoría en PostgreSQL, evitando tanto la fragilidad de un
ajuste mínimo como el desperdicio de un valor arbitrariamente grande.

Es una migración puramente aditiva sobre el tipo de columna -ningún
índice, restricción ni dato existente se elimina o recrea:
`ix_estadisticas_tipo`, `ix_estadisticas_juego_tipo_corte`,
`uq_estadisticas_con_corte` y `uq_estadisticas_sin_corte` (los
cuatro definidos sobre `tipo_estadistica` junto con otras columnas,
migración 0005) permanecen exactamente como están -ampliar la
longitud de un `VARCHAR` en PostgreSQL nunca reescribe los datos
existentes ni invalida un índice btree ya construido sobre esa
columna. Ningún valor real actual (máximo 54 caracteres) se ve
afectado por la ampliación; todos los datos existentes se preservan
sin pérdida.

`downgrade()` reduce el límite de vuelta a 50, pero esa operación es
potencialmente destructiva si existen filas con `tipo_estadistica`
de más de 50 caracteres (como el identificador real de AE-27) -un
`ALTER COLUMN ... TYPE VARCHAR(50)` directo fallaría en PostgreSQL
con el mismo `StringDataRightTruncation` que motivó esta corrección,
o truncaría silenciosamente datos según el dialecto. Para evitar
ambos desenlaces, `downgrade()` primero verifica explícitamente que
ninguna fila exceda 50 caracteres y aborta con un error explícito y
accionable si encuentra alguna, en vez de delegar en un error críptico
de PostgreSQL o arriesgar una truncación silenciosa.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "estadisticas",
        "tipo_estadistica",
        existing_type=sa.String(50),
        type_=sa.String(100),
        existing_nullable=False,
    )


def downgrade() -> None:
    conexion = op.get_bind()
    fila_excedida = conexion.execute(
        sa.text("SELECT tipo_estadistica FROM estadisticas WHERE length(tipo_estadistica) > 50 LIMIT 1")
    ).first()
    if fila_excedida is not None:
        raise RuntimeError(
            "No se puede revertir tipo_estadistica a varchar(50): existe al menos una fila con un "
            f"valor de {len(fila_excedida[0])} caracteres ('{fila_excedida[0]}'), que excede ese límite. "
            "Elimine o migre esas filas antes de intentar este downgrade."
        )
    op.alter_column(
        "estadisticas",
        "tipo_estadistica",
        existing_type=sa.String(100),
        type_=sa.String(50),
        existing_nullable=False,
    )
