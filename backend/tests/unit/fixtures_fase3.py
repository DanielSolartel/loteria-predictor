"""FIXTURES SINTETICAS de la Fase 3 (modelos registrados), solo para pruebas:
el laboratorio de Producto 4 y las carteras de Producto 5 sobre los mismos
historicos sinteticos en memoria, con el almacen del laboratorio compartido
(las carteras solo LEEN sus modelos registrados). Sin PostgreSQL ni Internet.
Ningun dato es real."""
from __future__ import annotations

import dataclasses

from app.application.ml import laboratorio_evaluacion as le
from app.application.use_cases.carteras import CarterasDeModelos, EjecutorCarterasEnEsteProceso
from app.infrastructure.storage.carteras_file_store import CarterasFileStore
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from tests.unit import fixtures_producto1 as fx
from tests.unit import fixtures_producto4 as f4

Reloj = f4.Reloj
LOCAL = f4.LOCAL
lanzar_ya = f4.lanzar_ya
limpiar = f4.limpiar
TAMANOS = {"BALOTO": 110, "BALOTO_REVANCHA": 100, "MILOTO": 87, "COLORLOTO": 90}
PROTOCOLO = le.Protocolo(bloques=2, perfil="reducido")
MODELOS = {"BALOTO": "random_forest_clasificador", "BALOTO_REVANCHA": "extra_trees_clasificador",
           "MILOTO": "random_forest_clasificador", "COLORLOTO": "extra_trees_poisson"}


@dataclasses.dataclass
class Entorno(f4.Entorno):
    @property
    def almacen_laboratorio(self) -> LaboratorioFileStore:
        return LaboratorioFileStore(self.directorio)

    def carteras(self, reloj=None, ejecutor=None) -> CarterasDeModelos:
        directorio = self.directorio.parent / "carteras"
        operacion = directorio / "operacion"
        return CarterasDeModelos(CarterasFileStore(directorio), RegistroEjecucionesArchivo(operacion),
                                 CerrojoPorJuego(operacion), self.abrir,
                                 ejecutor=ejecutor or EjecutorCarterasEnEsteProceso(), reloj=reloj or Reloj(),
                                 modelos=self.almacen_laboratorio)

    def corte(self, juego: str, atras: int = 5) -> int:
        """Corte de entrenamiento: el sorteo cargado `atras` posiciones antes del ultimo."""
        return self.historicos[juego][-1 - atras].numero_sorteo

    def registrar(self, lab, juego: str, modelo: str | None = None, atras: int = 5) -> dict:
        """Compara con corte explicito y entrena el modelo: (informe, ejecucion de entrenamiento)."""
        r = lab.comparar_ahora([juego], PROTOCOLO, corte=self.corte(juego, atras))["juegos"][juego]
        final = lab.entrenar_ahora(r["experimento"], modelo or MODELOS[juego])
        return {"experimento": r["experimento"], "entrenamiento": final, **final["juegos"][juego]}


def entorno(tmp_path, tamanos: dict | None = None) -> Entorno:
    tamanos = {**TAMANOS, **(tamanos or {})}
    historicos = {c: f4.historico(c, n) for c, n in tamanos.items()}
    juegos, resultados, _ = fx.repositorios({c: h for c, h in historicos.items() if c != "COLORLOTO"},
                                            colorloto=historicos.get("COLORLOTO"))
    return Entorno(juegos, resultados, historicos, tmp_path / "laboratorio")


def cliente(e: Entorno, *, client=LOCAL, lanzador=lanzar_ya, conectada: bool = True, laboratorio=None,
            carteras=None):
    """TestClient de la aplicacion real con laboratorio y carteras sinteticos."""
    from fastapi.testclient import TestClient

    from app.api import dependencies as dep
    from app.infrastructure.db.session import get_db
    from app.main import app

    lab = laboratorio or e.laboratorio()
    servicio = carteras or e.carteras()
    app.dependency_overrides = {
        get_db: lambda: fx._SesionFalsa(conectada),
        dep.get_laboratorio: lambda: lab,
        dep.get_lanzador_de_laboratorio: lambda: lanzador,
        dep.get_carteras: lambda: servicio,
        dep.get_lanzador_de_carteras: lambda: lanzador,
    }
    return TestClient(app, base_url="http://localhost:8000", client=client)


def token(c) -> str:
    return f4.token(c)
