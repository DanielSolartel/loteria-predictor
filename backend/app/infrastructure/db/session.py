from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: una sesión por request.

    Los repositorios (infrastructure/repositories) solo hacen
    `flush()`, nunca `commit()` -el commit es responsabilidad de la
    unidad de trabajo del request, no de cada operación individual.
    Esto evita commits parciales si un caso de uso hace varias
    llamadas al repositorio y una falla a mitad de camino."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
