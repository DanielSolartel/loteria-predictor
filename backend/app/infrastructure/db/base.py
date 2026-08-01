from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa única para todos los modelos ORM.
    Alembic la usa como `target_metadata` para autogenerar migraciones."""
