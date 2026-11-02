"""FIXTURES SINTETICAS de la Fase 4 (centro de predicciones), solo para pruebas:
el laboratorio, los modelos registrados y las carteras de la Fase 3 sobre los
mismos historicos sinteticos en memoria, el centro de resultados de Producto
6 que los lee y el almacen de explicaciones. Sin PostgreSQL ni Internet.
Ningun dato es real."""
from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

from app.application.use_cases.laboratorio import EjecutorEnEsteProceso
from app.application.use_cases.predicciones import CentroDePredicciones
from app.application.use_cases.resultados import CentroDeResultados
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from app.infrastructure.storage.predicciones_file_store import PrediccionesFileStore
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from app.infrastructure.storage.resultados_file_store import ResultadosFileStore
from tests.unit import fixtures_fase3 as f3
from tests.unit import fixtures_producto1 as fx

Reloj = f3.Reloj
LOCAL = f3.LOCAL
lanzar_ya = f3.lanzar_ya
limpiar = f3.limpiar
MODELOS = f3.MODELOS


@dataclasses.dataclass
class Entorno(f3.Entorno):
    @property
    def raiz(self) -> Path:
        return self.directorio.parent

    @property
    def almacen_predicciones(self) -> PrediccionesFileStore:
        return PrediccionesFileStore(self.raiz / "predicciones")

    def centro_de_resultados(self, carteras=None) -> CentroDeResultados:
        return CentroDeResultados(PronosticoExperimentalFileStore(self.raiz / "pronosticos"), self.almacen_laboratorio,
                                  (carteras or self.carteras())._almacen, ResultadosFileStore(self.raiz / "resultados"),
                                  self.abrir, reloj=Reloj())

    def centro(self, carteras=None, ejecutor=None, reloj=None) -> CentroDePredicciones:
        servicio = carteras or self.carteras(reloj=reloj)
        return CentroDePredicciones(servicio, self.centro_de_resultados(servicio), self.almacen_predicciones,
                                    self.almacen_laboratorio, ejecutor or EjecutorEnEsteProceso(),
                                    RegistroEjecucionesArchivo(self.raiz / "predicciones" / "operacion"),
                                    cerrojo=CerrojoPorJuego(self.raiz / "predicciones" / "operacion"),
                                    reloj=reloj or Reloj())

    def configurar(self, juego: str, modelo: str, *, cantidad: int = 3, registrado: str | None = None,
                   perfil: str | None = "reducido", semilla: int = 42, diversidad: str = "libre"):
        return self.carteras().configurar(juego, modelo, cantidad, diversidad, semilla,
                                          None if registrado else perfil, "prueba", registrado=registrado)


def entorno(tmp_path, tamanos: dict | None = None) -> Entorno:
    base = f3.entorno(tmp_path, tamanos)
    return Entorno(base.juegos, base.resultados, base.historicos, base.directorio)


def arbol(raiz: Path) -> dict[str, str]:
    """SHA-256 de cada archivo bajo `raiz` (para comprobar que un GET no escribe)."""
    if not raiz.exists():
        return {}
    return {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raiz.rglob("*")) if p.is_file()}


def cliente(e: Entorno, *, client=LOCAL, lanzador=lanzar_ya, conectada: bool = True, centro=None, carteras=None,
            laboratorio=None):
    """TestClient de la aplicacion real con el centro de predicciones sintetico."""
    from tests import consola_sesion

    from app.api import dependencies as dep
    from app.infrastructure.db.session import get_db
    from app.main import app

    servicio = carteras or e.carteras()
    lab = laboratorio or e.laboratorio()
    c = centro or e.centro(servicio)
    app.dependency_overrides = {
        get_db: lambda: fx._SesionFalsa(conectada),
        dep.get_laboratorio: lambda: lab,
        dep.get_lanzador_de_laboratorio: lambda: lanzador,
        dep.get_carteras: lambda: servicio,
        dep.get_lanzador_de_carteras: lambda: lanzador,
        dep.get_predicciones: lambda: c,
        dep.get_lanzador_de_predicciones: lambda: lanzador,
    }
    return consola_sesion.cliente_de_consola(app, client=client)  # E10.1: sesión legítima explícita


def token(c) -> str:
    return c.get("/predicciones").text.split('name="token_local" value="', 1)[1].split('"', 1)[0]
