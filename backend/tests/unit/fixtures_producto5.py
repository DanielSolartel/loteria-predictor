"""FIXTURES SINTETICAS de Producto 5, solo para pruebas: modelo combinado,
carteras y simulacion con repositorios en memoria (sin PostgreSQL ni
Internet), los historicos sinteticos de Producto 4 y un reloj fijo que avanza.
Ningun dato es real."""
from __future__ import annotations

import dataclasses

import numpy as np

from app.application.ml import laboratorio_variables as lv
from app.application.use_cases.carteras import CarterasDeModelos, EjecutorCarterasEnEsteProceso
from app.infrastructure.storage.carteras_file_store import CarterasFileStore
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from tests.unit import fixtures_producto1 as fx
from tests.unit import fixtures_producto4 as f4

Reloj = f4.Reloj
historico = f4.historico
LOCAL = f4.LOCAL
lanzar_ya = f4.lanzar_ya
# Lo justo para las cuatro reglas: MiLoto con su tamano real (87 sorteos: 27
# objetivos exteriores), ColorLoto con repeticiones de numero.
TAMANOS = {"BALOTO": 100, "BALOTO_REVANCHA": 90, "MILOTO": 87, "COLORLOTO": 90}


@dataclasses.dataclass
class Entorno(f4.Entorno):
    def carteras(self, reloj=None, ejecutor=None) -> CarterasDeModelos:
        """Por defecto entrena y simula en este mismo proceso (rapido, solo
        pruebas); las pruebas de aislamiento pasan `EjecutorCarterasEnProceso`."""
        operacion = self.directorio / "operacion"
        return CarterasDeModelos(CarterasFileStore(self.directorio), RegistroEjecucionesArchivo(operacion),
                                 CerrojoPorJuego(operacion), self.abrir,
                                 ejecutor=ejecutor or EjecutorCarterasEnEsteProceso(), reloj=reloj or Reloj())

    @property
    def almacen(self) -> CarterasFileStore:
        return CarterasFileStore(self.directorio)


def entorno(tmp_path, tamanos: dict | None = None) -> Entorno:
    tamanos = {**TAMANOS, **(tamanos or {})}
    historicos = {c: historico(c, n) for c, n in tamanos.items()}
    juegos, resultados, _ = fx.repositorios({c: h for c, h in historicos.items() if c != "COLORLOTO"},
                                            colorloto=historicos.get("COLORLOTO"))
    return Entorno(juegos, resultados, historicos, tmp_path / "carteras")


def cliente(e: Entorno, *, client=LOCAL, lanzador=lanzar_ya, conectada: bool = True, reloj=None, carteras=None):
    """TestClient de la aplicacion real con el almacen de carteras sintetico."""
    from tests import consola_sesion

    from app.api import dependencies as dep
    from app.infrastructure.db.session import get_db
    from app.main import app

    servicio = carteras or e.carteras(reloj)
    app.dependency_overrides = {
        get_db: lambda: fx._SesionFalsa(conectada),
        dep.get_carteras: lambda: servicio,
        dep.get_lanzador_de_carteras: lambda: lanzador,
    }
    return consola_sesion.cliente_de_consola(app, client=client)  # E10.1: sesión legítima explícita


limpiar = f4.limpiar
PALETA = ("AMARILLO", "AZUL", "BLANCO", "NEGRO", "ROJO", "VERDE")


def fuente_numeros(juego: str, pesos=None, sb=None) -> dict:
    """Vector fuente sintetico de numeros (marginales que suman 5) con pesos dados."""
    reglas = lv.REGLAS[juego]
    n = reglas.rango[1]
    w = np.ones(n) if pesos is None else np.asarray(pesos, dtype=float)
    salida = {"candidatos": list(range(1, n + 1)), "probabilidades": (reglas.cantidad * w / w.sum()).tolist()}
    if reglas.superbalota:
        s = np.ones(16) if sb is None else np.asarray(sb, dtype=float)
        salida["superbalota"] = {"candidatos": list(range(1, 17)), "probabilidades": (s / s.sum()).tolist()}
    return salida


def fuente_colorloto(pesos=None, paleta=PALETA) -> dict:
    """Distribucion sintetica de pares de ColorLoto (masa 1) con pesos dados."""
    candidatos = [[n, c] for n in range(1, 8) for c in paleta]
    w = np.ones(len(candidatos)) if pesos is None else np.asarray(pesos, dtype=float)
    return {"candidatos": candidatos, "probabilidades": (w / w.sum()).tolist(), "paleta": list(paleta)}


def token(c) -> str:
    return c.get("/carteras").text.split('name="token_local" value="', 1)[1].split('"', 1)[0]


def detalle(resultado: dict) -> str:
    """Estado y mensaje COMPLETO de un resultado del servicio (global o de un
    juego) para el texto de una asercion: pytest abrevia la representacion de
    un diccionario y ocultaba el mensaje original de un `fallo`."""
    juegos = resultado.get("juegos")
    if isinstance(juegos, dict):
        lineas = [f"ejecucion {resultado.get('id')}: {resultado.get('estado')}"]
        lineas += [f"{juego}: {r.get('estado')} - {r.get('mensaje')}" for juego, r in juegos.items()]
        return "\n".join(lineas)
    return f"{resultado.get('juego')}: {resultado.get('estado')} - {resultado.get('mensaje')}"
