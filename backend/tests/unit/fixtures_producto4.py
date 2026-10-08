"""FIXTURES SINTETICAS de Producto 4, solo para pruebas: laboratorio con
repositorios en memoria (sin PostgreSQL ni Internet), historicos de tamano
comparable a los reales (Baloto y Revancha ~640 sorteos, MiLoto corta de
~87, ColorLoto ~224) y un reloj fijo que avanza. Ningun dato es real."""
from __future__ import annotations

import contextlib
import dataclasses
from datetime import datetime, timedelta, timezone

from app.application.use_cases.laboratorio import EjecutorEnEsteProceso, LaboratorioDeModelos, Lectura
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from tests.unit import fixtures_producto1 as fx

TAMANOS_REALES = {"BALOTO": 638, "BALOTO_REVANCHA": 638, "MILOTO": 87, "COLORLOTO": 224}
TAMANOS_PEQUENOS = {"BALOTO": 160, "BALOTO_REVANCHA": 160, "MILOTO": 87, "COLORLOTO": 90}


class Reloj:
    def __init__(self, inicio=datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc)):
        self.ahora = inicio

    def __call__(self):
        self.ahora += timedelta(seconds=1)
        return self.ahora


def historico(codigo: str, n: int, semilla: int = 1):
    if codigo == "COLORLOTO":
        return fx.historico_colorloto(n, semilla=semilla)
    return fx.historico_numerico(codigo, n, primero=1 if codigo == "MILOTO" else 2081, semilla=semilla)


@dataclasses.dataclass
class Entorno:
    juegos: object
    resultados: object
    historicos: dict
    directorio: object
    base_caida: bool = False
    lecturas: int = 0

    @contextlib.contextmanager
    def abrir(self):
        self.lecturas += 1
        if self.base_caida:
            raise ConnectionError("connection to server failed: Connection refused")
        yield Lectura(self.juegos, self.resultados)

    def laboratorio(self, reloj=None, ejecutor=None) -> LaboratorioDeModelos:
        """Por defecto entrena en este mismo proceso (rapido, solo pruebas); las
        pruebas de aislamiento pasan `EjecutorEnProceso`."""
        operacion = self.directorio / "operacion"
        return LaboratorioDeModelos(LaboratorioFileStore(self.directorio), RegistroEjecucionesArchivo(operacion),
                                    CerrojoPorJuego(operacion), self.abrir, ejecutor=ejecutor or EjecutorEnEsteProceso(),
                                    reloj=reloj or Reloj())

    @property
    def almacen(self) -> LaboratorioFileStore:
        return LaboratorioFileStore(self.directorio)

    def anadir(self, codigo: str, sorteos: list) -> None:
        """Incorpora sorteos (como si la operacion diaria los hubiera importado)."""
        juego = self.juegos.obtener_por_codigo(codigo)
        destino = self.resultados.colorloto if codigo == "COLORLOTO" else self.resultados.numericos
        destino[juego.id] = [*destino.get(juego.id, []), *sorteos]

    def siguiente(self, codigo: str, cantidad: int = 1, semilla: int = 99):
        """Sorteos sinteticos posteriores al ultimo cargado."""
        ultimo = max((r for r in self.cargados(codigo)), key=lambda r: r.numero_sorteo)
        extra = historico(codigo, cantidad, semilla=semilla)
        return [dataclasses.replace(r, numero_sorteo=ultimo.numero_sorteo + i + 1,
                                    fecha=ultimo.fecha + timedelta(days=3 * (i + 1))) for i, r in enumerate(extra)]

    def cargados(self, codigo: str) -> list:
        juego = self.juegos.obtener_por_codigo(codigo)
        fuente = self.resultados.colorloto if codigo == "COLORLOTO" else self.resultados.numericos
        return sorted(fuente.get(juego.id, []), key=lambda r: r.numero_sorteo)


def entorno(tmp_path, tamanos: dict | None = None) -> Entorno:
    tamanos = {**TAMANOS_PEQUENOS, **(tamanos or {})}
    historicos = {c: historico(c, n) for c, n in tamanos.items()}
    juegos, resultados, _ = fx.repositorios({c: h for c, h in historicos.items() if c != "COLORLOTO"},
                                            colorloto=historicos.get("COLORLOTO"))
    return Entorno(juegos, resultados, historicos, tmp_path / "laboratorio")


LOCAL = ("127.0.0.1", 50000)


def lanzar_ya(funcion, inicio):
    funcion(inicio)


def cliente(e: Entorno, *, client=LOCAL, lanzador=lanzar_ya, conectada: bool = True, reloj=None):
    """TestClient de la aplicacion real con el laboratorio sintetico."""
    from fastapi.testclient import TestClient

    from app.api import dependencies as dep
    from app.infrastructure.db.session import get_db
    from app.main import app

    laboratorio = e.laboratorio(reloj)
    app.dependency_overrides = {
        get_db: lambda: fx._SesionFalsa(conectada),
        dep.get_laboratorio: lambda: laboratorio,
        dep.get_lanzador_de_laboratorio: lambda: lanzador,
    }
    return TestClient(app, base_url="http://localhost:8000", client=client)


def limpiar():
    from app.main import app
    app.dependency_overrides = {}


def token(c) -> str:
    return c.get("/laboratorio").text.split('name="token_local" value="', 1)[1].split('"', 1)[0]
