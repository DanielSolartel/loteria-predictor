"""
Contenedor de Dependency Injection.

Único módulo del sistema que conecta infraestructura concreta
(SQLAlchemy) con la capa de aplicación (casos de uso), vía las
funciones `Depends()` de FastAPI. Tanto `api/web` como `api/rest`
importan de aquí -nunca instancian un repositorio o caso de uso por
su cuenta. Esto es lo que garantiza que ambos adaptadores de entrada
comparten exactamente la misma lógica de negocio.
"""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.editar_sorteo import EditarSorteo
from app.application.use_cases.eliminar_sorteo import EliminarSorteo
from app.application.use_cases.consultar_juegos import ListarJuegos, ObtenerJuego
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.gestionar_paleta_colores import GestionarPaletaColores
from app.application.use_cases.listar_sorteos import ListarSorteos
from app.application.use_cases.obtener_resumen_sistema import ObtenerResumenSistema
from app.application.use_cases.obtener_sorteo import ObtenerSorteo
from app.application.use_cases.registrar_sorteo import RegistrarSorteo
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.color_repository_sqlalchemy import ColorRepositorySQLAlchemy
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.sorteo_repository_sqlalchemy import SorteoRepositorySQLAlchemy


def get_juego_repository(db: Session = Depends(get_db)) -> JuegoRepositorySQLAlchemy:
    return JuegoRepositorySQLAlchemy(db)


def get_sorteo_repository(db: Session = Depends(get_db)) -> SorteoRepositorySQLAlchemy:
    return SorteoRepositorySQLAlchemy(db)


def get_color_repository(db: Session = Depends(get_db)) -> ColorRepositorySQLAlchemy:
    return ColorRepositorySQLAlchemy(db)


def get_game_factory(
    color_repo: ColorRepositorySQLAlchemy = Depends(get_color_repository),
) -> GameFactory:
    return GameFactory(color_repository=color_repo)


def get_listar_juegos(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
) -> ListarJuegos:
    return ListarJuegos(juego_repository=juego_repo)


def get_obtener_juego(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    game_factory: GameFactory = Depends(get_game_factory),
) -> ObtenerJuego:
    return ObtenerJuego(juego_repository=juego_repo, game_factory=game_factory)


def get_listar_sorteos(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
) -> ListarSorteos:
    return ListarSorteos(juego_repository=juego_repo, sorteo_repository=sorteo_repo)


def get_resumen_sistema(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
) -> ObtenerResumenSistema:
    return ObtenerResumenSistema(juego_repository=juego_repo, sorteo_repository=sorteo_repo)


def get_obtener_sorteo(
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
) -> ObtenerSorteo:
    return ObtenerSorteo(sorteo_repository=sorteo_repo)


def get_registrar_sorteo(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    game_factory: GameFactory = Depends(get_game_factory),
) -> RegistrarSorteo:
    return RegistrarSorteo(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=game_factory
    )


def get_editar_sorteo(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    game_factory: GameFactory = Depends(get_game_factory),
) -> EditarSorteo:
    return EditarSorteo(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=game_factory
    )


def get_eliminar_sorteo(
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
) -> EliminarSorteo:
    return EliminarSorteo(sorteo_repository=sorteo_repo)


def get_gestionar_paleta_colores(
    color_repo: ColorRepositorySQLAlchemy = Depends(get_color_repository),
) -> GestionarPaletaColores:
    return GestionarPaletaColores(color_repository=color_repo)
