"""Lecturas de la API publica: los mismos casos de uso y repositorios que la
aplicacion local, con una sesion PROPIA de solo lectura (en PostgreSQL,
`SET TRANSACTION READ ONLY`; siempre termina en ROLLBACK, nunca confirma).
Predicciones y simulaciones usan sus casos de uso, que ya leen la base en
transacciones de solo lectura y no escriben en sus consultas."""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import dependencies as dep
from app.application.use_cases.consultar_estadisticas_descriptivas import ConsultarEstadisticasDescriptivas
from app.application.use_cases.consultar_juegos import ListarJuegos, ObtenerJuego
from app.application.use_cases.consultar_resumen_juego import ConsultarResumenJuego
from app.application.use_cases.listar_sorteos import ListarSorteos
from app.application.use_cases.predicciones import CentroDePredicciones
from app.application.use_cases.simulaciones import SimulacionesFase7
from app.infrastructure.db import session as db_session
from app.infrastructure.repositories.color_repository_sqlalchemy import ColorRepositorySQLAlchemy
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
    ResultadosHistoricosRepositorySQLAlchemy,
)
from app.infrastructure.repositories.sorteo_repository_sqlalchemy import SorteoRepositorySQLAlchemy


def sesion_de_lectura() -> Generator[Session, None, None]:
    session = db_session.SessionLocal()
    try:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
        yield session
    finally:
        session.rollback()
        session.close()


def listar_juegos(db: Session = Depends(sesion_de_lectura)) -> ListarJuegos:
    return dep.get_listar_juegos(JuegoRepositorySQLAlchemy(db))


def obtener_juego(db: Session = Depends(sesion_de_lectura)) -> ObtenerJuego:
    return dep.get_obtener_juego(JuegoRepositorySQLAlchemy(db), dep.get_game_factory(ColorRepositorySQLAlchemy(db)))


def listar_sorteos(db: Session = Depends(sesion_de_lectura)) -> ListarSorteos:
    return dep.get_listar_sorteos(JuegoRepositorySQLAlchemy(db), SorteoRepositorySQLAlchemy(db))


def consultar_resumen(db: Session = Depends(sesion_de_lectura)) -> ConsultarResumenJuego:
    return dep.get_consultar_resumen_juego(JuegoRepositorySQLAlchemy(db), ResultadosHistoricosRepositorySQLAlchemy(db),
                                           ColorRepositorySQLAlchemy(db))


def consultar_estadisticas(db: Session = Depends(sesion_de_lectura)) -> ConsultarEstadisticasDescriptivas:
    return dep.get_consultar_estadisticas_descriptivas(
        JuegoRepositorySQLAlchemy(db), ResultadosHistoricosRepositorySQLAlchemy(db), ColorRepositorySQLAlchemy(db))


def centro_de_predicciones() -> CentroDePredicciones:
    return dep.get_predicciones(dep.get_carteras())


def simulaciones() -> SimulacionesFase7:
    return dep.get_simulaciones()


def estado_de_la_base() -> str:
    """`disponible` o `no_disponible`; el motivo nunca sale de aqui."""
    sesiones = sesion_de_lectura()
    try:
        next(sesiones).execute(text("SELECT 1"))
        return "disponible"
    except Exception:  # cualquier fallo de conexion: solo se informa el estado
        return "no_disponible"
    finally:
        sesiones.close()


def consultas_guardadas():
    """Lectores de Fases 3, Producto 5 y Producto 6, sin lanzadores ni recuperación.

    Construir estos proveedores no crea almacenes ni inicia procesos. Las
    consultas nuevas no utilizan el ejecutor de los casos de uso existentes.
    """
    from app.application.use_cases.consultas_guardadas import ConsultasGuardadas
    from app.core.config import get_settings
    from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore

    carteras = dep.get_carteras()
    return ConsultasGuardadas(LaboratorioFileStore(get_settings().directorio_laboratorio_modelos),
                             carteras, dep.get_resultados(carteras))
