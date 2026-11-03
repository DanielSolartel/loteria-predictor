from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def opciones_del_motor(ajustes) -> dict:
    """Argumentos de `create_engine` (Fase 10, E10.2).

    Sin `BASE_*` configurados devuelve exactamente los de siempre: la sesion de
    escritura de la consola, la CLI y Fase 6 no cambia. Con ellos (perfil privado
    de la API) y solo en PostgreSQL, cada conexion nueva fija
    `statement_timeout` e `idle_in_transaction_session_timeout`, y el pool queda
    acotado (tamano, desborde y espera de una conexion libre)."""
    opciones: dict = {"pool_pre_ping": True, "future": True}
    postgres = make_url(ajustes.database_url).get_backend_name() == "postgresql"
    parametros = []
    for nombre, valor in (("statement_timeout", ajustes.base_tiempo_maximo_consulta_ms),
                          ("idle_in_transaction_session_timeout", ajustes.base_tiempo_maximo_inactiva_ms)):
        if valor < 0:
            raise ValueError(f"{nombre}: no puede ser negativo")
        if valor:
            if not postgres:
                raise ValueError(f"{nombre}: solo se admite con PostgreSQL")
            parametros.append(f"-c {nombre}={int(valor)}")
    if parametros:
        opciones["connect_args"] = {"options": " ".join(parametros)}
    if ajustes.base_pool_tamano < 0 or ajustes.base_pool_desborde < 0 or ajustes.base_pool_espera_s < 0:
        raise ValueError("BASE_POOL_*: no pueden ser negativos")
    if ajustes.base_pool_tamano:
        opciones["pool_size"] = ajustes.base_pool_tamano
        opciones["max_overflow"] = ajustes.base_pool_desborde
    if ajustes.base_pool_espera_s:
        opciones["pool_timeout"] = ajustes.base_pool_espera_s
    return opciones


engine = create_engine(settings.database_url, **opciones_del_motor(settings))

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
