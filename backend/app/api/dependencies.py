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


import threading
from contextlib import contextmanager

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.use_cases.editar_sorteo import EditarSorteo
from app.application.use_cases.eliminar_sorteo import EliminarSorteo
from app.application.use_cases.calcular_y_persistir_estadistica import CalcularYPersistirEstadistica
from app.application.use_cases.consultar_juegos import ListarJuegos, ObtenerJuego
from app.application.use_cases.consultar_resumen_juego import ConsultarResumenJuego
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.generar_reporte_calidad_datos import GenerarReporteCalidadDatos
from app.application.use_cases.gestionar_paleta_colores import GestionarPaletaColores
from app.application.use_cases.listar_sorteos import ListarSorteos
from app.application.use_cases.obtener_estado_importacion import ObtenerEstadoImportacion
from app.application.use_cases.obtener_resumen_sistema import ObtenerResumenSistema
from app.application.use_cases.obtener_sorteo import ObtenerSorteo
from app.application.use_cases.obtener_sorteo_con_pareja import ObtenerSorteoConPareja
from app.application.use_cases.pronostico_experimental import (
    CompararConResultadosObservados,
    ConsultarPronosticosExperimentales,
    GenerarPronosticoExperimental,
    VerificarPronosticoExperimental,
)
from app.application.use_cases.laboratorio import LaboratorioDeModelos, Lectura
from app.application.use_cases.operacion_diaria import DependenciasDeJuego, OperacionDiaria
from app.application.use_cases.panel_diario import ConsultarPanelDiario
from app.application.use_cases.registrar_sorteo import RegistrarSorteo
from app.application.use_cases.rendimiento import ConsultarRendimiento
from app.application.use_cases.reimportar_sorteo import ReimportarSorteo
from app.application.use_cases.reprocesar_sorteos_desde_html import ReprocesarSorteosDesdeHtml
from app.application.use_cases.sincronizar_sorteos import SincronizarSorteos
from app.application.use_cases.validar_integridad import ValidarIntegridadDatos
from app.core.config import get_settings
from app.infrastructure.connectors.registry import ConnectorRegistry
from app.infrastructure.db import session as db_session
from app.infrastructure.db.session import get_db
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.repositories.color_repository_sqlalchemy import ColorRepositorySQLAlchemy
from app.infrastructure.repositories.estadistica_repository_sqlalchemy import EstadisticaRepositorySQLAlchemy
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import (
    ResultadosHistoricosRepositorySQLAlchemy,
)
from app.infrastructure.repositories.sincronizacion_repository_sqlalchemy import (
    SincronizacionRepositorySQLAlchemy,
)
from app.infrastructure.repositories.sorteo_repository_sqlalchemy import SorteoRepositorySQLAlchemy
from app.infrastructure.storage.html_file_storage import HtmlFileStorage
from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore

# Un único HtmlStorage y un único ConnectorRegistry para todo el
# proceso: los conectores mantienen su propia sesión HTTP (con
# keep-alive) y su caché interna (p.ej. MiLotoConnector), así que no
# tiene sentido reconstruirlos en cada request.
_html_storage = HtmlFileStorage()
_connector_registry = ConnectorRegistry(html_storage=_html_storage)


def get_connector_registry() -> ConnectorRegistry:
    return _connector_registry


def get_sincronizacion_repository(db: Session = Depends(get_db)) -> SincronizacionRepositorySQLAlchemy:
    return SincronizacionRepositorySQLAlchemy(db)


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


def get_obtener_sorteo_con_pareja(
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
) -> ObtenerSorteoConPareja:
    return ObtenerSorteoConPareja(sorteo_repository=sorteo_repo, juego_repository=juego_repo)


def get_estadistica_repository(db: Session = Depends(get_db)) -> EstadisticaRepositorySQLAlchemy:
    return EstadisticaRepositorySQLAlchemy(db)


def get_registrar_sorteo(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    estadistica_repo: EstadisticaRepositorySQLAlchemy = Depends(get_estadistica_repository),
) -> RegistrarSorteo:
    return RegistrarSorteo(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=game_factory,
        estadistica_repository=estadistica_repo,
    )


def get_editar_sorteo(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    estadistica_repo: EstadisticaRepositorySQLAlchemy = Depends(get_estadistica_repository),
) -> EditarSorteo:
    return EditarSorteo(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, game_factory=game_factory,
        estadistica_repository=estadistica_repo,
    )


def get_eliminar_sorteo(
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    estadistica_repo: EstadisticaRepositorySQLAlchemy = Depends(get_estadistica_repository),
) -> EliminarSorteo:
    return EliminarSorteo(sorteo_repository=sorteo_repo, estadistica_repository=estadistica_repo)


def get_gestionar_paleta_colores(
    color_repo: ColorRepositorySQLAlchemy = Depends(get_color_repository),
    estadistica_repo: EstadisticaRepositorySQLAlchemy = Depends(get_estadistica_repository),
) -> GestionarPaletaColores:
    return GestionarPaletaColores(color_repository=color_repo, estadistica_repository=estadistica_repo)


def get_unit_of_work(db: Session = Depends(get_db)) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(db)


def get_sincronizar_sorteos(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    sincronizacion_repo: SincronizacionRepositorySQLAlchemy = Depends(get_sincronizacion_repository),
    color_repo: ColorRepositorySQLAlchemy = Depends(get_color_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    connector_registry: ConnectorRegistry = Depends(get_connector_registry),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    estadistica_repo: EstadisticaRepositorySQLAlchemy = Depends(get_estadistica_repository),
) -> SincronizarSorteos:
    return SincronizarSorteos(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo,
        sincronizacion_repository=sincronizacion_repo, color_repository=color_repo,
        game_factory=game_factory, obtener_conector=connector_registry.obtener,
        unit_of_work=unit_of_work, estadistica_repository=estadistica_repo,
    )


def get_reimportar_sorteo(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    color_repo: ColorRepositorySQLAlchemy = Depends(get_color_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    connector_registry: ConnectorRegistry = Depends(get_connector_registry),
    estadistica_repo: EstadisticaRepositorySQLAlchemy = Depends(get_estadistica_repository),
) -> ReimportarSorteo:
    return ReimportarSorteo(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, color_repository=color_repo,
        game_factory=game_factory, obtener_conector=connector_registry.obtener,
        estadistica_repository=estadistica_repo,
    )


def get_reprocesar_desde_html(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    color_repo: ColorRepositorySQLAlchemy = Depends(get_color_repository),
    game_factory: GameFactory = Depends(get_game_factory),
    connector_registry: ConnectorRegistry = Depends(get_connector_registry),
    unit_of_work: SqlAlchemyUnitOfWork = Depends(get_unit_of_work),
    estadistica_repo: EstadisticaRepositorySQLAlchemy = Depends(get_estadistica_repository),
) -> ReprocesarSorteosDesdeHtml:
    return ReprocesarSorteosDesdeHtml(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo, color_repository=color_repo,
        game_factory=game_factory, obtener_conector=connector_registry.obtener,
        unit_of_work=unit_of_work, estadistica_repository=estadistica_repo,
    )


def get_reporte_calidad_datos(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    sincronizacion_repo: SincronizacionRepositorySQLAlchemy = Depends(get_sincronizacion_repository),
) -> GenerarReporteCalidadDatos:
    return GenerarReporteCalidadDatos(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo,
        sincronizacion_repository=sincronizacion_repo,
    )


def get_validar_integridad(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
) -> ValidarIntegridadDatos:
    return ValidarIntegridadDatos(juego_repository=juego_repo, sorteo_repository=sorteo_repo)


def get_estado_importacion(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    sorteo_repo: SorteoRepositorySQLAlchemy = Depends(get_sorteo_repository),
    sincronizacion_repo: SincronizacionRepositorySQLAlchemy = Depends(get_sincronizacion_repository),
    connector_registry: ConnectorRegistry = Depends(get_connector_registry),
) -> ObtenerEstadoImportacion:
    return ObtenerEstadoImportacion(
        juego_repository=juego_repo, sorteo_repository=sorteo_repo,
        sincronizacion_repository=sincronizacion_repo, obtener_conector=connector_registry.obtener,
    )


def get_resultados_historicos_repository(
    db: Session = Depends(get_db),
) -> ResultadosHistoricosRepositorySQLAlchemy:
    return ResultadosHistoricosRepositorySQLAlchemy(db)


def get_calcular_y_persistir_estadistica(
    historico_repo: ResultadosHistoricosRepositorySQLAlchemy = Depends(get_resultados_historicos_repository),
    estadistica_repo: EstadisticaRepositorySQLAlchemy = Depends(get_estadistica_repository),
    color_repo: ColorRepositorySQLAlchemy = Depends(get_color_repository),
) -> CalcularYPersistirEstadistica:
    return CalcularYPersistirEstadistica(
        historico_repository=historico_repo, estadistica_repository=estadistica_repo,
        color_repository=color_repo,
    )


# ---------------------------------------------------------------------------
# Producto 1: resumen por juego y pronostico experimental
# ---------------------------------------------------------------------------

def get_consultar_resumen_juego(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    historico_repo: ResultadosHistoricosRepositorySQLAlchemy = Depends(get_resultados_historicos_repository),
    color_repo: ColorRepositorySQLAlchemy = Depends(get_color_repository),
) -> ConsultarResumenJuego:
    return ConsultarResumenJuego(juego_repo, historico_repo, color_repo)


def get_almacen_pronosticos() -> PronosticoExperimentalFileStore:
    return PronosticoExperimentalFileStore(get_settings().directorio_pronosticos_experimentales)


def get_consultar_pronosticos(
    almacen: PronosticoExperimentalFileStore = Depends(get_almacen_pronosticos),
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    historico_repo: ResultadosHistoricosRepositorySQLAlchemy = Depends(get_resultados_historicos_repository),
) -> ConsultarPronosticosExperimentales:
    return ConsultarPronosticosExperimentales(almacen, juego_repo, historico_repo)


def get_generar_pronostico(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    historico_repo: ResultadosHistoricosRepositorySQLAlchemy = Depends(get_resultados_historicos_repository),
    almacen: PronosticoExperimentalFileStore = Depends(get_almacen_pronosticos),
) -> GenerarPronosticoExperimental:
    return GenerarPronosticoExperimental(juego_repo, historico_repo, almacen)


def get_verificar_pronostico(
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    historico_repo: ResultadosHistoricosRepositorySQLAlchemy = Depends(get_resultados_historicos_repository),
    almacen: PronosticoExperimentalFileStore = Depends(get_almacen_pronosticos),
) -> VerificarPronosticoExperimental:
    return VerificarPronosticoExperimental(juego_repo, historico_repo, almacen)


def get_comparar_resultados(
    almacen: PronosticoExperimentalFileStore = Depends(get_almacen_pronosticos),
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    historico_repo: ResultadosHistoricosRepositorySQLAlchemy = Depends(get_resultados_historicos_repository),
) -> CompararConResultadosObservados:
    return CompararConResultadosObservados(almacen, juego_repo, historico_repo)


# ---------------------------------------------------------------------------
# Producto 3: operacion diaria, panel y rendimiento
# ---------------------------------------------------------------------------

@contextmanager
def abrir_dependencias_de_operacion(codigo_juego: str, modo: str):
    """Dependencias de UN juego para la operacion diaria, con su PROPIA
    sesion (cada trabajador abre la suya; nunca se comparte entre hilos).
    En modo `local` la transaccion es de solo lectura (PostgreSQL rechaza
    cualquier escritura) y termina en ROLLBACK. En modo `actualizar` se usa
    `SincronizarSorteos`, que confirma sorteo a sorteo como en Importacion."""
    session = db_session.SessionLocal()
    try:
        if modo == "local":
            session.execute(text("SET TRANSACTION READ ONLY"))
        juegos = JuegoRepositorySQLAlchemy(session)
        resultados = ResultadosHistoricosRepositorySQLAlchemy(session)
        sincronizar = None
        if modo == "actualizar":
            colores = ColorRepositorySQLAlchemy(session)
            caso = SincronizarSorteos(
                juego_repository=juegos, sorteo_repository=SorteoRepositorySQLAlchemy(session),
                sincronizacion_repository=SincronizacionRepositorySQLAlchemy(session), color_repository=colores,
                game_factory=GameFactory(color_repository=colores), obtener_conector=_connector_registry.obtener,
                unit_of_work=SqlAlchemyUnitOfWork(session),
                estadistica_repository=EstadisticaRepositorySQLAlchemy(session))
            sincronizar = caso.ejecutar
        yield DependenciasDeJuego(juegos, resultados, sincronizar)
        if modo == "local":
            session.rollback()
        else:
            session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_operacion_diaria() -> OperacionDiaria:
    ajustes = get_settings()
    return OperacionDiaria(PronosticoExperimentalFileStore(ajustes.directorio_pronosticos_experimentales),
                           RegistroEjecucionesArchivo(ajustes.directorio_operacion),
                           CerrojoPorJuego(ajustes.directorio_operacion), abrir_dependencias_de_operacion)


def get_consultar_panel(
    almacen: PronosticoExperimentalFileStore = Depends(get_almacen_pronosticos),
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    historico_repo: ResultadosHistoricosRepositorySQLAlchemy = Depends(get_resultados_historicos_repository),
    operacion: OperacionDiaria = Depends(get_operacion_diaria),
) -> ConsultarPanelDiario:
    return ConsultarPanelDiario(almacen, juego_repo, historico_repo, operacion)


def get_consultar_rendimiento(
    almacen: PronosticoExperimentalFileStore = Depends(get_almacen_pronosticos),
    juego_repo: JuegoRepositorySQLAlchemy = Depends(get_juego_repository),
    historico_repo: ResultadosHistoricosRepositorySQLAlchemy = Depends(get_resultados_historicos_repository),
) -> ConsultarRendimiento:
    return ConsultarRendimiento(almacen, juego_repo, historico_repo)


def _lanzar_en_hilo(funcion, inicio) -> None:
    """La web no espera al entrenamiento: un hilo por ejecucion, que abre
    sus propias sesiones por juego. Sin programador ni servicios externos."""
    threading.Thread(target=funcion, args=(inicio,), daemon=True,
                     name=f"operacion-{inicio.ejecucion['id']}").start()


def get_lanzador_de_operacion():
    return _lanzar_en_hilo


# ---------------------------------------------------------------------------
# Producto 4: laboratorio de modelos
# ---------------------------------------------------------------------------

@contextmanager
def abrir_lectura_del_laboratorio():
    """Una lectura consistente del historico en su PROPIA sesion, con una
    transaccion de solo lectura que termina en ROLLBACK. Se cierra antes de
    entrenar: ninguna sesion SQL queda abierta durante una comparacion."""
    session = db_session.SessionLocal()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield Lectura(JuegoRepositorySQLAlchemy(session), ResultadosHistoricosRepositorySQLAlchemy(session))
        session.rollback()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_laboratorio() -> LaboratorioDeModelos:
    directorio = get_settings().directorio_laboratorio_modelos
    operacion = f"{directorio}/operacion"
    return LaboratorioDeModelos(LaboratorioFileStore(directorio), RegistroEjecucionesArchivo(operacion),
                                CerrojoPorJuego(operacion), abrir_lectura_del_laboratorio,
                                ejecutor=EjecutorEnProceso())


def _lanzar_comparacion_en_hilo(funcion, inicio) -> None:
    """La comparacion no se ejecuta en el hilo de la peticion web."""
    threading.Thread(target=funcion, args=(inicio,), daemon=True,
                     name=f"laboratorio-{inicio.ejecucion['id']}").start()


def get_lanzador_de_laboratorio():
    return _lanzar_comparacion_en_hilo
